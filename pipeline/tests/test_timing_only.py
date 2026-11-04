"""時長預檢(PLAN_TTS_FLOW T3)測試:build --check-only --timing-only 只給 script.json + timeline_tts.json、
完全沒有素材(圖、片段、clips)也能跑完,並回報同圖連續過久/過多句、鏡頭太短;--timing-only 單用要報錯。
素材根指到 tmp\\test_timing_only\\(環境變數 CLAUDE_VIDEO_ROOT),不碰正式 build\\、projects\\。
python -X utf8 pipeline/tests/test_timing_only.py(或 -m pytest)"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
REPO = PIPE.parent
TMP = REPO / "tmp" / "test_timing_only"


def _case(name, rows, anim_lines=()):
    """rows = [(圖名 或 None=影片標籤 v1, 秒數)];回傳 (script.json, timeline_tts.json, root)。"""
    root = TMP / name
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    lines, tl, t = [], [], 0.0
    for i, (img, dur) in enumerate(rows, 1):
        text = f"第{i}句旁白"
        ln = dict(text=text, **({"img": img} if img else {"v": "v1"}))
        if i in anim_lines:
            ln = dict(text=text, anim={"type": "stamp", "text": "X"})
        lines.append(ln)
        tl.append(dict(idx=i, text=text, start=t, end=t + dur - 0.1, visual_start=t, visual_end=t + dur, clauses=None))
        t += dur
    sp = root / "script.json"
    sp.write_text(json.dumps(dict(sections=[dict(name="s", lines=lines)]), ensure_ascii=False), encoding="utf-8")
    tp = root / "timeline_tts.json"
    tp.write_text(json.dumps(dict(fps=30, total=t, total_frames=round(t * 30), lines=tl), ensure_ascii=False), encoding="utf-8")
    return sp, tp, root


def _run(sp, tp, root, *flags):
    env = dict(os.environ, CLAUDE_VIDEO_ROOT=str(root), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "build.py"), "--script", str(sp), "--voice", "V", "--tag", "t",
                        "--out", "t.mp4", "--clips", "auto", "--timeline", str(tp), *flags],
                       cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_same_image_over_limit_without_any_media():
    """同圖連續 12 秒 / 3 句:沒有 images、raw、clips 也要跑完並報錯(不是報缺圖)。"""
    sp, tp, root = _case("long", [("a", 4.0), ("a", 4.0), ("a", 4.0), ("b", 4.0), (None, 20.0)])
    rc, out = _run(sp, tp, root, "--check-only", "--timing-only")
    assert rc == 1, out
    assert "同圖(a)連續 12.0 秒 > 9 秒" in out, out
    assert "連續超過 2 句" in out, out
    assert "不存在" not in out and "缺畫面" not in out and "挑不到" not in out, out   # 缺素材不算錯
    assert "錯誤 2" in out or "錯誤 3" in out, out
    assert not (root / "build" / "t" / "plan.json").exists()   # 不覆寫正式鏡頭計畫


def test_clean_script_passes_and_short_shot_flagged():
    sp, tp, root = _case("ok", [("a", 4.0), ("b", 4.0), (None, 20.0)])
    rc, out = _run(sp, tp, root, "--check-only", "--timing-only")
    assert rc == 0 and "錯誤 0" in out, out
    sp, tp, root = _case("short", [("a", 4.0), ("b", 1.0), ("c", 4.0)])   # 圖片鏡頭 1 秒 < 最短(相鄰無影片可借)
    rc, out = _run(sp, tp, root, "--check-only", "--timing-only")
    assert rc == 1 and "圖片鏡頭 1.00 秒" in out, out


def test_anim_dwell_checked():
    """check_anim 保留:動畫鏡頭太短(最後一步後停留不足)要報錯。"""
    sp, tp, root = _case("anim", [("a", 4.0), ("a", 1.0), ("b", 4.0)], anim_lines=(2,))
    rc, out = _run(sp, tp, root, "--check-only", "--timing-only")
    assert rc == 1 and "動畫鏡頭 1.00 秒" in out and "停留" in out, out


def test_make_version_timing_errors_of():
    """make_version 的時長預檢輸出 -> timing_errors:取「錯誤:」行;沒跑成(結束碼非 0 卻無錯誤行)也要記一筆,不能當通過。"""
    sys.path.insert(0, str(PIPE))
    import make_version as MV
    tail = ["鏡頭時長: …", "錯誤: 句1-3: 同圖(a)連續 12.0 秒 > 9 秒", "錯誤: 句5: 圖片鏡頭 1.00 秒 < 最短 3.2 秒", "時長預檢(--timing-only): 錯誤 2"]
    assert MV.timing_errors_of(1, tail) == ["句1-3: 同圖(a)連續 12.0 秒 > 9 秒", "句5: 圖片鏡頭 1.00 秒 < 最短 3.2 秒"]
    assert MV.timing_errors_of(0, ["時長預檢: 錯誤 0"]) == []
    crash = MV.timing_errors_of(1, ["Traceback", "FileNotFoundError: timeline_tts.json"])
    assert len(crash) == 1 and "執行失敗" in crash[0] and "FileNotFoundError" in crash[0]


def test_timing_only_requires_check_only():
    sp, tp, root = _case("flag", [("a", 4.0)])
    rc, out = _run(sp, tp, root, "--timing-only")
    assert rc == 2 and "--timing-only 只能與 --check-only 併用" in out, out


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("OK", n)
