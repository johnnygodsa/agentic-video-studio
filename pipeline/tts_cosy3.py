#!/usr/bin/env python3
r"""CosyVoice3 零樣本複製批次包裝(含全套品管重試)。介面同 tts_chattts.py(build.py 以 --tts-engine cosy3 呼叫):
<Claude_Video>/tts_env_chattts/Scripts/python.exe pipeline/tts_cosy3.py jobs.json --ref cosy_voice/ref_b.wav --speed 1.18 --voice V --rate R
jobs.json = [{"text": 送配音的文字(@say 後), "out": wav, "idx": 句編號, "verify": bool}];verify=true 且 out 存在:先品管既有音檔,過了就沿用。
品管(faster-whisper / speechbrain)在 tts_env_chattts 跑;合成交給 tts_env_cosy3 的常駐子行程 cosy3_worker.py(模型只載入一次)。
--ref 參考音(同主檔名 .txt 是其逐字稿);--voice / --rate 只當標籤(語速由 --speed 決定)。

每句:合成 -> 裁頭尾靜音(tts_tail.gentle_trim)-> 貼耳感濾鏡 FX(ffmpeg)-> 量測(tts_chattts.measure)-> 判定(tts_chattts.check + 句尾上揚)
  -> 未過換 seed 重錄(--max-retry)-> 語速重錄(--rate-seeds,speed 以偏差最小那次為基準、調幅減半、限起始 speed ±20%)
  -> 句中停頓/多餘停頓/雜音後處理(同 tts_chattts.main 結尾)-> out + <out>.qc.json(final=True)。
品管對象是「裁切 + 後製」後實際進影片的音檔。聲紋基準 = 參考音的 ECAPA 嵌入。
文字:job text 先 tts_cosy_text.unsay(@say 已換成 ChatTTS 寫法的英文詞換回原文)= 量測用文字;送引擎 = 量測用文字套 cosy_terms 英文寫法
  + cosy_pron 拼音標注 + 簡體 + 數字讀法,句尾保留問號/驚嘆號。量測用文字與 job text 不同時(英文詞換回)say_t 不輸出(字幕改用比例分段)。
品管項目 = tts_chattts 全部(聲紋/音高/回查/句尾兩字/句尾聲學/時間戳/長度/句中停頓/多餘停頓/語速/發音表回查)
  + 陳述句句尾上揚(最後 0.3 秒 F0 斜率 > --tail-rise 半音/秒,tail_rise)+ 英文句 ASR 寬鬆比對(asr_loose,cosy_terms 的 _asr_alias;
  英文段辨識不出時該位置要音近原詞/別名,否則 term_misread,tts_term_qc.loose_misses)+ 詞界長停頓(>= TP.STRAY_WB_FAIL,stray_pause)
  + 逗號連讀(非頓號標點的原始靜音 < TP.COMMA_RUNON_MIN,comma_runon:換 seed 重錄,不靠插入過關)。
  整批後:仍直送英文的詞跨句辨識寫法一致性(term_inconsistent,tts_term_qc.inconsistent)-> 不一致的句子換 seed 重錄。
未涵蓋:聲碼器電音感(整句 HNR/高頻平坦度/F0 抖動都分不出壞句,見 projects/tts_cosy3/handoff.md)。
整批基準(音高/每音節長度/聲紋迴歸/語速中位數)在句數 >= 30 時存成 jobs 同目錄 _qc_base_cosy3.json,小批次沿用。
多 GPU 分片(Kaggle T4x2,shard_gpus):另開 --shard-serve 子行程綁另一張卡,只分攤「合成 + 量測」(共用工作佇列);
  整批基準、判定、語速中位數、跨句一致性、後處理、副辨識仍在本行程對全部句子各做一次(與單 GPU 語意相同)。
"""
import argparse
import hashlib
import json
import os
import pickle
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gpu_lock as GL  # noqa: E402
import paths as P  # noqa: E402

os.environ["TEMP"] = os.environ["TMP"] = str(P.TMP)
os.environ.setdefault("HF_HOME", str(P.TTS_MODELS))
os.environ.setdefault("MODELSCOPE_CACHE", str(P.TTS_MODELS))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
import torchaudio  # noqa: E402
import tts_chattts as TC  # noqa: E402  品管函式(measure/check/QC/fit_spk/comma_only/num_to_cn)
import tts_cosy_text as CT  # noqa: E402
import tts_g2p as TG  # noqa: E402  g2pW 第三意見(T3;不可用時回 None,不影響配音)
import tts_asr as TA  # noqa: E402
import tts_pause as TP  # noqa: E402
import tts_term_qc as TQ  # noqa: E402  英文詞音近/跨句一致性(純函式)
from tts_tail import QC_VER, gentle_trim  # noqa: E402

SR = TC.SR
BASE_MIN = 30
COSY_ENV = P.venv_python(P.ROOT / "tts_env_cosy3")
FX = ("lowshelf=f=120:g=-3,equalizer=f=3000:t=q:w=1:g=2.5,"
      "acompressor=threshold=-24dB:ratio=4:attack=3:release=60:makeup=3")  # 使用者選定的「貼耳感」(2026-10-17)
COMMA_RETRY = 0  # 只差句中停頓/多餘停頓(後處理補得起來)就不再換 seed:CosyVoice 逗號處的靜音天生偏短(沒有 [uv_break]),
                 # 換 seed 也補不起來,反而換來聲紋/句尾問題(2026-10-17 smoke test 3 句 x 4-5 次);由後處理 fix_pauses 插入靜音
                 # (模型連讀 comma_runon 例外:不算後處理補得起來,見 stop_retry)


_tl = threading.local()   # 分片執行緒:ex = 綁定的 Remote(None = 本行程)、tag = log 前綴


def log(msg):
    print(getattr(_tl, "tag", "") + msg, file=sys.stderr, flush=True)


def stop_retry(m, tries):
    """主品管重錄迴圈要不要停:只差後處理補得起來的項目就不再換 seed;詞界長停頓、comma_runon 不算(comma_only 為假)。"""
    return TC.comma_only(m) and tries >= COMMA_RETRY and not m.get("stray_wb_long")


def wait_vram(tag):
    """排隊拿全機 GPU 鎖(gpu_lock.py;含 nvidia-smi <= 3000 MiB;父行程 make_version/shorts_build 已持有就直接通過);行程結束自動釋放。"""
    GL.gpu_lock(tag, "tts_cosy3").acquire()


