#!/usr/bin/env python3
r"""留存曲線對句:把觀眾留存曲線的大跌點對回 timeline.json 的句子(research_文案優化 70_留存對句.md 的程式化版本)。

  python -X utf8 pipeline/retention_align.py --tag gow_sales [--timeline <path>] [--curve <json>] [--video-id <id>] [--top 5] [--json]
  python -X utf8 pipeline/retention_align.py --all --curve <70_留存曲線.json>

curve 來源:--curve 指到「{tag: {video_id, points}}」格式檔,或 Youtube AD latest.json(videos[].retention / retention_typical);
都沒給就試 paths.ytad_export_latest()。結果寫 build/<tag>/retention_align.json。細節見 pipeline/docs/retention.md。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402
from script_structure import RE_SENT, classify_hook  # noqa: E402

END_CUT_PCT = 95.0      # 位置超過此值的跌點不算(結尾自然流失)
MIN_GAP = 2             # 入選跌點彼此相隔的點數需 > MIN_GAP
MAX_LINES = 3           # 每個跌點最多列幾句


# ---------- 讀檔 ----------
def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_timeline(tag, explicit=None):
    """--timeline 優先;否則 keep/<tag>/timeline.json,再 build/<tag>/timeline.json。找不到回 None。"""
    if explicit:
        return Path(explicit)
    cands = [P.ROOT / "keep" / tag / "timeline.json", P.REPO / "keep" / tag / "timeline.json",
             P.build_dir(tag) / "timeline.json"]
    return next((c for c in cands if c.is_file()), None)


def _points(raw):
    """[[pos, val], …] → [(float, float)],依位置排序。"""
    return sorted((float(p[0]), float(p[1])) for p in (raw or []) if len(p) >= 2)


def _typical(raw):
    """[[pos, low, high], …] → [(pos, low, high)]。"""
    return sorted((float(p[0]), float(p[1]), float(p[2])) for p in (raw or []) if len(p) >= 3)


def load_curve(tag, curve_path=None, video_id=None):
    """回傳 {video_id, points, typical, source};找不到回 None。"""
    path = Path(curve_path) if curve_path else getattr(P, "ytad_export_latest", lambda: None)()
    if not path or not Path(path).is_file():
        return None
    data = _load(path)
    if isinstance(data, dict) and isinstance(data.get("videos"), list):      # latest.json
        vids = data["videos"]
        v = next((x for x in vids if video_id and x.get("video_id") == video_id), None)
        if v is None:
            v = next((x for x in vids if x.get("tag") == tag and x.get("retention")), None) \
                or next((x for x in vids if x.get("tag") == tag), None)
        if v is None or not v.get("retention"):
            return None
        return {"video_id": v.get("video_id"), "points": _points(v["retention"]),
                "typical": _typical(v.get("retention_typical")), "source": str(path),
                "duration_s": v.get("duration_s")}
    if isinstance(data, dict):                                               # 70_留存曲線.json
        rec = data.get(tag)
        if rec is None and video_id:
            rec = next((r for r in data.values() if isinstance(r, dict) and r.get("video_id") == video_id), None)
        if not rec or not rec.get("points"):
            return None
        return {"video_id": rec.get("video_id"), "points": _points(rec["points"]),
                "typical": _typical(rec.get("typical")), "source": str(path), "duration_s": None}
    return None


# ---------- 計算 ----------
def interp(points, pos):
    """在位置 pos(%)內插留存;超出範圍取端點。"""
    if not points:
        return None
    if pos <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= pos <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (pos - x0) / (x1 - x0)
    return points[-1][1]


def interp_typical(typical, pos):
    """回傳 (low, high) 或 None。"""
    if not typical:
        return None
    lo = interp([(p, l) for p, l, _ in typical], pos)
    hi = interp([(p, h) for p, _, h in typical], pos)
    return lo, hi


def hook_type(tag, lines):
    sf = P.build_dir(tag) / "structure.json"
    if sf.is_file():
        try:
            h = _load(sf).get("hook_type")
            if h:
                return h
        except (OSError, ValueError):
            pass
    sents = [x.strip() for l in lines[:3] for x in RE_SENT.findall(l.get("text", "")) if x.strip()]
    return classify_hook(sents[:3])[0]


def lines_in(lines, a, b):
    """與 [a, b] 秒區間有交集的句子(最多 MAX_LINES 句)。"""
    out = []
    for l in lines:
        s, e = l.get("start"), l.get("end")
        if s is None or e is None:
            continue
        if s < b and e > a:
            out.append({"idx": l.get("idx"), "start": round(s, 1), "end": round(e, 1), "text": l.get("text", "")})
    return out[:MAX_LINES]


def find_drops(points, typical, total, lines, top=5):
    cand = []
    for i in range(len(points) - 1):
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        if x1 > END_CUT_PCT:
            continue
        cand.append((y0 - y1, i))
    cand.sort(key=lambda t: -t[0])
    picked = []
    for d, i in cand:
        if all(abs(i - j) > MIN_GAP for _, j in picked):
            picked.append((d, i))
        if len(picked) >= top:
            break
    picked.sort(key=lambda t: t[1])      # 輸出依時間順序
    drops = []
    for d, i in picked:
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        a, b = x0 / 100 * total, x1 / 100 * total
        rec = {"pos_from": x0, "pos_to": x1, "sec_from": round(a, 1), "sec_to": round(b, 1),
               "ret_from": y0, "ret_to": y1, "drop": round(d, 2), "lines": lines_in(lines, a, b)}
        t = interp_typical(typical, x1)
        if t:
            lo, hi = t
            rec["typical_low"], rec["typical_high"] = round(lo, 2), round(hi, 2)
            rec["vs_typical"] = "低於" if y1 < lo else ("高於" if y1 > hi else "範圍內")
        drops.append(rec)
    return drops


def align(tag, timeline_path, curve, top=5):
    tl = _load(timeline_path)
    total = float(tl.get("total") or 0)
    lines = tl.get("lines") or []
    pts, typ = curve["points"], curve["typical"]
    res = {
        "tag": tag, "video_id": curve.get("video_id"), "total_s": round(total, 1),
        "retention_30s_pct": None if not total else round(interp(pts, 30 / total * 100), 2),
        "retention_50_pct": round(interp(pts, 50), 2),
        "intro_drop": round(pts[0][1] - pts[1][1], 2) if len(pts) > 1 else None,
        "hook_type": hook_type(tag, lines),
        "drops": find_drops(pts, typ, total, lines, top),
    }
    return res


def write_result(tag, res):
    out = P.build_dir(tag) / "retention_align.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# ---------- 輸出 ----------
def _p(x):
    return f"{x:.0f}"


def to_markdown(res):
    h = [f"## {res['tag']}({res['video_id'] or '-'},總長 {res['total_s']:.0f} 秒 = {res['total_s'] / 60:.1f} 分;"
         f"30 秒處留存 {res['retention_30s_pct']}%,50% 處留存 {res['retention_50_pct']}%;"
         f"0→1% 跌 {res['intro_drop']} 點;開場型態 {res['hook_type']})", ""]
    for d in res["drops"]:
        h.append(f"- 位置 {_p(d['pos_from'])}→{_p(d['pos_to'])}% ({_p(d['sec_from'])}–{_p(d['sec_to'])} 秒) "
                 f"跌 {d['drop']:.1f} 點({_p(d['ret_from'])}→{_p(d['ret_to'])}%)"
                 + (f",{d['vs_typical']}同長度典型({d['typical_low']}–{d['typical_high']}%)" if "vs_typical" in d else ""))
        for l in d["lines"]:
            h.append(f"  - 句{l['idx']} [{l['start']:.0f}-{l['end']:.0f}s] {l['text']}")
    return "\n".join(h) + "\n"


def summary_table(results):
    rows = ["| tag | 開場型態 | 0→1% 跌幅 | 30 秒留存 | 最大跌點(秒 / 句) |", "|---|---|---|---|---|"]
    for r in results:
        big = max(r["drops"], key=lambda d: d["drop"]) if r["drops"] else None
        bs = "-" if not big else f"{big['sec_from']:.0f}–{big['sec_to']:.0f}s / 句{'、'.join(str(l['idx']) for l in big['lines']) or '-'}"
        rows.append(f"| {r['tag']} | {r['hook_type']} | {r['intro_drop']} | {r['retention_30s_pct']}% | {bs} |")
    return "\n".join(rows) + "\n"


# ---------- CLI ----------
def run_all(curve_path, top):
    results = []
    seen = set()
    for kd in (P.ROOT / "keep", P.REPO / "keep"):
        if not kd.is_dir():
            continue
        for d in sorted(kd.iterdir()):
            tl = d / "timeline.json"
            if d.name in seen or not tl.is_file():
                continue
            seen.add(d.name)
            curve = load_curve(d.name, curve_path)
            if not curve:
                continue
            res = align(d.name, tl, curve, top)
            write_result(d.name, res)
            results.append(res)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description="留存曲線對句")
    ap.add_argument("--tag")
    ap.add_argument("--timeline")
    ap.add_argument("--curve")
    ap.add_argument("--video-id")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    if a.all:
        results = run_all(a.curve, a.top)
        if a.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(summary_table(results), end="")
        return 0
    if not a.tag:
        ap.error("需要 --tag 或 --all")
    tl = find_timeline(a.tag, a.timeline)
    if not tl or not Path(tl).is_file():
        print(f"找不到 {a.tag} 的 timeline.json(試過 keep/ 與 build/)", file=sys.stderr)
        return 2
    curve = load_curve(a.tag, a.curve, a.video_id)
    if not curve:
        print(f"找不到 {a.tag} 的留存曲線(--curve 檔無此 tag/video-id,或預設 latest.json 不存在)", file=sys.stderr)
        return 3
    res = align(a.tag, tl, curve, a.top)
    out = write_result(a.tag, res)
    print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else to_markdown(res), end="\n" if a.json else "")
    print(f"[寫入 {out}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
