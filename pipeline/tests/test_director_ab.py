"""director A→B4、gate_a/b/b4、specs、C 段改句迴圈:python -X utf8 -m pytest pipeline/tests/test_director_ab.py -q
假造產物放 repo tmp/ 下暫存目錄;LLM 用 AB.CALL 注入,檢查工具與 line_fix/speakable 用假物件,不真呼叫、不動 GPU、不 commit。"""
import json
import os
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director as D  # noqa: E402
import director_ab as AB  # noqa: E402
import paths  # noqa: E402
from gates import gate_a, gate_b, gate_b4, gate_d, specs  # noqa: E402

TAG = "demo"
SCRIPT = """@title 測試
# 一、開場
me_old|第一句話。 ;; {"f": ["F1"]}
img:debt|第二句話。

# 二、中段
anim|第三句話。 ;; {"anim": "x"}
"""
L1, L2, L3 = 3, 4, 7  # 三句旁白的 script.txt 行號
REAL_COMMIT = AB.commit_seg  # env fixture 換掉它,commit 測試用本尊


def _w(p, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _j(p, d):
    return _w(p, json.dumps(d, ensure_ascii=False))


def _r(data=None, ok=True, limited=False, error=""):
    return SimpleNamespace(ok=ok, data=data, limited=limited, error=error, text="")


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    root = base / f"test_director_ab_{uuid.uuid4().hex[:8]}"
    root.mkdir()
    for attr, sub in (("PROJECTS", "projects"), ("BUILD", "build"), ("OUTPUT", "output"), ("TMP", "tmp"), ("IMAGES", "images")):
        monkeypatch.setattr(paths, attr, root / sub)
    monkeypatch.setattr(paths, "REPO", root)
    monkeypatch.setattr(paths, "ROOT", root)
    monkeypatch.setenv("CV_BOARD_DIR", str(root / "channel"))
    (root / "channel").mkdir()
    (root / "projects" / TAG).mkdir(parents=True)
    monkeypatch.setattr(AB, "commit_seg", lambda tag, seg: None)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _pd(env):
    return env / "projects" / TAG


def _script(env, text=SCRIPT):
    return _w(env / TAG / "script.txt", text)


def _brief(env, **kw):
    _j(_pd(env) / "brief.json", {"tag": TAG, "topic": "t", "angle": "a", "channel": "ChannelA", "format": "評論片", **kw})


PLAN = {"consensus": ["甲", "乙", "丙"], "todo": ["查 X"],
        "claims": [{"id": "c1", "text": "論點", "source": "官網", "abs": "3 秒", "visual": "截圖", "block": "b1"}],
        "blocks": [{"title": "b1", "claim_ids": ["c1"], "est_sec": 420}]}


def _bad(items):
    return {i["id"] for i in items if not i["ok"]}


def _args(*extra, frm="A", to="B4"):
    return ["run", TAG, "--from", frm, "--to", to, *extra]


def _prod():
    return json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))


def _clean_tools(monkeypatch, sent=(), speak=None):
    """B 段檢查工具全換假:預設全過。"""
    speak = speak or {"lines": [], "errors": 0, "warns": 0}
    monkeypatch.setattr(gate_b, "lint_over", lambda tag: 0)
    monkeypatch.setattr(gate_b, "facts_stat", lambda tag: (0, 0, 0))
    monkeypatch.setattr(gate_b, "visual_errors", lambda tag, *e: 0)
    monkeypatch.setattr(gate_b, "sentence_hits", lambda tag: list(sent))
    monkeypatch.setattr(gate_b, "speak_report", lambda tag: speak)
    monkeypatch.setattr(gate_b, "missing_labels", lambda tag: [])
    monkeypatch.setattr(gate_b, "tool", lambda script, *a: (0, ""))


# ---------- specs ----------

def test_specs_lookup():
    assert specs.spec("ChannelA", "評論片") == {"target": (7, 10), "floor": 6}
    assert specs.spec("ChannelA", "長篇")["floor"] == 12
    assert specs.spec("ChannelB", "長篇") == {"target": (12, 25), "floor": 10} and specs.known("ChannelB", "長篇")
    assert specs.spec("ChannelB")["floor"] == 5  # 預設片型 = 考據片
    assert specs.spec("ChannelA", "搬運")["floor"] is None
    assert specs.spec("ChannelC", "隨便")["floor"] is None
    assert specs.spec("")["floor"] == 6
    assert specs.known("ChannelA", "長篇") and not specs.known("ChannelA", "短片") and specs.known("ChannelC", None)


def test_est_minutes(env):
    _script(env, f"@title x\n# 一、開場\nme_old|{'字' * specs.SPEECH_CPM}\n")
    assert specs.est_minutes(TAG) == pytest.approx(1.0)
    assert specs.est_minutes("nope") == 0.0


def test_gate_d_uses_brief_format(env, monkeypatch):
    out = env / "output" / TAG
    _w(out / f"{TAG}_v1.mp4")
    monkeypatch.setattr(gate_d, "probe_secs", lambda p: 11 * 60.0)
    assert "片長" not in _bad(gate_d.run(TAG, "v1", {"channel": "ChannelA"}))
    _brief(env, format="長篇")
    assert "片長" in _bad(gate_d.run(TAG, "v1", {"channel": "ChannelA"}))


# ---------- gate_a ----------

def _make_a(env):
    pd = _pd(env)
    _brief(env)
    _w(pd / "context.md")
    _j(pd / "plan.json", PLAN)
    _w(pd / "facts.md", "| F1 | 已證實 |\n")
    _j(pd / "assets_manifest.json", [{"claim": "c1", "kind": "screen", "path": "images/a.png", "hl": "", "ok": True}])


def test_gate_a_pass_and_each_fail(env):
    assert _bad(gate_a.run(TAG)) == set(gate_a.IDS)
    _make_a(env)
    assert not _bad(gate_a.run(TAG))
    pd = _pd(env)
    _j(pd / "plan.json", {**PLAN, "consensus": ["一"]})
    assert _bad(gate_a.run(TAG)) == {"玩家共識"}
    claims = [{**PLAN["claims"][0], "abs": ""}]
    _j(pd / "plan.json", {**PLAN, "claims": claims})
    assert _bad(gate_a.run(TAG)) == {"論點欄位"}
    _j(pd / "plan.json", PLAN)
    _w(pd / "facts.md", "| F1 | 待查 |\n")
    assert _bad(gate_a.run(TAG)) == {"facts待查0"}
    _w(pd / "facts.md", "| F1 | 已證實 |\n")
    _j(pd / "assets_manifest.json", [{"claim": "c1", "ok": False}])
    assert _bad(gate_a.run(TAG)) == {"素材manifest"}


