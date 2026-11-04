"""片段二次篩選(clips_lib 之外的補強):對 clips.json 內每支來源每 0.5 秒一格,量 平均亮度/對比(標準差)/下方字幕帶 OCR 字母數,
結果快取 tmp/clips_screen/<src>.json,再依門檻算出「不合格區間」寫回 clips.json 的 "exclude": {src: [[起,止],…]}(clips_lib.build 會把這些區間從片段挖掉)。
python pipeline/clips_screen.py --tag T scan            # 掃描並快取(OCR 慢)
python pipeline/clips_screen.py --tag T stats SRC T1 T2   # 印某來源 T1~T2 秒的逐格數值(校準門檻用)
python pipeline/clips_screen.py --tag T apply [--dark Y] [--dark-src SRC=Y ...] [--white 215] [--flat 22] [--flat-src tag:ow3=15 ...] [--letters 5]
  dark:Y 低於此值;white:Y 高於此值;flat:標準差低於此值(灰白低對比);letters:下方 30% 條帶 OCR 英文字母 >= 此值(內嵌字幕)
  --dark-src 可對單一來源(或標籤 tag:ow3)覆寫暗門檻。apply 會重算 exclude 的「自動」部分(key "auto_exclude"),手動 "exclude" 不動。
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import clips_lib as CL
import paths as P

FPS = 2
OCR_PS1 = Path(__file__).with_name("ocr_batch.ps1")
WORK = P.TMP / "clips_screen"


def cache_file(src):
    return WORK / f"{src}.json"


def scan_src(src):
    cf = cache_file(src)
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    d = WORK / "_frames" / src
    shutil.rmtree(d, ignore_errors=True)
    (d / "full").mkdir(parents=True)
    (d / "bot").mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(CL.raw(src)), "-vf", f"fps={FPS},scale=960:-2", "-q:v", "4",
                    str(d / "full" / "%05d.jpg")], check=True)
    files = sorted((d / "full").glob("*.jpg"))
    rows = []
    for f in files:
        im = Image.open(f).convert("L")
        a = np.asarray(im, dtype=np.float32)
        h = a.shape[0]
        # 取中間 80% 高(避開黑邊),量亮度與對比
        mid = a[int(h * 0.1):int(h * 0.9)]
        rows.append([float(mid.mean()), float(mid.std())])
        Image.open(f).crop((0, int(h * 0.7), 960, h)).save(d / "bot" / f.name, quality=90)
    out = d / "ocr.json"
    subprocess.run(["powershell", "-NoProfile", "-File", str(OCR_PS1), str(d / "bot"), str(out)], check=True)
    txt = json.loads(out.read_text(encoding="utf-8-sig"))
    res = []
    for i, f in enumerate(files):
        t = txt.get(f.name, "")
        res.append({"t": round(i / FPS, 2), "y": round(rows[i][0], 1), "sd": round(rows[i][1], 1),
                    "n": len(re.findall(r"[A-Za-z]", t)), "text": t[:60]})
    cf.parent.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(d, ignore_errors=True)
    return res


def load_spec(tag):
    path = P.project_file(tag, "clips.json")
    return path, json.loads(path.read_text(encoding="utf-8"))


def srcs_of(spec):
    dis = set(spec.get("disable", []))
    return [s for s in spec["sources"] if s not in dis and CL.raw(s).exists()]


def merge(bad_ts, pad=0.5):
    """不合格時間點(每格代表 1/FPS 秒)併成區間,前後各留 pad"""
    out = []
    for t in sorted(bad_ts):
        a, b = t - pad, t + 1 / FPS + pad
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [[round(max(a, 0), 1), round(b, 1)] for a, b in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("cmd", choices=["scan", "stats", "apply"])
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--dark", type=float, default=0)
    ap.add_argument("--dark-src", action="append", default=[])
    ap.add_argument("--flat-src", action="append", default=[], help="同 --dark-src,覆寫低對比門檻")
    ap.add_argument("--white", type=float, default=0)
    ap.add_argument("--flat", type=float, default=0)
    ap.add_argument("--letters", type=int, default=0)
    a = ap.parse_args()
    path, spec = load_spec(a.tag)
    if a.cmd == "scan":
        for s in srcs_of(spec):
            r = scan_src(s)
            print(f"{s}: {len(r)} 格")
        return
    if a.cmd == "stats":
        src, t1, t2 = a.rest[0], float(a.rest[1]), float(a.rest[2])
        for r in scan_src(src):
            if t1 <= r["t"] <= t2:
                print(r["t"], r["y"], r["sd"], r["n"], r["text"])
        return
    dark_over = {}
    for kv in a.dark_src:
        k, v = kv.rsplit("=", 1)
        dark_over[k] = float(v)
    flat_over = {}
    for kv in a.flat_src:
        k, v = kv.rsplit("=", 1)
        flat_over[k] = float(v)
    tag_of = {}
    for s, segs in spec["sources"].items():
        tag_of[s] = {t for seg in segs for t in (seg["tags"] if isinstance(seg, dict) else seg[2])}
    auto = {}
    for s in srcs_of(spec):
        dthr = dark_over.get(s)
        if dthr is None:
            dthr = max([v for k, v in dark_over.items() if k.startswith("tag:") and k[4:] in tag_of[s]] + [a.dark])
        fthr = max([v for k, v in flat_over.items() if k.startswith("tag:") and k[4:] in tag_of[s]] + [flat_over.get(s, 0), a.flat])
        bad = []
        for r in scan_src(s):
            if (dthr and r["y"] < dthr) or (a.white and r["y"] > a.white) or (fthr and r["sd"] < fthr) \
                    or (a.letters and r["n"] >= a.letters):
                bad.append(r["t"])
        if bad:
            auto[s] = merge(bad)
    spec["auto_exclude"] = auto
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("auto_exclude:", {s: len(v) for s, v in auto.items()})


if __name__ == "__main__":
    sys.exit(main())