# ------------------------------------------------------------ 文字
def _norm(t):
    t = re.sub(r"(\d[\d,]*(?:\.\d+)?)\s*%", lambda m: "百分之" + TC.num_to_cn(m.group(1)), t)
    t = re.sub(r"(\d{4})(?=年)", lambda m: TC.num_to_cn(m.group(1), True), t)
    t = re.sub(r"(\d[\d,]*(?:\.\d+)?)(\+?)", lambda m: TC.num_to_cn(m.group(1)) + ("多" if m.group(2) else ""), t)
    return t.translate(str.maketrans({"《": "", "》": "", "「": "", "」": "", "『": "", "』": "", "（": "，", "）": "，",
                                      "(": "，", ")": "，", "：": "，", "；": "，", "、": "，", ":": "，", ";": "，",
                                      "—": "，", "…": "，", "~": "", "～": ""}))


def engine_text(mtext):
    """送進 CosyVoice 的文字:英文寫法 -> 書名號冒號刪除 -> 拼音標注 -> 簡體 -> 數字讀法/標點(標注 token 原樣保留);
    句尾保留問號/驚嘆號(ChatTTS 一律收成句號是它的限制)。"""
    end = mtext.rstrip()[-1:]
    t, _ = CT.apply_pron(TC.tts_pron.drop_title_colon(CT.apply_terms(mtext)))
    t = TC._cc.convert(t).strip()
    t = "".join(x if CT.TOKEN_RE.fullmatch(x) else _norm(x) for x in CT.TOKEN_RE.split(t))
    t = re.sub(r"[\s。?!？！.，,]+$", "", t)
    return t + ("？" if end in "?？" else "！" if end in "!！" else "。")


def norm_hyp(t):
    """辨識文字對齊 engine_text 的寫法:簡體 + 數字讀法/標點(同 engine_text 的後兩步)。"""
    return _norm(TC._cc.convert(t))


def asr_inserts(engine, hyp1, hyp2):
    """句中多唸字(品管 F,2026-10-22):主/副辨識在同一位置都比 engine_text 多出字 -> [dict(at, ref_ctx, asr, asr2)],沒有回 []。
    門檻 tts_asr.INSERT_MIN / INSERT_POS_TOL;只用 qc.json 已存的 engine_text / asr / asr2 就能離線重算(--requal)。"""
    if not (engine and hyp1 and hyp2):
        return []
    return TA.common_inserts(engine, norm_hyp(hyp1), norm_hyp(hyp2))


def requal(tag, dry_run=False):
    """--requal <tag>:不載模型,對 build/<tag>/tts_cosy3/ 的既有 qc.json 離線重算 asr_inserts;命中的句子在 qc.json 標
    passed=false、fails 加 asr_insert、寫入 asr_insert,並刪掉旁邊的 .key(下次 build 該句快取不命中 -> 重錄)。dry_run 只列不動。"""
    d = P.tts_dir(tag, "cosy3")
    hits = []
    for qf in sorted(list(d.glob("*.qc.json")) + list((d / "sub").glob("*.qc.json"))):
        try:
            rec = json.loads(qf.read_text(encoding="utf-8"))
        except ValueError:
            continue
        ins = asr_inserts(rec.get("engine_text"), rec.get("asr"), rec.get("asr2")) if rec.get("engine") == "cosy3" else []
        if not ins:
            continue
        unit = str(rec.get("idx") or qf.name[:-len(".qc.json")])
        hits.append((unit, rec.get("engine_text", ""), ins))
        print(f"[requal] {unit}: {ins}")
        if not dry_run:
            rec.update(passed=False, asr_insert=ins, fails=[*(rec.get("fails") or []), *([] if "asr_insert" in (rec.get("fails") or []) else ["asr_insert"])])
            qf.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            qf.with_name(qf.name[:-len(".qc.json")] + ".key").unlink(missing_ok=True)
    print(f"[requal] {tag}: 命中 {len(hits)} 句{'(dry-run,沒動檔)' if dry_run else '(已標 fail、刪 .key,下次 build 重錄)'}")
    return hits


def statement(text):
    t = text.rstrip()
    return t[-1:] in "。!！" and not re.search(r"[嗎呢吧][。!！]$", t)


