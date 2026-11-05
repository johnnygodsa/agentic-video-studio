"""run_demo.py 的畫面風格主題(只有資料,畫法在 run_demo.py 依這裡的版面鍵分派)。

每個主題 = 一個 dict:
  版面鍵(字串,選畫法):bg 背景 / title 標題卡 / plain 一般文字卡 / bars 長條圖 / sub 字幕
  顏色鍵(RGB 或 RGBA tuple):見 midnight 的註解
--theme 可給內建名稱或 json 路徑;json 以 "base" 指定底(預設 midnight),其餘鍵覆寫(顏色寫 [r,g,b] 或 [r,g,b,a])。
"""
import json
from pathlib import Path

THEMES = {
    # 現在的樣子:深藍漸層、黃色重點、置中標題、描邊字幕
    "midnight": dict(
        bg="gradient", title="center", plain="rail", bars="classic", sub="stroke",
        bg_top=(30, 38, 54), bg_bot=(18, 22, 30), base=(18, 22, 30),
        accent=(255, 196, 0), accent2=(90, 150, 230),
        text=(235, 238, 245), text_hi=(255, 255, 255), text_dim=(170, 180, 200), text_mute=(150, 160, 180),
        label=(220, 225, 235), src=(140, 150, 170),
        track=(70, 80, 100), bar=(90, 150, 230), bar_hi=(255, 196, 0), bar_text=(255, 255, 255),
        sub_fg=(255, 255, 255), sub_stroke=(0, 0, 0), sub_bg=(0, 0, 0, 150),
        qa_fg=(255, 196, 0), qa_bg=(0, 0, 0),
    ),
    # 淺色編輯風:紙感米白 + 細格線、深字、靠左、細長條、白底黑字字幕帶
    "paper": dict(
        bg="paper", title="left", plain="editorial", bars="thin", sub="band",
        bg_top=(247, 243, 232), bg_bot=(247, 243, 232), base=(247, 243, 232), grid=(226, 219, 202),
        accent=(201, 69, 38), accent2=(60, 90, 120),
        text=(34, 34, 40), text_hi=(20, 20, 24), text_dim=(100, 96, 90), text_mute=(130, 125, 115),
        label=(34, 34, 40), src=(120, 115, 105),
        track=(214, 207, 190), bar=(120, 134, 150), bar_hi=(201, 69, 38), bar_text=(34, 34, 40),
        sub_fg=(0, 0, 0), sub_stroke=(255, 255, 255), sub_bg=(255, 255, 255, 255), sub_rule=(34, 34, 40),
        qa_fg=(201, 69, 38), qa_bg=(255, 255, 255),
    ),
    # 霓虹:深紫到深藍對角漸層、洋紅 + 青色發光、圓角、外框標題卡、半透明圓角字幕底
    "neon": dict(
        bg="neon", title="card", plain="glow", bars="round", sub="pill",
        bg_top=(34, 10, 70), bg_bot=(6, 16, 52), base=(20, 12, 56),
        glow1=(255, 40, 180), glow2=(0, 220, 255),
        accent=(255, 60, 190), accent2=(0, 230, 255),
        text=(240, 236, 255), text_hi=(255, 255, 255), text_dim=(180, 170, 230), text_mute=(150, 140, 205),
        label=(225, 220, 255), src=(150, 145, 205),
        track=(86, 60, 150), bar=(255, 60, 190), bar_hi=(0, 230, 255), bar_text=(255, 255, 255),
        card_fill=(14, 8, 44, 190),
        sub_fg=(255, 255, 255), sub_stroke=(0, 0, 0), sub_bg=(8, 4, 30, 175), sub_edge=(0, 230, 255),
        qa_fg=(0, 230, 255), qa_bg=(10, 6, 34),
    ),
    # 海報式:黃底大色塊(標題卡上方黑塊、文字卡左側黑欄、長條圖上方黑帶)、粗字、方形長條帶數值
    "bold": dict(
        bg="flat", title="poster", plain="side", bars="block", sub="slab",
        bg_top=(255, 214, 10), bg_bot=(255, 214, 10), base=(255, 214, 10),
        block=(16, 16, 20), accent=(232, 48, 28), accent2=(16, 16, 20),
        text=(16, 16, 20), text_hi=(255, 255, 255), text_dim=(70, 60, 20), text_mute=(90, 80, 30),
        label=(16, 16, 20), src=(60, 52, 16),
        track=(16, 16, 20), bar=(16, 16, 20), bar_hi=(232, 48, 28), bar_text=(255, 255, 255),
        tag_fg=(255, 255, 255), tag_bg=(232, 48, 28), dot_off=(90, 90, 100),
        sub_fg=(255, 255, 255), sub_stroke=(0, 0, 0), sub_bg=(16, 16, 20, 255), sub_rule=(232, 48, 28),
        qa_fg=(255, 214, 10), qa_bg=(16, 16, 20),
    ),
}


def _color(v):
    """json 的 [r,g,b(,a)] 轉 tuple;其他型別原樣。"""
    if isinstance(v, list) and len(v) in (3, 4) and all(isinstance(x, (int, float)) for x in v):
        return tuple(int(x) for x in v)
    return v


def load_theme(spec):
    """spec = 內建名稱或 json 路徑;回傳 (名稱, dict)。找不到就丟 SystemExit。"""
    if spec in THEMES:
        return spec, dict(THEMES[spec])
    p = Path(spec)
    if not p.is_file():
        raise SystemExit(f"[theme] 找不到主題 {spec!r}(內建:{'、'.join(THEMES)};或給 json 路徑)")
    raw = json.loads(p.read_text(encoding="utf-8-sig"))
    base = raw.pop("base", "midnight")
    if base not in THEMES:
        raise SystemExit(f"[theme] base {base!r} 不是內建主題({'、'.join(THEMES)})")
    t = dict(THEMES[base])
    t.update({k: _color(v) for k, v in raw.items()})
    return p.stem, t
