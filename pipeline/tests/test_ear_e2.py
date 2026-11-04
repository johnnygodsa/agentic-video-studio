"""耳朵 E2(pipeline/senses/ear_e2_*)測試:合成正弦音,不載模型、不需顯示卡、不跑對齊器子行程。
涵蓋:qc.json say_t -> 每字區間、對齊項對回原文(含英數與找不到的字)、標籤排除多音字、F0 特徵抽取(升調斜率 > 0、降調 < 0、
無聲段不炸)、比對判定(期望調機率低才 flag、可給多個期望讀音)。
需要 librosa / pypinyin(tts_env_chattts);沒裝就略過。
python -X utf8 pipeline/tests/test_ear_e2.py(或 -m pytest)"""
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
sys.path.insert(0, str(PIPE / "senses"))
import ear_e2_align as AL  # noqa: E402

try:
    import librosa  # noqa: F401
    import numpy as np
    import pypinyin  # noqa: F401
    import ear_e2_tone as T
    import ear_e2 as E
    HAVE = True
except ImportError:
    HAVE = False


def test_from_qc():
    qc = {"text": "你好,世界", "say_t": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]}
    text, spans = AL.from_qc(qc)
    assert text == "你好,世界" and spans[1] == ("好", 0.2, 0.4) and spans[4] == ("界", 0.8, 1.0)
    assert AL.from_qc({"text": "你好", "say_t": [0, 1]}) == (None, None)


def test_map_items():
    sp = AL.map_items("買EA的遊戲", [["買", 0.0, 0.2], ["EA", 0.25, 0.5], ["的遊", 0.5, 0.9]])
    assert sp[0] == ("買", 0.0, 0.25)            # 字迄接到下一個字起(同 say_t)
    assert sp[1][1] == 0.25 and sp[2][1] is None  # 英數整詞放在第一個位置
    assert abs(sp[3][1] - 0.5) < 1e-9 and abs(sp[4][1] - 0.7) < 1e-9
    assert sp[5] == ("戲", None, None)


def _tone_wav(segs, sr=16000):
    """[(起始 Hz, 結束 Hz, 秒)] -> 有諧波的滑音(None = 靜音)。"""
    out = []
    for f0, f1, d in segs:
        n = int(sr * d)
        if f0 is None:
            out.append(np.zeros(n, np.float32))
            continue
        f = np.linspace(f0, f1, n)
        ph = 2 * np.pi * np.cumsum(f) / sr
        out.append((0.5 * np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)).astype(np.float32))
    return np.concatenate(out)


def test_features_slope():
    if not HAVE:
        print("略過:沒有 librosa/pypinyin")
        return
    x = _tone_wav([(100, 160, 0.4), (160, 90, 0.4), (None, None, 0.3), (120, 120, 0.4)])
    spans = [("升", 0.0, 0.4), ("降", 0.4, 0.8), (",", 0.8, 1.1), ("平", 1.1, 1.5), ("無", None, None)]
    idx, X = T.features(x, spans)
    assert idx == [0, 1, 3] and X.shape == (3, len(T.feature_names()))
    slope = T.feature_names().index("slope")
    assert X[0, slope] > 0 > X[1, slope] and abs(X[2, slope]) < abs(X[0, slope])
    assert X[1, T.feature_names().index("brk_next")] == 1.0
    idx2, X2 = T.features(np.zeros(16000, np.float32), [("靜", 0.1, 0.5)])   # 全無聲:F0 欄是 nan,不丟例外
    assert idx2 == [0] and np.isnan(X2[0, 0])


def test_labels_exclude_poly():
    if not HAVE:
        return
    lab = T.labels("我們去銀行,A")
    for ch, t in zip("我們去銀", lab):
        if ch not in T.NEUTRAL:
            assert t is None if T.is_poly(ch) else t in T.TONES
    assert lab[1] == "5"                                          # 輕聲虛詞例外收標籤
    assert lab[4] is None and lab[5] is None and lab[6] is None   # 行(多音字)、標點、英文不進訓練
    assert T.tone_of("de") == "5" and T.tone_of("zhi2") == "2"


def test_compare():
    if not HAVE:
        return
    rows = [{"i": 3, "ch": "著", "tone": "4", "conf": 0.8, "probs": {"1": 0.05, "2": 0.05, "3": 0.0, "4": 0.8, "5": 0.1}}]
    c = E.compare(rows, {"3": "zhe5"})[0]
    assert c["flag"] and c["p_expect"] == 0.1
    assert not E.compare(rows, {"3": ["zhe5", "zhu4"]})[0]["flag"]
    assert E.compare(rows, {"7": "le5"})[0]["tone"] is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
