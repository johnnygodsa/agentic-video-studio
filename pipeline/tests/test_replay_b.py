"""B 段確定性檢查回歸(pytest 包裝,見 replay_b.py)。已發片 script.txt 不在就 skip。
python -X utf8 -m pytest pipeline/tests/test_replay_b.py -q"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay_b as R  # noqa: E402
import paths as P  # noqa: E402


def test_no_regression_vs_baseline():
    missing = [t for t in R.DEFAULT_TAGS if not (P.REPO / t / "script.txt").exists()]
    if missing:
        pytest.skip(f"script.txt 不存在:{missing}")
    base = R.load_baseline()
    if not base:
        pytest.skip("沒有基線,先跑 replay_b.py --update-baseline")
    results, touched = R.run_tags(R.DEFAULT_TAGS)
    assert not touched, f"工具寫了檔:{touched}"
    reg = R.compare(results, base)
    assert not reg, f"回歸:{reg}"
