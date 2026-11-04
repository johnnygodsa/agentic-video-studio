"""影片片段共用引擎(F3-1;取代各片 assets_<tag>_clips.py 的重複程式,舊檔保留為 legacy)。
輸入 projects/<tag>/clips.json(格式見 pipeline/README.md「clips_lib」),輸出 projects/<tag>/clips_<tag>.json(build.py --clips auto 讀的檔)。
python -X utf8 pipeline/clips_lib.py --tag <tag>                      # 依 clips.json 重建片段檔(自動修黑場頭尾、標 dark、偵測黑邊、存片段內硬切 cuts)
python -X utf8 pipeline/clips_lib.py --tag <tag> --check              # 每標籤片段數/總長度、每支來源 <=上限秒、起點與內部黑畫面
python -X utf8 pipeline/clips_lib.py --tag <tag> --overview           # 每支來源一張總覽圖(每片段中間一格)
python -X utf8 pipeline/clips_lib.py --tag <tag> --preview [--nf 3]   # 每標籤一張(nf>1 每片段等分 nf 格,選片用)
python -X utf8 pipeline/clips_lib.py --tag <tag> --sheet SRC START END STEP [OUT]   # 來源指定區間每 STEP 秒一格
共用選項:--spec <clips.json 路徑>(預設 projects/<tag>/clips.json)、--out <片段檔路徑>(預設 paths.clips_file(tag))、--outdir <圖片資料夾>(預設 output/<tag>)
"""
import argparse
import io
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

import clip_scan as CS
import paths as P

DEFAULTS = {"max_per_src": 120.0, "sec_per_line": 4.0, "black": 6, "dark": 40, "fps": 4, "scene_cuts": True}
SEG_KEYS = ("start", "end", "tags", "note")


class Spec:
    """clips.json 載入後的設定;欄位見 README。"""

    def __init__(self, tag, path=None, out=None):
        self.tag = tag
        self.path = Path(path) if path else P.project_file(tag, "clips.json")
        d = json.loads(self.path.read_text(encoding="utf-8"))
        self.params = dict(DEFAULTS, **d.get("params", {}))
        self.tags = d.get("tags") or []
        self.min = d.get("min", {})          # {標籤: [最少段數, 最少總秒]},有列的標籤不用通用門檻
        self.crop = d.get("crop", {})        # {來源: "w:h:x:y"}
        self.safe = d.get("safe", {})        # {來源: {"top":..,"bottom":..}}
        self.section = d.get("section", {})  # {來源: section_offset}
        self.script = P.REPO / d["script"] if d.get("script") else P.REPO / tag / "script.txt"
        self.disable = set(d.get("disable", []))     # 整支停用的來源(build 不收其片段)
        self.exclude = {}                            # {來源: [[起,止],…]} = 手動 "exclude" + clips_screen.py 產生的 "auto_exclude",build 時從片段挖掉
        for k in ("exclude", "auto_exclude"):
            for src, iv in d.get(k, {}).items():
                self.exclude.setdefault(src, []).extend(iv)
        self.seg = {src: [norm_seg(s) for s in segs] for src, segs in d["sources"].items() if src not in self.disable}
        self.out = Path(out) if out else P.clips_file(tag)
        if not self.tags:
            self.tags = list(dict.fromkeys(t for segs in self.seg.values() for s in segs for t in s[2]))

    def p(self, k):
        return self.params[k]


def norm_seg(s):
    """片段可寫物件 {start,end,tags,note,+覆寫欄位} 或陣列 [起,止,[標籤],備註,{覆寫}];回傳 (a,b,tags,note,over)"""
    if isinstance(s, dict):
        return (s["start"], s["end"], list(s["tags"]), s.get("note", ""), {k: v for k, v in s.items() if k not in SEG_KEYS})
    a, b, tags, note, *over = s
    return (a, b, list(tags), note, over[0] if over else {})


def minus_ranges(a, b, excl):
    """[a,b] 扣掉 excl 區間後剩下的片段(長度 < 1 秒者略)"""
    out, cur = [], a
    for x, y in sorted(excl):
        if y <= cur or x >= b:
            continue
        if x - cur >= 1.0:
            out.append((cur, x))
        cur = max(cur, y)
    if b - cur >= 1.0:
        out.append((cur, b))
    return out


