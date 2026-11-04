"""字幕拆段性質測試(hypothesis;3_製作 §4):python -X utf8 pipeline\\tests\\test_props_build.py
不變量:不崩潰、字幕無標點、接回 = 原文(去標點與空白)、每段不超過 SUB_MAX_W(單一不可拆 token 例外)。
沒裝 hypothesis 印 skip、exit 0(安裝位置 tmp\\pytools)。"""
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "tmp" / "pytools"))
try:
    from hypothesis import HealthCheck, given, settings, strategies as st
except ImportError:
    print("skip: hypothesis 未安裝")
    sys.exit(0)
import build as B  # noqa: E402

PIECES = (list("我們今天要講的是遊戲公司為什麼會把這個玩家社群搞砸了嗎呢一二三四五十百萬億著過")
          + ["惡靈古堡", "安魂曲", "兩百萬", "30", "1,200", "3.5", "60%", "EA", "Call of Duty", "BioWare", "PS5",
             "，", "。", "、", "：", "；", "？", "！", ",", ";", ":", "?", "!", "…", "—", "-", "·",
             "「", "」", "《", "》", "（", "）", "(", ")", "『", "』", "\"", "“", "”", "~", "～",
             " ", "  ", "​", "‍", "﻿", "😀", "👍🏻", ".", "'", "【", "】", "〈", "〉", "[", "]", "Mr. Smith", "U.S.", "don't", "–", "‧", "ＡＢＣ", "１２３", "Ａ", "　", "\t"])
TEXT = st.lists(st.sampled_from(PIECES), max_size=40).map("".join) | st.text(max_size=30)
SET = settings(max_examples=400, deadline=None, suppress_health_check=list(HealthCheck), derandomize=True)
# 字幕可留的:數字間的千分位/小數點/冒號(1,200、3.5、10:30)
DIGIT_SEP = re.compile(r"(?<=\d)[,.:](?=\d)")


def norm(s):
    """去標點與空白後的比對字串(接回檢查用)。"""
    return "".join(c for c in s if not B._sub_punct(c) and c not in B.STRIP_SET and not c.isspace())


SYMBOLS = B.SUB_SYMBOLS   # 符號不是斷句標點,字幕照留(60%、A/B)
IN_WORD = re.compile(r"(?<=[A-Za-z0-9])[-'./:,](?=[A-Za-z0-9])")   # 英數詞內的連字號/撇號/點(Call-of、don't、U.S)


def puncts(txt):
    """字幕裡殘留的標點(Unicode P 類;數字分隔與英數詞內的符號不算)。"""
    t = IN_WORD.sub("", DIGIT_SEP.sub("", txt))
    return [c for c in t if unicodedata.category(c).startswith("P") and c not in SYMBOLS]


@SET
@given(TEXT)
def prop_split_phrases(text):
    ph = B.split_phrases(text)
    for txt, w in ph:
        assert txt and txt == txt.strip(), (text, txt)
        assert not puncts(txt), ("字幕留了標點", text, txt)
        toks = B.TOKEN_RE.findall(txt)
        assert B._dw(toks) <= B.SUB_MAX_W or len([t for t in toks if not t.isspace()]) == 1, ("超寬", text, txt)
        assert w > 0
    assert norm("".join(t for t, _ in ph)) == norm(DIGIT_SEP.sub("", text)).replace(",", "").replace(".", "").replace(":", "") \
        or norm("".join(t for t, _ in ph)) == norm(text), ("接回不等於原文", text, ph)


@SET
@given(TEXT)
def prop_sub_seams(text):
    B.sub_seams(text)
    B.sub_phrase_seams(text)


REGRESS = [   # 反例回歸句(找到過的 bug):2026-11-05 半形句點與【】〈〉等標點原樣留在字幕
    "Hello. World is big.", "Mr. Smith 說", "【公告】玩家〈回應〉", "這是 'quoted' 字",
]


def main():
    fails = 0
    for fn in (prop_split_phrases, prop_sub_seams):
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as e:   # noqa: BLE001
            fails += 1
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e!r}"[:600])
    for text in REGRESS:
        try:
            prop_split_phrases.hypothesis.inner_test(text)
        except Exception as e:   # noqa: BLE001
            fails += 1
            print(f"FAIL 回歸 {text!r}: {e!r}"[:400])
    print("全部通過" if not fails else f"{fails} 項失敗")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
