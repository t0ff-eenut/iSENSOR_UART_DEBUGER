"""
간단한 UART 디버거 - 새로운 프로토콜 파서 테스트

ESP32-C3 PIR 센서의 UART 데이터를 실시간으로 파싱하여 출력
"""

import serial
from serial.tools.list_ports import comports
from uart_protocol.frame_parser import FrameParser
from uart_protocol.payload_parser import PayloadParser
from uart_protocol.protocol_config import get_data_type_name, BaudRate
import sys
import signal


class SimpleUartDebugger:
    """간단한 UART 디버거"""
    
    def __init__(self, baud_rate=BaudRate.BAUD_1152000):
        self.baud_rate = baud_rate
        self.serial_port = None
        self.parser = FrameParser()
        self.running = False
        
    def find_esp32_port(self):
        """ESP32 포트  자동 감지"""
        print("\n포트 검색 중...")
        ports = comports()
        
        for port in ports:
            print(f"  - {port.device}: {port.description}")
            # ESP32-C3는 일반적으로 CH343, CP210x 등의 USB-UART 칩 사용
            if port.vid and port.pid:
                return port.device
        
        # 자동 감지 실패 시 수동 입력
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
        """메인 루프"""
        if not self.serial_port or not self.serial_port.is_open:
            print("포트가 연결되지 않았습니다!")
            return
        
        print("\n" + "="*60)
        print("UART 데이터 수신 중... (Ctrl+C로 종료)")
        print("="*60 + "\n")
        
        self.running = True
        
        try:
            while self.running:
                # 바이트 읽기
                if self.serial_port.in_waiting > 0:
                    byte_data = self.serial_port.read(1)
                    if len(byte_data) > 0:
                        # 파서에 공급
                        frame = self.parser.feed_byte(byte_data[0])
                        
                        if frame is not None:
                            self._process_frame(frame)
        
        except KeyboardInterrupt:
            print("\n\n종료 신호 수신...")
        
        finally:
            self.stop()
    
    def _process_frame(self, frame):
        """프레임 처리 및 출력"""
        data_name = get_data_type_name(frame.data_type)
        
        # 프레임 정보 출력
        status = "✓" if frame.is_valid else "✗"
        print(f"{status} [{frame.timestamp.strftime('%H:%M:%S.%f')[:-3]}] "
              f"Type: {data_name:20s} "
              f"Length: {frame.data_length:4d} "
              f"Checksum: 0x{frame.checksum:04X}")
        
        # 체크섬 에러 출력
        if not frame.is_valid:
            print(f"  ⚠ {frame.error_message}")
        else:
            # 페이로드 파싱
            sensor_data = PayloadParser.parse(frame)
            if sensor_data:
                self._print_sensor_data(sensor_data)
    
    def _calculate_stats(self, data):
        """0이 아닌 값들에 대한 통계 계산"""
        valid_data = [x for x in data if x != 0]
        if not valid_data:
            return 0, 0, 0, 0  # Count, Min, Max, Avg
        
        count = len(valid_data)
        min_val = min(valid_data)
        max_val = max(valid_data)
        avg_val = sum(valid_data) / count
        return count, min_val, max_val, avg_val

    def _print_array_pretty(self, data, items_per_line=10, indent=4):
        """배열 데이터를 보기 좋게 출력"""
        for i in range(0, len(data), items_per_line):
            chunk = data[i:i + items_per_line]
            line = ", ".join(f"{x}" if isinstance(x, int) else f"{x:.2f}" for x in chunk)
            print(f"{' ' * indent}[{i:03d}] {line}")

    def _print_sensor_data(self, sensor_data):
        """센서 데이터 출력 (간략 + 상세)"""
        dt = sensor_data.data_type
        
        # ADC/Voltage 버퍼
        if sensor_data.adc_buffer:
            count, min_v, max_v, avg_v = self._calculate_stats(sensor_data.adc_buffer)
            print(f"  ADC: {len(sensor_data.adc_buffer)} samples (Valid: {count}) "
                  f"(Min: {min_v}, Max: {max_v}, Avg: {int(avg_v)})")
            self._print_array_pretty(sensor_data.adc_buffer)
        
        elif sensor_data.voltage_buffer:
            count, min_v, max_v, avg_v = self._calculate_stats(sensor_data.voltage_buffer)
            print(f"  Voltage: {len(sensor_data.voltage_buffer)} samples (Valid: {count}) "
                  f"(Min: {min_v}, Max: {max_v}, Avg: {int(avg_v)})")
            self._print_array_pretty(sensor_data.voltage_buffer)
        
        # HPF 버퍼
        elif sensor_data.hpf_buffer:
            count, min_v, max_v, avg_v = self._calculate_stats(sensor_data.hpf_buffer)
            print(f"  HPF: {len(sensor_data.hpf_buffer)} samples (Valid: {count}) "
                  f"(Min: {min_v:.2f}, Max: {max_v:.2f}, Avg: {avg_v:.2f})")
            self._print_array_pretty(sensor_data.hpf_buffer)
        
        # Delta 버퍼들
        elif sensor_data.adc_delta_buffer:
            count, min_v, max_v, avg_v = self._calculate_stats(sensor_data.adc_delta_buffer)
            print(f"  ADC Delta: {len(sensor_data.adc_delta_buffer)} samples (Valid: {count}) "
                  f"(Min: {min_v}, Max: {max_v}, Avg: {int(avg_v)})")
            self._print_array_pretty(sensor_data.adc_delta_buffer)
            
        elif sensor_data.voltage_delta_buffer:
            count, min_v, max_v, avg_v = self._calculate_stats(sensor_data.voltage_delta_buffer)
            print(f"  Voltage Delta: {len(sensor_data.voltage_delta_buffer)} samples (Valid: {count}) "
                  f"(Min: {min_v}, Max: {max_v}, Avg: {int(avg_v)})")
            self._print_array_pretty(sensor_data.voltage_delta_buffer)
            
        elif sensor_data.hpf_delta_buffer:
            count, min_v, max_v, avg_v = self._calculate_stats(sensor_data.hpf_delta_buffer)
            print(f"  HPF Delta: {len(sensor_data.hpf_delta_buffer)} samples (Valid: {count}) "
                  f"(Min: {min_v:.2f}, Max: {max_v:.2f}, Avg: {avg_v:.2f})")
            self._print_array_pretty(sensor_data.hpf_delta_buffer)
        
        # 설정값
        elif sensor_data.settings:
            s = sensor_data.settings
            print(f"  Settings:")
            print(f"    - TP1: {s.tp1}")
            print(f"    - TP2: {s.tp2}")
            print(f"    - LED: Max={s.led_max_percentage}%, Min={s.led_min_percentage}%, Ind={s.led_dimming_percentage}%")
            print(f"    - LED Step Time: {s.led_dimming_step_time_ms} ms")
            print(f"    - Occupancy Timeout: {s.occupancy_timeout_us} us")
            print(f"    - Sleep Time: {s.sleep_time} us")
        
        # 모든 버퍼
        elif sensor_data.all_buffers:
            print(f"  All Buffers: {list(sensor_data.all_buffers.keys())}")
    
    def stop(self):
        """종료"""
        self.running = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print("포트 닫힘")
        
        # 통계 출력
        self.parser.print_stats()


def signal_handler(sig, frame):
    """Ctrl+C 핸들러"""
    print("\n종료 중...")
    sys.exit(0)


if __name__ == "__main__":
    # Ctrl+C 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    
    print("="*60)
    print("iSENSOR UART Debugger - Simple Version")
    print("="*60)
    
    # 디버거 생성 및 실행
    debugger = SimpleUartDebugger()
    
    if debugger.connect():
        debugger.run()
    else:
        print("\n연결 실패. 프로그램을 종료합니다.")
        sys.exit(1)