def test_gate_a_short_needs_user_or_allow_short(env):
    _make_a(env)
    _j(_pd(env) / "plan.json", {**PLAN, "blocks": [{"title": "b", "claim_ids": [], "est_sec": 300}]})
    items = gate_a.run(TAG)
    assert _bad(items) == {"估片長"} and "要問使用者" in items[-1]["note"]
    _brief(env, allow_short=True)
    items = gate_a.run(TAG)
    assert not _bad(items) and "allow_short" in items[-1]["note"]
    _brief(env)
    _j(_pd(env) / "plan.json", {**PLAN, "blocks": [{"title": "b", "claim_ids": [], "est_sec": 390}]})
    items = gate_a.run(TAG)
    assert not _bad(items) and "低於目標 7 分" in items[-1]["note"]


def test_status_inference_moved_unchanged(env):
    ctx = {"channel": "ChannelA"}
    assert [i["id"] for i in D.check_a(TAG, ctx)] == ["context.md", "facts", "素材(clips)"]
    assert [i["id"] for i in D.check_b(TAG, ctx)] == ["script.txt", "visual_table", "玩家審"]
    assert [i["id"] for i in D.check_b4(TAG, ctx)] == ["tts_script", "pron_review"]


# ---------- gate_b ----------

def _make_b(env, monkeypatch, **tools):
    _script(env)
    _brief(env)
    _clean_tools(monkeypatch, **tools)
    monkeypatch.setattr(specs, "est_minutes", lambda tag: 8.0)
    _j(_pd(env) / "editor_review_r1.json", {"counts": {}, "items": []})
    _j(_pd(env) / "player_review_r1.json", {"counts": {}, "items": []})


def test_gate_b_no_script_all_fail(env):
    assert _bad(gate_b.run(TAG)) == set(gate_b.IDS)


def test_gate_b_pass_and_fail_items(env, monkeypatch):
    _make_b(env, monkeypatch)
    assert not _bad(gate_b.run(TAG))
    pd = _pd(env)
    _j(pd / "editor_review_r1.json", {"items": [{"line": 2, "type": "連貫"}]})
    _j(pd / "player_review_r1.json", {"items": [{"line": 1, "type": "關掉"}, {"line": 2, "type": "吵"}]})
    _j(pd / "ask_user.json", [{"line": 1}])
    assert _bad(gate_b.run(TAG)) == {"編輯審", "玩家審", "ask_user"}
    _j(pd / "editor_review_r1.json", {"revised": [2], "items": [{"line": 2, "type": "連貫"}]})
    _j(pd / "player_review_r2.json", {"items": [{"line": 2, "type": "吵"}]})  # 看最新輪
    (pd / "ask_user.json").unlink()
    assert not _bad(gate_b.run(TAG))
    monkeypatch.setattr(gate_b, "lint_over", lambda tag: 2)
    monkeypatch.setattr(gate_b, "facts_stat", lambda tag: (1, 0, 0))
    monkeypatch.setattr(gate_b, "visual_errors", lambda tag, *e: 1)
    monkeypatch.setattr(gate_b, "missing_labels", lambda tag: ["x"])
    monkeypatch.setattr(gate_b, "speak_report", lambda tag: {"lines": [], "errors": 3})
    assert _bad(gate_b.run(TAG)) == {"lint擋0", "facts_check", "visual_check", "標籤實檔", "speakable硬項"}


def test_gate_b_short_uses_est_minutes(env, monkeypatch):
    _make_b(env, monkeypatch)
    monkeypatch.setattr(specs, "est_minutes", lambda tag: 5.0)
    assert _bad(gate_b.run(TAG)) == {"估片長"}
    _brief(env, allow_short=True)
    assert not _bad(gate_b.run(TAG))


def test_warn_log_requires_kept_with_reason(env, monkeypatch):
    sent = [{"line": L1, "code": "LONG", "block": False, "why": "太長"}]
    _make_b(env, monkeypatch, sent=sent)
    _j(env / "build" / TAG / "structure.json", {"warnings": [{"code": "BLOCK_SEC", "line": 9, "text": "短"}]})
    assert _bad(gate_b.run(TAG)) == {"warn_log"}
    log = {f"lint:{L1}:LONG": {"action": "fixed", "reason": "x"}, "structure:9:BLOCK_SEC": {"action": "kept", "reason": ""}}
    _j(_pd(env) / "warn_log.json", log)
    assert len(gate_b.unrecorded(TAG)) == 2  # fixed 但還在、kept 沒理由 都不算
    log = {f"lint:{L1}:LONG": {"action": "kept", "reason": "故意"}, "structure:9:BLOCK_SEC": {"action": "kept", "reason": "題目短"}}
    _j(_pd(env) / "warn_log.json", log)
    assert not _bad(gate_b.run(TAG))


def test_gate_b_missing_dependency_is_ng_not_crash(env, monkeypatch):
    _make_b(env, monkeypatch)
    monkeypatch.setattr(gate_b, "speak_report", lambda tag: None)
    assert {"warn_log", "speakable硬項"} <= _bad(gate_b.run(TAG))


def test_missing_labels_real_parse(env):
    _script(env)
    assert gate_b.missing_labels(TAG) == ["img:debt", "me_old"]
    _j(_pd(env) / "clips.json", [{"tags": ["me_old"]}])
    _w(env / "images" / "em_debt.png")
    assert gate_b.missing_labels(TAG) == []


# ---------- gate_b4 ----------

def _make_b4(env, monkeypatch):
    _script(env)
    time.sleep(0.01)
    _w(env / "build" / TAG / "tts_script.md")
    _j(env / "build" / TAG / "sub_scan.json", {"seams": 0, "seams_judge": 0})
    _j(_pd(env) / "pron_review.json", {"items": [{"status": "已決"}, {"status": "可疑"}]})
    monkeypatch.setattr(gate_b4, "backlog_rows", lambda tag: [])


def test_gate_b4(env, monkeypatch):
    monkeypatch.setattr(gate_b4, "backlog_rows", lambda tag: [])
    assert _bad(gate_b4.run(TAG)) == {"tts_script", "接縫", "pron_review未決"}
    _make_b4(env, monkeypatch)
    assert not _bad(gate_b4.run(TAG))
    _j(env / "build" / TAG / "sub_scan.json", {"seams": 0, "seams_judge": 2})
    _j(_pd(env) / "pron_review.json", {"items": [{"status": "未決"}]})
    row = {"字": "打", "語境詞": "快打", "命中次數": "2", "狀態": "待規則", "來源片": TAG}
    monkeypatch.setattr(gate_b4, "backlog_rows", lambda tag: [row])
    assert _bad(gate_b4.run(TAG)) == {"接縫", "pron_review未決", "backlog前3"}
    _j(_pd(env) / "pron_apply.json", {"backlog": [{"word": "打", "context": "快打"}]})
    assert "backlog前3" not in _bad(gate_b4.run(TAG))


