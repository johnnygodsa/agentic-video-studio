"""pipeline/colab/colab_run.py 測試:setup 只驗指令組裝與跳過邏輯(dry-run,不安裝);tts 驗指令與環境變數;status/clean/pack 用假目錄。
python -X utf8 -m pytest pipeline/tests/test_colab_run.py"""
import json
import os
import shutil
import sys
import types
import zipfile
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE / "colab"))

import colab_run as CR  # noqa: E402
import paths as P  # noqa: E402

TMP = PIPE.parent / "tmp" / "test_colab_run"
WIN_ONLY = ("pywin32", "intel-openmp", "intel_openmp", "mkl", "tbb", "pyreadline3", "win32_setctime", "win32-setctime")


@pytest.fixture
def root():
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True)
    yield TMP
    shutil.rmtree(TMP, ignore_errors=True)


# ------------------------------------------------------------ 跨平台 venv 路徑
def test_venv_python(monkeypatch):
    assert P.venv_python("E") == Path("E") / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    monkeypatch.setattr(P, "os", types.SimpleNamespace(name="posix"))   # 只換 paths 模組看到的 os
    assert P.venv_python("/content/CV/tts_env_cosy3").as_posix().endswith("tts_env_cosy3/bin/python")


# ------------------------------------------------------------ requirements
@pytest.mark.parametrize("name,torch,cu", [("chattts", "2.6.0", "cu124"), ("cosy3", "2.3.1", "cu121"),
                                           ("asr", "2.11.0", "cu128"), ("asr_fun", "2.10.0", "cu128")])
def test_requirements(name, torch, cu):
    lines = [ln.strip() for ln in (CR.HERE / CR.ENVS[name]["req"]).read_text(encoding="utf-8").splitlines()]
    pkgs = [ln for ln in lines if ln and not ln.startswith(("#", "--"))]
    assert f"--extra-index-url https://download.pytorch.org/whl/{cu}" in lines
    assert f"torch=={torch}+{cu}" in pkgs and f"torchaudio=={torch}+{cu}" in pkgs
    names = [p.split("==")[0].lower() for p in pkgs]
    assert all("==" in p for p in pkgs), "每個套件都要固定版本"
    assert len(names) == len(set(names)), "套件重複"
    assert not set(names) & set(WIN_ONLY)


# ------------------------------------------------------------ setup:指令組裝與跳過
def test_env_steps(root):
    steps = CR.env_steps(root, "asr")
    py = str(P.venv_python(root / "tts_env_asr"))
    assert steps[0] == ["uv", "venv", "--python", "3.11", str(root / "tts_env_asr")]
    assert steps[1][:4] == ["uv", "pip", "install", "--python"] and steps[1][4] == py
    assert steps[1][-1] == str(CR.HERE / "req_asr.txt") and "unsafe-best-match" in steps[1]
    assert steps[2][0] == py and "cuda.is_available" in steps[2][-1]


def test_model_steps(root):
    s = CR.model_steps(root, "cosyvoice3")
    cosy = root / "tts_models" / "CosyVoice"
    assert s[0] == ["git", "clone", "--recursive", CR.COSY_GIT, str(cosy)]
    assert ["git", "-C", str(cosy), "checkout", "-q", CR.COSY_COMMIT] in s
    assert "submodule" in s[2]
    assert "FunAudioLLM/Fun-CosyVoice3-0.5B-2512" in s[-1][-1] and CR.MODELS["cosyvoice3"]["rev"] in s[-1][-1]
    assert repr(str(cosy / "pretrained_models" / "Fun-CosyVoice3-0.5B")) in s[-1][-1]
    (cosy / ".git").mkdir(parents=True)   # 已 clone:不再 clone,只 checkout 指定 commit
    assert all(c[:2] != ["git", "clone"] for c in CR.model_steps(root, "cosyvoice3"))
    w = CR.model_steps(root, "faster-whisper-small")
    assert len(w) == 1 and "cache_dir=" + repr(str(root / "tts_models" / ".")) in w[0][-1]
    assert "cache_dir=" + repr(str(root / "tts_models" / "hub")) in CR.model_steps(root, "spkrec-ecapa")[0][-1]
    assert "local_dir=" + repr(str(root / "tts_models" / "asr" / "qwen3-asr-0.6b")) in CR.model_steps(root, "qwen3-asr-0.6b")[0][-1]


