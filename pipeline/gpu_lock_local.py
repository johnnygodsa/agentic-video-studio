#!/usr/bin/env python3
r"""本機簡化 GPU 鎖:找不到共用鎖(<EXTERNAL_BACKEND>\_shared\gpu_lock.py,例如 KC 接手者的機器)時由 gpu_lock.py 改用。
單機互斥即可:holder.json(O_EXCL 建立)+ pid 存活判斷;不排優先序、不分專案、queue() 恆為空。
對外名稱與共用模組一致(gpu_lock.py 以同名轉出)。鎖目錄 = paths.TMP\.gpu_lock\(YT_GPU_LOCK_DIR 可改)。
環境變數沿用:YT_GPU_LOCK_NOSMI=1(不查顯存)、YT_GPU_LOCK_MAX_USED_MIB(門檻,0 關閉)、YT_GPU_LOCK_POLL(輪詢秒數)。
nvidia-smi 查不到時顯存門檻一律放行。
"""
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P  # noqa: E402

NO_DATE = "9999-99-99"
ENV_TOKEN = "YT_GPU_LOCK"
HOLDER = "holder.json"
DEFAULT_MAX_USED_MIB = 4000


def lock_dir():
    return Path(os.environ.get("YT_GPU_LOCK_DIR") or (P.TMP / ".gpu_lock"))


def poll_s():
    try:
        return float(os.environ.get("YT_GPU_LOCK_POLL") or 1.0)
    except ValueError:
        return 1.0


def _nosmi():
    return os.environ.get("YT_GPU_LOCK_NOSMI") == "1"


def max_used_mib():
    """硬門檻(MiB);NOSMI=1 或 <=0 回 None = 關閉。"""
    if _nosmi():
        return None
    v = (os.environ.get("YT_GPU_LOCK_MAX_USED_MIB") or "").strip()
    try:
        n = int(v) if v else DEFAULT_MAX_USED_MIB
    except ValueError:
        n = DEFAULT_MAX_USED_MIB
    return n if n > 0 else None


