r"""比武語料:最近 5 支片 build\<tag>\tts_qc.json 各取 60 句(優先品管未過、使用者聽審改過的句),共 300 句。

送引擎的文字兩引擎同一份:CosyVoice3 = tts_cosy3.engine_text(tts_cosy_text.unsay(text))(英文寫法、拼音標注、簡體、數字讀法);
IndexTTS2 = 同一份文字,只把 CosyVoice 拼音 token「[zh][ǎng]」換成 IndexTTS 的拼音寫法「ZHANG3」(to_indextts),其餘不動。
「聽審改過」= 句子命中 cosy_pron.json / cosy_terms.json 的 `_verified`(使用者聽審定案的詞)或 HEARD_EXTRA(cosy_pron `_doc` 記載的
聽審改讀音詞);是推估,報告註明。讀音表/引擎文字函式可注入,測試不載 torch。
"""
import json
import random
import re
from pathlib import Path

PER_TAG = 60
N_TAGS = 5
FAIL_MAX = 20     # 每支片最多取幾句品管未過
HEARD_MAX = 20    # 每支片最多取幾句聽審改過
MIN_CHARS = 4     # 量測文字至少幾個漢字
SEED = 20261027
HEARD_EXTRA = ("炸", "跟著", "卡在", "卡住", "卡關", "大幅", "一走進", "一整村")   # cosy_pron _doc 的聽審紀錄(2026-10-18~23)
CLS_ORDER = ("qc_fail", "heard", "plain")
HARD_CLS = ("qc_fail", "poly", "english", "plain")
HARD_SIZE = 80
HARD_QUOTA = {"qc_fail": 0.30, "poly": 0.40, "english": 0.25}   # 各類最多占的比例;不足由總分補
HARD_TAGS = 8

