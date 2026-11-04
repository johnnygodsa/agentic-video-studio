"""Colab 打包與匯回(channel/_archive/plans/PLAN_COLAB配音_2026-10-28.md T1)測試:假根、假 tag、假快取;不載模型、不需顯示卡、檢查腳本全 mock。
python -X utf8 -m pytest pipeline/tests/test_colab_pack.py -q"""
import contextlib
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
sys.path.insert(0, str(PIPE / "colab"))
import build as B  # noqa: E402
import freeze as FZ  # noqa: E402
import pack_for_colab as PK  # noqa: E402
import paths as P  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import tts_key as TK  # noqa: E402

TAG = "片X"
SAY = "這款遊戲的主角很帥。"
CMD = ["py", "tts_cosy3.py", "--ref", "ref_b.wav", "--speed", "1.18"]


def mk_root(base, name):
    """建一個假的 repo=素材根,並把 paths 指過去;回傳根目錄。"""
    root = base / name
    (root / "pipeline" / "tests").mkdir(parents=True)
    (root / "pipeline" / "__pycache__").mkdir()
    (root / "pipeline" / "tts_bakeoff").mkdir()
    (root / "pipeline" / "tools").mkdir()
    (root / "pipeline" / "colab").mkdir()
    for rel in ("a.py", "tests/t.py", "__pycache__/a.pyc", "tts_bakeoff/b.py", "tools/sync_kc_x.py", "tools/keep.py",
                "colab/pack_for_colab.py"):
        (root / "pipeline" / rel).write_text("x", encoding="utf-8")
    for tag in (TAG, "別片"):
        (root / tag).mkdir()
        (root / tag / "script.txt").write_text("文案", encoding="utf-8")
        (root / tag / "script.json").write_text("{}", encoding="utf-8")
        (root / "build" / tag / "tts_cosy3").mkdir(parents=True)
        (root / "build" / tag / "tts_cosy3" / "001.wav").write_bytes(b"w")
    (root / "cosy_voice").mkdir()
    (root / "cosy_voice" / "ref_b.wav").write_bytes(b"r")
    (root / "cosy_voice" / "ref_b.txt").write_text("稿", encoding="utf-8")
    for d in ("tts_env_chattts", "tts_models", "raw", "images", "bgm"):
        (root / d).mkdir()
        (root / d / "big.bin").write_bytes(b"z")
    (root / "channel").mkdir()
    (root / "channel" / "board.json").write_text("{}", encoding="utf-8")
    (root / "projects" / TAG).mkdir(parents=True)
    return root


@pytest.fixture
def fake(tmp_path, monkeypatch):
    root = mk_root(tmp_path, "root")
    use_root(monkeypatch, root)
    monkeypatch.setattr(PK, "run_gates", lambda tag, prefix: [])
    return root


def use_root(monkeypatch, root):
    for k, v in dict(REPO=root, ROOT=root, PROJECTS=root / "projects", BUILD=root / "build", TMP=root / "tmp",
                     COSY_REF=root / "cosy_voice" / "ref_b.wav").items():
        monkeypatch.setattr(P, k, v)


def put_unit(d, stem, passed, say=SAY, wav=b"wav", qc=True, extra=None):
    """寫一組假配音單位:wav + .key + .qc.json(passed True/False)。"""
    d.mkdir(parents=True, exist_ok=True)
    key = TK.full_key(TK.audio_key("cosy3", TK.cmd_sig(CMD), "V", "R", say), B.QC_VER)
    (d / f"{stem}.wav").write_bytes(wav)
    (d / f"{stem}.key").write_text(key)
    if qc:
        rec = dict(qc_ver=B.QC_VER, key=key, text=say, passed=passed, engine="cosy3", marker=wav.decode("latin1"))
        (d / f"{stem}.qc.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    for n, c in (extra or {}).items():
        (d / n).write_bytes(c)


def names(zp):
    return set(zipfile.ZipFile(zp).namelist())


# ---- ① 凍結拒打包 ----

def test_frozen_tag_refused(fake, capsys):
    (fake / "projects" / TAG / "freeze.json").write_text("{}", encoding="utf-8")
    rc, out = PK.pack(TAG)
    assert rc == 2 and out is None
    assert "已凍結" in capsys.readouterr().out
    assert not (fake / "tmp" / "colab").exists()


def test_frozen_tag_refused_cli(tmp_path):
    root = mk_root(tmp_path, "cliroot")
    (root / "projects" / TAG / "freeze.json").write_text("{}", encoding="utf-8")
    env = dict(os.environ, CLAUDE_VIDEO_ROOT=str(root), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "colab" / "pack_for_colab.py"), TAG],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 2 and "已凍結" in r.stdout
    h = subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "colab" / "pack_for_colab.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    assert h.returncode == 0 and "--import" in h.stdout


