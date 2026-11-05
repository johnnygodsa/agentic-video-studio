"""P5 C 段 decide 步(decide_step.py + pron_apply.verify + decide_list 已決定節 + listen_page 優先聽):
python -X utf8 pipeline/tests/test_decide_step.py   或   python -X utf8 -m pytest pipeline/tests/test_decide_step.py -q -p no:cacheprovider
LLM 換假(AB.CALL)、辭典/記憶換假;假 tag 與假詞表放 tmp\\test_decide_step\\,絕不寫真詞表(director_ab._pron_path、paths.PROJECTS、paths.output_dir 都指到 tmp)。"""
import copy
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
sys.path.insert(0, str(PIPE))

import decide_list as DL  # noqa: E402
import decide_step as DS  # noqa: E402
import director as D  # noqa: E402
import director_ab as AB  # noqa: E402
import paths as P  # noqa: E402
import pron_apply as PA  # noqa: E402
import tts_cosy_text as CT  # noqa: E402

TMP = PIPE.parent / "tmp" / "test_decide_step"
TEXTS = ["AAA 和 BBB 一起來", "研究者很多"]          # 未定 3:AAA、BBB(cosy_terms)、究(cosy_pron)
RULE_TEXTS = TEXTS + ["他們長怎樣"]                   # 再加一條標 unverified 的規則
GLOBALS = ("PRON", "PRON_VERIFIED", "TERMS", "TERMS_VERIFIED", "DIRECT", "RULES_RAW", "RULE_CHARS", "RULE_WORDS", "RULE_REGS")

TABLES = {
    "cosy_terms.json": {"_doc": "t", "_verified": ["OLD"], "_log": {"OLD": "舊"}, "_direct": [], "OLD": "o l d", "AAA": "a a a", "BBB": "bee"},
    "cosy_pron.json": {"_doc": "t", "_verified": ["舊詞"], "究": "[j][iū]", "舊詞": "[j][iù]"},
    "pron_rules.json": {"_doc": "t", "_verified": ["舊→[x]"], "長": {"model_default": "[ch][áng]", "always": False, "rules": [
        {"words": ["長怎樣"], "py": "[zh][ǎng]", "pos": [0], "unverified": True, "note": "新"}]}},
    "sub_words.txt": None,
}


def _bytes(env):
    return {n: (env.tables / n).read_bytes() for n in TABLES}


@pytest.fixture
def env(request, monkeypatch):
    d = TMP / request.node.name.replace("[", "_").replace("]", "")
    tables = d / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    for n, v in TABLES.items():
        txt = "" if v is None else json.dumps(v, ensure_ascii=False, indent=1) + "\n"
        (tables / n).write_bytes((txt.replace("\n", "\r\n") if n == "pron_rules.json" else txt).encode("utf-8"))   # 真檔 pron_rules.json 是 CRLF
    tag = f"t_{time.time_ns()}"
    saved = {k: getattr(CT, k) for k in GLOBALS}
    monkeypatch.setattr(AB, "_pron_path", lambda n: tables / n)
    monkeypatch.setattr(P, "PROJECTS", d / "projects")
    monkeypatch.setattr(P, "output_dir", lambda t: d / "output" / t)
    monkeypatch.setattr(DS, "_lookup", lambda q: [f"(假辭典){q}"])
    monkeypatch.setattr(DS, "_memory", lambda chars: [])
    monkeypatch.setattr(PA, "_tokens", lambda: None)     # 不依賴 tokenizer 檔
    (d / "projects" / tag).mkdir(parents=True, exist_ok=True)
    calls = []
    monkeypatch.setattr(AB, "CALL", None)
    yield SimpleNamespace(tag=tag, ver="v1", tables=tables, d=d, calls=calls)
    for k, v in saved.items():                          # 還原 tts_cosy_text 全域(別的測試用真表)
        setattr(CT, k, v)


def _llm(env, monkeypatch, rounds):
    """rounds = 每次 LLM 呼叫回的 items list(依序);超過就回空。"""
    seq = iter(rounds)

    def fake(tag, fn, prompt, **kw):
        env.calls.append({"fn": fn, "prompt": prompt, "kw": kw})
        return SimpleNamespace(ok=True, limited=False, error=None, data={"items": next(seq, [])})
    monkeypatch.setattr(AB, "CALL", fake)


def _ok(src, key, basis="辭典/慣例相符", **extra):
    return {"src": src, "key": key, "status": "已決", "decision": extra.get("decision") or {}, "basis": basis}


