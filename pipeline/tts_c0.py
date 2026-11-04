#!/usr/bin/env python3
r"""C0 風險句試配(channel/_archive/plans/PLAN_C0試配與讀音記憶_2026-10-31.md §3.4;全片配音前先試會唸錯的句子)。

tts_env_chattts\Scripts\python.exe -X utf8 pipeline\tts_c0.py <tag> [--seeds 2024,7,1234] [--dry-run] [--g2p]
風險位置:本片多音字位置中,記憶未命中且屬於 ①cosy_pron 或 pron_rules 標注 ②g2p 不一致 ③rule unverified;另加未驗證的直送英文詞。
挑句:完整配音單位(tts_split 子句,與正式配音同一段文字)貪婪集合覆蓋,同 1+1 語境 + 同標注算一個位置;上限 MAX_SENT,
      超過時依 pron_backlog 命中數優先,其餘列入報告 untested。
合成:沿用 tts_pron_verify 的 synth(本機、gpu_lock 排隊、--max-retry 0)與 judge_record,每句多 seed;工作檔只放 tmp\c0\<tag>\<批次>\,不寫 build\ 快取。
判定後寫記憶表(英文詞只進報告),出 projects\<tag>\c0_report.json 與 .md。記憶已判 bad + rewrite 的語境不重測,直接算唸錯。
結束碼:0 = 無唸錯(沒有風險位置時不載模型);3 = 有唸錯,逐條印;1 = 合成不完整。
--dry-run 只列位置、句數、預估分鐘,不載任何模型:g2p 不一致沿用上次實跑存的 tmp\c0\<tag>\g2p.json,沒有就不列(--g2p 才現算,CPU 載 g2pW)。
script_sha = 全片送配音文字(含標注)的 sha256;稿或讀音表改到文字,tts_dispatch 的 C0 閘門就要求重跑。
"""
import argparse
import difflib
import hashlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paths as P  # noqa: E402
import pron_backlog as PB  # noqa: E402
import pron_memory as PM  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import tts_pron_verify as V  # noqa: E402
import tts_script as SC  # noqa: E402
import tts_split as TS  # noqa: E402

MAX_SENT = 12
DEFAULT_SEEDS = "2024,7,1234"
EXIT_INCOMPLETE, EXIT_WRONG = 1, 3
OUTCOME = {"right": "唸對", "wrong": "唸錯", "undetermined": "無法判定"}


# ------------------------------------------------------------ 稿件
def report_path(tag):
    return P.PROJECTS / tag / "c0_report.json"


def script_sha(tag):
    # 刻意不用 freeze.narration_sha:這裡 hash 的是「套讀音標注後(pron_text)」的送引擎文字,讀音表改了也要重跑 C0;
    # narration_sha 只管稿面文字(凍結用),兩者不是同一個東西。
    return hashlib.sha256("\n".join(CT.pron_text(say)[0] for _, say in SC.script_lines(tag)).encode("utf-8")).hexdigest()


def units_of(says):
    """配音單位(子句,與 build 送合成的文字相同)-> [dict(line, say, mtext, t)];相同文字只留一份。"""
    out, seen = [], set()
    for i, say in enumerate(says, 1):
        for c, _gap in TS.split_clauses(say):
            if c not in seen:
                seen.add(c)
                out.append(dict(line=i, say=c, mtext=CT.unsay(c), t=CT.pron_source(c)))
    return out


def pos_map(a, b):
    """a 的字位置 -> b 的同一字位置(只對到完全相同的區段)。"""
    out = {}
    for i, j, n in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        out.update((i + k, j + k) for k in range(n))
    return out


# ------------------------------------------------------------ 風險位置
def annotated(t):
    """t 上會被標注的位置 {位置: dict(pos, ch, value, why)}(詞表逐字 + 規則事件)。"""
    spans, _ = CT._word_spans(t)
    found = {}
    for s, e, v in spans:
        us = PM.units(v)
        if len(us) == e - s:
            for k, x in enumerate(us):
                if x != t[s + k]:
                    found[s + k] = dict(pos=s + k, ch=t[s + k], value=x, why=["詞表"])
    for p, ch, py, _key, _src, unv in CT._live_events(t, spans):
        found[p] = dict(pos=p, ch=ch, value=py, why=["規則未驗證" if unv else "規則"])
    return found


