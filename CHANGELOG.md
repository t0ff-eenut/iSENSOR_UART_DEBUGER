# iSENSOR UART 디버거 변경 이력

---

## v0.7.0 — FFT_FEATURES(타입 13) 수신 지원 및 프로파일링 필드 재정의

**날짜:** 2026-04-24

### 원인

펌웨어 v0.3.4에서 `UART_TX_FFT_FEATURES` (타입 13, 72 bytes) 패킷 신규 추가 및
`UART_TX_PROFILING` 필드가 구버전(스택 HWM 포함 9개) → 신규 실행 시간 기반 9개로 재정의됨.

### 변경

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `UartDataType.FFT_FEATURES = 13` 추가, `RECEIVE_FFT_FEATURES_TOTAL_SIZE = 72` 추가, PROFILING 주석 신규 9개 필드로 업데이트 |
| `uart_protocol/data_models.py` | `ProfilingData` 9개 필드 재정의 (스택 HWM 제거 → ADC/FFT 실행 시간으로 교체), `FftFeaturesData` dataclass 신규 추가 (18개 필드, 72 bytes), `SensorData`에 `fft_features` 필드 추가 |
| `uart_protocol/data_parser.py` | `profiling_parser()` 루프 `range(8)→range(9)`, 신규 필드명 적용, `data_parser()` 타입 13 case 추가, `fft_features_parser()` 메서드 신규 구현 (float/int32/uint32 Big Endian) |
| `debugger_start.py` | `fft_features_data` 멤버 추가, `event_update_ui()`에서 타입 13 수신 시 저장, FFT 그래프 Y축 에너지(re²+im²)로 변경, FFT 레이블에 18개 특징값(영문+한글) 표시, 프로파일링 라벨 신규 9개 필드로 업데이트 |

### 신규: FFT_FEATURES 페이로드 (72 bytes, 18 필드 × 4 bytes Big Endian)

| 순서 | 필드명 | 타입 | 설명 |
|------|--------|------|------|
| 0 | `f_spectral_rolloff` | float | 스펙트럼 롤오프 (Hz) |
| 1 | `f_spectral_bandwidth` | float | 스펙트럼 대역폭 (Hz) |
| 2 | `i_peak_count` | int32 | 피크 빈 개수 |
| 3 | `f_mid_ratio` | float | 중주파(5~10Hz) 비율 |
| 4 | `f_low_to_high_ratio` | float | 저/고주파 에너지 비율 |
| 5 | `f_second_peak_freq` | float | 2번째 피크 주파수 (Hz) |
| 6 | `f_kurtosis` | float | 첨도 |
| 7 | `f_centroid` | float | 스펙트럼 무게중심 주파수 (Hz) |
| 8 | `f_peak_freq` | float | 1번째 피크 주파수 (Hz) |
| 9 | `f_low_ratio` | float | 저주파(0~5Hz) 비율 |
| 10 | `f_rms` | float | RMS 진폭 |
| 11 | `ui32_avg_energy` | uint32 | 평균 에너지 (정수) |
| 12 | `ui32_peak_energy` | uint32 | 피크 에너지 (정수) |
| 13 | `f_energy_variance` | float | 에너지 분산 |
| 14 | `f_peak_to_avg_e` | float | 피크/평균 에너지 비율 |
| 15 | `f_high_ratio` | float | 고주파(10Hz+) 비율 |
| 16 | `f_peak1_to_peak2_ratio` | float | 1위 vs 2위 피크 비율 |
| 17 | `f_skewness` | float | 왜도 |

### 변경: PROFILING 페이로드 (36 bytes, 9 필드 × uint32 Big Endian)

| 순서 | 구버전 필드 | 신버전 필드 |
|------|------------|------------|
| 0 | `adc_process_time_us` | `adc_reading_time_us` |
| 1 | `algo_process_time_us` | `adc_read_buffer_latency_time_us` |
| 2 | `loop_period_us` | `adc_processing_time_us` |
| 3 | `bg_stack_hwm` | `adc_buffer_insert_time_us` |
| 4 | `main_stack_hwm` | `fft_process_time_us` |
| 5 | `uart_tx_stack_hwm` | `fft_features_process_time_us` |
| 6 | `uart_rx_stack_hwm` | `fft_loop_a_time_us` |
| 7 | `fft_process_time_us` | `fft_loop_b_time_us` |
| 8 | `feat_process_time_us` | `fft_loop_c_time_us` |

