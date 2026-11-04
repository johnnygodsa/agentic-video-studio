#!/usr/bin/env bash
# 任何影片的 720p 預覽(< 29,000,000 bytes,兩段式編碼;re9 專用版見 re9_deliver.sh)。路徑全由 pipeline/paths.py 決定:
#   TAG=wow_forever VER=v1 bash pipeline/deliver_preview.sh preview -> <素材根>/output/<TAG>/<TAG>_${VER}_720p.mp4
# 完整版來源預設 <素材根>/output/<TAG>/<TAG>_${VER}.mp4;已交付到下載資料夾的版本用 SRC=<成片路徑> 指定。
set -euo pipefail
TAG=${TAG:?需要 TAG=<片名 tag>}
VER=${VER:-v1}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OUT=$(python "$HERE/paths.py" OUTPUT)/$TAG
BD=$(python "$HERE/paths.py" BUILD)/$TAG
SRC=${SRC:-$OUT/${TAG}_$VER.mp4}

preview() {
  local dur vk
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC")
  # 目標 27.3 MiB(約 28.6 MB,< 29,000,000 bytes):扣掉音訊 96k 與封裝/碼率誤差餘量 20k 後全給影像
  vk=$(python -c "print(int(27.3*8*1024*1024/float('$dur')/1000 - 96 - 20))")
  echo "preview: ${dur}s video ${vk}k"
  ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vf scale=1280:720:flags=lanczos -c:v libx264 -preset slow -b:v ${vk}k \
    -pass 1 -passlogfile "$BD/prev2pass" -an -f null -
  ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vf scale=1280:720:flags=lanczos -c:v libx264 -preset slow -b:v ${vk}k \
    -pass 2 -passlogfile "$BD/prev2pass" -c:a aac -b:a 96k -ar 48000 -movflags +faststart "$OUT/${TAG}_${VER}_720p.mp4"
  ls -la "$OUT/${TAG}_${VER}_720p.mp4"
}

"$@"
