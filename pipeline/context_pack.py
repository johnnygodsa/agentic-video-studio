#!/usr/bin/env python3
r"""寫稿上下文組裝器:把 Youtube AD 的 writer_brief、參考片與自頻道留言、本頻道舊片成效、spec 的 subject
組成 projects\<tag>\context.md(+ context.json),寫稿前必讀。契約:channel/_archive/plans/PLAN_文案資料驅動_2026-10-26.md §3.5。

  python -X utf8 pipeline/context_pack.py --tag <tag> --channel <ChannelA|ChannelB|ChannelC> [--event <id>]
         [--query "<kw>"] [--no-ytad] [--ytad-timeout 120]

任何來源缺都降級成該段「無資料:<原因>」,不中止;Youtube AD 一律唯讀。說明:docs/context_pack.md。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

try:  # 有 jieba 就用詞重疊分群,沒有就退回字 bigram
    import jieba as _jieba  # type: ignore
except Exception:  # noqa: BLE001
    _jieba = None

CHANNEL_SLOT = {"ChannelA": "main", "ChannelA": "main", "ChannelB": "c", "ChannelB": "c", "ChannelC": "d"}
CHANNEL_NAME = {"ChannelA": "ChannelA", "ChannelB": "ChannelB"}
SECTIONS = ("0 摘要與警示", "1 事件事實與一手來源", "2 需求與競品覆蓋", "3 飽和度", "4 玩家共識候選",
            "5 本頻道可比片與教訓", "6 受眾輪廓", "7 待查疑點與資料缺口", "8 brief 必填欄")
TOP_N = 50          # 每種語言最多取前 N 則分群
PER_VIDEO = 10      # 每支影片先取讚數前 N 則再合併(免得單一熱門片淹掉其他片)
ZH_LIST_ALL = 20    # 中文留言少於此數就全列,不分群
CJK_RATIO = 0.3     # 漢字佔字母類字元 ≥ 此比例 = 中文
MAX_GROUPS = 8      # 最多顯示幾群
JACCARD = 0.3       # 單鏈結門檻
REP_CHARS = 120     # 代表原句上限
OUTCOME_MIN_N = 3   # 舊片少於此數只寫資料不足
LEXICON = Path(__file__).resolve().parent / "comment_lexicon.json"


# ---------- 共用 ----------
def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _c(v, n=300):
    """欄位值轉一行字串(dict/list 用緊湊 JSON),超過 n 字截斷。"""
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n - 1] + "…"


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _dt(s):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def project_dir(tag):
    """專案目錄:素材根的 projects\\<tag>;那裡沒有而 repo 內有就用 repo 的(同 paths.project_file)。"""
    p, q = paths.PROJECTS / tag, paths.REPO / "projects" / tag
    return q if q.is_dir() and not p.is_dir() else p


def outcomes_file():
    return paths.find(Path("channel") / "outcomes.jsonl")


def load_subject(pdir):
    """spec.json(沒有則 spec_pkg.json)的 package.subject 與 topic_class;回 (subject 清單, topic_class, 檔名)。"""
    for name in ("spec.json", "spec_pkg.json"):
        d = _read_json(pdir / name)
        if isinstance(d, dict):
            pkg = d.get("package") or {}
            s = pkg.get("subject") or []
            s = [s] if isinstance(s, str) else [str(x) for x in s if x]
            return s, pkg.get("topic_class"), name
    return [], None, None


# ---------- 來源 A:Youtube AD writer_brief ----------
def _run_cli(cmd, timeout, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout, encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})


def _parse_brief(stdout):
    s = (stdout or "").strip()
    i = s.find("{")
    if i < 0:
        raise ValueError("輸出不是 JSON")
    obj, _ = json.JSONDecoder().raw_decode(s[i:])
    if isinstance(obj, dict) and isinstance(obj.get("doc"), dict):   # BriefResult.to_dict() 外層
        obj = obj["doc"]
    if not isinstance(obj, dict) or not any(k in obj for k in ("event", "demand", "saturation")):
        raise ValueError("JSON 缺 writer_brief 鍵")
    return obj


def fetch_brief(event, slot, query, timeout):
    """跑 intel_query.py brief … --json;回 (doc, None) 或 (None, 原因)。"""
    root = paths.ytad_root()
    script = root / "tools" / "intel_query.py"
    if not script.is_file():
        return None, f"找不到 {script.as_posix()}"
    if not event and not query:
        return None, "沒有 --event,也沒有關鍵字(--query 或 spec subject)"
    cmd = [sys.executable, "-X", "utf8", str(script), "brief", event or "-", "--slot", slot]
    if query:
        cmd += ["--query", query]
    cmd.append("--json")
    try:
        r = _run_cli(cmd, timeout, str(root))
    except subprocess.TimeoutExpired:
        return None, f"逾時 {timeout} 秒"
    except OSError as e:
        return None, f"無法執行({e})"
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:]
        return None, f"結束碼 {r.returncode}" + (f":{tail[0][:200]}" if tail else "")
    try:
        return _parse_brief(r.stdout), None
    except ValueError as e:
        return None, f"輸出解析失敗({e})"


def brief_video_ids(doc):
    """brief 裡出現的影片 id(可比片、最近自製片、競品片若有 video_id)。"""
    doc = doc or {}
    ids = {c.get("video_id") for c in (doc.get("own_history") or {}).get("comparables") or []}
    ids |= {v.get("video_id") for v in (doc.get("demand") or {}).get("top_competitor_videos") or []}
    ids.add(((doc.get("saturation") or {}).get("last_own_video") or {}).get("video_id"))
    return {i for i in ids if i}


# ---------- 來源 B:留言 ----------
def _norm(text):
    return re.sub(r"[\W_]+", "", (text or "").lower())


def _comment(c, vid, ts=None):
    return {"id": str(c.get("id") or ""), "text": " ".join(str(c.get("text") or "").split()),
            "like_count": _int(c.get("like_count")), "author": c.get("author") or "",
            "is_reply": (c.get("parent") or "root") != "root", "videos": {vid}, "ts": ts or c.get("published_at")}


def lang_of(text):
    """語言判定:漢字佔字母類字元 ≥ CJK_RATIO → zh;拉丁字母 ≥ 50% → en;其餘(含無字母)→ other。"""
    alpha = [ch for ch in text or "" if ch.isalpha()]
    if not alpha:
        return "other"
    han = sum(1 for ch in alpha if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf" or "\uf900" <= ch <= "\ufaff")
    if han / len(alpha) >= CJK_RATIO:
        return "zh"
    latin = sum(1 for ch in alpha if ch.isascii())
    return "en" if latin / len(alpha) >= 0.5 else "other"


def _upload_date(d):
    u = str(d.get("upload_date") or "")
    return f"{u[:4]}-{u[4:6]}-{u[6:8]}" if len(u) == 8 and u.isdigit() else (u or None)


def _source_row(d, vid, comments, origin):
    title = str(d.get("title") or "")
    return {"video_id": vid, "title": _clip(" ".join(title.split()), 30), "channel": d.get("channel") or d.get("uploader"),
            "view_count": d.get("view_count"), "comment_count": d.get("comment_count", d.get("n_total")),
            "upload_date": _upload_date(d), "lang": lang_of(title + " " + " ".join(c["text"] for c in comments)),
            "origin": origin}


def collect_comments(pdir, extra_ids=()):
    """讀 comments_ref/*.info.json(yt-dlp)與 ytad_comments_dir()/*.json(§3.3;只取相關影片);附來源影片表。"""
    out = {"ref_files": [], "ytad_files": [], "comments": [], "sources": [], "as_of": None}
    stamps, ref_ids = [], set()
    for f in sorted((pdir / "comments_ref").glob("*.info.json")):
        d = _read_json(f)
        if not isinstance(d, dict):
            continue
        vid = d.get("id") or f.name.split(".")[0]
        ref_ids.add(vid)
        out["ref_files"].append(f.name)
        cs = [_comment(c, vid, c.get("timestamp")) for c in d.get("comments") or []]
        out["comments"] += cs
        out["sources"].append(_source_row(d, vid, cs, "comments_ref"))
        if d.get("epoch"):
            stamps.append(datetime.fromtimestamp(_int(d["epoch"]), timezone.utc))
    want = ref_ids | set(extra_ids)
    cdir = paths.ytad_comments_dir()
    if want and cdir.is_dir():
        for f in sorted(cdir.glob("*.json")):
            if f.stem not in want:
                continue
            d = _read_json(f)
            if not isinstance(d, dict) or (d.get("video_id") or f.stem) not in want:
                continue
            vid = d.get("video_id") or f.stem
            out["ytad_files"].append(f.name)
            cs = [_comment(c, vid) for c in d.get("comments") or []]
            out["comments"] += cs
            out["sources"].append(_source_row(d, vid, cs, "ytad"))
            if _dt(d.get("captured_at")):
                stamps.append(_dt(d["captured_at"]))
    if stamps:
        out["as_of"] = max(stamps).isoformat(timespec="seconds")
    return out


def dedupe(comments):
    """先以 id、再以正規化文字合併(讚數取大、來源影片取聯集);去掉正規化後為空的(純表情)。"""
    def merge(table, key, c):
        o = table.get(key)
        if o is None:
            table[key] = c
        else:
            o["videos"] |= c["videos"]
            if c["like_count"] > o["like_count"]:
                o["like_count"] = c["like_count"]
    by_id, rest = {}, []
    for c in comments:
        if not _norm(c["text"]):
            continue
        if c["id"]:
            merge(by_id, c["id"], dict(c, videos=set(c["videos"])))
        else:
            rest.append(dict(c, videos=set(c["videos"])))
    by_text = {}
    for c in list(by_id.values()) + rest:
        merge(by_text, _norm(c["text"]), c)
    return sorted(by_text.values(), key=lambda c: (-c["like_count"], c["id"]))


def tokens(text):
    """分群用詞集合:jieba 可用時取詞;否則中日韓連續字取字 bigram(單字取本身),英數取整個詞
    (英文若也切 bigram,th/he 之類共用字母對會把無關長句併成一群)。"""
    if _jieba is not None:
        toks = {w for w in (_norm(w) for w in _jieba.lcut(text or "")) if w}
        if toks:
            return toks
    t = (text or "").lower()
    toks = set(re.findall(r"[a-z0-9]+", t))
    for run in re.findall(r"[^\W\da-z_]+", t):
        toks |= {run[i:i + 2] for i in range(len(run) - 1)} if len(run) >= 2 else {run}
    return toks


def token_method():
    return "jieba 詞重疊" if _jieba is not None else "字 bigram"


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def _clip(text, n=REP_CHARS):
    return text if len(text) <= n else text[:n - 1] + "…"


def cluster(top):
    """單鏈結(Jaccard ≥ JACCARD);回 (依合計讚數排序的前 MAX_GROUPS 群, 總群數)。"""
    toks = [tokens(c["text"]) for c in top]
    parent = list(range(len(top)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            if _jaccard(toks[i], toks[j]) >= JACCARD:
                parent[find(j)] = find(i)
    groups = {}
    for i in range(len(top)):
        groups.setdefault(find(i), []).append(top[i])
    out = []
    for ms in groups.values():
        rep = max(ms, key=lambda c: c["like_count"])
        out.append({"rep": _clip(rep["text"]), "likes": sum(c["like_count"] for c in ms), "n": len(ms),
                    "videos": sorted(set().union(*(c["videos"] for c in ms))),
                    "flags": dict(Counter(f for c in ms for f in c.get("flags", [])))})
    out.sort(key=lambda g: (-g["likes"], -g["n"]))
    return out[:MAX_GROUPS], len(out)


def load_lexicon():
    d = _read_json(LEXICON) or {}
    return d.get("flags") or {}, list(d.get("credibility") or [])


def flag_text(text, lex):
    t = (text or "").lower()
    return [f for f, words in lex.items() if any(w.lower() in t for w in words)]


def sample_per_video(comments, k=PER_VIDEO):
    """每支影片各自去重後取讚數前 k 則,再跨片合併去重。"""
    by_vid = {}
    for c in comments:
        by_vid.setdefault(next(iter(c["videos"])), []).append(c)
    return dedupe([c for cs in by_vid.values() for c in dedupe(cs)[:k]])


def _lang_part(full, sampled, cred, list_all_below=None):
    """單一語言:全部則數與旗標計數、取樣後分群(或少量時全列)。"""
    by_flag = Counter(f for c in full for f in c["flags"])
    part = {"n": len(full), "by_flag": dict(by_flag),
            "credibility_total": sum(1 for c in full if set(c["flags"]) & set(cred)),
            "listed_all": bool(list_all_below and 0 < len(full) < list_all_below)}
    if part["listed_all"]:
        part["n_sampled"] = len(full)
        part["items"] = [{"text": _clip(c["text"]), "like_count": c["like_count"], "videos": sorted(c["videos"]),
                          "flags": c["flags"]} for c in full]
        part["groups"], part["n_groups"] = [], 0
    else:
        part["n_sampled"] = len(sampled)
        part["items"] = []
        part["groups"], part["n_groups"] = cluster(sampled[:TOP_N])
    return part


def analyze_comments(raw):
    """全部去重標旗標(計數用);每片取前 PER_VIDEO 則合併後依語言分 zh/en 各自分群;旗標範例只取中文。"""
    lex, cred = load_lexicon()
    merged = dedupe(raw["comments"])
    for c in merged:
        c["flags"] = flag_text(c["text"], lex)
        c["lang"] = lang_of(c["text"])
    flags_by_norm = {_norm(c["text"]): c["flags"] for c in merged}
    sampled = sample_per_video(raw["comments"])
    for c in sampled:
        c["flags"] = flags_by_norm.get(_norm(c["text"]), [])
        c["lang"] = lang_of(c["text"])
    full = {lg: [c for c in merged if c["lang"] == lg] for lg in ("zh", "en")}
    samp = {lg: [c for c in sampled if c["lang"] == lg] for lg in ("zh", "en")}
    zh = _lang_part(full["zh"], samp["zh"], cred, ZH_LIST_ALL)
    zh["flagged_examples"] = {f: [{"text": _clip(c["text"], 80), "like_count": c["like_count"],
                                   "videos": sorted(c["videos"])} for c in full["zh"] if f in c["flags"]][:3]
                              for f in zh["by_flag"]}
    en = _lang_part(full["en"], samp["en"], cred)
    by_flag = Counter(f for c in merged for f in c["flags"])
    return {"ref_files": raw["ref_files"], "ytad_files": raw["ytad_files"], "as_of": raw["as_of"],
            "sources": raw["sources"], "n_raw": len(raw["comments"]), "n_total": len(merged),
            "n_other": len(merged) - zh["n"] - en["n"], "per_video": PER_VIDEO, "method": token_method(),
            "zh": zh, "en": en, "by_flag": dict(by_flag), "credibility_flags": cred,
            "credibility_total": sum(1 for c in merged if set(c["flags"]) & set(cred))}


# ---------- 來源 C:本頻道舊片成效 ----------
def load_outcomes(path):
    if not path.is_file():
        return None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def match_outcomes(rows, tag, subject, topic_class, keywords):
    """同 subject、同 topic_class 或標題/subject 含關鍵字的舊片(排除本片)。"""
    subj = {s.lower() for s in subject}
    kws = [k.lower() for k in keywords if k]
    out = []
    for r in rows or []:
        if r.get("tag") == tag:
            continue
        rs = r.get("subject") or []
        rs = {str(x).lower() for x in ([rs] if isinstance(rs, str) else rs)}
        title = str(r.get("title") or "").lower()
        hit = sorted(subj & rs)
        if hit:
            reason = "同 subject:" + "、".join(hit)
        elif topic_class and r.get("topic_class") == topic_class:
            reason = f"同 topic_class:{topic_class}"
        else:
            k = [k for k in kws if k in title or any(k in s for s in rs)]
            if not k:
                continue
            reason = "關鍵字:" + "、".join(k)
        out.append(dict(r, _reason=reason))
    return out


def _outcome_line(r):
    w = r.get("windows") or {}
    perf = ""
    for key in ("72h", "48h", "7d", "latest"):
        v = w.get(key)
        if isinstance(v, dict):
            parts = [f"{lab} {v[k]}" for k, lab in (("views", "觀看"), ("impressions", "曝光"), ("ctr", "CTR"),
                                                     ("ctr_pct", "CTR%"), ("avg_view_pct", "均看%"),
                                                     ("subs_net", "訂閱")) if v.get(k) is not None]
            perf = f"{key} " + " ".join(parts)
            break
    cells = [r.get("tag") or "?", r.get("title") or "", f"鉤子 {r.get('hook_type') or '?'}",
             f"題材 {r.get('topic_class') or '?'}", perf or "無成效窗口", r["_reason"]]
    return "- " + "|".join(str(x) for x in cells)


# ---------- Markdown 各段 ----------
def _head(src, as_of, n):
    return f"來源:{src}|as_of:{as_of or '不明'}|n:{n}"


def _brief_missing(ctx):
    return ctx["ytad_error"] or "Youtube AD 不可用:未知原因"


def sec_summary(ctx):
    doc, ev = ctx["brief"] or {}, ctx["event"]
    lines = [f"- 專案 {ctx['tag']}|頻道 {ctx['channel']}(slot {ctx['slot']})",
             f"- 事件:{ev.get('id')} {ev.get('name') or ''}".rstrip() if ev.get("id") else
             f"- 事件:未指定(關鍵字 {ctx['query'] or '無'})",
             f"- subject:{'、'.join(ctx['subject']) or '無'}",
             "- Youtube AD:" + (f"可用(brief {doc.get('generated_at') or '?'})" if ctx["brief"] else _brief_missing(ctx))]
    warns = [f"[{f.get('level') or '?'}] {f.get('text') or ''}" for f in doc.get("flags") or [] if isinstance(f, dict)]
    cm = ctx["comments"]
    if cm and cm["credibility_total"]:
        zh, en = cm["zh"], cm["en"]
        parts = "、".join(f"{f} {zh['by_flag'][f]}" for f in cm["credibility_flags"] if zh["by_flag"].get(f)) or "無"
        warns.append(f"留言可信度抱怨 中文 {zh['credibility_total']}/{zh['n']}、英文 {en['credibility_total']}/{en['n']} 則;"
                     f"中文:{parts}(啟發式,見 §4)")
    seq = ctx["same_event_seq"]
    if isinstance(seq, int) and seq >= 3:
        warns.append(f"本片是同事件近 7 天第 {seq} 支;過去同事件第 3–5 支觀看遞減(n=16,弱證據)")
    lines += [f"- 警示:{w}" for w in warns] or ["- 警示:無"]
    return _head("context_pack 彙整", ctx["generated_at"], len(warns)), lines


def sec_event(ctx):
    if not ctx["brief"]:
        return None, _brief_missing(ctx)
    ev = ctx["event"]
    if not ev.get("id") and not ev.get("name"):
        return None, f"無情報事件(關鍵字模式:{ctx['query'] or '無'})"
    links = sorted(ev.get("links") or [], key=lambda l: (l.get("tier") != "official", str(l.get("published_at") or "")))
    lines = [f"- {ev.get('name') or ''}({ev.get('id') or '?'})|類型 {ev.get('type') or '?'}",
             f"- 可信度 {ev.get('confidence') or '?'}|依據 {_c(ev.get('confidence_basis') or {})}",
             f"- first_seen {ev.get('first_seen') or '?'}|最早條目 {ev.get('earliest_item_at') or '?'}"
             f"|最新條目 {ev.get('last_item_at') or '?'}",
             f"- heat {ev.get('heat')}(報導量,不是觀眾需求){'|' + ev['heat_note'] if ev.get('heat_note') else ''}"]
    lines += [f"- 摘要:{s}" for s in ev.get("summary_lines") or []]
    if ev.get("tw_why"):
        lines.append(f"- 台灣為何在意:{ev['tw_why']}")
    lines += [f"- 切角:{a if isinstance(a, str) else _c(a)}" for a in ev.get("angles") or []]
    lines.append("- 來源:" if links else "- 來源:無")
    lines += [f"  - [{l.get('tier') or '?'}] {l.get('title') or ''}|{l.get('published_at') or '?'}"
              f"|{l.get('source') or ''}|{l.get('url') or ''}" for l in links]
    if ev.get("pack_path"):
        lines.append(f"- 事件包:{ev['pack_path']}")
    return _head("Youtube AD writer_brief.event", ctx["brief"].get("generated_at"), len(links)), lines


def sec_demand(ctx):
    if not ctx["brief"]:
        return None, _brief_missing(ctx)
    d = ctx["brief"].get("demand")
    if not d:
        return None, "brief 無 demand"
    vids = d.get("top_competitor_videos") or []
    lines = [f"- 競品影片 近 7 天 {d.get('competitor_videos_7d')}|近 14 天 {d.get('competitor_videos_14d')}"]
    lines += [f"  - {v.get('channel') or ''}|{v.get('title') or ''}|{v.get('published_at') or '?'}"
              f"|views/日 {v.get('views_per_day')}|倍數 {v.get('multiple')}|{v.get('duration_s')} 秒" for v in vids]
    if d.get("bili_top"):
        lines.append(f"- B 站:{_c(d['bili_top'], 400)}")
    if d.get("angle_words"):
        lines.append(f"- 競品標題高頻詞:{_c(d['angle_words'])}")
    if d.get("note"):
        lines.append(f"- 註:{d['note']}")
    return _head("Youtube AD writer_brief.demand", ctx["brief"].get("generated_at"), len(vids)), lines


def sec_saturation(ctx):
    if not ctx["brief"]:
        return None, _brief_missing(ctx)
    s = ctx["brief"].get("saturation")
    if not s:
        return None, "brief 無 saturation"
    last = s.get("last_own_video") or {}
    lines = [f"- 自製 近 7 天 {s.get('own_same_event_7d')}|近 14 天 {s.get('own_same_event_14d')}",
             f"- 搬運 近 7 天 {s.get('own_reposts_same_event_7d')}|姊妹頻道 近 7 天 {s.get('sibling_same_event_7d')}",
             f"- 最近一支:{last.get('video_id')}|{last.get('title') or ''}|{last.get('published_at') or '?'}"
             f"|觀看 {last.get('views_latest')}" if last else "- 最近一支:無"]
    return _head("Youtube AD writer_brief.saturation", ctx["brief"].get("generated_at"), ctx["same_event_7d"]), lines


def _flag_str(flags):
    if isinstance(flags, dict):
        return "、".join(f"{k}×{v}" for k, v in flags.items()) or "無"
    return "、".join(flags) or "無"


def _flag_counts(by_flag):
    return "、".join(f"{f} {n}" for f, n in sorted(by_flag.items(), key=lambda x: -x[1])) or "無"


def _lang_lines(part, label):
    if not part["n"]:
        return [f"- 無{label}留言"]
    if part["listed_all"]:
        lines = [f"- {label}共 {part['n']} 則(<{ZH_LIST_ALL}),全列:"]
        lines += [f"- [讚 {c['like_count']}|影片 {','.join(c['videos'])}|旗標 {_flag_str(c['flags'])}] 「{c['text']}」"
                  for c in part["items"]]
    else:
        lines = [f"- {label}全部 {part['n']} 則;每片前 {PER_VIDEO} 則取樣 {part['n_sampled']} 則,"
                 f"共 {part['n_groups']} 群,列前 {len(part['groups'])} 群"]
        lines += [f"- [讚 {g['likes']}|{g['n']} 則|影片 {','.join(g['videos'])}|旗標 {_flag_str(g['flags'])}] 「{g['rep']}」"
                  for g in part["groups"]]
    lines.append(f"- 旗標({label}全部 {part['n']} 則,啟發式詞表 comment_lexicon.json):{_flag_counts(part['by_flag'])}")
    return lines


def sec_comments(ctx):
    cm = ctx["comments"]
    if not cm or not cm["n_total"]:
        return None, f"projects/{ctx['tag']}/comments_ref 無 *.info.json,Youtube AD 也無對應留言檔"
    src = f"comments_ref {len(cm['ref_files'])} 檔 + Youtube AD 留言 {len(cm['ytad_files'])} 檔"
    lines = [f"- 來源影片 {len(cm['sources'])} 支:"]
    lines += [f"  - {r['video_id']}|{r['title']}|{r['channel'] or '?'}|觀看 {r['view_count']}|留言 {r['comment_count']}"
              f"|上傳 {r['upload_date'] or '?'}|{r['lang']}" for r in cm["sources"]]
    lines.append(f"- 去重後 {cm['n_total']} 則(原始 {cm['n_raw']};中文 {cm['zh']['n']}、英文 {cm['en']['n']}、其他 "
                 f"{cm['n_other']});每支影片先取讚數前 {PER_VIDEO} 則再合併,{cm['method']} Jaccard≥{JACCARD} 單鏈結")
    lines.append("### 4a 中文玩家")
    lines += _lang_lines(cm["zh"], "中文")
    for f in cm["credibility_flags"]:
        for e in cm["zh"]["flagged_examples"].get(f, []):
            lines.append(f"  - {f}|讚 {e['like_count']}|{','.join(e['videos'])}|「{e['text']}」")
    lines.append("### 4b 英文玩家")
    lines += _lang_lines(cm["en"], "英文")
    lines.append("- 以上是候選;人工判讀後才寫進 facts.md「玩家共識(閘門 1)」(中文玩家優先)")
    return _head(src, cm["as_of"], cm["n_total"]), lines


def sec_history(ctx):
    oh = (ctx["brief"] or {}).get("own_history") or {}
    oc = ctx["outcomes"]
    comps = oh.get("comparables") or []
    if not comps and not oh.get("lessons") and not oc["exists"]:
        reason = _brief_missing(ctx) if not ctx["brief"] else "brief 無 own_history"
        return None, f"{reason};channel/outcomes.jsonl 不存在"
    lines = []
    if ctx["brief"]:
        lines.append(f"- Youtube AD 可比片 n={len(comps)}")
        for c in comps:
            md = c.get("retention_max_drop") or {}
            lines.append(f"  - {c.get('video_id')}|{c.get('tag') or ''}|{c.get('title') or ''}|{c.get('published_at') or '?'}"
                         f"|{c.get('publish_mode') or '?'}|{c.get('duration_s')} 秒|觀看 {c.get('views_latest')}"
                         f"|曝光 {c.get('impressions')}|CTR {c.get('ctr_pct')}%|均看 {c.get('avg_view_pct')}%"
                         f"|30 秒留存 {c.get('retention_30s_pct')}%|最大跌點 {md.get('pos_pct')}% −{md.get('drop')}"
                         f"|{c.get('match_reason') or ''}")
        if oh.get("topic_class_stats"):
            lines.append(f"- 題材統計:{_c(oh['topic_class_stats'])}")
        lines += [f"- brief 教訓:{x if isinstance(x, str) else _c(x)}" for x in oh.get("lessons") or []]
    else:
        lines.append(f"- Youtube AD 可比片:無資料({_brief_missing(ctx)})")
    if not oc["exists"]:
        lines.append("- outcomes.jsonl:無資料(檔案不存在)")
    else:
        lines.append(f"- outcomes.jsonl 同題舊片 n={len(oc['matches'])}(共 {oc['n']} 支)")
        lines += ["  " + _outcome_line(r) for r in oc["matches"]]
        if len(oc["matches"]) < OUTCOME_MIN_N:
            lines.append(f"- 教訓:資料不足(n={len(oc['matches'])}<{OUTCOME_MIN_N})")
        else:
            lines.append("- 以上為教訓原料;統計結論看 channel/成效分析.md")
    return _head("Youtube AD own_history + channel/outcomes.jsonl", (ctx["brief"] or {}).get("generated_at"),
                 len(comps) + len(oc["matches"])), lines


def sec_audience(ctx):
    if not ctx["brief"]:
        return None, _brief_missing(ctx)
    a = ctx["brief"].get("audience")
    if not a:
        return None, "brief 無 audience"
    keys = [k for k in a if k not in ("period_days", "as_of")]
    lines = [f"- 期間 {a.get('period_days')} 天"]
    lines += [f"- {k}:{_c(a[k]) if a[k] is not None else '無資料'}" for k in keys]
    return _head("Youtube AD writer_brief.audience", a.get("as_of"), sum(1 for k in keys if a[k] is not None)), lines


def sec_gaps(ctx):
    lines = [f"- 待查:{q if isinstance(q, str) else _c(q)}" for q in ctx["event"].get("open_questions") or []]
    lines += [f"- 缺口:{g}" for g in ctx["gaps"]]
    if not lines:
        return None, "無待查疑點,也無資料缺口"
    return _head("brief.open_questions + context_pack 檢查", ctx["generated_at"], len(lines)), lines


def brief_fields(ctx):
    """§8 四欄(給 brief 直接貼);沒有 brief 回 None。"""
    if not ctx["brief"]:
        return None
    ev, s = ctx["event"], ctx["brief"].get("saturation") or {}
    links = ev.get("links") or []
    official = [l for l in links if l.get("tier") == "official"]
    basis = ev.get("confidence_basis") or {}
    return {"event_id": ev.get("id") or None, "heat": ev.get("heat"), "n_sources": len(links),
            "confidence_basis": basis, "official": bool(official),
            "official_titles": [l.get("title") or l.get("url") for l in official],
            "same_event_7d": ctx["same_event_7d"], "own_same_event_7d": s.get("own_same_event_7d"),
            "own_reposts_same_event_7d": s.get("own_reposts_same_event_7d"),
            "sibling_same_event_7d": s.get("sibling_same_event_7d")}


def sec_brief(ctx):
    bf = ctx["brief_fields"]
    if bf is None:
        return None, _brief_missing(ctx)
    b = bf["confidence_basis"]
    lines = [f"- 事件 ID:{bf['event_id'] or '無(關鍵字模式:' + (ctx['query'] or '') + ')'}",
             f"- heat 與來源數:heat {bf['heat']};來源 {bf['n_sources']} 筆(官方 {_c(b.get('official'))}、"
             f"媒體網域 {_c(b.get('media_domains'))}、社群 {_c(b.get('social'))})(註:heat=報導量,不是觀眾需求)",
             f"- 官方預告:有({len(bf['official_titles'])} 筆,首筆:{bf['official_titles'][0]})" if bf["official"]
             else "- 官方預告:無(event.links 無 tier=official)",
             f"- 同事件近 7 天已發:{bf['same_event_7d']} 支(自製 {bf['own_same_event_7d']} + 搬運 "
             f"{bf['own_reposts_same_event_7d']};姊妹頻道另 {bf['sibling_same_event_7d']})"]
    return _head("Youtube AD writer_brief", ctx["brief"].get("generated_at"), 4), lines


SECTION_FUNCS = (sec_summary, sec_event, sec_demand, sec_saturation, sec_comments, sec_history, sec_audience,
                 sec_gaps, sec_brief)


def render(ctx):
    out = [f"# context:{ctx['tag']}({ctx['channel']},{ctx['generated_at']})", "",
           "寫稿前必讀;由 pipeline/context_pack.py 產生,勿手改(重跑覆蓋)。", ""]
    for title, fn in zip(SECTIONS, SECTION_FUNCS):
        head, body = fn(ctx)
        out.append(f"## {title}")
        out += ([head] + body) if head else [f"無資料:{body}"]
        out.append("")
    return "\n".join(out)


# ---------- 組裝 ----------
def _sum_int(*vals):
    vals = [v for v in vals if isinstance(v, int)]
    return sum(vals) if vals else None


def build(tag, channel, event=None, query=None, use_ytad=True, timeout=120):
    channel = CHANNEL_NAME.get(channel, channel)
    slot = CHANNEL_SLOT[channel]
    pdir = project_dir(tag)
    subject, topic_class, spec_name = load_subject(pdir)
    q = query or (subject[0] if subject else None)
    brief, err = (None, "--no-ytad 略過 Youtube AD") if not use_ytad else fetch_brief(event, slot, q, timeout)
    if use_ytad and err:
        err = f"Youtube AD 不可用:{err}"
    ev = (brief or {}).get("event") or {}
    sat = (brief or {}).get("saturation") or {}
    own7 = sat.get("own_same_event_7d")
    raw = collect_comments(pdir, brief_video_ids(brief))
    comments = analyze_comments(raw) if raw["comments"] else None
    op = outcomes_file()
    rows = load_outcomes(op)
    matches = match_outcomes(rows, tag, subject, topic_class, subject + ([query] if query else []))
    gaps = []
    if err:
        gaps.append(err)
    if not spec_name:
        gaps.append(f"projects/{tag}/spec.json 不存在,沒有 subject 可比對舊片")
    elif not subject:
        gaps.append(f"{spec_name} 無 package.subject")
    if not raw["ref_files"]:
        gaps.append(f"projects/{tag}/comments_ref 無 yt-dlp 留言檔")
    if rows is None:
        gaps.append("channel/outcomes.jsonl 不存在(舊片教訓無資料)")
    if brief:
        gaps += [f"brief.audience.{k} 無資料" for k, v in (brief.get("audience") or {}).items() if v is None]
    ctx = {"tag": tag, "channel": channel, "slot": slot, "query": q, "subject": subject, "generated_at": _now(),
           "brief": brief, "ytad_error": err, "event": ev, "comments": comments,
           "same_event_7d": _sum_int(own7, sat.get("own_reposts_same_event_7d")),
           "same_event_seq": own7 + 1 if isinstance(own7, int) else None,
           "outcomes": {"path": paths.rel(op), "exists": rows is not None, "n": len(rows or []), "matches": matches},
           "gaps": gaps}
    ctx["brief_fields"] = brief_fields(ctx)
    data = {"schema": "context_pack/1", "tag": tag, "channel": channel, "slot": slot,
            "generated_at": ctx["generated_at"], "event_id": ev.get("id") or event or None,
            "competitor_videos_7d": ((brief or {}).get("demand") or {}).get("competitor_videos_7d"),
            "same_event_seq": ctx["same_event_seq"], "subject": subject, "topic_class": topic_class, "query": q,
            "ytad": {"used": use_ytad, "ok": brief is not None, "error": err},
            "brief_fields": ctx["brief_fields"], "comment_sources": raw["sources"],
            "comments_zh_n": (comments or {}).get("zh", {}).get("n", 0),
            "comments_en_n": (comments or {}).get("en", {}).get("n", 0), "comments": comments,
            "outcomes": dict(ctx["outcomes"], matches=[{k: v for k, v in r.items()} for r in matches]),
            "gaps": gaps, "brief": brief}
    return render(ctx), data


def main(argv=None):
    ap = argparse.ArgumentParser(description="寫稿上下文組裝(context.md / context.json)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--channel", required=True, choices=sorted(CHANNEL_SLOT))
    ap.add_argument("--event", help="情報事件 id(可只給結尾 6 字)")
    ap.add_argument("--query", help="關鍵字(沒有情報事件時;預設用 spec subject 第一個)")
    ap.add_argument("--no-ytad", action="store_true", help="不跑 Youtube AD brief")
    ap.add_argument("--ytad-timeout", type=int, default=120)
    a = ap.parse_args(argv)
    md, data = build(a.tag, a.channel, a.event, a.query, not a.no_ytad, a.ytad_timeout)
    pdir = project_dir(a.tag)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "context.md").write_text(md, encoding="utf-8")
    (pdir / "context.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=sorted) + "\n",
                                       encoding="utf-8")
    cm = data["comments"] or {}
    print(f"寫出 {paths.rel(pdir / 'context.md')}、context.json")
    print(f"Youtube AD:{'可用' if data['ytad']['ok'] else data['ytad']['error']}|留言 {cm.get('n_total', 0)} 則"
          f"(可信度抱怨 {cm.get('credibility_total', 0)})|舊片 {len(data['outcomes']['matches'])} 支|缺口 {len(data['gaps'])}")
    return data


if __name__ == "__main__":
    main()
