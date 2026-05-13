"""
╔══════════════════════════════════════════════════════════════════╗
║  PC 특징 추출기 (구버전 호환)                                    ║
╚══════════════════════════════════════════════════════════════════╝

현재 CSV에는 ESP32가 계산한 21개 특징 + ADC 256개 + FFT 129개 빈이 저장되어 있습니다.
이 모듈은 fft_0~128 컬럼으로부터 구버전(PC 계산) 25개 특징을 재계산합니다.

[ 구버전 25개 특징 ]
  · magnitudes_1~15  : fft_1~fft_15 직접 사용 (저주파~5Hz 영역)
  · peak_freq        : 최대 진폭 빈 인덱스 (argmax)
  · peak_mag         : 최대 진폭 값 (max)
  · std_mag          : 전체 FFT 진폭 표준편차
  · centroid         : 스펙트럼 무게중심 = Σ(i × fft_i) / Σfft_i
  · low_energy       : 저주파 에너지 = sum(fft_0~4)
  · mid_energy       : 중간 주파수 에너지 = sum(fft_5~15)
  · rms              : 실효값 = √mean(fft²)
  · low_ratio        : 저주파 비율 = low_energy / total_energy
  · spectral_entropy : 스펙트럼 엔트로피 = -Σ(p·log₂(p))
  · peak_to_mean     : 피크/평균 비율 = peak_mag / mean(fft)

[ CSV 컬럼 인덱스 ]
  fft_0 = col CSV_COL_FFT_START  (csv_layout.py 에서 정의 — 기본값 277)
  label = 항상 마지막 열
"""

import numpy as np
import os as _os
import sys as _sys

# csv_layout.py는 AI/ 에 위치 (이 파일은 AI/mlp/ 에 있음)
_MLP_DIR = _os.path.dirname(_os.path.abspath(__file__))
_AI_DIR  = _os.path.dirname(_MLP_DIR)
if _AI_DIR not in _sys.path:
    _sys.path.insert(0, _AI_DIR)
import csv_layout

# ──────────────────────────────────────────────────────────────
#  CSV 컨럼 레이아웃 상수  — csv_layout.py 에서 로드
#  여기 이름을 유지해야 다른 모듈(nn_mlp.py)이 from pc_feature_extractor import FFT_START_COL으로
#  가져가는 것이 계속 동작함
# ──────────────────────────────────────────────────────────────
FFT_START_COL = csv_layout.CSV_COL_FFT_START   # 277  (특징 21 + ADC 256)
FFT_N_BINS    = csv_layout.CSV_N_FFT            # 129  (fft_0 ~ fft_128)
ADC_START_COL = csv_layout.CSV_COL_ADC_START   # 21   (특징 21개 이후)
ADC_N_SAMPLES = csv_layout.CSV_N_ADC           # 256  (adc_0 ~ adc_255)

# 특징 이름 목록 (순서 고정)
PC_FEATURE_NAMES = (
    [f'magnitudes_{i}' for i in range(1, 16)]   # 15개
    + ['peak_freq', 'peak_mag', 'std_mag',
       'centroid', 'low_energy', 'mid_energy',
       'rms', 'low_ratio', 'spectral_entropy', 'peak_to_mean']  # 10개
)  # 총 25개


# ──────────────────────────────────────────────────────────────
#  내부 헬퍼: FFT magnitude 배열 → 25개 특징 (단일/배치 공통 로직)
# ──────────────────────────────────────────────────────────────

