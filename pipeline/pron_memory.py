#!/usr/bin/env python3
r"""語境讀音記憶 pipeline\pron_memory.json(channel/_archive/plans/PLAN_C0試配與讀音記憶_2026-10-31.md §2;程式本體只用標準函式庫)。

一筆 = 字在某語境的已知結果;語境鍵 = 原文(繁體,apply_pron 看到的文字)的 左 2 + 字 + 右 2、左 1 + 字 + 右 1、`*`(任何語境),查詢由長到短。
句界與標點記 |(碰到就停,不跨標點取字),英文、數字與拼音 token 整段記 #,空白略過。
state:ok(可直接用)/ bad(已知會錯,照 fix 處理)/ undetermined(測過但看不出,不再重測,留優先聽)。
evidence:ear(使用者聽過)> test(C0 或 tts_pron_verify 實測:唸對 >= 2、唸錯 0)。ear 蓋 test;test 不可覆蓋 ear。
fix.type:mark(拼音標注)/ zhe(著換着)/ rewrite(此語境要改寫,不自動套,value 寫上次寫法)。
wrong_as.kind:alt_reading(唸成另一讀音)/ token_unstable(標注變成無關的音)/ other。
實測預設記 1+1;同鍵結果矛盾時兩邊改記各自的 2+2(ctx)並標 conflict,1+1 留 tombstone(查詢略過,之後只記 2+2);
2+2 也相同就併在同一筆的 conflicts、state 改 undetermined,不自動套用,不靜默覆蓋。

python -X utf8 pipeline\pron_memory.py lookup <句>        這句命中哪些記憶
python -X utf8 pipeline\pron_memory.py add <字> --left 穿 --right 打 --py "[zh][uó]" [--state ok] [--evidence ear] [--any]
    [--fix-type mark|zhe|rewrite --fix-value V] [--heard 左 --kind token_unstable] [--tag t] [--note n]   手動登錄
python -X utf8 pipeline\pron_memory.py list [--char 著] [--conflicts]
python -X utf8 pipeline\pron_memory.py check              格式、token 存在、衝突;有錯結束碼 1
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEM_FILE = HERE / "pron_memory.json"
DOC = ("語境讀音記憶(channel/_archive/plans/PLAN_C0試配與讀音記憶_2026-10-31.md §2;格式與指令見 pron_memory.py 檔頭)。tts_c0 / tts_pron_verify 自動寫入,"
       "手動登錄用 pron_memory.py add,不直接改檔。")
STATES = ("ok", "bad", "undetermined")
EVIDENCE = ("ear", "test")
WRONG_KINDS = ("alt_reading", "token_unstable", "other")
FIX_TYPES = ("mark", "zhe", "rewrite")
LABEL = {"ok": "記憶 ok", "bad": "記憶 bad", "undetermined": "記憶 待聽"}
ANY, BOUND, ALNUM = "*", "|", "#"
TEST_MIN_RIGHT = 2
_INIT = set("b p m f d t n l g k h j q x zh ch sh r z c s y w".split())
_TOK = re.compile(r"\[[^\[\]\s]+\]|.", re.S)
_SYM = re.compile(r"\[[^\[\]\s]+\]|[A-Za-z0-9]+|\s+|.", re.S)
_CACHE = {}


# ------------------------------------------------------------ 讀寫
def _sig(path):
    try:
        st = Path(path).stat()
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size


def load(path=None):
    """-> {"_doc", "entries"};檔案不存在回空表。"""
    path = Path(path or MEM_FILE)
    if not path.exists():
        return {"_doc": DOC, "entries": []}
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.setdefault("entries", [])
    return doc


def save(doc, path=None):
    path = Path(path or MEM_FILE)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _index(path=None):
    """-> {(字, 左, 右): 條目}(略過 tombstone);依檔案 mtime/大小快取,檔案不存在回 {}。"""
    path = Path(path or MEM_FILE)
    sig = _sig(path)
    hit = _CACHE.get(str(path))
    if hit and hit[0] == sig:
        return hit[1]
    idx = {}
    if sig is not None:
        idx = {(e["char"], e["left"], e["right"]): e for e in load(path)["entries"] if not e.get("tombstone")}
    _CACHE[str(path)] = (sig, idx)
    return idx


def has_entries(path=None):
    return bool(_index(path))


# ------------------------------------------------------------ 語境
def _symbols(text):
    """-> (語境符號 list, {漢字位置: 符號序})。英文、數字、拼音 token 連成一個 #;標點連成一個 |;空白略過。"""
    syms, at = [], {}
    for m in _SYM.finditer(text):
        tk = m.group(0)
        if tk.isspace():
            continue
        if len(tk) == 1 and ("㐀" <= tk <= "鿿" or "豈" <= tk <= "﫿"):
            at[m.start()] = len(syms)
            syms.append(tk)
            continue
        s = ALNUM if len(tk) > 1 or (tk.isascii() and tk.isalnum()) else BOUND
        if not syms or syms[-1] != s:
            syms.append(s)
    return syms, at


