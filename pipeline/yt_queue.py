#!/usr/bin/env python3
r"""Youtube AD 後端 Claude 佇列的命令列客戶端(只用標準函式庫)。

python pipeline/yt_queue.py --status              列出佇列(每支一行:片名/頻道/步驟/狀態/錯誤前 60 字/video_id)
python pipeline/yt_queue.py --retry <檔名或路徑>   從失敗步驟重跑
python pipeline/yt_queue.py --cancel <檔名或路徑>  取消
python pipeline/yt_queue.py --schedule <檔名或路徑> --publish-at <ISO|HH:MM|auto> [--channel ChannelA|ChannelB] [--wait-min 120]
                                                  輪詢佇列到該片完成(done)拿 video_id,再 POST /api/videos/<id>/schedule(G-6)
後端網址預設 http://127.0.0.1:8000(環境變數 YT_QUEUE_URL 可覆寫)。檔名(非絕對路徑)以 paths.yt_inbox() 為基準。
deliver.py --enqueue 也呼叫這裡的 enqueue();加 --publish-at 時再呼叫 schedule_after_queue()。結束碼:0 成功(含 409 已在佇列)、1 其他錯誤、2 後端沒開。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paths as P

NO_BACKEND = "後端沒開,請先開 run.bat;成片已交付"

# G-6 發布時間:台北時間。頻道預設檔次見 _shared/RULES.md §5(ChannelA每日 18:00、ChannelB每日 21:00)
TAIPEI = timezone(timedelta(hours=8))
CHANNEL_SLOT = {"ChannelA": (18, 0), "ChannelB": (21, 0)}
LEAD_AUTO_MIN = 180      # auto:取「現在起 ≥3 小時」的下一個檔次(RULES §5 佇列節奏:發布前 ≥3 小時 enqueue)
LEAD_EXPLICIT_MIN = 30   # HH:MM:取現在起 ≥30 分鐘的下一次(後端下限 15 分鐘 + 餘量)
SCHEDULE_WAIT_MIN = 120  # 佇列完成輪詢上限(分鐘)
POLL_S = 30


def base_url():
    return (os.environ.get("YT_QUEUE_URL") or "http://127.0.0.1:8000").rstrip("/")


def call(method, endpoint, body=None, timeout=15):
    """回傳 (status, text);連不上回傳 (None, 錯誤文字)。HTTP 錯誤照樣回傳狀態碼與內文。"""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base_url() + endpoint, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        return None, str(e)


def video_path(arg):
    p = Path(arg)
    return str(p if p.is_absolute() else P.yt_inbox() / p)


def action(endpoint, path, no_backend_msg=NO_BACKEND):
    """POST {path}:回傳結束碼。2xx 與 409(已在佇列)為 0、連不上 2、其他 1。"""
    st, text = call("POST", endpoint, {"path": str(path)})
    if st is None:
        print(no_backend_msg)
        return 2
    if st == 409:
        print("已在佇列")
        return 0
    if 200 <= st < 300:
        print(f"{endpoint.rsplit('/', 1)[-1]} 完成({st}): {text[:300]}")
        return 0
    print(f"HTTP {st}: {text[:300]}")
    return 1


def enqueue(path):
    return action("/api/claude_queue/enqueue", path)


def _slot_after(h, m, now, lead_min):
    """now(台北)之後第一個 h:m,且至少晚 lead_min 分鐘。"""
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    while t < now + timedelta(minutes=lead_min):
        t += timedelta(days=1)
    return t


def resolve_publish_at(spec, channel=None, now=None):
    """--publish-at 值 -> 帶 +08:00 的 ISO 字串。spec:'auto'(或空)= 頻道預設檔次(channel 需為 ChannelA/ChannelB);
    'HH:MM' = 下一個該時刻(台北);ISO(無時區視為台北)= 照用,但需晚於現在 20 分鐘。不合法 raise ValueError。"""
    now = (now or datetime.now(TAIPEI)).astimezone(TAIPEI)
    text = (spec or "auto").strip()
    if text.lower() == "auto":
        hm = CHANNEL_SLOT.get(channel or "")
        if not hm:
            raise ValueError(f"頻道「{channel}」沒有預設檔次,--publish-at 請明確給 ISO 或 HH:MM")
        return _slot_after(*hm, now, LEAD_AUTO_MIN).isoformat(timespec="seconds")
    mm = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if mm:
        h, m = int(mm.group(1)), int(mm.group(2))
        if h > 23 or m > 59:
            raise ValueError(f"--publish-at 時間不合法: {text}")
        return _slot_after(h, m, now, LEAD_EXPLICIT_MIN).isoformat(timespec="seconds")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"--publish-at 格式不認得(要 ISO、HH:MM 或 auto): {text}") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TAIPEI)
    dt = dt.astimezone(TAIPEI)
    if dt < now + timedelta(minutes=20):
        raise ValueError(f"--publish-at {dt.isoformat(timespec='seconds')} 太近或已過(需晚於現在 20 分鐘以上)")
    return dt.isoformat(timespec="seconds")


def wait_video_id(name, timeout_s, interval=POLL_S, sleep=time.sleep, clock=time.monotonic):
    """輪詢 GET /api/claude_queue 到檔名 name 的項目 done。回傳 (video_id 或 None, 原因);原因 '' = 成功。
    failed/cancelled、逾時、後端連續 3 次連不上都回 (None, 原因)。"""
    t0, down = clock(), 0
    while True:
        st, text = call("GET", "/api/claude_queue")
        if st is None:
            down += 1
            if down >= 3:
                return None, "後端連不上"
        else:
            down = 0
            if st == 200:
                try:
                    it = next((x for x in _items(json.loads(text)) if isinstance(x, dict)
                               and (_get(x, "name") == name or Path(str(_get(x, "path"))).name == name)), None)
                except ValueError:
                    it = None
                if it:
                    status = str(_get(it, "status", "state"))
                    if status == "done":
                        vid = _get(it, "video_id")
                        return (vid, "") if vid != "-" else (None, "佇列完成但沒有 video_id")
                    if status in ("failed", "cancelled"):
                        return None, f"佇列{status}(步驟 {_get(it, 'step', 'current_step')}):{str(_get(it, 'error'))[:80]}"
        if clock() - t0 >= timeout_s:
            return None, f"等佇列逾時({int(timeout_s // 60)} 分鐘)"
        sleep(interval)


def schedule_after_queue(path, publish_at, wait_min=SCHEDULE_WAIT_MIN, interval=POLL_S, sleep=time.sleep, clock=time.monotonic):
    """等 path 這支片在佇列完成後 POST /api/videos/<video_id>/schedule {publish_at}。回傳結束碼 0/1;
    呼叫端(deliver)只警告不擋。失敗時印出手動補排程的指令。"""
    name = Path(path).name
    hint = f'手動補排程:python -X utf8 pipeline\\yt_queue.py --schedule "{name}" --publish-at {publish_at}'
    print(f"等佇列完成後排程 {publish_at}(最多 {wait_min} 分鐘,每 {interval} 秒查一次)…")
    vid, why = wait_video_id(name, wait_min * 60, interval, sleep, clock)
    if vid is None:
        print(f"警告:未排程({why})。{hint}")
        return 1
    st, text = call("POST", f"/api/videos/{vid}/schedule", {"publish_at": publish_at}, timeout=60)
    if st is not None and 200 <= st < 300:
        print(f"已排程 {vid} -> {publish_at}({st}): {text[:200]}")
        return 0
    print(f"警告:排程失敗(HTTP {st}: {text[:200]})。{hint}")
    return 1


def _items(obj):
    """寬鬆取出佇列項目清單:list、{items/queue/videos/jobs: list 或 dict}、或 {path: {...}}。"""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in ("items", "queue", "videos", "jobs", "entries"):
            if isinstance(obj.get(k), (list, dict)):
                return _items(obj[k])
        if obj and all(isinstance(v, dict) for v in obj.values()):
            return [v if "path" in v else dict(v, path=k) for k, v in obj.items()]
    return []


def _get(d, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return "-"


def fmt_row(it):
    path = _get(it, "path", "file", "name")
    name = Path(str(path)).stem if path != "-" else _get(it, "title")
    err = str(_get(it, "error", "last_error", "err")).replace("\n", " ")[:60]
    return " | ".join([str(name), str(_get(it, "channel")), str(_get(it, "step", "current_step")),
                       str(_get(it, "status", "state")), err, str(_get(it, "video_id"))])


def status():
    st, text = call("GET", "/api/claude_queue")
    if st is None:
        print("後端沒開,請先開 run.bat")
        return 2
    if st != 200:
        print(f"HTTP {st}: {text[:300]}")
        return 1
    try:
        items = _items(json.loads(text))
    except ValueError:
        print(f"回應不是 JSON: {text[:300]}")
        return 1
    print("片名 | 頻道 | 步驟 | 狀態 | 錯誤 | video_id")
    for it in items[:27]:
        print(fmt_row(it) if isinstance(it, dict) else str(it)[:120])
    if len(items) > 27:
        print(f"...另 {len(items) - 27} 支未顯示")
    if not items:
        print("(佇列是空的)")
    return 0


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--status", action="store_true")
    g.add_argument("--retry", metavar="檔名")
    g.add_argument("--cancel", metavar="檔名")
    g.add_argument("--schedule", metavar="檔名", help="等佇列完成後排發布時間(需 --publish-at)")
    ap.add_argument("--publish-at", default="auto", help="ISO(無時區=台北)| HH:MM | auto(依 --channel 預設檔次)")
    ap.add_argument("--channel", help="auto 用:ChannelA|ChannelB")
    ap.add_argument("--wait-min", type=int, default=SCHEDULE_WAIT_MIN)
    a = ap.parse_args()
    if a.schedule:
        try:
            when = resolve_publish_at(a.publish_at, {"ChannelA": "ChannelA", "ChannelB": "ChannelB"}.get(a.channel or "", a.channel))
        except ValueError as e:
            sys.exit(str(e))
        sys.exit(schedule_after_queue(video_path(a.schedule), when, a.wait_min))
    if a.status:
        sys.exit(status())
    if a.retry:
        sys.exit(action("/api/claude_queue/retry", video_path(a.retry), "後端沒開,請先開 run.bat"))
    sys.exit(action("/api/claude_queue/cancel", video_path(a.cancel), "後端沒開,請先開 run.bat"))


if __name__ == "__main__":
    main()