# ---------- brief / dry-run / check-only ----------

def test_brief_cmd(env, capsys):
    argv = ["brief", TAG, "--topic", "題", "--angle", "角", "--channel", "ChannelA", "--format", "評論片", "--url", "u1", "--url", "u2"]
    assert D.main(argv) == 0
    d = json.loads((_pd(env) / "brief.json").read_text(encoding="utf-8"))
    assert d["tag"] == TAG and d["urls"] == ["u1", "u2"] and "allow_short" not in d
    assert D.main(["brief", TAG, "--topic", "題", "--angle", "角", "--channel", "ChannelA", "--format", "不存在"]) == 2


def test_explain(env, capsys):
    assert D.main(["--explain", "B4"]) == 0
    assert "接縫" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        D.main([])


def test_dry_run_lists_all_steps(env, capsys):
    assert D.main(_args("--dry-run")) == 0
    out = capsys.readouterr().out
    for key in ("A/brief", "[卡點:待開工提問]", "A/context", "A/comments", "A/consensus", "A/research", "A/facts", "A/assets",
                "A/gate", "B/write", "B/speak", "B/lint", "B/editor", "B/player", "B/gate", "B4/pron", "B4/gate"):
        assert key in out, key
    assert not (D.prod_path(TAG)).exists()


def test_check_only_no_llm(env, monkeypatch, capsys):
    monkeypatch.setattr(AB, "CALL", lambda *a, **k: pytest.fail("不該呼叫 LLM"))
    monkeypatch.setattr(gate_b, "tool", lambda script, *a: pytest.fail("沒 script.txt 不該跑工具"))
    assert D.main(_args("--check-only")) == 3
    d = _prod()
    assert {"A", "B", "B4"} <= set(d["gates"]) and not d["gates"]["A"]["passed"]
    assert "NG  brief" in capsys.readouterr().out


def test_ver_required_for_cde(env, capsys):
    assert D.main(_args(to="C")) == 2


def test_no_brief_blocks(env):
    assert D.main(_args(to="A")) == 3
    b = _prod()["blocks"][-1]
    assert (b["seg"], b["step"], b["reason"]) == ("A", "brief", "待開工提問")


def test_precheck_from_b_needs_gate_a(env):
    assert D.main(_args(frm="B", to="B")) == 3
    assert _prod()["blocks"][-1]["step"] == "前置"


# ---------- A 段 ----------

def _fake_a(env, calls):
    def fake(tag, fn, prompt, **kw):
        calls.append((fn, kw.get("agent"), kw.get("model"), kw.get("effort")))
        if fn == "replan":
            time.sleep(0.03)  # Windows mtime 粒度,要比 facts 新
        if fn in ("consensus", "replan"):
            return _r(PLAN)
        if fn == "research":
            _w(_pd(env) / "facts_raw1.md")
        if fn == "facts":
            _w(_pd(env) / "facts.md", "| F1 | 已證實 |\n")
        if fn.startswith("assets_"):
            return _r({"items": [{"claim": "c1", "kind": fn[7:], "path": "p", "hl": "", "ok": True}]})
        return _r()
    return fake


def test_run_a_all_steps_then_skip(env, monkeypatch, capsys):
    _brief(env, urls=["https://x/1"])
    calls, cmds = [], []

    def fake_exec(tag, ver, seg, step, cmd):
        cmds.append(step)
        if step == "context":
            _w(_pd(env) / "context.md")
        if step == "comments":
            _w(_pd(env) / "comments_ref" / "abc.info.json", "{}")
        return 0, "", "=== m"

    committed = []
    monkeypatch.setattr(D, "_exec", fake_exec)
    monkeypatch.setattr(AB, "CALL", _fake_a(env, calls))
    monkeypatch.setattr(AB, "commit_seg", lambda tag, seg: committed.append(seg))
    assert D.main(_args(to="A")) == 0
    assert cmds == ["context", "comments"]
    assert [c[0] for c in calls[:4]] == ["consensus", "research", "facts", "replan"] and {c[0] for c in calls[4:]} == {"assets_screen", "assets_clip"}
    assert calls[0][1:3] == ("ab-planner", "sonnet") and calls[1][1:3] == ("researcher", "haiku") and calls[2][3] == "high"
    assert len(json.loads((_pd(env) / "assets_manifest.json").read_text(encoding="utf-8"))) == 2
    assert committed == ["A"] and _prod()["gates"]["A"]["passed"]
    calls.clear(), cmds.clear()
    assert D.main(_args(to="A")) == 0  # 產物比輸入新 = 全略過
    assert not calls and not cmds


def test_comments_without_urls_warns(env, monkeypatch):
    _brief(env)
    monkeypatch.setattr(D, "_exec", lambda *a: pytest.fail("沒網址不該跑"))
    AB.step_comments(TAG, {}, SimpleNamespace(ver=None))
    assert _prod()["warns"][-1]["step"] == "comments"


def test_limited_stops_with_block(env, monkeypatch):
    _brief(env)
    _w(_pd(env) / "context.md")
    monkeypatch.setattr(D, "_exec", lambda *a: (0, "", "m"))
    monkeypatch.setattr(AB, "CALL", lambda *a, **k: _r(ok=False, limited=True, error="用量上限"))
    assert D.main(_args(to="A")) == 3
    b = _prod()["blocks"][-1]
    assert (b["step"], b["reason"]) == ("consensus", "用量上限")


def test_validate_plan():
    assert AB._validate_plan(_r(PLAN)) is None
    assert "3–5" in AB._validate_plan(_r({**PLAN, "consensus": []}))
    assert "claims" in AB._validate_plan(_r({**PLAN, "claims": []}))


# ---------- 改句 ----------

def test_apply_lines_keeps_label_and_tail(env):
    _script(env)
    assert AB.script_rows(TAG) == {1: L1, 2: L2, 3: L3}
    assert AB.apply_lines(TAG, [{"line": 1, "new_line": "新第一句。"}, {"line": 2, "new_line": "x|新第二句。"},
                                {"line": 9, "new_line": "沒有"}, {"line": 3, "new_line": ""}]) == [1, 2]
    src = (env / TAG / "script.txt").read_text(encoding="utf-8").splitlines()
    assert src[L1 - 1] == 'me_old|新第一句。 ;; {"f": ["F1"]}' and src[L2 - 1] == "img:debt|新第二句。"
    assert src[L3 - 1].startswith("anim|第三句話。")


def test_revise_refused_when_frozen(env, monkeypatch):
    import freeze
    _script(env)
    _w(_pd(env) / "freeze.json", "{}")
    monkeypatch.setattr(freeze, "check", lambda tag: None)
    with pytest.raises(AB.Block):
        AB.revise(TAG, [{"line": 1}])


