"""
iSENSOR UART Debugger - GUI 버전

PyQt6와 pyqtgraph를 사용한 UART 데이터 시각화 도구
"""
import sys

import serial
from serial.tools import (list_ports)

import PyQt6.QtCore
# from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QGridLayout, QLabel, QTextEdit, QGroupBox, QTabWidget,
    QSpinBox, QAbstractSpinBox, QMessageBox,
    QSizePolicy
)


import pyqtgraph
# from pyqtgraph import (PlotWidget, mkPen, InfiniteLine, QtCore, pyqtgraph.TextItem)

import enum
# from enum import Enum, auto, IntEnum, Flag
# class TabType(str, Enum):
#     ADC_RAW = "adc_raw"
#     ADC_FFT = "adc_fft"
#     SW_FILTER = "sw_filter"
# class Mode(Enum):
#     OFF = auto()
#     ON = auto()
# class BaudRate(IntEnum):
#     B115200 = 115200
#     B230400 = 230400
# class Perm(Flag):
#     READ = auto()
#     WRITE = auto()
#     EXEC = auto()
# p = Perm.READ | Perm.WRITE
# if Perm.WRITE in p:
#     ...

import config                               as cfg
import uart_protocol.uart_protocol_config   as upcfg
import uart_protocol.uart_receive_parser    as upurp
import uart_protocol.data_parser            as updp
import uart_protocol.command_sender         as upcs

# from upcfg import (BaudRate)
# from upcs import CommandSender



# 맑은 고딕 : 'Malgun Gothic'
# Segoe UI: Windows 시스템 UI 폰트, 깔끔한 산세리프 → 데스크톱 앱 UI 권장
# Tahoma: 가독성 좋고 컴팩트한 산세리프 → 레이블/버튼에 적합
# Arial: 보편적 영문 산세리프 → 다국어(영문) 호환성 우수
# Verdana: 화면 가독성 최적화(넓은 문자) → 소형 글자에 강함
# Roboto: 구글/안드로이드 기본, 현대적 느낌 → 모바일/웹 스타일
# Noto Sans KR: 구글의 다국어 한글 지원 폰트 → 일관된 크로스플랫폼 표시
# Nanum Gothic / Nanum Myeongjo: 한국에서 자주 쓰이는 산세리프/명조
# Pretendard: 최근 인기 있는 깔끔한 한글 웹폰트 → 깔끔한 UI에 적합
# Gulim / Dotum / Batang: 오래된 Windows 기본 한글 글꼴(레거시 호환용)
MACRO_FONT_NAME = "font-family: {};"
MACRO_FONT_BOLD = "font-weight: bold;"
MACRO_FONT_SIZE = "font-size: {}pt;"

# Reusable CSS snippets for widgets
BUTTON_HOVER_BG = "QPushButton:hover { background-color: %s; }"
# print(BUTTON_HOVER_BG %'#3366ff')
# print(
#     """
#     QPushButton:hover {
#     background-color: #3366ff;
#     }
#     """
#     )
MACRO_BORDER_RADIUS = "border-radius: {}px;"
MACRO_PADDING = "padding: {}px;"
MACRO_BACKGROUND_COLOR = "background-color: {};"
MACRO_BORDER_STYLE = "border-style: {};"
MACRO_BORDER_SIZE = "border: {}px;"
MACRO_BORDER_COLOR = "border-color: {};"
MACRO_TEXT_COLOR = "color: {};"
# Fixed
# 의미: 크기가 sizeHint()에 정확히 고정됩니다(늘어나거나 줄어들지 않음).
# 사용처: 고정 아이콘, 고정 너비 버튼/라벨, 분할선 등.

# Minimum
# 의미: 가능한 한 작게(최소 크기) 유지하려 하고, 필요하면 늘어날 수 있음.
# 사용처: 최소 공간만 차지하되 여유 공간이 생기면 확장해도 되는 작은 컨트롤.

# Maximum
# 의미: 가능한 한 크게 늘어나려 하지만(여유 있으면), 줄이는 쪽으로는 제약이 있음(작아지길 원하지 않음).
# 사용처: 특수한 경우(보통 잘 쓰이지 않음).

# Preferred
# 의미: sizeHint()를 우선으로 삼고, 레이아웃 상황에 따라 늘어나거나 줄어들 수 있음.
# 사용처: 일반적인 위젯(레이블, 입력상자 등).

# MinimumExpanding
# 의미: Minimum 성격(최소 유지를 선호) + 여유 공간이 있으면 적극적으로 확장함.
# 사용처: 왼쪽 컨트롤은 최소, 오른쪽 뷰는 확장하는 레이아웃에서 가운데/오른쪽 확장 위젯.

# Expanding
# 의미: 가능한 한 여유 공간을 먼저 차지하려는 성향이 강함(확장 우선).
# 사용처: 플롯, 텍스트 에디터, 로그 창 같은 중심 컨텐츠.

# Ignored
# 의미: sizeHint()를 무시하고 레이아웃이 임의로 크기를 정함.
# 사용처: 커스텀 렌더링 캔버스 등 크기 제어를 전적으로 레이아웃에 맡길 때.

# 각 데이터 타입별 플롯을 저장할 딕셔너리
# self.plots = {}
# self.plot_widgets = {}  # pyqtgraph.PlotWidget 저장용
# self.threshold_lines = {}  # TP1 임계값 가로선 저장용
# self.tp1_recheck_lines = {}  # TP1 Recheck 임계값 가로선 저장용
# self.exceed_plots = {}  # TP1 초과 지점 표시용 ScatterPlot
# self.exceed_labels = {}  # TP1 초과 개수 표시용 pyqtgraph.TextItem
# self.stats_labels = {}  # 통계 정보 표시용 pyqtgraph.TextItem
# self.tp1_value = 0  # TP1 값 저장
# self.tp1_rck_value = 0  # TP1 Recheck 값 저장

NO_PORT_FOUND = "No ports found"