# ------------------------------------------------------------ 合成子行程
class Worker:
    def __init__(self, ref, ref_text, device, log_path):
        env = os.environ.copy()
        home = P.TMP / "cosy_home"  # gdown / modelscope 會在使用者家目錄建快取:導到 tmp,不寫 C 槽
        home.mkdir(parents=True, exist_ok=True)
        env.update(USERPROFILE=str(home), HOME=str(home), PYTHONPATH=str(Path(__file__).resolve().parent))
        self.log = open(log_path, "w", encoding="utf-8")
        self.p = subprocess.Popen([str(COSY_ENV), "-X", "utf8", str(Path(__file__).with_name("cosy3_worker.py")),
                                   "--ref", str(ref), "--ref-text", str(ref_text), "--device", device],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                                  text=True, encoding="utf-8", env=env)
        self.log_path = log_path
        self.sr = self._read("@@READY")["sr"]

    def _read(self, tag):
        for line in self.p.stdout:
            if line.startswith(tag + " "):
                return json.loads(line[len(tag) + 1:])
        sys.exit(f"[cosy3] cosy3_worker 中止,見 {self.log_path}")

    def call(self, **job):
        self.p.stdin.write(json.dumps(job, ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        return self._read("@@RES")

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=60)
        self.log.close()


def load_mono(path):
    w, sr = sf.read(str(path), dtype="float32")
    w = w.mean(axis=1) if w.ndim > 1 else w
    if sr != SR:
        w = torchaudio.functional.resample(torch.from_numpy(np.ascontiguousarray(w)), sr, SR).numpy()
    return w


# ------------------------------------------------------------ 嘗試層級續跑快取(TTS_RESUME_DIR;Colab 斷線後接著做)
RESUME_VER = "r1"


def resume_dir(tag):
    """環境變數 TTS_RESUME_DIR 有設才啟用:<TTS_RESUME_DIR>/<tag>/;沒設回傳 None(本機預設:不建目錄、行為不變)。"""
    root = os.environ.get("TTS_RESUME_DIR")
    return Path(root) / tag if root else None


def resume_key(text, seed, speed, voice, ref_text, device):
    """一次合成嘗試的鍵:送引擎文字 + seed + speed + 參考音檔名與逐字稿 + 合成裝置(cuda:N 正規化成 cuda,分片換卡不影響鍵)。"""
    device = str(device).split(":")[0]
    return hashlib.sha1(json.dumps([RESUME_VER, text, seed, f"{speed:g}", voice, ref_text, device],
                                   ensure_ascii=False).encode("utf-8")).hexdigest()


def synth_one(worker, rdir, key, text, seed, speed, out):
    """一次合成嘗試 -> out(raw wav,裁切/FX 前);回傳 (worker 結果, 是否沿用續跑快取)。
    rdir 有值:<rdir>/<key>.wav 在就複製到 out、不呼叫 worker;不在就合成後存一份(先寫 .part 再改名,被砍不留半檔)。"""
    hit = rdir / f"{key}.wav" if rdir else None
    if hit is not None and hit.exists() and hit.stat().st_size > 0:
        shutil.copyfile(hit, out)
        return dict(ok=True), True
    res = worker.call(text=text, seed=seed, speed=speed, out=str(out))
    if hit is not None and res.get("ok"):
        rdir.mkdir(parents=True, exist_ok=True)
        part = hit.with_name(f"{key}.{os.getpid()}.part")   # 分片子行程可能同時寫同一鍵:暫存檔各自一份
        shutil.copyfile(out, part)
        os.replace(part, hit)
    return res, False


def resume_status(d):
    """--resume-status:印續跑快取目錄(單一 tag 或 TTS_RESUME_DIR 根)有幾筆、幾 MB。"""
    fs = list(Path(d).rglob("*.wav")) if Path(d).exists() else []
    mb = sum(f.stat().st_size for f in fs) / 2**20
    print(f"[resume] {d}: {len(fs)} 筆嘗試,{mb:.1f} MB")
    return len(fs), mb


def env_limit(name, default):
    """重錄上限的預設值:環境變數 name(CV_TTS_MAX_RETRY / CV_TTS_RATE_SEEDS;Colab 用)有設就用它,夾到 1–12;
    不是整數就忽略並警告。CLI 明傳仍優先;不進快取鍵。"""
    v = os.environ.get(name, "").strip()
    if not v:
        return default
    try:
        return max(1, min(int(v), 12))
    except ValueError:
        print(f"[cosy3] 警告:{name}={v!r} 不是整數,忽略(用 {default})", file=sys.stderr)
        return default


# ------------------------------------------------------------ 多 GPU 分片(Kaggle T4x2)
def shard_gpus(device="cuda", count=None):
    """分片數:只在 Kaggle(CV_REMOTE_PLATFORM=kaggle 或 KAGGLE_KERNEL_RUN_TYPE 存在;CV_REMOTE_PLATFORM=colab 強制關)、
    --device cuda、且偵測到 >= 2 張卡時 > 1。CV_TTS_GPUS(預設 Kaggle 2、其餘 1)設 1 = 關。count = 卡數(測試用)。"""
    forced = os.environ.get("CV_REMOTE_PLATFORM", "").strip().lower()
    kaggle = forced == "kaggle" if forced in ("kaggle", "colab") else "KAGGLE_KERNEL_RUN_TYPE" in os.environ
    if not kaggle or device != "cuda":
        return 1
    try:
        want = int(os.environ.get("CV_TTS_GPUS", "").strip() or 2)
    except ValueError:
        log(f"[cosy3] 警告:CV_TTS_GPUS={os.environ['CV_TTS_GPUS']!r} 不是整數,忽略(用 2)")
        want = 2
    return max(1, min(want, torch.cuda.device_count() if count is None else count))


def gpu_ids(n):
    """分片 i 用的實體卡號:CUDA_VISIBLE_DEVICES 有設就照它的順序,否則 0..n-1。"""
    vis = [x.strip() for x in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if x.strip()]
    return (vis or [str(i) for i in range(n)])[:n]


class Remote:
    """--shard-serve 子行程(同 argv、CUDA_VISIBLE_DEVICES 只露一張卡 -> 裝置字串仍是 cuda,續跑快取鍵不變):
    自己載 CosyVoice3 + 主品管,make / cache 回 pickle (w, m[, hit]);判定(check)與副辨識留在本行程。stderr 加 [g<i>] 前綴轉印。"""

    def __init__(self, i, gpu, argv):
        self.i = i
        self.p = subprocess.Popen([sys.executable, "-X", "utf8", os.path.abspath(__file__), *argv, "--shard-serve", str(i)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu)))
        threading.Thread(target=self._relay, daemon=True).start()

    def _relay(self):
        for line in self.p.stderr:
            sys.stderr.write(f"[g{self.i}] " + line.decode("utf-8", "replace"))
            sys.stderr.flush()

    def _recv(self):
        try:
            return pickle.load(self.p.stdout)
        except (EOFError, pickle.UnpicklingError, OSError):
            sys.exit(f"[cosy3] 分片 g{self.i} 子行程中止(見上方 [g{self.i}] log)")

    def ready(self):
        """等子行程載入完成;失敗回 False(呼叫端少用這一片,不中止)。"""
        try:
            return self._recv() == "ready"
        except SystemExit as e:
            log(f"{e};改少用一張卡")
            self.p.kill()
            return False

    def call(self, *req):
        pickle.dump(req, self.p.stdin)
        self.p.stdin.flush()
        return self._recv()

    def make(self, j, seed, speed):
        return self.call("make", j, seed, speed)

    def cache(self, j):
        return self.call("cache", j)

    def close(self):
        try:
            pickle.dump(None, self.p.stdin)
            self.p.stdin.close()
        except OSError:
            pass
        self.p.wait(timeout=120)


