"""gpu_lock 退回本機簡化鎖測試(共用檔不存在不得 sys.exit;存在時仍載入共用模組)。
全在子行程跑,鎖目錄指到 paths.TMP\\test_gpu_lock_fallback\\,不碰真的 _shared\\.gpu_lock,不查 GPU。"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import paths as P  # noqa: E402

BASE = P.TMP / "test_gpu_lock_fallback"

CODE = r"""
import sys
sys.path.insert(0, sys.argv[1])
import gpu_lock as GL
print("MOD", GL._S.__name__)
for n in ("GPU_MAX_MIB ENV_TOKEN NO_DATE gpu_used_mib holder clean_stale queue status_text "
          "release_tag pid_alive lock_dir poll_s gpu_lock main").split():
    assert hasattr(GL, n), n
with GL.gpu_lock("t", "job", timeout=5):
    h = GL.holder()
    assert h and h["tag"] == "t", h
    with GL.gpu_lock("t", "child"):   # 可重入
        pass
    assert GL.holder()["tag"] == "t"
assert GL.holder() is None
print(GL.status_text().splitlines()[0])
assert GL.release_tag("nobody") == 0
print("OK")
"""


def run(shared):
    shutil.rmtree(BASE, ignore_errors=True)
    BASE.mkdir(parents=True)
    env = dict(os.environ, YT_SHARED_DIR=str(shared), YT_GPU_LOCK_DIR=str(BASE / "lock"),
               YT_GPU_LOCK_NOSMI="1", YT_GPU_LOCK_POLL="0.1")
    env.pop("YT_GPU_LOCK", None)
    return subprocess.run([sys.executable, "-X", "utf8", "-c", CODE, str(HERE)], env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


def test_fallback_when_shared_missing():
    r = run(BASE / "no_such_shared")
    assert r.returncode == 0, r.stderr
    assert "MOD gpu_lock_local" in r.stdout and r.stdout.strip().endswith("OK")
    warns = [x for x in r.stderr.splitlines() if "改用本機簡化鎖" in x]
    assert len(warns) == 1, r.stderr
    assert "找不到共用 GPU 鎖" in warns[0]


def test_shared_still_used_when_present():
    shared = P.SHARED
    if not (shared / "gpu_lock.py").is_file():
        import pytest
        pytest.skip("這台沒有共用 GPU 鎖")
    r = run(shared)
    assert r.returncode == 0, r.stderr
    assert "MOD yt_gpu_lock" in r.stdout
    assert "改用本機簡化鎖" not in r.stderr
