"""tts_pron 書名號冒號測試:python -X utf8 -m pytest pipeline\tests\test_tts_pron.py(不需顯示卡)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tts_pron  # noqa: E402


def test_title_colon_dropped():
    out = tts_pron.apply("《惡靈古堡:安魂曲》有一半")
    assert ":" not in out and "：" not in out and "惡靈古堡安魂曲" in out, out
    assert tts_pron.apply("《異形：孤立》更狠。") == "《異形孤立》更狠。"


def test_colon_outside_title_untouched():
    assert tts_pron.apply("總監說:不行") == "總監說:不行"
    assert tts_pron.apply("總監說：《異形》不行") == "總監說：《異形》不行"


def test_no_effect_on_sentences_without_title_colon():
    for t in ("請了公司史上第一位多元長。", "《異形》更狠。", "他看著我,然後走了。"):
        assert tts_pron.key_text(t) == tts_pron._fixed_same_len(t)


def test_changes_and_positions_ignore_title_colon():
    t = "《惡靈古堡:安魂曲》的多元長"
    assert tts_pron.changes(t) == ["多元長→掌"], tts_pron.changes(t)
    assert tts_pron.rule_positions(t) == {t.index("長"): "掌"}
    assert tts_pron.changes("《惡靈古堡:安魂曲》有一半") == []
