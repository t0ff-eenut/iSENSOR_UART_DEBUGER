# iSENSOR UART Debugger

PyQt6와 pyqtgraph를 사용한 UART 데이터 시각화 및 AI 분석 도구

---

## 환경 설정

### 1. 가상환경 생성

```bash
python -m venv .venv
```

### 2. 가상환경 활성화

**Windows (PowerShell)**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (CMD)**
```cmd
.venv\Scripts\activate.bat
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 실행

```bash
python debugger_start.py
```

---

## 주요 의존성

| 패키지 | 용도 |
|---|---|
| `PyQt6` | GUI 프레임워크 |
| `pyqtgraph` | 실시간 그래프 |
| `pyserial` | UART 시리얼 통신 |
| `bleak` | BLE 통신 |
| `numpy` | 수치 연산 |
| `scikit-learn` | SVM 분류 |
| `torch` | MLP 신경망 학습 |

---

## 변경 이력

[CHANGELOG.md](CHANGELOG.md) 참고
