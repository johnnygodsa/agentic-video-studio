"""video_cost 測試:python -X utf8 -m pytest pipeline/tests/test_video_cost.py -q
用 tmp_path 合成 jsonl 當對話目錄,不讀真實 C 槽;known 與 cache_path 都明確傳入。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import video_cost as V  # noqa: E402

KNOWN = {"aaa_one", "bbb_two", "framework"}


def _ts(n):
    return f"2026-11-0{1 + n // 1000}T00:{(n // 60) % 60:02d}:{n % 60:02d}.000Z"


def A(n, mid, model="claude-sonnet-5-5", i=0, cc=0, cr=0, o=0, cmd=None):
    """assistant 訊息;cmd 給了就帶一個 Bash tool_use。"""
    content = [{"type": "text", "text": "x"}]
    if cmd:
        content.append({"type": "tool_use", "id": "t" + mid, "name": "Bash", "input": {"command": cmd}})
    return {"type": "assistant", "timestamp": _ts(n),
            "message": {"id": mid, "model": model, "content": content,
                        "usage": {"input_tokens": i, "cache_creation_input_tokens": cc, "cache_read_input_tokens": cr, "output_tokens": o}}}


def U(n, text):
    return {"type": "user", "timestamp": _ts(n), "message": {"role": "user", "content": text}}


def TR(n):
    return {"type": "user", "timestamp": _ts(n), "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "bbb_two aaa_one"}]}}


def W(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def sub(dirp, parent, aid, rows, agent_type="core-dev"):
    p = dirp / parent / "subagents" / f"agent-{aid}.jsonl"
    W(p, rows)
    p.with_suffix("").with_suffix(".meta.json").write_text(json.dumps({"agentType": agent_type}), encoding="utf-8")


def run(tmp_path, known=KNOWN):
    return V.analyze([str(tmp_path / "conv")], tmp_path / "cache.json", known)


def test_eq_formula():
    assert V.eq_of(100, 1000, 10000, 20) == 100 + 1000 + 100 + 1000


def test_switch_tags_and_unattributed(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [
        U(1, "隨便聊聊"),
        A(2, "m0", o=10),                                                   # 未歸屬:eq 50 w 50
        U(3, "開始做 aaa_one 這支"),
        A(4, "m1", o=10),                                                   # aaa_one
        TR(5),                                                              # tool_result 內有 bbb_two,不可切換
        A(6, "m2", i=100, cmd=r"python -X utf8 pipeline\director.py run bbb_two --from A --to D"),  # 切到 bbb_two
        A(7, "m3", o=10),                                                   # bbb_two
        A(8, "m4", cmd=r"type <REPO_ROOT>\projects\aaa_one\brief.json"),  # 路徑切回 aaa_one
    ])
    r = run(tmp_path)
    assert r["tags"]["aaa_one"]["main"]["turns"] == 2 and r["tags"]["aaa_one"]["main"]["eq"] == 50
    assert r["tags"]["bbb_two"]["main"]["turns"] == 2 and r["tags"]["bbb_two"]["main"]["eq"] == 150
    un = r["unattr_days"]
    assert sum(v["main"]["turns"] for v in un.values()) == 1 and sum(v["main"]["eq"] for v in un.values()) == 50


def test_tag_patterns(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [
        A(1, "p1", cmd="python pipeline/run.py build --tag aaa_one --ver v1"),
        A(2, "p2", cmd=r"python pipeline\script_lint.py bbb_two"),
        A(3, "p3", cmd=r"edit <REPO_ROOT>\aaa_one\script.txt"),
    ])
    r = run(tmp_path)
    assert r["tags"]["aaa_one"]["main"]["turns"] == 2 and r["tags"]["bbb_two"]["main"]["turns"] == 1


def test_weak_tag_not_from_user_text(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [U(1, "這個 framework 很好用"), A(2, "w1", o=1),
                       A(3, "w2", cmd=r"cat <LOCAL_PATH>/x\projects\framework\a.json"), A(4, "w3", o=1)])
    r = run(tmp_path)
    assert sum(v["main"]["turns"] for v in r["unattr_days"].values()) == 1  # w1
    assert r["tags"]["framework"]["main"]["turns"] == 2  # 強模式(路徑)才切換


def test_subagent_own_tag_and_inherit(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [U(1, "做 aaa_one"), A(2, "m1", o=1), U(100, "改做 bbb_two"), A(101, "m2", o=1)])
    sub(d, "m1", "s1", [U(110, "請處理 projects\\aaa_one\\spec.json"), A(111, "s1a", o=10)], "researcher")   # 自有 tag
    sub(d, "m1", "s2", [U(120, "沒有片名的 prompt"), A(121, "s2a", o=20)], "asset-collector")          # 繼承父 = bbb_two
    sub(d, "m1", "s3", [U(5, "早期沒片名"), A(6, "s3a", o=40)], "core-dev")                             # 啟動時父已是 aaa_one
    r = run(tmp_path)
    a, b = r["tags"]["aaa_one"], r["tags"]["bbb_two"]
    assert a["subs"]["researcher"]["eq"] == 50 and a["subs"]["core-dev"]["eq"] == 200
    assert b["subs"]["asset-collector"]["eq"] == 100 and "researcher" not in b["subs"]
    assert V.conv_totals(a)["sub_eq"] == 250 and a["sessions"] == {"m1"}


def test_subagent_before_any_tag_is_unattributed(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [U(1, "hi"), A(2, "m1", o=1)])
    sub(d, "m1", "s1", [U(3, "no tag"), A(4, "s1a", o=10)])
    r = run(tmp_path)
    assert not r["tags"] and sum(v["sub"]["turns"] for v in r["unattr_days"].values()) == 1


def test_cross_file_dedup(tmp_path):
    d = tmp_path / "conv"
    rows = [U(1, "做 aaa_one"), A(2, "m1", o=10), A(3, "m2", o=10)]
    W(d / "a_orig.jsonl", rows)
    W(d / "b_fork.jsonl", rows + [A(4, "m3", o=10)])   # fork 複製舊訊息,只多一則
    r = run(tmp_path)
    m = r["tags"]["aaa_one"]["main"]
    assert m["turns"] == 3 and m["eq"] == 150


def test_streaming_same_id_takes_max_usage(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [U(1, "做 aaa_one"), A(2, "m1", o=2), A(3, "m1", o=10)])
    m = run(tmp_path)["tags"]["aaa_one"]["main"]
    assert m["turns"] == 1 and m["out"] == 10


def test_model_weights(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [U(1, "做 aaa_one"),
                       A(2, "o", "claude-opus-5", o=10), A(3, "s", "claude-sonnet-5-5", o=10),
                       A(4, "h", "claude-haiku-5", o=30), A(5, "f", "fable-5-1", o=10), A(6, "x", "<synthetic>", o=10)])
    m = run(tmp_path)["tags"]["aaa_one"]["main"]
    assert abs(m["w"] - (50 * 5 + 50 + 150 / 3 + 50 * 5 + 50)) < 1e-6
    assert m["eq"] == 50 + 50 + 150 + 50 + 50


def test_cache_hit_and_invalidate(tmp_path):
    d = tmp_path / "conv"
    f = d / "m1.jsonl"
    W(f, [U(1, "做 aaa_one"), A(2, "m1", o=10)])
    st = {}
    V.load_files([str(d)], tmp_path / "cache.json", st)
    assert st == {"hit": 0, "miss": 1}
    V.load_files([str(d)], tmp_path / "cache.json", st)
    assert st == {"hit": 1, "miss": 0}
    W(f, [U(1, "做 aaa_one"), A(2, "m1", o=10), A(3, "m2", o=10)])
    V.load_files([str(d)], tmp_path / "cache.json", st)
    assert st == {"hit": 0, "miss": 1}
    assert run(tmp_path)["tags"]["aaa_one"]["main"]["turns"] == 2


def test_usage_for_tag_shape(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [U(1, "做 aaa_one"), A(2, "m1", "claude-opus-5", i=10, cc=20, cr=100, o=5)])
    sub(d, "m1", "s1", [U(3, "x"), A(4, "s1a", o=10)])
    u = V.usage_for_tag("aaa_one", res=run(tmp_path))
    assert u["sessions"] == ["m1"] and u["turns"] == 2 and u["output"] == 15
    assert u["main_eq"] == 10 + 20 + 25 + 10 and abs(u["main_w"] - 65 * 5) < 1e-6 and u["sub_w"] == 50
    assert V.usage_for_tag("bbb_two", res=run(tmp_path))["sessions"] == []


def test_readonly_commands_do_not_switch(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [
        U(1, "做 aaa_one"),
        A(2, "r1", o=1, cmd=r"python -X utf8 pipeline\director.py cost bbb_two"),
        A(3, "r2", o=1, cmd=r"python -X utf8 pipeline\video_cost.py bbb_two --json"),
        A(4, "r3", o=1, cmd=r"python -X utf8 pipeline\director.py usage bbb_two && python pipeline/stats.py --tag bbb_two"),
        A(5, "r4", o=1, cmd=r"python pipeline\director.py status bbb_two; python pipeline\director.py --explain C"),
        A(6, "r5", o=1, cmd=r"python channel\fable_token_review\scripts\session_usage.py --tag bbb_two"),
        A(7, "r6", o=1, cmd=r"python pipeline\director.py log bbb_two --fn x --model y --in 1 --out 1"),
    ])
    r = run(tmp_path)
    assert "bbb_two" not in r["tags"] and r["tags"]["aaa_one"]["main"]["turns"] == 6
    # 寫入類照常切換
    W(d / "m2.jsonl", [A(1, "w1", o=1, cmd=r"python pipeline\director.py intervene bbb_two --what x"),
                       A(2, "w2", o=1, cmd=r"python pipeline\director.py feedback bbb_two --text x"),
                       A(3, "w3", o=1, cmd=r"python pipeline\director.py brief bbb_two --topic x")])
    assert run(tmp_path)["tags"]["bbb_two"]["main"]["turns"] == 3


def test_readonly_in_mixed_command_only_skips_that_segment(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [A(1, "m1", o=1, cmd=r"python pipeline\director.py cost aaa_one && python pipeline\director.py run bbb_two --from A --to D")])
    r = run(tmp_path)
    assert list(r["tags"]) == ["bbb_two"]


def test_subagent_prompt_readonly_inherits_parent(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [U(1, "做 aaa_one"), A(2, "m1", o=1)])
    sub(d, "m1", "s1", [U(10, r"請跑 python pipeline\video_cost.py bbb_two 並回報 bbb_two 的數字"), A(11, "s1a", o=10)])
    sub(d, "m1", "s2", [U(12, "統計 bbb_two 這片"), A(13, "s2a", o=10)])
    r = run(tmp_path)
    assert "bbb_two" not in r["tags"] and r["tags"]["aaa_one"]["subs"]["core-dev"]["turns"] == 2


def test_readonly_command_ignores_incidental_paths(tmp_path):
    d = tmp_path / "conv"
    W(d / "m1.jsonl", [A(1, "m1", o=1, cmd=r"cd <LOCAL_PATH>/x; python pipeline\director.py cost bbb_two | tail -3; python -c ""open('projects/bbb_two/production.json')""")])
    assert run(tmp_path)["tags"] == {}


