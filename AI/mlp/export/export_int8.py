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

import os, sys, glob, csv, pickle, datetime, re
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


def _parse_model_info(model_path: str, ai_dir: str) -> dict:
    """모델 파일명 + 로그 파일에서 학습 하이퍼파라미터와 결과를 추출한다."""
    stem     = os.path.splitext(os.path.basename(model_path))[0]
    log_path = os.path.join(ai_dir, 'logs', stem + '.log')
    info = {
        'n_samples': '?', 'n_features': '?', 'feature_mode': '?',
        'hidden_layers': '?', 'scaler_type': '?', 'batch_size': '?',
        'dropout': '?', 'lr': '?', 'lr_factor': '?', 'lr_patience': '?',
        'epochs': '?', 'train_date': '?',
        'best_val_acc': '?', 'best_epoch': '?', 'final_val_acc': '?',
        'feature_list': '',
    }
    # ---- 파일명 파싱 ----
    m = re.match(
        r'MLP_(\d+)_F(\d+)(_PC)?_L([\d-]+)(_rb)?'
        r'_b(\d+)_(D\d+)'
        r'_LR([\de\-]+)_LRF(\w+)_LRP(\d+)(?:_WD[\de\-]+)?'
        r'_ep(\d+)_(\d{4})_(\d{6})',
        stem
    )
    if m:
        (n_samp, n_feat, pc_tag, layers_str, rb_tag,
         batch, do_str, lr_str, lrf_tag, lrp, epochs,
         date_s, time_s) = m.groups()
        info['n_samples']    = f'{int(n_samp):,}'
        info['n_features']   = n_feat
        info['feature_mode'] = 'PC (PC-ADC 재계산)' if pc_tag else 'ESP32 (하드웨어 FFT)'
        info['hidden_layers']= layers_str.replace('-', ' -> ')
        info['scaler_type']  = 'RobustScaler' if rb_tag else 'StandardScaler'
        info['batch_size']   = batch
        do_int = int(do_str[1:])
        info['dropout']      = f'0.{do_int}'
        info['lr']           = lr_str
        # LRF: '5' -> 0.5, '1' -> 0.1, '25' -> 0.25
        if len(lrf_tag) <= 2:
            lrf_val = float('0.' + lrf_tag)
        else:
            lrf_val = float(lrf_tag) / (10 ** len(lrf_tag))
        info['lr_factor']    = f'{lrf_val:.2f}'
        info['lr_patience']  = lrp
        info['epochs']       = epochs
        info['train_date']   = f'{date_s[:2]}월 {date_s[2:]}일  {time_s[:2]}:{time_s[2:4]}:{time_s[4:]}'
    # ---- 로그 파일 파싱 ----
    if os.path.exists(log_path):
        best_val, best_ep, final_val, feat_list = 0.0, 0, None, ''
        with open(log_path, encoding='utf-8') as lf:
            for line in lf:
                ep_m = re.search(r'에폭\s+(\d+)/\d+.*?검증:\s*([\d.]+)%', line)
                if ep_m:
                    ep_num  = int(ep_m.group(1))
                    val_acc = float(ep_m.group(2))
                    if val_acc > best_val:
                        best_val, best_ep = val_acc, ep_num
                    final_val = val_acc
                feat_m = re.search(r'사용 특징 \(\d+개\):\s*(.+)', line)
                if feat_m:
                    feat_list = feat_m.group(1).strip()
        info['best_val_acc']  = f'{best_val:.1f}%'
        info['best_epoch']    = str(best_ep)
        info['final_val_acc'] = f'{final_val:.1f}%' if final_val is not None else '(없음)'
        info['feature_list']  = feat_list
    return info

# -- 모델 목록 탐색 + 사용자 선택 -------------------------------------------
def _list_models():
    d           = os.path.join(AI_DIR, 'models')
    fallback_sc = os.path.join(d, 'mlp_scaler.pkl')
    # 서브디렉토리 구조 models/{stem}/{stem}.pt 와 flat models/*.pt 모두 탐색
    pts = sorted(
        [p for p in glob.glob(os.path.join(d, '**', '*.pt'), recursive=True)
         if not os.path.basename(p).startswith('mlp_weights')],
        reverse=True
    )
    result = []
    for p in pts:
        sc = p.replace('.pt', '_scaler.pkl')
        if not os.path.exists(sc):
            sc = fallback_sc
        result.append((p, sc))
    return result

def _select_model(tag='int8'):
    candidates = _list_models()
    if not candidates:
        print(f'[{tag}] models/ 폴더에 .pt 파일이 없습니다.')
        print(f'[{tag}] 먼저 python AI/mlp/nn_mlp.py 로 학습하세요.')
        sys.exit(1)
    fallback_sc = os.path.join(AI_DIR, 'models', 'mlp_scaler.pkl')
    print(f'\n[{tag}] export할 모델을 선택하세요:')
    for i, (pt, sc) in enumerate(candidates):
        sc_tag = 'scaler:OK' if sc != fallback_sc else 'scaler:(fallback)'
        print(f'  [{i}] {os.path.basename(pt)}  ({sc_tag})')
    print(f'  [Enter] 자동 선택: {os.path.basename(candidates[0][0])}')
    try:
        sel = input('선택 번호: ').strip()
        if sel == '':
            return candidates[0]
        elif sel.isdigit() and int(sel) < len(candidates):
            return candidates[int(sel)]
        else:
            print(f'[{tag}] 잘못된 입력 -- 첫 번째 파일 사용.')
            return candidates[0]
    except (EOFError, KeyboardInterrupt):
        return candidates[0]

