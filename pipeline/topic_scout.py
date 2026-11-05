#!/usr/bin/env python3
r"""選題會議資料收集(0 token、唯讀;規格 channel/_archive/plans/PLAN_流程嚴謹化_2026-10-29.md §1.1;說明 pipeline\docs\stats.md「topic_scout」)。

    python -X utf8 pipeline\topic_scout.py --channel <頻道> [--date YYYY-MM-DD] [--out 路徑]
    -> tmp\scout_<頻道>_<日期>.md,並印路徑與各節筆數

章節:人設狀態(audience_model.persona_status)/ a 自製近 14 天(重用 stats.cmd_channel compare)/ b 回推偵測 / c 留言訊號 / d 競品與新聞(子行程)/ e Studio。
每節首行寫資料 as_of;缺資料寫明原因,不拋例外中止。Youtube AD 資料全部唯讀。
"""
import argparse
import json
import statistics
import subprocess
import sys
from datetime import date as _date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audience_model as AM  # noqa: E402
import paths as P  # noqa: E402
import stats as S  # noqa: E402

CANON = {"": "ChannelA", "c": "ChannelB", "d": "ChannelC"}
INTEL_SLOT = {"": "main", "c": "c"}            # intel_query 的 slot 名;d 沒有 -> 子行程會失敗 -> 該節「不可用」
LEXICON = Path(__file__).resolve().parent / "comment_lexicon.json"

BACK_MIN_AGE_DAYS = 7      # 回推:年齡 > 7 天
BACK_RATIO = 3.0           # 最新日 >= 3x 前 7 日逐日中位
BACK_MIN_VIEWS = 100       # 且最新日 >= 100
BASE_DAYS = 7
SLOW_RATIO = 1.5           # 緩升:近 7 日合計 >= 1.5x 前 7 日合計
SLOW_MIN_DAILY = 100       # 且近 7 日日均 >= 100
MIN_BASE_DAYS = 4          # 前段至少要有幾天才判定
NEAR_TOP = 5               # 未命中時列「近 7 日合計升幅」前 N 名(只排名)
COMMENT_VIDEOS = 5
SUBPROC_TIMEOUT = 120
STUDIO_MAX_LINES = 80
REBOUND_PATH = P.ROOT / "channel" / "rebound.json"   # 回溫命中(stats.py --hook 覆寫;選題會議/board 讀;不寫 board.json)
ACT_SLOT = {"": "a", "c": "c"}                       # Y 的 latest_activity_<mv_slot>.json:ChannelA a、ChannelB c
ACT_MIN_VIEWS = 500        # 最新活動:片齡 > 7 天且 views_48h >= max(500, 前 7 日日均 ×2 天 ×3)
ACT_MULT = 3.0


# ---------------------------------------------------------------- 回推:逐日序列
def _d(s):
    return _date.fromisoformat(str(s)[:10])


def daily_series(points):
    """points: [(日期 str, 累計觀看)] -> [(日期, 當日觀看, 是否跨日平均)]。
    同日期取最後一筆;相鄰兩點差分,間隔 g 天則每天 Δ/g(標跨日平均);Δ<0 或日期不遞增的相鄰對略過。"""
    by_day = {}
    for d, v in points:
        if d and isinstance(v, (int, float)) and not isinstance(v, bool):
            by_day[str(d)[:10]] = float(v)
    days = sorted(by_day)
    out = []
    for a, b in zip(days, days[1:]):
        g = (_d(b) - _d(a)).days
        delta = by_day[b] - by_day[a]
        if g <= 0 or delta < 0:
            continue
        for i in range(1, g + 1):
            out.append(((_d(a) + timedelta(days=i)).isoformat(), delta / g, g > 1))
    return out


