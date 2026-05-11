"""
╔══════════════════════════════════════════════════════════════════╗
║  MLP 동작 시각화 스크립트                                        ║
╚══════════════════════════════════════════════════════════════════╝

[ 그래프 목록 ]
  ① 신경망 구조도   — 레이어·뉴런 수·각 연산 흐름
  ② 데이터 분포도   — PCA 2D로 학습 데이터의 배경/사람 분포
  ③ 예측 신뢰도 분포 — 검증 데이터의 예측 확률 히스토그램
  ④ 혼동 행렬 히트맵 — 맞힘/놓침/오경보 시각화

[ 사용법 ]
  python3 AI/visualize.py
"""

import os
import sys
import pickle
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

# ── 한글 폰트 설정 (OS 자동 감지) ───────────────────────────────
import platform as _platform
_sys = _platform.system()
if _sys == 'Windows':
    matplotlib.rcParams['font.family'] = 'Malgun Gothic'
elif _sys == 'Darwin':
    matplotlib.rcParams['font.family'] = 'AppleGothic'
else:  # Linux 등
    matplotlib.rcParams['font.family'] = 'NanumGothic'
matplotlib.rcParams['axes.unicode_minus'] = False

# ── 경로 설정 ─────────────────────────────────────────────────────
# 스크립트 위치: AI/mlp/results/visualize.py
_HERE      = os.path.dirname(os.path.abspath(__file__))  # AI/mlp/results/
SCRIPT_DIR = os.path.dirname(_HERE)                      # AI/mlp/
PARENT_DIR = os.path.dirname(SCRIPT_DIR)                 # AI/
ROOT_DIR   = os.path.dirname(PARENT_DIR)                 # 프로젝트 루트 (data_csv/ 위치)
sys.path.insert(0, SCRIPT_DIR)   # nn_mlp 임포트 (AI/mlp/에 위치)
sys.path.insert(0, PARENT_DIR)   # 기타 상위 모듈

TRAIN_CSV    = os.path.join(SCRIPT_DIR, 'data_train.csv')
VAL_CSV      = os.path.join(SCRIPT_DIR, 'data_val.csv')
SCALER_PATH  = os.path.join(SCRIPT_DIR, 'models', 'mlp_scaler.pkl')
MODEL_PATH   = os.path.join(SCRIPT_DIR, 'models', 'mlp_weights.pt')
HISTORY_PATH = os.path.join(SCRIPT_DIR, 'models', 'train_history.json')

# 배경/사람 색상
COLOR_BG    = '#4C9BE8'   # 파랑
COLOR_HUMAN = '#E86B4C'   # 주황


# ── 모델 선택 인프라 ──────────────────────────────────────────────
from collections import namedtuple
ModelInfo = namedtuple('ModelInfo', ['name', 'pt', 'scaler', 'history', 'importance'])


def _list_model_versions() -> list:
    """models/ 폴더에서 MLP_* 버전 폴더 목록을 타임스탬프(MMDD_HHMMSS) 내림차순으로 반환."""
    model_dir = os.path.join(SCRIPT_DIR, 'models')
    folders = sorted(
        [d for d in os.listdir(model_dir)
         if os.path.isdir(os.path.join(model_dir, d)) and d.startswith('MLP_')],
        key=lambda d: d.rsplit('_', 2)[-2:],   # ['MMDD', 'HHMMSS'] 기준 정렬
        reverse=True,
    )
    return folders


def _pick_model_paths(folder_name: str) -> ModelInfo:
    """버전 폴더 이름으로 ModelInfo(pt, scaler, history, importance) 경로를 반환."""
    folder = os.path.join(SCRIPT_DIR, 'models', folder_name)
    stem   = folder_name
    return ModelInfo(
        name       = folder_name,
        pt         = os.path.join(folder, f'{stem}.pt'),
        scaler     = os.path.join(folder, f'{stem}_scaler.pkl'),
        history    = os.path.join(folder, f'{stem}_history.json'),
        importance = os.path.join(folder, f'{stem}_importance.json'),
    )


def _select_models() -> list:
    """콘솔 메뉴로 시각화할 모델을 선택합니다. ModelInfo 리스트를 반환합니다."""
    versions = _list_model_versions()

    if not versions:
        print("[!] models/ 에 MLP_* 버전 폴더가 없습니다. 기본 경로를 사용합니다.")
        return [ModelInfo('default', MODEL_PATH, SCALER_PATH, HISTORY_PATH,
                          os.path.join(SCRIPT_DIR, 'models', 'mlp_importance.json'))]

    print()
    print('=' * 65)
    print('  시각화할 모델을 선택하세요')
    print('=' * 65)
    print('  1. 가장 최신 모델')
    print('  2. 특정 모델 선택')
    print('  3. 모든 모델 (전체 저장)')
    print('-' * 65)
    choice = input('선택 (1/2/3): ').strip()

    if choice == '1':
        mi = _pick_model_paths(versions[0])
        print(f"  → {versions[0]}")
        return [mi]

    elif choice == '2':
        print()
        for i, v in enumerate(versions, 1):
            print(f'  {i:3d}. {v}')
        print()
        sel = input(f'번호 입력 (1~{len(versions)}): ').strip()
        try:
            idx = int(sel) - 1
            if not (0 <= idx < len(versions)):
                raise ValueError
        except ValueError:
            print('[!] 잘못된 입력. 가장 최신 모델을 사용합니다.')
            idx = 0
        mi = _pick_model_paths(versions[idx])
        print(f"  → {versions[idx]}")
        return [mi]

    elif choice == '3':
        print(f"  → 전체 {len(versions)}개 모델 시각화")
        return [_pick_model_paths(v) for v in versions]

    else:
        print('[!] 잘못된 입력. 가장 최신 모델을 사용합니다.')
        return [_pick_model_paths(versions[0])]


# ════════════════════════════════════════════════════════════════
# 데이터 로더 (prepare_data.py 불필요 — data_csv/ 직접 로드)
# ════════════════════════════════════════════════════════════════
# CSV 실제 컬럼 구조:
#   col 0~20  : ESP32 21개 특징 (spectral_rolloff ~ spectral_flatness)
#   col 21~276: ADC 256개 (사용 안 함)
#   col 277~405: FFT 129개 (fft_0 ~ fft_128)
#   col 406   : label
FFT_FEAT_COLS = [f'fft_{i}' for i in range(129)]   # fft_0 ~ fft_128


