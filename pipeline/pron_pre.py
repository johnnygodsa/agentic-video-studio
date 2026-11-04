#!/usr/bin/env python3
r"""B4 讀音確定性候選(flow v3;PLAN_token重設計_2026-11-03 §2(b) B2;規格 docs\director_ab.md「B4 v3」)。

python -X utf8 pipeline\pron_pre.py <tag> [--json] [--bdir <目錄>]    印候選;只讀(不寫 words.txt)

candidates(tag) -> {"seams","poly","english","backlog","auto_words","n"}:
- 資料來源 = build\<tag>\tts_script.json(tts_script.py 另寫的結構化統計,不解析 md)+ build\<tag>\sub_scan.json(seam_list)+ pron_backlog。
- seams:sub_scan 接縫;詞被斷詞器切成單一 token 的**程式直接寫** projects\<tag>\seam_words.txt 與 build\<tag>\words.txt(已凍結片不寫),
  呼叫端給 rescan 就重跑 sub_scan,仍剩的才是候選。
- poly:tts_script 算進「未決」的多音字位置(unverified 規則命中、g2p 不一致、記憶 bad),附本句、現標注、tts_moe lookup(字與語境詞)、pron_rules 該字條目。
  已審過的不再列:本片 pron_apply.json decided 帳本有的、規則條目 note 含「讀音審」的詞規則命中。
- english:未登錄英文、英文直送多次的詞,附句子(已在 decided 帳本者不列)。
- backlog:gate_b4.backlog_pending(本片 pron_backlog 前 3 條還沒處理紀錄的列),附命中句與 lookup。
n = 四類候選總數;n == 0 → step_pron 不呼叫 LLM。
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import paths as P  # noqa: E402

SENT_MAX = 3      # 英文 / backlog 每個候選最多附幾句
WORD_OK = re.compile(r"^.{2,8}$")


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _frozen(tag):
    return (P.PROJECTS / tag / "freeze.json").exists()


def decided(tag):
    """本片 pron_apply.json 的 decided 帳本 -> {(kind, char, word)}。"""
    d = _read_json(P.PROJECTS / tag / "pron_apply.json") or {}
    return {(x.get("kind"), x.get("char") or "", x.get("word") or "") for x in d.get("decided") or []}


# ------------------------------------------------------------ 接縫
def seam_words_file(tag):
    return P.PROJECTS / tag / "seam_words.txt"


def _seam_rows(sub, ts):
    """sub_scan.json 的 seam_list(+judge);舊檔沒有就退回 tts_script.json 逐行 seams(token 不明 = False)。"""
    rows = list(sub.get("seam_list") or []) + list(sub.get("seam_list_judge") or [])
    if not rows:
        for ln in (ts or {}).get("lines") or []:
            for a, b, why in ln.get("seams") or []:
                m = re.search(r"詞「(.+?)」", why)
                rows.append({"line": ln["i"], "a": a, "b": b, "why": why, "word": m.group(1) if m else None, "token": False})
    out, seen = [], set()
    for r in rows:
        k = (r.get("line"), r.get("a"), r.get("b"))
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def _write_seam_words(tag, words):
    """寫 projects\\<tag>\\seam_words.txt(tts_script 重產 words.txt 時併入)與 build\\<tag>\\words.txt(sub_scan 立即生效);回傳新增詞。"""
    import seg as SEG
    f = seam_words_file(tag)
    have = {w.strip() for w in f.read_text(encoding="utf-8").splitlines()} if f.exists() else set()
    new = [w for w in dict.fromkeys(words) if w not in have]
    if new:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write("".join(w + "\n" for w in new))
    wf = SEG.tag_words_file(tag)
    cur = wf.read_text(encoding="utf-8") if wf.exists() else "# pron_pre.py 寫入的接縫詞(其餘由 tts_script.py 產生)\n"
    have_w = set(cur.splitlines())
    add = [w for w in dict.fromkeys(words) if w not in have_w]
    if add:
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text(cur + ("" if cur.endswith("\n") else "\n") + "".join(w + "\n" for w in add), encoding="utf-8")
    return new


def _seams(tag, ts, write, rescan):
    sdir = P.build_dir(tag) / "sub_scan.json"
    sub = _read_json(sdir) or {}
    if not max(int(sub.get("seams") or 0), int(sub.get("seams_judge") or 0)):
        return [], []
    rows = _seam_rows(sub, ts)
    have = set(seam_words_file(tag).read_text(encoding="utf-8").split()) if seam_words_file(tag).exists() else set()
    auto = [r["word"] for r in rows if r.get("token") and r.get("word") and r["word"] not in have]
    if auto and not _frozen(tag):
        if write:
            _write_seam_words(tag, auto)
            if rescan is not None:
                rescan()
                sub = _read_json(sdir) or sub
                rows = _seam_rows(sub, ts)
        else:   # 唯讀:當作會被自動解掉
            rows = [r for r in rows if r.get("word") not in auto]
    else:
        auto = []
    line_text = {ln["i"]: ln.get("text") for ln in (ts or {}).get("lines") or []}
    cand = [dict(line=r["line"], a=r["a"], b=r["b"], why=r["why"], word=r.get("word") or f"{r['a']}|{r['b']}", seam_word=r.get("word"),
                 text=line_text.get(r["line"])) for r in rows]
    return cand, auto


# ------------------------------------------------------------ 多音字
def _lookup(q):
    import tts_moe
    try:
        return tts_moe.lookup(q)
    except Exception as e:  # noqa: BLE001
        return [f"lookup 失敗:{e}"]


def _rules_of(ch):
    d = _read_json(P.REPO / "pipeline" / "pron_rules.json") or {}
    return d.get(ch)


def _reviewed_rule(ch, word):
    """pron_rules 該字有含 word 的詞規則且 note 記過讀音審 = 先前審過(不是新規則第一次命中)。"""
    e = _rules_of(ch) or {}
    for r in e.get("rules") or []:
        if word in (r.get("words") or []) and "讀音審" in (r.get("note") or ""):
            return True
    return False


def _poly(tag, ts, seen):
    lines = {ln["i"]: ln for ln in (ts or {}).get("lines") or []}
    out = []
    for o in (ts or {}).get("open") or []:
        if o.get("kind") != "poly":
            continue
        ch, word = o.get("char") or "", o.get("word") or ""
        if ("poly", ch, word) in seen:
            continue
        if o.get("src") == "unverified" and _reviewed_rule(ch, word):
            continue
        ln = lines.get(o["line"]) or {}
        lk = {ch: _lookup(ch)}
        if len(word) > 1:
            lk[word] = _lookup(word)
        out.append(dict(line=o["line"], char=ch, word=word, src=o.get("src"), current=o.get("current"), sentence=ln.get("t") or ln.get("text"),
                        shown=ln.get("shown"), lookup=lk, rules=_rules_of(ch)))
    return out


def _english(tag, ts, seen):
    lines = {ln["i"]: ln for ln in (ts or {}).get("lines") or []}
    out = []
    for o in (ts or {}).get("open") or []:
        if o.get("kind") != "english" or ("english", "", o.get("word") or "") in seen:
            continue
        ls = o.get("lines") or ([o["line"]] if "line" in o else [])
        out.append(dict(word=o.get("word"), src=o.get("src"), lines=ls,
                        sentences=[(lines.get(i) or {}).get("t") for i in ls[:SENT_MAX]]))
    return out


def _backlog(tag, ts):
    from gates import gate_b4 as GB4
    lines = (ts or {}).get("lines") or []
    out = []
    for r in GB4.backlog_pending(tag):
        ch, ctx = r["字"], r["語境詞"]
        sents = [(ln.get("t"), ln["i"]) for ln in lines if ctx and ctx in (ln.get("t") or "")][:SENT_MAX]
        lk = {ch: _lookup(ch)}
        if len(ctx) > 1:
            lk[ctx] = _lookup(ctx)
        out.append(dict(char=ch, context=ctx, evidence=r["證據"], hits=r["命中次數"],
                        sentences=[dict(line=i, text=t) for t, i in sents], lookup=lk, rules=_rules_of(ch)))
    return out


def candidates(tag, bdir=None, write=True, rescan=None):
    """見檔頭。bdir = tts_script.json 所在目錄(離線重放用,預設 build\\<tag>);write=False 不寫 words.txt;rescan = 寫詞後重跑 sub_scan 的 callable。"""
    ts = _read_json(Path(bdir or P.build_dir(tag)) / "tts_script.json")
    if ts is None:
        raise FileNotFoundError(f"沒有 tts_script.json(先跑 tts_script.py {tag})")
    seen = decided(tag)
    seams, auto = _seams(tag, ts, write, rescan)
    seams = [s for s in seams if ("seam", "", s["word"]) not in seen]
    poly, eng, bl = _poly(tag, ts, seen), _english(tag, ts, seen), _backlog(tag, ts)
    return {"seams": seams, "poly": poly, "english": eng, "backlog": bl, "auto_words": auto,
            "n": len(seams) + len(poly) + len(eng) + len(bl)}


def counts(c):
    return {k: len(c[k]) for k in ("seams", "poly", "english", "backlog")} | {"auto_words": len(c.get("auto_words") or [])}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tag")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--bdir", help="tts_script.json 所在目錄(預設 build\\<tag>)")
    a = ap.parse_args(argv)
    c = candidates(a.tag, bdir=a.bdir, write=False)
    if a.json:
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return 0
    print(f"{a.tag}: 候選 {c['n']}  {counts(c)}")
    for s in c["seams"]:
        print(f"  接縫 句{s['line']} {s['a']}⏐{s['b']}({s['why']})")
    for p in c["poly"]:
        print(f"  多音 句{p['line']} {p['char']} 〈{p['word']}〉{p['src']} {p['current']}")
    for e in c["english"]:
        print(f"  英文 {e['word']} {e['src']} 句{e['lines']}")
    for b in c["backlog"]:
        print(f"  backlog {b['char']}|{b['context']} ×{b['hits']}")
    if c["auto_words"]:
        print(f"  (程式會自動寫入的接縫詞:{'、'.join(c['auto_words'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