# class enum_graph_plot_num(enum.IntEnum):
#     ADC_RAW = 0
#     ADC_FFT = ADC_RAW + 1
# class enum_graph_plot_range_opt(enum.IntEnum):
#     ALL = 0
#     ADAPTIVE = ALL + 1
# class enum_graph_plot_index(enum.IntEnum):
#     STR_PLOT_NAME = 0
#     INT_GRAPH_X_RANGE = STR_PLOT_NAME + 1
#     STR_GRAPH_X_LABEL_POS = INT_GRAPH_X_RANGE + 1
#     STR_GRAPH_X_LABEL = STR_GRAPH_X_LABEL_POS + 1
#     INT_GRAPH_Y_RANGE = STR_GRAPH_X_LABEL + 1
#     STR_GRAPH_Y_LABEL_POS = INT_GRAPH_Y_RANGE + 1
#     STR_GRAPH_Y_LABEL = STR_GRAPH_Y_LABEL_POS + 1
#     STR_LINE_COLOR = STR_GRAPH_Y_LABEL + 1
#     STR_LEGEND_TEXT = STR_LINE_COLOR + 1
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

    new_data            = PyQt6.QtCore.pyqtSignal(object)       # 파싱된 SensorData 객체
    log_message         = PyQt6.QtCore.pyqtSignal(str)          # 로그 메시지 (텍스트)
    event_connection_status   = PyQt6.QtCore.pyqtSignal(bool)         # 연결 상태 (True: 성공, False: 실패)   # emit 이벤트 함수


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
                    # print(f"debugger_start.py | [UART RX] {len(byte_data)} bytes received") # debugger_start.py | [UART RX] 32 bytes received
                    # print(f"debugger_start.py | byte_data : {byte_data}")                   # debugger_start.py | byte_data : b'\xaaU\xcc\t-\x00\x0f\xa0\x0f\xa0\x00\x00\x00\x00\x00\x00\x00\x14d\x00\x14\x00\x00\x00\x05\x00\x00\x01\xf4\x00\x00\x01'
                    
                    for byte in byte_data:
                        # print(f"debugger_start.py | byte : {byte}")                         # debugger_start.py | byte : 170
                        complete_receive_data = self.UartReceiveParser_handle.feed_byte(byte)
                        # print(f"debugger_start.py | complete_receive_data : {complete_receive_data}")     # debugger_start.py | frame : None

                        if complete_receive_data:
                            # ★ 디버그: 프레임 파싱 완료 (비활성화)
                            # print(f"[UART RX] Frame parsed! Type: {frame.data_type}, Payload: {frame.data_length} bytes")

                            sensor_data = self.DataParser_handle.data_parser(complete_receive_data)

                            # if sensor_data:
                            #     # ★ 디버그: 센서 데이터 파싱 완료 (비활성화)
                            #     # print(f"[UART RX] SensorData ready! Data type: {sensor_data.data_type}")
                            #     self.new_data.emit(sensor_data)
                            # else:
                            #     print(f"[UART RX] ⚠ PayloadParser returned None for type {complete_receive_data.data_type}")

                            # bytes_stx:bytes           # AA 55 CC (3 bytes)
                            # bytes_data_type:bytes     # 0~9 (UartDataType)
                            # bytes_data_length:bytes   # 데이터 길이 (Little Endian)
                            # bytes_data:bytes          # 실제 데이터
                            # bytes_checksum:bytes      # Sum 체크섬 (Little Endian)
                            # bytes_etx:bytes           # DD 55 AA (3 bytes)

                            if sensor_data == None:
                                # ★ 디버그: 센서 데이터 파싱 완료 (비활성화)
                                # print(f"[UART RX] SensorData ready! Data type: {sensor_data.data_type}")
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


        # plots = {}
        plot_widgets = {}  # pyqtgraph.PlotWidget 저장용
        # threshold_lines = {}  # TP1 임계값 가로선 저장용
        # tp1_recheck_lines = {}  # TP1 Recheck 임계값 가로선 저장용
        # exceed_plots = {}  # TP1 초과 지점 표시용 ScatterPlot
        # exceed_labels = {}  # TP1 초과 개수 표시용 pyqtgraph.TextItem
        # stats_labels = {}  # 통계 정보 표시용 pyqtgraph.TextItem
        # tp1_value = 0  # TP1 값 저장
        # tp1_rck_value = 0  # TP1 Recheck 값 저장
        
        # 나중에 tabData로 찾기
        # for i in range(self.adc_raw_plot_TabWidget.count()):
        #     if self.adc_raw_plot_TabWidget.tabText(i) == graph_tab_name:
        #     if self.adc_raw_plot_TabWidget.tabData(i) == graph_tab_name:
        #         pw = self.adc_raw_plot_TabWidget.widget(i)
        #         break
