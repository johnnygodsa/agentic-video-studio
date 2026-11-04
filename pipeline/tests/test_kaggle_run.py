"""kaggle_run 本機端測試(不連網):python -X utf8 -m pytest pipeline\\tests\\test_kaggle_run.py -q
假 kaggle CLI = 一支 Python 腳本(記錄參數/環境檢查、依 scenario.json 回假輸出),以 monkeypatch kaggle_cmd 取代真 CLI。
涵蓋:metadata 欄位、Dataset 首建 vs 新版、kernel_sources 只在有上一版時加、complete/error/逾時、quota 解析、
token 不出現在 stdout/任何寫出的檔、KAGGLE_CONFIG_DIR 有設、帳本。"""
import json
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline" / "remote"))
sys.path.insert(0, str(ROOT / "pipeline"))
import kaggle_run as kr  # noqa: E402

FAKE_TOKEN = "KGAT_FAKE_TOKEN_0123456789abcdef"

FAKE_CLI = textwrap.dedent('''
    import json, os, sys
    from pathlib import Path
    here = Path(__file__).parent
    sc = json.loads((here / "scenario.json").read_text(encoding="utf-8"))
    stf = here / "state.json"
    st = json.loads(stf.read_text()) if stf.exists() else {"pushed": False, "i": 0}
    a = sys.argv[1:]
    with open(here / "calls.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"args": a, "config_dir": os.environ.get("KAGGLE_CONFIG_DIR"),
                            "token_ok": os.environ.get("KAGGLE_API_TOKEN") == sc["token"]}) + "\\n")
    def save():
        stf.write_text(json.dumps(st))
    def out(s, rc=0):
        print(s); save(); sys.exit(rc)
    if a[:2] == ["config", "view"]:
        out("Configuration values from X\\n- username: tester\\n- auth_method: ACCESS_TOKEN")
    if a[0] == "quota":
        if sc.get("quota_fail"):
            out("boom", 1)
        if "--format" in a:
            out(json.dumps([{"resource": "GPU", "used": "0.22h", "remaining": sc["quota"], "total": "30.00h"},
                            {"resource": "TPU", "used": "0.00h", "remaining": "20.00h", "total": "20.00h"}]))
        out("resource  used   remaining  total\\nGPU       0.22h  %s  30.00h" % sc["quota"])
    if a[:2] == ["datasets", "status"]:
        if not sc["dataset_exists"] and not st.get("ds_made"):
            out("404 Not Found", 1)
        ver = sc.get("ds_version", 1) + (1 if st.get("ds_versioned") else 0)
        out(json.dumps({"status": "ready", "current_version_number": ver}))
    if a[:2] == ["datasets", "create"]:
        st["ds_made"] = True; out("Dataset creation successful")
    if a[:2] == ["datasets", "version"]:
        st["ds_versioned"] = True; out("Dataset version creation request successful")
    if a[:2] == ["kernels", "status"]:
        if not st["pushed"]:
            out('tester/k has status "KernelWorkerStatus.COMPLETE"' if sc["kernel_exists"] else "404 Not Found",
                0 if sc["kernel_exists"] else 1)
        seq = sc["statuses"]
        s = seq[min(st["i"], len(seq) - 1)]
        st["i"] += 1
        out('tester/k has status "KernelWorkerStatus.%s"' % s)
    if a[:2] == ["kernels", "push"]:
        st["pushed"] = True; out("Kernel version 1 successfully pushed")
    if a[:2] == ["kernels", "output"]:
        d = Path(a[a.index("-p") + 1]); d.mkdir(parents=True, exist_ok=True)
        for name, body in sc.get("output_files", {}).items():
            (d / name).write_text(body, encoding="utf-8")
        if sc.get("leak_token"):
            print("debug " + sc["token"])
        out("Output file downloaded")
    out("unexpected " + " ".join(a), 9)
''')


@pytest.fixture
def env(tmp_path, monkeypatch):
    remote = tmp_path / "remote"
    fake_dir = tmp_path / "fake"
    fake_dir.mkdir()
    (fake_dir / "fake_kaggle.py").write_text(FAKE_CLI, encoding="utf-8")
    tok = tmp_path / "secret" / "kaggle.json"
    tok.parent.mkdir()
    tok.write_text(FAKE_TOKEN + "\n", encoding="utf-8")
    monkeypatch.setenv("CV_KAGGLE_TOKEN_FILE", str(tok))
    monkeypatch.setattr(kr, "REMOTE", remote)
    monkeypatch.setattr(kr, "kaggle_cmd", lambda: [sys.executable, str(fake_dir / "fake_kaggle.py")])

    def fake_pack(tag, out_zip):
        out_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_zip, "w") as z:
            z.writestr("pipeline/colab/colab_run.py", "# stub")
        return 0

    imports = []
    monkeypatch.setattr(kr, "run_pack", fake_pack)
    monkeypatch.setattr(kr, "run_import", lambda z: imports.append(str(z)) or 0)

    class E:
        pass

    e = E()
    e.remote, e.fake, e.imports, e.tmp = remote, fake_dir, imports, tmp_path

    def scenario(**kw):
        sc = {"token": FAKE_TOKEN, "dataset_exists": False, "kernel_exists": False, "statuses": ["COMPLETE"], "quota": "29.78h"}
        sc.update(kw)
        (fake_dir / "scenario.json").write_text(json.dumps(sc), encoding="utf-8")

    def calls():
        f = fake_dir / "calls.jsonl"
        return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []

    e.scenario, e.calls = scenario, calls
    scenario()
    return e


