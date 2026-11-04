"""B10 素材員程式主導(PLAN_token重設計 §2 B10):python -X utf8 -m pytest pipeline/tests/test_assets_v3.py -q
LLM 用 AB.CALL 注入假函式;--check 用 AB._run_check 換假的,不真截圖。"""
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

TAG = "demo_a"


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    root = base / f"test_assets_v3_{uuid.uuid4().hex[:8]}"
    (root / "projects" / TAG).mkdir(parents=True)
    for attr, sub in (("PROJECTS", "projects"), ("BUILD", "build"), ("OUTPUT", "output"), ("TMP", "tmp"), ("IMAGES", "images")):
        monkeypatch.setattr(paths, attr, root / sub)
    monkeypatch.setattr(paths, "REPO", root)
    monkeypatch.setattr(paths, "ROOT", root)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _brief(env, flow):
    d = {"tag": TAG, "channel": "ChannelA"}
    if flow:
        d["flow"] = flow
    (env / "projects" / TAG / "brief.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def _setup(monkeypatch, log):
    items = [{"claim": "C1", "kind": "screen", "path": "images/demo_a_good.png", "hl": "x", "ok": True},
             {"claim": "C2", "kind": "screen", "path": "images/demo_a_bad.png", "hl": "y", "ok": True},
             {"claim": "C3", "kind": "screen", "path": "images/demo_a_off.png", "hl": "z", "ok": False, "why": "代理自報"}]

    def call(tag, fn, prompt, **kw):
        log.append((fn, prompt, kw))
        its = [dict(i) for i in items] if fn == "assets_screen" else [{"claim": "clips", "kind": "clip", "path": "p", "hl": "", "ok": True}]
        return SimpleNamespace(ok=True, data={"items": its}, limited=False, error="", text="")

    checked = []

    def run_check(script, names):
        checked.append((Path(script).name, tuple(names)))
        return (1, "  找不到 hl: y") if names == ["bad"] else (0, "OK")

    monkeypatch.setattr(AB, "CALL", call)
    monkeypatch.setattr(AB, "_news_scripts", lambda tag: {Path("assets_da_news.py"): "demo_a_"})
    monkeypatch.setattr(AB, "_run_check", run_check)
    return checked


def _manifest(env):
    return json.loads((env / "projects" / TAG / "assets_manifest.json").read_text(encoding="utf-8"))


def test_v3_recheck_flips_failed_item(env, monkeypatch):
    _brief(env, "v3")
    log = []
    checked = _setup(monkeypatch, log)
    AB.step_assets(TAG, {}, SimpleNamespace())
    m = {i["path"]: i for i in _manifest(env)}
    assert m["images/demo_a_good.png"]["ok"] is True
    assert m["images/demo_a_bad.png"]["ok"] is False and "程式複驗" in m["images/demo_a_bad.png"]["why"]
    assert m["images/demo_a_off.png"]["why"] == "代理自報"
    assert sorted(n for _, n in checked) == [("bad",), ("good",)]  # ok=false 與 clip 項不複驗
    assert next(i for i in _manifest(env) if i["kind"] == "clip")["ok"] is True


def test_v3_call_kwargs(env, monkeypatch):
    _brief(env, "v3")
    log = []
    _setup(monkeypatch, log)
    AB.step_assets(TAG, {}, SimpleNamespace())
    for fn, prompt, kw in log:
        assert kw["effort"] == "low" and "程式主導" in prompt and "不要自己開圖" in prompt
        assert "Bash" in kw["tools"] and kw["allowed"] is AB.ASSET_ALLOWED
    allowed = set(AB.ASSET_ALLOWED)
    assert "Bash(python -X utf8 pipeline/clips_lib.py*)" in allowed and "Bash(python -X utf8 pipeline" + chr(92) + "assets_*_news.py*)" in allowed
    assert "Bash(yt-dlp *)" in allowed   # 5cf33e6:素材員准 yt-dlp


def test_v3_unknown_script_flips(env, monkeypatch):
    _brief(env, "v3")
    _setup(monkeypatch, [])
    monkeypatch.setattr(AB, "_news_scripts", lambda tag: {})
    AB.step_assets(TAG, {}, SimpleNamespace())
    assert [i["ok"] for i in _manifest(env) if i["kind"] == "screen"] == [False, False, False]


@pytest.mark.parametrize("flow", [None, "v2"])
def test_v2_no_check(env, monkeypatch, flow):
    _brief(env, flow)
    log = []
    checked = _setup(monkeypatch, log)
    AB.step_assets(TAG, {}, SimpleNamespace())
    assert checked == []
    assert [i["ok"] for i in _manifest(env) if i["kind"] == "screen"] == [True, True, False]
    for fn, prompt, kw in log:
        assert "effort" not in kw and "allowed" not in kw and "程式主導" not in prompt
