"""director B 段 flow v3(PLAN_token重設計 §2(b) B1/B3/B4/B5/B6/B8):python -X utf8 -m pytest pipeline/tests/test_director_ab_v3.py -q
假專案放 repo tmp/ 下暫存目錄;LLM 用 AB.CALL 注入假函式,檢查工具換假的,不真呼叫、不 commit。"""
import json
import shutil
import sys
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director_ab as AB  # noqa: E402
import llm  # noqa: E402
import paths  # noqa: E402
from gates import gate_b, specs  # noqa: E402

TAG = "demo3"
SCRIPT = """@title 測試
# 一、開場
me_old|第一句有 3 秒的空檔。 ;; {"f": ["F1"]}
img:debt|第二句講別的事情。
anim|第三句再講一件事。 ;; {"anim": "x"}

# 二、中段
img:a|第四句是中段開頭。
img:b|第五句是中段結尾。
"""


def _w(p, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _r(data=None, ok=True):
    return SimpleNamespace(ok=ok, data=data, limited=False, error="", text="")


def _rev(items):
    return {"counts": {}, "items": [{"line": n, "type": t, "severity": "確定", "text": "", "reason": "", "fix": ""} for n, t in items]}


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    root = base / f"test_ab_v3_{uuid.uuid4().hex[:8]}"
    root.mkdir()
    for attr, sub in (("PROJECTS", "projects"), ("BUILD", "build"), ("OUTPUT", "output"), ("TMP", "tmp"), ("IMAGES", "images")):
        monkeypatch.setattr(paths, attr, root / sub)
    monkeypatch.setattr(paths, "REPO", root)
    monkeypatch.setattr(paths, "ROOT", root)
    monkeypatch.setenv("CV_BOARD_DIR", str(root / "channel"))
    monkeypatch.delenv("CV_REWRITE", raising=False)
    (root / "channel").mkdir()
    pd = root / "projects" / TAG
    _w(pd / "brief.json", json.dumps({"tag": TAG, "topic": "t", "angle": "a", "channel": "ChannelA", "format": "評論片", "flow": "v3"}, ensure_ascii=False))
    _w(pd / "facts.md", "| F1 | 空檔 3 秒 | 官網 | 已核 |\n")
    _w(root / TAG / "script.txt", SCRIPT)
    monkeypatch.setattr(AB, "commit_seg", lambda tag, seg: None)
    monkeypatch.setattr(AB, "_recheck", lambda tag: None)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _pd(env):
    return env / "projects" / TAG


def _fake(env, plan, log, barrier=None):
    """plan[fn 前綴] = 回傳資料或 callable(prompt) → 資料;*_r1 報告兩路要同時在跑(barrier)。"""
    def call(tag, fn, prompt, **kw):
        log.append((fn, prompt, kw))
        if fn in ("editor_r1", "player_r1") and barrier:
            barrier.wait()
        if fn == "player_r1":
            _w(_pd(env) / "player_review_r1.md")
        key = next((k for k in plan if fn.startswith(k)), None)
        if key is None:
            pytest.fail(f"不該呼叫 {fn}")
        d = plan[key]
        return _r(d(prompt) if callable(d) else d)
    return call


def _fns(log):
    return [f for f, *_ in log]


def _lines():
    return [r[1] for r in gate_b.narration(TAG)]


# ---------- flow 與步驟表 ----------

def test_flow_and_steps_v2_unchanged(env):
    a = SimpleNamespace(ver=None)
    assert AB.flow(TAG) == "v3"
    assert [s["step"] for s in AB.steps(TAG, "B", {}, a)] == ["write", "speak", "lint", "review"]
    _w(_pd(env) / "brief.json", json.dumps({"tag": TAG, "channel": "ChannelA"}))
    assert specs.flow(TAG) == "v2"
    assert [s["step"] for s in AB.steps(TAG, "B", {}, a)] == ["write", "speak", "lint", "editor", "player"]


def test_build_cmd_allowed_patterns():
    cmd = llm.build_cmd("m", tools=("Read", "Bash"), allowed=("Read", "Bash(python -X utf8 pipeline/script_lint.py:*)"))
    i = cmd.index("--allowedTools")
    assert cmd[cmd.index("--tools") + 1] == "Read,Bash"
    assert cmd[i + 1:i + 3] == ["Read", "Bash(python -X utf8 pipeline/script_lint.py:*)"]
    assert llm.build_cmd("m", tools=("Read",))[-1] == "Read"  # 沒給 allowed 行為不變


# ---------- B5 ----------

def test_write_skip_when_script_exists(env, monkeypatch):
    pd = _pd(env)
    plan_f = _w(pd / "plan.json", "{}")  # 比 script 新也不重寫
    assert "CV_REWRITE" in AB._write_skip(TAG, plan_f, pd / "facts.md", pd / "assets_manifest.json")
    monkeypatch.setenv("CV_REWRITE", "1")
    assert AB._write_skip(TAG, plan_f, pd / "facts.md", pd / "assets_manifest.json") is None


# ---------- B1 ----------

def test_write_v3_bash_whitelist_and_writer_log(env, monkeypatch):
    monkeypatch.setattr(gate_b, "module", lambda n: SimpleNamespace(explain=lambda: "可唸規則"))
    log = []

    def write(prompt):
        _w(_pd(env) / "outline.md")
        _w(_pd(env) / AB.WRITER_LOG, json.dumps([{"check": "lint", "line": 4, "code": "PAD", "action": "kept", "reason": "語氣需要"},
                                                 {"check": "speak", "line": 4, "code": "X", "reason": ""}]))
        return {}
    monkeypatch.setattr(AB, "CALL", _fake(env, {"write": write}, log))
    AB.step_write(TAG, {}, SimpleNamespace(ver=None))
    _, prompt, kw = log[0]
    assert "Bash" in kw["tools"] and "寫完自檢" in prompt and AB.WRITER_LOG in prompt
    assert "Bash(python -X utf8 pipeline/script_lint.py:*)" in kw["allowed"] and "Bash(python -X utf8 pipeline\\speakable.py:*)" in kw["allowed"]
    wl = gate_b.warn_log(TAG)
    assert list(wl) == [f"lint:{gate_b.sha8('第二句講別的事情。')}:PAD"] and wl[next(iter(wl))]["action"] == "kept"


# ---------- B6 ----------

def test_revise_why():
    assert AB.revise_why("有 3 秒。", "有 5 秒。").startswith("數字集合不同")
    assert AB.revise_why("有 3 秒。", "有 5 秒。", hint="數字錯了") is None
    assert AB.revise_why("有 3 秒。", "img:a|有 3 秒。").startswith("new_line 不可含")
    assert AB.revise_why("看 Steam 評價。", "看評價。", {"hl": "Steam"}).startswith("行尾 hl")


# ---------- B3 + B4 ----------

def _clean_plan(**over):
    plan = {"editor_r1": _rev([(1, "連貫"), (3, "報幕")]), "player_r1": _rev([(2, "誇大"), (4, "外行")]),
            "revise": {"items": [{"line": 1, "new_line": "第一句先講 3 秒的空檔。", "note": ""},
                                 {"line": 2, "new_line": "第二句改講別件事情。", "note": ""}], "kept": []},
            "player_spot": _rev([]), "fact_r2": _rev([])}
    plan.update(over)
    return plan


def test_parallel_review_then_single_revise(env, monkeypatch):
    log = []
    monkeypatch.setattr(AB, "CALL", _fake(env, _clean_plan(), log, threading.Barrier(2, timeout=10)))
    AB.step_review(TAG)
    fns = _fns(log)
    assert sorted(fns[:2]) == ["editor_r1", "player_r1"] and fns.count("revise") == 1
    assert fns[2:] == ["revise", "player_spot1", "fact_r2"]
    revise_prompt = log[2][1]
    assert "報幕" not in revise_prompt and "外行" not in revise_prompt  # 編輯審四類以外丟掉;玩家審非必處理不改
    ed = json.loads((_pd(env) / "editor_review_r1.json").read_text(encoding="utf-8"))
    assert ed["revised"] == [1] and ed["dropped"] == 1 and (_pd(env) / "editor_review_r1.md").exists()
    st = AB.review_state(TAG)
    assert st["done"] and not st["ask"] and not st["open_hard"] and not (_pd(env) / "ask_user.json").exists()
    assert [i["ok"] for i in gate_b.review_items_v3(TAG)] == [True, True]


def test_spot_only_changed_lines(env, monkeypatch):
    log = []
    plan = _clean_plan(player_r1=_rev([]), revise={"items": [{"line": 1, "new_line": "第一句先講 3 秒的空檔。", "note": ""}], "kept": []})
    monkeypatch.setattr(AB, "CALL", _fake(env, plan, log))
    AB.step_review(TAG)
    spot = next(p for f, p, _ in log if f.startswith("player_spot"))
    assert ">> 1." in spot and "   2." in spot and ">> 2." not in spot and "4." not in spot


def test_spot_batches_over_20_lines(env, monkeypatch):
    log = []
    monkeypatch.setattr(AB, "CALL", _fake(env, {"player_spot": _rev([(1, "吵")])}, log))
    monkeypatch.setattr(AB.GB, "narration", lambda tag: [(i, f"句{i}", "", {}) for i in range(1, 46)])
    items, out = AB._spot_items(TAG, list(range(1, 46)))
    assert _fns(log) == ["player_spot1"] * 3 and len(items) == 3 and out.name == "player_spot_1.json"


def test_left_wrong_goes_ask_user_other_types_do_not(env, monkeypatch):
    log = []
    plan = _clean_plan(player_r1=_rev([(4, "推論")]), revise={"items": [], "kept": []},
                       fact_r2=_rev([(3, "錯"), (5, "查無")]))
    monkeypatch.setattr(AB, "CALL", _fake(env, plan, log))
    with pytest.raises(AB.Block, match="要問使用者:1 條"):
        AB.step_review(TAG)
    ask = json.loads((_pd(env) / "ask_user.json").read_text(encoding="utf-8"))
    assert [(i["line"], i["type"]) for i in ask] == [(3, "錯")]  # 錯 revise 改不動 → 問;推論、查無只記


def test_only_hard_and_judge_are_asked(env, monkeypatch):
    log = []
    plan = _clean_plan(player_r1=_rev([(4, "推論"), (5, "可疑")]), editor_r1=_rev([]), revise={"items": [], "kept": []},
                       fact_r2=_rev([(3, "錯"), (2, "查無")]))
    monkeypatch.setattr(AB, "CALL", _fake(env, plan, log))
    with pytest.raises(AB.Block, match="要問使用者"):
        AB.step_review(TAG)
    ask = json.loads((_pd(env) / "ask_user.json").read_text(encoding="utf-8"))
    assert sorted((i["line"], i["type"]) for i in ask) == [(3, "錯"), (5, "可疑")]
    st = AB.review_state(TAG)
    assert [i["line"] for i in st["open_hard"]] == [3] and {(i["line"], i["type"]) for i in st["soft"]} >= {(4, "推論"), (2, "查無")}
    assert not gate_b.review_items_v3(TAG)[1]["ok"]
    # 主對話處理完清空 ask_user → 重跑結案,不花 LLM
    (_pd(env) / "ask_user.json").write_text("[]", encoding="utf-8")
    assert AB.review_skip(TAG) is None
    monkeypatch.setattr(AB, "CALL", lambda *a, **k: pytest.fail("不該呼叫 LLM"))
    AB.step_review(TAG)
    assert gate_b.review_items_v3(TAG)[1]["ok"] and AB.review_skip(TAG)


def test_wrong_revised_then_fact_spot_only_those_lines(env, monkeypatch):
    log = []
    plan = _clean_plan(editor_r1=_rev([]), player_r1=_rev([]), fact_r2=_rev([(4, "錯")]),
                       revise={"items": [{"line": 4, "new_line": "第四句才是中段開頭。", "note": ""}], "kept": []},
                       fact_spot=_rev([]))
    monkeypatch.setattr(AB, "CALL", _fake(env, plan, log))
    AB.step_review(TAG)
    assert _fns(log)[2:] == ["fact_r2", "revise", "fact_spot1"]
    spot = log[-1][1]
    assert ">> 4." in spot and ">> 3." not in spot
    assert AB.review_state(TAG)["done"] and _lines()[3] == "第四句才是中段開頭。"


def test_rerun_skips_when_narration_unchanged(env, monkeypatch):
    monkeypatch.setattr(AB, "CALL", _fake(env, _clean_plan(), []))
    AB.step_review(TAG)
    assert AB.review_skip(TAG)
    step = [s for s in AB.steps(TAG, "B", {}, SimpleNamespace(ver=None)) if s["step"] == "review"][0]
    assert step["skip"]()
    monkeypatch.setattr(AB, "CALL", lambda *a, **k: pytest.fail("不該呼叫 LLM"))
    AB.step_review(TAG)


def test_hand_edit_after_done_reviews_only_changed(env, monkeypatch):
    monkeypatch.setattr(AB, "CALL", _fake(env, _clean_plan(), []))
    AB.step_review(TAG)
    sc = env / TAG / "script.txt"
    sc.write_text(sc.read_text(encoding="utf-8").replace("第五句是中段結尾。", "第五句是手改過的結尾。"), encoding="utf-8")
    assert AB.review_skip(TAG) is None
    log = []
    monkeypatch.setattr(AB, "CALL", _fake(env, {"player_spot": _rev([]), "fact_spot": _rev([])}, log))
    AB.step_review(TAG)
    assert sorted(_fns(log)) == ["fact_spot1", "player_spot2"]
    assert all(">> 5." in p and ">> 4." not in p for _, p, _ in log)
    assert AB.review_skip(TAG)


def test_revise_number_change_rejected_and_retried(env, monkeypatch):
    log = []
    bad = {"items": [{"line": 1, "new_line": "第一句有 5 秒的空檔喔。", "note": ""}], "kept": []}
    plan = _clean_plan(editor_r1=_rev([]), player_r1=_rev([(1, "誇大")]), revise=bad)
    monkeypatch.setattr(AB, "CALL", _fake(env, plan, log))
    with pytest.raises(AB.Block, match="要問使用者"):  # 改不掉的誇大 → 問
        AB.step_review(TAG)
    assert _fns(log)[2:4] == ["revise", "revise_retry"]
    assert "數字集合不同" in log[3][1]
    assert _lines()[0] == "第一句有 3 秒的空檔。"
    st = AB.review_state(TAG)
    assert st["unresolved"][0]["line"] == 1
    pl = json.loads((_pd(env) / "player_review_r1.json").read_text(encoding="utf-8"))
    assert pl["revised"] == [] and "數字" in pl["kept"][0]["reason"]
