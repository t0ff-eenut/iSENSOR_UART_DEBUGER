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
# * final update : 2025/09/22
# ******************************************************************************
# */
from .adc_graph_header import *   # 헤더 역할 파일에서 전부 불러오기

A_graph_handle = []
A_graph_data_handle = []
A_graph_occu_handle = []

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

# 공간 만들기
gs_otsu_count = graph_structer(
                                None,   # app
                                None,   # win
                                None,   # plot
                                [],     # curve
                                [],     # A_data_windows
                                0,      # i_data_len
                                )
# 공간 만들기
gs_delta_otsu_count = graph_structer(
                                None,   # app
                                None,   # win
                                None,   # plot
                                [],     # curve
                                [],     # A_data_windows
                                0,      # i_data_len
                                )
# 공간 만들기
gs_occu = graph_structer(
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

A_graph_data_handle.append(gs_otsu_count)
A_graph_data_handle.append(gs_delta_otsu_count)

A_graph_occu_handle.append(gs_occu)


def graph_data_setting():
    global A_graph_handle, A_graph_data_handle, A_graph_occu_handle
    # 각 그래프마다 Data 공간 할당
    try:
        while True:
            if not Q_adc_graph_data_buffer.empty():
                # [DATA[], MIN[], MAX[], MID[], MEAN[], MIN_MAX_CENTER[], OTSU[]]
                A_receive_data = Q_adc_graph_data_buffer.get()
                for i_curve_data_index in range(C_CURVE_DEFINE.GRAPH_START, C_CURVE_DEFINE.NOMAL_GRAPH_SIZE, 1):
                    A_graph_handle[C_GRAPH_DEFINE.ADC_GRAPH].A_data_windows[i_curve_data_index] = A_receive_data[i_curve_data_index]
                for i_curve_data_index in range(C_CURVE_DEFINE.DATA_GRAPH_START, C_CURVE_DEFINE.DATA_GRAPH_SIZE, 1):
                    A_graph_data_handle[C_GRAPH_DATA_DEFINE.OTSU_COUNT].A_data_windows[i_curve_data_index - C_CURVE_DEFINE.DATA_GRAPH_START] = A_receive_data[i_curve_data_index]

            if not Q_adc_delta_graph_data_buffer.empty():
                # [DATA[], MIN[], MAX[], MID[], MEAN[], MIN_MAX_CENTER[], OTSU[]]
                A_receive_data = Q_adc_delta_graph_data_buffer.get()
                for i_curve_data_index in range(C_CURVE_DEFINE.GRAPH_START, C_CURVE_DEFINE.NOMAL_GRAPH_SIZE, 1):
                    A_graph_handle[C_GRAPH_DEFINE.ADC_DELTA_GRAPH].A_data_windows[i_curve_data_index] = A_receive_data[i_curve_data_index]
                    A_graph_handle[C_GRAPH_DEFINE.ADC_DELTA_GRAPH_ZOOM].A_data_windows[i_curve_data_index] = A_receive_data[i_curve_data_index]
                for i_curve_data_index in range(C_CURVE_DEFINE.DATA_GRAPH_START, C_CURVE_DEFINE.DATA_GRAPH_SIZE, 1):
                    A_graph_data_handle[C_GRAPH_DATA_DEFINE.DELTA_OTSU_COUNT].A_data_windows[i_curve_data_index - C_CURVE_DEFINE.DATA_GRAPH_START] = A_receive_data[i_curve_data_index]

                for i_curve_data_index in range(C_CURVE_DEFINE.OCCU_GRAPH_START, C_CURVE_DEFINE.OCCU_GRAPH_SIZE, 1):
                    A_graph_occu_handle[C_GRAPH_OCCUPANCY_DEFINE.OCCUPANCY].A_data_windows[i_curve_data_index - C_CURVE_DEFINE.OCCU_GRAPH_START] = A_receive_data[i_curve_data_index]

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
        print("A_graph_handle - sel_graph_handle.win 시작")
        if sel_graph_handle.win is None:
            print("A_graph_handle - sel_graph_handle.win 시작")
            sel_graph_handle.win = GraphicsLayoutWidget(show=True, title=A_GRAPH_TITLE_DEFINE[sel_graph_handle_num] + " Window")
            print("A_graph_handle - sel_graph_handle.plot 시작")
            # sel_graph_handle.plot  = sel_graph_handle.win.addPlot(title=A_GRAPH_TITLE_DEFINE[sel_graph_handle_num] + " Plot")
            sel_graph_handle.plot = sel_graph_handle.win.addPlot(title="Plot")
            print("A_graph_handle - sel_graph_handle.plot.setXRange 시작")
            sel_graph_handle.plot.setXRange(0, A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num], padding=0)
            print("A_graph_handle - sel_graph_handle.plot.setYRange 시작")
            sel_graph_handle.plot.setYRange(0, A_GRAPH_Y_RANGE_DEFINE[sel_graph_handle_num], padding=0)
        print("A_graph_handle - sel_graph_handle.A_data_windows 시작")
        # 그래프 Data 공간 초기화
        sel_graph_handle.A_data_windows = []
        for i_curve_index in range(C_CURVE_DEFINE.GRAPH_START, C_CURVE_DEFINE.NOMAL_GRAPH_SIZE, 1):
            if len(sel_graph_handle.A_data_windows) <= i_curve_index:
                sel_graph_handle.A_data_windows.append([])

        print("A_graph_handle - sel_graph_handle.curve 시작")
        # 그래프 선 생성
        # sel_graph_handle.curve.append(sel_graph_handle.plot.plot(pen=A_GRAPH_COLOR_DEFINE[0]))
        # 그래프 개수가 적은 경우
        # while len(sel_graph_handle.curve) < len(sel_graph_handle.A_data_windows):
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
        print("A_graph_handle - sel_graph_handle.data_windows_max_text 끝")

    for sel_graph_data_handle_num, sel_graph_data_handle in builtins.enumerate(list(A_graph_data_handle)):
        print("A_graph_data_handle - sel_graph_handle_num :", sel_graph_data_handle_num)
        print("A_graph_data_handle - sel_graph_handle.app 시작")
        sel_graph_data_handle.app = app
        print("A_graph_data_handle - sel_graph_handle.app 끝")

        if sel_graph_data_handle.win is None:
            print("A_graph_data_handle - sel_graph_handle.win 시작")
            sel_graph_data_handle.win = GraphicsLayoutWidget(show=True, title=A_GRAPH_DATA_TITLE_DEFINE[sel_graph_data_handle_num] + " Window")
            print("A_graph_data_handle - sel_graph_handle.plot 시작")
            sel_graph_data_handle.plot = sel_graph_data_handle.win.addPlot(title="Plot")
            print("A_graph_data_handle - sel_graph_handle.plot.setXRange 시작")
            sel_graph_data_handle.plot.setXRange(0, A_GRAPH_DATA_X_RANGE_DEFINE[sel_graph_data_handle_num], padding=0)
            print("A_graph_data_handle - sel_graph_handle.plot.setYRange 시작")
            sel_graph_data_handle.plot.setYRange(0, A_GRAPH_DATA_Y_RANGE_DEFINE[sel_graph_data_handle_num], padding=0)

        print("A_graph_data_handle - sel_graph_handle.A_data_windows 시작")
        # 그래프 Data 공간 초기화
        sel_graph_data_handle.A_data_windows = []
        # for i_curve_index in range(C_CURVE_DEFINE.OTSU_COUNT_CURVE - C_CURVE_DEFINE.DATA_GRAPH_START, C_CURVE_DEFINE.DATA_GRAPH_SIZE - C_CURVE_DEFINE.DATA_GRAPH_START, 1):
        for i_curve_index in range(C_GRAPH_DATA_CURVE_DEFINE.OTSU_COUNT_CURVE, C_GRAPH_DATA_CURVE_DEFINE.DATA_CURVE_DEFINE_ARRAY_SIZE, 1):
            if len(sel_graph_data_handle.A_data_windows) <= i_curve_index:
                sel_graph_data_handle.A_data_windows.append([])

        print("A_graph_data_handle - sel_graph_handle.curve 시작")
        for i_curve_index in range(len(sel_graph_data_handle.A_data_windows)):
            sel_graph_data_handle.curve.append(sel_graph_data_handle.plot.plot(pen=A_GRAPH_DATA_COLOR_DEFINE[i_curve_index]))
        print("A_graph_data_handle - sel_graph_handle.curve 끝")

    # OCCU
    for sel_graph_occu_handle_num, sel_graph_occu_handle in builtins.enumerate(list(A_graph_occu_handle)):
        print("A_graph_occu_handle - sel_graph_handle_num :", sel_graph_occu_handle_num)
        print("A_graph_occu_handle - sel_graph_handle.app 시작")
        sel_graph_occu_handle.app = app
        print("A_graph_occu_handle - sel_graph_handle.app 끝")

        if sel_graph_occu_handle.win is None:
            print("A_graph_occu_handle - sel_graph_handle.win 시작")
            sel_graph_occu_handle.win = GraphicsLayoutWidget(show=True, title=A_GRAPH_OCCUPANCY_TITLE_DEFINE[sel_graph_occu_handle_num] + " Window")
            print("A_graph_occu_handle - sel_graph_handle.plot 시작")
            sel_graph_occu_handle.plot = sel_graph_occu_handle.win.addPlot(title="Plot")
            print("A_graph_occu_handle - sel_graph_handle.plot.setXRange 시작")
            sel_graph_occu_handle.plot.setXRange(0, A_GRAPH_OCCUPANCY_X_RANGE_DEFINE[sel_graph_occu_handle_num], padding=0)
            print("A_graph_occu_handle - sel_graph_handle.plot.setYRange 시작")
            sel_graph_occu_handle.plot.setYRange(0, A_GRAPH_OCCUPANCY_Y_RANGE_DEFINE[sel_graph_occu_handle_num], padding=0)

        print("A_graph_occu_handle - sel_graph_handle.A_data_windows 시작")
        # 그래프 Data 공간 초기화
        sel_graph_occu_handle.A_data_windows = []
        # for i_curve_index in range(C_CURVE_DEFINE.OTSU_COUNT_CURVE - C_CURVE_DEFINE.DATA_GRAPH_START, C_CURVE_DEFINE.DATA_GRAPH_SIZE - C_CURVE_DEFINE.DATA_GRAPH_START, 1):
        for i_curve_index in range(C_GRAPH_OCCUPANCY_CURVE_DEFINE.OTSU_OCCU_CURVE, C_GRAPH_OCCUPANCY_CURVE_DEFINE.OCCUPANCY_CURVE_DEFINE_ARRAY_SIZE, 1):
            if len(sel_graph_occu_handle.A_data_windows) <= i_curve_index:
                sel_graph_occu_handle.A_data_windows.append([])

        print("A_graph_occu_handle - sel_graph_handle.curve 시작")
        for i_curve_index in range(len(sel_graph_occu_handle.A_data_windows)):
            sel_graph_occu_handle.curve.append(sel_graph_occu_handle.plot.plot(pen=A_GRAPH_OCCUPANCY_COLOR_DEFINE[i_curve_index]))
        print("A_graph_occu_handle - sel_graph_handle.curve 끝")


    # def tile_windows(A_graph_handle, cols=2, margin=50, win_w=640, win_h=480, screen_index=1):
    #     app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    #     # 모든 모니터 정보 가져오기
    #     screens = app.screens()
    #     if screen_index >= len(screens):
    #         print(f"모니터 {screen_index} 없음, 기본 모니터 사용")
    #         screen = app.primaryScreen()
    #     else:
    #         screen = screens[screen_index]

    #     rect = screen.availableGeometry()  # 선택한 모니터의 좌표계
    #     x0, y0 = rect.x() + margin, rect.y() + margin

    #     for idx in range(len(A_graph_handle)):
    #         win = A_graph_handle[idx].win
    #         col = idx % cols
    #         row = idx // cols
    #         x = x0 + col * (win_w + margin)
    #         y = y0 + row * (win_h + margin)
    #         win.setGeometry(x, y, win_w, win_h)
    #         win.show()
    # 모니터별 배치된 윈도우 개수를 저장
    

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

    # 첫 번째 모니터 → 데이터 그래프
    tile_windows(A_graph_data_handle, cols=2, margin=50, win_w=1024, win_h=480, screen_index=0)

    # 첫 번째 모니터 → 점유율 그래프 (위에 이어서 배치됨, 안 겹침)
    tile_windows(A_graph_occu_handle, cols=2, margin=50, win_w=1024, win_h=480, screen_index=0)

    
    data_process_thread = Thread(name="GRAPH DATA SETTING THREAD", target=data_process, daemon=1)
    data_process_thread.start()
    graph_data_setting_thread = Thread(name="GRAPH DATA SETTING THREAD", target=graph_data_setting, daemon=1)
    graph_data_setting_thread.start()

    print("graph_init 끝")

    return app

