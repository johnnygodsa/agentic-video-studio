"""tts_dispatch 測試:假帳本、假 quota/kaggle_run/pack/board,不連網。"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline" / "remote"))
sys.path.insert(0, str(ROOT / "pipeline"))
import tts_dispatch as td  # noqa: E402

NOW = datetime(2026, 10, 28, 12, 0, 0)


class Env:
    pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    e = Env()
    e.tmp = tmp_path
    e.remote = tmp_path / "remote"
    e.remote.mkdir()
    tok = tmp_path / "kaggle.json"
    tok.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(td.KR, "REMOTE", e.remote)
    monkeypatch.setenv("CV_KAGGLE_TOKEN_FILE", str(tok))
    e.tok = tok
    e.quota = 20.0
    monkeypatch.setattr(td.KR, "quota", lambda kind="GPU": e.quota)
    e.publish = None
    monkeypatch.setattr(td, "board_publish", lambda tag: e.publish)
    monkeypatch.setattr(td, "count_lines", lambda tag: 85)
    monkeypatch.setattr(td, "c0_status", lambda tag: (True, "已通過"))
    e.boards, e.launched, e.packs, e.imports = [], [], [], []
    monkeypatch.setattr(td, "board_set", lambda tag, text: e.boards.append((tag, text)))
    monkeypatch.setattr(td, "launch_kaggle", lambda tag, fg=False: (e.launched.append((tag, fg)) or (0, e.remote / tag / "run.log")))
    e.pack_rc = 0
    monkeypatch.setattr(td, "pack_colab", lambda tag: (e.packs.append(tag) or (e.pack_rc, e.tmp / f"colab_{tag}.zip")))
    e.import_rc = 0
    monkeypatch.setattr(td, "run_import", lambda z: (e.imports.append(str(z)) or e.import_rc))
    return e


def ledger(e, *rows):
    with open(e.remote / "usage.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def rows(e):
    f = e.remote / "usage.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()] if f.is_file() else []


def start(tag, backend, at="2026-10-28T10:00:00"):
    return {"event": "start", "tag": tag, "backend": backend, "start": at}


def end(tag, backend, **kw):
    return dict({"event": "end", "tag": tag, "backend": backend}, **kw)


# ---------- 預估與發布時間 ----------

def test_estimate_hours():
    assert td.estimate_hours(85) == pytest.approx(85 * 46 / 3600 + 0.25)
    assert td.estimate_hours(0) == pytest.approx(0.25)


def test_count_lines_json_and_txt(tmp_path, monkeypatch):
    monkeypatch.setattr(td.P, "REPO", tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "script.json").write_text(
        json.dumps({"sections": [{"lines": [1, 2, 3]}, {"lines": [4]}]}), encoding="utf-8")
    assert td.count_lines("a") == 4
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "script.txt").write_text("# 註解\n\n一句\n兩句\n", encoding="utf-8")
    assert td.count_lines("b") == 2
    assert td.count_lines("nope") == 0


def test_parse_publish():
    assert td.parse_publish("2026-10-30") == datetime(2026, 10, 30, 18, 0)
    assert td.parse_publish("2026-10-30T09:30:00") == datetime(2026, 10, 30, 9, 30)
    assert td.parse_publish("") is None and td.parse_publish("亂") is None


# ---------- survey:三後端都評估,建議順序 Colab -> Kaggle -> 本機 ----------

def sug(tag="t1", now=NOW):
    return td.survey(tag, now=now)


def test_survey_colab_first_and_all_evaluated(env):
    s, av, why, _ = sug()
    assert s == "colab" and av["colab"][0] and av["kaggle"][0] and av["local"][0]   # 不因 Colab 可用就停
    txt = " ".join(why)
    assert "Colab 可用" in txt and "Kaggle 可用" in txt and "本機 可用" in txt


def test_colab_busy_suggests_kaggle(env):
    ledger(env, start("x", "colab"))
    s, av, why, _ = sug()
    assert s == "kaggle" and "Colab 被占用" in " ".join(why) and "Kaggle 可用" in " ".join(why)


def test_kaggle_busy_one_suggests_local(env):
    ledger(env, start("x", "colab"), start("y", "kaggle"))
    s, av, why, _ = sug()
    assert s == "local" and "並行已滿(1/1" in " ".join(why) and "本機已有配音在排隊" in " ".join(why)


def test_three_jobs_one_per_backend_fourth_local(env):
    picks = []
    for tag in ("t1", "t2", "t3", "t4"):
        b = sug(tag)[0]
        picks.append(b)
        if b != "local":   # 模擬該後端寫了 start
            with open(env.remote / "usage.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(start(tag, b)) + chr(10))
    assert picks == ["colab", "kaggle", "local", "local"]


def test_kaggle_max_constant_relaxes(env, monkeypatch):
    monkeypatch.setattr(td, "KAGGLE_MAX", 2)
    ledger(env, start("x", "colab"), start("y", "kaggle"))
    assert sug()[0] == "kaggle"


def test_finished_kaggle_job_frees_slot(env):
    ledger(env, start("x", "colab"), start("a", "kaggle"), end("a", "kaggle", gpu_hours=1.0))
    assert sug()[0] == "kaggle"


def test_stale_kaggle_start_not_counted(env):
    ledger(env, start("x", "colab"), start("a", "kaggle", "2026-10-27T01:00:00"))
    assert sug()[0] == "kaggle"


def test_skip_is_noop_compat(env, capsys):
    assert td.main(["t1", "--skip", "colab", "--skip", "kaggle"]) == 4
    assert "建議:colab" in capsys.readouterr().out   # skip 不影響建議,也不觸發任何動作
    assert env.packs == [] and env.launched == [] and env.boards == [] and rows(env) == []


def test_kaggle_token_missing_with_colab_busy_suggests_local(env):
    env.tok.unlink()
    ledger(env, start("x", "colab"))
    s, av, why, _ = sug()
    assert s == "local" and not av["kaggle"][0] and "token" in " ".join(why)


def test_quota_insufficient(env):
    env.quota = 3.0   # 預估 85 句 ≈ 1.35h + 2h = 3.35h
    s, av, why, _ = sug()
    assert not av["kaggle"][0] and "配額不足" in " ".join(why)


def test_quota_exactly_enough(env):
    env.quota = td.estimate_hours(85) + td.QUOTA_BUFFER_H
    assert sug()[1]["kaggle"][0]


def test_quota_none_marks_kaggle_unavailable(env):
    env.quota = None
    ledger(env, start("x", "colab"))
    s, av, why, _ = sug()
    assert s == "local" and "查不到" in " ".join(why)


def test_colab_unavailable_when_publish_within_6h(env):
    env.publish = NOW + timedelta(hours=5)
    s, av, why, _ = sug()
    assert s == "kaggle" and not av["colab"][0] and "剩不到 6 小時" in " ".join(why)
    env.publish = NOW + timedelta(hours=7)
    assert sug()[0] == "colab"


def test_choose_requires_prefer(env):
    with pytest.raises(ValueError):
        td.choose("t1", None)


# ---------- 沒給 --prefer:只問不做 ----------

def test_no_prefer_asks_user_exit4(env, capsys):
    assert td.main(["t1"]) == 4
    out = capsys.readouterr().out
    assert "Colab 可用" in out and "Kaggle 可用" in out and "本機 可用" in out
    assert "建議:colab" in out and "--prefer colab|kaggle|local" in out and "請問使用者" in out
    assert env.packs == [] and env.launched == [] and env.boards == [] and rows(env) == []


def test_no_prefer_dry_run_also_exit4(env, capsys):
    assert td.main(["t1", "--dry-run"]) == 4
    assert "建議:" in capsys.readouterr().out
    assert env.packs == [] and env.launched == [] and env.boards == [] and rows(env) == []


# ---------- --prefer ----------

def test_prefer_kaggle_unavailable_errors(env, capsys):
    env.quota = None
    assert td.main(["t1", "--prefer", "kaggle"]) == 1
    assert "不改走別的" in capsys.readouterr().out
    assert env.launched == [] and env.packs == [] and env.boards == []


def test_prefer_kaggle_no_token_errors(env):
    env.tok.unlink()
    assert td.main(["t1", "--prefer", "kaggle"]) == 1


def test_prefer_kaggle_works_even_if_colab_free(env):
    assert td.main(["t1", "--prefer", "kaggle"]) == 0
    assert env.launched == [("t1", False)] and env.packs == []


def test_prefer_colab_ignores_deadline_but_not_occupancy(env):
    env.publish = datetime.now() + timedelta(hours=2)
    assert td.main(["t1", "--prefer", "colab"]) == 0
    assert td.main(["t2", "--prefer", "colab"]) == 1   # t1 占著


def test_prefer_local(env, capsys):
    assert td.main(["t1", "--prefer", "local"]) == 0
    out = capsys.readouterr().out
    assert "make_version.py --tag t1" in out and "--tts-review --freeze" in out
    assert rows(env) == []   # 本機不寫帳本
    assert env.boards and "本機" in env.boards[0][1]


# ---------- 執行動作 ----------

def test_dispatch_kaggle_background_and_foreground(env, capsys):
    assert td.main(["t1", "--prefer", "kaggle"]) == 0
    assert env.launched == [("t1", False)]
    assert "run.log" in capsys.readouterr().out
    assert env.boards[0][1].startswith("C配音:Kaggle")
    assert td.main(["t2", "--foreground", "--prefer", "kaggle"]) == 0
    assert env.launched[-1] == ("t2", True)


def test_dispatch_colab_packs_ledger_and_message(env, capsys):
    assert td.main(["t1", "--prefer", "colab"]) == 0
    out = capsys.readouterr().out
    assert env.packs == ["t1"]
    assert "colab_t1.zip" in out and "CV_colab" in out and "全部執行" in out and "tts_t1.zip" in out
    assert "已由主對話上傳" in out and "一定要你按" in out
    assert "--colab-cancel t1" in out and "--prefer kaggle|local" in out and "60" in out and "6 小時" in out
    assert "自動改" not in out and "--skip" not in out
    r = rows(env)
    assert len(r) == 1 and r[0]["event"] == "start" and r[0]["backend"] == "colab" and r[0]["tag"] == "t1"
    assert env.boards[0][1].startswith("C配音:Colab")


def test_dispatch_colab_pack_blocked_no_ledger(env):
    env.pack_rc = 2
    assert td.main(["t1", "--prefer", "colab"]) == 2
    assert rows(env) == [] and env.boards == []


def test_dry_run_with_prefer_writes_nothing(env, capsys):
    assert td.main(["t1", "--prefer", "colab", "--dry-run"]) == 0
    assert "選擇:colab" in capsys.readouterr().out
    assert env.packs == [] and env.launched == [] and env.boards == [] and rows(env) == []


def test_same_tag_already_running_refused(env, capsys):
    r0 = start("t1", "kaggle", datetime.now().isoformat())
    ledger(env, r0)
    assert td.main(["t1", "--prefer", "kaggle"]) == 1
    assert "已在 Kaggle 跑" in capsys.readouterr().out
    assert env.launched == [] and env.packs == [] and rows(env) == [r0]


# ---------- colab-done / cancel ----------

def test_colab_done_writes_end(env):
    ledger(env, start("t1", "colab", "2026-10-28T10:00:00"))
    assert td.main(["--colab-done", "t1", "x.zip"]) == 0
    assert env.imports == ["x.zip"]
    r = rows(env)
    assert r[-1]["event"] == "end" and r[-1]["backend"] == "colab" and r[-1]["rc"] == 0
    assert td.open_jobs(td.read_ledger(), "colab") == {}


def test_colab_done_import_failure_keeps_open(env):
    ledger(env, start("t1", "colab"))
    env.import_rc = 1
    assert td.main(["--colab-done", "t1", "x.zip"]) == 1
    assert "t1" in td.open_jobs(td.read_ledger(), "colab")


def test_colab_cancel(env):
    ledger(env, start("t1", "colab"))
    assert td.main(["--colab-cancel", "t1"]) == 0
    assert rows(env)[-1]["rc"] == "cancelled"
    assert td.open_jobs(td.read_ledger(), "colab") == {}


# ---------- 帳本統計與 status ----------

def test_weekly_used(env):
    ledger(env,
           end("a", "kaggle", end="2026-10-27T10:00:00", gpu_hours=1.5),
           end("b", "kaggle", end="2026-10-01T10:00:00", gpu_hours=9),          # 超過 7 天
           end("c", "colab", start="2026-10-28T08:00:00", end="2026-10-28T10:00:00"))
    r = td.read_ledger()
    assert td.weekly_used(r, "kaggle", NOW) == pytest.approx(1.5)
    assert td.weekly_used(r, "colab", NOW) == pytest.approx(2.0)


def test_status_output(env, capsys, monkeypatch):
    monkeypatch.setattr(td, "gpu_lock_first_line", lambda: "GPU 閒置")
    recent = datetime.now().isoformat()
    ledger(env, start("a", "kaggle", recent), start("b", "colab", recent), end("z", "kaggle", end=datetime.now().isoformat(), gpu_hours=2))
    assert td.main(["--status"]) == 0
    out = capsys.readouterr().out
    assert "剩餘 GPU 小時:20" in out and "kaggle 進行中:a" in out and "colab 進行中:b" in out
    assert out.index("colab 進行中") < out.index("kaggle 進行中") < out.index("剩餘 GPU")
    assert "kaggle 2.00h" in out and out.index("colab 0.00h") < out.index("kaggle 2.00h") and "GPU 閒置" in out


def test_refreeze_ok_flag_sets_env(env, monkeypatch):
    monkeypatch.delenv("CV_REFREEZE_OK", raising=False)
    td.main(["t1", "--dry-run", "--refreeze-ok"])
    assert os.environ.get("CV_REFREEZE_OK") == "1"
    monkeypatch.delenv("CV_REFREEZE_OK", raising=False)


# ---------- Kaggle 並行已滿排隊(P6) ----------

def _fake_ledger_sequence(monkeypatch, full_times):
    """前 full_times 次 read_ledger 回 Kaggle 有一支在跑,之後回空。"""
    calls = {"n": 0}

    def fake():
        calls["n"] += 1
        return [start("other", "kaggle", datetime.now().isoformat(timespec="seconds"))] if calls["n"] <= full_times else []
    monkeypatch.setattr(td, "read_ledger", fake)
    return calls


def test_prefer_kaggle_full_waits_then_dispatches(env, monkeypatch, capsys):
    _fake_ledger_sequence(monkeypatch, 2)
    sleeps = []
    assert td.dispatch("t1", "kaggle", sleep=sleeps.append) == 0
    assert sleeps == [td.KAGGLE_POLL_S] * 2
    assert env.launched == [("t1", False)]
    out = capsys.readouterr().out
    assert out.count("排隊中") == 2 and "已等 0 分鐘" in out and "已等 1 分鐘" in out and "1/1" in out


def test_prefer_kaggle_full_forever_times_out_with_original_error(env, monkeypatch, capsys):
    ledger(env, start("other", "kaggle", datetime.now().isoformat(timespec="seconds")))
    monkeypatch.setattr(td, "KAGGLE_WAIT_MAX", 300)
    sleeps = []
    assert td.dispatch("t1", "kaggle", sleep=sleeps.append) == 1
    assert len(sleeps) == 5 and env.launched == [] and env.boards == []
    out = capsys.readouterr().out
    assert "Kaggle 並行已滿" in out and "不改走別的" in out and "不再等" in out


def test_dry_run_kaggle_full_does_not_wait(env, monkeypatch):
    ledger(env, start("other", "kaggle", datetime.now().isoformat(timespec="seconds")))
    sleeps = []
    assert td.dispatch("t1", "kaggle", dry_run=True, sleep=sleeps.append) == 1
    assert sleeps == []


def test_prefer_kaggle_other_failure_does_not_wait(env):
    env.quota = None
    sleeps = []
    assert td.dispatch("t1", "kaggle", sleep=sleeps.append) == 1
    assert sleeps == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
