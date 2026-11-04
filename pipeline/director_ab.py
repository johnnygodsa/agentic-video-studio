r"""director 的 A→B4 步驟與 C 段改句迴圈(Phase 3)。規格:pipeline\docs\director_ab.md §4–§7。

由 director.plan_steps 呼叫 steps();每步 = director 步驟 dict(cmd 或 fn),fn 失敗丟 Block(director 記卡點)。
LLM 一律走 call_llm(預設 llm.call_escalating;測試把 CALL 換成假函式)。不動 GPU;C 段的配音由 make_version 自己走 gpu_lock。
"""
import difflib
import json
import math
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import director as D  # noqa: E402
import paths as P  # noqa: E402
from gates import gate_a, gate_b as GB, gate_b4 as GB4, specs  # noqa: E402

CALL = None  # 測試注入;None = llm.call_escalating
AB_SEGS = ("A", "B", "B4")
MAX_LINT, MAX_SPEAK, MAX_QC, MAX_PRON, MAX_PLAYER = 3, 3, 3, 3, 2
SPOT_MAX = 5  # 旁白改動 ≤ 此句數:編輯審不重跑,玩家審走小範圍(§5)
SIM_MAX, SHRINK_MIN, CLAUSE_MIN = 0.7, 0.6, 8  # 改稿回歸檢查:相鄰句相似度上限、改後字數下限比例、比對子句的最短字數
READ = ("Read", "Grep", "Glob")
WRITE = READ + ("Write",)
EDIT = WRITE + ("Edit",)
WEB = ("WebSearch", "WebFetch")
PRON_FILES = ("pron_rules.json", "cosy_pron.json", "sub_words.txt")
PRON_PATHS = PRON_FILES + ("pron_backlog.md",)
QC_KINDS = ("poly", "particle", "runon")  # garble 不改句(§7)
EDITOR_LOOP = ("連貫",)
PLAYER_MUST = ("錯", "誇大", "推論", "相反", "矛盾", "關掉", "可疑")
PLAYER_ASK = ("錯", "關掉", "誇大", "可疑", "相反")  # r2 還有 → ask_user,不開第三輪
PLAYER_EXTRA = "type 只用 錯/誇大/推論/相反/外行/矛盾/關掉/吵/可疑。人設 channel\\audience\\ 下本頻道 _personas.md。"
# ---- flow v3(PLAN_token重設計_2026-11-03 §2(b);docs\director_ab.md §5「flow v3」)----
EDITOR_V3 = ("連貫", "講兩次", "段間矛盾", "結構")  # B3:編輯審只審 lint 做不到的四類
FACT_TYPES = ("錯", "查無")  # r2 事實專審
HARD_TYPES = ("錯", "關掉")  # 被判這兩類的句一定要改過並驗過,否則問使用者
JUDGE_TYPES = ("誇大", "可疑", "相反")  # 裁決類:revise 後仍在 → 問使用者
MAX_SPOT_LOOP = 2  # revise → spot 迴圈最多兩次
SPOT_BATCH = 20  # 小範圍審一次最多標幾句
NUM_HINT = re.compile(r"數字|日期|金額|%|\d")  # B6:條目點名改數字才准數字集合變
WRITER_TOOLS = ("script_lint.py", "speakable.py", "script_txt2json.py", "facts_check.py", "visual_check.py", "script_structure.py")
WRITER_ALLOWED = tuple(f"Bash(python -X utf8 pipeline{sep}{t}:*)" for t in WRITER_TOOLS for sep in ("/", "\\"))
ASSET_TOOLS = ("assets_*_news.py", "assets_*_clips.py", "clips_lib.py", "clip_scan.py", "news_lib.py")  # B10:素材員只准跑這些
# 不用 `:*`:舊式前綴語法把中間的 * 當字面,assets_*_news.py 會全被擋(rc_3days 實測);改萬用字元語法
ASSET_ALLOWED = tuple(f"Bash(python -X utf8 pipeline{sep}{t}*)" for t in ASSET_TOOLS for sep in ("/", "\\")) + ("Bash(yt-dlp *)", "Read", "Grep", "Glob", "Write", "Edit")
ASSET_V3 = ("【程式主導】代理只做三件事:讀 plan.json 的 claims[].visual 與 facts.md 挑來源網址/時間碼、寫每片 assets_<簡稱>_news.py / clips spec、"
            "跑 --check / clips_lib --check 看文字結果。禁止用 Read 開任何 .png/.jpg/.mp4,不要截圖後自己看圖判斷(check 的 OCR/hl 核對結果就是依據)。"
            "上限 25 次工具呼叫。check 沒過就 ok=false 並在該項寫 why,不要自己開圖。director 會對每個 ok=true 的截圖項再跑一次 --check。"
            "片段來源不在 raw\\ 就用 yt-dlp 下載到 raw\\(照 pipeline\\docs\\assets.md 片段流程,前景跑,先 --skip-download 預檢年齡限制)。")
WRITER_LOG = "warn_log_writer.json"  # B1:寫稿員自檢後保留的警告(行號鍵)

_STR = {"type": "string"}
_INT = {"type": "integer"}
_ARR = lambda props, req=None: {"type": "array", "items": {"type": "object", "properties": props, "required": req or list(props)}}  # noqa: E731
REVIEW_SCHEMA = {"type": "object", "required": ["counts", "items"], "properties": {
    "counts": {"type": "object", "additionalProperties": _INT},
    "items": _ARR({"line": _INT, "type": _STR, "severity": _STR, "text": _STR, "reason": _STR, "fix": _STR})}}
PLAN_SCHEMA = {"type": "object", "required": ["consensus", "claims", "todo", "blocks"], "properties": {
    "consensus": {"type": "array", "items": _STR},
    "claims": _ARR({"id": _STR, "text": _STR, "source": _STR, "abs": _STR, "visual": _STR, "block": _STR}),
    "todo": {"type": "array", "items": _STR},
    "blocks": _ARR({"title": _STR, "claim_ids": {"type": "array", "items": _STR}, "est_sec": {"type": "number"}})}}
MANIFEST_SCHEMA = {"type": "object", "required": ["items"], "properties": {
    "items": _ARR({"claim": _STR, "kind": _STR, "path": _STR, "hl": _STR, "ok": {"type": "boolean"}, "why": _STR},
                  ["claim", "kind", "path", "hl", "ok"])}}  # why 可選(B10:ok=false 的原因)
REVISE_SCHEMA = {"type": "object", "required": ["items", "kept"], "properties": {
    "items": _ARR({"line": _INT, "new_line": _STR, "note": _STR}),
    "kept": _ARR({"key": _STR, "reason": _STR})}}
PRON_SCHEMA = {"type": "object", "required": ["counts", "items"], "properties": {
    "counts": {"type": "object", "additionalProperties": _INT},
    "items": _ARR({"line": _STR, "type": _STR, "word": _STR, "current": _STR, "fix": _STR, "basis": _STR, "status": _STR})}}
APPLY_SCHEMA = {"type": "object", "required": ["added", "backlog"], "properties": {
    "added": _ARR({"file": _STR, "entry": _STR}),
    "backlog": _ARR({"word": _STR, "context": _STR, "action": _STR, "reason": _STR})}}


class Block(Exception):
    """步驟卡點;reason 進 production.json.blocks。"""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _llm(tag, fn, prompt, **kw):
    if CALL is not None:
        return CALL(tag, fn, prompt, **kw)
    import llm
    return llm.call_escalating(tag, fn, prompt, **kw)


def _need(r, what):
    if r.limited:
        raise Block("用量上限")
    if not r.ok:
        raise Block(f"{what} 失敗:{r.error}")
    return r


def _pd(tag):
    return P.PROJECTS / tag


def _script(tag):
    return P.REPO / tag / "script.txt"


def _brief(tag):
    return D._read_json(_pd(tag) / "brief.json") or {}


def _plan(tag):
    return D._read_json(_pd(tag) / "plan.json") or {}


def _write_json(path, data):
    D._atomic_write(path, data)


def flow(tag):
    """brief.flow:缺 = "v2"(現行路徑);"v3" = B 段新路徑。單一來源 specs.flow(gate_b 也讀)。"""
    return specs.flow(tag)


def _newer_all(a, *inputs):
    """a 存在且比每個存在的 input 新;回傳略過原因或 None。"""
    a = Path(a)
    if a.exists() and all(D._newer(a, b) for b in inputs):
        return f"{a.name} 已有且比輸入新"
    return None


def write_brief(tag, fields):
    """合併寫 projects\\<tag>\\brief.json;回傳完整內容。"""
    cur = _brief(tag)
    cur.update({k: v for k, v in fields.items() if v not in (None, [], "")})
    cur["tag"] = tag
    _write_json(_pd(tag) / "brief.json", cur)
    return cur


# ---------- 改句:line_fix / revise / warn_log ----------

def _numbers(text):
    """句內數字:阿拉伯數字本身與不含阿拉伯數字的中文數字群(「73.1 萬」只看 73.1,換單位不算掉數字)。"""
    import line_fix as LF
    return {x for x in LF.numbers(text) if not re.search(r"\d", x) or re.fullmatch(r"[\d.]+", x)}


def _clauses(s):
    return [c.strip() for c in re.split(r"[,\uff0c、;\uff1b:\uff1a。?\uff1f!\uff01]", s) if len(c.strip()) >= CLAUSE_MIN]


def _similar(a, b):
    """整句相似度,與較長子句的重疊度(最長相同片段 ÷ 較短子句)取大:同一句話夾在兩個長句裡,整句比不出來。"""
    def overlap(x, y):
        return difflib.SequenceMatcher(None, x, y, autojunk=False).find_longest_match(0, len(x), 0, len(y)).size / min(len(x), len(y))

    return max([difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()] + [overlap(x, y) for x in _clauses(a) for y in _clauses(b)])


def regress_why(old, new, prev="", nxt="", reason="", names=()):
    """改前 old、改後 new 逐句回歸檢查;回退回原因,過關回 None。reason = 這句為什麼要改;names = 主體名(revise 另加 hl 字串)。"""
    gone = [n for n in (*re.findall(r"《[^》]+》", old), *names) if n in old and n not in new]
    if gone:
        return f"專名不見了:{'、'.join(dict.fromkeys(gone))}"
    if not re.search(r"數字|NUMS|num_dense", reason):
        lost = _numbers(old) - _numbers(new) - _numbers(reason)
        if lost:
            return f"數字不見了:{'、'.join(sorted(lost))}"
    for side in (prev, nxt):
        if side and _similar(new, side) >= SIM_MAX:
            return f"與相鄰句重複:{side[:20]}"
    a, b = len(re.sub(r"\s", "", old)), len(re.sub(r"\s", "", new))
    if b < a * SHRINK_MIN:
        return f"字數掉太多:{a} → {b}"
    return None


def changed_pairs(old, new):
    """兩份句子清單逐句對應,回內容有變的 [(old 索引, new 索引)];句數變動時對應不到的句子不列。"""
    if len(old) == len(new):
        return [(i, i) for i, (a, b) in enumerate(zip(old, new)) if a != b]
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if op == "replace" and i2 - i1 == j2 - j1:
            out += zip(range(i1, i2), range(j1, j2))
    return out


def changed_lines(old, new):
    """比對兩份句雜湊清單:回 (改動句數, 新稿要看的句號 1 起算);刪句算一句,看刪除點的下一句。"""
    count, lines = 0, set()
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if op != "equal":
            count += max(i2 - i1, j2 - j1)
            lines.update(range(j1 + 1, j2 + 1) or [min(j1 + 1, len(new))])
    return count, sorted(x for x in lines if x > 0)


