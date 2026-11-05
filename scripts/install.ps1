# One-step setup (Windows PowerShell).
#   .\scripts\install.ps1          demo + tests: no GPU, no models
#   .\scripts\install.ps1 -Full    full pipeline deps + Playwright Chromium + GSAP
param([switch]$Full)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Error "ffmpeg not found: install it first (winget install Gyan.FFmpeg)"; exit 1 }
python -m venv .venv
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -q --upgrade pip
if ($Full) {
  & $py -m pip install -q -r requirements.txt
  & $py -m playwright install chromium
  New-Item -ItemType Directory -Force pipeline\static\vendor | Out-Null
  if (-not (Test-Path pipeline\static\vendor\gsap.min.js)) {
    Invoke-WebRequest https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js -OutFile pipeline\static\vendor\gsap.min.js
  }
} else {
  & $py -m pip install -q -r requirements-ci.txt
}
& $py -X utf8 pipeline\demo\run_demo.py --tts none --out demo_out
Write-Host "`nDone. Video: demo_out\demo.mp4   (activate later with: .\.venv\Scripts\Activate.ps1)"