# target_PlotWidget.setObjectName("plot_"+graph_tab_name)
# pw = self.adc_raw_plot_TabWidget.findChild(pyqtgraph.PlotWidget, "plot_"+graph_tab_name)

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

    # def adc_bit_refrash(self):
    #     self.A_graph_plot_value[enum_graph_plot_num.ADC_RAW][enum_graph_plot_range_opt.ALL][enum_graph_plot_index.INT_GRAPH_Y_RANGE] = (1 << self.i_adc_bit) - 1
    # def adc_bit_setting(self, input_i_adc_bit):
    #     self.i_adc_bit = input_i_adc_bit
    #     self.adc_bit_refrash()



    """메인 윈도우"""
    def __init__(self):
        super().__init__()

        self.value_init()

        #TODO : str -> config로 옮기기
        self.graph_title_setting("ADC Full Scale", enum_graph_plot_num.ADC_RAW, enum_graph_plot_range_opt.ALL)
        self.graph_title_setting("ADC Zoom Scale", enum_graph_plot_num.ADC_RAW, enum_graph_plot_range_opt.ADAPTIVE)
        self.graph_x_range_setting(self.i_adc_window_size, enum_graph_plot_num.ADC_RAW)
        self.graph_x_label_pos_setting("bottom", enum_graph_plot_num.ADC_RAW)
        self.graph_x_label_setting("시간(10ms)", enum_graph_plot_num.ADC_RAW)
        self.graph_y_range_setting(self.adc_bit_2_range(12), enum_graph_plot_num.ADC_RAW, enum_graph_plot_range_opt.ALL)
        self.graph_y_label_pos_setting("left", enum_graph_plot_num.ADC_RAW)
        self.graph_y_label_setting("ADC", enum_graph_plot_num.ADC_RAW)
        self.graph_line_color_setting(cfg.ADC_RAW_LINE_COLOR, enum_graph_plot_num.ADC_RAW)
        self.graph_legend_setting('ADC', enum_graph_plot_num.ADC_RAW)

        self.graph_title_setting("ADC FFT Full Scale", enum_graph_plot_num.ADC_FFT, enum_graph_plot_range_opt.ALL)
        self.graph_title_setting("ADC FFT Zoom Scale", enum_graph_plot_num.ADC_FFT, enum_graph_plot_range_opt.ADAPTIVE)
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
        # 5px = 테두리 두께(픽셀).
        # solid = 테두리 스타일 — 실선(draw a solid line). (dashed, dotted, none 등 가능)
        # #3366ff = 테두리 색상(HEX).

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
        self.port_search_PushButton.clicked.connect(self.refresh_ports)
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
        self.port_connect_PushButton.clicked.connect(self.port_connection) # 버튼 기능 구현
        # addWidget(..., row, col, rowSpan, colSpan)의
        # 2 = 배치할 행(row) 인덱스 (0부터 시작)
        # 0 = 배치할 열(column) 인덱스 (0부터 시작)
        # 1 = 몇 행(rowSpan)을 차지할지 (여기선 1행)
        # 2 = 몇 열(columnSpan)을 차지할지 (여기선 2열)
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
        # self.nvs_setting_read_PushButton.clicked.connect(self.port_connection) # 버튼 기능 구현
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
        # self.nvs_setting_read_PushButton.clicked.connect(self.port_connection) # 버튼 기능 구현
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
        # self.tp1_SpinBox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
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
                                                  
        self.tp_setting_PushButton.clicked.connect(self.port_connection) # 버튼 기능 구현
        # addWidget(..., row, col, rowSpan, colSpan)의
        # 2 = 배치할 행(row) 인덱스 (0부터 시작)
        # 0 = 배치할 열(column) 인덱스 (0부터 시작)
        # 1 = 몇 행(rowSpan)을 차지할지 (여기선 1행)
        # 2 = 몇 열(columnSpan)을 차지할지 (여기선 2열)
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
        # self.right_VBoxLayout.addWidget(self.adc_raw_graph_GroupBox)           # 1-1. 상위 레이아웃에 위젯 적용
        self.right_VBoxLayout.addWidget(self.adc_raw_graph_GroupBox, stretch=2)           # 1-1. 상위 레이아웃에 위젯 적용

        self.adc_raw_graph_VBoxLayout = QVBoxLayout()                     # 2. 세로 방향 레이아웃 생성
        self.adc_raw_graph_GroupBox.setLayout(self.adc_raw_graph_VBoxLayout)            # 3. 레이아웃을 대상 위젯에 적용

        self.adc_raw_plot_TabWidget = QTabWidget()
        self.adc_raw_plot_TabWidget.setStyleSheet(""
                                                  + MACRO_BORDER_STYLE.format('none')
                                                  + MACRO_PADDING.format(0)
                                                  )
        self.adc_raw_plot_TabWidget.setMovable(True)  # 탭 드래그로 순서 변경 가능
        # self.adc_raw_graph_VBoxLayout.addWidget(self.adc_raw_plot_TabWidget, stretch=2)
        self.adc_raw_graph_VBoxLayout.addWidget(self.adc_raw_plot_TabWidget)
        
        self.adc_fft_graph_GroupBox = QGroupBox("ADC FFT Plot")             # 1. 대상 위젯 생성
        self.adc_fft_graph_GroupBox.setStyleSheet(""
                                                  + MACRO_PADDING.format(10)
                                                  )
        # self.right_VBoxLayout.addWidget(self.adc_fft_graph_GroupBox)           # 1-1. 상위 레이아웃에 위젯 적용
        self.right_VBoxLayout.addWidget(self.adc_fft_graph_GroupBox, stretch=2)           # 1-1. 상위 레이아웃에 위젯 적용

        self.adc_fft_graph_VBoxLayout = QVBoxLayout()                     # 2. 세로 방향 레이아웃 생성
        self.adc_fft_graph_GroupBox.setLayout(self.adc_fft_graph_VBoxLayout)            # 3. 레이아웃을 대상 위젯에 적용
        

        self.adc_fft_plot_TabWidget = QTabWidget()
        self.adc_fft_plot_TabWidget.setStyleSheet(""
                                                  + MACRO_BORDER_STYLE.format('none')
                                                  + MACRO_PADDING.format(0)
                                                  )
        self.adc_fft_plot_TabWidget.setMovable(True)  # 탭 드래그로 순서 변경 가능
        # self.adc_fft_graph_VBoxLayout.addWidget(self.adc_fft_plot_TabWidget, stretch=2)
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
    # @pyqtSlot(bool)
    def on_connection_status_changed(self, b_is_connected):
        """워커의 연결 상태 변경 시 UI 업데이트"""
        self.port_connect_PushButton.setEnabled(True)
        if b_is_connected:
            self.port_connect_PushButton.setText("Disconnect")
            # 모든 컨트롤 버튼 활성화
            # self.tp1_send_button.setEnabled(True)
            # self.tp2_send_button.setEnabled(True)
            # self.tp1_recheck_send_button.setEnabled(True)
            # self.get_settings_button.setEnabled(True)
            # self.save_nvs_button.setEnabled(True)
            # self.reset_button.setEnabled(True)

            self.tp_setting_PushButton.setEnabled(True)
            # CommandSender에 시리얼 포트 설정

            # self.serial_port:serial.Serial = serial.Serial(
            #     port        = self.i_port_num,
            #     baudrate    = self.i_baud_rate,
            #     bytesize    = serial.EIGHTBITS,
            #     parity      = serial.PARITY_NONE,
            #     stopbits    = serial.STOPBITS_ONE,
            #     timeout     = 1.0
            # )

            # PC -> Chip 명령 송신
            if self.uart_thread and self.uart_thread.serial_port:
                self.command_sender.set_serial(self.uart_thread.serial_port)
        else:
            self.port_connect_PushButton.setText("Connect")
            # 모든 컨트롤 버튼 비활성화
            # self.tp1_send_button.setEnabled(False)
            # self.tp2_send_button.setEnabled(False)
            # self.tp1_recheck_send_button.setEnabled(False)
            # self.get_settings_button.setEnabled(False)
            # self.save_nvs_button.setEnabled(False)
            # self.reset_button.setEnabled(False)
            self.tp_setting_PushButton.setEnabled(True)

            self.command_sender.set_serial(None)

            # Clean up the thread object
            if self.uart_thread:
                self.uart_thread.deleteLater()
                self.uart_thread = None
