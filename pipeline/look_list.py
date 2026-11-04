r"""畫面優先看清單:把散在記錄檔的畫面警告整理成「時間點 + 原因 + 要看什麼」,寫 output\<tag>\look_<ver>.md。
python -X utf8 pipeline\look_list.py <tag> <ver>        (只讀既有檔,不渲染、不用 GPU)

來源(都是警告,不改任何判定與門檻):
  1. 小件放不下        make_<ver>.log 的 `警告: 小件擺放: …` 與 `[anim_web] kit 警告:…`(log 文字)
  2. 動畫容量量測失敗  make_<ver>.log 的 `警告: 動畫容量…`(log 文字;容量超標是錯誤,會擋渲染,不會到這裡)
  3. 畫面單調          直接呼叫 script_lint.visual_warnings(讀 <tag>/script.json,結構化)
  4. K1/K2 小件比對    make_<ver>.log [visual_check] 區塊的 `警告 K1/K2` 清單(log 文字)
  5. 純色塊 / 閱讀卡 hero 抓失敗   news_lib 截圖時存的 tmp\look_list\flat\<圖>.json、tmp\cards\<名>.json 的 hero_fail(結構化;
     舊圖沒有這兩個檔就收不到,重截或重跑 --check 後才有)
時間:build\<tag>\timeline.json 的 shots(鏡頭起訖)與 lines(句號 → visual_start/visual_end)。
"""
import json
import re
import sys
from pathlib import Path

import paths as P

HINT = {
    "小件放不下": "小件(箭頭/標註/徽章)有沒有蓋到文字或圖表、是否貼邊",
    "動畫容量": "動畫的字級、元素是否過小或超出安全區",
    "畫面單調": "連續同類畫面,看要不要換素材或鏡頭型態",
    "同圖連用": "同一張圖停留太久,看要不要補畫面",
    "小件比對": "畫面表與 script 的小件種類不一致(缺或多),確認哪邊是對的",
    "純色塊": "截圖是不是空白頁、載入中或廣告空框",
    "閱讀卡純文字": "閱讀卡少了 hero 圖,版面是否太空",
}


def fmt_time(sec):
    s = int(max(0, sec))
    return f"{s // 60:02d}:{s % 60:02d}"


def _lines_of(msg):
    """訊息裡的『句N』或『句N-M』→ (a, b);沒有回 (None, None)。"""
    m = re.search(r"句\s*(\d+)(?:\s*[-~–]\s*(\d+))?", msg)
    if not m:
        return None, None
    a = int(m.group(1))
    return a, int(m.group(2) or a)


def raw_from_log(logp):
    """log 文字 → [(a, b, kind, reason)];a/b 為句號(None = 訊息沒帶句號)。"""
    out = []
    if not Path(logp).exists():
        return out
    rows = Path(logp).read_text(encoding="utf-8", errors="replace").splitlines()
    for i, ln in enumerate(rows):
        m = re.search(r"警告: 小件擺放(?:檢查失敗)?: (.*)", ln) or re.search(r"\[anim_web\] kit 警告:(.*)", ln)
        if m:
            a, b = _lines_of(m.group(1))
            out.append((a, b, "小件放不下", m.group(1).strip()))
            continue
        m = re.search(r"警告: (動畫容量.*)", ln)
        if m:
            a, b = _lines_of(m.group(1))
            out.append((a, b, "動畫容量", m.group(1).strip()))
            continue
        m = re.match(r"\s*警告 (K1|K2)\b", ln)
        if m:
            for sub in rows[i + 1:]:
                mm = re.match(r"\s{2,}句(\d+)\(行\d+\) (.*)", sub)
                if not mm:
                    break
                out.append((int(mm.group(1)), int(mm.group(1)), "小件比對", f"{m.group(1)} {mm.group(2).strip()}"))
    return out


def raw_from_lint(tag):
    """script_lint.visual_warnings(結構化)→ [(a, b, kind, reason)]。行號(script.txt)換成句號。"""
    import script_lint as SL
    spoken = SL.spoken_lines(tag)
    vl = SL.visual_lines(tag, spoken)
    if not vl:
        return []
    no2idx = {n: i for i, (n, _) in enumerate(spoken, 1)}
    out = []
    for name, hit, _over in SL.visual_warnings(vl):
        kind = "同圖連用" if "同一張圖" in name else "畫面單調"
        for ln, txt in hit:
            m = re.search(r"至 L(\d+)", txt)
            a = no2idx.get(ln)
            b = no2idx.get(int(m.group(1)), a) if m else a
            out.append((a, b, kind, f"L{ln} {txt}"))
    return out


