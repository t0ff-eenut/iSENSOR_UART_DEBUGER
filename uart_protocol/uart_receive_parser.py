# """
# STX/ETX 프레임 파서 (멀티바이트 패턴) - 디버그 버전

# 상태 머신 기반 UART 프레임 파싱
# """

# from enum import IntEnum, auto
# from typing import Optional, Tuple
# from uart_protocol.protocol_config import (
#     RECEIVE_STX, upcfg.UART_RECEIVE_ETX_PATTERN, upcfg.RECEIVE_STX_LENGTH, upcfg.UART_RECEIVE_ETX_SIZE,
#     RECEIVE_HEADER_LENGTH, FRAME_OVERHEAD_SIZE,
#     RECEIVE_MAX_PAYLOAD_LENGTH, get_data_type_name
# )
# from uart_protocol.data_models import UartFrame, ParserState
# from uart_protocol.checksum import calculate_checksum, verify_checksum
# from utils.byte_converter import bytes_to_uint16_le

# # 디버그 플래그
# DEBUG_PARSER = False  # ★ 디버그 비활성화

import enum

import config                               as cfg
import endian_converter                     as econv
import uart_protocol.uart_protocol_config   as upcfg
import uart_protocol.data_models            as updm
import uart_protocol.checksum               as upc



# class enum_parse_state(enum.IntEnum):
class enum_parse_state(enum.IntEnum):
    """프레임 파서 상태"""
    WAIT_STX        = enum.auto()   # STX 대기 (3 bytes)
    READ_HEADER     = enum.auto()   # 헤더 읽기 (data_type, data_length)
    READ_PAYLOAD    = enum.auto()   # 페이로드 읽기
    READ_CHECKSUM   = enum.auto()   # 체크섬 읽기
    READ_ETX        = enum.auto()   # ETX 읽기 (3 bytes)
    FRAME_COMPLETE  = enum.auto()   # 프레임 완성

DEBUG_PARSER = False  # ★ 디버그 비활성화

