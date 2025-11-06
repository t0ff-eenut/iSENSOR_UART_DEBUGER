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
####################################################
A_bandfilter_graph_object = []
####################################################

def data_process():
    global A_adc_graph_object, A_adc_delta_graph_object, A_bandfilter_graph_object
    for i_curve_index in range(C_CURVE_DEFINE.DATA_CURVE, C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE, 1):
        
        if i_curve_index == C_CURVE_DEFINE.DATA_CURVE:
            if len(A_adc_graph_object) <= i_curve_index:
                A_adc_graph_object.append([])
####################################################
            if len(A_bandfilter_graph_object) <= i_curve_index:
                A_bandfilter_graph_object.append([])
####################################################
        if len(A_adc_delta_graph_object) <= i_curve_index:
            A_adc_delta_graph_object.append([])


    # # TP1을 위함
    # A_adc_delta_graph_object.append([])

    while True:
        if not Q_data_buffer.empty():
            # print("Q_data_buffer.qsize() : ", Q_data_buffer.qsize())
            A_receive_data = Q_data_buffer.get()
            
            A_adc_graph_object[C_CURVE_DEFINE.DATA_CURVE] = A_receive_data[C_RECEIVE_QUEUE_DEFINE.A_ADC_BUF]
            Q_adc_graph_data_buffer.put(A_adc_graph_object)

            # i_tp2 = A_receive_data[C_RECEIVE_QUEUE_DEFINE.TP2]
            A_adc_delta_graph_object[C_CURVE_DEFINE.DATA_CURVE] = A_receive_data[C_RECEIVE_QUEUE_DEFINE.A_ADC_DELTA_BUF]
            A_adc_delta_graph_object[C_CURVE_DEFINE.OCCU_CURVE] = A_receive_data[C_RECEIVE_QUEUE_DEFINE.A_OCCU_BUF]
            A_adc_delta_graph_object[C_CURVE_DEFINE.TP1_CURVE]  = A_receive_data[C_RECEIVE_QUEUE_DEFINE.TP1]
            # A_adc_delta_graph_object[C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE+1]  = i_tp2
            Q_adc_delta_graph_data_buffer.put(A_adc_delta_graph_object)
            
####################################################
            A_bandfilter_graph_object[C_CURVE_DEFINE.DATA_CURVE] = A_receive_data[C_RECEIVE_QUEUE_DEFINE.A_BANDFILTER_BUF]
            Q_bandfilter_graph_data_buffer.put(A_bandfilter_graph_object)
####################################################

        sleep(0.001)
