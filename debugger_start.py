"""
iSENSOR UART Debugger - GUI 버전

PyQt6와 pyqtgraph를 사용한 UART 데이터 시각화 도구
"""
import sys
import os
import json
import time
import datetime
import logging
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
    QSizePolicy, QDialog, QCheckBox, QScrollArea, QDialogButtonBox, QLineEdit,
    QRadioButton, QButtonGroup, QProgressBar
)
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtCore import QFileSystemWatcher

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
import ble_worker as blew   # BLE 통신 모듈
# ############################# COPILOT EDIT END

MACRO_FONT_NAME = "font-family: {};"
MACRO_FONT_BOLD = "font-weight: bold;"
MACRO_FONT_SIZE = "font-size: {}pt;"

BUTTON_HOVER_BG      = "QPushButton:hover { background-color: %s; }"
BUTTON_HOVER_BG_BOLD = "QPushButton { font-weight: bold; } QPushButton:hover { background-color: %s; }"

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


class MlpTrainWorker(PyQt6.QtCore.QThread):
    """MLP 학습을 백그라운드에서 실행하는 워커 스레드.

    Signals:
        epoch_progress(epoch, total, train_loss, val_loss, train_acc, val_acc) : 매 에폭마다 발생
        log_message(str)                                       : CSV 로드 / 전처리 로그
        finished(bool)                                         : 학습 완료 여부
    """
    epoch_progress = PyQt6.QtCore.pyqtSignal(int, int, float, float, float, float)
    log_message    = PyQt6.QtCore.pyqtSignal(str)
    finished       = PyQt6.QtCore.pyqtSignal(bool)

    def __init__(self, mlp_handle, str_csv_path: str,
                 epochs: int = None, learning_rate: float = None,
                 early_stop_patience: int = None,
                 hidden_layers: list = None,
                 dropout_rate: float = None,
                 batch_size: int = None,
                 val_ratio: float = None,
                 random_state: int = None,
                 stratify: bool = None,
                 log_interval: int = None,
                 feature_mode: str = None,
                 scaler_type: str = None,
                 lr_scheduler_patience: int = None,
                 lr_scheduler_factor: float = None):
        super().__init__()
        self._mlp_handle              = mlp_handle
        self._str_csv_path            = str_csv_path
        self._epochs                  = epochs
        self._learning_rate           = learning_rate
        self._early_stop_patience     = early_stop_patience
        self._hidden_layers           = hidden_layers
        self._dropout_rate            = dropout_rate
        self._batch_size              = batch_size
        self._val_ratio               = val_ratio
        self._random_state            = random_state
        self._stratify                = stratify
        self._log_interval            = log_interval
        self._feature_mode            = feature_mode
        self._scaler_type             = scaler_type
        self._lr_scheduler_patience   = lr_scheduler_patience
        self._lr_scheduler_factor     = lr_scheduler_factor
        self._stop_requested          = False

    def stop(self):
        """학습 중단 요청 — 다음 에폭 콜백에서 False 반환하여 루프 탈출"""
        self._stop_requested = True

    def run(self):
        def _cb(epoch, total, loss, val_loss, train_acc, val_acc):
            if self._stop_requested:
                return False   # nn_mlp.py 학습 루프에 중단 신호
            self.epoch_progress.emit(epoch, total, float(loss),
                                     float(val_loss), float(train_acc), float(val_acc))

        result = self._mlp_handle.train(self._str_csv_path,
                                        progress_callback=_cb,
                                        log_callback=self.log_message.emit,
                                        epochs=self._epochs,
                                        learning_rate=self._learning_rate,
                                        early_stop_patience=self._early_stop_patience,
                                        hidden_layers=self._hidden_layers,
                                        dropout_rate=self._dropout_rate,
                                        batch_size=self._batch_size,
                                        val_ratio=self._val_ratio,
                                        random_state=self._random_state,
                                        stratify=self._stratify,
                                        log_interval=self._log_interval,
                                        feature_mode=self._feature_mode,
                                        scaler_type=self._scaler_type,
                                        lr_scheduler_patience=self._lr_scheduler_patience,
                                        lr_scheduler_factor=self._lr_scheduler_factor)
        self.finished.emit(result)


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
                # ── [macOS] read(1) 블로킹 방식 ──────────────────────────────────────────
                # macOS 일부 USB-UART 드라이버에서 in_waiting이 항상 0을 반환하는 문제 대응
                byte_data:bytes = self.serial_port.read(1)
                if byte_data:
                    if self.serial_port.in_waiting > 0:
                        byte_data += self.serial_port.read(self.serial_port.in_waiting)
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
        self._last_auto_saved_fft_key  = None   # 자동 저장 중복 방지: (avg_energy, peak_energy, peak_freq) 튜플
        # # ############################# COPILOT EDIT START (svm 핸들 초기화 + Phase 3 히스토리)
        self.svm_handle:svm.SVM_Module      = svm.SVM_Module()
        self.collector:tdc.TrainingDataCollector = tdc.TrainingDataCollector()  # data_csv/svm_data_TIMESTAMP.csv 자동 생성
        # ############################# COPILOT EDIT START (mlp 핸들 초기화)
        self.mlp_handle:nn_mlp.MLP_Module = nn_mlp.MLP_Module()
        # nn_mlp 로거 경고 → QMessageBox 연동
        _mlp_logger = logging.getLogger('nn_mlp')
        if not _mlp_logger.handlers:
            _mlp_logger.setLevel(logging.WARNING)
            class _MlpQtWarningHandler(logging.Handler):
                def __init__(self, parent_widget):
                    super().__init__()
                    self._parent = parent_widget
                def emit(self, record):
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(self._parent, "[MLP] 경고", self.format(record))
            _handler = _MlpQtWarningHandler(self)
            _handler.setFormatter(logging.Formatter('%(message)s'))
            _mlp_logger.addHandler(_handler)
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

        # data_csv/ 실시간 감시 (MLP 데이터 수 표시)
        self._data_csv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_csv")
        self._csv_watcher = QFileSystemWatcher()
        if os.path.isdir(self._data_csv_dir):
            self._csv_watcher.addPath(self._data_csv_dir)
            for _f in os.listdir(self._data_csv_dir):
                if _f.endswith('.csv'):
                    self._csv_watcher.addPath(os.path.join(self._data_csv_dir, _f))
        self._csv_watcher.directoryChanged.connect(self._on_data_csv_dir_changed)
        self._csv_watcher.fileChanged.connect(self._on_data_csv_file_changed)

        self.A_svm_probabilty           = []
        self.i_svm_label                = 0
        self.f_svm_confidence           = 0.0

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
        self.graph_y_label_setting("에너지", enum_graph_plot_num.ADC_FFT)
        self.graph_line_color_setting(cfg.ADC_FFT_LINE_COLOR, enum_graph_plot_num.ADC_FFT)
        self.graph_legend_setting('FFT 분포', enum_graph_plot_num.ADC_FFT)

        self.graph_title_setting(SVM_NAME, enum_graph_plot_num.SVM, enum_graph_plot_range_opt.ALL)
        self.graph_x_label_pos_setting("bottom", enum_graph_plot_num.SVM)
        self.graph_x_label_setting("피크 주파수(Hz)", enum_graph_plot_num.SVM)
        self.graph_y_label_pos_setting("left", enum_graph_plot_num.SVM)
        self.graph_y_label_setting("피크 강도", enum_graph_plot_num.SVM)
        self.graph_line_color_setting(cfg.SVM_LINE_COLOR, enum_graph_plot_num.SVM)

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
        self.left_GridLayout = QGridLayout()            # 2. 3열 그리드 레이아웃 생성
        self.left_GridLayout.setColumnStretch(0, 1)     # 좌열 / 중열 / 우열 동등 비율
        self.left_GridLayout.setColumnStretch(1, 1)
        self.left_GridLayout.setColumnStretch(2, 1)
        self.left_Widget.setLayout(self.left_GridLayout)     # 3. 레이아웃을 대상 위젯에 적용
# --- 제어창 표시 설정 ---
        self.left_control_Label = QLabel("제어창")             # 1. 대상 위젯 생성
        self.left_control_Label.setStyleSheet(""
                                              + MACRO_FONT_BOLD
                                              + MACRO_FONT_SIZE.format(14)
                                              )  # * 위젯 폰트 설정
        self.left_control_Label.setFixedHeight(30)             # * 위젯 가로 사이즈 설정
        self.left_GridLayout.addWidget(self.left_control_Label, 0, 0, 1, 3)    # Row0 - 전체 3열 차지