def test_lint_rounds_fix_then_clean(env, monkeypatch):
    _script(env)
    rounds = []
    states = [{"sent": [{"line": L1, "code": "VERDICT", "block": True, "why": "判決"}],
               "warns": [{"key": f"lint:{L2}:LONG", "check": "lint", "line": L2, "code": "LONG", "why": "長"}], "struct": []},
              {"sent": [], "warns": [], "struct": ["facts_check 未連結/狀態不符/錯誤 (1, 0, 0)"]},
              {"sent": [], "warns": [], "struct": []}]
    monkeypatch.setattr(AB, "lint_round", lambda tag: states[len(rounds)])

    def fix(tag, items, mode):
        rounds.append(("fix", items, mode))
        return {"fixed": [{"line": L1}], "unresolved": [{"line": L2, "why": "原文引言"}]}

    monkeypatch.setattr(AB, "_fix", fix)
    monkeypatch.setattr(AB, "revise", lambda tag, issues, warns=(), **k: rounds.append(("revise", issues)) or [])
    AB.step_lint(TAG)
    assert [r[0] for r in rounds] == ["fix", "revise"] and rounds[0][2] == "lint"
    assert {i["line"] for i in rounds[0][1]} == {L1, L2}
    assert gate_b.warn_log(TAG)[f"lint:{L2}:LONG"]["reason"] == "原文引言"


def test_lint_three_rounds_block(env, monkeypatch):
    st = {"sent": [{"line": L1, "code": "X", "block": True, "why": ""}], "warns": [], "struct": []}
    n = []
    monkeypatch.setattr(AB, "lint_round", lambda tag: st)
    monkeypatch.setattr(AB, "_fix", lambda *a: n.append(1) or {})
    with pytest.raises(AB.Block, match="3 輪"):
        AB.step_lint(TAG)
    assert len(n) == AB.MAX_LINT


def test_record_fix_prefers_reported_warn_log(env):
    w = [{"key": "lint:3:A", "line": 3}, {"key": "speak:4:B", "line": 4}]
    AB._record_fix(TAG, w, {"fixed": [{"line": 3}], "unresolved": [], "warn_log": [
        {"key": "speak:4:B", "action": "kept", "reason": "引言", "at": "t"}]})
    log = gate_b.warn_log(TAG)
    assert log["lint:3:A"]["action"] == "fixed" and log["speak:4:B"] ["reason"] == "引言"


def test_fix_refused_blocks(env, monkeypatch):
    monkeypatch.setattr(gate_b, "module", lambda n: SimpleNamespace(fix_lines=lambda *a, **k: {"refused": "已凍結"}))
    with pytest.raises(AB.Block, match="已凍結"):
        AB._fix(TAG, [], "qc")


def test_speak_loop(env, monkeypatch):
    bad = {"lines": [{"line": L1, "hits": [{"code": "NUM", "severity": "err", "why": "唸不出"}, {"code": "W", "severity": "warn"}]}], "errors": 1}
    seq = iter([bad, {"lines": [], "errors": 0}])
    monkeypatch.setattr(gate_b, "speak_report", lambda tag: next(seq))
    seen = []
    monkeypatch.setattr(AB, "_fix", lambda tag, items, mode: seen.append((items, mode)) or {})
    AB.step_speak(TAG)
    assert seen == [([{"line": L1, "reasons": ["NUM:唸不出"]}], "speak")]
    monkeypatch.setattr(gate_b, "speak_report", lambda tag: bad)
    with pytest.raises(AB.Block):
        AB.step_speak(TAG)


# ---------- 三審 ----------

def _reviewer(env, reports, log):
    """假 LLM:*_rN 寫 md 回 reports[fn];revise 回固定改句。"""
    def fake(tag, fn, prompt, **kw):
        log.append(fn)
        if fn == "revise":
            return _r({"items": [{"line": 1, "new_line": "改過。", "note": ""}], "kept": []})
        kind, _, n = fn.partition("_r")
        _w(_pd(env) / f"{kind}_review_r{n}.md")
        return _r(reports[fn])
    return fake


def _no_recheck(monkeypatch):
    monkeypatch.setattr(AB, "_recheck", lambda tag: None)


def test_editor_one_round_revise_marks_revised(env, monkeypatch):
    _script(env)
    log = []
    monkeypatch.setattr(AB, "CALL", _reviewer(env, {"editor_r1": {"counts": {"連貫斷點": 1}, "items": [{"line": 1, "type": "連貫"}, {"line": 3, "type": "報幕"}]}}, log))
    _no_recheck(monkeypatch)
    AB.step_editor(TAG)
    assert log == ["editor_r1", "revise"]
    d = json.loads((_pd(env) / "editor_review_r1.json").read_text(encoding="utf-8"))
    assert d["revised"] == [1] and not gate_b.open_items(d, ("連貫",))
    assert AB._review_round(TAG, "editor") is None  # 報告比 script 新 = 不再審


def test_player_two_rounds_clean(env, monkeypatch):
    _script(env)
    log = []
    monkeypatch.setattr(AB, "CALL", _reviewer(env, {"player_r1": {"counts": {}, "items": [{"line": 1, "type": "誇大"}]},
                                                    "player_r2": {"counts": {}, "items": [{"line": 2, "type": "吵"}]}}, log))
    _no_recheck(monkeypatch)
    AB.step_player(TAG)
    assert log == ["player_r1", "revise", "player_r2"]
    assert not (_pd(env) / "ask_user.json").exists()


def test_player_r1_clean_no_second_round(env, monkeypatch):
    _script(env)
    log = []
    monkeypatch.setattr(AB, "CALL", _reviewer(env, {"player_r1": {"counts": {}, "items": [{"line": 1, "type": "外行"}]}}, log))
    AB.step_player(TAG)
    assert log == ["player_r1"]


def test_player_r2_left_goes_ask_user_no_third(env, monkeypatch):
    _script(env)
    log = []
    monkeypatch.setattr(AB, "CALL", _reviewer(env, {"player_r1": {"counts": {}, "items": [{"line": 1, "type": "相反"}]},
                                                    "player_r2": {"counts": {}, "items": [{"line": 1, "type": "可疑"}, {"line": 2, "type": "吵"}]}}, log))
    _no_recheck(monkeypatch)
    with pytest.raises(AB.Block, match="要問使用者"):
        AB.step_player(TAG)
    assert log == ["player_r1", "revise", "player_r2"]
    ask = json.loads((_pd(env) / "ask_user.json").read_text(encoding="utf-8"))
    assert len(ask) == 1 and ask[0]["from"] == "player_review_r2.json"


