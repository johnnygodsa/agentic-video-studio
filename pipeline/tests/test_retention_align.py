"""retention_align.py 測試:真實 repo 檔(gow_sales / re9_leon / wow_forever)+ latest.json 形狀 fixture。輸出寫 tmp(monkeypatch paths.build_dir)。
PYTHONPATH=<repo> python3 -X utf8 -m pytest pipeline/tests/test_retention_align.py -q -p no:cacheprovider -s"""
import json
import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parent.parent
REPO = PIPE.parent
sys.path.insert(0, str(PIPE))
import paths as P  # noqa: E402
import retention_align as RA  # noqa: E402

CURVE = REPO / "channel" / "research_文案優化_2026-10-20" / "70_留存曲線.json"
FIX = Path(__file__).resolve().parent / "fixtures" / "retention"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "build_dir", lambda tag: tmp_path / "build" / tag)
    monkeypatch.setattr(P, "ROOT", REPO)
    return tmp_path


def _run(tag, env, capsys):
    rc = RA.main(["--tag", tag, "--curve", str(CURVE), "--timeline", str(REPO / "keep" / tag / "timeline.json"), "--json"])
    assert rc == 0
    res = json.loads(capsys.readouterr().out)
    assert (env / "build" / tag / "retention_align.json").is_file()
    return res


def _drop(res, a, b):
    return next(d for d in res["drops"] if round(d["pos_from"]) == a and round(d["pos_to"]) == b)


def _idx(d):
    return [l["idx"] for l in d["lines"]]


def test_gow_sales(env, capsys):
    r = _run("gow_sales", env, capsys)
    print("gow_sales", r["intro_drop"], r["retention_30s_pct"], r["hook_type"])
    assert len(r["drops"]) == 5 and r["video_id"] == "q1efIsqq7WI"
    d01, d67 = _drop(r, 0, 1), _drop(r, 6, 7)
    assert d01["drop"] == pytest.approx(2.3, abs=0.3)
    assert d67["drop"] == pytest.approx(2.5, abs=0.3)
    assert 4 in _idx(d67)
    assert "事變日" in "".join(l["text"] for l in d67["lines"])
    assert r["hook_type"] == "反差"
    assert all(d["pos_to"] <= 95 for d in r["drops"])


def test_re9_leon(env, capsys):
    r = _run("re9_leon", env, capsys)
    print("re9_leon", r["intro_drop"], r["retention_30s_pct"], r["hook_type"])
    d = _drop(r, 0, 1)
    assert d["drop"] == pytest.approx(3.8, abs=0.3)
    assert 1 in _idx(d)


def test_wow_forever(env, capsys):
    r = _run("wow_forever", env, capsys)
    print("wow_forever", r["intro_drop"], r["retention_30s_pct"], r["hook_type"])
    assert _drop(r, 0, 1)["drop"] == pytest.approx(7.8, abs=0.3)
    d45 = _drop(r, 4, 5)
    assert d45["drop"] == pytest.approx(6.3, abs=0.3)
    assert {8, 9, 10} <= set(_idx(d45))
    assert r["hook_type"] == "事件宣告"


def test_markdown_output(env, capsys):
    assert RA.main(["--tag", "gow_sales", "--curve", str(CURVE), "--timeline", str(REPO / "keep/gow_sales/timeline.json")]) == 0
    out = capsys.readouterr().out
    assert "位置 0→1%" in out and "句4" in out


def test_latest_json_shape(env, capsys):
    rc = RA.main(["--tag", "fix_tag", "--curve", str(FIX / "latest.json"), "--timeline", str(FIX / "timeline.json"), "--json"])
    assert rc == 0
    r = json.loads(capsys.readouterr().out)
    assert r["video_id"] == "FIXVID00001" and r["total_s"] == 100.0
    assert r["intro_drop"] == pytest.approx(6.5, abs=0.01)
    assert r["retention_30s_pct"] == pytest.approx(85.0, abs=0.01)   # 30 秒 = 位置 30%
    assert r["retention_50_pct"] == pytest.approx(75.0, abs=0.01)
    d0 = r["drops"][0]
    assert (d0["pos_from"], d0["pos_to"]) == (0.0, 1.0) and _idx(d0) == [1]
    assert d0["vs_typical"] == "低於"                                 # 93.5 < 典型下緣 97.5
    assert any(round(d["pos_from"]) == 9 for d in r["drops"])         # 9→10 的 4.5 點跌幅
    # 以 --video-id 選片
    rc = RA.main(["--tag", "zzz", "--video-id", "FIXVID00001", "--curve", str(FIX / "latest.json"),
                  "--timeline", str(FIX / "timeline.json"), "--json"])
    assert rc == 0
    capsys.readouterr()


def test_missing_curve_returns_error(env, capsys, monkeypatch):
    monkeypatch.setattr(P, "ytad_export_latest", lambda: env / "nope.json")
    rc = RA.main(["--tag", "gow_sales", "--timeline", str(REPO / "keep/gow_sales/timeline.json")])
    assert rc == 3
    capsys.readouterr()


def test_all_runs(env, capsys):
    assert RA.main(["--all", "--curve", str(CURVE)]) == 0
    out = capsys.readouterr().out
    for t in ("gow_sales", "re9_leon", "wow_forever"):
        assert t in out
    assert "開場型態" in out
