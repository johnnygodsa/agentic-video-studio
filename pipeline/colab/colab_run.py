r"""Colab 端:安裝、配音、狀態、打包(全部 Python,不跑 sh;筆記本 pipeline/colab/colab_tts.ipynb 呼叫)。

python -X utf8 pipeline/colab/colab_run.py setup [--dry-run]   四個環境(uv)平行裝 + 模型平行下載;完成標記在就跳過;結束碼 0 = 全部 OK
python -X utf8 pipeline/colab/colab_run.py tts <tag>            build.py --tts-only --tts-engine cosy3(與 make_version --tts-review 配音步同參數)
python -X utf8 pipeline/colab/colab_run.py status <tag>         已做好的單位(passed/failed)、_jobs.json 剩幾個、續跑快取筆數/MB
python -X utf8 pipeline/colab/colab_run.py clean <tag> [--resume]  刪工作檔(_cosy_work* _jobs.json *.log);--resume 連續跑快取一起刪(打包後)
python -X utf8 pipeline/colab/colab_run.py pack <tag>           build/<tag>/tts_cosy3/** + tts_qc.json -> <Drive>/CV_colab/tts_<tag>.zip
python -X utf8 pipeline/colab/colab_run.py kaggle-main <tag>    Kaggle 批次:prepare -> setup -> tts -> pack,每步寫 /kaggle/working/run_status.json,任一步非 0 就停

筆記本背景啟動配音用 tts_cmd(tag) / tts_env()(子行程自己跑,格子不卡住)。
環境變數:CV_COLAB_DRIVE(預設 /content/drive/MyDrive/CV_colab)、TTS_RESUME_DIR / TTS_RESUME_KEEP / TTS_ASR2_DEVICE / TTS_TS_DEVICE / TTS_FA_DEVICE
(沒設才給 Colab 預設)、CV_TTS_MAX_RETRY / CV_TTS_RATE_SEEDS(上限 12)。

平台:KAGGLE_KERNEL_RUN_TYPE 存在 = Kaggle(CV_REMOTE_PLATFORM=kaggle|colab 可強制)。Kaggle 的目錄配置:
  /tmp/CV                     素材根(CLAUDE_VIDEO_ROOT 沒設就用它):解壓的 colab_<tag>.zip、四個環境、模型(/tmp 約 1 TB)
  /kaggle/input/**            輸入 zip colab_<tag>.zip(遞迴找);上一次輸出經 kernel_sources 掛在 notebooks/<帳號>/<slug>/
  /kaggle/working             只放輸出(上限 20 GB):tts_<tag>.zip、run_status.json、resume/<tag>/、logs/
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))

KAGGLE_ROOT = Path("/tmp/CV")           # Kaggle 素材根:環境與模型放 /tmp(/kaggle/working 只有 20 GB)
KAGGLE_WORK = Path("/kaggle/working")   # Kaggle 輸出目錄
KAGGLE_INPUT = Path("/kaggle/input")    # Kaggle 輸入(Dataset、kernel_sources 掛載)


def platform():
    """-> 'kaggle' | 'colab'。CV_REMOTE_PLATFORM 可強制;否則看 KAGGLE_KERNEL_RUN_TYPE 在不在。"""
    forced = os.environ.get("CV_REMOTE_PLATFORM", "").strip().lower()
    if forced in ("kaggle", "colab"):
        return forced
    return "kaggle" if "KAGGLE_KERNEL_RUN_TYPE" in os.environ else "colab"


if platform() == "kaggle":   # paths.py import 時就決定 ROOT:Kaggle 沒指定就用 /tmp/CV
    os.environ.setdefault("CLAUDE_VIDEO_ROOT", str(KAGGLE_ROOT))

import paths as P  # noqa: E402

HERE = Path(__file__).resolve().parent
DRIVE = Path(os.environ.get("CV_COLAB_DRIVE", "/content/drive/MyDrive/CV_colab"))
RETRY_CAP = 12   # 重錄上限不開到無限(PLAN_COLAB §0):超過就當 12
MARK = ".cv_setup_ok"

# 四個環境:目錄名與本機相同(paths / tts_cosy3 / tts_asr 照用);Python 版本照本機
ENVS = {
    "chattts": dict(dir="tts_env_chattts", py="3.10", req="req_chattts.txt"),
    "cosy3": dict(dir="tts_env_cosy3", py="3.10", req="req_cosy3.txt"),
    "asr": dict(dir="tts_env_asr", py="3.11", req="req_asr.txt"),
    "asr_fun": dict(dir="tts_env_asr_fun", py="3.12", req="req_asr_fun.txt"),
}

# 模型(來源與 revision 見 tmp/colab/models.md;放的位置與本機 tts_models\ 相同)
# local_dir = 直接放到該目錄;cache_dir = HF 快取格式(程式執行時以 repo ID 查,如 faster-whisper download_root、speechbrain HF_HOME)
COSY_GIT = "https://github.com/FunAudioLLM/CosyVoice.git"
COSY_COMMIT = "074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc"
MODELS = {
    "cosyvoice3": dict(repo="FunAudioLLM/Fun-CosyVoice3-0.5B-2512", rev="29e01c4e8d000f4bcd70751be16fa94bf3d85a18",
                       local_dir="CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B", check="flow.pt", git=True),
    "qwen3-asr-0.6b": dict(repo="Qwen/Qwen3-ASR-0.6B", rev="5eb144179a02acc5e5ba31e748d22b0cf3e303b0",
                           local_dir="asr/qwen3-asr-0.6b", check="config.json"),
    "fun-asr-nano-hf": dict(repo="FunAudioLLM/Fun-ASR-Nano-2512-hf", rev="7ef6cafdc445b5beff0b730cbeb51952c793ca6e",
                            local_dir="asr/fun-asr-nano-hf", check="config.json"),
    "qwen3-forcedaligner-0.6b": dict(repo="Qwen/Qwen3-ForcedAligner-0.6B", rev="c7cbfc2048c462b0d63a45797104fc9db3ad62b7",
                                     local_dir="asr/qwen3-forcedaligner-0.6b", check="model.safetensors"),
    "faster-whisper-small": dict(repo="Systran/faster-whisper-small", rev="536b0662742c02347bc0e980a01041f333bce120",
                                 cache_dir=".", check="model.bin"),
    "spkrec-ecapa": dict(repo="speechbrain/spkrec-ecapa-voxceleb", rev="0f99f2d0ebe89ac095bcc5903c4dd8f72b367286",
                         cache_dir="hub", check="embedding_model.ckpt"),
}


def log(msg):
    print(f"[colab] {msg}", flush=True)


# ------------------------------------------------------------ setup:步驟組裝(dry-run / 測試只看這層)
def _sig(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def env_sig(name):
    e = ENVS[name]
    return _sig(e["py"], (HERE / e["req"]).read_bytes().decode("utf-8"))


def model_sig(name):
    m = MODELS[name]
    return _sig(m["repo"], m["rev"], COSY_COMMIT if m.get("git") else "")


def env_mark(root, name):
    return Path(root) / ENVS[name]["dir"] / MARK


def model_mark(root, name):
    return Path(root) / "tts_models" / ".cv_setup" / f"{name}.ok"


def done(mark, sig):
    return mark.is_file() and mark.read_text(encoding="utf-8").strip() == sig


def env_steps(root, name):
    """一個環境的指令清單:建 venv -> uv pip install -r req -> 驗證(torch 版本、cuda)。"""
    e, root = ENVS[name], Path(root)
    env = root / e["dir"]
    py = P.venv_python(env)
    probe = "import json, torch; print('@@TORCH ' + json.dumps({'torch': torch.__version__, 'cuda': torch.cuda.is_available()}))"
    return [
        ["uv", "venv", "--python", e["py"], str(env)],
        # build_constraints:setuptools<81(openai-whisper 20231117 的 setup.py 還 import pkg_resources;T6 首跑擋在這)
        ["uv", "pip", "install", "--python", str(py), "--index-strategy", "unsafe-best-match",
         "--build-constraints", str(HERE / "build_constraints.txt"), "-r", str(HERE / e["req"])],
        [str(py), "-c", probe],
    ]


def _hf_cmd(repo, rev, **kw):
    args = ", ".join(f"{k}={v!r}" for k, v in kw.items())
    return [sys.executable, "-c", f"from huggingface_hub import snapshot_download; "
                                  f"print(snapshot_download(repo_id={repo!r}, revision={rev!r}, {args}))"]


def model_steps(root, name):
    """一個模型的指令清單。CosyVoice:先 git clone 指定 commit(含 Matcha-TTS submodule),權重放進它的 pretrained_models。"""
    m, models = MODELS[name], Path(root) / "tts_models"
    steps = []
    if m.get("git"):
        cosy = models / "CosyVoice"
        if not (cosy / ".git").is_dir():
            steps.append(["git", "clone", "--recursive", COSY_GIT, str(cosy)])
        steps += [["git", "-C", str(cosy), "checkout", "-q", COSY_COMMIT],
                  ["git", "-C", str(cosy), "submodule", "update", "--init", "--recursive"]]
    if "local_dir" in m:
        steps.append(_hf_cmd(m["repo"], m["rev"], local_dir=str(models / m["local_dir"])))
    else:
        steps.append(_hf_cmd(m["repo"], m["rev"], cache_dir=str(models / m["cache_dir"])))
    return steps


def model_ok(root, name):
    """模型檔是否齊全(看代表檔)。"""
    m, models = MODELS[name], Path(root) / "tts_models"
    if "local_dir" in m:
        return (models / m["local_dir"] / m["check"]).is_file()
    snap = models / m["cache_dir"] / ("models--" + m["repo"].replace("/", "--")) / "snapshots" / m["rev"]
    return (snap / m["check"]).exists()


def pre_steps(have_uv, have_hf, pys):
    """平行安裝前的共用準備:uv、huggingface_hub(系統 python 下載模型用)、各版本 Python(一次裝完,避免平行搶同一份)。"""
    steps = []
    if not have_uv:
        steps.append([sys.executable, "-m", "pip", "install", "-q", "uv"])
    if not have_hf:
        steps.append([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub"])
    if pys:
        steps.append(["uv", "python", "install", *sorted(pys)])
    return steps


def _has_hf():
    try:
        import huggingface_hub  # noqa: F401
        return True
    except ImportError:
        return False


def plan(root):
    """-> (pre, tasks, skipped)。tasks = [(種類, 名稱, 指令清單, 完成標記, 簽章)];有完成標記且簽章相同的列入 skipped。"""
    root = Path(root)
    tasks, skipped = [], []
    for name in ENVS:
        sig, mark = env_sig(name), env_mark(root, name)
        (skipped.append(("env", name)) if done(mark, sig)
         else tasks.append(("env", name, env_steps(root, name), mark, sig)))
    for name in MODELS:
        sig, mark = model_sig(name), model_mark(root, name)
        (skipped.append(("model", name)) if done(mark, sig) and model_ok(root, name)
         else tasks.append(("model", name, model_steps(root, name), mark, sig)))
    pys = {ENVS[n]["py"] for kind, n, *_ in tasks if kind == "env"}
    pre = pre_steps(shutil.which("uv") is not None, _has_hf(), pys) if tasks else []
    return pre, tasks, skipped


# ------------------------------------------------------------ setup:執行
def _setup_env(root):
    """子行程環境:uv 快取放 tmp/(結束清掉);HF 下載走 tts_models;HOME 導到 tmp。"""
    root = Path(root)
    env = os.environ.copy()
    env.update(UV_CACHE_DIR=str(root / "tmp" / "uv_cache"), HF_HOME=str(root / "tts_models"),
               MODELSCOPE_CACHE=str(root / "tts_models"), PYTHONUTF8="1", UV_NO_PROGRESS="1",
               UV_LOCK_TIMEOUT="1800")   # 4 個環境平行裝、共用快取的大 wheel(nvidia-*)會互等,預設 300 秒會逾時(T6 實測)
    return env


def run_steps(steps, log_path, env):
    """依序跑指令,輸出附加到 log;回傳 (ok, 最後一個指令的 stdout 中 @@TORCH 那行)。"""
    probe = None
    with open(log_path, "a", encoding="utf-8") as f:
        for cmd in steps:
            f.write(f"$ {' '.join(map(str, cmd))}\n")
            f.flush()
            r = subprocess.run([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace", env=env)
            f.write(r.stdout)
            for line in r.stdout.splitlines():
                if line.startswith("@@TORCH "):
                    probe = json.loads(line[len("@@TORCH "):])
            if r.returncode:
                f.write(f"!! 結束碼 {r.returncode}\n")
                return False, probe
    return True, probe


def _run_task(root, task, env, gpu):
    kind, name, steps, mark, sig = task
    lp = Path(root) / "tmp" / "setup_logs" / (name + ".log" if kind == "env" else f"model_{name}.log")
    lp.write_text("", encoding="utf-8")
    # 沒有完成標記 = 上次沒裝完:環境整個重建(uv 快取還在,很快);CosyVoice clone 到一半(沒有 .git)也清掉重來
    stale = Path(root) / ENVS[name]["dir"] if kind == "env" else Path(root) / "tts_models" / "CosyVoice"
    if stale.exists() and (kind == "env" or (MODELS[name].get("git") and not (stale / ".git").is_dir())):
        shutil.rmtree(stale)
    ok, probe = run_steps(steps, lp, env)
    # HF 偶爾斷線(RemoteProtocolError):模型下載重試 2 次,snapshot_download 會續傳
    for n in range(2):
        if ok or kind != "model":
            break
        time.sleep(15 * (n + 1))
        with open(lp, "a", encoding="utf-8") as f:
            f.write(f"\n== 重試 {n + 1}\n")
        ok, probe = run_steps(steps, lp, env)
    msg = ""
    if kind == "env" and ok:
        if not probe:
            ok, msg = False, "驗證沒有輸出 torch 版本"
        elif gpu and not probe["cuda"]:
            ok, msg = False, f"torch {probe['torch']} 看不到 CUDA"
    if kind == "model" and ok and not model_ok(root, name):
        ok, msg = False, f"下載完找不到 {MODELS[name]['check']}"
    if ok:
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.write_text(sig, encoding="utf-8")
    log(f"{'完成' if ok else '失敗'} {kind} {name}{':' + msg if msg else ''}(log {lp})")
    return ok, probe


def env_probe(root, name):
    """已裝好的環境:問它的 torch 版本與 cuda。"""
    py = P.venv_python(Path(root) / ENVS[name]["dir"])
    if not py.exists():
        return None
    r = subprocess.run([str(py), "-c", env_steps(root, name)[-1][-1]], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("@@TORCH "):
            return json.loads(line[len("@@TORCH "):])
    return None


def clean_caches(root, env):
    for cmd in (["uv", "cache", "clean"], [sys.executable, "-m", "pip", "cache", "purge"]):
        if shutil.which(cmd[0]) or cmd[0] == sys.executable:
            subprocess.run(cmd, capture_output=True, env=env)
    shutil.rmtree(Path(root) / "tmp" / "uv_cache", ignore_errors=True)


def setup(root=None, dry_run=False, workers=8):
    root = Path(root or P.ROOT)
    pre, tasks, skipped = plan(root)
    for kind, name in skipped:
        log(f"跳過 {kind} {name}(已完成)")
    if dry_run:
        for cmd in pre:
            print("$", " ".join(map(str, cmd)))
        for kind, name, steps, mark, _ in tasks:
            print(f"# {kind} {name}(完成標記 {mark})")
            for cmd in steps:
                print("$", " ".join(map(str, cmd)))
        return 0
    if os.name == "nt":   # 會重建沒有完成標記的 tts_env_*:本機絕不能真的跑
        sys.exit("[colab] setup 只在 Colab/Linux 執行;本機只能 --dry-run")
    (root / "tmp" / "setup_logs").mkdir(parents=True, exist_ok=True)
    env = _setup_env(root)
    failed = []
    if pre:
        ok, _ = run_steps(pre, root / "tmp" / "setup_logs" / "_pre.log", env)
        if not ok:
            log(f"準備步驟失敗(uv / huggingface_hub / uv python install),見 {root / 'tmp' / 'setup_logs' / '_pre.log'}")
            return 1
    gpu = shutil.which("nvidia-smi") is not None
    probes = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {(t[0], t[1]): ex.submit(_run_task, root, t, env, gpu) for t in tasks}
        for (kind, name), fu in futs.items():
            ok, probe = fu.result()
            if not ok:
                failed.append(f"{kind} {name}")
            if kind == "env":
                probes[name] = probe
    print("\n== 安裝結果")
    for name in ENVS:
        pr = probes.get(name) or env_probe(root, name)
        print(f"  {ENVS[name]['dir']:18s} " + (f"torch {pr['torch']}  cuda={pr['cuda']}" if pr else "(無法驗證)"))
    for name in MODELS:
        print(f"  {name:22s} {'齊全' if model_ok(root, name) else '缺'}")
    if not failed:
        clean_caches(root, env)
    free = shutil.disk_usage(root).free / 2**30
    print(f"  硬碟剩餘 {free:.1f} GB")
    if failed:
        print("失敗:" + "、".join(failed) + f"(log 在 {root / 'tmp' / 'setup_logs'};修好後重跑 setup,已完成的會跳過)")
        return 1
    print("全部 OK")
    return 0


# ------------------------------------------------------------ tts
def resume_root():
    """續跑快取根目錄(<此目錄>/<tag>/):TTS_RESUME_DIR > Kaggle /kaggle/working/resume > Colab Drive/resume。"""
    env = os.environ.get("TTS_RESUME_DIR")
    return Path(env) if env else (KAGGLE_WORK / "resume" if platform() == "kaggle" else DRIVE / "resume")


def tts_gpus():
    """配音用幾張卡:CV_TTS_GPUS(預設 Kaggle 2、Colab 1)。>= 2 時兩張卡都露給 tts_cosy3,由它偵測卡數並分片(docs/tts.md §4.4)。"""
    try:
        return max(1, int(os.environ.get("CV_TTS_GPUS", "").strip() or (2 if platform() == "kaggle" else 1)))
    except ValueError:
        return 2 if platform() == "kaggle" else 1


def tts_shards(tag, root=None):
    """tts_cosy3 分片紀錄(build/<tag>/tts_cosy3/**/_cosy3_shards.json)依卡號加總 -> [dict(gpu, lines, tasks, minutes)];沒分片回 []。"""
    tot = {}
    for f in sorted(tts_dir(tag, root).rglob("_cosy3_shards.json")) if tts_dir(tag, root).is_dir() else []:
        try:
            shards = json.loads(f.read_text(encoding="utf-8")).get("shards") or []
        except (ValueError, OSError):
            continue
        for x in shards:
            t = tot.setdefault(x["gpu"], dict(gpu=x["gpu"], lines=0, tasks=0, minutes=0.0))
            for k in ("lines", "tasks", "minutes"):
                t[k] = round(t[k] + x.get(k, 0), 1) if k == "minutes" else t[k] + x.get(k, 0)
    return [tot[g] for g in sorted(tot)]


def tts_env():
    """配音子行程的環境變數。筆記本已設的(TTS_RESUME_DIR 等)沿用,沒設才給 Colab 預設。"""
    env = os.environ.copy()
    home = P.TMP / "colab_home"   # 套件在家目錄建快取:導到 tmp(本機 cosy3_worker / asr_worker 同做法)
    home.mkdir(parents=True, exist_ok=True)
    env.update(CLAUDE_VIDEO_ROOT=str(P.ROOT), PYTHONUTF8="1", HOME=str(home), USERPROFILE=str(home))
    for k, v in (("TTS_TS_DEVICE", "cuda"), ("TTS_ASR2_DEVICE", "cuda"), ("TTS_FA_DEVICE", "cuda"), ("TTS_RESUME_DIR", str(resume_root())),
                 ("TTS_RESUME_KEEP", "1")):
        env.setdefault(k, v)
    if os.name != "nt":   # faster-whisper(ctranslate2)找不到 venv 裡 pip 版 cuDNN 9 會 abort(-6):把 nvidia/*/lib 加進 LD_LIBRARY_PATH
        libs = sorted(str(d) for d in Path(P.TTS_ENV).parents[1].glob("lib/python3*/site-packages/nvidia/*/lib"))
        env["LD_LIBRARY_PATH"] = ":".join(libs + [x for x in [env.get("LD_LIBRARY_PATH")] if x])
        env.setdefault("MALLOC_ARENA_MAX", "2")   # glibc 多執行緒 arena 會把 RSS 撐大;4 個 torch 行程共用 12 GB

    if platform() == "kaggle" and tts_gpus() < 2:
        env.setdefault("CUDA_VISIBLE_DEVICES", "0")   # CV_TTS_GPUS=1:每個 Kaggle 核心各有自己的兩張 T4,這裡只是關掉分片
    return env   # CV_TTS_MAX_RETRY / CV_TTS_RATE_SEEDS 原樣傳下去:tts_cosy3 自己讀、夾到 1–12(env_limit)


def tts_cmd(tag):
    """與 make_version.py build()(--tts-review 配音步)同參數;--voice/--rate/--cosy-speed 進快取鍵,不可改。
    不帶 --clips auto / --max-per-src:只配音用不到選片段,而 Colab 沒有 projects/<tag>/clips_<tag>.json。"""
    return [str(P.TTS_ENV), "-X", "utf8", str(P.REPO / "pipeline" / "build.py"),
            "--script", f"{tag}/script.json", "--voice", "cosyB", "--rate", "+18%", "--gap", "0.12",
            "--section-gap", "0.30", "--tts-engine", "cosy3", "--tag", tag, "--tts-only", "--out", "colab"]


def tts(tag, tee=None):
    """凍結的片在本機 pack_for_colab 就擋掉了(Colab 沒有 projects/)。結束碼透傳。tee = 路徑:輸出同時印到 stdout 並存檔(Kaggle 摘要用)。"""
    for k in ("CV_TTS_MAX_RETRY", "CV_TTS_RATE_SEEDS"):
        if os.environ.get(k):
            log(f"{k}={os.environ[k]}(tts_cosy3 夾到 1–{RETRY_CAP})")
    log(" ".join(tts_cmd(tag)))
    if not tee:
        return subprocess.run(tts_cmd(tag), cwd=P.REPO, env=tts_env()).returncode
    Path(tee).parent.mkdir(parents=True, exist_ok=True)
    with open(tee, "a", encoding="utf-8") as f:
        p = subprocess.Popen(tts_cmd(tag), cwd=P.REPO, env=tts_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace")
        for line in p.stdout:
            print(line, end="", flush=True)
            f.write(line)
        return p.wait()


# ------------------------------------------------------------ status / clean / pack
def tts_dir(tag, root=None):
    return Path(root or P.ROOT) / "build" / tag / "tts_cosy3"


def _work(name):
    """底線開頭的工作檔(_cosy_work* _jobs.json _resume* 等)與 *.log:不打包、clean 會刪(底線開頭的只刪下列三種)。"""
    return name.startswith("_") or name.endswith(".log")


def unit_counts(tag, root=None):
    """-> dict(passed, failed, no_key, jobs_left, jobs)。單位 = <stem>.qc.json;passed/failed 只算 .key 也在的。"""
    d = tts_dir(tag, root)
    out = dict(passed=0, failed=0, no_key=0, jobs_left=0, jobs=0)
    if not d.is_dir():
        return out
    for qf in d.glob("*.qc.json"):
        stem = qf.name[:-len(".qc.json")]
        if not (d / f"{stem}.key").exists():
            out["no_key"] += 1
            continue
        try:
            ok = json.loads(qf.read_text(encoding="utf-8")).get("passed")
        except (OSError, ValueError):
            ok = None
        out["passed" if ok else "failed"] += 1
    jf = d / "_jobs.json"
    if jf.exists():
        jobs = json.loads(jf.read_text(encoding="utf-8"))
        out["jobs"] = len(jobs)
        out["jobs_left"] = sum(1 for j in jobs if not (d / Path(j["out"].replace("\\", "/")).name).with_suffix(".qc.json").exists())
    return out


def resume_status(tag):
    """續跑快取筆數/MB:用 tts_cosy3 --resume-status(環境還沒裝好就自己數,算法相同)。"""
    d = resume_root() / tag
    if P.TTS_ENV.exists():
        r = subprocess.run([str(P.TTS_ENV), "-X", "utf8", str(PIPE / "tts_cosy3.py"), "--resume-status", str(d)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=P.REPO)
        line = [ln for ln in r.stdout.splitlines() if ln.startswith("[resume]")]
        if line:
            return line[-1]
    fs = list(d.rglob("*.wav")) if d.exists() else []
    return f"[resume] {d}: {len(fs)} 筆嘗試,{sum(f.stat().st_size for f in fs) / 2**20:.1f} MB"


def status(tag, root=None, resume=True):
    c = unit_counts(tag, root)
    print(f"[status] {tag}:已完成 {c['passed'] + c['failed']} 個單位(通過 {c['passed']}、未過 {c['failed']});"
          f"有品管紀錄但還沒 .key {c['no_key']}")
    print(f"[status] _jobs.json:" + (f"{c['jobs']} 個,還剩 {c['jobs_left']} 個沒做" if c["jobs"] else "無(沒有進行中的批次)"))
    if resume:
        print(resume_status(tag))
    return c


def clean(tag, root=None, resume=False):
    """刪 _cosy_work*、_jobs.json、*.log(不刪音檔與 qc);resume=True 連 <TTS_RESUME_DIR>/<tag> 一起刪(打包回 Drive 後)。"""
    d, n = tts_dir(tag, root), 0
    if d.is_dir():
        for f in list(d.iterdir()):
            if f.name.startswith("_cosy_work") or f.name == "_jobs.json" or f.name.endswith(".log"):
                shutil.rmtree(f) if f.is_dir() else f.unlink()
                n += 1
    log(f"clean {tag}:刪 {n} 個工作檔")
    if resume:
        rd = resume_root() / tag
        if rd.exists():
            shutil.rmtree(rd)
            log(f"刪續跑快取 {rd}")
    return n


def pack_files(tag, root=None):
    """-> [(實際路徑, zip 內路徑)]:build/<tag>/tts_cosy3/**(排除底線開頭的工作檔/目錄與 *.log)+ build/<tag>/tts_qc.json。"""
    root = Path(root or P.ROOT)
    d, out = tts_dir(tag, root), []
    if d.is_dir():
        for dp, dns, fns in os.walk(d):
            dns[:] = sorted(x for x in dns if not _work(x))
            for fn in sorted(fns):
                if not _work(fn):
                    f = Path(dp) / fn
                    out.append((f, f.relative_to(root).as_posix()))
    qc = root / "build" / tag / "tts_qc.json"
    if qc.exists():
        out.append((qc, qc.relative_to(root).as_posix()))
    return out


def pack(tag, root=None, drive=None):
    """-> zip 路徑。先寫 .part 再改名:打包到一半斷線不會在 Drive 留下壞檔。"""
    files = pack_files(tag, root)
    if not files:
        sys.exit(f"[colab] build/{tag}/tts_cosy3 沒有東西可打包")
    drive = Path(drive or DRIVE)
    drive.mkdir(parents=True, exist_ok=True)
    out = drive / f"tts_{tag}.zip"
    part = out.with_name(out.name + ".part")
    with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
        for f, arc in files:
            z.write(f, arc)
    os.replace(part, out)
    log(f"{out}:{len(files)} 個檔,{out.stat().st_size / 2**20:.1f} MB")
    return out


# ------------------------------------------------------------ 接上先前做好的配音(Colab 筆記本 1b 格、Kaggle 掛回共用)
def apply_tts_zip(tag, zip_path, root=None):
    """把 tts_<tag>.zip 的 build/<tag>/** 解到素材根;沒通過品管的單位刪 .key(下次 build 不命中、重錄,同 tts_cosy3 --requal),
    通過的照常沿用。-> (解出幾個檔, 要重錄的單位 stem 清單)。"""
    root = Path(root or P.ROOT)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():   # 只收 build/<tag>/ 底下的檔(擋絕對路徑與 ..)
            parts = info.filename.replace("\\", "/").split("/")
            if info.is_dir() or info.filename.startswith("/") or ".." in parts or len(parts) < 3 \
                    or parts[0] != "build" or parts[1] != tag:
                continue
            z.extract(info, root)
            n += 1
    redo = []
    for qf in sorted((root / "build" / tag / "tts_cosy3").glob("**/*.qc.json")):
        try:
            passed = json.loads(qf.read_text(encoding="utf-8")).get("passed")
        except (OSError, ValueError):
            continue
        if passed is False:
            key = qf.with_name(qf.name[:-len(".qc.json")] + ".key")
            if key.exists():
                key.unlink()
                redo.append(qf.name[:-len(".qc.json")])
    return n, redo


