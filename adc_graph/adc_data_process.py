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
# * final update : 2025/09/23
# ******************************************************************************
# */

from .adc_data_process_header import *   # 헤더 역할 파일에서 전부 불러오기

# [DATA[], MIN[], MAX[], MID[], MEAN[], MIN_MAX_CENTER[], OTSU[]]
A_adc_graph_data        = []
A_adc_delta_graph_data  = []
######
A_adc_delta_graph_bg_data  = []
######
def otsu(graph_sel):
    global A_adc_graph_data, A_adc_delta_graph_data, A_adc_delta_graph_bg_data

    A_i_adc_val_count = [0] * d_ADC_MAX_RANGE
    i_data_len = 0

    if graph_sel == C_GRAPH_DEFINE.ADC_GRAPH:
        i_data_len = len(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE])
        for i_data_sel in range(i_data_len):
            A_i_adc_val_count[A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE][i_data_sel]] += 1
    elif graph_sel == C_GRAPH_DEFINE.ADC_DELTA_GRAPH:
        i_data_len = len(A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE])
        for i_data_sel in range(i_data_len):
            A_i_adc_val_count[A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE][i_data_sel]] += 1
        ######
        i_bg_data_len = len(A_adc_delta_graph_bg_data)
        for i_data_sel in range(i_bg_data_len):
            A_i_adc_val_count[A_adc_delta_graph_bg_data[i_data_sel]] += 1
        i_data_len += i_bg_data_len
        ######
    
    # 전체 값들에 대한 값 카운팅과 가중치 파악
    i_adc_val_all_count = 0
    i_adc_weight_sum    = 0
    for i_adc_val_sel in range(d_ADC_MAX_RANGE):
        i_adc_val_all_count += A_i_adc_val_count[i_adc_val_sel]
        i_adc_weight_sum += A_i_adc_val_count[i_adc_val_sel] * i_adc_val_sel      # 전체 가중치 파악
        # 모든 데이터를 확인했다면
        if i_adc_val_all_count >= i_data_len:
            break
    # 입력이 비었을 경우
    if i_adc_val_all_count == 0:
        return 0;

    i_background_weight_sum     = 0     # 배경 클래스의 가중치
    i_background_count          = 0     # 배경 클래스의 ADC Value 수
    i_occupancy_count           = 0     # 대상 클래스의 ADC Value 수

    d_background_weight_average = 0     # 배경 클래스의 ADC 평균
    d_occupancy_weight_average  = 0     # 대상 클래스의 ADC 평균
    d_var_between               = 0     # 배경, 대상 클래스간 분산도

    d_max_var                   = -1.0  #
    d_max_std                   = -1.0  #
    i_max_th                    = 0

    for i_adc_val_sel in range(d_ADC_MAX_RANGE):
        # 각 ADC 값마다 배경과 대상을 나누어 분산값 확인
        i_background_count += A_i_adc_val_count[i_adc_val_sel]
        # 값이 없으면 Pass
        if i_background_count == 0:
            continue
        
        # 배경과 대상의 count 값을 분할
        i_occupancy_count = i_adc_val_all_count - i_background_count

        # 값이 없으면 종료
        if i_occupancy_count == 0:
            break

        i_background_weight_sum += i_adc_val_sel * A_i_adc_val_count[i_adc_val_sel]                                                                 # 배경에 대한 가중치 파악
        d_background_weight_average = i_background_weight_sum / i_background_count                                                                  # 배경으로 선택한 값들의 평균
        d_occupancy_weight_average  = (i_adc_weight_sum - i_background_weight_sum) / i_occupancy_count                                              # 전체 가중치에서 배경 가중치를 뺀 나머지(대상) 가중치
        d_var_between               = i_background_count * i_occupancy_count * ((d_background_weight_average - d_occupancy_weight_average) ** 2)    # 배경과 재실의 분산 [w_b * w_f * (μ_b - μ_f)^2]
        d_std_between               = math.sqrt(d_var_between)

        if d_var_between > d_max_var:
            d_max_var = d_var_between
            d_max_std = d_std_between
            i_max_th = i_adc_val_sel

    return [i_max_th, d_max_var, d_max_std, A_i_adc_val_count]