def detect_pullback(series, prior_week_api=None, ratio=BACK_RATIO, min_views=BACK_MIN_VIEWS, base_days=BASE_DAYS, min_base=MIN_BASE_DAYS,
                    slow_ratio=SLOW_RATIO, slow_min_daily=SLOW_MIN_DAILY):
    """兩條觸發任一成立即 hit:①單日爆量 = 最新日 ≥ ratio× 前 base_days 日逐日中位且 ≥ min_views;
    ②緩升 = 近 7 日合計 ≥ slow_ratio× 前 7 日合計且近 7 日日均 ≥ slow_min_daily。
    前 7 日合計:逐日序列有完整 7 天就用,否則用 prior_week_api(匯出檔 views_7d 在 7 天前的值),都沒有則②不判。
    回傳 dict(hit/types/latest/day/median/ratio/spread/week/prev_week/prev_src/week_ratio/filled/reason)。"""
    if len(series) < min_base + 1:
        return {"hit": False, "types": [], "reason": f"逐日資料不足({len(series)} 天)"}
    day, latest, spread = series[-1]
    prior = [v for _, v, _ in series[-1 - base_days:-1]]
    if len(prior) < min_base:
        return {"hit": False, "types": [], "reason": f"前段資料不足({len(prior)} 天)"}
    med = statistics.median(prior)
    r = (latest / med) if med > 0 else (float("inf") if latest > 0 else 0.0)
    cur = series[-base_days:]
    prv = series[-2 * base_days:-base_days]
    week = sum(v for _, v, _ in cur) if len(cur) == base_days else None
    prev_week, prev_src = None, None
    if week is not None and len(prv) == base_days:
        prev_week, prev_src = sum(v for _, v, _ in prv), "逐日"
    elif week is not None and S.num(prior_week_api):
        prev_week, prev_src = float(prior_week_api), "views_7d"
    wr = (week / prev_week) if prev_week else None
    types = []
    if latest >= min_views and r >= ratio:
        types.append("單日爆量")
    if wr is not None and wr >= slow_ratio and week / base_days >= slow_min_daily:
        types.append("緩升")
    filled = any(sp for _, _, sp in cur) or (prev_src == "逐日" and any(sp for _, _, sp in prv))
    return {"hit": bool(types), "types": types, "day": day, "latest": latest, "median": med, "ratio": r, "spread": spread,
            "week": week, "prev_week": prev_week, "prev_src": prev_src, "week_ratio": wr, "filled": filled, "reason": None}


def load_series(export_dir, slot, upto=None):
    """channel_YYYY-MM-DD.json 日期副本 + channel_latest.json -> {video_id: {"row": 最新列, "points": [(my_daily_last, views_total)]}}。
    my_daily_last 是 API 每日資料的最後一天(比匯出日晚 ~3 天),同一值的多個副本只留最後一份。"""
    d = Path(export_dir)
    files = [p for day, p in S.dated_files(d, S.CHDATED_RE) if upto is None or day <= upto]
    lp = d / "channel_latest.json"
    if lp.is_file():
        files.append(lp)
    out = {}
    for p in files:
        data = S.read_json(p)
        ch = S.channel_of(data, slot)
        for v in (ch or {}).get("videos") or []:
            vid = v.get("video_id")
            if not vid:
                continue
            e = out.setdefault(vid, {"row": v, "points": {}, "v7": {}})
            e["row"] = v
            if v.get("my_daily_last") and S.num(v.get("views_total")) is not None:
                e["points"][str(v["my_daily_last"])[:10]] = v["views_total"]
                if S.num(v.get("views_7d")) is not None:
                    e["v7"][str(v["my_daily_last"])[:10]] = v["views_7d"]
    for e in out.values():
        e["points"] = sorted(e["points"].items())
    return out


def _video_of(latest, vid):
    for v in (latest or {}).get("videos") or []:
        if v.get("video_id") == vid:
            return v
    return None


def _top_sources(latest, vid, n=3):
    for v in (latest or {}).get("videos") or []:
        if v.get("video_id") == vid:
            ts = v.get("traffic_source") or {}
            items = sorted(((k, x) for k, x in ts.items() if S.num(x) is not None), key=lambda kv: -kv[1])[:n]
            return " / ".join(f"{k} {x:.1f}%" for k, x in items) if items else None
    return None


def daily_from_views_daily(vd, upto=None):
    """channel_latest 的 views_daily([[日期, views]],近 35 天)-> [(日期, views, False)];缺的日期補 0;壞資料回 []。"""
    by = {}
    for it in vd or []:
        try:
            d, v = str(it[0])[:10], it[1]
            _d(d)
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if S.num(v) is not None:
            by[d] = float(v)
    if not by:
        return []
    days = sorted(by)
    out, cur = [], _d(days[0])
    while cur <= _d(days[-1]):
        k = cur.isoformat()
        if upto is None or k <= upto:
            out.append((k, by.get(k, 0.0), False))
        cur += timedelta(days=1)
    return out


