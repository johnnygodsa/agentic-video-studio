r"""段 B4 gate(配音稿)。規格:pipeline\docs\director_ab.md §5–§6。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import director as D  # noqa: E402
import paths as P  # noqa: E402
from gates import specs  # noqa: E402

IDS = ("tts_script", "接縫", "pron_review未決", "backlog前3")
BACKLOG_N = 3


def status(tag, ctx):
    """director status 用(原 director.check_b4,行為不變)。"""
    ts = P.build_dir(tag) / "tts_script.md"
    v3 = specs.flow(tag) == "v3"   # v3:pron_review.json 由程式寫(pron_pre),沒有 md
    pv = P.PROJECTS / tag / ("pron_review.json" if v3 else "pron_review.md")
    return [D._item("tts_script", ts.exists(), "build\\<tag>\\tts_script.md 沒有", ts),
            D._item("pron_review", pv.exists(), f"{pv.name} 沒有", pv)]


def backlog_rows(tag):
    """pron_backlog.md 本片的「待規則」列,命中多的在前,取前 3。"""
    import pron_backlog as PB
    rows = [r for r in PB.load() if r["狀態"] == "待規則" and tag in r["來源片"]]
    return sorted(rows, key=lambda r: -int(r["命中次數"]))[:BACKLOG_N]


def backlog_pending(tag):
    """本片前 3 條裡 pron_apply.json 還沒處理紀錄的列。"""
    done = {(b.get("word"), b.get("context")) for b in (D._read_json(P.PROJECTS / tag / "pron_apply.json") or {}).get("backlog") or []}
    return [r for r in backlog_rows(tag) if (r["字"], r["語境詞"]) not in done]


def seam_count(tag):
    """build\\<tag>\\sub_scan.json 的接縫數(ckip 拆段 + 判讀取大者);沒有 = None。"""
    d = D._read_json(P.build_dir(tag) / "sub_scan.json")
    return None if d is None else max(int(d.get("seams") or 0), int(d.get("seams_judge") or 0))


def open_items(tag):
    """pron_review.json 狀態「未決」的條目;沒有檔 = None。"""
    d = D._read_json(P.PROJECTS / tag / "pron_review.json")
    return None if d is None else [i for i in d.get("items") or [] if i.get("status") == "未決"]


def run(tag, ver=None, ctx=None):
    """tts_script.md 比 script.txt 新;sub_scan 接縫 0;pron_review.json 未決 0;本片 backlog 前 3 條有處理紀錄。"""
    pd = P.PROJECTS / tag
    ts = P.build_dir(tag) / "tts_script.md"
    sc = P.REPO / tag / "script.txt"
    fresh = ts.exists() and sc.exists() and ts.stat().st_mtime >= sc.stat().st_mtime
    out = [D._item("tts_script", fresh, "tts_script.md 比 script.txt 新" if fresh else "tts_script.md 沒有或比 script.txt 舊", ts)]
    n = seam_count(tag)
    out.append(D._item("接縫", n == 0, "build\\<tag>\\sub_scan.json 沒有" if n is None else f"接縫 {n}",
                       P.build_dir(tag) / "sub_scan.json"))
    left = open_items(tag)
    out.append(D._item("pron_review未決", left == [], "pron_review.json 沒有" if left is None else f"未決 {len(left)} 條",
                       pd / "pron_review.json"))
    pend = backlog_pending(tag)
    out.append(D._item("backlog前3", not pend, f"未處理:{'、'.join(r['字'] + '|' + r['語境詞'] for r in pend) or '無'}"))
    return out
