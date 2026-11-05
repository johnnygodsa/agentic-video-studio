"""llm.py Codex 後端測試:python -X utf8 -m pytest pipeline/tests/test_llm_codex.py -q
全 mock:subprocess.run、shutil.which 換假的,不真呼叫 claude/codex;本機沒裝 codex 也能跑。"""
import json
import shutil
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director as D  # noqa: E402
import llm  # noqa: E402
import locale_cfg  # noqa: E402
import paths  # noqa: E402

TAG = "demo"


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    root = base / f"test_llm_codex_{uuid.uuid4().hex[:8]}"
    root.mkdir()
    monkeypatch.setattr(paths, "PROJECTS", root / "projects")
    monkeypatch.setattr(paths, "TMP", root / "tmp")
    monkeypatch.setattr(paths, "REPO", root)
    monkeypatch.setenv("CV_BOARD_DIR", str(root / "channel"))
    monkeypatch.delenv("STUDIO_LLM", raising=False)
    monkeypatch.setattr(locale_cfg, "CFG", root / "studio.json")
    monkeypatch.setattr(llm.shutil, "which", lambda name: None)
    (root / "channel").mkdir()
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _cfg(root, llm_cfg):
    (root / "studio.json").write_text(json.dumps({"llm": llm_cfg}), encoding="utf-8")


def _runner(monkeypatch, outs):
    """outs 依序為 (rc, last_message|None, stdout, stderr);last 不是 None 就寫進 -o 檔。記下 cmd、prompt、schema 檔內容。"""
    seen, seq = [], iter(outs)

    def fake(cmd, input=None, capture_output=True, timeout=None, cwd=None):
        rc, last, out, err = next(seq)
        rec = {"cmd": cmd, "prompt": input.decode("utf-8"), "cwd": cwd}
        if "--output-schema" in cmd:
            rec["schema"] = json.loads(Path(cmd[cmd.index("--output-schema") + 1]).read_text(encoding="utf-8"))
        if last is not None:
            Path(cmd[cmd.index("-o") + 1]).write_text(last, encoding="utf-8")
        seen.append(rec)
        return SimpleNamespace(returncode=rc, stdout=out.encode("utf-8"), stderr=err.encode("utf-8"))

    monkeypatch.setattr(llm.subprocess, "run", fake)
    return seen


# ---- 後端選擇 ----

def test_backend_priority(env, monkeypatch):
    assert llm.backend() == "claude"
    _cfg(env, {"backend": "codex"})
    assert llm.backend() == "codex"
    monkeypatch.setenv("STUDIO_LLM", "claude")
    assert llm.backend() == "claude"
    _cfg(env, {"backend": "claude"})
    monkeypatch.setenv("STUDIO_LLM", "Codex")
    assert llm.backend() == "codex"
    monkeypatch.setenv("STUDIO_LLM", "bogus")
    assert llm.backend() == "claude"


def test_locale_section_does_not_touch_locale_defaults(env):
    (env / "studio.json").write_text(json.dumps({"llm": {"backend": "codex"}, "locale": {"x": 1}}), encoding="utf-8")
    locale_cfg._load.cache_clear()
    try:
        assert locale_cfg.section("llm") == {"backend": "codex"} and locale_cfg.section("nope") == {}
        assert locale_cfg.get("x") is None and locale_cfg.enabled("price_local_currency")
    finally:
        locale_cfg._load.cache_clear()


# ---- 指令組成 ----

def test_claude_build_cmd_unchanged(monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda name: None)
    cmd = llm.build_cmd("claude-sonnet-5-5", agent="researcher", effort="high", tools=("Read", "Grep", "Agent"),
                        schema={"type": "object"}, allowed=["Read", "Bash(python -X utf8 pipeline/x.py:*)", "Task"])
    assert cmd == ["claude", "-p", "--output-format", "json", "--no-session-persistence", "--model", "claude-sonnet-5-5",
                   "--effort", "high", "--agent", "researcher", "--tools", "Read,Grep", "--allowedTools",
                   "Read", "Bash(python -X utf8 pipeline/x.py:*)", "--json-schema", '{"type": "object"}']
    assert llm.build_cmd("m") == ["claude", "-p", "--output-format", "json", "--no-session-persistence", "--model", "m",
                                  "--tools", "Read,Grep,Glob", "--allowedTools", "Read,Grep,Glob"]