def test_write_step_prompt_has_speakable_and_taste(env, monkeypatch):
    _brief(env)
    _w(env / "channel" / "taste" / "README.md", "| T01 | B | 開場摘要 | x |\n| T99 | C | 別段 | x |\n")
    monkeypatch.setattr(gate_b, "module", lambda n: SimpleNamespace(explain=lambda: "可唸規則"))
    monkeypatch.setattr(specs, "est_minutes", lambda tag: 99.0)  # 本測試只看 prompt,不測 P1 長度(見 test_write_length)
    seen = {}

    def fake(tag, fn, prompt, **kw):
        seen.update(prompt=prompt, **kw)
        _script(env)
        _w(_pd(env) / "outline.md")
        r = _r()
        assert kw["validate"](r) is None
        return r

    monkeypatch.setattr(AB, "CALL", fake)
    AB.step_write(TAG, {}, None)
    assert seen["agent"] == "script-writer" and seen["model"] == "opus" and seen["effort"] == "high"
    assert "可唸規則" in seen["prompt"] and "T01" in seen["prompt"] and "T99" not in seen["prompt"]
    assert "頻道_ChannelA.md" in seen["prompt"]


# ---------- B4 ----------

def test_only_added():
    assert AB._only_added({"a": {"b": 1}, "l": [1]}, {"a": {"b": 1, "c": 2}, "l": [1, 2], "x": 1})
    assert not AB._only_added({"a": 1}, {"a": 2}) and not AB._only_added({"a": 1}, {}) and not AB._only_added({"l": [1]}, {"l": [2]})


def test_apply_validate_restores_on_edit(env):
    f = _w(env / "pipeline" / "pron_rules.json", '{"a": 1}')
    check = AB._validate_apply(TAG, {"pron_rules.json": '{"a": 1}'}, [])
    assert check(_r({})) is None
    f.write_text('{"a": 2}', encoding="utf-8")
    assert "只能新增" in check(_r({}))
    assert f.read_text(encoding="utf-8") == '{"a": 1}'
    check = AB._validate_apply(TAG, {}, [{"字": "打", "語境詞": "快打"}])
    assert "打|快打" in check(_r({"backlog": []}))
    assert check(_r({"backlog": [{"word": "打", "context": "快打"}]})) is None


def test_pron_loop_until_clean(env, monkeypatch):
    _script(env)
    _w(env / "pipeline" / "pron_rules.json", "{}")
    log, reports = [], iter([{"items": [{"status": "未決", "word": "背"}]}, {"items": [{"status": "已決"}]}])

    def fake_exec(tag, ver, seg, step, cmd):
        log.append(step)
        if step == "tts_script":
            _w(env / "build" / TAG / "tts_script.md")
        if step == "sub_scan":
            _j(env / "build" / TAG / "sub_scan.json", {"seams": 0})
        return 0, "", "m"

    def fake(tag, fn, prompt, **kw):
        log.append(fn)
        if fn.startswith("pron_review"):
            _w(_pd(env) / "pron_review.md")
            return _r(next(reports))
        return _r({"added": [{"file": "pron_rules.json", "entry": "背"}], "backlog": []})

    _clean_tools(monkeypatch)
    monkeypatch.setattr(D, "_exec", fake_exec)
    monkeypatch.setattr(AB, "CALL", fake)
    monkeypatch.setattr(gate_b4, "backlog_rows", lambda tag: [])
    AB.step_pron(TAG, {}, SimpleNamespace(ver=None))
    assert log == ["tts_script", "sub_scan", "pron_review_r1", "pron_apply", "tts_script", "sub_scan", "pron_review_r2"]
    assert not _bad(gate_b4.run(TAG))


# ---------- C 段改句迴圈 ----------

def _qc_env(env, monkeypatch, reviews, ear=None):
    """每次 make_version 依序換 tts_review.json;回傳 fix 紀錄。"""
    _script(env)
    seq = iter(reviews)
    fixes = []

    def fake_exec(tag, ver, seg, step, cmd):
        assert "--freeze" not in cmd and "--tts-review" in cmd
        _j(env / "build" / TAG / "tts_review.json", next(seq))
        return 0, "", "m"

    monkeypatch.setattr(D, "_exec", fake_exec)
    monkeypatch.setattr(AB, "_fix", lambda tag, items, mode, call=None: fixes.append((items, mode)) or {"fixed": [{"line": i["line"]} for i in items]})
    if ear:
        _j(_pd(env) / "ear_e4_v1.json", ear)
    return fixes


A_VER = SimpleNamespace(ver="v1")
BAD = {"failed": [{"idx": 2, "fails": ["ASR"]}], "timing_errors": []}
GOOD = {"failed": [], "timing_errors": []}


def test_qc_clean_first_time(env, monkeypatch):
    assert not _qc_env(env, monkeypatch, [GOOD]) and AB.step_qc(TAG, {}, A_VER) is None


def test_qc_fix_then_pass_idx_to_file_line(env, monkeypatch):
    fixes = _qc_env(env, monkeypatch, [BAD, GOOD])
    AB.step_qc(TAG, {}, A_VER)
    assert fixes == [([{"line": L2, "reasons": ["ASR"]}], "qc")]


def test_qc_third_round_blocks_and_no_alias_loosening(env, monkeypatch):
    fixes = _qc_env(env, monkeypatch, [BAD, BAD, BAD, BAD])
    with pytest.raises(AB.Block, match="品管未過到第 3 輪"):
        AB.step_qc(TAG, {}, A_VER)
    assert len(fixes) == 3  # 第 3 輪那次是升級 Opus 改句(P4,見 test_qc_escalate.py),之後再驗仍未過才卡點


def test_qc_e4_garble_ignored_and_changed_line_not_blocked(env, monkeypatch):
    ear = {"results": {"1": {"flags": [{"kind": "garble", "char": "為"}]},
                       "3": {"flags": [{"kind": "runon", "char": "市", "expected": "pause"}]}}}
    fixes = _qc_env(env, monkeypatch, [GOOD, GOOD, GOOD], ear)
    AB.step_qc(TAG, {}, A_VER)  # E4 句改過仍有旗標 → 留給必聽,不擋
    assert [f[0][0]["line"] for f in fixes] == [L3] and "runon" in fixes[0][0][0]["reasons"][0]


def test_qc_timing_errors_map_to_lines(env, monkeypatch):
    _script(env)
    _j(env / "build" / TAG / "tts_review.json", {"failed": [], "timing_errors": ["句3 同圖 12 秒", "全片超長"]})
    hard, ear, orphan = AB.qc_issues(TAG, "v1", set())
    assert hard == [{"line": L3, "reasons": ["句3 同圖 12 秒"]}] and orphan == ["全片超長"]