def _raw_lines(tag):
    """script.txt 原始行(以 \\n 切,保留 \\r);沒檔回 None。"""
    path = _script(tag)
    return path.read_bytes().decode("utf-8").split("\n") if path.exists() else None


def _restore(tag, back):
    """back = {行號: 原始整行};只換這幾行,其他行與換行格式不動。"""
    els = _raw_lines(tag)
    for no, raw in back.items():
        els[no - 1] = raw
    _script(tag).write_bytes("\n".join(els).encode("utf-8"))


def _rows(tag):
    try:
        return GB.narration(tag)
    except (ValueError, OSError):
        return []


def _subjects(tag):
    import speakable
    return speakable.subject_names(tag)


def _regress_key(text):
    return f"regress:{GB.sha8(text)}"


def _locked(tag):
    """回歸檢查退回過的句:{行號: 退回原因},不再送 line_fix / revise。"""
    log = GB.warn_log(tag)
    return {r[0]: log[_regress_key(r[1])].get("reason", "") for r in _rows(tag) if _regress_key(r[1]) in log}


def _guard_fix(tag, items, res, raw):
    """line_fix 改到的句逐條回歸檢查;退回的句回復原文、記 regress 鎖,從 fixed 移到 unresolved(_record_fix 記 kept)。"""
    fixed = [f for f in res.get("fixed") or [] if "old" in f and "new" in f]
    if not fixed:
        return res
    rows, names, back = _rows(tag), _subjects(tag), {}
    index = {r[0]: i for i, r in enumerate(rows)}
    why = {i["line"]: " ".join(i.get("reasons") or []) for i in items}
    for f in fixed:
        i = index.get(f["line"])
        if i is None:
            continue
        side = (rows[i - 1][1] if i else "", rows[i + 1][1] if i + 1 < len(rows) else "")
        bad = regress_why(f["old"], f["new"], *side, why.get(f["line"], ""), names)
        if bad:
            back[f["line"]] = (f["old"], f"回歸檢查退回:{bad}")
    if not back:
        return res
    _restore(tag, {no: raw[no - 1] for no in back})
    merge_warn_log(tag, {_regress_key(old): {"action": "kept", "reason": bad} for old, bad in back.values()})
    stale = {str(no) for no in back}
    return {**res, "fixed": [f for f in res["fixed"] if f["line"] not in back],
            "warn_log": [e for e in res.get("warn_log") or [] if e.get("key", "").partition(":")[2].partition(":")[0] not in stale],
            "unresolved": [*(res.get("unresolved") or []), *({"line": no, "why": bad} for no, (_old, bad) in back.items())]}


def _fix(tag, items, mode):
    """line_fix.fix_lines;回傳其結果。模組未就緒或用量上限 → Block。
    lint/speak 改完逐句回歸檢查(_guard_fix),退回過的句不再送;qc 屬 C 段,不檢查。"""
    lf = GB.module("line_fix")
    if lf is None:
        raise Block("line_fix.py 未就緒")
    raw, held = (_raw_lines(tag), _locked(tag)) if mode != "qc" else (None, {})
    todo = [i for i in items if i["line"] not in held]
    res = lf.fix_lines(tag, todo, mode, call=CALL) if todo or not items else {}
    if res.get("refused"):
        raise Block(f"line_fix 拒絕:{res['refused']}")
    if res.get("limited") or any("用量上限" in str(u.get("why")) for u in res.get("unresolved") or []):
        raise Block("用量上限")
    if raw is not None:
        res = _guard_fix(tag, items, res, raw)
    skip = [{"line": i["line"], "why": held[i["line"]]} for i in items if i["line"] in held]
    return {**res, "unresolved": [*(res.get("unresolved") or []), *skip]} if skip else res


def merge_warn_log(tag, recs):
    """recs = {key: {action, reason}};補 at 後併進 warn_log.json。"""
    if not recs:
        return
    log = GB.warn_log(tag)
    for k, v in recs.items():
        log[k] = {"action": v["action"], "reason": v.get("reason", ""), "at": D.now_iso()}
    _write_json(_pd(tag) / "warn_log.json", log)


def _hash_key(key, texts):
    """line_fix 回報的行號鍵 → 句雜湊鍵(它的 speakable 正名成 gate 的 speak);對不到句子照舊。"""
    chk, _, rest = key.partition(":")
    no, _, code = rest.partition(":")
    text = texts.get(int(no)) if no.isdigit() else None
    return f"{'speak' if chk == 'speakable' else chk}:{GB.sha8(text)}:{code}" if text and code else key


def _carry_kept(tag, pairs):
    """pairs = [(舊句, 新句)]:舊句上 kept 的警告跟到新句(同舊的行號鍵行為),不用為改別的項目再送一次 line_fix。"""
    log, recs = GB.warn_log(tag), {}
    for old, new in pairs:
        a, b = GB.sha8(old), GB.sha8(new)
        for k, v in log.items():
            chk, _, rest = k.partition(":")
            if rest.startswith(f"{a}:") and v.get("action") == "kept":
                recs[f"{chk}:{b}:{rest[len(a) + 1:]}"] = v
    merge_warn_log(tag, recs)


def _record_fix(tag, warns, res):
    """把 line_fix 結果對到警告鍵:改到的句 = fixed,未解決 = kept(why 當理由);回報的 warn_log 優先。
    warns 的鍵是改前算的;回報的行號鍵用改前句文字換成雜湊鍵。"""
    fixed = {f["line"] for f in res.get("fixed") or []}
    why = {u["line"]: u.get("why", "") for u in res.get("unresolved") or []}
    texts = {r[0]: r[1] for r in _rows(tag)}
    texts.update({f["line"]: f["old"] for f in res.get("fixed") or [] if "old" in f})
    recs = {}
    for w in warns:
        if w["line"] in fixed:
            recs[w["key"]] = {"action": "fixed", "reason": "line_fix"}
        elif w["line"] in why:
            recs[w["key"]] = {"action": "kept", "reason": why[w["line"]]}
    for e in res.get("warn_log") or []:
        key = e.get("key") or f"{e.get('check')}:{e.get('line')}:{e.get('code')}"
        recs[_hash_key(key, texts)] = {"action": e.get("action", "kept"), "reason": e.get("reason", "")}
    merge_warn_log(tag, recs)
    _carry_kept(tag, [(f["old"], f["new"]) for f in res.get("fixed") or [] if "old" in f and "new" in f])


def _frozen(tag):
    if (_pd(tag) / "freeze.json").exists():
        import freeze as FZ
        return FZ.check(tag) is None
    return False


def script_rows(tag):
    """旁白句號 -> script.txt 行號(1 起算),與 script_txt2json 同源。"""
    import script_txt2json as T2J
    text = _script(tag).read_text(encoding="utf-8-sig")
    try:
        _, _, sections, *_ = T2J.parse(text)
    except SystemExit as e:
        raise Block(f"script.txt 解析失敗:{e.code}") from None
    return {i: row[0] for i, row in enumerate((r for s in sections for r in s["rows"]), 1)}


def apply_lines(tag, items):
    """套用 [{line:句號, new_line}]:換掉該行「標籤|」之後、「 ;; 」之前的字;回傳改到的句號。"""
    rows = script_rows(tag)
    path = _script(tag)
    src = path.read_text(encoding="utf-8-sig").splitlines()
    done = []
    for it in items:
        no = rows.get(it.get("line"))
        new = (it.get("new_line") or "").strip()
        if not no or not new:
            continue
        head, sep, body = src[no - 1].partition("|")
        if not sep:
            head, sep, body = "", "", src[no - 1]
        tail = body.rpartition(" ;; ")[2] if " ;; " in body else None
        new = new.partition(" ;; ")[0].rpartition("|")[2]
        src[no - 1] = f"{head}{sep}{new}" + (f" ;; {tail}" if tail is not None else "")
        done.append(it["line"])
    path.write_text("\n".join(src) + "\n", encoding="utf-8")
    return done


def _guard_revise(tag, raw, before, notes):
    """revise 後逐句比對,改壞的句回復原文、記 regress 鎖;回 ({新稿句號: 原因}, {改前行號: 原因})。對不到的句子保留 revise 結果。"""
    import line_fix as LF
    after, names = _rows(tag), _subjects(tag)
    old, new = [r[1] for r in before], [r[1] for r in after]
    bad, bad_lines, restore, recs, pairs = {}, {}, {}, {}, []
    for i, j in changed_pairs(old, new):
        side = (new[j - 1] if j else "", new[j + 1] if j + 1 < len(new) else "")
        why = regress_why(old[i], new[j], *side, notes.get(j + 1, ""), (*names, *LF._hl_list(before[i][3])))
        if not why:
            pairs.append((old[i], new[j]))
            continue
        bad[j + 1] = bad_lines[before[i][0]] = f"回歸檢查退回:{why}"
        restore[after[j][0]] = raw[before[i][0] - 1]
        recs[_regress_key(old[i])] = {"action": "kept", "reason": bad[j + 1]}
    if restore:
        _restore(tag, restore)
    merge_warn_log(tag, recs)
    _carry_kept(tag, pairs)
    return bad, bad_lines


def revise_why(old, new, extra=None, hint=""):
    """B6:revise 的 new_line 機械驗(line_fix.validate 同等項);回退回原因或 None。hint = 該句條目的 reason/fix。"""
    import line_fix as LF
    new = (new or "").strip()
    if not new:
        return "new_line 是空的"
    if "\n" in new or "\r" in new or "|" in new or LF.EXTRA_SEP.strip() in new:
        return "new_line 不可含換行、|、;;(只放旁白文字,不含標籤與行尾 json)"
    if not NUM_HINT.search(hint or "") and LF.numbers(new) != LF.numbers(old):
        a, b = LF.numbers(old) - LF.numbers(new), LF.numbers(new) - LF.numbers(old)
        return f"數字集合不同(少了 {sorted(a)}、多了 {sorted(b)});條目沒要改數字就原樣保留"
    miss = [h for h in LF._hl_list(extra or {}) if h in old and h not in new]
    if miss:
        return f"行尾 hl 必留字串不見了:{miss}"
    return None


def _issue_hint(issues, line):
    return " ".join(str(i.get(k) or "") for i in issues if isinstance(i, dict) and i.get("line") == line for k in ("reason", "fix"))


def _revise_call(tag, issues, warns, what, seg, fn="revise"):
    keys = "\n".join(f"- {w['key']}:{w['why']}" for w in warns) or "(無)"
    prompt = (f"改稿:projects\\{tag} 這支片,文案 {tag}\\script.txt,查證 projects\\{tag}\\facts.md。\n"
              f"下列 {what} 要處理(line = 第幾句旁白,從 1 起算,# 段標題與 @ 指令行不算):\n"
              f"{json.dumps(list(issues), ensure_ascii=False)}\n"
              f"下列警告能改就順手改,不改的放 kept 寫理由(key 照抄):\n{keys}\n"
              "不要動檔案;只回 JSON:items=[{line,new_line,note}](new_line 只放旁白文字,不含標籤與行尾 json),kept=[{key,reason}]。")
    return _need(_llm(tag, fn, prompt, agent="script-writer", model="opus", effort="medium", tools=READ,
                      schema=REVISE_SCHEMA, seg=seg), "revise").data


