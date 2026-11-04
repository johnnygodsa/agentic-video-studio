#!/usr/bin/env python3
r"""可唸性預檢(工作室 v2 Phase 3,規格 docs\director_ab.md §5/§7/§8;說明與實測門檻見 docs\speakable.md)。
寫稿與改句時用:不合成、不用 GPU,只看這句「送配音的文字」(@say 之後)有哪些地方 CosyVoice 容易唸壞。

python -X utf8 pipeline\speakable.py <tag> [--json] [--explain]
python -X utf8 pipeline\speakable.py --calibrate     掃 build\*\tts_qc.json 重算各特徵的品管未過率(門檻依據;docs\speakable.md)

項目(code,severity;門檻 T 由實測訂,依據在 docs\speakable.md「實測」):
  en_unregistered 未登錄英文(err,配音前本來就擋)/ memory_bad 讀音記憶標 bad 且要改寫(err;undetermined 不提示)
  poly_unmarked 本句命中「已知易錯字」卻沒有詞表/規則/記憶覆蓋(warn)/ backlog 命中 pron_backlog 待規則的語境(warn);
    這兩項命中在《…》或本片主體名內不報(片名不換說法,讀音由 B4 pron-review 處理)
  en_dense 英文佔比高 / num_dense 句內還有阿拉伯數字沒換成中文唸法 / clause_long 單一子句太長 / line_long 整句太長(依實測分 err/warn)
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402
import pron_memory as PM  # noqa: E402
import tts_cosy_text as C  # noqa: E402

HERE = Path(__file__).resolve().parent
# 門檻(依 build\*\tts_qc.json 11 支片 763 句實測,數字與未過率見 docs\speakable.md;未標 err 的都是 warn)
T = dict(
    en_ratio_warn=0.15, en_ratio_err=None,   # 英文單字數 ÷ 發音單位(中文一字、英文一詞、數字一位)
    digits_warn=3, digits_err=None,          # 送引擎前仍是阿拉伯數字的位數
    clause_warn=20, clause_err=None,         # 最長子句的發音單位數(以配音會停的標點切)
    line_warn=45, line_err=None,             # 整句發音單位數
    short_warn=16,                           # 整句發音單位數 < 此值提示「太短」(2_文案 §3 不寫太短的句子)
    poly_warn=3,                             # 本句「已知易錯字」沒被覆蓋的個數 >= 此值才提示(實測 >=3 句佔 10%,未過率最高)
)
# 實測(docs\speakable.md)出現在 >= 5% 句子、未過率不高於基準的高頻字(的 了 還 要 會…):每句都有,提示沒有資訊量,poly_unmarked 略過
COMMON_POLY = frozenset("的了還要會只那沒分好打地幾種覺給難更")
UNIT = re.compile(r"[A-Za-z]+|[0-9]|[一-鿿]")
EN = re.compile(r"[A-Za-z]+")
CLAUSE = re.compile(r"[,，、;；:：。?!？！]")
BACKLOG_PENDING = "待規則"
QUOTED = re.compile(r"《([^》]+)》")


# ---------------------------------------------------------------- 文字與讀音來源
def say_text(text, says=None):
    """字幕文字 -> 送配音的文字(@say 依序替換,同 freeze.narration_lines)。"""
    for k, v in says or []:
        text = text.replace(k, v)
    return text


def _src(say):
    return C.pron_source(say)


def _keep_positions(src):
    """pron_rules 裡 keep 規則(確認模型預設讀音正確)占住的位置;rule_events 不回 keep,這裡補上。"""
    pos = set()
    for w, _ch, offs, py, _unv in C.RULE_WORDS:
        if py is None:
            i = src.find(w)
            while i >= 0:
                pos.update(i + o for o in offs)
                i = src.find(w, i + 1)
    for pat, ch, py, _unv in C.RULE_REGS:
        if py is None:
            for m in pat.finditer(src):
                a, b = m.span("t") if "t" in pat.groupindex else m.span()
                pos.update(p for p in range(a, b) if src[p] == ch)
    return pos


def _covered(src, spans, ev):
    """詞表區段、規則事件(含 keep)、記憶命中、著 已處理的位置集合。"""
    cov = {p for s, e, _ in spans for p in range(s, e)}
    cov.update(e[0] for e in ev)
    cov.update(_keep_positions(src))
    cov.update(p for p, _e in PM.scan(src))
    cov.update(p for p, ch in enumerate(src) if ch == "著")
    return cov


def known_chars():
    """「已知易錯字」= pron_rules 有條目的字 ∪ 語境讀音記憶的字 ∪ pron_backlog 的字(pron_rules 外兩者是實際唸錯過/測過的)。"""
    mem = {e.get("char") for e in PM.load().get("entries", []) if e.get("char")}
    return set(C.RULE_CHARS) | mem | C._backlog_chars()


def _backlog_rows():
    """[(字, 語境詞, 命中次數, 來源片)],只取狀態「待規則」。"""
    f = C.BACKLOG_FILE
    if not f.exists():
        return []
    out = []
    for ln in f.read_text(encoding="utf-8").splitlines():
        r = [x.strip() for x in ln.split("|")]
        if ln.startswith("|") and len(r) > 7 and r[5] == BACKLOG_PENDING and r[1] != "字":
            out.append((r[1], r[2], r[4], r[6]))
    return out


def subject_names(tag):
    """本片主體名:spec package.subject、brief.topic 裡的《…》;都沒有就取 topic 開頭 4 字(topic 多以片名開頭,B 段還沒有 package)。"""
    def read(name):
        f = P.PROJECTS / tag / name
        try:
            d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        except ValueError:
            return {}
        return d if isinstance(d, dict) else {}

    subj = [s for s in (read("spec.json").get("package") or {}).get("subject") or [] if isinstance(s, str) and len(s) >= 2]
    topic = read("brief.json").get("topic") or ""
    names = subj + QUOTED.findall(topic)
    return list(dict.fromkeys(names)) or ([topic[:4]] if len(topic) >= 4 else [])


def _protected(s, names=()):
    """《…》內與主體名占的位置集合。"""
    pos = {p for m in re.finditer(r"《[^》]*》", s) for p in range(*m.span())}
    for n in names:
        i = s.find(n)
        while i >= 0:
            pos.update(range(i, i + len(n)))
            i = s.find(n, i + 1)
    return pos


def _ctx_outside(s, ctx, names=()):
    """語境詞 ctx 在 s 裡有沒有不是整段落在片名、主體名內的命中。"""
    prot, i = _protected(s, names), s.find(ctx)
    while i >= 0:
        if not prot.issuperset(range(i, i + len(ctx))):
            return True
        i = s.find(ctx, i + 1)
    return False


def _unregistered(say):
    """未登錄英文詞 list;優先用 terms_check(單一來源),沒有就用 tts_cosy_text.analyze。"""
    try:
        import terms_check
        return list(terms_check.unregistered([say]))
    except Exception:  # noqa: BLE001  terms_check 未就緒或讀不了
        return list(C.analyze([say])["unregistered"])


# ---------------------------------------------------------------- 特徵(門檻與實測共用)
def features(say):
    """一句送配音文字的數值特徵 dict:units、clause_max、en_n、en_ratio、digits、poly(未覆蓋的已知易錯字 [(位置, 字)])。"""
    src = _src(say)
    plain = C.TOKEN_RE.sub("", src)
    units = len(UNIT.findall(plain))
    clause_max = max((len(UNIT.findall(c)) for c in CLAUSE.split(plain)), default=0)
    en_n = len(EN.findall(plain))
    digits = len(re.findall(r"[0-9]", plain))
    spans = C._word_spans(src)[0]
    cov = _covered(src, spans, C._live_events(src, spans))
    kc = known_chars() - COMMON_POLY
    poly = [(p, ch) for p, ch in enumerate(src) if ch in kc and p not in cov]
    return dict(src=src, units=units, clause_max=clause_max, en_n=en_n, en_ratio=en_n / units if units else 0.0, digits=digits, poly=poly,
                en_tail=bool(EN.search(plain.rstrip(" 。?!,，、;；:：」』》)）")[-1:] or "")) and en_n > 0)


def _sev(v, warn, err):
    return "err" if err is not None and v >= err else "warn" if warn is not None and v >= warn else None


def check_line(text, says=None, names=()):
    """一句的可唸性命中 -> [{code, severity:"err"|"warn", span, why}]。text = 字幕文字;says = [(鍵, 唸法)](@say,可省,
    已經是送配音文字就不用給);names = 主體名(subject_names),backlog、poly_unmarked 在片名內不報,硬項不受影響。"""
    say = say_text(text, says)
    f, hits = features(say), []
    names = (*names, *QUOTED.findall(text), *QUOTED.findall(say))

    def add(code, sev, span, why):
        hits.append(dict(code=code, severity=sev, span=span, why=why))

    for w in _unregistered(say):
        add("en_unregistered", "err", w, f"英文詞「{w}」沒登錄 cosy_terms,配音前會被擋;改中文說法,或登錄後再用")
    src = f["src"]
    for _p, e in PM.scan(src):   # 記憶 undetermined = 已測過看不出對錯、不再重測、留優先聽,不是寫稿缺陷,不提示
        if PM.blocking(e):
            add("memory_bad", "err", PM.ctx_label(e), f"「{PM.ctx_label(e)}」實測唸錯({e.get('note') or '見 pron_memory'}),此語境要改寫")
    for ch, ctx, _n, tags in _backlog_rows():
        if _ctx_outside(src, ctx, names) or _ctx_outside(say, ctx, names):
            add("backlog", "warn", ctx, f"「{ctx}」在 pron_backlog 待規則({tags}),先加規則或換說法")
    prot = _protected(src, names)
    poly = [(p, ch) for p, ch in f["poly"] if p not in prot]
    if len(poly) >= T["poly_warn"]:
        ex = "、".join(dict.fromkeys(src[max(0, p - 1):p + 2] for p, _ in poly))
        add("poly_unmarked", "warn", ex, f"已知易錯字 {len(poly)} 個沒有詞表/規則/記憶覆蓋:{ex}")
    for code, v, key, label in (("en_dense", f["en_ratio"], "en_ratio", f"英文 {f['en_n']} 詞佔 {f['en_ratio']:.0%}"),
                                ("num_dense", f["digits"], "digits", f"句內仍有 {f['digits']} 位阿拉伯數字沒換成中文唸法(@say)"),
                                ("clause_long", f["clause_max"], "clause", f"最長子句 {f['clause_max']} 字"),
                                ("line_long", f["units"], "line", f"整句 {f['units']} 字")):
        sev = _sev(v, T[key + "_warn"], T[key + "_err"])
        if sev:
            add(code, sev, "", label + f"(門檻 {T[key + '_warn']}" + (f"/{T[key + '_err']}" if T[key + "_err"] is not None else "") + ")")
    if f["units"] < T["short_warn"]:
        add("line_short", "warn", "", f"整句只有 {f['units']} 字(< {T['short_warn']}):易飄聲、鏡頭湊不滿秒數,寫長一點或併入前句")
    if f["en_tail"]:
        add("en_tail", "warn", "", "句尾是英文詞:收尾唸不清楚的機率高,能避就避")
    return hits


# ---------------------------------------------------------------- 整支片
def script_rows(tag):
    """script.txt -> [(行號, 字幕文字, 送配音文字)];@say 與行尾 say 欄位同 freeze.narration_lines。解析失敗 raise ValueError。"""
    import script_txt2json as T2J
    try:
        _, says, sections, _, defs, _ = T2J.parse((P.ROOT / tag / "script.txt").read_text(encoding="utf-8-sig"))
        out = []
        for sec in sections:
            lines = T2J.build_lines(sec["rows"], defs)
            for (no, _tg, text, _ex), ln in zip(sec["rows"], lines):
                out.append((no, text, ln.get("say") or say_text(text, says)))
    except SystemExit as e:
        raise ValueError(str(e.code)) from None
    return out


def check_tag(tag):
    """{lines:[{line, hits}](只列有命中的句), errors:n, warns:n, n_lines:n}。"""
    lines, errs, warns, n = [], 0, 0, 0
    names = subject_names(tag)
    for no, text, say in script_rows(tag):
        n += 1
        hits = check_line(say, names=(*names, *QUOTED.findall(text)))
        if hits:
            lines.append(dict(line=no, hits=hits))
            errs += sum(h["severity"] == "err" for h in hits)
            warns += sum(h["severity"] == "warn" for h in hits)
    return dict(lines=lines, errors=errs, warns=warns, n_lines=n)


def explain():
    """給寫稿 prompt 的短規則(<= 40 行);門檻取自 T,實測依據見 docs\\speakable.md。"""
    en, cl, ln = T["en_ratio_warn"], T["clause_warn"], T["line_warn"]
    rows = [
        "配音(CosyVoice3)寫稿時的可唸性規則;寫完會跑 speakable 預檢,err 必改、warn 能改就改,不改要有理由:",
        "- 英文詞:只用 cosy_terms.json 已登錄或 _direct 的詞;沒登錄的 = err。新詞改中文說法(例:DLC 唸追加內容),英文留字幕與畫面。",
        f"- 英文佔比:一句英文單字數 ÷ 發音單位 >= {en:.0%} 提示;句尾英文能避就避。",
        "- 數字:字幕用阿拉伯數字,配音靠 @say 換中文唸法;句內沒被 @say 換掉的阿拉伯數字 >= %d 位提示。" % T["digits_warn"],
        f"- 子句:以 ,、;:。?! 切開,每個子句 >= {cl} 個發音單位提示(配音會多停);整句 >= {ln} 個發音單位提示。",
        "- 多音字:本句的「已知易錯字」(pron_rules、pron_memory、pron_backlog 有的字)沒被詞表/規則/記憶覆蓋會提示;能換說法就換,別硬賭模型讀對。",
        "- 讀音記憶標 bad 且要改寫的語境 = err;pron_backlog 待規則的語境 = warn,先換說法。",
        "- 不寫太短的句子、不用「啊」結尾、DEI 不放句尾;語助詞照 2_文案 §3 白名單。",
    ]
    return "\n".join(rows)


# ---------------------------------------------------------------- 實測門檻
QC_FAIL_TEXT = {"content", "pron", "term_misread", "pause_misplaced"}   # 內容/讀音類(與聲學類 tail_*、stray_pause 分開)


def calibrate(build_dir=None):
    """掃 build\\*\\tts_qc.json 的最終紀錄,回傳 {n, base:{目標:率}, rows:[(特徵, 區間, n, {目標: 率})]}。
    目標(皆以「這句」為單位):retry = 有任一次合成未過品管(retries > 0);retry3 = 重錄 >= 3 次;
    text = 某次合成因 content/pron/term_misread/pause_misplaced 未過;sim = 最終辨識相似度 < 0.95。"""
    root = Path(build_dir or P.ROOT / "build")
    recs = []
    for f in sorted(root.glob("*/tts_qc.json")):
        try:
            recs += [dict(r, _tag=f.parent.name) for r in json.loads(f.read_text(encoding="utf-8")).get("records", [])]
        except (OSError, ValueError):
            continue
    rows = []
    for r in recs:
        say = r.get("text") or ""
        f = features(say)
        fails = {k for t in r.get("attempts", []) if isinstance(t, dict) for k in t.get("fails", [])}
        rows.append((f, dict(retry=r.get("retries", 0) > 0, retry3=r.get("retries", 0) >= 3, text=bool(fails & QC_FAIL_TEXT), sim=(r.get("sim") or 1) < 0.95)))
    goals = ("retry", "retry3", "text", "sim")

    def rate(sel):
        return {g: (sum(y[g] for _, y in sel), len(sel)) for g in goals}
    out = dict(n=len(rows), base=rate(rows), rows=[])
    cuts = (
        ("units", (0, 16, 20, 30, 40, 45, 99)), ("clause_max", (0, 10, 13, 15, 18, 20, 99)), ("en_n", (0, 1, 2, 3, 99)), ("en_tail", (0, 1, 2)),
        ("en_ratio", (0, 0.001, 0.05, 0.10, 0.15, 0.25, 9)), ("digits", (0, 1, 3, 5, 99)),
        ("npoly", (0, 1, 2, 3, 99)),
    )
    for name, edges in cuts:
        for lo, hi in zip(edges, edges[1:]):
            sel = [(f, y) for f, y in rows if lo <= (len(f["poly"]) if name == "npoly" else int(f[name]) if name == "en_tail" else f[name]) < hi]
            if sel:
                out["rows"].append((name, f"[{lo},{hi})", len(sel), rate(sel)))
    ch = {}
    for f, y in rows:
        for c in {ch_ for _p, ch_ in f["poly"]}:
            ch.setdefault(c, []).append((f, y))
    for c, sel in sorted(ch.items(), key=lambda kv: -len(kv[1]))[:12]:
        out["rows"].append(("poly_char", c, len(sel), rate(sel)))
    return out


def _print_calibrate(res):
    pr = lambda d: "  ".join(f"{g} {a}/{b}={a / b:.0%}" for g, (a, b) in d.items())
    print(f"n={res['n']}\n基準  {pr(res['base'])}")
    for name, rng, n, d in res["rows"]:
        print(f"{name:<10}{rng:<12}n={n:<4}{pr(d)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="可唸性預檢")
    ap.add_argument("tag", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--explain", action="store_true", help="印給寫稿 prompt 的短規則")
    ap.add_argument("--calibrate", action="store_true", help="掃 build\\*\\tts_qc.json 重算特徵未過率")
    a = ap.parse_args(argv)
    if a.explain:
        print(explain())
        return 0
    if a.calibrate:
        _print_calibrate(calibrate())
        return 0
    if not a.tag:
        ap.error("要給 tag")
    r = check_tag(a.tag)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"[speakable] {a.tag}: {r['n_lines']} 句,err {r['errors']} 項、warn {r['warns']} 項(有命中 {len(r['lines'])} 句)")
        for ln in r["lines"]:
            for h in ln["hits"]:
                print(f"  L{ln['line']} {h['severity']:<4} {h['code']:<20} {h['why']}")
    return 1 if r["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
