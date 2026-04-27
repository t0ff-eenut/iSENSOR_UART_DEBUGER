# iSENSOR UART 디버거 변경 이력

---

## v0.6.4 — Settings 패킷 `fft_stride` 필드 추가 (동기화 완성)

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `config.py` | `UART_RECEIVE_SETTINGS_FFT_STRIDE_BYTESIZE = 2` 상수 추가 |
| `uart_protocol/uart_protocol_config.py` | `RECEIVE_SETTINGS_FFT_STRIDE_LENGTH` 상수 추가; `RECEIVE_SETTINGS_TOTAL_SIZE` 45 → 47 bytes |
| `uart_protocol/data_models.py` | `SettingsData.i_fft_stride` 필드 추가 (uint16, default=32); 도큐스트링 45→47 bytes 수정 |
| `uart_protocol/data_parser.py` | `settings_parser()` — `b_pir_status` 파싱 뒤 `i_fft_stride` uint16 BE 파싱 블록 추가 |
| `debugger_start.py` | `_settings_loaded` 블록에 `fft_stride_SpinBox.setValue(SettingsData_handle.i_fft_stride)` 추가 |

### 프로토콜 변경

| 필드 | 위치 (offset) | 타입 | Endian |
|------|-------------|------|--------|
| `fft_stride` | byte 45~46 | uint16 | Big Endian |

---

## v0.6.3 — ESP Control 레이아웃 정리 + 전체 SpinBox ▲▼ 통일 + FFT Magnitude × Gain 오버레이

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | ESP Control 개별 전송 버튼(9개) 제거 → "📡 전체 설정 전송하기" 버튼 1개로 일괄 전송; TP + LED + 타이머 + Occu/Sleep 순서대로 전송, 실패 항목만 경고창에 표시 |
| `debugger_start.py` | 💡 LED ON/OFF 토글 버튼은 독립 유지 (즉시 전송) |
| `debugger_start.py` | ESP Control 모든 SpinBox(LED Max/Min/Dim, Work/Step/Delay, Occu T/O, Sleep)에 ▲▼ 버튼 추가 — FFT Setting과 동일한 스타일·구조 (`setFixedWidth(28)`, `NoFocus`, `Maximum` SizePolicy) |
| `debugger_start.py` | TP1/TP1 RCK/TP2 ▲▼ 버튼 테두리 스타일 제거 → FFT Setting과 동일한 무테두리 스타일로 통일 |
| `debugger_start.py` | FFT 그래프에 두 번째 선 추가 — `sqrt(energy) × Gain` (오렌지 `#ff8800` 실선); Gain SpinBox 변경 시 즉시 재갱신 (`_on_fft_gain_changed`) |

---

## v0.6.2 — SpinBox 설정값 보호 + FFT Setting UI 개선 + TP 버튼 스타일 통일

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | `_settings_loaded` 플래그 도입 — Settings 패킷 수신 시 최초 1회만 SpinBox 업데이트, 이후 사용자 입력값 유지 |
| `debugger_start.py` | 연결 해제(`event_connection_status_changed`) 시 `_settings_loaded = False` 리셋 → 재연결 후 초기값 자동 수신 |
| `debugger_start.py` | "🔄 설정 새로고침" 버튼 추가 (ESP Control GroupBox 하단 row 13) — 클릭 시 `_settings_loaded = False` 리셋, 다음 수신 1회 업데이트 |
| `debugger_start.py` | FFT Setting — `Stride:` + suffix `" smp"` → `Stride (smp):` + suffix 없음 |
| `debugger_start.py` | TP1 / TP1 RCK / TP2 ▲▼ 화살표 버튼 6개에 테두리 스타일 추가 (`border: 1px solid #7F7F7F; border-radius: 3px`) |

---

