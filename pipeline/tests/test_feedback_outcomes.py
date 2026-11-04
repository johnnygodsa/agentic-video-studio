"""feedback.py --due / feedback_report.py 測試(假 latest.json 與假 projects/build,全在 tmp,不碰正式 outcomes/scorecard)。
python -X utf8 -m pytest pipeline/tests/test_feedback_outcomes.py"""
import json
import shutil
import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import feedback as FB  # noqa: E402
import feedback_report as FR  # noqa: E402
import paths as P  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "feedback" / "latest.json"


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
    _w(root / "projects/fb_new/spec.json", {"tag": "fb_new", "package": {"subject": ["蝙蝠俠"], "titles": [{"text": "x", "angle": "判"}]}})
    _w(root / "projects/fb_new/context.json", {"brief": {"event_id": "ev1", "competitor_videos_7d": 5, "same_event_seq": 2}})
    _w(root / "build/fb_new/structure.json", {"hook_type": "反差", "judge_sec": 12.5, "blocks": [1, 2, 3, 4], "chars_per_min": 330, "facts_per_min": 4.2})
    _w(root / "build/fb_new/facts_check.json", {"link_pct": 0.8})
    (root / "projects/fb_old").mkdir(parents=True)   # 沒有 spec.json、structure.json
    export = tmp_path / "latest.json"
    shutil.copy(FIX, export)
    return root, export


def run(export, *args):
    FB.main(["--export", str(export), *args])


