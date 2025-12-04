## 📝 내일 할 일 (2025-12-05)

### 1. main.c에서 잔여 Queue 모두 소진 후 종료

*   **구현 가능성**: **매우 높음**
    *   펌웨어에 데이터 생산을 중지하고, 큐의 상태를 확인하며, UART 전송 완료를 기다리는 기능들이 이미 존재합니다. 이 기능들을 올바른 순서로 호출하는 '안전 종료' 함수를 구현하면 됩니다.

*   **구현 방법**:
    1.  **ADC 읽기 중단**: ADC 데이터 생산을 가장 먼저 중단시킵니다. (`custom_adc_pause_reading()` 함수 구현 및 호출)
    2.  **데이터 처리 대기**: ADC 원시 데이터 큐와 가공된 데이터 큐가 모두 비워질 때까지 `while` 루프를 통해 대기합니다. (`custom_adc_is_processing_done()` 함수 구현 및 호출)
    3.  **UART 전송 대기**: `custom_uart_wait_all_tx_done()` 함수를 호출하여 UART 하드웨어 버퍼까지 완전히 비워지도록 대기합니다.
    4.  **최종 종료**: 모든 데이터 처리가 완료되면, `custom_adc_deinit()`, `custom_uart_deinit()` 등 기존의 리소스 해제 함수들을 호출하여 모든 스레드와 큐를 안전하게 종료합니다. 이 로직들을 기존의 `custom_iSENSOR_delete_thread()` 함수에 통합하여 구현하는 것을 추천합니다.

### 2. BLE로 UART 기능을 대체할 수 있는지 확인하기

*   **구현 가능성**: **높음**
    *   ESP32-C3는 BLE(Bluetooth Low Energy)를 지원하며, ESP-IDF 프레임워크는 이를 위한 강력한 API를 제공합니다. 기존의 UART 통신 로직을 BLE로 교체하는 것은 충분히 가능합니다.

*   **구현 방법**:
    1.  **BLE 프로파일 선택**: UART 통신을 가장 유사하게 흉내 낼 수 있는 표준 프로파일인 **"Nordic UART Service (NUS)"**를 사용하는 것을 추천합니다.
    2.  **펌웨어 수정**:
        *   BLE 스택 및 Nordic UART Service를 초기화하는 코드를 추가합니다. 이 서비스는 데이터를 보내고 받기 위한 두 개의 특성(Characteristic)을 가집니다.
        *   기존 `custom_uart_tx_thread`가 `uart_write_bytes`를 호출하는 대신, `esp_ble_gatts_notify_char` 함수를 호출하여 연결된 기기(PC, 스마트폰 등)로 데이터를 전송하도록 수정합니다. STX/ETX 프레이밍과 같은 데이터 구조는 그대로 재사용할 수 있습니다.
    3.  **PC 프로그램(Python) 수정**:
        *   기존 `pyserial` 대신 `bleak`과 같은 Python BLE 라이브러리를 사용해야 합니다.
        *   주변의 BLE 장치를 스캔하여 ESP32를 찾고, Nordic UART Service에 연결한 후, 데이터 수신(Notify)을 구독하도록 코드를 수정합니다.
        *   데이터를 수신한 이후의 파싱 로직(`FrameParser`, `PayloadParser`)은 변경할 필요 없이 그대로 재사용 가능합니다.

### 3. Graph에 TP1, TP2를 출력하는 좋은 방법 찾기

*   **구현 가능성**: **매우 높음**
    *   `pyqtgraph` 라이브러리는 그래프 위에 추가적인 정보를 시각화하는 다양한 기능을 제공합니다.