# ---------- 用量快照 / 校準 / 中文片名 ----------

from datetime import datetime, timedelta, timezone  # noqa: E402

NOW = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)


def _snap(at, h5, week, h5_reset=None, week_reset=None):
    return dict(at=V._iso(at), h5=h5, h5_reset=V._iso(h5_reset or at + timedelta(hours=2)),
                week=week, week_reset=V._iso(week_reset or at + timedelta(days=3)))


def _idx(items):
    """items [(datetime, w)] → build_w_index 用的 extra 清單(沒有對話檔)。"""
    return V.build_w_index([], [(V._key(d), w) for d, w in items])


def test_calibrate_coefficients():
    at = NOW
    # 週視窗起點 = at+3d−7d = at−4d;五小時起點 = at+2h−5h = at−3h
    idx = _idx([(at - timedelta(days=3), 600.0), (at - timedelta(hours=2), 300.0), (at - timedelta(days=6), 9999.0)])
    cal = V.calibrate([_snap(at, 10, 30)], idx)
    assert cal["week"]["coef"] == (600 + 300) / 30       # 起點前的 9999 不算
    assert cal["h5"]["coef"] == 300 / 10                  # 五小時只含 at−3h 之後
    assert V.pct_of(450, cal) == 15.0 and V.fmt_pct(450, cal) == "15.0%"
    assert V.fmt_pct(450, None) == "-"


