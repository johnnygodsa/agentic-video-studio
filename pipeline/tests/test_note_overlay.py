"""影片片段鏡頭右上角的 note 小字(note_events / note_wrap / write_ass 的 Note 事件):
python -X utf8 pipeline\tests\test_note_overlay.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build as B  # noqa: E402
import paths as P  # noqa: E402

F = B.FPS


def _shot(f0, n, kind="video", special=None):
    return dict(f0=f0, frames=n, kind=kind, special=special)


def test_events_video_only_and_merge():
    shots = [_shot(0, 90), _shot(90, 90), _shot(180, 60, "image"), _shot(240, 60, "image", "anim"), _shot(300, 60)]
    lines = [dict(idx=1, f0=0, f1=180, note="據報 彭博"),        # 兩個影片鏡頭 -> 併成一段
             dict(idx=2, f0=180, f1=240, note="Kotaku"),          # 圖片 -> 不畫
             dict(idx=3, f0=240, f1=300, note="Wikipedia"),       # anim -> 不畫
             dict(idx=4, f0=300, f1=360, note=""),                # 空 note -> 不畫
             dict(idx=5, f0=300, f1=360)]                         # 沒 note -> 不畫
    assert B.note_events(lines, shots) == [(0.0, 6.0, "據報 彭博")]


def test_events_partial_overlap():
    shots = [_shot(0, 60, "image"), _shot(60, 60)]
    lines = [dict(idx=1, f0=30, f1=120, note="美聯社")]   # 句跨圖片與影片:只畫影片那段
    assert B.note_events(lines, shots) == [(2.0, 4.0, "美聯社")]


def test_wrap():
    assert B.note_wrap("據報  彭博") == "據報 彭博"
    long = "匿名知情人士 彭博 經 Eurogamer 引述 " * 3
    out = B.note_wrap(long)
    assert "\\N" in out and all(B.note_text_width(x) <= B.NOTE_MAX_PX for x in out.split("\\N"))
    assert "\\N" in B.note_wrap("字" * 40)          # 沒空白:字數中點


def test_ea_me5_build_data():
    """用既有 build/ea_me5 的時間軸:句 1、句 8 有小字,anim / img 句沒有。"""
    tl_p = P.REPO / "build" / "ea_me5" / "timeline.json"
    sc_p = P.REPO / "ea_me5" / "script.json"
    if not (tl_p.exists() and sc_p.exists()):
        return
    tl = json.loads(tl_p.read_text(encoding="utf-8"))
    notes = {l["idx"]: l.get("note") for l in B.load_lines(sc_p)}
    shots = [dict(f0=round(s["start"] * F), frames=round((s["end"] - s["start"]) * F), kind=s["kind"], special=s["special"])
             for s in tl["shots"]]
    lines = [dict(idx=l["idx"], f0=round(l["visual_start"] * F), f1=round(l["visual_end"] * F), note=notes.get(l["idx"]))
             for l in tl["lines"]]
    ev = B.note_events(lines, shots)
    by = {}
    for s, e, t in ev:
        for ln in lines:
            if ln["f0"] / F - 1e-6 <= s and e <= ln["f1"] / F + 1e-6 and ln["note"] == t:
                by.setdefault(ln["idx"], []).append((s, e))
    assert by[1] == [(0.0, 7.2)]
    assert 8 in by and abs(by[8][0][0] - 44.1667) < 0.01 and abs(by[8][0][1] - 47.9) < 0.01
    for i in (2, 5, 6, 7, 9, 12):    # img / anim 句
        assert i not in by


if __name__ == "__main__":
    import tempfile
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v(Path(tempfile.mkdtemp())) if "tmp_path" in v.__code__.co_varnames[:1] else v()
    print("ok")
