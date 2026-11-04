r"""make_version.log_warn:非核心步驟失敗記進 production.json 的 warns,不中止、寫檔失敗也不拋。
tts_env_chattts\Scripts\python.exe -X utf8 -m pytest pipeline/tests/test_make_version_warns.py -q"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import make_version as MV  # noqa: E402
import paths  # noqa: E402


def test_log_warn_appends_to_production_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(paths, "PROJECTS", tmp_path)
    MV.log_warn("t1", "C22 優先聽", "寫檔失敗")
    MV.log_warn("t1", "C24 聽審頁", "又一個")
    d = json.loads((tmp_path / "t1" / "production.json").read_text(encoding="utf-8"))
    assert [(w["step"], w["msg"]) for w in d["warns"]] == [("C22 優先聽", "寫檔失敗"), ("C24 聽審頁", "又一個")]
    assert all(w["at"] for w in d["warns"]) and "警告:C22 優先聽" in capsys.readouterr().out


def test_log_warn_never_raises(monkeypatch, capsys):
    import director
    monkeypatch.setattr(director, "_append", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    MV.log_warn("t1", "E13 進度板", "x")
    assert "未寫入 production.json" in capsys.readouterr().out


def test_listen_failures_do_not_abort_source():
    """C22/C24/C21/C23/D26 的失敗分支都走 log_warn 且不設 rc=1(原始碼層檢查,避免回退成中止)。"""
    src = (Path(__file__).resolve().parents[1] / "make_version.py").read_text(encoding="utf-8")
    for step in ("C21 E4耳朵", "C22 優先聽", "C23 唸法清單", "C24 聽審頁", "D26 優先看"):
        assert f'log_warn(tag, "{step}"' in src, step
    i = src.index('elif st.fn == "listen_txt"')
    assert "rc, tail = 1" not in src[i:src.index('elif st.fn == "decide_list"')]
    j = src.index('elif st.fn == "listen":')
    assert "rc, tail = 1" not in src[j:src.index("else:", j)]


# ---- C0 進步驟表 ----
def _c0_env(monkeypatch, tmp_path, frozen=False):
    import freeze as FZ
    proj, repo = tmp_path / "projects", tmp_path / "repo"
    (proj / "t1").mkdir(parents=True)
    (repo / "t1").mkdir(parents=True)
    monkeypatch.setattr(paths, "PROJECTS", proj)
    monkeypatch.setattr(paths, "REPO", repo)
    fz = proj / "t1" / "freeze.json"
    monkeypatch.setattr(FZ, "freeze_path", lambda tag: fz)
    if frozen:
        fz.write_text("{}", encoding="utf-8")
    scr = repo / "t1" / "script.txt"
    scr.write_text("x", encoding="utf-8")
    return proj / "t1" / "c0_report.json", scr


def test_c0_needed_missing_old_fresh_frozen(monkeypatch, tmp_path):
    import os
    rep, scr = _c0_env(monkeypatch, tmp_path)
    assert MV.c0_needed("t1") == (True, "沒有 c0_report.json")
    rep.write_text("{}", encoding="utf-8")
    os.utime(rep, (1, 1))   # 報告比稿舊
    assert MV.c0_needed("t1") == (True, "c0_report.json 比 script.txt 舊")
    os.utime(rep, (scr.stat().st_mtime + 10,) * 2)   # 匯回後有較新報告:不重跑
    assert MV.c0_needed("t1") == (False, "已有報告")


def test_c0_needed_frozen_skips(monkeypatch, tmp_path):
    _c0_env(monkeypatch, tmp_path, frozen=True)
    assert MV.c0_needed("t1") == (False, "已凍結")


def test_c0_step_registered_for_tts_review_only():
    src = (Path(__file__).resolve().parents[1] / "make_version.py").read_text(encoding="utf-8")
    assert '"C0試配"' in src and "--skip-c0" in src and "sys.exit(3)" in src
    assert "三項文案檢查" not in src and "文案檢查六項" in src