def _side(syms, i, n, step):
    out, k = [], i + step
    while len(out) < n:
        s = syms[k] if 0 <= k < len(syms) else BOUND
        out.append(s)
        if s == BOUND:
            break
        k += step
    return "".join(reversed(out) if step < 0 else out)


def _keys(syms, i):
    """[(左2, 右2), (左1, 右1), (*, *)],查詢由長到短。"""
    return [(_side(syms, i, n, -1), _side(syms, i, n, 1)) for n in (2, 1)] + [(ANY, ANY)]


def context(text, pos):
    """text[pos] 的語境鍵 -> dict(l2, r2, l1, r1);pos 不是漢字回 None。"""
    syms, at = _symbols(text)
    if pos not in at:
        return None
    (l2, r2), (l1, r1), _ = _keys(syms, at[pos])
    return dict(l2=l2, r2=r2, l1=l1, r1=r1)


def scan(text, path=None):
    """這句命中的記憶 -> [(位置, 條目)];每個位置取最長語境。表空回 [],不做任何字串處理。"""
    idx = _index(path)
    if not idx:
        return []
    chars = {k[0] for k in idx}
    if chars.isdisjoint(text):
        return []
    syms, at = _symbols(text)
    out = []
    for p, i in at.items():
        ch = text[p]
        if ch in chars:
            e = next((idx[(ch, a, b)] for a, b in _keys(syms, i) if (ch, a, b) in idx), None)
            if e:
                out.append((p, e))
    return out


# ------------------------------------------------------------ 條目解讀
def mark_value(e):
    """apply_pron 要在這個位置換上的值;不自動套用(undetermined、rewrite、沒有 fix)回 None。"""
    fix = e.get("fix") or {}
    if e.get("state") not in ("ok", "bad"):
        return None
    if fix.get("type") == "zhe":
        return fix.get("value") or "着"
    return fix.get("value") if fix.get("type") == "mark" else None


def blocking(e):
    """bad + rewrite:這個語境要改寫,配音稿算未決、C0 算唸錯。"""
    return e.get("state") == "bad" and (e.get("fix") or {}).get("type") == "rewrite"


def ctx_label(e):
    return e["char"] if e["left"] == ANY else f"{e['left']}{e['char']}{e['right']}"


def hit_key(e):
    """pron_hits 的鍵(格式同規則的「詞→標注」)。"""
    return f"{ctx_label(e)}→{mark_value(e)}"


def fix_of(ch, py):
    """送引擎的值 -> fix(著換着 = zhe,其餘 mark);沒有標注回 None。"""
    if not py:
        return None
    return dict(type="zhe", value=py) if ch == "著" and py == "着" else dict(type="mark", value=py)


def units(v):
    """標注值 -> 每個字一單位的原字串(聲母 + 韻母 token 併一單位,一般字一單位)。"""
    toks, out, i = _TOK.findall(v), [], 0
    while i < len(toks):
        tk = toks[i]
        if tk[1:-1] in _INIT and i + 1 < len(toks) and len(toks[i + 1]) > 2:
            out.append(tk + toks[i + 1])
            i += 2
        else:
            out.append(tk)
            i += 1
    return out


# ------------------------------------------------------------ 寫入
def state_of(n_right, n_wrong, _n_undetermined=0):
    """實測結果 -> state(唸對 >= 2 且唸錯 0 才 ok;無法判定不算通過)。"""
    if n_wrong:
        return "bad"
    return "ok" if n_right >= TEST_MIN_RIGHT else "undetermined"


