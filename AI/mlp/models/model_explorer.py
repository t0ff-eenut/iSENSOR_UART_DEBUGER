"""
╔══════════════════════════════════════════════════════════════════╗
║  iSENSOR MLP Model Explorer  —  PyQt6 GUI                       ║
║  실행: python AI/mlp/model_explorer.py                           ║
╚══════════════════════════════════════════════════════════════════╝

[ 기능 ]
  • 필터 패널 — 레이어, 특징수, 드롭아웃, 배치, LR 기준 필터링
  • 모델 테이블 — Val Acc·Loss 기준 정렬, 다중 선택 지원
  • 비교 보기 탭 — Ctrl+다중선택 → 지표 비교 테이블
  • 곡선 비교 탭 — Val Acc / Val Loss / LR / LR 감소 효과 오버레이
"""

import sys
import os
import re
import json
import subprocess
from pathlib import Path

import numpy as np
import matplotlib
import matplotlib.ticker
from matplotlib.gridspec import GridSpecFromSubplotSpec as _GSFS
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter,
    QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QGroupBox, QCheckBox, QPushButton, QProgressBar,
    QTabWidget, QSizePolicy, QStatusBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont, QColor

# ── 경로 설정 ──────────────────────────────────────────────────────
# 스크립트 위치: AI/mlp/models/model_explorer.py
_HERE      = Path(__file__).resolve().parent   # AI/mlp/models/
SCRIPT_DIR = _HERE.parent                      # AI/mlp/
MODELS_DIR  = _HERE                            # AI/mlp/models/
RESULTS_DIR = SCRIPT_DIR / 'results'           # AI/mlp/results/

# ── 한글 폰트 ──────────────────────────────────────────────────────
_FONT_KO = 'Malgun Gothic'


# ════════════════════════════════════════════════════════════════════
#  메타데이터 파싱
# ════════════════════════════════════════════════════════════════════

def _parse_model_folder(name: str) -> dict:
    """폴더명에서 하이퍼파라미터 추출 + _history.json 에서 지표 로드."""
    info = {'name': name}

    # 레이어 구조: _L{layers}_b  (예: 128-64-32, 64-32_rb)
    m = re.search(r'_L([\w-]+)_b', name)
    if m:
        info['layers'] = m.group(1)

    # 특징 수 (숫자 부분만)
    m = re.search(r'_F(\d+)', name)
    if m:
        info['features'] = m.group(1)
    info['is_pc'] = '_PC_' in name

    # 드롭아웃: _D{n}_  → 0.n
    m = re.search(r'_D(\d+)_', name)
    if m:
        info['dropout'] = int(m.group(1)) / 10.0

    # 배치 크기
    m = re.search(r'_b(\d+)_', name)
    if m:
        info['batch'] = int(m.group(1))

    # 초기 LR
    m = re.search(r'_LR([\de-]+)_', name)
    if m:
        info['lr'] = m.group(1)

    # LR factor / patience
    m = re.search(r'_LRF(\d+)_', name)
    if m:
        info['lrf'] = int(m.group(1))

    m = re.search(r'_LRP(\d+)_', name)
    if m:
        info['lrp'] = int(m.group(1))

    # 에폭
    m = re.search(r'_ep(\d+)_', name)
    if m:
        info['epochs'] = int(m.group(1))

    # 타임스탬프 (MMDD_HHMMSS)
    m = re.search(r'_(\d{4}_\d{6})$', name)
    if m:
        info['datetime'] = m.group(1)

    # 학습 지표 로드
    hist_path = MODELS_DIR / name / f'{name}_history.json'
    if hist_path.exists():
        try:
            with open(hist_path, encoding='utf-8') as f:
                h = json.load(f)
            if h.get('val_acc'):
                info['best_val_acc']   = max(h['val_acc']) * 100
                info['final_val_acc']  = h['val_acc'][-1] * 100
            if h.get('val_loss'):
                info['best_val_loss']  = min(h['val_loss'])
                info['final_val_loss'] = h['val_loss'][-1]
            if h.get('train_acc'):
                info['train_acc_last'] = h['train_acc'][-1] * 100
            if h.get('train_loss'):
                info['train_loss_last'] = h['train_loss'][-1]
            # 과적합 지표
            if 'train_acc_last' in info and 'best_val_acc' in info:
                info['gap_acc'] = info['train_acc_last'] - info['best_val_acc']
            if 'train_loss_last' in info and 'final_val_loss' in info:
                info['gap_loss'] = info['final_val_loss'] - info['train_loss_last']
            if 'best_val_loss' in info and 'final_val_loss' in info:
                info['val_rebound'] = info['final_val_loss'] - info['best_val_loss']
            if h.get('best_epoch') is not None and h.get('val_acc'):
                info['best_epoch_h'] = h['best_epoch']
                info['overrun'] = len(h['val_acc']) - h['best_epoch']
        except Exception:
            pass

    return info


