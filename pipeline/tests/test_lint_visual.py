"""script_lint 畫面單調警告測試:python -X utf8 pipeline\tests\test_lint_visual.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import script_lint as L  # noqa: E402


def mk(*lines):
    return [(i + 1, d) for i, d in enumerate(lines)]


def test_three_images_warn():
    w = L.visual_warnings(mk({"img": "a"}, {"img": "b"}, {"img": "c"}))
    assert [x[0] for x in w] == ["連續 3 個鏡頭同類畫面"] and len(w[0][1]) == 1


def test_clip_between_resets():
    assert L.visual_warnings(mk({"img": "a"}, {"img": "b"}, {"v": "x"}, {"img": "c"})) == []


def test_same_shot_counts_once():
    # 同一張圖兩句 = 同一個鏡頭,只有 2 個鏡頭 → 無連續警告,但同圖連用 2 句警告
    w = L.visual_warnings(mk({"img": "a"}, {"img": "a"}, {"img": "b"}))
    assert [x[0] for x in w] == ["同一張圖連用 2 句以上"]


def test_clips_not_reported():
    assert L.visual_warnings(mk({"v": "x"}, {"v": "y"}, {"v": "z"}, {"v": "w"})) == []


def _chart(t="bars", vals=(150, 12, 18), **kw):
    return {"anim": dict({"type": t, "title": "測試", "items": [[f"項{i}", v, "萬"] for i, v in enumerate(vals)]}, **kw)}


def test_shock_hint():
    w = L.visual_warnings(mk(_chart(), dict(_chart(), step=1)))       # 同一組動畫只提示一次
    assert [x[0] for x in w] == ["單系列長條 / 直條最大值遠大於次大值(建議,不擋)"] and len(w[0][1]) == 1 and "shock" in w[0][1][0][1]
    assert len(L.visual_warnings(mk(_chart("cols", (5, 60, 9))))[0][1]) == 1
    for ok in (_chart(shock=True), _chart(shock=0), _chart(vals=(30, 12, 18)), _chart(series=["甲", "乙"]), _chart(stack=True)):
        assert L.visual_warnings(mk(ok)) == [], ok


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            print("ok", k)