def test_calibrate_excludes_low_usage_and_takes_median_of_last_n():
    base = NOW
    items, snaps = [], []
    # 7 筆快照,每筆整週視窗 w = pct×(係數 k):前面幾筆係數很離譜,但只取最近 5 筆;第 8 筆 2% 不納入
    for i, (pct, k) in enumerate([(10, 1000.0), (10, 1000.0), (10, 10.0), (10, 20.0), (10, 30.0), (10, 40.0), (10, 50.0), (2, 99999.0)]):
        at = base + timedelta(days=10 * i)
        items.append((at - timedelta(days=1), pct * k))
        snaps.append(_snap(at, pct, pct))
    cal = V.calibrate(snaps, _idx(items))
    assert [r["pct"] for r in cal["week"]["rows"]] == [10] * 5         # 2% 排除、只留最近 5 筆
    assert cal["week"]["coef"] == 30.0                                   # 中位數(10,20,30,40,50 → 30)
    # 不足 N 筆時有幾筆用幾筆
    assert V.calibrate(snaps[:1], _idx(items))["week"]["coef"] == 1000.0


def test_calibrate_skips_snapshot_outside_window_and_empty():
    at = NOW
    idx = _idx([(at - timedelta(hours=1), 100.0)])
    bad = _snap(at, 10, 10, h5_reset=at - timedelta(hours=1))             # 快照時間已超過重設 → 不納入五小時
    cal = V.calibrate([bad], idx)
    assert "h5" not in cal and "week" in cal
    assert V.calibrate([], idx) == {}


