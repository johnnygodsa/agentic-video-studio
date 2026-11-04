r"""跨環境合成:各引擎都用常駐子行程(模型只載一次),協定同 cosy3_worker.py:載入完成 stdout 印 `@@READY {json}`,
stdin 每行一個 JSON 工作,stdout 回 `@@RES {json}`;其他輸出走 stderr(導到 log 檔)。
  cosy3     tts_env_cosy3\Scripts\python.exe  pipeline\cosy3_worker.py(既有,不改)  工作 {text, seed, speed, out}
  indextts2 tts_env_indextts2\Scripts\python.exe pipeline\tts_bakeoff\indextts2_worker.py 工作 {text, seed, out[, target_sec]}
每句記牆鐘秒數;顯存 = 子行程回報的 torch 峰值 與 nvidia-smi 取樣(扣掉開跑前基線)取大者。
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))
import paths as P  # noqa: E402

ENGINES = ("cosy3", "indextts2", "breezy", "breezy_ann")
BREEZY = ("breezy", "breezy_ann")
TEXT_KEY = {"cosy3": "engine", "indextts2": "itext", "breezy": "btext", "breezy_ann": "bann"}   # 語料欄位:各引擎送哪一份文字
COSY_ENV = P.ROOT / "tts_env_cosy3" / "Scripts" / "python.exe"
INDEX_ENV = P.ROOT / "tts_env_indextts2" / "Scripts" / "python.exe"
INDEX_MODEL = P.TTS_MODELS / "IndexTTS2"            # checkpoints(config.yaml、gpt.pth、s2mel.pth…)
INDEX_REPO = P.TTS_MODELS / "index-tts"             # index-tts 原始碼(git clone;已 pip install -e 進 env 時可不存在)
INDEX_HF = INDEX_MODEL / "hf_cache"                 # IndexTTS2 執行時另抓的 w2v-bert / MaskGCT / campplus / BigVGAN
BREEZY_ENV = P.ROOT / "tts_env_breezy" / "Scripts" / "python.exe"
BREEZY_MODEL = P.TTS_MODELS / "BreezyVoice-300M"    # HF MediaTek-Research/BreezyVoice-300M(llm/flow/hift.pt、campplus.onnx、speech_tokenizer_v1.onnx…)
BREEZY_REPO = P.TTS_MODELS / "BreezyVoice"          # github mtkresearch/BreezyVoice 原始碼(git clone;不 pip install)
BREEZY_CACHE = P.TTS_MODELS / "BreezyVoice_cache"   # HF_HOME / TORCH_HOME / MODELSCOPE_CACHE、g2pW 模型(G2PWModel,v2-onnx)
BREEZY_G2PW = BREEZY_CACHE / "G2PWModel"
BREEZY_WETEXT = P.TTS_MODELS / "hub" / "pengzhendong" / "wetext"   # 唯讀:wetext 本機快取(cosy3 同一份)
COSY_SPEED = 1.18                                   # 同出片(make_version / tts_cosy3 預設)
SEED = 2024


def env_python(engine):
    return COSY_ENV if engine == "cosy3" else BREEZY_ENV if engine in BREEZY else INDEX_ENV


def worker_cmd(engine, ref, ref_text, opts=None):
    """子行程指令。opts(indextts2):fp16、dur_kwarg、dur_unit、tokens_per_sec、device。"""
    opts = opts or {}
    if engine in BREEZY:
        return [str(BREEZY_ENV), "-X", "utf8", str(HERE / "breezy_worker.py"), "--ref", str(ref), "--ref-text", str(ref_text),
                "--model-dir", str(BREEZY_MODEL), "--repo", str(BREEZY_REPO), "--g2pw-dir", str(BREEZY_G2PW),
                "--wetext-dir", str(BREEZY_WETEXT), "--device", opts.get("device", "cuda")]
    if engine == "cosy3":
        return [str(COSY_ENV), "-X", "utf8", str(PIPE / "cosy3_worker.py"), "--ref", str(ref), "--ref-text", str(ref_text),
                "--device", opts.get("device", "cuda")]
    cmd = [str(INDEX_ENV), "-X", "utf8", str(HERE / "indextts2_worker.py"), "--ref", str(ref), "--ref-text", str(ref_text),
           "--model-dir", str(INDEX_MODEL), "--repo", str(INDEX_REPO), "--device", opts.get("device", "cuda")]
    if not opts.get("fp16", True):
        cmd.append("--no-fp16")
    for k in ("dur_kwarg", "dur_unit", "tokens_per_sec"):
        if opts.get(k) is not None:
            cmd += ["--" + k.replace("_", "-"), str(opts[k])]
    return cmd


def worker_env(engine):
    env = os.environ.copy()
    home = P.TMP / ("cosy_home" if engine == "cosy3" else "breezy_home" if engine in BREEZY else "indextts2_home")   # 套件在家目錄建快取:導到 tmp,不寫 C 槽
    home.mkdir(parents=True, exist_ok=True)
    env.update(USERPROFILE=str(home), HOME=str(home), TEMP=str(P.TMP), TMP=str(P.TMP), PYTHONPATH=str(PIPE),
               PYTHONIOENCODING="utf-8")
    if engine in BREEZY:   # BreezyVoice 的 utils/ 等短名套件不可被 pipeline 的模組蓋過:不帶 PYTHONPATH
        env.pop("PYTHONPATH", None)
        env.update(HF_HOME=str(BREEZY_CACHE), TORCH_HOME=str(BREEZY_CACHE / "torch"), MODELSCOPE_CACHE=str(BREEZY_CACHE / "modelscope"),
                   APPDATA=str(home / "AppData" / "Roaming"), LOCALAPPDATA=str(home / "AppData" / "Local"), PYTHONUTF8="1")
    elif engine == "indextts2":
        env.update(HF_HOME=str(INDEX_HF), TORCH_HOME=str(INDEX_HF / "torch"), MODELSCOPE_CACHE=str(INDEX_HF / "modelscope"))
    else:
        env.setdefault("HF_HOME", str(P.TTS_MODELS))
        env.setdefault("MODELSCOPE_CACHE", str(P.TTS_MODELS))
    return env


class Worker:
    """常駐子行程客戶端。ready = @@READY 的內容(加 load_s);call(**job) -> @@RES 內容(加 sec = 牆鐘秒數)。"""

    def __init__(self, cmd, env, log_path):
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        self.log_path = log_path
        self.log = open(log_path, "w", encoding="utf-8")
        t0 = time.time()
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True,
                                  encoding="utf-8", env=env, cwd=str(P.REPO))
        self.ready = self._read("@@READY")
        self.ready["load_s"] = round(time.time() - t0, 1)

    def _read(self, tag):
        for line in self.p.stdout:
            if line.startswith(tag + " "):
                return json.loads(line[len(tag) + 1:])
        raise RuntimeError(f"子行程中止(結束碼 {self.p.poll()}),見 {self.log_path}")

    def call(self, **job):
        t0 = time.time()
        self.p.stdin.write(json.dumps(job, ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        res = self._read("@@RES")
        res.setdefault("sec", round(time.time() - t0, 3))
        res["wall_s"] = round(time.time() - t0, 3)
        return res

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=60)
        except Exception:  # noqa: BLE001  關不掉就砍
            self.p.kill()
        self.log.close()


class VramSampler(threading.Thread):
    """每 interval 秒呼叫 used()(MiB 或 None),記最大值;stop() 後讀 peak。"""

    def __init__(self, used, interval=1.0):
        super().__init__(daemon=True)
        self.used, self.interval, self.peak, self._stop_ev = used, interval, None, threading.Event()

    def run(self):
        while not self._stop_ev.is_set():
            try:
                v = self.used()
            except Exception:  # noqa: BLE001
                v = None
            if v is not None:
                self.peak = v if self.peak is None else max(self.peak, v)
            self._stop_ev.wait(self.interval)

    def stop(self):
        self._stop_ev.set()
        self.join(timeout=5)
        return self.peak


def torch_peak(res):
    """子行程回報的 torch 峰值(MiB):indextts2 = reserved/allocated 取大;cosy3_worker = vram_mib(max_memory_reserved)。"""
    vals = [res.get(k) for k in ("vram_reserved_mib", "vram_alloc_mib", "vram_mib")]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def run_batch(engine, items, out_dir, cmd, env, log_path, rows_path, gpu_used=None, seed=SEED, targets=None,
              text_key=None, speed=COSY_SPEED, worker_cls=Worker, on_row=None):
    """合成一批:已有輸出且 rows_path 有紀錄的句子略過(可續跑)。targets = {n: 目標秒數}(indextts2 時長控制)。
    -> summary dict(engine, load_s, ready, baseline_mib, smi_peak_mib, smi_delta_mib, torch_peak_mib, vram_peak_mib, n_ok, n_fail, crashed)。"""
    from tts_bakeoff import corpus as C
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    done = {r["n"] for r in C.read_jsonl(rows_path) if r.get("ok") and (out_dir / f"{r['n']}.wav").exists()}
    todo = [x for x in items if x["n"] not in done and (targets is None or x["n"] in targets)]
    text_key = text_key or TEXT_KEY.get(engine, "itext")
    base = gpu_used() if gpu_used else None
    sampler = VramSampler(gpu_used) if gpu_used else None
    if sampler:
        sampler.start()
    summ = dict(engine=engine, baseline_mib=base, todo=len(todo), skipped=len(done), n_ok=0, n_fail=0, crashed=None,
                torch_peak_mib=None, targets=targets is not None)
    w = None
    try:
        if not todo:
            return summ
        w = worker_cls(cmd, env, log_path)
        summ.update(load_s=w.ready.get("load_s"), ready=w.ready)
        summ["torch_peak_mib"] = torch_peak(w.ready)
        with open(rows_path, "a", encoding="utf-8") as rf:
            for x in todo:
                out = out_dir / f"{x['n']}.wav"
                job = dict(text=x[text_key], seed=seed, out=str(out))
                if engine == "cosy3":
                    job["speed"] = speed
                if targets is not None:
                    job["target_sec"] = targets[x["n"]]
                try:
                    res = w.call(**job)
                except RuntimeError as e:   # 子行程死掉(多半 OOM)
                    summ["crashed"] = str(e)
                    break
                row = dict(n=x["n"], ok=bool(res.get("ok")), dur=res.get("dur"), sec=res.get("sec"), wall_s=res.get("wall_s"),
                           torch_mib=torch_peak(res), err=res.get("err"), target_sec=job.get("target_sec"),
                           dur_used=res.get("dur_used"), final_text=res.get("final_text"))
                summ["n_ok" if row["ok"] else "n_fail"] += 1
                tp = row["torch_mib"]
                if tp is not None:
                    summ["torch_peak_mib"] = tp if summ["torch_peak_mib"] is None else max(summ["torch_peak_mib"], tp)
                rf.write(json.dumps(row, ensure_ascii=False) + "\n")
                rf.flush()
                if on_row:
                    on_row(row)
    finally:
        if w:
            w.close()
        if sampler:
            summ["smi_peak_mib"] = sampler.stop()
            if summ["smi_peak_mib"] is not None and base is not None:
                summ["smi_delta_mib"] = summ["smi_peak_mib"] - base
        cands = [v for v in (summ.get("torch_peak_mib"), summ.get("smi_delta_mib")) if v is not None]
        summ["vram_peak_mib"] = max(cands) if cands else None
    return summ