def test_due_writes_outcomes_and_scorecard(env):
    root, export = env
    run(export, "--due")
    rows = FB.read_outcomes()
    assert set(rows) == {"AAAAAAAAAAA", "BBBBBBBBBBB"}    # 非 is_self 不收
    r = rows["AAAAAAAAAAA"]
    assert r["publish_mode"] == "scheduled" and r["hook_type"] == "反差" and r["judge_sec"] == 12.5
    assert r["blocks"] == 4 and r["subject"] == "蝙蝠俠" and r["title_angle"] == "判"
    assert r["event_id"] == "ev1" and r["competitor_videos_7d"] == 5 and r["same_event_seq"] == 2
    assert r["facts_link_pct"] == 80.0 and r["duration_bucket"] == "<5分"
    assert r["hour"] == 12 and r["weekday"] == 2          # 04:49Z = 台北 12:49,2026-10-14 週三
    assert r["primary_window"] == "72h" and r["perf"]["72h"]["impressions"] == 7000
    assert r["perf"]["latest"]["browse_pct"] is None       # 缺值不用 SUBSCRIBER 代填
    assert r["angle"] == "判" and r["thumb_plan"] is None and r["note"] is None   # angle 由 spec 第 1 標題帶入
    assert r["comments_flags"] == ["quote_mismatch"]
    lines = [json.loads(x) for x in (root / "channel/outcomes.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["video_id"] for x in lines] == ["BBBBBBBBBBB", "AAAAAAAAAAA"]    # 依 published_at 排序
    sc = (root / "channel/scorecard.md").read_text(encoding="utf-8")
    assert sc.count("| 發布 |") == 1 and "鉤子" in sc and "48h(公開起算)" in sc and "7d(公開起算)" in sc and "72h(公開起算)" not in sc and "AAAAAAAAAAA" in sc and "CCCCCCCCCCC" not in sc


def test_rerun_overwrites_and_keeps_manual(env):
    root, export = env
    run(export, "--video", "AAAAAAAAAAA", "--angle", "A1", "--plan", "2")
    run(export, "--due")
    d = json.loads(export.read_text(encoding="utf-8"))
    d["videos"][0]["windows"]["48h"]["impressions"] = 9999.0
    export.write_text(json.dumps(d), encoding="utf-8")
    run(export, "--due")
    rows = FB.read_outcomes()
    assert len((root / "channel/outcomes.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    r = rows["AAAAAAAAAAA"]
    assert r["perf"]["48h"]["impressions"] == 9999.0
    assert r["angle"] == "A1" and r["thumb_plan"] == "2"       # 手動欄位沿用
    sc = (root / "channel/scorecard.md").read_text(encoding="utf-8")
    assert sc.count("AAAAAAAAAAA") == 1 and "9999" in sc


def test_single_video_writes_spec_result(env):
    root, export = env
    run(export, "--video", "AAAAAAAAAAA", "--tag", "fb_new", "--plan", "1")
    spec = json.loads((root / "projects/fb_new/spec.json").read_text(encoding="utf-8"))
    assert spec["result"]["video_id"] == "AAAAAAAAAAA" and spec["package"]["subject"] == ["蝙蝠俠"]


def test_retention_interpolation():
    curve = [[0.0, 100.0], [10.0, 80.0], [20.0, 60.0]]
    assert FB.retention_at(curve, 15.0) == pytest.approx(70.0)
    assert FB.retention_at(curve, 0.0) == 100.0 and FB.retention_at(curve, 20.0) == 60.0
    assert FB.retention_at(curve, 25.0) is None and FB.retention_at([], 5.0) is None
    assert FB.retention_at(curve, None) is None


def test_retention_30s_in_row(env):
    _, export = env
    run(export, "--due")
    rows = FB.read_outcomes()
    assert rows["AAAAAAAAAAA"]["retention_30s_pct"] == pytest.approx(70.0)   # 200 秒 -> 15% 位置
    assert rows["AAAAAAAAAAA"]["retention_curve_n"] == 5


def test_old_video_without_project_and_deleted(env):
    """沒有 projects 資料夾的 is_self 舊片入庫(特徵 null);deleted_at 的片不入庫,已在 outcomes 的被清掉並備份。"""
    root, export = env
    d = json.loads(export.read_text(encoding="utf-8"))
    base = d["videos"][0]
    d["videos"] += [dict(base, video_id="OLDNOPROJ01", tag="old_no_proj", title="舊片", hook_type=None),
                    dict(base, video_id="DELETEDVID1", tag="fb_new", deleted_at="2026-10-30T10:00:00")]
    export.write_text(json.dumps(d), encoding="utf-8")
    (root / "channel/outcomes.jsonl").write_text(json.dumps({"video_id": "DELETEDVID1", "published_at": "2026-10-01"}) + "\n", encoding="utf-8")
    run(export, "--due")
    rows = FB.read_outcomes()
    assert set(rows) == {"AAAAAAAAAAA", "BBBBBBBBBBB", "OLDNOPROJ01"}
    o = rows["OLDNOPROJ01"]
    assert o["tag"] == "old_no_proj" and o["subject"] is None and o["angle"] is None and o["note"] is None and o["hook_type"] is None
    assert list((root / "tmp").glob("outcomes_backup_*.jsonl"))


def test_plan_fields_from_spec_and_handoff(env):
    root, _ = env
    _w(root / "projects/fb_new/spec.json", {"package": {"titles": [{"text": "x", "angle": "反"}], "thumbs": [{"plan": 2, "angle": "反"}]}})
    (root / "projects/fb_new/handoff.md").write_text("- 風險:abc\n- 預失敗:同題第 3 支疲勞,CTR 低於 7%。\n", encoding="utf-8")
    assert FB.plan_fields("fb_new") == ("反", "2", "同題第 3 支疲勞,CTR 低於 7%。")
    (root / "projects/fb_old/handoff.md").write_text("結案回填切角 決、封面方案 1\n", encoding="utf-8")
    assert FB.plan_fields("fb_old") == ("決", "1", None)
    assert FB.plan_fields("nope") == (None, None, None)


def test_missing_fields_degrade(env):
    _, export = env
    run(export, "--due")
    r = FB.read_outcomes()["BBBBBBBBBBB"]
    assert r["publish_mode"] == "unknown" and r["duration_bucket"] is None and r["retention_30s_pct"] is None
    assert r["retention_curve_n"] == 0 and r["hook_type"] is None and r["judge_sec"] is None
    assert r["facts_link_pct"] is None and r["comments_flags"] is None and r["perf"]["latest"] is None
    assert r["primary_window"] == "7d" and r["perf"]["72h"] is None


def test_min_age_and_dry_run(env):
    root, export = env
    run(export, "--due", "--min-age-h", "150", "--dry-run")
    assert not (root / "channel/outcomes.jsonl").exists()
    run(export, "--due", "--min-age-h", "150")
    assert set(FB.read_outcomes()) == {"BBBBBBBBBBB"}


def test_legacy_scorecard_rows_kept(env):
    root, export = env
    old = "| 發布 | 頻道 | tag | video_id | 標題 | 切角 | 封面 |\n|---|---|---|---|---|---|---|\n| 2026-01-01 | ChannelA | old | OLDVIDEO001 | t | A | 1 |\n"
    (root / "channel/scorecard.md").write_text("# x\n\n" + old, encoding="utf-8")
    run(export, "--due")
    run(export, "--due")
    sc = (root / "channel/scorecard.md").read_text(encoding="utf-8")
    assert sc.count("OLDVIDEO001") == 1 and "舊格式列" in sc and sc.count("AAAAAAAAAAA") == 1


# ---------------------------------------------------------------- feedback_report
def _fake(i, ch="ChannelA", **kw):
    r = {"video_id": f"V{i:03d}", "is_self": 1, "channel": ch, "duration_s": 420,
         "primary_window": "7d", "hook_type": "反差" if i % 2 else "事件", "judge_sec": 10 + i, "title_angle": "判", "thumb_plan": "1",
         "subject": "a", "same_event_seq": 1, "competitor_videos_7d": 2, "hour": 12, "chars_per_min": 300 + i, "blocks": 4,
         "retention_30s_pct": 60 + i,
         "perf": {"7d": {"views": 1000, "impressions": 1000 * (i + 1), "ctr_pct": 4 + i * 0.1, "avg_view_pct": 40 + i, "subs_net": i}}}
    r.update(kw)
    return r


def test_report_small_n_all_insufficient():
    text = FR.build_report([_fake(i) for i in range(5)])
    assert "已知偏差" in text and "A/B 測試的混合值" in text and "互動觀看" in text and "排程片" in text and "typical" in text
    assert "資料不足(n=5)" in text
    assert "ρ=" not in text and "中位" not in text.split("## ChannelA")[1].replace("中位差", "")    # 沒有任何格印結論
    assert "沒有符合門檻" in text


def test_report_n20_tables_and_spearman():
    rows = [_fake(i) for i in range(20)]
    text = FR.build_report(rows)
    assert "ρ=+1.00" in text            # judge_sec 與 impressions 完全單調
    assert "[IQR" in text and "ChannelA/≤10分(n=20)" in text
    assert "反差" in text and "事件" in text


def test_report_strata_separate():
    rows = [_fake(i) for i in range(10)] + [_fake(100 + i, ch="ChannelB") for i in range(3)] + [_fake(200, is_self=0)]
    text = FR.build_report(rows)
    assert "ChannelB/≤10分(n=3)" in text and "ChannelA/≤10分(n=10)" in text and "V200" not in text
    assert "自製片 13 支" in text


def test_lesson_threshold():
    # 兩組各 10 支:A 曝光中位 ~1000、B ~5000,組內窄 -> 教訓;組內寬且重疊 -> 無教訓
    a = [_fake(i, hook_type="A", perf={"7d": {"impressions": 1000 + i, "views": 1}}) for i in range(10)]
    b = [_fake(50 + i, hook_type="B", perf={"7d": {"impressions": 5000 + i, "views": 1}}) for i in range(10)]
    sure, _ = FR.lessons(a + b, "x")
    assert any("鉤子型態" in s and "曝光" in s for s in sure)
    a2 = [_fake(i, hook_type="A", perf={"7d": {"impressions": 1000 * (i + 1), "views": 1}}) for i in range(10)]
    b2 = [_fake(50 + i, hook_type="B", perf={"7d": {"impressions": 1000 * (i + 1) + 100, "views": 1}}) for i in range(10)]
    sure2, _ = FR.lessons(a2 + b2, "x")
    assert not any("鉤子型態" in s and "曝光" in s for s in sure2)
    # 一組 n=5(<8):不列教訓,列候選
    sure3, cand3 = FR.lessons(a[:5] + b, "x")
    assert not any("鉤子型態" in s and "曝光" in s for s in sure3)
    assert any("鉤子型態" in s and "曝光" in s for s in cand3)


def test_spearman_ties_and_none():
    assert FR.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert FR.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert FR.spearman([1, 1, 1], [1, 2, 3]) is None
    assert FR.quantile([1, 2, 3, 4], 0.5) == 2.5 and FR.iqr([1, 2, 3, 4, 5]) == 2


def test_report_cli(env, tmp_path):
    root, export = env
    run(export, "--due")
    out = tmp_path / "r.md"
    FR.main(["--outcomes", str(root / "channel/outcomes.jsonl"), "--out", str(out)])
    assert "已知偏差" in out.read_text(encoding="utf-8")


def test_report_window_fixed_7d_and_excludes_handed_off():
    a = [_fake(i, perf={"48h": {"impressions": 99999, "views": 1}}) for i in range(3)]        # 只有 48h:不進分層表
    b = [_fake(10 + i, duration_s=900) for i in range(8)]                                       # >10 分帶
    c = [_fake(30 + i, ch="ChannelC") for i in range(8)]                                       # 已交出
    text = FR.build_report(a + b + c)
    assert "ChannelA/>10分(n=8)" in text and "≤10分" not in text and "ChannelC/" not in text
    assert "發布時段" not in text and "publish_mode" not in text and "99,999" not in text and "99999" not in text


def test_structure_computed_from_script_and_cached(env, monkeypatch):
    """projects / build 都沒有 structure.json 時,用 script_structure.analyze 即時算(script.txt),存回 projects;
    已有 projects 版本就不重算;沒有 script.txt 維持 null。"""
    import script_structure as SS
    root, export = env
    (root / "build/fb_new/structure.json").unlink()
    (root / "fb_new").mkdir()
    (root / "fb_new/script.txt").write_text("x", encoding="utf-8")
    calls = []

    def fake(src, paths=()):
        calls.append(src)
        return {"hook_type": "反差", "judge_sec": 7.5, "blocks": [1, 2, 3], "chars_per_min": 320, "facts_per_min": 5}
    monkeypatch.setattr(SS, "analyze", fake)
    run(export, "--due")
    r = FB.read_outcomes()["AAAAAAAAAAA"]
    assert r["hook_type"] == "反差" and r["judge_sec"] == 7.5 and r["blocks"] == 3
    saved = root / "projects/fb_new/structure.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["judge_sec"] == 7.5 and len(calls) == 1
    run(export, "--due")                                  # 第二次讀 projects 版本,不重算
    assert len(calls) == 1
    assert FB.structure_for("fb_old") == {} and FB.structure_for(None) == {}    # 沒有 script.txt -> null
