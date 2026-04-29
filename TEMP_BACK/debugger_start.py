"""
iSENSOR UART Debugger - GUI 버전

PyQt6와 pyqtgraph를 사용한 UART 데이터 시각화 도구
"""
import sys
import os
import time
import datetime
from typing import List, Optional
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
import numpy
import enum
import pyqtgraph
import math
import statistics
from collections import deque
import serial
from serial.tools import (list_ports)
import PyQt6.QtCore
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QGridLayout, QLabel, QTextEdit, QGroupBox, QTabWidget,
    QSpinBox, QDoubleSpinBox, QAbstractSpinBox, QMessageBox,
    QSizePolicy, QDialog, QCheckBox, QScrollArea, QDialogButtonBox
)
from PyQt6.QtGui import QShortcut, QKeySequence

import config                               as cfg
import uart_protocol.uart_protocol_config   as upcfg
import uart_protocol.uart_receive_parser    as upurp
import uart_protocol.data_parser            as updp
import uart_protocol.command_sender         as upcs
import uart_protocol.data_models            as updm
import fft
# ############################# COPILOT EDIT START (import AI modules)
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from AI.svm import svm
from AI import training_data_collector as tdc
from AI.mlp import nn_mlp
# ############################# COPILOT EDIT END

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
SVM_NAME = "SVM"

class IntAxisItem(pyqtgraph.AxisItem):
    """Y축 눈금을 정수배로만 표시하는 AxisItem.
    자동 스케일 환경에서 0.5, 1.5 같은 소수 눈금이 생기지 않도록 함.
    """
    def tickValues(self, minVal: float, maxVal: float, size: float):
        span = maxVal - minVal
        if span <= 0:
            return []
        # 화면 높이(px) 기준으로 눈금 간격(정수) 자동 결정 (최대 약 8개)
        raw_step = max(1, int(span / 8))
        # 1, 2, 5, 10, 20, 50 … 단위로 올림
        magnitude = 10 ** (len(str(raw_step)) - 1)
        for nice in (1, 2, 5, 10):
            step = nice * magnitude
            if span / step <= 10:
                break
        step = max(1, step)
        start = int(math.ceil(minVal / step)) * step
        ticks = list(range(start, int(math.floor(maxVal)) + 1, step))
        return [(step, ticks)]

    def tickStrings(self, values, scale, spacing):
        return [str(int(v)) for v in values]


class enum_graph_plot_num(enum.IntEnum):
    ADC_RAW = 0
    ADC_FFT = ADC_RAW + 1
    SVM     = ADC_FFT + 1
class enum_graph_plot_range_opt(enum.IntEnum):
    ALL         = 0
    ADAPTIVE    = ALL + 1

    SVM         = 0
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

