#!/usr/bin/env python3
r"""CosyVoice3 的文字前處理(只用標準函式庫;tts_cosy3.py 與 tts_terms.py --engine cosy3 共用)。
- 讀音:cosy_pron.json(拼音標注,長詞優先;不走 tts_pron 的同音字替換);pron_rules.json(多音字語境規則,在原文上比對,與詞表標注合併,重疊時詞表贏)。
- 語境讀音記憶:pron_memory.json(pron_memory.py;記憶 > 詞表 > 規則,_word_spans / _live_events 併入;表空或沒有檔案時兩者輸出與無記憶逐位元相同;
  記憶值與原本標注相同時不動,命中鍵不變,快取不失效)。
- 英文:cosy_terms.json(整詞換寫法);script 的 @say 已換成 ChatTTS 寫法的詞先由 unsay 換回原文。
- analyze:配音前英文詞對照(未登錄詞 = 錯誤,由主對話決定後登錄 cosy_terms.json)。
- 讀音變更偵測:pron_changed(.qc.json 紀錄, 文字) -> build.tts_all 讓讀音表改過的句子快取失效重錄(讀音沒變的不動)。
單獨執行:python -X utf8 pipeline/tts_cosy_text.py --check   驗證讀音表的拼音 token 都在 CosyVoice3 tokenizer 裡
         python -X utf8 pipeline/tts_cosy_text.py --audit-cache <快取目錄 或 tag>   唯讀列出讀音變更、下次會重錄的單位
         python -X utf8 pipeline/tts_cosy_text.py --dry-run <tag>   讀 <tag>\script.txt 數多音字規則會改到幾句(不配音、不動快取)
         python -X utf8 pipeline/tts_cosy_text.py --dry-run <tag>   讀 <tag>\script.txt 數多音字規則會改到幾句(不配音、不動快取)
- E1 全標注(pilot,PLAN_工作室v2 §6.3;docs/tts.md §4.7):環境變數 COSY_ANNOTATE=all(預設 table = 現行)時,詞表/規則/記憶沒標到的多音字
  也給拼音標注(ok 記憶 > g2pW > pypinyin 詞級);table 模式輸出與改前逐位元相同。多音字集合 COSY_POLYSET=rules|risk(預設)|all。
         python -X utf8 pipeline/tts_cosy_text.py --build-polyset-risk   重算 risk 集合寫 pipeline/moe/polyset_risk.txt(之後可手工增刪)
"""
import functools
import json
import os
import re
import sys
from pathlib import Path

import pron_memory as PM
import tts_pron

HERE = Path(__file__).resolve().parent
PRON_FILE, TERMS_FILE = HERE / "cosy_pron.json", HERE / "cosy_terms.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


_P, _T = _load(PRON_FILE), _load(TERMS_FILE)
PRON = {k: v for k, v in _P.items() if not k.startswith("_")}
PRON_VERIFIED = set(_P.get("_verified", []))
TERMS = {k: v for k, v in _T.items() if not k.startswith("_")}
TERMS_VERIFIED = set(_T.get("_verified", []))
DIRECT = list(_T.get("_direct", []))
ASR_ALIAS = _T.get("_asr_alias", {})
ASR_REJECT = {k: v for k, v in (_T.get("_asr_reject") or {}).items() if not k.startswith("_")}  # 原文詞 -> 辨識出現就算唸錯的字串
TOKEN_RE = re.compile(r"(\[[^\[\]\s]+\])")
RULES_FILE = HERE / "pron_rules.json"
TOKENIZER_PY = HERE.parent / "tts_models" / "CosyVoice" / "cosyvoice" / "tokenizer" / "tokenizer.py"
RULES_FILE = HERE / "pron_rules.json"
TOKENIZER_PY = HERE.parent / "tts_models" / "CosyVoice" / "cosyvoice" / "tokenizer" / "tokenizer.py"


def _word_re(w):
    return re.compile(rf"(?<![A-Za-z.]){re.escape(w)}(?![A-Za-z.])")


def unsay(text):
    """@say 已把 cosy_terms 登錄的英文詞換成 ChatTTS 寫法(say_terms.json,例 EA -> 伊誒)的,換回原文英文詞。"""
    try:
        st = _load(HERE / "say_terms.json")["terms"]
    except (OSError, ValueError, KeyError):
        return text
    for t in sorted(st, key=lambda t: -len(t.get("say") or "")):
        if t.get("say") and t["term"] in TERMS and t["say"] != t["term"]:
            text = text.replace(t["say"], t["term"])
    return text


# 替換值(中文寫法)送引擎時要帶的拼音標注(2026-10-30:「藝電」常被唸成 dì diàn;零聲母用 [y])。只在 apply_terms 套用,
# 不寫進 cosy_pron.json(那邊是在 terms 之後比對,換完 terms 的「藝電」已是標注,不會重複)。
TERM_ANNOT = {"藝電": "[y][ì][d][iàn]"}
_CJK = re.compile(r"[㐀-鿿豈-﫿　-〿＀-￯\[\]]")   # [ ] = 前一個詞換出的拼音標注邊界
_CJK_PLAIN = re.compile(r"[㐀-鿿豈-﫿]")


