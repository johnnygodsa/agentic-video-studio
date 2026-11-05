"""P1 寫稿長度前置(director_ab.step_write → _ensure_length):python -X utf8 pipeline/tests/test_write_length.py
假專案放 repo tmp/ 下暫存目錄;LLM 用 AB.CALL 注入假函式,不真呼叫、不 commit。失敗結束碼非 0。"""
import json
import shutil
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director_ab as AB  # noqa: E402
import paths  # noqa: E402
from gates import gate_b, specs  # noqa: E402

TAG = "demo_len"
FLOOR = 6  # ChannelA 評論片 floor 6 分


def _w(p, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _script(chars):
    return f'@title 測試\n# 一、開場\nme_old|{"字" * chars} ;; {{"f": ["F1"]}}\n'


def _r():
    return SimpleNamespace(ok=True, data={}, limited=False, error="", text="")


def _brief(env, **extra):
    _w(env / "projects" / TAG / "brief.json",
       json.dumps({"tag": TAG, "topic": "t", "angle": "a", "channel": "ChannelA", "format": "評論片", "flow": "v3", **extra}, ensure_ascii=False))


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    root = base / f"test_wl_{uuid.uuid4().hex[:8]}"
    root.mkdir()
    for attr, sub in (("PROJECTS", "projects"), ("BUILD", "build"), ("OUTPUT", "output"), ("TMP", "tmp"), ("IMAGES", "images")):
        monkeypatch.setattr(paths, attr, root / sub)
    monkeypatch.setattr(paths, "REPO", root)
    monkeypatch.setattr(paths, "ROOT", root)
    monkeypatch.setenv("CV_BOARD_DIR", str(root / "channel"))
    (root / "channel").mkdir()
    _brief(root)
    _w(root / "projects" / TAG / "facts.md", "| F1 | 空檔 3 秒 | 官網 | 已核 |\n| F2 | 另一件事 | 官網 | 已核 |\n")
    monkeypatch.setattr(gate_b, "module", lambda n: SimpleNamespace(explain=lambda: "可唸規則"))
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _fake(env, log, first, second):
    """write 寫 first 字、write_expand 寫 second 字(None = 不該被呼叫)。"""
    def call(tag, fn, prompt, **kw):
        log.append((fn, prompt))
        n = {"write": first, "write_expand": second}[fn]
        assert n is not None, f"不該呼叫 {fn}"
        _w(env / tag / "script.txt", _script(n))
        _w(env / "projects" / tag / "outline.md")
        return _r()
    return call


def _run(monkeypatch, env, first, second):
    log = []
    monkeypatch.setattr(AB, "CALL", _fake(env, log, first, second))
    err = None
    try:
        AB.step_write(TAG, {}, SimpleNamespace(ver=None))
    except AB.Block as e:
        err = e
    return [f for f, _ in log], log, err


def test_short_triggers_one_expand(env, monkeypatch):
    fns, log, err = _run(monkeypatch, env, 300, int(FLOOR * specs.SPEECH_CPM) + 50)
    assert fns == ["write", "write_expand"] and err is None
    prompt = log[1][1]
    assert "F2" in prompt and "F1" not in prompt.split("優先用還沒用到的 facts 編號:")[1].split("(來源")[0]  # 只列沒用過的
    assert specs.est_minutes(TAG) >= FLOOR


def test_long_enough_no_expand(env, monkeypatch):
    fns, _, err = _run(monkeypatch, env, int(FLOOR * specs.SPEECH_CPM) + 50, None)
    assert fns == ["write"] and err is None


def test_allow_short_no_expand(env, monkeypatch):
    _brief(env, allow_short=True)
    fns, _, err = _run(monkeypatch, env, 300, None)
    assert fns == ["write"] and err is None


def test_still_short_blocks_after_single_expand(env, monkeypatch):
    fns, _, err = _run(monkeypatch, env, 300, 600)
    assert fns == ["write", "write_expand"]
    assert err is not None and "要問使用者" in err.reason and "補素材/併題/照發" in err.reason


def test_v2_flow_also_checked(env, monkeypatch):
    _brief(env, flow=None)
    fns, _, err = _run(monkeypatch, env, 300, int(FLOOR * specs.SPEECH_CPM) + 50)
    assert fns == ["write", "write_expand"] and err is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
