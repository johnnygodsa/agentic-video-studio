#!/usr/bin/env python3
r"""多音字第三意見:g2pW(channel/_archive/plans/PLAN_工具升級_2026-10-26.md T3)。

g2pW = 依上下文判多音字讀音的 BERT 模型(ONNX,CPU 推論)。這支只當「第三意見」:
  - `predict(text)`:對 pron_rules.json 有列的多音字,回 [(位置, 字, 帶調拼音 tone3)];g2pW 不可用回 None(印一次警告,不讓配音失敗)。
  - `disagreements(text)`:g2pW 與「規則表」(cosy_pron 詞表 -> pron_rules 命中 -> 沒命中走 model_default)讀音不一致的位置。
    tts_cosy3 把結果寫進品管紀錄 `g2p_disagree`,listen_page 列入優先聽。**不改送引擎的文字、不改快取鍵、不改 QC_VER/KEY_VER。**
  - `disagreements_many(texts)`:同上的批次版(一次推論);`Background(texts)`:tts_cosy3 用,背景執行緒算完,主流程只在最終紀錄前取結果。
  - 拼音一律正規化成 tone3(`zhang3`;ü -> v,jqxy 後的 v -> u;輕聲 5)。`norm_py` 吃:數字調(hong2)、調號(hóng)、
    注音(ㄏㄨㄥˊ / ㄏㄨㄥ2 / ˙ㄉㄜ)、CosyVoice 標注(`[zh][ǎng]`)。
  - 輕聲寬鬆(`neutral_loose`,預設開):一邊是輕聲(5)而另一邊同音節不同調,不算不一致(送引擎的字沒有控制輕聲,不是我們要抓的錯)。

模型位置(本機,不寫 C 槽):`tts_models\G2PWModel\`(G2PW_MODEL_DIR 可改;要有 `version` 檔,沒有就視為不可用,不會在配音時偷偷下載);
BERT 來源 `tts_models\bert-base-chinese\`(G2PW_BERT_DIR 可改;沒有就用 g2pW 設定檔的名稱走 HuggingFace 快取,HF_HOME 預設導到 tmp\hf_home)。

CLI(tts_env_chattts 的 python):
  python -X utf8 pipeline\tts_g2p.py --download                  一次性:下載 g2pW 模型(需連網;裝完才可用)
  python -X utf8 pipeline\tts_g2p.py --check "他看著遠方發呆"        印這句的 g2pW 預測與規則表差異
  python -X utf8 pipeline\tts_g2p.py --eval [--limit N] [--labels f.tsv] [--out md]   準確率表(說明見 eval_report)
"""
import argparse
import json
import os
import re
import sys
import threading
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paths as P  # noqa: E402
import tts_cosy_text as CT  # noqa: E402

# ------------------------------------------------------------ 拼音 / 注音 -> tone3
_TONE_MARK = {"̄": "1", "́": "2", "̌": "3", "̀": "4"}
_BPM_TONE = {"ˊ": "2", "ˇ": "3", "ˋ": "4", "˙": "5", "ˉ": "1"}
_BPM_INIT = {"ㄅ": "b", "ㄆ": "p", "ㄇ": "m", "ㄈ": "f", "ㄉ": "d", "ㄊ": "t", "ㄋ": "n", "ㄌ": "l", "ㄍ": "g", "ㄎ": "k",
             "ㄏ": "h", "ㄐ": "j", "ㄑ": "q", "ㄒ": "x", "ㄓ": "zh", "ㄔ": "ch", "ㄕ": "sh", "ㄖ": "r", "ㄗ": "z", "ㄘ": "c", "ㄙ": "s"}
_BPM_FINAL = {"ㄚ": "a", "ㄛ": "o", "ㄜ": "e", "ㄝ": "e", "ㄞ": "ai", "ㄟ": "ei", "ㄠ": "ao", "ㄡ": "ou", "ㄢ": "an", "ㄣ": "en",
              "ㄤ": "ang", "ㄥ": "eng", "ㄦ": "er", "ㄧ": "i", "ㄧㄚ": "ia", "ㄧㄛ": "io", "ㄧㄝ": "ie", "ㄧㄞ": "iai", "ㄧㄠ": "iao",
              "ㄧㄡ": "iu", "ㄧㄢ": "ian", "ㄧㄣ": "in", "ㄧㄤ": "iang", "ㄧㄥ": "ing", "ㄨ": "u", "ㄨㄚ": "ua", "ㄨㄛ": "uo",
              "ㄨㄞ": "uai", "ㄨㄟ": "ui", "ㄨㄢ": "uan", "ㄨㄣ": "un", "ㄨㄤ": "uang", "ㄨㄥ": "ong", "ㄩ": "v", "ㄩㄝ": "ve",
              "ㄩㄢ": "van", "ㄩㄣ": "vn", "ㄩㄥ": "iong"}
