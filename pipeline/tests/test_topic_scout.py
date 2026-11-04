"""topic_scout.py 測試(假匯出檔與留言檔在 tmp;子行程以假 runner 取代,不打真 Youtube AD)。
python -X utf8 -m pytest pipeline/tests/test_topic_scout.py"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import topic_scout as T  # noqa: E402

START = date(2026, 10, 10)


def _row(vid, total, last, is_self=0, age=100.0, tag=None):
    return {"video_id": vid, "channel": "ChannelA", "slot": "", "title": f"標題{vid}", "published_at": "2026-06-01T00:00:00Z",
            "duration_s": 400, "is_self": is_self, "tag": tag, "age_days": age, "views_total": total, "my_daily_last": last}


def make_export(tmp, daily, extra_rows=None):
    """daily: {video_id: [每日觀看...]};產生連續日期副本(第 i 份的 my_daily_last = START+i,累計 = 前綴和)。"""
    n = max(len(v) for v in daily.values())
    for i in range(n):
        day = (START + timedelta(days=i)).isoformat()
        rows = [_row(vid, 1000 + sum(vals[:i + 1]), day, is_self=(vid == "selfA"), tag="tagA" if vid == "selfA" else None)
                for vid, vals in daily.items() if len(vals) > i]
        data = {"generated_at": day + "T08:00:00", "channels": [{"slot": "", "name": "ChannelA", "videos": rows + (extra_rows or [])}]}
        name = "channel_latest.json" if i == n - 1 else f"channel_{day}.json"
        (tmp / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if i == n - 1:   # 同時留一份日期副本,latest 與它同 my_daily_last -> 應去重
            (tmp / f"channel_{day}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return tmp


def test_daily_series_diff_and_spread():
    s = T.daily_series([("2026-10-10", 100), ("2026-10-11", 130), ("2026-10-14", 220)])
    assert [(d, v, sp) for d, v, sp in s] == [("2026-10-11", 30.0, False), ("2026-10-12", 30.0, True), ("2026-10-13", 30.0, True), ("2026-10-14", 30.0, True)]
    assert T.daily_series([("2026-10-10", 100), ("2026-10-11", 90)]) == []   # 累計倒退略過


def test_detect_pullback_hit_and_threshold():
    flat = [("2026-10-%02d" % (10 + i), 100.0, False) for i in range(8)]
    hit = T.detect_pullback(flat + [("2026-10-18", 350.0, False)])
    assert hit["hit"] and hit["ratio"] == 3.5 and hit["median"] == 100.0
    assert not T.detect_pullback(flat + [("2026-10-18", 290.0, False)])["hit"]        # < 3x
    low = [("2026-10-%02d" % (10 + i), 10.0, False) for i in range(8)]
    assert not T.detect_pullback(low + [("2026-10-18", 90.0, False)])["hit"]           # 9x 但 < 100
    assert "不足" in T.detect_pullback(flat[:3])["reason"]


def test_section_b_hits_old_video_only(tmp_path):
    daily = {"oldA": [100] * 9 + [400],            # 舊片,最新日 4x -> 命中
             "oldB": [100] * 9 + [150],            # 舊片,未達
             "selfA": [50] * 9 + [1000]}           # age <= 7 -> 不判
    d = make_export(tmp_path, daily, None)
    # selfA age 設為 3 天
    for p in tmp_path.glob("*.json"):
        j = json.loads(p.read_text(encoding="utf-8"))
        for r in j["channels"][0]["videos"]:
            if r["video_id"] == "selfA":
                r["age_days"] = 3.0
        p.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    latest = {"videos": []}
    lines, n = T.section_b(d, "", latest)
    text = "\n".join(lines)
    assert n == 1 and "oldA" in text.split("回推命中 1 支:")[1].split("未達門檻")[0]
    assert "oldB" not in text.split("未達門檻")[0] and "selfA" not in text
    assert "無來源資料" in text


def test_section_b_self_traffic_sources(tmp_path):
    d = make_export(tmp_path, {"selfA": [100] * 9 + [500]})
    for p in tmp_path.glob("*.json"):
        j = json.loads(p.read_text(encoding="utf-8"))
        j["channels"][0]["videos"][0]["age_days"] = 30.0
        p.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    latest = {"videos": [{"video_id": "selfA", "traffic_source": {"YT_SEARCH": 30.0, "SUBSCRIBER": 60.0, "YT_RELATED": 8.0, "X": 2.0}}]}
    lines, n = T.section_b(d, "", latest)
    assert n == 1
    assert "SUBSCRIBER 60.0% / YT_SEARCH 30.0% / YT_RELATED 8.0%" in "\n".join(lines)


def test_section_b_no_data_degrades(tmp_path):
    lines, n = T.section_b(tmp_path, "", None)
    assert n == 0 and lines[0].startswith("不可用")


def test_comment_summary_uses_summary_or_lexicon():
    doc = {"comments": [{"text": "AI配音好煩", "like_count": 5}, {"text": "沒意見", "like_count": 9}, {"text": "x" * 200, "like_count": 1}],
           "summary": {"by_flag": {"AI": 3, "資訊錯誤": 0}}}
    by, ai, src, top, n = T.comment_summary(doc)
    assert (ai, src, n) == (3, "summary", 3) and top[0][0] == 9 and len(top[2][1]) == 80
    doc2 = {"comments": doc["comments"], "summary": {}}                    # summary 缺 -> 詞表
    by, ai, src, top, n = T.comment_summary(doc2)
    assert src == "comment_lexicon.json" and by.get("AI", 0) >= 1


def test_section_c_missing_files_noted(tmp_path):
    cdir = tmp_path / "c"
    cdir.mkdir()
    (cdir / "v1.json").write_text(json.dumps({"captured_at": "2026-10-29T10:00:00", "status": "ok",
                                              "comments": [{"text": "好", "like_count": 2}], "summary": {"by_flag": {"AI": 1}}}), encoding="utf-8")
    latest = {"videos": [{"video_id": "v1", "slot": "", "is_self": 1, "tag": "t1", "published_at": "2026-10-28T00:00:00Z", "age_hours": 24},
                         {"video_id": "v2", "slot": "", "is_self": 1, "tag": "t2", "published_at": "2026-10-29T00:00:00Z", "age_hours": 2}]}
    lines, n = T.section_c(latest, "", cdir)
    assert n == 1 and "無留言檔:t2" in lines[0] and any("讚2" in x for x in lines)


def test_section_d_failure_degrades():
    lines, n = T.section_d("", runner=lambda cmd, cwd=None: (False, "結束碼 2:boom"))
    assert n == 0 and sum("不可用:結束碼 2:boom" in x for x in lines) == 2
    ok = lambda cmd, cwd=None: (True, "> 註解\n\nrow1\nrow2\n")
    lines, n = T.section_d("c", runner=ok)
    assert n == 4 and "  row1" in lines


def test_section_e_present_and_absent(tmp_path):
    assert "未讀 Studio" in T.section_e("2026-10-29", tmp_path)[0][0]
    (tmp_path / "studio_2026-10-29.txt").write_text("\n".join(f"L{i}" for i in range(100)), encoding="utf-8")
    lines, n = T.section_e("2026-10-29", tmp_path)
    assert n == 80 and "L79" in lines and "L80" not in lines


def test_build_survives_missing_everything(tmp_path):
    text, counts = T.build("", "2026-10-29", export_dir=tmp_path / "none", comments_dir=tmp_path / "nocomments", tmp_dir=tmp_path,
                           runner=lambda cmd, cwd=None: (False, "x"))
    for k in "abcde":
        assert f"## {k}." in text
    assert counts["b(回推命中)"] == 0 and "不可用" in text and "未讀 Studio" in text


def _ser(vals, spread=False):
    return [("2026-10-%02d" % (1 + i), float(v), spread) for i, v in enumerate(vals)]


def test_slow_ramp_hits_and_13x_misses():
    ramp = _ser([200] * 7 + [300] * 7)                        # 前7日 1400、近7日 2100 = 1.5x,單日無爆量
    r = T.detect_pullback(ramp)
    assert r["hit"] and r["types"] == ["緩升"] and r["week_ratio"] == 1.5 and r["prev_src"] == "逐日"
    assert not T.detect_pullback(_ser([200] * 7 + [260] * 7))["hit"]       # 1.3x 不命中
    assert not T.detect_pullback(_ser([20] * 7 + [40] * 7))["hit"]          # 2x 但日均 < 100
    burst = T.detect_pullback(_ser([100] * 13 + [400]))
    assert burst["hit"] and "單日爆量" in burst["types"]


def test_slow_uses_views_7d_when_prior_days_short_and_flags_filled():
    s = _ser([300] * 7, spread=True)                          # 只有近 7 日;前 7 日合計靠 API views_7d
    r = T.detect_pullback(s, prior_week_api=1400)
    assert r["hit"] and r["prev_src"] == "views_7d" and r["filled"]
    assert not T.detect_pullback(s, prior_week_api=1700)["hit"]            # 1.24x
    assert T.detect_pullback(s)["week_ratio"] is None                      # 沒有任何前段 -> 不判緩升


def test_section_b_slow_ramp_labelled(tmp_path):
    d = make_export(tmp_path, {"oldS": [200] * 8 + [300] * 7, "oldF": [200] * 8 + [260] * 7})
    lines, n = T.section_b(d, "", {"videos": []})
    text = "\n".join(lines)
    hit_part = text.split("回推命中 1 支:")[1].split("未達門檻")[0]
    assert n == 1 and "oldS" in hit_part and "觸發類型:緩升" in hit_part and "oldF" not in hit_part


def test_section_persona_expired_and_ok():
    exp = lambda n: {"status": "過期", "n_now": 130, "n_persona": 100, "reason": "自製留言 100→130(+30%)"}  # noqa: E731
    lines, n = T.section_persona("ChannelA", exp)
    assert n == 1 and "人設過期(自製留言 100→130(+30%)):選題會議前先重寫 channel\\audience\\ChannelA_personas.md,再派 topic-critic" in lines
    ok = lambda n: {"status": "OK", "n_now": 100, "n_persona": 100, "reason": "人設仍有效"}  # noqa: E731
    lines, n = T.section_persona("ChannelA", ok)
    assert n == 0 and len(lines) == 1 and "OK" in lines[0]


def test_build_has_persona_section_before_a(tmp_path):
    text, counts = T.build("", "2026-10-29", export_dir=tmp_path, comments_dir=tmp_path, tmp_dir=tmp_path,
                           runner=lambda cmd, cwd=None: (False, "x"))
    assert "## 人設狀態" in text and text.index("## 人設狀態") < text.index("## a. ")
    assert "人設(過期=1)" in counts