def _meta(e, tag="t1"):
    return json.loads((e.remote / tag / "kernel" / "kernel-metadata.json").read_text(encoding="utf-8"))


def _no_sleep(_):
    pass


class Clock:
    """假時鐘:每次 sleep 前進 poll 秒,逾時測試不真的等。"""
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += max(s, 1)


# ---------- push ----------

def test_push_first_create_metadata(env):
    rc, info = kr.push("t1", _no_sleep)
    assert rc == 0
    m = _meta(env)
    assert m["id"] == "tester/cvk-t1" and m["title"] == "cvk-t1"   # kernel 不可與 Dataset 同 slug(409)
    assert m["is_private"] is True and m["enable_gpu"] is True and m["enable_internet"] is True
    assert m["machine_shape"] == "NvidiaTeslaT4"
    assert m["dataset_sources"] == ["tester/cv-tts-t1"]
    assert m["kernel_sources"] == []          # 沒有上一版 -> 不掛自己
    assert m["code_file"] == "run.py" and m["kernel_type"] == "script"
    run_py = (env.remote / "t1" / "kernel" / "run.py").read_text(encoding="utf-8")
    compile(run_py, "run.py", "exec")
    assert 'TAG = "t1"' in run_py and "kaggle-main" in run_py
    verbs = [c["args"][:2] for c in env.calls()]
    assert ["datasets", "create"] in verbs and ["datasets", "version"] not in verbs
    ds_meta = json.loads((env.remote / "t1" / "dataset" / "dataset-metadata.json").read_text(encoding="utf-8"))
    assert ds_meta["id"] == "tester/cv-tts-t1"
    assert (env.remote / "t1" / "dataset" / "colab_t1.zip").is_file()
    assert info["dataset_mode"] == "create" and info["kernel_sources_prev"] is False


def test_push_new_dataset_version_and_kernel_sources(env):
    env.scenario(dataset_exists=True, kernel_exists=True)
    rc, info = kr.push("t1", _no_sleep)
    assert rc == 0
    verbs = [c["args"][:2] for c in env.calls()]
    assert ["datasets", "version"] in verbs and ["datasets", "create"] not in verbs
    assert _meta(env)["kernel_sources"] == ["tester/cvk-t1"]   # 上一版存在 -> 續跑
    assert info["dataset_mode"] == "version" and info["kernel_sources_prev"] is True


def test_push_tag_with_underscore_slug(env):
    kr.push("wow_stress", _no_sleep)
    assert _meta(env, "wow_stress")["id"] == "tester/cvk-wow-stress"


def test_push_blocked_by_pack_gate(env, monkeypatch):
    monkeypatch.setattr(kr, "run_pack", lambda tag, out: 2)
    rc, _ = kr.push("t1", _no_sleep)
    assert rc == kr.EXIT_PACK
    assert env.calls() == []                   # 擋項沒過就不碰 Kaggle


# ---------- wait ----------

def _pushed(e, **sc):
    e.scenario(**sc)
    assert kr.push("t1", _no_sleep)[0] == 0


def test_wait_complete_imports(env):
    status = {"ok": True, "steps": [{"name": "setup", "rc": 0}, {"name": "tts", "rc": 0}, {"name": "pack", "rc": 0}],
              "qc": {"passed": 85, "failed": 0}}
    _pushed(env, statuses=["QUEUED", "RUNNING", "RUNNING", "COMPLETE"],
            output_files={"run_status.json": json.dumps(status), "tts_t1.zip": "zipbytes"})
    clk = Clock()
    rc, info = kr.wait("t1", poll=300, timeout_h=12.5, sleep=clk.sleep, clock=clk)
    assert rc == 0 and info["status"] == "COMPLETE" and info["qc"] == {"passed": 85, "failed": 0}
    assert len(env.imports) == 1 and env.imports[0].endswith("tts_t1.zip")
    assert info["gpu_hours"] == pytest.approx(600 / 3600, abs=0.01)   # RUNNING 起算,到 COMPLETE 經過 2 輪輪詢


