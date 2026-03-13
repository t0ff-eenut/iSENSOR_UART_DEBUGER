"""
UART Command Sender - PC → ESP32 명령 전송 모듈

ESP32 디바이스에 명령을 전송하기 위한 프레임 생성 및 송신 기능
"""

from typing import Final
import serial
# import protocol_config

# from .protocol_config import (
#     STX_PATTERN,
#     ETX_PATTERN,
#     UartCommandType,
# )

class CommandSender:
    """PC → ESP32 UART 명령 송신 클래스"""
    
    def __init__(self, input_serial_port:serial.Serial = None):   # 기대값 serial.Serial
        """
        Args:
            serial_port: 이미 열린 시리얼 포트 객체 (선택)
        """
        self.serial_port = input_serial_port
    
    # def set_serial(self, serial_port: serial.Serial):
    #     """시리얼 포트 설정"""
    #     self.serial_port = serial_port
    
    # def calculate_checksum(self, data: bytes) -> int:
    #     """체크섬 계산 (Sum 방식, 16bit)
        
    #     Args:
    #         data: STX부터 PAYLOAD 끝까지의 데이터
            
    #     Returns:
    #         16bit 체크섬 값
    #     """
    #     return sum(data) & 0xFFFF
    
    # def build_frame(self, cmd_type: UartCommandType, payload: bytes = b'') -> bytes:
    #     """명령 프레임 생성
        
    #     프레임 구조:
    #     [STX:3] [CMD:1] [LEN:2] [PAYLOAD:N] [CHECKSUM:2] [ETX:3]
        
    #     Args:
    #         cmd_type: 명령 타입 (UartCommandType)
    #         payload: 페이로드 데이터 (bytes)
            
    #     Returns:
    #         완성된 프레임 (bytes)
    #     """
    #     # STX (3 bytes)
    #     frame = bytearray(STX_PATTERN)
        
    #     # CMD (1 byte)
    #     frame.append(cmd_type & 0xFF)
        
    #     # DATA_LENGTH (2 bytes, Little Endian)
    #     payload_len = len(payload)
    #     frame.append(payload_len & 0xFF)
    #     frame.append((payload_len >> 8) & 0xFF)
        
    #     # PAYLOAD (N bytes)
    #     frame.extend(payload)
        
    #     # CHECKSUM 계산 (STX ~ PAYLOAD)
    #     checksum = self.calculate_checksum(bytes(frame))
    #     frame.append(checksum & 0xFF)
    #     frame.append((checksum >> 8) & 0xFF)
        
    #     # ETX (3 bytes)
    #     frame.extend(ETX_PATTERN)
        
    #     return bytes(frame)
    
    # def send_frame(self, frame: bytes) -> bool:
    #     """프레임 전송
        
    #     Args:
    #         frame: 전송할 프레임
            
    #     Returns:
    #         True: 성공, False: 실패
    #     """
    #     if self.serial_port is None or not self.serial_port.is_open:
    #         print("[CommandSender] 시리얼 포트가 열려있지 않습니다")
    #         return False
        
    #     try:
    #         self.serial_port.write(frame)
    #         self.serial_port.flush()
    #         print(f"[CommandSender] 전송 완료: {len(frame)} bytes, {frame.hex(' ').upper()}")
    #         return True
    #     except Exception as e:
    #         print(f"[CommandSender] 전송 오류: {e}")
    #         return False
    
    # # ========================================
    # # 편의 함수들
    # # ========================================
    
    # def send_set_tp1(self, tp1_value: int) -> bool:
    #     """TP1 값 설정 명령 전송
        
    #     Args:
    #         tp1_value: TP1 값 (0-4095)
            
    #     Returns:
    #         True: 성공, False: 실패
    #     """
    #     # 범위 검사
    #     if not 0 <= tp1_value <= 65535:
    #         print(f"[CommandSender] TP1 값 범위 오류: {tp1_value}")
    #         return False
        
    #     # uint16_t Little Endian
    #     payload = bytes([
    #         tp1_value & 0xFF,
    #         (tp1_value >> 8) & 0xFF
    #     ])
        
    #     frame = self.build_frame(UartCommandType.CMD_SET_TP1, payload)
    #     return self.send_frame(frame)
    
    # def send_set_tp2(self, tp2_value: int) -> bool:
    #     """TP2 값 설정 명령 전송
        
    #     Args:
    #         tp2_value: TP2 값 (uint64)
            
    #     Returns:
    #         True: 성공, False: 실패
    #     """
    #     # uint64_t Little Endian
    #     payload = bytes([
    #         (tp2_value >> (i * 8)) & 0xFF
    #         for i in range(8)
    #     ])
        
    #     frame = self.build_frame(UartCommandType.CMD_SET_TP2, payload)
    #     return self.send_frame(frame)
    
    # def send_set_tp1_recheck(self, tp1_recheck_value: int) -> bool:
    #     """TP1 Recheck 값 설정 명령 전송
        
    #     Args:
    #         tp1_recheck_value: TP1 Recheck 값 (0-65535)
            
    #     Returns:
    #         True: 성공, False: 실패
    #     """
    #     # 범위 검사
    #     if not 0 <= tp1_recheck_value <= 65535:
    #         print(f"[CommandSender] TP1_RECHECK 값 범위 오류: {tp1_recheck_value}")
    #         return False
        
    #     # uint16_t Little Endian
    #     payload = bytes([
    #         tp1_recheck_value & 0xFF,
    #         (tp1_recheck_value >> 8) & 0xFF
    #     ])
        
    #     frame = self.build_frame(UartCommandType.CMD_SET_TP1_RECHECK, payload)
    #     return self.send_frame(frame)
    
    # def send_get_settings(self) -> bool:
    #     """설정값 요청 명령 전송
        
    #     Returns:
    #         True: 성공, False: 실패
    #     """
    #     frame = self.build_frame(UartCommandType.CMD_GET_SETTINGS)
    #     return self.send_frame(frame)
    
    # def send_save_nvs(self) -> bool:
    #     """NVS 저장 명령 전송
        
    #     Returns:
    #         True: 성공, False: 실패
    #     """
    #     frame = self.build_frame(UartCommandType.CMD_SAVE_NVS)
    #     return self.send_frame(frame)
    
    # def send_reset(self) -> bool:
    #     """ESP32 리셋 명령 전송
        
    #     Returns:
    #         True: 성공, False: 실패
    #     """
    #     frame = self.build_frame(UartCommandType.CMD_RESET)
    #     return self.send_frame(frame)
