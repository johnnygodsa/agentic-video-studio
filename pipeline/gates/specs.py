r"""片型規格單一來源(由 channel\規則\1_選題.md §3 搬入)與片長估算。規格:pipeline\docs\director_ab.md §3。

python -X utf8 pipeline\gates\specs.py   重量 SPEECH_CPM(最近 6 支有 timeline_tts.json 的片)
"""
import json
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths as P  # noqa: E402

UNSET = {"target": None, "floor": None}
FORMATS = {
    ("ChannelA", "評論片"): {"target": (7, 10), "floor": 6},
    ("ChannelA", "主場片"): {"target": (10, 15), "floor": 6},  # 上市窗主場片
    ("ChannelA", "長篇"): {"target": (15, 30), "floor": 12},
    ("ChannelA", "搬運"): UNSET,
    ("ChannelB", "考據片"): {"target": (6, 10), "floor": 5},
    ("ChannelB", "長篇"): {"target": (12, 25), "floor": 10},
    ("ChannelB", "搬運"): UNSET,
    ("ChannelC", None): UNSET,
    ("ChannelC", None): UNSET,
}
DEFAULT_FORMAT = {"ChannelA": "評論片", "ChannelB": "考據片"}  # 舊片沒有 brief.json 時的片型
FALLBACK = {"target": (7, 10), "floor": 6}  # 頻道不明(舊片 board 沒填)比照ChannelA評論片
# 2026-10-31 量:最近 6 支(ea_me5 322.2、wow_return 306.0、ally_ai 307.2、fog_still 305.8、bioware_dei 333.1、horror_sound 305.8)
# 旁白字數(pace.count_chars)÷ 首句起點到末句終點分鐘 的中位數 306.6。規則寫的 330 偏快,估片長會少估約 7%。
SPEECH_CPM = 307


def channel_key(channel):
    """資料裡同時有 ChannelA / ChannelA;統一成 FORMATS 的頻道鍵。沒對到回原字串。"""
    channel = channel or ""
    return next((c for c, _ in FORMATS if c in channel), channel)


def known(channel, fmt):
    key = channel_key(channel)
    return (key, fmt) in FORMATS or (key, None) in FORMATS


def spec(channel, fmt=None):
    """回傳 {target:(下,上)|None, floor:分|None};floor None = 不限片長。"""
    key = channel_key(channel)
    if (key, None) in FORMATS:
        return dict(FORMATS[(key, None)])
    return dict(FORMATS.get((key, fmt or DEFAULT_FORMAT.get(key)), FALLBACK))


FLOWS = ("v2", "v3")  # v3 = PLAN_token重設計_2026-11-03 §2(b) 的 B 段;一支片內不切


def flow(tag):
    """brief.json 的 flow 鍵;缺或不認得 = "v2"(現行路徑)。"""
    try:
        f = json.loads((P.PROJECTS / tag / "brief.json").read_text(encoding="utf-8-sig")).get("flow")
    except (OSError, ValueError, AttributeError):
        return "v2"
    return f if f in FLOWS else "v2"


def est_minutes(tag):
    """估片長(分)= 送配音文字字數 ÷ SPEECH_CPM。script.txt 解析失敗或不存在回 0。"""
    import freeze as FZ
    import pace
    try:
        return sum(pace.count_chars(t) for t in FZ.narration_lines(tag)) / SPEECH_CPM
    except (OSError, ValueError):
        return 0.0


def measure_cpm(n=6):
    """最近 n 支 timeline_tts.json 的字/分;回傳 ([(tag, 字/分)], 中位數)。"""
    import pace
    files = sorted(P.BUILD.glob("*/timeline_tts.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    rows = []
    for f in files[:n]:
        lines = json.loads(Path(f).read_text(encoding="utf-8")).get("lines") or []
        if lines:
            mins = (lines[-1]["end"] - lines[0]["start"]) / 60
            rows.append((f.parent.name, round(sum(pace.count_chars(x.get("text", "")) for x in lines) / mins, 1)))
    return rows, statistics.median(r[1] for r in rows) if rows else 0.0


if __name__ == "__main__":
    rows, med = measure_cpm()
    print(rows, "中位數", med)
