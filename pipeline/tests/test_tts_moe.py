"""tts_moe(教育部讀音精簡檔)測試:小 fixture,不依賴下載檔與 pipeline/moe 內容。
python -X utf8 pipeline/tests/test_tts_moe.py(或 -m pytest)
"""
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))

import tts_moe as M  # noqa: E402

ENTRIES = [
    {"title": "血", "heteronyms": [
        {"bopomofo": "ㄒㄧㄝˇ", "pinyin": "xiě", "definitions": [{"def": "體液。"}]},
        {"bopomofo": "ㄒㄩㄝˋ", "pinyin": "xuè", "definitions": [{"def": "(一)之讀音。"}]}]},
    {"title": "關", "heteronyms": [{"bopomofo": "ㄍㄨㄢ", "pinyin": "guān"}]},
    {"title": "卡", "heteronyms": [{"bopomofo": "ㄎㄚˇ", "pinyin": "kǎ"}, {"bopomofo": "ㄑㄧㄚˇ", "pinyin": "qiǎ"}]},
    {"title": "關卡", "heteronyms": [{"bopomofo": "ㄍㄨㄢ ㄎㄚˇ", "pinyin": "guān kǎ"}]},
    {"title": "卡子", "heteronyms": [{"bopomofo": "ㄑㄧㄚˇ ˙ㄗ", "pinyin": "qiǎ zi"}]},
    {"title": "熱血", "heteronyms": [{"bopomofo": "ㄖㄜˋ ㄒㄩㄝˋ", "pinyin": "rè xuè"}]},
    {"title": "{[8e40]}字", "heteronyms": [{"bopomofo": "ㄗˋ"}]},
    {"title": "一二三四五", "heteronyms": [{"bopomofo": "ㄧ ㄦˋ ㄙㄢ ㄙˋ ㄨˇ"}]},
]


def _data():
    return M.compact(ENTRIES)


def test_compact():
    pron, words, wp = _data()
    assert [r["bopomofo"] for r in pron["血"]] == ["ㄒㄧㄝˇ", "ㄒㄩㄝˋ"]
    assert pron["血"][1]["note"] == "(一)之讀音"
    assert pron["血"][1]["words"] == ["熱血"]
    assert pron["卡"][0]["words"] == ["關卡"] and pron["卡"][1]["words"] == ["卡子"]
    assert pron["關"][0]["words"] == []          # 單音字不收例詞
    assert words == ["關卡", "卡子", "熱血"] or set(words) == {"關卡", "卡子", "熱血"}   # 5 字詞與非純中文標題不收
    assert wp["關卡"] == "ㄍㄨㄢ ㄎㄚˇ" and "{[8e40]}字" not in wp


def test_lookup():
    pron, words, wp = _data()
    out = "\n".join(M.lookup("關卡", pron, set(words), wp))
    assert "辭典詞條" in out and "卡 在「關卡」讀 ㄎㄚˇ kǎ" in out
    out = "\n".join(M.lookup("血", pron, set(words), wp))
    assert "血(多音)" in out and "xuè" in out


def test_polyphones():
    pron, _, _ = _data()
    out = M.polyphones(pron, top=5)
    assert out[0].startswith("多讀音字 2 ")
    assert any(l.strip().startswith("血:") for l in out)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
