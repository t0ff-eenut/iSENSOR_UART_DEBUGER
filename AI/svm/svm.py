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

class enum_label(enum.IntEnum):
    LABEL_BACKGROUND = 0
    LABEL_HUMAN = LABEL_BACKGROUND + 1


# CSV 컬럼 인덱스 (ESP32 UART FftFeaturesData 순서, 0~17)
# | 0  | spectral_rolloff      | f_spectral_rolloff
# | 1  | spectral_bandwidth    | f_spectral_bandwidth
# | 2  | peak_count            | i_peak_count
# | 3  | mid_ratio             | f_mid_ratio
# | 4  | low_to_high_ratio     | f_low_to_high_ratio
# | 5  | second_peak_freq      | f_second_peak_freq
# | 6  | kurtosis              | f_kurtosis
# | 7  | centroid              | f_centroid
# | 8  | peak_freq             | f_peak_freq
# | 9  | low_ratio             | f_low_ratio
# | 10 | rms                   | f_rms
# | 11 | avg_energy            | ui32_avg_energy
# | 12 | peak_energy           | ui32_peak_energy
# | 13 | energy_variance       | f_energy_variance
# | 14 | peak_to_avg_e         | f_peak_to_avg_e
# | 15 | high_ratio            | f_high_ratio
# | 16 | peak1_to_peak2_ratio  | f_peak1_to_peak2_ratio
# | 17 | skewness              | f_skewness
# | 18 | dc_ratio              | f_dc_ratio
# | 19 | delta_peak_freq       | f_delta_peak_freq
# | 20 | spectral_flatness     | f_spectral_flatness
# | 21 (마지막)             | label
I_FEATURES_COUNT: int = 21  # FftFeaturesData 필드 수


def feature_vector_from_uart(ft) -> numpy.ndarray:
    """FftFeaturesData → 21차원 numpy 배열 (enum_csv_col 순서와 동일).

    SVM, MLP, TrainingDataCollector 등에서 공통 사용하는 모듈 레벨 함수.
    """
    return numpy.array([
        ft.f_spectral_rolloff,          # 0  SPECTRAL_ROLLOFF
        ft.f_spectral_bandwidth,        # 1  SPECTRAL_BANDWIDTH
        float(ft.i_peak_count),         # 2  PEAK_COUNT
        ft.f_mid_ratio,                 # 3  MID_RATIO
        ft.f_low_to_high_ratio,         # 4  LOW_TO_HIGH_RATIO
        ft.f_second_peak_freq,          # 5  SECOND_PEAK_FREQ
        ft.f_kurtosis,                  # 6  KURTOSIS
        ft.f_centroid,                  # 7  CENTROID
        ft.f_peak_freq,                 # 8  PEAK_FREQ
        ft.f_low_ratio,                 # 9  LOW_RATIO
        ft.f_rms,                       # 10 RMS
        float(ft.ui32_avg_energy),      # 11 AVG_ENERGY
        float(ft.ui32_peak_energy),     # 12 PEAK_ENERGY
        ft.f_energy_variance,           # 13 ENERGY_VARIANCE
        ft.f_peak_to_avg_e,             # 14 PEAK_TO_AVG_E
        ft.f_high_ratio,                # 15 HIGH_RATIO
        ft.f_peak1_to_peak2_ratio,      # 16 PEAK1_TO_PEAK2_RATIO
        ft.f_skewness,                  # 17 SKEWNESS
        ft.f_dc_ratio,                  # 18 DC_RATIO
        ft.f_delta_peak_freq,           # 19 DELTA_PEAK_FREQ
        ft.f_spectral_flatness,         # 20 SPECTRAL_FLATNESS
    ], dtype=float)


class enum_csv_col(enum.IntEnum):
    SPECTRAL_ROLLOFF      = 0
    SPECTRAL_BANDWIDTH    = 1
    PEAK_COUNT            = 2
    MID_RATIO             = 3
    LOW_TO_HIGH_RATIO     = 4
    SECOND_PEAK_FREQ      = 5
    KURTOSIS              = 6
    CENTROID              = 7
    PEAK_FREQ             = 8
    LOW_RATIO             = 9
    RMS                   = 10
    AVG_ENERGY            = 11
    PEAK_ENERGY           = 12
    ENERGY_VARIANCE       = 13
    PEAK_TO_AVG_E         = 14
    HIGH_RATIO            = 15
    PEAK1_TO_PEAK2_RATIO  = 16
    SKEWNESS              = 17
    DC_RATIO              = 18
    DELTA_PEAK_FREQ       = 19
    SPECTRAL_FLATNESS     = 20


