"""feedback.py / feedback_report.py 的 A/B 欄位、scorecard 欄與「A/B 教訓」節測試(假 projects 與 persona log,全在 tmp)。
python -X utf8 -m pytest pipeline/tests/test_feedback_ab.py"""
import json
import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import feedback as FB  # noqa: E402
import feedback_report as FR  # noqa: E402
import paths as P  # noqa: E402


def _w(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "channel").mkdir(parents=True)
    monkeypatch.setattr(P, "ROOT", root)
    monkeypatch.setattr(P, "PROJECTS", root / "projects")
    monkeypatch.setattr(P, "BUILD", root / "build")
    _w(root / "projects/ab_t/spec.json", {"package": {
        "subject": ["蝙蝠俠"],
        "titles": [{"text": "蝙蝠俠這次做對了3件事", "angle": "判"}, {"text": "為什麼沒人敢碰", "angle": "懸"}, {"text": "三年後才發現", "angle": "時"}],
        "covers": [{"angle": "判", "layout": "左人右字"}, {"angle": "懸"}, {"angle": "時"}]}})
    (root / "channel/cover_persona_log.jsonl").write_text(
        json.dumps({"tag": "ab_t", "plan": "2", "kind": "角色", "gesture": "雙手抱頭", "color": "黃黑"}, ensure_ascii=False) + "\n"
        + json.dumps({"tag": "other", "plan": "2", "kind": "X"}) + "\n", encoding="utf-8")
    return root


def _vid(ab, vid="AAAAAAAAAAA"):
    v = {"video_id": vid, "channel": "ChannelA", "tag": "ab_t", "title": "t", "published_at": "2026-10-01T04:00:00Z",
         "duration_s": 200, "is_self": 1, "age_hours": 300.0}
    if ab is not _MISSING:
        v["ab"] = ab
    return v


_MISSING = object()


def _ab(mode, status, winner=None, n=3):
    vers = [{"idx": i, "title": None if mode == "thumb" else f"標題{i}", "thumb": None, "share_pct": 40.0 + i,
             "label": "winner" if i == winner else None, "is_current": i == winner} for i in range(1, n + 1)]
    return {"mode": mode, "status": status, "winner_idx": winner, "versions": vers}


def test_missing_ab_is_null(env):
    r = FB.build_row(_vid(_MISSING), "ab_t")
    assert (r["ab_mode"], r["ab_status"], r["ab_winner_idx"], r["ab_versions"]) == (None, None, None, None)
    assert FB.ab_cell(r) == "—"
    assert FB.build_row(_vid(None), "ab_t")["ab_versions"] is None


def test_versions_enriched(env):
    r = FB.build_row(_vid(_ab("thumb", "winner", 2)), "ab_t")
    assert r["ab_mode"] == "thumb" and r["ab_status"] == "winner" and r["ab_winner_idx"] == 2
    v2 = r["ab_versions"][1]
    assert v2["title_angle"] == "懸" and v2["thumb_plan"] == 2 and v2["cover_angle"] == "懸"
    assert (v2["cover_kind"], v2["cover_gesture"], v2["cover_color"]) == ("角色", "雙手抱頭", "黃黑")   # persona log 只取該 tag+plan
    v1 = r["ab_versions"][0]
    assert v1["cover_kind"] is None and v1["cover_layout"] == "左人右字"
    t = FB.build_row(_vid(_ab("title", "winner", 1)), "ab_t")["ab_versions"]
    assert all(x["thumb_plan"] == 1 for x in t)                       # title 模式封面固定方案 1
    assert t[0]["title"] == "標題1" and t[0]["name_start"] is False
    # 匯出沒給 title 時取 spec 的標題文字
    r2 = FB.build_row(_vid({"mode": "title", "status": "winner", "winner_idx": 1,
                            "versions": [{"idx": 1, "title": None, "label": "winner"}]}), "ab_t")
    assert r2["ab_versions"][0]["title"].startswith("蝙蝠俠") and r2["ab_versions"][0]["name_start"] is True


