r"""CosyVoice3 零樣本複製合成常駐子行程(tts_env_cosy3 執行;由 tts_cosy3.py 啟動,模型只載入一次)。
stdin 每行一個 JSON:{"text": 送進引擎的文字, "seed": int, "speed": float, "out": wav 路徑}
  或 {"cmd": "tail_f0", "wav": 路徑}(句尾 F0 斜率;librosa 只裝在這個 env)。
stdout 回應以 "@@RES " 開頭的 JSON 行(其他輸出一律走 stderr)。啟動完成印 "@@READY {sr}"。
用法:tts_env_cosy3\Scripts\python.exe -X utf8 pipeline\cosy3_worker.py --ref wav --ref-text txt [--device cuda|cpu]
"""
import argparse, json, os, sys
from pathlib import Path

import paths as P

COSY = P.TTS_MODELS / "CosyVoice"
SYS_PROMPT = "You are a helpful assistant."
END = "<|endofprompt|>"
HOP, FRAME, MIN_FRAMES = 256, 2048, 4
SPK_ID = "cv_ref"     # 預存參考音的代號(只在這個行程內有效,不存檔)

ap = argparse.ArgumentParser()
ap.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
ap.add_argument("--ref", required=True)
ap.add_argument("--ref-text", required=True)
args = ap.parse_args()

if args.device == "cpu":
    os.environ["CUDA_VISIBLE_DEVICES"] = ""  # 前端以 torch.cuda.is_available() 選裝置
sys.path.insert(0, str(COSY))
sys.path.insert(0, str(COSY / "third_party" / "Matcha-TTS"))

out_fd = sys.stdout
sys.stdout = sys.stderr  # 模型載入/推論的雜訊印到 stderr,stdout 只留協定行

import numpy as np  # noqa: E402
import torch, torchaudio  # noqa: E402
from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402
from cosyvoice.utils.common import set_all_random_seed  # noqa: E402

# 文字正規化 wetext 每次都向 ModelScope 查版本;Colab 連 modelscope.cn 403 -> 前端退成「無正規化」、唸法跟本機不同。
# 素材根有快取就直接用,不連網(pack_for_colab 會把這個目錄一起打包)
WETEXT = P.TTS_MODELS / "hub" / "pengzhendong" / "wetext"
if (WETEXT / "zh").is_dir():
    import wetext.wetext as _wt  # noqa: E402
    _wt.snapshot_download = lambda *a, **k: str(WETEXT)


def reply(tag, obj):
    out_fd.write(f"{tag} {json.dumps(obj, ensure_ascii=False)}\n")
    out_fd.flush()


def tail_f0(path, win=0.3):
    """句尾 F0 斜率:librosa.pyin -> 最後一個有聲音框往前 win 秒內的有聲音框 -> 半音(12*log2 f0)對時間線性迴歸斜率(半音/秒,正 = 上揚)。"""
    import librosa
    y, sr = librosa.load(str(path), sr=None, mono=True)
    f0, vf, _ = librosa.pyin(y, fmin=60, fmax=400, sr=sr, frame_length=FRAME, hop_length=HOP)
    t = librosa.times_like(f0, sr=sr, hop_length=HOP)
    ok = vf & np.isfinite(f0)
    if ok.sum() < MIN_FRAMES:
        return dict(slope=None, n=int(ok.sum()))
    sel = ok & (t >= t[ok][-1] - win)
    if sel.sum() < MIN_FRAMES:
        return dict(slope=None, n=int(sel.sum()))
    k = np.polyfit(t[sel], 12 * np.log2(f0[sel]), 1)[0]
    return dict(slope=round(float(k), 1), hz=[round(float(f0[sel][0]), 1), round(float(f0[sel][-1]), 1)], n=int(sel.sum()))


model = AutoModel(model_dir=str(COSY / "pretrained_models" / "Fun-CosyVoice3-0.5B"))
if sys.platform.startswith("linux"):   # 載入時 CPU 暫存的權重還給系統(Colab 系統 RAM 12 GB;T6 實測載入後 RSS 5 GB)
    import ctypes, gc  # noqa: E401,E402
    gc.collect()
    ctypes.CDLL("libc.so.6").malloc_trim(0)
prompt = f"{SYS_PROMPT}{END}{Path(args.ref_text).read_text(encoding='utf-8').strip()}"
model.add_zero_shot_spk(prompt, args.ref, SPK_ID)   # 參考音特徵只算一次(每次合成省約 0.5 秒)
reply("@@READY", {"sr": model.sample_rate})

for line in sys.stdin:
    if not line.strip():
        continue
    job = json.loads(line)
    try:
        if job.get("cmd") == "tail_f0":
            reply("@@RES", dict(ok=True, **tail_f0(job["wav"], float(job.get("win", 0.3)))))
            continue
        set_all_random_seed(int(job["seed"]))
        # text_frontend=False:文字已由 tts_cosy3 正規化(數字轉讀法、拼音標注),前端不可再拆
        it = model.inference_zero_shot(job["text"], prompt, args.ref, stream=False,
                                       speed=float(job.get("speed", 1.0)), text_frontend=False, zero_shot_spk_id=SPK_ID)
        w = torch.cat([j["tts_speech"] for j in it], dim=1)
        torchaudio.save(job["out"], w, model.sample_rate)
        reply("@@RES", {"ok": True, "dur": round(w.shape[1] / model.sample_rate, 3),
                        "vram_mib": int(torch.cuda.max_memory_reserved() / 2**20) if torch.cuda.is_available() else 0})
    except Exception as e:  # noqa: BLE001
        reply("@@RES", {"ok": False, "err": repr(e)})