# --- Connection 그룹 설정 ---
        self.connection_GroupBox = QGroupBox("Connection")             # 1. 대상 위젯 생성
        self.connection_GridLayout = QGridLayout()                     # 2. Grid 레이아웃 생성 
        self.connection_GroupBox.setLayout(self.connection_GridLayout)            # 3. 레이아웃을 대상 위젯에 적용
        self.left_GridLayout.addWidget(self.connection_GroupBox, 1, 0)          # Row1 Col0 - Connection

        # --- � UART / BLE 토글 (Row 0) ---
        self._conn_type_ButtonGroup = QButtonGroup(self)
        self._uart_RadioButton = QRadioButton("🔌 UART")
        self._ble_RadioButton  = QRadioButton("📶 BLE")
        self._uart_RadioButton.setChecked(True)
        self._conn_type_ButtonGroup.addButton(self._uart_RadioButton, 0)
        self._conn_type_ButtonGroup.addButton(self._ble_RadioButton,  1)
        _conn_type_HBox = QHBoxLayout()
        _conn_type_HBox.addWidget(self._uart_RadioButton)
        _conn_type_HBox.addWidget(self._ble_RadioButton)
        self.connection_GridLayout.addLayout(_conn_type_HBox, 0, 0, 1, 2)
        self._uart_RadioButton.toggled.connect(self._on_conn_type_toggled)

        # --- �📶포트 설정 ---
        # --- 포트 라벨 설정 ---
        self.port_sel_Label = QLabel("📶포트: ")
        self.port_sel_Label.setStyleSheet(""
                                          + MACRO_FONT_BOLD
                                          # + MACRO_BORDER_RADIUS.format(6)
                                          + MACRO_BORDER_STYLE.format('none')
                                          )
        self.port_sel_Label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)    # 레이블은 텍스트 크기 위주, 늘어나지 않게
        self.connection_GridLayout.addWidget(self.port_sel_Label, 1, 0)         # 3. 위젯을 대상 레이아웃에 적용
        # --- 포트 목록 및 버튼 설정 ---
        self.port_sel_HBoxLayout = QHBoxLayout()                    # 2. 가로 방향 레이아웃 생성
        self.connection_GridLayout.addLayout(self.port_sel_HBoxLayout, 1, 1)         # 3. 위젯을 대상 레이아웃에 적용
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
        self.connection_GridLayout.addWidget(self.baudrate_sel_Label, 2, 0)         # 3. 위젯을 대상 레이아웃에 적용
        # --- 보드레이트 목록 설정 ---
        self.baudrate_sel_ComboBox = QComboBox()                               # 1. 대상 위젯 생성
        self.connection_GridLayout.addWidget(self.baudrate_sel_ComboBox, 2, 1)         # 3. 위젯을 대상 레이아웃에 적용

        # --- 📶 BLE 장치명 입력 (UART 선택 시 숨김) ---
        self._ble_device_Label = QLabel("📶 장치명: ")
        self._ble_device_Label.setStyleSheet(MACRO_FONT_BOLD + MACRO_BORDER_STYLE.format('none'))
        self._ble_device_LineEdit = QLineEdit(blew.ISENSOR_BLE_NAME)
        self._ble_device_LineEdit.setPlaceholderText("BLE 광고명 (예: iSENSOR)")
        self.connection_GridLayout.addWidget(self._ble_device_Label,    1, 0)
        self.connection_GridLayout.addWidget(self._ble_device_LineEdit, 1, 1)
        self._ble_device_Label.setVisible(False)
        self._ble_device_LineEdit.setVisible(False)

        # --- 연결하기 버튼 설정 ---
        self.port_connect_PushButton = QPushButton("🔌연결하기")
        self.port_connect_PushButton.setStyleSheet(""
                                                  + MACRO_FONT_BOLD 
                                                  )
        self.port_connect_PushButton.setStyleSheet(""
                                                  + BUTTON_HOVER_BG % cfg.LINE_COLOR
                                                  )
        self.port_connect_PushButton.clicked.connect(self.event_port_connection)
        self.connection_GridLayout.addWidget(self.port_connect_PushButton, 3, 0, 1, 2)

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
        self.left_GridLayout.addWidget(self.fft_gain_GroupBox, 4, 0, 1, 1)            # Row4 Col0 - FFT Setting


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

        # --- ADC 주석 패널 (FFT Setting 오른쪽, Row4 Col1) ---
        self.adc_stats_GroupBox = QGroupBox("ADC 주석")
        self.adc_stats_GroupBox.setStyleSheet("" + MACRO_BORDER_RADIUS.format(6))
        adc_stats_VBoxLayout = QVBoxLayout()
        self.adc_stats_GroupBox.setLayout(adc_stats_VBoxLayout)
        self.left_GridLayout.addWidget(self.adc_stats_GroupBox, 1, 2, 3, 1)   # Row1-3 Col2 - ADC 주석 패널

        self.adc_stats_Label = QLabel("수신 대기 중...")
        self.adc_stats_Label.setStyleSheet(
            "font-family: Consolas, monospace;"
            "font-size: 9pt;"
            "border-style: none;"
        )
        self.adc_stats_Label.setAlignment(PyQt6.QtCore.Qt.AlignmentFlag.AlignTop | PyQt6.QtCore.Qt.AlignmentFlag.AlignLeft)
        self.adc_stats_Label.setWordWrap(False)
        adc_stats_VBoxLayout.addWidget(self.adc_stats_Label)

############################################################################################################ SVM
        # --- SVM 데이터 수집 ---
        self.svm_collect_GroupBox = QGroupBox("SVM Setting")
        self.svm_collect_GroupBox.setStyleSheet("" + MACRO_BORDER_RADIUS.format(6))
        self.svm_collect_GridLayout = QGridLayout()
        self.svm_collect_GroupBox.setLayout(self.svm_collect_GridLayout)
        self.left_GridLayout.addWidget(self.svm_collect_GroupBox, 5, 0, 1, 1)          # Row5 Col0 - SVM Setting

        # --- FFT Features 패널 (SVM Setting 오른쪽, Row5 Col1) ---
        self.fft_features_GroupBox = QGroupBox("FFT Features")
        self.fft_features_GroupBox.setStyleSheet("" + MACRO_BORDER_RADIUS.format(6))
        fft_features_VBoxLayout = QVBoxLayout()
        self.fft_features_GroupBox.setLayout(fft_features_VBoxLayout)
        self.left_GridLayout.addWidget(self.fft_features_GroupBox, 4, 2, 2, 1)   # Row4-5 Col2 - FFT Features 패널

        self.fft_features_Label = QLabel("수신 대기 중...")
        self.fft_features_Label.setStyleSheet(
            "font-family: Consolas, monospace;"
            "font-size: 9pt;"
            "border-style: none;"
        )
        self.fft_features_Label.setAlignment(PyQt6.QtCore.Qt.AlignmentFlag.AlignTop | PyQt6.QtCore.Qt.AlignmentFlag.AlignLeft)
        self.fft_features_Label.setWordWrap(False)
        fft_features_VBoxLayout.addWidget(self.fft_features_Label)


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
        # QShortcut 대신 앱 레벨 eventFilter 사용 → SpinBox/LineEdit 포커스와 무관하게 동작
        QApplication.instance().installEventFilter(self)

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

