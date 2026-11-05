"""舊片回溫偵測(topic_scout.detect_rebound / load_activity / hook_line / write_rebound)。合成資料,不碰真匯出檔。"""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import topic_scout as T  # noqa: E402

END = date(2026, 10, 31)
TODAY = date(2026, 11, 3)


def vd(vals, end=END):
    """每日觀看 list -> views_daily [[日期, views]](最後一天 = end)。"""
    n = len(vals)
    return [[(end - timedelta(days=n - 1 - i)).isoformat(), v] for i, v in enumerate(vals)]


def row(vid, vals=None, age=100.0, is_self=False, title=None):
    r = {"video_id": vid, "title": title or f"標題{vid}", "published_at": "2026-06-01T00:00:00Z", "is_self": is_self, "tag": "t" if is_self else None,
         "age_days": age, "views_total": 1000, "my_daily_last": END.isoformat()}
    if vals is not None:
        r["views_daily"] = vd(vals)
    return r


def chan(*rows):
    return {"slot": "", "name": "ChannelA", "videos": list(rows)}


def test_views_daily_single_day_spike_hits():
    hits = T.detect_rebound(chan(row("spike", [100] * 20 + [450])), today=TODAY)
    assert [h["video_id"] for h in hits] == ["spike"]
    h = hits[0]
    assert h["source"] == "views_daily" and h["kind"] == "搬運" and "單日爆量" in h["types"] and h["max_day_ratio"] >= 4.4


def test_views_daily_slow_ramp_hits_and_flat_misses():
    ramp = [100] * 7 + [200] * 7        # 近 7 日 2x 前 7 日,日均 200 >= 100,最新日 200 只有 2x -> 只有緩升
    hits = T.detect_rebound(chan(row("ramp", ramp), row("flat", [100] * 14), row("quiet", [10] * 14 + [90])), today=TODAY)
    assert [h["video_id"] for h in hits] == ["ramp"] and hits[0]["types"] == ["緩升"] and abs(hits[0]["week_ratio"] - 2.0) < 1e-6


def test_young_video_not_judged():
    assert T.detect_rebound(chan(row("new", [100] * 20 + [900], age=3.0)), today=TODAY) == []


def test_views_daily_gap_filled_with_zero_and_bad_rows_ignored():
    s = T.daily_from_views_daily([["2026-10-01", 5], ["2026-10-04", 8], ["bad", 1], None, ["2026-10-02", "x"]])
    assert [x[1] for x in s] == [5, 0, 0, 8]
    assert T.daily_from_views_daily("garbage") == [] and T.daily_from_views_daily(None) == []


def test_fallback_to_date_copies_when_no_views_daily():
    pts = [((date(2026, 10, 20) + timedelta(days=i)).isoformat(), 1000 + 100 * i) for i in range(11)]
    pts.append(("2026-10-31", pts[-1][1] + 500))       # 最後一天 +500,前面每天 +100 -> 5x
    fb = {"old": {"row": row("old"), "points": pts, "v7": {}}}
    hits = T.detect_rebound(chan(row("old")), fallback=fb, today=TODAY)
    assert len(hits) == 1 and hits[0]["source"] == "日期副本" and hits[0]["latest"] == 500


def test_views_daily_preferred_over_date_copies():
    fb = {"x": {"row": row("x"), "points": [("2026-10-29", 1000), ("2026-10-30", 1100), ("2026-10-31", 1200)], "v7": {}}}
    hits = T.detect_rebound(chan(row("x", [100] * 20 + [450])), fallback=fb, today=TODAY)
    assert hits and hits[0]["source"] == "views_daily"


def test_upto_truncates_views_daily():
    r = row("w", [100] * 20 + [450])
    assert T.detect_rebound(chan(r), upto="2026-10-30", today=TODAY) == []          # 爆量那天被截掉
    assert len(T.detect_rebound(chan(r), upto="2026-10-31", today=TODAY)) == 1


# ---------------------------------------------------------------- 最新活動
def act(*vids, captured="2026-11-03T04:00:00"):
    return {"captured_at": captured, "channel": "ChannelA", "videos": [dict(video_id=v, views_48h=n, title="活動標題") for v, n in vids]}


def test_activity_hits_threshold_max_of_500_and_6x_daily():
    c = chan(row("lowbase", [20] * 14), row("highbase", [1000] * 14), row("young", [20] * 14, age=5))
    # lowbase 日均 20 -> 門檻 500;highbase 日均 1000 -> 門檻 6000
    hits = T.detect_rebound(c, activity=act(("lowbase", 520), ("highbase", 5000), ("young", 9999)), today=TODAY)
    ids = [h["video_id"] for h in hits]
    assert ids == ["lowbase"] and hits[0]["source"] == "最新活動" and hits[0]["views_48h"] == 520
    hits = T.detect_rebound(c, activity=act(("highbase", 6000)), today=TODAY)
    assert [h["video_id"] for h in hits] == ["highbase"]
    assert T.detect_rebound(c, activity=act(("lowbase", 499)), today=TODAY) == []


def test_activity_merges_with_series_hit():
    hits = T.detect_rebound(chan(row("both", [100] * 20 + [450])), activity=act(("both", 900)), today=TODAY)
    assert len(hits) == 1 and hits[0]["source"] == "views_daily+最新活動" and hits[0]["views_48h"] == 900


def test_activity_unknown_age_uses_published_at_else_skips():
    a = {"videos": [{"video_id": "ghost", "views_48h": 800, "published_at": "2026-01-01T00:00:00Z"},
                    {"video_id": "ghost2", "views_48h": 800}]}
    hits = T.detect_rebound(chan(), activity=a, today=TODAY)
    assert [h["video_id"] for h in hits] == ["ghost"]


