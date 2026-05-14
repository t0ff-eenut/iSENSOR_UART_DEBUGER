#!/usr/bin/env python3
"""
csv_label_editor.py
===================
data_csv/ CSV 파일의 label 검토 및 편집 도구.

사용법:
    python csv_label_editor.py
    python csv_label_editor.py data_csv/svm_data_xxx.csv

단축키:
    ←  / →      이전 / 다음 행
    0           label = 0 (Background) 적용
    1           label = 1 (Human) 적용
    Enter       선택한 레이블 적용 후 다음 행으로 이동
    Ctrl+S      CSV 저장
"""

from __future__ import annotations

import csv
import glob
import os
import sys
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame,
    QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QRadioButton, QScrollArea,
    QSpinBox, QSplitter, QStatusBar, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

# ─────────────────────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────────────────────
# 스크립트가 data_csv/ 안에 있으므로 __file__ 기준 절대 경로 사용
_SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
_CSV_DIR       = _SCRIPT_DIR                                      # CSV 파일들이 같은 폴더에 위치
_SNAP_DIR_DEF  = os.path.join(_SCRIPT_DIR, "snapshots")
_NEARBY_WIN    = 2.0
_MAX_NEARBY    = 7      # 홀수 권장 (과거 3 + 현재 + 미래 3)
_THUMB_SIZE    = 220

# label 값 → 행 배경색
_LABEL_COLOR: dict[int, QColor] = {
    1:  QColor(190, 240, 190),   # Human      — 연초록
    0:  QColor(255, 190, 190),   # Background — 연빨강
   -1:  QColor(210, 210, 210),   # Unknown    — 회색
}
# label 값 → 표시 텍스트 (cam_label / label 공용)
_LABEL_TEXT = {1: "🚶 Human (1)", 0: "🌄 BG (0)", -1: "❓ Unknown (-1)"}

# QButtonGroup id (Qt 예약값 -1 충돌 방지 → 100/200/300 사용)
_RB_ID_TO_VAL = {100: 1, 200: 0, 300: -1}
_VAL_TO_RB_ID = {v: k for k, v in _RB_ID_TO_VAL.items()}

