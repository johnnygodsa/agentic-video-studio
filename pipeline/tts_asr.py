"""配音品管的語音辨識(PLAN_語音辨識升級_2026-10-21 §3.7;在 tts_env_chattts 執行,tts_chattts.QC / tts_cosy3 使用)。
- `ASR(spec)`:統一介面 `transcribe(16 kHz float32) -> (文字, [(字詞, 起, 迄)])`。spec:
  qwen06(主辨識器,預設):Qwen3-ASR-0.6B,GPU,子行程 asr_worker.py(tts_env_asr)。
  fun_nano(副辨識器):Fun-ASR-Nano,CPU,子行程 asr_worker.py(tts_env_asr_fun)。
  whisper:<size>(或舊參數 medium/small/large-v3):faster-whisper 本行程,只給舊片重渲染。
- 字詞時間戳(channel/_archive/plans/PLAN_配音對齊_2026-10-29.md):qwen06 子行程另載 Qwen3-ForcedAligner-0.6B(`--aligner`),transcribe(x, text)
  給了對齊文字(簡體、無標點)就回它的逐字時間(`FA_DEVICE` = 環境變數 TTS_FA_DEVICE,預設 cpu;本機顯存放不下,Colab/Kaggle 設 cuda)。
  沒給 text、對齊失敗(words = null)或 TTS_TS=whisper(A/B、舊片重渲染)時退回本行程的 faster-whisper small
  (`TS_MODEL`,`TS_DEVICE` 預設 CPU int8;與子行程的辨識平行跑;TTS_TS=none 不載)。文字一律用主辨識器的,words 只拿來取時間
  (align_info 把 words 依拼音對回已知文本、容許辨識錯字)。最後一次用的時間戳來源記在 `last_ts`("qwen3-fa" | "whisper-small")。
- `Second` / `dual_phase` / `final_check`:副辨識器的雙辨識回查(背景執行緒,只跑通過主品管的那一次音檔)與重錄判定
  (純邏輯,可用假辨識器測)。
- `pron_pos_bad`:多音字位置讀音回查的純函式(tts_chattts.pron_rule_bad 用)。
- `common_inserts`:句中多唸字判定的純函式(兩套辨識在同一位置都比文案多出字 = 多唸;tts_cosy3 的 Second.post 與 --requal 用)。"""
import difflib
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

import paths as P

PRIMARY, SECONDARY = "qwen06", "fun_nano"
TS_MODEL = "small"
TS_DEVICE = os.environ.get("TTS_TS_DEVICE", "cpu")   # 2026-10-21 實測:cosy3 3.5 GB + Qwen 2.0 GB + 主程式 1.3 GB(含 whisper small fp16)= 6.75 GB,超過 6.5 GB 上限,時間戳模型改 CPU int8(可用環境變數改回 cuda)
FA_DEVICE = os.environ.get("TTS_FA_DEVICE", "cpu")   # 對齊器裝置 cuda | cpu | none;本機 6.8 GB 再加 1.77 GB 放不下,預設 cpu(每句約 0.45 s)
TS_MODE = os.environ.get("TTS_TS", "")               # whisper = 強制舊路徑(不用對齊器);none = 不載 whisper 退路
ENVS = {"qwen06": P.ROOT / "tts_env_asr", "fun_nano": P.ROOT / "tts_env_asr_fun"}
WORK = P.TMP / "asr_work"
CACHE = P.TMP / "asr_cache"
WHISPER_SIZES = ("tiny", "base", "small", "medium", "large-v2", "large-v3")


def parse_spec(spec):
    """'qwen06' / 'fun_nano' -> (後端, None);'whisper:medium' 或舊參數 'medium' -> ('whisper', 'medium')。"""
    s = (spec or PRIMARY).strip()
    if s in ENVS:
        return s, None
    if s.startswith("whisper"):
        return "whisper", s.split(":", 1)[1] if ":" in s else "medium"
    if s in WHISPER_SIZES:
        return "whisper", s
    raise ValueError(f"不認得的辨識器 {spec}(qwen06 | fun_nano | whisper:<size>)")


