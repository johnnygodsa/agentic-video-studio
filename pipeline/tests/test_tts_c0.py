"""C0 試配測試(不載模型、假的合成與讀音):挑句、判定寫記憶、報告、結束碼、dispatch 閘門。
python -X utf8 -m pytest pipeline/tests/test_tts_c0.py"""
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import pron_memory as PM  # noqa: E402
import tts_c0 as C0  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import tts_dispatch as TD  # noqa: E402

SAY = "你用補血道具。"
READ = {"寫": "xie3", "穴": "xue4"}
ALL = {"血": {"xie3", "xue4"}}


class FakePhon:
    def one(self, c):
        return READ.get(c, c)

    def all(self, c):
        return ALL.get(c, {self.one(c)})

    def key(self, c, py=None):
        return re.sub(r"\d", "", py or self.one(c))


def norm(s):
    return re.sub(r"[，。！？、,\s]+", "", s)


def fakes():
    return dict(norm=norm, ph=FakePhon(), reading=lambda v: "xie3", simp=lambda c: c)


@pytest.fixture
def env(tmp_path, monkeypatch):
    e = type("E", (), {})()
    e.says, e.asr, e.calls, e.locks = [SAY], {}, [], []
    monkeypatch.setattr(PM, "MEM_FILE", tmp_path / "mem.json")
    PM._CACHE.clear()
    monkeypatch.setattr(C0.P, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(C0.P, "REPO", tmp_path)
    monkeypatch.setattr(C0.P, "TMP", tmp_path / "tmp")
    monkeypatch.setattr(C0.SC, "script_lines", lambda tag: [(dict(text=s), s) for s in e.says])
    monkeypatch.setattr(C0, "g2p_disagree", lambda tag, units, compute=True: ([[] for _ in units], "g2p 測試略過"))
    monkeypatch.setattr(C0, "english_of", lambda says, units: e.english if hasattr(e, "english") else {})
    monkeypatch.setattr(C0, "backlog_table", lambda: [])

    def synth(items, seeds, work, max_retry):
        e.calls.append((len(items), list(seeds), max_retry))
        for s in seeds:
            for it in items:
                f = C0.V.out_wav(work, s, it).with_suffix(".qc.json")
                f.parent.mkdir(parents=True, exist_ok=True)
                asr = e.asr.get(s, e.asr.get("*", lambda t: t))(it["mtext"])
                f.write_text(json.dumps(dict(text=it["say"], measure_text=it["mtext"], asr=asr, asr2=asr, sim=0.95, asr2_sim=0.95, pron_bad=0,
                                             asr2_bad=False, term_misread=getattr(e, "term_misread", []))), encoding="utf-8")
        return []
    monkeypatch.setattr(C0.V, "synth", synth)

    @contextmanager
    def lock(tag, job):
        e.locks.append((tag, job))
        yield
    monkeypatch.setattr(C0.V.GL, "gpu_lock", lock)
    yield e
    PM._CACHE.clear()


def blood(sub):
    return lambda t: t.replace("血", sub)


# ------------------------------------------------------------ 純函式
def test_pos_map_handles_replaced_terms():
    m = C0.pos_map("藝電的血", "EA的血")
    assert m[3] == 3 and m[2] == 2 and 0 not in m


def test_units_are_clauses_and_dedup():
    us = C0.units_of(["第一句。第二句!", "第一句。"])
    assert [u["say"] for u in us] == ["第一句。", "第二句!"] and us[1]["line"] == 1


def test_cover_and_select():
    cands = {0: {"a"}, 1: {"a", "b"}, 2: {"c"}, 3: {"d"}}
    assert C0.cover(cands) == [1, 2, 3]
    assert C0.select(cands, {}, limit=3) == [1, 2, 3]
    assert C0.select(cands, {"d": 9}, limit=1) == [3]
    assert C0.cover({}) == []


# ------------------------------------------------------------ 計畫
def test_plan_finds_rule_position_and_context(env):
    p = C0.build_plan("t")
    assert len(p["items"]) == 1
    xs = {x["ch"]: x for x in p["items"][0]["positions"]}
    assert xs["血"]["value"] == "[x][iě]" and xs["血"]["ctx"] == "補血道" and p["untested"] == []


def test_plan_g2p_adds_unannotated_position(env, monkeypatch):
    env.says = ["一二三。"]
    monkeypatch.setattr(C0, "g2p_disagree", lambda tag, units, compute=True: ([[dict(pos=1, ch="二", rule="er4", g2p="liang3", src="rule")]], ""))
    x = C0.build_plan("t")["items"][0]["positions"][0]
    assert x["ch"] == "二" and x["value"] is None and x["want"] == "er4" and x["why"] == ["g2p"]


def test_plan_over_limit_reports_untested(env):
    env.says = [f"補血{c}具。" for c in "甲乙丙"]
    p = C0.build_plan("t", limit=2)
    assert len(p["items"]) == 2 and len(p["untested"]) == 1 and p["untested"][0]["ch"] == "血"


def test_plan_same_1plus1_context_counts_once(env):
    env.says = ["先補血道具。", "再補血道路。"]
    assert len(C0.build_plan("t")["items"]) == 1


def test_english_word_gets_sentence(env):
    env.says = ["今天很好。", "我玩 Foo 了。"]
    env.english = {"Foo": [1]}
    p = C0.build_plan("t")
    assert [it["words"] for it in p["items"]] == [["Foo"]] and p["english"] == ["Foo"]


# ------------------------------------------------------------ 真跑(假合成)
def test_run_right_writes_ok_memory_then_second_plan_empty(env):
    env.asr["*"] = blood("寫")
    assert C0.run("t", [1, 2, 3], **fakes()) == 0
    assert env.calls == [(1, [1, 2, 3], 0)] and env.locks == [("t", "tts_c0")]
    e = next(x for x in PM.load()["entries"] if x["char"] == "血")
    assert (e["state"], e["evidence"], e["n_right"], e["left"], e["right"]) == ("ok", "test", 3, "補", "道")
    rep = json.loads(C0.report_path("t").read_text(encoding="utf-8"))
    assert rep["script_sha"] == C0.script_sha("t") and rep["wrong"] == 0 and rep["right"] >= 1
    assert C0.report_path("t").with_suffix(".md").exists()
    assert C0.status("t")[0]
    assert not any(x["ch"] == "血" for it in C0.build_plan("t")["items"] for x in it["positions"])


def test_run_undetermined_is_not_ok_and_not_retested(env):
    assert C0.run("t", [1, 2, 3], **fakes()) == 0     # 辨識回原字
    e = next(x for x in PM.load()["entries"] if x["char"] == "血")
    assert e["state"] == "undetermined" and e["n_undetermined"] == 3
    assert C0.build_plan("t")["items"] == []


def test_run_wrong_exit3_and_blocks(env, capsys):
    env.asr[2] = blood("穴")
    assert C0.run("t", [1, 2, 3], **fakes()) == C0.EXIT_WRONG
    assert "唸錯 行 1 補血道" in capsys.readouterr().out
    e = next(x for x in PM.load()["entries"] if x["char"] == "血")
    assert e["state"] == "bad" and e["fix"]["type"] == "rewrite" and e["fix"]["value"] == SAY
    assert e["wrong_as"] == [dict(heard="穴", kind="alt_reading")]
    assert not C0.status("t")[0]
    calls = len(env.calls)
    assert C0.run("t", [1, 2, 3], **fakes()) == C0.EXIT_WRONG          # 不重測,記憶判定直接算唸錯,不載模型
    assert len(env.calls) == calls


def test_memory_write_does_not_change_engine_text(env):
    before = CT.pron_text(SAY)
    env.asr["*"] = blood("寫")
    assert C0.run("t", [1, 2, 3], **fakes()) == 0
    assert CT.pron_text(SAY) == before


def test_no_risk_no_model_exit0(env):
    env.says = ["今天很好。"]
    assert C0.run("t", [1, 2, 3], **fakes()) == 0
    assert env.calls == [] and env.locks == []
    assert C0.status("t")[0] and json.loads(C0.report_path("t").read_text(encoding="utf-8"))["sentences"] == 0


def test_english_result_only_in_report(env):
    env.says = ["我玩 Foo 了。"]
    env.english = {"Foo": [0]}
    env.term_misread = [dict(term="Foo", hit="福", src="asr", kind="loose")]
    assert C0.run("t", [1, 2], **fakes()) == C0.EXIT_WRONG
    rep = json.loads(C0.report_path("t").read_text(encoding="utf-8"))
    assert rep["english"][0]["word"] == "Foo" and rep["english"][0]["wrong"] == 2
    assert PM.load()["entries"] == []


def test_missing_records_exit1_and_gate_refuses(env, monkeypatch):
    monkeypatch.setattr(C0.V, "synth", lambda items, seeds, work, max_retry: list(seeds))
    assert C0.run("t", [1], **fakes()) == C0.EXIT_INCOMPLETE
    assert not C0.status("t")[0] and PM.load()["entries"] == []


def test_stale_work_dir_not_reused_after_script_change(env):
    env.asr["*"] = blood("寫")
    C0.run("t", [1, 2], **fakes())
    env.says = ["他吃補血丹藥。"]
    assert not C0.status("t")[0]
    assert C0.work_dir("t", [dict(id=0, say=SAY)]) != C0.work_dir("t", [dict(id=0, say=env.says[0])])


def test_status_detects_script_change(env):
    assert C0.status("t") == (False, "未跑(沒有 c0_report.json)")
    C0.run("t", [1], **fakes())
    assert C0.status("t")[0]
    env.says = ["今天很好。"]
    ok, msg = C0.status("t")
    assert not ok and "不符" in msg


def test_dry_run_does_not_synth_or_report(env, capsys):
    assert C0.main(["t", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "試配 1 句" in out and "× 3 seed" in out and "預估" in out and "補血道" in out
    assert env.calls == [] and env.locks == [] and not C0.report_path("t").exists()


# ------------------------------------------------------------ dispatch 閘門
@pytest.fixture
def gate(tmp_path, monkeypatch):
    e = type("G", (), {})()
    e.status, e.boards = (False, "未跑"), []
    monkeypatch.setattr(TD, "c0_status", lambda tag: e.status)
    monkeypatch.setattr(TD, "verify_ok", lambda tag: True)
    monkeypatch.setattr(TD, "board_publish", lambda tag: None)
    monkeypatch.setattr(TD, "board_set", lambda tag, text: e.boards.append(text))
    monkeypatch.setattr(TD, "count_lines", lambda tag: 10)
    monkeypatch.setattr(TD.KR, "REMOTE", tmp_path)
    monkeypatch.delenv("CV_REFREEZE_OK", raising=False)
    return e


def test_gate_refuses_with_command(gate, capsys):
    assert TD.main(["t1", "--prefer", "local"]) == 1
    out = capsys.readouterr().out
    assert "tts_c0.py t1" in out and "--skip-c0" in out and gate.boards == []


def test_gate_passes_when_ok_or_skipped(gate, monkeypatch):
    assert TD.main(["t1", "--prefer", "local", "--skip-c0"]) == 0
    gate.status = (True, "已通過")
    assert TD.main(["t1", "--prefer", "local"]) == 0


def test_gate_refreeze_ok_skips(gate, monkeypatch):
    assert TD.main(["t1", "--prefer", "local", "--refreeze-ok"]) == 0
    monkeypatch.delenv("CV_REFREEZE_OK", raising=False)


def test_gate_dry_run_only_prints(gate, capsys):
    assert TD.main(["t1", "--prefer", "local", "--dry-run"]) == 0
    assert "C0 試配:未跑" in capsys.readouterr().out


def test_status_line_without_prefer(gate, capsys, monkeypatch):
    monkeypatch.setattr(TD.KR, "quota", lambda kind="GPU": 20.0)
    assert TD.main(["t1"]) == TD.EXIT_ASK
    assert "C0 試配:未跑" in capsys.readouterr().out


def test_c0_status_exception_is_not_pass(monkeypatch):
    monkeypatch.setattr(C0, "status", lambda tag: 1 / 0)
    ok, msg = TD.c0_status("t1")
    assert not ok and "查不到" in msg
