"""
iSENSOR UART Debugger - GUI 버전

PyQt6와 pyqtgraph를 사용한 UART 데이터 시각화 도구
"""
import sys

import serial
from serial.tools import (list_ports)

import PyQt6.QtCore
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QGridLayout, QLabel, QTextEdit, QGroupBox, QTabWidget,
    QSpinBox, QAbstractSpinBox, QMessageBox,
    QSizePolicy
)

import pyqtgraph
import enum
import statistics
from typing import List, Optional

import config                               as cfg
import uart_protocol.uart_protocol_config   as upcfg
import uart_protocol.uart_receive_parser    as upurp
import uart_protocol.data_parser            as updp
import uart_protocol.command_sender         as upcs
import uart_protocol.data_models            as updm

MACRO_FONT_NAME = "font-family: {};"
MACRO_FONT_BOLD = "font-weight: bold;"
MACRO_FONT_SIZE = "font-size: {}pt;"

BUTTON_HOVER_BG = "QPushButton:hover { background-color: %s; }"

MACRO_BORDER_RADIUS = "border-radius: {}px;"
MACRO_PADDING = "padding: {}px;"
MACRO_BACKGROUND_COLOR = "background-color: {};"
MACRO_BORDER_STYLE = "border-style: {};"
MACRO_BORDER_SIZE = "border: {}px;"
MACRO_BORDER_COLOR = "border-color: {};"
MACRO_TEXT_COLOR = "color: {};"

NO_PORT_FOUND = "No ports found"

ADC_RAW_FULL_SCALE_NAME = "ADC Raw Full Scale"
ADC_RAW_ZOOM_SCALE_NAME = "ADC Raw Zoom Scale"
ADC_FFT_FULL_SCALE_NAME = "ADC FFT Full Scale"
ADC_FFT_ZOOM_SCALE_NAME = "ADC FFT Zoom Scale"

class enum_graph_plot_num(enum.IntEnum):
    ADC_RAW = 0
    ADC_FFT = ADC_RAW + 1
class enum_graph_plot_range_opt(enum.IntEnum):
    ALL         = 0
    ADAPTIVE    = ALL + 1
class enum_graph_plot_index(enum.IntEnum):
    STR_PLOT_NAME           = 0
    INT_GRAPH_X_RANGE       = STR_PLOT_NAME + 1
    STR_GRAPH_X_LABEL_POS   = INT_GRAPH_X_RANGE + 1
    STR_GRAPH_X_LABEL       = STR_GRAPH_X_LABEL_POS + 1
    INT_GRAPH_Y_RANGE       = STR_GRAPH_X_LABEL + 1
    STR_GRAPH_Y_LABEL_POS   = INT_GRAPH_Y_RANGE + 1
    STR_GRAPH_Y_LABEL       = STR_GRAPH_Y_LABEL_POS + 1
    STR_LINE_COLOR          = STR_GRAPH_Y_LABEL + 1
    STR_LEGEND_TEXT         = STR_LINE_COLOR + 1

class UartWorker(PyQt6.QtCore.QThread):
    """
    UART 통신을 처리하는 워커 스레드
    """
    event_new_data          = PyQt6.QtCore.pyqtSignal(object)       # 파싱된 SensorData 객체    # emit 이벤트 함수
    log_message             = PyQt6.QtCore.pyqtSignal(str)          # 로그 메시지 (텍스트)
    event_connection_status = PyQt6.QtCore.pyqtSignal(bool)         # 연결 상태 (True: 성공, False: 실패)   # emit 이벤트 함수


    def __init__(self, intput_i_port_num:int, input_i_baud_rate:int):
        super().__init__()
        self.i_port_num:int             = intput_i_port_num
        self.i_baud_rate:int            = input_i_baud_rate

        self.serial_port                = None
        self.b_uart_thread_running:bool = False
        self.UartReceiveParser_handle:upurp.UartReceiveParser   = upurp.UartReceiveParser()
        self.DataParser_handle:updp.DataParser                  = updp.DataParser()

    def run(self):
        """스레드 실행"""
        self.b_uart_thread_running:bool = True

        try:
            self.serial_port:serial.Serial = serial.Serial(
                port        = self.i_port_num,
                baudrate    = self.i_baud_rate,
                bytesize    = serial.EIGHTBITS,
                parity      = serial.PARITY_NONE,
                stopbits    = serial.STOPBITS_ONE,
                timeout     = 1.0
            )
            self.event_connection_status.emit(True)
            self.log_message.emit(f"✓ Connected to {self.i_port_num} at {self.i_baud_rate} bps.")

        except serial.SerialException as e:
            self.log_message.emit(f"✗ Connection failed: {e}")
            self.event_connection_status.emit(False)
            self.b_uart_thread_running = False
                    
            print(f"Payload parsing error: {e}")
            
            return

        while self.b_uart_thread_running:
            try:
                if self.serial_port.in_waiting > 0:
                    byte_data:bytes = self.serial_port.read(self.serial_port.in_waiting)                    
                    for byte in byte_data:
                        complete_receive_data:updm.UartReceiveData = self.UartReceiveParser_handle.feed_byte(byte)
                        if complete_receive_data:
                            sensor_data = self.DataParser_handle.data_parser(complete_receive_data)
                            if sensor_data:
                                self.event_new_data.emit(sensor_data)
                            else:
                                print(f"debugger_start.py | run() | sensor_data = None for type {complete_receive_data.bytes_data_type}")
            except serial.SerialException as e:
                self.log_message.emit(f"✗ Serial error: {e}")
                self.b_uart_thread_running = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.log_message.emit("Port closed.")
        self.event_connection_status.emit(False)

    def stop(self):
        """스레드 종료"""
        self.b_uart_thread_running = False
        self.log_message.emit("Requesting to stop UART thread...")
        self.wait(2000) # Wait up to 2 seconds for the thread to finish

