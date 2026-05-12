# iSENSOR UART 디버거 변경 이력

---

## v1.5.10 — Model Explorer 과적합 지표 추가 및 Train/Val 곡선 비교

**날짜:** 2026-05-12

### 추가

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/models/model_explorer.py` | `_parse_model_folder` — `train_acc_last`, `train_loss_last`, `gap_acc`, `gap_loss`, `val_rebound`, `overrun` 과적합 지표 6개 계산·저장 |
| `AI/mlp/models/model_explorer.py` | 비교 보기 탭 — `Δacc T-V (%)`, `Δloss V-T`, `Val 반등`, `과잉 에폭` 4개 행 추가, 낮을수록 좋음 기준 녹색/빨간색 강조 |
| `AI/mlp/models/model_explorer.py` | 곡선 비교 탭 상단 두 패널 — Train Acc / Train Loss 점선(동일 색, alpha=0.45) 오버레이 추가 |
| `AI/mlp/TUNING_GUIDE.md` | 섹션 9-1 신규 추가 — 과적합 지표 4개 정의/판독 가이드/곡선 비교 해석법 |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/models/model_explorer.py` | Accuracy 패널 타이틀 → `Accuracy (실선: Val, 점선: Train, -- : LR↓)` |
| `AI/mlp/models/model_explorer.py` | Loss 패널 타이틀 → `Loss (실선: Val, 점선: Train, -- : LR↓)` |

---

## v1.5.9 — Model Explorer 곡선/비교 탭 단일 모델 선택 지원 + LR 감소 수직선 표시

**날짜:** 2026-05-12

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/models/model_explorer.py` | 곡선 비교 탭 — 모델 1개 선택 시에도 학습 곡선 표시 (기존: 2개 이상 필수) |
| `AI/mlp/models/model_explorer.py` | 비교 보기 탭 — 모델 1개 선택 시에도 지표 표시 (기존: 2개 이상 필수) |
| `AI/mlp/models/model_explorer.py` | 곡선 비교 탭 Val Accuracy / Val Loss 패널에 LR 감소 시점 수직선 추가 — 모델별 고유 색상 점선(`--`), 패널 타이틀에 `(-- : LR 감소 시점)` 명시, 범례에서 LR↓ 항목 제외 |
| `AI/mlp/models/model_explorer.py` | 힌트 레이블 문구 수정 — 1개 선택도 가능함을 명시 |

---

## v1.5.8 — Model Explorer 필터 UX 개선

**날짜:** 2026-05-12

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/models/model_explorer.py` | 필터 체크박스 기본값 전체 **미체크** 로 변경 (체크 없음 = 필터 없음 = 전체 모델 표시) |
| `AI/mlp/models/model_explorer.py` | `모두 선택` / `모두 해제` 버튼 추가 — 필터 초기화 버튼 위에 나란히 배치 |
| `AI/mlp/models/model_explorer.py` | `필터 초기화` 버튼 동작을 전체 미체크 기준으로 통일 |

---

## v1.5.7 — MLP GPU 상태 표시 추가 및 PyTorch CUDA 환경 안내

**날짜:** 2026-05-12

### 추가

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | MLP Training GroupBox 하단에 `mlp_gpu_status_Label` 추가 — `torch.cuda.is_available()` 결과를 🟢/🔴 색상으로 실시간 표시, 툴팁에 CUDA 빌드 재설치 명령 안내 |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `requirements.txt` | torch 항목에 CPU 전용 빌드 한계 및 GPU(CUDA) 설치 방법 주석 추가 — Python ≤ 3.12 환경에서 `--index-url https://download.pytorch.org/whl/cu124` 사용 안내 |

### 기술 메모

- 현재 가상환경 Python 3.14.3 → PyTorch CUDA 공식 휠 미지원 (최대 3.12)
- GPU 학습 활성화하려면 **Python 3.12** 기반 가상환경 신규 생성 필요
- 시스템 GPU: NVIDIA GeForce GTX 1660 / CUDA 드라이버 13.1 (cu124 빌드 호환)

---

## v1.5.6 — Model Explorer UI 개선 (탭 정리 + LR 감소 효과 비교)

**날짜:** 2026-05-12

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/models/model_explorer.py` | `단일 보기` 탭 제거 — `VisualizationWorker`, `_start_visualization`, `_show_image` 등 관련 코드 일괄 삭제 |
| `AI/mlp/models/model_explorer.py` | 모델 선택 시 탭 자동 전환 제거 — 현재 보고 있는 탭 유지 |
| `AI/mlp/models/model_explorer.py` | 곡선 비교 탭 4번째 패널: `LR 변화율(lr[t]/lr[t-1])` → `LR 감소 효과` 로 교체 — `GridSpecFromSubplotSpec` 2서브패널(상: Δval_acc, 하: Δval_loss), 모델별 선+마커 오버레이, L1 단계 제외 |
| `AI/mlp/models/model_explorer.py` | `numpy` 임포트 추가, `GridSpecFromSubplotSpec` 임포트 추가 |

---

## v1.5.5 — Model Explorer 곡선 비교 탭 추가

**날짜:** 2026-05-12

### 추가

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/models/model_explorer.py` | `📉 곡선 비교` 탭 추가 — matplotlib Qt 임베딩, 2×2 패널 구성(Val Acc / Val Loss / LR(log) / LR변화율(lr[t]/lr[t-1], log)), 선택된 모델 곡선 오버레이, 모델 2개 이상 선택 시 자동 전환 |
| `AI/mlp/models/model_explorer.py` | `_load_history()` 헬퍼 함수 추가 — 모델 폴더에서 `_history.json` 직접 로드 |

---

## v1.5.4 — MLP Model Explorer GUI 추가 및 파일 구조 정리

**날짜:** 2026-05-11

### 추가

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/models/model_explorer.py` | PyQt6 기반 MLP 모델 탐색기 GUI 신규 추가 — 필터 패널(레이어·특징수·Dropout·Batch·LR), 모델 테이블(Val Acc 색상 강조·정렬), 단일 보기 탭(기존 PNG 자동 표시·재생성 버튼), 비교 보기 탭(Ctrl+다중선택 → 지표 비교 테이블) |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/results/visualize.py` | `AI/mlp/` → `AI/mlp/results/` 로 이동 — 출력 PNG 와 동일 폴더 배치, `_HERE`/`SCRIPT_DIR` 분리로 경로 참조 정상 유지 |
| `AI/mlp/models/model_explorer.py` | `AI/mlp/` → `AI/mlp/models/` 로 이동 — `_HERE`/`SCRIPT_DIR` 분리로 `models/`·`results/` 경로 정상 유지 |
| `AI/mlp/results/visualize.py` | `draw_architecture()` — Dropout 값을 state_dict 대신 폴더명 `_D{n}_` 패턴 파싱으로 교체 (`nn.Dropout.p` 는 state_dict 에 저장 안 됨) |
| `AI/mlp/results/visualize.py` | `draw_lr()` — Y축 범위 고정: 하단 `1e-6`(min_lr 수렴점), 상단 `max(lr)×5`(최소 `1e-2`) |

### 삭제

| 파일 | 이유 |
|---|---|
| `AI/mlp/prepare_data.py` | `visualize.py`가 `data_csv/` 직접 로드하므로 불필요 |
| `AI/mlp/compare_models.py` | `model_explorer.py` 비교 탭으로 기능 대체 |

---

## v1.5.3 — MLP 시각화 LR 분석 강화 및 history 구조 개선

**날짜:** 2026-05-11

### 추가

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/visualize.py` | `draw_lr()` 추가 — 에폭별 학습률 독립 그래프 (log 스케일, LR 감소 지점 주황 마커·어노테이션) |
| `AI/mlp/visualize.py` | `draw_lr_effect()` 추가 — LR 단계별 Δval_acc / Δloss 효과 분석 막대 그래프 (N=30 에폭 평균 비교) |
| `AI/mlp/visualize.py` | `draw_learning_curve()` — LR 감소 시점 초록 점선 수직선 추가 (방법 A) |
| `_migrate_lr.py` | 기존 모델 일괄 마이그레이션 스크립트 신규 추가 — `loss→train_loss` 키 리네임 + `.log` 파싱으로 `lr` 키 보완 (31개 JSON 처리) |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/visualize.py` | 레이아웃 **2×4 → 2×5** (`figsize=(32,12)`) — `gs[0,3]` LR 변화, `gs[1,3]` LR 효과 분석, `gs[:,4]` 특징 중요도 |
| `AI/mlp/visualize.py` | `draw_lr_effect()` x축 — 단계 수에 따라 레이블 동적 단축 (≤8: `L{k}\n{lr}`, ≤14: `L{k}` + 막대 하단 세로 LR, ≥15: 홀수만) |
| `AI/mlp/visualize.py` | `draw_lr()` 어노테이션 겹침 방지 — x 간격 기반 2패스 충돌 감지·offset 분산, arrowprops 연결선 추가 |
| `AI/mlp/visualize.py` | `draw_lr_effect()` 2패널 구조로 전환 — Δval_acc(위)·Δval_loss(아래) 분리, `GridSpecFromSubplotSpec` 사용, 각 패널이 y=0 기준선에서 시작 |
| `AI/mlp/visualize.py` | `draw_lr_effect()` L1(초기 단계) 제외 — 압도적 스케일 차이로 나머지 단계가 왜소해지는 문제 해결, 제목에 "L1 제외" 표기 |
| `AI/mlp/TUNING_GUIDE.md` | **§10 LR 감소 효과 그래프 해석** 섹션 추가 — 계산 방식, 막대 색상별 의미, 패널 구조, LRP/LRF 조정 판단표, 조기종료 도입 시기 판단 기준 |
| `AI/mlp/nn_mlp.py` | history 키 `loss` → **`train_loss`** 리네임 (2곳) |
| `AI/mlp/nn_mlp.py` | history에 `lr` 키 추가 — 매 에폭 학습률 기록 (2곳) |
| `AI/mlp/compare_models.py` | `h.get('train_loss', h.get('loss', []))` 폴백 읽기 적용 |

---

## v1.5.2 — MLP 시각화 하드코딩 제거 및 PC 모드 특징 추출 정확도 수정

**날짜:** 2026-05-11

