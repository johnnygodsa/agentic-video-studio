"""eye.py 測試:python -X utf8 -m pytest pipeline/tests/test_eye.py -q
不依賴真成片:用 ffmpeg 在 tmp_path 產 6 秒測試片;解析函式用固定 stderr 字串。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "senses"))

import eye  # noqa: E402
import paths  # noqa: E402

TAG = "demo"


def _ff(*args):
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.fixture
def env(monkeypatch, tmp_path):
    for attr, sub in (("PROJECTS", "projects"), ("BUILD", "build"), ("OUTPUT", "output")):
        monkeypatch.setattr(paths, attr, tmp_path / sub)
    (tmp_path / "output" / TAG).mkdir(parents=True)
    return tmp_path


@pytest.fixture(scope="module")
def black_mp4(tmp_path_factory):
    p = tmp_path_factory.mktemp("v") / "black.mp4"
    _ff("-f", "lavfi", "-i", "color=c=black:s=320x240:d=6:r=25", "-f", "lavfi", "-i", "sine=f=440:d=6",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(p))
    return p


@pytest.fixture(scope="module")
def src_mp4(tmp_path_factory):
    p = tmp_path_factory.mktemp("v") / "testsrc.mp4"
    _ff("-f", "lavfi", "-i", "testsrc=s=320x240:d=6:r=25", "-f", "lavfi", "-i", "sine=f=440:d=6",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(p))
    return p


def test_parse_blackdetect():
    t = "[blackdetect @ 0x1] black_start:2.5 black_end:4.04 black_duration:1.54\nblack_start:8 black_end:9.5"
    assert eye.parse_blackdetect(t) == [(2.5, 4.04), (8.0, 9.5)]


def test_parse_freezedetect():
    t = ("[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 3.2\n"
         "[freezedetect @ 0x1] lavfi.freezedetect.freeze_duration: 11.5\n"
         "[freezedetect @ 0x1] lavfi.freezedetect.freeze_end: 14.7\n"
         "[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 20")
    assert eye.parse_freezedetect(t, total=35) == [(3.2, 11.5), (20.0, 15.0)]


def test_parse_silencedetect_and_speech_starts():
    t = ("[silencedetect @ 0x1] silence_start: 0\n[silencedetect @ 0x1] silence_end: 1.2 | silence_duration: 1.2\n"
         "[silencedetect @ 0x1] silence_start: 5.0\n[silencedetect @ 0x1] silence_end: 6.5 | silence_duration: 1.5\n"
         "[silencedetect @ 0x1] silence_start: 9.0")
    s = eye.parse_silencedetect(t)
    assert s == [(0.0, 1.2), (5.0, 6.5), (9.0, None)]
    assert eye.speech_starts(s, 10.0) == [1.2, 6.5]
    assert eye.speech_starts([(3.0, 4.0)], 10.0) == [0.0, 4.0]


def test_parse_ebur128():
    t = ("[Parsed_ebur128_0 @ 0x1] t: 1 I: -30.0 LUFS\n[Parsed_ebur128_0 @ 0x1] Summary:\n\n"
         "  Integrated loudness:\n    I:         -14.3 LUFS\n    Threshold: -24.3 LUFS\n")
    assert eye.parse_ebur128(t) == -14.3
    assert eye.parse_ebur128("nothing") is None


def test_parse_chapters():
    md = "x\n```text\n【YouTube章節摘要】\n00:00 開場\n05:44 結尾\n1:02:03 長\n【業配區間】\n09:59 不算\n```"
    assert eye.parse_chapters(md) == [(0, "開場"), (344, "結尾"), (3723, "長")]
    assert eye.parse_chapters("沒有") == []


def test_black_detected(black_mp4):
    ok, note = eye.check_black(black_mp4, 6.0)
    assert not ok and "黑場" in note


def test_testsrc_no_false_positive(src_mp4):
    dur = eye.probe_duration(src_mp4)
    assert eye.check_black(src_mp4, dur)[0]
    assert eye.check_freeze(src_mp4, dur)[0]


def test_freeze_detected(tmp_path):
    p = tmp_path / "still.mp4"
    _ff("-f", "lavfi", "-i", "color=c=red:s=320x240:d=12:r=25", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p))
    ok, note = eye.check_freeze(p, 12.0)
    assert not ok and "靜止" in note


def test_ffmpeg_failure_is_item_not_exception(tmp_path):
    bad = tmp_path / "nope.mp4"
    bad.write_bytes(b"not a video")
    ok, note = eye.check_black(bad, None)
    assert not ok and "ffmpeg 失敗" in note
    assert not eye.check_lufs(bad)[0]


def test_lufs_on_sine(src_mp4):
    ok, note = eye.check_lufs(src_mp4)
    assert "LUFS" in note  # 數值不限,只驗有解析出來


def test_tail_and_chapters(env):
    tl = {"total": 100.0, "lines": [{"idx": 1, "start": 0.0, "end": 50.0}, {"idx": 2, "start": 50.0, "end": 99.0}]}
    assert eye.check_tail(101.0, tl)[0]
    assert not eye.check_tail(110.0, tl)[0]
    notes = paths.output_dir(TAG) / "v1_說明.md"
    notes.write_text("```text\n【YouTube章節摘要】\n00:00 開\n00:50 中\n【業配區間】\n```", encoding="utf-8")
    assert eye.check_chapters(TAG, "v1", tl)[0]
    notes.write_text("```text\n【YouTube章節摘要】\n00:00 開\n01:10 錯\n【業配區間】\n```", encoding="utf-8")
    assert not eye.check_chapters(TAG, "v1", tl)[0]
    notes.write_text("沒有章節", encoding="utf-8")
    ok, note = eye.check_chapters(TAG, "v1", tl)
    assert ok and "略過" in note


def test_main_writes_json_and_exit_code(env, src_mp4):
    (env / "output" / TAG / f"{TAG}_v1.mp4").write_bytes(src_mp4.read_bytes())
    tlf = paths.build_dir(TAG) / "timeline_tts.json"
    tlf.parent.mkdir(parents=True)
    tlf.write_text(json.dumps({"total": 6.0, "lines": [{"idx": 1, "start": 0.0, "end": 6.0}]}), encoding="utf-8")
    rc = eye.main(["--tag", TAG, "--ver", "v1"])
    res = json.loads((paths.PROJECTS / TAG / "eye_v1.json").read_text(encoding="utf-8"))
    assert [i["id"] for i in res["items"]] == ["black", "freeze", "lufs", "sync", "tail", "chapters"]
    assert rc == (0 if res["ok"] else 1)
    assert eye.main(["--tag", TAG, "--ver", "v9"]) == 1  # 沒有成片
