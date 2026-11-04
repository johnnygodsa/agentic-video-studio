"""「著」兩個回歸(2026-10-29):
1) 「編譯著色器」的「譯著」不能命中詞「譯著」(zhù),要走 著色 -> [zh][uó];「譯著作品」仍是 zhù。
2) 品管:always 字「著」辨識寫回同一字(着/著)不算讀錯;真的讀錯(看得到 -> 看不到)仍算。
需要 pypinyin / opencc(跑 TTS 的環境,例 tts_env_chattts);沒裝就略過。
python -X utf8 pipeline/tests/test_zhe_regress.py"""
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import tts_cosy_text as CT  # noqa: E402

try:
    import pypinyin  # noqa: F401
    HAVE_PY = True
except ImportError:
    HAVE_PY = False


def _engine(text):
    return CT.apply_pron(text)[0]   # 繁體原文上的拼音標注(engine_text 再轉簡體:編譯 -> 编译)


def test_yizhu_se_not_zhu_word():
    assert "編譯[zh][uó]色器" in _engine("遙控器都在編譯著色器")
    assert "[zh][ù]" not in _engine("遙控器都在編譯著色器")


def test_yizhu_zuopin_still_zhu():
    assert "譯[zh][ù]作品" in _engine("譯著作品")
    assert "[zh][ù]" in _engine("這本譯著很好看")


def test_fix_zhe_and_exception_words_consistent():
    import tts_pron
    assert CT.fix_zhe("編譯著色器")[0] == "編譯着色器"
    assert CT.fix_zhe("這本譯著")[0] == "這本譯著"
    assert tts_pron._mark_and_fix("譯著")[1] == {}
    assert tts_pron._mark_and_fix("譯著色")[1] == {}   # 著色 本來就在例外詞


def test_qc_same_char_not_bad():
    if not HAVE_PY:
        return
    import tts_chattts as TC
    ref = "可是 Steam 評論區排第一的那篇,吐槽的不是頭目,是一條著色器進度條。"
    hyp = "可是，Steam评论区排第一的那篇吐槽的，不是头目，是一条着色器进度条。"
    assert TC.asr_judge(ref, hyp, rules=True)["pron_bad"] == 0
    assert TC.asr_judge(ref, hyp.replace("着", "著"), rules=True)["pron_bad"] == 0


def test_qc_real_misread_still_bad():
    if not HAVE_PY:
        return
    import tts_chattts as TC
    assert TC.asr_judge("我看得到血條", "我看不到血条", rules=True)["pron_bad"] >= 1


if __name__ == "__main__":
    fails = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            try:
                v()
                print("ok", k)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print("FAIL", k, repr(e))
    sys.exit(1 if fails else 0)
