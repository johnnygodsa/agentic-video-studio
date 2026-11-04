"""文案結構檢查:python -X utf8 pipeline/script_structure.py <tag> [--json] [--timeline <path>] [--strict]

讀 <tag>/script.txt(用 script_txt2json.parse),檢查開場型態、中立聲明、第一判斷句秒數、塊(段落)長度與新料間隔、
最強證據位置、CTA 位置、結尾四件、字/分與事實/分。全部是警告;--strict 才有警告就回結束碼 1。
輸出 build/<tag>/structure.json 與 stdout 摘要(--json 時 stdout 改印 JSON)。規則出處與門檻見 pipeline/docs/structure.md。
有 --timeline、keep/<tag>/timeline.json、build/<tag>/timeline.json(依序,且 lines 數 = 資料行數)就用實際秒,否則用 pace 估。
門檻是 2026-10-26 依 channel/規則/2_文案.md §2 訂的初值;留存證據 n=6,屬弱證據,未校準。
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pace
import paths as P
import script_lint as L
import script_txt2json as T

# ---- 門檻與詞表(集中在這裡)
TH = dict(
    judge_sec=L.T["judge_sec"],          # 第一判斷句 <= 15 秒(沿用 lint)
    blocks=(4, 5), block_sec=(90, 150),  # 塊數、每塊秒數
    gap_sec=55,                          # 塊內新料間隔上限
    strongest_pct=(55, 75),              # 最強證據首次出現位置 %
    cta_pct_max=50,
    questions=(2, 3), ending_n=10, callback_n=6,
    cpm=(315, 350), fpm=(4, 9),
)
RE_VIEWER = re.compile(r"你|你的|你們|(?:台灣)?玩家(?:們)?(?:等|花|買|付|被|要)")
RE_MONEY = re.compile(r"美金|元|塊|月費|預購")
RE_TURN = re.compile(r"可是|結果|卻|偏偏|反而|竟")
# 開場「含數字」:阿拉伯數字,或中文數字後接單位(二零一九年、十月、一個多月、七十美金…)
RE_HOOK_NUM = re.compile(r"\d|[一二三四五六七八九十百千萬億兩]+(?:點|分|年|月|號|個|次|倍|萬|億|美金|元)")
RE_EVENT = re.compile(r"^(?:\d{4}\s?年|\d{1,2}\s?月|[一二三四五六七八九十]+月|日期|公告|宣布|更新說明|官方|Beta|測試期)", re.I)
RE_NEUTRAL = re.compile(r"不選邊|自己判斷|不替你下結論|不評論|中立")
RE_BLOCK_SKIP = re.compile(r"開場|結尾|片尾")
RE_LAND_WHO = re.compile(r"你|你的|玩家")
RE_LAND_WHAT = re.compile(r"錢|美金|小時|分鐘|天|等|買")
RE_SENT = re.compile(r"[^。?!？！]+[。?!？！]*")
RE_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?\s?(?:[萬億千百%％倍])?")
RE_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9&.\-]+")
RE_QUOTED = re.compile(r"[「《『]([^」》』]{2,6})[」》』]")
RE_CJK_RUN = re.compile(r"[一-鿿]+")
STOP_CHARS = set("的了是在我你他她它不有這那就都也和與而但很被把讓說會要還")
UNIT = {"萬": 1e4, "億": 1e8, "千": 1e3, "百": 1e2}
HOOK_TYPES = ("觀眾利害", "反差", "事件宣告", "背景交代")


def _num_value(m):
    """RE_NUM 命中 → (數值, 正規化字串);年份(1990–2035 且無單位)回 None。"""
    s = re.sub(r"\s", "", m.group(0))
    unit = s[-1] if s[-1] in "萬億千百%％倍" else ""
    body = s[:-1] if unit else s
    body = body.replace(",", "")
    try:
        v = float(body)
    except ValueError:
        return None
    if not unit and re.fullmatch(r"\d{4}", body) and 1990 <= v <= 2035:
        return None
    return v * UNIT.get(unit, 1), s.replace(",", "")


def _anim_type(extra, defs):
    a = extra.get("anim")
    if isinstance(a, str):
        a = defs.get("anim:" + a.partition("#")[0])
    return str(a.get("type", "")) if isinstance(a, dict) else ""


def build_units(sections, defs, timeline_lines=None):
    """展開成句子單位 [dict(line,row,sec,tag,extra,text,chars,start,end,anim)];有 timeline 用實際秒,否則用 pace 估。"""
    units, row_i, t = [], 0, 0.0
    for si, sec in enumerate(sections):
        for no, tag, text, extra in sec["rows"]:
            sents = [x.strip() for x in RE_SENT.findall(text) if pace.count_chars(x)]
            chars = [pace.count_chars(x) for x in sents]
            if timeline_lines is not None:
                r0, r1 = float(timeline_lines[row_i]["start"]), float(timeline_lines[row_i]["end"])
            else:
                r0, r1 = t, t + pace.est_seconds(text)
            tot = sum(chars) or 1
            acc = 0
            for s, c in zip(sents, chars):
                units.append(dict(line=no, row=row_i, sec=si, tag=tag, extra=extra, text=s, chars=c,
                                  start=r0 + (r1 - r0) * acc / tot, end=r0 + (r1 - r0) * (acc + c) / tot,
                                  anim=_anim_type(extra, defs)))
                acc += c
            t = r1
            row_i += 1
    return units


def is_new_fact(u):
    return bool(re.search(r"\d", u["text"])) or u["tag"].startswith("quote:") or (u["tag"].startswith("img:") and bool(u["extra"].get("hl")))


def classify_hook(sentences):
    """前 3 句(字串清單)→ (主型態, 命中的所有型態)。單一來源:retention_align 也呼叫這裡。
    優先序:反差(前 3 句含數字且含轉折詞)> 觀眾利害(前 2 句含 你/你的/你們、玩家+動詞、錢詞)>
    事件宣告(第 1 句以日期/公告/宣布/更新說明/官方/Beta/測試期 開頭,且前 3 句沒有轉折或你)> 背景交代。"""
    first3 = [x for x in (sentences or [])][:3]
    t2 = "".join(first3[:2])
    t3 = "".join(first3)
    m = []
    if RE_HOOK_NUM.search(t3) and RE_TURN.search(t3):
        m.append("反差")
    if RE_VIEWER.search(t2) or RE_MONEY.search(t2):
        m.append("觀眾利害")
    if first3 and RE_EVENT.match(first3[0].strip()) and not RE_TURN.search(t3) and "你" not in t3:
        m.append("事件宣告")
    return (m[0] if m else "背景交代"), m


def entities(units):
    """回扣開場用的實體:阿拉伯數字(含單位,排除無單位的 1–2 位數)、英數專名、「」《》內的名稱、不含虛字的 4 字連續中文片段。
    不依賴 jieba(沒裝也要跑);4 字片段是代理指標,會有少量誤中。"""
    ents = set()
    for u in units:
        s = u["text"]
        for m in RE_NUM.finditer(s):
            nv = _num_value(m)
            if nv and not re.fullmatch(r"\d{1,2}", nv[1]):
                ents.add(nv[1])
        ents.update(x.lower() for x in RE_LATIN.findall(s) if len(x) >= 2)
        ents.update(RE_QUOTED.findall(s))
        for run in RE_CJK_RUN.findall(s):
            for i in range(len(run) - 3):
                g = run[i:i + 4]
                if not (set(g) & STOP_CHARS):
                    ents.add(g)
    return ents


def numbers_of(units):
    out = set()
    for u in units:
        for m in RE_NUM.finditer(u["text"]):
            nv = _num_value(m)
            if nv and not re.fullmatch(r"\d{1,2}", nv[1]):
                out.add(nv[1])
    return out


def load_timeline(path, n_rows):
    """回傳 lines list(長度須 = 資料行數);讀不到/長度不符回 (None, 原因)。"""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        lines = d["lines"] if isinstance(d, dict) else d
        for x in lines:
            float(x["start"]), float(x["end"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        return None, f"timeline 讀不到或格式不符({path}):{type(e).__name__}"
    if len(lines) != n_rows:
        return None, f"timeline 句數 {len(lines)} ≠ 文案資料行 {n_rows}({path}),改用估算"
    return lines, None


def analyze(src, timeline_paths=()):
    """src = script.txt 全文;timeline_paths = 依序嘗試的 timeline.json 路徑。回傳結果 dict(即 structure.json 內容)。"""
    _, _, sections, _, defs, _ = T.parse(src)
    n_rows = sum(len(s["rows"]) for s in sections)
    tl, notes = None, []
    for p in timeline_paths:
        if p and Path(p).is_file():
            tl, why = load_timeline(p, n_rows)
            if tl is not None:
                break
            notes.append(why)
    units = build_units(sections, defs, tl)
    if not units:
        raise ValueError("沒有旁白行")
    total = max(u["end"] for u in units) or 1e-9
    cont = [u for u in units if u["tag"] != "cta"]
    if not cont:
        raise ValueError("沒有旁白行")
    warns = []

    def warn(code, line, text):
        warns.append(dict(code=code, line=line, text=text))

    def pct(u):
        return u["start"] / total * 100

    # ---- 開場型態
    first3 = cont[:3]
    hook, hook_all = classify_hook([u["text"] for u in first3])
    if hook in ("事件宣告", "背景交代"):
        ev = "/".join(u["text"][:30] for u in first3)
        warn("HOOK_TYPE", first3[0]["line"], f"開場是「{hook}」(0–1% 留存跌 6.6–7.8 點,反差 2.3,n=6 弱證據):{ev}")
    # ---- 中立聲明
    for u in cont:
        if RE_NEUTRAL.search(u["text"]):
            warn("NEUTRAL", u["line"], f"中立聲明:{u['text'][:40]}(再跌約 6.3 點,n=6 弱證據)")
    # ---- 第一判斷句
    ju = next((u for u in cont if L.JUDGE.search(u["text"])), None)
    judge_sec = round(ju["start"], 1) if ju else None
    if ju is None:
        warn("JUDGE_NONE", 0, "全片沒有判斷詞(詞表同 script_lint.JUDGE)")
    elif ju["start"] > TH["judge_sec"]:
        warn("JUDGE_LATE", ju["line"], f"第一個判斷句約 {ju['start']:.0f} 秒才出現(目標 <= {TH['judge_sec']}):{ju['text'][:30]}")
    # ---- 塊
    blocks, order = [], []
    for si, sec in enumerate(sections):
        if RE_BLOCK_SKIP.search(sec["name"]):
            continue
        us = [u for u in units if u["sec"] == si]
        if not us:
            continue
        cu = [u for u in us if u["tag"] != "cta"]
        nf = [u for u in cu if is_new_fact(u)]
        b0, b1 = us[0]["start"], (cu or us)[-1]["end"]   # 塊結束 = 最後一句旁白(cta 句不算塊內)
        lands = any(RE_LAND_WHO.search(u["text"]) and RE_LAND_WHAT.search(u["text"]) for u in cu)
        name = sec["name"] or "(未命名)"
        blocks.append(dict(name=name, start_s=round(b0, 1), end_s=round(b1, 1), new_facts=len(nf), lands_on_viewer=lands))
        order.append((b0, b1, name, nf, lands))
        dur = b1 - b0
        lo, hi = TH["block_sec"]
        if not lo <= dur <= hi:
            warn("BLOCK_SEC", us[0]["line"], f"「{name[:16]}」{dur:.0f} 秒(目標 {lo}–{hi};2_文案 §2 一塊 90–150 秒)")
        for a, b in zip(nf, nf[1:]):
            if b["start"] - a["start"] > TH["gap_sec"]:
                warn("FACT_GAP", a["line"], f"「{name[:12]}」L{a['line']}→L{b['line']} 之間 {b['start'] - a['start']:.0f} 秒沒有新料(上限 {TH['gap_sec']})")
        if not nf and dur > TH["gap_sec"]:
            warn("FACT_GAP", us[0]["line"], f"「{name[:12]}」{dur:.0f} 秒內沒有任何新料")
        if not lands:
            warn("NO_LANDING", us[0]["line"], f"「{name[:16]}」沒有落到觀眾的句子(你/玩家 + 錢/時間詞)")
    lo, hi = TH["blocks"]
    if not lo <= len(blocks) <= hi:
        warn("BLOCK_COUNT", 0, f"{len(blocks)} 塊(目標 {lo}–{hi};排除段名含 開場/結尾/片尾 的段)")
    # ---- 最強證據位置(代理指標:取最大數字所在句)
    cands = [dict(line=u["line"], pct=round(pct(u), 1), kind=k) for u in cont
             for k in [("quote" if u["tag"].startswith("quote:") else "num/compare" if re.search(r"num|compare", u["anim"]) or u["tag"].startswith("cmp:") else "")] if k]
    best, best_u = None, None
    for u in cont:
        for m in RE_NUM.finditer(u["text"]):
            nv = _num_value(m)
            if nv and (best is None or nv[0] > best):
                best, best_u = nv[0], u
    strongest = round(pct(best_u), 1) if best_u else None
    if strongest is not None and not TH["strongest_pct"][0] <= strongest <= TH["strongest_pct"][1]:
        warn("STRONGEST_POS", best_u["line"], f"最大數字所在句在 {strongest:.0f}%(目標 {TH['strongest_pct'][0]}–{TH['strongest_pct'][1]}%;"
             f"代理指標,不等於最強證據):{best_u['text'][:30]}")
    # ---- CTA
    ctas = [u for u in units if u["tag"] == "cta"]
    cta_pos = round(pct(ctas[0]), 1) if ctas else None
    if ctas:
        fb_end = order[0][1] if order else 0.0
        if ctas[0]["start"] < fb_end or cta_pos >= TH["cta_pct_max"]:
            warn("CTA_POS", ctas[0]["line"], f"cta 在 {cta_pos:.0f}%(須在第一塊結束 {fb_end:.0f} 秒之後、{TH['cta_pct_max']}% 之前)")
    else:
        notes.append("沒有 cta 標籤句(提示,非警告)")
    # ---- 結尾
    en = TH["ending_n"]
    end_us, before = cont[-en:], cont[:-en]
    head_us = before[:TH["callback_n"]] if before else cont[:0]
    q = sum(1 for u in end_us if re.search(r"[?？][」』)）\"'\s]*$", u["text"]))
    shared = sorted(entities(head_us) & entities(end_us), key=lambda x: (-len(x), x))
    new_nums = sorted(numbers_of(end_us) - numbers_of(before)) if before else []
    ending = dict(questions=q, judgment=any(L.JUDGE.search(u["text"]) for u in end_us),
                  callback=bool(shared), new_fact=bool(new_nums))
    qlo, qhi = TH["questions"]
    if not qlo <= q <= qhi:
        warn("END_QUESTIONS", end_us[-1]["line"], f"結尾 {en} 句有 {q} 個問句(目標 {qlo}–{qhi})")
    if not ending["judgment"]:
        warn("END_JUDGMENT", end_us[-1]["line"], f"結尾 {en} 句沒有判斷句")
    if not ending["callback"]:
        warn("END_CALLBACK", end_us[-1]["line"], "結尾沒有回扣開場前 6 句的實體(數字/專名)")
    if not ending["new_fact"]:
        warn("END_NEWFACT", end_us[-1]["line"], "結尾沒有前面沒出現過的新數字")
    # ---- 節奏
    chars = sum(u["chars"] for u in units)
    mins = total / 60
    cpm = chars / mins
    n_new = sum(1 for u in cont if is_new_fact(u))
    fpm = n_new / mins
    if tl is not None and not TH["cpm"][0] <= cpm <= TH["cpm"][1]:
        warn("CPM", 0, f"字/分 {cpm:.0f}(含停頓,規則帶 {TH['cpm'][0]}–{TH['cpm'][1]})")
    if not TH["fpm"][0] <= fpm <= TH["fpm"][1]:
        warn("FPM", 0, f"事實/分 {fpm:.1f}(規則帶 {TH['fpm'][0]}–{TH['fpm'][1]})")
    return dict(
        timeline_used=tl is not None, hook_type=hook, hook_matches=hook_all, judge_sec=judge_sec,
        blocks=blocks, strongest_pos_pct=strongest, strongest_candidates=cands, cta_pos_pct=cta_pos,
        ending=dict(ending, callback_hits=shared[:5], new_numbers=new_nums[:5]),
        chars_per_min=round(cpm, 1), facts_per_min=round(fpm, 2),
        metrics=dict(chars=chars, total_s=round(total, 1), minutes=round(mins, 2), sentences=len(units), new_fact_sentences=n_new,
                     chars_per_min=round(cpm, 1), facts_per_min=round(fpm, 2)),
        notes=notes, warnings=warns)


def summary(tag, r):
    ok = lambda b: "有" if b else "無"
    m, e = r["metrics"], r["ending"]
    out = [f"[structure] {tag}: {m['sentences']} 句、{m['chars']} 字、{m['total_s']:.0f} 秒({'timeline 實際秒' if r['timeline_used'] else '估算,字/分恆為 330'})",
           f"  開場型態: {r['hook_type']}(命中 {'/'.join(r['hook_matches']) or '無'})",
           f"  第一判斷句: {'%.0f 秒' % r['judge_sec'] if r['judge_sec'] is not None else '無'}(目標 <= {TH['judge_sec']})",
           f"  塊: {len(r['blocks'])} 塊(目標 {TH['blocks'][0]}–{TH['blocks'][1]})"]
    out += [f"    {b['name'][:14]} {b['end_s'] - b['start_s']:.0f}s 新料{b['new_facts']} 落到觀眾{ok(b['lands_on_viewer'])}" for b in r["blocks"][:6]]
    out += [f"  最大數字位置: {'%.0f%%' % r['strongest_pos_pct'] if r['strongest_pos_pct'] is not None else '無'}(目標 55–75%)"
            f" | CTA: {'%.0f%%' % r['cta_pos_pct'] if r['cta_pos_pct'] is not None else '無'}",
            f"  結尾: 問句 {e['questions']}、判斷{ok(e['judgment'])}、回扣{ok(e['callback'])}、新事實{ok(e['new_fact'])}",
            f"  節奏: 字/分 {('%.0f(315–350)' % r['chars_per_min']) if r['timeline_used'] else '需 timeline'}、事實/分 {r['facts_per_min']:.1f}(4–9)"]
    ws = r["warnings"]
    out.append(f"[structure] 警告 {len(ws)} 項(不中止;--strict 才算錯誤)")
    room = 24 - len(out)
    out += [f"  {w['code']} L{w['line']} {w['text'][:70]}" for w in ws[:max(room, 0)]]
    if len(ws) > room:
        out.append(f"  …另 {len(ws) - room} 項見 build/{tag}/structure.json")
    out += [f"  提示: {n}" for n in r["notes"]][:max(25 - len(out), 0)]
    return out[:25]


def main(argv=None):
    ap = argparse.ArgumentParser(description="文案結構檢查(警告制)")
    ap.add_argument("tag")
    ap.add_argument("--json", action="store_true", help="stdout 印完整 JSON(不印摘要)")
    ap.add_argument("--timeline", help="timeline.json 路徑(預設找 keep/<tag>、build/<tag>)")
    ap.add_argument("--strict", action="store_true", help="有警告就回結束碼 1")
    a = ap.parse_args(argv)
    sp = P.ROOT / a.tag / "script.txt"
    if not sp.is_file():
        sys.exit(f"[structure] 找不到 {sp}")
    cands = [a.timeline] if a.timeline else [P.ROOT / "keep" / a.tag / "timeline.json", P.build_dir(a.tag) / "timeline.json"]
    try:
        r = analyze(sp.read_text(encoding="utf-8-sig"), cands)
    except (SystemExit, ValueError) as e:
        print(f"[structure] 解析失敗:{e}", file=sys.stderr)
        sys.exit(2)
    bd = P.build_dir(a.tag)
    bd.mkdir(parents=True, exist_ok=True)
    (bd / "structure.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print("\n".join(summary(a.tag, r)))
    sys.exit(1 if a.strict and r["warnings"] else 0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