def add_g2p(found, u, dis):
    """g2p 不一致(位置在 mtext)併進 found;沒有標注的位置 value=None,應讀取規則表讀音。"""
    m2t = pos_map(u["mtext"], u["t"])
    for d in dis:
        p = m2t.get(d["pos"])
        if p is None:
            continue
        if p in found:
            found[p]["why"].append("g2p")
        else:
            found[p] = dict(pos=p, ch=d["ch"], value=None, want=d["rule"], why=["g2p"])


def backlog_table():
    return [(r["字"], r["語境詞"], int(r["命中次數"] or 0)) for r in PB.load()]


def risk_of(u, dis, backlog):
    """一個單位 -> (風險位置 list, 記憶已判要改寫的位置 list, 記憶命中數)。"""
    found = annotated(u["t"])
    add_g2p(found, u, dis)
    mem = dict(PM.scan(u["t"]))
    risk, known, n_mem = [], [], 0
    for p in sorted(found):
        x = found[p]
        e = mem.get(p)
        if e:
            n_mem += 1
            if PM.blocking(e):
                known.append(dict(x, line=u["line"], say=u["say"], ctx=PM.ctx_label(e), entry=e))
            continue
        c = PM.context(u["t"], p)
        x["ctx"] = f"{c['l1']}{x['ch']}{c['r1']}"
        x["elem"] = (x["ch"], c["l1"], c["r1"], x["value"] or "")
        x["weight"] = sum(n for ch, w, n in backlog if ch == x["ch"] and w in u["t"])
        risk.append(x)
    return risk, known, n_mem


def english_of(says, units):
    """未驗證的直送英文詞 {詞: 出現在哪些單位序}。"""
    import terms_check as TC
    words = TC.direct_open(says)
    return {w: [i for i, u in enumerate(units) if CT._word_re(w).search(u["mtext"])] for w in words}


# ------------------------------------------------------------ 挑句
def cover(cands, weight=None, limit=None):
    """貪婪集合覆蓋。cands = {單位序: 元素集合};weight = {元素: 權重}(有給就先比權重總和)。-> 選到的單位序 list。"""
    left = set().union(*cands.values()) if cands else set()
    chosen = []
    while left and (limit is None or len(chosen) < limit):
        def score(i):
            got = cands[i] & left
            return (sum(weight.get(x, 0) for x in got) if weight else 0), len(got), -i
        best = max((i for i in cands if i not in chosen), key=score)
        if not cands[best] & left:
            break
        chosen.append(best)
        left -= cands[best]
    return chosen


def select(cands, weight, limit=MAX_SENT):
    """全覆蓋不超過 limit 就用;超過時依 backlog 命中數優先,取滿 limit。"""
    full = cover(cands)
    return full if len(full) <= limit else cover(cands, weight, limit)


# ------------------------------------------------------------ 計畫
def g2p_file(tag):
    return P.TMP / "c0" / tag / "g2p.json"


def g2p_disagree(tag, units, compute=True):
    """每單位的 g2p 不一致 list(位置在 mtext);-> (list, 來源說明)。結果依文字存檔,dry-run 不現算就只讀舊檔。"""
    import tts_g2p as G
    texts = [u["mtext"] for u in units]
    sha = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()
    f = g2p_file(tag)
    if not compute:
        saved = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        if saved.get("sha") != sha:
            return [[] for _ in units], "g2p 未算(dry-run 不載模型;加 --g2p 現算)"
        return [G.compare(t, [tuple(x) for x in p]) for t, p in zip(texts, saved["preds"])], "g2p 用上次實跑的結果"
    preds = G.predict_many(texts)
    if preds is None:
        return [[] for _ in units], "g2p 不可用"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(dict(sha=sha, preds=preds), ensure_ascii=False), encoding="utf-8")
    return [G.compare(t, p) for t, p in zip(texts, preds)], "g2p 已現算"


