"""
╔══════════════════════════════════════════════════════════════════╗
║  CSV 데이터 병합 및 학습/검증 분리 스크립트                      ║
╚══════════════════════════════════════════════════════════════════╝

[ 기능 ]
  상위 폴더의 svm_data*.csv 파일을 모두 읽어 병합한 뒤,
  학습용(80%) / 검증용(20%) 으로 나눠 AI/ 폴더에 저장합니다.

[ 사용법 ]
  python AI/prepare_data.py

[ 출력 파일 ]
  AI/data_merged.csv  — 전체 병합 데이터
  AI/data_train.csv   — 학습용 (80%)
  AI/data_val.csv     — 검증용 (20%)

[ CSV 컬럼 순서 (표준 포맷) ]
  magnitudes_0 ~ magnitudes_150 (151개)
  peak_freq, peak_mag, avg_mag, std_mag, centroid,
  low_energy, mid_energy, high_energy, rms,
  low_ratio, spectral_entropy, peak_to_mean  (12개)
  label  (0=배경, 1=사람)
"""

import os
import glob
import pandas as pd
from sklearn.model_selection import train_test_split

# ── 표준 컬럼 정의 ────────────────────────────────────────────────
MAG_COLS  = [f'magnitudes_{i}' for i in range(151)]
STAT_COLS = [
    'peak_freq', 'peak_mag', 'avg_mag', 'std_mag', 'centroid',
    'low_energy', 'mid_energy', 'high_energy', 'rms',
    'low_ratio', 'spectral_entropy', 'peak_to_mean',
]
LABEL_COL    = 'label'
FEATURE_COLS = MAG_COLS + STAT_COLS          # 163개
ALL_COLS     = FEATURE_COLS + [LABEL_COL]    # 164개

VAL_RATIO   = 0.2
RANDOM_SEED = 42

# ── 경로 설정 ─────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)

OUTPUT_MERGED = os.path.join(SCRIPT_DIR, 'data_merged.csv')
OUTPUT_TRAIN  = os.path.join(SCRIPT_DIR, 'data_train.csv')
OUTPUT_VAL    = os.path.join(SCRIPT_DIR, 'data_val.csv')


def load_csv_safe(path: str) -> pd.DataFrame:
    """
    CSV 파일을 읽고 표준 164컬럼 포맷으로 정규화.

    - label 컬럼 없는 파일 → None 반환 (스킵)
    - 누락된 통계 컬럼      → 0으로 채움
    - 컬럼 순서             → 표준 순서로 재정렬
    """
    try:
        df = pd.read_csv(path)
    except Exception as e:
        print(f"  ⚠️  읽기 실패: {path} — {e}")
        return None

    # label 없으면 스킵
    if LABEL_COL not in df.columns:
        print(f"  ⏭️  label 컬럼 없음, 스킵: {os.path.basename(path)}")
        return None

    # 누락된 feature 컬럼 → 0으로 채움 (한 번에 concat)
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        preview = missing[:5]
        suffix  = f'... 외 {len(missing)-5}개' if len(missing) > 5 else ''
        print(f"  ⚠️  누락 컬럼 {len(missing)}개 → 0 채움: {preview}{suffix}")
        zero_df = pd.DataFrame(0.0, index=df.index, columns=missing)
        df = pd.concat([df, zero_df], axis=1)

    # 표준 컬럼 순서로 재배열 + label 정수화
    df = df[ALL_COLS].copy()
    df[LABEL_COL] = df[LABEL_COL].astype(int)
    return df


def main():
    # ── CSV 목록 탐색 ─────────────────────────────────────────────
    pattern = os.path.join(PARENT_DIR, 'svm_data*.csv')
    paths   = sorted(glob.glob(pattern))

    if not paths:
        print(f"❌ CSV 파일 없음: {pattern}")
        return

    print(f"발견된 CSV 파일: {len(paths)}개\n")

    # ── 각 파일 로드 ──────────────────────────────────────────────
    frames = []
    for p in paths:
        name = os.path.basename(p)
        df   = load_csv_safe(p)
        if df is None:
            continue
        n_bg    = int((df[LABEL_COL] == 0).sum())
        n_human = int((df[LABEL_COL] == 1).sum())
        print(f"  ✅ {name:35s} 총 {len(df):4d}행  (BG: {n_bg:3d}, Human: {n_human:3d})")
        frames.append(df)

    if not frames:
        print("\n❌ 사용 가능한 데이터 없음")
        return

    # ── 병합 + 중복 제거 ──────────────────────────────────────────
    merged  = pd.concat(frames, ignore_index=True)
    before  = len(merged)
    merged  = merged.drop_duplicates().reset_index(drop=True)
    removed = before - len(merged)

    n_total = len(merged)
    n_bg    = int((merged[LABEL_COL] == 0).sum())
    n_human = int((merged[LABEL_COL] == 1).sum())

    print(f"\n병합 결과: 총 {n_total}행  (BG: {n_bg}, Human: {n_human})")
    if removed:
        print(f"  → 중복 {removed}행 제거됨")

    # ── data_merged.csv 저장 ──────────────────────────────────────
    merged.to_csv(OUTPUT_MERGED, index=False)
    print(f"\n💾 병합 파일 저장: {OUTPUT_MERGED}")

    # ── train / val 분리 ──────────────────────────────────────────
    if n_total < 10 or len(merged[LABEL_COL].unique()) < 2:
        print("⚠️  데이터 부족 또는 클래스 불균형 — train/val 분리 불가")
        return

    train_df, val_df = train_test_split(
        merged,
        test_size=VAL_RATIO,
        random_state=RANDOM_SEED,
        stratify=merged[LABEL_COL],   # 클래스 비율 유지
    )

    train_df.to_csv(OUTPUT_TRAIN, index=False)
    val_df.to_csv(OUTPUT_VAL,     index=False)

    n_tr_bg    = int((train_df[LABEL_COL] == 0).sum())
    n_tr_human = int((train_df[LABEL_COL] == 1).sum())
    n_vl_bg    = int((val_df[LABEL_COL] == 0).sum())
    n_vl_human = int((val_df[LABEL_COL] == 1).sum())

    print(f"💾 학습용 저장: {OUTPUT_TRAIN}  ({len(train_df)}행 | BG: {n_tr_bg}, Human: {n_tr_human})")
    print(f"💾 검증용 저장: {OUTPUT_VAL}  ({len(val_df)}행 | BG: {n_vl_bg}, Human: {n_vl_human})")
    print("\n✅ 데이터 준비 완료!")


if __name__ == '__main__':
    main()
