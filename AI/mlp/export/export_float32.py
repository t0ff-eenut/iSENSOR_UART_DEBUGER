"""
ESP32-C3 배포용 float32 C 코드 생성
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
실행: python3 AI/export/export_float32.py
출력: AI/export/output/mlp_float32.h
      AI/export/output/mlp_float32.c

특징:
  - BatchNorm을 Linear에 융합 → C 코드에서 BN 연산 불필요
  - StandardScaler 정규화 내장
  - 단일 헤더 포함으로 ESP-IDF 프로젝트에 바로 사용 가능
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os, sys, glob, csv, pickle
import numpy as np
import torch
import torch.nn as nn

# ── 경로 설정 ─────────────────────────────────────────────────────
EXPORT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_DIR     = os.path.dirname(EXPORT_DIR)
ROOT_DIR   = os.path.dirname(AI_DIR)
OUT_DIR    = os.path.join(EXPORT_DIR, 'output')
os.makedirs(OUT_DIR, exist_ok=True)

sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, AI_DIR)
import nn_mlp
import csv_layout   # CSV 컨럼 레이아웃 공용 상수 (ROOT_DIR = AI/ 이어서 로드 가능)

# ── 현재 세팅과 일치하는 모델 탐색 ──────────────────────────────
def _find_model():
    d   = os.path.join(AI_DIR, 'models')
    ls  = '-'.join(str(h) for h in nn_mlp.HIDDEN_LAYERS)
    lr  = f'{nn_mlp.LEARNING_RATE:.0e}'
    pts = sorted(
        [p for p in glob.glob(os.path.join(d, f'mlp_L{ls}_ep{nn_mlp.EPOCHS}_lr{lr}_*.pt'))
         if not p.endswith('_scaler.pkl')],
        reverse=True
    )
    if pts:
        sc = pts[0].replace('.pt', '_scaler.pkl')
        if os.path.exists(sc):
            return pts[0], sc
    return (os.path.join(d, 'mlp_weights.pt'),
            os.path.join(d, 'mlp_scaler.pkl'))

mp, sp = _find_model()
if not os.path.exists(mp):
    print(f"[float32] 모델 없음 → {mp}")
    print("          먼저 python3 AI/nn_mlp.py 로 학습하세요")
    sys.exit(1)

model_sd    = torch.load(mp, map_location='cpu', weights_only=True)
input_size  = model_sd['net.0.weight'].shape[1]  # 체크포인트에서 입력 크기 자동 추출
model       = nn_mlp.OccupancyMLP.__new__(nn_mlp.OccupancyMLP)
nn_mlp.OccupancyMLP.__init__(model, input_size)
model.load_state_dict(model_sd)
model.eval()
with open(sp, 'rb') as f:
    scaler = pickle.load(f)

print(f"[float32] 모델 로드 → {os.path.basename(mp)}")
print(f"[float32] 세팅: HIDDEN_LAYERS={nn_mlp.HIDDEN_LAYERS}  EPOCHS={nn_mlp.EPOCHS}  LR={nn_mlp.LEARNING_RATE}")

# ── BatchNorm 융합 ───────────────────────────────────────────────
def _fuse_bn(lin, bn):
    """Linear + BatchNorm1d → 단일 Linear (BN 파라미터 흡수)"""
    W    = lin.weight.detach().numpy().copy()
    b    = (lin.bias.detach().numpy().copy()
            if lin.bias is not None else np.zeros(lin.out_features))
    g    = bn.weight.detach().numpy()
    beta = bn.bias.detach().numpy()
    mean = bn.running_mean.detach().numpy()
    var  = bn.running_var.detach().numpy()
    std  = np.sqrt(var + bn.eps)
    W_f  = W * (g / std)[:, None]
    b_f  = (b - mean) / std * g + beta
    return W_f, b_f

# ── 레이어 순회 & 가중치 추출 ────────────────────────────────────
layers = []   # [{'W': ndarray, 'b': ndarray, 'relu': bool}]
mods = list(model.net.children())
i = 0
while i < len(mods):
    m = mods[i]
    if isinstance(m, nn.Linear):
        if i + 1 < len(mods) and isinstance(mods[i + 1], nn.BatchNorm1d):
            W, b = _fuse_bn(m, mods[i + 1])
            has_relu = (i + 2 < len(mods) and isinstance(mods[i + 2], nn.ReLU))
            layers.append({'W': W, 'b': b, 'relu': has_relu})
            i += 2  # BN 건너뜀
        else:
            W = m.weight.detach().numpy().copy()
            b = (m.bias.detach().numpy().copy()
                 if m.bias is not None else np.zeros(m.out_features))
            has_relu = (i + 1 < len(mods) and isinstance(mods[i + 1], nn.ReLU))
            layers.append({'W': W, 'b': b, 'relu': has_relu})
    i += 1

INPUT_SIZE = layers[0]['W'].shape[1]
SIZES      = [l['W'].shape[0] for l in layers]
print(f"[float32] 구조 (BN 융합 후): {INPUT_SIZE} → {' → '.join(str(s) for s in SIZES)}")

# ── C 배열 생성 헬퍼 ─────────────────────────────────────────────
def _c_float_arr(arr: np.ndarray, name: str) -> str:
    flat  = arr.flatten()
    lines = [', '.join(f'{v:.8f}f' for v in flat[k:k + 8])
             for k in range(0, len(flat), 8)]
    body  = ',\n    '.join(lines)
    return (f'/* shape: {list(arr.shape)} */\n'
            f'static const float {name}[{len(flat)}] = {{\n'
            f'    {body}\n}};\n\n')

# ── Header 생성 ──────────────────────────────────────────────────
H = []
H.append('/**\n')
H.append(' * mlp_float32.h  —  MLP float32 추론  (ESP32-C3 배포용)\n')
H.append(' * 자동 생성: AI/export/export_float32.py\n')
H.append(f' * 모델: {os.path.basename(mp)}\n')
H.append(f' * 구조: {INPUT_SIZE} → {" → ".join(str(s) for s in SIZES)}\n')
H.append(' *\n')
H.append(' * 사용법 (ESP-IDF):\n')
H.append(' *   #include "mlp_float32.h"\n')
H.append(' *   float prob; int label = mlp_float32_infer(features, &prob);\n')
H.append(' */\n\n')
H.append('#pragma once\n')
H.append('#include <math.h>\n')
H.append('#include <stdint.h>\n\n')
H.append(f'#define MLP_INPUT_SIZE {INPUT_SIZE}  /* 입력 특징 수 (FFT 선택 특징) */\n\n')

H.append('/* ── StandardScaler 정규화 파라미터 ─────────────────────── */\n')
H.append(_c_float_arr(np.array(scaler.mean_),  'MLP_SCALER_MEAN'))
H.append(_c_float_arr(np.array(scaler.scale_), 'MLP_SCALER_STD'))

for i, l in enumerate(layers):
    tag = 'Linear→BN→ReLU (융합)' if i == 0 else ('Linear→ReLU' if l['relu'] else 'Linear (출력층)')
    H.append(f'/* ── Layer {i + 1}: {tag} ─────────────────────────────── */\n')
    H.append(_c_float_arr(l['W'], f'MLP_W{i + 1}'))
    H.append(_c_float_arr(l['b'], f'MLP_B{i + 1}'))

H.append('/**\n')
H.append(' * @brief  MLP float32 추론\n')
H.append(' * @param  raw_input  입력 특징 배열 (크기: MLP_INPUT_SIZE, 정규화 전)\n')
H.append(' * @param  human_prob 사람 확률 출력 (0.0 ~ 1.0)\n')
H.append(' * @return 0 = 배경(Background), 1 = 사람(Human)\n')
H.append(' */\n')
H.append('int mlp_float32_infer(const float *raw_input, float *human_prob);\n')

# ── Source 생성 ──────────────────────────────────────────────────
C = []
C.append('#include "mlp_float32.h"\n\n')
C.append('/* 완전연결층: 행렬곱 + 편향 + 선택적 ReLU */\n')
C.append('static void _fc(const float *in, int in_n, const float *W,\n')
C.append('                const float *b, float *out, int out_n, int relu) {\n')
C.append('    for (int i = 0; i < out_n; i++) {\n')
C.append('        float s = b[i];\n')
C.append('        for (int j = 0; j < in_n; j++) s += W[i * in_n + j] * in[j];\n')
C.append('        out[i] = (relu && s < 0.0f) ? 0.0f : s;\n')
C.append('    }\n')
C.append('}\n\n')

C.append('int mlp_float32_infer(const float *raw_input, float *human_prob) {\n')
C.append(f'    /* Step 1: StandardScaler 정규화 */\n')
C.append(f'    float x[{INPUT_SIZE}];\n')
C.append(f'    for (int i = 0; i < {INPUT_SIZE}; i++)\n')
C.append('        x[i] = (raw_input[i] - MLP_SCALER_MEAN[i]) / MLP_SCALER_STD[i];\n\n')

prev, prev_sz = 'x', INPUT_SIZE
for i, l in enumerate(layers):
    out_sz   = SIZES[i]
    cur      = f'h{i + 1}' if i < len(layers) - 1 else 'out'
    relu_val = 1 if l['relu'] else 0
    C.append(f'    /* Step {i + 2}: Layer {i + 1} */\n')
    C.append(f'    float {cur}[{out_sz}];\n')
    C.append(f'    _fc({prev}, {prev_sz}, MLP_W{i + 1}, MLP_B{i + 1}, {cur}, {out_sz}, {relu_val});\n\n')
    prev, prev_sz = cur, out_sz

C.append('    /* Step Final: Softmax → 확률 계산 */\n')
C.append('    float mx = out[0] > out[1] ? out[0] : out[1];\n')
C.append('    float e0 = expf(out[0] - mx), e1 = expf(out[1] - mx);\n')
C.append('    *human_prob = e1 / (e0 + e1);\n')
C.append('    return e1 > e0 ? 1 : 0;\n')
C.append('}\n')

# ── 파일 저장 ─────────────────────────────────────────────────────
for path, content in [
    (os.path.join(OUT_DIR, 'mlp_float32.h'), H),
    (os.path.join(OUT_DIR, 'mlp_float32.c'), C),
]:
    with open(path, 'w') as f:
        f.write(''.join(content))
    print(f"[float32] 저장 완료 → {path}")

# ── 크기 출력 ─────────────────────────────────────────────────────
total = sum(l['W'].size + l['b'].size for l in layers) + len(scaler.mean_) * 2
print(f"\n[float32] 파라미터 수: {total:,}개")
print(f"[float32] 모델 크기:   {total * 4 / 1024:.1f} KB  (float32 기준)")

# ── 정확도 검증 ───────────────────────────────────────────────────
val_csv = os.path.join(AI_DIR, 'data_val.csv')
if os.path.exists(val_csv):
    X_list, y_list = [], []
    with open(val_csv) as f:
        reader = csv.reader(f)
        next(reader)  # 헤더 스킵
        for row in reader:
            if not row:
                continue
            try:
                # 특징 컨럼(0~CSV_N_FEATURES-1)만 명시적으로 추출 — ADC/FFT/meta 컨럼 무시
                X_list.append([float(row[i]) for i in range(csv_layout.CSV_N_FEATURES)])
                y_list.append(int(float(row[-1])))
            except (ValueError, IndexError):
                continue
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list)
    Xs = torch.tensor(scaler.transform(X), dtype=torch.float32)
    with torch.no_grad():
        preds = model(Xs).argmax(dim=1).numpy()
    print(f"\n[float32] PyTorch 검증 정확도: {(preds == y).mean():.1%}")
    print(f"[float32] (C 코드는 동일한 가중치를 사용하므로 동일한 결과 예상)")
else:
    print(f"[float32] 검증 데이터 없음 → {val_csv}")