def _checked(tag, issues, items, before, what, seg, unresolved):
    """B6:驗 revise 回的每條;不過的帶原因重送一次(只送不過的),再不過不套用、記 unresolved。回 (可套用的 items, 重送回的 kept)。"""
    rows = dict(enumerate(before, 1))

    def bad_of(its):
        out = {}
        for it in its:
            r = rows.get(it.get("line"))
            why = r and revise_why(r[1], it.get("new_line"), r[3] if len(r) > 3 else {}, _issue_hint(issues, it["line"]))
            if why:
                out[it["line"]] = (it, why)
        return out

    bad = bad_of(items)
    if not bad:
        return items, []
    retry = [{"line": n, "rejected": it.get("new_line"), "why": why,
              "issues": [i for i in issues if isinstance(i, dict) and i.get("line") == n]} for n, (it, why) in bad.items()]
    data = _revise_call(tag, retry, (), f"{what}(上次的改句被機械驗退回,照 why 重改)", seg, fn="revise_retry")
    again = [it for it in data.get("items") or [] if it.get("line") in bad]
    still = bad_of(again)
    ok = [it for it in again if it["line"] not in still]
    unresolved += [{"line": n, "why": (still.get(n) or bad[n])[1]} for n in bad if n not in {it["line"] for it in ok}]
    return [it for it in items if it.get("line") not in bad] + ok, list(data.get("kept") or [])


def revise(tag, issues, warns=(), seg="B", what="審稿條目", check=False, unresolved=None):
    """改內容(Opus medium,script-writer);line_fix 不得改意思,這裡可以。回傳改到的句號(回歸檢查退回的不算)。
    check=True(v3,B6):new_line 先機械驗,不過退回重送一次,再不過不套用、記進 unresolved(list)。"""
    if _frozen(tag):
        raise Block("文案已凍結,revise 拒絕")
    held = _locked(tag)
    if held:
        no_of = script_rows(tag)
        issues = [i for i in issues if not (isinstance(i, dict) and no_of.get(i.get("line")) in held)]
        if not issues and not warns:
            return []
    raw, before = _raw_lines(tag), _rows(tag)
    data = _revise_call(tag, issues, warns, what, seg)
    items, kept_in = data.get("items") or [], list(data.get("kept") or [])
    if check:
        items, more = _checked(tag, list(issues), items, before, what, seg, unresolved if unresolved is not None else [])
        kept_in += more
    done = apply_lines(tag, items)
    notes = {}
    for it in (*(i for i in issues if isinstance(i, dict)), *items):
        notes[it.get("line")] = " ".join((notes.get(it.get("line"), ""), *(str(it.get(k) or "") for k in ("reason", "fix", "note"))))
    bad, bad_lines = _guard_revise(tag, raw, before, notes) if raw else ({}, {})
    kept = {k["key"]: {"action": "kept", "reason": k.get("reason", "")} for k in kept_in}
    kept.update({w["key"]: {"action": "kept", "reason": bad_lines[w["line"]]} for w in warns if w["line"] in bad_lines})
    fixed = {w["key"]: {"action": "fixed", "reason": "revise"} for w in warns if w["key"] not in kept}
    merge_warn_log(tag, {**fixed, **kept})
    return [n for n in done if n not in bad]


# ---------- A 段 ----------

def _context_cmd(tag, brief):
    cmd = D._sys() + [D._script("context_pack.py"), "--tag", tag, "--channel", brief.get("channel") or "<channel?>"]
    if brief.get("event"):
        cmd += ["--event", brief["event"]]
    if brief.get("query"):
        cmd += ["--query", brief["query"]]
    return cmd


def comment_urls(tag):
    """brief.urls,否則 context.json 的 comment_sources 裡帶 url/video_id 的項目。"""
    urls = list(_brief(tag).get("urls") or [])
    if urls:
        return urls
    for s in (D._read_json(_pd(tag) / "context.json") or {}).get("comment_sources") or []:
        if isinstance(s, dict):
            u = s.get("url") or (f"https://www.youtube.com/watch?v={s['video_id']}" if s.get("video_id") else None)
            if u:
                urls.append(u)
    return urls


def step_comments(tag, ctx, a):
    urls = comment_urls(tag)
    if not urls:
        D._warn(tag, "A", "comments", "brief.urls 與 context 都沒有同題片網址,跳過")
        return
    out = _pd(tag) / "comments_ref"
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["yt-dlp", "--write-comments", "--skip-download", "--no-warnings", "-o", str(out / "%(id)s.%(ext)s"), *urls]
    rc, text, _ = D._exec(tag, a.ver or "ab", "A", "comments", cmd)
    if rc != 0:
        D._warn(tag, "A", "comments", f"yt-dlp 結束碼 {rc}:{D._tail(text)}")


def _validate_plan(r):
    d = r.data or {}
    if not 3 <= len(d.get("consensus") or []) <= 5:
        return "consensus 要 3–5 行"
    bad = [str(c.get("id")) for c in d.get("claims") or [] if not all(c.get(k) for k in gate_a.CLAIM_KEYS)]
    if bad or not d.get("claims"):
        return f"claims 不可空,source/abs/visual 都要填;缺:{'、'.join(bad)}"
    return None


def step_consensus(tag, ctx, a):
    pd = f"projects\\{tag}"
    prompt = (f"開工資料 {pd}\\brief.json。讀 {pd}\\context.md §4、{pd}\\comments_ref\\(有就讀,大檔用 Grep)、brief。\n"
              "輸出 JSON:consensus 玩家共識 3–5 行;claims 論點清單,每點 id/text/source(來源)/abs(絕對值)/visual(畫面)/block;"
              "todo 還要查的說法;blocks 分塊 [{title, claim_ids, est_sec}],估秒照實,不灌水。\n"
              "visual 是玩家留言的論點寫「留言卡:<原句>」(字卡,不截圖)。")
    r = _need(_llm(tag, "consensus", prompt, agent="ab-planner", model="sonnet", tools=READ, schema=PLAN_SCHEMA,
                   seg="A", validate=_validate_plan), "consensus")
    _write_json(_pd(tag) / "plan.json", r.data)
    _write_json(_pd(tag) / "plan_draft.json", r.data)


def step_research(tag, ctx, a):
    todo = _plan(tag).get("todo") or []
    out = _pd(tag) / "facts_raw1.md"
    prompt = (f"待查清單(一次查完,每條照你的格式寫進 projects\\{tag}\\facts_raw1.md):\n" + "\n".join(f"- {t}" for t in todo)
              + f"\n開工資料 projects\\{tag}\\brief.json;brief.urls 有網址先讀。")
    _need(_llm(tag, "research", prompt, agent="researcher", model="haiku", tools=WRITE + WEB, seg="A",
               validate=lambda r: None if out.exists() else "facts_raw1.md 沒寫"), "research")


def _validate_facts(tag):
    def check(r):
        f = _pd(tag) / "facts.md"
        if not f.exists():
            return "facts.md 沒寫"
        n = D.count_pending_facts(f)
        return f"facts.md 還有待查 {n} 條,查不到要標查無或改說法" if n else None
    return check


def step_facts(tag, ctx, a):
    pd = f"projects\\{tag}"
    prompt = (f"把 {pd}\\facts_raw*.md 整理成 {pd}\\facts.md:欄位照 channel\\規則\\2_文案.md §5 閘門 2 事實核對表,"
              f"檔頭放 {pd}\\plan.json 的 consensus(玩家共識段),待查 0。查不到的標查無,不用印象補。只回一行統計。")
    _need(_llm(tag, "facts", prompt, agent="ab-planner", model="sonnet", effort="high", tools=WRITE, seg="A",
               validate=_validate_facts(tag)), "facts")


def step_replan(tag, ctx, a):
    """consensus 的論點在查證前寫的;facts 出來後依查到的東西重排 claims/blocks,不足片長照實寫(gate_a 判)。"""
    pd = f"projects\\{tag}"
    brief = D._read_json(_pd(tag) / "brief.json") or {}
    sp = specs.spec(brief.get("channel"), brief.get("format"))
    span = f"{sp['target'][0]}–{sp['target'][1]} 分" if sp.get("target") else "不設"
    if sp.get("target"):  # 長篇片:塊數跟片長走(一塊約 130 秒),上限 12 塊
        n_lo = math.ceil(sp["target"][0] * 60 / 130)
        n_hi = min(12, math.ceil(sp["target"][1] * 60 / 130))
        nblk = f"約 {min(n_lo, n_hi)}–{n_hi} 塊"
    else:
        nblk = "約 4–5 塊"
    prompt = (f"查證做完了,依 {pd}\\facts.md 重排 {pd}\\plan.json 的論點。另讀 {pd}\\brief.json;facts.md 有「主對話裁定」段就照它。\n"
              "輸出 JSON:consensus 沿用,被 facts 推翻的改寫;claims 只用核對狀態不是查無的編號,source 寫 F 編號與網址,"
              "abs 寫絕對值,visual 寫可截圖的網址與要標的原字,或片段標籤;block 填所屬分塊;"
              f"blocks 一塊 90–150 秒含 1–2 論點,{nblk},目標片長 {span},est_sec 照實不灌水,撐不到就照實少寫;todo 給空陣列。\n"
              "visual 是玩家留言的論點寫「留言卡:<原句>」(字卡,不截圖)。")
    r = _need(_llm(tag, "replan", prompt, agent="ab-planner", model="sonnet", effort="high", tools=READ, schema=PLAN_SCHEMA,
                   seg="A", validate=_validate_plan), "replan")
    _write_json(_pd(tag) / "plan.json", {**r.data, "todo": [], "replanned": True})


def _asset_call(tag, kind):
    pd = f"projects\\{tag}"
    what = {"screen": "網頁截圖(news_lib / news_specs,--check 0 錯、hl 原字核對)",
            "clip": ("影片片段(clips_lib、clip_scan,clips_lib --check 達標)。片段是全片共用池,manifest 只列一項 claim=clips;"
                     "raw\\ 已有同遊戲素材就沿用,從其他 projects\\*\\clips.json 找 sources")}[kind]
    prompt = (f"依 {pd}\\plan.json 的 claims[].visual 備素材,這次只做:{what}。做法 pipeline\\docs\\assets.md 對應節;查證對照 {pd}\\facts.md。\n"
              "visual 是字卡、圖表、動畫等非網頁的論點不用備也不要列;"
              "回 JSON:items=[{claim,kind,path,hl,ok}],kind 填 " + kind + ",ok 只有檢查真的過才 true;做不到的項目也要列(ok=false)。")
    kw = {"tools": EDIT + ("Bash",), "allowed": ASSET_ALLOWED, "effort": "low"} if flow(tag) == "v3" else {"tools": EDIT + ("Bash",)}
    if kw.get("effort"):
        prompt += "\n" + ASSET_V3
    return _llm(tag, f"assets_{kind}", prompt, agent="asset-collector", model="sonnet", schema=MANIFEST_SCHEMA, seg="A", **kw)


def _news_scripts(tag):
    """B10:本片的 assets_*_news.py → 輸出前綴。以 main(SPECS, "<tag>"…) 的 tag 比對;前綴取 prefix="…",缺則 <tag>_。"""
    out = {}
    for f in sorted((Path(__file__).resolve().parent).glob("assets_*_news.py")):
        try:
            txt = f.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"main\(\s*\w+\s*,\s*[\"']([^\"']+)[\"']([^\n]*)", txt)
        if m and m.group(1) == tag:
            pm = re.search(r"prefix\s*=\s*[\"']([^\"']*)[\"']", m.group(2))
            out[f] = pm.group(1) if pm else f"{tag}_"
    return out


