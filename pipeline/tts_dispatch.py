#!/usr/bin/env python3
r"""配音後端調度器(channel/_archive/plans/PLAN_遠端配音Kaggle_2026-10-28.md K4);只用標準函式庫,任何 Python 3.8+ 都能跑。

python -X utf8 pipeline\tts_dispatch.py <tag>                                 不自動選後端(使用者 2026-10-29 定):只評估 Colab/Kaggle/本機三者
    可用與否+理由,印建議後端(Colab -> Kaggle -> 本機,只是建議),不打包、不啟動、不寫帳本/board,結束碼 4。
    主對話收到後必須先問使用者要 Colab(C)、Kaggle(K) 還是本機,再用 --prefer 執行。--dry-run 沒給 --prefer 同樣結束碼 4。
python -X utf8 pipeline\tts_dispatch.py <tag> --prefer colab|kaggle|local [--dry-run] [--foreground] [--refreeze-ok] [--skip-c0]
    C0 閘門(channel/_archive/plans/PLAN_C0試配與讀音記憶_2026-10-31.md §3.5):--prefer 開跑前要 projects\<tag>\c0_report.json 存在、script_sha 與目前配音稿相符、唸錯 0,否則拒絕並印指令
    (結束碼 1;--skip-c0 略過,--refreeze-ok 自動略過,--dry-run 只印狀態)。不帶 --prefer 的狀態列也顯示 C0 狀態。
    Colab(1 支)、Kaggle(KAGGLE_MAX 支)、本機(每後端各一支,使用者 2026-10-28 定),選定後 board.py set <tag> --next "C配音:<後端>…"。
    Colab:帳本 colab 進行中 = 0;打包、帳本寫 start、印給使用者的訊息全文與退路(--prefer colab 不看發布時間門檻,使用者已決定)。
    Kaggle:token 檔存在 + kaggle_run.quota() 剩餘 >= 本片預估 + 緩衝 + 帳本 kaggle 進行中 < KAGGLE_MAX(quota 查不到 = 不可用)。
      預設背景(detached)啟動 kaggle_run.py run,log 寫 tmp
emote\<tag>
un.log;--foreground 前景跑(主對話用 run_in_background 等通知)。
    本機:印 make_version --tts-review --freeze 指令(不寫帳本,本機有 gpu_lock)。
    --prefer 指定的 Colab/Kaggle 不可用就報錯(結束碼 1),不改走別的。
    --prefer kaggle 且並行已滿:不報錯,每 KAGGLE_POLL_S(60)秒查帳本直到空出,最多 KAGGLE_WAIT_MAX(預設 3 小時,環境變數 KAGGLE_WAIT_MAX 秒可覆寫),
      逾時才回原本的「並行已滿」錯誤(結束碼 1);等待中每次印一行(已等分鐘、目前進行中數)。--dry-run 不等待。
    --dry-run(有 --prefer)只印選擇與理由,不打包、不推送、不寫帳本、不寫 board。
    --skip 已無自動選擇,僅相容(接受但不作用)。
python -X utf8 pipeline\tts_dispatch.py --colab-done <tag> <tts_<tag>.zip>   pack_for_colab.py --import,成功寫帳本 end
python -X utf8 pipeline\tts_dispatch.py --colab-cancel <tag>                 帳本寫 end(rc=cancelled)
python -X utf8 pipeline\tts_dispatch.py --status                              各後端進行中、Kaggle 剩餘、本週已用、gpu_lock 第一行
結束碼:0 成功/已啟動;1 失敗或後端不可用;2 Colab 打包被擋項擋下;4 沒給 --prefer(只印三後端狀態與建議,要先問使用者)。
帳本 tmp\remote\usage.jsonl(kaggle_run 與本檔共用):一行一事件 {event: start|end, tag, backend, start, end, gpu_hours, rc, ...};
某 (backend, tag) 最後事件是 start = 進行中。Kaggle 進行中超過 KAGGLE_STALE_H 視為當機殘留,不計並行。
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "remote"))
import paths as P  # noqa: E402
import kaggle_run as KR  # noqa: E402

# ---------- 常數(K1/K6 後更新) ----------
KAGGLE_MAX = 1               # Kaggle 實測可並行 2;使用者 2026-10-28 定每後端一支,要放寬改這個常數
COLAB_MAX_PARALLEL = 1
SEC_PER_LINE = 46            # KC quantum 實測:85 句第一輪約 65 分鐘;K6 後校正
SETUP_MIN = 15               # 安裝/載模型分鐘
QUOTA_BUFFER_H = 2.0         # Kaggle 剩餘需 >= 預估 + 緩衝
COLAB_WAIT_MIN = 60          # 使用者多久沒回就 cancel 並問使用者改 Kaggle/本機
PUBLISH_MIN_H = 6            # 發布時間剩不到幾小時不走 Colab(也是主對話的退路門檻)
PUBLISH_DEFAULT_HOUR = 18    # board 只有日期時當天幾點
KAGGLE_WAIT_MAX = int(os.environ.get("KAGGLE_WAIT_MAX", 3 * 3600))   # --prefer kaggle 並行已滿時最多排隊幾秒(P6)
KAGGLE_POLL_S = 60           # 排隊時每幾秒查一次帳本
KAGGLE_STALE_H = 14          # 超過 kaggle_run 逾時上限(12.5h)仍沒 end = 殘留
WEEK_DAYS = 7
BACKENDS = ("colab", "kaggle", "local")
EXIT_FAIL, EXIT_PACK, EXIT_ASK = 1, 2, 4


def log(msg=""):
    print(msg, flush=True)


# ---------- 預估與發布時間 ----------

def count_lines(tag):
    """句數:<tag>\\script.json 的 sections[].lines;沒有就數 script.txt 非空非 # 行;都沒有回 0。"""
    base = P.REPO / tag
    j = base / "script.json"
    if j.is_file():
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
            n = sum(len(s.get("lines", [])) for s in data.get("sections", []))
            if n:
                return n
        except (ValueError, AttributeError, TypeError):
            pass
    t = base / "script.txt"
    if t.is_file():
        return sum(1 for ln in t.read_text(encoding="utf-8", errors="replace").splitlines()
                   if ln.strip() and not ln.lstrip().startswith("#"))
    return 0


