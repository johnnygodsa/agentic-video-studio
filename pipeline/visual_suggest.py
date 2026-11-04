#!/usr/bin/env python3
r"""每句建議畫面(channel/_archive/plans/PLAN_FRAMEWORK.md §3.1 / §3.4)與泛用句比例。

  python -X utf8 pipeline/visual_suggest.py --tag onimusha [--spec <spec.json>]

只讀:script.txt(用 script_txt2json.parse/build_lines)與 projects/<tag>/spec.json(選填,沒有就略過 facts/visual_plan)。
每句兩個欄位:
  實際 = script.txt 欄位(anim / quote / compare / img / shots / card / hl)或 spec.visual_plan 的指定(已定);
         只有 v 影片標籤 = 普通 clip(未定)。
  建議 = 依句子特徵(數字、「」、年份期間、清單、新舊對照、因果、對立、查證表網頁出處)套 §3.1 表。
泛用句 = 建議為 clip、未指定畫面、且 v 標籤屬泛用標籤(GENERIC_TAGS 或 spec.generic_tags)。比例 = 泛用句 ÷ 總句數(目標 <= 10%)。
輸出 40 行內:句數多時只印「未定且建議特殊畫面」與泛用句,其餘計數。
spec_check 匯入 line_visual() 做數字句與疊加檢查。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import spec_check as sc  # noqa: E402

GENERIC_TAGS = {"games", "generic", "gen", "misc", "filler", "fill", "broll", "b-roll", "泛用"}
GENERIC_MAX = 0.10
MAX_LINES = 40

_CN = r"[零〇一二兩三四五六七八九十百千萬億]"
RE_YEAR = re.compile(r"(?:1[89]|20)\d{2}\s*年|[零〇一二]{4}年")
RE_NUMTOK = re.compile(r"\d[\d,\.]*|(?<!第)(?!一[年次天月日場集位名人])" + _CN + r"+[多幾餘]?(?:年|月|日|歲|倍|套|萬|億|公尺|公里|成|人|名|位|場|次|集|天|週|分|秒|小時)")
RE_CMP = re.compile(r"比|倍|相差|差了?|vs|VS|對上|高於|低於|多於|少於|超過|不到|分別|只有|剩")
RE_SPAN = re.compile(r"從.{1,10}(?:到|至)|整整|之間|(?:\d+|" + _CN + r"+)[多幾]?\s*(?:年|個月|週|天)(?:來|之久|以來|空白)|過去.{0,6}年|二十幾年")
RE_LIST = re.compile(r"第[一二三四五六七八九十](?:個|種|點|項|步|是|,|、|,)|一是|二是|三是|分別|幾個(?:問題|原因|理由)|[兩二三四五六七八九]\s*(?:個|種|點|件|項)(?:問題|原因|理由|重點|選擇|方法)|問題[一二三四五]")
RE_COMPARE = re.compile(r"以前.*現在|原本.*(?:現在|後來)|之前.*之後|從.{1,8}變成|相比|比起|對比")
RE_FLOW = re.compile(r"導致|因為.*所以|先.*再.*(?:最後|然後)|一環扣一環")
RE_VERSUS = re.compile(r"一邊.*一邊|另一邊|雙方|對決|站在.{1,6}那一邊")

SPECIAL = ("num", "bars", "timeline", "span", "card", "quote", "compare", "list", "flow", "versus", "screenshot")


def _plan_get(plan, i):
    """visual_plan 的鍵可以是 "3" 或 "3-5"。"""
    if str(i) in plan:
        return plan[str(i)]
    for k, v in plan.items():
        m = re.fullmatch(r"(\d+)-(\d+)", str(k))
        if m and int(m.group(1)) <= i <= int(m.group(2)):
            return v
    return None


def line_visual(ln, plan_entry=None):
    """一句的實際畫面。回傳 dict:
    kind  anim:<type> | quote | compare | shot(截圖/圖片)| clip
    plain True = 只有 v 標籤的普通 clip(沒指定畫面)
    card/hl  該句有卡片 / 紅底線
    overlay  anim 同時帶 v/img/shots/quote/compare(build 以 anim 優先、悄悄忽略素材,視為違規疊加)
    """
    a = ln.get("anim")
    v = ln.get("v")
    has_asset = bool((v and not str(v).startswith("anim:")) or ln.get("img") or ln.get("shots") or ln.get("quote") or ln.get("compare"))
    d = dict(kind="clip", plain=True, card=bool(ln.get("card")), hl=bool(ln.get("hl")), overlay=False, planned=False)
    if isinstance(a, dict):
        d.update(kind="anim:" + str(a.get("type")), plain=False, overlay=has_asset)
    elif ln.get("shots"):
        d.update(kind="clip", plain=False)
    elif ln.get("quote"):
        d.update(kind="quote", plain=False)
    elif ln.get("compare"):
        d.update(kind="compare", plain=False)
    elif ln.get("img"):
        d.update(kind="shot", plain=False)
    if d["card"]:
        d["plain"] = False
    if d["plain"] and plan_entry:
        p = str(plan_entry)
        kind = ("shot" if p.startswith(("screenshot", "img", "shot")) else
                "clip" if p.startswith("clip") else p.split("+")[0])
        d.update(kind=kind, plain=False, planned=True, card=d["card"] or p.startswith("card"))
    return d


def describe(d):
    s = d["kind"] + ("+hl" if d["hl"] and d["kind"] == "shot" else "") + ("+card" if d["card"] else "")
    return s + ("(plan)" if d["planned"] else "")


def feature_suggest(text):
    """只看句子本身,回傳 (建議類型, 理由)。"""
    if sc.RE_QUOTE.search(text):
        return "quote", "「」"
    if sc.has_number(text):
        years = RE_YEAR.findall(text)
        rest = RE_YEAR.sub(" ", text)
        toks = RE_NUMTOK.findall(rest)
        if len(years) >= 2 or (years and re.search(r"從.{0,12}(?:到|至)", text)):
            return "timeline", "年份/期間"
        if RE_SPAN.search(text):
            return "span", "期間"
        if len(toks) >= 3 or (len(toks) >= 2 and RE_CMP.search(rest)):
            return "bars", "多個數字比較"
        if years and not toks:
            return "card", "年份"
        return "num", "單一數字"
    if RE_COMPARE.search(text):
        return "compare", "新舊對照"
    if RE_LIST.search(text):
        return "list", "清單"
    if RE_FLOW.search(text):
        return "flow", "因果"
    if RE_VERSUS.search(text):
        return "versus", "對立"
    return None, ""


def analyse(lines, spec):
    """每句回傳 dict(i, text, act, sug, why, status, generic)。"""
    spec = spec or {}
    plan = spec.get("visual_plan") or {}
    gen = GENERIC_TAGS | set(spec.get("generic_tags") or [])
    web = {}  # 句號 -> 有網頁出處的 fact id
    for f in spec.get("facts", []):
        src = str(f.get("src", ""))
        if src.startswith("http") and not re.search(r"wikipedia|fandom|wiki\.|/wiki/", src):  # 百科頁不是新聞,不建議截圖
            for k in f.get("lines") or []:
                web.setdefault(k, f.get("id"))
    outro = set()
    for s in spec.get("sections", []):
        if s.get("role") == "outro" and isinstance(s.get("lines"), list) and len(s["lines"]) == 2:
            outro.update(range(s["lines"][0], s["lines"][1] + 1))
    rows = []
    for i, ln in enumerate(lines, 1):
        act = line_visual(ln, _plan_get(plan, i))
        sug, why = feature_suggest(ln["text"])
        if sug is None and i in outro:
            sug, why = "list", "結尾問題"
        if sug is None and i in web:
            sug, why = "screenshot", f"fact {web[i]} 網頁出處"
        tag = ln.get("v")
        is_gen = False
        if sug is None:
            sug = "clip"
            is_gen = bool(act["plain"] and tag in gen)
            if is_gen:
                sug = "generic"
        rows.append(dict(i=i, text=ln["text"], act=act, sug=sug, why=why, generic=is_gen, tag=tag,
                         status="未定" if act["plain"] else "已定"))
    return rows


def report(tag, rows, limit=MAX_LINES):
    n = len(rows)
    special_open = [r for r in rows if r["status"] == "未定" and r["sug"] in SPECIAL]
    generic = [r for r in rows if r["generic"]]
    fixed = n - sum(1 for r in rows if r["status"] == "未定")
    out = [f"visual_suggest {tag}: {n} 句"]

    def fmt(r):
        a = describe(r["act"]) if r["status"] == "已定" else f"clip({r['tag']})" if r["tag"] else "clip"
        sug = r["sug"] + (f"[{r['why']}]" if r["why"] else "")
        return f"  句{r['i']:<3}{r['status']} 實際 {a:<16} 建議 {sug:<22} {r['text'][:14]}"

    if n + 4 <= limit:
        show = rows
    else:
        show = sorted({r["i"]: r for r in special_open + generic}.values(), key=lambda r: r["i"])
        out.append(f"  (句數多:只列「未定且建議特殊畫面」{len(special_open)} 句與泛用 {len(generic)} 句)")
    room = limit - len(out) - 3
    for r in show[:room]:
        out.append(fmt(r))
    if len(show) > room:
        out.append(f"  …另 {len(show) - room} 句")
    ratio = len(generic) / n if n else 0
    out.append(f"已定 {fixed} 句(自製 anim/quote {sum(1 for r in rows if r['act']['kind'].startswith(('anim', 'quote')))})、"
               f"未定但建議特殊畫面 {len(special_open)} 句")
    out.append(f"泛用句 {len(generic)}/{n} = {ratio:.0%}(目標 <={GENERIC_MAX:.0%}){'  超標' if ratio > GENERIC_MAX else ''}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--spec", help="spec.json 路徑(預設 projects/<tag>/spec.json,沒有就略過)")
    a = ap.parse_args()
    sp = Path(a.spec) if a.spec else paths.PROJECTS / a.tag / "spec.json"
    spec = json.loads(sp.read_text(encoding="utf-8-sig")) if sp.exists() else {}
    lines = sc.load_lines(a.tag)
    print(report(a.tag, analyse(lines, spec)))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
