"""
학습 데이터 수집 모듈

FftFeaturesData → CSV 파일 저장을 담당하는 공용 수집기.
SVM, MLP 등 어떤 모델에서도 동일한 CSV를 사용할 수 있도록
모델에 종속되지 않는 독립 모듈로 분리.
"""

import csv
import datetime
import glob
import os
import sys

# svm.py 는 AI/svm/ 에 위치
_AI_DIR  = os.path.dirname(os.path.abspath(__file__))
_SVM_DIR = os.path.join(_AI_DIR, 'svm')
if _SVM_DIR not in sys.path:
    sys.path.insert(0, _SVM_DIR)

import svm  # enum_label, feature_vector_from_uart, I_FEATURES_COUNT


_CSV_HEADER_FEATURES = [
    "spectral_rolloff", "spectral_bandwidth", "peak_count", "mid_ratio",
    "low_to_high_ratio", "second_peak_freq", "kurtosis", "centroid",
    "peak_freq", "low_ratio", "rms", "avg_energy", "peak_energy",
    "energy_variance", "peak_to_avg_e", "high_ratio",
    "peak1_to_peak2_ratio", "skewness",
    "dc_ratio", "delta_peak_freq", "spectral_flatness",
]


def _build_header(n_adc: int, n_fft: int) -> list:
    """특징 21열 + adc_N열 + fft_M열 + label 로 구성된 헤더를 반환."""
    h = list(_CSV_HEADER_FEATURES)
    h += [f"adc_{i}" for i in range(n_adc)]
    h += [f"fft_{i}" for i in range(n_fft)]
    h.append("label")
    return h


# data_csv/ 폴더 안에 타임스탬프 기반 파일명을 생성하는 헬퍼
def make_session_csv_path(base_dir: str = "data_csv",
                          i_window: int = 0,
                          i_stride: int = 0,
                          i_interval: int = 0) -> str:
    """자동 수집 토글 ON 시 호출 — 수집 조건을 파일명에 포함하여 반환.

    Args:
        i_window:   Window Size (ADC 샘플 수)
        i_stride:   FFT Stride (샘플 단위)
        i_interval: 저장 주기 (FFT 갱신 횟수)

    Returns:
        예) data_csv/svm_data_20260428_112250_W256_S32_I1.csv
    """
    os.makedirs(base_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    meta = f"_W{i_window}_S{i_stride}_I{i_interval}" if (i_window or i_stride or i_interval) else ""
    return os.path.join(base_dir, f"svm_data_{ts}{meta}.csv")


class TrainingDataCollector:
    """FFT 특징값 + 레이블을 CSV에 누적 저장하는 수집기.

    SVM / MLP 등 학습 파이프라인에 공통으로 사용됨.
    """

    def __init__(self, str_csv_path: str = None):
        # 경로 미지정 시 data_csv/ 폴더에 타임스탬프 파일 자동 생성
        if str_csv_path is None:
            str_csv_path = make_session_csv_path()
        self.str_csv_path: str    = str_csv_path

        self.i_bg_count: int      = 0
        self.i_human_count: int   = 0

        self._I_FLUSH_EVERY: int  = 20    # 이 개수마다 CSV 에 한꺼번에 기록
        self._write_buffer: list  = []
        self._b_need_header: bool = not os.path.exists(str_csv_path)

        # ADC / FFT 배열 크기 (첫 샘플 수신 시 확정)
        self._i_adc_len: int = 0
        self._i_fft_len: int = 0

        # 앱 시작 시 기존 CSV 에서 카운터 초기화
        self._load_counts_from_csv()

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------

    def _load_counts_from_csv(self):
        """기존 CSV 파일에서 BG / Human 개수를 메모리에 로드."""
        if not os.path.exists(self.str_csv_path):
            return
        try:
            with open(self.str_csv_path, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)  # 헤더 스킵
                for row in reader:
                    if not row:
                        continue
                    label = int(float(row[-1]))
                    if label == svm.enum_label.LABEL_BACKGROUND:
                        self.i_bg_count += 1
                    elif label == svm.enum_label.LABEL_HUMAN:
                        self.i_human_count += 1
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 공개 인터페이스
    # ------------------------------------------------------------------

    def save_sample(self, ft, i_label: int,
                    A_adc=None, A_fft_mag=None):
        """FftFeaturesData + 레이블(+ 선택적 원시 배열)을 버퍼에 추가하고 필요 시 CSV 에 flush.

        Args:
            ft        : FftFeaturesData (None 이면 무시)
            i_label   : enum_label.LABEL_BACKGROUND (0) or LABEL_HUMAN (1)
            A_adc     : ADC 샘플 배열 (list/ndarray, 예: 256개)  — CNN 학습용
            A_fft_mag : FFT magnitude 배열 (list/ndarray, 예: 129개) — CNN 학습용
        """
        if ft is None:
            return

        A_adc_list = list(A_adc)     if A_adc     is not None else []
        A_fft_list = list(A_fft_mag) if A_fft_mag is not None else []

        # 배열 크기 최초 확정
        if A_adc_list and self._i_adc_len == 0:
            self._i_adc_len = len(A_adc_list)
        if A_fft_list and self._i_fft_len == 0:
            self._i_fft_len = len(A_fft_list)

        A_row = list(svm.feature_vector_from_uart(ft)) + A_adc_list + A_fft_list + [float(i_label)]

        if i_label == svm.enum_label.LABEL_BACKGROUND:
            self.i_bg_count += 1
        else:
            self.i_human_count += 1

        self._write_buffer.append(A_row)

        if len(self._write_buffer) >= self._I_FLUSH_EVERY:
            self.flush_write_buffer()

    def flush_write_buffer(self):
        """버퍼에 쌓인 행들을 CSV 에 한 번에 기록."""
        if not self._write_buffer:
            return

        b_write_header = self._b_need_header
        with open(self.str_csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if b_write_header:
                writer.writerow(_build_header(self._i_adc_len, self._i_fft_len))
                self._b_need_header = False
            writer.writerows(self._write_buffer)

        self._write_buffer.clear()