class SvmFeatureDialog(QDialog):
    """SVM 학습/예측에 사용할 특징을 선택하는 다이얼로그

    Features:
        - 스펙트럼 전체 (magnitudes_0 ~ _150, 인덱스 0~150)
        - 통계 특징 9개 (인덱스 151~159) 개별 선택
    """
    # (표시 라벨, 시작 인덱스, 끝 인덱스+1)
    # ⭐ = 권장 선택 (기본 ON)  |  그 외 = 기본 OFF
    _FEATURE_DEFS = [
        ("spectral_rolloff       — 스펙트럼 롤오프 (Hz)",            int(svm.enum_csv_col.SPECTRAL_ROLLOFF),     int(svm.enum_csv_col.SPECTRAL_ROLLOFF)     + 1),
        ("spectral_bandwidth     — 스펙트럼 대역폭 (Hz)",            int(svm.enum_csv_col.SPECTRAL_BANDWIDTH),   int(svm.enum_csv_col.SPECTRAL_BANDWIDTH)   + 1),
        ("peak_count             — 피크 빈 개수 (avg+2σ 초과)",      int(svm.enum_csv_col.PEAK_COUNT),           int(svm.enum_csv_col.PEAK_COUNT)           + 1),
        ("mid_ratio              — 중주파 비율 (5~10Hz)",             int(svm.enum_csv_col.MID_RATIO),            int(svm.enum_csv_col.MID_RATIO)            + 1),
        ("⭐ low_to_high_ratio   — 저/고주파 에너지 비율",            int(svm.enum_csv_col.LOW_TO_HIGH_RATIO),    int(svm.enum_csv_col.LOW_TO_HIGH_RATIO)    + 1),
        ("second_peak_freq       — 2번째 피크 주파수 (Hz)",           int(svm.enum_csv_col.SECOND_PEAK_FREQ),     int(svm.enum_csv_col.SECOND_PEAK_FREQ)     + 1),
        ("⭐ kurtosis            — 에너지 분포 첨도",                 int(svm.enum_csv_col.KURTOSIS),             int(svm.enum_csv_col.KURTOSIS)             + 1),
        ("⭐ centroid            — 스펙트럼 무게중심 (Hz)",            int(svm.enum_csv_col.CENTROID),             int(svm.enum_csv_col.CENTROID)             + 1),
        ("⭐ peak_freq           — 1위 피크 주파수 (Hz)",              int(svm.enum_csv_col.PEAK_FREQ),            int(svm.enum_csv_col.PEAK_FREQ)            + 1),
        ("⭐ low_ratio           — 저주파 비율 (0~5Hz)",               int(svm.enum_csv_col.LOW_RATIO),            int(svm.enum_csv_col.LOW_RATIO)            + 1),
        ("⭐ rms                 — RMS 에너지",                       int(svm.enum_csv_col.RMS),                  int(svm.enum_csv_col.RMS)                  + 1),
        ("⭐ avg_energy          — 평균 에너지 (정수)",                int(svm.enum_csv_col.AVG_ENERGY),           int(svm.enum_csv_col.AVG_ENERGY)           + 1),
        ("peak_energy            — 피크 에너지 (정수)",                int(svm.enum_csv_col.PEAK_ENERGY),          int(svm.enum_csv_col.PEAK_ENERGY)          + 1),
        ("energy_variance        — 에너지 분산",                      int(svm.enum_csv_col.ENERGY_VARIANCE),      int(svm.enum_csv_col.ENERGY_VARIANCE)      + 1),
        ("⭐ peak_to_avg_e       — 피크/평균 에너지 비율",             int(svm.enum_csv_col.PEAK_TO_AVG_E),        int(svm.enum_csv_col.PEAK_TO_AVG_E)        + 1),
        ("high_ratio             — 고주파 비율 (10Hz+)",              int(svm.enum_csv_col.HIGH_RATIO),           int(svm.enum_csv_col.HIGH_RATIO)           + 1),
        ("⭐ peak1_to_peak2_ratio — 1위/2위 피크 에너지 비율",         int(svm.enum_csv_col.PEAK1_TO_PEAK2_RATIO), int(svm.enum_csv_col.PEAK1_TO_PEAK2_RATIO) + 1),
        ("⭐ skewness            — 에너지 분포 왜도",                  int(svm.enum_csv_col.SKEWNESS),             int(svm.enum_csv_col.SKEWNESS)             + 1),
        ("dc_ratio               — DC 에너지 비율 (잔류 DC)",           int(svm.enum_csv_col.DC_RATIO),             int(svm.enum_csv_col.DC_RATIO)             + 1),
        ("delta_peak_freq        — 프레임 간 피크 주파수 변화량 (Hz)",   int(svm.enum_csv_col.DELTA_PEAK_FREQ),      int(svm.enum_csv_col.DELTA_PEAK_FREQ)      + 1),
        ("spectral_flatness      — 스펙트럼 평탄도 (0=순수톤, 1=백색잡음)", int(svm.enum_csv_col.SPECTRAL_FLATNESS),    int(svm.enum_csv_col.SPECTRAL_FLATNESS)    + 1),
    ]

    def __init__(self, current_indices: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SVM 특징 선택")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        info_label = QLabel("학습·예측에 사용할 특징을 선택하세요.\n(변경 후 재학습이 필요합니다)")
        info_label.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(info_label)

        # 체크박스 생성
        self._checkboxes: list[QCheckBox] = []
        current_set = set(current_indices)
        for label, i_start, i_end in self._FEATURE_DEFS:
            cb = QCheckBox(label)
            # 해당 범위 인덱스가 모두 포함돼 있으면 체크
            cb.setChecked(all(i in current_set for i in range(i_start, i_end)))
            layout.addWidget(cb)
            self._checkboxes.append(cb)

        # 경고 레이블
        self._warn_label = QLabel("")
        self._warn_label.setStyleSheet("color: #e05050; padding: 2px;")
        layout.addWidget(self._warn_label)

        # 버튼
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_accept(self):
        if not any(cb.isChecked() for cb in self._checkboxes):
            self._warn_label.setText("⚠ 최소 하나 이상 선택해야 합니다.")
            return
        self.accept()

    def get_feature_indices(self) -> list:
        """선택된 특징의 컬럼 인덱스 목록(정렬) 반환"""
        indices = []
        for cb, (_, i_start, i_end) in zip(self._checkboxes, self._FEATURE_DEFS):
            if cb.isChecked():
                indices.extend(range(i_start, i_end))
        return sorted(indices)


class SvmTrainWorker(PyQt6.QtCore.QThread):
    """SVM 학습을 백그라운드에서 실행하는 워커 스레드"""
    finished = PyQt6.QtCore.pyqtSignal(bool)  # 학습 성공 여부

    def __init__(self, svm_handle, str_csv_path: str):
        super().__init__()
        self._svm_handle   = svm_handle
        self._str_csv_path = str_csv_path

    def run(self):
        result = self._svm_handle.train(self._str_csv_path)
        self.finished.emit(result)


class SvmRebuild2dWorker(PyQt6.QtCore.QThread):
    """X/Y 2D SVM 재학습을 백그라운드에서 실행"""
    finished = PyQt6.QtCore.pyqtSignal(object, object, object, object)  # scaler, model, x_col, y_col

    def __init__(self, X_full, y, xi_col, yi_col, x_col, y_col):
        super().__init__()
        self._X_full  = X_full
        self._y       = y
        self._xi_col  = xi_col
        self._yi_col  = yi_col
        self._x_col   = x_col
        self._y_col   = y_col

    def run(self):
        X_2d      = self._X_full[:, [self._xi_col, self._yi_col]]
        scaler_2d = StandardScaler()
        X_scaled  = scaler_2d.fit_transform(X_2d)
        model_2d  = SVC(kernel='rbf', C=1.0, gamma='scale', probability=True)
        model_2d.fit(X_scaled, self._y)
        self.finished.emit(scaler_2d, model_2d, self._x_col, self._y_col)


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
        self.f_sampling_rate = input_f_sampling_rate
        self.fft_handle.f_sampling_rate = self.f_sampling_rate
        self.svm_handle.f_sampling_rate = self.f_sampling_rate

    def value_init(self):        
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
        self.A_svm_plot_TabWidget_configs:list = [
            # PLOT_NAME_INDEX, INT_GRAPH_X_RANGE(x), INT_GRAPH_Y_RANGE(y)
            [
                "TEMP_PLOT_NAME - 1.0"
                , 0, "POS", 'LABEL'
                , 0, "POS", 'LABEL'
                , "#000000", "TEMP_LEGEND"
            ],
            # [
            #     "TEMP_PLOT_NAME - 1.1"
            #     , 0, "POS", 'LABEL'
            #     , 0, "POS", 'LABEL'
            #     , "#000000", "TEMP_LEGEND"
            # ],
        ]
        self.A_graph_plot_value.append(self.A_adc_raw_plot_TabWidget_configs)   # 0
        self.A_graph_plot_value.append(self.A_adc_fft_plot_TabWidget_configs)   # 1
        self.A_graph_plot_value.append(self.A_svm_plot_TabWidget_configs)       # 2
        self.uart_thread = None
        self.command_sender = upcs.CommandSender()  # 명령 송신 객체
        self._settings_loaded: bool = False  # 초기 설정값 수신 여부 (한 번만 SpinBox 반영)

        self.b_auto_save_bg:bool    = False  # 배경 자동 저장 토글 상태
        self.b_auto_save_human:bool = False  # 사람 자동 저장 토글 상태
        self.i_auto_save_stride:int = 1      # 자동 저장 주기 (FFT 갱신 횟수)
        self.i_fft_since_last_save:int = 0   # 마지막 저장 이후 FFT 갱신 횟수

        self.A_adc_buffer     = []
        self.i_adc_buffer_len = 0
        self.i_adc_min        = 0
        self.i_adc_mid        = 0
        self.i_adc_max        = 0
        self.f_adc_avg        = 0.0
        self.f_adc_std        = 0.0

        self.A_adc_exclusion_zero_buffer     = []
        self.i_adc_exclusion_zero_buffer_len = 0
        self.i_adc_exclusion_zero_min        = 0
        self.i_adc_exclusion_zero_mid        = 0
        self.i_adc_exclusion_zero_max        = 0
        self.f_adc_exclusion_zero_avg        = 0.0
        self.f_adc_exclusion_zero_std        = 0.0
        

        self.i_tp1_over_count                = 0
        self.i_tp1_rck_over_count            = 0


        self.fft_handle:fft.FFT_Module = fft.FFT_Module()
        self.A_fft_frequencies         = []
        self.A_fft_magnitudes          = []
        self.f_fft_gain                = 0
        self.f_fft_adc_avg             = 0
        self.i_fft_peak_idx            = 0
        self.f_fft_peak_freq           = 0
        self.f_fft_peak_mag            = 0
        self.fft_features_data         = None   # FftFeaturesData (타입 13)
        self._last_auto_saved_fft_features = None   # 자동 저장 중복 방지 (동일 패킷 겹치기 차단)
        # # ############################# COPILOT EDIT START (svm 핸들 초기화 + Phase 3 히스토리)
        self.svm_handle:svm.SVM_Module      = svm.SVM_Module()
        self.collector:tdc.TrainingDataCollector = tdc.TrainingDataCollector()  # data_csv/svm_data_TIMESTAMP.csv 자동 생성
        # ############################# COPILOT EDIT START (mlp 핸들 초기화)
        self.mlp_handle:nn_mlp.MLP_Module = nn_mlp.MLP_Module()
        self.A_mlp_probability  = [1.0, 0.0]
        self.i_mlp_label        = 0
        self.f_mlp_confidence   = 0.0
        self._mlp_history: deque = deque(maxlen=100)  # 최근 100프레임 판정 이력
        # ############################# COPILOT EDIT END

        self.svm_x_col:svm.enum_csv_col = svm.enum_csv_col.SPECTRAL_FLATNESS
        self.svm_y_col:svm.enum_csv_col = svm.enum_csv_col.LOW_RATIO

        # 결정 경계 재계산 캐시 (뷰 범위/축 변경 시에만 재계산)
        self._svm_boundary_cache        = None   # (x_min, x_max, y_min, y_max, x_col, y_col)
        self._svm_pca_boundary_cache    = None   # (x_min, x_max, y_min, y_max)

        # 사용자가 직접 zoom/pan 했는지 여부 (True면 autoRange 호출 안 함)
        self._b_svm_user_zoomed:bool     = False
        self._b_svm_pca_user_zoomed:bool = False

        # X/Y 2특징 전용 SVM (2D 판정용)
        self._svm_2d_model   = None   # SVC (2D)
        self._svm_2d_scaler  = None   # StandardScaler (2D)
        self._svm_2d_x_col   = None   # 마지막으로 학습한 x_col
        self._svm_2d_y_col   = None   # 마지막으로 학습한 y_col
        self._svm_2d_label   = 0
        self._svm_2d_conf    = 0.0
        self._svm_2d_proba   = []

        self.A_svm_probabilty           = []
        self.i_svm_label                = 0
        self.f_svm_confidence           = 0.0

        # self.svm_handle.str_svm_csv_path:str             = "svm_data.csv"
        # self.str_svm_waveform_csv_path:str    = "svm_waveforms.csv"
        # self._SVM_HISTORY_MAXLEN:int          = 60
        # self._svm_history:deque               = deque(maxlen=self._SVM_HISTORY_MAXLEN)
        # self._last_adc_raw:list               = []
        # self._svm_waveform_overlay_items:list = []
        # # ############################# COPILOT EDIT END

        self.adc_window_size_setting(cfg.WINDOW_SIZE)
        self.adc_tp1_setting(10)
        self.adc_tp1_rck_setting(1000)
        self.adc_smapling_rate_setting(100)


        
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
        self.graph_x_range_setting(self.f_sampling_rate / 2, enum_graph_plot_num.ADC_FFT)
        self.graph_x_label_pos_setting("bottom", enum_graph_plot_num.ADC_FFT)
        self.graph_x_label_setting("주파수(Hz)", enum_graph_plot_num.ADC_FFT)
        self.graph_y_range_setting(self.adc_bit_2_range(12) / 2, enum_graph_plot_num.ADC_FFT, enum_graph_plot_range_opt.ALL)
        self.graph_y_label_pos_setting("left", enum_graph_plot_num.ADC_FFT)
        self.graph_y_label_setting("강도", enum_graph_plot_num.ADC_FFT)
        self.graph_line_color_setting(cfg.ADC_FFT_LINE_COLOR, enum_graph_plot_num.ADC_FFT)
        self.graph_legend_setting('FFT 분포', enum_graph_plot_num.ADC_FFT)

        self.graph_title_setting(SVM_NAME, enum_graph_plot_num.SVM, enum_graph_plot_range_opt.ALL)
        # self.graph_x_range_setting(self.f_sampling_rate / 2, enum_graph_plot_num.SVM)
        self.graph_x_label_pos_setting("bottom", enum_graph_plot_num.SVM)
        self.graph_x_label_setting("피크 주파수(Hz)", enum_graph_plot_num.SVM)
        # self.graph_y_range_setting(self.adc_bit_2_range(12) / 2, enum_graph_plot_num.SVM, enum_graph_plot_range_opt.ALL)
        self.graph_y_label_pos_setting("left", enum_graph_plot_num.SVM)
        self.graph_y_label_setting("피크 강도", enum_graph_plot_num.SVM)
        self.graph_line_color_setting(cfg.SVM_LINE_COLOR, enum_graph_plot_num.SVM)
        # self.graph_legend_setting('FFT 분포', enum_graph_plot_num.SVM)

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
        self.left_GridLayout = QGridLayout()            # 2. 2열 그리드 레이아웃 생성
        self.left_GridLayout.setColumnStretch(0, 1)     # 좌열 / 우열 동등 비율
        self.left_GridLayout.setColumnStretch(1, 1)
        self.left_Widget.setLayout(self.left_GridLayout)     # 3. 레이아웃을 대상 위젯에 적용
# --- 제어창 표시 설정 ---
        self.left_control_Label = QLabel("제어창")             # 1. 대상 위젯 생성
        self.left_control_Label.setStyleSheet(""
                                              + MACRO_FONT_BOLD
                                              + MACRO_FONT_SIZE.format(14)
                                              )  # * 위젯 폰트 설정
        self.left_control_Label.setFixedHeight(30)             # * 위젯 가로 사이즈 설정
        self.left_GridLayout.addWidget(self.left_control_Label, 0, 0, 1, 2)    # Row0 - 전체 2열 차지
# --- Connection 그룹 설정 ---
        self.connection_GroupBox = QGroupBox("Connection")             # 1. 대상 위젯 생성
        # self.connection_GroupBox.setFlat(True)
        self.connection_GridLayout = QGridLayout()                     # 2. Grid 레이아웃 생성 
        self.connection_GroupBox.setLayout(self.connection_GridLayout)            # 3. 레이아웃을 대상 위젯에 적용
        self.left_GridLayout.addWidget(self.connection_GroupBox, 1, 0)          # Row1 Col0 - Connection

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
        self.status_GroupBox = QGroupBox("Status")             # 1. 대상 위젯 생성
        self.status_GroupBox.setStyleSheet(""
                                           + MACRO_BORDER_RADIUS.format(6)
                                           )
        self.status_GridLayout = QGridLayout()                     # 2. Grid 레이아웃 생성
        self.status_GroupBox.setLayout(self.status_GridLayout)            # 3. 레이아웃을 대상 위젯에 적용
        self.left_GridLayout.addWidget(self.status_GroupBox, 2, 0, 2, 1)       # Row2-3 Col0 - Setting(Status)

        # --- 제어창 표시 설정 ---
        self.connect_status_Label = QLabel("🔴 Not connected")
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

        # --- MLP 추론 결과 표시 설정 ---
        self.mlp_result_Label = QLabel("🤖 MLP: 모델 로딩 중...")
        self.mlp_result_Label.setStyleSheet(""
                                            + MACRO_FONT_BOLD
                                            + MACRO_FONT_SIZE.format(14)
                                            )
        self.status_GridLayout.addWidget(self.mlp_result_Label)
        # 초기 MLP 상태 반영
        if self.mlp_handle.b_is_trained:
            self.mlp_result_Label.setText("🤖 MLP: 대기 중 (모델 로드 완료)")
        else:
            self.mlp_result_Label.setText("🤖 MLP: 미로드 (모델 없음)")

        # --- 프로파일링 표시 설정 ---
        self.profiling_Label = QLabel("⏱ 프로파일링: 대기 중")
        self.profiling_Label.setStyleSheet(""
                                           + MACRO_FONT_SIZE.format(11)
                                           + MACRO_BORDER_STYLE.format('none')
                                           )
        self.profiling_Label.setWordWrap(True)
        self.status_GridLayout.addWidget(self.profiling_Label)

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
        # tp_setting_GroupBox는 ESP Control에 통합되므로 left_GridLayout에 추가하지 않음

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
        self.tp2_SpinBox.setMaximum(4096)  # SpinBox는 int32 최대값까지만 지원
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

        # ############################# COPILOT EDIT START (FFT Gain 그룹박스 + SVM Data Collect 그룹박스 UI)
        # --- FFT Setting (게인 + Stride) ---
        self.fft_gain_GroupBox = QGroupBox("FFT Setting")             # 1. 대상 위젯 생성
        self.fft_gain_GroupBox.setStyleSheet(""
                                               + MACRO_BORDER_RADIUS.format(6)
                                               )
        self.fft_gain_GridLayout = QGridLayout()                     # 2. Grid 레이아웃 생성
        self.fft_gain_GroupBox.setLayout(self.fft_gain_GridLayout)            # 3. 레이아웃을 대상 위젯에 적용
        self.left_GridLayout.addWidget(self.fft_gain_GroupBox, 4, 0, 1, 2)            # Row4 Col0-1 - FFT Setting (전체 폭)


        # --- Gain 라벨 ---
        self.fft_gain_Label = QLabel("Gain: ")
        self.fft_gain_Label.setStyleSheet(""
                                          + MACRO_FONT_BOLD
                                          + MACRO_BORDER_STYLE.format('none')
                                          )
        self.fft_gain_Label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.fft_gain_GridLayout.addWidget(self.fft_gain_Label, 0, 0)

        self.fft_gain_HBoxLayout = QHBoxLayout()
        self.fft_gain_GridLayout.addLayout(self.fft_gain_HBoxLayout, 0, 1)
        self.fft_gain_SpinBox = QDoubleSpinBox()
        self.fft_gain_SpinBox.setMinimum(0.1)
        self.fft_gain_SpinBox.setMaximum(1000.0)
        self.fft_gain_SpinBox.setSingleStep(1.0)
        self.fft_gain_SpinBox.setDecimals(1)
        self.fft_gain_SpinBox.setValue(20.0)  # 기본값
        self.fft_gain_SpinBox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.fft_gain_SpinBox.valueChanged.connect(self._on_fft_gain_changed)
        self.fft_gain_HBoxLayout.addWidget(self.fft_gain_SpinBox)
        self.fft_gain_up_btn = QPushButton("▲")
        self.fft_gain_down_btn = QPushButton("▼")
        for b in (self.fft_gain_up_btn, self.fft_gain_down_btn):
            b.setFixedWidth(28)
            b.setFocusPolicy(PyQt6.QtCore.Qt.FocusPolicy.NoFocus)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.fft_gain_up_btn.clicked.connect(self.fft_gain_SpinBox.stepUp)
        self.fft_gain_down_btn.clicked.connect(self.fft_gain_SpinBox.stepDown)
        self.fft_gain_HBoxLayout.addWidget(self.fft_gain_up_btn)
        self.fft_gain_HBoxLayout.addWidget(self.fft_gain_down_btn)

        # --- FFT Stride 라벨 ---
        self.fft_stride_Label = QLabel("Stride (smp):")
        self.fft_stride_Label.setStyleSheet(""
                                            + MACRO_FONT_BOLD
                                            + MACRO_BORDER_STYLE.format('none')
                                            )
        self.fft_stride_Label.setToolTip("smp = sample(\uc0d8\ud50c)\n"
                                         "ESP\uc5d0\uc11c ADC \uc0d8\ud50c\uc744 N\uac1c \uc218\uc9d1\ud560 \ub54c\ub9c8\ub2e4 FFT\ub97c 1\ud68c \uc2e4\ud589\n"
                                         "Fs = 100 Hz \u2192 1 smp = 10 ms")
        self.fft_stride_Label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.fft_gain_GridLayout.addWidget(self.fft_stride_Label, 1, 0)

        self.fft_stride_HBoxLayout = QHBoxLayout()
        self.fft_gain_GridLayout.addLayout(self.fft_stride_HBoxLayout, 1, 1)
        self.fft_stride_SpinBox = QSpinBox()
        self.fft_stride_SpinBox.setMinimum(1)
        self.fft_stride_SpinBox.setMaximum(256)   # WINDOW_SIZE 상한
        self.fft_stride_SpinBox.setSingleStep(1)
        self.fft_stride_SpinBox.setValue(32)      # 기본값 (FFT_STRIDE = WINDOW_SIZE/8 = 32)
        self.fft_stride_SpinBox.setSuffix("")
        self.fft_stride_SpinBox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.fft_stride_SpinBox.setToolTip("ADC 몇 샘플마다 FFT를 1회 실행할지 결정\n"
                                           "1 smp = 10 ms (Fs=100 Hz) 예) 32 smp = 320 ms")
        self.fft_stride_HBoxLayout.addWidget(self.fft_stride_SpinBox)
        self.fft_stride_up_btn = QPushButton("▲")
        self.fft_stride_down_btn = QPushButton("▼")
        for b in (self.fft_stride_up_btn, self.fft_stride_down_btn):
            b.setFixedWidth(28)
            b.setFocusPolicy(PyQt6.QtCore.Qt.FocusPolicy.NoFocus)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.fft_stride_up_btn.clicked.connect(self.fft_stride_SpinBox.stepUp)
        self.fft_stride_down_btn.clicked.connect(self.fft_stride_SpinBox.stepDown)
        self.fft_stride_HBoxLayout.addWidget(self.fft_stride_up_btn)
        self.fft_stride_HBoxLayout.addWidget(self.fft_stride_down_btn)

        # FFT Stride ms 표시 라벨 (SpinBox 값 변경 시 자동 갱신)
        self.fft_stride_ms_Label = QLabel("= 32 smp × 10 ms/smp = 320 ms (0.32 s)")
        self.fft_stride_ms_Label.setStyleSheet("" + MACRO_BORDER_STYLE.format('none'))
        self.fft_gain_GridLayout.addWidget(self.fft_stride_ms_Label, 2, 0, 1, 2)
        self.fft_stride_SpinBox.valueChanged.connect(
            lambda v: self.fft_stride_ms_Label.setText(
                f"= {v} smp × 10 ms/smp = {v * 10} ms ({v * 10 / 1000:.2f} s)"
            )
        )

        # FFT Stride 전송 버튼
        self.fft_stride_send_PushButton = QPushButton("📡 Stride 전송")
        self.fft_stride_send_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.fft_stride_send_PushButton.clicked.connect(self.event_send_fft_stride_command)
        self.fft_gain_GridLayout.addWidget(self.fft_stride_send_PushButton, 3, 0, 1, 2)



############################################################################################################ SVM
        # --- SVM 데이터 수집 ---
        self.svm_collect_GroupBox = QGroupBox("SVM Setting")
        self.svm_collect_GroupBox.setStyleSheet("" + MACRO_BORDER_RADIUS.format(6))
        self.svm_collect_GridLayout = QGridLayout()
        self.svm_collect_GroupBox.setLayout(self.svm_collect_GridLayout)
        self.left_GridLayout.addWidget(self.svm_collect_GroupBox, 5, 0, 1, 2)          # Row5 Col0-1 - SVM Setting (전체 폭)

        # 샘플 카운트 레이블
        self.svm_count_Label = QLabel("BackGround : 0  |  Occupancy : 0")
        self.svm_count_Label.setStyleSheet("" + MACRO_FONT_BOLD + MACRO_BORDER_STYLE.format('none'))
        self.svm_collect_GridLayout.addWidget(self.svm_count_Label, 0, 0, 1, 2)

        # 배경 저장 버튼
        self.svm_bg_PushButton = QPushButton("💾 배경 저장")
        self.svm_bg_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.svm_bg_PushButton.clicked.connect(self.event_svm_save_background)
        self.svm_collect_GridLayout.addWidget(self.svm_bg_PushButton, 1, 0)

        # 사람 저장 버튼
        self.svm_human_PushButton = QPushButton("💾 사람 저장")
        self.svm_human_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.svm_human_PushButton.clicked.connect(self.event_svm_save_occupancy)
        self.svm_collect_GridLayout.addWidget(self.svm_human_PushButton, 1, 1)

        # 자동 저장 토글 버튼
        _TOGGLE_STYLE = (
            "QPushButton { font-weight: bold; border: 1px solid gray; border-radius: 4px; padding: 3px; }"
            "QPushButton:checked { background-color: #2e8b2e; color: white; border: 1px solid #1a5c1a; }"
        )
        self.svm_auto_bg_ToggleButton = QPushButton("🔴 배경 자동 OFF  [1]")
        self.svm_auto_bg_ToggleButton.setCheckable(True)
        self.svm_auto_bg_ToggleButton.setStyleSheet(_TOGGLE_STYLE)
        self.svm_auto_bg_ToggleButton.toggled.connect(self.event_svm_auto_bg_toggled)
        self.svm_collect_GridLayout.addWidget(self.svm_auto_bg_ToggleButton, 2, 0)

        self.svm_auto_human_ToggleButton = QPushButton("🔴 사람 자동 OFF  [2]")
        self.svm_auto_human_ToggleButton.setCheckable(True)
        self.svm_auto_human_ToggleButton.setStyleSheet(_TOGGLE_STYLE)
        self.svm_auto_human_ToggleButton.toggled.connect(self.event_svm_auto_human_toggled)
        self.svm_collect_GridLayout.addWidget(self.svm_auto_human_ToggleButton, 2, 1)

        # 자동 저장 주기 설정 (FFT 갱신 횟수 기반)
        _interval_label = QLabel("저장 주기(FFT 횟수):")
        _interval_label.setStyleSheet("" + MACRO_FONT_BOLD)
        self.svm_collect_GridLayout.addWidget(_interval_label, 3, 0)
        self.svm_auto_save_interval_SpinBox = QSpinBox()
        self.svm_auto_save_interval_SpinBox.setRange(1, 500)
        self.svm_auto_save_interval_SpinBox.setSingleStep(1)
        self.svm_auto_save_interval_SpinBox.setValue(1)
        self.svm_auto_save_interval_SpinBox.setSuffix(" 회")
        self.svm_auto_save_interval_SpinBox.valueChanged.connect(self.event_svm_auto_save_interval_changed)
        self.svm_collect_GridLayout.addWidget(self.svm_auto_save_interval_SpinBox, 3, 1)

        # 단축키: 1=배경 자동 토글, 2=사람 자동 토글, 3=학습 데이터 삭제
        QShortcut(QKeySequence("1"), self).activated.connect(
            lambda: self.svm_auto_bg_ToggleButton.setChecked(not self.svm_auto_bg_ToggleButton.isChecked())
        )
        QShortcut(QKeySequence("2"), self).activated.connect(
            lambda: self.svm_auto_human_ToggleButton.setChecked(not self.svm_auto_human_ToggleButton.isChecked())
        )
        QShortcut(QKeySequence("3"), self).activated.connect(self.event_svm_clear)

        # SVM 학습 버튼
        self.svm_train_PushButton = QPushButton("🤖 SVM 학습")
        self.svm_train_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.svm_train_PushButton.clicked.connect(self.event_svm_train)
        self.svm_collect_GridLayout.addWidget(self.svm_train_PushButton, 4, 0, 1, 2)

        # 학습 상태 레이블
        self.svm_status_Label = QLabel("미학습")
        self.svm_status_Label.setStyleSheet("" + MACRO_FONT_BOLD + MACRO_BORDER_STYLE.format('none'))
        self.svm_collect_GridLayout.addWidget(self.svm_status_Label, 5, 0, 1, 2)

        # 학습 데이터 삭제 버튼
        self.svm_clear_PushButton = QPushButton("🗑 학습 데이터 삭제  [3]")
        self.svm_clear_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.svm_clear_PushButton.clicked.connect(self.event_svm_clear)
        self.svm_collect_GridLayout.addWidget(self.svm_clear_PushButton, 6, 0, 1, 2)

        # 특징 선택 버튼
        self.svm_feature_PushButton = QPushButton("⚙ 특징 선택...")
        self.svm_feature_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.svm_feature_PushButton.clicked.connect(self.event_svm_feature_select)
        self.svm_collect_GridLayout.addWidget(self.svm_feature_PushButton, 7, 0, 1, 2)

        # 현재 선택된 특징 수 표시 레이블
        self.svm_feature_count_Label = QLabel(f"선택된 특징: 24개 (권장 세트)")
        self.svm_feature_count_Label.setStyleSheet("" + MACRO_BORDER_STYLE.format('none'))
        self.svm_collect_GridLayout.addWidget(self.svm_feature_count_Label, 8, 0, 1, 2)

        # X/Y 축 선택 콤보박스
        self.svm_collect_GridLayout.addWidget(QLabel("Y축:"), 9, 0)
        self.svm_y_ComboBox = QComboBox()
        for col in svm.enum_csv_col:
            self.svm_y_ComboBox.addItem(self._SVM_COL_LABEL_MAP.get(col, col.name), userData=col)
        self.svm_y_ComboBox.setCurrentIndex(list(svm.enum_csv_col).index(svm.enum_csv_col.LOW_RATIO))
        self.svm_collect_GridLayout.addWidget(self.svm_y_ComboBox, 9, 1)

        self.svm_collect_GridLayout.addWidget(QLabel("X축:"), 10, 0)
        self.svm_x_ComboBox = QComboBox()
        for col in svm.enum_csv_col:
            self.svm_x_ComboBox.addItem(self._SVM_COL_LABEL_MAP.get(col, col.name), userData=col)
        self.svm_x_ComboBox.setCurrentIndex(list(svm.enum_csv_col).index(svm.enum_csv_col.SPECTRAL_FLATNESS))
        self.svm_collect_GridLayout.addWidget(self.svm_x_ComboBox, 10, 1)

        self.svm_x_ComboBox.currentIndexChanged.connect(self.on_svm_axis_changed)
        self.svm_y_ComboBox.currentIndexChanged.connect(self.on_svm_axis_changed)
        self._refresh_axis_combos()  # 초기 특징 선택과 동기화

        # 점 표시 토글 버튼
        _TOGGLE_STYLE3 = (
            "QPushButton { font-weight: bold; border: 1px solid gray; border-radius: 4px; padding: 3px; }"
            "QPushButton:checked { background-color: #5a3a00; color: #ffcc44; border: 1px solid #886600; }"
        )
        _TOGGLE_STYLE4 = (
            "QPushButton { font-weight: bold; border: 1px solid gray; border-radius: 4px; padding: 3px; }"
            "QPushButton:checked { background-color: #0a4a20; color: #44ee80; border: 1px solid #116633; }"
        )
        self.svm_show_bg_ToggleButton = QPushButton("화면: 배경 표시")
        self.svm_show_bg_ToggleButton.setCheckable(True)
        self.svm_show_bg_ToggleButton.setChecked(True)
        self.svm_show_bg_ToggleButton.setStyleSheet(_TOGGLE_STYLE3)
        self.svm_show_bg_ToggleButton.toggled.connect(lambda checked: self._set_svm_point_visible(cfg.SVM_BACKGROUND_POINT_NAME, checked))
        self.svm_collect_GridLayout.addWidget(self.svm_show_bg_ToggleButton, 11, 0)

        self.svm_show_occu_ToggleButton = QPushButton("화면: 사람 표시")
        self.svm_show_occu_ToggleButton.setCheckable(True)
        self.svm_show_occu_ToggleButton.setChecked(True)
        self.svm_show_occu_ToggleButton.setStyleSheet(_TOGGLE_STYLE4)
        self.svm_show_occu_ToggleButton.toggled.connect(lambda checked: self._set_svm_point_visible(cfg.SVM_OCCUPANCY_POINT_NAME, checked))
        self.svm_collect_GridLayout.addWidget(self.svm_show_occu_ToggleButton, 11, 1)

############################################################################################################ SVM

############################################################################################################ LED & 타이머 설정
        self.led_setting_GroupBox = QGroupBox("iSENSOR ESP Control")
        self.led_setting_GroupBox.setStyleSheet("" + MACRO_BORDER_RADIUS.format(6))
        self.led_setting_GridLayout = QGridLayout()
        self.led_setting_GroupBox.setLayout(self.led_setting_GridLayout)
        self.left_GridLayout.addWidget(self.led_setting_GroupBox, 1, 1, 3, 1)   # Row1-3 Col1 - ESP Control

        # ---- 헬퍼: 라벨 + SpinBox 행 생성 (전송 버튼 없음 — 일괄 전송 버튼 사용) ----
        # 열 비율: [라벨 고정 | SpinBox 확장 | (예약)] 1열
        self.led_setting_GridLayout.setColumnStretch(0, 0)
        self.led_setting_GridLayout.setColumnStretch(1, 1)
        self.led_setting_GridLayout.setColumnStretch(2, 0)

        # --- TP 항목 편입 (row 0~2) ---
        self.led_setting_GridLayout.addWidget(self.tp1_Label, 0, 0)
        _tp1_h = QHBoxLayout()
        _tp1_h.setContentsMargins(0, 0, 0, 0); _tp1_h.setSpacing(2)
        _tp1_h.addWidget(self.tp1_SpinBox); _tp1_h.addWidget(self.tp1_up_btn); _tp1_h.addWidget(self.tp1_down_btn)
        self.led_setting_GridLayout.addLayout(_tp1_h, 0, 1, 1, 2)

        self.led_setting_GridLayout.addWidget(self.tp1_rck_Label, 1, 0)
        _tp1rck_h = QHBoxLayout()
        _tp1rck_h.setContentsMargins(0, 0, 0, 0); _tp1rck_h.setSpacing(2)
        _tp1rck_h.addWidget(self.tp1_rck_SpinBox); _tp1rck_h.addWidget(self.tp1_rkc_up_btn); _tp1rck_h.addWidget(self.tp1_rkc_down_btn)
        self.led_setting_GridLayout.addLayout(_tp1rck_h, 1, 1, 1, 2)

        self.led_setting_GridLayout.addWidget(self.tp2_Label, 2, 0)
        _tp2_h = QHBoxLayout()
        _tp2_h.setContentsMargins(0, 0, 0, 0); _tp2_h.setSpacing(2)
        _tp2_h.addWidget(self.tp2_SpinBox); _tp2_h.addWidget(self.tp2_up_btn); _tp2_h.addWidget(self.tp2_down_btn)
        self.led_setting_GridLayout.addLayout(_tp2_h, 2, 1, 1, 2)

        def _mk_spin(mn, mx, default):
            sb = QSpinBox()
            sb.setMinimum(mn); sb.setMaximum(mx); sb.setValue(default)
            sb.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            return sb

        def _mk_btn(label):
            b = QPushButton(label)
            b.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
            return b

        # ---- 헬퍼: ▲▼ 버튼 쌍 생성 (FFT Setting과 동일한 스타일) ----
        def _mk_arrow_pair(spinbox):
            up_btn   = QPushButton("▲")
            down_btn = QPushButton("▼")
            for b in (up_btn, down_btn):
                b.setFixedWidth(28)
                b.setFocusPolicy(PyQt6.QtCore.Qt.FocusPolicy.NoFocus)
                b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
            up_btn.clicked.connect(spinbox.stepUp)
            down_btn.clicked.connect(spinbox.stepDown)
            return up_btn, down_btn

        # ---- 헬퍼: 라벨 + SpinBox + ▲▼ 행 생성 ----
        def _ctrl_row(row, label_txt, spinbox):
            lbl = QLabel(label_txt)
            lbl.setStyleSheet("" + MACRO_FONT_BOLD + MACRO_BORDER_STYLE.format('none'))
            lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
            self.led_setting_GridLayout.addWidget(lbl, row, 0)
            up_btn, down_btn = _mk_arrow_pair(spinbox)
            h = QHBoxLayout()
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(2)
            h.addWidget(spinbox); h.addWidget(up_btn); h.addWidget(down_btn)
            self.led_setting_GridLayout.addLayout(h, row, 1, 1, 2)

        # LED Max / Min / Dim %  (row 3~5)
        self.led_max_SpinBox = _mk_spin(0, 100, 100)
        _ctrl_row(3, "LED Max (%):", self.led_max_SpinBox)

        self.led_min_SpinBox = _mk_spin(0, 100, 10)
        _ctrl_row(4, "LED Min (%):", self.led_min_SpinBox)

        self.led_dim_SpinBox = _mk_spin(0, 100, 50)
        _ctrl_row(5, "LED Dim (%):", self.led_dim_SpinBox)

        # LED Work / Step / Delay ms  (row 6~8)
        self.led_work_ms_SpinBox = _mk_spin(0, 600000, 30000)
        _ctrl_row(6, "Work (ms):", self.led_work_ms_SpinBox)

        self.led_step_ms_SpinBox = _mk_spin(0, 60000, 10)
        _ctrl_row(7, "Step (ms):", self.led_step_ms_SpinBox)

        self.led_delay_ms_SpinBox = _mk_spin(0, 60000, 500)
        _ctrl_row(8, "Delay (ms):", self.led_delay_ms_SpinBox)

        # Occu Timeout (row 9) — 단위 선택 가능 (µs / ms / s)
        self.occu_timeout_s_SpinBox = _mk_spin(0, 2147483647, 5)
        self.occu_unit_ComboBox = QComboBox()
        self.occu_unit_ComboBox.addItems(["µs", "ms", "s"])
        self.occu_unit_ComboBox.setCurrentText("s")
        self.occu_unit_ComboBox.setFixedWidth(48)
        self.occu_unit_ComboBox.currentTextChanged.connect(
            lambda u: self._on_time_unit_changed(self.occu_timeout_s_SpinBox, u))
        self._on_time_unit_changed(self.occu_timeout_s_SpinBox, "s")
        _occu_up, _occu_down = _mk_arrow_pair(self.occu_timeout_s_SpinBox)
        _occu_lbl = QLabel("Occu T/O:")
        _occu_lbl.setStyleSheet("" + MACRO_FONT_BOLD + MACRO_BORDER_STYLE.format('none'))
        _occu_lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.led_setting_GridLayout.addWidget(_occu_lbl, 9, 0)
        _occu_h = QHBoxLayout()
        _occu_h.setContentsMargins(0, 0, 0, 0)
        _occu_h.setSpacing(2)
        _occu_h.addWidget(self.occu_timeout_s_SpinBox)
        _occu_h.addWidget(self.occu_unit_ComboBox)
        _occu_h.addWidget(_occu_up); _occu_h.addWidget(_occu_down)
        self.led_setting_GridLayout.addLayout(_occu_h, 9, 1, 1, 2)

        # Sleep Time (row 10) — 단위 선택 가능 (µs / ms / s)
        self.sleep_time_s_SpinBox = _mk_spin(0, 2147483647, 10)
        self.sleep_unit_ComboBox = QComboBox()
        self.sleep_unit_ComboBox.addItems(["µs", "ms", "s"])
        self.sleep_unit_ComboBox.setCurrentText("s")
        self.sleep_unit_ComboBox.setFixedWidth(48)
        self.sleep_unit_ComboBox.currentTextChanged.connect(
            lambda u: self._on_time_unit_changed(self.sleep_time_s_SpinBox, u))
        self._on_time_unit_changed(self.sleep_time_s_SpinBox, "s")
        _sleep_up, _sleep_down = _mk_arrow_pair(self.sleep_time_s_SpinBox)
        _sleep_lbl = QLabel("Sleep:")
        _sleep_lbl.setStyleSheet("" + MACRO_FONT_BOLD + MACRO_BORDER_STYLE.format('none'))
        _sleep_lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.led_setting_GridLayout.addWidget(_sleep_lbl, 10, 0)
        _sleep_h = QHBoxLayout()
        _sleep_h.setContentsMargins(0, 0, 0, 0)
        _sleep_h.setSpacing(2)
        _sleep_h.addWidget(self.sleep_time_s_SpinBox)
        _sleep_h.addWidget(self.sleep_unit_ComboBox)
        _sleep_h.addWidget(_sleep_up); _sleep_h.addWidget(_sleep_down)
        self.led_setting_GridLayout.addLayout(_sleep_h, 10, 1, 1, 2)

        # 일괄 전송 버튼 (row 11) — TP + 모든 LED/타이머 설정 한 번에 전송
        self.all_settings_send_PushButton = _mk_btn("📡 전체 설정 전송하기")
        self.all_settings_send_PushButton.setStyleSheet("" + MACRO_FONT_BOLD + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.all_settings_send_PushButton.clicked.connect(self.event_send_all_settings_command)
        self.led_setting_GridLayout.addWidget(self.all_settings_send_PushButton, 11, 0, 1, 3)

        # LED ON/OFF 토글 버튼 (row 12) — 독립 유지
        self.led_onoff_ToggleButton = QPushButton("💡 LED ON")
        self.led_onoff_ToggleButton.setCheckable(True)
        self.led_onoff_ToggleButton.setChecked(True)
        self.led_onoff_ToggleButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.led_onoff_ToggleButton.toggled.connect(self.event_send_led_onoff_command)
        self.led_setting_GridLayout.addWidget(self.led_onoff_ToggleButton, 12, 0, 1, 3)

        # 설정 새로고침 버튼 (row 13)
        self.settings_reload_PushButton = QPushButton("🔄 설정 새로고침")
        self.settings_reload_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.settings_reload_PushButton.clicked.connect(self._event_settings_reload)
        self.led_setting_GridLayout.addWidget(self.settings_reload_PushButton, 13, 0, 1, 3)

############################################################################################################ LED & 타이머 설정

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

############################################################################################################ SVM
        # ############################# COPILOT EDIT START (Phase 2: SVM 산점도 탭)
        # --- SVM + MLP 세로 컨테이너 (main_HBoxLayout의 하나의 컬럼) ---
        self.svm_mlp_Widget = QWidget()
        self.svm_mlp_VBoxLayout = QVBoxLayout()
        self.svm_mlp_VBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.svm_mlp_VBoxLayout.setSpacing(4)
        self.svm_mlp_Widget.setLayout(self.svm_mlp_VBoxLayout)
        self.main_HBoxLayout.addWidget(self.svm_mlp_Widget, stretch=2)

        # --- SVM Plots 그룹 (위) ---
        self.svm_graph_GroupBox = QGroupBox("SVM Plots")
        self.svm_graph_GroupBox.setStyleSheet("" + MACRO_PADDING.format(10))
        self.svm_mlp_VBoxLayout.addWidget(self.svm_graph_GroupBox, stretch=1)
        self.svm_graph_VBoxLayout = QVBoxLayout()
        self.svm_graph_GroupBox.setLayout(self.svm_graph_VBoxLayout)
        self.svm_plot_TabWidget = QTabWidget()
        self.svm_plot_TabWidget.setStyleSheet("" + MACRO_BORDER_STYLE.format('none') + MACRO_PADDING.format(0))
        self.svm_plot_TabWidget.setMovable(True)
        self.svm_graph_VBoxLayout.addWidget(self.svm_plot_TabWidget)

        self.create_svm_plot_tab(self.A_graph_plot_value[enum_graph_plot_num.SVM][enum_graph_plot_range_opt.SVM])
        self.create_svm_pca_tab()

        # --- MLP Plots 그룹 (아래) ---
        self.mlp_graph_GroupBox = QGroupBox("MLP Plots")
        self.mlp_graph_GroupBox.setStyleSheet("" + MACRO_PADDING.format(10))
        self.svm_mlp_VBoxLayout.addWidget(self.mlp_graph_GroupBox, stretch=1)
        self.mlp_graph_VBoxLayout = QVBoxLayout()
        self.mlp_graph_GroupBox.setLayout(self.mlp_graph_VBoxLayout)
        self.mlp_plot_TabWidget = QTabWidget()
        self.mlp_plot_TabWidget.setStyleSheet("" + MACRO_BORDER_STYLE.format('none') + MACRO_PADDING.format(0))
        self.mlp_plot_TabWidget.setMovable(True)
        self.mlp_graph_VBoxLayout.addWidget(self.mlp_plot_TabWidget)

        self.create_mlp_prob_tab()
        self.create_mlp_history_tab()

        # self.svm_scatter_PlotWidget = pyqtgraph.PlotWidget()
        # self.svm_scatter_PlotWidget.setTitle("SVM Feature Space")
        # self.svm_scatter_PlotWidget.setLabel('bottom', 'Peak Freq (Hz)', **{'font-size': '12pt'})
        # self.svm_scatter_PlotWidget.setLabel('left',   'Peak Mag',       **{'font-size': '12pt'})
        # self.svm_scatter_PlotWidget.addLegend(offset=(10, 10))
        # self.svm_scatter_PlotWidget.setMouseEnabled(x=True, y=True)
        # 실시간 점 (예측 위치)
        # self.svm_realtime_scatter = pyqtgraph.ScatterPlotItem(
        #     size=14, pen=pyqtgraph.mkPen('w', width=2),
        #     brush=pyqtgraph.mkBrush(255, 255, 0, 200),
        #     symbol='star', name='현재'
        # )
        # self.svm_scatter_PlotWidget.addItem(self.svm_realtime_scatter)
        # self.svm_plot_TabWidget.addTab(self.svm_scatter_PlotWidget, "SVM 산점도")

        # ############################# COPILOT EDIT END
        # # ############################# COPILOT EDIT START (Phase 3: 분류 히스토리 탭)
        # self.svm_history_PlotWidget = pyqtgraph.PlotWidget()
        # self.svm_history_PlotWidget.setTitle("분류 히스토리  (빨강=사람  /  초록=배경)", color='w', size='12pt')
        # self.svm_history_PlotWidget.hideAxis('left')
        # self.svm_history_PlotWidget.getAxis('bottom').setLabel('← 오래된  |  최근 →')
        # self.svm_history_PlotWidget.setMouseEnabled(x=False, y=False)
        # self.svm_history_PlotWidget.setMenuEnabled(False)
        # self.svm_history_img = pyqtgraph.ImageItem()
        # self.svm_history_PlotWidget.addItem(self.svm_history_img)
        # self.svm_history_PlotWidget.getViewBox().disableAutoRange()  # auto-range 가 setImage 후 범위 덧쓰는 것 방지
        # self.svm_plot_TabWidget.addTab(self.svm_history_PlotWidget, "분류 히스토리")
        # self._update_svm_history_display()  # 초기 회색 표시
        # # ############################# COPILOT EDIT END
        # # ############################# COPILOT EDIT START (Phase A+B: 파형 뷰 탭)
        # self.svm_waveform_PlotWidget = pyqtgraph.PlotWidget()
        # self.svm_waveform_PlotWidget.setTitle("파형 뷰  (현재=밝은선 / 저장=흐린선)", color='w', size='12pt')
        # self.svm_waveform_PlotWidget.setLabel('bottom', '시간 (sec)', **{'font-size': '12pt'})
        # self.svm_waveform_PlotWidget.setLabel('left',   'ADC 값',    **{'font-size': '12pt'})
        # self.svm_waveform_PlotWidget.setYRange(0, 4095, padding=0.05)
        # self.svm_waveform_PlotWidget.setMouseEnabled(x=True, y=True)
        # # 실시간 파형 라인 (SVM 결과에 따라 색 변경)
        # self.svm_realtime_waveform = self.svm_waveform_PlotWidget.plot(
        #     [], pen=pyqtgraph.mkPen('w', width=2), name='현재 프레임'
        # )
        # self.svm_plot_TabWidget.addTab(self.svm_waveform_PlotWidget, "파형 뷰")
        # # ############################# COPILOT EDIT END
    ############################################################################################################ SVM

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
            self.connect_status_Label.setText("🟢 Connected")
            self.tp_setting_PushButton.setEnabled(True)
            # PC -> Chip 명령 송신
            if self.uart_thread and self.uart_thread.serial_port:
                self.command_sender.set_serial(self.uart_thread.serial_port)
        else:
            self.port_connect_PushButton.setText("Connect")
            self.connect_status_Label.setText("🔴 Not connected")
            self.tp_setting_PushButton.setEnabled(True)
            self.command_sender.set_serial(None)
            self._settings_loaded = False  # 재연결 시 초기값 다시 수신

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

    def event_send_all_settings_command(self):
        """TP + LED + 타이머 설정 전체를 한 번에 ESP32에 전송"""
        failed = []

        # TP
        v = self.tp1_SpinBox.value()
        if self.command_sender.send_set_tp1(v):
            self.log_TextEdit.append(f"[TX] TP1: {v}")
        else:
            failed.append("TP1")

        v = self.tp1_rck_SpinBox.value()
        if self.command_sender.send_set_tp1_recheck(v):
            self.log_TextEdit.append(f"[TX] TP1 RCK: {v}")
        else:
            failed.append("TP1 RCK")

        v = self.tp2_SpinBox.value()
        if self.command_sender.send_set_tp2(v):
            self.log_TextEdit.append(f"[TX] TP2: {v}")
        else:
            failed.append("TP2")

        # LED %
        v = self.led_max_SpinBox.value()
        if self.command_sender.send_set_led_max_per(v):
            self.log_TextEdit.append(f"[TX] LED Max: {v}%")
        else:
            failed.append("LED Max")

        v = self.led_min_SpinBox.value()
        if self.command_sender.send_set_led_min_per(v):
            self.log_TextEdit.append(f"[TX] LED Min: {v}%")
        else:
            failed.append("LED Min")

        v = self.led_dim_SpinBox.value()
        if self.command_sender.send_set_led_dim_per(v):
            self.log_TextEdit.append(f"[TX] LED Dim: {v}%")
        else:
            failed.append("LED Dim")

        # 타이머 ms
        v = self.led_work_ms_SpinBox.value()
        if self.command_sender.send_set_led_work_ms(v):
            self.log_TextEdit.append(f"[TX] Work: {v} ms")
        else:
            failed.append("Work")

        v = self.led_step_ms_SpinBox.value()
        if self.command_sender.send_set_led_step_ms(v):
            self.log_TextEdit.append(f"[TX] Step: {v} ms")
        else:
            failed.append("Step")

        v = self.led_delay_ms_SpinBox.value()
        if self.command_sender.send_set_led_delay_ms(v):
            self.log_TextEdit.append(f"[TX] Delay: {v} ms")
        else:
            failed.append("Delay")

        # Occu / Sleep (단위 변환 포함)
        if not self._send_time_value_occu():
            failed.append("Occu T/O")

        if not self._send_time_value_sleep():
            failed.append("Sleep")

        if failed:
            QMessageBox.warning(self, "일부 전송 실패",
                                f"다음 항목 전송 실패:\n{', '.join(failed)}\n연결 상태를 확인하세요.")
        else:
            self.log_TextEdit.append("[TX] ✅ 전체 설정 전송 완료")

    def event_send_fft_stride_command(self):
        """FFT Stride 값을 ESP32에 전송 (CMD_SET_FFT_STRIDE = 0x13)"""
        i_stride = self.fft_stride_SpinBox.value()
        if self.command_sender.send_set_fft_stride(i_stride):
            self.log_TextEdit.append(f"[TX] FFT Stride 설정 명령 전송: {i_stride} smp = {i_stride * 10} ms")
        else:
            self.log_TextEdit.append("[TX] FFT Stride 전송 실패 - 연결 상태를 확인하세요")
            QMessageBox.warning(self, "전송 실패", "FFT Stride 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")

    def _send_led_setting(self, send_func, value, label: str):
        """LED/타이머 설정 공통 전송 헬퍼. value=None이면 send_func()를 직접 호출."""
        if value is None:
            result = send_func()
        else:
            result = send_func(value)
        if result:
            self.log_TextEdit.append(f"[TX] {label} 설정 전송: {value}")
        else:
            self.log_TextEdit.append(f"[TX] {label} 전송 실패 - 연결 상태를 확인하세요")
            QMessageBox.warning(self, "전송 실패", f"{label} 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")

    _TIME_UNIT_MULTIPLIER = {"µs": 1, "ms": 1_000, "s": 1_000_000}
    _TIME_UNIT_MAX        = {"µs": 2_147_483_647, "ms": 2_147_483_647, "s": 2_147_483_647}

    def _on_time_unit_changed(self, spinbox, unit: str):
        """단위 ComboBox 변경 시 SpinBox 최대값 조정"""
        spinbox.setMaximum(self._TIME_UNIT_MAX.get(unit, 2_147_483_647))

    def _send_time_value_occu(self) -> bool:
        """Occu Timeout 단위 변환 후 전송"""
        unit = self.occu_unit_ComboBox.currentText()
        val_us = self.occu_timeout_s_SpinBox.value() * self._TIME_UNIT_MULTIPLIER[unit]
        self.log_TextEdit.append(f"[TX] Occu Timeout 전송: {self.occu_timeout_s_SpinBox.value()} {unit} = {val_us} µs")
        return self.command_sender.send_set_occu_timeout_us(val_us)

    def _send_time_value_sleep(self) -> bool:
        """Sleep Time 단위 변환 후 전송"""
        unit = self.sleep_unit_ComboBox.currentText()
        val_us = self.sleep_time_s_SpinBox.value() * self._TIME_UNIT_MULTIPLIER[unit]
        self.log_TextEdit.append(f"[TX] Sleep Time 전송: {self.sleep_time_s_SpinBox.value()} {unit} = {val_us} µs")
        return self.command_sender.send_set_sleep_time_us(val_us)

    def _event_settings_reload(self):
        """설정 새로고침 버튼: 다음 Settings 수신 시 SpinBox를 1회 업데이트"""
        self._settings_loaded = False
        self.log_TextEdit.append("[설정] 다음 Settings 패킷 수신 시 SpinBox를 업데이트합니다.")

    def _on_fft_gain_changed(self, _value: float):
        """Gain SpinBox 변경 시 현재 FFT 데이터로 Magnitude 선 즉시 재갱신"""
        if len(self.A_fft_energies) == 0 or len(self.A_fft_frequencies) != len(self.A_fft_energies):
            return
        for tab_name in (ADC_FFT_FULL_SCALE_NAME, ADC_FFT_ZOOM_SCALE_NAME):
            widget = self.get_TabWidget(tab_name)
            if widget is None:
                continue
            lines = widget.getPlotItem().listDataItems()
            if len(lines) < 2:
                continue
            gain = self.fft_gain_SpinBox.value()
            y_mag = numpy.sqrt(numpy.maximum(self.A_fft_energies.astype(numpy.float64), 0)) * gain
            lines[1].setData(self.A_fft_frequencies, y_mag)

    def event_send_led_onoff_command(self, b_checked: bool):
        """LED ON/OFF 토글 전송 (CMD_SET_LED_ONOFF = 0x1C)"""
        self.led_onoff_ToggleButton.setText("💡 LED ON" if b_checked else "🔴 LED OFF")
        if self.command_sender.send_set_led_onoff(b_checked):
            self.log_TextEdit.append(f"[TX] LED {'ON' if b_checked else 'OFF'} 명령 전송")
        else:
            self.log_TextEdit.append("[TX] LED ON/OFF 전송 실패 - 연결 상태를 확인하세요")
            QMessageBox.warning(self, "전송 실패", "LED ON/OFF 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")


### 이벤트 ##########
############################################################################################################ SVM
    # ############################# COPILOT EDIT START (SVM 이벤트 핸들러)
    # def _get_last_fft_raw(self):
    #     """마지막 FFT raw magnitudes 반환 (게인 미적용)"""
    #     return getattr(self, '_last_fft_raw', None), getattr(self, '_last_fft_freqs', None)

    def event_svm_auto_bg_toggled(self, b_checked: bool):
        """배경 자동 저장 토글 상태 변경"""
        self.b_auto_save_bg = b_checked
        if b_checked:
            # 사람 자동 저장과 상호 배제
            if self.b_auto_save_human:
                self.svm_auto_human_ToggleButton.setChecked(False)
            self.i_fft_since_last_save = 0  # 즉시 첫 저장되도록 리셋
            self.svm_auto_bg_ToggleButton.setText("🟢 배경 자동 ON  [1]")
            self.log_TextEdit.append(f"[SVM] 배경 자동 저장 ON — FFT {self.i_auto_save_stride}회마다 배경으로 저장됩니다.")
        else:
            self.svm_auto_bg_ToggleButton.setText("🔴 배경 자동 OFF  [1]")
            self.log_TextEdit.append("[SVM] 배경 자동 저장 OFF")

    def event_svm_auto_human_toggled(self, b_checked: bool):
        """사람 자동 저장 토글 상태 변경"""
        self.b_auto_save_human = b_checked
        if b_checked:
            # 배경 자동 저장과 상호 배제
            if self.b_auto_save_bg:
                self.svm_auto_bg_ToggleButton.setChecked(False)
            self.i_fft_since_last_save = 0  # 즉시 첫 저장되도록 리셋
            self.svm_auto_human_ToggleButton.setText("🟢 사람 자동 ON  [2]")
            self.log_TextEdit.append(f"[SVM] 사람 자동 저장 ON — FFT {self.i_auto_save_stride}회마다 사람으로 저장됩니다.")
        else:
            self.svm_auto_human_ToggleButton.setText("🔴 사람 자동 OFF  [2]")
            self.log_TextEdit.append("[SVM] 사람 자동 저장 OFF")

    def event_svm_auto_save_interval_changed(self, i_value: int):
        """자동 저장 주기 변경 (FFT 갱신 횟수)"""
        self.i_auto_save_stride = int(i_value)

    def event_svm_save_background(self):
        """현재 FFT 결과를 배경(0) 레이블로 저장"""
        # A_mags_raw, A_freqs = self._get_last_fft_raw()

        # self.svm_handle.A_frequencies
        # self.svm_handle.A_magnitudes

        if not self.uart_thread or self.fft_features_data is None:
            ######################################################################## 경고 대화상자
            QMessageBox.warning(self, "배경 정보 저장 실패", "FFT 특징이 없습니다.\n 먼저 데이터를 수신하세요.")
            ######################################################################## 경고 대화상자
            return
        
        # A_feature = self.svm_handle.extract_features(A_mags_raw, A_freqs)
        # A_feature = self.svm_handle.extract_features()
        # self.svm_handle.save_sample(A_feature, svm.enum_label.LABEL_BACKGROUND, self.svm_handle.str_svm_csv_path)
        self.collector.save_sample(self.fft_features_data, svm.enum_label.LABEL_BACKGROUND)
        self.collector.flush_write_buffer()  # 수동 저장: 버퍼 대기 없이 즉시 기록

        # if self._last_adc_raw:
        #     self.svm_handle.save_waveform(self._last_adc_raw, svm.enum_label.LABEL_BACKGROUND, self.str_svm_waveform_csv_path)
        #     self.update_svm_waveform_overlay()

        self.update_svm_label_count()
        self.log_TextEdit.append("[SVM] 배경 샘플 저장 완료")

    def event_svm_save_occupancy(self):
        """현재 FFT 결과를 사람(1) 레이블로 저장"""
        # A_mags_raw, A_freqs = self._get_last_fft_raw()
        # if A_mags_raw is None:
        #     QMessageBox.warning(self, "저장 실패", "FFT 데이터가 없습니다.\n먼저 데이터를 수신하세요.")
        #     return
        # A_feature = self.svm_handle.extract_features(A_mags_raw, A_freqs)
        # self.svm_handle.save_sample(A_feature, svm.enum_label.LABEL_HUMAN, self.svm_handle.str_svm_csv_path)
        # if self._last_adc_raw:
        #     self.svm_handle.save_waveform(self._last_adc_raw, svm.enum_label.LABEL_HUMAN, self.str_svm_waveform_csv_path)
        #     self.update_svm_waveform_overlay()
        # self.update_svm_label_count()
        # self.log_TextEdit.append("[SVM] 사람 샘플 저장 완료")

        if not self.uart_thread or self.fft_features_data is None:
            ######################################################################## 경고 대화상자
            QMessageBox.warning(self, "재실 정보 저장 실패", "FFT 특징이 없습니다.\n 먼저 데이터를 수신하세요.")
            ######################################################################## 경고 대화상자
            return

        self.collector.save_sample(self.fft_features_data, svm.enum_label.LABEL_HUMAN)
        self.collector.flush_write_buffer()  # 수동 저장: 버퍼 대기 없이 즉시 기록

        self.update_svm_label_count()
        self.log_TextEdit.append("[SVM] 재실 샘플 저장 완료")

    def event_svm_feature_select(self):
        """특징 선택 다이얼로그 열기"""
        dlg = SvmFeatureDialog(self.svm_handle.A_feature_indices, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_indices = dlg.get_feature_indices()
        if new_indices == self.svm_handle.A_feature_indices:
            return  # 변경 없으면 아무것도 안 함

        self.svm_handle.A_feature_indices = new_indices
        self._refresh_axis_combos()  # 콤보박스를 새 특징 목록에 맞게 갱신

        # 특징 변경 시 기존 학습 모델 무효화
        self.svm_handle.b_is_trained = False
        self._svm_boundary_cache     = None
        self._svm_pca_boundary_cache = None
        self.svm_status_Label.setText("미학습 (특징 변경됨)")

        # 레이블 업데이트
        n = len(new_indices)
        total = svm.I_FEATURES_COUNT
        _I_RECOMMENDED = 24
        suffix = "(전체)" if n == total else "(권장 세트)" if n == _I_RECOMMENDED else ""
        self.svm_feature_count_Label.setText(f"선택된 특징: {n}개 {suffix}".strip())
        self.log_TextEdit.append(f"[SVM] 특징 {n}개 선택 — 재학습 필요")

    def event_svm_train(self):
        """CSV 데이터로 SVM 학습 (백그라운드 스레드)"""
        self.svm_train_PushButton.setEnabled(False)
        self.svm_status_Label.setText("학습 중...")

        self._svm_train_worker = SvmTrainWorker(self.svm_handle, os.path.dirname(self.collector.str_csv_path))
        self._svm_train_worker.finished.connect(self._on_svm_train_finished)
        self._svm_train_worker.start()

    def _on_svm_train_finished(self, b_train_done: bool):
        """학습 완료 후 UI 업데이트 (메인 스레드에서 실행)"""
        self.svm_train_PushButton.setEnabled(True)
        self._svm_boundary_cache     = None
        self._svm_pca_boundary_cache = None
        if b_train_done:
            self._rebuild_svm_2d()  # 2D 모델 학습
            self.svm_status_Label.setText(f"학습 완료  BG:{self.collector.i_bg_count} / Human:{self.collector.i_human_count}")
            self.log_TextEdit.append(f"[SVM] 학습 완료  BG:{self.collector.i_bg_count} / Human:{self.collector.i_human_count}")
        else:
            self.svm_status_Label.setText("학습 실패 - 데이터 부족")
            QMessageBox.warning(self, "학습 실패", "데이터가 부족합니다.\n10개 이상 수집하세요.")


    def event_svm_clear(self):
        """CSV 학습 데이터 삭제 + SVM 초기화"""

        if not os.path.exists(self.collector.str_csv_path):
            QMessageBox.warning(self, "학습 데이터 삭제 실패", f"'{self.collector.str_csv_path}' 파일이 존재하지 않습니다.")
            return

        ######################################################################## 물어보는 대화상자
        reply_QMessageBox = QMessageBox.question(
            self, "학습 데이터 삭제",
            f"'{self.collector.str_csv_path}' 파일을 삭제하고 SVM을 초기화합니다.\n계속할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        ######################################################################## 물어보는 대화상자
        if reply_QMessageBox == QMessageBox.StandardButton.No:
            return
        
        if os.path.exists(self.collector.str_csv_path):
            os.remove(self.collector.str_csv_path)
        # if os.path.exists(self.str_svm_waveform_csv_path):
        #     os.remove(self.str_svm_waveform_csv_path)
        self.svm_handle = svm.SVM_Module()  # 완전 초기화
        self.collector  = tdc.TrainingDataCollector()  # 카운터/버퍼 리셋
        self._svm_boundary_cache     = None
        self._svm_pca_boundary_cache = None
        self._svm_2d_model  = None
        self._svm_2d_scaler = None


        self.svm_status_Label.setText("미학습")
        self.svm_count_Label.setText("BackGround : 0  |  Occupancy : 0")

        self.log_TextEdit.append("[SVM] 학습 데이터 삭제 및 초기화 완료")


        # # 산점도 초기화
        # for item in self.svm_scatter_PlotWidget.listDataItems():
        #     if item is not self.svm_realtime_scatter:
        #         self.svm_scatter_PlotWidget.removeItem(item)
        # self.svm_realtime_scatter.setData([], [])

        # # Phase 3: 히스토리 초기화
        # self._svm_history.clear()
        # self._update_svm_history_display()
        # # 파형 오버레이 초기화
        # for item in self._svm_waveform_overlay_items:
        #     self.svm_waveform_PlotWidget.removeItem(item)
        # self._svm_waveform_overlay_items.clear()
        # self.svm_realtime_waveform.setData([], [])
        # self.svm_realtime_waveform.setPen(pyqtgraph.mkPen('w', width=2))

        # i_get_tp2 = self.tp2_SpinBox.value()    
        # if self.command_sender.send_set_tp2(i_get_tp2):
        #     self.log_TextEdit.append(f"[TX] TP2 설정 명령 전송: {i_get_tp2}")
        # else:
        #     self.log_TextEdit.append("[TX] TP2 전송 실패 - 연결 상태를 확인하세요")
        #     QMessageBox.warning(self, "전송 실패", "TP2 명령 전송에 실패했습니다.\n연결 상태를 확인하세요.")

#     # ############################# COPILOT EDIT START (Phase A+B: update_svm_waveform_overlay)
#     def update_svm_waveform_overlay(self):
#         """저장된 파형 CSV를 읽어 오버레이 그래프 갱신
#         초록 선 = 배경(LABEL_BACKGROUND), 빨강 선 = 사람(LABEL_HUMAN)
#         """
#         # 기존 오버레이 제거
#         for item in self._svm_waveform_overlay_items:
#             self.svm_waveform_PlotWidget.removeItem(item)
#         self._svm_waveform_overlay_items.clear()

#         A_waveforms = self.svm_handle.load_waveforms(self.str_svm_waveform_csv_path)
#         for A_raw, i_label in A_waveforms:
#             x_wave = numpy.arange(len(A_raw)) / 100.0  # 시간축 (초)
#             if i_label == svm.enum_label.LABEL_HUMAN:
#                 pen = pyqtgraph.mkPen((220, 0, 0, 70), width=1)
#             else:
#                 pen = pyqtgraph.mkPen((0, 180, 0, 70), width=1)
#             item = self.svm_waveform_PlotWidget.plot(x_wave, A_raw, pen=pen)
#             self._svm_waveform_overlay_items.append(item)

#         # 실시간 라인을 맨 위 z-order로 유지
#         self.svm_waveform_PlotWidget.removeItem(self.svm_realtime_waveform)
#         self.svm_waveform_PlotWidget.addItem(self.svm_realtime_waveform)
#     # ############################# COPILOT EDIT END

#     # ############################# COPILOT EDIT START (Phase 3: _update_svm_history_display)
#     def _update_svm_history_display(self):
#         """분류 히스토리 ImageItem 갱신 (최신값이 오른쪽 끝)"""
#         _BAR_H = 40  # y축 높이 (픽셀 두께 확보 - 1픽셀은 렌더링 시 사라질 수 있음)
#         # shape: (maxlen, BAR_H, 3) → pyqtgraph image[x, y, ch]
#         img = numpy.full((self._SVM_HISTORY_MAXLEN, _BAR_H, 3), 40, dtype=numpy.uint8)
#         i_history_len = len(self._svm_history)
#         i_offset = self._SVM_HISTORY_MAXLEN - i_history_len  # 최신이 오른쪽 끝에 오도록
#         for i, i_label in enumerate(self._svm_history):
#             pos = i_offset + i
#             if i_label == svm.enum_label.LABEL_HUMAN:
#                 img[pos, :, :] = [220, 0, 0]    # 빨강 = 사람 (전체 높이 칠하기)
#             else:
#                 img[pos, :, :] = [0, 180, 0]    # 초록 = 배경 (전체 높이 칠하기)
#         # levels=(0,255) 명시: autoLevels=False일 때 단색 이미지에서 levels=(40,40) 오류 방지
#         self.svm_history_img.setImage(img, autoLevels=False, levels=(0, 255))
#         # setImage 후 범위 재적용 (setImage 호출 시 ViewBox 범위가 리셋될 수 있음)
#         self.svm_history_PlotWidget.setXRange(0, self._SVM_HISTORY_MAXLEN, padding=0.02)
#         self.svm_history_PlotWidget.setYRange(0, _BAR_H, padding=0.0)
#         # 타이틀에 감지율 표시
#         if i_history_len > 0:
#             i_human_cnt = sum(1 for x in self._svm_history if x == svm.enum_label.LABEL_HUMAN)
#             f_rate = i_human_cnt / i_history_len * 100
#             self.svm_history_PlotWidget.setTitle(
#                 f"분류 히스토리  |  감지율: {f_rate:.1f}%  ({i_human_cnt}/{i_history_len}회)  "
#                 f"(빨강=사람 / 초록=배경)",
#                 color='w', size='12pt'
#             )
#         else:
#             self.svm_history_PlotWidget.setTitle(
#                 "분류 히스토리  (빨강=사람  /  초록=배경)",
#                 color='w', size='12pt'
#             )
#     # ############################# COPILOT EDIT END
# ############################################################################################################ SVM

    def get_adc_buffer_info(self, inter_A_buffer:list):
        """0이 아닌 값들에 대한 통계 계산"""
        i_buffer_len = len(inter_A_buffer)
        i_buffer_min = numpy.min(inter_A_buffer)
        i_buffer_mid = numpy.median(inter_A_buffer)
        i_buffer_max = numpy.max(inter_A_buffer)
        # f_buffer_avg = sum(inter_A_buffer) / i_buffer_len
        f_buffer_avg = numpy.mean(inter_A_buffer)
        f_buffer_std = numpy.std(inter_A_buffer)
        


        A_exclusion_zero_buffer = [x for x in inter_A_buffer if x != 0]
        if not A_exclusion_zero_buffer:
            return (
                i_buffer_len
                , i_buffer_min
                , i_buffer_mid
                , i_buffer_max
                , f_buffer_avg
                , f_buffer_std
                , []     # A_exclusion_zero_buffer
                , 0      # i_exclusion_zero_buffer_len
                , 0      # i_exclusion_zero_buffer_min
                , 0      # i_exclusion_zero_buffer_mid
                , 0      # i_exclusion_zero_buffer_max
                , 0.0    # f_exclusion_zero_buffer_avg
                , 0.0    # f_exclusion_zero_buffer_std
            )
        
        i_exclusion_zero_buffer_len = len(A_exclusion_zero_buffer)
        i_exclusion_zero_buffer_min = numpy.min(A_exclusion_zero_buffer)
        i_exclusion_zero_buffer_mid = numpy.median(A_exclusion_zero_buffer)
        i_exclusion_zero_buffer_max = numpy.max(A_exclusion_zero_buffer)
        # f_exclusion_zero_buffer_avg = sum(A_exclusion_zero_buffer) / i_exclusion_zero_buffer_len
        f_exclusion_zero_buffer_avg = numpy.mean(A_exclusion_zero_buffer)
        f_exclusion_zero_buffer_std = numpy.std(A_exclusion_zero_buffer)
        

        return (
            i_buffer_len
            , i_buffer_min
            , i_buffer_mid
            , i_buffer_max
            , f_buffer_avg
            , f_buffer_std
            , A_exclusion_zero_buffer
            , i_exclusion_zero_buffer_len
            , i_exclusion_zero_buffer_min
            , i_exclusion_zero_buffer_mid
            , i_exclusion_zero_buffer_max
            , f_exclusion_zero_buffer_avg
            , f_exclusion_zero_buffer_std
            )

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


#############################################################
        # 'o'	원 (circle)
        # 's'	사각형 (square)
        # 't'	삼각형 위 (triangle up)
        # 't1'	삼각형 위 (triangle up, alias)
        # 't2'	삼각형 오른쪽
        # 't3'	삼각형 왼쪽
        # 'd'	다이아몬드 (diamond)
        # '+'	플러스
        # 'x'	X자
        # 'p'	오각형 (pentagon)
        # 'h'	육각형 (hexagon)
        # 'star'	별 (star)
        # 'arrow_up'	화살표 위
        # 'arrow_right'	화살표 오른쪽
        # 'arrow_down'	화살표 아래
        # 'arrow_left'	화살표 왼쪽
        # 'crosshair'	크로스헤어
    def create_scatter(self, target_PlotWidget, s_inter_name, s_color_code):
        point_ScatterPlotItem = pyqtgraph.ScatterPlotItem(
            pen=None,
            brush=pyqtgraph.mkBrush(s_color_code),
            size=7,
            symbol='o'
        )
        point_ScatterPlotItem.role = s_inter_name
        target_PlotWidget.addItem(point_ScatterPlotItem, ignoreBounds=True)
        # target_PlotWidget.addItem(point_ScatterPlotItem)

        return point_ScatterPlotItem
    
    def create_svm_now_scatter(self, target_PlotWidget, s_inter_name, s_color_code):
        point_ScatterPlotItem = pyqtgraph.ScatterPlotItem(
            pen=pyqtgraph.mkPen('w', width=2),
            brush=pyqtgraph.mkBrush(s_color_code),
            size=32,
            symbol='star'
        )
        point_ScatterPlotItem.role = s_inter_name
        point_ScatterPlotItem.setZValue(10)  # 다른 모든 아이템 위에 표시
        # target_PlotWidget.addItem(point_ScatterPlotItem, ignoreBounds=True)
        target_PlotWidget.addItem(point_ScatterPlotItem)

        return point_ScatterPlotItem

    def create_svm_bg_scatter(self, target_PlotWidget, s_inter_name, s_color_code):
        point_ScatterPlotItem = pyqtgraph.ScatterPlotItem(
            pen=pyqtgraph.mkPen('w', width=2),
            brush=pyqtgraph.mkBrush(s_color_code),
            size=14,
            symbol='x'
        )
        point_ScatterPlotItem.role = s_inter_name
        # target_PlotWidget.addItem(point_ScatterPlotItem, ignoreBounds=True)
        target_PlotWidget.addItem(point_ScatterPlotItem)

        return point_ScatterPlotItem
    
    def create_svm_occu_scatter(self, target_PlotWidget, s_inter_name, s_color_code):
        point_ScatterPlotItem = pyqtgraph.ScatterPlotItem(
            pen=pyqtgraph.mkPen('w', width=2),
            brush=pyqtgraph.mkBrush(s_color_code),
            size=14,
            symbol='o'
        )
        point_ScatterPlotItem.role = s_inter_name
        # target_PlotWidget.addItem(point_ScatterPlotItem, ignoreBounds=True)
        target_PlotWidget.addItem(point_ScatterPlotItem)
        return point_ScatterPlotItem

    def create_adc_plot_tab(self, graph_plot_value:list):

        target_PlotWidget = pyqtgraph.PlotWidget(axisItems={'left': IntAxisItem(orientation='left')})
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
        self.create_label(target_PlotWidget, cfg.ADC_LABEL_NAME, cfg.ADC_LABEL_ANCHOR_X, cfg.ADC_LABEL_ANCHOR_Y, cfg.ADC_LABEL_COLOR)

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
        target_PlotWidget.getAxis('left').enableAutoSIPrefix(False)   # ×0.001 같은 SI 배율 표기 비활성화 → 소수점 직접 표시

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

        # 두 번째 선: Magnitude (sqrt(energy) × Gain) — PC 계산, 오렌지색 실선
        target_PlotWidget.plot(
            pen=pyqtgraph.mkPen(color='#ff8800', width=1,
                                style=pyqtgraph.QtCore.Qt.PenStyle.SolidLine),
            name='Mag × Gain'
        )

        # # 피크 주파수 표시용 텍스트 아이템
        # peak_TextItem = pyqtgraph.TextItem(anchor=(0, 1), color='y')
        # target_PlotWidget.addItem(peak_TextItem)

        self.create_label(target_PlotWidget, cfg.FFT_LABEL_NAME, cfg.FFT_LABEL_ANCHOR_X, cfg.FFT_LABEL_ANCHOR_Y, cfg.FFT_LABEL_COLOR)

        # tp1_recheck_lines[graph_tab_name] = self.tp1_rck_InfiniteLine
        self.adc_fft_plot_TabWidget.addTab(target_PlotWidget, graph_plot_value[enum_graph_plot_index.STR_PLOT_NAME])

        # # 피크 라벨 저장용 딕셔너리
        # if not hasattr(self, 'fft_peak_labels'):
        #     self.fft_peak_labels = {}
        # self.fft_peak_labels[graph_tab_name] = peak_label


    def create_svm_plot_tab(self, graph_plot_value:list):

        target_PlotWidget = pyqtgraph.PlotWidget()
        # SVM 그래프는 데이터에 따라 범위가 달라지므로 마우스 조작 허용
        target_PlotWidget.setMouseEnabled(x=True, y=True)
        target_PlotWidget.setMenuEnabled(False)
    
        target_PlotWidget.setTitle(f"{graph_plot_value[enum_graph_plot_index.STR_PLOT_NAME]}")
        target_PlotWidget.setLabel(f"{graph_plot_value[enum_graph_plot_index.STR_GRAPH_X_LABEL_POS]}", f"{graph_plot_value[enum_graph_plot_index.STR_GRAPH_X_LABEL]}", **{'font-size': '14pt'})
        target_PlotWidget.setLabel(f"{graph_plot_value[enum_graph_plot_index.STR_GRAPH_Y_LABEL_POS]}", graph_plot_value[enum_graph_plot_index.STR_GRAPH_Y_LABEL], **{'font-size': '14pt'})
        # 고정 범위/하한 제거 → enableAutoRange()로 대신 처리

        # 결정 경계 배경 이미지 (스캐터 점 뒤에 배치)
        boundary_ImageItem = pyqtgraph.ImageItem()
        boundary_ImageItem.role = cfg.SVM_BOUNDARY_IMAGE_NAME
        boundary_ImageItem.setZValue(-10)  # 스캐터 점보다 뒤에 배치
        target_PlotWidget.addItem(boundary_ImageItem, ignoreBounds=True)

        self.create_svm_now_scatter(target_PlotWidget, cfg.SVM_NOW_POINT_NAME, cfg.SVM_NOW_POINT_COLOR)

        self.create_svm_bg_scatter(target_PlotWidget, cfg.SVM_BACKGROUND_POINT_NAME, cfg.SVM_BACKGROUND_POINT_COLOR)
        self.create_svm_occu_scatter(target_PlotWidget, cfg.SVM_OCCUPANCY_POINT_NAME, cfg.SVM_OCCUPANCY_POINT_COLOR)

        # # 피크 주파수 표시용 텍스트 아이템
        # peak_TextItem = pyqtgraph.TextItem(anchor=(0, 1), color='y')
        # target_PlotWidget.addItem(peak_TextItem)

        self.create_label(target_PlotWidget, cfg.SVM_LABEL_NAME, cfg.SVM_LABEL_ANCHOR_X, cfg.SVM_LABEL_ANCHOR_Y, cfg.SVM_LABEL_COLOR)

        # 사용자가 마우스로 zoom/pan 하면 자동 범위 조정 비활성화
        target_PlotWidget.getPlotItem().getViewBox().sigRangeChangedManually.connect(
            lambda: setattr(self, '_b_svm_user_zoomed', True)
        )
        # 더블클릭 시 zoom 초기화
        target_PlotWidget.scene().sigMouseClicked.connect(
            lambda e: (setattr(self, '_b_svm_user_zoomed', False), target_PlotWidget.enableAutoRange())
            if e.double() else None
        )

        self.svm_plot_TabWidget.addTab(target_PlotWidget, graph_plot_value[enum_graph_plot_index.STR_PLOT_NAME])

        # # 피크 라벨 저장용 딕셔너리
        # if not hasattr(self, 'fft_peak_labels'):
        #     self.fft_peak_labels = {}
        # self.fft_peak_labels[graph_tab_name] = peak_label

    def create_svm_pca_tab(self):
        """PCA 2D 투영 탭 생성 — SVM 결정 경계를 PC1/PC2 축으로 시각화"""
        target_PlotWidget = pyqtgraph.PlotWidget()
        target_PlotWidget.setMouseEnabled(x=True, y=True)
        target_PlotWidget.setMenuEnabled(False)
        target_PlotWidget.setTitle(cfg.SVM_PCA_NAME)
        target_PlotWidget.setLabel('bottom', 'PC1', **{'font-size': '14pt'})
        target_PlotWidget.setLabel('left',   'PC2', **{'font-size': '14pt'})

        # 결정 경계 배경 이미지 (스캐터 점 뒤에 배치)
        boundary_ImageItem = pyqtgraph.ImageItem()
        boundary_ImageItem.role = cfg.SVM_PCA_BOUNDARY_IMAGE_NAME
        boundary_ImageItem.setZValue(-10)
        target_PlotWidget.addItem(boundary_ImageItem, ignoreBounds=True)

        self.create_svm_now_scatter(target_PlotWidget, cfg.SVM_PCA_NOW_POINT_NAME,  cfg.SVM_PCA_NOW_POINT_COLOR)
        self.create_svm_bg_scatter(target_PlotWidget, cfg.SVM_PCA_BG_POINT_NAME,   cfg.SVM_PCA_BG_POINT_COLOR)
        self.create_svm_occu_scatter(target_PlotWidget, cfg.SVM_PCA_OCCU_POINT_NAME, cfg.SVM_PCA_OCCU_POINT_COLOR)

        self.create_label(target_PlotWidget, cfg.SVM_PCA_LABEL_NAME,
                          cfg.SVM_LABEL_ANCHOR_X, cfg.SVM_LABEL_ANCHOR_Y, cfg.SVM_LABEL_COLOR)

        # 사용자가 마우스로 zoom/pan 하면 자동 범위 조정 비활성화
        target_PlotWidget.getPlotItem().getViewBox().sigRangeChangedManually.connect(
            lambda: setattr(self, '_b_svm_pca_user_zoomed', True)
        )
        # 더블클릭 시 zoom 초기화
        target_PlotWidget.scene().sigMouseClicked.connect(
            lambda e: (setattr(self, '_b_svm_pca_user_zoomed', False), target_PlotWidget.enableAutoRange())
            if e.double() else None
        )

        self.svm_plot_TabWidget.addTab(target_PlotWidget, cfg.SVM_PCA_NAME)

    def create_mlp_prob_tab(self):
        """MLP 실시간 확률 막대 탭 — 배경/사람 확률을 BarGraph로 표시"""
        pw = pyqtgraph.PlotWidget()
        pw.setTitle("MLP 실시간 확률", color='w', size='12pt')
        pw.setLabel('left', '확률', **{'font-size': '12pt'})
        pw.setYRange(0, 1.05, padding=0)
        pw.setXRange(-0.6, 1.6, padding=0)
        pw.setMouseEnabled(x=False, y=False)
        pw.setMenuEnabled(False)
        pw.showGrid(y=True, alpha=0.3)

        # X축 눈금을 배경/사람 텍스트로 교체
        ax = pw.getAxis('bottom')
        ax.setTicks([[(0, '배경'), (1, '사람')]])

        # 배경 확률 막대 (파랑)
        self._mlp_bg_bar = pyqtgraph.BarGraphItem(
            x=[0], height=[1.0], width=0.6, brush=pyqtgraph.mkBrush(76, 155, 232, 200)
        )
        self._mlp_bg_bar.role = 'mlp_bg_bar'
        pw.addItem(self._mlp_bg_bar)

        # 사람 확률 막대 (빨강)
        self._mlp_human_bar = pyqtgraph.BarGraphItem(
            x=[1], height=[0.0], width=0.6, brush=pyqtgraph.mkBrush(232, 107, 76, 200)
        )
        self._mlp_human_bar.role = 'mlp_human_bar'
        pw.addItem(self._mlp_human_bar)

        # 0.5 기준선
        threshold_line = pyqtgraph.InfiniteLine(pos=0.5, angle=0, pen=pyqtgraph.mkPen('y', width=1, style=PyQt6.QtCore.Qt.PenStyle.DashLine))
        pw.addItem(threshold_line)

        # 신뢰도 텍스트 라벨
        self._mlp_conf_text = pyqtgraph.TextItem("", color='w', anchor=(0.5, 0))
        self._mlp_conf_text.setPos(0.5, 1.05)
        pw.addItem(self._mlp_conf_text)

        self.mlp_plot_TabWidget.addTab(pw, "MLP 확률")

    def create_mlp_history_tab(self):
        """MLP 판정 히스토리 탭 — 최근 100 프레임 판정을 색상 스트립으로 표시"""
        pw = pyqtgraph.PlotWidget()
        pw.setTitle("MLP 판정 히스토리  (🔴 사람 / 🔵 배경)", color='w', size='12pt')
        pw.setLabel('bottom', '← 오래된  |  최근 →', **{'font-size': '11pt'})
        pw.hideAxis('left')
        pw.setMouseEnabled(x=False, y=False)
        pw.setMenuEnabled(False)

        self._mlp_history_img = pyqtgraph.ImageItem()
        self._mlp_history_img.role = 'mlp_history_img'
        pw.addItem(self._mlp_history_img)
        pw.getViewBox().disableAutoRange()
        pw.getViewBox().setRange(xRange=(0, 100), yRange=(0, 20), padding=0)

        self.mlp_plot_TabWidget.addTab(pw, "MLP 히스토리")
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

        for i_index in range(self.svm_plot_TabWidget.count()):
            if self.svm_plot_TabWidget.tabText(i_index) == input_plot_name:
                return self.svm_plot_TabWidget.widget(i_index)

        return None

    def buffer_setting(self, A_inter_data:list):
        self.A_adc_buffer = A_inter_data

        (
            self.i_adc_buffer_len
            , self.i_adc_min
            , self.i_adc_mid
            , self.i_adc_max
            , self.f_adc_avg
            , self.f_adc_std
            , self.A_adc_exclusion_zero_buffer
            , self.i_adc_exclusion_zero_buffer_len
            , self.i_adc_exclusion_zero_min
            , self.i_adc_exclusion_zero_mid
            , self.i_adc_exclusion_zero_max
            , self.f_adc_exclusion_zero_avg
            , self.f_adc_exclusion_zero_std
        ) = self.get_adc_buffer_info(self.A_adc_buffer)

        (
            # ESP32에서 FFT를 수행하므로 PC 측 fft_handle.fft() 호출 비활성화
            # self.A_fft_frequencies
            # , self.A_fft_magnitudes
            # , self.f_fft_gain
            # , self.f_fft_adc_avg
            # , self.i_fft_peak_idx
            # , self.f_fft_peak_freq
            # , self.f_fft_peak_mag
        # ) = self.fft_handle.fft(self.A_adc_buffer, self.fft_gain_SpinBox.value())
        # ------ ESP32 FFT 수신 시 event_update_ui()에서 A_fft_frequencies/A_fft_magnitudes 갱신 ------
        ) = ()

        # print(f"debugger_start.py | buffer_setting() | f_adc_avg : {self.f_adc_avg} == f_fft_adc_avg : {self.f_fft_adc_avg}")

        # if self.svm_handle.b_is_trained:
        #     A_feature = self.svm_handle.extract_features(self.A_fft_magnitudes, self.A_fft_frequencies)
        # else:
        #     A_feature = None


        # self.svm_handle.svm(self.A_fft_magnitudes, self.A_fft_frequencies)
        # FFT 데이터가 수신된 경우에만 SVM/MLP 추론 (타입 12 미수신 시 빈 배열로 크래시 방지)
        if self.fft_features_data is not None:
            (
                self.A_svm_probabilty
                , self.i_svm_label
                , self.f_svm_confidence
            ) = self.svm_handle.svm(self.fft_features_data)

            # ############################# COPILOT EDIT START (MLP 실시간 추론)
            if self.mlp_handle.b_is_trained:
                (
                    self.A_mlp_probability
                    , self.i_mlp_label
                    , self.f_mlp_confidence
                ) = self.mlp_handle.mlp(self.fft_features_data)
            # ############################# COPILOT EDIT END


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

    def update_exceed_points(self, inter_Widget:QWidget, A_inter_data:List) -> list:
        """TP1 초과 지점을 빨간색 점, TP1_RECHECK 초과 지점을 주황색 점으로 표시"""

        A_i_tp1_over_x     = []  # 빨간 점 (TP1 ~ TP1_RECHECK)
        A_i_tp1_over_y     = []
        A_i_tp1_rck_over_x = []  # 주황 점 (TP1_RECHECK 초과)
        A_i_tp1_rck_over_y = []  # BUG FIX: x로 오타나 있었음
        
        for i_count, value in enumerate(A_inter_data):
            if self.i_tp1_rck > 0 and value > self.i_tp1_rck:
                # TP1_RECHECK 초과 → 주황 점
                A_i_tp1_rck_over_x.append(i_count)
                A_i_tp1_rck_over_y.append(value)    
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
        i_tp1_over_count = len(A_i_tp1_over_x)

        for item in items:
            if isinstance(item, pyqtgraph.ScatterPlotItem) and getattr(item, 'role', None) == cfg.TP1_RCK_POINT_NAME:
                target_scatter = item

        target_scatter.setData(A_i_tp1_rck_over_x, A_i_tp1_rck_over_y)
        i_tp1_rck_over_count = len(A_i_tp1_rck_over_x)

        return i_tp1_over_count, i_tp1_rck_over_count

    def update_adc_graph(self, inter_Widget:QWidget):
        """그래프 우측 상단에 통계 정보(최소, 최대, 중앙값, 평균) 표시
        Args:
            plot_name: 플롯 이름
            data: 데이터 배열
            y_max: 고정 Y축 최대값 (옵션)
            positive_only: True면 양수 값만 필터링해서 통계 계산
        """
        
        PlotItem = inter_Widget.getPlotItem()
        lines = PlotItem.listDataItems()
        if lines:
            lines[0].setData(self.A_adc_buffer)
        else:
            inter_Widget.plot(self.A_adc_buffer)

        # 수신된 실제 버퍼 크기로 X축 범위 실시간 업데이트
        n = len(self.A_adc_buffer)
        if n > 0:
            inter_Widget.setXRange(0, n - 1, padding=0.02)


        target_label = None
        items = getattr(PlotItem, 'items', None)  # 일부 버전은 속성, 일부는 다른 구조일 수 있음
        for item in items:
            if isinstance(item, pyqtgraph.TextItem) and getattr(item, 'role', None) == cfg.ADC_LABEL_NAME:
                target_label = item

######## TODO : get_adc_buffer_info 수정하기
        # (
        #     self.i_adc_buffer_len
        #     ,self.i_exclusion_zero_adc_buffer_len
        #     ,self.i_adc_min
        #     ,self.i_adc_max
        #     ,self.i_adc_avg
        #     ,self.i_adc_mid
        # ) = self.get_adc_buffer_info(self.A_adc_buffer)

        (
            self.i_tp1_over_count
            ,self.i_tp1_rck_over_count
        ) = self.update_exceed_points(inter_Widget, self.A_adc_buffer)  # TP1 초과점 표시

        s_stats_text = (
            f"총 Len : {self.i_adc_buffer_len}개\n"
            f"실제 값 Len : {self.i_adc_exclusion_zero_buffer_len}개)\n"
            f"실제 값 Min : {self.i_adc_exclusion_zero_min}\n"
            f"실제 값 Mid : {self.i_adc_exclusion_zero_mid}\n"
            f"실제 값 Max : {self.i_adc_exclusion_zero_max}\n"
            f"실제 값 Avg : {self.f_adc_exclusion_zero_avg:.1f}\n"
            f"실제 값 Std : {self.f_adc_exclusion_zero_std:.1f}\n"
            
            f"TP1 : {self.i_tp1_over_count}\n"
            f"TP1_RCK : {self.i_tp1_rck_over_count}\n"
        )
        target_label.setText(s_stats_text)

        ViewBox = PlotItem.getViewBox()
        x_max = ViewBox.viewRange()[0][1]
        y_max = ViewBox.viewRange()[1][1]

        target_label.setPos(x_max, y_max)

    # def compute_fft(self, adc_buffer, apply_window=True):
    #     """ADC 버퍼에 FFT 적용
        
    #     Args:
    #         adc_buffer: ADC 샘플 배열 (예: 300개의 uint16)
    #         apply_window: 윈도우 함수 적용 여부
            
    #     Returns:
    #         frequencies: 주파수 배열 (Hz)
    #         magnitudes: 진폭 배열 (정규화됨)
    #     """
    #     # n = len(adc_buffer)
        
    #     # # 1. DC 오프셋 제거
    #     # signal = np.array(adc_buffer, dtype=np.float64)
    #     # signal = signal - np.mean(signal)
        
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

    def update_fft_graph(self, inter_Widget:QWidget):
        """FFT 그래프 업데이트
        Args:
            adc_buffer: ADC 샘플 배열
        """
        # ############################# COPILOT EDIT START (raw magnitudes 저장 + 게인 분리)
        # raw magnitudes (게인 미적용) → SVM 특징 추출용
        # self.A_fft_frequencies, self.A_fft_magnitudes, self.i_fft_mean_freq, self.i_fft_peak_idx, self.i_fft_peak_freq, self.i_fft_peak_mag = self.fft_handle.fft(A_inter_data, self.fft_gain_SpinBox.value())

        # (
        #     self.A_fft_frequencies
        #     ,self.A_fft_magnitudes
        #     ,self.i_fft_mean_freq
        #     ,self.i_fft_peak_idx
        #     ,self.i_fft_peak_freq
        #     ,self.i_fft_peak_mag
        # ) = self.fft_handle.fft(self.A_adc_buffer, self.fft_gain_SpinBox.value())

        # self.svm_handle.A_frequencies = A_frequencies
        # self.svm_handle.A_magnitudes  = A_magnitudes
        # self.svm_handle.i_mean        = i_mean
        # self.svm_handle.i_peak_idx    = i_peak_idx
        # self.svm_handle.i_peak_freq   = i_peak_freq
        # self.svm_handle.i_peak_mag    = i_peak_mag
        # self._last_fft_raw   = A_magnitudes_raw.copy()
        # self._last_fft_freqs = A_frequencies.copy()
        # self._last_adc_raw   = list(A_inter_data)   # 파형 오버레이/실시간 뷰용 원시 ADC 저장

        # # 게인 적용 → 그래프 표시용
        # A_magnitudes = A_magnitudes * self.fft_gain_SpinBox.value()
        # ############################# COPILOT EDIT END
        # print(f"debugger_start.py | update_fft_graph() | A_return_fft_data = {A_return_fft_data}")
        # 전체 스펙트럼 그래프 업데이트
        # if "ADC_FFT" in self.plots:
        #     self.plots["ADC_FFT"].setData(frequencies, magnitudes)
            
        #     # 피크 주파수 찾기 (DC 제외)
        #     if len(magnitudes) > 1:
        #         # DC(0Hz) 제외한 영역에서 피크 찾기
        #         peak_idx = np.argmax(magnitudes[1:]) + 1
        #         peak_freq = frequencies[peak_idx]
        #         peak_mag = magnitudes[peak_idx]
                
        #         # 피크 라벨 업데이트 (Mean 값 포함)
        #         if "ADC_FFT" in self.fft_peak_labels:
        #             label = self.fft_peak_labels["ADC_FFT"]
        #             label.setText(f"DC Mean: {dc_mean:.1f}\nPeak: {peak_freq:.2f} Hz\n진폭(Mag): {peak_mag:.1f}")
        #             label.setPos(frequencies[-1] * 0.6, 50)  # Y축 150 고정, 중간 위치


        PlotItem = inter_Widget.getPlotItem()
        lines = PlotItem.listDataItems()
        # 에너지(re²+im²) 분포를 그래프에 표시
        if len(self.A_fft_energies) > 0 and len(self.A_fft_frequencies) == len(self.A_fft_energies):
            y_energy = self.A_fft_energies.astype(numpy.float64)
        else:
            y_energy = self.A_fft_magnitudes

        # Magnitude = sqrt(energy) × Gain (PC 계산)
        gain = self.fft_gain_SpinBox.value()
        y_mag = numpy.sqrt(numpy.maximum(y_energy, 0)) * gain

        if len(lines) >= 2:
            lines[0].setData(self.A_fft_frequencies, y_energy)  # 에너지 선 (노란 대시)
            lines[1].setData(self.A_fft_frequencies, y_mag)     # Magnitude × Gain 선 (오렌지 실선)
        elif len(lines) == 1:
            lines[0].setData(self.A_fft_frequencies, y_energy)
            inter_Widget.plot(self.A_fft_frequencies, y_mag,
                              pen=pyqtgraph.mkPen(color='#ff8800', width=1,
                                                  style=pyqtgraph.QtCore.Qt.PenStyle.SolidLine),
                              name='Mag × Gain')
        else:
            inter_Widget.plot(self.A_fft_frequencies, y_energy)
            inter_Widget.plot(self.A_fft_frequencies, y_mag,
                              pen=pyqtgraph.mkPen(color='#ff8800', width=1,
                                                  style=pyqtgraph.QtCore.Qt.PenStyle.SolidLine),
                              name='Mag × Gain')

        target_label = None
        items = getattr(PlotItem, 'items', None)  # 일부 버전은 속성, 일부는 다른 구조일 수 있음
        for item in items:
            if isinstance(item, pyqtgraph.TextItem) and getattr(item, 'role', None) == cfg.FFT_LABEL_NAME:
                target_label = item

        # 기본 FFT 통계
        s_stats_text = (
            f"Peak Freq : {self.f_fft_peak_freq:.2f} Hz\n"
            f"Peak Idx  : {self.i_fft_peak_idx}\n"
        )
        # FFT 특징값 (타입 13) — 수신된 경우 추가 표시
        if self.fft_features_data is not None:
            ft = self.fft_features_data
            s_stats_text += (
                f"--- FFT Features ---\n"
                f"Centroid      (무게중심 주파수) : {ft.f_centroid:.2f} Hz\n"
                f"Rolloff       (롤오프 주파수)   : {ft.f_spectral_rolloff:.2f} Hz\n"
                f"Bandwidth     (대역폭)          : {ft.f_spectral_bandwidth:.2f} Hz\n"
                f"Peak Freq     (1위 피크 주파수) : {ft.f_peak_freq:.2f} Hz\n"
                f"2nd Peak Freq (2위 피크 주파수) : {ft.f_second_peak_freq:.2f} Hz\n"
                f"Peak Count    (피크 빈 개수)    : {ft.i_peak_count}\n"
                f"RMS           (RMS 진폭)        : {ft.f_rms:.4f}\n"
                f"Avg Energy    (평균 에너지)     : {ft.ui32_avg_energy}\n"
                f"Peak Energy   (피크 에너지)     : {ft.ui32_peak_energy}\n"
                f"Low Ratio     (저주파 비율)     : {ft.f_low_ratio:.3f}\n"
                f"Mid Ratio     (중주파 비율)     : {ft.f_mid_ratio:.3f}\n"
                f"High Ratio    (고주파 비율)     : {ft.f_high_ratio:.3f}\n"
                f"L/H Ratio     (저/고주파 비율)  : {ft.f_low_to_high_ratio:.3f}\n"
                f"P1/P2 Ratio   (1위/2위 피크 비율): {ft.f_peak1_to_peak2_ratio:.3f}\n"
                f"Peak/Avg E    (피크/평균 에너지 비율): {ft.f_peak_to_avg_e:.3f}\n"
                f"E Variance    (에너지 분산)     : {ft.f_energy_variance:.2f}\n"
                f"Kurtosis      (첨도)            : {ft.f_kurtosis:.3f}\n"
                f"Skewness      (왜도)            : {ft.f_skewness:.3f}\n"
            )

        target_label.setText(s_stats_text)
        ViewBox = PlotItem.getViewBox()
        x_max = ViewBox.viewRange()[0][1]
        y_max = ViewBox.viewRange()[1][1]

        target_label.setPos(x_max, y_max)


    _SVM_COL_LABEL_MAP = {
        svm.enum_csv_col.SPECTRAL_ROLLOFF     : "스펙트럼 롤오프(Hz)",
        svm.enum_csv_col.SPECTRAL_BANDWIDTH   : "스펙트럼 대역폭(Hz)",
        svm.enum_csv_col.PEAK_COUNT           : "피크 개수",
        svm.enum_csv_col.MID_RATIO            : "중주파 에너지 비율",
        svm.enum_csv_col.LOW_TO_HIGH_RATIO    : "저고주파 비율",
        svm.enum_csv_col.SECOND_PEAK_FREQ     : "2차 피크 주파수(Hz)",
        svm.enum_csv_col.KURTOSIS             : "첨도(Kurtosis)",
        svm.enum_csv_col.CENTROID             : "무게중심 주파수(Hz)",
        svm.enum_csv_col.PEAK_FREQ            : "피크 주파수(Hz)",
        svm.enum_csv_col.LOW_RATIO            : "저주파 에너지 비율",
        svm.enum_csv_col.RMS                  : "RMS 에너지",
        svm.enum_csv_col.AVG_ENERGY           : "평균 에너지",
        svm.enum_csv_col.PEAK_ENERGY          : "피크 에너지",
        svm.enum_csv_col.ENERGY_VARIANCE      : "에너지 분산",
        svm.enum_csv_col.PEAK_TO_AVG_E        : "피크-평균 에너지 비율",
        svm.enum_csv_col.HIGH_RATIO           : "고주파 에너지 비율",
        svm.enum_csv_col.PEAK1_TO_PEAK2_RATIO : "1차-2차 피크 비율",
        svm.enum_csv_col.SKEWNESS             : "왜도(Skewness)",
        svm.enum_csv_col.DC_RATIO             : "DC 에너지 비율",
        svm.enum_csv_col.DELTA_PEAK_FREQ      : "피크 주파수 변화량(Hz)",
        svm.enum_csv_col.SPECTRAL_FLATNESS    : "스펙트럼 평탄도",
    }
    def _set_svm_point_visible(self, role_name: str, visible: bool):
        """SVM 그래프에서 특정 role의 ScatterPlotItem 표시/숨김"""
        get_Widget = self.get_TabWidget(SVM_NAME)
        if get_Widget is None:
            return
        for item in getattr(get_Widget.getPlotItem(), 'items', []):
            if isinstance(item, pyqtgraph.ScatterPlotItem) and getattr(item, 'role', None) == role_name:
                item.setVisible(visible)

    def _rebuild_svm_2d(self):
        """현재 X/Y 축 2개 특징만으로 SVM을 백그라운드에서 학습"""
        if not self.svm_handle.b_is_trained or not self.svm_handle.A_train_features:
            self._svm_2d_model  = None
            self._svm_2d_scaler = None
            return
        X_full = numpy.array(self.svm_handle.A_train_features)
        y      = numpy.array(self.svm_handle.A_train_labels)
        worker = SvmRebuild2dWorker(
            X_full, y,
            int(self.svm_x_col), int(self.svm_y_col),
            self.svm_x_col, self.svm_y_col
        )
        worker.finished.connect(self._on_svm_2d_rebuilt)
        worker.finished.connect(worker.deleteLater)
        self._svm_2d_worker = worker  # GC 방지
        worker.start()

    @PyQt6.QtCore.pyqtSlot(object, object, object, object)
    def _on_svm_2d_rebuilt(self, scaler_2d, model_2d, x_col, y_col):
        """2D SVM 학습 완료 콜백 (메인 스레드)"""
        # 현재 콤보박스 값과 같을 때만 적용 (도중에 축이 바뀐 경우를 충돌 제거)
        if x_col != self.svm_x_col or y_col != self.svm_y_col:
            return
        self._svm_2d_scaler = scaler_2d
        self._svm_2d_model  = model_2d
        self._svm_2d_x_col  = x_col
        self._svm_2d_y_col  = y_col
        self._svm_boundary_cache = None
        # 경계 즉시 갱신
        get_Widget = self.get_TabWidget(SVM_NAME)
        if get_Widget is not None:
            self.update_svm_graph(get_Widget)

    def _refresh_axis_combos(self):
        """선택된 A_feature_indices 에 포함된 enum_csv_col 항목만 콤보박스에 표시"""
        feat_set = set(self.svm_handle.A_feature_indices)
        prev_x = self.svm_x_col
        prev_y = self.svm_y_col

        for combo, attr in [(self.svm_x_ComboBox, 'svm_x_col'), (self.svm_y_ComboBox, 'svm_y_col')]:
            combo.blockSignals(True)
            combo.clear()
            prev_val = getattr(self, attr)
            new_idx  = 0
            for i, col in enumerate(svm.enum_csv_col):
                if int(col) in feat_set:
                    combo.addItem(self._SVM_COL_LABEL_MAP.get(col, col.name), userData=col)
                    if col == prev_val:
                        new_idx = combo.count() - 1
            combo.setCurrentIndex(new_idx)
            setattr(self, attr, combo.currentData())
            combo.blockSignals(False)

        # X/Y 가 바뀐 경우 캐시 무효화
        if self.svm_x_col != prev_x or self.svm_y_col != prev_y:
            self._svm_boundary_cache = None

    def set_svm_axis_labels(self, inter_Widget:QWidget, x_col:svm.enum_csv_col, y_col:svm.enum_csv_col):
        inter_Widget.setLabel('bottom', self._SVM_COL_LABEL_MAP.get(x_col, str(x_col)), **{'font-size': '14pt'})
        inter_Widget.setLabel('left',   self._SVM_COL_LABEL_MAP.get(y_col, str(y_col)), **{'font-size': '14pt'})

    def on_svm_axis_changed(self):
        self.svm_x_col = self.svm_x_ComboBox.currentData()
        self.svm_y_col = self.svm_y_ComboBox.currentData()
        self._svm_boundary_cache = None
        self._svm_2d_model = None   # 이전 모델 즉시 무효화 (학습 완료 전까지 경계 숨김)
        self._rebuild_svm_2d()      # 백그라운드에서 재학습 시작 (뇌택 X)
    def update_svm_graph(self, inter_Widget:QWidget):

        # ############################# COPILOT EDIT START (Phase 1+2+3+A: 실시간 SVM 분류 + 산점도 + 히스토리 + 파형 뷰)
        # # Phase A: 파형 뷰 실시간 라인 갱신 (SVM 학습 여부 무관하게 항상 업데이트)
        # _x_wave = numpy.arange(len(self.A_adc_buffer)) / cfg.FFT_SAMPLING_RATE
        # self.svm_realtime_waveform.setData(_x_wave, list(self.A_adc_buffer))

        # if self.svm_handle.b_is_trained:



        #     A_feature = self.svm_handle.extract_features(self.A_fft_magnitudes, self.A_fft_frequencies)






            
        #     i_label, f_confidence = self.svm_handle.predict(A_feature)

            # (i_label, f_confidence)
            # i_label      : LABEL_BACKGROUND(0) or LABEL_HUMAN(1)
            # f_confidence : 신뢰도 0.0~1.0
        # if self.i_svm_label == svm.enum_label.LABEL_HUMAN:

        #     # inter_Widget.setBackground((80, 0, 0, 180))
        #     s_svm_result = f"● 사람 감지  ({self.f_svm_confidence*100:.1f}%)"
        #     rt_brush = pyqtgraph.mkBrush(255, 80, 80, 230)
        #     # self.svm_realtime_waveform.setPen(pyqtgraph.mkPen((255, 80, 80), width=2))  # 빨강

        # else:

        #     # inter_Widget.setBackground((0, 60, 0, 180))
        #     s_svm_result = f"○ 배경  ({self.f_svm_confidence*100:.1f}%)"
        #     rt_brush = pyqtgraph.mkBrush(80, 255, 80, 230)
        #     # self.svm_realtime_waveform.setPen(pyqtgraph.mkPen((80, 255, 80), width=2))  # 초록





        #     target_label.setText(s_stats_text + f"SVM : {s_svm_result}")

        #     # Phase 2: 산점도에 실시간 현재 위치 표시
        #     f_peak_freq = float(self.A_fft_frequencies[self.i_fft_peak_idx])
        #     f_peak_mag  = float(self.A_fft_magnitudes[self.i_fft_peak_idx])
        #     self.svm_realtime_scatter.setData(
        #         x=[f_peak_freq], y=[f_peak_mag],
        #         brush=rt_brush
        #     )
        #     # Phase 3: 히스토리 deque 에 레이블 추가 → 히스토리 탭 갱신
        #     self._svm_history.append(i_label)
        #     self._update_svm_history_display()


        # else:
        #     inter_Widget.setBackground('default')
        #     self.svm_realtime_waveform.setPen(pyqtgraph.mkPen('w', width=2))  # 미학습 → 흰색


        # ############################# COPILOT EDIT END



##################### TODO : 여기 꾸며야 함

        # with open(self.svm_handle.str_svm_csv_path, 'r') as f:
        #     reader = csv.reader(f)
        #     next(reader, None)  # 헤더 스킵
        #     for row in reader:
        #         if len(row) < 2:
        #             continue
        #         # peak_freq = 인덱스 151 (mag_0~150 다음)
        #         # peak_mag  = 인덱스 152
        #         f_peak_freq = float(row[151])
        #         f_peak_mag  = float(row[152])
        #         i_label     = int(row[-1])
        #         if i_label == svm.enum_label.LABEL_BACKGROUND:
        #             A_bg_x.append(f_peak_freq)
        #             A_bg_y.append(f_peak_mag)
        #         else:
        #             A_human_x.append(f_peak_freq)
        #             A_human_y.append(f_peak_mag)



        A_svm_bg_x, A_svm_bg_y = [], []
        A_svm_occu_x, A_svm_occu_y = [], []

        # target_scatter = None
        # PlotItem = inter_Widget.getPlotItem()
        # items = getattr(PlotItem, 'items', None)  # 일부 버전은 속성, 일부는 다른 구조일 수 있음
        # for item in items:
        #     if isinstance(item, pyqtgraph.ScatterPlotItem) and getattr(item, 'role', None) == cfg.SVM_BACKGROUND_NAME:
        #         target_scatter = item
        # # ScatterPlot 업데이트
        # target_scatter.setData(A_i_tp1_over_x, A_i_tp1_over_y)
        # # 초과 개수 라벨 업데이트 (우측 상단 위치)



        # for item in list(inter_Widget.listDataItems()):
        #     if item is not self.svm_realtime_scatter:
        #         inter_Widget.removeItem(item)

        self.set_svm_axis_labels(inter_Widget, self.svm_x_col, self.svm_y_col)

        for features, label in zip(self.svm_handle.A_train_features, self.svm_handle.A_train_labels):
            x = features[self.svm_x_col]
            y = features[self.svm_y_col]
            if label == svm.enum_label.LABEL_BACKGROUND:
                A_svm_bg_x.append(x)
                A_svm_bg_y.append(y)
            else:
                A_svm_occu_x.append(x)
                A_svm_occu_y.append(y)

        # 배경 점
        target_scatter = None
        PlotItem = inter_Widget.getPlotItem()
        items = getattr(PlotItem, 'items', None)
        for item in items:
            if isinstance(item, pyqtgraph.ScatterPlotItem) and getattr(item, 'role', None) == cfg.SVM_BACKGROUND_POINT_NAME:
                target_scatter = item
        if target_scatter is not None:
            target_scatter.setData(A_svm_bg_x, A_svm_bg_y)
            target_scatter.setVisible(self.svm_show_bg_ToggleButton.isChecked())

        # 사람 점
        target_scatter = None
        PlotItem = inter_Widget.getPlotItem()
        items = getattr(PlotItem, 'items', None)
        for item in items:
            if isinstance(item, pyqtgraph.ScatterPlotItem) and getattr(item, 'role', None) == cfg.SVM_OCCUPANCY_POINT_NAME:
                target_scatter = item
        if target_scatter is not None:
            target_scatter.setData(A_svm_occu_x, A_svm_occu_y)
            target_scatter.setVisible(self.svm_show_occu_ToggleButton.isChecked())

        # 사용자가 직접 zoom/pan 하지 않은 경우에만 자동 범위 조정
        # (경계 배경 표시 중에는 autoRange 비활성화 → 뷰 안정화로 캐시 히트율 향상)
        if not self._b_svm_user_zoomed and not self.svm_handle.b_is_trained:
            inter_Widget.enableAutoRange()


        # 실시간 현재 위치 점 (star) 업데이트
        now_scatter = None
        PlotItem = inter_Widget.getPlotItem()
        items = getattr(PlotItem, 'items', None)
        for item in items:
            if isinstance(item, pyqtgraph.ScatterPlotItem) and getattr(item, 'role', None) == cfg.SVM_NOW_POINT_NAME:
                now_scatter = item
        if now_scatter is not None:
            now_x = self.svm_handle.A_train_features[-1][self.svm_x_col] if self.svm_handle.A_train_features else None
            # 현재 프레임의 특징값을 직접 svm_handle 멤버에서 읽기
            _col_to_attr = {
                svm.enum_csv_col.PEAK_FREQ        : 'f_peak_freq',
                svm.enum_csv_col.PEAK_MAG         : 'f_peak_mag',
                svm.enum_csv_col.AVG_MAG          : 'f_avg_mag',
                svm.enum_csv_col.STD_MAG          : 'f_std_mag',
                svm.enum_csv_col.CENTROID         : 'f_centroid',
                svm.enum_csv_col.LOW_ENERGY       : 'f_low_energy',
                svm.enum_csv_col.MID_ENERGY       : 'f_mid_energy',
                svm.enum_csv_col.HIGH_ENERGY      : 'f_high_energy',
                svm.enum_csv_col.RMS              : 'f_rms',
                svm.enum_csv_col.LOW_RATIO        : 'f_low_ratio',
                svm.enum_csv_col.SPECTRAL_ENTROPY : 'f_spectral_entropy',
                svm.enum_csv_col.PEAK_TO_MEAN     : 'f_peak_to_mean',
            }
            now_x = getattr(self.svm_handle, _col_to_attr[self.svm_x_col], 0.0)
            now_y = getattr(self.svm_handle, _col_to_attr[self.svm_y_col], 0.0)
            now_scatter.setData(x=[now_x], y=[now_y])

        # 2D SVM 실시간 판정 (모델이 준비된 경우)
        if self._svm_2d_model is not None and self._svm_2d_scaler is not None:
            _now_x2 = getattr(self.svm_handle, _col_to_attr.get(self.svm_x_col, ''), 0.0) \
                      if hasattr(self.svm_handle, _col_to_attr.get(self.svm_x_col, '_')) else 0.0
            _now_y2 = getattr(self.svm_handle, _col_to_attr.get(self.svm_y_col, ''), 0.0) \
                      if hasattr(self.svm_handle, _col_to_attr.get(self.svm_y_col, '_')) else 0.0
            _v2 = self._svm_2d_scaler.transform([[_now_x2, _now_y2]])
            self._svm_2d_label = int(self._svm_2d_model.predict(_v2)[0])
            _p2 = self._svm_2d_model.predict_proba(_v2)[0]
            self._svm_2d_conf  = float(_p2[self._svm_2d_label])
            self._svm_2d_proba = _p2

        # 결정 경계 배경 렌더링 (학습된 경우만)
        boundary_item = None
        for item in getattr(inter_Widget.getPlotItem(), 'items', []):
            if isinstance(item, pyqtgraph.ImageItem) and getattr(item, 'role', None) == cfg.SVM_BOUNDARY_IMAGE_NAME:
                boundary_item = item
        if boundary_item is not None:
            if self.svm_handle.b_is_trained and self._svm_2d_model is not None:
                ViewBox = inter_Widget.getPlotItem().getViewBox()
                x_min, x_max = ViewBox.viewRange()[0]
                y_min, y_max = ViewBox.viewRange()[1]
                _cache_key = (round(x_min, 4), round(x_max, 4), round(y_min, 4), round(y_max, 4),
                              self.svm_x_col, self.svm_y_col)
                if self._svm_boundary_cache != _cache_key:
                    self._svm_boundary_cache = _cache_key
                    N = 40
                    x_grid = numpy.linspace(x_min, x_max, N)
                    y_grid = numpy.linspace(y_min, y_max, N)
                    xx, yy = numpy.meshgrid(x_grid, y_grid, indexing='ij')
                    grid_2d        = numpy.column_stack([xx.ravel(), yy.ravel()])   # (N*N, 2)
                    grid_2d_scaled = self._svm_2d_scaler.transform(grid_2d)         # (N*N, 2)
                    Z = self._svm_2d_model.predict(grid_2d_scaled).reshape(N, N)
                    img = numpy.zeros((N, N, 4), dtype=numpy.uint8)
                    img[Z == svm.enum_label.LABEL_BACKGROUND] = [255, 200,  0, 50]
                    img[Z == svm.enum_label.LABEL_HUMAN]      = [  0, 180, 80, 50]
                    boundary_item.setImage(img)
                    boundary_item.setRect(pyqtgraph.QtCore.QRectF(
                        x_min, y_min, x_max - x_min, y_max - y_min
                    ))
            else:
                boundary_item.clear()
                self._svm_boundary_cache = None

        # 우측 상단 범위 텍스트 라벨 업데이트
        target_label = None
        PlotItem_label = inter_Widget.getPlotItem()
        for item in getattr(PlotItem_label, 'items', []):
            if isinstance(item, pyqtgraph.TextItem) and getattr(item, 'role', None) == cfg.SVM_LABEL_NAME:
                target_label = item
        if target_label is not None:
            ViewBox = PlotItem_label.getViewBox()
            x_min, x_max = ViewBox.viewRange()[0]
            y_min, y_max = ViewBox.viewRange()[1]
            x_label = self._SVM_COL_LABEL_MAP.get(self.svm_x_col, str(self.svm_x_col))
            y_label = self._SVM_COL_LABEL_MAP.get(self.svm_y_col, str(self.svm_y_col))

            h = self.svm_handle
            if h.b_is_trained and len(h.A_probabilty) >= 2:
                prob_bg   = h.A_probabilty[svm.enum_label.LABEL_BACKGROUND] * 100
                prob_occu = h.A_probabilty[svm.enum_label.LABEL_HUMAN]      * 100
                svm_label_str = "Occupancy" if h.i_label == svm.enum_label.LABEL_HUMAN else "Background"
                pc1, pc2  = h.get_pca_now()
                # 2D 판정
                if self._svm_2d_model is not None and len(self._svm_2d_proba) >= 2:
                    d2_bg   = self._svm_2d_proba[svm.enum_label.LABEL_BACKGROUND] * 100
                    d2_occu = self._svm_2d_proba[svm.enum_label.LABEL_HUMAN]      * 100
                    d2_str  = "Occupancy" if self._svm_2d_label == svm.enum_label.LABEL_HUMAN else "Background"
                    s_2d = (
                        f"[ 2D 판정 (X/Y만) ] {d2_str}  ({self._svm_2d_conf*100:.1f}%)\n"
                        f"  Background : {d2_bg:.1f}%\n"
                        f"  Occupancy  : {d2_occu:.1f}%\n\n"
                    )
                else:
                    s_2d = "[ 2D 판정 (X/Y만) ] 비대기\n\n"
                s_info = (
                    f"[ SVM 판정 (24D 전체) ] {svm_label_str}  ({h.f_confidence*100:.1f}%)\n"
                    f"  Background : {prob_bg:.1f}%\n"
                    f"  Occupancy  : {prob_occu:.1f}%\n\n"
                    + s_2d +
                    f"[ PCA 좌표 ]\n"
                    f"  PC1 : {pc1:+.4f}\n"
                    f"  PC2 : {pc2:+.4f}\n\n"
                    f"[ 뷰 범위 ]\n"
                    f"  X ({x_label})\n"
                    f"    {x_min:.3f} ~ {x_max:.3f}\n"
                    f"  Y ({y_label})\n"
                    f"    {y_min:.3f} ~ {y_max:.3f}"
                )
            else:
                s_info = (
                    f"[ SVM 판정 ] 미학습\n\n"
                    f"[ 뷰 범위 ]\n"
                    f"  X ({x_label})\n"
                    f"    {x_min:.3f} ~ {x_max:.3f}\n"
                    f"  Y ({y_label})\n"
                    f"    {y_min:.3f} ~ {y_max:.3f}"
                )
            target_label.setText(s_info)
            target_label.setPos(x_max, y_max)


    def update_svm_pca_graph(self, inter_Widget: QWidget):
        """PCA 2D 투영 탭 실시간 업데이트"""
        if inter_Widget is None:
            return

        A_pca_bg_x,   A_pca_bg_y   = [], []
        A_pca_occu_x, A_pca_occu_y = [], []

        PlotItem = inter_Widget.getPlotItem()
        items = getattr(PlotItem, 'items', [])

        if self.svm_handle.b_is_trained and self.svm_handle.A_pca_train_2d is not None:
            for pca_point, label in zip(self.svm_handle.A_pca_train_2d, self.svm_handle.A_train_labels):
                if label == svm.enum_label.LABEL_BACKGROUND:
                    A_pca_bg_x.append(float(pca_point[0]))
                    A_pca_bg_y.append(float(pca_point[1]))
                else:
                    A_pca_occu_x.append(float(pca_point[0]))
                    A_pca_occu_y.append(float(pca_point[1]))

        # 배경 / 사람 스캐터 업데이트
        for item in items:
            role = getattr(item, 'role', None)
            if not isinstance(item, pyqtgraph.ScatterPlotItem):
                continue
            if role == cfg.SVM_PCA_BG_POINT_NAME:
                item.setData(A_pca_bg_x, A_pca_bg_y)
            elif role == cfg.SVM_PCA_OCCU_POINT_NAME:
                item.setData(A_pca_occu_x, A_pca_occu_y)

        # 사용자가 직접 zoom/pan 하지 않은 경우에만 자동 범위 조정
        if not self._b_svm_pca_user_zoomed:
            inter_Widget.enableAutoRange()

        # 현재 위치 (now) star 업데이트
        pc1, pc2 = self.svm_handle.get_pca_now()
        for item in items:
            if isinstance(item, pyqtgraph.ScatterPlotItem) and getattr(item, 'role', None) == cfg.SVM_PCA_NOW_POINT_NAME:
                item.setData(x=[pc1], y=[pc2])

        # 결정 경계 배경 이미지
        for item in items:
            if not (isinstance(item, pyqtgraph.ImageItem) and getattr(item, 'role', None) == cfg.SVM_PCA_BOUNDARY_IMAGE_NAME):
                continue
            if self.svm_handle.b_is_trained and self.svm_handle.pca is not None:
                ViewBox = PlotItem.getViewBox()
                x_min, x_max = ViewBox.viewRange()[0]
                y_min, y_max = ViewBox.viewRange()[1]
                _cache_key = (round(x_min, 4), round(x_max, 4), round(y_min, 4), round(y_max, 4))
                if self._svm_pca_boundary_cache != _cache_key:
                    self._svm_pca_boundary_cache = _cache_key
                    N = 40
                    pc1_grid = numpy.linspace(x_min, x_max, N)
                    pc2_grid = numpy.linspace(y_min, y_max, N)
                    xx, yy = numpy.meshgrid(pc1_grid, pc2_grid, indexing='ij')
                    grid_2d = numpy.column_stack([xx.ravel(), yy.ravel()])
                    # PCA 역변환 → 이미 스케일된 160D 공간 → SVM 직접 예측
                    grid_160d = self.svm_handle.pca.inverse_transform(grid_2d)
                    Z = self.svm_handle.svm_model.predict(grid_160d).reshape(N, N)
                    img = numpy.zeros((N, N, 4), dtype=numpy.uint8)
                    img[Z == svm.enum_label.LABEL_BACKGROUND] = [255, 200,  0, 50]
                    img[Z == svm.enum_label.LABEL_HUMAN]      = [  0, 180, 80, 50]
                    item.setImage(img)
                    item.setRect(pyqtgraph.QtCore.QRectF(x_min, y_min, x_max - x_min, y_max - y_min))
            else:
                item.clear()
                self._svm_pca_boundary_cache = None

        # 범위 텍스트 라벨 업데이트
        for item in items:
            if isinstance(item, pyqtgraph.TextItem) and getattr(item, 'role', None) == cfg.SVM_PCA_LABEL_NAME:
                ViewBox = PlotItem.getViewBox()
                x_min, x_max = ViewBox.viewRange()[0]
                y_min, y_max = ViewBox.viewRange()[1]

                h = self.svm_handle
                if h.b_is_trained and len(h.A_probabilty) >= 2:
                    prob_bg    = h.A_probabilty[svm.enum_label.LABEL_BACKGROUND] * 100
                    prob_occu  = h.A_probabilty[svm.enum_label.LABEL_HUMAN]      * 100
                    label_str  = "Occupancy" if h.i_label == svm.enum_label.LABEL_HUMAN else "Background"
                    s_info = (
                        f"[ 판정 ] {label_str}  ({h.f_confidence*100:.1f}%)\n"
                        f"  Background : {prob_bg:.1f}%\n"
                        f"  Occupancy  : {prob_occu:.1f}%\n"
                        f"\n"
                        f"[ PCA 좌표 ]\n"
                        f"  PC1 : {pc1:+.4f}\n"
                        f"  PC2 : {pc2:+.4f}\n"
                        f"\n"
                        f"[ 특징값 ]\n"
                        f"  peak_freq  : {h.f_peak_freq:.3f} Hz\n"
                        f"  peak_mag   : {h.f_peak_mag:.4f}\n"
                        f"  avg_mag    : {h.f_avg_mag:.4f}\n"
                        f"  std_mag    : {h.f_std_mag:.4f}\n"
                        f"  centroid   : {h.f_centroid:.3f} Hz\n"
                        f"  low_energy : {h.f_low_energy:.4f}\n"
                        f"  mid_energy : {h.f_mid_energy:.4f}\n"
                        f"  high_energy: {h.f_high_energy:.4f}\n"
                        f"  rms        : {h.f_rms:.4f}\n"
                        f"\n"
                        f"[ 학습 샘플 ]\n"
                        f"  BG     : {self.collector.i_bg_count}\n"
                        f"  Occu   : {self.collector.i_human_count}\n"
                        f"\n"
                        f"[ 뷰 범위 ]\n"
                        f"  PC1 : {x_min:.3f} ~ {x_max:.3f}\n"
                        f"  PC2 : {y_min:.3f} ~ {y_max:.3f}"
                    )
                else:
                    s_info = (
                        f"[ 판정 ] 미학습\n"
                        f"\n"
                        f"[ 뷰 범위 ]\n"
                        f"  PC1 : {x_min:.3f} ~ {x_max:.3f}\n"
                        f"  PC2 : {y_min:.3f} ~ {y_max:.3f}"
                    )
                item.setText(s_info)
                item.setPos(x_max, y_max)

    def update_mlp_visual(self):
        """MLP 확률 막대 및 히스토리 탭 실시간 업데이트"""
        prob = self.A_mlp_probability if len(self.A_mlp_probability) == 2 else [1.0, 0.0]

        # ── 확률 막대 업데이트 ──────────────────────────────────────
        self._mlp_bg_bar.setOpts(height=[prob[0]])
        self._mlp_human_bar.setOpts(height=[prob[1]])

        if self.i_mlp_label == svm.enum_label.LABEL_HUMAN:
            self._mlp_conf_text.setText(f"● 사람  {prob[1]*100:.1f}%", color='#ff5555')
        else:
            self._mlp_conf_text.setText(f"○ 배경  {prob[0]*100:.1f}%", color='#55cc55')

        # ── 히스토리 업데이트 ─────────────────────────────────────
        self._mlp_history.append(self.i_mlp_label)
        n = len(self._mlp_history)
        if n > 0:
            # shape: (n, 20, 4) RGBA 이미지
            img_arr = numpy.zeros((n, 20, 4), dtype=numpy.uint8)
            for i, label in enumerate(self._mlp_history):
                if label == svm.enum_label.LABEL_HUMAN:
                    img_arr[i, :] = [232, 80, 76, 230]   # 빨강 = 사람
                else:
                    img_arr[i, :] = [76, 155, 232, 230]  # 파랑 = 배경
            self._mlp_history_img.setImage(img_arr, autoLevels=False)
            # 뷰 범위 고정 (가장 최근 100프레임이 오른쪽에 표시되도록)
            self._mlp_history_img.getViewBox().setRange(
                xRange=(0, 100), yRange=(0, 20), padding=0
            )
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

    def closeEvent(self, event):
        """윈도우 종료 이벤트 — 버퍼에 남은 데이터를 CSV에 기록 후 종료"""
        self.collector.flush_write_buffer()
        if self.uart_thread and self.uart_thread.isRunning():
            self.uart_thread.stop()
        event.accept()





    # # ############################# COPILOT EDIT START (Phase 2: update_svm_scatter)
    # def update_svm_scatter(self):
    #     """
    #     CSV 데이터로 산점도 갱신 (학습 완료 후 호출)
    #     X축: peak_freq  Y축: peak_mag
    #     """
    #     # import csv as _csv
    #     # import os

    #     if not os.path.exists(self.svm_handle.str_svm_csv_path):
    #         return

    #     A_bg_x, A_bg_y = [], []
    #     A_human_x, A_human_y = [], []

    #     # with open(self.svm_handle.str_svm_csv_path, 'r') as f:
    #     #     reader = csv.reader(f)
    #     #     next(reader, None)  # 헤더 스킵
    #     #     for row in reader:
    #     #         if len(row) < 2:
    #     #             continue
    #     #         # peak_freq = 인덱스 151 (mag_0~150 다음)
    #     #         # peak_mag  = 인덱스 152
    #     #         f_peak_freq = float(row[151])
    #     #         f_peak_mag  = float(row[152])
    #     #         i_label     = int(row[-1])
    #     #         if i_label == svm.enum_label.LABEL_BACKGROUND:
    #     #             A_bg_x.append(f_peak_freq)
    #     #             A_bg_y.append(f_peak_mag)
    #     #         else:
    #     #             A_human_x.append(f_peak_freq)
    #     #             A_human_y.append(f_peak_mag)

    #     # 기존 배경/사람 점 제거
    #     for item in list(self.svm_scatter_PlotWidget.listDataItems()):
    #         if item is not self.svm_realtime_scatter:
    #             self.svm_scatter_PlotWidget.removeItem(item)

    #     # 배경 점 (초록)
    #     if A_bg_x:
    #         scatter_bg = pyqtgraph.ScatterPlotItem(
    #             x=A_bg_x, y=A_bg_y,
    #             size=8, pen=pyqtgraph.mkPen(None),
    #             brush=pyqtgraph.mkBrush(0, 200, 0, 180),
    #             symbol='o', name='배경'
    #         )
    #         self.svm_scatter_PlotWidget.addItem(scatter_bg)

    #     # 사람 점 (빨강)
    #     if A_human_x:
    #         scatter_human = pyqtgraph.ScatterPlotItem(
    #             x=A_human_x, y=A_human_y,
    #             size=8, pen=pyqtgraph.mkPen(None),
    #             brush=pyqtgraph.mkBrush(220, 0, 0, 180),
    #             symbol='t', name='사람'
    #         )
    #         self.svm_scatter_PlotWidget.addItem(scatter_human)
    # # ############################# COPILOT EDIT END






    def update_svm_label_count(self):
        # i_bg, i_human = self.svm_handle.get_sample_counts(self.svm_handle.str_svm_csv_path)
        # i_bg_count, i_human_count = self.svm_handle.get_label_counts()
        # self.svm_count_Label.setText(f"BG: {i_bg_count}  |  Human: {i_human_count}")
        self.svm_count_Label.setText(f"BackGround: {self.collector.i_bg_count}  |  Occupancy: {self.collector.i_human_count}")

    # # def log_TextEdit_print_sensor_data(self, input_sensor_parser_data:updm.SensorData):
    # #     """센서 데이터를 로그 문자열로 변환"""
    # #     s_data_name = upcfg.get_data_type_name(input_sensor_parser_data.i_data_type)
        
    # #     s_chksum_pass_status = "✓" if input_sensor_parser_data.UartReceiveData_raw.b_chksum_pass else "✗"
    # #     s_header_text = (f"{s_chksum_pass_status}\n"
    # #                     f"UartReceiveData[{input_sensor_parser_data.UartReceiveData_raw.timestamp.strftime('%H:%M:%S.%f')[:-3]}],\n"
    # #                     f"SensorData[{input_sensor_parser_data.timestamp.strftime('%H:%M:%S.%f')[:-3]}],\n"
    # #                     f"Type: {s_data_name},\n"
    # #                     f"bytes_data_length: {input_sensor_parser_data.UartReceiveData_raw.bytes_data_length},\n"
    # #                     f"bytes_data: {input_sensor_parser_data.UartReceiveData_raw.bytes_data},\n"
    # #                     f"bytes_checksum: 0x{input_sensor_parser_data.UartReceiveData_raw.bytes_checksum},\n"
    # #                     f"Checksum: 0x{input_sensor_parser_data.UartReceiveData_raw.bytes_checksum},\n"
    # #                     f"i_data_type: {input_sensor_parser_data.i_data_type},\n"
    # #                     f"i_adc_raw: {input_sensor_parser_data.i_adc_raw},\n"
    # #                     f"A_adc_buffer: {input_sensor_parser_data.A_adc_buffer},\n"
    # #                     f"settings: {input_sensor_parser_data.settings},\n"
    # #                     f")\n")

    # #     A_s_log_lines = [s_header_text]

    # #     # --- 버퍼 데이터 처리 ---
    # #     A_target_buffer, s_target_name = None, None
    # #     if input_sensor_parser_data.A_adc_buffer:
    # #         A_target_buffer, s_target_name = input_sensor_parser_data.A_adc_buffer, "ADC Buffer"

    # #     if A_target_buffer is not None and s_target_name is not None:

    # #         #### TODO : get_adc_buffer_info 수정하기
    # #         i_buffer_len, i_exclusion_zero_buffer_len, i_min, i_max, i_avg, i_mid = self.get_adc_buffer_info(A_target_buffer)

    # #         s_stats_text = (
    # #             f"총 Len: {i_buffer_len}개\n"
    # #             f"실제 값 Len: {i_exclusion_zero_buffer_len}개)\n"
    # #             f"실제 값 Min: {i_min}\n"
    # #             f"실제 값 Max: {i_max}\n"
    # #             f"실제 값 Avg: {i_avg:.1f}\n"
    # #             f"실제 값 Mid: {i_mid}"
    # #         )
    # #         A_s_log_lines.append(s_stats_text)

    # #     # --- 설정값 처리 ---
    # #     elif input_sensor_parser_data.settings:
    # #         SettingsData_handle = input_sensor_parser_data.settings
    # #         s_occupancy_status = "🟢 재실 O" if SettingsData_handle.b_occu_status else "⚪ 재실 X"
    # #         A_s_log_lines.append(f"Settings : {s_occupancy_status}")
    # #         A_s_log_lines.append(f" - TP1 : {SettingsData_handle.i_tp1}")
    # #         A_s_log_lines.append(f" - TP1 Recheck : {SettingsData_handle.i_tp1_recheck}")
    # #         A_s_log_lines.append(f" - TP2 : {SettingsData_handle.i_tp2}")
    # #         A_s_log_lines.append(f" - LED : Max={SettingsData_handle.i_led_max_per}%, Min={SettingsData_handle.i_led_min_per}%, Dim={SettingsData_handle.i_led_dim_per}%")
    # #         A_s_log_lines.append(f" - LED Step : {SettingsData_handle.i_led_work_ms} ms, Work : {SettingsData_handle.i_led_step_ms} ms, Delay : {SettingsData_handle.i_led_delay_ms} ms")
    # #         A_s_log_lines.append(f" - Occupancy Timeout : {SettingsData_handle.i_occu_chk_timeout_us} us")
    # #         A_s_log_lines.append(f" - Sleep Time : {SettingsData_handle.i_sleep_time_us} us")
    # #         A_s_log_lines.append(f" - Occupancy : {SettingsData_handle.b_occu_status}")
    # #         A_s_log_lines.append(f" - PIR Output : {SettingsData_handle.b_pir_status}")

    # #     return "\n".join(A_s_log_lines) # 리스트의 각 항목을 \n(줄바꿈)으로 이어 붙여 하나의 문자열로 만듭니다.

    @PyQt6.QtCore.pyqtSlot(object)
    def event_update_ui(self, input_sensor_parser_data:updm.SensorData):
        if input_sensor_parser_data.A_adc_buffer:

            self.buffer_setting(input_sensor_parser_data.A_adc_buffer)
            

            get_Widget = self.get_TabWidget(ADC_RAW_FULL_SCALE_NAME)
            self.update_adc_graph(get_Widget)
            get_Widget = self.get_TabWidget(ADC_RAW_ZOOM_SCALE_NAME)
            self.update_adc_graph(get_Widget)
            
            # ★ FFT 그래프는 FFT 패킷 수신 시(아래 블록)에서만 갱신 — ADC 수신마다 재호출 불필요
            # (FFT는 FFT_STRIDE 샘플마다 1회 계산되므로 ADC보다 갱신 빈도가 낮음)

            # ★ SVM 분석 및 그래프 업데이트 (학습된 경우에만)
            if self.svm_handle.b_is_trained:
                get_Widget = self.get_TabWidget(SVM_NAME)
                self.update_svm_graph(get_Widget)
                get_Widget = self.get_TabWidget(cfg.SVM_PCA_NAME)
                self.update_svm_pca_graph(get_Widget)

            # ★ MLP 추론 결과 라벨 업데이트
            if self.mlp_handle.b_is_trained:
                if self.i_mlp_label == svm.enum_label.LABEL_HUMAN:
                    self.mlp_result_Label.setText(f"🔴 MLP: 사람 감지  ({self.f_mlp_confidence*100:.1f}%)")
                    self.mlp_result_Label.setStyleSheet(MACRO_FONT_BOLD + MACRO_FONT_SIZE.format(14) + MACRO_TEXT_COLOR.format('#ff5555'))
                else:
                    self.mlp_result_Label.setText(f"🟢 MLP: 배경  ({self.f_mlp_confidence*100:.1f}%)")
                    self.mlp_result_Label.setStyleSheet(MACRO_FONT_BOLD + MACRO_FONT_SIZE.format(14) + MACRO_TEXT_COLOR.format('#55cc55'))
                self.update_mlp_visual()
            else:
                self.mlp_result_Label.setText("🤖 MLP: 미로드 (모델 없음)")
                self.mlp_result_Label.setStyleSheet(MACRO_FONT_BOLD + MACRO_FONT_SIZE.format(14))

            # ★ 자동 저장 토글 ON 상태일 때 FFT 데이터 준비된 경우만, 구독 유니트에서 저장 (시간 기반 → FFT 갱신 횟수 기반로 변경)
            # 자동 저장은 아래 '# 5. ESP32 FFT 수신 데이터 업데이트' 블록에서 처리됨



        # 3. 설정값 업데이트
        if input_sensor_parser_data.settings:
            SettingsData_handle = input_sensor_parser_data.settings
            self.adc_tp1_setting(SettingsData_handle.i_tp1)
            self.adc_tp1_rck_setting(SettingsData_handle.i_tp1_recheck)

            # SpinBox 초기값 반영 (최초 1회 또는 새로고침 버튼 클릭 후 1회)
            if not self._settings_loaded:
                self.tp1_SpinBox.setValue(         SettingsData_handle.i_tp1)
                self.tp1_rck_SpinBox.setValue(     SettingsData_handle.i_tp1_recheck)
                self.tp2_SpinBox.setValue(         SettingsData_handle.i_tp2)
                self.led_max_SpinBox.setValue(     SettingsData_handle.i_led_max_per)
                self.led_min_SpinBox.setValue(     SettingsData_handle.i_led_min_per)
                self.led_dim_SpinBox.setValue(     SettingsData_handle.i_led_dim_per)
                self.led_work_ms_SpinBox.setValue( SettingsData_handle.i_led_work_ms)
                self.led_step_ms_SpinBox.setValue( SettingsData_handle.i_led_step_ms)
                self.led_delay_ms_SpinBox.setValue(SettingsData_handle.i_led_delay_ms)
                self.occu_timeout_s_SpinBox.setValue(int(
                    SettingsData_handle.i_occu_chk_timeout_us // self._TIME_UNIT_MULTIPLIER[self.occu_unit_ComboBox.currentText()]))
                self.sleep_time_s_SpinBox.setValue(int(
                    SettingsData_handle.i_sleep_time_us // self._TIME_UNIT_MULTIPLIER[self.sleep_unit_ComboBox.currentText()]))
                self.fft_stride_SpinBox.setValue(SettingsData_handle.i_fft_stride)
                self._settings_loaded = True

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

        self.update_svm_label_count()

        # 4. 프로파일링 데이터 업데이트
        if input_sensor_parser_data.profiling:
            p = input_sensor_parser_data.profiling
            profiling_str = (
                f"⏱ ADC Read:       {p.adc_reading_time_us} µs\n"
                f"⏱ ADC Buf Lat:    {p.adc_read_buffer_latency_time_us} µs\n"
                f"⏱ ADC Processing: {p.adc_processing_time_us} µs\n"
                f"⏱ ADC Buf Insert: {p.adc_buffer_insert_time_us} µs\n"
                f"🌀 FFT 처리:       {p.fft_process_time_us} µs\n"
                f"🔬 특징 추출:       {p.fft_features_process_time_us} µs\n"
                f"🔁 FFT Loop A:     {p.fft_loop_a_time_us} µs\n"
                f"🔁 FFT Loop B:     {p.fft_loop_b_time_us} µs\n"
                f"🔁 FFT Loop C:     {p.fft_loop_c_time_us} µs"
            )
            self.profiling_Label.setText(profiling_str)

        # 5. ESP32 FFT 수신 데이터 업데이트
        if input_sensor_parser_data.fft_features:
            self.fft_features_data = input_sensor_parser_data.fft_features

        if input_sensor_parser_data.fft_result:
            fft_data = input_sensor_parser_data.fft_result
            fft_output_size = len(fft_data.magnitudes)
            # 주파수 배열 계산: freq[k] = k × SAMPLING_FREQ / WINDOW_SIZE
            import numpy as np
            self.A_fft_frequencies = numpy.array([k * self.f_sampling_rate / (2 * (fft_output_size - 1)) for k in range(fft_output_size)])
            self.A_fft_energies    = numpy.array(fft_data.energies,    dtype=numpy.uint32)   # re²+im² 정수 에너지
            self.A_fft_magnitudes  = numpy.array(fft_data.magnitudes,  dtype=numpy.float64)  # sqrt 복원 ADC 단위
            if fft_output_size > 0:
                self.i_fft_peak_idx   = int(np.argmax(self.A_fft_magnitudes[1:]) + 1)  # DC 제외
                self.f_fft_peak_freq  = self.A_fft_frequencies[self.i_fft_peak_idx]
                self.f_fft_peak_mag   = self.A_fft_magnitudes[self.i_fft_peak_idx]
            # FFT 그래프 갱신
            get_Widget = self.get_TabWidget(ADC_FFT_FULL_SCALE_NAME)
            self.update_fft_graph(get_Widget)
            get_Widget = self.get_TabWidget(ADC_FFT_ZOOM_SCALE_NAME)
            self.update_fft_graph(get_Widget)

            # ★ FFT 갱신 횟수 기반 자동 저장
            # ESP32에서 새 FFT 결과가 도착할 때마다 카운터 증가,
            # i_auto_save_stride회마다 SVM 특징을 1회 캐포마 함으로 동일 프레임 중복 저장 방지.
            if self.b_auto_save_bg or self.b_auto_save_human:
                # 새 fft_features 패킷이 도착한 경우만 카운터 증가 (동일 객체 반복 전송 차단)
                if (self.fft_features_data is not None
                        and self.fft_features_data is not self._last_auto_saved_fft_features):
                    self.i_fft_since_last_save += 1
                    if self.i_fft_since_last_save >= self.i_auto_save_stride:
                        self.i_fft_since_last_save = 0
                        self._last_auto_saved_fft_features = self.fft_features_data
                        if self.b_auto_save_bg:
                            self.collector.save_sample(self.fft_features_data, svm.enum_label.LABEL_BACKGROUND)
                        else:
                            self.collector.save_sample(self.fft_features_data, svm.enum_label.LABEL_HUMAN)
                        self.update_svm_label_count()

        # """UI 업데이트: 로그, 그래프, 설정 표시"""
        # # 1. 로그 텍스트 업데이트 (최대 500줄 제한)
        # log_str = self.log_TextEdit_print_sensor_data(input_sensor_parser_data)
        # self.log_TextEdit.append(log_str)
        
        # log_TextEdit_doc = self.log_TextEdit.document()
        # if log_TextEdit_doc.blockCount() > cfg.MAX_LOG_LINES:
        #     cursor = self.log_TextEdit.textCursor() # 내부 편집 커서(QTextCursor) 객체
        #     cursor.movePosition(cursor.MoveOperation.Start) # 커서를 문서의 맨 앞으로 이동
        #     # 아래로 N번 이동하면서(세 번째 인자가 N) 이동 중인 범위를 선택(두번째 인자 KeepAnchor가 선택 상태 유지).
        #     # 여기서 N = blockCount() - MAX_LOG_LINES (총 블록(줄) 수에서 허용 최대줄을 뺀 값) — 즉, 초과한 만큼의 첫 N줄을 선택함.
        #     cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, log_TextEdit_doc.blockCount() - cfg.MAX_LOG_LINES)
        #     # 택된 텍스트(즉 문서 맨 앞부터 초과분까지)를 삭제
        #     cursor.removeSelectedText()
        
        # self.log_TextEdit.verticalScrollBar().setValue(self.log_TextEdit.verticalScrollBar().maximum())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