### 결과

- 타입 13 패킷 수신 시 FFT 특징값 18개가 그래프 레이블에 실시간 표시됨.
- FFT 그래프 Y축이 진폭(magnitude)에서 에너지(re²+im², uint32)로 변경됨.
- 프로파일링 패널이 ADC/FFT 단계별 실행 시간 9개로 재편됨.
- 펌웨어 `v0.3.4`와 프로토콜 호환.

---

## v0.6.0 — FFT energy uint32 수신 및 magnitude 복원 처리

**날짜:** 2026-04-22

### 원인

펌웨어 v0.3.1에서 `UART_TX_FFT` 패킷 포맷이 `float magnitude × 129 (516 bytes)`에서
`uint32 energy × 129 (516 bytes)`로 변경됨.
PC에서 `sqrt(energy) / scale × 2/N` 으로 magnitude를 복원하여 기존 그래프에 표시.

### 변경

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `RECEIVE_FFT_TOTAL_SIZE` 확인 (516 bytes, 변동 없음) |
| `uart_protocol/data_models.py` | `FftData`에 `energies: List[int]` 필드 추가 (`magnitudes` 필드 유지) |
| `uart_protocol/data_parser.py` | `fft_parser()`: `>129f` → `>129I` (uint32 언패킹), magnitude 복원 수식 추가 (`sqrt(e)/8 × 2/256` 또는 `1/256` for k=0) |
| `debugger_start.py` | `A_fft_energies = numpy.array(fft_data.energies, dtype=numpy.uint32)` 추가 |

### FFT magnitude 복원 수식

```python
FFT_SC16_SCALE = 8
N = 256  # FFT_SIZE
magnitudes = [
    math.sqrt(e) / FFT_SC16_SCALE * (1.0 / N if k == 0 else 2.0 / N)
    for k, e in enumerate(energies)
]
```

### 결과

- 펌웨어에서 sqrtf×129 실행 없이 FFT 결과 전송.
- PC에서 `math.sqrt()` × 129 수행 (Python, GIL 영향 무시 수준).
- GUI FFT 그래프 표시 값 스케일 동일 (ADC 단위).
- `energies` 배열은 향후 PC 측 특징 추출 시 energy 기반 계산에 직접 사용 가능.

---

## v0.5.0 — 특징 추출 실행 시간 프로파일링 수신 지원

**날짜:** 2026-04-22

### 수정

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `RECEIVE_PROFILING_TOTAL_SIZE` 32 → 36 bytes (9×4, `feat_process_time_us` 필드 추가) |
| `uart_protocol/data_models.py` | `ProfilingData`에 `feat_process_time_us` 필드 추가, `__repr__` 업데이트 |
| `uart_protocol/data_parser.py` | `fields[8]` 파싱 추가 (`feat_process_time_us`) |
| `debugger_start.py` | 프로파일링 라벨에 `특징 추출: X µs` 항목 추가 |

### 결과

- 프로파일링 패널에 FFT 처리 시간과 별도로 특징 추출 실행 시간이 표시된다.
- 폄웨어 `v0.3.0`과 프로토콜 호환 (패이로드 9필드, 36 bytes)

---

## v0.4.0 — ADC/FFT 그래프 품질 개선 및 버그 수정

**날짜:** 2026-04-22

### 수정

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | ADC 그래프 Y축에 `IntAxisItem` 적용 — 자동 스케일 시 정수 배수 눈금만 표시 |
| `debugger_start.py` | FFT 그래프 Y축 `enableAutoSIPrefix(False)` 추가 — `×0.001` 같은 SI 배율 주석 제거, 소수점 직접 표시 |
| `debugger_start.py` | `get_adc_buffer_info()` 버그 수정 — 버퍼 전체가 0일 때 4개 값만 반환하던 문제 수정 (13개 기본값 반환으로 `ValueError` 해소) |
| `debugger_start.py` | ADC 수신 블록에서 FFT 그래프 갱신 호출 제거 — FFT 그래프는 `fft_result` 패킷 수신 시에만 갱신 |

