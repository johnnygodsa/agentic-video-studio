r"""IndexTTS2 零樣本合成常駐子行程(tts_env_indextts2 執行;由 tts_bakeoff/engines.py 啟動,模型只載入一次)。協定同 cosy3_worker.py:
  載入完成 stdout 印 `@@READY {sr?, dur_supported, dur_kwarg, dur_unit, vram_alloc_mib, vram_reserved_mib, version}`
  stdin 每行 JSON {"text": 送引擎文字, "seed": int, "out": wav 路徑[, "target_sec": 目標秒數]}
  stdout 回 `@@RES {"ok", "dur", "sec", "sr", "vram_alloc_mib", "vram_reserved_mib", "dur_used"}`(失敗 {"ok": false, "err"});其餘輸出走 stderr。
用法:tts_env_indextts2\Scripts\python.exe -X utf8 pipeline\tts_bakeoff\indextts2_worker.py --ref cosy_voice\ref_b.wav
       --model-dir tts_models\IndexTTS2 [--repo tts_models\index-tts] [--no-fp16] [--dur-kwarg 名稱 --dur-unit sec|ms|tokens]

API 依官方 index-tts(indextts.infer_v2.IndexTTS2):IndexTTS2(cfg_path, model_dir, use_fp16, use_cuda_kernel, use_deepspeed)、
infer(spk_audio_prompt, text, output_path, ...)。建構參數依 inspect.signature 過濾,版本差異不致崩潰。
**時長控制**:論文說可指定生成 token 數,但公開 infer() 是否有此參數依版本而定(本機要確認)。未給 --dur-kwarg 時只在 infer 的
具名參數裡找 DUR_CANDIDATES;找不到 = dur_supported=false,帶 target_sec 的工作回 err="dur_unsupported"(報告記「此版不支援」)。
--dur-unit tokens 時 秒數 × --tokens-per-sec(預設 50,語意 token 率,本機確認)換算。
參考音逐字稿(--ref-text)IndexTTS2 不需要,只記錄。
"""
import argparse
import inspect
import json
import os
import random
import sys
import time
import wave
from pathlib import Path

if sys.path and Path(sys.path[0] or ".").resolve() == Path(__file__).resolve().parent:   # 本資料夾的短名模組不可蓋過 indextts 的依賴
    sys.path.pop(0)

DUR_CANDIDATES = {"target_duration": "sec", "duration": "sec", "target_dur": "sec", "speech_duration": "sec",
                  "target_length": "tokens", "target_tokens": "tokens", "num_tokens": "tokens", "speech_tokens": "tokens"}

ap = argparse.ArgumentParser()
ap.add_argument("--ref", required=True)
ap.add_argument("--ref-text")
ap.add_argument("--model-dir", required=True)
ap.add_argument("--repo", help="index-tts 原始碼目錄(沒 pip install -e 時加進 sys.path)")
ap.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
ap.add_argument("--no-fp16", action="store_true")
ap.add_argument("--dur-kwarg", help="infer() 的時長參數名(本機依 index-tts 版本確認)")
ap.add_argument("--dur-unit", choices=["sec", "ms", "tokens"], help="時長參數單位(未給時依 DUR_CANDIDATES 或 sec)")
ap.add_argument("--tokens-per-sec", type=float, default=50.0)
ap.add_argument("--gen-json", default="", help="額外 infer 參數 JSON(例 {\"temperature\": 0.8})")
args = ap.parse_args()

if args.device == "cpu":
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
if args.repo and Path(args.repo).is_dir():
    sys.path.insert(0, str(Path(args.repo).resolve()))

out_fd = sys.stdout
sys.stdout = sys.stderr  # 模型載入/推論的雜訊印到 stderr,stdout 只留協定行


def reply(tag, obj):
    out_fd.write(f"{tag} {json.dumps(obj, ensure_ascii=False)}\n")
    out_fd.flush()


