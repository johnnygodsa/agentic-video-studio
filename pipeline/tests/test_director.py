"""director 骨架測試:python -X utf8 -m pytest pipeline/tests/test_director.py -q
假造產物放 repo tmp/ 下暫存目錄(paths 各根目錄與 CV_BOARD_DIR 以 monkeypatch 指過去)。真片(ea_me5、bioware_dei)只跑 status 不報錯。"""
import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director as D  # noqa: E402
import paths  # noqa: E402

TAG = "demo"


def _w(p, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    root = base / f"test_director_{uuid.uuid4().hex[:8]}"
    root.mkdir()
    for attr, sub in (("PROJECTS", "projects"), ("BUILD", "build"), ("OUTPUT", "output"), ("TMP", "tmp")):
        monkeypatch.setattr(paths, attr, root / sub)
    monkeypatch.setattr(paths, "REPO", root / "repo")
    monkeypatch.setattr(paths, "ROOT", root)
    monkeypatch.setenv("CV_BOARD_DIR", str(root / "channel"))
    (root / "channel").mkdir()
    (root / "repo" / TAG).mkdir(parents=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _board(root, **rec):
    (root / "channel" / "board.json").write_text(json.dumps({TAG: rec}, ensure_ascii=False), encoding="utf-8")


def _states(res):
    return {k: g["state"] for k, g in res["gates"].items()}


def test_empty(env):
    res = D.collect(TAG)
    assert res["stage"] == "0選題"
    assert set(_states(res).values()) == {D.NONE}


def test_stage_a_pending_facts(env):
    pd = env / "projects" / TAG
    _w(pd / "context.md")
    _w(pd / "clips_demo.json", "[]")
    _w(pd / "facts.md", "狀態:一手 / 待查 = 圖例\n| # | 主張 | 狀態 |\n|---|---|---|\n| F1 | a | 一手 |\n| F2 | b | 待查 |\n")
    res = D.collect(TAG)
    assert res["states"]["A"] == D.PART and res["stage"] == "A資料"
    assert D.count_pending_facts(pd / "facts.md") == 1
    miss = [i["note"] for i in res["gates"]["A"]["items"] if not i["ok"]]
    assert miss and "待查 1" in miss[0]
    _w(pd / "facts.md", "| # | 狀態 |\n|---|---|\n| F1 | 一手 |\n")
    assert D.collect(TAG)["states"]["A"] == D.DONE


def test_stage_b_b4_c(env):
    pd, bd = env / "projects" / TAG, env / "build" / TAG
    _w(env / "repo" / TAG / "script.txt")
    _w(pd / "visual_table.md")
    _w(pd / "player_review_r1.md")
    res = D.collect(TAG)
    assert res["states"]["B"] == D.DONE and res["stage"] == "B文案"
    _w(bd / "tts_script.md")
    _w(pd / "pron_review.md")
    assert D.collect(TAG)["states"]["B4"] == D.DONE
    # C:品管未過 > 0 不算完成
    _w(pd / "c0_report.md")
    _w(pd / "c0_report.json", json.dumps({"wrong": 0}))
    _w(bd / "tts_review.json", json.dumps({"failed": [3], "timing_errors": []}))
    _w(pd / "freeze.json", "{}")
    res = D.collect(TAG)
    assert res["states"]["C"] == D.PART and res["stage"] == "C配音"
    _w(bd / "tts_review.json", json.dumps({"failed": [], "timing_errors": []}))
    _w(env / "output" / TAG / "listen_v1.txt")
    res = D.collect(TAG)
    assert res["states"]["C"] == D.DONE and res["stage"] == "已凍結"
    # C0 唸錯 > 0
    _w(pd / "c0_report.json", json.dumps({"wrong": 2}))
    assert D.collect(TAG)["states"]["C"] == D.PART


def test_stage_d_e(env):
    out = env / "output" / TAG
    _w(out / "demo_v1.mp4")
    _w(out / "demo_v2.mp4")
    _w(out / "demo_v2_720p.mp4")
    _w(out / "look_v2.md")
    res = D.collect(TAG)
    assert res["states"]["D"] == D.DONE and res["stage"] == "D畫面"
    assert [v["ver"] for v in res["versions"]] == ["v1", "v2"] and res["artifacts"]["mp4"].endswith("demo_v2.mp4")
    _w(out / "v2_說明.md")
    _w(env / "projects" / TAG / "handoff.md", "上傳完成:video_id `VIDEO000002`,未排程")
    _board(env, stage="E自審", channel="ChannelA")
    res = D.collect(TAG)
    assert res["artifacts"]["video_id"] == "VIDEO000002" and res["channel"] == "ChannelA"
    assert res["states"]["E"] == D.PART and res["stage"] == "E自審"
    _board(env, stage="已排程")
    res = D.collect(TAG)
    assert res["states"]["E"] == D.DONE and res["stage"] == "已排程"
    _board(env, stage="結案")
    assert D.collect(TAG)["stage"] == "結案"


def test_stage0_channel_filter(env):
    _w(env / "tmp" / "scout_ChannelA_x.md")
    _w(env / "tmp" / "critic_ChannelB_x.md")
    assert D.collect(TAG, "ChannelA")["states"]["0"] == D.PART
    assert D.collect(TAG, "")["states"]["0"] == D.DONE


def test_init_idempotent(env):
    d1, new1 = D.init(TAG, "ChannelA")
    D.log_call(TAG, "x", "m", 1, 1)
    d2, new2 = D.init(TAG, "ChannelB")
    assert new1 and not new2
    assert d2["channel"] == "ChannelA" and len(d2["llm_calls"]) == 1
    assert set(d1) >= {"tag", "channel", "created", "stage", "gates", "llm_calls", "interventions", "feedback", "artifacts", "versions"}


def test_log_intervene_feedback_append(env):
    r = D.log_call(TAG, "scout", "sonnet", 100, 10, 1000)
    assert r["cost_eq"] == 100 + 50 + 100
    D.log_call(TAG, "critic", "opus", 1, 1, cost=9.0)
    D.intervene(TAG, "改封面")
    D.feedback(TAG, "開場太長", "T12")
    D.feedback(TAG, "ok")
    d = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))
    assert [c["fn"] for c in d["llm_calls"]] == ["scout", "critic"] and d["llm_calls"][1]["cost_eq"] == 9.0
    assert d["interventions"][0]["who"] == "user" and d["interventions"][0]["resolved"] is False
    assert [f["taste_case"] for f in d["feedback"]] == ["T12", None]


