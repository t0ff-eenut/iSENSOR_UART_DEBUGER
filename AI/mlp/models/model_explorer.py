"""
╔══════════════════════════════════════════════════════════════════╗
║  iSENSOR MLP Model Explorer  —  PyQt6 GUI                       ║
║  실행: python AI/mlp/model_explorer.py                           ║
╚══════════════════════════════════════════════════════════════════╝

[ 기능 ]
  • 필터 패널 — 레이어, 특징수, 드롭아웃, 배치, LR 기준 필터링
  • 모델 테이블 — Val Acc·Loss 기준 정렬, 다중 선택 지원
  • 단일 보기 탭 — 모델 선택 시 기존 PNG 자동 표시 / 재생성 버튼
  • 비교 보기 탭 — Ctrl+클릭으로 여러 모델 선택 → 지표 비교 테이블
"""

import sys
import os
import re
import json
import subprocess
from pathlib import Path

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
        self.worker: VisualizationWorker | None = None
        self._current_pix: QPixmap | None = None
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

        # ·· 탭 1: 단일 보기 ··
        single = QWidget()
        sl = QVBoxLayout(single)
        sl.setContentsMargins(6, 6, 6, 6)
        sl.setSpacing(6)

        self.info_label = QLabel('모델을 선택하세요.')
        self.info_label.setFont(QFont(_FONT_KO, 9))
        self.info_label.setWordWrap(True)
        sl.addWidget(self.info_label)

        btn_row = QHBoxLayout()
        self.gen_btn = QPushButton('📊  시각화 생성 / 새로고침')
        self.gen_btn.setEnabled(False)
        self.gen_btn.clicked.connect(self._start_visualization)
        btn_row.addWidget(self.gen_btn)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(18)
        self.progress.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_row.addWidget(self.progress)
        sl.addLayout(btn_row)

        self.img_scroll = QScrollArea()
        self.img_scroll.setWidgetResizable(False)
        self.img_label = QLabel('이미지 없음')
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setFont(QFont(_FONT_KO, 10))
        self.img_scroll.setWidget(self.img_label)
        sl.addWidget(self.img_scroll, 1)

        self._tabs.addTab(single, '📊  단일 보기')

        # ·· 탭 2: 비교 보기 ··
        compare = QWidget()
        coml = QVBoxLayout(compare)
        coml.setContentsMargins(6, 6, 6, 6)
        coml.setSpacing(6)

        hint = QLabel('테이블에서 여러 모델을 선택(Ctrl+클릭 또는 Shift+클릭)하면 지표를 비교합니다.')
        hint.setFont(QFont(_FONT_KO, 9))
        hint.setWordWrap(True)
        coml.addWidget(hint)

        self.compare_table = QTableWidget()
        self.compare_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.compare_table.setAlternatingRowColors(True)
        self.compare_table.setFont(QFont(_FONT_KO, 9))
        coml.addWidget(self.compare_table, 1)

        self._tabs.addTab(compare, '📈  비교 보기')

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
                cb.setChecked(True)
                cb.stateChanged.connect(self._apply_filters)
                g_layout.addWidget(cb)
                self._filter_checks[(param, val)] = cb

            self._filter_layout.addWidget(group)

    def _reset_filters(self):
        for cb in self._filter_checks.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self._apply_filters()

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
        if not models:
            self.gen_btn.setEnabled(False)
            self.info_label.setText('모델을 선택하세요.')
            self._update_compare_table([])
            return

        if len(models) == 1:
            mdl  = models[0]
            acc  = f"{mdl['best_val_acc']:.1f}%"  if isinstance(mdl.get('best_val_acc'), float)  else '?'
            loss = f"{mdl['best_val_loss']:.5f}"   if isinstance(mdl.get('best_val_loss'), float) else '?'
            self.info_label.setText(
                f"{mdl['name']}\n"
                f"Val Acc: {acc}  |  Val Loss: {loss}  |  "
                f"레이어: {mdl.get('layers','-')}  |  "
                f"Dropout: {mdl.get('dropout','-')}  |  "
                f"Batch: {mdl.get('batch','-')}  |  "
                f"LR: {mdl.get('lr','-')}  |  에폭: {mdl.get('epochs','-')}"
            )
            self.gen_btn.setEnabled(True)
            # 기존 PNG 자동 표시
            existing = find_existing_png(mdl['name'])
            if existing:
                self._show_image(str(existing))
        else:
            self.info_label.setText(f'{len(models)}개 모델 선택됨 → 비교 보기 탭 확인')
            self.gen_btn.setEnabled(False)

        self._update_compare_table(models)
        if len(models) >= 2:
            self._tabs.setCurrentIndex(1)   # 비교 탭 자동 전환

    # ─────────────────────────────────────────────────────────────────
    #  시각화 생성
    # ─────────────────────────────────────────────────────────────────

    def _start_visualization(self):
        models = self._selected_models()
        if not models:
            return
        mdl  = models[0]
        rank = self.all_models.index(mdl) + 1   # 1-based (visualize.py 와 동일)

        self.gen_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.img_label.setText('⏳  시각화 생성 중...')
        self.statusBar().showMessage(f'시각화 생성 중: {mdl["name"]}')

        self.worker = VisualizationWorker(mdl['name'], rank)
        self.worker.finished.connect(self._on_viz_done)
        self.worker.error.connect(self._on_viz_error)
        self.worker.start()

    def _on_viz_done(self, png_path: str):
        self.progress.setVisible(False)
        self.gen_btn.setEnabled(True)
        self._show_image(png_path)
        self.statusBar().showMessage(f'저장 완료: {png_path}', 5000)

    def _on_viz_error(self, msg: str):
        self.progress.setVisible(False)
        self.gen_btn.setEnabled(True)
        self.img_label.setText(f'❌  오류:\n\n{msg}')
        self.statusBar().showMessage('시각화 생성 실패', 5000)

    def _show_image(self, path: str):
        pix = QPixmap(path)
        if pix.isNull():
            self.img_label.setText(f'이미지를 불러올 수 없습니다:\n{path}')
            return
        self._current_pix = pix
        self._scale_and_set_image()

    def _scale_and_set_image(self):
        if self._current_pix is None or self._current_pix.isNull():
            return
        avail_w = max(self.img_scroll.viewport().width() - 4, 400)
        if self._current_pix.width() > avail_w:
            scaled = self._current_pix.scaledToWidth(
                avail_w, Qt.TransformationMode.SmoothTransformation
            )
        else:
            scaled = self._current_pix
        self.img_label.setPixmap(scaled)
        self.img_label.resize(scaled.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scale_and_set_image()

    # ─────────────────────────────────────────────────────────────────
    #  비교 테이블
    # ─────────────────────────────────────────────────────────────────

    _COMPARE_METRICS: list[tuple[str, callable]] = [
        ('Val Acc (%)',  lambda m: f"{m['best_val_acc']:.2f}"   if isinstance(m.get('best_val_acc'), float)  else '-'),
        ('Val Loss',     lambda m: f"{m['best_val_loss']:.5f}"  if isinstance(m.get('best_val_loss'), float) else '-'),
        ('레이어',       lambda m: m.get('layers', '-')),
        ('특징 수',      lambda m: f"F{m.get('features','-')}" + (' [PC]' if m.get('is_pc') else '')),
        ('Dropout',      lambda m: str(m.get('dropout', '-'))),
        ('Batch',        lambda m: str(m.get('batch', '-'))),
        ('LR',           lambda m: m.get('lr', '-')),
        ('LRF',          lambda m: str(m.get('lrf', '-'))),
        ('LRP',          lambda m: str(m.get('lrp', '-'))),
        ('에폭',         lambda m: str(m.get('epochs', '-'))),
        ('날짜',         lambda m: m.get('datetime', '-')),
    ]

    def _update_compare_table(self, models: list[dict]):
        if len(models) < 2:
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

        for row, (label, getter) in enumerate(self._COMPARE_METRICS):
            self.compare_table.setItem(row, 0, QTableWidgetItem(label))
            for col, mdl in enumerate(models, 1):
                val  = getter(mdl)
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # Val Acc 최대값 강조 (연녹색 배경)
                if label == 'Val Acc (%)' and best_acc is not None:
                    if isinstance(mdl.get('best_val_acc'), float) and mdl['best_val_acc'] == best_acc:
                        item.setBackground(QColor('#D5F5E3'))
                self.compare_table.setItem(row, col, item)

        self.compare_table.resizeColumnsToContents()


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
