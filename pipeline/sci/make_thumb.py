"""科普頻道封面一個指令出圖(F4-1):tpl_thumb 模板 → output\\<tag>\\<tag>_thumb.png(1920x1080,deliver.py 認這個檔名)。

用法:python -X utf8 pipeline\\sci\\make_thumb.py --tag <tag> [--data <json路徑>]   (預設讀 <tag>\\thumb.json)
data 欄位見 tpl_thumb.js 開頭。流程:資料檢查(Tpl.thumb.check)→ 算圖 → 量外框做幾何檢查(安全區、右下淨空、字與鴿子/prop 重疊、鴿子佔高)
→ 縮成 320 寬後每行字高 ≥ 下限(主 33 / 副 18 / 補 15 px,= 1080 高時 200/110/90 的 1/6)。另存 246x138、168x94 縮圖到 tmp\\thumb_<tag>\\ 供人看。
結束碼:0 通過;1 幾何或縮小檢查未過;2 資料錯誤。"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402
from render_clip import build_html  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from PIL import Image  # noqa: E402

SAFE = (96, 54, 1824, 1026)          # 四邊 5%
CLEAR = (1632, 918, 1920, 1080)      # 右下角 15%(片長標籤)
PG_SHARE = (0.55, 0.72)              # 鴿子外框佔畫面高(§4.1 55–70%,外框含描邊多一點)
SMALL_W = 320
FLOOR_PX = (33, 18, 15)              # 320 寬下每行字高下限 = 200/110/90 ÷ 6
STROKE_PAD = {"thumbtext": (10, 10, 18, 19), "plate": (4, 4, 4, 4)}   # measure() 已含 2 的邊;描邊 12 與陰影 (8,9) 補上:左上右下


def hit(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--data")
    a = ap.parse_args()
    if not re.fullmatch(r"[\w-]+", a.tag):
        sys.exit("tag 只能用英數、底線、連字號")
    src = Path(a.data) if a.data else paths.ROOT / a.tag / "thumb.json"
    if not src.is_absolute():
        src = paths.ROOT / src
    data = json.loads(src.read_text(encoding="utf-8"))
    data.pop("說明", None)
    out = paths.OUTPUT / a.tag / f"{a.tag}_thumb.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    small_dir = paths.TMP / f"thumb_{a.tag}"
    small_dir.mkdir(parents=True, exist_ok=True)
    stage = paths.TMP / f"stage_thumb_{a.tag}.html"
    stage.write_text(build_html("tpl"), encoding="utf-8")
    params = {"tpl": "thumb", "hue": data.get("hue", 46), "dur": 0.1, "data": data}
    errs, fails = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script(f"window.__PARAMS = {json.dumps(params, ensure_ascii=False)};")
        pg.goto(stage.as_uri())
        pg.wait_for_function("window.__done===true")
        chk = pg.evaluate("Scene.check(PARAMS)") or []
        for m in chk:
            print(("  " if m.startswith("警告") else "資料錯誤:") + m)
        if any(not m.startswith("警告") for m in chk):
            b.close()
            sys.exit(2)
        r = pg.evaluate("()=>{seek(0);return {els:measure(),same:same(0),fs:[0,1,2].map(i=>{const g=document.querySelector('[data-id=\"tl'+i+'\"] text');"
                        "return g?+g.getAttribute('font-size'):0}),font:document.fonts.check('64px \"GenSen\"','ChannelC')}}")
        pg.screenshot(path=str(out))
        b.close()
    if errs or not r["font"] or not r["same"]:
        print(f"算圖異常:console 錯誤 {errs[:3]} GenSen={r['font']} 純函式={r['same']}")
        sys.exit(1)

    # 幾何檢查(外框單位 px)
    box = {}
    for e in r["els"]:
        pad = STROKE_PAD.get(e["k"], (0, 0, 0, 0))
        box[e["id"] or e["k"]] = (e["x0"] - pad[0], e["y0"] - pad[1], e["x1"] + pad[2], e["y1"] + pad[3], e["k"])
    texts = {k: v for k, v in box.items() if v[4] in ("thumbtext", "plate")}
    pigeon = box.get("p")
    if len(texts) != 3 or not pigeon:
        fails.append(f"物件數不對:字 {len(texts)} 行、鴿子 {'有' if pigeon else '無'}")
    else:
        for k, v in box.items():
            if not (v[0] >= SAFE[0] and v[1] >= SAFE[1] and v[2] <= SAFE[2] and v[3] <= SAFE[3]):
                fails.append(f"{k} 外框 ({v[0]:.0f},{v[1]:.0f},{v[2]:.0f},{v[3]:.0f}) 超出安全區 {SAFE}")
            if hit(v, CLEAR):
                fails.append(f"{k} 進入右下角淨空區 {CLEAR}")
        for k, v in texts.items():
            for o in ("p", "prop"):
                if o in box and hit(v, box[o]):
                    fails.append(f"字 {k} 與 {o} 外框重疊")
        share = (pigeon[3] - pigeon[1]) / 1080
        if not PG_SHARE[0] <= share <= PG_SHARE[1]:
            fails.append(f"鴿子外框佔畫面高 {share:.0%},不在 {PG_SHARE[0]:.0%}–{PG_SHARE[1]:.0%}")
        print(f"鴿子外框 ({pigeon[0]:.0f},{pigeon[1]:.0f},{pigeon[2]:.0f},{pigeon[3]:.0f}) 佔高 {share:.0%}、字區 x {min(v[0] for v in texts.values()):.0f}–{max(v[2] for v in texts.values()):.0f}")

    # 縮小檢查:320 寬(=1/6)後每行字高;另存兩個小圖
    im = Image.open(out).convert("RGB")
    assert im.size == (1920, 1080), im.size
    im.resize((SMALL_W, 180), Image.LANCZOS).save(small_dir / f"{a.tag}_320.png")
    im.resize((246, 138), Image.LANCZOS).save(small_dir / f"{a.tag}_246.png")
    im.resize((168, 94), Image.LANCZOS).save(small_dir / f"{a.tag}_168.png")
    s = SMALL_W / 1920
    names = ("主", "副", "補")
    parts = []
    for i, fs in enumerate(r["fs"]):
        h = fs * s
        parts.append(f"{names[i]} {h:.1f}px(下限 {FLOOR_PX[i]})")
        if h < FLOOR_PX[i]:
            fails.append(f"縮小檢查:{names[i]}文字 320 寬下字高 {h:.1f}px < {FLOOR_PX[i]}px")
    print("縮小檢查 320 寬:" + "、".join(parts) + f";字級 {r['fs']}")
    print(f"→ {paths.rel(out)}(小圖 {paths.rel(small_dir)})")
    for f in fails:
        print("未過:" + f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
