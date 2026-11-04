r"""英文詞品管(2026-10-30;純函式,只讀 cosy_terms.json;pypinyin 有就用(tts_env_chattts),沒有退回逐字比對):
- direct_open(texts):配音前,送引擎仍唸英文、在 cosy_terms `_direct` 但不在 `_verified` 的詞 -> {詞: [行號]};
  >= OPEN_MIN 行 = 配音稿「未決」(建議音譯),1 行 = 警告(tts_script.py)。
- frag(text, hyp, a, b):原文 [a, b) 在辨識文字裡的對應片段(拼音鍵 difflib,取前後錨點之間);對不準回 None。
- sounds_like(frag, cands):片段與候選寫法(原詞拼寫、_asr_alias、cosy_terms 寫法)的音近分數(拼音鍵字串相似度)。
- loose_misses(text, hyp):asr_loose zh_only 漏洞補強 —— 英文段辨識不出時,該位置的片段至少要音近原詞/別名(>= SOUND_MIN),
  否則記 term_misread(kind="loose")。
- inconsistent(items):跨句一致性 —— 仍直送英文的詞在同片 >= 2 句時,各句主辨識在該詞位置的寫法與多數寫法差異大
  (拼音鍵相似度 < CONSIST_MIN)且不接近原詞/別名(< ORIG_MIN)-> term_inconsistent;只有 1 句或無多數 -> 只列優先聽(term_listen)。
離線報告(只讀 qc.json,不改檔):python pipeline/run.py tts_term_qc <tag>... [--all] [--stray]
"""
import argparse
import difflib
import json
import re
import sys
from collections import defaultdict

import terms_check as TCK
import tts_cosy_text as CT

OPEN_MIN = 2          # 未驗證的直送英文詞同片出現幾句以上算未決(建議音譯)
SOUND_MIN = 0.5       # 片段與原詞/別名的音近分數門檻(< 這個值 = 唸錯/聽不出)
CONSIST_MIN = 0.6     # 跨句一致性:片段與多數寫法的拼音鍵相似度門檻
ORIG_MIN = 0.75       # 跨句一致性的豁免:片段與原詞/別名的音近分數達此值 = 就是原詞,少數寫法也不算(同 asr_loose 的 found_min);
                      # 用 SOUND_MIN 當豁免會讓 term_inconsistent 退化成 term_misread 的子集(那些句子 loose_misses 已抓)
FRAG_EXTRA = 4        # 片段鍵數上限 = 原詞鍵數 + 這個值;超過視為錨點對不準(None,不判)
_PY = []


def _pinyin(c):
    if not _PY:
        try:
            from pypinyin import Style, lazy_pinyin
            _PY.append(lambda ch: lazy_pinyin(ch, style=Style.NORMAL)[0])
        except ImportError:
            _PY.append(None)
    return _PY[0](c) if _PY[0] else c


def _key(c):
    """單字鍵:英數小寫;中文 = 不帶調拼音並模糊 zh/z、ch/c、sh/s、ng/n(同 tts_asr._key);沒有 pypinyin 用字本身。"""
    if c.isascii():
        return c.lower()
    s = _pinyin(c)
    return re.sub(r"^([zcs])h", r"\1", s).replace("ng", "n") if s.isascii() else s


def _keys(s):
    """[(原字位置, 鍵)];只留英數與中日韓字(空白、標點、引號略過)。"""
    return [(i, _key(c)) for i, c in enumerate(s) if c.isalnum()]


def phon(s):
    return "".join(k for _, k in _keys(s or ""))


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def frag(text, hyp, a, b):
    """原文 text[a:b] 在辨識文字 hyp 的對應片段:用拼音鍵對齊,取 [a, b) 之前最後一個對到的字之後、之後第一個對到的字之前。
    片段鍵數超過原詞鍵數 + FRAG_EXTRA 回 None(錨點對不準,不判);整段沒唸回 ""。"""
    tk, hk = _keys(text), _keys(hyp or "")
    if not tk or not hk:
        return None
    sm = difflib.SequenceMatcher(None, [k for _, k in tk], [k for _, k in hk], autojunk=False)
    left, right = 0, len(hk)
    for i, j, n in sm.get_matching_blocks():
        for d in range(n):
            if tk[i + d][0] < a:
                left = max(left, j + d + 1)
            elif tk[i + d][0] >= b:
                right = min(right, j + d)
    if right <= left:
        return ""
    if right - left > sum(1 for p, _ in tk if a <= p < b) + FRAG_EXTRA:
        return None
    return hyp[hk[left][0]: hk[right - 1][0] + 1]