# 零聲母的拼寫(i 行改 y、u 行改 w、ü 行改 yu)
_ZERO_INIT = {"i": "yi", "ia": "ya", "io": "yo", "ie": "ye", "iai": "yai", "iao": "yao", "iu": "you", "ian": "yan", "in": "yin",
              "iang": "yang", "ing": "ying", "iong": "yong", "u": "wu", "ua": "wa", "uo": "wo", "uai": "wai", "ui": "wei",
              "uan": "wan", "un": "wen", "uang": "wang", "ong": "weng", "v": "yu", "ve": "yue", "van": "yuan", "vn": "yun"}
_RETRO = {"zh", "ch", "sh", "r", "z", "c", "s"}   # 只有聲母的音節(ㄓ = zhi)
_BPM_RE = re.compile(r"[㄀-ㄯㆠ-ㆿ]")


def _bopomofo(s):
    """注音 -> tone3。支援 ˊˇˋ˙(前綴或後綴)與尾端數字 1-5;沒標 = 一聲。解析不了回 None。"""
    tone, body = None, []
    for c in s:
        if c in _BPM_TONE:
            tone = _BPM_TONE[c]
        elif c.isdigit():
            tone = {"0": "5"}.get(c, c)
        elif _BPM_RE.match(c):
            body.append(c)
        elif not c.isspace():
            return None
    body = "".join(body)
    ini = ""
    if body and body[0] in _BPM_INIT:
        ini, body = _BPM_INIT[body[0]], body[1:]
    if not body:
        if ini in _RETRO:
            return f"{ini}i{tone or '1'}"
        return None
    fin = _BPM_FINAL.get(body)
    if fin is None:
        return None
    base = _ZERO_INIT.get(fin, fin) if not ini else ini + fin
    return _fix_v(base) + (tone or "1")


def _fix_v(base):
    """ü:jqxy 後寫 u(ju、xue、yun),其餘保持 v(lv、nve)。"""
    return re.sub(r"^([jqxy])v", r"\1u", base)


def norm_py(s):
    """任何拼音/注音寫法 -> tone3 小寫(zhang3、lv4、xue4;輕聲 5)。解析不了回 None。
    接受:hong2 / hóng / ㄏㄨㄥˊ / ㄏㄨㄥ2 / ˙ㄉㄜ / `[zh][ǎng]`(CosyVoice 標注,無調號 = 輕聲)。"""
    if not s or not isinstance(s, str):
        return None
    s = s.strip().replace("[", "").replace("]", "").lower()
    if not s:
        return None
    if _BPM_RE.search(s):
        return _bopomofo(s)
    tone, out = None, []
    for c in unicodedata.normalize("NFD", s):
        if c in _TONE_MARK:
            tone = _TONE_MARK[c]
        elif c == "̈":          # ü = u + 分音符
            out[-1:] = ["v"]
        elif c.isdigit():
            tone = "5" if c == "0" else c
        elif c == "ü":
            out.append("v")
        elif unicodedata.combining(c):
            continue
        elif c.isalpha() and c.isascii():
            out.append(c)
        else:
            return None
    base = "".join(out)
    if not base or not re.fullmatch(r"[a-z]+", base):
        return None
    return _fix_v(base) + (tone or "5")


def _split(r):
    return r[:-1], r[-1]


def same_reading(a, b, neutral_loose=True):
    """兩個讀音(任何寫法)是否算同一個。neutral_loose:同音節、其中一邊輕聲 -> 算同。任一邊解析不了 -> 視為相同(不亂報)。"""
    a, b = norm_py(a), norm_py(b)
    if a is None or b is None or a == b:
        return True
    (sa, ta), (sb, tb) = _split(a), _split(b)
    return neutral_loose and sa == sb and "5" in (ta, tb)


