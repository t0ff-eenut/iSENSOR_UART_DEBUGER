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

# ── 한글 폰트 설정 (macOS) ───────────────────────────────────────
matplotlib.rcParams['font.family'] = 'AppleGothic'
matplotlib.rcParams['axes.unicode_minus'] = False

# ── 경로 설정 ─────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

TRAIN_CSV    = os.path.join(SCRIPT_DIR, 'data_train.csv')
VAL_CSV      = os.path.join(SCRIPT_DIR, 'data_val.csv')
SCALER_PATH  = os.path.join(SCRIPT_DIR, 'models', 'mlp_scaler.pkl')
MODEL_PATH   = os.path.join(SCRIPT_DIR, 'models', 'mlp_weights.pt')
HISTORY_PATH = os.path.join(SCRIPT_DIR, 'models', 'train_history.json')

# 배경/사람 색상
COLOR_BG    = '#4C9BE8'   # 파랑
COLOR_HUMAN = '#E86B4C'   # 주황


def _resolve_model_paths():
    """현재 nn_mlp.py 세팅값과 일치하는 버전 모델 경로를 반환.
    없으면 고정 경로(mlp_weights.pt / mlp_scaler.pkl)로 폴백.
    Returns: (model_path, scaler_path)
    """
    import glob
    import nn_mlp as mlp_mod

    model_dir  = os.path.join(SCRIPT_DIR, 'models')
    layers_str = '-'.join(str(h) for h in mlp_mod.HIDDEN_LAYERS)
    lr_str     = f'{mlp_mod.LEARNING_RATE:.0e}'
    ep         = mlp_mod.EPOCHS
    pattern    = os.path.join(model_dir, f'mlp_L{layers_str}_ep{ep}_lr{lr_str}_*.pt')

    candidates = sorted(
        [p for p in glob.glob(pattern) if not p.endswith('_scaler.pkl')],
        reverse=True
    )
    if candidates:
        ver_model  = candidates[0]
        ver_scaler = ver_model.replace('.pt', '_scaler.pkl')
        if os.path.exists(ver_scaler):
            print(f"[visualize] 버전 모델 로드 → {os.path.basename(ver_model)}")
            return ver_model, ver_scaler

    print(f"[visualize] 고정 모델 로드 → mlp_weights.pt")
    return MODEL_PATH, SCALER_PATH