## v0.6.1 — Status/Control UI 개선 + Occu Timeout·Sleep Time µs 단위 직접 제어

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | `connect_status_Label` 초기값 `"🔴 Not connected"` 로 변경; 연결 시 `"🟢 Connected"`, 해제 시 `"🔴 Not connected"` 로 텍스트 변경 |
| `debugger_start.py` | Status GroupBox 타이틀 `"Setting"` → `"Status"`; LED/타이머 GroupBox 타이틀 `"Setting"` → `"iSENSOR ESP Control"` |
| `debugger_start.py` | Occu Timeout · Sleep Time SpinBox에 `µs / ms / s` 단위 선택 ComboBox 추가 (기본값 `s`); 전송 시 선택 단위 × 배율 → µs 변환 후 8byte uint64 LE 전송; Settings 수신 시 현재 단위로 나눠 SpinBox 표시 |
| `debugger_start.py` | `_on_time_unit_changed()`, `_send_time_value_occu()`, `_send_time_value_sleep()` 헬퍼 메서드 추가; `_TIME_UNIT_MULTIPLIER` 클래스 상수 추가 |
| `uart_protocol/command_sender.py` | `_uint64_le()` 헬퍼 추가; `send_set_occu_timeout_s` → `send_set_occu_timeout_us` (8byte), `send_set_sleep_time_s` → `send_set_sleep_time_us` (8byte) 로 변경 |

### 단위 선택 범위

| 단위 선택 | SpinBox 최대값 | µs 환산 최대 |
|----------|--------------|-------------|
| µs | 2,147,483,647 | ~35.7분 |
| ms | 2,147,483,647 | ~24.8일 |
| s | 2,147,483,647 | ~68년 |

---

## v0.6.0 — LED & 타이머 설정 GroupBox 추가 + Settings 자동 반영

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `config.py` | `CMD_SET_LED_MAX_PER(0x14)` ~ `CMD_SET_LED_ONOFF(0x1C)` 9개 커맨드 상수 추가 |
| `uart_protocol/uart_protocol_config.py` | `UartCommandType` enum에 9개 CMD 추가 |
| `uart_protocol/command_sender.py` | `send_set_led_max_per` / `send_set_led_min_per` / `send_set_led_dim_per` / `send_set_led_work_ms` / `send_set_led_step_ms` / `send_set_led_delay_ms` / `send_set_occu_timeout_s` / `send_set_sleep_time_s` / `send_set_led_onoff` 메서드 추가; 공통 `_uint32_le()` 헬퍼 추가 |
| `debugger_start.py` | Row4(2열 전체) "LED & 타이머 설정" GroupBox 추가 — LED Max/Min/Dim%, Work/Step/Delay ms, Occu Timeout(초), Sleep Time(초) SpinBox + 개별 전송 버튼; 💡 LED ON/OFF 체크가능 토글 버튼 추가; `_send_led_setting()` 공통 헬퍼 + `event_send_led_onoff_command()` 핸들러 추가; Settings 수신 시 모든 SpinBox 자동 반영 (us→초 변환 포함) |

### 커맨드 테이블

| CMD | 값 | Payload | 단위 |
|-----|-----|---------|------|
| `CMD_SET_LED_MAX_PER` | `0x14` | uint8_t | 0~100 % |
| `CMD_SET_LED_MIN_PER` | `0x15` | uint8_t | 0~100 % |
| `CMD_SET_LED_DIM_PER` | `0x16` | uint8_t | 0~100 % |
| `CMD_SET_LED_WORK_MS` | `0x17` | uint32_t LE | ms |
| `CMD_SET_LED_STEP_MS` | `0x18` | uint32_t LE | ms |
| `CMD_SET_LED_DELAY_MS`| `0x19` | uint32_t LE | ms |
| `CMD_SET_OCCU_TIMEOUT`| `0x1A` | uint32_t LE | 초 |
| `CMD_SET_SLEEP_TIME`  | `0x1B` | uint32_t LE | 초 |
| `CMD_SET_LED_ONOFF`   | `0x1C` | uint8_t | 0=OFF 1=ON |

---