def _load_raw_dataset():
    """data_csv/ 폴더의 svm_data*.csv 를 직접 로드해 train/val 로 분리 반환.
    Returns: (df_train, df_val)  — pandas DataFrame (원본 컬럼 유지, label 포함)
             (None, None) 실패 시
    """
    import glob
    import pandas as pd
    from sklearn.model_selection import train_test_split

    pattern = os.path.join(ROOT_DIR, 'data_csv', 'svm_data*.csv')
    paths   = sorted(glob.glob(pattern))
    if not paths:
        print("  [데이터] data_csv/svm_data*.csv 없음 — PCA·신뢰도·혼동행렬 스킵")
        return None, None

    frames = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            if 'label' not in df.columns:
                continue
            df['label'] = df['label'].astype(int)
            frames.append(df)
        except Exception:
            continue

    if not frames:
        return None, None

    merged = (pd.concat(frames, ignore_index=True)
                .drop_duplicates()
                .reset_index(drop=True))
    if len(merged) < 10 or len(merged['label'].unique()) < 2:
        return None, None

    df_train, df_val = train_test_split(
        merged, test_size=0.2, random_state=42, stratify=merged['label'])
    print(f"  [데이터] 로드 완료 — 학습 {len(df_train)}개 / 검증 {len(df_val)}개")
    return df_train, df_val


def _load_model(model_path: str, input_size: int):
    """state_dict에서 실제 은닉층 구조를 읽어 OccupancyMLP를 생성한다.
    저장된 모델의 HIDDEN_LAYERS가 무엇이든 정확히 로드된다.
    """
    import torch
    from nn_mlp import OccupancyMLP
    sd = torch.load(model_path, map_location='cpu', weights_only=True)
    linear_shapes = sorted(
        [(int(k.split('.')[1]), v.shape)
         for k, v in sd.items()
         if k.startswith('net.') and k.endswith('.weight') and v.ndim == 2],
        key=lambda x: x[0]
    )
    hidden = [shape[0] for _, shape in linear_shapes[:-1]]
    model = OccupancyMLP(input_size, hidden_layers=hidden)
    model.load_state_dict(sd)
    model.eval()
    return model


def _extract_features(df: 'pd.DataFrame', importance_path: str = None) -> tuple:
    """DataFrame에서 모델에 맞는 특징 행렬과 레이블을 추출.
    importance.json 의 features 목록을 읽어 모드 자동 판별 + 특징 순서 정렬:
      - 'magnitudes_' 포함 → pc_feature_extractor로 25개 특징 계산 후 importance 순서로 재정렬
      - 그 외              → ESP32: importance features 순서(소문자) 그대로 df 컬럼 추출
    Returns: (X: np.ndarray, y: np.ndarray)
    """
    import json
    y = df['label'].values.astype(int)

    # importance.json 로드
    imp_features = None
    is_pc = False
    if importance_path and os.path.exists(importance_path):
        try:
            with open(importance_path, encoding='utf-8') as _f:
                _imp = json.load(_f)
            imp_features = _imp.get('features', [])
            is_pc = any('magnitudes_' in n.lower() for n in imp_features)
        except Exception:
            pass

    if is_pc:
        import pc_feature_extractor as pce
        # 학습과 동일한 방식: ADC 컬럼 → numpy FFT → 25개 특징
        # (ESP32 하드웨어 FFT 컬럼이 아닌 ADC 원시 데이터에서 재계산)
        X_full = df.drop(columns=['label']).values  # label 제외, 컬럼 순서 유지
        X = pce.extract_pc_features_from_adc_batch(X_full).astype(np.float32)
    else:
        # ESP32: importance.json features(대문자) → CSV 컬럼 인덱스 기준 오름차순 정렬
        # → 학습 시 feature_indices(range 기반) 순서와 동일하게 복원
        if imp_features:
            col_upper = {col.upper(): col for col in df.columns}
            matched = [col_upper[n] for n in imp_features if n in col_upper]
            ordered_cols = sorted(matched, key=lambda c: df.columns.get_loc(c))
        else:
            ordered_cols = [c for c in df.columns if c != 'label'][:21]
        X = df[ordered_cols].values.astype(np.float32)

    return X, y