### 상세

**IntAxisItem (ADC Y축 정수 눈금)**
- `pyqtgraph.AxisItem` 서브클래스 추가
- `tickValues()`: 화면 높이 기준 최대 ~8개 정수 간격 눈금 자동 생성 (1→2→5→10 배율)
- `tickStrings()`: 소수점 없이 정수 문자열 반환
- ADC Raw Full Scale / Zoom Scale 탭에만 적용 (FFT는 소수점 유지)

**FFT 그래프 갱신 분리**
- 이전: ADC 패킷 수신 시마다 `update_fft_graph()` 호출 → FFT 데이터 미변경 상태에서 재표시만 반복
- 이후: `fft_result` 패킷이 도착할 때만 갱신 (`FFT_STRIDE`=64샘플마다 1회)

**`get_adc_buffer_info()` 버그**
- 버퍼 전체 0일 때 (연결 직후 등) `return 0, 0, 0, 0` → `ValueError: not enough values to unpack (expected 13, got 4)` 발생
- 수정: 13개 기본값(전체 통계는 계산된 값, zero-excluded 통계는 0)을 반환하도록 변경

### 결과

- ADC Y축에 `0.5`, `1.5` 같은 소수 눈금이 사라지고 `1`, `2`, `3` 등 정수만 표시된다.
- FFT Y축에서 `×0.001` 배율 표기가 사라지고 `0.0012` 등 실제 소수점 값이 표시된다.
- 연결 직후 ADC 버퍼가 0으로 채워진 상태에서도 UI 오류 없이 정상 동작한다.
- ADC/FFT 그래프가 각자의 수신 주기에 맞춰 독립적으로 갱신된다.

---

## v0.3.0 — MLP 전용 Plot 분리 및 ADC 그래프 시간축 실시간 업데이트

**날짜:** 2026-04-22

### 수정

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | MLP 탭을 SVM TabWidget에서 분리하여 독립 `mlp_graph_GroupBox` + `mlp_plot_TabWidget` 생성. SVM/MLP 영역을 수직 컨테이너(`svm_mlp_Widget`)로 묶어 `main_HBoxLayout`에 단일 컬럼으로 배치 |
| `debugger_start.py` | ADC 그래프 시간축 하드코딩(`300`) → `cfg.WINDOW_SIZE`(=256) 초기값으로 변경. 데이터 수신 시마다 실제 버퍼 길이(`len(self.A_adc_buffer)`)로 X축을 실시간 갱신(`setXRange`) |

### 레이아웃 변경 상세

**이전:**
```
main_HBoxLayout
└── svm_graph_GroupBox
    └── svm_plot_TabWidget
        ├── SVM 탭
        ├── SVM PCA 탭
        ├── MLP 확률 탭   ← SVM TabWidget 내 혼재
        └── MLP 히스토리 탭
```

**이후:**
```
main_HBoxLayout
└── svm_mlp_Widget (수직 컨테이너)
    ├── svm_graph_GroupBox  →  svm_plot_TabWidget (SVM, SVM PCA)
    └── mlp_graph_GroupBox  →  mlp_plot_TabWidget (MLP 확률, MLP 히스토리)
```

### 결과

- SVM Plot과 MLP Plot이 동일 컬럼에서 50:50 비율로 위/아래 분리된다.
- ADC 그래프 X축이 ESP32 버퍼 크기와 항상 일치한다 (첫 수신 전에도 `cfg.WINDOW_SIZE` 기준).
- `WINDOW_SIZE` 값 변경 시 초기값과 실시간 축 범위 모두 자동으로 반영된다.

---

## v0.2.0 — ESP32 FFT 수신 파싱 및 PC FFT 연산 대체

**날짜:** 2026-04-22

### 원인

ESP32 펌웨어(v0.2.0)에서 온디바이스 FFT 결과를 UART 타입 12로 전송하도록 변경됨에 따라,
PC 측도 타입 12 파싱 로직을 추가하고 기존 PC 연산 FFT를 수신 FFT 데이터로 교체해야 했다.
또한 `ProfilingData`에 `fft_process_time_us` 필드가 추가(7→8 필드, 28→32 bytes)되어
타입 11 파서도 함께 수정이 필요했다.

