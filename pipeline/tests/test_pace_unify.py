"""語速常數統一測試(channel/_archive/plans/PLAN_文案資料驅動_2026-10-26.md §3.6):spec_check / style_metrics / visual_check 都引用 pace.py。
PYTHONPATH=<repo> python3 -X utf8 -m pytest pipeline/tests/test_pace_unify.py -q"""
import re
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import pace  # noqa: E402
import spec_check as SC  # noqa: E402
import visual_check as VC  # noqa: E402


def test_spec_check_cps_is_pace():
    assert SC.CPS == pace.CHARS_PER_SEC == 5.5


def test_spec_check_table_uses_pace():
    lines = [{"text": "字" * 11}] * 10                      # 110 字 → 20 秒
    spec = {"targets": {"len_s": [19, 21], "judgment_by_s": 4}, "judgment_line": 2}
    rows = {r[0]: r for r in SC.table(spec, lines)}
    assert rows["估計片長"][2] == "20s(110字)" and rows["估計片長"][3] == "ok"
    assert rows["判斷句秒數"][2] == "約4s" and rows["判斷句秒數"][3] == "ok"    # 22 字 ÷ 5.5 = 4.0


def test_visual_check_est_from_pace():
    assert abs(VC.CFG["est_sec_per_char"] - 1 / pace.CHARS_PER_SEC) < 1e-12


def test_style_metrics_no_hardcoded_cps():
    src = (PIPE / "style_metrics.py").read_text(encoding="utf-8")
    assert "pace.CHARS_PER_SEC" in src and not re.search(r"/\s*6\.5", src)