## v0.5.1 — 좌측 패널 배치 column-first로 변경

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | 좌측 GridLayout 배치를 row-first → column-first로 변경: Connection(Row1 Col0), TP Setting(Row1 Col1), Status(Row2-3 Col0 rowSpan=2), FFT Setting(Row2 Col1), SVM Setting(Row3 Col1) |

### 변경 후 구조

```
Col0              │ Col1
Connection        │ TP Setting
Status (span 2행) │ FFT Setting
                  │ SVM Setting
```

---

## v0.5.0 — FFT Stride GUI 제어 + 좌측 패널 2열 레이아웃

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `config.py` | `LEFT_BOX_WIDTH` 400 → 800; `CMD_SET_FFT_STRIDE = 0x13` 추가 |
| `uart_protocol/uart_protocol_config.py` | `UartCommandType.CMD_SET_FFT_STRIDE = 0x13` 추가 |
| `uart_protocol/command_sender.py` | `send_set_fft_stride(i_stride_value: int) → bool` 메서드 추가 (범위 검증 1~256, uint16_t Little Endian) |
| `debugger_start.py` | 좌측 패널 `QVBoxLayout` → `QGridLayout` 2열 균등 배치; `FFT Gain` 그룹박스 타이틀 → `FFT Setting`; Stride SpinBox(1~256 smp, 기본 32) + ms 자동 환산 라벨 + 전송 버튼 추가; `event_send_fft_stride_command()` 핸들러 추가 |

### GUI 레이아웃 구조

```
Row0 (span 2열): 제어창
Row1 col0: Connection   | col1: Setting (Status)
Row2 col0: TP Setting   | col1: FFT Setting (Gain + Stride)
Row3 (span 2열): SVM Setting
```

### FFT Stride 제어 동작

- SpinBox 값 변경 시 `= N ms (약 X.XX s)` 라벨 실시간 갱신 (Fs=100 Hz 기준, 1 smp = 10 ms)
- "📡 Stride 전송" 버튼 → `CMD_SET_FFT_STRIDE(0x13)` 프레임 UART 전송
- 전송 성공/실패 로그 출력

---

