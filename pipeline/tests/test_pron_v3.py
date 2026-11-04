"""B4 讀音確定性化(PLAN_token重設計 §2(b) B2/B9):python -X utf8 -m pytest pipeline/tests/test_pron_v3.py -q
假專案放 repo tmp/ 下暫存目錄;paths.REPO 指到暫存根,所以 director_ab._pron_path 讀的是暫存根\\pipeline\\ 的假讀音檔,
絕不碰真的 pron_rules.json / cosy_pron.json / sub_words.txt。LLM 用 AB.CALL 注入假函式。"""
import json
import shutil
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director as D  # noqa: E402
import director_ab as AB  # noqa: E402
import paths  # noqa: E402
import pron_apply as PA  # noqa: E402
import pron_pre as PRE  # noqa: E402
from gates import gate_b4 as GB4  # noqa: E402

TAG = "demo4"
SCRIPT = """@title 測試
# 一、開場
me_old|他流血了,血量見底。
img:debt|她得到了獎勵,因為這樣。
img:a|為了這件事,大家都來了。
"""
RULES = {"_doc": "測試 doc", "血": {"model_default": "[x][uè]", "always": False, "rules": [{"words": ["流血"], "py": "[x][iě]"}]}}
PRON = {"_doc": "x", "遊戲": "遊[x][ì]"}
TERMS = {"_doc": "x", "_direct": ["Steam"], "_log": {}}
SUBW = "部門\r\n多元長\r\n"


def _w(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))
    return p


def _j(p, d):
    return _w(p, json.dumps(d, ensure_ascii=False, indent=1) + "\n")


def _r(data=None, ok=True):
    return SimpleNamespace(ok=ok, data=data, limited=False, error="", text="")


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    root = base / f"test_pron_v3_{uuid.uuid4().hex[:8]}"
    root.mkdir()
    real = paths.REPO
    for attr, sub in (("PROJECTS", "projects"), ("BUILD", "build"), ("OUTPUT", "output"), ("TMP", "tmp"), ("IMAGES", "images")):
        monkeypatch.setattr(paths, attr, root / sub)
    monkeypatch.setattr(paths, "REPO", root)
    monkeypatch.setattr(paths, "ROOT", root)
    monkeypatch.setenv("CV_BOARD_DIR", str(root / "channel"))
    (root / "channel").mkdir()
    pd = root / "projects" / TAG
    _j(pd / "brief.json", {"tag": TAG, "topic": "t", "angle": "a", "channel": "ChannelA", "format": "評論片", "flow": "v3"})
    _w(root / TAG / "script.txt", SCRIPT)
    pl = root / "pipeline"
    _j(pl / "pron_rules.json", RULES)
    _j(pl / "cosy_pron.json", PRON)
    _w(pl / "cosy_terms.json", json.dumps(TERMS, ensure_ascii=False, indent=1))   # 真檔結尾沒換行
    _w(pl / "sub_words.txt", SUBW)
    monkeypatch.setattr(AB, "commit_seg", lambda tag, seg: None)
    monkeypatch.setattr(GB4, "backlog_rows", lambda tag: [])
    monkeypatch.setattr(AB, "step_b4_prep", lambda tag, a: None)   # tts_script / sub_scan 是子程序,測試直接寫假結果
    yield SimpleNamespace(root=root, pd=pd, pl=pl, bd=root / "build" / TAG, real=real)
    shutil.rmtree(root, ignore_errors=True)


def _ts(env, open_=(), seams=0):
    lines = [{"i": 1, "text": "他流血了,血量見底。", "t": "他流血了,血量見底。", "shown": "他流血了,血量見底。", "seams": []}]
    _j(env.bd / "tts_script.json", {"tag": TAG, "lines": lines, "open": list(open_)})
    _w(env.bd / "tts_script.md", "x")
    _j(env.bd / "sub_scan.json", {"seams": seams, "seams_judge": 0})


POLY = {"kind": "poly", "src": "unverified", "line": 1, "pos": 5, "char": "血", "word": "血量", "current": "血量→[x][iě](word)"}
ARGS = SimpleNamespace(ver="v1")


def _read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- (a) 候選 0 → 不叫 LLM
def test_zero_candidates_no_llm(env):
    _ts(env)
    calls = []
    AB.CALL = lambda *a, **k: calls.append(a) or _r({"items": []})
    try:
        AB.step_pron_v3(TAG, {}, ARGS)
    finally:
        AB.CALL = None
    assert calls == []
    pr = _read(env.pd / "pron_review.json")
    assert pr["items"] == [] and pr["source"] == "pron_pre" and pr["counts"]["未決"] == 0
    assert GB4.open_items(TAG) == []