def _sub_term(text, w, v):
    """整詞 w 換成 v。v 頭/尾是 CJK 字時,原文該詞緊鄰的空格若另一側也是 CJK 字(或中文標點),去掉那個空格
    (「藝電 剛砍掉」會讓模型在空格處多唸字);只動這種替換造成的空格。回傳 (新文字, 次數)。"""
    out, pos, n = [], 0, 0
    head, tail = bool(_CJK_PLAIN.match(v)), bool(_CJK_PLAIN.match(v[-1:]))
    shown = TERM_ANNOT.get(v, v)
    for m in _word_re(w).finditer(text):
        s, e = m.start(), m.end()
        if head:
            k = s
            while k > pos and text[k - 1] == " ":
                k -= 1
            if k < s and k > 0 and _CJK.match(text[k - 1]):
                s = k
        if tail:
            k = e
            while k < len(text) and text[k] == " ":
                k += 1
            if k > e and k < len(text) and _CJK.match(text[k]):
                e = k
        out += [text[pos:s], shown]
        pos, n = e, n + 1
    out.append(text[pos:])
    return "".join(out), n


def apply_terms(text, extra=None):
    """英文整詞(前後不是英文字母或點)換成 CosyVoice 寫法;中文寫法兩側原本的英文空格在 CJK 旁會去掉(_sub_term)。"""
    terms = dict(TERMS, **(extra or {}))
    for w in sorted(terms, key=len, reverse=True):
        text = _sub_term(text, w, terms[w])[0]
    return text


# 「著」(2026-10-21 使用者:助詞「跟著」等多次被唸成 zhù「住」,要強制唸常用音):OpenCC t2s 不改「著」,
# 模型看到的「著」= 簡體的 zhù。除了真的唸 zhù 的詞(ZHU_WORDS,繁簡兩種寫法),一律換成簡體「着」(zhe/zháo/zhuó,沒有 zhù 讀法)。
ZHU_WORDS = ["著名", "著作", "著稱", "著称", "顯著", "显著", "卓著", "昭著", "名著", "巨著", "專著", "专著", "編著", "编著",
             "譯著", "译著", "論著", "论著", "原著", "土著", "著者", "著錄", "著录", "著書", "著书", "著述", "遺著", "遗著",
             "新著", "拙著", "合著"]
ZHE_HIT = "著→着"
ZHU_NOT_NEXT = {"譯著": "色", "译著": "色"}   # 「編譯著色器」的「譯著」不是名詞,後面接色就不算 ZHU_WORDS(與 pron_rules.json 的 譯著(?!色) 一致)


def _zhu_at(text, i, w):
    """text[i] 的「著」是否落在 ZHU_WORDS 的詞 w 裡(含 ZHU_NOT_NEXT 的排除)。"""
    a = i - w.index("著")
    return a >= 0 and text[a:a + len(w)] == w and not text.startswith(ZHU_NOT_NEXT.get(w, "\x00"), a + len(w))


def fix_zhe(text):
    """非 ZHU_WORDS 的「著」換成「着」。回傳 (文字, 有沒有換)。"""
    out = list(text)
    for i, ch in enumerate(text):
        if ch == "著" and not any(_zhu_at(text, i, w) for w in ZHU_WORDS):
            out[i] = "着"
    t = "".join(out)
    return t, t != text


def _pron_words(text):
    """cosy_pron.json 詞表標注(長詞優先,標注後原詞已不存在,不會再被短詞命中)。回傳 (文字, 命中的詞)。"""
    hits = []
    for w in sorted(PRON, key=len, reverse=True):
        if w in text:
            hits.append(w)
            text = text.replace(w, PRON[w])
    return text, hits


# ---- 多音字語境規則(pron_rules.json;設計見 pipeline/docs/PLAN_多音字規則_2026-10-21.md §1) ----
def _compile_rules(raw):
    """-> (chars, words, regs)。words = [(詞, 字, 位置, py|None=keep, unverified)] 長詞優先、同長 keep 先(其餘保持檔內順序);
    regs = [(編譯後正規式, 字, py|None, unverified)] 依檔內順序。"""
    chars, words, regs = {}, [], []
    for ch, e in raw.items():
        if ch.startswith("_"):
            continue
        chars[ch] = e
        for r in e.get("rules", []):
            py = None if r.get("keep") else r["py"]
            unv = bool(r.get("unverified"))
            for w in r.get("words", []):
                offs = tuple(r.get("pos") or [i for i, c in enumerate(w) if c == ch])
                if not offs or any(not 0 <= o < len(w) or w[o] != ch for o in offs):
                    raise ValueError(f"pron_rules.json「{ch}」的詞「{w}」沒有可標的「{ch}」或 pos 不對")
                words.append((w, ch, offs, py, unv))
            if "re" in r:
                regs.append((re.compile(r["re"]), ch, py, unv))
    words.sort(key=lambda x: (-len(x[0]), x[3] is not None))
    return chars, words, regs