### 수정 (버그픽스)

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/visualize.py` | PC 모드 특징 추출 오류 수정 — `fft_*` 컬럼(하드웨어 FFT) 대신 ADC 컬럼 → numpy FFT 재계산(`extract_pc_features_from_adc_batch`) 사용, 학습 파이프라인과 동일하게 통일 |
| `AI/mlp/visualize.py` | 특징 순서 불일치 수정 — `importance.json features`가 중요도 내림차순이므로 ESP32 모드는 CSV 컬럼 인덱스 기준 오름차순 정렬로 복원 |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/visualize.py` | `draw_architecture()` — `HIDDEN_LAYERS`/`DROPOUT_RATE` 전역 상수 대신 저장된 `.pt` state_dict에서 실제 레이어 크기·드롭아웃 값 동적 추출 |
| `AI/mlp/visualize.py` | `_extract_features()` — PC/ESP32 모드 판별을 폴더명(`_PC_`) 하드코딩에서 `importance.json features`의 `magnitudes_` 포함 여부 기반으로 교체 |
| `AI/mlp/visualize.py` | `_extract_features()` — ESP32 모드 컬럼 목록 `ESP32_FEAT_COLS` 하드코딩 제거, `importance.json features`(대문자) → CSV 컬럼 인덱스 기준 자동 정렬 |
| `AI/mlp/visualize.py` | `ESP32_FEAT_COLS` 상수 제거 |

---

## v1.5.1 — MLP 시각화 고도화 (LR 보조축, 전처리 내장, 특징 중요도)

**날짜:** 2026-05-11

### 추가

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/visualize.py` | `_load_raw_dataset()` 내장 — `data_csv/svm_data*.csv` 직접 로드 → `prepare_data.py` 불필요 |
| `AI/mlp/visualize.py` | `draw_importance()` 추가 — 특징 중요도 가로 막대 차트 (≥10%: 주황, 5~10%: 파랑, <5%: 연청) |
| `AI/mlp/visualize.py` | `ModelInfo` namedtuple에 `importance` 필드 추가 |
| `AI/mlp/nn_mlp.py` | history dict에 `'lr'` 키 추가 — 매 에폭 학습률 기록 |
| `requirements.txt` | `pandas>=1.5.0` 추가 |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/visualize.py` | 레이아웃 2×3 → **2×4** (`figsize=(26,12)`) — 특징 중요도 우측 열 2행 span |
| `AI/mlp/visualize.py` | `draw_learning_curve()` — 손실 그래프에 LR 보조축(오른쪽 y축, 로그 스케일, 초록 점선) 추가 |
| `AI/mlp/visualize.py` | `draw_learning_curve()` — `val_loss` 곡선 추가, 검증 손실 최솟값 마커, 과적합 구역 음영 |
| `AI/mlp/visualize.py` | `draw_pca()`, `draw_confidence()`, `draw_confusion_matrix()` — `raw_data` 파라미터 추가 |
| `AI/mlp/visualize.py` | `draw_pca()`, `draw_confidence()`, `draw_confusion_matrix()` — scaler feature 수 불일치 시 graceful 처리 (크래시 없이 안내 메시지 표시) |
| `AI/mlp/visualize.py` | `_list_model_versions()` — 정렬 기준을 알파벳 → **폴더명 끝 `MMDD_HHMMSS` 타임스탬프** 기준으로 수정 |
| `AI/mlp/visualize.py` | 저장 파일명 — `모델폴더명_acc{val_acc:.1f}.png` (타임스탬프 없음) |
| `AI/mlp/visualize.py` | `plt.show()` 제거 — 연속 처리 시 블로킹 방지 |

---

## v1.5.0 — MLP 파일 명명 규칙 통일 및 시각화 모델 선택 기능

**날짜:** 2026-05-11

### 추가

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | `_count_csv_rows()` 헬퍼 메서드 추가 — CSV 파일(또는 폴더)의 데이터 행 수를 헤더 제외 카운트 |
| `AI/mlp/nn_mlp.py` | `_compute_stem()` 에 `n_samples` 파라미터 추가 — 학습 데이터 샘플 수를 파일명에 포함 (`MLP_{n_samples}_...`) |
| `AI/mlp/nn_mlp.py` | `_compute_stem()` 파일명 키 대소문자 규칙 적용 — `F`, `D`, `LR`, `LRF`, `LRP` 대문자 / `b`, `ep` 소문자 |
| `AI/mlp/_rename_mlp_files.py` | 기존 파일 일괄 이름 변경 유틸리티 신규 추가 — 구 명명 규칙(3가지 패턴) → 신 명명 규칙으로 30개 로그 + 31개 모델 폴더 rename (`DRY_RUN=True` 기본) |
| `AI/mlp/visualize.py` | `ModelInfo` namedtuple 추가 — `(name, pt, scaler, history)` 경로 묶음 |
| `AI/mlp/visualize.py` | `_list_model_versions()` 추가 — `models/MLP_*` 폴더 목록 내림차순 반환 |
| `AI/mlp/visualize.py` | `_pick_model_paths()` 추가 — 폴더명으로 `ModelInfo` 경로 구성 |
| `AI/mlp/visualize.py` | `_select_models()` 추가 — 콘솔 메뉴: ① 최신 모델 / ② 특정 모델 선택 / ③ 모든 모델 전체 저장 |
| `AI/mlp/visualize.py` | `_render_one(model_info)` 추가 — 단일 모델 대시보드 생성·저장 함수 (루프 지원) |
| `requirements.txt` | `matplotlib>=3.7.0` 추가 |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | `train()` — `_count_csv_rows()` 호출 후 `n_samples`를 `_compute_stem()`에 전달 |
| `AI/mlp/visualize.py` | 한글 폰트 설정을 OS 자동 감지 방식으로 변경 — Windows: `Malgun Gothic`, macOS: `AppleGothic`, Linux: `NanumGothic` |
| `AI/mlp/visualize.py` | `_resolve_model_paths()` 제거 → `_select_models()` 메뉴 방식으로 교체 |
| `AI/mlp/visualize.py` | `draw_learning_curve()` — `history_path` 파라미터 추가 (미지정 시 기본 경로 폴백) |
| `AI/mlp/visualize.py` | `draw_confidence()` — `model_info` 파라미터 추가 |
| `AI/mlp/visualize.py` | `draw_confusion_matrix()` — `model_info` 파라미터 추가 |
| `AI/mlp/visualize.py` | `main()` — `_render_one()` + 루프 구조로 재구성, 저장 파일명을 모델 폴더명 기반으로 변경 |

---

## v1.4.1 — MLP 과적합 진단 및 로그 개선

**날짜:** 2026-05-10

### 수정

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | `_train_impl()` 에폭 로그 출력에 **검증 손실(`검증손실: X.XXXX`)** 컬럼 추가 — 기존에는 val_loss가 history에만 기록되고 로그에 미출력 |
| `AI/mlp/nn_mlp.py` | `scheduler.step(avg_loss)` → **`scheduler.step(val_loss)`** 로 수정 — `ReduceLROnPlateau`의 감시 대상을 train loss에서 val loss로 교정 (과적합 중 LR 지속 문제 수정) |

