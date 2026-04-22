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
import sys
import csv
import json
import pickle
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# svm.py는 상위 폴더에 위치하므로 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# svm.py의 enum_label, A_feature_indices 재사용
import svm


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  학습 로그 저장용 Tee (stdout → 콘솔 + 파일 동시 출력)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _Tee:
    """sys.stdout을 콘솔과 파일에 동시에 기록하는 듀얼 스트림."""
    def __init__(self, orig, f):
        self._orig = orig
        self._f    = f
    def write(self, s):
        self._orig.write(s)
        self._f.write(s)
    def flush(self):
        self._orig.flush()
        self._f.flush()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  하이퍼파라미터 (튜닝이 필요하면 여기서 수정)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── 학습 설정 ────────────────────────────────────────────────────
EPOCHS        = 300   # 전체 데이터를 몇 번 반복 학습할지
BATCH_SIZE    = 16    # 한 번에 처리할 샘플 수
LEARNING_RATE = 5e-4  # 학습률
VAL_RATIO     = 0.2   # 검증 데이터 비율 (전체의 20%)

# ── 신경망 구조 ──────────────────────────────────────────────────
# HIDDEN_LAYERS : 각 은닉층의 뉴런 수를 리스트로 지정
#   예) [64, 32]       → 은닉층 2개
#       [128, 64, 32]  → 은닉층 3개 ← 현재 (v3.0)
#       [256]          → 은닉층 1개
HIDDEN_LAYERS = [128, 64, 32]

DROPOUT_RATE  = 0.3   # 드롭아웃: 첫 번째 은닉층 뒤 뉴런의 30%를 랜덤 OFF → 과적합 방지
# ※ 학습/검증 차이가 5%+ 벌어지면 0.4~0.5로 올릴 것

# ── 학습률 스케줄러 설정 ─────────────────────────────────────────
# ReduceLROnPlateau: 검증 손실이 patience 에폭 동안 줄지 않으면
# 학습률을 factor 배로 줄임 → 정체 구간에서 더 세밀하게 수렴
LR_SCHEDULER_PATIENCE = 10    # 몇 에폭 동안 개선 없으면 낮출지
LR_SCHEDULER_FACTOR   = 0.5   # 학습률을 몇 배로 낮출지 (0.5 = 절반)