def test_plan_steps_c_has_loop_before_freeze(env):
    a = SimpleNamespace(ver="v1", backend="local")
    names = [s["step"] for s in D.plan_steps(TAG, "C", {"title": "", "channel": ""}, a)]
    assert names.index("改句迴圈") < names.index("配音凍結")


# ---------- commit / log ----------

def _git_fake(results):
    calls = []
    seq = iter(results)

    def fake(*args):
        calls.append(args)
        rc, err = next(seq) if args[0] in ("add", "commit") else (1, "")
        return SimpleNamespace(returncode=rc, stdout="", stderr=err)

    return fake, calls


def test_commit_explicit_paths_and_retry(env, monkeypatch):
    monkeypatch.setattr(AB.time, "sleep", lambda s: None)
    _script(env)
    fake, calls = _git_fake([(1, "index.lock exists"), (0, ""), (0, "")])
    monkeypatch.setattr(AB, "_git", fake)
    assert REAL_COMMIT(TAG, "A") is True
    commit = [c for c in calls if c[0] == "commit"][0]
    assert commit[1:3] == ("-m", f"director {TAG}: A 過 gate")
    assert "--" in commit and f":(exclude)projects/{TAG}/comments_ref" in commit
    assert "." not in commit


def test_commit_failure_warns_only(env, monkeypatch):
    monkeypatch.setattr(AB.time, "sleep", lambda s: None)
    fake, _ = _git_fake([(1, "index.lock")] * 3)
    monkeypatch.setattr(AB, "_git", fake)
    assert REAL_COMMIT(TAG, "B") is False
    assert _prod()["warns"][-1]["step"] == "commit"