def graph_refresh():
    global A_graph_handle, A_graph_data_handle, A_graph_occu_handle
    try:
        # 모든 그래프에 대해서
        for sel_graph_handle_num, sel_graph_handle in builtins.enumerate(list(A_graph_handle)):
            for sel_curve_num, sel_curve in builtins.enumerate(list(sel_graph_handle.curve)):
                # print("A_graph_handle ", sel_graph_handle.A_data_windows[sel_curve_num])
                sel_curve.setData(sel_graph_handle.A_data_windows[sel_curve_num])   # [][..., ..., ....]

            sel_graph_handle.last_data_text.setText(f"RAW/Delta(White): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.DATA_CURVE])-1]}\n"
                                                    +f"MIN MAX 중앙값(LightGreen): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MIN_MAX_CENTER_CURVE][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MIN_MAX_CENTER_CURVE])-1]}\n"
                                                    +f"중앙값(Orange): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MID_CURVE][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MID_CURVE])-1]}\n"
                                                    +f"평균값(Green): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MEAN_CURVE][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MEAN_CURVE])-1]}\n"
                                                    +f"Otsu(Red): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.OTSU_CURVE][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.OTSU_CURVE])-1]}\n"
                                                    +f"MOVING HIGH(Yellow): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MOVING_AVG_STD_HIGH][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MOVING_AVG_STD_HIGH])-1]}\n"
                                                    +f"MOVING LOW(Yellow): {sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MOVING_AVG_STD_LOW][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MOVING_AVG_STD_LOW])-1]}\n"
                                                    )
            # sel_graph_handle.last_data_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 5, A_GRAPH_Y_RANGE_DEFINE[sel_graph_handle_num] / 2)
            sel_graph_handle.last_data_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 5, A_GRAPH_Y_RANGE_DEFINE[sel_graph_handle_num] * 0.65)

            i_last_min_data = sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MIN_CURVE][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MIN_CURVE]) - 1]
            sel_graph_handle.data_windows_min_line.setPos(i_last_min_data)
            sel_graph_handle.data_windows_min_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 1, i_last_min_data - 200)
            sel_graph_handle.data_windows_min_text.setText(f"MIN_{A_GRAPH_TITLE_DEFINE[sel_graph_handle_num]}: {i_last_min_data}")

            i_last_mid_data = sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MID_CURVE][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MID_CURVE]) - 1]
            sel_graph_handle.data_windows_mid_line.setPos(i_last_mid_data)
            sel_graph_handle.data_windows_mid_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 1, i_last_mid_data - 50)
            sel_graph_handle.data_windows_mid_text.setText(f"MID_{A_GRAPH_TITLE_DEFINE[sel_graph_handle_num]}: {i_last_mid_data}")

            i_last_max_data = sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MAX_CURVE][len(sel_graph_handle.A_data_windows[C_CURVE_DEFINE.MAX_CURVE]) - 1]
            sel_graph_handle.data_windows_max_line.setPos(i_last_max_data)
            sel_graph_handle.data_windows_max_text.setPos(A_GRAPH_X_RANGE_DEFINE[sel_graph_handle_num] - 1, i_last_max_data)
            sel_graph_handle.data_windows_max_text.setText(f"MAX_{A_GRAPH_TITLE_DEFINE[sel_graph_handle_num]}: {i_last_max_data}")


        for sel_graph_data_handle_num, sel_graph_data_handle in builtins.enumerate(list(A_graph_data_handle)):
            for sel_curve_num, sel_curve in builtins.enumerate(list(sel_graph_data_handle.curve)):
                # print("A_graph_data_handle", sel_graph_data_handle.A_data_windows[sel_curve_num])
                sel_curve.setData(sel_graph_data_handle.A_data_windows[sel_curve_num])   # [][..., ..., ....]

        for sel_graph_occu_handle_num, sel_graph_occu_handle in builtins.enumerate(list(A_graph_occu_handle)):
            for sel_curve_num, sel_curve in builtins.enumerate(list(sel_graph_occu_handle.curve)):
                # print("A_graph_data_handle", sel_graph_occu_handle.A_data_windows[sel_curve_num])
                sel_curve.setData(sel_graph_occu_handle.A_data_windows[sel_curve_num])   # [][..., ..., ....]

        sleep(0.001)

    except Exception:   
        pass