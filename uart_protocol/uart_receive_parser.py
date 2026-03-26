# """
# STX/ETX 프레임 파서 (멀티바이트 패턴) - 디버그 버전

# 상태 머신 기반 UART 프레임 파싱
# """

# from enum import IntEnum, auto
# from typing import Optional, Tuple
# from uart_protocol.protocol_config import (
#     UART_RECEIVE_STX_PATTERN, upcfg.UART_RECEIVE_ETX_PATTERN, upcfg.RECEIVE_STX_LENGTH, upcfg.UART_RECEIVE_ETX_SIZE,
#     RECEIVE_HEADER_LENGTH, FRAME_OVERHEAD_SIZE,
#     RECEIVE_MAX_PAYLOAD_LENGTH, get_data_type_name
# )
# from uart_protocol.data_models import UartFrame, ParserState
# from uart_protocol.checksum import calculate_checksum, verify_checksum
# from utils.byte_converter import bytes_to_uint16_le

# # 디버그 플래그
# DEBUG_PARSER = False  # ★ 디버그 비활성화
from typing import List, Optional
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
    READ_DATA       = enum.auto()   # 데이턴 읽기
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
        # self.bytes_receive_stx: Optional[bytes] = None
        # self.bytes_receive_data_type: Optional[int] = None
        # self.bytes_receive_data_length: Optional[int] = None
        # self.bytes_receive_data: Optional[bytes] = None
        # self.bytes_receive_checksum: Optional[int] = None
        self.bytes_receive_stx:bytes            = None
        self.bytes_receive_data_type:bytes      = None
        self.bytes_receive_data_length:bytes    = None
        self.bytes_receive_data:bytes           = None
        self.bytes_receive_checksum:bytes       = None
        self.bytes_receive_etx:bytes            = None

        self.b_chksum_pass:bool                 = False

        
    def reset(self):
        """파서 상태 초기화"""
        self.enum_parse_state = enum_parse_state.WAIT_STX
        self.A_receive_byte_buffer.clear()
        self.bytes_receive_stx:bytes            = None
        self.bytes_receive_data_type:bytes      = None
        self.bytes_receive_data_length:bytes    = None
        self.bytes_receive_data:bytes           = None
        self.bytes_receive_checksum:bytes       = None
        self.bytes_receive_etx:bytes            = None
        
        self.b_chksum_pass:bool                 = False
    
    # def feed_byte(self, byte: int) -> Optional[UartFrame]:
    def feed_byte(self, input_i_byte:int) -> Optional[updm.UartReceiveData]: # UartFrame 객체 또는 None을 반환

        # print(f"uart_receive_parser.py | feed_byte() | input_i_byte : {input_i_byte}")   # uart_receive_parser.py | input_i_byte : 192

        """바이트를 파서에 공급"""
        self.A_receive_byte_buffer.append(input_i_byte)
        # print(f"uart_receive_parser.py | feed_byte() | self.A_receive_byte_buffer : {self.A_receive_byte_buffer}")   # uart_receive_parser.py | input_i_byte : 192
        # print(f"uart_receive_parser.py | feed_byte() | self.enum_parse_state : {self.enum_parse_state}")   # uart_receive_parser.py | input_i_byte : 192

        if self.enum_parse_state == enum_parse_state.WAIT_STX:
            return self.parse_stx()
        elif self.enum_parse_state == enum_parse_state.READ_HEADER:
            return self.parse_header()
        elif self.enum_parse_state == enum_parse_state.READ_DATA:
            return self.parse_data()
        elif self.enum_parse_state == enum_parse_state.READ_CHECKSUM:
            return self.parse_checksum()
        elif self.enum_parse_state == enum_parse_state.READ_ETX:
            return self.parse_etx()
        
        return None
    
    def parse_stx(self) -> None:
        """STX 패턴 파싱 (3 bytes)"""
        while len(self.A_receive_byte_buffer) >= upcfg.RECEIVE_STX_LENGTH:
            if bytes(self.A_receive_byte_buffer[:upcfg.RECEIVE_STX_LENGTH]) == bytes(upcfg.UART_RECEIVE_STX_PATTERN):
                
                # print(f"uart_receive_parser.py | parse_stx() | bytes(self.A_receive_byte_buffer[:upcfg.RECEIVE_STX_LENGTH]) : {bytes(self.A_receive_byte_buffer[:upcfg.RECEIVE_STX_LENGTH])}")   # 
                # print(f"uart_receive_parser.py | parse_stx() | bytes(upcfg.UART_RECEIVE_STX_PATTERN) : {bytes(upcfg.UART_RECEIVE_STX_PATTERN)}")

                self.bytes_receive_stx = bytes(self.A_receive_byte_buffer[:upcfg.RECEIVE_STX_LENGTH])
                self.enum_parse_state = enum_parse_state.READ_HEADER

                # self.ParserState_handle.i_stx_found_count += 1
                # if DEBUG_PARSER and self.stx_found_count <= 5:
                #     print(f"\n[DEBUG] STX 발견! (#{self.stx_found_count})")
                # print(f"uart_receive_parser.py | parse_stx() | STX 발견! (#{self.ParserState_handle.i_stx_found_count}번째)")

                # 왜 여기선 pop을 안하지?

                return None # 다음 단계를 위한 return

            else:
                # self.ParserState_handle.i_sync_errors += 1
                self.A_receive_byte_buffer.pop(0)
                # print(f"uart_receive_parser.py | parse_stx() | self.ParserState_handle.i_sync_errors : {self.ParserState_handle.i_sync_errors}")

        return None # buffer 내용이 부족한 경우 return
        
    
    def parse_header(self) -> None:

        """헤더 파싱 (STX(3) + data_type + data_length)"""
        if len(self.A_receive_byte_buffer) < upcfg.RECEIVE_HEADER_LENGTH:
            # buffer 내용이 부족한 경우 return
            # print(f"uart_receive_parser.py | parse_header() | read byte")
            return None
        
        # self.bytes_receive_data_type = self.A_receive_byte_buffer[upcfg.RECEIVE_STX_LENGTH]    # DATA_TYPE
        # print(f"uart_receive_parser.py | parse_header() | self.A_receive_byte_buffer[upcfg.RECEIVE_STX_LENGTH] : {self.A_receive_byte_buffer[upcfg.RECEIVE_STX_LENGTH]}")
        # self.bytes_receive_data_type = bytes(self.A_receive_byte_buffer[upcfg.RECEIVE_STX_LENGTH])    # DATA_TYPE
        # print(f"uart_receive_parser.py | parse_header() | self.bytes_receive_data_type : {self.bytes_receive_data_type}")
        # self.bytes_receive_data_type = econv.bytes_to_uint64_le(self.bytes_receive_data_type)
        # print(f"uart_receive_parser.py | parse_header() | self.bytes_receive_data_type : {self.bytes_receive_data_type}")

        self.bytes_receive_data_type = self.A_receive_byte_buffer[upcfg.RECEIVE_STX_LENGTH]    # DATA_TYPE

        i_data_length_start = upcfg.RECEIVE_STX_LENGTH + upcfg.RECEIVE_DATA_TYPE_LENGTH
        i_data_length_end = i_data_length_start + upcfg.RECEIVE_DATA_TYPE_SIZE_LENGTH
        # little edian 
        self.bytes_receive_data_length = econv.bytes_to_uint16_le(bytes(self.A_receive_byte_buffer[i_data_length_start:i_data_length_end]))
        # print(f"uart_receive_parser.py | parse_header() | self.bytes_receive_data_length : {self.bytes_receive_data_length}")

        # self.ParserState_handle.i_header_parsed_count += 1
        # if DEBUG_PARSER and updm.i_header_parsed_count <= 5:
        #     print(f"[DEBUG] 헤더 파싱: type={self.bytes_receive_data_type}, length={self.bytes_receive_data_length}")
        # print(f"uart_receive_parser.py | parse_header() | 헤더 파싱: type={self.bytes_receive_data_type}, length={self.bytes_receive_data_length}")
        
        if self.bytes_receive_data_length > upcfg.RECEIVE_MAX_PAYLOAD_LENGTH:
            # if DEBUG_PARSER:
            #     print(f"[DEBUG] ❌ 페이로드 크기 초과: {self.bytes_receive_data_length} > {RECEIVE_MAX_PAYLOAD_LENGTH}")
            print(f"uart_receive_parser.py | parse_header() | ❌ 페이로드 크기 초과: {self.bytes_receive_data_length} > {upcfg.RECEIVE_MAX_PAYLOAD_LENGTH}")
            # self.ParserState_handle.i_sync_errors += 1
            self.reset()
            return None
        
        self.enum_parse_state = enum_parse_state.READ_DATA

        return None
    
    def parse_data(self) -> None:        
        """data 파싱 (STX(3) + data_type + data_length + data)"""
        if len(self.A_receive_byte_buffer) < upcfg.RECEIVE_HEADER_LENGTH + self.bytes_receive_data_length:
            # buffer 내용이 부족한 경우 return
            # print(f"uart_receive_parser.py | parse_header() | read byte")
            return None


        i_data_start = upcfg.RECEIVE_HEADER_LENGTH
        i_data_end = i_data_start + self.bytes_receive_data_length
        self.bytes_receive_data = bytes(self.A_receive_byte_buffer[i_data_start:i_data_end])
        
        self.enum_parse_state = enum_parse_state.READ_CHECKSUM
        return None
    
    def parse_checksum(self) -> None:
        """체크섬 파싱 (STX(3) + data_type + data_length + data + checksum)"""
        if len(self.A_receive_byte_buffer) < upcfg.RECEIVE_HEADER_LENGTH + self.bytes_receive_data_length + upcfg.RECEIVE_CHECKSUM_LENGTH:
            return None
        
        # checksum_pos = upcfg.RECEIVE_HEADER_LENGTH + self.bytes_receive_data_length
        i_checksum_start = upcfg.RECEIVE_HEADER_LENGTH + self.bytes_receive_data_length
        i_checksum_end = i_checksum_start + upcfg.RECEIVE_CHECKSUM_LENGTH
        self.bytes_receive_checksum = econv.bytes_to_uint16_le(bytes(self.A_receive_byte_buffer[i_checksum_start:i_checksum_end]))
        
        self.enum_parse_state = enum_parse_state.READ_ETX
        return None
    
    def parse_etx(self) -> Optional[updm.UartFrame]:
        """ETX 패턴 파싱 및 프레임 완성 (3 bytes)"""
        if len(self.A_receive_byte_buffer) < upcfg.RECEIVE_HEADER_LENGTH + self.bytes_receive_data_length + upcfg.RECEIVE_CHECKSUM_LENGTH + upcfg.UART_RECEIVE_ETX_SIZE:
            return None

        # etx_pos = upcfg.RECEIVE_HEADER_LENGTH + self.bytes_receive_data_length + 2
        i_etx_start = upcfg.RECEIVE_HEADER_LENGTH + self.bytes_receive_data_length + upcfg.RECEIVE_CHECKSUM_LENGTH
        i_etx_end = i_etx_start + upcfg.UART_RECEIVE_ETX_SIZE
        self.bytes_receive_etx = bytes(self.A_receive_byte_buffer[i_etx_start:i_etx_end])
        
        # if DEBUG_PARSER and self.etx_check_count <= 5:
        # print(f"[DEBUG] ETX 체크 #{self.etx_check_count}:")
        # print(f"uart_receive_parser.py | parse_etx() | 예상 ETX 위치: {i_etx_start}")
        # print(f"uart_receive_parser.py | parse_etx() | 수신된 ETX: {self.bytes_receive_etx.hex().upper()}")
        # print(f"uart_receive_parser.py | parse_etx() | 기대 ETX: {bytes(upcfg.UART_RECEIVE_ETX_PATTERN).hex().upper()}")

        
        # if self.bytes_receive_etx != upcfg.UART_RECEIVE_ETX_PATTERN:
        if self.bytes_receive_etx != bytes(upcfg.UART_RECEIVE_ETX_PATTERN):
            # if DEBUG_PARSER and self.etx_check_count <= 5:
            print(f"uart_receive_parser.py | parse_etx() | ❌ ETX 불일치!")
            # self.ParserState_handle.i_sync_errors += 1
            self.reset()
            return None
        
        # 체크섬 검증
        receive_data = bytes(self.A_receive_byte_buffer[0:upcfg.RECEIVE_HEADER_LENGTH + self.bytes_receive_data_length])
        self.b_chksum_pass = upc.verify_checksum(receive_data, self.bytes_receive_checksum)
        
        # if DEBUG_PARSER:
        # print(f"uart_receive_parser.py | parse_etx() | ✓ 프레임 완성! 체크섬: {'OK' if self.b_chksum_pass else 'FAIL'}")
        

        # self.reset()
        # return None
    
        receive_data = updm.UartReceiveData(
            bytes_stx=self.bytes_receive_stx,
            bytes_data_type=self.bytes_receive_data_type,
            bytes_data_length=self.bytes_receive_data_length,
            bytes_data=self.bytes_receive_data,
            bytes_checksum=self.bytes_receive_checksum,
            bytes_etx=self.bytes_receive_etx,

            b_chksum_pass=self.b_chksum_pass,

            error_message=None if self.b_chksum_pass else "Checksum mismatch"
        )
        
        # self.ParserState_handle.total_frames += 1
        # if self.b_chksum_pass:
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
