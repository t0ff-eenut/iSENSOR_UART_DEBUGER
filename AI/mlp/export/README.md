# ESP32-C3 배포용 MLP 모델 내보내기

> 생성 스크립트: `export_float32.py` / `export_int8.py`  
> 출력 위치: `AI/export/output/`

---

## 실행 방법

```bash
# v3.0 모델 학습 완료 후 실행
python3 AI/export/export_float32.py   # float32 C 코드 생성
python3 AI/export/export_int8.py      # int8 양자화 C 코드 생성
```

생성된 `.h` + `.c` 파일을 ESP-IDF 프로젝트에 복사하고 include만 하면 바로 사용 가능합니다.

```c
// ESP32-C3 코드 예시
#include "mlp_float32.h"   // 또는 mlp_int8.h

float human_prob;
int label = mlp_float32_infer(fft_features, &human_prob);
// label: 0 = 배경, 1 = 사람
// human_prob: 사람일 확률 (0.0 ~ 1.0)
```

---

## float32 vs int8 비교

### 기본 수치 (v3.0 기준: [128, 64, 32])

| 항목 | float32 | int8 |
|---|---|---|
| 가중치 데이터 타입 | `float` (4바이트) | `int8_t` (1바이트) |
| 편향 데이터 타입 | `float` (4바이트) | `int32_t` (4바이트) |
| 모델 가중치 크기 | ~56 KB | **~15 KB** |
| 압축률 | 기준 | **약 4배 압축** |
| 추론 정확도 손실 | 없음 | 보통 **0.1 ~ 0.3%p** |

---

### 내부 연산 방식

#### float32
```
입력(float) → [float × float MAC] → 출력(float)
```
- 모든 연산이 float 부동소수점
- ESP32-C3는 FPU(부동소수점 전용 하드웨어)가 없으므로 **소프트웨어로 float 연산** → 상대적으로 느림

#### int8
```
입력(float) → [양자화 → int8] → [int8 × int8 → int32 MAC] → [dequantize → float] → 출력
```
- 가중치는 int8로 저장 (메모리 절약)
- MAC(곱셈-누산) 연산은 정수 연산 → RISC-V 정수 명령어 활용 → **float보다 빠름**
- 레이어 출력에서만 float 복원 (1회 dequantize)

---

### 양자화 방식 (Symmetric PTQ)

```
가중치 양자화: W_int8 = round(W_float / scale)
              scale = max|W| / 127

편향 양자화:   b_int32 = round(b_float / (in_scale × w_scale))

추론 시:       acc = Σ (W_int8[i] × x_int8[i])  + b_int32   ← int32 정수 연산
              output = acc × (in_scale × w_scale)             ← 한 번만 float 변환
```

**PTQ (Post-Training Quantization)**: 재학습 없이 학습된 모델을 변환.  
캘리브레이션 데이터(`data_val.csv`)로 각 레이어 입력 범위를 측정해 scale 결정.

---

### BatchNorm 융합

두 버전 모두 내보내기 시 **BatchNorm을 Linear에 수학적으로 흡수**합니다.

```
원래: Linear → BatchNorm → ReLU  (3개 연산)
변환: Linear(BN 융합) → ReLU    (2개 연산)
```

C 코드에서 별도의 BatchNorm 연산이 필요 없어 구현이 단순해집니다.

---

### ESP32-C3 배포 권장 기준

| 상황 | 권장 버전 |
|---|---|
| 메모리 여유 있고 정확도 최우선 | **float32** |
| 메모리 절약 + 추론 속도 최우선 | **int8** |
| 둘 다 동작하는지 먼저 확인 | float32로 검증 후 int8 교체 |

> ESP32-C3 SRAM 400KB 기준  
> float32: 56KB(모델) + TFLite Micro 불필요 (순수 C 코드) → 여유 있음  
> int8:    15KB(모델) → **더욱 여유롭고 추론 속도 유리**

---

### 출력 파일 구조

```
AI/export/output/
    mlp_float32.h   — StandardScaler + float 가중치 배열 + 함수 선언
    mlp_float32.c   — mlp_float32_infer() 구현
    mlp_int8.h      — StandardScaler + int8 가중치 + int32 편향 + scale 상수
    mlp_int8.c      — mlp_int8_infer() 구현 (int32 MAC 루프)
```

파일명에 버전 정보가 없는 이유: `nn_mlp.py`의 현재 세팅(`HIDDEN_LAYERS`, `EPOCHS`, `LEARNING_RATE`)을 읽어 해당 모델을 자동으로 찾아 생성하므로, 세팅을 바꾸고 재실행하면 그 버전의 코드가 덮어써집니다.
