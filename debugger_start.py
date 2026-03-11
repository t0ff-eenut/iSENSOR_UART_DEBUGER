"""
iSENSOR UART Debugger - GUI 버전

PyQt6와 pyqtgraph를 사용한 UART 데이터 시각화 도구
"""
import sys
from serial.tools import (list_ports)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QGridLayout, QLabel, QTextEdit, QGroupBox, QTabWidget,
    QSpinBox, QAbstractSpinBox, QMessageBox,
    QSizePolicy
)
from PyQt6.QtCore import Qt
# import pyqtgraph
from pyqtgraph import (PlotWidget, mkPen, InfiniteLine, QtCore, TextItem)

from uart_protocol.protocol_config import (BaudRate)



WINDOW_POSITION_X = 100
WINDOW_POSITION_Y = 100
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

LEFT_BOX_WIDTH = 400



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
SS_PT = "font-family: {};"
SS_BOLD = "font-weight: bold;"
SS_PT_SIZE = "font-size: {}pt;"

BORDER_RADIUS = "border-radius: {}px;"
PADDING = "padding: {}px;"

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
# self.plot_widgets = {}  # PlotWidget 저장용
# self.threshold_lines = {}  # TP1 임계값 가로선 저장용
# self.tp1_recheck_lines = {}  # TP1 Recheck 임계값 가로선 저장용
# self.exceed_plots = {}  # TP1 초과 지점 표시용 ScatterPlot
# self.exceed_labels = {}  # TP1 초과 개수 표시용 TextItem
# self.stats_labels = {}  # 통계 정보 표시용 TextItem
# self.tp1_value = 0  # TP1 값 저장
# self.tp1_rck_value = 0  # TP1 Recheck 값 저장
plots = {}
plot_widgets = {}  # PlotWidget 저장용
threshold_lines = {}  # TP1 임계값 가로선 저장용
tp1_recheck_lines = {}  # TP1 Recheck 임계값 가로선 저장용
exceed_plots = {}  # TP1 초과 지점 표시용 ScatterPlot
exceed_labels = {}  # TP1 초과 개수 표시용 TextItem
stats_labels = {}  # 통계 정보 표시용 TextItem
tp1_value = 0  # TP1 값 저장
tp1_rck_value = 0  # TP1 Recheck 값 저장


adc_raw_plot_TabWidget_configs = [
    # Tab Name, Range, OPT TP1 Show
    ("ADC RAW [All Range]", (0, 4096)),   # TP1 선 및 초과점 표시
    ("ADC RAW [Adaptive Range]", None),  # TP1 선 및 초과점 표시
]
adc_fft_plot_TabWidget_configs = [
    # Tab Name, Range, OPT TP1 Show
    ("ADC RAW [All Range]", (0, 4096)),   # TP1 선 및 초과점 표시
    ("ADC RAW [Adaptive Range]", None),  # TP1 선 및 초과점 표시
]

class MainWindow(QMainWindow):
    """메인 윈도우"""
    def __init__(self):
        super().__init__()
        # self.setWindowTitle("iSENSOR PIR UART Debugger")
        # self.setGeometry(100, 100, 1200, 800)
        self.setWindowTitle("iSENSOR PIR UART Debugger")
        self.setGeometry(WINDOW_POSITION_X, WINDOW_POSITION_Y, WINDOW_WIDTH, WINDOW_HEIGHT)

        # --- 메인 레이아웃 ---
        self.main_Widget = QWidget()                     # 1. 대상 위젯 생성
        self.setCentralWidget(self.main_Widget)
        self.main_HBoxLayout = QHBoxLayout()            # 2. 가로 방향 레이아웃 생성    (자식 위젯들을 좌→우로 배치)
        self.main_Widget.setLayout(self.main_HBoxLayout)     # 3. 레이아웃 적용
        
        # --- 좌측 패널 (제어 + 설정) ---
        self.left_Widget = QWidget()                     # 1. 대상 위젯 생성
        self.left_Widget.setFixedWidth(LEFT_BOX_WIDTH)              # * 위젯 가로 사이즈 설정
        # 5px = 테두리 두께(픽셀).
        # solid = 테두리 스타일 — 실선(draw a solid line). (dashed, dotted, none 등 가능)
        # #3366ff = 테두리 색상(HEX).
        self.left_Widget.setStyleSheet(""
            + "background-color: #77aaff;"
            + "border: 2px;"
            + "border-style: solid;"
            + "border-color: #3366ff;"
            # + "border-radius: 6px;"
            + BORDER_RADIUS.format(6)
            + PADDING.format(2)
            + "color: #bbeeff;"
            )
        self.main_HBoxLayout.addWidget(self.left_Widget)     # 1-1. 상위 레이아웃에 위젯 적용

# --- 좌측 패널 구성 ---
        self.left_VBoxLayout = QVBoxLayout()            # 2. 세로 방향 레이아웃 생성
        self.left_Widget.setLayout(self.left_VBoxLayout)     # 3. 레이아웃을 대상 위젯에 적용
# --- 제어창 표시 설정 ---
        self.left_control_Label = QLabel("제어창")             # 1. 대상 위젯 생성
        self.left_control_Label.setStyleSheet(""
            + SS_BOLD
            + SS_PT_SIZE.format(14)
            )  # * 위젯 폰트 설정
        self.left_control_Label.setFixedHeight(30)             # * 위젯 가로 사이즈 설정
        self.left_VBoxLayout.addWidget(self.left_control_Label)    # 1-1. 상위 레이아웃에 위젯 적용