def test_codex_sandbox():
    assert llm.codex_sandbox(("Read", "Grep", "Glob")) == "read-only"
    assert llm.codex_sandbox(("Read", "Edit")) == "workspace-write"
    assert llm.codex_sandbox(("Read",), ["Bash(python -X utf8 pipeline/x.py:*)"]) == "workspace-write"
    assert llm.codex_sandbox(("Read", "Write")) == "workspace-write"


def test_build_codex_cmd(monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda name: "C:/bin/codex.cmd" if name == "codex" else None)
    cmd = llm.build_codex_cmd(None, out_file="o.txt")
    assert cmd == ["C:/bin/codex.cmd", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-o", "o.txt", "-"]
    cmd = llm.build_codex_cmd("gpt-x", effort="max", tools=("Write",), schema_file="s.json", out_file="o.txt")
    assert cmd[cmd.index("--sandbox") + 1] == "workspace-write" and cmd[cmd.index("-m") + 1] == "gpt-x"
    assert cmd[cmd.index("-c") + 1] == "model_reasoning_effort=high"
    assert cmd[cmd.index("--output-schema") + 1] == "s.json" and cmd[-3:] == ["-o", "o.txt", "-"]
    for e, want in (("low", "low"), ("medium", "medium"), ("xhigh", "high")):
        assert llm.build_codex_cmd(effort=e, out_file="o")[6] == f"model_reasoning_effort={want}"


def test_codex_model_mapping(env):
    assert llm.codex_model("sonnet") is None and llm.codex_model("claude-opus-5-5") is None
    _cfg(env, {"codex_models": {"opus": "big", "sonnet": "mid"}})
    assert llm.codex_model("opus") == "big" and llm.codex_model("claude-sonnet-5-5") == "mid"
    assert llm.codex_model("haiku") is None


def test_agent_preamble_strips_frontmatter(env):
    d = env / ".claude" / "agents"
    d.mkdir(parents=True)
    (d / "researcher.md").write_text("---\nname: researcher\ntools: Read\n---\n\n你是研究員。\n", encoding="utf-8")
    assert llm.agent_preamble("researcher") == "你是研究員。"
    assert llm.agent_preamble("missing") is None


# ---- call ----

def test_call_codex_agent_schema_and_json(env, monkeypatch):
    _cfg(env, {"backend": "codex", "codex_output_schema": True})
    d = env / ".claude" / "agents"
    d.mkdir(parents=True)
    (d / "fact-check.md").write_text("---\nname: fact-check\nmodel: opus\n---\n核對事實。", encoding="utf-8")
    seen = _runner(monkeypatch, [(0, '```json\n{"a": 1}\n```', "stdout 不採用", "log")])
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}
    r = llm.call(TAG, "fc", "任務內容", agent="fact-check", model="sonnet", effort="medium", schema=schema, seg="B")
    assert r.ok and r.data == {"a": 1} and r.model == "codex-default" and r.usage == {}
    cmd = seen[0]["cmd"]
    assert cmd[:5] == ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only"] and "-m" not in cmd
    assert "--agent" not in cmd and cmd[cmd.index("-c") + 1] == "model_reasoning_effort=medium"
    assert seen[0]["schema"] == schema
    p = seen[0]["prompt"]
    assert p.startswith("核對事實。" + llm.AGENT_SEP + "任務內容") and "name: fact-check" not in p
    assert llm.SCHEMA_TAIL in p
    assert not list((paths.TMP / "llm" / TAG).glob("*_codex_*")), "暫存檔要刪"
    assert len(list((paths.TMP / "llm" / TAG).glob("*_fc.json"))) == 1
    c = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))["llm_calls"][-1]
    assert c["model"] == "codex-default" and c["ok"] is True and c["agent"] == "fact-check" and c["input_tokens"] == 0