# 英文字母的中文唸法(拼音鍵;全大寫縮寫逐字母唸時辨識常寫成音譯:IGN -> 艾吉恩)
LETTER = dict(A="ei", B="bi", C="xi", D="di", E="yi", F="aifu", G="ji", H="aiqi", I="ai", J="jie", K="kai", L="aier",
              M="aimu", N="en", O="ou", P="pi", Q="kiu", R="aer", S="aisi", T="ti", U="you", V="wei", W="dabuliu",
              X="aikesi", Y="wai", Z="zei")


def cands(term, text=None):
    """term 的可接受寫法:原詞拼寫 + cosy_terms 寫法 + _asr_alias(+ 全大寫縮寫的逐字母唸法,tuple);
    text 給定時也併入與 term 重疊的登錄詞(長詞的別名)。"""
    out = [term]
    if re.fullmatch(r"[A-Z]{2,5}", term):
        out.append(tuple(LETTER[c] for c in term))   # tuple = 逐音節比(整串比會讓「白先生」靠 ai/i/en 字母湊到高分)
    keys = {term}
    if text is not None:
        for w in set(CT.TERMS) | set(CT.ASR_ALIAS):
            if w != term and (w in term or term in w) and CT._word_re(w).search(text):
                keys.add(w)
    for w in keys:
        if w in CT.TERMS:
            out.append(CT.TERMS[w])
        out += CT.ASR_ALIAS.get(w, [])
    return out


def sounds_like(f, cs):
    """片段 f 與候選寫法 cs 的最高音近分數(拼音鍵字串相似度,0–1)。"""
    k = phon(f)
    syl = [x for _, x in _keys(f or "")]
    return max((ratio(syl, list(c)) if isinstance(c, tuple) else ratio(k, phon(c)) for c in cs if c), default=0.0)


_still_en = TCK.still_en   # 判斷收在 terms_check(單一來源)


# ------------------------------------------------------------ 配音前:未驗證的直送英文詞(項目 1)
def direct_open(texts):
    """texts = 送配音文字 list(第 i 個 = 第 i+1 行)。回傳 {詞: [行號]}:在 _direct、不在 _verified、2 字元以上
    (單一字母唸字母本身,不列)。>= OPEN_MIN 行 = 未決,1 行 = 警告。判斷在 terms_check.direct_open。"""
    return TCK.direct_open(texts)


# ------------------------------------------------------------ asr_loose zh_only 補強(項目 3)
_RUN = re.compile(r"[A-Za-z][A-Za-z.\s]*[A-Za-z]|[A-Za-z]")


def _lkey(t):
    return re.sub(r"[\s./\\_-]", "", t.lower())


def alias_back(hyp, text):
    """辨識結果裡 _asr_alias 的音譯/別寫換回原文英文詞(只換這句文字有的詞;同 tts_cosy3.asr_loose)。"""
    for term, alts in CT.ASR_ALIAS.items():
        if term in text:
            for alt in sorted(alts, key=len, reverse=True):
                hyp = hyp.replace(alt, term)
    return hyp


def loose_misses(text, hyp, found_min=0.75, sound_min=SOUND_MIN):
    """英文段在辨識裡找不到(同 asr_loose:別名換回後英數段相似度 < found_min)時,取該位置片段,與原詞/別名/寫法都不音近
    (< sound_min)-> [dict(term, hit, src="asr", kind="loose", score)]。單一字母、片段對不準(None)不判。"""
    if not hyp:
        return []
    ref_t = re.sub(r"(?<=[A-Za-z])\s*[點点]\s*(?=[A-Za-z])", ".", text)
    runs = re.findall(r"[a-z0-9]+", _lkey(alias_back(hyp, text)))
    out = []
    for mt in _RUN.finditer(ref_t):
        term, k = mt.group(0).strip(), _lkey(mt.group(0))
        if len(k) < 2 or any(ratio(k, x) >= found_min for x in runs):
            continue
        f = frag(ref_t, hyp, mt.start(), mt.end())
        if f is None:
            continue
        s = sounds_like(f, cands(term, ref_t))
        if s < sound_min:
            out.append(dict(term=term, hit=f, src="asr", kind="loose", score=round(s, 2)))
    return out