def test_gate_problem_refused(fake, monkeypatch, capsys):
    monkeypatch.setattr(PK, "run_gates", lambda tag, prefix: ["script_lint 失敗(結束碼 1):超標 3 項"])
    rc, out = PK.pack(TAG)
    assert rc == 2 and out is None and "script_lint" in capsys.readouterr().out
    assert not (fake / "tmp" / "colab").exists()


def test_gate_cmds_same_as_make_version(fake):
    cmds = dict(PK.gate_cmds(TAG, "x_"))
    assert list(cmds) == ["txt2json", "script_lint", "tts_terms"]
    assert cmds["tts_terms"][-3:] == [TAG, "--engine", "cosy3"] and cmds["script_lint"][-1] == TAG


# ---- ② zip 內容規則 ----

def test_zip_contents(fake):
    put_unit(fake / "build" / TAG / "tts_cosy3", "002", True, extra={"002.trim.wav": b"t"})
    put_unit(fake / "build" / TAG / "tts_cosy3" / "sub", "003_1", True)
    base = fake / "build" / TAG / "tts_cosy3"
    (base / "_cosy_work").mkdir()
    (base / "_cosy_work" / "tmp.wav").write_bytes(b"j")
    (base / "_jobs.json").write_text("[]")
    (base / "_cosy3_worker.log").write_text("log")
    (base / "_qc_base_cosy3.json").write_text("{}")
    rc, out = PK.pack(TAG)
    assert rc == 0 and out == fake / "tmp" / "colab" / f"colab_{TAG}.zip"
    ns = names(out)
    assert {"pipeline/a.py", "pipeline/tools/keep.py", f"{TAG}/script.txt", f"{TAG}/script.json", "cosy_voice/ref_b.wav",
            "cosy_voice/ref_b.txt", ".video_root", f"build/{TAG}/tts_cosy3/001.wav", f"build/{TAG}/tts_cosy3/002.trim.wav",
            f"build/{TAG}/tts_cosy3/sub/003_1.qc.json", f"build/{TAG}/tts_cosy3/_qc_base_cosy3.json"} <= ns
    assert not [n for n in ns if n.startswith(("pipeline/tests/", "pipeline/tts_bakeoff/")) or "__pycache__" in n
                or "sync_kc" in n]
    assert not [n for n in ns if not n.startswith("tts_models/hub/pengzhendong/wetext/") and n.startswith(("tts_env_", "tts_models", "raw/", "images/", "bgm/", "channel/", "別片/",
                                               "build/別片"))]
    assert not [n for n in ns if "_cosy_work" in n or "_jobs" in n or n.endswith(".log")]
    assert not any(n.startswith("/") or ".." in n or "\\" in n for n in ns)
    assert not (out.with_name(out.name + ".part")).exists()


def test_missing_colab_run_warns_not_fails(fake, capsys):
    rc, out = PK.pack(TAG)
    assert rc == 0 and "colab_run.py 尚不存在" in capsys.readouterr().out
    (fake / "pipeline" / "colab" / "colab_run.py").write_text("x")
    rc, out = PK.pack(TAG, out=fake / "o.zip")
    assert "pipeline/colab/colab_run.py" in names(out)


# ---- ③ 匯入擋路徑 ----

def make_zip(path, entries):
    with zipfile.ZipFile(path, "w") as zf:
        for n, c in entries.items():
            zf.writestr(n, c)
    return path


@pytest.mark.parametrize("bad", [f"build/{TAG}/tts_cosy3/../../../evil.txt", "/abs/evil.txt", "C:/evil.txt",
                                 f"build\\{TAG}\\tts_cosy3\\..\\x.wav"])
def test_import_blocks_unsafe_paths(fake, tmp_path, bad):
    zp = make_zip(tmp_path / "bad.zip", {f"build/{TAG}/tts_cosy3/009.wav": b"ok", bad: b"x"})
    with pytest.raises(ValueError):
        PK.import_zip(zp)
    assert not (fake / "build" / TAG / "tts_cosy3" / "009.wav").exists()      # 整包拒收,沒有寫任何檔
    assert not (fake.parent / "evil.txt").exists()
    assert PK.main(["--import", str(zp)]) == 2


