"""stats.py 測試(假匯出檔在 tmp、HTTP 與 run.bat 全 mock;不啟動後端、不打真後端)。
python -X utf8 -m pytest pipeline/tests/test_stats.py"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import stats as S  # noqa: E402
import paths as P  # noqa: E402

NOW = datetime(2026, 10, 27, 10, 0, 0)


def _win(views, basis="exact"):
    return {"views": views, "impressions": views * 5 if views else None, "ctr_pct": 5.0, "avg_view_pct": 45.0, "subs_net": 1,
            "browse_pct": 80.0, "basis": basis, "period": "first_48h", "captured_at": "2026-10-27T04:00:00", "age_hours": 48.5, "typical": {}}


def _vid(vid, tag, slot="", age=100.0, dur=420, views=1000, stale=False, w7="pending"):
    return {"video_id": vid, "slot": slot, "channel": S.SLOT_NAME[slot], "tag": tag, "ver": "v1", "title": f"標題{tag}",
            "published_at": "2026-10-20T10:00:00Z", "duration_s": dur, "is_self": 1, "age_hours": age, "deleted_at": None,
            "latest": {"captured_at": "2026-10-27T04:00:00", "age_hours": age, "views": views, "impressions": views * 5, "ctr_pct": 5.5,
                       "avg_view_pct": 44.0, "avg_view_s": 180, "watch_time_min": 100, "subs_net": 2, "typical": {"views": [800.0, 1500.0]}},
            "windows": {"48h": _win(views * 0.6), "7d": _win(views, "approx") if w7 == "approx" else _win(None, w7), "28d": _win(None, "pending")},
            "traffic_source": {"SUBSCRIBER": 70.0, "YT_SEARCH": 30.0}, "retention": [[0, 100], [100, 40]],
            "health": {"last_ok": "2026-10-27T04:00:00", "last_fail": None, "fail_reason": None, "consecutive_fails": 0, "stale": stale}}


def make_latest(gen="2026-10-27T05:00:00", missing=(), videos=None, alerts=()):
    vs = videos if videos is not None else [_vid("vidA", "tagA", age=200, views=2000, w7="approx"), _vid("vidB", "tagB", "c", age=50)]
    return {"schema_version": 1, "generated_at": gen, "tz": "+08:00", "data_as_of": "2026-10-27T04:00:00",
            "summary": {"videos": len(vs), "with_snapshot": len(vs), "missing_today_snapshot": list(missing), "alerts": len(alerts)},
            "videos": vs, "alerts": list(alerts)}


def _m(n, q1, med, q3):
    return {"n": n, "median": med, "q1": q1, "q3": q3}


def make_channel():
    base = {"kind": "self", "duration": "5to12", "duration_label": "5–12分", "n": 8,
            "metrics": {"views_7d": _m(8, 1000, 2000, 3000), "views_first7d": _m(6, 800, 1800, 2800), "avg_view_pct": _m(8, 40, 45, 50), "ctr_pct": _m(8, 5, 6, 7)}}
    other = dict(base, kind="other", n=30)
    cv = {"video_id": "vidA", "channel": "ChannelA", "slot": "", "title": "標題tagA", "published_at": "2026-10-20T10:00:00Z", "duration_s": 420,
          "is_self": True, "tag": "tagA", "age_days": 8.3, "views_7d": 4000, "views_first7d": 4000, "views_28d": 4000, "avg_view_pct": 45.0, "ctr_pct": 5.5}
    cn = dict(cv, video_id="vidN", is_self=False, tag=None, title="別人的片", views_7d=50)
    riv = {"video_id": "r1", "title": "Rival Hit", "channel_title": "RivalCh", "platform": "youtube", "published_at": "2026-10-25T00:00:00Z",
           "age_days": 2, "views": 100000, "views_per_day": 50000, "velocity_kind": "growth", "duration_s": 600}
    return {"schema_version": 1, "generated_at": "2026-10-27T05:00:00", "channels": [
        {"name": "ChannelA", "slot": "", "data_as_of": {"my_daily": "2026-10-24", "competitors": "2026-10-26T08:00:00"}, "warnings": [],
         "videos": [cv, cn], "baselines": [base, other], "rivals": [riv]},
        {"name": "ChannelC", "slot": "d", "data_as_of": {"my_daily": None, "competitors": None}, "warnings": [],
         "videos": [], "baselines": [], "rivals": []}]}


@pytest.fixture
def exp(tmp_path):
    d = tmp_path / "export"
    d.mkdir()
    (d / "latest.json").write_text(json.dumps(make_latest(), ensure_ascii=False), encoding="utf-8")
    (d / "channel_latest.json").write_text(json.dumps(make_channel(), ensure_ascii=False), encoding="utf-8")
    return d


@pytest.fixture(autouse=True)
def no_network(monkeypatch, tmp_path):
    """對外動作預設炸掉,測試要用就自己 mock(確保不會真的打後端或啟動 run.bat)。"""
    def boom(*a, **k):
        raise AssertionError("測試中不得連真後端/啟動行程")
    monkeypatch.setattr(S.urllib.request, "urlopen", boom)
    monkeypatch.setattr(S.subprocess, "Popen", boom)
    monkeypatch.setattr(S, "_sleep", lambda s: None)
    import topic_scout
    monkeypatch.setattr(topic_scout, "REBOUND_PATH", tmp_path / "rebound.json")   # hook 會覆寫 rebound.json,不得寫到真 repo


def out(argv, capsys, now=NOW):
    args = S.build_parser().parse_args(argv)
    lines = S.run(args, now)
    S.emit(lines, cap=S.HOOK_CAP if args.hook else S.LINE_CAP)
    return capsys.readouterr().out


def test_head_fresh_and_stale():
    ok = make_latest()
    assert S.freshness_info(ok, NOW)[0] is True
    assert "當天數據" in S.head_line(ok, NOW)
    old = make_latest(gen="2026-10-25T06:03:09", missing=["vidB"])
    line = S.head_line(old, NOW)
    assert line.startswith("⚠ 數據非當天:資料時間 2026-10-25T06:03:09") and "缺 1 支(tagB)" in line and "匯出非今天" in line
    miss = S.head_line(make_latest(missing=["vidA"]), NOW)
    assert miss.startswith("⚠ 數據非當天") and "匯出非今天" not in miss
    assert S.head_line(None, NOW).startswith("⚠ 數據非當天")


def test_summary_under_60_lines_and_first_line_has_time(exp, capsys):
    vs = [_vid(f"v{i}", f"t{i}", age=24.0 + i) for i in range(90)]
    (exp / "latest.json").write_text(json.dumps(make_latest(videos=vs)), encoding="utf-8")
    lines = out(["--export-dir", str(exp)], capsys).splitlines()
    assert len(lines) <= 60
    assert "資料時間 2026-10-27T05:00:00" in lines[0]
    assert "另" in lines[-1] and "略" in lines[-1]


def test_summary_missing_export(tmp_path, capsys):
    assert out(["--export-dir", str(tmp_path / "nope")], capsys).startswith("⚠ 數據非當天")


def test_tag_and_unknown(exp, capsys):
    t = out(["--export-dir", str(exp), "--tag", "tagA"], capsys)
    assert "標題tagA" in t and "7d  [approx]" in t and "流量來源" in t
    assert "找不到 nope" in out(["--export-dir", str(exp), "--tag", "nope"], capsys)
    assert "tagA" in out(["--export-dir", str(exp), "--tag", "vidA"], capsys)


def test_tag_traffic_7d_line_only_when_field_present(exp, capsys):
    assert "7d 來源" not in out(["--export-dir", str(exp), "--tag", "tagA"], capsys)
    lt = make_latest()
    lt["videos"][0]["traffic_7d"] = {"BROWSE": 600, "SUGGESTED": 300, "SEARCH": 100, "EXTERNAL": 0, "NOTIFICATION": 0, "OTHER": 0,
                                     "captured_at": "2026-10-27T04:00:00"}
    lt["videos"][0]["traffic_recent"] = {"BROWSE": 1, "SEARCH": 1}
    (exp / "latest.json").write_text(json.dumps(lt, ensure_ascii=False), encoding="utf-8")
    t = out(["--export-dir", str(exp), "--tag", "tagA"], capsys)
    assert "7d 來源:瀏覽 60% 推薦 30% 搜尋 10%(擷取 2026-10-27)" in t and "近7日來源:瀏覽 50% 搜尋 50%" in t and "外部" not in t
    assert "來源:" not in out(["--export-dir", str(exp), "--tag", "tagB"], capsys).replace("流量來源:", "")
    assert S.traffic_mix({"BROWSE": 0}) is None and S.traffic_mix("x") is None


def test_stale_only(exp, capsys):
    ok = out(["--export-dir", str(exp), "--stale"], capsys)
    assert ok.splitlines()[-1] == "無其他異常"
    vs = [_vid("vidA", "tagA", stale=True), _vid("vidB", "tagB", "c")]
    vs[1]["health"]["consecutive_fails"] = 3
    vs[1]["health"]["fail_reason"] = "x" * 200
    al = [{"video_id": "vidA", "tag": "tagA", "message": "61 小時無成功快照"}]
    (exp / "latest.json").write_text(json.dumps(make_latest(missing=["vidA"], videos=vs, alerts=al)), encoding="utf-8")
    t = out(["--export-dir", str(exp), "--stale"], capsys)
    assert "抓取異常:tagA 61 小時" in t and "缺當天快照:tagA" in t and "連續失敗 3 次:tagB" in t
    assert "x" * 100 not in t


def test_channel_compare_rivals(exp, capsys):
    t = out(["--export-dir", str(exp), "--channel", "ChannelA"], capsys)
    assert "[ChannelA]" in t and "自製 5–12分" in t and "非自製 5–12分" in t and "別人的片" in t
    c = out(["--export-dir", str(exp), "--channel", "ChannelA", "--compare"], capsys)
    assert "高於Q3" in c and "Rival Hit" in c and "首7日" in c          # 首7日 4000 > Q3 2800;口徑標明首7日
    r = out(["--export-dir", str(exp), "--channel", "ChannelC", "--rivals", "3"], capsys)
    assert "[ChannelC]" in r and "無競品資料" in r
    r2 = out(["--export-dir", str(exp), "--channel", "ChannelA", "--rivals", "5"], capsys)
    assert "Rival Hit" in r2
    assert "需要 --channel" in out(["--export-dir", str(exp), "--compare"], capsys)


def test_compare_young_video_not_positioned(exp, capsys):
    ch = make_channel()
    ch["channels"][0]["videos"][0]["age_days"] = 3.0
    ch["channels"][0]["videos"][0]["views_first7d"] = None
    (exp / "channel_latest.json").write_text(json.dumps(ch), encoding="utf-8")
    assert "未滿7天" in out(["--export-dir", str(exp), "--channel", "ChannelA", "--compare"], capsys)


def test_review_tag_history_and_baseline(exp, tmp_path, monkeypatch, capsys):
    for day, views in (("2026-10-25", 1200), ("2026-10-26", 1700)):
        v = _vid("vidA", "tagA", age=100, views=views, w7="approx")
        v["latest"]["captured_at"] = f"{day}T04:00:00"
        (exp / f"{day}.json").write_text(json.dumps(make_latest(videos=[v])), encoding="utf-8")
    proj = tmp_path / "projects"
    (proj / "tagA").mkdir(parents=True)
    (proj / "tagA" / "spec.json").write_text(json.dumps({"package": {"titles": [{"text": "計畫標題X", "angle": "數"}], "thumbs": []},
                                                         "result": {"48h": {"state": "ok", "views": 1200, "ctr": 5.0, "avg_view_pct": 44.0}}}), encoding="utf-8")
    monkeypatch.setattr(P, "PROJECTS", proj)
    t = out(["--export-dir", str(exp), "--review", "tagA"], capsys)
    assert "逐日曲線(3 天" in t and "2026-10-25" in t and "2026-10-26" in t and "2026-10-27" in t
    assert "對頻道自製基準" in t and "首7天觀看 2,000" in t and "中位以上" in t
    assert "計畫標題[數] 計畫標題X" in t and "spec.result 48h" in t


def test_review_channel_days(exp, capsys):
    t = out(["--export-dir", str(exp), "--review", "--channel", "ChannelA", "--days", "28"], capsys)
    assert "[ChannelA] 近 28 天自製片 1 支" in t and "tagA" in t and "tagB" not in t
    assert "需要 <tag>" in out(["--export-dir", str(exp), "--review"], capsys)


def _cv(vid, is_self, subs, views, age_days):
    return {"video_id": vid, "is_self": is_self, "subs_net": subs, "views_total": views, "age_days": age_days,
            "published_at": "2026-10-01T00:00:00Z", "duration_s": 420, "tag": vid, "title": vid}


def test_subs_per_k_helpers():
    assert S.subs_per_k(20, 100000) == pytest.approx(0.2)
    assert S.subs_per_k(5, 999) is None and S.subs_per_k(None, 5000) is None
    assert S.fpk(5, 999) == "-" and S.fpk(None, 5000) == "-"
    assert S.fpk(20, 100000) == "0.20" and S.fpk(2, 10000) == "0.20*" and S.fpk(-3, 10000) == "-0.30*"
    assert S.is_small_subs(4, 5000) and not S.is_small_subs(5, 5000) and not S.is_small_subs(4, 500)


def test_subs_groups_split_and_stats():
    ch = {"videos": [_cv("s1", True, 10, 10000, 5), _cv("s2", True, 30, 10000, 40), _cv("s3", True, 1, 500, 10),
                     _cv("s4", True, 8, 20000, 200), _cv("o1", False, 4, 4000, 30), _cv("o2", False, None, 9000, 30)]}
    g = S.subs_groups(ch, NOW)
    r = g[("self", "recent")]
    assert r["n"] == 2 and r["ratio"] == pytest.approx(2.0) and r["median"] == pytest.approx(2.0)   # s3 觀看<1000 不算
    assert g[("self", "old")]["n"] == 1 and g[("self", "old")]["ratio"] == pytest.approx(0.4)
    assert g[("other", "recent")]["n"] == 1 and g[("other", "old")] is None                       # o2 無 subs_net 不算
    lines = S.subs_baseline_lines(ch, NOW)
    assert lines[0].startswith("訂閱/千") and len(lines) == 3 and "n2" in lines[1] and "-" in lines[2]
    assert "歷史 n<8 不比(匯出只含近期片)" in lines[1] and "0.40" not in lines[1]       # 歷史 n=1 不印數值
    big = {"videos": [_cv(f"h{i}", True, 2, 10000, 200) for i in range(8)]}
    assert "歷史 0.20|0.20|n8" in S.subs_baseline_lines(big, NOW)[1]                 # n≥8 才印


def test_subs_columns_and_small_note(exp, capsys):
    ch = make_channel()
    ch["channels"][0]["videos"][0].update(subs_net=2, views_total=4000)       # 0.50*,淨增<5
    (exp / "channel_latest.json").write_text(json.dumps(ch), encoding="utf-8")
    c = out(["--export-dir", str(exp), "--channel", "ChannelA", "--compare"], capsys)
    assert "訂閱/千(合計|中位|n" in c and "訂/千 0.50*" in c and S.SUBS_NOTE in c
    t = out(["--export-dir", str(exp), "--tag", "tagA"], capsys)
    assert "訂閱 2(1.00*/千)" in t and t.count(S.SUBS_NOTE) == 1
    r = out(["--export-dir", str(exp), "--review", "--channel", "ChannelA"], capsys)
    assert "訂/千" in r and S.SUBS_NOTE in r
    rt = out(["--export-dir", str(exp), "--review", "tagA"], capsys)
    assert "訂閱/千 1.00* vs 同期自製合計" in rt and rt.count(S.SUBS_NOTE) == 1


class FakeBackend:
    """依序回覆 freshness;記錄 POST。"""
    def __init__(self, fresh_seq, up=True, refresh=None):
        self.seq = list(fresh_seq)
        self.up = up
        self.refresh = refresh or {"ok": True, "already_fresh": False, "jobs": [{"id": "j1"}], "blocked": []}
        self.posts = 0
        self.gets = 0

    def http(self, method, endpoint, timeout=3.0):
        if not self.up:
            return None, "URLError"
        if method == "POST":
            self.posts += 1
            return self.refresh, None
        self.gets += 1
        f = self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]
        return {"ok": True, "fresh": f}, None


def test_ensure_fresh_already(monkeypatch):
    fb = FakeBackend([True])
    monkeypatch.setattr(S, "http", fb.http)
    assert S.ensure_fresh(log=lambda m: None) == (True, "已是當天") and fb.posts == 0


def test_ensure_fresh_refreshes_and_polls(monkeypatch):
    fb = FakeBackend([False, False, False, True])
    monkeypatch.setattr(S, "http", fb.http)
    ok, note = S.ensure_fresh(log=lambda m: None)
    assert ok and fb.posts == 1 and fb.gets == 4


def test_ensure_fresh_timeout_does_not_block(monkeypatch):
    fb = FakeBackend([False])
    monkeypatch.setattr(S, "http", fb.http)
    ok, note = S.ensure_fresh(log=lambda m: None)
    assert not ok and "20 分鐘" in note and fb.posts == 1


def test_ensure_fresh_blocked(monkeypatch):
    fb = FakeBackend([False], refresh={"ok": True, "already_fresh": False, "jobs": [], "blocked": [{"mv_slot": "a", "reason": "chrome"}]})
    monkeypatch.setattr(S, "http", fb.http)
    ok, note = S.ensure_fresh(log=lambda m: None)
    assert not ok and "chrome" in note


def test_ensure_fresh_backend_down_launches_and_gives_up(monkeypatch):
    fb = FakeBackend([False], up=False)
    launched = []
    monkeypatch.setattr(S, "http", fb.http)
    monkeypatch.setattr(S, "launch_backend", lambda: (launched.append(1) or True, "已背景啟動"))
    ok, note = S.ensure_fresh(log=lambda m: None)
    assert not ok and note == "後端等不到" and launched == [1]


def test_ensure_fresh_backend_comes_up(monkeypatch):
    state = {"n": 0}

    def http(method, endpoint, timeout=3.0):
        if method == "GET":
            state["n"] += 1
            return (None, "down") if state["n"] < 3 else ({"fresh": True}, None)
        return {"jobs": []}, None
    monkeypatch.setattr(S, "http", http)
    monkeypatch.setattr(S, "launch_backend", lambda: (True, "ok"))
    assert S.ensure_fresh(log=lambda m: None)[0] is True


def test_run_ensure_fresh_failure_marks_stale(exp, monkeypatch, capsys):
    (exp / "latest.json").write_text(json.dumps(make_latest(gen="2026-10-25T06:03:09", missing=["vidB"])), encoding="utf-8")
    monkeypatch.setattr(S, "ensure_fresh", lambda log=print: (False, "後端等不到"))
    t = out(["--export-dir", str(exp), "--ensure-fresh"], capsys)
    assert t.splitlines()[0].startswith("⚠ 數據非當天:資料時間 2026-10-25T06:03:09") and "後端等不到" in t.splitlines()[0]


def test_hook_three_lines_backend_down(exp, monkeypatch, capsys):
    monkeypatch.setattr(S, "http", lambda *a, **k: (None, "down"))
    launched = []
    monkeypatch.setattr(S, "launch_backend", lambda: (launched.append(1) or True, "已背景啟動 run.bat autostart"))
    t = out(["--export-dir", str(exp), "--hook"], capsys)
    assert len(t.splitlines()) == 4 and t.splitlines()[3].startswith("[回溫]") and launched == [1] and "後端沒開" in t and "資料時間" in t


def test_hook_stale_triggers_bg_refresh(exp, monkeypatch, capsys):
    monkeypatch.setattr(S, "http", lambda *a, **k: ({"fresh": False}, None))
    called = []
    monkeypatch.setattr(S, "spawn_bg_refresh", lambda: called.append(1) or True)
    (exp / "latest.json").write_text(json.dumps(make_latest(gen="2026-10-25T06:03:09", missing=["vidB"])), encoding="utf-8")
    t = out(["--export-dir", str(exp), "--hook"], capsys)
    assert called == [1] and "刷新已觸發" in t and "非當天" in t


def test_hook_fresh_no_refresh(exp, monkeypatch, capsys):
    monkeypatch.setattr(S, "http", lambda *a, **k: ({"fresh": True}, None))
    monkeypatch.setattr(S, "spawn_bg_refresh", lambda: (_ for _ in ()).throw(AssertionError("不該刷新")))
    t = out(["--export-dir", str(exp), "--hook"], capsys)
    assert "後端回報已是當天" in t


def test_hook_error_only_warns(exp, monkeypatch, capsys):
    monkeypatch.setattr(S, "cmd_hook", lambda d, now=None: (_ for _ in ()).throw(RuntimeError("壞了")))
    assert S.main(["--hook", "--export-dir", str(exp)]) == 0
    assert "警告" in capsys.readouterr().out


def test_resolve_slot():
    assert S.resolve_slot("ChannelA") == "" and S.resolve_slot("ChannelB") == "c" and S.resolve_slot("ChannelC") == "d"
    assert S.resolve_slot("xx") is None and S.resolve_slot(None) is None
