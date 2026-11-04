"""語音辨識常駐子行程(由 tts_asr.Worker 啟動,模型只載入一次)。
Qwen3-ASR-0.6B 跑在 tts_env_asr(torch 2.11)、Fun-ASR-Nano 跑在 tts_env_asr_fun(transformers 5),與品管主程式的
tts_env_chattts(torch 2.6 / transformers 4.57)套件版本不相容,所以各自包成子行程。
用法:<env>\\Scripts\\python.exe -X utf8 asr_worker.py --backend qwen06|fun_nano --models <tts_models\\asr> [--device cuda|cpu]
     [--aligner cuda|cpu|none](只 qwen06:另載 Qwen3-ForcedAligner-0.6B 給逐字時間,channel/_archive/plans/PLAN_配音對齊_2026-10-29.md §2.1)
協定:載入完成印一行 `@@READY {json}`;stdin 每行一個 JSON {"npy": 16 kHz float32 .npy 路徑[, "text": 對齊用文字]}
({"cmd": "quit"} 結束),stdout 回一行 `@@RES {"ok": true, "text": ..., "sec": ...}`(失敗 {"ok": false, "err": ...})。
請求有 text 且對齊器已載入時,回覆多 "words": [[字, 起, 迄], ...](秒;對齊失敗為 null,錯誤只寫 stderr,辨識文字照回)。
其餘輸出一律走 stderr。"""
import argparse
import json
import os
import re
import sys
import time

import numpy as np

UNIT_RE = re.compile(r"[A-Za-z]+|[0-9]|[一-鿿]")   # 與 tts_pause.units 相同的發音單位


def build(backend, models, device, threads):
    import torch
    if backend == "qwen06":
        from qwen_asr import Qwen3ASRModel
        cuda = device == "cuda"
        m = Qwen3ASRModel.from_pretrained(os.path.join(models, "qwen3-asr-0.6b"),
                                          dtype=torch.bfloat16 if cuda else torch.float32,
                                          device_map="cuda:0" if cuda else "cpu",
                                          max_inference_batch_size=1, max_new_tokens=256)
        return lambda x: m.transcribe(audio=(x, 16000), language="Chinese")[0].text
    if backend == "fun_nano":
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
        torch.set_num_threads(threads)
        d = os.path.join(models, "fun-asr-nano-hf")
        proc = AutoProcessor.from_pretrained(d, trust_remote_code=False)
        # device=cuda(TTS_ASR2_DEVICE=cuda,Colab)才上顯示卡:免費版系統 RAM 12 GB 放不下 CPU 版 3.6 GB(T6 OOM);本機預設 CPU 不變
        dev = "cuda" if device == "cuda" else "cpu"
        m = AutoModelForSpeechSeq2Seq.from_pretrained(d, trust_remote_code=False, dtype=torch.float32).to(dev).eval()
        # 不用 device_map="cuda:0":tts_env_asr_fun 沒裝 accelerate,from_pretrained 會直接中止(T6 實測);CPU 殘留靠 main() 的 malloc_trim

        def f(x):
            inp = proc.apply_transcription_request(audio=x, language="zh", processor_kwargs={
                "return_tensors": "pt", "audio_kwargs": {"sampling_rate": 16000}, "text_kwargs": {"padding": True}}).to(dev)
            with torch.inference_mode():
                g = m.generate(**inp, max_new_tokens=128, do_sample=False)
            return proc.batch_decode(g[:, inp.input_ids.shape[1]:], skip_special_tokens=True)[0]
        return f
    raise SystemExit(f"[asr_worker] 不認得的後端 {backend}")


def build_aligner(models, device):
    """Qwen3-ForcedAligner-0.6B -> f(x, text) = [[字, 起, 迄], ...]:一個對齊項含多個單位時(英數混排)逐單位等分時間。"""
    import torch
    from qwen_asr import Qwen3ForcedAligner
    cuda = device == "cuda"
    fa = Qwen3ForcedAligner.from_pretrained(os.path.join(models, "qwen3-forcedaligner-0.6b"),
                                            dtype=torch.bfloat16 if cuda else torch.float32,
                                            device_map="cuda:0" if cuda else "cpu")

    def f(x, text):
        out = []
        for it in fa.align((x, 16000), text, "Chinese")[0].items:
            us = UNIT_RE.findall(it.text) or [it.text]
            s, e = float(it.start_time), float(it.end_time)
            for k, u in enumerate(us):
                out.append([u, round(s + (e - s) * k / len(us), 3), round(s + (e - s) * (k + 1) / len(us), 3)])
        return out
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True)
    ap.add_argument("--models", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--aligner", default="none", choices=("cuda", "cpu", "none"))
    a = ap.parse_args()
    out, sys.stdout = sys.stdout, sys.stderr  # 模型載入的雜訊不可混進協定
    t0 = time.time()
    f = build(a.backend, a.models, a.device, a.threads)
    fa = build_aligner(a.models, a.aligner) if a.backend == "qwen06" and a.aligner != "none" else None
    if sys.platform.startswith("linux") and "cuda" in (a.device, a.aligner):   # 載入時 CPU 暫存還給系統(Colab RAM 12 GB;T6 實測 fun_nano 上 GPU 後 RSS 仍 3.4 GB)
        import ctypes, gc
        gc.collect()
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    f(np.zeros(16000, dtype=np.float32))  # 暖機
    if fa:
        fa(np.zeros(16000, dtype=np.float32), "你好")
    vram = 0
    if "cuda" in (a.device, a.aligner):
        import torch
        vram = int(torch.cuda.max_memory_allocated() // 2 ** 20)
    out.write("@@READY " + json.dumps(dict(backend=a.backend, device=a.device, aligner=a.aligner if fa else "none",
                                           load_s=round(time.time() - t0, 1), vram_mb=vram)) + "\n")
    out.flush()
    for line in sys.stdin:
        if not line.strip():
            continue
        job = json.loads(line)
        if job.get("cmd") == "quit":
            break
        t = time.time()
        try:
            x = np.load(job["npy"])
            res = dict(ok=True, text=f(x), sec=round(time.time() - t, 3))
        except Exception as e:  # noqa: BLE001  辨識失敗回報給主程式,不讓子行程死掉
            res = dict(ok=False, err=repr(e)[:300])
        if res["ok"] and fa and job.get("text"):
            try:
                res["words"] = fa(x, job["text"])
            except Exception as e:  # noqa: BLE001  對齊失敗:words = null,主程式退回 whisper 時間戳
                print(f"[asr_worker] 對齊失敗: {e!r}"[:300], file=sys.stderr, flush=True)
                res["words"] = None
            res["sec"] = round(time.time() - t, 3)
        out.write("@@RES " + json.dumps(res, ensure_ascii=False) + "\n")
        out.flush()


if __name__ == "__main__":
    main()