# ------------------------------------------------------------ 規則表的讀音
_INITS = {"b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "j", "q", "x", "zh", "ch", "sh", "r", "z", "c", "s", "y", "w"}


def _char_reading(c):
    """單一個字的預設讀音(pypinyin);沒裝或查不到回 None。"""
    try:
        from pypinyin import Style, lazy_pinyin
    except ImportError:
        return None
    r = lazy_pinyin(c, style=Style.TONE3, neutral_tone_with_five=True)
    return norm_py(r[0]) if r else None


def mark_reading(py):
    """送引擎的標注 -> tone3:`[zh][ǎng]` 拼起來轉;單一個字(「着」「的」)-> 該字預設讀音。"""
    if not py:
        return None
    if "[" in py:
        return norm_py(py)
    return _char_reading(py) if len(py) == 1 else None


def _syllable_units(ann):
    """cosy_pron 詞表標注字串 -> 每個字的讀音 list:原字保留的位置 None,拼音 token 組 -> tone3。
    token 兩兩成音節(聲母 + 韻母,或單獨的韻母)。"""
    units, toks = [], []

    def flush():
        i = 0
        while i < len(toks):
            if toks[i] in _INITS and i + 1 < len(toks) and toks[i + 1] not in _INITS:
                units.append(norm_py(toks[i] + toks[i + 1]))
                i += 2
            else:
                units.append(norm_py(toks[i]))
                i += 1
        toks.clear()

    for part in CT.TOKEN_RE.split(ann):
        if not part:
            continue
        if CT.TOKEN_RE.fullmatch(part):
            toks.append(part[1:-1])
        else:
            flush()
            units.extend([None] * len(part))
    flush()
    return units


def expected(text):
    """規則表對「規則收的多音字」每個位置給的讀音 -> {位置: (字, tone3, 來源)}。
    來源:pron = cosy_pron 詞表標注;rule = pron_rules 命中(含 always 字的預設標注);default = 沒命中,走該字 model_default。
    詞表區段裡原字保留的位置(讀音交給模型)與查不到讀音的位置不輸出。text = 原文(CT.unsay 後)。"""
    spans, _ = CT._word_spans(text)
    ev = {e[0]: e for e in CT._live_events(text, spans)}
    out = {}
    for s, e, ann in spans:
        units = _syllable_units(ann)
        if len(units) != e - s:
            continue
        for k, u in enumerate(units):
            if u and text[s + k] in CT.RULE_CHARS:
                out[s + k] = (text[s + k], u, "pron")
    covered = {p for s, e, _ in spans for p in range(s, e)}
    for p, ch in enumerate(text):
        if ch not in CT.RULE_CHARS or p in covered:
            continue
        if p in ev:
            rd, src = mark_reading(ev[p][2]), ("default" if ev[p][4] == "default" else "rule")
        else:
            rd, src = mark_reading(CT.RULE_CHARS[ch].get("model_default")), "default"
        if rd:
            out[p] = (ch, rd, src)
    return out


# ------------------------------------------------------------ g2pW 載入(延遲、CPU;不可用回 None)
_CONV = []          # [converter] 或 [None](載入失敗,不重試)
_WARNED = []


def _warn(msg):
    if not _WARNED:
        _WARNED.append(1)
        print(f"[g2p] g2pW 不可用,略過第三意見(配音照常):{msg}", file=sys.stderr)


def model_dir():
    return Path(os.environ.get("G2PW_MODEL_DIR") or P.ROOT / "tts_models" / "G2PWModel")


def _make_converter(allow_download=False):
    """建 g2pW 轉換器(style=pinyin,CPU)。HF_HOME 預設導到 tmp(不寫 C 槽)。"""
    os.environ.setdefault("HF_HOME", str(P.TMP / "hf_home"))
    from g2pw import G2PWConverter
    md = model_dir()
    if not (md / "version").exists() and not allow_download:
        raise FileNotFoundError(f"找不到 g2pW 模型 {md}(先跑 --download)")
    bert = os.environ.get("G2PW_BERT_DIR") or str(P.ROOT / "tts_models" / "bert-base-chinese")
    kw = dict(model_dir=str(md) + os.sep, style="pinyin", num_workers=0, enable_non_tradional_chinese=True)
    if (Path(bert) / "config.json").exists():
        kw["model_source"] = bert
    conv = G2PWConverter(**kw)
    conv.num_workers = 0   # 套件把 0 當沒給、退回設定檔的 2:每次呼叫 spawn 兩個子行程(Windows 重新 import 主程式,逐句呼叫約 5 秒/句的主因)
    return conv


def converter():
    """延遲載入;失敗回 None 並印一次警告。"""
    if not _CONV:
        try:
            _CONV.append(_make_converter())
        except Exception as e:  # noqa: BLE001  任何原因(沒裝、沒模型、被擋)都不能讓配音失敗
            _CONV.append(None)
            _warn(f"{type(e).__name__}: {str(e)[:120]}")
    return _CONV[0]


def set_converter(conv):
    """測試/外部注入預測器:callable(list[str]) -> list[list[str|None]](同 G2PWConverter);None = 重設為未載入。"""
    _CONV.clear()
    _WARNED.clear()
    if conv is not None:
        _CONV.append(conv)


def predict_many(texts, conv=None):
    """-> 每句 [(位置, 字, tone3)](只含 pron_rules 有列的字、且 g2pW 有給讀音);g2pW 不可用或推論失敗回 None。"""
    conv = conv or converter()
    if conv is None:
        return None
    texts = list(texts)
    try:
        res = conv(texts)
    except Exception as e:  # noqa: BLE001
        _warn(f"推論失敗 {type(e).__name__}: {str(e)[:120]}")
        return None
    out = []
    for t, row in zip(texts, res):
        one = []
        for i, ch in enumerate(t):
            if ch in CT.RULE_CHARS and i < len(row):
                py = norm_py(row[i])
                if py:
                    one.append((i, ch, py))
        out.append(one)
    return out


def predict(text, conv=None):
    """一句 -> [(位置, 字, tone3)] 或 None(模型不可用)。位置 = 在傳入文字中的字元索引。"""
    r = predict_many([text], conv)
    return None if r is None else r[0]


def compare(text, preds, neutral_loose=True):
    """規則表 vs g2pW(preds = predict 的輸出,text = 同一份原文)-> 不一致清單 [dict(pos, ch, rule, g2p, src)]。"""
    exp = expected(text)
    return [dict(pos=i, ch=ch, rule=exp[i][1], g2p=py, src=exp[i][2]) for i, ch, py in preds
            if i in exp and not same_reading(exp[i][1], py, neutral_loose)]


def disagreements(text, conv=None, neutral_loose=True):
    """tts_cosy3 用:這句(say 文字)g2pW 與規則表不一致的位置清單([] = 全一致);g2pW 不可用回 None。"""
    t = CT.unsay(text)
    preds = predict(t, conv)
    return None if preds is None else compare(t, preds, neutral_loose)


def disagreements_many(texts, conv=None, neutral_loose=True):
    """批次版 disagreements,一次推論 -> {text: 不一致清單 | None}。g2pW 不可用或推論失敗整批 None;只有比對出錯的那句 None。"""
    texts = list(dict.fromkeys(texts))
    plain = [CT.unsay(t) for t in texts]
    preds = predict_many(plain, conv)
    if preds is None:
        return dict.fromkeys(texts)
    out = {}
    for t, u, p in zip(texts, plain, preds):
        try:
            out[t] = compare(u, p, neutral_loose)
        except Exception as e:  # noqa: BLE001
            print(f"[g2p] 略過「{t[:20]}」: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            out[t] = None
    return out


def record_fields(result, text):
    """品管紀錄要加的欄位:有結果才寫 g2p_disagree([] = 全一致也寫);None(不可用/失敗)不寫。"""
    v = result.get(text)
    return {} if v is None else {"g2p_disagree": v}


class Background:
    """背景執行緒批次算 disagreements_many(結果只依文字,不必擋主流程)。任何例外都吞掉記 log,該批退回沒有結果。
    wait() 取結果:最多等到起算 JOIN_BASE + JOIN_PER_TEXT x 句數 秒,逾時回 {}(daemon 執行緒不擋行程結束,之後算完也不採用)。"""
    JOIN_BASE, JOIN_PER_TEXT = 120.0, 3.0   # 實測含載入約 0.2 秒/句(ally_ai 75 句 12 秒 + 載入 5 秒)

    def __init__(self, texts, log=None, conv=None):
        self.texts = list(dict.fromkeys(texts))
        self.log = log or (lambda m: print(m, file=sys.stderr, flush=True))
        self.res = {}
        self.t0 = time.perf_counter()
        self.deadline = self.t0 + self.JOIN_BASE + self.JOIN_PER_TEXT * len(self.texts)
        self.thread = threading.Thread(target=self._run, args=(conv,), name="g2pw", daemon=True)
        self.thread.start()

    def _run(self, conv):
        try:
            res = disagreements_many(self.texts, conv)
            n = sum(v is not None for v in res.values())
            self.log(f"[g2p] 背景批次 {len(self.texts)} 句 {time.perf_counter() - self.t0:.1f}s,有結果 {n} 句")
            self.res = res
        except Exception as e:  # noqa: BLE001  g2pW 任何問題都不能讓配音失敗
            self.log(f"[g2p] 背景批次失敗,略過第三意見: {type(e).__name__}: {str(e)[:120]}")

    def wait(self):
        """-> {text: 不一致清單 | None};執行緒失敗或逾時回 {}。"""
        self.thread.join(max(0.0, self.deadline - time.perf_counter()))
        if self.thread.is_alive():
            self.log(f"[g2p] 背景批次逾時({time.perf_counter() - self.t0:.0f}s),略過第三意見")
            return {}
        return self.res


# ------------------------------------------------------------ 準確率工具(--eval)
def _verified_keys():
    return set(CT.RULES_RAW.get("_verified", []))


def verified_cases(sentences):
    """已驗證答案 -> [dict(text, pos, ch, ans, src)]。
    a) pron_rules.json `_verified`(使用者聽審 / 語音回查定案的「詞→標注」「字→標注」):句子裡命中這個鍵的位置,答案 = 標注讀音。
    b) cosy_pron.json `_verified` 詞:句子含該詞,詞裡「規則收的多音字」的位置,答案 = 詞表標注讀音。"""
    vk, cases, seen = _verified_keys(), [], set()
    pv = [w for w in CT.PRON_VERIFIED if w in CT.PRON]
    for text in sentences:
        spans, _ = CT._word_spans(text)
        for e in CT._live_events(text, spans):
            if e[3] in vk and (text, e[0]) not in seen:
                rd = mark_reading(e[2])
                if rd:
                    seen.add((text, e[0]))
                    cases.append(dict(text=text, pos=e[0], ch=e[1], ans=rd, src="pron_rules._verified"))
        for s, en, ann in spans:
            if text[s:en] not in pv:
                continue
            units = _syllable_units(ann)
            if len(units) != en - s:
                continue
            for k, u in enumerate(units):
                p = s + k
                if u and text[p] in CT.RULE_CHARS and (text, p) not in seen:
                    seen.add((text, p))
                    cases.append(dict(text=text, pos=p, ch=text[p], ans=u, src="cosy_pron._verified"))
    return cases


def label_cases(path):
    """--labels:TSV `句子<TAB>位置(0 起算)<TAB>正確拼音`(使用者聽審判定的獨立答案)。"""
    cases = []
    for ln in Path(path).read_text(encoding="utf-8-sig").splitlines():
        parts = ln.split("\t")
        if len(parts) < 3 or ln.startswith("#"):
            continue
        text, pos, py = parts[0], int(parts[1]), norm_py(parts[2])
        if py and 0 <= pos < len(text):
            cases.append(dict(text=text, pos=pos, ch=text[pos], ans=py, src="labels"))
    return cases


def corpus_sentences(limit=None):
    """文案語料(所有 <片名>\\script.txt 的句子,tts_pron_verify.corpus 同一套)+ 規則造句(讓每條已驗證規則至少有句子)。"""
    import tts_pron_verify as V
    sents = [m for _tag, m, _s in V.corpus()]
    synth = []
    try:
        items, _rules, _st = V.plan(per_rule=3)
        synth = [it["mtext"] for it in items if it.get("synthetic")]
    except Exception as e:  # noqa: BLE001  造句失敗不擋評估
        print(f"[g2p] 規則造句略過:{e}", file=sys.stderr)
    out = list(dict.fromkeys(sents + synth))
    return out[:limit] if limit else out


def _pct(a, b):
    return f"{a / b:.1%}" if b else "-"


def evaluate(sentences, conv, extra_cases=(), neutral_loose=True):
    """-> dict(preds={句: {位置: tone3}}, cases=[含 g2p/rule 判定], secs, n_sent)。conv 不可用回 None。"""
    t0 = time.perf_counter()
    res = predict_many(sentences, conv)
    secs = time.perf_counter() - t0
    if res is None:
        return None
    preds = {s: {i: py for i, _c, py in r} for s, r in zip(sentences, res)}
    cases = verified_cases(sentences) + list(extra_cases)
    for c in cases:
        ex = expected(c["text"]).get(c["pos"])
        c["rule"] = ex[1] if ex else None
        c["g2p"] = preds.get(c["text"], {}).get(c["pos"])
    return dict(preds=preds, cases=cases, secs=secs, n_sent=len(sentences))


def eval_report(ev, sentences, neutral_loose=True, top=40):
    """markdown 準確率表。三個證據層級分開寫:
    1) 已驗證答案上的 g2pW 準確率(答案來自 `_verified`:詞型規則的答案本來就是規則表的標注 -> 規則表在這組上等於循環論證,
       只有 `--labels` 的獨立聽審答案才能真的比誰對);
    2) 規則表 vs g2pW 不一致時誰對(只算有答案的);
    3) 全語料一致率與不一致清單(沒答案,供人聽審判定後寫回 --labels)。"""
    cases = [c for c in ev["cases"] if c.get("g2p")]
    L = ["# g2pW 第三意見評估", "",
         f"- 句數 {ev['n_sent']},g2pW 推論 {ev['secs']:.1f} 秒({ev['secs'] / max(ev['n_sent'], 1):.3f} 秒/句,"
         f"300 句約 {ev['secs'] / max(ev['n_sent'], 1) * 300:.0f} 秒)。輕聲寬鬆={neutral_loose}。",
         f"- 答案來源:{', '.join(sorted({c['src'] for c in ev['cases']})) or '(無)'};有 g2pW 預測的答案位置 {len(cases)} 個"
         f"(已驗證鍵 {len(_verified_keys())} 條 + cosy_pron 已驗證詞 {len(CT.PRON_VERIFIED)} 個)。", ""]

    def right(rd, ans):
        return rd is not None and same_reading(rd, ans, neutral_loose)

    # 1) g2pW 單獨準確率(依字)
    by = {}
    for c in cases:
        r = by.setdefault(c["ch"], dict(n=0, g=0, rule=0))
        r["n"] += 1
        r["g"] += right(c["g2p"], c["ans"])
        r["rule"] += right(c["rule"], c["ans"])
    n = sum(r["n"] for r in by.values())
    g = sum(r["g"] for r in by.values())
    ru = sum(r["rule"] for r in by.values())
    L += ["## 1. 已驗證答案上的準確率", "", "| 字 | 位置數 | g2pW 對 | g2pW 準確率 | 規則表對 | 規則表準確率 |", "|---|---|---|---|---|---|"]
    for ch, r in sorted(by.items(), key=lambda x: -x[1]["n"]):
        L.append(f"| {ch} | {r['n']} | {r['g']} | {_pct(r['g'], r['n'])} | {r['rule']} | {_pct(r['rule'], r['n'])} |")
    L += [f"| **合計** | {n} | {g} | {_pct(g, n)} | {ru} | {_pct(ru, n)} |", "",
          "證據強度:答案取自 `_verified`(使用者聽審 / 規則定案),詞型規則的答案就是規則表標注,規則表準確率在這組偏高是循環論證,"
          "不可當成效;獨立比較要用 `--labels`(聽審判定的 句子/位置/正確拼音)。", ""]

    # 2) 不一致時誰對
    dis = [c for c in cases if c["rule"] is not None and not same_reading(c["rule"], c["g2p"], neutral_loose)]
    cnt = dict(rule=0, g2p=0, both=0)
    for c in dis:
        rr, gg = right(c["rule"], c["ans"]), right(c["g2p"], c["ans"])
        cnt["rule" if rr else "g2p" if gg else "both"] += 1
    L += ["## 2. 規則表 vs g2pW 不一致時誰對(限有答案的位置)", "", "| 結果 | 次數 |", "|---|---|",
          f"| 規則表對、g2pW 錯 | {cnt['rule']} |", f"| g2pW 對、規則表錯 | {cnt['g2p']} |",
          f"| 兩邊都錯 | {cnt['both']} |", f"| 不一致合計 | {len(dis)} / {len(cases)} |", ""]
    for c in dis[:top]:
        L.append(f"- 「{c['text']}」第 {c['pos']} 字「{c['ch']}」:答案 {c['ans']} / 規則 {c['rule']} / g2pW {c['g2p']}({c['src']})")
    L.append("")

    # 3) 全語料不一致
    allp = {}
    bad = []
    for s in sentences:
        exp = expected(s)
        for i, py in ev["preds"].get(s, {}).items():
            if i not in exp:
                continue
            ch = exp[i][0]
            a = allp.setdefault(ch, [0, 0])
            a[0] += 1
            if not same_reading(exp[i][1], py, neutral_loose):
                a[1] += 1
                bad.append((ch, s, i, exp[i][1], py, exp[i][2]))
    tot, dtot = sum(v[0] for v in allp.values()), sum(v[1] for v in allp.values())
    L += ["## 3. 全語料一致率(沒有答案,只看 g2pW 與規則表是否一致;不一致者需人聽審判定)", "",
          f"規則字位置 {tot} 個,一致 {tot - dtot}({_pct(tot - dtot, tot)}),不一致 {dtot}。", "",
          "| 字 | 位置數 | 不一致 | 不一致率 |", "|---|---|---|---|"]
    for ch, (a, b) in sorted(allp.items(), key=lambda x: -x[1][1])[:top]:
        L.append(f"| {ch} | {a} | {b} | {_pct(b, a)} |")
    L += ["", f"### 不一致清單(前 {top} 筆;聽審判定後可寫成 --labels 的 TSV:句子、位置、正確拼音)", ""]
    for ch, s, i, rd, py, src in bad[:top]:
        L.append(f"- 「{s}」第 {i} 字「{ch}」:規則 {rd}({src})/ g2pW {py}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="g2pW 第三意見(見檔頭說明)")
    ap.add_argument("--download", action="store_true", help="下載 g2pW 模型到 tts_models\\G2PWModel(需連網)")
    ap.add_argument("--check", metavar="TEXT", help="印這句的 g2pW 預測與規則表差異")
    ap.add_argument("--eval", action="store_true", help="準確率工具,輸出 markdown")
    ap.add_argument("--limit", type=int, help="--eval 只取前 N 句語料")
    ap.add_argument("--labels", help="--eval 額外答案 TSV:句子<TAB>位置<TAB>正確拼音")
    ap.add_argument("--strict-neutral", action="store_true", help="輕聲也算不一致(預設寬鬆)")
    ap.add_argument("--out", help="--eval 輸出 md 路徑(預設 tmp\\g2pw_eval_<日期>.md)")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    loose = not a.strict_neutral
    if a.download:
        _make_converter(allow_download=True)
        print(f"g2pW 模型已就緒:{model_dir()}")
    if a.check:
        t = CT.unsay(a.check)
        preds = predict(t)
        if preds is None:
            sys.exit(2)
        exp = expected(t)
        for i, ch, py in preds:
            e = exp.get(i)
            mark = "" if not e or same_reading(e[1], py, loose) else "  <-- 不一致"
            print(f"{i} {ch} g2pW={py} 規則表={e[1] + '(' + e[2] + ')' if e else '-'}{mark}")
    if a.eval:
        conv = converter()
        if conv is None:
            sys.exit(2)
        sents = corpus_sentences(a.limit)
        ev = evaluate(sents, conv, label_cases(a.labels) if a.labels else (), loose)
        if ev is None:
            sys.exit(2)
        md = eval_report(ev, sents, loose)
        out = Path(a.out) if a.out else P.TMP / f"g2pw_eval_{time.strftime('%Y-%m-%d')}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(md[:1500])
        print(f"完整報告:{out}")


if __name__ == "__main__":
    main()
