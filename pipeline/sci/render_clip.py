"""科普頻道場景算圖:pipeline\\sci\\stage.html 載入 scenes\\<scene>.js,每 0.1 秒 seek 一張 PNG,合成 mp4 與總覽圖。

用法:python -X utf8 pipeline\\sci\\render_clip.py <scene> --dur 3 --hue 46 --params "{json}" --out <name> [--t0 0] [--frames-only] [--portrait]
輸出:tmp\\<name>\\f_000.png.. → output\\channel\\<name>.mp4(10fps 輸入、30fps 輸出)、<name>_strip.png(10 欄,每格寬 384)
--frames-only 只出 PNG 序列(合成正片用)。--portrait 直式 1080x1920(版面常數見 kit.js 的 LAYOUT.portrait)。每格同時量紙片外框並印檢查摘要(出界、安全邊界、字幕帶、淨空區、字牌與鴿子重疊)。
"""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402
from channel_sheet import font_css  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

FPS = 10
VIEW = {False: (1920, 1080), True: (1080, 1920)}   # 橫/直式視窗尺寸;檢查用的邊距與字幕帶讀 kit.js 的 Kit.L
SCI = paths.ROOT / "pipeline" / "sci"


def build_html(scene, portrait=False):
    html = (SCI / "stage.html").read_text(encoding="utf-8").replace("/*FONTS*/", font_css())
    if portrait:                                     # 舞台尺寸 1920x1080 → 1080x1920
        html = (html.replace("width:1920px;height:1080px", "width:1080px;height:1920px")
                .replace('width="1920" height="1080" viewBox="0 0 1920 1080"', 'width="1080" height="1920" viewBox="0 0 1080 1920"'))
    for tag, f in (("/*PIGEON_JS*/", SCI / "pigeon.js"), ("/*KIT_JS*/", SCI / "kit.js"), ("/*CHARTS_JS*/", SCI / "charts.js"),
                   ("/*SCENE_JS*/", SCI / "scenes" / f"{scene}.js")):
        html = html.replace(tag, f.read_text(encoding="utf-8"))
    # 各片的圖解庫 props_<片名>.js 全部載入(各自掛在 window.Props<片名>,互不相干)
    props = "\n".join(f.read_text(encoding="utf-8") for f in sorted(SCI.glob("props_*.js")))
    # 場景模板(F4-0):tpl_common.js 先載,其餘 tpl_<名>.js 各自掛 window.Tpl.<名>
    tpls = [SCI / "tpl_common.js"] + [f for f in sorted(SCI.glob("tpl_*.js")) if f.name != "tpl_common.js"]
    tpl = "\n".join(f.read_text(encoding="utf-8") for f in tpls if f.exists())
    return html.replace("/*PROPS_JS*/", props).replace("/*TPL_JS*/", tpl)


def hit(b, z):
    return b[0] < z[2] and b[2] > z[0] and b[1] < z[3] and b[3] > z[1]


