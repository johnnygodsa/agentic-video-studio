"""cols / share / num 版面測試:python -X utf8 pipeline\\tests\\test_new_anim_layout.py
涵蓋:cols 幾何(槽寬、柱寬、基線、最高柱頂、置中、標籤過長報錯、強調規則、2–7 根)、share 幾何(條左端 460、寬 1280、列距、下緣上限、同名同色、
總和驗證 parse_anim、段寬放不下不畫數值)、num 幾何(字級、置中、等比縮小、count-up 判斷)、三種的邊界與重疊(anim_problems)、秒數函式。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import anim_lib as AL  # noqa: E402
import build as B  # noqa: E402

FAILS = []


def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  {info}" if info else ""))
    if not cond:
        FAILS.append(name)


def perr(a):
    errs = []
    ok = B.parse_anim(dict(idx=1, anim=a), None, errs)
    return ok, errs


# ---- cols
items = [["2022", 3, "款"], ["2023", 9, "款"], ["2024", 5, "款"], ["2025", 4, "款"], ["2026", 4, "款"]]
lay = AL._ColsLayout("標題", items)
check("cols 槽寬 = min(280, 1500/n)", lay.slot == 280 and AL._ColsLayout("t", items[:2] + items[:2] + items[:2] + items[:1]).slot == 1500 / 7)
check("cols 柱寬 = min(150, 槽寬*0.6)", lay.bw == 150 and abs(AL._ColsLayout("t", [["a", 1], ["b", 2]] * 3 + [["c", 1]]).bw - 1500 / 7 * 0.6) < 1e-6)
pl = [lay.place(k) for k in range(5)]
check("cols 基線 y=700、最高柱頂 y=330", all(p["bar"][3] == 700 for p in pl) and min(p["bar"][1] for p in pl) == 330)
check("cols 整組水平置中", abs(lay.x0 + 5 * lay.slot / 2 - 960) < 1e-6 and abs((pl[0]["bar"][0] + pl[4]["bar"][2]) / 2 - 960) < 1e-6 + 65)
check("cols 數值在柱頂上方 16px", pl[1]["val"][1][3] == 330 - 16, f"{pl[1]['val'][1][3]}")
check("cols 標籤上緣距基線 18px", all(p["label"][1][1] == 718 for p in pl[:1]), f"{pl[0]['label'][1]}")
check("cols 自動強調最大值、其餘中性色", lay.hi == [False, True, False, False, False] and lay.color(1) == AL.PAL_ACCENT and lay.color(0) == AL.PAL_NEUTRAL)
check("cols hi 指定不再自動強調", AL._ColsLayout("t", [["a", 1, "", {"hi": True}], ["b", 2]]).hi == [True, False])
check("cols 數值全相同不強調", AL._ColsLayout("t", [["a", 2], ["b", 2]]).hi == [False, False])
for bad in ([["a", 1]], [[str(i), 1] for i in range(8)]):
    try:
        AL._ColsLayout("t", bad)
        check(f"cols {len(bad)} 根報錯", False)
    except ValueError:
        check(f"cols {len(bad)} 根報錯", True)
try:
    AL._ColsLayout("t", [["這個標籤太長了吧", 1], ["b", 2]] * 3 + [["c", 1]])
    check("cols 標籤過長報錯", False)
except ValueError as e:
    check("cols 標籤過長報錯", "標籤過長" in str(e), str(e)[:30])
check("cols 示例無問題(含 src)", AL.anim_problems(dict(type="cols", title="Sweet Baby Inc 掛名的遊戲", src="維基百科整理", items=items)) == [])
check("cols 逐步秒數 = bars", AL.cols_step_seconds(0, 3) == AL.bars_step_seconds(0, 3) and AL.cols_step_seconds(2, 2) == 0.1)

# ---- share
rows = [dict(label="加入前", parts=[["聯盟", 60, "alliance"], ["部落", 40, "horde"]]),
        dict(label="加入後", parts=[["聯盟", 40, "alliance"], ["部落", 60, "horde"]])]
sl = AL._ShareLayout("陣營比例", rows)
check("share 條左端 460、寬 1280", sl.bounds[2] == 460 + 1280 and sl.segs[0][0]["x0"] == 0 and abs(sl.segs[0][-1]["x1"] - 1280) < 1e-6)
check("share 段與段 4px 空隙", all(abs(r[1]["x0"] - r[0]["x1"] - 4) < 1e-6 for r in sl.segs))
check("share 條厚 96 列距 72", (sl.bh, sl.gap) == (96, 72) and sl.tops[1] - sl.tops[0] == 168, f"{sl.bh} {sl.gap} {sl.tops}")
check("share 列標籤右緣 420", all(l["bb"][2] == 420 for l in sl.lbl), f"{[l['bb'] for l in sl.lbl]}")
check("share 下緣 <= 800", sl.bounds[3] <= 800 and AL._ShareLayout("t", rows, "%", "出處").bounds[3] <= 752)
check("share 同名同色(第二列不同指定也以第一次為準)",
      AL._ShareLayout("t", [rows[0], dict(label="x", parts=[["聯盟", 50, "#ff0000"], ["部落", 50]])]).cmap["聯盟"] == AL.BAR_COLORS["alliance"])
dl = AL._ShareLayout("t", [dict(label="a", parts=[["甲", 50], ["乙", 30], ["丙", 20]]), dict(label="b", parts=[["甲", 20], ["乙", 30], ["丙", 50]])])
check("share 預設色序且同名同色", [dl.cmap[n] for n in ("甲", "乙", "丙")] == AL.SHARE_SEQ[:3])
four = AL._ShareLayout("t", [dict(label=str(i), parts=[["甲", 50], ["乙", 50]]) for i in range(4)])
check("share 4 列可排且下緣 <= 800", four.bounds[3] <= 800, f"bh={four.bh} gap={four.gap} bottom={four.bounds[3]}")
narrow = AL._ShareLayout("t", [dict(label="a", parts=[["甲", 99], ["乙", 1]])])
check("share 窄段不畫數值", [s["show"] for s in narrow.segs[0]] == [True, False])
check("share 圖例名稱依首次出現", dl.names == ["甲", "乙", "丙"])
for tot, good in ((100, True), (99, True), (101, True), (98, False), (102, False)):
    ok, errs = perr(dict(type="share", title="t", rows=[dict(label="a", parts=[["甲", tot - 40], ["乙", 40]])]))
    check(f"share 總和 {tot} {'通過' if good else '報錯'}", bool(ok) == good and (good or "99–101" in errs[0]), "" if good else errs[0][:40])
check("share 示例無問題", AL.anim_problems(dict(type="share", title="陣營比例", rows=rows)) == [])
check("share 逐步秒數", AL.share_step_seconds(0, 0) == 0.5 and AL.share_step_seconds(1, 1) == 0.1 and abs(AL.share_step_seconds(0, 2) - 1.35) < 1e-9)

# ---- num
nl = AL._NumLayout("首月銷量", "2,300 萬", "前作同期 1,800 萬", "up")
check("num big 300px、單位 0.45 倍(135)", nl.size == 300 and nl.items[0]["size"] == 300 and nl.items[1]["size"] == 135)
check("num big 整行置中、垂直中心 450", abs((nl.big_box[0] + nl.big_box[2]) / 2 - 960) <= 2 and abs((nl.big_box[1] + nl.big_box[3]) / 2 - 450) <= 2, f"{nl.big_box}")
check("num 單位與數字共用基線", nl.items[0]["xy"][1] + nl.items[0]["bl"] == nl.items[1]["xy"][1] + nl.items[1]["bl"])
check("num label 中心 y=230、compare 中心 y=660", abs((nl.boxes[0][1][1] + nl.boxes[0][1][3]) / 2 - 230) <= 2 and abs((nl.boxes[-1][1][1] + nl.boxes[-1][1][3]) / 2 - 660) <= 2)
check("num tone up 有三角、none 沒有", nl.tri is not None and AL._NumLayout("a", "5", "b", "none").tri is None and AL._NumLayout("a", "5", "b").tri is None)
wide = AL._NumLayout("a", "1,234,567,890 億美金元", "b")
check("num 過寬等比縮小到 <= 1728", wide.size < 300 and wide.big_box[2] - wide.big_box[0] <= 1728, f"size={wide.size} w={wide.big_box[2] - wide.big_box[0]}")
check("num count-up 判斷", AL.num_is_count("2,300 萬") and AL.num_is_count("29.99 美金") and not AL.num_is_count("80 → 100 元") and not AL.num_is_count("很多"))
check("num 箭頭案例排得下", AL._NumLayout("a", "80 → 100 元", "b").total <= 1728)
check("num 示例無問題", AL.anim_problems(dict(type="num", label="首月銷量", big="2,300 萬", compare="前作同期 1,800 萬", tone="up", src="官方")) == [])
check("num 秒數", abs(AL.num_step_seconds(0, 1, "2,300 萬") - 1.2) < 1e-9 and abs(AL.num_step_seconds(0, 2, "2,300 萬") - 1.95) < 1e-9
      and abs(AL.num_step_seconds(1, 2, "2,300 萬") - 0.5) < 1e-9 and AL.num_step_seconds(1, 1) == 0.1)
check("num 淡入型秒數較短", AL.num_step_seconds(0, 1, "80 → 100 元") < AL.num_step_seconds(0, 1, "80 元"))
fr = AL.make_num_step("a", "2,300 萬", "b", "up", 2, 0, True)
check("num 同一 t 同一張圖(純函式)", (AL.make_num_step("a", "2,300 萬", "b", "up", 2, 0, True)[10] == fr[10]).all() and len(fr) == int(round(AL.num_step_seconds(0, 2, "2,300 萬") * AL.FPS)))

# ---- parse_anim 其他驗證
for a, good in ((dict(type="cols", title="t", items=items), True), (dict(type="cols", title="t", items=items, step=4), True),
                (dict(type="cols", title="t", items=items, step=5), False), (dict(type="cols", title="t", items=items[:1]), False),
                (dict(type="share", title="t", rows=rows, step=1), True), (dict(type="share", title="t", rows=rows, step=2), False),
                (dict(type="share", title="t", rows=[dict(label="a", parts=[["甲", 100]])]), False),
                (dict(type="num", label="a", big="5"), True), (dict(type="num", label="a", big="5", compare="b", step=1), True),
                (dict(type="num", label="a", big="5", step=1), False), (dict(type="num", label="a", big="5", tone="x"), False)):
    ok, errs = perr(a)
    check(f"parse {a['type']} {'合法' if good else '非法'} {a.get('step', '-')}", bool(ok) == good, "" if good else (errs[0][:50] if errs else ""))

print("\n失敗 %d 項" % len(FAILS))
sys.exit(1 if FAILS else 0)
