"""
UART 프로토콜 설정 및 상수 정의

ESP32-C3 PIR 센서의 UART 프로토콜 관련 상수와 설정을 중앙 집중화
"""

from enum import IntEnum
from dataclasses import dataclass
from typing import Final

# ==================== 프로토콜 상수 ====================

# 멀티바이트 프레임 구분자 (데이터 충돌 방지)
STX_PATTERN: Final[bytes] = bytes([0xAA, 0x55, 0xCC])
ETX_PATTERN: Final[bytes] = bytes([0xDD, 0x55, 0xAA])
STX_SIZE: Final[int] = 3
ETX_SIZE: Final[int] = 3

# 하위 호환성 (단일 바이트 참조용)
STX: Final[int] = 0xCC  # 마지막 바이트
ETX: Final[int] = 0xAA  # 마지막 바이트

# 프로토콜 제한
WINDOW_SIZE: Final[int] = 300  # ESP32 펌웨어의 WINDOW_SIZE
MAX_PAYLOAD_SIZE: Final[int] = 1500  # 최대 페이로드 크기

# 프레임 구조 크기 (bytes) - 멀티바이트 패턴
FRAME_STX_SIZE: Final[int] = 3  # AA 55 CC
FRAME_DATA_TYPE_SIZE: Final[int] = 1
FRAME_DATA_LENGTH_SIZE: Final[int] = 2
FRAME_CHECKSUM_SIZE: Final[int] = 2
FRAME_ETX_SIZE: Final[int] = 3  # DD 55 AA
FRAME_HEADER_SIZE: Final[int] = FRAME_STX_SIZE + FRAME_DATA_TYPE_SIZE + FRAME_DATA_LENGTH_SIZE  # 6 bytes
FRAME_FOOTER_SIZE: Final[int] = FRAME_CHECKSUM_SIZE + FRAME_ETX_SIZE  # 5 bytes
FRAME_OVERHEAD_SIZE: Final[int] = FRAME_HEADER_SIZE + FRAME_FOOTER_SIZE  # 11 bytes

# ==================== 데이터 타입 ====================

class UartDataType(IntEnum):
    """UART 데이터 타입 Enum (ESP32 펌웨어의 utdte와 동일)
    
    ⚠️ C 펌웨어의 uart_tx_data_type_enum과 정확히 일치해야 함!
    """
    
    # ADC_BUFFER = 0              # UART_TX_ADC_RAW_BUFFER - ADC RAW 버퍼 (uint16 × WINDOW_SIZE)
    # VOLTAGE_BUFFER = 1          # UART_TX_ADC_RAW_VOLTAGE_BUFFER - Voltage 버퍼 (uint16 × WINDOW_SIZE)
    # ADC_HPF_BUFFER = 2          # UART_TX_ADC_SW_HPF_BUFFER - SW HPF 버퍼 (float32 × WINDOW_SIZE)
    # ADC_BPF_BUFFER = 3          # UART_TX_ADC_SW_BPF_BUFFER - SW BPF 버퍼 (float32 × WINDOW_SIZE)
    # HPF_BUFFER = 4              # UART_TX_HPF_BUFFER - HW HPF 버퍼 (uint16 × WINDOW_SIZE)
    # HPF_VOLTAGE_BUFFER = 5      # UART_TX_HPF_VOLTAGE_BUFFER - HW HPF Voltage 버퍼 (uint16 × WINDOW_SIZE)
    # BPF_BUFFER = 6              # UART_TX_BPF_BUFFER - HW BPF 버퍼 (uint16 × WINDOW_SIZE)
    # BPF_VOLTAGE_BUFFER = 7      # UART_TX_BPF_VOLTAGE_BUFFER - HW BPF Voltage 버퍼 (uint16 × WINDOW_SIZE)
    # SETTINGS = 8                # UART_TX_SETTINGS - 설정값 (TP1, TP2, LED 등)
    # ALL_DATA = 9                # UART_TX_ALL_DATA - 모든 데이터 (현재 미지원)
    RAW_VALUE = 0                # UART_TX_ADC_RAW_VALUE
    ADC_BUFFER = 1               # UART_TX_ADC_RAW_BUFFER
    VOLTAGE_BUFFER = 2           # UART_TX_ADC_RAW_VOLTAGE_BUFFER
    ADC_HPF_BUFFER = 3        # UART_TX_ADC_SW_HPF_BUFFER
    ADC_BPF_BUFFER = 4        # UART_TX_ADC_SW_BPF_BUFFER
    HPF_BUFFER = 5               # UART_TX_HPF_BUFFER
    HPF_VOLTAGE_BUFFER = 6       # UART_TX_HPF_VOLTAGE_BUFFER
    BPF_BUFFER = 7               # UART_TX_BPF_BUFFER
    BPF_VOLTAGE_BUFFER = 8       # UART_TX_BPF_VOLTAGE_BUFFER
    SETTINGS = 9                 # UART_TX_SETTINGS
    ALL_DATA = 10                # UART_TX_ALL_DATA


class UartCommandType(IntEnum):
    """PC → ESP32 명령 타입 (ESP32 펌웨어의 CommandType_t와 동일)
    
    기존 데이터 타입(0x00~0x09)과 충돌하지 않도록 0x10부터 시작
    """
    
    CMD_SET_TP1         = 0x10  # TP1 임계값 설정 (payload: uint16_t, 2 bytes)
    CMD_SET_TP2         = 0x11  # TP2 카운트 설정 (payload: uint64_t, 8 bytes)
    CMD_SET_TP1_RECHECK = 0x12  # TP1 Recheck 임계값 설정 (payload: uint16_t, 2 bytes)
    CMD_GET_SETTINGS    = 0x20  # 현재 설정값 요청 (payload: 없음)
    CMD_SAVE_NVS        = 0x30  # 현재 설정을 NVS에 저장 (payload: 없음)
    CMD_RESET           = 0xF0  # ESP32 소프트 리셋 (payload: 없음)


