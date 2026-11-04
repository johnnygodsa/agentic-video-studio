"""E1 全標注(tts_cosy_text annotate_mode;docs/tts.md §4.7):table 模式與改前逐位元相同、all 模式 token 全在 tokenizer。"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pron_memory as PM  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import tts_script as TSC  # noqa: E402

FIX = HERE / "fixtures" / "ear_e1" / "table_sha.json"   # 改前用 tts_cosy_text 產生(記憶表停用)
TABLES = ("cosy_pron.json", "pron_rules.json", "cosy_terms.json", "say_terms.json")
FROZEN = ("bioware_dei", "ea_me5")


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


@pytest.fixture
def clean(monkeypatch, tmp_path):
    """記憶表停用(基準產生時同樣停用)、不吃外部 COSY_ANNOTATE。"""
    monkeypatch.setattr(PM, "MEM_FILE", tmp_path / "no_memory.json")
    monkeypatch.delenv(CT.ANNOTATE_ENV, raising=False)


def _says(tag):
    return [say for _ln, say in TSC.script_lines(tag)]


def test_table_mode_bit_identical(clean):
    fx = json.loads(FIX.read_text(encoding="utf-8"))
    if _sha("".join((CT.HERE / f).read_text(encoding="utf-8") for f in TABLES)) != fx["tables"]:
        pytest.skip("讀音表已改,改前基準不再適用")
    n = 0
    for tag in FROZEN:
        want = fx["tags"][tag]
        for say in _says(tag):
            if _sha(say) not in want:   # 稿子之後改過的句子不比
                continue
            for mode in (None, "table"):
                t, hits = CT.pron_text(say, mode)
                assert _sha(t + "\x00" + "|".join(hits)) == want[_sha(say)], (tag, mode, say)
            n += 1
    assert n >= 100


def test_all_mode_tokens_in_tokenizer(clean, monkeypatch):
    pytest.importorskip("pypinyin")
    if not CT.TOKENIZER_PY.exists():
        pytest.skip("沒有 CosyVoice tokenizer 檔")
    monkeypatch.setattr(CT, "_g2pw_row", lambda _t: None)   # 測試不載 g2pW(token 由 py_tokens 同一道驗證)
    have, added = CT._tokenizer_tokens(), 0
    for tag in FROZEN:
        for say in _says(tag):
            t, hits = CT.pron_text(say, "all")
            bad = set(CT.TOKEN_RE.findall(t)) - have
            assert not bad, (tag, say, bad)
            added += sum(h.startswith(CT.E1_KEY) for h in hits)
            for m in CT.poly_marks(CT.pron_source(say), "all"):
                assert m[3] in {"table", "rule", "memory", "zhe", "g2pw", "pypinyin", "none"}
    assert added > 0


def test_env_switch(clean, monkeypatch):
    pytest.importorskip("pypinyin")
    monkeypatch.setattr(CT, "_g2pw_row", lambda _t: None)
    say = "這個行業的數值很重要"
    table = CT.pron_text(say)
    monkeypatch.setenv(CT.ANNOTATE_ENV, "all")
    assert CT.pron_text(say) == CT.pron_text(say, "all") != table
    monkeypatch.setenv(CT.ANNOTATE_ENV, "bogus")
    assert CT.pron_text(say) == table


def test_polyphone_set(monkeypatch):
    monkeypatch.delenv(CT.POLYSET_ENV, raising=False)
    rules, risk, every = (CT.polyphone_chars(n) for n in CT.POLYSETS)
    assert CT.polyphone_chars() == risk                      # 預設 risk
    assert rules and set(CT.RULE_CHARS) - CT.SANDHI_SKIP - {"著"} == rules
    assert rules <= risk and risk and risk < every            # risk 非空且 ⊂ all
    assert not every & (CT.SANDHI_SKIP | {"著"})


def test_risky_drops_variant_and_neutral():
    assert not CT._risky([dict(pinyin="tā"), dict(pinyin="tuō", note="(一)之又音")])
    assert not CT._risky([dict(pinyin="le"), dict(pinyin="lè")])   # 只差輕聲 -> 不算
    assert not CT._risky([dict(pinyin="ma"), dict(pinyin="mā")])
    assert CT._risky([dict(pinyin="háng"), dict(pinyin="xíng")])


@pytest.mark.parametrize("py3,want", [("zhang3", "[zh][ǎng]"), ("yi4", "[y][ì]"), ("wu4", "[w][ù]"), ("yue4", "[y][uè]"),
                                      ("xue2", "[x][ué]"), ("lv4", "[l][ǜ]"), ("lve4", "[l][vè]"), ("de5", "[d][e]"),
                                      ("jiu4", "[j][iù]"), ("gui4", "[g][uì]"), ("er2", "[ér]"), ("q5", None)])
def test_py_tokens(py3, want):
    if not CT.TOKENIZER_PY.exists():
        pytest.skip("沒有 CosyVoice tokenizer 檔")
    assert CT.py_tokens(py3) == want
