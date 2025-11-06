from serial import *   # 헤더 역할 파일에서 전부 불러오기
from serial.tools.list_ports import comports

from random import randint

from custom_queue.queue_header import *

UART = 0
TEST = 1
MODE = UART

BAUD_RATE_115200 = 115200
BAUD_RATE_230400 = 230400
BAUD_RATE_460800 = 460800
BAUD_RATE_500000 = 500000
BAUD_RATE_576000 = 576000
BAUD_RATE_921600 = 921600
BAUD_RATE_1000000 = 1000000
BAUD_RATE_1152000 = 1152000
BAUD_RATE_1500000 = 1500000
BAUD_RATE_2000000 = 2000000
BAUD_RATE_2500000 = 2500000
BAUD_RATE_3000000 = 3000000
BAUD_RATE_3500000 = 3500000
BAUD_RATE_4000000 = 4000000

BAUD_RATE_SEL = BAUD_RATE_1500000

serial_component_handle = None

# Uart Recive 구조체
class receive_uart_adc_structer:
    def __init__(self
                 , ui8_signal
                 , ui8_group_1_length, ui8_group_1_8bit_length, ui8_adc, ui8_voltage, ui8_tp1
                 , ui8_group_2_length, ui8_group_2_8bit_length, ui8_tp2, ui8_switch_status, ui8_occu_triger
                 , ui8_group_3_length, ui8_group_3_8bit_length, ui8_adc_buf, ui8_adc_delta_buf
                 , ui8_group_4_length, ui8_group_4_8bit_length, ui8_occu_buf
#####################################################################################################
                 , ui8_group_5_length, ui8_group_5_8bit_length, ui8_bandfilter_buf
#####################################################################################################
                 , ui8_chksum, ui8_dummy):
        self.ui8_signal                 = ui8_signal

        self.ui8_group_1_length         = ui8_group_1_length
        self.ui8_group_1_8bit_length    = ui8_group_1_8bit_length
        self.ui8_adc                    = ui8_adc
        self.ui8_voltage                = ui8_voltage
        self.ui8_tp1                    = ui8_tp1

        self.ui8_group_2_length         = ui8_group_2_length
        self.ui8_group_2_8bit_length    = ui8_group_2_8bit_length
        self.ui8_tp2                    = ui8_tp2
        self.ui8_switch_status          = ui8_switch_status
        self.ui8_occu_triger            = ui8_occu_triger

        self.ui8_group_3_length         = ui8_group_3_length
        self.ui8_group_3_8bit_length    = ui8_group_3_8bit_length
        self.ui8_adc_buf                = ui8_adc_buf
        self.ui8_adc_delta_buf          = ui8_adc_delta_buf

        self.ui8_group_4_length         = ui8_group_4_length
        self.ui8_group_4_8bit_length    = ui8_group_4_8bit_length
        self.ui8_occu_buf               = ui8_occu_buf
#####################################################################################################
        self.ui8_group_5_length         = ui8_group_5_length
        self.ui8_group_5_8bit_length    = ui8_group_5_8bit_length
        self.ui8_bandfilter_buf         = ui8_bandfilter_buf
#####################################################################################################
        self.ui8_chksum                 = ui8_chksum
        self.ui8_dummy                  = ui8_dummy


class C_UART_RECEIVE_DATA_PROCESS_LEVEL(IntEnum):
    SIGNAL              = 0

    GROUP_1_LENGTH      = 1
    GROUP_1_BIT_LENGTH  = 2
    ADC                 = 3
    VOLTAGE             = 4
    TP1                 = 5

    GROUP_2_LENGTH      = 6
    GROUP_2_BIT_LENGTH  = 7
    TP2                 = 8
    SWITCH_STATUS       = 9
    OCCU_TRIGER         = 10

    GROUP_3_LENGTH      = 11
    GROUP_3_BIT_LENGTH  = 12
    ADC_BUF             = 13
    ADC_DELTA_BUF       = 14

    GROUP_4_LENGTH      = 15
    GROUP_4_BIT_LENGTH  = 16
    OCCU_BUF            = 17
#####################################################################################################
    GROUP_5_LENGTH      = 18
    GROUP_5_BIT_LENGTH  = 19
    BANDFILTER_BUF      = 20
#####################################################################################################
    CHECKSUM            = 21
    DUMMY               = 22

class C_UART_SIGNAL(IntEnum):
    ADC_SIGNAL = 0xCC

from .uart_thread import *