d_double = 1.0
def moving_avg_std_threshold(graph_sel):
    global d_double, A_adc_graph_data, A_adc_delta_graph_data
    
    i_mean = 0
    i_variance = 0
    i_std = 0
    i_th_h = 0
    i_th_l = 0

    if graph_sel == C_GRAPH_DEFINE.ADC_GRAPH:
        A_temp = A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE]

    elif graph_sel == C_GRAPH_DEFINE.ADC_DELTA_GRAPH:
        A_temp = A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE]

    i_mean = sum(A_temp) / len(A_temp)
    i_variance = sum((x - i_mean) ** 2 for x in A_temp) / len(A_temp)
    i_std = i_variance ** 0.5

    # i_th_h = i_mean + (0.8 * i_std)
    # i_th_l = i_mean - (0.8 * i_std)
    # i_th_h = i_mean + (1.2 * i_std)
    # i_th_l = i_mean - (1.2 * i_std)
    # i_th_h = i_mean + (1.9 * i_std)
    # i_th_l = i_mean - (1.9 * i_std)
    # i_th_h = i_mean + (2.2 * i_std)
    # i_th_l = i_mean - (2.2 * i_std)
    i_th_h = i_mean + (d_double * i_std)
    i_th_l = i_mean - (d_double * i_std)

    return [i_th_h, i_th_l]

