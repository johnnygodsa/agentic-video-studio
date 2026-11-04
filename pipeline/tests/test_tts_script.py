"""tts_script(配音稿)、seg 每片詞表、pron_backlog 測試:小 fixture,不配音、不讀 build 產物、不依賴 moe 下載檔。
python -X utf8 pipeline/tests/test_tts_script.py(或 -m pytest)
"""
import json
import sys
import tempfile
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))

import freeze as FZ  # noqa: E402
import paths as P  # noqa: E402
import pron_backlog as PB  # noqa: E402
import seg as SEG  # noqa: E402
import tts_script as TS  # noqa: E402


def test_annotate():
    assert TS.readable("[zh][í]") == "zhí"
    assert TS.annotate("執行長", "執行[zh][ǎng]") == "執行長[zhǎng]"
    assert TS.annotate("角色", "[j][iǎo]色") == "角[jiǎo]色"
    assert TS.annotate("得", "的") == "得[的]"
    assert TS.annotate("調漲", "[t][iáo][zh][ǎng]") == "調[tiáo]漲[zhǎng]"


def test_extract_words():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        proj, old = d / "projects", (P.PROJECTS, FZ.script_path)
        (proj / "t1").mkdir(parents=True)
        (d / "script.txt").write_text("標題\n《質量效應》續作喊停\n", encoding="utf-8")
        (proj / "t1" / "facts.md").write_text("《闇龍紀元》 Dragon Age 《沒出現在稿》\n", encoding="utf-8")
        (proj / "t1" / "spec.json").write_text(json.dumps({"tw_names": {"Mass Effect": {"tw": "質量效應"}}}), encoding="utf-8")
        P.PROJECTS, FZ.script_path = proj, (lambda tag: d / "script.txt")
        try:
            lines = [({"text": "做出《質量效應》的工作室,Dragon Age 也有人在玩", "hl": "工作室"}, "")]
            cut = lambda t: ["做出", "《", "質量", "效應", "》", "的", "工作", "室", ",", "Dragon Age", " ", "也", "有人", "在", "玩"]
            words = TS.extract_words("t1", lines, moe_words={"工作室", "人在", "質量"}, sub_words=["有人"], cut=cut)
        finally:
            P.PROJECTS, FZ.script_path = old
    assert "質量效應" in words and "Dragon Age" in words and "工作室" in words
    assert "沒出現在稿" not in words and "闇龍紀元" not in words     # 不在本片稿內不收
    assert "人在" not in words       # 跨斷詞界的偶然子字串不收
    assert "質量" not in words       # 本來就是一個斷詞單位,不必收


def test_seg_set_tag():
    before = list(SEG.sub_words())
    assert SEG.set_tag("__no_such_tag__") == 0 and SEG.sub_words() == before      # 沒有 words.txt -> 一字不差
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "words.txt"
        f.write_text("# 註解\n測試專名甲乙\n" + (before[0] if before else "") + "\n", encoding="utf-8")
        try:
            assert SEG.set_tag("x", f) == 1
            assert SEG.sub_words()[-1] == "測試專名甲乙" and SEG.sub_words()[:len(before)] == before
        finally:
            SEG._TAG_WORDS = []


def test_backlog_upsert():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "b.md"
        assert PB.upsert([("勾", "不勾也", "polyphone strong")] * 2, "a", f, "2026-10-01") == (1, 0)
        PB.upsert([("勾", "不勾也", "polyphone strong")] * 2, "a", f)          # 同片重跑不累加
        assert PB.load(f)[0]["命中次數"] == "2"
        PB.upsert([("勾", "不勾也", "g2p 不一致")], "b", f)
        r = PB.load(f)[0]
        assert r["命中次數"] == "3" and r["證據"] == "polyphone strong、g2p 不一致" and r["src"] == {"a": 2, "b": 1}
        rows = PB.load(f)
        rows[0]["狀態"] = "已驗證"
        PB.save(rows, f)
        PB.upsert([("勾", "不勾也", "g2p 不一致")], "c", f)
        assert PB.load(f)[0]["狀態"] == "已驗證"                               # 不降級
        PB.upsert([("差", "差不", "pron_rules 未驗證")], "c", f)
        assert [r["字"] for r in PB.top(3, f)] == ["差"]


def test_polyphone_items():
    rep = {"tag": "x", "items": [dict(char="倒", pos=2, kind="alt", evidence="strong", text="只能倒是"),
                                 dict(char="長", pos=0, kind="alt", evidence="weak", text="長大"),
                                 dict(char="和", pos=0, kind="other", evidence="strong", text="和平")]}
    assert PB.polyphone_items(rep) == [("倒", "能倒是", "polyphone strong")]


def test_verify_unfrozen():
    old = FZ.freeze_path
    FZ.freeze_path = lambda tag: P.REPO / "tmp" / "__no_such__" / "freeze.json"
    try:
        msgs = []
        assert TS.verify("__no_such__", out=msgs.append) == 0 and "未凍結" in msgs[0]
    finally:
        FZ.freeze_path = old


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
