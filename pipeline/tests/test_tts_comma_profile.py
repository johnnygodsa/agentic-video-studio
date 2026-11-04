"""逗號停頓側寫(--comma-profile)的單元測試(不需顯示卡):python -X utf8 -m pytest pipeline/tests/test_tts_comma_profile.py -q
1. comma_params:std 任意句回現行常數;long 長句(子句 >= 3 或字數 >= 35)回 long 值,短句回 std 值。
2. 合成的正弦波 + 靜音:長句單位逗號處 0.33 秒靜音,std 剪到 <= 0.22、long 保留;短句單位兩種側寫結果相同。
3. 不傳 profile 與傳 std 結果位元相同。
4. trim_key:long 含 comma=long 後綴,std 與原公式相同。"""
import hashlib
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import tts_key as TK  # noqa: E402
import tts_pause as TP  # noqa: E402

SR = 24000
STD = dict(COMMA_MIN=0.10, COMMA_MAX=0.22, COMMA_TARGET=0.20)
LONG = dict(COMMA_MIN=0.16, COMMA_MAX=0.38, COMMA_TARGET=0.26)
LONG_TEXT = "啊啊，啊啊，啊啊。"      # 3 子句
SHORT_TEXT = "啊啊，啊啊。"          # 2 子句、4 字


def tone(sec, amp=0.5, f=180.0):
    return (amp * np.sin(2 * np.pi * f * np.arange(int(sec * SR)) / SR)).astype(np.float32)


def sil(sec):
    return np.zeros(int(sec * SR), dtype=np.float32)


def long_case(gap):
    """3 段語音(各 0.6 秒、2 字)之間兩個 gap 秒的靜音,再接 0.2 秒句尾靜音;回傳 (波形, 各字時間)。"""
    w = np.concatenate([tone(0.6), sil(gap), tone(0.6), sil(gap), tone(0.6), sil(0.2)])
    s1, s2 = 0.6 + gap, 1.2 + 2 * gap
    return w, [[0, .3], [.3, .6], [s1, s1 + .3], [s1 + .3, s1 + .6], [s2, s2 + .3], [s2 + .3, s2 + .6]]


def short_case(gap):
    w = np.concatenate([tone(0.6), sil(gap), tone(0.6), sil(0.2)])
    s1 = 0.6 + gap
    return w, [[0, .3], [.3, .6], [s1, s1 + .3], [s1 + .3, s1 + .6]]


def measured(w, text, times):
    return TP.measure_pauses(w, SR, text, times)


def test_comma_params():
    assert TP.comma_params("啊" * 60, "std") == STD
    assert TP.comma_params(LONG_TEXT, "std") == STD
    assert TP.comma_params(LONG_TEXT, "long") == LONG                       # 3 子句
    assert TP.comma_params("啊" * 36 + "，啊。", "long") == LONG              # 2 子句但 >= 35 字
    assert TP.comma_params(SHORT_TEXT, "long") == STD                       # 短句
    assert TP.comma_params("", "long") == STD and TP.comma_params(None, "long") == STD
    assert TP.comma_params("甲，乙；丙", "long") == LONG                     # ;也算子句分隔
    assert TP.PROFILES["std"] == STD and TP.PROFILES["long"] == LONG


def test_long_sentence_keeps_long_pause():
    w, t = long_case(0.33)
    ps = measured(w, LONG_TEXT, t)
    assert len(ps) == 2 and all(abs(p["sil"] - 0.33) <= 0.011 for p in ps), ps
    w_std, acts_std = TP.fix_pauses(w, SR, ps, LONG_TEXT, "std")
    ps_std = measured(w_std, LONG_TEXT, t)
    assert acts_std == {1: "trim", 3: "trim"} and all(p["sil"] <= TP.COMMA_MAX for p in ps_std), (acts_std, ps_std)
    w_long, acts_long = TP.fix_pauses(w, SR, ps, LONG_TEXT, "long")
    assert acts_long == {} and len(w_long) == len(w) and np.array_equal(w_long, w)
    assert not TP.out_of_range(ps, LONG_TEXT, "long") and TP.out_of_range(ps, LONG_TEXT, "std")


def test_long_profile_pads_short_pause_to_long_target():
    w, t = long_case(0.12)      # std 下已合格(0.10-0.22),long 下不足 0.16 -> 補到 0.26
    ps = measured(w, LONG_TEXT, t)
    assert not TP.out_of_range(ps, LONG_TEXT, "std") and TP.out_of_range(ps, LONG_TEXT, "long")
    w2, acts = TP.fix_pauses(w, SR, ps, LONG_TEXT, "long")
    ps2 = measured(w2, LONG_TEXT, t)
    assert acts == {1: "insert", 3: "insert"}
    assert all(abs(p["sil"] - LONG["COMMA_TARGET"]) <= 0.03 for p in ps2), ps2
    assert TP.comma_bad(ps2, LONG_TEXT, "long") == [] and TP.comma_bad(ps, LONG_TEXT, "long") != []


def test_short_sentence_same_in_both_profiles():
    w, t = short_case(0.33)
    ps = measured(w, SHORT_TEXT, t)
    a, acts_a = TP.fix_pauses(w, SR, ps, SHORT_TEXT, "std")
    b, acts_b = TP.fix_pauses(w, SR, ps, SHORT_TEXT, "long")
    assert acts_a == acts_b == {1: "trim"} and np.array_equal(a, b)
    assert measured(b, SHORT_TEXT, t)[0]["sil"] <= TP.COMMA_MAX


def test_default_is_std_bit_identical():
    for gap in (0.03, 0.12, 0.33):
        for text, case in ((LONG_TEXT, long_case), (SHORT_TEXT, short_case)):
            w, t = case(gap)
            ps = measured(w, text, t)
            base, acts0 = TP.fix_pauses(w, SR, ps)
            for kw in (dict(profile="std"), dict(text=text), dict(text=text, profile="std")):
                other, acts1 = TP.fix_pauses(w, SR, ps, **kw)
                assert acts0 == acts1 and base.tobytes() == other.tobytes(), (gap, text, kw)
            assert TP.out_of_range(ps) == any(not TP.COMMA_MIN <= p["sil"] <= TP.COMMA_MAX for p in ps)
            assert TP.comma_bad(ps) == [p["at"] for p in ps if p["sil"] < TP.COMMA_MIN]


def test_unknown_profile_rejected():
    try:
        TP.comma_params(LONG_TEXT, "xx")
    except ValueError:
        return
    raise AssertionError("unknown profile accepted")


def test_trim_key():
    key_text, sha, ver = "abc|qc6", "d" * 40, "t1"
    old = lambda final: hashlib.sha1((key_text.split("|", 1)[0] + sha + ver + ("|final" if final else "")).encode()).hexdigest()
    for final in (False, True):
        assert TK.trim_key(key_text, sha, ver, final) == old(final)
        assert TK.trim_key(key_text, sha, ver, final, "std") == old(final)
        k_long = TK.trim_key(key_text, sha, ver, final, "long")
        want = hashlib.sha1((key_text.split("|", 1)[0] + sha + ver + ("|final" if final else "") + "|comma=long").encode()).hexdigest()
        assert k_long == want and k_long != old(final)
