"""畫面優先看清單測試:python -X utf8 pipeline\tests\test_look_list.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import look_list as K  # noqa: E402

TL = dict(
    shots=[dict(n=1, start=0.0, end=10.2), dict(n=2, start=10.2, end=75.4), dict(n=3, start=75.4, end=130.0)],
    lines=[dict(idx=1, text="第一句旁白的文字內容很長很長很長很長很長很長很長很長很長", visual_start=0.0, visual_end=10.2, shots=[1]),
           dict(idx=2, text="第二句", visual_start=10.2, visual_end=40.0, shots=[2]),
           dict(idx=3, text="第三句", visual_start=40.0, visual_end=75.4, shots=[2]),
           dict(idx=4, text="第四句", visual_start=75.4, visual_end=130.0, shots=[3])])


def test_fmt_time():
    assert K.fmt_time(0) == "00:00" and K.fmt_time(59.9) == "00:59" and K.fmt_time(75.4) == "01:15" and K.fmt_time(3725) == "62:05"


def test_merge_same_shot_and_sort():
    raw = [(4, 4, "純色塊", "x.png: 50%"), (3, 3, "小件放不下", "句3 arrow 放不下"), (2, 2, "小件比對", "K1 少了 badge"),
           (1, 1, "畫面單調", "L5 至 L9 連續 3 個")]
    rows = K.build_rows(raw, TL)
    assert [r["line"] for r in rows] == [1, 2, 4]            # 依時間排序
    mid = rows[1]
    assert (mid["t0"], mid["t1"]) == (10.2, 75.4)             # 句2、句3 同鏡頭 → 一列,時間取鏡頭起訖
    assert mid["line_end"] == 3 and mid["kind"] == "小件比對、小件放不下"
    assert "K1" in mid["reason"] and "arrow" in mid["reason"] and mid["hint"].count("；") == 1


def test_no_line_goes_last():
    rows = K.build_rows([(None, None, "小件放不下", "某處"), (4, 4, "純色塊", "y")], TL)
    assert rows[-1]["t0"] is None and rows[0]["line"] == 4


def test_unknown_line_skips_time():
    rows = K.build_rows([(99, 99, "純色塊", "z")], TL)
    assert rows[0]["t0"] is None


def test_render_md():
    rows = K.build_rows([(1, 1, "畫面單調", "r"), (2, 3, "純色塊", "a|b")], TL)
    md = K.render_md(rows, "t", "v1")
    assert "| 00:00–00:10 | 1 | " + TL["lines"][0]["text"][:20] + " |" in md and TL["lines"][0]["text"][:21] not in md   # 前 20 字
    assert "| 00:10–01:15 | 2-3 |" in md and "a/b" in md                       # 範圍句號、管線符號跳脫
    assert md.count("\n|") >= 4


def test_render_empty():
    assert "本版畫面無程式警告" in K.render_md([], "t", "v1")


def test_log_parse():
    log = "\n".join([
        "[3/10] 檢查 OK", "警告: 小件擺放: 句12 kit arrow 放不下,選侵入最少者", "警告: 挑片段 tag=a: 其他警告",
        "[anim_web] kit 警告:句20-21 pop 放不下", "警告: 動畫容量量測失敗,略過: X",
        "[visual_check] t:3 句", "  警告 K1 x2", "    句5(行60) 表有 callout", "    句6(行61) 表有 tick", "  警告 A x1", "    句7(行62) 數字句"])
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "make.log"
        p.write_text(log, encoding="utf-8")
        raw = K.raw_from_log(p)
    kinds = [(a, b, k) for a, b, k, _ in raw]
    assert kinds == [(12, 12, "小件放不下"), (20, 21, "小件放不下"), (None, None, "動畫容量"),
                     (5, 5, "小件比對"), (6, 6, "小件比對")]
    assert K.raw_from_log(Path("nope.log")) == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("ok", f.__name__)
    print(f"{len(fns)} 項通過")
