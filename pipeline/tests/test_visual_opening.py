"""visual_check 警告 O(開場文字卡連續 >= 3)、Q(引言卡缺 who)測試:python -X utf8 -m pytest pipeline/tests/test_visual_opening.py -q
script.txt 寫在 tmp\test_visual_opening\。"""
import shutil
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import visual_check as VC  # noqa: E402

TMP = PIPE.parent / "tmp" / "test_visual_opening"
DEFS = """@def quote:a={"who":"某總監","text":"原話。","src":"訪談"}
@def quote:b={"text":"沒說話者。","src":"訪談"}
"""


def _codes(body):
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True)
    src = TMP / "script.txt"
    src.write_text("# 測試 T\n" + DEFS + "# 一\n" + body, encoding="utf-8")
    top, defs, notes, lines = VC.load("t", src)
    W, E, _ = VC.check("t", top, defs, notes, lines, None)
    shutil.rmtree(TMP, ignore_errors=True)
    return [(c, i) for c, i, _ in W if c in ("O", "Q")], E


def test_opening_three_text_cards_warns():
    w, E = _codes("img:a|一。\nquote:a|二。\nimg:b|三。\nclipx|四。\nclipx|五。\nclipx|六。\n")
    assert w == [("O", 1)] and not E


def test_opening_two_text_cards_ok_and_late_run_ignored():
    w, _ = _codes("img:a|一。\nquote:a|二。\nclipx|三。\nclipx|四。\nclipx|五。\nclipx|六。\nimg:a|七。\nimg:b|八。\nimg:c|九。\n")
    assert w == []


def test_opening_run_cut_at_sixth_line():
    w, _ = _codes("clipx|一。\nclipx|二。\nclipx|三。\nclipx|四。\nimg:a|五。\nimg:b|六。\nimg:c|七。\n")
    assert w == []


def test_quote_without_who_warns_once():
    w, _ = _codes("clipx|一。\nquote:b|二。\nclipx|三。\nquote:b|四。\nclipx|五。\nquote:a|六。\n")
    assert w == [("Q", 2)]