def build_plan(tag, compute_g2p=True, limit=MAX_SENT):
    """-> dict(units, items, untested, known, english, note, n_mem)。"""
    says = [s for _, s in SC.script_lines(tag)]
    units = units_of(says)
    dis, note = g2p_disagree(tag, units, compute_g2p)
    backlog = backlog_table()
    risk, known, n_mem = {}, [], 0
    for i, (u, d) in enumerate(zip(units, dis)):
        r, k, n = risk_of(u, d, backlog)
        n_mem += n
        known += k
        if r:
            risk[i] = r
    english = english_of(says, units)
    cands, weight = {}, {}
    for i, rows in risk.items():
        cands[i] = {x["elem"] for x in rows}
        for x in rows:
            weight[x["elem"]] = max(weight.get(x["elem"], 0), x["weight"])
    for w, idxs in english.items():
        for i in idxs:
            cands.setdefault(i, set()).add(("en", w))
    chosen = sorted(select(cands, weight, limit))
    items = []
    for i in chosen:
        u = units[i]
        items.append(dict(u, id=len(items), positions=[dict(x) for x in risk.get(i, [])],
                          words=[w for w, idxs in english.items() if i in idxs]))
    done = set().union(*(cands[i] for i in chosen)) if chosen else set()
    untested, seen = [], set()
    for i, rows in risk.items():
        for x in rows:
            if x["elem"] not in done and x["elem"] not in seen:
                seen.add(x["elem"])
                untested.append(dict(ch=x["ch"], ctx=x["ctx"], value=x["value"], why=x["why"], weight=x["weight"], line=units[i]["line"], say=units[i]["say"]))
    untested.sort(key=lambda x: -x["weight"])
    un_en = [w for w in english if ("en", w) not in done]
    return dict(units=units, items=items, untested=untested, untested_en=un_en, known=known, english=list(english), note=note, n_mem=n_mem)


def work_dir(tag, items):
    """工作資料夾依這批句子與送引擎文字分開,稿或標注變了不會讀到舊 qc 紀錄。"""
    sig = "\n".join(f"{it['id']}|{it['say']}|{CT.pron_text(it['say'])[0]}" for it in items)
    return P.TMP / "c0" / tag / hashlib.sha1(sig.encode("utf-8")).hexdigest()[:12]


# ------------------------------------------------------------ 判定
def _default_reading(value):
    import tts_asr as TA
    return TA.token_reading(value)


def judge_items(items, seeds, work, norm=None, ph=None, reading=None, simp=None):
    """每句每 seed 判定;結果掛在 item["positions"][k]["results"] 與 item["en"]。-> 缺紀錄的筆數。"""
    ph, reading, simp = ph or V.PyPhon(), reading or _default_reading, simp or V.simp
    missing = 0
    for it in items:
        t2m = pos_map(it["t"], it["mtext"])
        by, targets = {}, {}
        for x in it["positions"]:
            x["results"] = []
            mp = t2m.get(x["pos"])
            if mp is not None:
                by[mp] = x
                targets[mp] = (simp(x["ch"]), x.get("want") or reading(x["value"]), x["ch"] in CT.RULE_ALWAYS)
        it["en"] = {w: Counter() for w in it["words"]}
        for s in seeds:
            rec = V.read_rec(work, s, it)
            if rec is None:
                missing += 1
                continue
            j = V.judge_record(rec, targets, norm=norm, ph=ph) if targets else dict(positions=[])
            got = {p["pos"]: p for p in j["positions"]}
            for x in it["positions"]:
                mp = t2m.get(x["pos"])
                x["results"].append(got.get(mp) or dict(pos=mp, ch=x["ch"], want=x.get("want"), main=None, second=None,
                                                        hyp_main=None, hyp_second=None, result="undetermined"))
            bad = {str(m.get("term", "")).lower() for m in rec.get("term_misread") or []}
            for w in it["words"]:
                it["en"][w]["wrong" if w.lower() in bad else "right"] += 1
                if w.lower() in bad:
                    it["en"][w]["heard:" + (rec.get("asr") or "")[:60]] += 1
    return missing


def tally(x):
    return Counter(PM.seed_outcome(p) for p in x["results"])


def suggestion(x, c, wrongs):
    if c["wrong"]:
        kinds = {w["kind"] for w in wrongs}
        if x["ch"] == "著":
            return "著 試 pron_memory add --fix-type zhe,或改寫這句"
        return "標注沒效(變成無關的音):換詞或改寫這句" if "token_unstable" in kinds else "唸成另一讀音:改標注或改寫這句"
    return "" if c["right"] >= PM.TEST_MIN_RIGHT else "辨識看不出,留優先聽"


