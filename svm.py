# 샘플 300개, 샘플링 레이트가 100Hz
# 빈 번호	주파수 범위	의미
# 빈 0 (mag_0)	0 Hz	DC 성분
# 빈 1 (mag_1)	~0.33 Hz	0.33Hz 신호 세기
# 빈 2 (mag_2)	~0.67 Hz	0.67Hz 신호 세기
# ...	...	...
# 빈 150 (mag_150)	~50 Hz	50Hz 신호 세기


# ############################# COPILOT EDIT START (svm.py 신규 생성)
import enum
import numpy
import csv
import os
from sklearn.svm       import SVC
from sklearn.preprocessing import StandardScaler

class enum_label(enum.IntEnum):
    LABEL_BACKGROUND = 0
    LABEL_HUMAN = LABEL_BACKGROUND + 1


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
        self.f_low_energy  = 0.0
        self.f_mid_energy  = 0.0
        self.f_high_energy = 0.0
        self.f_rms         = 0.0

        self.i_bg_count    = 0
        self.i_human_count = 0

        self.scaler:StandardScaler  = StandardScaler()
        self.svm_model:SVC          = SVC(kernel='rbf', C=1.0, gamma='scale', probability=True) # probability=True = 거리값을 확률로 변환 -> 내부적으로는 Platt Scaling 이라는 방법




        self.i_label        = enum_label.LABEL_BACKGROUND
        self.A_probabilty   = []
        self.f_confidence   = 0.0


        
        self.b_is_trained:bool      = False

        self.A_train_features:list  = []   # 학습 특징 벡터 목록
        self.A_train_labels:list    = []   # 학습 레이블 목록


    def svm(self, inter_A_freq, inter_A_mag):
        self.A_frequencies  = inter_A_freq
        self.A_magnitudes   = inter_A_mag
        
        self.extract_features()     # 특징 추출
        self.predict()              # 예측

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

        A_features = numpy.array([
            self.f_peak_freq
            , self.f_peak_mag
            , self.f_avg_mag
            , self.f_std_mag
            , self.f_centroid
            , self.f_low_energy  
            , self.f_mid_energy  
            , self.f_high_energy 
            , self.f_rms
            , input_i_label         # 이것도 float으로 저장됨
            ])

        """특징 벡터 + 레이블을 CSV에 한 줄 추가

        Args:
            A_feature_vector : 특징 벡터 (161개)
            i_label          : LABEL_BACKGROUND(0) or LABEL_HUMAN(1)
            str_csv_path     : 저장할 CSV 파일 경로
        """
        b_write_header = not os.path.exists(self.str_svm_csv_path)
        with open(self.str_svm_csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if b_write_header:
                # 헤더 생성
                A_header = [f"magnitudes_{i}" for i in range(len(self.A_magnitudes))]
                
                # self.i_peak_idx
                # , self.f_peak_freq
                # , self.f_peak_mag
                # , self.f_avg_mag
                # , self.f_std_mag
                # , self.f_centroid
                # , self.f_low_energy  
                # , self.f_mid_energy  
                # , self.f_high_energy 
                # , self.f_rms

                # centroid (X) vs mid_energy (Y): 사람 존재 시 중주파대에 에너지가 몰리고, 무게중심도 이동하므로 분리가 잘 됨
                # rms (X) vs peak_mag (Y): 전체 에너지 세기 vs 최대 피크 세기
                # low_energy (X) vs mid_energy (Y): 저/중주파 에너지 비율로 분류
                
                A_header += [
                    "peak_freq"
                    , "peak_mag"
                    , "avg_mag"
                    , "std_mag"
                    , "centroid"
                    , "low_energy"
                    , "mid_energy"
                    , "high_energy"
                    , "rms"
                ]
                writer.writerow(A_header)
            writer.writerow(list(self.A_magnitudes) + list(A_features))

    # def get_label_counts(self, str_csv_path:str) -> tuple:
    def update_label_counts(self) -> tuple:
        """CSV 파일에서 클래스별 샘플 수 반환

        Returns:
            (i_background_count, i_human_count)
        """
        # i_bg_count    = 0
        # i_human_count = 0

        if not os.path.exists(self.str_svm_csv_path):
            return self.i_bg_count, self.i_human_count

        with open(self.str_svm_csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # 헤더 스킵
            for row in reader:
                if len(row) == 0:
                    continue
                A_labels = int(float(row[-1]))    # 끝 항목
                # if label == enum_label.LABEL_BACKGROUND:
                #     self.i_bg_count += 1
                # elif label == enum_label.LABEL_HUMAN:
                #     self.i_human_count += 1
                self.i_bg_count    = A_labels.count(enum_label.LABEL_BACKGROUND)
                self.i_human_count = A_labels.count(enum_label.LABEL_HUMAN)

        # return self.i_bg_count, self.i_human_count

    # # -------------------------------------------------------
    # # 학습
    # # -------------------------------------------------------
    # def train(self, str_csv_path:str) -> bool:
    def train(self) -> bool:
        """CSV 파일로 SVM 학습

        Returns:
            True: 학습 성공 / False: 데이터 부족
        """

        if not os.path.exists(self.str_svm_csv_path):
            return False

        A_features = []
        A_labels = []
        with open(self.str_svm_csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # 헤더 스킵
            for row in reader:
                if len(row) < 2: # 2차원 그래프라서?
                    continue
                A_features.append([float(v) for v in row[:-1]])    # (학습 입력, 160개 float)
                A_labels.append(int(float(row[-1])))             # (정답 레이블)

        if len(A_features) < 10:
            return False

        i_bg_count    = A_labels.count(enum_label.LABEL_BACKGROUND)
        i_human_count = A_labels.count(enum_label.LABEL_HUMAN)
        if i_bg_count == 0 or i_human_count == 0:
            return False

        X = numpy.array(A_features)
        Y = numpy.array(A_labels)

        X_scaled = self.scaler.fit_transform(X) # 표준화(정규화)
        self.svm_model.fit(X_scaled, Y)         # 경계면 학습       
        # w1 곱하기 rms + w2 곱하기 centroid + ... + w160 곱하기 마지막특징 + b 라는 수식 하나를 계산
        # 두 그룹 사이의 마진이 최대가 되는 가중치 조합을 수학적으로 찾아내고, 그게 최종 w1~w160
        # 두 클래스 사이의 마진(Margin, 간격)을 최대화
        # 서포트 벡터(Support Vectors): 경계면과 가장 가까이 있는 데이터 포인트들을 말합니다.
        # 마진: 이 서포트 벡터들과 경계면 사이의 거리입니다. 이 거리가 멀수록(두꺼울수록) 새로운 데이터가 들어왔을 때 더 정확하게 분류할 확률이 높다고 판단합니다.
        # 라그랑주 승수법(Lagrange Multipliers) 기법 사용

        # SMO(Sequential Minimal Optimization): scikit-learn의 SVM은 내부적으로 libsvm 라이브러리를 사용하는데, 여기서 주로 SMO 알고리즘이 돌아갑니다. 수천 개의 데이터를 한꺼번에 계산하기 힘드니, 한 번에 2개씩 골라서 최적의 가중치를 조금씩 업데이트하며 전체적인 최적값을 찾아가는 방식입니다.

        print(self.svm_model.coef_) # 학습된 가중치

        self.b_is_trained = True
        
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

        if not self.b_is_trained:
            # return LABEL_BACKGROUND, 0.0
            self.i_label        = enum_label.LABEL_BACKGROUND
            self.f_confidence   = 0.0
            return

        A_features = numpy.array([
            self.i_peak_idx
            , self.f_peak_freq
            , self.f_peak_mag
            , self.f_avg_mag
            , self.f_std_mag
            , self.f_centroid
            , self.f_low_energy  
            , self.f_mid_energy  
            , self.f_high_energy 
            , self.f_rms
            ])
        
        # predict 와 predict_proba 가 이 2차원 구조를 기대하기 때문에 [A_features] 로 일부러 감싼 것
        A_scaler_features   = self.scaler.transform([A_features])                   # 정규화(표준화) / 모든 특징값을 "평균 0, 표준편차 1" 기준으로 변환합니다.
        # array([[ 0.23, -1.45,  2.11, -0.33,  0.87, -0.12,  1.54, -0.78,  0.45,  0.99]])
        self.i_label      = int(self.svm_model.predict(A_scaler_features)[0])     # 결과를 항상 배열로 감싸서 반환 [[0]] or [[1]]
        self.A_probabilty = self.svm_model.predict_proba(A_scaler_features)[0]    # 결과를 항상 배열로 감싸서 반환 [[0.87, 0.13]]
        self.f_confidence = float(self.A_probabilty[self.i_label])

        # return i_label, f_confidence

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