def check(rows, meta, L, tpl=False):
    """rows: [(t, [外框...], same)];回傳摘要行與是否通過。外框含描邊;陰影另加(右 5u、下 6u)。
    tpl=True(scenes\\tpl.js 模板場景)另查「鴿子間距」:每片內容紙片(鴿子與襯底以外、已進場)與鴿子外框
    水平距 ≥ 40(直式 24)或垂直距 ≥ 24 才算分開(F4-0c;非模板場景不查)。"""
    W, H, SAFE, SUB_BAND, MG = L["W"], L["H"], L["SAFE"], L["SUB_BAND"], L["margin"]   # MG = [左,上,右,下]
    bad = {"出界": [], "邊距<80": [], "字幕帶": [], "淨空區": [], "字牌壓鴿子": [], "非純函式": []}
    if tpl:
        bad["鴿子間距"] = []
    GX, GY = (40 if W > H else 24), 24
    gap = {"橫": (1e9, None), "直": (1e9, None)}
    margin, sides, heights = (1e9, None), [], []
    for t, els, same in rows:
        if not same:
            bad["非純函式"].append(f"{t:.1f}")
        for e in els:
            tag = f"{t:.1f}:{e['k']}{e['id']}"
            box = (e["x0"], e["y0"], e["x1"], e["y1"])
            full = (e["x0"], e["y0"], e["x1"] + 5 * e["u"], e["y1"] + 6 * e["u"])
            if hit(full, (0, SUB_BAND[0], W, SUB_BAND[1])):
                bad["字幕帶"].append(tag)
            if any(hit(full, z) for z in meta.get("clear", [])):
                bad["淨空區"].append(tag)
            if e["enter"]:
                continue
            if full[0] < 0 or full[1] < 0 or full[2] > W or full[3] > H:
                bad["出界"].append(tag)
            # 各邊離畫面邊的距離減去該邊下限,再加回 SAFE;四邊下限都是 SAFE 時即「最小邊距」,小於 SAFE 即未過
            m = min(box[0] - MG[0], box[1] - MG[1], W - MG[2] - box[2], H - MG[3] - box[3]) + SAFE
            if m < margin[0]:
                margin = (m, tag)
            if m < SAFE - 0.01:
                bad["邊距<80"].append(tag)
            if e["k"] == "pigeon":
                heights.append((box[3] - box[1], t))
        if tpl:
            for p in (e for e in els if e["k"] == "pigeon"):
                for e in (x for x in els if x["k"] not in ("pigeon", "ground") and not x["enter"]):
                    dx = max(e["x0"] - p["x1"], p["x0"] - e["x1"])
                    dy = max(e["y0"] - p["y1"], p["y0"] - e["y1"])
                    side, v = ("橫", dx) if dx >= GX else ("直", dy)
                    if v < gap[side][0]:
                        gap[side] = (v, f"{t:.1f}:{e['k']}{e['id']}")
                    if dx < GX and dy < GY:
                        bad["鴿子間距"].append(f"{t:.1f}:{e['k']}{e['id']}")
        if t + 1e-6 >= meta.get("noOverlapFrom", 1e9):
            pg = [e for e in els if e["k"] == "pigeon"]
            for a in (e for e in els if e["k"] == "tile"):
                if any(hit((a["x0"], a["y0"], a["x1"], a["y1"]), (p["x0"], p["y0"], p["x1"], p["y1"])) for p in pg):
                    bad["字牌壓鴿子"].append(f"{t:.1f}:{a['id']}")
    last = rows[-1][1]
    sides = [e["side"] for e in last if e["k"] == "tile"]
    out = []
    if sides:
        out.append(f"字牌 {len(sides)} 張,單牌邊長 {min(sides):.1f}–{max(sides):.1f}px(末格)")
    if heights:
        hmax, hlast = max(heights), heights[-1]
        out.append(f"鴿子高 進場後首格 {heights[0][0]:.0f}px({heights[0][0] / H:.1%},t={heights[0][1]:.1f})")
        out.append(f"鴿子高 最大 {hmax[0]:.0f}px({hmax[0] / H:.1%},t={hmax[1]:.1f})、末格 {hlast[0]:.0f}px({hlast[0] / H:.1%})")
    out.append(f"最小邊距 {margin[0]:.1f}px({margin[1]});進場中的紙片不計邊距與出界")
    if tpl and any(v[1] for v in gap.values()):
        out.append("內容與鴿子最小間距 " + "、".join(f"{k} {v[0]:.1f}px({v[1]})" for k, v in gap.items() if v[1])
                   + f"(下限 橫 {GX}/直 {GY})")
    ok = True
    for name, items in bad.items():
        if items:
            ok = False
            out.append(f"未過 {name} {len(items)} 筆:{'、'.join(items[:6])}")
    out.append("檢查:" + ("全部通過" if ok else "未過"))
    return out, ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--dur", type=float, default=3.0)
    ap.add_argument("--hue", type=float, default=46)
    ap.add_argument("--params", default="{}")
    ap.add_argument("--out")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--frames-only", action="store_true")
    ap.add_argument("--portrait", action="store_true")
    a = ap.parse_args()
    name = a.out or a.scene
    if not re.fullmatch(r"[\w-]+", name) or not re.fullmatch(r"[\w-]+", a.scene):
        sys.exit("scene 與 --out 只能用英數、底線、連字號")
    raw = Path(a.params[1:]).read_text(encoding="utf-8") if a.params.startswith("@") else a.params   # @檔案 = 從檔讀 json
    params = {"hue": a.hue, "dur": a.dur, **json.loads(raw)}
    if a.portrait:
        params["portrait"] = True
    W, H = VIEW[bool(a.portrait)]
    n = round(a.dur * FPS)
    frames = paths.TMP / name
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    out_dir = paths.OUTPUT / "channel"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = paths.TMP / f"stage_{name}.html"
    tmp.write_text(build_html(a.scene, a.portrait), encoding="utf-8")
    errors, rows = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.add_init_script(f"window.__PARAMS = {json.dumps(params, ensure_ascii=False)};")
        pg.goto(tmp.as_uri())
        pg.wait_for_function("window.__done===true")
        font = pg.evaluate("({st:[...document.fonts].filter(f=>f.family.replace(/\"/g,'')==='GenSen').map(f=>f.status),"
                           "ok:document.fonts.check('64px \"GenSen\"','ChannelC?')})")
        meta = pg.evaluate("Scene.meta ? Scene.meta(PARAMS) : {}")
        L = pg.evaluate("Kit.L")
        if (L["W"], L["H"]) != (W, H):
            sys.exit(f"版面不符:kit.js 的 LAYOUT 是 {L['W']}x{L['H']},視窗是 {W}x{H}")
        # 模板場景(scenes\tpl.js)算圖前先跑 check:錯誤 → 印「模板錯誤」並以代碼 2 結束;「警告」開頭的只印出
        chk = pg.evaluate("Scene.check ? Scene.check(PARAMS) : []") or []
        for m in chk:
            print(("  模板" if m.startswith("警告") else "模板錯誤:") + m)
        if any(not m.startswith("警告") for m in chk):
            b.close()
            sys.exit(2)
        for i in range(n):
            t = round(a.t0 + i / FPS, 1)
            r = pg.evaluate("(t)=>{seek(t);return {els:measure(),same:same(t)}}", t)
            rows.append((t, r["els"], r["same"]))
            pg.screenshot(path=str(frames / f"f_{i:03d}.png"))
        b.close()
    print(f"{a.scene}: {n} 格 t={a.t0:.1f}–{a.t0 + a.dur:.1f} → {paths.rel(frames)};console 錯誤 {len(errors)};GenSen {font['st']} check={font['ok']}")
    for e in errors[:5]:
        print("  ", e)
    lines, ok = check(rows, meta, L, a.scene == "tpl")
    for line in lines:
        print("  " + line)
    if not a.frames_only:
        src = ["-framerate", str(FPS), "-i", str(frames / "f_%03d.png")]
        mp4 = out_dir / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *src, "-vf", "fps=30,format=yuv420p",
                        "-c:v", "libx264", "-crf", "18", "-an", str(mp4)], check=True)
        strip = out_dir / f"{name}_strip.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *src, "-vf", f"scale=384:-1,tile=10x{math.ceil(n / 10)}",
                        "-frames:v", "1", str(strip)], check=True)
        print(f"  → {paths.rel(mp4)}、{paths.rel(strip)}")
    if errors or not ok or font["st"] != ["loaded"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
