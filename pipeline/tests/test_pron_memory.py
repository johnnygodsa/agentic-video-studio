"""語境讀音記憶測試(不載模型):語境鍵、apply_pron 接入(記憶 > 詞表 > 規則;表空逐位元相同;同值不動命中鍵)、寫入規則、配音稿與聽審頁接入。
python -X utf8 -m pytest pipeline/tests/test_pron_memory.py"""
import json
import re
import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import listen_page as LP  # noqa: E402
import pron_memory as PM  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import tts_pron_verify as V  # noqa: E402
import tts_script as TS  # noqa: E402

SAMPLES = ["他跟著你走,覺得很好。", "艾莉遞給你的彈藥和補血道具。", "《最後生還者》的遊戲規則很長,EA 也調好了。", "穿著打扮要好看。"]
READ = {"著": "zhe5", "左": "zuo3", "住": "zhu4", "寫": "xie3", "穴": "xue4"}
ALL = {"著": {"zhe5", "zhu4", "zhuo2", "zhao2"}, "血": {"xie3", "xue4"}}


class FakePhon:
    def one(self, c):
        return READ.get(c, c)

    def all(self, c):
        return ALL.get(c, {self.one(c)})

    def key(self, c, py=None):
        return re.sub(r"\d", "", py or self.one(c))


@pytest.fixture
def mem(tmp_path, monkeypatch):
    f = tmp_path / "pron_memory.json"
    monkeypatch.setattr(PM, "MEM_FILE", f)
    PM._CACHE.clear()

    def write(*entries):
        PM.save({"_doc": "t", "entries": list(entries)}, f)
        return f
    write.path = f
    yield write
    PM._CACHE.clear()


def entry(ch, left, right, py="", state="ok", fix=None, evidence="ear", **kw):
    return PM.make_entry(ch, left, right, py, state, evidence, fix=fix if fix is not None else PM.fix_of(ch, py), **kw)


# ------------------------------------------------------------ 表空
def test_empty_or_missing_table_is_identical(mem):
    missing = [CT.pron_text(s) for s in SAMPLES]
    assert not mem.path.exists()
    mem()
    assert [CT.pron_text(s) for s in SAMPLES] == missing
    assert PM.scan(SAMPLES[0]) == [] and not PM.has_entries()


def test_shipped_table_has_doc_and_passes_check():
    """正式表由 tts_c0 / tts_pron_verify 自動寫入(2026-10-31 起不再是空表):要有 _doc、格式檢查無錯誤。"""
    doc = json.loads((PIPE / "pron_memory.json").read_text(encoding="utf-8"))
    assert doc["_doc"] and isinstance(doc["entries"], list)
    errs, _conflicts = PM.check(doc)
    assert not errs, errs[:5]


# ------------------------------------------------------------ 語境鍵
def test_context_boundaries_and_alnum():
    assert PM.context("穿著打扮", 1) == dict(l2="|穿", r2="打扮", l1="穿", r1="打")
    t = "他,穿著打。"
    assert PM.context(t, 3) == dict(l2="|穿", r2="打|", l1="穿", r1="打")
    assert PM.context("RPG 3 穿著 Steam", 7)["l2"] == "#穿"
    assert PM.context("RPG 3 穿著 Steam", 7)["r1"] == "#"
    assert PM.context("[y][ì][d][iàn]穿著", 15)["l2"] == "#穿"


def test_scan_prefers_longer_context(mem):
    mem(entry("著", "穿", "打", "[zh][uó]"), entry("著", "|穿", "打扮", "[zh][ù]"), entry("著", "*", "*", "[zh][áo]"))
    t = "穿著打扮"
    assert PM.scan(t)[0][1]["py"] == "[zh][ù]"
    assert PM.scan("他穿著打人")[0][1]["py"] == "[zh][uó]"
    assert PM.scan("他看著人")[0][1]["py"] == "[zh][áo]"


# ------------------------------------------------------------ apply_pron 接入
def test_memory_beats_rule_and_key_format(mem):
    before = CT.pron_text("穿著打扮要好看。")
    rec = dict(pron_hits=CT.pron_hits("穿著打扮要好看。"))
    mem(entry("著", "穿", "打", "[zh][ù]"))
    text, hits = CT.pron_text("穿著打扮要好看。")
    assert "穿[zh][ù]打" in text and text != before[0]
    key = "穿著打→[zh][ù]"
    assert key in hits and CT.pron_hits("穿著打扮要好看。")[key] == "[zh][ù]"
    assert CT.pron_changed(rec, "穿著打扮要好看。")


def test_same_value_keeps_hits_and_cache(mem):
    say = "他跟著你走。"
    text, hits = CT.pron_text(say)
    rec = dict(pron_hits=CT.pron_hits(say))
    mem(entry("著", "跟", "你", "着"))
    assert CT.pron_text(say) == (text, hits)
    assert not CT.pron_changed(rec, say)


