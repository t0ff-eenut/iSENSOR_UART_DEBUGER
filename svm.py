# 샘플 256개, 샘플링 레이트가 100Hz
# 빈 번호	주파수 범위	의미
# 빈 0 (mag_0)	0 Hz	DC 성분
# 빈 1 (mag_1)	~0.33 Hz	0.33Hz 신호 세기
# 빈 2 (mag_2)	~0.67 Hz	0.67Hz 신호 세기
# ...	...	...
# 빈 150 (mag_150)	~50 Hz	50Hz 신호 세기


# 지금 특징 중 rms, low_energy, centroid 3개만으로도 꽤 잘 구분 가능
# 추가하면 좋은 건 DC 성분과 저주파 에너지 비율
# magnitudes 129개는 오히려 차원이 너무 높아서 소량 데이터에서 overfitting 위험 있음

# ############################# COPILOT EDIT START (svm.py 신규 생성)
import enum
import numpy
import csv
import os
from sklearn.svm       import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

import config as cfg

class enum_label(enum.IntEnum):
    LABEL_BACKGROUND = 0
    LABEL_HUMAN = LABEL_BACKGROUND + 1


# CSV 컬럼 인덱스
# | 0 ~ I_MAGNITUDES_COUNT-1 | magnitudes_0 ~ magnitudes_N  |
# | I_MAGNITUDES_COUNT + 0   | peak_freq                    |
# | I_MAGNITUDES_COUNT + 1   | peak_mag                     |
# | ...                      | 통계 특징들                      |
# | -1 (마지막)              | label                        |
# rfft(WINDOW_SIZE) 결과 크기 = WINDOW_SIZE // 2 + 1
# config.py 의 WINDOW_SIZE 값에서 자동 계산 — 직접 수정하지 말 것
I_MAGNITUDES_COUNT:int = cfg.WINDOW_SIZE // 2 + 1
class enum_csv_col(enum.IntEnum):
    PEAK_FREQ        = I_MAGNITUDES_COUNT + 0   # 129
    PEAK_MAG         = I_MAGNITUDES_COUNT + 1   # 130
    AVG_MAG          = I_MAGNITUDES_COUNT + 2   # 131
    STD_MAG          = I_MAGNITUDES_COUNT + 3   # 132
    CENTROID         = I_MAGNITUDES_COUNT + 4   # 133
    LOW_ENERGY       = I_MAGNITUDES_COUNT + 5   # 134
    MID_ENERGY       = I_MAGNITUDES_COUNT + 6   # 135
    HIGH_ENERGY      = I_MAGNITUDES_COUNT + 7   # 136
    RMS              = I_MAGNITUDES_COUNT + 8   # 137
    LOW_RATIO        = I_MAGNITUDES_COUNT + 9   # 138  저주파 에너지 비율
    SPECTRAL_ENTROPY = I_MAGNITUDES_COUNT + 10  # 139  스펙트럼 엔트로피
    PEAK_TO_MEAN     = I_MAGNITUDES_COUNT + 11  # 140  피크-투-평균 비율