def estimate_hours(lines):
    return lines * SEC_PER_LINE / 3600 + SETUP_MIN / 60


def parse_publish(s):
    """board 的 publish 字串 -> datetime(本地);只有日期 = 當天 PUBLISH_DEFAULT_HOUR 點;空/壞 = None。"""
    if not s:
        return None
    s = str(s).strip()
    try:
        if len(s) <= 10:
            return datetime.strptime(s, "%Y-%m-%d").replace(hour=PUBLISH_DEFAULT_HOUR)
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        return None


def board_publish(tag):
    try:
        import board
        return parse_publish((board.get(tag) or {}).get("publish"))
    except Exception:  # noqa: BLE001  進度板壞掉不影響調度
        return None


# ---------- 帳本 ----------

def ledger_file():
    return Path(KR.REMOTE) / "usage.jsonl"


def read_ledger():
    f = ledger_file()
    rows = []
    if f.is_file():
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict):
                rows.append(r)
    return rows


def write_ledger(**kw):
    f = ledger_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(kw, ensure_ascii=False) + "\n")


def _ts(s):
    try:
        return datetime.fromisoformat(str(s)).replace(tzinfo=None) if s else None
    except ValueError:
        return None


def open_jobs(rows, backend, now=None):
    """某後端進行中的 {tag: start 事件}(最後事件是 start);Kaggle 超過 KAGGLE_STALE_H 的殘留不計。"""
    cur = {}
    for r in rows:
        if r.get("backend") != backend or not r.get("tag"):
            continue
        if r.get("event") == "start":
            cur[r["tag"]] = r
        elif r.get("event") == "end":
            cur.pop(r["tag"], None)
    if backend == "kaggle":
        now = now or datetime.now()
        for t in [t for t, r in cur.items() if _ts(r.get("start")) and now - _ts(r["start"]) > timedelta(hours=KAGGLE_STALE_H)]:
            del cur[t]
    return cur


def weekly_used(rows, backend, now=None):
    """近 WEEK_DAYS 天該後端已結束工作的 GPU 小時(沒填 gpu_hours 就用 end-start)。"""
    now = now or datetime.now()
    total = 0.0
    for r in rows:
        if r.get("backend") != backend or r.get("event") != "end":
            continue
        e = _ts(r.get("end"))
        if not e or now - e > timedelta(days=WEEK_DAYS):
            continue
        h = r.get("gpu_hours")
        if not h and _ts(r.get("start")):
            h = (e - _ts(r["start"])).total_seconds() / 3600
        total += float(h or 0)
    return total


# ---------- 後端可用性與選擇 ----------

