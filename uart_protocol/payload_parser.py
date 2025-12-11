"""
페이로드 파서

데이터 타입별 페이로드 파싱
"""

from typing import List, Optional
from uart_protocol.protocol_config import UartDataType, WINDOW_SIZE, SETTINGS_TOTAL_SIZE
from uart_protocol.data_models import SensorData, SettingsData, UartFrame
from utils.byte_converter import (
    bytes_to_uint16_be, bytes_to_uint16_le,
    bytes_to_uint32_be, bytes_to_uint64_be,
    bytes_to_uint16_array_be, bytes_to_float32_array_le,
    bytes_to_bool_array
)


class PayloadParser:
    """페이로드 파서"""
    
    @staticmethod
    def parse(frame: UartFrame) -> Optional[SensorData]:
        """
        프레임의 페이로드를 파싱하여 SensorData 반환
        
        Args:
            frame: UartFrame
        
        Returns:
            SensorData 또는 None (파싱 실패 시)
        """
        try:
            data_type = frame.data_type
            payload = frame.payload
            
            sensor_data = SensorData(
                data_type=data_type,
                timestamp=frame.timestamp,
                raw_frame=frame
            )
            
            # 데이터 타입별 파싱
            if data_type == UartDataType.ADC_BUFFER:
                sensor_data.adc_buffer = PayloadParser._parse_uint16_buffer(payload)
            
            elif data_type == UartDataType.VOLTAGE_BUFFER:
                sensor_data.voltage_buffer = PayloadParser._parse_uint16_buffer(payload)
            
            elif data_type == UartDataType.HPF_BUFFER:
                sensor_data.hpf_buffer = PayloadParser._parse_float32_buffer(payload)
            
            elif data_type == UartDataType.ADC_DELTA_BUFFER:
                sensor_data.adc_delta_buffer = PayloadParser._parse_uint16_buffer(payload)
            
            elif data_type == UartDataType.VOLTAGE_DELTA_BUFFER:
                sensor_data.voltage_delta_buffer = PayloadParser._parse_uint16_buffer(payload)
            
            elif data_type == UartDataType.HPF_DELTA_BUFFER:
                sensor_data.hpf_delta_buffer = PayloadParser._parse_float32_buffer(payload)
            
            elif data_type == UartDataType.OCCUPANCY_BUFFER:
                sensor_data.occupancy_buffer = PayloadParser._parse_bool_buffer(payload)
            
            elif data_type == UartDataType.SETTINGS:
                sensor_data.settings = PayloadParser._parse_settings(payload)
            
            elif data_type == UartDataType.ALL_BUFFERS:
                sensor_data.all_buffers = PayloadParser._parse_all_buffers(payload)
            
            else:
                # 알 수 없는 타입
                return None
            
            return sensor_data
        
        except Exception as e:
            print(f"Payload parsing error: {e}")
            return None
    
    @staticmethod
    def _parse_uint16_buffer(payload: bytes) -> List[int]:
        """
        uint16 버퍼 파싱 (Big Endian)
        
        Args:
            payload: 바이트 배열 (600 bytes for WINDOW_SIZE=300)
        
        Returns:
            List[int]: uint16 리스트
        """
        return bytes_to_uint16_array_be(payload)
    
    @staticmethod
    def _parse_float32_buffer(payload: bytes) -> List[float]:
        """
        float32 버퍼 파싱 (Little Endian)
        
        Args:
            payload: 바이트 배열 (1200 bytes for WINDOW_SIZE=300)
        
        Returns:
            List[float]: float32 리스트
        """
        return bytes_to_float32_array_le(payload)
    
    @staticmethod
    def _parse_bool_buffer(payload: bytes) -> List[bool]:
        """
        bool 버퍼 파싱
        
        Args:
            payload: 바이트 배열 (300 bytes for WINDOW_SIZE=300)
        
        Returns:
            List[bool]: bool 리스트
        """
        return bytes_to_bool_array(payload)
    
    @staticmethod
    def _parse_settings(payload: bytes) -> SettingsData:
        """
        설정값 파싱 (34 bytes)
        
        구조:
        - TP1: uint16 (Big Endian) - 2 bytes
        - TP2: uint64 (Big Endian) - 8 bytes
        - LED_MAX: uint8 - 1 byte
        - LED_MIN: uint8 - 1 byte
        - LED_IND: uint8 - 1 byte
        - LED_DIMMING_STEP_TIME_MS: uint32 (Big Endian) - 4 bytes
        - OCCU_TO: uint64 (Big Endian) - 8 bytes
        - SLEEP: uint64 (Big Endian) - 8 bytes
        - OCCUPANCY: bool (uint8) - 1 byte
        
        Args:
            payload: 34 bytes
        
        Returns:
            SettingsData
        """
        if len(payload) != SETTINGS_TOTAL_SIZE:
            raise ValueError(f"Expected {SETTINGS_TOTAL_SIZE} bytes, got {len(payload)}")
        
        offset = 0
        
        # TP1 Occupancy (uint16 BE)
        tp1 = bytes_to_uint16_be(payload[offset:offset+2])
        offset += 2
        
        # TP1 Recheck (uint16 BE)
        tp1_recheck = bytes_to_uint16_be(payload[offset:offset+2])
        offset += 2
        
        # TP2 (uint64 BE)
        tp2 = bytes_to_uint64_be(payload[offset:offset+8])
        offset += 8
        
        # LED_MAX (uint8)
        led_max = payload[offset]
        offset += 1
        
        # LED_MIN (uint8)
        led_min = payload[offset]
        offset += 1
        
        # LED_IND (uint8)
        led_ind = payload[offset]
        offset += 1
        
        # LED_DIMMING_STEP_TIME_MS (uint32 BE)
        led_dimming_step_time_ms = bytes_to_uint32_be(payload[offset:offset+4])
        offset += 4
        
        # LED_DIMMING_WORK_TIME_MS (uint32 BE)
        led_dimming_work_time_ms = bytes_to_uint32_be(payload[offset:offset+4])
        offset += 4
        
        # LED_DIMMING_DELAY_TIME_MS (uint32 BE)
        led_dimming_delay_time_ms = bytes_to_uint32_be(payload[offset:offset+4])
        offset += 4
        
        # OCCU_TO (uint64 BE)
        occu_to = bytes_to_uint64_be(payload[offset:offset+8])
        offset += 8
        
        # SLEEP (uint64 BE)
        sleep_time = bytes_to_uint64_be(payload[offset:offset+8])
        offset += 8
        
        # OCCUPANCY (bool, uint8)
        occupancy = bool(payload[offset])
        offset += 1
        
        # PIR_OUTPUT (bool, uint8)
        pir_output = bool(payload[offset])
        
        return SettingsData(
            tp1=tp1,
            tp1_recheck=tp1_recheck,
            tp2=tp2,
            led_max_percentage=led_max,
            led_min_percentage=led_min,
            led_dimming_percentage=led_ind,
            led_dimming_step_time_ms=led_dimming_step_time_ms,
            led_dimming_work_time_ms=led_dimming_work_time_ms,
            led_dimming_delay_time_ms=led_dimming_delay_time_ms,
            occupancy_timeout_us=occu_to,
            sleep_time=sleep_time,
            occupancy=occupancy,
            pir_output=pir_output
        )
    
    @staticmethod
    def _parse_all_buffers(payload: bytes) -> dict:
        """
        ALL_BUFFERS 파싱
        
        구조:
        - ADC Buffer: 600 bytes
        - Voltage Buffer: 600 bytes
        - HPF Buffer: 1200 bytes
        - Occupancy Buffer: 300 bytes
        총 2700 bytes
        
        Args:
            payload: 바이트 배열
        
        Returns:
            dict: 각 버퍼를 담은 딕셔너리
        """
        offset = 0
        
        # ADC Buffer (600 bytes)
        adc_size = WINDOW_SIZE * 2
        adc_buffer = bytes_to_uint16_array_be(payload[offset:offset+adc_size])
        offset += adc_size
        
        # Voltage Buffer (600 bytes)
        voltage_size = WINDOW_SIZE * 2
        voltage_buffer = bytes_to_uint16_array_be(payload[offset:offset+voltage_size])
        offset += voltage_size
        
        # HPF Buffer (1200 bytes)
        hpf_size = WINDOW_SIZE * 4
        hpf_buffer = bytes_to_float32_array_le(payload[offset:offset+hpf_size])
        offset += hpf_size
        
        # Occupancy Buffer (300 bytes)
        occupancy_size = WINDOW_SIZE
        occupancy_buffer = bytes_to_bool_array(payload[offset:offset+occupancy_size])
        
        return {
            'adc_buffer': adc_buffer,
            'voltage_buffer': voltage_buffer,
            'hpf_buffer': hpf_buffer,
            'occupancy_buffer': occupancy_buffer
        }
