"""taste_run runner 本身的測試 + 口味補洞(T14 played、T27 別名閘門)的整合測試。
tts_env_chattts\\Scripts\\python.exe -X utf8 -m pytest pipeline/tests/test_taste_run.py -q(不需顯示卡,不連網)"""
import json
import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
import freeze as FZ  # noqa: E402
import paths as P  # noqa: E402
import script_lint as L  # noqa: E402
import taste_run as R  # noqa: E402


def test_all_46_cases_registered_with_valid_status():
    assert sorted(R.CASES) == [f"T{i:02d}" for i in range(1, 47)]
    assert set(R.STATUSES) == {"pass", "fail", "llm", "audio", "gap"}


def test_full_run_has_no_fail_and_gap_is_not_pass(capsys):
    assert R.main(["--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["results"]) == 46 and sum(out["count"].values()) == 46
    assert out["count"]["fail"] == 0
    by = {r["id"]: r["status"] for r in out["results"]}
    assert by["T25"] == "gap" and by["T03"] == "llm"          # gap/llm 不會被算成 pass
    assert out["count"]["pass"] == sum(1 for s in by.values() if s == "pass")
    assert not R.TMP.exists()                                  # 假片目錄用完刪掉


def test_single_case_and_unknown_case(capsys):
    assert R.main(["--case", "t02"]) == 0
    assert "T02 pass" in capsys.readouterr().out
    assert R.main(["--case", "T99"]) == 2


def test_fail_gives_exit_1_and_exception_becomes_fail(monkeypatch, capsys):
    monkeypatch.setitem(R.CASES, "T02", dict(title="x", fn=lambda: R.judge(("壞例沒抓到", False)), audio=None))
    assert R.main(["--case", "T02"]) == 1
    assert "不成立:壞例沒抓到" in capsys.readouterr().out

    def boom():
        raise ValueError("炸了")
    monkeypatch.setitem(R.CASES, "T02", dict(title="x", fn=boom, audio=None))
    r = R.run_case("T02")
    assert r["status"] == "fail" and "ValueError" in r["note"]
    monkeypatch.setitem(R.CASES, "T02", dict(title="x", fn=lambda: R.gap("還沒有"), audio=None))
    assert R.main(["--case", "T02"]) == 0 and R.run_case("T02")["status"] == "gap"   # gap 不擋也不算 pass


def test_audio_layer_only_runs_with_flag(monkeypatch):
    called = []
    monkeypatch.setattr(R, "run_audio", lambda c: called.append(1) or (True, "exit 0"))
    monkeypatch.setitem(R.CASES, "T02", dict(title="x", fn=lambda: ("pass", ""), audio=["x.py"]))
    assert "未跑" in R.run_case("T02")["note"] and not called
    assert "音檔層 OK" in R.run_case("T02", audio=True)["note"] and called
    monkeypatch.setattr(R, "run_audio", lambda c: (False, "exit 1"))
    assert R.run_case("T02", audio=True)["status"] == "fail"


def test_rm_only_deletes_direct_children_of_tmp_taste(tmp_path):
    for bad in (P.TMP, P.REPO, P.TMP / "taste" / "T01" / "sub", tmp_path):
        with pytest.raises(RuntimeError):
            R._rm(bad)
    d = R.workdir("T_unit")
    (d / "f.txt").write_text("x", encoding="utf-8")
    assert d.parent == R.TMP and d.is_dir()
    R.cleanup()
    assert not d.exists()
    R._made.clear()


def test_scan_recent_returns_counts():
    rows = R.scan_recent(2)
    assert len(rows) == 2 and all({"tag", "OPEN_LOAD", "PRONOUN_FIRST", "PRICE_TWD", "DISCLAIMER", "PLAYED_CLAIM"} <= set(r) for r in rows)


# ---- 口味補洞 ----
def test_pbz_review_v1_v2_opening():
    v1, _ = R.fixture_lines("pbz_review_v1.txt")
    v2, _ = R.fixture_lines("pbz_review_v2.txt")
    assert L.opening_load(v1) and not L.opening_load(v2)


def test_played_claim_variants_and_handoff(tmp_path):
    (tmp_path / "handoff.md").write_text("使用者沒有玩過。", encoding="utf-8")
    assert L.not_played(str(tmp_path))
    (tmp_path / "brief.json").write_text(json.dumps({"played": False}), encoding="utf-8")
    (tmp_path / "handoff.md").write_text("沒提", encoding="utf-8")
    assert L.not_played(str(tmp_path))                       # brief.json played=false 也算
    assert L.played_claims([(1, "我玩了 12 小時。")], False) and not L.played_claims([(1, "我看了預告。")], False)


def test_price_exempt_big_amounts_and_twd():
    assert L.price_twd_missing([(1, "標準版 59.99 美金。")])
    assert not L.price_twd_missing([(1, "整筆交易 550 億美金。")])
    assert not L.price_twd_missing([(1, "標準版 59.99 美金,台幣 1,990。")])


# ---- T27:freeze 別名閘門整合 ----
@pytest.fixture
def fz_env(tmp_path, monkeypatch):
    sp = tmp_path / "script.txt"
    sp.write_text("@title t\n# a\nimg:a|EA 宣布關閉工作室。\n", encoding="utf-8")
    monkeypatch.setattr(FZ, "script_path", lambda tag: sp)
    monkeypatch.setattr(FZ, "freeze_path", lambda tag: tmp_path / "freeze.json")
    monkeypatch.setattr(FZ, "review_path", lambda tag: tmp_path / "tts_review.json")
    monkeypatch.setattr(P, "tts_dir", lambda tag, engine=None: tmp_path / "tts")
    monkeypatch.setattr(P, "build_dir", lambda tag: tmp_path)
    rv = dict(script_sha256=FZ.sha256(sp), narration_sha=FZ.narration_sha("t"), at="2026-10-31T00:00:00", failed=[], no_qc=[], timing_errors=[],
              tts_keys_sha=FZ.tts_keys_sha("t", "cosy3"), engine="cosy3")
    (tmp_path / "tts_review.json").write_text(json.dumps(rv), encoding="utf-8")
    return tmp_path


def test_freeze_blocks_new_alias_used_in_script(fz_env, monkeypatch):
    monkeypatch.setattr(FZ, "alias_table", lambda *a, **k: {"EA": ["藝電", "易電"]})
    monkeypatch.setattr(FZ, "alias_base", lambda tag: {"EA": ["藝電"]})
    with pytest.raises(FZ.FreezeRefused) as e:
        FZ.freeze("t", "聽審通過")
    assert any("易電" in x for x in e.value.args[0])
    assert not (fz_env / "freeze.json").exists()
    rec = FZ.freeze("t", "聽審通過", alias_ok="新廠商音譯一次登錄")
    assert rec["alias_ok"] == "新廠商音譯一次登錄" and rec["asr_alias"] == {"EA": ["藝電", "易電"]}
    assert json.loads((fz_env / "freeze.json").read_text(encoding="utf-8"))["alias_ok"]


def test_freeze_passes_when_no_new_alias_or_unrelated(fz_env, monkeypatch):
    monkeypatch.setattr(FZ, "alias_table", lambda *a, **k: {"EA": ["藝電"], "Kotaku": ["口他口"]})
    monkeypatch.setattr(FZ, "alias_base", lambda tag: {"EA": ["藝電"]})
    assert "alias_ok" not in FZ.freeze("t", "聽審通過")      # 新增的 Kotaku 本片沒用到 -> 放行


def test_alias_base_prefers_snapshot(monkeypatch):
    monkeypatch.setattr(FZ, "load", lambda tag: {"asr_alias": {"EA": ["藝電"]}})
    assert FZ.alias_base("t") == {"EA": ["藝電"]}
    assert FZ.alias_added({"EA": ["藝電", "易電"], "X": ["y"]}, {"EA": ["藝電"]}) == {"EA": ["易電"], "X": ["y"]}
