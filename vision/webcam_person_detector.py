"""
webcam_person_detector.py
=========================
웹캠 + OpenCV/YOLO/MediaPipe를 이용한 사람 감지 독립 모듈.

백엔드 우선순위 (AUTO):
  1. YOLOv8n      — 바운딩 박스, 상반신 포함 다양한 포즈, 정확도 최우수 (권장)
  2. MediaPipe    — 스켈레톤 33 관절, 전신/상반신 모두 지원, 보통
  3. OpenCV HOG   — 전신 기준 학습, 상반신 취약, 폴백용

상반신 감지 지원:
  YOLO      : 우수  (COCO 80클래스, 부분 가림/상반신 포함)
  MediaPipe : 보통  (전신 없으면 visibility 낮아짐)
  HOG       : 취약  (전신 기준으로 학습됨)

사용 예시::

    from vision.webcam_person_detector import WebcamPersonDetector

    with WebcamPersonDetector(camera_index=0) as det:
        while True:
            result = det.detect()
            if result.frame is None:
                break
            cv2.imshow("Preview", result.frame)
            print("label:", result.label, "  conf:", result.confidence)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

반환 label:
  1  -> 사람 있음 (Human)
  0  -> 배경     (Background)
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# ── YOLOv8 임포트 (선택적) ────────────────────────────────────────────────────
try:
    from ultralytics import YOLO as _YOLO              # type: ignore
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False

# ── MediaPipe 임포트 (선택적) ─────────────────────────────────────────────────
try:
    import mediapipe as mp                             # type: ignore
    # 0.10+: Tasks API (mp.tasks.vision.PoseLandmarker)
    # 0.9.x: Solutions API (mp.solutions.pose) — PyPI에 현재 빌드 없음
    _MP_TASKS_API = (
        hasattr(mp, "tasks") and
        hasattr(mp.tasks, "vision") and
        hasattr(mp.tasks.vision, "PoseLandmarker")
    )
    _MP_LEGACY_API = hasattr(mp, "solutions") and hasattr(mp.solutions, "pose")
    _MP_AVAILABLE  = _MP_TASKS_API or _MP_LEGACY_API
except ImportError:
    _MP_AVAILABLE = _MP_TASKS_API = _MP_LEGACY_API = False


# ─────────────────────────────────────────────────────────────────────────────
class DetectionBackend(enum.Enum):
    YOLO      = "yolo"        # YOLOv8n — 바운딩 박스, 상반신 포함 (권장)
    MEDIAPIPE = "mediapipe"   # MediaPipe Pose — 스켈레톤 기반
    HOG       = "hog"         # OpenCV HOG+SVM — 전신 기준 (폴백)
    AUTO      = "auto"        # YOLO > MediaPipe > HOG 자동 선택


@dataclass
class DetectionResult:
    """단일 프레임 감지 결과"""
    label:       int           # 0 = 배경, 1 = 사람
    confidence:  float         # 0.0 ~ 1.0  (가장 신뢰도 높은 박스 기준)
    frame:       np.ndarray    # 오버레이 포함 BGR 이미지
    backend:     str           # 실제 사용된 백엔드 이름
    n_persons:   int   = 0     # 감지된 사람 수 (YOLO/HOG)
    latency_ms:  float = 0.0   # 처리 시간 (ms)
    human_conf:  float = 0.0   # 사람 확신도 (YOLO valid box 최고 score, 없으면 0)
    bg_conf:     float = 0.0   # 배경 확신도 = 1 - max_raw_score (YOLO 전용, 없으면 0)
    raw_frame:   Optional[np.ndarray] = None  # UI 오버레이 없는 원본 프레임 (스냅샷 저장용)


# ─────────────────────────────────────────────────────────────────────────────
class WebcamPersonDetector:
    """
    웹캠에서 사람 존재 여부를 실시간으로 감지하는 클래스.

    Parameters
    ----------
    camera_index : int
        OpenCV VideoCapture 인덱스 (기본 0)
    backend : DetectionBackend
        감지 백엔드 (기본 AUTO = YOLO 우선)
    yolo_model : str
        YOLOv8 모델 이름 또는 경로 (기본 'yolov8n.pt' — nano)
    yolo_conf : float
        YOLO 감지 최소 신뢰도 (0.0~1.0, 기본 0.4)
    yolo_iou : float
        YOLO NMS IoU 임계값 (기본 0.45)
    mp_det_conf : float
        MediaPipe 최소 감지 신뢰도 (기본 0.5)
    mp_trk_conf : float
        MediaPipe 최소 추적 신뢰도 (기본 0.5)
    mp_vis_thr : float
        MediaPipe 랜드마크 가시성 기준 (기본 0.6)
    mp_lmk_ratio : float
        MediaPipe 가시 랜드마크 비율 임계값 (기본 0.3)
    mp_delegate : str
        MediaPipe 추론 장치 ``"cpu"`` 또는 ``"gpu"`` (기본 ``"cpu"``)
        GPU 는 Tasks API (mediapipe 0.10+) 에서만 유효, 미지원 시 CPU 폴백
    ui_scale : float
        우상단 상태 박스 텍스트 크기 배율 (기본 1.0)
    """

    # MediaPipe 주요 관절 (신뢰도 계산용)
    _MP_KEY_LMK = [0, 11, 12, 13, 14, 15, 16, 23, 24]

    def __init__(
        self,
        camera_index: int = 0,
        backend: DetectionBackend = DetectionBackend.AUTO,
        yolo_model: str = "yolov8n.pt",
        yolo_conf: float = 0.4,
        yolo_iou: float = 0.45,
        mp_det_conf: float = 0.5,
        mp_trk_conf: float = 0.5,
        mp_vis_thr: float = 0.6,
        mp_lmk_ratio: float = 0.3,
        mp_delegate: str = "cpu",
        ui_scale: float = 1.0,
    ) -> None:
        self._cam_idx      = camera_index
        self._backend      = backend
        self._yolo_model   = yolo_model
        self._yolo_conf    = yolo_conf
        self._yolo_iou     = yolo_iou
        self._mp_det_conf  = mp_det_conf
        self._mp_trk_conf  = mp_trk_conf
        self._mp_vis_thr   = mp_vis_thr
        self._mp_lmk_ratio = mp_lmk_ratio
        self._mp_delegate  = mp_delegate.lower()
        self._ui_scale     = ui_scale

        self._cap:  Optional[cv2.VideoCapture] = None
        self._yolo: Optional[object] = None
        self._pose: Optional[object] = None
        self._hog:  Optional[cv2.HOGDescriptor] = None
        self._active_backend: str = ""

    # ── 컨텍스트 매니저 ───────────────────────────────────────────────────────
    def __enter__(self) -> "WebcamPersonDetector":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ── 공개 API ──────────────────────────────────────────────────────────────
    def open(self) -> None:
        """웹캠 및 감지 백엔드 초기화"""
        self._cap = cv2.VideoCapture(self._cam_idx)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"웹캠 (index={self._cam_idx})을 열 수 없습니다. "
                "카메라 연결을 확인하세요."
            )

        req = self._backend
        if req == DetectionBackend.AUTO:
            if _YOLO_AVAILABLE:
                req = DetectionBackend.YOLO
            elif _MP_AVAILABLE:
                req = DetectionBackend.MEDIAPIPE
            else:
                req = DetectionBackend.HOG

        if req == DetectionBackend.YOLO:
            if not _YOLO_AVAILABLE:
                raise ImportError("ultralytics 미설치. pip install ultralytics")
            self._init_yolo()
            self._active_backend = "yolo"
        elif req == DetectionBackend.MEDIAPIPE:
            if not _MP_AVAILABLE:
                try:
                    import mediapipe as _mp_check  # type: ignore
                    _ver = getattr(_mp_check, "__version__", "?")
                    raise ImportError(
                        f"mediapipe {_ver} 은 지원 가능한 Pose API가 없습니다."
                    )
                except ModuleNotFoundError:
                    raise ImportError("mediapipe 미설치. pip install mediapipe")
            self._init_mediapipe()
            self._active_backend = "mediapipe"
        else:
            self._init_hog()
            self._active_backend = "hog"

    def close(self) -> None:
        """리소스 해제"""
        if self._cap is not None and self._cap.isOpened():
            self._cap.release()
        if self._pose is not None:
            self._pose.close()

    def detect(self) -> DetectionResult:
        """
        웹캠에서 한 프레임을 읽어 사람 감지 수행.

        Returns
        -------
        DetectionResult
            frame=None 이면 카메라 읽기 실패
        """
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("open()을 먼저 호출하세요.")

        ret, frame = self._cap.read()
        if not ret or frame is None:
            return DetectionResult(label=0, confidence=0.0,
                                   frame=None, backend=self._active_backend)

        t0 = time.perf_counter()
        if self._active_backend == "yolo":
            result = self._detect_yolo(frame)
        elif self._active_backend == "mediapipe":
            result = self._detect_mediapipe(frame)
        else:
            result = self._detect_hog(frame)
        result.raw_frame  = frame                               # 오버레이 없는 원본
        result.latency_ms = (time.perf_counter() - t0) * 1000.0
        return result

    # ── YOLOv8 초기화 & 감지 ─────────────────────────────────────────────────
    def _init_yolo(self) -> None:
        import os, logging
        # vision/ 폴더에 파일이 있으면 그 경로를 사용, 없으면 이름만 전달(자동 다운로드)
        _vision_dir = os.path.dirname(os.path.abspath(__file__))
        _local_path = os.path.join(_vision_dir, self._yolo_model)
        model_arg   = _local_path if os.path.exists(_local_path) else self._yolo_model
        self._yolo  = _YOLO(model_arg)
        logging.getLogger("ultralytics").setLevel(logging.WARNING)

    # BG 확신도 계산용 low-conf probe (임계값 이하 박스의 raw score 수집)
    _YOLO_RAW_PROBE_CONF = 0.01

    def _detect_yolo(self, frame: np.ndarray) -> DetectionResult:
        # conf를 낮게 설정해 임계값 미만 박스도 수집 → BG 확신도 계산에 사용
        results = self._yolo.predict(
            frame,
            conf=self._YOLO_RAW_PROBE_CONF,
            iou=self._yolo_iou,
            classes=[0],        # person class only
            show=False,         # ultralytics 자체 창 표시 방지
            verbose=False,
        )
        overlay   = frame.copy()
        all_boxes = results[0].boxes  # 임계값 이하 포함 모든 박스

        # raw 최고 점수: BG 확신도 = 1 - max_raw  (낮을수록 확실한 배경)
        all_confs    = [float(b.conf[0]) for b in all_boxes] if all_boxes else []
        max_raw_conf = max(all_confs) if all_confs else 0.0

        # YOLO_CONF 이상인 박스만 유효 Human으로 처리
        valid_boxes = ([b for b in all_boxes if float(b.conf[0]) >= self._yolo_conf]
                       if all_boxes else [])
        n_persons   = len(valid_boxes)

        if n_persons == 0:
            bg_conf = 1.0 - max_raw_conf
            self._draw_status(overlay, 0, 0.0, bg_conf, "YOLO", 0)
            return DetectionResult(label=0, confidence=bg_conf,
                                   frame=overlay, backend="yolo", n_persons=0,
                                   human_conf=0.0, bg_conf=bg_conf)

        best_conf = 0.0
        for box in valid_boxes:
            conf = float(box.conf[0])
            if conf > best_conf:
                best_conf = conf
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            g     = int(200 * conf)
            color = (0, g, 255 - g)
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
            cv2.putText(overlay, f"person {conf:.2f}",
                        (x1, max(y1 - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        color, 2, cv2.LINE_AA)

        bg_conf = 1.0 - max_raw_conf
        self._draw_status(overlay, 1, best_conf, bg_conf, "YOLO", n_persons)
        return DetectionResult(label=1, confidence=best_conf,
                               frame=overlay, backend="yolo",
                               n_persons=n_persons,
                               human_conf=best_conf, bg_conf=bg_conf)

    @property
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def backend_name(self) -> str:
        return self._active_backend

    # MediaPipe Pose 표준 연결선 (Tasks API 에서 직접 제공하지 않으므로 하드코딩)
    _MP_POSE_CONNECTIONS = [
        (0,1),(1,2),(2,3),(3,7),(0,4),(4,5),(5,6),(6,8),   # 얼굴
        (9,10),                                              # 입
        (11,12),                                             # 어깨
        (11,13),(13,15),(15,17),(15,19),(15,21),(17,19),     # 오른팔
        (12,14),(14,16),(16,18),(16,20),(16,22),(18,20),     # 왼팔
        (11,23),(12,24),(23,24),                             # 몸통
        (23,25),(25,27),(27,29),(27,31),(29,31),             # 오른다리
        (24,26),(26,28),(28,30),(28,32),(30,32),             # 왼다리
    ]

    # ── MediaPipe 초기화 & 감지 ───────────────────────────────────────────────
    def _init_mediapipe(self) -> None:
        """Tasks API (0.10+) 우선, Legacy API (0.9.x) 폴백"""
        if _MP_TASKS_API:
            self._init_mediapipe_tasks()
        elif _MP_LEGACY_API:
            self._init_mediapipe_legacy()
        else:
            _ver = getattr(mp, "__version__", "?")
            raise ImportError(
                f"mediapipe {_ver} 에서 Pose API를 찾을 수 없습니다."
            )

    def _init_mediapipe_tasks(self) -> None:
        """mediapipe 0.10+ Tasks API 초기화 (모델 파일 없으면 자동 다운로드)"""
        import os, urllib.request
        _vision_dir = os.path.dirname(os.path.abspath(__file__))
        _model_path = os.path.join(_vision_dir, "pose_landmarker_lite.task")
        if not os.path.exists(_model_path):
            _url = (
                "https://storage.googleapis.com/mediapipe-models/"
                "pose_landmarker/pose_landmarker_lite/float16/latest/"
                "pose_landmarker_lite.task"
            )
            print(f"[MediaPipe] 모델 다운로드 중 (약 6 MB): {_url}")
            urllib.request.urlretrieve(_url, _model_path)
            print(f"[MediaPipe] 저장 완료: {_model_path}")

        _delegate_enum = (
            mp.tasks.BaseOptions.Delegate.GPU
            if self._mp_delegate == "gpu"
            else mp.tasks.BaseOptions.Delegate.CPU
        )
        try:
            options = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path=_model_path,
                    delegate=_delegate_enum,
                ),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=self._mp_det_conf,
                min_tracking_confidence=self._mp_trk_conf,
                min_pose_presence_confidence=self._mp_det_conf,
            )
            self._pose = mp.tasks.vision.PoseLandmarker.create_from_options(options)
            _used = "GPU" if self._mp_delegate == "gpu" else "CPU"
            print(f"[MediaPipe] PoseLandmarker 초기화 완료 (delegate={_used})")
        except Exception as e:
            if self._mp_delegate == "gpu":
                print(f"[MediaPipe] GPU delegate 실패 ({e}), CPU 폴백")
                self._mp_delegate = "cpu"
                self._init_mediapipe_tasks()   # CPU 로 재시도
                return
            raise
        self._mp_use_tasks = True

    def _init_mediapipe_legacy(self) -> None:
        """mediapipe 0.9.x Legacy solutions API 초기화"""
        self._mp_pose  = mp.solutions.pose
        self._mp_draw  = mp.solutions.drawing_utils
        self._mp_style = mp.solutions.drawing_styles
        self._pose = self._mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=self._mp_det_conf,
            min_tracking_confidence=self._mp_trk_conf,
        )
        self._mp_use_tasks = False

    def _detect_mediapipe(self, frame: np.ndarray) -> DetectionResult:
        if getattr(self, "_mp_use_tasks", False):
            return self._detect_mediapipe_tasks(frame)
        return self._detect_mediapipe_legacy(frame)

    def _detect_mediapipe_tasks(self, frame: np.ndarray) -> DetectionResult:
        """Tasks API (0.10+) 감지"""
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result  = self._pose.detect(mp_img)
        overlay = frame.copy()

        if not result.pose_landmarks:
            self._draw_status(overlay, 0, 0.0, 1.0, "MediaPipe", 0)
            return DetectionResult(label=0, confidence=0.0,
                                   frame=overlay, backend="mediapipe", n_persons=0)

        lmks      = result.pose_landmarks[0]   # 첫 번째 사람
        key_vis   = [lmks[i].visibility for i in self._MP_KEY_LMK if i < len(lmks)]
        conf      = float(np.mean(key_vis)) if key_vis else 0.0
        all_vis   = [lm.visibility for lm in lmks]
        vis_ratio = sum(v >= self._mp_vis_thr for v in all_vis) / max(len(all_vis), 1)
        label     = 1 if vis_ratio >= self._mp_lmk_ratio else 0

        # 랜드마크 그리기
        h, w = frame.shape[:2]
        for start_i, end_i in self._MP_POSE_CONNECTIONS:
            if start_i < len(lmks) and end_i < len(lmks):
                sx = int(lmks[start_i].x * w); sy = int(lmks[start_i].y * h)
                ex = int(lmks[end_i].x * w);   ey = int(lmks[end_i].y * h)
                cv2.line(overlay, (sx, sy), (ex, ey), (0, 200, 100), 2)
        for lm in lmks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(overlay, (cx, cy), 4, (0, 255, 0), -1)

        bg_conf = 1.0 - conf
        self._draw_status(overlay, label, conf, bg_conf, "MediaPipe", int(label))
        return DetectionResult(label=label, confidence=conf,
                               frame=overlay, backend="mediapipe",
                               n_persons=int(label),
                               human_conf=conf, bg_conf=bg_conf)

    def _detect_mediapipe_legacy(self, frame: np.ndarray) -> DetectionResult:
        """Legacy solutions API (0.9.x) 감지"""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        res = self._pose.process(rgb)
        rgb.flags.writeable = True
        overlay = frame.copy()

        if res.pose_landmarks is None:
            self._draw_status(overlay, 0, 0.0, 1.0, "MediaPipe", 0)
            return DetectionResult(label=0, confidence=0.0,
                                   frame=overlay, backend="mediapipe", n_persons=0)

        lmks      = res.pose_landmarks.landmark
        key_vis   = [lmks[i].visibility for i in self._MP_KEY_LMK]
        conf      = float(np.mean(key_vis))
        all_vis   = [lm.visibility for lm in lmks]
        vis_ratio = sum(v >= self._mp_vis_thr for v in all_vis) / len(all_vis)
        label     = 1 if vis_ratio >= self._mp_lmk_ratio else 0

        self._mp_draw.draw_landmarks(
            overlay, res.pose_landmarks,
            self._mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self._mp_style.get_default_pose_landmarks_style(),
        )
        bg_conf = 1.0 - conf
        self._draw_status(overlay, label, conf, bg_conf, "MediaPipe", int(label))
        return DetectionResult(label=label, confidence=conf,
                               frame=overlay, backend="mediapipe",
                               n_persons=int(label),
                               human_conf=conf, bg_conf=bg_conf)

    # ── HOG 초기화 & 감지 ────────────────────────────────────────────────────
    def _init_hog(self) -> None:
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def _detect_hog(self, frame: np.ndarray) -> DetectionResult:
        small = cv2.resize(frame, (640, 480))
        boxes, weights = self._hog.detectMultiScale(
            small, winStride=(8, 8), padding=(4, 4), scale=1.05)
        overlay = frame.copy()

        if len(boxes) == 0:
            self._draw_status(overlay, 0, 0.0, 1.0, "HOG", 0)
            return DetectionResult(label=0, confidence=0.0,
                                   frame=overlay, backend="hog", n_persons=0)

        sx = frame.shape[1] / 640
        sy = frame.shape[0] / 480
        best_conf = 0.0
        for i, (x, y, w, h) in enumerate(boxes):
            conf = float(np.clip(weights[i] / 2.0, 0.0, 1.0))
            if conf > best_conf:
                best_conf = conf
            rx, ry = int(x * sx), int(y * sy)
            rw, rh = int(w * sx), int(h * sy)
            cv2.rectangle(overlay, (rx, ry), (rx + rw, ry + rh), (0, 200, 0), 2)
            cv2.putText(overlay, f"person {conf:.2f}",
                        (rx, max(ry - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (0, 200, 0), 2, cv2.LINE_AA)

        self._draw_status(overlay, 1, best_conf, 1.0 - best_conf, "HOG", len(boxes))
        return DetectionResult(label=1, confidence=best_conf,
                               frame=overlay, backend="hog",
                               n_persons=len(boxes))

    # ── UI 오버레이 ───────────────────────────────────────────────────────────
    def _draw_status(self, frame: np.ndarray, label: int,
                     human_conf: float, bg_conf: float,
                     backend: str, n: int) -> None:
        """프레임 우상단에 감지 상태 표시 (human/bg 확신도 동시 표시)"""
        s     = self._ui_scale
        color = (0, 200, 0) if label == 1 else (100, 100, 100)
        line1 = (f"HUMAN x{n}  hm={human_conf:.2f}" if label == 1
                 else f"BACKGROUND  bg={bg_conf:.2f}")
        line2 = (f"bg={bg_conf:.2f}" if label == 1
                 else f"hm={human_conf:.2f}")
        btext = f"[{backend.upper()}]"
        h, w  = frame.shape[:2]

        bw    = int(282 * s)
        bh    = int(80  * s)   # 3줄로 늘어남
        pad   = int(8   * s)
        x0    = w - bw - pad
        y0    = pad

        cv2.rectangle(frame, (x0, y0), (x0 + bw, y0 + bh), (0, 0, 0), -1)
        cv2.rectangle(frame, (x0, y0), (x0 + bw, y0 + bh), color, max(1, round(2 * s)))
        cv2.putText(frame, line1, (x0 + int(5 * s), y0 + int(24 * s)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65 * s, color,
                    max(1, round(2 * s)), cv2.LINE_AA)
        cv2.putText(frame, line2, (x0 + int(5 * s), y0 + int(48 * s)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55 * s, (180, 220, 180),
                    max(1, round(1 * s)), cv2.LINE_AA)
        cv2.putText(frame, btext, (x0 + int(5 * s), y0 + int(68 * s)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45 * s, (140, 140, 140),
                    max(1, round(1 * s)), cv2.LINE_AA)