# ------------------------------------------------------------ 跨句一致性(項目 2)
def en_terms(text):
    """送引擎仍是英文的登錄詞位置 [(詞, 起, 迄)]:_direct 的詞 + cosy_terms 寫法含 3 個以上連續英文字母的詞(IGN、Row blocks);
    長詞優先、2 字元以上。"""
    ws = sorted({w for w in CT.DIRECT if len(w) >= 2 and _still_en(w)} |
                {w for w, v in CT.TERMS.items() if re.search(r"[A-Za-z]{3}", v)}, key=len, reverse=True)
    out, t = [], text
    for w in ws:
        p = CT._word_re(w)
        for m in p.finditer(t):
            out.append((w, m.start(), m.end()))
        t = p.sub(lambda m: "\x00" * len(m.group(0)), t)
    return sorted(out, key=lambda x: x[1])


def _frags(items):
    by = defaultdict(list)
    for uid, text, hyp in items:
        if not hyp:
            continue
        for w, a, b in en_terms(text):
            f = frag(text, hyp, a, b)
            if f is not None:
                by[w].append((uid, f))
    return by


def inconsistent(items, min_sim=CONSIST_MIN, sound_min=SOUND_MIN, orig_min=ORIG_MIN):
    """items = [(單位, 量測文字, 主辨識)]。同一詞 >= 2 句:多數寫法 = 與最多片段相似(>= min_sim)的那個,支持數 >= 2 且過半;
    與多數差異大(< min_sim)且不接近原詞/別名(< orig_min)的句子 -> bad。只有 1 句或無多數:不音近原詞(< sound_min)的列 listen。
    回傳 (bad {單位: [dict(term, got, major)]}, listen {單位: [dict(term, got)]}, majors {詞: 多數寫法})。"""
    bad, listen, majors = defaultdict(list), defaultdict(list), {}
    for w, L in _frags(items).items():
        cs = cands(w)
        ks = [phon(f) for _, f in L]
        n = len(L)
        sup = [sum(ratio(ks[i], ks[j]) >= min_sim for j in range(n)) for i in range(n)]
        c = max(range(n), key=lambda i: (sup[i], -i))
        if len({u for u, _ in L}) >= 2 and sup[c] >= 2 and sup[c] * 2 > n:
            majors[w] = L[c][1]
            for (u, f), k in zip(L, ks):
                if ratio(k, ks[c]) < min_sim and sounds_like(f, cs) < orig_min:
                    bad[u].append(dict(term=w, got=f, major=L[c][1]))
        else:
            for u, f in L:
                if sounds_like(f, cs) < sound_min:
                    listen[u].append(dict(term=w, got=f))
    return dict(bad), dict(listen), majors


def off_major(text, hyp, majors, min_sim=CONSIST_MIN, orig_min=ORIG_MIN):
    """重錄後檢查:這句仍直送英文的詞,片段與 majors 的多數寫法差異大且不接近原詞/別名 -> [dict(term, got, major)]。"""
    out = []
    for w, a, b in en_terms(text):
        if w not in majors:
            continue
        f = frag(text, hyp, a, b)
        if f is not None and ratio(phon(f), phon(majors[w])) < min_sim and sounds_like(f, cands(w)) < orig_min:
            out.append(dict(term=w, got=f, major=majors[w]))
    return out


