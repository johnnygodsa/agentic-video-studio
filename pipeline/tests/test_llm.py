"""llm.py 測試:python -X utf8 -m pytest pipeline/tests/test_llm.py -q
不真呼叫 claude:_spawn 換假的;假造輸出比照 2026-10-31 實測的 --json-schema 欄位(result、structured_output、usage)。"""
import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director as D  # noqa: E402
import llm  # noqa: E402
import paths  # noqa: E402

TAG = "demo"
USAGE = {"input_tokens": 2, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 50, "output_tokens": 7}


def _env(result="好", structured=None, is_error=False, **kw):
    d = {"type": "result", "is_error": is_error, "result": result, "usage": USAGE, **kw}
    if structured is not None:
        d["structured_output"] = structured
    return json.dumps(d, ensure_ascii=False)


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    root = base / f"test_llm_{uuid.uuid4().hex[:8]}"
    root.mkdir()
    monkeypatch.setattr(paths, "PROJECTS", root / "projects")
    monkeypatch.setattr(paths, "TMP", root / "tmp")
    monkeypatch.setenv("CV_BOARD_DIR", str(root / "channel"))
    (root / "channel").mkdir()
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _spawner(monkeypatch, outs):
    """outs 依序回傳;記下每次的 cmd 與 prompt。"""
    seen = []
    seq = iter(outs)

    def fake(cmd, prompt, timeout, cwd):
        seen.append({"cmd": cmd, "prompt": prompt, "cwd": cwd})
        return next(seq)

    monkeypatch.setattr(llm, "_spawn", fake)
    return seen


def test_build_cmd():
    cmd = llm.build_cmd("claude-haiku-5-5", agent="researcher", effort="high", tools=("Read", "Agent", "Task", "Write"),
                        schema={"type": "object"})
    assert cmd[1:7] == ["-p", "--output-format", "json", "--no-session-persistence", "--model", "claude-haiku-5-5"]
    assert cmd[cmd.index("--tools") + 1] == "Read,Write" and cmd[cmd.index("--allowedTools") + 1] == "Read,Write"
    assert cmd[cmd.index("--agent") + 1] == "researcher" and cmd[cmd.index("--effort") + 1] == "high"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == {"type": "object"}
    assert "--bare" not in cmd and "--max-budget-usd" not in cmd
    bare = llm.build_cmd("m")
    assert "--agent" not in bare and "--effort" not in bare and "--json-schema" not in bare


def test_interpret_schema_and_fallback():
    r = llm._interpret(0, _env(structured={"ok": True}), "", "m", {"x": 1}, 1.0)
    assert r.ok and r.data == {"ok": True}
    r = llm._interpret(0, _env(result='說明\n```json\n{"a": 1}\n```'), "", "m", {"x": 1}, 1.0)
    assert r.ok and r.data == {"a": 1}
    r = llm._interpret(0, _env(result='前面 {"a": 2} 後面'), "", "m", {"x": 1}, 1.0)
    assert r.ok and r.data == {"a": 2}
    r = llm._interpret(0, _env(result="沒有 JSON"), "", "m", {"x": 1}, 1.0)
    assert not r.ok and "schema" in r.error
    r = llm._interpret(0, _env(result="純文字"), "", "m", None, 1.0)
    assert r.ok and r.data is None and r.text == "純文字"
    events = json.dumps([{"type": "system"}, {"type": "result", "is_error": False, "result": "x", "usage": USAGE}])
    assert llm._interpret(0, events, "", "m", None, 1.0).text == "x"


def test_schema_text_path_like_agent_mode():
    """--agent 下沒有 structured_output,只有回覆文字;欄位自己驗。"""
    sch = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
        "type": "object", "required": ["line"], "properties": {"line": {"type": "integer"}, "ok": {"type": "boolean"}}}}}}
    assert llm._interpret(0, _env(result='{"items": [{"line": 1}]}'), "", "m", sch, 1.0).ok
    r = llm._interpret(0, _env(result='{"other": 1}'), "", "m", sch, 1.0)
    assert not r.ok and "items" in r.error
    r = llm._interpret(0, _env(result='{"items": [{"nope": 1}]}'), "", "m", sch, 1.0)
    assert not r.ok and "items[0].line" in r.error
    r = llm._interpret(0, _env(result='{"items": [{"line": "12"}]}'), "", "m", sch, 1.0)
    assert not r.ok and "items[0].line" in r.error
    assert llm.schema_miss(sch, {"items": [{"line": True}]}) == "items[0].line"