def _run_check(script, names):
    """跑 assets_*_news.py <name> --check(news_lib.main 的 --check 介面);回 (退出碼, 輸出尾段)。"""
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", str(script), "--check", *names], cwd=str(P.REPO), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, f"check 無法執行:{e}"
    return r.returncode, "\n".join(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-6:])


def verify_screens(tag, items):
    """B10(v3):對 manifest 每個 ok=true 的截圖項自己跑一次 --check(逐項),不過改 ok=false 附 why;代理謊報也抓得到。"""
    scripts = _news_scripts(tag)
    for it in items:
        if not (it.get("ok") and it.get("kind") == "screen"):
            continue
        stem = Path(str(it.get("path") or "")).stem
        hit = [(len(pre), f, pre) for f, pre in scripts.items() if stem.startswith(pre) and len(stem) > len(pre)]
        if not hit:
            it["ok"], it["why"] = False, f"程式複驗:找不到產出 {stem} 的 assets_*_news.py(main 的 tag 要是 {tag})"
            continue
        top = max(h[0] for h in hit)
        cand = [(f, pre) for n, f, pre in hit if n == top]
        if len(cand) > 1:  # 同前綴多支腳本:優先選 SPECS 含該名稱的,再取 mtime 最新
            name = stem[top:]
            def _has(f):
                try:
                    return f'"{name}":' in f.read_text(encoding="utf-8")
                except OSError:
                    return False
            f, pre = max(cand, key=lambda c: (_has(c[0]), c[0].stat().st_mtime))
        else:
            f, pre = cand[0]
        rc, out = _run_check(f, [stem[len(pre):]])
        if rc:
            it["ok"], it["why"] = False, f"程式複驗 --check 未過:{out[-300:]}"
    return items


def step_assets(tag, ctx, a):
    with ThreadPoolExecutor(2) as ex:
        rs = list(ex.map(lambda k: _asset_call(tag, k), ("screen", "clip")))
    items = []
    for r, name in zip(rs, ("assets_screen", "assets_clip")):
        items += _need(r, name).data.get("items") or []
    if flow(tag) == "v3":
        verify_screens(tag, items)
    _write_json(_pd(tag) / "assets_manifest.json", items)


# ---------- B 段 ----------

def _taste_b():
    """channel\\taste\\README.md 裡段別 B 的案例列(摘要,≤20 行)。"""
    f = P.ROOT / "channel" / "taste" / "README.md"
    if not f.exists():
        return "(無)"
    return "\n".join([l for l in f.read_text(encoding="utf-8").splitlines() if re.match(r"\|\s*T\d+\s*\|\s*B\s*\|", l)][:20]) or "(無)"


def _channel_file(tag):
    name = specs.channel_key(_brief(tag).get("channel"))
    return f"channel\\規則\\頻道_{name}.md"


def step_write(tag, ctx, a):
    sp = GB.module("speakable")
    if sp is None:
        raise Block("speakable.py 未就緒")
    pd = f"projects\\{tag}"
    brief = _brief(tag)
    s = specs.spec(brief.get("channel"), brief.get("format"))
    length = f"目標片長 {s['target'][0]}–{s['target'][1]} 分" if s["target"] else "不設片長"
    prompt = (f"寫稿 {tag}。輸入:{pd}\\brief.json、{pd}\\plan.json、{pd}\\facts.md、{pd}\\assets_manifest.json、{_channel_file(tag)}、"
              f"channel\\規則\\2_文案.md §1–§3 §6。{length},一分鐘約 {specs.SPEECH_CPM} 字。\n"
              f"輸出:{tag}\\script.txt 與 {pd}\\outline.md。截圖前綴寫在說明行「前綴 xx_」,img: 標籤不含前綴(images\\xx_name.png 寫 img:name)。\n\n可唸性規則:\n{sp.explain()}\n\n以前犯過的錯(不要再犯):\n{_taste_b()}")
    v3 = flow(tag) == "v3"
    kw = {"tools": EDIT + ("Bash",), "allowed": EDIT + WRITER_ALLOWED} if v3 else {"tools": EDIT}
    if v3:
        prompt += _selfcheck_prompt(tag)
    out, t0 = _script(tag), time.time()
    _need(_llm(tag, "write", prompt, agent="script-writer", model="opus", effort="high", seg="B", **kw,
               validate=lambda r: None if out.exists() and (_pd(tag) / "outline.md").exists() else "script.txt / outline.md 沒寫"), "write")
    if v3:
        merge_writer_log(tag, since=t0)


def _selfcheck_prompt(tag):
    """B1(v3):寫稿員寫完自己跑檢查到全過;剩下的警告寫 warn_log_writer.json(行號鍵),director 換成句雜湊鍵。"""
    pd = f"projects\\{tag}"
    cmds = (f"script_txt2json.py {tag}/script.txt [--img-prefix 前綴_]", f"script_structure.py {tag}",
            f"visual_check.py --tag {tag} --table", f"facts_check.py {tag}", f"script_lint.py {tag} --all", f"speakable.py {tag}")
    return ("\n\n寫完自檢(Bash 只准下列指令,路徑用正斜線,其他指令會被拒):\n" + "\n".join(f"- python -X utf8 pipeline/{c}" for c in cmds)
            + "\n跑到全過才結束:script_lint 擋 0、speakable 硬項 0、facts_check 未連結/狀態不符/錯誤 0、visual_check 錯誤 0。"
            f"\n剩下的警告能改就改;不改的每條寫進 {pd}\\{WRITER_LOG} = [{{check, line, code, action:\"kept\", reason}}]"
            "(check 只用 lint/speak/structure;line = script.txt 行號;code 照工具印的代碼;reason 寫為什麼保留)。"
            "\n整個工作上限約 30 次工具呼叫,到了就停,沒清的留給 director。")


def merge_writer_log(tag, since=0.0):
    """B1:warn_log_writer.json(寫稿員自檢,行號鍵)→ 句雜湊鍵(與 gate_b.warnings 同法)併進 warn_log,action kept。
    檔比 since 舊(上一次寫稿留下的)不併;回併入筆數。"""
    f = _pd(tag) / WRITER_LOG
    if not f.exists() or f.stat().st_mtime < since:
        return 0
    data, rows, recs = D._read_json(f), _rows(tag), {}
    for e in data if isinstance(data, list) else []:
        if not isinstance(e, dict) or not e.get("code") or not e.get("reason") or not str(e.get("line", "")).isdigit():
            continue
        chk, line = {"speakable": "speak"}.get(e.get("check"), e.get("check")), int(e["line"])
        mark = GB.warn_mark(chk, line, rows)
        recs[f"{chk}:{line}:{e['code']}" if mark is None else f"{chk}:{GB.sha8(mark)}:{e['code']}"] = {
            "action": "kept", "reason": f"寫稿員:{e['reason']}"}
    merge_warn_log(tag, recs)
    return len(recs)


def _speak_errs(report):
    """speakable.check_tag 的硬項 -> line_fix items。"""
    out = []
    for row in report.get("lines") or []:
        why = [f"{h['code']}:{h.get('why', '')}" for h in row.get("hits") or [] if h.get("severity") == "err"]
        if why:
            out.append({"line": row["line"], "reasons": why})
    return out


def step_speak(tag, ctx=None, a=None):
    """speakable 硬項 → line_fix(mode=speak);≤3 輪,仍有 = 卡點。"""
    report = GB.speak_report(tag)
    if report is None:
        raise Block("speakable.py 未就緒")
    for _ in range(MAX_SPEAK):
        items = _speak_errs(report)
        if not items:
            return
        _fix(tag, items, "speak")
        report = GB.speak_report(tag)
    if _speak_errs(report):
        raise Block(f"speakable 硬項 {report.get('errors')} 條,{MAX_SPEAK} 輪未清")


def _txt2json(tag):
    """參數與 make_version 同:輸入 <tag>/script.txt、前綴讀說明行(沒寫就走預設,visual_check 會報)。"""
    import make_version as MV
    prefix = MV.script_img_prefix(tag)
    return GB.tool("script_txt2json.py", f"{tag}/script.txt", *(["--img-prefix", prefix] if prefix else []))


def lint_round(tag):
    """跑四個檢查(txt2json → structure → visual --table → lint);回 {sent, warns, struct}。"""
    rc, text = _txt2json(tag)
    if rc != 0:
        raise Block(f"script_txt2json 失敗:{D._tail(text)}")
    GB.tool("script_structure.py", tag)
    struct = []
    ve = GB.visual_errors(tag, "--table")
    if ve != 0:
        struct.append(f"visual_check 錯誤 {ve}")
    fs = GB.facts_stat(tag)
    if fs != (0, 0, 0):
        struct.append(f"facts_check 未連結/狀態不符/錯誤 {fs}")
    sent = GB.sentence_hits(tag)
    if sent is None:
        raise Block("script_lint.check_sentences 未就緒")
    blocks = [s for s in sent if s.get("block")]
    n = GB.lint_over(tag)
    if n and not blocks:
        struct.append(f"script_lint 超標 {n} 項(非句級)")
    return {"sent": blocks, "warns": GB.unrecorded(tag), "struct": struct}


def _reasons(hits):
    by = {}
    for h in hits:
        by.setdefault(h["line"], []).append(f"{h['code']}:{h.get('why', '')}")
    return [{"line": k, "reasons": v} for k, v in by.items()]


def step_lint(tag, ctx=None, a=None):
    """句級 → line_fix;結構級 → revise;≤3 輪。警告進 warn_log。"""
    for _ in range(MAX_LINT):
        st = lint_round(tag)
        if not st["sent"] and not st["warns"] and not st["struct"]:
            return
        line_warns = [w for w in st["warns"] if w["check"] != "structure"]
        struct_warns = [w for w in st["warns"] if w["check"] == "structure"]
        if st["sent"] or line_warns:
            res = _fix(tag, _reasons(st["sent"] + line_warns), "lint")
            _record_fix(tag, line_warns, res)
        if st["struct"] or struct_warns:
            revise(tag, st["struct"], struct_warns, what="結構問題")
    st = lint_round(tag)
    if st["sent"] or st["struct"] or st["warns"]:
        raise Block(f"lint {MAX_LINT} 輪未清:擋 {len(st['sent'])}、結構 {st['struct']}、警告未處理 {len(st['warns'])}")


def _recheck(tag):
    """revise 後再過一次可唸性與 lint(沒命中就不花 LLM)。"""
    step_speak(tag)
    step_lint(tag)


def _review_state(tag, kind):
    """(下一輪輪次, 小範圍句號):比對報告的 narration 與目前旁白。沒變 = (None, []);>SPOT_MAX 句 = 下一輪;
    ≤SPOT_MAX 句 = (None, 句號),編輯審不重跑、玩家審走 _spot_review。舊報告沒有 narration 退回 mtime。"""
    n, data, path = GB.latest_review(tag, kind)
    if path is None:
        return 1, []
    saved = (data or {}).get("narration")
    cur = GB.narration_hashes(tag) if saved else None
    if not cur:
        return (n + 1 if D._newer(_script(tag), path) else None), []
    count, lines = changed_lines(saved, cur)
    if not count:
        return None, []
    if count > SPOT_MAX or (kind == "player" and data.get("revised") and n < MAX_PLAYER):  # r1 revise 完中斷:照走 r2
        return n + 1, []
    return None, lines


def _review_round(tag, kind):
    """本輪輪次;None = 報告仍有效(或小改,編輯審不重跑)。"""
    return _review_state(tag, kind)[0]


def _seal(tag, path, data):
    """報告的 narration 更新成目前旁白並寫回:這份稿已審過。"""
    data["narration"] = GB.narration_hashes(tag)
    _write_json(path, data)


