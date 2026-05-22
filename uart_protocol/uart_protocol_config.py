"""
UART 프로토콜 설정 및 상수 정의

ESP32-C3 PIR 센서의 UART 프로토콜 관련 상수와 설정을 중앙 집중화
"""
import enum
# from enum import IntEnum

import config   as cfg

"""
UART Receive Data Frame Model

멀티바이트 STX/ETX 프레임 구조:
| STX(3) | DATA_TYPE | DATA_LENGTH | PAYLOAD | CHECKSUM | ETX(3) |
"""
UART_RECEIVE_STX_PATTERN:bytes      = cfg.UART_RECEIVE_START_PATTERN
# STX_SIZE:int            = cfg.UART_RECEIVE_START_SIGNAL_SIZE
RECEIVE_STX_LENGTH:int = len(UART_RECEIVE_STX_PATTERN)


RECEIVE_DATA_TYPE_LENGTH:int        = cfg.UART_RECEIVE_DATA_TYPE_BYTESIZE
RECEIVE_DATA_TYPE_SIZE_LENGTH:int   = cfg.UART_RECEIVE_DATA_LENGTH_BYTESIZE
RECEIVE_DATA_TPYE_FILD_LENGTH:int   = RECEIVE_DATA_TYPE_LENGTH + RECEIVE_DATA_TYPE_SIZE_LENGTH
RECEIVE_HEADER_LENGTH:int           = RECEIVE_STX_LENGTH + RECEIVE_DATA_TPYE_FILD_LENGTH

RECEIVE_MAX_PAYLOAD_LENGTH:int      = cfg.UART_RECEIVE_MAX_PAYLOAD_BYTESIZE

RECEIVE_CHECKSUM_LENGTH:int         = cfg.UART_RECEIVE_CHECKSUM_BYTESIZE

UART_RECEIVE_ETX_PATTERN:bytes      = cfg.UART_RECEIVE_END_PATTERN
# ETX_SIZE:int            = cfg.END_SIGNAL_SIZE
UART_RECEIVE_ETX_SIZE:int           = len(UART_RECEIVE_ETX_PATTERN)

# SETTINGS 페이로드 구조 크기
RECEIVE_SETTINGS_TP1_LENGTH:int                 = cfg.UART_RECEIVE_SETTINGS_TP1_BYTESIZE
RECEIVE_SETTINGS_TP1_RECHECK_LENGTH:int         = cfg.UART_RECEIVE_SETTINGS_TP1_RECHECK_BYTESIZE
RECEIVE_SETTINGS_TP2_LENGTH:int                 = cfg.UART_RECEIVE_SETTINGS_TP2_BYTESIZE
RECEIVE_SETTINGS_LED_MAX_PER_LENGTH:int         = cfg.UART_RECEIVE_SETTINGS_LED_MAX_PER_BYTESIZE
RECEIVE_SETTINGS_LED_MIN_PER_LENGTH:int         = cfg.UART_RECEIVE_SETTINGS_LED_MIN_PER_BYTESIZE
RECEIVE_SETTINGS_LED_DIM_PER_LENGTH:int         = cfg.UART_RECEIVE_SETTINGS_LED_DIM_PER_BYTESIZE
RECEIVE_SETTINGS_LED_WORK_MS_LENGTH:int         = cfg.UART_RECEIVE_SETTINGS_LED_WORK_MS_BYTESIZE
RECEIVE_SETTINGS_LED_STEP_MS_LENGTH:int         = cfg.UART_RECEIVE_SETTINGS_LED_STEP_MS_BYTESIZE
RECEIVE_SETTINGS_LED_DELAY_MS_LENGTH:int        = cfg.UART_RECEIVE_SETTINGS_LED_DELAY_MS_BYTESIZE
RECEIVE_SETTINGS_OCCU_CHK_TIMEOUT_LENGTH:int    = cfg.UART_RECEIVE_SETTINGS_OCCU_CHK_TIMEOUT_BYTESIZE
RECEIVE_SETTINGS_SLEEP_TIME_LENGTH:int          = cfg.UART_RECEIVE_SETTINGS_SLEEP_TIME_BYTESIZE
RECEIVE_SETTINGS_OCCUPANCY_STATUS_LENGTH:int    = cfg.UART_RECEIVE_SETTINGS_OCCUPANCY_STATUS_BYTESIZE
RECEIVE_SETTINGS_PIR_STATUS_LENGTH:int          = cfg.UART_RECEIVE_SETTINGS_PIR_STATUS_BYTESIZE
RECEIVE_SETTINGS_FFT_STRIDE_LENGTH:int          = cfg.UART_RECEIVE_SETTINGS_FFT_STRIDE_BYTESIZE
RECEIVE_SETTINGS_TOTAL_SIZE:int = (
    RECEIVE_SETTINGS_TP1_LENGTH
    + RECEIVE_SETTINGS_TP1_RECHECK_LENGTH
    + RECEIVE_SETTINGS_TP2_LENGTH
    + RECEIVE_SETTINGS_LED_MAX_PER_LENGTH
    + RECEIVE_SETTINGS_LED_MIN_PER_LENGTH
    + RECEIVE_SETTINGS_LED_DIM_PER_LENGTH
    + RECEIVE_SETTINGS_LED_WORK_MS_LENGTH
    + RECEIVE_SETTINGS_LED_STEP_MS_LENGTH
    + RECEIVE_SETTINGS_LED_DELAY_MS_LENGTH
    + RECEIVE_SETTINGS_OCCU_CHK_TIMEOUT_LENGTH
    + RECEIVE_SETTINGS_SLEEP_TIME_LENGTH
    + RECEIVE_SETTINGS_OCCUPANCY_STATUS_LENGTH
    + RECEIVE_SETTINGS_PIR_STATUS_LENGTH
    + RECEIVE_SETTINGS_FFT_STRIDE_LENGTH
)  # 47 bytes




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