def test_log_call_compat_and_thread_safe(env):
    r = D.log_call(TAG, "x", "m", 1, 1)
    assert "secs" not in r and "agent" not in r
    r = D.log_call(TAG, "y", "m", 1, 1, 0, secs=1.5, ok=False, seg="B", agent="a")
    assert (r["secs"], r["ok"], r["seg"], r["agent"]) == (1.5, False, "B", "a")
    ts = [threading.Thread(target=D.log_call, args=(TAG, f"t{i}", "m", 1, 1)) for i in range(16)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(_prod()["llm_calls"]) == 18


# ---------- warn_log 句雜湊鍵 ----------

def _shift(env):
    """最前面加一句:後面行號全部 +1。"""
    _script(env, SCRIPT.replace("# 一、開場\n", "# 一、開場\nme_old|新加的一句。\n"))


def test_warn_key_survives_added_line(env, monkeypatch):
    sent = [{"line": L1, "code": "LONG", "block": False, "why": "太長"}]
    _make_b(env, monkeypatch, sent=sent)
    key = gate_b.warnings(TAG)[0]["key"]
    assert key == f"lint:{gate_b.sha8('第一句話。')}:LONG"
    _j(_pd(env) / "warn_log.json", {key: {"action": "kept", "reason": "故意"}})
    _shift(env)
    monkeypatch.setattr(gate_b, "sentence_hits", lambda tag: [{**sent[0], "line": L1 + 1}])
    assert not gate_b.unrecorded(TAG)


def test_warn_key_new_first_legacy_accepted(env, monkeypatch):
    _make_b(env, monkeypatch, sent=[{"line": L1, "code": "LONG", "block": False, "why": ""}])
    key = gate_b.warnings(TAG)[0]["key"]
    _j(_pd(env) / "warn_log.json", {f"lint:{L1}:LONG": {"action": "kept", "reason": "舊片"}})
    assert not gate_b.unrecorded(TAG)  # 舊的行號鍵也認
    _j(_pd(env) / "warn_log.json", {f"lint:{L1}:LONG": {"action": "kept", "reason": "舊片"}, key: {"action": "fixed", "reason": "x"}})
    assert len(gate_b.unrecorded(TAG)) == 1  # 新鍵優先


def test_warn_key_structure_uses_section_title(env, monkeypatch):
    _make_b(env, monkeypatch)
    _j(env / "build" / TAG / "structure.json", {"warnings": [{"code": "A", "line": L1, "text": ""}, {"code": "B", "line": 6, "text": ""},
                                                             {"code": "C", "line": 0, "text": ""}]})
    a, b, c = gate_b.warnings(TAG)
    assert a["key"] == f"structure:{gate_b.sha8('第一句話。')}:A"
    assert b["key"] == f"structure:{gate_b.sha8('一、開場')}:B" and b["legacy"] == "structure:6:B"
    assert c["key"] == f"structure:{gate_b.sha8('')}:C"


def test_record_fix_turns_line_keys_into_hash(env):
    _script(env)
    new, old = "改好的第二句。", "第二句話。"
    _script(env, SCRIPT.replace(old, new))
    h1, h2 = gate_b.sha8("第一句話。"), gate_b.sha8(old)
    _j(_pd(env) / "warn_log.json", {f"lint:{h2}:KEEP": {"action": "kept", "reason": "舊理由"}})
    AB._record_fix(TAG, [], {"fixed": [{"line": L2, "old": old, "new": new}], "warn_log": [
        {"key": f"speakable:{L1}:backlog", "action": "kept", "reason": "引言"}, {"key": f"lint:{L2}:LONG", "action": "fixed", "reason": "短了"}]})
    log = gate_b.warn_log(TAG)
    assert log[f"speak:{h1}:backlog"]["reason"] == "引言" and log[f"lint:{h2}:LONG"]["action"] == "fixed"
    assert log[f"lint:{gate_b.sha8(new)}:KEEP"]["reason"] == "舊理由"  # kept 跟到新句


# ---------- 審稿有效性與小範圍審 ----------

LONG = "@title 測試\n# 一、開場\n" + "".join(f"me_old|這是第{i}句,內容各不相同{i * 7}。\n" for i in range(1, 9))


def _report(env, kind, n, text, **kw):
    _script(env, text)
    _j(_pd(env) / f"{kind}_review_r{n}.json", {"counts": {}, "items": [], "narration": gate_b.narration_hashes(TAG), **kw})


def _mtime(path, offset):
    t = time.time() + offset
    os.utime(path, (t, t))


def _spot_fake(items, log):
    def fake(tag, fn, prompt, **kw):
        log.append((fn, prompt))
        return _r({"counts": {}, "items": items})
    return fake


def test_review_valid_when_only_tags_change(env):
    _report(env, "editor", 1, SCRIPT)
    _script(env, SCRIPT.replace("me_old|", "img:x|").replace('{"f": ["F1"]}', '{"hl": ["第一"]}').replace("@title 測試\n", "@title 測試\n@say 第三=第叁\n"))
    _mtime(env / TAG / "script.txt", 5)
    assert AB._review_state(TAG, "editor") == (None, [])


def test_review_old_report_falls_back_to_mtime(env):
    _script(env)
    _j(_pd(env) / "editor_review_r1.json", {"counts": {}, "items": []})
    _mtime(env / TAG / "script.txt", 5)
    assert AB._review_round(TAG, "editor") == 2


def test_review_small_change_editor_not_rerun_player_spot(env):
    _report(env, "editor", 1, LONG)
    _report(env, "player", 2, LONG)
    _script(env, LONG.replace("這是第3句", "這是改過的第3句"))
    _mtime(env / TAG / "script.txt", 5)
    assert AB._review_round(TAG, "editor") is None
    assert AB._review_state(TAG, "player") == (None, [3])


def _big(text):
    for i in range(1, 7):
        text = text.replace(f"這是第{i}句", f"這是改過的第{i}句")
    return text


def test_review_big_change_opens_next_round(env):
    _report(env, "editor", 1, LONG)
    _script(env, _big(LONG))
    assert AB._review_round(TAG, "editor") == 2


def test_changed_lines_insert_delete():
    assert AB.changed_lines(list("abcd"), list("abcd")) == (0, [])
    assert AB.changed_lines(list("abcd"), list("abXcd")) == (1, [3])
    assert AB.changed_lines(list("abcd"), list("acd")) == (1, [2])
    assert AB.changed_lines(list("abcd"), list("abc")) == (1, [3])


def test_player_spot_after_two_rounds_no_block_no_round(env, monkeypatch):
    _report(env, "player", 2, LONG)
    _script(env, LONG.replace("這是第3句", "這是改過的第3句"))
    log = []
    monkeypatch.setattr(AB, "CALL", _spot_fake([{"line": 3, "type": "吵"}], log))
    AB.step_player(TAG)
    assert [x[0] for x in log] == ["player_spot1"]
    prompt = log[0][1]
    assert ">> 3. 這是改過的第3句" in prompt and "   2. 這是第2句" in prompt and "   4. 這是第4句" in prompt and "這是第5句" not in prompt
    assert not (_pd(env) / "player_review_r3.json").exists() and (_pd(env) / "player_spot_1.json").exists()
    assert AB._review_state(TAG, "player") == (None, [])  # 審過了,重跑不再審


def test_player_spot_must_goes_ask_user_no_revise(env, monkeypatch):
    _report(env, "player", 1, LONG)
    _script(env, LONG.replace("這是第3句", "這是改過的第3句"))
    _j(_pd(env) / "ask_user.json", [{"from": "x"}])
    log = []
    monkeypatch.setattr(AB, "CALL", _spot_fake([{"line": 3, "type": "可疑"}, {"line": 3, "type": "吵"}], log))
    with pytest.raises(AB.Block, match="要問使用者"):
        AB.step_player(TAG)
    assert [x[0] for x in log] == ["player_spot1"]  # 沒有 revise
    ask = json.loads((_pd(env) / "ask_user.json").read_text(encoding="utf-8"))
    assert len(ask) == 2 and ask[1]["from"] == "player_spot_1.json"
    assert AB._review_state(TAG, "player") == (None, [])


def test_player_big_change_after_two_rounds_still_blocks(env, monkeypatch):
    _report(env, "player", 2, LONG)
    _script(env, _big(LONG))
    with pytest.raises(AB.Block, match="要主對話決定"):
        AB.step_player(TAG)


def test_player_r1_revised_interrupted_goes_r2(env):
    _report(env, "player", 1, LONG, revised=[3])
    _script(env, LONG.replace("這是第3句", "這是改過的第3句"))
    assert AB._review_state(TAG, "player") == (2, [])


def test_review_writes_narration_and_editor_seals_after_revise(env, monkeypatch):
    _script(env)
    log = []
    monkeypatch.setattr(AB, "CALL", _reviewer(env, {"editor_r1": {"counts": {}, "items": [{"line": 1, "type": "連貫"}]}}, log))
    _no_recheck(monkeypatch)
    AB.step_editor(TAG)
    d = json.loads((_pd(env) / "editor_review_r1.json").read_text(encoding="utf-8"))
    assert d["narration"] == gate_b.narration_hashes(TAG) and len(d["narration"]) == 3


# ---------- 改稿回歸檢查 ----------

def test_regress_title_replaced():
    assert "專名" in AB.regress_why("《影之刃零》開賣第三天,同時在線破紀錄。", "本作零開賣第三天,同時在線破紀錄。")
    assert "專名" in AB.regress_why("影之刃零開賣第三天,同時在線破紀錄。", "新作開賣第三天,同時在線破紀錄。", names=["影之刃零"])
    assert "專名" in AB.regress_why("開賣後官方沒發修正公告,最新的還是《理智與瘋狂》那封長信。",
                                    "理智與瘋狂開賣後沒發修正公告,最新的還是那封開賣前的長信。")
    assert AB.regress_why("《影之刃零》開賣第三天。", "《影之刃零》開賣到第三天。", names=["影之刃零"]) is None


def test_regress_number_lost_unless_reason_says_so():
    old, new = "峰值第二天又往上推,超過 73.1 萬人,排進史上前段。", "峰值第二天又往上推,人數超過很多,排進史上前段。"
    assert "數字" in AB.regress_why(old, new)
    assert AB.regress_why(old, new, reason="NUMS:一句數字太多") is None
    assert AB.regress_why(old, new, reason="查證後 73.1 不能講") is None
    assert "數字" in AB.regress_why(old, new, reason="CLAUSE_LONG:最長子句 23 字")
    assert AB.regress_why(old, old.replace("73.1 萬人", "73.1 萬名玩家")) is None


def test_regress_adjacent_repeat():
    side = "繁體中文的負評,嫌戰鬥像是雙方各自跳舞,起步就低在這。"
    old, new = "中文區的玩家都說打起來沒感覺,手感不對。", "中文區的玩家都說戰鬥像是雙方各自跳舞,打起來沒感覺。"
    assert "相鄰" in AB.regress_why(old, new, prev=side)
    assert "相鄰" in AB.regress_why(old, new, nxt=side)
    assert "相鄰" in AB.regress_why(old, side, prev=side)
    assert AB.regress_why(old, new, prev="接著看評分,Metacritic 上 PC 版平均八十八分,比預期高不少。") is None


def test_regress_too_short():
    assert "字數" in AB.regress_why("這一句本來講得很長,後面還有一段補充說明。", "這一句本來很長。")
    assert AB.regress_why("這一句本來講得很長。", "這一句講得很長。") is None


def test_changed_pairs_unmatched_left_alone():
    assert AB.changed_pairs(["a", "b", "c"], ["a", "X", "c"]) == [(1, 1)]
    assert AB.changed_pairs(["a", "b", "c"], ["a", "X", "Y", "c"]) == []  # 句數變動對不到
    assert AB.changed_pairs(["a", "b", "c", "d"], ["a", "X", "c", "d", "e"]) == [(1, 1)]


REG = """@title 測試
# 一、開場
me_old|《影之刃零》開賣第三天,同時在線破紀錄。
img:debt|第二句話講別的事情,跟前面沒有關係。 ;; {"hl": ["別的事情"]}
anim|第三句話再換一個方向,也不一樣。
"""
RL1, RL2 = 3, 4
TITLE_LINE = "《影之刃零》開賣第三天,同時在線破紀錄。"


def _fake_line_fix(env, monkeypatch, changes, seen):
    def fix_lines(tag, items, mode, call=None):
        seen.append([i["line"] for i in items])
        p = env / TAG / "script.txt"
        text = p.read_text(encoding="utf-8")
        fixed = []
        for no, old, new in changes:
            if no in {i["line"] for i in items}:
                text = text.replace(old, new)
                fixed.append({"line": no, "old": old, "new": new})
        p.write_text(text, encoding="utf-8")
        return {"fixed": fixed, "unresolved": [], "warn_log": [{"key": f"lint:{no}:X", "action": "fixed", "reason": "n"} for no, _o, _n in changes]}
    monkeypatch.setattr(gate_b, "module", lambda n: SimpleNamespace(fix_lines=fix_lines))


def test_fix_rolls_back_bad_line_and_never_retries(env, monkeypatch):
    _script(env, REG)
    seen = []
    _fake_line_fix(env, monkeypatch, [(RL1, TITLE_LINE, "本作零開賣第三天,同時在線破紀錄。")], seen)
    res = AB._fix(TAG, [{"line": RL1, "reasons": ["X:長"]}], "lint")
    AB._record_fix(TAG, [{"key": "lint:k:X", "line": RL1}], res)
    assert (env / TAG / "script.txt").read_text(encoding="utf-8") == REG
    log = gate_b.warn_log(TAG)
    assert log["lint:k:X"]["action"] == "kept" and "回歸檢查退回" in log["lint:k:X"]["reason"]
    assert log[f"regress:{gate_b.sha8(TITLE_LINE)}"]["action"] == "kept"
    assert not res["fixed"] and not res["warn_log"]
    res = AB._fix(TAG, [{"line": RL1, "reasons": ["X:長"]}, {"line": RL2, "reasons": ["Y:長"]}], "lint")
    assert seen == [[RL1], [RL2]]  # 同一句不再送
    assert any(u["line"] == RL1 for u in res["unresolved"])
    AB._fix(TAG, [{"line": RL1, "reasons": ["X:長"]}], "lint")
    assert seen == [[RL1], [RL2]]  # 全部鎖住 = 不呼叫 LLM


def test_fix_qc_not_guarded(env, monkeypatch):
    _script(env, REG)
    new = "本作零開賣第三天,同時在線破紀錄。"
    _fake_line_fix(env, monkeypatch, [(RL1, TITLE_LINE, new)], [])
    res = AB._fix(TAG, [{"line": RL1, "reasons": ["qc"]}], "qc")
    assert res["fixed"] and new in (env / TAG / "script.txt").read_text(encoding="utf-8")


def _revise_fake(items, log=None):
    def fake(tag, fn, prompt, **kw):
        if log is not None:
            log.append(fn)
        return _r({"items": items, "kept": []})
    return fake


def test_revise_rolls_back_bad_sentence_keeps_good(env, monkeypatch):
    _script(env, REG)
    monkeypatch.setattr(AB, "CALL", _revise_fake([{"line": 1, "new_line": "本作零開賣第三天,同時在線破紀錄。", "note": ""},
                                                  {"line": 3, "new_line": "第三句話往另一個方向走,說法也不同。", "note": ""}]))
    done = AB.revise(TAG, [{"line": 1, "reason": "太長", "fix": ""}, {"line": 3, "reason": "報幕", "fix": ""}])
    text = (env / TAG / "script.txt").read_text(encoding="utf-8")
    assert done == [3] and "《影之刃零》" in text and "第三句話往另一個方向走" in text
    assert "專名" in gate_b.warn_log(TAG)[f"regress:{gate_b.sha8(TITLE_LINE)}"]["reason"]


def test_revise_hl_text_lost_rolled_back(env, monkeypatch):
    _script(env, REG)
    monkeypatch.setattr(AB, "CALL", _revise_fake([{"line": 2, "new_line": "第二句話講其他的方向,跟前面沒有關係。", "note": ""}]))
    assert AB.revise(TAG, [{"line": 2, "reason": "x", "fix": ""}]) == []
    assert "別的事情" in (env / TAG / "script.txt").read_text(encoding="utf-8")


def test_revise_locked_sentence_not_resent(env, monkeypatch):
    _script(env, REG)
    AB.merge_warn_log(TAG, {f"regress:{gate_b.sha8(TITLE_LINE)}": {"action": "kept", "reason": "回歸檢查退回"}})
    log = []
    monkeypatch.setattr(AB, "CALL", _revise_fake([], log))
    assert AB.revise(TAG, [{"line": 1, "reason": "x"}]) == [] and log == []


def test_revise_rollback_keeps_warn_as_kept(env, monkeypatch):
    _script(env, REG)
    monkeypatch.setattr(AB, "CALL", _revise_fake([{"line": 1, "new_line": "新作開賣第三天,同時在線破紀錄。", "note": ""}]))
    AB.revise(TAG, ["結構問題"], [{"key": "structure:k:NO_LANDING", "line": RL1, "why": "x"}, {"key": "structure:k2:Z", "line": 99, "why": "y"}])
    log = gate_b.warn_log(TAG)
    assert log["structure:k:NO_LANDING"]["action"] == "kept" and "回歸檢查退回" in log["structure:k:NO_LANDING"]["reason"]
    assert log["structure:k2:Z"]["action"] == "fixed"


# ---------- write 不因 facts 重寫 ----------

def _write_step():
    return next(s for s in AB.steps(TAG, "B", {}, None) if s["step"] == "write")


def test_write_skip_ignores_newer_facts(env, capsys, monkeypatch):
    pd = _pd(env)
    _script(env)
    _w(pd / "plan.json", "{}")
    _w(pd / "assets_manifest.json", "{}")
    _mtime(pd / "plan.json", -50)
    _mtime(pd / "assets_manifest.json", -50)
    _mtime(env / TAG / "script.txt", -20)
    _w(pd / "facts.md")
    assert _write_step()["skip"]()
    assert "比 script.txt 新" in capsys.readouterr().out
    _mtime(pd / "plan.json", 5)
    assert _write_step()["skip"]()  # B5:plan 較新也不重寫
    monkeypatch.setenv("CV_REWRITE", "1")
    assert _write_step()["skip"]() is None  # 要重寫才設 CV_REWRITE=1