############################################################################################################

    def insert_ports_to_ComboBox(self):
        """사용 가능한 시리얼 포트 목록 채우기"""
        self.port_sel_ComboBox.clear()
        A_ports:list = list_ports.comports()
        for port in A_ports:
            # self.port_sel_ComboBox.addItem(f"{port.description}")
            self.port_sel_ComboBox.addItem(f"{port.device}: {port.description}", port.device)
        if not A_ports:
            self.port_sel_ComboBox.addItem(NO_PORT_FOUND)

    def refresh_ports(self):
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

    def port_connection(self):
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
            # self.uart_thread.new_data.connect(self.update_ui)
            # self.uart_thread.log_message.connect(self.log_TextEdit.append)

            # emit 연결
            self.uart_thread.event_connection_status.connect(self.on_connection_status_changed)

            self.uart_thread.start()
            
            self.port_connect_PushButton.setText("Connecting...")
            self.port_connect_PushButton.setEnabled(False) # Disable button while connecting

    # @pyqtSlot(object)
    # def update_ui(self, data: SensorData):
    #     """UI 업데이트: 로그, 그래프, 설정 표시"""
    #     # 1. 로그 텍스트 업데이트 (최대 500줄 제한)
    #     log_str = self._format_sensor_data_for_log(data)
    #     self.log_TextEdit.append(log_str)
        
    #     # 로그 줄 수 제한 (메모리 누수 방지)
    #     MAX_LOG_LINES = 500
    #     doc = self.log_TextEdit.document()
    #     if doc.blockCount() > MAX_LOG_LINES:
    #         cursor = self.log_TextEdit.textCursor()
    #         cursor.movePosition(cursor.MoveOperation.Start)
    #         cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, doc.blockCount() - MAX_LOG_LINES)
    #         cursor.removeSelectedText()
        
    #     self.log_TextEdit.verticalScrollBar().setValue(self.log_TextEdit.verticalScrollBar().maximum())

    #     # 2. 그래프 업데이트
    #     if data.adc_buffer:
    #         self._get_or_create_plot("ADC_BUFFER (Adaptive)", show_tp1_line=True).setData(data.adc_buffer)
    #         self._update_stats("ADC_BUFFER (Adaptive)", data.adc_buffer)
    #         self._update_exceed_points("ADC_BUFFER (Adaptive)", data.adc_buffer, y_max=4096)  # TP1 초과점 표시
    #         self._get_or_create_plot("ADC_BUFFER", fixed_range=(0, 4096), show_tp1_line=True).setData(data.adc_buffer)
    #         self._update_stats("ADC_BUFFER", data.adc_buffer, y_max=3900)
    #         self._update_exceed_points("ADC_BUFFER", data.adc_buffer, y_max=3900)  # TP1 초과점 표시
            
    #         # ★ FFT 분석 및 그래프 업데이트
    #         self._update_fft_plot(data.adc_buffer)
    #     # 델타 버퍼는 비활성화됨
    #     # elif data.adc_delta_buffer:
    #     #     self._get_or_create_plot("ADC_DELTA_BUFFER").setData(data.adc_delta_buffer)
    #     #     self._update_stats("ADC_DELTA_BUFFER", data.adc_delta_buffer)
    #     #     self._get_or_create_plot("ADC_DELTA_BUFFER (Fixed)", fixed_range=(0, 4096), show_tp1_line=True).setData(data.adc_delta_buffer)
    #     #     self._update_stats("ADC_DELTA_BUFFER (Fixed)", data.adc_delta_buffer, y_max=3900)
    #     #     self._update_exceed_points("ADC_DELTA_BUFFER (Fixed)", data.adc_delta_buffer, y_max=3900)
    #     # VOLTAGE_BUFFER 삭제됨
    #     elif data.adc_hpf_buffer:  # SW HPF 버퍼
    #         self._get_or_create_plot("ADC_HPF_BUFFER (Adaptive)").setData(data.adc_hpf_buffer)
    #         self._update_stats("ADC_HPF_BUFFER (Adaptive)", data.adc_hpf_buffer)
    #         self._get_or_create_plot("ADC_HPF_BUFFER", fixed_range=(0, 3500), show_tp1_line=True).setData(data.adc_hpf_buffer)
    #         self._update_stats("ADC_HPF_BUFFER", data.adc_hpf_buffer, y_max=3300, positive_only=True)
            
    #         # ★ TP1 초과 지점 빨간색으로 표시
    #         self._update_exceed_points("ADC_HPF_BUFFER", data.adc_hpf_buffer, y_max=3300)
            
    #         # ★ SW Filter Plot (4번째 그래프)에도 표시
    #         self._get_or_create_plot("SW_HPF_BUFFER (Zoom)").setData(data.adc_hpf_buffer)
    #         self._update_stats("SW_HPF_BUFFER (Zoom)", data.adc_hpf_buffer, y_max=300)
    #         self._update_exceed_points("SW_HPF_BUFFER (Zoom)", data.adc_hpf_buffer, y_max=300)
    #         self._get_or_create_plot("SW_HPF_BUFFER", fixed_range=(0, 4096), show_tp1_line=True).setData(data.adc_hpf_buffer)
    #         self._update_stats("SW_HPF_BUFFER", data.adc_hpf_buffer, y_max=3900)
    #         self._update_exceed_points("SW_HPF_BUFFER", data.adc_hpf_buffer, y_max=3900)
    #     # hpf_buffer (하위 호환성 - adc_hpf_buffer 별칭)
    #     elif data.hpf_buffer:
    #         self._get_or_create_plot("ADC_HPF_BUFFER (Adaptive)").setData(data.hpf_buffer)
    #         self._update_stats("ADC_HPF_BUFFER (Adaptive)", data.hpf_buffer)
    #         self._get_or_create_plot("ADC_HPF_BUFFER", fixed_range=(0, 3500), show_tp1_line=True).setData(data.hpf_buffer)
    #         self._update_stats("ADC_HPF_BUFFER", data.hpf_buffer, y_max=3300, positive_only=True)
    #         self._update_exceed_points("ADC_HPF_BUFFER", data.hpf_buffer, y_max=3300)
        
    #     # SW BPF 버퍼 (Band-Pass Filter 적용값)
    #     elif data.adc_bpf_buffer:
    #         self._get_or_create_plot("ADC_BPF_BUFFER (Adaptive)").setData(data.adc_bpf_buffer)
    #         self._update_stats("ADC_BPF_BUFFER (Adaptive)", data.adc_bpf_buffer)
    #         self._get_or_create_plot("ADC_BPF_BUFFER", fixed_range=(0, 3500), show_tp1_line=True).setData(data.adc_bpf_buffer)
    #         self._update_stats("ADC_BPF_BUFFER", data.adc_bpf_buffer, y_max=3300, positive_only=True)
    #         self._update_exceed_points("ADC_BPF_BUFFER", data.adc_bpf_buffer, y_max=3300)
            
    #         # ★ SW Filter Plot (4번째 그래프)에도 표시
    #         self._get_or_create_plot("SW_BPF_BUFFER (Zoom)").setData(data.adc_bpf_buffer)
    #         self._update_stats("SW_BPF_BUFFER (Zoom)", data.adc_bpf_buffer, y_max=300)
    #         self._update_exceed_points("SW_BPF_BUFFER (Zoom)", data.adc_bpf_buffer, y_max=300)
    #         self._get_or_create_plot("SW_BPF_BUFFER", fixed_range=(0, 4096), show_tp1_line=True).setData(data.adc_bpf_buffer)
    #         self._update_stats("SW_BPF_BUFFER", data.adc_bpf_buffer, y_max=3900)
    #         self._update_exceed_points("SW_BPF_BUFFER", data.adc_bpf_buffer, y_max=3900)
        
    #     # HW HPF 버퍼 (하드웨어 HPF 채널 RAW ADC)
    #     elif data.hw_hpf_buffer:
    #         # 3번째 그래프 (HW Filter)
    #         self._get_or_create_plot("HW_HPF_BUFFER (Zoom)").setData(data.hw_hpf_buffer)
    #         self._update_stats("HW_HPF_BUFFER (Zoom)", data.hw_hpf_buffer, y_max=300)
    #         self._update_exceed_points("HW_HPF_BUFFER (Zoom)", data.hw_hpf_buffer, y_max=300)
    #         self._get_or_create_plot("HW_HPF_BUFFER", fixed_range=(0, 4096), show_tp1_line=True).setData(data.hw_hpf_buffer)
    #         self._update_stats("HW_HPF_BUFFER", data.hw_hpf_buffer, y_max=3900)
    #         # ★ TP1 초과 지점 표시
    #         self._update_exceed_points("HW_HPF_BUFFER", data.hw_hpf_buffer, y_max=3900)
            
    #         # 4번째 그래프 (SW Filter) - HW HPF 데이터가 있으면 SW 플롯은 업데이트하지 않음 (SW 데이터가 별도로 전송됨)
        
    #     # HW BPF 버퍼 (하드웨어 BPF 채널 RAW ADC)
    #     elif data.hw_bpf_buffer:
    #         # 3번째 그래프 (HW Filter)
    #         self._get_or_create_plot("HW_BPF_BUFFER (Zoom)").setData(data.hw_bpf_buffer)
    #         self._update_stats("HW_BPF_BUFFER (Zoom)", data.hw_bpf_buffer, y_max=300)
    #         self._update_exceed_points("HW_BPF_BUFFER (Zoom)", data.hw_bpf_buffer, y_max=300)
    #         self._get_or_create_plot("HW_BPF_BUFFER", fixed_range=(0, 4096), show_tp1_line=True).setData(data.hw_bpf_buffer)
    #         self._update_stats("HW_BPF_BUFFER", data.hw_bpf_buffer, y_max=3900)
    #         # ★ TP1 초과 지점 표시
    #         self._update_exceed_points("HW_BPF_BUFFER", data.hw_bpf_buffer, y_max=3900)
            
    #         # 4번째 그래프 (SW Filter) - HW BPF 데이터가 있으면 SW 플롯은 업데이트하지 않음 (SW 데이터가 별도로 전송됨)
        
    #     # 델타 버퍼는 비활성화됨
    #     # elif data.voltage_delta_buffer:
    #     #     self._get_or_create_plot("VOLTAGE_DELTA_BUFFER").setData(data.voltage_delta_buffer)
    #     #     self._update_stats("VOLTAGE_DELTA_BUFFER", data.voltage_delta_buffer)
    #     # elif data.hpf_delta_buffer:
    #     #     self._get_or_create_plot("HPF_DELTA_BUFFER").setData(data.hpf_delta_buffer)
    #     #     self._update_stats("HPF_DELTA_BUFFER", data.hpf_delta_buffer)
    #     #     self._get_or_create_plot("HPF_DELTA_BUFFER (Fixed)", fixed_range=(-50, 2500), show_tp1_line=True).setData(data.hpf_delta_buffer)
    #     #     self._update_stats("HPF_DELTA_BUFFER (Fixed)", data.hpf_delta_buffer, y_max=2300)
    #     #     self._update_exceed_points("HPF_DELTA_BUFFER (Fixed)", data.hpf_delta_buffer, y_max=2400)


    #     # 3. 설정값 업데이트
    #     if data.settings:
    #         s = data.settings
    #         self.tp1_value = s.tp1  # TP1 값 저장
    #         self.tp1_recheck_value = s.tp1_recheck  # TP1 Recheck 값 저장
            
    #         # TP1 가로선 업데이트
    #         self._update_threshold_lines()
            
    #         # 재실 상태 라벨 업데이트 (눈에 띄게!)
    #         if s.occupancy:
    #             self.occupancy_label.setText("🟢 재실 상태: 재실")
    #             self.occupancy_label.setStyleSheet("""
    #                 QLabel {
    #                     font-size: 14px;
    #                     font-weight: bold;
    #                     padding: 8px;
    #                     border-radius: 5px;
    #                     background-color: #1a4d1a;
    #                     color: #66ff66;
    #                 }
    #             """)
    #         else:
    #             self.occupancy_label.setText("⚪ 재실 상태: 없음")
    #             self.occupancy_label.setStyleSheet("""
    #                 QLabel {
    #                     font-size: 14px;
    #                     font-weight: bold;
    #                     padding: 8px;
    #                     border-radius: 5px;
    #                     background-color: #3a3a3a;
    #                     color: #888888;
    #                 }
    #             """)
            
    #         # PIR 출력 상태 라벨 업데이트
    #         if s.pir_output:
    #             self.pir_output_label.setText("📡 PIR 출력: ON")
    #             self.pir_output_label.setStyleSheet("""
    #                 QLabel {
    #                     font-size: 14px;
    #                     font-weight: bold;
    #                     padding: 8px;
    #                     border-radius: 5px;
    #                     background-color: #4d4d1a;
    #                     color: #ffff66;
    #                 }
    #             """)
    #         else:
    #             self.pir_output_label.setText("📡 PIR 출력: OFF")
    #             self.pir_output_label.setStyleSheet("""
    #                 QLabel {
    #                     font-size: 14px;
    #                     font-weight: bold;
    #                     MACRO_PADDING: 8px;
    #                     border-radius: 5px;
    #                     background-color: #3a3a3a;
    #                     color: #888888;
    #                 }
    #             """)
            
    #         settings_str = (
    #             f"TP1: {s.tp1}\n"
    #             f"TP1 Recheck: {s.tp1_recheck}\n"
    #             f"TP2: {s.tp2}\n"
    #             f"LED Max: {s.led_max_percentage}%\n"
    #             f"LED Min: {s.led_min_percentage}%\n"
    #             f"LED dimming: {s.led_dimming_percentage}%\n"
    #             f"LED Step: {s.led_dimming_step_time_ms} ms\n"
    #             f"LED Work: {s.led_dimming_work_time_ms} ms\n"
    #             f"LED Delay: {s.led_dimming_delay_time_ms} ms\n"
    #             f"Occupancy Timeout: {s.occupancy_timeout_us} us\n"
    #             f"Sleep Time: {s.sleep_time} us"
    #         )
    #         self.settings_label.setText(settings_str)

    # def _calculate_stats(self, data):
    #     """0이 아닌 값들에 대한 통계 계산"""
    #     valid_data = [x for x in data if x != 0]
    #     if not valid_data:
    #         return 0, 0, 0, 0
        
    #     count = len(valid_data)
    #     min_val = min(valid_data)
    #     max_val = max(valid_data)
    #     avg_val = sum(valid_data) / count
    #     return count, min_val, max_val, avg_val

    # def _format_array_pretty(self, data, items_per_line=10, indent=4):
    #     """배열 데이터를 보기 좋게 문자열로 변환"""
    #     lines = []
    #     for i in range(0, len(data), items_per_line):
    #         chunk = data[i:i + items_per_line]
    #         line = ", ".join(f"{x}" if isinstance(x, int) else f"{x:.2f}" for x in chunk)
    #         lines.append(f"{' ' * indent}[{i:03d}] {line}")
    #     return "\n".join(lines)

    # def _format_sensor_data_for_log(self, sensor_data: SensorData):
    #     """센서 데이터를 로그 문자열로 변환"""
    #     frame = sensor_data.raw_frame
    #     data_name = get_data_type_name(frame.data_type)
        
    #     status = "✓" if frame.is_valid else "✗"
    #     header = (f"{status} [{frame.timestamp.strftime('%H:%M:%S.%f')[:-3]}] "
    #               f"Type: {data_name:20s} "
    #               f"Length: {frame.data_length:4d} "
    #               f"Checksum: 0x{frame.checksum:04X}")

    #     log_lines = [header]

    #     # --- 버퍼 데이터 처리 ---
    #     buffer, name = None, None
    #     if sensor_data.adc_buffer:
    #         buffer, name = sensor_data.adc_buffer, "ADC"
    #     # voltage_buffer 로그 처리 삭제됨
    #     elif sensor_data.adc_hpf_buffer:
    #         buffer, name = sensor_data.adc_hpf_buffer, "SW HPF"
    #     elif sensor_data.hpf_buffer:  # 하위 호환성
    #         buffer, name = sensor_data.hpf_buffer, "SW HPF"
    #     elif sensor_data.adc_bpf_buffer:
    #         buffer, name = sensor_data.adc_bpf_buffer, "SW BPF"
    #     elif sensor_data.hw_hpf_buffer:
    #         buffer, name = sensor_data.hw_hpf_buffer, "HW HPF"
    #     elif sensor_data.hw_bpf_buffer:
    #         buffer, name = sensor_data.hw_bpf_buffer, "HW BPF"
    #     # 델타 버퍼는 비활성화됨
    #     # elif sensor_data.adc_delta_buffer:
    #     #     buffer, name = sensor_data.adc_delta_buffer, "ADC Delta"
    #     # elif sensor_data.voltage_delta_buffer:
    #     #     buffer, name = sensor_data.voltage_delta_buffer, "Voltage Delta"
    #     # elif sensor_data.hpf_delta_buffer:
    #     #     buffer, name = sensor_data.hpf_delta_buffer, "HPF Delta"

    #     if buffer is not None and name is not None:

    #         count, min_v, max_v, avg_v = self._calculate_stats(buffer)
    #         # 정수형 avg 값은 소수점 없이 표현
    #         avg_str = f"{int(avg_v)}" if isinstance(avg_v, float) and avg_v.is_integer() else f"{avg_v:.2f}"

    #         log_lines.append(f"  {name}: {len(buffer)} samples (Valid: {count}) "
    #                             f"(Min: {min_v}, Max: {max_v}, Avg: {avg_str})")
    #         # 배열 전체 출력 제거 (성능 개선)
    #         # log_lines.append(self._format_array_pretty(buffer))

    #     # --- 설정값 처리 ---
    #     elif sensor_data.settings:
    #         s = sensor_data.settings
    #         occupancy_status = "🟢 재실" if s.occupancy else "⚪ 없음"
    #         log_lines.append("  Settings:")
    #         log_lines.append(f"    - TP1: {s.tp1}")
    #         log_lines.append(f"    - TP1 Recheck: {s.tp1_recheck}")
    #         log_lines.append(f"    - TP2: {s.tp2}")
    #         log_lines.append(f"    - LED: Max={s.led_max_percentage}%, Min={s.led_min_percentage}%, Dim={s.led_dimming_percentage}%")
    #         log_lines.append(f"    - LED Step: {s.led_dimming_step_time_ms} ms, Work: {s.led_dimming_work_time_ms} ms, Delay: {s.led_dimming_delay_time_ms} ms")
    #         log_lines.append(f"    - Occupancy Timeout: {s.occupancy_timeout_us} us")
    #         log_lines.append(f"    - Sleep Time: {s.sleep_time} us")
    #         log_lines.append(f"    - Occupancy: {occupancy_status}")

    #     return "\n".join(log_lines)

    # def create_plot_tab(self, graph_tab_name, graph_fixed_range=None, opt_show_tp1=False, tab_type="adc_raw"):


    def create_line(self, target_PlotWidget, i_value, s_label, s_color_code):
        # TP1 임계값 가로선 추가 (빨간색)
        self.tp_InfiniteLine = pyqtgraph.InfiniteLine(
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
        target_PlotWidget.addItem(self.tp_InfiniteLine)
        # self.tp_InfiniteLine.label.setPos(self.tp_InfiniteLine.label.pos() + pyqtgraph.QtCore.QPointF(-100, 0))
        # self.tp_InfiniteLine.label.setPos(self.tp_InfiniteLine.label.pos() - pyqtgraph.QtCore.QPointF(-100, 0))

    # def create_adc_plot_tab(self, graph_tab_name=None, graph_range_x=None, graph_range_y=None):
    def create_adc_plot_tab(self, graph_plot_value):

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
        
        self.create_line(target_PlotWidget, self.i_tp1, f'TP1={self.i_tp1}', cfg.TP1_COLOR)
        self.create_line(target_PlotWidget, self.i_tp1_rck, f'TP1_RCK={self.i_tp1_rck}', cfg.TP1_RCK_COLOR)

        # tp1_recheck_lines[graph_tab_name] = self.tp1_rck_InfiniteLine
        self.adc_raw_plot_TabWidget.addTab(target_PlotWidget, graph_plot_value[enum_graph_plot_index.STR_PLOT_NAME])

    def create_fft_plot_tab(self, graph_plot_value):

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


    # def _update_threshold_lines(self):
    #     """모든 임계값 가로선의 위치 업데이트"""
    #     # TP1 빨간선 업데이트
    #     for name, line in self.threshold_lines.items():
    #         line.setValue(self.tp1_value)
    #         line.label.setText(f'TP1={self.tp1_value}')
        
    #     # TP1 Recheck 주황선 업데이트
    #     for name, line in self.tp1_recheck_lines.items():
    #         line.setValue(self.tp1_recheck_value)
    #         line.label.setText(f'TP1_RCK={self.tp1_recheck_value}')

    # def _update_stats(self, plot_name, data, y_max=None, positive_only=False):
    #     """그래프 우측 상단에 통계 정보(최소, 최대, 중앙값, 평균) 표시
        
    #     Args:
    #         plot_name: 플롯 이름
    #         data: 데이터 배열
    #         y_max: 고정 Y축 최대값 (옵션)
    #         positive_only: True면 양수 값만 필터링해서 통계 계산
    #     """
    #     import statistics
        
    #     if plot_name not in self.plot_widgets:
    #         return
        
    #     plot_widget = self.plot_widgets[plot_name]
        
    #     # 통계 라벨이 없으면 생성
    #     if plot_name not in self.stats_labels:
    #         label = pg.pyqtgraph.TextItem(
    #             text='',
    #             color=(200, 200, 200),  # 연한 회색
    #             anchor=(1, 0)  # 우측 상단 기준
    #         )
    #         label.setFont(pg.QtGui.QFont('Consolas', 9))
    #         plot_widget.addItem(label)
    #         self.stats_labels[plot_name] = label
        
    #     # 양수만 필터링 (옵션)
    #     if positive_only:
    #         filtered_data = [x for x in data if x > 0]
    #     else:
    #         filtered_data = data
        
    #     # 통계 계산
    #     if len(filtered_data) > 0:
    #         min_val = min(filtered_data)
    #         max_val = max(filtered_data)
    #         avg_val = sum(filtered_data) / len(filtered_data)
    #         median_val = statistics.median(filtered_data)
            
    #         # 포맷팅 (소수점 1자리)
    #         if positive_only:
    #             stats_text = (
    #                 f"(양수만 {len(filtered_data)}개)\n"
    #                 f"Min: {min_val:.1f}\n"
    #                 f"Max: {max_val:.1f}\n"
    #                 f"Med: {median_val:.1f}\n"
    #                 f"Avg: {avg_val:.1f}"
    #             )
    #         else:
    #             stats_text = (
    #                 f"Min: {min_val:.1f}\n"
    #                 f"Max: {max_val:.1f}\n"
    #                 f"Med: {median_val:.1f}\n"
    #                 f"Avg: {avg_val:.1f}"
    #             )
    #     else:
    #         stats_text = "No positive data" if positive_only else "No data"
        
    #     # 라벨 업데이트
    #     self.stats_labels[plot_name].setText(stats_text)
        
    #     # 위치 설정 (우측 상단)
    #     if y_max is None:
    #         # 자동 스케일 그래프의 경우 데이터 최대값 기준
    #         y_pos = max(data) if len(data) > 0 else 100
    #     else:
    #         y_pos = y_max - 100  # 고정 범위 그래프의 경우
        
    #     self.stats_labels[plot_name].setPos(len(data) - 2, y_pos)

    # def _update_exceed_points(self, plot_name, data, y_max=3900):
    #     """TP1 초과 지점을 빨간색 점, TP1_RECHECK 초과 지점을 주황색 점으로 표시"""
    #     if plot_name not in self.plot_widgets:
    #         return
        
    #     plot_widget = self.plot_widgets[plot_name]
        
    #     # TP1 초과용 ScatterPlot (빨간색)
    #     if plot_name not in self.exceed_plots:
    #         scatter = pg.ScatterPlotItem(
    #             pen=None,
    #             brush=pg.mkBrush('r'),  # 빨간색
    #             size=8,
    #             symbol='o'
    #         )
    #         plot_widget.addItem(scatter)
    #         self.exceed_plots[plot_name] = scatter
        
    #     # TP1_RECHECK 초과용 ScatterPlot (주황색)
    #     recheck_key = f"{plot_name}_recheck"
    #     if recheck_key not in self.exceed_plots:
    #         scatter_recheck = pg.ScatterPlotItem(
    #             pen=None,
    #             brush=pg.mkBrush(255, 165, 0),  # 주황색
    #             size=10,
    #             symbol='s'  # 사각형으로 구분
    #         )
    #         plot_widget.addItem(scatter_recheck)
    #         self.exceed_plots[recheck_key] = scatter_recheck
        
    #     # 초과 개수 표시용 pyqtgraph.TextItem 생성
    #     if plot_name not in self.exceed_labels:
    #         label = pg.pyqtgraph.TextItem(
    #             text='TP1 초과: 0 / TP1_RCK 초과: 0',
    #             color='r',
    #             anchor=(1, 0)  # 우측 상단 기준
    #         )
    #         label.setFont(pg.QtGui.QFont('Arial', 10, pg.QtGui.QFont.Weight.Bold))
    #         plot_widget.addItem(label)
    #         self.exceed_labels[plot_name] = label
        
    #     # 영역 구분 방식:
    #     # 🔴 빨간 점: TP1 < value <= TP1_RECHECK (중간 영역)
    #     # 🟠 주황 점: value > TP1_RECHECK (높은 영역)
        
    #     exceed_x = []  # 빨간 점 (TP1 ~ TP1_RECHECK)
    #     exceed_y = []
    #     exceed_recheck_x = []  # 주황 점 (TP1_RECHECK 초과)
    #     exceed_recheck_y = []
        
    #     for i, value in enumerate(data):
    #         if self.tp1_recheck_value > 0 and value > self.tp1_recheck_value:
    #             # TP1_RECHECK 초과 → 주황 점
    #             exceed_recheck_x.append(i)
    #             exceed_recheck_y.append(value)
    #         elif self.tp1_value > 0 and value > self.tp1_value:
    #             # TP1 초과 but TP1_RECHECK 이하 → 빨간 점
    #             exceed_x.append(i)
    #             exceed_y.append(value)
        
    #     # ScatterPlot 업데이트
    #     self.exceed_plots[plot_name].setData(exceed_x, exceed_y)
    #     self.exceed_plots[recheck_key].setData(exceed_recheck_x, exceed_recheck_y)
        
    #     # 초과 개수 라벨 업데이트 (우측 상단 위치)
    #     exceed_count = len(exceed_x)
    #     exceed_recheck_count = len(exceed_recheck_x)
    #     self.exceed_labels[plot_name].setText(f'TP1: {exceed_count} / TP1_RCK: {exceed_recheck_count}')
    #     # 우측 상단에 위치 (x=데이터길이-5, y=고정범위 상단)
    #     self.exceed_labels[plot_name].setPos(len(data) - 5, y_max)

    # def send_tp1_command(self):
    #     """TP1 값을 ESP32에 전송"""
    #     tp1_value = self.tp1_spinbox.value()
        
    #     if self.command_sender.send_set_tp1(tp1_value):
    #         self.log_TextEdit.append(f"[TX] TP1 설정 명령 전송: {tp1_value}")
    #         # 로컬 tp1_value 업데이트 및 그래프 임계선 업데이트
    #         self.tp1_value = tp1_value
    #         self._update_threshold_lines()
    #     else:
    #         self.log_TextEdit.append("[TX] TP1 전송 실패 - 연결 상태를 확인하세요")
    #         QMessageBox.warning(self, "전송 실패", "TP1 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")
    
    # def send_tp2_command(self):
    #     """TP2 값을 ESP32에 전송"""
    #     tp2_value = self.tp2_spinbox.value()
        
    #     if self.command_sender.send_set_tp2(tp2_value):
    #         self.log_TextEdit.append(f"[TX] TP2 설정 명령 전송: {tp2_value}")
    #     else:
    #         self.log_TextEdit.append("[TX] TP2 전송 실패 - 연결 상태를 확인하세요")
    #         QMessageBox.warning(self, "전송 실패", "TP2 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")
    
    # def send_tp1_recheck_command(self):
    #     """TP1_RECHECK 값을 ESP32에 전송"""
    #     tp1_recheck_value = self.tp1_recheck_spinbox.value()
        
    #     if self.command_sender.send_set_tp1_recheck(tp1_recheck_value):
    #         self.log_TextEdit.append(f"[TX] TP1_RECHECK 설정 명령 전송: {tp1_recheck_value}")
    #         # 로컬 tp1_recheck_value 업데이트 및 그래프 임계선 업데이트
    #         self.tp1_recheck_value = tp1_recheck_value
    #         self._update_threshold_lines()
    #     else:
    #         self.log_TextEdit.append("[TX] TP1_RECHECK 전송 실패 - 연결 상태를 확인하세요")
    #         QMessageBox.warning(self, "전송 실패", "TP1_RECHECK 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")
    
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())