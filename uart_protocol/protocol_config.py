"""
UART 프로토콜 설정 및 상수 정의

ESP32-C3 PIR 센서의 UART 프로토콜 관련 상수와 설정을 중앙 집중화
"""
import enum
# from enum import IntEnum

import config

STX_PATTERN = config.START_SIGNAL
ETX_PATTERN = config.END_SIGNAL
STX_SIZE    = config.START_SIGNAL_SIZE
ETX_SIZE    = config.END_SIGNAL_SIZE

# ==================== Baud Rate 옵션 ====================
class BaudRate(enum.IntEnum):
    """지원하는 Baud Rate 옵션"""
    BAUD_115200 = 115200
    BAUD_230400 = 230400
    BAUD_460800 = 460800
    BAUD_500000 = 500000
    BAUD_576000 = 576000
    BAUD_921600 = 921600
    BAUD_1000000 = 1000000
    BAUD_1152000 = 1152000  # 기본값
    BAUD_1500000 = 1500000
    BAUD_2000000 = 2000000
    BAUD_2500000 = 2500000
    BAUD_3000000 = 3000000
    BAUD_3500000 = 3500000
    BAUD_4000000 = 4000000

# # ==================== 유틸리티 함수 ====================

# def get_data_type_name(data_type: int) -> str:
#     """데이터 타입 번호를 이름으로 변환"""
#     try:
#         return UartDataType(data_type).name
#     except ValueError:
#         return f"UNKNOWN({data_type})"


# def get_expected_payload_size(data_type: int) -> int:
#     """데이터 타입에 대한 예상 페이로드 크기 반환"""
#     try:
#         dt = UartDataType(data_type)
#         return PAYLOAD_SIZE_MAP.get(dt, 0)
#     except ValueError:
#         return 0

class UartCommandType(enum.IntEnum):
    """PC → ESP32 명령 타입 (ESP32 펌웨어의 CommandType_t와 동일)
    
    기존 데이터 타입(0x00~0x09)과 충돌하지 않도록 0x10부터 시작
    """
    CMD_SET_TP1         = config.CMD_SETTING_TP1  # TP1 임계값 설정 (payload: uint16_t, 2 bytes)
    CMD_SET_TP2         = config.CMD_SETTING_TP2  # TP2 카운트 설정 (payload: uint64_t, 8 bytes)
    CMD_SET_TP1_RECHECK = config.CMD_SETTTING_TP1_RECHECK  # TP1 Recheck 임계값 설정 (payload: uint16_t, 2 bytes)
    CMD_GET_SETTINGS    = config.CMD_GET_SETTINGS  # 현재 설정값 요청 (payload: 없음)
    CMD_SAVE_NVS        = config.CMD_SAVE_NVS  # 현재 설정을 NVS에 저장 (payload: 없음)
    CMD_RESET           = config.CMD_RESET  # ESP32 소프트 리셋 (payload: 없음)