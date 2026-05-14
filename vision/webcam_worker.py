"""
vision/webcam_worker.py
=======================
WebcamPersonDetector 를 PyQt6 QThread 로 래핑한 백그라운드 워커.

debugger_start.py (MainWindow) 에서 import 해서 사용.
WebcamPersonDetector 의 detect() 루프를 별도 스레드에서 실행하고,
최신 감지 결과를 _latest 딕셔너리에 항상 갱신한다.

사용 예::

    worker = WebcamWorker(yolo_model="yolov8n.pt", yolo_conf=0.3)
    worker.result_ready.connect(self._on_cam_result)
    worker.start()
    ...
    latest = worker.latest()   # FFT 저장 시점에 호출
    worker.stop()
"""

from __future__ import annotations

import collections
import time

import PyQt6.QtCore


# ─────────────────────────────────────────────────────────────────────────────
# 기본 파라미터 (test_webcam_detector.py 와 동일 기본값)
# ─────────────────────────────────────────────────────────────────────────────
_DEFAULT_CAMERA_INDEX   = 0
_DEFAULT_YOLO_MODEL     = "yolov8n.pt"   # GUI 내장용: nano (속도 우선)
_DEFAULT_YOLO_CONF      = 0.3
_DEFAULT_SMOOTH_WINDOW  = 10
_DEFAULT_SMOOTH_THRESH  = 3
_DEFAULT_CAM_MAX_AGE    = 0.5            # 최신값 유효 시간 (초) — STEP 3 에서 사용


class WebcamWorker(PyQt6.QtCore.QThread):
    """
    WebcamPersonDetector 백그라운드 스레드.

    Signals
    -------
    result_ready(dict)
        매 프레임마다 emit. dict 키:
          label        : int   — smooth 판정 (0=BG, 1=Human)
          human_conf   : float — 사람 확신도
          bg_conf      : float — 배경 확신도
          smooth_votes : int   — 최근 SMOOTH_WINDOW 중 Human 투표 수
          raw_label    : int   — 원시 단일 프레임 판정
          n_persons    : int   — YOLO 감지 사람 수
          latency_ms   : float — 처리 시간 (ms)
          timestamp    : float — time.time() 기록 시각
    error_occurred(str)
        초기화 실패 또는 치명적 에러 메시지.
    """

    result_ready   = PyQt6.QtCore.pyqtSignal(dict)
    frame_ready    = PyQt6.QtCore.pyqtSignal(object)   # numpy BGR 프레임 (감지 오버레이 포함)
    error_occurred = PyQt6.QtCore.pyqtSignal(str)

    def __init__(
        self,
        camera_index:  int   = _DEFAULT_CAMERA_INDEX,
        yolo_model:    str   = _DEFAULT_YOLO_MODEL,
        yolo_conf:     float = _DEFAULT_YOLO_CONF,
        smooth_window: int   = _DEFAULT_SMOOTH_WINDOW,
        smooth_thresh: int   = _DEFAULT_SMOOTH_THRESH,
        cam_max_age:   float = _DEFAULT_CAM_MAX_AGE,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._camera_index  = camera_index
        self._yolo_model    = yolo_model
        self._yolo_conf     = yolo_conf
        self._smooth_window = smooth_window
        self._smooth_thresh = smooth_thresh
        self._cam_max_age   = cam_max_age

        self._running: bool = False

        # 최신 감지 결과 — MainWindow 가 FFT 저장 시점에 latest() 로 읽는다
        self._latest: dict = {
            "label":        0,
            "human_conf":   0.0,
            "bg_conf":      1.0,
            "smooth_votes": 0,
            "raw_label":    0,
            "n_persons":    0,
            "latency_ms":   0.0,
            "timestamp":    0.0,   # 0.0 = 아직 결과 없음
        }
        self._latest_frame     = None   # 최신 오버레이 프레임 (프리뷰용)
        self._latest_raw_frame = None   # 최신 원본 프레임 (스냅샷 저장용)

    # ── 공개 API ──────────────────────────────────────────────────────────────

    def latest(self) -> dict:
        """
        가장 최근 감지 결과를 반환.

        Returns
        -------
        dict
            timestamp 가 0.0 이면 아직 첫 프레임도 처리되지 않은 상태.
        """
        return dict(self._latest)   # 얕은 복사로 반환 (dict 교체에 안전)

    def is_fresh(self) -> bool:
        """최신 결과가 cam_max_age 이내인지 여부."""
        age = time.time() - self._latest["timestamp"]
        return self._latest["timestamp"] > 0.0 and age < self._cam_max_age

    def latest_frame(self):
        """최신 오버레이 프레임 반환 (없으면 None). GIL 원자성에 의존."""
        return self._latest_frame

    def latest_raw_frame(self):
        """최신 원본 프레임 반환 — UI 오버레이 없음 (스냅샷 저장용)."""
        return self._latest_raw_frame

    def stop(self) -> None:
        """스레드 종료 요청. 최대 3초 대기."""
        self._running = False
        self.wait(3000)

    # ── QThread.run ───────────────────────────────────────────────────────────

    def run(self) -> None:
        # 임포트는 스레드 내부에서 수행 (Qt 메인 스레드 블로킹 방지)
        try:
            from vision.webcam_person_detector import (
                WebcamPersonDetector, DetectionBackend,
            )
        except ImportError as e:
            self.error_occurred.emit(f"[WebcamWorker] 임포트 실패: {e}")
            return

        detector = WebcamPersonDetector(
            camera_index=self._camera_index,
            backend=DetectionBackend.AUTO,
            yolo_model=self._yolo_model,
            yolo_conf=self._yolo_conf,
        )

        try:
            detector.open()
        except (RuntimeError, ImportError) as e:
            self.error_occurred.emit(f"[WebcamWorker] 초기화 실패: {e}")
            return

        label_buf  = collections.deque([0] * self._smooth_window,
                                       maxlen=self._smooth_window)
        self._running = True

        try:
            while self._running:
                result = detector.detect()

                if result.frame is None:
                    # 프레임 읽기 실패 — 잠깐 대기 후 재시도
                    self.msleep(50)
                    continue

                # 시간적 앙상블
                label_buf.append(result.label)
                smooth_votes = sum(label_buf)
                smooth_label = 1 if smooth_votes >= self._smooth_thresh else 0

                payload = {
                    "label":        smooth_label,
                    "human_conf":   result.human_conf,
                    "bg_conf":      result.bg_conf,
                    "smooth_votes": smooth_votes,
                    "raw_label":    result.label,
                    "n_persons":    result.n_persons,
                    "latency_ms":   result.latency_ms,
                    "timestamp":    time.time(),
                }
                # dict 를 한 번에 교체 — GIL 이 원자성 보장
                self._latest_frame     = result.frame
                self._latest_raw_frame = result.raw_frame
                self._latest = payload
                self.result_ready.emit(payload)
                if result.frame is not None:
                    self.frame_ready.emit(result.frame)

        finally:
            detector.close()
            self._running = False
