"""一次產生動畫素材庫到 <素材根>\\anim\\;已存在且參數相同(manifest 雜湊)則略過。

用法(專案根執行):
  python -X utf8 pipeline\\anim_make.py                 # 產生所有素材
  python -X utf8 pipeline\\anim_make.py --test          # 另產 output\\anim_test\\overview.png 與 demo.mp4
  python -X utf8 pipeline\\anim_make.py --force --only emoji/clap
  python -X utf8 pipeline\\anim_make.py --title "第二章 神的資格"   # 額外產生帶標題的轉場 anim\\trans\\trans_title_<hash>.mov
產出清單與格數見 anim\\manifest.json。與 build.py 無關。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anim_lib as A
import paths as P

ROOT_DEFAULT = str(P.ROOT)

TIMELINE_POINTS = [("1998", "浣熊市毀滅", "#E53935"),
                   ("2001", "收養葛蕾絲、研發解藥", "#F2F2F2"),
                   ("2006", "「我有資格當神」", "#B3001B")]
TIMELINE_Q = (1, 2)
STAMPS = {"unverified": "未經證實", "maybe_not_certain": "可能 ≠ 確定"}
DEMO_TITLE = "標題示範"


def _hash(obj):
    return hashlib.md5(json.dumps([A.LIB_VERSION, obj], ensure_ascii=False, sort_keys=True).encode("utf8")).hexdigest()[:12]


def _dir_bytes(p):
    return sum(os.path.getsize(os.path.join(p, f)) for f in os.listdir(p)) if os.path.isdir(p) else 0


def _item(anim, rel, frames, fps=A.FPS, alpha=True, png_dir=None, tp=None, **extra):
    """寫出 mov(或 mp4)與選用 PNG 序列,回傳 manifest item。rel 不含副檔名。"""
    path = os.path.join(anim, rel + (".mov" if alpha else ".mp4"))
    A.save_mov(frames, path, fps, alpha)
    it = {"name": rel.replace("\\", "/"), "path": rel.replace("\\", "/") + (".mov" if alpha else ".mp4"),
          "frames": len(frames), "w": frames[0].shape[1], "h": frames[0].shape[0], "fps": fps,
          "alpha": alpha, "bytes": os.path.getsize(path),
          "tp": tp or [int(len(frames) * f) for f in (0.1, 0.35, 0.65, 0.97)]}
    if png_dir:
        A.save_png_seq(frames, os.path.join(anim, png_dir))
        it["png_dir"] = png_dir.replace("\\", "/"); it["png_bytes"] = _dir_bytes(os.path.join(anim, png_dir))
    it.update(extra)
    return it


def build_units(anim, titles):
    """每個 unit = (unit_name, params, builder)。builder() 回傳 manifest items。"""
    units = []
    cache = os.path.join(anim, "_src")
    for name, (cp, label) in A.EMOJI.items():
        for sec in (2, 3):
            def b(name=name, sec=sec, label=label):
                fr = A.make_emoji(name, float(sec), cache)
                n = len(fr)
                rel = f"emoji\\{name}_{sec}s"
                return [_item(anim, rel, fr, png_dir=rel, tp=[1, 3, n // 2, n - 4], label=label)]
            units.append((f"emoji/{name}_{sec}s", {"cp": cp, "sec": sec}, b))
    units.append(("trans_wipe", {}, lambda: [_item(anim, "trans\\trans_wipe", A.make_wipe(), tp=[3, 6, 7, 11], label="轉場 wipe 0.5s")]))
    units.append(("trans_glitch", {"seconds": 0.35}, lambda: [_item(anim, "trans\\trans_glitch", A.make_glitch(), tp=[1, 3, 5, 8], label="轉場 glitch 0.35s(疊加版)")]))
    for t in [DEMO_TITLE] + list(titles):
        key = "demo" if t == DEMO_TITLE else hashlib.md5(t.encode("utf8")).hexdigest()[:6]
        units.append((f"trans_title_{key}", {"text": t},
                      lambda t=t, key=key: [_item(anim, f"trans\\trans_title_{key}", A.make_title_wipe(t),
                                                  tp=[6, 10, 20, 37], label=f"轉場 title wipe「{t}」1.3s")]))
    for bg in ("alpha", "dark"):
        def b(bg=bg):
            segs = A.make_timeline(TIMELINE_POINTS, TIMELINE_Q, bg=bg)
            items = []
            for s in segs:
                nm = f"timeline\\timeline{'_dark' if bg == 'dark' else ''}_{s['name']}"
                items.append(_item(anim, nm, s["frames"], alpha=(bg == "alpha"), hold=s["hold"], loop=s["loop"],
                                   label=f"timeline {s['name']}" + ("(深色底)" if bg == "dark" else "")))
            return items
        units.append((f"timeline_{bg}", {"points": TIMELINE_POINTS, "q": TIMELINE_Q}, b))
    units.append(("puzzle", {"seconds": 2.5}, lambda: [_item(anim, "puzzle\\puzzle", A.make_puzzle(), tp=[12, 30, 50, 74], label="puzzle 2.5s")]))
    for key, text in STAMPS.items():
        units.append((f"stamp_{key}", {"text": text, "hold": 1.0},
                      lambda key=key, text=text: [_item(anim, f"stamp\\stamp_{key}", A.make_stamp(text, hold=1.0),
                                                        tp=[2, 4, 8, 47], label=f"stamp「{text}」0.6s+凍結1.0s")]))
    return units


def build(root, force=False, only=None, titles=()):
    anim = os.path.join(root, "anim")
    os.makedirs(anim, exist_ok=True)
    mpath = os.path.join(anim, "manifest.json")
    man = json.load(open(mpath, encoding="utf8")) if os.path.exists(mpath) else {}
    for uname, params, builder in build_units(anim, titles):
        if only and only not in uname:
            continue
        h = _hash(params)
        ent = man.get(uname)
        if (not force and ent and ent["hash"] == h and
                all(os.path.exists(os.path.join(anim, it["path"])) for it in ent["items"])):
            print("略過(已存在):", uname); continue
        t = time.time()
        items = builder()
        man[uname] = {"hash": h, "items": items}
        json.dump(man, open(mpath, "w", encoding="utf8"), ensure_ascii=False, indent=1)
        print(f"產生 {uname}: {sum(i['frames'] for i in items)} 格 ({time.time() - t:.1f}s)")
    return man


# ------------------------------------------------------------------ 驗收:overview / demo
def _pick_dark_screenshot(root):
    d = os.path.join(root, "images"); best = None
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(".png") or f.startswith("zh_") or f.startswith("src_"):
            continue
        try:
            im = Image.open(os.path.join(d, f)).convert("L"); im.thumbnail((160, 90))
            m = float(np.asarray(im).mean())
        except Exception:
            continue
        if best is None or m < best[0]:
            best = (m, f)
    return os.path.join(d, best[1])


def _cover(im, w=A.W, h=A.H):
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s + .5), int(im.height * s + .5)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def _checker(w, h, t=32):
    yy, xx = np.mgrid[0:h, 0:w]
    v = np.where(((xx // t) + (yy // t)) % 2 == 0, 150, 108).astype(np.uint8)
    return Image.fromarray(np.stack([v, v, v, np.full_like(v, 255)], -1), "RGBA")


def _over(bg, fr, x=0, y=0):
    """straight-alpha ndarray 疊到 bg(PIL RGBA)。"""
    layer = Image.new("RGBA", bg.size, (0, 0, 0, 0)); layer.paste(Image.fromarray(fr, "RGBA"), (x, y))
    return Image.alpha_composite(bg, layer)


def overview(root, man, shot, out):
    anim = os.path.join(root, "anim")
    bg_shot = _cover(Image.open(shot).convert("RGBA"))
    items = [it for u in man.values() for it in u["items"]]
    items = [it for it in items if it["alpha"]]
    LABEL_W, GAP = 300, 6
    rows = []     # (PIL image)
    f_lbl = A.font(26)
    for it in items:
        frames = dict(A.read_frames(os.path.join(anim, it["path"]), it["w"], it["h"], set(it["tp"])))
        if it["w"] == 360:   # emoji:8 格同列(前 4 棋盤格、後 4 深色截圖),格寬 250
            cs = 250
            row = Image.new("RGB", (LABEL_W + 8 * (cs + GAP), cs + 4), (24, 24, 28))
            ImageDraw.Draw(row).multiline_text((10, 20), f"{it['name'].split('/')[-1]}\n{it['frames']} 格\n{it.get('label', '')}",
                                               font=f_lbl, fill=(255, 255, 255), spacing=8)
            for k, idx in enumerate(it["tp"]):
                for j, bgi in enumerate((_checker(360, 360, 24), bg_shot.crop((780, 220, 1140, 580)))):
                    cell = _over(bgi, frames[idx]).resize((cs, cs), Image.LANCZOS).convert("RGB")
                    row.paste(cell, (LABEL_W + (j * 4 + k) * (cs + GAP), 2))
            rows.append(row)
        else:                # 1920x1080:標題列 + 棋盤格列 + 截圖列
            cw, ch = 570, 321
            tot_w = 4 * (cw + GAP) + GAP
            blk = Image.new("RGB", (tot_w, 34 + 2 * (ch + GAP)), (24, 24, 28))
            ImageDraw.Draw(blk).text((8, 2), f"{it['name']}  {it['frames']} 格 ({it['frames'] / it['fps']:.2f}s)  {it.get('label', '')}",
                                     font=f_lbl, fill=(255, 255, 255))
            for j, bgi in enumerate((_checker(A.W, A.H, 48), bg_shot)):
                for k, idx in enumerate(it["tp"]):
                    cell = _over(bgi, frames[idx]).resize((cw, ch), Image.LANCZOS).convert("RGB")
                    blk.paste(cell, (GAP + k * (cw + GAP), 34 + j * (ch + GAP)))
            rows.append(blk)
    W_all = max(r.width for r in rows)
    H_all = sum(r.height + 4 for r in rows)
    sheet = Image.new("RGB", (W_all, H_all), (10, 10, 12)); y = 0
    for r in rows:
        sheet.paste(r, (0, y)); y += r.height + 4
    assert sheet.width <= 2400, sheet.width
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    return sheet.size


def demo(root, man, shot, out):
    import anim_lib as L
    anim = os.path.join(root, "anim")
    bg = _cover(Image.open(shot).convert("RGBA"))
    bg_np = np.asarray(bg.convert("RGB"))
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080", "-r", "30", "-i", "-",
           "-vf", "scale=1280:720:flags=lanczos", "-c:v", "libx264", "-crf", "25", "-preset", "medium",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    f_lbl = A.font(34)

    def label(img, text):
        d = ImageDraw.Draw(img); d.text((30, 24), text, font=f_lbl, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
        return img

    def emit(img):
        p.stdin.write(np.asarray(img.convert("RGB")).tobytes())

    def gap():
        for _ in range(9):
            emit(bg)

    # 真正的 RGB 分離+切片位移(glitch_vf)示範:對背景靜圖跑 ffmpeg filter
    gl_path = os.path.join(os.path.dirname(out), "_glitch_vf.mp4")
    bgpng = os.path.join(os.path.dirname(out), "_bg.png"); bg.convert("RGB").save(bgpng)
    fc = L.glitch_vf(0.3, 0.35)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", "1.0", "-i", bgpng, "-filter_complex", fc,
                    "-map", "[out]", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", gl_path], check=True)
    plan = []
    names = [k for k in man]
    def pick(pred):
        return [it for k in names for it in man[k]["items"] if pred(it)]
    plan += pick(lambda it: it["name"].startswith("emoji/") and it["name"].endswith("_2s"))
    plan += pick(lambda it: it["name"] in ("trans/trans_wipe", "trans/trans_title_demo", "trans/trans_glitch"))
    plan += [{"name": "glitch_vf(真正位移)", "special": gl_path}]
    plan += pick(lambda it: it["name"].startswith("timeline/timeline_") and it["alpha"])
    plan += pick(lambda it: it["name"] in ("puzzle/puzzle",) or it["name"].startswith("stamp/"))
    total = 0
    for it in plan:
        if "special" in it:
            for _, fr in A.read_frames(it["special"], A.W, A.H):
                emit(label(Image.fromarray(fr, "RGBA"), it["name"])); total += 1
        else:
            ox, oy = ((960 - 180, 400 - 180) if it["w"] == 360 else (0, 0))
            for _, fr in A.read_frames(os.path.join(anim, it["path"]), it["w"], it["h"]):
                emit(label(_over(bg, fr, ox, oy), it["name"])); total += 1
        gap(); total += 9
    p.stdin.close(); p.wait()
    return total / 30.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT_DEFAULT)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default=None, help="只處理名稱含此字串的 unit(如 emoji/clap、timeline)")
    ap.add_argument("--title", action="append", default=[], help="額外產生帶標題的 wipe(可重複)")
    ap.add_argument("--test", action="store_true", help="另產 output\\anim_test\\overview.png / demo.mp4")
    a = ap.parse_args()
    man = build(a.root, a.force, a.only, a.title)
    if a.test:
        shot = _pick_dark_screenshot(a.root)
        print("測試背景:", shot)
        out = str(P.OUTPUT / "anim_test")
        print("overview 尺寸:", overview(a.root, man, shot, os.path.join(out, "overview.png")))
        print("demo 秒數:", round(demo(a.root, man, shot, os.path.join(out, "demo.mp4")), 1))


if __name__ == "__main__":
    main()