def _marked(tag, lines):
    """旁白小段:lines 標 >>,附前後各一句。"""
    texts = [r[1] for r in GB.narration(tag)]
    show = sorted({k for i in lines for k in (i - 1, i, i + 1) if 1 <= k <= len(texts)})
    return "\n".join(f"{'>>' if k in lines else '  '} {k}. {texts[k - 1]}" for k in show)


def _batched(tag, fn, lines, prompt_of, what, **kw):
    """lines 每 SPOT_BATCH 句一批:prompt_of(標記內文) → LLM(REVIEW_SCHEMA);回 (合併 counts, items)。"""
    counts, items = {}, []
    for b in range(0, len(lines), SPOT_BATCH):
        r = _need(_llm(tag, fn, prompt_of(_marked(tag, lines[b:b + SPOT_BATCH])), schema=REVIEW_SCHEMA, seg="B", **kw), what)
        for c, v in (r.data.get("counts") or {}).items():
            counts[c] = counts.get(c, 0) + (v if isinstance(v, int) else 0)
        items += r.data.get("items") or []
    return counts, items


def _spot_items(tag, lines):
    """玩家審小範圍:只審 lines(任意句數,>SPOT_BATCH 分批);結果寫 player_spot_<k>.json。回 (items, 檔)。"""
    pd = f"projects\\{tag}"

    def prompt_of(body):
        return (f"小範圍審 {tag}\\script.txt:只審下面標 >> 的句子(稿件剛改過),沒標的是前後文,不審。"
                f"查證 {pd}\\facts.md、{pd}\\plan.json 的 consensus。\n{body}\n"
                "type 只用 錯/誇大/推論/相反/外行/矛盾/關掉/吵/可疑。人設 channel\\audience\\ 下本頻道 _personas.md。不寫檔,line 用上面的句號。\n"
                "最後回報用此 JSON:counts 各類條數,items=[{line,type,severity,text,reason,fix}]。")

    k = len(D._glob(_pd(tag), "player_spot_*.json")) + 1
    counts, items = _batched(tag, f"player_spot{k}", lines, prompt_of, "玩家審小範圍", agent="player-review", model="opus", tools=READ + WEB)
    out = _pd(tag) / f"player_spot_{k}.json"
    _write_json(out, {"counts": counts, "items": items, "lines": lines})
    return items, out


def _spot_review(tag, lines):
    """旁白小改(v2):玩家審只審這幾句(附前後各一句),不佔 MAX_PLAYER;命中必處理不自動改,進 ask_user.json 交主對話。"""
    items, out = _spot_items(tag, lines)
    _, data, path = GB.latest_review(tag, "player")
    _seal(tag, path, data)
    must = [i for i in items if i.get("type") in PLAYER_MUST]
    if must:
        _write_json(_pd(tag) / "ask_user.json", [*GB.ask_user(tag), *({"from": out.name, **i} for i in must)])
        raise Block(f"要問使用者:玩家審小範圍 {len(must)} 條")


def _review(tag, kind, n, extra=""):
    md = _pd(tag) / f"{kind}_review_r{n}.md"
    pd = f"projects\\{tag}"
    snap = GB.narration_hashes(tag)
    prompt = (f"審 {tag}\\script.txt,查證 {pd}\\facts.md、{pd}\\context.md、{pd}\\plan.json 的 consensus;{extra}\n"
              f"報告寫到 {pd}\\{kind}_review_r{n}.md。line 用第幾句旁白(1 起算,段標題與 @ 行不算)。\n"
              "最後回報用此 JSON:counts 各類條數,items=[{line,type,severity,text,reason,fix}]。")
    r = _need(_llm(tag, f"{kind}_r{n}", prompt, agent=f"{kind}-review", model="opus",
                   tools=WRITE + (WEB if kind == "player" else ()), schema=REVIEW_SCHEMA, seg="B",
                   validate=lambda res: None if md.exists() else f"{md.name} 沒寫"), f"{kind} 審")
    out = _pd(tag) / f"{kind}_review_r{n}.json"
    data = {**r.data, "narration": snap}
    _write_json(out, data)
    return data, out


def step_editor(tag, ctx=None, a=None):
    """一輪:連貫斷點 >0 → revise,報告記 revised(gate 不再算);不重審。"""
    n = _review_round(tag, "editor")
    data, path = _review(tag, "editor", n, "連貫審列出的條目 type 一律填「連貫」,counts 要有「連貫斷點」。")
    items = GB.open_items(data, EDITOR_LOOP)
    if items:
        data["revised"] = revise(tag, items, what="編輯審連貫斷點")
        _seal(tag, path, data)  # 本輪已結案,重跑不再審;_recheck 中斷也算
        _recheck(tag)
        _seal(tag, path, data)


def step_player(tag, ctx=None, a=None):
    """≤2 輪:r1 必處理條目 → revise → r2;r2 仍有 → ask_user.json,卡點 要問使用者(不開第三輪)。
    旁白只小改 → 小範圍審,不佔輪數(含滿 2 輪後)。"""
    n, spot = _review_state(tag, "player")
    if spot:
        return _spot_review(tag, spot)
    while n and n <= MAX_PLAYER:
        data, path = _review(tag, "player", n, PLAYER_EXTRA)
        if n == MAX_PLAYER:
            left = [i for i in data.get("items") or [] if i.get("type") in PLAYER_ASK]
            if left:
                _write_json(_pd(tag) / "ask_user.json", [{"from": path.name, **i} for i in left])
                raise Block(f"要問使用者:玩家審 r{n} 仍有 {len(left)} 條")
            return
        must = [i for i in data.get("items") or [] if i.get("type") in PLAYER_MUST]
        if not must:
            return
        data["revised"] = revise(tag, must, what="玩家審必處理條目")
        _write_json(path, data)
        _recheck(tag)
        n += 1
    if n and n > MAX_PLAYER:
        raise Block("玩家審已滿 2 輪且文案後來又改過,要主對話決定")


# ---------- B 段 flow v3:審稿合併(B3、B4) ----------

def _review_md(data, title):
    """編輯審 v3 不寫 md:由 JSON 產簡表。"""
    cell = lambda s: str(s or "").replace("|", "/").replace("\n", " ")  # noqa: E731
    out = [f"# {title}", "", "| 句 | 類型 | 原句 | 理由 | 改法 |", "|---|---|---|---|---|"]
    out += [f"| {i.get('line')} | {cell(i.get('type'))} | {cell(i.get('text'))[:40]} | {cell(i.get('reason'))} | {cell(i.get('fix'))} |"
            for i in data.get("items") or []]
    out += ["", "counts:" + "、".join(f"{k} {v}" for k, v in (data.get("counts") or {}).items())]
    return "\n".join(out) + "\n"


def _editor_v3(tag):
    """B3:編輯審只審四類、只回 JSON;director 寫 editor_review_r1.json 與 .md。其他 type 丟掉(lint 已管)。"""
    pd = f"projects\\{tag}"
    snap = GB.narration_hashes(tag)
    prompt = (f"審 {tag}\\script.txt,只審四類:{'/'.join(EDITOR_V3)}(定義見你的代理說明;lint 已管的碼不要列)。"
              f"對照 {pd}\\facts.md、{pd}\\plan.json 的 consensus;build\\{tag}\\structure.json 有就讀。\n"
              "不寫檔。line 用第幾句旁白(1 起算,段標題與 @ 行不算);結構項對不到句就填該段第一句。type 只用上面四個字串。\n"
              "最後回報用此 JSON:counts 各類條數,items=[{line,type,severity,text,reason,fix}]。")
    r = _need(_llm(tag, "editor_r1", prompt, agent="editor-review", model="opus", tools=READ, schema=REVIEW_SCHEMA, seg="B"), "editor 審")
    items = [i for i in r.data.get("items") or [] if i.get("type") in EDITOR_V3]
    data = {**r.data, "items": items, "dropped": len(r.data.get("items") or []) - len(items), "narration": snap}
    out = _pd(tag) / "editor_review_r1.json"
    _write_json(out, data)
    (_pd(tag) / "editor_review_r1.md").write_text(_review_md(data, f"{tag} 編輯審 r1(flow v3,由 JSON 產)"), encoding="utf-8")
    return data, out


def _fact_check(tag, lines=None):
    """r2 事實專審(Sonnet,fact-check):只查錯;lines 給了只審那幾句(附前後文,分批)。回 (items, 檔)。"""
    pd = f"projects\\{tag}"
    rule = ("只查「錯」:數字、日期、引言、誰說的、機制、譯名與 facts.md 或第一手來源不符;不評角度、不評文筆、不評語氣。\n"
            "type 只用 錯/查無(查無 = facts.md 沒有、你也查不到來源的說法)。不寫檔;line 用第幾句旁白(1 起算,段標題與 @ 行不算)。\n"
            "最後回報用此 JSON:counts 各類條數,items=[{line,type,severity,text,reason,fix}]。")
    kw = dict(agent="fact-check", model="sonnet", tools=READ + WEB)
    if lines:
        k = len(D._glob(_pd(tag), "fact_spot_*.json")) + 1
        out = _pd(tag) / f"fact_spot_{k}.json"
        counts, items = _batched(tag, f"fact_spot{k}", lines, lambda body: (
            f"事實專審 {tag}\\script.txt,對照 {pd}\\facts.md。只審下面標 >> 的句子(剛改過),沒標的是前後文。\n{body}\n" + rule), "事實專審", **kw)
    else:
        out = _pd(tag) / "fact_review_r2.json"
        r = _need(_llm(tag, "fact_r2", f"事實專審 {tag}\\script.txt 全稿逐句,對照 {pd}\\facts.md。\n" + rule,
                       schema=REVIEW_SCHEMA, seg="B", **kw), "事實專審")
        counts, items = r.data.get("counts") or {}, r.data.get("items") or []
    items = [i for i in items if i.get("type") in FACT_TYPES]
    _write_json(out, {"counts": counts, "items": items, "narration": GB.narration_hashes(tag), **({"lines": lines} if lines else {})})
    return items, out


def review_state(tag):
    return D._read_json(_pd(tag) / "review_state.json") or {}


def _tagged(items, src):
    return [{"from": src, **i} for i in items]


def _dedupe(items):
    seen, out = set(), []
    for i in items:
        k = (i.get("line"), i.get("type"))
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


def _mark_r1(data, path, revised, types, unresolved):
    """r1 報告:改到的句記 revised,其餘條目記 kept + 原因(gate v3 要每條有處理紀錄)。"""
    lines = {i.get("line") for i in data.get("items") or [] if i.get("type") in types}
    why = {u["line"]: u["why"] for u in unresolved}
    data["revised"] = sorted(n for n in revised if n in lines)
    data["kept"] = [{"line": i.get("line"), "type": i.get("type"), "reason": why.get(i.get("line"), "改稿員未改")}
                    for i in data.get("items") or [] if i.get("type") in types and i.get("line") not in data["revised"]]
    _write_json(path, data)


def review_skip(tag):
    """review 步略過原因或 None:已完成且旁白沒變;ask 已被主對話清空(要結案)不略過。"""
    st = review_state(tag)
    if not st.get("done") or st.get("narration") != GB.narration_hashes(tag):
        return None
    if st.get("ask") and not GB.ask_user(tag):
        return None
    return "審稿仍有效(旁白沒變)"


