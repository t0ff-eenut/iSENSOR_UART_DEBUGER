"""
ESP32-C3 배포용 int8 양자화 C 코드 생성
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
실행: python3 AI/export/export_int8.py
출력: AI/export/output/mlp_int8.h
      AI/export/output/mlp_int8.c

양자화 방식: Symmetric Per-Tensor Post-Training Quantization (PTQ)
  - 가중치: float32 → int8  (scale = max|W| / 127)
  - 편향:   float32 → int32 (scale = in_scale × w_scale)
  - 내부 누산: int32 (MAC 루프 정수 연산)
  - float 변환: 레이어 출력에서만 1회 (dequantize)

float32 대비 장점:
  - 가중치 메모리: 1/4 (int8 vs float32)
  - MAC 속도: RISC-V 정수 곱셈 활용 → float보다 빠름 (FPU 없는 ESP32-C3)
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
    print(f"[int8] 모델 없음 → {mp}")
    print("       먼저 python3 AI/nn_mlp.py 로 학습하세요")
    sys.exit(1)

model_sd    = torch.load(mp, map_location='cpu', weights_only=True)
input_size  = model_sd['net.0.weight'].shape[1]  # 체크포인트에서 입력 크기 자동 추출
model       = nn_mlp.OccupancyMLP.__new__(nn_mlp.OccupancyMLP)
nn_mlp.OccupancyMLP.__init__(model, input_size)
model.load_state_dict(model_sd)
model.eval()
with open(sp, 'rb') as f:
    scaler = pickle.load(f)

print(f"[int8] 모델 로드 → {os.path.basename(mp)}")
print(f"[int8] 세팅: HIDDEN_LAYERS={nn_mlp.HIDDEN_LAYERS}  EPOCHS={nn_mlp.EPOCHS}  LR={nn_mlp.LEARNING_RATE}")

# ── BatchNorm 융합 ───────────────────────────────────────────────
def _fuse_bn(lin, bn):
    W    = lin.weight.detach().numpy().copy()
    b    = (lin.bias.detach().numpy().copy()
            if lin.bias is not None else np.zeros(lin.out_features))
    g    = bn.weight.detach().numpy()
    beta = bn.bias.detach().numpy()
    mean = bn.running_mean.detach().numpy()
    var  = bn.running_var.detach().numpy()
    std  = np.sqrt(var + bn.eps)
    return W * (g / std)[:, None], (b - mean) / std * g + beta

layers_f = []   # [{'W', 'b', 'relu'}]
mods = list(model.net.children())
i = 0
while i < len(mods):
    m = mods[i]
    if isinstance(m, nn.Linear):
        if i + 1 < len(mods) and isinstance(mods[i + 1], nn.BatchNorm1d):
            W, b = _fuse_bn(m, mods[i + 1])
            has_relu = (i + 2 < len(mods) and isinstance(mods[i + 2], nn.ReLU))
            layers_f.append({'W': W, 'b': b, 'relu': has_relu})
            i += 2
        else:
            W = m.weight.detach().numpy().copy()
            b = (m.bias.detach().numpy().copy()
                 if m.bias is not None else np.zeros(m.out_features))
            has_relu = (i + 1 < len(mods) and isinstance(mods[i + 1], nn.ReLU))
            layers_f.append({'W': W, 'b': b, 'relu': has_relu})
    i += 1

INPUT_SIZE = layers_f[0]['W'].shape[1]
SIZES      = [l['W'].shape[0] for l in layers_f]
N          = len(layers_f)

# ── 캘리브레이션 데이터 로드 ──────────────────────────────────────
val_csv = os.path.join(AI_DIR, 'data_val.csv')
if not os.path.exists(val_csv):
    print(f"[int8] 캘리브레이션 데이터 없음 → {val_csv}")
    sys.exit(1)

X_list, y_list = [], []
with open(val_csv) as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        if not row:
            continue
        try:
            # 특징 컨럼(0~CSV_N_FEATURES-1)만 명시적으로 추출 — ADC/FFT/meta 컨럼 무시
            X_list.append([float(row[i]) for i in range(csv_layout.CSV_N_FEATURES)])
            y_list.append(int(float(row[-1])))
        except (ValueError, IndexError):
            continue

X_raw = np.array(X_list, dtype=np.float32)
y_cal = np.array(y_list)
X_cal = scaler.transform(X_raw).astype(np.float32)
print(f"[int8] 캘리브레이션: {len(X_cal)} 샘플")

# ── 활성화 범위 수집 (각 레이어 입력의 max|x|) ───────────────────
def _calibrate(X_norm):
    """fused float32 레이어로 순방향 전파 → 각 레이어 입력 max(abs) 수집"""
    cur = X_norm.copy()
    in_maxs = []
    for l in layers_f:
        in_maxs.append(float(np.abs(cur).max()))
        out = cur @ l['W'].T + l['b']
        if l['relu']:
            out = np.maximum(out, 0.0)
        cur = out
    return in_maxs

in_maxs   = _calibrate(X_cal)
in_scales = [mx / 127.0 if mx > 0 else 1e-8 for mx in in_maxs]
print(f"[int8] 레이어별 입력 max: {[f'{v:.4f}' for v in in_maxs]}")

# ── 가중치 양자화 (symmetric per-tensor int8) ─────────────────────
def _quant_w(W: np.ndarray):
    """가중치 → int8 + scale"""
    max_abs = float(np.abs(W).max())
    scale   = max_abs / 127.0 if max_abs > 0 else 1e-8
    W_q     = np.clip(np.round(W / scale), -127, 127).astype(np.int8)
    return W_q, scale

def _quant_bias(b: np.ndarray, in_s: float, w_s: float):
    """편향 → int32 (int8 누산 단위로 사전 양자화)"""
    acc_scale = in_s * w_s
    return np.round(b / acc_scale).astype(np.int32)

layers_q = []
for i, l in enumerate(layers_f):
    W_q, w_s = _quant_w(l['W'])
    in_s     = in_scales[i]
    b_q      = _quant_bias(l['b'], in_s, w_s)
    layers_q.append({
        'W_q':      W_q,
        'b_q':      b_q,
        'in_scale': in_s,
        'w_scale':  w_s,
        'relu':     l['relu'],
    })
    print(f"[int8] Layer {i+1}: w_scale={w_s:.6f}, in_scale={in_s:.6f}")

# ── Python 시뮬레이션 (C 코드와 동일 로직) ───────────────────────
def _infer_q8(X_norm: np.ndarray) -> np.ndarray:
    cur = X_norm.copy()
    for lq in layers_q:
        in_s = lq['in_scale']
        w_s  = lq['w_scale']
        # 입력 양자화 (float → int8)
        x_q  = np.clip(np.round(cur / in_s), -127, 127).astype(np.int32)
        W_q  = lq['W_q'].astype(np.int32)
        b_q  = lq['b_q'].astype(np.int32)
        # int32 MAC 누산
        acc  = x_q @ W_q.T + b_q
        # dequantize → float
        val  = acc.astype(np.float32) * (in_s * w_s)
        cur  = np.maximum(val, 0.0) if lq['relu'] else val
    # Softmax
    mx    = cur.max(axis=1, keepdims=True)
    exps  = np.exp(cur - mx)
    return exps / exps.sum(axis=1, keepdims=True)

probs_q = _infer_q8(X_cal)
preds_q = probs_q.argmax(axis=1)
acc_q   = (preds_q == y_cal).mean()

# float32 기준 정확도
with torch.no_grad():
    probs_f = torch.softmax(model(torch.tensor(X_cal)), dim=1).numpy()
acc_f = (probs_f.argmax(axis=1) == y_cal).mean()

print(f"\n[int8] float32 정확도: {acc_f:.1%}")
print(f"[int8] int8   정확도: {acc_q:.1%}  (차이: {(acc_q - acc_f)*100:+.2f}%p)")

# ── C 배열 생성 헬퍼 ─────────────────────────────────────────────
def _c_int8_arr(arr: np.ndarray, name: str) -> str:
    flat  = arr.flatten().astype(np.int8)
    lines = [', '.join(f'{int(v):4d}' for v in flat[k:k + 16])
             for k in range(0, len(flat), 16)]
    body  = ',\n    '.join(lines)
    return (f'/* shape: {list(arr.shape)} */\n'
            f'static const int8_t {name}[{len(flat)}] = {{\n'
            f'    {body}\n}};\n\n')

def _c_int32_arr(arr: np.ndarray, name: str) -> str:
    flat  = arr.flatten().astype(np.int32)
    lines = [', '.join(f'{int(v):11d}' for v in flat[k:k + 8])
             for k in range(0, len(flat), 8)]
    body  = ',\n    '.join(lines)
    return (f'/* shape: {list(arr.shape)} */\n'
            f'static const int32_t {name}[{len(flat)}] = {{\n'
            f'    {body}\n}};\n\n')

def _c_float_arr(arr: np.ndarray, name: str) -> str:
    flat = arr.flatten()
    vals = ', '.join(f'{v:.8f}f' for v in flat)
    return f'static const float {name}[{len(flat)}] = {{{vals}}};\n\n'

# ── Header 생성 ──────────────────────────────────────────────────
H = []
H.append('/**\n')
H.append(' * mlp_int8.h  —  MLP int8 양자화 추론  (ESP32-C3 배포용)\n')
H.append(' * 자동 생성: AI/export/export_int8.py\n')
H.append(f' * 모델: {os.path.basename(mp)}\n')
H.append(f' * 구조: {INPUT_SIZE} → {" → ".join(str(s) for s in SIZES)}\n')
H.append(f' * 양자화: Symmetric PTQ int8  (float32 대비 {(acc_q-acc_f)*100:+.2f}%p)\n')
H.append(' *\n')
H.append(' * 사용법 (ESP-IDF):\n')
H.append(' *   #include "mlp_int8.h"\n')
H.append(' *   float prob; int label = mlp_int8_infer(features, &prob);\n')
H.append(' */\n\n')
H.append('#pragma once\n')
H.append('#include <math.h>\n')
H.append('#include <stdint.h>\n\n')
H.append(f'#define MLP_INPUT_SIZE {INPUT_SIZE}\n\n')

H.append('/* ── StandardScaler 정규화 파라미터 ─────────────────────── */\n')
H.append(_c_float_arr(np.array(scaler.mean_),  'MLP_SCALER_MEAN'))
H.append(_c_float_arr(np.array(scaler.scale_), 'MLP_SCALER_STD'))

H.append('/* ── 레이어별 양자화 scale (float) ──────────────────────── */\n')
for i, lq in enumerate(layers_q):
    acc_s = lq['in_scale'] * lq['w_scale']
    H.append(f'#define MLP_L{i+1}_IN_SCALE   {lq["in_scale"]:.8f}f\n')
    H.append(f'#define MLP_L{i+1}_W_SCALE    {lq["w_scale"]:.8f}f\n')
    H.append(f'#define MLP_L{i+1}_ACC_SCALE  {acc_s:.8f}f  /* = IN × W */\n\n')

for i, lq in enumerate(layers_q):
    H.append(f'/* ── Layer {i+1} 가중치 (int8) ──────────────────────────── */\n')
    H.append(_c_int8_arr(lq['W_q'], f'MLP_W{i+1}_Q'))
    H.append(f'/* ── Layer {i+1} 편향 (int32, 사전 양자화) ──────────────── */\n')
    H.append(_c_int32_arr(lq['b_q'], f'MLP_B{i+1}_Q'))

H.append('/**\n')
H.append(' * @brief  MLP int8 양자화 추론\n')
H.append(' * @param  raw_input  입력 배열 (크기: MLP_INPUT_SIZE, 정규화 전)\n')
H.append(' * @param  human_prob 사람 확률 출력 (0.0 ~ 1.0)\n')
H.append(' * @return 0 = 배경(Background), 1 = 사람(Human)\n')
H.append(' */\n')
H.append('int mlp_int8_infer(const float *raw_input, float *human_prob);\n')

# ── Source 생성 ──────────────────────────────────────────────────
C = []
C.append('#include "mlp_int8.h"\n\n')

C.append('/* float → int8 양자화 (symmetric) */\n')
C.append('static int8_t _to_q8(float v, float scale) {\n')
C.append('    float q = v / scale;\n')
C.append('    if (q >  127.0f) return  127;\n')
C.append('    if (q < -127.0f) return -127;\n')
C.append('    return (int8_t)(int32_t)(q >= 0.0f ? q + 0.5f : q - 0.5f);\n')
C.append('}\n\n')

C.append('/* int8 완전연결층: int32 MAC 누산 → float 출력 */\n')
C.append('static void _fc_q8(\n')
C.append('    const int8_t  *in,   int     in_n,\n')
C.append('    const int8_t  *W_q,  float   in_scale,\n')
C.append('    const int32_t *b_q,  float   acc_scale,\n')
C.append('    float *out, int out_n, int relu\n')
C.append(') {\n')
C.append('    for (int i = 0; i < out_n; i++) {\n')
C.append('        int32_t acc = b_q[i];\n')
C.append('        const int8_t *wi = W_q + i * in_n;\n')
C.append('        for (int j = 0; j < in_n; j++)\n')
C.append('            acc += (int32_t)wi[j] * (int32_t)in[j];  /* int8×int8→int32 */\n')
C.append('        float s = (float)acc * acc_scale;\n')
C.append('        out[i] = (relu && s < 0.0f) ? 0.0f : s;\n')
C.append('    }\n')
C.append('}\n\n')

C.append('int mlp_int8_infer(const float *raw_input, float *human_prob) {\n')
C.append('    /* Step 1: StandardScaler 정규화 */\n')
C.append(f'    float x[{INPUT_SIZE}];\n')
C.append(f'    for (int i = 0; i < {INPUT_SIZE}; i++)\n')
C.append('        x[i] = (raw_input[i] - MLP_SCALER_MEAN[i]) / MLP_SCALER_STD[i];\n\n')

prev_f, prev_q, prev_sz = 'x', 'x_q', INPUT_SIZE

C.append(f'    /* Step 2: 입력 → int8 양자화 */\n')
C.append(f'    int8_t {prev_q}[{INPUT_SIZE}];\n')
C.append(f'    for (int i = 0; i < {INPUT_SIZE}; i++) {prev_q}[i] = _to_q8({prev_f}[i], MLP_L1_IN_SCALE);\n\n')

for i, lq in enumerate(layers_q):
    out_sz   = SIZES[i]
    relu_val = 1 if lq['relu'] else 0
    cur_f    = f'h{i + 1}' if i < N - 1 else 'out'
    cur_q    = f'h{i + 1}_q'
    C.append(f'    /* Step {i + 3}: Layer {i + 1} */\n')
    C.append(f'    float {cur_f}[{out_sz}];\n')
    C.append(f'    _fc_q8({prev_q}, {prev_sz}, MLP_W{i+1}_Q, MLP_L{i+1}_IN_SCALE,\n')
    C.append(f'           MLP_B{i+1}_Q, MLP_L{i+1}_ACC_SCALE, {cur_f}, {out_sz}, {relu_val});\n')
    if lq['relu'] and i < N - 1:
        next_in_scale = layers_q[i + 1]['in_scale']
        C.append(f'    int8_t {cur_q}[{out_sz}];\n')
        C.append(f'    for (int i = 0; i < {out_sz}; i++) {cur_q}[i] = _to_q8({cur_f}[i], MLP_L{i+2}_IN_SCALE);\n')
        prev_q = cur_q
    C.append('\n')
    prev_f, prev_sz = cur_f, out_sz

C.append('    /* Step Final: Softmax → 확률 */\n')
C.append('    float mx = out[0] > out[1] ? out[0] : out[1];\n')
C.append('    float e0 = expf(out[0] - mx), e1 = expf(out[1] - mx);\n')
C.append('    *human_prob = e1 / (e0 + e1);\n')
C.append('    return e1 > e0 ? 1 : 0;\n')
C.append('}\n')

# ── 파일 저장 ─────────────────────────────────────────────────────
for path, content in [
    (os.path.join(OUT_DIR, 'mlp_int8.h'), H),
    (os.path.join(OUT_DIR, 'mlp_int8.c'), C),
]:
    with open(path, 'w') as f:
        f.write(''.join(content))
    print(f"[int8] 저장 완료 → {path}")

# ── 크기 비교 ─────────────────────────────────────────────────────
w_params   = sum(lq['W_q'].size for lq in layers_q)
b_params   = sum(lq['b_q'].size for lq in layers_q)
scaler_p   = len(scaler.mean_) * 2
int8_bytes = w_params * 1 + b_params * 4 + scaler_p * 4
f32_bytes  = (w_params + b_params + scaler_p) * 4

print(f"\n[비교]")
print(f"  float32 모델 크기: {f32_bytes / 1024:.1f} KB")
print(f"  int8    모델 크기: {int8_bytes / 1024:.1f} KB  ({f32_bytes / int8_bytes:.1f}x 압축)")
print(f"  정확도 손실:       {(acc_q - acc_f) * 100:+.2f}%p")