def _rule_tokens(raw):
    return {t for e in raw.values() if isinstance(e, dict)
            for v in [e.get("model_default", "")] + [r.get("py") or "" for r in e.get("rules", [])]
            for t in TOKEN_RE.findall(v)}


def _tokenizer_tokens(tokenizer_py=None):
    return set(re.findall(r'"(\[[^\[\]"]+\])"', Path(tokenizer_py or TOKENIZER_PY).read_text(encoding="utf-8")))


def _load_rules():
    raw = _load(RULES_FILE)
    if TOKENIZER_PY.exists():  # 載入時逐一驗 token(壞的印出來並 raise);沒有 tokenizer 檔(別台機器)就略過,--check 仍可驗
        bad = sorted(_rule_tokens(raw) - _tokenizer_tokens())
        if bad:
            print(f"pron_rules.json 有不存在的拼音 token: {bad}", file=sys.stderr)
            raise ValueError(f"pron_rules.json 有不存在的拼音 token: {bad}")
    return raw, _compile_rules(raw)


RULES_RAW, (RULE_CHARS, RULE_WORDS, RULE_REGS) = _load_rules()
RULE_ALWAYS = {c for c, e in RULE_CHARS.items() if e.get("always")}


def rule_events(text):
    """多音字規則會標注的位置:[(位置, 字, 標注, 命中鍵, 來源 word|re|default, unverified)],依位置排序。
    順序:words(長詞優先)-> re(檔內順序;只對未處理位置)-> always 字的 model_default。keep 規則只佔位不標注。
    輸入是原文(含前後文);落在詞表區段內的命中由 _live_events 去掉。"""
    done = {}  # 位置 -> (py|None, 鍵, 來源, unverified)
    for w, ch, offs, py, unv in RULE_WORDS:
        i = text.find(w)
        while i >= 0:
            pos = [i + o for o in offs]
            if not any(p in done for p in pos):
                for p in pos:
                    done[p] = (py, f"{w}→{py}" if py else None, "word", unv)
            i = text.find(w, i + 1)
    for pat, ch, py, unv in RULE_REGS:
        for m in pat.finditer(text):
            a, b = m.span("t") if "t" in pat.groupindex else m.span()
            for p in range(a, b):
                if text[p] == ch and p not in done:
                    done[p] = (py, f"{ch}→{py}" if py else None, "re", unv)
    for p, c in enumerate(text):
        if c in RULE_ALWAYS and (p not in done or done[p][0] is None):
            e = RULE_CHARS[c]
            done[p] = (e["model_default"], f"{c}→{e['model_default']}", "default", bool(e.get("default_unverified")))
    return [(p, text[p], *done[p]) for p in sorted(done) if done[p][0]]


def apply_rules(text):
    """多音字語境規則單獨標注(不含詞表;apply_pron 才是合併版)。回傳 (文字, 命中鍵 list;鍵 = 「詞→標注」或「字→標注」)。"""
    ev = rule_events(text)
    if not ev:
        return text, []
    out, hits = list(text), []
    for p, _ch, py, key, _src, _unv in ev:
        out[p] = py
        if key not in hits:
            hits.append(key)
    return "".join(out), hits


def _memory_marks(text):
    """語境讀音記憶要換上標注的位置 {位置: (標注值, 命中鍵)};表空回 {}。"""
    out = {}
    for p, e in PM.scan(text):
        v = PM.mark_value(e)
        if v:
            out[p] = (v, PM.hit_key(e))
    return out


def _trim_spans(spans, marks):
    """記憶位置落在詞表區段內且標注不同:區段切開,讓出該字(其餘字沿用詞表標注);對不齊的區段不動。"""
    out = []
    for s, e, v in spans:
        us = PM.units(v)
        cut = [k for k in range(e - s) if s + k in marks and us[k] != marks[s + k][0]] if len(us) == e - s else []
        if not cut:
            out.append((s, e, v))
            continue
        a = 0
        for k in cut + [e - s]:
            if k > a:
                out.append((s + a, s + k, "".join(us[a:k])))
            a = k + 1
    return out


def _word_spans(text):
    """cosy_pron.json 詞表在「原文」上的命中區段(長詞優先、區段不重疊;記憶改標注的字讓出,見 _trim_spans)。回傳 ([(起, 迄, 標注)], 命中的詞)。"""
    order = sorted(PRON, key=len, reverse=True)
    cand = []   # (-長度, 起點, 詞序, 詞):長詞優先,同長取左邊先出現的(關卡關卡 = 關卡|關卡,不是中間的 卡關)
    for k, w in enumerate(order):
        i = text.find(w)
        while i >= 0:
            cand.append((-len(w), i, k, w))
            i = text.find(w, i + 1)
    spans, used = [], set()
    for _n, i, k, w in sorted(cand):
        j = i + len(w)
        if not any(i < e and s < j for s, e, _ in spans):
            spans.append((i, j, PRON[w]))
            used.add(k)
    hits = [order[k] for k in sorted(used)]
    marks = _memory_marks(text)
    return (_trim_spans(sorted(spans), marks) if marks else sorted(spans)), hits