def test_write_preserves_history(env):
    D.log_call(TAG, "x", "m", 1, 1)
    D.intervene(TAG, "a")
    D.feedback(TAG, "b")
    data = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))
    data["gates"] = {"A": {"attempts": 2}}
    D.prod_path(TAG).write_text(json.dumps(data), encoding="utf-8")
    _w(env / "projects" / TAG / "context.md")
    D.main(["status", TAG, "--write"])
    d = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))
    assert len(d["llm_calls"]) == len(d["interventions"]) == len(d["feedback"]) == 1
    assert d["gates"]["A"]["attempts"] == 2 and d["gates"]["A"]["state"] == D.PART and d["stage"] == "A資料"


def test_cli_table_and_json(env, capsys):
    _w(env / "projects" / TAG / "context.md")
    assert D.main(["status", TAG]) == 0
    out = capsys.readouterr().out
    assert "段 | 推斷狀態 | 依據檔 | 缺什麼" in out and "A 資料 | 進行中" in out
    D.main(["status", TAG, "--json"])
    assert json.loads(capsys.readouterr().out)["gates"]["A"]["state"] == D.PART


@pytest.mark.parametrize("tag", ["ea_me5", "bioware_dei"])
def test_real_projects_no_error(tag, capsys):
    if not (paths.PROJECTS / tag).exists():
        pytest.skip("無此專案")
    before = D.prod_path(tag).exists()
    assert D.main(["status", tag]) == 0
    print(capsys.readouterr().out)
    assert D.prod_path(tag).exists() == before  # status 不加 --write 不產檔
