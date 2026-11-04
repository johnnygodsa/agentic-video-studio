r"""段 C gate(配音凍結)。規格:pipeline\docs\director.md「run:C→E 串接」。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import director as D  # noqa: E402
import paths as P  # noqa: E402

IDS = ("C0試配", "品管", "freeze", "listen", "ear_e4", "唸法")


def status(tag, ctx):
    """director status 用(原 director.check_c,行為不變)。"""
    pd = P.PROJECTS / tag
    out = []
    c0 = pd / "c0_report.md"
    if not c0.exists():
        out.append(D._item("C0試配", False, "c0_report.md 沒有"))
    else:
        rj = D._read_json(pd / "c0_report.json") or {}
        wrong = D._count(rj.get("wrong"))
        out.append(D._item("C0試配", wrong == 0, f"C0 唸錯 {wrong}", c0))
    rv = P.build_dir(tag) / "tts_review.json"
    if not rv.exists():
        out.append(D._item("品管", False, "tts_review.json 沒有"))
    else:
        d = D._read_json(rv) or {}
        failed, timing = D._count(d.get("failed")), D._count(d.get("timing_errors"))
        out.append(D._item("品管", failed == 0 and timing == 0, f"品管未過 {failed}、時長預檢 {timing}", rv))
    fz = pd / "freeze.json"
    out.append(D._item("freeze", fz.exists(), "freeze.json 沒有", fz))
    ls = D._first(D._glob(P.output_dir(tag), "listen_v*.txt"))
    out.append(D._item("listen", ls, "output\\<tag>\\listen_v*.txt 沒有", ls))
    return out


def run(tag, ver, ctx=None):
    """硬擋:C0 唸錯 0;品管未過 0、時長預檢 0、新合成 0;freeze 與現配音文本一致;listen_<ver>.txt;ear_e4_<ver>.json;唸法未定 0(decide_<ver>.md,沒有檔 = 舊片相容,視為沒有待定)。"""
    pd = P.PROJECTS / tag
    out = []
    c0 = pd / "c0_report.json"
    rj = D._read_json(c0)
    if rj is None:
        out.append(D._item("C0試配", False, "c0_report.json 沒有"))
    else:
        wrong = D._count(rj.get("wrong"))
        out.append(D._item("C0試配", wrong == 0, f"C0 唸錯 {wrong}", c0))
    rv = P.build_dir(tag) / "tts_review.json"
    d = D._read_json(rv)
    if d is None:
        out.append(D._item("品管", False, "tts_review.json 沒有"))
    else:
        failed, timing = D._count(d.get("failed")), D._count(d.get("timing_errors"))
        new = D._count(d.get("new_synth"))  # 遠端匯回後才有此欄;沒有 = 0
        out.append(D._item("品管", failed == 0 and timing == 0 and new == 0,
                           f"品管未過 {failed}、時長預檢 {timing}、新合成 {new}", rv))
    fz = pd / "freeze.json"
    if not fz.exists():
        out.append(D._item("freeze", False, "freeze.json 沒有"))
    else:
        import freeze as FZ
        msg = FZ.check(tag)
        out.append(D._item("freeze", msg is None, msg or "narration_sha 與現文本一致", fz))
    ls = P.output_dir(tag) / f"listen_{ver}.txt"
    out.append(D._item("listen", ls.exists(), f"output\\<tag>\\listen_{ver}.txt 沒有", ls))
    ear = pd / f"ear_e4_{ver}.json"
    out.append(D._item("ear_e4", ear.exists(), f"ear_e4_{ver}.json 沒有", ear))
    import decide_list as DL
    dec = P.output_dir(tag) / f"decide_{ver}.md"
    n = DL.count_undecided(tag, ver)
    if not dec.exists():
        out.append(D._item("唸法", True, f"decide_{ver}.md 不存在,視為沒有待定唸法(舊片相容)"))
    elif n is None:
        out.append(D._item("唸法", False, f"decide_{ver}.md 讀不出未定筆數(摘要行不符)", dec))
    else:
        out.append(D._item("唸法", sum(n) == 0, f"唸法未定 {sum(n)}(英文 {n[0]}、讀音 {n[1]})", dec))
    return out
