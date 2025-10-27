from .adc_graph_header import *

class C_RECEIVE_QUEUE_DEFINE(IntEnum):
    RAW_ADC     = 0
    RAW_VOLTAGE = 1
    TP1         = 2

class C_OTSU_RETURN_DEFINE(IntEnum):
    MAX_TH      = 0
    MAX_VAR     = 1
    MAX_STD     = 2
    OTSU_COUNT  = 3

class C_MOVING_AVG_STD_RETURN_DEFINE(IntEnum):
    TH_HIGH     = 0
    TH_LOW      = 1

# d_ADC_RANGE = 4096

from .adc_data_process import *

