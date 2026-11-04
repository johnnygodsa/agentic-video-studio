r"""BreezyVoice(聯發科台灣華語 TTS,CosyVoice-300M 改版)零樣本合成常駐子行程(tts_env_breezy 執行;由 tts_bakeoff/engines.py 啟動,模型只載入一次)。
協定同 indextts2_worker.py / cosy3_worker.py:
  載入完成 stdout 印 `@@READY {sr, load_s, vram_alloc_mib, vram_reserved_mib, ...}`
  stdin 每行 JSON {"text": 送引擎文字(繁體;可含「字[:ㄓㄤ3]」注音標注), "seed": int, "out": wav 路徑}
       或 {"cmd": "prep", "text": ...}(只回 final_text,不合成)、{"cmd": "quit"}
  stdout 回 `@@RES {"ok", "dur", "sec", "sr", "final_text", "vram_alloc_mib", "vram_reserved_mib"}`(失敗 {"ok": false, "err"});其餘輸出走 stderr。
用法:tts_env_breezy\Scripts\python.exe -X utf8 pipeline\tts_bakeoff\breezy_worker.py --ref cosy_voice\ref_b.wav --ref-text cosy_voice\ref_b.txt
       --model-dir tts_models\BreezyVoice-300M --repo tts_models\BreezyVoice --g2pw-dir tts_models\BreezyVoice_cache\G2PWModel
       [--wetext-dir tts_models\hub\pengzhendong\wetext] [--device cuda|cpu]

流程照官方 single_inference.py:文字正規化(CosyVoice 前端 text_normalize_new)-> g2pW 對罕見/易錯字自動補注音(get_bopomofo_rare;
文字裡已有的「字[:注音]」不再補)-> inference_zero_shot_no_normalize(依句末標點分句合成再串接)。與官方不同的三處(都不改 repo 原始碼):
 1. `tn` 套件(WeTextProcessing,需要 pynini,Windows 無 wheel)用 wetext(CosyVoice3 同一個,kaldifst)頂替:sys.modules 注入同名介面。
 2. 文字裡有手動注音標注時逐段正規化:官方 text_normalize_new 對「非最後一段、且不以 。 結尾」的段落會 text[:-1] 砍掉最後一字,
    手動標注在句中時會吃掉被標注的字本身;逐段各當最後一段正規化即不砍。
 3. 參考音特徵(文字 token 以外)只算一次(官方每句重算);char2phn 查不到的字(全形符號等)當 0 個讀音,不拋 KeyError。
"""
import argparse
import collections
import json
import os
import random
import re
import sys
import time
import types
from pathlib import Path

if sys.path and Path(sys.path[0] or ".").resolve() == Path(__file__).resolve().parent:   # 本資料夾的短名模組(corpus/report…)不可蓋過第三方套件
    sys.path.pop(0)

ap = argparse.ArgumentParser()
ap.add_argument("--ref", required=True)
ap.add_argument("--ref-text", required=True, help="參考音逐字稿檔(繁體)")
ap.add_argument("--model-dir", required=True)
ap.add_argument("--repo", required=True, help="BreezyVoice 原始碼目錄(git clone)")
ap.add_argument("--g2pw-dir", required=True, help="g2pW 模型目錄(不存在 = 套件首次自動下載到這裡)")
ap.add_argument("--wetext-dir", help="wetext 本機快取(有 zh 子目錄就不連網查版本)")
ap.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
args = ap.parse_args()

if args.device == "cpu":
    os.environ["CUDA_VISIBLE_DEVICES"] = ""   # 前端以 torch.cuda.is_available() 選裝置;冒煙測試不碰顯示卡
repo = Path(args.repo).resolve()
sys.path.insert(0, str(repo / "third_party" / "Matcha-TTS"))
sys.path.insert(0, str(repo))

out_fd = sys.stdout
sys.stdout = sys.stderr  # 模型載入/推論的雜訊印到 stderr,stdout 只留協定行


def reply(tag, obj):
    out_fd.write(f"{tag} {json.dumps(obj, ensure_ascii=False)}\n")
    out_fd.flush()


def install_tn_shim(wetext_dir):
    """cosyvoice.cli.frontend 要 `tn.chinese.normalizer.Normalizer` / `tn.english.normalizer.Normalizer`:用 wetext 頂替(同 CosyVoice3 做法)。"""
    import wetext.wetext as _wt
    if wetext_dir and (Path(wetext_dir) / "zh").is_dir():
        _wt.snapshot_download = lambda *a, **k: str(wetext_dir)   # 不連 modelscope 查版本
    from wetext import Normalizer

    class ZhNormalizer(Normalizer):
        def __init__(self, remove_erhua=False, full_to_half=False, **kw):   # full_to_half:wetext 沒有此參數,忽略
            super().__init__(remove_erhua=remove_erhua)

    class EnNormalizer(Normalizer):
        def __init__(self, **kw):
            super().__init__()

    for name, cls in (("tn.chinese.normalizer", ZhNormalizer), ("tn.english.normalizer", EnNormalizer)):
        m = types.ModuleType(name)
        m.Normalizer = cls
        sys.modules[name] = m
    for name in ("tn", "tn.chinese", "tn.english"):
        sys.modules.setdefault(name, types.ModuleType(name))


