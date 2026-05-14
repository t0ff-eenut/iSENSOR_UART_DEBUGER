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
import logging
import time as _time

# nn_mlp 전용 로거 — debugger_start.py 에서 핸들러를 추가해 GUI 경고창 연동
logger = logging.getLogger('nn_mlp')
import pickle
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import train_test_split

# svm.py는 AI/svm/ 폴더에 위치하므로 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'svm'))

# svm.py의 enum_label, A_feature_indices 재사용
import svm


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  학습 로그 저장용 Tee (stdout → 콘솔 + 파일 동시 출력)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _Tee:
    """sys.stdout을 콘솔, 파일, GUI 콜백에 동시에 기록하는 멀티 스트림."""
    def __init__(self, orig, f, log_cb=None):
        self._orig   = orig
        self._f      = f
        self._log_cb = log_cb
        self._buf    = ""
    def write(self, s):
        self._orig.write(s)
        self._f.write(s)
        self._f.flush()          # 실시간 파일 반영
        if self._log_cb:
            self._buf += s
            while '\n' in self._buf:
                line, self._buf = self._buf.split('\n', 1)
                if line.strip():
                    self._log_cb(line)
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

# ── 정규화 설정 ──────────────────────────────────────────────────
# Weight Decay (L2 정규화): 가중치 크기에 패널티를 부여해 과적합 억제
#   0.0    = 비활성화 (기본값)
#   1e-5   = 약한 정규화 (train-val 갭 -0.3~0.5%p 기대)
#   1e-4   = 중간 정규화 (권장 시작점, -0.5~1.5%p 기대)
#   5e-4   = 강한 정규화 (val acc 소폭 하락 가능)
WEIGHT_DECAY = 0.0

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

    def __init__(self, input_size: int,
                 hidden_layers: list = None,
                 dropout_rate: float = None):
        super().__init__()
        _layers  = hidden_layers if hidden_layers is not None else HIDDEN_LAYERS
        _dropout = dropout_rate  if dropout_rate  is not None else DROPOUT_RATE

        layers = []
        in_size = input_size

        for i, h_size in enumerate(_layers):
            layers.append(nn.Linear(in_size, h_size))

            # 첫 번째 은닉층에만 BatchNorm + Dropout 적용
            if i == 0:
                layers.append(nn.BatchNorm1d(h_size))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(p=_dropout))
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

        # 모델 & 스케일러 초기화
        # feature_indices / input_size 는 property — _svm_ref.A_feature_indices를 항상 참조
        self.model:  OccupancyMLP  = OccupancyMLP(self.input_size)
        self.scaler: StandardScaler = StandardScaler()

        # SVM_Module과 동일한 결과 속성
        self.b_is_trained: bool  = False
        self.i_label: int        = svm.enum_label.LABEL_BACKGROUND
        self.A_probability: list = [1.0, 0.0]
        self.f_confidence: float = 0.0

        # 실시간 추론용 캐시 (mlp() 호출 시 갱신)
        self._A_fft_mags_cache: list = []   # FFT magnitude (esp32_fft 모드용)
        self._A_adc_cache: list      = []   # ADC 샘플 (pc 모드 실시간 추론용)

        # 이전에 저장된 모델이 있으면 자동 로드
        self._try_load_model()

    # ─────────────────────────────────────────────────────────
    # 특징 인덱스 / 입력 크기 (항상 _svm_ref 기준으로 읽음)
    # ─────────────────────────────────────────────────────────
    @property
    def feature_indices(self) -> list:
        """GUI 특징 선택 변경 시 MLP도 자동으로 반영"""
        return self._svm_ref.A_feature_indices

    @feature_indices.setter
    def feature_indices(self, value: list):
        self._svm_ref.A_feature_indices = value

    @property
    def input_size(self) -> int:
        return len(self._svm_ref.A_feature_indices)

    @property
    def _feat_mode(self) -> str:
        """스케일러 특징 수에서 학습 모드를 추론 (21→esp32, 36→esp32_fft, 25→pc)."""
        n = getattr(self.scaler, 'n_features_in_', self.input_size)
        if n == svm.I_FEATURES_COUNT_EXTENDED:
            return 'esp32_fft'
        if n == 25:
            return 'pc'
        return 'esp32'

    # ─────────────────────────────────────────────────────────
    # 외부에서 호출하는 메인 함수 (svm.svm()과 동일한 시그니처)
    # ─────────────────────────────────────────────────────────
    def mlp(self, input_ft, A_fft_mags=None, A_adc=None):
        """
        UART 수신 FftFeaturesData로 재실 여부를 판단합니다.
        (SVM_Module.svm()과 동일한 반환값 구조)

        Args:
            input_ft   : FftFeaturesData — None이면 무시
            A_fft_mags : FFT magnitude 배열 (esp32_fft 모드 추론 시 필요)
            A_adc      : ADC 샘플 배열 (pc 모드 실시간 추론 시 필요)

        Returns:
            (A_probability, i_label, f_confidence)
        """
        if input_ft is None:
            return (self.A_probability, self.i_label, self.f_confidence)

        # SVM 참조 객체에 ft 등록
        self._svm_ref.ft = input_ft

        # 캐시 갱신
        if A_fft_mags is not None:
            self._A_fft_mags_cache = A_fft_mags
        if A_adc is not None:
            self._A_adc_cache = A_adc

        # 학습된 경우에만 예측
        if self.b_is_trained:
            self._predict()

        return (self.A_probability, self.i_label, self.f_confidence)

    # ─────────────────────────────────────────────────────────
    # 학습
    # ─────────────────────────────────────────────────────────
    def _count_csv_rows(self, csv_path: str) -> int:
        """CSV 파일(또는 폴더)의 데이터 행 수만 빠르게 카운트 (헤더 제외)."""
        import glob as _glob
        if os.path.isdir(csv_path):
            csv_files = sorted(_glob.glob(os.path.join(csv_path, 'svm_data*.csv')))
        elif os.path.isfile(csv_path):
            csv_files = [csv_path]
        else:
            return 0
        count = 0
        for fpath in csv_files:
            with open(fpath, 'r') as f:
                count += sum(1 for row in f if row.strip()) - 1  # 헤더 제외
        return max(count, 0)

    def _compute_stem(self, hidden_layers, epochs, learning_rate,
                       dropout_rate, batch_size, feature_mode, scaler_type,
                       lr_scheduler_patience=None, lr_scheduler_factor=None,
                       weight_decay=None,
                       n_samples=0) -> str:
        """모델/로그 파일명 공통 stem 생성
        형식: MLP_{n_samples}_F{n_feat}{_PC?}_L{layers}{_rb?}_b{batch}_D{dropout}_LR{lr}_LRF{factor}_LRP{patience}{_WD?}_ep{epochs}_{date}_{time}
        """
        import datetime, math as _m
        # Layer 구조
        layers_str = '-'.join(str(h) for h in hidden_layers)
        # Scaler 태그
        scaler_tag = '_rb' if scaler_type == 'robust' else ''
        # Dropout  (0.3 → 'D3')
        do_str     = str(dropout_rate).replace('0.', 'D')
        # LR  (e.g. 1e-3, 5e-4)
        _exp   = int(_m.floor(_m.log10(learning_rate)))
        _man   = round(learning_rate / (10 ** _exp), 1)
        _man_s = str(int(_man)) if _man == int(_man) else str(_man)
        lr_str = f'{_man_s}e{_exp}'
        # LR factor  (0.5 → 'LRF5', 0.1 → 'LRF1')
        _lrf     = lr_scheduler_factor   if lr_scheduler_factor   is not None else LR_SCHEDULER_FACTOR
        _lrf_tag = str(_lrf).replace('0.', '').replace('.', '')
        # LR patience  (10 → 'LRP10')
        _lrp     = lr_scheduler_patience if lr_scheduler_patience is not None else LR_SCHEDULER_PATIENCE
        # Feature mode 태그
        mode_tag = '_PC' if feature_mode == 'pc' else ''
        n_feat   = self.input_size
        # Weight Decay 태그 (0이면 생략)
        _wd      = weight_decay if weight_decay is not None else WEIGHT_DECAY
        _wd_tag  = '' if _wd == 0.0 else f'_WD{_wd:.0e}'.replace('e-0', 'e-').replace('e+0', 'e')
        ts       = datetime.datetime.now().strftime('%m%d_%H%M%S')
        return (f'MLP_{n_samples}_F{n_feat}{mode_tag}'
                f'_L{layers_str}{scaler_tag}'
                f'_b{batch_size}_{do_str}'
                f'_LR{lr_str}_LRF{_lrf_tag}_LRP{_lrp}{_wd_tag}'
                f'_ep{epochs}_{ts}')

    def train(self, csv_path: str = "svm_data.csv",
              progress_callback=None, log_callback=None,
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
              lr_scheduler_factor: float = None,
              weight_decay: float = None,
              filter_stride: int = None,
              filter_interval: int = None,
              filter_mode: str = 'match',
              use_cam_label: bool = False) -> bool:
        """
        CSV 파일을 로드해 MLP를 학습합니다.

        학습 흐름:
          CSV 로드
            ↓
          선택된 24개 특징만 추출
            ↓
          train(80%) / val(20%) 분리
            ↓
          StandardScaler/RobustScaler로 정규화
            ↓
          DataLoader 생성 (미니배치 학습)
            ↓
          EPOCHS 번 반복:
            · 순전파 → 손실 계산 → 역전파 → 가중치 업데이트
            · 검증 정확도 출력
            ↓
          모델 저장 (models/ 폴더)

        Args:
            csv_path          : 학습 데이터 CSV 경로
            progress_callback : 매 에폭 호출되는 콜백 (epoch, total, loss, train_acc, val_acc)
                                GUI 실시간 진행 표시용. None이면 무시.

        Returns:
            True: 학습 성공 / False: 데이터 부족 또는 파일 없음
        """
        # 파라미터 기본값 확정 (stem 생성에 동일하게 사용)
        _epochs    = epochs        if epochs        is not None else EPOCHS
        _lr        = learning_rate if learning_rate is not None else LEARNING_RATE
        _hidden    = hidden_layers if hidden_layers is not None else HIDDEN_LAYERS
        _dropout   = dropout_rate  if dropout_rate  is not None else DROPOUT_RATE
        _batch     = batch_size    if batch_size    is not None else BATCH_SIZE
        _feat_mode = feature_mode  if feature_mode  is not None else 'esp32'
        _scaler_tp = scaler_type   if scaler_type   is not None else 'standard'

        # CSV 데이터 수 미리 카운트 → stem에 반영
        _n_samples = self._count_csv_rows(csv_path)

        # stem 확정 → 로그 파일명 & 모델 파일명 모두 이 stem 사용
        stem       = self._compute_stem(_hidden, _epochs, _lr, _dropout, _batch,
                                        _feat_mode, _scaler_tp,
                                        lr_scheduler_patience, lr_scheduler_factor,
                                        weight_decay=weight_decay,
                                        n_samples=_n_samples)
        log_dir    = os.path.join(self._AI_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path   = os.path.join(log_dir, stem + '.log')

        _log_f     = open(log_path, 'w', encoding='utf-8')
        _orig_out  = sys.stdout
        sys.stdout = _Tee(_orig_out, _log_f, log_cb=log_callback)
        try:
            return self._train_impl(csv_path, progress_callback,
                                    epochs=_epochs,
                                    learning_rate=_lr,
                                    early_stop_patience=early_stop_patience,
                                    hidden_layers=_hidden,
                                    dropout_rate=_dropout,
                                    batch_size=_batch,
                                    val_ratio=val_ratio,
                                    random_state=random_state,
                                    stratify=stratify,
                                    log_interval=log_interval,
                                    feature_mode=_feat_mode,
                                    scaler_type=_scaler_tp,
                                    lr_scheduler_patience=lr_scheduler_patience,
                                    lr_scheduler_factor=lr_scheduler_factor,
                                    weight_decay=weight_decay,
                                    filter_stride=filter_stride,
                                    filter_interval=filter_interval,
                                    filter_mode=filter_mode,
                                    use_cam_label=use_cam_label,
                                    model_stem=stem)
        finally:
            sys.stdout = _orig_out
            _log_f.close()
            print(f"[MLP] 📝 학습 로그 저장 → {log_path}")

    def _train_impl(self, csv_path: str, progress_callback=None,
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
                    lr_scheduler_factor: float = None,
                    weight_decay: float = None,
                    filter_stride: int = None,
                    filter_interval: int = None,
                    filter_mode: str = 'match',
                    use_cam_label: bool = False,
                    model_stem: str = None) -> bool:
        # 파라미터 기본값 설정 (train()에서 이미 확정되어 넘어오지만 단돈 방어)
        _epochs       = epochs        if epochs        is not None else EPOCHS
        _lr           = learning_rate if learning_rate is not None else LEARNING_RATE
        _patience     = early_stop_patience if early_stop_patience is not None else 20
        _hidden       = hidden_layers if hidden_layers is not None else HIDDEN_LAYERS
        _dropout      = dropout_rate  if dropout_rate  is not None else DROPOUT_RATE
        _batch_size   = batch_size    if batch_size    is not None else BATCH_SIZE
        _val_ratio    = val_ratio     if val_ratio     is not None else VAL_RATIO
        _random_state = random_state  if random_state  is not None else 42
        _stratify     = stratify      if stratify      is not None else True
        _log_interval = log_interval  if log_interval  is not None else 10
        _feat_mode    = feature_mode  if feature_mode  is not None else 'esp32'
        _scaler_type  = scaler_type   if scaler_type   is not None else 'standard'
        _lr_patience  = lr_scheduler_patience if lr_scheduler_patience is not None else LR_SCHEDULER_PATIENCE
        _lr_factor    = lr_scheduler_factor   if lr_scheduler_factor   is not None else LR_SCHEDULER_FACTOR
        _wd           = weight_decay  if weight_decay  is not None else WEIGHT_DECAY

        # ① CSV 로드
        X_raw, y = self._load_csv(csv_path,
                                  filter_stride=filter_stride,
                                  filter_interval=filter_interval,
                                  filter_mode=filter_mode,
                                  use_cam_label=use_cam_label)
        if X_raw is None:
            print("[MLP] ❌ 데이터 부족 또는 파일 없음 — 학습 불가")
            return False

        n_samples = len(y)
        n_bg    = int(np.sum(y == 0))
        n_human = int(np.sum(y == 1))
        print(f"[MLP] 로드 완료 | 전체: {n_samples}개  (배경: {n_bg}, 사람: {n_human})")

        # ② 특징 추출 (모드에 따라 분기)
        _mlp_dir = os.path.dirname(os.path.abspath(__file__))
        if _mlp_dir not in sys.path:
            sys.path.insert(0, _mlp_dir)

        if _feat_mode == 'pc':
            from pc_feature_extractor import extract_pc_features_from_adc_batch, PC_FEATURE_NAMES
            X = extract_pc_features_from_adc_batch(X_raw)   # ADC → numpy FFT → (N, 25)
            _feat_names_display = PC_FEATURE_NAMES
            print(f"[MLP] 특징 모드: PC-ADC재계산 ({len(PC_FEATURE_NAMES)}개)")
        elif _feat_mode == 'esp32_fft':
            from pc_feature_extractor import FFT_START_COL
            fft_low_cols = list(range(FFT_START_COL + 1, FFT_START_COL + 16))  # fft_1 ~ fft_15
            if X_raw.shape[1] <= max(fft_low_cols):
                print("[MLP] ❌ esp32_fft 모드: CSV에 FFT 컬럼 없음 (save_sample 시 A_fft_mag 저장 필요)")
                return False
            X_base    = X_raw[:, self.feature_indices]        # (N, 21)
            X_fft_low = X_raw[:, fft_low_cols]               # (N, 15)
            X = np.concatenate([X_base, X_fft_low], axis=1)  # (N, 36)
            _feat_names_display = (
                [svm.enum_csv_col(i).name for i in self.feature_indices]
                + [f'fft_{i}' for i in range(1, 16)]
            )
            print(f"[MLP] 특징 모드: ESP32+저주파FFT ({X.shape[1]}개)")
        else:  # 'esp32'
            X = X_raw[:, self.feature_indices]
            _feat_names_display = [svm.enum_csv_col(i).name for i in self.feature_indices]
            print(f"[MLP] 특징 모드: ESP32 ({len(self.feature_indices)}개)")

        # ③ train/val 분리
        #    stratify=y : 각 클래스 비율을 유지하면서 분리
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=_val_ratio,
            random_state=_random_state if _random_state >= 0 else None,
            stratify=y if _stratify else None
        )
        _rs_str = str(_random_state) if _random_state >= 0 else '랜덤'
        _st_str = '유지' if _stratify else '미사용'
        print(f"[MLP] 학습: {len(y_train)}개 ({1-_val_ratio:.0%})  검증: {len(y_val)}개 ({_val_ratio:.0%})  [비율고정: {_st_str} | 분리시드: {_rs_str}]")

        # ④ 정규화
        #    fit_transform : 훈련 데이터 기준으로 평균/분산 계산 + 변환
        #    transform     : 검증 데이터는 훈련 기준으로만 변환 (정보 누수 방지)
        if _scaler_type == 'robust':
            self.scaler = RobustScaler()   # 중앙값/IQR 기반 — 이상치 진동한 환경에 강건
        else:
            self.scaler = StandardScaler() # z-score 기반 — 기본값
        _scaler_tag = 'robust' if _scaler_type == 'robust' else 'std'
        print(f"[MLP] 스케일러: {'RobustScaler (중앙값/IQR)' if _scaler_type == 'robust' else 'StandardScaler (z-score)'}")
        X_train = self.scaler.fit_transform(X_train).astype(np.float32)
        X_val   = self.scaler.transform(X_val).astype(np.float32)

        # ⑤ 배치 크기 조정 (데이터가 너무 적으면 batch_size 줄임)
        effective_batch = min(_batch_size, max(2, n_samples // 4))

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
        _n_features = X_train.shape[1]   # ESP32 or PC 특징 수
        _device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = OccupancyMLP(_n_features,
                                  hidden_layers=_hidden,
                                  dropout_rate=_dropout).to(_device)

        # CrossEntropyLoss:
        #   내부적으로 Softmax + NLLLoss를 합친 다중 분류 손실함수
        #   출력 logit을 그대로 넣으면 됨 (별도 Softmax 불필요)
        criterion = nn.CrossEntropyLoss().to(_device)

        # Adam 옵티마이저:
        #   SGD(확률적 경사하강법)의 개선판
        #   파라미터마다 학습률을 자동으로 조절 → 빠르고 안정적
        #   weight_decay: L2 정규화 계수 (0 = 비활성화, 1e-4 정도 권장)
        optimizer = optim.Adam(self.model.parameters(), lr=_lr, weight_decay=_wd)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', patience=_lr_patience,
            factor=_lr_factor, min_lr=1e-6
        )
        # ⑦ 에폭 반복 학습
        layers_str = ' → '.join(str(h) for h in _hidden)
        _es_str    = f"patience={_patience}" if _patience > 0 else "비활성화"
        _st_str2   = '유지' if _stratify else '미사용'
        _rs_str2   = str(_random_state) if _random_state >= 0 else '랜덤'
        _sc_str    = 'RobustScaler' if _scaler_type == 'robust' else 'StandardScaler'
        _fm_str    = {'pc': 'PC-ADC재계산', 'esp32_fft': 'ESP32+저주파FFT'}.get(_feat_mode, 'ESP32')
        print(f"[MLP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"[MLP]  디바이스: {_device}" + (f" ({torch.cuda.get_device_name(0)})" if _device.type == 'cuda' else ""))
        print(f"[MLP]  구조: {_n_features} → {layers_str} → 2")
        print(f"[MLP]  에폭: {_epochs}  배치: {effective_batch}  LR: {_lr:.2e}  Dropout: {_dropout}")
        print(f"[MLP]  Early Stop: {_es_str}")
        print(f"[MLP]  LR 스케줄러: patience={_lr_patience}  factor={_lr_factor}  min_lr=1e-6")
        print(f"[MLP]  Weight Decay (L2): {_wd:.0e}" + (" (비활성화)" if _wd == 0.0 else " (정규화 활성화)"))
        print(f"[MLP]  검증 비율: {_val_ratio:.0%}  분리 비율고정: {_st_str2}  분리 시드: {_rs_str2}")
        print(f"[MLP]  스케일러: {_sc_str}  특징 모드: {_fm_str}")
        # 사용 특징 출력
        print(f"[MLP]  사용 특징 ({len(_feat_names_display)}개): {', '.join(_feat_names_display)}")
        print(f"[MLP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        best_val_acc   = 0.0
        best_state     = None
        no_improve_cnt = 0
        history = {'epochs': [], 'train_loss': [], 'val_loss': [], 'train_acc': [], 'val_acc': [], 'lr': []}
        _train_start = _time.perf_counter()

        for epoch in range(1, _epochs + 1):
            _epoch_start = _time.perf_counter()

            # ── 학습 단계 ─────────────────────────────────
            self.model.train()  # train 모드: Dropout 활성화

            total_loss = 0.0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(_device)
                y_batch = y_batch.to(_device)
                optimizer.zero_grad()                  # 이전 기울기 초기화
                logits = self.model(X_batch)           # 순전파
                loss   = criterion(logits, y_batch)    # 손실 계산
                loss.backward()                        # 역전파 (기울기 계산)
                optimizer.step()                       # 가중치 업데이트
                total_loss += loss.item()

            avg_loss  = total_loss / len(train_loader)
            val_loss  = self._evaluate_loss(val_loader, criterion, _device)
            train_acc = self._evaluate(train_loader, _device)
            val_acc   = self._evaluate(val_loader, _device)
            scheduler.step(val_loss)

            current_lr = optimizer.param_groups[0]['lr']
            history['epochs'].append(epoch)
            history['train_loss'].append(round(avg_loss, 6))
            history['val_loss'].append(round(val_loss, 6))
            history['train_acc'].append(round(train_acc, 6))
            history['val_acc'].append(round(val_acc, 6))
            history['lr'].append(round(current_lr, 10))

            # GUI 실시간 진행 콜백 (False 반환 시 학습 중단)
            if progress_callback is not None:
                if progress_callback(epoch, _epochs, avg_loss, val_loss, train_acc, val_acc) is False:
                    print(f"[MLP] ⏹ 학습 중단 요청 — {epoch}에폭에서 중단")
                    break

            # Best checkpoint 저장
            if val_acc > best_val_acc:
                best_val_acc   = val_acc
                best_state     = {k: v.clone() for k, v in self.model.state_dict().items()}
                no_improve_cnt = 0
            else:
                no_improve_cnt += 1

            if epoch % _log_interval == 0:
                _epoch_sec = _time.perf_counter() - _epoch_start
                star = " ★" if no_improve_cnt == 0 else ""
                print(f"  에폭 {epoch:3d}/{_epochs} | 손실: {avg_loss:.4f} | 검증손실: {val_loss:.4f} | 학습: {train_acc:.1%} | 검증: {val_acc:.1%} | lr: {current_lr:.2e} | {_epoch_sec:.1f}s{star}")

            # Early stopping
            if _patience > 0 and no_improve_cnt >= _patience:
                print(f"[MLP] ⏹ Early stopping — {epoch}에폭 (검증 정확도 {_patience}에폭간 개선 없음)")
                break

        # Best checkpoint 복원 후 저장
        if best_state is not None:
            self.model.load_state_dict(best_state)
        _total_sec  = _time.perf_counter() - _train_start
        _total_m, _total_s = divmod(int(_total_sec), 60)
        print(f"[MLP] ✅ 학습 완료 | [{layers_str}] | 최고 검증 정확도: {best_val_acc:.1%}  (베스트 체크포인트 복원됨)")
        print(f"[MLP] ⏱  전체 학습 시간: {_total_m}분 {_total_s}초 ({_total_sec:.1f}s)")

        # 추가 비교 지표 계산 (best 체크포인트 복원 후 val 데이터 기준)
        from sklearn.metrics import precision_recall_fscore_support as _prf, confusion_matrix as _sk_cm
        self.model.eval()
        with torch.no_grad():
            _val_preds = self.model(torch.tensor(X_val).to(_device)).argmax(dim=1).cpu().numpy()
        _, _rec, _f1, _ = _prf(y_val, _val_preds, labels=[0, 1], zero_division=0)
        _cm = _sk_cm(y_val, _val_preds)
        _TN, _FP = int(_cm[0][0]), int(_cm[0][1])
        _FN, _TP = int(_cm[1][0]), int(_cm[1][1])
        _bg_fpr  = _FP / (_TN + _FP) if (_TN + _FP) > 0 else 0.0
        _bg_tnr  = _TN / (_TN + _FP) if (_TN + _FP) > 0 else 0.0
        _human_fnr = _FN / (_FN + _TP) if (_FN + _TP) > 0 else 0.0
        _best_idx = history['val_acc'].index(max(history['val_acc']))
        history['best_epoch']   = history['epochs'][_best_idx]
        history['min_val_loss'] = round(min(history['val_loss']), 6) if history.get('val_loss') else None
        history['human_recall'] = round(float(_rec[1]), 4)   # TPR: 사람 탐지율
        history['human_fnr']    = round(float(_human_fnr), 4)  # FNR: 사람 오탐율(눈침)
        history['bg_tnr']       = round(float(_bg_tnr), 4)     # TNR: 배경 정확 탐지율
        history['bg_fpr']       = round(float(_bg_fpr), 4)     # FPR: 배경 오탐율(오경보)
        history['f1_human']     = round(float(_f1[1]), 4)

        # ⑧ Permutation Importance 출력 + 저장
        _importance  = self._permutation_importance(X_val, y_val, _feat_names_display, device=_device)

        # ⑨ 모델 저장 후 완료 플래그 설정
        self._save_model(history=history, importance=_importance, feature_mode=_feat_mode,
                         hidden_layers=_hidden, epochs=_epochs,
                         learning_rate=_lr, dropout_rate=_dropout, batch_size=effective_batch,
                         stem=model_stem)
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
        stem     = self._compute_stem(HIDDEN_LAYERS, EPOCHS, LEARNING_RATE,
                                      DROPOUT_RATE, BATCH_SIZE, 'esp32', 'standard')
        log_dir  = os.path.join(self._AI_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, stem + '.log')

        _log_f     = open(log_path, 'w', encoding='utf-8')
        _orig_out  = sys.stdout
        sys.stdout = _Tee(_orig_out, _log_f)
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

        # ⑥ 모델 / 손실함수 / 옵티마이저 초기화 (train_eval 전용 — 상수 그대로 사용)
        self.model = OccupancyMLP(self.input_size,
                                  hidden_layers=HIDDEN_LAYERS,
                                  dropout_rate=DROPOUT_RATE)
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
        history = {'epochs': [], 'train_loss': [], 'val_loss': [], 'train_acc': [], 'val_acc': [], 'lr': []}

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

            current_lr = optimizer.param_groups[0]['lr']
            history['epochs'].append(epoch)
            history['train_loss'].append(round(avg_loss, 6))
            history['train_acc'].append(round(train_acc, 6))
            history['val_acc'].append(round(val_acc, 6))
            history['lr'].append(round(current_lr, 10))

            if epoch % 10 == 0:
                print(f"  에폭 {epoch:3d}/{EPOCHS} | 손실: {avg_loss:.4f} | 학습: {train_acc:.1%} | 검증: {val_acc:.1%} | lr: {current_lr:.2e}")
                if val_acc > best_val_acc:
                    best_val_acc = val_acc

        # ⑧ 최종 상세 평가
        print(f"\n[MLP] ── 최종 검증 결과 ─────────────────────────────")
        self._evaluate_detail(X_val, y_val)
        print(f"[MLP] ✅ 학습 완료 | [{layers_str}] | 최고 검증 정확도: {best_val_acc:.1%}")

        # 추가 비교 지표 계산
        from sklearn.metrics import precision_recall_fscore_support as _prf, confusion_matrix as _sk_cm
        _te_device = next(self.model.parameters()).device
        self.model.eval()
        with torch.no_grad():
            _val_preds = self.model(torch.tensor(X_val).to(_te_device)).argmax(dim=1).cpu().numpy()
        _, _rec, _f1, _ = _prf(y_val, _val_preds, labels=[0, 1], zero_division=0)
        _cm = _sk_cm(y_val, _val_preds)
        _TN, _FP = int(_cm[0][0]), int(_cm[0][1])
        _FN, _TP = int(_cm[1][0]), int(_cm[1][1])
        _bg_fpr    = _FP / (_TN + _FP) if (_TN + _FP) > 0 else 0.0
        _bg_tnr    = _TN / (_TN + _FP) if (_TN + _FP) > 0 else 0.0
        _human_fnr = _FN / (_FN + _TP) if (_FN + _TP) > 0 else 0.0
        _best_idx = history['val_acc'].index(max(history['val_acc']))
        history['best_epoch']   = history['epochs'][_best_idx]
        history['min_val_loss'] = round(min(history['val_loss']), 6) if history.get('val_loss') else None
        history['human_recall'] = round(float(_rec[1]), 4)     # TPR: 사람 탐지율
        history['human_fnr']    = round(float(_human_fnr), 4)  # FNR: 사람 오탐(눈침)
        history['bg_tnr']       = round(float(_bg_tnr), 4)     # TNR: 배경 정확 탐지율
        history['bg_fpr']       = round(float(_bg_fpr), 4)     # FPR: 배경 오탐(오경보)
        history['f1_human']     = round(float(_f1[1]), 4)

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
        self._feat_mode 에 따라 특징 벡터를 구성하고 재실 여부를 예측합니다.
        결과를 self.i_label, self.f_confidence에 저장합니다.
        """
        svm_ref = self._svm_ref
        if svm_ref.ft is None:
            return

        mode = self._feat_mode

        if mode == 'esp32_fft':
            # 21개 UART 특징 + 저주파 FFT magnitude 빈 1~15 (15개) = 36개
            base = svm.feature_vector_from_uart(svm_ref.ft).astype(np.float32)
            if len(self._A_fft_mags_cache) >= 16:
                fft_low = np.array(self._A_fft_mags_cache[1:16], dtype=np.float32)
            else:
                fft_low = np.zeros(15, dtype=np.float32)
            X_feat = np.concatenate([base, fft_low]).reshape(1, -1)
        elif mode == 'pc':
            # ADC 샘플 → numpy FFT → 25개 PC 특징
            if len(self._A_adc_cache) < 16:
                return  # ADC 데이터 없으면 스킵
            _mlp_dir = os.path.dirname(os.path.abspath(__file__))
            if _mlp_dir not in sys.path:
                sys.path.insert(0, _mlp_dir)
            from pc_feature_extractor import compute_pc_features_realtime
            X_feat = compute_pc_features_realtime(self._A_adc_cache).reshape(1, -1).astype(np.float32)
        else:  # 'esp32'
            A_full = svm.feature_vector_from_uart(svm_ref.ft).astype(np.float32)
            X_feat = A_full[self.feature_indices].reshape(1, -1)

        # 스케일러 특징 수 불일치 시 예측 스킵 (호환 불가 모델 로드 방지)
        if hasattr(self.scaler, 'n_features_in_') and self.scaler.n_features_in_ != X_feat.shape[1]:
            if not getattr(self, '_b_feat_mismatch_warned', False):
                self._b_feat_mismatch_warned = True  # QMessageBox 블로킹 전에 먼저 설정 (재진입 방지)
                self.b_is_trained = False            # 재진입 시 mlp() 호출 차단
                # logger.warning(
                #     "스케일러 특징 수 불일치: 로드된 모델은 %d개를 기대하지만 현재 입력은 %d개입니다.\n"
                #     "호환되는 모델(21-특징)로 재학습하거나 올바른 .pt 파일을 선택하세요.",
                #     self.scaler.n_features_in_, X_feat.shape[1]
                # )

                logger.warning(
                    "MLP 모델 자동 로드 실패 — 특징 수 불일치\n"
                    "모델이 기대하는 특징 수: %d개  /  현재 설정: %d개\n"
                    "\n호환되는 모델(특징 : %d)을 선택하거나 재학습하세요.",
                    self.scaler.n_features_in_, X_feat.shape[1], X_feat.shape[1]
                )

            else:
                self.b_is_trained = False
            return
        self._b_feat_mismatch_warned = False  # 정상 상태 시 플래그 초기화
        X_scaled = self.scaler.transform(X_feat)

        # 추론 모드 (eval): Dropout 비활성화, BatchNorm 고정 통계 사용
        self.model.eval()
        _device = next(self.model.parameters()).device
        with torch.no_grad():  # 기울기 계산 비활성 → 메모리 절약, 속도 향상
            logits    = self.model(torch.tensor(X_scaled).to(_device))
            # softmax: logit → 확률 (합계 = 1.0)
            probs     = torch.softmax(logits, dim=1).cpu().numpy()[0]
            pred_idx  = int(np.argmax(probs))  # 더 높은 확률의 클래스 선택

        self.A_probability = probs.tolist()           # [배경 확률, 사람 확률]
        self.i_label       = pred_idx                 # 0 or 1
        self.f_confidence  = float(probs[pred_idx])   # 선택된 클래스의 확률

    # ─────────────────────────────────────────────────────────
    # 내부 유틸리티
    # ─────────────────────────────────────────────────────────
    def _load_csv(self, csv_path: str, min_check: bool = True,
                  filter_stride: int = None, filter_interval: int = None,
                  filter_mode: str = 'match', use_cam_label: bool = False):
        """
        CSV 파일 또는 폴더 경로를 받아 (특징 행렬, 레이블 배열) 반환.
        폴더이면 svm_data*.csv 전체를 병합해 로드.
        데이터 부족 시 (None, None) 반환.

        Args:
            csv_path        : CSV 파일 경로 또는 data_csv/ 폴더 경로
            min_check       : True면 최소 샘플(10개) + 양 클래스 존재 여부 확인
            filter_stride   : 필터 목표 stride 값 (None = 필터 없음)
            filter_interval : 필터 목표 interval 값 (None = 필터 없음)
            filter_mode     : 'match'      = 태그 매칭 (stride/interval이 정확히 일치하는 행만)
                              'downsample' = 다운샘플링 (목표 주기 비율로 N번째 행 추출)
        """
        import glob as _glob

        _filt_s = filter_stride   if (filter_stride   is not None and filter_stride   > 0) else None
        _filt_i = filter_interval if (filter_interval is not None and filter_interval > 0) else None
        _target_ms = (_filt_s or 1) * (_filt_i or 1) * 10 if (_filt_s or _filt_i) else None

        # 폴더면 svm_data*.csv 전체 병합
        if os.path.isdir(csv_path):
            csv_files = sorted(_glob.glob(os.path.join(csv_path, "svm_data*.csv")))
        elif os.path.isfile(csv_path):
            csv_files = [csv_path]
        else:
            print(f"[MLP] ❌ 파일/폴더 없음: {csv_path}")
            return None, None

        if not csv_files:
            print(f"[MLP] ❌ CSV 파일 없음: {csv_path}")
            return None, None

        X_list, y_list = [], []
        n_skipped_total = 0
        for fpath in csv_files:
            before = len(X_list)
            n_skipped = 0
            _period_counters: dict = {}   # 다운샘플링용 row_ms별 카운터
            with open(fpath, 'r') as f:
                reader = csv.reader(f)
                header = next(reader, None)  # 헤더 한 줄 건너뜀
                # stride/interval 컬럼 인덱스 탐색 (없으면 None)
                _stride_idx   = header.index('stride')   if header and 'stride'   in header else None
                _interval_idx = header.index('interval') if header and 'interval' in header else None
                # 카메라 메타 컬럼 인덱스 탐색 (학습 특징에서 제외해야 함)
                _CAM_META_COLS = ('cam_label', 'cam_hm_conf', 'cam_bg_conf', 'timestamp')
                _cam_meta_indices = [header.index(c) for c in _CAM_META_COLS if header and c in header]
                _cam_label_idx = header.index('cam_label') if header and 'cam_label' in header else None
                for row in reader:
                    if not row:
                        continue
                    row_s = int(float(row[_stride_idx]))   if _stride_idx   is not None else 1
                    row_i = int(float(row[_interval_idx])) if _interval_idx is not None else 1

                    if filter_mode == 'match':
                        # ── 태그 매칭: stride/interval이 정확히 일치하는 행만 통과 ──
                        if _filt_s is not None and _stride_idx is not None:
                            if row_s != _filt_s:
                                n_skipped += 1
                                continue
                        if _filt_i is not None and _interval_idx is not None:
                            if row_i != _filt_i:
                                n_skipped += 1
                                continue
                    elif filter_mode == 'downsample' and _target_ms is not None:
                        # ── 다운샘플링: 목표 주기(target_ms) 기준으로 N번째 행 추출 ──
                        # target_ms = filter_stride * filter_interval * 10ms
                        # row_ms    = row_stride   * row_interval    * 10ms
                        # step      = target_ms // row_ms  (목표 주기가 row 주기보다 크거나 같아야 함)
                        row_ms = row_s * row_i * 10
                        if row_ms > _target_ms or _target_ms % row_ms != 0:
                            # row 주기가 목표보다 크거나, 배수 관계가 아니면 제외
                            n_skipped += 1
                            continue
                        step = _target_ms // row_ms
                        cnt = _period_counters.get(row_ms, 0)
                        _period_counters[row_ms] = cnt + 1
                        if cnt % step != 0:  # 0번째, step번째, 2*step번째... 만 통과
                            n_skipped += 1
                            continue

                    # 레이블 결정
                    if use_cam_label and _cam_label_idx is not None:
                        _lbl = int(float(row[_cam_label_idx]))
                        if _lbl == -1:  # 카메라 레이블 없는 행 제외
                            n_skipped += 1
                            continue
                    else:
                        _lbl = int(float(row[-1]))

                    # 마지막 컬럼이 레이블, 나머지가 특징
                    # stride/interval/카메라 메타 컬럼은 학습 특징에서 제외
                    raw_row = [float(v) for v in row[:-1]]
                    _remove_indices = sorted(
                        {i for i in (_stride_idx, _interval_idx) if i is not None} | set(_cam_meta_indices),
                        reverse=True)
                    for _ri in _remove_indices:
                        if _ri < len(raw_row):
                            raw_row.pop(_ri)
                    X_list.append(raw_row)
                    y_list.append(_lbl)
            n_added = len(X_list) - before
            n_skipped_total += n_skipped
            print(f"[MLP]   {os.path.basename(fpath):<50s} {n_added:4d}샘플" +
                  (f"  (필터 제외: {n_skipped})" if n_skipped else ""))

        if (_filt_s is not None or _filt_i is not None) and n_skipped_total:
            if filter_mode == 'match':
                filt_desc = []
                if _filt_s is not None: filt_desc.append(f"stride={_filt_s}")
                if _filt_i is not None: filt_desc.append(f"interval={_filt_i}")
                mode_str = f"태그 매칭: {', '.join(filt_desc)}"
            else:
                mode_str = f"다운샘플링: 목표 주기 {_target_ms}ms"
            print(f"[MLP] 필터 적용 ({mode_str})  →  총 {len(X_list)}샘플 사용 / {n_skipped_total}샘플 제외")
        elif len(csv_files) > 1:
            print(f"[MLP] CSV {len(csv_files)}개 병합  →  총 {len(X_list)}샘플")
        else:
            print(f"[MLP] CSV 로드  →  총 {len(X_list)}샘플")

        y = np.array(y_list)

        # 최소 조건: 샘플 10개 이상, 클래스가 배경+사람 둘 다 있어야 함
        if min_check and (len(X_list) < 10 or len(np.unique(y)) < 2):
            return None, None

        return np.array(X_list, dtype=np.float32), y

    def _permutation_importance(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
        feature_names: list,
        n_repeat: int = 5,
        device=None,
    ) -> None:
        """
        Permutation Importance: 검증 세트에서 특징 하나씩 랜덤 셔플 후
        정확도 하락폭(Δacc)을 측정해 특징 중요도를 출력합니다.
        """
        _dev = device if device is not None else torch.device('cpu')
        self.model.eval()
        # 베이스라인 정확도 (셔플 없음)
        with torch.no_grad():
            preds_base = self.model(
                torch.tensor(X_val, dtype=torch.float32).to(_dev)
            ).argmax(1).cpu().numpy()
        baseline = float((preds_base == y_val).mean())

        scores = []
        rng = np.random.default_rng(seed=42)
        for i in range(X_val.shape[1]):
            drops = []
            for _ in range(n_repeat):
                X_perm = X_val.copy()
                rng.shuffle(X_perm[:, i])          # i번째 특징만 셔플
                with torch.no_grad():
                    preds = self.model(
                        torch.tensor(X_perm, dtype=torch.float32).to(_dev)
                    ).argmax(1).cpu().numpy()
                drops.append(baseline - float((preds == y_val).mean()))
            scores.append(float(np.mean(drops)))

        _FEAT_KO = {
            'SPECTRAL_ROLLOFF':      '스펙트럼 롤오프',
            'SPECTRAL_BANDWIDTH':    '스펙트럼 대역폭',
            'PEAK_COUNT':            '피크 빈 개수',
            'MID_RATIO':             '중주파 비율 (5~10Hz)',
            'LOW_TO_HIGH_RATIO':     '저/고주파 에너지 비율',
            'SECOND_PEAK_FREQ':      '2번째 피크 주파수',
            'KURTOSIS':              '에너지 분포 첨도',
            'CENTROID':              '스펙트럼 무게중심',
            'PEAK_FREQ':             '1위 피크 주파수',
            'LOW_RATIO':             '저주파 비율 (0~5Hz)',
            'RMS':                   'RMS 에너지',
            'AVG_ENERGY':            '평균 에너지',
            'PEAK_ENERGY':           '피크 에너지',
            'ENERGY_VARIANCE':       '에너지 분산',
            'PEAK_TO_AVG_E':         '피크/평균 에너지 비',
            'HIGH_RATIO':            '고주파 비율 (10Hz↑)',
            'PEAK1_TO_PEAK2_RATIO':  '1·2위 피크 비율',
            'SKEWNESS':              '스펙트럼 비대칭도',
            'DC_RATIO':              'DC 성분 비율',
            'DELTA_PEAK_FREQ':       '피크 주파수 변화량',
            'SPECTRAL_FLATNESS':     '스펙트럼 평탄도',
        }

        ranked = sorted(zip(feature_names, scores), key=lambda x: -x[1])
        print(f"[MLP] ── Permutation Importance (베이스라인 정확도: {baseline:.1%}) ─")
        for rank, (name, drop) in enumerate(ranked, 1):
            bar  = '█' * max(0, round(drop * 200))
            sign = '+' if drop >= 0 else ''
            ko   = _FEAT_KO.get(name.upper(), '')
            ko_str = f'  ({ko})' if ko else ''
            print(f"  {rank:2d}. {name:<28s}  Δacc={sign}{drop:+.4f}  {bar}{ko_str}")
        print(f"[MLP] ─────────────────────────────────────────────")
        return {
            'baseline_acc': round(baseline, 6),
            'features':     [name for name, _ in ranked],
            'importance':   [round(drop, 6) for _, drop in ranked],
        }

    def _evaluate(self, loader: DataLoader, device=None) -> float:
        """DataLoader의 정확도(accuracy)를 계산해 반환"""
        _dev = device if device is not None else torch.device('cpu')
        self.model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for X_batch, y_batch in loader:
                X_batch = X_batch.to(_dev)
                y_batch = y_batch.to(_dev)
                # argmax: 가장 높은 점수의 클래스 인덱스 선택
                preds    = self.model(X_batch).argmax(dim=1)
                correct += (preds == y_batch).sum().item()
                total   += len(y_batch)
        return correct / total if total > 0 else 0.0

    def _evaluate_loss(self, loader: DataLoader, criterion, device=None) -> float:
        """DataLoader의 평균 loss를 계산해 반환"""
        _dev = device if device is not None else torch.device('cpu')
        self.model.eval()
        total_loss, n_batches = 0.0, 0
        with torch.no_grad():
            for X_batch, y_batch in loader:
                X_batch = X_batch.to(_dev)
                y_batch = y_batch.to(_dev)
                logits = self.model(X_batch)
                total_loss += criterion(logits, y_batch).item()
                n_batches  += 1
        return total_loss / n_batches if n_batches > 0 else 0.0

    def _save_model(self, history: dict = None, importance: dict = None, feature_mode: str = 'esp32',
                     hidden_layers: list = None, epochs: int = None,
                     learning_rate: float = None, dropout_rate: float = None,
                     batch_size: int = None, stem: str = None) -> None:
        """모델 가중치와 스케일러를 저장.
        - 고정 경로(mlp_weights.pt): 추론 시 자동 로드용
        - 버전 경로 models/{stem}/{stem}.pt: 결과물 보관용 (stem은 train()에서 생성해 전달)
        - history가 전달되면 동일한 파일명으로 _history.json 저장
        - importance가 전달되면 동일한 파일명으로 _importance.json 저장
        """
        os.makedirs(os.path.dirname(self.MODEL_PATH), exist_ok=True)

        # ① 고정 경로 저장 (추론·로드용)
        torch.save(self.model.state_dict(), self.MODEL_PATH)
        with open(self.SCALER_PATH, 'wb') as f:
            pickle.dump(self.scaler, f)

        # ② stem — train()에서 전달받은 값 그대로 사용 (없으면 폴백 생성)
        if stem is None:
            stem = self._compute_stem(
                hidden_layers if hidden_layers is not None else HIDDEN_LAYERS,
                epochs        if epochs        is not None else EPOCHS,
                learning_rate if learning_rate is not None else LEARNING_RATE,
                dropout_rate  if dropout_rate  is not None else DROPOUT_RATE,
                batch_size    if batch_size    is not None else BATCH_SIZE,
                feature_mode, 'robust' if isinstance(self.scaler, RobustScaler) else 'standard'
            )

        model_dir  = os.path.dirname(self.MODEL_PATH)
        # 버전 파일 전용 서브폴더 생성: models/{stem}/
        ver_dir    = os.path.join(model_dir, stem)
        os.makedirs(ver_dir, exist_ok=True)
        ver_model  = os.path.join(ver_dir, stem + '.pt')
        ver_scaler = os.path.join(ver_dir, stem + '_scaler.pkl')

        torch.save(self.model.state_dict(), ver_model)
        with open(ver_scaler, 'wb') as f:
            pickle.dump(self.scaler, f)

        # ③ 학습 이력 JSON 저장 (모델 선택 시 그래프 재현용)
        if history:
            ver_history = os.path.join(ver_dir, stem + '_history.json')
            with open(ver_history, 'w', encoding='utf-8') as f:
                json.dump(history, f)

        # ④ Permutation Importance JSON 저장
        if importance:
            ver_importance = os.path.join(ver_dir, stem + '_importance.json')
            with open(ver_importance, 'w', encoding='utf-8') as f:
                json.dump(importance, f, ensure_ascii=False)
            print(f"[MLP] 특징 중요도 저장 → {ver_importance}")

        print(f"[MLP] 저장 완료 → {self.MODEL_PATH}  (추론용)")
        print(f"[MLP] 버전 보관 → {ver_dir}/")

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
            def _chg(curr_v, prev_v, higher_is_better=True):
                d = curr_v - prev_v
                if d == 0:   arrow = '→ 유지'
                elif (d > 0) == higher_is_better: arrow = '↑ 개선'
                else:        arrow = '↓ 하락'
                sign = '+' if d >= 0 else ''
                return d, sign, arrow

            prev_best = max(prev['val_acc']) * 100
            curr_best = max(history['val_acc']) * 100
            print()
            print("  ── 이전 학습과 비교 ──────────────────────────────────────────────────")
            print(f"  {'지표':<26}  {'이전':>10}  {'현재':>10}  {'변화'}")
            print(f"  {'─' * 68}")

            d, s, a = _chg(curr_best, prev_best)
            print(f"  {'최고 검증 정확도':<26}  {prev_best:>9.1f}%  {curr_best:>9.1f}%  {s}{d:.1f}%p  {a}")

            if history.get('min_val_loss') is not None and prev.get('min_val_loss') is not None:
                d, s, a = _chg(history['min_val_loss'], prev['min_val_loss'], higher_is_better=False)
                print(f"  {'최소 검증 손실':<26}  {prev['min_val_loss']:>10.4f}  {history['min_val_loss']:>10.4f}  {s}{abs(d):.4f}  {a}")

            if 'human_recall' in history and 'human_recall' in prev:
                p_hr = prev['human_recall'] * 100
                c_hr = history['human_recall'] * 100
                d, s, a = _chg(c_hr, p_hr)
                print(f"  {'사람 Recall (탐지율) TPR':<26}  {p_hr:>9.1f}%  {c_hr:>9.1f}%  {s}{d:.1f}%p  {a}")

            if 'human_fnr' in history and 'human_fnr' in prev:
                p_fnr = prev['human_fnr'] * 100
                c_fnr = history['human_fnr'] * 100
                d, s, a = _chg(c_fnr, p_fnr, higher_is_better=False)
                print(f"  {'사람 오탐률 (눈침) FNR':<26}  {p_fnr:>9.1f}%  {c_fnr:>9.1f}%  {s}{abs(d):.1f}%p  {a}")

            if 'bg_tnr' in history and 'bg_tnr' in prev:
                p_tnr = prev['bg_tnr'] * 100
                c_tnr = history['bg_tnr'] * 100
                d, s, a = _chg(c_tnr, p_tnr)
                print(f"  {'배경 정확 탐지율 TNR':<26}  {p_tnr:>9.1f}%  {c_tnr:>9.1f}%  {s}{d:.1f}%p  {a}")

            if 'bg_fpr' in history and 'bg_fpr' in prev:
                p_fpr = prev['bg_fpr'] * 100
                c_fpr = history['bg_fpr'] * 100
                d, s, a = _chg(c_fpr, p_fpr, higher_is_better=False)
                print(f"  {'배경 오탐률 (오경보) FPR':<26}  {p_fpr:>9.1f}%  {c_fpr:>9.1f}%  {s}{abs(d):.1f}%p  {a}")

            if 'f1_human' in history and 'f1_human' in prev:
                d, s, a = _chg(history['f1_human'], prev['f1_human'])
                print(f"  {'사람 F1 Score':<26}  {prev['f1_human']:>10.4f}  {history['f1_human']:>10.4f}  {s}{abs(d):.4f}  {a}")

            if 'best_epoch' in history and 'best_epoch' in prev:
                d_ep = history['best_epoch'] - prev['best_epoch']
                s_ep = '+' if d_ep >= 0 else ''
                print(f"  {'베스트 에폭':<26}  {prev['best_epoch']:>10d}  {history['best_epoch']:>10d}  {s_ep}{d_ep:d}")

            print()

    @staticmethod
    def _infer_arch_from_state_dict(state_dict: dict) -> tuple:
        """state_dict의 weight shape으로 (input_size, hidden_layers) 역추론.

        OccupancyMLP 구조 규칙:
          net.0 : Linear (첫 번째 은닉층) — [h0, input_size]
          net.1 : BatchNorm1d  (BN weight shape 1D → Linear 아님)
          net.4 : Linear (두 번째 은닉층, 있을 때)
          net.6 : Linear (세 번째 은닉층 or 출력)
          ...마지막 2D weight의 shape[0] == 2 → 출력층
        """
        # 2D weight 키를 인덱스 순서대로 수집
        linear_weights = sorted(
            [(int(k.split('.')[1]), v)
             for k, v in state_dict.items()
             if k.startswith('net.') and k.endswith('.weight') and v.dim() == 2],
            key=lambda x: x[0]
        )
        # 첫 번째 Linear: net.0.weight = [h0, input_size]
        input_size = linear_weights[0][1].shape[1]
        # 마지막이 출력층 (shape[0] == 2), 나머지가 은닉층
        hidden_layers = [w.shape[0] for _, w in linear_weights[:-1]]
        return input_size, hidden_layers

    def _rebuild_model_from_state_dict(self, state_dict: dict) -> None:
        """state_dict 아키텍처에 맞게 self.model 재빌드."""
        input_size, hidden_layers = self._infer_arch_from_state_dict(state_dict)
        if input_size != self.input_size or hidden_layers != list(self.model.net[0].weight.shape[0:1]):
            self.model = OccupancyMLP(input_size, hidden_layers=hidden_layers)
            print(f"[MLP] 모델 재빌드: input={input_size}  hidden={hidden_layers}")

    def load_model_file(self, pt_path: str) -> 'dict | None':
        """지정된 .pt 파일과 대응 스케일러를 로드.
        반환: history dict (있으면) 또는 None
        """
        scaler_path  = pt_path.replace('.pt', '_scaler.pkl')
        history_path = pt_path.replace('.pt', '_history.json')
        try:
            state_dict = torch.load(pt_path, map_location='cpu', weights_only=True)
            self._rebuild_model_from_state_dict(state_dict)
            self.model.load_state_dict(state_dict)
            if os.path.exists(scaler_path):
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
            self.model.eval()
            self.b_is_trained = True
            history = None
            if os.path.exists(history_path):
                with open(history_path, encoding='utf-8') as f:
                    history = json.load(f)
            print(f"[MLP] 모델 로드 → {os.path.basename(pt_path)}")
            return history
        except Exception as e:
            print(f"[MLP] 모델 로드 실패: {e}")
            return None

    def models_dir(self) -> str:
        """models/ 폴더 절대 경로 반환"""
        return os.path.dirname(self.MODEL_PATH)

    def _try_load_model(self) -> None:
        """현재 하이퍼파라미터 세팅과 일치하는 버전 모델을 우선 로드.
        없으면 고정 경로(mlp_weights.pt)로 폴백.

        탐색 패턴: mlp_L{layers}_ep{ep}_lr{lr}_*.pt
        여러 개 일치하면 가장 최근 파일(이름 기준 내림차순) 선택.
        """
        import glob

        model_dir  = os.path.dirname(self.MODEL_PATH)
        layers_str = '-'.join(str(h) for h in HIDDEN_LAYERS)
        import math as _m
        _auto_exp  = int(_m.floor(_m.log10(LEARNING_RATE)))
        _auto_man  = round(LEARNING_RATE / (10 ** _auto_exp), 1)
        _auto_mans = str(int(_auto_man)) if _auto_man == int(_auto_man) else str(_auto_man)
        lr_str     = f'{_auto_mans}e{_auto_exp}'
        # 새 서브폴더 구조: models/{stem}/{stem}.pt
        subdir_pattern = os.path.join(model_dir,
                                      f'mlp_L{layers_str}_ep{EPOCHS}_lr{lr_str}_*',
                                      f'mlp_L{layers_str}_ep{EPOCHS}_lr{lr_str}_*.pt')
        # 이전 플랫 구조 (하위 호환): models/{stem}.pt
        flat_pattern = os.path.join(model_dir, f'mlp_L{layers_str}_ep{EPOCHS}_lr{lr_str}_*.pt')

        candidates = sorted(
            [p for p in glob.glob(subdir_pattern) + glob.glob(flat_pattern)
             if not p.endswith('_scaler.pkl') and '_pc_' not in os.path.basename(p)],
            reverse=True
        )

        if candidates:
            ver_model  = candidates[0]
            ver_scaler = ver_model.replace('.pt', '_scaler.pkl')
            if os.path.exists(ver_scaler):
                try:
                    with open(ver_scaler, 'rb') as f:
                        _scaler_candidate = pickle.load(f)
                    # 스케일러 특징 수 검증 (21개 UART 특징과 일치해야 함)
                    _expected = len(self.feature_indices)
                    if hasattr(_scaler_candidate, 'n_features_in_') and _scaler_candidate.n_features_in_ != _expected:
                        logger.warning(
                            "MLP 모델 자동 로드 실패 — 특징 수 불일치\n"
                            "파일: %s\n"
                            "모델이 기대하는 특징 수: %d개  /  현재 설정: %d개\n"
                            "\n호환되는 모델(21-특징)을 선택하거나 재학습하세요.",
                            os.path.basename(ver_model),
                            _scaler_candidate.n_features_in_, _expected
                        )
                    else:
                        state_dict = torch.load(ver_model, map_location='cpu', weights_only=True)
                        self._rebuild_model_from_state_dict(state_dict)
                        self.model.load_state_dict(state_dict)
                        self.scaler = _scaler_candidate
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
            with open(self.SCALER_PATH, 'rb') as f:
                _scaler_fb = pickle.load(f)
            _expected = len(self.feature_indices)
            if hasattr(_scaler_fb, 'n_features_in_') and _scaler_fb.n_features_in_ != _expected:
                logger.warning(
                    "MLP 고정 모델 로드 실패 — 특징 수 불일치\n"
                    "파일: mlp_weights.pt / mlp_scaler.pkl\n"
                    "모델이 기대하는 특징 수: %d개  /  현재 설정: %d개\n"
                    "\n호환되는 모델(21-특징)을 선택하거나 재학습하세요.",
                    _scaler_fb.n_features_in_, _expected
                )
                return
            state_dict = torch.load(self.MODEL_PATH, map_location='cpu', weights_only=True)
            self._rebuild_model_from_state_dict(state_dict)
            self.model.load_state_dict(state_dict)
            self.scaler = _scaler_fb
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

