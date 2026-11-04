#!/usr/bin/env python3
r"""單一場景草稿:依 build\<tag>\film_timeline.json 取該場景的 dur 與 lines,呼叫 render_clip 算圖(只出格),並出每秒一格的總覽圖。
用法:python -X utf8 pipeline\sci\scene_clip.py --tag turtle --scene t_hook
輸出:tmp\sc_<scene>\(每 0.1 秒一張)與 tmp\sc_<scene>\_sheet.png(每秒一格、6 欄、每格寬 480);render_clip 的檢查摘要照印。"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths as P
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("--tag", required=True)
ap.add_argument("--scene", required=True)
a = ap.parse_args()
film = json.loads((P.REPO / a.tag / "film.json").read_text(encoding="utf-8"))
tl = json.loads((P.build_dir(a.tag) / "film_timeline.json").read_text(encoding="utf-8"))
sc = next(s for s in tl["scenes"] if s["scene"] == a.scene)
out = f"sc_{a.scene}"
r = subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).with_name("render_clip.py")), a.scene, "--dur", str(sc["dur"]),
                    "--hue", str(film["hue"]), "--params", json.dumps({"lines": sc.get("lines", [])}, ensure_ascii=False), "--out", out, "--frames-only"],
                   cwd=P.REPO)
d = P.ROOT / "tmp" / out
fr = sorted(p for p in d.glob("*.png") if not p.name.startswith("_"))[::10]
if fr:
    cols, w = 6, 480
    h = w * 9 // 16
    sheet = Image.new("RGB", (cols * w, ((len(fr) + cols - 1) // cols) * h), "white")
    for i, p in enumerate(fr):
        sheet.paste(Image.open(p).convert("RGB").resize((w, h)), ((i % cols) * w, (i // cols) * h))
    sheet.save(d / "_sheet.png")
    print(f"總覽 {d / '_sheet.png'}({len(fr)} 格)")
sys.exit(r.returncode)