def kaggle_availability(tag, need_h, rows, now=None):
    """-> (可用, 理由)。"""
    if not KR.token_file().is_file():
        return False, f"Kaggle token 檔不存在({KR.token_file()})"
    running = open_jobs(rows, "kaggle", now)
    if tag in running:
        return False, f"{tag} 已在 Kaggle 跑(帳本有 start 無 end)"
    if len(running) >= KAGGLE_MAX:
        return False, f"Kaggle 並行已滿({len(running)}/{KAGGLE_MAX}:{'、'.join(running)})"
    q = KR.quota()
    if q is None:
        return False, "查不到 Kaggle 配額(連不上或 token 無效)"
    if q < need_h + QUOTA_BUFFER_H:
        return False, f"Kaggle 配額不足:剩 {q:g}h < 預估 {need_h:.2f}h + 緩衝 {QUOTA_BUFFER_H:g}h"
    return True, f"Kaggle 剩 {q:g}h >= 預估 {need_h:.2f}h + 緩衝 {QUOTA_BUFFER_H:g}h,並行 {len(running)}/{KAGGLE_MAX}"


def colab_availability(tag, rows, publish, now=None, check_deadline=True):
    now = now or datetime.now()
    running = open_jobs(rows, "colab", now)
    if len(running) >= COLAB_MAX_PARALLEL:
        return False, f"Colab 被占用({'、'.join(running)} 帳本有 start 無 end;已完成/放棄請 --colab-done / --colab-cancel)"
    if check_deadline and publish is not None and publish - now < timedelta(hours=PUBLISH_MIN_H):
        return False, f"發布時間 {publish:%Y-%m-%d %H:%M} 剩不到 {PUBLISH_MIN_H} 小時,等使用者操作 Colab 來不及"
    return True, "Colab 空閒" + ("" if publish is None else f",發布 {publish:%Y-%m-%d %H:%M}")


def survey(tag, now=None):
    """-> (建議後端, {backend: (可用, 理由)}, 理由清單, 預估小時)。三個後端都評估,不因前一個可用就停。
    建議沿用 Colab -> Kaggle -> 本機,只是建議,不代表會執行(要使用者決定)。"""
    now = now or datetime.now()
    rows = read_ledger()
    lines = count_lines(tag)
    need = estimate_hours(lines)
    publish = board_publish(tag)
    av = {
        "colab": colab_availability(tag, rows, publish, now),
        "kaggle": kaggle_availability(tag, need, rows, now),
        "local": (True, "永遠可用(gpu_lock 排隊;本機已有配音在排隊時會依發布日順序等待)"),
    }
    why = [f"{tag}:{lines} 句,預估 {need:.2f}h(句×{SEC_PER_LINE}s + 安裝 {SETUP_MIN}min)"]
    for b, label in (("colab", "Colab"), ("kaggle", "Kaggle"), ("local", "本機")):
        ok, r = av[b]
        why.append(f"{label} {'可用' if ok else '不可用'}:{r}")
    suggest = next(b for b in BACKENDS if av[b][0])
    return suggest, av, why, need


def choose(tag, prefer, now=None):
    """-> (backend|None, 理由清單, 預估小時);只處理使用者指定的 prefer。backend None = 指定的後端不可用。"""
    if prefer not in BACKENDS:
        raise ValueError("choose() 需要 prefer;沒指定後端請用 survey() 並先問使用者")
    now = now or datetime.now()
    rows = read_ledger()
    lines = count_lines(tag)
    need = estimate_hours(lines)
    publish = board_publish(tag)
    why = [f"{tag}:{lines} 句,預估 {need:.2f}h(句×{SEC_PER_LINE}s + 安裝 {SETUP_MIN}min)"]
    if prefer == "local":
        return "local", why + ["--prefer local"], need
    if prefer == "colab":
        ok, r = colab_availability(tag, rows, publish, now, check_deadline=False)
        why.append(("Colab 可用:" if ok else "Colab 不可用:") + r)
        return ("colab" if ok else None), why, need
    ok, r = kaggle_availability(tag, need, rows, now)
    why.append(("Kaggle 可用:" if ok else "Kaggle 不可用:") + r)
    return ("kaggle" if ok else None), why, need


# ---------- 動作 ----------

def board_set(tag, text):
    r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "board.py"), "set", tag, "--next", text],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        log(f"(board 更新失敗,不影響調度:{(r.stdout + r.stderr).strip()[-200:]})")


