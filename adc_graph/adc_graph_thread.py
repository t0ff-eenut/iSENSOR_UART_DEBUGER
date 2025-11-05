# /*
# ******************************************************************************
# * File Name          : adc_graph_thread.py
# * Description        : 
# ******************************************************************************
# * ESP32에서 UART를 통해 수신한 DATA를 그래프로 출력하기 위한 프로그램
# ******************************************************************************

# ******************************************************************************
# * first update : 2025/08/24
# ******************************************************************************
# * final update : 2025/10/28
# ******************************************************************************
# */
from .adc_graph_header import *   # 헤더 역할 파일에서 전부 불러오기

A_graph_handle = []

# 공간 만들기
gs_adc = graph_structer(
                        None,   # app
                        None,   # win
                        None,   # plot
                        [],     # curve
                        [],     # A_data_windows
                        0,      # i_data_len
                        )

# 공간 만들기
gs_adc_delta = graph_structer(
                                None,   # app
                                None,   # win
                                None,   # plot
                                [],     # curve
                                [],     # A_data_windows
                                0,      # i_data_len
                                )

# 공간 만들기
gs_adc_delta_zoom = graph_structer(
                                None,   # app
                                None,   # win
                                None,   # plot
                                [],     # curve
                                [],     # A_data_windows
                                0,      # i_data_len
                                )

A_graph_handle.append(gs_adc)
A_graph_handle.append(gs_adc_delta)
A_graph_handle.append(gs_adc_delta_zoom)

i_tp1 = 0
i_tp2 = 0

def graph_data_setting():
    global A_graph_handle, A_graph_data_handle, A_graph_occu_handle, i_tp1, i_tp2
    # 각 그래프마다 Data 공간 할당
    try:
        while True:
            if not Q_adc_graph_data_buffer.empty():
                # print("Q_adc_graph_data_buffer.qsize() : ", Q_adc_graph_data_buffer.qsize())
                A_receive_data = Q_adc_graph_data_buffer.get()
                for i_curve_data_index in range(C_CURVE_DEFINE.GRAPH_START, C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE, 1):
                    A_graph_handle[C_GRAPH_DEFINE.ADC_GRAPH].A_data_windows[i_curve_data_index] = A_receive_data[i_curve_data_index]

            if not Q_adc_delta_graph_data_buffer.empty():
                # print("Q_adc_delta_graph_data_buffer.qsize() : ", Q_adc_delta_graph_data_buffer.qsize())
                A_receive_data = Q_adc_delta_graph_data_buffer.get()
                for i_curve_data_index in range(C_CURVE_DEFINE.GRAPH_START, C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE, 1):
                    # print("i_curve_data_index : ", i_curve_data_index)
                    # print("C_CURVE_DEFINE.OCCU_CURVE : ", C_CURVE_DEFINE.OCCU_CURVE)
                    if i_curve_data_index == C_CURVE_DEFINE.OCCU_CURVE:
                        scale_factor = A_GRAPH_Y_RANGE_DEFINE[C_GRAPH_DEFINE.ADC_DELTA_GRAPH]
                        A_occu_data = [x * scale_factor for x in A_receive_data[C_CURVE_DEFINE.OCCU_CURVE]]
                        A_graph_handle[C_GRAPH_DEFINE.ADC_DELTA_GRAPH].A_data_windows[i_curve_data_index] = A_occu_data
                        # print("A_graph_handle[C_GRAPH_DEFINE.ADC_DELTA_GRAPH].A_data_windows[i_curve_data_index] : ", A_graph_handle[C_GRAPH_DEFINE.ADC_DELTA_GRAPH].A_data_windows[i_curve_data_index])

                        scale_factor = A_GRAPH_Y_RANGE_DEFINE[C_GRAPH_DEFINE.ADC_DELTA_GRAPH_ZOOM]
                        A_occu_zoom_data = [x * scale_factor for x in A_receive_data[C_CURVE_DEFINE.OCCU_CURVE]]
                        A_graph_handle[C_GRAPH_DEFINE.ADC_DELTA_GRAPH_ZOOM].A_data_windows[i_curve_data_index] = A_occu_zoom_data
                        # print("A_graph_handle[C_GRAPH_DEFINE.ADC_DELTA_GRAPH_ZOOM].A_data_windows[i_curve_data_index] : ", A_graph_handle[C_GRAPH_DEFINE.ADC_DELTA_GRAPH_ZOOM].A_data_windows[i_curve_data_index])

                    else:
                        A_graph_handle[C_GRAPH_DEFINE.ADC_DELTA_GRAPH].A_data_windows[i_curve_data_index] = A_receive_data[i_curve_data_index]
                        A_graph_handle[C_GRAPH_DEFINE.ADC_DELTA_GRAPH_ZOOM].A_data_windows[i_curve_data_index] = A_receive_data[i_curve_data_index]

                i_tp1 = A_receive_data[C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE]
                i_tp2 = A_receive_data[C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE+1]

            sleep(0.001)

    except Exception:   
        pass