def _merge_memory(text, spans, ev, marks):
    """規則事件併入記憶(來源 memory,記憶贏);值與原本相同的位置不動,命中鍵不變。"""
    by, plain = {e[0]: e for e in ev}, fix_zhe(text)[0]
    for p, (v, key) in marks.items():
        if not any(s <= p < en for s, en, _ in spans) and v != (by[p][2] if p in by else plain[p]):
            by[p] = (p, text[p], v, key, "memory", False)
    return [by[p] for p in sorted(by)]


def _live_events(text, spans):
    """原文上的規則命中,去掉落在詞表區段內的(詞表贏);再併入語境讀音記憶。"""
    ev = [e for e in rule_events(text) if not any(s <= e[0] < en for s, en, _ in spans)]
    marks = _memory_marks(text)
    return _merge_memory(text, spans, ev, marks) if marks else ev


# ---- E1 全標注(pilot;預設 table = 現行,COSY_ANNOTATE=all 才開) ----
ANNOTATE_ENV, ANNOTATE_MODES = "COSY_ANNOTATE", ("table", "all")
POLYSET_ENV, POLYSETS = "COSY_POLYSET", ("rules", "risk", "all")
RISK_FILE = HERE / "moe" / "polyset_risk.txt"
BACKLOG_FILE = HERE / "pron_backlog.md"
_VARIANT_NOTE = re.compile(r"又音|讀音|語音")   # 審訂表「(一)之又音/讀音/語音」= 又音、文白異讀
E1_KEY = "E1:"              # all 模式新增標注的命中鍵前綴(與規則鍵分開,pron_changed 才判得出 table/all 切換)
SANDHI_SKIP = {"一", "不"}   # 變調字交給模型(標死本調反而唸錯變調)
_TONES = {"a": "āáǎà", "o": "ōóǒò", "e": "ēéěè", "i": "īíǐì", "u": "ūúǔù", "ü": "ǖǘǚǜ"}
_INITS2, _INITS1 = ("zh", "ch", "sh"), set("bpmfdtnlgkhjqxrzcsyw")


def annotate_mode(mode=None):
    """table(現行)| all;mode 沒給讀環境變數 COSY_ANNOTATE,不認得的值當 table。"""
    m = (mode or os.environ.get(ANNOTATE_ENV) or "table").strip().lower()
    return m if m in ANNOTATE_MODES else "table"


@functools.lru_cache(maxsize=1)
def _token_set():
    return frozenset(_tokenizer_tokens()) if TOKENIZER_PY.exists() else frozenset()


def polyset_name(polyset=None):
    """rules | risk(預設)| all;沒給讀環境變數 COSY_POLYSET,不認得的值當 risk。"""
    m = (polyset or os.environ.get(POLYSET_ENV) or "risk").strip().lower()
    return m if m in POLYSETS else "risk"


def _moe_pron():
    try:
        import tts_moe
        return tts_moe.load_pron()
    except Exception:  # noqa: BLE001  審訂表檔不在(別台機器)
        return {}


def _risky(readings):
    """審訂表讀音去掉又音/讀音/語音,再去掉「只差輕聲」(輕聲讀音的音節另有帶調讀音)後,仍有 >= 2 個不同讀音。"""
    import tts_g2p as G
    pys = {G.norm_py(r.get("pinyin")) for r in readings if not _VARIANT_NOTE.search(r.get("note") or "")} - {None}
    toned = {p for p in pys if not p.endswith("5")}
    pys = toned | {p for p in pys if p.endswith("5") and not any(t[:-1] == p[:-1] for t in toned)}
    return len(pys) >= 2


def _backlog_chars():
    if not BACKLOG_FILE.exists():
        return set()
    rows = (ln.split("|") for ln in BACKLOG_FILE.read_text(encoding="utf-8").splitlines() if ln.startswith("|"))
    return {r[1].strip() for r in rows if len(r) > 2 and len(r[1].strip()) == 1 and r[1].strip() != "字"}


def build_risk():
    """risk 集合 = 審訂表有實質不同讀音的字(_risky)∪ pron_rules ∪ pron_backlog ∪ pron_memory 的字(排序後的 list)。"""
    moe = {c for c, v in _moe_pron().items() if len(v) > 1 and _risky(v)}
    mem = {e.get("char") for e in PM.load().get("entries", []) if e.get("char")}
    return sorted(moe | set(RULE_CHARS) | _backlog_chars() | mem)