def get_data_type_name(data_type: int) -> str:
    """데이터 타입 번호를 이름으로 변환"""
    try:
        return UartDataType(data_type).name
    except ValueError:
        return f"UNKNOWN({data_type})"


# def get_expected_payload_size(data_type: int) -> int:
#     """데이터 타입에 대한 예상 페이로드 크기 반환"""
#     try:
#         dt = UartDataType(data_type)
#         return PAYLOAD_SIZE_MAP.get(dt, 0)
#     except ValueError:
#         return 0

# custom_esp_uart_thread.h -> uart_tx_data_type_enum
class UartDataType(enum.IntEnum):
    RAW_VALUE = 0                # UART_TX_ADC_RAW_VALUE
    ADC_BUFFER = 1               # UART_TX_ADC_RAW_BUFFER
    # VOLTAGE_BUFFER = 2           # UART_TX_ADC_RAW_VOLTAGE_BUFFER
    # ADC_HPF_BUFFER = 3        # UART_TX_ADC_SW_HPF_BUFFER
    # ADC_BPF_BUFFER = 4        # UART_TX_ADC_SW_BPF_BUFFER
    # HPF_BUFFER = 5               # UART_TX_HPF_BUFFER
    # HPF_VOLTAGE_BUFFER = 6       # UART_TX_HPF_VOLTAGE_BUFFER
    # BPF_BUFFER = 7               # UART_TX_BPF_BUFFER
    # BPF_VOLTAGE_BUFFER = 8       # UART_TX_BPF_VOLTAGE_BUFFER
    SETTINGS = 9                 # UART_TX_SETTINGS
    # ALL_DATA = 10                # UART_TX_ALL_DATA
    PROFILING = 11               # UART_TX_PROFILING (40 bytes: 10 x uint32_t Big Endian)
    FFT = 12                     # UART_TX_FFT (FFT_OUTPUT_SIZE x 4 bytes Big Endian uint32)
    FFT_FEATURES = 13            # UART_TX_FFT_FEATURES (84 bytes: 21 필드 Big Endian)
    MLP_RESULT = 14              # UART_TX_MLP_RESULT (8 bytes: int32 label + float32 prob)

# PROFILING 페이로드 크기: 11개 필드 x 4 bytes = 44 bytes
# 필드 순서 (펜웨어 uart_thread.c UART_TX_PROFILING case와 동일):
#   0: adc_reading_time_us
#   1: adc_read_buffer_latency_time_us
#   2: adc_processing_time_us
#   3: adc_buffer_insert_time_us
#   4: fft_process_time_us
#   5: fft_features_process_time_us
#   6: fft_loop_a_time_us
#   7: fft_loop_b_time_us
#   8: fft_loop_c_time_us
#   9: float32_mlp_infer_time_us
#  10: int8_mlp_infer_time_us
RECEIVE_PROFILING_TOTAL_SIZE:int = 44   # 11 x uint32_t