def raw_from_assets(tag):
    """截圖 / 閱讀卡的結構化警告(news_lib 存的 side 檔),只看這支片 script.json 用到的圖。"""
    f = P.ROOT / tag / "script.json"
    if not f.exists():
        return []
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        js = [ln for sec in d["sections"] for ln in sec["lines"]]
    except (ValueError, KeyError, TypeError):
        return []
    use = {}   # 圖檔名主幹 -> [首句, 末句]
    for i, ln in enumerate(js, 1):
        img = ln.get("img")
        if isinstance(img, str) and img:
            u = use.setdefault(Path(img).stem, [i, i])
            u[1] = i
    cards = {}
    cdir = P.TMP / "cards"
    for cf in cdir.glob("*.json") if cdir.exists() else []:
        try:
            cards[cf.stem] = json.loads(cf.read_text(encoding="utf-8")).get("hero_fail")
        except (ValueError, OSError):
            pass
    out = []
    for stem, (a, b) in use.items():
        ff = P.TMP / "look_list" / "flat" / f"{stem}.json"
        if ff.exists():
            try:
                fl = json.loads(ff.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                fl = {}
            if fl.get("warn"):
                out.append((a, b, "純色塊", f"{stem}: 重點區單色連通區域 {fl.get('frac', 0):.0%}"))
        names = [n for n in cards if stem == n or stem.endswith(n)]
        if names:
            n = max(names, key=len)
            hf = cards[n] or ""
            if hf.startswith("hero 圖抓失敗"):
                out.append((a, b, "閱讀卡純文字", f"{stem}: {hf}"))
    return out


def collect_raw(tag, ver):
    raw = raw_from_log(P.output_dir(tag) / f"make_{ver}.log")
    for fn in (raw_from_lint, raw_from_assets):
        try:
            raw += fn(tag)
        except Exception as e:   # 單一來源失敗不影響其他來源
            raw.append((None, None, "清單來源失敗", f"{fn.__name__}: {type(e).__name__}: {e}"))
    seen, out = set(), []
    for r in raw:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def build_rows(raw, tl):
    """raw → 依時間排序、同一鏡頭合併的列。tl = timeline.json(dict)。
    列:dict(t0, t1, line, line_end, text, kind, reason, hint);沒有句號的警告 t0=t1=None,排最後。"""
    lines = {l["idx"]: l for l in tl.get("lines", [])}
    shots = {s["n"]: s for s in tl.get("shots", [])}
    groups = {}
    for a, b, kind, reason in sorted(raw, key=lambda r: (r[0] is None, r[0] or 0)):   # 穩定排序:同鏡頭的原因依句號
        ln = lines.get(a) if a is not None else None
        if ln is None:
            key, t0, t1 = ("none", kind, reason), None, None
        else:
            sn = (ln.get("shots") or [None])[0]
            if sn in shots:
                key, t0, t1 = ("shot", sn), shots[sn]["start"], shots[sn]["end"]
            else:
                key, t0, t1 = ("line", a), ln["visual_start"], ln["visual_end"]
        g = groups.setdefault(key, dict(t0=t0, t1=t1, a=a, b=b, kinds=[], reasons=[]))
        if a is not None:
            g["a"] = a if g["a"] is None else min(g["a"], a)
            g["b"] = max(g["b"] or a, b or a)
        if kind not in g["kinds"]:
            g["kinds"].append(kind)
        g["reasons"].append(reason)
    rows = []
    for g in groups.values():
        a = g["a"]
        text = lines[a]["text"] if a in lines else ""
        rows.append(dict(t0=g["t0"], t1=g["t1"], line=a, line_end=g["b"], text=text,
                         kind="、".join(g["kinds"]), reason="；".join(g["reasons"]),
                         hint="；".join(HINT.get(k, "") for k in g["kinds"] if HINT.get(k))))
    rows.sort(key=lambda r: (r["t0"] is None, r["t0"] or 0, r["line"] or 0))
    return rows


def collect(tag, ver, tl=None, raw=None):
    if tl is None:
        tl = json.loads((P.build_dir(tag) / "timeline.json").read_text(encoding="utf-8"))
    return build_rows(collect_raw(tag, ver) if raw is None else raw, tl)


def _cell(s):
    return str(s).replace("|", "/").replace("\n", " ")


def render_md(rows, tag, ver):
    out = [f"# {tag} {ver} 畫面優先看清單", ""]
    if not rows:
        return "\n".join(out + ["本版畫面無程式警告。", ""])
    out += [f"程式警告 {len(rows)} 處(同一鏡頭的警告已合併)。只看這些時間點,其餘畫面無程式警告;警告不等於錯誤,看過覺得沒問題就略過。", "",
            "| 時間 | 句號 | 旁白前 20 字 | 原因 | 要看什麼 |", "|---|---|---|---|---|"]
    for r in rows:
        t = f"{fmt_time(r['t0'])}–{fmt_time(r['t1'])}" if r["t0"] is not None else "—"
        ln = "—" if r["line"] is None else (str(r["line"]) if r["line_end"] in (None, r["line"]) else f"{r['line']}-{r['line_end']}")
        out.append(f"| {t} | {ln} | {_cell(r['text'][:20])} | {_cell(r['kind'])}:{_cell(r['reason'])} | {_cell(r['hint'])} |")
    return "\n".join(out) + "\n"


def write_md(rows, path, tag, ver):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_md(rows, tag, ver), encoding="utf-8")
    return p


def run(tag, ver):
    """make_version 用:寫 look_<ver>.md,回傳一行摘要。"""
    rows = collect(tag, ver)
    p = write_md(rows, P.output_dir(tag) / f"look_{ver}.md", tag, ver)
    return f"優先看:{len(rows)} 處({p.name})"


def main():
    if len(sys.argv) != 3:
        sys.exit("用法:look_list.py <tag> <ver>")
    tag, ver = sys.argv[1:]
    rows = collect(tag, ver)
    p = write_md(rows, P.output_dir(tag) / f"look_{ver}.md", tag, ver)
    print(f"優先看:{len(rows)} 處 -> {p}")
    for r in rows[:5]:
        t = f"{fmt_time(r['t0'])}–{fmt_time(r['t1'])}" if r["t0"] is not None else "—"
        print(f"  {t} 句{r['line']} {r['text'][:20]} | {r['kind']}:{r['reason'][:60]}")


if __name__ == "__main__":
    main()
