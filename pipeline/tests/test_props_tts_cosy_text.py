"""讀音標注 apply_pron 性質測試(hypothesis):python -X utf8 pipeline\\tests\\test_props_tts_cosy_text.py
不變量(table 模式):不崩潰、非中文字(英數、標點、emoji、零寬字元)原樣且順序不變、中文字只會被換掉不會多出來、
重複套用結果不變(已標注的文字再送一次不再變)。沒裝 hypothesis 印 skip、exit 0(安裝位置 tmp\\pytools)。"""
import os
import re
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
os.environ.pop("COSY_ANNOTATE", None)   # table 模式(all 模式要 g2pw 模型,不在此測)
import tts_cosy_text as T  # noqa: E402

CJK = re.compile(r"[㐀-鿿]")
PIECES = (sorted(T.PRON) + sorted(T.RULE_CHARS) + list("我們他很高說銀行還沒開作看著的了是一不")
          + ["長得", "行長", "著作", "看著", "譯著色", "銀行", "EA", "PS5", "30", "，", "。", "：", "《", "》", "「", "」",
             " ", "​", "﻿", "😀", "ＡＢ", "１２", "　", "?", "!"])
TEXT = st.lists(st.sampled_from(PIECES), max_size=30).map("".join) | st.text(alphabet=st.characters(exclude_characters="[]"), max_size=20)
SET = settings(max_examples=400, deadline=None, suppress_health_check=list(HealthCheck), derandomize=True)


def plain(t):
    """標注 token([zh][ǎng])拿掉後的文字。"""
    return T.TOKEN_RE.sub("", t)


@SET
@given(TEXT)
def prop_apply_pron(text):
    out, hits = T.apply_pron(text)
    assert isinstance(hits, list)
    rest = plain(out)
    assert [c for c in rest if not CJK.match(c)] == [c for c in text if not CJK.match(c)], ("非中文字被改", text, out)
    assert len(CJK.findall(rest)) <= len(CJK.findall(text)), ("中文字變多", text, out)
    again = T.apply_pron(out)[0]
    assert again == out, ("重複套用結果不同", text, out, again)


REGRESS = [   # 反例回歸句(找到過的 bug):2026-11-05 同長詞重疊依詞表順序選,關卡關卡 被中間的 卡關 吃掉
    "關卡關卡", "卡關卡住",
]


def main():
    fails = 0
    try:
        prop_apply_pron()
        print("OK  prop_apply_pron")
    except Exception as e:   # noqa: BLE001
        fails += 1
        print(f"FAIL prop_apply_pron: {type(e).__name__}: {e!r}"[:800])
    for text in REGRESS:
        try:
            prop_apply_pron.hypothesis.inner_test(text)
        except Exception as e:   # noqa: BLE001
            fails += 1
            print(f"FAIL 回歸 {text!r}: {e!r}"[:400])
    print("全部通過" if not fails else f"{fails} 項失敗")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