# ------------------------------------------------------------ 後端
class Worker:
    """asr_worker.py 常駐子行程(協定見該檔)。submit 回 Future;同一個子行程的請求由單一執行緒依序送,可在背景跑。
    啟動不等載入完成:第一個請求才等 @@READY(模型載入與主程式其他載入平行)。"""

    def __init__(self, backend, device, aligner="none"):
        env = os.environ.copy()
        home = P.TMP / "asr_home"  # transformers / modelscope 會在家目錄建快取:導到 tmp,不寫 C 槽
        for d in (home, WORK, CACHE / "hf" / "hub", CACHE / "ms", CACHE / "torch", CACHE / "tmp"):
            d.mkdir(parents=True, exist_ok=True)
        env.update(USERPROFILE=str(home), HOME=str(home), HF_HOME=str(CACHE / "hf"), HF_HUB_CACHE=str(CACHE / "hf" / "hub"),
                   MODELSCOPE_CACHE=str(CACHE / "ms"), TORCH_HOME=str(CACHE / "torch"), TMP=str(CACHE / "tmp"),
                   TEMP=str(CACHE / "tmp"), TMPDIR=str(CACHE / "tmp"), PYTHONUTF8="1", HF_HUB_OFFLINE="1")
        self.backend, self.device = backend, device
        self.log_path = WORK / f"_{backend}_worker.log"
        self.log = open(self.log_path, "w", encoding="utf-8")
        self.p = subprocess.Popen([str(P.venv_python(ENVS[backend])), "-X", "utf8",
                                   str(Path(__file__).with_name("asr_worker.py")), "--backend", backend,
                                   "--models", str(P.TTS_MODELS / "asr"), "--device", device, "--aligner", aligner],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                                  text=True, encoding="utf-8", env=env)
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.ready = None

    def _read(self, tag):
        for line in self.p.stdout:
            if line.startswith(tag + " "):
                return json.loads(line[len(tag) + 1:])
        raise RuntimeError(f"[tts_asr] {self.backend} 子行程中止,見 {self.log_path}")

    def _req(self, x, text=None):
        """送一筆請求,回 @@RES 的 dict(text 給了才帶進請求,子行程有對齊器時回覆多 words)。"""
        if self.ready is None:
            self.ready = self._read("@@READY")
        f = WORK / f"{uuid.uuid4().hex}.npy"
        np.save(f, np.ascontiguousarray(x, dtype=np.float32))
        job = dict(npy=str(f))
        if text:
            job["text"] = text
        try:
            self.p.stdin.write(json.dumps(job, ensure_ascii=False) + "\n")
            self.p.stdin.flush()
            r = self._read("@@RES")
        finally:
            f.unlink(missing_ok=True)
        if not r["ok"]:
            raise RuntimeError(f"[tts_asr] {self.backend} 辨識失敗: {r['err']}")
        return r

    def _call(self, x):
        return self._req(x)["text"]

    def _call_align(self, x, text):
        r = self._req(x, text)
        return r["text"], r.get("words")

    def submit(self, x):
        return self.pool.submit(self._call, x)

    def submit_align(self, x, text):
        """辨識 + 對齊:Future -> (文字, [[字, 起, 迄], ...] 或 None = 對齊失敗/子行程沒有對齊器)。"""
        return self.pool.submit(self._call_align, x, text)

    def close(self):
        self.pool.shutdown(wait=True)
        try:
            self.p.stdin.write(json.dumps(dict(cmd="quit")) + "\n")
            self.p.stdin.close()
            self.p.wait(timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            self.p.kill()
        self.log.close()


class Whisper:
    """faster-whisper(本行程):主辨識器的字詞時間戳(small),或舊片重渲染的主辨識器(medium)。"""

    def __init__(self, size, device="cuda"):
        import torch
        if hasattr(os, "add_dll_directory"):   # 只有 Windows 有;Linux(Colab)靠 torch 先載入的 CUDA 函式庫
            os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
        from faster_whisper import WhisperModel
        self.m = WhisperModel(size, device=device, compute_type="float16" if device == "cuda" else "int8",
                              download_root=str(P.TTS_MODELS))
        self.lock = threading.Lock()

    def transcribe(self, x):
        with self.lock:
            segs, _ = self.m.transcribe(x, language="zh", word_timestamps=True, beam_size=5,
                                        condition_on_previous_text=False)
            words = [(wd.word, wd.start, wd.end) for s in segs for wd in (s.words or [])]
        return "".join(w[0] for w in words), words


class ASR:
    """統一介面:transcribe(16 kHz float32) -> (文字, words)。ts=None 時不取時間戳(words 為空;副辨識器用)。"""

    def __init__(self, spec=PRIMARY, device="cuda", ts=TS_MODEL):
        self.kind, size = parse_spec(spec)
        self.worker = self.ts = self.wh = None
        self.fa, self.last_ts = False, None
        if self.kind == "whisper":
            self.wh = Whisper(size, device)
            self.name = f"whisper-{size}"
            return
        # 對齊器只給主辨識器(要取時間戳的);TTS_TS=whisper 或 TTS_FA_DEVICE=none 走舊路徑
        self.fa = bool(ts) and self.kind == "qwen06" and TS_MODE != "whisper" and FA_DEVICE != "none"
        # fun_nano(副辨識)預設 CPU;TTS_ASR2_DEVICE=cuda 改上顯示卡(Colab 系統 RAM 放不下 CPU 版)
        self.worker = Worker(self.kind, device if self.kind == "qwen06" else os.environ.get("TTS_ASR2_DEVICE", "cpu"),
                             **(dict(aligner=FA_DEVICE) if self.fa else {}))
        self.ts_size = ts
        self.ts = Whisper(ts, TS_DEVICE) if ts and not (self.fa and TS_MODE == "none") else None
        self.name = self.kind + ("+fa:qwen3" if self.fa else "") + (f"+ts:whisper-{ts}" if self.ts else "")

    def transcribe(self, x, text=None):
        """text = 對齊用文字(簡體、無標點);有對齊器且給了 text 就用對齊器的逐字時間,否則(或對齊失敗)用 whisper。"""
        x = np.ascontiguousarray(x, dtype=np.float32)
        if self.wh:
            self.last_ts = self.name
            return self.wh.transcribe(x)
        if text and getattr(self, "fa", False):
            hyp, words = self.worker.submit_align(x, text).result()
            if words is not None:
                self.last_ts = "qwen3-fa"
                return hyp, [(u, s, e) for u, s, e in words]
            print("[tts_asr] 對齊失敗,改用 whisper 時間戳", file=sys.stderr, flush=True)
            words = self.ts.transcribe(x)[1] if self.ts else []
            self.last_ts = self._ts_name()
            return hyp, words
        fut = self.worker.submit(x)  # 子行程辨識與本行程的時間戳辨識平行
        words = self.ts.transcribe(x)[1] if self.ts else []
        self.last_ts = self._ts_name()
        return fut.result(), words

    def _ts_name(self):
        return f"whisper-{getattr(self, 'ts_size', TS_MODEL)}" if self.ts else None

    def submit(self, x):
        """只要文字、在背景跑(副辨識器):回 Future。"""
        x = np.ascontiguousarray(x, dtype=np.float32)
        if self.wh:
            return ThreadPoolExecutor(max_workers=1).submit(lambda: self.wh.transcribe(x)[0])
        return self.worker.submit(x)

    def close(self):
        if self.worker:
            self.worker.close()


# ------------------------------------------------------------ 雙辨識回查
def is_bad2(sim, pron_bad, sim_min):
    """副辨識結果與文案不符:相似度低於主品管門檻,或多音字/換字位置聽成另一個讀音。"""
    return sim < sim_min or pron_bad > 0


def fields(m):
    """qc 紀錄的副辨識欄位(沒跑副辨識 = 關掉 --asr2 或該句最終音檔沒有 wav:asr2 為 None)。"""
    return dict(asr2=m.get("asr2"), asr2_sim=m.get("asr2_sim"), asr2_bad=bool(m.get("asr2_bad")))


class Second:
    """副辨識器回查。judge(text, hyp2) -> (sim, pron_bad);結果寫回量測 dict m 的 asr2 / asr2_sim / asr2_bad。
    submit 立即回(背景執行緒排隊辨識),collect 等全部結果。asr 可換成假辨識器(有 submit(x) -> Future 即可)。"""

    def __init__(self, judge, sim_min, asr=None, spec=SECONDARY, post=None):
        self.asr = asr or ASR(spec, device="cpu", ts=None)
        self.name = getattr(self.asr, "name", spec)
        self.judge, self.sim_min, self.post = judge, sim_min, post   # post(m, text, hyp2) -> 真值 = 另有不一致(asr2_bad),可寫 m 的額外欄位
        self.pending = {}

    def submit(self, m, text, x16):
        if "asr2" in m or id(m) in self.pending:
            return
        self.pending[id(m)] = (m, text, self.asr.submit(x16))

    def collect(self):
        for m, text, fut in self.pending.values():
            hyp = fut.result()
            sim, pron = self.judge(text, hyp)
            bad = is_bad2(sim, pron, self.sim_min)
            if self.post and self.post(m, text, hyp):
                bad = True
            m.update(asr2=hyp, asr2_sim=round(sim, 3), asr2_bad=bad)
        self.pending.clear()

    def close(self):
        if hasattr(self.asr, "close"):
            self.asr.close()


def dual_phase(res, sec, retry, max_retry, text_of, wav16, par=None):
    """雙辨識重錄(主品管重試之後呼叫):res 每筆 {w, m, ok, tries};通過主品管、副辨識不一致 -> 重錄(重錄次數與主品管
    合計不超過 max_retry);新的那次也要先過主品管才跑副辨識,一致就換上;都不一致 -> 留副辨識相似度最高的那次
    (asr2_bad=True,列優先聽,不擋交付)。retry(r) -> (w, m, ok) 合成並量測一次新嘗試。
    par(rows, body):多 GPU 分片時各句重錄分給各片並行(副辨識 submit+collect 成對上鎖,只有一份副辨識);None = 依序。
    回傳 (因副辨識重錄的次數, 最後仍不一致的筆數)。"""
    for r in res:
        if r["ok"]:
            sec.submit(r["m"], text_of(r), wav16(r["w"]))
    sec.collect()
    n_re = [0]
    lock = threading.Lock()

    def one(r):
        best_w, best = r["w"], r["m"]
        while len(r["tries"]) - 1 < max_retry:
            w, m, ok = retry(r)
            r["tries"].append(m)
            with lock:
                n_re[0] += 1
            if not ok:
                continue
            with lock:
                sec.submit(m, text_of(r), wav16(w))
                sec.collect()
            if not m["asr2_bad"] or m["asr2_sim"] > best["asr2_sim"]:
                best_w, best = w, m
            if not m["asr2_bad"]:
                break
        r["w"], r["m"] = best_w, best

    rows = [r for r in res if r["ok"] and r["m"].get("asr2_bad")]
    if par:
        par(rows, one)
    else:
        for r in rows:
            one(r)
    return n_re[0], sum(1 for r in res if r["ok"] and r["m"].get("asr2_bad"))


def final_check(res, sec, text_of, wav16):
    """最終音檔還沒跑過副辨識的(語速重錄換了一次嘗試)補跑一次;不一致只記 asr2_bad,不再重錄。
    不論主品管 ok:品管未過但仍會進影片的句子也要有副辨識紀錄(只讀不重錄,不改 ok / fails;2026-10-22)。
    後處理(插靜音、剪停頓)沿用原嘗試的副辨識結果(量測 dict 以 dict(舊, **新) 合併,asr2 欄位帶過去)。"""
    for r in res:
        sec.submit(r["m"], text_of(r), wav16(r["w"]))
    sec.collect()


# ------------------------------------------------------------ 多音字位置讀音回查
def _one(c):
    from pypinyin import Style, lazy_pinyin
    return lazy_pinyin(c, style=Style.TONE3, neutral_tone_with_five=True)[0]


def _key(c, py=None):
    """對齊用的鍵:英數小寫;中文 = 不帶調拼音並模糊 zh/z、ch/c、sh/s、ng/n。py 給定時用它(多音字位置用應讀的音)。"""
    if not py and c.isascii():
        return c.lower()
    s = re.sub(r"\d", "", py or _one(c))
    return re.sub(r"^([zcs])h", r"\1", s).replace("ng", "n")


def token_reading(py):
    """標注 -> 帶調拼音 tone3:CosyVoice 拼音 token「[zh][ǎng]」-> zhang3;單一個字(換字、簡體「着」)-> 該字預設讀音。"""
    toks = re.findall(r"\[([^\[\]\s]+)\]", py or "")
    if not toks:
        return _one(py)
    from pypinyin.contrib.tone_convert import to_tone3
    return to_tone3("".join(toks), neutral_tone_with_five=True)


def _keys(c):
    """字 c 所有讀音的對齊鍵(去調、模糊聲母韻尾;多音字取全部)。"""
    from pypinyin import Style, pinyin
    return {_key(c, p) for p in pinyin(c, style=Style.TONE3, heteronym=True, neutral_tone_with_five=True)[0]}


def pron_pos_bad(ref, hyp, targets):
    """ref / hyp:已正規化(去標點、同一字形體系)的文案與辨識文字;targets {ref 位置: (原字, 應讀 tone3[, strict])}。
    回傳讀錯的 ref 位置 list:辨識結果對齊到該位置的字不是原字、且它的預設讀音是原字「另一個讀音」(長 -> 腸 chang2)。
    辨識成原字(或應讀的同音字)時文字層看不出聲調,不算;辨識成不相干的音由內容相似度把關。
    strict=True(always 字:著、得、曝…,模型常唸成不相干的音,單字替換相似度照樣過)再加一條:辨識字不是原字(著/着視為同字),
    且它的任何讀音(不計聲調)都不等於應讀音 -> 也算(得 的位置辨識成 不/猛/某/么 -> bad;的/德 不算;非 ASCII 才比)。"""
    from pypinyin import Style, pinyin
    rk = [_key(c, targets[i][1] if i in targets else None) for i, c in enumerate(ref)]
    sm = difflib.SequenceMatcher(None, rk, [_key(c) for c in hyp], autojunk=False)
    bad = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if not (tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1)):
            continue
        for d in range(i2 - i1):
            i = i1 + d
            if i not in targets:
                continue
            (oc, want, *rest), h = targets[i], hyp[j1 + d]
            strict = bool(rest and rest[0])
            same = h == oc or {h, oc} <= {"著", "着"}   # 辨識寫回原字(著/着只是簡繁寫法):讀音無從分辨,不算錯
            if strict and want.endswith("5") and not same and _key(h) == _key(oc, want):
                continue   # 輕聲應讀(得 -> 的):同音不同調的字(德 de2)聽不出聲調,不算
            wrong = set(pinyin(oc, style=Style.TONE3, heteronym=True, neutral_tone_with_five=True)[0]) - {want}
            if not same and _one(h) in wrong:
                bad.append(i)
            elif (strict and not same and not h.isascii()
                  and _key(oc, want) not in _keys(h)):
                bad.append(i)
    return bad