*   **구현 방법**:
    1.  **임계값(Threshold) 시각화**: TP1과 TP2는 일종의 임계값이므로, 그래프 위에 **수평선**으로 표시하는 것이 가장 직관적이고 효과적입니다.
    2.  **`InfiniteLine` 사용**: `pyqtgraph`의 `pg.InfiniteLine` 객체를 사용하면 그래프에 수평 또는 수직선을 쉽게 추가할 수 있습니다.
    3.  **구현 순서**:
        *   `SETTINGS` 데이터가 수신되었을 때, `tp1`과 `tp2` 값을 `MainWindow`의 멤버 변수에 저장합니다.
        *   `ADC_DELTA_BUFFER` 그래프가 처음 생성될 때, TP1과 TP2에 해당하는 `InfiniteLine` 두 개를 생성하여 그래프에 추가합니다. (펌웨어 코드를 보면 TP값들은 `ADC_DELTA_BUFFER`와 직접적으로 연관됩니다.)
        *   이후 `SETTINGS` 데이터가 업데이트될 때마다, 저장된 `InfiniteLine` 객체의 `setValue()` 메소드를 호출하여 선의 위치를 새로운 TP값으로 업데이트해줍니다.

---

# iSENSOR UART Debugger

ESP32-C3 PIR 재실 감지 센서의 UART 데이터를 수신하고 파싱하는 모듈형 디버깅 도구

---

## 📋 프로젝트 개요

이 프로젝트는 `iSENSOR_PIR_ESP32_C3_MINI_FW` 펌웨어에서 송신하는 UART 데이터를 실시간으로 수신, 파싱, 시각화하는 Python 기반 디버거입니다.

### 주요 특징
- ✅ **STX/ETX 프레임 프로토콜** 지원
- ✅ **10가지 데이터 타입** 파싱 (ADC, Voltage, HPF, Occupancy 등)
- ✅ **모듈형 구조**로 재사용 및 확장 용이
- ✅ **체크섬 검증**으로 데이터 무결성 보장
- ✅ **실시간 데이터 출력** 및 로깅

---

## 🔌 UART 프로토콜 구조

### 프레임 포맷
```
| STX | DATA_TYPE | DATA_LENGTH | PAYLOAD | CHECKSUM | ETX |
|  3  |     1     |      2      | 0~1500   |    2     |  3  | (bytes)
```

### 필드 상세

| 필드 | 크기 | 설명 | 값 |
|------|------|------|-----|
| **STX** | 3 bytes | Start of Text | `0xAA 0x55 0xCC` |
| **DATA_TYPE** | 1 byte | 데이터 타입 | 0~9 |
| **DATA_LENGTH** | 2 bytes | 페이로드 길이 (Little Endian) | 0~512 |
| **PAYLOAD** | 가변 | 실제 데이터 | 타입에 따라 다름 |
| **CHECKSUM** | 2 bytes | Sum 체크섬 (Little Endian) | STX~PAYLOAD 합 |
| **ETX** | 3 bytes | End of Text | `0xDD 0x55 0xAA` |

### 데이터 타입

| 타입 | 값 | 설명 | 페이로드 크기 |
|------|-----|------|---------------|
| ADC_BUFFER | 0 | ADC 버퍼 (uint16 × 300) | 600 bytes |
| VOLTAGE_BUFFER | 1 | Voltage 버퍼 (uint16 × 300) | 600 bytes |
| HPF_BUFFER | 2 | HPF 버퍼 (float32 × 300) | 1200 bytes |
| ADC_DELTA_BUFFER | 3 | ADC Delta 버퍼 (uint16 × 300) | 600 bytes |
| VOLTAGE_DELTA_BUFFER | 4 | Voltage Delta 버퍼 (uint16 × 300) | 600 bytes |
| HPF_DELTA_BUFFER | 5 | HPF Delta 버퍼 (float32 × 300) | 1200 bytes |
| OCCUPANCY_BUFFER | 6 | Occupancy 버퍼 (bool × 300) | 300 bytes |
| SETTINGS | 7 | 설정값 (TP1, TP2, LED 등) | 33 bytes |
| ALL_BUFFERS | 8 | 모든 버퍼 통합 | 가변 |
| ALL_DATA | 9 | 모든 데이터 (미지원) | - |

### 체크섬 계산
```python
def calculate_checksum(data: bytes) -> int:
    """STX부터 PAYLOAD 끝까지 모든 바이트의 합 (16bit)"""
    return sum(data) & 0xFFFF
```

---

## 📁 프로젝트 구조

