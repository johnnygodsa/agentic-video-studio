"""spec_check 譯名表(PLAN_TTS_FLOW R5)單元測試。python -X utf8 pipeline/tests/test_spec_names.py"""
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import spec_check as S  # noqa: E402

NAMES = {"Phantom Liberty": {"tw": "自由幻局", "avoid": ["往日之影"]}, "Night City": "夜之城"}


def errs(spec, texts, says=None):
    lines = []
    for i, t in enumerate(texts):
        ln = {"text": t}
        if says and says[i]:
            ln["say"] = says[i]
        lines.append(ln)
    return S.check(spec, lines)


def main():
    # avoid 他譯 -> 1 個錯誤
    assert len(errs({"tw_names": NAMES}, ["這次資料片叫往日之影,玩家很期待"])) == 1
    # 用譯名 -> 0
    assert errs({"tw_names": NAMES}, ["這次資料片叫自由幻局,玩家很期待"]) == []
    # 他譯只出現在 @say -> 仍擋
    assert len(errs({"tw_names": NAMES}, ["資料片來了"], ["資料片叫往日之影"])) == 1
    # 字幕原文、say 有譯名 -> 通過;字幕原文且 say 沒譯名 -> 錯誤
    assert errs({"tw_names": NAMES}, ["Phantom Liberty 來了"], ["自由幻局來了"]) == []
    assert len(errs({"tw_names": NAMES}, ["Phantom Liberty 來了"])) == 1
    # 純字串簡寫 + ASCII 邊界/大小寫
    assert len(errs({"tw_names": NAMES}, ["night city 很大"])) == 1
    assert errs({"tw_names": NAMES}, ["Night Cityscape 與夜之城無關"]) == []
    # 譯名含他譯字樣不誤判
    assert errs({"tw_names": {"X": {"tw": "往日之影傳說", "avoid": ["往日之影"]}}}, ["往日之影傳說開賣"]) == []
    # 無 names:行為不變;list names 仍是真人姓名(舊行為:含姓名句需 fact 涵蓋)
    assert errs({}, ["往日之影 Phantom Liberty"]) == []
    assert errs({"names": ["林克"], "tw_names": NAMES}, ["自由幻局"]) == []
    assert len(errs({"names": ["林克"]}, ["林克出場了"])) == 1
    assert errs({"names": ["林克"], "facts": [{"id": "f1", "lines": [1], "status": "confirmed"}]}, ["林克出場了"]) == []
    print("test_spec_names OK")


if __name__ == "__main__":
    main()
