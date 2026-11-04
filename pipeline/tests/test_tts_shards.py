"""tts_cosy3 多 GPU 分片(Kaggle T4x2)測試:假 executor、不載模型。
python -X utf8 -m pytest pipeline/tests/test_tts_shards.py(要用 tts_env_chattts 的 python:import tts_cosy3)。"""
import hashlib
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))

import tts_asr as TA  # noqa: E402
import tts_cosy3 as C3  # noqa: E402
import tts_pause as TP  # noqa: E402

MAX_RETRY = 4


# ------------------------------------------------------------ 平台判定 / 卡號 / 快取鍵
@pytest.fixture
def env(monkeypatch):
    for k in ("KAGGLE_KERNEL_RUN_TYPE", "CV_REMOTE_PLATFORM", "CV_TTS_GPUS", "CUDA_VISIBLE_DEVICES"):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_shard_gpus_only_kaggle(env):
    assert C3.shard_gpus("cuda", count=2) == 1                 # 本機 / Colab:舊路徑
    env.setenv("KAGGLE_KERNEL_RUN_TYPE", "Batch")
    assert C3.shard_gpus("cuda", count=2) == 2
    assert C3.shard_gpus("cuda", count=1) == 1                 # 只偵測到一張卡
    assert C3.shard_gpus("cpu", count=2) == 1
    env.setenv("CV_TTS_GPUS", "1")                             # 關分片
    assert C3.shard_gpus("cuda", count=2) == 1
    env.setenv("CV_TTS_GPUS", "x")                             # 非整數忽略 -> 預設 2
    assert C3.shard_gpus("cuda", count=2) == 2
    env.delenv("CV_TTS_GPUS")
    env.setenv("CV_REMOTE_PLATFORM", "colab")                  # 強制 Colab
    assert C3.shard_gpus("cuda", count=2) == 1
    env.delenv("KAGGLE_KERNEL_RUN_TYPE")
    env.setenv("CV_REMOTE_PLATFORM", "kaggle")
    assert C3.shard_gpus("cuda", count=2) == 2


def test_gpu_ids(env):
    assert C3.gpu_ids(2) == ["0", "1"]
    env.setenv("CUDA_VISIBLE_DEVICES", "3, 5")
    assert C3.gpu_ids(2) == ["3", "5"]


def test_resume_key_device_normalized():
    old = hashlib.sha1(json.dumps([C3.RESUME_VER, "好。", 1, "1.18", "ref_b.wav", "稿", "cuda"],
                                  ensure_ascii=False).encode("utf-8")).hexdigest()
    k = C3.resume_key("好。", 1, 1.18, "ref_b.wav", "稿", "cuda")
    assert k == old                                            # 既有快取鍵逐位元不變
    assert k == C3.resume_key("好。", 1, 1.18, "ref_b.wav", "稿", "cuda:0") == C3.resume_key("好。", 1, 1.18, "ref_b.wav", "稿", "cuda:1")
    assert k != C3.resume_key("好。", 1, 1.18, "ref_b.wav", "稿", "cpu")


# ------------------------------------------------------------ 假 executor 與縮小版主流程(同 tts_cosy3.main 的分派寫法)
def fake_attempt(j, seed, speed):
    """依 (句, seed) 決定結果:確定性,與哪張卡無關(模擬兩張同型 T4)。"""
    h = int(hashlib.sha1(f"{j['k']}:{seed}:{speed:g}".encode()).hexdigest(), 16)
    ok = (h % 3 == 0) or j["k"] % 5 == 0
    asr = j["text"] + ("" if h % 7 else "錯")
    m = dict(seed=seed, speed=speed, fails=[] if ok else ["sim"], score=(h % 100) / 100, asr=asr, cps=4 + (h % 10) / 10,
             asr2_bad=None)
    return np.full(8, h % 97, dtype=np.float32), m


class FakeEx:
    """遠端分片的替身:make 回 (w, m, hit),記經手的句子。"""

    def __init__(self, name):
        self.name, self.seen = name, []

    def make(self, j, seed, speed):
        time.sleep(0.001)
        self.seen.append(j["k"])
        w, m = fake_attempt(j, seed, speed)
        return w, m, False


