"""hl 底線卡詞時序(hl_word_time / hl_starts):python -X utf8 -m pytest pipeline/tests/test_hl_word.py -q"""
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build as B  # noqa: E402


def ticks(say, step=0.2):
    """say 每個字元位置的秒數:每字 step 秒,長度 len(say)+1。"""
    return [round(i * step, 3) for i in range(len(say) + 1)]


def line(text, say=None, say_t=None, v0=10.0, dur=3.0, clauses=None):
    ln = dict(idx=1, text=text, vstart=v0, dur=dur, clauses=clauses)
    if say:
        ln["say"] = say
    if say_t is not None:
        ln["qc"] = dict(say_t=say_t)
    return ln


def clause(text, start, say_t):
    return dict(text=text, start=start, end=start + 1.0, gap=0.1, say_t=say_t)


# ---------------------------------------------------------------- hl_word_time
def test_word_mid_sentence():
    t = "這間公司宣布裁員"
    assert B.hl_word_time(line(t, say_t=ticks(t)), ["裁員"]) == pytest.approx(11.2)


def test_word_at_sentence_start_stays_at_base():
    t = "這間公司宣布裁員"
    tw = B.hl_word_time(line(t, say_t=ticks(t)), ["這間"])
    assert tw == pytest.approx(10.0)
    assert B.hl_starts([dict(f0=300, tw=tw)], 300, 150) == pytest.approx([B.HL_DELAY])


def test_earliest_of_several_keywords():
    t = "這間公司宣布裁員"
    assert B.hl_word_time(line(t, say_t=ticks(t)), ["裁員", "沒唸到", "公司"]) == pytest.approx(10.4)


def test_say_replaced_text_differs():
    ln = line("EA 宣布", say="藝電宣布", say_t=ticks("藝電宣布"))
    assert B.hl_word_time(ln, ["宣布"]) == pytest.approx(10.4)
    assert B.hl_word_time(ln, ["EA"]) == pytest.approx(10.0)
    assert B.hl_word_time(ln, ["ea"]) == pytest.approx(10.0)   # 忽略大小寫


def test_keyword_ignores_whitespace():
    t = "關掉第 19 間工作室"
    assert B.hl_word_time(line(t, say_t=ticks(t)), ["第19間"]) == pytest.approx(10.4)
    assert B.hl_word_time(line(t, say_t=ticks(t)), ["第 1 9間"]) == pytest.approx(10.4)


def test_keyword_ignores_whitespace_with_say_replaced():
    s = "關掉第十九間工作室"
    ln = line("關掉第 19 間工作室", say=s, say_t=ticks(s))
    assert B.hl_word_time(ln, ["第19間"]) == pytest.approx(10.4)


def test_clauses_use_their_own_timing():
    a, b = "前面先講。", "後面才講裁員。"
    ln = line(a + b, clauses=[clause(a, 0.0, ticks(a)), clause(b, 2.0, ticks(b))])
    assert B.hl_word_time(ln, ["裁員"]) == pytest.approx(10.0 + 2.0 + 0.8)
    assert B.hl_word_time(ln, ["先講"]) == pytest.approx(10.4)


def test_clause_without_timing_is_none_only_for_that_clause():
    a, b = "前面先講。", "後面才講裁員。"
    ln = line(a + b, clauses=[clause(a, 0.0, ticks(a)), clause(b, 2.0, None)])
    assert B.hl_word_time(ln, ["裁員"]) is None
    assert B.hl_word_time(ln, ["先講"]) == pytest.approx(10.4)


def test_no_timing_or_no_word_is_none():
    t = "這間公司宣布裁員"
    assert B.hl_word_time(line(t), ["裁員"]) is None                        # 沒有 say_t
    assert B.hl_word_time(line(t, say_t=ticks(t)[:-1]), ["裁員"]) is None   # 長度不符
    assert B.hl_word_time(line(t, say_t=ticks(t)), ["圖上才有"]) is None    # 詞不在旁白
    assert B.hl_word_time(line(t, say_t=ticks(t)), ["  "]) is None          # 空關鍵字不算命中句首
    assert B.hl_word_time(line(t, say_t=ticks(t)), []) is None


def test_bad_input_never_raises():
    t = "這間公司宣布裁員"
    assert B.hl_word_time(dict(idx=1, text=t, f0=0, f1=30), ["裁員"]) is None   # 時長預檢以外沒有 vstart 的行
    assert B.hl_word_time(line(t, say_t=ticks(t)), None) is None
    bad = ticks(t)
    bad[6] = None
    assert B.hl_word_time(line(t, say_t=bad), ["裁員"]) is None


# ---------------------------------------------------------------- hl_starts(FPS = 30)
def test_starts_follow_word_time():
    assert B.hl_starts([dict(f0=300, tw=12.0)], 300, 300) == pytest.approx([2.0 - B.HL_WORD_LEAD])


def test_starts_relative_to_shot_not_line():
    assert B.hl_starts([dict(f0=300, tw=12.0)], 270, 300) == pytest.approx([3.0 - B.HL_WORD_LEAD])


def test_clamped_by_shot_end():
    assert B.hl_starts([dict(f0=300, tw=14.8)], 300, 150) == pytest.approx([5.0 - B.HL_MIN_SHOW])


