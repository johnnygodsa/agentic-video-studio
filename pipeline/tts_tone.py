"""多音字聲調核對(靠 F0 軌跡,不靠辨識器文字;PLAN_語音辨識升級_2026-10-21 §3 / §3.7 第 2、3 點)。

辨識器常把唸錯聲調的音「改正」成正確的字,文字層只抓得到約三分之一;這裡直接量音檔:取多音字命中位置的字時段,
算 F0 軌跡,正規化到說話者音域(p10 -> 0、p90 -> 1),用規則分五類:
  1 平(高而平)  2 升  3 低 / 降升(低音域、或中間凹)  4 降  5 輕聲(短且低)
與規則要求的聲調比,不符 = tone_bad。

介面(純函式,numpy;只有 f0_track 需要 librosa):
  estimate_range(wav, sr)                      -> dict(lo, hi, med)  整句(或整批串起來)有聲段 F0 的 p10/p90(半音)
  tone_at(wav, sr, t0, t1, speaker_range)      -> dict(tone, conf, f0)  單字時段的聲調
  check_tones(wav, sr, say_t, hits, speaker_range) -> [dict(pos, expected, got, ok, conf)]
      say_t = tts_chattts.align_info 的 say_t(送配音文字每個字元位置的秒數,長度 len+1);hits = [(pos, 預期聲調 1..5)]
  tone_of_pinyin("zhu4") -> 4(帶調拼音末位數字,5 = 輕聲)
  classify_track(times, f0_hz, t0, t1, speaker_range) -> 同 tone_at,吃現成軌跡(測試與批次用,不載模型、不讀 wav)

預期接法(尚未接入):tts_cosy3.py 在 `pron_hits` 處,對每個命中的多音字呼叫 check_tones(裁切後實際進影片的音檔,
say_t 取自 align_info),不過記 `tone_bad` -> 換 seed 重錄,兩次不過列優先聽。目前只有本檔與校正腳本 tmp/tone_calib/。
校正結果見檔尾常數的註解與 pipeline/docs/tts.md。
"""
import math

import numpy as np

HOP = 0.010            # F0 軌跡的幀距(秒)
F_MIN, F_MAX = 65.0, 420.0   # pyin 搜尋範圍(Hz),涵蓋男聲到偏高的女聲
REF_HZ = 100.0         # 半音換算基準
WIN_PAD = 0.04         # 字時段兩側各擴這麼多秒補對齊誤差(Whisper 字詞時間誤差約此量級)
MIN_VOICED = 4         # 字時段內有聲幀少於這個數就判不出(tone=None)

# --- 門檻:2026-10-21 用 tmp/asr_bakeoff/r2/pairs.jsonl 的 60 對(120 音檔,CosyVoice3 現行設定;
#     使用者人耳確認 8 對正確/故意錯成立,其餘推定)擬合,過程與數字見 tmp/tone_calib/report.md。
#     所有位置量都在正規化音域(說話者 p10 = 0、p90 = 1)。
TH = dict(
    D5=0.11,    # 輕聲:有聲時長 <= D5 秒 ...
    M5=0.45,    # ... 且平均音高 <= M5
    V3=0.25,    # 三聲:中間凹陷深度(兩端較低者 - 最低點)>= V3 且最低點落在字內部
    L3=0.30,    # 三聲:平均音高 <= L3 且沒有明顯升降
    F4=0.20,    # 四聲:終點 - 起點 <= -F4
    R2=0.20,    # 二聲:終點 - 起點 >= +R2
    H1=0.45,    # 一聲:平均音高須 >= H1,否則歸三聲(低而平)
)
# 校正結果(2026-10-21,tmp/tone_calib/report.md):**未達標,不可接入品管**。
#   五類準確率(5 折交叉驗證)36%(全資料樣本內 43%,規則初始值 23%);輕聲 vs 四聲平衡準確率 57%(近乎擲硬幣);
#   「判出聲調不符」當偵測:偵測率 50% / 誤報率 42%(辨識器 Qwen3-0.6B 為 30% / 2%),無法分辨。
#   另有約 28% 的字時段判不出(有聲幀 < MIN_VOICED)。主因推測:Whisper 字詞時間誤差(約 0.1 秒)與一個字的長度(中位 0.12 秒)
#   同量級,字窗常蓋到鄰字;連讀語調(降階、句末、變調)又讓絕對 F0 走向與單字聲調脫鉤。上面 TH 是理想化形狀設計的值(單元測試用),
#   下面 TH_FIT 是語料上擬合的值(校正報告第 5 節),兩者都沒有可用的準確率。
TH_FIT = dict(D5=0.051, M5=0.347, V3=0.419, L3=0.518, F4=0.075, R2=-0.066, H1=0.899)
FIT_PAD = 0.0
USABLE = False         # 準確率達標(五類 >= 85%,或二分達標)前保持 False;接入品管的人要先檢查這個旗標
CONF_SCALE = 0.25      # 決定性比較的餘裕除以這個值 -> conf(0.5 起算,上限 1)
CONF_MIN = 0.0         # 不符且 conf >= CONF_MIN 才記 ok=False(低信心的不符只標 unsure)