# ------------------------------------------------------------ 離線報告(只讀)
def _records(tag):
    import paths as P
    d = P.tts_dir(tag, "cosy3")
    out = []
    for qf in sorted(list(d.glob("*.qc.json")) + list((d / "sub").glob("*.qc.json"))):
        try:
            rec = json.loads(qf.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if rec.get("engine") == "cosy3":
            out.append((str(rec.get("idx") or qf.name[:-len(".qc.json")]), rec))
    return out


def report(tag, stray_fail):
    recs = _records(tag)
    texts = [(u, r.get("measure_text") or CT.unsay(r.get("text") or ""), r.get("asr")) for u, r in recs]
    loose = [(u, x) for u, t, h in texts for x in loose_misses(t, h)]
    bad, listen, majors = inconsistent(texts)
    strays = [(u, x) for u, r in recs for x in (r.get("stray_fix") or [])
              if x.get("kind") == "wb" and x.get("before", 0) >= stray_fail - 1e-9]
    print(f"== {tag}:{len(recs)} 句")
    print(f"[loose] term_misread(asr_loose 補強)命中 {len({u for u, _ in loose})} 句")
    for u, x in loose:
        print(f"  {u} {x['term']} -> 「{x['hit']}」 音近 {x['score']}")
    print(f"[consist] term_inconsistent 命中 {len(bad)} 句;列優先聽 {len(listen)} 句;有多數寫法的詞 {len(majors)}")
    for u, xs in sorted(bad.items()):
        print("  " + u + " " + ";".join(f"{x['term']} 「{x['got']}」 多數「{x['major']}」" for x in xs))
    for u, xs in sorted(listen.items()):
        print("  (聽)" + u + " " + ";".join(f"{x['term']} 「{x['got']}」" for x in xs))
    has_kind = any(x.get("kind") for _, r in recs for x in r.get("stray_fix") or [])
    print(f"[stray] 詞界停頓 >= {stray_fail:.2f}s(stray_fix before)命中 {len({u for u, _ in strays})} 句"
          + ("" if has_kind else "(舊紀錄沒有 kind,判不出,不代表沒有)"))
    for u, x in strays:
        print(f"  {u} {x['at']} {x['before']:.3f}s")
    return dict(loose=len({u for u, _ in loose}), consist=len(bad), listen=len(listen), stray=len({u for u, _ in strays}))


def stray_stats():
    """全部 build/*/tts_cosy3 的詞界多餘停頓(stray_fix kind=wb 的 before)分布,與句中逗號停頓(pauses sil>0)對照。"""
    import paths as P
    wb, comma, n, hit = [], [], 0, 0
    for d in sorted(P.BUILD.glob("*/tts_cosy3")):
        recs = _records(d.parent.name)
        if not any(x.get("kind") for _, r in recs for x in r.get("stray_fix") or []):
            continue   # 2026-10-29 前的紀錄沒有 kind,分不出詞界/詞中,不計入分母
        n += len(recs)
        for u, r in recs:
            vals = [x["before"] for x in r.get("stray_fix") or [] if x.get("kind") == "wb"]
            wb += vals
            hit += any(v >= 0.20 - 1e-9 for v in vals)
            comma += [p["sil"] for p in r.get("pauses") or [] if p.get("sil", 0) > 0]
    q = lambda v, p: sorted(v)[min(len(v) - 1, int(p * len(v)))] if v else 0  # noqa: E731
    print(f"[stray-stats] 有 kind 紀錄的片共 {n} 句({hit} 句有 >= 0.20s);詞界多餘停頓 {len(wb)} 筆:p50 {q(wb, .5):.3f} p75 {q(wb, .75):.3f} p90 {q(wb, .9):.3f} 最大 {max(wb or [0]):.3f}")
    for t in (0.12, 0.15, 0.18, 0.20, 0.22, 0.25, 0.30):
        print(f"  >= {t:.2f}s:{sum(v >= t - 1e-9 for v in wb)} 筆")
    print(f"  對照 句中逗號停頓(最終音檔){len(comma)} 筆:p10 {q(comma, .1):.3f} p50 {q(comma, .5):.3f} p90 {q(comma, .9):.3f}")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import tts_pause as TP
    ap = argparse.ArgumentParser(description="英文詞品管與詞界停頓的離線報告(只讀 qc.json,不改檔)")
    ap.add_argument("tags", nargs="*")
    ap.add_argument("--all", action="store_true", help="所有 build/*/tts_cosy3")
    ap.add_argument("--stray", action="store_true", help="印詞界多餘停頓分布(門檻依據)")
    a = ap.parse_args(argv)
    if a.stray:
        stray_stats()
    tags = a.tags
    if a.all:
        import paths as P
        tags = [d.parent.name for d in sorted(P.BUILD.glob("*/tts_cosy3"))]
    for t in tags:
        report(t, TP.STRAY_WB_FAIL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
