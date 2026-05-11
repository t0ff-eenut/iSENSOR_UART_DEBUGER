"""
MLP 로그/모델 파일명 통일 스크립트
구 형식 → 새 형식으로 일괄 이름 변경

DRY_RUN = True  → 미리보기만 (실제 변경 없음)
DRY_RUN = False → 실제 변경
"""

import os, re, math, json

DRY_RUN = True   # ← False로 바꾸면 실제 실행

LOGS_DIR     = os.path.join(os.path.dirname(__file__), 'logs')
MODELS_DIR   = os.path.join(os.path.dirname(__file__), 'models')


# ──────────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────────
def normalize_lr(lr_str: str) -> str:
    """lr 문자열을 표준 형식으로 정규화: '5e-04' → '5e-4', '1e-3' → '1e-3'"""
    try:
        val = float(lr_str)
        exp = int(math.floor(math.log10(val)))
        man = round(val / (10 ** exp), 1)
        man_s = str(int(man)) if man == int(man) else str(man)
        return f'{man_s}e{exp}'
    except Exception:
        return lr_str


def get_n_samples(log_path: str) -> int:
    """로그 파일에서 총 샘플 수 추출 (없으면 0)."""
    if not log_path or not os.path.exists(log_path):
        return 0
    try:
        with open(log_path, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        for pat in [
            r'로드 완료.*?전체[:\s]+(\d+)개',
            r'CSV.*?총\s+(\d+)개',
            r'병합.*?총\s+(\d+)개',
            r'총\s+(\d+)개',
            r'총\s+(\d+)샘플',
        ]:
            m = re.search(pat, content)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return 0


# ──────────────────────────────────────────────────────────────────
# 구버전 stem 파싱
# ──────────────────────────────────────────────────────────────────
def parse_stem(stem: str) -> dict | None:
    """
    구버전 stem을 파싱해 파라미터 dict 반환. 인식 불가 시 None.

    지원하는 형식:
      Style A (lrp/lrf 포함):
        mlp_L{layers}[_rb]_b{batch}_d{do}_ep{ep}_lr{lr}_lrp{lrp}_lrf{lrf}[_pc]_f{f}_{mmdd}_{HHMMSS}
      Style B (lrp/lrf 없음, 6자리 시간):
        mlp_L{layers}_ep{ep}_lr{lr}_d{do}_b{batch}_f{f}[_pc]_{mmdd}_{HHMMSS}
      Style B-4 (lrp/lrf 없음, 4자리 시간):
        mlp_L{layers}_ep{ep}_lr{lr}_d{do}_b{batch}_f{f}[_pc]_{mmdd}_{HHMM}
    """
    # ── Style A ───────────────────────────────────────────────────
    m = re.match(
        r'mlp_L([\d-]+?)(_rb)?_b(\d+)_(d\d+)_ep(\d+)_lr([\de.+-]+)_lrp(\d+)_lrf(\d+)(_pc)?_f(\d+)_(\d{4})_(\d{6})$',
        stem,
    )
    if m:
        layers, rb, batch, do, ep, lr, lrp, lrf, pc, f, date, time_ = m.groups()
        return dict(layers=layers, rb=bool(rb), batch=int(batch),
                    do=do, epochs=int(ep), lr=lr,
                    lrp=int(lrp), lrf=int(lrf), pc=bool(pc),
                    n_feat=int(f), date=date, time=time_)

    # ── Style B (6자리 시간) ──────────────────────────────────────
    m = re.match(
        r'mlp_L([\d-]+)_ep(\d+)_lr([\de.+-]+)_(d\d+)_b(\d+)_f(\d+)(_pc)?_(\d{4})_(\d{6})$',
        stem,
    )
    if m:
        layers, ep, lr, do, batch, f, pc, date, time_ = m.groups()
        return dict(layers=layers, rb=False, batch=int(batch),
                    do=do, epochs=int(ep), lr=lr,
                    lrp=None, lrf=None, pc=bool(pc),
                    n_feat=int(f), date=date, time=time_)

    # ── Style B-4 (4자리 시간) ────────────────────────────────────
    m = re.match(
        r'mlp_L([\d-]+)_ep(\d+)_lr([\de.+-]+)_(d\d+)_b(\d+)_f(\d+)(_pc)?_(\d{4})_(\d{4})$',
        stem,
    )
    if m:
        layers, ep, lr, do, batch, f, pc, date, time_ = m.groups()
        return dict(layers=layers, rb=False, batch=int(batch),
                    do=do, epochs=int(ep), lr=lr,
                    lrp=None, lrf=None, pc=bool(pc),
                    n_feat=int(f), date=date, time=time_ + '00')

    return None


# ──────────────────────────────────────────────────────────────────
# 새 stem 생성
# ──────────────────────────────────────────────────────────────────
def build_new_stem(p: dict, n_samples: int) -> str:
    rb   = '_rb' if p['rb'] else ''
    pc   = '_PC' if p['pc'] else ''
    do   = p['do'].upper()                   # d2 → D2, d3 → D3
    lr   = normalize_lr(p['lr'])
    lrf  = str(p['lrf']) if p['lrf'] is not None else '0'   # 없으면 0 (무스케줄러)
    lrp  = str(p['lrp']) if p['lrp'] is not None else '0'
    return (
        f"MLP_{n_samples}_F{p['n_feat']}{pc}"
        f"_L{p['layers']}{rb}"
        f"_b{p['batch']}_{do}"
        f"_LR{lr}_LRF{lrf}_LRP{lrp}"
        f"_ep{p['epochs']}_{p['date']}_{p['time']}"
    )


# ──────────────────────────────────────────────────────────────────
# 이름 변경 실행
# ──────────────────────────────────────────────────────────────────
def do_rename(src: str, dst: str):
    if src == dst:
        return
    if DRY_RUN:
        print(f"    {os.path.basename(src)}")
        print(f"  → {os.path.basename(dst)}")
    else:
        os.rename(src, dst)


# ──────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────
def main():
    mode = "DRY-RUN (미리보기)" if DRY_RUN else "실제 변경"
    print(f"\n{'='*70}")
    print(f"  MLP 파일명 통일 [{mode}]")
    print(f"{'='*70}\n")

    # stem 매핑 (log stem → new stem), 모델 폴더에서 재활용
    stem_map: dict[str, str] = {}

    # ── 1. 로그 파일 ─────────────────────────────────────────────
    print("[ 로그 파일 ]")
    print("-" * 70)
    log_changed = 0
    for fname in sorted(os.listdir(LOGS_DIR)):
        if not fname.endswith('.log'):
            continue
        stem = fname[:-4]
        p = parse_stem(stem)
        if p is None:
            print(f"  SKIP (파싱 불가): {fname}")
            continue

        n = get_n_samples(os.path.join(LOGS_DIR, fname))
        new_stem = build_new_stem(p, n)
        stem_map[stem] = new_stem
        new_fname = new_stem + '.log'

        if fname == new_fname:
            print(f"  SAME: {fname}")
            continue

        do_rename(os.path.join(LOGS_DIR, fname),
                  os.path.join(LOGS_DIR, new_fname))
        log_changed += 1
        print()

    print(f"\n  → 변경 대상 {log_changed}개\n")

    # ── 2. 모델 폴더 ─────────────────────────────────────────────
    print("[ 모델 폴더 ]")
    print("-" * 70)
    model_changed = 0
    for dname in sorted(os.listdir(MODELS_DIR)):
        dpath = os.path.join(MODELS_DIR, dname)
        if not os.path.isdir(dpath):
            continue

        p = parse_stem(dname)
        if p is None:
            print(f"  SKIP (파싱 불가): {dname}/")
            continue

        # 로그 파일에서 이미 n_samples를 구한 경우 재사용
        if dname in stem_map:
            new_stem = stem_map[dname]
        else:
            log_path = os.path.join(LOGS_DIR, dname + '.log')
            n = get_n_samples(log_path)
            new_stem = build_new_stem(p, n)

        if dname == new_stem:
            print(f"  SAME: {dname}/")
            continue

        # 폴더 내부 파일 rename (stem으로 시작하는 것만)
        for fname in sorted(os.listdir(dpath)):
            if fname.startswith(dname):
                suffix = fname[len(dname):]
                do_rename(os.path.join(dpath, fname),
                          os.path.join(dpath, new_stem + suffix))

        # 폴더 자체 rename
        print(f"    {dname}/")
        print(f"  → {new_stem}/")
        do_rename(dpath, os.path.join(MODELS_DIR, new_stem))
        model_changed += 1
        print()

    print(f"\n  → 변경 대상 {model_changed}개\n")
    print("=" * 70)
    if DRY_RUN:
        print("  ※ 실제 변경하려면 DRY_RUN = False 로 수정 후 재실행")
    else:
        print("  ✅ 완료")
    print("=" * 70)


if __name__ == '__main__':
    main()
