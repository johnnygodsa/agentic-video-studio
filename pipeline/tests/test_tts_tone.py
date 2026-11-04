"""聲調核對的單元測試(合成 F0 軌跡,不載模型、不讀 wav):python -X utf8 pipeline\\tests\\test_tts_tone.py
(函式名 test_* 也可用 pytest 跑;本機各 venv 沒裝 pytest,所以附 main)
1. 五類規則:理想化的平 / 升 / 降升 / 降 / 短而低輕聲,在說話者音域(100-200 Hz)上各歸對類。
2. 音域正規化:同樣的形狀整體移到另一個說話者音域(男聲 -> 女聲)判定不變。
3. 判不出:有聲幀太少 -> tone=None。
4. check_tones:say_t 字時段對位、不符 ok=False、判不出 ok=None、tone_of_pinyin。"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import tts_tone as T  # noqa: E402

LO, HI = 12 * np.log2(100 / 100.0), 12 * np.log2(200 / 100.0)   # 半音:0 ~ 12
RNG = dict(lo=LO, hi=HI, med=6.0)


def shape(norm, t_start, dur, rng=RNG):
    """norm = 正規化音高(0 = 音域下緣,1 = 上緣)隨時間的函式 -> (times, f0_hz) 的一段;前後補 0.05 秒無聲(nan)。"""
    t = np.arange(t_start, t_start + dur, T.HOP)
    st = rng["lo"] + np.array([norm((x - t_start) / dur) for x in t]) * (rng["hi"] - rng["lo"])
    return t, T.REF_HZ * 2 ** (st / 12)


SHAPES = {
    1: (lambda u: 0.80, 0.22),
    2: (lambda u: 0.30 + 0.60 * u, 0.22),
    3: (lambda u: 0.45 - 1.6 * u * (1 - u) * 1.2 + 0.0, 0.28),   # 兩端 0.45、中間凹到約 0.21... 見下方 dip 檢查
    4: (lambda u: 0.90 - 0.70 * u, 0.20),
    5: (lambda u: 0.20, 0.07),
}


def three(u):                        # 降升:0.45 -> 0.0 -> 0.5
    return 0.45 - 0.45 * np.sin(np.pi * u) + 0.05 * u


def track(tone, rng=RNG, t0=0.5):
    f, d = SHAPES[tone]
    f = three if tone == 3 else f
    return shape(f, t0, d, rng), t0, t0 + d


def test_five_classes():
    for tone in (1, 2, 3, 4, 5):
        (t, f0), a, b = track(tone)
        r = T.classify_track(t, f0, a, b, RNG)
        assert r["tone"] == tone, (tone, r)
        assert 0.0 <= r["conf"] <= 1.0


def test_range_normalisation():
    """女聲音域(200-400 Hz)同樣的形狀判定不變;絕對音高高一倍不會把一聲看成別的。"""
    rng_f = dict(lo=12.0, hi=24.0, med=18.0)
    for tone in (1, 2, 3, 4, 5):
        f, d = SHAPES[tone]
        f = three if tone == 3 else f
        t, f0 = shape(f, 0.5, d, rng_f)
        assert T.classify_track(t, f0, 0.5, 0.5 + d, rng_f)["tone"] == tone, tone


def test_unvoiced_gives_none():
    t = np.arange(0, 1, T.HOP)
    f0 = np.full_like(t, np.nan)
    f0[10:12] = 150.0                # 只有 2 個有聲幀 < MIN_VOICED
    r = T.classify_track(t, f0, 0.05, 0.3, RNG)
    assert r["tone"] is None and r["conf"] == 0.0
    assert T.classify_track(t, f0, 0.05, 0.3, None)["tone"] is None


def test_estimate_range():
    t, f0 = shape(lambda u: u, 0.0, 1.0)              # 100 -> 200 Hz 線性半音
    r = T.estimate_range(track=(t, f0))
    assert abs(r["lo"] - 1.2) < 0.3 and abs(r["hi"] - 10.8) < 0.3, r
    assert T.estimate_range(track=(t, np.full_like(t, np.nan))) is None


def test_tone_of_pinyin():
    assert T.tone_of_pinyin("zhu4") == 4 and T.tone_of_pinyin("zhe5") == 5
    assert T.tone_of_pinyin("zhe") is None and T.tone_of_pinyin("") is None


def test_check_tones():
    """三個字接在一條軌跡上:字0 = 四聲、字1 = 輕聲、字2 = 二聲;預期 [4, 4, 4] -> 只有字 0 ok。"""
    parts, say_t, t0 = [], [], 0.2
    for tone in (4, 5, 2):
        f, d = SHAPES[tone]
        t, f0 = shape(f, t0, d)
        parts.append((t, f0))
        say_t.append(t0)
        t0 += d + 0.14                     # 字間 0.14 秒無聲(大於兩側各擴 WIN_PAD)
    say_t.append(t0)
    t = np.arange(0, t0 + 0.2, T.HOP)
    f0 = np.full_like(t, np.nan)
    for tt, ff in parts:
        i = np.round(tt / T.HOP).astype(int)
        f0[i] = ff
    res = T.check_tones(None, 24000, say_t, [(0, 4), (1, 4), (2, 4), (9, 4)], RNG, track=(t, f0))
    assert [r["got"] for r in res[:3]] == [4, 5, 2], res
    assert [r["ok"] for r in res] == [True, False, False, None], res
    assert res[3]["got"] is None
    assert res[0]["expected"] == 4 and res[0]["pos"] == 0


def main():
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("通過", name)
            except AssertionError as e:
                fails += 1
                print("失敗", name, e)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