class MainWindow(QMainWindow):
    def adc_bit_2_range(self, input_i_bit:int = 0) -> int:
        return (1 << input_i_bit) - 1

    # GUI Window
    def adc_window_size_setting(self, input_i_adc_window_size:int):
        self.i_adc_window_size:int = input_i_adc_window_size

    # ADC
    def adc_tp1_setting(self, input_i_tp1:int):
        self.i_tp1:int = input_i_tp1
    def adc_tp1_rck_setting(self, input_i_tp1_rck:int):
        self.i_tp1_rck:int = input_i_tp1_rck

    # FFT
    def adc_smapling_rate_setting(self, input_f_sampling_rate:float):
        self.f_sampling_rate:float = input_f_sampling_rate

    def value_init(self):
        self.adc_window_size_setting(300)
        self.adc_tp1_setting(10)
        self.adc_tp1_rck_setting(1000)
        self.adc_smapling_rate_setting(100)
        
        self.A_graph_plot_value:list = []
        """
        STR_PLOT_NAME
        INT_GRAPH_X_RANGE(x), INT_GRAPH_Y_RANGE(y)
        STR_LINE_COLOR, STR_LEGEND_TEXT
        """
        self.A_adc_raw_plot_TabWidget_configs:list = [
            [
                "TEMP_PLOT_NAME - 0.0"
                , 0, "POS", 'LABEL'
                , 0, "POS", 'LABEL'
                , "#000000", "TEMP_LEGEND"
            ],
            [
                "TEMP_PLOT_NAME - 0.1"
                , 0, "POS", 'LABEL'
                , 0, "POS", 'LABEL'
                , "#000000", "TEMP_LEGEND"
            ],
        ]
        self.A_adc_fft_plot_TabWidget_configs:list = [
            # PLOT_NAME_INDEX, INT_GRAPH_X_RANGE(x), INT_GRAPH_Y_RANGE(y)
            [
                "TEMP_PLOT_NAME - 1.0"
                , 0, "POS", 'LABEL'
                , 0, "POS", 'LABEL'
                , "#000000", "TEMP_LEGEND"
            ],
            [
                "TEMP_PLOT_NAME - 1.1"
                , 0, "POS", 'LABEL'
                , 0, "POS", 'LABEL'
                , "#000000", "TEMP_LEGEND"
            ],
        ]
        self.A_graph_plot_value.append(self.A_adc_raw_plot_TabWidget_configs)   # 0
        self.A_graph_plot_value.append(self.A_adc_fft_plot_TabWidget_configs)   # 1
        self.uart_thread = None
        self.command_sender = upcs.CommandSender()  # 명령 송신 객체
        
    def graph_title_setting(self, input_s_graph_title:str, input_enum_graph_plot_num:enum_graph_plot_num = None, input_enum_graph_plot_range_opt:enum_graph_plot_range_opt = None):
        for enum_graph_plot_num_index in range(len(self.A_graph_plot_value)):
            for enum_graph_plot_range_opt_index in range(len(self.A_graph_plot_value[enum_graph_plot_num_index])):
                if (input_enum_graph_plot_num is None) or (input_enum_graph_plot_num == enum_graph_plot_num_index):
                    if (input_enum_graph_plot_range_opt is None) or (input_enum_graph_plot_range_opt == enum_graph_plot_range_opt_index):
                        self.A_graph_plot_value[enum_graph_plot_num_index][enum_graph_plot_range_opt_index][enum_graph_plot_index.STR_PLOT_NAME] = input_s_graph_title

    def graph_x_range_setting(self, input_i_graph_x_range:int, input_enum_graph_plot_num:enum_graph_plot_num = None, input_enum_graph_plot_range_opt:enum_graph_plot_range_opt = None):
        for enum_graph_plot_num_index in range(len(self.A_graph_plot_value)):
            for enum_graph_plot_range_opt_index in range(len(self.A_graph_plot_value[enum_graph_plot_num_index])):
                if (input_enum_graph_plot_num is None) or (input_enum_graph_plot_num == enum_graph_plot_num_index):
                    if (input_enum_graph_plot_range_opt is None) or (input_enum_graph_plot_range_opt == enum_graph_plot_range_opt_index):
                        self.A_graph_plot_value[enum_graph_plot_num_index][enum_graph_plot_range_opt_index][enum_graph_plot_index.INT_GRAPH_X_RANGE] = input_i_graph_x_range

    def graph_x_label_pos_setting(self, input_s_graph_x_label_pos:str, input_enum_graph_plot_num:enum_graph_plot_num = None, input_enum_graph_plot_range_opt:enum_graph_plot_range_opt = None):
        for enum_graph_plot_num_index in range(len(self.A_graph_plot_value)):
            for enum_graph_plot_range_opt_index in range(len(self.A_graph_plot_value[enum_graph_plot_num_index])):
                if (input_enum_graph_plot_num is None) or (input_enum_graph_plot_num == enum_graph_plot_num_index):
                    if (input_enum_graph_plot_range_opt is None) or (input_enum_graph_plot_range_opt == enum_graph_plot_range_opt_index):
                        self.A_graph_plot_value[enum_graph_plot_num_index][enum_graph_plot_range_opt_index][enum_graph_plot_index.STR_GRAPH_X_LABEL_POS] = input_s_graph_x_label_pos

    def graph_x_label_setting(self, input_s_graph_x_label:str, input_enum_graph_plot_num:enum_graph_plot_num = None, input_enum_graph_plot_range_opt:enum_graph_plot_range_opt = None):
        for enum_graph_plot_num_index in range(len(self.A_graph_plot_value)):
            for enum_graph_plot_range_opt_index in range(len(self.A_graph_plot_value[enum_graph_plot_num_index])):
                if (input_enum_graph_plot_num is None) or (input_enum_graph_plot_num == enum_graph_plot_num_index):
                    if (input_enum_graph_plot_range_opt is None) or (input_enum_graph_plot_range_opt == enum_graph_plot_range_opt_index):
                        self.A_graph_plot_value[enum_graph_plot_num_index][enum_graph_plot_range_opt_index][enum_graph_plot_index.STR_GRAPH_X_LABEL] = input_s_graph_x_label

    def graph_y_range_setting(self, input_i_graph_y_range:int, input_enum_graph_plot_num:enum_graph_plot_num = None, input_enum_graph_plot_range_opt:enum_graph_plot_range_opt = None):
        for enum_graph_plot_num_index in range(len(self.A_graph_plot_value)):
            for enum_graph_plot_range_opt_index in range(len(self.A_graph_plot_value[enum_graph_plot_num_index])):
                if (input_enum_graph_plot_num is None) or (input_enum_graph_plot_num == enum_graph_plot_num_index):
                    if (input_enum_graph_plot_range_opt is None) or (input_enum_graph_plot_range_opt == enum_graph_plot_range_opt_index):
                        self.A_graph_plot_value[enum_graph_plot_num_index][enum_graph_plot_range_opt_index][enum_graph_plot_index.INT_GRAPH_Y_RANGE] = input_i_graph_y_range

    def graph_y_label_pos_setting(self, input_s_graph_y_label_pos:str, input_enum_graph_plot_num:enum_graph_plot_num = None, input_enum_graph_plot_range_opt:enum_graph_plot_range_opt = None):
        for enum_graph_plot_num_index in range(len(self.A_graph_plot_value)):
            for enum_graph_plot_range_opt_index in range(len(self.A_graph_plot_value[enum_graph_plot_num_index])):
                if (input_enum_graph_plot_num is None) or (input_enum_graph_plot_num == enum_graph_plot_num_index):
                    if (input_enum_graph_plot_range_opt is None) or (input_enum_graph_plot_range_opt == enum_graph_plot_range_opt_index):
                        self.A_graph_plot_value[enum_graph_plot_num_index][enum_graph_plot_range_opt_index][enum_graph_plot_index.STR_GRAPH_Y_LABEL_POS] = input_s_graph_y_label_pos

    def graph_y_label_setting(self, input_s_graph_y_label:str, input_enum_graph_plot_num:enum_graph_plot_num = None, input_enum_graph_plot_range_opt:enum_graph_plot_range_opt = None):
        for enum_graph_plot_num_index in range(len(self.A_graph_plot_value)):
            for enum_graph_plot_range_opt_index in range(len(self.A_graph_plot_value[enum_graph_plot_num_index])):
                if (input_enum_graph_plot_num is None) or (input_enum_graph_plot_num == enum_graph_plot_num_index):
                    if (input_enum_graph_plot_range_opt is None) or (input_enum_graph_plot_range_opt == enum_graph_plot_range_opt_index):
                        self.A_graph_plot_value[enum_graph_plot_num_index][enum_graph_plot_range_opt_index][enum_graph_plot_index.STR_GRAPH_Y_LABEL] = input_s_graph_y_label

    def graph_line_color_setting(self, input_s_graph_line_color:str, input_enum_graph_plot_num:enum_graph_plot_num = None, input_enum_graph_plot_range_opt:enum_graph_plot_range_opt = None):
        for enum_graph_plot_num_index in range(len(self.A_graph_plot_value)):
            for enum_graph_plot_range_opt_index in range(len(self.A_graph_plot_value[enum_graph_plot_num_index])):
                if (input_enum_graph_plot_num is None) or (input_enum_graph_plot_num == enum_graph_plot_num_index):
                    if (input_enum_graph_plot_range_opt is None) or (input_enum_graph_plot_range_opt == enum_graph_plot_range_opt_index):
                        self.A_graph_plot_value[enum_graph_plot_num_index][enum_graph_plot_range_opt_index][enum_graph_plot_index.STR_LINE_COLOR] = input_s_graph_line_color

    def graph_legend_setting(self, input_s_graph_legend:str, input_enum_graph_plot_num:enum_graph_plot_num = None, input_enum_graph_plot_range_opt:enum_graph_plot_range_opt = None):
        for enum_graph_plot_num_index in range(len(self.A_graph_plot_value)):
            for enum_graph_plot_range_opt_index in range(len(self.A_graph_plot_value[enum_graph_plot_num_index])):
                if (input_enum_graph_plot_num is None) or (input_enum_graph_plot_num == enum_graph_plot_num_index):
                    if (input_enum_graph_plot_range_opt is None) or (input_enum_graph_plot_range_opt == enum_graph_plot_range_opt_index):
                        self.A_graph_plot_value[enum_graph_plot_num_index][enum_graph_plot_range_opt_index][enum_graph_plot_index.STR_LEGEND_TEXT] = input_s_graph_legend

    """메인 윈도우"""
    def __init__(self):
        super().__init__()

        self.value_init()

        #TODO : str -> config로 옮기기
        self.graph_title_setting(ADC_RAW_FULL_SCALE_NAME, enum_graph_plot_num.ADC_RAW, enum_graph_plot_range_opt.ALL)
        self.graph_title_setting(ADC_RAW_ZOOM_SCALE_NAME, enum_graph_plot_num.ADC_RAW, enum_graph_plot_range_opt.ADAPTIVE)
        self.graph_x_range_setting(self.i_adc_window_size, enum_graph_plot_num.ADC_RAW)
        self.graph_x_label_pos_setting("bottom", enum_graph_plot_num.ADC_RAW)
        self.graph_x_label_setting("시간(10ms)", enum_graph_plot_num.ADC_RAW)
        self.graph_y_range_setting(self.adc_bit_2_range(12), enum_graph_plot_num.ADC_RAW, enum_graph_plot_range_opt.ALL)
        self.graph_y_label_pos_setting("left", enum_graph_plot_num.ADC_RAW)
        self.graph_y_label_setting("ADC", enum_graph_plot_num.ADC_RAW)
        self.graph_line_color_setting(cfg.ADC_RAW_LINE_COLOR, enum_graph_plot_num.ADC_RAW)
        self.graph_legend_setting('ADC', enum_graph_plot_num.ADC_RAW)

        self.graph_title_setting(ADC_FFT_FULL_SCALE_NAME, enum_graph_plot_num.ADC_FFT, enum_graph_plot_range_opt.ALL)
        self.graph_title_setting(ADC_FFT_ZOOM_SCALE_NAME, enum_graph_plot_num.ADC_FFT, enum_graph_plot_range_opt.ADAPTIVE)
        self.graph_x_range_setting(100, enum_graph_plot_num.ADC_FFT)
        self.graph_x_label_pos_setting("bottom", enum_graph_plot_num.ADC_FFT)
        self.graph_x_label_setting("주파수(Hz)", enum_graph_plot_num.ADC_FFT)
        # self.graph_y_range_setting(150, enum_graph_plot_num.ADC_FFT, enum_graph_plot_range_opt.ALL)
        self.graph_y_label_pos_setting("left", enum_graph_plot_num.ADC_FFT)
        self.graph_y_label_setting("강도", enum_graph_plot_num.ADC_FFT)
        self.graph_line_color_setting(cfg.ADC_FFT_LINE_COLOR, enum_graph_plot_num.ADC_FFT)
        self.graph_legend_setting('FFT 분포', enum_graph_plot_num.ADC_FFT)

        self.setWindowTitle(cfg.WINDOW_TITLE)
        self.setGeometry(
            cfg.WINDOW_POSITION_X
            , cfg.WINDOW_POSITION_Y
            , cfg.WINDOW_WIDTH
            , cfg.WINDOW_HEIGHT
            )

        # --- 메인 레이아웃 ---
        self.main_Widget = QWidget()                     # 1. 대상 위젯 생성
        self.setCentralWidget(self.main_Widget)
        self.main_HBoxLayout = QHBoxLayout()            # 2. 가로 방향 레이아웃 생성    (자식 위젯들을 좌→우로 배치)
        self.main_Widget.setLayout(self.main_HBoxLayout)     # 3. 레이아웃 적용
        
        # --- 좌측 패널 (제어 + 설정) ---
        self.left_Widget = QWidget()                     # 1. 대상 위젯 생성
        self.left_Widget.setFixedWidth(cfg.LEFT_BOX_WIDTH)              # * 위젯 가로 사이즈 설정

        self.left_Widget.setStyleSheet(""
                                       + MACRO_BORDER_RADIUS.format(6)
                                       + MACRO_PADDING.format(2)
                                       + MACRO_BACKGROUND_COLOR.format(cfg.BACKGROUND_COLOR)
                                       + MACRO_BORDER_SIZE.format(2)
                                       + MACRO_BORDER_STYLE.format('solid')
                                       + MACRO_BORDER_COLOR.format(cfg.LINE_COLOR)
                                       + MACRO_TEXT_COLOR.format(cfg.TEXT_COLOR)
                                       )
        self.main_HBoxLayout.addWidget(self.left_Widget, stretch=1)     # 1-1. 상위 레이아웃에 위젯 적용