def make_entry(ch, left, right, py="", state="ok", evidence="test", wrong_as=None, fix=None, n_right=0, n_wrong=0, n_undetermined=0,
               tag="", day=None, note="", ctx=None):
    e = dict(char=ch, left=left, right=right, py=py, state=state, evidence=evidence, wrong_as=list(wrong_as or []), fix=fix,
             seeds=n_right + n_wrong + n_undetermined, n_right=n_right, n_wrong=n_wrong, n_undetermined=n_undetermined,
             tag=tag, date=day or date.today().isoformat(), note=note)
    if ctx:
        e["ctx"] = list(ctx)
    return e


def _find(rows, e):
    return next((r for r in rows if (r["char"], r["left"], r["right"]) == (e["char"], e["left"], e["right"])), None)


def _contradicts(a, b):
    return bool(a["py"] and b["py"] and a["py"] != b["py"]) or {a["state"], b["state"]} == {"ok", "bad"}


def _merge_wrong(a, b):
    out = list(a.get("wrong_as") or [])
    return out + [x for x in b.get("wrong_as") or [] if x not in out]


def _add_run(e, run):
    if run:
        e.setdefault("runs", []).append(run)


def _merge(old, e, run):
    for k in ("seeds", "n_right", "n_wrong", "n_undetermined"):
        old[k] += e[k]
    state = state_of(old["n_right"], old["n_wrong"]) if old["evidence"] == "test" else e["state"]
    if e["state"] == state:
        old["fix"] = e["fix"] or old["fix"]
    old["state"], old["py"] = state, old["py"] or e["py"]
    old["wrong_as"], old["date"] = _merge_wrong(old, e), e["date"]
    if old.get("ctx") and e.get("ctx") and old["ctx"] != e["ctx"]:
        old.pop("ctx")   # 已涵蓋多個 2+2:之後矛盾時無法細分,走同筆並列
    _add_run(old, run)


def _rekey(e, ctx):
    return dict(e, left=ctx[0], right=ctx[1], conflict=True)


def _split(doc, old, e, run):
    """同鍵結果矛盾:兩邊各記自己的 2+2 並標 conflict;2+2 分不開就併在同一筆、改 undetermined。"""
    rows = doc["entries"]
    a, b = old.get("ctx"), e.get("ctx")
    if not a or not b or a == b or [old["left"], old["right"]] == a:
        old.setdefault("conflicts", []).append({k: e.get(k) for k in ("py", "state", "evidence", "n_right", "n_wrong", "n_undetermined", "tag", "date")})
        old["state"], old["fix"] = "undetermined", None
        _add_run(old, run)
        return "conflict"
    rows.remove(old)
    tomb = make_entry(old["char"], old["left"], old["right"], state="undetermined", evidence=old["evidence"],
                      tag=e["tag"], day=e["date"], note="1+1 結果矛盾,已改記 2+2")
    tomb["tombstone"] = True
    rows.append(tomb)
    rows.append(_rekey(old, a))
    new = _rekey(e, b)
    _add_run(new, run)
    rows.append(new)
    return "conflict"


def upsert(doc, e, run=None):
    """新增或併入一筆。-> added / merged / replaced / conflict / ear_kept / skipped(同一次實測已記過,重跑判定不重複累計)。"""
    rows = doc["entries"]
    old = _find(rows, e)
    if old is None:
        _add_run(e, run)
        rows.append(e)
        return "added"
    if run and run in old.get("runs", []):
        return "skipped"
    if old.get("tombstone"):
        if not e.get("ctx") or [e["left"], e["right"]] == e["ctx"]:
            old.setdefault("conflicts", []).append({k: e.get(k) for k in ("py", "state", "evidence", "tag", "date")})
            _add_run(old, run)
            return "conflict"
        return upsert(doc, _rekey(e, e["ctx"]), run)
    if e["evidence"] == "test" and old["evidence"] == "ear":
        return "ear_kept"
    if e["evidence"] == "ear" and old["evidence"] == "test":
        e["wrong_as"] = _merge_wrong(old, e)
        _add_run(e, run)
        rows[rows.index(old)] = e
        return "replaced"
    if _contradicts(old, e):
        return _split(doc, old, e, run)
    _merge(old, e, run)
    return "merged"