def _finish_model(root, name):
    m = CR.MODELS[name]
    if "local_dir" in m:
        f = root / "tts_models" / m["local_dir"] / m["check"]
    else:
        f = (root / "tts_models" / m["cache_dir"] / ("models--" + m["repo"].replace("/", "--")) / "snapshots" / m["rev"]
             / m["check"])
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"x")
    mk = CR.model_mark(root, name)
    mk.parent.mkdir(parents=True, exist_ok=True)
    mk.write_text(CR.model_sig(name), encoding="utf-8")


def test_plan_skip(root):
    pre, tasks, skipped = CR.plan(root)
    assert not skipped and len(tasks) == len(CR.ENVS) + len(CR.MODELS)
    assert any(c[:3] == ["uv", "python", "install"] and set(c[3:]) == {"3.10", "3.11", "3.12"} for c in pre)
    # 環境:標記簽章相同才跳過;req 改了(簽章不同)就重裝
    mk = CR.env_mark(root, "chattts")
    mk.parent.mkdir(parents=True)
    mk.write_text(CR.env_sig("chattts"), encoding="utf-8")
    mk2 = CR.env_mark(root, "cosy3")
    mk2.parent.mkdir(parents=True)
    mk2.write_text("old", encoding="utf-8")
    # 模型:標記在、代表檔也在才跳過;標記在但檔案不見了照樣下載
    _finish_model(root, "qwen3-asr-0.6b")
    _finish_model(root, "spkrec-ecapa")
    CR.model_mark(root, "fun-asr-nano-hf").write_text(CR.model_sig("fun-asr-nano-hf"), encoding="utf-8")
    pre, tasks, skipped = CR.plan(root)
    assert set(skipped) == {("env", "chattts"), ("model", "qwen3-asr-0.6b"), ("model", "spkrec-ecapa")}
    names = {t[1] for t in tasks}
    assert {"cosy3", "fun-asr-nano-hf"} <= names and "chattts" not in names
    assert any(c[:3] == ["uv", "python", "install"] and "3.10" in c for c in pre)   # cosy3 還要 3.10


def test_plan_all_done(root):
    for name in CR.ENVS:
        mk = CR.env_mark(root, name)
        mk.parent.mkdir(parents=True)
        mk.write_text(CR.env_sig(name), encoding="utf-8")
    for name in CR.MODELS:
        _finish_model(root, name)
    pre, tasks, skipped = CR.plan(root)
    assert pre == [] and tasks == [] and len(skipped) == len(CR.ENVS) + len(CR.MODELS)


def test_setup_dry_run(root, capsys):
    _finish_model(root, "faster-whisper-small")
    assert CR.setup(root, dry_run=True) == 0
    out = capsys.readouterr().out
    assert "跳過 model faster-whisper-small" in out
    assert "$ uv venv --python 3.12" in out and "$ git clone --recursive" in out
    assert not (root / "tmp").exists() and not (root / "tts_env_chattts").exists()   # dry-run 不建任何東西


@pytest.mark.skipif(os.name != "nt", reason="只在本機(Windows)擋")
def test_setup_refuses_on_windows(root):
    with pytest.raises(SystemExit):
        CR.setup(root, dry_run=False)


def test_main_dry_run():
    assert CR.main(["setup", "--dry-run"]) == 0