# MLP_RESULT 페이로드 크기:
#   float_label(int32 BE) + float_prob(float32 BE) + int_label(int32 BE) + int_prob(float32 BE) = 16 bytes
RECEIVE_MLP_RESULT_TOTAL_SIZE:int = 16

# FFT 페이로드 크기: (WINDOW_SIZE/2 + 1) 진폭값 x 4 bytes = 516 bytes
RECEIVE_FFT_TOTAL_SIZE:int = (cfg.WINDOW_SIZE // 2 + 1) * 4  # 516 bytes

# FFT_FEATURES 페이로드 크기: 21개 필드 x 4 bytes = 84 bytes
# float×16 + int32×1(i_peak_count) + uint32×1(ui32_avg_energy, ui32_peak_energy 각 4) = 72 bytes
# 실제: float×14 + int32×1 + uint32×2 + float×1 = 18필드 × 4bytes
RECEIVE_FFT_FEATURES_TOTAL_SIZE:int = 21 * 4  # 84 bytes

class UartCommandType(enum.IntEnum):
    """PC → ESP32 명령 타입 (ESP32 펌웨어의 CommandType_t와 동일)
    
    기존 데이터 타입(0x00~0x09)과 충돌하지 않도록 0x10부터 시작
    """
    CMD_SET_TP1         = cfg.CMD_SETTING_TP1        # TP1 임계값 설정 (payload: uint16_t, 2 bytes)
    CMD_SET_TP2         = cfg.CMD_SETTING_TP2        # TP2 카운트 설정 (payload: uint64_t, 8 bytes)
    CMD_SET_TP1_RECHECK = cfg.CMD_SETTTING_TP1_RECHECK  # TP1 Recheck 임계값 설정 (payload: uint16_t, 2 bytes)
    CMD_SET_FFT_STRIDE  = cfg.CMD_SET_FFT_STRIDE     # FFT Stride 설정 (payload: uint16_t, 2 bytes)
    CMD_SET_LED_MAX_PER = cfg.CMD_SET_LED_MAX_PER    # LED 최대 밝기 (payload: uint8_t, 0~100 %)
    CMD_SET_LED_MIN_PER = cfg.CMD_SET_LED_MIN_PER    # LED 최소 밝기 (payload: uint8_t, 0~100 %)
    CMD_SET_LED_DIM_PER = cfg.CMD_SET_LED_DIM_PER    # LED 디밍 밝기 (payload: uint8_t, 0~100 %)
    CMD_SET_LED_WORK_MS = cfg.CMD_SET_LED_WORK_MS    # LED 점등 유지 시간 (payload: uint32_t LE, ms)
    CMD_SET_LED_STEP_MS = cfg.CMD_SET_LED_STEP_MS    # LED 디밍 스텝 시간 (payload: uint32_t LE, ms)
    CMD_SET_LED_DELAY_MS= cfg.CMD_SET_LED_DELAY_MS   # LED 디밍 딜레이 시간 (payload: uint32_t LE, ms)
    CMD_SET_OCCU_TIMEOUT= cfg.CMD_SET_OCCU_TIMEOUT   # 재실 확인 타임아웃 (payload: uint32_t LE, 초)
    CMD_SET_SLEEP_TIME  = cfg.CMD_SET_SLEEP_TIME     # 슬립 시간 (payload: uint32_t LE, 초)
    CMD_SET_LED_ONOFF          = cfg.CMD_SET_LED_ONOFF          # LED ON/OFF (payload: uint8_t, 0=OFF 1=ON)
    CMD_SET_MLP_FLOAT_ENABLE   = cfg.CMD_SET_MLP_FLOAT_ENABLE   # Float32 MLP ON/OFF (payload: uint8_t)
    CMD_SET_MLP_INT8_ENABLE    = cfg.CMD_SET_MLP_INT8_ENABLE    # Int8 MLP ON/OFF (payload: uint8_t)
    CMD_GET_SETTINGS    = cfg.CMD_GET_SETTINGS       # 현재 설정값 요청 (payload: 없음)
    CMD_SAVE_NVS        = cfg.CMD_SAVE_NVS           # 현재 설정을 NVS에 저장 (payload: 없음)
    CMD_RESET           = cfg.CMD_RESET              # ESP32 소프트 리셋 (payload: 없음)