def kaggle_cmd_for(tag):
    return [sys.executable, "-X", "utf8", str(HERE / "remote" / "kaggle_run.py"), "run", tag]


def launch_kaggle(tag, foreground=False):
    """foreground -> 回 kaggle_run run 的結束碼;否則 detached 子行程(log 寫 run.log),回 (0, log 路徑)。"""
    cmd = kaggle_cmd_for(tag)
    if foreground:
        return subprocess.run(cmd).returncode, None
    d = Path(KR.REMOTE) / tag
    d.mkdir(parents=True, exist_ok=True)
    lf = d / "run.log"
    kw = {}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW  # 不用 DETACHED_PROCESS:子行程再開的 kaggle/python 會各跳 cmd 視窗
    else:
        kw["start_new_session"] = True
    with open(lf, "w", encoding="utf-8") as fh:
        subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
    return 0, lf


def pack_colab(tag):
    out = P.TMP / "colab" / f"colab_{tag}.zip"
    rc = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "colab" / "pack_for_colab.py"), tag,
                         "--out", str(out)]).returncode
    return rc, out


def run_import(zip_path):
    return subprocess.run([sys.executable, "-X", "utf8", str(HERE / "colab" / "pack_for_colab.py"),
                           "--import", str(zip_path)]).returncode


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def local_command(tag):
    return rf"python -X utf8 pipeline\make_version.py --tag {tag} --ver <ver> --tts-review --freeze"


def colab_user_message(tag, zip_path):
    return (
        f"【請使用者操作 Colab 配音:{tag}】\n"
        f"1. {zip_path} 已由主對話上傳到 Google Drive 的 CV_colab\\ 資料夾"
        f"(若主對話無法上傳,才請使用者自己放進去)。\n"
        f"2. 開 pipeline\\colab\\colab_tts.ipynb,把 TAG 改成 {tag},按「全部執行」"
        f"(第一次安裝約 10–15 分鐘;斷線重跑會接著做)。這一步一定要你按,Colab 沒有 API,不按就不會開始。\n"
        f"3. 跑完後下載 Drive CV_colab\\tts_{tag}.zip,回報該 zip 的路徑給我。"
    )


def colab_fallback_note(tag):
    return (f"【主對話退路】使用者 {COLAB_WAIT_MIN} 分鐘內沒回,或發布時間剩不到 {PUBLISH_MIN_H} 小時 → "
            f"`tts_dispatch.py --colab-cancel {tag}`,然後問使用者改 Kaggle 還是本機,"
            f"再用 `tts_dispatch.py {tag} --prefer kaggle|local` 執行(由使用者決定,不替他選)。"
            f"使用者回報 zip 後:`tts_dispatch.py --colab-done {tag} <zip>`,再跑 make_version --tts-review --freeze(必須新合成 0)。")


def c0_status(tag):
    """C0 試配狀態 -> (通過, 說明)。"""
    try:
        import tts_c0
        return tts_c0.status(tag)
    except Exception as e:  # noqa: BLE001  查不到就當沒過,由 --skip-c0 明確放行
        return False, f"查不到 C0 狀態({type(e).__name__}: {str(e)[:120]})"


def advise(tag):
    """沒給 --prefer:只印三後端狀態與建議,不做任何動作;回 EXIT_ASK。"""
    suggest, av, why, _ = survey(tag)
    log(f"== 配音後端狀態 {tag}(尚未選後端,未打包/未啟動/未寫帳本)")
    for w in why:
        log("  " + w)
    log("  C0 試配:" + c0_status(tag)[1])
    log(f"建議:{suggest}(依 Colab -> Kaggle -> 本機,僅供參考)")
    log("【給主對話】請問使用者要在 Colab(C)、Kaggle(K) 還是本機跑,再用 --prefer colab|kaggle|local 執行")
    return EXIT_ASK


def verify_ok(tag):
    """打包前:配音稿與凍結一致(tts_script.py --verify);不一致就擋(--refreeze-ok / CV_REFREEZE_OK=1 改稿重錄時放行)。"""
    rc = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "tts_script.py"), tag, "--verify"]).returncode
    if rc == 0 or os.environ.get("CV_REFREEZE_OK") == "1":
        return True
    log(f"錯誤:配音文本與凍結不一致,不打包。查:python -X utf8 pipeline\\tts_script.py {tag} --verify"
        "(確定要改稿重錄才加 --refreeze-ok)")
    return False