# ------------------------------------------------------------ tts
def test_tts_cmd():
    c = CR.tts_cmd("demo")
    assert c[0] == str(P.TTS_ENV) and c[3].endswith("build.py")
    s = " ".join(c[4:])
    assert s == ("--script demo/script.json --voice cosyB --rate +18% --gap 0.12 --section-gap 0.30 "
                 "--tts-engine cosy3 --tag demo --tts-only --out colab")
    mv = (PIPE / "make_version.py").read_text(encoding="utf-8")   # 進快取鍵的參數與 make_version 一致
    for frag in ('"--rate", "+18%"', '"--gap", "0.12"', '"--section-gap", "0.30"', 'voice, spk = "cosyB", None'):
        assert frag in mv


def test_tts_env(monkeypatch):
    for k in ("TTS_RESUME_DIR", "TTS_RESUME_KEEP", "TTS_ASR2_DEVICE", "TTS_TS_DEVICE", "CV_TTS_MAX_RETRY", "CV_TTS_RATE_SEEDS"):
        monkeypatch.delenv(k, raising=False)
    e = CR.tts_env()
    assert e["CLAUDE_VIDEO_ROOT"] == str(P.ROOT) and e["TTS_TS_DEVICE"] == "cuda" and e["TTS_ASR2_DEVICE"] == "cuda"
    assert e["TTS_RESUME_DIR"] == str(CR.DRIVE / "resume") and e["TTS_RESUME_KEEP"] == "1"
    assert e["HOME"] == e["USERPROFILE"] == str(P.TMP / "colab_home")
    assert "CV_TTS_MAX_RETRY" not in e and "CV_TTS_RATE_SEEDS" not in e
    monkeypatch.setenv("TTS_RESUME_DIR", "/x/resume")   # 筆記本設的沿用
    monkeypatch.setenv("CV_TTS_MAX_RETRY", "99")         # 原樣傳給 tts_cosy3,由它夾上限(test_colab_resume::test_env_limit)
    e = CR.tts_env()
    assert e["TTS_RESUME_DIR"] == "/x/resume" and e["CV_TTS_MAX_RETRY"] == "99"


