"""E3 盲聽版:Gemini 不看參考文字先逐字轉寫(字 + 帶調拼音 + 停頓位置),再由程式機械比對參考文字。
為什麼:ear_e3_gemini 附參考文字的審稿提示,flash-lite 會照文字點頭(真值召回 2%);盲轉寫時它分得出壞例。

用法
  python -X utf8 pipeline\senses\ear_e3_blind.py --truth channel\taste\ear\truth.json --out tmp\ear_e3_blind.json [--model gemini-3.5-flash-lite] [--rpm 10]
  python -X utf8 pipeline\senses\ear_e3_blind.py --wav f.wav --text "參考文字"
快取:tmp\ear_e3_blind_cache.json 以 (wav sha1, model) 為鍵,重算評分不重打 API(--redo 強制重打)。
旗標(每句):
  tone      對齊後同音節但聲調不同(忽略輕聲、三聲連讀、一/不 變調)
  syl       音節不同(多唸、漏唸、讀錯;參考文字夾數字或英文的空隙不算)
  runon     參考文字的逗號/頓號/分號處沒聽到停頓(<0.15 秒)
  misplaced 聽到 ≥0.3 秒停頓但參考文字該處沒有標點
  long_span 連續 >LONG_SPAN 字沒停頓
真值比對:讀音類壞例算 tone/syl 命中(嚴格:位置 ±1 相符);斷句/停頓類算 runon/misplaced/long_span;其餘任一旗標。
好例:每種旗標分別算誤報率,方便挑要開哪幾種。
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402
from senses import ear_e3_gemini as g  # noqa: E402
from pypinyin import Style, lazy_pinyin  # noqa: E402

LONG_SPAN = 18
CJK = re.compile(r"[一-鿿]")
PAUSE_PUNCT = ",、;:,;:"
ANY_PUNCT = PAUSE_PUNCT + "。.!?!?《》「」『』()()—…"

BLIND_PROMPT = """你是國語語音轉寫員。請只憑你聽到的聲音,逐字轉寫這段音檔(台灣國語),不要猜測、不要修正成通順的句子:聽到什麼就寫什麼,聽不清就照最接近的音寫。
輸出 JSON(只輸出 JSON):
{"transcript": "逐字轉寫(繁體中文,英文詞照英文寫)",
 "syllables": [{"char": "字", "pinyin": "帶聲調數字的拼音,例 hai2、zhe5(輕聲用 5)"}],  # 每個中文字一項,依順序;英文詞一項 {"char":"英文詞","pinyin":"EN"}
 "pauses": [{"after_index": 停頓前最後一個 syllables 的索引(從 0 起), "sec": 停頓秒數(小數)}],  # 只列 ≥0.1 秒的明顯停頓,不含句尾
 "unclear": [索引, ...]  # 聽不清楚、像被吞掉或糊在一起的音節索引
}"""


NUMERAL = set("一二三四五六七八九十百千萬億零兩點分之")
EQUIV = {"得": {"de2", "de5", "dei3"}, "的": {"de5", "di4", "di2"}, "了": {"le5", "liao3"}}  # 參考拼音不可靠的常用字:任一讀音都算同音節


def ref_tokens(text):
    """參考文字 -> [(idx_in_text, char, pinyin_tone3)];只取中文字。著→着(專案配音稿也這樣轉)。"""
    chars = [(i, c) for i, c in enumerate(text) if CJK.match(c)]
    pys = lazy_pinyin("".join(("着" if c == "著" else c) for _, c in chars), style=Style.TONE3, neutral_tone_with_five=True)
    return [(i, c, p) for (i, c), p in zip(chars, pys)]


def split_py(p):
    m = re.match(r"^([a-zü:]+)([1-5])?$", (p or "").strip().lower().replace("v", "ü"))
    return (m.group(1), int(m.group(2) or 5)) if m else (p, 5)


def gap_has_other(text, a, b):
    """參考文字 text[a+1:b] 之間有沒有數字或英文字母(TTS 會唸出額外音節)。"""
    seg = text[a + 1:b] if b > a else ""
    return bool(re.search(r"[0-9A-Za-z]", seg))


def tone_ok(ref_tone, heard_tone, ref_char, next_ref_tone):
    if ref_tone == heard_tone or ref_tone == 5 or heard_tone == 5:
        return True
    if ref_char in "一不":
        return True
    if ref_tone == 3 and heard_tone == 2 and next_ref_tone == 3:  # 三聲連讀
        return True
    return False


def compare(text, blind):
    """盲轉寫結果 vs 參考文字 -> dict(flags, issues, spans)。"""
    ref = ref_tokens(text)
    syl = [s for s in (blind.get("syllables") or []) if isinstance(s, dict)]
    heard = [(str(s.get("char") or ""), str(s.get("pinyin") or "")) for s in syl]
    heard_cjk = [(k, c, p) for k, (c, p) in enumerate(heard) if CJK.match(c or "") and p.upper() != "EN"]
    a = [split_py(p)[0] for _, _, p in ref]
    b = [split_py(p)[0] for _, _, p in heard_cjk]
    issues = []
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for di in range(i2 - i1):
                ri, hj = i1 + di, j1 + di
                rt, ht = split_py(ref[ri][2])[1], split_py(heard_cjk[hj][2])[1]
                nxt = split_py(ref[ri + 1][2])[1] if ri + 1 < len(ref) else 0
                if not tone_ok(rt, ht, ref[ri][1], nxt):
                    issues.append(dict(kind="tone", ref_pos=ref[ri][0], ref_char=ref[ri][1], ref_py=ref[ri][2], heard_py=heard_cjk[hj][2]))
            continue
        prev_txt = ref[i1 - 1][0] if i1 > 0 else -1
        next_txt = ref[i1][0] if i1 < len(ref) else len(text)
        if op == "insert" and gap_has_other(text, prev_txt, next_txt):
            continue  # 數字/英文的空隙,TTS 多唸的音節不算
        if op == "replace" and gap_has_other(text, prev_txt, next_txt):
            continue
        if op in ("replace", "delete"):
            for ri in range(i1, i2):
                hp = heard_cjk[j1 + (ri - i1)][2] if op == "replace" and j1 + (ri - i1) < j2 else ""
                if op == "delete" and ref[ri][1] in NUMERAL:
                    continue  # 模型常把數字轉成阿拉伯數字,不算漏唸
                if ref[ri][1] in EQUIV and (hp.lower() in EQUIV[ref[ri][1]] or not hp):
                    continue
                issues.append(dict(kind="syl", ref_pos=ref[ri][0], ref_char=ref[ri][1], ref_py=ref[ri][2], heard_py=hp))
        else:  # insert
            issues.append(dict(kind="syl", ref_pos=next_txt, ref_char="", ref_py="",
                               heard_py="+" + " ".join(p for _, _, p in heard_cjk[j1:j2])))
    # 停頓:把 heard 索引映回參考文字位置
    hmap = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for di in range(i2 - i1):
                hmap[heard_cjk[j1 + di][0]] = ref[i1 + di][0]
    pauses = []
    for p in blind.get("pauses") or []:
        if not isinstance(p, dict):
            continue
        try:
            k, sec = int(p.get("after_index")), float(p.get("sec") or 0)
        except (TypeError, ValueError):
            continue
        pos = hmap.get(k)
        if pos is None:  # 找最近有對映的 heard 索引
            near = [kk for kk in hmap if abs(kk - k) <= 1]
            pos = hmap[min(near, key=lambda kk: abs(kk - k))] if near else None
        pauses.append(dict(after_pos=pos, sec=sec))
    expect_pause = [i for i, ch in enumerate(text) if ch in PAUSE_PUNCT and i + 1 < len(text) and i > 0]
    for i in expect_pause:
        prev_cjk = max((r[0] for r in ref if r[0] < i), default=None)
        if prev_cjk is None:
            continue
        if not any(p["after_pos"] is not None and abs(p["after_pos"] - prev_cjk) <= 1 and p["sec"] >= 0.15 for p in pauses):
            issues.append(dict(kind="runon", ref_pos=prev_cjk, ref_char=text[prev_cjk], ref_py="", heard_py=""))
    for p in pauses:
        if p["after_pos"] is None or p["sec"] < 0.3:
            continue
        window = text[p["after_pos"]:p["after_pos"] + 3]
        if not any(ch in ANY_PUNCT for ch in window):
            issues.append(dict(kind="misplaced", ref_pos=p["after_pos"], ref_char=text[p["after_pos"]], ref_py="", heard_py=f"{p['sec']:.2f}s"))
    # 長段無停頓(以參考文字算字數,停頓點 = 聽到的停頓 ∪ 標點)
    stops = sorted({p["after_pos"] for p in pauses if p["after_pos"] is not None and p["sec"] >= 0.15} | {i for i, ch in enumerate(text) if ch in ANY_PUNCT})
    last, spans = -1, []
    for s in stops + [len(text)]:
        n = sum(1 for r in ref if last < r[0] <= s)
        if n > LONG_SPAN:
            spans.append((last + 1, s, n))
        last = s
    for a0, b0, n in spans:
        issues.append(dict(kind="long_span", ref_pos=a0, ref_char=text[a0:a0 + 6], ref_py="", heard_py=f"{n}字"))
    for k in blind.get("unclear") or []:
        try:
            pos = hmap.get(int(k))
        except (TypeError, ValueError):
            continue
        if pos is not None:
            issues.append(dict(kind="unclear", ref_pos=pos, ref_char=text[pos], ref_py="", heard_py=""))
    flags = sorted({i["kind"] for i in issues})
    return dict(flags=flags, issues=issues, transcript=str(blind.get("transcript") or ""))


def blind_call(wav, args, key, limiter, cache):
    ck = f"{g.sha1_of(wav)}|{args.model}"
    if ck in cache and not args.redo:
        return cache[ck], True
    def once():
        limiter.wait()
        return g._generate(args.model, wav, BLIND_PROMPT, key)
    raw, usage = g.with_retry(once)
    d = g.parse_json_text(raw)
    cache[ck] = dict(blind=d, usage=usage)
    return cache[ck], False


def truth_hit(it, cmp, truth_row):
    issue = str(truth_row.get("issue") or "")
    kinds = set(cmp["flags"])
    if "讀音" in issue or "多唸" in issue or "吞音" in issue or "漏唸" in issue or "數字" in issue:
        pos = truth_row.get("pos")
        strict = any(i["kind"] in ("tone", "syl", "unclear") and pos is not None and i["ref_pos"] is not None and abs(i["ref_pos"] - int(pos)) <= 1 for i in cmp["issues"]) if pos is not None else False
        loose = bool(kinds & {"tone", "syl", "unclear"})
    elif "斷句" in issue or "停頓" in issue:
        strict = loose = bool(kinds & {"runon", "misplaced", "long_span"})
    elif "英文" in issue:
        strict = loose = bool(kinds & {"syl", "unclear"})
    else:
        strict = loose = bool(kinds)
    return strict, loose


def run_truth(args):
    key = None if args.rescore else g.api_key()
    limiter = g.RateLimiter(args.rpm)
    cache_p = paths.ROOT / "tmp" / "ear_e3_blind_cache.json"
    cache = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.exists() else {}
    rows_raw = json.loads(Path(paths.find(args.truth)).read_text(encoding="utf-8"))
    rows_raw = rows_raw.get("items", rows_raw) if isinstance(rows_raw, dict) else rows_raw
    out = []
    for n, tr in enumerate(rows_raw):
        wav = tr.get("audio") or tr.get("wav")
        wav = paths.find(wav) if wav else None
        if not wav or not Path(wav).exists():
            continue
        try:
            if args.rescore:
                ck = f"{g.sha1_of(wav)}|{args.model}"
                if ck not in cache:
                    continue
                rec, cached = cache[ck], True
            else:
                rec, cached = blind_call(wav, args, key, limiter, cache)
        except (g.ApiError, ValueError) as e:
            print(f"[{tr.get('id')}] 錯誤 {str(e)[:120]}")
            out.append(dict(id=tr.get("id"), kind=tr.get("kind"), issue=tr.get("issue"), error=str(e)[:200]))
            continue
        if not cached:
            cache_p.parent.mkdir(parents=True, exist_ok=True)
            cache_p.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        cmp = compare(tr.get("text") or "", rec["blind"])
        strict, loose = truth_hit(tr, cmp, tr) if tr.get("kind") == "bad" else (None, None)
        out.append(dict(id=tr.get("id"), kind=tr.get("kind"), issue=tr.get("issue"), char=tr.get("char"), pos=tr.get("pos"),
                        flags=cmp["flags"], hit=strict, hit_loose=loose, issues=cmp["issues"], transcript=cmp["transcript"]))
        mark = ("命中" if strict else "寬鬆" if loose else "漏抓") if tr.get("kind") == "bad" else ("誤報" if cmp["flags"] else "OK")
        print(f"[{tr.get('id')}] {mark} {','.join(cmp['flags'])}  {tr.get('issue') or ''}", flush=True)
    stats = score(out)
    if args.out:
        g.save_json(paths.find(args.out), dict(stats=stats, model=args.model, items=out))
    print_stats(stats)


def score(out):
    bad = [r for r in out if r.get("kind") == "bad" and "flags" in r]
    good = [r for r in out if r.get("kind") == "good" and "flags" in r]
    rate = lambda xs: (sum(1 for x in xs if x) / len(xs)) if xs else None  # noqa: E731
    bycat = {}
    for r in bad:
        c = (r.get("issue") or "").split(":")[0]
        d = bycat.setdefault(c, dict(n=0, hit=0, loose=0))
        d["n"] += 1
        d["hit"] += bool(r["hit"])
        d["loose"] += bool(r["hit_loose"])
    fa_kind = {}
    for k in ("tone", "syl", "runon", "misplaced", "long_span", "unclear"):
        fa_kind[k] = rate([k in r["flags"] for r in good])
    return dict(n_bad=len(bad), n_good=len(good), recall=rate([r["hit"] for r in bad]), recall_loose=rate([r["hit_loose"] for r in bad]),
                fa_any=rate([bool(r["flags"]) for r in good]), fa_by_kind=fa_kind, by_category=bycat)


def print_stats(st):
    pct = lambda v: "n/a" if v is None else f"{v * 100:.0f}%"  # noqa: E731
    print(f"\n壞例 {st['n_bad']}:召回 {pct(st['recall'])}(寬鬆 {pct(st['recall_loose'])});好例 {st['n_good']}:任一旗標誤報 {pct(st['fa_any'])}")
    print("好例各旗標誤報:", {k: pct(v) for k, v in st["fa_by_kind"].items()})
    for c, d in sorted(st["by_category"].items(), key=lambda kv: -kv[1]["n"]):
        print(f"  {c}: n={d['n']} 命中 {d['hit']} 寬鬆 {d['loose']}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth")
    ap.add_argument("--out")
    ap.add_argument("--wav")
    ap.add_argument("--text", default="")
    ap.add_argument("--model", default="gemini-3.5-flash-lite")
    ap.add_argument("--rpm", type=float, default=10)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--rescore", action="store_true", help="只用快取重算評分,不打 API")
    args = ap.parse_args(argv)
    if args.truth:
        run_truth(args)
        return 0
    key = g.api_key()
    limiter = g.RateLimiter(args.rpm)
    rec, _ = blind_call(paths.find(args.wav), args, key, limiter, {})
    cmp = compare(args.text, rec["blind"])
    print(json.dumps(dict(transcript=cmp["transcript"], flags=cmp["flags"], issues=cmp["issues"], blind=rec["blind"]), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
