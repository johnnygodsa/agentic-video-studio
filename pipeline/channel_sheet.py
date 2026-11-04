"""頻道資產樣張:把 channel\\draft\\<name>.html 用無頭 Edge 截成 output\\channel\\<name>.png。

用法:python -X utf8 pipeline\\channel_sheet.py mascots palettes
html 內的 /*FONTS*/ 會換成本機字型的 @font-face(字型檔唯讀引用,不複製)。
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

import paths

USER_FONTS = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
REPO_FONTS = paths.REPO / "fonts"


def _font(name):
    """repo fonts\\ 有就用(副本專案隨附字型),否則用使用者安裝的字型。"""
    f = REPO_FONTS / name
    return f if f.exists() else USER_FONTS / name


FONTS = {
    "Sub": paths.ROOT / "fonts" / "NotoSansTC-SubBold.ttf",
    "GenSeki": _font("GenSekiGothic2TW-H.otf"),
    "GenSen": _font("GenSenRounded2TW-H.otf"),
    "Chiron": _font("ChironGoRoundTC-900H.otf"),
    "GenYo": _font("GenYoGothic2TW-H.otf"),
    "Swei": _font("獅尾圓體 SweiGothicCJKtc-Black.ttf"),
    "Glow": _font("GlowSansTC-Compressed-ExtraBold.otf"),
}


def font_css():
    out = []
    for name, f in FONTS.items():
        if not f.exists():
            print(f"缺字型 {name}: {f.name}")
            continue
        out.append(f'@font-face{{font-family:"{name}";src:url("{f.as_uri()}")}}')
    return "\n".join(out)


def main(names):
    src_dir = paths.ROOT / "channel" / "draft"
    out_dir = paths.OUTPUT / "channel"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths.TMP.mkdir(exist_ok=True)
    css = font_css()
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for n in names:
            html = (src_dir / f"{n}.html").read_text(encoding="utf-8").replace("/*FONTS*/", css)
            # /*PIGEON_JS*/ 換成 pipeline\sci\pigeon.js 內容(暫存 html 不靠相對路徑)
            html = html.replace("/*PIGEON_JS*/", (paths.ROOT / "pipeline" / "sci" / "pigeon.js").read_text(encoding="utf-8"))
            tmp = paths.TMP / f"channel_{n}.html"
            tmp.write_text(html, encoding="utf-8")
            pg.goto(tmp.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(400)
            bad = pg.evaluate("[...document.fonts].filter(f=>f.status!=='loaded').map(f=>f.family)")
            out = out_dir / f"{n}.png"
            pg.screenshot(path=str(out), full_page=True)
            print(f"{n}: {paths.rel(out)} 未載入字型 {bad or '無'}")
        b.close()


if __name__ == "__main__":
    main(sys.argv[1:])