def max_day_ratio(series, base_days=BASE_DAYS, min_base=MIN_BASE_DAYS):
    """近 base_days 日內,各日 ÷ 其前 base_days 日中位(分母至少 1)的最大值;資料不足回 None。"""
    best = None
    for i in range(max(0, len(series) - base_days), len(series)):
        prior = [v for _, v, _ in series[max(0, i - base_days):i]]
        if len(prior) < min_base:
            continue
        r = series[i][1] / max(statistics.median(prior), 1.0)
        best = r if best is None or r > best else best
    return best


def _series_of(e, upto=None):
    """優先 views_daily,不足(或沒有欄位)退回日期副本差分。回傳 (series, 來源, prior_week_api)。"""
    try:
        sv = daily_from_views_daily(e["row"].get("views_daily"), upto)
    except Exception:  # noqa: BLE001
        sv = []
    if len(sv) >= MIN_BASE_DAYS + 1:
        return sv, "views_daily", None
    sr = daily_series(e["points"])
    prior = e["v7"].get((_d(sr[-1][0]) - timedelta(days=BASE_DAYS)).isoformat()) if sr else None
    return sr, "日期副本", prior


def _hit(vid, row, r, src, series):
    return {"video_id": vid, "title": row.get("title") or "", "kind": "自製" if row.get("is_self") else "搬運", "is_self": bool(row.get("is_self")),
            "tag": row.get("tag"), "published": (row.get("published_at") or "")[:10], "age_days": S.num(row.get("age_days")),
            "source": src, "types": list(r["types"]), "day": r["day"], "latest": r["latest"], "median": r["median"], "ratio": r["ratio"],
            "spread": r["spread"], "week": r["week"], "prev_week": r["prev_week"], "prev_src": r["prev_src"], "week_ratio": r["week_ratio"],
            "filled": r["filled"], "max_day_ratio": max_day_ratio(series), "views_48h": None}


def _entries(channel, fallback):
    """channel(channel_latest 的單一頻道 dict)+ fallback(load_series 結果)-> {vid: {row, points, v7}}。"""
    out = {}
    for v in (channel or {}).get("videos") or []:
        if v.get("video_id"):
            out[v["video_id"]] = {"row": v, "points": [], "v7": {}}
    for vid, e in (fallback or {}).items():
        if vid in out:
            out[vid]["points"], out[vid]["v7"] = e["points"], e["v7"]
        else:
            out[vid] = e
    return out


def _scan(channel, fallback=None, upto=None):
    """回傳 (hits, near, series_map)。年齡 <= 7 天不判;series_map 供最新活動取前 7 日日均。"""
    hits, near, smap = [], [], {}
    for vid, e in _entries(channel, fallback).items():
        row = e["row"]
        if (S.num(row.get("age_days")) or 0) <= BACK_MIN_AGE_DAYS:
            continue
        sr, src, prior_api = _series_of(e, upto)
        smap[vid] = sr
        r = detect_pullback(sr, prior_week_api=prior_api)
        if r.get("latest") is None:
            continue
        (hits if r["hit"] else near).append(_hit(vid, row, r, src, sr))
    return hits, near, smap


def load_activity(export_dir, slot):
    r"""Y 的 data\own\latest_activity_<slot>.json(匯出資料夾的上一層);不存在/壞檔/d 頻道 -> None。"""
    k = ACT_SLOT.get(slot)
    if not k:
        return None
    doc = S.read_json(Path(export_dir).parent / f"latest_activity_{k}.json")
    if isinstance(doc, list):
        doc = {"videos": doc}
    return doc if isinstance(doc, dict) else None


def _pick(d, *keys):
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return None


