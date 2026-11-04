"""多餘停頓、停頓內雜音、發音表規則的單元測試(不需顯示卡):python -X utf8 pipeline\\tests\\test_tts_stray.py
1. 多餘停頓:合成的正弦波 + 靜音,find_strays 只抓非標點處、夠長的靜音;fix_strays 剪到 STRAY_KEEP。
2. 停頓內雜音:句中停頓內放低音量雜訊,clean_pauses 後內部 RMS < PAUSE_CLEAN_DB,長度與停頓外的波形不變。
3. 句尾雜音:語音結束後能量回升的雜訊由 clean_tail 清掉;自然衰減的句尾不動。
4. 發音表:職稱「長」、動詞「量」的規則與不可誤傷的詞。"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import tts_pause as TP  # noqa: E402
import tts_pron  # noqa: E402

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


def noise(sec, std, seed=1):
    return (np.random.default_rng(seed).standard_normal(int(sec * SR)) * std).astype(np.float32)


def times_of(parts):
    """parts = [(波形, 是否為字)] -> 各字的 [起, 迄]。"""
    out, t = [], 0.0
    for w, is_char in parts:
        if is_char:
            out.append([t, t + len(w) / SR])
        t += len(w) / SR
    return out


# ---- 1 多餘停頓
text = "甲乙,丙丁戊。"
parts = [(tone(0.5), 1), (sil(0.20), 0), (tone(0.5), 1), (sil(0.18), 0), (tone(0.5), 1), (sil(0.09), 0), (tone(0.4), 1),
         (sil(0.06), 0), (tone(0.4), 1), (sil(0.2), 0)]
w = np.concatenate([p[0] for p in parts])
times = times_of(parts)
pauses = TP.measure_pauses(w, SR, text, times)
strays = TP.find_strays(w, SR, text, times, pauses)
expect("逗號處的靜音不算多餘停頓", len(pauses) == 1 and abs(pauses[0]["sil"] - 0.18) < 0.011, str(pauses))
expect("抓到兩處多餘停頓(0.20 與 0.09),0.06 不算", [s["at"] for s in strays] == ["甲|乙", "丙|丁"] and
       abs(strays[0]["sil"] - 0.20) < 0.011 and abs(strays[1]["sil"] - 0.09) < 0.011, str(strays))
expect("只有 >= STRAY_MIN 的算品管未過", [s["sil"] >= TP.STRAY_MIN for s in strays] == [True, False])
w2, n = TP.fix_strays(w, SR, strays)
cut = sum(s["sil"] - TP.STRAY_KEEP for s in strays)
expect("剪短後長度少了多出來的部分", n == 2 and abs((len(w) - len(w2)) / SR - cut) < 0.002, f"{(len(w) - len(w2)) / SR:.3f} vs {cut:.3f}")
runs = [(j - i) * TP.HOP for i, j in TP.inner_runs(TP.frame_db(w2, SR))]
expect("剪短後的靜音約 STRAY_KEEP,逗號停頓不動", sorted(round(r, 2) for r in runs) == [0.04, 0.04, 0.06, 0.18], str(runs))
shift = lambda t: t - sum(s["sil"] - TP.STRAY_KEEP for s in strays if s["t0"] < t)
times2 = [[shift(a), shift(b)] for a, b in times]
p2 = TP.measure_pauses(w2, SR, text, times2)
expect("剪短後沒有多餘停頓", TP.find_strays(w2, SR, text, times2, p2) == [])
expect("接點沒有爆音(交叉淡化在靜音內)", float(np.abs(np.diff(w2)).max()) <= float(np.abs(np.diff(w)).max()) + 1e-6)

# 標點沒量到靜音(對齊偏掉)時,附近的靜音不當多餘停頓
fake = [dict(i=1, at="乙|丙", est=0.9, t0=0.9, t1=0.9, sil=0.0, dip=0.0)]
expect("標點找不到靜音時,附近 STRAY_UNSURE 秒內不判多餘停頓", [s["at"] for s in TP.find_strays(w, SR, text, times, fake)] == ["丙|丁"])

# 詞邊界(bounds):甲|乙 0.20、乙|丙 0.095 在詞邊界,丙|丁 0.12 在詞中
text3 = "甲乙丙丁。"
parts = [(tone(0.5), 1), (sil(0.20), 0), (tone(0.5), 1), (sil(0.095), 0), (tone(0.5), 1), (sil(0.12), 0), (tone(0.4), 1),
         (sil(0.2), 0)]
w = np.concatenate([p[0] for p in parts])
times = times_of(parts)
pauses = TP.measure_pauses(w, SR, text3, times)
old = TP.find_strays(w, SR, text3, times, pauses)
expect("bounds=None 與舊版相同(三處都列、全部 mid)", [(s["at"], s["kind"]) for s in old] ==
       [("甲|乙", "mid"), ("乙|丙", "mid"), ("丙|丁", "mid")], str(old))
ss = TP.find_strays(w, SR, text3, times, pauses, bounds={0, 1})
expect("詞邊界 <= STRAY_WB_KEEP 不列、詞邊界 0.20 列 wb、詞中 0.12 列 mid",
       [(s["at"], s["kind"]) for s in ss] == [("甲|乙", "wb"), ("丙|丁", "mid")], str(ss))
w2, n = TP.fix_strays(w, SR, ss)
runs = sorted(round((j - i) * TP.HOP, 2) for i, j in TP.inner_runs(TP.frame_db(w2, SR)))
expect("詞邊界剪到 STRAY_WB_KEEP、詞中剪到 STRAY_KEEP、0.095 不動", n == 2 and runs == [0.04, 0.1, 0.1], str(runs))
short = np.concatenate([tone(0.5), sil(0.08), tone(0.5), sil(0.2)])
expect("詞邊界 0.08 不列", TP.find_strays(short, SR, "甲乙。", times_of([(tone(0.5), 1), (sil(0.08), 0), (tone(0.5), 1)]), [],
                                     min_sil=0.05, bounds={0}) == [])
wb = TP.word_bounds("百分之五只加,从这一条Steam开始2026年")
if wb is None:
    print("略過 word_bounds(沒有 jieba)")
else:
    us = [u[0] for u in TP.units("百分之五只加,从这一条Steam开始2026年")]
    expect("word_bounds 只在單位交界、英文數字各一單位", all(0 <= k < len(us) - 1 for k in wb) and
           us.index("Steam") - 1 in wb and us.index("Steam") in wb, str(sorted(wb)))

# ---- 2 停頓內雜音
parts = [(tone(0.6), 1), (noise(0.2, 0.003), 0), (tone(0.6), 1), (sil(0.2), 0)]
w = np.concatenate([p[0] for p in parts])
text2 = "甲,乙。"
times = times_of(parts)
pauses = TP.measure_pauses(w, SR, text2, times)
w2, log = TP.clean_pauses(w, SR, pauses)
a, b = int(pauses[0]["t0"] * SR), int(pauses[0]["t1"] * SR)
e = int(TP.PAUSE_EDGE * SR)
expect("停頓量得到(雜訊低於靜音門檻)", abs(pauses[0]["sil"] - 0.2) < 0.011, str(pauses))
expect("處理前內部 RMS 約 -50 dBFS", len(log) == 1 and -53 < log[0]["before"] < -48, str(log))
expect("處理後內部 RMS < PAUSE_CLEAN_DB", log[0]["after"] < TP.PAUSE_CLEAN_DB and TP.rms_db(w2[a + e: b - e]) < TP.PAUSE_CLEAN_DB, str(log))
expect("長度不變、停頓外的波形不變", len(w2) == len(w) and np.array_equal(w2[:a], w[:a]) and np.array_equal(w2[b:], w[b:]))
expect("停頓長度不變", abs(TP.measure_pauses(w2, SR, text2, times)[0]["sil"] - pauses[0]["sil"]) < 0.006)

# ---- 3 句尾雜音
w = np.concatenate([tone(0.6), sil(0.08), noise(0.05, 0.003), sil(0.05)])
w2, ms = TP.clean_tail(w, SR)
expect("句尾回升的雜訊被清掉", 90 <= ms <= 110 and TP.rms_db(w2[int(0.7 * SR):]) < TP.PAUSE_CLEAN_DB and len(w2) == len(w), f"{ms}ms")
expect("語音部分不變", np.array_equal(w2[: int(0.6 * SR)], w[: int(0.6 * SR)]))
decay = tone(0.4) * np.exp(-np.arange(int(0.4 * SR)) / (0.03 * SR)).astype(np.float32)
w = np.concatenate([tone(0.6), decay, sil(0.05)])
expect("自然衰減的句尾不動", TP.clean_tail(w, SR)[1] == 0)

# ---- 4 發音表
ap = tts_pron.apply
expect("多元長 -> 掌", ap("請了公司史上第一位多元長。") == "請了公司史上第一位多元掌。")
expect("執行長/董事長/財務長 -> 掌", ap("執行長跟董事長、財務長都到了") == "執行掌跟董事掌、財務掌都到了")
expect("不誤傷 長大/很長/長期/執行長期", ap("長大、很長、長期,執行長期計畫") == "長大、很長、長期,執行長期計畫")
expect("一項一項量 -> 良", ap("性別、種族、年紀、體型,一項一項量。") == "性別、種族、年紀、體型,一項一項良。")
expect("量體溫/測量/丈量/量一量 -> 良", ap("量體溫、測量、丈量、量一量") == "良體溫、測良、丈良、良一良")
expect("再量一次/怎麼量 -> 良", ap("再量一次,到底怎麼量?") == "再良一次,到底怎麼良?")
keep = "數量、力量、大量、質量、流量表,大量身體數據,需要量很大,未來量產"
expect("不誤傷名詞的量", ap(keep) == keep, ap(keep))
expect("rule_positions 給出換字位置", tts_pron.rule_positions("第一位多元長。") == {5: "掌"} and
       tts_pron.rule_positions("他看著我") == {})
expect("changes 不含「著」", tts_pron.changes("看著多元長") == ["多元長→掌"], str(tts_pron.changes("看著多元長")))

print("\n結果:", "全部通過" if not FAILS else f"失敗 {len(FAILS)} 項:{FAILS}")


def test_all():  # pytest 收集用:上面的檢查在匯入時已跑完
    assert not FAILS, FAILS


if __name__ == "__main__":
    sys.exit(1 if FAILS else 0)