i_moving_std_occu_count = 0
i_moving_std_noise_count = 0
def data_process():
    global d_double, i_moving_std_occu_count, i_moving_std_noise_count, A_adc_graph_data, A_adc_delta_graph_data, A_adc_delta_graph_bg_data

    for i_curve_index in range(C_CURVE_DEFINE.DATA_CURVE, C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE, 1):
        if len(A_adc_graph_data) <= i_curve_index:
            A_adc_graph_data.append([])
        if len(A_adc_delta_graph_data) <= i_curve_index:
            A_adc_delta_graph_data.append([])

    while True:
        if not Q_data_buffer.empty():
            # print("len DATA_CURVE : ", len(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE]))

            # Data 개수가 d_WINDOW_SIZE 이상인 경우
            if len(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE]) > d_WINDOW_SIZE:
                # 1~100 개만 유지
                for i_curve_index in range(C_CURVE_DEFINE.DATA_CURVE, C_CURVE_DEFINE.OCCU_GRAPH_SIZE, 1):
                    # A_adc_graph_data[i_curve_index] = A_adc_graph_data[i_curve_index][1:d_WINDOW_SIZE]
                    A_adc_graph_data[i_curve_index] = A_adc_graph_data[i_curve_index][-d_WINDOW_SIZE:]

            A_receive_data = Q_data_buffer.get()

            A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE].append(A_receive_data[C_RECEIVE_QUEUE_DEFINE.RAW_ADC])
            A_adc_graph_data[C_CURVE_DEFINE.MIN_CURVE].append(int(min(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE])))
            A_adc_graph_data[C_CURVE_DEFINE.MAX_CURVE].append(int(max(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE])))
            A_adc_graph_data[C_CURVE_DEFINE.MID_CURVE].append(int(median(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE])))
            A_adc_graph_data[C_CURVE_DEFINE.MEAN_CURVE].append(int(mean(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE])))
            A_adc_graph_data[C_CURVE_DEFINE.MIN_MAX_CENTER_CURVE].append(((int(min(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE])) + int(max(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE]))) / 2))
            A_i_otsu_resualt = otsu(C_GRAPH_DEFINE.ADC_GRAPH)
            A_adc_graph_data[C_CURVE_DEFINE.OTSU_CURVE].append(A_i_otsu_resualt[C_OTSU_RETURN_DEFINE.MAX_TH])
            A_i_moving_avg_std_resualt = moving_avg_std_threshold(C_GRAPH_DEFINE.ADC_GRAPH)
            A_adc_graph_data[C_CURVE_DEFINE.MOVING_AVG_STD_HIGH].append(A_i_moving_avg_std_resualt[C_MOVING_AVG_STD_RETURN_DEFINE.TH_HIGH])
            A_adc_graph_data[C_CURVE_DEFINE.MOVING_AVG_STD_LOW].append(A_i_moving_avg_std_resualt[C_MOVING_AVG_STD_RETURN_DEFINE.TH_LOW])
            
            A_adc_graph_data[C_CURVE_DEFINE.OTSU_OCCU_CURVE].append(int(0))
            A_adc_graph_data[C_CURVE_DEFINE.MOVING_STD_OCCU_CURVE].append(int(0))

            A_adc_graph_data[C_CURVE_DEFINE.OTSU_COUNT_CURVE] = A_i_otsu_resualt[C_OTSU_RETURN_DEFINE.OTSU_COUNT]

            #queue 입력 = A_input_data = [DATA[], MIN[], MAX[], MID[], MEAN[], MIN_MAX_CENTER[], OTSU[]]
            Q_adc_graph_data_buffer.put(A_adc_graph_data)

            
            if len(A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE]) >= d_WINDOW_SIZE:
                # 1~100 개만 유지
                for i_curve_index in range(C_CURVE_DEFINE.DATA_CURVE, C_CURVE_DEFINE.OCCU_GRAPH_SIZE, 1):
                    # A_adc_delta_graph_data[i_curve_index] = A_adc_delta_graph_data[i_curve_index][1:d_WINDOW_SIZE]
                    A_adc_delta_graph_data[i_curve_index] = A_adc_delta_graph_data[i_curve_index][-d_WINDOW_SIZE:]
            #####
            if len(A_adc_delta_graph_bg_data) >= d_WINDOW_SIZE:
                # 1~100 개만 유지
                
                A_adc_delta_graph_bg_data = A_adc_delta_graph_bg_data[-d_WINDOW_SIZE:]
            #####

            if len(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE]) >= 2:
                i_adc_delta = abs(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE][len(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE]) - 2] 
                                - A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE][len(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE]) - 1])
            else:
                # i_adc_delta = A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE][len(A_adc_graph_data[C_CURVE_DEFINE.DATA_CURVE]) - 1]
                i_adc_delta = 0

            A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE].append(i_adc_delta)
            A_adc_delta_graph_data[C_CURVE_DEFINE.MIN_CURVE].append(int(min(A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE])))
            A_adc_delta_graph_data[C_CURVE_DEFINE.MAX_CURVE].append(int(max(A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE])))
            A_adc_delta_graph_data[C_CURVE_DEFINE.MID_CURVE].append(int(median(A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE])))
            A_adc_delta_graph_data[C_CURVE_DEFINE.MEAN_CURVE].append(int(mean(A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE])))
            A_adc_delta_graph_data[C_CURVE_DEFINE.MIN_MAX_CENTER_CURVE].append(((int(min(A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE])) + int(max(A_adc_delta_graph_data[C_CURVE_DEFINE.DATA_CURVE]))) / 2))
            A_i_otsu_resualt = otsu(C_GRAPH_DEFINE.ADC_DELTA_GRAPH)
            A_adc_delta_graph_data[C_CURVE_DEFINE.OTSU_CURVE].append(A_i_otsu_resualt[C_OTSU_RETURN_DEFINE.MAX_TH])
            A_i_moving_avg_std_resualt = moving_avg_std_threshold(C_GRAPH_DEFINE.ADC_DELTA_GRAPH)
            A_adc_delta_graph_data[C_CURVE_DEFINE.MOVING_AVG_STD_HIGH].append(A_i_moving_avg_std_resualt[C_MOVING_AVG_STD_RETURN_DEFINE.TH_HIGH])
            A_adc_delta_graph_data[C_CURVE_DEFINE.MOVING_AVG_STD_LOW].append(A_i_moving_avg_std_resualt[C_MOVING_AVG_STD_RETURN_DEFINE.TH_LOW])

            A_adc_delta_graph_data[C_CURVE_DEFINE.OTSU_OCCU_CURVE].append(int(i_adc_delta >= A_i_otsu_resualt[C_OTSU_RETURN_DEFINE.MAX_TH]))
            A_adc_delta_graph_data[C_CURVE_DEFINE.MOVING_STD_OCCU_CURVE].append(int(i_adc_delta >= A_i_moving_avg_std_resualt[C_MOVING_AVG_STD_RETURN_DEFINE.TH_HIGH])*2)

            ####
            if i_adc_delta < A_i_otsu_resualt[C_OTSU_RETURN_DEFINE.MAX_TH]:
                A_adc_delta_graph_bg_data.append(i_adc_delta)
            ####

            # if i_adc_delta >= A_i_moving_avg_std_resualt[C_MOVING_AVG_STD_RETURN_DEFINE.TH_HIGH]:
            #     print("MOVING_STD_OCCU 가 ON 일 때")
            #     print("occu_count 증가")
            #     i_moving_std_occu_count += 1
            #     if i_adc_delta < 150 and ((i_moving_std_occu_count >= 1 and i_moving_std_noise_count >= 1) or (i_moving_std_noise_count >= 10)):
            #         print("노이즈일 가능성이 높음")
            #         d_double += 0.1
            #         print("d_double 0.1 상승: ", d_double)

            #     i_moving_std_noise_count = 0
            #     if i_moving_std_occu_count >= 2:
            #         print("움직임일 가능성이 높음")

            # else:
            #     i_moving_std_occu_count = 0
            #     i_moving_std_noise_count += 1


                
            A_adc_delta_graph_data[C_CURVE_DEFINE.OTSU_COUNT_CURVE] = A_i_otsu_resualt[C_OTSU_RETURN_DEFINE.OTSU_COUNT]

            #queue 입력 = A_input_data = [DATA[], MIN[], MAX[], MID[], MEAN[], MIN_MAX_CENTER[], OTSU[]]
            Q_adc_delta_graph_data_buffer.put(A_adc_delta_graph_data)

        sleep(0.001)
