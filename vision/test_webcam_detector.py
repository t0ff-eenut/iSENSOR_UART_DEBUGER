"""
test_webcam_detector.py
=======================
WebcamPersonDetector 독립 테스트 스크립트.

실행 방법:
    cd iSENSOR_UART_DEBUGER 프로젝트 루트로 이동
    .venv/Scripts/python.exe vision/test_webcam_detector.py

키 조작:
    q / ESC  — 종료
    창 X 버튼 — 종료 (마우스로 창 닫기)
    s        — 현재 프레임 저장 (test_snapshot_XXXXXX.png)
    b        — 백엔드 전환 (MediaPipe ↔ HOG)  ※ 재초기화

성능 지표:
    - 실시간 FPS
    - 평균 처리 시간 (ms)
    - 감지 결과 통계 (사람/배경 횟수)
"""

import sys
import os
import time
import collections

import cv2

# 프로젝트 루트를 sys.path에 추가 (vision 패키지 인식용)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from vision.webcam_person_detector import WebcamPersonDetector, DetectionBackend


# ─────────────────────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────────────────────
CAMERA_INDEX              = 0       # 웹캠 번호 (0 = 기본)
BACKEND                   = DetectionBackend.AUTO
# YOLO 파라미터
#   "yolov8n.pt"  — nano   (~6 MB,  빠름,   정확도 보통)
#   "yolov8s.pt"  — small  (~22 MB, 보통,   정확도 좋음)  ← 권장
#   "yolov8m.pt"  — medium (~52 MB, 느림,   정확도 최고)
YOLO_MODEL                = "yolov8m.pt"
# YOLO_CONF                 = 0.4     # 감지 최소 신뢰도
YOLO_CONF                 = 0.3     # 감지 최소 신뢰도
YOLO_PREDOWNLOAD_ALL      = True    # 시작 시 n/s/m 3종 모두 미리 다운로드
# MediaPipe 파라미터 (MediaPipe 백엔드 선택 시)
PERSON_VISIBILITY_THR     = 0.6
PERSON_LANDMARK_RATIO     = 0.3
WINDOW_NAME               = "iSENSOR_WebcamDetector"   # OpenCV 창 ID (ASCII만 사용)
# 창 크기 설정 (세 가지 방식 중 하나만 사용)
#   방식 1: 픽셀 직접 지정  — WINDOW_WIDTH/HEIGHT에 양수 입력, WINDOW_SCALE = 0.0
#   방식 2: 입력 해상도 배율 — WINDOW_SCALE에 양수 입력 (예: 1.5 = 1.5배)
#   방식 3: 원본 크기 유지  — 모두 0 (기본)
WINDOW_WIDTH              = 0       # 창 너비 px  (0 = 배율 또는 원본 사용)
WINDOW_HEIGHT             = 0       # 창 높이 px  (0 = 배율 또는 원본 사용)
WINDOW_SCALE              = 1.5     # 입력 해상도 배율 (0.0 = 픽셀 직접 지정 사용)
# UI(오버레이 텍스트) 크기 배율
#   1.0 = 기본 크기, 1.5 = 1.5배 크게, 0.7 = 작게
#   WINDOW_SCALE과 독립 설정 가능 (창 크기와 관계없이 텍스트만 조절)
UI_SCALE                  = 0.5
# 콘솔 로그 출력 간격 (프레임 단위)
#   1 = 매 프레임 출력, 2 = 2프레임마다, 30 = 약 1초마다 (30 fps 기준)
# LOG_INTERVAL_FRAMES       = 30
LOG_INTERVAL_FRAMES       = 5
# 시간적 앙상블 (Temporal Smoothing) — 간헐적 오판단 흡수
#   최근 SMOOTH_WINDOW 프레임 중 SMOOTH_THRESH개 이상 Human이면 최종 Human 판정
SMOOTH_WINDOW             = 10       # 관찰 프레임 수
SMOOTH_THRESH             = 3      # Human 판정 최솟값 (5프레임 중 3개 이상이면 Human)