@pytest.mark.parametrize("ab,expect", [
    (_ab("thumb", "winner", 2), "封面#2 勝 42%"),
    (_ab("title", "winner", 1), "標題#1 勝 41%"),
    (_ab("both", "winner", 3), "合測#3 勝 43%"),
    (_ab("title", "same"), "相同"),
    (_ab("thumb", "inconclusive"), "無法判定"),
    (_ab("thumb", "running"), "進行中"),
    (_ab("title", "stopped"), "已停止"),
    ({"mode": None, "status": "not_set", "versions": []}, "未設定"),
    ({"mode": None, "status": "unknown", "versions": None}, "—"),
])
def test_ab_cell_and_scorecard(env, ab, expect):
    r = FB.build_row(_vid(ab), "ab_t")
    assert FB.ab_cell(r) == expect
    FB.write_outcomes({r["video_id"]: r})
    FB.write_scorecard([r])
    sc = (env / "channel/scorecard.md").read_text(encoding="utf-8")
    assert "| 標題切角 | A/B |" in sc and expect in sc
    assert FB.sc_line(r).count("|") == len(FB.SC_HEADER) + 1


def _row(i, mode, status, winner, ch="ChannelA", titles=None, **vkw):
    n = 3
    vers = [dict({"idx": k, "title": (titles or {}).get(k, f"標題{k}"), "label": "winner" if k == winner else None,
                  "title_angle": "判" if k == 1 else "懸", "thumb_plan": 1 if mode == "title" else k,
                  "cover_angle": "判" if k == 1 else "懸", "name_start": k == 1}, **vkw) for k in range(1, n + 1)]
    return {"video_id": f"V{i:010d}", "tag": f"t{i}", "channel": ch, "is_self": 1, "published_at": f"2026-10-{i % 28 + 1:02d}T00:00:00Z",
            "duration_bucket": "<5分", "publish_mode": "scheduled", "ab_mode": mode, "ab_status": status,
            "ab_winner_idx": winner, "ab_versions": vers}


def test_report_no_ab_data():
    out = FR.build_report([{"video_id": "x", "is_self": 1, "channel": "ChannelA"}])
    assert "## A/B 教訓" in out and "尚無 A/B 資料" in out
    # 只有進行中 / 未設定也算沒有資料
    out2 = FR.build_report([_row(1, "title", "running", None), _row(2, None, "not_set", None)])
    assert "尚無 A/B 資料" in out2


def test_report_threshold_n8():
    # 3 版 x 2 支 = 6 參賽 -> 資料不足;3 版 x 3 支 = 9 參賽 -> 印勝率
    few = FR.ab_section([_row(i, "thumb", "winner", 1) for i in range(2)])
    assert any("| 判 |" in ln and "資料不足(n=2)" in ln for ln in few)
    many = FR.ab_section([_row(i, "thumb", "winner", 1) for i in range(8)])
    line = next(ln for ln in many if ln.startswith("| 判 |"))
    assert "| 8 | 8 | 100% |" in line                     # 切角「判」:參賽 8、勝 8
    line2 = next(ln for ln in many if ln.startswith("| 懸 |"))
    assert "| 16 | 0 | 0% |" in line2


def test_report_unattributable_and_status_filter():
    rows = [_row(1, "both", "winner", 2), _row(2, "title", "same", None), _row(3, "thumb", "inconclusive", None),
            _row(4, "title", "running", None), _row(5, "title", "not_set", None), _row(6, "title", "unknown", None), _row(7, "title", "stopped", None)]
    out = "\n".join(FR.ab_section(rows))
    assert "合測(不能歸因" in out and "標題#2(懸)+封面方案2" in out
    assert "完成的測試 3 支" in out                       # running / stopped / not_set / unknown 不算
    # same / inconclusive 有參賽、沒有勝
    assert "both/winner 1" in out and "title/same 1" in out and "thumb/inconclusive 1" in out
    assert "stopped" not in out


def _with_shares(row, shares):
    for v, sh in zip(row["ab_versions"], shares):
        v["share_pct"] = sh
    return row


def test_report_per_channel_and_title_features():
    # ChannelA title 模式:版本1「我玩了3天」(含經驗框)每場占比 50,其餘 25 -> 8 場 -> 印占比差;ChannelB thumb 模式仍是勝率表
    titles = {1: "我玩了3天", 2: "官方公告", 3: "別買了"}
    rows = [_with_shares(_row(i, "title", "winner", 1, ch="ChannelA", titles=titles), [50, 25, 25]) for i in range(8)]
    rows += [_row(20 + i, "thumb", "winner", 2, ch="ChannelB", cover_kind="角色") for i in range(8)]
    out = "\n".join(FR.ab_section(rows))
    assert "### ChannelA" in out and "### ChannelB" in out
    kuang = out.split("### ChannelA")[1]
    line = next(ln for ln in kuang.splitlines() if ln.startswith("| 經驗框"))
    assert "| 8 | +25.0 | [+25.0, +25.0] | 加分 |" in line         # 超額:+16.7 對 -8.3 -> 差 25
    assert "| 角色 | 24 | 8 | 33% |" in out                         # ChannelB thumb 模式 kind
    langren = out.split("### ChannelB")[1].split("### ChannelA")[0]
    assert "標題模式" not in langren and "封面切角" in langren
    # 場數不足:只印場數、不下結論
    few = "\n".join(FR.ab_section(rows[:3]))
    assert "可比較 3 場" in few and "樣本不足" in few and "| 經驗框" not in few