############################################################################################################ MLP Training
        self.mlp_train_GroupBox = QGroupBox("MLP Training")
        self.mlp_train_GroupBox.setStyleSheet("" + MACRO_BORDER_RADIUS.format(6))
        self.mlp_train_GridLayout = QGridLayout()
        self.mlp_train_GroupBox.setLayout(self.mlp_train_GridLayout)
        self.left_GridLayout.addWidget(self.mlp_train_GroupBox, 4, 1, 2, 1)     # Row4-5 Col1 - MLP Training

        # CSV 파일 선택 레이블 + 버튼
        self.mlp_csv_Label = QLabel("CSV: data_csv/ 전체 병합 학습")
        self.mlp_csv_Label.setStyleSheet("" + MACRO_BORDER_STYLE.format('none'))
        self.mlp_train_GridLayout.addWidget(self.mlp_csv_Label, 0, 0, 1, 2)

        # 총 학습 데이터 수 표시 레이블
        self.mlp_data_count_Label = QLabel("총 데이터: 계산 중...")
        self.mlp_data_count_Label.setStyleSheet(
            MACRO_BORDER_STYLE.format('none') + MACRO_FONT_BOLD
        )
        self.mlp_train_GridLayout.addWidget(self.mlp_data_count_Label, 1, 0, 1, 2)

        # ── 하이퍼파라미터 설정 행 ────────────────────────────
        import AI.mlp.nn_mlp as _nn_mlp_ref

        # 에폭
        self.mlp_epochs_Label = QLabel("에폭")
        self.mlp_epochs_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_train_GridLayout.addWidget(self.mlp_epochs_Label, 6, 0)

        self.mlp_epochs_SpinBox = QSpinBox()
        self.mlp_epochs_SpinBox.setRange(10, 100000)
        self.mlp_epochs_SpinBox.setSingleStep(50)
        self.mlp_epochs_SpinBox.setValue(_nn_mlp_ref.EPOCHS)
        self.mlp_train_GridLayout.addWidget(self.mlp_epochs_SpinBox, 6, 1)

        # 학습률 (가수 × 10^지수 방식 직접 입력)
        self.mlp_lr_Label = QLabel("LR")
        self.mlp_lr_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_lr_Label.setToolTip("LR = 가수 × 10^지수  (예: 5.0 e-4 → 5×10⁻⁴ = 0.0005)")
        self.mlp_train_GridLayout.addWidget(self.mlp_lr_Label, 7, 0)

        import math as _math
        _lr_default     = _nn_mlp_ref.LEARNING_RATE
        _lr_exp_default = int(_math.floor(_math.log10(_lr_default)))   # e.g. -4
        _lr_man_default = round(_lr_default / (10 ** _lr_exp_default), 1)  # e.g. 5.0

        _lr_container = QWidget()
        _lr_hbox      = QHBoxLayout(_lr_container)
        _lr_hbox.setContentsMargins(0, 0, 0, 0)
        _lr_hbox.setSpacing(2)

        self.mlp_lr_mantissa_DoubleSpinBox = QDoubleSpinBox()
        self.mlp_lr_mantissa_DoubleSpinBox.setRange(1.0, 9.9)
        self.mlp_lr_mantissa_DoubleSpinBox.setSingleStep(0.5)
        self.mlp_lr_mantissa_DoubleSpinBox.setDecimals(1)
        self.mlp_lr_mantissa_DoubleSpinBox.setValue(_lr_man_default)
        self.mlp_lr_mantissa_DoubleSpinBox.setToolTip("LR 가수부 (1.0 ~ 9.9)")

        self.mlp_lr_exp_SpinBox = QSpinBox()
        self.mlp_lr_exp_SpinBox.setRange(-7, -1)
        self.mlp_lr_exp_SpinBox.setSingleStep(1)
        self.mlp_lr_exp_SpinBox.setValue(_lr_exp_default)
        self.mlp_lr_exp_SpinBox.setPrefix("e")
        self.mlp_lr_exp_SpinBox.setToolTip("LR 지수부 (e-1 ~ e-7)\n예: e-4 → ×10⁻⁴")

        _lr_hbox.addWidget(self.mlp_lr_mantissa_DoubleSpinBox)
        _lr_hbox.addWidget(self.mlp_lr_exp_SpinBox)
        self.mlp_train_GridLayout.addWidget(_lr_container, 7, 1)

        # Early Stop patience
        self.mlp_es_Label = QLabel("Early Stop")
        self.mlp_es_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_train_GridLayout.addWidget(self.mlp_es_Label, 10, 0)

        self.mlp_es_SpinBox = QSpinBox()
        self.mlp_es_SpinBox.setRange(0, 200)
        self.mlp_es_SpinBox.setSingleStep(5)
        self.mlp_es_SpinBox.setValue(20)
        self.mlp_es_SpinBox.setSpecialValueText("비활성화")  # 0일 때 표시
        self.mlp_train_GridLayout.addWidget(self.mlp_es_SpinBox, 10, 1)

        # 레이어 구조
        self.mlp_layers_Label = QLabel("Layer")
        self.mlp_layers_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_train_GridLayout.addWidget(self.mlp_layers_Label, 2, 0)

        self.mlp_layers_ComboBox = QComboBox()
        for _l in ["256-128-64-32", "128-64-32", "64-32", "256-128-64", "128-64", "64"]:
            self.mlp_layers_ComboBox.addItem(_l)
        _default_layers = '-'.join(str(h) for h in _nn_mlp_ref.HIDDEN_LAYERS)
        idx = self.mlp_layers_ComboBox.findText(_default_layers)
        self.mlp_layers_ComboBox.setCurrentIndex(idx if idx >= 0 else 0)
        self.mlp_train_GridLayout.addWidget(self.mlp_layers_ComboBox, 2, 1)

        # Dropout
        self.mlp_dropout_Label = QLabel("Dropout")
        self.mlp_dropout_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_train_GridLayout.addWidget(self.mlp_dropout_Label, 5, 0)

        self.mlp_dropout_SpinBox = QDoubleSpinBox()
        self.mlp_dropout_SpinBox.setRange(0.0, 1.0)
        self.mlp_dropout_SpinBox.setSingleStep(0.05)
        self.mlp_dropout_SpinBox.setDecimals(2)
        self.mlp_dropout_SpinBox.setValue(_nn_mlp_ref.DROPOUT_RATE)
        self.mlp_train_GridLayout.addWidget(self.mlp_dropout_SpinBox, 5, 1)

        # Batch size
        self.mlp_batch_Label = QLabel("Batch")
        self.mlp_batch_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_train_GridLayout.addWidget(self.mlp_batch_Label, 4, 0)

        self.mlp_batch_SpinBox = QSpinBox()
        self.mlp_batch_SpinBox.setRange(4, 256)
        self.mlp_batch_SpinBox.setSingleStep(8)
        self.mlp_batch_SpinBox.setValue(_nn_mlp_ref.BATCH_SIZE)
        self.mlp_train_GridLayout.addWidget(self.mlp_batch_SpinBox, 4, 1)

        # 검증 비율 (Val Ratio)
        self.mlp_val_ratio_Label = QLabel("검증 비율")
        self.mlp_val_ratio_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_val_ratio_Label.setToolTip("전체 데이터 중 검증에 사용할 비율 (예: 0.2 = 20%)")
        self.mlp_train_GridLayout.addWidget(self.mlp_val_ratio_Label, 11, 0)

        self.mlp_val_ratio_ComboBox = QComboBox()
        for _vr in ["0.10", "0.15", "0.20", "0.25", "0.30"]:
            self.mlp_val_ratio_ComboBox.addItem(_vr)
        self.mlp_val_ratio_ComboBox.setCurrentText(f"{_nn_mlp_ref.VAL_RATIO:.2f}")
        self.mlp_train_GridLayout.addWidget(self.mlp_val_ratio_ComboBox, 11, 1)

        # 분리 시드 (random_state)
        self.mlp_seed_Label = QLabel("분리 시드\n(-1=매번 다름, 숫자=고정)")
        self.mlp_seed_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_seed_Label.setToolTip("학습/검증 분리 시 사용하는 랜덤 시드\n-1 → 실행마다 다르게 분리 (재현 불가)\n0 이상 → 항상 동일하게 분리 (재현 가능)")
        self.mlp_train_GridLayout.addWidget(self.mlp_seed_Label, 13, 0)

        self.mlp_seed_SpinBox = QSpinBox()
        self.mlp_seed_SpinBox.setRange(-1, 9999)
        self.mlp_seed_SpinBox.setSingleStep(1)
        self.mlp_seed_SpinBox.setValue(42)
        self.mlp_seed_SpinBox.setSpecialValueText("랜덤 (-1)")
        self.mlp_train_GridLayout.addWidget(self.mlp_seed_SpinBox, 13, 1)

        # 비율 고정 (stratify)
        self.mlp_stratify_Label = QLabel("비율 고정")
        self.mlp_stratify_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_stratify_Label.setToolTip("배경/사람 비율을 학습·검증에 동일하게 유지할지 여부")
        self.mlp_train_GridLayout.addWidget(self.mlp_stratify_Label, 12, 0)

        self.mlp_stratify_ComboBox = QComboBox()
        self.mlp_stratify_ComboBox.addItem("사용 (비율 동일하게 분리)")
        self.mlp_stratify_ComboBox.addItem("미사용 (완전 랜덤 분리)")
        self.mlp_train_GridLayout.addWidget(self.mlp_stratify_ComboBox, 12, 1)

        # 로그 출력 주기
        self.mlp_log_interval_Label = QLabel("로그 주기")
        self.mlp_log_interval_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_log_interval_Label.setToolTip("몇 에폭마다 손실/정확도를 출력할지")
        self.mlp_train_GridLayout.addWidget(self.mlp_log_interval_Label, 14, 0)

        self.mlp_log_interval_SpinBox = QSpinBox()
        self.mlp_log_interval_SpinBox.setRange(1, 100)
        self.mlp_log_interval_SpinBox.setSingleStep(1)
        self.mlp_log_interval_SpinBox.setValue(10)
        self.mlp_log_interval_SpinBox.setSuffix(" 에폭마다")
        self.mlp_train_GridLayout.addWidget(self.mlp_log_interval_SpinBox, 14, 1)

        # 특징 모드 선택
        self.mlp_feature_mode_Label = QLabel("특징 모드")
        self.mlp_feature_mode_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_feature_mode_Label.setToolTip(
            "ESP32 (21개): ESP32가 계산한 특징 그대로 학습\n"
            "PC 재계산 (25개): FFT 데이터로 PC에서 재계산한 특징으로 학습"
        )
        self.mlp_train_GridLayout.addWidget(self.mlp_feature_mode_Label, 15, 0)

        self.mlp_feature_mode_ComboBox = QComboBox()
        self.mlp_feature_mode_ComboBox.addItem("ESP32 (21개 특징)")
        self.mlp_feature_mode_ComboBox.addItem("PC 재계산 (25개 특징)")
        self.mlp_feature_mode_ComboBox.setToolTip(
            "학습에 사용할 특징 세트를 선택합니다.\n"
            "PC 재계산: FFT 원시 데이터로 PC에서 25개 특징 추출 → ESP32 결과와 비교 가능"
        )
        self.mlp_train_GridLayout.addWidget(self.mlp_feature_mode_ComboBox, 15, 1)

        # 스케일러 선택
        self.mlp_scaler_Label = QLabel("스케일러")
        self.mlp_scaler_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_scaler_Label.setToolTip(
            "StandardScaler: z-score 정규화 (평균0, 표준편차1) — 기본값\n"
            "RobustScaler: 중앙값/IQR 기반 — 이상치에 강건, 환경 노이즈 변동 시 유리"
        )
        self.mlp_train_GridLayout.addWidget(self.mlp_scaler_Label, 3, 0)

        self.mlp_scaler_ComboBox = QComboBox()
        self.mlp_scaler_ComboBox.addItem("Standard (z-score)")
        self.mlp_scaler_ComboBox.addItem("Robust (중앙값/IQR)")
        self.mlp_scaler_ComboBox.setToolTip(
            "Standard: 평균·표준편차 기반 정규화 (일반적 환경)\n"
            "Robust: 중앙값·IQR 기반 — SPECTRAL_FLATNESS 같은 이상치에 민감한 특징에 유리"
        )
        self.mlp_train_GridLayout.addWidget(self.mlp_scaler_ComboBox, 3, 1)

        # LR 스케줄러 Patience
        self.mlp_lr_patience_Label = QLabel("LR 감소 대기")
        self.mlp_lr_patience_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_lr_patience_Label.setToolTip(
            "ReduceLROnPlateau patience\n"
            "검증 손실이 이 에폭 수 동안 개선되지 않으면 LR을 factor배로 낮춤\n"
            "값이 작을수록 LR이 빨리 감소 (기본값: 10)"
        )
        self.mlp_train_GridLayout.addWidget(self.mlp_lr_patience_Label, 9, 0)

        self.mlp_lr_patience_SpinBox = QSpinBox()
        self.mlp_lr_patience_SpinBox.setRange(1, 200)
        self.mlp_lr_patience_SpinBox.setSingleStep(5)
        self.mlp_lr_patience_SpinBox.setValue(10)
        self.mlp_lr_patience_SpinBox.setSuffix(" 에폭")
        self.mlp_train_GridLayout.addWidget(self.mlp_lr_patience_SpinBox, 9, 1)

        # LR 스케줄러 Factor
        self.mlp_lr_factor_Label = QLabel("LR 감소 비율")
        self.mlp_lr_factor_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_lr_factor_Label.setToolTip(
            "ReduceLROnPlateau factor\n"
            "LR 감소 시 현재 LR에 곱하는 비율 (0.5 = 절반)\n"
            "값이 작을수록 LR을 더 많이 낮춤 (기본값: 0.5)"
        )
        self.mlp_train_GridLayout.addWidget(self.mlp_lr_factor_Label, 8, 0)

        self.mlp_lr_factor_DoubleSpinBox = QDoubleSpinBox()
        self.mlp_lr_factor_DoubleSpinBox.setRange(0.01, 0.99)
        self.mlp_lr_factor_DoubleSpinBox.setSingleStep(0.05)
        self.mlp_lr_factor_DoubleSpinBox.setDecimals(2)
        self.mlp_lr_factor_DoubleSpinBox.setValue(0.5)
        self.mlp_lr_factor_DoubleSpinBox.setToolTip("0.5 = LR 절반 감소 (권장) / 0.1 = 90% 감소 (공격적)")
        self.mlp_train_GridLayout.addWidget(self.mlp_lr_factor_DoubleSpinBox, 8, 1)

        # 학습 버튼
        self.mlp_train_PushButton = QPushButton("🧠 MLP 학습")
        self.mlp_train_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.mlp_train_PushButton.clicked.connect(self.event_mlp_train)
        self.mlp_train_GridLayout.addWidget(self.mlp_train_PushButton, 16, 0, 1, 1)

        # 학습 중단 버튼
        self.mlp_stop_PushButton = QPushButton("⏹ 중단")
        self.mlp_stop_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.mlp_stop_PushButton.setEnabled(False)
        self.mlp_stop_PushButton.clicked.connect(self.event_mlp_stop)
        self.mlp_train_GridLayout.addWidget(self.mlp_stop_PushButton, 16, 1, 1, 1)

        # 에폭 진행률 바
        self.mlp_progress_ProgressBar = QProgressBar()
        self.mlp_progress_ProgressBar.setRange(0, 100)
        self.mlp_progress_ProgressBar.setValue(0)
        self.mlp_progress_ProgressBar.setTextVisible(True)
        self.mlp_progress_ProgressBar.setFormat("대기 중")
        self.mlp_train_GridLayout.addWidget(self.mlp_progress_ProgressBar, 17, 0, 1, 2)

        # 학습 상태 레이블
        self.mlp_status_Label = QLabel("미학습" if not self.mlp_handle.b_is_trained else "모델 로드 완료")
        self.mlp_status_Label.setStyleSheet("" + MACRO_FONT_BOLD + MACRO_BORDER_STYLE.format('none'))
        self.mlp_train_GridLayout.addWidget(self.mlp_status_Label, 18, 0, 1, 2)

        # ── 저장 모델 선택 ──────────────────────────────────────
        self.mlp_model_Label = QLabel("💾 모델 선택")
        self.mlp_model_Label.setStyleSheet(MACRO_BORDER_STYLE.format('none'))
        self.mlp_train_GridLayout.addWidget(self.mlp_model_Label, 18, 0)

        self.mlp_model_ComboBox = QComboBox()
        self.mlp_model_ComboBox.setToolTip("models/ 폴더의 버전 .pt 파일 목록")
        self.mlp_train_GridLayout.addWidget(self.mlp_model_ComboBox, 18, 1)

        self.mlp_model_refresh_PushButton = QPushButton("🔄 목록 갱신")
        self.mlp_model_refresh_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.mlp_model_refresh_PushButton.clicked.connect(self._refresh_mlp_model_list)
        self.mlp_train_GridLayout.addWidget(self.mlp_model_refresh_PushButton, 19, 0)

        self.mlp_model_load_PushButton = QPushButton("📂 모델 로드")
        self.mlp_model_load_PushButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.mlp_model_load_PushButton.clicked.connect(self.event_mlp_load_model)
        self.mlp_train_GridLayout.addWidget(self.mlp_model_load_PushButton, 19, 1)

        # 초기 목록 채우기
        self._refresh_mlp_model_list()
        # 초기 데이터 수 갱신
        self._update_mlp_data_count()

