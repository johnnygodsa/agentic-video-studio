"""OCR 引擎比較(T4):同一批圖分別用 Windows OCR(win)與 RapidOCR(rapid)跑,輸出命中數與每張秒數的 markdown 表。
python pipeline/ocr_compare.py <圖檔或資料夾>... [--engines win,rapid] [--synth N] [--out tmp/ocr_compare.md]
python pipeline/ocr_compare.py --clip <src>... [--engines win,rapid]     # 對 raw\\<src>.mp4 各跑一次 clip_scan.scan,比剔除數與秒數
  --synth N   用 fonts/ 的 Noto Sans TC 產生 N 張「內嵌中文字幕」合成圖(放 tmp/ocr_compare_synth/),補真實截圖不足
命中 = 一張圖 OCR 到的 英文字母數 >= clip_scan.TEXT_MIN(8)或 中文字數 >= 4(即 clip_scan / 字幕偵測會視為「有字」)
只量引擎本身:第一次呼叫(載入模型)另列,不計入每張秒數。
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

import assets_lib as AL
import paths as P

TEXT_MIN = 8
CJK_MIN = 4
EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
SYNTH_LINES = [
    ("這個遊戲的劇情真的很扯", "Press Start to continue"),
    ("官方宣布延期到明年", "COMING SOON 2027"),
    ("玩家評價兩極 差評如潮", "Steam Overwhelmingly Negative"),
    ("開發商道歉 承諾退款", "We are sorry for the delay"),
    ("預告片一公開就引發討論", "Official Trailer 4K"),
    ("伺服器今晚維護六小時", "Server maintenance tonight"),
    ("售價漲到七十美元", "Now available for $69.99"),
    ("這次改版砍掉了三個職業", "Patch notes 2.4.1"),
    ("實機畫面比預告差很多", "Gameplay not final footage"),
    ("訂閱頻道 看更多遊戲新聞", "SUBSCRIBE for more"),
]


def make_synth(n, out_dir):
    """合成「遊戲畫面 + 下方中文字幕 + 上方英文字卡」圖,回傳路徑清單。"""
    import random
    from PIL import Image, ImageDraw
    out_dir.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(4)
    paths = []
    for i in range(n):
        zh, en = SYNTH_LINES[i % len(SYNTH_LINES)]
        bg = tuple(rnd.randint(20, 90) for _ in range(3))
        im = Image.new("RGB", (960, 540), bg)
        d = ImageDraw.Draw(im)
        for _ in range(6):    # 背景雜訊色塊,模擬遊戲畫面
            x, y = rnd.randint(0, 800), rnd.randint(0, 400)
            d.rectangle((x, y, x + rnd.randint(40, 200), y + rnd.randint(30, 140)),
                        fill=tuple(rnd.randint(0, 140) for _ in range(3)))
        f = AL.font(36, True)
        w = d.textlength(zh, font=f)
        d.text(((960 - w) / 2, 450), zh, font=f, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        f2 = AL.font(28)
        d.text((40, 30), en, font=f2, fill=(240, 240, 240), stroke_width=1, stroke_fill=(0, 0, 0))
        p = out_dir / f"synth_{i + 1:02d}.png"
        im.save(p)
        paths.append(p)
    return paths


def collect(args):
    out = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            out += sorted(x for x in p.iterdir() if x.suffix.lower() in EXTS)
        elif p.exists():
            out.append(p)
        else:
            print(f"找不到:{a}", file=sys.stderr)
    return out


def stats(lines):
    text = "".join(ln["text"] for ln in lines)
    letters = len(re.findall(r"[A-Za-z]", text))
    cjk = len(re.findall(r"[㐀-鿿]", text))
    return letters, cjk, letters >= TEXT_MIN or cjk >= CJK_MIN


def check_engine(eng):
    """回傳 None = 可用,否則原因字串"""
    if eng == "rapid":
        try:
            import rapidocr_onnxruntime  # noqa: F401
        except ImportError:
            return "rapidocr_onnxruntime 未安裝"
    elif eng == "win":
        import shutil
        if not shutil.which("powershell"):
            return "找不到 powershell(非 Windows)"
    else:
        return "未知引擎"
    return None


def run_images(files, engines):
    res = {}     # eng -> {"load": s, "rows": {name: (sec, letters, cjk, hit, text)}, "err": str}
    for eng in engines:
        why = check_engine(eng)
        if why:
            res[eng] = dict(err=why)
            continue
        os.environ["OCR_ENGINE"] = eng
        r = dict(rows={}, load=0.0)
        try:
            t = time.perf_counter()
            AL.ocr(files[0])          # 暖機(rapid 載入模型;win 起第一個 powershell),不計入每張秒數
            r["load"] = time.perf_counter() - t
            for f in files:
                t = time.perf_counter()
                lines = AL.ocr(f)
                sec = time.perf_counter() - t
                letters, cjk, hit = stats(lines)
                r["rows"][f.name] = (sec, letters, cjk, hit, " / ".join(ln["text"] for ln in lines))
        except Exception as e:      # noqa: BLE001
            r["err"] = f"{type(e).__name__}: {e}"
        res[eng] = r
    return res


def md_images(files, engines, res):
    L = ["## 圖片比較", ""]
    head = "| 圖 |" + "".join(f" {e} 秒 | {e} 字母/中文 | {e} 命中 |" for e in engines)
    L += [head, "|---|" + "---|---|---|" * len(engines)]
    for f in files:
        row = f"| {f.name} |"
        for e in engines:
            r = res[e]
            if "err" in r and f.name not in r.get("rows", {}):
                row += " n/a | n/a | n/a |"
            else:
                sec, le, cj, hit, _ = r["rows"][f.name]
                row += f" {sec:.2f} | {le}/{cj} | {'Y' if hit else '-'} |"
        L.append(row)
    L += ["", "| 引擎 | 命中數 | 平均每張秒數 | 首次呼叫(載入)秒 | 備註 |", "|---|---|---|---|---|"]
    for e in engines:
        r = res[e]
        rows = r.get("rows", {})
        if not rows:
            L.append(f"| {e} | n/a | n/a | n/a | {r.get('err', '')} |")
            continue
        hits = sum(1 for v in rows.values() if v[3])
        avg = sum(v[0] for v in rows.values()) / len(rows)
        L.append(f"| {e} | {hits}/{len(rows)} | {avg:.2f} | {r['load']:.2f} | {r.get('err', '')} |")
    L += ["", "### 辨識文字樣本", ""]
    for f in files:
        L.append(f"- `{f.name}`")
        for e in engines:
            v = res[e].get("rows", {}).get(f.name)
            L.append(f"  - {e}: {v[4][:80] if v else 'n/a'}")
    return L


def run_clip(srcs, engines):
    import clip_scan as CS
    L = ["## clip_scan 比較", "", "| 來源 | 引擎 | 總秒數 | 每格秒數 | 區段數 | 可用秒 | 剔除(亮度/文字) |", "|---|---|---|---|---|---|---|"]
    for s in srcs:
        for e in engines:
            why = check_engine(e)
            if why:
                L.append(f"| {s} | {e} | n/a | n/a | n/a | n/a | {why} |")
                continue
            os.environ["OCR_ENGINE"] = e
            t = time.perf_counter()
            try:
                r = CS.scan(s)
            except Exception as ex:      # noqa: BLE001
                L.append(f"| {s} | {e} | n/a | n/a | n/a | n/a | {type(ex).__name__}: {ex} |")
                continue
            sec = time.perf_counter() - t
            use = sum(b - a for a, b, _ in r["runs"])
            L.append(f"| {s} | {e} | {sec:.0f} | {sec / max(r['dur'], 1):.2f} | {len(r['runs'])} | {use:.0f} | "
                     f"{r['bad']['亮度']}/{r['bad']['文字']} |")
    return L


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--engines", default="win,rapid")
    ap.add_argument("--synth", type=int, default=0)
    ap.add_argument("--clip", nargs="+", default=[])
    ap.add_argument("--out", default=str(P.TMP / "ocr_compare.md"))
    a = ap.parse_args()
    engines = [e.strip() for e in a.engines.split(",") if e.strip()]
    files = collect(a.paths)
    if a.synth:
        files += make_synth(a.synth, P.TMP / "ocr_compare_synth")
    L = ["# OCR 引擎比較", ""]
    if files:
        L += md_images(files, engines, run_images(files, engines))
    if a.clip:
        L += [""] + run_clip(a.clip, engines)
    if not files and not a.clip:
        ap.error("要給圖檔/資料夾、--synth 或 --clip")
    txt = "\n".join(L) + "\n"
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(txt, encoding="utf-8")
    print(txt)
    print(f"已寫入 {out}")


if __name__ == "__main__":
    main()