# ── 하위 호환용 (visualize.py 등에서 참조) ──────────────────────
HIDDEN_SIZE_1 = HIDDEN_LAYERS[0]
HIDDEN_SIZE_2 = HIDDEN_LAYERS[1] if len(HIDDEN_LAYERS) > 1 else HIDDEN_LAYERS[0]


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
    HIDDEN_LAYERS 리스트에 지정된 대로 은닉층을 동적으로 생성합니다.

    예) HIDDEN_LAYERS = [64, 32]
        입력(24) → Linear(24→64)→BN→ReLU→Dropout → Linear(64→32)→ReLU → Linear(32→2)

    예) HIDDEN_LAYERS = [128, 64, 32]
        입력(24) → 128 → 64 → 32 → 출력(2)  (은닉층 3개)
    """

    def __init__(self, input_size: int):
        super().__init__()

        layers = []
        in_size = input_size

        for i, h_size in enumerate(HIDDEN_LAYERS):
            layers.append(nn.Linear(in_size, h_size))

            # 첫 번째 은닉층에만 BatchNorm + Dropout 적용
            if i == 0:
                layers.append(nn.BatchNorm1d(h_size))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(p=DROPOUT_RATE))
            else:
                layers.append(nn.ReLU())

            in_size = h_size

        # 출력층
        layers.append(nn.Linear(in_size, 2))

        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
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

    # 모델 저장 경로 (AI/models/ 폴더 아래)
    _AI_DIR     = os.path.dirname(os.path.abspath(__file__))          # AI/ 절대경로
    MODEL_PATH  = os.path.join(_AI_DIR, 'models', 'mlp_weights.pt')  # 신경망 가중치
    SCALER_PATH = os.path.join(_AI_DIR, 'models', 'mlp_scaler.pkl')  # StandardScaler 파라미터

    def __init__(self):
        # SVM_Module 인스턴스를 특징 추출기로 재활용
        # (특징 추출 코드를 다시 짤 필요 없음)
        self._svm_ref = svm.SVM_Module()

        # SVM과 동일한 24개 특징 인덱스 사용
        self.feature_indices: list = self._svm_ref.A_feature_indices
        self.input_size: int       = len(self.feature_indices)  # 25 (svm.A_feature_indices 기준)

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
            inter_A_freq : 주파수 배열 (129개)
            inter_A_mag  : 진폭 배열  (129개)

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
        log_path    = self._make_log_path('train')
        _log_f      = open(log_path, 'w', encoding='utf-8')
        _orig_out   = sys.stdout
        sys.stdout  = _Tee(_orig_out, _log_f)
        try:
            return self._train_impl(csv_path)
        finally:
            sys.stdout = _orig_out
            _log_f.close()
            print(f"[MLP] 📝 학습 로그 저장 → {log_path}")

    def _train_impl(self, csv_path: str) -> bool:
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
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', patience=LR_SCHEDULER_PATIENCE,
            factor=LR_SCHEDULER_FACTOR, min_lr=1e-6
        )
        # ⑦ 에폭 반복 학습
        layers_str = ' → '.join(str(h) for h in HIDDEN_LAYERS)
        print(f"[MLP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"[MLP]  구조: {self.input_size} → {layers_str} → 2")
        print(f"[MLP]  에폭: {EPOCHS}  배치: {effective_batch}  LR: {LEARNING_RATE:.0e}  Dropout: {DROPOUT_RATE}")
        print(f"[MLP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        best_val_acc = 0.0
        history = {'epochs': [], 'loss': [], 'train_acc': [], 'val_acc': []}

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

            avg_loss  = total_loss / len(train_loader)
            train_acc = self._evaluate(train_loader)
            val_acc   = self._evaluate(val_loader)
            scheduler.step(avg_loss)

            history['epochs'].append(epoch)
            history['loss'].append(round(avg_loss, 6))
            history['train_acc'].append(round(train_acc, 6))
            history['val_acc'].append(round(val_acc, 6))

            if epoch % 10 == 0:
                current_lr = optimizer.param_groups[0]['lr']
                print(f"  에폭 {epoch:3d}/{EPOCHS} | 손실: {avg_loss:.4f} | 학습: {train_acc:.1%} | 검증: {val_acc:.1%} | lr: {current_lr:.2e}")
                if val_acc > best_val_acc:
                    best_val_acc = val_acc

        print(f"[MLP] ✅ 학습 완료 | [{layers_str}] | 최고 검증 정확도: {best_val_acc:.1%}")

        # ⑧ 모델 저장 후 완료 플래그 설정
        self._save_model()
        self._save_history(history)
        self.b_is_trained = True
        return True

    # ─────────────────────────────────────────────────────────
    # 사전 분리된 학습/검증 파일로 학습 + 상세 평가
    # ─────────────────────────────────────────────────────────
    def train_eval(
        self,
        train_csv: str = 'AI/data_train.csv',
        val_csv:   str = 'AI/data_val.csv',
    ) -> bool:
        """
        prepare_data.py 로 만든 학습/검증 CSV를 각각 사용해
        MLP를 학습하고 검증 데이터로 상세 평가를 출력합니다.

        일반 train()과의 차이:
          · train/val 분리를 외부에서 고정 — 재현성 보장
          · 학습 완료 후 정밀도/재현율/F1 + 혼동 행렬 출력

        Args:
            train_csv : 학습용 CSV (prepare_data.py → AI/data_train.csv)
            val_csv   : 검증용 CSV (prepare_data.py → AI/data_val.csv)

        Returns:
            True: 성공 / False: 실패
        """
        log_path    = self._make_log_path('train_eval')
        _log_f      = open(log_path, 'w', encoding='utf-8')
        _orig_out   = sys.stdout
        sys.stdout  = _Tee(_orig_out, _log_f)
        try:
            return self._train_eval_impl(train_csv, val_csv)
        finally:
            sys.stdout = _orig_out
            _log_f.close()
            print(f"[MLP] 📝 학습 로그 저장 → {log_path}")

    def _train_eval_impl(self, train_csv: str, val_csv: str) -> bool:
        # ① 학습 데이터 로드
        X_train_raw, y_train = self._load_csv(train_csv)
        if X_train_raw is None:
            print(f"[MLP] ❌ 학습 데이터 로드 실패: {train_csv}")
            return False

        # ② 검증 데이터 로드 (최소 샘플 수 체크 없이)
        X_val_raw, y_val = self._load_csv(val_csv, min_check=False)
        if X_val_raw is None:
            print(f"[MLP] ❌ 검증 데이터 로드 실패: {val_csv}")
            return False

        n_train = len(y_train)
        n_val   = len(y_val)
        print(f"[MLP] 학습 데이터: {n_train}개 | 검증 데이터: {n_val}개")

        # ③ 특징 선택
        X_train = X_train_raw[:, self.feature_indices]
        X_val   = X_val_raw[:,   self.feature_indices]

        # ④ 정규화 (학습 기준으로 fit, 검증은 transform만)
        self.scaler = StandardScaler()
        X_train = self.scaler.fit_transform(X_train).astype(np.float32)
        X_val   = self.scaler.transform(X_val).astype(np.float32)

        # ⑤ DataLoader 생성
        effective_batch = min(BATCH_SIZE, max(2, n_train // 4))
        train_loader = DataLoader(
            OccupancyDataset(X_train, y_train),
            batch_size=effective_batch,
            shuffle=True,
        )
        val_loader = DataLoader(
            OccupancyDataset(X_val, y_val),
            batch_size=effective_batch,
        )

        # ⑥ 모델 / 손실함수 / 옵티마이저 초기화
        self.model = OccupancyMLP(self.input_size)
        criterion  = nn.CrossEntropyLoss()
        optimizer  = optim.Adam(self.model.parameters(), lr=LEARNING_RATE)
        scheduler  = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', patience=LR_SCHEDULER_PATIENCE,
            factor=LR_SCHEDULER_FACTOR, min_lr=1e-6
        )
        # ⑦ 에폭 반복 학습
        layers_str = ' → '.join(str(h) for h in HIDDEN_LAYERS)
        print(f"[MLP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"[MLP]  구조: {self.input_size} → {layers_str} → 2")
        print(f"[MLP]  에폭: {EPOCHS}  배치: {effective_batch}  LR: {LEARNING_RATE:.0e}  Dropout: {DROPOUT_RATE}")
        print(f"[MLP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        best_val_acc = 0.0
        history = {'epochs': [], 'loss': [], 'train_acc': [], 'val_acc': []}

        for epoch in range(1, EPOCHS + 1):
            self.model.train()
            total_loss = 0.0
            for X_batch, y_batch in train_loader:
                optimizer.zero_grad()
                loss = criterion(self.model(X_batch), y_batch)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            avg_loss  = total_loss / len(train_loader)
            train_acc = self._evaluate(train_loader)
            val_acc   = self._evaluate(val_loader)
            scheduler.step(avg_loss)

            history['epochs'].append(epoch)
            history['loss'].append(round(avg_loss, 6))
            history['train_acc'].append(round(train_acc, 6))
            history['val_acc'].append(round(val_acc, 6))

            if epoch % 10 == 0:
                current_lr = optimizer.param_groups[0]['lr']
                print(f"  에폭 {epoch:3d}/{EPOCHS} | 손실: {avg_loss:.4f} | 학습: {train_acc:.1%} | 검증: {val_acc:.1%} | lr: {current_lr:.2e}")
                if val_acc > best_val_acc:
                    best_val_acc = val_acc

        # ⑧ 최종 상세 평가
        print(f"\n[MLP] ── 최종 검증 결과 ─────────────────────────────")
        self._evaluate_detail(X_val, y_val)
        print(f"[MLP] ✅ 학습 완료 | [{layers_str}] | 최고 검증 정확도: {best_val_acc:.1%}")

        # ⑨ 모델 저장
        self._save_model()
        self._save_history(history)
        self.b_is_trained = True
        return True

    def evaluate(self, val_csv: str = 'AI/data_val.csv') -> bool:
        """
        저장된 모델을 로드해 val_csv 전체를 추론하고 상세 결과를 출력합니다.
        학습 없이 추론만 수행할 때 사용합니다.

        Args:
            val_csv : 검증용 CSV 경로 (기본값: AI/data_val.csv)

        Returns:
            True: 성공 / False: 모델 없음 또는 데이터 오류
        """
        if not self.b_is_trained:
            print("[MLP] ❌ 저장된 모델 없음 — 먼저 학습을 실행하세요:")
            print("     python3 AI/nn_mlp.py --mode split")
            return False

        X_raw, y = self._load_csv(val_csv, min_check=False)
        if X_raw is None:
            print(f"[MLP] ❌ 검증 데이터 로드 실패: {val_csv}")
            return False

        X = X_raw[:, self.feature_indices]
        X = self.scaler.transform(X).astype(np.float32)

        n_bg    = int((y == 0).sum())
        n_human = int((y == 1).sum())
        print(f"[MLP] 추론 대상: {len(y)}행  (BG: {n_bg}, Human: {n_human})")
        print(f"[MLP] ── 추론 결과 ─────────────────────────────────────")
        self._evaluate_detail(X, y)
        return True

    def _evaluate_detail(self, X_val: np.ndarray, y_val: np.ndarray) -> None:
        """
        검증 데이터에 대해 클래스별 정밀도/재현율/F1 및 혼동 행렬을 한글로 출력.
        """
        from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

        self.model.eval()
        with torch.no_grad():
            preds = self.model(torch.tensor(X_val)).argmax(dim=1).numpy()

        cm = confusion_matrix(y_val, preds)

        # 클래스별 지표 계산
        prec, rec, f1, sup = precision_recall_fscore_support(y_val, preds, labels=[0, 1])
        # 전체 정확도
        accuracy = float((preds == y_val).sum()) / len(y_val)
        # macro / weighted 평균
        prec_m,  rec_m,  f1_m,  _ = precision_recall_fscore_support(y_val, preds, average='macro')
        prec_w,  rec_w,  f1_w,  _ = precision_recall_fscore_support(y_val, preds, average='weighted')

        cls_names = ['배경(BG)', '사람(Human)']
        w = 12  # 열 너비

        # ── 지표 설명 출력 ─────────────────────────────────────────
        # 정밀도 (Precision) : 모델이 '사람'이라고 예측한 것 중 실제로 사람인 비율
        #                      → 오경보(배경→사람 오판) 얼마나 없는지
        # 재현율 (Recall)    : 실제 '사람' 중 모델이 올바르게 잡아낸 비율
        #                      → 놓침(사람→배경 오판) 얼마나 없는지  ← 재실 감지에서 가장 중요
        # F1 점수            : 정밀도와 재현율의 조화 평균 (둘 다 높아야 높게 나옴)
        # 단순 평균          : 클래스 수에 상관없이 클래스별 지표를 단순 평균
        # 가중 평균          : 각 클래스의 샘플 수 비율로 가중해서 평균
        print()
        print("  ── 지표 설명 ──────────────────────────────────────────────────")
        print("  정밀도(Precision) : '사람'이라 예측한 것 중 실제 사람인 비율   → 오경보 방지")
        print("  재현율(Recall)    : 실제 사람 중 모델이 올바르게 잡아낸 비율   → 놓침 방지 ★")
        print("  F1 점수           : 정밀도·재현율의 조화 평균 (둘 다 높아야 높음)")
        print("  단순 평균         : 클래스별 지표를 동일 가중치로 평균")
        print("  가중 평균         : 클래스별 샘플 수 비율로 가중하여 평균")
        print()

        # ── 지표 테이블 ────────────────────────────────────────────
        header = f"  {'클래스':<{w}}  {'정밀도':>8}  {'재현율':>8}  {'F1 점수':>8}  {'샘플 수':>7}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for i, name in enumerate(cls_names):
            print(f"  {name:<{w}}  {prec[i]:>8.3f}  {rec[i]:>8.3f}  {f1[i]:>8.3f}  {int(sup[i]):>7}")
        print()
        print(f"  {'전체 정확도':<{w}}  {'':>8}  {'':>8}  {accuracy:>8.3f}  {len(y_val):>7}")
        print(f"  {'단순 평균':<{w}}  {prec_m:>8.3f}  {rec_m:>8.3f}  {f1_m:>8.3f}  {len(y_val):>7}")
        print(f"  {'가중 평균':<{w}}  {prec_w:>8.3f}  {rec_w:>8.3f}  {f1_w:>8.3f}  {len(y_val):>7}")

        # ── 혼동 행렬 ──────────────────────────────────────────────
        # 행(row) = 실제 정답, 열(col) = 모델 예측 결과
        #
        #                    예측: 배경    예측: 사람
        #   실제: 배경    [ TN(맞음) ]  [ FP(오경보) ]  ← 배경을 사람으로 오판
        #   실제: 사람    [ FN(놓침) ]  [ TP(맞음)  ]  ← 사람을 배경으로 오판 (위험!)
        #
        #   TN (True Negative)  : 배경 → 배경  ✅ 정확히 맞힘
        #   FP (False Positive) : 배경 → 사람  ❌ 없는 사람 감지 (오경보)
        #   FN (False Negative) : 사람 → 배경  ❌ 실제 사람을 놓침  ← 가장 위험한 오류
        #   TP (True Positive)  : 사람 → 사람  ✅ 정확히 맞힘
        print()
        print("  ── 혼동 행렬 ──────────────────────────────")
        print(f"  {'':16}  {'예측: 배경':>12}  {'예측: 사람':>12}")
        print(f"  {'실제: 배경':16}  {cm[0][0]:>12}  {cm[0][1]:>12}")
        print(f"  {'실제: 사람':16}  {cm[1][0]:>12}  {cm[1][1]:>12}")
        print()

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
    def _load_csv(self, csv_path: str, min_check: bool = True):
        """
        CSV 파일을 읽어 (특징 행렬, 레이블 배열) 반환.
        데이터 부족 시 (None, None) 반환.

        Args:
            csv_path  : CSV 파일 경로
            min_check : True면 최소 샘플(10개) + 양 클래스 존재 여부 확인
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
        if min_check and (len(X_list) < 10 or len(np.unique(y)) < 2):
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
        """모델 가중치와 스케일러를 저장.
        - 고정 경로(mlp_weights.pt): 추론 시 자동 로드용
        - 버전 경로(mlp_L{layers}_ep{ep}_lr{lr}_{timestamp}.pt): 결과물 보관용
        """
        import datetime
        os.makedirs(os.path.dirname(self.MODEL_PATH), exist_ok=True)

        # ① 고정 경로 저장 (추론·로드용)
        torch.save(self.model.state_dict(), self.MODEL_PATH)
        with open(self.SCALER_PATH, 'wb') as f:
            pickle.dump(self.scaler, f)

        # ② 버전 파일명 생성 (시각화 파일명과 동일한 패턴)
        layers_str = '-'.join(str(h) for h in HIDDEN_LAYERS)
        timestamp  = datetime.datetime.now().strftime('%m%d_%H%M')
        lr_str     = f'{LEARNING_RATE:.0e}'
        stem       = f'mlp_L{layers_str}_ep{EPOCHS}_lr{lr_str}_{timestamp}'

        model_dir  = os.path.dirname(self.MODEL_PATH)
        ver_model  = os.path.join(model_dir, stem + '.pt')
        ver_scaler = os.path.join(model_dir, stem + '_scaler.pkl')

        torch.save(self.model.state_dict(), ver_model)
        with open(ver_scaler, 'wb') as f:
            pickle.dump(self.scaler, f)

        print(f"[MLP] 저장 완료 → {self.MODEL_PATH}  (추론용)")
        print(f"[MLP] 버전 보관 → {ver_model}")

    def _make_log_path(self, mode: str = 'train') -> str:
        """학습 로그 파일 경로 생성 (AI/logs/ 폴더).
        파일명: train_{layers}_{timestamp}.log
        """
        import datetime
        log_dir    = os.path.join(self._AI_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        layers_str = '-'.join(str(h) for h in HIDDEN_LAYERS)
        ts         = datetime.datetime.now().strftime('%m%d_%H%M%S')
        return os.path.join(log_dir, f'{mode}_L{layers_str}_ep{EPOCHS}_{ts}.log')

    def _save_history(self, history: dict) -> None:
        """에폭별 학습 이력을 JSON으로 저장하고, 이전 결과와 비교 출력"""
        history_path = os.path.join(self._AI_DIR, 'models', 'train_history.json')
        os.makedirs(os.path.dirname(history_path), exist_ok=True)

        # 이전 결과 로드 (있으면)
        prev = None
        if os.path.exists(history_path):
            try:
                with open(history_path, encoding='utf-8') as f:
                    prev = json.load(f)
            except Exception:
                pass

        # 현재 결과 저장
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f)
        print(f"[MLP] 📊 학습 이력 저장 → {history_path}")

        # 이전 결과와 비교 출력
        if prev and prev.get('val_acc'):
            prev_best = max(prev['val_acc']) * 100
            curr_best = max(history['val_acc']) * 100
            diff      = curr_best - prev_best
            sign      = '+' if diff >= 0 else ''
            print()
            print("  ── 이전 학습과 비교 ──────────────────────────────────")
            print(f"  이전 최고 검증 정확도: {prev_best:.1f}%")
            print(f"  현재 최고 검증 정확도: {curr_best:.1f}%")
            print(f"  변화: {sign}{diff:.1f}%p  {'↑ 개선' if diff > 0 else ('→ 유지' if diff == 0 else '↓ 하락')}")
            print()

    def _try_load_model(self) -> None:
        """현재 하이퍼파라미터 세팅과 일치하는 버전 모델을 우선 로드.
        없으면 고정 경로(mlp_weights.pt)로 폴백.

        탐색 패턴: mlp_L{layers}_ep{ep}_lr{lr}_*.pt
        여러 개 일치하면 가장 최근 파일(이름 기준 내림차순) 선택.
        """
        import glob

        model_dir  = os.path.dirname(self.MODEL_PATH)
        layers_str = '-'.join(str(h) for h in HIDDEN_LAYERS)
        lr_str     = f'{LEARNING_RATE:.0e}'
        pattern    = os.path.join(model_dir, f'mlp_L{layers_str}_ep{EPOCHS}_lr{lr_str}_*.pt')

        # scaler가 없는 .pt (버전 모델만) 필터링 — *_scaler.pkl 제외
        candidates = sorted(
            [p for p in glob.glob(pattern) if not p.endswith('_scaler.pkl')],
            reverse=True  # 파일명 내림차순 → 최신 타임스탬프 우선
        )

        if candidates:
            ver_model  = candidates[0]
            ver_scaler = ver_model.replace('.pt', '_scaler.pkl')
            if os.path.exists(ver_scaler):
                try:
                    state_dict = torch.load(ver_model, map_location='cpu', weights_only=True)
                    self.model.load_state_dict(state_dict)
                    with open(ver_scaler, 'rb') as f:
                        self.scaler = pickle.load(f)
                    self.model.eval()
                    self.b_is_trained = True
                    print(f"[MLP] 버전 모델 로드 → {os.path.basename(ver_model)}")
                    return
                except Exception as e:
                    print(f"[MLP] 버전 모델 로드 실패, 고정 경로로 시도: {e}")

        # 폴백: 고정 경로 (mlp_weights.pt)
        if not (os.path.exists(self.MODEL_PATH) and os.path.exists(self.SCALER_PATH)):
            return
        try:
            state_dict = torch.load(self.MODEL_PATH, map_location='cpu', weights_only=True)
            self.model.load_state_dict(state_dict)
            with open(self.SCALER_PATH, 'rb') as f:
                self.scaler = pickle.load(f)
            self.model.eval()
            self.b_is_trained = True
            print(f"[MLP] 고정 모델 로드 → {self.MODEL_PATH}")
        except Exception as e:
            print(f"[MLP] 모델 로드 실패 (재학습 필요): {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  직접 실행 시 학습 + 간단 테스트
#  $ python nn_mlp.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    TRAIN_CSV = 'AI/data_train.csv'
    VAL_CSV   = 'AI/data_val.csv'
    SIMPLE_CSV = 'svm_data.csv'

    print("=" * 60)
    print("  MLP 재실 판단 모델")
    print("=" * 60)
    print("  [1] 학습 + 검증  (AI/data_train.csv → AI/data_val.csv)")
    print("  [2] 추론만       (저장된 모델로 AI/data_val.csv 평가)")
    print("  [3] 간단 학습    (svm_data.csv 하나로 학습+내부 검증)")
    print("=" * 60)

    while True:
        choice = input("모드 선택 (1 / 2 / 3): ").strip()
        if choice in ('1', '2', '3'):
            break
        print("  1, 2, 3 중 하나를 입력하세요.")

    module = MLP_Module()

    if choice == '2':
        print(f"\n[모드] 추론 — 학습 없이 저장된 모델로 평가")
        module.evaluate(val_csv=VAL_CSV)

    elif choice == '1':
        if not (os.path.exists(TRAIN_CSV) and os.path.exists(VAL_CSV)):
            print(f"\n⚠️  학습/검증 파일 없음. 먼저 prepare_data.py 를 실행하세요:")
            print(f"    python3 AI/prepare_data.py")
        else:
            success = module.train_eval(train_csv=TRAIN_CSV, val_csv=VAL_CSV)
            if success:
                print("\n✅ 학습+검증 완료! AI/models/ 폴더에 모델이 저장되었습니다.")
            else:
                print("\n❌ 학습 실패.")

    else:  # choice == '3'
        success = module.train(csv_path=SIMPLE_CSV)
        if success:
            print("\n✅ 학습 완료! AI/models/ 폴더에 모델이 저장되었습니다.")
            print("   다음 실행 시 자동으로 로드됩니다.")
        else:
            print("\n❌ 학습 실패.")
            print(f"   {SIMPLE_CSV} 가 있고, 배경/사람 데이터가 각각 있는지 확인하세요.")

