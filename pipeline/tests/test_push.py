"""鏡頭間 0.2 秒輕推移(六項 D):靜態→靜態才推、--no-push / push:false 關閉、文字離邊限制自動減小、濾鏡式:
python -X utf8 pipeline\tests\test_push.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build as B  # noqa: E402


def _s(i, kind="image", special=None, fx="none"):
    return dict(line=i, kind=kind, special=special, fx=fx, frames=90)


def test_static_to_static_only():
    shots = [_s(1, "video"), _s(2, special="quote"), _s(3, special="quote"), _s(4, special="anim"), _s(5, special="quote")]
    out = B.plan_push(shots, [dict(idx=i) for i in range(1, 6)], Path("."))
    assert [s["push"] for s in shots] == [0.0, 0.0, B.PUSH_Z, 0.0, 0.0]     # 只有 2→3(quote→quote);片段 / 動畫兩側都不推
    assert len(out) == 1 and out[0][:2] == (2, 3)


def test_off_switches():
    shots = [_s(1, special="quote"), _s(2, special="quote")]
    B.plan_push(shots, [dict(idx=1), dict(idx=2)], Path("."), enabled=False)
    assert shots[1]["push"] == 0.0
    B.plan_push(shots, [dict(idx=1), dict(idx=2, push=False)], Path("."))
    assert shots[1]["push"] == 0.0


def test_filter_expr():
    f = B._punch_filter([], 1.02)
    assert "pow(1-clip(on/" in f and "0.02000" in f
    assert "pow(" not in B._punch_filter([0.5])


if __name__ == "__main__":
    for _n, _f in list(globals().items()):
        if _n.startswith("test_"):
            _f()
    print("test_push: all passed")