def semitone(f):
    return 12.0 * np.log2(np.asarray(f, float) / REF_HZ)


def tone_of_pinyin(py):
    """帶調拼音(數字調 1..5,5 = 輕聲)-> 聲調整數;沒有數字回 None。"""
    py = (py or "").strip()
    return int(py[-1]) if py and py[-1] in "12345" else None


def f0_track(wav, sr):
    """整段音檔的 F0 軌跡 -> (times, f0_hz);無聲幀為 nan。librosa.pyin,CPU。"""
    import librosa
    y = np.ascontiguousarray(wav, dtype=np.float32)
    fl = int(0.064 * sr)
    f0, _vf, _vp = librosa.pyin(y, fmin=F_MIN, fmax=F_MAX, sr=sr, frame_length=fl,
                                hop_length=int(HOP * sr), center=True)
    return np.arange(len(f0)) * HOP, np.asarray(f0, float)


def estimate_range(wav=None, sr=None, track=None):
    """說話者音域:有聲段 F0(半音)的 p10 / p90 / 中位數。可傳現成 track=(times, f0) 省掉重算。"""
    t, f0 = track if track is not None else f0_track(wav, sr)
    v = f0[np.isfinite(f0)]
    if len(v) < 10:
        return None
    st = semitone(v)
    lo, med, hi = np.percentile(st, [10, 50, 90])
    if hi - lo < 2.0:           # 幾乎沒有音高變化(破損音檔):撐開避免除以零
        lo, hi = med - 1.0, med + 1.0
    return dict(lo=float(lo), hi=float(hi), med=float(med))


def _smooth(st):
    """3 點中位數去掉單幀八度跳。"""
    if len(st) < 3:
        return st
    pad = np.concatenate([[st[0]], st, [st[-1]]])
    return np.median(np.stack([pad[:-2], pad[1:-1], pad[2:]]), axis=0)


def _main_run(times, sel, t0, t1, gap=5):
    """擴窗後可能蓋到鄰字的有聲幀:有聲幀以 > gap 幀的無聲隔開成幾段,只留與核心 [t0, t1] 重疊最多的那段。"""
    idx = np.flatnonzero(sel)
    if len(idx) == 0:
        return sel
    cuts = np.flatnonzero(np.diff(idx) > gap) + 1
    best, best_ov = None, -1.0
    for seg in np.split(idx, cuts):
        ov = min(times[seg[-1]], t1) - max(times[seg[0]], t0)
        if ov > best_ov:
            best, best_ov = seg, ov
    out = np.zeros_like(sel)
    out[best] = True
    return out


