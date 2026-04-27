"""
UART Command Sender - PC → ESP32 명령 전송 모듈

ESP32 디바이스에 명령을 전송하기 위한 프레임 생성 및 송신 기능
"""

from typing import Final
import serial
# import protocol_config

import uart_protocol.uart_protocol_config   as upcfg

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

        self.A_send_byte_buffer:bytearray    = bytearray()
    
    def set_serial(self, input_serial_port:serial.Serial):
        """시리얼 포트 설정"""
        self.serial_port = input_serial_port
    
    def calculate_checksum(self, data: bytes) -> int:
        """체크섬 계산 (Sum 방식, 16bit)
        
        Args:
            data: STX부터 PAYLOAD 끝까지의 데이터
            
        Returns:
            16bit 체크섬 값
        """
        return sum(data) & 0xFFFF
    
    # self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_TP1, byte_data)
    def make_uart_send_data(self, cmd_type: upcfg.UartCommandType, input_byte_data: bytes = b'') -> bytes:
        """명령 프레임 생성
        
        프레임 구조:
        [STX:3] [CMD:1] [LEN:2] [PAYLOAD:N] [CHECKSUM:2] [ETX:3]
        
        Args:
            cmd_type: 명령 타입 (UartCommandType)
            payload: 페이로드 데이터 (bytes)
            
        Returns:
            완성된 프레임 (bytes)
        """
        self.A_send_byte_buffer.clear()
        
        # STX (3 bytes)
        # bframe = bytearray(upcfg.UART_RECEIVE_STX_PATTERN)
        self.A_send_byte_buffer.extend(upcfg.UART_RECEIVE_STX_PATTERN)
        
        # CMD (1 byte)
        self.A_send_byte_buffer.append(cmd_type & 0xFF)
        
        # DATA_LENGTH (2 bytes, Little Endian)
        i_data_len = len(input_byte_data)
        self.A_send_byte_buffer.append(i_data_len & 0xFF)
        self.A_send_byte_buffer.append((i_data_len >> 8) & 0xFF)
        
        # PAYLOAD (N bytes)
        self.A_send_byte_buffer.extend(input_byte_data)
        
        # CHECKSUM 계산 (STX ~ PAYLOAD)
        i_checksum = self.calculate_checksum(bytes(self.A_send_byte_buffer))
        self.A_send_byte_buffer.append(i_checksum & 0xFF)
        self.A_send_byte_buffer.append((i_checksum >> 8) & 0xFF)
        
        # ETX (3 bytes)
        self.A_send_byte_buffer.extend(upcfg.UART_RECEIVE_ETX_PATTERN)
        
        return bytes(self.A_send_byte_buffer)
    
    def uart_send_data(self, input_byte_data: bytes) -> bool:
        """프레임 전송
        
        Args:
            frame: 전송할 프레임
            
        Returns:
            True: 성공, False: 실패
        """
        if self.serial_port is None or not self.serial_port.is_open:
            print("[CommandSender] 시리얼 포트가 열려있지 않습니다")
            return False
        
        try:
            self.serial_port.write(input_byte_data)
            self.serial_port.flush()
            print(f"[CommandSender] 전송 완료: {len(input_byte_data)} bytes, {input_byte_data.hex(' ').upper()}")
            return True
        except Exception as e:
            print(f"[CommandSender] 전송 오류: {e}")
            return False
    
    # # ========================================
    # # 편의 함수들
    # # ========================================
    
    def send_set_tp1(self, inter_i_tp1_value: int) -> bool:
        """TP1 값 설정 명령 전송
        
        Args:
            tp1_value: TP1 값 (0-4095)
            
        Returns:
            True: 성공, False: 실패
        """
        # 범위 검사
        if not 0 <= inter_i_tp1_value <= 4095:
            print(f"[CommandSender] TP1 값 범위 오류: {inter_i_tp1_value}")
            return False
        
        # uint16_t Little Endian
        byte_data = bytes([
            inter_i_tp1_value & 0xFF,
            (inter_i_tp1_value >> 8) & 0xFF
        ])
        
        return_send_data = self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_TP1, byte_data)
        return self.uart_send_data(return_send_data)

    def send_set_tp1_recheck(self, inter_i_tp1_rck_value: int) -> bool:
        """TP1 Recheck 값 설정 명령 전송
        
        Args:
            inter_i_tp1_rck_value: TP1 Recheck 값 (0-65535)
            
        Returns:
            True: 성공, False: 실패
        """
        # 범위 검사
        if not 0 <= inter_i_tp1_rck_value <= 4095:
            print(f"[CommandSender] TP1_RECHECK 값 범위 오류: {inter_i_tp1_rck_value}")
            return False
        
        # uint16_t Little Endian
        byte_data = bytes([
            inter_i_tp1_rck_value & 0xFF,
            (inter_i_tp1_rck_value >> 8) & 0xFF
        ])
        
        return_send_data = self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_TP1_RECHECK, byte_data)
        return self.uart_send_data(return_send_data)
    
    def send_set_tp2(self, inter_i_tp2_value: int) -> bool:
        """TP2 값 설정 명령 전송
        
        Args:
            tp2_value: TP2 값 (uint64)
            
        Returns:
            True: 성공, False: 실패
        """
        # uint64_t Little Endian
        byte_data = bytes([
            (inter_i_tp2_value >> (i * 8)) & 0xFF
            for i in range(8)
        ])
        
        return_send_data = self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_TP2, byte_data)
        return self.uart_send_data(return_send_data)
    

    
    def send_set_fft_stride(self, i_stride_value: int) -> bool:
        """FFT Stride 값 설정 명령 전송 (ADC 몇 샘플마다 FFT를 실행할지)

        Args:
            i_stride_value: Stride 값 (1 ~ 256)

        Returns:
            True: 성공, False: 실패
        """
        if not 1 <= i_stride_value <= 256:
            print(f"[CommandSender] FFT Stride 값 범위 오류: {i_stride_value}")
            return False

        # uint16_t Little Endian
        byte_data = bytes([
            i_stride_value & 0xFF,
            (i_stride_value >> 8) & 0xFF
        ])

        return_send_data = self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_FFT_STRIDE, byte_data)
        return self.uart_send_data(return_send_data)

    def send_set_led_max_per(self, value: int) -> bool:
        if not 0 <= value <= 100:
            return False
        return self.uart_send_data(self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_LED_MAX_PER, bytes([value & 0xFF])))

    def send_set_led_min_per(self, value: int) -> bool:
        if not 0 <= value <= 100:
            return False
        return self.uart_send_data(self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_LED_MIN_PER, bytes([value & 0xFF])))

    def send_set_led_dim_per(self, value: int) -> bool:
        if not 0 <= value <= 100:
            return False
        return self.uart_send_data(self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_LED_DIM_PER, bytes([value & 0xFF])))

    def _uint32_le(self, value: int) -> bytes:
        return bytes([value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, (value >> 24) & 0xFF])

    def _uint64_le(self, value: int) -> bytes:
        return bytes([(value >> (i * 8)) & 0xFF for i in range(8)])

    def send_set_led_work_ms(self, value_ms: int) -> bool:
        if value_ms < 0:
            return False
        return self.uart_send_data(self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_LED_WORK_MS, self._uint32_le(value_ms)))

    def send_set_led_step_ms(self, value_ms: int) -> bool:
        if value_ms < 0:
            return False
        return self.uart_send_data(self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_LED_STEP_MS, self._uint32_le(value_ms)))

    def send_set_led_delay_ms(self, value_ms: int) -> bool:
        if value_ms < 0:
            return False
        return self.uart_send_data(self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_LED_DELAY_MS, self._uint32_le(value_ms)))

    def send_set_occu_timeout_us(self, value_us: int) -> bool:
        if value_us < 0:
            return False
        return self.uart_send_data(self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_OCCU_TIMEOUT, self._uint64_le(value_us)))

    def send_set_sleep_time_us(self, value_us: int) -> bool:
        if value_us < 0:
            return False
        return self.uart_send_data(self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_SLEEP_TIME, self._uint64_le(value_us)))

    def send_set_led_onoff(self, b_on: bool) -> bool:
        return self.uart_send_data(self.make_uart_send_data(upcfg.UartCommandType.CMD_SET_LED_ONOFF, bytes([0x01 if b_on else 0x00])))

    # def send_get_settings(self) -> bool:
    #     """설정값 요청 명령 전송
        
    #     Returns:
    #         True: 성공, False: 실패
    #     """
    #     frame = self.make_uart_send_data(UartCommandType.CMD_GET_SETTINGS)
    #     return self.uart_send_data(frame)
    
    # def send_save_nvs(self) -> bool:
    #     """NVS 저장 명령 전송
        
    #     Returns:
    #         True: 성공, False: 실패
    #     """
    #     frame = self.make_uart_send_data(UartCommandType.CMD_SAVE_NVS)
    #     return self.uart_send_data(frame)
    
    # def send_reset(self) -> bool:
    #     """ESP32 리셋 명령 전송
        
    #     Returns:
    #         True: 성공, False: 실패
    #     """
    #     frame = self.make_uart_send_data(UartCommandType.CMD_RESET)
    #     return self.uart_send_data(frame)