def seed_outcome(p):
    """judge_record 的一個位置 -> right / wrong / undetermined。只有相似度過、沒有任何辨識聽成應讀音的同音字時算無法判定
    (辨識線索不寫進 ok,PLAN §1、§2)。"""
    if p["result"] == "right" and "right" not in (p.get("main"), p.get("second")):
        return "undetermined"
    return p["result"]


def wrong_entry(p, py, ph=None):
    """唸錯的位置 -> wrong_as 一項 dict(heard, kind);聽成 None 回 None。"""
    h = p.get("hyp_main") if p.get("main") == "wrong" else p.get("hyp_second") if p.get("second") == "wrong" else None
    if h is None:
        return None
    kind = "other"
    if ph is not None:
        kind = "alt_reading" if ph.one(h) in ph.all(p["ch"]) - {p.get("want")} else "token_unstable" if py else "other"
    return dict(heard=h, kind=kind)


def record_tests(rows, run, ph=None, day=None, path=None):
    """實測結果寫進記憶表(tts_c0 與 tts_pron_verify 共用)。rows = [dict(text, pos, ch, py, results=[judge_record 的位置], tag, rewrite)];
    同一次實測、同 1+1 語境、同標注先彙總再寫;run = 這次實測的識別字串。-> Counter(動作)。"""
    groups = defaultdict(lambda: dict(c=Counter(), wrong=[], rewrite="", tag="", ctx=None))
    for r in rows:
        c = context(r["text"], r["pos"])
        if c is None or not r["results"]:
            continue
        g = groups[(r["ch"], c["l1"], c["r1"], r.get("py") or "")]
        g["tag"] = g["tag"] or r.get("tag") or ""
        g["rewrite"] = g["rewrite"] or r.get("rewrite") or ""
        g["ctx"] = g["ctx"] or (c["l2"], c["r2"])
        for p in r["results"]:
            o = seed_outcome(p)
            g["c"][o] += 1
            w = wrong_entry(p, r.get("py"), ph) if o == "wrong" else None
            if w and w not in g["wrong"]:
                g["wrong"].append(w)
    if not groups:
        return Counter()
    doc, acts = load(path), Counter()
    for (ch, left, right, py), g in groups.items():
        c = g["c"]
        state = state_of(c["right"], c["wrong"])
        fix = dict(type="rewrite", value=g["rewrite"]) if state == "bad" else fix_of(ch, py)
        e = make_entry(ch, left, right, py, state, "test", g["wrong"], fix, c["right"], c["wrong"], c["undetermined"], g["tag"], day, ctx=g["ctx"])
        acts[upsert(doc, e, f"{run}/{py}")] += 1
    save(doc, path)
    return acts


# ------------------------------------------------------------ 檢查
def check(doc, tokens=None):
    """-> (錯誤 list, 衝突 list)。tokens = CosyVoice3 tokenizer 的 token 集合(None = 不驗)。"""
    errs, conflicts, seen = [], [], set()
    for i, e in enumerate(doc.get("entries", [])):
        name = f"#{i} {e.get('left')}{e.get('char')}{e.get('right')}"
        miss = [k for k in ("char", "left", "right", "py", "state", "evidence", "fix", "date") if k not in e]
        if miss:
            errs.append(f"{name}: 缺欄位 {miss}")
            continue
        key = (e["char"], e["left"], e["right"])
        if key in seen:
            errs.append(f"{name}: 同鍵重複")
        seen.add(key)
        if e.get("conflict") or e.get("conflicts"):
            conflicts.append(name)
        if e.get("tombstone"):
            continue
        fix = e["fix"] or {}
        if e["state"] not in STATES:
            errs.append(f"{name}: state 不對({e['state']})")
        if e["evidence"] not in EVIDENCE:
            errs.append(f"{name}: evidence 不對({e['evidence']})")
        if fix and fix.get("type") not in FIX_TYPES:
            errs.append(f"{name}: fix.type 不對({fix.get('type')})")
        if e["state"] == "bad" and not fix:
            errs.append(f"{name}: bad 要有 fix")
        if e["state"] == "ok" and e["evidence"] == "test" and (e.get("n_right", 0) < TEST_MIN_RIGHT or e.get("n_wrong", 0)):
            errs.append(f"{name}: test 的 ok 要唸對 >= {TEST_MIN_RIGHT}、唸錯 0")
        for w in e.get("wrong_as") or []:
            if w.get("kind") not in WRONG_KINDS:
                errs.append(f"{name}: wrong_as.kind 不對({w.get('kind')})")
        if tokens is not None:
            vals = [e["py"]] + ([fix.get("value") or ""] if fix.get("type") == "mark" else [])
            bad = sorted({t for v in vals for t in re.findall(r"\[[^\[\]\s]+\]", v)} - tokens)
            if bad:
                errs.append(f"{name}: 拼音 token 不存在 {bad}")
    return errs, conflicts


