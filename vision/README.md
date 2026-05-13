# vision 패키지

웹캠 기반 사람 감지 독립 모듈. `debugger_start.py` GUI와 분리되어 단독으로 실행 및 검증할 수 있습니다.

---

## 파일 구성

```
vision/
├── __init__.py                  # 패키지 진입점
├── webcam_person_detector.py    # 핵심 감지 모듈
├── test_webcam_detector.py      # 독립 성능 검증 스크립트
└── README.md                    # 이 문서
```

---

## 의존성

```
opencv-python >= 4.8.0
mediapipe     >= 0.10.0         # MediaPipe 백엔드 사용 시
ultralytics   >= 8.0.0          # YOLO 백엔드 사용 시 (yolov8n.pt 첫 실행 시 자동 다운로드)
```

---

## 백엔드 비교

| 백엔드 | 상반신 감지 | 부분 가림 | 속도 | 권장 용도 |
|--------|------------|-----------|------|-----------|
| **YOLOv8n** (권장) | ✅ 우수 | ✅ 강함 | 빠름 | 기본 선택 |
| MediaPipe Pose | ⚠️ 보통 | ⚠️ 취약 | 보통 | 스켈레톤 필요 시 |
| OpenCV HOG | ❌ 취약 | ❌ 취약 | 빠름 | 폴백 전용 |

**AUTO 선택 순서**: YOLO → MediaPipe → HOG (의존성 없으면 다음으로 자동 전환)

---

## 기본 사용법

```python
from vision.webcam_person_detector import WebcamPersonDetector, DetectionBackend

detector = WebcamPersonDetector(camera_index=0, backend=DetectionBackend.AUTO)

with detector:
    while True:
        result = detector.detect()
        if result.frame is None:
            break
        print(f"label={result.label}  conf={result.confidence:.2f}  backend={result.backend}")
        # label: 1 = 사람, 0 = 배경
```

### `DetectionResult` 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `label` | `int` | `1` = 사람, `0` = 배경 |
| `confidence` | `float` | 0.0 ~ 1.0 (가장 높은 박스 기준) |
| `frame` | `np.ndarray` | 오버레이 포함 BGR 이미지 |
| `backend` | `str` | 실제 사용된 백엔드 이름 |
| `n_persons` | `int` | 감지된 사람 수 |
| `latency_ms` | `float` | 감지 처리 시간 (ms) |

---

## 테스트 스크립트 실행

프로젝트 루트에서 실행합니다:

```powershell
cd C:\...\iSENSOR_UART_DEBUGER
.venv\Scripts\python.exe vision\test_webcam_detector.py
```

### 설정 상수 (스크립트 상단)

| 상수 | 기본값 | 설명 |
|------|--------|------|
| `CAMERA_INDEX` | `0` | 웹캠 번호 |
| `BACKEND` | `AUTO` | 감지 백엔드 |
| `YOLO_CONF` | `0.4` | YOLO 최소 신뢰도 |
| `PERSON_VISIBILITY_THR` | `0.6` | MediaPipe 랜드마크 가시성 임계값 |
| `PERSON_LANDMARK_RATIO` | `0.3` | MediaPipe 가시 관절 비율 임계값 |
| `WINDOW_NAME` | `"iSENSOR_WebcamDetector"` | OpenCV 창 이름 (ASCII 전용) |
| `WINDOW_WIDTH` | `0` | 창 너비 px (0 = 배율/원본 사용) |
| `WINDOW_HEIGHT` | `0` | 창 높이 px (0 = 배율/원본 사용) |
| `WINDOW_SCALE` | `1.0` | 카메라 해상도 배율 (0.0 = px 직접 지정 우선) |
| `LOG_INTERVAL_FRAMES` | `30` | 콘솔 로그 출력 간격 (프레임 단위) |

### 창 크기 설정 방식 (우선순위 순)

```python
# 방식 1 — 픽셀 직접 지정
WINDOW_WIDTH  = 1280
WINDOW_HEIGHT = 720
WINDOW_SCALE  = 0.0   # 0이면 픽셀 직접 지정 활성화

# 방식 2 — 카메라 해상도 배율
WINDOW_WIDTH  = 0
WINDOW_HEIGHT = 0
WINDOW_SCALE  = 1.5   # 640×480 카메라 → 960×720 창

# 방식 3 — 원본 크기 유지 (기본)
WINDOW_WIDTH  = 0
WINDOW_HEIGHT = 0
WINDOW_SCALE  = 1.0
```

### 로그 출력 간격 예시

```python
LOG_INTERVAL_FRAMES = 1    # 매 프레임 출력 (디버깅)
LOG_INTERVAL_FRAMES = 2    # 2프레임마다
LOG_INTERVAL_FRAMES = 30   # ~1초마다 (30fps 기준, 기본값)
LOG_INTERVAL_FRAMES = 60   # ~2초마다
```

### 키 조작

| 키 | 동작 |
|----|------|
| `q` / `ESC` | 종료 |
| 창 X 버튼 | 종료 |
| `s` | 현재 프레임 스냅샷 저장 (`test_snapshot_XXXX.png`) |

### 화면 오버레이 정보

| 항목 | 설명 |
|------|------|
| `Res` | 카메라 실제 해상도 (W × H) |
| `FPS` | 최근 30프레임 평균 |
| `Latency` | 최근 30프레임 평균 감지 처리시간 (ms) |
| `Human` | 누적 사람 프레임 수 및 비율 |
| `BG` | 누적 배경 프레임 수 |

---

## 참고

- Windows에서 OpenCV `namedWindow` / `imshow` 창 이름에 한글·특수문자 포함 시 별도 창이 열리는 버그 있음 → `WINDOW_NAME`은 ASCII 전용으로 설정
- `yolov8n.pt` (~6 MB)는 첫 실행 시 Ultralytics Hub에서 자동 다운로드됨
- 현재 독립 검증 단계이며, 검증 후 `debugger_start.py` 데이터 수집 탭과 통합 예정
