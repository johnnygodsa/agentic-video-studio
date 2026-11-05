#!/usr/bin/env bash
# One-step setup (Linux / macOS / WSL).
#   ./scripts/install.sh          demo + tests: no GPU, no models
#   ./scripts/install.sh --full   full pipeline deps + Playwright Chromium + GSAP
set -euo pipefail
cd "$(dirname "$0")/.."
command -v ffmpeg >/dev/null || { echo "ffmpeg not found: install it first (apt install ffmpeg / brew install ffmpeg)"; exit 1; }
PY=${PYTHON:-python3}
"$PY" -m venv .venv
. .venv/bin/activate
python -m pip install -q --upgrade pip
if [ "${1:-}" = "--full" ]; then
  python -m pip install -q -r requirements.txt
  python -m playwright install chromium
  mkdir -p pipeline/static/vendor
  [ -f pipeline/static/vendor/gsap.min.js ] || curl -fsSL https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js -o pipeline/static/vendor/gsap.min.js
else
  python -m pip install -q -r requirements-ci.txt
fi
python -X utf8 pipeline/demo/run_demo.py --tts none --out demo_out
echo
echo "Done. Video: demo_out/demo.mp4   (activate later with: . .venv/bin/activate)"
