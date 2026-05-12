# iSENSOR UART Debugger - 환경 자동 설치 스크립트
# 사용법: PowerShell에서 .\setup.ps1 실행
# GPU(NVIDIA) 감지 시 CUDA 빌드 torch를, 없으면 CPU 빌드를 자동 설치합니다.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── Python 3.12 확인 ────────────────────────────────────────────
Write-Host "`n[1/4] Python 3.12 확인 중..." -ForegroundColor Cyan
try {
    $pyVer = & py -3.12 --version 2>&1
    Write-Host "  OK: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "  Python 3.12 미설치 → winget으로 설치합니다." -ForegroundColor Yellow
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    # PATH 갱신을 위해 재실행 필요 여부 안내
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User')
}

# ── 가상환경 생성 ────────────────────────────────────────────────
Write-Host "`n[2/4] 가상환경 생성 중 (.venv, Python 3.12)..." -ForegroundColor Cyan
if (Test-Path ".venv") {
    Write-Host "  기존 .venv 발견 → 재사용합니다." -ForegroundColor Yellow
} else {
    & py -3.12 -m venv .venv
    Write-Host "  OK: .venv 생성 완료" -ForegroundColor Green
}

$pip = ".venv\Scripts\python.exe"

# ── GPU 감지 ────────────────────────────────────────────────────
Write-Host "`n[3/4] GPU 감지 중..." -ForegroundColor Cyan
$gpuFound = $false
try {
    $nvsmi = & nvidia-smi 2>&1
    if ($LASTEXITCODE -eq 0) {
        $gpuFound = $true
        # GPU 이름 파싱
        $gpuLine = $nvsmi | Select-String "GeForce|RTX|GTX|Quadro|Tesla" | Select-Object -First 1
        Write-Host "  NVIDIA GPU 감지됨: $($gpuLine.Line.Trim())" -ForegroundColor Green
    }
} catch {
    # nvidia-smi 없음 → CPU 전용
}

# ── torch 설치 ──────────────────────────────────────────────────
if ($gpuFound) {
    Write-Host "`n  → GPU 빌드 설치 (torch+cu124, 약 2.5GB)..." -ForegroundColor Cyan
    & $pip -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
} else {
    Write-Host "`n  → GPU 없음 — CPU 빌드 설치..." -ForegroundColor Cyan
    & $pip -m pip install torch
}

# ── 나머지 의존성 ────────────────────────────────────────────────
Write-Host "`n[4/4] requirements.txt 설치 중..." -ForegroundColor Cyan
& $pip -m pip install -r requirements.txt

# ── 결과 확인 ───────────────────────────────────────────────────
Write-Host "`n설치 완료 — 환경 확인:" -ForegroundColor Green
& $pip -c "import torch; cuda=torch.cuda.is_available(); gpu=torch.cuda.get_device_name(0) if cuda else 'N/A'; print(f'  torch : {torch.__version__}'); print(f'  CUDA  : {cuda}'); print(f'  GPU   : {gpu}')"

Write-Host "`n실행 방법:" -ForegroundColor Cyan
Write-Host "  .venv\Scripts\Activate.ps1"
Write-Host "  python debugger_start.py"
