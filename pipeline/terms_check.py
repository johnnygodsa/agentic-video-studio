#!/usr/bin/env python3
r"""英文詞判斷的單一來源(Phase 3,介面見 docs\director_ab.md §8)。
原本 tts_terms / tts_script / decide_list / tts_c0 / tts_cosy_text.unverified / tts_term_qc 各判一次「這句有哪些英文詞、登錄了沒、驗證了沒」,收在這裡:
  analyze(texts, terms=None)   say_terms.json 版(ChatTTS;原 tts_terms.analyze):unapplied / unregistered / direct
  unregistered(texts)          cosy_terms.json 版(預設引擎):送配音文字裡 cosy_terms 與 _direct 都沒有的英文詞(依首見順序)
  unregistered_by_line(texts)  同上,{行號: [詞]}
  registered_unverified(text)  這句用到、在 cosy_terms(含 _direct)有登錄但不在 _verified 的英文詞(decide_list ①、tts_cosy_text.unverified)
  direct_open(texts)           未驗證且仍直送英文的詞 {詞: [行號]}(tts_script 未決/警告、tts_c0 英文風險、tts_term_qc.direct_open 轉呼叫)
tts_cosy3 的 term_misread / term_inconsistent 是品管層(辨識結果比對),不在這裡,只共用 still_en。
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TERMS_FILE = HERE / "say_terms.json"
_W = r"[A-Za-z0-9][A-Za-z0-9.&'\-]*"
TOKEN_RE = re.compile(_W + r"(?: " + _W + r")*")
MASK = "\x00"


def _ct():
    import tts_cosy_text as CT   # 延後載入:ChatTTS 版 analyze 不需要 cosy 表
    return CT


# ------------------------------------------------------------ say_terms.json 版(ChatTTS)
def load_terms(path=TERMS_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))["terms"]


def is_latin(term):
    return bool(re.fullmatch(r"[A-Za-z0-9.&'\- ]+", term)) and re.search(r"[A-Za-z]", term) is not None


def _pat(term):
    """拉丁詞要求前後不是英數(避免 CA 命中 CAD);非拉丁詞純子字串。"""
    if is_latin(term):
        return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])")
    return re.compile(re.escape(term))


def _mask(text, pat):
    return pat.sub(lambda m: MASK * len(m.group(0)), text)


def analyze(texts, terms=None):
    """texts = 送配音的文字 list(第 i 個 = 第 i+1 句);terms 不給 = 讀 say_terms.json。回傳 dict:unapplied / unregistered / direct。"""
    terms = load_terms() if terms is None else terms
    by_len = sorted(terms, key=lambda t: -len(t["term"]))
    pats = [(t, _pat(t["term"])) for t in by_len]
    say_pats = [re.compile(re.escape(t["say"])) for t in by_len if t.get("say") and re.search(r"[A-Za-z]", t["say"])]
    unapplied, unreg, direct = {}, {}, {}
    for i, raw in enumerate(texts, 1):
        text = raw or ""
        for sp in say_pats:  # 已套用的唸法(如 C.A.、Xbox 三六零)先遮掉
            text = _mask(text, sp)
        for t, p in pats:
            if not p.search(text):
                continue
            bucket = direct if t.get("say") is None else unapplied
            e = bucket.setdefault(t["term"], {"say": t.get("say"), "lines": []})
            e["lines"].append(i)
            text = _mask(text, p)
        for m in TOKEN_RE.finditer(text):
            tok = m.group(0).rstrip(".-'")
            if not re.search(r"[A-Za-z]", tok):
                continue
            e = unreg.setdefault(tok, {"lines": []})
            if i not in e["lines"]:
                e["lines"].append(i)
    return {"unapplied": unapplied, "unregistered": unreg, "direct": direct}


# ------------------------------------------------------------ cosy_terms.json 版(預設引擎)
def analyze_cosy(texts):
    """同 analyze 的回傳格式,對照 cosy_terms.json(寫法由引擎自動套,unapplied 恆空)。"""
    return _ct().analyze(texts)


def unregistered(texts):
    """cosy 引擎:送配音文字(@say 後)裡沒登錄的英文詞,依首見順序。"""
    return list(analyze_cosy(texts)["unregistered"])


def unregistered_by_line(texts):
    """同 unregistered,{行號(從 1): [詞]}。"""
    out = {}
    for w, e in analyze_cosy(texts)["unregistered"].items():
        for i in e["lines"]:
            out.setdefault(i, []).append(w)
    return out


def registered_unverified(text):
    """這句用到的、cosy_terms(含 _direct)有登錄但不在 _verified 的英文詞(順序 = TERMS 再 DIRECT)。text 為含 @say 的原文。"""
    CT = _ct()
    t = CT.unsay(text or "")
    return [w for w in list(CT.TERMS) + list(CT.DIRECT) if w not in CT.TERMS_VERIFIED and CT._word_re(w).search(t)]


def still_en(w):
    """送引擎仍是英文:_direct 的詞若 cosy_terms 另有寫法,以寫法為準(寫法沒有英文字母就不算)。"""
    return re.search(r"[A-Za-z]", _ct().TERMS.get(w, w)) is not None


def direct_open(texts):
    """texts = 送配音文字 list(第 i 個 = 第 i+1 行)。回傳 {詞: [行號]}:在 _direct、不在 _verified、2 字元以上
    (單一字母唸字母本身,不列)。行數 >= tts_term_qc.OPEN_MIN = 未決,1 行 = 警告。"""
    CT = _ct()
    return {w: e["lines"] for w, e in CT.analyze(texts)["direct"].items()
            if w not in CT.TERMS_VERIFIED and len(w) >= 2 and still_en(w)}