def _extract_features_from_fft_arr(fft: np.ndarray) -> np.ndarray:
    """FFT magnitude 배열(shape: FFT_N_BINS,) → 25개 특징 벡터 (shape: 25,)."""
    fft = fft.astype(np.float64)
    total_energy = np.sum(fft) + 1e-12
    magnitudes   = fft[1:16]
    peak_idx     = int(np.argmax(fft))
    peak_mag     = float(fft[peak_idx])
    std_mag      = float(np.std(fft))
    indices      = np.arange(len(fft), dtype=np.float64)
    centroid     = float(np.sum(indices * fft) / total_energy)
    low_energy   = float(np.sum(fft[0:5]))
    mid_energy   = float(np.sum(fft[5:16]))
    rms          = float(np.sqrt(np.mean(fft ** 2)))
    low_ratio    = float(low_energy / total_energy)
    p            = np.clip(fft / total_energy, 1e-12, None)
    spectral_entropy = float(-np.sum(p * np.log2(p)))
    mean_mag     = float(np.mean(fft)) + 1e-12
    peak_to_mean = peak_mag / mean_mag
    return np.array(
        list(magnitudes)
        + [peak_idx, peak_mag, std_mag,
           centroid, low_energy, mid_energy,
           rms, low_ratio, spectral_entropy, peak_to_mean],
        dtype=np.float32,
    )


def _extract_features_batch(fft: np.ndarray) -> np.ndarray:
    """FFT magnitude 배열 (shape: N × FFT_N_BINS) → 25개 특징 행렬 (shape: N × 25)."""
    fft = fft.astype(np.float64)
    N   = fft.shape[0]
    total_energy = fft.sum(axis=1, keepdims=True) + 1e-12
    magnitudes   = fft[:, 1:16]
    peak_idx     = fft.argmax(axis=1).reshape(N, 1)
    peak_mag     = fft.max(axis=1).reshape(N, 1)
    std_mag      = fft.std(axis=1).reshape(N, 1)
    indices      = np.arange(fft.shape[1], dtype=np.float64)
    centroid     = (fft @ indices).reshape(N, 1) / total_energy
    low_energy   = fft[:, 0:5].sum(axis=1).reshape(N, 1)
    mid_energy   = fft[:, 5:16].sum(axis=1).reshape(N, 1)
    rms          = np.sqrt((fft ** 2).mean(axis=1)).reshape(N, 1)
    low_ratio    = low_energy / total_energy
    p            = np.clip(fft / total_energy, 1e-12, None)
    spectral_entropy = (-(p * np.log2(p)).sum(axis=1)).reshape(N, 1)
    mean_mag     = (fft.mean(axis=1) + 1e-12).reshape(N, 1)
    peak_to_mean = peak_mag / mean_mag
    result = np.concatenate(
        [magnitudes, peak_idx, peak_mag, std_mag,
         centroid, low_energy, mid_energy,
         rms, low_ratio, spectral_entropy, peak_to_mean],
        axis=1,
    )
    return result.astype(np.float32)


def extract_pc_features(row_full: np.ndarray) -> np.ndarray:
    """
    CSV 한 행(전체 406개 특징 컬럼)에서 PC 기반 25개 특징을 추출합니다.
    (FFT 빈 컬럼 277~405 사용 — 구버전 호환)

    Args:
        row_full : shape (406,) — label 제외한 전체 특징 벡터

    Returns:
        shape (25,) float32 특징 벡터
    """
    fft = row_full[FFT_START_COL: FFT_START_COL + FFT_N_BINS].astype(np.float64)
    return _extract_features_from_fft_arr(fft)


def extract_pc_features_batch(X_full: np.ndarray) -> np.ndarray:
    """
    여러 행에 대해 PC 특징을 일괄 추출합니다. (FFT 빈 컬럼 사용 — 구버전 호환)

    Args:
        X_full : shape (N, 406) — label 제외 전체 특징 행렬

    Returns:
        shape (N, 25) float32
    """
    fft = X_full[:, FFT_START_COL: FFT_START_COL + FFT_N_BINS]
    return _extract_features_batch(fft)


# ──────────────────────────────────────────────────────────────
#  ADC 기반 PC 특징 추출 (ADC → numpy FFT → 25개 특징)
#  · 학습 CSV: adc_0~255 컬럼(21~276) 에서 FFT 직접 계산
#  · 실시간 추론: A_adc_buffer 배열로 FFT 계산
# ──────────────────────────────────────────────────────────────

