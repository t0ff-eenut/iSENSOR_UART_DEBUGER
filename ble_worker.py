"""
BLE Worker 모듈 — bleak 기반 BLE 통신

UartWorker와 동일한 시그널 인터페이스를 제공하여 MainWindow에서 UART/BLE를 투명하게 교체 가능.

BLE 프로토콜:
    Nordic UART Service (NUS) 사용
    - Service UUID : 6E400001-B5A3-F393-E0A9-E50E24DCCA9E
    - RX (PC→ESP): 6E400002-B5A3-F393-E0A9-E50E24DCCA9E  (write without response)
    - TX (ESP→PC): 6E400003-B5A3-F393-E0A9-E50E24DCCA9E  (notify)

의존성:
    pip install bleak
"""

import asyncio

import PyQt6.QtCore
from PyQt6.QtCore import QThread

import uart_protocol.uart_receive_parser as upurp
import uart_protocol.data_parser         as updp

# ──────────────────────────────────────────────
# Nordic UART Service (NUS) UUID
# ──────────────────────────────────────────────
NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_UUID      = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # PC → ESP32 (write)
NUS_TX_UUID      = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # ESP32 → PC (notify)

ISENSOR_BLE_NAME    = "iSENSOR"   # BLE 광고명 (펌웨어에서 설정한 이름과 일치해야 함)
BLE_SCAN_TIMEOUT_S  = 10.0        # 장치 검색 타임아웃 (초)
BLE_MTU_SIZE        = 247         # BLE 5.0 최대 ATT MTU (bytes) — 전송 청크 크기 상한


class BleSerial:
    """CommandSender.set_serial()에 전달하는 BLE TX 어댑터.

    serial.Serial.write() / is_open 인터페이스를 구현하여
    기존 CommandSender를 수정 없이 BLE에서도 재사용한다.
    """

    def __init__(self, send_callback):
        """
        Args:
            send_callback: bytes를 받아 BLE로 전송하는 콜백 (BleWorker._enqueue_tx)
        """
        self._send_callback = send_callback

    def write(self, data: bytes):
        """serial.Serial.write() 호환 — BLE TX 큐에 넣기."""
        if self._send_callback:
            self._send_callback(data)

    @property
    def is_open(self) -> bool:
        """serial.Serial.is_open 호환."""
        return self._send_callback is not None