def vram():
    import torch
    if not torch.cuda.is_available():
        return dict(vram_alloc_mib=0, vram_reserved_mib=0)
    return dict(vram_alloc_mib=int(torch.cuda.max_memory_allocated() / 2 ** 20),
                vram_reserved_mib=int(torch.cuda.max_memory_reserved() / 2 ** 20))


SR = 22050
ANN = re.compile(r"(\[:[^\]]*\])")     # 手動注音標注「[:ㄓㄤ3]」
NEEDS_NORM = re.compile(r"[\w㐀-鿿]")


def normalize(fe, text):
    """官方 text_normalize_new;含手動標注時逐段正規化(見檔頭第 2 點)。"""
    if "[:" not in text:
        return fe.text_normalize_new(text, split=False)
    out = []
    for p in ANN.split(text):
        if ANN.fullmatch(p) or not NEEDS_NORM.search(p):
            out.append(p)
        else:
            out.append(fe.text_normalize_new(p, split=False))
    return "".join(out)


try:
    import numpy as np
    import torch
    import torchaudio
    install_tn_shim(args.wetext_dir)
    import single_inference as SI   # repo 內官方腳本(main() 有 __name__ 保護,匯入無副作用)
    from cosyvoice.utils.file_utils import load_wav
except Exception as e:  # noqa: BLE001
    print(f"[breezy_worker] 匯入失敗: {e!r}", file=sys.stderr, flush=True)
    sys.exit(2)

if args.device == "cpu":
    torch.set_num_threads(os.cpu_count() or 4)   # 官方腳本把執行緒數設成 1,CPU 冒煙測試放開
SI.char2phn = collections.defaultdict(list, SI.char2phn)   # get_bopomofo_rare 查不到的字不拋 KeyError

t_load = time.time()
tts = SI.CustomCosyVoice(args.model_dir)
fe = tts.frontend
from g2pw import G2PWConverter  # noqa: E402
conv = G2PWConverter(model_dir=args.g2pw_dir)   # 預設 style=bopomofo(同官方 single_inference)
conv.num_workers = 0   # 套件把 0 當沒給、退回設定檔的 2:每次呼叫 spawn 子行程(Windows 很慢)

prompt_wav = load_wav(args.ref, 16000)
prompt_text = SI.get_bopomofo_rare(normalize(fe, Path(args.ref_text).read_text(encoding="utf-8").strip()), conv)
BASE = fe.frontend_zero_shot("好。", prompt_text, prompt_wav)   # 參考音特徵只算一次;每句只換文字 token
reply("@@READY", dict(sr=SR, load_s=round(time.time() - t_load, 1), prompt_text=prompt_text, device=args.device, **vram()))


def synthesize(final_text):
    """依句末標點分句,各句合成後串接(同官方 inference_zero_shot_no_normalize)。"""
    parts = []
    for sent in re.split(r"(?<=[？！。.?!])\s*", final_text):
        if not sent:
            continue
        tok, tok_len = fe._extract_text_token(sent)
        out = tts.model.inference(**dict(BASE, text=tok, text_len=tok_len))
        parts.append(out["tts_speech"])
    return torch.concat(parts, dim=1)


for line in sys.stdin:
    if not line.strip():
        continue
    job = json.loads(line)
    try:
        if job.get("cmd") == "quit":
            break
        if job.get("cmd") == "prep":   # 只做文字前處理(正規化 + 補注音),不合成:檢查實際送進模型的文字
            reply("@@RES", dict(ok=True, final_text=SI.get_bopomofo_rare(normalize(fe, job["text"]), conv)))
            continue
        s = int(job.get("seed", 2024))
        random.seed(s)
        np.random.seed(s % 2 ** 32)
        torch.manual_seed(s)
        t0 = time.time()
        final = SI.get_bopomofo_rare(normalize(fe, job["text"]), conv)
        wav = synthesize(final)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        sec = time.time() - t0
        torchaudio.save(job["out"], wav, SR)
        reply("@@RES", dict(ok=True, dur=round(wav.shape[1] / SR, 3), sec=round(sec, 3), sr=SR, final_text=final, **vram()))
    except Exception as e:  # noqa: BLE001  OOM 等:回報失敗,行程繼續
        if "out of memory" in repr(e).lower():
            try:
                torch.cuda.empty_cache()
            except Exception:  # noqa: BLE001
                pass
        reply("@@RES", dict(ok=False, err=repr(e)[:300], **vram()))
