# /*
# ******************************************************************************
# * File Name          : uart_thread.py
# * Description        : UART RECEIVE MODULE
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

from .uart_header import *   # 헤더 역할 파일에서 전부 불러오기


################## UART INIT ##############################
def uart_init():
    global serial_component_handle

    A_comports              = comports()
    A_comport_devices       = []
    A_esp32_component_port  = []
    s_comport_name          = ""

    for comport in A_comports:
        print("#################", comport.name, "#################")
        print("name : ",            comport.name)
        print("device : ",          comport.device)
        print("description : ",     comport.description)
        print("hwid : ",            comport.hwid)
        print("vid : ",             comport.vid)
        print("pid : ",             comport.pid)
        print("serial_number : ",   comport.serial_number)
        print("location : ",        comport.location)
        print("manufacturer : ",    comport.manufacturer)
        print("product : ",         comport.product)
        print("interface : ",       comport.interface)
        # name :  COM5
        # device :  COM5
        # description :  USB-Enhanced-SERIAL CH343(COM5)
        # hwid :  USB VID:PID=1A86:55D3 SER=58CF028302 LOCATION=1-3
        # vid :  6790
        # pid :  21971
        # serial_number :  58CF028302
        # location :  1-3
        # manufacturer :  wch.cn
        # product :  None
        # interface :  None
        # ['USB', 'VID:PID=1A86:55D3', 'SER=58CF028302', 'LOCATION=1-3']
        
        # /dev/cu.wchusbserial2110
        
        A_comport_devices.append(comport.device)
        
        if len(comport.hwid.split(" ")) > 1:                                        # ['USB', 'VID:PID=1A86:55D3', 'SER=58CF028302', 'LOCATION=1-3']
            if len(comport.hwid.split(" ")[1].split("=")) > 1:                      # ['VID:PID', '1A86:7523']
                print("")
                print("if ESP32 ? = ", comport.hwid.split(" ")[1])                  # 'VID:PID=1A86:55D3'
                A_esp32_component_port.append(comport.device)
        print("")

    if len(A_esp32_component_port) == 1:
        s_comport_name = A_esp32_component_port[0]
    else:
        print("Connected COM ports: " + str(A_comport_devices))
        s_sel_COM = input()
        if len(s_sel_COM) < 3:
            s_comport_name = "COM"+str(s_sel_COM)
        else:
            s_comport_name = str(s_sel_COM)
    print("")
    print("################# Connected ", s_comport_name, "#################")
    print("")
    serial_component_handle = Serial(s_comport_name, BAUD_RATE_SEL)
    return serial_component_handle
################## UART INIT ##############################

################## UART Recive Thread ##############################
def uart_receive():
    while True:
        try:
            Q_uart_buffer.put(serial_component_handle.read())
        except KeyboardInterrupt:
            break
################## UART Recive Thread ##############################