def test_share_contrast_known_answer(monkeypatch):
    monkeypatch.setattr(FR, "MIN_N", 2)
    # 兩場:A 占比 60/40,B 55/45 -> 超額 +10/-10、+5/-5;經驗框(我玩/我看)在第 1 版
    tests = FR.share_tests([
        [{"title": "【爆料】我玩了3天", "share_pct": 60}, {"title": "官方公告", "share_pct": 40}],
        [{"title": "我看完了", "share_pct": 55}, {"title": "別買", "share_pct": 45}],
        [{"title": "同標題", "share_pct": 50}, {"title": "同標題", "share_pct": 50}],      # 標題相同 -> 不算一場
        [{"title": "缺占比", "share_pct": None}, {"title": "另一個", "share_pct": 50}],     # 缺 share_pct -> 不算
    ])
    assert len(tests) == 2 and tests[0][0] == ("我玩了3天", 10.0)     # 【】已去掉
    exp = next(f for f in FR.SHARE_FEATURES if f[0].startswith("經驗框"))
    n, m, lo, hi = FR.share_contrast(tests, exp[1])
    assert n == 2 and m == pytest.approx(15.0)                        # (20 + 10) / 2
    assert 10.0 <= lo <= hi <= 20.0 and lo > 0
    assert any("加分" in ln and ln.startswith("| 經驗框") for ln in FR.share_feature_table(tests))
    # 三段以上 vs 兩段:只看全版本都有空格的場(無空格的場排除)
    seg = FR.share_tests([
        [{"title": "甲 乙 丙", "share_pct": 30}, {"title": "甲 乙", "share_pct": 70}],      # -20 對 +20 -> -40
        [{"title": "a b c", "share_pct": 40}, {"title": "a b", "share_pct": 60}],          # -10 對 +10 -> -20
        [{"title": "甲 乙 丙", "share_pct": 10}, {"title": "乙丙", "share_pct": 90}],        # 有版本沒空格 -> 排除
    ])
    f = next(f for f in FR.SHARE_FEATURES if f[0].startswith("三段以上"))
    n, m, lo, hi = FR.share_contrast(seg, f[1], f[2])
    assert n == 2 and m == pytest.approx(-30.0) and hi < 0
    assert FR.share_gap_line(seg).startswith("場內最高-最低占比差:中位")
    # 預設門檻 8:2 場不印特徵
    monkeypatch.setattr(FR, "MIN_N", 8)
    assert "樣本不足" in "\n".join(FR.share_feature_table(tests))


def test_report_main_end_to_end(env, tmp_path):
    r = FB.build_row(_vid(_ab("title", "winner", 1)), "ab_t")
    FB.write_outcomes({r["video_id"]: r})
    out = tmp_path / "成效分析.md"
    FR.main(["--outcomes", str(env / "channel/outcomes.jsonl"), "--out", str(out),
             "--channel-export", str(tmp_path / "不存在.json")])
    text = out.read_text(encoding="utf-8")
    assert "## A/B 教訓" in text and "## 全頻道標題測試" in text and "讀不到 channel_latest.json" in text


# ---------------------------------------------------------------- 全頻道標題測試(channel_latest fixture)
def _cv(vid, pub, status, mode, titles, winner=None, shares=None, is_self=True, ab=True):
    v = {"video_id": vid, "title": titles[0], "published_at": pub}
    if is_self is not None:
        v["is_self"] = is_self
    if ab:
        shares = shares or [40.0, 35.0, 25.0]
        v["ab"] = {"mode": mode, "status": status, "winner_idx": winner if status == "winner" else None,
                   "versions": [{"idx": i, "title": t, "share_pct": shares[i - 1],
                                 "label": "winner" if i == winner else None} for i, t in enumerate(titles, 1)]}
    return v


