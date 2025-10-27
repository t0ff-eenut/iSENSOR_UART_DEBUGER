# /*
# ******************************************************************************
# * File Name          : debuger_start.c
# * Description        : UART RECEIVE PROGRAM
# ******************************************************************************
# * ESP32에서 UART를 통해 수신한 DATA를 그래프로 출력하기 위한 프로그램
# * UART 초기화 및 데이터 송신 기능을 포함
# * UART 데이터 전송 규격 : 8N1 (8비트 데이터, 패리티 없음, 스톱 비트 1)
# * UART 데이터 전송 규칙 : / SIGNAL(8b) / ADC(16b) / VOLTAGE(16b) / checksum(8b) / DUMMY(8b) /
# ******************************************************************************

# ******************************************************************************
# * first update : 2025/08/21
# ******************************************************************************
# * final update : 2025/10/21
# ******************************************************************************
# */


from custom_uart.uart_header import *
from adc_graph.adc_graph_header import *

# MODE            = TEST
# MODE            = UART
# BAUD_RATE_SEL   = BAUD_RATE_115200
# BAUD_RATE_SEL   = BAUD_RATE_576000

def handle_sigint(sig, frame):
    print("Ctrl+C 감지 → 안전 종료")
    QtWidgets.QApplication.quit()

if __name__ == '__main__':
    print("UART 초기화",end="\n\n")
    if MODE == UART:
        serial_comport_handle = uart_init()
        print("UART Receive Thread 시작",end="\n\n")
        print("BAUD_RATE_SEL : ", BAUD_RATE_SEL, end="\n\n")
        uart_receive_thread = Thread(name="UART RECEIVE THREAD", target=uart_receive, daemon=1)
        uart_receive_thread.start()
    
    print("UART Receive Data Process Thread 시작",end="\n\n")
    uart_receive_data_process_thread = Thread(name="UART RECEIVE DATA PROCESS THREAD", target=uart_receive_data_process_thread, daemon=1)
    uart_receive_data_process_thread.start()
################## GRAPH SETTING ##############################
    # gs = graph_init()
    app = graph_init()


    # 🔽 여기에서 시그널 핸들러 등록
    signal.signal(signal.SIGINT, handle_sigint)

    timer = QtCore.QTimer()
    timer.timeout.connect(graph_refresh)
    # timer.start(10)
    timer.start(50)

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("main keyboard")
################## GRAPH SETTING ##############################