def test_clamped_by_next_segment():
    ts = B.hl_starts([dict(f0=300, tw=13.5), dict(f0=330, tw=13.6)], 300, 300)
    assert ts == pytest.approx([3.5 - B.HL_MIN_SHOW, 3.5])


def test_clamp_chain_runs_from_the_back():
    ts = B.hl_starts([dict(f0=300, tw=14.0), dict(f0=330, tw=14.0), dict(f0=360, tw=14.0)], 300, 150)
    assert ts == pytest.approx([1.9, 2.9, 3.9])


def test_clamp_never_earlier_than_base():
    assert B.hl_starts([dict(f0=300, tw=10.9)], 300, 30) == pytest.approx([B.HL_DELAY])   # 鏡頭比 HL_MIN_SHOW 短
    ts = B.hl_starts([dict(f0=300, tw=11.0), dict(f0=315, tw=11.0)], 300, 300)
    assert ts == pytest.approx([B.HL_DELAY, 0.9])                                         # 兩句相隔不到 HL_MIN_SHOW


def test_no_tw_keeps_current_timing_exactly():
    hs = [dict(f0=300, tw=None), dict(f0=345), dict(f0=400, tw=None)]
    assert B.hl_starts(hs, 290, 120) == [(h["f0"] - 290) / B.FPS + B.HL_DELAY for h in hs]


def test_tw_segment_clamped_by_following_fallback_segment():
    assert B.hl_starts([dict(f0=300, tw=13.5), dict(f0=390, tw=None)], 300, 300) == pytest.approx([2.3, 3.3])


def test_empty():
    assert B.hl_starts([], 0, 30) == []


# ---------------------------------------------------------------- 接到鏡頭與渲染
def test_layout_shots_stores_word_time():
    t = "這間公司宣布裁員"
    ln = dict(line(t, say_t=ticks(t)), sec="s", img="pic", hl=["裁員"], f0=300, f1=390)
    shots, errs = B.layout_shots([ln])
    assert not errs and shots[0]["hls"][0]["tw"] == pytest.approx(11.2)


def test_prep_hl_uses_word_time_and_skips_no_hit(tmp_path):
    hit = dict(box=(10, 10, 100, 30), ux0=10, ux1=100, uy=34)
    s = dict(img="pic", f0=300, frames=300, hls=[dict(kws=["甲"], f0=300, tw=11.0), dict(kws=["乙"], f0=330, tw=11.5),
                                                  dict(kws=["丙"], f0=360, tw=None)])
    B.prep_hl(s, str(tmp_path / "s"), 200, 100, 1, dict(sc=1.0, pos=(0, 0), hits=[[hit], [], [hit]]))
    L = s["hl_layers"]
    assert len(L) == 2                                         # 無命中的段不算進時序
    assert [x["t0"] for x in L] == pytest.approx([0.9, 2.3])   # 第二段 base = 60 格 + HL_DELAY
    assert L[0]["t1"] == L[1]["t0"] and L[1]["t1"] is None


class FakeFfmpeg:
    """make_img_p 的 ffmpeg:不真的編碼,只收格數並產出 .part.mp4。"""
    calls = []

    def __init__(self, cmd, stdin=None):
        Path(cmd[-1]).write_bytes(b"x")
        self.stdin = self
        self.n = 0
        FakeFfmpeg.calls.append(self)

    def write(self, b):
        self.n += 1

    def close(self):
        pass

    def wait(self):
        return 0


def _img_p(monkeypatch, tmp_path, tws, groups, frames=90):
    monkeypatch.setattr(B, "_img_p_geom", lambda img, kws, media: dict(k=1.0, ox=0, oy=0, ents=[], groups=groups))
    monkeypatch.setattr(B, "_img_p_base", lambda g: Image.new("RGBA", (64, 64), (0, 0, 0, 255)))
    monkeypatch.setattr(B.subprocess, "Popen", FakeFfmpeg)
    s = dict(img="pic", f0=300, frames=frames,
             hls=[dict(line=i, kws=["詞"], f0=300 + i * 15, tw=tw) for i, tw in enumerate(tws)])
    return B.make_img_p(s, tmp_path, tmp_path / "out" / "0001_img.png")[0]


def test_make_img_p_cache_follows_word_time(monkeypatch, tmp_path):
    box = (4, 4, 40, 16)
    a = _img_p(monkeypatch, tmp_path, [None], [[box]])
    b = _img_p(monkeypatch, tmp_path, [11.0], [[box]])
    c = _img_p(monkeypatch, tmp_path, [11.0], [[box]])
    assert a.name != b.name and b.name == c.name   # 起點變了檔名簽章跟著變;相同起點沿用快取


def test_make_img_p_skips_segment_without_bars(monkeypatch, tmp_path):
    box = (4, 4, 40, 16)
    # 第一段沒有命中:不算進時序,否則第二段會被夾到不同位置(簽章不同)
    a = _img_p(monkeypatch, tmp_path, [11.0, 11.0], [[], [box]], frames=120)
    b = _img_p(monkeypatch, tmp_path, [None, 11.0], [[], [box]], frames=120)
    assert a.name == b.name


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