# --- Connection 그룹 설정 ---
        self.connection_GroupBox = QGroupBox("Connection")             # 1. 대상 위젯 생성
        # self.connection_GroupBox.setStyleSheet(""
        #     + BORDER_RADIUS.format(6)
            
        #     )
        self.connection_GroupBox.setFlat(True)
        # self.connection_GroupBox.setStyleSheet("""
        # QGroupBox {
        # border: none;
        # background-color: transparent;
        # border-radius: 6px;
        # }
        # QGroupBox::title {
        # subcontrol-origin: margin;
        # left: 8px;
        # padding: 2px 6px;
        # }
        # """)
        self.connection_GridLayout = QGridLayout()                     # 2. Grid 레이아웃 생성 
        self.connection_GroupBox.setLayout(self.connection_GridLayout)            # 3. 레이아웃을 대상 위젯에 적용
        self.left_VBoxLayout.addWidget(self.connection_GroupBox)           # 1-1. 상위 레이아웃에 위젯 적용

        # --- 📶포트 설정 ---
        # --- 포트 라벨 설정 ---
        self.port_sel_Label = QLabel("📶포트: ")
        self.port_sel_Label.setStyleSheet(""
            + SS_BOLD
            # + BORDER_RADIUS.format(6)
            + "border-style: none;"
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
            + SS_BOLD
            )  # * 위젯 폰트 설정
        self.port_search_PushButton.setStyleSheet("""
            QPushButton:hover {
            background-color: #3366ff;
            }
            """)
        self.port_search_PushButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)  # 레이블은 텍스트 크기 위주, 늘어나지 않게
        self.port_search_PushButton.clicked.connect(self.refresh_ports)
        self.port_sel_HBoxLayout.addWidget(self.port_search_PushButton)         # 3. 위젯을 대상 레이아웃에 적용

        # --- ⚡보드레이트 설정 ---
        # --- 보드레이트 라벨 설정 ---
        self.baudrate_sel_Label = QLabel("⚡보드레이트: ")
        self.baudrate_sel_Label.setStyleSheet(""
            + SS_BOLD
            # + BORDER_RADIUS.format(6)
            + "border-style: none;"
            )
        self.baudrate_sel_Label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)    # 레이블은 텍스트 크기 위주, 늘어나지 않게
        self.connection_GridLayout.addWidget(self.baudrate_sel_Label, 1, 0)         # 3. 위젯을 대상 레이아웃에 적용
        # --- 보드레이트 목록 설정 ---
        self.baudrate_sel_ComboBox = QComboBox()                               # 1. 대상 위젯 생성
        self.connection_GridLayout.addWidget(self.baudrate_sel_ComboBox, 1, 1)         # 3. 위젯을 대상 레이아웃에 적용
        
        # --- 연결하기 버튼 설정 ---
        self.port_connect_PushButton = QPushButton("🔌연결하기")
        self.port_connect_PushButton.setStyleSheet(""
            + SS_BOLD
            )  # * 위젯 폰트 설정
        self.port_connect_PushButton.setStyleSheet("""
            QPushButton:hover {
            background-color: #3366ff;
            }
            """)
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
            + BORDER_RADIUS.format(6)
            )
        self.status_GridLayout = QGridLayout()                     # 2. Grid 레이아웃 생성
        self.status_GroupBox.setLayout(self.status_GridLayout)            # 3. 레이아웃을 대상 위젯에 적용
        self.left_VBoxLayout.addWidget(self.status_GroupBox)           # 1-1. 상위 레이아웃에 위젯 적용

        # --- 제어창 표시 설정 ---
        self.connect_status_Label = QLabel("Not connected")
        self.connect_status_Label.setStyleSheet(""
            + SS_BOLD
            + SS_PT_SIZE.format(14)
            + "border-style: none;"
            )
        self.connect_status_Label.setWordWrap(True)             # 자동 줄넘김
        self.status_GridLayout.addWidget(self.connect_status_Label)

        # --- 재실 여부 표시 설정 ---
        self.occupancy_Label = QLabel("⚪ 재실 상태: 대기 중")
        self.occupancy_Label.setStyleSheet(""
            + SS_BOLD
            + SS_PT_SIZE.format(14)
            )  # * 위젯 폰트 설정
        self.status_GridLayout.addWidget(self.occupancy_Label)

        # --- PIR 출력 표시 설정 ---
        self.pir_output_Label = QLabel("💤 PIR 출력: 대기 중")  # 👀
        self.pir_output_Label.setStyleSheet(""
            + SS_BOLD
            + SS_PT_SIZE.format(14)
            )  # * 위젯 폰트 설정
        self.status_GridLayout.addWidget(self.pir_output_Label)