class UartReceiveParser:
    """
    멀티바이트 STX/ETX 기반 UART 프레임 파서
    """
    
    def __init__(self):
        self.enum_parse_state:enum_parse_state      = enum_parse_state.WAIT_STX
        self.A_receive_byte_buffer:bytearray        = bytearray()
        # self.ParserState_handle:updm.ParserState    = updm.ParserState()
        
        # 현재 파싱 중인 프레임 정보
        # self.receive_stx: Optional[bytes] = None
        # self.receive_data_type: Optional[int] = None
        # self.receive_data_length: Optional[int] = None
        # self.receive_payload: Optional[bytes] = None
        # self.receive_checksum: Optional[int] = None
        self.receive_stx:bytes          = None
        self.receive_data_type:bytes    = None
        self.receive_data_length:bytes  = None
        self.receive_payload:bytes      = None
        self.receive_checksum:bytes     = None
        self.receive_etx:bytes          = None

        
    def reset(self):
        """파서 상태 초기화"""
        self.enum_parse_state = enum_parse_state.WAIT_STX
        self.A_receive_byte_buffer.clear()
        self.receive_stx:bytes          = None
        self.receive_data_type:bytes    = None
        self.receive_data_length:bytes  = None
        self.receive_payload:bytes      = None
        self.receive_checksum:bytes     = None
        self.receive_etx:bytes          = None
    
    # def feed_byte(self, byte: int) -> Optional[UartFrame]:
    def feed_byte(self, input_i_byte:int) -> Optional[UartFrame]: # UartFrame 객체 또는 None을 반환

        # print(f"frame_parser.py | feed_byte() | input_i_byte : {input_i_byte}")   # frame_parser.py | input_i_byte : 192

        """바이트를 파서에 공급"""
        self.A_receive_byte_buffer.append(input_i_byte)
        # print(f"frame_parser.py | feed_byte() | self.A_receive_byte_buffer : {self.A_receive_byte_buffer}")   # frame_parser.py | input_i_byte : 192
        # print(f"frame_parser.py | feed_byte() | self.enum_parse_state : {self.enum_parse_state}")   # frame_parser.py | input_i_byte : 192

        if self.enum_parse_state == enum_parse_state.WAIT_STX:
            return self.parse_stx()
        elif self.enum_parse_state == enum_parse_state.READ_HEADER:
            return self.parse_header()
        elif self.enum_parse_state == enum_parse_state.READ_PAYLOAD:
            return self.parse_payload()
        elif self.enum_parse_state == enum_parse_state.READ_CHECKSUM:
            return self.parse_checksum()
        elif self.enum_parse_state == enum_parse_state.READ_ETX:
            return self.parse_etx()
        
        return None
    
    def parse_stx(self):
        """STX 패턴 파싱 (3 bytes)"""
        while len(self.A_receive_byte_buffer) >= upcfg.RECEIVE_STX_LENGTH:
            if bytes(self.A_receive_byte_buffer[:upcfg.RECEIVE_STX_LENGTH]) == bytes(upcfg.RECEIVE_STX):
                
                # print(f"frame_parser.py | parse_stx() | bytes(self.A_receive_byte_buffer[:upcfg.RECEIVE_STX_LENGTH]) : {bytes(self.A_receive_byte_buffer[:upcfg.RECEIVE_STX_LENGTH])}")   # 
                # print(f"frame_parser.py | parse_stx() | bytes(upcfg.RECEIVE_STX) : {bytes(upcfg.RECEIVE_STX)}")

                self.receive_stx = bytes(self.A_receive_byte_buffer[:upcfg.RECEIVE_STX_LENGTH])
                self.enum_parse_state = enum_parse_state.READ_HEADER

                # self.ParserState_handle.i_stx_found_count += 1
                # if DEBUG_PARSER and self.stx_found_count <= 5:
                #     print(f"\n[DEBUG] STX 발견! (#{self.stx_found_count})")
                # print(f"frame_parser.py | parse_stx() | STX 발견! (#{self.ParserState_handle.i_stx_found_count}번째)")

                # 왜 여기선 pop을 안하지?

                return None # 다음 단계를 위한 return

            else:
                # self.ParserState_handle.i_sync_errors += 1
                self.A_receive_byte_buffer.pop(0)
                # print(f"frame_parser.py | parse_stx() | self.ParserState_handle.i_sync_errors : {self.ParserState_handle.i_sync_errors}")

        return None # buffer 내용이 부족한 경우 return
        
    
    def parse_header(self):

        """헤더 파싱 (STX(3) + data_type + data_length)"""
        if len(self.A_receive_byte_buffer) < upcfg.RECEIVE_HEADER_LENGTH:
            # buffer 내용이 부족한 경우 return
            # print(f"frame_parser.py | parse_header() | read byte")
            return None
        
        # self.receive_data_type = self.A_receive_byte_buffer[upcfg.RECEIVE_STX_LENGTH]    # DATA_TYPE
        self.receive_data_type = bytes(self.A_receive_byte_buffer[upcfg.RECEIVE_STX_LENGTH])    # DATA_TYPE

        i_data_length_start = upcfg.RECEIVE_STX_LENGTH + upcfg.RECEIVE_DATA_TYPE_LENGTH
        i_data_length_end = i_data_length_start + upcfg.RECEIVE_DATA_TYPE_SIZE_LENGTH
        # little edian 
        self.receive_data_length = econv.bytes_to_uint16_le(bytes(self.A_receive_byte_buffer[i_data_length_start:i_data_length_end]))
        # print(f"frame_parser.py | parse_header() | self.receive_data_length : {self.receive_data_length}")

        # self.ParserState_handle.i_header_parsed_count += 1
        # if DEBUG_PARSER and updm.i_header_parsed_count <= 5:
        #     print(f"[DEBUG] 헤더 파싱: type={self.receive_data_type}, length={self.receive_data_length}")
        # print(f"frame_parser.py | parse_header() | 헤더 파싱: type={self.receive_data_type}, length={self.receive_data_length}")
        
        if self.receive_data_length > upcfg.RECEIVE_MAX_PAYLOAD_LENGTH:
            # if DEBUG_PARSER:
            #     print(f"[DEBUG] ❌ 페이로드 크기 초과: {self.receive_data_length} > {RECEIVE_MAX_PAYLOAD_LENGTH}")
            print(f"frame_parser.py | parse_header() | ❌ 페이로드 크기 초과: {self.receive_data_length} > {upcfg.RECEIVE_MAX_PAYLOAD_LENGTH}")
            # self.ParserState_handle.i_sync_errors += 1
            self.reset()
            return None
        
        self.enum_parse_state = enum_parse_state.READ_PAYLOAD

        return None
    
    def parse_payload(self):
        """페이로드 파싱"""
        expected_length = upcfg.RECEIVE_HEADER_LENGTH + self.receive_data_length
        if len(self.A_receive_byte_buffer) < expected_length:
            return None
        
        i_payload_start = upcfg.RECEIVE_HEADER_LENGTH
        i_payload_end = i_payload_start + self.receive_data_length
        self.receive_payload = bytes(self.A_receive_byte_buffer[i_payload_start:i_payload_end])
        
        self.enum_parse_state = enum_parse_state.READ_CHECKSUM
        return None
    
    def parse_checksum(self):
        """체크섬 파싱"""
        expected_length = upcfg.RECEIVE_HEADER_LENGTH + self.receive_data_length + 2
        
        if len(self.A_receive_byte_buffer) < expected_length:
            return None
        
        checksum_pos = upcfg.RECEIVE_HEADER_LENGTH + self.receive_data_length
        i_checksum_start = upcfg.RECEIVE_HEADER_LENGTH + self.receive_data_length
        i_checksum_end = i_checksum_start + self.receive_checksum
        self.receive_checksum = econv.bytes_to_uint16_le(bytes(self.A_receive_byte_buffer[i_checksum_start:i_checksum_end]))
        
        self.enum_parse_state = enum_parse_state.READ_ETX
        return None
    
    def parse_etx(self) -> UartFrame:
        """ETX 패턴 파싱 및 프레임 완성 (3 bytes)"""
        expected_length = upcfg.RECEIVE_HEADER_LENGTH + self.receive_data_length + 2 + upcfg.UART_RECEIVE_ETX_SIZE
        
        if len(self.A_receive_byte_buffer) < expected_length:
            return None
        
        # self.etx_check_count += 1
        # self.ParserState_handle.i_etx_check_count += 1

        etx_pos = upcfg.RECEIVE_HEADER_LENGTH + self.receive_data_length + 2
        self.receive_etx = bytes(self.A_receive_byte_buffer[etx_pos:etx_pos+upcfg.UART_RECEIVE_ETX_SIZE])
        
        # if DEBUG_PARSER and self.etx_check_count <= 5:
        # print(f"[DEBUG] ETX 체크 #{self.etx_check_count}:")
        print(f"frame_parser.py | parse_etx() | 예상 ETX 위치: {etx_pos}")
        print(f"frame_parser.py | parse_etx() | 수신된 ETX: {self.receive_etx.hex().upper()}")
        
        # print(f"  기대 ETX: {upcfg.UART_RECEIVE_ETX_PATTERN.hex().upper()}")
        print(f"frame_parser.py | parse_etx() | 기대 ETX: {bytes(upcfg.UART_RECEIVE_ETX_PATTERN).hex().upper()}")

        
        # if self.receive_etx != upcfg.UART_RECEIVE_ETX_PATTERN:
        if self.receive_etx != bytes(upcfg.UART_RECEIVE_ETX_PATTERN):
            # if DEBUG_PARSER and self.etx_check_count <= 5:
            print(f"frame_parser.py | parse_etx() | ❌ ETX 불일치!")
            # self.ParserState_handle.i_sync_errors += 1
            self.reset()
            return None
        
        # 체크섬 검증
        receive_data = bytes(self.A_receive_byte_buffer[0:upcfg.RECEIVE_HEADER_LENGTH + self.receive_data_length])
        is_valid = upc.verify_checksum(receive_data, self.receive_checksum)
        
        # if DEBUG_PARSER:
        print(f"frame_parser.py | parse_etx() | ✓ 프레임 완성! 체크섬: {'OK' if is_valid else 'FAIL'}")
        

        # self.reset()
        # return None
    
        receive_data = updm.UartReceiveData(
            stx=self.receive_stx,
            data_type=self.receive_data_type,
            data_length=self.receive_data_length,
            payload=self.receive_payload,
            checksum=self.receive_checksum,
            etx=self.receive_etx,

            is_valid=is_valid,
            error_message=None if is_valid else "Checksum mismatch"
        )
        
        # self.ParserState_handle.total_frames += 1
        # if is_valid:
        #     self.ParserState_handle.valid_frames += 1
        #     self.ParserState_handle.last_valid_time = receive_data.timestamp
        # else:
        #     self.ParserState_handle.invalid_frames += 1
        #     self.ParserState_handle.checksum_errors += 1
        #     self.ParserState_handle.last_error_time = receive_data.timestamp
        
        # self.ParserState_handle.last_frame = receive_data

        self.reset()
        
        return receive_data
    