## v0.4.4 — import 구조 패키지화 (AI/ `__init__.py` 추가)

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/__init__.py` | **신규** — `AI/` 디렉토리를 Python 패키지로 등록 |
| `debugger_start.py` | `sys.path.insert` 3회 + flat import → 프로젝트 루트 1회 insert + 패키지 import로 단순화: `from AI.svm import svm` / `from AI import training_data_collector as tdc` / `from AI.mlp import nn_mlp` |
| `AI/training_data_collector.py` | `AI/svm/` 에서 `AI/` 로 이동 (모델 무관 공용 모듈 위치 정정); import를 `sys.path.insert(AI/svm/) + import svm` 방식으로 수정 |

### 배경

`AI/svm/__init__.py`(빈 파일)가 존재하여 `import svm` 이 `AI/svm/svm.py` 대신 패키지를 불러오는 문제가 있었음.  
`AI/__init__.py`를 추가해 `AI`를 패키지로 만든 후 `from AI.svm import svm` 형태로 명시적 경로 import로 전환하여 해결.

---

## v0.4.3 — 파일 구조 재편 (fft/, AI/svm/, AI/mlp/)

**날짜:** 2026-04-27

### 변경

| 이전 경로 | 이후 경로 | 비고 |
|---|---|---|
| `fft.py` | `fft/__init__.py` | `uart_protocol/` 패턴 통일 |
| `svm.py` | `AI/svm/svm.py` | SVM 모듈 독립 패키지화 |
| `training_data_collector.py` | `AI/svm/training_data_collector.py` | SVM과 동일 패키지 |
| `AI/nn_mlp.py` | `AI/mlp/nn_mlp.py` | MLP 모듈 독립 패키지화 |
| `AI/prepare_data.py` | `AI/mlp/prepare_data.py` | MLP 전처리 스크립트 |
| `AI/visualize.py` | `AI/mlp/visualize.py` | MLP 시각화 스크립트 |
| `AI/TUNING_GUIDE.md` | `AI/mlp/TUNING_GUIDE.md` | |
| `AI/export/` | `AI/mlp/export/` | C 코드 내보내기 |
| `AI/models/` | `AI/mlp/models/` | 학습된 가중치/스케일러 |
| `AI/logs/` | `AI/mlp/logs/` | 학습 로그 |
| `AI/results/` | `AI/mlp/results/` | 검증 결과 |
| `AI/data_*.csv` | `AI/mlp/data_*.csv` | 분할 학습 데이터 |

각 폴더에 `__init__.py` 추가하여 Python 패키지로 구성.

---

## v0.4.2 — 학습 데이터 수집 모듈 분리 (TrainingDataCollector)

**날짜:** 2026-04-27

### 원인

`SVM_Module` 내부에 CSV 수집 로직(저장 버퍼, 카운터, 헤더 기록 등)이 내장되어 있어
MLP 등 다른 모델이 동일한 CSV를 재사용할 수 없는 구조였음.
학습 데이터 수집을 모델에 종속시키지 않고 공용 모듈로 분리함.

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/svm/training_data_collector.py` | **신규** — `TrainingDataCollector` 클래스: CSV 경로·버퍼·카운터 소유, `save_sample(ft, i_label)` / `flush_write_buffer()` 제공 |
| `AI/svm/svm.py` | `SVM_Module.__init__`에서 `str_svm_csv_path`, `i_bg_count`, `i_human_count`, `_write_buffer`, `_b_need_header` 제거; `save_sample()` / `flush_write_buffer()` / `_load_counts_from_csv()` / `update_label_counts()` 메서드 제거; `_feature_vector_from_uart()` 정적 메서드 → 모듈 레벨 함수 `feature_vector_from_uart(ft)` 로 승격; `train()` 시그니처에 `str_csv_path: str = "svm_data.csv"` 파라미터 추가 |
| `AI/mlp/nn_mlp.py` | `_predict()` 내 `svm_ref._feature_vector_from_uart(svm_ref.ft)` → `svm.feature_vector_from_uart(svm_ref.ft)` |
| `debugger_start.py` | `import training_data_collector as tdc` 추가; `self.collector = tdc.TrainingDataCollector()` 인스턴스 생성; `SvmTrainWorker(svm_handle, str_csv_path)` 시그니처 업데이트; 모든 `svm_handle.save_sample` → `collector.save_sample(self.fft_features_data, ...)`, `svm_handle.flush_write_buffer()` → `collector.flush_write_buffer()`, `svm_handle.i_bg_count/i_human_count` → `collector.i_bg_count/i_human_count` 로 교체 |

### 결과

- `TrainingDataCollector`는 `svm`에 의존하지만 `svm`은 `training_data_collector`에 의존하지 않으므로 순환 의존 없음.
- MLP 학습 시에도 동일한 `TrainingDataCollector` 인스턴스로 CSV 수집 가능.

---

## v0.4.1 — FFT 특징 3개 신규 추가 (f_dc_ratio / f_delta_peak_freq / f_spectral_flatness)

**날짜:** 2026-04-25

### 원인

펌웨어 v0.3.5에서 `fft_features_t`에 3개 특징 추가 및 UART 패킷 확장:
`72 bytes (18 필드)` → `84 bytes (21 필드)`

### 변경

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `RECEIVE_FFT_FEATURES_TOTAL_SIZE` 72→84, 주석 18→21 필드 |
| `uart_protocol/data_models.py` | `FftFeaturesData`에 `f_dc_ratio`, `f_delta_peak_freq`, `f_spectral_flatness` 필드 추가, 테이블 및 `__repr__` 업데이트 |
| `uart_protocol/data_parser.py` | `fft_features_parser()` 오프셋 72/76/80에 3개 필드 파싱 추가, docstring 21 필드로 업데이트 |
| `svm.py` | `I_FEATURES_COUNT` 18→21, `enum_csv_col`에 `DC_RATIO=18`, `DELTA_PEAK_FREQ=19`, `SPECTRAL_FLATNESS=20` 추가, `_feature_vector_from_uart()` 21차원으로 확장 |
| `debugger_start.py` | `SvmFeatureDialog._FEATURE_DEFS`에 3개 항목 추가 |

