"""共用斷詞層(T2,2026-10-27):字幕拆段(build._cut_reasons)、直式動畫換行(build._wrap_toks)、閱讀卡/anim_web(text_wrap.card_cut)共用。
- 選擇:`seg.set_seg("jieba"|"ckip")`(build.py --seg)或環境變數 CV_SEG;預設 jieba。ckip 沒裝或模型載入失敗 -> 印警告退回 jieba。
- 介面:`segmenter(name=None)` -> 斷詞器(.name / .cut(text) / .prefetch(texts)),`cut` 傳入**原文**(繁體),回傳詞清單且 "".join == 原文;全不可用回傳 None。
- jieba:詞典是簡體,先逐字轉簡體斷詞、再依長度切回原字;`sub_words.txt` 以 add_word 加入(同舊作法,輸出不變)。
- ckip(ckip-transformers,台灣繁體訓練,直接吃繁體;CPU 跑):套件沒有自訂詞典功能,`sub_words.txt` 以後處理併詞
  (落在詞表詞內部的斷點一律移除;詞表詞兩端若與 ckip 詞界不合就不動,與 jieba 的 `inside` 檢查語意一致)。模型用 CV_CKIP_MODEL(albert-tiny|albert-base|bert-base,預設 bert-base),
  固定 CPU(device=-1,不佔顯示卡、不需 gpu_lock)。
- 跨界字串檢查(build._cross_word)查的是 jieba 詞典詞頻,與選哪個斷詞器無關(它是「詞典」不是「斷詞器」)。
- 每片詞表(2026-10-29,channel/_archive/plans/PLAN_流程嚴謹化_2026-10-29.md §4.2):`set_tag(tag)` 載入 `build/<tag>/words.txt`(tts_script.py 產),併在 sub_words 之後;
  沒有這個檔 = 行為與舊版一字不差(已凍結片不產 words.txt)。一個行程只設一次(jieba 加過的詞無法移除)。
  有 words.txt 時(2026-10-29)另讀 `projects/<tag>/spec.json` 的 tw_names(鍵與 tw 值,值含冒號/空白再拆片),並開啟片語模式
  (`phrase_mode()`:build._split_long 用片語評分選切點);沒有 words.txt = 兩者都不做。
"""
import json
import re
import os
import time
from pathlib import Path

ENV_SEG = "CV_SEG"
ENV_CKIP_MODEL = "CV_CKIP_MODEL"
NAMES = ("jieba", "ckip")
SUB_WORDS_FILE = Path(__file__).with_name("sub_words.txt")   # 專案自訂詞表(一行一詞):字幕拆段不可切開的詞

_name = None          # set_seg 指定的名稱;None = 看環境變數
_SUB_WORDS = None
_TAG_WORDS = []       # set_tag 載入的每片詞表(不含已在 sub_words.txt 的);空 = 舊行為
_PHRASE = False       # 片語模式(有每片詞表才開;set_phrase 可強制,測試用)
_T2S = None           # None=未載入, False=不可用, 否則為 opencc 轉換器
_JIEBA = None         # None=未載入, False=不可用, 否則 jieba 模組
_OBJS = {}            # 名稱 -> 斷詞器(含失敗的 None)
_WARNED = set()
STATS = {"ckip_load_s": 0.0}


def _warn(key, msg):
    if key not in _WARNED:
        _WARNED.add(key)
        print(f"[warn] {msg}")


def set_seg(name):
    """指定預設斷詞器(None = 看環境變數 / jieba)。"""
    global _name
    if name is not None and name not in NAMES:
        raise ValueError(f"--seg 只能是 {'|'.join(NAMES)}: {name}")
    _name = name


def seg_name():
    """要求的斷詞器名稱(未必可用;實際可用的看 segmenter().name)。"""
    n = _name or os.environ.get(ENV_SEG, "").strip().lower() or "jieba"
    if n not in NAMES:
        _warn("badseg", f"{ENV_SEG}={n} 不認得(只有 {'|'.join(NAMES)}),改用 jieba")
        return "jieba"
    return n