@functools.lru_cache(maxsize=None)
def polyphone_chars(polyset=None):
    """多音字集合(COSY_POLYSET):rules = pron_rules.json 的字;risk(預設)= pipeline/moe/polyset_risk.txt(一行一字,可手工增刪;
    沒有檔就現算 build_risk)∪ rules;all = 審訂表全部多讀音字 ∪ risk(risk ⊂ all)。「著」由 fix_zhe 處理、一/不 交給模型,都不列。"""
    name, rules = polyset_name(polyset), set(RULE_CHARS)
    if name in ("risk", "all"):
        chars = (set(RISK_FILE.read_text(encoding="utf-8").split()) if RISK_FILE.exists() else set(build_risk())) | rules
        if name == "all":
            chars |= {c for c, v in _moe_pron().items() if len(v) > 1}
    else:
        chars = rules
    return frozenset(chars - SANDHI_SKIP - {"著"})


def _mark_final(fin, tone):
    """韻母加調號(a/e 優先、ou 標 o、其餘標最後一個母音);輕聲不標。"""
    if tone == 5:
        return fin
    k = fin.find("a") if "a" in fin else fin.find("e") if "e" in fin else fin.find("o") if "ou" in fin else         max(fin.rfind(c) for c in "iuüo")
    return fin[:k] + _TONES[fin[k]][tone - 1] + fin[k + 1:]


def py_tokens(py3):
    """tone3(zhang3、lv4、yue4、de5)-> 標注 `[zh][ǎng]`。寫法照 TERM_ANNOT / cosy_pron 慣例:零聲母用 [y]/[w] 當聲母、
    jqxy 後的 ü 寫 u([j][ué]、[y][uè])、l/n 後單獨的 ü 用 [ǘ]、üe 用 [vè];任一 token 不在 tokenizer 回 None(不標)。"""
    m = re.fullmatch(r"([a-zü]+)([1-5])", (py3 or "").strip().lower())
    if not m:
        return None
    base, tone = re.sub(r"^([jqxy])[üv]", r"u", m.group(1).replace("v", "ü")), int(m.group(2))
    init = base[:2] if base[:2] in _INITS2 else base[0] if base[0] in _INITS1 and len(base) > 1 else ""
    fin = base[len(init):]
    if not fin or not re.search(r"[aeiouü]", fin):
        return None
    fin = _mark_final(fin, tone)
    if len(fin) > 1 and fin[0] == "ü":
        fin = "v" + fin[1:]
    toks = ([f"[{init}]"] if init else []) + [f"[{fin}]"]
    have = _token_set()
    return "".join(toks) if have and all(t in have for t in toks) else None


@functools.lru_cache(maxsize=4096)
def _g2pw_row(text):
    """g2pW 對整句的逐字 tone3(有裝且模型在才用);不可用回 None。"""
    import tts_g2p as G
    conv = G.converter()
    if conv is None:
        return None
    try:
        row = conv([text])[0]
    except Exception:  # noqa: BLE001
        return None
    return tuple(G.norm_py(r) if r else None for r in row)


@functools.lru_cache(maxsize=4096)
def _pypinyin_row(text):
    """pypinyin 詞級讀音(每段連續漢字整段丟進 lazy_pinyin,由它斷詞取詞音);沒裝回 None。"""
    try:
        from pypinyin import Style, lazy_pinyin
    except ImportError:
        return None
    row = [None] * len(text)
    for m in _CJK_PLAIN_RUN.finditer(text):
        r = lazy_pinyin(m.group(0), style=Style.TONE3, neutral_tone_with_five=True, v_to_u=True)
        if len(r) == len(m.group(0)):
            row[m.start():m.end()] = r
    return tuple(row)


_CJK_PLAIN_RUN = re.compile(r"[㐀-鿿豈-﫿]+")


def _memory_ok(text):
    """state ok 的語境讀音記憶裡 py 是拼音標注的位置 {位置: 標注}(現行只套 fix=mark 的;all 模式連只記 py 的也用)。"""
    out = {}
    for p, e in PM.scan(text):
        py = e.get("py") or ""
        if e.get("state") == "ok" and py and not TOKEN_RE.sub("", py) and all(t in _token_set() for t in TOKEN_RE.findall(py)):
            out[p] = py
    return out


