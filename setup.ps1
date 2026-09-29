# TTS 작업실 — 윈도우 처음 설치 (setup.bat 이 이 파일을 실행한다)
# 파이썬 3.12 · ffmpeg · Node.js 를 winget 으로 깔고, .venv 를 만들고, 화면을 빌드하고, 바탕화면 아이콘을 만든다.
# 음성 모델(0.6B 약 2.5GB / 1.7B 약 4.5GB)은 첫 생성 때 자동으로 받는다.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Root = $PSScriptRoot

function Step($msg) { Write-Host ""; Write-Host "▶ $msg" -ForegroundColor Cyan }
function RefreshPath {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Need($cmd, $id, $name) {
  if (Get-Command $cmd -ErrorAction SilentlyContinue) { Write-Host "  $name 있음"; return }
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "$name 가 없고 winget 도 없습니다. $name 를 직접 설치한 뒤 다시 실행하세요."
  }
  Write-Host "  $name 설치 중… (관리자 확인 창이 뜨면 '예')"
  winget install --id $id -e --silent --accept-source-agreements --accept-package-agreements | Out-Host
  RefreshPath
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    throw "$name 설치 뒤에도 찾을 수 없습니다. 이 창을 닫고 setup.bat 을 다시 실행하세요."
  }
}

Step "필요한 프로그램 확인"
Need "ffmpeg" "Gyan.FFmpeg" "ffmpeg"
Need "npm" "OpenJS.NodeJS.LTS" "Node.js"
$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) { try { & py -3.12 -c "print(1)" *> $null; if ($LASTEXITCODE -eq 0) { $py = @("py", "-3.12") } } catch {} }
if (-not $py) {
  Write-Host "  파이썬 3.12 설치 중…"
  winget install --id Python.Python.3.12 -e --silent --accept-source-agreements --accept-package-agreements | Out-Host
  RefreshPath
  $py = @("py", "-3.12")
}

Step "파이썬 환경 만들기 (.venv)"
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $py[0] $py[1] -m venv .venv }
$vpy = Join-Path $Root ".venv\Scripts\python.exe"
& $vpy -m pip install --upgrade pip | Out-Null

$gpu = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { & nvidia-smi *> $null; $gpu = ($LASTEXITCODE -eq 0) }
if ($gpu) {
  Step "NVIDIA 그래픽카드 발견 → GPU 판 PyTorch 설치 (1.7B 모델을 씁니다)"
  & $vpy -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126
} else {
  Step "그래픽카드 가속 없음 → CPU 판 PyTorch 설치 (0.6B 모델을 씁니다, 느립니다)"
  & $vpy -m pip install torch torchaudio
}
if ($LASTEXITCODE -ne 0) { throw "PyTorch 설치 실패" }

Step "나머지 패키지 설치"
& $vpy -m pip install -r requirements-win.txt
if ($LASTEXITCODE -ne 0) { throw "패키지 설치 실패" }

Step "화면 빌드"
Push-Location web
npm ci
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm ci 실패" }
npm run build | Out-Null
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "화면 빌드 실패" }
Pop-Location

New-Item -ItemType Directory -Force -Path voices, projects | Out-Null

Step "바탕화면 아이콘 만들기"
& $vpy tools\make_icon.py tools\icon.ico
$desktop = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path $desktop "TTS 작업실.lnk"))
$lnk.TargetPath = Join-Path $Root "studio.bat"
$lnk.WorkingDirectory = $Root
$lnk.IconLocation = (Join-Path $Root "tools\icon.ico")
$lnk.Description = "TTS 작업실 — 내 목소리 나레이션"
$lnk.Save()

Step "준비 끝"
Write-Host "  1) 바탕화면의 'TTS 작업실' 아이콘을 누르세요. 까만 창이 뜨고 브라우저가 열립니다. 그 창을 닫으면 꺼집니다."
Write-Host "  2) 처음 열면 목소리 화면이 뜹니다. 10~15초 녹음하고(짧을수록 빠르고 가볍습니다), 받아쓰기를 실제로 말한 대로 고치세요."
Write-Host "  3) 첫 생성 때 모델을 내려받느라 몇 분 걸립니다."
if (-not $gpu) { Write-Host "  ※ 그래픽카드 가속 없이 CPU 로 돕니다. 문장 길이의 5~15배 시간이 걸릴 수 있습니다." -ForegroundColor Yellow }