### 추가

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/TUNING_GUIDE.md` | **섹션 9. 과적합 진단 및 대응** 추가 — L256-128-64-32 실험 결과 기반 증상·원인·해결방법·버그 수정 내용 포함 |

### 배경

`L256-128-64-32` 구조 학습 시 Val Loss가 지속 상승하는 과적합 현상 발견.  
원인 조사 과정에서 두 가지 버그(`val_loss` 로그 누락, `scheduler.step` 대상 오류) 확인 및 수정.

---

## v1.4.0 — MLP 학습 제어 기능 개선

**날짜:** 2026-05-10

### 추가

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | MLP 학습 패널에 **⏹ 중단 버튼** 추가 — 학습 중일 때만 활성화, 클릭 시 다음 에폭 완료 후 즉시 중단 |
| `debugger_start.py` | `event_mlp_stop()` — 중단 버튼 이벤트 핸들러 추가 |
| `debugger_start.py` | `MlpTrainWorker.stop()` — 중단 플래그 설정 메서드 추가 |
| `debugger_start.py` | `MlpTrainWorker._stop_requested` — 중단 플래그 필드 추가 |
| `AI/mlp/nn_mlp.py` | 학습 루프 내 `progress_callback` 반환값 체크 — `False` 반환 시 루프 `break` (중단 메시지 출력 포함) |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | `mlp_train_PushButton` 레이아웃을 `(16, 0, 1, 2)` → `(16, 0, 1, 1)` 로 축소 (중단 버튼 공간 확보) |
| `debugger_start.py` | `event_mlp_train()` — 학습 시작 시 중단 버튼 활성화 |
| `debugger_start.py` | `_on_mlp_train_finished()` — 중단 버튼 비활성화, 중단 여부에 따라 상태 메시지 분기 (`학습 완료` / `학습 중단`) |
| `debugger_start.py` | `MlpTrainWorker._cb()` — 중단 플래그 확인 후 `False` 반환하도록 변경 |
| `debugger_start.py` | `mlp_epochs_SpinBox.setRange(10, 2000)` → `setRange(10, 100000)` 로 상한 확장 |
| `AI/mlp/TUNING_GUIDE.md` | **섹션 8. Epoch 수 설정 기준** 추가 — 분야별 범위, 이 프로젝트 실험 결과, 판단 기준, UI 상한 내용 포함 |

---

## v1.3.0 — MLP UI 편의 기능 개선

**날짜:** 2026-05-09

### 추가

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | MLP Layer 콤보박스에 **`256-128-64-32`** (4층 구조) 항목 추가 — 목록 맨 위에 배치 |
| `debugger_start.py` | MLP 학습 곡선 탭에 **자동 스케일 토글 버튼** 추가 (`🔒 자동 스케일: ON` / `🔓 자동 스케일: OFF`) |
| `debugger_start.py` | `_on_mlp_curve_user_zoomed()` — 사용자가 스크롤/드래그 시 자동 스케일 자동 OFF 전환 |
| `debugger_start.py` | `_on_mlp_autoscale_toggled()` — 버튼 클릭으로 자동 스케일 수동 ON/OFF 전환 |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | Dropout 입력을 **ComboBox** (0.0~0.5 고정 목록) → **`QDoubleSpinBox`** (0.00~1.00, 0.05 단위, 직접 입력 가능)으로 교체 |
| `debugger_start.py` | `create_mlp_train_curve_tab()` — PlotWidget을 `self._mlp_curve_pw`로 저장, 탭 콘텐츠를 컨테이너 위젯(`QVBoxLayout`)으로 감싸 버튼+그래프 구조로 변경 |
| `debugger_start.py` | `_on_mlp_epoch_progress()` — 자동 스케일 ON 상태일 때만 `enableAutoRange()` 호출 |
| `debugger_start.py` | `event_mlp_load_model()` — 모델 로드 시 자동 스케일 ON으로 초기화하여 전체 학습 곡선 표시 |
| `debugger_start.py` | `_save_settings()` — `dropout` 저장 방식을 `currentText()` → `str(value())` 로 변경 |
| `debugger_start.py` | `_load_settings()` — `dropout` 복원 방식을 `_set_combo_text()` → `_set_double_spin()` 으로 변경 |

---

## v1.2.0 — MLP 학습 로그 개선 및 파일 구조 리팩토링

**날짜:** 2026-05-07

### 추가

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | 에폭 로그 출력에 **에폭별 소요 시간** 표시 (`{N}s` 컬럼 추가) |
| `AI/mlp/nn_mlp.py` | 학습 완료 시 **전체 학습 소요 시간** 출력 (`⏱ N분 N초`) |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | `_Tee.write()` — `_f.flush()` 즉시 호출로 **로그 파일 실시간 반영** (학습 중에도 파일 확인 가능) |
| `AI/mlp/nn_mlp.py` | `_compute_stem()` 헬퍼 메서드 신규 추가 — 모델/로그 파일명 stem을 한 곳에서 생성 |
| `AI/mlp/nn_mlp.py` | `train()` — 파라미터 확정 직후 `_compute_stem()` 호출, 로그 파일을 **stem 이름으로 바로 생성** (rename 로직 제거) |
| `AI/mlp/nn_mlp.py` | `_train_impl()` — `model_stem` 파라미터 추가, `_save_model(stem=...)` 으로 전달 |
| `AI/mlp/nn_mlp.py` | `_save_model()` — `stem` 파라미터 추가, 내부 stem 재계산 로직 제거 (stem은 `train()` 시작 시 1회만 생성) |
| `AI/mlp/nn_mlp.py` | `_make_log_path()` 메서드 제거 (불완전한 임시명 방식 폐기) |
| `AI/mlp/nn_mlp.py` | `self._last_model_stem` 및 `finally` 블록 rename 코드 전체 제거 |
| `AI/mlp/nn_mlp.py` | `train_eval()` — 동일한 `_compute_stem()` 방식으로 통일 |

---

## v1.1.0 — MLP 학습 파라미터 GUI 확장 및 파일 구조 개선

**날짜:** 2026-05-07

### 추가

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | MLP 학습 패널에 **LR Scheduler Patience** SpinBox 추가 (row 14, 범위 1~200, 기본값 10) |
| `debugger_start.py` | MLP 학습 패널에 **LR Scheduler Factor** ComboBox 추가 (row 15, 선택지 0.1/0.2/0.3/0.5/0.7, 기본값 0.5) |
| `debugger_start.py` | MLP LR 입력 방식을 고정 목록 → **가수부(1.0~9.9) + 지수부(e-1~e-7) 직접 입력** 방식으로 변경 |
| `AI/mlp/nn_mlp.py` | `train()` / `_train_impl()` 에 `lr_scheduler_patience`, `lr_scheduler_factor` 파라미터 추가 |
| `AI/mlp/nn_mlp.py` | `ReduceLROnPlateau` 호출부를 전역 상수 대신 파라미터 값 사용 |

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | 로그 파일명을 임시 timestamp 명 → **모델 파일 stem과 완전히 동일한 이름**으로 rename (`_last_model_stem` 활용) |
| `AI/mlp/nn_mlp.py` | 버전 모델/스케일러/히스토리/중요도 파일을 `models/` 직접 저장 → **`models/{stem}/` 서브폴더** 구조로 변경 |
| `debugger_start.py` | `_refresh_mlp_model_list()` — 서브폴더 기반 목록 나열로 변경 |
| `debugger_start.py` | `event_mlp_load_model()` — `models/{stem}/{stem}.pt` 경로로 로드 (flat 구조 하위 호환 유지) |
| `debugger_start.py` | `_save_settings()` / `_load_settings()` 에 `lr_patience`, `lr_factor`, `lr_mantissa`, `lr_exp` 항목 추가 |
| `AI/mlp/nn_mlp.py` | `_try_load_model()` — 서브폴더 패턴 + flat 패턴 병행 탐색 (하위 호환) |

---

## v1.0.0 — Dead Code 전면 제거 (코드 정리)

**날짜:** 2026-05-07

### 수정

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | 주석 처리된 죽은 코드(dead code) 전면 제거 — 약 3942줄 → 3711줄 (약 231줄 감소) |
| `debugger_start.py` | `value_init()` 내 미사용 주석 변수 5줄 제거 (`svm_handle.str_svm_csv_path`, `_SVM_HISTORY_MAXLEN` 등) |
| `debugger_start.py` | SVM 그래프 설정 주석 3줄 제거 (`graph_x_range_setting`, `graph_y_range_setting`, `graph_legend_setting`) |
| `debugger_start.py` | ESP32 리셋 버튼 주석 블록 제거 |
| `debugger_start.py` | NVS 설정 읽기/저장 버튼 주석 블록 2세트 + 구분선 제거 |
| `debugger_start.py` | SVM scatter/history/waveform 탭 주석 블록 3개 제거 |
| `debugger_start.py` | SVM CSV 삭제 후 초기화 주석 블록 제거 (scatter/history/waveform 초기화 + TP2 명령) |
| `debugger_start.py` | `update_svm_waveform_overlay()` 전체 주석 메서드 제거 |
| `debugger_start.py` | `_update_svm_history_display()` 전체 주석 메서드 제거 |
| `debugger_start.py` | `send_save_nvs_command()`, `send_reset_command()`, `apply_plot_range()`, `reset_plot_range()` 주석 메서드 제거 |
| `debugger_start.py` | `update_svm_scatter()` 전체 주석 메서드 제거 |
| `debugger_start.py` | `log_TextEdit_print_sensor_data()` 전체 주석 메서드 제거 (55줄) |
| `debugger_start.py` | `event_update_ui()` 하단 구버전 로그 주석 블록 제거 |
| `debugger_start.py` | `update_svm_label_count()` 내 주석 3줄 제거 |
| `debugger_start.py` | `create_mlp_train_curve_tab()` 하단 FFT 관련 잔여 주석 블록 제거 (`_compute_fft`, `_update_fft_plot`) |
| `debugger_start.py` | `buffer_setting()` 내 ESP32 FFT 비활성화 주석 블록 제거 |
| `debugger_start.py` | `update_fft_graph()` 내 raw magnitudes 주석 블록 제거 |
| `debugger_start.py` | `update_svm_graph()` 내 Phase 1+2+3+A 주석 블록 제거 |
| `debugger_start.py` | `_get_last_fft_raw()` 전체 주석 메서드 제거 |
| `debugger_start.py` | `event_svm_save_background()` 내 구버전 주석 3줄 제거 |
| `debugger_start.py` | `event_svm_save_occupancy()` 내 구버전 구현 주석 블록 12줄 제거 |
| `debugger_start.py` | `UartWorker.run()` 내 Windows 폴링 방식 주석 블록 13줄 제거 |
| `debugger_start.py` | `create_fft_plot_tab()` 내 피크 TextItem 주석 블록 2곳 제거 |
| `debugger_start.py` | `create_svm_plot_tab()` 하단 피크 라벨 딕셔너리 주석 블록 2곳 제거 |
| `debugger_start.py` | `connection_GroupBox.setFlat(True)` 단일 주석 줄 제거 |
| `debugger_start.py` | `tp_setting_PushButton.setStyleSheet` 구버전 단일 주석 줄 제거 |
| `debugger_start.py` | FFT 관련 변수 초기화 주석 3줄 제거 (`f_sampling_rate`, `uart_thread` 등) |

---

## v0.9.9 — 학습 비교 지표 확장 및 GUI 설정 유지

**날짜:** 2026-05-07

### 추가

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | 학습 완료 후 추가 비교 지표 계산 및 `train_history.json` 저장: `best_epoch`, `min_val_loss`, `human_recall`(TPR), `human_fnr`(FNR), `bg_tnr`(TNR), `bg_fpr`(FPR), `f1_human` |
| `AI/mlp/nn_mlp.py` | `_save_history()` 비교 출력을 테이블 형식으로 개편 — 지표명/이전값/현재값/변화/방향 5열 |
| `AI/mlp/nn_mlp.py` | 비교 지표에 **사람 오탐률 FNR** (사람→배경 눈침) 및 **배경 정확 탐지율 TNR** 추가 — 사람 TPR·FNR·배경 TNR·FPR 4개 대칭 구조 |
| `debugger_start.py` | `_save_settings()` — 프로그램 종료 시 UI 설정을 `ui_settings.json`으로 저장 |
| `debugger_start.py` | `_load_settings()` — 프로그램 시작 시 `ui_settings.json`에서 UI 설정 복원 (특징 선택, MLP 파라미터 13개 항목) |

### 수정

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | 기존 `_save_history()` 단일 정확도 비교 → 7개 지표 테이블 비교로 교체 |
| `debugger_start.py` | `closeEvent`에 `_save_settings()` 호출 추가 |

---

## v0.9.8 — RobustScaler 선택 기능 및 모델 파일명 개선

**날짜:** 2026-05-07

### 추가

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | `from sklearn.preprocessing import RobustScaler` 추가 |
| `AI/mlp/nn_mlp.py` | `train()` / `_train_impl()`에 `scaler_type: str = None` 파라미터 추가 — `'robust'` 지정 시 RobustScaler(중앙값/IQR), 기본값은 StandardScaler(z-score) |
| `AI/mlp/nn_mlp.py` | `_save_model()` — RobustScaler 선택 시 모델/스케일러 파일명에 `_rb` 태그 삽입 |
| `AI/mlp/nn_mlp.py` | `_make_log_path()` — RobustScaler 선택 시 로그 파일명에 `_rb` 태그 삽입 |
| `AI/mlp/nn_mlp.py` | `_permutation_importance()` 출력에 `_FEAT_KO` 딕셔너리 추가, 각 특징명 옆에 한글명 병기 |
| `debugger_start.py` | MLP 학습 패널에 **스케일러 선택 ComboBox** 추가 (`Standard (z-score)` / `Robust (중앙값/IQR)`) — row 13, 기존 row 13 이하 항목은 +1 이동 |
| `debugger_start.py` | `MlpTrainWorker`에 `scaler_type` 파라미터 추가 및 `train()` 호출 시 전달 |
| `debugger_start.py` | `event_mlp_train()`에서 스케일러 ComboBox 선택값 읽어 Worker에 전달 |

---

## v0.9.7 — CSV 세션 단일화 및 MLP 학습 곡선 Train/Val Loss 분리

**날짜:** 2026-05-07

### 수정

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | 배경/사람 자동 저장 토글 ON 시 매번 새 CSV를 생성하던 동작 제거; 프로그램 시작 시 `__init__`에서 생성한 `collector`를 프로그램 종료까지 재사용 — 토글을 여러 번 껐다 켜도 하나의 CSV 파일에 계속 누적 저장됨 |
| `debugger_start.py` | `MlpTrainWorker.epoch_progress` 시그널에 `val_loss` 추가 (시그니처: `int, int, float, float, float, float`) |
| `debugger_start.py` | `_on_mlp_epoch_progress()` — `val_loss` 파라미터 추가; 진행 바 포맷에 `val_loss` 수치 표시 |
| `debugger_start.py` | MLP 학습 곡선 탭에 **Val Loss (주황색, `#ff9900`)** 곡선 추가; `_mlp_train_val_loss` 버퍼 추가 |
| `debugger_start.py` | 모델 로드(`event_mlp_select`) 시 저장된 `val_loss` 이력을 그래프에 반영 |
| `AI/mlp/nn_mlp.py` | `_evaluate_loss(loader, criterion, device)` 메서드 추가 — DataLoader 기준 평균 val loss 계산 |
| `AI/mlp/nn_mlp.py` | 학습 루프에서 매 에폭 `val_loss` 계산 및 `history['val_loss']` 저장 |
| `AI/mlp/nn_mlp.py` | `progress_callback` 시그니처 변경: `(epoch, total, train_loss, val_loss, train_acc, val_acc)` |

