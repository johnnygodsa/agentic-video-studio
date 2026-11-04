#!/usr/bin/env python3
r"""改句:一批句子一次呼叫 LLM 改寫,機器逐項硬驗後才寫回 script.txt(工作室 v2 Phase 3,規格 docs\director_ab.md §5/§7/§8)。

python -X utf8 pipeline\line_fix.py <tag> --lines 12,15 --reason "<一句>" [--mode lint|qc|speak] [--dry-run]

fix_lines(tag, items, mode, *, call=None, dry_run=False) -> {fixed:[{line,old,new}], unresolved:[{line,why}], warn_log:[...], kept:[...], refused:str}
  items = [{line:int, reasons:[str]}](line = script.txt 行號);mode = lint | qc | speak(只影響給模型的說明)。
  call 預設 llm.call_escalating(簽名同:call(tag, fn, prompt, **kw) -> 有 ok/data/error 的結果;測試注入假的)。模型預設 sonnet,llm 與 terms_check 延遲 import。
  **不得改意思**(改意思是 revise 的事):prompt 禁止,機器只驗得到下面幾項,語意仍靠 prompt 與審稿:
    只換字幕文字(標籤、行尾 json 原樣不動;新句不可含 | 、 ;; 、換行)/ 數字集合相同 / 行尾 hl 字串(原句有的)仍在新句 /
    送配音後阿拉伯數字不增加 / script_lint.sentence_hits 沒有 block 項、可唸性 check_line 沒有 err、且不新增任何命中碼 /
    reasons 裡點名的命中碼要消掉。不過關帶原因重試(最多 MAX_ROUNDS 輪,每輪只重送還沒過的句子)。
  新句與原句相同 = 保留(kept):只在沒有 block/err 時可行,note 要有理由,記進 warn_log。
  最終不過的列 unresolved、不寫檔;全過才(分批)原子寫入,保留其他行與換行格式。已凍結片(有 freeze.json)整批拒絕,回 refused。
  warn_log = [{key:"<檢查>:<句號>:<代碼>", action:"fixed"|"kept", reason, at}],director 換成句雜湊鍵後落進 projects\<tag>\warn_log.json;本函式不寫它。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402
import script_lint as L  # noqa: E402
import speakable as S  # noqa: E402

MODES = ("lint", "qc", "speak")
MAX_ROUNDS = 3
MODEL = "sonnet"
SCHEMA = {
    "type": "object",
    "properties": {"fixes": {"type": "array", "items": {
        "type": "object",
        "properties": {"line": {"type": "integer"}, "new_text": {"type": "string"}, "note": {"type": "string"}},
        "required": ["line", "new_text", "note"]}}},
    "required": ["fixes"],
}
MODE_NOTE = {
    "lint": "文案 lint 命中(AI 感、句型、判決腔、語助詞等):改成不命中的白話寫法。",
    "qc": "配音品管未過(語音辨識對不上、讀音或停頓出問題):換成更好唸的說法(拆短子句、避開易讀錯字的詞、少英文);數字照舊。",
    "speak": "可唸性預檢命中(未登錄英文、易讀錯的字、句太短或太長、數字太多等):換成更好唸的說法。",
}
EXTRA_SEP = " ;; "
_ANIM_SHORT = re.compile(r"anim:[^\s#{}]+(#\S+)?")
_NUM_ARABIC = re.compile(r"\d[\d,]*(?:\.\d+)?")


# ---------------------------------------------------------------- script.txt 列解析(同 script_txt2json.split_extra 的嚴格路徑)
def script_path(tag):
    return P.ROOT / tag / "script.txt"


def _is_spoken(raw):
    s = raw.strip()
    return bool(s) and s[0] not in "@#" and "|" in s


def _split_raw(raw):
    """一行(不含換行)-> (前綴含標籤與 |, 文字前空白, 字幕文字, 文字後空白, 行尾 ' ;; {json}' 原樣或 '', extra dict)。"""
    pre, bar, rest = raw.partition("|")
    head, sep, tail = rest.rpartition(EXTRA_SEP)
    extra = {}
    if sep and (tail.lstrip().startswith("{") or _ANIM_SHORT.fullmatch(tail.strip())):
        t = tail.strip()
        if t.startswith("{"):
            try:
                d = json.loads(t)
                extra = d if isinstance(d, dict) else {}
            except ValueError:
                extra = {}
        else:
            extra = {"anim": t[5:]}
        body, tailpart = head, sep + tail
    else:
        body, tailpart = rest, ""
    lead = body[:len(body) - len(body.lstrip())]
    trail = body[len(body.rstrip()):]
    return pre + bar, lead, body.strip(), trail, tailpart, extra


def load_script(tag):
    """-> (全部元素 list[str](以 \\n 切,保留行尾 \\r), 旁白列 list[dict(no, text, extra)], says [(鍵, 唸法)])。"""
    data = script_path(tag).read_bytes().decode("utf-8")   # 不經 universal newlines,保留 CRLF

    els = data.split("\n")
    rows, says = [], []
    for i, el in enumerate(els, 1):
        raw = el.rstrip("\r")
        s = raw.strip()
        if s.startswith("@say"):
            k, eq, v = s[4:].strip().partition("=")
            if eq:
                says.append((k.strip(), v.strip()))
        elif _is_spoken(raw):
            _p, _l, text, _t, _tail, extra = _split_raw(raw)
            rows.append(dict(no=i, text=text, extra=extra))
    return els, rows, says


def write_atomic(path, text):
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:   # 不轉換換行
        f.write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------- 驗證
def numbers(t):
    """一句裡的數字集合:阿拉伯數字(去逗號)與 script_lint.num_groups 的數字群(去空白與逗號)。"""
    return {x.replace(",", "") for x in _NUM_ARABIC.findall(t)} | {re.sub(r"[\s,]", "", g) for g in L.num_groups(t)}


def _hl_list(extra):
    hl = extra.get("hl")
    return [h for h in ([hl] if isinstance(hl, str) else hl if isinstance(hl, list) else []) if isinstance(h, str) and h]


def _digits_left(text, says):
    return len(re.findall(r"[0-9]", S.say_text(text, says)))


def _hits(ln, text, nxt, says, pseg, names=()):
    """-> (lint 命中 list, speakable 命中 list)。"""
    return L.sentence_hits(ln, text, nxt, pseg), S.check_line(text, says, names=names)


def _codes(lint_hits, sp_hits):
    return {h["code"] for h in lint_hits} | {h["code"] for h in sp_hits}


def validate(new, ctx, says, pseg):
    """新句硬驗;回 None = 過,否則一句失敗原因(帶回給模型重做)。ctx = 該句的原始資訊。"""
    old = ctx["text"]
    if not isinstance(new, str) or not new.strip():
        return "new_text 是空的"
    new = new.strip()
    if "\n" in new or "\r" in new or "|" in new or EXTRA_SEP in new or EXTRA_SEP.strip() in new:
        return "new_text 不可含換行、|、;;"
    if numbers(new) != numbers(old):
        a, b = numbers(old) - numbers(new), numbers(new) - numbers(old)
        return f"數字集合不同(少了 {sorted(a)}、多了 {sorted(b)});數字要原樣保留"
    miss = [h for h in ctx["hl"] if h in old and h not in new]
    if miss:
        return f"行尾 hl 必留字串不見了:{miss}"
    if _digits_left(new, says) > _digits_left(old, says):
        return "送配音後阿拉伯數字變多(@say 的鍵被改壞了?);@say 鍵出現在句中要原樣保留"
    lint, sp = _hits(ctx["no"], new, ctx["next"], says, pseg, ctx.get("names", ()))
    blocks = [h for h in lint if h["block"]]
    errs = [h for h in sp if h["severity"] == "err"]
    if blocks or errs:
        return "仍有硬項:" + ";".join([f"{h['code']} {h['why']}" for h in blocks] + [f"{h['code']} {h['why']}" for h in errs])
    added = _codes(lint, sp) - ctx["codes"]
    if added:
        return f"新增了原本沒有的檢查命中:{sorted(added)}"
    if new == old:
        return None
    named = [c for c in ctx["codes"] if any(c in r for r in ctx["reasons"])]
    left = [c for c in named if c in _codes(lint, sp)]
    if left:
        return f"reasons 點名的命中還在:{left}"
    return None


# ---------------------------------------------------------------- prompt
def build_prompt(pending, mode, rejected):
    rules = [
        "只改字幕文字;意思、事實、立場、語氣強度都不變,不新增資訊、不刪關鍵資訊(改意思不是你的工作)。",
        "句中所有數字(阿拉伯數字與中文數字)原樣保留,不增減、不換寫法。",
        "must_keep 的字串必須原字出現在新句;say_keys(@say 鍵)出現在句中要原樣保留。",
        "不新增英文詞(原句有的英文詞照留);不放 | 、;; 、換行;一行一句,台灣用語,白話口語。",
        "新句不可出現新的檢查命中,原本命中的要消掉(hits 逐條列出;判決腔、語助詞耶/蛤/齁/嗯、句尾啊 = 必消)。",
        "prev / next 是前後句,只供銜接,不要改它們。",
        "確定不用改(只有警告、沒有 block/err 才可以)就把 new_text 原樣照抄,note 寫保留的理由。",
    ]
    items = []
    for ctx in pending:
        it = dict(line=ctx["no"], text=ctx["text"], prev=ctx["prev"], next=ctx["next"], reasons=ctx["reasons"], hits=ctx["why"],
                  must_keep=ctx["hl"], say_keys=ctx["say_keys"])
        if ctx["no"] in rejected:
            it["上一版被退回"] = rejected[ctx["no"]]
        items.append(it)
    return "\n".join([
        "你是繁體中文遊戲影片旁白的改句員。以下句子要改寫。", f"原因類型:{MODE_NOTE[mode]}", "", "硬規則(機器逐項驗,不過會退回重做):",
        *(f"{i}. {r}" for i, r in enumerate(rules, 1)), "",
        "輸入(JSON 清單,line = script.txt 行號):", json.dumps(items, ensure_ascii=False, indent=1), "",
        '輸出 JSON:{"fixes":[{"line":行號,"new_text":"新句","note":"一句話:改了什麼、為什麼"}]},每個 line 都要有一筆,不要有別的文字。',
    ])


def _payload(res):
    """call 的結果 -> (fixes list | None, 錯誤訊息)。接受 llm.Result(ok/data/error)或直接的 dict/list。"""
    if hasattr(res, "ok"):
        if not res.ok:
            return None, getattr(res, "error", "") or "LLM 呼叫失敗"
        data = res.data
    else:
        data = res
    if isinstance(data, dict):
        data = data.get("fixes", data.get("items"))
    if not isinstance(data, list):
        return None, "回傳不是 {fixes:[...]} 或清單"
    return [d for d in data if isinstance(d, dict)], ""


# ---------------------------------------------------------------- 主函式
def _now():
    return datetime.now().isoformat(timespec="seconds")


def _refusal(tag):
    import freeze
    if not freeze.load(tag):
        return ""
    return freeze.check(tag) or f"{tag} 已凍結(freeze.json);改稿需使用者同意,同意後 freeze.py {tag} --refreeze"


def fix_lines(tag, items, mode, *, call=None, dry_run=False):
    if mode not in MODES:
        raise ValueError(f"mode 要是 {MODES}")
    merged = {}
    for it in items:
        merged.setdefault(int(str(it["line"]).partition(".")[0]), []).extend(str(r) for r in it.get("reasons") or [])
    out = dict(fixed=[], unresolved=[], warn_log=[], kept=[], refused="")
    why = _refusal(tag)
    if why:
        out["refused"] = why
        out["unresolved"] = [dict(line=n, why=why) for n in sorted(merged)]
        return out
    els, rows, says = load_script(tag)
    by_no = {r["no"]: i for i, r in enumerate(rows)}
    pseg = L._pseg()
    names = S.subject_names(tag)
    ctxs, unresolved = {}, {}
    for n, reasons in sorted(merged.items()):
        i = by_no.get(n)
        if i is None:
            unresolved[n] = f"L{n} 不是旁白行"
            continue
        r = rows[i]
        if "say" in r["extra"]:
            unresolved[n] = "行尾有 say 欄位(改字幕不改配音),請手動改"
            continue
        nxt = rows[i + 1]["text"] if i + 1 < len(rows) else None
        lint, sp = _hits(n, r["text"], nxt, says, pseg, names)
        ctxs[n] = dict(no=n, text=r["text"], prev=rows[i - 1]["text"] if i else None, next=nxt, reasons=reasons, hl=_hl_list(r["extra"]), names=names,
                       say_keys=[k for k, _ in says if k in r["text"]], lint=lint, sp=sp, codes=_codes(lint, sp),
                       why=[f"{h['code']}:{h['why']}" for h in lint] + [f"{h['code']}:{h['why']}" for h in sp])
    call = call or _default_call()
    pending, rejected, good = dict(ctxs), {}, {}
    for _round in range(MAX_ROUNDS):
        if not pending:
            break
        res = call(tag, "line_fix", build_prompt(list(pending.values()), mode, rejected), agent="line-fix", model=MODEL, effort="low",
                   tools=("Read",), schema=SCHEMA, seg="C" if mode == "qc" else "B")
        fixes, err = _payload(res)
        if fixes is None:
            for n in pending:
                rejected[n] = err
            if getattr(res, "limited", False):
                break
            continue
        seen = set()
        for f in fixes:
            try:
                n = int(f.get("line"))
            except (TypeError, ValueError):
                continue
            if n not in pending or n in seen:
                continue
            seen.add(n)
            new, note = f.get("new_text"), (f.get("note") or "").strip()
            bad = validate(new, pending[n], says, pseg)
            if bad is None and isinstance(new, str) and new.strip() == pending[n]["text"] and not note:
                bad = "保留原句要在 note 寫理由"
            if bad:
                rejected[n] = f"new_text={new!r} 被退回:{bad}"
                continue
            good[n] = (new.strip(), note)
            del pending[n]
        for n in pending:
            if n not in seen:
                rejected[n] = "這一輪沒有回這句"
    for n, c in pending.items():
        unresolved[n] = rejected.get(n, "未改好")
    now = _now()
    for n, (new, note) in sorted(good.items()):
        c = ctxs[n]
        lint, sp = _hits(n, new, c["next"], says, pseg, names)
        gone = [("lint", h["code"]) for h in c["lint"] if h["code"] not in {x["code"] for x in lint}] + \
               [("speakable", h["code"]) for h in c["sp"] if h["code"] not in {x["code"] for x in sp}]
        if new == c["text"]:
            named = [c_ for c_ in c["codes"] if any(c_ in r for r in c["reasons"])] or sorted(c["codes"])
            out["kept"].append(dict(line=n, note=note))
            out["warn_log"] += [dict(key=f"{chk}:{n}:{code}", action="kept", reason=note, at=now)
                                for chk, code in dict.fromkeys([("lint", h["code"]) for h in c["lint"]] + [("speakable", h["code"]) for h in c["sp"]]) if code in named]
        else:
            out["fixed"].append(dict(line=n, old=c["text"], new=new))
            out["warn_log"] += [dict(key=f"{chk}:{n}:{code}", action="fixed", reason=note, at=now) for chk, code in dict.fromkeys(gone)]
    if out["fixed"] and not dry_run:
        # 寫入前重讀:這幾句在這段時間被別人改過就不覆蓋
        els2, rows2, _ = load_script(tag)
        cur = {r["no"]: r["text"] for r in rows2}
        for f in list(out["fixed"]):
            if cur.get(f["line"]) != f["old"]:
                out["fixed"].remove(f)
                unresolved[f["line"]] = "script.txt 在改句期間被改動,未覆蓋"
                out["warn_log"] = [w for w in out["warn_log"] if w["key"].split(":")[1] != str(f["line"])]
        for f in out["fixed"]:
            raw = els2[f["line"] - 1]
            cr = "\r" if raw.endswith("\r") else ""
            pre, lead, _old, trail, tail, _ex = _split_raw(raw[:-1] if cr else raw)
            els2[f["line"] - 1] = pre + lead + f["new"] + trail + tail + cr
        if out["fixed"]:
            write_atomic(script_path(tag), "\n".join(els2))
    out["unresolved"] = [dict(line=n, why=w) for n, w in sorted(unresolved.items())]
    return out


def _default_call():
    import llm   # 延遲 import:別的代理在寫,單元測試不載
    return llm.call_escalating


def main(argv=None):
    ap = argparse.ArgumentParser(description="改句(只換字幕文字,機器硬驗)")
    ap.add_argument("tag")
    ap.add_argument("--lines", required=True, help="script.txt 行號,逗號分隔,例 12,15")
    ap.add_argument("--reason", required=True, help="一句話說為什麼要改")
    ap.add_argument("--mode", choices=MODES, default="lint")
    ap.add_argument("--dry-run", action="store_true", help="呼叫模型並驗證,但不寫檔")
    a = ap.parse_args(argv)
    lines = [int(x) for x in re.split(r"[,\s]+", a.lines.strip()) if x]
    r = fix_lines(a.tag, [dict(line=n, reasons=[a.reason]) for n in lines], a.mode, dry_run=a.dry_run)
    if r["refused"]:
        print("拒絕:" + r["refused"])
        return 2
    for f in r["fixed"]:
        print(f"L{f['line']} {'(dry-run) ' if a.dry_run else ''}改:\n  - {f['old']}\n  + {f['new']}")
    for k in r["kept"]:
        print(f"L{k['line']} 保留:{k['note']}")
    for u in r["unresolved"]:
        print(f"L{u['line']} 未解決:{u['why']}")
    print(f"[line_fix] 改 {len(r['fixed'])}、保留 {len(r['kept'])}、未解決 {len(r['unresolved'])}、warn_log {len(r['warn_log'])} 筆" + ("(dry-run 未寫檔)" if a.dry_run else ""))
    return 1 if r["unresolved"] else 0


if __name__ == "__main__":
    sys.exit(main())
