"""
디버그 UART 디버거 - 원시 바이트 출력

ESP32-C3 PIR 센서의 UART 데이터를 실시간으로 16진수로 출력
"""

import serial
from serial.tools.list_ports import comports
from uart_protocol.frame_parser import FrameParser
from uart_protocol.payload_parser import PayloadParser
from uart_protocol.protocol_config import get_data_type_name, BaudRate, STX, ETX
import sys
import signal
import time


class DebugUartReader:
    """디버그 UART  리더 - 원시 바이트 출력"""
    
    def __init__(self, baud_rate=BaudRate.BAUD_1152000):
        self.baud_rate = baud_rate
        self.serial_port = None
        self.parser = FrameParser()
        self.running = False
        
        # 통계
        self.total_bytes = 0
        self.last_print_time = time.time()
        self.bytes_since_last_print = 0
        
    def find_esp32_port(self):
        """ESP32 포트 자동 감지"""
        print("\n포트 검색 중...")
        ports = comports()
        
        for port in ports:
            print(f"  - {port.device}: {port.description}")
            if port.vid and port.pid:
                return port.device
        
        if ports:
            print(f"\n사용 가능한 포트: {[p.device for p in ports]}")
            port_input = input("포트 번호 입력 (예: COM5 또는 5): ")
            if len(port_input) < 4:
                return f"COM{port_input}"
            return port_input
        
        print("포트를 찾을 수 없습니다!")
        return None
    
    def connect(self, port=None):
        """UART 연결"""
        if port is None:
            port = self.find_esp32_port()
        
        if port is None:
            return False
        
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            print(f"\n✓ {port} 연결 성공! (Baud: {self.baud_rate})")
            return True
        
        except Exception as e:
            print(f"\n✗ 연결 실패: {e}")
            return False
    
    def run(self):
        """메인 루프 - 원시 바이트 출력"""
        if not self.serial_port or not self.serial_port.is_open:
            print("포트가 연결되지 않았습니다!")
            return
        
        print("\n" + "="*70)
        print("UART 원시 데이터 수신 중... (Ctrl+C로 종료)")
        print("="*70)
        print("\n형식: [번호] HEX (ASCII) | 파서 상태")
        print("-"*70 + "\n")
        
        self.running = True
        line_buffer = []
        line_count = 0
        
        try:
            while self.running:
                if self.serial_port.in_waiting > 0:
                    byte_data = self.serial_port.read(1)
                    if len(byte_data) > 0:
                        byte_val = byte_data[0]
                        self.total_bytes += 1
                        self.bytes_since_last_print += 1
                        
                        # 버퍼에 추가
                        line_buffer.append(byte_val)
                        
                        # 16바이트마다 줄바꿈
                        if len(line_buffer) >= 16:
                            self._print_line(line_buffer, line_count)
                            line_buffer = []
                            line_count += 1
                        
                        # 파서에도 공급
                        frame = self.parser.feed_byte(byte_val)
                        if frame is not None:
                            print(f"\n{'='*70}")
                            print(f"✓ 프레임 파싱 성공!")
                            print(f"  타입: {get_data_type_name(frame.data_type)}")
                            print(f"  길이: {frame.data_length} bytes")
                            print(f"  체크섬: 0x{frame.checksum:04X} ({'OK' if frame.is_valid else 'FAIL'})")
                            print(f"{'='*70}\n")
                        
                        # 1초마다 통계 출력
                        current_time = time.time()
                        if current_time - self.last_print_time >= 1.0:
                            self._print_stats()
                            self.last_print_time = current_time
                            self.bytes_since_last_print = 0
                
        except KeyboardInterrupt:
            print("\n\n종료 신호 수신...")
            # 남은 버퍼 출력
            if line_buffer:
                self._print_line(line_buffer, line_count)
        
        finally:
            self.stop()
    
    def _print_line(self, buffer, line_num):
        """16바이트 라인 출력"""
        # 16진수
        hex_str = ' '.join(f'{b:02X}' for b in buffer)
        
        # ASCII (출력 가능한 문자만)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in buffer)
        
        # STX/ETX 강조
        markers = []
        for b in buffer:
            if b == STX:
                markers.append('S')
            elif b == ETX:
                markers.append('E')
            else:
                markers.append(' ')
        marker_str = ''.join(markers)
        
        print(f"[{line_num:04d}] {hex_str:48s} | {ascii_str:16s} | {marker_str}")
        # flush: 출력 버퍼를 즉시 비워서 화면에 표시
        # {line_num:04d}: 줄 번호를 4자리 정수로 표시 (예: 0001, 0042, 1234)
        # {hex_str:48s}: 16진수 문자열을 48자 폭으로 왼쪽 정렬 (공백 패딩)
        # {ascii_str:16s}: ASCII 문자열을 16자 폭으로 왼쪽 정렬
        # {marker_str}: STX/ETX 마커 문자열 (폭 지정 없음)
        
    def _print_stats(self):
        """통계 출력"""
        stats = self.parser.get_stats()
        print(f"[통계] 총:{self.total_bytes} bytes | "
              f"프레임:{stats.valid_frames}/{stats.total_frames} | "
              f"동기에러:{stats.sync_errors} | "
              f"속도:{self.bytes_since_last_print} B/s")
    
    def stop(self):
        """종료"""
        self.running = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print("\n포트 닫힘")
        
        # 최종 통계
        self.parser.print_stats()


def signal_handler(sig, frame):
    """Ctrl+C 핸들러"""
    print("\n종료 중...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    
    print("="*70)
    print("iSENSOR UART Debugger - Debug Mode (Raw Bytes)")
    print("="*70)
    
    debugger = DebugUartReader()
    
    if debugger.connect():
        debugger.run()
    else:
        print("\n연결 실패. 프로그램을 종료합니다.")
        sys.exit(1)