def pipeline(shards, n=24):
    """pass1 -> 主品管重錄 -> 雙辨識 -> 整批一致性(全部句子一次)-> 不一致重錄;回傳 (每句最終狀態, 一致性呼叫紀錄)。"""
    jobs = [dict(k=k, text=f"第{k}句。") for k in range(n)]
    local = []

    def make(j, seed, speed):
        ex = getattr(C3._tl, "ex", None)
        if ex:
            w, m, _ = ex.make(j, seed, speed)
            return w, m
        time.sleep(0.001)
        local.append(j["k"])
        return fake_attempt(j, seed, speed)

    def next_seed(r):
        used = {t["seed"] for t in r["tries"]}
        k = 1
        while 2024 + 1009 * k in used:
            k += 1
        return 2024 + 1009 * k

    def retry2(r):
        w, m = make(r["job"], next_seed(r), 1.18)
        return w, m, not m["fails"]

    res = [None] * n

    def first(j):
        w, m = make(j, 2024, 1.18)
        res[j["k"]] = dict(job=j, w=w, m=m, tries=[m], ok=not m["fails"])
    kof = lambda r: r["job"]["k"]  # noqa: E731
    shards.par(jobs, first, key=lambda j: j["k"])
    shards.par([r for r in res if not r["ok"]], lambda r: TP.retry_best(r, retry2, MAX_RETRY, lambda m, t: False), key=kof)

    class FakeSec:
        def __init__(self):
            self.pending = []

        def submit(self, m, text, x16):
            self.pending.append(m)

        def collect(self):
            for m in self.pending:
                m.update(asr2=m["asr"], asr2_sim=m["score"], asr2_bad=m["asr"].endswith("錯"))
            self.pending.clear()

    TA.dual_phase(res, FakeSec(), retry2, MAX_RETRY, lambda r: r["job"]["text"], lambda w: w,
                  par=(lambda xs, f: shards.par(xs, f, kof)) if shards.n > 1 else None)

    calls = []

    def inconsistent(items):   # 替身:多數寫法用全片句子算(與 TQ.inconsistent 同介面的最小版)
        calls.append(len(items))
        bad = [k for k, _, asr in items if asr and asr.endswith("錯")]
        return {k: [dict(term="x", got="錯")] for k in bad}, {}, None

    incon, _, _ = inconsistent([(k, r["job"]["text"], r["m"].get("asr")) for k, r in enumerate(res)])

    def incon1(x):
        k, _ = x
        r = res[k]
        while len(r["tries"]) - 1 < MAX_RETRY:
            w, m = make(r["job"], next_seed(r), 1.18)
            r["tries"].append(m)
            if not m["fails"] and not m["asr"].endswith("錯"):
                r["w"], r["m"], r["ok"] = w, m, True
                break
    shards.par(incon.items(), incon1, key=lambda x: x[0])
    final = [dict(ok=r["ok"], seed=r["m"]["seed"], w=float(r["w"][0]), tries=[t["seed"] for t in r["tries"]],
                  asr2_bad=r["m"].get("asr2_bad")) for r in res]
    return final, calls, local


def test_sharded_equals_single():
    single, calls1, _ = pipeline(C3.Shards())
    ex = FakeEx("g1")
    sh = C3.Shards([ex])
    multi, calls2, local = pipeline(sh)
    assert multi == single                                     # 合併後每句結果與單 GPU 相同
    assert calls1 == calls2 == [24]                            # 一致性只在合併後對全部 24 句跑一次
    assert ex.seen and local                                   # 兩片都有拿到工作(共用佇列)
    summ = sh.summary()
    assert [s["gpu"] for s in summ] == [0, 1] and sum(s["tasks"] for s in summ) > 24
    assert all(s["lines"] > 0 for s in summ)


def test_single_shard_is_plain_loop():
    order = []
    sh = C3.Shards()
    sh.par(range(5), order.append)
    assert order == [0, 1, 2, 3, 4] and sh.n == 1
    assert threading.current_thread() is threading.main_thread()


def test_par_propagates_exit():
    sh = C3.Shards([FakeEx("g1")])

    def body(x):
        if x == 3:
            sys.exit("合成失敗")
    with pytest.raises(SystemExit):
        sh.par(range(10), body)


def test_log_prefix(capsys):
    sh = C3.Shards([FakeEx("g1")])
    sh.par(range(4), lambda x: (time.sleep(0.01), C3.log(f"x{x}")))
    err = capsys.readouterr().err
    assert all(line[:4] in ("[g0]", "[g1]") for line in err.splitlines())
    C3.log("主執行緒")
    assert capsys.readouterr().err == "主執行緒\n"             # 單 GPU / 主執行緒:無前綴
