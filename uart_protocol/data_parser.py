"""
페이로드 파서

데이터 타입별 페이로드 파싱
"""

# from typing import List, Optional
# from uart_protocol.uart_protocol_config import UartDataType, WINDOW_SIZE, SETTINGS_TOTAL_SIZE
# from uart_protocol.data_models import SensorData, SettingsData, UartFrame
# from utils.byte_converter import (
#     bytes_to_uint16_be, bytes_to_uint16_le,
#     bytes_to_uint32_be, bytes_to_uint64_be,
#     bytes_to_uint16_array_be, bytes_to_float32_array_le,
#     bytes_to_bool_array
# )

from typing import List, Optional

import endian_converter                     as econv
import uart_protocol.uart_protocol_config   as upcfg
import uart_protocol.data_models            as updm



# class PayloadParser:
class DataParser:
    """Uart Parser -> Data Parser"""
    
    # @staticmethod
    # def parse(frame: UartFrame) -> Optional[SensorData]:
    def data_parser(self, complete_receive_data:updm.UartReceiveData) -> Optional[updm.SensorData]:
        """
        프레임의 페이로드를 파싱하여 SensorData 반환
        
        Args:
            frame: UartFrame
        
        Returns:
            SensorData 또는 None (파싱 실패 시)
        """
        try:
            # data_type = complete_receive_data.data_type
            # bytes_data = complete_receive_data.bytes_data
            
            # sensor_data = updm.SensorData(
            #     data_type=data_type,
            #     timestamp=complete_receive_data.timestamp,
            #     UartReceiveData_raw=complete_receive_data
            # )

            # print(f"data_parser.py | data_parser() | complete_receive_data: {complete_receive_data}")
            
            sensor_data = updm.SensorData(
                UartReceiveData_raw=complete_receive_data,
                i_data_type=complete_receive_data.bytes_data_type,

                timestamp=complete_receive_data.timestamp,
            )
            # payload_parser.py | parse() | frame.data_type: 9
            # payload_parser.py | parse() | UartDataType.ADC_BUFFER: 1
            # payload_parser.py | parse() | frame.data_type: 0
            # payload_parser.py | parse() | UartDataType.ADC_BUFFER: 1
            # print(f"data_parser.py | data_parser() | sensor_data.i_data_type: {sensor_data.i_data_type}")
            # print(f"data_parser.py | data_parser() | upcfg.UartDataType.RAW_VALUE: {upcfg.UartDataType.RAW_VALUE}")
            # print(f"data_parser.py | data_parser() | int(sensor_data.i_data_type): {int(sensor_data.i_data_type)}")
            # print(f"data_parser.py | data_parser() | bytes(upcfg.UartDataType.RAW_VALUE): {bytes(upcfg.UartDataType.RAW_VALUE)}")


            # 데이터 타입별 파싱
            if int(sensor_data.i_data_type) == upcfg.UartDataType.RAW_VALUE:
                # sensor_data.A_adc_buffer = PayloadParser._parse_uint16_buffer(bytes_data)
                sensor_data.i_adc_raw = econv.bytes_to_uint16_array_be(complete_receive_data.bytes_data)
                
            elif sensor_data.i_data_type == upcfg.UartDataType.ADC_BUFFER:
                sensor_data.A_adc_buffer = econv.bytes_to_uint16_array_be(complete_receive_data.bytes_data)
            # elif sensor_data.i_data_typ == upcfg.UartDataType.VOLTAGE_BUFFER:
            #     sensor_data.voltage_buffer = PayloadParser._parse_uint16_buffer(bytes_data)
            
            # elif sensor_data.i_data_typ == upcfg.UartDataType.ADC_HPF_BUFFER:  # SW HPF
            #     sensor_data.adc_hpf_buffer = PayloadParser._parse_float32_buffer(bytes_data)
            
            # elif sensor_data.i_data_typ == upcfg.UartDataType.ADC_BPF_BUFFER:  # SW BPF
            #     sensor_data.adc_bpf_buffer = PayloadParser._parse_float32_buffer(bytes_data)
            
            # elif sensor_data.i_data_typ == upcfg.UartDataType.HPF_BUFFER:  # HW HPF (RAW uint16)
            #     sensor_data.hw_hpf_buffer = PayloadParser._parse_uint16_buffer(bytes_data)
            
            # elif sensor_data.i_data_typ == upcfg.UartDataType.HPF_VOLTAGE_BUFFER:  # HW HPF Voltage (uint16)
            #     # 현재 GUI에서는 hw_hpf_buffer와 동일하게 처리
            #     sensor_data.hw_hpf_buffer = PayloadParser._parse_uint16_buffer(bytes_data)
            
            # elif sensor_data.i_data_typ == upcfg.UartDataType.BPF_BUFFER:  # HW BPF (RAW uint16)
            #     sensor_data.hw_bpf_buffer = PayloadParser._parse_uint16_buffer(bytes_data)
            
            # elif sensor_data.i_data_typ == upcfg.UartDataType.BPF_VOLTAGE_BUFFER:  # HW BPF Voltage (uint16)
            #     # 현재 GUI에서는 hw_bpf_buffer와 동일하게 처리
            #     sensor_data.hw_bpf_buffer = PayloadParser._parse_uint16_buffer(bytes_data)

            elif sensor_data.i_data_type == upcfg.UartDataType.SETTINGS:
                sensor_data.settings = self.settings_parser(complete_receive_data.bytes_data)

            elif sensor_data.i_data_type == upcfg.UartDataType.PROFILING:
                sensor_data.profiling = self.profiling_parser(complete_receive_data.bytes_data)

            elif sensor_data.i_data_type == upcfg.UartDataType.FFT:
                sensor_data.fft_result = self.fft_parser(complete_receive_data.bytes_data)

            elif sensor_data.i_data_type == upcfg.UartDataType.FFT_FEATURES:
                sensor_data.fft_features = self.fft_features_parser(complete_receive_data.bytes_data)
                
            # elif sensor_data.i_data_typ == upcfg.UartDataType.ALL_DATA:
            #     # ALL_DATA는 현재 미지원
            #     pass
            
            else:
                # 알 수 없는 타입
                return None
            
            # print(f"data_parser.py | data_parser() | sensor_data: {sensor_data}")
            return sensor_data
        
        except Exception as e:
            print(f"data_parser.py | data_parser() | Payload parsing error: {e}")
            return None
    
    # @staticmethod
    # def _parse_uint16_buffer(bytes_data: bytes) -> List[int]:
    #     """
    #     uint16 버퍼 파싱 (Big Endian)
        
    #     Args:
    #         bytes_data: 바이트 배열 (600 bytes for WINDOW_SIZE=300)
        
    #     Returns:
    #         List[int]: uint16 리스트
    #     """
    #     return econv.bytes_to_uint16_array_be(bytes_data)
    
    # @staticmethod
    # def _parse_float32_buffer(bytes_data: bytes) -> List[float]:
    #     """
    #     float32 버퍼 파싱 (Little Endian)
        
    #     Args:
    #         bytes_data: 바이트 배열 (1200 bytes for WINDOW_SIZE=300)
        
    #     Returns:
    #         List[float]: float32 리스트
    #     """
    #     return econv.bytes_to_float32_array_le(bytes_data)
    
    # @staticmethod
    # def _parse_bool_buffer(bytes_data: bytes) -> List[bool]:
    #     """
    #     bool 버퍼 파싱
        
    #     Args:
    #         bytes_data: 바이트 배열 (300 bytes for WINDOW_SIZE=300)
        
    #     Returns:
    #         List[bool]: bool 리스트
    #     """
    #     return econv.bytes_to_bool_array(bytes_data)
    
    # @staticmethod
    def settings_parser(self, bytes_data:bytes) -> updm.SettingsData:
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
            bytes_data: 34 bytes
        
        Returns:
            SettingsData
        """

        if len(bytes_data) != upcfg.RECEIVE_SETTINGS_TOTAL_SIZE:
            # error 코드 출력
            raise ValueError(f"Expected {upcfg.RECEIVE_SETTINGS_TOTAL_SIZE} bytes, got {len(bytes_data)}") 
        
        SettingData_handle = updm.SettingsData()

        # TP1 Occupancy (uint16 BE)
        i_tp1_start = 0
        i_tp1_end = i_tp1_start + upcfg.RECEIVE_SETTINGS_TP1_LENGTH
        SettingData_handle.i_tp1 = econv.bytes_to_uint16_be(bytes_data[i_tp1_start:i_tp1_end])
        i_tp1_rck_start = i_tp1_end
        i_tp1_rck_end = i_tp1_rck_start + upcfg.RECEIVE_SETTINGS_TP1_RECHECK_LENGTH
        # TP1 Recheck (uint16 BE)
        SettingData_handle.i_tp1_recheck = econv.bytes_to_uint16_be(bytes_data[i_tp1_rck_start:i_tp1_rck_end])
        i_tp2_start = i_tp1_rck_end
        i_tp2_end = i_tp2_start + upcfg.RECEIVE_SETTINGS_TP2_LENGTH
        # TP2 (uint64 BE)
        SettingData_handle.i_tp2 = econv.bytes_to_uint64_be(bytes_data[i_tp2_start:i_tp2_end])
        
        i_led_max_per_start = i_tp2_end
        i_led_max_per_end = i_led_max_per_start + upcfg.RECEIVE_SETTINGS_LED_MAX_PER_LENGTH
        # LED Max Percentage (uint8)
        SettingData_handle.i_led_max_per = econv.bytes_to_int_auto(bytes_data[i_led_max_per_start:i_led_max_per_end], endian='big')
        i_led_min_per_start = i_led_max_per_end
        i_led_min_per_end = i_led_min_per_start + upcfg.RECEIVE_SETTINGS_LED_MIN_PER_LENGTH
        # LED Min Percentage (uint8)
        SettingData_handle.i_led_min_per = econv.bytes_to_int_auto(bytes_data[i_led_min_per_start:i_led_min_per_end], endian='big')
        i_led_dim_per_start = i_led_min_per_end
        i_led_dim_per_end = i_led_dim_per_start + upcfg.RECEIVE_SETTINGS_LED_DIM_PER_LENGTH
        # LED Dimming Percentage (uint8)
        SettingData_handle.i_led_dim_per = econv.bytes_to_int_auto(bytes_data[i_led_dim_per_start:i_led_dim_per_end], endian='big')

        i_led_work_ms_start = i_led_dim_per_end
        i_led_work_ms_end = i_led_work_ms_start + upcfg.RECEIVE_SETTINGS_LED_WORK_MS_LENGTH
        # 
        SettingData_handle.i_led_work_ms = econv.bytes_to_uint32_be(bytes_data[i_led_work_ms_start:i_led_work_ms_end])
        i_led_step_ms_start = i_led_work_ms_end
        i_led_step_ms_end = i_led_step_ms_start + upcfg.RECEIVE_SETTINGS_LED_STEP_MS_LENGTH
        # 
        SettingData_handle.i_led_step_ms = econv.bytes_to_uint32_be(bytes_data[i_led_step_ms_start:i_led_step_ms_end])
        i_led_delay_ms_start = i_led_step_ms_end
        i_led_delay_ms_end = i_led_delay_ms_start + upcfg.RECEIVE_SETTINGS_LED_DELAY_MS_LENGTH
        # 
        SettingData_handle.i_led_delay_ms = econv.bytes_to_uint32_be(bytes_data[i_led_delay_ms_start:i_led_delay_ms_end])

        i_occu_chk_timeout_start = i_led_delay_ms_end
        i_occu_chk_timeout_end = i_occu_chk_timeout_start + upcfg.RECEIVE_SETTINGS_OCCU_CHK_TIMEOUT_LENGTH
        # 
        SettingData_handle.i_occu_chk_timeout_us = econv.bytes_to_uint64_be(bytes_data[i_occu_chk_timeout_start:i_occu_chk_timeout_end])
        i_sleep_time_start = i_occu_chk_timeout_end
        i_sleep_time_end = i_sleep_time_start + upcfg.RECEIVE_SETTINGS_SLEEP_TIME_LENGTH
        # 
        SettingData_handle.i_sleep_time_us = econv.bytes_to_uint64_be(bytes_data[i_sleep_time_start:i_sleep_time_end])

        b_occu_status_start = i_sleep_time_end
        b_occu_status_end = b_occu_status_start + upcfg.RECEIVE_SETTINGS_OCCUPANCY_STATUS_LENGTH
        # Occupancy status (bool from uint8)
        SettingData_handle.b_occu_status = bool(econv.bytes_to_int_auto(bytes_data[b_occu_status_start:b_occu_status_end], endian='big'))
        b_pir_status_start = b_occu_status_end
        b_pir_status_end = b_pir_status_start + upcfg.RECEIVE_SETTINGS_PIR_STATUS_LENGTH
        # PIR status (bool from uint8)
        SettingData_handle.b_pir_status = bool(econv.bytes_to_int_auto(bytes_data[b_pir_status_start:b_pir_status_end], endian='big'))


        print(f"data_parser.py | settings_parser() | SettingData_handle.b_occu_status: {SettingData_handle.b_occu_status}")
        print(f"data_parser.py | settings_parser() | SettingData_handle.b_pir_status: {SettingData_handle.b_pir_status}")


        return SettingData_handle


        # # LED_MAX (uint8)
        # led_max = bytes_data[i_pointer]
        # i_pointer += 1
        
        # # LED_MIN (uint8)
        # led_min = bytes_data[i_pointer]
        # i_pointer += 1
        
        # # LED_IND (uint8)
        # led_ind = bytes_data[i_pointer]
        # i_pointer += 1
        
        # # LED_DIMMING_STEP_TIME_MS (uint32 BE)
        # led_dimming_step_time_ms = econv.bytes_to_uint32_be(bytes_data[i_pointer:i_pointer+4])
        # i_pointer += 4
        
        # # LED_DIMMING_WORK_TIME_MS (uint32 BE)
        # led_dimming_work_time_ms = econv.bytes_to_uint32_be(bytes_data[i_pointer:i_pointer+4])
        # i_pointer += 4
        
        # # LED_DIMMING_DELAY_TIME_MS (uint32 BE)
        # led_dimming_delay_time_ms = econv.bytes_to_uint32_be(bytes_data[i_pointer:i_pointer+4])
        # i_pointer += 4
        
        # # OCCU_TO (uint64 BE)
        # occu_to = econv.bytes_to_uint64_be(bytes_data[i_pointer:i_pointer+8])
        # i_pointer += 8
        
        # # SLEEP (uint64 BE)
        # sleep_time = econv.bytes_to_uint64_be(bytes_data[i_pointer:i_pointer+8])
        # i_pointer += 8
        
        # # OCCUPANCY (bool, uint8)
        # occupancy = bool(bytes_data[i_pointer])
        # i_pointer += 1
        
        # # PIR_OUTPUT (bool, uint8)
        # pir_output = bool(bytes_data[i_pointer])
        
        # return updm.SettingsData(
        #     tp1=tp1,
        #     tp1_recheck=tp1_recheck,
        #     tp2=tp2,
        #     led_max_percentage=led_max,
        #     led_min_percentage=led_min,
        #     led_dimming_percentage=led_ind,
        #     led_dimming_step_time_ms=led_dimming_step_time_ms,
        #     led_dimming_work_time_ms=led_dimming_work_time_ms,
        #     led_dimming_delay_time_ms=led_dimming_delay_time_ms,
        #     occupancy_timeout_us=occu_to,
        #     sleep_time=sleep_time,
        #     occupancy=occupancy,
        #     pir_output=pir_output
        # )
    
    # @staticmethod
    # def _parse_all_buffers(bytes_data: bytes) -> dict:
    #     """
    #     ALL_BUFFERS 파싱
        
    #     구조:
    #     - ADC Buffer: 600 bytes
    #     - Voltage Buffer: 600 bytes
    #     - HPF Buffer: 1200 bytes
    #     - Occupancy Buffer: 300 bytes
    #     총 2700 bytes
        
    #     Args:
    #         bytes_data: 바이트 배열
        
    #     Returns:
    #         dict: 각 버퍼를 담은 딕셔너리
    #     """
    #     i_pointer = 0
        
    #     # ADC Buffer (600 bytes)
    #     adc_size = WINDOW_SIZE * 2
    #     adc_buffer = econv.bytes_to_uint16_array_be(bytes_data[i_pointer:i_pointer+adc_size])
    #     i_pointer += adc_size
        
    #     # Voltage Buffer (600 bytes)
    #     voltage_size = WINDOW_SIZE * 2
    #     voltage_buffer = econv.bytes_to_uint16_array_be(bytes_data[i_pointer:i_pointer+voltage_size])
    #     i_pointer += voltage_size
        
    #     # HPF Buffer (1200 bytes)
    #     hpf_size = WINDOW_SIZE * 4
    #     hpf_buffer = econv.bytes_to_float32_array_le(bytes_data[i_pointer:i_pointer+hpf_size])
    #     i_pointer += hpf_size
        
    #     # Occupancy Buffer (300 bytes)
    #     occupancy_size = WINDOW_SIZE
    #     occupancy_buffer = econv.bytes_to_bool_array(bytes_data[i_pointer:i_pointer+occupancy_size])
        
    #     return {
    #         'adc_buffer': adc_buffer,
    #         'voltage_buffer': voltage_buffer,
    #         'hpf_buffer': hpf_buffer,
    #         'occupancy_buffer': occupancy_buffer
    #     }

    def profiling_parser(self, bytes_data: bytes) -> updm.ProfilingData:
        """
        프로파일링 데이터 파싱 (36 bytes: 9 x uint32_t Big Endian)

        필드 순서 (펌웨어 UART_TX_PROFILING case 와 동일):
          0: adc_reading_time_us              (uint32 BE)
          1: adc_read_buffer_latency_time_us  (uint32 BE)
          2: adc_processing_time_us           (uint32 BE)
          3: adc_buffer_insert_time_us        (uint32 BE)
          4: fft_process_time_us              (uint32 BE)
          5: fft_features_process_time_us     (uint32 BE)
          6: fft_loop_a_time_us               (uint32 BE)
          7: fft_loop_b_time_us               (uint32 BE)
          8: fft_loop_c_time_us               (uint32 BE)

        Args:
            bytes_data: 36 bytes

        Returns:
            ProfilingData
        """
        if len(bytes_data) != upcfg.RECEIVE_PROFILING_TOTAL_SIZE:
            raise ValueError(
                f"ProfilingData: expected {upcfg.RECEIVE_PROFILING_TOTAL_SIZE} bytes, got {len(bytes_data)}"
            )

        fields = []
        for i in range(9):
            offset = i * 4
            value = (
                (bytes_data[offset]     << 24) |
                (bytes_data[offset + 1] << 16) |
                (bytes_data[offset + 2] <<  8) |
                 bytes_data[offset + 3]
            )
            fields.append(value)

        return updm.ProfilingData(
            adc_reading_time_us             = fields[0],
            adc_read_buffer_latency_time_us = fields[1],
            adc_processing_time_us          = fields[2],
            adc_buffer_insert_time_us       = fields[3],
            fft_process_time_us             = fields[4],
            fft_features_process_time_us    = fields[5],
            fft_loop_a_time_us              = fields[6],
            fft_loop_b_time_us              = fields[7],
            fft_loop_c_time_us              = fields[8],
        )

    def fft_parser(self, bytes_data: bytes) -> updm.FftData:
        """
        FFT 에너지 스펙트럼 파싱 (FFT_OUTPUT_SIZE x uint32 Big Endian)

        필드: energies[0..FFT_OUTPUT_SIZE-1] (uint32 BE, re²+im²)
        예) FFT_OUTPUT_SIZE=129, WINDOW_SIZE=256 → 516 bytes

        magnitude 복원:
          k=0  : sqrt(E) / FFT_SC16_SCALE * 1/N
          k>=1 : sqrt(E) / FFT_SC16_SCALE * 2/N
          FFT_SC16_SCALE=8, N=WINDOW_SIZE=256

        Args:
            bytes_data: upcfg.RECEIVE_FFT_TOTAL_SIZE bytes

        Returns:
            FftData (energies + magnitudes 둘 다 보관)
        """
        import struct
        import math

        if len(bytes_data) != upcfg.RECEIVE_FFT_TOTAL_SIZE:
            raise ValueError(
                f"FftData: expected {upcfg.RECEIVE_FFT_TOTAL_SIZE} bytes, got {len(bytes_data)}"
            )

        fft_output_size = upcfg.RECEIVE_FFT_TOTAL_SIZE // 4
        energies = list(struct.unpack(f'>{fft_output_size}I', bytes_data))

        FFT_SC16_SCALE = 8
        N = fft_output_size * 2 - 2  # WINDOW_SIZE = (FFT_OUTPUT_SIZE-1)*2 = 256
        magnitudes = [
            math.sqrt(e) / FFT_SC16_SCALE * (1.0 / N if k == 0 else 2.0 / N)
            for k, e in enumerate(energies)
        ]
        return updm.FftData(energies=energies, magnitudes=magnitudes)

    def fft_features_parser(self, bytes_data: bytes) -> updm.FftFeaturesData:
        """
        FFT 특징값 파싱 (72 bytes: 18 필드 × 4 bytes Big Endian)

        필드 순서 (펌웨어 UART_TX_FFT_FEATURES case 직렬화 순서와 동일):
          0:  f_spectral_rolloff     (float BE)
          1:  f_spectral_bandwidth   (float BE)
          2:  i_peak_count           (int32 BE  — signed)
          3:  f_mid_ratio            (float BE)
          4:  f_low_to_high_ratio    (float BE)
          5:  f_second_peak_freq     (float BE)
          6:  f_kurtosis             (float BE)
          7:  f_centroid             (float BE)
          8:  f_peak_freq            (float BE)
          9:  f_low_ratio            (float BE)
          10: f_rms                  (float BE)
          11: ui32_avg_energy        (uint32 BE)
          12: ui32_peak_energy       (uint32 BE)
          13: f_energy_variance      (float BE)
          14: f_peak_to_avg_e        (float BE)
          15: f_high_ratio           (float BE)
          16: f_peak1_to_peak2_ratio (float BE)
          17: f_skewness             (float BE)

        Args:
            bytes_data: 72 bytes

        Returns:
            FftFeaturesData
        """
        import struct

        if len(bytes_data) != upcfg.RECEIVE_FFT_FEATURES_TOTAL_SIZE:
            raise ValueError(
                f"FftFeaturesData: expected {upcfg.RECEIVE_FFT_FEATURES_TOTAL_SIZE} bytes, got {len(bytes_data)}"
            )

        def read_float(offset: int) -> float:
            return struct.unpack('>f', bytes_data[offset:offset + 4])[0]

        def read_int32(offset: int) -> int:
            return struct.unpack('>i', bytes_data[offset:offset + 4])[0]

        def read_uint32(offset: int) -> int:
            return struct.unpack('>I', bytes_data[offset:offset + 4])[0]

        return updm.FftFeaturesData(
            f_spectral_rolloff     = read_float(  0),
            f_spectral_bandwidth   = read_float(  4),
            i_peak_count           = read_int32(  8),   # int32 (signed)
            f_mid_ratio            = read_float( 12),
            f_low_to_high_ratio    = read_float( 16),
            f_second_peak_freq     = read_float( 20),
            f_kurtosis             = read_float( 24),
            f_centroid             = read_float( 28),
            f_peak_freq            = read_float( 32),
            f_low_ratio            = read_float( 36),
            f_rms                  = read_float( 40),
            ui32_avg_energy        = read_uint32(44),
            ui32_peak_energy       = read_uint32(48),
            f_energy_variance      = read_float( 52),
            f_peak_to_avg_e        = read_float( 56),
            f_high_ratio           = read_float( 60),
            f_peak1_to_peak2_ratio = read_float( 64),
            f_skewness             = read_float( 68),
        )
