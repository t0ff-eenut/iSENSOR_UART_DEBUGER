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
    settings:Optional['SettingsData'] = None
    # settings: Optional[parse_settings] = None
    
    # 프로파일링 데이터 (타입 11)
    profiling:Optional['ProfilingData'] = None
    # FFT 진폭 데이터 (타입 12)
    fft_result:Optional['FftData'] = None
    # FFT 특징값 데이터 (타입 13)
    fft_features:Optional['FftFeaturesData'] = None
    # MLP 추론 결과 (타입 14)
    mlp_result:Optional['MlpResultData'] = None
    # MLP 추론 결과 (타입 14)
    mlp_result:Optional['MlpResultData'] = None
    
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
    i_fft_stride:int = 32              # uint16 (FFT stride, default=32)
    
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
    ESP32 실행 시간 프로파일링 데이터 (타입 11)

    페이로드 레이아웃 (Big Endian, 36 bytes: 9 x uint32_t)
    펌웨어 UART_TX_PROFILING case 필드 순서와 동일:
    | 필드                              | 크기 | 설명                        |
    |----------------------------------|------|-----------------------------|
    | adc_reading_time_us              | 4    | ADC Read 시작~끝 (µs)        |
    | adc_read_buffer_latency_time_us  | 4    | ADC 확인~Process 시작 (µs)   |
    | adc_processing_time_us           | 4    | ADC Process 시작~끝 (µs)     |
    | adc_buffer_insert_time_us        | 4    | Mode ADC 버퍼 입력 (µs)      |
    | fft_process_time_us              | 4    | FFT Process 시작~끝 (µs)     |
    | fft_features_process_time_us     | 4    | FFT 특징 추출 시작~끝 (µs)   |
    | fft_loop_a_time_us               | 4    | FFT 루프 A 시간 (µs)          |
    | fft_loop_b_time_us               | 4    | FFT 루프 B 시간 (µs)          |
    | fft_loop_c_time_us               | 4    | FFT 루프 C 시간 (µs)          |
    """
    adc_reading_time_us:int              = 0
    adc_read_buffer_latency_time_us:int  = 0
    adc_processing_time_us:int           = 0
    adc_buffer_insert_time_us:int        = 0
    fft_process_time_us:int              = 0
    fft_features_process_time_us:int     = 0
    fft_loop_a_time_us:int               = 0
    fft_loop_b_time_us:int               = 0
    fft_loop_c_time_us:int               = 0
    float32_mlp_infer_time_us:int        = 0
    int8_mlp_infer_time_us:int           = 0

    def __repr__(self) -> str:
        return (
            f"\nProfilingData(\n"
            f"  adc_reading              = {self.adc_reading_time_us} µs\n"
            f"  adc_read_buf_latency     = {self.adc_read_buffer_latency_time_us} µs\n"
            f"  adc_processing           = {self.adc_processing_time_us} µs\n"
            f"  adc_buffer_insert        = {self.adc_buffer_insert_time_us} µs\n"
            f"  fft_process              = {self.fft_process_time_us} µs\n"
            f"  fft_features_process     = {self.fft_features_process_time_us} µs\n"
            f"  fft_loop_a               = {self.fft_loop_a_time_us} µs\n"
            f"  fft_loop_b               = {self.fft_loop_b_time_us} µs\n"
            f"  fft_loop_c               = {self.fft_loop_c_time_us} µs\n"
            f"  float32_mlp_infer        = {self.float32_mlp_infer_time_us} µs\n"
            f"  int8_mlp_infer           = {self.int8_mlp_infer_time_us} µs\n"
            f")"
        )


@dataclass
class MlpResultData:
    """
    ESP32 MLP 추론 결과 (타입 14)

    페이로드 레이아웃 (Big Endian, 16 bytes):
    | 필드         | 크기 | 설명                              |
    |-------------|------|----------------------------------|
    | float_label | 4   | int32 BE  float MLP 클래스 (0=배경, 1=사람) |
    | float_prob  | 4   | float32 BE  float MLP 확률 (0.0~1.0) |
    | int_label   | 4   | int32 BE  int8 MLP 클래스 (0=배경, 1=사람) |
    | int_prob    | 4   | float32 BE  int8 MLP 확률 (0.0~1.0) |
    """
    i_float_label: int   = 0    # float MLP: 0=배경, 1=사람
    f_float_prob:  float = 0.0  # float MLP: 추론 확률 (0.0~1.0)
    i_int_label:   int   = 0    # int8 MLP: 0=배경, 1=사람
    f_int_prob:    float = 0.0  # int8 MLP: 추론 확률 (0.0~1.0)

    def __repr__(self) -> str:
        float_lbl = "사람" if self.i_float_label == 1 else "배경"
        int_lbl   = "사람" if self.i_int_label   == 1 else "배경"
        return (
            f"\nMlpResultData(\n"
            f"  float: {self.i_float_label} ({float_lbl})  prob={self.f_float_prob:.4f}\n"
            f"  int8 : {self.i_int_label}   ({int_lbl})  prob={self.f_int_prob:.4f}\n"
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


@dataclass
class FftFeaturesData:
    """
    FFT 특징값 데이터 (타입 13)

    페이로드 레이아웃 (Big Endian, 84 bytes: 21 필드 × 4 bytes)
    펌웨어 UART_TX_FFT_FEATURES case 직렬화 순서와 동일:
    | 시퀀스 | 필드명                  | 타입   | 설명                       |
    |--------|------------------------|--------|----------------------------|
    |  0     | f_spectral_rolloff     | float  | 스펙트럼 롤오프 (Hz)        |
    |  1     | f_spectral_bandwidth   | float  | 스펙트럼 대역폭 (Hz)        |
    |  2     | i_peak_count           | int32  | 피크 빈 개수                |
    |  3     | f_mid_ratio            | float  | 중주파(5~10Hz) 비율         |
    |  4     | f_low_to_high_ratio    | float  | 저/고주파 에너지 비율       |
    |  5     | f_second_peak_freq     | float  | 2번째 피크 주파수 (Hz)      |
    |  6     | f_kurtosis             | float  | 첨도                        |
    |  7     | f_centroid             | float  | 스펙트럼 무게중심 주파수 (Hz)|
    |  8     | f_peak_freq            | float  | 1번째 피크 주파수 (Hz)      |
    |  9     | f_low_ratio            | float  | 저주파(0~5Hz) 비율          |
    | 10     | f_rms                  | float  | RMS 진폭                    |
    | 11     | ui32_avg_energy        | uint32 | 평균 에너지 (정수)           |
    | 12     | ui32_peak_energy       | uint32 | 피크 에너지 (정수)           |
    | 13     | f_energy_variance      | float  | 에너지 분산                 |
    | 14     | f_peak_to_avg_e        | float  | 피크/평균 에너지 비율        |
    | 15     | f_high_ratio           | float  | 고주파(10Hz+) 비율          |
    | 16     | f_peak1_to_peak2_ratio | float  | 1위 vs 2위 피크 비율        |
    | 17     | f_skewness             | float  | 왜도                        |
    | 18     | f_dc_ratio             | float  | DC 에너지 비율              |
    | 19     | f_delta_peak_freq      | float  | 프레임 간 피크 주파수 변화량   |
    | 20     | f_spectral_flatness    | float  | 스펙트럼 평탄도             |
    """
    f_spectral_rolloff:float     = 0.0
    f_spectral_bandwidth:float   = 0.0
    i_peak_count:int             = 0
    f_mid_ratio:float            = 0.0
    f_low_to_high_ratio:float    = 0.0
    f_second_peak_freq:float     = 0.0
    f_kurtosis:float             = 0.0
    f_centroid:float             = 0.0
    f_peak_freq:float            = 0.0
    f_low_ratio:float            = 0.0
    f_rms:float                  = 0.0
    ui32_avg_energy:int          = 0
    ui32_peak_energy:int         = 0
    f_energy_variance:float      = 0.0
    f_peak_to_avg_e:float        = 0.0
    f_high_ratio:float           = 0.0
    f_peak1_to_peak2_ratio:float = 0.0
    f_skewness:float             = 0.0
    f_dc_ratio:float             = 0.0
    f_delta_peak_freq:float      = 0.0
    f_spectral_flatness:float    = 0.0

    def __repr__(self) -> str:
        return (
            f"\nFftFeaturesData(\n"
            f"  rolloff          = {self.f_spectral_rolloff:.4f} Hz\n"
            f"  bandwidth        = {self.f_spectral_bandwidth:.4f} Hz\n"
            f"  peak_count       = {self.i_peak_count}\n"
            f"  mid_ratio        = {self.f_mid_ratio:.4f}\n"
            f"  low_to_high      = {self.f_low_to_high_ratio:.4f}\n"
            f"  second_peak_freq = {self.f_second_peak_freq:.4f} Hz\n"
            f"  kurtosis         = {self.f_kurtosis:.4f}\n"
            f"  centroid         = {self.f_centroid:.4f} Hz\n"
            f"  peak_freq        = {self.f_peak_freq:.4f} Hz\n"
            f"  low_ratio        = {self.f_low_ratio:.4f}\n"
            f"  rms              = {self.f_rms:.6f}\n"
            f"  avg_energy       = {self.ui32_avg_energy}\n"
            f"  peak_energy      = {self.ui32_peak_energy}\n"
            f"  energy_variance  = {self.f_energy_variance:.4f}\n"
            f"  peak_to_avg_e    = {self.f_peak_to_avg_e:.4f}\n"
            f"  high_ratio       = {self.f_high_ratio:.4f}\n"
            f"  peak1_to_peak2   = {self.f_peak1_to_peak2_ratio:.4f}\n"
            f"  skewness         = {self.f_skewness:.4f}\n"
            f"  dc_ratio         = {self.f_dc_ratio:.4f}\n"
            f"  delta_peak_freq  = {self.f_delta_peak_freq:.4f} Hz\n"
            f"  spectral_flatness= {self.f_spectral_flatness:.4f}\n"
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
