"""
데이터 모델 정의

UART 프레임 및 센서 데이터 구조
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any
from datetime import datetime

import uart_protocol.data_models            as updm

# class UartDataType(enum.IntEnum):
#     RAW_VALUE = 0                # UART_TX_ADC_RAW_VALUE
#     ADC_BUFFER = 1               # UART_TX_ADC_RAW_BUFFER
#     VOLTAGE_BUFFER = 2           # UART_TX_ADC_RAW_VOLTAGE_BUFFER
#     ADC_HPF_BUFFER = 3        # UART_TX_ADC_SW_HPF_BUFFER
#     ADC_BPF_BUFFER = 4        # UART_TX_ADC_SW_BPF_BUFFER
#     HPF_BUFFER = 5               # UART_TX_HPF_BUFFER
#     HPF_VOLTAGE_BUFFER = 6       # UART_TX_HPF_VOLTAGE_BUFFER
#     BPF_BUFFER = 7               # UART_TX_BPF_BUFFER
#     BPF_VOLTAGE_BUFFER = 8       # UART_TX_BPF_VOLTAGE_BUFFER
#     SETTINGS = 9                 # UART_TX_SETTINGS
#     ALL_DATA = 10                # UART_TX_ALL_DATA

@dataclass
class UartReceiveData:
    """
    UART Receive Data Frame Model

    멀티바이트 STX/ETX 프레임 구조:
    | STX(3) | DATA_TYPE | DATA_LENGTH | DATA | CHECKSUM | ETX(3) |

    uart_receive_parser.py
    data_parser.py
    """
    bytes_stx:bytes           # AA 55 CC (3 bytes)
    bytes_data_type:bytes     # 0~9 (UartDataType)
    bytes_data_length:bytes   # 데이터 길이 (Little Endian)
    bytes_data:bytes          # 실제 데이터
    bytes_checksum:bytes      # Sum 체크섬 (Little Endian)
    bytes_etx:bytes           # DD 55 AA (3 bytes)
    

    # 메타데이터
    b_chksum_pass:bool = True       # 체크섬 검증 결과
    timestamp:datetime = field(default_factory=datetime.now)
    error_message:Optional[str] = None
    
    def __repr__(self) -> str:
        return (
            f"UartFrame("
            f"type={self.bytes_data_type}, "
            f"length={self.bytes_data_length}, "
            f"chksum pass={self.b_chksum_pass}, "
            #f"time={self.timestamp.strftime('%H:%M:%S.%f')[:-3]}"
            f")"
        )

import uart_protocol.uart_protocol_config   as upcfg
@dataclass
class SensorData:
    """
    파싱된 센서 데이터
    
    데이터 타입에 따라 다른 필드가 채워짐
    """

    # 원본 프레임 참조
    UartFrame_raw:updm.UartFrame = None
    i_data_type:int = 0

    i_adc_raw:int   = 0
    # 버퍼 데이터 (uint16 or float32)
    adc_buffer: Optional[List[int]] = None              # 타입 0 (RAW)
    # voltage_buffer: Optional[List[int]] = None          # 타입 1 (Voltage)
    # adc_hpf_buffer: Optional[List[float]] = None        # 타입 2 (SW HPF 적용값)
    # hpf_buffer: Optional[List[float]] = None            # 타입 2 별칭 (하위 호환성)
    # adc_bpf_buffer: Optional[List[float]] = None        # 타입 3 (SW BPF 적용값)
    # hw_hpf_buffer: Optional[List[int]] = None           # 타입 4 (HW HPF RAW)
    # hw_bpf_buffer: Optional[List[int]] = None           # 타입 5 (HW BPF RAW)
    # 델타 버퍼 및 Occupancy 버퍼는 비활성화됨
    # adc_delta_buffer: Optional[List[int]] = None      # (비활성화)
    # voltage_delta_buffer: Optional[List[int]] = None  # (비활성화)
    # hpf_delta_buffer: Optional[List[float]] = None    # (비활성화)
    # occupancy_buffer: Optional[List[bool]] = None     # (비활성화)
    
    # 설정 데이터 (타입 6)
    settings: Optional['SettingsData'] = None
    # settings: Optional[parse_settings] = None
    
    
    # # 통합 데이터 (타입 7)
    # all_buffers: Optional[dict] = None


    timestamp:datetime = field(default_factory=datetime.now)
    

    
    def __repr__(self) -> str:
        data_name = upcfg.get_data_type_name(self.i_data_type)
        return (
            f"SensorData("
            f"type={data_name}, "
            f"time={self.timestamp.strftime('%H:%M:%S.%f')[:-3]}"
            f")"
        )


@dataclass
class SettingsData:
    """
    설정값 데이터 (타입 7)
    
    총 45 bytes:
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
    """
    tp1: int                            # uint16 (occupancy)
    tp1_recheck: int                    # uint16 (recheck)
    tp2: int                            # uint64
    led_max_percentage: int             # uint8
    led_min_percentage: int             # uint8
    led_dimming_percentage: int         # uint8
    led_dimming_work_time_ms: int       # uint32
    led_dimming_step_time_ms: int       # uint32
    led_dimming_delay_time_ms: int      # uint32
    occupancy_check_timeout_us: int     # uint64
    sleep_time: int                     # uint64
    occupancy: bool = False             # bool (재실 여부)
    pir_output: bool = False            # bool (PIR 출력)
    
    def __repr__(self) -> str:
        return (
            f"SettingsData("
            f"TP1={self.tp1}, "
            f"TP1_RECHECK={self.tp1_recheck}, "
            f"TP2={self.tp2}, "
            f"LED={self.led_max_percentage}/{self.led_min_percentage}/{self.led_dimming_percentage}%, "
            f"WORK={self.led_dimming_work_time_ms}ms, "
            f"STEP={self.led_dimming_step_time_ms}ms, "
            f"DELAY={self.led_dimming_delay_time_ms}ms, "
            f"OCCUPANCY={'재실' if self.occupancy else '없음'}, "
            f"PIR={'ON' if self.pir_output else 'OFF'}"
            f")"
        )


# @dataclass
class ParserState:


    def __init__(self):
        """
        프레임 파서 상태
        """
        # 통계
        self.i_sync_errors:int       = 0
        self.i_stx_found_count:int   = 0

        self.total_frames:int        = 0
        self.valid_frames:int        = 0
        self.invalid_frames:int      = 0
        self.checksum_errors:int     = 0
        
        
        # 디버그용 카운터
        # self.stx_found_count        = 0
        self.i_header_parsed_count    = 0
        self.i_etx_check_count        = 0

        # # 최근 프레임
        # self.last_frame: Optional[UartFrame] = None
        # self.last_valid_time: Optional[datetime] = None
        # self.last_error_time: Optional[datetime] = None

    # """
    # 프레임 파서 상태
    # """
    # # 통계
    # i_sync_errors:int       = 0
    # i_stx_found_count:int   = 0

    # total_frames:int        = 0
    # valid_frames:int        = 0
    # invalid_frames:int      = 0
    # checksum_errors:int     = 0
    
    
    #     # # 디버그용 카운터
    #     # self.stx_found_count        = 0
    #     # self.header_parsed_count    = 0
    #     # self.etx_check_count        = 0

    # # 최근 프레임
    # last_frame: Optional[UartFrame] = None
    # last_valid_time: Optional[datetime] = None
    # last_error_time: Optional[datetime] = None
    
    # def success_rate(self) -> float:
    #     """체크섬 검증 성공률 반환 (0.0 ~ 1.0)"""
    #     if self.total_frames == 0:
    #         return 0.0
    #     return self.valid_frames / self.total_frames
    
    # def __repr__(self) -> str:
    #     return (
    #         f"ParserState("
    #         f"total={self.total_frames}, "
    #         f"valid={self.valid_frames}, "
    #         f"invalid={self.invalid_frames}, "
    #         f"rate={self.success_rate():.1%}"
    #         f")"
    #     )
