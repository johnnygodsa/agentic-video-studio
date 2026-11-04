"""截圖出處標籤改 lower 下標籤(拆字、退回條件、與使用者 lower 去重、不計節制上限)+ 畫面表 kit 欄比對:
python -X utf8 pipeline\tests\test_label_lower.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build as B  # noqa: E402
import visual_check as VC  # noqa: E402


def test_split_tag_text():
    assert B.split_tag_text("中文翻譯 · 原文:Press Start 2026/05/29") == ("原文:Press Start", "中文翻譯 · 2026/05/29")
    assert B.split_tag_text("中文翻譯 · 原文:Hardcore Gamer 2026/10") == ("原文:Hardcore Gamer", "中文翻譯 · 2026/10")
    assert B.split_tag_text("中文翻譯 · 原文:京鄉") == ("原文:京鄉", "中文翻譯")
    assert B.split_tag_text("來源:某某") == ("來源:某某", "")      # site 以 = 開頭的原樣標籤


def _media(tmp_path, tag_text):
    d = tmp_path / "images"
    d.mkdir()
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (1920, 1080), (30, 30, 34))
    ImageDraw.Draw(im).rounded_rectangle((1300, 1030, 1904, 1066), 8, fill=(0, 0, 0))
    ImageDraw.Draw(im).rectangle((1320, 1038, 1700, 1056), fill=(255, 255, 255))   # 白字塊 -> split_label 認得是標籤
    im.save(d / "x.png")
    if tag_text:
        (d / "x.layout.json").write_text(json.dumps(dict(tag_text=tag_text)), encoding="utf-8")
    return tmp_path


def _shot():
    return [dict(kind="image", img="x", line=1, last_line=1, fx="none")]


def test_decide_labels(tmp_path):
    B._label_cache.clear()
    m = _media(tmp_path, "中文翻譯 · 原文:Press Start 2026/05/29")
    lines = [dict(idx=1, text="a")]
    s = _shot()
    assert B.decide_labels(s, lines, m) == []
    assert s[0]["label_lower"] == dict(text="原文:Press Start", sub="中文翻譯 · 2026/05/29")
    # corner:CLI / script 頂層 / 單句(單句優先)
    s = _shot()
    B.decide_labels(s, lines, m, "corner")
    assert s[0]["label_lower"] is None
    s = _shot()
    B.decide_labels(s, lines, m, "lower", "corner")
    assert s[0]["label_lower"] is None
    s = _shot()
    B.decide_labels(s, [dict(idx=1, text="a", label_style="lower")], m, "corner", "corner")
    assert s[0]["label_lower"]
    # 使用者已寫 lower -> 不加自動 lower(保留角標)
    s = _shot()
    B.decide_labels(s, [dict(idx=1, text="a", kit=[dict(type="lower", text="x")])], m)
    assert s[0]["label_lower"] is None
    # 不認得的值
    s = _shot()
    assert B.decide_labels(s, [dict(idx=1, text="a", label_style="zzz")], m)


def test_decide_labels_old_image_falls_back(tmp_path):
    B._label_cache.clear()
    m = _media(tmp_path, None)
    s = _shot()
    assert B.decide_labels(s, [dict(idx=1, text="a")], m) == []
    assert s[0]["label_lower"] is None


def test_auto_lower_not_counted_in_shot_limit():
    s = [dict(kits=[dict(type="callout", t=0.3, line=1)] * 4, label_lower=dict(text="原文:A"), line=1)]
    assert B.KIT.shot_errors(s[0]["kits"], False) == []
    B.attach_label_lowers(s)
    assert len(s[0]["kits"]) == 5 and s[0]["kits"][-1]["type"] == "lower" and s[0]["kits"][-1]["t"] == 0.0


def test_visual_table_kit_compare(tmp_path):
    t = tmp_path / "t.md"
    t.write_text("| 句# | 行號 | kit | 警告 |\n|---|---|---|---|\n| 1 | 5 | callout:一團亂, arrow |  |\n"
                 "| 2 | 6 | tick |  |\n| 3 | 7 |  |  |\n", encoding="utf-8")
    ex = {"kit": [{"type": "callout", "at": {"text": "一團亂"}}, {"type": "arrow", "at": {"text": "一團亂"}}]}
    lines = [dict(idx=1, extra=ex, codes=[]), dict(idx=2, extra={}, codes=[]),
             dict(idx=3, extra={"kit": {"type": "lower", "text": "A"}}, codes=[])]
    W = VC.kit_compare(lines, t)
    assert [(c, i) for c, i, _ in W] == [("K1", 2), ("K2", 3)]
    assert VC.kit_cell(ex) == "callout:一團亂, arrow"
    t.write_text("| 句# | kit2 |\n|---|---|\n| 1 | x |\n", encoding="utf-8")   # 沒有 kit 欄 -> 不比對
    assert VC.kit_compare(lines, t) == []


if __name__ == "__main__":
    import inspect
    import tempfile
    for _n, _f in list(globals().items()):
        if _n.startswith("test_"):
            if inspect.signature(_f).parameters:
                with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / "tmp") as _d:
                    _f(Path(_d))
            else:
                _f()
    print("test_label_lower: all passed")