def _finish(tag, st, ask, soft):
    """結算:ask(錯/關掉 + 裁決類)整批寫 ask_user.json 並卡點;其餘型別只記 soft。"""
    ask = _dedupe(ask)
    st.update(stage=None, done=True, narration=GB.narration_hashes(tag), ask=ask, soft=_dedupe(soft),
              open_hard=[i for i in ask if i.get("type") in HARD_TYPES], at=D.now_iso())
    _write_json(_pd(tag) / "review_state.json", st)
    if ask:
        _write_json(_pd(tag) / "ask_user.json", ask)
        raise Block(f"要問使用者:{len(ask)} 條")


def _review_delta(tag, st):
    """已審完的稿又被改(主對話手改):只對改過的句做玩家小範圍審 + 事實專審,平行;命中直接問,不再自動改。"""
    _, lines = changed_lines(st.get("narration") or [], GB.narration_hashes(tag))
    if not lines:
        return _finish(tag, st, [], st.get("soft") or [])
    with ThreadPoolExecutor(2) as ex:
        fs, ff = ex.submit(_spot_items, tag, lines), ex.submit(_fact_check, tag, lines)
        (sp, sp_out), (fc, fc_out) = fs.result(), ff.result()
    st.setdefault("rounds", []).extend([
        {"kind": "player_spot", "file": sp_out.name, "lines": len(lines), "items": len(sp), "at": D.now_iso()},
        {"kind": "fact_spot", "file": fc_out.name, "lines": len(lines), "items": len(fc), "at": D.now_iso()}])
    sp, fc = _tagged(sp, sp_out.name), _tagged(fc, fc_out.name)
    ask = [i for i in sp if i.get("type") in PLAYER_ASK] + [i for i in fc if i.get("type") == "錯"]
    _finish(tag, st, ask, [*(st.get("soft") or []), *(i for i in sp + fc if i not in ask)])


def _review_full(tag, st):
    """r1 平行審 → 合併一次 revise(機械驗)→ spot 改過句(≤2 次)→ r2 事實專審 → 錯 revise+驗 → 結算。
    每階段寫 review_state.stage,中斷後從該階段接(r1 報告的 narration 等於當時旁白就沿用,不重審)。"""
    path = _pd(tag) / "review_state.json"
    rounds, unresolved, soft = st.setdefault("rounds", []), st.setdefault("unresolved", []), st.setdefault("soft", [])

    def save(**kw):
        st.update(kw, done=False)
        _write_json(path, st)

    cur = GB.narration_hashes(tag)
    if not st.get("stage"):  # 1. editor r1 與 player r1 平行審同一版稿
        got = {}
        for k in ("editor", "player"):
            p = _pd(tag) / f"{k}_review_r1.json"
            d = D._read_json(p)
            if d and d.get("narration") == cur and "revised" not in d:
                got[k] = (d, p)
        jobs = {"editor": lambda: _editor_v3(tag), "player": lambda: _review(tag, "player", 1, PLAYER_EXTRA)}
        with ThreadPoolExecutor(2) as ex:
            futs = {k: ex.submit(f) for k, f in jobs.items() if k not in got}
            got.update({k: f.result() for k, f in futs.items()})
        rounds += [{"kind": k, "file": got[k][1].name, "items": len(got[k][0].get("items") or []), "at": D.now_iso()} for k in futs]
        save(stage="r1", pre=cur)
    ed_p, pl_p = _pd(tag) / "editor_review_r1.json", _pd(tag) / "player_review_r1.json"
    ed, pl = D._read_json(ed_p) or {}, D._read_json(pl_p) or {}
    if st["stage"] == "r1":  # 2. 條目合併,一次 revise
        if "revised" not in pl:
            issues = (ed.get("items") or []) + [i for i in pl.get("items") or [] if i.get("type") in PLAYER_MUST]
            done = revise(tag, issues, what="編輯審四類與玩家審必處理條目", check=True, unresolved=unresolved) if issues else []
            _mark_r1(ed, ed_p, done, EDITOR_V3, unresolved)
            _mark_r1(pl, pl_p, done, PLAYER_MUST, unresolved)
        _recheck(tag)
        save(stage="revised")
    if st["stage"] == "revised":  # 3. 玩家審只驗改過的句;必處理再改再驗,整個迴圈 ≤ MAX_SPOT_LOOP
        _, lines = changed_lines(st["pre"], GB.narration_hashes(tag))
        left = []
        for k in range(MAX_SPOT_LOOP):
            if not lines:
                break
            items, out = _spot_items(tag, lines)
            rounds.append({"kind": "player_spot", "file": out.name, "lines": len(lines), "items": len(items), "at": D.now_iso()})
            must = _tagged([i for i in items if i.get("type") in PLAYER_MUST], out.name)
            soft += _tagged([i for i in items if i.get("type") not in PLAYER_MUST], out.name)
            left = [i for i in left if i.get("line") not in lines] + must
            if not must or k == MAX_SPOT_LOOP - 1:
                break
            before = GB.narration_hashes(tag)
            revise(tag, must, what="玩家小範圍審必處理條目", check=True, unresolved=unresolved)
            _recheck(tag)
            _, lines = changed_lines(before, GB.narration_hashes(tag))
        save(stage="spot", spot_left=left)
    if st["stage"] == "spot":  # 4. r2 = 事實專審全稿;「錯」→ revise → 只驗那些句一次
        fc, out = _fact_check(tag)
        rounds.append({"kind": "fact", "file": out.name, "items": len(fc), "at": D.now_iso()})
        wrong = _tagged([i for i in fc if i.get("type") == "錯"], out.name)
        soft += _tagged([i for i in fc if i.get("type") != "錯"], out.name)
        left = []
        if wrong:
            before = GB.narration_hashes(tag)
            revise(tag, wrong, what="事實專審判錯的句", check=True, unresolved=unresolved)
            _recheck(tag)
            _, lines = changed_lines(before, GB.narration_hashes(tag))
            left = [i for i in wrong if i.get("line") not in lines]
            if lines:
                again, out2 = _fact_check(tag, lines)
                rounds.append({"kind": "fact_spot", "file": out2.name, "lines": len(lines), "items": len(again), "at": D.now_iso()})
                left += _tagged([i for i in again if i.get("type") == "錯"], out2.name)
                soft += _tagged([i for i in again if i.get("type") != "錯"], out2.name)
        save(stage="fact", fact_left=left)
    # 5. 結算:r1 沒改到的必處理 + spot / 事實專審後仍在的
    done = set(pl.get("revised") or [])
    r1_left = _tagged([i for i in pl.get("items") or [] if i.get("type") in PLAYER_MUST and i.get("line") not in done], pl_p.name)
    rest = _dedupe(r1_left + (st.get("spot_left") or []) + (st.get("fact_left") or []))
    ask = [i for i in rest if i.get("type") in HARD_TYPES + JUDGE_TYPES]
    _finish(tag, st, ask, soft + [i for i in rest if i not in ask])


def step_review(tag, ctx=None, a=None):
    """flow v3 審稿(取代 editor + player):見 _review_full;已審完且旁白被改 → _review_delta;ask_user 未清 → 卡點不花 LLM。"""
    ask = GB.ask_user(tag)
    if ask:
        raise Block(f"要問使用者:ask_user.json 還有 {len(ask)} 條(處理完清空再跑)")
    st = review_state(tag)
    if not st.get("done"):
        return _review_full(tag, st)
    if st.get("ask"):  # 主對話已處理並清空 ask_user.json:這批結案
        st.update(resolved=[*(st.get("resolved") or []), *st["ask"]], ask=[], open_hard=[])
        _write_json(_pd(tag) / "review_state.json", st)
    if st.get("narration") != GB.narration_hashes(tag):
        _review_delta(tag, st)


# ---------- B4 ----------

def _only_added(old, new):
    """new 是否只比 old 多東西(舊條目全在、值不變)。"""
    if isinstance(old, dict):
        return isinstance(new, dict) and all(k in new and _only_added(v, new[k]) for k, v in old.items())
    if isinstance(old, list):
        return isinstance(new, list) and all(x in new for x in old)
    return old == new


def _pron_path(name):
    return P.REPO / "pipeline" / name


