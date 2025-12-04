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
|  1  |     1     |      2      | 0~512   |    2     |  1  | (bytes)
```

### 필드 상세

| 필드 | 크기 | 설명 | 값 |
|------|------|------|-----|
| **STX** | 1 byte | Start of Text | `0x02` |
| **DATA_TYPE** | 1 byte | 데이터 타입 | 0~9 |
| **DATA_LENGTH** | 2 bytes | 페이로드 길이 (Little Endian) | 0~512 |
| **PAYLOAD** | 가변 | 실제 데이터 | 타입에 따라 다름 |
| **CHECKSUM** | 2 bytes | Sum 체크섬 (Little Endian) | STX~PAYLOAD 합 |
| **ETX** | 1 byte | End of Text | `0x03` |

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
| 신호 식별 | 0xCC 매직 넘버 | STX (0x02) |
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