# ------------------------------------------------------------ 句中多唸字(兩套辨識同位置都多出字)
INSERT_MIN = 1       # 一套辨識比文案多出的音節數(權重)達此值才算插入事件
INSERT_POS_TOL = 1   # 兩套辨識的插入位置(文案詞元索引)相差不超過此值才算同一處

_INIT = r"zh|ch|sh|[bpmfdtnlgkhjqxrzcswy]"
_SYL = re.compile(rf"\[({_INIT})\]\[([^\[\]]+)\]|\[([^\[\]]+)\]|([A-Za-z]+)|([一-鿿])")
_DETONE = str.maketrans("āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜńňǹḿ", "aaaaeeeeiiiioooouuuuvvvvnnnm")


def _fuzzy(s):
    return re.sub(r"^([zcs])h", r"\1", s).replace("ng", "n")


def _syllables(s):
    """文字 -> [(對齊鍵, 權重, 原文, 是否英文詞)]。拼音 token 組([zh][ǎng])與中文字 = 1 音節;單一英文字母 = 1;
    相鄰的單一字母(A I)合成一個詞、與多字母英文單字一樣權重 0(英文名斷詞差異不算插入);標點、空白、殘留數字略過。"""
    out, run = [], False   # run:最後一個詞元是由單一字母組成(可再併下一個單一字母)
    for m in _SYL.finditer(s):
        ini, fin, solo, en, zh = m.groups()
        if en and len(en) == 1:
            if run:
                out[-1][0] += en.lower()
                out[-1][2] += en
                out[-1][1] = 0
            else:
                out.append(["en:" + en.lower(), 1, en, True])
            run = True
            continue
        run = False
        if fin:
            out.append([_fuzzy((ini + fin).translate(_DETONE)), 1, m.group(0), False])
        elif solo:
            out.append([_fuzzy(solo.translate(_DETONE)), 1, m.group(0), False])
        elif en:
            out.append(["en:" + en.lower(), 0, en, True])
        else:
            out.append([_key(zh), 1, zh, False])
    return out