def draw_architecture(ax, model_info=None):
    """
    모델의 scaler / importance.json 을 읽어 MLP 구조를 동적으로 그립니다.
    입력 크기는 scaler.n_features_in_ 에서, 특징 유형은 importance.json 에서 읽습니다.
    """
    import json
    import torch
    import nn_mlp as mlp_mod

    # ── 입력 크기: scaler에서 읽음 ────────────────────────────────
    INPUT_SIZE = 21  # 기본값 (ESP32 21개)
    if model_info and os.path.exists(model_info.scaler):
        try:
            with open(model_info.scaler, 'rb') as _f:
                _scaler = pickle.load(_f)
            INPUT_SIZE = getattr(_scaler, 'n_features_in_', INPUT_SIZE)
        except Exception:
            pass

    # ── 특징 유형 레이블: importance.json features 로 판별 ─────────
    feat_label = 'ESP32 특징'
    if model_info and os.path.exists(model_info.importance):
        try:
            with open(model_info.importance, encoding='utf-8') as _f:
                _imp = json.load(_f)
            if any('magnitudes_' in n.lower() for n in _imp.get('features', [])):
                feat_label = 'PC 계산 특징'
        except Exception:
            pass

    # ── 실제 레이어 구조: state_dict에서 Linear weight shape 추출 ──────
    HIDDEN      = mlp_mod.HIDDEN_LAYERS   # 기본값 (모델 로드 실패 시 폴백)
    DROPOUT     = mlp_mod.DROPOUT_RATE
    OUTPUT_SIZE = 2

    # Dropout: nn.Dropout은 state_dict에 파라미터가 없으므로 폴더명에서 파싱
    # 명명 규칙: ..._D{n}_... → 0.n  (예: D2→0.2, D3→0.3)
    if model_info:
        import re as _re
        _m = _re.search(r'_D(\d+)_', model_info.name)
        if _m:
            DROPOUT = int(_m.group(1)) / 10.0

    if model_info and os.path.exists(model_info.pt):
        try:
            sd = torch.load(model_info.pt, map_location='cpu', weights_only=True)
            # 'net.N.weight' 중 2D인 것(Linear)만 추출, 인덱스 오름차순 정렬
            linear_weights = sorted(
                [(int(k.split('.')[1]), v.shape)
                 for k, v in sd.items()
                 if k.startswith('net.') and k.endswith('.weight') and v.ndim == 2],
                key=lambda x: x[0]
            )
            # 마지막은 출력층 → 제외, 중간이 은닉층 출력 크기
            HIDDEN = [shape[0] for _, shape in linear_weights[:-1]]
        except Exception:
            pass

    hidden_colors = ['#F0C895', '#95F0B4', '#C8A8F0', '#F0E695', '#A8D8F0']

    # 입력층
    layer_defs = [
        (f'입력층\n({INPUT_SIZE}개 {feat_label})', INPUT_SIZE, '#95C8F0', None),
    ]

    # 은닉층 (HIDDEN_LAYERS 길이만큼 자동 생성)
    prev = INPUT_SIZE
    for i, h in enumerate(HIDDEN):
        if i == 0:
            ops = f'Linear({prev}→{h})\nBatchNorm\nReLU\nDropout({DROPOUT:.0%})'
        else:
            ops = f'Linear({prev}→{h})\nReLU'
        color = hidden_colors[i % len(hidden_colors)]
        layer_defs.append((f'은닉층 {i+1}\n({h} 뉴런)', h, color, ops))
        prev = h

    # 출력층
    layer_defs.append(
        (f'출력층\n({OUTPUT_SIZE}개 클래스)', OUTPUT_SIZE, '#F09595',
         f'Linear({prev}→{OUTPUT_SIZE})\nSoftmax')
    )

    n_layers = len(layer_defs)
    margin = 0.8
    xs = [margin + i * (10 - 2 * margin) / (n_layers - 1) for i in range(n_layers)]

    hidden_summary = ', '.join(str(h) for h in HIDDEN)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title(
        f'① MLP 신경망 구조  '
        f'(은닉층 {len(HIDDEN)}개 | [{hidden_summary}] | Dropout={DROPOUT:.0%})',
        fontsize=11, fontweight='bold', pad=10
    )

    MAX_NODES = 8
    node_positions = {}

    for li, (label, n_nodes, color, ops) in enumerate(layer_defs):
        cx = xs[li]
        display_n = min(n_nodes, MAX_NODES)
        gap = 7.5 / (display_n + 1)
        positions = [(cx, 1.0 + gap * (ni + 1)) for ni in range(display_n)]
        node_positions[li] = positions

        # 레이어 배경 박스
        rect = mpatches.FancyBboxPatch(
            (cx - 0.42, 0.8), 0.84, 8.0,
            boxstyle='round,pad=0.05',
            facecolor=color, edgecolor='gray', alpha=0.3, linewidth=1.2,
        )
        ax.add_patch(rect)

        # 노드
        for (nx, ny) in positions:
            circle = plt.Circle((nx, ny), 0.18, color=color,
                                 ec='gray', linewidth=1.0, zorder=3)
            ax.add_patch(circle)

        # 생략 표시 (노드가 잘렸을 때)
        if n_nodes > MAX_NODES:
            mid = len(positions) // 2
            for dot_dy in [-0.35, 0, 0.35]:
                ax.text(cx, positions[mid][1] + dot_dy * 2.2,
                        '·', ha='center', va='center', fontsize=16, color='gray')

        # 레이어 레이블 (위)
        ax.text(cx, 9.5, label, ha='center', va='center',
                fontsize=7.5, fontweight='bold', color='#333333')

        # 연산 설명 (아래)
        if ops:
            ax.text(cx, 0.38, ops, ha='center', va='center',
                    fontsize=6, color='#555555',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                              edgecolor='lightgray', alpha=0.8))

    # 레이어 간 연결선
    for li in range(n_layers - 1):
        src_pos = node_positions[li]
        dst_pos = node_positions[li + 1]
        for sx, sy in src_pos:
            for dx, dy in [dst_pos[0], dst_pos[-1]]:
                ax.plot([sx + 0.18, dx - 0.18], [sy, dy],
                        color='gray', alpha=0.12, linewidth=0.5, zorder=1)

    # 화살표 (레이어 사이)
    for li in range(n_layers - 1):
        x1 = xs[li] + 0.45
        x2 = xs[li + 1] - 0.45
        ax.annotate('', xy=(x2, 5.0), xytext=(x1, 5.0),
                    arrowprops=dict(arrowstyle='->', color='#555', lw=1.5))