# ==================== 페이로드 크기 ====================

# 각 데이터 타입별 예상 페이로드 크기 (bytes)
PAYLOAD_SIZE_MAP = {
    UartDataType.ADC_BUFFER: WINDOW_SIZE * 2,           # 600 bytes (uint16)
    UartDataType.VOLTAGE_BUFFER: WINDOW_SIZE * 2,       # 600 bytes (uint16)
    UartDataType.ADC_HPF_BUFFER: WINDOW_SIZE * 4,       # 1200 bytes (float32) - SW HPF
    UartDataType.ADC_BPF_BUFFER: WINDOW_SIZE * 4,       # 1200 bytes (float32) - SW BPF
    UartDataType.HPF_BUFFER: WINDOW_SIZE * 2,           # 600 bytes (uint16) - HW HPF
    UartDataType.HPF_VOLTAGE_BUFFER: WINDOW_SIZE * 2,   # 600 bytes (uint16) - HW HPF Voltage
    UartDataType.BPF_BUFFER: WINDOW_SIZE * 2,           # 600 bytes (uint16) - HW BPF
    UartDataType.BPF_VOLTAGE_BUFFER: WINDOW_SIZE * 2,   # 600 bytes (uint16) - HW BPF Voltage
    UartDataType.SETTINGS: 45,                          # 45 bytes (고정)
    # ALL_DATA는 가변 크기
}


# SETTINGS 페이로드 구조 크기
SETTINGS_TP1_SIZE: Final[int] = 2          # uint16 (occupancy)
SETTINGS_TP1_RECHECK_SIZE: Final[int] = 2  # uint16 (recheck)
SETTINGS_TP2_SIZE: Final[int] = 8          # uint64
SETTINGS_LED_MAX_SIZE: Final[int] = 1      # uint8
SETTINGS_LED_MIN_SIZE: Final[int] = 1      # uint8
SETTINGS_LED_IND_SIZE: Final[int] = 1      # uint8
SETTINGS_LED_STEP_SIZE: Final[int] = 4     # uint32 (led_dimming_step_time_ms)
SETTINGS_LED_WORK_SIZE: Final[int] = 4     # uint32 (led_dimming_work_time_ms)
SETTINGS_LED_DELAY_SIZE: Final[int] = 4    # uint32 (led_dimming_delay_time_ms)
SETTINGS_OCCU_TO_SIZE: Final[int] = 8      # uint64
SETTINGS_SLEEP_SIZE: Final[int] = 8        # uint64
SETTINGS_OCCUPANCY_SIZE: Final[int] = 1    # bool (uint8)
SETTINGS_PIR_OUTPUT_SIZE: Final[int] = 1   # bool (uint8)
SETTINGS_TOTAL_SIZE: Final[int] = (
    SETTINGS_TP1_SIZE + SETTINGS_TP1_RECHECK_SIZE + SETTINGS_TP2_SIZE +
    SETTINGS_LED_MAX_SIZE + SETTINGS_LED_MIN_SIZE + SETTINGS_LED_IND_SIZE +
    SETTINGS_LED_STEP_SIZE + SETTINGS_LED_WORK_SIZE + SETTINGS_LED_DELAY_SIZE +
    SETTINGS_OCCU_TO_SIZE + SETTINGS_SLEEP_SIZE +
    SETTINGS_OCCUPANCY_SIZE + SETTINGS_PIR_OUTPUT_SIZE
)  # 45 bytes


# ==================== UART 설정 ====================

@dataclass
class UartConfig:
    """UART 통신 설정"""
    baud_rate: int = 1500000
    port: str = "AUTO"  # "AUTO" 또는 "COM5" 등
    timeout: float = 1.0
    
    # 프로토콜 설정
    window_size: int = WINDOW_SIZE
    max_payload_size: int = MAX_PAYLOAD_SIZE
    
    # 로깅 설정  
    log_level: str = "INFO"
    log_file: str = "uart_debug.log"


# ==================== Baud Rate 옵션 ====================

class BaudRate(IntEnum):
    """지원하는 Baud Rate 옵션"""
    BAUD_115200 = 115200
    BAUD_230400 = 230400
    BAUD_460800 = 460800
    BAUD_500000 = 500000
    BAUD_576000 = 576000
    BAUD_921600 = 921600
    BAUD_1000000 = 1000000
    BAUD_1152000 = 1152000
    BAUD_1500000 = 1500000  # 기본값
    BAUD_2000000 = 2000000
    BAUD_2500000 = 2500000
    BAUD_3000000 = 3000000
    BAUD_3500000 = 3500000
    BAUD_4000000 = 4000000


# ==================== 유틸리티 함수 ====================

def get_data_type_name(data_type: int) -> str:
    """데이터 타입 번호를 이름으로 변환"""
    try:
        return UartDataType(data_type).name
    except ValueError:
        return f"UNKNOWN({data_type})"


def get_expected_payload_size(data_type: int) -> int:
    """데이터 타입에 대한 예상 페이로드 크기 반환"""
    try:
        dt = UartDataType(data_type)
        return PAYLOAD_SIZE_MAP.get(dt, 0)
    except ValueError:
        return 0