# ------------------------------------------------------------ status / clean / pack(假快取)
def _fake_cache(root, tag="demo"):
    d = root / "build" / tag / "tts_cosy3"
    d.mkdir(parents=True)
    for stem, passed, key in (("001", True, True), ("002", False, True), ("003", True, False)):
        (d / f"{stem}.wav").write_bytes(b"RIFF")
        (d / f"{stem}.qc.json").write_text(json.dumps({"passed": passed}), encoding="utf-8")
        if key:
            (d / f"{stem}.key").write_text("k", encoding="utf-8")
    (d / "001.trim.wav").write_bytes(b"RIFF")
    (d / "001.trim.key").write_text("t", encoding="utf-8")
    jobs = [{"idx": i, "out": f"C:\\x\\build\\{tag}\\tts_cosy3\\{i:03d}.wav"} for i in (2, 3, 4)]
    (d / "_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    (d / "_cosy_work0").mkdir()
    (d / "_cosy_work0" / "a.wav").write_bytes(b"x")
    (d / "_cosy3_worker.log").write_text("log", encoding="utf-8")
    (d / "_resume_x.json").write_text("{}", encoding="utf-8")
    (root / "build" / tag / "tts_qc.json").write_text("{}", encoding="utf-8")
    return d


def test_status(root, capsys):
    _fake_cache(root)
    c = CR.status("demo", root, resume=False)
    assert c == dict(passed=1, failed=1, no_key=1, jobs=3, jobs_left=1)
    assert "還剩 1 個" in capsys.readouterr().out
    assert CR.unit_counts("none", root)["jobs"] == 0


def test_pack(root):
    _fake_cache(root)
    drive = root / "drive"
    out = CR.pack("demo", root, drive)
    assert out == drive / "tts_demo.zip" and not list(drive.glob("*.part"))
    names = set(zipfile.ZipFile(out).namelist())
    pre = "build/demo/tts_cosy3/"
    assert names == {pre + n for n in ("001.wav", "001.qc.json", "001.key", "001.trim.wav", "001.trim.key", "002.wav",
                                       "002.qc.json", "002.key", "003.wav", "003.qc.json")} | {"build/demo/tts_qc.json"}


def test_clean(root, monkeypatch):
    d = _fake_cache(root)
    rd = root / "resume"
    (rd / "demo").mkdir(parents=True)
    (rd / "demo" / "k.wav").write_bytes(b"x")
    monkeypatch.setenv("TTS_RESUME_DIR", str(rd))
    assert CR.clean("demo", root) == 3
    assert not (d / "_jobs.json").exists() and not (d / "_cosy_work0").exists() and not (d / "_cosy3_worker.log").exists()
    assert (d / "001.wav").exists() and (d / "002.qc.json").exists() and (rd / "demo").exists()
    CR.clean("demo", root, resume=True)
    assert not (rd / "demo").exists()


# ------------------------------------------------------------ 筆記本
def test_notebook():
    nb = json.loads((CR.HERE / "colab_tts.ipynb").read_text(encoding="utf-8"))
    src = "\n".join("".join(c["source"]) for c in nb["cells"])
    assert len(nb["cells"]) == 9 and nb["cells"][0]["cell_type"] == "markdown"
    assert all(not c.get("outputs") for c in nb["cells"] if c["cell_type"] == "code")
    for s in ("CV_colab", "/content/CV", "import colab_run as CR", "TTS_RESUME_DIR", "TTS_RESUME_KEEP", "TTS_ASR2_DEVICE",
              "TTS_TS_DEVICE", "# os.environ['CV_TTS_MAX_RETRY'] = '12'", "CR.tts_cmd(TAG)", "CR.tts_env()", "CR.pack(TAG)", "CR.apply_tts_zip(TAG, TTS_ZIP, CV)"):
        assert s in src, s
    assert "KC_" not in src and "999" not in src and "selftest" not in src
    nbformat = pytest.importorskip("nbformat")
    nbformat.validate(nbformat.reads(json.dumps(nb), as_version=4))


# ------------------------------------------------------------ Kaggle
@pytest.fixture
def plat(monkeypatch):
    for k in ("KAGGLE_KERNEL_RUN_TYPE", "CV_REMOTE_PLATFORM", "TTS_RESUME_DIR", "CUDA_VISIBLE_DEVICES", "CV_TTS_GPUS"):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_platform(plat):
    assert CR.platform() == "colab"
    plat.setenv("KAGGLE_KERNEL_RUN_TYPE", "Batch")
    assert CR.platform() == "kaggle"
    plat.setenv("CV_REMOTE_PLATFORM", "colab")   # 強制優先
    assert CR.platform() == "colab"
    plat.setenv("CV_REMOTE_PLATFORM", "kaggle")
    plat.delenv("KAGGLE_KERNEL_RUN_TYPE")
    assert CR.platform() == "kaggle"
    plat.setenv("CV_REMOTE_PLATFORM", "bogus")   # 無效值忽略
    assert CR.platform() == "colab"


def test_kaggle_tts_env(plat):
    plat.setenv("CV_REMOTE_PLATFORM", "kaggle")
    e = CR.tts_env()
    assert e["TTS_RESUME_DIR"] == str(CR.KAGGLE_WORK / "resume") and e["TTS_RESUME_KEEP"] == "1"
    assert "CUDA_VISIBLE_DEVICES" not in e and e["TTS_TS_DEVICE"] == "cuda"   # 預設兩張卡都給 tts_cosy3 分片
    assert CR.tts_gpus() == 2
    plat.setenv("CV_TTS_GPUS", "1")   # 關分片:只用第一張
    assert CR.tts_env()["CUDA_VISIBLE_DEVICES"] == "0" and CR.tts_gpus() == 1
    plat.setenv("CUDA_VISIBLE_DEVICES", "1")   # 呼叫端已設的沿用
    assert CR.tts_env()["CUDA_VISIBLE_DEVICES"] == "1"
    plat.delenv("CV_TTS_GPUS")
    plat.setenv("CV_REMOTE_PLATFORM", "colab")
    plat.delenv("CUDA_VISIBLE_DEVICES")
    assert "CUDA_VISIBLE_DEVICES" not in CR.tts_env() and CR.tts_gpus() == 1


def test_tts_shards(root):
    assert CR.tts_shards("t", root) == []
    d = CR.tts_dir("t", root)
    (d / "sub").mkdir(parents=True)
    (d / "_cosy3_shards.json").write_text(json.dumps(dict(gpus=2, shards=[dict(gpu=0, lines=30, tasks=50, minutes=10.2),
                                                                         dict(gpu=1, lines=29, tasks=48, minutes=9.9)])))
    (d / "sub" / "_cosy3_shards.json").write_text(json.dumps(dict(gpus=2, shards=[dict(gpu=1, lines=2, tasks=2, minutes=0.3)])))
    assert CR.tts_shards("t", root) == [dict(gpu=0, lines=30, tasks=50, minutes=10.2), dict(gpu=1, lines=31, tasks=50, minutes=10.2)]


def test_find_input_zip(root):
    inp = root / "input"
    assert CR.find_input_zip("demo", inp) is None
    a = inp / "datasets" / "demo-user" / "cv-tts-demo"
    b = inp / "x" / "y" / "z"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "colab_other.zip").write_bytes(b"x")
    (a / "colab_demo.zip").write_bytes(b"old")
    (b / "colab_demo.zip").write_bytes(b"new")
    os.utime(a / "colab_demo.zip", (1, 1))
    assert CR.find_input_zip("demo", inp) == b / "colab_demo.zip"   # 結構不固定、遞迴找、多個取最新