### 수정

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `UartDataType.FFT = 12` 추가. `RECEIVE_FFT_TOTAL_SIZE = (WINDOW_SIZE//2+1)*4` (=516) 상수 추가. `RECEIVE_PROFILING_TOTAL_SIZE` 28→32 bytes로 수정 |
| `uart_protocol/data_models.py` | `ProfilingData`에 `fft_process_time_us` 필드 추가 (7→8 필드). `FftData` 데이터클래스 신규 추가(`magnitudes: List[float]`). `SensorData`에 `fft_result: Optional[FftData]` 필드 추가 |
| `uart_protocol/data_parser.py` | `profiling_parser()`: 파싱 루프 7→8 필드, `fft_process_time_us` 반환. `data_parser()`에 타입 12 분기 추가. `fft_parser()` 메서드 신규 구현 (516 bytes → 129 × float32 BE) |
| `debugger_start.py` | `buffer_setting()`: `fft_handle.fft()` 호출 주석 처리(PC FFT 비활성화). `event_update_ui()`: 타입 12 수신 시 `A_fft_frequencies` / `A_fft_magnitudes` 갱신 후 FFT 그래프 업데이트 |

**`FftData` 데이터클래스:**

| 필드 | 타입 | 설명 |
|---|---|---|
| `magnitudes` | `List[float]` | 129개 진폭값 (Big Endian float32 파싱 결과) |

**`ProfilingData` 변경 (7→8 필드):**

| 추가 필드 | 설명 | 단위 |
|---|---|---|
| `fft_process_time_us` | ESP32 FFT 실행 시간 | µs |

### 결과

- UART 타입 12 수신 시 `SensorData.fft_result`에 `FftData` 객체가 채워진다.
- PC FFT 연산(`fft_handle.fft()`)을 거치지 않고 ESP32 연산 결과로 FFT 그래프가 직접 갱신된다.
- SVM/MLP 추론은 기존과 동일하게 `A_fft_frequencies` / `A_fft_magnitudes` 를 사용한다.
- 타입 11 파싱 크기 불일치 오류 없이 32 bytes(8 필드)가 정상 파싱된다.

---

## v0.1.0 — 프로파일링 데이터(타입 11) 수신 파싱 추가

**날짜:** 2026-04-22

### 원인

펌웨어에서 UART 데이터 타입 11(`UART_TX_PROFILING`)으로 실행 시간 및 FreeRTOS Task
스택 고수위(HWM) 데이터 전송이 추가됨에 따라, PC 디버거 측에도 해당 타입의 수신 파싱
로직이 필요해졌다.

### 수정

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `UartDataType.PROFILING = 11` 추가, `RECEIVE_PROFILING_TOTAL_SIZE = 28` 상수 추가 |
| `uart_protocol/data_models.py` | `ProfilingData` 데이터클래스 추가(7개 필드), `SensorData.profiling: Optional[ProfilingData]` 필드 추가 |
| `uart_protocol/data_parser.py` | `DataParser.data_parser()`에 타입 11 분기 추가, `profiling_parser()` 메서드 구현 |

**`ProfilingData` 데이터클래스 필드:**

| 필드 | 설명 | 단위 |
|---|---|---|
| `adc_process_time_us` | ADC 큐 수신 ~ 버퍼 저장 처리 시간 | µs |
| `algo_process_time_us` | TP1/TP2 알고리즘 실행 시간 | µs |
| `loop_period_us` | 배경 스레드 루프 주기 | µs |
| `bg_stack_hwm` | Background Task 스택 고수위 | words |
| `main_stack_hwm` | Main Task 스택 고수위 | words |
| `uart_tx_stack_hwm` | UART TX Task 스택 고수위 | words |
| `uart_rx_stack_hwm` | UART RX Task 스택 고수위 | words |

### 결과

- 타입 11 프레임 수신 시 `SensorData.profiling`에 파싱된 `ProfilingData` 객체가 채워진다.
- 파싱 포맷: 28 bytes, 7 × uint32_t Big Endian.
- 기존 프로토콜 파서 구조(`data_parser` → `data_models`)와 동일한 패턴을 유지한다.