# ════════════════════════════════════════════════════════════════
# Ⅱ 학습 공선 (손실 & 정확도 vs 에폭)
# ════════════════════════════════════════════════════════════════
def draw_learning_curve(ax_acc, ax_loss, history_path=None, lr_data=None):
    """
    학습 중 기록된 에폭별 정확도(학습/검증)와 손실를 그래프로 표시합니다.
    lr_data: LR 목록이 주어지면 감소 시점에 회색 수직선 표시.
    학습 이이력 파일(train_history.json)이 없으면 안내를 출력합니다.
    """
    import json

    _history = history_path or HISTORY_PATH
    no_data_msg = '학습 이력 없음\n(nn_mlp.py 학습을 먼저 실행하세요)'

    if not os.path.exists(_history):
        for ax in (ax_acc, ax_loss):
            ax.text(0.5, 0.5, no_data_msg,
                    ha='center', va='center', transform=ax.transAxes,
                    fontsize=10, color='gray')
            ax.axis('off')
        ax_acc.set_title('Ⅱ 에폭별 정확도', fontsize=13, fontweight='bold')
        ax_loss.set_title('Ⅲ 에폭별 손실', fontsize=13, fontweight='bold')
        return

    with open(_history, encoding='utf-8') as f:
        h = json.load(f)

    epochs     = h['epochs']
    loss       = h.get('train_loss', h.get('loss', []))
    train_acc  = [v * 100 for v in h['train_acc']]
    val_acc    = [v * 100 for v in h['val_acc']]
    # lr_data 우선순위: 인자 > history JSON
    _lr = lr_data if lr_data else h.get('lr', [])

    # LR 감소 시점 추출
    def _get_drop_epochs(lrs, eps):
        drops = []
        prev = lrs[0]
        for ep, lr in zip(eps, lrs):
            if lr < prev - 1e-12:
                drops.append(ep)
            prev = lr
        return drops
    drop_eps = _get_drop_epochs(_lr, epochs) if len(_lr) == len(epochs) else []

    # ── 정확도 그래프 ─────────────────────────
    train_arr = np.array(train_acc)
    val_arr   = np.array(val_acc)

    ax_acc.plot(epochs, train_acc, color='#4C9BE8', linewidth=1.8, label='학습 정확도')
    ax_acc.plot(epochs, val_acc,   color='#E86B4C', linewidth=1.8, label='검증 정확도', linestyle='--')

    # 과적합 구역: 학습 > 검증 인 구간
    ax_acc.fill_between(epochs, train_arr, val_arr,
                        where=(train_arr > val_arr),
                        alpha=0.12, color='red', label='과적합 구역')

    # 검증 최고 에폭
    best_val_idx   = int(np.argmax(val_arr))
    best_val_epoch = epochs[best_val_idx]
    best_val_acc   = float(val_arr[best_val_idx])
    ax_acc.axvline(best_val_epoch, color='#E86B4C', linestyle=':', linewidth=1.2, alpha=0.8)
    ax_acc.annotate(
        f'검증 최고\n{best_val_acc:.1f}% (ep {best_val_epoch})',
        xy=(best_val_epoch, best_val_acc),
        xytext=(0.97, 0.05), textcoords='axes fraction',
        fontsize=7.5, color='#E86B4C', ha='right', va='bottom',
        arrowprops=dict(arrowstyle='->', color='#E86B4C', lw=1.0),
        bbox=dict(boxstyle='round,pad=0.2', facecolor='#fff5f0', edgecolor='#E86B4C', alpha=0.8),
    )

    # 학습 최고 에폭
    best_tr_idx   = int(np.argmax(train_arr))
    best_tr_epoch = epochs[best_tr_idx]
    best_tr_acc   = float(train_arr[best_tr_idx])
    ax_acc.axvline(best_tr_epoch, color='#4C9BE8', linestyle=':', linewidth=1.2, alpha=0.8)
    ax_acc.annotate(
        f'학습 최고\n{best_tr_acc:.1f}% (ep {best_tr_epoch})',
        xy=(best_tr_epoch, best_tr_acc),
        xytext=(0.97, 0.25), textcoords='axes fraction',
        fontsize=7.5, color='#4C9BE8', ha='right', va='bottom',
        arrowprops=dict(arrowstyle='->', color='#4C9BE8', lw=1.0),
        bbox=dict(boxstyle='round,pad=0.2', facecolor='#f0f5ff', edgecolor='#4C9BE8', alpha=0.8),
    )

    ax_acc.set_title('Ⅱ 에폭별 정확도', fontsize=13, fontweight='bold')
    ax_acc.set_xlabel('에폭', fontsize=9)
    ax_acc.set_ylabel('정확도 (%)', fontsize=9)
    ax_acc.set_ylim(50, 100)
    ax_acc.legend(fontsize=9, loc='upper left')
    ax_acc.grid(True, alpha=0.3)

    # ── 방법 A: LR 감소 시점 수직선 (정확도 그래프) ──────────────
    for dep in drop_eps:
        ax_acc.axvline(dep, color='#27AE60', linestyle='--',
                       linewidth=0.9, alpha=0.55, zorder=1)
    if drop_eps:
        ax_acc.axvline(drop_eps[0], color='#27AE60', linestyle='--',
                       linewidth=0.9, alpha=0.55, label='LR 감소', zorder=1)
        ax_acc.legend(fontsize=9, loc='upper left')

    # ── 손실 그래프 ─────────────────────────
    val_loss_data = h.get('val_loss', [])

    ax_loss.plot(epochs, loss, color='#8E44AD', linewidth=1.8, label='학습 손실')
    if val_loss_data and len(val_loss_data) == len(epochs):
        val_loss_arr = np.array(val_loss_data)
        ax_loss.plot(epochs, val_loss_data, color='#E86B4C', linewidth=1.8,
                     linestyle='--', label='검증 손실')
        # 과적합 구역: val_loss > train_loss
        ax_loss.fill_between(epochs, np.array(loss), val_loss_arr,
                             where=(val_loss_arr > np.array(loss)),
                             alpha=0.12, color='red', label='과적합 구역')
        # 검증 손실 최솟값 마커
        min_vl_idx   = int(np.argmin(val_loss_arr))
        min_vl_epoch = epochs[min_vl_idx]
        min_vl       = float(val_loss_arr[min_vl_idx])
        ax_loss.axvline(min_vl_epoch, color='#E86B4C', linestyle=':', linewidth=1.2, alpha=0.8)
        ax_loss.annotate(
            f'검증 손실 최소\n{min_vl:.4f} (ep {min_vl_epoch})',
            xy=(min_vl_epoch, min_vl),
            xytext=(0.97, 0.75), textcoords='axes fraction',
            fontsize=7.5, color='#E86B4C', ha='right', va='top',
            arrowprops=dict(arrowstyle='->', color='#E86B4C', lw=1.0),
            bbox=dict(boxstyle='round,pad=0.2', facecolor='#fff5f0', edgecolor='#E86B4C', alpha=0.8),
        )
        ax_loss.legend(fontsize=9, loc='upper right')

    # ── 방법 A: LR 감소 시점 수직선 (손실 그래프) ────────────────
    for dep in drop_eps:
        ax_loss.axvline(dep, color='#27AE60', linestyle='--',
                        linewidth=0.9, alpha=0.55, zorder=1)

    ax_loss.set_title('Ⅲ 에폭별 손실', fontsize=13, fontweight='bold')
    ax_loss.set_xlabel('에폭', fontsize=9)
    ax_loss.set_ylabel('손실', fontsize=9)
    # ax_loss.set_ylim(0.2, 0.65)
    ax_loss.set_ylim(0.05, 0.65)
    ax_loss.grid(True, alpha=0.3)


