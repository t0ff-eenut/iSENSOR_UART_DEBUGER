
WINDOW_TITLE        = 'iSENSOR PIR SENSOR DEBUG'
WINDOW_POSITION_X   = 100
WINDOW_POSITION_Y   = 100
WINDOW_WIDTH        = 1200
WINDOW_HEIGHT       = 800
LEFT_BOX_WIDTH      = 400

# from typing import Final
# # 멀티바이트 프레임 구분자 (데이터 충돌 방지)
# # Final == 상수 (재할당이 발생하면 경고/오류)
# START_SIGNAL: Final[bytes] = bytes([0xAA, 0x55, 0xCC])
# END_SIGNAL: Final[bytes] = bytes([0xDD, 0x55, 0xAA])
# START_SIGNAL_SIZE: Final[int] = 3
# END_SIGNAL_SIZE: Final[int] = 3

START_SIGNAL        = [0xAA, 0x55, 0xCC]
END_SIGNAL          = [0xDD, 0x55, 0xAA]
START_SIGNAL_SIZE   = 3
END_SIGNAL_SIZE     = 3

CMD_SETTING_TP1             = 0x10  # TP1 임계값 설정 (payload: uint16_t, 2 bytes)
CMD_SETTING_TP2             = 0x11  # TP2 카운트 설정 (payload: uint64_t, 8 bytes)
CMD_SETTTING_TP1_RECHECK    = 0x12  # TP1 Recheck 임계값 설정 (payload: uint16_t, 2 bytes)
CMD_GET_SETTINGS            = 0x20  # 현재 설정값 요청 (payload: 없음)
CMD_SAVE_NVS                = 0x30  # 현재 설정을 NVS에 저장 (payload: 없음)
CMD_RESET                   = 0xF0  # ESP32 소프트 리셋 (payload: 없음)