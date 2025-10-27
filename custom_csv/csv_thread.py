# /*
# ******************************************************************************
# * File Name          : csv_thread.py
# * Description        : CSV SAVER MODULE
# ******************************************************************************
# * CSV 파일로 저장하기 위한 기능을 포함
# * 
# ******************************************************************************

# ******************************************************************************
# * first update : 2025/08/25
# ******************************************************************************
# * final update : 2025/08/25
# ******************************************************************************
# */

from .csv_header import *   # 헤더 역할 파일에서 전부 불러오기

################## CSV INIT ##############################
def stream_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row['timestamp'])
            adc = int(row['adc'])
            voltage = int(row['voltage'])
            # 처리...
            yield ts, adc, voltage

def read_csv():
    df = pd.read_csv('logs/20250825_120000_data.csv', parse_dates=['timestamp'])
    # 필요한 컬럼만 선택
    df = df[['timestamp','adc','voltage','adc_delta','voltage_delta']]