---

## v0.9.6 — ESP32+FFT 확장 모드 및 PC-ADC 재계산 모드 추가

**날짜:** 2026-05-04

### 추가

**원인**
- PC 모드(`feature_mode='pc'`)가 CSV에 미리 저장된 FFT 빈 컬럼을 재사용해 ADC 원본 신호의 위상·스케일 정보 손실
- ESP32 모드의 21개 UART 특징이 저주파 FFT 에너지 분포(빈 1~15)를 포함하지 않아 저속 움직임 판별 정확도 저하
- `_predict()` 가 단일 경로(esp32)만 지원해 모드 전환 시 특징 수 불일치로 스케일러 오류 발생 가능

**수정**

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/pc_feature_extractor.py` | `ADC_START_COL = 21`, `ADC_N_SAMPLES = 256` 상수 추가; 내부 헬퍼 `_extract_features_from_fft_arr()` / `_extract_features_batch()` 로 공통 로직 분리 |
| `AI/mlp/pc_feature_extractor.py` | `extract_pc_features_from_adc(row_full)` / `extract_pc_features_from_adc_batch(X_full)` — CSV ADC 컬럼(21~276) → numpy FFT → 25개 특징 (학습용) |
| `AI/mlp/pc_feature_extractor.py` | `compute_pc_features_realtime(A_adc)` — ADC 배열 직접 입력 → 25개 특징 (실시간 추론용) |
| `AI/svm/svm.py` | `enum_csv_col`에 `FFT_BIN_1 ~ FFT_BIN_15` (index 21~35) 추가; `feature_vector_from_uart_extended(ft, A_fft_mags)` — 21 + 저주파 bins 1~15 = **36차원** 벡터; `I_FEATURES_COUNT_EXTENDED = 36` 상수 추가 |
| `AI/mlp/nn_mlp.py` | `_A_fft_mags_cache` / `_A_adc_cache` 멤버 추가; `mlp()` 에 `A_fft_mags`, `A_adc` 파라미터 추가 |
| `AI/mlp/nn_mlp.py` | `_feat_mode` 프로퍼티 — `scaler.n_features_in_` 로 모드 자동 추론 (21→`esp32`, 36→`esp32_fft`, 25→`pc`) |
| `AI/mlp/nn_mlp.py` | `_predict()` — 모드별 특징 벡터 구성 분기 (`esp32_fft` / `pc` / `esp32`) |
| `AI/mlp/nn_mlp.py` | `_train_impl(feature_mode='esp32_fft')` — CSV `fft_1~15` 컬럼을 UART 21개에 결합해 36개로 학습; `feature_mode='pc'` — ADC 컬럼 → numpy FFT → 25개로 학습 |
| `debugger_start.py` | `mlp_handle.mlp()` 호출에 `A_fft_mags=self.A_fft_magnitudes`, `A_adc=self.A_adc_buffer` 전달 |

**결과**
- PC 모드: ADC 원본 → numpy FFT 직접 계산으로 CSV 저장 FFT 빈 컬럼 불필요, 정보 손실 없음
- ESP32 모드(`esp32_fft`): 저주파 FFT 빈 1~15 추가로 36차원 특징 벡터 구성, 저속 움직임 감지 향상 기대
- 실시간 추론 시 로드된 모델의 `scaler.n_features_in_` 에서 모드 자동 판별 — 수동 설정 불필요

---

## v0.9.4 — PCA 그래프 특징 텍스트 구버전 속성 참조 제거

**날짜:** 2026-05-04

### 버그 수정

| 파일 | 수정 내용 |
|---|---|
| `debugger_start.py` | `update_svm_pca_graph()` — `h.f_peak_freq` 등 `SVM_Module` 구버전 속성 직접 참조 제거; `svm.feature_vector_from_uart(h.ft)`로 특징 벡터 추출 후 `enum_csv_col` 인덱스 기반 `_fv(col)` 헬퍼로 교체 |
| `debugger_start.py` | `update_svm_pca_graph()` — 존재하지 않는 특징 항목(`peak_mag`, `avg_mag`, `std_mag`, `low/mid/high_energy`) → 현재 21개 UART 특징 기반 항목(`kurtosis`, `skewness`, `dc_ratio`, `spectral_flatness`)으로 교체 |

---

## v0.9.3 — SVM 그래프 실시간 점 위치 구버전 속성 참조 제거

**날짜:** 2026-05-04

### 버그 수정

| 파일 | 수정 내용 |
|---|---|
| `debugger_start.py` | `update_svm_graph()` — `_col_to_attr` 딕셔너리(구버전 PC 25-특징 기반 `enum_csv_col` 키 사용) 전체 제거; `AttributeError: type object 'enum_csv_col' has no attribute 'PEAK_MAG'` 오류 수정 |
| `debugger_start.py` | `update_svm_graph()` — 현재 프레임 좌표 계산을 `svm.feature_vector_from_uart(svm_handle.ft)[int(col)]` 직접 인덱싱으로 교체 (now_scatter, 2D SVM 판정 블록 모두 적용) |

---

## v0.9.2 — MLP 자동 로드 시 PC 모델 혼용 방지

**날짜:** 2026-05-04

### 버그 수정

| 파일 | 수정 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | `_try_load_model()` — 파일명 역순 정렬 시 `_pc_` 접두 모델(PC 25-특징 전용)이 UART 21-특징 파이프라인에 우선 로드되는 문제 수정; candidates 필터에 `'_pc_' not in os.path.basename(p)` 조건 추가 |
| `AI/mlp/nn_mlp.py` | `_try_load_model()` — `ValueError: X has 21 features, but StandardScaler is expecting 25 features` 오류 방지 |

---

## v0.9.1 — ModuleNotFoundError 핫픽스

**날짜:** 2026-04-29

### 버그 수정

| 파일 | 수정 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | PC 특징 모드 선택 시 `ModuleNotFoundError: No module named 'pc_feature_extractor'` 오류 수정 — `__file__` 기준으로 `AI/mlp/` 경로를 `sys.path`에 동적 추가 (debugger_start.py 실행 시 작업 디렉토리가 다를 때도 정상 임포트) |

---

## v0.9.0 — PC 특징 재계산 모드 + GPU 가속 학습

**날짜:** 2026-04-29

### 추가 / 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/pc_feature_extractor.py` | **신규** — FFT 원시 데이터(129개 빈)로 PC에서 25개 특징 재계산 (`magnitudes_1~15`, `peak_freq`, `peak_mag`, `std_mag`, `centroid`, `low/mid_energy`, `rms`, `low_ratio`, `spectral_entropy`, `peak_to_mean`) |
| `AI/mlp/nn_mlp.py` | `train()` / `_train_impl()` — `feature_mode` 파라미터 추가 (`'esp32'` / `'pc'`) |
| `AI/mlp/nn_mlp.py` | `_train_impl()` — feature_mode에 따라 ESP32 21개 특징 또는 PC 재계산 25개 특징 분기 |
| `AI/mlp/nn_mlp.py` | `OccupancyMLP` 초기화 — `_n_features = X_train.shape[1]`로 동적 입력 크기 처리 (esp32/pc 모두 대응) |
| `AI/mlp/nn_mlp.py` | `_save_model()` — `feature_mode` 파라미터 추가, PC 모드 시 파일명에 `_pc` 태그 포함 |
| `AI/mlp/nn_mlp.py` | `_train_impl()` — CUDA 자동 감지 및 GPU 학습 지원 (`torch.device('cuda'/'cpu')`) |
| `AI/mlp/nn_mlp.py` | `_train_impl()` — 학습 시작 시 사용 디바이스 + GPU 이름 출력 |
| `AI/mlp/nn_mlp.py` | `_train_impl()` — 학습 배치 텐서 `.to(device)` 적용 |
| `AI/mlp/nn_mlp.py` | `_evaluate()` — `device` 파라미터 추가, 배치 텐서 `.to(device)` 적용 |
| `AI/mlp/nn_mlp.py` | `_permutation_importance()` — `device` 파라미터 추가, 추론 텐서 `.to(device)` + `.cpu().numpy()` 변환 |
| `debugger_start.py` | `MlpTrainWorker` — `feature_mode` 파라미터 추가, `train()` 호출 시 전달 |
| `debugger_start.py` | MLP Training GroupBox — Row 11에 **"특징 모드"** ComboBox 추가 (`ESP32 (21개 특징)` / `PC 재계산 (25개 특징)`) |
| `debugger_start.py` | `event_mlp_train()` — 선택된 특징 모드를 파싱해 `MlpTrainWorker`에 전달 |

---

## v0.8.0 — MLP 학습 파이프라인 개선 + GUI 하이퍼파라미터 전면 설정

**날짜:** 2026-04-29