def test_wait_error_reports_step_and_tail(env, capsys):
    status = {"ok": False, "steps": [{"name": "setup", "rc": 0}, {"name": "tts", "rc": 1}]}
    lines = [{"stream_name": "stdout", "data": f"line{i}\n"} for i in range(50)]
    _pushed(env, statuses=["RUNNING", "ERROR"],
            output_files={"run_status.json": json.dumps(status), "k.log": json.dumps(lines)})
    clk = Clock()
    rc, info = kr.wait("t1", poll=60, timeout_h=12.5, sleep=clk.sleep, clock=clk)
    out = capsys.readouterr().out
    assert rc == kr.EXIT_FAIL and info["status"] == "ERROR"
    assert "tts" in out and "line49" in out and "line20" in out and "line19" not in out   # 失敗步驟 + 最後 30 行
    assert env.imports == []                   # 沒有 tts zip 就不匯回


def test_wait_error_still_imports_partial_zip(env):
    status = {"ok": False, "steps": [{"name": "tts", "rc": 1}]}
    _pushed(env, statuses=["ERROR"], output_files={"run_status.json": json.dumps(status), "tts_t1.zip": "z"})
    assert kr.wait("t1", sleep=_no_sleep)[0] == kr.EXIT_FAIL
    assert len(env.imports) == 1


def test_wait_complete_but_failed_step_is_failure(env):
    status = {"steps": [{"name": "tts", "rc": 3}]}
    _pushed(env, statuses=["COMPLETE"], output_files={"run_status.json": json.dumps(status)})
    assert kr.wait("t1", sleep=_no_sleep)[0] == kr.EXIT_FAIL


def test_wait_timeout(env):
    _pushed(env, statuses=["RUNNING"], output_files={"k.log": "last words\n"})
    clk = Clock()
    rc, info = kr.wait("t1", poll=300, timeout_h=1, sleep=clk.sleep, clock=clk)
    assert rc == kr.EXIT_TIMEOUT and info["status"] == "TIMEOUT"
    assert clk.t >= 3600
    assert any(c["args"][:2] == ["kernels", "output"] for c in env.calls())   # 逾時仍嘗試取回輸出


# ---------- quota ----------

def test_quota_json(env):
    assert kr.quota() == pytest.approx(29.78)


def test_quota_failure_returns_none(env):
    env.scenario(quota_fail=True)
    assert kr.quota() is None


def test_quota_no_token_returns_none(env, monkeypatch):
    monkeypatch.setenv("CV_KAGGLE_TOKEN_FILE", str(env.tmp / "nope.json"))
    assert kr.quota() is None


def test_quota_cli_prints_number(env, capsys):
    assert kr.main(["quota"]) == 0
    assert "29.78" in capsys.readouterr().out


# ---------- 憑證 / 環境 ----------

def test_token_never_leaks_and_config_dir_set(env, capsys):
    status = {"steps": [{"name": "tts", "rc": 0}]}
    env.scenario(statuses=["COMPLETE"], leak_token=True,
                 output_files={"run_status.json": json.dumps(status), "tts_t1.zip": "z"})
    rc = kr.run("t1", poll=1, sleep=_no_sleep)
    assert rc == 0
    cap = capsys.readouterr()
    assert FAKE_TOKEN not in cap.out + cap.err
    calls = env.calls()
    assert calls and all(c["token_ok"] for c in calls)                   # 子行程確實拿到 token
    assert all(Path(c["config_dir"]) == env.remote / "kcfg" for c in calls)   # 一律 tmp\remote\kcfg
    for f in env.remote.rglob("*"):                                      # 寫出的任何檔都不含 token
        if f.is_file():
            assert FAKE_TOKEN.encode() not in f.read_bytes(), f


def test_missing_token_file_is_error_not_traceback(env, monkeypatch, capsys):
    monkeypatch.setenv("CV_KAGGLE_TOKEN_FILE", str(env.tmp / "nope.json"))
    assert kr.main(["push", "t1"]) == kr.EXIT_FAIL
    assert "token" in capsys.readouterr().out


# ---------- 帳本 ----------

def test_run_writes_ledger_start_and_end(env):
    status = {"steps": [{"name": "tts", "rc": 0}], "qc": {"passed": 3}}
    env.scenario(statuses=["RUNNING", "COMPLETE"], output_files={"run_status.json": json.dumps(status), "tts_t1.zip": "z"})
    clk = Clock()
    assert kr.run("t1", poll=300, sleep=clk.sleep, clock=clk) == 0
    rows = [json.loads(l) for l in (env.remote / "usage.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in rows] == ["start", "end"]
    s, e = rows
    assert s["tag"] == e["tag"] == "t1" and s["backend"] == "kaggle" and e["kernel"] == "tester/cvk-t1"
    assert e["rc"] == 0 and e["qc"] == {"passed": 3} and "start" in e and "end" in e and "gpu_hours" in e


def test_run_failure_ledger_rc(env):
    env.scenario(statuses=["ERROR"], output_files={"run_status.json": json.dumps({"steps": [{"name": "setup", "rc": 1}]})})
    assert kr.run("t1", poll=1, sleep=_no_sleep) == kr.EXIT_FAIL
    rows = [json.loads(l) for l in (env.remote / "usage.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["event"] == "end" and rows[-1]["rc"] == kr.EXIT_FAIL and rows[-1]["status"] == "ERROR"