# ════════════════════════════════════════════════════════════════
# ① 신경망 구조도
# ════════════════════════════════════════════════════════════════
def draw_architecture(ax):
    """
    nn_mlp.py 의 하이퍼파라미터를 직접 읽어 MLP 구조를 동적으로 그립니다.
    HIDDEN_LAYERS 리스트를 바꾸면 은닉층 수/크기가 자동 반영됩니다.
    """
    import nn_mlp as mlp_mod

    INPUT_SIZE   = 24
    HIDDEN       = mlp_mod.HIDDEN_LAYERS          # 예: [64, 32] or [128, 64, 32]
    DROPOUT      = mlp_mod.DROPOUT_RATE
    OUTPUT_SIZE  = 2

    hidden_colors = ['#F0C895', '#95F0B4', '#C8A8F0', '#F0E695', '#A8D8F0']

    # 입력층
    layer_defs = [
        (f'입력층\n({INPUT_SIZE}개 FFT 특징)', INPUT_SIZE, '#95C8F0', None),
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
def draw_learning_curve(ax_acc, ax_loss):
    """
    학습 중 기록된 에폭별 정확도(학습/검증)와 손실를 그래프로 표시합니다.
    학습 이이력 파일(train_history.json)이 없으면 안내를 출력합니다.
    """
    import json

    no_data_msg = '학습 이력 없음\n(nn_mlp.py 학습을 먼저 실행하세요)'

    if not os.path.exists(HISTORY_PATH):
        for ax in (ax_acc, ax_loss):
            ax.text(0.5, 0.5, no_data_msg,
                    ha='center', va='center', transform=ax.transAxes,
                    fontsize=10, color='gray')
            ax.axis('off')
        ax_acc.set_title('Ⅱ 에폭별 정확도', fontsize=13, fontweight='bold')
        ax_loss.set_title('Ⅲ 에폭별 손실', fontsize=13, fontweight='bold')
        return

    with open(HISTORY_PATH, encoding='utf-8') as f:
        h = json.load(f)

    epochs     = h['epochs']
    loss       = h['loss']
    train_acc  = [v * 100 for v in h['train_acc']]
    val_acc    = [v * 100 for v in h['val_acc']]

    # ── 정확도 그래프 ─────────────────────────
    ax_acc.plot(epochs, train_acc, color='#4C9BE8', linewidth=1.8, label='학습 정확도')
    ax_acc.plot(epochs, val_acc,   color='#E86B4C', linewidth=1.8, label='검증 정확도', linestyle='--')

    # 과적합 구역: 학습 > 검증 인 구간 연합 색으로 표시
    train_arr = np.array(train_acc)
    val_arr   = np.array(val_acc)
    ax_acc.fill_between(epochs, train_arr, val_arr,
                        where=(train_arr > val_arr),
                        alpha=0.12, color='red', label='과적합 구역')

    best_epoch = epochs[int(np.argmax(val_arr))]
    best_val   = float(np.max(val_arr))
    ax_acc.axvline(best_epoch, color='gray', linestyle=':', linewidth=1.2, alpha=0.7)
    ax_acc.text(best_epoch + 0.5, best_val - 2,
                f'최고 {best_val:.1f}%\n(에폭 {best_epoch})',
                fontsize=7.5, color='#E86B4C')

    ax_acc.set_title('Ⅱ 에폭별 정확도', fontsize=13, fontweight='bold')
    ax_acc.set_xlabel('에폭', fontsize=9)
    ax_acc.set_ylabel('정확도 (%)', fontsize=9)
    ax_acc.set_ylim(max(0, min(train_acc + val_acc) - 5), 102)
    ax_acc.legend(fontsize=9)
    ax_acc.grid(True, alpha=0.3)

    # ── 손실 그래프 ─────────────────────────
    ax_loss.plot(epochs, loss, color='#8E44AD', linewidth=1.8)
    ax_loss.set_title('Ⅲ 에폭별 손실 (CrossEntropy)', fontsize=13, fontweight='bold')
    ax_loss.set_xlabel('에폭', fontsize=9)
    ax_loss.set_ylabel('손실', fontsize=9)
    ax_loss.grid(True, alpha=0.3)


# ════════════════════════════════════════════════════════════════
# Ⅲ 데이터 분포도 (PCA 2D)
# ════════════════════════════════════════════════════════════════
def draw_pca(ax):
    """
    학습 데이터를 PCA로 2차원에 투영해 배경/사람 분포를 점으로 표시합니다.
    """
    from sklearn.decomposition import PCA
    import csv

    ax.set_title('③ 데이터 분포 (PCA 2D 투영)', fontsize=13, fontweight='bold')

    if not os.path.exists(TRAIN_CSV):
        ax.text(0.5, 0.5, '학습 데이터 없음\n(prepare_data.py 먼저 실행)',
                ha='center', va='center', transform=ax.transAxes, fontsize=11, color='gray')
        return

    # CSV 로드
    import svm as svm_mod
    svm_ref = svm_mod.SVM_Module()
    feat_idx = svm_ref.A_feature_indices

    X_list, y_list = [], []
    with open(TRAIN_CSV) as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if not row: continue
            X_list.append([float(v) for v in row[:-1]])
            y_list.append(int(float(row[-1])))

    X = np.array(X_list)[:, feat_idx]
    y = np.array(y_list)

    # 표시할 샘플 수 제한 (너무 많으면 느림)
    MAX_SAMPLES = 3000
    if len(y) > MAX_SAMPLES:
        idx = np.random.choice(len(y), MAX_SAMPLES, replace=False)
        X, y = X[idx], y[idx]

    # 정규화 후 PCA
    if os.path.exists(SCALER_PATH):
        with open(SCALER_PATH, 'rb') as f:
            scaler = pickle.load(f)
        X_scaled = scaler.transform(X)
    else:
        from sklearn.preprocessing import StandardScaler
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
def draw_confidence(ax):
    """
    검증 데이터에 대해 모델이 '사람'이라고 예측한 확률 분포를 히스토그램으로 표시합니다.
    0.5 미만 → 배경 예측, 0.5 이상 → 사람 예측
    """
    import torch, csv

    ax.set_title('④ 예측 신뢰도 분포 (사람 확률)', fontsize=13, fontweight='bold')

    cur_model_path, cur_scaler_path = _resolve_model_paths()
    if not (os.path.exists(cur_model_path) and os.path.exists(VAL_CSV)):
        ax.text(0.5, 0.5, '모델 또는 검증 데이터 없음\n(먼저 학습을 실행하세요)',
                ha='center', va='center', transform=ax.transAxes, fontsize=11, color='gray')
        return

    sys.path.insert(0, PARENT_DIR)
    import svm as svm_mod
    svm_ref = svm_mod.SVM_Module()
    feat_idx = svm_ref.A_feature_indices

    # 데이터 로드
    X_list, y_list = [], []
    with open(VAL_CSV) as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if not row: continue
            X_list.append([float(v) for v in row[:-1]])
            y_list.append(int(float(row[-1])))

    X_raw = np.array(X_list)[:, feat_idx].astype(np.float32)
    y     = np.array(y_list)

    with open(cur_scaler_path, 'rb') as f:
        scaler = pickle.load(f)
    X_scaled = torch.tensor(scaler.transform(X_raw), dtype=torch.float32)

    # 모델 로드 & 추론
    from nn_mlp import OccupancyMLP
    model = OccupancyMLP(len(feat_idx))
    model.load_state_dict(torch.load(cur_model_path, map_location='cpu', weights_only=True))
    model.eval()
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

    # 오분류 설명
    ax.text(0.25, 0.92, '← 배경으로 예측',
            ha='center', va='top', transform=ax.transAxes, fontsize=8, color='#555')
    ax.text(0.75, 0.92, '사람으로 예측 →',
            ha='center', va='top', transform=ax.transAxes, fontsize=8, color='#555')


# ════════════════════════════════════════════════════════════════
# Ⅴ 혼동 행렬 히트맵
# ════════════════════════════════════════════════════════════════
def draw_confusion_matrix(ax):
    """
    혼동 행렬을 색상 히트맵으로 표시합니다.
    대각선(TN, TP)은 초록, 비대각선(FP, FN)은 빨간 계열.
    """
    import torch, csv
    from sklearn.metrics import confusion_matrix

    ax.set_title('⑤ 혼동 행렬', fontsize=13, fontweight='bold')

    cur_model_path, cur_scaler_path = _resolve_model_paths()
    if not (os.path.exists(cur_model_path) and os.path.exists(VAL_CSV)):
        ax.text(0.5, 0.5, '모델 또는 검증 데이터 없음',
                ha='center', va='center', transform=ax.transAxes, fontsize=11, color='gray')
        return

    sys.path.insert(0, PARENT_DIR)
    import svm as svm_mod
    svm_ref = svm_mod.SVM_Module()
    feat_idx = svm_ref.A_feature_indices

    X_list, y_list = [], []
    with open(VAL_CSV) as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if not row: continue
            X_list.append([float(v) for v in row[:-1]])
            y_list.append(int(float(row[-1])))

    X_raw = np.array(X_list)[:, feat_idx].astype(np.float32)
    y     = np.array(y_list)

    with open(cur_scaler_path, 'rb') as f:
        scaler = pickle.load(f)
    X_scaled = torch.tensor(scaler.transform(X_raw), dtype=torch.float32)

    from nn_mlp import OccupancyMLP
    model = OccupancyMLP(len(feat_idx))
    model.load_state_dict(torch.load(cur_model_path, map_location='cpu', weights_only=True))
    model.eval()
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
# 메인
# ════════════════════════════════════════════════════════════════
def main():
    fig = plt.figure(figsize=(20, 12))
    fig.suptitle('MLP 재실 판단 모델 — 동작 시각화', fontsize=16, fontweight='bold', y=0.99)

    # 레이아웃: 2행 3열
    #   행0: ① 구조도(전체 폭), ② 정확도, ③ 손실
    #   행1: ③ PCA,            ④ 신뢰도, ⑤ 혼동 행렬
    gs = fig.add_gridspec(2, 3, hspace=0.50, wspace=0.35,
                          top=0.94, bottom=0.07, left=0.05, right=0.97)

    ax_arch = fig.add_subplot(gs[0, 0])   # 신경망 구조도
    ax_acc  = fig.add_subplot(gs[0, 1])   # 에폭별 정확도
    ax_loss = fig.add_subplot(gs[0, 2])   # 에폭별 손실
    ax_pca  = fig.add_subplot(gs[1, 0])   # PCA 분포
    ax_conf = fig.add_subplot(gs[1, 1])   # 신뢰도 히스토그램
    ax_cm   = fig.add_subplot(gs[1, 2])   # 혼동 행렬

    print("① 신경망 구조도 그리는 중...")
    draw_architecture(ax_arch)

    print("②③ 학습 공선 그리는 중...")
    draw_learning_curve(ax_acc, ax_loss)

    print("③ 데이터 분포(PCA) 그리는 중...")
    draw_pca(ax_pca)

    print("④ 예측 신뢰도 분포 그리는 중...")
    draw_confidence(ax_conf)

    print("⑤ 혼동 행렬 그리는 중...")
    draw_confusion_matrix(ax_cm)

    # ── 파일명: 하이퍼파라미터 + 최고 검증 정확도 + 날짜시각 ──────
    import nn_mlp as mlp_mod
    import json
    from datetime import datetime

    layers_str = '-'.join(str(h) for h in mlp_mod.HIDDEN_LAYERS)  # 예: 128-64-32
    ep         = mlp_mod.EPOCHS
    lr         = mlp_mod.LEARNING_RATE
    dp         = mlp_mod.DROPOUT_RATE

    # 최고 검증 정확도 읽기 (train_history.json)
    acc_str = ''
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding='utf-8') as f:
                h = json.load(f)
            best_acc = max(h['val_acc']) * 100
            acc_str = f'_acc{best_acc:.1f}'
        except Exception:
            pass

    timestamp  = datetime.now().strftime('%m%d_%H%M')
    filename   = f'mlp_L{layers_str}_ep{ep}_lr{lr:.0e}_dp{int(dp*10)}{acc_str}_{timestamp}.png'
    # 예: mlp_L128-64-32_ep200_lr5e-04_dp3_acc97.5_0422_1430.png

    out_dir = os.path.join(SCRIPT_DIR, 'results')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)

    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"\n✅ 저장 완료: {out_path}")
    plt.show()


if __name__ == '__main__':
    main()