def _activity_hits(channel, activity, smap, today=None, fallback=None):
    """最新活動命中:片齡 > 7 天且 views_48h >= max(500, 前 7 日日均×2×3)。前 7 日日均取逐日序列最後 7 天(不足 4 天視為 0)。欄位名容錯。"""
    out = []
    today = today or _date.today()
    rows = {vid: e["row"] for vid, e in _entries(channel, fallback).items()}
    doc = activity or {}
    for av in doc.get("videos") or doc.get("items") or []:
        if not isinstance(av, dict):
            continue
        vid = _pick(av, "video_id", "videoId", "id")
        v48 = S.num(_pick(av, "views_48h", "views48h", "views_48"))
        if not vid or v48 is None:
            continue
        row = rows.get(vid) or {}
        age = S.num(row.get("age_days"))
        if age is None and av.get("published_at"):
            try:
                age = (today - datetime.fromisoformat(str(av["published_at"]).replace("Z", "+00:00")).date()).days
            except ValueError:
                age = None
        if age is None or age <= BACK_MIN_AGE_DAYS:
            continue
        tail = [v for _, v, _ in (smap.get(vid) or [])[-BASE_DAYS:]]
        base = sum(tail) / len(tail) if len(tail) >= MIN_BASE_DAYS else 0.0
        need = max(ACT_MIN_VIEWS, base * 2 * ACT_MULT)
        if v48 < need:
            continue
        out.append({"video_id": vid, "title": row.get("title") or av.get("title") or "", "kind": "自製" if row.get("is_self") else "搬運",
                    "is_self": bool(row.get("is_self")), "tag": row.get("tag"), "published": (row.get("published_at") or av.get("published_at") or "")[:10],
                    "age_days": age, "source": "最新活動", "types": ["最新活動"], "day": None, "latest": None, "median": None,
                    "ratio": None, "spread": False, "week": None, "prev_week": None, "prev_src": None, "week_ratio": None, "filled": False,
                    "max_day_ratio": None, "views_48h": v48, "act_ratio": (v48 / (base * 2)) if base > 0 else None, "need_48h": need})
    return out


def detect_rebound(channel, activity=None, fallback=None, upto=None, today=None):
    """舊片回溫偵測核心(stats.py --hook、選題會議共用)。channel = channel_latest 單一頻道 dict;fallback = load_series(日期副本)。
    回傳 hits:video_id/title/kind(自製|搬運)/age_days/week/prev_week/week_ratio/max_day_ratio/source(views_daily|日期副本|最新活動,
    兩者都中以「+」相連)/types…。門檻同 b 節;最新活動見 _activity_hits。"""
    hits, _near, smap = _scan(channel, fallback, upto)
    for a in _activity_hits(channel, activity, smap, today, fallback):
        h = next((x for x in hits if x["video_id"] == a["video_id"]), None)
        if h:
            h["source"] += "+最新活動"
            h["views_48h"], h["act_ratio"] = a["views_48h"], a["act_ratio"]
        else:
            hits.append(a)
    return hits


def _best_mult(h):
    """摘要用倍數 = 實際觸發的那幾條裡最大者:緩升 -> 近 7 日/前 7 日;單日爆量 -> 最新日/前 7 日中位;最新活動 -> 48h/前 7 日 2 日量。"""
    c = []
    if "緩升" in h["types"]:
        c.append(h.get("week_ratio"))
    if "單日爆量" in h["types"]:
        c.append(h.get("ratio"))
    c.append(h.get("act_ratio"))
    c = [x for x in c if x is not None and x != float("inf")]
    return max(c) if c else h.get("max_day_ratio")


def scan_slot(export_dir, slot, upto=None, today=None):
    """讀匯出檔 + 最新活動,回傳該頻道 hits;channel_latest 沒有此頻道回 []。"""
    d = Path(export_dir)
    channel = S.channel_of(S.load_channel(d), slot)
    if not channel:
        return []
    hits = detect_rebound(channel, load_activity(d, slot), load_series(d, slot, upto), upto, today)
    try:   # latest.json 每片的 traffic_7d / traffic_recent(Y 的 XREQ R8);有才帶,沒有照舊
        by = {v.get("video_id"): v for v in (S.load_latest(d) or {}).get("videos") or []}
    except (AttributeError, TypeError):
        by = {}
    for h in hits:
        for k in ("traffic_recent", "traffic_7d"):
            if isinstance((by.get(h["video_id"]) or {}).get(k), dict):
                h[k] = by[h["video_id"]][k]
    return hits


def _clean(o):
    if isinstance(o, float) and (o != o or o in (float("inf"), float("-inf"))):
        return None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


