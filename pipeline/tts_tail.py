"""配音句尾處理的共用工具(只依賴 numpy):build.py、tts_chattts.py 共用同一套門檻。

背景:句尾掉字是 ChatTTS 在語音還沒收完就輸出結束符,音檔結尾停在高能量(硬切),
固定門檻的裁靜音在實測中沒有切到語音,但對低能量句尾沒有餘裕;所以裁切一律「相對該句峰值」且尾端多留,
並提供硬切/尾端靜音的量測給品管用。
"""
import numpy as np

QC_VER = "qc8"          # 品管版本:規則有變就改;快取旁註(.qc.json)不是這個版本就必須重新檢驗;qc7 = 2026-10-21 雙辨識(Qwen3-ASR 主 / Fun-ASR 副)+ pron_rules 位置回查;qc8 = 2026-10-29 字詞時間戳改 Qwen3-ForcedAligner + 多餘停頓依詞邊界(舊快取只重新檢驗,不重錄)
HEAD_KEEP = 0.03        # 頭端保留秒數
TAIL_KEEP = 0.15        # 尾端保留秒數(句尾輕聲字能量低,寧可多留)
TRIM_REL_DB = 50.0      # 裁靜音門檻:低於該句峰值這麼多 dB 才算靜音
FADE = 0.025            # 尾端淡出秒數
GAP_REL_DB = 40.0       # 句中/句尾「靜音間隙」門檻(相對峰值)
SPEECH_REL_DB = 35.0    # 高於峰值-35dB 視為語音能量
HARD_DB = -20.0         # 結尾能量仍高於峰值-20dB = 硬切
MIN_TAIL_QUIET = 0.12   # 結尾至少要有這麼長的靜音才算收尾完整(塞音閉鎖不到 0.1 秒,不會誤認)
TRIM_VER = f"trim-v2:rel-{TRIM_REL_DB:g}dB:{HEAD_KEEP}:{TAIL_KEEP}:{FADE}"


def frame_db(w, sr, hop=0.005):
    """每 hop 秒一格的 RMS(dB)。"""
    n = max(1, int(sr * hop))
    m = len(w) // n
    if m == 0:
        return np.zeros(0)
    x = np.asarray(w[: m * n], dtype=np.float64).reshape(m, n)
    return 10 * np.log10((x * x).mean(axis=1) + 1e-12)


def _rel_db(seg, peak_db):
    if len(seg) == 0:
        return -120.0
    x = np.asarray(seg, dtype=np.float64)
    return round(float(10 * np.log10((x * x).mean() + 1e-12) - peak_db), 1)


def tail_stats(w, sr):
    """句尾聲學指標(相對該句 10ms 影格 RMS 峰值)。
    tail40_db:最後 40ms;prefade_db:淡出之前的 40ms;quiet_ms:結尾連續低於峰值-35dB 的長度;
    voiced_end:最後一格語音能量的結束秒數。"""
    e = frame_db(w, sr, 0.01)
    if e.size == 0:
        return dict(tail40_db=-120.0, prefade_db=-120.0, quiet_ms=0, voiced_end=0.0, hard_cut=False)
    pk = float(e.max())
    loud = np.flatnonzero(e > pk - SPEECH_REL_DB)
    n40, nf = int(sr * 0.04), int(sr * FADE)
    d = dict(tail40_db=_rel_db(w[-n40:], pk), prefade_db=_rel_db(w[-(n40 + nf):-nf], pk),
             quiet_ms=int(round((len(w) / sr - (loud[-1] + 1) * 0.01) * 1000)),
             voiced_end=round(float((loud[-1] + 1) * 0.01), 3))
    d["hard_cut"] = bool(max(d["tail40_db"], d["prefade_db"]) > HARD_DB)
    return d


def quiet_runs(w, sr, rel_db=GAP_REL_DB, min_len=0.15, hop=0.005):
    """低於峰值 rel_db 的連續區段 [(起, 迄)](秒),含開頭與結尾的靜音。"""
    e = frame_db(w, sr, hop)
    if e.size == 0:
        return []
    q = e < e.max() - rel_db
    out, i = [], 0
    while i < len(q):
        if q[i]:
            j = i
            while j < len(q) and q[j]:
                j += 1
            if (j - i) * hop >= min_len - 1e-9:
                out.append((round(i * hop, 3), round(j * hop, 3)))
            i = j
        else:
            i += 1
    return out


def trim_bounds(w, sr, head_keep=HEAD_KEEP, tail_keep=TAIL_KEEP, rel_db=TRIM_REL_DB):
    """溫和裁靜音的保留範圍 (a, b)(樣本):門檻相對該句峰值,頭留 head_keep、尾留 tail_keep。全靜音則不裁。"""
    hop = 0.005
    e = frame_db(w, sr, hop)
    if e.size == 0:
        return 0, len(w)
    loud = np.flatnonzero(e > e.max() - rel_db)
    if loud.size == 0:  # 能量含 NaN 時比較全為假,比照全靜音不裁,交給品管擋
        return 0, len(w)
    n = max(1, int(sr * hop))
    a = max(0, int(loud[0]) * n - int(head_keep * sr))
    b = min(len(w), (int(loud[-1]) + 1) * n + int(tail_keep * sr))
    return a, b


def fade_out(x, sr, sec=FADE):
    """尾端線性淡出;x 可為 (n,) 或 (n, 聲道)。回傳新陣列。"""
    x = np.array(x, dtype=np.float32, copy=True)
    n = min(len(x), int(sr * sec))
    if n > 0:
        ramp = np.linspace(1.0, 0.0, n, dtype=np.float32)
        x[-n:] *= ramp if x.ndim == 1 else ramp[:, None]
    return x


def gentle_trim(w, sr):
    """溫和裁靜音 + 尾端淡出。回傳 (波形, 頭裁秒數, 尾裁秒數)。"""
    a, b = trim_bounds(w, sr)
    return fade_out(w[a:b], sr), a / sr, (len(w) - b) / sr