def _zip(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for n, c in files.items():
            z.writestr(n, c)
    return path


def test_extract_input(root):
    z = _zip(root / "in" / "colab_demo.zip", {"pipeline/colab/colab_run.py": "x", "projects/demo/script.json": "{}"})
    r = root / "CV"
    assert CR.extract_input(z, r) is True and (r / "pipeline" / "colab" / "colab_run.py").read_text() == "x"
    (r / "projects" / "demo" / "script.json").write_text("edited")
    assert CR.extract_input(z, r) is False and (r / "projects" / "demo" / "script.json").read_text() == "edited"


def _qc_zip(path, tag="demo"):
    pre = f"build/{tag}/tts_cosy3/"
    return _zip(path, {pre + "001.wav": "a", pre + "001.qc.json": json.dumps({"passed": True}), pre + "001.key": "k",
                       pre + "002.wav": "b", pre + "002.qc.json": json.dumps({"passed": False}), pre + "002.key": "k",
                       "build/other/tts_cosy3/009.wav": "x", "build/../evil.txt": "x", f"build/{tag}/a": "x"})


def test_apply_tts_zip(root):
    z = _qc_zip(root / "tts_demo.zip")
    r = root / "CV"
    n, redo = CR.apply_tts_zip("demo", z, r)
    d = r / "build" / "demo" / "tts_cosy3"
    assert n == 7 and redo == ["002"]   # other 與 .. 被擋;build/demo/a 只有 3 段(len>=3)照收
    assert (d / "001.key").exists() and not (d / "002.key").exists() and (d / "002.wav").exists()
    assert not (r / "build" / "other").exists() and not (root / "evil.txt").exists() and not (r / "evil.txt").exists()


def test_mount_resume(root):
    inp, work, r = root / "input", root / "work", root / "CV"
    assert CR.mount_resume("demo", inp, work, r) == dict(resume_from=[], tts_zip=None, files=0, redo=[])   # 沒掛載 = 全新
    k = inp / "notebooks" / "demo-user" / "cv-demo"
    (k / "resume" / "demo" / "sub").mkdir(parents=True)
    (k / "resume" / "demo" / "sub" / "a.wav").write_bytes(b"w")
    (k / "resume" / "other").mkdir()
    (k / "resume" / "other" / "b.wav").write_bytes(b"w")
    _qc_zip(k / "tts_demo.zip")
    m = CR.mount_resume("demo", inp, work, r)
    assert (work / "resume" / "demo" / "sub" / "a.wav").read_bytes() == b"w" and not (work / "resume" / "other").exists()
    assert m["resume_from"] == [str(k / "resume" / "demo")] and m["tts_zip"] == str(k / "tts_demo.zip")
    assert m["redo"] == ["002"] and not (r / "build" / "demo" / "tts_cosy3" / "002.key").exists()


def _fake_kaggle(root, monkeypatch, calls, fail=None):
    """假 setup/tts/pack;fail = 讓哪一步回 5。輸入 zip 放在 root/input。"""
    _zip(root / "input" / "ds" / "colab_demo.zip", {"pipeline/colab/colab_run.py": "x"})
    monkeypatch.setattr(CR, "_self_in_root", lambda r: True)

    def mk(name):
        def f(*a, **kw):
            calls.append(name)
            if name == "tts":
                (root / "CV" / "build" / "demo").mkdir(parents=True, exist_ok=True)
                (root / "CV" / "build" / "demo" / "tts_qc.json").write_text(
                    json.dumps({"passed": 8, "checked": 10, "failed": [{"idx": 3}, {"idx": 7}]}), encoding="utf-8")
            if name == "pack" and fail == name:   # 真的 pack 回路徑、失敗時 sys.exit
                sys.exit(5)
            return 5 if fail == name else 0
        return f
    for n in ("setup", "tts", "pack"):
        monkeypatch.setattr(CR, n, mk(n))
    return dict(root=root / "CV", work=root / "work", input_root=root / "input")


def _status(root):
    return json.loads((root / "work" / "run_status.json").read_text(encoding="utf-8"))


def test_kaggle_main_order_and_status(root, monkeypatch, capsys):
    calls = []
    kw = _fake_kaggle(root, monkeypatch, calls)
    assert CR.kaggle_main("demo", **kw) == 0
    assert calls == ["setup", "tts", "pack"]
    st = _status(root)
    assert [s["step"] for s in st["steps"]] == ["prepare", "setup", "tts", "pack"] and all(s["rc"] == 0 for s in st["steps"])
    assert st["state"] == "done" and st["step"] == "pack" and st["rc"] == 0 and isinstance(st["minutes"], float)
    assert st["qc"] == dict(passed=8, checked=10, failed=[3, 7]) and st["tag"] == "demo"
    assert (root / "CV" / "pipeline" / "colab" / "colab_run.py").exists()   # 輸入 zip 解到素材根
    assert (root / "work" / "logs" / "setup_summary.txt").exists()
    out = capsys.readouterr().out
    assert "步驟 setup 開始" in out and "步驟 pack 結束 rc=0" in out and "全部完成" in out


@pytest.mark.parametrize("fail,expect", [("setup", ["setup"]), ("tts", ["setup", "tts"]), ("pack", ["setup", "tts", "pack"])])
def test_kaggle_main_stops_on_failure(root, monkeypatch, fail, expect):
    calls = []
    kw = _fake_kaggle(root, monkeypatch, calls, fail=fail)
    assert CR.kaggle_main("demo", **kw) == 5
    assert calls == expect
    st = _status(root)
    assert st["state"] == "failed" and st["step"] == fail and st["rc"] == 5 and st["steps"][-1]["rc"] == 5
    assert st["steps"][-1]["step"] == fail


def test_kaggle_main_no_input_zip(root, monkeypatch):
    calls = []
    kw = _fake_kaggle(root, monkeypatch, calls)
    (root / "input" / "ds" / "colab_demo.zip").unlink()
    assert CR.kaggle_main("demo", **kw) == 2 and calls == []
    st = _status(root)
    assert st["state"] == "failed" and st["step"] == "prepare" and st["rc"] == 2 and st["qc"] is None


def test_kaggle_main_catches_exit_and_exception(root, monkeypatch):
    calls = []
    kw = _fake_kaggle(root, monkeypatch, calls)

    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(CR, "tts", boom)
    assert CR.kaggle_main("demo", **kw) == 1 and _status(root)["step"] == "tts"
    monkeypatch.setattr(CR, "tts", lambda *a, **k: 0)
    monkeypatch.setattr(CR, "pack", lambda *a, **k: sys.exit("沒有東西可打包"))
    assert CR.kaggle_main("demo", **kw) == 1 and _status(root)["step"] == "pack"


def test_kaggle_main_mounts_resume(root, monkeypatch):
    calls = []
    kw = _fake_kaggle(root, monkeypatch, calls)
    k = root / "input" / "notebooks" / "u" / "s"
    (k / "resume" / "demo").mkdir(parents=True)
    (k / "resume" / "demo" / "a.wav").write_bytes(b"w")
    assert CR.kaggle_main("demo", **kw) == 0
    assert (root / "work" / "resume" / "demo" / "a.wav").exists() and "resume_mb" in _status(root)


def test_kaggle_main_reexec_from_extracted_copy(root, monkeypatch):
    calls, ran = [], []
    kw = _fake_kaggle(root, monkeypatch, calls)
    monkeypatch.setattr(CR, "_self_in_root", lambda r: False)   # 執行的是 Dataset 裡那份
    monkeypatch.delenv("CV_KAGGLE_REEXEC", raising=False)
    monkeypatch.setattr(CR.subprocess, "run", lambda cmd, **k: ran.append((cmd, k["env"])) or types.SimpleNamespace(returncode=0))
    assert CR.kaggle_main("demo", **kw) == 0 and calls == []   # 本行程不跑 setup/tts/pack,交給解壓後那份
    cmd, env = ran[0]
    assert cmd[-2:] == ["kaggle-main", "demo"] and cmd[-3] == str(root / "CV" / "pipeline" / "colab" / "colab_run.py")
    assert env["CV_KAGGLE_REEXEC"] == "1" and env["CLAUDE_VIDEO_ROOT"] == str(root / "CV")


def test_main_registers_kaggle_main(monkeypatch):
    got = []
    monkeypatch.setattr(CR, "kaggle_main", lambda tag: got.append(tag) or 0)
    assert CR.main(["kaggle-main", "demo"]) == 0 and got == ["demo"]


def test_find_input_zip_env_first(root, monkeypatch):
    inp = root / "input"
    (inp / "a").mkdir(parents=True)
    (inp / "a" / "colab_demo.zip").write_bytes(b"x")
    z = root / "repacked" / "colab_demo.zip"
    z.parent.mkdir()
    z.write_bytes(b"y")
    monkeypatch.setenv("CV_KAGGLE_INPUT_ZIP", str(z))
    assert CR.find_input_zip("demo", inp) == z
    monkeypatch.setenv("CV_KAGGLE_INPUT_ZIP", str(root / "nope.zip"))   # 不存在 -> 照舊 glob
    assert CR.find_input_zip("demo", inp) == inp / "a" / "colab_demo.zip"


def test_mount_resume_env_first(root, monkeypatch):
    inp, work, r = root / "input", root / "work", root / "CV"
    other = inp / "notebooks" / "u" / "other"
    (other / "resume" / "demo").mkdir(parents=True)
    (other / "resume" / "demo" / "no.wav").write_bytes(b"n")
    prev = root / "mnt" / "prev"
    (prev / "resume" / "demo").mkdir(parents=True)
    (prev / "resume" / "demo" / "a.wav").write_bytes(b"w")
    _qc_zip(prev / "tts_demo.zip")
    monkeypatch.setenv("CV_KAGGLE_PREV_RESUME", str(prev / "resume" / "demo"))
    m = CR.mount_resume("demo", inp, work, r)
    assert (work / "resume" / "demo" / "a.wav").exists() and not (work / "resume" / "demo" / "no.wav").exists()
    assert m["tts_zip"] == str(prev / "tts_demo.zip") and m["redo"] == ["002"]


def test_status_steps_have_name_rc(root, monkeypatch):
    kw = _fake_kaggle(root, monkeypatch, [])
    CR.kaggle_main("demo", **kw)
    assert all({"name", "rc"} <= set(s) for s in _status(root)["steps"]) and "qc" in _status(root)