def write_rebound(per_slot, now=None, out=None):
    r"""per_slot: {slot: hits}。覆寫 channel\rebound.json(先寫 .tmp 再換名)。回傳路徑。"""
    out = Path(out or REBOUND_PATH)
    hits = [dict(h, channel=CANON.get(sl, sl), slot=sl) for sl, hs in per_slot.items() for h in hs]
    doc = {"generated_at": (now or datetime.now()).isoformat(timespec="seconds"), "hits": hits}
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(_clean(doc), ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(out)
    return out


def hook_line(export_dir, now=None, out=None):
    """stats.py --hook 的 [回溫] 行;同時覆寫 rebound.json(寫檔失敗只略過)。例外交給呼叫端轉警告。"""
    now = now or datetime.now()
    per = {sl: scan_slot(export_dir, sl, today=now.date()) for sl in ("", "c")}
    try:
        write_rebound(per, now, out)
    except OSError:
        pass
    if not any(per.values()):
        return "[回溫] 無"

    def part(label, hs):
        hs = sorted(hs, key=lambda h: -(_best_mult(h) or 0))
        names = ",".join(h["title"][:12] + ("" if _best_mult(h) is None else f" ×{_best_mult(h):.1f}") for h in hs[:3])
        return f"{label} {len(hs)} 支" + (f"({names}{'…' if len(hs) > 3 else ''})" if hs else "")
    return "[回溫] " + " ".join(part(lb, per[sl]) for lb, sl in (("ChannelA", ""), ("ChannelB", "c")))


def section_b(export_dir, slot, latest, upto=None):
    """回推偵測;回傳 (lines, n_hit)。"""
    series = load_series(export_dir, slot, upto)
    if not series:
        return ["不可用:channel 日期副本與 channel_latest.json 都沒有此頻道影片"], 0
    channel = {"videos": [e["row"] for e in series.values()]}
    n_vd = sum(1 for e in series.values() if e["row"].get("views_daily"))
    last_days = sorted({p[-1][0] for p in (e["points"] for e in series.values()) if p})
    lines = [f"逐日資料:{len(series)} 支、my_daily_last 到 {last_days[-1] if last_days else '-'}(優先用 channel_latest 的 views_daily,目前 {n_vd} 支有;"
             f"沒有的退回日期副本 views_total 相鄰差分,跨多日的差值按天平均補值,列尾註「含補值」)",
             f"門檻(年齡 > {BACK_MIN_AGE_DAYS} 天,兩條任一成立):①單日爆量 = 最新日 ≥ {BACK_RATIO:g}× 前 {BASE_DAYS} 日逐日中位且 ≥ {BACK_MIN_VIEWS}"
             f"(前段 ≥ {MIN_BASE_DAYS} 天才判);②緩升 = 近 7 日合計 ≥ {SLOW_RATIO:g}× 前 7 日合計且近 7 日日均 ≥ {SLOW_MIN_DAILY}"
             f"(前 7 日合計:逐日滿 7 天用逐日,否則用匯出檔 views_7d 在 7 天前的值)"]
    hits, near, smap = _scan(channel, series, upto)
    activity = load_activity(export_dir, slot)
    lines.append(f"最新活動檔:{'captured_at ' + str(activity.get('captured_at')) if activity else '無(Y 尚未提供或此頻道沒有)'};"
                 f"門檻 片齡 > {BACK_MIN_AGE_DAYS} 天且 views_48h ≥ max({ACT_MIN_VIEWS}, 前 7 日日均×2×{ACT_MULT:g})")

    def fmt(h):
        kind = "自製" if h["is_self"] else "非自製"
        src = _top_sources(latest, h["video_id"]) if h["is_self"] else None
        wk = (f"近7日合計 {S.fv(h['week'])} / 前7日合計 {S.fv(h['prev_week'])}[{h['prev_src']}] = {h['week_ratio']:.2f}×"
              if h.get("week_ratio") else "近7日/前7日合計:資料不足")
        typ = "/".join(h["types"]) if h["types"] else "未觸發"
        return (f"  {h['video_id']} [{kind}] 觸發類型:{typ} tag={h.get('tag') or '-'} 發布 {h['published']} {h['title'][:30]}\n"
                f"    最新日 {h['day']}{'(均)' if h['spread'] else ''} 觀看 {S.fv(h['latest'])} / 前{BASE_DAYS}日中位 {S.fv(h['median'])} = "
                f"{'∞' if h['ratio'] == float('inf') else format(h['ratio'], '.2f')}×;{wk}{'  含補值' if h['filled'] else ''}  [資料:{h['source']}]\n"
                f"    流量來源前3:{src or '無來源資料'}" + "".join("\n  " + t for t in S.traffic_lines(_video_of(latest, h["video_id"]))))

    acts = _activity_hits(channel, activity, smap, _d(upto) if upto else None, series)
    act_ids = {a["video_id"] for a in acts}
    lines.append(f"回推命中 {len(hits)} 支:")
    if hits:
        for h in sorted(hits, key=lambda x: -(x["week_ratio"] or 0)):
            lines.append(fmt(h) + ("\n    另被最新活動命中" if h["video_id"] in act_ids else ""))
    else:
        lines.append("  (無)")
    hit_ids = {h["video_id"] for h in hits}
    extra = [a for a in acts if a["video_id"] not in hit_ids]
    if extra:
        lines.append(f"最新活動命中 {len(extra)} 支(逐日資料未達門檻,但 48h 量大):")
        for a in extra:
            lines.append(f"  {a['video_id']} [{'自製' if a['is_self'] else '非自製'}] 48h {S.fv(a['views_48h'])}(門檻 {S.fv(a['need_48h'])})"
                         f" tag={a.get('tag') or '-'} 發布 {a['published']} {a['title'][:30]}")
    cand = [x for x in near if x.get("week_ratio")]
    cand.sort(key=lambda x: -x["week_ratio"])
    if cand:
        lines.append(f"未達門檻、近 7 日合計升幅前 {NEAR_TOP}(只排名,不是回推;最新日 ≥ {BACK_MIN_VIEWS} 才列):")
        shown = 0
        for h in cand:
            if h["latest"] < BACK_MIN_VIEWS:
                continue
            lines.append(fmt(h))
            shown += 1
            if shown >= NEAR_TOP:
                break
    return lines, len(hits) + len(extra)


# ---------------------------------------------------------------- 留言
def _lexicon_counts(texts):
    try:
        lex = json.loads(LEXICON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for flag, words in (lex.get("flags") or {}).items():
        ws = [w.lower() for w in words]
        n = sum(1 for t in texts if any(w in t.lower() for w in ws))
        if n:
            out[flag] = n
    return out


def comment_summary(doc):
    """回傳 (by_flag dict, ai_n, 來源說明, top5 list[(讚, 原句)], n)。summary 缺 by_flag 時用 comment_lexicon.json 比對。"""
    comments = [c for c in (doc.get("comments") or []) if isinstance(c, dict) and c.get("text")]
    summ = doc.get("summary") or {}
    if isinstance(summ.get("by_flag"), dict):
        by_flag, src = summ["by_flag"], "summary"
    else:
        by_flag, src = _lexicon_counts([c["text"] for c in comments]), "comment_lexicon.json"
    top = sorted(comments, key=lambda c: -(S.num(c.get("like_count")) or 0))[:5]
    top5 = [(S.num(c.get("like_count")) or 0, " ".join(str(c["text"]).split())[:80]) for c in top]
    return by_flag, by_flag.get("AI", 0), src, top5, len(comments)


def section_c(latest, slot, comments_dir):
    """近 5 支自製片留言訊號;回傳 (lines, 支數)。"""
    vids = [v for v in S.self_videos(latest, slot) if v.get("published_at")]
    vids.sort(key=lambda v: v.get("published_at") or "", reverse=True)
    lines, shown, missing, caps = [], 0, [], []
    for v in vids[:COMMENT_VIDEOS + 4]:
        if shown >= COMMENT_VIDEOS:
            break
        doc = S.read_json(Path(comments_dir) / f"{v['video_id']}.json")
        name = v.get("tag") or v["video_id"]
        if not doc:
            missing.append(name)
            continue
        shown += 1
        caps.append(str(doc.get("captured_at") or ""))
        by_flag, ai_n, src, top5, n = comment_summary(doc)
        flags = " ".join(f"{k}{x}" for k, x in by_flag.items() if x) or "(無)"
        lines.append(f"{name} ({v['video_id']}) 留言 {n} 則(status {doc.get('status')}) | by_flag[{src}]:{flags} | 旁白/配音抱怨(AI旗標){ai_n}")
        for likes, text in top5:
            lines.append(f"  讚{int(likes)} {text}")
    head = f"留言檔 captured_at {min(caps)[:16]} ~ {max(caps)[:16]}" if caps else "留言檔:找不到任何近期自製片的留言檔"
    if missing:
        head += f" | 無留言檔:{','.join(missing)}"
    if not vids:
        head = "latest.json 沒有此頻道自製片,無法挑近 5 支"
    return [head] + lines, shown


# ---------------------------------------------------------------- 子行程 / Studio
def run_cmd(cmd, cwd=None, timeout=SUBPROC_TIMEOUT):
    """跑子行程;回傳 (ok, 輸出文字或一行錯誤)。"""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"逾時 {timeout}s"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    if r.returncode != 0:
        tail = [x for x in (r.stderr or r.stdout or "").splitlines() if x.strip()]
        return False, f"結束碼 {r.returncode}:{tail[-1].strip()[:200] if tail else '無輸出'}"
    return True, r.stdout


def key_lines(text, n):
    out = [x.rstrip() for x in text.splitlines() if x.strip() and not x.lstrip().startswith(">")]
    return out[:n]


def section_d(slot, runner=run_cmd):
    """競品與新聞;回傳 (lines, 行數)。runner 可替換(測試)。"""
    root = P.ytad_root()
    lines = [f"子行程即時查詢 {datetime.now():%Y-%m-%d %H:%M}(Youtube AD 資料庫現況,各取前 N 行)"]
    jobs = [("競品機會(intel_query opportunities,前 10 行)", [sys.executable, "-X", "utf8", str(root / "tools" / "intel_query.py"),
                                                          "opportunities", "--slot", INTEL_SLOT.get(slot, slot or "main"), "--limit", "10"], 10),
            ("新聞爆量詞(trend_emerging --top 10,含表頭 12 行)", [sys.executable, "-X", "utf8", str(root / "backend" / "trend_emerging.py"),
                                                           "--slot", slot, "--top", "10"], 12)]
    n = 0
    for label, cmd, cap in jobs:
        lines.append(f"[{label}]")
        if slot not in INTEL_SLOT and "intel_query" in cmd[3]:
            ok, out = False, f"此頻道 slot '{slot}' 沒有 intel_query 設定"
        else:
            ok, out = runner(cmd, cwd=str(root))
        if ok:
            ks = key_lines(out, cap)
            lines += [f"  {x}" for x in ks] or ["  (無輸出)"]
            n += len(ks)
        else:
            lines.append(f"  不可用:{out}")
    return lines, n


def section_e(date_s, tmp_dir=None):
    f = Path(tmp_dir or P.TMP) / f"studio_{date_s}.txt"
    if not f.is_file():
        return ["未讀 Studio(手動:Chrome 讀 tab-research 與即時 48h)"], 0
    raw = f.read_text(encoding="utf-8", errors="replace").splitlines()
    shown = raw[:STUDIO_MAX_LINES]
    lines = [f"{f.name} 修改時間 {datetime.fromtimestamp(f.stat().st_mtime):%Y-%m-%d %H:%M}(共 {len(raw)} 行)"] + shown
    if len(raw) > STUDIO_MAX_LINES:
        lines.append(f"…(超過 {STUDIO_MAX_LINES} 行,餘 {len(raw) - STUDIO_MAX_LINES} 行略,見原檔)")
    return lines, len(shown)


# ---------------------------------------------------------------- 組裝
def _safe(fn, *a):
    """章節不得中止整份:例外 -> (['不可用:…'], 0)。"""
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001
        return [f"不可用:{type(e).__name__}: {e}"], 0


def section_persona(name, status_fn=None):
    """人設狀態(選題會議前置):過期時提醒先重寫人設再派 topic-critic。"""
    st = (status_fn or AM.persona_status)(name)
    lines = [f"{name}:{st['status']}(自製留言 現在 {st['n_now']}/人設寫時 {st['n_persona'] if st['n_persona'] is not None else '未知'};{st['reason']})"]
    if st["status"] == "過期":
        lines.append(f"人設過期({st['reason']}):選題會議前先重寫 channel\\audience\\{name}_personas.md,再派 topic-critic")
    if st["status"] == "樣本不足":
        lines.append("人設為競品推測(樣本不足,不重寫):topic-critic 老觀眾席與 player-review 第一行註明「樣本不足」")
    return lines, 1 if st["status"] == "過期" else 0


def _section_a(latest, chdata, slot, now):
    lines = S.cmd_channel(latest, chdata, slot, now, None, compare=True)
    return lines, len(lines)


def build(slot, date_s, export_dir=None, comments_dir=None, tmp_dir=None, runner=run_cmd, now=None):
    """回傳 (markdown 文字, {章節: 筆數})。"""
    d = S.export_dir(export_dir)
    latest, chdata = S.load_latest(d), S.load_channel(d)
    name = CANON.get(slot, slot)
    now = now or datetime.fromisoformat(f"{date_s}T23:59:00")
    cdir = comments_dir or P.ytad_comments_dir()
    gen = (latest or {}).get("generated_at") or "找不到 latest.json"
    chgen = (chdata or {}).get("generated_at") or "找不到 channel_latest.json"

    pl, npl = _safe(section_persona, name)
    a, na = _safe(_section_a, latest, chdata, slot, now)
    b, nb = _safe(section_b, d, slot, latest, date_s)
    c, nc = _safe(section_c, latest, slot, cdir)
    dd, nd = _safe(section_d, slot, runner)
    e, ne = _safe(section_e, date_s, tmp_dir)
    asof = {"p": "channel\\audience\\<頻道>_personas.md 第 1 行 persona_meta + _stats.md + outcomes.jsonl",
            "a": f"latest.json generated_at {gen} | channel_latest.json generated_at {chgen}",
            "b": f"channel 日期副本 + channel_latest.json(generated_at {chgen})",
            "c": f"latest.json generated_at {gen}(挑自製片)+ 留言檔",
            "d": "子行程即時輸出", "e": f"tmp\\studio_{date_s}.txt"}
    out = [f"# 選題會議資料:{name} {date_s}", f"(topic_scout.py 產出,唯讀;規格 channel/_archive/plans/PLAN_流程嚴謹化_2026-10-29.md §1.1)", ""]
    for key, title, body in (("p", "人設狀態", pl), ("a", "a. 自製近 14 天(= stats.py --compare)", a), ("b", "b. 回推偵測(舊片被演算法重新推)", b),
                             ("c", f"c. 留言訊號(近 {COMMENT_VIDEOS} 支自製片)", c), ("d", "d. 競品與新聞", dd), ("e", "e. Studio 研究分頁與即時 48h", e)):
        out += [f"## {title}", f"資料 as_of:{asof[key]}", "```text", *body, "```", ""]
    return "\n".join(out), {"人設(過期=1)": npl, "a": na, "b(回推命中)": nb, "c(支)": nc, "d": nd, "e": ne}


def main(argv=None):
    ap = argparse.ArgumentParser(description="選題會議資料收集(唯讀、0 token)")
    ap.add_argument("--channel", required=True, help="ChannelA / ChannelB / ChannelC(或簡稱)")
    ap.add_argument("--date", help="YYYY-MM-DD,預設今天(檔名、Studio 檔、日期副本截止)")
    ap.add_argument("--out", help="輸出路徑,預設 tmp\\scout_<頻道>_<日期>.md")
    ap.add_argument("--export-dir", help="覆寫 Youtube AD 匯出資料夾(測試用)")
    ap.add_argument("--comments-dir", help="覆寫留言檔資料夾(測試用)")
    args = ap.parse_args(argv)
    slot = S.resolve_slot(args.channel)
    if slot is None:
        sys.exit(f"不認得頻道 {args.channel};認得:{'/'.join(S.SLOT_ALIAS)}")
    date_s = args.date or datetime.now().strftime("%Y-%m-%d")
    text, counts = build(slot, date_s, args.export_dir, args.comments_dir)
    out = Path(args.out) if args.out else P.TMP / f"scout_{CANON[slot]}_{date_s}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(out)
    print(" | ".join(f"{k} {v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