def poly_marks(text, mode=None, spans=None, ev=None, polyset=None):
    """原文(pron_source)每個多音字位置 -> [(位置, 字, 標注|None, 來源, 是否 all 模式新增)],依位置排序。
    來源:table(cosy_pron 詞表區段)、rule(pron_rules)、memory(語境讀音記憶)、zhe(著換着)= 現行就處理;
    all 模式對其餘多音字依序取 memory(ok 記憶)> g2pw > pypinyin,都沒有或 token 不在 tokenizer 記 none(不標)。
    table 模式只回現行處理到的位置。"""
    if spans is None:
        spans = _word_spans(text)[0]
    if ev is None:
        ev = _live_events(text, spans)
    by = {e[0]: e for e in ev}
    out, todo, poly = [], [], polyphone_chars(polyset_name(polyset))
    for p, ch in enumerate(text):
        span = next(((s, e, v) for s, e, v in spans if s <= p < e), None)
        if span is not None:
            if ch in poly or ch in RULE_CHARS:
                s, e, v = span
                us = PM.units(v)
                out.append((p, ch, us[p - s] if len(us) == e - s else v, "table", False))   # 對得齊取該字單位,否則整段
        elif p in by:
            out.append((p, ch, by[p][2], "memory" if by[p][4] == "memory" else "rule", False))
        elif ch == "著" and not any(_zhu_at(text, p, w) for w in ZHU_WORDS):
            out.append((p, ch, "着", "zhe", False))
        elif ch in poly:
            todo.append((p, ch))
    if annotate_mode(mode) == "all" and todo:
        mem = _memory_ok(text)
        rows = [("g2pw", _g2pw_row(text)), ("pypinyin", _pypinyin_row(text))]
        for p, ch in todo:
            v, src = (mem[p], "memory") if p in mem else (None, "none")
            for name, row in rows:
                if v is None and row is not None and p < len(row) and row[p]:
                    v = py_tokens(row[p])
                    src = name if v else src
            out.append((p, ch, v, src, True))
    return sorted(out)


def _e1_marks(text, spans, ev, mode=None, polyset=None):
    """all 模式新增標注 [(位置, 字, 標注)];table 模式回 []。"""
    if annotate_mode(mode) != "all":
        return []
    return [(p, ch, v) for p, ch, v, _src, new in poly_marks(text, "all", spans, ev, polyset) if new and v]


def apply_pron(text, mode=None, polyset=None):
    """拼音標注:語境讀音記憶、詞表(cosy_pron)與多音字規則(pron_rules)都在原文上比對(規則看得到原字前後文),再合併;
    重疊時 記憶 > 詞表 > 規則(規則命中作廢)。最後剩下的「著」換「着」。回傳 (文字, 命中鍵 list)。
    COSY_ANNOTATE=all(或 mode="all"):其餘多音字再補標注(poly_marks;命中鍵前綴 E1:)。"""
    spans, hits = _word_spans(text)
    ev = _live_events(text, spans)
    rep = {e[0]: e[2] for e in ev}
    e1 = _e1_marks(text, spans, ev, mode, polyset)
    rep.update((p, v) for p, _ch, v in e1)
    out, i, pos = [], 0, 0
    for s, e, v in spans:
        out.append("".join(rep.get(p, text[p]) for p in range(pos, s)))
        out.append(v)
        pos = e
    out.append("".join(rep.get(p, text[p]) for p in range(pos, len(text))))
    text = "".join(out)
    for _p, _ch, _py, key, _src, _unv in ev:
        if key not in hits:
            hits.append(key)
    for _p, ch, v in e1:
        if f"{E1_KEY}{ch}→{v}" not in hits:
            hits.append(f"{E1_KEY}{ch}→{v}")
    text, zhe = fix_zhe(text)
    if zhe:
        hits.append(ZHE_HIT)
    return text, hits


def pron_source(say):
    """apply_pron 看到的文字:unsay -> 英文寫法 -> 書名號冒號刪除(語境讀音記憶的語境鍵以此為準)。"""
    return tts_pron.drop_title_colon(apply_terms(unsay(say)))


def pron_text(say, mode=None):
    """送配音的文字(@say 後)依 tts_cosy3.engine_text 同樣順序做到拼音標注為止:unsay -> 英文寫法 -> 書名號冒號刪除
    -> 拼音標注。回傳 (文字, 命中的詞)。"""
    return apply_pron(pron_source(say), mode)


def _hit_value(h):
    """命中鍵的標注:詞表的詞 -> PRON 標注;規則/著/E1 的鍵「詞→標注」「字→標注」-> 箭頭後面。"""
    return PRON.get(h) or h.split("→", 1)[-1]


def pron_hits(say):
    """這句命中的讀音詞與其標注 {詞: 標注}(tts_cosy3 存進 .qc.json 的 pron_hits)。"""
    return {w: _hit_value(w) for w in pron_text(say)[1]}


def pron_tokens(say):
    """這句送進引擎的拼音標注 token 序列(engine_text 之後的簡體/數字正規化不動 token,可與舊紀錄的 engine_text 比對)。"""
    return TOKEN_RE.findall(pron_text(say)[0])


def pron_changed(rec, say):
    """音檔旁的 .qc.json 紀錄(rec)錄音時的讀音標注是否與目前讀音表不同(cosy_pron.json 改過 -> 這句要重錄)。
    紀錄有 pron_hits 就比對命中詞與標注;只有 engine_text 就比對標注 token 序列;都沒有(舊紀錄)視為一致。"""
    if not rec:
        return False
    if isinstance(rec.get("pron_hits"), dict):
        return rec["pron_hits"] != pron_hits(say)
    if rec.get("engine_text"):
        return TOKEN_RE.findall(rec["engine_text"]) != pron_tokens(say) or fix_zhe(rec["engine_text"])[1]
    return False