INITIALS = {"b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "j", "q", "x", "zh", "ch", "sh", "r", "z", "c", "s", "y", "w"}
_TONES = {}
for _base, _marks in (("a", "āáǎà"), ("e", "ēéěè"), ("i", "īíǐì"), ("o", "ōóǒò"), ("u", "ūúǔù"), ("v", "ǖǘǚǜ")):
    for _k, _c in enumerate(_marks, 1):
        _TONES[_c] = (_base, _k)
TOKEN_RUN = re.compile(r"(?:\[[^\[\]\s]+\])+")


# ------------------------------------------------------------ 拼音 token -> IndexTTS 寫法
def marked_to_tone3(s):
    """帶調號拼音 -> tone3(ǎng -> ang3、lǜ -> lv4);沒有調號 = 輕聲 5。"""
    out, tone = [], 5
    for c in s:
        if c in _TONES:
            b, tone = _TONES[c]
            out.append(b)
        else:
            out.append("v" if c in "üv" else c)
    return "".join(out) + str(tone)


def token_syllables(run):
    """一串連續 CosyVoice 拼音 token -> 音節 list(聲母 token + 韻母 token 合成一個;零聲母用 [y]/[w] 當聲母)。"""
    toks = re.findall(r"\[([^\[\]\s]+)\]", run)
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t in INITIALS and i + 1 < len(toks) and toks[i + 1] not in INITIALS:
            out.append(t + toks[i + 1])
            i += 2
        else:
            out.append(t)
            i += 1
    return out


def to_indextts(engine_text, upper=True):
    """CosyVoice 送引擎文字 -> IndexTTS2 文字:拼音 token 換成「音節+調號數字」(IndexTTS 前端的拼音控制寫法,例 ZHANG3),其餘不動。
    IndexTTS 前端的拼音寫法以本機 index-tts 版本為準(indextts/utils/front.py 的 PINYIN_TONE_PATTERN),見計畫檔 T1 實作紀錄。"""
    def rep(m):
        s = "".join(marked_to_tone3(x) for x in token_syllables(m.group(0)))
        return s.upper() if upper else s
    return TOKEN_RUN.sub(rep, engine_text)


# ------------------------------------------------------------ 拼音 token -> BreezyVoice 注音標注
ZY_INITIAL = {"b": "ㄅ", "p": "ㄆ", "m": "ㄇ", "f": "ㄈ", "d": "ㄉ", "t": "ㄊ", "n": "ㄋ", "l": "ㄌ", "g": "ㄍ", "k": "ㄎ", "h": "ㄏ",
              "j": "ㄐ", "q": "ㄑ", "x": "ㄒ", "zh": "ㄓ", "ch": "ㄔ", "sh": "ㄕ", "r": "ㄖ", "z": "ㄗ", "c": "ㄘ", "s": "ㄙ"}
ZY_FINAL = {"a": "ㄚ", "o": "ㄛ", "e": "ㄜ", "ê": "ㄝ", "ai": "ㄞ", "ei": "ㄟ", "ao": "ㄠ", "ou": "ㄡ", "an": "ㄢ", "en": "ㄣ", "ang": "ㄤ",
            "eng": "ㄥ", "er": "ㄦ", "i": "ㄧ", "ia": "ㄧㄚ", "io": "ㄧㄛ", "ie": "ㄧㄝ", "iao": "ㄧㄠ", "iu": "ㄧㄡ", "iou": "ㄧㄡ",
            "ian": "ㄧㄢ", "in": "ㄧㄣ", "iang": "ㄧㄤ", "ing": "ㄧㄥ", "iong": "ㄩㄥ", "u": "ㄨ", "ua": "ㄨㄚ", "uo": "ㄨㄛ",
            "uai": "ㄨㄞ", "ui": "ㄨㄟ", "uei": "ㄨㄟ", "uan": "ㄨㄢ", "un": "ㄨㄣ", "uen": "ㄨㄣ", "uang": "ㄨㄤ", "ueng": "ㄨㄥ",
            "ong": "ㄨㄥ", "v": "ㄩ", "ve": "ㄩㄝ", "van": "ㄩㄢ", "vn": "ㄩㄣ"}
ZY_RETROFLEX = {"zh", "ch", "sh", "r", "z", "c", "s"}   # 這些聲母後的 i = 空韻(zhi -> ㄓ)


def _zy_final(ini, fin):
    """聲母(token 的 y/w/空 = 零聲母)+ 韻母(tone3 去聲調,ü 寫 v)-> 注音韻母;對不上回 None。"""
    if ini in ZY_RETROFLEX and fin == "i":
        return ""
    if ini in ("j", "q", "x", "y") and fin.startswith("u"):   # ju/qu/xu/yu:u 實為 ü
        fin = "v" + fin[1:]
    if ini == "y":      # 零聲母 y:i/ü 開頭照原樣(yi、yin、ying、yu…),其餘補 i(ya -> ia、ye -> ie、you -> iou、yong -> iong)
        if not fin.startswith(("i", "v")):
            fin = "ie" if fin == "e" else "i" + fin
    elif ini == "w":    # 零聲母 w:u 開頭照原樣(wu),其餘補 u(wa -> ua、wo -> uo、wei -> uei、wen -> uen、weng -> ueng)
        if not fin.startswith("u"):
            fin = "u" + fin
    return ZY_FINAL.get(fin)


def syllable_to_zhuyin(ini, fin_tone3):
    """ini = 聲母 token 內容(沒有給 ""),fin_tone3 = 韻母 + 調號數字(ang3、v4、e5)-> 「ㄓㄤ3」;對不上回 None。調號數字 1–5(輕聲 5,同 BreezyVoice 的 char2phn)。"""
    if not fin_tone3 or fin_tone3[-1] not in "12345":
        return None
    z = _zy_final(ini, fin_tone3[:-1])
    if z is None:
        return None
    head = "" if ini in ("", "y", "w") else ZY_INITIAL.get(ini)
    return None if head is None else head + z + fin_tone3[-1]


def run_to_zhuyin(run):
    """一個字的標注單位(「[zh][ǎng]」「[ì]」)-> 注音;對不上(非拼音 token、聲母/韻母不在表內)回 None。"""
    toks = re.findall(r"\[([^\[\]\s]+)\]", run)
    if not toks or len(toks) > 2 or "".join(f"[{t}]" for t in toks) != run:
        return None
    if len(toks) == 2:
        if toks[0] not in INITIALS:
            return None
        return syllable_to_zhuyin(toks[0], marked_to_tone3(toks[1]))
    if toks[0] in INITIALS:
        return None
    return syllable_to_zhuyin("", marked_to_tone3(toks[0]))


_UNIT = re.compile(r"(?:\[[^\[\]\s]+\]){1,2}|.", re.S)


def unit_split(value):
    """cosy_pron 標注值(拼音 token 與一般字混合,例「執行[zh][ǎng]」)-> 每個原文字一個單位(拼音單位 = 聲母+韻母 token;一般字 = None)。"""
    out, toks = [], re.findall(r"\[[^\[\]\s]+\]|[^\[\]]", value)
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.startswith("["):
            if t[1:-1] in INITIALS and i + 1 < len(toks) and toks[i + 1].startswith("[") and toks[i + 1][1:-1] not in INITIALS:
                out.append(t + toks[i + 1])
                i += 2
            else:
                out.append(t)
                i += 1
        else:
            out.append(None)
            i += 1
    return out


def annotate_zhuyin(text, marks):
    """text 在位置 marks{位置: 拼音單位} 的字後面加「[:注音]」。-> (標注後文字, 標注數, 對不上的 [(位置, 字, 單位)])。"""
    out, n, bad = [], 0, []
    for i, ch in enumerate(text):
        out.append(ch)
        run = marks.get(i)
        if not run:
            continue
        zy = run_to_zhuyin(run)
        if zy:
            out.append(f"[:{zy}]")
            n += 1
        else:
            bad.append((i, ch, run))
    return "".join(out), n, bad


def span_marks(spans, events):
    """cosy_pron 詞表區段 [(起, 迄, 標注值)] 與規則事件 [(位置, 字, 標注, ...)] -> ({位置: 拼音單位}, [單位數對不上的區段])。
    規則事件在詞表區段之外(tts_cosy_text._live_events 已去掉重疊),直接蓋上;只收拼音 token 的標注。"""
    marks, bad = {}, []
    for s, e, v in spans:
        us = unit_split(v)
        if len(us) != e - s:
            bad.append((s, e, v))
            continue
        marks.update({s + k: u for k, u in enumerate(us) if u})
    for ev in events:
        if "[" in ev[2]:   # 非拼音 token 的換字(著 -> 着,簡體修正)BreezyVoice 不需要,略過
            marks[ev[0]] = ev[2]
    return marks, bad


# ------------------------------------------------------------ BreezyVoice 文字
_END_PUNCT = re.compile(r"[\s。?!？！.，,]+$")
# 句中標點:同 tts_cosy3._norm 的符號處理(引號書名號拿掉、括號/冒號/分號/破折號/刪節號收成逗號),但「、」保留(中文原生的頓號,不必換)
_PUNCT_MAP = {"《": "", "》": "", "「": "", "」": "", "『": "", "』": "", "（": "，", "）": "，", "(": "，", ")": "，", "：": "，", "；": "，",
              ":": "，", ";": "，", "—": "，", "…": "，", "~": "", "～": ""}
_TIDY = re.compile(r"\[:[^\]]*\]|[" + "".join(re.escape(c) for c in _PUNCT_MAP) + "]")
_HALF = re.compile(r"(?<=[^\x00-\x7f]|\])([,!?])")     # 接在中文字(或注音標注)後面的半形逗號/驚嘆/問號 -> 全形(BreezyVoice 訓練文字是全形)
_FULL = {",": "，", "!": "！", "?": "？"}


def tidy_punct(t):
    """BreezyVoice 句中標點整理(「[:注音]」標注原樣保留)。"""
    t = _TIDY.sub(lambda m: m.group(0) if m.group(0).startswith("[:") else _PUNCT_MAP[m.group(0)], t)
    return _HALF.sub(lambda m: _FULL[m.group(1)], t)


def revert_term_annot(text, term_annot):
    """apply_terms 換出的標注 token(TERM_ANNOT,例「藝電」->「[y][ì][d][iàn]」)換回原中文詞 -> (文字, {位置: 拼音單位});BreezyVoice 要保留字本身。"""
    if not term_annot:
        return text, {}
    inv = {tok: key for key, tok in term_annot.items()}
    pat = re.compile("|".join(re.escape(t) for t in sorted(inv, key=len, reverse=True)))
    out, marks, pos, n = [], {}, 0, 0
    for m in pat.finditer(text):
        n += m.start() - pos
        out.append(text[pos:m.start()])
        key = inv[m.group(0)]
        for k, u in enumerate(unit_split(m.group(0))):
            if u:
                marks[n + k] = u
        out.append(key)
        n += len(key)
        pos = m.end()
    out.append(text[pos:])
    return "".join(out), marks


def breezy_text(mtext, source_fn=None, marks_fn=None, term_annot=None):
    """量測文字 -> (breezy 純文字, breezy_ann 標注文字, 標注數, 對不上的 [(位置, 字, 單位)] 或區段)。

    步驟同 tts_cosy3.engine_text 的前半(英文寫法 cosy_terms -> 書名號冒號刪除),但不做拼音 token / 簡體 / 數字讀法(繁體照送,數字交給
    BreezyVoice 自己的前端);句中標點見 tidy_punct;句尾標點收成一個(? ! 保留,其餘 。);「[」「]」拿掉(BreezyVoice 用它標注音)。
    標注 = 讀音表(cosy_pron 詞表)+ 多音字規則(pron_rules)+ 語境讀音記憶命中的位置(tts_cosy_text._word_spans / _live_events,
    在標點整理之前的文字上比對,語境同 cosy3;E1 全標注、「著 -> 着」不帶:後者是簡體,BreezyVoice 前端吃繁體)。
    source_fn(mtext) -> 英文寫法後的文字、marks_fn(text) -> ({位置: 拼音單位}, 區段對不上 list) 可注入(測試)。"""
    import tts_cosy_text as CT
    mtext = re.sub(r"[\[\]]", "", mtext)
    end = mtext.rstrip()[-1:]
    src = source_fn or (lambda m: CT.tts_pron.drop_title_colon(CT.apply_terms(m)))
    ta = CT.TERM_ANNOT if term_annot is None else term_annot
    t, extra = revert_term_annot(src(mtext), ta)
    if marks_fn is None:
        def marks_fn(x):
            spans, _ = CT._word_spans(x)
            return span_marks(spans, CT._live_events(x, spans))
    marks, bad_spans = marks_fn(t)
    marks = {**marks, **extra}   # TERM_ANNOT 的標注(詞已在原位)
    ann, n, bad = annotate_zhuyin(t, {p: u for p, u in marks.items() if p < len(t)})
    tail = "？" if end in "?？" else "！" if end in "!！" else "。"
    plain, ann = (_END_PUNCT.sub("", tidy_punct(x)) + tail for x in (t, ann))
    return plain, ann, n, list(bad) + list(bad_spans)


# ------------------------------------------------------------ 找片、讀紀錄
def load_records(qc_path):
    d = json.loads(Path(qc_path).read_text(encoding="utf-8"))
    return d.get("records") or d.get("lines") or []


def is_cosy3(recs):
    return any(r.get("engine") == "cosy3" for r in recs)


def find_tags(build_dir, n=N_TAGS):
    r"""build\<tag>\tts_qc.json 依修改時間新到舊,只取 cosy3 引擎的片(略過 test_ 開頭)-> [tag]。"""
    cands = []
    for f in Path(build_dir).glob("*/tts_qc.json"):
        tag = f.parent.name
        if tag.startswith(("test_", "_")):
            continue
        try:
            if is_cosy3(load_records(f)):
                cands.append((f.stat().st_mtime, tag))
        except (ValueError, OSError):
            continue
    return [t for _, t in sorted(cands, reverse=True)[:n]]


# ------------------------------------------------------------ 分類與抽樣
def heard_default(text):
    """句子命中使用者聽審定案的讀音/英文寫法(cosy_pron/cosy_terms `_verified`)或 HEARD_EXTRA。"""
    import tts_cosy_text as CT
    m = CT.unsay(text)
    if any(w in m for w in HEARD_EXTRA):
        return True
    return any(k in CT.PRON_VERIFIED for k in CT.pron_hits(text)) or any(k in CT.TERMS_VERIFIED for k in CT.term_hits(text))


def classify(rec, heard_fn):
    if rec.get("passed") is False:
        return "qc_fail"
    if heard_fn(rec.get("text") or ""):
        return "heard"
    return "plain"


def _han(s):
    return len(re.findall(r"[一-鿿]", s))


def sample_tag(tag, recs, heard_fn, unsay_fn, seen, per_tag=PER_TAG, fail_max=FAIL_MAX, heard_max=HEARD_MAX, seed=SEED):
    """一支片抽 per_tag 句:品管未過(<= fail_max)-> 聽審改過(<= heard_max)-> 其餘隨機補滿;量測文字去重(跨片共用 seen)。
    -> [dict(tag, idx, text, mtext, cls, prod_passed, prod_fails, prod_dur)]。"""
    pool = {c: [] for c in CLS_ORDER}
    for r in recs:
        text = r.get("text") or ""
        mtext = r.get("measure_text") or unsay_fn(text)
        if _han(mtext) < MIN_CHARS or mtext in seen:
            continue
        pool[classify(r, heard_fn)].append(dict(tag=tag, idx=r.get("idx"), text=text, mtext=mtext,
                                                prod_passed=r.get("passed"), prod_fails=list(r.get("fails") or []),
                                                prod_dur=r.get("dur")))
    rng = random.Random(f"{seed}:{tag}")
    out, used = [], set()

    def take(lst, k, cls):
        lst = list(lst)
        rng.shuffle(lst)
        for x in lst:
            if len(out) >= per_tag or k <= 0:
                break
            if x["mtext"] in used:
                continue
            out.append(dict(x, cls=cls))
            used.add(x["mtext"])
            k -= 1

    take(pool["qc_fail"], fail_max, "qc_fail")
    take(pool["heard"], heard_max, "heard")
    rest = [x for c in CLS_ORDER for x in pool[c] if x["mtext"] not in used]
    take(rest, per_tag, "fill")
    for x in out:   # 補滿的句子保留原分類資訊(品管未過/聽審超過上限的也可能被抽到)
        if x["cls"] == "fill":
            x["cls"] = "qc_fail" if x["prod_passed"] is False else "heard" if heard_fn(x["text"]) else "plain"
    seen.update(x["mtext"] for x in out)
    return out


def breezy_fields(mtext, fn=None):
    """BreezyVoice 兩個變體的文字欄位:btext(純文字)、bann(加我們的注音標注)、bann_n(標注數)、bann_unmapped(對不上注音的標注)。"""
    t, a, n, bad = (fn or breezy_text)(mtext)
    return dict(btext=t, bann=a, bann_n=n, bann_unmapped=[list(x) for x in bad])


def build_corpus(tag_recs, engine_fn, heard_fn=None, unsay_fn=None, per_tag=PER_TAG, breezy_fn=None, **kw):
    """tag_recs = [(tag, records)] -> items(加 n 編號、engine = CosyVoice 送引擎文字、itext = IndexTTS2 文字;breezy_fn 給了才加 BreezyVoice 欄位)。"""
    heard_fn = heard_fn or heard_default
    if unsay_fn is None:
        import tts_cosy_text as CT
        unsay_fn = CT.unsay
    seen, items = set(), []
    for tag, recs in tag_recs:
        for x in sample_tag(tag, recs, heard_fn, unsay_fn, seen, per_tag=per_tag, **kw):
            eng = engine_fn(x["mtext"])
            extra = breezy_fields(x["mtext"], breezy_fn) if breezy_fn else {}
            items.append(dict(x, n=len(items), engine=eng, itext=to_indextts(eng), **extra))
    return items


# ------------------------------------------------------------ 難句語料(--focus hard)
EN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9.&'\-]*")


def poly_score(rec):
    """多音字難度:讀音表/規則命中數(pron_hits)+ g2pW 第三意見不同意的位置數(g2p_disagree)。"""
    return len(rec.get("pron_hits") or {}) + len(rec.get("g2p_disagree") or [])


def en_score(mtext):
    """英文詞個數(整詞,含縮寫、帶點/連字號的詞)。"""
    return len(EN_WORD.findall(mtext))


def load_qc_dir(qc_dir):
    """逐句 qc 紀錄(build\<tag>\tts_cosy3\<idx>.qc.json 與 sub\)裡品管未過的 -> records。tts_qc.json 是定稿後的結果,常常全過;
    逐句檔留著重錄過程中最後一次沒過的句(例 rc_3days C 段卡住的句),拿來當難句。"""
    out = []
    qc_dir = Path(qc_dir)
    for f in sorted(list(qc_dir.glob("[0-9]*.qc.json")) + list((qc_dir / "sub").glob("[0-9]*.qc.json"))):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if r.get("engine") == "cosy3" and r.get("passed") is False and (r.get("text") or r.get("measure_text")):
            out.append(r)
    return out


def hard_pool(tag_recs, unsay_fn):
    """[(tag, records)](新到舊)-> 難句候選 list(量測文字去重,太短不收;先出現的 tag 優先)。"""
    pool, seen = [], set()
    for rank, (tag, recs) in enumerate(tag_recs):
        for r in recs:
            text = r.get("text") or ""
            mtext = r.get("measure_text") or unsay_fn(text)
            if _han(mtext) < MIN_CHARS or mtext in seen:
                continue
            seen.add(mtext)
            pool.append(dict(tag=tag, idx=r.get("idx"), text=text, mtext=mtext, prod_passed=r.get("passed"),
                             prod_fails=list(r.get("fails") or []), prod_dur=r.get("dur"), rank=rank,
                             fail=r.get("passed") is False, poly=poly_score(r), en=en_score(mtext)))
    return pool


def select_hard(pool, size=HARD_SIZE, quota=None, seed=SEED):
    """難句抽樣 size 句:品管未過(<= 30%,新片優先)-> 多音字命中多(<= 40%,命中數高者優先)-> 英文詞多(<= 25%,>= 2 個詞,多者優先)
    -> 其餘依總分(未過 3 分 + 多音字命中 + 英文詞數)補滿。cls = 入選的類別(補的依最顯著的特徵標)。同 seed 可重現。"""
    quota = dict(HARD_QUOTA, **(quota or {}))
    rng = random.Random(f"{seed}:hard")
    order = list(pool)
    rng.shuffle(order)
    out, used = [], set()

    def take(cands, k, cls):
        for x in cands:
            if len(out) >= size or k <= 0:
                break
            if x["mtext"] in used:
                continue
            out.append(dict(x, cls=cls))
            used.add(x["mtext"])
            k -= 1

    take(sorted((x for x in order if x["fail"]), key=lambda x: x["rank"]), int(size * quota["qc_fail"]), "qc_fail")
    take(sorted((x for x in order if x["poly"] >= 2), key=lambda x: -x["poly"]), int(size * quota["poly"]), "poly")
    take(sorted((x for x in order if x["en"] >= 2), key=lambda x: -x["en"]), int(size * quota["english"]), "english")
    rest = sorted((x for x in order if x["mtext"] not in used), key=lambda x: -(3 * x["fail"] + x["poly"] + x["en"]))
    for x in rest:
        if len(out) >= size:
            break
        out.append(dict(x, cls="qc_fail" if x["fail"] else "poly" if x["poly"] else "english" if x["en"] else "plain"))
    return out


def build_hard(tag_recs, engine_fn, unsay_fn=None, size=HARD_SIZE, breezy_fn=None, **kw):
    """難句語料 items(欄位同 build_corpus;另有 poly、en 分數)。"""
    if unsay_fn is None:
        import tts_cosy_text as CT
        unsay_fn = CT.unsay
    items = []
    for x in select_hard(hard_pool(tag_recs, unsay_fn), size=size, **kw):
        x = {k: v for k, v in x.items() if k not in ("rank", "fail")}
        eng = engine_fn(x["mtext"])
        extra = breezy_fields(x["mtext"], breezy_fn) if breezy_fn else {}
        items.append(dict(x, n=len(items), engine=eng, itext=to_indextts(eng), **extra))
    return items


def stats(items):
    by_tag = {}
    for x in items:
        d = by_tag.setdefault(x["tag"], {})
        d[x["cls"]] = d.get(x["cls"], 0) + 1
    return by_tag


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
