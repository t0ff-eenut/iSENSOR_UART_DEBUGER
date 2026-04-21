"""
╔══════════════════════════════════════════════════════════════════╗
║  1D-CNN (1차원 합성곱 신경망) 기반 재실 판단 딥러닝 모델        ║
╚══════════════════════════════════════════════════════════════════╝

[ 개념 ]
  FFT 스펙트럼 151개의 빈(bin)을 1차원 신호로 보고,
  합성곱(Convolution) 필터로 주파수 패턴을 자동으로 학습합니다.

  예: "0.5~3Hz 사이에 에너지가 솟아있으면 사람 신호"
      이런 국소 패턴을 Conv1d 필터가 스스로 발견합니다.

[ 구조 ]
  스펙트럼(151)
      ↓ reshape → (1, 151)
  [Conv1d(16) → BN → ReLU → MaxPool] → (16, 75)
      ↓
  [Conv1d(32) → BN → ReLU → MaxPool] → (32, 37)
      ↓
  [Conv1d(64) → BN → ReLU → AvgPool] → (64,  4)
      ↓ Flatten
  [FC(256→64) → ReLU → Dropout]
      ↓
  [FC(64→2)]  →  BACKGROUND / HUMAN

  ★ MLP와의 차이:
    MLP : 특징을 사람이 직접 골라서(24개) 입력
    CNN : 원시 스펙트럼(151개)을 그대로 넣고 특징 추출을 모델이 학습

[ 사용법 ]
  ① 직접 실행 (학습):
       python nn_cnn.py

  ② 코드에서 import:
       from nn_cnn import CNN_Module
       cnn = CNN_Module()
       cnn.train()   # svm_data.csv 로드 후 학습
       prob, label, conf = cnn.cnn(A_frequencies, A_magnitudes)

[ 필요 패키지 ]
  pip install torch torchvision
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

import svm   # enum_label, I_MAGNITUDES_COUNT 재사용


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  하이퍼파라미터 (튜닝이 필요하면 여기서 수정)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EPOCHS         = 100   # 전체 데이터를 몇 번 반복 학습할지
BATCH_SIZE     = 16    # 한 번에 처리할 샘플 수
LEARNING_RATE  = 1e-3  # 학습률 (0.001)
DROPOUT_RATE   = 0.3   # 드롭아웃 비율 (30% 뉴런 랜덤 OFF)
VAL_RATIO      = 0.2   # 검증 데이터 비율 (20%)

# Conv 채널 수: 각 합성곱 층이 몇 가지 패턴을 학습할지
CH1 = 16   # 1번째 Conv: 저수준 패턴 16가지 (예: 특정 주파수 대역 에너지)
CH2 = 32   # 2번째 Conv: 중간 수준 패턴 32가지 (여러 대역의 조합)
CH3 = 64   # 3번째 Conv: 고수준 패턴 64가지 (사람 vs 배경 특유 구조)

# CNN 입력 크기: FFT 스펙트럼 빈 수 (DC 포함 151개)
SPECTRUM_LEN = svm.I_MAGNITUDES_COUNT   # 151


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ① 데이터셋 클래스 — CNN 전용 (magnitudes 151개를 입력으로 사용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class SpectrumDataset(Dataset):
    """
    FFT 스펙트럼(151개)을 PyTorch 텐서로 감싸는 컨테이너.

    MLP와 달리 CNN은 원시 스펙트럼을 사용하므로
    특징 선택 과정 없이 모든 빈 값을 그대로 입력합니다.
    """

    def __init__(self, X: np.ndarray, y: np.ndarray):
        # X shape: (N, 151) → 그대로 저장
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ② CNN 모델 구조 정의
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class OccupancyCNN(nn.Module):
    """
    FFT 스펙트럼을 1D 신호로 처리하는 합성곱 신경망.

    ┌─────────────────────────────────────────────────────────┐
    │ 입력: 스펙트럼 151개 → reshape (1채널, 길이151)          │
    │                                                         │
    │ Conv층1: Conv1d(1→16, k=5) → BN → ReLU → MaxPool(2)   │
    │          출력 shape: (16채널, 75)                       │
    │   └─ 16개의 필터가 각각 5개 연속 빈의 패턴을 감지       │
    │                                                         │
    │ Conv층2: Conv1d(16→32, k=3) → BN → ReLU → MaxPool(2)  │
    │          출력 shape: (32채널, 37)                       │
    │   └─ 이전 패턴들의 조합을 32개 필터로 학습              │
    │                                                         │
    │ Conv층3: Conv1d(32→64, k=3) → BN → ReLU → AvgPool(4)  │
    │          출력 shape: (64채널, 4) → Flatten → (256,)    │
    │   └─ 더 추상적인 고수준 특징 64개 추출                  │
    │                                                         │
    │ FC층1: Linear(256→64) → ReLU → Dropout(30%)           │
    │ FC층2: Linear(64→2)   → [BG 점수, Human 점수]          │
    └─────────────────────────────────────────────────────────┘

    용어 설명:
      Conv1d     : 1차원 합성곱 — 이웃한 여러 빈의 패턴을 감지
                   (이미지에선 2D, 음성/스펙트럼에선 1D 사용)
      kernel     : 필터 창의 크기 (k=5면 5개 빈을 한 번에 봄)
      padding    : 가장자리 빈 처리 (padding=k//2 → 출력 크기 유지)
      MaxPool1d  : 두 값 중 큰 값만 통과 → 크기 절반, 주요 패턴 유지
      AvgPool1d  : Adaptive 버전 — 고정 크기(4)로 압축
      Flatten    : (채널, 길이) → 1D 벡터로 펼치기 (FC층 입력 준비)
    """

    def __init__(self):
        super().__init__()

        # ── 합성곱 블록 ──────────────────────────────────────────
        # padding = kernel_size // 2 → "same padding": 입력/출력 길이 동일
        self.conv_block = nn.Sequential(

            # Conv층 1: 저수준 스펙트럼 패턴 감지
            # 입력: (batch, 1, 151) → 출력: (batch, 16, 151)
            nn.Conv1d(in_channels=1, out_channels=CH1, kernel_size=5, padding=2),
            nn.BatchNorm1d(CH1),
            nn.ReLU(),
            # MaxPool: 151 → 75  (floor(151/2))
            nn.MaxPool1d(kernel_size=2),

            # Conv층 2: 중간 수준 패턴 (여러 대역의 조합)
            # 입력: (batch, 16, 75) → 출력: (batch, 32, 75)
            nn.Conv1d(in_channels=CH1, out_channels=CH2, kernel_size=3, padding=1),
            nn.BatchNorm1d(CH2),
            nn.ReLU(),
            # MaxPool: 75 → 37
            nn.MaxPool1d(kernel_size=2),

            # Conv층 3: 고수준 패턴 (사람/배경 특유 구조)
            # 입력: (batch, 32, 37) → 출력: (batch, 64, 37)
            nn.Conv1d(in_channels=CH2, out_channels=CH3, kernel_size=3, padding=1),
            nn.BatchNorm1d(CH3),
            nn.ReLU(),
            # AdaptiveAvgPool: 37 → 4 (고정 크기로 압축 — 입력 길이가 달라져도 OK)
            nn.AdaptiveAvgPool1d(output_size=4),
        )

        # Flatten 후 크기: CH3 * 4 = 64 * 4 = 256
        flatten_size = CH3 * 4

        # ── 완전연결(분류) 블록 ───────────────────────────────────
        self.fc_block = nn.Sequential(
            nn.Linear(flatten_size, 64),
            nn.ReLU(),
            nn.Dropout(p=DROPOUT_RATE),
            nn.Linear(64, 2),   # 출력: [BACKGROUND 점수, HUMAN 점수]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        순전파:
          입력 x : (batch, 151)  ← 스펙트럼 1D 벡터
          출력   : (batch, 2)    ← 각 클래스의 점수(logit)
        """
        # Conv1d는 (batch, channels, length) 형태를 기대
        # → (batch, 151) → (batch, 1, 151) 로 차원 추가
        x = x.unsqueeze(1)            # (batch, 1, 151)

        x = self.conv_block(x)        # (batch, 64, 4)
        x = x.flatten(start_dim=1)    # (batch, 256) — 1D 벡터로 펼치기
        x = self.fc_block(x)          # (batch, 2)
        return x


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ③ SVM_Module과 동일한 API를 가진 래퍼 클래스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class CNN_Module:
    """
    CNN 모델을 SVM_Module과 동일한 방식으로 사용하는 래퍼.

    MLP_Module / SVM_Module 과 달리,
    CNN은 24개 선택 특징 대신 원시 스펙트럼 151개 전체를 입력으로 씁니다.

    주요 속성:
      b_is_trained  : 학습 완료 여부
      i_label       : 최근 예측 결과 (0=배경, 1=사람)
      f_confidence  : 최근 예측 신뢰도 (0.0 ~ 1.0)
      A_probability : [배경 확률, 사람 확률] 리스트
    """

    # 모델 저장 경로
    MODEL_PATH  = "models/cnn_weights.pt"
    SCALER_PATH = "models/cnn_scaler.pkl"

    def __init__(self):
        # SVM_Module 인스턴스를 특징 추출기로 재활용 (공통 extract_features 사용)
        self._svm_ref = svm.SVM_Module()

        # 모델 & 스케일러 초기화
        self.model:  OccupancyCNN   = OccupancyCNN()
        self.scaler: StandardScaler = StandardScaler()

        # SVM_Module과 동일한 결과 속성
        self.b_is_trained: bool  = False
        self.i_label: int        = svm.enum_label.LABEL_BACKGROUND
        self.A_probability: list = [1.0, 0.0]
        self.f_confidence: float = 0.0

        # 이전에 저장된 모델이 있으면 자동 로드
        self._try_load_model()

    # ─────────────────────────────────────────────────────────
    # 외부에서 호출하는 메인 함수
    # ─────────────────────────────────────────────────────────
    def cnn(self, inter_A_freq, inter_A_mag):
        """
        FFT 주파수/진폭 배열을 받아 재실 여부를 판단합니다.
        (SVM_Module.svm()과 동일한 반환값 구조)

        Args:
            inter_A_freq : 주파수 배열 (151개)
            inter_A_mag  : 진폭 배열  (151개, 이게 CNN의 실제 입력)

        Returns:
            (A_probability, i_label, f_confidence)
        """
        # SVM 참조 객체로 특징 추출 (A_magnitudes, A_frequencies 업데이트)
        self._svm_ref.A_frequencies = inter_A_freq
        self._svm_ref.A_magnitudes  = inter_A_mag
        self._svm_ref.extract_features()  # 통계 특징도 계산 (현재는 미사용, 확장 가능)

        if self.b_is_trained:
            self._predict()

        return (self.A_probability, self.i_label, self.f_confidence)

    # ─────────────────────────────────────────────────────────
    # 학습
    # ─────────────────────────────────────────────────────────
    def train(self, csv_path: str = "svm_data.csv") -> bool:
        """
        CSV 파일을 로드해 1D-CNN을 학습합니다.

        MLP와의 차이점:
          · 입력: 24개 선택 특징 대신 스펙트럼 151개 전체 사용
          · CNN이 어떤 주파수 패턴이 중요한지 스스로 학습

        학습 흐름:
          CSV 로드
            ↓
          스펙트럼 151개 컬럼만 추출 (magnitudes_0 ~ magnitudes_150)
            ↓
          train(80%) / val(20%) 분리
            ↓
          StandardScaler 정규화
            ↓
          EPOCHS 번 반복 학습
            ↓
          모델 저장

        Returns:
            True: 학습 성공 / False: 데이터 부족
        """
        # ① CSV 로드
        X_raw, y = self._load_csv(csv_path)
        if X_raw is None:
            print("[CNN] ❌ 데이터 부족 또는 파일 없음 — 학습 불가")
            return False

        n_samples = len(y)
        n_bg    = int(np.sum(y == 0))
        n_human = int(np.sum(y == 1))
        print(f"[CNN] 로드 완료 | 전체: {n_samples}개  (배경: {n_bg}, 사람: {n_human})")

        # ② 스펙트럼 151개만 추출 (컬럼 0 ~ 150)
        #    CSV 전체 컬럼: 151(스펙트럼) + 12(통계) + 1(레이블) = 164
        X = X_raw[:, :SPECTRUM_LEN]   # shape: (N, 151)

        # ③ train/val 분리
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=VAL_RATIO, random_state=42, stratify=y
        )

        # ④ 정규화
        #    스펙트럼 값의 범위가 크고 다양하므로 정규화 필수
        self.scaler = StandardScaler()
        X_train = self.scaler.fit_transform(X_train).astype(np.float32)
        X_val   = self.scaler.transform(X_val).astype(np.float32)

        # ⑤ DataLoader 생성
        effective_batch = min(BATCH_SIZE, max(2, n_samples // 4))

        train_loader = DataLoader(
            SpectrumDataset(X_train, y_train),
            batch_size=effective_batch,
            shuffle=True,
            drop_last=False,
        )
        val_loader = DataLoader(
            SpectrumDataset(X_val, y_val),
            batch_size=effective_batch,
        )

        # ⑥ 모델 / 손실함수 / 옵티마이저 초기화
        self.model = OccupancyCNN()
        criterion  = nn.CrossEntropyLoss()
        optimizer  = optim.Adam(self.model.parameters(), lr=LEARNING_RATE)

        # ⑦ 에폭 반복 학습
        print(f"[CNN] 학습 시작 (에폭: {EPOCHS}, 배치: {effective_batch})")
        best_val_acc = 0.0

        for epoch in range(1, EPOCHS + 1):

            # ── 학습 단계 ─────────────────────────────────
            self.model.train()   # Conv/BN/Dropout 학습 모드
            total_loss = 0.0

            for X_batch, y_batch in train_loader:
                optimizer.zero_grad()
                # X_batch shape: (batch, 151)
                # CNN forward 내부에서 (batch, 1, 151)로 reshape됨
                logits = self.model(X_batch)
                loss   = criterion(logits, y_batch)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            # ── 검증 단계 (매 10 에폭마다) ────────────────
            if epoch % 10 == 0:
                val_acc  = self._evaluate(val_loader)
                avg_loss = total_loss / len(train_loader)
                print(f"  에폭 {epoch:3d}/{EPOCHS} | 손실: {avg_loss:.4f} | 검증 정확도: {val_acc:.1%}")
                if val_acc > best_val_acc:
                    best_val_acc = val_acc

        print(f"[CNN] ✅ 학습 완료 | 최고 검증 정확도: {best_val_acc:.1%}")

        # ⑧ 저장
        self._save_model()
        self.b_is_trained = True
        return True

    # ─────────────────────────────────────────────────────────
    # 예측 (내부 전용)
    # ─────────────────────────────────────────────────────────
    def _predict(self) -> None:
        """
        현재 프레임의 스펙트럼(151개)으로 재실 여부를 예측합니다.
        MLP와 달리 특징 선택 없이 원시 스펙트럼을 그대로 사용합니다.
        """
        # 현재 스펙트럼 151개 추출
        X_mag = np.array(self._svm_ref.A_magnitudes, dtype=np.float32).reshape(1, -1)
        # shape: (1, 151)

        # 정규화 (학습 시와 동일한 scaler 사용)
        X_scaled = self.scaler.transform(X_mag).astype(np.float32)

        # 추론 (eval 모드: Dropout OFF, BN 고정 통계)
        self.model.eval()
        with torch.no_grad():
            # X_scaled: (1, 151) → CNN 내부에서 (1, 1, 151)로 처리됨
            logits   = self.model(torch.tensor(X_scaled))
            probs    = torch.softmax(logits, dim=1).numpy()[0]
            pred_idx = int(np.argmax(probs))

        self.A_probability = probs.tolist()
        self.i_label       = pred_idx
        self.f_confidence  = float(probs[pred_idx])

    # ─────────────────────────────────────────────────────────
    # 내부 유틸리티
    # ─────────────────────────────────────────────────────────
    def _load_csv(self, csv_path: str):
        """CSV 파일을 읽어 (전체 특징 행렬, 레이블 배열) 반환"""
        if not os.path.exists(csv_path):
            print(f"[CNN] ❌ 파일 없음: {csv_path}")
            return None, None

        X_list, y_list = [], []
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # 헤더 스킵
            for row in reader:
                if not row:
                    continue
                X_list.append([float(v) for v in row[:-1]])   # 마지막 컬럼 제외 (특징)
                y_list.append(int(float(row[-1])))             # 마지막 컬럼 (레이블)

        y = np.array(y_list)

        if len(X_list) < 10 or len(np.unique(y)) < 2:
            return None, None

        return np.array(X_list, dtype=np.float32), y

    def _evaluate(self, loader: DataLoader) -> float:
        """DataLoader의 분류 정확도 계산"""
        self.model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for X_batch, y_batch in loader:
                preds    = self.model(X_batch).argmax(dim=1)
                correct += (preds == y_batch).sum().item()
                total   += len(y_batch)
        return correct / total if total > 0 else 0.0

    def _save_model(self) -> None:
        """모델 가중치와 스케일러를 파일로 저장"""
        os.makedirs("models", exist_ok=True)
        torch.save(self.model.state_dict(), self.MODEL_PATH)
        with open(self.SCALER_PATH, 'wb') as f:
            pickle.dump(self.scaler, f)
        print(f"[CNN] 💾 저장 완료 → {self.MODEL_PATH}")

    def _try_load_model(self) -> None:
        """앱 재시작 시 저장된 모델을 자동으로 로드"""
        if not (os.path.exists(self.MODEL_PATH) and os.path.exists(self.SCALER_PATH)):
            return
        try:
            state_dict = torch.load(self.MODEL_PATH, map_location='cpu', weights_only=True)
            self.model.load_state_dict(state_dict)
            with open(self.SCALER_PATH, 'rb') as f:
                self.scaler = pickle.load(f)
            self.model.eval()
            self.b_is_trained = True
            print(f"[CNN] ✅ 저장된 모델 로드 완료: {self.MODEL_PATH}")
        except Exception as e:
            print(f"[CNN] ⚠️ 모델 로드 실패 (재학습 필요): {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  직접 실행 시 학습 + 간단 테스트
#  $ python nn_cnn.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    print("=" * 60)
    print("  1D-CNN 재실 판단 모델 학습")
    print("=" * 60)

    # 모델 아키텍처 요약 출력 (torchinfo 없어도 간단히 확인 가능)
    model_summary = OccupancyCNN()
    n_params = sum(p.numel() for p in model_summary.parameters() if p.requires_grad)
    print(f"\n[CNN] 학습 파라미터 수: {n_params:,}개")
    print(f"[CNN] 입력 크기: {SPECTRUM_LEN}개 (FFT 스펙트럼 빈)\n")

    module = CNN_Module()
    success = module.train(csv_path="svm_data.csv")

    if success:
        print("\n✅ 학습 완료! models/ 폴더에 모델이 저장되었습니다.")
        print("   다음 실행 시 자동으로 로드됩니다.")
    else:
        print("\n❌ 학습 실패.")
        print("   svm_data.csv 가 있고, 배경/사람 데이터가 각각 있는지 확인하세요.")
