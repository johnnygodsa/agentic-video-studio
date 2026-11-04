"""text_wrap 與 script_lint 文字 helper 性質測試(hypothesis):python -X utf8 pipeline\\tests\\test_props_text_lint.py
不變量:不崩潰;break_groups 串回 = 原文、不在行首禁則字前切;zwsp 去掉 U+200B = 原文;
clause_cut 去掉「|」= 原文;sentences 只含原文片段且不含句末標點;num_groups 每組都是原文子字串。
沒裝 hypothesis 印 skip、exit 0(安裝位置 tmp\\pytools)。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "tmp" / "pytools"))
try:
    from hypothesis import HealthCheck, given, settings, strategies as st
except ImportError:
    print("skip: hypothesis 未安裝")
    sys.exit(0)
import script_lint as L  # noqa: E402
import text_wrap as TW  # noqa: E402

PIECES = (list("我們今天要講的是遊戲公司為什麼會把玩家社群搞砸了嗎呢一二兩三十百萬億個款倍")
          + ["30", "1,200", "3.5", "60%", "2024", "EA", "Call of Duty", "PS5", "-", "，", "。", "、", "：", "？", "！",
             ",", ".", "?", "!", "「", "」", "《", "》", "（", "）", "(", ")", "…", "—", " ", "  ", "​", "﻿",
             "😀", "ＡＢ", "１２", "　", "\t", "\n", "|"])
TEXT = st.lists(st.sampled_from(PIECES), max_size=40).map("".join) | st.text(max_size=30)
SET = settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck), derandomize=True)


@SET
@given(TEXT)
def prop_text_wrap(text):
    if not text:
        return
    gs = TW.break_groups(text)
    assert "".join(gs) == text, ("break_groups 串回不等於原文", text, gs)
    for a, b in zip(gs, gs[1:]):
        assert b[0] not in TW._NO_BREAK_BEFORE, ("行首禁則字", text, gs)
    z = TW.zwsp(text)
    assert z.replace(TW.ZWSP, "") == text.replace(TW.ZWSP, ""), ("zwsp 改了原文", text, z)
    assert TW.zwsp(z) == z


@SET
@given(TEXT)
def prop_script_lint(text):
    c = L.clause_cut(text)
    assert c is None or c.replace("|", "") == text.replace("|", ""), ("clause_cut 改了原文", text, c)
    for _ln, s in L.sentences([(1, text)]):
        assert s and s in text and not set(s) & set("。?!？！"), ("sentences", text, s)
    for g in L.num_groups(text):
        assert g and g in text, ("num_groups", text, g)
    L.clen(text)
    L.report_sentence(text)
    L.source_lead(text)


def main():
    fails = 0
    for fn in (prop_text_wrap, prop_script_lint):
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as e:   # noqa: BLE001
            fails += 1
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e!r}"[:800])
    print("全部通過" if not fails else f"{fails} 項失敗")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