def features(times, f0, t0, t1, rng, pad=WIN_PAD):
    """字時段的 F0 特徵(正規化音域);有聲幀不足回 None。"""
    times, f0 = np.asarray(times, float), np.asarray(f0, float)
    sel = (times >= t0 - pad) & (times <= t1 + pad) & np.isfinite(f0)
    sel = _main_run(times, sel, t0, t1)
    if sel.sum() < MIN_VOICED:
        return None
    n = (_smooth(semitone(f0[sel])) - rng["lo"]) / (rng["hi"] - rng["lo"])
    k = max(1, len(n) // 4)
    start, end = float(np.mean(n[:k])), float(np.mean(n[-k:]))
    i = int(np.argmin(n))
    mn = float(n[i])
    return dict(dur=float(sel.sum() * HOP), mean=float(np.mean(n)), start=start, end=end, delta=end - start,
                mn=mn, mx=float(np.max(n)), tmin=i / max(1, len(n) - 1), dip=min(start, end) - mn,
                slope=float((n[-1] - n[0]) / max(HOP, len(n) * HOP)))


def decide(ft, th=None):
    """特徵 -> (聲調, 餘裕)。順序:輕聲 > 三聲(凹) > 四 > 二 > 三聲(低) > 一聲。餘裕 = 決定性比較超過門檻的量。"""
    th = th or TH
    if ft["dur"] <= th["D5"] and ft["mean"] <= th["M5"]:
        return 5, min(th["D5"] - ft["dur"], th["M5"] - ft["mean"])
    if ft["dip"] >= th["V3"] and 0.15 < ft["tmin"] < 0.85:
        return 3, ft["dip"] - th["V3"]
    d = ft["delta"]
    if d <= -th["F4"]:
        return 4, -d - th["F4"]
    if d >= th["R2"]:
        return 2, d - th["R2"]
    if ft["mean"] <= th["L3"] or ft["mean"] < th["H1"]:
        return 3, max(th["L3"] - ft["mean"], th["H1"] - ft["mean"])
    return 1, min(th["R2"] - d, d + th["F4"], ft["mean"] - th["H1"])


def classify_track(times, f0, t0, t1, rng, th=None, pad=WIN_PAD):
    ft = features(times, f0, t0, t1, rng, pad) if rng else None
    if ft is None:
        return dict(tone=None, conf=0.0, f0=None)
    tone, margin = decide(ft, th)
    conf = float(min(1.0, max(0.0, 0.5 + margin / CONF_SCALE * 0.5)))
    return dict(tone=tone, conf=round(conf, 3), f0={k: round(v, 3) for k, v in ft.items()})


def tone_at(wav, sr, t0, t1, speaker_range, th=None):
    """單字時段 [t0, t1] 秒的聲調。前後各多取 0.3 秒讓 pyin 有上下文。"""
    a = max(0.0, t0 - 0.3)
    seg = np.asarray(wav)[int(a * sr):int((t1 + 0.3) * sr)]
    t, f0 = f0_track(seg, sr)
    return classify_track(t + a, f0, t0, t1, speaker_range, th)


def check_tones(wav, sr, say_t, hits, speaker_range=None, th=None, track=None):
    """hits = [(pos, 預期聲調)];回傳每個命中字的 dict(pos, expected, got, ok, conf)。
    ok=False 只在「判得出且不符且 conf >= CONF_MIN」;判不出(got=None)ok=None,不當錯也不當對(品管層照「不過列優先聽」另議)。"""
    track = track if track is not None else f0_track(wav, sr)
    rng = speaker_range or estimate_range(track=track)
    out = []
    for pos, exp in hits:
        if not say_t or pos + 1 >= len(say_t):
            out.append(dict(pos=pos, expected=exp, got=None, ok=None, conf=0.0))
            continue
        r = classify_track(track[0], track[1], say_t[pos], say_t[pos + 1], rng, th)
        got = r["tone"]
        ok = None if got is None else (got == exp or r["conf"] < CONF_MIN)
        out.append(dict(pos=pos, expected=exp, got=got, ok=ok, conf=r["conf"]))
    return out
