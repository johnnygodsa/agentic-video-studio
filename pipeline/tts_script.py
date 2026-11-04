#!/usr/bin/env python3
r"""配音稿(channel/_archive/plans/PLAN_流程嚴謹化_2026-10-29.md §4.1;B4 步驟,docs/tts.md §4.5)。不配音、不動快取、不改送引擎文字。

python -X utf8 pipeline\tts_script.py <tag> [--no-words]   -> build\<tag>\tts_script.md(+ build\<tag>\words.txt、pron_backlog.md upsert)
python -X utf8 pipeline\tts_script.py <tag> --words        已凍結片也強制產 words.txt(改版 / refreeze 用;會改變該片字幕拆段)
python -X utf8 pipeline\tts_script.py <tag> --verify       重算送引擎文字與 projects\<tag>\freeze.json 比對;不一致結束碼 1,未凍結結束碼 0
python -X utf8 pipeline\tts_script.py <tag> --words-out <檔> 只抽每片詞表寫到指定檔(已凍結片做前後對照用,不寫 build\<tag>)
python -X utf8 pipeline\tts_script.py --backlog-top 3     pron_backlog.md 待規則命中最多的前 N

每行一列:行號 | 字幕拆段(⏐ = 段界;✗ = 切開詞的接縫,與 build.sub_seams 同一函式、同一斷詞器)| 送配音文字(標注顯示為 字[拼音])
          | 子句停頓秒(tts_split)| 多音字命中(來源 詞表 / 規則:word|re|default)| g2p 不一致(有 g2pW 才列)| 未登錄英文(cosy_terms)
          | 英文直送未驗證(_direct 不在 _verified:>= 2 行「英文直送多次:建議音譯」算未決,1 行「英文直送單次」警告)
          | 超長子句(標點間子句 > SUB_MAX_W 全形,ASCII 0.5;列子句與字數,pron-review / 主對話據此加逗號)
末尾統計:接縫、多音字命中、g2p 不一致、未登錄、超長子句、未決(= g2p 不一致 + 未登錄 + pron_rules unverified 命中 + 英文直送多次的詞 + 記憶 bad 要改寫)。
多音字命中欄另標語境讀音記憶「記憶 ok|bad|待聽」(pron_memory.py);pron-review 只審沒有記憶的位置。
COSY_ANNOTATE=all(E1 全標注)時命中欄另列「字→拼音(全標:memory|g2pw|pypinyin)」= all 模式新增標注與來源(詞表/規則/記憶沿用原標示)。
每片詞表 build\<tag>\words.txt:**已凍結片(projects\<tag>\freeze.json 存在)不產**,避免改動已凍結片的字幕拆段;--no-words 也不產。
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import freeze as FZ  # noqa: E402
import paths as P  # noqa: E402
import pron_memory as PM  # noqa: E402

_INIT = set("b p m f d t n l g k h j q x zh ch sh r z c s y w".split())
_UNIT = re.compile(r"\[[^\[\]\s]+\]|.", re.S)
_BOOK = re.compile(r"《([^《》\n]{2,8})》")
_EN = re.compile(r"[A-Za-z][A-Za-z0-9.&'\-]*(?: [A-Za-z0-9][A-Za-z0-9.&'\-]*)+")
_CJK = re.compile(r"[\u3400-\u9fff]")


# ------------------------------------------------------------ 稿件
def script_lines(tag):
    """[(ln, say)],與 freeze.narration_lines 同源(say = 行尾 say 欄,否則 text 套 @say)。"""
    import script_txt2json as T2J
    _, says, sections, _, defs, _ = T2J.parse(FZ.script_path(tag).read_text(encoding="utf-8-sig"))
    out = []
    for sec in sections:
        for ln in T2J.build_lines(sec["rows"], defs):
            say = ln["text"]
            for k, v in says:
                say = say.replace(k, v)
            out.append((ln, ln.get("say") or say))
    return out


# ------------------------------------------------------------ 讀音顯示
def _units(v):
    """標注值 -> [(ch|py, 內容)]:一般字一單位;拼音 token 聲母+韻母併成一單位。"""
    toks, out, i = _UNIT.findall(v), [], 0
    while i < len(toks):
        tk = toks[i]
        if len(tk) > 2 and tk[0] == "[":
            body = tk[1:-1]
            if body in _INIT and i + 1 < len(toks) and toks[i + 1][:1] == "[" and len(toks[i + 1]) > 2:
                out.append(("py", body + toks[i + 1][1:-1]))
                i += 2
                continue
            out.append(("py", body))
        else:
            out.append(("ch", tk))
        i += 1
    return out


def readable(v):
    return " ".join(u[1] for u in _units(v) if u[0] == "py") or v


def annotate(orig, v):
    """原文片段 + 標注值 -> 字[拼音](對不齊就整段 原文[拼音])。"""
    us = _units(v)
    if len(us) != len(orig):
        return f"{orig}[{readable(v)}]"
    return "".join((u[1] if u[1] == c else f"{c}[{u[1]}]") if u[0] == "ch" else f"{c}[{u[1]}]" for c, u in zip(orig, us))


def pron_view(say):
    """-> (顯示文字, 命中清單[str], unverified 規則事件[(位置, 字, 鍵, 來源)], 送引擎前的原文 t)。
    與 tts_cosy_text.pron_text 同樣順序(unsay -> 英文寫法 -> 書名號冒號 -> 記憶+詞表+規則 -> 著);只轉顯示,不改送引擎文字。"""
    import tts_cosy_text as CT
    t = CT.pron_source(say)
    spans, _ = CT._word_spans(t)
    ev = CT._live_events(t, spans)
    rep = {e[0]: e for e in ev}
    e1 = [(p, ch, v, src) for p, ch, v, src, new in CT.poly_marks(t, None, spans, ev) if new and v] if CT.annotate_mode() == "all" else []
    rep.update((p, (p, ch, v)) for p, ch, v, _src in e1)
    out, pos, hits = [], 0, []

    def plain(a, b):
        return "".join(annotate(t[p], rep[p][2]) if p in rep else t[p] for p in range(a, b))
    for s, e, v in spans:
        out.append(plain(pos, s))
        out.append(annotate(t[s:e], v))
        hits.append(f"{t[s:e]}→{readable(v)}(詞表)")
        pos = e
    out.append(plain(pos, len(t)))
    for p, ch, py, key, src, unv in ev:
        hits.append(f"{ch}→{readable(py)}(記憶)" if src == "memory" else f"{ch}→{readable(py)}(規則:{src}{',未驗證' if unv else ''})")
    hits += [f"{ch}→{readable(v)}(全標:{src})" for _p, ch, v, src in e1]   # E1 all 模式:來源 memory|g2pw|pypinyin
    shown, zhe = CT.fix_zhe("".join(out))
    if zhe:
        hits.append(f"{CT.ZHE_HIT}(fix_zhe)")
    unv = [(p, ch, key, src) for p, ch, py, key, src, u in ev if u]
    return shown, hits, unv, t


# ------------------------------------------------------------ 每片詞表
def _pieces(s):
    return [x.strip() for x in re.split(r"[,、;/|:：,\s]+", s) if x.strip()]


def _ok_len(w):
    return 2 <= len(w) <= 8 if _CJK.search(w) else 2 <= len(w) <= 24


def extra_words(tag):
    r"""projects\<tag>\seam_words.txt(pron_pre 確定性寫入的接縫詞,每行一詞):tts_script 重產 words.txt 時併入,避免被覆寫。"""
    f = P.PROJECTS / tag / "seam_words.txt"
    return [w.strip() for w in f.read_text(encoding="utf-8").splitlines() if w.strip() and not w.startswith("#")] if f.exists() else []


def extract_words(tag, lines, moe_words=None, sub_words=(), cut=None):
    """抽本片專名 + 本片出現的教育部 2–4 字詞條。lines = [(ln, say)];cut = 斷詞函式(預設 jieba)。回傳排序後清單。"""
    texts = [ln["text"] for ln, _ in lines]
    blob = "\n".join(texts)
    srcs = [FZ.script_path(tag)] + sorted((P.PROJECTS / tag).glob("facts*.md")) + [P.PROJECTS / tag / "context.md"]
    cands = []
    for f in srcs:
        if f.exists():
            s = f.read_text(encoding="utf-8-sig")
            cands += _BOOK.findall(s) + _EN.findall(s)
    for ln, _ in lines:
        hl = ln.get("hl")
        for h in (hl if isinstance(hl, list) else [hl] if hl else []):
            cands += _pieces(str(h))
    spec = P.PROJECTS / tag / "spec.json"
    if spec.exists():
        tw = json.loads(spec.read_text(encoding="utf-8")).get("tw_names") or {}
        for k, v in (tw.items() if isinstance(tw, dict) else ((x, None) for x in tw)):
            name = v.get("tw") if isinstance(v, dict) else v
            for x in [k, name] + _pieces(name or ""):
                if x:
                    cands.append(x)
    base = set(sub_words)
    words = {w for w in (c.strip() for c in cands) if _ok_len(w) and w in blob and w not in base}
    if moe_words:
        if cut is None:
            import seg as SEG
            cut = SEG.JIEBA_SEG.cut
        for t in texts:
            bounds, p = {0}, 0
            for w in cut(t):
                p += len(w)
                bounds.add(p)
            for i in range(len(t)):
                if i not in bounds:
                    continue
                for L in (2, 3, 4):
                    w = t[i:i + L]
                    # 兩端都落在斷詞界、且斷詞器把它切開(內部有界)才收:跨詞界的偶然子字串不收
                    if len(w) == L and w in moe_words and i + L in bounds and any(i < b < i + L for b in bounds) and w not in base:
                        words.add(w)
    return sorted(words)


# ------------------------------------------------------------ verify
def verify(tag, out=print):
    """0 = 一致或未凍結;1 = 不一致(列行號)。"""
    fz_file = FZ.freeze_path(tag)
    if not fz_file.exists():
        out(f"{tag}: 未凍結(沒有 {fz_file.relative_to(P.REPO)}),不比對")
        return 0
    import tts_cosy_text as CT
    fz = json.loads(fz_file.read_text(encoding="utf-8"))
    lines = script_lines(tag)
    says = [s for _, s in lines]
    bad = []
    sha_ok = FZ.text_same(tag, fz)  # 算法唯一來源 freeze.narration_sha(舊凍結才比整檔)
    engine = fz.get("engine") or "cosy3"
    tdir = P.tts_dir(tag, engine)
    for i, say in enumerate(says, 1):
        qf = tdir / f"{i:03d}.qc.json"
        if not qf.exists():      # 拆子句的行音檔在子目錄(鍵名),逐行比對略過,只靠整體 sha
            continue
        try:
            rec = json.loads(qf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if rec.get("text") not in (None, say):
            bad.append((i, "文字與錄音時不同"))
        elif engine == "cosy3" and (CT.pron_changed(rec, say) or CT.terms_changed(rec, say)):
            bad.append((i, "讀音表/英文表改過,送引擎文字已變"))
    if sha_ok and not bad:
        out(f"{tag}: 配音文本與凍結一致({len(says)} 句,engine={engine})")
        return 0
    out(f"{tag}: 配音文本與凍結不一致" + ("" if sha_ok else "(narration_sha 不符)") + f",{len(bad)} 行可定位:")
    for i, why in bad[:40]:
        out(f"  句{i}: {why}")
    if not sha_ok and not bad:
        out("  (無法定位行號:可能是拆子句的行或句數變動;用 freeze.py --status 看)")
    return 1


# ------------------------------------------------------------ 配音稿
def _cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ") if s else "-"


def long_clauses(text):
    """標點間子句寬度 > SUB_MAX_W(與字幕斷句同一個 _sub_pieces / _dw)-> [(子句, 寬度)]。"""
    import build as B
    out = []
    for p in B._sub_pieces(text):
        core = B._strip(p)
        if core and B._dw(core) > B.SUB_MAX_W:
            out.append((B._clean_sub(core), B._dw(core)))
    return out


def build_script(tag, write_words=True, force_words=False, out_dir=None):
    """out_dir 給定 = 唯讀重放:md/json 寫到該目錄,不產 words.txt、不 upsert pron_backlog(pron_pre 離線重放用)。"""
    import build as B
    import pron_backlog as PB
    import seg as SEG
    import tts_cosy_text as CT
    import tts_split as TS
    lines = script_lines(tag)
    frozen = FZ.freeze_path(tag).exists()
    wfile = SEG.tag_words_file(tag)
    if out_dir is not None:
        write_words = False
    if write_words and (not frozen or force_words):
        import tts_moe
        words = sorted(set(extract_words(tag, lines, tts_moe.load_words(), SEG.sub_words())) | set(extra_words(tag)))
        wfile.parent.mkdir(parents=True, exist_ok=True)
        wfile.write_text("# tts_script.py 自動產生(本片專名 + 本片出現的教育部辭典詞);改這裡無效,改來源或 sub_words.txt\n"
                         + "\n".join(words) + "\n", encoding="utf-8")
        print(f"每片詞表 {len(words)} 詞 -> {wfile.relative_to(P.REPO)}")
    elif frozen and write_words:
        print("已凍結:不產 words.txt(避免改動已凍結片的字幕拆段)" + (",沿用既有檔" if wfile.exists() else ""))
    SEG.set_tag(tag)
    says = [s for _, s in lines]
    import terms_check as TC
    import tts_term_qc as TQ
    unreg = TC.unregistered_by_line(says)
    dopen = TC.direct_open(says)   # 未驗證的直送英文詞:>= OPEN_MIN 行 = 未決(建議音譯),1 行 = 警告
    dmark = {}
    for w, ls in dopen.items():
        for i in ls:
            dmark.setdefault(i, []).append(f"{w}(英文直送多次:建議音譯)" if len(ls) >= TQ.OPEN_MIN else f"{w}(英文直送單次)")
    n_dmulti = sum(len(ls) >= TQ.OPEN_MIN for ls in dopen.values())
    n_dsingle = len(dopen) - n_dmulti
    import tts_g2p as G
    tts = [CT.unsay(s) for s in says]
    preds = G.predict_many(tts)
    g2p_on = preds is not None
    rows, n_seam, n_hit, n_g2p, n_unreg, n_unv, n_long, n_rewrite, backlog = [], 0, 0, 0, 0, 0, 0, 0, []
    jl, jopen = [], []   # tts_script.json:lines = 逐行結構化資料、open = 未決清單(pron_pre.py 讀,不解析 md)
    for i, (ln, say) in enumerate(lines, 1):
        segs = [t for t, _ in B.split_phrases(ln["text"])]
        seams = B.sub_seams(ln["text"])
        sub = "⏐".join(segs) + "".join(f" ✗切詞:{a}⏐{b}({why})" for a, b, why in seams)
        shown, hits, unv, t = pron_view(say)
        mem = PM.scan(t)
        hits += [f"{PM.ctx_label(e)}:{PM.LABEL[e['state']]}" for _, e in mem]
        n_rewrite += sum(PM.blocking(e) for _, e in mem)
        jopen += [dict(kind="poly", src="memory_bad", line=i, pos=p, char=e["char"], word=PM.ctx_label(e)) for p, e in mem if PM.blocking(e)]
        gaps = [g for _, g in TS.split_clauses(say)][:-1]
        dis = G.compare(tts[i - 1], preds[i - 1]) if g2p_on else []
        g2p = [f"{d['ch']}:規則{d['rule']}/g2p {d['g2p']}" for d in dis]
        ur = unreg.get(i, [])
        lc = long_clauses(ln["text"])
        n_long += len(lc)
        n_seam += len(seams)
        n_hit += len(hits)
        n_g2p += len(dis)
        n_unreg += len(ur)
        n_unv += len(unv)
        jopen += [dict(kind="poly", src="g2p", line=i, pos=d["pos"], char=d["ch"], word=PB.context(tts[i - 1], d["pos"]),
                       current=f"規則{d['rule']}/g2p {d['g2p']}") for d in dis]
        jopen += [dict(kind="poly", src="unverified", line=i, pos=p, char=ch, word=key.split("→")[0] if src == "word" and key else PB.context(t, p),
                       current=f"{key}({src})") for p, ch, key, src in unv]
        jopen += [dict(kind="english", src="unreg", line=i, word=w) for w in ur]
        jl.append(dict(i=i, text=ln["text"], say=say, t=t, shown=shown, seams=[list(x) for x in seams], hits=list(dict.fromkeys(hits)),
                       unv=[dict(pos=p, char=ch, key=key, src=src) for p, ch, key, src in unv],
                       g2p=[dict(pos=d["pos"], char=d["ch"], rule=d["rule"], g2p=d["g2p"]) for d in dis], unreg=list(ur),
                       direct=dmark.get(i, []), long=[[c, w] for c, w in lc]))
        backlog += [(d["ch"], PB.context(tts[i - 1], d["pos"]), "g2p 不一致") for d in dis]
        backlog += [(ch, key.split("→")[0] if src == "word" and key else PB.context(t, p), "pron_rules 未驗證")
                    for p, ch, key, src in unv]
        rows.append([i, sub, shown, "/".join(f"{g:.2f}" for g in gaps), "、".join(dict.fromkeys(hits)), "、".join(g2p), "、".join(ur),
                     "、".join(dmark.get(i, [])), "、".join(f"{c}({w:g})" for c, w in lc)])
    n_open = n_g2p + n_unreg + n_unv + n_dmulti + n_rewrite
    jopen += [dict(kind="english", src="direct_multi", word=w, lines=list(ls)) for w, ls in dopen.items() if len(ls) >= TQ.OPEN_MIN]
    md = [f"# 配音稿 {tag}(tts_script.py 產;改稿改 {tag}/script.txt 或讀音表後重跑)", "",
          f"斷詞器 {SEG.segmenter().name if SEG.segmenter() else 'none'};每片詞表 {'有' if wfile.exists() else '無'};"
          f"g2pW {'有' if g2p_on else '未安裝(g2p 欄不列)'};{'已凍結' if frozen else '未凍結'}", "",
          "| 行 | 字幕拆段 | 送配音文字 | 子句停頓 | 多音字命中 | g2p 不一致 | 未登錄英文 | 英文直送未驗證 | 超長子句 |",
          "|---|---|---|---|---|---|---|---|---|"]
    md += ["| " + " | ".join(_cell(c) if k else str(c) for k, c in enumerate(r)) + " |" for r in rows]
    stat = (f"接縫 {n_seam}、多音字命中 {n_hit}、g2p 不一致 {n_g2p}、未登錄 {n_unreg}、超長子句 {n_long}、"
            f"英文直送單次(警告){n_dsingle} 詞、"
            f"未決 {n_open}(= g2p 不一致 {n_g2p} + 未登錄 {n_unreg} + pron_rules unverified 命中 {n_unv}"
            f" + 英文直送多次 {n_dmulti} 詞{f' + 記憶 bad 要改寫 {n_rewrite}' if n_rewrite else ''})")
    md += ["", f"統計:{stat}", ""]
    odir = Path(out_dir) if out_dir is not None else P.build_dir(tag)
    out = odir / "tts_script.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md), encoding="utf-8")
    (odir / "tts_script.json").write_text(json.dumps(dict(
        tag=tag, frozen=frozen, n_open=n_open, n_seam=n_seam, n_hit=n_hit,
        counts=dict(g2p=n_g2p, unreg=n_unreg, unverified=n_unv, direct_multi=n_dmulti, direct_single=n_dsingle, memory_bad=n_rewrite, long=n_long),
        lines=jl, open=jopen), ensure_ascii=False, indent=1), encoding="utf-8")   # 只多寫 json,md 與送引擎文字不變
    if backlog and out_dir is None:
        new, upd = PB.upsert(backlog, tag)
        print(f"pron_backlog: 新增 {new}、更新 {upd}")
    print(f"配音稿 {len(rows)} 行 -> {out.relative_to(P.REPO) if out.is_relative_to(P.REPO) else out}\n{stat}")
    return n_open


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tag", nargs="?")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--no-words", action="store_true", help="不產 build/<tag>/words.txt")
    ap.add_argument("--words", action="store_true", help="已凍結片也強制產 words.txt(改版 / refreeze 用)")
    ap.add_argument("--words-out", help="只抽詞表寫到此檔(不寫配音稿)")
    ap.add_argument("--backlog-top", type=int, metavar="N")
    a = ap.parse_args(argv)
    if a.backlog_top:
        import pron_backlog as PB
        for r in PB.top(a.backlog_top):
            print(f"{r['字']} | {r['語境詞']} | {r['證據']} | {r['命中次數']} | {r['來源片']}")
        return 0
    if not a.tag:
        ap.error("要給 tag")
    if a.verify:
        return verify(a.tag)
    if a.words_out:
        import seg as SEG
        import tts_moe
        words = extract_words(a.tag, script_lines(a.tag), tts_moe.load_words(), SEG.sub_words())
        Path(a.words_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.words_out).write_text("\n".join(words) + "\n", encoding="utf-8")
        print(f"{len(words)} 詞 -> {a.words_out}")
        return 0
    build_script(a.tag, write_words=not a.no_words, force_words=a.words)
    return 0


if __name__ == "__main__":
    sys.exit(main())