def test_candidates_shape(env):
    _ts(env, [POLY, {"kind": "english", "src": "direct_multi", "word": "Xbox", "lines": [1]}])
    c = PRE.candidates(TAG, write=False)
    assert c["n"] == 2 and len(c["poly"]) == 1 and len(c["english"]) == 1
    p = c["poly"][0]
    assert p["char"] == "血" and "血" in p["lookup"] and p["rules"]["model_default"] == "[x][uè]"


def test_reviewed_rule_not_candidate(env):
    rules = _read(env.pl / "pron_rules.json")
    rules["血"]["rules"].append({"words": ["血量"], "py": "[x][iě]", "unverified": True, "note": "2026-11-01 讀音審 old"})
    _j(env.pl / "pron_rules.json", rules)
    _ts(env, [POLY])
    assert PRE.candidates(TAG, write=False)["n"] == 0


# ---------------------------------------------------------------- (b) decisions → 只新增
def test_apply_only_added_and_errors(env):
    old = {n: (env.pl / n).read_bytes() for n in ("pron_rules.json", "cosy_pron.json", "cosy_terms.json", "sub_words.txt")}
    dec = [
        {"kind": "rule", "char": "血", "words": ["血量"], "py": "[x][iě]", "unverified": True, "note": "測試"},
        {"kind": "rule", "char": "為", "re": "為(?=了)", "py": "[w][èi]", "model_default": "[w][éi]", "unverified": True},
        {"kind": "word", "word": "手遊", "py": "手遊[x][ì]"},
        {"kind": "term", "word": "Xbox", "action": "direct"},
        {"kind": "sub_word", "word": "魷魚遊戲"},
        {"kind": "backlog", "word": "血", "context": "流血", "action": "不加", "reason": "已有"},
        # 以下都要進 errors、不寫
        {"kind": "rule", "char": "血", "words": ["血標"], "py": "[x][zzzz]"},
        {"kind": "rule", "char": "血", "re": "血(", "py": "[x][iě]"},
        {"kind": "rule", "char": "血", "words": ["流水"], "py": "[x][iě]"},
        {"kind": "word", "word": "遊戲", "py": "遊[x][ì]"},
        {"kind": "sub_word", "word": "部門"},
        {"kind": "nope"},
    ]
    res = PA.apply(dec, TAG)
    from tts_cosy_text import TOKENIZER_PY
    if not TOKENIZER_PY.exists():
        pytest.skip("沒有 CosyVoice tokenizer,token 驗證略過")
    assert len(res["added"]) == 5 and len(res["errors"]) == 6, res
    rules = _read(env.pl / "pron_rules.json")
    assert rules["血"]["rules"][-1]["words"] == ["血量"] and rules["血"]["rules"][-1]["unverified"] is True
    assert "讀音審" in rules["血"]["rules"][-1]["note"]
    assert rules["為"]["model_default"] == "[w][éi]" and rules["為"]["always"] is False
    assert AB._only_added(json.loads(old["pron_rules.json"]), rules)
    assert _read(env.pl / "cosy_pron.json")["手遊"] == "手遊[x][ì]"
    t = (env.pl / "cosy_terms.json").read_bytes()
    assert not t.endswith(b"\n") and "Xbox" in _read(env.pl / "cosy_terms.json")["_direct"] and AB._only_added(json.loads(old["cosy_terms.json"]), _read(env.pl / "cosy_terms.json"))
    sw = (env.pl / "sub_words.txt").read_bytes()
    assert sw == old["sub_words.txt"] + "魷魚遊戲\r\n".encode("utf-8")
    ap = _read(env.pd / "pron_apply.json")
    assert len(ap["added"]) == 5 and ap["backlog"][0]["word"] == "血"


def test_apply_self_check_restores(env, monkeypatch):
    before = (env.pl / "cosy_pron.json").read_bytes()
    monkeypatch.setattr(AB, "_only_added", lambda old, new: False)
    res = PA.apply([{"kind": "word", "word": "手遊", "py": "手遊[x][ì]"}], TAG)
    assert (env.pl / "cosy_pron.json").read_bytes() == before
    assert res["added"] == [] and any("還原" in e for e in res["errors"])


def test_step_pron_v3_applies_and_settles(env):
    _ts(env, [POLY])
    calls = []

    def call(tag, fn, prompt, **kw):
        calls.append((fn, kw.get("tools"), prompt))
        return _r({"items": [{"line": 1, "kind": "poly", "char": "血", "word": "血量", "current": "x", "status": "已決", "basis": "辭典 xiě",
                              "decision": {"kind": "rule", "char": "血", "words": ["血量"], "py": "[x][iě]", "unverified": True, "note": "血量 xiě"}}]})
    AB.CALL = call
    try:
        AB.step_pron_v3(TAG, {}, ARGS)
    finally:
        AB.CALL = None
    assert len(calls) == 1 and calls[0][1] == ("Read",) and "血量" in calls[0][2] and "Bash" not in str(calls[0][1])
    rules = _read(env.pl / "pron_rules.json")
    assert any(r.get("words") == ["血量"] for r in rules["血"]["rules"])
    pr = _read(env.pd / "pron_review.json")
    assert pr["source"] == "pron_pre+llm" and pr["counts"]["已決"] == 1 and GB4.open_items(TAG) == []
    assert _read(env.pd / "pron_apply.json")["decided"][0]["word"] == "血量"


