
WINDOW_TITLE:str        = 'iSENSOR PIR SENSOR DEBUG'
WINDOW_POSITION_X:int   = 100
WINDOW_POSITION_Y:int   = 100
WINDOW_WIDTH:int        = 1200
WINDOW_HEIGHT:int       = 800
LEFT_BOX_WIDTH:int      = 400


BACKGROUND_COLOR:str    = "#003D83"
LINE_COLOR:str          = "#7F7F7F"
TEXT_COLOR:str          = "#FFFFFF"
# LINE_RADIUS         = 6

# cfg.BACKGROUND_COLOR
# cfg.LINE_COLOR
# cfg.TEXT_COLOR
ADC_RAW_LINE_COLOR:str  = "#059200"
ADC_FFT_LINE_COLOR:str  = "#eeff00"


# ax = 0 → 텍스트의 왼쪽이 pos에 정렬,
# ax = 1 → 텍스트의 오른쪽이 pos에 정렬,
# ay = 0 → 텍스트의 위쪽이 pos에 정렬,
# ay = 1 → 텍스트의 아래쪽이 pos에 정렬.
ADC_LABEL_NAME:str          = 'adc_graph_value_info'
ADC_LABEL_ANCHOR_X:int      = 1 
ADC_LABEL_ANCHOR_Y:int      = 0
ADC_LABEL_COLOR:str         = "#898989"

TP1_LINE_NAME:str       = 'TP1_line_name'
TP1_COLOR:str           = "#FF0000"
TP1_RCK_LINE_NAME:str   = 'TP1_rck_line_name'
TP1_RCK_COLOR:str       = "#FFA500"

TP1_POINT_NAME:str      = 'TP1_scatter_name'
TP1_POINT_COLOR:str     = "#FF0000"
TP1_RCK_POINT_NAME:str  = 'TP1_RCK_scatter_name'
TP1_RCK_POINT_COLOR:str = "#FFA500"



FFT_LABEL_NAME:str          = 'fft_graph_value_info'
FFT_LABEL_ANCHOR_X:int      = 1 
FFT_LABEL_ANCHOR_Y:int      = 0
FFT_LABEL_COLOR:str         = "#898989"

FFT_SAMPLING_RATE           = 100

MAX_LOG_LINES:int           = 500

# from typing import Final
# # 멀티바이트 프레임 구분자 (데이터 충돌 방지)
# # Final == 상수 (재할당이 발생하면 경고/오류)
# START_SIGNAL: Final[bytes] = bytes([0xAA, 0x55, 0xCC])
# END_SIGNAL: Final[bytes] = bytes([0xDD, 0x55, 0xAA])
# START_SIGNAL_SIZE: Final[int] = 3
# END_SIGNAL_SIZE: Final[int] = 3

UART_RECEIVE_START_PATTERN:bytes         = [0xAA, 0x55, 0xCC]
# UART_RECEIVE_START_SIGNAL_SIZE:int   = 3
# UART_RECEIVE_START_SIGNAL_SIZE:int   = len(UART_RECEIVE_START_SIGNAL)
UART_RECEIVE_END_PATTERN:bytes           = [0xDD, 0x55, 0xAA]
# UART_RECEIVE_END_SIGNAL_SIZE:int     = 3
# UART_RECEIVE_END_SIGNAL_SIZE:int     = len(UART_RECEIVE_END_SIGNAL)

UART_RECEIVE_DATA_TYPE_BYTESIZE:int     = 1
UART_RECEIVE_DATA_LENGTH_BYTESIZE:int   = 2
UART_RECEIVE_MAX_PAYLOAD_BYTESIZE:int   = 1500
UART_RECEIVE_CHECKSUM_BYTESIZE:int      = 2

# custom_esp_uart_thread.c
UART_RECEIVE_SETTINGS_TP1_BYTESIZE:int              = 2 # uint16 (TP1)
UART_RECEIVE_SETTINGS_TP1_RECHECK_BYTESIZE:int      = 2 # uint16 (RECHECK_TP1)
UART_RECEIVE_SETTINGS_TP2_BYTESIZE:int              = 8 # uint64

UART_RECEIVE_SETTINGS_LED_MAX_PER_BYTESIZE:int      = 1 # uint8
UART_RECEIVE_SETTINGS_LED_MIN_PER_BYTESIZE:int      = 1 # uint8
UART_RECEIVE_SETTINGS_LED_DIM_PER_BYTESIZE:int      = 1 # uint8

# WORK_MS / STEP_MS = DIM LEVEL
# LED ON TIME = WORK_MS + DELAY_MS + WORK_MS
UART_RECEIVE_SETTINGS_LED_WORK_MS_BYTESIZE:int      = 4 # uint32
UART_RECEIVE_SETTINGS_LED_STEP_MS_BYTESIZE:int      = 4 # uint32
UART_RECEIVE_SETTINGS_LED_DELAY_MS_BYTESIZE:int     = 4 # uint32

UART_RECEIVE_SETTINGS_OCCU_CHK_TIMEOUT_BYTESIZE:int = 8 # uint64
UART_RECEIVE_SETTINGS_SLEEP_TIME_BYTESIZE:int       = 8 # uint64

UART_RECEIVE_SETTINGS_OCCUPANCY_STATUS_BYTESIZE:int = 1 # bool
UART_RECEIVE_SETTINGS_PIR_STATUS_BYTESIZE:int       = 1 # bool


CMD_SETTING_TP1:int           = 0x10  # TP1 임계값 설정 (payload: uint16_t, 2 bytes)
CMD_SETTING_TP2:int           = 0x11  # TP2 카운트 설정 (payload: uint64_t, 8 bytes)
CMD_SETTTING_TP1_RECHECK:int  = 0x12  # TP1 Recheck 임계값 설정 (payload: uint16_t, 2 bytes)
CMD_GET_SETTINGS:int          = 0x20  # 현재 설정값 요청 (payload: 없음)
CMD_SAVE_NVS:int              = 0x30  # 현재 설정을 NVS에 저장 (payload: 없음)
CMD_RESET:int                 = 0xF0  # ESP32 소프트 리셋 (payload: 없음)