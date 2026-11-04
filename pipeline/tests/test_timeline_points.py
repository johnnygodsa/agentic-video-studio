"""timeline 每個 anim 自帶 points 的測試:python -X utf8 pipeline\tests\test_timeline_points.py
涵蓋:自帶 points 優先、無 points 退回頂層 timeline.points(舊片相容)、兩者皆無報錯、step 範圍依該組 points、
不同 points 的相鄰句不合鏡頭、同組 points 合鏡、頂層 vs 自帶不合鏡、版面檢查與動畫快取簽章吃到該組 points。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import build as B  # noqa: E402

FAILS = []


def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  {info}" if info else ""))
    if not cond:
        FAILS.append(name)


PA = [["2019", "第一件事"], ["2020", "第二件事"], ["2021", "第三件事"]]
PB = [["三月", "甲"], ["四月", "乙"]]
TOP = {"points": [["2001", "頂層一"], ["2002", "頂層二"]], "question_between": [0, 1]}


def ln(i, a):
    return {"idx": i, "anim": a}


def parse(a, tl=None):
    errs = []
    r = B.parse_anim(ln(1, a), tl, errs)
    return r, errs


# 1) 自帶 points
r, e = parse({"type": "timeline", "points": PA, "step": 2}, None)
check("自帶 points:無頂層也可用", r is not None and not e, e)
r, e = parse({"type": "timeline", "points": PB, "step": 2}, None)
check("step 超出該組 points 報錯", r is None and any("step 錯誤" in x for x in e), e)
r, e = parse({"type": "timeline", "points": PA, "step": "q"}, TOP)
check("自帶 points 的 q 不借頂層 question_between", r is None and any("question_between" in x for x in e), e)
r, e = parse({"type": "timeline", "points": PA, "question_between": [0, 1], "step": "q"}, None)
check("自帶 question_between 可用", r is not None and not e, e)
r, e = parse({"type": "timeline", "points": [], "step": 0}, TOP)
check("points 為空陣列報錯", r is None and e, e)
r, e = parse({"type": "timeline", "points": "x", "step": 0}, TOP)
check("points 非陣列報錯", r is None and e, e)

# 2) 舊片相容:無自帶 points -> 頂層
r, e = parse({"type": "timeline", "step": 1}, TOP)
check("退回頂層 points", r is not None and not e, e)
r, e = parse({"type": "timeline", "step": "q"}, TOP)
check("退回頂層 question_between", r is not None and not e, e)
r, e = parse({"type": "timeline", "step": 2}, TOP)
check("頂層組 step 超出報錯", r is None and e, e)
r, e = parse({"type": "timeline", "step": 0}, None)
check("兩者皆無報錯", r is None and any("沒有 points" in x for x in e), e)

# 3) tl_meta
check("tl_meta 自帶優先", B.tl_meta({"points": PA}, TOP)["points"] == PA)
check("tl_meta 退回頂層", B.tl_meta({}, TOP) is TOP)
check("tl_meta 皆無 -> {}", B.tl_meta({}, None) == {})

# 4) 鏡頭合併:相同 points 合併;不同 points 不合併;頂層與自帶不合併
def tl(i, pts, step):
    a = {"type": "timeline", "step": step}
    if pts is not None:
        a["points"] = pts
    return ln(i, a)


runs = B.group_runs([tl(1, PA, 0), tl(2, PA, 1), tl(3, PB, 0), tl(4, PB, 1), tl(5, PA, 0)])
check("兩組 points 分成 3 鏡", [[x["idx"] for x in r["lines"]] for r in runs] == [[1, 2], [3, 4], [5]],
      [[x["idx"] for x in r["lines"]] for r in runs])
runs = B.group_runs([tl(1, None, 0), tl(2, None, 1), tl(3, None, 2)])
check("舊片頂層 step 連續同一鏡", len(runs) == 1)
runs = B.group_runs([tl(1, None, 0), tl(2, PA, 0)])
check("頂層與自帶 points 不合鏡", len(runs) == 2)
runs = B.group_runs([ln(1, {"type": "timeline", "points": PA, "src": "甲", "step": 0}),
                     ln(2, {"type": "timeline", "points": PA, "src": "甲", "step": 1})])
check("同組 points 帶 src 合鏡", len(runs) == 1)

# 5) 版面檢查吃該組 points
ok = B._check_src({"type": "timeline", "points": PA, "src": "出處"}, {"parts": [{"line": 1}], "lines": [1]}, None) \
    if hasattr(B, "_line_span") else []
check("_check_src 自帶 points 不丟例外", isinstance(ok, list), ok)

# 6) 動畫快取簽章:points 不同 -> 簽章不同(簽章含各句 anim)
check("anim dict 含 points 時 _jkey 不同",
      B._jkey({"type": "timeline", "points": PA, "step": 0}) != B._jkey({"type": "timeline", "points": PB, "step": 0}))

print("\n" + ("全部通過" if not FAILS else f"失敗 {len(FAILS)} 項:{FAILS}"))
sys.exit(1 if FAILS else 0)