def test_memory_trims_word_table_span(mem):
    say = "遊戲的規則。"
    assert "[x][ì]" in CT.pron_text(say)[0]
    mem(entry("戲", "遊", "的", "[h][ū]"))
    text, hits = CT.pron_text(say)
    assert "遊[h][ū]的" in text and "[x][ì]" not in text and "遊戲的→[h][ū]" in hits


def test_memory_marks_unannotated_char(mem):
    assert "[" not in CT.pron_text("一二三。")[0]
    mem(entry("二", "一", "三", "[l][iǎng]"))
    assert CT.pron_text("一二三。")[0] == "一[l][iǎng]三。"


def test_bad_mark_applies_rewrite_and_undetermined_do_not(mem):
    say = "一二三。"
    base = CT.pron_text(say)
    mem(entry("二", "一", "三", "[l][iǎng]", state="bad", fix=dict(type="rewrite", value=say)))
    assert CT.pron_text(say) == base
    assert PM.blocking(PM.scan(say)[0][1])
    mem(entry("二", "一", "三", "[l][iǎng]", state="undetermined"))
    assert CT.pron_text(say) == base
    mem(entry("二", "一", "三", "", state="bad", fix=dict(type="mark", value="[l][iǎng]")))
    assert "[l][iǎng]" in CT.pron_text(say)[0]


def test_zhe_fix_and_qc_targets_follow_memory(mem):
    mem(entry("著", "名", "人", "着", fix=dict(type="zhe", value="着")))
    assert "名着人" in CT.pron_text("著名著人。")[0]
    mem(entry("血", "補", "道", "[x][uè]"))
    ev = CT._live_events("補血道具", CT._word_spans("補血道具")[0])
    assert ev == [(1, "血", "[x][uè]", "補血道→[x][uè]", "memory", False)]


# ------------------------------------------------------------ 寫入規則
def test_upsert_ear_over_test_and_test_cannot_override_ear():
    doc = {"entries": []}
    assert PM.upsert(doc, entry("著", "穿", "打", "[zh][uó]", evidence="test", n_right=2, wrong_as=[dict(heard="左", kind="other")])) == "added"
    assert PM.upsert(doc, entry("著", "穿", "打", "[zh][ù]")) == "replaced"
    e = doc["entries"][0]
    assert e["evidence"] == "ear" and e["py"] == "[zh][ù]" and e["wrong_as"]
    assert PM.upsert(doc, entry("著", "穿", "打", "[zh][uó]", evidence="test", n_right=3)) == "ear_kept"
    assert doc["entries"][0]["py"] == "[zh][ù]"


def test_contradiction_splits_to_2plus2_with_tombstone(mem):
    a = entry("著", "穿", "打", "[zh][uó]", evidence="test", n_right=3, ctx=("|穿", "打扮"))
    b = entry("著", "穿", "打", "", state="bad", evidence="test", n_wrong=1, fix=dict(type="rewrite", value="x"), ctx=("他穿", "打人"))
    doc = {"_doc": "t", "entries": []}
    PM.upsert(doc, a)
    assert PM.upsert(doc, b, "r1") == "conflict"
    keys = {(e["left"], e["right"]): e for e in doc["entries"]}
    assert keys[("穿", "打")].get("tombstone") and keys[("|穿", "打扮")]["conflict"] and keys[("他穿", "打人")]["conflict"]
    PM.save(doc, mem.path)
    assert PM.scan("穿著打扮")[0][1]["py"] == "[zh][uó]"
    assert PM.scan("你穿著打他") == []            # 其他 2+2 不吃 tombstone
    assert PM.upsert(doc, entry("著", "穿", "打", "[zh][uó]", evidence="test", n_right=2, ctx=("你穿", "打他"))) == "added"
    assert any(e["left"] == "你穿" and e.get("conflict") for e in doc["entries"])
    assert PM.check(doc)[1]


def test_same_2plus2_contradiction_stays_in_one_row():
    doc = {"entries": []}
    PM.upsert(doc, entry("著", "穿", "打", "[zh][uó]", evidence="test", n_right=3, ctx=("|穿", "打扮")))
    assert PM.upsert(doc, entry("著", "穿", "打", "[zh][ù]", evidence="test", n_right=3, ctx=("|穿", "打扮"))) == "conflict"
    e = doc["entries"][0]
    assert len(doc["entries"]) == 1 and e["state"] == "undetermined" and e["fix"] is None and e["conflicts"][0]["py"] == "[zh][ù]"


def pos(result, main="right", second="same", hyp="住", want="zhuo2", ch="著"):
    return dict(pos=1, ch=ch, want=want, main=main, second=second, hyp_main=hyp, hyp_second=None, result=result)


def test_seed_outcome_requires_heard_reading():
    assert PM.seed_outcome(pos("right")) == "right"
    assert PM.seed_outcome(pos("right", main="same", second="other")) == "undetermined"
    assert PM.seed_outcome(pos("wrong", main="wrong")) == "wrong"


