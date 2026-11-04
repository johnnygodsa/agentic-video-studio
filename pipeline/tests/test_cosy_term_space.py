"""cosy_terms 換成中文寫法後,英文兩側的空格在 CJK 旁要去掉;「藝電」帶拼音標注(不需顯示卡;terms 用替身表)。
python -X utf8 pipeline/tests/test_cosy_term_space.py(或 -m pytest)"""
import sys
from contextlib import contextmanager
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import tts_cosy_text as CT  # noqa: E402

TERMS = {"EA": "藝電", "Avellone": "阿維隆", "Roblox": "Roblox", "Bio Ware": "生物軟體"}


@contextmanager
def terms(t=TERMS):
    keep = CT.TERMS
    CT.TERMS = dict(t)
    try:
        yield
    finally:
        CT.TERMS = keep


def test_space_removed_beside_cjk():
    with terms():
        assert CT.apply_terms("是 Avellone 說") == "是阿維隆說"
        assert CT.apply_terms("Avellone 說,然後 Avellone。") == "阿維隆說,然後阿維隆。"
        assert CT.apply_terms("他 說 Avellone 算過") == "他 說阿維隆算過"


def test_other_spaces_kept():
    with terms():
        assert CT.apply_terms("play Roblox with EA games") == "play Roblox with 藝電 games".replace("藝電", CT.TERM_ANNOT["藝電"])
        assert CT.apply_terms("is EA good") == "is " + CT.TERM_ANNOT["藝電"] + " good"
        assert CT.apply_terms("我 Roblox 你") == "我 Roblox 你"   # 值不是 CJK:空格不動
        assert CT.apply_terms("EA 的 Avellone and") == CT.TERM_ANNOT["藝電"] + "的阿維隆 and"


def test_ea_annotated():
    with terms():
        t = CT.apply_terms("是 EA 想學 EA")
        assert t == "是" + CT.TERM_ANNOT["藝電"] + "想學" + CT.TERM_ANNOT["藝電"]
        assert "藝電" not in t
        assert CT.apply_pron(t)[0].count("[y][ì][d][iàn]") == 2   # pron 不重複標注
        assert CT.term_hits("是 EA 想學") == {"EA": "藝電"}   # 快取紀錄的寫法仍是 terms 值


def test_adjacent_terms_and_cjk_punct():
    with terms():
        assert CT.apply_terms("Avellone EA") == "阿維隆" + CT.TERM_ANNOT["藝電"]   # 兩個連續替換間的空格也去掉
        assert CT.apply_terms("EA,Avellone") == CT.TERM_ANNOT["藝電"] + ",阿維隆"
        assert CT.apply_terms("你好, EA") == "你好, " + CT.TERM_ANNOT["藝電"]   # 半形逗號不算中文標點


def test_pron_tokens_exist():
    have = CT._tokenizer_tokens()
    assert set(CT.TOKEN_RE.findall(CT.TERM_ANNOT["藝電"])) <= have


if __name__ == "__main__":
    tests = [(n, f) for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for n, f in tests:
        f()
        print("ok", n)
    print(f"{len(tests)} passed")