# ─────────────────────────────────────────────────────────────────────────────
def predownload_yolo_models() -> None:
    """yolov8n / yolov8s / yolov8m 모델 파일 미리 다운로드 (캐시 없으면 자동 다운로드)"""
    try:
        from ultralytics import YOLO
        for model_name in ("yolov8n.pt", "yolov8s.pt", "yolov8m.pt"):
            print(f"  [모델 다운로드] {model_name} ...", end=" ", flush=True)
            YOLO(model_name)   # 캐시에 없으면 다운로드, 있으면 즉시 반환
            print("OK")
    except ImportError:
        print("  [WARN] ultralytics 미설치 — YOLO 모델 사전 다운로드 건너뜀")


# ─────────────────────────────────────────────────────────────────────────────
def draw_stats(frame, fps: float, latency: float,
               n_human: int, n_bg: int,
               raw_label: int, human_conf: float, bg_conf: float,
               smooth_label: int, smooth_votes: int) -> None:
    """좌상단에 통계 오버레이 표시 (human/bg 확신도 동시 표시)"""
    total = n_human + n_bg
    ratio = n_human / total if total > 0 else 0.0
    h, w  = frame.shape[:2]

    # 앙상블 결과 표시 문자열 및 색상 (BGR)
    smooth_str   = (f"HUMAN ({smooth_votes}/{SMOOTH_WINDOW})"
                    if smooth_label == 1
                    else f"BG    ({SMOOTH_WINDOW - smooth_votes}/{SMOOTH_WINDOW})")
    smooth_color = (80, 200, 80) if smooth_label == 1 else (80, 80, 200)

    # UI 배율 적용 폰트/간격 계산
    fs_main  = 0.60 * UI_SCALE          # 앙상블 결과 줄 폰트 크기
    fs_sub   = 0.55 * UI_SCALE          # 나머지 통계 줄 폰트 크기
    th_main  = max(1, round(2 * UI_SCALE))  # 굵기
    th_sub   = max(1, round(1 * UI_SCALE))
    lh       = int(22 * UI_SCALE)       # 줄 간격 px
    y0       = int(15 * UI_SCALE)       # 첫 줄 y 위치

    lines = [
        f"Res     : {w} x {h}",
        f"FPS     : {fps:5.1f}",
        f"Latency : {latency:5.1f} ms",
        f"Raw     : {'HUMAN' if raw_label == 1 else 'BG   '}  hm={human_conf:.2f}  bg={bg_conf:.2f}",
        f"Human   : {n_human:5d}  ({ratio*100:.1f}%)",
        f"BG      : {n_bg:5d}",
    ]
    x0 = 10

    # 1행: 앙상블 최종 결과 (굵게, 색상 구분)
    cv2.putText(frame, f"Detect  : {smooth_str}", (x0, y0),
                cv2.FONT_HERSHEY_SIMPLEX, fs_main, smooth_color, th_main, cv2.LINE_AA)

    for i, line in enumerate(lines):
        y = y0 + (i + 1) * lh
        cv2.putText(frame, line, (x0, y),
                    cv2.FONT_HERSHEY_SIMPLEX, fs_sub,
                    (220, 220, 220), th_sub, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────────────────────
def run_test() -> None:
    print("=" * 55)
    print("  WebcamPersonDetector  독립 테스트")
    print("=" * 55)
    print(f"  카메라 인덱스  : {CAMERA_INDEX}")
    print(f"  요청 백엔드    : {BACKEND.value}")
    print(f"  YOLO 모델      : {YOLO_MODEL}")
    print(f"  앙상블         : 최근 {SMOOTH_WINDOW}프레임 중 {SMOOTH_THRESH}개 이상 Human")
    print("  키 조작: q/ESC=종료  s=스냅샷 저장")
    print("=" * 55)

    if YOLO_PREDOWNLOAD_ALL:
        print("\n  [사전 다운로드] YOLO 모델 3종 확인 중...")
        predownload_yolo_models()

    detector = WebcamPersonDetector(
        camera_index=CAMERA_INDEX,
        backend=BACKEND,
        yolo_model=YOLO_MODEL,
        yolo_conf=YOLO_CONF,
        mp_vis_thr=PERSON_VISIBILITY_THR,
        mp_lmk_ratio=PERSON_LANDMARK_RATIO,
        ui_scale=UI_SCALE,
    )

    try:
        detector.open()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except ImportError as e:
        print(f"[WARN] {e}  →  HOG 백엔드로 전환합니다.")
        detector.close()
        detector = WebcamPersonDetector(
            camera_index=CAMERA_INDEX,
            backend=DetectionBackend.HOG,
        )
        detector.open()

    # 카메라 원본 해상도 읽기
    cap = detector._cap
    cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 창 크기 결정: 픽셀 직접 > 배율 > 원본
    if WINDOW_WIDTH > 0 and WINDOW_HEIGHT > 0:
        win_w, win_h = WINDOW_WIDTH, WINDOW_HEIGHT
    elif WINDOW_SCALE > 0.0:
        win_w = int(cam_w * WINDOW_SCALE)
        win_h = int(cam_h * WINDOW_SCALE)
    else:
        win_w, win_h = cam_w, cam_h

    print(f"  실제 사용 백엔드: {detector.backend_name.upper()}")
    print(f"  카메라 해상도   : {cam_w} x {cam_h}")
    print(f"  창 크기         : {win_w} x {win_h}")
    print("  창이 열리면 테스트를 시작하세요.\n")

    fps_buf    = collections.deque(maxlen=30)
    lat_buf    = collections.deque(maxlen=30)
    n_human    = 0
    n_bg       = 0
    snap_count = 0
    label_buf  = collections.deque([0] * SMOOTH_WINDOW, maxlen=SMOOTH_WINDOW)
    t_prev     = time.perf_counter()

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, win_w, win_h)

    try:
        while True:
            result = detector.detect()

            if result.frame is None:
                print("[WARN] 프레임 읽기 실패, 재시도 중...")
                time.sleep(0.05)
                continue

            # FPS 계산
            t_now = time.perf_counter()
            fps_buf.append(1.0 / max(t_now - t_prev, 1e-6))
            t_prev = t_now
            lat_buf.append(result.latency_ms)

            # 시간적 앙상블: 최근 SMOOTH_WINDOW 프레임 다수결
            label_buf.append(result.label)
            smooth_votes = sum(label_buf)
            smooth_label = 1 if smooth_votes >= SMOOTH_THRESH else 0

            if smooth_label == 1:
                n_human += 1
            else:
                n_bg    += 1

            avg_fps = sum(fps_buf) / len(fps_buf)
            avg_lat = sum(lat_buf) / len(lat_buf)

            draw_stats(result.frame, avg_fps, avg_lat, n_human, n_bg,
                       result.label, result.human_conf, result.bg_conf,
                       smooth_label, smooth_votes)

            # 창 X 버튼 감지 — imshow 이전에 체크해야 함
            # (imshow는 닫힌 창을 자동 재생성하므로 imshow 후 체크하면 항상 visible)
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break

            cv2.imshow(WINDOW_NAME, result.frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):   # q 또는 ESC
                break

            # 콘솔 로그 (LOG_INTERVAL_FRAMES 프레임마다)
            if (n_human + n_bg) % LOG_INTERVAL_FRAMES == 0:
                raw_str    = "Human" if result.label == 1 else "BG"
                smooth_str = "Human" if smooth_label == 1 else "BG"
                n_str      = f" x{result.n_persons}" if result.n_persons > 0 else ""
                print(f"  raw={raw_str}{n_str}  hm={result.human_conf:.2f}  bg={result.bg_conf:.2f}"
                      f"  smooth={smooth_str}({smooth_votes}/{SMOOTH_WINDOW})"
                      f"  FPS={avg_fps:.1f}  lat={avg_lat:.1f}ms")

            if key == ord('s'):
                fname = f"test_snapshot_{snap_count:04d}.png"
                cv2.imwrite(fname, result.frame)
                print(f"  스냅샷 저장: {fname}")
                snap_count += 1

    finally:
        detector.close()
        cv2.destroyAllWindows()

    # 최종 통계 출력
    total = n_human + n_bg
    print("\n" + "=" * 55)
    print("  테스트 결과 요약")
    print("=" * 55)
    print(f"  총 프레임      : {total}")
    print(f"  사람 감지 프레임: {n_human}  ({n_human/total*100:.1f}%)" if total else "  (프레임 없음)")
    print(f"  배경 프레임    : {n_bg}  ({n_bg/total*100:.1f}%)" if total else "")
    print(f"  평균 FPS       : {sum(fps_buf)/len(fps_buf):.1f}" if fps_buf else "")
    print(f"  평균 처리시간  : {sum(lat_buf)/len(lat_buf):.1f} ms" if lat_buf else "")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_test()
