#!/usr/bin/env python3
r"""成片總覽圖:每 N 秒取一格(含燒進去的字幕),標上時間、句編號與鏡頭種類,供逐張檢查。

python -X utf8 pipeline/qa_sheet.py <成片.mp4> <timeline.json> <輸出前綴> [--every 6] [--per 30] [--cols 5] [--times 12.5,40 ...]
輸出 <前綴>_01.png、_02.png…(每張寬 480*cols、最多 per 格);--times 改為只取指定秒數(抽查用)。
"""
import argparse
import io
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import paths as P

FONT = r"C:\Windows\Fonts\msjhbd.ttc"
CW, CH = 480, 270


def grab(video, t):
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={CW}:{CH}", "-f", "image2pipe", "-c:v", "png", "-"], capture_output=True)
    return Image.open(io.BytesIO(p.stdout)).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("timeline")
    ap.add_argument("out")
    ap.add_argument("--every", type=float, default=6.0)
    ap.add_argument("--per", type=int, default=30)
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--times")
    a = ap.parse_args()
    # 相對路徑以素材根為基準(build/<tag>/...、output/<tag>/...),與目前工作目錄無關
    a.video, a.timeline, a.out = P.find(a.video), P.find(a.timeline), P.out_file(a.out)
    tl = json.loads(Path(a.timeline).read_text(encoding="utf-8"))
    total = tl["total_frames"] / tl["fps"]
    if a.times:
        ts = [float(x) for x in a.times.split(",")]
    else:
        ts, t = [], a.every / 2
        while t < total:
            ts.append(t)
            t += a.every

    def label(t):
        ln = next((l for l in tl["lines"] if l["visual_start"] <= t < l["visual_end"]), None)
        sh = next((s for s in tl.get("shots", []) if s["start"] <= t < s["end"]), None)
        kind = ""
        if sh:
            kind = sh.get("special") or ("img" if sh["kind"] == "image" else (sh.get("tag") or "video"))
        return f"{int(t // 60)}:{t % 60:04.1f} 句{ln['idx'] if ln else '?'} {kind}"

    with ThreadPoolExecutor(6) as ex:
        ims = list(ex.map(lambda t: grab(a.video, t), ts))
    font = ImageFont.truetype(FONT, 17)
    outs = []
    for k in range(0, len(ts), a.per):
        chunk = list(zip(ts[k:k + a.per], ims[k:k + a.per]))
        sheet = Image.new("RGB", (CW * a.cols, CH * -(-len(chunk) // a.cols)), (0, 0, 0))
        d = ImageDraw.Draw(sheet)
        for i, (t, im) in enumerate(chunk):
            x, y = (i % a.cols) * CW, (i // a.cols) * CH
            sheet.paste(im, (x, y))
            lab = label(t)
            d.rectangle([x, y, x + d.textlength(lab, font=font) + 8, y + 22], fill=(0, 0, 0))
            d.text((x + 4, y + 1), lab, font=font, fill=(255, 255, 0))
        f = Path(f"{a.out}_{k // a.per + 1:02d}.png")
        sheet.save(f)
        outs.append(f)
        print(f, sheet.size)


if __name__ == "__main__":
    main()
