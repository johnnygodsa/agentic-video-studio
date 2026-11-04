#!/usr/bin/env python3
r"""逐句事實連結檢查(PLAN 文案資料驅動 §3.7;閘門 2「文案每個數字、日期、引言都對回表上一列」的機器版)。

  python -X utf8 pipeline/facts_check.py <tag> [--strict] [--write-spec] [--json]

資料:<tag>\script.txt 的旁白句(句號 = 依序 1-based,與 spec_check 相同)、projects\<tag>\facts*.md(facts_lib.parse)。
需要核對的句:含數字(阿拉伯數字、年月日、有單位的中文數字)、「」引言、或 spec.json names[] 人名。
  有 f(行尾 json "f": ["F12","F13"]):句內每個數字都要出現在所引 F 的 主張/原句/絕對值/來源(去網址) 的數字集合,
    否則「數字不符」(狀態不符);引了不存在的 F → 錯誤。
  無 f:自動配對(標 auto)= 句內所有數字交集只剩一條 F(多條時再用「」引言/人名縮小);否則「未連結」。
  所引(或 auto)的 F 狀態為 derived/single/unverified/secondary 者:該句要有行尾 json note,
    或 anim/quote 的 src 含「未證實|推算|轉述|媒體|報價|估」,否則警告「弱狀態無小字」。
  句子連到(含 auto)的 F 另查兩項(2026-11-03):
    無出處:F 的來源沒有 http(s) 網址、也沒引用其他 F 編號或本機檔(comments_ref\、.md、.json),或原句空/「查無」
      (狀態 derived 推算的列原句可空,來源仍要有網址或 F 參照;facts_lib.source_gaps);
    引矛盾:F 的 status_raw 含「矛盾」(兩邊都列、不裁定的列不可拿來當句子依據)。
  表級(不需句子):facts.md 狀態不是「查無」、卻缺網址/原句的列,印「表內缺出處」清單,只警告、不影響 exit。
輸出:繁體中文摘要;最後一行固定
  `[facts_check] 連結 N/M 句 (xx%)、未連結 K、狀態不符 J、錯誤 E、無出處 X、引矛盾 Y`(X、Y 在尾端追加,舊解析器抓前段照常可用)。
  --json 會在摘要之前另印一段 JSON;--strict 時狀態不符+錯誤+無出處+引矛盾 > 0 → exit 1(其餘一律 exit 0)。
  --write-spec 把連結結果寫進 projects\<tag>\spec.json 的 facts[](每條有連到句的 F 一筆;保留其他鍵;檔案不存在就建最小檔)。
  id 重複(例如 facts.md 與 facts_r2a.md 都有 F1)時,依 facts_lib.find_files 的順序,先出現者勝。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facts_lib as FL  # noqa: E402
import paths  # noqa: E402
import spec_check as SC  # noqa: E402

WEAK_NOTE_RE = re.compile(r"未證實|推算|轉述|媒體|報價|估")
SPEC_STATUS = {"confirmed": "confirmed", "derived": "partial", "secondary": "partial", "player_quote": "single",
               "single": "single", "unverified": "unverified", "unknown": "partial"}
RE_QUOTE_TXT = re.compile(r"[「『]([^」』]+)[」』]")


def _f_ids(raw):
    """行尾 f 欄位 -> (canon id 清單, 錯誤訊息或 None)。"""
    if raw is None:
        return [], None
    if isinstance(raw, str):
        raw = [x for x in re.split(r"[,\s、,]+", raw) if x]
    if not isinstance(raw, list) or not all(isinstance(x, (str, int)) for x in raw):
        return [], 'f 要是清單 ["F12","F13"]'
    return [FL.canon_id(x) for x in raw], None


def _fact_blob(f):
    return " ".join((f.claim, f.quote, f.magnitude, f.source))


def _note_ok(ln):
    if ln.get("note"):
        return True
    for k in ("anim", "quote"):
        d = ln.get(k)
        if isinstance(d, dict) and WEAK_NOTE_RE.search(str(d.get("src", ""))):
            return True
    return False


def analyze(lines, facts, names=()):
    """回傳 dict:sentences(逐句結果)與統計。lines 為 spec_check.load_lines 的句子 dict 清單。"""
    by_id, dups = {}, []
    for f in facts:
        k = FL.canon_id(f.id)
        if k in by_id:
            dups.append(k)
        else:
            by_id[k] = f
    nums_of = {k: FL.fact_numbers(f) for k, f in by_id.items()}

    sents = []
    for i, ln in enumerate(lines, 1):
        t = ln.get("text") or ""
        quotes = [q.strip() for q in RE_QUOTE_TXT.findall(t) if len(q.strip()) >= 2]
        hit = [x for x in names if x and x in t]
        why = []
        if SC.has_number(t) or FL.sentence_numbers(t):   # 後者補上 美金/元/點 等單位的中文數字
            why.append("數字")
        if SC.RE_QUOTE.search(t):
            why.append("引言")
        if hit:
            why.append("人名")
        ids, ferr = _f_ids(ln.get("f"))
        s = dict(i=i, text=t, need=bool(why), why=why, f=[], auto=False, linked=False,
                 mismatch=[], errors=[], weak=[], reason="", no_source=[], contra=[])
        if ferr:
            s["errors"].append(ferr)
        if not (why or ids):
            sents.append(s)
            continue
        nums = FL.sentence_numbers(t)
        if ids:
            unknown = [x for x in ids if x not in by_id]
            if unknown:
                s["errors"].append("引用不存在的 " + "/".join(unknown))
            ids = [x for x in ids if x in by_id]
            s["f"] = ids
            if ids and not s["errors"]:
                union = set().union(*(nums_of[x] for x in ids))
                miss = sorted(n for n in nums if n not in union and not (n.endswith("%") and n[:-1] in union))
                if miss:
                    s["mismatch"].append(f"數字 {'、'.join(miss)} 不在 {'/'.join(ids)}")
                else:
                    s["linked"] = True
        else:
            pool = list(by_id)
            if nums:
                for n in nums:
                    pool = [k for k in pool if n in nums_of[k] or (n.endswith("%") and n[:-1] in nums_of[k])]
            narrowed = False
            for term in quotes + hit:
                sub = [k for k in pool if term in _fact_blob(by_id[k])]
                if sub:
                    pool, narrowed = sub, True
                elif not nums:
                    pool = []
            if not nums and not narrowed:
                pool = []
            if len(pool) == 1:
                s.update(f=pool, auto=True, linked=True)
            elif not nums and not narrowed:
                s["reason"] = "引言/人名在事實表找不到對應列"
            elif not pool:
                s["reason"] = "數字 " + "、".join(sorted(nums)) + " 沒有同時出現在任何一條 F"
            else:
                s["reason"] = f"數字對到多條 F({'/'.join(pool[:5])}{'…' if len(pool) > 5 else ''}),請加 f"
        if s["f"] and s["linked"]:
            weak = [x for x in s["f"] if by_id[x].status in FL.WEAK]
            if weak and not _note_ok(ln):
                s["weak"] = [f"{x}({by_id[x].status_raw or by_id[x].status})" for x in weak]
        for x in s["f"]:
            gaps = FL.source_gaps(by_id[x])
            if gaps:
                s["no_source"].append(f"{x}({'、'.join(gaps)})")
            if "矛盾" in (by_id[x].status_raw or ""):
                s["contra"].append(f"{x}({by_id[x].status_raw[:24]})")
        sents.append(s)

    need = [s for s in sents if s["need"]]
    n_link = sum(1 for s in need if s["linked"])
    n_un = sum(1 for s in need if not s["linked"] and not s["f"] and not s["errors"])
    n_mis = sum(1 for s in sents if s["mismatch"])
    n_err = sum(len(s["errors"]) for s in sents)
    n_nosrc = sum(1 for s in sents if s["no_source"])
    n_contra = sum(1 for s in sents if s["contra"])
    table_gaps = [[k, "、".join(g)] for k, f in by_id.items() if "查無" not in (f.status_raw or "") and (g := FL.source_gaps(f))]
    return dict(sentences=sents, need=len(need), linked=n_link, unlinked=n_un, mismatch=n_mis, errors=n_err,
                no_source=n_nosrc, contra=n_contra, table_gaps=table_gaps,
                dup_ids=sorted(set(dups)), facts=len(by_id), by_id=by_id)


def spec_facts(res, project_root=None):
    """analyze 結果 -> spec.json 的 facts[]。"""
    out = []
    lines_of = {}
    for s in res["sentences"]:
        if s["linked"]:
            for x in s["f"]:
                lines_of.setdefault(x, []).append(s["i"])
    for k, f in res["by_id"].items():
        if k not in lines_of:
            continue
        try:
            src = Path(f.file).resolve().relative_to(paths.ROOT.resolve()).as_posix()
        except (ValueError, OSError):
            src = Path(f.file).as_posix()
        out.append(dict(id=k, claim=f.claim, lines=sorted(set(lines_of[k])), status=SPEC_STATUS.get(f.status, "partial"),
                        src=src))
    return out


def write_spec(tag, facts_list):
    sp = paths.PROJECTS / tag / "spec.json"
    spec = {}
    if sp.exists():
        spec = json.loads(sp.read_text(encoding="utf-8-sig"))
    else:
        sp.parent.mkdir(parents=True, exist_ok=True)
        spec = {"tag": tag}
    spec["facts"] = facts_list
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    return sp


def summary_line(res):
    m, n = res["need"], res["linked"]
    pct = 100.0 if m == 0 else n * 100.0 / m
    return (f"[facts_check] 連結 {n}/{m} 句 ({pct:.0f}%)、未連結 {res['unlinked']}、狀態不符 {res['mismatch']}、錯誤 {res['errors']}"
            f"、無出處 {res['no_source']}、引矛盾 {res['contra']}")


def bad_count(res):
    """--strict 的 exit 1 條件:狀態不符+錯誤+無出處+引矛盾。"""
    return res["mismatch"] + res["errors"] + res["no_source"] + res["contra"]


def report(tag, res, fact_files):
    out = [f"facts_check {tag}: 旁白 {len(res['sentences'])} 句、需核對 {res['need']} 句、事實表 {res['facts']} 條"
           f"({len(fact_files)} 個檔)"]
    if res["dup_ids"]:
        out.append(f"  註:id 重複 {len(res['dup_ids'])} 個({'、'.join(res['dup_ids'][:8])}),取先出現者")
    auto = sum(1 for s in res["sentences"] if s["auto"])
    out.append(f"  已連結 {res['linked']} 句(其中自動配對 auto {auto} 句)")
    for s in res["sentences"]:
        for m in s["mismatch"]:
            out.append(f"  狀態不符 句{s['i']}:{m}:{s['text'][:28]}")
        for e in s["errors"]:
            out.append(f"  錯誤 句{s['i']}:{e}:{s['text'][:28]}")
        if s["no_source"]:
            out.append(f"  無出處 句{s['i']}:{'、'.join(s['no_source'])}:{s['text'][:28]}")
        if s["contra"]:
            out.append(f"  引矛盾 句{s['i']}:{'、'.join(s['contra'])}:{s['text'][:28]}")
    un = [s for s in res["sentences"] if s["need"] and not s["linked"] and not s["f"] and not s["errors"]]
    for s in un[:25]:
        out.append(f"  未連結 句{s['i']}[{'、'.join(s['why'])}]:{s['text'][:28]}  ({s['reason']})")
    if len(un) > 25:
        out.append(f"  …另 {len(un) - 25} 句未連結")
    weak = [s for s in res["sentences"] if s["weak"]]
    out.append(f"  警告 弱狀態無小字 {len(weak)} 句")
    for s in weak[:15]:
        out.append(f"  警告 句{s['i']} 連到 {'、'.join(s['weak'])} 但沒有 note/未證實類 src:{s['text'][:24]}")
    if len(weak) > 15:
        out.append(f"  …另 {len(weak) - 15} 句")
    tg = res["table_gaps"]
    if tg:
        out.append(f"  表內缺出處(只警告){len(tg)} 條:狀態不是查無、卻缺網址/原句")
        for k, g in tg[:25]:
            out.append(f"    {k}:{g}")
        if len(tg) > 25:
            out.append(f"    …另 {len(tg) - 25} 條")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="逐句事實連結檢查")
    ap.add_argument("tag")
    ap.add_argument("--strict", action="store_true", help="狀態不符+錯誤+無出處+引矛盾 > 0 → exit 1")
    ap.add_argument("--write-spec", action="store_true", help="把連結結果寫進 projects/<tag>/spec.json 的 facts[]")
    ap.add_argument("--json", action="store_true", help="摘要之前另印 JSON")
    a = ap.parse_args(argv)
    pdir = paths.PROJECTS / a.tag
    files = FL.find_files(pdir)
    if not (paths.ROOT / a.tag / "script.txt").exists():
        print(f"找不到 {paths.ROOT / a.tag / 'script.txt'}")
        print("[facts_check] 連結 0/0 句 (100%)、未連結 0、狀態不符 0、錯誤 1、無出處 0、引矛盾 0")
        return 2
    lines = SC.load_lines(a.tag)
    facts = FL.parse(files) if files else []
    names = []
    sp = pdir / "spec.json"
    if sp.exists():
        try:
            names = [x for x in (json.loads(sp.read_text(encoding="utf-8-sig")).get("names") or []) if isinstance(x, str)]
        except ValueError:
            pass
    res = analyze(lines, facts, names)
    if not facts:
        res["errors"] += 1
    if a.json:
        slim = {k: v for k, v in res.items() if k != "by_id"}
        slim["tag"] = a.tag
        print(json.dumps(slim, ensure_ascii=False, indent=1))
    for ln in report(a.tag, res, files):
        print(ln)
    if not facts:
        print("  錯誤:找不到事實表(projects/%s/facts*.md 沒有表頭含 # 與 主張 的表)" % a.tag)
    if a.write_spec:
        p = write_spec(a.tag, spec_facts(res))
        print(f"  已寫入 {p} 的 facts[]({len(spec_facts(res))} 筆)")
    print(summary_line(res))
    return 1 if (a.strict and bad_count(res) > 0) else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