# ------------------------------------------------------------ CLI
def _line(e):
    return (f"{ctx_label(e)} {e['state']}/{e['evidence']} 標注 {e['py'] or '-'} fix {(e.get('fix') or {}).get('type') or '-'} "
            f"對{e.get('n_right', 0)} 錯{e.get('n_wrong', 0)} 無{e.get('n_undetermined', 0)} {e.get('tag', '')} {e.get('date', '')}"
            + (" 衝突" if e.get("conflict") or e.get("conflicts") else "") + (" 已停用" if e.get("tombstone") else ""))


def _cmd_lookup(a):
    import tts_cosy_text as CT
    hits = scan(CT.pron_source(a.text))
    for p, e in hits:
        print(f"位置 {p}:{_line(e)}")
    if not hits:
        print("無命中")
    return 0


def _cmd_add(a):
    if a.any:
        a.left = a.right = ANY
    elif a.left is None or a.right is None:
        sys.exit("要給 --left 與 --right,或 --any")
    fix = dict(type=a.fix_type, value=a.fix_value or (a.py if a.fix_type == "mark" else "着" if a.fix_type == "zhe" else "")) if a.fix_type else fix_of(a.char, a.py)
    wrong = [dict(heard=a.heard, kind=a.kind)] if a.heard else []
    e = make_entry(a.char, a.left, a.right, a.py, a.state, a.evidence, wrong, fix, tag=a.tag, note=a.note)
    errs, _ = check({"entries": [e]}, _tokens())
    if errs:
        sys.exit("\n".join(errs))
    doc = load()
    act = upsert(doc, e)
    save(doc)
    print(f"{act}:{_line(e)}")
    return 0


def _cmd_list(a):
    rows = [e for e in load()["entries"] if (not a.char or e["char"] == a.char) and (not a.conflicts or e.get("conflict") or e.get("conflicts"))]
    for e in rows:
        print(_line(e))
    print(f"共 {len(rows)} 筆")
    return 0


def _tokens():
    import tts_cosy_text as CT
    return CT._tokenizer_tokens() if CT.TOKENIZER_PY.exists() else None


def _cmd_check(_a):
    doc = load()
    errs, conflicts = check(doc, _tokens())
    for x in errs:
        print("錯誤:" + x)
    for x in conflicts:
        print("衝突:" + x)
    print(f"{len(doc['entries'])} 筆,錯誤 {len(errs)}、衝突 {len(conflicts)}")
    return 1 if errs else 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="語境讀音記憶")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("lookup")
    s.add_argument("text")
    s.set_defaults(fn=_cmd_lookup)
    s = sub.add_parser("add")
    s.add_argument("char")
    s.add_argument("--left")
    s.add_argument("--right")
    s.add_argument("--any", action="store_true", help="任何語境(標注本身不穩的字)")
    s.add_argument("--py", default="")
    s.add_argument("--state", choices=STATES, default="ok")
    s.add_argument("--evidence", choices=EVIDENCE, default="ear")
    s.add_argument("--fix-type", choices=FIX_TYPES)
    s.add_argument("--fix-value")
    s.add_argument("--heard")
    s.add_argument("--kind", choices=WRONG_KINDS, default="other")
    s.add_argument("--tag", default="")
    s.add_argument("--note", default="")
    s.set_defaults(fn=_cmd_add)
    s = sub.add_parser("list")
    s.add_argument("--char")
    s.add_argument("--conflicts", action="store_true")
    s.set_defaults(fn=_cmd_list)
    s = sub.add_parser("check")
    s.set_defaults(fn=_cmd_check)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
