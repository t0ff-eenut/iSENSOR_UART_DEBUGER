"""
CSV 컬럼 레이아웃 공용 상수  —  단일 진실의 원천(Single Source of Truth)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CSV 저장 구조 (training_data_collector.py 기준):

  has_meta=False:
  ┌──────────┬──────────┬──────────┬────────┐
  │feat 0~20 │adc 0~255 │fft 0~128 │ label  │
  │  21개    │  256개   │  129개   │   1개  │
  └──────────┴──────────┴──────────┴────────┘
  col:  0          21        277       406

  has_meta=True (stride/interval 컬럼 포함):
  ┌──────────┬──────────┬──────────┬──────────────┬────────┐
  │feat 0~20 │adc 0~255 │fft 0~128 │stride,interval│ label │
  │  21개    │  256개   │  129개   │    2개        │  1개  │
  └──────────┴──────────┴──────────┴──────────────┴────────┘
  col:  0          21        277         406,407      408

이 파일만 수정하면 관련 코드 전체에 반영됩니다.
──────────────────────────────────────────────────────────────────
사용 방법 (AI/ 내부 모듈):
    import csv_layout
    feat = row[:csv_layout.CSV_N_FEATURES]

사용 방법 (외부/서브패키지):
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))  # AI/ 추가
    import csv_layout
"""

# ── ESP32 UART 특징 (FftFeaturesData) ────────────────────────────
# svm.feature_vector_from_uart() 반환 차원  ← 바꾸면 ESP32 펌웨어도 같이 바꿔야 함
CSV_N_FEATURES  = 21

# ── 원시 데이터 배열 ─────────────────────────────────────────────
CSV_N_ADC       = 256   # adc_0 ~ adc_255
CSV_N_FFT       = 129   # fft_0 ~ fft_128

# ── 메타 컬럼 ────────────────────────────────────────────────────
CSV_N_META      = 2     # stride, interval  (has_meta=True 일 때만 존재)

# ── 컬럼 시작 인덱스 (has_meta=False 기준) ───────────────────────
CSV_COL_FEAT_START = 0
CSV_COL_ADC_START  = CSV_N_FEATURES                            # 21
CSV_COL_FFT_START  = CSV_N_FEATURES + CSV_N_ADC                # 277
CSV_COL_META_START = CSV_N_FEATURES + CSV_N_ADC + CSV_N_FFT   # 406  (stride 위치)
# label 은 항상 마지막 열:
#   has_meta=False  →  col 406
#   has_meta=True   →  col 408