############################################################################################################ MLP Training

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
        self.all_settings_send_PushButton.setStyleSheet(BUTTON_HOVER_BG_BOLD % cfg.LINE_COLOR)
        self.all_settings_send_PushButton.clicked.connect(self.event_send_all_settings_command)
        self.led_setting_GridLayout.addWidget(self.all_settings_send_PushButton, 11, 0, 1, 3)

        # LED ON/OFF 토글 버튼 (row 12) — 독립 유지
        self.led_onoff_ToggleButton = QPushButton("� LED OFF")
        self.led_onoff_ToggleButton.setCheckable(True)
        self.led_onoff_ToggleButton.setStyleSheet("" + BUTTON_HOVER_BG % cfg.LINE_COLOR)
        self.led_onoff_ToggleButton.toggled.connect(self.event_send_led_onoff_command)
        # 초기 상태: OFF (blockSignals로 시그널 발화 방지 — UART 미연결 상태에서 명령 전송 막기)
        self.led_onoff_ToggleButton.blockSignals(True)
        self.led_onoff_ToggleButton.setChecked(False)
        self.led_onoff_ToggleButton.blockSignals(False)
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
        self.create_mlp_train_curve_tab()

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

        # ── 마지막: 저장된 설정 복원 ─────────────────────────────
        self._load_settings()