def test_snapshot_roundtrip_and_now_line(tmp_path):
    p = tmp_path / "snap.jsonl"
    rec = V.add_snapshot(19, "2026-11-05T14:00:00Z", 32, "2026-11-10T01:59:59Z", fable=4, now=NOW, path=p)
    assert rec["at"] == "2026-11-05T12:00:00Z" and rec["fable"] == 4
    snaps = V.load_snapshots(p)
    assert len(snaps) == 1 and snaps[0]["week"] == 32
    idx = _idx([(NOW - timedelta(hours=1), 190.0), (NOW + timedelta(minutes=30), 40.0)])
    cal = V.calibrate(snaps, idx)                                         # h5 coef = 190/19 = 10
    line = V.now_line(snaps, idx, cal, now=NOW + timedelta(hours=1))
    assert "五小時 19% → 約 23%(+4.0%" in line and "重設剩 1h00m" in line
    assert "快照視窗已重設" in V.now_line(snaps, idx, cal, now=NOW + timedelta(hours=3))
    assert "尚無用量快照" in V.now_line([], idx, {})


def test_render_without_snapshots_is_w_only():
    rep = dict(segs=[], total=dict(n=0))
    r = dict(tag="aaa_one", director=rep, director_w=1e6, director_eq=1e6, conv=V.conv_totals(None), subs={}, main=V._blank(),
             total_w=1e6, total_eq=1e6)
    out = V.render_tag(r, None, {"aaa_one": "測試片"})
    assert out.startswith("測試片(aaa_one)") and "占週上限" not in out and "--snap" in out
    md = V.render_ledger([dict(tag="aaa_one", channel="", start="2026-11-01", director_w=1e6, conv_w=0, total_w=1e6,
                               total_eq=1e6, sessions=1)], {}, None, None, {"aaa_one": "測試片"})
    assert "| 週 %" not in md and "測試片(aaa_one)" in md and "--snap" in md


def test_render_with_calibration_shows_percent():
    cal = {"week": dict(coef=1e6, rows=[dict(at="2026-11-05T12:00:00Z", pct=30, w=3e7, coef=1e6)]),
           "h5": dict(coef=1e5, rows=[dict(at="2026-11-05T12:00:00Z", pct=10, w=1e6, coef=1e5)])}
    rep = dict(segs=[], total=dict(n=0))
    r = dict(tag="aaa_one", director=rep, director_w=0, director_eq=0, conv=V.conv_totals(None), subs={}, main=V._blank(),
             total_w=5e6, total_eq=5e6)
    out = V.render_tag(r, cal, {})
    assert "占週上限" in out and "5.0%(≈ 0.5 個五小時額度)" in out and out.splitlines()[0].startswith("aaa_one token")
    md = V.render_ledger([dict(tag="aaa_one", channel="", start="2026-11-01", director_w=0, conv_w=5e6, total_w=5e6,
                               total_eq=5e6, sessions=1)], {}, None, cal, {})
    assert "| 週 %" in md and "| 5.0% |" in md and "每 1% = 1.00M w" in md
    assert md.index("| 5.0% |") < md.index("5.00M |", md.index("| 5.0% |") + 5)   # 週 % 在前、總 w 在後


def test_names_display_and_ensure(tmp_path):
    p = tmp_path / "names.json"
    assert V.disp("x_y", {}) == "x_y" and V.disp("x_y", {"x_y": "某片"}) == "某片(x_y)"
    assert V.ensure_name("new_tag", "魔獸世界永恆十一月五日開服台灣玩家該站哪一服", p) is True
    names = V.load_names(p)
    assert names["new_tag"] == "魔獸世界永恆十一月五日開服"[:12] and len(names["new_tag"]) <= 12
    assert V.ensure_name("new_tag", "別的題目", p) is False and V.load_names(p)["new_tag"] == names["new_tag"]   # 已有不覆蓋
    assert V.ensure_name("t2", "", p) is False