# ------------------------------------------------------------ Kaggle:批次執行(kaggle-main)
def find_input_zip(tag, input_root=None):
    """/kaggle/input 下遞迴找 colab_<tag>.zip(Dataset 掛載路徑結構不固定);多個取最新。找不到 -> None。"""
    env = os.environ.get("CV_KAGGLE_INPUT_ZIP")   # K3 啟動稿指定(Dataset 被自動解開時它會在 /tmp 重打包):存在且是檔就用
    if env and Path(env).is_file():
        return Path(env)
    hits = sorted(Path(input_root or KAGGLE_INPUT).glob(f"**/colab_{tag}.zip"), key=lambda f: f.stat().st_mtime)
    return hits[-1] if hits else None


def extract_input(zip_path, root=None):
    """輸入 zip 解到素材根;同一個 zip(大小+mtime)已解過就跳過。-> 是否真的解了。"""
    root = Path(root or P.ROOT)
    zip_path = Path(zip_path)
    st = zip_path.stat()
    stamp, mark = f"{st.st_size}-{int(st.st_mtime)}", root / ".cv_zip"
    if mark.is_file() and mark.read_text(encoding="utf-8") == stamp:
        return False
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(root)
    mark.write_text(stamp, encoding="utf-8")
    return True


def mount_resume(tag, input_root=None, work=None, root=None):
    """上一次本片的輸出經 kernel_sources 掛回 /kaggle/input/notebooks/<帳號>/<slug>/:
    resume/<tag>/ 複製到 <work>/resume/<tag>/(之後的續跑與輸出都在 working);同處的 tts_<tag>.zip(多個取最新)先套用。
    -> dict(resume_from=[來源], tts_zip=路徑或 None, files=解出檔數, redo=[stem])。"""
    base, work = Path(input_root or KAGGLE_INPUT) / "notebooks", Path(work or KAGGLE_WORK)
    cands = sorted(d for d in base.glob("*/*") if d.is_dir())
    prev = os.environ.get("CV_KAGGLE_PREV_RESUME")   # K3 啟動稿指定的 .../resume/<tag>;同層上兩級有 tts_<tag>.zip 一併套用
    if prev and Path(prev).is_dir():
        cands = [Path(prev).parent.parent]
    out = dict(resume_from=[], tts_zip=None, files=0, redo=[])
    for d in cands:
        if (d / "resume" / tag).is_dir():
            shutil.copytree(d / "resume" / tag, work / "resume" / tag, dirs_exist_ok=True)
            out["resume_from"].append(str(d / "resume" / tag))
    zips = sorted((d / f"tts_{tag}.zip" for d in cands if (d / f"tts_{tag}.zip").is_file()), key=lambda f: f.stat().st_mtime)
    if zips:
        out["tts_zip"] = str(zips[-1])
        out["files"], out["redo"] = apply_tts_zip(tag, zips[-1], root)
    return out