ALL3 = [_ok("cosy_terms", "AAA"), _ok("cosy_terms", "BBB"), _ok("cosy_pron", "究")]


def _tbl(env, name):
    return json.loads((env.tables / name).read_text(encoding="utf-8"))


def test_three_undecided_decide_to_zero_and_only_added(env, monkeypatch):
    before = {n: json.loads(b) for n, b in ((n, (env.tables / n).read_bytes()) for n in ("cosy_terms.json", "cosy_pron.json"))}
    _llm(env, monkeypatch, [ALL3])
    refresh = DS.refresh_tables()
    assert len(DS.candidates(TEXTS)) == 3 and refresh is CT
    r = DS.run(env.tag, env.ver, TEXTS)
    assert r["before"] == 3 and r["rounds"] == 1 and len(r["decided"]) == 3 and len(env.calls) == 1
    assert env.calls[0]["kw"]["agent"] == "pron-review" and env.calls[0]["kw"]["tools"] == ("Read",) and env.calls[0]["kw"]["model"] == "sonnet"
    t, p = _tbl(env, "cosy_terms.json"), _tbl(env, "cosy_pron.json")
    assert {"AAA", "BBB"} <= set(t["_verified"]) and "究" in p["_verified"]
    assert AB._only_added(before["cosy_terms.json"], t) and AB._only_added(before["cosy_pron.json"], p)   # 既有條目不變
    assert (t["AAA"], t["BBB"], p["究"]) == ("a a a", "bee", "[j][iū]")
    assert "AAA" in t["_log"] and t["_log"]["OLD"] == "舊"
    md = (env.d / "output" / env.tag / f"decide_{env.ver}.md").read_text(encoding="utf-8")
    assert DL.count_undecided(env.tag, env.ver) == (0, 0) and "④ 已決定" in md and "AAA" in md and "究" in md
    assert sorted(DL.decided_lines(env.tag, env.ver)) == [1, 2]


def test_incomplete_then_second_round_completes(env, monkeypatch):
    _llm(env, monkeypatch, [[_ok("cosy_terms", "AAA")], [_ok("cosy_terms", "BBB"), _ok("cosy_pron", "究")]])
    r = DS.run(env.tag, env.ver, TEXTS)
    assert r["rounds"] == 2 and len(r["decided"]) == 3
    assert "上一輪" in env.calls[1]["prompt"] and "BBB" in env.calls[1]["prompt"] and '"key": "AAA"' not in env.calls[1]["prompt"].split("候選:")[1]


def test_incomplete_twice_blocks_with_left(env, monkeypatch):
    _llm(env, monkeypatch, [[_ok("cosy_terms", "AAA")], []])
    with pytest.raises(AB.Block, match=r"唸法未定 2"):
        DS.run(env.tag, env.ver, TEXTS)
    assert len(env.calls) == 2                                   # LLM 最多兩輪
    assert DL.count_undecided(env.tag, env.ver) == (1, 1)        # decide 清單照實寫:BBB、究仍未定 → gate 不放行
    assert "AAA" in _tbl(env, "cosy_terms.json")["_verified"] and "BBB" not in _tbl(env, "cosy_terms.json")["_verified"]


def test_status_undecided_never_verified(env, monkeypatch):
    before = _bytes(env)
    nope = [{"src": s, "key": k, "status": "未決", "decision": {}, "basis": "不確定"} for s, k in (("cosy_terms", "AAA"), ("cosy_terms", "BBB"), ("cosy_pron", "究"))]
    _llm(env, monkeypatch, [nope, nope])
    with pytest.raises(AB.Block, match="唸法未定 3"):
        DS.run(env.tag, env.ver, TEXTS)
    assert _bytes(env) == before                                  # 一個位元組都沒動