class SVM_Module():

    def __init__(self):

        # 최신 UART 수신 FftFeaturesData
        self.ft = None

        self.scaler:StandardScaler    = StandardScaler()
        self.svm_model:SVC            = SVC(kernel='rbf', C=1.0, gamma='scale', probability=True)

        self.pca:PCA                      = None   # 학습 후 생성
        self.A_pca_train_2d:numpy.ndarray = None   # shape: (N, 2) — 훈련 데이터 PCA 투영

        self.i_label        = enum_label.LABEL_BACKGROUND
        self.A_probabilty   = []
        self.f_confidence   = 0.0

        # 학습/예측에 사용할 컬럼 인덱스 (0~20: UART FftFeaturesData 21개 특징)
        # 기본값: PIR 인체 감지 권장 10개
        #   LOW_TO_HIGH_RATIO(4), KURTOSIS(6), CENTROID(7), PEAK_FREQ(8), LOW_RATIO(9),
        #   RMS(10), AVG_ENERGY(11), PEAK_TO_AVG_E(14), PEAK1_TO_PEAK2_RATIO(16), SKEWNESS(17)
        self.A_feature_indices: list = sorted([
            int(enum_csv_col.LOW_TO_HIGH_RATIO),    # 4
            int(enum_csv_col.KURTOSIS),             # 6
            int(enum_csv_col.CENTROID),             # 7
            int(enum_csv_col.PEAK_FREQ),            # 8
            int(enum_csv_col.LOW_RATIO),            # 9
            int(enum_csv_col.RMS),                  # 10
            int(enum_csv_col.AVG_ENERGY),           # 11
            int(enum_csv_col.PEAK_TO_AVG_E),        # 14
            int(enum_csv_col.PEAK1_TO_PEAK2_RATIO), # 16
            int(enum_csv_col.SKEWNESS),             # 17
        ])

        self.b_is_trained:bool      = False

        self.A_train_features:list  = []   # 학습 특징 벡터 목록
        self.A_train_labels:list    = []   # 학습 레이블 목록

    def svm(self, input_ft):
        """UART 수신 FftFeaturesData로 특징 저장 및 예측 수행.

        Args:
            input_ft: FftFeaturesData — None이면 무시
        """
        if input_ft is None:
            return (self.A_probabilty, self.i_label, self.f_confidence)
        self.ft = input_ft
        if self.b_is_trained:
            self.predict()          # 예측 (학습된 경우에만)

        return (
            self.A_probabilty
            , self.i_label
            , self.f_confidence
            )

    # -------------------------------------------------------
    # 학습
    # -------------------------------------------------------
    def train(self, str_csv_path: str = "data_csv") -> bool:
        """CSV 파일 또는 폴더로 SVM 학습.

        Args:
            str_csv_path: CSV 파일 경로 또는 svm_data*.csv 가 들어있는 폴더 경로.
                          폴더를 전달하면 내부의 svm_data*.csv 를 모두 병합해서 학습.

        Returns:
            True: 학습 성공 / False: 데이터 부족
        """
        import glob

        # 폴더이면 svm_data*.csv 전부 수집, 파일이면 단일 목록
        if os.path.isdir(str_csv_path):
            csv_files = sorted(glob.glob(os.path.join(str_csv_path, "svm_data*.csv")))
        elif os.path.isfile(str_csv_path):
            csv_files = [str_csv_path]
        else:
            return False

        if not csv_files:
            return False

        A_features      = []   # 마스킹된 특징 (SVM 학습용)
        A_full_features = []   # 전체 21개 행 (그래프 표시용)
        A_labels = []
        for csv_file in csv_files:
            with open(csv_file, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)  # 헤더 스킵
                for row in reader:
                    if len(row) < 2:
                        continue
                    A_full_row = [float(v) for v in row[:-1]]        # 21개 특징 전체
                    A_features.append([A_full_row[i] for i in self.A_feature_indices])
                    A_full_features.append(A_full_row)
                    A_labels.append(int(float(row[-1])))

        if len(A_features) < 10:
            return False

        i_bg_count    = A_labels.count(enum_label.LABEL_BACKGROUND)
        i_human_count = A_labels.count(enum_label.LABEL_HUMAN)
        if i_bg_count == 0 or i_human_count == 0:
            return False

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
        self.A_train_features = A_full_features  # 전체 18개 행 보관 → 그래프에서 원본 컬럼 인덱스로 접근
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

        if not self.b_is_trained or self.ft is None or not hasattr(self.scaler, 'mean_') or not isinstance(self.scaler.mean_, numpy.ndarray):
            self.i_label        = enum_label.LABEL_BACKGROUND
            self.f_confidence   = 0.0
            return

        # UART 수신 FftFeaturesData → 18차원 특징벡터 → 선택된 인덱스만 추출
        A_full     = feature_vector_from_uart(self.ft)
        A_features = A_full[self.A_feature_indices].reshape(1, -1)

        # predict 와 predict_proba 가 이 2차원 구조를 기대하기 때문에 reshape(1,-1) 사용
        A_scaler_features   = self.scaler.transform(A_features)
        self.i_label      = int(self.svm_model.predict(A_scaler_features)[0])
        self.A_probabilty = self.svm_model.predict_proba(A_scaler_features)[0]
        self.f_confidence = float(self.A_probabilty[self.i_label])

    def get_pca_now(self) -> tuple:
        """현재 프레임 특징벡터를 PCA 2D 공간으로 변환

        Returns:
            (pc1, pc2) — 현재 위치의 PCA 좌표. 미학습 시 (0.0, 0.0)
        """
        if not self.b_is_trained or self.pca is None or self.ft is None or not hasattr(self.scaler, 'mean_') or not isinstance(self.scaler.mean_, numpy.ndarray):
            return 0.0, 0.0
        A_full     = feature_vector_from_uart(self.ft)
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