# ════════════════════════════════════════════════════════════════
# Ⅳ 학습률 (LR) 변화
# ════════════════════════════════════════════════════════════════
def draw_lr(ax, history_path=None):
    """에폭별 학습률(LR) 변화를 log 스케일로 표시합니다."""
    import json

    _history = history_path or HISTORY_PATH

    if not os.path.exists(_history):
        ax.text(0.5, 0.5, '학습 이력 없음', ha='center', va='center',
                transform=ax.transAxes, fontsize=10, color='gray')
        ax.axis('off')
        ax.set_title('Ⅳ 학습률 (LR)', fontsize=13, fontweight='bold')
        return

    with open(_history, encoding='utf-8') as f:
        h = json.load(f)

    epochs  = h['epochs']
    lr_data = h.get('lr', [])

    ax.set_title('Ⅳ 학습률 (LR) 변화', fontsize=13, fontweight='bold')
    ax.set_xlabel('에폭', fontsize=9)
    ax.set_ylabel('학습률 (LR)', fontsize=9)

    if not lr_data or len(lr_data) != len(epochs):
        ax.text(0.5, 0.5, 'LR 데이터 없음', ha='center', va='center',
                transform=ax.transAxes, fontsize=10, color='gray')
        ax.grid(True, alpha=0.3)
        return

    ax.plot(epochs, lr_data, color='#27AE60', linewidth=1.8, label='학습률 (LR)')
    ax.set_yscale('log')
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.LogFormatterSciNotation(labelOnlyBase=False))

    # Y축 범위 고정: 하단 1e-6(min_lr 수렴점), 상단 max(lr)*5 (최소 1e-2)
    y_top = max(max(lr_data) * 5, 1e-2)
    ax.set_ylim(1e-6, y_top)

    # LR 변화 지점 마커 (이전 에폭 대비 감소한 첫 에폭)
    prev = lr_data[0]
    drop_epochs, drop_lrs = [], []
    for i, (ep, lr) in enumerate(zip(epochs, lr_data)):
        if lr < prev - 1e-12:
            drop_epochs.append(ep)
            drop_lrs.append(lr)
        prev = lr
    if drop_epochs:
        ax.scatter(drop_epochs, drop_lrs, color='#E86B4C', zorder=5,
                   s=30, label=f'LR 감소 ({len(drop_epochs)}회)')

        n_drops  = len(drop_epochs)
        ep_range = max(epochs[-1] - epochs[0], 1)
        fs       = 5.5 if n_drops <= 10 else 5.0

        # ── 겹침 방지 y-offset 계산 ──────────────────────────
        BASE = 18   # 기본 offset (points)
        STEP = 14   # 충돌 시 추가 offset

        offsets = [BASE * (1 if i % 2 == 0 else -1) for i in range(n_drops)]

        # 좌→우 두 패스: 인접 점과 같은 방향이면 반전, 아직 가까우면 offset 키움
        for _ in range(2):
            for i in range(1, n_drops):
                x_gap = (drop_epochs[i] - drop_epochs[i - 1]) / ep_range
                if x_gap < 0.07:
                    if (offsets[i] > 0) == (offsets[i - 1] > 0):
                        offsets[i] = -offsets[i]
                    if x_gap < 0.035:
                        same = [abs(offsets[j]) for j in range(i)
                                if (offsets[j] > 0) == (offsets[i] > 0)
                                and (drop_epochs[i] - drop_epochs[j]) / ep_range < 0.07]
                        if same:
                            offsets[i] = (max(same) + STEP) * (1 if offsets[i] > 0 else -1)

        for ep, lr, yo in zip(drop_epochs, drop_lrs, offsets):
            va_str = 'bottom' if yo > 0 else 'top'
            ax.annotate(f'ep{ep}\n{lr:.1e}',
                        xy=(ep, lr),
                        xytext=(0, yo),
                        textcoords='offset points',
                        fontsize=fs, color='#C0392B',
                        ha='center', va=va_str,
                        arrowprops=dict(arrowstyle='-', color='#E86B4C',
                                        linewidth=0.5, shrinkA=0, shrinkB=2),
                        bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                  edgecolor='#E86B4C', alpha=0.75, linewidth=0.5),
                        zorder=6)

    # 초기/최종 LR 표시
    ax.annotate(f'초기: {lr_data[0]:.2e}',
                xy=(epochs[0], lr_data[0]),
                xytext=(0.03, 0.92), textcoords='axes fraction',
                fontsize=7.5, color='#27AE60',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#f0fff4',
                          edgecolor='#27AE60', alpha=0.8))
    ax.annotate(f'최종: {lr_data[-1]:.2e}',
                xy=(epochs[-1], lr_data[-1]),
                xytext=(0.97, 0.05), textcoords='axes fraction',
                fontsize=7.5, color='#27AE60', ha='right',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#f0fff4',
                          edgecolor='#27AE60', alpha=0.8))

    ax.legend(fontsize=9, loc='upper right')
    ax.grid(True, alpha=0.3)


