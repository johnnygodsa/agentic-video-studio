#!/usr/bin/env python3
r"""Kaggle 遠端配音本機端(channel/_archive/plans/PLAN_遠端配音Kaggle_2026-10-28.md K3);只用標準函式庫,任何 Python 3.8+ 都能跑,Kaggle CLI 以子行程呼叫
tts_env_kaggle(paths.KAGGLE_ENV;py3.12 + kaggle 2.2.5)的 kaggle.exe。

python -X utf8 pipeline\remote\kaggle_run.py push <tag>             打包(擋項照舊)-> 私有 Dataset cv-tts-<tag>(首建/新版)-> kernels push
python -X utf8 pipeline\remote\kaggle_run.py wait <tag> [--poll 300] [--timeout-h 12.5]
                                                                     輪詢 -> 下載輸出到 tmp\remote\<tag>\out -> pack_for_colab.py --import
python -X utf8 pipeline\remote\kaggle_run.py run <tag>              push + wait,寫帳本 tmp\remote\usage.jsonl(start/end)
python -X utf8 pipeline\remote\kaggle_run.py quota                  印 GPU 剩餘小時(查不到結束碼 1)
結束碼:0 成功;1 失敗(kernel error/cancel、輸出缺、匯回失敗);2 打包被擋項擋下;3 逾時。

憑證:token 檔(預設 repo 上一層的 _secrets\kaggle\kaggle.json,即 paths.ROOT.parent;CV_KAGGLE_TOKEN_FILE 可改)內容只放進 kaggle 子行程的環境變數
KAGGLE_API_TOKEN,不印、不寫檔;KAGGLE_CONFIG_DIR 固定 tmp\remote\kcfg(舊版 CLI 否則會寫 C 槽)。

Kaggle 端契約(與 colab_run.py kaggle-main 對接):kernel 啟動稿(run.py)在 /kaggle/input/** 找 colab_<tag>.zip(找不到則用
Dataset 自動解開的樹重新打包到 /tmp),只解出 pipeline/ 到 /tmp/cv_boot 後執行 `colab_run.py kaggle-main <tag>`;
傳入環境變數 CV_KAGGLE_INPUT_ZIP(輸入 zip 路徑)、CV_KAGGLE_PREV_RESUME(kernel_sources 掛回的上一版 resume/<tag>,有才設)。
輸出契約:/kaggle/working/{run_status.json, tts_<tag>.zip, resume/<tag>/}。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths as P  # noqa: E402

REMOTE = P.TMP / "remote"
TOKEN_FILE_DEFAULT = P.ROOT.parent / "_secrets" / "kaggle" / "kaggle.json"
MACHINE_SHAPE = "NvidiaTeslaT4"
EXIT_FAIL, EXIT_PACK, EXIT_TIMEOUT = 1, 2, 3
DATASET_READY_WAIT_S = 900
STATUS_ERR_LIMIT = 6          # 連續查詢失敗幾次就放棄(網路短暫斷線不算)
TERMINAL_OK = {"COMPLETE"}
TERMINAL_BAD = {"ERROR", "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED"}


def log(msg):
    print(msg, flush=True)


class KaggleError(RuntimeError):
    pass


# ---------- 憑證與 CLI ----------

def token_file():
    return Path(os.environ.get("CV_KAGGLE_TOKEN_FILE") or TOKEN_FILE_DEFAULT)


def read_token():
    f = token_file()
    if not f.is_file():
        raise KaggleError(f"找不到 Kaggle token 檔 {f}(K0:Settings -> API -> Create New Token,放到該路徑)")
    tok = f.read_text(encoding="utf-8", errors="replace").strip()
    if not tok:
        raise KaggleError(f"Kaggle token 檔是空的:{f}")
    return tok


def kaggle_cmd():
    """Kaggle CLI 指令(list)。預設 tts_env_kaggle 的 kaggle(.exe),沒有就找 PATH。"""
    d = Path(P.KAGGLE_ENV).parent
    for n in ("kaggle.exe", "kaggle"):
        if (d / n).is_file():
            return [str(d / n)]
    w = shutil.which("kaggle")
    if w:
        return [w]
    raise KaggleError(f"找不到 kaggle CLI({d} 或 PATH);請建 tts_env_kaggle:uv venv --python 3.12 tts_env_kaggle; uv pip install kaggle==2.2.5")


def kaggle_env():
    env = dict(os.environ, KAGGLE_API_TOKEN=read_token(), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cfg = REMOTE / "kcfg"
    cfg.mkdir(parents=True, exist_ok=True)
    env["KAGGLE_CONFIG_DIR"] = str(cfg)
    return env


def _scrub(text, token):
    return text.replace(token, "***") if token and text else text


def kaggle(args, check=True):
    """跑 kaggle 子指令;回傳 (rc, 合併輸出)。輸出會先抹掉 token。check=True 且 rc!=0 丟 KaggleError。"""
    env = kaggle_env()
    tok = env["KAGGLE_API_TOKEN"]
    r = subprocess.run(kaggle_cmd() + [str(a) for a in args], env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = _scrub(((r.stdout or "") + (r.stderr or "")).strip(), tok)
    if check and r.returncode:
        raise KaggleError(f"kaggle {' '.join(str(a) for a in args[:2])} 失敗(結束碼 {r.returncode}):{out[-600:]}")
    return r.returncode, out


def account():
    _, out = kaggle(["config", "view"])
    m = re.search(r"username:\s*(\S+)", out)
    if not m or m.group(1) == "None":
        raise KaggleError("kaggle config view 取不到 username(token 無效?)")
    return m.group(1)


def slug_of(tag):
    s = re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")
    return f"cv-tts-{s}"


def kernel_slug_of(tag):
    """kernel 不可與 Dataset 同 slug(實測 SaveKernel 回 409 Conflict,2026-10-28 wow_eternal_pre)。"""
    return "cvk-" + slug_of(tag)[len("cv-tts-"):]


# ---------- 配額 ----------

def quota(kind="GPU"):
    """kaggle quota 的剩餘小時(float);失敗回 None。"""
    try:
        rc, out = kaggle(["quota", "--format", "json"], check=False)
        if rc == 0:
            for row in json.loads(out):
                if str(row.get("resource", "")).upper() == kind:
                    return float(str(row["remaining"]).rstrip("hH "))
        rc, out = kaggle(["quota"], check=False)   # 舊輸出格式備援:表格
        m = re.search(rf"^{kind}\s+[\d.]+h\s+([\d.]+)h", out, re.M) if rc == 0 else None
        return float(m.group(1)) if m else None
    except (KaggleError, ValueError, KeyError, TypeError, AttributeError):
        return None


# ---------- push ----------

KERNEL_SCRIPT = r'''# 由 pipeline/remote/kaggle_run.py 產生,勿手改。只負責從 Dataset 解出 pipeline 再交給 colab_run.py kaggle-main。
import glob, json, os, shutil, subprocess, sys, zipfile
TAG = "__TAG__"
WORK, BOOT = "/kaggle/working", "/tmp/cv_boot"


def fail(msg):
    print("[bootstrap] " + msg, flush=True)
    if not os.path.exists(WORK + "/run_status.json"):
        json.dump({"tag": TAG, "ok": False, "steps": [{"name": "bootstrap", "rc": 1, "error": msg}]},
                  open(WORK + "/run_status.json", "w", encoding="utf-8"), ensure_ascii=False)
    sys.exit(1)


zips = glob.glob("/kaggle/input/**/colab_%s.zip" % TAG, recursive=True)
os.makedirs(BOOT, exist_ok=True)
if zips:
    zp = zips[0]
    with zipfile.ZipFile(zp) as z:
        z.extractall(BOOT, [n for n in z.namelist() if n.startswith("pipeline/")])
else:   # Dataset 被自動解壓:從解開的樹取 pipeline,並重新打包成 colab_run.py 要的輸入 zip
    hits = glob.glob("/kaggle/input/**/pipeline/colab/colab_run.py", recursive=True)
    if not hits:
        fail("/kaggle/input 找不到 colab_%s.zip,也找不到解開的 pipeline/" % TAG)
    tree = hits[0].rsplit("/pipeline/colab/", 1)[0]
    shutil.copytree(tree + "/pipeline", BOOT + "/pipeline", dirs_exist_ok=True)
    zp = "/tmp/colab_%s.zip" % TAG
    shutil.make_archive(zp[:-4], "zip", tree)
os.environ["CV_KAGGLE_INPUT_ZIP"] = zp
prev = glob.glob("/kaggle/input/**/resume/%s" % TAG, recursive=True)
if prev:
    os.environ["CV_KAGGLE_PREV_RESUME"] = prev[0]
rc = subprocess.call([sys.executable, "pipeline/colab/colab_run.py", "kaggle-main", TAG], cwd=BOOT)
if rc:
    fail("colab_run.py kaggle-main 結束碼 %d" % rc)
'''


def tag_dir(tag):
    return REMOTE / tag


def run_pack(tag, out_zip):
    """呼叫 pack_for_colab.py(擋項照舊);回傳結束碼。"""
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-X", "utf8", str(Path(P.REPO) / "pipeline" / "colab" / "pack_for_colab.py"), tag, "--out", str(out_zip)]
    return subprocess.run(cmd, cwd=P.REPO, env=dict(os.environ, PYTHONIOENCODING="utf-8")).returncode


def _exists(kind, ident):
    rc, _ = kaggle([kind, "status", ident], check=False)
    return rc == 0


def _dataset_state(ident):
    """(status 文字小寫, 版本號或 None)。"""
    rc, out = kaggle(["datasets", "status", ident, "--format", "json"], check=False)
    if rc != 0:
        return "", None
    try:
        d = json.loads(out)
        if isinstance(d, list):
            d = d[0] if d else {}
        v = d.get("current_version_number", d.get("currentVersionNumber"))
        return str(d.get("status", "")).lower(), int(v) if v is not None else None
    except (ValueError, TypeError, AttributeError):
        return out.lower(), None


def upload_dataset(tag, user, zip_path, sleep=time.sleep):
    """私有 Dataset <user>/cv-tts-<tag>:不存在就建、存在就出新版;等到處理完成。回傳 (id, 'create'|'version')。"""
    ds_id = f"{user}/{slug_of(tag)}"
    d = tag_dir(tag) / "dataset"
    d.mkdir(parents=True, exist_ok=True)
    for f in d.iterdir():
        if f.is_file() and f.name != zip_path.name:
            f.unlink()
    if Path(zip_path).parent != d:
        shutil.copy2(zip_path, d / Path(zip_path).name)
    (d / "dataset-metadata.json").write_text(
        json.dumps({"title": slug_of(tag), "id": ds_id, "licenses": [{"name": "CC0-1.0"}]}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    existed = _exists("datasets", ds_id)
    before = _dataset_state(ds_id)[1] if existed else None
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    if existed:
        log(f"Dataset {ds_id} 已存在(版本 {before}),出新版…")
        kaggle(["datasets", "version", "-p", d, "-m", f"{tag} {stamp}", "-r", "skip"])
    else:
        log(f"Dataset {ds_id} 首建(私有)…")
        kaggle(["datasets", "create", "-p", d, "-r", "skip"])
    waited = 0
    while True:
        st, ver = _dataset_state(ds_id)
        if "ready" in st and (before is None or ver is None or ver > before):
            break
        if waited >= DATASET_READY_WAIT_S:
            raise KaggleError(f"Dataset {ds_id} 超過 {DATASET_READY_WAIT_S}s 仍未 ready(status={st!r})")
        sleep(10)
        waited += 10
    return ds_id, ("version" if existed else "create")


def write_kernel_dir(tag, user, ds_id, with_prev):
    """tmp\\remote\\<tag>\\kernel\\{kernel-metadata.json, run.py};回傳 (目錄, kernel id)。"""
    k_id = f"{user}/{kernel_slug_of(tag)}"
    d = tag_dir(tag) / "kernel"
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": k_id, "title": kernel_slug_of(tag), "code_file": "run.py", "language": "python", "kernel_type": "script",
        "is_private": True, "enable_gpu": True, "enable_internet": True, "machine_shape": MACHINE_SHAPE,
        "dataset_sources": [ds_id], "competition_sources": [],
        "kernel_sources": [k_id] if with_prev else [],
    }
    (d / "kernel-metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "run.py").write_text(KERNEL_SCRIPT.replace("__TAG__", tag), encoding="utf-8")
    return d, k_id


def push(tag, sleep=time.sleep):
    """回傳 (結束碼, 資訊 dict)。"""
    td = tag_dir(tag)
    zip_path = td / "dataset" / f"colab_{tag}.zip"
    rc = run_pack(tag, zip_path)
    if rc:
        log(f"打包失敗/被擋(結束碼 {rc}),不上傳")
        return (EXIT_PACK if rc == EXIT_PACK else EXIT_FAIL), {}
    user = account()
    ds_id, ds_mode = upload_dataset(tag, user, zip_path, sleep)
    k_id = f"{user}/{kernel_slug_of(tag)}"
    with_prev = _exists("kernels", k_id)
    kdir, k_id = write_kernel_dir(tag, user, ds_id, with_prev)
    log(f"推送 kernel {k_id}(續跑上一版輸出:{'是' if with_prev else '否'})…")
    _, out = kaggle(["kernels", "push", "-p", kdir])
    log(out)
    info = {"tag": tag, "kernel": k_id, "dataset": ds_id, "dataset_mode": ds_mode, "kernel_sources_prev": with_prev,
            "pushed_at": now_iso()}
    (td / "state.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0, info


# ---------- wait ----------

def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_status(out):
    """'<k> has status "KernelWorkerStatus.COMPLETE"' -> 'COMPLETE';解析不出回 ''。"""
    m = re.search(r'has status\s+"([^"]*)"', out)
    return m.group(1).split(".")[-1].strip().upper() if m else ""


def load_state(tag):
    f = tag_dir(tag) / "state.json"
    if f.is_file():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"tag": tag, "kernel": f"{account()}/{kernel_slug_of(tag)}"}


def log_tail(out_dir, n=30):
    """輸出目錄裡 *.log 的最後 n 行(Kaggle 的 log 可能是 JSON 陣列,取每筆 data)。"""
    lines = []
    for f in sorted(Path(out_dir).glob("*.log")):
        raw = f.read_text(encoding="utf-8", errors="replace")
        try:
            data = json.loads(raw if raw.rstrip().endswith("]") else raw.rstrip().rstrip(",") + "]")
            lines += "".join(str(e.get("data", "")) for e in data if isinstance(e, dict)).splitlines()
        except (ValueError, AttributeError):
            lines += raw.splitlines()
    return lines[-n:]


def failed_steps(status):
    """從 run_status.json 找失敗步驟(steps 可為 list[dict] 或 dict[name->dict];rc/returncode/exit_code 非 0)。"""
    steps = status.get("steps") if isinstance(status, dict) else None
    if isinstance(steps, dict):
        steps = [dict(v, name=k) if isinstance(v, dict) else {"name": k, "rc": v} for k, v in steps.items()]
    bad = []
    for s in steps or []:
        rc = next((s[k] for k in ("rc", "returncode", "exit_code") if k in s), 0)
        if rc not in (0, None):
            bad.append(s.get("name", "?"))
    return bad


def fetch_output(kernel, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rc, out = kaggle(["kernels", "output", kernel, "-p", out_dir, "-o"], check=False)
    if rc:
        log(f"下載輸出失敗(結束碼 {rc}):{out[-300:]}")
    return rc == 0


def run_import(zip_path):
    cmd = [sys.executable, "-X", "utf8", str(Path(P.REPO) / "pipeline" / "colab" / "pack_for_colab.py"), "--import", str(zip_path)]
    return subprocess.run(cmd, cwd=P.REPO, env=dict(os.environ, PYTHONIOENCODING="utf-8")).returncode


def import_result(tag, out_dir):
    """有 tts_<tag>.zip 就 pack_for_colab --import;回傳結束碼(沒有 zip 回 None)。"""
    z = next(iter(sorted(Path(out_dir).rglob(f"tts_{tag}.zip"))), None)
    if not z:
        return None
    return run_import(z)


def read_run_status(out_dir):
    f = next(iter(sorted(Path(out_dir).rglob("run_status.json"))), None)
    if not f:
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return {"unreadable": True}


def wait(tag, poll=300, timeout_h=12.5, sleep=time.sleep, clock=time.monotonic):
    """輪詢到結束;回傳 (結束碼, 資訊 dict:status/started_running_at/qc/gpu_hours…)。"""
    st = load_state(tag)
    kernel = st["kernel"]
    out_dir = tag_dir(tag) / "out"
    t0 = clock()
    deadline = t0 + timeout_h * 3600
    running_at, status, errs, last = None, "", 0, ""
    info = {"tag": tag, "kernel": kernel}
    while True:
        rc, out = kaggle(["kernels", "status", kernel], check=False)
        status = parse_status(out) if rc == 0 else ""
        if rc != 0 or not status:
            errs += 1
            log(f"查詢狀態失敗({errs}/{STATUS_ERR_LIMIT}):{out[-200:]}")
            if errs >= STATUS_ERR_LIMIT:
                status = "UNKNOWN"
                break
        else:
            errs = 0
            if status != last:
                log(f"[{datetime.now():%H:%M:%S}] {kernel} -> {status}")
                last = status
            if status == "RUNNING" and running_at is None:
                running_at = clock()
            if status in TERMINAL_OK | TERMINAL_BAD:
                break
        if clock() >= deadline:
            status = "TIMEOUT"
            break
        sleep(poll)
    end = clock()
    info["status"] = status
    info["gpu_hours"] = round((end - (running_at if running_at is not None else t0)) / 3600, 3) if running_at is not None else 0.0
    got = fetch_output(kernel, out_dir)
    rs = read_run_status(out_dir) if got else None
    info["qc"] = (rs or {}).get("qc") or (rs or {}).get("qc_summary")
    bad = failed_steps(rs or {})
    if status in TERMINAL_OK and rs is not None and not bad:
        z = import_result(tag, out_dir)
        if z is None:
            log(f"complete 但輸出沒有 tts_{tag}.zip")
            info["error"] = "no_zip"
            return EXIT_FAIL, info
        if z:
            info["error"] = "import_failed"
            return EXIT_FAIL, info
        log(f"{tag} 遠端配音完成並已匯回")
        return 0, info
    info["error"] = status.lower() if status != "COMPLETE" else ("failed_steps" if bad else "no_run_status")
    log(f"遠端配音未成功:status={status}" + (f"、失敗步驟={bad}" if bad else "") + ("" if rs is not None else "、沒有 run_status.json"))
    z = import_result(tag, out_dir) if got else None   # 能拿到的結果仍匯回(品管過的句子不浪費)
    if z is not None:
        log(f"部分輸出已匯回(結束碼 {z})")
    for l in log_tail(out_dir):
        log("  | " + l)
    return (EXIT_TIMEOUT if status == "TIMEOUT" else EXIT_FAIL), info


# ---------- 帳本 ----------

def ledger(**kw):
    f = REMOTE / "usage.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(kw, backend="kaggle"), ensure_ascii=False) + "\n")


def run(tag, poll=300, timeout_h=12.5, sleep=time.sleep, clock=time.monotonic):
    start = now_iso()
    slug = None
    try:
        slug = f"{account()}/{kernel_slug_of(tag)}"
    except KaggleError:
        pass
    ledger(event="start", tag=tag, kernel=slug, start=start)
    info = {}
    try:
        rc, info = push(tag, sleep)
        if rc == 0:
            rc, w = wait(tag, poll, timeout_h, sleep, clock)
            info = dict(info, **w)
    except KaggleError as e:
        log(f"失敗:{e}")
        rc, info = EXIT_FAIL, dict(info, error=str(e)[:300])
    ledger(event="end", tag=tag, kernel=info.get("kernel") or slug, start=start, end=now_iso(),
           gpu_hours=info.get("gpu_hours", 0.0), rc=rc, status=info.get("status"), error=info.get("error"), qc=info.get("qc"))
    return rc


# ---------- CLI ----------

def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Kaggle 遠端配音本機端(channel/_archive/plans/PLAN_遠端配音Kaggle_2026-10-28.md K3)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("push").add_argument("tag")
    for name in ("wait", "run"):
        p = sub.add_parser(name)
        p.add_argument("tag")
        p.add_argument("--poll", type=float, default=300, help="輪詢間隔秒,預設 300")
        p.add_argument("--timeout-h", type=float, default=12.5, help="等待上限小時,預設 12.5")
    sub.add_parser("quota")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "quota":
            q = quota()
            if q is None:
                log("查不到 Kaggle GPU 配額")
                return EXIT_FAIL
            log(f"Kaggle GPU 本週剩餘 {q:g} 小時")
            return 0
        if a.cmd == "push":
            return push(a.tag)[0]
        if a.cmd == "wait":
            return wait(a.tag, a.poll, a.timeout_h)[0]
        return run(a.tag, a.poll, a.timeout_h)
    except KaggleError as e:
        log(f"失敗:{e}")
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
