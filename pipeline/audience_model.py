"""觀眾模型統計:把留言彙整成 channel/audience/<頻道>_comments.jsonl 與 <頻道>_stats.md(0 token,來源唯讀)。

用法:python -X utf8 pipeline/audience_model.py --channel <ChannelA|ChannelB|ChannelA|ChannelB|…> [--update]
  預設:由來源重建,寫兩個檔。
  --update:另外保留既有 jsonl 裡「來源檔已消失」的列(同鍵時以新抓的為準、讚數取大);重跑結果相同。
來源(都唯讀,見 channel/_archive/plans/PLAN_流程嚴謹化_2026-10-29.md §3):
  ytad     Youtube AD data/own/comments/*.json(自製片 24h 抓的,own_comments 格式)
  ref_own  projects/*/comments_ref/*.json 中的 own_comments 格式(dict 有 video_id/captured_at)
  ref_info projects/*/comments_ref/*.info.json(yt-dlp --write-comments,競品)
  ref_list projects/*/comments_ref/*.comments.json 的 yt-dlp 純陣列格式(競品)
  channel/選題檢討_證據_2026-10-20/comments_all.md 是摘要表格,讚數與原句混在儲存格敘述裡,無法穩定解析 → 略過。
旗標/軸向:comment_lexicon.json(演算法抄自 Youtube AD backend/comment_flags.py,不 import 那邊)。啟發式,精度未驗證。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

LEXICON = Path(__file__).resolve().parent / "comment_lexicon.json"
TZ8 = timezone(timedelta(hours=8))
OTHER = "其他"
SRC_ORDER = ["ytad", "ref_own", "ref_info", "ref_list"]
SRC_LABEL = {
    "ytad": "自製片 Youtube AD data/own/comments",
    "ref_own": "自製片 comments_ref(own 格式)",
    "ref_info": "競品 comments_ref *.info.json(yt-dlp)",
    "ref_list": "競品 comments_ref *.comments.json(yt-dlp 陣列)",
}
CHANNEL_ALIAS = {"ChannelA": "ChannelA", "ChannelB": "ChannelB"}
TOP_LIKED_N = 50
BIGRAM_N = 50
TEXT_CHARS_TOP = 120
TEXT_CHARS_LIST = 200

# 簡繁視為同一(opencc 有就用,沒有退回小對照表)
try:
    from opencc import OpenCC
    _S2T = OpenCC("s2t").convert
except Exception:  # pragma: no cover
    _MAP = str.maketrans({c: t for c, t in zip(
        "说对错乱讲钱买玩游戏戏视频标题题剧乐样见观点务这个们还没开关实后发现应该认为爱评论头华从质单双变设计识线终组络让给听愿",
        "說對錯亂講錢買玩遊戲戲視頻標題題劇樂樣見觀點務這個們還沒開關實後發現應該認為愛評論頭華從質單雙變設計識線終組絡讓給聽願")})

    def _S2T(s):
        return s.translate(_MAP)

STOP_CHARS = set("的了是我你他她它就也有在這那和與跟都很還要會可以嗎吧啊呢啦哦喔個一們什麼麼說到被把讓為以於但而及或之"
                 "，。！？、：；「」『』（）()[],.!?:;\"' 　\n")
CJK_RUN = re.compile(r"[一-鿿]+")
NARRATION_RE = re.compile(r"旁白|配音|聲音|念稿|唸稿|讀稿|語速|語氣|流暢|機器人|合成音|斷句|發音|ai\s*聲|ai\s*配", re.I)
POS_WORDS = ["讚", "認同", "說得對", "說得好", "說的對", "說的好", "講得對", "講得好", "同意", "支持", "正解",
             "不錯", "好看", "感謝", "謝謝", "加油", "有道理", "推薦", "說得沒錯", "太對", "沒錯"]
NEG_WORDS = ["錯", "亂講", "亂說", "沒玩過", "沒在玩", "雲玩家", "爛", "垃圾", "誤導", "無腦", "胡說", "洗腦",
             "不實", "假的", "ai配音", "ai 配音", "標題黨", "騙"]
NEG_STRIP = ["不錯", "沒錯", "沒說錯", "不會錯", "說得沒錯", "不是錯"]


# ───────────── 旗標(抄 Youtube AD backend/comment_flags.classify) ─────────────
def _compile(words):
    plain, rx = [], []
    for w in words or []:
        if w.startswith("re:"):
            rx.append(re.compile(w[3:], re.IGNORECASE))
        elif w:
            plain.append(w.lower())
    return plain, rx


def _hit(compiled, low):
    plain, rx = compiled
    return any(w in low for w in plain) or any(r.search(low) for r in rx)


def load_lexicon(path: Path = LEXICON) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "order": list(d.get("flag_order") or d["flags"].keys()),
        "flags": {k: _compile(v) for k, v in d["flags"].items()},
        "video": _compile(d.get("video_axis")),
        "game": _compile(d.get("game_axis")),
        "implied": set(d.get("video_implied_flags") or []),
    }


def classify(text: str, lex: dict) -> dict:
    low = (text or "").lower()
    flags = [f for f in lex["order"] if _hit(lex["flags"].get(f, ([], [])), low)]
    game = _hit(lex["game"], low)
    if _hit(lex["video"], low):
        axis = "video"
    elif not game and any(f in lex["implied"] for f in flags):
        axis = "video"
    elif game:
        axis = "game"
    else:
        axis = "unknown"
    return {"flags": flags or [OTHER], "axis": axis}


# ───────────── 解析 ─────────────
def norm_channel(name) -> str:
    n = (name or "").strip()
    return CHANNEL_ALIAS.get(n, n)


def _iso(ts) -> str:
    """字串或 epoch 秒 → +08:00 ISO(秒)。無法解析回傳空字串。"""
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, TZ8).isoformat(timespec="seconds")
        if ts:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ8)
            return dt.astimezone(TZ8).isoformat(timespec="seconds")
    except (ValueError, OSError, OverflowError):
        pass
    return ""


def _like(c) -> int:
    try:
        return int(c.get("like_count") or c.get("like") or 0)
    except (TypeError, ValueError):
        return 0


def _read_json(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def parse_file(path: Path):
    """回傳 dict(kind, video_id, title, channel, captured_at, comments) 或 None。
    kind:own(own_comments dict)/info(yt-dlp info.json)/list(yt-dlp 純陣列)。"""
    path = Path(path)
    d = _read_json(path)
    if d is None:
        return None
    if isinstance(d, list):
        vid = path.name.split(".")[0]
        title = ""
        sib = _read_json(path.with_name(vid + ".info.json"))
        cap = ""
        if isinstance(sib, dict):
            title = sib.get("title") or ""
            cap = _iso(sib.get("epoch"))
        if not cap:
            cap = _iso(path.stat().st_mtime)
        return {"kind": "list", "video_id": vid, "title": title, "channel": "", "captured_at": cap, "comments": d}
    if not isinstance(d, dict) or not isinstance(d.get("comments"), list):
        return None
    if "captured_at" in d and "video_id" in d:
        return {"kind": "own", "video_id": d["video_id"], "title": d.get("title") or "",
                "channel": norm_channel(d.get("channel")), "captured_at": _iso(d.get("captured_at")),
                "comments": d["comments"], "status": d.get("status")}
    if d.get("id"):
        return {"kind": "info", "video_id": d["id"], "title": d.get("title") or d.get("fulltitle") or "",
                "channel": "", "captured_at": _iso(d.get("epoch")) or _iso(path.stat().st_mtime),
                "comments": d["comments"]}
    return None


def _jsonl(p: Path):
    out = []
    try:
        for ln in Path(p).read_text(encoding="utf-8").splitlines():
            if ln.strip():
                out.append(json.loads(ln))
    except (OSError, ValueError):
        pass
    return out


def build_maps(root: Path):
    """tag→頻道、video_id→(tag, 頻道, 切角)。來源優先序:outcomes > spec.json > board.json。"""
    tag_ch, vid_info = {}, {}
    for r in _jsonl(root / "channel" / "outcomes.jsonl"):
        tag, vid, ch = r.get("tag"), r.get("video_id"), norm_channel(r.get("channel"))
        if tag and ch:
            tag_ch[tag] = ch
        if vid:
            vid_info[vid] = {"tag": tag or "", "channel": ch, "angle": r.get("angle") or r.get("title_angle") or ""}
    for sp in sorted((root / "projects").glob("*/spec.json")):
        d = _read_json(sp)
        if not isinstance(d, dict):
            continue
        tag = sp.parent.name
        if d.get("channel"):
            tag_ch.setdefault(tag, norm_channel(d["channel"]))
        if d.get("video_id"):
            vid_info.setdefault(d["video_id"], {"tag": tag, "channel": norm_channel(d.get("channel")), "angle": ""})
    board = _read_json(root / "channel" / "board.json")
    if isinstance(board, dict):
        for tag, v in board.items():
            if isinstance(v, dict) and v.get("channel"):
                tag_ch.setdefault(tag, norm_channel(v["channel"]))
    return tag_ch, vid_info


def gather_sources(root: Path, ytad_dir: Path):
    """列出 (src, tag_or_None, 路徑),順序固定(ytad → ref_own → ref_info → ref_list)。"""
    items = []
    if ytad_dir and Path(ytad_dir).is_dir():
        for p in sorted(Path(ytad_dir).glob("*.json")):
            items.append(("ytad", None, p))
    ref = []
    for p in sorted((root / "projects").glob("*/comments_ref/*.json")):
        if p.name.endswith(".info.json"):
            ref.append(("ref_info", p.parent.parent.name, p))
        elif p.name.endswith(".comments.json"):
            ref.append(("ref_comments", p.parent.parent.name, p))
    items += [i for i in ref if i[0] == "ref_comments"]  # 稍後依格式分 ref_own/ref_list
    items += [i for i in ref if i[0] == "ref_info"]
    return items


def collect(root: Path, ytad_dir: Path, lex: dict, channel: str):
    """掃全部來源 → (rows, stats_meta)。rows 已依 (video_id,作者,前40字) 去重、只留該頻道。"""
    tag_ch, vid_info = build_maps(root)
    parsed = []
    for src, tag, p in gather_sources(root, ytad_dir):
        f = parse_file(p)
        if not f:
            continue
        if src == "ref_comments":
            src = "ref_own" if f["kind"] == "own" else ("ref_list" if f["kind"] == "list" else "ref_info")
        elif src == "ytad" and f["kind"] != "own":
            continue
        parsed.append((src, tag, f))
    # 自製片 video_id → tag(comments_ref 裡的 own 格式檔 tag 以專案資料夾為準)
    for src, tag, f in parsed:
        if src == "ref_own" and f["video_id"] not in vid_info:
            vid_info[f["video_id"]] = {"tag": tag, "channel": f["channel"], "angle": ""}
    parsed.sort(key=lambda x: SRC_ORDER.index(x[0]))
    meta = {"files": Counter(), "parsed": Counter(), "unassigned": 0, "skipped_empty": 0}
    rows = {}
    for src, ref_tag, f in parsed:
        is_own = src in ("ytad", "ref_own")
        if is_own:
            info = vid_info.get(f["video_id"], {})
            tag = info.get("tag") or ref_tag or ""
            ch = f["channel"] or info.get("channel") or tag_ch.get(tag, "")
        else:
            tag = ref_tag or ""
            ch = tag_ch.get(tag, "")
        meta["files"][src] += 1
        if not ch:
            meta["unassigned"] += len(f["comments"])
            continue
        if ch != channel:
            continue
        for c in f["comments"]:
            if not isinstance(c, dict):
                continue
            text = (c.get("text") or "").strip()
            if not text:
                continue
            meta["parsed"][src] += 1
            author = c.get("author") or ""
            key = (f["video_id"], author, text[:40])
            like = _like(c)
            if key in rows:
                rows[key]["like"] = max(rows[key]["like"], like)
                continue
            r = classify(text, lex)
            rows[key] = {"video_id": f["video_id"], "tag": tag, "is_own": is_own, "like": like, "text": text,
                         "flags": r["flags"], "axis": r["axis"], "captured_at": f["captured_at"],
                         "author": author, "title": f["title"], "src": src}
    return list(rows.values()), meta


def row_key(r):
    return (r["video_id"], r.get("author") or "", r["text"][:40])


def merge_existing(new_rows, old_rows):
    """--update:保留來源已消失的舊列;同鍵以新抓為準、讚數取大。"""
    by = {row_key(r): r for r in old_rows}
    for r in new_rows:
        o = by.get(row_key(r))
        if o:
            r = dict(r, like=max(r["like"], o.get("like", 0)))
        by[row_key(r)] = r
    return list(by.values())


def sort_rows(rows):
    return sorted(rows, key=lambda r: (r["video_id"], -r["like"], r.get("author") or "", r["text"]))


# ───────────── 統計 ─────────────
def tnorm(s: str) -> str:
    return _S2T(s).lower()


def bigrams(text: str):
    out = set()
    for run in CJK_RUN.findall(tnorm(text)):
        for i in range(len(run) - 1):
            a, b = run[i], run[i + 1]
            if a in STOP_CHARS or b in STOP_CHARS:
                continue
            out.add(a + b)
    return out


def polarity(text: str) -> str:
    t = tnorm(text)
    for w in NEG_STRIP:
        t = t.replace(w, "")
    pos = any(w in tnorm(text) for w in POS_WORDS)
    neg = any(w in t for w in NEG_WORDS)
    if pos and not neg:
        return "pos"
    if neg and not pos:
        return "neg"
    return "neutral"


def _one_line(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n] + "…"


def _vtitle(r) -> str:
    return (r.get("title") or r["video_id"])[:20]


def render_stats(channel: str, rows: list, meta: dict, lex_flags: list) -> str:
    n = len(rows)
    own = [r for r in rows if r["is_own"]]
    comp = [r for r in rows if not r["is_own"]]
    caps = [r["captured_at"] for r in rows if r["captured_at"]]
    as_of = max(caps, key=lambda s: datetime.fromisoformat(s)) if caps else "無"
    L = [f"# {channel} 觀眾模型統計",
         f"as_of {as_of}｜n={n}(自製片 {len(own)}、競品 {len(comp)})｜來源重建自唯讀留言檔,可重跑;詞表與正負比皆為啟發式,精度未驗證。", ""]
    L.append("## 來源筆數(去重後保留)")
    sc = Counter(r.get("src") for r in rows)
    for s in SRC_ORDER:
        L.append(f"- {SRC_LABEL[s]}:{sc.get(s, 0)} 則(本次解析檔 {meta['files'].get(s, 0)} 個、原始 {meta['parsed'].get(s, 0)} 則)")
    L.append("- `選題檢討_證據_2026-10-20/comments_all.md`:略過(摘要表,讚數與原句混在敘述儲存格,無法穩定解析)")
    if meta.get("unassigned"):
        L.append(f"- 無法歸屬頻道而略過:{meta['unassigned']} 則(tag 不在 outcomes/spec/board)")
    vids = Counter((r["video_id"], r["is_own"]) for r in rows)
    L.append(f"- 影片數:自製 {sum(1 for k in vids if k[1])}、競品 {sum(1 for k in vids if not k[1])}")
    cjk = sum(1 for r in rows if CJK_RUN.search(r["text"]))
    L.append(f"- 含中文字的留言 {cjk} 則({cjk * 100 // max(n, 1)}%);其餘多為英文競品留言,英文不進 bigram")
    L.append("")

    for label, subset in (("全部", rows), ("自製片", own), ("競品", comp)):
        if label != "全部" and not subset:
            continue
        L.append(f"## by_flag({label},n={len(subset)};可複選,佔比=該旗標則數/{len(subset)})")
        c = Counter(f for r in subset for f in r["flags"])
        for f in list(lex_flags) + [OTHER]:
            if c.get(f):
                L.append(f"- {f}:{c[f]}({c[f] * 100 / max(len(subset), 1):.1f}%)")
        ax = Counter(r["axis"] for r in subset)
        L.append(f"- 軸向:對影片 {ax.get('video', 0)}、對遊戲 {ax.get('game', 0)}、不明 {ax.get('unknown', 0)}")
        L.append("")

    for label, subset in (("自製片", own), ("競品", comp)):
        top = sorted(subset, key=lambda r: (-r["like"], r["video_id"], r["text"]))[:TOP_LIKED_N]
        L.append(f"## 讚前 {TOP_LIKED_N}({label}留言;原句≤{TEXT_CHARS_TOP} 字)")
        if not top:
            L.append("(無)")
        for r in top:
            L.append(f"- 讚{r['like']}｜{_vtitle(r)}｜{_one_line(r['text'], TEXT_CHARS_TOP)}")
        L.append("")

    cnt, cnt_own = Counter(), Counter()
    for r in rows:
        for b in bigrams(r["text"]):
            cnt[b] += 1
            if r["is_own"]:
                cnt_own[b] += 1
    L.append(f"## bigram 前 {BIGRAM_N}(中文字 2 連字,簡繁轉繁體合併,去停用字;每則留言同詞只算 1 次)")
    for b, k in sorted(cnt.items(), key=lambda x: (-x[1], x[0]))[:BIGRAM_N]:
        L.append(f"- {b}:{k}(自製片 {cnt_own.get(b, 0)})")
    L.append("")

    L.append("## 按影片切角的讚數加權正負比(僅自製片;啟發式)")
    L.append(f"正向詞:{'、'.join(POS_WORDS[:8])}…;負向詞:{'、'.join(NEG_WORDS[:8])}…(「不錯/沒錯」不算負)。"
             "權重=讚數+1;比=正權重/(正+負權重);同則正負並存算中性。切角取 outcomes.jsonl 的 angle,空則退用 title_angle,仍空為「未標」。")
    ang = defaultdict(lambda: {"vids": set(), "n": 0, "pos": 0, "neg": 0, "pw": 0, "nw": 0})
    for r in own:
        a = ANGLE_OF.get(r["video_id"]) or "未標"
        g = ang[a]
        g["vids"].add(r["video_id"])
        g["n"] += 1
        p = polarity(r["text"])
        if p == "pos":
            g["pos"] += 1
            g["pw"] += r["like"] + 1
        elif p == "neg":
            g["neg"] += 1
            g["nw"] += r["like"] + 1
    L.append("")
    L.append("| 切角 | 片數 | 留言 | 正 | 負 | 加權正負比 |")
    L.append("|---|---|---|---|---|---|")
    for a, g in sorted(ang.items(), key=lambda x: (-x[1]["n"], x[0])):
        tot = g["pw"] + g["nw"]
        ratio = f"{g['pw'] / tot:.2f}" if tot else "—"
        L.append(f"| {a} | {len(g['vids'])} | {g['n']} | {g['pos']} | {g['neg']} | {ratio} |")
    L.append("")

    nar = sorted((r for r in own if NARRATION_RE.search(tnorm(r["text"]))), key=lambda r: (-r["like"], r["text"]))
    L.append(f"## 旁白/配音/AI 配音/流暢 相關原句(自製片全部 {len(nar)} 則;命中關鍵詞,含非抱怨)")
    for r in nar:
        L.append(f"- 讚{r['like']}｜{_vtitle(r)}｜{_one_line(r['text'], TEXT_CHARS_LIST)}")
    if not nar:
        L.append("(無)")
    L.append("")
    err = sorted((r for r in own if "資訊錯誤" in r["flags"]), key=lambda r: (-r["like"], r["text"]))
    L.append(f"## 資訊錯誤 旗標原句(自製片全部 {len(err)} 則)")
    for r in err:
        L.append(f"- 讚{r['like']}｜{_vtitle(r)}｜{_one_line(r['text'], TEXT_CHARS_LIST)}")
    if not err:
        L.append("(無)")
    L.append("")
    return "\n".join(L)


ANGLE_OF: dict = {}


def run(channel: str, update: bool = False, root: Path = None, ytad_dir: Path = None, out_dir: Path = None):
    """主流程;回傳 (rows, meta, jsonl 路徑, stats 路徑)。"""
    root = Path(root or paths.ROOT)
    ytad_dir = Path(ytad_dir) if ytad_dir is not None else paths.ytad_comments_dir()
    out_dir = Path(out_dir or root / "channel" / "audience")
    channel = norm_channel(channel)
    lex = load_lexicon()
    rows, meta = collect(root, ytad_dir, lex, channel)
    jp = out_dir / f"{channel}_comments.jsonl"
    if update:
        rows = merge_existing(rows, [r for r in _jsonl(jp)])
    rows = sort_rows(rows)
    _, vid_info = build_maps(root)
    ANGLE_OF.clear()
    ANGLE_OF.update({v: i["angle"] for v, i in vid_info.items() if i.get("angle")})
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_j = jp.with_name(jp.name + ".tmp")   # 先寫暫存再換名,hook 逾時被砍也不留半截檔
    with open(tmp_j, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")
    sp = out_dir / f"{channel}_stats.md"
    tmp_s = sp.with_name(sp.name + ".tmp")
    tmp_s.write_text(render_stats(channel, rows, meta, lex["order"]), encoding="utf-8", newline="\n")
    os.replace(tmp_j, jp)
    os.replace(tmp_s, sp)
    return rows, meta, jp, sp


# ───────────── 人設狀態 / SessionStart hook(channel/_archive/plans/PLAN_流程嚴謹化_2026-10-29.md §3 閉環) ─────────────
PERSONA_META_RE = re.compile(r"<!--\s*persona_meta:\s*(\{.*?\})\s*-->")
PERSONA_GROW = 0.30        # 自製 n 比人設寫時增 >=30% -> 過期
PERSONA_MAX_DAYS = 90      # 人設檔超過 90 天 -> 過期
PERSONA_ZERO_BASE_N = 200  # 人設寫時自製 n=0:自製 n 達 200 才算過期(人設檔自己寫的重寫門檻)
ANGLE_DAYS = 30            # outcomes 近 30 天的切角代號若人設正文沒提 -> 過期
HOOK_TIMEOUT = 10.0
HOOK_CHANNELS = (("ChannelA", "ChannelA"), ("ChannelB", "ChannelB"))


def _own_n_now(channel: str, out_dir: Path) -> int:
    """現在自製片留言數:優先 stats.md 檔頭「自製片 N」,退而數 jsonl 的 is_own。"""
    sp = out_dir / f"{channel}_stats.md"
    if sp.exists():
        m = re.search(r"自製片\s*(\d+)", "".join(sp.read_text(encoding="utf-8").splitlines(True)[:4]))
        if m:
            return int(m.group(1))
    jp = out_dir / f"{channel}_comments.jsonl"
    if jp.exists():
        return sum(1 for r in _jsonl(jp) if r.get("is_own"))
    return 0


def persona_status(channel: str, root: Path = None, out_dir: Path = None, now: datetime = None) -> dict:
    """人設是否過期。回傳 dict(status 'OK'|'過期', n_now, n_persona, reason)。
    人設檔第 1 行:<!-- persona_meta: {"as_of":"YYYY-MM-DD","n_own":479,"n_all":5653,"angles":["判"]} -->"""
    root = Path(root or paths.ROOT)
    out_dir = Path(out_dir or root / "channel" / "audience")
    channel = norm_channel(channel)
    now = now or datetime.now()
    n_now = _own_n_now(channel, out_dir)
    pp = out_dir / f"{channel}_personas.md"
    if not pp.exists():
        return {"status": "過期", "n_now": n_now, "n_persona": None, "reason": "人設檔不存在"}
    text = pp.read_text(encoding="utf-8").lstrip("\ufeff")
    first = text.splitlines()[0] if text.strip() else ""
    m = PERSONA_META_RE.match(first)
    if not m:
        return {"status": "過期", "n_now": n_now, "n_persona": None,
                "reason": "人設檔第 1 行沒有 persona_meta(視為過期)"}
    try:
        meta = json.loads(m.group(1))
        as_of = datetime.fromisoformat(str(meta["as_of"])[:10])
        n_p = int(meta["n_own"])
    except Exception as e:  # noqa: BLE001
        return {"status": "過期", "n_now": n_now, "n_persona": None, "reason": f"persona_meta 讀不懂({type(e).__name__})"}
    reasons = []
    age = (now.replace(hour=0, minute=0, second=0, microsecond=0) - as_of).days
    if age > PERSONA_MAX_DAYS:
        reasons.append(f"人設已 {age} 天(>{PERSONA_MAX_DAYS})")
    if n_p > 0:
        if n_now >= n_p * (1 + PERSONA_GROW):
            reasons.append(f"自製留言 {n_p}→{n_now}(+{(n_now - n_p) / n_p:.0%})")
    elif n_now >= PERSONA_ZERO_BASE_N:
        reasons.append(f"自製留言 0→{n_now}(≥{PERSONA_ZERO_BASE_N})")
    body = text.split("\n", 1)[1] if "\n" in text else ""
    covered = meta.get("angles")   # 人設寫時已涵蓋的切角代號;沒有此鍵才退回正文比對
    covered = set(map(str, covered)) if isinstance(covered, list) else None
    op = root / "channel" / "outcomes.jsonl"
    cj = out_dir / f"{channel}_comments.jsonl"
    have = {r.get("video_id") for r in _jsonl(cj)} if cj.exists() else set()   # 已有留言的 video_id
    seen, new_angles, pending = set(), [], []
    for r in (_jsonl(op) if op.exists() else []):
        if norm_channel(r.get("channel")) != channel:
            continue
        code = (r.get("angle") or r.get("title_angle") or "").strip()
        try:
            pub = datetime.fromisoformat(str(r.get("published_at"))[:19].replace("Z", ""))
        except Exception:  # noqa: BLE001
            continue
        if not code or not 0 <= (now - pub).days <= ANGLE_DAYS:
            continue
        if code in covered if covered is not None else code in body:
            continue
        if r.get("video_id") in have:        # 該切角的片留言已進模型 -> 人設沒涵蓋 = 過期
            if code not in new_angles:
                new_angles.append(code)
        elif code not in pending:            # 留言還沒抓:不算過期,只提示
            pending.append(code)
    pending = [c for c in pending if c not in new_angles]
    reasons += [f"新切角:{c}" for c in new_angles]
    hint = f"切角 {'、'.join(pending)} 的片尚無留言檔:結案 24h 抓後再更新" if pending else ""
    if n_p == 0 and n_now < PERSONA_ZERO_BASE_N:
        # 人設寫時沒有自製留言、現在也還不到門檻:重寫也沒新資料,狀態用「樣本不足」(不重寫),不叫過期
        return {"status": "樣本不足", "n_now": n_now, "n_persona": n_p, "hint": hint,
                "reason": f"樣本不足(自製留言 {n_now}<{PERSONA_ZERO_BASE_N},不重寫;達 {PERSONA_ZERO_BASE_N} 則才重寫)"}
    return {"status": "過期" if reasons else "OK", "n_now": n_now, "n_persona": n_p, "hint": hint,
            "reason": "、".join(reasons) if reasons else "人設仍有效" + (f";{hint}" if hint else "")}


def _hook_update(channel: str, res: dict):
    try:
        jp = paths.ROOT / "channel" / "audience" / f"{channel}_comments.jsonl"
        old = sum(1 for _ in _jsonl(jp)) if jp.exists() else 0
        rows = run(channel, True)[0]
        res[channel] = (len(rows), len(rows) - old)
    except Exception as e:  # noqa: BLE001
        res[channel] = e


def hook_main(timeout: float = HOOK_TIMEOUT) -> int:
    """SessionStart:兩頻道 --update(總時限 timeout 秒,超時略過)+ 人設狀態,只印 1 行,結束碼 0。"""
    res, ths = {}, []
    t0 = time.time()
    for _, full in HOOK_CHANNELS:
        t = threading.Thread(target=_hook_update, args=(full, res), daemon=True)
        t.start()
        ths.append(t)
    for t in ths:
        t.join(max(0.0, timeout - (time.time() - t0)))
    timed_out = any(t.is_alive() for t in ths)
    parts = []
    for short, full in HOOK_CHANNELS:
        r = res.get(full)
        parts.append(f"{short} n={r[0]}({r[1]:+d})" if isinstance(r, tuple) else f"{short} 更新失敗")
    try:
        ps = [f"{short} {persona_status(full)['status']}" for short, full in HOOK_CHANNELS]
    except Exception as e:  # noqa: BLE001
        ps = [f"狀態失敗({type(e).__name__})"]
    head = f"略過(更新逾時 {timeout:.0f}s)" if timed_out else " ".join(parts)
    print(f"[觀眾] {head};人設 {' '.join(ps)}", flush=True)
    if timed_out:
        os._exit(0)   # 背景緒不等;檔案是暫存+換名寫入,不會留半截
    return 0


def main():
    ap = argparse.ArgumentParser(description="留言彙整成觀眾模型統計(0 token)")
    ap.add_argument("--channel")
    ap.add_argument("--hook", action="store_true", help="SessionStart:兩頻道 --update + 人設狀態,印 1 行,逾時 10 秒略過")
    ap.add_argument("--update", action="store_true", help="保留既有 jsonl 中來源已消失的列(冪等)")
    a = ap.parse_args()
    if a.hook:
        try:
            sys.exit(hook_main())
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"[觀眾] 略過({type(e).__name__}: {e})")
            sys.exit(0)
    if not a.channel:
        ap.error("需要 --channel 或 --hook")
    rows, meta, jp, sp = run(a.channel, a.update)
    sc = Counter(r.get("src") for r in rows)
    print(f"{norm_channel(a.channel)} n={len(rows)}(自製 {sum(1 for r in rows if r['is_own'])}) 來源:"
          + "、".join(f"{s}={sc.get(s, 0)}" for s in SRC_ORDER))
    print(f"→ {jp}\n→ {sp}")


if __name__ == "__main__":
    main()