### 추가 / 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | `_load_csv()` — 파일별 샘플 수 출력, 병합 총계 출력 |
| `AI/mlp/nn_mlp.py` | `_train_impl()` — 학습/검증 분리 개수·비율 출력 |
| `AI/mlp/nn_mlp.py` | `_train_impl()` — Best checkpoint (`state_dict` clone + 학습 완료 후 복원) |
| `AI/mlp/nn_mlp.py` | `_train_impl()` — Early stopping (`patience` 에폭 이상 Val Acc 미개선 시 자동 중단) |
| `AI/mlp/nn_mlp.py` | `OccupancyMLP.__init__` — `hidden_layers`, `dropout_rate` 런타임 파라미터화 |
| `AI/mlp/nn_mlp.py` | `train()` / `_train_impl()` — 6가지 하이퍼파라미터(`epochs`, `lr`, `early_stop_patience`, `hidden_layers`, `dropout_rate`, `batch_size`) + 4가지 분리 설정(`val_ratio`, `random_state`, `stratify`, `log_interval`) 파라미터 추가 |
| `AI/mlp/nn_mlp.py` | `_train_impl()` — 학습 시작 시 사용 특징 이름 출력 (`enum_csv_col` 활용) |
| `AI/mlp/nn_mlp.py` | `_save_model()` — `history` 파라미터 추가, 버전 파일명과 동일한 패턴으로 `_history.json` 저장 |
| `AI/mlp/nn_mlp.py` | `load_model_file()` 신규 — 지정 `.pt` 파일 로드 + `_history.json` 반환 |
| `AI/mlp/nn_mlp.py` | `models_dir()` 신규 — `models/` 폴더 절대 경로 반환 |
| `AI/mlp/nn_mlp.py` | `_infer_arch_from_state_dict()` 신규 — `state_dict` shape 역추론으로 `(input_size, hidden_layers)` 반환 |
| `AI/mlp/nn_mlp.py` | `_rebuild_model_from_state_dict()` 신규 — 구조 불일치 시 모델 자동 재빌드 (구버전 .pt 로드 가능) |
| `AI/mlp/nn_mlp.py` | `MLP_Module.feature_indices` — `@property`로 변경, `_svm_ref.A_feature_indices` 항상 동기화 |
| `AI/svm/svm.py` | `A_feature_indices` — `list(range(21))` 전체 21개 특징 사용으로 변경 |
| `debugger_start.py` | `MlpTrainWorker` — 10가지 하이퍼파라미터 전달 지원 |
| `debugger_start.py` | MLP Training GroupBox — GUI 위젯 전면 추가: 에폭/LR/Early Stop/Layer/Dropout/Batch/검증비율/분리시드/비율고정/로그주기 |
| `debugger_start.py` | `_on_mlp_train_finished()` — 학습 완료 후 모델 목록 자동 갱신 |
| `debugger_start.py` | `_refresh_mlp_model_list()` 신규 — `models/` 폴더 버전 `.pt` 파일 목록 ComboBox 갱신 |
| `debugger_start.py` | `event_mlp_load_model()` 신규 — 선택 모델 로드 + 저장된 학습 곡선 그래프 자동 표시 |
| `debugger_start.py` | `event_svm_feature_select()` — SVM 특징 변경 시 MLP `feature_indices`도 동기화 |
| `debugger_start.py` | `BUTTON_HOVER_BG_BOLD` 상수 추가 — `font-weight: bold` + hover 색상 혼합 스타일시트 |
| `debugger_start.py` | `log_TextEdit.append` — 학습 로그 GUI 실시간 출력 (`_Tee` 콜백 연결) |

### 버그 수정

| 파일 | 수정 내용 |
|---|---|
| `AI/mlp/nn_mlp.py` | `_try_load_model()` / `load_model_file()` — `_rebuild_model_from_state_dict()` 적용으로 구조 불일치 오류 해결 |
| `debugger_start.py` | `MACRO_FONT_BOLD + BUTTON_HOVER_BG` 혼합 → `BUTTON_HOVER_BG_BOLD`로 교체, Qt 스타일시트 파싱 경고 제거 |

### GUI MLP Training 패널 최종 레이아웃

```
Row  0 : CSV 경로 안내
Row  1 : 에폭 (10~2000)
Row  2 : LR (학습률)
Row  3 : Early Stop (0=비활성화)
Row  4 : Layer 구조
Row  5 : Dropout
Row  6 : Batch
Row  7 : 검증 비율  (전체 중 검증에 쓸 비율)
Row  8 : 분리 시드  (-1=매번 다름, 42=고정)
Row  9 : 비율 고정  (배경:사람 비율 유지 여부)
Row 10 : 로그 주기  (몇 에폭마다 출력)
Row 11 : [🧠 MLP 학습] 버튼
Row 12 : 진행률 바
Row 13 : 상태 레이블
Row 14 : 모델 선택 ComboBox
Row 15 : [🔄 목록 갱신] [📂 모델 로드]
```

---

## v0.7.1 — requirements.txt 추가 (가상환경 의존성 관리)

**날짜:** 2026-04-28

### 추가

| 파일 | 변경 내용 |
|---|---|
| `requirements.txt` | **신규** — 프로젝트 외부 의존성 목록: `PyQt6`, `pyqtgraph`, `pyserial`, `bleak`, `numpy`, `scikit-learn`, `torch` |

### 사용법

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## v0.7.0 — BLE 통신 모듈 추가 (UART/BLE 토글)

**날짜:** 2026-04-28

### 추가

| 파일 | 변경 내용 |
|---|---|
| `ble_worker.py` | **신규** — `BleWorker(QThread)` 구현; Nordic UART Service(NUS) GATT 기반 BLE 통신; `UartWorker`와 동일한 시그널(`event_new_data`, `event_connection_status`, `log_message`) 인터페이스 제공 |
| `ble_worker.py` | `BleSerial` 어댑터 클래스 — `serial.Serial.write()` 인터페이스 구현, 기존 `CommandSender.set_serial()` 재사용 가능 |
| `debugger_start.py` | Connection GroupBox에 UART/BLE 선택 `QButtonGroup` (RadioButton) 추가 (Row 0) |
| `debugger_start.py` | BLE 선택 시 포트/보드레이트 위젯 숨김, 장치명 입력 QLineEdit 표시 (`iSENSOR` 기본값) |
| `debugger_start.py` | `event_port_connection()` — 선택된 통신 방식에 따라 `UartWorker` / `BleWorker` 분기 생성 |

### 의존성

```
pip install bleak
```

### BLE GATT UUID (Nordic UART Service)

| UUID | 방향 | 용도 |
|---|---|---|
| `6E400001-...` | — | NUS Service |
| `6E400002-...` | PC → ESP32 | Write (명령 전송) |
| `6E400003-...` | ESP32 → PC | Notify (데이터 수신) |

---

## v0.6.5 — CSV 삭제 개선 + LED 버그 수정 + 자동 저장 개선 + UI 개선

**날짜:** 2026-04-28

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | `event_svm_clear()` 전면 재작성 — 다중 선택 QDialog(QCheckBox 목록) 표시; 현재 세션 파일 "← 현재 세션" 표시; 현재 파일 삭제 시에만 collector/SVM 리셋 |
| `debugger_start.py` | LED 토글 버튼 초기화 버그 수정 — `blockSignals(True/False)` 적용, 초기 상태 `setChecked(False)` ("🔴 LED OFF") |
| `debugger_start.py` | 자동 수집(BG/Human) 토글 OFF 시 `flush_write_buffer()` 호출 — 20개 미만 버퍼 데이터 손실 방지 |
| `debugger_start.py` | FFT Y축 레이블 "강도" → "에너지" 변경 |
| `debugger_start.py` | 좌측 패널 레이아웃 재구성 — Row4 Col1: ADC 주석(`adc_stats_GroupBox`), Row5 Col1: FFT Features(`fft_features_GroupBox`) |
| `debugger_start.py` | ADC/FFT 그래프 내 TextItem 제거 → 좌측 패널 QLabel(`adc_stats_Label`, `fft_features_Label`)로 이전 |
| `AI/training_data_collector.py` | `make_session_csv_path()` — `i_window`, `i_stride`, `i_interval` 파라미터 추가; 파일명에 메타데이터 포함 (`_W256_S32_I1`) |
| `debugger_start.py` | 자동 수집 토글 ON 시 현재 설정값(`i_adc_window_size`, `fft_stride_SpinBox`, `i_auto_save_stride`)으로 새 collector 생성 |

---

## v0.6.4 — Settings 패킷 `fft_stride` 필드 추가 (동기화 완성)

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `config.py` | `UART_RECEIVE_SETTINGS_FFT_STRIDE_BYTESIZE = 2` 상수 추가 |
| `uart_protocol/uart_protocol_config.py` | `RECEIVE_SETTINGS_FFT_STRIDE_LENGTH` 상수 추가; `RECEIVE_SETTINGS_TOTAL_SIZE` 45 → 47 bytes |
| `uart_protocol/data_models.py` | `SettingsData.i_fft_stride` 필드 추가 (uint16, default=32); 도큐스트링 45→47 bytes 수정 |
| `uart_protocol/data_parser.py` | `settings_parser()` — `b_pir_status` 파싱 뒤 `i_fft_stride` uint16 BE 파싱 블록 추가 |
| `debugger_start.py` | `_settings_loaded` 블록에 `fft_stride_SpinBox.setValue(SettingsData_handle.i_fft_stride)` 추가 |

### 프로토콜 변경

| 필드 | 위치 (offset) | 타입 | Endian |
|------|-------------|------|--------|
| `fft_stride` | byte 45~46 | uint16 | Big Endian |

---

## v0.6.3 — ESP Control 레이아웃 정리 + 전체 SpinBox ▲▼ 통일 + FFT Magnitude × Gain 오버레이

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | ESP Control 개별 전송 버튼(9개) 제거 → "📡 전체 설정 전송하기" 버튼 1개로 일괄 전송; TP + LED + 타이머 + Occu/Sleep 순서대로 전송, 실패 항목만 경고창에 표시 |
| `debugger_start.py` | 💡 LED ON/OFF 토글 버튼은 독립 유지 (즉시 전송) |
| `debugger_start.py` | ESP Control 모든 SpinBox(LED Max/Min/Dim, Work/Step/Delay, Occu T/O, Sleep)에 ▲▼ 버튼 추가 — FFT Setting과 동일한 스타일·구조 (`setFixedWidth(28)`, `NoFocus`, `Maximum` SizePolicy) |
| `debugger_start.py` | TP1/TP1 RCK/TP2 ▲▼ 버튼 테두리 스타일 제거 → FFT Setting과 동일한 무테두리 스타일로 통일 |
| `debugger_start.py` | FFT 그래프에 두 번째 선 추가 — `sqrt(energy) × Gain` (오렌지 `#ff8800` 실선); Gain SpinBox 변경 시 즉시 재갱신 (`_on_fft_gain_changed`) |

---

## v0.6.2 — SpinBox 설정값 보호 + FFT Setting UI 개선 + TP 버튼 스타일 통일

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | `_settings_loaded` 플래그 도입 — Settings 패킷 수신 시 최초 1회만 SpinBox 업데이트, 이후 사용자 입력값 유지 |
| `debugger_start.py` | 연결 해제(`event_connection_status_changed`) 시 `_settings_loaded = False` 리셋 → 재연결 후 초기값 자동 수신 |
| `debugger_start.py` | "🔄 설정 새로고침" 버튼 추가 (ESP Control GroupBox 하단 row 13) — 클릭 시 `_settings_loaded = False` 리셋, 다음 수신 1회 업데이트 |
| `debugger_start.py` | FFT Setting — `Stride:` + suffix `" smp"` → `Stride (smp):` + suffix 없음 |
| `debugger_start.py` | TP1 / TP1 RCK / TP2 ▲▼ 화살표 버튼 6개에 테두리 스타일 추가 (`border: 1px solid #7F7F7F; border-radius: 3px`) |