def test_zero_candidates_no_llm(env, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("未定 0 不該叫 LLM")
    monkeypatch.setattr(AB, "CALL", boom)
    r = DS.run(env.tag, env.ver, ["沒有英文也沒有標注"])
    assert r["before"] == 0 and r["rounds"] == 0


def test_decision_adds_only_and_never_overwrites(env, monkeypatch):
    """LLM 想改既有條目(term AAA 換寫法)→ pron_apply 擋(已有),既有值不變;新詞 CCC 的 term decision 才新增,並一併標已驗。"""
    t = json.loads((env.tables / "cosy_terms.json").read_text(encoding="utf-8"))
    texts = TEXTS + ["CCC 出現"]
    bad = _ok("cosy_terms", "AAA", decision={"kind": "term", "word": "AAA", "py": "totally changed"})
    comp = _ok("cosy_pron", "究", decision={"kind": "term", "word": "CCC", "py": "c c c"})
    _llm(env, monkeypatch, [[bad, _ok("cosy_terms", "BBB"), comp]])
    r = DS.run(env.tag, env.ver, texts)
    t2 = _tbl(env, "cosy_terms.json")
    assert t2["AAA"] == t["AAA"] and t2["CCC"] == "c c c" and "CCC" in t2["_verified"] and AB._only_added(t, t2)
    assert r["left"] == []


def test_verify_rule_flag_flip_only(env, monkeypatch):
    """pron_rules:unverified true -> false + `_verified` 加鍵;其餘(py、words、pos、note、舊鍵)一個字都不變。"""
    old = _tbl(env, "pron_rules.json")
    _llm(env, monkeypatch, [ALL3 + [_ok("pron_rules", "長怎樣→[zh][ǎng]")]])
    r = DS.run(env.tag, env.ver, RULE_TEXTS)
    assert r["before"] == 4 and len(r["decided"]) == 4
    new = _tbl(env, "pron_rules.json")
    assert new["長"]["rules"][0]["unverified"] is False and "長怎樣→[zh][ǎng]" in new["_verified"]
    expect = copy.deepcopy(old)
    expect["長"]["rules"][0]["unverified"] = False
    expect["_verified"] = old["_verified"] + ["長怎樣→[zh][ǎng]"]
    assert new == expect
    raw = (env.tables / "pron_rules.json").read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") > 0                  # 原檔 CRLF 維持,不整檔換行
    assert DL.count_undecided(env.tag, env.ver) == (0, 0)


def test_verify_unknown_key_rejected_file_untouched(env):
    before = _bytes(env)
    res = PA.verify([{"file": "cosy_terms", "key": "ZZZ"}, {"file": "pron_rules", "key": "沒有→[x]"}, {"file": "cosy_pron", "key": "_doc"}, {"file": "x", "key": "AAA"}], env.tag)
    assert not res["verified"] and len(res["errors"]) == 4
    assert _bytes(env) == before


def test_verified_only_checker():
    old = {"_verified": ["a"], "長": {"rules": [{"py": "[a]", "unverified": True, "words": ["w"]}], "model_default": "[b]"}}
    ok = copy.deepcopy(old)
    ok["_verified"].append("b")
    ok["長"]["rules"][0]["unverified"] = False
    assert PA._verified_only(old, ok)
    for mut in (lambda d: d["長"]["rules"][0].__setitem__("py", "[c]"),            # 改既有讀音
                lambda d: d["長"]["rules"][0].__setitem__("words", ["w", "x"]),   # 改 words
                lambda d: d["長"]["rules"].append({"py": "[d]"}),                  # 新增規則(verify 不准)
                lambda d: d.__setitem__("新字", {}),                               # 新增頂層條目
                lambda d: d["_verified"].remove("a")):                             # 拿掉舊鍵
        bad = copy.deepcopy(ok)
        mut(bad)
        assert not PA._verified_only(old, bad)
    flip_back = copy.deepcopy(old)
    flip_back["長"]["rules"][0]["unverified"] = True
    bad2 = copy.deepcopy(old)
    bad2["長"]["rules"][0]["unverified"] = False
    assert PA._verified_only(old, bad2) and not PA._verified_only(bad2, flip_back)   # false -> true 不行


def test_c_plan_has_decide_step_between_c0_and_qc():
    steps = [s["step"] for s in D.plan_steps("t_no_such_tag", "C", {}, SimpleNamespace(ver="v1", backend=None))]
    assert steps.index("c0") < steps.index("唸法決定") < steps.index("後端") < steps.index("改句迴圈") < steps.index("配音凍結")


def test_listen_reason_for_decided_lines(env, monkeypatch):
    import listen_page as LP
    DS._save(env.tag, env.ver, [{"src": "cosy_terms", "key": "AAA", "lines": [2], "sample": "x", "current": "寫法 a", "basis": "b", "round": 1, "at": "2026-11-05"}])
    recs = [{"idx": 1, "text": "一"}, {"idx": 2, "text": "二"}, {"idx": "2.1", "text": "二半"}]
    monkeypatch.setattr(LP, "e4_items", lambda tag, ver: {})
    why = LP.pick_reasons(recs, env.tag, env.ver)
    assert 1 not in why and any(c == "director_decided" for c, _ in why[2]) and any(c == "director_decided" for c, _ in why["2.1"])
    assert not LP.is_must(why[2])                                  # 列「其他待聽」,不升必聽


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