# ════════════════════════════════════════════════════════════════
# ④ LR 단계별 효과 분석 (Δval_acc / Δloss)
# ════════════════════════════════════════════════════════════════
def draw_lr_effect(ax, history_path=None):
    """
    LR이 감소하는 시점을 기준으로 단계를 나누고,
    각 단계 직전 N에폭 vs 직후 N에폭의 val_acc 및 val_loss 변화량을
    위(Δval_acc) / 아래(Δval_loss) 두 패널로 나눠 표시.
    """
    import json
    from matplotlib.gridspec import GridSpecFromSubplotSpec

    N = 30   # 감소 전후 평균 대상 에폭 수

    _history = history_path or HISTORY_PATH

    def _fallback(msg):
        ax.set_title('⑤ LR 감소 효과 (Δval_acc / Δloss)', fontsize=11, fontweight='bold')
        ax.text(0.5, 0.5, msg, ha='center', va='center',
                transform=ax.transAxes, fontsize=10, color='gray')
        ax.axis('off')

    if not os.path.exists(_history):
        _fallback('학습 이력 없음')
        return

    with open(_history, encoding='utf-8') as f:
        h = json.load(f)

    epochs   = h['epochs']
    lr_data  = h.get('lr', [])
    val_acc  = [v * 100 for v in h['val_acc']]
    val_loss = h.get('val_loss', [])

    if not lr_data or len(lr_data) != len(epochs):
        _fallback('LR 데이터 없음')
        return

    # LR 감소 시점 및 단계 구간 정의
    drop_indices = []
    prev = lr_data[0]
    for i, lr in enumerate(lr_data):
        if lr < prev - 1e-12:
            drop_indices.append(i)
        prev = lr

    if not drop_indices:
        _fallback('LR 감소 없음\n(스케줄러 비활성 모델)')
        return

    boundaries = [0] + drop_indices + [len(epochs)]
    stages = list(zip(boundaries[:-1], boundaries[1:]))

    labels, d_acc_list, d_loss_list = [], [], []
    for k, (s, e) in enumerate(stages):
        if k == 0:   # L1(초기 단계) 제외 — 편차가 너무 커서 나머지가 작아보임
            continue
        seg_acc  = val_acc[s:e]
        seg_loss = val_loss[s:e] if val_loss else []
        if len(seg_acc) < 2:
            continue

        n_use = min(N, len(seg_acc) // 2)
        acc_before = np.mean(seg_acc[:n_use])
        acc_after  = np.mean(seg_acc[-n_use:])
        d_acc = acc_after - acc_before

        if seg_loss and len(seg_loss) == (e - s):
            loss_before = np.mean(seg_loss[:n_use])
            loss_after  = np.mean(seg_loss[-n_use:])
            d_loss = loss_after - loss_before
        else:
            d_loss = 0.0

        lr_val = lr_data[s]
        labels.append((k + 1, lr_val, epochs[s], epochs[e - 1]))
        d_acc_list.append(d_acc)
        d_loss_list.append(d_loss)

    if not labels:
        _fallback('데이터 부족')
        return

    n_stages = len(labels)
    x        = np.arange(n_stages)

    # ── gs[1,3] 위치를 위/아래 2개 서브패널로 분할 ──
    fig  = ax.get_figure()
    ss   = ax.get_subplotspec()
    ax.remove()
    inner   = GridSpecFromSubplotSpec(2, 1, subplot_spec=ss, hspace=0.55)
    ax_acc  = fig.add_subplot(inner[0])
    ax_loss = fig.add_subplot(inner[1])

    # x축 레이블: 8개 이하 → 2줄(L번호+LR값), 9~14 → 45° 회전, 15+ → 홀수만
    if n_stages <= 8:
        tick_labels = [f'L{k}\n{lr:.1e}' for k, lr, _, _ in labels]
        rot, ha_str, fs = 0, 'center', 7
    elif n_stages <= 14:
        tick_labels = [f'L{k}\n{lr:.1e}' for k, lr, _, _ in labels]
        rot, ha_str, fs = 45, 'right', 6
    else:
        tick_labels = [f'L{k}' if k % 2 == 1 else '' for k, _, _, _ in labels]
        rot, ha_str, fs = 0, 'center', 6

    # ── 위 패널: Δval_acc ──
    ax_acc.set_title(f'⑤ LR 감소 효과  (N={N}에폭 / 단계수={n_stages}, L1 제외)',
                     fontsize=10, fontweight='bold')
    bars_acc = ax_acc.bar(x, d_acc_list, 0.6,
                          color=['#4C9BE8' if v >= 0 else '#E86B4C' for v in d_acc_list],
                          alpha=0.85)
    ax_acc.axhline(0, color='black', linewidth=0.8, alpha=0.4)
    ax_acc.set_ylabel('Δval_acc (%)', fontsize=8, color='#4C9BE8')
    ax_acc.tick_params(axis='y', colors='#4C9BE8', labelsize=7)
    ax_acc.set_xticks(x)
    ax_acc.set_xticklabels(['' for _ in x])   # 아래 패널에만 레이블
    ax_acc.grid(True, alpha=0.2, axis='y')
    if n_stages <= 10:
        for bar, v in zip(bars_acc, d_acc_list):
            ax_acc.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + (0.05 if v >= 0 else -0.05),
                        f'{v:+.1f}', ha='center',
                        va='bottom' if v >= 0 else 'top',
                        fontsize=6, color='#4C9BE8' if v >= 0 else '#E86B4C')

    # ── 아래 패널: Δval_loss ──
    bars_loss = ax_loss.bar(x, d_loss_list, 0.6,
                            color=['#8E44AD' if v <= 0 else '#E86B4C' for v in d_loss_list],
                            alpha=0.85)
    ax_loss.axhline(0, color='black', linewidth=0.8, alpha=0.4)
    ax_loss.set_ylabel('Δval_loss', fontsize=8, color='#8E44AD')
    ax_loss.tick_params(axis='y', colors='#8E44AD', labelsize=7)
    ax_loss.set_xticks(x)
    ax_loss.set_xticklabels(tick_labels, fontsize=fs, rotation=rot, ha=ha_str)
    ax_loss.set_xlabel('LR 단계', fontsize=8)
    ax_loss.grid(True, alpha=0.2, axis='y')
    if n_stages <= 10:
        for bar, v in zip(bars_loss, d_loss_list):
            ax_loss.text(bar.get_x() + bar.get_width() / 2,
                         bar.get_height() + (0.001 if v >= 0 else -0.001),
                         f'{v:+.3f}', ha='center',
                         va='bottom' if v >= 0 else 'top',
                         fontsize=6, color='#8E44AD' if v <= 0 else '#E86B4C')