def row(results, py="[zh][uó]", text="穿著打扮"):
    return dict(text=text, pos=1, ch="著", py=py, results=results, tag="t1", rewrite=text)


def test_record_tests_states_and_rerun(mem):
    acts = PM.record_tests([row([pos("right"), pos("right"), pos("undetermined", main="same")])], "c0:a", FakePhon())
    assert acts["added"] == 1
    e = PM.load()["entries"][0]
    assert (e["state"], e["evidence"], e["n_right"], e["n_undetermined"], e["seeds"]) == ("ok", "test", 2, 1, 3)
    assert (e["left"], e["right"], e["ctx"], e["fix"]) == ("穿", "打", ["|穿", "打扮"], dict(type="mark", value="[zh][uó]"))
    assert PM.record_tests([row([pos("right"), pos("right")])], "c0:a", FakePhon())["skipped"] == 1
    assert PM.load()["entries"][0]["seeds"] == 3


def test_record_tests_one_right_is_undetermined_and_wrong_is_bad(mem):
    PM.record_tests([row([pos("right")])], "a")
    assert PM.load()["entries"][0]["state"] == "undetermined"
    PM.save({"entries": []})
    w = pos("wrong", main="wrong", hyp="住")
    PM.record_tests([row([w, pos("right")])], "b", FakePhon())
    e = PM.load()["entries"][0]
    assert e["state"] == "bad" and e["fix"] == dict(type="rewrite", value="穿著打扮")
    assert e["wrong_as"] == [dict(heard="住", kind="alt_reading")]
    PM.save({"entries": []})
    PM.record_tests([row([pos("wrong", main="wrong", hyp="左")])], "c", FakePhon())
    assert PM.load()["entries"][0]["wrong_as"][0]["kind"] == "token_unstable"


def test_record_tests_undetermined_then_ok_merges(mem):
    PM.record_tests([row([pos("right")])], "a")
    PM.record_tests([row([pos("right")])], "b")
    e = PM.load()["entries"][0]
    assert e["state"] == "ok" and e["n_right"] == 2 and len(PM.load()["entries"]) == 1


def test_check_catches_bad_rows():
    bad = entry("著", "穿", "打", "[nope]", state="ok", evidence="test", n_right=1)
    bad["wrong_as"] = [dict(heard="x", kind="?")]
    errs, _ = PM.check({"entries": [bad, dict(bad), dict(char="x")]}, tokens={"[zh]"})
    text = "\n".join(errs)
    assert "唸對" in text and "token" in text and "kind" in text and "同鍵" in text and "缺欄位" in text


# ------------------------------------------------------------ 接入點
def test_pron_view_shows_memory(mem):
    mem(entry("二", "一", "三", "[l][iǎng]"))
    shown, hits, unv, t = TS.pron_view("一二三。")
    assert "二[liǎng]" in shown and any("(記憶)" in h for h in hits) and t == "一二三。"


def test_listen_page_lists_undetermined(mem):
    recs = [dict(idx=1, text="一二三。"), dict(idx=2, text="四五六。")]
    assert LP.pick_reasons(recs) == {}
    mem(entry("二", "一", "三", "[l][iǎng]", state="undetermined"))
    r = LP.pick_reasons(recs)
    assert list(r) == [1] and r[1][0][0] == "mem_pending" and "一二三" in r[1][0][1]


def test_verify_writes_memory(mem):
    item = dict(id=0, mtext="穿著打扮", say="穿著打扮", ch="著", py="[zh][uó]", tag="t1", rule="著#0")
    res = [dict(item=item, seed=s, rec={}, judge=dict(result="right", positions=[pos("right")])) for s in (1, 2)]
    res.append(dict(item=item, seed=3, rec=None, judge=None))
    assert V.record_memory(res, "verify:d", FakePhon())["added"] == 1
    assert V.record_memory(res, "verify:d", FakePhon())["skipped"] == 1
    e = PM.load()["entries"][0]
    assert e["state"] == "ok" and e["tag"] == "t1" and e["n_right"] == 2


def test_cli_add_list_lookup_check(mem, capsys):
    assert PM.main(["add", "二", "--left", "一", "--right", "三", "--py", "[l][iǎng]", "--heard", "而", "--kind", "alt_reading"]) == 0
    assert PM.main(["add", "著", "--any", "--py", "着", "--fix-type", "zhe", "--evidence", "ear"]) == 0
    assert PM.main(["lookup", "一二三"]) == 0
    assert PM.main(["list", "--char", "二"]) == 0
    assert PM.main(["check"]) == 0
    out = capsys.readouterr().out
    assert "added" in out and "位置 1" in out and "共 1 筆" in out and "錯誤 0" in out
    rows = PM.load()["entries"]
    assert rows[0]["evidence"] == "ear" and rows[0]["fix"]["type"] == "mark" and rows[1]["left"] == "*" and rows[1]["fix"]["type"] == "zhe"