#     def parse_bytes(self, data: bytes) -> list[UartFrame]:
#         """바이트 스트림을 파싱하여 프레임 리스트 반환"""
#         frames = []
#         for byte in data:
#             frame = self.feed_byte(byte)
#             if frame is not None:
#                 frames.append(frame)
#         return frames
    
#     def get_stats(self) -> ParserState:
#         """파서 통계 반환"""
#         return self.ParserState_handle
    
#     def print_stats(self):
#         """파서 통계 출력"""
#         print(f"\n{'='*50}")
#         print(f"Frame Parser Statistics")
#         print(f"{'='*50}")
#         print(f"Total Frames:      {self.ParserState_handle.total_frames}")
#         print(f"Valid Frames:      {self.ParserState_handle.valid_frames}")
#         print(f"Invalid Frames:    {self.ParserState_handle.invalid_frames}")
#         print(f"Checksum Errors:   {self.ParserState_handle.checksum_errors}")
#         print(f"Sync Errors:       {self.ParserState_handle.i_sync_errors}")
#         print(f"Success Rate:      {self.ParserState_handle.success_rate():.1%}")
#         print(f"{'='*50}")
#         if DEBUG_PARSER:
#             print(f"[DEBUG] STX Found:     {self.stx_found_count}")
#             print(f"[DEBUG] Header Parsed: {self.header_parsed_count}")
#             print(f"[DEBUG] ETX Checked:   {self.etx_check_count}")
#             print(f"{'='*50}")
