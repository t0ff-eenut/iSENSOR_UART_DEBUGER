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
  fft_0 = col 277, fft_128 = col 405
  label = col 406
"""

import numpy as np

# ──────────────────────────────────────────────────────────────
#  현재 CSV에서 FFT 빈의 시작 인덱스
# ──────────────────────────────────────────────────────────────
FFT_START_COL = 277   # CSV에서 fft_0 컬럼 인덱스
FFT_N_BINS    = 129   # fft_0 ~ fft_128

# 특징 이름 목록 (순서 고정)
PC_FEATURE_NAMES = (
    [f'magnitudes_{i}' for i in range(1, 16)]   # 15개
    + ['peak_freq', 'peak_mag', 'std_mag',
       'centroid', 'low_energy', 'mid_energy',
       'rms', 'low_ratio', 'spectral_entropy', 'peak_to_mean']  # 10개
)  # 총 25개


def extract_pc_features(row_full: np.ndarray) -> np.ndarray:
    """
    CSV 한 행(전체 406개 특징 컬럼)에서 PC 기반 25개 특징을 추출합니다.

    Args:
        row_full : shape (406,) — label 제외한 전체 특징 벡터

    Returns:
        shape (25,) float32 특징 벡터
    """
    fft = row_full[FFT_START_COL: FFT_START_COL + FFT_N_BINS].astype(np.float64)

    # 1~15번 빈 직접 사용
    magnitudes = fft[1:16]  # shape (15,)

    total_energy = np.sum(fft) + 1e-12  # 0 나누기 방지

    peak_idx = int(np.argmax(fft))
    peak_mag = float(fft[peak_idx])
    std_mag  = float(np.std(fft))

    # 스펙트럼 무게중심
    indices  = np.arange(FFT_N_BINS, dtype=np.float64)
    centroid = float(np.sum(indices * fft) / total_energy)

    # 에너지
    low_energy = float(np.sum(fft[0:5]))     # 빈 0~4
    mid_energy = float(np.sum(fft[5:16]))    # 빈 5~15

    # RMS
    rms = float(np.sqrt(np.mean(fft ** 2)))

    # 저주파 비율
    low_ratio = float(low_energy / total_energy)

    # 스펙트럼 엔트로피
    p = fft / total_energy
    p = np.clip(p, 1e-12, None)  # log(0) 방지
    spectral_entropy = float(-np.sum(p * np.log2(p)))

    # 피크/평균 비율
    mean_mag     = float(np.mean(fft)) + 1e-12
    peak_to_mean = peak_mag / mean_mag

    feat = np.array(
        list(magnitudes)
        + [peak_idx, peak_mag, std_mag,
           centroid, low_energy, mid_energy,
           rms, low_ratio, spectral_entropy, peak_to_mean],
        dtype=np.float32,
    )
    return feat  # shape (25,)


def extract_pc_features_batch(X_full: np.ndarray) -> np.ndarray:
    """
    여러 행에 대해 PC 특징을 일괄 추출합니다.

    Args:
        X_full : shape (N, 406) — label 제외 전체 특징 행렬

    Returns:
        shape (N, 25) float32
    """
    fft = X_full[:, FFT_START_COL: FFT_START_COL + FFT_N_BINS].astype(np.float64)
    N   = fft.shape[0]

    total_energy = fft.sum(axis=1, keepdims=True) + 1e-12

    magnitudes = fft[:, 1:16]                      # (N, 15)

    peak_idx = fft.argmax(axis=1).reshape(N, 1)    # (N, 1)
    peak_mag = fft.max(axis=1).reshape(N, 1)       # (N, 1)
    std_mag  = fft.std(axis=1).reshape(N, 1)       # (N, 1)

    indices  = np.arange(FFT_N_BINS, dtype=np.float64)
    centroid = (fft @ indices).reshape(N, 1) / total_energy  # (N, 1)

    low_energy  = fft[:, 0:5].sum(axis=1).reshape(N, 1)
    mid_energy  = fft[:, 5:16].sum(axis=1).reshape(N, 1)
    rms         = np.sqrt((fft ** 2).mean(axis=1)).reshape(N, 1)
    low_ratio   = low_energy / total_energy

    p = fft / total_energy
    p = np.clip(p, 1e-12, None)
    spectral_entropy = (-( p * np.log2(p)).sum(axis=1)).reshape(N, 1)

    mean_mag     = (fft.mean(axis=1) + 1e-12).reshape(N, 1)
    peak_to_mean = peak_mag / mean_mag

    result = np.concatenate(
        [magnitudes, peak_idx, peak_mag, std_mag,
         centroid, low_energy, mid_energy,
         rms, low_ratio, spectral_entropy, peak_to_mean],
        axis=1,
    )
    return result.astype(np.float32)   # (N, 25)


# ──────────────────────────────────────────────────────────────
#  단독 실행 시 확인용
# ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    dummy = np.zeros(406, dtype=np.float32)
    dummy[FFT_START_COL + 3] = 1.0   # 3번 빈에 피크
    feat = extract_pc_features(dummy)
    print(f"특징 수: {len(feat)}")
    for name, val in zip(PC_FEATURE_NAMES, feat):
        print(f"  {name:<22s} = {val:.4f}")