def raw(src):
    return P.RAW / f"{src}.mp4"


def probe_dur(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw(src))],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def detect_crop(src, a, b):
    """在片段內取 3 個時間點 cropdetect,只接受純黑邊(pillarbox 或 letterbox)且 >=3%;回傳 'w:h:x:y' 或 None"""
    best = None
    for f in (0.2, 0.5, 0.8):
        r = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{a + (b - a) * f:.1f}", "-t", "2", "-i", str(raw(src)),
                            "-vf", "cropdetect=24:2:0", "-f", "null", "-"], capture_output=True, text=True)
        m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr)
        if m:
            w, h, x, y = map(int, m[-1])
            if best is None or w * h > best[0] * best[1]:
                best = (w, h, x, y)
    if not best:
        return None
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(raw(src))], capture_output=True, text=True)
    W, H = map(int, r.stdout.strip().split(",")[:2])
    w, h, x, y = best
    pillar = h >= H * 0.99 and w < W * 0.97 and abs(x - (W - w - x)) <= 4
    letter = w >= W * 0.99 and h < H * 0.97 and abs(y - (H - h - y)) <= 4
    return f"{w}:{h}:{x}:{y}" if (pillar or letter) else None


def luma(sp, src, a, b, crop=None):
    """a~b 秒每 1/fps 秒一個平均亮度(crop 內)"""
    vf = (f"crop={crop}," if crop else "") + f"fps={sp.p('fps')},scale=64:36,format=gray"
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.2f}", "-t", f"{b - a:.2f}", "-i", str(raw(src)),
                          "-vf", vf, "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(out, dtype=np.uint8).reshape(-1, 64 * 36).mean(1)