def test_activity_field_name_tolerance_and_garbage():
    a = {"items": [{"videoId": "v", "views48h": 700}, "junk", {"video_id": "n", "views_48h": None}]}
    hits = T.detect_rebound(chan(row("v", [10] * 14), row("n", [10] * 14)), activity=a, today=TODAY)
    assert [h["video_id"] for h in hits] == ["v"]


def test_load_activity_missing_bad_and_slots(tmp_path):
    exp = tmp_path / "export"
    exp.mkdir()
    assert T.load_activity(exp, "") is None and T.load_activity(exp, "c") is None and T.load_activity(exp, "d") is None
    (tmp_path / "latest_activity_a.json").write_text("{壞檔", encoding="utf-8")
    (tmp_path / "latest_activity_c.json").write_text(json.dumps(act(("z", 600))), encoding="utf-8")
    assert T.load_activity(exp, "") is None
    assert T.load_activity(exp, "c")["videos"][0]["video_id"] == "z"


# ---------------------------------------------------------------- hook / 寫檔
def write_export(tmp_path, kuang_rows, lang_rows=()):
    exp = tmp_path / "export"
    exp.mkdir(exist_ok=True)
    doc = {"generated_at": "2026-11-03T06:00:00", "channels": [{"slot": "", "name": "ChannelA", "videos": list(kuang_rows)},
                                                                {"slot": "c", "name": "ChannelB", "videos": list(lang_rows)}]}
    (exp / "channel_latest.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return exp


def test_hook_line_none_and_writes_empty_file(tmp_path):
    exp = write_export(tmp_path, [row("a", [100] * 14)])
    out = tmp_path / "rebound.json"
    assert T.hook_line(exp, datetime(2026, 11, 3, 9), out) == "[回溫] 無"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["hits"] == [] and doc["generated_at"].startswith("2026-11-03T09")


def test_hook_line_hits_both_channels_and_json(tmp_path):
    exp = write_export(tmp_path, [row("a", [100] * 7 + [200] * 7, title="暗黑破壞神2至今仍讓玩家瘋狂的祕密")], [row("b", [100] * 20 + [450], title="ChannelB舊片")])
    (tmp_path / "latest_activity_c.json").write_text(json.dumps(act(("b", 900))), encoding="utf-8")
    out = tmp_path / "rebound.json"
    line = T.hook_line(exp, datetime(2026, 11, 3, 9), out)
    assert line.startswith("[回溫] ChannelA 1 支(暗黑破壞神2至今仍讓玩家 ×2.0)") and "ChannelB 1 支(ChannelB舊片 ×" in line and "\n" not in line
    hits = json.loads(out.read_text(encoding="utf-8"))["hits"]
    assert {(h["channel"], h["video_id"]) for h in hits} == {("ChannelA", "a"), ("ChannelB", "b")}
    assert [h for h in hits if h["video_id"] == "b"][0]["source"] == "views_daily+最新活動"


def test_rebound_json_carries_traffic_fields_only_when_present(tmp_path):
    exp = write_export(tmp_path, [row("a", [100] * 7 + [200] * 7, is_self=True), row("c", [100] * 7 + [200] * 7, is_self=True)])
    tr = {"BROWSE": 70, "SUGGESTED": 30, "captured_at": "2026-11-03T04:00:00"}
    (exp / "latest.json").write_text(json.dumps({"videos": [{"video_id": "a", "traffic_recent": tr, "traffic_7d": tr}, {"video_id": "c"}]}), encoding="utf-8")
    out = tmp_path / "rebound.json"
    T.hook_line(exp, datetime(2026, 11, 3, 9), out)
    hits = {h["video_id"]: h for h in json.loads(out.read_text(encoding="utf-8"))["hits"]}
    assert hits["a"]["traffic_recent"] == tr and hits["a"]["traffic_7d"] == tr
    assert "traffic_recent" not in hits["c"] and "traffic_7d" not in hits["c"]


def test_hook_line_missing_channel_data_is_wu(tmp_path):
    exp = tmp_path / "export"
    exp.mkdir()
    assert T.hook_line(exp, datetime(2026, 11, 3, 9), tmp_path / "r.json") == "[回溫] 無"


def test_hook_line_write_failure_does_not_raise(tmp_path):
    exp = write_export(tmp_path, [row("a", [100] * 14)])
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    assert T.hook_line(exp, datetime(2026, 11, 3, 9), blocker / "sub" / "r.json") == "[回溫] 無"


def test_9W0UMS_8878_wave_would_be_caught_with_views_daily():
    """2026-10 實測:9W0UMS-8878(搬運)10/14 日均 2386 -> 10/18–10/31 逐日如下;模擬 views_daily,波峰前半段(10/21 前後)就該命中。"""
    wave = [5110, 5338, 4974, 7201, 8306, 7950, 4993, 4350, 4009, 2721, 1987, 1938, 1010, 870]
    base = {(date(2026, 10, 14) - timedelta(days=k)).isoformat(): 2386 for k in range(15)}
    base.update({(date(2026, 10, 15) + timedelta(days=k)).isoformat(): 2386 for k in range(3)})       # 10/15–17 無資料,保守補平
    base.update({(date(2026, 10, 18) + timedelta(days=k)).isoformat(): v for k, v in enumerate(wave)})
    r = row("9W0UMS-8878")
    r["views_daily"] = sorted([k, v] for k, v in base.items())
    hit_days = [d for d in range(18, 32) if T.detect_rebound(chan(r), upto=f"2026-10-{d}", today=TODAY)]
    assert hit_days[0] == 21 and 22 in hit_days and 31 not in hit_days