def sub_words():
    global _SUB_WORDS
    if _SUB_WORDS is None:
        _SUB_WORDS = []
        if SUB_WORDS_FILE.exists():
            _SUB_WORDS = _read_words(SUB_WORDS_FILE)
    return _SUB_WORDS + _TAG_WORDS if _TAG_WORDS else _SUB_WORDS


def _read_words(path):
    return [w.strip() for w in Path(path).read_text(encoding="utf-8").splitlines() if w.strip() and not w.startswith("#")]


def tag_words_file(tag):
    import paths as P
    return P.build_dir(tag) / "words.txt"


def phrase_mode():
    """片語模式:字幕拆段在合法切點上加片語評分(build._phrase_score)。"""
    return _PHRASE


def set_phrase(on):
    global _PHRASE
    _PHRASE = bool(on)


def tw_name_words(tag):
    """projects/<tag>/spec.json 的 tw_names:鍵與 tw 值(含冒號/空白的再拆片);中文 2–8 字、英文 2–24 字元。"""
    import paths as P
    f = P.PROJECTS / tag / "spec.json" if tag else None
    if f is None or not f.exists():
        return []
    try:
        tw = json.loads(f.read_text(encoding="utf-8")).get("tw_names") or {}
    except Exception:  # noqa: BLE001
        return []
    out = []
    for k, v in (tw.items() if isinstance(tw, dict) else ((x, None) for x in tw)):
        name = v.get("tw") if isinstance(v, dict) else v
        for x in [k, name] + re.split(r"[,、;/|:：,\s]+", name or ""):
            x = (x or "").strip()
            if x and (2 <= len(x) <= 8 if re.search(r"[㐀-鿿]", x) else 2 <= len(x) <= 24):
                out.append(x)
    return out


def set_tag(tag, path=None):
    """載入每片詞表(path 預設 build/<tag>/words.txt)+ spec.json tw_names,並開片語模式;檔案不存在 = 不動。回傳新加入的詞數。"""
    global _TAG_WORDS, _PHRASE
    f = Path(path) if path else (tag_words_file(tag) if tag else None)
    if f is None or not f.exists():
        return 0
    _PHRASE = True
    base = set(sub_words())
    new = [w for w in dict.fromkeys(_read_words(f) + tw_name_words(tag)) if w not in base]
    _TAG_WORDS = _TAG_WORDS + new
    if _JIEBA:                       # jieba 已載入:補加;未載入則 jieba_module() 載入時一起加
        for w in new:
            _JIEBA.add_word(simp(w))
    for o in _OBJS.values():         # ckip 快取作廢(併詞表變了)
        if o is not None:
            o._cache.clear()
    return len(new)


def simp(text):
    """jieba 內建詞典是簡體,繁體直接丟進去會斷錯(人事部/門):斷詞與查詞典前先逐字轉簡體;長度變了或 opencc 不可用就用原字。"""
    global _T2S
    if _T2S is None:
        try:
            from opencc import OpenCC
            _T2S = OpenCC("t2s")
        except Exception as e:  # noqa: BLE001
            _T2S = False
            print(f"[warn] opencc 不可用,字幕斷詞直接用繁體(準確度較差): {e}")
    out = _T2S.convert(text) if _T2S else text
    return out if len(out) == len(text) else text


def jieba_module():
    """jieba 模組(已加入 sub_words);不可用回傳 None。"""
    global _JIEBA
    if _JIEBA is None:
        try:
            import logging
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                import jieba
            jieba.setLogLevel(logging.WARNING)
            for w in sub_words():
                jieba.add_word(simp(w))
            _JIEBA = jieba
        except Exception as e:  # noqa: BLE001
            _JIEBA = False
            print(f"[warn] jieba 不可用,字幕斷句退回逐字切: {e}")
    return _JIEBA or None


class JiebaSeg:
    name = "jieba"

    def cut(self, text):
        jb = jieba_module()
        out, pos = [], 0
        for w in jb.cut(simp(text), HMM=True):
            out.append(text[pos:pos + len(w)])
            pos += len(w)
        return out

    def prefetch(self, texts):
        return None