# --- 좌측 패널 구성 ---
        self.left_VBoxLayout = QVBoxLayout()            # 2. 세로 방향 레이아웃 생성
        self.left_Widget.setLayout(self.left_VBoxLayout)     # 3. 레이아웃을 대상 위젯에 적용
# --- 제어창 표시 설정 ---
        self.left_control_Label = QLabel("제어창")             # 1. 대상 위젯 생성
        self.left_control_Label.setStyleSheet(""
                                              + MACRO_FONT_BOLD
                                              + MACRO_FONT_SIZE.format(14)
                                              )  # * 위젯 폰트 설정
        self.left_control_Label.setFixedHeight(30)             # * 위젯 가로 사이즈 설정
        self.left_VBoxLayout.addWidget(self.left_control_Label)    # 1-1. 상위 레이아웃에 위젯 적용
# --- Connection 그룹 설정 ---
        self.connection_GroupBox = QGroupBox("Connection")             # 1. 대상 위젯 생성
        # self.connection_GroupBox.setFlat(True)
        self.connection_GridLayout = QGridLayout()                     # 2. Grid 레이아웃 생성 
        self.connection_GroupBox.setLayout(self.connection_GridLayout)            # 3. 레이아웃을 대상 위젯에 적용
        self.left_VBoxLayout.addWidget(self.connection_GroupBox)           # 1-1. 상위 레이아웃에 위젯 적용

        # --- 📶포트 설정 ---
        # --- 포트 라벨 설정 ---
        self.port_sel_Label = QLabel("📶포트: ")
        self.port_sel_Label.setStyleSheet(""
                                          + MACRO_FONT_BOLD
                                          # + MACRO_BORDER_RADIUS.format(6)
                                          + MACRO_BORDER_STYLE.format('none')
                                          )
        self.port_sel_Label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)    # 레이블은 텍스트 크기 위주, 늘어나지 않게
        self.connection_GridLayout.addWidget(self.port_sel_Label, 0, 0)         # 3. 위젯을 대상 레이아웃에 적용
        # --- 포트 목록 및 버튼 설정 ---
        self.port_sel_HBoxLayout = QHBoxLayout()                    # 2. 가로 방향 레이아웃 생성
        self.connection_GridLayout.addLayout(self.port_sel_HBoxLayout, 0, 1)         # 3. 위젯을 대상 레이아웃에 적용
        self.port_sel_ComboBox = QComboBox()                               # 1. 대상 위젯 생성
        self.port_sel_HBoxLayout.addWidget(self.port_sel_ComboBox)         # 3. 위젯을 대상 레이아웃에 적용

        self.port_search_PushButton = QPushButton("🔍검색")     # 1. 대상 위젯 생성
        self.port_search_PushButton.setStyleSheet(""
                                                  + MACRO_FONT_BOLD 
                                                  )
        self.port_search_PushButton.setStyleSheet(""
                                                  + BUTTON_HOVER_BG % cfg.LINE_COLOR
                                                  )
        self.port_search_PushButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)  # 레이블은 텍스트 크기 위주, 늘어나지 않게
        self.port_search_PushButton.clicked.connect(self.event_refresh_ports)
        self.port_sel_HBoxLayout.addWidget(self.port_search_PushButton)         # 3. 위젯을 대상 레이아웃에 적용

        # --- ⚡보드레이트 설정 ---
        # --- 보드레이트 라벨 설정 ---
        self.baudrate_sel_Label = QLabel("⚡보드레이트: ")
        self.baudrate_sel_Label.setStyleSheet(""
                                              + MACRO_FONT_BOLD
                                              # + MACRO_BORDER_RADIUS.format(6)
                                              + MACRO_BORDER_STYLE.format('none')
                                              )
        self.baudrate_sel_Label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)    # 레이블은 텍스트 크기 위주, 늘어나지 않게
        self.connection_GridLayout.addWidget(self.baudrate_sel_Label, 1, 0)         # 3. 위젯을 대상 레이아웃에 적용
        # --- 보드레이트 목록 설정 ---
        self.baudrate_sel_ComboBox = QComboBox()                               # 1. 대상 위젯 생성
        self.connection_GridLayout.addWidget(self.baudrate_sel_ComboBox, 1, 1)         # 3. 위젯을 대상 레이아웃에 적용
        
        # --- 연결하기 버튼 설정 ---
        self.port_connect_PushButton = QPushButton("🔌연결하기")
        self.port_connect_PushButton.setStyleSheet(""
                                                  + MACRO_FONT_BOLD 
                                                  )
        self.port_connect_PushButton.setStyleSheet(""
                                                  + BUTTON_HOVER_BG % cfg.LINE_COLOR
                                                  )
        self.port_connect_PushButton.clicked.connect(self.event_port_connection) # 버튼 기능 구현
        self.connection_GridLayout.addWidget(self.port_connect_PushButton, 2, 0, 1, 2)

#################################################################################################################
        # # ESP32 리셋 버튼 (Connect 버튼 바로 아래)
        # self.reset_button = QPushButton("🔄 ESP32 리셋")
        # self.reset_button.setEnabled(False)
        # self.reset_button.setStyleSheet("QPushButton { color: #cc3333; }")
        # self.connection_GridLayout.addWidget(self.reset_button, 3, 0, 1, 2)
#################################################################################################################
        
        self.insert_ports_to_ComboBox()
        self.insert_baudrates_to_ComboBox()

# --- Status 그룹 설정 ---
        self.status_GroupBox = QGroupBox("Setting")             # 1. 대상 위젯 생성
        self.status_GroupBox.setStyleSheet(""
                                           + MACRO_BORDER_RADIUS.format(6)
                                           )
        self.status_GridLayout = QGridLayout()                     # 2. Grid 레이아웃 생성
        self.status_GroupBox.setLayout(self.status_GridLayout)            # 3. 레이아웃을 대상 위젯에 적용
        self.left_VBoxLayout.addWidget(self.status_GroupBox)           # 1-1. 상위 레이아웃에 위젯 적용

        # --- 제어창 표시 설정 ---
        self.connect_status_Label = QLabel("Not connected")
        self.connect_status_Label.setStyleSheet(""
                                                + MACRO_FONT_BOLD
                                                + MACRO_FONT_SIZE.format(14)
                                                + MACRO_BORDER_STYLE.format('none')
                                                )
        self.connect_status_Label.setWordWrap(True)             # 자동 줄넘김
        self.status_GridLayout.addWidget(self.connect_status_Label)

        # --- 재실 여부 표시 설정 ---
        self.occupancy_Label = QLabel("⚪ 재실 상태: 대기 중")
        self.occupancy_Label.setStyleSheet(""
                                           + MACRO_FONT_BOLD
                                           + MACRO_FONT_SIZE.format(14)
                                           )  # * 위젯 폰트 설정
        self.status_GridLayout.addWidget(self.occupancy_Label)

        # --- PIR 출력 표시 설정 ---
        self.pir_output_Label = QLabel("💤 PIR 출력: 대기 중")  # 👀
        self.pir_output_Label.setStyleSheet(""
                                            + MACRO_FONT_BOLD
                                            + MACRO_FONT_SIZE.format(14)
                                            )  # * 위젯 폰트 설정
        self.status_GridLayout.addWidget(self.pir_output_Label)

############### NVS 설정 기능 구현하기 ###############################################################################
        # # --- 설정 값 불러오기 버튼 설정 ---
        # self.nvs_setting_read_PushButton = QPushButton("🔄 NVS 설정 값 불러오기")
        # self.nvs_setting_read_PushButton.setStyleSheet(""
        #     + MACRO_FONT_BOLD
        #     )  # * 위젯 폰트 설정
        # self.nvs_setting_read_PushButton.setStyleSheet("""
        #     QPushButton:hover {
        #     background-color: #3366ff;
        #     }
        #     """)
        # self.nvs_setting_read_PushButton.clicked.connect(self.event_port_connection) # 버튼 기능 구현
        # self.status_GridLayout.addWidget(self.nvs_setting_read_PushButton)

        # # --- 설정 값 저장하기 버튼 설정 ---
        # self.nvs_setting_read_PushButton = QPushButton("🔄 NVS 설정 값 불러오기")
        # self.nvs_setting_read_PushButton.setStyleSheet(""
        #     + MACRO_FONT_BOLD
        #     )  # * 위젯 폰트 설정
        # self.nvs_setting_read_PushButton.setStyleSheet("""
        #     QPushButton:hover {
        #     background-color: #3366ff;
        #     }
        #     """)
        # self.nvs_setting_read_PushButton.clicked.connect(self.event_port_connection) # 버튼 기능 구현
        # self.status_GridLayout.addWidget(self.nvs_setting_read_PushButton)
############### NVS 설정 기능 구현하기 ###############################################################################