def _inserts(ref, hyp):
    """hyp 相對 ref 的插入事件 [(ref 詞元索引起, 迄, 多出的文字, 多出詞元的鍵集合)]:對齊後 hyp 區段權重 - ref 區段權重 >= INSERT_MIN。
    replace 區段若 ref 側有英文詞、hyp 側卻沒有英文詞(辨識把英文名寫成中文音譯)略過。"""
    r, h = _syllables(ref), _syllables(hyp)
    sm = difflib.SequenceMatcher(None, [t[0] for t in r], [t[0] for t in h], autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag not in ("insert", "replace"):
            continue
        if tag == "replace" and any(t[3] for t in r[i1:i2]) and not any(t[3] for t in h[j1:j2]):
            continue
        # 英文詞被聽成單一字母(App -> F)不算多出:ref 側沒對到 hyp 英文詞的英文詞,可抵掉 hyp 側的單一字母
        spare_en = sum(1 for t in r[i1:i2] if t[3]) - sum(1 for t in h[j1:j2] if t[3] and t[1] == 0)
        letters = sum(1 for t in h[j1:j2] if t[3] and t[1] == 1)
        extra = sum(t[1] for t in h[j1:j2]) - sum(t[1] for t in r[i1:i2]) - min(max(spare_en, 0), letters)
        if extra >= INSERT_MIN:
            out.append((i1, max(i1, i2), "".join(t[2] for t in h[j1:j2]), {t[0] for t in h[j1:j2] if t[1]}))
    return out


def common_inserts(ref, hyp1, hyp2):
    """句中多唸字:ref = 實際送進引擎的文字(engine_text,含拼音 token);hyp1 / hyp2 = 兩套辨識(已過簡體與數字/標點正規化)。
    兩套辨識在同一位置(詞元索引差 <= INSERT_POS_TOL)都比 ref 多出 >= INSERT_MIN 音節、且多出的字至少有一個音(不計聲調)相同
    (兩套各聽成不同的字多半是辨識幻覺,不算) -> 回傳 [dict(at, ref_ctx, asr, asr2)],沒有回 []。"""
    a, b = _inserts(ref, hyp1), _inserts(ref, hyp2)
    if not a or not b:
        return []
    r = _syllables(ref)
    out = []
    for s1, e1, t1, k1 in a:
        for s2, e2, t2, k2 in b:
            if s1 - INSERT_POS_TOL <= e2 and s2 - INSERT_POS_TOL <= e1 and k1 & k2:
                ctx = "".join(t[2] for t in r[max(0, s1 - 3):s1]) + "|" + "".join(t[2] for t in r[s1:s1 + 3])
                out.append(dict(at=s1, ref_ctx=ctx, asr=t1, asr2=t2))
                break
    return out


if __name__ == "__main__":  # 單檔辨識:python tts_asr.py <wav> [spec]
    import soundfile as sf
    x, sr = sf.read(sys.argv[1], dtype="float32")
    x = x.mean(axis=1) if x.ndim > 1 else x
    if sr != 16000:
        import torch
        import torchaudio
        x = torchaudio.functional.resample(torch.from_numpy(x), sr, 16000).numpy()
    a = ASR(sys.argv[2] if len(sys.argv) > 2 else PRIMARY)
    print(a.name, a.transcribe(x))
    a.close()
