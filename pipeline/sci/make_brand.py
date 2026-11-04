"""「ChannelC」品牌圖一個指令出圖:brand.js → output\brand\{avatar_A,avatar_B,banner_A,banner_B}.png。

用法:python -X utf8 pipeline\sci\make_brand.py
avatar 800x800(內切圓 80% = 半徑 320 內放文字/印章)、banner 2560x1440(Logo 與副標須在正中 1546x423 安全區內)。
檢查:逐組(只顯示該組、透明底)截圖量墨跡外框(像素 alpha);avatar 另以全部不透明像素到圓心的最大距離驗 ≤ 320;
banner 驗 logo、副標、燒瓶外框在安全區內。縮圖存 tmp\brand\:avatar 98/36 圓形遮罩、banner 安全區裁切與 1060 寬。
結束碼:0 通過;1 檢查未過。"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402
from channel_sheet import font_css  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
import numpy as np  # noqa: E402

SCI = Path(__file__).resolve().parent
OUT = paths.OUTPUT / "brand"
TMPD = paths.TMP / "brand"
NAMES = ("avatar_A", "avatar_B", "banner_A", "banner_B")
AV_R = 800 / 2 * 0.8          # 內切圓 80% 半徑
THR = 24                      # 墨跡判定:alpha > THR


def html():
    return ("<!doctype html><html><head><meta charset='utf-8'><style>" + font_css() +
            "\n*{margin:0}html,body{background:transparent}</style></head><body><svg id='s' xmlns='http://www.w3.org/2000/svg'></svg><script>" +
            (SCI / "brand.js").read_text(encoding="utf-8") + "</script></body></html>")


def ink(png_bytes):
    a = np.array(Image.open(io.BytesIO(png_bytes)).convert("RGBA"))[:, :, 3]
    return a > THR


def bbox(m):
    ys, xs = np.where(m)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else None


def circle_mask(im, d):
    im = im.convert("RGB").resize((d, d), Image.LANCZOS).convert("RGBA")
    k = 8
    mk = Image.new("L", (d * k, d * k), 0)
    ImageDraw.Draw(mk).ellipse((0, 0, d * k - 1, d * k - 1), fill=255)
    im.putalpha(mk.resize((d, d), Image.LANCZOS))
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TMPD.mkdir(parents=True, exist_ok=True)
    stage = TMPD / "stage_brand.html"
    stage.write_text(html(), encoding="utf-8")
    fails, errs = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        for name in NAMES:
            pg = b.new_page(viewport={"width": 800, "height": 800})
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(stage.as_uri())
            d = pg.evaluate("(()=>{const d=Brand.draw('" + name + "');const s=document.getElementById('s');"
                            "s.setAttribute('width',d.w);s.setAttribute('height',d.h);s.setAttribute('viewBox','0 0 '+d.w+' '+d.h);"
                            "s.innerHTML=d.svg;return {w:d.w,h:d.h}})()")
            pg.set_viewport_size({"width": d["w"], "height": d["h"]})
            pg.evaluate("document.fonts.load('64px \"GenSen\"','ChannelC認真那些的事?')")
            pg.wait_for_function("document.fonts.check('64px \"GenSen\"','ChannelC')")
            groups = pg.evaluate("[...document.querySelectorAll('[data-g]')].map(g=>g.dataset.g)")
            boxes, allm = {}, None
            for g in groups:
                if g in ("bg", "deco"):
                    continue
                pg.evaluate(f"document.querySelectorAll('[data-g]').forEach(e=>e.style.display=e.dataset.g==='{g}'?'':'none')")
                m = ink(pg.screenshot(omit_background=True))
                boxes[g] = bbox(m)
                allm = m if allm is None else (allm | m)
            pg.evaluate("document.querySelectorAll('[data-g]').forEach(e=>e.style.display='')")
            pg.screenshot(path=str(OUT / f"{name}.png"))
            pg.close()
            im = Image.open(OUT / f"{name}.png").convert("RGB")
            assert im.size == (d["w"], d["h"]), im.size
            if name.startswith("avatar"):
                ys, xs = np.where(allm)
                dist = float(np.hypot(xs + 0.5 - 400, ys + 0.5 - 400).max())
                u = (min(v[0] for v in boxes.values()), min(v[1] for v in boxes.values()), max(v[2] for v in boxes.values()), max(v[3] for v in boxes.values()))
                print(f"{name}: 外框 {u} ({u[2]-u[0]}x{u[3]-u[1]});中心偏移 ({(u[0]+u[2])/2-400:+.0f},{(u[1]+u[3])/2-400:+.0f});最遠墨跡距圓心 {dist:.0f}px(上限 {AV_R:.0f} = 圓 80%)")
                if dist > AV_R:
                    fails.append(f"{name} 墨跡超出內切圓 80%:{dist:.0f} > {AV_R:.0f}")
                circle_mask(im, 98).save(TMPD / f"{name}_98.png")
                circle_mask(im, 36).save(TMPD / f"{name}_36.png")
            else:
                sx, sy, sw, sh = 507, 508.5, 1546, 423          # 安全區(水平垂直置中)
                S = (sx, sy, sx + sw, sy + sh)
                parts = []
                for g, v in boxes.items():
                    ok = v[0] >= S[0] and v[1] >= S[1] and v[2] <= S[2] and v[3] <= S[3]
                    parts.append(f"{g} {v}({v[2]-v[0]}x{v[3]-v[1]}){'' if ok else ' 出界'}")
                    if not ok:
                        fails.append(f"{name} {g} 外框 {v} 超出安全區 {S}")
                u = (min(v[0] for v in boxes.values()), min(v[1] for v in boxes.values()), max(v[2] for v in boxes.values()), max(v[3] for v in boxes.values()))
                print(f"{name}: " + "、".join(parts) + f";整組 {u},中心 ({(u[0]+u[2])/2:.0f},{(u[1]+u[3])/2:.0f})(安全區中心 1280,720)")
                im.crop((507, 508, 507 + 1546, 508 + 424)).save(TMPD / f"{name}_safe.png")
                im.resize((1060, round(1060 * 1440 / 2560)), Image.LANCZOS).save(TMPD / f"{name}_1060.png")
        b.close()
    if errs:
        fails.append(f"console 錯誤 {errs[:3]}")
    print(f"→ {paths.rel(OUT)}(縮圖 {paths.rel(TMPD)})")
    for f in fails:
        print("未過:" + f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