def _smi(field):
    try:
        r = subprocess.run(["nvidia-smi", f"--query-gpu={field}", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    vals = [int(x) for x in r.stdout.split() if x.strip().isdigit()]
    return max(vals) if r.returncode == 0 and vals else None


def gpu_used_mib():
    return _smi("memory.used")


def pid_alive(pid, start=None):  # noqa: ARG001  start 只為與共用模組簽名一致
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        k.OpenProcess.restype = ctypes.c_void_p
        h = k.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return k.GetLastError() == 5   # 拒絕存取 = 存在
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
        k.CloseHandle(ctypes.c_void_p(h))
        return bool(ok) and code.value == 259   # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def holder():
    return _read(lock_dir() / HOLDER)


def queue():
    return []   # 簡化版不排隊序


def describe(entry):
    if not entry:
        return "無"
    return f"{entry.get('tag')}/{entry.get('job')}"


def clean_stale(warn=True):
    """持有者 pid 已不存在就清掉;回傳被清掉的持有者(或 None)。"""
    hp = lock_dir() / HOLDER
    h = _read(hp)
    if h is None:
        try:   # 剛建立還沒寫完內容的檔不動
            if hp.exists() and time.time() - hp.stat().st_mtime > 5:
                hp.unlink()
        except OSError:
            pass
        return None
    if pid_alive(h.get("pid")):
        return None
    try:
        hp.unlink()
    except OSError:
        return None
    if warn:
        print(f"警告:清除殘留 GPU 鎖 {describe(h)}(pid {h.get('pid')} 已不存在)", flush=True)
    return h


class GpuLock:
    """with GpuLock(project, tag, job, ...):;acquire()/release() 亦可(release 可重複呼叫)。"""

    def __init__(self, project, tag, job, *, due=NO_DATE, timeout=None, cancelled=None,
                 on_wait=None, poll=None, set_env=True, report_every=60):
        self.project, self.tag, self.job, self.due = project, tag, job, due or NO_DATE
        self.timeout, self.cancelled, self.on_wait = timeout, cancelled, on_wait
        self.poll, self.set_env, self.report_every = poll, set_env, report_every
        self.held = self.nested = False
        self.token = f"{project}|{tag}|{job}|{os.getpid()}|{uuid.uuid4().hex[:8]}"

    def _entry(self):
        return dict(project=self.project, tag=self.tag, job=self.job, pid=os.getpid(), token=self.token,
                    since=datetime.now().isoformat(timespec="seconds"), due=self.due)

    def acquire(self):
        tok = os.environ.get(ENV_TOKEN)
        if tok and (holder() or {}).get("token") == tok:   # 父行程已持有
            self.nested = True
            return self
        d = lock_dir()
        d.mkdir(parents=True, exist_ok=True)
        t0, last = time.time(), None
        poll = self.poll if self.poll is not None else poll_s()
        limit = max_used_mib()
        while True:
            if self.cancelled is not None and self.cancelled():
                raise RuntimeError(f"取消等 GPU:{self.tag}/{self.job}")
            clean_stale()
            used = None
            ok_gpu = True
            if limit is not None and not (d / HOLDER).exists():
                used = gpu_used_mib()
                ok_gpu = used is None or used <= limit   # 查不到 = 放行
            if ok_gpu and self._try_take(d / HOLDER):
                return self
            now = time.time()
            if self.on_wait is not None and (last is None or now - last >= self.report_every):
                info = dict(ahead=[], holder=holder(), waited_s=now - t0)
                if used is not None and limit is not None and used > limit:
                    info.update(gpu_used=used, gpu_limit=limit)
                try:
                    self.on_wait(info)
                except Exception:  # noqa: BLE001
                    pass
                last = now
            if self.timeout is not None and now - t0 > self.timeout:
                raise TimeoutError(f"等 GPU 超過 {self.timeout} 秒")
            time.sleep(poll)

    def _try_take(self, hp):
        try:
            fd = os.open(hp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError:   # FileExistsError 或刪除中:下輪再搶
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self._entry(), f, ensure_ascii=False)
        self.held = True
        if self.set_env:
            os.environ[ENV_TOKEN] = self.token
        return True

    def release(self):
        if self.held:
            hp = lock_dir() / HOLDER
            h = _read(hp)
            if h and h.get("token") == self.token:
                try:
                    hp.unlink()
                except OSError:
                    pass
            if self.set_env and os.environ.get(ENV_TOKEN) == self.token:
                os.environ.pop(ENV_TOKEN, None)
            self.held = False

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()


def gpu_lock(project, tag, job, **kw):
    return GpuLock(project, tag, job, **kw)


def status_dict():
    cleaned = clean_stale(warn=False)
    used = None if _nosmi() else gpu_used_mib()
    lim = max_used_mib()
    return dict(lock_dir=str(lock_dir()), cleaned=cleaned, holder=holder(), queue=[], gpu_used_mib=used,
                gpu_total_mib=None, gpu_limit=lim, max_used_mib=lim, nosmi=_nosmi())


def status_text(s=None):
    s = s or status_dict()
    h = s["holder"]
    lines = ["(本機簡化鎖,非全機共用鎖)"]
    c = s.get("cleaned")
    if c is not None:
        lines.append(f"清除殘留 GPU 鎖 {describe(c)}(pid {c.get('pid')} 已不存在)")
    lines.append(f"持有:{describe(h)} pid {h.get('pid')} 自 {str(h.get('since') or '')[11:19] or '-'}" if h else "持有:無")
    lines.append("隊列 0 支(簡化版不排隊)")
    lim = s.get("gpu_limit")
    gate = "門檻關閉" if lim is None else f"門檻 ≤{lim}"
    if s["nosmi"]:
        lines.append(f"顯存:未查詢(YT_GPU_LOCK_NOSMI=1;{gate})")
    elif s["gpu_used_mib"] is None:
        lines.append(f"顯存:查不到(nvidia-smi 失敗,一律放行;{gate})")
    else:
        lines.append(f"顯存已用 {s['gpu_used_mib']} MiB({gate})")
    return "\n".join(lines)


def release_tag(tag):
    hp = lock_dir() / HOLDER
    h = _read(hp)
    if h and h.get("tag") == tag:
        try:
            hp.unlink()
            return 1
        except OSError:
            return 0
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="本機簡化 GPU 鎖")
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    r = sub.add_parser("release")
    r.add_argument("tag")
    sub.add_parser("clean")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        s = status_dict()
        print(json.dumps(s, ensure_ascii=False, indent=2) if a.json else status_text(s))
    elif a.cmd == "clean":
        print("已清除殘留持有者" if clean_stale() is not None else "沒有殘留持有者")
    else:
        n = release_tag(a.tag)
        print(f"已清除 {a.tag} 的 {n} 個鎖檔" if n else f"{a.tag} 沒有持有")
    return 0


if __name__ == "__main__":
    sys.exit(main())
