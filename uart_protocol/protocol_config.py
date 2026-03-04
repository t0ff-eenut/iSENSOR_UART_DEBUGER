"""
UART 프로토콜 설정 및 상수 정의

ESP32-C3 PIR 센서의 UART 프로토콜 관련 상수와 설정을 중앙 집중화
"""

from enum import IntEnum

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