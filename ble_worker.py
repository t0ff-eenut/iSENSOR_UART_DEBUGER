import asyncio
import logging
from bleak import BleakScanner, BleakClient
from PyQt6.QtCore import QThread, pyqtSignal, QObject

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BLE_WORKER")

# NUS UUIDs
NUS_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
NUS_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E" # PC -> ESP32
NUS_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E" # ESP32 -> PC

class BleWorker(QThread):
    # Signals
    sig_connected = pyqtSignal(str)      # 연결 성공 시 (장치 이름)
    sig_disconnected = pyqtSignal()      # 연결 해제 시
    sig_data_received = pyqtSignal(bytes) # 데이터 수신 시 (Raw Data)
    sig_error = pyqtSignal(str)          # 에러 발생 시
    sig_scan_result = pyqtSignal(list)   # 스캔 결과 (list of BleakDevice)
    sig_status_msg = pyqtSignal(str)     # 상태 메시지

    def __init__(self):
        super().__init__()
        self.client = None
        self.loop = None
        self.target_device = None
        self.is_running = False
        self.should_connect = False
        self.should_scan = False
        self.should_disconnect = False
        
        # 데이터 버퍼링을 위한 변수
        self.rx_buffer = bytearray()

    def run(self):
        """QThread의 메인 루프 (asyncio 이벤트 루프 실행)"""
        self.is_running = True
        
        # 새 이벤트 루프 생성 및 설정
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._async_main())
        except Exception as e:
            logger.error(f"BLE Worker Error: {e}")
            self.sig_error.emit(str(e))
        finally:
            self.loop.close()
            self.is_running = False
            logger.info("BLE Worker Stopped")

    async def _async_main(self):
        """비동기 메인 루프"""
        while self.is_running:
            if self.should_scan:
                self.should_scan = False
                await self._scan_devices()
            
            if self.should_connect and self.target_device:
                self.should_connect = False
                await self._connect_device()
            
            if self.should_disconnect:
                self.should_disconnect = False
                await self._disconnect_device()
            
            # 연결 상태 유지 및 모니터링
            if self.client and self.client.is_connected:
                # 연결된 상태에서 주기적인 작업이 필요하다면 여기에 추가
                pass
            
            await asyncio.sleep(0.1)

    async def _scan_devices(self):
        """BLE 장치 스캔"""
        self.sig_status_msg.emit("Scanning for BLE devices...")
        try:
            devices = await BleakScanner.discover()
            # iSENSOR 장치 필터링 (선택 사항)
            filtered_devices = [d for d in devices if d.name and "iSENSOR" in d.name]
            # 모든 장치 반환 (디버깅용)
            self.sig_scan_result.emit(devices)
            self.sig_status_msg.emit(f"Scan complete. Found {len(devices)} devices.")
        except Exception as e:
            self.sig_error.emit(f"Scan failed: {e}")

    async def _connect_device(self):
        """BLE 장치 연결"""
        if not self.target_device:
            return

        self.sig_status_msg.emit(f"Connecting to {self.target_device.name}...")
        
        try:
            self.client = BleakClient(self.target_device.address, disconnected_callback=self._on_disconnected)
            await self.client.connect()
            
            if self.client.is_connected:
                self.sig_connected.emit(self.target_device.name)
                self.sig_status_msg.emit(f"Connected to {self.target_device.name}")
                
                # NUS TX Notification 구독
                await self.client.start_notify(NUS_TX_CHAR_UUID, self._notification_handler)
                self.sig_status_msg.emit("Notification started")
            else:
                self.sig_error.emit("Connection failed")
                
        except Exception as e:
            self.sig_error.emit(f"Connection error: {e}")
            if self.client:
                await self._disconnect_device()

    async def _disconnect_device(self):
        """BLE 장치 연결 해제"""
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
            finally:
                self.client = None
                self.sig_disconnected.emit()
                self.sig_status_msg.emit("Disconnected")

    def _on_disconnected(self, client):
        """연결 해제 콜백 (BleakClient)"""
        logger.info("Disconnected callback called")
        self.client = None
        self.sig_disconnected.emit()
        self.sig_status_msg.emit("Disconnected (Callback)")

    def _notification_handler(self, sender, data):
        """데이터 수신 핸들러"""
        # Raw 데이터를 그대로 상위(GUI)로 전달하여 처리하게 함
        # 또는 여기서 STX/ETX 파싱을 할 수도 있음.
        # 기존 UART 파서(debug_uart_reader.py)를 재사용하기 위해 Raw 데이터를 전달하는 것이 좋음.
        # 하지만 BLE 패킷은 쪼개져서 올 수 있으므로, 여기서 버퍼링을 하거나
        # 상위에서 버퍼링을 해야 함.
        # debug_uart_reader.py는 시리얼 포트에서 읽는 구조이므로,
        # 여기서는 데이터를 받아 signal로 쏘고, GUI 메인 스레드에서 이를 받아 처리하는 구조가 적절함.
        
        self.sig_data_received.emit(bytes(data))

    # =========================================================================
    # 외부 제어 메서드 (메인 스레드에서 호출)
    # =========================================================================
    
    def start_scan(self):
        """스캔 요청"""
        self.should_scan = True

    def connect_to_device(self, device):
        """연결 요청"""
        self.target_device = device
        self.should_connect = True

    def disconnect(self):
        """연결 해제 요청"""
        self.should_disconnect = True

    def stop(self):
        """워커 중지"""
        self.is_running = False
        self.wait()
