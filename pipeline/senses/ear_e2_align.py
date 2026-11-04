#!/usr/bin/env python3
r"""耳朵 E2 對齊(PLAN_工作室v2_2026-10-31 §6.3):一句配音 -> 每字 (字, 起, 迄) 秒。
- 來源一(快取句,免費):品管旁註 NNN.qc.json 的 say_t(品管時 Qwen3-ForcedAligner-0.6B 對齊,len = len(文字)+1,
  第 i 字 = [say_t[i], say_t[i+1]];標點的區間就是停頓)。
- 來源二(任意音檔):tts_env_asr 子行程跑 Qwen3-ForcedAligner(tts_models\asr\qwen3-forcedaligner-0.6b),
  結果換成與 say_t 相同的寫法(字迄 = 下一個有時間的字起),訓練與推論特徵一致。預設 CPU;--device cuda 走全機 gpu_lock。
只用標準函式庫(子行程在 tts_env_asr 以 --worker 執行本檔)。
單獨執行:python -X utf8 pipeline/senses/ear_e2_align.py --wav <f> --text <t> [--device cpu|cuda]   印 JSON
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))

MARK = "@@E2@@"


def from_qc(qc):
    """qc.json dict -> (文字, [(字, 起, 迄)]);say_t 長度對不上回 (None, None)。"""
    st = qc.get("say_t") or []
    for key in ("text", "measure_text"):
        t = qc.get(key) or ""
        if st and len(st) == len(t) + 1:
            return t, [(t[i], float(st[i]), float(st[i + 1])) for i in range(len(t))]
    return None, None


def _is_cjk(ch):
    return "㐀" <= ch <= "鿿" or "豈" <= ch <= "﫿"


def map_items(text, items):
    """對齊項 [[單位, 起, 迄]] -> 原文每字 (字, 起, 迄)(找不到的字起迄為 None);字迄改成下一個有時間的字起(同 say_t)。"""
    st, en = [None] * len(text), [None] * len(text)
    cur = 0
    for tok, s, e in items:
        units = list(tok) if tok and all(_is_cjk(c) for c in tok) else [tok]
        for k, u in enumerate(units):
            j = text.find(u, cur) if u else -1
            if j < 0:
                continue
            st[j], en[j] = s + (e - s) * k / len(units), s + (e - s) * (k + 1) / len(units)
            cur = j + len(u)
    nxt = None
    for i in range(len(text) - 1, -1, -1):
        if st[i] is None:
            continue
        if nxt is not None:
            en[i] = max(en[i], nxt) if nxt - en[i] < 0.5 else en[i]   # 長停頓不併進字裡
        nxt = st[i]
    return [(text[i], st[i], en[i]) for i in range(len(text))]


def align_wav(wav, text, device="cpu", tag="ear_e2"):
    """任意音檔 -> [(字, 起, 迄)]。子行程跑 tts_env_asr;cuda 時排全機 GPU 鎖。"""
    import paths
    py = paths.venv_python(paths.ROOT / "tts_env_asr")
    model = paths.TTS_MODELS / "asr" / "qwen3-forcedaligner-0.6b"
    cmd = [str(py), "-X", "utf8", str(Path(__file__).resolve()), "--worker",
           "--wav", str(wav), "--text", text, "--device", device, "--model", str(model)]

    def run():
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        line = next((ln for ln in reversed(r.stdout.splitlines()) if ln.startswith(MARK)), None)
        if line is None:
            raise RuntimeError(f"對齊失敗(rc={r.returncode}):{r.stderr.strip()[-400:]}")
        return json.loads(line[len(MARK):])
    if device == "cuda":
        from gpu_lock import gpu_lock
        with gpu_lock(tag, "ear_e2_align"):
            items = run()
    else:
        items = run()
    return map_items(text, items)


def _worker(a):
    out, sys.stdout = sys.stdout, sys.stderr  # 模型載入的雜訊不可混進結果行
    from math import gcd
    import soundfile as sf
    import torch
    from qwen_asr import Qwen3ForcedAligner
    x, sr = sf.read(a.wav, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr != 16000:
        from scipy.signal import resample_poly
        g = gcd(16000, sr)
        x = resample_poly(x, 16000 // g, sr // g).astype("float32")
    cuda = a.device == "cuda"
    fa = Qwen3ForcedAligner.from_pretrained(a.model, dtype=torch.bfloat16 if cuda else torch.float32,
                                            device_map="cuda:0" if cuda else "cpu")
    items = [[it.text, round(float(it.start_time), 3), round(float(it.end_time), 3)]
             for it in fa.align((x, 16000), a.text, "Chinese")[0].items]
    out.write(MARK + json.dumps(items, ensure_ascii=False) + "\n")
    out.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--model")
    a = ap.parse_args()
    if a.worker:
        return _worker(a)
    print(json.dumps(align_wav(a.wav, a.text, a.device), ensure_ascii=False))


if __name__ == "__main__":
    main()
