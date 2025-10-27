import sys, threading                       
from PyQt6 import QtWidgets
# import pyqtgraph           
from pyqtgraph import *
from statistics import *
import builtins
import math   # math 모듈 불러오기
from collections import defaultdict

from custom_queue.queue_header import *

d_WINDOW_SIZE       = 30
d_ADC_MAX_RANGE     = 4096
# d_VOLTAGE_MAX_RANGE = 3200
d_GRAPH_X_RANGE     = d_WINDOW_SIZE

# Graph Recive 구조체
class graph_structer:
    def __init__(self, app, win, plot, curve, A_data_windows, i_data_len):
        self.app            = app
        self.win            = win
        self.plot           = plot
        self.curve          = curve
        self.A_data_windows = A_data_windows
        self.i_data_len     = i_data_len

class C_GRAPH_DEFINE(IntEnum):
    ADC_GRAPH               = 0
    ADC_DELTA_GRAPH         = 1
    ADC_DELTA_GRAPH_ZOOM    = 2

A_GRAPH_X_RANGE_DEFINE = [d_GRAPH_X_RANGE      # ADC
                          ,d_GRAPH_X_RANGE     # ADC_DELTA
                          ,d_GRAPH_X_RANGE     # ADC_DELTA
                          ]   
A_GRAPH_Y_RANGE_DEFINE = [d_ADC_MAX_RANGE      # ADC
                          ,d_ADC_MAX_RANGE     # ADC_DELTA
                          ,300                 # ADC_DELTA
                          ]    
A_GRAPH_TITLE_DEFINE = ["ADC" 
                        ,"ADC_DELTA"
                        ,"ADC_DELTA_ZOOM"
                        ]

class C_CURVE_DEFINE(IntEnum):
    GRAPH_START             = 0
    DATA_CURVE              = GRAPH_START
    MIN_CURVE               = DATA_CURVE            + 1
    MAX_CURVE               = MIN_CURVE             + 1
    MID_CURVE               = MAX_CURVE             + 1
    MEAN_CURVE              = MID_CURVE             + 1
    MIN_MAX_CENTER_CURVE    = MEAN_CURVE            + 1
    OTSU_CURVE              = MIN_MAX_CENTER_CURVE  + 1
    MOVING_AVG_STD_HIGH     = OTSU_CURVE            + 1
    MOVING_AVG_STD_LOW      = MOVING_AVG_STD_HIGH   + 1
    NOMAL_GRAPH_SIZE        = MOVING_AVG_STD_LOW    + 1

    OCCU_GRAPH_START        = NOMAL_GRAPH_SIZE
    OTSU_OCCU_CURVE         = OCCU_GRAPH_START
    MOVING_STD_OCCU_CURVE   = OTSU_OCCU_CURVE + 1
    OCCU_GRAPH_SIZE         = MOVING_STD_OCCU_CURVE + 1

    DATA_GRAPH_START        = OCCU_GRAPH_SIZE
    OTSU_COUNT_CURVE        = DATA_GRAPH_START
    DATA_GRAPH_SIZE         = OTSU_COUNT_CURVE + 1

    CURVE_DEFINE_ARRAY_SIZE = DATA_GRAPH_SIZE

A_GRAPH_COLOR_DEFINE = ['white'         # DATA_CURVE
                        ,'gray'         # MIN_CURVE
                        ,'gray'         # MAX_CURVE
                        ,'blue'         # MID_CURVE             // 배열 중앙값
                        ,'green'        # MEAN_CURVE            // 배열 평균값
                        ,'light green'  # MIN_MAX_CENTER_CURVE  // 배열 MIN MAX 중앙값
                        ,'red'          # OTSU_CURVE            // 배열 OTSU
                        ,'yellow'       # MOVING_AVG_STD_HIGH
                        ,'yellow'       # MOVING_AVG_STD_LOW 
                        ]

class C_GRAPH_OCCUPANCY_DEFINE(IntEnum):
    OCCUPANCY               = 0

A_GRAPH_OCCUPANCY_X_RANGE_DEFINE = [d_GRAPH_X_RANGE
                                    ]   
A_GRAPH_OCCUPANCY_Y_RANGE_DEFINE = [2
                                    ]    
A_GRAPH_OCCUPANCY_TITLE_DEFINE = ["OCCUPANCY"
                                    ]
class C_GRAPH_OCCUPANCY_CURVE_DEFINE(IntEnum):
    OTSU_OCCU_CURVE                     = 0
    MOVING_AVG_STD_OCCU_CURVE           = 1
    OCCUPANCY_CURVE_DEFINE_ARRAY_SIZE   = MOVING_AVG_STD_OCCU_CURVE  + 1

A_GRAPH_OCCUPANCY_COLOR_DEFINE = ['red'
                                , 'yellow'
                                ]

class C_GRAPH_DATA_DEFINE(IntEnum):
    OTSU_COUNT              = 0
    DELTA_OTSU_COUNT        = 1
A_GRAPH_DATA_X_RANGE_DEFINE = [d_ADC_MAX_RANGE
                            ,d_ADC_MAX_RANGE
                            ]   
A_GRAPH_DATA_Y_RANGE_DEFINE = [int(d_WINDOW_SIZE * 0.6)
                            , int(d_WINDOW_SIZE * 0.6)
                            ]    
A_GRAPH_DATA_TITLE_DEFINE = ["OTSU COUNT"
                            , "DELTA_OTSU COUNT"
                            ]
class C_GRAPH_DATA_CURVE_DEFINE(IntEnum):
    OTSU_COUNT_CURVE                = 0
    DATA_CURVE_DEFINE_ARRAY_SIZE    = OTSU_COUNT_CURVE  + 1

A_GRAPH_DATA_COLOR_DEFINE = ['gray'
                            ]






# graph array define
class C_GRAPH_LINE_DEFINE(IntEnum):
    MIN = 0
    MID = 1
    MAX = 2

d_LINE_SIZE = len(C_GRAPH_LINE_DEFINE)

from .adc_data_process_header import *
from .adc_graph_thread import *