```
iSENSOR_UART_DEBUGER/
├── uart_protocol/          # UART 프로토콜 파싱 엔진
│   ├── protocol_config.py  # 상수, enum 정의
│   ├── data_models.py      # 데이터 모델 (@dataclass)
│   ├── checksum.py         # 체크섬 계산/검증
│   ├── frame_parser.py     # STX/ETX 프레임 파서
│   └── payload_parser.py   # 페이로드 파서
├── custom_uart/            # UART 통신 모듈
│   ├── uart_header.py      # UART 헤더 및 설정
│   └── uart_thread.py      # UART 수신 스레드
├── utils/                  # 유틸리티
│   ├── byte_converter.py   # 바이트 변환 (Endian)
│   └── logger.py           # 로깅 시스템
├── custom_queue/           # 큐 관리
├── adc_graph/              # 그래프 시각화
├── debuger_start.py        # 메인 프로그램
├── config.yaml             # 설정 파일
├── README.md               # 이 문서
└── PROTOCOL.md             # 프로토콜 상세 문서
```

---

## 🚀 빠른 시작

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 실행
```bash
python debuger_start.py
```

### 3. 설정 (config.yaml)
```yaml
uart:
  baud_rate: 1500000
  port: AUTO        # 자동 감지 또는 COM5
  timeout: 1.0

protocol:
  window_size: 300
  max_payload_size: 512

logging:
  level: INFO
  file: uart_debug.log
```

---

## 🔧 구현 계획

### Phase 1: 프로젝트 분석 ✅
- [x] 기존 코드 구조 파악
- [x] ESP32 펌웨어 UART 프로토콜 분석
- [x] STX/ETX 프레임 구조 확인
- [x] WINDOW_SIZE=300, Sum 체크섬 파악

### Phase 2: 핵심 모듈 구현
- [ ] `uart_protocol/` 디렉토리 생성
- [ ] `protocol_config.py` - STX/ETX, enum
- [ ] `data_models.py` - UartFrame, SensorData
- [ ] `checksum.py` - Sum 체크섬
- [ ] `frame_parser.py` - 프레임 파싱
- [ ] `payload_parser.py` - 페이로드 파싱

### Phase 3: 유틸리티 모듈
- [ ] `byte_converter.py` - Big/Little Endian
- [ ] `logger.py` - 컬러 로깅

### Phase 4: 리팩토링
- [ ] 백업 생성 (`BACKUP_YYYYMMDD/`)
- [ ] `uart_header.py` 개선
- [ ] `uart_thread.py` 새 파서 적용

### Phase 5: 메인 프로그램
- [ ] `config.yaml` 생성
- [ ] `debuger_start.py` CLI 인자
- [ ] 실시간 출력 기능

### Phase 6: 문서화
- [x] `README.md` 작성
- [ ] `PROTOCOL.md` 상세 문서
- [ ] 예제 패킷 분석

### Phase 7: 테스트
- [ ] 단위 테스트 (체크섬, 변환)
- [ ] 샘플 데이터 파싱
- [ ] ESP32 실시간 테스트

---

## 🔍 주요 변경사항

### 백업 코드와의 차이점

| 항목 | 백업 코드 | 현재 구현 |
|------|-----------|-----------|
| 프레임 구조 | 그룹 기반 (5개 그룹) | STX/ETX 프레임 |
| 체크섬 | XOR | Sum (16bit) |
| 신호 식별 | 0xCC 매직 넘버 | STX (0xAA 0x55 0xCC) |
| 데이터 구조 | 동적 길이 그룹 | 고정 타입 페이로드 |
| WINDOW_SIZE | 불명확 | 300 |

---

## 📚 참고 문서

- [PROTOCOL.md](PROTOCOL.md) - UART 프로토콜 상세 문서
- [ESP32 펌웨어](../iSENSOR_PIR_ESP32_C3_MINI_FW/) - UART 송신 코드

---

## 📝 라이센스

이 프로젝트는 iSENSOR PIR ESP32-C3 프로젝트의 일부입니다.

---

## 🤝 기여

버그 리포트 및 개선 제안은 환영합니다!

---

**최종 업데이트**: 2025-12-04