# ------------------------------------------------------------ 報告
def build_report(tag, plan, seeds, ph=None, sha=None, missing=0, day=None):
    rows = []
    for it in plan["items"]:
        for x in it["positions"]:
            c, wrongs = tally(x), []
            for p in x["results"]:
                w = PM.wrong_entry(p, x["value"], ph) if PM.seed_outcome(p) == "wrong" else None
                if w and w not in wrongs:
                    wrongs.append(w)
            result = "wrong" if c["wrong"] else "right" if c["right"] >= PM.TEST_MIN_RIGHT else "undetermined"
            rows.append(dict(ch=x["ch"], ctx=x["ctx"], value=x["value"], why=x["why"], line=it["line"], say=it["say"], result=result,
                             right=c["right"], wrong=c["wrong"], undetermined=c["undetermined"], heard=wrongs, suggest=suggestion(x, c, wrongs)))
    en = []
    for it in plan["items"]:
        for w, c in it.get("en", {}).items():
            en.append(dict(word=w, line=it["line"], say=it["say"], right=c["right"], wrong=c["wrong"],
                           heard=[k[6:] for k in c if k.startswith("heard:")], result="wrong" if c["wrong"] else "right"))
    known = [dict(ch=x["ch"], ctx=x["ctx"], value=x["value"], line=x["line"], say=x["say"], wrong_as=x["entry"].get("wrong_as"),
                  last=(x["entry"].get("fix") or {}).get("value")) for x in plan["known"]]
    c = Counter(r["result"] for r in rows)
    n_wrong = c["wrong"] + sum(r["result"] == "wrong" for r in en) + len(known)
    return dict(tag=tag, date=day or date.today().isoformat(), script_sha=sha, seeds=seeds, max_sent=MAX_SENT, sentences=len(plan["items"]),
                g2p=plan["note"], memory_hits=plan["n_mem"], positions=rows, english=en, known_bad=known, untested=plan["untested"],
                untested_en=plan["untested_en"], missing=missing, right=c["right"], undetermined=c["undetermined"], wrong=n_wrong)