class Shards:
    """executor 0 = 本行程(None:用本行程的 worker/qc),其餘 = Remote。par(items, body, key) 用共用工作佇列:每條執行緒
    綁一個 executor,誰先做完誰拿下一項;body 內的 make / from_cache 經 _tl.ex 分派。只有一個 executor 時 = 原本的依序 for 迴圈。"""

    def __init__(self, remotes=()):
        self.ex = [None, *remotes]
        self.lock = threading.Lock()
        self.stats = [dict(gpu=i, lines=set(), tasks=0, sec=0.0) for i in range(len(self.ex))]

    @property
    def n(self):
        return len(self.ex)

    def par(self, items, body, key=None):
        items = list(items)
        if self.n == 1:
            for x in items:
                body(x)
            return
        errs = []

        def run(i):
            _tl.ex, _tl.tag = self.ex[i], f"[g{i}] "
            st = self.stats[i]
            while True:
                with self.lock:
                    if errs or not items:
                        return
                    x = items.pop(0)
                t = time.time()
                try:
                    body(x)
                except BaseException as e:  # noqa: BLE001 含 sys.exit:帶回主執行緒再拋
                    with self.lock:
                        errs.append(e)
                    return
                with self.lock:
                    st["tasks"] += 1
                    st["sec"] += time.time() - t
                    if key:
                        st["lines"].add(key(x))

        ths = [threading.Thread(target=run, args=(i,), daemon=True) for i in range(self.n)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        if errs:
            raise errs[0]

    def summary(self):
        """每片:lines = 經手的句數(不重複)、tasks = 工作數(一句一階段算一個)、minutes = 忙碌分鐘。"""
        return [dict(gpu=s["gpu"], lines=len(s["lines"]), tasks=s["tasks"], minutes=round(s["sec"] / 60, 1))
                for s in self.stats]

    def close(self):
        for ex in self.ex[1:]:
            ex.close()


SHARDS_FILE = "_cosy3_shards.json"   # jobs 同目錄;只有分片時才寫(colab_run 讀進 run_status steps)


# ------------------------------------------------------------ 主程式
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="?")
    ap.add_argument("--requal", metavar="TAG", help="不合成:對 build/<TAG>/tts_cosy3 既有 qc.json 離線重算句中多唸字品管,命中的標 fail 並刪 .key(重錄)")
    ap.add_argument("--dry-run", action="store_true", help="--requal 只列命中的句子,不動檔")
    ap.add_argument("--ref", help="參考音 wav(同主檔名 .txt 為逐字稿;合成時必給)")
    ap.add_argument("--speed", type=float, default=1.18)
    ap.add_argument("--voice", help="標籤(build.py 一律會傳)")
    ap.add_argument("--rate", default="+0%", help="標籤(語速由 --speed 決定)")
    ap.add_argument("--device", choices=["cuda", "cpu"], default="cuda", help="合成裝置(品管固定用 GPU)")
    ap.add_argument("--seed", type=int, default=2024)
    ap.add_argument("--report")
    ap.add_argument("--asr-model", default=TA.PRIMARY, help="主辨識器 qwen06 | whisper:<size>(舊片重渲染)")
    ap.add_argument("--asr2", default=TA.SECONDARY, help="副辨識器(CPU,通過主品管者不一致重錄,其餘最終音檔只記 asr2_bad);none = 不跑")
    ap.add_argument("--max-retry", type=int, default=env_limit("CV_TTS_MAX_RETRY", 6))
    ap.add_argument("--rate-seeds", type=int, default=env_limit("CV_TTS_RATE_SEEDS", 6))
    ap.add_argument("--pitch-tol", type=float, default=0.18)
    ap.add_argument("--sim-min", type=float, default=0.85)
    ap.add_argument("--spk-min", type=float, default=0.30)
    ap.add_argument("--spk-k", type=float, default=2.5)
    ap.add_argument("--rate-tol", type=float, default=TC.RATE_TOL)
    ap.add_argument("--tail-rise", type=float, default=12.0, help="陳述句句尾 F0 斜率上限(半音/秒)")
    ap.add_argument("--comma-profile", choices=sorted(TP.PROFILES), default="std",
                    help="逗號停頓側寫:std = 現行(預設);long = 長句逗號停頓較長(僅供本機 A/B 試聽)")
    ap.add_argument("--speed-min", type=float, default=0.7)
    ap.add_argument("--speed-max", type=float, default=1.6)
    ap.add_argument("--resume-tag", help="續跑快取子目錄名(TTS_RESUME_DIR 有設才用;預設由 jobs.json 所在的 build/<tag> 推)")
    ap.add_argument("--resume-status", metavar="DIR", help="不合成:印續跑快取目錄的筆數與 MB")
    ap.add_argument("--shard-serve", type=int, default=0, help=argparse.SUPPRESS)   # 內部:多 GPU 分片子行程編號
    a = ap.parse_args()
    if a.shard_serve:   # 協定走原 stdout(pickle);fd 1 改指 stderr,模型載入的雜訊不會混進協定
        proto = os.fdopen(os.dup(1), "wb")
        os.dup2(2, 1)
        sys.stdout = sys.stderr
    if a.resume_status:
        resume_status(a.resume_status)
        return
    if a.requal:
        requal(a.requal, a.dry_run)
        return
    if not a.jobs or not a.ref:
        ap.error("要給 jobs.json 與 --ref(或 --requal TAG)")
    ref = Path(a.ref)
    ref_text = ref.with_suffix(".txt")
    if not ref.exists() or not ref_text.exists():
        sys.exit(f"[cosy3] 找不到參考音或逐字稿: {ref} / {ref_text}")
    jobs = json.load(open(a.jobs, encoding="utf-8"))
    jdir = Path(a.jobs).resolve().parent
    report = a.report or os.path.splitext(a.jobs)[0] + ".qc.json"
    sfx = f"_g{a.shard_serve}" if a.shard_serve else ""
    work = jdir / f"_cosy_work{sfx}"
    work.mkdir(exist_ok=True)
    voice = ref.name

    try:
        lock_tag = jdir.resolve().relative_to(P.BUILD.resolve()).parts[0]
    except ValueError:
        lock_tag = jdir.name
    rdir = resume_dir(a.resume_tag or lock_tag)
    ref_txt = ref_text.read_text(encoding="utf-8").strip()
    resume_hits = [0]
    remotes = []
    if not a.shard_serve:
        wait_vram(lock_tag)
        (jdir / SHARDS_FILE).unlink(missing_ok=True)
        n_gpu = shard_gpus(a.device)
        remotes = [Remote(i, g, sys.argv[1:]) for i, g in enumerate(gpu_ids(n_gpu)) if i]   # 先開:與本行程載模型重疊
    t0 = time.time()
    worker = Worker(ref, ref_text, a.device, jdir / f"_cosy3_worker{sfx}.log")
    qc = TC.QC(a.asr_model, a.spk_min, pron_rules=True)
    ref_w = load_mono(ref)
    qc.spk_base = qc.embed(ref_w)
    torch.cuda.reset_peak_memory_stats()
    log(f"[cosy3] 載入 {time.time() - t0:.0f}s;{len(jobs)} 個單位,參考音 {voice},speed {a.speed}")
    t1 = time.time()

    def fx(w, tag):
        src, dst = work / f"{tag}.trim.wav", work / f"{tag}.fx.wav"
        sf.write(str(src), w, SR, subtype="FLOAT")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", FX, "-c:a", "pcm_f32le", str(dst)],
                       check=True)
        return load_mono(dst)

    def asr_loose(m, text):
        """英文句的 ASR 寬鬆比對(只會放寬 sim / tail_ok):英文段忽略大小寫/空白/點;某英文段辨識不出就只比中文。"""
        ref_t = re.sub(r"(?<=[A-Za-z])\s*[點点]\s*(?=[A-Za-z])", ".", text)
        key = lambda t: re.sub(r"[\s./\\_-]", "", t.lower())  # noqa: E731
        segs = [key(x) for x in re.findall(r"[A-Za-z][A-Za-z.\s]*[A-Za-z]|[A-Za-z]", ref_t)]
        if not segs:
            return
        hyp = m["asr"]
        for term, alts in CT.ASR_ALIAS.items():
            if term in text:
                for alt in sorted(alts, key=len, reverse=True):
                    hyp = hyp.replace(alt, term)
        runs = re.findall(r"[a-z0-9]+", key(hyp))
        en = {k: any(TC._ratio(k, x) >= 0.75 for x in runs) for k in segs}
        zh_only = not all(en.values())
        r_n, h_n = key(TC.norm_text(ref_t)), key(TC.norm_text(hyp))
        if zh_only:
            r_n, h_n = re.sub(r"[a-z0-9]", "", r_n), re.sub(r"[a-z0-9]", "", h_n)
        sim = round(max(TC._ratio(r_n, h_n), m["sim_pinyin"]), 3) if r_n else m["sim"]
        tail = TC.tail_ok(ref_t, hyp)
        m["asr_loose"] = dict(mode="zh_only" if zh_only else "loose", sim_strict=m["sim"], sim=sim,
                              tail_ok_strict=m["tail_ok"], tail_ok=tail)
        m["sim"], m["tail_ok"] = max(m["sim"], sim), m["tail_ok"] or tail

    def measure(w, j, tag):
        w, m = TC.measure(qc, w, j["mtext"])
        asr_loose(m, j["mtext"])
        m["term_misread"] = CT.asr_rejects(j["mtext"], {"asr": m["asr"]}) + TQ.loose_misses(j["mtext"], m["asr"])
        qf = work / f"{tag}.qc.wav"
        sf.write(str(qf), w, SR)
        tf = worker.call(cmd="tail_f0", wav=str(qf))
        m.update(statement=statement(j["mtext"]), tail_slope=tf.get("slope"), tail_hz=tf.get("hz"))
        if j["mtext"] != j["text"]:
            m["say_t"] = None  # 量測文字(英文詞換回)與送配音文字長度不同,字元時間對不回 job text
        return w, m

    def make_here(j, seed, speed):
        tag = f"{j['k']}_{seed}_{speed:g}"
        raw = work / f"{tag}.raw.wav"
        res, hit = synth_one(worker, rdir, rdir and resume_key(j["engine"], seed, speed, voice, ref_txt, a.device),
                             j["engine"], seed, speed, raw)
        if not res["ok"]:
            sys.exit(f"[cosy3] 第 {j.get('idx')} 句合成失敗: {res['err']}")
        w, m = measure(fx(gentle_trim(load_mono(raw), SR)[0], tag), j, tag)
        m.update(source="synth", seed=seed, speed=speed, no_cut=False)
        return w, m, hit

    def make(j, seed, speed):
        """一次合成嘗試;分片執行緒內交給綁定的 executor(Remote 或本行程)。"""
        ex = getattr(_tl, "ex", None)
        w, m, hit = ex.make(j, seed, speed) if ex else make_here(j, seed, speed)
        with stat_lock:
            resume_hits[0] += hit
        return w, m

    def from_cache(j):
        w, m = measure(load_mono(j["out"]), j, f"{j['k']}_cache")
        m.update(source="cache", seed=None, speed=None, no_cut=False)
        rec = TP.load_qc(os.path.splitext(j["out"])[0] + ".qc.json")
        m["comma_runon"] = TP.runon_from_rec(rec)   # 最終音檔已插過靜音,原始靜音只能看舊紀錄;都沒有 = 不判
        ats = TP.inserted_ats(rec)
        if ats:   # 舊音檔曾插入靜音:用插入位置驗證重驗(插錯 -> pause_misplaced,check 判未過、換 seed 重錄)
            items = [(p, (p["t0"] + p["t1"]) / 2) for p in m.get("pauses") or [] if p["at"] in ats and p["sil"] > 0]
            pv = verify_inserts(w, j["mtext"], items)
            m["pause_verify"] = pv
            bad = [x["at"] for x in pv if x["ok"] is False]
            if bad:
                m["pause_misplaced"] = bad
        return w, m

    def cache_any(j):
        ex = getattr(_tl, "ex", None)
        return ex.cache(j) if ex else from_cache(j)

    def alias_back(hyp, text):
        """辨識結果裡 cosy_terms `_asr_alias` 的音譯/別寫換回原文英文詞(只換這句文字有的詞)。"""
        for term, alts in CT.ASR_ALIAS.items():
            if term in text:
                for alt in sorted(alts, key=len, reverse=True):
                    hyp = hyp.replace(alt, term)
        return hyp

    def verify_inserts(w, text, items):
        """插入位置驗證:items = [(停頓, 插入靜音中點秒數)];各在中點切開,用主辨識器辨識前 TP.HEAD_SEC 秒,
        結尾要對到原文該停頓標點前的字(TP.head_match;拼音鍵容忍同音字)。回傳 [dict(at, t, head_asr, ok)]。"""
        us = [u[0] for u in TP.units(TC.prep_text(text))]
        out = []
        for p, t in items:
            seg = w[max(0, int((t - TP.HEAD_SEC) * SR)): int(t * SR)]
            hyp = qc.transcribe(seg)[0] if len(seg) >= int(0.2 * SR) else ""
            hu = [u for u, _, _ in TP.hyp_units([(alias_back(hyp, text), 0.0, 1.0)])]
            out.append(dict(at=p["at"], t=round(t, 3), head_asr=hyp, ok=TP.head_match(us[: p["i"] + 1], hu, TC._align_key)))
        return out

    def check(m):
        TC.check(m, base_f0, base_spc, a, fit)
        if m.get("statement") and m.get("tail_slope") is not None and m["tail_slope"] > a.tail_rise:
            m["fails"].append("tail_rise")
            m["score"] = round(m["score"] - 0.3 - 0.02 * (m["tail_slope"] - a.tail_rise), 3)
        if m.get("term_misread"):   # 英文詞辨識出否決字串(cosy_terms _asr_reject):換 seed 重錄
            m["fails"].append("term_misread")
            m["score"] = round(m["score"] - 0.3, 3)
        if m.get("pause_misplaced"):   # 插入的靜音插錯位置(插入位置驗證);不在 POST_FIXABLE,換 seed 重錄
            m["fails"].append("pause_misplaced")
            m["score"] = round(m["score"] - 0.3, 3)
        # 詞界自發長停頓(>= STRAY_WB_FAIL):stray_pause 未過、換 seed 重錄(重錄迴圈不因 comma_only 提早停);
        # 後處理剪短過的(stray_wb_cut)仍算未過
        TP.judge_runon(m)   # 模型連讀:原始靜音 < COMMA_RUNON_MIN,不在 POST_FIXABLE,換 seed 重錄;後處理重量測沿用,插入過不了關
        m["stray_wb_long"] = TP.wb_long(m.get("strays"))
        if (m["stray_wb_long"] or m.get("stray_wb_cut")) and "stray_pause" not in m["fails"]:
            m["fails"].append("stray_pause")
            m["score"] = round(m["score"] - 0.1 * max(1, len(m["stray_wb_long"])), 3)
        if m.get("term_inconsistent"):   # 跨句一致性(整批後判定;後處理重量測沿用)
            m["fails"].append("term_inconsistent")
            m["score"] = round(m["score"] - 0.3, 3)
        return not m["fails"]

    def judge2(text, hyp):
        """副辨識回查:同主品管的比對(含 pron_rules 位置)+ 英文句寬鬆比對。"""
        d = TC.asr_judge(text, hyp, True)
        mm = dict(asr=hyp, sim=d["sim"], sim_pinyin=d["sim_pinyin"], tail_ok=True)
        asr_loose(mm, text)
        return mm["sim"], d["pron_bad"]

    def insert_post(m, text, hyp2):
        """副辨識回來後的多唸字判定:主/副辨識同位置都多出字 -> 記 asr_insert 並算 asr2_bad(進 dual_phase 重錄)。"""
        ins = asr_inserts(engine_text(text), m.get("asr"), hyp2)
        m["asr_insert"] = ins
        rej = CT.asr_rejects(text, {"asr": m.get("asr"), "asr2": hyp2})   # 副辨識的英文詞否決字串也算(asr2_bad 進重錄)
        m["term_misread"] = rej + [x for x in m.get("term_misread") or [] if x.get("kind") == "loose"]   # 主辨識音近不過的保留
        return bool(ins) or any(x["src"] == "asr2" for x in rej)

    if a.shard_serve:   # 分片子行程:只做合成 + 量測;判定、副辨識、後處理、寫檔都在主行程
        pickle.dump("ready", proto)
        proto.flush()
        while True:
            try:
                req = pickle.load(sys.stdin.buffer)
            except EOFError:
                break
            if req is None:
                break
            op, j, *rest = req
            pickle.dump(make_here(j, *rest) if op == "make" else from_cache(j), proto)
            proto.flush()
        worker.close()
        qc.close()
        shutil.rmtree(work, ignore_errors=True)
        return

    stat_lock = threading.Lock()
    shards = Shards([r for r in remotes if r.ready()])
    if remotes:
        log(f"[cosy3] 多 GPU 分片 {shards.n} 片(g0 = 本行程;副辨識只在 g0 跑一份)")
    kof = lambda r: r["job"]["k"]  # noqa: E731
    sec = TA.Second(judge2, a.sim_min, post=insert_post) if a.asr2 != "none" else None
    text_of, wav16 = (lambda r: r["job"]["mtext"]), qc.to16

    for k, j in enumerate(jobs):
        j["k"] = k
        j["mtext"] = CT.unsay(j["text"])
        j["engine"] = engine_text(j["mtext"])
    g2p_bg = TG.Background([j["text"] for j in jobs], log)   # 第三意見(T3):只依文字,背景算完,最終紀錄時取用

    # 第一輪
    res = [None] * len(jobs)
    done = [0]

    def first(j):
        w, m = cache_any(j) if j.get("verify") and os.path.exists(j["out"]) else make(j, a.seed, a.speed)
        res[j["k"]] = dict(job=j, w=w, m=m, tries=[m])
        with stat_lock:
            done[0] += 1
            n = done[0]
        if n % 20 == 0:
            log(f"  pass1 {n}/{len(jobs)}")
    shards.par(jobs, first, key=lambda j: j["k"])

    base_file = jdir / "_qc_base_cosy3.json"
    base = None
    if len(jobs) < BASE_MIN and base_file.exists():
        b = json.loads(base_file.read_text(encoding="utf-8"))
        if (b.get("qc_ver"), b.get("voice"), b.get("speed")) == (QC_VER, voice, a.speed):
            base = b
    if base is None:
        base = dict(qc_ver=QC_VER, voice=voice, speed=a.speed, n=len(jobs),
                    base_f0=statistics.median(r["m"]["f0"] for r in res if r["m"]["f0"] > 0),
                    base_spc=statistics.median(r["m"]["spc"] for r in res), spk_fit=list(TC.fit_spk(res)))
    base_f0, base_spc, fit = base["base_f0"], base["base_spc"], tuple(base["spk_fit"])
    log(f"[cosy3] 基準(n={base['n']}): f0={base_f0:.1f} spc={base_spc:.3f} 聲紋 sim~{fit[0]:.3f}+{fit[1]:.3f}*ln(dur) "
        f"sigma={fit[2]:.3f}")
    for r in res:
        r["ok"] = check(r["m"])
        if sec and r["ok"]:
            sec.submit(r["m"], text_of(r), wav16(r["w"]))  # 副辨識在背景跑,與主品管重試重疊
    log(f"[cosy3] 第一輪通過 {sum(r['ok'] for r in res)}/{len(res)}")

    def next_seed(r):
        used = {t["seed"] for t in r["tries"] if t.get("seed") is not None}
        k = 1
        while a.seed + 1009 * k in used:
            k += 1
        return a.seed + 1009 * k

    def retry2(r):
        w, m = make(r["job"], next_seed(r), a.speed)
        return w, m, check(m)

    todo = [r for r in res if not r["ok"]]
    done[0] = 0

    def retry1(r):
        TP.retry_best(r, retry2, a.max_retry, stop_retry)
        with stat_lock:
            done[0] += 1
            n = done[0]
        if n % 10 == 0:
            log(f"  retry {n}/{len(todo)}")
    shards.par(todo, retry1, key=kof)

    # 雙辨識:通過主品管的音檔再給副辨識器(Fun-ASR-Nano)聽,不一致就重錄(計入 --max-retry),仍不一致記 asr2_bad
    if sec:
        n2, bad2 = TA.dual_phase(res, sec, retry2, a.max_retry, text_of, wav16,
                                 par=(lambda xs, f: shards.par(xs, f, kof)) if shards.n > 1 else None)
        log(f"[cosy3] 副辨識 {sec.name}:因不一致重錄 {n2} 次,仍不一致 {bad2} 句")

    # 語速:基準 = 整批最終音檔的中位數(句數夠多存回基準檔,小批次沿用)
    cps_med = base.get("base_cps")
    if cps_med is None or len(jobs) >= BASE_MIN:
        cps_med = statistics.median(r["m"]["cps"] for r in res)
        base["base_cps"] = cps_med
    if len(jobs) >= BASE_MIN:
        base_file.write_text(json.dumps(base, indent=1), encoding="utf-8")
    dev = lambda m: m["cps"] / cps_med - 1  # noqa: E731
    out_of_range = [r for r in res if abs(dev(r["m"])) > a.rate_tol]
    log(f"[cosy3] 語速中位數 {cps_med:.3f} 字/有聲秒;超出 ±{a.rate_tol:.0%} 的單位 {len(out_of_range)}/{len(res)}")

    def rate1(x):
        n, r = x
        d0 = dev(r["m"])
        cands = [(abs(dev(r["m"])), r["m"], r["w"])] if r["ok"] or TC.comma_only(r["m"]) else []
        r["rate_tries"] = [dict(seed=r["m"].get("seed"), speed=r["m"].get("speed"), cps=r["m"]["cps"],
                                dev=round(d0, 3), ok=r["ok"], start=True)]
        new = 0
        while new < a.rate_seeds and not (cands and min(c[0] for c in cands) <= a.rate_tol / 2):
            # 以偏差最小那次為基準、調幅減半、限制在 --speed ±20%(2026-10-17:以上一次為基準會在 1.03-1.36 震盪)
            best = min((t for t in r["tries"] if t.get("speed")), key=lambda t: abs(dev(t)), default=None)
            sp = (best["speed"] / (1 + 0.5 * dev(best))) if best else a.speed / (1 + 0.5 * d0)
            sp = round(min(a.speed_max, a.speed * 1.2, max(a.speed_min, a.speed * 0.8, sp)), 2)
            w, m = make(r["job"], next_seed(r), sp)
            ok = check(m)
            r["tries"].append(m)
            new += 1
            r["rate_tries"].append(dict(seed=m["seed"], speed=sp, cps=m["cps"], dev=round(dev(m), 3), ok=ok, fails=m["fails"]))
            if ok or TC.comma_only(m):
                cands.append((abs(dev(m)), m, w))
        if cands:
            _, m, w = min(cands, key=lambda c: (c[0] > a.rate_tol, bool(c[1]["fails"]), c[0]))
            r["w"], r["m"], r["ok"] = w, m, not m["fails"]
        log(f"  rate {n}/{len(out_of_range)}: {r['job'].get('idx')} {d0:+.0%} -> {dev(r['m']):+.0%} (新 seed {new})")
    shards.par(enumerate(out_of_range, 1), rate1, key=lambda x: kof(x[1]))

    # 跨句一致性(整批一次):仍直送英文的詞在 >= 2 句時,主辨識在該詞位置的寫法與多數寫法差異大且不音近原詞 -> term_inconsistent,
    # 換 seed 重錄(計入 --max-retry;新音檔過主品管或只差後處理項、且寫法回到多數才換上),仍不過 = 品管未過;無多數只列優先聽
    incon, listen, majors = TQ.inconsistent([(k, r["job"]["mtext"], r["m"].get("asr")) for k, r in enumerate(res)])
    for k, xs in listen.items():
        res[k]["m"]["term_listen"] = xs

    def incon1(x):   # 判定已在上一行對全部句子做完一次;這裡只把各句重錄分給各片
        k, xs = x
        r = res[k]
        r["m"]["term_inconsistent"] = xs
        r["ok"] = check(r["m"])
        while len(r["tries"]) - 1 < a.max_retry:
            w, m = make(r["job"], next_seed(r), r["m"].get("speed") or a.speed)
            ok = check(m)
            r["tries"].append(m)
            if (ok or TC.comma_only(m)) and not TQ.off_major(r["job"]["mtext"], m["asr"], majors):
                r["w"], r["m"], r["ok"] = w, m, ok
                break
        log(f"  term_inconsistent {r['job'].get('idx')} {xs[0]['term']}「{xs[0]['got']}」: {'重錄通過' if not r['m'].get('term_inconsistent') else '仍未過'}")
    shards.par(incon.items(), incon1, key=lambda x: x[0])

    # 最終音檔的後處理(同 tts_chattts.main 結尾):句中停頓補/剪 -> 多餘停頓剪短 -> 停頓內部與句尾雜音清除
    def remeasure(r, w2):
        w2, mm = measure(w2, r["job"], f"{r['job']['k']}_post")
        m2 = dict(r["m"], **{k: v for k, v in mm.items() if k not in ("no_cut", "source", "seed", "speed")})
        check(m2)
        return w2, m2, [f for f in m2["fails"] if f not in r["m"]["fails"] and f not in TC.POST_FIXABLE]

    def fix_commas(r, ps, skip=()):
        """句中停頓補/剪(跳過 skip 裡的停頓 i);回傳 (新波形, 新指標, 插入的 {i: 中點秒}) 或 None(沒動作或修完變差已記 *_reverted)。"""
        m, edits = r["m"], []
        w2, acts = TP.fix_pauses(r["w"], SR, [p for p in ps if p["i"] not in skip], r["job"]["mtext"], a.comma_profile, edits)
        if not acts:
            return None
        w2, m2, worse = remeasure(r, w2)
        if worse or len(m2["pauses"]) != len(ps):
            m["pause_fix_reverted"] = worse or ["pauses"]
            return None
        m2["pause_fix"] = [dict(at=p["at"], act=acts.get(p["i"], "none"), before=p["sil"], after=q["sil"])
                           for p, q in zip(ps, m2["pauses"])]
        return w2, m2, TP.insert_mids(edits, SR)

    def post(r):
        """最終音檔的後處理;回傳是否有插入的靜音因插錯位置被退回(該句記 pause_misplaced,未過)。"""
        m, misplaced = r["m"], False
        ps = m.get("pauses") or []
        if TP.out_of_range(ps, r["job"]["mtext"], a.comma_profile):
            got = fix_commas(r, ps)
            if got and got[2]:   # 插入位置驗證(只驗插入,不驗剪短)
                items = [(p, got[2][p["i"]]) for p in ps if p["i"] in got[2]]
                pv = verify_inserts(got[0], r["job"]["mtext"], items)
                bad = {p["i"] for (p, _), x in zip(items, pv) if x["ok"] is False}
                if bad:   # 插錯的那幾處退回不插,其餘(含剪短)重做一次
                    misplaced = True
                    got = fix_commas(r, ps, bad)
                    tgt = got[1] if got else m
                    tgt["pause_misplaced"] = [p["at"] for p in ps if p["i"] in bad]
                    tgt["fails"] = tgt["fails"] + ["pause_misplaced"]
                (got[1] if got else m)["pause_verify"] = pv
            if got:
                r["w"], r["m"], m = got[0], got[1], got[1]
        ss = m.get("strays") or []
        if ss:
            w2, n_cut = TP.fix_strays(r["w"], SR, ss)
            if n_cut:
                w2, m2, worse = remeasure(r, w2)
                if worse or len(m2["pauses"]) != len(m["pauses"]):
                    m["stray_fix_reverted"] = worse or ["pauses"]
                else:
                    m2["stray_fix"] = [dict(at=x["at"], kind=x.get("kind"), before=x["sil"], after=TP.stray_keep(x))
                                       for x in ss]
                    cut = TP.wb_long(ss)
                    if cut:   # 詞界長停頓重錄用完仍有:剪短但仍算未過
                        m2["stray_wb_cut"] = cut
                        m2["fails"] = m2["fails"] + ([] if "stray_pause" in m2["fails"] else ["stray_pause"])
                    r["w"], r["m"], m = w2, m2, m2
        w2, plog = TP.clean_pauses(r["w"], SR, m.get("pauses") or [])
        w2, tail_ms = TP.clean_tail(w2, SR)
        if plog or tail_ms:
            w2, m2, worse = remeasure(r, w2)
            if worse or len(m2["pauses"]) != len(m["pauses"]):
                m["clean_reverted"] = worse or ["pauses"]
            else:
                m2["pause_clean"] = plog
                if tail_ms:
                    m2["tail_clean_ms"] = tail_ms
                r["w"], r["m"], m = w2, m2, m2
        bad = TP.comma_bad(m.get("pauses") or [], r["job"]["mtext"], a.comma_profile)
        if bad:
            m["comma_bad"] = bad
            m["fails"] = [f for f in m["fails"] if f != "comma_short"] + ["comma_bad"]
        r["ok"] = not m["fails"]
        return misplaced

    # 插錯位置的句子換 seed 重錄(計入 --max-retry):新音檔後處理完全通過才換上,否則留原音檔(comma_bad + pause_misplaced,未過)
    for r in [r for r in res if post(r)]:
        while len(r["tries"]) - 1 < a.max_retry:
            w, m = make(r["job"], next_seed(r), r["m"].get("speed") or a.speed)
            r["tries"].append(m)
            if not (check(m) or TC.comma_only(m)):
                continue
            r2 = dict(job=r["job"], w=w, m=m)
            if not post(r2) and r2["ok"]:
                r["w"], r["m"], r["ok"] = r2["w"], r2["m"], True
                break
        log(f"  pause_misplaced {r['job'].get('idx')}: {'重錄通過' if r['ok'] else '仍未過'}")

    if sec:
        TA.final_check(res, sec, text_of, wav16)
        for r in res:   # 重錄次數用完仍有句中多唸字 / 英文詞否決字串:品管不過(列未通過,不擋交付)
            for k in ("asr_insert", "term_misread"):
                if r["m"].get(k) and k not in r["m"]["fails"]:
                    r["m"]["fails"] = r["m"]["fails"] + [k]
                    r["ok"] = False
    g2p_res = g2p_bg.wait()
    lines, audio_s = [], 0.0
    for r in res:
        j, m = r["job"], r["m"]
        m.update(rate_med=round(cps_med, 3), rate_dev=round(dev(m), 3), rate_ok=abs(dev(m)) <= a.rate_tol,
                 rate_retried=len(r.get("rate_tries", [])) - 1 if r.get("rate_tries") else 0)
        if not m["rate_ok"] and "rate" not in m["fails"]:
            m["fails"] = m["fails"] + ["rate"]
            r["ok"] = False
        sf.write(j["out"], r["w"], SR)
        audio_s += len(r["w"]) / SR
        pron_new, en_new = CT.unverified(j["text"])
        rec = dict(qc_ver=QC_VER, engine="cosy3", idx=j.get("idx"), text=j["text"], measure_text=j["mtext"],
                   engine_text=j["engine"], pron_hits=CT.pron_hits(j["text"]), term_hits=CT.term_hits(j["text"]), passed=r["ok"], retries=len(r["tries"]) - 1, final=True,
                   wav_sha1=hashlib.sha1(open(j["out"], "rb").read()).hexdigest(),
                   cosy_pron_unverified=pron_new, cosy_en_unverified=en_new)
        rec.update(TG.record_fields(g2p_res, j["text"]))   # g2pW 與規則表讀音不一致;只寫紀錄,不改送引擎文字/快取鍵/QC_VER
        rec.update(TC._public(m))
        rec["comma_profile"] = a.comma_profile
        rec.update(asr_engine=qc.asr_engine, asr2_engine=sec.name if sec else None, **TA.fields(m))
        if r.get("rate_tries"):
            rec["rate_tries"] = r["rate_tries"]
        rec["attempts"] = [dict(source=x["source"], seed=x["seed"], speed=x.get("speed"), fails=x["fails"],
                                score=x["score"], sim=x["sim"], spk_sim=x["spk_sim"], f0_ratio=x["f0_ratio"],
                                cps=x["cps"], quiet_ms=x["quiet_ms"], tail_slope=x.get("tail_slope"), asr=x["asr"],
                                comma=[p["sil"] for p in x.get("pauses") or []],
                                stray=[p["sil"] for p in x.get("strays") or []]) for x in r["tries"]]
        json.dump(rec, open(os.path.splitext(j["out"])[0] + ".qc.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        lines.append(rec)
    worker.close()
    shards.close()
    qc.close()
    if sec:
        sec.close()
    if shards.n > 1:
        summ = shards.summary()
        (jdir / SHARDS_FILE).write_text(json.dumps(dict(gpus=shards.n, shards=summ), indent=1), encoding="utf-8")
        log("[cosy3] 分片:" + ";".join(f"g{s['gpu']} {s['lines']} 句 {s['tasks']} 工作 {s['minutes']} 分" for s in summ))
    for f in work.glob("*.wav"):
        f.unlink()
    kept = [x["idx"] for x in lines if x["source"] == "cache"]
    failed = [x["idx"] for x in lines if not x["passed"]]
    json.dump(dict(qc_ver=QC_VER, engine="Fun-CosyVoice3-0.5B zero_shot", voice=voice, speed=a.speed, fx=FX, base=base,
                   thresholds=dict(pitch_tol=a.pitch_tol, sim_min=a.sim_min, spk_min=a.spk_min, spk_k=a.spk_k,
                                   rate_tol=a.rate_tol, tail_rise=a.tail_rise, max_retry=a.max_retry,
                                   rate_seeds=a.rate_seeds, min_tail_quiet=TC.MIN_TAIL_QUIET,
                                   end_margin_ms=TC.END_MARGIN_MS, tail_extra_ms=TC.TAIL_EXTRA_MS,
                                   comma_min=TP.COMMA_MIN, comma_max=TP.COMMA_MAX, comma_profile=a.comma_profile,
                                   comma_target=TP.COMMA_TARGET, comma_runon_min=TP.COMMA_RUNON_MIN,
                                   stray_min=TP.STRAY_MIN, stray_wb_fail=TP.STRAY_WB_FAIL,
                                   sound_min=TQ.SOUND_MIN, consist_min=TQ.CONSIST_MIN),
                   kept_from_cache=len(kept), rerecorded=len(lines) - len(kept), failed=failed, lines=lines),
              open(report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    t_gen = time.time() - t1
    log(f"[cosy3] qc 沿用既有音檔={len(kept)} 重錄={len(lines) - len(kept)} 未通過={failed} gen={t_gen:.0f}s "
        f"audio={audio_s:.1f}s rtf={t_gen / max(audio_s, 1e-6):.2f} peakVRAM(qc)={torch.cuda.max_memory_reserved() / 2**20:.0f}MB")
    if rdir:   # 整批成功才走到這裡;TTS_RESUME_KEEP=1(Colab)留到打包後再刪
        log(f"[cosy3] 續跑快取 {rdir}: 沿用 {resume_hits[0]} 次合成嘗試")
        if os.environ.get("TTS_RESUME_KEEP") != "1":
            shutil.rmtree(rdir, ignore_errors=True)


if __name__ == "__main__":
    main()