def draw_pca(ax, df_train=None, model_info=None):
    """
    학습 데이터를 PCA로 2차원에 투영해 배경/사람 분포를 점으로 표시합니다.
    df_train: _load_raw_dataset() 반환 DataFrame
    """
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    ax.set_title('③ 데이터 분포 (PCA 2D 투영)', fontsize=13, fontweight='bold')

    if df_train is None:
        ax.text(0.5, 0.5, '데이터 없음\n(data_csv/ 폴더에 svm_data*.csv 필요)',
                ha='center', va='center', transform=ax.transAxes, fontsize=11, color='gray')
        return

    imp_path = model_info.importance if model_info else None
    try:
        X, y = _extract_features(df_train, imp_path)
    except Exception as e:
        ax.text(0.5, 0.5, f'특징 추출 실패\n{e}',
                ha='center', va='center', transform=ax.transAxes, fontsize=10, color='gray')
        return

    # 표시할 샘플 수 제한 (너무 많으면 느림)
    MAX_SAMPLES = 3000
    if len(y) > MAX_SAMPLES:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(y), MAX_SAMPLES, replace=False)
        X, y = X[idx], y[idx]

    # 정규화 후 PCA — 모델 scaler 사용 (특징 수 일치 시), 아니면 새로 fit
    cur_scaler_path = model_info.scaler if model_info else SCALER_PATH
    if os.path.exists(cur_scaler_path):
        with open(cur_scaler_path, 'rb') as f:
            scaler = pickle.load(f)
        if hasattr(scaler, 'n_features_in_') and scaler.n_features_in_ == X.shape[1]:
            X_scaled = scaler.transform(X)
        else:
            X_scaled = StandardScaler().fit_transform(X)
    else:
        X_scaled = StandardScaler().fit_transform(X)

    pca = PCA(n_components=2)
    X_2d = pca.fit_transform(X_scaled)
    var_ratio = pca.explained_variance_ratio_

    mask_bg    = y == 0
    mask_human = y == 1

    ax.scatter(X_2d[mask_bg, 0],    X_2d[mask_bg, 1],
               c=COLOR_BG,    alpha=0.35, s=8, label=f'배경 ({mask_bg.sum()}개)')
    ax.scatter(X_2d[mask_human, 0], X_2d[mask_human, 1],
               c=COLOR_HUMAN, alpha=0.35, s=8, label=f'사람 ({mask_human.sum()}개)')

    ax.set_xlabel(f'PC1 (분산 {var_ratio[0]:.1%})', fontsize=9)
    ax.set_ylabel(f'PC2 (분산 {var_ratio[1]:.1%})', fontsize=9)
    ax.legend(fontsize=9, markerscale=2)
    ax.grid(True, alpha=0.3)

    total_var = var_ratio[0] + var_ratio[1]
    ax.text(0.02, 0.98, f'2PC 설명력: {total_var:.1%}',
            transform=ax.transAxes, fontsize=8, va='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))


# ════════════════════════════════════════════════════════════════
# Ⅳ 예측 신뢰도 분포 히스토그램
# ════════════════════════════════════════════════════════════════
def draw_confidence(ax, model_info=None, df_val=None):
    """
    검증 데이터에 대해 모델이 '사람'이라고 예측한 확률 분포를 히스토그램으로 표시합니다.
    df_val: _load_raw_dataset() 반환 DataFrame
    """
    import torch

    ax.set_title('④ 예측 신뢰도 분포 (사람 확률)', fontsize=13, fontweight='bold')

    cur_model_path  = model_info.pt         if model_info else MODEL_PATH
    cur_scaler_path = model_info.scaler     if model_info else SCALER_PATH
    imp_path        = model_info.importance if model_info else None

    if not os.path.exists(cur_model_path):
        ax.text(0.5, 0.5, '모델 없음\n(먼저 학습을 실행하세요)',
                ha='center', va='center', transform=ax.transAxes, fontsize=11, color='gray')
        return

    if df_val is None:
        ax.text(0.5, 0.5, '검증 데이터 없음\n(data_csv/ 폴더에 svm_data*.csv 필요)',
                ha='center', va='center', transform=ax.transAxes, fontsize=11, color='gray')
        return

    try:
        X_raw, y = _extract_features(df_val, imp_path)
    except Exception as e:
        ax.text(0.5, 0.5, f'특징 추출 실패\n{e}',
                ha='center', va='center', transform=ax.transAxes, fontsize=10, color='gray')
        return

    with open(cur_scaler_path, 'rb') as f:
        scaler = pickle.load(f)
    X_scaled = torch.tensor(scaler.transform(X_raw), dtype=torch.float32)

    model = _load_model(cur_model_path, X_raw.shape[1])
    with torch.no_grad():
        probs = torch.softmax(model(X_scaled), dim=1).numpy()

    human_prob = probs[:, 1]   # '사람'일 확률

    bins = np.linspace(0, 1, 41)
    ax.hist(human_prob[y == 0], bins=bins, color=COLOR_BG,    alpha=0.7,
            label='실제: 배경', edgecolor='white', linewidth=0.3)
    ax.hist(human_prob[y == 1], bins=bins, color=COLOR_HUMAN, alpha=0.7,
            label='실제: 사람', edgecolor='white', linewidth=0.3)

    ax.axvline(x=0.5, color='black', linestyle='--', linewidth=1.2, label='결정 경계 (0.5)')
    ax.set_xlabel('사람일 확률', fontsize=10)
    ax.set_ylabel('샘플 수', fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')

    ax.text(0.25, 0.92, '← 배경으로 예측',
            ha='center', va='top', transform=ax.transAxes, fontsize=8, color='#555')
    ax.text(0.75, 0.92, '사람으로 예측 →',
            ha='center', va='top', transform=ax.transAxes, fontsize=8, color='#555')



# ════════════════════════════════════════════════════════════════
# Ⅴ 혼동 행렬 히트맵
# ════════════════════════════════════════════════════════════════
def draw_confusion_matrix(ax, model_info=None, df_val=None):
    """
    혼동 행렬을 색상 히트맵으로 표시합니다.
    df_val: _load_raw_dataset() 반환 DataFrame
    """
    import torch
    from sklearn.metrics import confusion_matrix

    ax.set_title('⑤ 혼동 행렬', fontsize=13, fontweight='bold')

    cur_model_path  = model_info.pt         if model_info else MODEL_PATH
    cur_scaler_path = model_info.scaler     if model_info else SCALER_PATH
    imp_path        = model_info.importance if model_info else None

    if not os.path.exists(cur_model_path):
        ax.text(0.5, 0.5, '모델 없음',
                ha='center', va='center', transform=ax.transAxes, fontsize=11, color='gray')
        return

    if df_val is None:
        ax.text(0.5, 0.5, '검증 데이터 없음\n(data_csv/ 폴더에 svm_data*.csv 필요)',
                ha='center', va='center', transform=ax.transAxes, fontsize=11, color='gray')
        return

    try:
        X_raw, y = _extract_features(df_val, imp_path)
    except Exception as e:
        ax.text(0.5, 0.5, f'특징 추출 실패\n{e}',
                ha='center', va='center', transform=ax.transAxes, fontsize=10, color='gray')
        return

    with open(cur_scaler_path, 'rb') as f:
        scaler = pickle.load(f)
    X_scaled = torch.tensor(scaler.transform(X_raw), dtype=torch.float32)

    model = _load_model(cur_model_path, X_raw.shape[1])
    with torch.no_grad():
        preds = model(X_scaled).argmax(dim=1).numpy()

    cm = confusion_matrix(y, preds)

    # 색상: 대각선 초록, 비대각선 빨강
    colors = np.array([
        ['#5DBB63', '#E86B4C'],   # TN(맞음), FP(오경보)
        ['#E86B4C', '#5DBB63'],   # FN(놓침), TP(맞음)
    ])

    cell_labels = [
        ['TN\n(배경→배경 OK)', 'FP\n(배경→사람 NG\n오경보)'],
        ['FN\n(사람→배경 NG\n놓침)', 'TP\n(사람→사람 OK)'],
    ]

    cls_names = ['배경(BG)', '사람(Human)']
    n = 2
    for i in range(n):
        for j in range(n):
            rect = mpatches.FancyBboxPatch(
                (j + 0.05, n - i - 0.95), 0.9, 0.9,
                boxstyle='round,pad=0.05',
                facecolor=colors[i][j], edgecolor='white',
                linewidth=2, alpha=0.75,
            )
            ax.add_patch(rect)
            # 숫자
            ax.text(j + 0.5, n - i - 0.5 + 0.15, f'{cm[i][j]:,}',
                    ha='center', va='center', fontsize=15, fontweight='bold', color='white')
            # 라벨
            ax.text(j + 0.5, n - i - 0.5 - 0.22, cell_labels[i][j],
                    ha='center', va='center', fontsize=7, color='white', alpha=0.9)

    ax.set_xlim(0, n)
    ax.set_ylim(0, n)
    ax.set_xticks([0.5, 1.5])
    ax.set_yticks([0.5, 1.5])
    ax.set_xticklabels([f'예측: {c}' for c in cls_names], fontsize=9)
    ax.set_yticklabels([f'실제: {c}' for c in reversed(cls_names)], fontsize=9)
    ax.set_xlabel('모델 예측', fontsize=10, labelpad=8)
    ax.set_ylabel('실제 정답', fontsize=10, labelpad=8)
    ax.tick_params(length=0)

    total = cm.sum()
    acc   = np.diag(cm).sum() / total
    ax.text(0.5, -0.12, f'전체 정확도: {acc:.1%}  |  총 샘플: {total:,}개',
            ha='center', va='top', transform=ax.transAxes,
            fontsize=9, color='#444')


# ════════════════════════════════════════════════════════════════
# ⑥ 특징 중요도 (Permutation Importance)
# ════════════════════════════════════════════════════════════════
def draw_importance(ax, importance_path=None):
    """_importance.json 을 읽어 가로 막대 그래프로 특징 중요도를 표시합니다."""
    import json

    ax.set_title('⑥ 특징 중요도 (Permutation)', fontsize=13, fontweight='bold')

    path = importance_path
    if not path or not os.path.exists(path):
        ax.text(0.5, 0.5, '중요도 데이터 없음\n(학습 후 _importance.json 생성)',
                ha='center', va='center', transform=ax.transAxes, fontsize=11, color='gray')
        ax.axis('off')
        return

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    features   = data['features']
    importance = data['importance']
    baseline   = data.get('baseline_acc', None)

    # 중요도 내림차순 정렬 (이미 정렬돼 있지만 명시)
    pairs = sorted(zip(importance, features), reverse=True)
    imp_vals  = [v for v, _ in pairs]
    feat_names = [n for _, n in pairs]

    n = len(feat_names)
    colors = ['#E86B4C' if v >= 0.1 else '#4C9BE8' if v >= 0.05 else '#95BFD8'
              for v in imp_vals]

    bars = ax.barh(range(n), imp_vals, color=colors, edgecolor='white',
                   linewidth=0.5, height=0.7)
    ax.set_yticks(range(n))
    ax.set_yticklabels(feat_names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel('정확도 하락 (중요도)', fontsize=9)
    ax.grid(True, alpha=0.3, axis='x')

    # 값 레이블
    for bar, val in zip(bars, imp_vals):
        ax.text(val + 0.002, bar.get_y() + bar.get_height() / 2,
                f'{val:.3f}', va='center', fontsize=7, color='#333')

    # 범례 (색상 기준)
    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor='#E86B4C', label='높음 (≥10%)'),
        Patch(facecolor='#4C9BE8', label='중간 (5~10%)'),
        Patch(facecolor='#95BFD8', label='낮음 (<5%)'),
    ]
    ax.legend(handles=legend_elems, fontsize=7, loc='lower right')

    if baseline is not None:
        ax.set_title(f'⑥ 특징 중요도 (베이스라인 정확도: {baseline:.1%})',
                     fontsize=11, fontweight='bold')


# ════════════════════════════════════════════════════════════════
# 렌더링 & 메인
# ════════════════════════════════════════════════════════════════
def _render_one(model_info: ModelInfo):
    """단일 모델에 대한 시각화 대시보드를 생성·저장합니다."""
    import json

    fig = plt.figure(figsize=(32, 12))
    fig.suptitle(f'MLP 재실 판단 모델 — {model_info.name}',
                 fontsize=13, fontweight='bold', y=0.99)

    # 레이아웃: 2행 5열
    #   행0: ① 구조도, ② 정확도, ③ 손실, ④ LR, ⑦ 특징 중요도
    #   행1: ⑤ PCA,   ⑥ 신뢰도, ⑤ 혼동행렬, (빈칸), ⑦ (이어짐)
    gs = fig.add_gridspec(2, 5, hspace=0.50, wspace=0.38,
                          top=0.94, bottom=0.07, left=0.03, right=0.97)

    ax_arch = fig.add_subplot(gs[0, 0])        # ① 신경망 구조도
    ax_acc  = fig.add_subplot(gs[0, 1])        # ② 에폭별 정확도
    ax_loss = fig.add_subplot(gs[0, 2])        # ③ 에폭별 손실
    ax_lr   = fig.add_subplot(gs[0, 3])        # ④ 학습률 (LR)
    ax_imp  = fig.add_subplot(gs[:, 4])        # ⑦ 특징 중요도 (2행 합침)
    ax_pca  = fig.add_subplot(gs[1, 0])        # ⑤ PCA 분포
    ax_conf = fig.add_subplot(gs[1, 1])        # ⑥ 신뢰도 히스토그램
    ax_cm   = fig.add_subplot(gs[1, 2])        # ⑤ 혼동 행렬
    ax_eff  = fig.add_subplot(gs[1, 3])        # ⑤ LR 효과 분석

    print("  ① 신경망 구조도 그리는 중...")
    draw_architecture(ax_arch, model_info=model_info)

    print("  ②③ 학습 곡선 그리는 중...")
    # LR 데이터를 history에서 읽어 수직선 공유
    _lr_for_curve = []
    if os.path.exists(model_info.history):
        import json as _j
        with open(model_info.history, encoding='utf-8') as _f:
            _h = _j.load(_f)
        _lr_for_curve = _h.get('lr', [])
    draw_learning_curve(ax_acc, ax_loss, history_path=model_info.history,
                        lr_data=_lr_for_curve)

    print("  ④ LR 변화 그리는 중...")
    draw_lr(ax_lr, history_path=model_info.history)

    print("  ⑥ 특징 중요도 그리는 중...")
    draw_importance(ax_imp, importance_path=model_info.importance)

    print("  데이터 로딩 중 (data_csv/ 직접 로드)...")
    df_train, df_val = _load_raw_dataset()

    print("  ③ 데이터 분포(PCA) 그리는 중...")
    draw_pca(ax_pca, df_train=df_train, model_info=model_info)

    print("  ④ 예측 신뢰도 분포 그리는 중...")
    draw_confidence(ax_conf, model_info=model_info, df_val=df_val)

    print("  ⑤ 혼동 행렬 그리는 중...")
    draw_confusion_matrix(ax_cm, model_info=model_info, df_val=df_val)
    print("  ⑤ LR 효과 분석 그리는 중...")
    draw_lr_effect(ax_eff, history_path=model_info.history)
    # ── 파일명: 모델명 + 최고 검증 정확도 ──────────────────────────
    acc_str = ''
    if os.path.exists(model_info.history):
        try:
            with open(model_info.history, encoding='utf-8') as f:
                h = json.load(f)
            best_acc = max(h['val_acc']) * 100
            acc_str = f'_acc{best_acc:.1f}'
        except Exception:
            pass

    filename = f'{model_info.name}{acc_str}.png'

    out_dir  = _HERE   # 스크립트가 이미 results/ 안에 위치
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)

    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✅ 저장 완료: {out_path}")


def main():
    models = _select_models()
    total  = len(models)
    for i, mi in enumerate(models, 1):
        if total > 1:
            print(f'\n[{i}/{total}] {mi.name}')
        _render_one(mi)
    if total > 1:
        print(f'\n✅ 전체 {total}개 모델 시각화 완료')


if __name__ == '__main__':
    main()
