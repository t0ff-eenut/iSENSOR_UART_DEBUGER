"""
iSENSOR UART Debugger - GUI 버전

PyQt6와 pyqtgraph를 사용한 UART 데이터 시각화 도구
"""

import sys
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QGridLayout, QLabel, QTextEdit, QGroupBox, QTabWidget
)
from PyQt6.QtCore import pyqtSlot, QThread, pyqtSignal
import pyqtgraph as pg
from ble_worker import BleWorker
from PyQt6.QtWidgets import QRadioButton, QButtonGroup

# --- 기존 로직 import ---
from uart_protocol.frame_parser import FrameParser
from uart_protocol.payload_parser import PayloadParser
from uart_protocol.data_models import UartFrame, SensorData
from uart_protocol.protocol_config import BaudRate, get_data_type_name, UartDataType


import serial

class UartWorker(QThread):
    """UART 통신을 처리하는 워커 스레드"""
    new_data = pyqtSignal(object)      # 파싱된 SensorData 객체
    log_message = pyqtSignal(str)       # 로그 메시지 (텍스트)
    connection_status = pyqtSignal(bool)  # 연결 상태 (True: 성공, False: 실패)

    def __init__(self, port, baud_rate):
        super().__init__()
        self.port = port
        self.baud_rate = baud_rate
        self.running = False
        self.serial_port = None
        self.parser = FrameParser()

    def run(self):
        """스레드 실행"""
        self.running = True
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            self.connection_status.emit(True)
            self.log_message.emit(f"✓ Connected to {self.port} at {self.baud_rate} bps.")

        except serial.SerialException as e:
            self.log_message.emit(f"✗ Connection failed: {e}")
            self.connection_status.emit(False)
            self.running = False
            return

        while self.running:
            try:
                if self.serial_port.in_waiting > 0:
                    byte_data = self.serial_port.read(self.serial_port.in_waiting)
                    for byte in byte_data:
                        frame = self.parser.feed_byte(byte)
                        if frame:
                            sensor_data = PayloadParser.parse(frame)
                            if sensor_data:
                                self.new_data.emit(sensor_data)

            except serial.SerialException as e:
                self.log_message.emit(f"✗ Serial error: {e}")
                self.running = False
        
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.log_message.emit("Port closed.")
        
        self.connection_status.emit(False)

    def stop(self):
        """스레드 종료"""
        self.running = False
        self.log_message.emit("Requesting to stop UART thread...")
        self.wait(2000) # Wait up to 2 seconds for the thread to finish