# --- TP 제어 그룹 설정 ---
        self.tp_setting_GroupBox = QGroupBox("TP Setting")             # 1. 대상 위젯 생성
        self.tp_setting_GroupBox.setStyleSheet(""
                                               + MACRO_BORDER_RADIUS.format(6)
                                               )
        self.tp_setting_GridLayout = QGridLayout()                     # 2. Grid 레이아웃 생성
        self.tp_setting_GroupBox.setLayout(self.tp_setting_GridLayout)            # 3. 레이아웃을 대상 위젯에 적용
        self.left_VBoxLayout.addWidget(self.tp_setting_GroupBox)           # 1-1. 상위 레이아웃에 위젯 적용

        # --- TP1 설정 ---
        # --- TP1 라벨 설정 ---
        self.tp1_Label = QLabel("TP1: ")
        self.tp1_Label.setStyleSheet(""
                                     + MACRO_FONT_BOLD
                                     + MACRO_BORDER_STYLE.format('none')
                                     )
        self.tp1_Label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)    # 레이블은 텍스트 크기 위주, 늘어나지 않게
        self.tp_setting_GridLayout.addWidget(self.tp1_Label, 0, 0)         # 3. 위젯을 대상 레이아웃에 적용

        self.tp1_HBoxLayout = QHBoxLayout()                    # 2. 가로 방향 레이아웃 생성
        self.tp_setting_GridLayout.addLayout(self.tp1_HBoxLayout, 0, 1)         # 3. 위젯을 대상 레이아웃에 적용
        self.tp1_SpinBox = QSpinBox()
        self.tp1_SpinBox.setMinimum(0)
        self.tp1_SpinBox.setMaximum(4095)
        self.tp1_SpinBox.setValue(300)  # 기본값
        # 내장 버튼을 숨기고 외부 버튼으로 대체
        self.tp1_SpinBox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.tp1_HBoxLayout.addWidget(self.tp1_SpinBox)
        # 별도 버튼: 상승 / 하강
        self.tp1_up_btn = QPushButton("▲")
        self.tp1_down_btn = QPushButton("▼")
        for b in (self.tp1_up_btn, self.tp1_down_btn):
            b.setFixedWidth(28)
            b.setFocusPolicy(PyQt6.QtCore.Qt.FocusPolicy.NoFocus)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.tp1_up_btn.clicked.connect(self.tp1_SpinBox.stepUp)
        self.tp1_down_btn.clicked.connect(self.tp1_SpinBox.stepDown)
        self.tp1_HBoxLayout.addWidget(self.tp1_up_btn)
        self.tp1_HBoxLayout.addWidget(self.tp1_down_btn)

        # --- TP1 RCK 설정 ---
        # --- TP1 RCK 라벨 설정 ---
        self.tp1_rck_Label = QLabel("TP1 RCK: ")
        self.tp1_rck_Label.setStyleSheet(""
                                         + MACRO_FONT_BOLD
                                         + MACRO_BORDER_STYLE.format('none')
                                         )
        self.tp1_rck_Label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)    # 레이블은 텍스트 크기 위주, 늘어나지 않게
        self.tp_setting_GridLayout.addWidget(self.tp1_rck_Label, 1, 0)         # 3. 위젯을 대상 레이아웃에 적용

        self.tp1_rck_HBoxLayout = QHBoxLayout()                    # 2. 가로 방향 레이아웃 생성
        self.tp_setting_GridLayout.addLayout(self.tp1_rck_HBoxLayout, 1, 1)         # 3. 위젯을 대상 레이아웃에 적용
        self.tp1_rck_SpinBox = QSpinBox()
        self.tp1_rck_SpinBox.setMinimum(0)
        self.tp1_rck_SpinBox.setMaximum(4095)
        self.tp1_rck_SpinBox.setValue(2000)  # 기본값
        # 내장 버튼을 숨기고 외부 버튼으로 대체
        self.tp1_rck_SpinBox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.tp1_rck_HBoxLayout.addWidget(self.tp1_rck_SpinBox)
        # 별도 버튼: 상승 / 하강
        self.tp1_rkc_up_btn = QPushButton("▲")
        self.tp1_rkc_down_btn = QPushButton("▼")
        for b in (self.tp1_rkc_up_btn, self.tp1_rkc_down_btn):
            b.setFixedWidth(28)
            b.setFocusPolicy(PyQt6.QtCore.Qt.FocusPolicy.NoFocus)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.tp1_rkc_up_btn.clicked.connect(self.tp1_rck_SpinBox.stepUp)
        self.tp1_rkc_down_btn.clicked.connect(self.tp1_rck_SpinBox.stepDown)
        self.tp1_rck_HBoxLayout.addWidget(self.tp1_rkc_up_btn)
        self.tp1_rck_HBoxLayout.addWidget(self.tp1_rkc_down_btn)


        # --- TP2 설정 ---
        # --- TP2 라벨 설정 ---
        self.tp2_Label = QLabel("TP2: ")
        self.tp2_Label.setStyleSheet(""
                                     + MACRO_FONT_BOLD
                                     + MACRO_BORDER_STYLE.format('none')
                                     )
        self.tp2_Label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)    # 레이블은 텍스트 크기 위주, 늘어나지 않게
        self.tp_setting_GridLayout.addWidget(self.tp2_Label, 2, 0)         # 3. 위젯을 대상 레이아웃에 적용

        self.tp2_HBoxLayout = QHBoxLayout()                    # 2. 가로 방향 레이아웃 생성
        self.tp_setting_GridLayout.addLayout(self.tp2_HBoxLayout, 2, 1)         # 3. 위젯을 대상 레이아웃에 적용
        self.tp2_SpinBox = QSpinBox()
        self.tp2_SpinBox.setMinimum(0)
        self.tp2_SpinBox.setMaximum(2147483647)  # SpinBox는 int32 최대값까지만 지원
        self.tp2_SpinBox.setValue(10)  # 기본값
        # 내장 버튼을 숨기고 외부 버튼으로 대체
        self.tp2_SpinBox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.tp2_HBoxLayout.addWidget(self.tp2_SpinBox)
        # 별도 버튼: 상승 / 하강
        self.tp2_up_btn = QPushButton("▲")
        self.tp2_down_btn = QPushButton("▼")
        for b in (self.tp2_up_btn, self.tp2_down_btn):
            b.setFixedWidth(28)
            b.setFocusPolicy(PyQt6.QtCore.Qt.FocusPolicy.NoFocus)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.tp2_up_btn.clicked.connect(self.tp2_SpinBox.stepUp)
        self.tp2_down_btn.clicked.connect(self.tp2_SpinBox.stepDown)
        self.tp2_HBoxLayout.addWidget(self.tp2_up_btn)
        self.tp2_HBoxLayout.addWidget(self.tp2_down_btn)

        # --- TP 값 저장하기 버튼 설정 ---
        self.tp_setting_PushButton = QPushButton("🔄 TP 값 전송하기")
        # self.tp_setting_PushButton.setStyleSheet(MACRO_FONT_BOLD + BUTTON_HOVER_BG.format('#3366ff'))
        self.tp_setting_PushButton.setStyleSheet(""
                                                  + MACRO_FONT_BOLD 
                                                  )
        self.tp_setting_PushButton.setStyleSheet(""
                                                  + BUTTON_HOVER_BG % cfg.LINE_COLOR
                                                  )
                                                  
        self.tp_setting_PushButton.clicked.connect(self.event_send_tp_command) # 버튼 기능 구현
        self.tp_setting_GridLayout.addWidget(self.tp_setting_PushButton, 4, 0, 1, 2)

        # --- 우측 패널 (그래프 + 로그) ---
        self.right_Widget = QWidget()                    # 1. 대상 위젯 생성
        self.right_Widget.setStyleSheet(""
                                        + MACRO_BORDER_RADIUS.format(6)
                                        + MACRO_PADDING.format(2)
                                        + MACRO_BACKGROUND_COLOR.format(cfg.BACKGROUND_COLOR)
                                        + MACRO_BORDER_SIZE.format(2)
                                        + MACRO_BORDER_STYLE.format('solid')
                                        + MACRO_BORDER_COLOR.format(cfg.LINE_COLOR)
                                        + MACRO_TEXT_COLOR.format(cfg.TEXT_COLOR)
                                        )

        self.main_HBoxLayout.addWidget(self.right_Widget, stretch=2)    # 1-1. 상위 레이아웃에 위젯 적용
        self.right_VBoxLayout = QVBoxLayout()           # 2. 세로 방향 레이아웃 생성
        self.right_Widget.setLayout(self.right_VBoxLayout)   # 3. 레이아웃을 대상 위젯에 적용

        self.adc_raw_graph_GroupBox = QGroupBox("ADC RAW Data Plot")             # 1. 대상 위젯 생성
        self.adc_raw_graph_GroupBox.setStyleSheet(""
                                                  + MACRO_PADDING.format(10)
                                                  )
        self.right_VBoxLayout.addWidget(self.adc_raw_graph_GroupBox, stretch=2)           # 1-1. 상위 레이아웃에 위젯 적용

        self.adc_raw_graph_VBoxLayout = QVBoxLayout()                     # 2. 세로 방향 레이아웃 생성
        self.adc_raw_graph_GroupBox.setLayout(self.adc_raw_graph_VBoxLayout)            # 3. 레이아웃을 대상 위젯에 적용

        self.adc_raw_plot_TabWidget = QTabWidget()
        self.adc_raw_plot_TabWidget.setStyleSheet(""
                                                  + MACRO_BORDER_STYLE.format('none')
                                                  + MACRO_PADDING.format(0)
                                                  )
        self.adc_raw_plot_TabWidget.setMovable(True)  # 탭 드래그로 순서 변경 가능
        self.adc_raw_graph_VBoxLayout.addWidget(self.adc_raw_plot_TabWidget)
        
        self.adc_fft_graph_GroupBox = QGroupBox("ADC FFT Plot")             # 1. 대상 위젯 생성
        self.adc_fft_graph_GroupBox.setStyleSheet(""
                                                  + MACRO_PADDING.format(10)
                                                  )
        self.right_VBoxLayout.addWidget(self.adc_fft_graph_GroupBox, stretch=2)           # 1-1. 상위 레이아웃에 위젯 적용

        self.adc_fft_graph_VBoxLayout = QVBoxLayout()                     # 2. 세로 방향 레이아웃 생성
        self.adc_fft_graph_GroupBox.setLayout(self.adc_fft_graph_VBoxLayout)            # 3. 레이아웃을 대상 위젯에 적용
        

        self.adc_fft_plot_TabWidget = QTabWidget()
        self.adc_fft_plot_TabWidget.setStyleSheet(""
                                                  + MACRO_BORDER_STYLE.format('none')
                                                  + MACRO_PADDING.format(0)
                                                  )
        self.adc_fft_plot_TabWidget.setMovable(True)  # 탭 드래그로 순서 변경 가능
        self.adc_fft_graph_VBoxLayout.addWidget(self.adc_fft_plot_TabWidget)
    
        for plot_opt in enum_graph_plot_range_opt:
            self.create_adc_plot_tab(self.A_graph_plot_value[enum_graph_plot_num.ADC_RAW][plot_opt])
            self.create_fft_plot_tab(self.A_graph_plot_value[enum_graph_plot_num.ADC_FFT][plot_opt])

        # --- 로그 패널 (그래프 + 로그) ---
        self.log_Widget = QWidget()                    # 1. 대상 위젯 생성
        self.log_Widget.setStyleSheet(""
                                        + MACRO_BORDER_RADIUS.format(6)
                                        + MACRO_PADDING.format(2)
                                        + MACRO_BACKGROUND_COLOR.format(cfg.BACKGROUND_COLOR)
                                        + MACRO_BORDER_SIZE.format(2)
                                        + MACRO_BORDER_STYLE.format('solid')
                                        + MACRO_BORDER_COLOR.format(cfg.LINE_COLOR)
                                        + MACRO_TEXT_COLOR.format(cfg.TEXT_COLOR)
                                        )

        self.main_HBoxLayout.addWidget(self.log_Widget, stretch=1)    # 1-1. 상위 레이아웃에 위젯 적용
        self.log_VBoxLayout = QVBoxLayout()           # 2. 세로 방향 레이아웃 생성
        self.log_Widget.setLayout(self.log_VBoxLayout)   # 3. 레이아웃을 대상 위젯에 적용


        self.log_GroupBox = QGroupBox("Log")
        self.log_VBoxLayout.addWidget(self.log_GroupBox)           # 1-1. 상위 레이아웃에 위젯 적용
        self.log_VBoxLayout = QVBoxLayout()
        self.log_GroupBox.setLayout(self.log_VBoxLayout)
        
        self.log_TextEdit = QTextEdit()
        self.log_TextEdit.setReadOnly(True)
        self.log_VBoxLayout.addWidget(self.log_TextEdit)

        self.adc_fft_graph_VBoxLayout.addWidget(self.adc_fft_plot_TabWidget, stretch=1)  # 3. 로그
        
        # FFT 관련 변수 초기화
        # self.f_sampling_rate = 100.0  # 100Hz (ADC_SPEED_MS = 10ms)

        # self.uart_thread = None
        # self.command_sender = upcs.CommandSender(None)  # 명령 송신 객체