def term_hits(say):
    """這句命中的英文寫法 {英文詞: 寫法}(同 apply_terms 的長詞優先順序;tts_cosy3 存進 .qc.json 的 term_hits)。"""
    text, hits = unsay(say), {}
    for w in sorted(TERMS, key=len, reverse=True):
        text, n = _word_re(w).subn(lambda _, v=TERMS[w]: v, text)
        if n:
            hits[w] = TERMS[w]
    return hits


def _en_words(text):
    """去掉拼音 token 後的英文字母單字序列(OpenCC 與數字/標點正規化不動英文字母,可比對舊紀錄的 engine_text)。"""
    return re.findall(r"[A-Za-z]+", TOKEN_RE.sub("", text))


def terms_changed(rec, say):
    """音檔旁的 .qc.json 紀錄錄音時的英文寫法(cosy_terms.json)是否與目前不同(Roblox 改 Row blocks -> 這句要重錄)。
    紀錄有 term_hits 就比對命中詞與寫法;舊紀錄只有 engine_text 就比對英文單字序列(限制:舊紀錄裡「中文改中文」的寫法變更測不到);
    都沒有視為一致。"""
    if not rec:
        return False
    if isinstance(rec.get("term_hits"), dict):
        return rec["term_hits"] != term_hits(say)
    if rec.get("engine_text"):
        return _en_words(rec["engine_text"]) != _en_words(pron_text(say)[0])
    return False


