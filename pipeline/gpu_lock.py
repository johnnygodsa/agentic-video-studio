#!/usr/bin/env python3
r"""全機唯一 GPU 鎖的 Claude_Video 薄殼(實作在 <EXTERNAL_BACKEND>\_shared\gpu_lock.py,與 Youtube AD 共用同一把鎖)。

with gpu_lock(tag, job):  ...GPU 段...
  鎖目錄 <EXTERNAL_BACKEND>\_shared\.gpu_lock\(YT_GPU_LOCK_DIR 可改):holder.json = 持有者;queue\ 一人一個排隊檔。
  優先序:到期日制。本薄殼把 board.json 的 publish 當到期日傳入(早者先、無日期最後);Youtube AD 的工作視為今天到期;同日依入隊時間。
  顯存硬門檻:輪到自己時顯存已用 <= 4000 MiB 才放行(預設;YT_GPU_LOCK_MAX_USED_MIB 可改、0 關閉)。
  等待中每 60 秒印一行;持有者/排隊者 pid 不存在 = 殘留鎖,自動清除並印警告。
  可重入:持有者把 token 放進環境變數 YT_GPU_LOCK,子行程(build -> tts_cosy3 等)看到相同 token 就直接通過。
gpu_used_mib():共用的顯存查詢(make_version / tts_pron_verify 等呼叫它)。

python -X utf8 <EXTERNAL_BACKEND>\_shared\gpu_lock.py status   持有者與隊列(建議;本檔 status 轉呼叫同一支)
python -X utf8 pipeline/gpu_lock.py status             同上
python -X utf8 pipeline/gpu_lock.py release <tag>      手動解殘留鎖(持有者或隊列中該 tag 的檔)
共用檔不存在(KC 機器)時退回 gpu_lock_local.py 的本機簡化鎖(單機互斥、不排優先序、鎖目錄 tmp\.gpu_lock\),import 時印一行 stderr 警告。
測試用環境變數:YT_GPU_LOCK_DIR(鎖目錄)、YT_GPU_LOCK_NOSMI=1(不查顯存)、YT_GPU_LOCK_POLL(輪詢秒數)。
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P  # noqa: E402


def _load_shared(path):
    """載入共用模組(以 yt_gpu_lock 為名,避免與本檔 gpu_lock 撞名;同行程只載一次)。"""
    m = sys.modules.get("yt_gpu_lock")
    if m is None:
        spec = importlib.util.spec_from_file_location("yt_gpu_lock", path)
        m = importlib.util.module_from_spec(spec)
        sys.modules["yt_gpu_lock"] = m
        spec.loader.exec_module(m)
    return m


_SHARED_FILE = P.SHARED / "gpu_lock.py"
if _SHARED_FILE.is_file():
    _S = _load_shared(_SHARED_FILE)
else:   # KC 接手者等沒有共用目錄的機器:改用本機簡化鎖(gpu_lock_local.py),不中斷配音/出片
    import gpu_lock_local as _S  # noqa: E402
    print(f"WARNING: 找不到共用 GPU 鎖,改用本機簡化鎖({_SHARED_FILE})", file=sys.stderr, flush=True)

GPU_MAX_MIB = _S.max_used_mib()   # 共用模組目前的實際門檻(MiB);關閉時為 None
ENV_TOKEN = _S.ENV_TOKEN
NO_DATE = _S.NO_DATE
gpu_used_mib = _S.gpu_used_mib
holder = _S.holder
clean_stale = _S.clean_stale
queue = _S.queue
status_text = _S.status_text
release_tag = _S.release_tag
pid_alive = _S.pid_alive
lock_dir = _S.lock_dir
poll_s = _S.poll_s


def _publish_of(tag):
    try:
        import board
        return (board.get(tag) or {}).get("publish") or NO_DATE
    except Exception:  # noqa: BLE001  進度板壞掉不影響排隊
        return NO_DATE


def _report(info):
    ahead = [str(e.get("tag")) for e in info["ahead"]]
    gpu_s = ""
    if info.get("gpu_used") is not None:
        gpu_s = f";顯存已用 {info['gpu_used']} MiB > {info['gpu_limit']}"
    print(f"等 GPU:前面 {len(ahead)} 支({'、'.join(ahead) or '-'}),目前持有 {_S.describe(info['holder'])}{gpu_s}", flush=True)


def gpu_lock(tag, job, timeout=None):
    return _S.GpuLock("cv", tag, job, due=_publish_of(tag), timeout=timeout, on_wait=_report, set_env=True)


def main():
    return _S.main()


if __name__ == "__main__":
    sys.exit(main())