def test_interpret_failures():
    r = llm._interpret(0, "不是 json", "", "m", None, 1.0)
    assert not r.ok and "不是 JSON" in r.error and not r.limited
    r = llm._interpret(0, _env(result="壞了", is_error=True), "", "m", None, 1.0)
    assert not r.ok and "is_error" in r.error
    r = llm._interpret(1, "", "boom", "m", None, 1.0)
    assert not r.ok and "boom" in r.error and r.rc == 1
    r = llm._interpret(None, "", "逾時 5 秒", "m", None, 1.0)
    assert not r.ok and "逾時" in r.error and r.rc == -1 and not r.limited


@pytest.mark.parametrize("rc,out,err", [
    (0, _env(result="Claude AI usage limit reached", is_error=True), ""),
    (1, "", "You've hit your weekly limit"),
    (1, "", "429 rate_limit_error"),
    (0, _env(result="usage limit reached"), ""),  # 沒標 is_error 的短回覆
])
def test_limited(rc, out, err):
    r = llm._interpret(rc, out, err, "m", None, 1.0)
    assert r.limited and not r.ok and r.error == "用量上限"


def test_long_text_mentioning_rate_limit_is_not_limited():
    r = llm._interpret(0, _env(result="這支片在講 rate limit。" + "字" * 500), "", "m", None, 1.0)
    assert r.ok and not r.limited


def test_call_logs_and_saves_raw(env, monkeypatch):
    seen = _spawner(monkeypatch, [(0, _env(structured={"a": 1}), "")])
    r = llm.call(TAG, "fn1", "提示", agent="ab-planner", model="sonnet", schema={"type": "object"}, seg="A")
    assert r.ok and r.model == llm.MODELS["sonnet"]
    assert seen[0]["prompt"].startswith("提示") and llm.SCHEMA_TAIL in seen[0]["prompt"] and '"object"' in seen[0]["prompt"]
    c = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))["llm_calls"][-1]
    assert (c["input_tokens"], c["output_tokens"], c["cache_read"]) == (102, 7, 50)
    assert c["ok"] is True and c["seg"] == "A" and c["agent"] == "ab-planner" and "secs" in c
    assert len(list((env / "tmp" / "llm" / TAG).glob("*_fn1.json"))) == 1


def test_call_validate_failure_is_logged(env, monkeypatch):
    _spawner(monkeypatch, [(0, _env(), "")])
    r = llm.call(TAG, "fn2", "p", validate=lambda res: "檔案沒寫")
    assert not r.ok and r.error == "檔案沒寫"
    assert json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))["llm_calls"][-1]["ok"] is False


def test_escalating_sequence_and_reason(env, monkeypatch):
    seen = _spawner(monkeypatch, [(1, "", "e1"), (1, "", "e2"), (0, _env(), "")])
    r = llm.call_escalating(TAG, "f", "原提示", model="sonnet")
    assert r.ok and r.model == llm.MODELS["opus"]
    models = [s["cmd"][s["cmd"].index("--model") + 1] for s in seen]
    assert models == [llm.MODELS["sonnet"], llm.MODELS["sonnet"], llm.MODELS["opus"]]
    assert seen[0]["prompt"] == "原提示" and "e1" in seen[1]["prompt"] and "e2" in seen[2]["prompt"] and "e1" not in seen[2]["prompt"]


def test_escalating_opus_gives_up(env, monkeypatch):
    seen = _spawner(monkeypatch, [(1, "", "e1"), (1, "", "e2")])
    r = llm.call_escalating(TAG, "f", "p", model="opus")
    assert not r.ok and len(seen) == 2


def test_escalating_limited_stops_at_once(env, monkeypatch):
    seen = _spawner(monkeypatch, [(1, "", "usage limit reached")])
    r = llm.call_escalating(TAG, "f", "p", model="haiku")
    assert r.limited and len(seen) == 1


def test_call_timeout_via_real_spawn(env, monkeypatch):
    def boom(*a, **k):
        import subprocess
        raise subprocess.TimeoutExpired("claude", 1)

    monkeypatch.setattr(llm.subprocess, "run", boom)
    assert llm._spawn(["claude"], "p", 1, ".")[0] is None
