"""
STX/ETX 프레임 파서 (멀티바이트 패턴) - 디버그 버전

상태 머신 기반 UART 프레임 파싱
"""

from enum import IntEnum, auto
from typing import Optional, Tuple
from uart_protocol.protocol_config import (
    STX_PATTERN, ETX_PATTERN, STX_SIZE, ETX_SIZE,
    FRAME_HEADER_SIZE, FRAME_OVERHEAD_SIZE,
    MAX_PAYLOAD_SIZE, get_data_type_name
)
from uart_protocol.data_models import UartFrame, ParserState
from uart_protocol.checksum import calculate_checksum, verify_checksum
from utils.byte_converter import bytes_to_uint16_le

# 디버그 플래그
DEBUG_PARSER = False  # ★ 디버그 비활성화


class ParseState(IntEnum):
    """프레임 파서 상태"""
    WAIT_STX = auto()           # STX 대기 (3 bytes)
    READ_HEADER = auto()        # 헤더 읽기 (data_type, data_length)
    READ_PAYLOAD = auto()       # 페이로드 읽기
    READ_CHECKSUM = auto()      # 체크섬 읽기
    READ_ETX = auto()           # ETX 읽기 (3 bytes)
    FRAME_COMPLETE = auto()     # 프레임 완성


class FrameParser:
    """
    멀티바이트 STX/ETX 기반 UART 프레임 파서
    """
    
    def __init__(self):
        self.state = ParseState.WAIT_STX
        self.buffer = bytearray()
        self.stats = ParserState()
        
        # 현재 파싱 중인 프레임 정보
        self.current_stx: Optional[bytes] = None
        self.current_data_type: Optional[int] = None
        self.current_data_length: Optional[int] = None
        self.current_payload: Optional[bytes] = None
        self.current_checksum: Optional[int] = None
        
        # 디버그용 카운터
        self.stx_found_count = 0
        self.header_parsed_count = 0
        self.etx_check_count = 0
        
    def reset(self):
        """파서 상태 초기화"""
        self.state = ParseState.WAIT_STX
        self.buffer.clear()
        self.current_stx = None
        self.current_data_type = None
        self.current_data_length = None
        self.current_payload = None
        self.current_checksum = None
    
    def feed_byte(self, byte: int) -> Optional[UartFrame]:
        """바이트를 파서에 공급"""
        self.buffer.append(byte)
        
        if self.state == ParseState.WAIT_STX:
            return self._parse_stx()
        elif self.state == ParseState.READ_HEADER:
            return self._parse_header()
        elif self.state == ParseState.READ_PAYLOAD:
            return self._parse_payload()
        elif self.state == ParseState.READ_CHECKSUM:
            return self._parse_checksum()
        elif self.state == ParseState.READ_ETX:
            return self._parse_etx()
        
        return None
    
    def _parse_stx(self) -> Optional[UartFrame]:
        """STX 패턴 파싱 (3 bytes)"""
        while len(self.buffer) >= STX_SIZE:
            if bytes(self.buffer[:STX_SIZE]) == STX_PATTERN:
                self.current_stx = STX_PATTERN
                self.state = ParseState.READ_HEADER
                self.stx_found_count += 1
                if DEBUG_PARSER and self.stx_found_count <= 5:
                    print(f"\n[DEBUG] STX 발견! (#{self.stx_found_count})")
                return None
            else:
                self.stats.sync_errors += 1
                self.buffer.pop(0)
        return None
    
    def _parse_header(self) -> Optional[UartFrame]:
        """헤더 파싱 (STX(3) + data_type + data_length)"""
        if len(self.buffer) < FRAME_HEADER_SIZE:
            return None
        
        self.current_data_type = self.buffer[STX_SIZE]
        length_start = STX_SIZE + 1
        self.current_data_length = bytes_to_uint16_le(bytes(self.buffer[length_start:length_start+2]))
        
        self.header_parsed_count += 1
        if DEBUG_PARSER and self.header_parsed_count <= 5:
            print(f"[DEBUG] 헤더 파싱: type={self.current_data_type}, length={self.current_data_length}")
        
        if self.current_data_length > MAX_PAYLOAD_SIZE:
            if DEBUG_PARSER:
                print(f"[DEBUG] ❌ 페이로드 크기 초과: {self.current_data_length} > {MAX_PAYLOAD_SIZE}")
            self.stats.sync_errors += 1
            self.reset()
            return None
        
        self.state = ParseState.READ_PAYLOAD
        return None
    
    def _parse_payload(self) -> Optional[UartFrame]:
        """페이로드 파싱"""
        expected_length = FRAME_HEADER_SIZE + self.current_data_length
        
        if len(self.buffer) < expected_length:
            return None
        
        payload_start = FRAME_HEADER_SIZE
        payload_end = payload_start + self.current_data_length
        self.current_payload = bytes(self.buffer[payload_start:payload_end])
        
        self.state = ParseState.READ_CHECKSUM
        return None
    
    def _parse_checksum(self) -> Optional[UartFrame]:
        """체크섬 파싱"""
        expected_length = FRAME_HEADER_SIZE + self.current_data_length + 2
        
        if len(self.buffer) < expected_length:
            return None
        
        checksum_pos = FRAME_HEADER_SIZE + self.current_data_length
        self.current_checksum = bytes_to_uint16_le(bytes(self.buffer[checksum_pos:checksum_pos+2]))
        
        self.state = ParseState.READ_ETX
        return None
    
    def _parse_etx(self) -> Optional[UartFrame]:
        """ETX 패턴 파싱 및 프레임 완성 (3 bytes)"""
        expected_length = FRAME_HEADER_SIZE + self.current_data_length + 2 + ETX_SIZE
        
        if len(self.buffer) < expected_length:
            return None
        
        self.etx_check_count += 1
        
        etx_pos = FRAME_HEADER_SIZE + self.current_data_length + 2
        received_etx = bytes(self.buffer[etx_pos:etx_pos+ETX_SIZE])
        
        if DEBUG_PARSER and self.etx_check_count <= 5:
            print(f"[DEBUG] ETX 체크 #{self.etx_check_count}:")
            print(f"  예상 ETX 위치: {etx_pos}")
            print(f"  수신된 ETX: {received_etx.hex().upper()}")
            print(f"  기대 ETX: {ETX_PATTERN.hex().upper()}")
        
        if received_etx != ETX_PATTERN:
            if DEBUG_PARSER and self.etx_check_count <= 5:
                print(f"[DEBUG] ❌ ETX 불일치!")
            self.stats.sync_errors += 1
            self.reset()
            return None
        
        # 체크섬 검증
        checksum_data = bytes(self.buffer[0:FRAME_HEADER_SIZE + self.current_data_length])
        is_valid = verify_checksum(checksum_data, self.current_checksum)
        
        if DEBUG_PARSER:
            print(f"[DEBUG] ✓ 프레임 완성! 체크섬: {'OK' if is_valid else 'FAIL'}")
        
        frame = UartFrame(
            stx=self.current_stx,
            data_type=self.current_data_type,
            data_length=self.current_data_length,
            payload=self.current_payload,
            checksum=self.current_checksum,
            etx=received_etx,
            is_valid=is_valid,
            error_message=None if is_valid else "Checksum mismatch"
        )
        
        self.stats.total_frames += 1
        if is_valid:
            self.stats.valid_frames += 1
            self.stats.last_valid_time = frame.timestamp
        else:
            self.stats.invalid_frames += 1
            self.stats.checksum_errors += 1
            self.stats.last_error_time = frame.timestamp
        
        self.stats.last_frame = frame
        self.reset()
        
        return frame
    
    def parse_bytes(self, data: bytes) -> list[UartFrame]:
        """바이트 스트림을 파싱하여 프레임 리스트 반환"""
        frames = []
        for byte in data:
            frame = self.feed_byte(byte)
            if frame is not None:
                frames.append(frame)
        return frames
    
    def get_stats(self) -> ParserState:
        """파서 통계 반환"""
        return self.stats
    
    def print_stats(self):
        """파서 통계 출력"""
        print(f"\n{'='*50}")
        print(f"Frame Parser Statistics")
        print(f"{'='*50}")
        print(f"Total Frames:      {self.stats.total_frames}")
        print(f"Valid Frames:      {self.stats.valid_frames}")
        print(f"Invalid Frames:    {self.stats.invalid_frames}")
        print(f"Checksum Errors:   {self.stats.checksum_errors}")
        print(f"Sync Errors:       {self.stats.sync_errors}")
        print(f"Success Rate:      {self.stats.success_rate():.1%}")
        print(f"{'='*50}")
        if DEBUG_PARSER:
            print(f"[DEBUG] STX Found:     {self.stx_found_count}")
            print(f"[DEBUG] Header Parsed: {self.header_parsed_count}")
            print(f"[DEBUG] ETX Checked:   {self.etx_check_count}")
            print(f"{'='*50}")