class MainWindow(QMainWindow):
    """메인 윈도우"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iSENSOR UART Debugger")
        self.setGeometry(100, 100, 1200, 800)

        # --- 메인 레이아웃 ---
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # --- 좌측 패널 (제어 + 설정) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        left_panel.setFixedWidth(300)

        # --- 우측 패널 (그래프 + 로그) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        # --- 좌측 패널 구성 ---
        # 1. 연결 제어 그룹
        conn_group = QGroupBox("Connection")
        conn_layout = QGridLayout()
        conn_group.setLayout(conn_layout)

        # 통신 모드 선택
        self.mode_group = QButtonGroup()
        self.radio_uart = QRadioButton("UART")
        self.radio_ble = QRadioButton("BLE")
        self.radio_uart.setChecked(True)
        self.mode_group.addButton(self.radio_uart)
        self.mode_group.addButton(self.radio_ble)
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.radio_uart)
        mode_layout.addWidget(self.radio_ble)
        conn_layout.addLayout(mode_layout, 0, 0, 1, 2)

        # UART UI
        self.uart_widget = QWidget()
        uart_layout = QGridLayout()
        self.uart_widget.setLayout(uart_layout)
        uart_layout.setContentsMargins(0, 0, 0, 0)

        self.port_combo = QComboBox()
        self.baud_combo = QComboBox()
        uart_layout.addWidget(QLabel("Port:"), 0, 0)
        uart_layout.addWidget(self.port_combo, 0, 1)
        uart_layout.addWidget(QLabel("Baud:"), 1, 0)
        uart_layout.addWidget(self.baud_combo, 1, 1)

        # BLE UI
        self.ble_widget = QWidget()
        ble_layout = QGridLayout()
        self.ble_widget.setLayout(ble_layout)
        ble_layout.setContentsMargins(0, 0, 0, 0)

        self.ble_scan_btn = QPushButton("Scan")
        self.ble_device_combo = QComboBox()
        ble_layout.addWidget(self.ble_scan_btn, 0, 0)
        ble_layout.addWidget(self.ble_device_combo, 0, 1)
        
        conn_layout.addWidget(self.uart_widget, 1, 0, 1, 2)
        conn_layout.addWidget(self.ble_widget, 2, 0, 1, 2)
        self.ble_widget.hide() # 초기에는 숨김

        self.connect_button = QPushButton("Connect")
        conn_layout.addWidget(self.connect_button, 3, 0, 1, 2)
        
        self.populate_ports()
        self.populate_bauds()

        # UI 이벤트 연결
        self.radio_uart.toggled.connect(self.update_ui_mode)
        self.ble_scan_btn.clicked.connect(self.start_ble_scan)

        # 2. 설정 표시 그룹
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout()
        settings_group.setLayout(settings_layout)
        self.settings_label = QLabel("Not connected")
        self.settings_label.setWordWrap(True)
        settings_layout.addWidget(self.settings_label)

        left_layout.addWidget(conn_group)
        left_layout.addWidget(settings_group)
        left_layout.addStretch(1)

        # --- 우측 패널 구성 ---
        # 1. 그래프 위젯 (상/하 두 개의 탭 위젯)
        
        # 상단: ADC 관련 그래프
        upper_graph_group = QGroupBox("ADC Data Plot")
        upper_graph_layout = QVBoxLayout()
        upper_graph_group.setLayout(upper_graph_layout)
        
        self.upper_plot_tabs = QTabWidget()
        upper_graph_layout.addWidget(self.upper_plot_tabs)
        
        # 하단: HPF 관련 그래프
        lower_graph_group = QGroupBox("HPF Data Plot")
        lower_graph_layout = QVBoxLayout()
        lower_graph_group.setLayout(lower_graph_layout)
        
        self.lower_plot_tabs = QTabWidget()
        lower_graph_layout.addWidget(self.lower_plot_tabs)

        # 각 데이터 타입별 플롯을 저장할 딕셔너리
        self.plots = {}
        self.plot_widgets = {}  # PlotWidget 저장용
        self.threshold_lines = {}  # 임계값 가로선 저장용
        self.exceed_plots = {}  # TP1 초과 지점 표시용 ScatterPlot
        self.exceed_labels = {}  # TP1 초과 개수 표시용 TextItem
        self.stats_labels = {}  # 통계 정보 표시용 TextItem
        self.tp1_value = 0  # TP1 값 저장


        # 2. 로그 위젯
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        right_layout.addWidget(upper_graph_group, stretch=2)  # 상단 그래프
        right_layout.addWidget(lower_graph_group, stretch=2)  # 하단 그래프
        right_layout.addWidget(log_group, stretch=1)  # 로그

        # --- 시그널/슬롯 연결 ---
        self.connect_button.clicked.connect(self.toggle_connection)
        
        self.uart_thread = None
        self.ble_thread = None
        self.ble_devices = [] # 스캔된 장치 리스트 저장용
        self.frame_parser = FrameParser() # BLE용 파서 (UART는 스레드 내부에 있음)

    def log_message(self, message):
        """로그 메시지 출력"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def update_ui_mode(self):
        """통신 모드에 따라 UI 업데이트"""
        if self.radio_uart.isChecked():
            self.uart_widget.show()
            self.ble_widget.hide()
        else:
            self.uart_widget.hide()
            self.ble_widget.show()

    def start_ble_scan(self):
        """BLE 스캔 시작"""
        if self.ble_thread is None:
            self.ble_thread = BleWorker()
            self.ble_thread.sig_scan_result.connect(self.on_ble_scan_result)
            self.ble_thread.sig_status_msg.connect(self.log_message)
            self.ble_thread.sig_error.connect(self.log_message)
            self.ble_thread.sig_connected.connect(self.on_ble_connected)
            self.ble_thread.sig_disconnected.connect(self.on_ble_disconnected)
            self.ble_thread.sig_data_received.connect(self.on_ble_data_received)
            self.ble_thread.start()
        
        self.ble_thread.start_scan()
        self.ble_scan_btn.setEnabled(False)
        self.log_message("Scanning started...")

    @pyqtSlot(list)
    def on_ble_scan_result(self, devices):
        """BLE 스캔 결과 처리"""
        self.ble_scan_btn.setEnabled(True)
        self.ble_device_combo.clear()
        self.ble_devices = devices
        for dev in devices:
            # dev.name이 있으면 사용, 없으면 Unknown
            name = dev.name if dev.name else "Unknown"
            self.ble_device_combo.addItem(f"{name} ({dev.address})", dev)
        
        if not devices:
            self.log_message("No devices found.")

    @pyqtSlot(str)
    def on_ble_connected(self, device_name):
        """BLE 연결 성공 시"""
        self.connect_button.setText("Disconnect")
        self.connect_button.setEnabled(True)
        self.log_message(f"Connected to {device_name}")
        # UI 잠금 등 추가 처리 가능

    @pyqtSlot()
    def on_ble_disconnected(self):
        """BLE 연결 해제 시"""
        self.connect_button.setText("Connect")
        self.connect_button.setEnabled(True)
        self.log_message("Disconnected from BLE device")
        # 스레드 정리? 재사용? -> 재사용 가능하도록 유지

    @pyqtSlot(bytes)
    def on_ble_data_received(self, data):
        """BLE 데이터 수신 시"""
        # self.log_message(f"RX: {len(data)} bytes") # 디버그용 (너무 많으면 주석)
        for byte in data:
            frame = self.frame_parser.feed_byte(byte)
            if frame:
                sensor_data = PayloadParser.parse(frame)
                if sensor_data:
                    self.update_plot(sensor_data)

    def toggle_connection(self):
        """연결/해제 토글"""
        if self.radio_uart.isChecked():
            self.toggle_uart_connection()
        else:
            self.toggle_ble_connection()

    def toggle_ble_connection(self):
        """BLE 연결 토글"""
        if self.ble_thread and self.ble_thread.client and self.ble_thread.client.is_connected:
            # Disconnect
            self.ble_thread.disconnect()
            self.connect_button.setEnabled(False)
        else:
            # Connect
            idx = self.ble_device_combo.currentIndex()
            if idx < 0:
                self.log_message("No device selected.")
                return
            
            device = self.ble_device_combo.itemData(idx)
            if not device:
                return

            if self.ble_thread is None:
                # 스레드가 없으면 생성 (스캔 안하고 바로 연결 시도 시)
                self.ble_thread = BleWorker()
                self.ble_thread.sig_scan_result.connect(self.on_ble_scan_result)
                self.ble_thread.sig_status_msg.connect(self.log_message)
                self.ble_thread.sig_error.connect(self.log_message)
                self.ble_thread.sig_connected.connect(self.on_ble_connected)
                self.ble_thread.sig_disconnected.connect(self.on_ble_disconnected)
                self.ble_thread.sig_data_received.connect(self.on_ble_data_received)
                self.ble_thread.start()

            self.ble_thread.connect_to_device(device)
            self.connect_button.setEnabled(False)

    def toggle_uart_connection(self):
        """기존 UART 연결 로직"""
        if self.uart_thread and self.uart_thread.isRunning():
            self.uart_thread.stop()
            self.connect_button.setEnabled(False)
            self.connect_button.setText("Disconnecting...")
        else:
            port = self.port_combo.currentText()
            try:
                baud = int(self.baud_combo.currentText())
            except ValueError:
                self.log_message("Invalid Baud Rate")
                return

            self.uart_thread = UartWorker(port, baud)
            self.uart_thread.new_data.connect(self.update_plot)
            self.uart_thread.log_message.connect(self.log_message)
            self.uart_thread.connection_status.connect(self.on_connection_status_changed)
            self.uart_thread.start()
            self.connect_button.setEnabled(False)
            self.connect_button.setText("Connecting...")

    @pyqtSlot(bool)
    def on_connection_status_changed(self, is_connected):
        """워커의 연결 상태 변경 시 UI 업데이트"""
        self.connect_button.setEnabled(True)
        if is_connected:
            self.connect_button.setText("Disconnect")
        else:
            self.connect_button.setText("Connect")
            # Clean up the thread object
            if self.uart_thread:
                self.uart_thread.deleteLater()
                self.uart_thread = None


    def populate_ports(self):
        """사용 가능한 시리얼 포트 목록 채우기"""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device}: {port.description}", port.device)
        if not ports:
            self.port_combo.addItem("No ports found")

    def populate_bauds(self):
        """Baud Rate 목록 채우기"""
        self.baud_combo.clear()
        for rate in BaudRate:
            self.baud_combo.addItem(str(rate.value), rate.value)
        self.baud_combo.setCurrentText(str(BaudRate.BAUD_1152000.value))

    @pyqtSlot(object)
    def update_plot(self, data: SensorData):
        """UI 업데이트: 로그, 그래프, 설정 표시"""
        # 1. 로그 텍스트 업데이트
        log_str = self._format_sensor_data_for_log(data)
        self.log_text.append(log_str)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

        # 2. 그래프 업데이트
        if data.adc_buffer:
            self._get_or_create_plot("ADC_BUFFER").setData(data.adc_buffer)
            self._update_stats("ADC_BUFFER", data.adc_buffer)
            self._get_or_create_plot("ADC_BUFFER (Fixed)", fixed_range=(0, 4096)).setData(data.adc_buffer)
            self._update_stats("ADC_BUFFER (Fixed)", data.adc_buffer, y_max=3900)
        elif data.adc_delta_buffer:
            self._get_or_create_plot("ADC_DELTA_BUFFER").setData(data.adc_delta_buffer)
            self._update_stats("ADC_DELTA_BUFFER", data.adc_delta_buffer)
            self._get_or_create_plot("ADC_DELTA_BUFFER (Fixed)", fixed_range=(0, 4096), show_tp1_line=True).setData(data.adc_delta_buffer)
            self._update_stats("ADC_DELTA_BUFFER (Fixed)", data.adc_delta_buffer, y_max=3900)
            
            # ★ TP1 초과 지점 빨간색으로 표시
            self._update_exceed_points("ADC_DELTA_BUFFER (Fixed)", data.adc_delta_buffer, y_max=3900)
        elif data.voltage_buffer:
            self._get_or_create_plot("VOLTAGE_BUFFER").setData(data.voltage_buffer)
            self._update_stats("VOLTAGE_BUFFER", data.voltage_buffer)
        elif data.hpf_buffer:
            self._get_or_create_plot("HPF_BUFFER").setData(data.hpf_buffer)
            self._update_stats("HPF_BUFFER", data.hpf_buffer)
        elif data.voltage_delta_buffer:
            self._get_or_create_plot("VOLTAGE_DELTA_BUFFER").setData(data.voltage_delta_buffer)
            self._update_stats("VOLTAGE_DELTA_BUFFER", data.voltage_delta_buffer)
        elif data.hpf_delta_buffer:
            self._get_or_create_plot("HPF_DELTA_BUFFER").setData(data.hpf_delta_buffer)
            self._update_stats("HPF_DELTA_BUFFER", data.hpf_delta_buffer)
            self._get_or_create_plot("HPF_DELTA_BUFFER (Fixed)", fixed_range=(-50, 2500), show_tp1_line=True).setData(data.hpf_delta_buffer)
            self._update_stats("HPF_DELTA_BUFFER (Fixed)", data.hpf_delta_buffer, y_max=2300)
            
            # ★ TP1 초과 지점 빨간색으로 표시
            self._update_exceed_points("HPF_DELTA_BUFFER (Fixed)", data.hpf_delta_buffer, y_max=2400)

        # 3. 설정값 업데이트
        if data.settings:
            s = data.settings
            self.tp1_value = s.tp1  # TP1 값 저장
            
            # TP1 가로선 업데이트
            self._update_threshold_lines()
            
            settings_str = (
                f"TP1: {s.tp1}\n"
                f"TP2: {s.tp2}\n"
                f"LED Max: {s.led_max_percentage}%\n"
                f"LED Min: {s.led_min_percentage}%\n"
                f"LED Indicator: {s.led_indicator_percentage}%\n"
                f"LED Delay: {s.led_indicator_delay_time_ms} ms\n"
                f"Occupancy Timeout: {s.occupancy_timeout_us} us\n"
                f"Sleep Time: {s.sleep_time} us"
            )
            self.settings_label.setText(settings_str)

    def _calculate_stats(self, data):
        """0이 아닌 값들에 대한 통계 계산"""
        valid_data = [x for x in data if x != 0]
        if not valid_data:
            return 0, 0, 0, 0
        
        count = len(valid_data)
        min_val = min(valid_data)
        max_val = max(valid_data)
        avg_val = sum(valid_data) / count
        return count, min_val, max_val, avg_val

    def _format_array_pretty(self, data, items_per_line=10, indent=4):
        """배열 데이터를 보기 좋게 문자열로 변환"""
        lines = []
        for i in range(0, len(data), items_per_line):
            chunk = data[i:i + items_per_line]
            line = ", ".join(f"{x}" if isinstance(x, int) else f"{x:.2f}" for x in chunk)
            lines.append(f"{' ' * indent}[{i:03d}] {line}")
        return "\n".join(lines)

    def _format_sensor_data_for_log(self, sensor_data: SensorData):
        """센서 데이터를 로그 문자열로 변환"""
        frame = sensor_data.raw_frame
        data_name = get_data_type_name(frame.data_type)
        
        status = "✓" if frame.is_valid else "✗"
        header = (f"{status} [{frame.timestamp.strftime('%H:%M:%S.%f')[:-3]}] "
                  f"Type: {data_name:20s} "
                  f"Length: {frame.data_length:4d} "
                  f"Checksum: 0x{frame.checksum:04X}")

        log_lines = [header]

        # --- 버퍼 데이터 처리 ---
        buffer, name = None, None
        if sensor_data.adc_buffer:
            buffer, name = sensor_data.adc_buffer, "ADC"
        elif sensor_data.voltage_buffer:
            buffer, name = sensor_data.voltage_buffer, "Voltage"
        elif sensor_data.hpf_buffer:
            buffer, name = sensor_data.hpf_buffer, "HPF"
        elif sensor_data.adc_delta_buffer:
            buffer, name = sensor_data.adc_delta_buffer, "ADC Delta"
        elif sensor_data.voltage_delta_buffer:
            buffer, name = sensor_data.voltage_delta_buffer, "Voltage Delta"
        elif sensor_data.hpf_delta_buffer:
            buffer, name = sensor_data.hpf_delta_buffer, "HPF Delta"

        if buffer is not None and name is not None:
            count, min_v, max_v, avg_v = self._calculate_stats(buffer)
            # 정수형 avg 값은 소수점 없이 표현
            avg_str = f"{int(avg_v)}" if isinstance(avg_v, float) and avg_v.is_integer() else f"{avg_v:.2f}"

            log_lines.append(f"  {name}: {len(buffer)} samples (Valid: {count}) "
                                f"(Min: {min_v}, Max: {max_v}, Avg: {avg_str})")
            log_lines.append(self._format_array_pretty(buffer))

        # --- 설정값 처리 ---
        elif sensor_data.settings:
            s = sensor_data.settings
            log_lines.append("  Settings:")
            log_lines.append(f"    - TP1: {s.tp1}")
            log_lines.append(f"    - TP2: {s.tp2}")
            log_lines.append(f"    - LED: Max={s.led_max_percentage}%, Min={s.led_min_percentage}%, Ind={s.led_indicator_percentage}%")
            log_lines.append(f"    - LED Delay: {s.led_indicator_delay_time_ms} ms")
            log_lines.append(f"    - Occupancy Timeout: {s.occupancy_timeout_us} us")
            log_lines.append(f"    - Sleep Time: {s.sleep_time} us")

        return "\n".join(log_lines)

    def _get_or_create_plot(self, name, fixed_range=None, show_tp1_line=False):
        """데이터 타입 이름으로 플롯을 가져오거나 새로 생성. fixed_range가 주어지면 Y축 고정."""
        if name in self.plots:
            # 해당 탭으로 전환 로직 제거
            return self.plots[name]
        else:
            # 새 플롯 위젯과 탭 생성
            plot_widget = pg.PlotWidget()
            
            # ★ 마우스 드래그(팬) 및 휠 줌 비활성화
            plot_widget.setMouseEnabled(x=False, y=False)  # 드래그로 이동 비활성화
            plot_widget.setMenuEnabled(False)  # 우클릭 메뉴 비활성화
            
            if fixed_range:
                plot_widget.setYRange(fixed_range[0], fixed_range[1], padding=0)
                plot_widget.setTitle(f"{name} (Fixed Range)")
            else:
                plot_widget.setTitle(name)
            
            # ★ TP1 임계값 가로선 추가
            if show_tp1_line:
                tp1_line = pg.InfiniteLine(
                    pos=self.tp1_value, 
                    angle=0,  # 0 = 가로선
                    pen=pg.mkPen('r', width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
                    label=f'TP1={self.tp1_value}',
                    labelOpts={'position': 0.95, 'color': 'r', 'fill': (200, 200, 200, 100)}
                )
                plot_widget.addItem(tp1_line)
                self.threshold_lines[name] = tp1_line
                
            plot_item = plot_widget.plot(pen='y', name=name)
            
            # ★ HPF 관련은 하단 탭, 나머지는 상단 탭에 추가
            if "HPF" in name:
                self.lower_plot_tabs.addTab(plot_widget, name)
            else:
                self.upper_plot_tabs.addTab(plot_widget, name)
            
            self.plots[name] = plot_item
            self.plot_widgets[name] = plot_widget  # PlotWidget도 저장
            
            # 새로 추가된 탭으로 자동 전환 로직 제거
            
            return plot_item

    def _update_threshold_lines(self):
        """모든 임계값 가로선의 위치 업데이트"""
        for name, line in self.threshold_lines.items():
            line.setValue(self.tp1_value)
            line.label.setText(f'TP1={self.tp1_value}')

    def _update_stats(self, plot_name, data, y_max=None):
        """그래프 우측 상단에 통계 정보(최소, 최대, 중앙값, 평균) 표시"""
        import statistics
        
        if plot_name not in self.plot_widgets:
            return
        
        plot_widget = self.plot_widgets[plot_name]
        
        # 통계 라벨이 없으면 생성
        if plot_name not in self.stats_labels:
            label = pg.TextItem(
                text='',
                color=(200, 200, 200),  # 연한 회색
                anchor=(1, 0)  # 우측 상단 기준
            )
            label.setFont(pg.QtGui.QFont('Consolas', 9))
            plot_widget.addItem(label)
            self.stats_labels[plot_name] = label
        
        # 통계 계산
        if len(data) > 0:
            min_val = min(data)
            max_val = max(data)
            avg_val = sum(data) / len(data)
            median_val = statistics.median(data)
            
            # 포맷팅 (소수점 1자리)
            stats_text = (
                f"Min: {min_val:.1f}\n"
                f"Max: {max_val:.1f}\n"
                f"Med: {median_val:.1f}\n"
                f"Avg: {avg_val:.1f}"
            )
        else:
            stats_text = "No data"
        
        # 라벨 업데이트
        self.stats_labels[plot_name].setText(stats_text)
        
        # 위치 설정 (우측 상단)
        if y_max is None:
            # 자동 스케일 그래프의 경우 데이터 최대값 기준
            y_pos = max(data) if len(data) > 0 else 100
        else:
            y_pos = y_max - 100  # 고정 범위 그래프의 경우
        
        self.stats_labels[plot_name].setPos(len(data) - 2, y_pos)

    def _update_exceed_points(self, plot_name, data, y_max=3900):
        """TP1 초과 지점을 빨간색 점으로 표시"""
        if plot_name not in self.plot_widgets:
            return
        
        plot_widget = self.plot_widgets[plot_name]
        
        # 기존 ScatterPlot이 없으면 생성
        if plot_name not in self.exceed_plots:
            scatter = pg.ScatterPlotItem(
                pen=None,
                brush=pg.mkBrush('r'),  # 빨간색
                size=8,
                symbol='o'
            )
            plot_widget.addItem(scatter)
            self.exceed_plots[plot_name] = scatter
        
        # 초과 개수 표시용 TextItem 생성
        if plot_name not in self.exceed_labels:
            label = pg.TextItem(
                text='TP1 초과 개수: 0',
                color='r',
                anchor=(1, 0)  # 우측 상단 기준
            )
            label.setFont(pg.QtGui.QFont('Arial', 12, pg.QtGui.QFont.Weight.Bold))
            plot_widget.addItem(label)
            self.exceed_labels[plot_name] = label
        
        # TP1 초과하는 지점 찾기
        exceed_x = []
        exceed_y = []
        for i, value in enumerate(data):
            if value > self.tp1_value and self.tp1_value > 0:
                exceed_x.append(i)
                exceed_y.append(value)
        
        # ScatterPlot 업데이트
        self.exceed_plots[plot_name].setData(exceed_x, exceed_y)
        
        # 초과 개수 라벨 업데이트 (우측 상단 위치)
        exceed_count = len(exceed_x)
        self.exceed_labels[plot_name].setText(f'TP1 초과 개수: {exceed_count}')
        # 우측 상단에 위치 (x=데이터길이-5, y=고정범위 상단)
        self.exceed_labels[plot_name].setPos(len(data) - 5, y_max)

    def closeEvent(self, event):
        """윈도우 종료 이벤트"""
        if self.uart_thread and self.uart_thread.isRunning():
            self.uart_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