def qc_summary(tag, root=None):
    """build/<tag>/tts_qc.json -> dict(passed, checked, failed=[idx]);沒有檔 -> None。"""
    f = Path(root or P.ROOT) / "build" / tag / "tts_qc.json"
    try:
        q = json.loads(f.read_text(encoding="utf-8"))
        return dict(passed=q["passed"], checked=q["checked"], failed=[x["idx"] for x in q.get("failed", [])])
    except (OSError, ValueError, KeyError):
        return None


def _tail(path, n):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").replace("\r", "\n").splitlines()[-n:]
    except OSError:
        return []


def write_summaries(work, root, step, tee=None):
    """setup / tts 的 log 摘要寫進 <work>/logs/(輸出目錄,下載得到)。"""
    ld = Path(work) / "logs"
    ld.mkdir(parents=True, exist_ok=True)
    if step == "setup":
        lines = []
        for f in sorted((Path(root) / "tmp" / "setup_logs").glob("*.log")):
            lines += [f"== {f.name}"] + [x[:300] for x in _tail(f, 15)]
        (ld / "setup_summary.txt").write_text("\n".join(lines), encoding="utf-8")
    elif step == "tts" and tee:
        (ld / "tts_summary.txt").write_text("\n".join(x[:300] for x in _tail(tee, 120)), encoding="utf-8")