def refine(sp, src, a, b, crop):
    """切掉黑場:在 a~b 內找出連續「不黑」區段(容許 1 格的黑閃),兩端各內縮 0.25 秒,留 >=2.5 秒者。
    回傳 [(start, end, mean_luma)]"""
    fps = sp.p("fps")
    y = luma(sp, src, a, b, crop)
    n = len(y)
    ok = [v >= sp.p("black") + 3 for v in y]    # 比檢查門檻嚴一點,避免取樣對齊差異
    for i in range(1, n - 1):                  # 單格黑閃視為連續
        if not ok[i] and ok[i - 1] and ok[i + 1]:
            ok[i] = True
    out, i = [], 0
    while i < n:
        if not ok[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and ok[j + 1]:
            j += 1
        s0 = a + i / fps + (0.25 if i > 0 else 0)
        e0 = a + (j + 1) / fps - (0.25 if j < n - 1 else 0)
        if e0 - s0 >= 2.5:
            out.append((round(s0, 1), round(e0, 1), float(y[i:j + 1].mean())))
        i = j + 1
    return out


def build(sp):
    clips = []
    have = [src for src in sp.seg if raw(src).exists()]
    all_cuts = {}
    if sp.p("scene_cuts"):   # 來源影片內的硬切(每支整支掃一次,有快取 raw/<src>.cuts.json):存進各片段的 cuts,build.py 挑片段時避開
        with ThreadPoolExecutor(4) as ex:
            all_cuts = dict(zip(have, ex.map(CS.scene_cuts, have)))
    for src, items in sp.seg.items():
        if not raw(src).exists():
            print(f"[skip] {src}: raw 檔不存在(尚未下載)")
            continue
        dur = probe_dur(src)
        for a, b, tags, note, over in items:
            b = min(b, dur - 0.1)
            safe = dict(sp.safe.get(src, {}), **over)
            crop = safe.pop("crop", None) or sp.crop.get(src) or detect_crop(src, a, b)
            rs = [r for a2, b2 in minus_ranges(a, b, sp.exclude.get(src, [])) for r in refine(sp, src, a2, b2, crop)]
            if not rs:
                print(f"  [drop] {src} {a}-{b} {tags}: 太短或整段黑")
                continue
            for s, e, m in rs:
                c = {"src": src, "start": s, "end": e, "tags": tags, "note": note}
                if sp.p("scene_cuts"):
                    c["cuts"] = [t for t in all_cuts[src] if s < t < e]
                if m < sp.p("dark"):
                    c["dark"] = True
                if crop:
                    c["crop"] = crop
                c.update(safe)
                if sp.section.get(src):
                    c["section_offset"] = sp.section[src]
                clips.append(c)
        print(f"{src}: dur={dur:.0f}")
    sp.out.parent.mkdir(parents=True, exist_ok=True)
    sp.out.write_text(json.dumps(clips, ensure_ascii=False, indent=1), encoding="utf-8")
    extra = ";片段內硬切 %d 處" % sum(len(c["cuts"]) for c in clips) if sp.p("scene_cuts") else ""
    print("wrote", sp.out, len(clips), "clips" + extra)
    return clips


def tag_lines(sp):
    cnt = Counter()
    if not sp.script.exists():
        return cnt
    for ln in sp.script.read_text(encoding="utf-8").splitlines():
        if not ln or ln[0] in "#@" or "|" not in ln:
            continue
        cnt[ln.split("|", 1)[0].strip()] += 1
    return cnt


def union_len(spans):
    spans = sorted(spans)
    tot, cur_e, cs = 0.0, None, None
    for s, e in spans:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                tot += cur_e - cs
            cs, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        tot += cur_e - cs
    return tot


def check(sp):
    clips = json.loads(sp.out.read_text(encoding="utf-8"))
    cnt = tag_lines(sp)
    black, fps, mx_src = sp.p("black"), sp.p("fps"), sp.p("max_per_src")
    ok = True
    print(f"{'tag':<13}{'lines':>5}{'need':>6}{'segs':>5}{'secs':>7}  result")
    for t in sp.tags:
        cs = [c for c in clips if t in c["tags"]]
        tot = sum(c["end"] - c["start"] for c in cs)
        need = cnt.get(t, 0) * sp.p("sec_per_line")
        if t in sp.min:
            n, s = sp.min[t]
            good = len(cs) >= n and tot >= s
            note = f"  (>= {n} 段/{s:.0f}s;句數x{sp.p('sec_per_line'):g}s={need:.0f}s)"
        else:
            good = len(cs) >= 3 and tot >= need
            note = f"  srcs={sorted({c['src'] for c in cs})}"
        ok &= good
        print(f"{t:<13}{cnt.get(t, 0):>5}{need:>6.0f}{len(cs):>5}{tot:>7.1f}  {'OK' if good else 'FAIL'}{note}")
    print("\n來源使用秒數(重疊只算一次,上限 %d):" % mx_src)
    by = defaultdict(list)
    for c in clips:
        by[c["src"]].append((c["start"], c["end"]))
    for s, spans in by.items():
        u = union_len(spans)
        bad = u > mx_src
        ok &= not bad
        print(f"  {s:<14}{u:6.1f}s {'FAIL' if bad else 'OK'}")
    print("\n片段起點亮度(0.5 秒內平均,<%d 視為黑):" % black)
    for c in clips:
        y = luma(sp, c["src"], c["start"], c["start"] + 0.5, c.get("crop"))
        v = float(y.mean()) if len(y) else 0
        if v < black or c["end"] <= c["start"]:
            ok = False
            print(f"  BLACK {c['src']} {c['start']}-{c['end']} lum={v:.1f}")
    print("\n片段內部黑畫面(連續 >=0.5 秒):")
    for c in clips:
        y = luma(sp, c["src"], c["start"], c["end"], c.get("crop"))
        run = mx = 0
        for v in y:
            run = run + 1 if v < black else 0
            mx = max(mx, run)
        if mx >= fps // 2:
            ok = False
            print(f"  BLACK-RUN {c['src']} {c['start']}-{c['end']} {mx / fps:.2f}s")
    print("\n全部達標" if ok else "\n有未達標項目")
    return ok


def grab(src, t, crop=None, w=320):
    """來源在 t 秒的一格(PIL Image,去黑邊後縮成寬 w);失敗回 None"""
    from PIL import Image
    vf = (f"crop={crop}," if crop else "") + f"scale={w}:-2"
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(raw(src)), "-vf", vf,
                        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB") if r.stdout else None


def contact_sheet(items, out, cols=6, w=320):
    """items = [(src, t, crop, label, safe_dict)];每格畫標籤,有 top/bottom 就畫紅線(線外是會被推出畫面的區域)"""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.load_default(size=14)
    frames = []
    for src, t, crop, label, safe in items:
        im = grab(src, t, crop, w) or Image.new("RGB", (w, w * 9 // 16), (60, 0, 0))
        d = ImageDraw.Draw(im)
        for k in ("top", "bottom"):
            if k in safe:
                y = int(im.height * safe[k])
                d.line([(0, y), (im.width, y)], fill=(255, 0, 0), width=2)
        d.rectangle([0, 0, im.width, 18], fill=(0, 0, 0))
        d.text((3, 1), label, fill=(255, 255, 0), font=font)
        frames.append(im)
    h = max(f.height for f in frames)
    rows = (len(frames) + cols - 1) // cols
    sheet_im = Image.new("RGB", (cols * w, rows * h), (0, 0, 0))
    for i, f in enumerate(frames):
        sheet_im.paste(f, ((i % cols) * w, (i // cols) * h))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sheet_im.save(out, quality=88)
    print("wrote", out, len(frames), "frames")


def sheet(sp, argv):
    src, a, b, step = argv[0], float(argv[1]), float(argv[2]), float(argv[3])
    out = argv[4] if len(argv) > 4 else P.TMP / "clips_sheet" / f"{src}_{int(a)}_{int(b)}.jpg"
    crop = sp.crop.get(src) if sp else None
    ts = [a + i * step for i in range(int((b - a) / step) + 1)]
    contact_sheet([(src, t, crop, f"{src[:6]} {t:.1f}", {}) for t in ts], out)


def _safe_of(c):
    return {k: c[k] for k in ("top", "bottom") if k in c}


def preview(sp, outdir, nf=1):
    """每標籤一張:每個片段取中間一格(nf>1 取等分 nf 格,選片時查鏡頭內容);用片段檔的最終起訖(含自動修過的黑場與 crop)"""
    clips = json.loads(sp.out.read_text(encoding="utf-8"))
    for t in sp.tags:
        cs = [c for c in clips if t in c["tags"]]
        items = []
        for c in cs:
            for i in range(nf):
                tt = c["start"] + (c["end"] - c["start"]) * (i + 0.5) / nf
                items.append((c["src"], tt, c.get("crop"),
                              f"{c['src'][:6]} {tt:.1f} [{c['start']}-{c['end']}]" + (" D" if c.get("dark") else ""), _safe_of(c)))
        if items:
            contact_sheet(items, outdir / (f"clips_{t}.jpg" if nf == 1 else f"clips_{t}_x{nf}.jpg"), cols=6 if nf == 1 else 3)


def overview(sp, outdir):
    """每支來源一張總覽(每個片段取中間一格,寬 240,標出起訖秒):<outdir>/clips_<src>.jpg"""
    clips = json.loads(sp.out.read_text(encoding="utf-8"))
    for src in sp.seg:
        cs = [c for c in clips if c["src"] == src]
        if cs:
            items = [(src, (c["start"] + c["end"]) / 2, c.get("crop"),
                      f"{c['start']:.0f}-{c['end']:.0f}" + (" D" if c.get("dark") else ""), _safe_of(c)) for c in cs]
            contact_sheet(items, outdir / f"clips_{src}.jpg", cols=8, w=240)


def main(argv=None):
    ap = argparse.ArgumentParser(description="影片片段共用引擎(見檔頭)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--spec")
    ap.add_argument("--out")
    ap.add_argument("--outdir")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--overview", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--nf", type=int, default=1)
    ap.add_argument("--sheet", nargs="+", metavar="SRC START END STEP [OUT]")
    a = ap.parse_args(argv)
    sp = Spec(a.tag, a.spec, a.out)
    outdir = Path(a.outdir) if a.outdir else P.output_dir(a.tag)
    if a.sheet:
        sheet(sp, a.sheet)
    elif a.check:
        return 0 if check(sp) else 1
    elif a.overview:
        overview(sp, outdir)
    elif a.preview:
        preview(sp, outdir, a.nf)
    else:
        build(sp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