def write_report(rep):
    jf = report_path(rep["tag"])
    jf.parent.mkdir(parents=True, exist_ok=True)
    jf.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    L = [f"# C0 試配 {rep['tag']} {rep['date']}", "",
         f"{rep['sentences']} 句 × {len(rep['seeds'])} seed;位置:唸對 {rep['right']}、唸錯 {rep['wrong']}、無法判定 {rep['undetermined']};"
         f"未試 {len(rep['untested'])} 位置、{len(rep['untested_en'])} 英文詞;記憶命中 {rep['memory_hits']};{rep['g2p']}", "",
         "皆為未聽審的文字層回查;辨識看不出聲調,無法判定不算通過。", "",
         "| 行 | 字 | 語境 | 標注 | 風險 | 判定 | 對/錯/無 | 聽成 | 建議 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rep["positions"], key=lambda r: (V.VERDICT_ORDER[r["result"]], r["line"])):
        heard = "、".join(f"{w['heard']}({w['kind']})" for w in r["heard"])
        L.append(f"| {r['line']} | {r['ch']} | {V._cell(r['ctx'])} | {r['value'] or '-'} | {'、'.join(r['why'])} | {OUTCOME[r['result']]} | "
                 f"{r['right']}/{r['wrong']}/{r['undetermined']} | {V._cell(heard)} | {r['suggest']} |")
    if rep["known_bad"]:
        L += ["", "## 記憶已判要改寫(不重測,算唸錯)"] + [f"- 行 {k['line']} {k['ctx']}:{k['say']}" for k in rep["known_bad"]]
    if rep["english"]:
        L += ["", "## 英文詞(只進報告,不進記憶表)"] + [f"- 行 {e['line']} {e['word']}:{OUTCOME[e['result']]} {e['right']}/{e['wrong']} {'、'.join(e['heard'])}" for e in rep["english"]]
    if rep["untested"] or rep["untested_en"]:
        L += ["", f"## 超過 {rep['max_sent']} 句未試"] + [f"- 行 {u['line']} {u['ctx']}(backlog {u['weight']})" for u in rep["untested"]] + [f"- 英文 {w}" for w in rep["untested_en"]]
    jf.with_suffix(".md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return jf


def memory_rows(tag, items):
    return [dict(text=it["t"], pos=x["pos"], ch=x["ch"], py=x["value"] or "", results=x["results"], tag=tag, rewrite=it["say"])
            for it in items for x in it["positions"]]


def print_wrong(rep):
    for r in rep["positions"]:
        if r["result"] == "wrong":
            print(f"唸錯 行 {r['line']} {r['ctx']}:聽成 {'、'.join(w['heard'] for w in r['heard']) or '?'}|{r['say']}")
    for e in rep["english"]:
        if e["result"] == "wrong":
            print(f"唸錯 行 {e['line']} 英文 {e['word']}:{'、'.join(e['heard'])}")
    for k in rep["known_bad"]:
        print(f"唸錯 行 {k['line']} {k['ctx']}:記憶已判要改寫|{k['say']}")


# ------------------------------------------------------------ 閘門狀態(tts_dispatch 用)
def status(tag):
    """-> (通過, 說明)。"""
    f = report_path(tag)
    if not f.exists():
        return False, "未跑(沒有 c0_report.json)"
    rep = json.loads(f.read_text(encoding="utf-8"))
    if rep.get("script_sha") != script_sha(tag):
        return False, f"報告與目前配音稿不符({rep.get('date')} 的結果,稿或讀音表已改)"
    if rep.get("missing"):
        return False, f"上次合成不完整(缺 {rep['missing']} 筆)"
    if rep.get("wrong"):
        return False, f"唸錯 {rep['wrong']} 處(見 {f.with_suffix('.md').relative_to(P.REPO)})"
    return True, f"已通過({rep.get('date')}:{rep.get('sentences')} 句,無法判定 {rep.get('undetermined')})"


# ------------------------------------------------------------ 執行
def dry_run(tag, plan, seeds):
    its = plan["items"]
    n_pos = sum(len(it["positions"]) for it in its)
    n_en = sum(len(it["words"]) for it in its)
    total = len(its) * len(seeds)
    print(f"{tag}:配音單位 {len(plan['units'])},記憶命中 {plan['n_mem']},記憶已判要改寫 {len(plan['known'])},{plan['note']}")
    print(f"試配 {len(its)} 句(上限 {MAX_SENT})× {len(seeds)} seed = 合成 {total} 句,預估 {total * V.SEC_PER_SENT / 60:.0f} 分鐘;"
          f"涵蓋位置 {n_pos}、英文詞 {n_en},未試 {len(plan['untested'])} 位置、{len(plan['untested_en'])} 英文詞")
    for it in its:
        ps = "、".join(f"{x['ctx']}={x['value'] or '-'}({'/'.join(x['why'])})" for x in it["positions"])
        print(f"  行 {it['line']}|{it['say']}\n    {ps}" + (f"\n    英文 {'、'.join(it['words'])}" if it["words"] else ""))
    for x in plan["known"]:
        print(f"  記憶要改寫 行 {x['line']} {x['ctx']}|{x['say']}")


def run(tag, seeds, plan=None, max_retry=0, norm=None, ph=None, reading=None, simp=None):
    """真跑一次(不含 dry-run)。-> 結束碼。"""
    plan = plan or build_plan(tag)
    items, missing = plan["items"], 0
    rep_ph = None
    if items:
        work = work_dir(tag, items)
        work.mkdir(parents=True, exist_ok=True)
        (work / "manifest.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        with V.GL.gpu_lock(tag, "tts_c0"):
            bad = V.synth(items, seeds, work, max_retry)
        if bad:
            print(f"注意:seed {bad} 的 tts_cosy3 非正常結束,報告只含已完成的句子")
        rep_ph = ph or V.PyPhon()
        missing = judge_items(items, seeds, work, norm, rep_ph, reading, simp)
        acts = PM.record_tests(memory_rows(tag, items), f"c0:{tag}:{work.name}", rep_ph)
        print("語境讀音記憶:" + ("、".join(f"{k} {v}" for k, v in acts.items()) or "沒有可寫的結果"))
    rep = build_report(tag, plan, seeds, rep_ph, script_sha(tag), missing)
    jf = write_report(rep)
    print(f"C0 {tag}:{rep['sentences']} 句,唸對 {rep['right']}、唸錯 {rep['wrong']}、無法判定 {rep['undetermined']}、未試 {len(rep['untested'])}"
          f"\n報告 {jf.relative_to(P.REPO)}")
    print_wrong(rep)
    if missing:
        print(f"合成不完整:缺 {missing} 筆紀錄")
        return EXIT_INCOMPLETE
    return EXIT_WRONG if rep["wrong"] else 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tag")
    ap.add_argument("--seeds", default=DEFAULT_SEEDS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--g2p", action="store_true", help="dry-run 也現算 g2p 不一致(CPU 載 g2pW)")
    a = ap.parse_args(argv)
    seeds = [int(x) for x in a.seeds.split(",") if x.strip()]
    plan = build_plan(a.tag, compute_g2p=a.g2p or not a.dry_run)
    if a.dry_run:
        dry_run(a.tag, plan, seeds)
        return 0
    return run(a.tag, seeds, plan)


if __name__ == "__main__":
    sys.exit(main())
