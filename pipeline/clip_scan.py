"""影片片段程式篩選:對 raw\<src>.mp4 每秒取一格,用亮度(黑/過暗)與 OCR(assets_lib.ocr_batch,預設 RapidOCR,OCR_ENGINE=win 退回 Windows OCR;logo、字卡、ESRB、內嵌字幕)
剔除壞格,輸出連續乾淨區段。不逐格看圖。
python pipeline/clip_scan.py <src>... [--min 3] [--dark 22] [--out tmp/clip_scan.json]   (偏暗的遊戲如 Alan Wake 用 --dark 10)
結果 {src: {"dur":秒, "runs":[[起,止,平均亮度],…], "bad":{亮度:n,文字:n}}}
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import assets_lib as AL
import paths as P

DARK_MIN = 22          # 全幅平均亮度低於此視為過暗
TEXT_MIN = 8           # 一格 OCR 英文字母數 >= 此值視為有字卡/字幕
WORDS = re.compile(r"ESRB|RATING|PEGI|MATURE|PLAYSTATION|XBOX|NINTENDO|STEAM|COPYRIGHT|RIGHTS|PRE-?ORDER|WISHLIST|AVAILABLE|COMING|SUBSCRIBE|SHOWCASE|GAME PASS", re.I)
SCENE_THR = 0.3        # ffmpeg scene 分數超過此值視為硬切


def scene_cuts(src, thr=SCENE_THR):
    """raw\\<src>.mp4 整支的硬切時間(秒 = 新鏡頭第一格的時間)。縮到 320 寬跑 ffmpeg 的 scene 偵測;
    結果快取在 raw\\<src>.cuts.json(門檻或檔案大小變了才重算)。"""
    path = P.RAW / f"{src}.mp4"
    cache = path.with_suffix(".cuts.json")
    sig = [thr, path.stat().st_size]
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("sig") == sig:
                return data["cuts"]
        except ValueError:
            pass
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-an", "-sn", "-vf",
                        f"scale=320:-2,select='gt(scene,{thr})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    cuts = [round(float(x), 3) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    cache.write_text(json.dumps(dict(sig=sig, cuts=cuts)), encoding="utf-8")
    return cuts


def scan(src, min_run=3):
    work = P.TMP / "clip_scan" / src
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(P.RAW / f"{src}.mp4"), "-vf", "fps=1,scale=960:-2",
                    "-q:v", "4", str(work / "%04d.jpg")], check=True)
    files = sorted(work.glob("*.jpg"))
    lum = [float(np.asarray(Image.open(f).convert("L")).mean()) for f in files]
    txt = AL.ocr_batch(work)
    ok, nb_l, nb_t = [], 0, 0
    for f, y in zip(files, lum):
        t = txt.get(f.name, "")
        letters = len(re.findall(r"[A-Za-z]", t))
        bad_l = y < DARK_MIN
        bad_t = letters >= TEXT_MIN or (letters >= 3 and bool(WORDS.search(t)))
        nb_l += bad_l
        nb_t += bad_t and not bad_l
        ok.append(not (bad_l or bad_t))
    runs, i, n = [], 0, len(ok)
    while i < n:
        if not ok[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and ok[j + 1]:
            j += 1
        # 第 k 張 ≈ k-1 ~ k 秒;兩端各內縮 0.5 秒避開邊界
        a, b = i + 0.5, j + 1 - 0.5 + 0.0
        if b - a >= min_run:
            runs.append([a, b, round(float(np.mean(lum[i:j + 1])), 1)])
        i = j + 1
    shutil.rmtree(work, ignore_errors=True)
    return {"dur": n, "runs": runs, "bad": {"亮度": nb_l, "文字": nb_t}}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mr = float(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 3
    outp = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else P.TMP / "clip_scan.json"
    if "--min" in sys.argv:
        args.remove(sys.argv[sys.argv.index("--min") + 1])
    if "--dark" in sys.argv:
        DARK_MIN = float(sys.argv[sys.argv.index("--dark") + 1])
        args.remove(sys.argv[sys.argv.index("--dark") + 1])
    if "--out" in sys.argv:
        args.remove(sys.argv[sys.argv.index("--out") + 1])
    res = {}
    for s in args:
        res[s] = scan(s, mr)
        r = res[s]
        print(f"{s}: dur={r['dur']} runs={len(r['runs'])} 可用={sum(b - a for a, b, _ in r['runs']):.0f}s 剔除={r['bad']}")
    outp.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