################## UART Checksum Process ##############################
def receive_uart_adc_structer_checksum(receive_uart_adc_structer_value):

    # bytes.fromhex("00"),    # ui8_signal
    # bytes.fromhex("00"),    # ui8_group_1_length
    # bytes.fromhex("00"),    # ui8_group_1_8bit_length
    # [],                     # ui8_adc
    # [],                     # ui8_voltage
    # [],                     # ui8_tp1
    # bytes.fromhex("00"),    # ui8_group_2_length
    # bytes.fromhex("00"),    # ui8_group_2_8bit_length
    # [],                     # ui8_tp2
    # [],                     # ui8_switch_status
    # [],                     # ui8_occu_triger
    # bytes.fromhex("00"),    # ui8_group_3_length
    # bytes.fromhex("00"),    # ui8_group_3_8bit_length
    # [],                     # ui8_adc_buf
    # [],                     # ui8_adc_delta_buf
    # bytes.fromhex("00"),    # ui8_group_4_length
    # bytes.fromhex("00"),    # ui8_group_4_8bit_length
    # [],                     # ui8_occu_buf
    # bytes.fromhex("00"),    # ui8_chksum
    # bytes.fromhex("00"),    # ui8_dummy

    # XOR 기반 체크섬 계산
    checksum = 0
    
    if isinstance(receive_uart_adc_structer_value.ui8_signal, bytes):
        checksum ^= receive_uart_adc_structer_value.ui8_signal[0]
    else:
        checksum ^= receive_uart_adc_structer_value.ui8_signal

    if isinstance(receive_uart_adc_structer_value.ui8_group_1_length, bytes):
        checksum ^= receive_uart_adc_structer_value.ui8_group_1_length[0]
    else:
        checksum ^= receive_uart_adc_structer_value.ui8_group_1_length
    if isinstance(receive_uart_adc_structer_value.ui8_group_1_8bit_length, bytes):
        checksum ^= receive_uart_adc_structer_value.ui8_group_1_8bit_length[0]
    else:
        checksum ^= receive_uart_adc_structer_value.ui8_group_1_8bit_length
    for ui8_adc_8byte in receive_uart_adc_structer_value.ui8_adc:
        if isinstance(ui8_adc_8byte, bytes):
            checksum ^= ui8_adc_8byte[0]
        else:
            checksum ^= ui8_adc_8byte
    for ui8_voltage_8byte in receive_uart_adc_structer_value.ui8_voltage:
        if isinstance(ui8_voltage_8byte, bytes):
            checksum ^= ui8_voltage_8byte[0]
        else:
            checksum ^= ui8_voltage_8byte
    for ui8_tp1_8byte in receive_uart_adc_structer_value.ui8_tp1:
        if isinstance(ui8_tp1_8byte, bytes):
            checksum ^= ui8_tp1_8byte[0]
        else:
            checksum ^= ui8_tp1_8byte

    if isinstance(receive_uart_adc_structer_value.ui8_group_2_length, bytes):
        checksum ^= receive_uart_adc_structer_value.ui8_group_2_length[0]
    else:
        checksum ^= receive_uart_adc_structer_value.ui8_group_2_length
    if isinstance(receive_uart_adc_structer_value.ui8_group_2_8bit_length, bytes):
        checksum ^= receive_uart_adc_structer_value.ui8_group_2_8bit_length[0]
    else:
        checksum ^= receive_uart_adc_structer_value.ui8_group_2_8bit_length
    for ui8_tp2_8byte in receive_uart_adc_structer_value.ui8_tp2:
        if isinstance(ui8_tp2_8byte, bytes):
            checksum ^= ui8_tp2_8byte[0]
        else:
            checksum ^= ui8_tp2_8byte
    for ui8_switch_status_8byte in receive_uart_adc_structer_value.ui8_switch_status:
        if isinstance(ui8_switch_status_8byte, bytes):
            checksum ^= ui8_switch_status_8byte[0]
        else:
            checksum ^= ui8_switch_status_8byte
    for ui8_occu_triger_8byte in receive_uart_adc_structer_value.ui8_occu_triger:
        if isinstance(ui8_occu_triger_8byte, bytes):
            checksum ^= ui8_occu_triger_8byte[0]
        else:
            checksum ^= ui8_occu_triger_8byte

    if isinstance(receive_uart_adc_structer_value.ui8_group_3_length, bytes):
        checksum ^= receive_uart_adc_structer_value.ui8_group_3_length[0]
    else:
        checksum ^= receive_uart_adc_structer_value.ui8_group_3_length
    if isinstance(receive_uart_adc_structer_value.ui8_group_3_8bit_length, bytes):
        checksum ^= receive_uart_adc_structer_value.ui8_group_3_8bit_length[0]
    else:
        checksum ^= receive_uart_adc_structer_value.ui8_group_3_8bit_length
    for ui8_adc_buf_8byte in receive_uart_adc_structer_value.ui8_adc_buf:
        if isinstance(ui8_adc_buf_8byte, bytes):
            checksum ^= ui8_adc_buf_8byte[0]
        else:
            checksum ^= ui8_adc_buf_8byte
    for ui8_adc_delta_buf_8byte in receive_uart_adc_structer_value.ui8_adc_delta_buf:
        if isinstance(ui8_adc_delta_buf_8byte, bytes):
            checksum ^= ui8_adc_delta_buf_8byte[0]
        else:
            checksum ^= ui8_adc_delta_buf_8byte

    if isinstance(receive_uart_adc_structer_value.ui8_group_4_length, bytes):
        checksum ^= receive_uart_adc_structer_value.ui8_group_4_length[0]
    else:
        checksum ^= receive_uart_adc_structer_value.ui8_group_4_length
    if isinstance(receive_uart_adc_structer_value.ui8_group_4_8bit_length, bytes):
        checksum ^= receive_uart_adc_structer_value.ui8_group_4_8bit_length[0]
    else:
        checksum ^= receive_uart_adc_structer_value.ui8_group_4_8bit_length
    for ui8_occu_buf_8byte in receive_uart_adc_structer_value.ui8_occu_buf:
        if isinstance(ui8_occu_buf_8byte, bytes):
            checksum ^= ui8_occu_buf_8byte[0]
        else:
            checksum ^= ui8_occu_buf_8byte

    return checksum
