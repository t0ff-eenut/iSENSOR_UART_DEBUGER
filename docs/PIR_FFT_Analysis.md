# PIR 센서 출력 신호의 FFT 분석 가능 여부 검토

> **작성일**: 2025-12-22  
> **목적**: PIR 센서 앰프 출력(델타 신호)에 FFT 분석 적용의 의미와 근거 정리

---

## 📌 배경

PIR(Passive Infrared) 센서의 앰프 출력은 **적외선 변화량(델타 값)**을 나타내는 AC 신호입니다.  
이러한 델타 신호에 FFT(Fast Fourier Transform)를 적용하는 것이 의미가 있는지 검토합니다.

---

## 🔬 PIR 센서 출력 특성

### 1. AC(델타) 신호 생성 원리

| 특성 | 설명 |
|---|---|
| **AC 장치** | PIR 센서는 **적외선의 "변화"**만 감지합니다. 정적인 IR은 감지하지 않습니다. |
| **차분 구조** | 2개의 반대 극성 감지 소자가 있어, 주변 온도 변화는 상쇄되고 **움직임만 검출**됩니다. |
| **출력 전압** | 원시 출력은 ~1mVpp 수준으로 매우 작으며, 내장 Amp가 증폭합니다. |
| **시간 미분** | 출력 전압은 **적외선 변화율에 비례** → 빠른 움직임 = 빠른 전압 변화 |

### 2. 수학적 표현

```
V_out(t) ∝ dI/dt

여기서:
  V_out: PIR 센서 출력 전압
  I: 적외선 에너지
  dI/dt: 적외선 변화율 (미분)
```

---

## 📊 PIR 신호의 주파수 특성

다양한 출처에서 확인된 PIR 센서 신호의 주파수 범위:

| 출처 | 주파수 범위 | 비고 |
|---|---|---|
| AllAboutCircuits | **0.5 Hz ~ 5 Hz** | 일반적인 인체 움직임 |
| Texas Instruments | **0.7 Hz ~ 30 Hz** | 빠른 움직임 포함 |
| InfraTec | **1 Hz ~ 10 Hz** | 일반적인 동작 범위 |
| 연구 논문 | **0.1 Hz ~ 10 Hz** | 1/f 노이즈 특성 고려 |

### 주파수 응답 결정 요인

1. **열 시간 상수 (Thermal Time Constant)**: 하한 주파수 결정
2. **전기적 시간 상수 (Electrical Time Constant)**: 상한 주파수 결정
3. **앰프 필터링**: 고역통과(HPF) + 저역통과(LPF) = 대역통과 특성

---

## ✅ FFT 분석이 의미 있는 이유

### 1. 델타 신호의 FFT 특성

```
미분 신호의 FFT = 원 신호의 FFT × (j × 2π × f)
```

| 특성 | 설명 |
|---|---|
| **저주파 약화** | 0Hz(DC) 성분은 미분 시 0이 됨 |
| **고주파 강조** | 주파수가 높을수록 증폭됨 |
| **속도 정보 강조** | 빠른 움직임의 주파수 성분이 더 잘 보임 |

**결론**: 미분된 신호의 FFT는 **움직임의 속도 정보**를 명확히 나타냅니다!

### 2. FFT로 얻을 수 있는 정보

| 분석 항목 | 의미 | 활용 |
|---|---|---|
| **지배 주파수 피크** | 움직임의 주된 속도 | 걷기/뛰기 구분 |
| **스펙트럼 분포** | 움직임 패턴 | 사람/동물 구분 |
| **노이즈 주파수** | 전원 노이즈(50/60Hz) | 노이즈 필터 설계 |
| **필터 효과 검증** | HPF/BPF 차단 주파수 | 필터 튜닝 |

### 3. 실제 연구/산업 사례

- **사람 vs 동물 구분**: 걸음 주파수 패턴 차이 분석
- **제스처 인식**: 손 움직임의 주파수 특성 분석
- **활동 분류**: 걷기, 앉기, 눕기 등의 패턴 구분
- **노이즈 분석**: 환경 노이즈와 움직임 신호 분리

---

## ⚠️ 구현 시 주의사항

### 1. 샘플링 주파수 확인

```
현재 설정: ADC_SPEED_MS = 10ms
샘플링 주파수: Fs = 1000 / 10 = 100 Hz
나이퀴스트 주파수: Fn = Fs / 2 = 50 Hz

PIR 관심 대역: 0.5 ~ 10 Hz → 충분히 커버됨 ✅
```

### 2. DC 오프셋 제거 (필수)

```python
# DC 제거 후 FFT 수행
signal = np.array(adc_buffer) - np.mean(adc_buffer)
```

### 3. 윈도우 함수 적용 (권장)

```python
# 스펙트럼 누설(Spectral Leakage) 방지
window = np.hanning(len(signal))
fft_result = np.fft.rfft(signal * window)
```

### 4. 진폭 정규화

```python
# 단측 스펙트럼으로 정규화
n = len(signal)
magnitudes = np.abs(fft_result) * 2 / n
magnitudes[0] /= 2  # DC 성분은 2배 하지 않음
```

---

## 📐 FFT 구현 코드 예시

```python
import numpy as np

def compute_fft(adc_buffer, sampling_rate=100.0, apply_window=True):
    """
    ADC 버퍼에 FFT 적용
    
    Args:
        adc_buffer: ADC 샘플 배열 (예: 300개의 uint16)
        sampling_rate: 샘플링 주파수 (Hz)
        apply_window: 윈도우 함수 적용 여부
        
    Returns:
        frequencies: 주파수 배열 (Hz)
        magnitudes: 진폭 배열 (정규화됨)
    """
    n = len(adc_buffer)
    
    # 1. DC 오프셋 제거
    signal = np.array(adc_buffer, dtype=np.float64)
    signal = signal - np.mean(signal)
    
    # 2. 윈도우 함수 적용 (선택)
    if apply_window:
        window = np.hanning(n)
        signal = signal * window
    
    # 3. FFT 연산 (실수 신호용 rfft)
    fft_result = np.fft.rfft(signal)
    
    # 4. 진폭 계산 및 정규화
    magnitudes = np.abs(fft_result) * 2 / n
    magnitudes[0] /= 2  # DC 성분 보정
    
    # 5. 주파수 축 생성
    frequencies = np.fft.rfftfreq(n, d=1.0/sampling_rate)
    
    return frequencies, magnitudes
```

---

## 🎯 결론

| 질문 | 답변 |
|---|---|
| **PIR Amp 출력(델타 값)에 FFT가 의미 있나?** | ✅ **예, 매우 의미 있습니다!** |
| **주요 이유** | 1. 델타 신호의 FFT는 움직임 속도 정보를 강조<br>2. 주파수 패턴으로 움직임 유형 분석 가능<br>3. 노이즈 식별 및 필터 효과 검증에 유용 |
| **관심 주파수 대역** | 0.5 ~ 10 Hz (인체 움직임) |
| **구현 시 필수 사항** | DC 오프셋 제거, 적절한 샘플링 주파수 |

---

## 📚 참고 자료

1. Texas Instruments - PIR Motion Sensor Design Guidelines
2. STMicroelectronics - PIR Sensor Application Notes
3. AllAboutCircuits - PIR Sensor Signal Conditioning
4. InfraTec - Pyroelectric Detector Fundamentals
5. ResearchGate - FFT Analysis of PIR Sensor Signals

---

*이 문서는 iSENSOR 프로젝트의 기술 검토 자료입니다.*
