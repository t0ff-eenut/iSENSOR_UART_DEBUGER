"""
데이터 모델 정의

UART 프레임 및 센서 데이터 구조
"""

from dataclasses import dataclass,field
from typing import Optional,List,Any
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
            f"\nUartReceiveData(\n"
            f"bytes_stx\t={self.bytes_stx},\n"
            f"bytes_data_type\t={self.bytes_data_type},\n"
            f"bytes_data_length\t={self.bytes_data_length},\n"
            f"bytes_data\t={self.bytes_data},\n"
            f"bytes_checksum\t={self.bytes_checksum},\n"
            f"bytes_etx\t={self.bytes_etx},\n"
            f"b_chksum_pass\t={self.b_chksum_pass},\n"
            f"timestamp\t={self.timestamp.strftime('%H:%M:%S.%f')[:-3]},\n"
            f"error_message\t={self.error_message},\n"
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
    UartReceiveData_raw:updm.UartReceiveData = None
    i_data_type:int = 0
    i_adc_raw:int   = 0
    # 버퍼 데이터 (uint16 or float32)
    A_adc_buffer:Optional[List[int]] = None              # 타입 0 (RAW)
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
    settings:Optional[SettingsData] = None
    # settings: Optional[parse_settings] = None
    
    # 프로파일링 데이터 (타입 11)
    profiling:Optional['ProfilingData'] = None
    # FFT 진폭 데이터 (타입 12)
    fft_result:Optional['FftData'] = None
    
    # # 통합 데이터 (타입 7)
    # all_buffers: Optional[dict] = None


    timestamp:datetime = field(default_factory=datetime.now)
    

    
    def __repr__(self) -> str:
        # data_name = upcfg.get_data_type_name(self.i_data_type)
        return (
            f"\nSensorData(\n"
            f"UartReceiveData_raw={self.UartReceiveData_raw},\n"
            f"i_data_type={self.i_data_type},\n"
            f"i_adc_raw={self.i_adc_raw},\n"
            f"A_adc_buffer={self.A_adc_buffer},\n"
            f"settings={self.settings},\n"
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
    i_tp1:int = 0                      # uint16 (occupancy)
    i_tp1_recheck:int = 0              # uint16 (recheck)
    i_tp2:int = 0                      # uint64
    i_led_max_per:int = 0              # uint8
    i_led_min_per:int = 0              # uint8
    i_led_dim_per:int = 0              # uint8
    i_led_work_ms:int = 0              # uint32
    i_led_step_ms:int = 0              # uint32
    i_led_delay_ms:int = 0             # uint32
    i_occu_chk_timeout_us:int = 0         # uint64
    i_sleep_time_us:int = 0               # uint64
    b_occu_status:bool = False         # bool (재실 여부)
    b_pir_status:bool = False          # bool (PIR 출력)
    
    def __repr__(self) -> str:
        return (
            f"\nSettingsData("
            f"TP1={self.i_tp1},\n"
            f"TP1_RECHECK={self.i_tp1_recheck},\n"
            f"TP2={self.i_tp2},\n"
            f"LED={self.i_led_max_per}/{self.i_led_min_per}/{self.i_led_dim_per}%,\n"
            f"WORK={self.i_led_work_ms}ms,\n"
            f"STEP={self.i_led_step_ms}ms,\n"
            f"DELAY={self.i_led_delay_ms}ms,\n"
            f"OCCU_CHK_TIME={self.i_occu_chk_timeout_us}ms,\n"
            f"SELLP_TIME={self.i_sleep_time_us}ms,\n"
            f"OCCUPANCY={'재실' if self.b_occu_status else '없음'},\n"
            f"PIR={'ON' if self.b_pir_status else 'OFF'}"
            f")"
        )


@dataclass
class ProfilingData:
    """
    ESP32 실행 시간 및 Task 스택 사용량 프로파일링 데이터 (타입 11)

    페이로드 레이아웃 (Big Endian, 28 bytes: 7 x uint32_t):
    | 필드                    | 크기 | 설명                              |
    |------------------------|------|----------------------------------|
    | adc_process_time_us    | 4    | ADC 큐 수신~버퍼 저장 처리 시간 (µs) |
    | algo_process_time_us   | 4    | TP1/TP2 알고리즘 실행 시간 (µs)     |
    | loop_period_us         | 4    | 배경 스레드 루프 주기 (µs)           |
    | bg_stack_hwm           | 4    | 배경 Task 스택 고수위 (words)        |
    | main_stack_hwm         | 4    | Main Task 스택 고수위 (words)       |
    | uart_tx_stack_hwm      | 4    | UART TX Task 스택 고수위 (words)    |
    | uart_rx_stack_hwm      | 4    | UART RX Task 스택 고수위 (words)    |
    """
    adc_process_time_us:int   = 0   # ADC 큐 수신 ~ 버퍼 저장 처리 시간 (µs)
    algo_process_time_us:int  = 0   # TP1/TP2 알고리즘 실행 시간 (µs)
    loop_period_us:int        = 0   # 배경 스레드 루프 주기 (µs)
    bg_stack_hwm:int          = 0   # 배경 Task 스택 고수위 (words)
    main_stack_hwm:int        = 0   # Main Task 스택 고수위 (words)
    uart_tx_stack_hwm:int     = 0   # UART TX Task 스택 고수위 (words)
    uart_rx_stack_hwm:int     = 0   # UART RX Task 스택 고수위 (words)
    fft_process_time_us:int   = 0   # FFT 실행 시간 (µs)
    feat_process_time_us:int  = 0   # 특징 추출 실행 시간 (µs)

    def __repr__(self) -> str:
        return (
            f"\nProfilingData(\n"
            f"  adc_process  = {self.adc_process_time_us} µs\n"
            f"  algo_process = {self.algo_process_time_us} µs\n"
            f"  loop_period  = {self.loop_period_us} µs  ({self.loop_period_us/1000:.2f} ms)\n"
            f"  bg_stack_hwm      = {self.bg_stack_hwm} words\n"
            f"  main_stack_hwm    = {self.main_stack_hwm} words\n"
            f"  uart_tx_stack_hwm = {self.uart_tx_stack_hwm} words\n"
            f"  uart_rx_stack_hwm = {self.uart_rx_stack_hwm} words\n"
            f"  fft_process_time  = {self.fft_process_time_us} µs\n"
            f"  feat_process_time = {self.feat_process_time_us} µs\n"
            f")"
        )


@dataclass
class FftData:
    """
    FFT 에너지 스펙트럼 데이터 (타입 12)

    페이로드 레이아웃 (Big Endian, FFT_OUTPUT_SIZE x 4 bytes):
    | 필드      | 크기 | 설명                              |
    |----------|------|----------------------------------|
    | energies | 516  | 129 x uint32 BE  re²+im² (sc16²) |

    주파수 매핑: freq[k] = k × SAMPLING_FREQ / WINDOW_SIZE
    예) k=1 → 100/256 ≈ 0.39Hz, k=50 → 50×100/256 ≈ 19.5Hz

    magnitudes: PC에서 sqrt(energy) × FFT_SC16_SCALE × (2/N 또는 1/N) 복원
    """
    energies:   List[int]   = field(default_factory=list)   # uint32 re²+im² (129개)
    magnitudes: List[float] = field(default_factory=list)   # sqrt 복원 ADC 단위 (129개)

    def __repr__(self) -> str:
        peak_idx = max(range(len(self.magnitudes)), key=lambda i: self.magnitudes[i]) if self.magnitudes else -1
        return (
            f"\nFftData(\n"
            f"  count       = {len(self.energies)}\n"
            f"  peak_idx    = {peak_idx}\n"
            f"  peak_mag    = {self.magnitudes[peak_idx]:.4f if self.magnitudes else 0}\n"
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
    #         f"total={self.total_frames},\n"
    #         f"valid={self.valid_frames},\n"
    #         f"invalid={self.invalid_frames},\n"
    #         f"rate={self.success_rate():.1%}"
    #         f")"
    #     )