def test_import_ignores_non_cache_and_work_files(fake, tmp_path):
    q = json.dumps(dict(passed=True))
    zp = make_zip(tmp_path / "t.zip", {f"build/{TAG}/tts_cosy3/001.qc.json": q, f"build/{TAG}/tts_cosy3/001.wav": b"n",
                                       f"build/{TAG}/tts_qc.json": "{}", f"build/{TAG}/tts_cosy3/_jobs.json": "[]",
                                       f"build/{TAG}/tts_cosy3/_cosy_work/x.wav": b"j", f"build/{TAG}/tts_cosy3/a.log": "l",
                                       f"pipeline/a.py": "evil"})
    res = PK.import_zip(zp)
    d = fake / "build" / TAG / "tts_cosy3"
    assert res["tag"] == TAG and res["written"] == 1
    assert not (d / "_jobs.json").exists() and not (d / "_cosy_work").exists() and not (d / "a.log").exists()
    assert not (fake / "build" / TAG / "tts_qc.json").exists()


def test_import_multi_tag_rejected(fake, tmp_path):
    zp = make_zip(tmp_path / "m.zip", {"build/甲/tts_cosy3/001.wav": b"a", "build/乙/tts_cosy3/001.wav": b"b"})
    with pytest.raises(ValueError):
        PK.import_zip(zp)


# ---- ④ 合併規則三種 ----

def test_merge_rules(fake, tmp_path, capsys):
    loc = fake / "build" / TAG / "tts_cosy3"
    put_unit(loc, "001", True, wav=b"local-pass")                       # zip passed=true -> 覆蓋
    put_unit(loc, "002", True, wav=b"local-pass", extra={"002.trim.wav": b"old-trim"})   # zip passed=false,本機 passed=true -> 保留本機
    put_unit(loc, "003", False, wav=b"local-fail")                      # zip passed=false,本機也沒過 -> 寫入 zip 的
    put_unit(loc, "010", True, wav=b"local-pass")                       # zip 沒有這句 -> 不動
    put_unit(loc, "001", True, wav=b"local-pass", extra={"001.trim.wav": b"stale-trim"})   # 舊 trim 會被整組換掉
    z = tmp_path / "z"
    put_unit(z, "001", True, wav=b"zip-pass")
    put_unit(z, "002", False, wav=b"zip-fail")
    put_unit(z, "003", False, wav=b"zip-fail")
    put_unit(z, "004", True, wav=b"zip-new")                            # 本機沒有 -> 寫入
    zp = tmp_path / f"tts_{TAG}.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        for f in z.iterdir():
            zf.write(f, f"build/{TAG}/tts_cosy3/{f.name}")
    res = PK.import_zip(zp)
    assert (res["written"], res["kept"], res["failed"]) == (3, 1, ["003"])
    assert (loc / "001.wav").read_bytes() == b"zip-pass" and not (loc / "001.trim.wav").exists()
    assert (loc / "002.wav").read_bytes() == b"local-pass" and (loc / "002.trim.wav").read_bytes() == b"old-trim"
    assert json.loads((loc / "002.qc.json").read_text(encoding="utf-8"))["passed"] is True
    assert (loc / "003.wav").read_bytes() == b"zip-fail"
    assert json.loads((loc / "003.qc.json").read_text(encoding="utf-8"))["marker"] == "zip-fail"
    assert (loc / "004.wav").read_bytes() == b"zip-new" and (loc / "004.key").exists()
    assert (loc / "010.wav").read_bytes() == b"local-pass"
    assert "寫入 3、保留本機 1、未過 1 句:['003']" in capsys.readouterr().out


def test_merge_zip_no_qc_does_not_clobber_local(fake, tmp_path):
    loc = fake / "build" / TAG / "tts_cosy3"
    put_unit(loc, "001", False, wav=b"local-fail")
    zp = make_zip(tmp_path / "n.zip", {f"build/{TAG}/tts_cosy3/001.wav": b"zip-bare"})
    res = PK.import_zip(zp)
    assert res["kept"] == 1 and res["failed"] == ["001"] and (loc / "001.wav").read_bytes() == b"local-fail"


def test_merge_stale_local_key_replaced_by_zip(fake, tmp_path, capsys):
    """本機是舊文字(.key 音檔鍵不同)且 passed=true,zip 是改稿後新錄但品管未過 -> 用 zip 的,且列入未過。"""
    loc = fake / "build" / TAG / "tts_cosy3"
    put_unit(loc, "001", True, say="舊文字。", wav=b"local-old")
    put_unit(loc, "002", True, say=SAY, wav=b"local-same")                 # 鍵相同 -> 仍保留本機
    z = tmp_path / "z"
    put_unit(z, "001", False, say="新文字。", wav=b"zip-new-fail")
    put_unit(z, "002", False, say=SAY, wav=b"zip-fail")
    zp = tmp_path / "t.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        for f in z.iterdir():
            zf.write(f, f"build/{TAG}/tts_cosy3/{f.name}")
    res = PK.import_zip(zp)
    assert (loc / "001.wav").read_bytes() == b"zip-new-fail" and (loc / "002.wav").read_bytes() == b"local-same"
    assert (res["written"], res["kept"], res["failed"]) == (1, 1, ["001"])
    assert json.loads((loc / "001.qc.json").read_text(encoding="utf-8"))["text"] == "新文字。"