---

## v0.6.1 — Status/Control UI 개선 + Occu Timeout·Sleep Time µs 단위 직접 제어

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | `connect_status_Label` 초기값 `"🔴 Not connected"` 로 변경; 연결 시 `"🟢 Connected"`, 해제 시 `"🔴 Not connected"` 로 텍스트 변경 |
| `debugger_start.py` | Status GroupBox 타이틀 `"Setting"` → `"Status"`; LED/타이머 GroupBox 타이틀 `"Setting"` → `"iSENSOR ESP Control"` |
| `debugger_start.py` | Occu Timeout · Sleep Time SpinBox에 `µs / ms / s` 단위 선택 ComboBox 추가 (기본값 `s`); 전송 시 선택 단위 × 배율 → µs 변환 후 8byte uint64 LE 전송; Settings 수신 시 현재 단위로 나눠 SpinBox 표시 |
| `debugger_start.py` | `_on_time_unit_changed()`, `_send_time_value_occu()`, `_send_time_value_sleep()` 헬퍼 메서드 추가; `_TIME_UNIT_MULTIPLIER` 클래스 상수 추가 |
| `uart_protocol/command_sender.py` | `_uint64_le()` 헬퍼 추가; `send_set_occu_timeout_s` → `send_set_occu_timeout_us` (8byte), `send_set_sleep_time_s` → `send_set_sleep_time_us` (8byte) 로 변경 |

### 단위 선택 범위

| 단위 선택 | SpinBox 최대값 | µs 환산 최대 |
|----------|--------------|-------------|
| µs | 2,147,483,647 | ~35.7분 |
| ms | 2,147,483,647 | ~24.8일 |
| s | 2,147,483,647 | ~68년 |

---

## v0.6.0 — LED & 타이머 설정 GroupBox 추가 + Settings 자동 반영

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `config.py` | `CMD_SET_LED_MAX_PER(0x14)` ~ `CMD_SET_LED_ONOFF(0x1C)` 9개 커맨드 상수 추가 |
| `uart_protocol/uart_protocol_config.py` | `UartCommandType` enum에 9개 CMD 추가 |
| `uart_protocol/command_sender.py` | `send_set_led_max_per` / `send_set_led_min_per` / `send_set_led_dim_per` / `send_set_led_work_ms` / `send_set_led_step_ms` / `send_set_led_delay_ms` / `send_set_occu_timeout_s` / `send_set_sleep_time_s` / `send_set_led_onoff` 메서드 추가; 공통 `_uint32_le()` 헬퍼 추가 |
| `debugger_start.py` | Row4(2열 전체) "LED & 타이머 설정" GroupBox 추가 — LED Max/Min/Dim%, Work/Step/Delay ms, Occu Timeout(초), Sleep Time(초) SpinBox + 개별 전송 버튼; 💡 LED ON/OFF 체크가능 토글 버튼 추가; `_send_led_setting()` 공통 헬퍼 + `event_send_led_onoff_command()` 핸들러 추가; Settings 수신 시 모든 SpinBox 자동 반영 (us→초 변환 포함) |

### 커맨드 테이블

| CMD | 값 | Payload | 단위 |
|-----|-----|---------|------|
| `CMD_SET_LED_MAX_PER` | `0x14` | uint8_t | 0~100 % |
| `CMD_SET_LED_MIN_PER` | `0x15` | uint8_t | 0~100 % |
| `CMD_SET_LED_DIM_PER` | `0x16` | uint8_t | 0~100 % |
| `CMD_SET_LED_WORK_MS` | `0x17` | uint32_t LE | ms |
| `CMD_SET_LED_STEP_MS` | `0x18` | uint32_t LE | ms |
| `CMD_SET_LED_DELAY_MS`| `0x19` | uint32_t LE | ms |
| `CMD_SET_OCCU_TIMEOUT`| `0x1A` | uint32_t LE | 초 |
| `CMD_SET_SLEEP_TIME`  | `0x1B` | uint32_t LE | 초 |
| `CMD_SET_LED_ONOFF`   | `0x1C` | uint8_t | 0=OFF 1=ON |

---

## v0.5.1 — 좌측 패널 배치 column-first로 변경

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | 좌측 GridLayout 배치를 row-first → column-first로 변경: Connection(Row1 Col0), TP Setting(Row1 Col1), Status(Row2-3 Col0 rowSpan=2), FFT Setting(Row2 Col1), SVM Setting(Row3 Col1) |

### 변경 후 구조

```
Col0              │ Col1
Connection        │ TP Setting
Status (span 2행) │ FFT Setting
                  │ SVM Setting
```

---

## v0.5.0 — FFT Stride GUI 제어 + 좌측 패널 2열 레이아웃

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `config.py` | `LEFT_BOX_WIDTH` 400 → 800; `CMD_SET_FFT_STRIDE = 0x13` 추가 |
| `uart_protocol/uart_protocol_config.py` | `UartCommandType.CMD_SET_FFT_STRIDE = 0x13` 추가 |
| `uart_protocol/command_sender.py` | `send_set_fft_stride(i_stride_value: int) → bool` 메서드 추가 (범위 검증 1~256, uint16_t Little Endian) |
| `debugger_start.py` | 좌측 패널 `QVBoxLayout` → `QGridLayout` 2열 균등 배치; `FFT Gain` 그룹박스 타이틀 → `FFT Setting`; Stride SpinBox(1~256 smp, 기본 32) + ms 자동 환산 라벨 + 전송 버튼 추가; `event_send_fft_stride_command()` 핸들러 추가 |

### GUI 레이아웃 구조

```
Row0 (span 2열): 제어창
Row1 col0: Connection   | col1: Setting (Status)
Row2 col0: TP Setting   | col1: FFT Setting (Gain + Stride)
Row3 (span 2열): SVM Setting
```

### FFT Stride 제어 동작

- SpinBox 값 변경 시 `= N ms (약 X.XX s)` 라벨 실시간 갱신 (Fs=100 Hz 기준, 1 smp = 10 ms)
- "📡 Stride 전송" 버튼 → `CMD_SET_FFT_STRIDE(0x13)` 프레임 UART 전송
- 전송 성공/실패 로그 출력

---

## v0.4.4 — import 구조 패키지화 (AI/ `__init__.py` 추가)