def _self_in_root(root):
    return Path(__file__).resolve() == (Path(root) / "pipeline" / "colab" / "colab_run.py").resolve()


def _dir_mb(d):
    return round(sum(f.stat().st_size for f in Path(d).rglob("*") if f.is_file()) / 2**20, 1) if Path(d).is_dir() else 0.0


def kaggle_main(tag, root=None, work=None, input_root=None):
    """Kaggle 批次:prepare(找輸入 zip、解壓、掛回續跑)-> setup -> tts -> pack。每步結束寫 <work>/run_status.json
    {tag, state, step, rc, minutes, steps[], qc, resume_mb};任一步非 0 就停(rc 寫進 status)。-> 結束碼。"""
    root, work = Path(root or P.ROOT), Path(work or KAGGLE_WORK)
    work.mkdir(parents=True, exist_ok=True)
    st = dict(tag=tag, platform=platform(), state="running", step="prepare", rc=None, minutes=0.0, steps=[], qc=None)
    sf = work / "run_status.json"
    t_all = time.time()

    def save():
        st["resume_mb"] = _dir_mb(work / "resume" / tag)
        st["total_minutes"] = round((time.time() - t_all) / 60, 1)
        sf.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")

    def prepare():
        zp = find_input_zip(tag, input_root)
        if zp is None:
            print(f"[kaggle] 找不到 colab_{tag}.zip(找過 {input_root or KAGGLE_INPUT})")
            return 2
        print(f"[kaggle] 輸入 {zp}:{'已解壓到' if extract_input(zp, root) else '已解過,沿用'} {root}")
        m = mount_resume(tag, input_root, work, root)
        print(f"[kaggle] 掛回續跑:快取來源 {len(m['resume_from'])} 處;tts zip {m['tts_zip'] or '無'}"
              f"(沿用 {m['files']} 檔,重錄 {len(m['redo'])} 句)")
        return 0

    tee = root / "tmp" / f"tts_{tag}.log"
    steps = [("prepare", prepare),
             ("setup", lambda: setup(root)),
             ("tts", lambda: tts(tag, tee=tee)),
             ("pack", lambda: (pack(tag, root, work), 0)[1])]
    for name, fn in steps:
        st.update(step=name, rc=None)
        save()
        print(f"[kaggle] === 步驟 {name} 開始", flush=True)
        t0 = time.time()
        try:
            rc = fn() or 0
        except SystemExit as e:   # setup/pack 失敗時 sys.exit(訊息)
            print(f"[kaggle] {e}")
            rc = e.code if isinstance(e.code, int) and e.code else 1
        except Exception as e:  # noqa: BLE001 批次沒人看:任何例外都要落進 status
            print(f"[kaggle] {name} 例外:{type(e).__name__}: {e}")
            rc = 1
        mins = round((time.time() - t0) / 60, 1)
        write_summaries(work, root, name, tee)
        st["steps"].append(dict(name=name, step=name, rc=rc, minutes=mins))
        if name == "tts" and tts_shards(tag, root):   # 新欄位:每片句數/工作數/分鐘(單 GPU 不寫)
            st["steps"][-1]["shards"] = tts_shards(tag, root)
        st.update(step=name, rc=rc, minutes=mins, qc=qc_summary(tag, root))
        if name == "prepare" and rc == 0 and not os.environ.get("CV_KAGGLE_REEXEC") and not _self_in_root(root):
            # 跑的是 Dataset 裡的 colab_run.py,tts_cmd 要用解壓後素材根裡的 pipeline/:換那份重跑整個 kaggle-main
            child = [sys.executable, "-X", "utf8", str(root / "pipeline" / "colab" / "colab_run.py"), "kaggle-main", tag]
            print("[kaggle] 換用解壓後的 colab_run.py:" + " ".join(child), flush=True)
            return subprocess.run(child, env={**os.environ, "CV_KAGGLE_REEXEC": "1", "CLAUDE_VIDEO_ROOT": str(root)}).returncode
        print(f"[kaggle] === 步驟 {name} 結束 rc={rc}({mins} 分)" + (f";品管 {st['qc']}" if st["qc"] else ""), flush=True)
        if rc:
            st["state"] = "failed"
            save()
            return rc
        save()
    st["state"] = "done"
    save()
    print(f"[kaggle] 全部完成:{work / ('tts_' + tag + '.zip')};品管 {st['qc']}(狀態 {sf})")
    return 0


# ------------------------------------------------------------ 主程式
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--dry-run", action="store_true", help="只印要跑的指令(含跳過哪些),不執行")
    for name in ("tts", "status", "pack", "kaggle-main"):
        sub.add_parser(name).add_argument("tag")
    c = sub.add_parser("clean")
    c.add_argument("tag")
    c.add_argument("--resume", action="store_true", help="連續跑快取 <TTS_RESUME_DIR>/<tag> 一起刪")
    a = ap.parse_args(argv)
    if a.cmd == "setup":
        return setup(dry_run=a.dry_run)
    if a.cmd == "tts":
        return tts(a.tag)
    if a.cmd == "kaggle-main":
        return kaggle_main(a.tag)
    if a.cmd == "status":
        status(a.tag)
    elif a.cmd == "clean":
        clean(a.tag, resume=a.resume)
    elif a.cmd == "pack":
        pack(a.tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
