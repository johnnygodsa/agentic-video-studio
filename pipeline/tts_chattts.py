#!/usr/bin/env python3
r"""ChatTTS 批次包裝(含品管重試)。用 tts_env_chattts 的 python 執行:
<Claude_Video>/tts_env_chattts/Scripts/python.exe pipeline/tts_chattts.py jobs.json --spk-pt X.pt --rate +18%

jobs.json = [{"text": "...", "out": "xxx.wav", "idx": 句編號(可省), "verify": true(可省)}, ...];模型只載入一次。
  verify=true 且 out 已存在:先對現有音檔做品管,通過就沿用(只做溫和裁切),不通過才重錄。
--voice: seed<N> = 以 N 為種子隨機抽說話人。
--spk-pt <檔>: 外部音色檔(768 維 float tensor;與 --voice 擇一,同時給則以音色檔為準),僅以
  torch.load(weights_only=True) 載入,再用本版 ChatTTS 的 speaker._encode 轉成壓縮字串;取樣種子用 --seed。
--rate: +10% -> [speed_6](每 +10% 加 1 級,範圍 0-9,預設 5)。
發音修正:prep_text 會先呼叫 tts_pron.apply(助詞「著」->「者」等,見該檔檔頭);只改送進模型的文字,品管把替換前後視為同字,
  辨識成 zhù 字(住注柱...)才算錯(fails=pron)。
口語填充:一律 skip_refine_text,不產生 [oral]/[laugh]。繁體字先轉簡體。

句尾截斷的對策(犧牲尾綴):本版 ChatTTS 常在最後一個字還沒唸完就輸出結束符(音檔停在高能量,或乾脆漏掉句尾的
欸/啊/了/沒有),Whisper 又會把缺的字腦補回來。所以合成時在原句後面接固定的犧牲短句 SACRIFICE,讓截斷落在
犧牲段;合成後用「ASR 字詞時間戳 + 靜音間隙」找出原句與犧牲段之間的停頓,從停頓起點後 TAIL_KEEP 秒切掉後段,
再分別辨識前後兩段確認(前段句尾兩字完整、後段認得出犧牲短句)。找不到可確認的切點 = 失敗重試。

品管對象是「最終寫出的音檔」(已裁頭尾、已切掉犧牲段;build.py 之後只轉取樣率不再裁切)。任一不過就換 seed 重試,
最多 --max-retry 次,全失敗取分數最高者並在報告標示 passed=false:
  1 音高:基頻中位數在整批中位數 ±18% 內
  2 內容:faster-whisper 辨識後與原文比對(簡體、去標點/數字/英文),字元或拼音相似度 >= 0.85
  3 句尾兩字:原文最後兩個單位(中文字比讀音、連續英文當一個單位)必須正好是辨識結果的結尾,後面不得多字(tail_chars);
          尾端多出語助詞(嗯啊呃...)時,只有在它與前面語音之間有 >= 0.25 秒靜音才裁掉重驗,否則算失敗(tail_particle)
  4 句尾聲學:結尾能量仍高於峰值-20dB = 硬切(hard_cut);結尾靜音不足 0.12 秒(tail_abrupt)
  5 時間戳:最後一字的結束時間距檔尾 >= 0.05 秒(end_margin);最後一字之後不得再有 > 0.3 秒的聲音(tail_extra)
  6 長度:每音節秒數在整批中位數的 0.6-1.6 倍
  7 聲紋:ECAPA 嵌入與基準(3 句校正句中最相似兩句的平均)cosine >= 依長度迴歸門檻(整批迴歸 - k*sigma,下限 --spk-min)
  8 語速(全部品管過後的最後一關):每單位「字數(n_syllables,送進引擎的字) ÷ 有聲長度」與整批中位數(base_cps)差 > RATE_TOL 就換 seed
    重錄,最多 RATE_SEEDS 個新 seed;只有「其他品管全過」的候選才算數,取最接近中位數者(已在中位數 ±RATE_TOL/2 內就停);
    8 個 seed 都不到範圍的保留最接近者並在 .qc.json 標 rate_ok=false。
  9 多餘停頓(tts_pause.find_strays):非句中標點處的靜音 >= STRAY_MIN 秒(stray_pause)先換 seed 重錄(與句中停頓共用 COMMA_RETRY 次),
    仍有就由 fix_strays 剪到 STRAY_KEEP 秒;STRAY_TRIM_MIN 以上、未達 STRAY_MIN 的不重錄,直接剪。紀錄 stray_fix。
    詞邊界(jieba,kind="wb")的靜音 <= STRAY_WB_KEEP 不算、超過只剪到 STRAY_WB_KEEP,不算品管未過(channel/_archive/plans/PLAN_配音對齊_2026-10-29.md §2.4)。
  10 發音表換字回查(pron_rule_bad):職稱「長」->掌、動詞「量」->良 等換字位置,辨識出的字讀成原字的另一個讀音(長->腸、量->亮)就算 pron。
最終音檔的後處理(main 結尾;修過就重新辨識量測,別項變差就退回):句中停頓補/剪(pause_fix)-> 多餘停頓剪短(stray_fix)->
  句中停頓內部與句尾靜音區的換氣聲/雜音換成數位靜音(pause_clean、tail_clean_ms;tts_pause.clean_pauses / clean_tail)。
整批基準(音高/語速/聲紋迴歸)在句數 >= 30 時存成 jobs 同目錄的 _qc_base.json,之後的小批次沿用,避免樣本太少失準。
輸出:每句 out 旁寫 <名稱>.qc.json(含 qc_ver、音檔 sha1、是否通過與各項指標;build.py 據此判斷快取能否沿用),
另寫整批報告(預設 jobs 同名 .qc.json)。
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P  # noqa: E402
import tts_pron  # noqa: E402
import tts_pause as TP  # noqa: E402
import tts_asr as TA  # noqa: E402

os.environ.setdefault("HF_HOME", str(P.TTS_MODELS))
for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
import torchaudio  # noqa: E402
from opencc import OpenCC  # noqa: E402

from tts_tail import (GAP_REL_DB, MIN_TAIL_QUIET, QC_VER, TAIL_KEEP, fade_out, gentle_trim, quiet_runs,  # noqa: E402
                      tail_stats, trim_bounds)

SR = 24000
MODELS = os.path.join(os.environ["HF_HOME"])
PARTICLES = set("嗯啊呃哦呀喔唉哎额诶")
CALIB = ["今天我們來聊一聊這款遊戲到底值不值得買。", "這個問題很多人都問過,答案其實沒有那麼簡單。",
         "先看畫面,再看操作手感,最後才是劇情。"]
# 犧牲尾綴:實測各種寫法後,[uv_break] + 短句最能穩定在原句後產生 >= 0.15 秒停頓(tail_diagnosis.json 的 sacrifice_test)
SACRIFICE = "[uv_break]好的，就这样。"
SACRIFICE_SAY = "好的就这样"
MIN_GAP = 0.15          # 原句與犧牲段之間的靜音間隙至少這麼長才當切點
BLIP_GAP = 0.25         # 句尾多餘聲音與前面語音之間的靜音至少這麼長才裁
END_MARGIN_MS = 50      # 最後一字的時間戳距檔尾至少這麼多(實測:硬切的音檔 <= 40,正常收尾 >= 65)
TAIL_EXTRA_MS = 300     # 最後一字之後最多容許這麼長的聲音
BASE_MIN = 30           # 句數達此值才用本批統計當基準並存檔
RATE_TOL = 0.12         # 語速(字數 ÷ 有聲長度)與全片中位數差超過這個比例就換 seed 重錄
RATE_SEEDS = 8          # 語速重錄最多再試幾個 seed
POST_FIXABLE = ("comma_short", "stray_pause")  # 後處理補得起來的品管項(插入靜音 / 剪短),不必為它一直重錄
COMMA_MARK = "[uv_break]"  # 句中逗號送進引擎時換成的寫法(見 engine_text)。2026-10-11 實測 5 句 x 3 seed:保留「，」靜音中位數 0.015 秒(18/21 處不足 0.10);換成 [uv_break] 中位數 0.22 秒(0.095-0.405,1/22 處不足);「，[uv_break]」沒有更好且回查相似度較低
_cc = OpenCC("t2s")
_NUM = "零〇一二三四五六七八九十百千萬万兩两"
_PUNCT_RE = re.compile(r"[\s\W_]+|[A-Za-z0-9]+|[%s]" % _NUM, re.U)
_NUM_DOT_RE = re.compile(r"(?<=[%s])[點点](?=[%s])" % (_NUM, _NUM))  # 數字之間的「點」(二點零)


def speed_prompt(rate):
    pct = float(rate.strip().rstrip("%"))
    return f"[speed_{min(9, max(0, round(5 + pct / 10)))}]"


def load_chat():
    import ChatTTS
    chat = ChatTTS.Chat()
    if not chat.load(source="huggingface", compile=False):
        raise RuntimeError("ChatTTS 模型載入失敗")
    return chat


def load_spk_pt(chat, path):
    """安全載入舊格式音色檔:只用 weights_only=True,失敗直接報錯,不退回 pickle。"""
    t = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(t, torch.Tensor) or t.shape != (768,):
        raise RuntimeError(f"音色檔格式不符(需 768 維 tensor): {path}")
    return chat.speaker._encode(t.float())


def synth(chat, text, seed, rate, spk):
    import ChatTTS
    torch.manual_seed(seed)
    if spk is None:
        spk = chat.sample_random_speaker()
    p_code = ChatTTS.Chat.InferCodeParams(spk_emb=spk, prompt=speed_prompt(rate), temperature=0.3,
                                          top_P=0.7, top_K=20, manual_seed=seed)
    wavs = chat.infer([text], skip_refine_text=True, params_infer_code=p_code, use_decoder=True)
    w = np.asarray(wavs[0], dtype=np.float32).reshape(-1)
    peak = float(np.abs(w).max()) if w.size else 0.0
    return w * (0.95 / peak) if peak > 0.95 else w  # 避免削波


_D = "零一二三四五六七八九"


def _group4(n, lead_liang):
    """0 < n < 10000 的中文讀法(含內部補零由呼叫端處理)。"""
    out, units = "", [(1000, "千"), (100, "百"), (10, "十"), (1, "")]
    zero = False
    started = False
    for u, name in units:
        d = n // u % 10
        if d == 0:
            if started:
                zero = True
            continue
        if zero:
            out += "零"
            zero = False
        if u == 10 and d == 1 and not started and not lead_liang:
            out += "十"
        elif d == 2 and u >= 100:
            out += "两" + name
        else:
            out += _D[d] + name
        started = True
    return out


def int_to_cn(n):
    if n == 0:
        return "零"
    parts = []
    for size, unit in ((10 ** 8, "亿"), (10 ** 4, "万"), (1, "")):
        g = n // size % (10000 if size > 1 else 10000)
        if size == 10 ** 8:
            g = n // size
        if g:
            parts.append((g, unit))
    out, prev_zero_pad = "", False
    for i, (g, unit) in enumerate(parts):
        txt = _group4(g, False)
        if g < 1000 and i > 0:
            txt = "零" + txt
        if g == 2 and unit:
            txt = "两"
        out += txt + unit
    return out


def num_to_cn(tok, year_ctx=False):
    tok = tok.replace(",", "")
    if "." in tok:
        a, b = tok.split(".", 1)
        return int_to_cn(int(a or 0)) + "点" + "".join(_D[int(c)] for c in b)
    if year_ctx or len(tok) > 8 or (len(tok) > 1 and tok[0] == "0"):
        return "".join(_D[int(c)] for c in tok)
    return int_to_cn(int(tok))


def prep_text(text):
    """發音修正(tts_pron:助詞「著」等多音字誤讀),繁->簡,數字轉中文讀法(本版 ChatTTS 沒有數字正規化器,數字會被直接丟掉造成漏字),標點整理。
    句尾一律收成「。」:本版 ChatTTS 的正規化會把「?」整個刪掉,句子變成沒有結尾標點。"""
    t = _cc.convert(tts_pron.apply(text)).strip()
    t = re.sub(r"(\d[\d,]*(?:\.\d+)?)\s*%", lambda m: "百分之" + num_to_cn(m.group(1)), t)
    t = re.sub(r"(\d{4})(?=年)", lambda m: num_to_cn(m.group(1), True), t)
    t = re.sub(r"(\d[\d,]*(?:\.\d+)?)(\+?)", lambda m: num_to_cn(m.group(1)) + ("多" if m.group(2) else ""), t)
    t = t.translate(str.maketrans({"《": "", "》": "", "「": "", "」": "", "『": "", "』": "", "（": "，", "）": "，",
                                   "(": "，", ")": "，", "：": "，", "；": "，", "、": "，", ":": "，", ";": "，",
                                   "—": "，", "…": "，", "~": "", "～": ""}))
    return re.sub(r"[\s。?!？！.，,]+$", "", t) + "。"


def engine_text(text):
    """實際送進 ChatTTS 的文字:prep_text 的結果,句中的逗號換成 COMMA_MARK。
    另開一個函式是因為 prep_text 也拿來數音節與對齊,控制符不能混進去。"""
    t = prep_text(text)
    return t if COMMA_MARK == "，" else re.sub("[，,]", COMMA_MARK, t[:-1]) + t[-1]


def n_syllables(text):
    """估計音節數:中文一字一音節(數字先轉成中文讀法),英文單字以母音群數估計。"""
    t = prep_text(text)
    en = sum(max(1, len(re.findall(r"[aeiouy]+", w.lower()))) for w in re.findall(r"[A-Za-z]+", t))
    return max(1, len(re.findall(r"[\u4e00-\u9fff]", t)) + en)


# ------------------------------------------------------------ 訊號分析
def envelope_db(w, hop=0.01):
    n = int(SR * hop)
    m = len(w) // n
    if m == 0:
        return np.zeros(0)
    rms = np.sqrt((w[: m * n].reshape(m, n) ** 2).mean(axis=1) + 1e-12)
    return 20 * np.log10(rms)


def voiced_segments(w, rel_db=35.0, merge_gap=0.12, hop=0.01):
    env = envelope_db(w, hop)
    if env.size == 0:
        return []
    on = env > env.max() - rel_db
    segs, i = [], 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            segs.append([i * hop, j * hop])
            i = j
        else:
            i += 1
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < merge_gap:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return merged


def trim_tail_blip(w):
    """句尾多出的短促聲音(像「嗯」)裁掉:最後一段 <0.4s 且與前段之間有 >= BLIP_GAP 秒靜音才裁
    (呼叫端另需 ASR 確認多出語助詞;診斷顯示舊版較寬的條件沒有誤傷,但也不該只憑能量就裁)。"""
    segs = voiced_segments(w)
    if len(segs) >= 2 and segs[-1][1] - segs[-1][0] < 0.4 and segs[-1][0] - segs[-2][1] >= BLIP_GAP:
        return fade_out(w[: int((segs[-2][1] + TAIL_KEEP) * SR)], SR), True
    return w, False


def f0_median(w):
    t = torch.from_numpy(w)
    f0 = torchaudio.functional.detect_pitch_frequency(t, SR, frame_time=1e-2, freq_low=60, freq_high=400)
    env = envelope_db(w)
    k = min(len(f0), len(env))
    if k == 0:
        return 0.0
    ok = torch.from_numpy(env[:k] > env.max() - 25)
    f = f0[:k][ok & (f0[:k] > 0)]
    return float(f.median()) if f.numel() else 0.0


# ------------------------------------------------------------ 文字比對
def norm_text(s):
    return _PUNCT_RE.sub("", _cc.convert(s))


def pinyin_seq(s):
    from pypinyin import Style, lazy_pinyin
    return lazy_pinyin(s, style=Style.NORMAL, errors="ignore")


def _ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def similarity(ref, hyp):
    r, h = norm_text(ref), norm_text(hyp)
    if not r:
        return 1.0, 1.0
    return _ratio(r, h), _ratio(pinyin_seq(r), pinyin_seq(h))


def tail_particle(ref, hyp):
    r, h = norm_text(ref), norm_text(hyp)
    return bool(h) and h[-1] in PARTICLES and (not r or r[-1] != h[-1])


def _fuzzy(p):
    """拼音模糊化:平翹舌、前後鼻音不分(ASR 常混)。"""
    return re.sub(r"ng$", "n", re.sub(r"^([zcs])h", r"\1", p))


def tail_units(s):
    """比對句尾用的單位序列:中文字(數字、數字之間的「點」除外,ASR 會寫成阿拉伯數字)-> 該字所有讀音(模糊化)的集合;
    中間沒有中文字的連續英文 -> 一個小寫字串。"""
    from pypinyin import Style, pinyin
    out = []
    for tok in re.findall(r"[A-Za-z]+|[\u4e00-\u9fff]", _NUM_DOT_RE.sub("", _cc.convert(s))):
        if tok.isascii():
            if out and isinstance(out[-1], str):
                out[-1] += tok.lower()
            else:
                out.append(tok.lower())
        elif tok not in _NUM:
            ps = pinyin(tok, style=Style.NORMAL, heteronym=True, errors="ignore")
            out.append(frozenset(_fuzzy(p) for p in (ps[0] if ps else [])))
    return out


def _unit_match(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return isinstance(a, str) and isinstance(b, str) and _ratio(a[-10:], b[-10:]) >= 0.6
    return bool(a & b)


def _weight(u):
    """單位的份量:英文算字母數,中文字算 3(約一個音節的字母數)。"""
    return len(u) if isinstance(u, str) else 3


def tail_ok(ref, hyp):
    """原文最後 2 個單位必須正好是辨識結果的結尾(其後不得多字),防止漏唸句尾字或殘留犧牲段。
    句尾是英文時中文 ASR 拼不準(常寫成別的英文字或音譯),改為要求:英文前那個中文字之後,還有份量相當的內容。"""
    want, got = tail_units(ref)[-2:], tail_units(hyp)
    if want and isinstance(want[-1], str):
        k = -1
        if len(want) == 2:
            k = max((i for i, u in enumerate(got) if _unit_match(want[0], u)), default=None)
            if k is None:
                return False
        return 0.5 * len(want[-1]) <= sum(_weight(u) for u in got[k + 1:]) <= 1.6 * len(want[-1]) + 3
    return len(got) >= len(want) and all(_unit_match(a, b) for a, b in zip(want, got[len(got) - len(want):]))


def tokens(s):
    """粗略的音節序列(切分原句/犧牲段用):中文字 -> 拼音,英文單字 -> 小寫原字;數字略過。"""
    return [t.lower() if t.isascii() else (pinyin_seq(t) or [t])[0]
            for t in re.findall(r"[A-Za-z]+|[\u4e00-\u9fff]", _cc.convert(s)) if t not in _NUM]


def is_sacrifice(hyp):
    """切下來的後段是否就是犧牲短句(開頭容許語助詞;短句本身常被截斷,認得出開頭即可),且沒有夾帶別的字(含英文、數字)。"""
    if re.search(r"[A-Za-z0-9]", hyp):
        return False
    h = norm_text(hyp).lstrip("".join(PARTICLES))
    got, want = [_fuzzy(p) for p in pinyin_seq(h)], [_fuzzy(p) for p in pinyin_seq(SACRIFICE_SAY)]
    return 0 < len(got) <= len(want) + 2 and (got[:2] == want[:2] or (got[0] == want[0] and _ratio(got, want) >= 0.5))


# ------------------------------------------------------------ 模型封裝
class QC:
    """品管模型:語音辨識(tts_asr.ASR;預設 Qwen3-ASR-0.6B + faster-whisper small 取字詞時間)與聲紋(ECAPA)。
    pron_rules=True(CosyVoice3 路徑)時 pron_rule_bad 也回查 pron_rules.json 多音字規則的位置。"""

    def __init__(self, asr_model, spk_min, pron_rules=False):
        self.asr = TA.ASR(asr_model)
        self.asr_engine = self.asr.name
        self.pron_rules = pron_rules
        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except ImportError:
            from speechbrain.pretrained import EncoderClassifier
        self.ecapa = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb", savedir=os.path.join(MODELS, "spkrec-ecapa"),
            run_opts={"device": "cuda"})
        self.spk_min = spk_min
        self.spk_base = None

    @staticmethod
    def to16(w):
        return torchaudio.functional.resample(torch.from_numpy(np.ascontiguousarray(w)), SR, 16000).numpy()

    def transcribe(self, w, text=None):
        """text = 對齊用文字(fa_text);ts_engine = 這次字詞時間戳的來源("qwen3-fa" | "whisper-small")。"""
        out = self.asr.transcribe(self.to16(w), text)
        self.ts_engine = getattr(self.asr, "last_ts", None)
        return out

    def close(self):
        self.asr.close()

    @torch.no_grad()
    def embed(self, w):
        x = torchaudio.functional.resample(torch.from_numpy(np.ascontiguousarray(w)), SR, 16000)[None].cuda()
        return torch.nn.functional.normalize(self.ecapa.encode_batch(x).squeeze(), dim=0)

    def set_speaker_base(self, wavs):
        es = [self.embed(w) for w in wavs]
        best, pair = -2, (0, 1)
        for i in range(len(es)):
            for j in range(i + 1, len(es)):
                s = float(es[i] @ es[j])
                if s > best:
                    best, pair = s, (i, j)
        self.spk_base = torch.nn.functional.normalize(es[pair[0]] + es[pair[1]], dim=0)
        return best


# ------------------------------------------------------------ 犧牲尾綴切除
def split_words(words, ref):
    """把辨識字詞分成「原句 / 犧牲短句」:回傳犧牲段起始索引 k(兩段各自與原文、短句的音節相似度依長度加權,取總和最大)。"""
    rp, sp = tokens(ref), tokens(SACRIFICE_SAY)
    best_k, best = len(words), -1.0
    for k in range(len(words) + 1):
        a = tokens("".join(x[0] for x in words[:k]))
        b = tokens("".join(x[0] for x in words[k:]))
        sc = _ratio(rp, a) * len(rp) + _ratio(sp, b) * len(sp)
        if sc > best:
            best_k, best = k, sc
    return best_k


def cut_sacrifice(qc, w, text):
    """從「原句 + 犧牲尾綴」的合成結果切出原句。回傳 (原句波形, 辨識文字, 字詞, info);找不到可確認的切點時波形為 None,
    info["fallback"] 給一個未經確認的切點秒數(只在全部重試都失敗時拿來墊底)。
    ASR 字詞時間戳只用來框出交界的大概位置(誤差可達 0.3 秒);真正的切點是那附近的靜音間隙:由早到晚,
    第一個「切下來的後段辨識出來就只有犧牲短句」的間隙。前段句尾是否完整,由之後的品管(tail_chars)把關。"""
    hyp, words = qc.transcribe(w, fa_text(text) + fa_text(SACRIFICE_SAY))
    k = split_words(words, text)
    dur = len(w) / SR
    info = dict(pre_asr=hyp, fallback=round(dur, 3))
    if not 0 < k < len(words):
        return None, None, None, dict(info, why="no_suffix")
    t_last, t_sfx = words[k - 1][2], words[k][1]
    gaps = [g for g in quiet_runs(w, SR, GAP_REL_DB, MIN_GAP)
            if g[0] > 0.2 and g[1] < dur - 0.05 and g[1] > t_last - 0.6 and g[0] < t_sfx + 0.4]
    near = [g for g in gaps if g[0] <= t_sfx + 0.1]  # 沒有任何間隙通過驗證時,退而用犧牲段開始前最近的間隙
    info.update(t_last=round(t_last, 2), t_sfx=round(t_sfx, 2), gaps=gaps,
                fallback=round(near[-1][0] + TAIL_KEEP if near else max(0.2, t_sfx - 0.05), 3))
    for g in gaps:
        cut = int((g[0] + TAIL_KEEP) * SR)
        hyp_r, _ = qc.transcribe(w[cut:])
        if not is_sacrifice(hyp_r):
            continue
        head = fade_out(w[:cut], SR)
        hyp_h, words_h = qc.transcribe(head, fa_text(text))
        info.update(gap=g, sfx_asr=hyp_r)
        return head, hyp_h, words_h, info
    return None, None, None, dict(info, why="unverified" if gaps else "no_gap")


# ------------------------------------------------------------ 品管
def _align_key(u):
    return u.lower() if u.isascii() else _fuzzy((pinyin_seq(u) or [u])[0])


def fa_text(text):
    """對齊器(Qwen3-ForcedAligner)用的文字:prep_text 後的發音單位串起來(簡體、無標點,數字已轉中文讀法)。"""
    return _cc.convert("".join(u[0] for u in TP.units(prep_text(text))))


def align_info(w, text, words):
    """辨識字詞時間對回已知文本(辨識結果只拿來取時間):回傳 pauses = 每個句中停頓的實測靜音(tts_pause.measure_pauses)、
    say_t = text(送進本程式的句子,@say 替換後)每個字元位置在音檔中的秒數(長度 len(text)+1;build.py 的字幕分段用)、
    align_cov = 對得到辨識字的單位比例。"""
    prep = prep_text(text)
    dur = len(w) / SR
    hyp = TP.hyp_units([(_cc.convert(x[0]), x[1], x[2]) for x in words or []])
    times, matched = TP.align([u[0] for u in TP.units(prep)], hyp, dur, _align_key)
    simp, say_t = _cc.convert(text), None
    cmap = TP.char_map(simp, prep)   # prep_text 把頓號換成逗號:原文頓號位置對回 prep,標成軟停頓
    pauses = TP.measure_pauses(w, SR, prep, times, soft_at={cmap[q] for q, c in enumerate(simp) if c in TP.SOFT_MARKS})
    strays = TP.find_strays(w, SR, prep, times, pauses, bounds=TP.word_bounds(prep))
    if len(simp) == len(text):
        cs = TP.char_starts(prep, times, dur, pauses)
        say_t = [round(cs[q], 3) for q in cmap]
    return dict(pauses=pauses, strays=strays, say_t=say_t, align_cov=round(sum(matched) / max(1, len(matched)), 3))


def comma_only(m):
    """沒過的只有後處理補得起來的項目(POST_FIXABLE):句中停頓不足且每一處都補得起來(tts_pause.fixable,最後由 fix_pauses
    插入靜音)、非標點處的多餘停頓(最後由 fix_strays 剪短)。"""
    fails = m.get("fails") or []
    return bool(fails) and set(fails) <= set(POST_FIXABLE) and \
        all(TP.fixable(p) for p in m["pauses"] if p["sil"] < TP.COMMA_MIN and not TP.soft_skip(p))


# 近音字寫法 -> 語音辨識必須聽得出的字樣(聽不出就當發音錯,換 seed 重錄)。
# 2026-10-11 使用者聽過七種 EA 寫法後選定「伊誒」(A/B),其餘否決;「伊誒」辨識結果不固定(EA/耶/BN),不設回查。
ASR_EXPECT = {}


def pron_targets(text, rules=False):
    """回查讀音的位置 {text 位置: (原字(簡體), 應讀 tone3)}:發音表換字(職稱「長」->掌、動詞「量」->良…;
    tts_pron.rule_positions,應讀 = 換上去那個字的預設讀音);rules=True 再加 pron_rules.json 多音字規則命中的位置
    (tts_cosy_text 的規則事件,應讀 = 標注的拼音;同一位置以規則為準;always 字的位置多帶 strict=True,
    見 tts_asr.pron_pos_bad)。"""
    tg = {i: (_cc.convert(text[i]), TA.token_reading(_cc.convert(c))) for i, c in tts_pron.rule_positions(text).items()}
    if rules:
        import tts_cosy_text as CT
        for p, ch, py, *_ in CT._live_events(text, CT._word_spans(text)[0]):
            if py and p < len(text) and text[p] == ch:
                tg[p] = (_cc.convert(ch), TA.token_reading(py), ch in CT.RULE_ALWAYS)  # 第三項 strict:always 字非同音即記錯
    return tg


def pron_rule_bad(text, hyp, rules=False):
    """回查位置(pron_targets)上,辨識出來的字若讀成原字的「另一個讀音」(長 -> 腸 chang2、量 -> 亮 liang4),算一個。
    辨識寫回原字或應讀的同音字時讀音無從分辨,不算錯;辨識成完全不相干的音由內容相似度把關,
    但 always 字(著、得、曝…)的位置辨識成非同音的字(看得到 -> 看不到)也算(判定見 tts_asr.pron_pos_bad)。"""
    tg = pron_targets(text, rules)
    if not tg:
        return 0
    ref_n = norm_text("".join(tts_pron.MARK if i in tg else c for i, c in enumerate(text)))
    if ref_n.count(tts_pron.MARK) != len(tg):
        return 0
    order = iter(tg[i] for i in sorted(tg))
    targets, ref = {}, []
    for k, c in enumerate(ref_n):
        if c == tts_pron.MARK:
            targets[k] = next(order)
            c = targets[k][0]
        ref.append(c)
    return len(TA.pron_pos_bad("".join(ref), norm_text(hyp), targets))


def asr_judge(text, hyp, rules=False):
    """辨識文字與文案的比對(主品管 measure 與副辨識回查共用):回傳 sim_char / sim_pinyin / sim / pron_bad。"""
    ref, hyp_c, pron_bad = tts_pron.qc_pair(text, hyp, norm_text)  # 助詞「著」換字:著/着/者視為同字;辨識成 zhù 字才算錯
    pron_bad += pron_rule_bad(text, hyp, rules)
    pron_bad += sum(1 for k, v in ASR_EXPECT.items() if k in text and v not in hyp.upper().replace(" ", ""))
    c, p = similarity(ref, hyp_c)
    return dict(sim_char=round(c, 3), sim_pinyin=round(p, 3), sim=round(max(c, p), 3), pron_bad=pron_bad,
                ref=ref, hyp_c=hyp_c)


def measure(qc, w, text, hyp=None, words=None):
    """對最終音檔量測各項指標。回傳 (最終波形, 指標);只有「ASR 確認多出語助詞且其前有足夠靜音」時才會再裁尾。"""
    if hyp is None:
        hyp, words = qc.transcribe(w, fa_text(text))
    trimmed = False
    if tail_particle(text, hyp):
        w2, cut = trim_tail_blip(w)
        if cut:
            w, trimmed = w2, True
            hyp, words = qc.transcribe(w, fa_text(text))
    jd = asr_judge(text, hyp, getattr(qc, "pron_rules", False))
    ref, hyp_c, pron_bad, c, p = jd["ref"], jd["hyp_c"], jd["pron_bad"], jd["sim_char"], jd["sim_pinyin"]
    segs = voiced_segments(w)
    span = (segs[-1][1] - segs[0][0]) if segs else 0.0
    voiced_s = sum(b - a for a, b in segs)   # 有聲長度:語音段(段間靜音 < 0.12 秒併段)的總和,不含句中停頓
    dur = len(w) / SR
    ts = tail_stats(w, SR)
    last_end = min(dur, words[-1][2]) if words else 0.0
    return w, dict(align_info(w, text, words), asr=hyp, sim_char=round(c, 3), sim_pinyin=round(p, 3), sim=round(max(c, p), 3),
                   n_syl=n_syllables(text), voiced_s=round(voiced_s, 3), cps=round(n_syllables(text) / max(voiced_s, 0.05), 3),
                   f0=round(f0_median(w), 1), spk_sim=round(float(qc.embed(w) @ qc.spk_base), 3),
                   spc=span / n_syllables(text), particle=tail_particle(ref, hyp_c), tail_ok=tail_ok(ref, hyp_c), pron_bad=pron_bad,
                   tail_trimmed=trimmed, dur=round(dur, 3), tail40_db=ts["tail40_db"], prefade_db=ts["prefade_db"],
                   quiet_ms=ts["quiet_ms"], hard_cut=ts["hard_cut"],
                   end_margin_ms=int(round((dur - last_end) * 1000)),
                   tail_extra_ms=int(round((ts["voiced_end"] - last_end) * 1000)), no_cut=False,
                   ts_engine=getattr(qc, "ts_engine", None))


def from_cache(qc, path, text):
    """既有音檔(舊快取):溫和裁切後直接量測。"""
    w, sr = sf.read(path, dtype="float32")
    w = w.mean(axis=1) if w.ndim > 1 else w
    if sr != SR:
        w = torchaudio.functional.resample(torch.from_numpy(np.ascontiguousarray(w)), sr, SR).numpy()
    w, m = measure(qc, gentle_trim(w, SR)[0], text)
    return w, dict(m, source="cache", seed=None)


def from_synth(qc, chat, text, seed, rate, spk):
    """合成「原句 + 犧牲尾綴」-> 裁頭 -> 切掉犧牲段 -> 量測。"""
    raw = synth(chat, engine_text(text) + SACRIFICE, seed, rate, spk)
    raw = raw[trim_bounds(raw, SR)[0]:]
    head, hyp, words, info = cut_sacrifice(qc, raw, text)
    no_cut = head is None
    if no_cut:
        head = fade_out(raw[: int(info["fallback"] * SR)], SR)
    w, m = measure(qc, head, text, hyp, words)
    return w, dict(m, source="synth", seed=seed, no_cut=no_cut, cut=info)


def from_plain(qc, chat, text, seed, rate, spk):
    """不加犧牲尾綴的合成(舊作法,句尾可能被截)。只在加尾綴怎麼試都不過時拿來一起比分數
    (句尾夾英文時模型常接不上尾綴,整句後半反而亂掉)。"""
    w, m = measure(qc, gentle_trim(synth(chat, engine_text(text), seed, rate, spk), SR)[0], text)
    return w, dict(m, source="plain", seed=seed)


def fit_spk(res):
    """聲紋相似度隨語句長度上升(短句天生偏低),以整批(第一輪)的 sim ~ a + b*log(dur) 穩健迴歸為基準。"""
    x = np.log([max(0.3, r["m"]["dur"]) for r in res])
    y = np.array([r["m"]["spk_sim"] for r in res])
    w = np.ones(len(x))
    A = np.vstack([np.ones_like(x), x]).T
    coef, sigma = np.zeros(2), 0.1
    for _ in range(5):
        coef = np.linalg.lstsq(A * w[:, None], y * w, rcond=None)[0]
        d = y - A @ coef
        sigma = max(0.02, 1.4826 * float(np.median(np.abs(d - np.median(d)))))
        w = (np.abs(d) < 2.5 * sigma).astype(float)
    return float(coef[0]), float(coef[1]), sigma


def spk_thr(a, fit, dur):
    ia, ib, sigma = fit
    return max(a.spk_min, ia + ib * np.log(max(0.3, dur)) - a.spk_k * sigma)


def check(m, base_f0, base_spc, a, fit):
    fails = []
    m["f0_ratio"] = round(m["f0"] / base_f0, 3) if base_f0 else 0
    m["spc_ratio"] = round(m["spc"] / base_spc, 3) if base_spc else 1
    if abs(m["f0_ratio"] - 1) > a.pitch_tol:
        fails.append("pitch")
    m["spk_thr"] = round(float(spk_thr(a, fit, m["dur"])), 3)
    if m["spk_sim"] < m["spk_thr"]:
        fails.append("speaker")
    if m["sim"] < a.sim_min:
        fails.append("content")
    if m.get("pron_bad"):
        fails.append("pron")
    if m["particle"]:
        fails.append("tail_particle")
    if not m["tail_ok"]:
        fails.append("tail_chars")
    if m["no_cut"]:
        fails.append("no_cut")
    if m["hard_cut"]:
        fails.append("hard_cut")
    if m["quiet_ms"] < MIN_TAIL_QUIET * 1000:
        fails.append("tail_abrupt")
    if m["end_margin_ms"] < END_MARGIN_MS:
        fails.append("end_margin")
    if m["tail_extra_ms"] > TAIL_EXTRA_MS:
        fails.append("tail_extra")
    if not (0.6 <= m["spc_ratio"] <= 1.6):
        fails.append("length")
    short = [p for p in m.get("pauses") or [] if p["sil"] < TP.COMMA_MIN and not TP.soft_skip(p)]
    if short:  # 句中停頓不足:先換 seed 重錄;最後仍不足由 fix_pauses 插入靜音,補不了的改記 comma_bad(頓號補不起來的不算,soft_skip)
        fails.append("comma_short")
    stray = [x for x in m.get("strays") or [] if x["sil"] >= TP.STRAY_MIN and x.get("kind") != "wb"]
    if stray:  # 詞中的多餘停頓:先換 seed 重錄;最後仍有由 fix_strays 剪短(詞邊界的只剪到 STRAY_WB_KEEP,不算未過)
        fails.append("stray_pause")
    m["fails"] = fails
    # 分數(全失敗時取最高):各項違規量加總的負值;句尾相關的違規權重最重
    pen = max(0, abs(m["f0_ratio"] - 1) - a.pitch_tol) + max(0, m["spk_thr"] - m["spk_sim"]) * 2 \
        + max(0, a.sim_min - m["sim"]) + 0.4 * m.get("pron_bad", 0) + (0.3 if m["particle"] else 0) + (0.3 if not m["tail_ok"] else 0) \
        + max(0, 0.6 - m["spc_ratio"], m["spc_ratio"] - 1.6) + sum(0.1 if TP.fixable(p) else 0.4 for p in short) + 0.1 * len(stray) \
        + sum(p for f, p in (("no_cut", 2.0), ("hard_cut", 0.5), ("tail_abrupt", 0.3), ("end_margin", 0.2),
                             ("tail_extra", 0.3)) if f in fails)  # no_cut 的音檔是亂猜切點切出來的,排在最後
    m["score"] = round(-pen, 3)
    return not fails


def _public(m):
    """寫進報告的指標(去掉內部用欄位)。"""
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items() if k != "spc"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs")
    ap.add_argument("--voice", help="seed<N>")
    ap.add_argument("--spk-pt", help="外部音色檔 (.pt),與 --voice 擇一")
    ap.add_argument("--seed", type=int, default=2024, help="取樣基準種子(重試時依序 +1009*k)")
    ap.add_argument("--rate", default="+0%")
    ap.add_argument("--report", help="整批品管報告 JSON 路徑(預設 jobs 同名 .qc.json)")
    ap.add_argument("--asr-model", default=TA.PRIMARY, help="主辨識器 qwen06 | whisper:<size>(舊片重渲染)")
    ap.add_argument("--asr2", default=TA.SECONDARY, help="副辨識器(CPU,通過主品管者不一致重錄,其餘最終音檔只記 asr2_bad);none = 不跑")
    ap.add_argument("--max-retry", type=int, default=8)
    ap.add_argument("--pitch-tol", type=float, default=0.18)
    ap.add_argument("--sim-min", type=float, default=0.85)
    ap.add_argument("--spk-min", type=float, default=0.30, help="聲紋 cosine 絕對下限")
    ap.add_argument("--rate-tol", type=float, default=RATE_TOL, help="語速與整批中位數相差超過此比例就換 seed")
    ap.add_argument("--rate-seeds", type=int, default=RATE_SEEDS, help="語速重錄最多再試幾個 seed")
    ap.add_argument("--spk-k", type=float, default=2.5, help="聲紋門檻 = 依長度迴歸值 - k * 穩健 sigma")
    ap.add_argument("--comma-profile", choices=sorted(TP.PROFILES), default="std",
                    help="逗號停頓側寫:std = 現行(預設);long = 長句逗號停頓較長(僅供本機 A/B 試聽)")
    ap.add_argument("--no-qc", action="store_true", help="不做品管也不加犧牲尾綴(句尾可能被截斷,僅供試聽)")
    a = ap.parse_args()
    if not a.voice and not a.spk_pt:
        sys.exit("--voice 與 --spk-pt 需擇一")
    if not a.spk_pt:  # 給了 --spk-pt 時以音色檔為準,--voice 僅作標籤(build.py 一律會傳 --voice)
        m = re.fullmatch(r"seed(\d+)", a.voice)
        if not m:
            sys.exit("--voice 需為 seed<N>")
        a.seed = int(m.group(1))
    jobs = json.load(open(a.jobs, encoding="utf-8"))
    report = a.report or os.path.splitext(a.jobs)[0] + ".qc.json"
    voice = os.path.basename(a.spk_pt) if a.spk_pt else a.voice  # 音色檔只記檔名:_qc_base.json 與報告不含絕對路徑

    t0 = time.time()
    chat = load_chat()
    spk = load_spk_pt(chat, a.spk_pt) if a.spk_pt else chat.sample_random_speaker()
    qc = None if a.no_qc else QC(a.asr_model, a.spk_min)
    sec = TA.Second(lambda t, h: (lambda d: (d["sim"], d["pron_bad"]))(asr_judge(t, h)), a.sim_min) \
        if qc and a.asr2 != "none" else None
    torch.cuda.reset_peak_memory_stats()
    t_load = time.time() - t0
    t1 = time.time()
    audio_s = 0.0

    if a.no_qc:
        for j in jobs:
            w = synth(chat, prep_text(j["text"]), a.seed, a.rate, spk)
            sf.write(j["out"], w, SR)
            audio_s += len(w) / SR
        print(f"[chattts] no-qc audio={audio_s:.1f}s gen={time.time() - t1:.1f}s", file=sys.stderr)
        return

    calib = [synth(chat, prep_text(t), a.seed + 31 * k, a.rate, spk) for k, t in enumerate(CALIB)]
    calib_sim = qc.set_speaker_base(calib)
    print(f"[chattts] 校正句最高兩句聲紋相似度={calib_sim:.3f}", file=sys.stderr, flush=True)

    # 第一輪:verify 的句子先看既有音檔,其餘直接合成
    res = []
    for k, j in enumerate(jobs):
        if j.get("verify") and os.path.exists(j["out"]):
            w, m = from_cache(qc, j["out"], j["text"])
        else:
            w, m = from_synth(qc, chat, j["text"], a.seed, a.rate, spk)
        res.append(dict(job=j, w=w, m=m, tries=[m]))
        if (k + 1) % 20 == 0:
            print(f"  pass1 {k + 1}/{len(jobs)}", file=sys.stderr, flush=True)

    # 整批基準:句數夠多就用本批並存檔,否則沿用同目錄先前存的
    base_file = os.path.join(os.path.dirname(os.path.abspath(a.jobs)), "_qc_base.json")
    base = None
    if len(jobs) < BASE_MIN and os.path.exists(base_file):
        b = json.load(open(base_file, encoding="utf-8"))
        if (b.get("qc_ver"), b.get("voice"), b.get("rate")) == (QC_VER, voice, a.rate):
            base = b
    if base is None:
        base = dict(qc_ver=QC_VER, voice=voice, rate=a.rate, n=len(jobs),
                    base_f0=statistics.median(r["m"]["f0"] for r in res if r["m"]["f0"] > 0),
                    base_spc=statistics.median(r["m"]["spc"] for r in res), spk_fit=list(fit_spk(res)))
        if len(jobs) >= BASE_MIN:
            json.dump(base, open(base_file, "w", encoding="utf-8"), indent=1)
    base_f0, base_spc, fit = base["base_f0"], base["base_spc"], tuple(base["spk_fit"])
    print(f"[chattts] 基準(n={base['n']}): f0={base_f0:.1f} spc={base_spc:.3f} 聲紋 sim~{fit[0]:.3f}+{fit[1]:.3f}*ln(dur), "
          f"穩健sigma={fit[2]:.3f}, 門檻=迴歸-{a.spk_k}sigma(下限{a.spk_min})", file=sys.stderr, flush=True)
    for r in res:
        r["ok"] = check(r["m"], base_f0, base_spc, a, fit)
        if sec and r["ok"]:
            sec.submit(r["m"], r["job"]["text"], qc.to16(r["w"]))  # 副辨識在背景跑,與主品管重試重疊
    n_cache = sum(1 for r in res if r["m"]["source"] == "cache")
    print(f"[chattts] 第一輪: 既有音檔 {n_cache} 句(通過 {sum(1 for r in res if r['ok'] and r['m']['source'] == 'cache')}),"
          f"新合成 {len(res) - n_cache} 句(通過 {sum(1 for r in res if r['ok'] and r['m']['source'] == 'synth')})",
          file=sys.stderr, flush=True)

    # 重試(既有音檔沒過的,從基準 seed 開始合成)
    todo = [r for r in res if not r["ok"]]
    for n, r in enumerate(todo, 1):
        k = 0 if r["m"]["source"] == "cache" else 1
        tries = 0
        while not r["ok"] and tries <= a.max_retry:
            if comma_only(r["m"]) and tries >= TP.COMMA_RETRY:
                break  # 只差句中停頓、而且插入靜音補得起來:不再為它多錄
            if tries < a.max_retry:
                w, m = from_synth(qc, chat, r["job"]["text"], a.seed + 1009 * k, a.rate, spk)
            elif r["tries"][0]["source"] == "cache":
                break  # 既有音檔就是不加尾綴的版本,已經在候選裡
            else:      # 加尾綴全數失敗:補一個不加尾綴的版本一起比
                w, m = from_plain(qc, chat, r["job"]["text"], a.seed, a.rate, spk)
            ok = check(m, base_f0, base_spc, a, fit)
            r["tries"].append(m)
            if ok or m["score"] > r["m"]["score"]:
                r["w"], r["m"] = w, m
            r["ok"] = ok
            k += 1
            tries += 1
        if n % 20 == 0:
            print(f"  retry {n}/{len(todo)}", file=sys.stderr, flush=True)

    # 雙辨識:通過主品管的音檔再給副辨識器(Fun-ASR-Nano)聽,不一致就重錄(計入 --max-retry),仍不一致記 asr2_bad
    def retry2(r):
        used = {t.get("seed") for t in r["tries"]}
        k = 1
        while a.seed + 1009 * k in used:
            k += 1
        w, m = from_synth(qc, chat, r["job"]["text"], a.seed + 1009 * k, a.rate, spk)
        return w, m, check(m, base_f0, base_spc, a, fit)

    text_of, wav16 = (lambda r: r["job"]["text"]), qc.to16
    if sec:
        n2, bad2 = TA.dual_phase(res, sec, retry2, a.max_retry, text_of, wav16)
        print(f"[chattts] 副辨識 {sec.name}:因不一致重錄 {n2} 次,仍不一致 {bad2} 句", file=sys.stderr, flush=True)

    # 語速品管:基準 = 整批最終音檔的中位數(句數 >= BASE_MIN 時存回 _qc_base.json,小批次沿用)
    cps_med = base.get("base_cps")
    if cps_med is None or len(jobs) >= BASE_MIN:
        cps_med = statistics.median(r["m"]["cps"] for r in res)
        base["base_cps"] = cps_med
        if len(jobs) >= BASE_MIN:
            json.dump(base, open(base_file, "w", encoding="utf-8"), indent=1)
    dev = lambda m: m["cps"] / cps_med - 1
    out_of_range = [r for r in res if abs(dev(r["m"])) > a.rate_tol]
    print(f"[chattts] 語速中位數 {cps_med:.3f} 字/有聲秒;超出 ±{a.rate_tol:.0%} 的單位 {len(out_of_range)}/{len(res)}",
          file=sys.stderr, flush=True)
    for n, r in enumerate(out_of_range, 1):
        text = r["job"]["text"]
        tried = {t["seed"] for t in r["tries"] if t.get("seed") is not None}
        d0 = dev(r["m"])
        cands = [(abs(dev(r["m"])), r["m"], r["w"])] if r["ok"] or comma_only(r["m"]) else []
        r["rate_tries"] = [dict(seed=r["m"].get("seed"), cps=r["m"]["cps"], dev=round(dev(r["m"]), 3), ok=r["ok"], start=True)]
        k, new = 0, 0
        while new < a.rate_seeds and not (cands and min(c[0] for c in cands) <= a.rate_tol / 2):
            k += 1
            seed = a.seed + 1009 * k
            if seed in tried:
                continue
            new += 1
            w, m = from_synth(qc, chat, text, seed, a.rate, spk)
            ok = check(m, base_f0, base_spc, a, fit)
            r["tries"].append(m)
            r["rate_tries"].append(dict(seed=seed, cps=m["cps"], dev=round(dev(m), 3), ok=ok, fails=m["fails"]))
            if ok or comma_only(m):
                cands.append((abs(dev(m)), m, w))
        if cands:  # 先取語速在容許內的,其次是句中停頓不必補的,再取最接近中位數的
            _, m, w = min(cands, key=lambda c: (c[0] > a.rate_tol, bool(c[1]["fails"]), c[0]))
            r["w"], r["m"], r["ok"] = w, m, not m["fails"]
        print(f"  rate {n}/{len(out_of_range)}: {r['job'].get('idx')} {d0:+.0%}"
              f" -> {dev(r['m']):+.0%} (新 seed {new})", file=sys.stderr, flush=True)

    # 最終音檔的後處理;修過的重新辨識、重新量測,之後寫出的語速、句尾、say_t 都以處理後的音檔為準。
    # 1 句中停頓補/剪  2 非標點處的多餘停頓剪短  3 句中停頓內部與句尾靜音區的雜音換成數位靜音
    def remeasure(r, w2):
        """回傳 (波形, 新指標, 處理後才冒出來的品管未過項);有冒出來的就退回未處理的音檔。"""
        w2, mm = measure(qc, w2, r["job"]["text"])
        m2 = dict(r["m"], **{k: v for k, v in mm.items() if k != "no_cut"})
        check(m2, base_f0, base_spc, a, fit)
        return w2, m2, [f for f in m2["fails"] if f not in r["m"]["fails"] and f not in POST_FIXABLE]

    for r in res:
        m = r["m"]
        ps = m.get("pauses") or []
        if TP.out_of_range(ps, r["job"]["text"], a.comma_profile):
            w2, acts = TP.fix_pauses(r["w"], SR, ps, r["job"]["text"], a.comma_profile, std_target=TP.COMMA_TARGET_CHATTTS)
            if acts:
                w2, m2, worse = remeasure(r, w2)
                if worse or len(m2["pauses"]) != len(ps):
                    m["pause_fix_reverted"] = worse or ["pauses"]   # 修完反而別項不過:退回未修的音檔
                else:
                    m2["pause_fix"] = [dict(at=p["at"], act=acts.get(p["i"], "none"), before=p["sil"], after=q["sil"])
                                       for p, q in zip(ps, m2["pauses"])]
                    r["w"], r["m"], m = w2, m2, m2
        ss = m.get("strays") or []
        if ss:
            w2, n_cut = TP.fix_strays(r["w"], SR, ss)
            if n_cut:
                w2, m2, worse = remeasure(r, w2)
                if worse or len(m2["pauses"]) != len(m["pauses"]):
                    m["stray_fix_reverted"] = worse or ["pauses"]
                else:
                    m2["stray_fix"] = [dict(at=x["at"], kind=x.get("kind"), before=x["sil"], after=TP.stray_keep(x))
                                       for x in ss]
                    r["w"], r["m"], m = w2, m2, m2
        w2, plog = TP.clean_pauses(r["w"], SR, m.get("pauses") or [])
        w2, tail_ms = TP.clean_tail(w2, SR)
        if plog or tail_ms:
            w2, m2, worse = remeasure(r, w2)
            if worse or len(m2["pauses"]) != len(m["pauses"]):
                m["clean_reverted"] = worse or ["pauses"]
            else:
                m2["pause_clean"] = plog
                if tail_ms:
                    m2["tail_clean_ms"] = tail_ms
                r["w"], r["m"], m = w2, m2, m2
        bad = TP.comma_bad(m.get("pauses") or [], r["job"]["text"], a.comma_profile)
        if bad:  # 沒有能量低谷可補(兩字連音)或補了仍不足:列入品管未過,請使用者優先聽
            m["comma_bad"] = bad
            m["fails"] = [f for f in m["fails"] if f != "comma_short"] + ["comma_bad"]
        r["ok"] = not m["fails"]

    if sec:
        TA.final_check(res, sec, text_of, wav16)
    lines = []
    for r in res:
        j, m = r["job"], r["m"]
        m["rate_med"] = round(cps_med, 3)
        m["rate_dev"] = round(dev(m), 3)
        m["rate_ok"] = abs(dev(m)) <= a.rate_tol
        m["rate_retried"] = len(r.get("rate_tries", [])) - 1 if r.get("rate_tries") else 0
        sf.write(j["out"], r["w"], SR)
        audio_s += len(r["w"]) / SR
        rec = dict(qc_ver=QC_VER, idx=j.get("idx"), text=j["text"], passed=r["ok"], retries=len(r["tries"]) - 1,
                   final=True, wav_sha1=hashlib.sha1(open(j["out"], "rb").read()).hexdigest())
        rec.update(_public(m))
        rec["comma_profile"] = a.comma_profile
        rec.update(asr_engine=qc.asr_engine, asr2_engine=sec.name if sec else None, **TA.fields(m))
        if r.get("rate_tries"):
            rec["rate_tries"] = r["rate_tries"]
        rec["attempts"] = [dict(source=x["source"], seed=x["seed"], fails=x["fails"], score=x["score"], sim=x["sim"],
                                spk_sim=x["spk_sim"], f0_ratio=x["f0_ratio"], quiet_ms=x["quiet_ms"],
                                tail40_db=x["tail40_db"], asr=x["asr"], comma=[p["sil"] for p in x.get("pauses") or []],
                                stray=[p["sil"] for p in x.get("strays") or []],
                                why=(x.get("cut") or {}).get("why")) for x in r["tries"]]
        json.dump(rec, open(os.path.splitext(j["out"])[0] + ".qc.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        lines.append(rec)
    qc.close()
    if sec:
        sec.close()
    kept = [x["idx"] for x in lines if x["source"] == "cache"]  # 其餘為重錄(synth = 加尾綴,plain = 不加尾綴的備援)
    failed = [x["idx"] for x in lines if not x["passed"]]
    json.dump(dict(qc_ver=QC_VER, voice=voice, rate=a.rate, sacrifice=SACRIFICE, base=base, calib_pair_sim=calib_sim,
                   thresholds=dict(pitch_tol=a.pitch_tol, sim_min=a.sim_min, spk_min=a.spk_min, spk_k=a.spk_k,
                                   min_tail_quiet=MIN_TAIL_QUIET, end_margin_ms=END_MARGIN_MS,
                                   tail_extra_ms=TAIL_EXTRA_MS, min_gap=MIN_GAP, comma_min=TP.COMMA_MIN,
                                   comma_max=TP.COMMA_MAX, comma_target=TP.COMMA_TARGET_CHATTTS, comma_mark=COMMA_MARK,
                                   comma_profile=a.comma_profile,
                                   stray_min=TP.STRAY_MIN, stray_trim_min=TP.STRAY_TRIM_MIN, stray_keep=TP.STRAY_KEEP,
                                   pause_edge=TP.PAUSE_EDGE),
                   kept_from_cache=len(kept), rerecorded=len(lines) - len(kept), failed=failed, lines=lines),
              open(report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    t_gen = time.time() - t1
    peak = torch.cuda.max_memory_reserved() / 2**20
    print(f"[chattts] qc 沿用既有音檔={len(kept)} 重錄={len(lines) - len(kept)} 未通過={failed} "
          f"load={t_load:.1f}s gen={t_gen:.1f}s audio={audio_s:.1f}s rtf={t_gen / max(audio_s, 1e-6):.2f} "
          f"peakVRAM(torch reserved)={peak:.0f}MB report={report}", file=sys.stderr)


if __name__ == "__main__":
    main()
