# iSENSOR UART Debugger

PyQt6와 pyqtgraph를 사용한 UART 데이터 시각화 및 AI 분석 도구

---

## 환경 설정

> **Python 버전 주의**
> - GPU(CUDA) 가속 MLP 학습을 사용하려면 반드시 **Python 3.12** 환경이 필요합니다.  
>   PyTorch CUDA 공식 휠이 Python ≤ 3.12 까지만 제공됩니다.
> - GPU가 없는 환경이라면 어떤 Python 버전이든 무관합니다.

---

### 방법 A — 자동 설치 스크립트 (권장)

`setup.ps1`이 GPU 유무를 자동 감지하여 적합한 torch 빌드를 설치합니다.

```powershell
.\setup.ps1
```

스크립트 동작 순서:
1. Python 3.12 미설치 시 winget으로 자동 설치
2. `.venv` 가상환경 생성 (Python 3.12)
3. NVIDIA GPU 감지 → GPU 빌드 / 미감지 → CPU 빌드 torch 설치
4. `requirements.txt` 나머지 의존성 설치

---

### 방법 B — 수동 설치

#### 1. Python 3.12 설치 (GPU 사용 시 필수)

```powershell
winget install Python.Python.3.12
```

> GPU가 없다면 기존 Python을 그대로 사용해도 됩니다.

#### 2. 가상환경 생성

**GPU 사용 — Python 3.12 지정**
```powershell
py -3.12 -m venv .venv
```

**CPU 전용 — 버전 무관**
```powershell
python -m venv .venv
```

#### 3. 가상환경 활성화

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

#### 4. 의존성 설치

**GPU(CUDA 12.4) — Python 3.12 환경**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
```

**CPU 전용**
```bash
pip install -r requirements.txt
```

> 실행 후 MLP Training 패널 하단 GPU 상태가 🟢이면 GPU 학습 활성화된 것입니다.

#### 5. 실행

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
| `torch` | MLP 신경망 학습 (GPU: CUDA 12.4 빌드 권장, Python 3.12 환경 필요) |

---

## 변경 이력

[CHANGELOG.md](CHANGELOG.md) 참고
