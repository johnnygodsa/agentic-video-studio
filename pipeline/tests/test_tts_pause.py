"""句中停頓與對齊的單元測試(不需顯示卡):python -X utf8 pipeline\\tests\\test_tts_pause.py
1. 對齊:辨識字詞時間對回已知文本(同字、漏字、阿拉伯數字)、@say 替換後的字元位置對應。
2. 停頓後處理:合成的正弦波 + 靜音片段,量測 -> 插入/剪除 -> 再量測。
3. build.py 的字幕分段時間:有 say_t 用實測時間,沒有就用送配音字數等比例。"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import tts_pause as TP  # noqa: E402

SR = 24000
FAILS = []


def expect(name, cond, detail=""):
    print(("通過" if cond else "失敗"), name, detail)
    if not cond:
        FAILS.append(name)


def tone(sec, amp=0.5, f=180.0):
    return (amp * np.sin(2 * np.pi * f * np.arange(int(sec * SR)) / SR)).astype(np.float32)


def sil(sec):
    return np.zeros(int(sec * SR), dtype=np.float32)


def test_align():
    ref = [u[0] for u in TP.units("就这样，没有下文。")]
    hyp = TP.hyp_units([("就这样", 0.0, 0.6), ("没有", 0.75, 1.05), ("下文", 1.05, 1.5)])
    t, ok = TP.align(ref, hyp, 1.6)
    expect("對齊:全部對到", all(ok) and len(t) == 7)
    expect("對齊:逗號前後的字", abs(t[2][1] - 0.6) < 1e-6 and abs(t[3][0] - 0.75) < 1e-6, f"{t[2]} {t[3]}")
    # 漏字 + 數字:原文「二零二四年那份」辨識成「2024年那」,「份」對不到 -> 夾在前後之間
    ref = [u[0] for u in TP.units("二零二四年那份，讲")]
    hyp = TP.hyp_units([("2024年", 0.0, 1.0), ("那", 1.0, 1.2), ("讲", 1.6, 1.8)])
    t, ok = TP.align(ref, hyp, 2.0)
    expect("對齊:阿拉伯數字對回中文數字", ok[:5] == [True] * 5 and abs(t[1][0] - 0.2) < 1e-6, str(ok))
    expect("對齊:漏字夾在前後之間", not ok[6] and abs(t[6][0] - 1.2) < 1e-6 and abs(t[6][1] - 1.6) < 1e-6, str(t[6]))
    expect("對齊:時間不倒退", all(t[k][0] <= t[k + 1][0] for k in range(len(t) - 1)))
    pos = TP.char_map("EA 的年報", "美商藝電 的年報")
    expect("字元位置:@say 替換後一對一接回", pos[2:] == [4, 5, 6, 7, 8], str(pos))
    cs = TP.char_starts("就这样，没有", [[0, .2], [.2, .4], [.4, .6], [.75, .9], [.9, 1.05]], 1.2,
                        [dict(i=2, sil=0.1, t0=0.62, t1=0.72)])
    expect("每字時間:標點 = 靜音開始、下一字 = 靜音結束", abs(cs[3] - 0.62) < 1e-6 and abs(cs[4] - 0.72) < 1e-6, str(cs))


def pauses_of(w, text, bounds):
    return TP.measure_pauses(w, SR, text, bounds)


def test_pause():
    text = "啊啊，啊啊。"
    # 逗號在第 2、3 個字之間;各字時間照合成的片段給(模擬對齊結果,故意偏 0.05 秒)
    def case(gap_w, gap_sec):
        w = np.concatenate([tone(0.6), gap_w, tone(0.6), sil(0.2)])
        b = 0.6 + gap_sec / 2 + 0.05
        return w, [[0, .3], [.3, b], [b, b + .3], [b + .3, b + .6]]

    w, t = case(sil(0.03), 0.03)
    p = pauses_of(w, text, t)
    expect("量測:短停頓", len(p) == 1 and abs(p[0]["sil"] - 0.03) <= 0.011, str(p))
    w2, acts = TP.fix_pauses(w, SR, p)
    p2 = pauses_of(w2, text, t)
    expect("插入靜音:補到目標", acts == {1: "insert"} and TP.COMMA_MIN <= p2[0]["sil"] <= TP.COMMA_MAX
           and abs(p2[0]["sil"] - TP.COMMA_TARGET) <= 0.03, f"{p[0]['sil']} -> {p2[0]['sil']}")
    expect("插入靜音:長度只多出補的部分", abs((len(w2) - len(w)) / SR - (TP.COMMA_TARGET - p[0]["sil"])) < 0.002)

    w, t = case(sil(0.40), 0.40)
    p = pauses_of(w, text, t)
    w2, acts = TP.fix_pauses(w, SR, p)
    p2 = pauses_of(w2, text, t)
    expect("剪除:太長剪到上限", acts == {1: "trim"} and abs(p[0]["sil"] - 0.40) <= 0.011
           and abs(p2[0]["sil"] - TP.COMMA_MAX) <= 0.011, f"{p[0]['sil']} -> {p2[0]['sil']}")

    w, t = case(sil(0.15), 0.15)
    p = pauses_of(w, text, t)
    w2, acts = TP.fix_pauses(w, SR, p)
    expect("範圍內:不動", acts == {} and len(w2) == len(w) and TP.COMMA_MIN <= p[0]["sil"] <= TP.COMMA_MAX, str(p))

    w, t = case(tone(0.04, amp=0.5 * 10 ** (-20 / 20)), 0.04)   # 沒有靜音,只有 20 dB 的能量低谷
    p = pauses_of(w, text, t)
    w2, acts = TP.fix_pauses(w, SR, p)
    p2 = pauses_of(w2, text, t)
    expect("能量低谷:可插入", p[0]["sil"] == 0 and TP.fixable(p[0]) and acts == {1: "insert"}
           and TP.COMMA_MIN <= p2[0]["sil"] <= TP.COMMA_MAX, f"dip={p[0]['dip']} -> {p2[0]['sil']}")

    w, t = case(tone(0.04, amp=0.5 * 10 ** (-5 / 20)), 0.04)    # 兩字連音:沒有低谷
    p = pauses_of(w, text, t)
    w2, acts = TP.fix_pauses(w, SR, p)
    expect("連音:不補(comma_bad)", p[0]["sil"] == 0 and not TP.fixable(p[0]) and acts == {} and len(w2) == len(w),
           f"dip={p[0]['dip']}")
    expect("逗號連音:仍列 comma_bad、仍算超出範圍", not p[0]["soft"] and TP.comma_bad(p) == ["啊|啊"] and TP.out_of_range(p))

    # 頓號(軟停頓):列舉不停是自然唸法
    soft_text = "啊啊、啊啊。"
    p = TP.measure_pauses(w, SR, soft_text, t)
    w2, acts = TP.fix_pauses(w, SR, p)
    expect("頓號連音:soft、不列 comma_bad、不插、不算超出範圍", p[0]["soft"] and TP.soft_skip(p[0]) and TP.comma_bad(p) == []
           and not TP.out_of_range(p) and acts == {} and len(w2) == len(w), str(p))
    p = TP.measure_pauses(w, SR, text, t, soft_at={2})   # prep 已換成逗號:由 soft_at 標回頓號位置
    expect("soft_at 標回頓號", p[0]["soft"] and TP.comma_bad(p) == [], str(p))
    w, t = case(tone(0.04, amp=0.5 * 10 ** (-20 / 20)), 0.04)
    p = TP.measure_pauses(w, SR, soft_text, t)
    w2, acts = TP.fix_pauses(w, SR, p)
    p2 = TP.measure_pauses(w2, SR, soft_text, t)
    expect("頓號有低谷(fixable):照插到 COMMA_TARGET", p[0]["soft"] and p[0]["sil"] == 0 and TP.out_of_range(p)
           and acts == {1: "insert"} and abs(p2[0]["sil"] - TP.COMMA_TARGET) <= 0.03, f"{p[0]} -> {p2[0]['sil']}")


def test_build():
    import build as B
    text, say = "EA 的年報、微軟的報告,同一年都出了類似的事。", "美商藝電 的年報、微軟的報告,同一年都出了類似的事。"
    ph = B.split_phrases(text)
    spans = B._phrase_spans(text, ph)
    expect("字幕段位置:對得回原文", spans is not None and len(spans) == len(ph), str(spans))
    say_t = [round(0.2 * k, 3) for k in range(len(say) + 1)]   # 每個字元 0.2 秒
    out = B._phrase_times(text, say, say_t, 10.0, 10.0 + say_t[-1], 99.0)
    pos = TP.char_map(text, say)
    want = [10.0] + [10.0 + say_t[pos[a]] - B.SUB_LEAD for a, _ in spans[1:]]
    expect("字幕時間:各段起點 = 該段第一個字的實測時間", [round(x[1], 3) for x in out] == [round(x, 3) for x in want]
           and out[-1][2] == 99.0 and all(out[k][2] == out[k + 1][1] for k in range(len(out) - 1)), str(out))
    old = B._phrase_times(text, say, None, 10.0, 10.0 + say_t[-1], 99.0, legacy=True)
    new = B._phrase_times(text, say, None, 10.0, 10.0 + say_t[-1], 99.0)
    expect("字幕時間:沒有實測時用送配音字數等比例(第一段 EA 唸四個字,比顯示字數長)",
           len(new) == len(old) and (len(new) < 2 or new[1][1] > old[1][1]), f"{old[1][1] if len(old) > 1 else ''} -> "
           f"{new[1][1] if len(new) > 1 else ''}")
    bad = B._phrase_times(text, say, [0.0] * (len(say) + 1), 10.0, 10.0 + say_t[-1], 99.0)
    expect("字幕時間:實測時間不合理時退回等比例", [x[1] for x in bad] == [x[1] for x in new])


def main():
    test_align()
    test_pause()
    if "--no-build" not in sys.argv:
        test_build()
    print("全部通過" if not FAILS else f"失敗 {len(FAILS)} 項: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