_screen_window_count = defaultdict(int)
def graph_init():
    global _screen_window_count, A_graph_handle, A_graph_data_handle, A_graph_occu_handle
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    print("graph_init 시작")
    for sel_graph_handle_num, sel_graph_handle in builtins.enumerate(list(A_graph_handle)):
        print("A_graph_handle - sel_graph_handle_num :", sel_graph_handle_num)

        print("A_graph_handle - sel_graph_handle.app 시작")
        sel_graph_handle.app = app
        if sel_graph_handle.win is None:
            print("A_graph_handle - sel_graph_handle.win 시작")
            sel_graph_handle.win = GraphicsLayoutWidget(show=True, title=A_GRAPH_TITLE_DEFINE[sel_graph_handle_num] + " Window")
            print("A_graph_handle - sel_graph_handle.plot 시작")
            sel_graph_handle.plot = sel_graph_handle.win.addPlot(title="Plot")
            print("A_graph_handle - sel_graph_handle.plot.setXRange 시작")
            sel_graph_handle.plot.setXRange(0, A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num], padding=0)
            print("A_graph_handle - sel_graph_handle.plot.setYRange 시작")
            sel_graph_handle.plot.setYRange(0, A_GRAPH_Y_RANGE_DEFINE[sel_graph_handle_num], padding=0)
        print("A_graph_handle - sel_graph_handle.A_data_windows 시작")
        # 그래프 Data 공간 초기화
        sel_graph_handle.A_data_windows = []
        for i_curve_index in range(C_CURVE_DEFINE.GRAPH_START, C_CURVE_DEFINE.CURVE_DEFINE_ARRAY_SIZE, 1):
            if len(sel_graph_handle.A_data_windows) <= i_curve_index:
                sel_graph_handle.A_data_windows.append([])

        print("A_graph_handle - sel_graph_handle.curve 시작")
        for i_curve_index in range(len(sel_graph_handle.A_data_windows)):
            sel_graph_handle.curve.append(sel_graph_handle.plot.plot(pen=A_GRAPH_COLOR_DEFINE[i_curve_index]))

        print("A_graph_handle - sel_graph_handle.last_data_text 시작")
        # 마지막 데이터 텍스트 생성
        sel_graph_handle.last_data_text = TextItem(html='<span style="color: yellow; font-size: 14pt;">0</span>', anchor=(1,1))
        sel_graph_handle.plot.addItem(sel_graph_handle.last_data_text)  # 그래프에 추가
        sel_graph_handle.last_data_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 5, 300)         # x, y 위치 (조정 가능)

        print("A_graph_handle - sel_graph_handle.data_windows_min_line 시작")
        # 가로 줄 생성
        sel_graph_handle.data_windows_min_line = InfiniteLine(pos=200, angle=0, movable=False, pen='g')
        sel_graph_handle.plot.addItem(sel_graph_handle.data_windows_min_line)
        print("A_graph_handle - sel_graph_handle.data_windows_min_text 시작")
        # 텍스트 생성
        sel_graph_handle.data_windows_min_text = TextItem(html='<span style="color: yellow; font-size: 14pt;">0</span>', anchor=(1,1))
        sel_graph_handle.plot.addItem(sel_graph_handle.data_windows_min_text)
        sel_graph_handle.data_windows_min_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 5, (d_ADC_MAX_RANGE / 2) - 500)     # x, y 위치 (조정 가능)

        print("A_graph_handle - sel_graph_handle.data_windows_mid_line 시작")
        # 가로 줄 생성
        sel_graph_handle.data_windows_mid_line = InfiniteLine(pos=300, angle=0, movable=False, pen='g')
        sel_graph_handle.plot.addItem(sel_graph_handle.data_windows_mid_line)
        print("A_graph_handle - sel_graph_handle.data_windows_mid_text 시작")
        # 텍스트 생성
        sel_graph_handle.data_windows_mid_text = TextItem(html='<span style="color: yellow; font-size: 14pt;">0</span>', anchor=(1,1))
        sel_graph_handle.plot.addItem(sel_graph_handle.data_windows_mid_text)
        sel_graph_handle.data_windows_mid_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 5, (d_ADC_MAX_RANGE / 2) - 500)     # x, y 위치 (조정 가능)

        print("A_graph_handle - sel_graph_handle.data_windows_max_line 시작")
        # 가로 줄 생성
        sel_graph_handle.data_windows_max_line = InfiniteLine(pos=400, angle=0, movable=False, pen='g')
        sel_graph_handle.plot.addItem(sel_graph_handle.data_windows_max_line)
        print("A_graph_handle - sel_graph_handle.data_windows_max_text 시작")
        # 텍스트 생성
        sel_graph_handle.data_windows_max_text = TextItem(html='<span style="color: yellow; font-size: 14pt;">0</span>', anchor=(1,1))
        sel_graph_handle.plot.addItem(sel_graph_handle.data_windows_max_text)  # 그래프에 추가
        sel_graph_handle.data_windows_max_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 5, (d_ADC_MAX_RANGE / 2) - 500)     # x, y 위치 (조정 가능)

        if sel_graph_handle_num > 0:
            print("A_graph_handle - sel_graph_handle.data_windows_tp1_line 시작")
            # 가로 줄 생성
            sel_graph_handle.data_windows_tp1_line = InfiniteLine(pos=400, angle=0, movable=False, pen='r')
            sel_graph_handle.plot.addItem(sel_graph_handle.data_windows_tp1_line)
            print("A_graph_handle - sel_graph_handle.data_windows_tp1_text 시작")
            # 텍스트 생성
            sel_graph_handle.data_windows_tp1_text = TextItem(html='<span style="color: yellow; font-size: 14pt;">0</span>', anchor=(1,1))
            sel_graph_handle.plot.addItem(sel_graph_handle.data_windows_tp1_text)  # 그래프에 추가
            sel_graph_handle.data_windows_tp1_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 5, (d_ADC_MAX_RANGE / 2) - 500)     # x, y 위치 (조정 가능)

        print("A_graph_handle - sel_graph_handle 끝")

    def tile_windows(A_graph_handle, cols=2, margin=50, win_w=640, win_h=480, screen_index=0):
        global _screen_window_count

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        screens = app.screens()
        if screen_index >= len(screens):
            print(f"모니터 {screen_index} 없음, 기본 모니터 사용")
            screen = app.primaryScreen()
        else:
            screen = screens[screen_index]

        rect = screen.availableGeometry()
        x0, y0 = rect.x() + margin, rect.y() + margin

        # 이미 배치된 개수만큼 오프셋 row 계산
        start_idx = _screen_window_count[screen_index]

        for idx, handle in builtins.enumerate(A_graph_handle):
            win = handle.win
            abs_idx = start_idx + idx   # 전체 index
            col = abs_idx % cols
            row = abs_idx // cols
            x = x0 + col * (win_w + margin)
            y = y0 + row * (win_h + margin)
            win.setGeometry(x, y, win_w, win_h)
            win.show()

        _screen_window_count[screen_index] += len(A_graph_handle)

    # # 두 번째 모니터에 띄우기 (screen_index=1)
    # tile_windows(A_graph_handle, cols=1, margin=50, win_w=1024, win_h=480, screen_index=1)
    # tile_windows(A_graph_data_handle, cols=1, margin=50, win_w=1024, win_h=480, screen_index=0)
    # tile_windows(A_graph_occu_handle, cols=1, margin=50, win_w=1024, win_h=480, screen_index=0)
    # 두 번째 모니터 → 첫 번째 윈도우 배치
    tile_windows(A_graph_handle, cols=1, margin=50, win_w=1024, win_h=480, screen_index=1)

    # # 첫 번째 모니터 → 데이터 그래프
    # tile_windows(A_graph_data_handle, cols=2, margin=50, win_w=1024, win_h=480, screen_index=0)

    # # 첫 번째 모니터 → 점유율 그래프 (위에 이어서 배치됨, 안 겹침)
    # tile_windows(A_graph_occu_handle, cols=2, margin=50, win_w=1024, win_h=480, screen_index=0)

    
    data_process_thread = Thread(name="GRAPH DATA SETTING THREAD", target=data_process, daemon=1)
    data_process_thread.start()
    graph_data_setting_thread = Thread(name="GRAPH DATA SETTING THREAD", target=graph_data_setting, daemon=1)
    graph_data_setting_thread.start()

    print("graph_init 끝")

    return app