################## UART Checksum Process ##############################

################## UART Recive Frame ##############################
def uart_receive_data_process_thread():
    # 공간 만들기
    rus = receive_uart_adc_structer(
                                    bytes.fromhex("00"),    # ui8_signal
                                    bytes.fromhex("00"),    # ui8_group_1_length
                                    bytes.fromhex("00"),    # ui8_group_1_8bit_length
                                    [],                     # ui8_adc
                                    [],                     # ui8_voltage
                                    [],                     # ui8_tp1
                                    bytes.fromhex("00"),    # ui8_group_2_length
                                    bytes.fromhex("00"),    # ui8_group_2_8bit_length
                                    [],                     # ui8_tp2
                                    [],                     # ui8_switch_status
                                    [],                     # ui8_occu_triger
                                    bytes.fromhex("00"),    # ui8_group_3_length
                                    bytes.fromhex("00"),    # ui8_group_3_8bit_length
                                    [],                     # ui8_adc_buf
                                    [],                     # ui8_adc_delta_buf
                                    bytes.fromhex("00"),    # ui8_group_4_length
                                    bytes.fromhex("00"),    # ui8_group_4_8bit_length
                                    [],                     # ui8_occu_buf
                                    bytes.fromhex("00"),    # ui8_chksum
                                    bytes.fromhex("00"),    # ui8_dummy
                                    )
    i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.SIGNAL


    i_adc = 0
    i_voltage = 0
    i_adc_range = 300
    i_adc_max_range = (1500 + i_adc_range)
    i_adc_min_range = (1500 - i_adc_range)
    
    while True:
        try:
            if MODE == UART:
                if not Q_uart_buffer.empty():
                    byte_uart_read_8bit = Q_uart_buffer.get()   ## read CMD Signal(Byte단위[8bit])
                    ##############################
                    # 들어오는 Bit
                    # # print("RAW DATA : ", byte_uart_read_8bit)
                    # # print("UART DATA : ", byte_uart_read_8bit[0], " ", hex(byte_uart_read_8bit[0]))
                    # print("UART DATA : ", byte_uart_read_8bit[0], " ", hex(byte_uart_read_8bit[0]),end="\t")
                    ##############################

                    ########## Process Level ##########
                    match i_switch_level:
                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.SIGNAL:
                            ########## Signal 판단 ##########
                            match byte_uart_read_8bit[0]:
                                case C_UART_SIGNAL.ADC_SIGNAL:
                                    # # print("ADC signal received")
                                    # print("<- SIGNAL")
                                    rus.ui8_signal = byte_uart_read_8bit[0]
                                    i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_1_LENGTH
                                case _:
                                    # # print("Unknown signal received")
                                    pass

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_1_LENGTH:
                            ########## Bit Length 판단 ##########
                            # print("<- GROUP_1_LENGTH")
                            rus.ui8_group_1_length = byte_uart_read_8bit[0]
                            i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_1_BIT_LENGTH

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_1_BIT_LENGTH:
                            # print("<- GROUP_1_BIT_LENGTH")
                            ########## Bit Length 판단 ##########
                            rus.ui8_group_1_8bit_length = byte_uart_read_8bit[0]
                            i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.ADC

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.ADC:
                            # print("<- ADC")
                            ########## ADC 판단 ##########
                            rus.ui8_adc.append(byte_uart_read_8bit[0])
                            if len(rus.ui8_adc) == rus.ui8_group_1_8bit_length:
                                i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.VOLTAGE

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.VOLTAGE:
                            # print("<- VOLTAGE")
                            ########## Voltage 판단 ##########
                            rus.ui8_voltage.append(byte_uart_read_8bit[0])
                            if len(rus.ui8_voltage) == rus.ui8_group_1_8bit_length:
                                i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.TP1

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.TP1:
                            # print("<- TP1")
                            ########## Voltage 판단 ##########
                            rus.ui8_tp1.append(byte_uart_read_8bit[0])
                            if len(rus.ui8_tp1) == rus.ui8_group_1_8bit_length:
                                i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_2_LENGTH


                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_2_LENGTH:
                            # print("<- GROUP_2_LENGTH")
                            ########## Bit Length 판단 ##########
                            rus.ui8_group_2_length = byte_uart_read_8bit[0]
                            i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_2_BIT_LENGTH

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_2_BIT_LENGTH:
                            # print("<- GROUP_2_BIT_LENGTH")
                            ########## Bit Length 판단 ##########
                            rus.ui8_group_2_8bit_length = byte_uart_read_8bit[0]
                            i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.TP2

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.TP2:
                            # print("<- TP2")
                            ########## ADC 판단 ##########
                            rus.ui8_tp2.append(byte_uart_read_8bit[0])
                            if len(rus.ui8_tp2) == rus.ui8_group_2_8bit_length:
                                i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.SWITCH_STATUS

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.SWITCH_STATUS:
                            # print("<- SWITCH_STATUS")
                            ########## Voltage 판단 ##########
                            rus.ui8_switch_status.append(byte_uart_read_8bit[0])
                            if len(rus.ui8_switch_status) == rus.ui8_group_2_8bit_length:
                                i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.OCCU_TRIGER

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.OCCU_TRIGER:
                            # print("<- OCCU_TRIGER")
                            ########## Voltage 판단 ##########
                            rus.ui8_occu_triger.append(byte_uart_read_8bit[0])
                            if len(rus.ui8_occu_triger) == rus.ui8_group_2_8bit_length:
                                i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_3_LENGTH


                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_3_LENGTH:
                            # print("<- GROUP_3_LENGTH")
                            ########## Bit Length 판단 ##########
                            rus.ui8_group_3_length = byte_uart_read_8bit[0]
                            i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_3_BIT_LENGTH

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_3_BIT_LENGTH:
                            # print("<- GROUP_3_BIT_LENGTH")
                            ########## Bit Length 판단 ##########
                            rus.ui8_group_3_8bit_length = byte_uart_read_8bit[0]
                            i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.ADC_BUF

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.ADC_BUF:
                            # print("<- ADC_BUF")
                            ########## ADC 판단 ##########
                            rus.ui8_adc_buf.append(byte_uart_read_8bit[0])
                            if len(rus.ui8_adc_buf) == rus.ui8_group_3_8bit_length:
                                i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.ADC_DELTA_BUF

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.ADC_DELTA_BUF:
                            # print("<- ADC_DELTA_BUF")
                            ########## Voltage 판단 ##########
                            rus.ui8_adc_delta_buf.append(byte_uart_read_8bit[0])
                            if len(rus.ui8_adc_delta_buf) == rus.ui8_group_3_8bit_length:
                                i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_4_LENGTH



                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_4_LENGTH:
                            # print("<- GROUP_4_LENGTH")
                            ########## Bit Length 판단 ##########
                            rus.ui8_group_4_length = byte_uart_read_8bit[0]
                            i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_4_BIT_LENGTH

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.GROUP_4_BIT_LENGTH:
                            # print("<- GROUP_4_BIT_LENGTH")
                            ########## Bit Length 판단 ##########
                            rus.ui8_group_4_8bit_length = byte_uart_read_8bit[0]
                            i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.OCCU_BUF

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.OCCU_BUF:
                            # print("<- OCCU_BUF")
                            ########## Voltage 판단 ##########
                            rus.ui8_occu_buf.append(byte_uart_read_8bit[0])
                            if len(rus.ui8_occu_buf) == rus.ui8_group_4_8bit_length:
                                i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.CHECKSUM


                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.CHECKSUM:
                            # print("<- CHECKSUM")
                            ########## Voltage 판단 ##########
                            rus.ui8_chksum = byte_uart_read_8bit[0]
                            i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.DUMMY

                        case C_UART_RECEIVE_DATA_PROCESS_LEVEL.DUMMY:
                            # print("<- DUMMY")
                            ########## Dummy 판단 ##########
                            rus.ui8_dummy = byte_uart_read_8bit[0]

                            if receive_uart_adc_structer_checksum(rus) == rus.ui8_chksum:
                                # bytes.fromhex("00"),    # ui8_signal
                                # bytes.fromhex("00"),    # ui8_group_1_length
                                # bytes.fromhex("00"),    # ui8_group_1_8bit_length
                                # [],                     # ui8_adc
                                # [],                     # ui8_voltage
                                # [],                     # ui8_tp1
                                # bytes.fromhex("00"),    # ui8_group_2_length
                                # bytes.fromhex("00"),    # ui8_group_2_8bit_length
                                # [],                     # ui8_tp2
                                # [],                     # ui8_switch_status
                                # [],                     # ui8_occu_triger
                                # bytes.fromhex("00"),    # ui8_group_3_length
                                # bytes.fromhex("00"),    # ui8_group_3_8bit_length
                                # [],                     # ui8_adc_buf
                                # [],                     # ui8_adc_delta_buf
                                # bytes.fromhex("00"),    # ui8_group_4_length
                                # bytes.fromhex("00"),    # ui8_group_4_8bit_length
                                # [],                     # ui8_occu_buf
                                # bytes.fromhex("00"),    # ui8_chksum
                                # bytes.fromhex("00"),    # ui8_dummy

                                # print("CHKSUM OK")
                                # print("rus.ui8_signal : ", rus.ui8_signal)
                                # print("rus.ui8_group_1_length : ", rus.ui8_group_1_length)
                                # print("rus.ui8_group_1_8bit_length : ", rus.ui8_group_1_8bit_length)
                                # print("rus.ui8_adc : ", rus.ui8_adc)
                                # print("rus.ui8_voltage : ", rus.ui8_voltage)
                                # print("rus.ui8_tp1 : ", rus.ui8_tp1)
                                # print("rus.ui8_group_2_length : ", rus.ui8_group_2_length)
                                # print("rus.ui8_group_2_8bit_length : ", rus.ui8_group_2_8bit_length)
                                # print("rus.ui8_tp2 : ", rus.ui8_tp2)
                                # print("rus.ui8_switch_status : ", rus.ui8_switch_status)
                                # print("rus.ui8_occu_triger : ", rus.ui8_occu_triger)
                                # print("rus.ui8_group_3_length : ", rus.ui8_group_3_length)
                                # print("rus.ui8_group_3_8bit_length : ", rus.ui8_group_3_8bit_length)
                                # print("rus.ui8_adc_buf : ", rus.ui8_adc_buf)
                                # print("rus.ui8_adc_delta_buf : ", rus.ui8_adc_delta_buf)
                                # print("rus.ui8_group_4_length : ", rus.ui8_group_4_length)
                                # print("rus.ui8_group_4_8bit_length : ", rus.ui8_group_4_8bit_length)
                                # print("rus.ui8_occu_buf : ", rus.ui8_occu_buf)
                                # print("rus.ui8_chksum : ", rus.ui8_chksum)
                                # print("rus.ui8_dummy : ", rus.ui8_dummy)

                                A_receive_data = []
                                i_adc = 0
                                i_voltage = 0
                                i_tp1 = 0
                                for i in range(rus.ui8_group_1_8bit_length):
                                    i_adc       = i_adc     | (rus.ui8_adc[i]       << (8 * i))
                                    i_voltage   = i_voltage | (rus.ui8_voltage[i]   << (8 * i))
                                    i_tp1       = i_tp1     | (rus.ui8_tp1[i]       << (8 * i))
                                A_receive_data.append(i_adc)
                                A_receive_data.append(i_voltage)
                                A_receive_data.append(i_tp1)
                                # A_receive_data.append(b_refresh)
                                Q_data_buffer.put(A_receive_data)
                            # else:
                                # print("CHKSUM Level Error -> Go SIGNAL")

                            i_switch_level = C_UART_RECEIVE_DATA_PROCESS_LEVEL.SIGNAL
        
                            # 배열 초기화
                            rus.ui8_adc             = []
                            rus.ui8_voltage         = []
                            rus.ui8_tp1             = []
                            rus.ui8_tp2             = []
                            rus.ui8_switch_status   = []
                            rus.ui8_occu_triger     = []
                            rus.ui8_adc_buf         = []
                            rus.ui8_adc_delta_buf   = []
                            rus.ui8_occu_buf        = []
                        case _:
                            # # print("Unknown signal received")
                            pass
                    # print("")

            elif MODE == TEST:
                A_receive_data = []

                i_adc = randint(i_adc_min_range, i_adc_max_range)
                i_voltage = (3200 / 4096) * i_adc

                A_receive_data.append(i_adc)
                A_receive_data.append(i_voltage)
                Q_graph_buffer.put(A_receive_data)

            sleep(1 / (1000 * 1000))

        except KeyboardInterrupt:
            break