def test_frozen_refused_when_narration_unchanged(fake, monkeypatch, capsys):
    (fake / "projects" / TAG / "freeze.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(FZ, "check", lambda tag: None)
    monkeypatch.delenv("CV_REFREEZE_OK", raising=False)
    rc, _ = PK.pack(TAG)
    assert rc == 2 and "文本未變" in capsys.readouterr().out


def test_frozen_allowed_when_narration_changed(fake, monkeypatch, capsys):
    (fake / "projects" / TAG / "freeze.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(FZ, "check", lambda tag: "配音文本已改")
    monkeypatch.delenv("CV_REFREEZE_OK", raising=False)
    rc, out = PK.pack(TAG)
    assert rc == 0 and out and "放行打包" in capsys.readouterr().out


def test_frozen_allowed_with_refreeze_ok_flag_and_env(fake, monkeypatch):
    (fake / "projects" / TAG / "freeze.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(FZ, "check", lambda tag: None)
    monkeypatch.delenv("CV_REFREEZE_OK", raising=False)
    assert PK.pack(TAG, refreeze_ok=True)[0] == 0
    monkeypatch.setenv("CV_REFREEZE_OK", "1")
    assert PK.pack(TAG)[0] == 0


def test_main_import_prints_next_step(fake, tmp_path, capsys):
    z = tmp_path / "z"
    put_unit(z, "001", True)
    zp = tmp_path / "t.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        for f in z.iterdir():
            zf.write(f, f"build/{TAG}/tts_cosy3/{f.name}")
    assert PK.main(["--import", str(zp)]) == 0
    out = capsys.readouterr().out
    assert f"--tag {TAG}" in out and "--tts-review --freeze" in out


# ---- ⑤ 打包 -> 匯回 -> build.tts_all(no_synth=True) 全命中 ----

def test_roundtrip_all_hit_no_synth(fake, tmp_path, monkeypatch):
    says = {1: "這款遊戲的主角很帥。", 2: "這款遊戲的配角很帥。"}
    src = fake / "build" / TAG / "tts_cosy3"
    for i, s in says.items():
        wav = b"\0" * 4800 * 4
        stem = f"{i:03d}"
        put_unit(src, stem, True, say=s, wav=wav)
        # 品管紀錄需符合 build._qc_record:wav_sha1 與目前音檔相同
        qf = src / f"{stem}.qc.json"
        rec = json.loads(qf.read_text(encoding="utf-8"))
        rec["wav_sha1"] = B.file_sha1(src / f"{stem}.wav")
        qf.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    rc, zp = PK.pack(TAG)
    assert rc == 0
    # 換成另一個空根(模擬 Colab 做完後回本機):只把快取部分寫回
    colab_out = tmp_path / f"tts_{TAG}.zip"
    with zipfile.ZipFile(zp) as zin, zipfile.ZipFile(colab_out, "w") as zout:
        for n in zin.namelist():
            if n.startswith(f"build/{TAG}/tts_cosy3/"):
                zout.writestr(n, zin.read(n))
    root2 = mk_root(tmp_path, "root2")
    import shutil
    shutil.rmtree(root2 / "build" / TAG)
    use_root(monkeypatch, root2)
    res = PK.import_zip(colab_out)
    assert res["written"] == 2 and res["failed"] == []
    d = P.tts_dir(TAG, "cosy3")

    def boom(*a, **k):
        raise AssertionError("不該合成")
    monkeypatch.setattr(B, "_trim_one", lambda u: u.update(wav=u["raw"]))
    monkeypatch.setattr(B, "assemble_line", lambda ln, td: None)
    monkeypatch.setattr(B, "_synth_external", boom)
    monkeypatch.setattr(B, "write_qc_report", lambda *a, **k: [])
    monkeypatch.setattr(CT, "PRON", {})
    monkeypatch.setattr(CT, "TERMS", {})
    lines = [dict(idx=i, text=s, say=s) for i, s in says.items()]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        B.tts_all(lines, "V", "R", d, engine="cosy3", tts_cmd=CMD, no_synth=True)   # 有未命中會 SystemExit
    assert "命中 2、需合成或重新檢驗 0" in buf.getvalue()