def graph_refresh():
    global A_graph_handle, A_graph_data_handle, A_graph_occu_handle, i_tp1, i_tp2
    try:
        # 모든 그래프에 대해서
        for sel_graph_handle_num, sel_graph_handle in builtins.enumerate(list(A_graph_handle)):
            for sel_curve_num, sel_curve in builtins.enumerate(list(sel_graph_handle.curve)):
                sel_curve.setData(sel_graph_handle.A_data_windows[sel_curve_num])   # [][..., ..., ....]
                
            if sel_graph_handle_num > 0:
                sel_graph_handle.last_data_text.setText(
                    # f"RAW/Delta(White): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE])-1]}\n"
                    # f"전체 배열: {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]}\n"
                    f" ".join([str(x) for x in sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]])+"\n"
                    +f" ".join([str(x) for x in sel_graph_handle.A_data_windows[C_CURVE_DEFINE.OCCU_CURVE]])+"\n"
                    +f"RAW/Delta(White): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE][0]}\n"
                    +f"MIN MAX 중앙값(Blue): {((int(min(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE])) + int(max(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]))) / 2)}\n"
                    +f"중앙값(Yellow): {int(median(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]))}\n"
                    +f"평균값(Orange): {int(mean(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]))}\n"
                    +f"TP1(Red): {i_tp1}\n"
                    +f"TP2: {i_tp2}\n"
                    )
            else:
                sel_graph_handle.last_data_text.setText(
                    # f"RAW/Delta(White): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE])-1]}\n"
                    # f"전체 배열: {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]}\n"
                    f" ".join([str(x) for x in sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]])+"\n"
                    +f"RAW/Delta(White): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE][0]}\n"
                    +f"MIN MAX 중앙값(Blue): {((int(min(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE])) + int(max(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]))) / 2)}\n"
                    +f"중앙값(Yellow): {int(median(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]))}\n"
                    +f"평균값(Orange): {int(mean(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]))}\n"
                    )
                
            sel_graph_handle.last_data_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 5, A_GRAPH_Y_RANGE_DEFINE[sel_graph_handle_num] * 0.65)

            i_last_min_data = int(min(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]))
            sel_graph_handle.data_windows_min_line.setPos(i_last_min_data)
            sel_graph_handle.data_windows_min_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 1, i_last_min_data - 200)
            sel_graph_handle.data_windows_min_text.setText(f"MIN_{A_GRAPH_TITLE_DEFINE[sel_graph_handle_num]}: {i_last_min_data}")

            i_last_mid_data = int(median(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]))
            sel_graph_handle.data_windows_mid_line.setPos(i_last_mid_data)
            sel_graph_handle.data_windows_mid_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 1, i_last_mid_data - 50)
            sel_graph_handle.data_windows_mid_text.setText(f"MID_{A_GRAPH_TITLE_DEFINE[sel_graph_handle_num]}: {i_last_mid_data}")

            i_last_max_data = int(max(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE]))
            sel_graph_handle.data_windows_max_line.setPos(i_last_max_data)
            sel_graph_handle.data_windows_max_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 1, i_last_max_data)
            sel_graph_handle.data_windows_max_text.setText(f"MAX_{A_GRAPH_TITLE_DEFINE[sel_graph_handle_num]}: {i_last_max_data}")
            
            if sel_graph_handle_num > 0:
                sel_graph_handle.data_windows_tp1_line.setPos(i_tp1)
                sel_graph_handle.data_windows_tp1_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 1, i_tp1)
                sel_graph_handle.data_windows_tp1_text.setText(f"TP1_{A_GRAPH_TITLE_DEFINE[sel_graph_handle_num]}: {i_tp1}")

        sleep(0.001)

    except Exception:   
        pass