############### NVS 설정 기능 구현하기 ###############################################################################
        # # --- 설정 값 불러오기 버튼 설정 ---
        # self.nvs_setting_read_PushButton = QPushButton("🔄 NVS 설정 값 불러오기")
        # self.nvs_setting_read_PushButton.setStyleSheet(""
        #     + SS_BOLD
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
        #     + SS_BOLD
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
            + BORDER_RADIUS.format(6)
            )
        self.tp_setting_GridLayout = QGridLayout()                     # 2. Grid 레이아웃 생성
        self.tp_setting_GroupBox.setLayout(self.tp_setting_GridLayout)            # 3. 레이아웃을 대상 위젯에 적용
        self.left_VBoxLayout.addWidget(self.tp_setting_GroupBox)           # 1-1. 상위 레이아웃에 위젯 적용

        # --- TP1 설정 ---
        # --- TP1 라벨 설정 ---
        self.tp1_Label = QLabel("TP1: ")
        self.tp1_Label.setStyleSheet(""
            + SS_BOLD
            # + BORDER_RADIUS.format(6)
            + "border-style: none;"
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
        # self.tp1_SpinBox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.tp1_HBoxLayout.addWidget(self.tp1_SpinBox)
        # 별도 버튼: 상승 / 하강
        self.tp1_up_btn = QPushButton("▲")
        self.tp1_down_btn = QPushButton("▼")
        for b in (self.tp1_up_btn, self.tp1_down_btn):
            b.setFixedWidth(28)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.tp1_up_btn.clicked.connect(self.tp1_SpinBox.stepUp)
        self.tp1_down_btn.clicked.connect(self.tp1_SpinBox.stepDown)
        self.tp1_HBoxLayout.addWidget(self.tp1_up_btn)
        self.tp1_HBoxLayout.addWidget(self.tp1_down_btn)

        # --- TP1 RCK 설정 ---
        # --- TP1 RCK 라벨 설정 ---
        self.tp1_rck_Label = QLabel("TP1 RCK: ")
        self.tp1_rck_Label.setStyleSheet(""
            + SS_BOLD
            # + BORDER_RADIUS.format(6)
            + "border-style: none;"
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
        # self.tp1_SpinBox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.tp1_rck_HBoxLayout.addWidget(self.tp1_rck_SpinBox)
        # 별도 버튼: 상승 / 하강
        self.tp1_rkc_up_btn = QPushButton("▲")
        self.tp1_rkc_down_btn = QPushButton("▼")
        for b in (self.tp1_rkc_up_btn, self.tp1_rkc_down_btn):
            b.setFixedWidth(28)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.tp1_rkc_up_btn.clicked.connect(self.tp1_rck_SpinBox.stepUp)
        self.tp1_rkc_down_btn.clicked.connect(self.tp1_rck_SpinBox.stepDown)
        self.tp1_rck_HBoxLayout.addWidget(self.tp1_rkc_up_btn)
        self.tp1_rck_HBoxLayout.addWidget(self.tp1_rkc_down_btn)


        # --- TP2 설정 ---
        # --- TP2 라벨 설정 ---
        self.tp2_Label = QLabel("TP2: ")
        self.tp2_Label.setStyleSheet(""
            + SS_BOLD
            # + BORDER_RADIUS.format(6)
            + "border-style: none;"
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
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.tp2_up_btn.clicked.connect(self.tp2_SpinBox.stepUp)
        self.tp2_down_btn.clicked.connect(self.tp2_SpinBox.stepDown)
        self.tp2_HBoxLayout.addWidget(self.tp2_up_btn)
        self.tp2_HBoxLayout.addWidget(self.tp2_down_btn)

        # --- TP 값 저장하기 버튼 설정 ---
        self.tp_setting_PushButton = QPushButton("🔄 TP 값 전송하기")
        self.tp_setting_PushButton.setStyleSheet(""
            + SS_BOLD
            )  # * 위젯 폰트 설정
        self.tp_setting_PushButton.setStyleSheet("""
            QPushButton:hover {
            background-color: #3366ff;
            }
            """)
        self.tp_setting_PushButton.clicked.connect(self.port_connection) # 버튼 기능 구현
        # addWidget(..., row, col, rowSpan, colSpan)의
        # 2 = 배치할 행(row) 인덱스 (0부터 시작)
        # 0 = 배치할 열(column) 인덱스 (0부터 시작)
        # 1 = 몇 행(rowSpan)을 차지할지 (여기선 1행)
        # 2 = 몇 열(columnSpan)을 차지할지 (여기선 2열)
        self.tp_setting_GridLayout.addWidget(self.tp_setting_PushButton, 4, 0, 1, 2)


        
    #     # 6. Plot Range Control 그룹
    #     range_control_group = QGroupBox("Plot Range Control")
    #     range_control_layout = QVBoxLayout()
    #     range_control_group.setLayout(range_control_layout)
        
    #     # 그래프 선택 콤보박스
    #     range_control_layout.addWidget(QLabel("Select Plot:"))
    #     self.plot_select_combo = QComboBox()
    #     self.plot_select_combo.addItems([
    #         "HW_HPF_BUFFER",
    #         "HW_HPF_BUFFER (Zoom)",
    #         "HW_BPF_BUFFER",
    #         "HW_BPF_BUFFER (Zoom)",
    #         "SW_HPF_BUFFER",
    #         "SW_HPF_BUFFER (Zoom)",
    #         "SW_BPF_BUFFER",
    #         "SW_BPF_BUFFER (Zoom)",
    #         "ADC_BUFFER",
    #         "ADC_BUFFER (Adaptive)",
    #     ])
    #     range_control_layout.addWidget(self.plot_select_combo)
        
    #     # Y축 범위 설정
    #     y_range_layout = QGridLayout()
    #     y_range_layout.addWidget(QLabel("Y Min:"), 0, 0)
    #     self.y_min_spinbox = QSpinBox()
    #     self.y_min_spinbox.setMinimum(-10000)
    #     self.y_min_spinbox.setMaximum(10000)
    #     self.y_min_spinbox.setValue(0)
    #     y_range_layout.addWidget(self.y_min_spinbox, 0, 1)
        
    #     y_range_layout.addWidget(QLabel("Y Max:"), 1, 0)
    #     self.y_max_spinbox = QSpinBox()
    #     self.y_max_spinbox.setMinimum(-10000)
    #     self.y_max_spinbox.setMaximum(10000)
    #     self.y_max_spinbox.setValue(4096)
    #     y_range_layout.addWidget(self.y_max_spinbox, 1, 1)
        
    #     range_control_layout.addLayout(y_range_layout)
        
    #     # Apply 버튼
    #     self.apply_range_button = QPushButton("Apply Y Range")
    #     self.apply_range_button.clicked.connect(self.apply_plot_range)
    #     range_control_layout.addWidget(self.apply_range_button)
        
    #     # Auto Range 버튼
    #     self.auto_range_button = QPushButton("🔄 Auto Range")
    #     self.auto_range_button.clicked.connect(self.reset_plot_range)
    #     range_control_layout.addWidget(self.auto_range_button)
        
    #     self.left_VBoxLayout.addWidget(range_control_group)
    #     self.left_VBoxLayout.addStretch(1)

    #     # --- 우측 패널 구성 ---
    #     # 1. 그래프 위젯 (3개의 탭 위젯으로 분리)
        
    #     # 상단: ADC RAW 그래프 (원본 신호)
    #     adc_raw_graph_group = QGroupBox("ADC RAW Data Plot")
    #     adc_raw_graph_layout = QVBoxLayout()
    #     adc_raw_graph_group.setLayout(adc_raw_graph_layout)
        
    #     self.adc_raw_plot_tabs = QTabWidget()
    #     self.adc_raw_plot_tabs.setMovable(True)  # 탭 드래그로 순서 변경 가능
    #     adc_raw_graph_layout.addWidget(self.adc_raw_plot_tabs)
        
    #     # 중단: SW 필터 그래프 (ADC_HPF + ADC_BPF) - 비활성화
    #     # sw_filter_graph_group = QGroupBox("SW Filter Data Plot (ADC_HPF, ADC_BPF)")
    #     # sw_filter_graph_layout = QVBoxLayout()
    #     # sw_filter_graph_group.setLayout(sw_filter_graph_layout)
        
    #     self.sw_filter_plot_tabs = QTabWidget()  # 참조용으로 유지
    #     # self.sw_filter_plot_tabs.setMovable(True)
    #     # sw_filter_graph_layout.addWidget(self.sw_filter_plot_tabs)
        
    #     # 3번째: HW 필터 채널 그래프 (HW_HPF + HW_BPF)
    #     hw_filter_graph_group = QGroupBox("HW Filter Data Plot (HW_HPF, HW_BPF)")
    #     hw_filter_graph_layout = QVBoxLayout()
    #     hw_filter_graph_group.setLayout(hw_filter_graph_layout)
        
    #     self.hw_filter_plot_tabs = QTabWidget()
    #     self.hw_filter_plot_tabs.setMovable(True)  # 탭 드래그로 순서 변경 가능
    #     hw_filter_graph_layout.addWidget(self.hw_filter_plot_tabs)
        
    #     # 4번째: SW 필터 채널 그래프 (SW_HPF + SW_BPF)
    #     sw_filter_2_graph_group = QGroupBox("SW Filter Data Plot (SW_HPF, SW_BPF)")
    #     sw_filter_2_graph_layout = QVBoxLayout()
    #     sw_filter_2_graph_group.setLayout(sw_filter_2_graph_layout)
        
    #     self.hw_filter_2_plot_tabs = QTabWidget()
    #     self.hw_filter_2_plot_tabs.setMovable(True)  # 탭 드래그로 순서 변경 가능
    #     sw_filter_2_graph_layout.addWidget(self.hw_filter_2_plot_tabs)
        
    #     # 2번째: FFT 스펙트럼 그래프 (주파수 분석)
    #     fft_graph_group = QGroupBox("FFT Spectrum Analysis (ADC_BUFFER -> Frequency Domain)")
    #     fft_graph_layout = QVBoxLayout()
    #     fft_graph_group.setLayout(fft_graph_layout)
        
    #     self.fft_plot_tabs = QTabWidget()
    #     self.fft_plot_tabs.setMovable(True)  # 탭 드래그로 순서 변경 가능
    #     fft_graph_layout.addWidget(self.fft_plot_tabs)

    #     # 각 데이터 타입별 플롯을 저장할 딕셔너리
    #     self.plots = {}
    #     self.plot_widgets = {}  # PlotWidget 저장용
    #     self.threshold_lines = {}  # TP1 임계값 가로선 저장용
    #     self.tp1_recheck_lines = {}  # TP1 Recheck 임계값 가로선 저장용
    #     self.exceed_plots = {}  # TP1 초과 지점 표시용 ScatterPlot
    #     self.exceed_labels = {}  # TP1 초과 개수 표시용 TextItem
    #     self.stats_labels = {}  # 통계 정보 표시용 TextItem
    #     self.tp1_value = 0  # TP1 값 저장
    #     self.tp1_recheck_value = 0  # TP1 Recheck 값 저장

    #     # ★ 탭을 미리 정해진 순서로 생성 (각 영역 내에서 드래그로 순서 변경 가능)
    #     # 1. ADC RAW 탭 (원본 신호) - TP1 선 및 초과점 표시 포함
    #     adc_raw_tab_configs = [
    #         ("ADC_BUFFER", (0, 4096), True),   # TP1 선 및 초과점 표시
    #         ("ADC_BUFFER (Adaptive)", None, True),  # TP1 선 및 초과점 표시
    #     ]
    #     for name, fixed_range, show_tp1 in adc_raw_tab_configs:
    #         self._create_plot_tab(name, fixed_range, show_tp1, tab_type="adc_raw")
        
    #     # 2. FFT 스펙트럼 탭 (주파수 분석) - 별도 그룹박스
    #     fft_tab_configs = [
    #         ("ADC_FFT", None),              # 전체 주파수 (0~50Hz)
    #         ("ADC_FFT (Zoom)", (0, 15)),    # 확대 (0~15Hz, PIR 관심 대역)
    #     ]
    #     for name, x_range in fft_tab_configs:
    #         self._create_fft_plot_tab(name, x_range, y_max=150)
        
    #     # 2. SW 필터 탭 (ADC_HPF, ADC_BPF) - 비활성화
    #     # sw_filter_tab_configs = [
    #     #     ("ADC_HPF_BUFFER", (0, 3500), True),
    #     #     ("ADC_HPF_BUFFER (Adaptive)", None, False),       # SW HPF
    #     #     ("ADC_BPF_BUFFER", (0, 3500), True),
    #     #     ("ADC_BPF_BUFFER (Adaptive)", None, False),       # SW BPF
    #     # ]
    #     # for name, fixed_range, show_tp1 in sw_filter_tab_configs:
    #     #     self._create_plot_tab(name, fixed_range, show_tp1, tab_type="sw_filter")
        
    #     # 3. HW 필터 탭 (HW_HPF, HW_BPF 채널) - 비활성화
    #     # hw_filter_tab_configs = [
    #     #     ("HW_HPF_BUFFER", (0, 4096), True),  # TP1 선 및 초과점 표시
    #     #     ("HW_HPF_BUFFER (Zoom)", (0, 300), True),        # HW HPF 확대 + TP1
    #     #     ("HW_BPF_BUFFER", (0, 4096), True),  # TP1 선 및 초과점 표시
    #     #     ("HW_BPF_BUFFER (Zoom)", (0, 300), True),        # HW BPF 확대 + TP1
    #     # ]
    #     # for name, fixed_range, show_tp1 in hw_filter_tab_configs:
    #     #     self._create_plot_tab(name, fixed_range, show_tp1, tab_type="hw_filter")
        
    #     # 4. SW 필터 탭 (SW_HPF, SW_BPF 채널) - 비활성화
    #     # sw_filter_2_tab_configs = [
    #     #     ("SW_HPF_BUFFER", (0, 4096), True),  # TP1 선 및 초과점 표시
    #     #     ("SW_HPF_BUFFER (Zoom)", (0, 300), True),        # SW HPF 확대 + TP1
    #     #     ("SW_BPF_BUFFER", (0, 4096), True),  # TP1 선 및 초과점 표시
    #     #     ("SW_BPF_BUFFER (Zoom)", (0, 300), True),        # SW BPF 확대 + TP1
    #     # ]
    #     # for name, fixed_range, show_tp1 in sw_filter_2_tab_configs:
    #     #     self._create_plot_tab(name, fixed_range, show_tp1, tab_type="hw_filter_2")


    #     # 2. 로그 위젯
    #     log_group = QGroupBox("Log")
    #     log_layout = QVBoxLayout()
    #     log_group.setLayout(log_layout)
        
    #     self.log_text = QTextEdit()
    #     self.log_text.setReadOnly(True)
    #     log_layout.addWidget(self.log_text)

    #     self.right_VBoxLayout.addWidget(adc_raw_graph_group, stretch=2)       # 1. 상단 그래프 (ADC RAW)
    #     self.right_VBoxLayout.addWidget(fft_graph_group, stretch=2)            # 2. FFT 스펙트럼
    #     # self.right_VBoxLayout.addWidget(sw_filter_graph_group, stretch=2)     # (SW 필터) - 비활성화
    #     # self.right_VBoxLayout.addWidget(hw_filter_graph_group, stretch=2)     # 3. HW 필터 - 비활성화
    #     # self.right_VBoxLayout.addWidget(sw_filter_2_graph_group, stretch=2)   # 4. SW 필터 (SW_HPF, SW_BPF) - 비활성화
    #     self.right_VBoxLayout.addWidget(log_group, stretch=1)  # 3. 로그
        
    #     # FFT 관련 변수 초기화
    #     self.sampling_rate = 100.0  # 100Hz (ADC_SPEED_MS = 10ms)



    #     # --- 시그널/슬롯 연결 ---
    #     self.connect_button.clicked.connect(self.port_connection)
    #     self.tp1_send_button.clicked.connect(self.send_tp1_command)
    #     self.tp2_send_button.clicked.connect(self.send_tp2_command)
    #     self.tp1_recheck_send_button.clicked.connect(self.send_tp1_recheck_command)
    #     self.get_settings_button.clicked.connect(self.send_get_settings_command)
    #     self.save_nvs_button.clicked.connect(self.send_save_nvs_command)
    #     self.reset_button.clicked.connect(self.send_reset_command)
        
    #     self.uart_thread = None
    #     self.command_sender = CommandSender()  # 명령 송신 객체

#################################################################################################################
        # --- 우측 패널 (그래프 + 로그) ---
        self.right_Widget = QWidget()                    # 1. 대상 위젯 생성
        self.right_Widget.setStyleSheet(""
            + "background-color: #77aaff;"
            + "border: 2px;"
            + "border-style: solid;"
            + "border-color: #3366ff;"
            + BORDER_RADIUS.format(6)
            + PADDING.format(10)
            + "color: #bbeeff;"
        )
        self.main_HBoxLayout.addWidget(self.right_Widget)    # 1-1. 상위 레이아웃에 위젯 적용
        self.right_VBoxLayout = QVBoxLayout()           # 2. 세로 방향 레이아웃 생성
        self.right_Widget.setLayout(self.right_VBoxLayout)   # 3. 레이아웃을 대상 위젯에 적용

        # self.right_Widget.setStyleSheet("background-color: #ffdbac; border: 1px solid #f1c27d;")
        # right_placeholder = QLabel("그래프 및 로그")
        # right_placeholder.setStyleSheet("font-size:16px; font-weight:bold; padding:12px; color: #e0ac69;")
        # self.right_VBoxLayout.addWidget(right_placeholder)

        self.adc_raw_graph_GroupBox = QGroupBox("ADC RAW Data Plot")             # 1. 대상 위젯 생성
        self.adc_raw_graph_GroupBox.setStyleSheet(""
            + PADDING.format(10)
        )
        self.right_VBoxLayout.addWidget(self.adc_raw_graph_GroupBox)           # 1-1. 상위 레이아웃에 위젯 적용
        self.adc_raw_graph_VBoxLayout = QVBoxLayout()                     # 2. 세로 방향 레이아웃 생성
        self.adc_raw_graph_GroupBox.setLayout(self.adc_raw_graph_VBoxLayout)            # 3. 레이아웃을 대상 위젯에 적용

        self.adc_raw_plot_TabWidget = QTabWidget()
        self.adc_raw_plot_TabWidget.setStyleSheet(""
            + PADDING.format(2)
        )
        self.adc_raw_plot_TabWidget.setMovable(True)  # 탭 드래그로 순서 변경 가능
        self.adc_raw_graph_VBoxLayout.addWidget(self.adc_raw_plot_TabWidget)
        
        self.adc_fft_plot_TabWidget = QTabWidget()
        self.adc_fft_plot_TabWidget.setStyleSheet(""
            + PADDING.format(2)
        )
        self.adc_fft_plot_TabWidget.setMovable(True)  # 탭 드래그로 순서 변경 가능
        self.adc_raw_graph_VBoxLayout.addWidget(self.adc_fft_plot_TabWidget)
    

        for graph_tab_name, graph_fixed_range in adc_raw_plot_TabWidget_configs:
            # self.create_plot_tab(graph_tab_name, graph_fixed_range, opt_show_tp1, tab_type="adc_raw")
            self.create_adc_plot_tab(graph_tab_name, graph_fixed_range)

        for name, x_range in adc_fft_plot_TabWidget_configs:
            self.create_fft_plot_tab(name, x_range, y_max=150)
#################################################################################################################

    # @pyqtSlot(bool)
    # def on_connection_status_changed(self, is_connected):
    #     """워커의 연결 상태 변경 시 UI 업데이트"""
    #     self.connect_button.setEnabled(True)
    #     if is_connected:
    #         self.connect_button.setText("Disconnect")
    #         # 모든 컨트롤 버튼 활성화
    #         self.tp1_send_button.setEnabled(True)
    #         self.tp2_send_button.setEnabled(True)
    #         self.tp1_recheck_send_button.setEnabled(True)
    #         self.get_settings_button.setEnabled(True)
    #         self.save_nvs_button.setEnabled(True)
    #         self.reset_button.setEnabled(True)
    #         # CommandSender에 시리얼 포트 설정
    #         if self.uart_thread and self.uart_thread.serial_port:
    #             self.command_sender.set_serial(self.uart_thread.serial_port)
    #     else:
    #         self.connect_button.setText("Connect")
    #         # 모든 컨트롤 버튼 비활성화
    #         self.tp1_send_button.setEnabled(False)
    #         self.tp2_send_button.setEnabled(False)
    #         self.tp1_recheck_send_button.setEnabled(False)
    #         self.get_settings_button.setEnabled(False)
    #         self.save_nvs_button.setEnabled(False)
    #         self.reset_button.setEnabled(False)
    #         self.command_sender.set_serial(None)
    #         # Clean up the thread object
    #         if self.uart_thread:
    #             self.uart_thread.deleteLater()
    #             self.uart_thread = None

    def insert_ports_to_ComboBox(self):
        """사용 가능한 시리얼 포트 목록 채우기"""
        self.port_sel_ComboBox.clear()
        ports = list_ports.comports()
        for port in ports:
            # self.port_sel_ComboBox.addItem(f"{port.device} : {port.description}", port.device)
            self.port_sel_ComboBox.addItem(f"{port.description}")
        if not ports:
            self.port_sel_ComboBox.addItem("No ports found")

    def refresh_ports(self):
        """COM Port 재검색 (버튼 클릭 시 호출)"""
        self.insert_ports_to_ComboBox()
        port_count = self.port_sel_ComboBox.count()
        if port_count > 0 and ("No ports found" not in self.port_sel_ComboBox.itemText(0)):
            self.log_text.append(f"🔍 COM Port 재검색 완료: {port_count}개 포트 발견")
        else:
            self.log_text.append("🔍 COM Port 재검색 완료: 포트를 찾을 수 없습니다")

    def insert_baudrates_to_ComboBox(self):
        """Baud Rate 목록 채우기"""
        self.baudrate_sel_ComboBox.clear()
        for rate in BaudRate:
            self.baudrate_sel_ComboBox.addItem(str(rate.value), rate.value)
        self.baudrate_sel_ComboBox.setCurrentText(str(BaudRate.BAUD_1152000.value))

    def port_connection(self):
        """연결/해제 토글"""
        if self.uart_thread and self.uart_thread.isRunning():
            # 연결 해제
            self.uart_thread.stop()
            self.connect_button.setText("Connect")
            self.log_text.append("Disconnected.")
        else:
            # 연결
            port = self.port_sel_ComboBox.currentData()
            baud = self.baudrate_sel_ComboBox.currentData()
            if not port or "No ports found" in port:
                self.log_text.append("Error: No serial port selected.")
                return

            self.uart_thread = UartWorker(port, baud)
            self.uart_thread.log_message.connect(self.log_text.append)
            self.uart_thread.new_data.connect(self.update_ui)
            self.uart_thread.connection_status.connect(self.on_connection_status_changed)
            self.uart_thread.start()
            
            self.connect_button.setText("Connecting...")
            self.connect_button.setEnabled(False) # Disable button while connecting

    # @pyqtSlot(object)
    # def update_ui(self, data: SensorData):
    #     """UI 업데이트: 로그, 그래프, 설정 표시"""
    #     # 1. 로그 텍스트 업데이트 (최대 500줄 제한)
    #     log_str = self._format_sensor_data_for_log(data)
    #     self.log_text.append(log_str)
        
    #     # 로그 줄 수 제한 (메모리 누수 방지)
    #     MAX_LOG_LINES = 500
    #     doc = self.log_text.document()
    #     if doc.blockCount() > MAX_LOG_LINES:
    #         cursor = self.log_text.textCursor()
    #         cursor.movePosition(cursor.MoveOperation.Start)
    #         cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, doc.blockCount() - MAX_LOG_LINES)
    #         cursor.removeSelectedText()
        
    #     self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

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
    #                     padding: 8px;
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
    def create_adc_plot_tab(self, graph_tab_name, graph_fixed_range=None):

        """플롯 탭을 미리 생성 (초기화 시 호출)
        Args:
            name: 플롯 이름
            fixed_range: Y축 고정 범위 (튜플) 또는 None (자동)
            show_tp1_line: TP1 임계선 표시 여부
            # tab_type: 탭 타입 ("adc_raw", "sw_filter", "hw_filter")
        """
        self.target_PlotWidget = PlotWidget()
        
        # 마우스 드래그(팬) 및 휠 줌 비활성화
        self.target_PlotWidget.setMouseEnabled(x=False, y=False)
        self.target_PlotWidget.setMenuEnabled(False)
    
        if graph_fixed_range:
            self.target_PlotWidget.setYRange(graph_fixed_range[0], graph_fixed_range[1], padding=0)
        self.target_PlotWidget.setTitle(f"{graph_tab_name}")

        # TP1 임계값 가로선 추가 (빨간색)
        self.tp1_InfiniteLine = InfiniteLine(
            pos=tp1_value, 
            angle=0,                                    # 선의 기울기(도 단위). 0은 수평(가로), 90은 수직(세로). 양수 값은 반시계 방향으로 회전합니다. 예: angle=0(가로), angle=45(대각선 위로 기울어진 선).
            pen=mkPen(
                color='#ff0000'                       # 선 색 (문자열 'r', 색 이름, 16진 문자열 '#ff0000', (R,G,B) 또는 (R,G,B,A) 튜플, 또는 QtGui.QColor 가능).
                , width=2                               # 선 굵기(픽셀)
                , style=QtCore.Qt.PenStyle.DashLine     # 선 스타일(점선/실선 등). SolidLine (실선), DashLine (대시선), DotLine (점선), DashDotLine, DashDotDotLine, NoPen (그리지 않음)
                ),
            label=f'TP1={tp1_value}',              # 이 그래프에서 어디에 보이는지:
            labelOpts={
                'position': 0.95                        # 0.0 ~ 1.0, 선을 따라 텍스트가 놓일 상대 위치 (예: 0.95). 0.95는 그래프의 하
                , 'color': '#ff0000'                  # 텍스트 색 (문자열/튜플/Qt color). 예: 'r' 또는 (255,0,0).
                , 'fill': (200, 200, 200, 100)          # 텍스트 배경 채우기 색 — RGBA 튜플 (R,G,B,A) 또는 QColor. A는 투명도(0~255). 예: (200,200,200,100).
                                                        # anchor: (옵션) 텍스트 정렬/앵커를 튜플로 지정할 수 있음(사용법은 약간 복잡).
                                                        # rotateAxis / angle: (환경/버전마다 이름이 다를 수 있음) 텍스트를 선과 함께 회전시킬 수 있는 옵션(선과 평행하게 표시).
                                                        # movable: (일부 버전에서) 라벨을 마우스로 이동 가능하게 할 수 있음.
                                                        # 구체적 사용 가능한 키와 동작은 설치된 pyqtgraph 버전 문서를 참조하세요.
                }
        )
        self.target_PlotWidget.addItem(self.tp1_InfiniteLine)
        threshold_lines[graph_tab_name] = self.tp1_InfiniteLine
        
        # TP1 Recheck 임계값 가로선 추가 (주황색)
        self.tp1_rck_InfiniteLine = InfiniteLine(
            pos=tp1_rck_value, 
            angle=0,
            pen=mkPen(
                color=(255, 165, 0)
                , width=2
                , style=QtCore.Qt.PenStyle.DashLine
                ),  # Orange
            label=f'TP1_RCK={tp1_rck_value}',
            labelOpts={
                'position': 0.85
                , 'color': (255, 165, 0)
                , 'fill': (200, 200, 200, 100)
                }
        )
        self.target_PlotWidget.addItem(self.tp1_rck_InfiniteLine)
        tp1_recheck_lines[graph_tab_name] = self.tp1_rck_InfiniteLine
            
        # plot_item = self.target_PlotWidget.plot(
        #     pen='y'
        #     , name=graph_tab_name
        #     )
        
        # 탭 타입에 따라 해당 탭 위젯에 추가
        # if tab_type == "adc_raw":
        #     self.adc_raw_plot_TabWidget.addTab(self.target_PlotWidget, graph_tab_name)
        # elif tab_type == "adc_fft":
        #     self.adc_fft_plot_TabWidget.addTab(self.target_PlotWidget, graph_tab_name)
        # elif tab_type == "sw_filter":
        #     self.sw_filter_plot_tabs.addTab(self.target_PlotWidget, name)
        # elif tab_type == "hw_filter":
        #     self.hw_filter_plot_tabs.addTab(self.target_PlotWidget, name)
        # elif tab_type == "hw_filter_2":
        #     self.hw_filter_2_plot_tabs.addTab(self.target_PlotWidget, name)

        self.adc_raw_plot_TabWidget.addTab(self.target_PlotWidget, graph_tab_name)

        
        # self.plot_widgets[graph_tab_name] = self.target_PlotWidget
        # self.adc_raw_plot_TabWigdet.addTab(self.plot_widgets[graph_tab_name], graph_tab_name)
        # plot_item = self.plot_widgets[graph_tab_name].plot(
        #     pen='y'
        #     , name=graph_tab_name
        #     )
        # self.plots[graph_tab_name] = plot_item

        # plot_item = self.target_PlotWidget.plot(
        #     pen='y'
        #     , name=graph_tab_name
        #     )
        # self.plots[graph_tab_name] = plot_item
        # self.plot_widgets[graph_tab_name] = self.target_PlotWidget

        # print("name : ", graph_tab_name, "\tself.plots[graph_tab_name] : ", self.plots[graph_tab_name], "\tself.plot_widgets[graph_tab_name] : ", self.plot_widgets[graph_tab_name])

    def create_fft_plot_tab(self, name, x_range=None, y_max=150):
        
        """FFT 스펙트럼 플롯 탭 생성
        Args:
            name: 플롯 이름 (예: "ADC_FFT", "ADC_FFT (Zoom)")
            x_range: X축 범위 (주파수 Hz) - 튜플 또는 None
            y_max: Y축 최대값 (진폭) - 기본값 150
        """

        # """플롯 탭을 미리 생성 (초기화 시 호출)
        # Args:
        #     name: 플롯 이름
        #     fixed_range: Y축 고정 범위 (튜플) 또는 None (자동)
        #     show_tp1_line: TP1 임계선 표시 여부
        #     tab_type: 탭 타입 ("adc_raw", "sw_filter", "hw_filter")
        # """

        self.target_PlotWidget = PlotWidget()
        
        # 마우스 드래그(팬) 및 휠 줌 비활성화
        self.target_PlotWidget.setMouseEnabled(x=False, y=False)
        self.target_PlotWidget.setMenuEnabled(False)
        
        # X축 라벨 설정 (주파수)
        self.target_PlotWidget.setLabel('bottom', 'Frequency', units='Hz')
        self.target_PlotWidget.setLabel('left', 'Magnitude')
        self.target_PlotWidget.setTitle(name)
        
        # X축 범위 설정
        if x_range:
            self.target_PlotWidget.setXRange(x_range[0], x_range[1], padding=0)
        
        # Y축 범위 고정 설정
        if y_max:
            self.target_PlotWidget.setYRange(0, y_max, padding=0)
        
        # 바 그래프 스타일로 그리기 (stepMode)
        plot_item = self.target_PlotWidget.plot(
            pen=mkPen(
                color=(0, 255, 255)
                , width=1
                ),  # Cyan
            fillLevel=0,
            fillBrush=(0, 255, 255, 80),  # 반투명 Cyan
            name=name
        )
        
        # 피크 주파수 표시용 텍스트 아이템
        peak_label = TextItem(anchor=(0, 1), color='y')
        self.target_PlotWidget.addItem(peak_label)
        
        # FFT 전용 탭에 추가
        self.target_PlotWidget.addTab(self.target_PlotWidget, name)
        
        # 저장
        self.plots[name] = plot_item
        self.plot_widgets[name] = self.target_PlotWidget
        
        # 피크 라벨 저장용 딕셔너리
        if not hasattr(self, 'fft_peak_labels'):
            self.fft_peak_labels = {}
        self.fft_peak_labels[name] = peak_label

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
    #     frequencies = np.fft.rfftfreq(n, d=1.0/self.sampling_rate)
        
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
    #         label = pg.TextItem(
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
        
    #     # 초과 개수 표시용 TextItem 생성
    #     if plot_name not in self.exceed_labels:
    #         label = pg.TextItem(
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
    #         self.log_text.append(f"[TX] TP1 설정 명령 전송: {tp1_value}")
    #         # 로컬 tp1_value 업데이트 및 그래프 임계선 업데이트
    #         self.tp1_value = tp1_value
    #         self._update_threshold_lines()
    #     else:
    #         self.log_text.append("[TX] TP1 전송 실패 - 연결 상태를 확인하세요")
    #         QMessageBox.warning(self, "전송 실패", "TP1 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")
    
    # def send_tp2_command(self):
    #     """TP2 값을 ESP32에 전송"""
    #     tp2_value = self.tp2_spinbox.value()
        
    #     if self.command_sender.send_set_tp2(tp2_value):
    #         self.log_text.append(f"[TX] TP2 설정 명령 전송: {tp2_value}")
    #     else:
    #         self.log_text.append("[TX] TP2 전송 실패 - 연결 상태를 확인하세요")
    #         QMessageBox.warning(self, "전송 실패", "TP2 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")
    
    # def send_tp1_recheck_command(self):
    #     """TP1_RECHECK 값을 ESP32에 전송"""
    #     tp1_recheck_value = self.tp1_recheck_spinbox.value()
        
    #     if self.command_sender.send_set_tp1_recheck(tp1_recheck_value):
    #         self.log_text.append(f"[TX] TP1_RECHECK 설정 명령 전송: {tp1_recheck_value}")
    #         # 로컬 tp1_recheck_value 업데이트 및 그래프 임계선 업데이트
    #         self.tp1_recheck_value = tp1_recheck_value
    #         self._update_threshold_lines()
    #     else:
    #         self.log_text.append("[TX] TP1_RECHECK 전송 실패 - 연결 상태를 확인하세요")
    #         QMessageBox.warning(self, "전송 실패", "TP1_RECHECK 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")
    
    # def send_get_settings_command(self):
    #     """ESP32에 현재 설정값을 요청"""
    #     if self.command_sender.send_get_settings():
    #         self.log_text.append("[TX] 설정값 요청 명령 전송")
    #     else:
    #         self.log_text.append("[TX] 설정값 요청 실패 - 연결 상태를 확인하세요")

    # def send_save_nvs_command(self):
    #     """현재 설정을 NVS(비휘발성 메모리)에 저장"""
    #     if self.command_sender.send_save_nvs():
    #         self.log_text.append("[TX] 💾 NVS 저장 명령 전송")
    #         QMessageBox.information(self, "NVS 저장", "설정값이 NVS에 저장되었습니다.")
    #     else:
    #         self.log_text.append("[TX] NVS 저장 실패 - 연결 상태를 확인하세요")
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
    #             self.log_text.append("[TX] 🔄 ESP32 리셋 명령 전송 (1초 후 리셋됨)")
    #         else:
    #             self.log_text.append("[TX] 리셋 실패 - 연결 상태를 확인하세요")

    # def apply_plot_range(self):
    #     """선택한 플롯의 Y축 범위를 적용"""
    #     plot_name = self.plot_select_combo.currentText()
    #     y_min = self.y_min_spinbox.value()
    #     y_max = self.y_max_spinbox.value()
        
    #     if plot_name in self.plot_widgets:
    #         plot_widget = self.plot_widgets[plot_name]
    #         plot_widget.setYRange(y_min, y_max, padding=0)
    #         self.log_text.append(f"📊 {plot_name} Y축 범위 설정: {y_min} ~ {y_max}")
    #     else:
    #         self.log_text.append(f"⚠️ 플롯 '{plot_name}'을 찾을 수 없습니다.")
    
    # def reset_plot_range(self):
    #     """선택한 플롯의 Y축 범위를 자동으로 리셋"""
    #     plot_name = self.plot_select_combo.currentText()
        
    #     if plot_name in self.plot_widgets:
    #         plot_widget = self.plot_widgets[plot_name]
    #         plot_widget.enableAutoRange(axis='y')
    #         self.log_text.append(f"🔄 {plot_name} Y축 자동 범위 활성화")
    #     else:
    #         self.log_text.append(f"⚠️ 플롯 '{plot_name}'을 찾을 수 없습니다.")

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