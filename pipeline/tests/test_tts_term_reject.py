"""英文詞唸錯回查 tts_cosy_text.asr_rejects(cosy_terms `_asr_reject`;純函式、不需顯示卡):
python -X utf8 pipeline\\tests\\test_tts_term_reject.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tts_cosy_text as CT  # noqa: E402

FAILS = []
TABLE = {"_doc": "略過", "BioWare": ["瓦", "哇", "奥瓦", "欧瓦"]}
TEXT = "做出《質量效應》的 BioWare 宣布關門"


def expect(name, cond, detail=""):
    print(("通過" if cond else "失敗"), name, detail)
    if not cond:
        FAILS.append(name)


def main():
    r = CT.asr_rejects(TEXT, {"asr": "做出质量效应的百奥瓦宣布关门"}, TABLE)
    expect("主辨識命中(瓦、奥瓦)", {x["hit"] for x in r} == {"瓦", "奥瓦"} and {x["src"] for x in r} == {"asr"}, str(r))
    r = CT.asr_rejects(TEXT, {"asr": "做出质量效应的BioWare宣布关门", "asr2": "的白欧瓦宣布"}, TABLE)
    expect("只有副辨識命中", r and all(x["src"] == "asr2" and x["term"] == "BioWare" for x in r), str(r))
    expect("辨識正確不命中", CT.asr_rejects(TEXT, {"asr": "的Bioware宣布关门", "asr2": None}, TABLE) == [])
    expect("句子沒有原文詞不查", CT.asr_rejects("瓦解了", {"asr": "瓦解了"}, TABLE) == [])
    expect("原文本身有的字不算", CT.asr_rejects("BioWare 瓦解", {"asr": "BioWare瓦解"}, TABLE) == [])
    expect("原文有一個、辨識多一個才算", len(CT.asr_rejects("BioWare 瓦解", {"asr": "百奥瓦瓦解"}, TABLE)) >= 1)
    expect("底線鍵略過", CT.asr_rejects("_doc 略過", {"asr": "略過"}, TABLE) == [])
    expect("載入的表不含底線鍵", not any(k.startswith("_") for k in CT.ASR_REJECT))
    print("全部通過" if not FAILS else f"失敗 {len(FAILS)}: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