mp, sp = _select_model('int8')
print('[int8] 선택된 모델:', os.path.basename(mp))
_minfo = _parse_model_info(mp, AI_DIR)

model_sd    = torch.load(mp, map_location='cpu', weights_only=True)
input_size  = model_sd['net.0.weight'].shape[1]  # 체크포인트에서 입력 크기 자동 추출

# ── 체크포인트에서 hidden_layers 자동 추론 ──────────────────────
# Linear 가중치(2D)만 추려 정렬 후 마지막(출력층) 제외
_lin_keys = sorted(
    [k for k, v in model_sd.items() if k.endswith('.weight') and v.dim() == 2],
    key=lambda k: int(k.split('.')[1])
)
hidden_layers = [model_sd[k].shape[0] for k in _lin_keys[:-1]]  # 출력층 제외

model = nn_mlp.OccupancyMLP.__new__(nn_mlp.OccupancyMLP)
nn_mlp.OccupancyMLP.__init__(model, input_size, hidden_layers=hidden_layers)
model.load_state_dict(model_sd)
model.eval()
with open(sp, 'rb') as f:
    scaler = pickle.load(f)

print(f"[int8] 모델 로드 → {os.path.basename(mp)}")
print(f"[int8] 추론된 구조: input={input_size}  hidden_layers={hidden_layers}")

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
    # fallback: 프로젝트 루트/data_csv/ 에서 CSV 목록 제시 후 선택
    _PROJ_ROOT  = os.path.dirname(ROOT_DIR)  # AI/ 의 부모 = 프로젝트 루트
    _candidates = sorted(glob.glob(os.path.join(_PROJ_ROOT, 'data_csv', '*.csv')))
    if not _candidates:
        print(f"[int8] 캘리브레이션 데이터 없음 → {val_csv}")
        print("       data_csv/ 폴더에 CSV가 없습니다. 데이터를 먼저 수집하세요.")
        sys.exit(1)
    print("\n[int8] data_val.csv 없음 — 캘리브레이션에 사용할 CSV를 선택하세요:")
    for i, p in enumerate(_candidates):
        print(f"  [{i}] {os.path.basename(p)}")
    print(f"  [Enter] 최신 파일 자동 선택 ({os.path.basename(_candidates[-1])})")
    try:
        _sel = input("선택 번호: ").strip()
        if _sel == '':
            val_csv = _candidates[-1]
        elif _sel.isdigit() and int(_sel) < len(_candidates):
            val_csv = _candidates[int(_sel)]
        else:
            print("[int8] 잘못된 입력 — 최신 파일로 대체합니다.")
            val_csv = _candidates[-1]
    except (EOFError, KeyboardInterrupt):
        val_csv = _candidates[-1]
    print(f"[int8] 캘리브레이션 파일: {os.path.basename(val_csv)}")

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
        # 99 백분위수 클리핑 — 이상치 1개가 scale을 늘려 정밀도 낭비하는 것 방지
        in_maxs.append(float(np.percentile(np.abs(cur), 99)))
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
_now      = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
_mp_rel   = os.path.relpath(mp,  ROOT_DIR)   # AI/ 기준 상대경로
_sp_rel   = os.path.relpath(sp,  ROOT_DIR)
_cal_rel  = os.path.relpath(val_csv, os.path.dirname(ROOT_DIR))
_n_params = sum(lq['W_q'].size + lq['b_q'].size for lq in layers_q)
_mem_w    = sum(lq['W_q'].size     for lq in layers_q)          # bytes (int8)
_mem_b    = sum(lq['b_q'].size * 4 for lq in layers_q)          # bytes (int32)
_mem_sc   = len(scaler.mean_) * 2 * 4                           # bytes (float32)
_mem_tot  = _mem_w + _mem_b + _mem_sc

def _layer_desc(i, lq):
    if i == 0:   return f'{SIZES[i]:4d}  (Linear\u2192BN\u2192ReLU\u2192Dropout, BN \uc735\ud569)'
    elif lq['relu']: return f'{SIZES[i]:4d}  (Linear\u2192ReLU)'
    else:            return f'{SIZES[i]:4d}  (Linear, \ucd9c\ub825\uce35)'