**날짜:** 2026-04-27

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/__init__.py` | **신규** — `AI/` 디렉토리를 Python 패키지로 등록 |
| `debugger_start.py` | `sys.path.insert` 3회 + flat import → 프로젝트 루트 1회 insert + 패키지 import로 단순화: `from AI.svm import svm` / `from AI import training_data_collector as tdc` / `from AI.mlp import nn_mlp` |
| `AI/training_data_collector.py` | `AI/svm/` 에서 `AI/` 로 이동 (모델 무관 공용 모듈 위치 정정); import를 `sys.path.insert(AI/svm/) + import svm` 방식으로 수정 |

### 배경

`AI/svm/__init__.py`(빈 파일)가 존재하여 `import svm` 이 `AI/svm/svm.py` 대신 패키지를 불러오는 문제가 있었음.  
`AI/__init__.py`를 추가해 `AI`를 패키지로 만든 후 `from AI.svm import svm` 형태로 명시적 경로 import로 전환하여 해결.

---

## v0.4.3 — 파일 구조 재편 (fft/, AI/svm/, AI/mlp/)

**날짜:** 2026-04-27

### 변경

| 이전 경로 | 이후 경로 | 비고 |
|---|---|---|
| `fft.py` | `fft/__init__.py` | `uart_protocol/` 패턴 통일 |
| `svm.py` | `AI/svm/svm.py` | SVM 모듈 독립 패키지화 |
| `training_data_collector.py` | `AI/svm/training_data_collector.py` | SVM과 동일 패키지 |
| `AI/nn_mlp.py` | `AI/mlp/nn_mlp.py` | MLP 모듈 독립 패키지화 |
| `AI/prepare_data.py` | `AI/mlp/prepare_data.py` | MLP 전처리 스크립트 |
| `AI/visualize.py` | `AI/mlp/visualize.py` | MLP 시각화 스크립트 |
| `AI/TUNING_GUIDE.md` | `AI/mlp/TUNING_GUIDE.md` | |
| `AI/export/` | `AI/mlp/export/` | C 코드 내보내기 |
| `AI/models/` | `AI/mlp/models/` | 학습된 가중치/스케일러 |
| `AI/logs/` | `AI/mlp/logs/` | 학습 로그 |
| `AI/results/` | `AI/mlp/results/` | 검증 결과 |
| `AI/data_*.csv` | `AI/mlp/data_*.csv` | 분할 학습 데이터 |

각 폴더에 `__init__.py` 추가하여 Python 패키지로 구성.

---

## v0.4.2 — 학습 데이터 수집 모듈 분리 (TrainingDataCollector)

**날짜:** 2026-04-27

### 원인

`SVM_Module` 내부에 CSV 수집 로직(저장 버퍼, 카운터, 헤더 기록 등)이 내장되어 있어
MLP 등 다른 모델이 동일한 CSV를 재사용할 수 없는 구조였음.
학습 데이터 수집을 모델에 종속시키지 않고 공용 모듈로 분리함.

### 변경

| 파일 | 변경 내용 |
|---|---|
| `AI/svm/training_data_collector.py` | **신규** — `TrainingDataCollector` 클래스: CSV 경로·버퍼·카운터 소유, `save_sample(ft, i_label)` / `flush_write_buffer()` 제공 |
| `AI/svm/svm.py` | `SVM_Module.__init__`에서 `str_svm_csv_path`, `i_bg_count`, `i_human_count`, `_write_buffer`, `_b_need_header` 제거; `save_sample()` / `flush_write_buffer()` / `_load_counts_from_csv()` / `update_label_counts()` 메서드 제거; `_feature_vector_from_uart()` 정적 메서드 → 모듈 레벨 함수 `feature_vector_from_uart(ft)` 로 승격; `train()` 시그니처에 `str_csv_path: str = "svm_data.csv"` 파라미터 추가 |
| `AI/mlp/nn_mlp.py` | `_predict()` 내 `svm_ref._feature_vector_from_uart(svm_ref.ft)` → `svm.feature_vector_from_uart(svm_ref.ft)` |
| `debugger_start.py` | `import training_data_collector as tdc` 추가; `self.collector = tdc.TrainingDataCollector()` 인스턴스 생성; `SvmTrainWorker(svm_handle, str_csv_path)` 시그니처 업데이트; 모든 `svm_handle.save_sample` → `collector.save_sample(self.fft_features_data, ...)`, `svm_handle.flush_write_buffer()` → `collector.flush_write_buffer()`, `svm_handle.i_bg_count/i_human_count` → `collector.i_bg_count/i_human_count` 로 교체 |

### 결과

- `TrainingDataCollector`는 `svm`에 의존하지만 `svm`은 `training_data_collector`에 의존하지 않으므로 순환 의존 없음.
- MLP 학습 시에도 동일한 `TrainingDataCollector` 인스턴스로 CSV 수집 가능.

---

## v0.4.1 — FFT 특징 3개 신규 추가 (f_dc_ratio / f_delta_peak_freq / f_spectral_flatness)

**날짜:** 2026-04-25

### 원인

펌웨어 v0.3.5에서 `fft_features_t`에 3개 특징 추가 및 UART 패킷 확장:
`72 bytes (18 필드)` → `84 bytes (21 필드)`

### 변경

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `RECEIVE_FFT_FEATURES_TOTAL_SIZE` 72→84, 주석 18→21 필드 |
| `uart_protocol/data_models.py` | `FftFeaturesData`에 `f_dc_ratio`, `f_delta_peak_freq`, `f_spectral_flatness` 필드 추가, 테이블 및 `__repr__` 업데이트 |
| `uart_protocol/data_parser.py` | `fft_features_parser()` 오프셋 72/76/80에 3개 필드 파싱 추가, docstring 21 필드로 업데이트 |
| `svm.py` | `I_FEATURES_COUNT` 18→21, `enum_csv_col`에 `DC_RATIO=18`, `DELTA_PEAK_FREQ=19`, `SPECTRAL_FLATNESS=20` 추가, `_feature_vector_from_uart()` 21차원으로 확장 |
| `debugger_start.py` | `SvmFeatureDialog._FEATURE_DEFS`에 3개 항목 추가 |

### 신규 필드 (오프셋 72~80)

| 인덱스 | 필드명 | 설명 |
|--------|--------|------|
| 18 | `f_dc_ratio` | DC 에너지 비율 = E[k=0] / total_E |
| 19 | `f_delta_peak_freq` | 프레임 간 피크 주파수 변화량 (Hz) |
| 20 | `f_spectral_flatness` | 스펙트럼 평탄도 (1=백색잡음, 0=순수톤) |

### 결과

- 기존 `svm_data.csv` (21 컬럼) 형식 유지 (18→21 확장이므로 기존 18-컬럼 CSV는 재수집 필요)
- 펌웨어 `v0.3.5`와 프로토콜 호환.

---

## v0.4.0 — Python ML 파이프라인 UART 특징 기반으로 전면 재정렬

**날짜:** 2026-04-25

### 원인

Python(`svm.py`, `AI/nn_mlp.py`)이 `A_fft_magnitudes`(sqrt(E_k))로 특징을 직접 계산하고 있었으나,
ESP32는 에너지(re²+im²) 기반으로 특징을 계산하여 UART 타입 13으로 전송함.
→ Python이 계산한 값과 ESP32가 전송하는 값의 수치 스케일이 달라 학습/추론 파이프라인이 불일치 상태였음.

### 변경

| 파일 | 변경 내용 |
|---|---|
| `svm.py` | `import config` 제거, `I_FEATURES_COUNT=18`, `enum_csv_col` 18개 항목(UART 필드 순서), `__init__`에서 Python 계산 멤버 변수 제거 (`f_peak_freq`, `A_magnitudes` 등), `self.ft = None` (최신 FftFeaturesData), `svm(input_ft)` 서명 변경 (FftFeaturesData 직접 수신), `_feature_vector_from_uart(ft)` 정적 메서드 신규 추가, `save_sample()` / `train()` / `predict()` / `get_pca_now()` 모두 UART 특징 기반으로 변경, CSV 헤더 18컬럼+label(19열)로 변경 |
| `debugger_start.py` | `SvmFeatureDialog._FEATURE_DEFS` 18개 UART 특징으로 교체 (기존 14개), `buffer_setting()`에서 `svm_handle.svm(fft_features_data)` / `mlp_handle.mlp(fft_features_data)` 호출로 변경, 저장 버튼 가드 `A_magnitudes is None` → `ft is None`으로 변경, 자동저장 조건도 동일하게 변경 |
| `AI/nn_mlp.py` | `mlp(input_ft)` 서명 변경 (FftFeaturesData 직접 수신), `_predict()`에서 163차원 직접 계산 제거 → `svm_ref._feature_vector_from_uart(svm_ref.ft)` 사용 |

### 결과

- 학습·추론에 사용하는 특징값이 ESP32 UART 전송값과 완전히 일치함.
- 기존 `svm_data.csv` (142 컬럼 형식)는 새 형식(19 컬럼)과 호환 불가 — 데이터 재수집 필요.
- 펌웨어 `v0.3.4`와 프로토콜 호환.

---

## v0.3.1 — FFT_FEATURES(타입 13) 수신 지원 및 프로파일링 필드 재정의

**날짜:** 2026-04-24

### 원인

펌웨어 v0.3.4에서 `UART_TX_FFT_FEATURES` (타입 13, 72 bytes) 패킷 신규 추가 및
`UART_TX_PROFILING` 필드가 구버전(스택 HWM 포함 9개) → 신규 실행 시간 기반 9개로 재정의됨.

### 변경

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `UartDataType.FFT_FEATURES = 13` 추가, `RECEIVE_FFT_FEATURES_TOTAL_SIZE = 72` 추가, PROFILING 주석 신규 9개 필드로 업데이트 |
| `uart_protocol/data_models.py` | `ProfilingData` 9개 필드 재정의 (스택 HWM 제거 → ADC/FFT 실행 시간으로 교체), `FftFeaturesData` dataclass 신규 추가 (18개 필드, 72 bytes), `SensorData`에 `fft_features` 필드 추가 |
| `uart_protocol/data_parser.py` | `profiling_parser()` 루프 `range(8)→range(9)`, 신규 필드명 적용, `data_parser()` 타입 13 case 추가, `fft_features_parser()` 메서드 신규 구현 (float/int32/uint32 Big Endian) |
| `debugger_start.py` | `fft_features_data` 멤버 추가, `event_update_ui()`에서 타입 13 수신 시 저장, FFT 그래프 Y축 에너지(re²+im²)로 변경, FFT 레이블에 18개 특징값(영문+한글) 표시, 프로파일링 라벨 신규 9개 필드로 업데이트 |

### 신규: FFT_FEATURES 페이로드 (72 bytes, 18 필드 × 4 bytes Big Endian)

| 순서 | 필드명 | 타입 | 설명 |
|------|--------|------|------|
| 0 | `f_spectral_rolloff` | float | 스펙트럼 롤오프 (Hz) |
| 1 | `f_spectral_bandwidth` | float | 스펙트럼 대역폭 (Hz) |
| 2 | `i_peak_count` | int32 | 피크 빈 개수 |
| 3 | `f_mid_ratio` | float | 중주파(5~10Hz) 비율 |
| 4 | `f_low_to_high_ratio` | float | 저/고주파 에너지 비율 |
| 5 | `f_second_peak_freq` | float | 2번째 피크 주파수 (Hz) |
| 6 | `f_kurtosis` | float | 첨도 |
| 7 | `f_centroid` | float | 스펙트럼 무게중심 주파수 (Hz) |
| 8 | `f_peak_freq` | float | 1번째 피크 주파수 (Hz) |
| 9 | `f_low_ratio` | float | 저주파(0~5Hz) 비율 |
| 10 | `f_rms` | float | RMS 진폭 |
| 11 | `ui32_avg_energy` | uint32 | 평균 에너지 (정수) |
| 12 | `ui32_peak_energy` | uint32 | 피크 에너지 (정수) |
| 13 | `f_energy_variance` | float | 에너지 분산 |
| 14 | `f_peak_to_avg_e` | float | 피크/평균 에너지 비율 |
| 15 | `f_high_ratio` | float | 고주파(10Hz+) 비율 |
| 16 | `f_peak1_to_peak2_ratio` | float | 1위 vs 2위 피크 비율 |
| 17 | `f_skewness` | float | 왜도 |

### 변경: PROFILING 페이로드 (36 bytes, 9 필드 × uint32 Big Endian)

| 순서 | 구버전 필드 | 신버전 필드 |
|------|------------|------------|
| 0 | `adc_process_time_us` | `adc_reading_time_us` |
| 1 | `algo_process_time_us` | `adc_read_buffer_latency_time_us` |
| 2 | `loop_period_us` | `adc_processing_time_us` |
| 3 | `bg_stack_hwm` | `adc_buffer_insert_time_us` |
| 4 | `main_stack_hwm` | `fft_process_time_us` |
| 5 | `uart_tx_stack_hwm` | `fft_features_process_time_us` |
| 6 | `uart_rx_stack_hwm` | `fft_loop_a_time_us` |
| 7 | `fft_process_time_us` | `fft_loop_b_time_us` |
| 8 | `feat_process_time_us` | `fft_loop_c_time_us` |

### 결과

- 타입 13 패킷 수신 시 FFT 특징값 18개가 그래프 레이블에 실시간 표시됨.
- FFT 그래프 Y축이 진폭(magnitude)에서 에너지(re²+im², uint32)로 변경됨.
- 프로파일링 패널이 ADC/FFT 단계별 실행 시간 9개로 재편됨.
- 펌웨어 `v0.3.4`와 프로토콜 호환.

---

## v0.3.0 — FFT energy uint32 수신 및 magnitude 복원 처리

**날짜:** 2026-04-22

### 원인

펌웨어 v0.3.1에서 `UART_TX_FFT` 패킷 포맷이 `float magnitude × 129 (516 bytes)`에서
`uint32 energy × 129 (516 bytes)`로 변경됨.
PC에서 `sqrt(energy) / scale × 2/N` 으로 magnitude를 복원하여 기존 그래프에 표시.

### 변경

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `RECEIVE_FFT_TOTAL_SIZE` 확인 (516 bytes, 변동 없음) |
| `uart_protocol/data_models.py` | `FftData`에 `energies: List[int]` 필드 추가 (`magnitudes` 필드 유지) |
| `uart_protocol/data_parser.py` | `fft_parser()`: `>129f` → `>129I` (uint32 언패킹), magnitude 복원 수식 추가 (`sqrt(e)/8 × 2/256` 또는 `1/256` for k=0) |
| `debugger_start.py` | `A_fft_energies = numpy.array(fft_data.energies, dtype=numpy.uint32)` 추가 |

### FFT magnitude 복원 수식

```python
FFT_SC16_SCALE = 8
N = 256  # FFT_SIZE
magnitudes = [
    math.sqrt(e) / FFT_SC16_SCALE * (1.0 / N if k == 0 else 2.0 / N)
    for k, e in enumerate(energies)
]
```

### 결과

- 펌웨어에서 sqrtf×129 실행 없이 FFT 결과 전송.
- PC에서 `math.sqrt()` × 129 수행 (Python, GIL 영향 무시 수준).
- GUI FFT 그래프 표시 값 스케일 동일 (ADC 단위).
- `energies` 배열은 향후 PC 측 특징 추출 시 energy 기반 계산에 직접 사용 가능.

---

## v0.2.3 — 특징 추출 실행 시간 프로파일링 수신 지원

**날짜:** 2026-04-22

### 수정

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `RECEIVE_PROFILING_TOTAL_SIZE` 32 → 36 bytes (9×4, `feat_process_time_us` 필드 추가) |
| `uart_protocol/data_models.py` | `ProfilingData`에 `feat_process_time_us` 필드 추가, `__repr__` 업데이트 |
| `uart_protocol/data_parser.py` | `fields[8]` 파싱 추가 (`feat_process_time_us`) |
| `debugger_start.py` | 프로파일링 라벨에 `특징 추출: X µs` 항목 추가 |

### 결과

- 프로파일링 패널에 FFT 처리 시간과 별도로 특징 추출 실행 시간이 표시된다.
- 폄웨어 `v0.3.0`과 프로토콜 호환 (패이로드 9필드, 36 bytes)

---

## v0.2.2 — ADC/FFT 그래프 품질 개선 및 버그 수정

**날짜:** 2026-04-22

### 수정

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | ADC 그래프 Y축에 `IntAxisItem` 적용 — 자동 스케일 시 정수 배수 눈금만 표시 |
| `debugger_start.py` | FFT 그래프 Y축 `enableAutoSIPrefix(False)` 추가 — `×0.001` 같은 SI 배율 주석 제거, 소수점 직접 표시 |
| `debugger_start.py` | `get_adc_buffer_info()` 버그 수정 — 버퍼 전체가 0일 때 4개 값만 반환하던 문제 수정 (13개 기본값 반환으로 `ValueError` 해소) |
| `debugger_start.py` | ADC 수신 블록에서 FFT 그래프 갱신 호출 제거 — FFT 그래프는 `fft_result` 패킷 수신 시에만 갱신 |

### 상세

**IntAxisItem (ADC Y축 정수 눈금)**
- `pyqtgraph.AxisItem` 서브클래스 추가
- `tickValues()`: 화면 높이 기준 최대 ~8개 정수 간격 눈금 자동 생성 (1→2→5→10 배율)
- `tickStrings()`: 소수점 없이 정수 문자열 반환
- ADC Raw Full Scale / Zoom Scale 탭에만 적용 (FFT는 소수점 유지)

**FFT 그래프 갱신 분리**
- 이전: ADC 패킷 수신 시마다 `update_fft_graph()` 호출 → FFT 데이터 미변경 상태에서 재표시만 반복
- 이후: `fft_result` 패킷이 도착할 때만 갱신 (`FFT_STRIDE`=64샘플마다 1회)

**`get_adc_buffer_info()` 버그**
- 버퍼 전체 0일 때 (연결 직후 등) `return 0, 0, 0, 0` → `ValueError: not enough values to unpack (expected 13, got 4)` 발생
- 수정: 13개 기본값(전체 통계는 계산된 값, zero-excluded 통계는 0)을 반환하도록 변경

### 결과

- ADC Y축에 `0.5`, `1.5` 같은 소수 눈금이 사라지고 `1`, `2`, `3` 등 정수만 표시된다.
- FFT Y축에서 `×0.001` 배율 표기가 사라지고 `0.0012` 등 실제 소수점 값이 표시된다.
- 연결 직후 ADC 버퍼가 0으로 채워진 상태에서도 UI 오류 없이 정상 동작한다.
- ADC/FFT 그래프가 각자의 수신 주기에 맞춰 독립적으로 갱신된다.

---

## v0.2.1 — MLP 전용 Plot 분리 및 ADC 그래프 시간축 실시간 업데이트

**날짜:** 2026-04-22

### 수정

| 파일 | 변경 내용 |
|---|---|
| `debugger_start.py` | MLP 탭을 SVM TabWidget에서 분리하여 독립 `mlp_graph_GroupBox` + `mlp_plot_TabWidget` 생성. SVM/MLP 영역을 수직 컨테이너(`svm_mlp_Widget`)로 묶어 `main_HBoxLayout`에 단일 컬럼으로 배치 |
| `debugger_start.py` | ADC 그래프 시간축 하드코딩(`300`) → `cfg.WINDOW_SIZE`(=256) 초기값으로 변경. 데이터 수신 시마다 실제 버퍼 길이(`len(self.A_adc_buffer)`)로 X축을 실시간 갱신(`setXRange`) |

### 레이아웃 변경 상세

**이전:**
```
main_HBoxLayout
└── svm_graph_GroupBox
    └── svm_plot_TabWidget
        ├── SVM 탭
        ├── SVM PCA 탭
        ├── MLP 확률 탭   ← SVM TabWidget 내 혼재
        └── MLP 히스토리 탭
