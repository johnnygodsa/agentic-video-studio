"""唸法清單(PLAN_TTS_FLOW T5)測試:假 cosy_terms / pron_rules 條目(直接改 tts_cosy_text 的模組變數,結束還原),不碰正式 json、不配音、不用顯示卡。
輸出寫 tmp\test_decide_list\(替身 paths.output_dir)。
python -X utf8 pipeline/tests/test_decide_list.py(或 -m pytest)"""
import contextlib
import copy
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import decide_list as D  # noqa: E402
import tts_cosy_text as CT  # noqa: E402

TMP = PIPE.parent / "tmp" / "test_decide_list"


@contextlib.contextmanager
def _patched(**kw):
    old = {k: getattr(CT, k) for k in kw}
    try:
        for k, v in kw.items():
            setattr(CT, k, v)
        yield
    finally:
        for k, v in old.items():
            setattr(CT, k, v)


def test_en_two_unverified_then_verified():
    texts = ["AAA 和 BBB 一起來", "只有 AAA", "沒有英文"]
    with _patched(TERMS={"AAA": "a a a", "BBB": "bee"}, DIRECT=[], TERMS_VERIFIED=set()):
        r = D.en_undecided(texts)
        assert sorted(r) == ["AAA", "BBB"] and r["AAA"]["lines"] == [1, 2] and r["BBB"]["say"] == "bee"
    with _patched(TERMS={"AAA": "a a a", "BBB": "bee"}, DIRECT=[], TERMS_VERIFIED={"AAA", "BBB"}):
        assert D.en_undecided(texts) == {}


def test_en_direct_included_and_unused_not_listed():
    with _patched(TERMS={"AAA": "a"}, DIRECT=["DDD"], TERMS_VERIFIED=set()):
        r = D.en_undecided(["DDD 出現"])
        assert list(r) == ["DDD"] and r["DDD"]["say"] is None   # AAA 本片沒用到 -> 不列


def test_pron_rule_not_in_verified_is_listed():
    raw = copy.deepcopy(CT.RULES_RAW)
    key = "著名→[zh][ù]"
    assert key in raw["_verified"]
    assert key not in D.pron_undecided(["他是著名的人"])     # 現有條目一律視為已驗
    raw["_verified"] = [k for k in raw["_verified"] if k != key]   # 模擬新增規則(未列入 _verified)
    with _patched(RULES_RAW=raw):
        r = D.pron_undecided(["他是著名的人"])
        assert key in r and r[key]["src"] == "pron_rules" and r[key]["lines"] == [1]
        raw["_verified"].append(key)
        assert key not in D.pron_undecided(["他是著名的人"])


def test_pron_cosy_pron_not_verified():
    with _patched(PRON={"究": "[j][iū]"}, PRON_VERIFIED=set()):
        assert "究" in D.pron_undecided(["研究者"])
    with _patched(PRON={"究": "[j][iū]"}, PRON_VERIFIED={"究"}):
        assert "究" not in D.pron_undecided(["研究者"])


def test_all_existing_rule_keys_verified():
    """規則鍵不在 _verified = 新增未聽審(2026-10-29 起 bioware_dei 穿著/伺候/黃柏/得接上等):不要求全在 _verified,
    但每個沒驗的鍵都必須被 pron_undecided 列出(機制不漏);已驗的鍵不列。
    例外:規則標 unverified(2026-11-01 起,例 暴露 同時在 _verified)一律列入優先聽。"""
    ver = set(CT.RULES_RAW["_verified"])
    for w, _ch, _offs, py, unv in CT.RULE_WORDS:
        if not py:
            continue
        key = f"{w}→{py}"
        listed = key in D.pron_undecided([w])
        assert listed == (unv or key not in ver), key


def test_verified_key_does_not_change_compiled_rules():
    """_verified 鍵不進讀音標注(也就不進快取鍵):拿掉它,編譯結果與標注輸出相同。"""
    raw = {k: v for k, v in CT.RULES_RAW.items() if k != "_verified"}
    chars, words, regs = CT._compile_rules(raw)
    assert (chars, words) == (CT.RULE_CHARS, CT.RULE_WORDS) and [r.pattern for r, *_ in regs] == [r.pattern for r, *_ in CT.RULE_REGS]
    assert "_verified" not in CT.RULE_CHARS and CT._rule_tokens(raw) == CT._rule_tokens(CT.RULES_RAW)


def test_polyphone_failure_does_not_abort():
    old_env, old_out = D.P.TTS_ENV, D.P.output_dir
    try:
        D.P.TTS_ENV = TMP / "no_such_python.exe"
        D.P.output_dir = lambda tag: TMP / tag
        with _patched(TERMS={"AAA": "a"}, DIRECT=[], TERMS_VERIFIED=set()):
            msg = D.run("t_poly", "vT", texts=["AAA"])
        body = (TMP / "t_poly" / "decide_vT.md").read_text(encoding="utf-8")
        assert "要你決定的唸法 1 筆" in msg and "未跑:找不到配音環境" in body and "AAA" in body
        items, note = D.polyphone("t_poly")
        assert items == [] and note.startswith("未跑:")
    finally:
        D.P.TTS_ENV, D.P.output_dir = old_env, old_out


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("OK", n)
