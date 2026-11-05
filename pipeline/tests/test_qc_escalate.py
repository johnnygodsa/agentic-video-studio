"""P4 C 段改句迴圈升級 Opus + script_lint 品管易失敗句型警告:
python -X utf8 pipeline/tests/test_qc_escalate.py   或   python -X utf8 -m pytest pipeline/tests/test_qc_escalate.py -q
LLM 與品管(make_version)全換假的,不真呼叫、不動 GPU、不 commit。"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import director as D  # noqa: E402
import director_ab as AB  # noqa: E402
import script_lint as L  # noqa: E402
from test_director_ab import A_VER, BAD, GOOD, L2, TAG, _j, _r, _script, env  # noqa: E402,F401  (env = fixture)


def _reviews(env, monkeypatch, reviews):
    """每次 make_version 依序換 tts_review.json;回傳 make_version 次數 list。"""
    _script(env)
    seq, runs = iter(reviews), []

    def fake_exec(tag, ver, seg, step, cmd):
        runs.append(step)
        _j(env / "build" / TAG / "tts_review.json", next(seq))
        return 0, "", "m"

    monkeypatch.setattr(D, "_exec", fake_exec)
    return runs


def _fix_log(monkeypatch):
    """_fix 換假:記 (mode, 是否帶 call),全數回 fixed(附 old/new)。"""
    log = []

    def fake(tag, items, mode, call=None):
        log.append((mode, call is not None, [i["line"] for i in items]))
        return {"fixed": [{"line": i["line"], "old": f"舊{len(log)}", "new": f"新{len(log)}"} for i in items]}

    monkeypatch.setattr(AB, "_fix", fake)
    return log


def test_loop_reaches_fourth_step_with_escalation_then_passes(env, monkeypatch):
    runs = _reviews(env, monkeypatch, [BAD, BAD, BAD, GOOD])
    log = _fix_log(monkeypatch)
    AB.step_qc(TAG, {}, A_VER)
    assert len(runs) == 4
    assert [c for _, c, _ in log] == [False, False, True]   # 第 3 輪那次才帶 Opus call
    assert all(m == "qc" and ln == [L2] for m, _, ln in log)


def test_still_failing_after_escalation_blocks(env, monkeypatch):
    runs = _reviews(env, monkeypatch, [BAD, BAD, BAD, BAD])
    log = _fix_log(monkeypatch)
    with pytest.raises(AB.Block, match="品管未過到第 3 輪"):
        AB.step_qc(TAG, {}, A_VER)
    assert len(runs) == 4 and len(log) == 3   # 升級只一次,不再有第 5 次


def test_pass_before_third_round_never_escalates(env, monkeypatch):
    runs = _reviews(env, monkeypatch, [BAD, GOOD])
    log = _fix_log(monkeypatch)
    AB.step_qc(TAG, {}, A_VER)
    assert len(runs) == 2 and [c for _, c, _ in log] == [False]


def test_orphan_timing_error_only_does_not_escalate(env, monkeypatch):
    runs = _reviews(env, monkeypatch, [{"failed": [], "timing_errors": ["全片超長"]}])
    log = _fix_log(monkeypatch)
    with pytest.raises(AB.Block, match="時長"):
        AB.step_qc(TAG, {}, A_VER)
    assert len(runs) == 1 and not log


def test_escalated_call_uses_opus_and_prompt_has_history(env, monkeypatch):
    """第 4 步經 _fix → line_fix.fix_lines(換假,吃 call)→ _llm(model=opus);prompt 附前兩輪失敗代碼與改前改後。"""
    runs = _reviews(env, monkeypatch, [BAD, BAD, BAD, GOOD])
    calls, seen = [], []

    def fake_fix_lines(tag, items, mode, call=None, dry_run=False):
        seen.append(mode)
        n = len(seen)
        r = call(tag, "line_fix", "BASE", agent="line-fix", model="sonnet", effort="low")
        return {"fixed": [{"line": items[0]["line"], "old": f"原句{n}", "new": f"改句{n}"}], "unresolved": [], "warn_log": [], "kept": []}

    monkeypatch.setattr(AB.GB, "module", lambda name: SimpleNamespace(fix_lines=fake_fix_lines) if name == "line_fix" else None)
    monkeypatch.setattr(AB, "CALL", lambda tag, fn, prompt, **kw: calls.append((fn, prompt, kw)) or _r({"fixes": []}))
    AB.step_qc(TAG, {}, A_VER)
    assert len(runs) == 4 and len(calls) == 3
    assert all(c[2]["model"] == "sonnet" for c in calls[:2]) and calls[2][2]["model"] == "opus"
    p = calls[2][1]
    assert p.startswith("BASE") and "ASR" in p and "原句1" in p and "改句1" in p and "原句2" in p and "不放寬別名" in p
    assert "BASE" in calls[0][1] and "升級重改" not in calls[0][1]


# ---------- script_lint 三型警告(只警告,不 block) ----------

def _codes(text):
    return {h["code"] for h in L.qc_prone_hits(1, text)}


def test_short_line():
    assert "SHORT_LINE" in _codes("留言告訴我。")
    assert "SHORT_LINE" not in _codes("歡迎在留言區告訴我你的看法。")


def test_comma_many():
    assert "COMMA_MANY" in _codes("先是這樣,再是那樣,然後又這樣,接著那樣,最後才結束。")
    assert "COMMA_MANY" not in _codes("先是這樣,再是那樣,然後又這樣,最後才結束。")


def test_en_tail():
    assert "EN_TAIL" in _codes("他們把這個模式叫做 PvP。")
    assert "EN_TAIL" not in _codes("他們把這個模式叫做 PvP 玩法。")


def test_warnings_are_not_blocks_and_in_sentence_hits(tmp_path, monkeypatch):
    import paths as P
    monkeypatch.setattr(P, "ROOT", tmp_path)
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "script.txt").write_text("@title T\n# 一\na|留言告訴我。\nb|這個遊戲做得很好,玩家都很喜歡。\n", encoding="utf-8")
    r = L.check_sentences("t")
    assert [(h["line"], h["code"], h["block"]) for h in r] == [(3, "SHORT_LINE", False)]
    assert L.T["short_chars"] == 8 and L.T["comma_warn"] == 4


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
