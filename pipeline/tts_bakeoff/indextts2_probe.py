#!/usr/bin/env python3
r"""T1 配音引擎比武第 1 步:IndexTTS2 冷啟量測探針(tts_env_indextts2 執行;channel/_archive/plans/PLAN_工具升級_2026-10-26.md T1)。

量:模型載入秒數;載入後與合成期間顯存峰值兩種(torch.cuda.max_memory_reserved/allocated,與背景執行緒每 0.2 秒
pynvml/nvidia-smi 取整卡已用 MiB(扣開跑前基線)與本行程 MiB(WDDM 下多半查不到 = null));每句合成秒數、音檔秒數、RTF、
該句期間顯存峰值;第一句標「冷啟首句」。CUDA OOM 與其他例外逐句記進 json,不讓行程靜默死掉;每句寫完就落檔。
語料:build\<tag>\tts_qc.json(預設 = 最新修改的那份)取 n 句(含最長句,其餘依長度平均取);送引擎文字 = 該句紀錄的
engine_text(tts_cosy3.engine_text = tts_cosy_text 處理後的同一份;缺時用 tts_cosy_text.pron_text 重算),
其中 CosyVoice3 拼音 token([q][í])換成 IndexTTS2 的拼音聲調寫法(qi2),其餘原樣。
GPU:開模型前照 pipeline\gpu_lock.py 排隊(tag t1_bakeoff;board 沒有發片日 = 排在有日期的工作之後),結束(含例外)釋放。
不開 deepspeed、use_cuda_kernel=False;QwenEmotion(情緒文字模型)預設不載(比武不用情緒文字;--qwen-emo 才載)。
暫存/快取一律導到 D 槽(HF_HOME、HF_HUB_CACHE、TORCH_HOME、MODELSCOPE_CACHE、TMP 等,本檔開頭強制設定),預設離線(HF_HUB_OFFLINE=1)。

用法:tts_env_indextts2\Scripts\python.exe -X utf8 pipeline\tts_bakeoff\indextts2_probe.py [--fp16|--fp32] [--n 10] [--tag <tag>] [--out json]
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time
import traceback
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
sys.path.insert(0, str(PIPE))
import paths as P  # noqa: E402

MODEL_DIR = P.TTS_MODELS / "IndexTTS-2"
REPO_DIR = P.TTS_MODELS / "index-tts"
OUT_DIR = P.TMP / "tts_bakeoff"
LOCK_TAG, LOCK_JOB = "t1_bakeoff", "indextts2_probe"
POLL_S = 0.2


def set_cache_env(offline=True):
    """所有快取與暫存導到 D 槽(repo 的 tts_models\\ 與 tmp\\);在 import torch/transformers 前呼叫。"""
    tmp = P.TMP / "indextts2_tmp"
    env = {
        "HF_HOME": MODEL_DIR / "hf_home", "HF_HUB_CACHE": MODEL_DIR / "hf_home" / "hub",
        "TORCH_HOME": P.TTS_MODELS / "torch_home", "MODELSCOPE_CACHE": P.TTS_MODELS / "modelscope_cache",
        "NLTK_DATA": P.TTS_MODELS / "nltk_data", "MPLCONFIGDIR": tmp / "mpl", "XDG_CACHE_HOME": tmp / "xdg",
        "NUMBA_CACHE_DIR": tmp / "numba", "TMP": tmp, "TEMP": tmp, "TMPDIR": tmp,
    }
    for k, v in env.items():
        Path(v).mkdir(parents=True, exist_ok=True)
        os.environ[k] = str(v)
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import tempfile
    tempfile.tempdir = str(tmp)


# ------------------------------------------------------------ 語料
INITIALS = {"zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "j", "q", "x", "r", "z", "c", "s", "y", "w"}
_TONES = {}
for _base, _marks in (("a", "āáǎà"), ("e", "ēéěè"), ("i", "īíǐì"), ("o", "ōóǒò"), ("u", "ūúǔù"), ("v", "ǖǘǚǜ")):
    for _n, _c in enumerate(_marks, 1):
        _TONES[_c] = (_base, _n)
COSY_SEQ = re.compile(r"(?:\[[^\[\]\s]+\])+")


def _syllable(s):
    """'qí' -> 'qi2';無聲調符號 = 輕聲 5;ü -> v。"""
    tone, out = 5, []
    for ch in s:
        if ch in _TONES:
            b, tone = _TONES[ch]
            out.append(b)
        else:
            out.append("v" if ch == "ü" else ch)
    return "".join(out) + str(tone)


def cosy_to_index(text):
    """CosyVoice3 拼音 token 串([x][ì][j][iǎo])-> IndexTTS2 拼音聲調(xi4jiao3);聲母 token 與下一個韻母 token 合成一個音節。"""
    def conv(m):
        toks, out, ini = re.findall(r"\[([^\[\]\s]+)\]", m.group(0)), [], ""
        for t in toks:
            if t in INITIALS and not ini:
                ini = t
                continue
            out.append(_syllable(ini + t))
            ini = ""
        if ini:
            out.append(ini)
        return "".join(out)
    return COSY_SEQ.sub(conv, text)


def latest_qc(tag=None):
    if tag:
        return P.BUILD / tag / "tts_qc.json"
    cands = sorted(P.BUILD.glob("*/tts_qc.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for c in cands:
        try:
            if json.loads(c.read_text(encoding="utf-8")).get("records"):
                return c
        except (OSError, ValueError):
            continue
    sys.exit("找不到有 records 的 build\\<tag>\\tts_qc.json")


def pick_corpus(qc_path, n):
    """取 n 句:最長句必選,其餘依 measure_text 長度排序後平均取(長短混合);回傳依原 idx 排序。"""
    recs = [r for r in json.loads(qc_path.read_text(encoding="utf-8"))["records"] if (r.get("measure_text") or r.get("text"))]
    recs.sort(key=lambda r: len(r.get("measure_text") or r["text"]))
    if len(recs) <= n:
        chosen = recs
    else:
        idx = {len(recs) - 1} | {round(i * (len(recs) - 1) / (n - 1)) for i in range(n)} if n > 1 else {len(recs) - 1}
        k = 0
        while len(idx) < n:  # 四捨五入撞號時補滿
            if k not in idx:
                idx.add(k)
            k += 1
        chosen = [recs[i] for i in sorted(idx)]
    longest = max(len(r.get("measure_text") or r["text"]) for r in chosen)
    out = []
    for r in sorted(chosen, key=lambda r: float(r.get("idx") or 0)):  # idx 可能是 '9.1' 這類子句編號
        cosy = r.get("engine_text")
        src = "qc.engine_text"
        if not cosy:
            import tts_cosy_text as CT
            cosy, _ = CT.pron_text(r["text"])
            src = "tts_cosy_text.pron_text"
        mt = r.get("measure_text") or r["text"]
        out.append(dict(idx=r.get("idx"), measure_text=mt, cosy_engine_text=cosy, text_source=src,
                        engine_text=cosy_to_index(cosy), chars=len(mt), longest=len(mt) == longest))
    return out


# ------------------------------------------------------------ 顯存監看
class VramMonitor(threading.Thread):
    """每 POLL_S 秒取整卡已用 MiB 與本行程 MiB;peak 為整段峰值,window 為 reset_window 之後的峰值。"""

    def __init__(self):
        super().__init__(daemon=True)
        self.pid, self.stop_ev = os.getpid(), threading.Event()
        self.nvml = self._init_nvml()
        self.backend = "pynvml" if self.nvml else "nvidia-smi"
        self.baseline = None
        self.lock = threading.Lock()
        self.peak = dict(card=None, proc=None)
        self.win = dict(card=None, proc=None)
        self.samples, self.errors = 0, 0

    @staticmethod
    def _init_nvml():
        try:
            import pynvml
            pynvml.nvmlInit()
            return pynvml, pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:  # noqa: BLE001  沒裝 nvidia-ml-py 或驅動不給 -> 改用 nvidia-smi
            return None

    def read(self):
        """回傳 (整卡已用 MiB, 本行程 MiB 或 None)。"""
        if self.nvml:
            nv, h = self.nvml
            card = nv.nvmlDeviceGetMemoryInfo(h).used // 2**20
            proc = None
            try:
                for p in nv.nvmlDeviceGetComputeRunningProcesses(h):
                    if p.pid == self.pid and p.usedGpuMemory:
                        proc = p.usedGpuMemory // 2**20
            except Exception:  # noqa: BLE001
                pass
            return int(card), proc
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=5)
        card = int(r.stdout.split()[0])
        proc = None
        r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            parts = [x.strip() for x in line.split(",")]
            if len(parts) == 2 and parts[0] == str(self.pid) and parts[1].isdigit():
                proc = int(parts[1])
        return card, proc

    def set_baseline(self):
        self.baseline = self.read()[0]
        return self.baseline

    def reset_window(self):
        with self.lock:
            self.win = dict(card=None, proc=None)

    def window(self):
        with self.lock:
            return self._fmt(self.win)

    def overall(self):
        with self.lock:
            return self._fmt(self.peak)

    def _fmt(self, d):
        card = d["card"]
        return dict(card_used_mib=card, card_delta_mib=(card - self.baseline) if card is not None and self.baseline is not None else None,
                    proc_mib=d["proc"])

    def run(self):
        while not self.stop_ev.is_set():
            t = time.perf_counter()
            try:
                card, proc = self.read()
                with self.lock:
                    self.samples += 1
                    for d in (self.peak, self.win):
                        d["card"] = card if d["card"] is None else max(d["card"], card)
                        if proc is not None:
                            d["proc"] = proc if d["proc"] is None else max(d["proc"], proc)
            except Exception:  # noqa: BLE001
                self.errors += 1
            self.stop_ev.wait(max(0.0, POLL_S - (time.perf_counter() - t)))


def torch_peaks(torch):
    return dict(max_reserved_mib=round(torch.cuda.max_memory_reserved() / 2**20),
                max_allocated_mib=round(torch.cuda.max_memory_allocated() / 2**20))


def wav_seconds(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def err_summary(e):
    return f"{type(e).__name__}: {str(e).strip().splitlines()[0][:300] if str(e).strip() else ''}"


# ------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser(description="IndexTTS2 冷啟量測探針(T1 第 1 步)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--fp16", dest="fp16", action="store_true", default=True, help="半精度(預設)")
    g.add_argument("--fp32", dest="fp16", action="store_false", help="全精度")
    ap.add_argument("--n", type=int, default=10, help="句數(預設 10)")
    ap.add_argument("--tag", help="語料來源 build\\<tag>\\tts_qc.json(預設最新修改的那份)")
    ap.add_argument("--out", help="結果 json(預設 tmp\\tts_bakeoff\\probe_<fp16|fp32>.json)")
    ap.add_argument("--ref", default=str(P.COSY_REF), help="參考音(預設 cosy_voice\\ref_b.wav)")
    ap.add_argument("--qwen-emo", action="store_true", help="一併載入 QwenEmotion(情緒文字模型;預設不載)")
    ap.add_argument("--online", action="store_true", help="允許連網補下載附屬模型(預設離線)")
    a = ap.parse_args()

    set_cache_env(offline=not a.online)
    fp = "fp16" if a.fp16 else "fp32"
    out = Path(a.out) if a.out else OUT_DIR / f"probe_{fp}.json"
    wav_dir = OUT_DIR / "probe_wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    wav_dir.mkdir(parents=True, exist_ok=True)

    qc_path = latest_qc(a.tag)
    corpus = pick_corpus(qc_path, a.n)
    ref_txt = Path(a.ref).with_suffix(".txt")
    res = dict(engine="indextts2", precision=fp, model_dir=str(MODEL_DIR), qc_source=str(qc_path), ref=a.ref,
               ref_text=str(ref_txt) if ref_txt.is_file() else None, ref_text_used=False,
               options=dict(use_deepspeed=False, use_cuda_kernel=False, use_qwen_emo=a.qwen_emo, offline=not a.online),
               started=time.strftime("%Y-%m-%d %H:%M:%S"), lock=dict(tag=LOCK_TAG, job=LOCK_JOB),
               baseline_card_mib=None, load=None, sentences=[], errors=[], summary=None)

    def dump():
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    import gpu_lock as GL
    lk = GL.gpu_lock(LOCK_TAG, LOCK_JOB)
    mon = None
    torch = None
    try:
        t_wait = time.perf_counter()
        lk.acquire()
        res["lock"]["wait_s"] = round(time.perf_counter() - t_wait, 1)
        mon = VramMonitor()
        res["baseline_card_mib"] = mon.set_baseline()
        res["vram_monitor"] = dict(backend=mon.backend, poll_s=POLL_S)
        mon.start()
        dump()

        t0 = time.perf_counter()
        import torch  # noqa: F811
        if str(REPO_DIR) not in sys.path:
            sys.path.append(str(REPO_DIR))
        from indextts.infer_v2 import IndexTTS2
        from indextts.utils.model_download import ensure_models_available
        import_s = time.perf_counter() - t0
        res["torch"] = dict(version=torch.__version__, cuda=torch.version.cuda, device=torch.cuda.get_device_name(0),
                            capability=".".join(map(str, torch.cuda.get_device_capability(0))))
        try:
            aux = ensure_models_available(str(MODEL_DIR))
            t1 = time.perf_counter()
            tts = IndexTTS2(cfg_path=str(MODEL_DIR / "config.yaml"), model_dir=str(MODEL_DIR), use_fp16=a.fp16,
                            device="cuda:0", use_cuda_kernel=False, use_deepspeed=False, use_qwen_emo=a.qwen_emo,
                            aux_paths=aux)
            torch.cuda.synchronize()
            load_s = time.perf_counter() - t1
        except Exception as e:  # noqa: BLE001  載入失敗(含 OOM)記錄後結束
            res["load"] = dict(ok=False, import_s=round(import_s, 2), error=err_summary(e),
                               oom=isinstance(e, torch.cuda.OutOfMemoryError), trace=traceback.format_exc()[-2000:],
                               torch=torch_peaks(torch), smi=mon.overall())
            res["errors"].append(dict(stage="load", error=err_summary(e)))
            return 1
        time.sleep(POLL_S * 2)  # 讓監看執行緒取到載入後的穩態
        res["load"] = dict(ok=True, import_s=round(import_s, 2), load_s=round(load_s, 2), torch=torch_peaks(torch),
                           smi=mon.overall())
        dump()

        for k, c in enumerate(corpus):
            rec = dict(k=k, label="冷啟首句" if k == 0 else "", cold_first=k == 0, **c)
            wav = wav_dir / f"{fp}_{k:02d}_idx{c['idx']}.wav"
            torch.cuda.reset_peak_memory_stats()
            mon.reset_window()
            t = time.perf_counter()
            try:
                tts.infer(spk_audio_prompt=a.ref, text=c["engine_text"], output_path=str(wav), verbose=False)
                torch.cuda.synchronize()
                syn = time.perf_counter() - t
                aud = wav_seconds(wav) if wav.is_file() else None
                rec.update(ok=bool(aud), synth_s=round(syn, 2), audio_s=round(aud, 2) if aud else None,
                           rtf=round(syn / aud, 3) if aud else None, wav=str(wav))
                if not aud:
                    rec["error"] = "沒有產出音檔"
                    res["errors"].append(dict(stage="synth", k=k, idx=c["idx"], error=rec["error"]))
            except Exception as e:  # noqa: BLE001  OOM 與其他例外逐句記錄後繼續
                oom = isinstance(e, torch.cuda.OutOfMemoryError) or "out of memory" in str(e).lower()
                rec.update(ok=False, synth_s=round(time.perf_counter() - t, 2), error=err_summary(e), oom=oom,
                           trace=traceback.format_exc()[-1500:])
                res["errors"].append(dict(stage="synth", k=k, idx=c["idx"], error=err_summary(e), oom=oom))
                if oom:
                    torch.cuda.empty_cache()
            time.sleep(POLL_S)
            rec["torch"] = torch_peaks(torch)
            rec["smi"] = mon.window()
            res["sentences"].append(rec)
            dump()
        return 0 if not res["errors"] else 2
    except KeyboardInterrupt:
        res["errors"].append(dict(stage="interrupt", error="KeyboardInterrupt"))
        return 130
    except Exception as e:  # noqa: BLE001
        res["errors"].append(dict(stage="probe", error=err_summary(e), trace=traceback.format_exc()[-2000:]))
        return 1
    finally:
        if mon:
            mon.stop_ev.set()
            mon.join(timeout=2)
            res["vram_monitor"].update(samples=mon.samples, errors=mon.errors, overall=mon.overall())
        try:
            lk.release()
        except Exception as e:  # noqa: BLE001
            res["errors"].append(dict(stage="release", error=err_summary(e)))
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        res["summary"] = summarize(res)
        dump()
        print_summary(res, out)


def summarize(res):
    ok = [s for s in res["sentences"] if s.get("ok")]
    syn = [s["synth_s"] for s in ok]
    rtf = [s["rtf"] for s in ok if s.get("rtf")]
    peaks_r = [s["torch"]["max_reserved_mib"] for s in res["sentences"] if s.get("torch")]
    peaks_a = [s["torch"]["max_allocated_mib"] for s in res["sentences"] if s.get("torch")]
    load = res.get("load") or {}
    if load.get("torch"):
        peaks_r.append(load["torch"]["max_reserved_mib"])
        peaks_a.append(load["torch"]["max_allocated_mib"])
    ov = (res.get("vram_monitor") or {}).get("overall") or {}
    first = res["sentences"][0] if res["sentences"] else {}
    return dict(load_s=load.get("load_s"), torch_max_reserved_mib=max(peaks_r) if peaks_r else None,
                torch_max_allocated_mib=max(peaks_a) if peaks_a else None,
                smi_card_delta_peak_mib=ov.get("card_delta_mib"), smi_card_used_peak_mib=ov.get("card_used_mib"),
                smi_proc_peak_mib=ov.get("proc_mib"), sentences=len(res["sentences"]), ok=len(ok),
                cold_first_synth_s=first.get("synth_s"), cold_first_rtf=first.get("rtf"),
                synth_s_median=round(statistics.median(syn), 2) if syn else None, synth_s_max=max(syn) if syn else None,
                rtf_median=round(statistics.median(rtf), 3) if rtf else None, errors=len(res["errors"]),
                oom=sum(1 for e in res["errors"] if e.get("oom")))


def print_summary(res, out):
    s = res["summary"]
    print(f"[indextts2 {res['precision']}] 載入 {s['load_s']} 秒;句數 {s['ok']}/{s['sentences']};錯誤 {s['errors']}(OOM {s['oom']})")
    print(f"torch 峰值:reserved {s['torch_max_reserved_mib']} MiB / allocated {s['torch_max_allocated_mib']} MiB")
    print(f"監看峰值({(res.get('vram_monitor') or {}).get('backend')}):整卡 +{s['smi_card_delta_peak_mib']} MiB"
          f"(已用 {s['smi_card_used_peak_mib']},基線 {res['baseline_card_mib']});本行程 {s['smi_proc_peak_mib']} MiB")
    print(f"冷啟首句 {s['cold_first_synth_s']} 秒(RTF {s['cold_first_rtf']});每句中位數 {s['synth_s_median']} 秒、最大 {s['synth_s_max']} 秒;RTF 中位數 {s['rtf_median']}")
    for e in res["errors"][:3]:
        print(f"錯誤 {e.get('stage')} k={e.get('k')}: {e.get('error')}")
    print(f"結果:{out}")


if __name__ == "__main__":
    sys.exit(main())
