# ############################# COPILOT EDIT START (svm.py 신규 생성)
import numpy
import csv
import os
from sklearn.svm       import SVC
from sklearn.preprocessing import StandardScaler

# 레이블 정의
LABEL_BACKGROUND = 0  # 배경 (사람 없음)
LABEL_HUMAN      = 1  # 사람 감지

class SVM_Module():

    def __init__(self):
        self.scaler:StandardScaler  = StandardScaler()
        self.svm_model:SVC          = SVC(kernel='rbf', C=1.0, gamma='scale', probability=True)
        self.b_is_trained:bool      = False

        self.A_train_features:list  = []   # 학습 특징 벡터 목록
        self.A_train_labels:list    = []   # 학습 레이블 목록

    # -------------------------------------------------------
    # 특징 추출
    # -------------------------------------------------------
    def extract_features(self, A_magnitudes_raw:numpy.ndarray, A_frequencies:numpy.ndarray) -> numpy.ndarray:
        """FFT 결과에서 SVM 특징 벡터 추출 (게인 적용 전 raw magnitudes 사용)

        Args:
            A_magnitudes_raw : 게인 미적용 정규화된 진폭 배열 (151개)
            A_frequencies    : 주파수 배열 Hz (151개)

        Returns:
            numpy.ndarray: 특징 벡터 (전체 스펙트럼 151개 + 통계 10개 = 161개)
        """
        mags = A_magnitudes_raw
        freqs = A_frequencies

        # --- 통계 특징 10개 ---
        # 1. 피크 주파수 (DC 제외)
        i_peak_idx      = numpy.argmax(mags[1:]) + 1
        f_peak_freq     = freqs[i_peak_idx]

        # 2. 피크 진폭
        f_peak_mag      = mags[i_peak_idx]

        # 3. 전체 평균 진폭 (DC 제외)
        f_mean_mag      = numpy.mean(mags[1:])

        # 4. 진폭 표준편차
        f_std_mag       = numpy.std(mags[1:])

        # 5. 스펙트럼 무게중심 주파수
        f_total_energy  = numpy.sum(mags[1:])
        if f_total_energy > 0:
            f_centroid  = numpy.sum(freqs[1:] * mags[1:]) / f_total_energy
        else:
            f_centroid  = 0.0

        # 6~8. 대역별 에너지 합
        low_mask        = (freqs >= 0.0) & (freqs <  5.0)   # 저주파 0~5Hz
        mid_mask        = (freqs >= 5.0) & (freqs < 20.0)   # 중주파 5~20Hz
        high_mask       = (freqs >= 20.0)                    # 고주파 20~50Hz
        f_low_energy    = numpy.sum(mags[low_mask])
        f_mid_energy    = numpy.sum(mags[mid_mask])
        f_high_energy   = numpy.sum(mags[high_mask])

        # 9. RMS 에너지
        f_rms           = numpy.sqrt(numpy.mean(mags[1:] ** 2))

        # 10. 임계값 이상 피크 개수 (평균 + 2*표준편차 초과)
        f_threshold     = f_mean_mag + 2.0 * f_std_mag
        i_peak_count    = int(numpy.sum(mags[1:] > f_threshold))

        A_stat_features = numpy.array([
            f_peak_freq,
            f_peak_mag,
            f_mean_mag,
            f_std_mag,
            f_centroid,
            f_low_energy,
            f_mid_energy,
            f_high_energy,
            f_rms,
            float(i_peak_count),
        ])

        # 전체 스펙트럼(151개) + 통계(10개) = 161개
        A_feature_vector = numpy.concatenate([mags, A_stat_features])
        return A_feature_vector

    # -------------------------------------------------------
    # 데이터 수집 (CSV 저장)
    # -------------------------------------------------------
    def save_sample(self, A_feature_vector:numpy.ndarray, i_label:int, str_csv_path:str):
        """특징 벡터 + 레이블을 CSV에 한 줄 추가

        Args:
            A_feature_vector : 특징 벡터 (161개)
            i_label          : LABEL_BACKGROUND(0) or LABEL_HUMAN(1)
            str_csv_path     : 저장할 CSV 파일 경로
        """
        b_write_header = not os.path.exists(str_csv_path)

        with open(str_csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if b_write_header:
                # 헤더 생성
                A_header = [f"mag_{i}" for i in range(151)]
                A_header += [
                    "peak_freq", "peak_mag", "mean_mag", "std_mag",
                    "centroid", "low_energy", "mid_energy", "high_energy",
                    "rms", "peak_count", "label"
                ]
                writer.writerow(A_header)
            writer.writerow(list(A_feature_vector) + [i_label])

    def get_sample_counts(self, str_csv_path:str) -> tuple:
        """CSV 파일에서 클래스별 샘플 수 반환

        Returns:
            (i_background_count, i_human_count)
        """
        if not os.path.exists(str_csv_path):
            return 0, 0

        i_bg    = 0
        i_human = 0
        with open(str_csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # 헤더 스킵
            for row in reader:
                if len(row) == 0:
                    continue
                label = int(row[-1])
                if label == LABEL_BACKGROUND:
                    i_bg += 1
                elif label == LABEL_HUMAN:
                    i_human += 1
        return i_bg, i_human

    # -------------------------------------------------------
    # 학습
    # -------------------------------------------------------
    def train(self, str_csv_path:str) -> bool:
        """CSV 파일로 SVM 학습

        Returns:
            True: 학습 성공 / False: 데이터 부족
        """
        if not os.path.exists(str_csv_path):
            return False

        A_X = []
        A_y = []
        with open(str_csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # 헤더 스킵
            for row in reader:
                if len(row) < 2:
                    continue
                A_X.append([float(v) for v in row[:-1]])
                A_y.append(int(row[-1]))

        if len(A_X) < 10:
            return False

        i_bg_count    = A_y.count(LABEL_BACKGROUND)
        i_human_count = A_y.count(LABEL_HUMAN)
        if i_bg_count == 0 or i_human_count == 0:
            return False

        X = numpy.array(A_X)
        y = numpy.array(A_y)

        X_scaled = self.scaler.fit_transform(X)
        self.svm_model.fit(X_scaled, y)
        self.b_is_trained = True
        return True

    # -------------------------------------------------------
    # 예측
    # -------------------------------------------------------
    def predict(self, A_feature_vector:numpy.ndarray) -> tuple:
        """실시간 분류 예측

        Args:
            A_feature_vector: 특징 벡터 (161개)

        Returns:
            (i_label, f_confidence)
            i_label      : LABEL_BACKGROUND(0) or LABEL_HUMAN(1)
            f_confidence : 신뢰도 0.0~1.0
        """
        if not self.b_is_trained:
            return LABEL_BACKGROUND, 0.0

        X = self.scaler.transform([A_feature_vector])
        i_label         = int(self.svm_model.predict(X)[0])
        A_proba         = self.svm_model.predict_proba(X)[0]
        f_confidence    = float(A_proba[i_label])
        return i_label, f_confidence

    # -------------------------------------------------------
    # 파형 데이터 저장/로드 (SVM 학습 CSV와 분리된 별도 CSV)
    # -------------------------------------------------------
    def save_waveform(self, A_adc_raw:list, i_label:int, str_waveform_csv_path:str):
        """원시 ADC 파형(N개) + 레이블을 별도 CSV에 한 줄 추가

        Args:
            A_adc_raw             : 원시 ADC 샘플 목록 (예: 300개)
            i_label               : LABEL_BACKGROUND(0) or LABEL_HUMAN(1)
            str_waveform_csv_path : 파형 전용 CSV 파일 경로
        """
        b_write_header = not os.path.exists(str_waveform_csv_path)
        with open(str_waveform_csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if b_write_header:
                A_header = [f"raw_{i}" for i in range(len(A_adc_raw))] + ["label"]
                writer.writerow(A_header)
            writer.writerow(list(A_adc_raw) + [i_label])

    def load_waveforms(self, str_waveform_csv_path:str) -> list:
        """파형 CSV에서 (numpy_array, label) 목록 반환

        Returns:
            list of (numpy.ndarray, int) — (ADC 파형 배열, 레이블)
        """
        if not os.path.exists(str_waveform_csv_path):
            return []
        A_result = []
        with open(str_waveform_csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # 헤더 스킵
            for row in reader:
                if len(row) < 2:
                    continue
                i_label = int(row[-1])
                A_raw   = numpy.array([float(v) for v in row[:-1]])
                A_result.append((A_raw, i_label))
        return A_result
# ############################# COPILOT EDIT END