def merge_sub_words(text, words, sub_words_list):
    """後處理併詞:移除落在 sub_words 詞內部的斷點(詞兩端不動)。words 的 join 必須等於 text。"""
    if not sub_words_list or len(words) < 2:
        return list(words)
    bounds, p = set(), 0
    for w in words[:-1]:
        p += len(w)
        bounds.add(p)
    for sw in sub_words_list:
        i = text.find(sw)
        while i >= 0:
            bounds.difference_update(range(i + 1, i + len(sw)))
            i = text.find(sw, i + 1)
    cuts = [0] + sorted(bounds) + [len(text)]
    return [text[a:b] for a, b in zip(cuts, cuts[1:])]


def align_words(text, words):
    """把斷詞器回傳的詞對回原文(模型可能吃掉空白):回傳 join == text 的詞清單,對不上回傳 None。空白併入前一個詞的尾端(開頭的空白併入第一個詞)。"""
    if "".join(words) == text:
        return list(words)
    out, pos = [], 0
    for w in words:
        start = pos
        for ch in w:
            if ch.isspace():
                continue
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if pos >= len(text) or text[pos] != ch:
                return None
            pos += 1
        while pos < len(text) and text[pos].isspace():      # 詞後的空白算前詞尾端
            pos += 1
        if pos > start:
            out.append(text[start:pos])
    if pos < len(text):
        return None
    return out


class CkipSeg:
    """ckip-transformers 斷詞器。`ws` 可注入(測試用假物件):ws(list[str]) -> list[list[str]]。"""
    name = "ckip"

    def __init__(self, ws=None, sub_words_list=None, batch_size=64):
        self._ws = ws
        self._sw = sub_words_list
        self._bs = batch_size
        self._cache = {}
        self.fallback_calls = 0     # 對不回原文而退回 jieba 的次數
        self.calls = 0              # 實際送進模型的句數

    def _words(self):
        return sub_words() if self._sw is None else self._sw

    def _run(self, texts):
        self.calls += len(texts)
        res = self._ws(texts, use_delim=False, batch_size=self._bs, show_progress=False)
        return [list(r) for r in res]

    def prefetch(self, texts):
        """批次送模型(比逐句快很多);已有快取的略過。"""
        todo = [t for t in dict.fromkeys(texts) if t and t not in self._cache]
        if not todo:
            return
        for t, ws in zip(todo, self._run(todo)):
            self._store(t, ws)

    def _store(self, text, raw):
        words = align_words(text, raw)
        if words is None:
            self.fallback_calls += 1
            _warn("ckipalign", "ckip 斷詞結果對不回原文,該句退回 jieba")
            jb = jieba_module()
            words = JiebaSeg().cut(text) if jb else list(text)
        self._cache[text] = merge_sub_words(text, words, self._words())

    def cut(self, text):
        if not text:
            return []
        if text not in self._cache:
            self.prefetch([text])
        return list(self._cache[text])


def _load_ckip():
    """載入 ckip 斷詞器;失敗(沒裝、模型下不到)印警告回傳 None。"""
    t0 = time.process_time()
    try:
        from ckip_transformers.nlp import CkipWordSegmenter
        model = os.environ.get(ENV_CKIP_MODEL, "").strip() or "bert-base"
        ws = CkipWordSegmenter(model=model, device=-1)
    except Exception as e:  # noqa: BLE001
        _warn("ckipload", f"ckip 斷詞不可用,退回 jieba(要先 pip install ckip-transformers,首次載入需連 HuggingFace 下載模型): {type(e).__name__}: {e}")
        return None
    STATS["ckip_load_s"] = time.process_time() - t0
    return CkipSeg(ws)


def segmenter(name=None):
    """回傳斷詞器;ckip 不可用退回 jieba;jieba 也不可用回傳 None。"""
    n = name or seg_name()
    if n == "ckip":
        if "ckip" not in _OBJS:
            _OBJS["ckip"] = _load_ckip()
        if _OBJS["ckip"] is not None:
            return _OBJS["ckip"]
    return JIEBA_SEG if jieba_module() else None


JIEBA_SEG = JiebaSeg()