def _list_sorted_folders() -> list[str]:
    """models/ 에서 MLP_* 폴더를 타임스탬프 내림차순으로 반환 (visualize.py 와 동일 정렬)."""
    if not MODELS_DIR.exists():
        return []
    return sorted(
        [d.name for d in MODELS_DIR.iterdir()
         if d.is_dir() and d.name.startswith('MLP_')],
        key=lambda d: d.rsplit('_', 2)[-2:],
        reverse=True,
    )


def load_all_models() -> list[dict]:
    return [_parse_model_folder(f) for f in _list_sorted_folders()]


def find_existing_png(model_name: str) -> Path | None:
    """results/ 에서 {model_name}*.png 탐색."""
    if not RESULTS_DIR.exists():
        return None
    for p in RESULTS_DIR.glob(f'{model_name}*.png'):
        return p
    return None


def _load_history(model_name: str) -> dict | None:
    """모델 폴더의 _history.json 전체 내용 반환. 없으면 None."""
    hist_path = MODELS_DIR / model_name / f'{model_name}_history.json'
    if not hist_path.exists():
        return None
    try:
        with open(hist_path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════
#  숫자 정렬 가능한 TableWidgetItem
# ════════════════════════════════════════════════════════════════════

class _NumItem(QTableWidgetItem):
    """숫자 문자열을 수치로 비교하는 테이블 아이템."""
    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return float(self.text().strip('% ')) < float(other.text().strip('% '))
        except ValueError:
            return super().__lt__(other)


# ════════════════════════════════════════════════════════════════════
#  시각화 생성 Worker (백그라운드 스레드)
# ════════════════════════════════════════════════════════════════════

class VisualizationWorker(QThread):
    finished = pyqtSignal(str)   # 완료 → PNG 절대경로
    error    = pyqtSignal(str)   # 오류 → 메시지

    def __init__(self, model_name: str, rank: int):
        """rank: visualize.py 메뉴에서 사용하는 1-based 번호."""
        super().__init__()
        self._model_name = model_name
        self._rank       = rank

    def run(self):
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / 'results' / 'visualize.py')],
                input=f'2\n{self._rank}\n',
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            # 출력에서 저장 경로 파싱
            for line in proc.stdout.split('\n'):
                if '저장 완료:' in line:
                    png_path = line.split('저장 완료:')[1].strip()
                    self.finished.emit(png_path)
                    return
            # 폴백: results/ 에서 직접 탐색
            p = find_existing_png(self._model_name)
            if p:
                self.finished.emit(str(p))
                return
            self.error.emit(proc.stderr or proc.stdout or '저장 경로를 찾지 못했습니다.')
        except Exception as exc:
            self.error.emit(str(exc))


# ════════════════════════════════════════════════════════════════════
#  메인 윈도우
# ════════════════════════════════════════════════════════════════════

_TABLE_COLS = [
    '#', '모델명', 'Val Acc (%)', 'Val Loss',
    '레이어', '특징 수', 'Dropout', 'Batch', 'LR', '에폭', '날짜',
]
# UserRole 에 저장할 내용: all_models 내 0-based 인덱스
_RANK_ROLE = Qt.ItemDataRole.UserRole


class ModelExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('iSENSOR MLP Model Explorer')
        self.resize(1700, 960)

        self.all_models      = load_all_models()
        self.filtered_models: list[dict] = []
        self._filter_checks: dict[tuple, QCheckBox] = {}

        self._build_ui()
        self._populate_filters()
        self._apply_filters()   # 초기 테이블 채우기

    # ─────────────────────────────────────────────────────────────────
    #  UI 구성
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ── 왼쪽: 필터 패널 ──────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(200)
        left.setMaximumWidth(250)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 6, 6)
        ll.setSpacing(4)

        hdr = QLabel('🔍  필터')
        hdr.setFont(QFont(_FONT_KO, 11, QFont.Weight.Bold))
        ll.addWidget(hdr)

        fscroll = QScrollArea()
        fscroll.setWidgetResizable(True)
        fscroll.setFrameShape(QFrame.Shape.NoFrame)
        self._filter_widget = QWidget()
        self._filter_layout = QVBoxLayout(self._filter_widget)
        self._filter_layout.setSpacing(6)
        self._filter_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        fscroll.setWidget(self._filter_widget)
        ll.addWidget(fscroll, 1)

        sel_row = QHBoxLayout()
        sel_row.setSpacing(4)
        all_btn = QPushButton('모두 선택')
        all_btn.clicked.connect(self._select_all_filters)
        none_btn = QPushButton('모두 해제')
        none_btn.clicked.connect(self._deselect_all_filters)
        sel_row.addWidget(all_btn)
        sel_row.addWidget(none_btn)
        ll.addLayout(sel_row)

        reset_btn = QPushButton('필터 초기화')
        reset_btn.clicked.connect(self._reset_filters)
        ll.addWidget(reset_btn)

        splitter.addWidget(left)

        # ── 가운데: 모델 테이블 ───────────────────────────────────────
        center = QWidget()
        center.setMinimumWidth(380)
        cl = QVBoxLayout(center)
        cl.setContentsMargins(6, 6, 6, 6)
        cl.setSpacing(4)

        self.count_label = QLabel()
        self.count_label.setFont(QFont(_FONT_KO, 9))
        cl.addWidget(self.count_label)

        self.table = QTableWidget()
        self.table.setColumnCount(len(_TABLE_COLS))
        self.table.setHorizontalHeaderLabels(_TABLE_COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setFont(QFont(_FONT_KO, 9))
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)   # 모델명 열 stretch
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        cl.addWidget(self.table, 1)

        splitter.addWidget(center)

        # ── 오른쪽: 탭 ────────────────────────────────────────────────
        self._tabs = QTabWidget()

        # ·· 탭 1: 비교 보기 ··
        compare = QWidget()
        coml = QVBoxLayout(compare)
        coml.setContentsMargins(6, 6, 6, 6)
        coml.setSpacing(6)

        hint = QLabel('테이블에서 모델을 선택합니다. 여러 모델(Ctrl+클릭 또는 Shift+클릭)을 선택하면 지표를 비교합니다.')
        hint.setFont(QFont(_FONT_KO, 9))
        hint.setWordWrap(True)
        coml.addWidget(hint)

        self.compare_table = QTableWidget()
        self.compare_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.compare_table.setAlternatingRowColors(True)
        self.compare_table.setFont(QFont(_FONT_KO, 9))
        coml.addWidget(self.compare_table, 1)

        self._tabs.addTab(compare, '📈  비교 보기')

        # ·· 탭 2: 곡선 비교 ··
        curve = QWidget()
        curl  = QVBoxLayout(curve)
        curl.setContentsMargins(4, 4, 4, 4)
        curl.setSpacing(2)

        curve_hint = QLabel('모델을 선택하면 학습 곡선을 표시합니다. Ctrl+클릭으로 여러 모델을 선택하면 곡선을 겹쳐서 비교합니다.')
        curve_hint.setFont(QFont(_FONT_KO, 9))
        curl.addWidget(curve_hint)

        self._curve_fig    = Figure(figsize=(14, 7))
        self._curve_canvas = FigureCanvasQTAgg(self._curve_fig)
        self._curve_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        curl.addWidget(self._curve_canvas, 1)

        self._tabs.addTab(curve, '📉  곡선 비교')

        splitter.addWidget(self._tabs)
        splitter.setSizes([220, 440, 1040])

        # 상태바
        self.setStatusBar(QStatusBar())

    # ─────────────────────────────────────────────────────────────────
    #  필터 구성
    # ─────────────────────────────────────────────────────────────────

    # 필터 항목 정의: (그룹 제목, param key, display 값 추출 함수)
    _PARAM_DEFS = [
        ('레이어 구조', 'layers',
         lambda m: m.get('layers', '-')),
        ('특징 수',     'features',
         lambda m: f"F{m.get('features','-')}" + (' [PC]' if m.get('is_pc') else '')),
        ('드롭아웃',   'dropout',
         lambda m: str(m.get('dropout', '-'))),
        ('배치 크기',  'batch',
         lambda m: str(m.get('batch', '-'))),
        ('초기 LR',    'lr',
         lambda m: m.get('lr', '-')),
    ]

    def _populate_filters(self):
        for group_label, param, get_disp in self._PARAM_DEFS:
            unique_vals = sorted({get_disp(m) for m in self.all_models})
            if not unique_vals:
                continue

            group = QGroupBox(group_label)
            group.setFont(QFont(_FONT_KO, 9))
            g_layout = QVBoxLayout(group)
            g_layout.setSpacing(2)
            g_layout.setContentsMargins(6, 4, 6, 6)

            for val in unique_vals:
                cb = QCheckBox(val)
                cb.setChecked(False)
                cb.stateChanged.connect(self._apply_filters)
                g_layout.addWidget(cb)
                self._filter_checks[(param, val)] = cb

            self._filter_layout.addWidget(group)

    def _select_all_filters(self):
        for cb in self._filter_checks.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self._apply_filters()

    def _deselect_all_filters(self):
        for cb in self._filter_checks.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._apply_filters()

    def _reset_filters(self):
        self._deselect_all_filters()

    def _apply_filters(self):
        # param 별 허용 집합 수집
        allowed: dict[str, set] = {}
        for (param, val), cb in self._filter_checks.items():
            if cb.isChecked():
                allowed.setdefault(param, set()).add(val)

        result = []
        for mdl in self.all_models:
            ok = True
            for _, param, get_disp in self._PARAM_DEFS:
                if param in allowed and get_disp(mdl) not in allowed[param]:
                    ok = False
                    break
            if ok:
                result.append(mdl)

        self.filtered_models = result
        self._refresh_table()

    # ─────────────────────────────────────────────────────────────────
    #  테이블 갱신
    # ─────────────────────────────────────────────────────────────────

    def _refresh_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for mdl in self.filtered_models:
            rank = self.all_models.index(mdl)   # 0-based (visualize.py rank = rank+1)
            row  = self.table.rowCount()
            self.table.insertRow(row)

            acc_val  = mdl.get('best_val_acc')
            loss_val = mdl.get('best_val_loss')
            feat_str = f"F{mdl.get('features','-')}" + (' [PC]' if mdl.get('is_pc') else '')

            cells: list[tuple[str, bool]] = [
                (str(rank + 1),                                                   True),   # #
                (mdl['name'],                                                     False),  # 모델명
                (f"{acc_val:.1f}" if isinstance(acc_val, float) else '-',        True),   # Val Acc
                (f"{loss_val:.5f}" if isinstance(loss_val, float) else '-',      True),   # Val Loss
                (mdl.get('layers', '-'),                                          False),  # 레이어
                (feat_str,                                                        False),  # 특징 수
                (str(mdl.get('dropout', '-')),                                    True),   # Dropout
                (str(mdl.get('batch', '-')),                                      True),   # Batch
                (mdl.get('lr', '-'),                                              False),  # LR
                (str(mdl.get('epochs', '-')),                                     True),   # 에폭
                (mdl.get('datetime', '-'),                                        False),  # 날짜
            ]

            for col, (text, numeric) in enumerate(cells):
                item = _NumItem(text) if numeric else QTableWidgetItem(text)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                    if col != 1
                    else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                # Val Acc 색상 강조
                if col == 2 and isinstance(acc_val, float):
                    if acc_val >= 90:
                        item.setForeground(QColor('#27AE60'))
                    elif acc_val >= 80:
                        item.setForeground(QColor('#2980B9'))
                    elif acc_val < 70:
                        item.setForeground(QColor('#E74C3C'))
                # rank 를 UserRole 에 저장 (0-based)
                if col == 0:
                    item.setData(_RANK_ROLE, rank)
                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)
        self.count_label.setText(
            f'표시: {len(self.filtered_models)}개  /  전체: {len(self.all_models)}개'
        )
        # 내용에 맞게 열 너비 조정 (모델명 열 제외)
        for col in [0, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
            self.table.resizeColumnToContents(col)

    # ─────────────────────────────────────────────────────────────────
    #  선택 이벤트
    # ─────────────────────────────────────────────────────────────────

    def _selected_models(self) -> list[dict]:
        """현재 선택된 행에 대응하는 모델 리스트 반환."""
        selected = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item is not None:
                rank = item.data(_RANK_ROLE)
                if isinstance(rank, int) and 0 <= rank < len(self.all_models):
                    selected.append(self.all_models[rank])
        return selected

    def _on_selection_changed(self):
        models = self._selected_models()
        self._update_compare_table(models)
        self._update_curve_compare(models)

    # ─────────────────────────────────────────────────────────────────
    #  비교 테이블
    # ─────────────────────────────────────────────────────────────────

    # (레이블, getter, 툴팁) — 툴팁: 정의 · 예시 · 적정 범위
    _COMPARE_METRICS: list[tuple[str, callable, str]] = [
        ('Val Acc (%)',
         lambda m: f"{m['best_val_acc']:.2f}"   if isinstance(m.get('best_val_acc'), float)  else '-',
         "검증 정확도 최고값\n"
         "공식: max(val_acc) × 100\n"
         "예시: 88.50 %\n"
         "기준: ↑ 높을수록 좋음\n"
         "적정: 85 % 이상 목표"),
        ('Val Loss',
         lambda m: f"{m['best_val_loss']:.5f}"  if isinstance(m.get('best_val_loss'), float) else '-',
         "검증 손실 최솟값 (CrossEntropy)\n"
         "공식: min(val_loss)\n"
         "예시: 0.35120\n"
         "기준: ↓ 낮을수록 좋음\n"
         "적정: 0.4 미만"),
        ('레이어',
         lambda m: m.get('layers', '-'),
         "은닉층 구조 (뉴런 수)\n"
         "예시: 128-64-32\n"
         "참고: 입력 14~21개 기준\n"
         "  128-64-32 — 균형 잡힌 기본 구조\n"
         "  64-32      — 경량, 과적합 위험 낮음\n"
         "  256-128-64-32 — 고성능/과적합 위험 높음"),
        ('특징 수',
         lambda m: f"F{m.get('features','-')}" + (' [PC]' if m.get('is_pc') else ''),
         "모델 입력 특징 수\n"
         "예시: F14, F21 [PC]\n"
         "[PC] = 원시 특징 대신 PCA 주성분 사용"),
        ('Dropout',
         lambda m: str(m.get('dropout', '-')),
         "드롭아웃 비율\n"
         "예시: 0.2 (= 20 % 뉴런 무작위 비활성화)\n"
         "기준: 과적합 심할수록 높임\n"
         "적정: 0.1 ~ 0.4\n"
         "  0.0 — 드롭아웃 없음 (소규모 모델에서만)\n"
         "  0.2 — 기본값, 현재 데이터셋 최적\n"
         "  0.4 — 강한 정규화, 학습 속도 저하"),
        ('Batch',
         lambda m: str(m.get('batch', '-')),
         "미니배치 크기\n"
         "예시: 128\n"
         "기준: 배치 ↑ → 안정적이지만 일반화 약화\n"
         "적정: 64 ~ 256\n"
         "  64  — 노이즈 많지만 일반화 유리\n"
         "  128 — 기본값, 속도·안정성 균형\n"
         "  256 — 빠르지만 과적합 위험"),
        ('LR',
         lambda m: m.get('lr', '-'),
         "초기 학습률 (Learning Rate)\n"
         "예시: 1e-3\n"
         "기준: 클수록 빠른 수렴, 작을수록 안정\n"
         "적정: 5e-4 ~ 2e-3\n"
         "  2e-3 — 빠른 초기 수렴, 발산 주의\n"
         "  1e-3 — 기본값\n"
         "  1e-4 — 미세 조정 (fine-tuning) 용"),
        ('LRF',
         lambda m: str(m.get('lrf', '-')),
         "LR 스케줄러 감소 인수 (ReduceLROnPlateau factor)\n"
         "공식: 새 LR = 현재 LR × (LRF / 10)\n"
         "예시: LRF=9 → factor=0.9 (10 % 감소)\n"
         "적정: 7 ~ 9 (factor 0.7~0.9)\n"
         "  5 — 한 번에 50 % 감소, 급격한 변화\n"
         "  9 — 완만한 감소, 안정적"),
        ('LRP',
         lambda m: str(m.get('lrp', '-')),
         "LR 스케줄러 patience (개선 없으면 LR 감소까지 기다릴 에폭 수)\n"
         "예시: LRP=50 → 50에폭 개선 없으면 LR 감소\n"
         "적정: 30 ~ 100\n"
         "  20  — 민감, LR 자주 감소\n"
         "  50  — 기본값\n"
         "  100 — 보수적, 수렴이 느린 모델에 적합"),
        ('에폭',
         lambda m: str(m.get('epochs', '-')),
         "총 학습 에폭 수 (Early Stopping 미적용 시 최대)\n"
         "예시: 1000\n"
         "참고: Early Stopping 적용 시 실제 학습은 조기 종료됨\n"
         "적정: 500 ~ 2000"),
        ('날짜',
         lambda m: m.get('datetime', '-'),
         "학습 완료 시각 (MMDD_HHMMSS)\n"
         "예시: 0508_143022 → 5월 8일 14:30:22"),
        # ── 과적합 지표 ──
        ('Δacc T-V (%)',
         lambda m: f"{m['gap_acc']:+.2f}"    if isinstance(m.get('gap_acc'),     float) else '-',
         "Train/Val 정확도 갭 (과적합 1차 지표)\n"
         "공식: train_acc_last − val_acc_best\n"
         "예시: +6.9 % → Train이 Val보다 6.9 % 높음\n"
         "기준: ↓ 낮을수록 좋음 (0에 가까울수록 일반화 잘 됨)\n"
         "적정: < 3 %     → 정상\n"
         "       3 ~ 8 %  → 경미한 과적합, Dropout 상향 고려\n"
         "       > 8 %    → 명확한 과적합, 구조 축소 또는 데이터 증강 필요"),
        ('Δloss V-T',
         lambda m: f"{m['gap_loss']:+.5f}"   if isinstance(m.get('gap_loss'),    float) else '-',
         "Val/Train 손실 갭 (과적합 2차 지표)\n"
         "공식: val_loss_final − train_loss_last\n"
         "예시: +0.0070 → Val Loss가 Train Loss보다 0.007 높음\n"
         "기준: ↓ 낮을수록 좋음 (양수=과적합, 음수=드문 역전)\n"
         "적정: < 0.01   → 정상\n"
         "       0.01~0.05 → 경미한 과적합\n"
         "       > 0.05    → 심각한 과적합"),
        ('Val 반등',
         lambda m: f"{m['val_rebound']:+.5f}" if isinstance(m.get('val_rebound'), float) else '-',
         "Best 이후 Val Loss 반등량 (학습 과잉 지표)\n"
         "공식: val_loss_final − val_loss_best\n"
         "예시: +0.0037 → 최저점 이후 0.0037 올라온 상태로 학습 종료\n"
         "기준: ↓ 낮을수록 좋음 (0=Early Stopping 완벽 동작)\n"
         "적정: < 0.005  → Early Stopping 잘 동작\n"
         "       0.005~0.02 → 다소 과잉 학습\n"
         "       > 0.02     → patience 값을 줄이거나 es_delta 조정"),
        ('과잉 에폭',
         lambda m: str(m.get('overrun', '-')),
         "Best 이후 불필요하게 돈 에폭 수\n"
         "공식: total_epochs − best_epoch\n"
         "예시: 173 → best 이후 173에폭을 더 돌았음\n"
         "기준: ↓ 낮을수록 좋음\n"
         "적정: < 50    → patience 적절\n"
         "       50~200 → 약간 낭비, patience 줄이기 고려\n"
         "       > 200  → patience 또는 lr_factor 조정 필요"),
    ]

    def _update_compare_table(self, models: list[dict]):
        if len(models) < 1:
            self.compare_table.setRowCount(0)
            self.compare_table.setColumnCount(0)
            return

        n = len(models)
        self.compare_table.setRowCount(len(self._COMPARE_METRICS))
        self.compare_table.setColumnCount(n + 1)

        # 헤더: 지표 | 모델1 | 모델2 | ...
        short_names = []
        for m in models:
            # 날짜 앞까지 표시 (너무 길면 자름)
            n_str = m['name']
            ts_m = re.search(r'_(\d{4}_\d{6})$', n_str)
            short = n_str[:ts_m.start()] if ts_m else n_str
            short_names.append(short[-32:])   # 최대 32자
        self.compare_table.setHorizontalHeaderLabels(['지표'] + short_names)

        # 최고 Val Acc 값 찾기 (녹색 강조용)
        accs = [m.get('best_val_acc') for m in models if isinstance(m.get('best_val_acc'), float)]
        best_acc = max(accs) if accs else None

        # 행별 수치 비교 색상 적용을 위해 값 먼저 수집
        # 수치 비교 가능한 행: Val Acc(높을수록↑), Val Loss(낮을수록↑ = 역방향), Dropout, Batch, LR, LRF, LRP, 에폭
        # "높을수록 좋음" 행과 "낮을수록 좋음" 행을 구분
        _HIGHER_BETTER = {'Val Acc (%)'}
        _LOWER_BETTER  = {'Val Loss', 'Δacc T-V (%)', 'Δloss V-T', 'Val 반등', '과잉 에폭'}
        # 나머지 수치 행은 단순 최대/최소 강조 (방향 없음 → 최대=연두, 최소=연빨)
        _NUMERIC_ROWS  = {'Dropout', 'Batch', 'LR', 'LRF', 'LRP', '에폭'}

        for row, (label, getter, tooltip) in enumerate(self._COMPARE_METRICS):
            lbl_item = QTableWidgetItem(label)
            lbl_item.setToolTip(tooltip)
            self.compare_table.setItem(row, 0, lbl_item)

            vals = [getter(mdl) for mdl in models]

            # 수치 파싱 시도
            numeric_vals: list[float | None] = []
            for v in vals:
                try:
                    numeric_vals.append(float(v))
                except (ValueError, TypeError):
                    numeric_vals.append(None)

            valid_nums = [v for v in numeric_vals if v is not None]
            max_v = max(valid_nums) if len(valid_nums) >= 2 else None
            min_v = min(valid_nums) if len(valid_nums) >= 2 else None

            for col, (mdl, val, num) in enumerate(zip(models, vals, numeric_vals), 1):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if num is not None and max_v is not None and max_v != min_v:
                    if label in _HIGHER_BETTER:
                        if num == max_v:
                            item.setForeground(QColor('#5A9E6F'))   # 연두
                        elif num == min_v:
                            item.setForeground(QColor('#C0614A'))   # 연빨
                    elif label in _LOWER_BETTER:
                        if num == min_v:
                            item.setForeground(QColor('#5A9E6F'))   # 낮을수록 좋음 → 최솟값 연두
                        elif num == max_v:
                            item.setForeground(QColor('#C0614A'))   # 최댓값 연빨
                    elif label in _NUMERIC_ROWS:
                        if num == max_v:
                            item.setForeground(QColor('#5A9E6F'))
                        elif num == min_v:
                            item.setForeground(QColor('#C0614A'))

                self.compare_table.setItem(row, col, item)

        self.compare_table.resizeColumnsToContents()

    # ─────────────────────────────────────────────────────────────────
    #  곡선 비교 (오버레이 그래프)
    # ─────────────────────────────────────────────────────────────────

    _CURVE_COLORS = [
        '#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6',
        '#1ABC9C', '#E67E22', '#34495E', '#E91E63', '#00BCD4',
    ]

    def _update_curve_compare(self, models: list[dict]):
        self._curve_fig.clear()
        self._curve_fig.patch.set_facecolor('#F8F9FA')

        if len(models) < 1:
            ax = self._curve_fig.add_subplot(111)
            ax.text(0.5, 0.5, '모델을 선택하세요',
                    ha='center', va='center', fontsize=13, color='#999',
                    transform=ax.transAxes)
            ax.set_axis_off()
            self._curve_canvas.draw()
            return

        # 히스토리 로드
        loaded: list[tuple[dict, str, str]] = []   # (history, label, color)
        for i, mdl in enumerate(models):
            h = _load_history(mdl['name'])
            if not h:
                continue
            feat_str = f"F{mdl.get('features','-')}" + ('[PC]' if mdl.get('is_pc') else '')
            lbl = (f"L{mdl.get('layers','-')} {feat_str} "
                   f"D{mdl.get('dropout','-')} b{mdl.get('batch','-')} "
                   f"lr{mdl.get('lr','-')} ep{mdl.get('epochs','-')}")
            loaded.append((h, lbl, self._CURVE_COLORS[i % len(self._CURVE_COLORS)]))

        if not loaded:
            self._curve_canvas.draw()
            return

        # 서브플롯 구성: 2×2
        gs = self._curve_fig.add_gridspec(
            2, 2, hspace=0.42, wspace=0.32,
            left=0.06, right=0.98, top=0.93, bottom=0.08
        )
        ax_acc  = self._curve_fig.add_subplot(gs[0, 0])
        ax_loss = self._curve_fig.add_subplot(gs[0, 1])
        ax_lr   = self._curve_fig.add_subplot(gs[1, 0])
        # 下우 패널(우하): LR 감소 효과 비교 — 상/하 2서브패널
        _lr_eff_inner = _GSFS(2, 1, subplot_spec=gs[1, 1], hspace=0.55)
        ax_eff_acc  = self._curve_fig.add_subplot(_lr_eff_inner[0])
        ax_eff_loss = self._curve_fig.add_subplot(_lr_eff_inner[1])

        for h, lbl, c in loaded:
            n_ep   = len(h.get('val_acc', h.get('val_loss', [])))
            epochs = list(range(1, n_ep + 1))

            if h.get('val_acc'):
                ax_acc.plot(epochs[:len(h['val_acc'])],
                            [v * 100 for v in h['val_acc']],
                            color=c, linewidth=1.4, label=lbl, alpha=0.85)
            if h.get('train_acc'):
                ax_acc.plot(epochs[:len(h['train_acc'])],
                            [v * 100 for v in h['train_acc']],
                            color=c, linewidth=0.9, linestyle=':', alpha=0.45)

            if h.get('val_loss'):
                ax_loss.plot(epochs[:len(h['val_loss'])],
                             h['val_loss'],
                             color=c, linewidth=1.4, label=lbl, alpha=0.85)
            if h.get('train_loss'):
                ax_loss.plot(epochs[:len(h['train_loss'])],
                             h['train_loss'],
                             color=c, linewidth=0.9, linestyle=':', alpha=0.45)

            if h.get('lr'):
                lr_data = h['lr']
                ax_lr.plot(epochs[:len(lr_data)], lr_data,
                           color=c, linewidth=1.4, label=lbl, alpha=0.85)

            # LR 감소 시점 수직선 — Acc / Loss 패널에 모델 색상 점선으로 표시
            if h.get('lr'):
                _ep_base = h.get('epochs', epochs)
                _lr_list = h['lr']
                _prev    = _lr_list[0]
                _first   = True
                for _ep, _lr in zip(_ep_base[:len(_lr_list)], _lr_list):
                    if _lr < _prev - 1e-12:
                        _kw = dict(color=c, linestyle='--', linewidth=0.9,
                                   alpha=0.45, zorder=1)
                        if _first:
                            ax_acc.axvline(_ep, label=f'LR↓ {lbl[:20]}', **_kw)
                            _first = False
                        else:
                            ax_acc.axvline(_ep, **_kw)
                        ax_loss.axvline(_ep, **_kw)
                    _prev = _lr

        # ── LR 감소 효과 계산 및 오버레이 ───────────────────────────
        _N = 30   # 감소 전후 평균 대상 에폭
        has_effect = False
        for h, lbl, c in loaded:
            lr_data  = h.get('lr', [])
            _val_acc  = [v * 100 for v in h.get('val_acc', [])]
            _val_loss = h.get('val_loss', [])
            _ep_list  = h.get('epochs', list(range(1, len(_val_acc) + 1)))

            if not lr_data or len(lr_data) != len(_ep_list):
                continue

            drop_idx = []
            prev = lr_data[0]
            for i, lr in enumerate(lr_data):
                if lr < prev - 1e-12:
                    drop_idx.append(i)
                prev = lr
            if not drop_idx:
                continue

            boundaries = [0] + drop_idx + [len(_ep_list)]
            stages = list(zip(boundaries[:-1], boundaries[1:]))

            s_nums, d_acc_vals, d_loss_vals = [], [], []
            for k, (s, e) in enumerate(stages):
                if k == 0:   # L1 제외
                    continue
                seg_a = _val_acc[s:e]
                seg_l = _val_loss[s:e] if _val_loss else []
                if len(seg_a) < 2:
                    continue
                n_use = min(_N, len(seg_a) // 2)
                d_a = np.mean(seg_a[-n_use:]) - np.mean(seg_a[:n_use])
                d_l = (np.mean(seg_l[-n_use:]) - np.mean(seg_l[:n_use])
                       if len(seg_l) == (e - s) else 0.0)
                s_nums.append(k + 1)
                d_acc_vals.append(d_a)
                d_loss_vals.append(d_l)

            if not s_nums:
                continue
            has_effect = True
            ax_eff_acc.plot(s_nums, d_acc_vals, 'o-',
                            color=c, linewidth=1.5, markersize=4,
                            label=lbl, alpha=0.85)
            ax_eff_loss.plot(s_nums, d_loss_vals, 'o-',
                             color=c, linewidth=1.5, markersize=4,
                             label=lbl, alpha=0.85)

        _lkw = dict(fontsize=6, framealpha=0.7,
                    ncol=1 if len(loaded) <= 4 else 2)
        _log_fmt = matplotlib.ticker.LogFormatterSciNotation(labelOnlyBase=False)

        ax_acc.set_title('Accuracy  (실선: Val, 점선: Train,  -- : LR↓)', fontsize=9)
        ax_acc.set_xlabel('Epoch', fontsize=8); ax_acc.set_ylabel('%', fontsize=8)
        ax_acc.grid(True, alpha=0.25)
        # 범례: 곡선 항목만 (LR↓ 수직선 항목 제외)
        _handles, _labels = ax_acc.get_legend_handles_labels()
        _curve_h = [(h, l) for h, l in zip(_handles, _labels) if not l.startswith('LR↓')]
        if _curve_h:
            ax_acc.legend(*zip(*_curve_h), **_lkw, loc='lower right')

        ax_loss.set_title('Loss  (실선: Val, 점선: Train,  -- : LR↓)', fontsize=9)
        ax_loss.set_xlabel('Epoch', fontsize=8)
        ax_loss.grid(True, alpha=0.25)
        _handles, _labels = ax_loss.get_legend_handles_labels()
        _curve_h = [(h, l) for h, l in zip(_handles, _labels) if not l.startswith('LR↓')]
        if _curve_h:
            ax_loss.legend(*zip(*_curve_h), **_lkw, loc='upper right')

        ax_lr.set_title('학습률 (LR)', fontsize=9)
        ax_lr.set_xlabel('Epoch', fontsize=8)
        ax_lr.set_yscale('log'); ax_lr.set_ylim(bottom=1e-6)
        ax_lr.yaxis.set_major_formatter(_log_fmt)
        ax_lr.grid(True, alpha=0.25)
        ax_lr.legend(**_lkw, loc='lower left')

        ax_eff_acc.set_title(f'LR 감소 효과  (N={30}에폭, L1 제외)', fontsize=9, fontweight='bold')
        ax_eff_acc.axhline(0, color='#999', linewidth=0.8, linestyle='--')
        ax_eff_acc.set_ylabel('Δval_acc (%)', fontsize=8, color='#4C9BE8')
        ax_eff_acc.tick_params(axis='y', colors='#4C9BE8', labelsize=7)
        ax_eff_acc.set_xticks([])
        ax_eff_acc.grid(True, alpha=0.2, axis='y')
        if has_effect:
            ax_eff_acc.legend(**_lkw, loc='best')
        else:
            ax_eff_acc.text(0.5, 0.5, 'LR 스케줄러 없음',
                            ha='center', va='center',
                            transform=ax_eff_acc.transAxes, fontsize=9, color='gray')

        ax_eff_loss.axhline(0, color='#999', linewidth=0.8, linestyle='--')
        ax_eff_loss.set_ylabel('Δval_loss', fontsize=8, color='#8E44AD')
        ax_eff_loss.tick_params(axis='y', colors='#8E44AD', labelsize=7)
        ax_eff_loss.set_xlabel('LR 단계', fontsize=8)
        ax_eff_loss.grid(True, alpha=0.2, axis='y')
        if has_effect:
            ax_eff_loss.legend(**_lkw, loc='best')

        self._curve_canvas.draw()


# ════════════════════════════════════════════════════════════════════
#  진입점
# ════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 한글 폰트 전역 설정
    font = QFont(_FONT_KO, 9)
    app.setFont(font)

    win = ModelExplorer()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