def test_call_codex_missing_agent(env, monkeypatch):
    _cfg(env, {"backend": "codex"})
    seen = _runner(monkeypatch, [])
    r = llm.call(TAG, "x", "p", agent="nobody")
    assert not r.ok and "nobody" in r.error and not seen


def test_call_codex_falls_back_to_stdout_and_maps_model(env, monkeypatch):
    _cfg(env, {"backend": "codex", "codex_models": {"sonnet": "mid"}})
    seen = _runner(monkeypatch, [(0, None, "純文字回覆\n", "")])
    r = llm.call(TAG, "x", "p", model="sonnet", tools=("Read", "Edit"))
    assert r.ok and r.text == "純文字回覆" and r.model == "mid"
    assert seen[0]["cmd"][seen[0]["cmd"].index("-m") + 1] == "mid" and "workspace-write" in seen[0]["cmd"]


def test_call_codex_schema_miss_and_empty(env, monkeypatch):
    _cfg(env, {"backend": "codex"})
    _runner(monkeypatch, [(0, '{"b": 1}', "", ""), (0, "", "", "")])
    schema = {"type": "object", "required": ["a"]}
    assert "不符 schema" in llm.call(TAG, "x", "p", schema=schema).error
    assert llm.call(TAG, "x", "p").error == "回覆為空"


@pytest.mark.parametrize("rc,last,err,limited", [
    (1, None, "ERROR: You've hit your usage limit. Try again later.", True),
    (0, "Rate limit reached", "", True),
    (1, None, "使用者 prompt 提到 rate limit" + "x" * 3000 + "\nERROR: boom", False),
    (0, "內文提到 rate limit 但是很長" + "字" * 500, "", False),
])
def test_codex_limit_detection(env, monkeypatch, rc, last, err, limited):
    _cfg(env, {"backend": "codex"})
    _runner(monkeypatch, [(rc, last, "", err)])
    r = llm.call(TAG, "x", "p")
    assert r.limited is limited and (r.error == "用量上限") is limited


def test_escalating_codex_maps_opus_and_stops(env, monkeypatch):
    _cfg(env, {"backend": "codex", "codex_models": {"opus": "big"}})
    seen = _runner(monkeypatch, [(1, None, "", "e1"), (1, None, "", "e2"), (1, None, "", "e3")])
    r = llm.call_escalating(TAG, "x", "p", model="sonnet")
    assert not r.ok and len(seen) == 3
    assert ["-m" in s["cmd"] for s in seen] == [False, False, True]
    assert seen[2]["cmd"][seen[2]["cmd"].index("-m") + 1] == "big" and r.model == "big"


def test_escalating_codex_without_models_is_finite(env, monkeypatch):
    _cfg(env, {"backend": "codex"})
    seen = _runner(monkeypatch, [(1, None, "", "e")] * 3)
    r = llm.call_escalating(TAG, "x", "p", model="opus")
    assert not r.ok and len(seen) == 2


def test_default_backend_still_claude(env, monkeypatch):
    seen = _runner(monkeypatch, [(0, None, json.dumps({"type": "result", "is_error": False, "result": "好", "usage": {}}), "")])
    r = llm.call(TAG, "x", "p")
    assert r.ok and r.model == "claude-sonnet-5-5" and seen[0]["cmd"][:2] == ["claude", "-p"]


def test_call_codex_no_output_schema_by_default(env, monkeypatch):
    """預設不傳 --output-schema(嚴格模式與現有 schema 不相容);schema 仍寫進 prompt。"""
    _cfg(env, {"backend": "codex"})
    seen = _runner(monkeypatch, [(0, '{"a": 1}', "", "")])
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}
    r = llm.call(TAG, "fc2", "任務", model="sonnet", schema=schema, seg="B")
    assert r.ok and r.data == {"a": 1}
    assert "--output-schema" not in seen[0]["cmd"] and llm.SCHEMA_TAIL in seen[0]["prompt"]