def _chan_fixture():
    t = ["【爆料】蝙蝠俠這次做對了3件事？", "為什麼沒人敢碰", "三年後才發現，原來是這樣啊"]
    return {"channels": [
        {"name": "ChannelA", "slot": "", "videos": [
            _cv("V1", "2026-10-01T00:00:00Z", "winner", "title", t, 1),
            _cv("V2", "2026-10-05T00:00:00Z", "winner", "both", t, 2, shares=[20.0, 50.0, 30.0], is_self=False),
            _cv("V3", "2026-10-03T00:00:00Z", "same", "title", t),
            _cv("V4", "2026-10-04T00:00:00Z", "inconclusive", "title", t, is_self=False),
            _cv("V5", "2026-10-06T00:00:00Z", "winner", "thumb", t, 1),        # thumb 不算
            _cv("V6", "2026-10-07T00:00:00Z", "running", "title", t),          # 未結束不算
            _cv("V7", "2026-10-08T00:00:00Z", "stopped", "title", t),          # stopped 不算
            _cv("V8", "2026-10-09T00:00:00Z", "winner", "title", t, ab=False),  # 缺 ab 鍵不炸
            {"video_id": "V9", "title": "x", "published_at": "2026-10-10T00:00:00Z", "ab": None},
            {"video_id": "V10", "title": "x", "ab": {"mode": "title", "status": "winner", "versions": None}},
        ]},
        {"name": "ChannelB", "slot": "c", "videos": [
            _cv("W1", "2026-10-02T00:00:00Z", "same", "title", t, is_self=None),
            _cv("W2", "2026-10-02T00:00:00Z", "winner", "title", t, 3, is_self=None),
        ]},
        {"name": "ChannelC", "slot": "d", "videos": [{"video_id": "D1", "title": "x"}]},
    ]}


def test_channel_section_threshold_and_counts():
    out = "\n".join(FR.channel_ab_section(_chan_fixture()))
    assert "### ChannelA(完成的標題測試 3 場;另 mode=both 1 場不納入)" in out and "結果:勝出 1、相同 1、無法判定 1" in out
    assert "### ChannelB(完成的標題測試 2 場)" in out and "### ChannelC" not in out
    kuang = out.split("### ChannelA")[1].split("### ChannelB")[0]
    # 3 場 < 8 場:不印特徵表,只印樣本不足
    assert "樣本不足(可比較的測試 3 場" in kuang and "| 含數字 |" not in kuang
    # 自製 / 搬運分開:V1、V3 自製;V4 搬運(V2 是 both,不納入)
    assert "自製 2 場(勝出 1、相同 1、無法判定 0);搬運 1 場(勝出 0、相同 0、無法判定 1)" in kuang
    langren = out.split("### ChannelB")[1]
    assert "沒有 is_self 欄,自製與搬運全部合計" in langren


def test_channel_section_winner_list_order_and_cap():
    fx = _chan_fixture()
    t = ["【爆料】蝙蝠俠這次做對了3件事？", "為什麼沒人敢碰", "三年後才發現，原來是這樣啊"]
    fx["channels"][0]["videos"].append(_cv("V11", "2026-10-05T00:00:00Z", "winner", "title", t, 2, shares=[20.0, 50.0, 30.0]))
    out = FR.channel_ab_section(fx)
    kuang = "\n".join(out).split("### ChannelA")[1].split("### ChannelB")[0]
    lines = [ln for ln in kuang.splitlines() if ln.startswith("- 2026")]
    assert len(lines) == 2 and lines[0].startswith("- 2026-10-05") and lines[1].startswith("- 2026-10-01")   # 新到舊;both 不列
    assert "勝 「為什麼沒人敢碰」(50%) / 敗 「【爆料】蝙蝠俠這次做對了3件事？」(20%)、「三年後才發現，原來是這樣啊」(30%)" in lines[0]
    # 只取最近 20 場
    many = {"channels": [{"name": "X", "videos": [_cv(f"M{i}", f"2026-09-{i + 1:02d}T00:00:00Z", "winner", "title", ["甲", "乙", "丙"], 1)
                                                  for i in range(25)]}]}
    ls = [ln for ln in FR.channel_ab_section(many) if ln.startswith("- 2026")]
    assert len(ls) == 20 and ls[0].startswith("- 2026-09-25") and ls[-1].startswith("- 2026-09-06")


def test_channel_section_missing_or_empty():
    assert "讀不到 channel_latest.json" in "\n".join(FR.channel_ab_section(None))
    assert "尚無標題測試資料" in "\n".join(FR.channel_ab_section({"channels": [{"name": "A", "videos": [{"video_id": "z"}]}]}))
    assert "尚無標題測試資料" in "\n".join(FR.channel_ab_section({"channels": []}))
    # build_report 帶 channel_data 時附在 A/B 教訓之後
    out = FR.build_report([], _chan_fixture())
    assert out.index("## A/B 教訓") < out.index("## 全頻道標題測試")
