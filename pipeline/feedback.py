#!/usr/bin/env python3
r"""發片後數據回饋(P4 回饋閉環):讀 Youtube AD 匯出的 data\own\export\latest.json,每支自製片寫一行 channel\outcomes.jsonl,
再從 outcomes 重寫 channel\scorecard.md。

  python -X utf8 pipeline\feedback.py --due [--export <path>] [--min-age-h 72] [--dry-run]
      對 is_self、未刪除(deleted_at 為空)且 age >= min-age-h 的每支片:特徵 + 成效 -> outcomes.jsonl(以 video_id 覆蓋該行)。
      沒有 projects 資料夾的舊片也入庫(特徵欄 null);有 spec.json / handoff.md 時自動帶入 angle、thumb_plan、note(預失敗)。
      匯出已刪除的片會從 outcomes 清掉(清除前備份到 tmp 資料夾)
  python -X utf8 pipeline\feedback.py --video <id> [--tag <tag>] [--angle A1] [--plan 1]
      單片(同一條路徑,不看 min-age):寫 outcomes 該行、scorecard、有 --tag 且有 spec.json 時把成效寫回 spec 的 result。
      --angle(切角代號)/--plan(封面方案)手動補,不給就沿用 outcomes 該行原值

latest.json 來源:paths.ytad_export_latest()(若有),否則由 paths.trend_db 路徑推導 <YTAD>\data\own\export\latest.json;--export 覆寫。
窗口(48h/72h/7d/latest)取 latest.json 該片 windows 與 latest;缺的欄位一律 null,不估算。欄位表見 pipeline\docs\feedback.md。
結構特徵(hook_type、judge_sec 等):projects\<tag>\structure.json -> build\<tag>\structure.json -> 由 <tag>\script.txt 用 script_structure.analyze 即時算並存回 projects;
都沒有維持 null。既有列的特徵重算:再跑一次 --due(每次都重建並覆蓋該 video_id 的列,手動 angle/thumb_plan/note 沿用)。
retention_30s_pct = 留存曲線在「30 秒 / duration_s * 100」位置線性內插(超出曲線範圍 -> null)。
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402

TPE = timezone(timedelta(hours=8))
WIN_HOURS = {"48h": 48, "72h": 72, "7d": 168}
SC_WINDOWS = ("48h", "7d")                  # scorecard 只顯示匯出實際有的窗口(匯出沒有 72h)
PRIMARY_ORDER = ("72h", "7d", "48h")          # 主要成效窗口:有哪個用哪個(報告用)
PERF_KEYS = ("views", "impressions", "ctr_pct", "avg_view_pct", "subs_net", "browse_pct")
SC_COLS = [("views", "觀看"), ("impressions", "曝光"), ("ctr_pct", "CTR%"), ("avg_view_pct", "均看%"),
           ("browse_pct", "瀏覽%"), ("nonsub_pct", "非訂閱%"), ("subs_net", "訂閱")]
SC_HEAD = ["發布", "頻道", "tag", "video_id", "標題", "切角", "封面", "鉤子", "判斷秒", "標題切角", "A/B"]
SC_HEADER = SC_HEAD + [f"{w}(公開起算) {n}" for w in SC_WINDOWS for _, n in SC_COLS]
SC_NOTE = ("# 成效紀錄 scorecard\n\n"
           "由 `pipeline\\feedback.py` 從 `channel\\outcomes.jsonl` 重寫(每個 video_id 一列;請勿手改本表,改 outcomes 或重跑指令)。"
           "數據取自 Youtube AD 匯出 latest.json;「未到期」= 發布未滿該窗口;「無資料」= 匯出沒有此欄(不估算);"
           "「無快照」= 已滿窗口但匯出沒有該窗口數據。窗口以匯出的 published_at 起算(Youtube AD 2026-10-26 起為實際公開時間;更早登記的片為上傳時間,後端 `own_register.py repair-published --apply` 可修)。\n\n")
LEGACY_NOTE = "\n## 舊格式列(feedback.py 改版前寫入,未併入 outcomes)\n\n"
DUR_BUCKETS = ((300, "<5分"), (480, "5-8分"), (720, "8-12分"))


# ---------------------------------------------------------------- 路徑
def outcomes_path():
    return P.ROOT / "channel" / "outcomes.jsonl"


def scorecard_path():
    return P.ROOT / "channel" / "scorecard.md"


def export_path(override=None):
    if override:
        return Path(override)
    fn = getattr(P, "ytad_export_latest", None)
    if fn:
        return Path(fn())
    return P.trend_db("ChannelA").parent.parent / "own" / "export" / "latest.json"   # <YTAD>\data\trend\trend.db -> <YTAD>\data\own\export


# ---------------------------------------------------------------- 讀檔小工具
def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _dig(d, *keys, depth=3):
    """在 d(dict)裡找第一個出現的 keys 之一(先本層,再往下找 depth 層的 dict);找不到回 None。"""
    if not isinstance(d, dict):
        return None
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    if depth > 0:
        for v in d.values():
            if isinstance(v, dict):
                r = _dig(v, *keys, depth=depth - 1)
                if r is not None:
                    return r
    return None


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _fnum(x, nd=2):
    x = _num(x)
    return None if x is None else round(float(x), nd)


# ---------------------------------------------------------------- 特徵
def duration_bucket(sec):
    if not _num(sec) or sec <= 0:
        return None
    for lim, name in DUR_BUCKETS:
        if sec < lim:
            return name
    return ">12分"


def retention_at(curve, pos):
    """留存曲線 [[位置%, 留存%], ...] 在 pos(%)處線性內插;pos 超出曲線範圍回 None。"""
    pts = sorted({(float(a), float(b)) for a, b in (curve or []) if _num(a) is not None and _num(b) is not None})
    if not pts or pos is None or pos < pts[0][0] or pos > pts[-1][0]:
        return None
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= pos <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (pos - x0) / (x1 - x0)
    return pts[-1][1] if pos == pts[-1][0] else None


def _parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)


def _facts_link_pct(tag):
    d = _read_json(P.BUILD / tag / "facts_check.json")
    v = _dig(d, "facts_link_pct", "link_pct", "link_rate", "linked_pct")
    v = _num(v)
    if v is None:
        return None
    return round(v * 100 if 0 <= v <= 1 else v, 1)


def _proj(tag):
    """projects 下的 <tag> 目錄;tag 空或資料夾不存在回 None(舊片 / 無 tag 的特徵欄一律 null)。"""
    d = P.PROJECTS / tag if tag else None
    return d if d is not None and d.is_dir() else None


def _first_text(pat, text):
    m = re.search(pat, text or "")
    return m.group(1).strip() if m else None


def plan_fields(tag):
    """從 projects 的 <tag> 資料夾自動帶 (angle 切角代號, thumb_plan 封面方案, note 預失敗)。
    angle / thumb_plan:spec.json package 第 1 標題切角 / 第 1 封面方案;沒有再從 handoff.md 撈「切角 X」「方案 N」。
    note:handoff.md(或 brief.md)的「預失敗:…」那行(4_交付發片 §7.3 預失敗對照)。查不到 None。"""
    d = _proj(tag)
    if not d:
        return None, None, None
    pkg = (_read_json(d / "spec.json") or {}).get("package") or {}
    titles, thumbs = pkg.get("titles") or [], pkg.get("thumbs") or pkg.get("covers") or []
    t0 = titles[0] if titles and isinstance(titles[0], dict) else {}
    c0 = thumbs[0] if thumbs and isinstance(thumbs[0], dict) else {}
    texts = []
    for fn in ("handoff.md", "brief.md"):
        try:
            texts.append((d / fn).read_text(encoding="utf-8"))
        except OSError:
            pass
    ho = "\n".join(texts)
    angle = t0.get("angle") or _first_text(r"切角[「 ]*([數反判損引身矛決問獵])", ho)
    plan = c0.get("plan") if c0.get("plan") is not None else _first_text(r"方案 ?(\d)", ho)
    note = _first_text(r"預失敗[::]\s*([^\n]+)", ho)
    return angle, (str(plan) if plan is not None else None), (note[:300] if note else None)


def spec_features(tag):
    spec = (_read_json(_proj(tag) / "spec.json") if _proj(tag) else None) or {}
    pkg = spec.get("package") or {}
    subj = pkg.get("subject")
    subj = subj[0] if isinstance(subj, list) and subj else (subj if isinstance(subj, str) else None)
    titles = pkg.get("titles") or []
    t0 = titles[0] if titles and isinstance(titles[0], dict) else {}
    return {"subject": subj or None, "event_id": spec.get("event_id"), "title_angle": t0.get("angle") or None}


def structure_for(tag):
    r"""結構特徵 dict。順序:projects\<tag>\structure.json -> build\<tag>\structure.json -> 用 script_structure.analyze 即時算
    (<tag>\script.txt 全文 + keep/build 的 timeline.json),算得出來且 projects 有該 tag 資料夾就存回 projects\<tag>\structure.json。
    都沒有(或 script.txt 不存在 / 解析失敗)回 {}。"""
    if not tag:
        return {}
    d = _proj(tag)
    for p in ((d / "structure.json") if d else None, P.BUILD / tag / "structure.json"):
        st = _read_json(p) if p else None
        if isinstance(st, dict) and st:
            return st
    sp = P.ROOT / tag / "script.txt"
    if not sp.is_file():
        return {}
    try:
        import script_structure as SS
        st = SS.analyze(sp.read_text(encoding="utf-8-sig"),
                        [P.ROOT / "keep" / tag / "timeline.json", P.BUILD / tag / "timeline.json"])
    except (SystemExit, Exception):      # 文案格式不合 / 沒有旁白行:特徵維持 null
        return {}
    if d:
        (d / "structure.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    return st


def build_features(v, tag):
    has = _proj(tag) is not None        # 舊片沒有 projects 資料夾:特徵欄 null,只留匯出欄位與成效
    ctx = (_read_json(P.PROJECTS / tag / "context.json") if has else None) or {}
    st = structure_for(tag)
    sf = spec_features(tag)
    blocks = _dig(st, "blocks", "block_count", "n_blocks")
    if isinstance(blocks, list):
        blocks = len(blocks)
    pub = _parse_utc(v["published_at"]).astimezone(TPE) if v.get("published_at") else None
    dur = _num(v.get("duration_s"))
    return {
        "channel": v.get("channel"), "slot": v.get("slot"), "tag": tag, "video_id": v.get("video_id"),
        "title": v.get("title"), "published_at": v.get("published_at"),
        "publish_mode": v.get("publish_mode") or "unknown",
        "duration_s": dur, "duration_bucket": duration_bucket(dur),
        "weekday": pub.weekday() if pub else None, "hour": pub.hour if pub else None,   # 台北時間;weekday 0=週一
        "subject": sf["subject"], "event_id": sf["event_id"] or _dig(ctx, "event_id"),
        "competitor_videos_7d": _num(_dig(ctx, "competitor_videos_7d")),
        "same_event_seq": _num(_dig(ctx, "same_event_seq")),
        "hook_type": _dig(st, "hook_type", "opening_type", "opening"),
        "judge_sec": _num(_dig(st, "judge_sec", "first_judgment_s", "judgment_sec")),
        "blocks": _num(blocks), "chars_per_min": _num(_dig(st, "chars_per_min")),
        "facts_per_min": _num(_dig(st, "facts_per_min")),
        "facts_link_pct": _facts_link_pct(tag) if has else None,
        "title_angle": sf["title_angle"], "thumb_plan": None, "angle": None, "note": None,
    }


# ---------------------------------------------------------------- A/B 測試(匯出 ab 物件,格式見 Youtube AD PLAN_AB測試 §2.2)
AB_MODE_LABEL = {"title": "標題", "thumb": "封面", "both": "合測"}


def cover_log_path():
    return P.ROOT / "channel" / "cover_persona_log.jsonl"


def _persona_entry(tag, plan):
    """cover_persona_log.jsonl 中該 tag + plan 的最後一筆(沒有回 {})。"""
    path = cover_log_path()
    hit = {}
    if not path.exists():
        return hit
    for ln in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("tag") == tag and str(e.get("plan")) == str(plan):
            hit = e
    return hit


def _at(lst, i):
    return lst[i] if isinstance(lst, list) and 0 <= i < len(lst) and isinstance(lst[i], dict) else {}


def _ab_version(ver, mode, tag, spec):
    """單一版本:保留匯出欄位,補 title_angle、thumb_plan 與封面特徵(spec / persona log);查不到一律 null。"""
    pkg = spec.get("package") or {}
    idx = ver.get("idx") if isinstance(ver.get("idx"), int) else None
    titles, covers = pkg.get("titles"), pkg.get("covers")
    t = _at(titles, idx - 1) if idx else {}
    c = _at(covers, idx - 1) if idx else {}
    plan = (1 if mode == "title" else idx)
    title = ver.get("title") or t.get("text")
    subj = pkg.get("subject")
    subj = [x for x in (subj if isinstance(subj, list) else [subj]) if isinstance(x, str) and x]
    pers = _persona_entry(tag, plan) if plan else {}
    return {
        "idx": idx, "title": title, "thumb": ver.get("thumb"), "share_pct": _fnum(ver.get("share_pct")),
        "label": ver.get("label"), "is_current": ver.get("is_current"),
        "title_angle": t.get("angle") or None, "thumb_plan": plan,
        "name_start": (any(title.startswith(x) for x in subj) if title and subj else None),
        "cover_angle": c.get("angle") or t.get("angle") or None,      # 封面切角:spec covers 優先,否則同序標題切角(§3.4 第 N 標題搭方案 N)
        "cover_kind": pers.get("kind"), "cover_gesture": pers.get("gesture"), "cover_color": pers.get("color"),
        "cover_layout": c.get("layout") or c.get("版型") or None,
    }


def build_ab(v, tag):
    """匯出每片的 ab -> outcomes 欄位;缺 ab 鍵(或不是 dict)一律 null。status 照錄(含 stopped:手動停止,winner_idx 為 null)。"""
    ab = v.get("ab")
    if not isinstance(ab, dict):
        return {"ab_mode": None, "ab_status": None, "ab_winner_idx": None, "ab_versions": None}
    spec = (_read_json(P.PROJECTS / tag / "spec.json") if _proj(tag) else None) or {}
    mode = ab.get("mode")
    vers = ab.get("versions")
    vers = [_ab_version(x, mode, tag, spec) for x in vers if isinstance(x, dict)] if isinstance(vers, list) else None
    w = ab.get("winner_idx")
    return {"ab_mode": mode, "ab_status": ab.get("status"), "ab_winner_idx": w if isinstance(w, int) else None,
            "ab_versions": vers}


def ab_cell(row):
    """scorecard 的 A/B 欄。"""
    st, mode = row.get("ab_status"), row.get("ab_mode")
    if st == "winner":
        w = row.get("ab_winner_idx")
        vers = row.get("ab_versions") or []
        cur = next((x for x in vers if x.get("idx") == w or x.get("label") == "winner"), None)
        w = w if w is not None else (cur or {}).get("idx")
        share = (cur or {}).get("share_pct")
        lab = AB_MODE_LABEL.get(mode, "版本")
        return f"{lab}#{w} 勝" + (f" {_fmt(round(share))}%" if share is not None else "") if w is not None else f"{lab} 勝出"
    return {"same": "相同", "inconclusive": "無法判定", "running": "進行中", "stopped": "已停止", "not_set": "未設定"}.get(st, "—")


# ---------------------------------------------------------------- 成效
def _perf_block(src, extra_basis=None):
    out = {k: _fnum(src.get(k)) for k in PERF_KEYS}
    out["basis"] = src.get("basis") or extra_basis
    out["age_hours"] = _fnum(src.get("age_hours"), 1)
    return out


def build_perf(v):
    perf = {}
    wins = v.get("windows") or {}
    for w in WIN_HOURS:
        perf[w] = _perf_block(wins[w]) if isinstance(wins.get(w), dict) else None
    lat = v.get("latest")
    if isinstance(lat, dict):
        perf["latest"] = _perf_block(lat, "latest")      # browse_pct 缺就是 null;SUBSCRIBER 是首頁動態不是訂閱者,不代填
    else:
        perf["latest"] = None
    return perf


def has_data(blk):
    return bool(blk) and any(blk.get(k) is not None for k in PERF_KEYS)


def primary_window(perf):
    return next((w for w in PRIMARY_ORDER if has_data(perf.get(w))), None)


def build_row(v, tag, now=None):
    row = build_features(v, tag)
    row["angle"], row["thumb_plan"], row["note"] = plan_fields(tag)
    row["is_self"] = 1 if v.get("is_self") else 0
    row["age_hours"] = _fnum(v.get("age_hours"), 1)
    perf = build_perf(v)
    row["perf"] = perf
    row["primary_window"] = primary_window(perf)
    curve = v.get("retention") or []
    d = row["duration_s"]
    r30 = retention_at(curve, 30.0 / d * 100) if d else None
    row["retention_30s_pct"] = _fnum(r30)
    row["retention_curve_n"] = len(curve)
    cm = v.get("comments")
    row["comments_flags"] = cm.get("flags") if isinstance(cm, dict) else None
    row.update(build_ab(v, tag))
    row["fetched_at"] = (now or datetime.now()).strftime("%Y-%m-%dT%H:%M:%S")
    return row


# ---------------------------------------------------------------- outcomes 讀寫
def read_outcomes(path=None):
    path = Path(path) if path else outcomes_path()
    rows = {}
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if r.get("video_id"):
                    rows[r["video_id"]] = r
    return rows


def write_outcomes(rows, path=None):
    path = Path(path) if path else outcomes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows.values(), key=lambda r: (r.get("published_at") or "", r["video_id"]))
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ordered), encoding="utf-8")
    return ordered


def merge_row(old, new, angle=None, plan=None):
    """新算的 row 覆蓋舊的;手動欄位(angle、thumb_plan、note)已有舊值就沿用(自動帶入不覆蓋)。"""
    for k in ("angle", "thumb_plan", "note"):
        if old and old.get(k) is not None:       # 舊值(手動補或先前自動帶入)優先於這次自動帶入;--angle/--plan 另行覆蓋
            new[k] = old[k]
    if angle is not None:
        new["angle"] = angle
    if plan is not None:
        new["thumb_plan"] = str(plan)
    return new


# ---------------------------------------------------------------- scorecard
def _esc(s):
    return str(s).replace("|", "/").replace("\n", " ")


def _fmt(v):
    if v is None:
        return "—"
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _cell(row, w, key):
    hours = WIN_HOURS[w]
    age = row.get("age_hours")
    if age is not None and age < hours:
        return "未到期"
    blk = (row.get("perf") or {}).get(w)
    if not has_data(blk):
        return "無快照"
    if key == "nonsub_pct":
        return "無資料"
    return _fmt(blk.get(key))


def sc_line(row):
    head = [(row.get("published_at") or "")[:10], row.get("channel"), row.get("tag"), row["video_id"], row.get("title"),
            row.get("angle"), row.get("thumb_plan"), row.get("hook_type"), row.get("judge_sec"), row.get("title_angle"), ab_cell(row)]
    head = ["—" if h is None else (_fmt(h) if isinstance(h, (int, float)) else h) for h in head]
    cells = head + [_cell(row, w, k) for w in SC_WINDOWS for k, _ in SC_COLS]
    return "| " + " | ".join(_esc(c) for c in cells) + " |"


def _legacy_rows(path, known_ids):
    """既有 scorecard 裡 video_id 不在 outcomes 的列(依所屬表頭分組),原樣保留。"""
    groups, header = {}, None
    if not path.exists():
        return groups
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.startswith("| 發布 |"):
            header = None if "| 鉤子 |" in ln else ln      # 含「鉤子」欄 = feedback.py 由 outcomes 產的表(任一版表頭),不是舊格式,不保留(已刪片因此一併消失)
        elif ln.startswith("|") and not ln.startswith("|---") and header:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) > 3 and cells[3] not in known_ids:
                groups.setdefault(header, []).append(ln)
    return groups


def write_scorecard(rows):
    path = scorecard_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy = _legacy_rows(path, {r["video_id"] for r in rows})
    head_ln = "| " + " | ".join(SC_HEADER) + " |"
    out = [SC_NOTE + head_ln, "|" + "---|" * len(SC_HEADER)] + [sc_line(r) for r in rows]
    if legacy:
        out.append(LEGACY_NOTE.rstrip("\n"))
        for hdr, lines in legacy.items():
            n = len([c for c in hdr.strip().strip("|").split("|")])
            out += ["", hdr, "|" + "---|" * n] + lines
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------- 主流程
def load_export(path):
    d = _read_json(path)
    if not isinstance(d, dict) or not isinstance(d.get("videos"), list):
        sys.exit(f"讀不到 latest.json 或格式不對: {path}")
    return d["videos"]


def collect_rows(videos, min_age_h=72, only_vid=None):
    """回傳 (rows, skipped[(video_id/tag, 原因)])。"""
    rows, skipped = [], []
    for v in videos:
        vid = v.get("video_id")
        if only_vid and vid != only_vid:
            continue
        tag = v.get("tag") or None
        if not v.get("is_self"):
            if only_vid:
                skipped.append((vid, "非自製片(is_self=0)"))
            continue
        if v.get("deleted_at"):
            skipped.append((vid, f"已刪除({v['deleted_at']}),不入庫"))
            continue
        age = _num(v.get("age_hours"))
        if age is None or age < min_age_h:
            skipped.append((vid, f"未滿 {min_age_h}h(age={age})"))
            continue
        rows.append(build_row(v, tag))
    return rows, skipped


def purge_deleted(old, deleted_ids, dry_run=False):
    """把匯出標為已刪除的 video_id 從 outcomes 拿掉;有拿掉且非 dry-run 時先備份舊檔到 tmp。回傳被清掉的 video_id list。"""
    gone = [vid for vid in old if vid in deleted_ids]
    if gone and not dry_run and outcomes_path().exists():
        bak = P.ROOT / "tmp" / f"outcomes_backup_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        bak.parent.mkdir(parents=True, exist_ok=True)
        bak.write_bytes(outcomes_path().read_bytes())
    for vid in gone:
        del old[vid]
    return gone


def apply_rows(new_rows, angle=None, plan=None, dry_run=False, deleted_ids=()):
    old = read_outcomes()
    purge_deleted(old, set(deleted_ids), dry_run)
    for r in new_rows:
        old[r["video_id"]] = merge_row(old.get(r["video_id"]), r, angle, plan)
    if dry_run:
        return sorted(old.values(), key=lambda r: (r.get("published_at") or "", r["video_id"]))
    ordered = write_outcomes(old)
    write_scorecard(ordered)
    return ordered


def write_spec_result(tag, row):
    spec = P.PROJECTS / tag / "spec.json"
    if not spec.exists():
        return None
    d = json.loads(spec.read_text(encoding="utf-8"))
    d["result"] = {k: row.get(k) for k in ("video_id", "published_at", "age_hours", "perf", "primary_window",
                                           "retention_30s_pct", "fetched_at")}
    spec.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return spec


def _summary(r):
    pw = r.get("primary_window")
    b = (r.get("perf") or {}).get(pw) or {}
    return (f"{r.get('channel')}|{r.get('tag')}|{r.get('video_id')}|主窗口 {pw or '無'} 曝光 {_fmt(b.get('impressions'))} "
            f"CTR {_fmt(b.get('ctr_pct'))} 均看 {_fmt(b.get('avg_view_pct'))} 30s留存 {_fmt(r.get('retention_30s_pct'))}")


def main(argv):
    ap = argparse.ArgumentParser(description="發片後成效回饋 -> channel\\outcomes.jsonl 與 scorecard.md")
    ap.add_argument("--due", action="store_true", help="處理 latest.json 內所有已滿 --min-age-h 的自製片")
    ap.add_argument("--video", help="單片模式:YouTube video_id")
    ap.add_argument("--tag", help="單片模式:片名 tag(省略則用匯出的 tag;有 spec.json 就寫回 result)")
    ap.add_argument("--angle", help="切角代號(手動補,單片模式)")
    ap.add_argument("--plan", help="封面方案編號(手動補,單片模式)")
    ap.add_argument("--export", help="latest.json 路徑(預設 YTAD data\\own\\export\\latest.json)")
    ap.add_argument("--min-age-h", type=float, default=72, help="--due 的最小發布時數(預設 72)")
    ap.add_argument("--dry-run", action="store_true", help="只印,不寫檔")
    a = ap.parse_args(argv)
    if a.due == bool(a.video):
        ap.error("請二選一:--due 或 --video <id>")
    if a.video and not re.fullmatch(r"[\w-]{6,20}", a.video):
        sys.exit("video_id 格式不對")
    exp = export_path(a.export)
    videos = load_export(exp)
    if a.video:
        if a.tag:   # 手動給 tag 優先於匯出的 tag
            videos = [dict(v, tag=a.tag) if v.get("video_id") == a.video else v for v in videos]
        rows, skipped = collect_rows(videos, min_age_h=0, only_vid=a.video)
        if not rows:
            sys.exit(f"{a.video} 無法處理: {skipped[0][1] if skipped else '匯出沒有此影片'}")
    else:
        rows, skipped = collect_rows(videos, a.min_age_h)
    deleted = {v.get("video_id") for v in videos if v.get("deleted_at") and v.get("video_id")}
    ordered = apply_rows(rows, a.angle, a.plan, a.dry_run, deleted)
    for r in rows:
        print(_summary(r))
        if a.video and a.tag and not a.dry_run:
            sp = write_spec_result(a.tag, next(x for x in ordered if x["video_id"] == r["video_id"]))
            print(f"spec: {sp if sp else '無 spec,未寫入'}")
    for vid, why in skipped:
        print(f"略過 {vid}: {why}")
    print(f"{'[dry-run] ' if a.dry_run else ''}處理 {len(rows)} 支,略過 {len(skipped)} 支;outcomes 共 {len(ordered)} 行"
          + ("" if a.dry_run else f"\noutcomes: {outcomes_path()}\nscorecard: {scorecard_path()}"))


if __name__ == "__main__":
    main(sys.argv[1:])