class SVM_Module():

    def __init__(self):

        self.str_svm_csv_path:str          = "svm_data.csv"
        self.str_svm_waveform_csv_path:str = "svm_waveforms.csv"

        self.A_frequencies = []
        self.A_magnitudes  = []
        
        self.i_peak_idx     = 0
        self.f_peak_freq    = 0.0   # 1. 피크 주파수 (DC 제외
        self.f_peak_mag     = 0.0   # 2. 피크 진폭
        self.f_avg_mag      = 0.0   # 3. 전체 평균 진폭 (DC 제외)
        self.f_std_mag      = 0.0   # 4. 진폭 표준편차
        self.f_total_energy = 0.0   
        self.f_centroid     = 0.0   # 5. 스펙트럼 무게중심 주파수

        self.f_1st_freq_cut = 5.0
        self.f_2nd_freq_cut = 10.0
        self.f_3st_freq_cut = 15.0
        self.A_b_low_mask  = []
        self.A_b_mid_mask  = []
        self.A_b_high_mask = []
        self.f_low_energy       = 0.0
        self.f_mid_energy       = 0.0
        self.f_high_energy      = 0.0
        self.f_rms              = 0.0
        self.f_low_ratio        = 0.0  # 저주파 에너지 비율  low / (low+mid+high)
        self.f_spectral_entropy = 0.0  # 스펙트럼 엔트로피  -Σ p·log(p)
        self.f_peak_to_mean     = 0.0  # 피크-투-평균 비율  peak_mag / avg_mag

        self.i_bg_count    = 0
        self.i_human_count = 0

        self.scaler:StandardScaler  = StandardScaler()
        self.svm_model:SVC          = SVC(kernel='rbf', C=1.0, gamma='scale', probability=True)

        self.pca:PCA                    = None   # 학습 후 생성
        self.A_pca_train_2d:numpy.ndarray = None # shape: (N, 2) — 훈련 데이터 PCA 투영




        self.i_label        = enum_label.LABEL_BACKGROUND
        self.A_probabilty   = []
        self.f_confidence   = 0.0

        # 학습/예측에 사용할 컬럼 인덱스 (0~150: magnitudes, 151~162: 통계+파생 특징)
        # 기본값: 권장 세트 24개
        #   - 저주파 스펙트럼 빈 1~15 (0.3~5Hz, 15개)
        #   - 핵심 통계 9개: peak_freq, peak_mag, std_mag, centroid,
        #                   low_energy, mid_energy, rms, low_ratio, spectral_entropy, peak_to_mean
        _A_low_spec = list(range(1, 16))  # 빈 1~15
        _A_stat     = [
            int(enum_csv_col.PEAK_FREQ),         # 129
            int(enum_csv_col.PEAK_MAG),          # 130
            int(enum_csv_col.STD_MAG),           # 132  (avg_mag 제외)
            int(enum_csv_col.CENTROID),          # 133
            int(enum_csv_col.LOW_ENERGY),        # 134
            int(enum_csv_col.MID_ENERGY),        # 135  (high_energy 제외)
            int(enum_csv_col.RMS),               # 137
            int(enum_csv_col.LOW_RATIO),         # 138
            int(enum_csv_col.SPECTRAL_ENTROPY),  # 139
            int(enum_csv_col.PEAK_TO_MEAN),      # 162
        ]
        self.A_feature_indices: list = sorted(_A_low_spec + _A_stat)  # 25개 (저주파 15 + 통계 10)

        self.b_is_trained:bool      = False

        self.A_train_features:list  = []   # 학습 특징 벡터 목록
        self.A_train_labels:list    = []   # 학습 레이블 목록

        # 배치 쓰기 버퍼
        self._I_FLUSH_EVERY:int     = 20   # 20개 모이면 한 번에 CSV flush
        self._write_buffer:list     = []   # (row_list,) 형태로 쌓아 둠
        self._b_need_header:bool    = not os.path.exists(self.str_svm_csv_path)

        # 앱 시작 시 기존 CSV에서 카운터 초기화
        self._load_counts_from_csv()


    def _load_counts_from_csv(self):
        """앱 시작 시 기존 CSV 파일에서 BG/Human 개수를 메모리에 로드"""
        if not os.path.exists(self.str_svm_csv_path):
            return
        try:
            with open(self.str_svm_csv_path, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)  # 헤더 스킵
                for row in reader:
                    if not row:
                        continue
                    label = int(float(row[-1]))
                    if label == enum_label.LABEL_BACKGROUND:
                        self.i_bg_count += 1
                    elif label == enum_label.LABEL_HUMAN:
                        self.i_human_count += 1
        except Exception:
            pass

    def svm(self, inter_A_freq, inter_A_mag):
        self.A_frequencies  = inter_A_freq
        self.A_magnitudes   = inter_A_mag
        
        self.extract_features()     # 특징 추출
        if self.b_is_trained:
            self.predict()          # 예측 (학습된 경우에만)

        return (
            self.A_probabilty
            , self.i_label
            , self.f_confidence
            )

    # -------------------------------------------------------
    # 특징 추출
    # -------------------------------------------------------
    # def extract_features(self, A_magnitudes_raw:numpy.ndarray, A_frequencies:numpy.ndarray) -> numpy.ndarray:
    def extract_features(self) -> numpy.ndarray:
        """FFT 결과에서 SVM 특징 벡터 추출 (게인 적용 전 raw magnitudes 사용)

        Args:
            A_magnitudes_raw : 게인 미적용 정규화된 진폭 배열 (151개)
            A_frequencies    : 주파수 배열 Hz (151개)

        Returns:
            numpy.ndarray: 특징 벡터 (전체 스펙트럼 151개 + 통계 10개 = 161개)
        """


        # --- feature 10개 ---
        self.i_peak_idx  = numpy.argmax(self.A_magnitudes[1:]) + 1
        self.f_peak_freq = self.A_frequencies[self.i_peak_idx]       # 1. 피크 주파수 (DC 제외)  X축
        self.f_peak_mag  = self.A_magnitudes[self.i_peak_idx]        # 2. 피크 진폭              Y축
        self.f_avg_mag   = numpy.mean(self.A_magnitudes[1:])         # 3. 전체 평균 진폭 (DC 제외)
        self.f_std_mag   = numpy.std(self.A_magnitudes[1:])          # 4. 진폭 표준편차

        self.f_total_energy = numpy.sum(self.A_magnitudes[1:])          
        if self.f_total_energy > 0:
            # 결과 배열=[f1 ⋅ m1, f2 ⋅ m2 , f3 ⋅ m3]​
            self.f_centroid  = numpy.sum(self.A_frequencies[1:] * self.A_magnitudes[1:]) / self.f_total_energy       # 5. 스펙트럼 무게중심 주파수
        else:
            self.f_centroid  = 0.0

        # 6~8. 대역별 에너지 합
        self.A_b_low_mask  = (self.A_frequencies >= 0.0) & (self.A_frequencies <  self.f_1st_freq_cut)                 # 저주파 0~5Hz
        self.A_b_mid_mask  = (self.A_frequencies >= self.f_1st_freq_cut) & (self.A_frequencies < self.f_2nd_freq_cut)  # 중주파 5~20Hz
        self.A_b_high_mask = (self.A_frequencies >= self.f_2nd_freq_cut)                                               # 고주파 20~50Hz
        self.f_low_energy  = numpy.sum(self.A_magnitudes[self.A_b_low_mask])
        self.f_mid_energy  = numpy.sum(self.A_magnitudes[self.A_b_mid_mask])
        self.f_high_energy = numpy.sum(self.A_magnitudes[self.A_b_high_mask])

        # print(f"svm.py | extract_features() | f_total_energy : {self.f_total_energy} == f_low_energy + f_mid_energy + f_high_energy : {self.f_low_energy + self.f_mid_energy + self.f_high_energy}")

        # 9. RMS 에너지
        # RMS : "전체 에너지의 평균적인 크기" — 각 진폭을 제곱해서 평균낸 뒤 루트. → 신호가 전반적으로 얼마나 강한가
        # STD : "평균으로부터 얼마나 흩어져 있는가" — 평균을 빼고 제곱해서 평균낸 뒤 루트.→ 신호가 전반적으로 얼마나 들쭉날쭉한가
        # RMS^2 = STD^2 + 평균^2
        # self.f_rms = numpy.sqrt(numpy.mean(self.A_magnitudes[1:] ** 2))
        self.f_rms = numpy.sqrt(self.f_std_mag**2 + self.f_avg_mag**2) # 두 에너지의 합 = 전체 에너지

        # 10. 저주파 에너지 비율 — 사람이면 0.6↑, 배경이면 0.3↓ / 스케일 불변
        _band_total = self.f_low_energy + self.f_mid_energy + self.f_high_energy
        self.f_low_ratio = self.f_low_energy / _band_total if _band_total > 0 else 0.0

        # 11. 스펙트럼 엔트로피 — 사람이면 에너지 집중(낮음), 배경이면 고르게 분산(높음)
        _A_mag_dc_excl = self.A_magnitudes[1:]
        _mag_sum = numpy.sum(_A_mag_dc_excl)
        if _mag_sum > 0:
            _A_prob = _A_mag_dc_excl / _mag_sum                         # 확률 분포
            _A_prob_nz = _A_prob[_A_prob > 0]                           # 0 제거 (log 연산 안전)
            self.f_spectral_entropy = float(-numpy.sum(_A_prob_nz * numpy.log(_A_prob_nz)))
        else:
            self.f_spectral_entropy = 0.0

        # 12. 피크-투-평균 비율 — 사람이면 특정 주파수가 뾰족하게 솟음(큼), 배경이면 고름(낮음)
        self.f_peak_to_mean = self.f_peak_mag / self.f_avg_mag if self.f_avg_mag > 0 else 0.0

        # 10. 임계값 이상 피크 개수 (평균 + 2*표준편차 초과)
        # self.f_threshold  = self.f_avg_mag + 2.0 * self.f_std_mag
        # self.i_peak_count = int(numpy.sum(self.A_magnitudes[1:] > self.f_threshold))

        # A_stat_features = numpy.array([
        #     f_peak_freq,
        #     f_peak_mag,
        #     f_mean_mag,
        #     f_std_mag,
        #     f_centroid,
        #     f_low_energy,
        #     f_mid_energy,
        #     f_high_energy,
        #     f_rms,
        #     float(i_peak_count),
        # ])

        # # 전체 스펙트럼(151개) + 통계(10개) = 161개
        # A_feature_vector = numpy.concatenate([self.A_magnitudes, A_stat_features])




        # return A_feature_vector
        # return (
        #     self.i_peak_idx
        #     , self.f_peak_freq
        #     , self.f_peak_mag
        #     , self.f_avg_mag
        #     , self.f_std_mag
        #     , self.f_centroid
        #     , self.f_low_energy  
        #     , self.f_mid_energy  
        #     , self.f_high_energy 
        #     , self.f_rms
        #     )


    # -------------------------------------------------------
    # 데이터 수집 (CSV 저장)
    # -------------------------------------------------------
    # def save_sample(self, A_feature_vector:numpy.ndarray, i_label:int, str_csv_path:str):
    def save_sample(self, input_i_label:int):

        A_row = list(self.A_magnitudes) + [
            self.f_peak_freq
            , self.f_peak_mag
            , self.f_avg_mag
            , self.f_std_mag
            , self.f_centroid
            , self.f_low_energy  
            , self.f_mid_energy  
            , self.f_high_energy 
            , self.f_rms
            , self.f_low_ratio        # 160
            , self.f_spectral_entropy # 161
            , self.f_peak_to_mean     # 162
            , float(input_i_label)
        ]

        # 메모리 카운터 즉시 증가 (CSV 읽기 불필요)
        if input_i_label == enum_label.LABEL_BACKGROUND:
            self.i_bg_count += 1
        else:
            self.i_human_count += 1

        self._write_buffer.append(A_row)

        # 버퍼가 가득 찼을 때만 파일 flush
        if len(self._write_buffer) >= self._I_FLUSH_EVERY:
            self.flush_write_buffer()

    def flush_write_buffer(self):
        """버퍼에 쌓인 행들을 CSV에 한 번에 씁니다."""
        if not self._write_buffer:
            return

        b_write_header = self._b_need_header
        with open(self.str_svm_csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if b_write_header:
                A_header = [f"magnitudes_{i}" for i in range(I_MAGNITUDES_COUNT)]
                A_header += [
                    "peak_freq", "peak_mag", "avg_mag", "std_mag",
                    "centroid", "low_energy", "mid_energy", "high_energy", "rms",
                    "low_ratio", "spectral_entropy", "peak_to_mean",
                    "label"
                ]
                writer.writerow(A_header)
                self._b_need_header = False
            writer.writerows(self._write_buffer)

        self._write_buffer.clear()

    # def get_label_counts(self, str_csv_path:str) -> tuple:
    def update_label_counts(self) -> tuple:
        """CSV 파일에서 클래스별 샘플 수 반환

        Returns:
            (i_background_count, i_human_count)
        """
        # 메모리 카운터를 그대로 사용 — CSV 재읽기 없음
        # (save_sample 호출 시 즉시 증가되므로 항상 정확)
        pass  # i_bg_count / i_human_count 는 save_sample 에서 직접 관리

    # # -------------------------------------------------------
    # # 학습
    # # -------------------------------------------------------
    def train(self) -> bool:
        """CSV 파일로 SVM 학습

        Returns:
            True: 학습 성공 / False: 데이터 부족
        """

        if not os.path.exists(self.str_svm_csv_path):
            return False

        A_features      = []   # 마스킹된 특징 (SVM 학습용)
        A_full_features = []   # 전체 163개 행 (그래프 표시용)
        A_labels = []
        with open(self.str_svm_csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # 헤더 스킵
            for row in reader:
                if len(row) < 2: # 2차원 그래프라서?
                    continue
                A_full_row = [float(v) for v in row[:-1]]        # 163개 전체
                A_features.append([A_full_row[i] for i in self.A_feature_indices])  # 선택된 특징만
                A_full_features.append(A_full_row)               # 전체 행 보존 (그래프용)
                A_labels.append(int(float(row[-1])))             # (정답 레이블)

        if len(A_features) < 10:
            return False

        i_bg_count    = A_labels.count(enum_label.LABEL_BACKGROUND)
        i_human_count = A_labels.count(enum_label.LABEL_HUMAN)
        if i_bg_count == 0 or i_human_count == 0:
            return False

        # 메모리 카운터를 CSV 실제 데이터 기준으로 동기화 (앱 재시작 후에도 정확하게 표시)
        self.i_bg_count    = i_bg_count
        self.i_human_count = i_human_count

        X = numpy.array(A_features, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        Y = numpy.array(A_labels)

        # scaler/model 을 새로 생성해 이전 학습 상태 완전 초기화
        self.scaler    = StandardScaler()
        self.svm_model = SVC(kernel='rbf', C=1.0, gamma='scale', probability=True)
        X_scaled = self.scaler.fit_transform(X)
        self.svm_model.fit(X_scaled, Y)         # 경계면 학습

        # PCA 2차원 투영 (표준화된 데이터 기준)
        self.pca = PCA(n_components=2)
        self.A_pca_train_2d = self.pca.fit_transform(X_scaled)  # shape: (N, 2)

        self.b_is_trained = True
        self.A_train_features = A_full_features  # 전체 163개 행 보관 → 그래프에서 원본 컬럼 인덱스로 접근
        self.A_train_labels   = A_labels
        
        return True
    

    # -------------------------------------------------------
    # 예측
    # -------------------------------------------------------
    # 전체 스펙트럼(151개) + 통계(10개) = 161개

    # def predict(self, A_feature_vector:numpy.ndarray) -> tuple:
    def predict(self) -> tuple:
        """실시간 분류 예측

        Args:
            A_feature_vector: 특징 벡터 (161개)

        Returns:
            (i_label, f_confidence)
            i_label      : LABEL_BACKGROUND(0) or LABEL_HUMAN(1)
            f_confidence : 신뢰도 0.0~1.0
        """

        if not self.b_is_trained or not hasattr(self.scaler, 'mean_') or not isinstance(self.scaler.mean_, numpy.ndarray):
            # return LABEL_BACKGROUND, 0.0
            self.i_label        = enum_label.LABEL_BACKGROUND
            self.f_confidence   = 0.0
            return

        A_stat_features = numpy.array([
            self.f_peak_freq
            , self.f_peak_mag
            , self.f_avg_mag
            , self.f_std_mag
            , self.f_centroid
            , self.f_low_energy  
            , self.f_mid_energy  
            , self.f_high_energy 
            , self.f_rms
            , self.f_low_ratio
            , self.f_spectral_entropy
            , self.f_peak_to_mean
            ])
        # 학습 시와 동일한 구조: magnitudes(151개) + stat(12개) = 163개 → 선택된 인덱스만 추출
        A_full = numpy.concatenate([numpy.asarray(self.A_magnitudes, dtype=float), A_stat_features])
        A_features = A_full[self.A_feature_indices].reshape(1, -1)

        # predict 와 predict_proba 가 이 2차원 구조를 기대하기 때문에 reshape(1,-1) 사용
        A_scaler_features   = self.scaler.transform(A_features)                   # 정규화(표준화) / 모든 특징값을 "평균 0, 표준편차 1" 기준으로 변환합니다.
        # array([[ 0.23, -1.45,  2.11, -0.33,  0.87, -0.12,  1.54, -0.78,  0.45,  0.99]])
        self.i_label      = int(self.svm_model.predict(A_scaler_features)[0])     # 결과를 항상 배열로 감싸서 반환 [[0]] or [[1]]
        self.A_probabilty = self.svm_model.predict_proba(A_scaler_features)[0]    # 결과를 항상 배열로 감싸서 반환 [[0.87, 0.13]]
        self.f_confidence = float(self.A_probabilty[self.i_label])

        # return i_label, f_confidence

    def get_pca_now(self) -> tuple:
        """현재 프레임 특징벡터를 PCA 2D 공간으로 변환

        Returns:
            (pc1, pc2) — 현재 위치의 PCA 좌표. 미학습 시 (0.0, 0.0)
        """
        if not self.b_is_trained or self.pca is None or not hasattr(self.scaler, 'mean_') or not isinstance(self.scaler.mean_, numpy.ndarray):
            return 0.0, 0.0
        A_stat_features = numpy.array([
            self.f_peak_freq, self.f_peak_mag, self.f_avg_mag, self.f_std_mag,
            self.f_centroid, self.f_low_energy, self.f_mid_energy, self.f_high_energy, self.f_rms,
            self.f_low_ratio, self.f_spectral_entropy, self.f_peak_to_mean
        ])
        A_full     = numpy.concatenate([numpy.asarray(self.A_magnitudes, dtype=float), A_stat_features])
        A_features = A_full[self.A_feature_indices].reshape(1, -1)
        A_scaled   = self.scaler.transform(A_features)
        pca_2d     = self.pca.transform(A_scaled)  # shape: (1, 2)
        return float(pca_2d[0, 0]), float(pca_2d[0, 1])

    # # -------------------------------------------------------
    # # 파형 데이터 저장/로드 (SVM 학습 CSV와 분리된 별도 CSV)
    # # -------------------------------------------------------
    # def save_waveform(self, A_adc_raw:list, i_label:int, str_waveform_csv_path:str):
    #     """원시 ADC 파형(N개) + 레이블을 별도 CSV에 한 줄 추가

    #     Args:
    #         A_adc_raw             : 원시 ADC 샘플 목록 (예: 300개)
    #         i_label               : LABEL_BACKGROUND(0) or LABEL_HUMAN(1)
    #         str_waveform_csv_path : 파형 전용 CSV 파일 경로
    #     """
    #     b_write_header = not os.path.exists(str_waveform_csv_path)
    #     with open(str_waveform_csv_path, 'a', newline='') as f:
    #         writer = csv.writer(f)
    #         if b_write_header:
    #             A_header = [f"raw_{i}" for i in range(len(A_adc_raw))] + ["label"]
    #             writer.writerow(A_header)
    #         writer.writerow(list(A_adc_raw) + [i_label])

#     def load_waveforms(self, str_waveform_csv_path:str) -> list:
#         """파형 CSV에서 (numpy_array, label) 목록 반환

#         Returns:
#             list of (numpy.ndarray, int) — (ADC 파형 배열, 레이블)
#         """
#         if not os.path.exists(str_waveform_csv_path):
#             return []
#         A_result = []
#         with open(str_waveform_csv_path, 'r') as f:
#             reader = csv.reader(f)
#             next(reader, None)  # 헤더 스킵
#             for row in reader:
#                 if len(row) < 2:
#                     continue
#                 i_label = int(row[-1])
#                 A_raw   = numpy.array([float(v) for v in row[:-1]])
#                 A_result.append((A_raw, i_label))
#         return A_result
# # ############################# COPILOT EDIT END



















# class PurePythonSVM:
#     def __init__(self, learning_rate=0.001, lambda_param=0.01, n_iterations=1000):
#         self.lr = learning_rate          # 학습률 (η)
#         self.lambda_param = lambda_param  # 규제 강도 (λ, 마진 넓이 조절)
#         self.n_iterations = n_iterations  # 반복 횟수
#         self.w = None                    # 가중치 리스트
#         self.b = 0.0                     # 편향 (Bias)

#     def fit(self, X, Y):
#         # 1. 초기화: 가중치(w)를 특성 개수만큼 0.0으로 설정
#         n_features = len(X[0])
#         self.w = [0.0] * n_features
#         self.b = 0.0

#         # 2. 라벨 변환: 혹시 0과 1로 들어왔다면 SVM 수식에 맞게 -1과 1로 변환
#         y_transformed = [1 if y_val > 0 else -1 for y_val in Y]

#         # 3. 반복 학습 (Gradient Descent)
#         for _ in range(self.n_iterations):
#             for idx, x_i in enumerate(X):
#                 # 수식 계산: w * x + b (순수 파이썬으로 내적 구현)
#                 linear_output = sum(w_j * x_ij for w_j, x_ij in zip(self.w, x_i)) + self.b
                
#                 # 조건 확인: y_i * (w * x + b) >= 1
#                 condition = y_transformed[idx] * linear_output >= 1

#                 if condition:
#                     # 상황 A: 올바르게 분류되었고 마진 밖에 있을 때 (가중치만 감소)
#                     self.w = [
#                         w_j - self.lr * (2 * self.lambda_param * w_j) 
#                         for w_j in self.w
#                     ]
#                 else:
#                     # 상황 B: 잘못 분류되었거나 마진 안에 있을 때 (가중치 및 편향 업데이트)
#                     self.w = [
#                         w_j - self.lr * (2 * self.lambda_param * w_j - y_transformed[idx] * x_ij) 
#                         for w_j, x_ij in zip(self.w, x_i)
#                     ]
#                     self.b += self.lr * y_transformed[idx]

#     def predict(self, X):
#         # 학습된 모델로 예측 수행
#         predictions = []
#         for x_i in X:
#             linear_output = sum(w_j * x_ij for w_j, x_ij in zip(self.w, x_i)) + self.b
#             # 0보다 크면 1번 클래스, 작으면 -1번 클래스
#             predictions.append(1 if linear_output >= 0 else -1)
#         return predictions
    

#     ################################################################## 테스트용

#     # 2개의 특성을 가진 4개의 데이터 (선형 분리가 가능한 예시)
#     X_train = [
#         [1.0, 2.0],  # 클래스 1
#         [2.0, 3.0],  # 클래스 1
#         [5.0, 1.0],  # 클래스 -1
#         [6.0, 2.0]   # 클래스 -1
#     ]
#     Y_train = [1, 1, -1, -1]

#     # 모델 생성 및 학습
#     svm = PurePythonSVM(learning_rate=0.01, n_iterations=1000)
#     svm.fit(X_train, Y_train)

#     # 학습된 결과 확인
#     print("최종 가중치(w):", svm.w)
#     print("최종 편향(b):", svm.b)

#     # 새로운 데이터 예측
#     test_data = [[1.5, 2.5], [5.5, 1.5]]
#     print("예측 결과:", svm.predict(test_data))
#     # 출력 예상: [1, -1]