############################################################################################################
    def event_connection_status_changed(self, b_is_connected):
        """워커의 연결 상태 변경 시 UI 업데이트"""
        self.port_connect_PushButton.setEnabled(True)
        if b_is_connected:
            self.port_connect_PushButton.setText("Disconnect")
            self.tp_setting_PushButton.setEnabled(True)
            # PC -> Chip 명령 송신
            if self.uart_thread and self.uart_thread.serial_port:
                self.command_sender.set_serial(self.uart_thread.serial_port)
        else:
            self.port_connect_PushButton.setText("Connect")
            self.tp_setting_PushButton.setEnabled(True)
            self.command_sender.set_serial(None)

            if self.uart_thread:
                self.uart_thread.deleteLater()
                self.uart_thread = None
############################################################################################################

    def insert_ports_to_ComboBox(self):
        """사용 가능한 시리얼 포트 목록 채우기"""
        self.port_sel_ComboBox.clear()
        A_ports:list = list_ports.comports()
        for port in A_ports:
            self.port_sel_ComboBox.addItem(f"{port.device}: {port.description}", port.device)
        if not A_ports:
            self.port_sel_ComboBox.addItem(NO_PORT_FOUND)

    def event_refresh_ports(self):
        """COM Port 재검색 (버튼 클릭 시 호출)"""
        self.insert_ports_to_ComboBox()
        port_count = self.port_sel_ComboBox.count()
        if port_count > 0 and (NO_PORT_FOUND not in self.port_sel_ComboBox.itemText(0)):
            self.log_TextEdit.append(f"🔍 COM Port 재검색 완료: {port_count}개 포트 발견")
        else:
            self.log_TextEdit.append("🔍 COM Port 재검색 완료: 포트를 찾을 수 없습니다")

    def insert_baudrates_to_ComboBox(self):
        """Baud Rate 목록 채우기"""
        self.baudrate_sel_ComboBox.clear()
        for rate in upcfg.BaudRate:
            self.baudrate_sel_ComboBox.addItem(str(rate.value), rate.value)
        self.baudrate_sel_ComboBox.setCurrentText(str(upcfg.BaudRate.BAUD_1152000.value))

    def event_port_connection(self):
        """연결/해제 토글"""

        if self.uart_thread and self.uart_thread.isRunning():
            # 연결 해제
            self.uart_thread.stop()
            self.port_connect_PushButton.setText("Connect")
            self.log_TextEdit.append("Disconnected.")
        else:
            # 연결
            port = self.port_sel_ComboBox.currentData()
            self.log_TextEdit.append(f"Connected port {port}")
            if not port or NO_PORT_FOUND in port:
                self.log_TextEdit.append("Error: 선택된 포트가 없습니다.")
                return
            baud = self.baudrate_sel_ComboBox.currentData()
            self.uart_thread = UartWorker(port, baud)
            self.uart_thread.event_new_data.connect(self.event_update_ui)
            self.uart_thread.event_connection_status.connect(self.event_connection_status_changed)
            self.uart_thread.start()
            self.port_connect_PushButton.setText("Connecting...")
            self.port_connect_PushButton.setEnabled(False) # Disable button while connecting

    def event_send_tp_command(self):
        """TP1 값을 ESP32에 전송"""
        i_get_tp1 = self.tp1_SpinBox.value()    
        if self.command_sender.send_set_tp1(i_get_tp1):
            self.log_TextEdit.append(f"[TX] TP1 설정 명령 전송: {i_get_tp1}")
        else:
            self.log_TextEdit.append("[TX] TP1 전송 실패 - 연결 상태를 확인하세요")
            QMessageBox.warning(self, "전송 실패", "TP1 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")

        i_get_tp1_rck = self.tp1_rck_SpinBox.value()
        if self.command_sender.send_set_tp1_recheck(i_get_tp1_rck):
            self.log_TextEdit.append(f"[TX] TP1_RECHECK 설정 명령 전송: {i_get_tp1}")
        else:
            self.log_TextEdit.append("[TX] TP1_RECHECK 전송 실패 - 연결 상태를 확인하세요")
            QMessageBox.warning(self, "전송 실패", "TP1_RECHECK 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")


        i_get_tp2 = self.tp2_SpinBox.value()    
        if self.command_sender.send_set_tp2(i_get_tp2):
            self.log_TextEdit.append(f"[TX] TP2 설정 명령 전송: {i_get_tp2}")
        else:
            self.log_TextEdit.append("[TX] TP2 전송 실패 - 연결 상태를 확인하세요")
            QMessageBox.warning(self, "전송 실패", "TP2 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")

    def graph_statistics(self, inter_buffer:list):
        """0이 아닌 값들에 대한 통계 계산"""
        i_buffer_len = len(inter_buffer)
        exclusion_zero_buffer = [x for x in inter_buffer if x != 0]
        if not exclusion_zero_buffer:
            return 0, 0, 0, 0
        
        i_exclusion_zero_buffer_len = len(exclusion_zero_buffer)
        i_min = min(exclusion_zero_buffer)
        i_max = max(exclusion_zero_buffer)
        i_avg = sum(exclusion_zero_buffer) / i_exclusion_zero_buffer_len
        i_mid = statistics.median(exclusion_zero_buffer)

        return i_buffer_len, i_exclusion_zero_buffer_len, i_min, i_max, i_avg, i_mid

    def log_TextEdit_print_sensor_data(self, input_sensor_parser_data:updm.SensorData):
        """센서 데이터를 로그 문자열로 변환"""
        s_data_name = upcfg.get_data_type_name(input_sensor_parser_data.i_data_type)
        
        s_chksum_pass_status = "✓" if input_sensor_parser_data.UartReceiveData_raw.b_chksum_pass else "✗"
        s_header_text = (f"{s_chksum_pass_status}\n"
                        f"UartReceiveData[{input_sensor_parser_data.UartReceiveData_raw.timestamp.strftime('%H:%M:%S.%f')[:-3]}],\n"
                        f"SensorData[{input_sensor_parser_data.timestamp.strftime('%H:%M:%S.%f')[:-3]}],\n"
                        f"Type: {s_data_name},\n"
                        f"bytes_data_length: {input_sensor_parser_data.UartReceiveData_raw.bytes_data_length},\n"
                        f"bytes_data: {input_sensor_parser_data.UartReceiveData_raw.bytes_data},\n"
                        f"bytes_checksum: 0x{input_sensor_parser_data.UartReceiveData_raw.bytes_checksum},\n"
                        f"Checksum: 0x{input_sensor_parser_data.UartReceiveData_raw.bytes_checksum},\n"
                        f"i_data_type: {input_sensor_parser_data.i_data_type},\n"
                        f"i_adc_raw: {input_sensor_parser_data.i_adc_raw},\n"
                        f"A_adc_buffer: {input_sensor_parser_data.A_adc_buffer},\n"
                        f"settings: {input_sensor_parser_data.settings},\n"
                        f")\n")

        A_s_log_lines = [s_header_text]

        # --- 버퍼 데이터 처리 ---
        A_target_buffer, s_target_name = None, None
        if input_sensor_parser_data.A_adc_buffer:
            A_target_buffer, s_target_name = input_sensor_parser_data.A_adc_buffer, "ADC Buffer"

        if A_target_buffer is not None and s_target_name is not None:
            i_buffer_len, i_exclusion_zero_buffer_len, i_min, i_max, i_avg, i_mid = self.graph_statistics(A_target_buffer)
            s_stats_text = (
                f"총 Len: {i_buffer_len}개\n"
                f"실제 값 Len: {i_exclusion_zero_buffer_len}개)\n"
                f"실제 값 Min: {i_min}\n"
                f"실제 값 Max: {i_max}\n"
                f"실제 값 Avg: {i_avg:.1f}\n"
                f"실제 값 Mid: {i_mid}"
            )
            A_s_log_lines.append(s_stats_text)

        # --- 설정값 처리 ---
        elif input_sensor_parser_data.settings:
            SettingsData_handle = input_sensor_parser_data.settings
            s_occupancy_status = "🟢 재실 O" if SettingsData_handle.b_occu_status else "⚪ 재실 X"
            A_s_log_lines.append(f"Settings : {s_occupancy_status}")
            A_s_log_lines.append(f" - TP1 : {SettingsData_handle.i_tp1}")
            A_s_log_lines.append(f" - TP1 Recheck : {SettingsData_handle.i_tp1_recheck}")
            A_s_log_lines.append(f" - TP2 : {SettingsData_handle.i_tp2}")
            A_s_log_lines.append(f" - LED : Max={SettingsData_handle.i_led_max_per}%, Min={SettingsData_handle.i_led_min_per}%, Dim={SettingsData_handle.i_led_dim_per}%")
            A_s_log_lines.append(f" - LED Step : {SettingsData_handle.i_led_work_ms} ms, Work : {SettingsData_handle.i_led_step_ms} ms, Delay : {SettingsData_handle.i_led_delay_ms} ms")
            A_s_log_lines.append(f" - Occupancy Timeout : {SettingsData_handle.i_occu_chk_timeout_us} us")
            A_s_log_lines.append(f" - Sleep Time : {SettingsData_handle.i_sleep_time_us} us")
            A_s_log_lines.append(f" - Occupancy : {SettingsData_handle.b_occu_status}")
            A_s_log_lines.append(f" - PIR Output : {SettingsData_handle.b_pir_status}")

        return "\n".join(A_s_log_lines) # 리스트의 각 항목을 \n(줄바꿈)으로 이어 붙여 하나의 문자열로 만듭니다.

    def create_line(self, target_PlotWidget, s_inter_name, i_value, s_label, s_color_code):
        # TP1 임계값 가로선 추가 (빨간색)
        tp_InfiniteLine = pyqtgraph.InfiniteLine(
            pos=i_value, 
            angle=0,                                    # 선의 기울기(도 단위). 0은 수평(가로), 90은 수직(세로). 양수 값은 반시계 방향으로 회전합니다. 예: angle=0(가로), angle=45(대각선 위로 기울어진 선).
            pen=pyqtgraph.mkPen(
                color=s_color_code                       # 선 색 (문자열 'r', 색 이름, 16진 문자열 '#ff0000', (R,G,B) 또는 (R,G,B,A) 튜플, 또는 QtGui.QColor 가능).
                , width=2                               # 선 굵기(픽셀)
                , style=pyqtgraph.QtCore.Qt.PenStyle.DashLine     # 선 스타일(점선/실선 등). SolidLine (실선), DashLine (대시선), DotLine (점선), DashDotLine, DashDotDotLine, NoPen (그리지 않음)
                ),
            label=s_label,              # 이 그래프에서 어디에 보이는지:
            labelOpts={
                'position': 0.95                        # 0.0 ~ 1.0, 선을 따라 텍스트가 놓일 상대 위치 (예: 0.95). 0.95는 그래프의 하
                , 'color': s_color_code                  # 텍스트 색 (문자열/튜플/Qt color). 예: 'r' 또는 (255,0,0).
                , 'fill': (200, 200, 200, 100)          # 텍스트 배경 채우기 색 — RGBA 튜플 (R,G,B,A) 또는 QColor. A는 투명도(0~255). 예: (200,200,200,100).
                                                        # anchor: (옵션) 텍스트 정렬/앵커를 튜플로 지정할 수 있음(사용법은 약간 복잡).
                                                        # rotateAxis / angle: (환경/버전마다 이름이 다를 수 있음) 텍스트를 선과 함께 회전시킬 수 있는 옵션(선과 평행하게 표시).
                                                        # movable: (일부 버전에서) 라벨을 마우스로 이동 가능하게 할 수 있음.
                                                        # 구체적 사용 가능한 키와 동작은 설치된 pyqtgraph 버전 문서를 참조하세요.
                }
        )
        tp_InfiniteLine.role = s_inter_name
        target_PlotWidget.addItem(tp_InfiniteLine, ignoreBounds=True)

    def create_label(self, target_PlotWidget, s_inter_name, i_x_anchor, i_y_anchor, s_color_code):
        label_TextItem = pyqtgraph.TextItem(
            text='TEMP_LABEL_TEXT',
            color=s_color_code,
            anchor=(i_x_anchor, i_y_anchor),  # 우측 상단 기준
        )
        label_TextItem.setFont(pyqtgraph.QtGui.QFont('Consolas', 9))
        label_TextItem.role = s_inter_name
        target_PlotWidget.addItem(label_TextItem, ignoreBounds=True) # pyqtgraph가 auto-range 계산 시 이 TextItem의 위치를 무시

        return label_TextItem

    def create_scatter(self, target_PlotWidget, s_inter_name, s_color_code):
        point_ScatterPlotItem = pyqtgraph.ScatterPlotItem(
            pen=None,
            brush=pyqtgraph.mkBrush(s_color_code),
            size=7,
            symbol='o'
        )
        point_ScatterPlotItem.role = s_inter_name
        target_PlotWidget.addItem(point_ScatterPlotItem, ignoreBounds=True)

        return point_ScatterPlotItem

    def create_adc_plot_tab(self, graph_plot_value:list):

        target_PlotWidget = pyqtgraph.PlotWidget()
        # 마우스 드래그(팬) 및 휠 줌 비활성화
        target_PlotWidget.setMouseEnabled(x=False, y=False)
        target_PlotWidget.setMenuEnabled(False)
    
        target_PlotWidget.setTitle(f"{graph_plot_value[enum_graph_plot_index.STR_PLOT_NAME]}")
        target_PlotWidget.setLabel(f"{graph_plot_value[enum_graph_plot_index.STR_GRAPH_X_LABEL_POS]}", f"{graph_plot_value[enum_graph_plot_index.STR_GRAPH_X_LABEL]}", **{'font-size': '14pt'})
        if graph_plot_value[enum_graph_plot_index.INT_GRAPH_X_RANGE]:
            target_PlotWidget.setXRange(0, graph_plot_value[enum_graph_plot_index.INT_GRAPH_X_RANGE], padding=0)
        target_PlotWidget.setLabel(graph_plot_value[enum_graph_plot_index.STR_GRAPH_Y_LABEL_POS], graph_plot_value[enum_graph_plot_index.STR_GRAPH_Y_LABEL], **{'font-size': '14pt'})
        if graph_plot_value[enum_graph_plot_index.INT_GRAPH_Y_RANGE]:
            target_PlotWidget.setYRange(0, graph_plot_value[enum_graph_plot_index.INT_GRAPH_Y_RANGE], padding=0)
        target_PlotWidget.getPlotItem().getViewBox().setLimits(yMin=0) # 하한 0 고정

        target_PlotWidget.addLegend(offset=(10,10))            # 범례 추가(옵션: offset)
        target_PlotWidget.plot(
            pen=pyqtgraph.mkPen(
                color=graph_plot_value[enum_graph_plot_index.STR_LINE_COLOR]                       # 선 색 (문자열 'r', 색 이름, 16진 문자열 '#ff0000', (R,G,B) 또는 (R,G,B,A) 튜플, 또는 QtGui.QColor 가능).
                , width=1                               # 선 굵기(픽셀)
                , style=pyqtgraph.QtCore.Qt.PenStyle.DashLine     # 선 스타일(점선/실선 등). SolidLine (실선), DashLine (대시선), DotLine (점선), DashDotLine, DashDotDotLine, NoPen (그리지 않음)
                )
            , fillLevel=0
            , fillBrush=(0, 255, 255, 80)
            , name=graph_plot_value[enum_graph_plot_index.STR_LEGEND_TEXT]
        )
        
        self.create_line(target_PlotWidget, cfg.TP1_LINE_NAME, self.i_tp1, f'TP1={self.i_tp1}', cfg.TP1_COLOR)
        self.create_line(target_PlotWidget, cfg.TP1_RCK_LINE_NAME, self.i_tp1_rck, f'TP1_RCK={self.i_tp1_rck}', cfg.TP1_RCK_COLOR)
        self.create_scatter(target_PlotWidget, cfg.TP1_POINT_NAME, cfg.TP1_POINT_COLOR)
        self.create_scatter(target_PlotWidget, cfg.TP1_RCK_POINT_NAME, cfg.TP1_RCK_POINT_COLOR)
        self.create_label(target_PlotWidget, cfg.LABEL_NAME, cfg.LABEL_ANCHOR_X, cfg.LABEL_ANCHOR_Y, cfg.LABEL_COLOR)

        self.adc_raw_plot_TabWidget.addTab(target_PlotWidget, graph_plot_value[enum_graph_plot_index.STR_PLOT_NAME])

    def create_fft_plot_tab(self, graph_plot_value:list):

        target_PlotWidget = pyqtgraph.PlotWidget()
        # 마우스 드래그(팬) 및 휠 줌 비활성화
        target_PlotWidget.setMouseEnabled(x=False, y=False)
        target_PlotWidget.setMenuEnabled(False)
    
        target_PlotWidget.setTitle(f"{graph_plot_value[enum_graph_plot_index.STR_PLOT_NAME]}")
        target_PlotWidget.setLabel(f"{graph_plot_value[enum_graph_plot_index.STR_GRAPH_X_LABEL_POS]}", f"{graph_plot_value[enum_graph_plot_index.STR_GRAPH_X_LABEL]}", **{'font-size': '14pt'})
        if graph_plot_value[enum_graph_plot_index.INT_GRAPH_X_RANGE]:
            target_PlotWidget.setXRange(0, graph_plot_value[enum_graph_plot_index.INT_GRAPH_X_RANGE], padding=0)
        target_PlotWidget.setLabel(f"{graph_plot_value[enum_graph_plot_index.STR_GRAPH_Y_LABEL_POS]}", graph_plot_value[enum_graph_plot_index.STR_GRAPH_Y_LABEL], **{'font-size': '14pt'})
        if graph_plot_value[enum_graph_plot_index.INT_GRAPH_Y_RANGE]:
            target_PlotWidget.setYRange(0, graph_plot_value[enum_graph_plot_index.INT_GRAPH_Y_RANGE], padding=0)
        target_PlotWidget.getPlotItem().getViewBox().setLimits(yMin=0) # 하한 0 고정

        target_PlotWidget.addLegend(offset=(10,10))            # 범례 추가(옵션: offset)
        target_PlotWidget.plot(
            pen=pyqtgraph.mkPen(
                color=graph_plot_value[enum_graph_plot_index.STR_LINE_COLOR]                       # 선 색 (문자열 'r', 색 이름, 16진 문자열 '#ff0000', (R,G,B) 또는 (R,G,B,A) 튜플, 또는 QtGui.QColor 가능).
                , width=1                               # 선 굵기(픽셀)
                , style=pyqtgraph.QtCore.Qt.PenStyle.DashLine     # 선 스타일(점선/실선 등). SolidLine (실선), DashLine (대시선), DotLine (점선), DashDotLine, DashDotDotLine, NoPen (그리지 않음)
                )
            , fillLevel=0
            , fillBrush=(0, 255, 255, 80)
            , name=graph_plot_value[enum_graph_plot_index.STR_LEGEND_TEXT]
        )

        # 피크 주파수 표시용 텍스트 아이템
        peak_TextItem = pyqtgraph.TextItem(anchor=(0, 1), color='y')
        target_PlotWidget.addItem(peak_TextItem)

        # tp1_recheck_lines[graph_tab_name] = self.tp1_rck_InfiniteLine
        self.adc_fft_plot_TabWidget.addTab(target_PlotWidget, graph_plot_value[enum_graph_plot_index.STR_PLOT_NAME])

        # # 피크 라벨 저장용 딕셔너리
        # if not hasattr(self, 'fft_peak_labels'):
        #     self.fft_peak_labels = {}
        # self.fft_peak_labels[graph_tab_name] = peak_label






        

    # def _compute_fft(self, adc_buffer, apply_window=True):
    #     """ADC 버퍼에 FFT 적용
        
    #     Args:
    #         adc_buffer: ADC 샘플 배열 (예: 300개의 uint16)
    #         apply_window: 윈도우 함수 적용 여부
            
    #     Returns:
    #         frequencies: 주파수 배열 (Hz)
    #         magnitudes: 진폭 배열 (정규화됨)
    #     """
    #     n = len(adc_buffer)
        
    #     # 1. DC 오프셋 제거
    #     signal = np.array(adc_buffer, dtype=np.float64)
    #     signal = signal - np.mean(signal)
        
    #     # 2. 윈도우 함수 적용 (스펙트럼 누설 방지)
    #     if apply_window:
    #         window = np.hanning(n)
    #         signal = signal * window
        
    #     # 3. FFT 연산 (실수 신호용 rfft)
    #     fft_result = np.fft.rfft(signal)
        
    #     # 4. 진폭 계산 및 정규화
    #     magnitudes = np.abs(fft_result) * 2 / n
    #     magnitudes[0] /= 2  # DC 성분 보정
        
    #     # 5. 주파수 축 생성
    #     frequencies = np.fft.rfftfreq(n, d=1.0/self.f_sampling_rate)
        
    #     return frequencies, magnitudes

    # def _update_fft_plot(self, adc_buffer):
    #     """FFT 그래프 업데이트
        
    #     Args:
    #         adc_buffer: ADC 샘플 배열
    #     """
    #     if len(adc_buffer) < 10:
    #         return
        
    #     # DC 오프셋 (Mean 값) 계산
    #     dc_mean = np.mean(adc_buffer)
        
    #     # FFT 계산
    #     frequencies, magnitudes = self._compute_fft(adc_buffer)
        
    #     # 전체 스펙트럼 그래프 업데이트
    #     if "ADC_FFT" in self.plots:
    #         self.plots["ADC_FFT"].setData(frequencies, magnitudes)
            
    #         # 피크 주파수 찾기 (DC 제외)
    #         if len(magnitudes) > 1:
    #             # DC(0Hz) 제외한 영역에서 피크 찾기
    #             peak_idx = np.argmax(magnitudes[1:]) + 1
    #             peak_freq = frequencies[peak_idx]
    #             peak_mag = magnitudes[peak_idx]
                
    #             # 피크 라벨 업데이트 (Mean 값 포함)
    #             if "ADC_FFT" in self.fft_peak_labels:
    #                 label = self.fft_peak_labels["ADC_FFT"]
    #                 label.setText(f"DC Mean: {dc_mean:.1f}\nPeak: {peak_freq:.2f} Hz\n진폭(Mag): {peak_mag:.1f}")
    #                 label.setPos(frequencies[-1] * 0.6, 50)  # Y축 150 고정, 중간 위치
        
    #     # 확대 스펙트럼 그래프 업데이트 (0~15Hz)
    #     if "ADC_FFT (Zoom)" in self.plots:
    #         self.plots["ADC_FFT (Zoom)"].setData(frequencies, magnitudes)
            
    #         # 0~15Hz 범위에서 피크 찾기
    #         zoom_mask = frequencies <= 15
    #         if np.any(zoom_mask) and len(magnitudes[zoom_mask]) > 1:
    #             zoom_freqs = frequencies[zoom_mask]
    #             zoom_mags = magnitudes[zoom_mask]
                
    #             # DC 제외
    #             peak_idx = np.argmax(zoom_mags[1:]) + 1
    #             peak_freq = zoom_freqs[peak_idx]
    #             peak_mag = zoom_mags[peak_idx]
                
    #             if "ADC_FFT (Zoom)" in self.fft_peak_labels:
    #                 label = self.fft_peak_labels["ADC_FFT (Zoom)"]
    #                 label.setText(f"DC Mean: {dc_mean:.1f}\nPeak: {peak_freq:.2f} Hz\n진폭(Mag): {peak_mag:.1f}")
    #                 label.setPos(10, 50)  # Y축 150 고정, 중간 위치


    # [
    #     "TEMP_PLOT_NAME - 0.0"
    #     , 0, "POS", 'LABEL'
    #     , 0, "POS", 'LABEL'
    #     , "#000000", "TEMP_LEGEND"
    # ]
    # class enum_graph_plot_index(enum.IntEnum):
    # STR_PLOT_NAME           = 0
    # INT_GRAPH_X_RANGE       = STR_PLOT_NAME + 1
    # STR_GRAPH_X_LABEL_POS   = INT_GRAPH_X_RANGE + 1
    # STR_GRAPH_X_LABEL       = STR_GRAPH_X_LABEL_POS + 1
    # INT_GRAPH_Y_RANGE       = STR_GRAPH_X_LABEL + 1
    # STR_GRAPH_Y_LABEL_POS   = INT_GRAPH_Y_RANGE + 1
    # STR_GRAPH_Y_LABEL       = STR_GRAPH_Y_LABEL_POS + 1
    # STR_LINE_COLOR          = STR_GRAPH_Y_LABEL + 1
    # STR_LEGEND_TEXT         = STR_LINE_COLOR + 1
    # self._get_or_create_plot("ADC_BUFFER (Adaptive)", show_tp1_line=True).setData(input_sensor_parser_data.A_adc_buffer)
    # def _get_or_create_plot(self, name, fixed_range=None, show_tp1_line=False):
    #     """데이터 타입 이름으로 플롯을 반환. 미리 생성된 탭을 사용."""
    #     if name in self.plots:
    #         return self.plots[name]
    #     else:
    #         # 미리 생성되지 않은 탭은 동적으로 생성 (fallback)
    #         # 이름에 따라 적절한 탭 타입 결정
    #         if ("HW_HPF" in name or "HW_BPF" in name) and "_2" in name:
    #             tab_type = "hw_filter_2"
    #         elif "HW_HPF" in name or "HW_BPF" in name:
    #             tab_type = "hw_filter"
    #         elif "ADC_HPF" in name or "ADC_BPF" in name:
    #             tab_type = "sw_filter"
    #         else:
    #             tab_type = "adc_raw"
    #         self._create_plot_tab(name, fixed_range, show_tp1_line, tab_type)
    #         return self.plots[name]

    def get_TabWidget(self, input_plot_name:str) -> Optional[QWidget]:
        # 나중에 tabData로 찾기
        for i_index in range(self.adc_raw_plot_TabWidget.count()):
            if self.adc_raw_plot_TabWidget.tabText(i_index) == input_plot_name:
                return self.adc_raw_plot_TabWidget.widget(i_index)
            
        for i_index in range(self.adc_fft_plot_TabWidget.count()):
            if self.adc_fft_plot_TabWidget.tabText(i_index) == input_plot_name:
                return self.adc_fft_plot_TabWidget.widget(i_index)

        return None

    def update_threshold_lines(self, inter_Widget:QWidget):

        target_line = None
        PlotItem = inter_Widget.getPlotItem()
        items = getattr(PlotItem, 'items', None)  # 일부 버전은 속성, 일부는 다른 구조일 수 있음
        for item in items:
            if isinstance(item, pyqtgraph.InfiniteLine) and getattr(item, 'role', None) == cfg.TP1_LINE_NAME:
                target_line = item
        target_line.setValue(self.i_tp1)
        target_line.label.setText(f'TP1={self.i_tp1}')

        items = getattr(PlotItem, 'items', None)  # 일부 버전은 속성, 일부는 다른 구조일 수 있음
        for item in items:
            if isinstance(item, pyqtgraph.InfiniteLine) and getattr(item, 'role', None) == cfg.TP1_RCK_LINE_NAME:
                target_line = item
        target_line.setValue(self.i_tp1_rck)
        target_line.label.setText(f'TP1={self.i_tp1_rck}')

    def update_status(self, inter_Widget:QWidget, A_inter_data:updm.SensorData):
        """그래프 우측 상단에 통계 정보(최소, 최대, 중앙값, 평균) 표시
        
        Args:
            plot_name: 플롯 이름
            data: 데이터 배열
            y_max: 고정 Y축 최대값 (옵션)
            positive_only: True면 양수 값만 필터링해서 통계 계산
        """
        target_label = None
        PlotItem = inter_Widget.getPlotItem()
        items = getattr(PlotItem, 'items', None)  # 일부 버전은 속성, 일부는 다른 구조일 수 있음

        # 검색 시
        for item in items:
            if isinstance(item, pyqtgraph.TextItem) and getattr(item, 'role', None) == cfg.LABEL_NAME:
                target_label = item
        
        i_buffer_len, i_exclusion_zero_buffer_len, i_min, i_max, i_avg, i_mid = self.graph_statistics(A_inter_data)
        return_value = self.update_exceed_points(inter_Widget, A_inter_data)  # TP1 초과점 표시

        s_stats_text = (
            f"총 Len : {i_buffer_len}개\n"
            f"실제 값 Len : {i_exclusion_zero_buffer_len}개)\n"
            f"실제 값 Min : {i_min}\n"
            f"실제 값 Max : {i_max}\n"
            f"실제 값 Avg : {i_avg:.1f}\n"
            f"실제 값 Mid : {i_mid}\n"
            f"TP1: {return_value[0]}\n"
            f"TP1_RCK: {return_value[1]}\n"
        )

        target_label.setText(s_stats_text)

        ViewBox = PlotItem.getViewBox()
        x_max = ViewBox.viewRange()[0][1]
        y_max = ViewBox.viewRange()[1][1]

        target_label.setPos(x_max, y_max)

    def update_exceed_points(self, inter_Widget:QWidget, A_inter_data:updm.SensorData) -> list:
        """TP1 초과 지점을 빨간색 점, TP1_RECHECK 초과 지점을 주황색 점으로 표시"""

        A_i_tp1_over_x = []  # 빨간 점 (TP1 ~ TP1_RECHECK)
        A_i_tp1_over_y = []
        A_i_tp1_rck_over_x = []  # 주황 점 (TP1_RECHECK 초과)
        A_i_tp1_rck_over_y = []  # BUG FIX: x로 오타나 있었음
        
        for i_count, value in enumerate(A_inter_data):
            if self.i_tp1_rck > 0 and value > self.i_tp1_rck:
                # TP1_RECHECK 초과 → 주황 점
                A_i_tp1_rck_over_x.append(i_count)
                A_i_tp1_rck_over_y.append(value)  # BUG FIX: x에 value를 넣고 있었음
            elif self.i_tp1 > 0 and value > self.i_tp1:
                # TP1 초과 but TP1_RECHECK 이하 → 빨간 점
                A_i_tp1_over_x.append(i_count)
                A_i_tp1_over_y.append(value)
            
        target_scatter = None
        PlotItem = inter_Widget.getPlotItem()
        items = getattr(PlotItem, 'items', None)  # 일부 버전은 속성, 일부는 다른 구조일 수 있음

        for item in items:
            if isinstance(item, pyqtgraph.ScatterPlotItem) and getattr(item, 'role', None) == cfg.TP1_POINT_NAME:
                target_scatter = item
        # ScatterPlot 업데이트
        target_scatter.setData(A_i_tp1_over_x, A_i_tp1_over_y)
        # 초과 개수 라벨 업데이트 (우측 상단 위치)
        tp1_over_count = len(A_i_tp1_over_x)

        for item in items:
            if isinstance(item, pyqtgraph.ScatterPlotItem) and getattr(item, 'role', None) == cfg.TP1_RCK_POINT_NAME:
                target_scatter = item

        target_scatter.setData(A_i_tp1_rck_over_x, A_i_tp1_rck_over_y)
        tp1_rck_over_count = len(A_i_tp1_rck_over_x)

        return tp1_over_count, tp1_rck_over_count



    

    # def send_get_settings_command(self):
    #     """ESP32에 현재 설정값을 요청"""
    #     if self.command_sender.send_get_settings():
    #         self.log_TextEdit.append("[TX] 설정값 요청 명령 전송")
    #     else:
    #         self.log_TextEdit.append("[TX] 설정값 요청 실패 - 연결 상태를 확인하세요")

    # def send_save_nvs_command(self):
    #     """현재 설정을 NVS(비휘발성 메모리)에 저장"""
    #     if self.command_sender.send_save_nvs():
    #         self.log_TextEdit.append("[TX] 💾 NVS 저장 명령 전송")
    #         QMessageBox.information(self, "NVS 저장", "설정값이 NVS에 저장되었습니다.")
    #     else:
    #         self.log_TextEdit.append("[TX] NVS 저장 실패 - 연결 상태를 확인하세요")
    #         QMessageBox.warning(self, "전송 실패", "NVS 저장 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")

    # def send_reset_command(self):
    #     """ESP32 소프트 리셋"""
    #     # 확인 대화상자
    #     reply = QMessageBox.question(
    #         self, 
    #         "ESP32 리셋", 
    #         "ESP32를 리셋하시겠습니까?\n연결이 끊어집니다.",
    #         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    #         QMessageBox.StandardButton.No
    #     )
        
    #     if reply == QMessageBox.StandardButton.Yes:
    #         if self.command_sender.send_reset():
    #             self.log_TextEdit.append("[TX] 🔄 ESP32 리셋 명령 전송 (1초 후 리셋됨)")
    #         else:
    #             self.log_TextEdit.append("[TX] 리셋 실패 - 연결 상태를 확인하세요")

    # def apply_plot_range(self):
    #     """선택한 플롯의 Y축 범위를 적용"""
    #     plot_name = self.plot_select_combo.currentText()
    #     y_min = self.y_min_spinbox.value()
    #     y_max = self.y_max_spinbox.value()
        
    #     if plot_name in self.plot_widgets:
    #         plot_widget = self.plot_widgets[plot_name]
    #         plot_widget.setYRange(y_min, y_max, MACRO_PADDING=0)
    #         self.log_TextEdit.append(f"📊 {plot_name} Y축 범위 설정: {y_min} ~ {y_max}")
    #     else:
    #         self.log_TextEdit.append(f"⚠️ 플롯 '{plot_name}'을 찾을 수 없습니다.")
    
    # def reset_plot_range(self):
    #     """선택한 플롯의 Y축 범위를 자동으로 리셋"""
    #     plot_name = self.plot_select_combo.currentText()
        
    #     if plot_name in self.plot_widgets:
    #         plot_widget = self.plot_widgets[plot_name]
    #         plot_widget.enableAutoRange(axis='y')
    #         self.log_TextEdit.append(f"🔄 {plot_name} Y축 자동 범위 활성화")
    #     else:
    #         self.log_TextEdit.append(f"⚠️ 플롯 '{plot_name}'을 찾을 수 없습니다.")

    # def closeEvent(self, event):
    #     """윈도우 종료 이벤트"""
    #     if self.uart_thread and self.uart_thread.isRunning():
    #         self.uart_thread.stop()
    #     event.accept()


    @PyQt6.QtCore.pyqtSlot(object)
    def event_update_ui(self, input_sensor_parser_data:updm.SensorData):
        """UI 업데이트: 로그, 그래프, 설정 표시"""
        # 1. 로그 텍스트 업데이트 (최대 500줄 제한)
        log_str = self.log_TextEdit_print_sensor_data(input_sensor_parser_data)
        self.log_TextEdit.append(log_str)
        
        log_TextEdit_doc = self.log_TextEdit.document()
        if log_TextEdit_doc.blockCount() > cfg.MAX_LOG_LINES:
            cursor = self.log_TextEdit.textCursor() # 내부 편집 커서(QTextCursor) 객체
            cursor.movePosition(cursor.MoveOperation.Start) # 커서를 문서의 맨 앞으로 이동
            # 아래로 N번 이동하면서(세 번째 인자가 N) 이동 중인 범위를 선택(두번째 인자 KeepAnchor가 선택 상태 유지).
            # 여기서 N = blockCount() - MAX_LOG_LINES (총 블록(줄) 수에서 허용 최대줄을 뺀 값) — 즉, 초과한 만큼의 첫 N줄을 선택함.
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, log_TextEdit_doc.blockCount() - cfg.MAX_LOG_LINES)
            # 택된 텍스트(즉 문서 맨 앞부터 초과분까지)를 삭제
            cursor.removeSelectedText()
        
        self.log_TextEdit.verticalScrollBar().setValue(self.log_TextEdit.verticalScrollBar().maximum())
        if input_sensor_parser_data.A_adc_buffer:
            get_Widget = self.get_TabWidget(ADC_RAW_FULL_SCALE_NAME)

            ### update_status 처럼 함수로 만들기 ############################################
            if not get_Widget:
                print(f"debugger_start.py | MainWindow | event_update_ui | get_Widget = {get_Widget} [ADC_RAW_FULL_SCALE_NAME]")
            else:
                Items = get_Widget.getPlotItem()
                lines = Items.listDataItems()
                if lines:
                    lines[0].setData(input_sensor_parser_data.A_adc_buffer)
                else:
                    get_Widget.plot(input_sensor_parser_data.A_adc_buffer)
            ### update_status 처럼 함수로 만들기 ############################################
            self.update_status(get_Widget, input_sensor_parser_data.A_adc_buffer)
            get_Widget = self.get_TabWidget(ADC_RAW_ZOOM_SCALE_NAME)

            ### update_status 처럼 함수로 만들기 ############################################
            if not get_Widget:
                print(f"debugger_start.py | MainWindow | event_update_ui | get_Widget = {get_Widget} [ADC_RAW_ZOOM_SCALE_NAME]")
            else:
                Items = get_Widget.getPlotItem()
                lines = Items.listDataItems()
                if lines:
                    lines[0].setData(input_sensor_parser_data.A_adc_buffer)
                else:
                    get_Widget.plot(input_sensor_parser_data.A_adc_buffer)
            ### update_status 처럼 함수로 만들기 ############################################
            self.update_status(get_Widget, input_sensor_parser_data.A_adc_buffer)
            
            # ★ FFT 분석 및 그래프 업데이트
            # self._update_fft_plot(input_sensor_parser_data.A_adc_buffer)

        # 3. 설정값 업데이트
        if input_sensor_parser_data.settings:
            SettingsData_handle = input_sensor_parser_data.settings
            self.adc_tp1_setting(SettingsData_handle.i_tp1)
            self.adc_tp1_rck_setting(SettingsData_handle.i_tp1_recheck)

            get_Widget = self.get_TabWidget(ADC_RAW_FULL_SCALE_NAME)
            self.update_threshold_lines(get_Widget)
            get_Widget = self.get_TabWidget(ADC_RAW_ZOOM_SCALE_NAME)
            self.update_threshold_lines(get_Widget)

            if SettingsData_handle.b_occu_status:
                self.occupancy_Label.setText("🟢 재실 중")
            else:
                self.occupancy_Label.setText("⚪ 재실 중이 아님")
            
            # PIR 출력 상태 라벨 업데이트
            if SettingsData_handle.b_pir_status:
                self.pir_output_Label.setText("📡 PIR 출력: ON")
            else:
                self.pir_output_Label.setText("📡 PIR 출력: OFF")
            
            settings_str = (
                f"TP1: {SettingsData_handle.i_tp1}\n"
                f"TP1 Recheck: {SettingsData_handle.i_tp1_recheck}\n"
                f"TP2: {SettingsData_handle.i_tp2}\n"
                f"LED Max: {SettingsData_handle.i_led_max_per}%\n"
                f"LED Min: {SettingsData_handle.i_led_min_per}%\n"
                f"LED dimming: {SettingsData_handle.i_led_dim_per}%\n"
                f"LED Work: {SettingsData_handle.i_led_work_ms} ms\n"
                f"LED Step: {SettingsData_handle.i_led_step_ms} ms\n"
                f"LED Delay: {SettingsData_handle.i_led_delay_ms} ms\n"
                f"Occupancy Timeout: {SettingsData_handle.i_occu_chk_timeout_us} us\n"
                f"Sleep Time: {SettingsData_handle.i_sleep_time_us} us"
            )
            self.connect_status_Label.setText(settings_str)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())