### 신규 필드 (오프셋 72~80)

| 인덱스 | 필드명 | 설명 |
|--------|--------|------|
| 18 | `f_dc_ratio` | DC 에너지 비율 = E[k=0] / total_E |
| 19 | `f_delta_peak_freq` | 프레임 간 피크 주파수 변화량 (Hz) |
| 20 | `f_spectral_flatness` | 스펙트럼 평탄도 (1=백색잡음, 0=순수톤) |

### 결과

- 기존 `svm_data.csv` (21 컬럼) 형식 유지 (18→21 확장이므로 기존 18-컬럼 CSV는 재수집 필요)
- 펌웨어 `v0.3.5`와 프로토콜 호환.

---

## v0.4.0 — Python ML 파이프라인 UART 특징 기반으로 전면 재정렬

**날짜:** 2026-04-25

### 원인

Python(`svm.py`, `AI/nn_mlp.py`)이 `A_fft_magnitudes`(sqrt(E_k))로 특징을 직접 계산하고 있었으나,
ESP32는 에너지(re²+im²) 기반으로 특징을 계산하여 UART 타입 13으로 전송함.
→ Python이 계산한 값과 ESP32가 전송하는 값의 수치 스케일이 달라 학습/추론 파이프라인이 불일치 상태였음.

### 변경

| 파일 | 변경 내용 |
|---|---|
| `svm.py` | `import config` 제거, `I_FEATURES_COUNT=18`, `enum_csv_col` 18개 항목(UART 필드 순서), `__init__`에서 Python 계산 멤버 변수 제거 (`f_peak_freq`, `A_magnitudes` 등), `self.ft = None` (최신 FftFeaturesData), `svm(input_ft)` 서명 변경 (FftFeaturesData 직접 수신), `_feature_vector_from_uart(ft)` 정적 메서드 신규 추가, `save_sample()` / `train()` / `predict()` / `get_pca_now()` 모두 UART 특징 기반으로 변경, CSV 헤더 18컬럼+label(19열)로 변경 |
| `debugger_start.py` | `SvmFeatureDialog._FEATURE_DEFS` 18개 UART 특징으로 교체 (기존 14개), `buffer_setting()`에서 `svm_handle.svm(fft_features_data)` / `mlp_handle.mlp(fft_features_data)` 호출로 변경, 저장 버튼 가드 `A_magnitudes is None` → `ft is None`으로 변경, 자동저장 조건도 동일하게 변경 |
| `AI/nn_mlp.py` | `mlp(input_ft)` 서명 변경 (FftFeaturesData 직접 수신), `_predict()`에서 163차원 직접 계산 제거 → `svm_ref._feature_vector_from_uart(svm_ref.ft)` 사용 |

### 결과

- 학습·추론에 사용하는 특징값이 ESP32 UART 전송값과 완전히 일치함.
- 기존 `svm_data.csv` (142 컬럼 형식)는 새 형식(19 컬럼)과 호환 불가 — 데이터 재수집 필요.
- 펌웨어 `v0.3.4`와 프로토콜 호환.

---

## v0.3.1 — FFT_FEATURES(타입 13) 수신 지원 및 프로파일링 필드 재정의

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

## v0.3.0 — FFT energy uint32 수신 및 magnitude 복원 처리

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

## v0.2.3 — 특징 추출 실행 시간 프로파일링 수신 지원

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

## v0.2.2 — ADC/FFT 그래프 품질 개선 및 버그 수정

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

## v0.2.1 — MLP 전용 Plot 분리 및 ADC 그래프 시간축 실시간 업데이트

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