def _adc_to_fft_mags(adc: np.ndarray) -> np.ndarray:
    """ADC 샘플 배열 → DC 제거 → numpy FFT → magnitude (FFT_N_BINS개)."""
    adc = adc.astype(np.float64)
    adc -= adc.mean()  # DC 성분 제거
    n   = len(adc)
    fft_complex = np.fft.rfft(adc)
    mags        = np.abs(fft_complex) * 2.0 / n
    mags[0]    /= 2.0            # DC 빈은 단방향이므로 2배 보정 불필요
    # FFT_N_BINS(129) 길이에 맞춤
    if len(mags) < FFT_N_BINS:
        mags = np.concatenate([mags, np.zeros(FFT_N_BINS - len(mags))])
    return mags[:FFT_N_BINS]


def extract_pc_features_from_adc(row_full: np.ndarray) -> np.ndarray:
    """
    CSV 한 행의 ADC 컬럼(adc_0~255)에서 numpy FFT를 계산해 25개 특징을 추출합니다.
    (PC 모드 학습 데이터 준비용)

    Args:
        row_full : shape (406+,) — label 제외 전체 특징 벡터

    Returns:
        shape (25,) float32
    """
    adc  = row_full[ADC_START_COL: ADC_START_COL + ADC_N_SAMPLES]
    mags = _adc_to_fft_mags(adc)
    return _extract_features_from_fft_arr(mags)


def extract_pc_features_from_adc_batch(X_full: np.ndarray) -> np.ndarray:
    """
    여러 행의 ADC 컬럼(adc_0~255)에서 일괄 PC 특징을 추출합니다.
    (PC 모드 학습 CSV 전처리용)

    Args:
        X_full : shape (N, 406+) — label 제외 전체 특징 행렬

    Returns:
        shape (N, 25) float32
    """
    adc  = X_full[:, ADC_START_COL: ADC_START_COL + ADC_N_SAMPLES].astype(np.float64)
    adc -= adc.mean(axis=1, keepdims=True)          # DC 성분 제거
    fft_complex = np.fft.rfft(adc, axis=1)          # (N, 129)
    mags        = np.abs(fft_complex) * 2.0 / ADC_N_SAMPLES
    mags[:, 0] /= 2.0
    return _extract_features_batch(mags)


def compute_pc_features_realtime(A_adc) -> np.ndarray:
    """
    실시간 추론용: ADC 샘플 배열 → numpy FFT → 25개 PC 특징.
    (debugger_start.py 의 A_adc_buffer 를 직접 입력)

    Args:
        A_adc : array-like, 길이 ≥ 16 (권장: 256)

    Returns:
        shape (25,) float32
    """
    mags = _adc_to_fft_mags(np.asarray(A_adc))
    return _extract_features_from_fft_arr(mags)


# ──────────────────────────────────────────────────────────────
#  단독 실행 시 확인용
# ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    dummy = np.zeros(407, dtype=np.float32)
    dummy[FFT_START_COL + 3] = 1.0   # FFT 3번 빈에 피크
    feat = extract_pc_features(dummy)
    print(f"[FFT 빈 기반] 특징 수: {len(feat)}")
    for name, val in zip(PC_FEATURE_NAMES, feat):
        print(f"  {name:<22s} = {val:.4f}")

    # ADC 기반 테스트
    dummy_adc = np.zeros(407, dtype=np.float32)
    # ADC 컬럼에 단순 정현파 삽입
    t = np.arange(ADC_N_SAMPLES)
    dummy_adc[ADC_START_COL: ADC_START_COL + ADC_N_SAMPLES] = np.sin(2 * np.pi * 3 * t / ADC_N_SAMPLES).astype(np.float32)
    feat_adc = extract_pc_features_from_adc(dummy_adc)
    print(f"\n[ADC 기반] 특징 수: {len(feat_adc)}")
    for name, val in zip(PC_FEATURE_NAMES, feat_adc):
        print(f"  {name:<22s} = {val:.4f}")
