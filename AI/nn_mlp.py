"""
╔══════════════════════════════════════════════════════════════════╗
║  MLP (다층 퍼셉트론) 기반 재실 판단 딥러닝 모델                 ║
╚══════════════════════════════════════════════════════════════════╝

[ 개념 ]
  퍼셉트론(뉴런)을 여러 층으로 쌓아 복잡한 패턴을 학습하는 신경망.
  SVM과 동일한 24개 특징을 입력으로 받으므로 직접 비교가 가능합니다.

[ 구조 ]
  입력(24) → [FC→BN→ReLU→Dropout] → [FC→ReLU] → 출력(2)
                 은닉층 1(64)             은닉층 2(32)

[ 사용법 ]
  ① 직접 실행 (학습):
       python nn_mlp.py

  ② 코드에서 import:
       from nn_mlp import MLP_Module
       mlp = MLP_Module()
       mlp.train()   # svm_data.csv 로드 후 학습
       prob, label, conf = mlp.mlp(A_frequencies, A_magnitudes)

[ 필요 패키지 ]
  pip install torch torchvision
  (sklearn, numpy 는 기존 SVM에서 이미 설치됨)
"""

import os
import csv
import pickle
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# svm.py의 enum_label, A_feature_indices 재사용
import svm


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  하이퍼파라미터 (튜닝이 필요하면 여기서 수정)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EPOCHS        = 100   # 전체 데이터를 몇 번 반복 학습할지 (많을수록 정확 but 느림)
BATCH_SIZE    = 16    # 한 번에 처리할 샘플 수 (데이터가 적으면 8 또는 4로 줄임)
LEARNING_RATE = 1e-3  # 학습률: 가중치를 얼마나 크게 업데이트할지 (0.001)
DROPOUT_RATE  = 0.3   # 드롭아웃: 뉴런의 30%를 랜덤하게 끄기 → 과적합 방지
HIDDEN_SIZE_1 = 64    # 1번째 은닉층 뉴런 수
HIDDEN_SIZE_2 = 32    # 2번째 은닉층 뉴런 수
VAL_RATIO     = 0.2   # 검증 데이터 비율 (전체의 20%)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ① 데이터셋 클래스 — PyTorch DataLoader가 미니배치를 만들기 위해 필요
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class OccupancyDataset(Dataset):
    """
    CSV에서 읽은 numpy 배열을 PyTorch 텐서로 감싸는 컨테이너.

    DataLoader에 넣으면 자동으로 미니배치(묶음)를 만들어 줍니다.
    예: 100개 샘플 / BATCH_SIZE=16 → 7번 미니배치 반복
    """

    def __init__(self, X: np.ndarray, y: np.ndarray):
        # numpy → PyTorch 텐서 변환
        # float32: GPU/CPU 모두 호환되는 기본 부동소수점 타입
        # long   : CrossEntropyLoss가 요구하는 정수 레이블 타입
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self) -> int:
        """샘플 총 개수 반환 (DataLoader가 내부적으로 호출)"""
        return len(self.y)

    def __getitem__(self, idx: int):
        """인덱스 idx에 해당하는 (특징벡터, 레이블) 반환"""
        return self.X[idx], self.y[idx]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ② MLP 모델 구조 정의
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class OccupancyMLP(nn.Module):
    """
    재실 판단을 위한 MLP (다층 퍼셉트론) 신경망.

    ┌─────────────────────────────────────────────┐
    │ 입력층  : 24개 FFT 특징                     │
    │                  ↓                          │
    │ 은닉층1 : Linear(24→64)                     │
    │           BatchNorm1d(64) ─ 정규화          │
    │           ReLU            ─ 활성화          │
    │           Dropout(30%)    ─ 과적합 방지      │
    │                  ↓                          │
    │ 은닉층2 : Linear(64→32)                     │
    │           ReLU                              │
    │                  ↓                          │
    │ 출력층  : Linear(32→2)                      │
    │           [BACKGROUND 점수, HUMAN 점수]     │
    └─────────────────────────────────────────────┘

    용어 설명:
      Linear     : 행렬 곱 계산 (y = Wx + b), 완전연결층
      BatchNorm  : 배치 내 값을 평균0/분산1로 정규화 → 학습 안정화
      ReLU       : max(0, x) — 음수 제거, 비선형성 부여
      Dropout    : 학습 시 일부 뉴런 랜덤 OFF → 과적합 방지
                   (추론/평가 시에는 자동으로 전부 ON)
    """

    def __init__(self, input_size: int):
        super().__init__()

        # nn.Sequential: 레이어를 순서대로 쌓는 컨테이너
        self.net = nn.Sequential(

            # ── 은닉층 1 ─────────────────────────────────
            nn.Linear(input_size, HIDDEN_SIZE_1),   # 입력 → 64
            nn.BatchNorm1d(HIDDEN_SIZE_1),           # 배치 정규화
            nn.ReLU(),                               # 활성화 함수
            nn.Dropout(p=DROPOUT_RATE),              # 드롭아웃

            # ── 은닉층 2 ─────────────────────────────────
            nn.Linear(HIDDEN_SIZE_1, HIDDEN_SIZE_2), # 64 → 32
            nn.ReLU(),

            # ── 출력층 ───────────────────────────────────
            # 2개의 점수(logit)를 출력 → 나중에 softmax로 확률 변환
            # CrossEntropyLoss를 쓸 때는 softmax를 여기서 넣지 않음!
            nn.Linear(HIDDEN_SIZE_2, 2),             # 32 → 2 (BG / Human)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        순전파 (Forward Pass):
        입력 x를 받아 각 클래스의 점수(logit)를 반환합니다.
        학습 엔진이 자동으로 이 함수를 호출합니다.
        """
        return self.net(x)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ③ SVM_Module과 동일한 API를 가진 래퍼 클래스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class MLP_Module:
    """
    MLP 모델을 SVM_Module과 동일한 방식으로 사용하는 래퍼.

    debugger_start.py에서 svm_handle 대신 mlp_handle로 교체 가능하도록
    동일한 속성명과 메서드 시그니처를 사용합니다.

    주요 속성:
      b_is_trained  : 학습 완료 여부 (True/False)
      i_label       : 최근 예측 결과 (0=배경, 1=사람)
      f_confidence  : 최근 예측 신뢰도 (0.0 ~ 1.0)
      A_probability : [배경 확률, 사람 확률] 리스트
    """

    # 모델 저장 경로 (models/ 폴더 아래)
    MODEL_PATH  = "models/mlp_weights.pt"   # 신경망 가중치
    SCALER_PATH = "models/mlp_scaler.pkl"   # StandardScaler 파라미터

    def __init__(self):
        # SVM_Module 인스턴스를 특징 추출기로 재활용
        # (특징 추출 코드를 다시 짤 필요 없음)
        self._svm_ref = svm.SVM_Module()

        # SVM과 동일한 24개 특징 인덱스 사용
        self.feature_indices: list = self._svm_ref.A_feature_indices
        self.input_size: int       = len(self.feature_indices)  # 24

        # 모델 & 스케일러 초기화
        self.model:  OccupancyMLP  = OccupancyMLP(self.input_size)
        self.scaler: StandardScaler = StandardScaler()

        # SVM_Module과 동일한 결과 속성
        self.b_is_trained: bool  = False
        self.i_label: int        = svm.enum_label.LABEL_BACKGROUND
        self.A_probability: list = [1.0, 0.0]
        self.f_confidence: float = 0.0

        # 이전에 저장된 모델이 있으면 자동 로드
        self._try_load_model()

    # ─────────────────────────────────────────────────────────
    # 외부에서 호출하는 메인 함수 (svm.svm()과 동일한 시그니처)
    # ─────────────────────────────────────────────────────────
    def mlp(self, inter_A_freq, inter_A_mag):
        """
        FFT 주파수/진폭 배열을 받아 재실 여부를 판단합니다.
        (SVM_Module.svm()과 동일한 반환값 구조)

        Args:
            inter_A_freq : 주파수 배열 (151개)
            inter_A_mag  : 진폭 배열  (151개)

        Returns:
            (A_probability, i_label, f_confidence)
        """
        # ① SVM 참조 객체로 특징 추출
        self._svm_ref.A_frequencies = inter_A_freq
        self._svm_ref.A_magnitudes  = inter_A_mag
        self._svm_ref.extract_features()

        # ② 학습된 경우에만 예측
        if self.b_is_trained:
            self._predict()

        return (self.A_probability, self.i_label, self.f_confidence)

    # ─────────────────────────────────────────────────────────
    # 학습
    # ─────────────────────────────────────────────────────────
    def train(self, csv_path: str = "svm_data.csv") -> bool:
        """
        CSV 파일을 로드해 MLP를 학습합니다.

        학습 흐름:
          CSV 로드
            ↓
          선택된 24개 특징만 추출
            ↓
          train(80%) / val(20%) 분리
            ↓
          StandardScaler로 정규화 (평균0, 표준편차1)
            ↓
          DataLoader 생성 (미니배치 학습)
            ↓
          EPOCHS 번 반복:
            · 순전파 → 손실 계산 → 역전파 → 가중치 업데이트
            · 검증 정확도 출력
            ↓
          모델 저장 (models/ 폴더)

        Returns:
            True: 학습 성공 / False: 데이터 부족 또는 파일 없음
        """
        # ① CSV 로드
        X_raw, y = self._load_csv(csv_path)
        if X_raw is None:
            print("[MLP] ❌ 데이터 부족 또는 파일 없음 — 학습 불가")
            return False

        n_samples = len(y)
        n_bg    = int(np.sum(y == 0))
        n_human = int(np.sum(y == 1))
        print(f"[MLP] 로드 완료 | 전체: {n_samples}개  (배경: {n_bg}, 사람: {n_human})")

        # ② 선택된 24개 특징만 추출
        X = X_raw[:, self.feature_indices]

        # ③ train/val 분리
        #    stratify=y : 각 클래스 비율을 유지하면서 분리
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=VAL_RATIO, random_state=42, stratify=y
        )

        # ④ 정규화
        #    fit_transform : 훈련 데이터 기준으로 평균/분산 계산 + 변환
        #    transform     : 검증 데이터는 훈련 기준으로만 변환 (정보 누수 방지)
        self.scaler = StandardScaler()
        X_train = self.scaler.fit_transform(X_train).astype(np.float32)
        X_val   = self.scaler.transform(X_val).astype(np.float32)

        # ⑤ 배치 크기 조정 (데이터가 너무 적으면 batch_size 줄임)
        effective_batch = min(BATCH_SIZE, max(2, n_samples // 4))

        train_loader = DataLoader(
            OccupancyDataset(X_train, y_train),
            batch_size=effective_batch,
            shuffle=True,       # 매 에폭마다 순서 섞기 → 학습 안정화
            drop_last=False,    # 마지막 미니배치가 불완전해도 버리지 않음
        )
        val_loader = DataLoader(
            OccupancyDataset(X_val, y_val),
            batch_size=effective_batch,
        )

        # ⑥ 모델 / 손실함수 / 옵티마이저 초기화
        self.model = OccupancyMLP(self.input_size)

        # CrossEntropyLoss:
        #   내부적으로 Softmax + NLLLoss를 합친 다중 분류 손실함수
        #   출력 logit을 그대로 넣으면 됨 (별도 Softmax 불필요)
        criterion = nn.CrossEntropyLoss()

        # Adam 옵티마이저:
        #   SGD(확률적 경사하강법)의 개선판
        #   파라미터마다 학습률을 자동으로 조절 → 빠르고 안정적
        optimizer = optim.Adam(self.model.parameters(), lr=LEARNING_RATE)

        # ⑦ 에폭 반복 학습
        print(f"[MLP] 학습 시작 (에폭: {EPOCHS}, 배치: {effective_batch})")
        best_val_acc = 0.0

        for epoch in range(1, EPOCHS + 1):

            # ── 학습 단계 ─────────────────────────────────
            self.model.train()  # train 모드: Dropout 활성화

            total_loss = 0.0
            for X_batch, y_batch in train_loader:
                optimizer.zero_grad()                  # 이전 기울기 초기화
                logits = self.model(X_batch)           # 순전파
                loss   = criterion(logits, y_batch)    # 손실 계산
                loss.backward()                        # 역전파 (기울기 계산)
                optimizer.step()                       # 가중치 업데이트
                total_loss += loss.item()

            # ── 검증 단계 (매 10 에폭마다 출력) ──────────
            if epoch % 10 == 0:
                val_acc = self._evaluate(val_loader)
                avg_loss = total_loss / len(train_loader)
                print(f"  에폭 {epoch:3d}/{EPOCHS} | 손실: {avg_loss:.4f} | 검증 정확도: {val_acc:.1%}")
                if val_acc > best_val_acc:
                    best_val_acc = val_acc

        print(f"[MLP] ✅ 학습 완료 | 최고 검증 정확도: {best_val_acc:.1%}")

        # ⑧ 모델 저장 후 완료 플래그 설정
        self._save_model()
        self.b_is_trained = True
        return True

    # ─────────────────────────────────────────────────────────
    # 예측 (내부 전용)
    # ─────────────────────────────────────────────────────────
    def _predict(self) -> None:
        """
        self._svm_ref에 추출된 특징으로 재실 여부를 예측합니다.
        결과를 self.i_label, self.f_confidence에 저장합니다.
        """
        svm_ref = self._svm_ref

        # 전체 163개 컬럼 벡터 조립 (CSV 저장 형식과 동일)
        A_stat = np.array([
            svm_ref.f_peak_freq, svm_ref.f_peak_mag, svm_ref.f_avg_mag,
            svm_ref.f_std_mag,   svm_ref.f_centroid,  svm_ref.f_low_energy,
            svm_ref.f_mid_energy, svm_ref.f_high_energy, svm_ref.f_rms,
            svm_ref.f_low_ratio,  svm_ref.f_spectral_entropy, svm_ref.f_peak_to_mean
        ])
        A_full = np.concatenate([np.array(svm_ref.A_magnitudes, dtype=np.float32), A_stat])

        # 24개 선택된 특징만 추출 → 정규화
        X_feat   = A_full[self.feature_indices].reshape(1, -1).astype(np.float32)
        X_scaled = self.scaler.transform(X_feat)

        # 추론 모드 (eval): Dropout 비활성화, BatchNorm 고정 통계 사용
        self.model.eval()
        with torch.no_grad():  # 기울기 계산 비활성 → 메모리 절약, 속도 향상
            logits    = self.model(torch.tensor(X_scaled))
            # softmax: logit → 확률 (합계 = 1.0)
            probs     = torch.softmax(logits, dim=1).numpy()[0]
            pred_idx  = int(np.argmax(probs))  # 더 높은 확률의 클래스 선택

        self.A_probability = probs.tolist()           # [배경 확률, 사람 확률]
        self.i_label       = pred_idx                 # 0 or 1
        self.f_confidence  = float(probs[pred_idx])   # 선택된 클래스의 확률

    # ─────────────────────────────────────────────────────────
    # 내부 유틸리티
    # ─────────────────────────────────────────────────────────
    def _load_csv(self, csv_path: str):
        """
        CSV 파일을 읽어 (특징 행렬, 레이블 배열) 반환.
        데이터 부족 시 (None, None) 반환.
        """
        if not os.path.exists(csv_path):
            print(f"[MLP] ❌ 파일 없음: {csv_path}")
            return None, None

        X_list, y_list = [], []
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # 헤더 한 줄 건너뜀
            for row in reader:
                if not row:
                    continue
                # 마지막 컬럼이 레이블, 나머지가 특징
                X_list.append([float(v) for v in row[:-1]])
                y_list.append(int(float(row[-1])))

        y = np.array(y_list)

        # 최소 조건: 샘플 10개 이상, 클래스가 배경+사람 둘 다 있어야 함
        if len(X_list) < 10 or len(np.unique(y)) < 2:
            return None, None

        return np.array(X_list, dtype=np.float32), y

    def _evaluate(self, loader: DataLoader) -> float:
        """DataLoader의 정확도(accuracy)를 계산해 반환"""
        self.model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for X_batch, y_batch in loader:
                # argmax: 가장 높은 점수의 클래스 인덱스 선택
                preds    = self.model(X_batch).argmax(dim=1)
                correct += (preds == y_batch).sum().item()
                total   += len(y_batch)
        return correct / total if total > 0 else 0.0

    def _save_model(self) -> None:
        """모델 가중치와 스케일러를 파일로 저장"""
        os.makedirs("models", exist_ok=True)
        # state_dict: 모델의 모든 가중치(W, b)를 담은 딕셔너리
        torch.save(self.model.state_dict(), self.MODEL_PATH)
        with open(self.SCALER_PATH, 'wb') as f:
            pickle.dump(self.scaler, f)
        print(f"[MLP] 💾 저장 완료 → {self.MODEL_PATH}")

    def _try_load_model(self) -> None:
        """앱 재시작 시 저장된 모델을 자동으로 로드 (재학습 불필요)"""
        if not (os.path.exists(self.MODEL_PATH) and os.path.exists(self.SCALER_PATH)):
            return
        try:
            # map_location='cpu': GPU가 없어도 CPU에서 로드
            state_dict = torch.load(self.MODEL_PATH, map_location='cpu', weights_only=True)
            self.model.load_state_dict(state_dict)
            with open(self.SCALER_PATH, 'rb') as f:
                self.scaler = pickle.load(f)
            self.model.eval()
            self.b_is_trained = True
            print(f"[MLP] ✅ 저장된 모델 로드 완료: {self.MODEL_PATH}")
        except Exception as e:
            print(f"[MLP] ⚠️ 모델 로드 실패 (재학습 필요): {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  직접 실행 시 학습 + 간단 테스트
#  $ python nn_mlp.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    print("=" * 60)
    print("  MLP 재실 판단 모델 학습")
    print("=" * 60)

    module = MLP_Module()
    success = module.train(csv_path="svm_data.csv")

    if success:
        print("\n✅ 학습 완료! models/ 폴더에 모델이 저장되었습니다.")
        print("   다음 실행 시 자동으로 로드됩니다.")
    else:
        print("\n❌ 학습 실패.")
        print("   svm_data.csv 가 있고, 배경/사람 데이터가 각각 있는지 확인하세요.")
