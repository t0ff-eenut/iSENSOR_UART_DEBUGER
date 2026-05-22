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

def _select_model(tag='float32'):
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

mp, sp = _select_model('float32')
print('[float32] 선택된 모델:', os.path.basename(mp))
_minfo = _parse_model_info(mp, AI_DIR)

model_sd    = torch.load(mp, map_location='cpu', weights_only=True)
input_size  = model_sd['net.0.weight'].shape[1]  # 체크포인트에서 입력 크기 자동 추출

# ── 체크포인트에서 hidden_layers 자동 추론 ──────────────────────
_lin_keys = sorted(
    [k for k, v in model_sd.items() if k.endswith('.weight') and v.dim() == 2],
    key=lambda k: int(k.split('.')[1])
)
hidden_layers = [model_sd[k].shape[0] for k in _lin_keys[:-1]]  # 출력층 제외

model       = nn_mlp.OccupancyMLP.__new__(nn_mlp.OccupancyMLP)
nn_mlp.OccupancyMLP.__init__(model, input_size, hidden_layers=hidden_layers)
model.load_state_dict(model_sd)
model.eval()
with open(sp, 'rb') as f:
    scaler = pickle.load(f)

print(f"[float32] 모델 로드 → {os.path.basename(mp)}")
print(f"[float32] 추론된 구조: input={input_size}  hidden_layers={hidden_layers}")

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
_now      = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
_mp_rel   = os.path.relpath(mp, ROOT_DIR)
_sp_rel   = os.path.relpath(sp, ROOT_DIR)
_n_params = sum(l['W'].size + l['b'].size for l in layers)
_mem_wb   = sum((l['W'].size + l['b'].size) * 4 for l in layers)  # bytes (float32)
_mem_sc   = len(scaler.mean_) * 2 * 4
_mem_tot  = _mem_wb + _mem_sc

def _layer_desc(i, l):
    if i == 0:       return f'{SIZES[i]:4d}  (Linear\u2192BN\u2192ReLU\u2192Dropout, BN \uc735\ud569)'
    elif l['relu']:  return f'{SIZES[i]:4d}  (Linear\u2192ReLU)'
    else:            return f'{SIZES[i]:4d}  (Linear, \ucd9c\ub825\uce35)'

H = []
H.append(' /**\n')
H.append('  * mlp_float32.h  —  MLP float32 \ucd94\ub860  (ESP32-C3 \ubc30\ud3ec\uc6a9)\n')
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
for i, l in enumerate(layers):
    H.append(f'  *   \uc740\ub2c9\uce35 {i+1}    : {_layer_desc(i, l)}\n')
H.append(f'  *   \ucd9c\ub825\uce35     :    2  (Background=0 / Human=1)\n')
H.append(f'  *   \ucd1d \ud30c\ub77c\ubbf8\ud130 : {_n_params:,}\uac1c\n')
H.append('  *\n')
H.append('  * [\uba54\ubaa8\ub9ac \uc0ac\uc6a9\ub7c9 (\ucf54\ub4dc \ud50c\ub798\uc2dc \uae30\uc900)]\n')
H.append(f'  *   \uac00\uc911\uce58+\ud3b8\ud5a5 (f32) : {_mem_wb:,} B = {_mem_wb/1024:.1f} KB\n')
H.append(f'  *   Scaler (f32)     : {_mem_sc:,} B = {_mem_sc/1024:.1f} KB\n')
H.append(f'  *   \ud569\uacc4             : {_mem_tot:,} B = {_mem_tot/1024:.1f} KB\n')
H.append('  *\n')
H.append('  * [\uc0ac\uc6a9\ubc95 (ESP-IDF)]\n')
H.append('  *   #include "mlp_float32.h"\n')
H.append('  *   float prob; int label = mlp_float32_infer(features, &prob);\n')
H.append('  */\n\n')
H.append('#pragma once\n')
H.append('#include <math.h>\n')
H.append('#include <stdint.h>\n\n')
H.append(f'#define MLP_F32_INPUT_SIZE {INPUT_SIZE}  /* 입력 특징 수 (FFT 선택 특징) */\n\n')

H.append('/* ── StandardScaler 정규화 파라미터 ─────────────────────── */\n')
H.append(_c_float_arr(np.array(scaler.mean_),  'MLP_F32_SCALER_MEAN'))
H.append(_c_float_arr(np.array(scaler.scale_), 'MLP_F32_SCALER_STD'))

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
C.append('        x[i] = (raw_input[i] - MLP_F32_SCALER_MEAN[i]) / MLP_F32_SCALER_STD[i];\n\n')

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
    with open(path, 'w', encoding='utf-8') as f:
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