# 테이블 컬럼 인덱스
_COL_CHK = 0   # ☑ 체크박스 (UserRole = orig_idx)
_COL_NUM = 1   # 행 번호
_COL_CAM = 2   # cam_label (참조용)
_COL_LBL = 3   # label (편집 대상, 색상 기준)
_COL_HM  = 4   # hm_conf
_COL_BG  = 5   # bg_conf
_COL_TS  = 6   # timestamp


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────────────────────
def _load_pixmap(path: str, max_px: int = _THUMB_SIZE) -> Optional[QPixmap]:
    """파일에서 QPixmap 로드 (비율 유지). 실패 시 None."""
    if not os.path.isfile(path):
        return None
    px = QPixmap(path)
    if px.isNull():
        return None
    return px.scaled(
        max_px, max_px,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _find_nearby_snapshots(ts: float, snap_dir: str, window: float) -> List[Tuple[float, str]]:
    """
    ts ± window 초 이내 스냅샷을 시간 오름차순(부호 있는 delta)으로 반환.
    반환: [(signed_delta, fpath), ...] — 음수=이전 프레임, 양수=이후 프레임
    """
    results: List[Tuple[float, str]] = []
    for fpath in glob.glob(os.path.join(snap_dir, "frame_*.jpg")):
        stem = os.path.basename(fpath)[len("frame_"):-len(".jpg")]
        try:
            fts   = float(stem)
            delta = fts - ts          # 부호 있는 시간 차이
            if abs(delta) <= window:
                results.append((delta, fpath))
        except ValueError:
            continue
    results.sort(key=lambda x: x[0])  # 시간 오름차순 (과거 → 미래)
    return results


def _calc_fps(snap_dir: str) -> Optional[float]:
    """스냅샷 파일명 타임스탬프 기반 FPS 추정 (중앙값 간격 사용)."""
    timestamps: List[float] = []
    for fpath in glob.glob(os.path.join(snap_dir, "frame_*.jpg")):
        stem = os.path.basename(fpath)[len("frame_"):-len(".jpg")]
        try:
            timestamps.append(float(stem))
        except ValueError:
            continue
    if len(timestamps) < 2:
        return None
    timestamps.sort()
    diffs = sorted(timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1))
    median_diff = diffs[len(diffs) // 2]
    return (1.0 / median_diff) if median_diff > 0 else None


# ─────────────────────────────────────────────────────────────────────────────
# 이미지 카드 위젯
# ─────────────────────────────────────────────────────────────────────────────
class _ImageCard(QFrame):
    """스냅샷 1장 + 방향 정보 카드."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.Box)
        self.setFixedWidth(_THUMB_SIZE + 20)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)

        self._img = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._img.setFixedSize(_THUMB_SIZE, _THUMB_SIZE)
        self._img.setStyleSheet("background: #1a1a1a;")
        lay.addWidget(self._img)

        self._dir_lbl = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._dir_lbl.setStyleSheet("font-size: 11px; font-weight: bold;")
        lay.addWidget(self._dir_lbl)

        self._name_lbl = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._name_lbl.setStyleSheet("font-size: 9px; color: #666;")
        self._name_lbl.setWordWrap(True)
        lay.addWidget(self._name_lbl)

    def set_snap(self, fpath: str, delta: float) -> None:
        px = _load_pixmap(fpath)
        if px:
            self._img.setPixmap(px)
            self._img.setText("")
        else:
            self._img.clear()
            self._img.setText("load err")

        is_exact = abs(delta) < 0.002
        if is_exact:
            self._dir_lbl.setText("🎯 현재 프레임")
            self._dir_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #00aa00;")
            self.setStyleSheet("QFrame { border: 2px solid #00aa00; }")
        elif delta < 0:
            self._dir_lbl.setText(f"◀ {delta:.3f}s  (이전)")
            self._dir_lbl.setStyleSheet("font-size: 10px; color: #4488ff;")
            self.setStyleSheet("")
        else:
            self._dir_lbl.setText(f"이후  +{delta:.3f}s ▶")
            self._dir_lbl.setStyleSheet("font-size: 10px; color: #ff8844;")
            self.setStyleSheet("")

        self._name_lbl.setText(os.path.basename(fpath)[:28])

    def clear_snap(self) -> None:
        self._img.clear()
        self._img.setText("no image")
        self._dir_lbl.setText("")
        self._name_lbl.setText("")
        self.setStyleSheet("")


# ─────────────────────────────────────────────────────────────────────────────
# 메인 윈도우
# ─────────────────────────────────────────────────────────────────────────────
class CsvLabelEditor(QMainWindow):
    """CSV label 검토 및 편집 메인 윈도우."""

    def __init__(self, initial_csv: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowTitle("📋 CSV label 편집기")
        self.resize(1600, 900)

        # 상태 변수
        self._csv_path:     Optional[str]             = None
        self._headers:      List[str]                 = []
        self._rows:         List[List[str]]            = []
        self._modified:     bool                      = False
        self._current_orig: int                       = -1
        self._snap_dir:     str                       = _SNAP_DIR_DEF
        self._fps_cache:    Dict[str, Optional[float]] = {}

        # 컬럼 인덱스 (CSV 로드 후 갱신)
        self._ci_cam_label   = -1
        self._ci_cam_hm_conf = -1
        self._ci_cam_bg_conf = -1
        self._ci_timestamp   = -1
        self._ci_label       = -1

        self._build_ui()
        self._refresh_csv_list()

        # 단축키
        QShortcut(QKeySequence(Qt.Key.Key_Left),  self, self._go_prev)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._go_next)
        QShortcut(QKeySequence("Ctrl+S"),          self, self._save_csv)
        QShortcut(QKeySequence(Qt.Key.Key_0),      self, lambda: self._quick_label(0))
        QShortcut(QKeySequence(Qt.Key.Key_1),      self, lambda: self._quick_label(1))
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self._apply_and_next)
        QShortcut(QKeySequence(Qt.Key.Key_Enter),  self, self._apply_and_next)

        if initial_csv:
            self._load_csv(initial_csv)

    # ─────────────────────────────────────────────────────────────────────────
    # UI 빌드
    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        vlay = QVBoxLayout(root)
        vlay.setContentsMargins(6, 6, 6, 6)
        vlay.setSpacing(6)

        # ── 파일 툴바 ─────────────────────────────────────────────────────────
        tb = QHBoxLayout()
        tb.addWidget(QLabel("CSV:"))
        self._csv_combo = QComboBox()
        self._csv_combo.setMinimumWidth(380)
        tb.addWidget(self._csv_combo, 1)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(32)
        btn_refresh.setToolTip("data_csv/ 목록 새로고침")
        btn_refresh.clicked.connect(self._refresh_csv_list)
        tb.addWidget(btn_refresh)

        btn_load = QPushButton("📂 불러오기")
        btn_load.clicked.connect(self._on_load_combo)
        tb.addWidget(btn_load)

        btn_browse = QPushButton("🗂 파일 선택…")
        btn_browse.clicked.connect(self._on_browse)
        tb.addWidget(btn_browse)

        self._save_btn = QPushButton("💾 저장 (Ctrl+S)")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_csv)
        tb.addWidget(self._save_btn)
        vlay.addLayout(tb)

        # ── 스냅샷 설정 바 ────────────────────────────────────────────────────
        sb = QHBoxLayout()
        sb.addWidget(QLabel("스냅샷 폴더:"))
        self._snap_lbl = QLabel(_SNAP_DIR_DEF)
        self._snap_lbl.setStyleSheet("color: #555; font-size: 11px;")
        sb.addWidget(self._snap_lbl, 1)

        btn_snap = QPushButton("📁")
        btn_snap.setFixedWidth(32)
        btn_snap.setToolTip("스냅샷 폴더 변경")
        btn_snap.clicked.connect(self._on_snap_browse)
        sb.addWidget(btn_snap)

        sb.addWidget(QLabel("  근방 ±"))
        self._win_spin = QSpinBox()
        self._win_spin.setRange(1, 120)
        self._win_spin.setValue(int(_NEARBY_WIN))
        self._win_spin.setSuffix(" 초")
        self._win_spin.setFixedWidth(80)
        self._win_spin.valueChanged.connect(self._on_window_changed)
        sb.addWidget(self._win_spin)

        self._fps_lbl = QLabel("")
        self._fps_lbl.setStyleSheet("color: #333; font-size: 11px; margin-left: 12px;")
        sb.addWidget(self._fps_lbl)
        sb.addStretch()
        vlay.addLayout(sb)

        # ── 본체 ──────────────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        vlay.addWidget(splitter, 1)

        # ── 좌측: 행 테이블 ───────────────────────────────────────────────────
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)

        flt_row = QHBoxLayout()
        flt_row.addWidget(QLabel("필터:"))
        self._filter_cb = QComboBox()
        self._filter_cb.addItems(["전체", "🚶 Human (1)", "🌄 BG (0)", "❓ Unknown (-1)"])
        self._filter_cb.currentIndexChanged.connect(self._apply_filter)
        flt_row.addWidget(self._filter_cb)

        btn_chk_all  = QPushButton("☑ 전체 선택")
        btn_chk_all.setFixedWidth(90)
        btn_chk_all.clicked.connect(lambda: self._set_all_checked(True))
        flt_row.addWidget(btn_chk_all)

        btn_chk_none = QPushButton("☐ 선택 해제")
        btn_chk_none.setFixedWidth(90)
        btn_chk_none.clicked.connect(lambda: self._set_all_checked(False))
        flt_row.addWidget(btn_chk_none)

        flt_row.addStretch()
        self._cnt_lbl = QLabel("0 행")
        flt_row.addWidget(self._cnt_lbl)
        lv.addLayout(flt_row)

        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["☑", "#", "cam_label", "label", "hm_conf", "bg_conf", "timestamp"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(_COL_CHK, 28)
        self._table.setColumnWidth(_COL_NUM, 50)
        self._table.setColumnWidth(_COL_CAM, 120)
        self._table.setColumnWidth(_COL_LBL, 120)
        self._table.setColumnWidth(_COL_HM,  65)
        self._table.setColumnWidth(_COL_BG,  65)
        self._table.currentCellChanged.connect(
            lambda row, _col, _pr, _pc: self._on_table_row_changed(row)
        )
        self._table.itemChanged.connect(self._on_item_changed)
        lv.addWidget(self._table, 1)

        splitter.addWidget(left)

        # ── 우측 ──────────────────────────────────────────────────────────────
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)

        # 이미지 영역
        img_group = QGroupBox("📸 근방 스냅샷  (◀ 이전  |  🎯 현재  |  이후 ▶)")
        ig = QVBoxLayout(img_group)

        self._img_scroll = QScrollArea()
        self._img_scroll.setWidgetResizable(True)
        self._img_scroll.setFixedHeight(_THUMB_SIZE + 95)
        self._img_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        img_inner = QWidget()
        self._img_hlay = QHBoxLayout(img_inner)
        self._img_hlay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._img_hlay.setSpacing(8)
        self._img_scroll.setWidget(img_inner)
        ig.addWidget(self._img_scroll)

        self._cards: List[_ImageCard] = []
        for _ in range(_MAX_NEARBY):
            card = _ImageCard()
            card.hide()
            self._img_hlay.addWidget(card)
            self._cards.append(card)

        self._no_img_lbl = QLabel(
            "스냅샷 없음\n(data_csv/snapshots/ 폴더 확인 또는 근방 범위를 늘려보세요)"
        )
        self._no_img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_img_lbl.setStyleSheet("color: #888; font-size: 12px;")
        self._img_hlay.addWidget(self._no_img_lbl)

        rv.addWidget(img_group)

        # 행 정보
        info_group = QGroupBox("ℹ️ 현재 행 정보")
        ig2 = QHBoxLayout(info_group)
        ig2.setSpacing(14)

        def _info_pair(lbl: str) -> QLabel:
            ig2.addWidget(QLabel(f"<b>{lbl}</b>"))
            v = QLabel("—")
            v.setMinimumWidth(110)
            ig2.addWidget(v)
            return v

        self._i_row = _info_pair("행:")
        self._i_cam = _info_pair("cam_label:")
        self._i_lbl = _info_pair("label:")
        self._i_hm  = _info_pair("hm_conf:")
        self._i_bg  = _info_pair("bg_conf:")
        self._i_ts  = _info_pair("timestamp:")
        ig2.addStretch()
        rv.addWidget(info_group)

        # 편집 패널
        edit_group = QGroupBox("✏️ label 편집")
        eg = QVBoxLayout(edit_group)

        rb_row = QHBoxLayout()
        rb_row.addWidget(QLabel("새 label:"))
        self._rb_human = QRadioButton("🚶 Human (1)")
        self._rb_bg    = QRadioButton("🌄 Background (0)")
        self._rb_unk   = QRadioButton("❓ Unknown (-1)")
        self._rb_grp   = QButtonGroup(self)
        self._rb_grp.addButton(self._rb_human, 100)
        self._rb_grp.addButton(self._rb_bg,    200)
        self._rb_grp.addButton(self._rb_unk,   300)
        rb_row.addWidget(self._rb_human)
        rb_row.addWidget(self._rb_bg)
        rb_row.addWidget(self._rb_unk)
        rb_row.addStretch()
        eg.addLayout(rb_row)

        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton("✅ 적용")
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)

        self._apply_next_btn = QPushButton("✅ 적용 & 다음 (Enter)")
        self._apply_next_btn.clicked.connect(self._apply_and_next)
        btn_row.addWidget(self._apply_next_btn)

        btn_row.addSpacing(16)
        self._prev_btn = QPushButton("◀ 이전 (←)")
        self._prev_btn.clicked.connect(self._go_prev)
        btn_row.addWidget(self._prev_btn)

        self._next_btn = QPushButton("다음 (→) ▶")
        self._next_btn.clicked.connect(self._go_next)
        btn_row.addWidget(self._next_btn)
        btn_row.addStretch()
        eg.addLayout(btn_row)

        # 일괄 적용 행
        bulk_row = QHBoxLayout()
        self._checked_cnt_lbl = QLabel("☑ 0개 선택")
        self._checked_cnt_lbl.setStyleSheet("font-weight: bold;")
        bulk_row.addWidget(self._checked_cnt_lbl)

        self._bulk_btn = QPushButton("📋 선택 행 일괄 적용")
        self._bulk_btn.setToolTip("체크된 모든 행에 위에서 선택한 label을 일괄 적용합니다.")
        self._bulk_btn.clicked.connect(self._bulk_apply)
        bulk_row.addWidget(self._bulk_btn)
        bulk_row.addStretch()
        eg.addLayout(bulk_row)

        hint = QLabel(
            "단축키:  ← →  이동  |  0  BG  |  1  Human  |  Enter  적용+다음  |  Ctrl+S  저장"
        )
        hint.setStyleSheet("color: #777; font-size: 11px;")
        eg.addWidget(hint)

        rv.addWidget(edit_group)
        splitter.addWidget(right)
        splitter.setSizes([430, 1170])

        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("CSV 파일을 선택하고 '불러오기'를 클릭하세요.")

    # ─────────────────────────────────────────────────────────────────────────
    # CSV 파일 목록 갱신
    # ─────────────────────────────────────────────────────────────────────────
    def _refresh_csv_list(self) -> None:
        prev = self._csv_combo.currentText()
        self._csv_combo.clear()
        for f in sorted(glob.glob(os.path.join(_CSV_DIR, "*.csv")), reverse=True):
            self._csv_combo.addItem(os.path.basename(f), userData=f)
        idx = self._csv_combo.findText(prev)
        if idx >= 0:
            self._csv_combo.setCurrentIndex(idx)

    # ─────────────────────────────────────────────────────────────────────────
    # CSV 로드
    # ─────────────────────────────────────────────────────────────────────────
    def _on_load_combo(self) -> None:
        path = self._csv_combo.currentData()
        if path:
            self._load_csv(path)

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "CSV 파일 선택", _CSV_DIR, "CSV (*.csv)")
        if path:
            self._load_csv(path)

    def _load_csv(self, path: str) -> None:
        if self._modified and not self._confirm_discard():
            return
        try:
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        except OSError as e:
            QMessageBox.critical(self, "오류", f"파일 읽기 실패:\n{e}")
            return
        if not rows:
            QMessageBox.warning(self, "경고", "빈 CSV 파일입니다.")
            return

        self._headers  = rows[0]
        self._rows     = rows[1:]
        self._csv_path = path
        self._modified = False

        h = self._headers
        self._ci_cam_label   = h.index("cam_label")   if "cam_label"   in h else -1
        self._ci_cam_hm_conf = h.index("cam_hm_conf") if "cam_hm_conf" in h else -1
        self._ci_cam_bg_conf = h.index("cam_bg_conf") if "cam_bg_conf" in h else -1
        self._ci_timestamp   = h.index("timestamp")   if "timestamp"   in h else -1
        self._ci_label       = h.index("label")       if "label"       in h else -1

        if self._ci_label == -1:
            QMessageBox.warning(self, "경고", "CSV에 'label' 컬럼이 없습니다.")

        self._build_table()
        self._save_btn.setEnabled(True)
        self.setWindowTitle(f"📋 CSV label 편집기 — {os.path.basename(path)}")
        self._statusbar.showMessage(f"로드: {path}  ({len(self._rows)} 행)")
        if self._rows:
            self._table.selectRow(0)

    # ─────────────────────────────────────────────────────────────────────────
    # 테이블 빌드
    # ─────────────────────────────────────────────────────────────────────────
    def _build_table(self) -> None:
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        for orig_idx, row in enumerate(self._rows):
            self._append_table_row(orig_idx, row)
        self._table.blockSignals(False)
        self._apply_filter()
        self._update_check_count()

    def _append_table_row(self, orig_idx: int, row: List[str]) -> None:
        tr = self._table.rowCount()
        self._table.insertRow(tr)

        def _get(ci: int) -> str:
            return row[ci] if 0 <= ci < len(row) else "—"

        cam_str = _get(self._ci_cam_label)
        lbl_str = _get(self._ci_label)
        hm_str  = _get(self._ci_cam_hm_conf)
        bg_str  = _get(self._ci_cam_bg_conf)
        ts_str  = _get(self._ci_timestamp)

        # label → 색상 기준
        try:
            lbl_val  = int(float(lbl_str))
            lbl_disp = _LABEL_TEXT.get(lbl_val, lbl_str)
            bg_color = _LABEL_COLOR.get(lbl_val, QColor(255, 255, 255))
        except (ValueError, TypeError):
            lbl_disp = lbl_str
            bg_color = QColor(255, 255, 255)

        # cam_label 표시 텍스트
        try:
            cam_val  = int(float(cam_str))
            cam_disp = _LABEL_TEXT.get(cam_val, cam_str)
        except (ValueError, TypeError):
            cam_disp = cam_str

        try:
            hm_disp = f"{float(hm_str):.3f}"
            bg_disp = f"{float(bg_str):.3f}"
        except (ValueError, TypeError):
            hm_disp = hm_str
            bg_disp = bg_str

        try:
            ts_disp = f"{float(ts_str):.3f}"
        except (ValueError, TypeError):
            ts_disp = ts_str

        brush    = QBrush(bg_color)
        black_fg = QBrush(Qt.GlobalColor.black)

        # Col 0: 체크박스 — UserRole에 orig_idx 저장
        chk_item = QTableWidgetItem()
        chk_item.setData(Qt.ItemDataRole.UserRole, orig_idx)
        chk_item.setCheckState(Qt.CheckState.Unchecked)
        chk_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsSelectable
        )
        chk_item.setBackground(brush)
        self._table.setItem(tr, _COL_CHK, chk_item)

        # Col 1~6: 데이터 셀 (검은 폰트)
        cells = [str(orig_idx + 1), cam_disp, lbl_disp, hm_disp, bg_disp, ts_disp]
        for c_off, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, orig_idx)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(brush)
            item.setForeground(black_fg)
            self._table.setItem(tr, _COL_NUM + c_off, item)

    def _refresh_table_row(self, orig_idx: int) -> None:
        """orig_idx 행의 label 텍스트/색상 갱신."""
        for tr in range(self._table.rowCount()):
            chk = self._table.item(tr, _COL_CHK)
            if chk and chk.data(Qt.ItemDataRole.UserRole) == orig_idx:
                row = self._rows[orig_idx]
                lbl_str = row[self._ci_label] if 0 <= self._ci_label < len(row) else "—"
                try:
                    lbl_val  = int(float(lbl_str))
                    lbl_disp = _LABEL_TEXT.get(lbl_val, lbl_str)
                    brush    = QBrush(_LABEL_COLOR.get(lbl_val, QColor(255, 255, 255)))
                except (ValueError, TypeError):
                    lbl_disp = lbl_str
                    brush    = QBrush(QColor(255, 255, 255))

                black_fg = QBrush(Qt.GlobalColor.black)
                it = self._table.item(tr, _COL_LBL)
                if it:
                    it.setText(lbl_disp)
                for c in range(7):
                    it2 = self._table.item(tr, c)
                    if it2:
                        it2.setBackground(brush)
                        it2.setForeground(black_fg)
                break

    # ─────────────────────────────────────────────────────────────────────────
    # 체크박스 관련
    # ─────────────────────────────────────────────────────────────────────────
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == _COL_CHK:
            self._update_check_count()

    def _update_check_count(self) -> None:
        count = sum(
            1
            for tr in range(self._table.rowCount())
            if not self._table.isRowHidden(tr)
            and self._table.item(tr, _COL_CHK) is not None
            and self._table.item(tr, _COL_CHK).checkState() == Qt.CheckState.Checked
        )
        self._checked_cnt_lbl.setText(f"☑ {count}개 선택")

    def _set_all_checked(self, state: bool) -> None:
        cs = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        self._table.blockSignals(True)
        for tr in range(self._table.rowCount()):
            if not self._table.isRowHidden(tr):
                chk = self._table.item(tr, _COL_CHK)
                if chk:
                    chk.setCheckState(cs)
        self._table.blockSignals(False)
        self._update_check_count()

    # ─────────────────────────────────────────────────────────────────────────
    # 필터 (label 기준)
    # ─────────────────────────────────────────────────────────────────────────
    def _apply_filter(self) -> None:
        fi     = self._filter_cb.currentIndex()
        target = {0: None, 1: 1, 2: 0, 3: -1}.get(fi)
        visible = 0
        for tr in range(self._table.rowCount()):
            chk = self._table.item(tr, _COL_CHK)
            if chk is None:
                self._table.setRowHidden(tr, False)
                visible += 1
                continue
            orig_idx = chk.data(Qt.ItemDataRole.UserRole)
            if target is None:
                self._table.setRowHidden(tr, False)
                visible += 1
            else:
                row = self._rows[orig_idx] if 0 <= orig_idx < len(self._rows) else []
                try:
                    val = (
                        int(float(row[self._ci_label]))
                        if 0 <= self._ci_label < len(row)
                        else None
                    )
                except (ValueError, IndexError):
                    val = None
                hide = (val != target)
                self._table.setRowHidden(tr, hide)
                if not hide:
                    visible += 1
        self._cnt_lbl.setText(f"{visible} / {len(self._rows)} 행")
        self._update_check_count()

    # ─────────────────────────────────────────────────────────────────────────
    # 행 선택 → 상세 갱신
    # ─────────────────────────────────────────────────────────────────────────
    def _on_table_row_changed(self, tr: int) -> None:
        if tr < 0:
            return
        chk = self._table.item(tr, _COL_CHK)
        if chk is None:
            return
        orig_idx = chk.data(Qt.ItemDataRole.UserRole)
        if orig_idx is None:
            return
        self._current_orig = orig_idx
        self._refresh_detail(orig_idx)

    def _refresh_detail(self, orig_idx: int) -> None:
        if orig_idx < 0 or orig_idx >= len(self._rows):
            return
        row = self._rows[orig_idx]

        def _v(ci: int) -> str:
            return row[ci] if 0 <= ci < len(row) else "N/A"

        cam_str = _v(self._ci_cam_label)
        lbl_str = _v(self._ci_label)
        hm_str  = _v(self._ci_cam_hm_conf)
        bg_str  = _v(self._ci_cam_bg_conf)
        ts_str  = _v(self._ci_timestamp)

        self._i_row.setText(f"{orig_idx + 1} / {len(self._rows)}")

        # cam_label 표시 (참조용)
        try:
            cam_val = int(float(cam_str))
            self._i_cam.setText(_LABEL_TEXT.get(cam_val, cam_str))
            c = _LABEL_COLOR.get(cam_val, QColor(255, 255, 255))
            self._i_cam.setStyleSheet(
                f"font-weight: bold; padding: 2px 5px; border-radius: 3px; color: black;"
                f"background: rgb({c.red()},{c.green()},{c.blue()});"
            )
        except (ValueError, TypeError):
            self._i_cam.setText(cam_str)
            self._i_cam.setStyleSheet("color: black;")

        # label 표시 + 라디오버튼 동기화
        try:
            lbl_val = int(float(lbl_str))
            self._i_lbl.setText(_LABEL_TEXT.get(lbl_val, lbl_str))
            c = _LABEL_COLOR.get(lbl_val, QColor(255, 255, 255))
            self._i_lbl.setStyleSheet(
                f"font-weight: bold; font-size: 13px; padding: 2px 5px; "
                f"border-radius: 3px; color: black;"
                f"background: rgb({c.red()},{c.green()},{c.blue()});"
            )
            btn = self._rb_grp.button(_VAL_TO_RB_ID.get(lbl_val, 0))
            if btn:
                btn.setChecked(True)
        except (ValueError, TypeError):
            self._i_lbl.setText(lbl_str)
            self._i_lbl.setStyleSheet("color: black;")

        try:
            self._i_hm.setText(f"{float(hm_str):.4f}")
        except (ValueError, TypeError):
            self._i_hm.setText(hm_str)

        try:
            self._i_bg.setText(f"{float(bg_str):.4f}")
        except (ValueError, TypeError):
            self._i_bg.setText(bg_str)

        ts_float: Optional[float] = None
        try:
            ts_float = float(ts_str)
            self._i_ts.setText(f"{ts_float:.3f}")
        except (ValueError, TypeError):
            self._i_ts.setText(ts_str)

        self._update_images(ts_float)

    # ─────────────────────────────────────────────────────────────────────────
    # 이미지 갱신 + FPS
    # ─────────────────────────────────────────────────────────────────────────
    def _update_images(self, ts: Optional[float]) -> None:
        for card in self._cards:
            card.hide()
        self._no_img_lbl.show()

        if ts is None:
            return

        snaps = _find_nearby_snapshots(ts, self._snap_dir, float(self._win_spin.value()))
        snaps = snaps[:_MAX_NEARBY]
        if not snaps:
            return

        self._no_img_lbl.hide()
        for i, (delta, fpath) in enumerate(snaps):
            self._cards[i].set_snap(fpath, delta)
            self._cards[i].show()

        fps = self._get_fps()
        self._fps_lbl.setText(f"📹 약 {fps:.1f} FPS" if fps is not None else "")

    def _get_fps(self) -> Optional[float]:
        if self._snap_dir not in self._fps_cache:
            self._fps_cache[self._snap_dir] = _calc_fps(self._snap_dir)
        return self._fps_cache[self._snap_dir]

    def _on_window_changed(self) -> None:
        if self._current_orig >= 0:
            self._refresh_detail(self._current_orig)

    # ─────────────────────────────────────────────────────────────────────────
    # 편집 — 단일 행
    # ─────────────────────────────────────────────────────────────────────────
    def _on_apply(self) -> None:
        rb_id = self._rb_grp.checkedId()
        if rb_id in _RB_ID_TO_VAL:
            self._apply_label(self._current_orig, _RB_ID_TO_VAL[rb_id])

    def _apply_and_next(self) -> None:
        self._on_apply()
        self._go_next()

    def _quick_label(self, value: int) -> None:
        btn = self._rb_grp.button(_VAL_TO_RB_ID.get(value, 0))
        if btn:
            btn.setChecked(True)
        self._apply_label(self._current_orig, value)

    def _apply_label(self, orig_idx: int, value: int) -> None:
        if orig_idx < 0 or orig_idx >= len(self._rows):
            return
        if self._ci_label < 0:
            QMessageBox.warning(self, "오류", "label 컬럼이 없습니다.")
            return

        row = self._rows[orig_idx]
        old = row[self._ci_label]
        row[self._ci_label] = str(float(value))   # CSV 원본 형식(1.0/0.0) 유지
        self._modified = True

        self._table.blockSignals(True)
        self._refresh_table_row(orig_idx)
        self._table.blockSignals(False)

        self._apply_filter()
        self._refresh_detail(orig_idx)
        self._statusbar.showMessage(
            f"행 {orig_idx + 1}: label {old} → {value}  (미저장 — Ctrl+S)"
        )
        base = os.path.basename(self._csv_path) if self._csv_path else "—"
        self.setWindowTitle(f"📋 CSV label 편집기 — *{base}")

    # ─────────────────────────────────────────────────────────────────────────
    # 편집 — 일괄 적용
    # ─────────────────────────────────────────────────────────────────────────
    def _bulk_apply(self) -> None:
        rb_id = self._rb_grp.checkedId()
        if rb_id not in _RB_ID_TO_VAL:
            QMessageBox.warning(self, "알림", "적용할 label을 먼저 선택하세요.")
            return
        value = _RB_ID_TO_VAL[rb_id]

        checked_idxs: List[int] = [
            self._table.item(tr, _COL_CHK).data(Qt.ItemDataRole.UserRole)
            for tr in range(self._table.rowCount())
            if not self._table.isRowHidden(tr)
            and self._table.item(tr, _COL_CHK) is not None
            and self._table.item(tr, _COL_CHK).checkState() == Qt.CheckState.Checked
        ]

        if not checked_idxs:
            QMessageBox.information(self, "알림", "체크된 행이 없습니다.")
            return

        ret = QMessageBox.question(
            self, "일괄 적용 확인",
            f"체크된 {len(checked_idxs)}개 행의 label을\n"
            f"'{_LABEL_TEXT.get(value, str(value))}'으로 변경하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        self._table.blockSignals(True)
        for orig_idx in checked_idxs:
            row = self._rows[orig_idx]
            if 0 <= self._ci_label < len(row):
                row[self._ci_label] = str(float(value))
            self._refresh_table_row(orig_idx)
        self._table.blockSignals(False)

        self._modified = True
        self._apply_filter()
        if self._current_orig >= 0:
            self._refresh_detail(self._current_orig)

        base = os.path.basename(self._csv_path) if self._csv_path else "—"
        self.setWindowTitle(f"📋 CSV label 편집기 — *{base}")
        self._statusbar.showMessage(
            f"일괄 적용 완료: {len(checked_idxs)}개 행 → "
            f"{_LABEL_TEXT.get(value, str(value))}  (Ctrl+S로 저장)"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 행 이동
    # ─────────────────────────────────────────────────────────────────────────
    def _go_prev(self) -> None:
        cur = self._table.currentRow()
        for tr in range(cur - 1, -1, -1):
            if not self._table.isRowHidden(tr):
                self._table.selectRow(tr)
                self._table.scrollToItem(self._table.item(tr, _COL_NUM))
                return

    def _go_next(self) -> None:
        cur = self._table.currentRow()
        for tr in range(cur + 1, self._table.rowCount()):
            if not self._table.isRowHidden(tr):
                self._table.selectRow(tr)
                self._table.scrollToItem(self._table.item(tr, _COL_NUM))
                return

    # ─────────────────────────────────────────────────────────────────────────
    # 저장
    # ─────────────────────────────────────────────────────────────────────────
    def _save_csv(self) -> None:
        if not self._csv_path or not self._rows:
            return
        try:
            with open(self._csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._headers)
                writer.writerows(self._rows)
            self._modified = False
            base = os.path.basename(self._csv_path)
            self.setWindowTitle(f"📋 CSV label 편집기 — {base}")
            self._statusbar.showMessage(f"저장 완료: {self._csv_path}")
        except OSError as e:
            QMessageBox.critical(self, "저장 실패", str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # 스냅샷 폴더
    # ─────────────────────────────────────────────────────────────────────────
    def _on_snap_browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "스냅샷 폴더 선택", self._snap_dir)
        if d:
            self._snap_dir = d
            self._snap_lbl.setText(d)
            self._fps_cache.clear()
            if self._current_orig >= 0:
                self._refresh_detail(self._current_orig)

    # ─────────────────────────────────────────────────────────────────────────
    # 닫기 확인
    # ─────────────────────────────────────────────────────────────────────────
    def _confirm_discard(self) -> bool:
        ret = QMessageBox.question(
            self, "저장하지 않은 변경",
            "저장하지 않은 변경사항이 있습니다. 계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return ret == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._modified:
            ret = QMessageBox.question(
                self, "저장하지 않은 변경",
                "저장하지 않은 변경사항이 있습니다. 종료 전에 저장하시겠습니까?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if ret == QMessageBox.StandardButton.Save:
                self._save_csv()
                event.accept()
            elif ret == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    win = CsvLabelEditor(initial_csv=initial)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
