"""make_version.pick_bgm 測試(只測選曲,不渲染不配音)。python -X utf8 pipeline/tests/test_make_version_bgm.py 或 pytest。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import make_version as MV  # noqa: E402
import paths as P  # noqa: E402


def test_kuang():
    assert MV.pick_bgm(None, "ChannelA", "x") == ("ai_C2_light.wav", "依頻道 ChannelA")
    assert MV.pick_bgm(None, None, "x", "ChannelA")[0] == "ai_C2_light.wav"  # spec.json 全名


def test_lang():
    assert MV.pick_bgm(None, "ChannelB", "x") == ("ai_D2_reflective.wav", "依頻道 ChannelB")
    assert MV.pick_bgm(None, None, "x", "ChannelB")[0] == "ai_D2_reflective.wav"


def test_third_channel_rotates_stably():
    for ch in ("ChannelC", "ChannelC"):
        got = {MV.pick_bgm(None, ch, f"tag{i}")[0] for i in range(40)}
        assert got == set(MV.BGM_BY_CHANNEL["科普"])
    assert MV.pick_bgm(None, "ChannelC", "abc") == MV.pick_bgm(None, "ChannelC", "abc")  # 同 tag 穩定


def test_user_choice_wins():
    assert MV.pick_bgm("Foo.mp3", "ChannelA", "x") == ("Foo.mp3", "使用者指定")


def test_channel_beats_spec_and_fallback():
    assert MV.pick_bgm(None, "ChannelB", "x", "ChannelA")[0] == "ai_D2_reflective.wav"
    assert MV.pick_bgm(None, None, "x", None) == (MV.DEFAULT_BGM, "舊預設")
    assert MV.pick_bgm(None, None, "x", "不明頻道") == (MV.DEFAULT_BGM, "舊預設")


def test_files_exist():
    """副本專案(KC)只帶自己頻道的曲子:不存在的頻道曲略過,但至少要有一首在。"""
    names = [n for ns in MV.BGM_BY_CHANNEL.values() for n in ns]
    have = [n for n in names if (P.BGM / n).exists()]
    if (P.ROOT / "chattts_speaker").is_dir():  # 頻道主本機:全部都要在
        assert have == names, sorted(set(names) - set(have))
    elif not have:
        print("略過 test_files_exist:bgm 資料夾沒有任何頻道曲")


def test_spec_channel_of_missing():
    assert MV.spec_channel_of("__no_such_tag__") is None


def test_audio_consts_single_source():
    """BGM 常數/算法單一來源:make_version 與 build 用的就是 audio_consts 的同一份;make_film 走同一函式。"""
    import audio_consts as AC
    import build as B
    assert MV.BGM_BY_CHANNEL is AC.BGM_BY_CHANNEL and MV.DEFAULT_BGM == AC.DEFAULT_BGM
    assert B.bgm_gain_auto is AC.bgm_gain_auto and B.BGM_BELOW_VOICE_DB == AC.BGM_BELOW_VOICE_DB == 5.7
    assert AC.bgm_for_channel("ChannelA", "x") == "ai_C2_light.wav" and AC.bgm_for_channel("不明", "x") is None
    win = (-30.0, -25.0, -20.0, -20.5)
    g, which = AC.bgm_gain_db(-18.0, win, 1.0)
    assert which == "p90" and abs(g - (-18.0 - 5.7 + 20.0 + 1.0)) < 1e-9
    lin, g2, w2 = AC.bgm_gain_auto(-18.0, win, 1.0)
    assert g2 == g and w2 == which and abs(lin - 10 ** (g / 20)) < 1e-12
    _, wk = AC.bgm_gain_db(-18.0, (-30.0, -25.0, -20.0, -10.0))   # 最大窗過大 -> 峰值條款
    assert wk == "peak"
    assert AC.sidecar_duck({"bgm_db": 1}) and not AC.sidecar_duck({"bgm_db": 1, "duck": False}) and not AC.sidecar_duck({})
    assert AC.sidecar_db({"bgm_db": "2.5"}) == 2.5 and AC.sidecar_db({}) == 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
    print(f"OK {len(fns)} tests")
