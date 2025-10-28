# /*
# ******************************************************************************
# * File Name          : adc_graph_thread.py
# * Description        : 
# ******************************************************************************
# * 
# ******************************************************************************

# ******************************************************************************
# * first update : 2025/09/23
# ******************************************************************************
# * final update : 2025/10/28
# ******************************************************************************
# */

from .adc_data_process_header import *   # 헤더 역할 파일에서 전부 불러오기

A_adc_graph_object        = []
A_adc_delta_graph_object  = []

def data_process():
    global A_adc_graph_object, A_adc_delta_graph_object
    for i_curve_index in range(C_CURVE_DEFINE.DATA_CURVE, C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE + 1, 1):
        if len(A_adc_graph_object) <= i_curve_index:
            A_adc_graph_object.append([])
        if len(A_adc_delta_graph_object) <= i_curve_index:
            A_adc_delta_graph_object.append([])
    # TP1을 위함
    A_adc_delta_graph_object.append([])

    while True:
        if not Q_data_buffer.empty():
            # if len(A_adc_graph_object[C_CURVE_DEFINE.DATA_CURVE]) > d_WINDOW_SIZE:
            #     # 1~100 개만 유지
            #     for i_curve_index in range(C_CURVE_DEFINE.DATA_CURVE, C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE, 1):
            #         A_adc_graph_object[i_curve_index] = A_adc_graph_object[i_curve_index][-d_WINDOW_SIZE:]

            A_receive_data = Q_data_buffer.get()
            # A_adc_graph_object[C_CURVE_DEFINE.DATA_CURVE].append(A_receive_data[C_RECEIVE_QUEUE_DEFINE.RAW_ADC])
            A_adc_graph_object[C_CURVE_DEFINE.DATA_CURVE] = A_receive_data[C_RECEIVE_QUEUE_DEFINE.A_ADC_BUF]
            Q_adc_graph_data_buffer.put(A_adc_graph_object)

            
            # if len(A_adc_delta_graph_object[C_CURVE_DEFINE.DATA_CURVE]) >= d_WINDOW_SIZE:
            #     for i_curve_index in range(C_CURVE_DEFINE.DATA_CURVE, C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE, 1):
            #         A_adc_delta_graph_object[i_curve_index] = A_adc_delta_graph_object[i_curve_index][-d_WINDOW_SIZE:]

            # if len(A_adc_graph_object[C_CURVE_DEFINE.DATA_CURVE]) >= 2:
            #     i_adc_delta = abs(A_adc_graph_object[C_CURVE_DEFINE.DATA_CURVE][len(A_adc_graph_object[C_CURVE_DEFINE.DATA_CURVE]) - 2] 
            #                     - A_adc_graph_object[C_CURVE_DEFINE.DATA_CURVE][len(A_adc_graph_object[C_CURVE_DEFINE.DATA_CURVE]) - 1])
            # else:
            #     i_adc_delta = 0

            i_tp1 = A_receive_data[C_RECEIVE_QUEUE_DEFINE.TP1]
            i_tp2 = A_receive_data[C_RECEIVE_QUEUE_DEFINE.TP2]

            # A_adc_delta_graph_object[C_CURVE_DEFINE.DATA_CURVE].append(i_adc_delta)
            A_adc_delta_graph_object[C_CURVE_DEFINE.DATA_CURVE] = A_receive_data[C_RECEIVE_QUEUE_DEFINE.A_ADC_DELTA_BUF]
            A_adc_delta_graph_object[C_CURVE_DEFINE.OCCU_CURVE] = A_receive_data[C_RECEIVE_QUEUE_DEFINE.A_OCCU_BUF]
            
            A_adc_delta_graph_object[C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE] = i_tp1
            A_adc_delta_graph_object[C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE+1] = i_tp2

            Q_adc_delta_graph_data_buffer.put(A_adc_delta_graph_object)

        sleep(0.001)
