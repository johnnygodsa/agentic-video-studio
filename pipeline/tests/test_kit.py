"""動態小件(kit)定位換算與節制規則:python -X utf8 -m pytest pipeline/tests/test_kit.py -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build as B  # noqa: E402
import kit as KIT  # noqa: E402

ENTRIES = [
    {"text": "這款遊戲 一團", "box": [100, 200, 500, 260]},
    {"text": "亂的開場", "box": [100, 270, 400, 330], "chars": [[100, 175], [175, 250], [250, 325], [325, 400]]},
    {"text": "後面又一團亂", "box": [100, 400, 700, 460]},
]


def test_find_text_first_hit_across_lines():
    # 忽略空白與大小寫、跨行取第一個命中:第 0 行整框 + 第 1 行「亂」字框
    assert KIT.find_text_rect(ENTRIES, "一 團亂") == (100, 200, 500, 330)
    assert KIT.find_text_rect(ENTRIES, "開場") == (250, 270, 400, 330)
    assert KIT.find_text_rect(ENTRIES, "不存在") is None


def test_to_canvas_and_pct():
    assert KIT.to_canvas((100, 200, 500, 330), 0.5, (40, 60)) == [90.0, 160.0, 200.0, 65.0]
    assert KIT.to_canvas((100, 200, 500, 330), 0.5, (40, 60), ox=30) == [120.0, 160.0, 200.0, 65.0]
    assert KIT.pct_rect([10, 20, 30, 40], (1920, 1080)) == [192.0, 216.0, 576.0, 432.0]


def test_map_rect_follows_drift():
    zoom = (1.04, 0.5, 0.5)
    rect = [120.0, 160.0, 200.0, 65.0]          # 頁面座標,左補邊 30
    for u in (0.0, 1.0):
        z, sx = 1 + 0.04 * u, B.DRIFT_PX * (2 * u - 1)
        exp_x = 90 * z - (z - 1) * B.W * 0.5 + sx
        exp_y = 160 * z - (z - 1) * B.H * 0.5
        got = KIT.map_rect(rect, B.fx_map("drift_r", u, zoom), ox=30)
        assert abs(got[0] - exp_x) < 1e-6 and abs(got[1] - exp_y) < 1e-6
        assert abs(got[2] - 200 * z) < 1e-6 and abs(got[3] - 65 * z) < 1e-6
    # drift_l 方向相反
    assert KIT.map_rect(rect, B.fx_map("drift_l", 0.0, zoom), ox=30)[0] == 90 + B.DRIFT_PX


def test_map_rect_tilt_matches_quad():
    # 畫布四角經 tilt 映射 = _tilt_quad 的四角
    f = B.fx_map("tilt_l", 0.5)
    got = KIT.map_rect([0, 0, B.W, B.H], f)
    q = B._tilt_quad("tilt_l", 0.5)
    assert abs(got[0] - min(p[0] for p in q)) < 1e-6 and abs(got[1] - min(p[1] for p in q)) < 1e-6


def test_limits():
    three = [{"type": "callout", "at": {"text": "a"}}, {"type": "punch"}, {"type": "punch"}]
    errs = KIT.line_errors(three)
    assert any("同一句小件 3 個" in e for e in errs) and any("punch 2 次" in e for e in errs)
    assert KIT.item_errors({"type": "blink"})[0].startswith("沒有這種小件")
    assert KIT.item_errors({"type": "lower"}) == ["lower 缺必要欄位 text"]
    assert KIT.item_errors({"type": "callout", "at": {"text": "a", "box": [1, 2, 3, 4]}})
    assert KIT.shot_errors([{"type": "spotlight", "at": {"box": [1, 1, 1, 1]}}], tilt=True)
    assert not KIT.shot_errors([{"type": "spotlight", "at": {"box": [1, 1, 1, 1]}}], tilt=False)
    assert KIT.shot_errors([{"type": "tick", "at": {"box": [1, 1, 1, 1]}}] * 5, tilt=False)


# ---------------------------------------------------------------- 擺放:不重疊
VIS = (0, 0, 1920, 840)
TEXTS = [[65, 255, 1730, 87], [65, 363, 326, 87], [65, 470, 1237, 87], [65, 577, 900, 87]]     # 四行密集大字
TARGET = [456, 470, 195, 87]


def _clear(box, obs, margin):
    return all(KIT.gap(box, o) >= margin - 1e-6 for o in obs)


def test_gap_and_subtract():
    assert KIT.gap([0, 0, 10, 10], [20, 0, 10, 10]) == 10
    assert KIT.gap([0, 0, 10, 10], [5, 5, 10, 10]) == 0
    pieces = KIT.subtract([0, 0, 100, 20], [40, 0, 20, 20])
    assert sorted(p[0] for p in pieces) == [0, 60] and all(KIT.overlap_area(p, [40, 0, 20, 20]) == 0 for p in pieces)


def test_layout_pop_badge_lower_arrow_clear():
    items = [{"type": "pop", "text": "火藥桶", "rect": TARGET, "line": 1}, {"type": "badge", "text": "302萬", "rect": TARGET, "line": 1},
             {"type": "lower", "text": "體育京鄉", "sub": "2026/05/29 玩家反應整理", "line": 1},
             {"type": "arrow", "rect": TARGET, "line": 1}]
    out, recs, warns = KIT.layout(items, VIS, TEXTS)
    assert not warns, warns
    by = {r["type"]: r for r in recs}
    assert by["pop"]["nearest"] >= KIT.MARGIN and by["badge"]["nearest"] >= KIT.BADGE_MARGIN and by["lower"]["nearest"] >= KIT.LOWER_MARGIN
    for r in recs:                               # 字幕安全區:框不進 VIS 下緣以下(箭頭除外會另驗)
        assert r["box"][1] + r["box"][3] <= VIS[3] + 1e-6
    a = next(i for i in out if i["type"] == "arrow")
    ob = [q for o in TEXTS for q in KIT.subtract(o, [TARGET[0] - 1, TARGET[1] - 1, TARGET[2] + 2, TARGET[3] + 2])]
    assert KIT.arrow_cost(a["tip"], a["tail"], a["u"], ob, (0, 0, 1920, 840))[0] == 0
    assert 120 <= KIT.pt_gap(a["tail"], TARGET) <= 260 and abs(KIT.pt_gap(a["tip"], TARGET) - 8) < 1.5
    assert a["wobble"] == [3, 2.4]


def test_layout_pop_shrinks_then_warns():
    wall = [[0, 0, 1920, 840]]                    # 全滿:找不到 -> ok False + 警告,不丟例外
    out, recs, warns = KIT.layout([{"type": "pop", "text": "火藥桶", "rect": TARGET, "line": 3}], VIS, wall)
    assert warns and "放不下" in warns[0] and out[0]["size"] == round(120 * KIT.POP_SCALES[-1])
    gap_band = [[0, 0, 1920, 300], [0, 560, 1920, 280]]       # 中間只有 260 高的空白帶:120 字級(高 140)塞得下
    out, recs, warns = KIT.layout([{"type": "pop", "text": "火藥桶", "rect": [900, 100, 100, 80], "line": 3}], VIS, gap_band)
    assert not warns and 300 + KIT.MARGIN <= out[0]["pos"][1] and recs[0]["nearest"] >= KIT.MARGIN
    tight = [[0, 0, 1920, 360], [0, 520, 1920, 320]]          # 空白帶只有 160 高:要縮字級才放得下(邊距 24 * 2 + 框)
    out, recs, warns = KIT.layout([{"type": "pop", "text": "火藥桶", "rect": [900, 100, 100, 80], "line": 3}], VIS, tight)
    assert out[0]["size"] < 120


def test_layout_lower_moves_up_and_badge_avoids_chart():
    last_line = [[65, 700, 900, 87]]              # 最後一行內文壓在預設位置
    out, recs, warns = KIT.layout([{"type": "lower", "text": "體育京鄉", "sub": "2026/05/29", "line": 1}], VIS, last_line)
    assert not warns and recs[0]["nearest"] >= KIT.LOWER_MARGIN and out[0]["pos"][1] + 100 < 700 + 200
    bars = [[100, 100, 800, 60], [100, 180, 800, 60], [100, 260, 1100, 60], [1210, 260, 120, 60]]      # 最後一列末端有數值
    tgt = [1210, 260, 120, 60]
    out, recs, warns = KIT.layout([{"type": "badge", "text": "302萬", "rect": tgt, "line": 1}], VIS, bars)
    assert not warns and _clear(recs[0]["box"], bars, KIT.BADGE_MARGIN)


def test_layout_portrait_window():
    """直式畫面窗 1080x1080(計畫 #5c):可放區 = 文字安全框 PORTRAIT_VIS,lower 貼左下、arrow / pop / badge 不出框。"""
    pv = KIT.PORTRAIT_VIS
    assert pv == (80, 40, 940, 1040)
    tgt = [500, 300, 200, 60]
    items = [{"type": "lower", "text": "體育京鄉", "sub": "2026/05/29", "line": 1}, {"type": "pop", "text": "火藥桶", "rect": tgt, "line": 1},
             {"type": "badge", "text": "302萬", "rect": tgt, "line": 1}, {"type": "arrow", "rect": tgt, "line": 1}]
    out, recs, warns = KIT.layout(items, pv, [tgt], portrait=True)
    for r in recs:
        if r.get("fixed") or r["type"] == "arrow":
            continue
        x, y, w, h = r["box"]
        assert pv[0] - 1 <= x and x + w <= pv[2] + 1 and pv[1] - 1 <= y and y + h <= pv[3] + 1, (r["type"], r["box"])
    low = next(r for r in recs if r["type"] == "lower")
    assert abs(low["box"][0] - pv[0]) < 1 and low["box"][1] > 700, low
    for it in out:
        if it["type"] == "arrow":
            for x, y in (it["tip"], it["tail"]):
                assert pv[0] - 1 <= x <= pv[2] + 1 and pv[1] - 1 <= y <= pv[3] + 1, it
    j = KIT.job([{"type": "lower", "text": "體育京鄉", "t": 0.3, "line": 1}], (1080, 1080), pv, portrait=True)
    assert j["data"]["portrait"] and j["size"] == [1080, 1080]


if __name__ == "__main__":
    for _n, _f in list(globals().items()):
        if _n.startswith("test_"):
            _f()
    print("test_kit: all passed")