def audit_cache(tts_dir):
    """唯讀稽核配音快取目錄(含 sub/):回傳讀音或英文寫法已變更、下次配音會重錄的 [(單位, 文字)]。不動任何檔。"""
    out = []
    d = Path(tts_dir)
    for qf in sorted(list(d.glob("*.qc.json")) + list((d / "sub").glob("*.qc.json"))):
        try:
            rec = json.loads(qf.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if rec.get("engine") == "cosy3" and rec.get("text") and (pron_changed(rec, rec["text"]) or terms_changed(rec, rec["text"])):
            unit = str(rec.get("idx") or qf.name[:-len(".qc.json")])
            out.append((unit if qf.parent == d else f"sub/{unit}", rec["text"]))
    return out


def asr_rejects(text, hyps, table=None):
    """英文詞唸錯回查(cosy_terms `_asr_reject`,純函式):句子含原文詞,且某個辨識結果含該詞的否決字串
    (出現次數多於原文本身,避免原文就有的字誤判)-> 一筆 dict(term, hit, src)。hyps = {來源: 辨識文字}(asr / asr2)。
    命中 = 品管項 term_misread(BioWare 唸成「Bio 哇」時辨識寫「百奥瓦」,asr_loose 仍判通過;2026-10-30)。"""
    out = []
    for term, rejects in (ASR_REJECT if table is None else table).items():
        if term.startswith("_") or term not in text:
            continue
        for src, hyp in hyps.items():
            for r in rejects:
                if hyp and hyp.count(r) > text.count(r):
                    out.append(dict(term=term, hit=r, src=src))
    return out


def unverified(text):
    """這句用到的未聽審讀音標注與直接唸的英文詞(聽審頁優先聽用)。"""
    t = unsay(text)
    ev = _live_events(t, _word_spans(t)[0])
    rule_keys, unv_keys = {e[3] for e in ev}, {e[3] for e in ev if e[5]}
    pron = [w for w in apply_pron(t)[1] if (w in unv_keys if w in rule_keys else w not in PRON_VERIFIED)]
    import terms_check   # 英文詞判斷單一來源(延後載入:terms_check 反過來 import 本檔)
    return pron, terms_check.registered_unverified(text)


_W = r"[A-Za-z0-9][A-Za-z0-9.&'\-]*"
_TOK = re.compile(_W + r"(?: " + _W + r")*")


def analyze(texts):
    """texts = 送配音的文字 list(@say 後)。回傳同 tts_terms.analyze 的格式:unapplied 恆空(寫法由引擎自動套)、
    unregistered = cosy_terms 與 _direct 都沒有的英文詞、direct = 直接唸英文的詞(資訊,未聽審者列優先聽)。"""
    unreg, direct = {}, {}
    known = sorted(list(TERMS) + DIRECT + [v for v in TERMS.values() if re.search(r"[A-Za-z]", v)], key=len, reverse=True)
    for i, raw in enumerate(texts, 1):
        text = unsay(raw or "")
        for w in known:
            p = _word_re(w)
            if p.search(text):
                if w in DIRECT:
                    direct.setdefault(w, {"say": None, "lines": []})["lines"].append(i)
                text = p.sub(lambda m: "\x00" * len(m.group(0)), text)
        text = TOKEN_RE.sub("", text)
        for m in _TOK.finditer(text):
            tok = m.group(0).rstrip(".-'")
            if re.search(r"[A-Za-z]", tok):
                e = unreg.setdefault(tok, {"lines": []})
                if i not in e["lines"]:
                    e["lines"].append(i)
    return {"unapplied": {}, "unregistered": unreg, "direct": direct}


def check_e1():
    """E1 全標注可轉率(資訊,不影響 --check 結束碼):審訂表多音字的每個讀音能否轉成 tokenizer 有的標注;轉不了的 all 模式不標。"""
    import tts_g2p as G
    import tts_moe
    pron, tot, ok, miss = tts_moe.load_pron(), 0, 0, set()
    for ch in polyphone_chars("all"):
        for r in pron.get(ch, []):
            py3 = G.norm_py(r.get("pinyin"))
            if not py3:
                continue
            tot += 1
            if py_tokens(py3):
                ok += 1
            else:
                miss.add(py3)
    return len(polyphone_chars("all")), tot, ok, sorted(miss)


def check_pron(tokenizer_py=None):
    """讀音表(cosy_pron.json)與多音字規則(pron_rules.json)每個 [..] token 都必須在 CosyVoice3 tokenizer 的特殊 token 表裡,回傳不存在的 token。"""
    have = _tokenizer_tokens(tokenizer_py)
    return sorted(({t for v in PRON.values() for t in TOKEN_RE.findall(v)} | _rule_tokens(RULES_RAW)) - have)


def _tidy(say):
    """dry-run 用:跟 pron_text 同樣先做 unsay -> 英文寫法 -> 書名號冒號刪除,再進讀音標注。"""
    return tts_pron.drop_title_colon(apply_terms(unsay(say)))


def dry_run(tag):
    """讀 <tag>\\script.txt 每句的 say 文字(@say 之後),數多音字規則會改到幾句;印摘要,不配音、不動快取。"""
    import collections
    import script_txt2json
    src = (HERE.parent / tag / "script.txt").read_text(encoding="utf-8-sig")
    _title, says, sections, _top, _defs, _skipped = script_txt2json.parse(src)
    total = hit = nondef = alw = 0
    by_char, by_key, by_always = collections.Counter(), collections.Counter(), collections.Counter()
    for sec in sections:
        for _no, _tag, text, _extra in sec["rows"]:
            say = text
            for k, v in says:
                say = say.replace(k, v)
            total += 1
            ev = _live_events(_tidy(say), _word_spans(_tidy(say))[0])
            if not ev:
                continue
            hit += 1
            nondef += any(e[4] != "default" for e in ev)
            alw += any(e[4] == "default" for e in ev)
            for _p, ch, _py, key, src_, _unv in ev:
                if src_ != "default":
                    by_char[ch] += 1
                    by_key[key] += 1
                else:
                    by_always[ch] += 1
    print(f"{tag}: 總句數 {total}、規則改到的句數 {hit}(含非預設讀音 {nondef} 句、含 always 預設標注 {alw} 句)")
    print("非預設讀音各字命中次數前 10: " + "、".join(f"{c}×{n}" for c, n in by_char.most_common(10)))
    print("命中鍵前 10: " + "、".join(f"{k}×{n}" for k, n in by_key.most_common(10)))
    print("always 字預設標注次數: " + "、".join(f"{c}×{n}" for c, n in by_always.most_common()))


if __name__ == "__main__":
    if "--build-polyset-risk" in sys.argv:
        risk = build_risk()
        RISK_FILE.write_text("\n".join(risk) + "\n", encoding="utf-8")
        print(f"risk 集合 {len(risk)} 字 -> {RISK_FILE}")
        sys.exit(0)
    if "--check" in sys.argv:
        bad = check_pron()
        print("讀音表 token 全部存在" if not bad else f"不存在的 token: {bad}")
        n_ch, n_rd, n_ok, miss = check_e1()
        print(f"E1 全標注:多音字 {n_ch} 字、審訂讀音 {n_rd} 個可轉標注 {n_ok} 個(轉不了的 all 模式不標,例 {miss[:12]})")
        sys.exit(1 if bad else 0)
    if "--dry-run" in sys.argv:  # 參數 = 片名 tag
        dry_run(sys.argv[sys.argv.index("--dry-run") + 1])
        sys.exit(0)
    if "--audit-cache" in sys.argv:  # 參數 = 快取目錄,或片名 tag(取 paths.tts_dir(tag, "cosy3"))
        arg = sys.argv[sys.argv.index("--audit-cache") + 1]
        d = Path(arg)
        if not d.is_dir() or not any(d.glob("*.qc.json")):   # 同名文案資料夾(<tag>\)不是快取目錄:沒有 .qc.json 就當 tag
            import paths
            d = paths.tts_dir(arg, "cosy3")
        bad = audit_cache(d)
        print(f"{d}: 讀音變更、會重錄 {len(bad)} 個單位")
        for unit, text in bad:
            print(f"  {unit}  {text}")