```

**이후:**
```
main_HBoxLayout
└── svm_mlp_Widget (수직 컨테이너)
    ├── svm_graph_GroupBox  →  svm_plot_TabWidget (SVM, SVM PCA)
    └── mlp_graph_GroupBox  →  mlp_plot_TabWidget (MLP 확률, MLP 히스토리)
```

### 결과

- SVM Plot과 MLP Plot이 동일 컬럼에서 50:50 비율로 위/아래 분리된다.
- ADC 그래프 X축이 ESP32 버퍼 크기와 항상 일치한다 (첫 수신 전에도 `cfg.WINDOW_SIZE` 기준).
- `WINDOW_SIZE` 값 변경 시 초기값과 실시간 축 범위 모두 자동으로 반영된다.

---

## v0.2.0 — ESP32 FFT 수신 파싱 및 PC FFT 연산 대체

**날짜:** 2026-04-22

### 원인

ESP32 펌웨어(v0.2.0)에서 온디바이스 FFT 결과를 UART 타입 12로 전송하도록 변경됨에 따라,
PC 측도 타입 12 파싱 로직을 추가하고 기존 PC 연산 FFT를 수신 FFT 데이터로 교체해야 했다.
또한 `ProfilingData`에 `fft_process_time_us` 필드가 추가(7→8 필드, 28→32 bytes)되어
타입 11 파서도 함께 수정이 필요했다.

### 수정

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `UartDataType.FFT = 12` 추가. `RECEIVE_FFT_TOTAL_SIZE = (WINDOW_SIZE//2+1)*4` (=516) 상수 추가. `RECEIVE_PROFILING_TOTAL_SIZE` 28→32 bytes로 수정 |
| `uart_protocol/data_models.py` | `ProfilingData`에 `fft_process_time_us` 필드 추가 (7→8 필드). `FftData` 데이터클래스 신규 추가(`magnitudes: List[float]`). `SensorData`에 `fft_result: Optional[FftData]` 필드 추가 |
| `uart_protocol/data_parser.py` | `profiling_parser()`: 파싱 루프 7→8 필드, `fft_process_time_us` 반환. `data_parser()`에 타입 12 분기 추가. `fft_parser()` 메서드 신규 구현 (516 bytes → 129 × float32 BE) |
| `debugger_start.py` | `buffer_setting()`: `fft_handle.fft()` 호출 주석 처리(PC FFT 비활성화). `event_update_ui()`: 타입 12 수신 시 `A_fft_frequencies` / `A_fft_magnitudes` 갱신 후 FFT 그래프 업데이트 |

**`FftData` 데이터클래스:**

| 필드 | 타입 | 설명 |
|---|---|---|
| `magnitudes` | `List[float]` | 129개 진폭값 (Big Endian float32 파싱 결과) |

**`ProfilingData` 변경 (7→8 필드):**

| 추가 필드 | 설명 | 단위 |
|---|---|---|
| `fft_process_time_us` | ESP32 FFT 실행 시간 | µs |

### 결과

- UART 타입 12 수신 시 `SensorData.fft_result`에 `FftData` 객체가 채워진다.
- PC FFT 연산(`fft_handle.fft()`)을 거치지 않고 ESP32 연산 결과로 FFT 그래프가 직접 갱신된다.
- SVM/MLP 추론은 기존과 동일하게 `A_fft_frequencies` / `A_fft_magnitudes` 를 사용한다.
- 타입 11 파싱 크기 불일치 오류 없이 32 bytes(8 필드)가 정상 파싱된다.

---

## v0.1.0 — 프로파일링 데이터(타입 11) 수신 파싱 추가

**날짜:** 2026-04-22

### 원인

펌웨어에서 UART 데이터 타입 11(`UART_TX_PROFILING`)으로 실행 시간 및 FreeRTOS Task
스택 고수위(HWM) 데이터 전송이 추가됨에 따라, PC 디버거 측에도 해당 타입의 수신 파싱
로직이 필요해졌다.

### 수정

| 파일 | 변경 내용 |
|---|---|
| `uart_protocol/uart_protocol_config.py` | `UartDataType.PROFILING = 11` 추가, `RECEIVE_PROFILING_TOTAL_SIZE = 28` 상수 추가 |
| `uart_protocol/data_models.py` | `ProfilingData` 데이터클래스 추가(7개 필드), `SensorData.profiling: Optional[ProfilingData]` 필드 추가 |
| `uart_protocol/data_parser.py` | `DataParser.data_parser()`에 타입 11 분기 추가, `profiling_parser()` 메서드 구현 |

**`ProfilingData` 데이터클래스 필드:**

| 필드 | 설명 | 단위 |
|---|---|---|
| `adc_process_time_us` | ADC 큐 수신 ~ 버퍼 저장 처리 시간 | µs |
| `algo_process_time_us` | TP1/TP2 알고리즘 실행 시간 | µs |
| `loop_period_us` | 배경 스레드 루프 주기 | µs |
| `bg_stack_hwm` | Background Task 스택 고수위 | words |
| `main_stack_hwm` | Main Task 스택 고수위 | words |
| `uart_tx_stack_hwm` | UART TX Task 스택 고수위 | words |
| `uart_rx_stack_hwm` | UART RX Task 스택 고수위 | words |

### 결과

- 타입 11 프레임 수신 시 `SensorData.profiling`에 파싱된 `ProfilingData` 객체가 채워진다.
- 파싱 포맷: 28 bytes, 7 × uint32_t Big Endian.
- 기존 프로토콜 파서 구조(`data_parser` → `data_models`)와 동일한 패턴을 유지한다.