def test_step_pron_v3_bad_decision_left_open(env):
    _ts(env, [POLY])
    AB.CALL = lambda tag, fn, prompt, **kw: _r({"items": [{"line": 1, "kind": "poly", "char": "血", "word": "血量", "current": "x", "status": "已決", "basis": "b",
                                                            "decision": {"kind": "rule", "char": "血", "words": ["流水"], "py": "[x][iě]"}}]})
    try:
        with pytest.raises(AB.Block):
            AB.step_pron_v3(TAG, {}, ARGS)
    finally:
        AB.CALL = None
    assert [i["status"] for i in _read(env.pd / "pron_review.json")["items"]] == ["未決"]
    assert GB4.open_items(TAG)


def test_seam_words_auto_written(env):
    _ts(env, seams=1)
    sub = _read(env.bd / "sub_scan.json")
    sub["seam_list"] = [{"line": 1, "a": "魷魚", "b": "遊戲", "why": "詞「魷魚遊戲」", "word": "魷魚遊戲", "token": True},
                        {"line": 1, "a": "他流", "b": "血了", "why": "詞「流血」", "word": "流血", "token": False}]
    _j(env.bd / "sub_scan.json", sub)
    rescans = []
    c = PRE.candidates(TAG, rescan=lambda: rescans.append(1))
    assert rescans == [1] and "魷魚遊戲" in (env.pd / "seam_words.txt").read_text(encoding="utf-8")
    assert "魷魚遊戲" in (env.bd / "words.txt").read_text(encoding="utf-8")
    assert len(c["seams"]) == 2      # 假 rescan 沒改 sub_scan.json:兩個都還在,交給 LLM
    # 已凍結片不寫
    _j(env.pd / "freeze.json", {})
    (env.pd / "seam_words.txt").unlink()
    c2 = PRE.candidates(TAG, rescan=lambda: rescans.append(2))
    assert rescans == [1] and not (env.pd / "seam_words.txt").exists() and len(c2["seams"]) == 2


# ---------------------------------------------------------------- (c) 雜湊 skip
def test_step_hash_skip(env):
    ran = []
    f = AB.memoized(TAG, "B4/pron", AB.hash_b4, lambda: ran.append(1))
    assert AB.memo_skip(TAG, "B4/pron", AB.hash_b4) is None            # 還沒成功過
    f()
    prod = _read(D.prod_path(TAG))
    assert list(prod["step_hash"]) == ["B4/pron"] and len(prod["step_hash"]["B4/pron"]) == 8
    assert "相同" in AB.memo_skip(TAG, "B4/pron", AB.hash_b4)
    assert AB.memo_skip(TAG, "B4/pron", AB.hash_b4, ok=lambda: False) is None      # gate 沒過不 skip
    rules = _read(env.pl / "pron_rules.json")                            # 讀音檔變 → 不 skip
    rules["血"]["rules"].append({"words": ["血標"], "py": "[x][iě]"})
    _j(env.pl / "pron_rules.json", rules)
    assert AB.memo_skip(TAG, "B4/pron", AB.hash_b4) is None
    AB.memoized(TAG, "B4/pron", AB.hash_b4, lambda: None)()
    assert AB.memo_skip(TAG, "B4/pron", AB.hash_b4)
    _w(env.root / TAG / "script.txt", SCRIPT + "img:z|多一句。\n")      # 旁白變 → 不 skip
    assert AB.memo_skip(TAG, "B4/pron", AB.hash_b4) is None
    assert _read(D.prod_path(TAG))["tag"] == TAG                          # 其他欄位還在


def test_step_hash_not_recorded_on_block(env):
    def boom():
        raise AB.Block("x")
    with pytest.raises(AB.Block):
        AB.memoized(TAG, "B4/pron", AB.hash_b4, boom)()
    assert "step_hash" not in (_read(D.prod_path(TAG)) if D.prod_path(TAG).exists() else {})


def test_v2_no_memo(env):
    _j(env.pd / "brief.json", {"tag": TAG, "channel": "ChannelA", "format": "評論片"})
    AB.memoized(TAG, "B4/pron", AB.hash_b4, lambda: None)()
    assert AB.memo_skip(TAG, "B4/pron", AB.hash_b4) is None
    assert "step_hash" not in (_read(D.prod_path(TAG)) if D.prod_path(TAG).exists() else {})


def test_gate_status_v3_uses_json(env):
    _ts(env)
    AB.step_pron_v3(TAG, {}, ARGS)
    names = [i["id"] for i in GB4.status(TAG, {}) if i["ok"]]
    assert "pron_review" in names