def vram():
    import torch
    if not torch.cuda.is_available():
        return dict(vram_alloc_mib=0, vram_reserved_mib=0)
    return dict(vram_alloc_mib=int(torch.cuda.max_memory_allocated() / 2 ** 20),
                vram_reserved_mib=int(torch.cuda.max_memory_reserved() / 2 ** 20))


def wav_info(path):
    try:
        with wave.open(str(path), "rb") as f:
            return f.getnframes() / f.getframerate(), f.getframerate()
    except wave.Error:   # 浮點 wav 等 wave 讀不了的格式
        import soundfile as sf
        i = sf.info(str(path))
        return i.frames / i.samplerate, i.samplerate


def dur_value(sec, unit):
    if unit == "ms":
        return int(round(sec * 1000))
    if unit == "tokens":
        return int(round(sec * args.tokens_per_sec))
    return float(sec)


try:
    import numpy as np
    import torch
    from indextts.infer_v2 import IndexTTS2
except Exception as e:  # noqa: BLE001
    print(f"[indextts2_worker] 匯入失敗: {e!r}", file=sys.stderr, flush=True)
    sys.exit(2)

md = Path(args.model_dir)
want = dict(cfg_path=str(md / "config.yaml"), model_dir=str(md), use_fp16=not args.no_fp16, use_cuda_kernel=False,
            use_deepspeed=False, device="cuda:0" if args.device == "cuda" else "cpu")
params = inspect.signature(IndexTTS2.__init__).parameters
tts = IndexTTS2(**{k: v for k, v in want.items() if k in params})

infer_params = inspect.signature(tts.infer).parameters
var_kw = any(p.kind == p.VAR_KEYWORD for p in infer_params.values())
if args.dur_kwarg:
    dur_kwarg = args.dur_kwarg
    dur_supported = dur_kwarg in infer_params or var_kw   # 走 **generation_kwargs 的要本機確認真的有作用(報告看誤差)
    dur_unit = args.dur_unit or DUR_CANDIDATES.get(dur_kwarg, "sec")
else:
    dur_kwarg = next((k for k in DUR_CANDIDATES if k in infer_params), None)
    dur_supported = dur_kwarg is not None
    dur_unit = args.dur_unit or DUR_CANDIDATES.get(dur_kwarg or "", "sec")
gen = json.loads(args.gen_json) if args.gen_json else {}
try:
    from importlib.metadata import version
    ver = version("indextts")
except Exception:  # noqa: BLE001
    ver = None
reply("@@READY", dict(dur_supported=dur_supported, dur_kwarg=dur_kwarg, dur_unit=dur_unit, fp16=not args.no_fp16,
                      infer_params=sorted(infer_params), version=ver, **vram()))

for line in sys.stdin:
    if not line.strip():
        continue
    job = json.loads(line)
    try:
        if job.get("cmd") == "quit":
            break
        kw = dict(gen)
        if job.get("target_sec") is not None:
            if not dur_supported:
                reply("@@RES", dict(ok=False, err="dur_unsupported"))
                continue
            kw[dur_kwarg] = dur_value(float(job["target_sec"]), dur_unit)
        s = int(job.get("seed", 2024))
        random.seed(s)
        np.random.seed(s % 2 ** 32)
        torch.manual_seed(s)
        t0 = time.time()
        tts.infer(spk_audio_prompt=args.ref, text=job["text"], output_path=job["out"], verbose=False, **kw)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        sec = time.time() - t0
        dur, sr = wav_info(job["out"])
        reply("@@RES", dict(ok=True, dur=round(dur, 3), sec=round(sec, 3), sr=sr,
                            dur_used=kw.get(dur_kwarg) if dur_kwarg else None, **vram()))
    except Exception as e:  # noqa: BLE001  OOM 等:回報失敗,行程繼續(OOM 後通常仍可用;不行的話下一句會再失敗)
        if "out of memory" in repr(e).lower():
            try:
                torch.cuda.empty_cache()
            except Exception:  # noqa: BLE001
                pass
        reply("@@RES", dict(ok=False, err=repr(e)[:300], **vram()))
