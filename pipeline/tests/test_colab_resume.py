"""tts_cosy3 嘗試層級續跑快取(TTS_RESUME_DIR)測試:假 Worker、不載模型。
python -X utf8 -m pytest pipeline/tests/test_colab_resume.py(要用 tts_env_chattts 的 python:import tts_cosy3)。"""
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))

import tts_cosy3 as C3  # noqa: E402

TMP = PIPE.parent / "tmp" / "test_colab_resume"


class FakeWorker:
    """依 (文字, seed, speed) 產生確定的 raw wav;記合成呼叫次數。"""

    def __init__(self):
        self.n = 0

    def call(self, text, seed, speed, out):
        self.n += 1
        rng = np.random.default_rng(abs(hash((text, seed, speed))) % 2**32)
        sf.write(out, rng.standard_normal(2400).astype(np.float32) * 0.1, C3.SR)
        return dict(ok=True)


ATTEMPTS = [("第一句。", 2024, 1.18), ("第二句。", 2024, 1.18), ("第二句。", 7, 1.18), ("第三句。", 2024, 1.3)]


def _run(worker, rdir, out_dir):
    """模擬 make() 的合成步:每次嘗試寫 out_dir/<k>.raw.wav;回傳 (沿用次數, 各輸出位元)。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    hits, data = 0, []
    for k, (text, seed, speed) in enumerate(ATTEMPTS):
        raw = out_dir / f"{k}.raw.wav"
        key = rdir and C3.resume_key(text, seed, speed, "ref_b.wav", "參考逐字稿", "cuda")
        res, hit = C3.synth_one(worker, rdir, key, text, seed, speed, raw)
        assert res["ok"]
        hits += hit
        data.append(raw.read_bytes())
    return hits, data


def _env(**kw):
    keep = {k: os.environ.get(k) for k in kw}
    for k, v in kw.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    return keep


def test_resume_second_run_no_synth_same_bytes():
    shutil.rmtree(TMP, ignore_errors=True)
    keep = _env(TTS_RESUME_DIR=str(TMP / "resume"))
    try:
        rdir = C3.resume_dir("fake_tag")
        assert rdir == TMP / "resume" / "fake_tag"
        w1 = FakeWorker()
        h1, d1 = _run(w1, rdir, TMP / "run1")
        assert (w1.n, h1) == (len(ATTEMPTS), 0)
        assert C3.resume_status(rdir)[0] == len(ATTEMPTS) and not list(rdir.glob("*.part"))
        w2 = FakeWorker()   # 「斷線後重跑」:新行程、新的 _cosy_work
        h2, d2 = _run(w2, rdir, TMP / "run2")
        assert (w2.n, h2) == (0, len(ATTEMPTS)) and d1 == d2
    finally:
        _env(**keep)
        shutil.rmtree(TMP, ignore_errors=True)


def test_resume_key_changes_with_params():
    base = C3.resume_key("好。", 1, 1.18, "ref_b.wav", "稿", "cuda")
    assert base == C3.resume_key("好。", 1, 1.18, "ref_b.wav", "稿", "cuda")
    others = [C3.resume_key("壞。", 1, 1.18, "ref_b.wav", "稿", "cuda"), C3.resume_key("好。", 2, 1.18, "ref_b.wav", "稿", "cuda"),
              C3.resume_key("好。", 1, 1.3, "ref_b.wav", "稿", "cuda"), C3.resume_key("好。", 1, 1.18, "ref_a.wav", "稿", "cuda"),
              C3.resume_key("好。", 1, 1.18, "ref_b.wav", "別稿", "cuda"), C3.resume_key("好。", 1, 1.18, "ref_b.wav", "稿", "cpu")]
    assert base not in others and len(set(others)) == len(others)


def test_no_env_no_dir():
    shutil.rmtree(TMP, ignore_errors=True)
    keep = _env(TTS_RESUME_DIR=None)
    try:
        rdir = C3.resume_dir("fake_tag")
        assert rdir is None
        w = FakeWorker()
        h, _ = _run(w, rdir, TMP / "run")
        assert (w.n, h) == (len(ATTEMPTS), 0)
        assert sorted(p.name for p in TMP.iterdir()) == ["run"]   # 只有輸出,沒建任何快取目錄
    finally:
        _env(**keep)
        shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    n = 0
    for k, fn in list(globals().items()):
        if k.startswith("test_") and callable(fn):
            fn()
            n += 1
    print(f"test_colab_resume: {n} 項通過")


def test_env_limit(monkeypatch):
    """CV_TTS_MAX_RETRY / CV_TTS_RATE_SEEDS -> argparse 預設值:夾到 1–12,非整數忽略。"""
    monkeypatch.setenv("CV_TTS_MAX_RETRY", "99")
    assert C3.env_limit("CV_TTS_MAX_RETRY", 6) == 12
    monkeypatch.setenv("CV_TTS_MAX_RETRY", "abc")
    assert C3.env_limit("CV_TTS_MAX_RETRY", 6) == 6
    monkeypatch.setenv("CV_TTS_RATE_SEEDS", "0")
    assert C3.env_limit("CV_TTS_RATE_SEEDS", 6) == 1
    monkeypatch.delenv("CV_TTS_RATE_SEEDS")
    assert C3.env_limit("CV_TTS_RATE_SEEDS", 6) == 6
