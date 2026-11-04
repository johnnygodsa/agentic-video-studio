"""C 段改句迴圈:line_fix 改 script.txt 後,重跑的 make_version --tts-review 第一步必須是 txt2json(重轉 script.json),且不帶 --img-prefix 也找得到前綴。
python -X utf8 -m pytest pipeline/tests/test_c_loop_retransform.py -q"""
import subprocess
import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
import make_version as MV  # noqa: E402
import paths  # noqa: E402


def test_script_img_prefix_reads_note(monkeypatch, tmp_path):
    (tmp_path / "t1").mkdir()
    monkeypatch.setattr(paths, "REPO", tmp_path)
    f = tmp_path / "t1" / "script.txt"
    f.write_text("# 標題\n# 截圖(前綴 ain_,英日韓文頁):a=x\nimg:a|句。\n", encoding="utf-8")
    assert MV.script_img_prefix("t1") == "ain_"
    f.write_text("# 畫面標籤:x;img:* 截圖(assets,前綴 bw_)\n", encoding="utf-8")
    assert MV.script_img_prefix("t1") == "bw_"
    f.write_text("# 圖檔前綴:cp25_\n", encoding="utf-8")
    assert MV.script_img_prefix("t1") == "cp25_"
    f.write_text("# 沒有\nimg:a|前綴 zz_ 在句子裡不算。\n", encoding="utf-8")
    assert MV.script_img_prefix("t1") is None
    assert MV.script_img_prefix("nope") is None


def test_tts_review_first_step_is_txt2json_without_img_prefix():
    tag = "ai_nextfest"
    if not (paths.REPO / tag / "script.txt").exists():
        pytest.skip(f"{tag}/script.txt 不在")
    r = subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "make_version.py"), "--tag", tag, "--ver", "v9", "--tts-review", "--dry-run"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(paths.REPO))
    steps = [l for l in r.stdout.splitlines() if l.startswith("[1/")]
    assert r.returncode == 0 and steps and "script_txt2json" in steps[0] and "--img-prefix ain_" in steps[0], r.stdout[-400:] + r.stderr[-400:]