H = []
H.append(' /**\n')
H.append('  * mlp_int8.h  —  MLP int8 \uc591\uc790\ud654 \ucd94\ub860  (ESP32-C3 \ubc30\ud3ec\uc6a9)\n')
H.append('  * \u2550' * 55 + '\n')
H.append(f'  * \uc0dd\uc131 \uc77c\uc2dc : {_now}\n')
H.append('  *\n')
H.append('  * [\ubaa8\ub378 \ud30c\uc77c]\n')
H.append(f'  *   \ud30c\uc77c\uba85   : {os.path.basename(mp)}\n')
H.append(f'  *   \uacbd\ub85c     : {_mp_rel}\n')
H.append(f'  *   Scaler   : {_sp_rel}\n')
H.append('  *\n')
H.append('  * [학습 정보]\n')
H.append(f'  *   샘플 수        : {_minfo["n_samples"]}개\n')
H.append(f'  *   특징 수 / 모드  : {_minfo["n_features"]}개  ({_minfo["feature_mode"]})\n')
H.append(f'  *   배치 크기      : {_minfo["batch_size"]}\n')
H.append(f'  *   Dropout        : {_minfo["dropout"]}\n')
H.append(f'  *   Learning Rate  : {_minfo["lr"]}\n')
H.append(f'  *   LR 감소        : factor={_minfo["lr_factor"]}  patience={_minfo["lr_patience"]} epoch\n')
H.append(f'  *   총 에폭        : {_minfo["epochs"]}\n')
H.append(f'  *   최고 검증 정확도: {_minfo["best_val_acc"]}  (에폭 {_minfo["best_epoch"]})\n')
H.append(f'  *   최종 검증 정확도: {_minfo["final_val_acc"]}\n')
H.append(f'  *   학습 일시      : {_minfo["train_date"]}\n')
if _minfo['feature_list']:
    _feats = _minfo['feature_list'].split(', ')
    _line_parts, _line_len = [], 0
    for _ft in _feats:
        if _line_len + len(_ft) + 2 > 68 and _line_parts:
            H.append(f'  *     {", ".join(_line_parts)},\n')
            _line_parts, _line_len = [_ft], len(_ft)
        else:
            _line_parts.append(_ft)
            _line_len += len(_ft) + 2
    if _line_parts:
        H.append(f'  *     {", ".join(_line_parts)}\n')
H.append('  *\n')
H.append('  * [\uc2e0\uacbd\ub9dd \uad6c\uc870]\n')
H.append(f'  *   \uc785\ub825\uce35     :  {INPUT_SIZE:3d}  (StandardScaler \uc815\uaddc\ud654)\n')
for i, lq in enumerate(layers_q):
    H.append(f'  *   \uc740\ub2c9\uce35 {i+1}    : {_layer_desc(i, lq)}\n')
H.append(f'  *   \ucd9c\ub825\uce35     :    2  (Background=0 / Human=1)\n')
H.append(f'  *   \ucd1d \ud30c\ub77c\ubbf8\ud130 : {_n_params:,}\uac1c\n')
H.append('  *\n')
H.append('  * [\uc591\uc790\ud654 \uc815\ubcf4]\n')
H.append('  *   \ubc29\uc2dd     : Symmetric Per-Tensor PTQ int8\n')
H.append(f'  *   float32 \uc815\ud655\ub3c4 : {acc_f:.1%}\n')
H.append(f'  *   int8 \uc815\ud655\ub3c4    : {acc_q:.1%}  (\ucc28\uc774: {(acc_q-acc_f)*100:+.2f}%p)\n')
H.append(f'  *   \uce98\ub9ac\ube0c\ub808\uc774\uc158 : {os.path.basename(val_csv)} ({len(X_cal):,} \uc0d8\ud50c)\n')
H.append('  *\n')
H.append('  * [\uba54\ubaa8\ub9ac \uc0ac\uc6a9\ub7c9 (\ucf54\ub4dc \ud50c\ub798\uc2dc \uae30\uc900)]\n')
H.append(f'  *   \uac00\uc911\uce58 (int8)  : {_mem_w:,} B = {_mem_w/1024:.1f} KB\n')
H.append(f'  *   \ud3b8\ud5a5 (int32)  : {_mem_b:,} B = {_mem_b/1024:.1f} KB\n')
H.append(f'  *   Scaler (f32)  : {_mem_sc:,} B = {_mem_sc/1024:.1f} KB\n')
H.append(f'  *   \ud569\uacc4          : {_mem_tot:,} B = {_mem_tot/1024:.1f} KB\n')
H.append('  *\n')
H.append('  * [\uc0ac\uc6a9\ubc95 (ESP-IDF)]\n')
H.append('  *   #include "mlp_int8.h"\n')
H.append('  *   float prob; int label = mlp_int8_infer(features, &prob);\n')
H.append('  */\n\n')
H.append('#pragma once\n')
H.append('#include <math.h>\n')
H.append('#include <stdint.h>\n\n')
H.append(f'#define MLP_INT8_INPUT_SIZE {INPUT_SIZE}\n\n')

H.append('/* ── StandardScaler 정규화 파라미터 ─────────────────────── */\n')
H.append(_c_float_arr(np.array(scaler.mean_),  'MLP_INT8_SCALER_MEAN'))
H.append(_c_float_arr(np.array(scaler.scale_), 'MLP_INT8_SCALER_STD'))

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
C.append('        x[i] = (raw_input[i] - MLP_INT8_SCALER_MEAN[i]) / MLP_INT8_SCALER_STD[i];\n\n')

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
    with open(path, 'w', encoding='utf-8') as f:
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