def wait_kaggle_slot(tag, sleep=None, poll_s=None, max_s=None, now=None):
    """--prefer kaggle 且 Kaggle 並行已滿 -> 每 poll_s 秒重讀帳本直到空出;回 True = 不必再等(空出、或根本不是並行已滿)、
    False = 等滿 max_s 仍滿(呼叫端接著照原本流程回「並行已滿」錯誤)。sleep 可注入(測試用),已等秒數以 poll_s 累計。"""
    sleep = sleep or time.sleep
    poll_s = KAGGLE_POLL_S if poll_s is None else poll_s
    max_s = KAGGLE_WAIT_MAX if max_s is None else max_s
    waited = 0
    while True:
        running = open_jobs(read_ledger(), "kaggle", now)
        if tag in running or len(running) < KAGGLE_MAX or not KR.token_file().is_file():
            return True   # 空出,或屬其他錯誤(同 tag 進行中、無 token)交給 choose 回報
        if waited >= max_s:
            log(f"Kaggle 並行仍滿({len(running)}/{KAGGLE_MAX}:{'、'.join(running)}),已等 {waited // 60} 分鐘達上限 {max_s // 60} 分鐘,不再等")
            return False
        log(f"Kaggle 並行已滿({len(running)}/{KAGGLE_MAX}:{'、'.join(running)}),排隊中,已等 {waited // 60} 分鐘,{poll_s} 秒後再查")
        sleep(poll_s)
        waited += poll_s


def dispatch(tag, prefer=None, dry_run=False, foreground=False, skip_c0=False, sleep=None):
    if prefer is None:
        return advise(tag)
    if prefer == "kaggle" and not dry_run:
        wait_kaggle_slot(tag, sleep=sleep)
    backend, why, need = choose(tag, prefer)
    log(f"== 配音後端調度 {tag}" + (" (dry-run)" if dry_run else ""))
    for w in why:
        log("  " + w)
    if backend is None:
        log(f"錯誤:--prefer {prefer} 不可用,不改走別的後端")
        return EXIT_FAIL
    log(f"選擇:{backend}")
    c0_ok, c0_msg = c0_status(tag)
    log("C0 試配:" + c0_msg)
    rows = read_ledger()
    stuck = [b for b in ("kaggle", "colab") if tag in open_jobs(rows, b)]
    if stuck and not dry_run and backend != "local":
        log(f"錯誤:{tag} 在 {stuck[0]} 已有進行中的工作(帳本 start 無 end)")
        return EXIT_FAIL
    if dry_run:
        return 0
    if not (c0_ok or skip_c0 or os.environ.get("CV_REFREEZE_OK") == "1"):
        log(rf"錯誤:C0 試配未通過,不開跑。先跑:tts_env_chattts\Scripts\python.exe -X utf8 pipeline\tts_c0.py {tag}"
            "(確定略過才加 --skip-c0)")
        return EXIT_FAIL
    if not verify_ok(tag):
        return EXIT_FAIL
    if backend == "kaggle":
        board_set(tag, "C配音:Kaggle 遠端配音中,完成自動匯回後跑 make_version --tts-review --freeze(新合成須 0)")
        rc, lf = launch_kaggle(tag, foreground)
        if foreground:
            log(f"kaggle_run 結束碼 {rc}。" + ("成功:已自動 --import;接著跑 make_version --tts-review --freeze(必須新合成 0)。"
                                               if rc == 0 else "失敗:看上方輸出,可 --prefer local。"))
            return rc
        log(f"已在背景啟動 kaggle_run.py run {tag};log:{lf}")
        log("完成時 kaggle_run 會自動 --import;等完成後跑 make_version --tts-review --freeze(必須新合成 0)。"
            f"主對話要被通知完成,應一開始就用 run_in_background 執行:python -X utf8 pipeline\\tts_dispatch.py {tag} --foreground")
        return 0
    if backend == "colab":
        rc, zp = pack_colab(tag)
        if rc:
            log(f"Colab 打包失敗(結束碼 {rc};擋項見上方輸出),未寫帳本")
            return EXIT_PACK if rc == EXIT_PACK else EXIT_FAIL
        write_ledger(event="start", tag=tag, backend="colab", start=now_iso(), zip=str(zp))
        board_set(tag, "C配音:Colab 等使用者跑筆記本(60 分未回改本機)")
        log("")
        log(colab_user_message(tag, zp))
        log("")
        log(colab_fallback_note(tag))
        return 0
    board_set(tag, "C配音:本機 make_version --tts-review --freeze")
    log("請主對話背景執行(GPU 由 gpu_lock 排隊):")
    log("  " + local_command(tag))
    return 0


