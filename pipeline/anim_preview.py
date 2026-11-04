"""動畫鏡頭靜態預覽:每個動畫鏡頭的每一步輸出一張 1920x1080 PNG(含光點星座背景),走 build.py 實際的算圖路徑。

用法(專案根執行):
  python -X utf8 pipeline\\anim_preview.py <script.json> <輸出資料夾> [--types versus,flow,list,timeline] [--all]
  python -X utf8 pipeline\\anim_preview.py <script.json> <輸出資料夾> --sheet   # 全片動畫總覽 sheet_NN.jpg(每張 9 格,960x540,三欄)+ anim_problems 異常
  python -X utf8 pipeline\\anim_preview.py --bars-demo <輸出資料夾>      # bars 單色五條 + 分組類別色兩案例 -> bars_sbi.png / bars_grouped.png,並印版面量測
預設每種類型只取第一個鏡頭;--all 取全部。檔名 <類型>_句<編號>_step<步>.png。
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anim_lib as AL
import build as B
import paths as P

STEP_FRAMES = 100        # 每一句給 3.3 秒,足夠任何一步播完


def render_run(run, tlmeta, media, out_dir, tag):
    parts = [dict(line=ln["idx"], frames=STEP_FRAMES, anim=ln["anim"]) for ln in run["lines"]]
    s = dict(parts=parts, f0=0, frames=STEP_FRAMES * len(parts), special="anim")
    frames = list(B._anim_layers(s, tlmeta, media, "alpha"))
    done = []
    for i, p in enumerate(parts):
        step = p["anim"].get("step", "all")
        if i and parts[i - 1]["anim"].get("step", "all") == step:
            continue
        k = (i + 1) * STEP_FRAMES - 1
        rgb = AL.over_star(frames[k], k / AL.FPS)
        name = f"{tag}_句{run['lines'][i]['idx']}_step{step}.png"
        Image.fromarray(rgb).save(out_dir / name)
        done.append(name)
    return done


BARS_SBI = dict(title="Sweet Baby Inc 掛名的遊戲", src="維基百科整理", items=[["2022", 3, "款"], ["2023", 9, "款"], ["2024", 5, "款"], ["2025", 4, "款"], ["2026", 4, "款"]])
BARS_GROUPED = dict(title="加入前後,陣營比例", groups=[
    dict(title="加入前", bars=[["聯盟", 60, "%", dict(color="alliance")], ["部落", 40, "%", dict(color="horde")]]),
    dict(title="加入後", bars=[["聯盟", 40, "%", dict(color="alliance")], ["部落", 60, "%", dict(color="horde")]])])


def bars_report(lay):
    """量測 bars 最終版面:條 y 範圍 / 間隔、最長條終點、最後一條下緣、強調條、文字框重疊與出界(用繪字墨跡 bbox)。"""
    boxes, bars = [], []
    for k in range(lay.n):
        pl = lay.place(k)
        bars.append(pl["bar"])
        for nm in ("label", "icon", "val"):
            if nm in pl:
                boxes.append((f"{nm}{k}", pl[nm][1]))
    for g in range(len(lay.gspr)):
        boxes.append((f"group{g}", lay.group_place(g)[1]))
    sb = AL.src_place(lay.src)[2] if lay.src else None
    gaps = [round(bars[i + 1][1] - bars[i][3], 1) for i in range(len(bars) - 1)]
    print("每條 y:", [(round(b[1]), round(b[3])) for b in bars], "相鄰間隔:", gaps)
    print("最長條終點 x:", max(b[2] for b in bars), "最後一條下緣 y:", bars[-1][3], "條厚/間隔:", lay.bh, lay.geo["gap"])
    print("強調條:", [lay.items[k][0] for k in range(lay.n) if lay.hi[k]])
    bad = [f"{a}/{b}" for i, (a, ba) in enumerate(boxes) for b, bb in boxes[i + 1:]
           if ba[0] < bb[2] and bb[0] < ba[2] and ba[1] < bb[3] and bb[1] < ba[3]]
    out = [n for n, b in boxes if b[0] < 0 or b[1] < 0 or b[2] > AL.W or b[3] > AL.H]
    print("文字框重疊:", bad or "無", "出界:", out or "無", "(共", len(boxes), "框)")
    if sb:
        hit = [n for n, b in boxes if b[0] < sb[2] and sb[0] < b[2] and b[1] < sb[3] and sb[1] < b[3]]
        print("src 框:", sb, "與內容重疊:", hit or "無", "(下緣上限", AL.BARS_BOTTOM_SRC, ")")
    print("數值框(數字加單位):", [tuple(lay.place(k)["val"][1]) for k in range(lay.n)])


def bars_demo(out_dir, media, names=("bars_sbi.png", "bars_grouped.png")):
    icon_root = str(media / "anim")
    for name, a in zip(names, (BARS_SBI, BARS_GROUPED)):
        items, groups = a.get("items"), a.get("groups")
        n = sum(len(g["bars"]) for g in groups) if groups else len(items)
        fr = AL.make_bars_step(a["title"], items, n, 0, title_in=True, bg="alpha", groups=groups, icon_root=icon_root, src=a.get("src"))
        k = len(fr) - 1
        Image.fromarray(AL.over_star(fr[k], k / AL.FPS)).save(out_dir / name)
        print("輸出", out_dir / name)
        bars_report(AL._BarsLayout(items, groups, icon_root, a.get("src")))


NEW_DEMOS = [
    ("cols_demo.png", dict(type="cols", title="Sweet Baby Inc 掛名的遊戲", src="維基百科整理",
                           items=[["2022", 3, "款"], ["2023", 9, "款"], ["2024", 5, "款"], ["2025", 4, "款"], ["2026", 4, "款"]])),
    ("share_demo.png", dict(type="share", title="陣營比例", rows=[
        dict(label="加入前", parts=[["聯盟", 60, "alliance"], ["部落", 40, "horde"]]),
        dict(label="加入後", parts=[["聯盟", 40, "alliance"], ["部落", 60, "horde"]])])),
    ("num_demo.png", dict(type="num", label="首月銷量", big="2,300 萬", compare="前作同期 1,800 萬", tone="up")),
]


def new_report(a):
    """cols / share / num 最終版面量測:內容邊界、文字框重疊與出界、版面問題(anim_problems)。"""
    lay = AL.new_layout(a)
    bb = lay.bounds
    boxes = list(lay.boxes)
    sb = AL.src_place(a["src"])[2] if a.get("src") else None
    if sb:
        boxes.append(("src", sb))
    bad = [f"{x}/{y}" for i, (x, bx) in enumerate(boxes) for y, by in boxes[i + 1:] if AL._hit(bx, by)]
    out = [n for n, b in boxes if b[0] < 0 or b[1] < 0 or b[2] > AL.W or b[3] > AL.H]
    print(f"[{a['type']}] 內容邊界 l={bb[0]} t={bb[1]} r={bb[2]} b={bb[3]}(左右離邊 {bb[0]}/{AL.W - bb[2]},下緣 {bb[3]})")
    if a["type"] == "cols":
        print("  字級: 標籤", AL.BARS_LABEL_FS, "數值", AL.BARS_VAL_FS, "強調", AL.BARS_VAL_FS_HI, "| 槽寬", round(lay.slot), "柱寬", round(lay.bw),
              "| 強調:", [lay.items[k][0] for k in range(lay.n) if lay.hi[k]])
        print("  標籤框:", [lay.place(k)["label"][1] for k in range(lay.n)])
    elif a["type"] == "share":
        print("  字級: 列標籤", AL.BARS_LABEL_FS, "段內數值", AL.SHARE_VAL_FS, "圖例", AL.SHARE_LEGEND_FS, "| 條厚/列距", lay.bh, lay.gap, "| 列 top", lay.tops)
        print("  顏色:", {k: v for k, v in lay.cmap.items()}, "| 數值框:", [[tuple(sg["bb"]) for sg in r if sg["show"]] for r in lay.segs])
    else:
        print("  字級: label", AL.NUM_LABEL_FS, "big", lay.size, "單位", round(lay.size * AL.NUM_UNIT_RATIO), "compare", AL.NUM_CMP_FS, "| count-up", lay.count)
        print("  框:", {n: tuple(b) for n, b in lay.boxes})
    print("  文字框重疊:", bad or "無", "出界:", out or "無", "| anim_problems:", AL.anim_problems(a) or "無")


def new_demo(out_dir):
    for name, a in NEW_DEMOS:
        t = a["type"]
        if t == "cols":
            fr = AL.make_cols_step(a["title"], a["items"], len(a["items"]), 0, title_in=True, bg="alpha", src=a.get("src"))
        elif t == "share":
            fr = AL.make_share_step(a["title"], a["rows"], len(a["rows"]), 0, title_in=True, bg="alpha", src=a.get("src"))
        else:
            fr = AL.make_num_step(a.get("label"), a["big"], a.get("compare"), a.get("tone"), None, 0, title_in=True, bg="alpha", src=a.get("src"))
        k = len(fr) - 1
        Image.fromarray(AL.over_star(fr[k], k / AL.FPS)).save(out_dir / name)
        print("輸出", out_dir / name)
        new_report(a)


SHEET_CELL = (960, 540)
SHEET_PER = 9          # 每張 3 欄 x 3 列
SHEET_ISSUES_MAX = 25  # 印出的異常項上限(輸出 30 行內)


def _last_frame(run, tlmeta, media):
    """該 run 所有動畫格(走 build 實際算圖路徑,每句 STEP_FRAMES 格)的最後一格疊星座背景;串流處理不整批存。"""
    parts = [dict(line=ln["idx"], frames=STEP_FRAMES, anim=ln["anim"]) for ln in run["lines"]]
    s = dict(parts=parts, f0=0, frames=STEP_FRAMES * len(parts), special="anim")
    last, k = None, -1
    for k, f in enumerate(B._anim_layers(s, tlmeta, media, "alpha")):
        last = f
    return AL.over_star(last, k / AL.FPS)


def sheet(script_arg, out_dir, media):
    """全片動畫總覽:每個動畫鏡頭取最後一格,縮成 960x540,三欄拼 sheet_01.jpg…(每張最多 9 格);並對每個鏡頭跑 anim_problems。"""
    from PIL import ImageDraw
    script = P.find(script_arg, P.REPO)
    lines = B.load_lines(script)
    secs, tlmeta = B.load_meta(script)
    runs = [r for r in B.group_runs(lines) if r["key"][0] == "anim"]
    cw, ch = SHEET_CELL
    cells, issues = [], []
    fnt = AL.font(30)
    for run in runs:
        a = run["lines"][0]["anim"]
        i0, i1 = run["lines"][0]["idx"], run["lines"][-1]["idx"]
        label = f"句{i0}" + (f"-{i1}" if i1 != i0 else "") + f" {a['type']}"
        try:
            probs = AL.anim_problems(a, B.tl_meta(a, tlmeta).get("points"))
        except Exception as e:      # 版面算不出來也算異常
            probs = [f"{type(e).__name__}: {e}"]
        issues += [f"{label}: {p}" for p in probs]
        im = Image.fromarray(_last_frame(run, tlmeta, media)).resize(SHEET_CELL, Image.LANCZOS).convert("RGBA")
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        l, t, r, b = d.textbbox((0, 0), label, font=fnt)
        d.rectangle([0, 0, r - l + 24, b - t + 20], fill=(0, 0, 0, 150))
        d.text((12 - l, 10 - t), label, font=fnt, fill=(255, 255, 255, 255))
        cells.append(Image.alpha_composite(im, ov).convert("RGB"))
    names = []
    for n, i in enumerate(range(0, len(cells), SHEET_PER), 1):
        grp = cells[i:i + SHEET_PER]
        sh = Image.new("RGB", (cw * 3, ch * ((len(grp) + 2) // 3)), (0, 0, 0))
        for j, c in enumerate(grp):
            sh.paste(c, ((j % 3) * cw, (j // 3) * ch))
        name = f"sheet_{n:02d}.jpg"
        sh.save(out_dir / name, quality=85)
        names.append(name)
    print(f"動畫鏡頭 {len(runs)} 個 -> {', '.join(names) or '(無)'};異常 {len(issues)} 筆")
    for x in issues[:SHEET_ISSUES_MAX]:
        print("  異常:", x)
    if len(issues) > SHEET_ISSUES_MAX:
        print(f"  …其餘 {len(issues) - SHEET_ISSUES_MAX} 筆省略")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--types", default="versus,flow,list,timeline")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--bars-demo", action="store_true")
    ap.add_argument("--new-demo", action="store_true")
    ap.add_argument("--sheet", action="store_true", help="全片動畫總覽:每個動畫鏡頭最後一格拼成 sheet_NN.jpg,並印 anim_problems 異常")
    ap.add_argument("--media", default=str(P.ROOT))
    args = ap.parse_args()
    out_dir = Path(args.out or args.script)
    out_dir.mkdir(parents=True, exist_ok=True)
    media = Path(args.media)
    if args.sheet:
        return sheet(args.script, out_dir, media)
    if args.bars_demo:
        return bars_demo(out_dir, media)
    if args.new_demo:
        return new_demo(out_dir)
    script = P.find(args.script, P.REPO)
    lines = B.load_lines(script)
    secs, tlmeta = B.load_meta(script)
    want, seen = args.types.split(","), set()
    for run in B.group_runs(lines):
        if run["key"][0] != "anim":
            continue
        typ = run["lines"][0]["anim"]["type"]
        if typ not in want or (typ in seen and not args.all):
            continue
        seen.add(typ)
        for name in render_run(run, tlmeta, media, out_dir, typ):
            print(name)


if __name__ == "__main__":
    main()
