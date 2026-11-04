"""tts_report 在 --tts-only 產物上可跑:假 build 目錄只有 timeline_tts.json + tts 目錄的 <句>.line.wav(沒有 timeline.json / voice.wav)。
全寫 tmp\test_tts_report_tts_only\(替身 paths.BUILD / PROJECTS)。python -X utf8 pipeline/tests/test_tts_report_tts_only.py(或 -m pytest)"""
import json
import shutil
import sys
import wave
from pathlib import Path

import numpy as np

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import paths as P  # noqa: E402
import tts_report as T  # noqa: E402

TMP = PIPE.parent / "tmp" / "test_tts_report_tts_only"
SR = 48000


def _wav(path, x):
    pcm = np.repeat((np.clip(x, -1, 1) * 32767).astype("<i2")[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _fake_build(tag):
    shutil.rmtree(TMP, ignore_errors=True)
    bd = TMP / "build" / tag
    td = bd / "tts_cosy3"
    td.mkdir(parents=True)
    (bd / "tts_qc.json").write_text(json.dumps({"records": [{"engine": "cosy3"}]}), encoding="utf-8")
    # 一行兩子句:0.5s 音 + 0.4s 靜音 + 0.5s 音
    t = np.arange(int(0.5 * SR)) / SR
    tone = 0.5 * np.sin(2 * np.pi * 440 * t)
    _wav(td / "001.line.wav", np.concatenate([tone, np.zeros(int(0.4 * SR)), tone]))
    cl = [dict(text="第一段", start=0.5, end=1.0, gap=0.4), dict(text="第二段", start=1.4, end=1.9, gap=0.0)]
    tl = dict(fps=30, total=2.0, lines=[dict(idx=1, text="第一段第二段", start=0.5, end=1.9, clauses=cl),
                                        dict(idx=2, text="單句", start=2.0, end=2.5, clauses=None)])
    (bd / "timeline_tts.json").write_text(json.dumps(tl), encoding="utf-8")
    unit = dict(idx="1.1", text="x", cps=6.0, rate_ok=True, rate_dev=0.0, source="synth")
    (td / "_jobs.qc.json").write_text(json.dumps({"lines": [unit], "failed": []}), encoding="utf-8")
    return bd


def test_tts_only_dir_runs():
    tag = "faketag"
    _fake_build(tag)
    old = P.BUILD, P.PROJECTS
    P.BUILD, P.PROJECTS = TMP / "build", TMP / "projects"
    old_argv = sys.argv
    try:
        sys.argv = ["tts_report.py", tag]
        T.main()
    finally:
        P.BUILD, P.PROJECTS = old
        sys.argv = old_argv
    rep = json.loads((TMP / "projects" / tag / "tts_report.json").read_text(encoding="utf-8"))
    assert rep["boundaries"] == 1
    assert abs(rep["boundary_list"][0]["silence_s"] - 0.4) < 0.03   # 量到句界靜音 ≈ 0.4 秒(拼接位置正確)
    assert rep["units"] == 1


def test_stale_timeline_json_ignored():
    """timeline.json(+voice.wav)比 timeline_tts.json 舊 = 上一版渲染殘留,不可用。"""
    import os
    tag = "faketag"
    bd = _fake_build(tag)
    (bd / "timeline.json").write_text(json.dumps({"lines": []}), encoding="utf-8")
    _wav(bd / "voice.wav", np.zeros(SR))
    new = (bd / "timeline_tts.json").stat().st_mtime + 100
    os.utime(bd / "timeline.json", (new - 1000, new - 1000))
    os.utime(bd / "voice.wav", (new - 1000, new - 1000))
    old = P.BUILD
    P.BUILD = TMP / "build"
    try:
        tl, x, sr = T.load_timeline_voice(tag)
    finally:
        P.BUILD = old
    assert len(tl["lines"]) == 2 and len(x) >= SR


if __name__ == "__main__":
    test_tts_only_dir_runs()
    test_stale_timeline_json_ignored()
    print("OK")