def colab_done(tag, zip_path):
    if tag not in open_jobs(read_ledger(), "colab"):
        log(f"警告:帳本沒有 {tag} 進行中的 Colab 工作,仍嘗試匯入")
    rc = run_import(zip_path)
    if rc:
        log(f"匯入失敗(結束碼 {rc});帳本維持進行中,可修正後重跑或 --colab-cancel")
        return EXIT_FAIL
    e = now_iso()
    st = open_jobs(read_ledger(), "colab").get(tag, {}).get("start")
    write_ledger(event="end", tag=tag, backend="colab", start=st, end=e, rc=0,
                 gpu_hours=round((_ts(e) - _ts(st)).total_seconds() / 3600, 3) if _ts(st) else 0.0)
    log(f"Colab 匯入完成。接著跑 make_version --tts-review --freeze(必須新合成 0):{local_command(tag)}")
    return 0


def colab_cancel(tag):
    st = open_jobs(read_ledger(), "colab").get(tag, {}).get("start")
    write_ledger(event="end", tag=tag, backend="colab", start=st, end=now_iso(), rc="cancelled", gpu_hours=0.0)
    log(f"已取消 {tag} 的 Colab 工作(帳本寫 end rc=cancelled)")
    return 0


def gpu_lock_first_line():
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "gpu_lock.py"), "status"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60)
        lines = (r.stdout or r.stderr or "").strip().splitlines()
        return lines[0] if lines else "(無輸出)"
    except (OSError, subprocess.SubprocessError) as e:
        return f"(查詢失敗:{e})"


def status():
    rows = read_ledger()
    for b in ("colab", "kaggle"):
        jobs = open_jobs(rows, b)
        desc = "、".join(f"{t}(自 {r.get('start')})" for t, r in jobs.items()) or "無"
        log(f"{b} 進行中:{desc}")
    q = KR.quota()
    log("Kaggle 剩餘 GPU 小時:" + (f"{q:g}" if q is not None else "查不到"))
    log("本週已用小時:" + ";".join(f"{b} {weekly_used(rows, b):.2f}h" for b in ("colab", "kaggle")))
    log("本機 gpu_lock:" + gpu_lock_first_line())
    return 0


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="配音後端調度器(不自動選;先問使用者 C/K/本機,再 --prefer)")
    ap.add_argument("tag", nargs="?")
    ap.add_argument("--prefer", choices=BACKENDS)
    ap.add_argument("--skip", action="append", default=[], choices=("colab", "kaggle"), help="已無自動選擇,僅相容(不作用)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refreeze-ok", action="store_true", help="已凍結的片改旁白後允許遠端打包重錄(設 CV_REFREEZE_OK=1 給 pack_for_colab/kaggle_run 沿用)")
    ap.add_argument("--skip-c0", action="store_true", help="略過 C0 試配閘門")
    ap.add_argument("--polyset", choices=("rules", "risk", "all"), default=None, help="E1 all 模式的多音字集合:設 COSY_POLYSET(預設 risk)")
    ap.add_argument("--annotate", choices=("table", "all"), default=None,
                    help="cosy3 拼音標注模式(E1 pilot):設 COSY_ANNOTATE 給本機子行程;遠端(Colab/Kaggle)不帶")
    ap.add_argument("--foreground", action="store_true", help="選到 Kaggle 時前景跑 kaggle_run run(主對話用 run_in_background)")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--colab-done", nargs=2, metavar=("TAG", "ZIP"))
    ap.add_argument("--colab-cancel", metavar="TAG")
    a = ap.parse_args(argv)
    if a.refreeze_ok:
        os.environ["CV_REFREEZE_OK"] = "1"
    if a.annotate:
        os.environ["COSY_ANNOTATE"] = a.annotate
    if a.polyset:
        os.environ["COSY_POLYSET"] = a.polyset
    if a.status:
        return status()
    if a.colab_done:
        return colab_done(a.colab_done[0], a.colab_done[1])
    if a.colab_cancel:
        return colab_cancel(a.colab_cancel)
    if not a.tag:
        ap.error("需要 <tag>(或 --status / --colab-done / --colab-cancel)")
    return dispatch(a.tag, a.prefer, a.dry_run, a.foreground, a.skip_c0)


if __name__ == "__main__":
    sys.exit(main())
