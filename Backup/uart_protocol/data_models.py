"""
데이터 모델 정의

UART 프레임 및 센서 데이터 구조
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any
from datetime import datetime


@dataclass
class UartFrame:
    """
    UART 프레임 데이터 모델
    
    멀티바이트 STX/ETX 프레임 구조:
    | STX(3) | DATA_TYPE | DATA_LENGTH | PAYLOAD | CHECKSUM | ETX(3) |
    """
    stx: bytes                  # AA 55 CC (3 bytes)
    data_type: int              # 0~9 (UartDataType)
    data_length: int            # 페이로드 길이 (Little Endian)
    payload: bytes              # 실제 데이터
    checksum: int               # Sum 체크섬 (Little Endian)
    etx: bytes                  # DD 55 AA (3 bytes)
    
    # 메타데이터
    timestamp: datetime = field(default_factory=datetime.now)
    is_valid: bool = True       # 체크섬 검증 결과
    error_message: Optional[str] = None
    
    def __repr__(self) -> str:
        return (
            f"UartFrame("
            f"type={self.data_type}, "
            f"length={self.data_length}, "
            f"valid={self.is_valid}, "
            f"time={self.timestamp.strftime('%H:%M:%S.%f')[:-3]}"
            f")"
        )


@dataclass
class SensorData:
    """
    파싱된 센서 데이터
    
    데이터 타입에 따라 다른 필드가 채워짐
    """
    data_type: int
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 버퍼 데이터 (uint16 or float32)
    adc_buffer: Optional[List[int]] = None              # 타입 0 (RAW)
    voltage_buffer: Optional[List[int]] = None          # 타입 1 (Voltage)
    adc_hpf_buffer: Optional[List[float]] = None        # 타입 2 (SW HPF 적용값)
    hpf_buffer: Optional[List[float]] = None            # 타입 2 별칭 (하위 호환성)
    adc_bpf_buffer: Optional[List[float]] = None        # 타입 3 (SW BPF 적용값)
    hw_hpf_buffer: Optional[List[int]] = None           # 타입 4 (HW HPF RAW)
    hw_bpf_buffer: Optional[List[int]] = None           # 타입 5 (HW BPF RAW)
    # 델타 버퍼 및 Occupancy 버퍼는 비활성화됨
    # adc_delta_buffer: Optional[List[int]] = None      # (비활성화)
    # voltage_delta_buffer: Optional[List[int]] = None  # (비활성화)
    # hpf_delta_buffer: Optional[List[float]] = None    # (비활성화)
    # occupancy_buffer: Optional[List[bool]] = None     # (비활성화)
    
    # 설정 데이터 (타입 6)
    settings: Optional['SettingsData'] = None
    
    # 통합 데이터 (타입 7)
    all_buffers: Optional[dict] = None

    
    # 원본 프레임 참조
    raw_frame: Optional[UartFrame] = None
    
    def __repr__(self) -> str:
        from uart_protocol.protocol_config import get_data_type_name
        data_name = get_data_type_name(self.data_type)
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
    - TP1: uint16 (2 bytes)
    - TP1_RECHECK: uint16 (2 bytes)
    - TP2: uint64 (8 bytes)
    - LED_MAX: uint8 (1 byte)
    - LED_MIN: uint8 (1 byte)
    - LED_DIMMING: uint8 (1 byte)
    - LED_DIMMING_STEP_TIME_MS: uint32 (4 bytes)
    - LED_DIMMING_WORK_TIME_MS: uint32 (4 bytes)
    - LED_DIMMING_DELAY_TIME_MS: uint32 (4 bytes)
    - OCCU_TO: uint64 (8 bytes)
    - SLEEP: uint64 (8 bytes)
    - OCCUPANCY: bool (1 byte)
    - PIR_OUTPUT: bool (1 byte)
    """
    tp1: int                            # uint16 (occupancy)
    tp1_recheck: int                    # uint16 (recheck)
    tp2: int                            # uint64
    led_max_percentage: int             # uint8
    led_min_percentage: int             # uint8
    led_dimming_percentage: int         # uint8
    led_dimming_step_time_ms: int       # uint32
    led_dimming_work_time_ms: int       # uint32
    led_dimming_delay_time_ms: int      # uint32
    occupancy_timeout_us: int           # uint64
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
            f"STEP={self.led_dimming_step_time_ms}ms, "
            f"WORK={self.led_dimming_work_time_ms}ms, "
            f"DELAY={self.led_dimming_delay_time_ms}ms, "
            f"OCCUPANCY={'재실' if self.occupancy else '없음'}, "
            f"PIR={'ON' if self.pir_output else 'OFF'}"
            f")"
        )


@dataclass
class ParserState:
    """
    프레임 파서 상태
    """
    # 통계
    total_frames: int = 0
    valid_frames: int = 0
    invalid_frames: int = 0
    checksum_errors: int = 0
    sync_errors: int = 0
    
    # 최근 프레임
    last_frame: Optional[UartFrame] = None
    last_valid_time: Optional[datetime] = None
    last_error_time: Optional[datetime] = None
    
    def success_rate(self) -> float:
        """체크섬 검증 성공률 반환 (0.0 ~ 1.0)"""
        if self.total_frames == 0:
            return 0.0
        return self.valid_frames / self.total_frames
    
    def __repr__(self) -> str:
        return (
            f"ParserState("
            f"total={self.total_frames}, "
            f"valid={self.valid_frames}, "
            f"invalid={self.invalid_frames}, "
            f"rate={self.success_rate():.1%}"
            f")"
        )
