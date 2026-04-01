import numpy

import config                               as cfg
import uart_protocol.data_models            as updm

class FFT_Module():

    def __init__(self):
        self.f_sampling_rate:float  = cfg.FFT_SAMPLING_RATE

        self.A_data        = 0
        self.i_data_len    = 0
        self.f_gain        = 0

        self.A_f_data = []
        self.A_DC_exit_data = []

        self.A_fft_result   = []

        self.A_frequencies = []
        self.A_magnitudes  = []
        self.f_mean_adc    = 0.0
        self.i_peak_idx    = 0
        self.f_peak_freq   = 0
        self.f_peak_mag    = 0


    def fft(self, A_inter_data:list, f_gain:float = 1.0) -> list:
        """ADC 버퍼에 FFT 적용
        
        Args:
            A_inter_data: ADC 샘플 배열 (예: 300개의 uint16)
            f_gain: 진폭 게인 (표시용, 기본값 1.0)
            
        Returns:
            frequencies: 주파수 배열 (Hz)
            magnitudes: 진폭 배열 (게인 적용됨)
        """

        self.A_data     = A_inter_data
        self.i_data_len = len(self.A_data)
        self.f_gain     = f_gain

        # 1. DC 오프셋 제거
        self.A_f_data = numpy.array(self.A_data, dtype=numpy.float64)
        self.f_mean_adc = numpy.mean(self.A_f_data)               # 배열의 평균값
        self.A_DC_exit_data = self.A_f_data - self.f_mean_adc     # 배열 DC 성분 제거

        # 3. FFT 연산(음수 주파수 포함 -> 양수와 대칭)
        # fft_result = numpy.fft.fft(A_signal)
        # frequencies = numpy.fft.fftfreq(i_data_len, d=1.0/self.f_sampling_rate)

        # # ON / OFF
        # # 2. 윈도우 함수 적용 (스펙트럼 누설 방지)
        # window = numpy.hanning(i_data_len)
        # A_signal = A_signal * window

        # 3. FFT 연산 (실수 신호용 rfft)
        # 실수 신호는 양수=음수 대칭이라 음수 주파수 구간 자체가 없어집니다.
        # resualt = 크기(진폭)	해당 주파수가 얼마나 강한가 abs()
        #           위상	    해당 주파수의 시작 타이밍   angle()
        # frequencies = [0Hz,   0.33Hz,  0.67Hz,  20.3Hz,  ...]
        # magnitudes  = [0.0,   24.5,    1.2,     245.7,   ...]
        #                                         ↑
        #                             "20.3Hz 신호가 세기 245.7로 존재한다"

        # fft_result 단독으로는 세기만 있고 주파수는 없음
        # rfftfreq와 합쳐야 비로소 주파수 + 세기 조합
        self.A_fft_result = numpy.fft.rfft(self.A_DC_exit_data)
        # print(f"fft.py | fft() | len {len(fft_result)}\nfft_result = {fft_result}")
        

        # # 4. 진폭 계산 및 정규화 (abs(fft_result[k]) × N/2)
        # magnitudes = 진폭(세기)
        self.A_magnitudes = numpy.abs(self.A_fft_result) * (2 / self.i_data_len)
        self.A_magnitudes[0] /= 2  # DC 성분 보정
        
        self.A_magnitudes = self.A_magnitudes * self.f_gain  # 게인 적용 (표시용)

        # # 5. 주파수 축 생성
        self.A_frequencies = numpy.fft.rfftfreq(self.i_data_len, d=1.0/self.f_sampling_rate)

        print(f"fft.py | fft() | len {len(self.A_magnitudes)}\n A_magnitudes = {self.A_magnitudes}")
        print(f"fft.py | fft() | len {len(self.A_frequencies)}\n A_frequencies = {self.A_frequencies}")

        if len(self.A_magnitudes) > 1:
            # DC(0Hz) 제외한 영역에서 피크 찾기
            self.i_peak_idx = numpy.argmax(self.A_magnitudes[1:]) + 1
            self.i_peak_freq = self.A_frequencies[self.i_peak_idx]
            self.i_peak_mag = self.A_magnitudes[self.i_peak_idx]
        else:
            self.i_peak_idx = 0
            self.i_peak_freq = 0
            self.i_peak_mag = 0
            
            # # 피크 라벨 업데이트 (Mean 값 포함)
            # if "ADC_FFT" in self.fft_peak_labels:
            #     label = self.fft_peak_labels["ADC_FFT"]
            #     label.setText(f"DC Mean: {dc_mean:.1f}\nPeak: {peak_freq:.2f} Hz\n진폭(Mag): {peak_mag:.1f}")
            #     label.setPos(frequencies[-1] * 0.6, 50)  # Y축 150 고정, 중간 위치



        return (
            self.A_frequencies
            , self.A_magnitudes
            , self.f_gain
            , self.f_mean_adc
            , self.i_peak_idx
            , self.i_peak_freq
            , self.i_peak_mag
            )