def _validate_apply(tag, snap, pending):
    """讀音檔還能解析、只新增;backlog 前 3 條都有紀錄。不符就還原並回失敗原因。"""
    def check(r):
        for name, text in snap.items():
            f = _pron_path(name)
            if name.endswith(".json"):
                try:
                    ok = _only_added(json.loads(text), json.loads(f.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    ok = False
            else:
                ok = f.read_text(encoding="utf-8").startswith(text)
            if not ok:
                f.write_text(text, encoding="utf-8")
                return f"{name} 只能新增條目,已還原"
        done = {(b.get("word"), b.get("context")) for b in (r.data or {}).get("backlog") or []}
        miss = [f"{p['字']}|{p['語境詞']}" for p in pending if (p["字"], p["語境詞"]) not in done]
        return f"backlog 這幾條要回報處理:{'、'.join(miss)}" if miss else None
    return check


def _pron_review(tag, n):
    pd = f"projects\\{tag}"
    md = _pd(tag) / "pron_review.md"
    prompt = (f"審配音稿 build\\{tag}\\tts_script.md,報告寫 {pd}\\pron_review.md(第 {n} 輪,覆寫)。"
              f"另看 build\\{tag}\\sub_scan.json 的接縫數。\n"
              "最後回報用此 JSON:counts 各類條數,items=[{line,type,word,current,fix,basis,status}];status 只用 未決(要改規則或詞表)/已決/可疑。")
    r = _need(_llm(tag, f"pron_review_r{n}", prompt, agent="pron-review", model="sonnet", tools=WRITE + ("Bash",),
                   schema=PRON_SCHEMA, seg="B4", validate=lambda res: None if md.exists() else "pron_review.md 沒寫"), "pron-review")
    _write_json(_pd(tag) / "pron_review.json", r.data)
    return r.data


def _pron_apply(tag, items, pending):
    snap = {n: _pron_path(n).read_text(encoding="utf-8") for n in PRON_FILES if _pron_path(n).exists()}
    prompt = (f"把下列讀音審結果寫進 pipeline\\pron_rules.json / pipeline\\cosy_pron.json(接縫詞寫 pipeline\\sub_words.txt 檔尾),只新增條目,不改既有:\n"
              f"{json.dumps(items, ensure_ascii=False)}\n"
              f"本片 pron_backlog 前 3 條也要處理(能定就加規則,不能定寫理由):\n{json.dumps(pending, ensure_ascii=False)}\n"
              "回 JSON:added=[{file,entry}],backlog=[{word,context,action,reason}],word/context 照抄上面的 字/語境詞。")
    r = _need(_llm(tag, "pron_apply", prompt, agent="pron-apply", model="sonnet", tools=EDIT, schema=APPLY_SCHEMA, seg="B4",
                   validate=_validate_apply(tag, snap, pending)), "pron-apply")
    f = _pd(tag) / "pron_apply.json"
    cur = D._read_json(f) or {"added": [], "backlog": []}
    cur["added"] += r.data.get("added") or []
    cur["backlog"] += r.data.get("backlog") or []
    _write_json(f, cur)


def _tts_script_cmd(tag):
    return D._sys() + [D._script("tts_script.py"), tag]


def _sub_scan_cmd(tag):
    return D._py() + [D._script("sub_scan.py"), "--tag", tag, "--seg", "ckip", "--json", D._rel(P.build_dir(tag) / "sub_scan.json")]


def step_b4_prep(tag, a):
    """txt2json → tts_script → sub_scan(接縫 >0 結束碼 1,交給 pron 迴圈)。"""
    rc, text = _txt2json(tag)
    if rc != 0:
        raise Block(f"script_txt2json 失敗:{D._tail(text)}")
    rc, text, marker = D._exec(tag, a.ver or "ab", "B4", "tts_script", _tts_script_cmd(tag))
    if rc != 0:
        raise Block(f"tts_script 結束碼 {rc}:{D._tail(text)}")
    D._exec(tag, a.ver or "ab", "B4", "sub_scan", _sub_scan_cmd(tag))
    if GB4.seam_count(tag) is None:
        raise Block("sub_scan 沒產出 sub_scan.json")


def step_pron(tag, ctx, a):
    """tts_script/sub_scan → pron-review → pron-apply → 重跑到未決 0、接縫 0、backlog 前 3 有處理;≤3 輪。flow v3 走 step_pron_v3。"""
    if flow(tag) == "v3":
        return step_pron_v3(tag, ctx, a)
    for n in range(1, MAX_PRON + 1):
        step_b4_prep(tag, a)
        data = _pron_review(tag, n)
        left = [i for i in data.get("items") or [] if i.get("status") == "未決"]
        pending = GB4.backlog_pending(tag)
        if not left and not pending and GB4.seam_count(tag) == 0:
            return
        if n == MAX_PRON:
            break
        _pron_apply(tag, left, pending)
    raise Block(f"讀音 {MAX_PRON} 輪未清:未決 {len(left)}、接縫 {GB4.seam_count(tag)}、backlog {len(pending)}")


# ---------- B4 flow v3(PLAN_token重設計_2026-11-03 §2(b) B2;docs\director_ab.md「B4 v3」)----------

MAX_PRON_V3 = 2   # LLM 最多兩輪;之後只重算候選
_DEC = {"type": "object", "required": ["kind"], "properties": {
    "kind": _STR, "char": _STR, "words": {"type": "array", "items": _STR}, "re": _STR, "py": _STR,
    "pos": {"type": "array", "items": _INT}, "model_default": _STR, "unverified": {"type": "boolean"}, "note": _STR,
    "word": _STR, "context": _STR, "action": _STR, "reason": _STR}}
PRON3_SCHEMA = {"type": "object", "required": ["items"], "properties": {
    "items": _ARR({"line": _INT, "kind": _STR, "char": _STR, "word": _STR, "current": _STR, "status": _STR, "decision": _DEC, "basis": _STR})}}
PRON3_FORMAT = (
    "decision 格式(沒有要寫入就給 {};程式只新增、驗 py token 與 re,錯的會退回):\n"
    "- rule:{kind:\"rule\",char:\"血\",words:[\"詞\"]或re:\"正規式\",py:\"[x][iě]\",pos:[詞內位置,可省],unverified:true,note:\"一句依據\"};"
    "新字另給 model_default。words 的每個詞都要含該字;re 用 lookaround 縮小範圍。\n"
    "- word:{kind:\"word\",word:\"詞\",py:\"帶拼音標注的整詞寫法\"}(cosy_pron.json)\n"
    "- term:{kind:\"term\",word:\"英文詞\",py:\"送引擎寫法\"} 或 {kind:\"term\",word:\"英文詞\",action:\"direct\"}(維持直送)\n"
    "- sub_word:{kind:\"sub_word\",word:\"詞\"}(接縫的詞要併成一段,寫 sub_words.txt)\n"
    "- backlog:{kind:\"backlog\",word:\"字\",context:\"語境詞\",action:\"採取的動作\",reason:\"理由\"}(word/context 照抄候選的 char/context)\n"
    "items 每筆:line(句號,沒有填 0)、kind(poly|seam|english|backlog,照抄候選所屬類)、char、word(照抄候選)、current(現況)、"
    "status(已決=有依據且已給 decision 或確認現況正確;可疑=拿不準也不影響讀音(「一」變調、停頓靠聽);未決=還需要改)、basis(依據,查 lookup 結果)。"
    "每個候選都要回一筆。查讀音只看候選附的 lookup 與規則條目,不要 Read 整份 pron_rules.json,不要跑 Bash。")


def _pron3_prompt(tag, c, n):
    rules = {}
    for p in list(c["poly"]) + list(c["backlog"]):
        if p.get("rules") is not None:
            rules.setdefault(p["char"], p["rules"])
    slim = {k: [{x: y for x, y in it.items() if x != "rules"} for it in c[k]] for k in ("seams", "poly", "english", "backlog")}
    doc = (D._read_json(_pron_path("pron_rules.json")) or {}).get("_doc") or ""
    return (f"flow v3 讀音審(第 {n} 輪)。只決下列候選(程式已從 build\\{tag}\\tts_script.json 與 sub_scan.json 算出),不審整份配音稿。\n"
            f"候選:\n{json.dumps(slim, ensure_ascii=False)}\n"
            f"候選裡出現的字在 pron_rules.json 的現有條目(只給這幾個字):\n{json.dumps(rules, ensure_ascii=False)}\n"
            f"pron_rules.json 的 _doc:{doc}\n{PRON3_FORMAT}")


def _pron3_check(res):
    bad = []
    for i in (res.data or {}).get("items") or []:
        if i.get("status") not in ("已決", "可疑", "未決"):
            bad.append(f"句{i.get('line')} status 只能是 已決/可疑/未決")
        d = i.get("decision") or {}
        if d and d.get("kind") not in ("rule", "word", "term", "sub_word", "backlog"):
            bad.append(f"句{i.get('line')} decision.kind 不認得:{d.get('kind')}")
    return "；".join(bad[:5]) or None


def _pron3_review(tag, n, c):
    r = _need(_llm(tag, f"pron_review_r{n}", _pron3_prompt(tag, c, n), agent="pron-review", model="sonnet", tools=("Read",),
                   schema=PRON3_SCHEMA, seg="B4", validate=_pron3_check), "pron-review")
    return (r.data or {}).get("items") or []


def _pron3_apply(tag, items):
    """逐條套 decision(各自驗、各自記錯);成功或「已存在」→ 該條記進 decided 帳本,寫入失敗 → 退回未決。回傳 (items, 寫入條數, 錯誤)。"""
    import pron_apply as PA
    n_add, errs = 0, []
    for it in items:
        d = it.get("decision") or {}
        if not d:
            continue
        res = PA.apply([d], tag)
        n_add += len(res["added"]) + len(res.get("backlog") or [])
        hard = [e for e in res["errors"] if not re.search(r"已存在|已有", e)]
        if hard:
            it["status"] = "未決"
            it["basis"] = f"{it.get('basis') or ''} | 寫入失敗:{'；'.join(hard)}".strip(" |")
            errs += hard
    PA.record_seen(tag, items)
    return items, n_add, errs


def _pron3_left(c):
    """候選仍在 = 未決(接縫另由 gate 的 sub_scan 判)。"""
    out = []
    out += [dict(line=s["line"], kind="seam", char="", word=s["word"], current=f"{s['a']}⏐{s['b']}({s['why']})", status="未決", basis="pron_pre:接縫仍在") for s in c["seams"]]
    out += [dict(line=p["line"], kind="poly", char=p["char"], word=p["word"], current=p.get("current") or "", status="未決", basis=f"pron_pre:{p.get('src')}") for p in c["poly"]]
    out += [dict(line=(e["lines"] or [0])[0], kind="english", char="", word=e["word"], current=e["src"], status="未決", basis="pron_pre:英文") for e in c["english"]]
    return out


def _write_pron3(tag, items, left, source, cand_n):
    """pron_review.json(gate 用):items = 本次 LLM 看過的條目(同鍵後者蓋前者)+ 仍未決的候選。"""
    last = {}
    for it in items:
        last[(it.get("kind"), it.get("char"), it.get("word"))] = it
    lk = {(x["kind"], x["char"], x["word"]) for x in left}
    allit = [i for i in last.values() if (i.get("kind"), i.get("char"), i.get("word")) not in lk] + left
    counts = {"候選": cand_n, "未決": sum(i.get("status") == "未決" for i in allit), "已決": sum(i.get("status") == "已決" for i in allit),
              "可疑": sum(i.get("status") == "可疑" for i in allit)}
    _write_json(_pd(tag) / "pron_review.json", {"counts": counts, "items": allit, "source": source})
    return counts


def step_pron_v3(tag, ctx, a):
    """prep → pron_pre 候選 → 0 條:不叫 LLM,直接寫 pron_review.json;否則 Sonnet 一次決定 → pron_apply 程式寫入 → 重算,≤2 輪 LLM。"""
    import pron_pre as PRE

    def rescan():
        D._exec(tag, a.ver or "ab", "B4", "sub_scan", _sub_scan_cmd(tag))
    seen_items, first_n, c, calls = [], None, None, 0
    for n in range(1, MAX_PRON_V3 + 2):
        step_b4_prep(tag, a)
        c = PRE.candidates(tag, rescan=rescan)
        first_n = c["n"] if first_n is None else first_n
        if not c["n"] or n > MAX_PRON_V3:
            break
        calls += 1
        items = _pron3_review(tag, n, c)
        done, n_add, errs = _pron3_apply(tag, items)
        seen_items += done
        print(f"pron v3 第 {n} 輪:候選 {c['n']}、決定 {len(done)}、寫入 {n_add}" + (f"、寫入失敗 {len(errs)}" if errs else ""))
        # 只有 backlog 被「已決」不會改 tts_script/sub_scan,重算仍會乾淨;其餘改了讀音檔,下一輪 prep 會重算
    left = _pron3_left(c)
    counts = _write_pron3(tag, seen_items, left, "pron_pre" if not calls else "pron_pre+llm", first_n or 0)
    pending, seams = GB4.backlog_pending(tag), GB4.seam_count(tag)
    if left or pending or seams:
        raise Block(f"讀音 v3 未清:未決 {len(left)}、接縫 {seams}、backlog {len(pending)}({calls} 輪 LLM)")
    return counts


# ---------- B9 步驟雜湊(flow v3;production.json 的 step_hash: {"<seg>/<step>": sha8})----------

STEP_HASH = "step_hash"


def _sha(*parts):
    import hashlib
    h = hashlib.sha1()
    for p in parts:
        h.update(p if isinstance(p, bytes) else str(p).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:8]


def _bytes(path):
    try:
        return Path(path).read_bytes()
    except OSError:
        return b""


def hash_b4(tag):
    """送配音文字 + 讀音檔(pron_rules、cosy_pron、cosy_terms、sub_words)+ 本片接縫詞;script 讀不到回 None(不 skip)。"""
    try:
        import tts_script as TS
        says = "\n".join(s for _, s in TS.script_lines(tag))
    except (Exception, SystemExit):  # noqa: BLE001  script_txt2json 解析失敗是 sys.exit
        return None
    return _sha(says, *[_bytes(_pron_path(n)) for n in PRON_FILES + ("cosy_terms.json",)], _bytes(_pd(tag) / "seam_words.txt"))


def hash_assets(tag):
    """plan.json 的每條 claim 的 id + visual(素材員的輸入);沒有 plan 回 None。"""
    claims = _plan(tag).get("claims")
    return _sha(json.dumps([(c.get("id"), c.get("visual")) for c in claims], ensure_ascii=False)) if claims else None


def hash_review(tag):
    """每句旁白雜湊 + facts.md(審稿的輸入)。"""
    hs = GB.narration_hashes(tag)
    return _sha(json.dumps(hs), _bytes(_pd(tag) / "facts.md")) if hs else None


def step_hash(tag, key):
    return ((D.load_prod(tag) or {}).get(STEP_HASH) or {}).get(key)


def set_step_hash(tag, key, sha):
    """只動 step_hash 欄位(讀進整份再寫回,其他欄位原樣)。"""
    with D._LOCK:
        data, _ = D.init(tag)
        data.setdefault(STEP_HASH, {})[key] = sha
        D._atomic_write(D.prod_path(tag), data)


def memo_skip(tag, key, hash_fn, ok=None):
    """v3:輸入雜湊與上次成功時相同(且 ok() 為真)→ 回略過原因;否則 None。"""
    if flow(tag) != "v3":
        return None
    h = hash_fn(tag)
    if h and step_hash(tag, key) == h and (ok is None or ok()):
        return f"步驟雜湊相同({key} {h}),上次成功"
    return None


def memoized(tag, key, hash_fn, fn):
    """包住步驟 fn:成功(沒丟 Block)後記下輸入雜湊(v3 才記);fn 的回傳照給。"""
    def run():
        r = fn()
        if flow(tag) == "v3":
            h = hash_fn(tag)
            if h:
                set_step_hash(tag, key, h)
        return r
    return run


# ---------- C 段改句迴圈(§7) ----------

def qc_issues(tag, ver, seen):
    """回 (品管/時長 items, E4 items, 對不到句的時長錯誤);line = script.txt 行號(line_fix 用),報告裡的 idx 是句號要換算。
    seen = 已改過的 E4 行(留給必聽,不再改)。"""
    try:
        rows = script_rows(tag)
    except Block:
        rows = {}
    rv = D._read_json(P.build_dir(tag) / "tts_review.json") or {}
    hard = {}
    for f in rv.get("failed") or []:
        idx, fails = (f.get("idx"), f.get("fails")) if isinstance(f, dict) else (f, None)
        hard.setdefault(rows.get(idx, idx), []).extend(str(x) for x in (fails or ["品管未過"]))
    orphan = []
    for e in rv.get("timing_errors") or []:
        m = re.search(r"句\s*(\d+)", str(e))
        if m:
            hard.setdefault(rows.get(int(m.group(1)), int(m.group(1))), []).append(str(e))
        else:
            orphan.append(str(e))
    ear = {}
    for k, r in ((D._read_json(_pd(tag) / f"ear_e4_{ver}.json") or {}).get("results") or {}).items():
        fl = [f for f in r.get("flags") or [] if f.get("kind") in QC_KINDS]
        no = rows.get(int(k), int(k))
        if fl and no not in seen and no not in hard:
            ear[no] = [f"E4 {f['kind']}:{f.get('char')}(期望 {f.get('expected')},聽到 {f.get('heard') or '無'})" for f in fl]
    to_items = lambda d: [{"line": k, "reasons": v} for k, v in d.items()]  # noqa: E731
    return to_items(hard), to_items(ear), orphan


def step_qc(tag, ctx, a):
    """make_version --tts-review(不凍結)→ 品管/時長/E4 有句 → line_fix(qc)→ 重跑;第 3 輪品管仍未過 = 卡點。
    不放寬別名、不動品管門檻;只改句。"""
    cmd = D._sys() + [D._script("make_version.py"), "--tag", tag, "--ver", a.ver, "--tts-review"]
    seen = set()
    for n in range(1, MAX_QC + 1):
        rc, text, _ = D._exec(tag, a.ver, "C", f"改句r{n}", cmd)
        if rc != 0:
            raise Block(f"make_version --tts-review 結束碼 {rc}:{D._tail(text)}")
        hard, ear, orphan = qc_issues(tag, a.ver, seen)
        if not hard and not ear and not orphan:
            return
        if n == MAX_QC:
            break
        if orphan and not hard and not ear:
            break
        res = _fix(tag, hard + ear, "qc")
        seen |= {f["line"] for f in res.get("fixed") or [] if f["line"] in {i["line"] for i in ear}}
    if hard or orphan:
        raise Block(f"品管未過到第 {MAX_QC} 輪:句 {[i['line'] for i in hard]}" + (f";時長 {orphan[:3]}" if orphan else ""))


# ---------- 段末 commit ----------

def _git(*args):
    return subprocess.run(["git", *args], cwd=P.REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")


def commit_seg(tag, seg):
    """段過 gate commit:只 add 明確路徑(comments_ref 不進 git);index.lock 重試 3 次,失敗記 warn 不中止。回傳是否有 commit。"""
    paths = [p for p in (P.REPO / tag, _pd(tag)) if p.exists()]
    if seg == "B4":
        paths += [p for p in (_pron_path(n) for n in PRON_PATHS) if p.exists()]
    spec = [D._rel(p) for p in paths] + [f":(exclude){D._rel(_pd(tag))}/comments_ref"]
    err = ""
    for _ in range(3):
        r = _git("add", "--", *spec)
        if r.returncode == 0:
            if _git("diff", "--cached", "--quiet", "--", *spec).returncode == 0:
                return False
            r = _git("commit", "-m", f"director {tag}: {seg} 過 gate", "--", *spec)
            if r.returncode == 0:
                return True
        err = (r.stderr or r.stdout).strip()
        if "index.lock" not in err:
            break
        time.sleep(2)
    D._warn(tag, seg, "commit", err[-300:] or "git 失敗")
    return False


# ---------- 步驟表 ----------

def _write_skip(tag, plan_f, facts_f, mf_f):
    """B5:script.txt 已有就不重寫(plan/manifest/facts 較新只提醒;整稿重寫會蓋掉手修並連鎖重審)。
    要重寫:該次 run 設環境變數 CV_REWRITE=1(之後併成 run --rewrite)。"""
    sc = _script(tag)
    if os.environ.get("CV_REWRITE") == "1" or not sc.exists():
        return None
    newer = [f.name for f in (plan_f, mf_f, facts_f) if f.exists() and not D._newer(sc, f)]
    if newer:
        print(f"[write] {'、'.join(newer)} 比 script.txt 新:不重寫,lint/facts_check 照跑;要重寫該次 run 設 CV_REWRITE=1")
    return "script.txt 已有(要重寫設 CV_REWRITE=1)"


def steps(tag, seg, ctx, a):
    """本段步驟 [{step, cmd, skip, block, status_only, fn, desc}];skip 可為 callable(執行前才評)。"""
    out = []

    def add(step, cmd=None, fn=None, desc="", skip=None, block=None):
        out.append({"step": step, "cmd": cmd, "fn": fn, "desc": desc, "skip": skip, "block": block, "status_only": False})

    def bind(f):
        return lambda: f(tag, ctx, a)

    pd = _pd(tag)
    brief_f, plan_f, facts_f, mf_f = pd / "brief.json", pd / "plan.json", pd / "facts.md", pd / "assets_manifest.json"
    draft = lambda: pd / "plan_draft.json" if (pd / "plan_draft.json").exists() else plan_f  # replan 會改寫 plan.json,前段比對 draft
    if seg == "A":
        brief = _brief(tag)
        miss = [k for k in gate_a.BRIEF_KEYS if not brief.get(k)]
        bad_fmt = brief.get("channel") and not specs.known(brief.get("channel"), brief.get("format"))
        add("brief", desc=f"檢查 {D._rel(brief_f)}",
            block="待開工提問" if not brief_f.exists() or miss else f"片型不在 specs.FORMATS:{brief.get('channel')}/{brief.get('format')}" if bad_fmt else None,
            skip=None if not brief_f.exists() or miss or bad_fmt else "brief 齊")
        add("context", _context_cmd(tag, brief), skip=lambda: _newer_all(pd / "context.md", brief_f))
        add("comments", fn=bind(step_comments), desc="yt-dlp --write-comments 同題片 → comments_ref\\(沒網址跳過記 warn)",
            skip=lambda: "comments_ref 已有" if D._glob(pd / "comments_ref", "*.json") else None)
        add("consensus", fn=bind(step_consensus), desc="LLM sonnet agent=ab-planner → plan.json",
            skip=lambda: _newer_all(draft(), brief_f, pd / "context.md"))
        add("research", fn=bind(step_research), desc="LLM haiku agent=researcher plan.todo → facts_raw1.md",
            skip=lambda: "plan.todo 空" if plan_f.exists() and not _plan(tag).get("todo") else _newer_all(pd / "facts_raw1.md", draft()))
        add("facts", fn=bind(step_facts), desc="LLM sonnet high agent=ab-planner → facts.md",
            skip=lambda: _newer_all(facts_f, draft(), *sorted(pd.glob("facts_raw*.md"))))  # 主對話補查的 facts_raw2+ 也觸發重整
        add("replan", fn=bind(step_replan), desc="LLM sonnet high agent=ab-planner facts → plan.json(claims/blocks 重排)",
            skip=lambda: _newer_all(plan_f, facts_f) if _plan(tag).get("replanned") else None)
        add("assets", fn=memoized(tag, "A/assets", hash_assets, bind(step_assets)), desc="LLM sonnet agent=asset-collector 截圖+片段平行 → assets_manifest.json",
            skip=lambda: _newer_all(mf_f, plan_f) or memo_skip(tag, "A/assets", hash_assets, ok=mf_f.exists))
    elif seg == "B":
        v3 = flow(tag) == "v3"
        add("write", fn=bind(step_write), skip=lambda: _write_skip(tag, plan_f, facts_f, mf_f),
            desc="LLM opus high agent=script-writer(+Bash 白名單自檢到擋 0、硬項 0,保留警告 → warn_log_writer.json)→ <tag>\\script.txt、outline.md"
            if v3 else "LLM opus high agent=script-writer → <tag>\\script.txt、outline.md")
        add("speak", fn=bind(step_speak), desc="speakable 硬項 → line_fix(speak),≤3 輪")
        add("lint", fn=bind(step_lint), desc="script_txt2json、script_structure、visual_check --table、facts_check、script_lint;句級 → line_fix,結構級 → revise,≤3 輪")
        if v3:
            add("review", fn=memoized(tag, "B/review", hash_review, bind(step_review)), skip=lambda: review_skip(tag),
                desc="flow v3:LLM opus editor-review(四類)與 player-review 平行 → 一次 revise(機械驗)→ 玩家審只驗改過句 ≤2 次"
                     " → LLM sonnet fact-check 全稿只查錯 → 錯 revise+驗 → 殘留錯/裁決類 → ask_user;review_state.json")
            return out
        add("editor", fn=bind(step_editor), desc="LLM opus agent=editor-review → editor_review_r<n>.md/json;連貫斷點 → revise,一輪",
            skip=lambda: None if _review_round(tag, "editor") else "編輯審仍有效(旁白沒變或只小改)")
        add("player", fn=bind(step_player), desc="LLM opus agent=player-review → player_review_r<n>.md/json;≤2 輪,r2 仍有 → ask_user;旁白小改走小範圍審",
            skip=lambda: None if any(_review_state(tag, "player")) else "玩家審仍有效(旁白沒變)")
    elif seg == "B4":
        v3 = flow(tag) == "v3"
        add("pron", fn=memoized(tag, "B4/pron", hash_b4, bind(step_pron)),
            desc="flow v3:tts_script、sub_scan → pron_pre 確定性候選(0 條不叫 LLM)→ Sonnet pron-review 一次 → pron_apply 程式寫入,≤2 輪;輸入雜湊相同且 gate 過則略過"
            if v3 else "tts_script.py、sub_scan(ckip)→ LLM sonnet pron-review → LLM sonnet pron-apply(含 backlog 前 3)→ 重跑到未決 0,≤3 輪",
            skip=lambda: memo_skip(tag, "B4/pron", hash_b4, ok=lambda: all(i["ok"] for i in GB4.run(tag))))
    return out