class BleWorker(QThread):
    """bleak 기반 BLE 비동기 통신 스레드.

    UartWorker와 동일한 시그널 인터페이스:
        event_new_data          — SensorData 수신 시
        event_connection_status — 연결/해제 시
        log_message             — 로그 문자열

    사용 예:
        worker = BleWorker("iSENSOR")
        worker.event_new_data.connect(self.event_update_ui)
        worker.event_connection_status.connect(self.event_connection_status_changed)
        worker.log_message.connect(self.log_TextEdit.append)
        worker.start()

        # 명령 전송 시
        command_sender.set_serial(worker.ble_serial)
    """

    event_new_data          = PyQt6.QtCore.pyqtSignal(object)   # SensorData
    event_connection_status = PyQt6.QtCore.pyqtSignal(bool)     # True: 연결됨
    log_message             = PyQt6.QtCore.pyqtSignal(str)

    def __init__(self, str_device_name: str = ISENSOR_BLE_NAME):
        super().__init__()
        self.str_device_name: str               = str_device_name
        self._b_running:      bool              = False
        self._loop:           asyncio.AbstractEventLoop = None
        self._tx_queue:       asyncio.Queue     = None

        # 수신 파이프라인 (UartWorker와 동일)
        self.UartReceiveParser_handle = upurp.UartReceiveParser()
        self.DataParser_handle        = updp.DataParser()

        # CommandSender에 전달할 BLE TX 어댑터
        self.ble_serial = BleSerial(self._enqueue_tx)

    # ──────────────────────────────────────────
    # QThread 진입점
    # ──────────────────────────────────────────

    def run(self):
        """asyncio 이벤트 루프를 이 스레드에서 실행."""
        self._b_running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._ble_main())
        except Exception as e:
            self.log_message.emit(f"[BLE] 치명적 오류: {e}")
            self.event_connection_status.emit(False)
        finally:
            self._loop.close()
            self._loop    = None
            self._b_running = False

    def stop(self):
        """스레드 종료 요청."""
        self._b_running = False
        self.log_message.emit("[BLE] 연결 종료 요청...")
        self.wait(3000)

    # ──────────────────────────────────────────
    # BLE 비동기 메인
    # ──────────────────────────────────────────

    async def _ble_main(self):
        """BLE 장치 검색 → 연결 → 수신/송신 루프."""
        try:
            from bleak import BleakClient, BleakScanner
        except ImportError:
            self.log_message.emit("[BLE] 오류: bleak 라이브러리가 설치되지 않았습니다. (pip install bleak)")
            self.event_connection_status.emit(False)
            return

        self._tx_queue = asyncio.Queue()

        # ── 장치 검색 ──
        try:
            self.log_message.emit(f"[BLE] '{self.str_device_name}' 장치 검색 중... (최대 {BLE_SCAN_TIMEOUT_S:.0f}초)")
            device = await BleakScanner.find_device_by_name(
                self.str_device_name, timeout=BLE_SCAN_TIMEOUT_S
            )
        except Exception as e:
            self.log_message.emit(f"[BLE] 스캔 오류: {e}")
            self.event_connection_status.emit(False)
            return

        if device is None:
            self.log_message.emit(f"[BLE] '{self.str_device_name}' 장치를 찾을 수 없습니다.")
            self.event_connection_status.emit(False)
            return

        self.log_message.emit(f"[BLE] 장치 발견: {device.name} ({device.address})")

        # ── 연결 ──
        try:
            async with BleakClient(device) as client:
                self.log_message.emit(f"[BLE] ✓ 연결됨: {device.address}")
                self.event_connection_status.emit(True)

                # Notify 구독 (ESP32 → PC)
                await client.start_notify(NUS_TX_UUID, self._on_notify)

                # TX 큐 처리 루프
                while self._b_running and client.is_connected:
                    try:
                        data: bytes = await asyncio.wait_for(
                            self._tx_queue.get(), timeout=0.1
                        )
                        # BLE MTU 크기 단위로 분할 전송
                        for i in range(0, len(data), BLE_MTU_SIZE):
                            chunk = data[i:i + BLE_MTU_SIZE]
                            await client.write_gatt_char(NUS_RX_UUID, chunk, response=False)
                    except asyncio.TimeoutError:
                        pass  # 타임아웃은 정상 — 루프 계속

                await client.stop_notify(NUS_TX_UUID)

        except Exception as e:
            self.log_message.emit(f"[BLE] 오류: {e}")
        finally:
            self.event_connection_status.emit(False)
            self.log_message.emit("[BLE] 연결 해제됨.")

    # ──────────────────────────────────────────
    # 수신 콜백
    # ──────────────────────────────────────────

    def _on_notify(self, sender, data: bytearray):
        """ESP32 → PC BLE Notify 수신 콜백.

        수신 바이트를 UartReceiveParser에 순서대로 피드하여
        완성된 프레임을 DataParser로 파싱, event_new_data 시그널 발행.
        """
        for byte in data:
            complete = self.UartReceiveParser_handle.feed_byte(byte)
            if complete:
                sensor_data = self.DataParser_handle.data_parser(complete)
                if sensor_data:
                    self.event_new_data.emit(sensor_data)

    # ──────────────────────────────────────────
    # 송신 헬퍼
    # ──────────────────────────────────────────

    def _enqueue_tx(self, data: bytes):
        """BleSerial.write() 호출 시 asyncio TX 큐에 삽입.

        QThread 컨텍스트(메인 스레드)에서 호출되므로
        thread-safe한 run_coroutine_threadsafe 사용.
        """
        if self._loop and self._tx_queue and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._tx_queue.put(bytes(data)), self._loop
            )
