#!/usr/bin/env python3
r"""自製片數據一站式查看(D3,取代直接開 own.db):只讀 Youtube AD 匯出檔,不開 DB、不自己算窗口。

  python -X utf8 pipeline\stats.py                          總覽(<=60 行)
  python -X utf8 pipeline\stats.py --tag <tag|video_id>     單片
  python -X utf8 pipeline\stats.py --stale                  只印異常(非當天、缺快照、健康警示、窗口無快照)
  python -X utf8 pipeline\stats.py --channel ChannelA        頻道自製/非自製基準 + 近期片
  python -X utf8 pipeline\stats.py --channel ChannelA --compare   自製 vs 頻道基準 vs 競品(規劃新片用)
  python -X utf8 pipeline\stats.py --channel ChannelA --rivals 10 競品熱門前 N
  python -X utf8 pipeline\stats.py --review <tag>           單片逐日曲線 + 窗口值 + 對基準位置 + 計畫 vs 結果
  python -X utf8 pipeline\stats.py --review --channel ChannelB --days 28   頻道期間內自製片檢討表
  加 --ensure-fresh:先確認數據是當天(後端沒開就 run.bat autostart,缺快照就 POST /api/own/refresh,最多等 20 分鐘);失敗不擋,標「非當天」
  --hook:SessionStart 用,5 秒內結束、4 行內(第 4 行 [回溫],同時覆寫 channel\rebound.json)、錯誤只警告

匯出檔:paths.ytad_export_dir()(latest.json、YYYY-MM-DD.json、channel_latest.json、channel_YYYY-MM-DD.json);--export-dir 覆寫。
後端網址同 yt_queue(YT_QUEUE_URL,預設 http://127.0.0.1:8000)。規格見 pipeline\docs\stats.md。
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402

LINE_CAP = 60
HOOK_CAP = 4        # --hook 行數上限:資料時間 / 當天與否 / 刷新狀態 / [回溫]
SLOT_ALIAS = {"ChannelA": "", "ChannelA": "", "ChannelB": "c", "ChannelB": "c",
              "ChannelC": "d", "ChannelC": "d", "ChannelC": "d"}
SLOT_NAME = {"": "ChannelA", "c": "ChannelB", "d": "ChannelC"}
POLL_S = 30
WAIT_REFRESH_S = 20 * 60
WAIT_BACKEND_S = 120
DATED_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")
CHDATED_RE = re.compile(r"^channel_(\d{4}-\d{2}-\d{2})\.json$")

_sleep = time.sleep      # 測試可替換
_now = datetime.now


# ---------------------------------------------------------------- 讀檔
def export_dir(override=None):
    return Path(override) if override else P.ytad_export_dir()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_latest(d):
    return read_json(Path(d) / "latest.json")


def load_channel(d):
    return read_json(Path(d) / "channel_latest.json")


def resolve_slot(name):
    """頻道名/簡稱 -> slot;不認得回 None。"""
    if name is None:
        return None
    return SLOT_ALIAS.get(str(name).strip())


# ---------------------------------------------------------------- 後端
def base_url():
    import yt_queue
    return yt_queue.base_url()


def http(method, endpoint, timeout=3.0):
    """回傳 (dict|None, 錯誤文字|None)。連不上/非 JSON/HTTP 錯誤 -> (None, 原因)。"""
    req = urllib.request.Request(base_url() + endpoint, data=b"" if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return None, f"{type(e).__name__}: {e}"


def freshness(timeout=3.0):
    return http("GET", "/api/own/freshness", timeout)


def launch_backend():
    """背景執行 Youtube AD 的 run.bat autostart(8000 已有人就自己結束)。不等待。回傳 (ok, 訊息)。"""
    bat = P.yt_ad_root() / "run.bat"
    if not bat.is_file():
        return False, f"找不到 {bat}"
    try:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW  # 不可加 DETACHED_PROCESS:會讓 CREATE_NO_WINDOW 失效,孫行程各跳一個 cmd 視窗
        subprocess.Popen(["cmd.exe", "/c", str(bat), "autostart"], cwd=str(bat.parent), creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        return True, "已背景啟動 run.bat autostart"
    except OSError as e:
        return False, f"啟動失敗 {e}"


def spawn_bg_refresh():
    """背景行程 POST /api/own/refresh(同步重寫匯出檔可能數秒,hook 不等)。"""
    try:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW  # 不可加 DETACHED_PROCESS:會讓 CREATE_NO_WINDOW 失效,孫行程各跳一個 cmd 視窗
        subprocess.Popen([sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--bg-refresh"], creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        return True
    except OSError:
        return False


def ensure_fresh(log=print):
    """回傳 (fresh:bool, note:str)。任何失敗都不擋:note 說明原因。"""
    fr, err = freshness()
    if fr is None:
        ok, msg = launch_backend()
        log(f"後端沒開({err});{msg},等 8000 起來(最多 {WAIT_BACKEND_S} 秒)")
        if not ok:
            return False, f"後端沒開且{msg}"
        waited = 0
        while waited < WAIT_BACKEND_S:
            _sleep(5)
            waited += 5
            fr, err = freshness()
            if fr is not None:
                break
        if fr is None:
            return False, "後端等不到"
    if fr.get("fresh"):
        return True, "已是當天"
    res, err = http("POST", "/api/own/refresh", timeout=120)
    if res is None:
        return False, f"refresh 失敗({err})"
    if res.get("blocked") and not res.get("jobs") and not res.get("already_fresh"):
        return False, "refresh 被擋(Chrome 拉不起來):" + "; ".join(str(b.get("reason")) for b in res["blocked"])
    log(f"已觸發刷新:{len(res.get('jobs') or [])} 個 Job;每 {POLL_S} 秒查一次,最多等 {WAIT_REFRESH_S // 60} 分鐘")
    waited = 0
    while True:
        fr, err = freshness()
        if fr and fr.get("fresh"):
            return True, "刷新完成"
        if waited >= WAIT_REFRESH_S:
            return False, f"等 {WAIT_REFRESH_S // 60} 分鐘仍未完成"
        _sleep(POLL_S)
        waited += POLL_S


# ---------------------------------------------------------------- 資料時間 / 新鮮度
def parse_ts(s):
    try:
        return datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None


def freshness_info(latest, now=None):
    """由 latest.json 算 (is_today, generated_at, data_as_of, missing:list[tag/id])。latest 為 None -> (False, None, None, [])。"""
    if not latest:
        return False, None, None, []
    now = now or _now()
    gen = parse_ts(latest.get("generated_at"))
    miss_ids = ((latest.get("summary") or {}).get("missing_today_snapshot")) or []
    by_id = {v.get("video_id"): v for v in latest.get("videos") or []}
    missing = [(by_id.get(i) or {}).get("tag") or i for i in miss_ids]
    today = bool(gen and gen.date() == now.date() and not miss_ids)
    return today, latest.get("generated_at"), latest.get("data_as_of"), missing


def head_line(latest, now=None, note=None):
    """輸出第一行:一律印資料時間;非當天加大字警示。"""
    if not latest:
        return "⚠ 數據非當天:找不到 latest.json(Youtube AD 匯出檔),無資料"
    ok, gen, asof, missing = freshness_info(latest, now)
    base = f"資料時間 {gen}(快照最舊 {asof})"
    if ok:
        return base + " | 當天數據,無缺快照"
    miss = f"缺 {len(missing)} 支({','.join(missing[:6])}{'…' if len(missing) > 6 else ''})"
    gdate = (parse_ts(gen) or _now()).date()
    why = "" if gdate == (now or _now()).date() else "匯出非今天、"
    line = f"⚠ 數據非當天:資料時間 {gen}、{why}{miss}"
    return line + (f" [{note}]" if note else "")


def emit(lines, cap=LINE_CAP):
    if len(lines) > cap:
        lines = lines[:cap - 1] + [f"…(超過 {cap} 行,餘 {len(lines) - cap + 1} 行略;用 --tag / --channel 縮小範圍)"]
    print("\n".join(lines))


# ---------------------------------------------------------------- 格式小工具
def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def fv(x, nd=0, suffix=""):
    x = num(x)
    if x is None:
        return "-"
    return (f"{x:,.{nd}f}" if nd else f"{x:,.0f}") + suffix


def fdur(sec):
    sec = num(sec)
    return "-" if sec is None else f"{int(sec) // 60}:{int(sec) % 60:02d}"


def age_str(hours):
    h = num(hours)
    if h is None:
        return "-"
    return f"{h:.0f}h" if h < 72 else f"{h / 24:.0f}d"


def win(v, name):
    return ((v.get("windows") or {}).get(name)) or {}


def win_cell(w):
    b = w.get("basis")
    if b in ("pending", "none") or num(w.get("views")) is None:
        return {"pending": "未到期", "none": "無快照"}.get(b, "-")
    return fv(w.get("views")) + ("~" if b == "approx" else "")


def dur_group(sec):
    sec = num(sec)
    if sec is None:
        return "all"
    return "lt5" if sec < 300 else ("5to12" if sec < 720 else "gt12")


def find_baseline(ch, kind, sec):
    """該頻道 kind(self/other)對片長分組的基準;分組沒有就退 all。"""
    bl = (ch or {}).get("baselines") or []
    for grp in (dur_group(sec), "all"):
        for b in bl:
            if b.get("kind") == kind and b.get("duration") == grp:
                return b
    return None


def position(value, m):
    """value 對 {median,q1,q3} 的位置字串。"""
    value = num(value)
    if value is None or not m or num(m.get("median")) is None:
        return "無基準" if value is not None else "-"
    if value < m["q1"]:
        return "低於Q1"
    if value > m["q3"]:
        return "高於Q3"
    return "中位以上" if value >= m["median"] else "中位以下"


# ---------------------------------------------------------------- 訂閱/千(每千觀看淨訂閱)
SUBS_MIN_VIEWS = 1000     # 觀看不足不算比率
SUBS_SMALL = 5            # 單片 |淨增| 低於此值標「*」(樣本小)
SUBS_NOTE = "* 淨增<5 人,樣本小不下結論"
RECENT_DAYS = 90          # 與頻道 baselines 同口徑


def subs_per_k(subs, views):
    """訂/千 = subs_net / views × 1000;views<1000 或 subs_net 為 None → None。"""
    s, v = num(subs), num(views)
    if s is None or v is None or v < SUBS_MIN_VIEWS:
        return None
    return s / v * 1000


def is_small_subs(subs, views):
    """有算出比率、但 |淨增| < 5 → 樣本小。"""
    return subs_per_k(subs, views) is not None and abs(num(subs)) < SUBS_SMALL


def fpk(subs, views):
    """單片訂/千字串;不算 → "-";樣本小加「*」。"""
    r = subs_per_k(subs, views)
    if r is None:
        return "-"
    return f"{r:.2f}" + ("*" if is_small_subs(subs, views) else "")


def add_small_note(lines, flag):
    if flag:
        lines.append(SUBS_NOTE)
    return lines


def _video_age_days(v, now=None):
    a = num(v.get("age_days"))
    if a is not None:
        return a
    p = parse_ts(str(v.get("published_at") or "")[:10])
    return ((now or _now()).date() - p.date()).days if p else None


def subs_groups(ch, now=None):
    """頻道 videos 分四組 {(kind, period): [訂/千,...] 與 Σ}:kind self/other × period recent(≤90 天)/old(>90 天)。
    只收可算的(subs_net 非 None 且 views_total ≥1000)。回傳 {key: {"ratio":合計, "median":中位, "n":n}|None}。"""
    acc = {(k, p): [] for k in ("self", "other") for p in ("recent", "old")}
    for v in ch.get("videos") or []:
        age = _video_age_days(v, now)
        if age is None or subs_per_k(v.get("subs_net"), v.get("views_total")) is None:
            continue
        acc[("self" if v.get("is_self") else "other", "recent" if age <= RECENT_DAYS else "old")].append((v["subs_net"], v["views_total"]))
    out = {}
    for key, rows in acc.items():
        if not rows:
            out[key] = None
            continue
        rates = sorted(s / w * 1000 for s, w in rows)
        mid = len(rates) // 2
        med = rates[mid] if len(rates) % 2 else (rates[mid - 1] + rates[mid]) / 2
        out[key] = {"ratio": sum(s for s, _ in rows) / sum(w for _, w in rows) * 1000, "median": med, "n": len(rows)}
    return out


SUBS_OLD_MIN_N = 8        # 歷史組 n 太小不印數值(匯出只含近期片)


def _sg_cell(g, min_n=0):
    if g and g["n"] < min_n:
        return f"n<{min_n} 不比(匯出只含近期片)"
    return "-" if not g else f"{g['ratio']:.2f}|{g['median']:.2f}|n{g['n']}"


def subs_baseline_lines(ch, now=None):
    g = subs_groups(ch, now)
    out = [f"訂閱/千(合計|中位|n;跟同期比,單片 |淨增|<{SUBS_SMALL} 標樣本小;≤{RECENT_DAYS}天 vs >{RECENT_DAYS}天歷史):"]
    for kind, label in (("self", "自製"), ("other", "非自製")):
        out.append(f"  {label:<3} ≤{RECENT_DAYS}天 {_sg_cell(g[(kind, 'recent')]):<18} 歷史 {_sg_cell(g[(kind, 'old')], SUBS_OLD_MIN_N)}")
    return out


def channel_of(chdata, slot):
    for c in (chdata or {}).get("channels") or []:
        if c.get("slot") == slot:
            return c
    return None


# ---------------------------------------------------------------- 總覽 / 單片 / 異常
def self_videos(latest, slot=None, days=None):
    out = []
    for v in (latest or {}).get("videos") or []:
        if v.get("deleted_at") or not v.get("is_self"):
            continue
        if slot is not None and v.get("slot") != slot:
            continue
        if days is not None and (num(v.get("age_hours")) or 0) > days * 24:
            continue
        out.append(v)
    return out


def video_row(v):
    lt = v.get("latest") or {}
    flag = ""
    if (v.get("health") or {}).get("stale"):
        flag = "!抓取停滯"
    return (f"{(v.get('tag') or v.get('video_id'))[:14]:<14} {v.get('slot') or '-':<1} {age_str(v.get('age_hours')):>5} "
            f"{fv(lt.get('views')):>8} {win_cell(win(v, '48h')):>7} {win_cell(win(v, '7d')):>7} "
            f"{fv(lt.get('ctr_pct'), 1, '%'):>6} {fv(lt.get('avg_view_pct'), 1, '%'):>7} {flag}")


ROW_HEAD = f"{'tag':<14} {'頻':<1} {'年齡':>5} {'觀看':>8} {'48h':>7} {'7d':>7} {'CTR':>6} {'均看%':>7}"


def cmd_summary(latest, now=None, note=None):
    lines = [head_line(latest, now, note)]
    if not latest:
        return lines
    s = latest.get("summary") or {}
    lines.append(f"自製片 {s.get('videos')} 支(有快照 {s.get('with_snapshot')});異常 {s.get('alerts')} 項。以下為發布 ≤28 天(~=近似窗口值):")
    lines.append(ROW_HEAD)
    vs = self_videos(latest, days=28)
    vs.sort(key=lambda v: v.get("age_hours") or 0)
    room = LINE_CAP - len(lines) - 2
    for v in vs[:room]:
        lines.append(video_row(v))
    if len(vs) > room:
        lines.append(f"…另 {len(vs) - room} 支略(--tag 看單片、--channel 看頻道)")
    return lines


def cmd_stale(latest, now=None, note=None):
    lines = [head_line(latest, now, note)]
    if not latest:
        return lines
    n0 = len(lines)
    for a in latest.get("alerts") or []:
        lines.append(f"抓取異常:{a.get('tag') or a.get('video_id')} {(a.get('message') or '')[:90]}")
    ids = set(((latest.get("summary") or {}).get("missing_today_snapshot")) or [])
    for v in self_videos(latest):
        h = v.get("health") or {}
        age = num(v.get("age_hours")) or 0
        if v.get("video_id") in ids:
            lines.append(f"缺當天快照:{v.get('tag') or v.get('video_id')}(年齡 {age_str(age)},最後成功 {h.get('last_ok')})")
        if num(h.get("consecutive_fails")) and h["consecutive_fails"] > 0:
            lines.append(f"連續失敗 {h['consecutive_fails']} 次:{v.get('tag') or v.get('video_id')} {(h.get('fail_reason') or '')[:70]}")
        for name, hrs in (("48h", 48), ("7d", 168), ("28d", 672)):
            if win(v, name).get("basis") == "none" and age >= hrs and age <= hrs * 3:
                lines.append(f"窗口 {name} 無快照:{v.get('tag') or v.get('video_id')}")
    if len(lines) == n0:
        lines.append("無其他異常")
    return lines


def find_video(latest, key):
    for v in (latest or {}).get("videos") or []:
        if key in (v.get("tag"), v.get("video_id")):
            return v
    return None


def cmd_tag(latest, key, chdata=None, now=None, note=None):
    lines = [head_line(latest, now, note)]
    v = find_video(latest, key)
    if not v:
        lines.append(f"找不到 {key}(latest.json 只含 is_self=1 的自製片)")
        return lines
    lt = v.get("latest") or {}
    lines.append(f"{v.get('tag')} {v.get('ver') or ''} | {v.get('channel')} | {v.get('title')}")
    lines.append(f"video_id {v.get('video_id')} | 發布 {v.get('published_at')} | 片長 {fdur(v.get('duration_s'))} | 年齡 {age_str(v.get('age_hours'))}")
    lines.append(f"最新快照 {lt.get('captured_at')}:觀看 {fv(lt.get('views'))} 曝光 {fv(lt.get('impressions'))} CTR {fv(lt.get('ctr_pct'), 2, '%')} "
                 f"均看 {fv(lt.get('avg_view_pct'), 1, '%')} 訂閱 {fv(lt.get('subs_net'))}({fpk(lt.get('subs_net'), lt.get('views'))}/千) 觀看時間 {fv(lt.get('watch_time_min'))}分")
    small = is_small_subs(lt.get("subs_net"), lt.get("views"))
    for name in ("48h", "7d", "28d"):
        w = win(v, name)
        small = small or is_small_subs(w.get("subs_net"), w.get("views"))
        lines.append(f"  {name:<3} [{w.get('basis')}] 觀看 {fv(w.get('views'))} 曝光 {fv(w.get('impressions'))} CTR {fv(w.get('ctr_pct'), 2, '%')} "
                     f"均看 {fv(w.get('avg_view_pct'), 1, '%')} 訂閱 {fv(w.get('subs_net'))}({fpk(w.get('subs_net'), w.get('views'))}/千) 瀏覽 {fv(w.get('browse_pct'), 1, '%')}")
    add_small_note(lines, small)
    typ = lt.get("typical") or {}
    if typ:
        lines.append("  頻道常見範圍:" + " ".join(f"{k} {fv(a)}~{fv(b)}" for k, (a, b) in typ.items()))
    ts = v.get("traffic_source") or {}
    if ts:
        top = sorted(ts.items(), key=lambda kv: -kv[1])[:4]
        lines.append("  流量來源:" + " ".join(f"{k} {p:.0f}%" for k, p in top))
    h = v.get("health") or {}
    lines.append(f"  抓取健康:最後成功 {h.get('last_ok')} 連續失敗 {h.get('consecutive_fails')}" + (f" 原因 {h.get('fail_reason')}" if h.get("fail_reason") else ""))
    return lines


# ---------------------------------------------------------------- 頻道 / compare / rivals
def asof_line(ch, chdata):
    a = (ch or {}).get("data_as_of") or {}
    return (f"頻道匯出 {(chdata or {}).get('generated_at')} | my_daily(API)到 {a.get('my_daily')} | 競品最新 {a.get('competitors')}")


def baseline_lines(ch):
    out = []
    for b in (ch.get("baselines") or []):
        if b.get("duration") == "all" and any(x.get("kind") == b.get("kind") and x.get("duration") != "all" for x in ch["baselines"]):
            continue
        m = b.get("metrics") or {}

        def cell(k, nd=0, suf=""):
            e = m.get(k)
            return f"{fv(e.get('median'), nd, suf)}[{fv(e.get('q1'), nd)}~{fv(e.get('q3'), nd)}]n{e.get('n')}" if e else "-"
        out.append(f"  {'自製' if b['kind'] == 'self' else '非自製'} {b.get('duration_label') or b.get('duration'):<5} n={b.get('n'):<3} "
                   f"7d {cell('views_7d')} 首7d {cell('views_first7d')} 均看 {cell('avg_view_pct', 1, '%')} CTR {cell('ctr_pct', 1, '%')}")
    return out


def shown_videos(ch, self_flag, limit):
    vs = [v for v in ch.get("videos") or [] if bool(v.get("is_self")) == self_flag]
    vs.sort(key=lambda v: v.get("published_at") or "", reverse=True)
    return vs[:limit]


def video_lines(ch, self_flag, limit):
    out = []
    for v in shown_videos(ch, self_flag, limit):
        out.append(f"  {(v.get('tag') or v.get('video_id'))[:12]:<12} {(v.get('published_at') or '')[:10]} {fdur(v.get('duration_s')):>5} "
                   f"7d {fv(v.get('views_7d')):>7} 28d {fv(v.get('views_28d')):>8} 均看 {fv(v.get('avg_view_pct'), 1, '%'):>6} CTR {fv(v.get('ctr_pct'), 1, '%'):>5} "
                   f"訂/千 {fpk(v.get('subs_net'), v.get('views_total')):>5} {(v.get('title') or '')[:22]}")
    return out


def any_small(vs):
    return any(is_small_subs(v.get("subs_net"), v.get("views_total")) for v in vs)


def rival_lines(ch, n):
    out = []
    for r in (ch.get("rivals") or [])[:n]:
        out.append(f"  {fv(r.get('views_per_day')):>9}/天 {fv(r.get('views')):>10} {fdur(r.get('duration_s')):>5} {(r.get('published_at') or '')[:10]} "
                   f"{(r.get('channel_title') or '')[:14]:<14} {(r.get('title') or '')[:26]}")
    return out


def cmd_channel(latest, chdata, slot, now=None, note=None, compare=False, rivals=None):
    lines = [head_line(latest, now, note)]
    ch = channel_of(chdata, slot)
    name = SLOT_NAME.get(slot, slot)
    if not ch:
        lines.append(f"channel_latest.json 沒有 {name} 的資料")
        return lines
    lines.append(f"[{name}] " + asof_line(ch, chdata))
    for w in ch.get("warnings") or []:
        lines.append(f"  匯出警告:{w}")
    if rivals is not None and not compare:
        lines.append(f"競品熱門前 {rivals}(views/天 | 累計 | 片長 | 發布 | 頻道 | 標題):")
        lines += rival_lines(ch, rivals) or ["  (無競品資料;選題關閉的頻道固定為空)"]
        return lines
    lines.append("基準(中位[Q1~Q3]nX;只用發布 ≤90 天的片):")
    lines += baseline_lines(ch) or ["  (無基準)"]
    lines += subs_baseline_lines(ch, now)
    small = False
    if compare:
        lines.append("自製近期片 vs 同片長自製基準(口徑:首7日觀看 views_first7d 比基準首7日中位;未滿7天者無首7日值,標未滿7天):")
        selfs = [v for v in ch.get("videos") or [] if v.get("is_self")]
        selfs.sort(key=lambda v: v.get("published_at") or "", reverse=True)
        for v in selfs[:8]:
            b = find_baseline(ch, "self", v.get("duration_s"))
            m = ((b or {}).get("metrics") or {}).get("views_first7d")
            first = num(v.get("views_first7d"))
            small = small or is_small_subs(v.get("subs_net"), v.get("views_total"))
            lines.append(f"  {(v.get('tag') or v.get('video_id'))[:14]:<14} {fdur(v.get('duration_s')):>5} 首7d {fv(first):>7} "
                         f"基準首7d中位 {fv((m or {}).get('median')):>7} 訂/千 {fpk(v.get('subs_net'), v.get('views_total')):>5} → "
                         + (position(first, m) if first is not None else "未滿7天"))
        lines.append("非自製近期片(同頻道其他來源,對照用):")
        lines += video_lines(ch, False, 5) or ["  (無)"]
        small = small or any_small(shown_videos(ch, False, 5))
        lines.append(f"競品熱門前 {rivals or 8}:")
        lines += rival_lines(ch, rivals or 8) or ["  (無競品資料)"]
    else:
        lines.append("自製近期片:")
        lines += video_lines(ch, True, 8) or ["  (無)"]
        lines.append("非自製近期片:")
        lines += video_lines(ch, False, 6) or ["  (無)"]
        small = any_small(shown_videos(ch, True, 8) + shown_videos(ch, False, 6))
    add_small_note(lines, small)
    return lines


# ---------------------------------------------------------------- review
def dated_files(d, regex):
    out = []
    for p in sorted(Path(d).glob("*.json")):
        m = regex.match(p.name)
        if m:
            out.append((m.group(1), p))
    return out


def history(d, video_id):
    """逐日(以快照 captured_at 的日期去重,同日取較晚)的 latest 曲線。回傳 list[dict]。"""
    by_day = {}
    files = [p for _, p in dated_files(d, DATED_RE)]
    lp = Path(d) / "latest.json"
    if lp.is_file():
        files.append(lp)
    for p in files:
        data = read_json(p)
        for v in (data or {}).get("videos") or []:
            if v.get("video_id") != video_id:
                continue
            lt = v.get("latest") or {}
            ts = lt.get("captured_at")
            if not ts:
                continue
            by_day[str(ts)[:10]] = {"day": str(ts)[:10], "captured_at": ts, "age_hours": lt.get("age_hours"), "views": lt.get("views"),
                                    "impressions": lt.get("impressions"), "ctr_pct": lt.get("ctr_pct"), "avg_view_pct": lt.get("avg_view_pct")}
    return [by_day[k] for k in sorted(by_day)]


def plan_lines(tag):
    """當初計畫(spec.json 的 package;handoff 只指出檔名)。"""
    out = []
    spec = read_json(P.PROJECTS / tag / "spec.json") if tag else None
    if spec:
        pkg = spec.get("package") or {}
        for t in (pkg.get("titles") or [])[:2]:
            out.append(f"  計畫標題[{t.get('angle', '?')}] {t.get('text')}")
        for t in (pkg.get("thumbs") or [])[:3]:
            out.append(f"  計畫封面{t.get('plan')}[{t.get('angle', '?')}] {'/'.join(map(str, t.get('lines') or []))}")
        r = spec.get("result") or {}
        for name in ("48h", "7d"):
            w = r.get(name) or {}
            if w:
                out.append(f"  spec.result {name}: state={w.get('state')} 觀看 {fv(w.get('views'))} CTR {fv(w.get('ctr'), 2, '%')} 均看 {fv(w.get('avg_view_pct'), 1, '%')}")
    if tag and (P.PROJECTS / tag / "handoff.md").is_file():
        out.append(f"  (handoff:projects\\{tag}\\handoff.md)")
    return out


def cmd_review_tag(d, latest, chdata, key, now=None, note=None):
    lines = cmd_tag(latest, key, chdata, now, note)
    v = find_video(latest, key)
    if not v:
        return lines
    hist = history(d, v["video_id"])
    lines.append(f"逐日曲線({len(hist)} 天;依各日匯出快照):")
    lines.append(f"  {'日期':<10} {'年齡':>5} {'觀看':>8} {'曝光':>8} {'CTR':>6} {'均看%':>7}")
    for h in hist[-14:]:
        lines.append(f"  {h['day']:<10} {age_str(h['age_hours']):>5} {fv(h['views']):>8} {fv(h['impressions']):>8} "
                     f"{fv(h['ctr_pct'], 1, '%'):>6} {fv(h['avg_view_pct'], 1, '%'):>7}")
    ch = channel_of(chdata, v.get("slot"))
    b = find_baseline(ch, "self", v.get("duration_s"))
    if b:
        m = b.get("metrics") or {}
        w7 = win(v, "7d")
        lt = v.get("latest") or {}
        first = w7.get("views") if w7.get("basis") in ("exact", "approx") else None
        lines.append(f"對頻道自製基準({b.get('duration_label')} n={b.get('n')}):")
        lines.append(f"  首7天觀看 {fv(first)} vs 中位 {fv((m.get('views_first7d') or {}).get('median'))} → {position(first, m.get('views_first7d'))}")
        lines.append(f"  均看% {fv(lt.get('avg_view_pct'), 1, '%')} vs 中位 {fv((m.get('avg_view_pct') or {}).get('median'), 1, '%')} → {position(lt.get('avg_view_pct'), m.get('avg_view_pct'))}")
        lines.append(f"  CTR {fv(lt.get('ctr_pct'), 1, '%')} vs 中位 {fv((m.get('ctr_pct') or {}).get('median'), 1, '%')} → {position(lt.get('ctr_pct'), m.get('ctr_pct'))}")
        sg = subs_groups(ch, now) if ch else {}
        gs, go = sg.get(("self", "recent")), sg.get(("other", "recent"))
        lines.append(f"  訂閱/千 {fpk(lt.get('subs_net'), lt.get('views'))} vs 同期自製合計 {fv((gs or {}).get('ratio'), 2)} / 非自製合計 {fv((go or {}).get('ratio'), 2)}"
                     f"(≤{RECENT_DAYS}天)")
        if is_small_subs(lt.get("subs_net"), lt.get("views")) and SUBS_NOTE not in lines:
            lines.append(SUBS_NOTE)
    else:
        lines.append("對頻道基準:channel_latest.json 沒有此片長分組的自製基準")
    pl = plan_lines(v.get("tag"))
    if pl:
        lines.append("當初計畫 vs 結果:")
        lines += pl
    return lines


def cmd_review_channel(latest, chdata, slot, days, now=None, note=None):
    lines = [head_line(latest, now, note)]
    name = SLOT_NAME.get(slot, slot)
    ch = channel_of(chdata, slot)
    vs = self_videos(latest, slot=slot, days=days)
    vs.sort(key=lambda v: v.get("age_hours") or 0)
    lines.append(f"[{name}] 近 {days} 天自製片 {len(vs)} 支(~=近似窗口;位置=首7天或目前觀看對同片長自製基準首7d)")
    lines.append(f"{'tag':<14} {'年齡':>5} {'片長':>5} {'觀看':>8} {'48h':>7} {'7d':>7} {'CTR':>6} {'均看%':>7} {'訂/千':>6} 位置")
    small = False
    for v in vs:
        lt = v.get("latest") or {}
        b = find_baseline(ch, "self", v.get("duration_s"))
        w7 = win(v, "7d")
        val = w7.get("views") if w7.get("basis") in ("exact", "approx") else None
        pos = position(val, ((b or {}).get("metrics") or {}).get("views_first7d")) if val is not None else "7d未到"
        lines.append(f"{(v.get('tag') or v.get('video_id'))[:14]:<14} {age_str(v.get('age_hours')):>5} {fdur(v.get('duration_s')):>5} "
                     f"{fv(lt.get('views')):>8} {win_cell(win(v, '48h')):>7} {win_cell(w7):>7} {fv(lt.get('ctr_pct'), 1, '%'):>6} "
                     f"{fv(lt.get('avg_view_pct'), 1, '%'):>7} {fpk(lt.get('subs_net'), lt.get('views')):>6} {pos}")
        small = small or is_small_subs(lt.get("subs_net"), lt.get("views"))
    if not vs:
        lines.append("  (期間內無自製片)")
    return add_small_note(lines, small)


# ---------------------------------------------------------------- hook
def cmd_hook(d, now=None):
    """3 行內;錯誤只警告。回傳 lines。"""
    now = now or _now()
    note = []
    fr, _err = freshness(timeout=1.0)
    latest = load_latest(d)
    if fr is None:
        ok, msg = launch_backend()
        note.append("後端沒開," + (msg if ok else f"也{msg}") + "(開好後再跑 stats.py --ensure-fresh)")
    elif not fr.get("fresh"):
        note.append("刷新已觸發(背景)" if spawn_bg_refresh() else "刷新觸發失敗")
    else:
        note.append("後端回報已是當天")
    ok_today, gen, asof, missing = freshness_info(latest, now)
    lines = [f"[數據] 資料時間 {gen}(快照最舊 {asof})" if latest else "[數據] 找不到 latest.json"]
    lines.append(f"[數據] {'當天' if ok_today else '⚠ 非當天'};缺當天快照 {len(missing)} 支" + (f"({','.join(missing[:5])})" if missing else ""))
    lines.append("[數據] " + ";".join(note))
    try:   # 舊片回溫(topic_scout.hook_line 同時覆寫 channel\rebound.json);失敗只警告
        import topic_scout
        lines.append(topic_scout.hook_line(d, now))
    except Exception as e:  # noqa: BLE001
        lines.append(f"[回溫] 警告:偵測失敗({type(e).__name__}: {e}),不影響開工")
    return lines


# ---------------------------------------------------------------- main
def build_parser():
    ap = argparse.ArgumentParser(description="自製片數據(讀 Youtube AD 匯出檔)")
    ap.add_argument("--tag", help="單片(tag 或 video_id)")
    ap.add_argument("--stale", action="store_true", help="只印異常")
    ap.add_argument("--channel", help="頻道(ChannelA/ChannelB/ChannelC=ChannelC)")
    ap.add_argument("--compare", action="store_true", help="自製 vs 基準 vs 競品(需 --channel)")
    ap.add_argument("--rivals", nargs="?", const=10, type=int, help="競品熱門前 N(需 --channel,預設 10)")
    ap.add_argument("--review", nargs="?", const=True, metavar="TAG", help="檢討:--review <tag> 或 --review --channel <名> --days N")
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--ensure-fresh", action="store_true", help="先確保是當天數據(最多等 20 分鐘,失敗不擋)")
    ap.add_argument("--hook", action="store_true", help="SessionStart hook:5 秒內、4 行內")
    ap.add_argument("--bg-refresh", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--export-dir", help="匯出檔資料夾(測試/覆寫)")
    return ap


def run(args, now=None):
    d = export_dir(args.export_dir)
    if args.hook:
        return cmd_hook(d, now)
    note = None
    if args.ensure_fresh:
        _ok, note = ensure_fresh(log=lambda m: print(m, file=sys.stderr))
        note = None if _ok else note
    latest, chdata = load_latest(d), load_channel(d)
    if args.review:
        if args.review is not True:
            return cmd_review_tag(d, latest, chdata, args.review, now, note)
        slot = resolve_slot(args.channel)
        if slot is None:
            return [head_line(latest, now, note), "--review 需要 <tag>,或加 --channel <名> [--days N]"]
        return cmd_review_channel(latest, chdata, slot, args.days, now, note)
    if args.channel or args.compare or args.rivals is not None:
        slot = resolve_slot(args.channel)
        if slot is None:
            return [head_line(latest, now, note), f"--compare/--rivals 需要 --channel <名>;認得:{'/'.join(SLOT_ALIAS)}"]
        return cmd_channel(latest, chdata, slot, now, note, compare=args.compare, rivals=args.rivals)
    if args.tag:
        return cmd_tag(latest, args.tag, chdata, now, note)
    if args.stale:
        return cmd_stale(latest, now, note)
    return cmd_summary(latest, now, note)


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.bg_refresh:
        http("POST", "/api/own/refresh", timeout=180)
        return 0
    try:
        lines = run(args)
    except Exception as e:  # noqa: BLE001  hook 與查詢都不得因數據問題中斷開工
        if args.hook:
            lines = [f"[數據] 警告:stats.py --hook 失敗({type(e).__name__}: {e}),不影響開工"]
        else:
            raise
    emit(lines, cap=HOOK_CAP if args.hook else LINE_CAP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