############################################################################################################
    def event_connection_status_changed(self, b_is_connected):
        """워커의 연결 상태 변경 시 UI 업데이트"""
        self.port_connect_PushButton.setEnabled(True)
        if b_is_connected:
            self.port_connect_PushButton.setText("Disconnect")
            self.connect_status_Label.setText("🟢 Connected")
            self.tp_setting_PushButton.setEnabled(True)
            # PC -> Chip 명령 송신 (UART만 — BLE는 연결 시 이미 ble_serial 설정됨)
            if self.uart_thread and hasattr(self.uart_thread, 'serial_port') and self.uart_thread.serial_port:
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

    def _on_conn_type_toggled(self, b_uart_checked: bool):
        """UART/BLE 라디오버튼 토글 — 관련 위젯 표시/숨김."""
        self.port_sel_Label.setVisible(b_uart_checked)
        self.port_sel_HBoxLayout.parentWidget()  # layout은 hide 불가, 자식 위젯 처리
        self.port_sel_ComboBox.setVisible(b_uart_checked)
        self.port_search_PushButton.setVisible(b_uart_checked)
        self.baudrate_sel_Label.setVisible(b_uart_checked)
        self.baudrate_sel_ComboBox.setVisible(b_uart_checked)
        self._ble_device_Label.setVisible(not b_uart_checked)
        self._ble_device_LineEdit.setVisible(not b_uart_checked)

    def event_port_connection(self):
        """연결/해제 토글 — UART / BLE 선택에 따라 분기."""

        if self.uart_thread and self.uart_thread.isRunning():
            # 연결 해제 (UART, BLE 공통)
            self.uart_thread.stop()
            self.port_connect_PushButton.setText("Connect")
            self.log_TextEdit.append("Disconnected.")
        elif self._uart_RadioButton.isChecked():
            # ── UART 연결 ──
            port = self.port_sel_ComboBox.currentData()
            self.log_TextEdit.append(f"Connected port {port}")
            if not port or NO_PORT_FOUND in port:
                self.log_TextEdit.append("Error: 선택된 포트가 없습니다.")
                return
            baud = self.baudrate_sel_ComboBox.currentData()
            self.uart_thread = UartWorker(port, baud)
            self.uart_thread.event_new_data.connect(self.event_update_ui)
            self.uart_thread.event_connection_status.connect(self.event_connection_status_changed)
            self.uart_thread.log_message.connect(self.log_TextEdit.append)
            self.uart_thread.start()
            self.port_connect_PushButton.setText("Connecting...")
            self.port_connect_PushButton.setEnabled(False)
        else:
            # ── BLE 연결 ──
            device_name = self._ble_device_LineEdit.text().strip() or blew.ISENSOR_BLE_NAME
            self.uart_thread = blew.BleWorker(device_name)
            self.uart_thread.event_new_data.connect(self.event_update_ui)
            self.uart_thread.event_connection_status.connect(self.event_connection_status_changed)
            self.uart_thread.log_message.connect(self.log_TextEdit.append)
            self.uart_thread.start()
            # BLE TX 어댑터를 command_sender에 연결
            self.command_sender.set_serial(self.uart_thread.ble_serial)
            self.port_connect_PushButton.setText("Connecting (BLE)...")
            self.port_connect_PushButton.setEnabled(False)

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

    def eventFilter(self, watched, event):
        """앱 레벨 이벤트 필터 — SpinBox/LineEdit 포커스와 무관하게 1/2/3 단축키 처리."""
        if event.type() == PyQt6.QtCore.QEvent.Type.KeyPress:
            focused = QApplication.focusWidget()
            # 텍스트 입력 위젯에 포커스가 없을 때만 숫자 단축키 발동
            if not isinstance(focused, (QSpinBox, QDoubleSpinBox, QLineEdit)):
                key = event.key()
                if event.modifiers() == PyQt6.QtCore.Qt.KeyboardModifier.NoModifier:
                    if key == PyQt6.QtCore.Qt.Key.Key_1:
                        self.svm_auto_bg_ToggleButton.setChecked(
                            not self.svm_auto_bg_ToggleButton.isChecked())
                        return True
                    elif key == PyQt6.QtCore.Qt.Key.Key_2:
                        self.svm_auto_human_ToggleButton.setChecked(
                            not self.svm_auto_human_ToggleButton.isChecked())
                        return True
                    elif key == PyQt6.QtCore.Qt.Key.Key_3:
                        self.event_svm_clear()
                        return True
        return super().eventFilter(watched, event)

    def event_svm_auto_bg_toggled(self, b_checked: bool):
        """배경 자동 저장 토글 상태 변경"""
        self.b_auto_save_bg = b_checked
        if b_checked:
            # 사람 자동 저장과 상호 배제
            if self.b_auto_save_human:
                self.svm_auto_human_ToggleButton.setChecked(False)
            # 프로그램 시작 시 생성된 collector 재사용 (새 파일 생성 안 함)
            self.i_fft_since_last_save = 0  # 즉시 첫 저장되도록 리셋
            self.svm_auto_bg_ToggleButton.setText("🟢 배경 자동 ON  [1]")
            self.log_TextEdit.append(f"[SVM] 배경 자동 저장 ON — {self.collector.str_csv_path} | FFT {self.i_auto_save_stride}회마다 배경으로 저장됩니다.")
        else:
            self.svm_auto_bg_ToggleButton.setText("🔴 배경 자동 OFF  [1]")
            # 버퍼에 남은 데이터 즉시 flush (20개 미만이어도 손실 방지)
            flushed = len(self.collector._write_buffer)
            self.collector.flush_write_buffer()
            self.log_TextEdit.append(f"[SVM] 배경 자동 저장 OFF — 잔여 {flushed}개 flush 완료")

    def event_svm_auto_human_toggled(self, b_checked: bool):
        """사람 자동 저장 토글 상태 변경"""
        self.b_auto_save_human = b_checked
        if b_checked:
            # 배경 자동 저장과 상호 배제
            if self.b_auto_save_bg:
                self.svm_auto_bg_ToggleButton.setChecked(False)
            # 프로그램 시작 시 생성된 collector 재사용 (새 파일 생성 안 함)
            self.i_fft_since_last_save = 0  # 즉시 첫 저장되도록 리셋
            self.svm_auto_human_ToggleButton.setText("🟢 사람 자동 ON  [2]")
            self.log_TextEdit.append(f"[SVM] 사람 자동 저장 ON — {self.collector.str_csv_path} | FFT {self.i_auto_save_stride}회마다 사람으로 저장됩니다.")
        else:
            self.svm_auto_human_ToggleButton.setText("🔴 사람 자동 OFF  [2]")
            # 버퍼에 남은 데이터 즉시 flush (20개 미만이어도 손실 방지)
            flushed = len(self.collector._write_buffer)
            self.collector.flush_write_buffer()
            self.log_TextEdit.append(f"[SVM] 사람 자동 저장 OFF — 잔여 {flushed}개 flush 완료")

    def event_svm_auto_save_interval_changed(self, i_value: int):
        """자동 저장 주기 변경 (FFT 갱신 횟수)"""
        self.i_auto_save_stride = int(i_value)

    def event_svm_save_background(self):
        """현재 FFT 결과를 배경(0) 레이블로 저장"""
        if not self.uart_thread or self.fft_features_data is None:
            ######################################################################## 경고 대화상자
            QMessageBox.warning(self, "배경 정보 저장 실패", "FFT 특징이 없습니다.\n 먼저 데이터를 수신하세요.")
            ######################################################################## 경고 대화상자
            return
        
        self.collector.save_sample(self.fft_features_data, svm.enum_label.LABEL_BACKGROUND,
                                    A_adc=self.A_adc_buffer or None,
                                    A_fft_mag=self.A_fft_magnitudes if len(self.A_fft_magnitudes) else None)
        self.collector.flush_write_buffer()  # 수동 저장: 버퍼 대기 없이 즉시 기록

        self.update_svm_label_count()
        self.log_TextEdit.append("[SVM] 배경 샘플 저장 완료")

    def event_svm_save_occupancy(self):
        """현재 FFT 결과를 사람(1) 레이블로 저장"""
        if not self.uart_thread or self.fft_features_data is None:
            ######################################################################## 경고 대화상자
            QMessageBox.warning(self, "재실 정보 저장 실패", "FFT 특징이 없습니다.\n 먼저 데이터를 수신하세요.")
            ######################################################################## 경고 대화상자
            return

        self.collector.save_sample(self.fft_features_data, svm.enum_label.LABEL_HUMAN,
                                    A_adc=self.A_adc_buffer or None,
                                    A_fft_mag=self.A_fft_magnitudes if len(self.A_fft_magnitudes) else None)
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

        self.svm_handle.A_feature_indices      = new_indices
        self.mlp_handle.feature_indices          = new_indices  # MLP도 동기화
        self._refresh_axis_combos()  # 콤보박스를 새 특징 목록에 맞게 갱신

        # 특징 변경 시 기존 학습 모델 무효화
        self.svm_handle.b_is_trained = False
        self.mlp_handle.b_is_trained = False
        self._svm_boundary_cache     = None
        self._svm_pca_boundary_cache = None
        self.svm_status_Label.setText("미학습 (특징 변경됨)")
        self.mlp_status_Label.setText("미학습 (특징 변경됨)")

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

    # ──────────────────────────────────────────────────────────────────
    # MLP 학습
    # ──────────────────────────────────────────────────────────────────
    def event_mlp_train(self):
        """현재 수집 세션 CSV로 MLP 학습 (백그라운드 스레드)"""
        self.mlp_train_PushButton.setEnabled(False)
        self.mlp_stop_PushButton.setEnabled(True)
        self.mlp_status_Label.setText("학습 중...")
        self.mlp_progress_ProgressBar.setValue(0)
        self.mlp_progress_ProgressBar.setFormat("에폭 0 / ?")

        # 학습 곡선 버퍼 초기화
        self._mlp_train_epochs.clear()
        self._mlp_train_loss.clear()
        self._mlp_train_val_loss.clear()
        self._mlp_train_train_acc.clear()
        self._mlp_train_val_acc.clear()
        self._mlp_curve_loss.setData([], [])
        self._mlp_curve_val_loss.setData([], [])
        self._mlp_curve_train_acc.setData([], [])
        self._mlp_curve_val_acc.setData([], [])

        # 학습 곡선 탭으로 전환
        for i in range(self.mlp_plot_TabWidget.count()):
            if self.mlp_plot_TabWidget.tabText(i) == "MLP 학습 곡선":
                self.mlp_plot_TabWidget.setCurrentIndex(i)
                break

        # GUI 설정값 파싱
        _hidden = [int(x) for x in self.mlp_layers_ComboBox.currentText().split('-')]
        _feat_mode = 'pc' if self.mlp_feature_mode_ComboBox.currentIndex() == 1 else 'esp32'
        _scaler_type = 'robust' if self.mlp_scaler_ComboBox.currentIndex() == 1 else 'standard'

        self._mlp_train_worker = MlpTrainWorker(
            self.mlp_handle,
            os.path.dirname(self.collector.str_csv_path),
            epochs                = self.mlp_epochs_SpinBox.value(),
            learning_rate         = self.mlp_lr_mantissa_DoubleSpinBox.value() * (10 ** self.mlp_lr_exp_SpinBox.value()),
            early_stop_patience   = self.mlp_es_SpinBox.value(),
            hidden_layers         = _hidden,
            dropout_rate          = self.mlp_dropout_SpinBox.value(),
            batch_size            = self.mlp_batch_SpinBox.value(),
            val_ratio             = float(self.mlp_val_ratio_ComboBox.currentText()),
            random_state          = self.mlp_seed_SpinBox.value(),
            stratify              = (self.mlp_stratify_ComboBox.currentIndex() == 0),
            log_interval          = self.mlp_log_interval_SpinBox.value(),
            feature_mode          = _feat_mode,
            scaler_type           = _scaler_type,
            lr_scheduler_patience = self.mlp_lr_patience_SpinBox.value(),
            lr_scheduler_factor   = self.mlp_lr_factor_DoubleSpinBox.value(),
        )
        self._mlp_train_worker.epoch_progress.connect(self._on_mlp_epoch_progress)
        self._mlp_train_worker.log_message.connect(self.log_TextEdit.append)
        self._mlp_train_worker.finished.connect(self._on_mlp_train_finished)
        self._mlp_train_worker.start()

    def event_mlp_stop(self):
        """학습 중단 버튼 클릭 — 워커에 중단 플래그 설정"""
        if hasattr(self, '_mlp_train_worker') and self._mlp_train_worker.isRunning():
            self._mlp_train_worker.stop()
            self.mlp_stop_PushButton.setEnabled(False)
            self.mlp_status_Label.setText("중단 요청 중... (현재 에폭 완료 후 중단)")

    def _on_mlp_epoch_progress(self, epoch: int, total: int,
                                loss: float, val_loss: float, train_acc: float, val_acc: float):
        """매 에폭 완료 시 진행률 바 + 학습 곡선 갱신 (메인 스레드)"""
        pct = int(epoch / total * 100)
        self.mlp_progress_ProgressBar.setValue(pct)
        self.mlp_progress_ProgressBar.setFormat(
            f"에폭 {epoch}/{total}  loss:{loss:.4f}  val_loss:{val_loss:.4f}  val:{val_acc:.1%}"
        )
        self.mlp_status_Label.setText(
            f"학습 중...  {epoch}/{total}  train:{train_acc:.1%}  val:{val_acc:.1%}"
        )

        self._mlp_train_epochs.append(epoch)
        self._mlp_train_loss.append(loss)
        self._mlp_train_val_loss.append(val_loss)
        self._mlp_train_train_acc.append(train_acc)
        self._mlp_train_val_acc.append(val_acc)

        self._mlp_curve_loss.setData(self._mlp_train_epochs, self._mlp_train_loss)
        self._mlp_curve_val_loss.setData(self._mlp_train_epochs, self._mlp_train_val_loss)
        self._mlp_curve_train_acc.setData(self._mlp_train_epochs, self._mlp_train_train_acc)
        self._mlp_curve_val_acc.setData(self._mlp_train_epochs, self._mlp_train_val_acc)

        if getattr(self, '_mlp_curve_auto_scale', True):
            self._mlp_curve_pw.enableAutoRange()

    def _on_mlp_train_finished(self, b_train_done: bool):
        """MLP 학습 완료 후 UI 업데이트 (메인 스레드)"""
        self.mlp_train_PushButton.setEnabled(True)
        self.mlp_stop_PushButton.setEnabled(False)
        _stopped = hasattr(self, '_mlp_train_worker') and self._mlp_train_worker._stop_requested
        if b_train_done:
            best_val = max(self._mlp_train_val_acc) if self._mlp_train_val_acc else 0.0
            self.mlp_progress_ProgressBar.setValue(100)
            if _stopped:
                self.mlp_progress_ProgressBar.setFormat(f"중단됨  최고 검증: {best_val:.1%}")
                self.mlp_status_Label.setText(f"학습 중단  최고 검증 정확도: {best_val:.1%}")
                self.log_TextEdit.append(f"[MLP] 학습 중단  최고 검증 정확도: {best_val:.1%}")
            else:
                self.mlp_progress_ProgressBar.setFormat(f"완료  최고 검증: {best_val:.1%}")
                self.mlp_status_Label.setText(f"학습 완료  최고 검증 정확도: {best_val:.1%}")
                self.log_TextEdit.append(f"[MLP] 학습 완료  최고 검증 정확도: {best_val:.1%}")
            # 학습 완료/중단 후 모델 목록 갱신
            self._refresh_mlp_model_list()
        else:
            self.mlp_progress_ProgressBar.setFormat("학습 실패")
            self.mlp_status_Label.setText("학습 실패 - 데이터 부족")
            QMessageBox.warning(self, "MLP 학습 실패", "데이터가 부족합니다.\n10개 이상 수집하세요.")

    # ──────────────────────────────────────────────────────────────────
    # MLP 모델 선택 / 로드
    # ──────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────
    # data_csv/ 실시간 데이터 수 카운트
    # ──────────────────────────────────────────────────────────────────
    def _count_mlp_csv_rows(self) -> tuple[int, int, int]:
        """data_csv/ 안 svm_data*.csv 파일의 전체 데이터 행 수를 반환.
        Returns: (total, n_bg, n_human)
        """
        import glob as _glob
        if not os.path.isdir(self._data_csv_dir):
            return 0, 0, 0
        csv_files = sorted(_glob.glob(os.path.join(self._data_csv_dir, "svm_data*.csv")))
        total, n_bg, n_human = 0, 0, 0
        for fpath in csv_files:
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    next(f, None)   # 헤더 건너뜀
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        total += 1
                        try:
                            label = int(float(line.rsplit(',', 1)[-1]))
                            if label == 0:
                                n_bg += 1
                            else:
                                n_human += 1
                        except ValueError:
                            pass
            except (OSError, StopIteration):
                pass
        return total, n_bg, n_human

    def _update_mlp_data_count(self, _path: str = ""):
        """mlp_data_count_Label 텍스트를 현재 CSV 데이터 수로 갱신."""
        total, n_bg, n_human = self._count_mlp_csv_rows()
        if total == 0:
            self.mlp_data_count_Label.setText("총 데이터: 0개  (CSV 없음)")
        else:
            self.mlp_data_count_Label.setText(
                f"총 데이터: {total}개  (배경 {n_bg} / 사람 {n_human})"
            )

    def _on_data_csv_dir_changed(self, path: str):
        """data_csv/ 폴더에 파일이 추가·삭제될 때 watcher 경로 재등록 후 카운트 갱신."""
        # 새로 생긴 CSV 파일을 watcher에 추가
        if os.path.isdir(self._data_csv_dir):
            for _f in os.listdir(self._data_csv_dir):
                if _f.endswith('.csv'):
                    fp = os.path.join(self._data_csv_dir, _f)
                    if fp not in self._csv_watcher.files():
                        self._csv_watcher.addPath(fp)
        self._update_mlp_data_count(path)

    def _on_data_csv_file_changed(self, path: str):
        """CSV 파일 내용이 변경될 때 카운트 갱신."""
        # 삭제된 파일은 watcher가 자동 제거하지만 재추가 시도
        if os.path.isfile(path) and path not in self._csv_watcher.files():
            self._csv_watcher.addPath(path)
        self._update_mlp_data_count(path)

    def _refresh_mlp_model_list(self):
        """models/ 폴더의 버전 모델 서브폴더 목록으로 ComboBox 갱신"""
        model_dir = self.mlp_handle.models_dir()
        if not os.path.isdir(model_dir):
            return
        # models/{stem}/{stem}.pt 구조만 수집 (stem = 폴더명)
        stems = sorted(
            [e.name for e in os.scandir(model_dir)
             if e.is_dir() and os.path.exists(os.path.join(e.path, e.name + '.pt'))],
            reverse=True  # 최신 파일명이 위에 오도록
        )
        self.mlp_model_ComboBox.clear()
        for s in stems:
            self.mlp_model_ComboBox.addItem(s)
        if stems:
            self.mlp_model_ComboBox.setCurrentIndex(0)

    def event_mlp_load_model(self):
        """선택된 .pt 파일 로드 + 저장된 학습 곡선 표시"""
        name = self.mlp_model_ComboBox.currentText()
        if not name:
            QMessageBox.information(self, "모델 로드", "선택된 모델이 없습니다.\n목록을 갱신하거나 먼저 학습하세요.")
            return
        # 서브폴더 구조: models/{stem}/{stem}.pt
        pt_path = os.path.join(self.mlp_handle.models_dir(), name, name + '.pt')
        # 이전 플랫 구조 하위 호환
        if not os.path.exists(pt_path):
            pt_path = os.path.join(self.mlp_handle.models_dir(), name)
        history = self.mlp_handle.load_model_file(pt_path)
        if not self.mlp_handle.b_is_trained:
            QMessageBox.warning(self, "모델 로드 실패", f"모델 로드에 실패했습니다.\n{name}")
            return

        # 상태 업데이트
        self.mlp_status_Label.setText(f"모델 로드: {name}")
        self.log_TextEdit.append(f"[MLP] 모델 로드 → {name}")

        # 학습 곡선 표시
        if history and history.get('epochs'):
            epochs     = history['epochs']
            loss_data  = history.get('loss', [])
            val_loss_data = history.get('val_loss', [])
            train_data = history.get('train_acc', [])
            val_data   = history.get('val_acc', [])

            # 버퍼 교체 (실시간 학습 후 덮어쓰기 방지용으로 복사)
            self._mlp_train_epochs    = list(epochs)
            self._mlp_train_loss      = list(loss_data)
            self._mlp_train_val_loss  = list(val_loss_data)
            self._mlp_train_train_acc = list(train_data)
            self._mlp_train_val_acc   = list(val_data)

            self._mlp_curve_loss.setData(epochs, loss_data)
            self._mlp_curve_val_loss.setData(epochs, val_loss_data)
            self._mlp_curve_train_acc.setData(epochs, train_data)
            self._mlp_curve_val_acc.setData(epochs, val_data)

            # 자동 스케일 ON으로 초기화하여 전체 곡선 보이게
            self._mlp_curve_auto_scale = True
            self._mlp_autoscale_Btn.blockSignals(True)
            self._mlp_autoscale_Btn.setChecked(False)
            self._mlp_autoscale_Btn.setText("🔒 자동 스케일: ON")
            self._mlp_autoscale_Btn.blockSignals(False)
            self._mlp_curve_pw.enableAutoRange()

            # 학습 곡선 탭으로 전환
            for i in range(self.mlp_plot_TabWidget.count()):
                if self.mlp_plot_TabWidget.tabText(i) == "MLP 학습 곡선":
                    self.mlp_plot_TabWidget.setCurrentIndex(i)
                    break

            best_val = max(val_data) if val_data else 0.0
            self.log_TextEdit.append(f"[MLP] 학습 이력 표시 — {len(epochs)}에폭  최고 검증: {best_val:.1%}")
        else:
            self.log_TextEdit.append("[MLP] 학습 이력 없음 (이전 학습 파일 — 재학습하면 생성됩니다)")
            self._mlp_curve_loss.setData([], [])
            self._mlp_curve_val_loss.setData([], [])
            self._mlp_curve_train_acc.setData([], [])
            self._mlp_curve_val_acc.setData([], [])

    def event_svm_clear(self):
        """CSV 파일 목록 다이얼로그 → 선택 삭제 + SVM 초기화"""

        # data_csv/ 폴더의 CSV 파일 목록 수집
        data_csv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_csv")
        csv_files = sorted(
            [f for f in os.listdir(data_csv_dir) if f.endswith(".csv")] if os.path.isdir(data_csv_dir) else []
        )

        if not csv_files:
            QMessageBox.information(self, "학습 데이터 삭제", "삭제할 CSV 파일이 없습니다.")
            return

        # ── 파일 선택 다이얼로그 ──────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle("삭제할 CSV 파일 선택")
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("삭제할 파일을 선택하세요 (복수 선택 가능):"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(4)

        checkboxes: list[QCheckBox] = []
        current_file = os.path.basename(self.collector.str_csv_path)
        for fname in csv_files:
            label = f"{fname}  ← 현재 세션" if fname == current_file else fname
            cb = QCheckBox(label)
            cb.setProperty("filename", fname)
            scroll_layout.addWidget(cb)
            checkboxes.append(cb)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # 전체 선택 / 해제 버튼 행
        btn_row = QHBoxLayout()
        btn_all   = QPushButton("전체 선택")
        btn_none  = QPushButton("전체 해제")
        btn_all.clicked.connect(lambda: [cb.setChecked(True)  for cb in checkboxes])
        btn_none.clicked.connect(lambda: [cb.setChecked(False) for cb in checkboxes])
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        layout.addLayout(btn_row)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = [cb.property("filename") for cb in checkboxes if cb.isChecked()]
        if not selected:
            return

        # ── 최종 확인 ────────────────────────────────────────────────────
        reply_QMessageBox = QMessageBox.question(
            self, "학습 데이터 삭제",
            f"선택한 {len(selected)}개 파일을 삭제하고 SVM을 초기화합니다.\n계속할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply_QMessageBox == QMessageBox.StandardButton.No:
            return

        # ── 삭제 실행 ────────────────────────────────────────────────────
        deleted_current = False
        for fname in selected:
            fpath = os.path.join(data_csv_dir, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
            if fname == current_file:
                deleted_current = True

        # 현재 세션 파일이 삭제된 경우 SVM/수집기 초기화
        if deleted_current:
            self.svm_handle = svm.SVM_Module()
            self.collector  = tdc.TrainingDataCollector()
            self._svm_boundary_cache     = None
            self._svm_pca_boundary_cache = None
            self._svm_2d_model  = None
            self._svm_2d_scaler = None
            self.svm_status_Label.setText("미학습")
            self.svm_count_Label.setText("BackGround : 0  |  Occupancy : 0")

        self.log_TextEdit.append(f"[SVM] {len(selected)}개 CSV 파일 삭제 완료: {', '.join(selected)}")

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
        # (ADC 통계는 좌측 패널 adc_stats_Label 에 표시 — 그래프 내 TextItem 제거됨)

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

        # (FFT 특징값은 좌측 패널 fft_features_Label 에 표시 — 그래프 내 주석 제거)

        # tp1_recheck_lines[graph_tab_name] = self.tp1_rck_InfiniteLine
        self.adc_fft_plot_TabWidget.addTab(target_PlotWidget, graph_plot_value[enum_graph_plot_index.STR_PLOT_NAME])


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

    def create_mlp_train_curve_tab(self):
        """MLP 학습 곡선 탭 — 에폭별 Loss / Train Acc / Val Acc 실시간 표시"""
        # 자동 스케일 상태 플래그
        self._mlp_curve_auto_scale: bool = True

        # 탭 컨테이너 (버튼 + 그래프)
        _tab_widget = QWidget()
        _tab_vbox   = QVBoxLayout(_tab_widget)
        _tab_vbox.setContentsMargins(0, 0, 0, 0)
        _tab_vbox.setSpacing(2)

        # 자동 스케일 토글 버튼
        self._mlp_autoscale_Btn = QPushButton("🔒 자동 스케일: ON")
        self._mlp_autoscale_Btn.setCheckable(True)
        self._mlp_autoscale_Btn.setChecked(False)   # False = 잠금 해제 = 자동 스케일 ON
        self._mlp_autoscale_Btn.setFixedHeight(24)
        self._mlp_autoscale_Btn.setToolTip(
            "ON: 학습 중 그래프 범위 자동 조절\n"
            "OFF: 수동 줌/팬 고정 (스크롤 후 자동으로 전환됨)"
        )
        self._mlp_autoscale_Btn.toggled.connect(self._on_mlp_autoscale_toggled)
        _tab_vbox.addWidget(self._mlp_autoscale_Btn)

        pw = pyqtgraph.PlotWidget()
        pw.setTitle("MLP 학습 곡선", color='w', size='12pt')
        pw.setLabel('bottom', 'Epoch', **{'font-size': '11pt'})
        pw.setLabel('left',   '값',    **{'font-size': '11pt'})
        pw.setYRange(0, 1.1, padding=0)
        pw.showGrid(x=True, y=True, alpha=0.3)
        pw.addLegend(offset=(10, 10))
        pw.setMenuEnabled(False)
        self._mlp_curve_pw = pw   # autoRange 호출용 참조 보관

        # 사용자가 직접 줌/팬 하면 자동 스케일 OFF
        pw.getPlotItem().getViewBox().sigRangeChangedManually.connect(
            self._on_mlp_curve_user_zoomed
        )

        self._mlp_curve_loss      = pw.plot([], [], pen=pyqtgraph.mkPen('y',       width=1), name='Train Loss')
        self._mlp_curve_val_loss   = pw.plot([], [], pen=pyqtgraph.mkPen('#ff9900', width=1), name='Val Loss')
        self._mlp_curve_train_acc  = pw.plot([], [], pen=pyqtgraph.mkPen('#44ee80', width=2), name='Train Acc')
        self._mlp_curve_val_acc    = pw.plot([], [], pen=pyqtgraph.mkPen('#ee4444', width=2), name='Val Acc')

        _tab_vbox.addWidget(pw, stretch=1)

        # 학습 곡선 데이터 버퍼
        self._mlp_train_epochs    = []
        self._mlp_train_loss      = []
        self._mlp_train_val_loss  = []
        self._mlp_train_train_acc = []
        self._mlp_train_val_acc   = []

        self.mlp_plot_TabWidget.addTab(_tab_widget, "MLP 학습 곡선")

    def _on_mlp_curve_user_zoomed(self, *_):
        """사용자가 직접 줌/팬 → 자동 스케일 OFF로 전환"""
        if self._mlp_curve_auto_scale:
            self._mlp_curve_auto_scale = False
            self._mlp_autoscale_Btn.blockSignals(True)
            self._mlp_autoscale_Btn.setChecked(True)
            self._mlp_autoscale_Btn.setText("🔓 자동 스케일: OFF")
            self._mlp_autoscale_Btn.blockSignals(False)

    def _on_mlp_autoscale_toggled(self, checked: bool):
        """버튼 클릭으로 자동 스케일 ON/OFF 전환"""
        # checked=True → OFF(잠금), checked=False → ON(자동)
        self._mlp_curve_auto_scale = not checked
        if self._mlp_curve_auto_scale:
            self._mlp_autoscale_Btn.setText("🔒 자동 스케일: ON")
            self._mlp_curve_pw.enableAutoRange()
        else:
            self._mlp_autoscale_Btn.setText("🔓 자동 스케일: OFF")

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
                ) = self.mlp_handle.mlp(
                    self.fft_features_data,
                    A_fft_mags=self.A_fft_magnitudes if len(self.A_fft_magnitudes) else None,
                    A_adc=self.A_adc_buffer if len(self.A_adc_buffer) else None,
                )
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

######## TODO : get_adc_buffer_info 수정하기

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
        # 좌측 패널 ADC 주석 레이블 갱신 (그래프 내 TextItem 제거됨)
        self.adc_stats_Label.setText(s_stats_text)

    def update_fft_graph(self, inter_Widget:QWidget):
        """FFT 그래프 업데이트
        Args:
            adc_buffer: ADC 샘플 배열
        """
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

        # 기본 FFT 통계
        s_stats_text = (
            f"Peak Freq : {self.f_fft_peak_freq:.2f} Hz\n"
            f"Peak Idx  : {self.i_fft_peak_idx}\n"
        )
        # FFT 특징값 (타입 13) — 수신된 경우 추가 표시
        if self.fft_features_data is not None:
            ft = self.fft_features_data
            s_stats_text += (
                f"\n[FFT Features]\n"
                f"Centroid      : {ft.f_centroid:.2f} Hz\n"
                f"Rolloff       : {ft.f_spectral_rolloff:.2f} Hz\n"
                f"Bandwidth     : {ft.f_spectral_bandwidth:.2f} Hz\n"
                f"Peak Freq     : {ft.f_peak_freq:.2f} Hz\n"
                f"2nd Peak Freq : {ft.f_second_peak_freq:.2f} Hz\n"
                f"Peak Count    : {ft.i_peak_count}\n"
                f"RMS           : {ft.f_rms:.4f}\n"
                f"Avg Energy    : {ft.ui32_avg_energy}\n"
                f"Peak Energy   : {ft.ui32_peak_energy}\n"
                f"Low Ratio     : {ft.f_low_ratio:.3f}\n"
                f"Mid Ratio     : {ft.f_mid_ratio:.3f}\n"
                f"High Ratio    : {ft.f_high_ratio:.3f}\n"
                f"L/H Ratio     : {ft.f_low_to_high_ratio:.3f}\n"
                f"P1/P2 Ratio   : {ft.f_peak1_to_peak2_ratio:.3f}\n"
                f"Peak/Avg E    : {ft.f_peak_to_avg_e:.3f}\n"
                f"E Variance    : {ft.f_energy_variance:.2f}\n"
                f"Kurtosis      : {ft.f_kurtosis:.3f}\n"
                f"Skewness      : {ft.f_skewness:.3f}\n"
                f"DC Ratio      : {ft.f_dc_ratio:.3f}\n"
                f"ΔPeak Freq    : {ft.f_delta_peak_freq:.2f} Hz\n"
                f"Flatness      : {ft.f_spectral_flatness:.4f}\n"
            )

        # 좌측 패널 FFT Features 레이블 갱신 (그래프 내 TextItem 제거됨)
        self.fft_features_Label.setText(s_stats_text)


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
            # 현재 프레임의 특징값을 feature_vector_from_uart로 직접 추출
            _ft_vec = svm.feature_vector_from_uart(self.svm_handle.ft) if self.svm_handle.ft is not None else None
            now_x = float(_ft_vec[int(self.svm_x_col)]) if _ft_vec is not None else 0.0
            now_y = float(_ft_vec[int(self.svm_y_col)]) if _ft_vec is not None else 0.0
            now_scatter.setData(x=[now_x], y=[now_y])

        # 2D SVM 실시간 판정 (모델이 준비된 경우)
        if self._svm_2d_model is not None and self._svm_2d_scaler is not None:
            _ft_vec2 = svm.feature_vector_from_uart(self.svm_handle.ft) if self.svm_handle.ft is not None else None
            _now_x2 = float(_ft_vec2[int(self.svm_x_col)]) if _ft_vec2 is not None else 0.0
            _now_y2 = float(_ft_vec2[int(self.svm_y_col)]) if _ft_vec2 is not None else 0.0
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
                    _ft = svm.feature_vector_from_uart(h.ft) if h.ft is not None else None
                    def _fv(col): return float(_ft[int(col)]) if _ft is not None else 0.0
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
                        f"  peak_freq  : {_fv(svm.enum_csv_col.PEAK_FREQ):.3f} Hz\n"
                        f"  centroid   : {_fv(svm.enum_csv_col.CENTROID):.3f} Hz\n"
                        f"  rms        : {_fv(svm.enum_csv_col.RMS):.4f}\n"
                        f"  low_ratio  : {_fv(svm.enum_csv_col.LOW_RATIO):.4f}\n"
                        f"  kurtosis   : {_fv(svm.enum_csv_col.KURTOSIS):.4f}\n"
                        f"  skewness   : {_fv(svm.enum_csv_col.SKEWNESS):.4f}\n"
                        f"  dc_ratio   : {_fv(svm.enum_csv_col.DC_RATIO):.4f}\n"
                        f"  sp_flat    : {_fv(svm.enum_csv_col.SPECTRAL_FLATNESS):.4f}\n"
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

    def closeEvent(self, event):
        """윈도우 종료 이벤트 — 버퍼에 남은 데이터를 CSV에 기록 후 종료"""
        self._save_settings()
        self.collector.flush_write_buffer()
        if self.uart_thread and self.uart_thread.isRunning():
            self.uart_thread.stop()
        event.accept()

    def _save_settings(self):
        """프로그램 종료 시 UI 설정을 JSON 파일로 저장"""
        _cfg = {
            'svm': {
                'feature_indices': self.svm_handle.A_feature_indices,
            },
            'mlp': {
                'epochs':       self.mlp_epochs_SpinBox.value(),
                'lr_mantissa':  self.mlp_lr_mantissa_DoubleSpinBox.value(),
                'lr_exp':       self.mlp_lr_exp_SpinBox.value(),
                'es':           self.mlp_es_SpinBox.value(),
                'layers':       self.mlp_layers_ComboBox.currentText(),
                'dropout':      str(self.mlp_dropout_SpinBox.value()),
                'batch':        self.mlp_batch_SpinBox.value(),
                'val_ratio':    self.mlp_val_ratio_ComboBox.currentText(),
                'seed':         self.mlp_seed_SpinBox.value(),
                'stratify':     self.mlp_stratify_ComboBox.currentIndex(),
                'log_interval':   self.mlp_log_interval_SpinBox.value(),
                'feature_mode':   self.mlp_feature_mode_ComboBox.currentIndex(),
                'scaler':         self.mlp_scaler_ComboBox.currentIndex(),
                'lr_patience':    self.mlp_lr_patience_SpinBox.value(),
                'lr_factor':      str(self.mlp_lr_factor_DoubleSpinBox.value()),
            },
        }
        _path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui_settings.json')
        try:
            with open(_path, 'w', encoding='utf-8') as f:
                json.dump(_cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[설정 저장 실패] {e}")

    def _load_settings(self):
        """프로그램 시작 시 JSON 파일에서 UI 설정 복원"""
        _path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui_settings.json')
        if not os.path.exists(_path):
            return
        try:
            with open(_path, encoding='utf-8') as f:
                _cfg = json.load(f)
        except Exception as e:
            print(f"[설정 불러오기 실패] {e}")
            return

        # 특징 선택 복원
        indices = _cfg.get('svm', {}).get('feature_indices')
        if indices:
            try:
                indices = [int(i) for i in indices]
                self.svm_handle.A_feature_indices = indices
                self.mlp_handle.feature_indices   = indices
                self._refresh_axis_combos()
            except Exception:
                pass

        # MLP 파라미터 복원
        mlp = _cfg.get('mlp', {})

        def _set_spin(widget, key):
            v = mlp.get(key)
            if v is not None:
                try: widget.setValue(int(v))
                except Exception: pass

        def _set_combo_text(widget, key):
            v = mlp.get(key)
            if v is not None:
                idx = widget.findText(str(v))
                if idx >= 0:
                    widget.setCurrentIndex(idx)

        def _set_combo_idx(widget, key):
            v = mlp.get(key)
            if v is not None:
                try: widget.setCurrentIndex(int(v))
                except Exception: pass

        def _set_double_spin(widget, key):
            v = mlp.get(key)
            if v is not None:
                try: widget.setValue(float(v))
                except Exception: pass

        _set_spin(self.mlp_epochs_SpinBox,                   'epochs')
        _set_double_spin(self.mlp_lr_mantissa_DoubleSpinBox, 'lr_mantissa')
        _set_spin(self.mlp_lr_exp_SpinBox,                   'lr_exp')
        _set_spin(self.mlp_es_SpinBox,               'es')
        _set_combo_text(self.mlp_layers_ComboBox,    'layers')
        _set_double_spin(self.mlp_dropout_SpinBox,   'dropout')
        _set_spin(self.mlp_batch_SpinBox,            'batch')
        _set_combo_text(self.mlp_val_ratio_ComboBox, 'val_ratio')
        _set_spin(self.mlp_seed_SpinBox,             'seed')
        _set_combo_idx(self.mlp_stratify_ComboBox,   'stratify')
        _set_spin(self.mlp_log_interval_SpinBox,     'log_interval')
        _set_combo_idx(self.mlp_feature_mode_ComboBox,'feature_mode')
        _set_combo_idx(self.mlp_scaler_ComboBox,     'scaler')
        _set_spin(self.mlp_lr_patience_SpinBox,      'lr_patience')
        _set_double_spin(self.mlp_lr_factor_DoubleSpinBox, 'lr_factor')


    def update_svm_label_count(self):
        self.svm_count_Label.setText(f"BackGround: {self.collector.i_bg_count}  |  Occupancy: {self.collector.i_human_count}")

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
                if self.fft_features_data is not None:
                    # 동일 FFT 프레임 판별: avg_energy + peak_energy + peak_freq 조합 키
                    _cur_key = (
                        self.fft_features_data.ui32_avg_energy,
                        self.fft_features_data.ui32_peak_energy,
                        self.fft_features_data.f_peak_freq,
                    )
                    if _cur_key != self._last_auto_saved_fft_key:
                        self.i_fft_since_last_save += 1
                        if self.i_fft_since_last_save >= self.i_auto_save_stride:
                            self.i_fft_since_last_save = 0
                            self._last_auto_saved_fft_key = _cur_key
                            if self.b_auto_save_bg:
                                self.collector.save_sample(self.fft_features_data, svm.enum_label.LABEL_BACKGROUND,
                                                           A_adc=self.A_adc_buffer or None,
                                                           A_fft_mag=self.A_fft_magnitudes if len(self.A_fft_magnitudes) else None)
                            else:
                                self.collector.save_sample(self.fft_features_data, svm.enum_label.LABEL_HUMAN,
                                                           A_adc=self.A_adc_buffer or None,
                                                           A_fft_mag=self.A_fft_magnitudes if len(self.A_fft_magnitudes) else None)
                            self.update_svm_label_count()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
