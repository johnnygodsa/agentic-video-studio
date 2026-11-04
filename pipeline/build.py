#!/usr/bin/env python3
"""文案 JSON -> 配音 + 燒錄字幕 + 依句切換畫面的 1920x1080 mp4。

python pipeline/run.py build --script <json> --voice <edge 語音> --rate +10% --tag <名稱> --out <mp4>
       [--lines A-B] [--clips auto] [--bed 0.06] [--max-per-src 90]

路徑一律由 paths.py 決定,與目前工作目錄無關:--script 相對於 repo 根;--clips / --bgm / --timeline 的相對路徑
以素材根 ROOT 為基準;快取在 ROOT/build/<tag>/;--out 只給檔名 -> ROOT/output/<tag>/<檔名>(其他相對路徑以 ROOT 為基準)。

注意:本機 ffmpeg drawtext 會 segfault,所有文字都用 Pillow 畫 PNG(卡片)或 libass(字幕)。
"""
import argparse
import asyncio
import hashlib
import json
import math
import random
import re
import shlex
import shutil
import subprocess
import sys
import unicodedata
import wave
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import anim_lib as AL
import anim_web as AW
from audio_consts import (BGM_BELOW_VOICE_DB, BGM_DYN_MAX_P50_DB, BGM_DYN_P90_P10_DB, BGM_NORM_MAX, BGM_NORM_MIN,  # noqa: F401
                          BGM_PEAK_BELOW_VOICE_DB, BGM_REF_DB, bgm_gain_auto, bgm_norm, bgm_sidecar, bgm_sidecar_db)
import freeze as FZ
import kit as KIT
import paths as P
import seg as SEG
import tts_cosy_text as CT
import tts_key as TK
import tts_pause as TPA
import tts_split as TS
from tts_tail import QC_VER, TRIM_VER, fade_out, trim_bounds

W, H, FPS = 1920, 1080, 30
SR = 48000
SPF = SR // FPS  # 每影格音訊取樣數 (1600)
FONT = str(P.FONT_BOLD)   # 卡片/引言/對比/劇透牌等 Pillow 文字(2026-10-22 起 Noto Sans TC 粗體,原微軟正黑體)
TAIL = 1.0  # 片尾保留秒數;句間/段間停頓由 --gap / --section-gap 控制
SUB_MAX_W = 18  # 每段字幕上限(全形字數;ASCII 以 0.5 計)
# 字幕外觀(2026-10-09 使用者定案):Noto Sans TC 粗體、白字、黑描邊、右下陰影、無底框
# 字型檔是由可變字型固定在 wght=700 產生的靜態檔(libass 讀可變字型只會拿到預設的細體);家族名獨立,樣式 Bold 設 0 以免再疊假粗體
SUB_FONT = str(P.REPO / "fonts" / "NotoSansTC-SubBold.ttf")
SUB_FONT_NAME = "Noto Sans TC SubBold"
SUB_FS = 85                           # libass 的 Fontsize 是「行高」;此字型行高 = 1.448 em
SUB_EM = SUB_FS / 1.448               # 一個全形字的寬(約 58.7px,與先前微軟正黑體字級 78 等大);Pillow 用這個字級量測才會和 libass 一致
SUB_PAD_X = 0.45 * SUB_EM             # 檢查寬度時左右各留的邊
SUB_CY = 924                          # 全形字墨跡的垂直中心(1080 高畫面)
SUB_INK_DY = -2.5                     # \an5 時 \pos 的 y 要比墨跡中心高多少(libass 實測;樣式 MarginV 須為 0,否則會再偏移)
SUB_OUTLINE = 2                       # 黑描邊粗(px)
SUB_SHADOW = 4                        # 陰影偏移(px,右下)
SUB_SHADOW_ALPHA = "60"               # 陰影透明度(00=不透明,FF=全透明);約 62% 不透明黑
SUB_MAX_FRAC = 0.88                   # 單行底框寬上限(占畫面寬)
SUB_PLAY = (W, H)                     # ASS 的 PlayResX / PlayResY
SUB_CX = W // 2                       # 字幕水平中心(\pos 的 x)
SUB_MAX_PX = SUB_MAX_FRAC * W         # 字幕段寬(含左右 pad)上限
# 字幕橫/直兩組(F2-3 Shorts,projects/framework/shorts_spec.md §4);橫式 = 上面的常數,一個都不可改。
# set_sub_profile 改寫模組全域,斷句(split_phrases/_split_long)、write_ass、寬度檢查都在呼叫時讀全域
SUB_PROFILES = {
    "landscape": dict(SUB_MAX_W=SUB_MAX_W, SUB_FS=SUB_FS, SUB_CX=SUB_CX, SUB_CY=SUB_CY, SUB_INK_DY=SUB_INK_DY,
                      SUB_OUTLINE=SUB_OUTLINE, SUB_SHADOW=SUB_SHADOW, SUB_SHADOW_ALPHA=SUB_SHADOW_ALPHA,
                      SUB_PLAY=SUB_PLAY, SUB_MAX_PX=SUB_MAX_PX),
    "portrait": dict(SUB_MAX_W=10, SUB_FS=112, SUB_CX=510, SUB_CY=1420, SUB_INK_DY=SUB_INK_DY * 112 / 85,
                     SUB_OUTLINE=3, SUB_SHADOW=5, SUB_SHADOW_ALPHA="60", SUB_PLAY=(1080, 1920), SUB_MAX_PX=860),
}
SUB_PROFILE = "landscape"
SHOT_WORKERS = 4

def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- 基礎工具
def run(cmd, cwd=None):
    p = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True)
    if p.returncode != 0:
        err = p.stderr.decode("utf-8", "replace")[-1500:]
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(str(c) for c in cmd[:8])}\n{err}")
    return p.stdout


def probe_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(out.decode().strip())


def probe_has_audio(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
               "-of", "csv=p=0", path])
    return bool(out.strip())


def sha1(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def file_sig(path):
    """快取簽章用的檔案指紋:相對於素材根的路徑 + 大小 + 修改時間(不含絕對路徑,素材根搬家後仍相同)。"""
    st = Path(path).stat()
    return f"{P.rel(path)}:{st.st_size}:{int(st.st_mtime)}"


# ---------------------------------------------------------------- 文案
def load_lines(script_path):
    data = json.loads(Path(script_path).read_text(encoding="utf-8"))
    lines, idx = [], 0
    for si, sec in enumerate(data["sections"]):
        for ln in sec["lines"]:
            idx += 1
            lines.append(dict(ln, idx=idx, sec=si))
    return lines


def load_meta(script_path):
    """script 頂層資料:sections 的 title/trans/name,以及 timeline(動畫用的時間軸節點)。"""
    data = json.loads(Path(script_path).read_text(encoding="utf-8"))
    secs = [{k: v for k, v in sec.items() if k != "lines"} for sec in data["sections"]]
    return secs, data.get("timeline")


def load_fallback(script_path):
    """script 頂層 fallback:{標籤: [備援標籤, …]}。挑片段時該標籤的未用片段不夠,就依序改用備援標籤的(pick_videos)。"""
    fb = json.loads(Path(script_path).read_text(encoding="utf-8")).get("fallback") or {}
    if not isinstance(fb, dict) or not all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in fb.values()):
        sys.exit('script 的 fallback 格式應為 {"標籤": ["備援標籤", …]}')
    return fb


def parse_range(spec, n):
    if not spec:
        return 1, n
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", spec.strip())
    if not m:
        sys.exit(f"--lines 格式錯誤: {spec}")
    a = int(m.group(1))
    b = int(m.group(2) or a)
    return max(1, a), min(n, b)


# ---------------------------------------------------------------- TTS
# 裁靜音一律用 tts_tail 的溫和裁切(門檻相對該句峰值、尾端多留並淡出)。
# 外部引擎若自帶品管並在 .qc.json 標示 final(tts_chattts.py),音檔已是品管過的最終版,這裡只轉格式不再裁。
# 快取鍵不含任何路徑(見 tts_key.py):.key = "<音檔鍵>|<品管版本>";音檔鍵相同的舊音檔可拿去重新檢驗,不必重錄。


def file_sha1(path):
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


def _synth_edge(todo, voice, rate):
    import edge_tts

    async def one(sem, say, raw, keyf, key, idx):
        async with sem:
            last = None
            for attempt in range(1, 4):
                try:
                    tmp = raw.with_suffix(".part")
                    await edge_tts.Communicate(say, voice, rate=rate).save(str(tmp))
                    if tmp.stat().st_size == 0:
                        raise RuntimeError("empty audio")
                    tmp.replace(raw)
                    keyf.write_text(key)
                    return
                except Exception as e:  # noqa: BLE001
                    last = e
                    await asyncio.sleep(2 * attempt)
            raise RuntimeError(f"TTS 第 {idx} 句失敗 3 次: {last}")

    async def main():
        sem = asyncio.Semaphore(4)
        await asyncio.gather(*(one(sem, *t) for t in todo))

    asyncio.run(main())


def _run_engine(cmd):
    """跑外部 TTS 引擎,把它 stderr 裡的摘要/進度行(以 [ 或兩個空白開頭;進度條不算)即時轉到 log,品管結果才會留在執行紀錄。"""
    p = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    tail = []
    for raw in p.stderr:
        line = raw.decode("utf-8", "replace").rstrip("\r\n").split("\r")[-1]
        tail = (tail + [line])[-25:]
        if line.startswith(("[", "  ")) and "it/s" not in line:
            log("  " + line.strip())
    if p.wait() != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(str(c) for c in cmd[:8])}\n" + "\n".join(tail))


def _synth_external(todo, tts_cmd, voice, rate, tts_dir):
    """子行程批次合成:cmd <jobs.json> --voice V --rate R;jobs = [{"idx","text","out","verify"}]。
    verify=True:out 是同一段文字的舊音檔,請引擎先重新檢驗、不過再重錄(不支援的引擎會直接重錄)。
    引擎若寫了 <out 去副檔名>.qc.json 就補上快取鍵;沒寫(引擎沒有品管)則代寫一份 qc="none" 的紀錄。"""
    jobs = [{"idx": idx, "text": say, "out": str(raw), "verify": verify} for say, raw, _, _, idx, verify in todo]
    for _, raw, keyf, _, _, verify in todo:
        if not verify:
            keyf.unlink(missing_ok=True)
    jf = tts_dir / "_jobs.json"
    jf.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    _run_engine(list(tts_cmd) + [jf, "--voice", voice, "--rate", rate])
    for say, raw, keyf, key, idx, _ in todo:
        if not raw.exists() or raw.stat().st_size == 0:
            raise RuntimeError(f"外部 TTS 第 {idx} 句沒有輸出: {raw}")
        keyf.write_text(key)
        qf, sha = raw.with_suffix(".qc.json"), file_sha1(raw)
        rec = json.loads(qf.read_text(encoding="utf-8")) if qf.exists() else None
        if not rec or rec.get("wav_sha1") != sha:
            rec = dict(qc_ver=QC_VER, qc="none", text=say, passed=None, wav_sha1=sha)
        rec["key"] = key
        qf.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")


def _qc_json(raw):
    """音檔旁的 .qc.json 原始內容(不檢查版本);沒有或壞掉回傳 None。"""
    qf = raw.with_suffix(".qc.json")
    if not qf.exists():
        return None
    try:
        return json.loads(qf.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _qc_record(raw, key):
    """音檔旁的品管紀錄;必須是目前的 QC 版本、同一把快取鍵、且音檔內容沒被換過才算數,否則回傳 None(要重新檢驗)。"""
    rec = _qc_json(raw)
    if rec is None:
        return None
    ok = rec.get("qc_ver") == QC_VER and rec.get("key") == key and rec.get("wav_sha1") == file_sha1(raw)
    return rec if ok else None


def _pron_changed(engine, u, rec):
    """cosy3:音檔錄音時的讀音標注(cosy_pron.json / pron_rules.json)或英文寫法(cosy_terms.json)與目前不同 -> 要重錄
    (音檔鍵用原文計,表改了鍵不會變)。rec = 已採用的品管紀錄,沒有就讀音檔旁的原始紀錄;紀錄沒有相關欄位(舊紀錄)視為一致。其他引擎恆為 False。"""
    if engine != "cosy3":
        return False
    rec = rec or _qc_json(u["raw"])
    return CT.pron_changed(rec, u["say"]) or CT.terms_changed(rec, u["say"])


def _trim_one(u):
    """u = 配音單位(一個子句或一整行):u["raw"] 原始音檔,u["qc"] 品管紀錄;產生 <raw>.trim.wav 並設 u["wav"]。"""
    raw = u["raw"]
    wav = raw.with_suffix(".trim.wav")
    tkey = raw.with_suffix(".trim.key")
    final = bool((u.get("qc") or {}).get("final"))
    key = TK.trim_key(raw.with_suffix(".key").read_text(), file_sha1(raw), TRIM_VER, final, u.get("comma_profile", "std"))
    u["wav"] = wav
    if wav.exists() and tkey.exists() and tkey.read_text() == key:
        return
    pcm = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", raw, "-f", "s16le", "-ar", str(SR), "-ac", "2", "-"])
    if final:  # 進影片的就是通過品管的那一份:長度對不上代表轉檔出了問題
        if abs(len(pcm) / 4 / SR - u["qc"]["dur"]) > 0.005:
            raise RuntimeError(f"單位 {u['label']} 轉檔後長度 {len(pcm) / 4 / SR:.3f}s 與品管紀錄 {u['qc']['dur']}s 不符")
    else:
        x = np.frombuffer(pcm, dtype="<i2").reshape(-1, 2).astype(np.float32) / 32768.0
        a, b = trim_bounds(x.mean(axis=1), SR)
        pcm = (np.clip(fade_out(x[a:b], SR), -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    write_wav(wav, [pcm])
    tkey.write_text(key)


def write_qc_report(units, redone, path):
    """合併每個配音單位的品管紀錄成一份涵蓋全部單位的報告;回傳未通過的 (單位標籤, 原因)。標籤:單句行 = 句編號,多句行 = "句.子句序"。"""
    recs = [dict(u["qc"], idx=u["label"]) for u in units if u.get("qc")]
    checked = [r for r in recs if r.get("passed") is not None]
    failed = [dict(idx=r["idx"], fails=r.get("fails"), text=r.get("text"), asr=r.get("asr")) for r in checked
              if not r["passed"]]
    rep = dict(qc_ver=QC_VER, units=len(units), checked=len(checked), passed=len(checked) - len(failed), failed=failed,
               no_qc=[u["label"] for u in units if not (u.get("qc") and u["qc"].get("passed") is not None)],
               # 音檔來源(不隨重跑改變):cache = 舊音檔重新檢驗通過後沿用;synth/plain = 在目前 QC 版本下重錄
               by_source={s: sum(1 for r in checked if r.get("source") == s) for s in ("cache", "synth", "plain")},
               this_run=dict(reused_record=len(units) - len(redone),
                             kept_after_recheck=[r["idx"] for r in recs if r["idx"] in redone and r.get("source") == "cache"],
                             rerecorded=[r["idx"] for r in recs if r["idx"] in redone and r.get("source") != "cache"]),
               records=recs)
    path.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return [(f["idx"], f["fails"]) for f in failed]


def tts_silent(lines, tts_dir):
    """測試用靜音引擎(--tts-engine silent):每句一段靜音,長度取 script 的 silent_dur,沒有則依字數估(約 0.22 秒/字)。"""
    for ln in lines:
        dur = float(ln.get("silent_dur") or max(1.5, 0.22 * len(ln.get("say") or ln["text"])))
        ln["wav"] = tts_dir / f"{ln['idx']:03d}.silent.wav"
        write_wav(ln["wav"], [b"\0" * (round(dur * SR) * 4)])


CACHE_SUFFIXES = (".key", ".qc.json", ".trim.wav", ".trim.key")


def relocate_tts_cache(want, tts_dir, ext):
    """快取以「文字」為鍵:文案插句/刪句後句編號會位移,先依 .key 內容把既有音檔搬到新的句編號。
    want = {句編號: 音檔鍵}(不含品管版本)。先全部複製到暫存名再一次換上,來源與目的互相重疊也不會蓋掉。回傳搬動的句數。"""
    have = {}
    for kf in tts_dir.glob("[0-9][0-9][0-9].key"):
        if (tts_dir / f"{kf.stem}.{ext}").exists():
            have.setdefault(TK.audio_part(kf.read_text()), int(kf.stem))
    moves = {i: have[k] for i, k in want.items() if have.get(k) not in (None, i)}
    moves = {i: o for i, o in moves.items()
             if not ((tts_dir / f"{i:03d}.key").exists()
                     and TK.audio_part((tts_dir / f"{i:03d}.key").read_text()) == want[i])}
    if not moves:
        return 0
    sufs = (f".{ext}",) + CACHE_SUFFIXES
    staged = []
    for i, o in moves.items():
        for suf in sufs:
            src, tmp = tts_dir / f"{o:03d}{suf}", tts_dir / f"_mv{i:03d}{suf}"
            tmp.unlink(missing_ok=True)
            if src.exists():
                shutil.copy2(src, tmp)
            staged.append((tmp, tts_dir / f"{i:03d}{suf}"))
    for tmp, dst in staged:
        dst.unlink(missing_ok=True)
        if tmp.exists():
            tmp.replace(dst)
    return len(moves)


def _read_pcm(path):
    with wave.open(str(path), "rb") as w:
        return w.readframes(w.getnframes())


def assemble_line(ln, tts_dir):
    """一行的音檔:單一單位直接用其 trim.wav;多個子句 = 各子句 trim.wav + 句後停頓(ln["clauses"] 記錄各子句在行內的起訖秒)。"""
    us = ln["units"]
    if len(us) == 1:
        ln["wav"], ln["clauses"] = us[0]["wav"], None
        return
    chunks, cl, n = [], [], 0
    for u in us:
        pcm = _read_pcm(u["wav"])
        cl.append(dict(text=u["say"], start=n / SR, end=(n + len(pcm) // 4) / SR, gap=u["gap"],
                       say_t=(u.get("qc") or {}).get("say_t")))
        chunks.append(pcm)
        n += len(pcm) // 4
        g = round(u["gap"] * SR)
        chunks.append(b"\0" * (g * 4))
        n += g
    ln["wav"] = tts_dir / f"{ln['idx']:03d}.line.wav"
    write_wav(ln["wav"], chunks)
    ln["clauses"] = cl


def frozen_abort(frozen, reasons):
    """凍結後禁新合成(PLAN_TTS_FLOW R3/T4):reasons = [(單位標籤, 原因)](快取未命中的單位);逐句印出後 exit 2。"""
    print(f"凍結後禁止新合成:{frozen} 已凍結,但有 {len(reasons)} 個配音單位的快取未命中(要重錄/重新檢驗),已中止,沒有動任何音檔")
    for label, why in reasons[:40]:
        print(f"  句{label}:{why}")
    if len(reasons) > 40:
        print(f"  …另 {len(reasons) - 40} 個")
    print("文案、讀音表、英文表在凍結後改動一律不重錄。確需重錄:先取得使用者同意,再 "
          f"`python -X utf8 pipeline\\freeze.py {frozen} --refreeze --reason \"<使用者同意的理由>\"`,並重走 make_version --tts-review(重錄+聽審)。")
    sys.exit(2)


def tts_all(lines, voice, rate, tts_dir, engine="edge", tts_cmd=None, no_synth=False, frozen=None, comma_profile="std"):
    """tts_cmd:外部引擎的合成指令(字串清單)。no_synth:有任何一句需要合成/重新檢驗就中止,不動任何音檔。
    frozen:已凍結的片名(freeze.json 存在才傳);快取未命中(含重新檢驗)即逐句列出原因並 exit 2,不動任何音檔(--no-synth 的中止先於它)。
    配音單位:外部引擎(chattts)一行含多個句子時依 。?! 拆成子句各自合成各自品管(tts_split),音檔放 tts/sub/<音檔鍵>.wav,
    再用 assemble_line 接成整行;單句的行沿用 tts/<句編號>.wav(快取鍵與拆句機制出現前相同)。
    comma_profile:逗號停頓側寫(std | long,見 tts_pause.PROFILES)。非 std 時才在合成指令後附 --comma-profile(不進音檔鍵:cmd_sig 用原指令算),
    品管紀錄的 comma_profile 與要求不同 = 同一份音檔重新檢驗(引擎重做停頓後處理),裁切鍵加 |comma=<profile>;std 時所有鍵與舊版相同。"""
    tts_dir.mkdir(parents=True, exist_ok=True)
    if engine == "silent":
        return tts_silent(lines, tts_dir)
    ext = "mp3" if engine == "edge" else "wav"
    sig = TK.cmd_sig(tts_cmd)
    if comma_profile != "std" and tts_cmd:
        tts_cmd = list(tts_cmd) + ["--comma-profile", comma_profile]   # 在 cmd_sig 之後才附加:音檔鍵不變
    sub_dir = tts_dir / "sub"
    uniq = {}     # raw -> 單位(相同文字的子句共用一個音檔)
    for ln in lines:
        say = ln.get("say") or ln["text"]
        parts = [(say, 0.0)] if engine == "edge" else TS.split_clauses(say)
        ln["units"] = []
        for k, (csay, gap) in enumerate(parts):
            akey = TK.audio_key(engine, sig, voice, rate, csay)
            if len(parts) == 1:
                raw, label = tts_dir / f"{ln['idx']:03d}.{ext}", ln["idx"]
            else:
                raw, label = sub_dir / f"{akey}.{ext}", f"{ln['idx']}.{k + 1}"
            u = uniq.setdefault(raw, dict(raw=raw, say=csay, akey=akey, label=label, single=len(parts) == 1,
                                          comma_profile=comma_profile))
            ln["units"].append(dict(raw=raw, say=csay, gap=gap))
    if any(not u["single"] for u in uniq.values()):
        sub_dir.mkdir(exist_ok=True)
    units = list(uniq.values())
    if not no_synth:
        moved = relocate_tts_cache({u["label"]: u["akey"] for u in units if u["single"]}, tts_dir, ext)
        if moved:
            log(f"TTS 快取: 依文字鍵搬移 {moved} 句到新的句編號")
    todo, pron_redo, why = [], [], {}    # why:單位標籤 -> 未命中原因(凍結中止訊息用)
    for u in units:
        key = TK.full_key(u["akey"], None if engine == "edge" else QC_VER)
        raw = u["raw"]
        keyf = raw.with_suffix(".key")
        old = keyf.read_text() if raw.exists() and keyf.exists() else None
        if engine == "edge":
            if old != key:
                todo.append((u["say"], raw, keyf, key, u["label"]))
                why[u["label"]] = "無快取(新句或文字改)" if old is None else "文字或合成參數改(key 不同)"
            continue
        # 外部引擎:除了鍵相符,還要有目前 QC 版本的紀錄才直接沿用;音檔鍵相同的舊音檔(品管版本不同)送去重新檢驗
        u["qc"] = _qc_record(raw, key) if old == key else None
        if u["qc"] is not None and engine in ("chattts", "cosy3") and u["qc"].get("qc") != "none" \
                and (u["qc"].get("comma_profile") or "std") != comma_profile:   # 同一份音檔、只換停頓側寫:重新檢驗(不重錄)
            why[u["label"]] = f"逗號停頓側寫改({u['qc'].get('comma_profile') or 'std'} -> {comma_profile})"
            u["qc"] = None
            todo.append((u["say"], raw, keyf, key, u["label"], True))
            continue
        same_audio = old is not None and TK.audio_part(old) == u["akey"]
        if same_audio and _pron_changed(engine, u, u["qc"]):  # 讀音表改過:不沿用、不重新檢驗,直接重錄
            rec = u["qc"] or _qc_json(raw)
            u["qc"], same_audio = None, False
            pron_redo.append(u["label"])
            kinds = "/".join(n for n, f in (("讀音表", CT.pron_changed), ("英文表", CT.terms_changed)) if f(rec, u["say"]))
            why[u["label"]] = f"{kinds or '讀音/英文表'}改(key 不同)"
        elif old is None:
            why[u["label"]] = "無快取(新句或文字改)"
        elif not same_audio:
            why[u["label"]] = "文字或合成參數改(key 不同)"
        elif frozen and u["qc"] is None:   # 凍結:音檔鍵相符、只有品管版本/紀錄不同 -> 品管已定案,沿用現有音檔與紀錄,不重新檢驗、不改 .key
            u["qc"] = _qc_json(raw)
            continue
        else:
            why[u["label"]] = "品管版本或紀錄不符,需重新檢驗(key 不同)"
        if u["qc"] is None:
            todo.append((u["say"], raw, keyf, key, u["label"], same_audio))
    if pron_redo:
        log(f"cosy3 讀音/英文寫法變更 {len(pron_redo)} 句重錄: {', '.join(str(x) for x in pron_redo)}")
    n_multi = sum(1 for ln in lines if len(ln["units"]) > 1)
    log(f"TTS 快取[{engine}]: {len(lines)} 行 = {len(units)} 個配音單位(其中 {n_multi} 行拆成子句);"
        f"命中 {len(units) - len(todo)}、需合成或重新檢驗 {len(todo)}")
    if todo and no_synth:
        sys.exit(f"--no-synth: 有 {len(todo)} 個單位的配音快取沒有命中(單位 {', '.join(str(t[4]) for t in todo[:20])}"
                 f"{' …' if len(todo) > 20 else ''}),已中止,沒有動任何音檔")
    if todo and frozen:
        frozen_abort(frozen, [(t[4], why.get(t[4], "key 不同")) for t in todo])
    if todo:
        if engine == "edge":
            log(f"TTS[{engine}]: 產生 {len(todo)} 句 ({voice} {rate})")
            _synth_edge(todo, voice, rate)
        else:
            if not tts_cmd:
                sys.exit(f"--tts-engine {engine} 需要 --tts-cmd")
            n_ver = sum(1 for t in todo if t[5])
            log(f"TTS[{engine}]: 重新檢驗既有音檔 {n_ver} 個、新合成 {len(todo) - n_ver} 個 ({voice} {rate}, {QC_VER})")
            _synth_external(todo, tts_cmd, voice, rate, tts_dir)
            keys = {t[1]: t[3] for t in todo}
            for u in units:
                if u["raw"] in keys:
                    u["qc"] = _qc_record(u["raw"], keys[u["raw"]])
    if engine != "edge":
        failed = write_qc_report(units, {t[4] for t in todo}, tts_dir.parent / "tts_qc.json")
        if failed:
            log(f"警告: TTS 品管未通過 {len(failed)} 個單位(已取重試中最佳者): "
                + "; ".join(f"{i} {'/'.join(f)}" for i, f in failed))
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(_trim_one, units))
    for ln in lines:
        for cu in ln["units"]:
            cu["wav"] = uniq[cu["raw"]]["wav"]
            cu["qc"] = uniq[cu["raw"]].get("qc")
        ln["raw"] = ln["units"][0]["raw"]
        ln["qc"] = uniq[ln["units"][0]["raw"]].get("qc") if len(ln["units"]) == 1 else None
        assemble_line(ln, tts_dir)


# ---------------------------------------------------------------- 時間軸
def anim_hold_pads(lines, durs, gap, section_gap, tlmeta=None, card_min=0.0, img_min=0.0):
    """動畫鏡頭「最後一步完全顯示後至少停留 ANIM_HOLD 秒」:鏡頭(連續句)太短時,在該鏡頭最後一句之後補靜音,
    鏡頭就延到下一句的開頭之後(下一句的配音、字幕與畫面都順延,畫面與聲音仍同步)。
    卡片同理:緊接在獨立畫面(動畫 / quote / compare)前面的卡片(卡片不能蓋到它們)不足 card_min 秒時,在卡片最後一句後補靜音。
    圖片 / quote / compare / 影片鏡頭低於最短時長、且相鄰沒有可借時間的影片鏡頭時(img_min > 0),同樣在鏡頭最後一句後補靜音。
    回傳每句「句後補的靜音秒數」。動畫鏡頭內部的句間停頓不變。"""
    n = len(lines)
    gaps = [(section_gap if lines[i + 1]["sec"] != lines[i]["sec"] else gap) if i + 1 < n else TAIL for i in range(n)]
    pads = [0.0] * n
    pos = {ln["idx"]: i for i, ln in enumerate(lines)}
    for run in group_runs(lines):
        if run["key"][0] != "anim":
            continue
        errs = []
        if any(parse_anim(ln, tlmeta, errs) is None for ln in run["lines"]) or errs:
            continue    # 規格錯誤的由 check_anim 報告
        items, t = [], 0.0
        for ln in run["lines"]:
            i = pos[ln["idx"]]
            items.append(dict(anim=ln["anim"], t0=t))
            t += durs[i] + gaps[i]
        fin, hold = anim_finish(items)
        if t < fin + hold:
            pads[pos[run["lines"][-1]["idx"]]] = fin + hold - t + 2.0 / FPS   # 多 2 格,吸收 f0 取整的誤差
    if card_min > 0:
        i = 0
        while i < n:
            if not lines[i].get("card"):
                i += 1
                continue
            j = i
            while j + 1 < n and lines[j + 1].get("card") == lines[i]["card"]:
                j += 1
            if j + 1 < n and visual_key(lines[j + 1])[0] in ("anim", "quote", "compare"):
                t = sum(durs[k] + gaps[k] + pads[k] for k in range(i, j + 1))
                if t < card_min:
                    pads[j] += card_min - t + 2.0 / FPS
            i = j + 1
    if img_min > 0:   # 圖片 / quote / compare / 影片鏡頭太短又借不到時間(相鄰不是可借的影片鏡頭):在鏡頭最後一句後補靜音
        runs = group_runs(lines)

        def rdur(r):
            return sum(durs[pos[l["idx"]]] + gaps[pos[l["idx"]]] + pads[pos[l["idx"]]] for l in r["lines"])
        for k, run in enumerate(runs):
            kind = run["key"][0]
            if kind == "img":
                mn = img_min
            elif kind == "quote":
                mn = max(SPECIAL_MIN, quote_chars(run["lines"][0]["quote"]) / QUOTE_CPS)
            elif kind == "compare":
                mn = SPECIAL_MIN
            elif kind == "v":
                mn = VIDEO_MIN
            else:
                continue
            need = mn - rdur(run)
            if need <= 0:
                continue
            borrow = BORROW_VIDEO if kind == "v" else BORROW_IMAGE
            nbr = [runs[x] for x in (k + 1, k - 1) if 0 <= x < len(runs)]
            if any(r["key"][0] == "v" and rdur(r) - borrow >= VIDEO_MIN for r in nbr):
                need -= borrow    # 剩下的由 stitch_min 向相鄰影片鏡頭借
            if need > 0:
                pads[pos[run["lines"][-1]["idx"]]] += need + 2.0 / FPS
    for i in range(n - 1):   # 行尾 "pause": 秒數 = 句後總靜音下限(句間/段間停頓 + 上面的補靜音,取最大值不相加;最後一句不套)
        p = lines[i].get("pause")
        if p is not None:
            pads[i] = max(pads[i], float(p) - gaps[i])
    return pads


def pause_padded(ln, pad, gap):
    """這句的補靜音是否由 pause 決定(log 標記用)。"""
    p = ln.get("pause")
    return p is not None and pad > 0 and abs(pad + gap - float(p)) < 1e-9


def build_timeline(lines, gap, section_gap, tlmeta=None, card_min=0.0, img_min=0.0):
    with ThreadPoolExecutor(8) as ex:
        durs = list(ex.map(lambda l: probe_duration(l["wav"]), lines))
    pads = anim_hold_pads(lines, durs, gap, section_gap, tlmeta, card_min, img_min)
    t = 0.0
    for i, (ln, d) in enumerate(zip(lines, durs)):
        ln["vstart"], ln["dur"], ln["vend"], ln["pad_after"] = t, d, t + d, pads[i]
        if i + 1 < len(lines):
            t = ln["vend"] + pads[i] + (section_gap if lines[i + 1]["sec"] != ln["sec"] else gap)
    if any(pads):
        gaps = [(section_gap if lines[i + 1]["sec"] != ln["sec"] else gap) if i + 1 < len(lines) else TAIL
                for i, ln in enumerate(lines)]
        log("補靜音(動畫最後一步完全顯示後至少 %.1f 秒;卡片接獨立畫面時至少卡片最短秒數;標 pause 的是行尾 pause 指定): " % ANIM_HOLD
            + ", ".join(f"句{ln['idx']} +{pd:.2f}s" + ("(pause)" if pause_padded(ln, pd, g) else "")
                        for ln, pd, g in zip(lines, pads, gaps) if pd))
    total = lines[-1]["vend"] + pads[-1] + TAIL
    for i, ln in enumerate(lines):
        ln["f0"] = round(ln["vstart"] * FPS)
    for i, ln in enumerate(lines):
        ln["f1"] = lines[i + 1]["f0"] if i + 1 < len(lines) else round(total * FPS)
    return total, round(total * FPS)


# ---------------------------------------------------------------- 挑片段
DARK_Y = 28.0       # 候選鏡頭頭/中/尾三格的平均亮度(Y)低於此值視為黑畫面
SKIP_Y = 16.0       # 低於此值的候選直接跳過(提亮也救不回來)
LIFT_Y = 40.0       # 平均亮度低於此值的影片鏡頭自動提亮
LIFT_GAMMA = (1.25, 1.40)  # 提亮用的 eq gamma:Y=LIFT_Y 時取前者,越暗越高,Y<=SKIP_Y 時取後者(gamma 不動白點,不會過曝)
SAME_SRC_GAP = 20.0  # 相鄰鏡頭取自同一段素材(clips 的同一筆)時,起點至少相隔秒數
ZOOM_MAX = 1.25      # 為了把內嵌字幕/浮水印推出畫面,cover 之後最多再放大的倍率
_luma_cache = {}
_luma_file = None
_dim_cache = {}


def lift_gamma(y):
    """影片鏡頭的提亮 gamma;不需要提亮(或亮度未知)回傳 None。"""
    if y is None or y >= LIFT_Y:
        return None
    lo, hi = LIFT_GAMMA
    return lo + (hi - lo) * min(1.0, (LIFT_Y - y) / (LIFT_Y - SKIP_Y))


def load_luma_cache(path):
    """亮度探測結果存檔(--check-only 與正式渲染共用同一份,重跑不必再探測)。"""
    global _luma_file
    _luma_file = Path(path)
    if _luma_file.exists():
        try:
            _luma_cache.update(json.loads(_luma_file.read_text(encoding="utf-8")))
        except ValueError:
            pass


def save_luma_cache():
    if _luma_file:
        _luma_file.write_text(json.dumps(_luma_cache), encoding="utf-8")


def luma_at(media, src, t, crop=None):
    key = f"{src}@{round(t, 1)}@{crop or ''}"
    if key not in _luma_cache:
        try:
            out = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}", "-i",
                       media / "raw" / f"{src}.mp4", "-frames:v", "1",
                       "-vf", (f"crop={crop}," if crop else "") + "scale=64:36,format=gray", "-f", "rawvideo", "-"])
            _luma_cache[key] = sum(out) / len(out) if out else 0.0
        except RuntimeError:
            _luma_cache[key] = 255.0  # 讀不到就不當作黑畫面(後續渲染時會報真正的錯)
    return _luma_cache[key]


def brightness(media, src, start, length, crop=None):
    ts = [start + 0.1, start + length / 2, start + max(0.1, length - 0.1)]
    return sum(luma_at(media, src, t, crop) for t in ts) / 3


def probe_dims(path):
    path = str(path)
    if path not in _dim_cache:
        out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                   "-of", "csv=p=0", path]).decode().strip().split(",")
        _dim_cache[path] = (int(out[0]), int(out[1]))
    return _dim_cache[path]


def find_clip(clips, src, t):
    """手動指定的鏡頭:找出涵蓋該時間點的 clips 條目(取其 crop / top / bottom)。"""
    for c in clips or []:
        if c["src"] == src and c["start"] - 0.5 <= t <= c["end"] + 0.5:
            return c
    return None


def frame_spec(media, src, clip):
    """影片鏡頭取景:clip["crop"] 去黑邊 -> cover 到 WxH -> 依 top/bottom(去黑邊後畫面的可見垂直範圍)
    額外放大(上限 ZOOM_MAX)並平移,讓內嵌字幕/浮水印/角標落在畫面外。回傳 dict(vf, zoom, leak)。
    leak:放到上限仍遮不掉時,禁區露出的像素高度(0 = 完全在畫面外)。"""
    clip = clip or {}
    sw0, sh0 = probe_dims(media / "raw" / f"{src}.mp4")
    crop = clip.get("crop")
    cw, ch = (int(x) for x in crop.split(":")[:2]) if crop else (sw0, sh0)
    k0 = max(W / cw, H / ch)
    a, b = float(clip.get("top", 0.0)), float(clip.get("bottom", 1.0))
    z = min(ZOOM_MAX, max(1.0, H / ((b - a) * ch * k0)))
    sw, sh = math.ceil(cw * k0 * z / 2) * 2, math.ceil(ch * k0 * z / 2) * 2
    lo, hi = a * sh, b * sh - H              # 平移量 oy 的容許範圍(畫面上緣對應縮放後的 y)
    oy = (sh - H) / 2
    if hi < lo:                              # 兩頭顧不了:下方(字幕)優先
        oy = hi
    else:
        oy = min(max(oy, lo), hi)
    oy = round(min(max(oy, 0), sh - H))
    ox = (sw - W) // 2
    leak = max(0.0, (oy + H) - b * sh) + max(0.0, a * sh - oy)
    vf = (f"crop={crop}," if crop else "") + f"scale={sw}:{sh},crop={W}:{H}:{ox}:{oy}"
    return dict(vf=vf, zoom=round(z, 3), leak=round(leak, 1))


REUSE_GAP = 60.0     # 重用已用過的畫面時,與同一段畫面的每一次使用在成片上至少相隔秒數
REUSE_STEP = 0.5     # 重用時在片段內找起點的步距(秒)
REUSE_PROBES = 6     # 重用時最多量幾個候選的亮度
CUT_GUARD = 0.1      # 硬切時間的誤差餘量(秒):鏡頭頭尾各往外多看這麼多,起點/終點貼著硬切時也離開這麼遠


def cut_violations(clip, start, length):
    """影片鏡頭用到的素材區段 [start, start+length] 內,離頭或尾不到 VIDEO_MIN 秒的來源硬切(秒)。
    硬切時間來自 clips 的 cuts 欄位(片段建檔時用 clip_scan.scene_cuts 偵測);沒有該欄位 = 沒建檔,不檢查。
    例:dei v1 句 77 的片段在結束前 0.13 秒遇到預告本身的硬切,成片出現 0.13 秒的閃格。"""
    end, mn = start + length, (clip or {}).get("cut_min", VIDEO_MIN)  # cut_min:片段可覆寫(快剪預告用,clips.json 片段欄位)
    return [c for c in (clip or {}).get("cuts") or ()
            if start - CUT_GUARD < c < end + CUT_GUARD and (c - start < mn or end - c < mn)]


class ClipPicker:
    def __init__(self, clips, max_per_src, media, seed=20240607):
        self.clips = clips
        self.max_per_src = max_per_src
        self.media = media
        self.rng = random.Random(seed)
        self.used = defaultdict(list)
        self.usage = defaultdict(float)
        self.gap = SAME_SRC_GAP
        self.avoid = []   # [(clip, start)] 時間上相鄰、已定案的影片鏡頭:同一段素材要避開相近位置,並盡量換來源
        self.warnings = []
        self.hist = []    # [(src, a, b, t0, t1)] 每次使用的素材區間與它在成片上的起訖秒(重用時檢查相隔多久)
        self.at = None    # 正在挑的鏡頭在成片上的 (起, 訖) 秒;有設才記入 hist

    def snapshot(self):
        return ({k: list(v) for k, v in self.used.items()}, dict(self.usage), self.rng.getstate(), len(self.warnings),
                len(self.hist))

    def restore(self, st):
        self.used = defaultdict(list, {k: list(v) for k, v in st[0].items()})
        self.usage = defaultdict(float, st[1])
        self.rng.setstate(st[2])
        del self.warnings[st[3]:]
        del self.hist[st[4]:]

    def mark(self, src, a, b):
        self.used[src].append((a, b))
        self.usage[src] += b - a
        if self.at:
            self.hist.append((src, a, b, self.at[0], self.at[1]))

    def _free(self, clip):
        segs = [(clip["start"], clip["end"])]
        for ua, ub in sorted(self.used[clip["src"]]):
            nxt = []
            for a, b in segs:
                if ub <= a or ua >= b:
                    nxt.append((a, b))
                    continue
                if ua > a:
                    nxt.append((a, ua))
                if ub < b:
                    nxt.append((ub, b))
            segs = nxt
        return segs

    def _rand_start(self, clip, a, b, length):
        """在可用區間 [a, b-length] 內隨機取起點;相鄰鏡頭取自同一段素材時避開 +-self.gap(預設 SAME_SRC_GAP)。"""
        ranges = [(a, b - length)]
        for ac, ls in self.avoid:
            if ac is not clip:
                continue
            nxt = []
            for x, y in ranges:
                if y < ls - self.gap or x > ls + self.gap:
                    nxt.append((x, y))
                    continue
                if x < ls - self.gap:
                    nxt.append((x, ls - self.gap))
                if y > ls + self.gap:
                    nxt.append((ls + self.gap, y))
            ranges = nxt
        ranges = [(x, y) for x, y in ranges if y >= x]
        if not ranges:
            return None
        x, y = self.rng.choices(ranges, weights=[max(1e-6, y - x) for x, y in ranges])[0]
        return round(max(x, min(self.rng.uniform(x, y), y)), 2)

    def _cut_fix(self, clip, a, b, start, length):
        """start 起的 length 秒若有離頭尾太近的硬切:改成從某個硬切之後起、或收在某個硬切之前(離 start 最近的優先);
        可用區間 [a, b] 內放不下回傳 None(換候選)。"""
        if not cut_violations(clip, start, length):
            return start
        for c in sorted(clip.get("cuts") or (), key=lambda c: abs(c - start)):
            for x in (round(c + CUT_GUARD, 2), round(c - CUT_GUARD - length, 2)):
                if (a <= x <= b - length and not cut_violations(clip, x, length)
                        and not any(ac is clip and abs(x - ls) < self.gap for ac, ls in self.avoid)):
                    return x
        return None

    def note_manual(self, idx, src, start, length, crop=None):
        """手動指定的鏡頭:檢查亮度,只警告。"""
        y = brightness(self.media, src, start, length, crop)
        if y < DARK_Y:
            self.warnings.append(f"句{idx}: 指定鏡頭 {src}@{start} 平均亮度 Y={y:.1f} 太暗")
        return y

    def pick(self, tag, length):
        """回傳 (clip, start, 亮度);挑不到回傳 None。"""
        by_src = defaultdict(list)
        for c in self.clips:
            if tag not in c.get("tags", []):
                continue
            if self.usage[c["src"]] + length > self.max_per_src:
                continue
            for a, b in self._free(c):
                if b - a >= length:
                    by_src[c["src"]].append((c, a, b))
        if not by_src:
            return None
        near = {c["src"] for c, _ in self.avoid if c}
        order = sorted(by_src, key=lambda s: (s in near, self.usage[s], self.rng.random()))
        best, black, probes = None, None, 0  # black:Y < SKIP_Y 的候選,只在完全沒有別的可用時才墊底
        for src in order:
            for _ in range(8):
                c, a, b = self.rng.choice(by_src[src])
                start = self._rand_start(c, a, b, length)
                if start is not None:
                    start = self._cut_fix(c, a, b, start, length)
                if start is None:
                    continue
                probes += 1
                y = brightness(self.media, src, start, length, c.get("crop"))
                if y < SKIP_Y:
                    if black is None or y > black[0]:
                        black = (y, c, start)
                elif best is None or y > best[0]:
                    best = (y, c, start)
                if y >= DARK_Y or probes >= 24:
                    break
            if (best and best[0] >= DARK_Y) or probes >= 24:
                break
        if best is None and black is None:
            return None
        y, c, start = best or black
        if best is None:
            self.warnings.append(f"挑片段 tag={tag}: 所有候選都低於 Y={SKIP_Y:.0f},只能使用 {c['src']}@{start} (Y={y:.1f})")
        elif y < DARK_Y:
            self.warnings.append(f"挑片段 tag={tag}: 找不到夠亮的候選,退而使用 {c['src']}@{start} (Y={y:.1f},將自動提亮)")
        self.mark(c["src"], start, start + length)
        return c, start, y

    def pick_reuse(self, tag, length):
        """最後手段:重用同標籤已用過的畫面。條件:與重疊到的每一次使用在成片上相隔 >= REUSE_GAP 秒、同來源累計秒數(重用也計入)
        不超過上限、相鄰鏡頭取自同一段素材時起點仍相隔 self.gap 秒。優先用次數最少、離最近一次使用最久的。
        回傳 (clip, start, 亮度, 重疊到的使用次數, 與最近一次使用相隔秒數);挑不到回傳 None。"""
        t0, t1 = self.at
        cands = []
        for c in self.clips:
            room = c["end"] - c["start"] - length
            if tag not in c.get("tags", []) or room < -1e-6 or self.usage[c["src"]] + length > self.max_per_src:
                continue
            hs = [h for h in self.hist if h[0] == c["src"]]
            room = max(room, 0.0)
            xs = {round(c["start"] + k * REUSE_STEP, 2) for k in range(int(room / REUSE_STEP) + 1)}
            for x in sorted(xs | {round(c["start"] + room, 2)}):
                if any(ac is c and abs(x - ls) < self.gap for ac, ls in self.avoid) or cut_violations(c, x, length):
                    continue
                far = [max(h[3] - t1, t0 - h[4]) for h in hs if h[1] < x + length and x < h[2]]
                if all(d >= REUSE_GAP for d in far):
                    cands.append((len(far), -min(far, default=0.0), c["src"], x, c))
        cands.sort(key=lambda k: k[:4])
        best = None
        for n, far, src, x, c in cands[:REUSE_PROBES]:
            y = brightness(self.media, src, x, length, c.get("crop"))
            if best is None or y > best[0]:
                best = (y, c, x, n, -far)
            if y >= DARK_Y:
                break
        if best is None:
            return None
        y, c, x, n, far = best
        self.mark(c["src"], x, x + length)
        return c, x, y, n, far


# ---------------------------------------------------------------- 計畫鏡頭
# 鏡頭 = 連續句子共用的一個畫面。連續句子的畫面規格相同(同標籤 / 同一張圖 / 同一個 quote、compare / 同一個 anim)
# 就併成一段(run);影片 run 再依句界切成 VIDEO_MIN ~ VIDEO_MAX 秒的鏡頭,其餘一段就是一個鏡頭。
FX_CYCLE = ["tilt_l", "tilt_r", "zoom"]   # photo 組(遊戲截圖、實機照片、kind=photo 的圖)
FX_CYCLE_TEXT = ["drift_r", "drift_l"]     # text 組(閱讀卡與文字為主的網頁截圖;2026-10-22 PLAN_閱讀卡 #4):極慢 zoom + 水平漂移,不傾斜
ZOOM_END_TEXT = 1.04   # text 組 zoom 終點倍率上限(1.00 -> 1.04)
DRIFT_PX = 24          # text 組水平漂移:整個鏡頭期間由 -24px 慢移到 +24px(drift_l 反向)
LEGACY_TILT = False    # --legacy-tilt:有 .boxes.json 的舊圖(沒有 layout kind)也照 photo 組輪用 tilt,舊片重渲染要保持原外觀時用
VIDEO_MIN = 2.5      # 影片鏡頭最短秒數
VIDEO_MAX = 8.0      # 同一影片片段最長秒數(超過就換同標籤的另一段)
VIDEO_SPLIT = 6.5    # 影片鏡頭超過這個長度就等分
P_VIDEO_MAX, P_VIDEO_SPLIT = 5.0, 4.5   # 直式(--portrait)用的上限與等分門檻(main 換上)
SPECIAL_MIN = 3.5    # quote / compare 最短秒數
QUOTE_CPS = 8.0      # quote:每 8 個字至少 1 秒
IMG_MAX = 9.0        # 同一張圖連續顯示上限(秒)
IMG_MAX_UNITS = 2    # 同一張圖連續句數上限(為了湊最短時長而併在一起的短句算 1 句)
BORROW_IMAGE = 1.2   # 圖片/quote/compare 不足最短時長時,最多向相鄰影片鏡頭借幾秒
BORROW_VIDEO = 0.8   # 影片鏡頭不足最短時長時,最多向相鄰影片鏡頭借幾秒


def special_imgs(ln):
    """quote / compare 句用到的圖片名(用來檢查存在與同圖連續)。"""
    if ln.get("quote"):
        return [ln["img"]] if ln.get("img") else []
    if ln.get("compare"):
        return [ln["compare"][sd]["img"] for sd in ("left", "right")]
    return []


def _jkey(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def visual_key(ln):
    """這一句的畫面規格;相鄰句子規格相同就共用鏡頭。"""
    a = ln.get("anim")
    if isinstance(a, dict):  # timeline 連續 step 是同一個連續鏡頭;其餘動畫規格完全相同才合併
        if a.get("type") == "list" and isinstance(a.get("step"), int):  # list 的各 step 同樣是一個連續鏡頭
            return ("anim", "list:" + _jkey({k: v for k, v in a.items() if k != "step"}))
        if a.get("type") in LEVEL_TYPES and "step" in a:  # bars(step = "title" 或 0..n-1)/ versus / flow / cols / share / num 逐步模式同理
            return ("anim", a["type"] + ":" + _jkey({k: v for k, v in a.items() if k != "step"}))
        if a.get("type") == "timeline":  # 自帶 points 的 timeline:同一組 points(含 question_between)才是同一鏡;無 points = 頂層共用組
            own = {k: a[k] for k in ("points", "question_between") if k in a}
            return ("anim", "timeline" + (":" + _jkey(own) if own else ""))
        return ("anim", _jkey(a))
    if ln.get("shots"):
        return ("manual", ln["idx"])
    if ln.get("quote"):
        return ("quote", _jkey([ln["quote"], ln.get("img")]))
    if ln.get("compare"):
        return ("compare", _jkey(ln["compare"]))
    if ln.get("img"):
        return ("img", ln["img"])
    if ln.get("v"):
        return ("v", ln["v"])
    return ("none", ln["idx"])


def group_runs(lines):
    runs = []
    for ln in lines:
        k = visual_key(ln)
        if runs and runs[-1]["key"] == k and k[0] not in ("manual", "none"):
            runs[-1]["lines"].append(ln)
        else:
            runs.append(dict(key=k, lines=[ln]))
    return runs


def video_groups(ls):
    """同標籤的連續句:依句界切段,短於 VIDEO_MIN 的句子併入下一句(最後一句太短就併入前一段)。回傳 [[f0, f1, 首句, 末句]]。"""
    vmin = round(VIDEO_MIN * FPS)
    groups, cur = [], None
    for ln in ls:
        if cur is None:
            cur = [ln["f0"], ln["f1"], ln["idx"], ln["idx"]]
        else:
            cur[1], cur[3] = ln["f1"], ln["idx"]
        if cur[1] - cur[0] >= vmin:
            groups.append(cur)
            cur = None
    if cur is not None:
        if groups:
            groups[-1][1], groups[-1][3] = cur[1], cur[3]
        else:
            groups.append(cur)
    return groups


def quote_chars(q):
    return sum(1 for ch in q.get("text", "") if not ch.isspace())


def shot_min_frames(s, img_min):
    if s["kind"] == "video":
        return round(VIDEO_MIN * FPS)
    sp = s.get("special")
    if sp == "anim":
        return 0  # 動畫鏡頭另外檢查(動畫長度 + 0.5 秒)
    if sp == "quote":
        return round(max(SPECIAL_MIN, quote_chars(s["quote"]) / QUOTE_CPS) * FPS)
    if sp == "compare":
        return round(SPECIAL_MIN * FPS)
    return round(img_min * FPS)


def kind_name(s):
    return {"anim": "動畫", "quote": "quote", "compare": "compare"}.get(s.get("special")) or \
        ("影片" if s["kind"] == "video" else "圖片")


def img_kind(media, img):
    """圖的動態分組:"text"(極慢 zoom + 漂移)| "photo"(tilt/zoom 輪替)。
    images/<img>.layout.json 有 kind 就照它;沒有 kind 但有 .boxes.json 的舊圖視為 text(LEGACY_TILT 時視為 photo);其餘(遊戲截圖)photo。"""
    if LEGACY_TILT:
        return "photo"
    f = media / "images" / f"{img}.layout.json"
    if f.exists():
        try:
            k = json.loads(f.read_text(encoding="utf-8")).get("kind")
        except ValueError:
            k = None
        if k in ("text", "photo"):
            return k
    return "text" if _load_boxes(media, img) else "photo"


def layout_shots(lines, kind_of=None):
    """第一階段:只排鏡頭的時間(尚未挑影片片段)。kind_of(img) -> "text"|"photo" 決定圖片鏡頭預設 fx 用哪一組。回傳 (shots, errors)。"""
    shots, errors = [], []
    fx_i = tx_i = tilt_dir = 0
    for run in group_runs(lines):
        kind, ls = run["key"][0], run["lines"]
        a, b = ls[0], ls[-1]
        base = dict(line=a["idx"], last_line=b["idx"], j=0, f0=a["f0"], frames=b["f1"] - a["f0"])
        if kind == "anim":
            shots.append(dict(base, kind="image", img=f"@anim{a['idx']}", fx="none", special="anim", hls=[],
                              parts=[dict(line=l["idx"], frames=l["f1"] - l["f0"], anim=l["anim"]) for l in ls]))
        elif kind in ("quote", "compare"):
            shots.append(dict(base, kind="image", img=f"@{kind}{a['idx']}", fx="none", special=kind, hls=[],
                              quote=a.get("quote"), compare=a.get("compare"), bg_img=a.get("img")))
        elif kind == "img":
            fx = next((l["fx"] for l in ls if l.get("fx") is not None), None)
            if fx is None:
                if kind_of and kind_of(a["img"]) == "text":
                    fx = FX_CYCLE_TEXT[tx_i % len(FX_CYCLE_TEXT)]
                    tx_i += 1
                else:
                    fx = FX_CYCLE[fx_i % len(FX_CYCLE)]
                    fx_i += 1
            if fx == "tilt":
                fx = "tilt_l" if tilt_dir % 2 == 0 else "tilt_r"
                tilt_dir += 1
            if fx == "drift":
                fx = FX_CYCLE_TEXT[tx_i % len(FX_CYCLE_TEXT)]
                tx_i += 1
            if fx not in ("tilt_l", "tilt_r", "zoom", "drift_l", "drift_r", "none"):
                errors.append(f"句{a['idx']}: 不支援的 fx '{fx}'")
                fx = "none"
            shots.append(dict(base, kind="image", img=a["img"], fx=fx,
                              hls=[dict(line=l["idx"], kws=l["hl"], f0=l["f0"], tw=hl_word_time(l, l["hl"])) for l in ls if l.get("hl")],
                              focus=[l["focus"] for l in ls if l.get("focus")]))
        elif kind == "manual":
            k, F = len(a["shots"]), a["f1"] - a["f0"]
            for j, sp in enumerate(a["shots"]):
                shots.append(dict(base, kind="video", manual=True, src=sp["src"], start=float(sp["start"]), j=j,
                                  f0=a["f0"] + F * j // k, frames=F * (j + 1) // k - F * j // k))
        elif kind == "v":
            for g0, g1, la, lb in video_groups(ls):
                shots.append(dict(kind="video", tag=a["v"], line=la, last_line=lb, j=0, f0=g0, frames=g1 - g0))
        else:
            errors.append(f"句{a['idx']}: 缺畫面(沒有 v / img / quote / compare / anim / shots)")
            shots.append(dict(base, kind="video", tag=None))
    return shots, errors


def stitch_min(shots, img_min):
    """鏡頭不足最短時長時,向相鄰的影片鏡頭借時間(先借後面、再借前面;借完對方仍須 >= VIDEO_MIN,且有上限)。
    圖片鏡頭因此會提早出現或多停留一下;hl 底線仍在該詞被唸到的那一句開始時畫出。借不到的留給檢查報錯。"""
    vmin = round(VIDEO_MIN * FPS)
    for i, s in enumerate(shots):
        need = shot_min_frames(s, img_min) - s["frames"]
        if need <= 0 or s.get("manual") or (s["kind"] == "video" and not s.get("tag")):
            continue
        if need > round((BORROW_VIDEO if s["kind"] == "video" else BORROW_IMAGE) * FPS):
            continue
        nx = shots[i + 1] if i + 1 < len(shots) else None
        pv = shots[i - 1] if i else None

        def ok(d):
            return d is not None and d["kind"] == "video" and d.get("tag") and not d.get("manual") \
                and d["frames"] - need >= vmin
        if ok(nx):
            nx["f0"] += need
            nx["frames"] -= need
            s["frames"] += need
        elif ok(pv):
            pv["frames"] -= need
            s["f0"] -= need
            s["frames"] += need


def pick_videos(shots, media, clips, max_per_src, fallback=None):
    """第二階段:替影片鏡頭挑片段。素材少的標籤(指名特定畫面的子標籤)先挑,免得被通用標籤用掉;
    太長(> VIDEO_SPLIT)就等分成幾段,挑不到再試著多分一段。相鄰鏡頭盡量換來源,同一段素材則避開相近位置。
    回傳 (新的 shots, errors, warnings, 各來源使用秒數, 補救統計 dict(split, fallback, reuse))。挑不到的鏡頭標 missing(--check-only 繼續檢查,正式渲染會中止)。"""
    # 自動補救:第一輪照原規則挑;挑不到的鏡頭留到第二輪(不影響第一輪已挑好的),依序試
    #   備援標籤(script 頂層 fallback[標籤] 的順序,同樣可等分成幾段)的未用片段 -> 重用同標籤已用過的畫面(ClipPicker.pick_reuse,每次列警告)。
    #   仍挑不到才報錯。fix 統計:split = 超過 VIDEO_MAX 或沒有單一未用片段夠長而分段的鏡頭數;fallback / reuse = 段數。
    picker = ClipPicker(clips or [], max_per_src, media)
    errors, fallback = [], fallback or {}
    fix = dict(split=0, fallback=0, reuse=0)
    vmin, split, vmax = round(VIDEO_MIN * FPS), round(VIDEO_SPLIT * FPS), round(VIDEO_MAX * FPS)
    avail = defaultdict(float)
    for c in clips or []:
        for t in c.get("tags", []):
            avail[t] += c["end"] - c["start"]
    placed = {}  # 原 shots 的索引 -> 定案的鏡頭清單
    for i, s in enumerate(shots):
        if s["kind"] != "video":
            placed[i] = [s]
        elif s.get("manual"):  # 先登記明確指定的 shots,避免自動挑到重疊區間
            s["clip"] = find_clip(clips, s["src"], s["start"])
            if not (media / "raw" / f"{s['src']}.mp4").exists():
                errors.append(f"句{s['line']}: raw/{s['src']}.mp4 不存在")
                s["missing"] = True
            else:
                picker.mark(s["src"], s["start"], s["start"] + s["frames"] / FPS)
                s["luma"] = picker.note_manual(s["line"], s["src"], s["start"], s["frames"] / FPS,
                                               (s["clip"] or {}).get("crop"))
            placed[i] = [s]

    def neighbor(i, edge):
        d = placed.get(i)
        if not d or d[edge]["kind"] != "video" or d[edge].get("missing") or not d[edge].get("clip"):
            return []
        return [(d[edge]["clip"], d[edge]["start"])]

    for d in list(placed.values()):  # 手動指定的鏡頭也記入使用紀錄(重用時要和它們相隔 REUSE_GAP 秒)
        for s in d:
            if s["kind"] == "video" and s.get("manual") and not s.get("missing"):
                picker.hist.append((s["src"], s["start"], s["start"] + s["frames"] / FPS,
                                    s["f0"] / FPS, (s["f0"] + s["frames"]) / FPS))
    for x in sorted({x for v in fallback.values() for x in v if not avail.get(x)}):
        picker.warnings.append(f"fallback 的備援標籤「{x}」不在 clips 裡")

    def counts(i):
        """第 i 個鏡頭的基本段數與可試的段數範圍(每段 >= VIDEO_MIN)。"""
        F = shots[i]["frames"]
        n0 = 1 if F <= split else math.ceil(F / split)
        return n0, range(n0, max(n0, F // vmin) + 1)

    def attempt(i, n, tags, reuse=False):
        """把第 i 個鏡頭等分成 n 段,每段依 tags 的順序挑未用片段;reuse:都挑不到時重用該鏡頭標籤已用過的畫面(列警告)。
        每段都挑到才回傳鏡頭清單,否則還原挑片狀態並回傳 None。"""
        s = shots[i]
        F = s["frames"]
        st, cand = picker.snapshot(), []
        for j in range(n):
            a, b = F * j // n, F * (j + 1) // n
            picker.avoid = neighbor(i - 1, -1) + neighbor(i + 1, 0) + [(c["clip"], c["start"]) for c in cand]
            picker.at = ((s["f0"] + a) / FPS, (s["f0"] + b) / FPS)
            r, extra = None, {}
            for tg in tags:
                r = picker.pick(tg, (b - a) / FPS)
                if r is not None:
                    extra = dict(fb=tg) if tg != s["tag"] else {}
                    break
            if r is None and reuse:
                r = picker.pick_reuse(s["tag"], (b - a) / FPS)
                if r is not None and r[3]:
                    extra = dict(reuse=r[3])
                    picker.warnings.append(
                        f"{_line_span(s)}: 標籤「{s['tag']}」未用片段不足,重用 {r[0]['src']}@{r[1]:.2f}-{r[1] + (b - a) / FPS:.2f}"
                        f"(這段畫面第 {r[3] + 1} 次使用,與最近一次相隔 {r[4]:.0f} 秒)")
            if r is None:
                picker.restore(st)
                return None
            c, start, y = r[:3]
            cand.append(dict(s, j=j, f0=s["f0"] + a, frames=b - a, src=c["src"], start=start, luma=y, clip=c,
                             mute=bool(c.get("mute")), **extra))
        return cand

    def settle(i, done):
        if len(done) > 1 and (shots[i]["frames"] > vmax or len(done) > counts(i)[0]):
            fix["split"] += 1
        placed[i] = done

    todo = [i for i in range(len(shots)) if i not in placed]
    failed = []
    for i in sorted(todo, key=lambda i: (avail.get(shots[i].get("tag"), 0.0), i)):
        tag = shots[i].get("tag")
        done = None
        # 先照規矩挑;挑不到再放寬「同一段素材要隔 SAME_SRC_GAP 秒」(仍不重疊);還是挑不到的留到第二輪補救
        if avail.get(tag):
            for gap, n in [(g, n) for g in (SAME_SRC_GAP, 3.0) for n in counts(i)[1]]:
                picker.gap = gap
                done = attempt(i, n, [tag])
                if done:
                    break
        picker.gap = SAME_SRC_GAP
        if done:
            settle(i, done)
        else:
            failed.append(i)
    for i in failed:  # 第二輪:備援標籤的未用片段 -> 重用同標籤已用過的畫面;修不了才報錯
        s = shots[i]
        F, tag = s["frames"], s.get("tag")
        fbs = [x for x in fallback.get(tag) or [] if avail.get(x)]
        done = None
        if fbs:
            for gap, n in [(g, n) for g in (SAME_SRC_GAP, 3.0) for n in counts(i)[1]]:
                picker.gap = gap
                done = attempt(i, n, [tag] + fbs)
                if done:
                    break
        if done is None and avail.get(tag):
            picker.gap = 3.0
            for n in counts(i)[1]:
                done = attempt(i, n, [tag] + fbs, reuse=True)
                if done:
                    break
        picker.gap = SAME_SRC_GAP
        if done is None:
            why = "片段不足、太短或來源已達使用上限" if avail.get(tag) else "clips 沒有這個標籤"
            errors.append(f"{_line_span(s)}: 標籤「{tag}」挑不到 {F / FPS:.1f} 秒的片段({why})")
            placed[i] = [dict(s, missing=True, src=None, start=0.0, luma=None, clip=None)]
            continue
        for d in done:
            if d.get("fb"):
                fix["fallback"] += 1
                log(f"備援: {_line_span(s)} 標籤「{tag}」未用片段不足,改用「{d['fb']}」{d['src']}@{d['start']}({d['frames'] / FPS:.1f} 秒)")
            if d.get("reuse"):
                fix["reuse"] += 1
        settle(i, done)
    return [x for i in range(len(shots)) for x in placed[i]], errors, picker.warnings, dict(picker.usage), fix


# ---------------------------------------------------------------- 卡片 PNG
CARD_BOTTOM_KEEP = 270  # 卡片組下緣至少離畫面底部的距離(避開字幕區)


def _fit_font(text, size, max_w, stroke):
    while size > 20:
        f = ImageFont.truetype(FONT, size, index=0)
        l, _, r, _ = f.getbbox(text, stroke_width=stroke)
        if r - l <= max_w:
            return f
        size -= 4
    return ImageFont.truetype(FONT, 20, index=0)


def make_card(card, path):
    max_w = int(W * 0.86)
    bigs = [s for s in card.get("big", "").split("|") if s]
    smalls = [s for s in card.get("small", "").split("|") if s]
    bsz, ssz = 320, 84
    while True:
        big_size = min((_fit_font(s, int(bsz), max_w, 14).size for s in bigs), default=int(bsz))
        small_size = min((_fit_font(s, int(ssz), max_w, 6).size for s in smalls), default=int(ssz))
        bh = int(big_size * (1.0 if len(bigs) > 1 else 1.1))  # 多行時行距收緊
        sh = int(small_size * 1.3)
        gap = 48 if bigs and smalls else 0
        total = bh * len(bigs) + gap + sh * len(smalls)
        if total <= H - CARD_BOTTOM_KEEP - 40 or bsz <= 120:
            break
        bsz, ssz = bsz * 0.92, ssz * 0.92
    fb = ImageFont.truetype(FONT, big_size, index=0)
    fs = ImageFont.truetype(FONT, small_size, index=0)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = (H - total) / 2
    if y + total > H - CARD_BOTTOM_KEEP:  # 垂直置中,但不侵入底部字幕區
        y = H - CARD_BOTTOM_KEEP - total
    for s in bigs:
        d.text((W / 2, y + bh / 2), s, font=fb, fill=(255, 255, 255, 255), anchor="mm",
               stroke_width=14, stroke_fill=(16, 16, 16, 255))
        y += bh
    y += gap
    for s in smalls:
        d.text((W / 2, y + sh / 2), s, font=fs, fill=(0xFF, 0xD4, 0x79, 255), anchor="mm",
               stroke_width=6, stroke_fill=(16, 16, 16, 255))
        y += sh
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


# 開場劇透警告(script.json 頂層 "spoiler": {"text": "標題|說明", "dur": 秒};沒有欄位就完全不加濾鏡)
SPOILER_TOP, SPOILER_FADE = 48, 0.4
SPOILER_TITLE_PX, SPOILER_SUB_PX = 54, 40
SPOILER_PAD_X, SPOILER_PAD_Y, SPOILER_GAP, SPOILER_RADIUS = 40, 24, 12, 24
SPOILER_BG_ALPHA = 179            # 約 70% 不透明黑
SPOILER_RED = (0xFF, 0x4D, 0x4D)


def make_spoiler(text, path):
    """畫劇透警告牌(只含牌子本身,透明底 RGBA)。回傳 (x, y, w, h):牌子在 1920x1080 畫面上的位置,水平置中、頂端 SPOILER_TOP。"""
    title, sep, sub = text.partition("|")
    if not sep:
        title, sub = "劇透警告", text
    ft = ImageFont.truetype(FONT, SPOILER_TITLE_PX, index=0)
    fs = ImageFont.truetype(FONT, SPOILER_SUB_PX, index=0)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    tw = d0.textlength(title, font=ft)
    sw = d0.textlength(sub, font=fs) if sub else 0
    w = int(max(tw, sw)) + 2 * SPOILER_PAD_X
    th, sh = int(SPOILER_TITLE_PX * 1.25), int(SPOILER_SUB_PX * 1.25)
    h = 2 * SPOILER_PAD_Y + th + ((SPOILER_GAP + sh) if sub else 0)
    if w > W - 120:
        sys.exit(f"劇透警告文字太長(牌寬 {w}px > {W - 120}px):{text}")
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=SPOILER_RADIUS, fill=(0, 0, 0, SPOILER_BG_ALPHA))
    d.text((w / 2, SPOILER_PAD_Y + th / 2), title, font=ft, fill=SPOILER_RED + (255,), anchor="mm")
    if sub:
        d.text((w / 2, SPOILER_PAD_Y + th + SPOILER_GAP + sh / 2), sub, font=fs, fill=(255, 255, 255, 255), anchor="mm")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return (W - w) // 2, SPOILER_TOP, w, h


def spoiler_filters(sp_cfg, png, in_idx, in_label, out_label):
    """劇透牌:靜態、只在最後 SPOILER_FADE 秒淡出。回傳 (額外輸入參數, filter 字串)。"""
    dur = float(sp_cfg.get("dur", 6.0))
    x, y, _, _ = make_spoiler(sp_cfg["text"], png)
    inp = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(png)]
    f = (f"[{in_idx}:v]format=rgba,fade=t=out:st={max(0.0, dur - SPOILER_FADE):.3f}:d={SPOILER_FADE}:alpha=1[spw];"
         f"[{in_label}][spw]overlay=x={x}:y={y}:format=auto:eof_action=pass[{out_label}]")
    return inp, f


# ---------------------------------------------------------------- 字幕
TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[,.:\-/'][A-Za-z0-9]+)*[%+]*|\s+|.", re.S)
FULL_PUNCT = set("，。？！、：；")
HALF_PUNCT = set(",;:?!")
STRIP_SET = FULL_PUNCT | HALF_PUNCT | set("… —-·\t")
OPENERS, CLOSERS = set("「《『（("), set("」》』）)")
SUB_PUNCT = set("，。、？！：；「」『』《》（）()…·—-,;:?!\"“”‘’~～.'[]{}<>【】〈〉〔〕–‧•⋯")   # 字幕不顯示的標點(2026-10-10 使用者指定:字幕只留純文字)
SUB_SYMBOLS = set("%％#＃&＆@＠/／*＊\\")   # Unicode 標點類但字幕照留的符號(60%、A/B)


def _sub_punct(x):
    """字幕不顯示的單一 token:SUB_PUNCT,或其他 Unicode 標點(P 類;SUB_SYMBOLS 除外)。英數詞內的符號包在詞 token 裡,不受影響。"""
    return x in SUB_PUNCT or (len(x) == 1 and unicodedata.category(x)[0] == "P" and x not in SUB_SYMBOLS)


def _tw(tok):
    if tok.isspace():
        return 0.5
    return 0.5 * len(tok) if ord(tok[0]) < 128 else 1.0


def _is_punct(tok):
    return tok in FULL_PUNCT or tok in HALF_PUNCT


def _strip(toks):
    a, b = 0, len(toks)
    while a < b and toks[a] in STRIP_SET:
        a += 1
    while b > a and toks[b - 1] in STRIP_SET:
        b -= 1
    return toks[a:b]


def _clean_sub(toks):
    """字幕顯示文字:單獨的標點字元換成一個半形空格(數字內的小數點等包在英數字詞裡,不動),連續空格併一個、頭尾去空格。"""
    t = "".join(" " if (_sub_punct(x) or x.isspace()) else x for x in toks)
    t = re.sub(r"(?<!\d)[,;:]|[,;:](?!\d)", " ", t)   # 英數詞內的逗號(EA,Kotaku、Laidlaw,2017)也去掉;只留數字間的千分位
    return re.sub(r" {2,}", " ", t).strip()


def _dw(toks):
    return sum(_tw(t) for t in toks)


SUB_WORDS_FILE = SEG.SUB_WORDS_FILE   # 專案自訂詞表(一行一詞):字幕拆段不可切開的詞(讀取在 seg.py)
STICKY_HEAD = set("的了著過們嗎呢吧啦")           # 不可當段首的黏前字
PREF_AROUND = set("的了在是和與就也都把被")        # 切點偏好:這些虛詞前後
CN_NUM = set("零〇一二兩三四五六七八九十百千萬億")
SPLIT_MIN_W = 3                                   # 每段最短寬度,避免殘段
CROSS_LR = ((1, 1), (2, 1), (1, 2), (2, 2))       # 切點左右各取幾個字組成跨界字串(是詞典裡的詞就不可切)


def _sub_words():
    return SEG.sub_words()


def _simp(text):
    """jieba 內建詞典是簡體,繁體直接丟進去會斷錯(人事部/門):斷詞與查詞典前先逐字轉簡體;長度變了或 opencc 不可用就用原字。"""
    return SEG.simp(text)


def _jieba():
    """jieba 模組(跨界字串檢查查它的詞典詞頻;斷詞器選擇見 seg.py / --seg)。不可用回傳 False。"""
    return SEG.jieba_module() or False


def _wrap_toks(text):
    """直式動畫換行用 token(join = text):括號整段、英數詞(含詞間空白)整段、其餘用斷詞器(預設 jieba:繁轉簡斷、切回原字;--seg ckip 直接斷繁體),黏前字併入前詞。
    斷詞器不可用回傳 None(anim_lib 退回逐字)。"""
    sg = SEG.segmenter()
    if not sg:
        return None
    out = []
    for m in re.finditer(r"[（(][^（()）]*[)）]|[A-Za-z0-9][A-Za-z0-9 ,.:%+/\-']*[A-Za-z0-9%]|[A-Za-z0-9]|\s+"
                         r"|[^\s（(A-Za-z0-9]+|.", text):
        seg = m.group(0)
        if not re.match(r"[\s（(A-Za-z0-9]", seg):
            for w in sg.cut(seg):
                if out and w[0] in STICKY_HEAD and not out[-1].isspace():   # 黏前字(的、們…)不當行首
                    out[-1] += w
                else:
                    out.append(w)
        else:
            out.append(seg)
    return out


AL.WORD_TOKS = _wrap_toks


def _is_cjk(c):
    return "\u4e00" <= c <= "\u9fff"


def _cross_word(text, simp, off):
    """切在 text[off] 前:左右各取 1-2 個字的跨界字串若是詞典裡的詞(jieba 詞典詞頻 > 0,含自訂詞表),回傳該詞,否則 None。"""
    jb = _jieba()
    if not jb:
        return None
    freq = jb.dt.FREQ
    for l, r in CROSS_LR:
        if off - l < 0 or off + r > len(text):
            continue
        w = simp[off - l: off + r]
        if all(_is_cjk(c) for c in w) and freq.get(w, 0) > 0:
            return text[off - l: off + r]
    return None


def _cut_reasons(toks, cross=True, seg=None):
    """每個 token 位置 i(切在 toks[i-1] 與 toks[i] 之間)不可切的原因,可切為 None。斷詞器不可用時回傳 None。
    不可切:落在斷詞器(預設 jieba,--seg 可換 ckip;seg 參數可臨時指定,sub_scan 交叉判讀用)斷出的詞或自訂詞表的詞中間、括號/空白、段首黏前字、數字與量詞、中文數字串,
    以及(cross=True)跨界字串是詞典裡的詞(斷錯時的第二道檢查,查 jieba 詞典詞頻)。"""
    sg = SEG.segmenter(seg)
    if not sg:
        return None
    text = "".join(toks)
    simp = _simp(text)
    inside, pos = {}, 0     # 詞內的字元位置 -> 該詞
    for w in sg.cut(text):
        for q in range(pos + 1, pos + len(w)):
            inside[q] = text[pos: pos + len(w)]
        pos += len(w)
    for w in _sub_words():
        p = text.find(w)
        while p >= 0:
            for q in range(p + 1, p + len(w)):
                inside[q] = w
            p = text.find(w, p + 1)
    in_title = set()    # 含冒號的書名(寬度不超過 SUB_MAX_W 時)整個不可切開:切在 toks[i-1] 與 toks[i] 之間,a < i <= b
    for a, b in _title_colon_spans(toks):
        if _dw(toks[a + 1:b]) <= SUB_MAX_W:
            in_title.update(range(a + 1, b + 1))
    out, off = {}, 0
    for i, t in enumerate(toks):
        if i > 0:
            prev = toks[i - 1]
            why = None
            if i in in_title:
                why = "書名號內"
            elif off in inside:
                why = f"詞「{inside[off]}」"
            elif prev in OPENERS or t in CLOSERS or t.isspace():
                why = "括號或空白"
            elif t in STICKY_HEAD:
                why = f"段首黏前字「{t}」"
            elif prev[0].isdigit() or (prev.isspace() and i >= 2 and toks[i - 2][0].isdigit()):   # 數字 + 量詞(跨空白也算)
                why = "數字與量詞"
            elif prev in CN_NUM and t in CN_NUM:
                why = "中文數字串"
            elif cross:
                w = _cross_word(text, simp, off)
                why = f"詞「{w}」" if w else None
            out[i] = why
        off += len(t)
    return out


def _legal_cuts(toks, cross=True):
    """回傳可切的 token 位置集合(切在 toks[i-1] 與 toks[i] 之間)。None 表示斷詞器不可用。"""
    why = _cut_reasons(toks, cross)
    return None if why is None else {i for i, w in why.items() if w is None}


# ---- 片語切點評分(2026-10-29):合法切點(不切詞)之上的偏好;只在每片詞表模式(seg.phrase_mode())用於選切點,掃描(sub_phrase_seams)一律判讀
PH_HARD, PH_SOFT, PH_DE, PH_BONUS, PH_DESHI = 1000, 100, 60, 15, 20   # 不可切單位 / 功能詞後等 / 的字結構內 / 偏好切點 / 「X的是」後
PH_FUNC = {"因為", "所以", "就是", "早在", "而且", "沒有", "只是", "還是", "或是", "以及", "並且", "如果", "雖然", "為了", "對於", "關於",
           "由於", "除了", "連同", "甚至", "已經", "曾經", "正在", "一直", "比較", "非常", "這個", "那個", "這些", "那些", "每個"}
PH_FUNC1 = set("是跟在的地得把被讓從對向比給當到有沒也才還就只都又很更最不和與及或並而但卻再於由為以將替往朝自連這那每")
PH_PRE = {"因為", "所以", "就", "也", "才", "還", "跟", "而且", "結果", "最後", "但是", "但", "可是", "不過", "甚至", "卻", "然後",
          "於是", "直到", "只是", "還是", "而", "並", "再", "後來", "因此", "否則", "如果", "雖然", "連"}
PH_MEASURE = set("個間名位家款支部條隻張次場套份台輛本篇集季代種項筆件塊座層段頁句首片組批群些")
PH_DE_WIN = 5           # 切點右邊幾個中文字內出現「的」(中間沒有功能詞)= 切在「的」字結構的修飾語裡


def _is_en(t):
    return bool(re.match(r"[A-Za-z]", t or ""))


def _is_cjk_tok(t):
    return bool(t) and _is_cjk(t[0])


def _pos_words(text):
    """[(起, 訖, 詞, 詞性)](jieba.posseg,繁轉簡斷、切回原字);不可用回傳 None。"""
    if not _jieba():
        return None
    try:
        import jieba.posseg as PS
    except Exception:  # noqa: BLE001
        return None
    out, pos = [], 0
    for w, flag in PS.cut(_simp(text)):
        out.append((pos, pos + len(w), text[pos:pos + len(w)], flag))
        pos += len(w)
    return out


def _phrase_score(toks):
    """每個切點 i(切在 toks[i-1] 與 toks[i] 之間)-> (分數, 原因);分數越大越不該切(負數 = 偏好)。斷詞器不可用回傳 None。
    扣分:①功能詞後 ②數量詞組內 ③英文連續 token 中間 ④英文與緊接的中文名詞之間(PH_HARD)/中文名詞與英文之間 ⑤「的」字結構修飾語內;
    加分:切在連接詞/副詞前、「的+名詞」或「X的是」之後。兩段長度均衡由 _split_dp 的平方差負責(次要分)。"""
    text = "".join(toks)
    pw = _pos_words(text)
    if pw is None:
        return None
    at = {}             # 字元位置 -> 所屬 posseg 詞索引
    for k, (a, b, _, _) in enumerate(pw):
        for q in range(a, b):
            at[q] = k
    out, off = {}, 0
    for i, t in enumerate(toks):
        if i == 0:
            off += len(t)
            continue
        lo = off            # 左邊最後一個非空白字元之後
        while lo > 0 and text[lo - 1].isspace():
            lo -= 1
        ro = off
        while ro < len(text) and text[ro].isspace():
            ro += 1
        lk, rk = at.get(lo - 1), at.get(ro)
        lw = pw[lk] if lk is not None else None
        rw = pw[rk] if rk is not None else None
        ltok = next((x for x in reversed(toks[:i]) if not x.isspace()), "")
        ltok2 = next((x for x in reversed(toks[:i - 1]) if not x.isspace()), "") if i >= 2 else ""
        rtok = next((x for x in toks[i:] if not x.isspace()), "")
        lword = text[lw[0]:lo] if lw else ltok          # 左詞(只取切點左邊那部分)
        rword = text[ro:rw[1]] if rw else rtok
        lnoun = lw is not None and _is_cjk(text[lo - 1]) and (lw[3][:1] == "n" or lw[3] == "x")
        rnoun = rw is not None and ro < len(text) and _is_cjk(text[ro]) and (rw[3][:1] == "n" or rw[3] == "x")
        sc, why = 0, None
        if _is_en(rtok) and re.search(r"[A-Za-z0-9.]$", ltok) and _is_en(ltok) and t.isspace() is False and toks[i - 1].isspace():
            sc, why = PH_HARD, "英文名中間"
        elif _is_en(ltok) and rnoun:
            sc, why = PH_HARD, f"英文與名詞「{ltok}{rword}」"
        elif re.search(r"\d$", ltok) and _is_cjk_tok(rtok):
            sc, why = PH_HARD, "數字與單位"
        elif (ltok in PH_MEASURE and (ltok2[:1].isdigit() or ltok2 in CN_NUM)) or (ltok in CN_NUM and rtok in PH_MEASURE)                 or (lw is not None and lw[3][:1] == "m" and _is_cjk(text[lo - 1]) and lw[2][-1:] in PH_MEASURE and rnoun):
            sc, why = PH_HARD, "數量詞組"
        elif lword in PH_FUNC or (len(lword) == 1 and lword in PH_FUNC1):
            if lword[-1:] == "是" and text[max(lo - 2, 0):lo - 1] == "的":
                sc, why = -PH_DESHI, None                 # 「罵的是|隊友」:X的是 之後是自然停頓
            else:
                sc, why = PH_SOFT, f"功能詞後「{lw[2] if lw else lword}」"
        elif lnoun and _is_en(rtok):
            sc, why = PH_SOFT, f"名詞與英文「{lword} {rtok}」"
        elif lw is not None and lw[1] == lo and len(lw[2]) == 1 and lw[3][:1] == "v" and (rnoun or _is_en(rtok)):
            sc, why = PH_DE, f"單字動詞與受詞「{lw[2]}{rword}」"
        if sc >= 0 and why is None:
            seg_r = text[ro:ro + PH_DE_WIN + 1]
            m = re.match(r"([一-鿿]{1,%d})的" % PH_DE_WIN, seg_r)
            # 「的」前那段含動詞/形容詞/副詞 = 關係子句修飾語(立場完全|相反的朋友),切開扣分;全是名詞/代名詞 = 所有格(批評過|達絮的穿著),不扣
            pred = m and any(w[3][:1] in ("v", "a", "d") for w in pw if w[0] < ro + len(m.group(1)) and w[1] > ro)
            if pred and not any(c in PH_FUNC1 for c in m.group(1)) and not any(w in m.group(1) for w in PH_FUNC):
                sc, why = PH_DE, f"「的」字結構內「{m.group(0)}」"
            else:
                bonus = 0
                if rword in PH_PRE or (rw is not None and rw[2] in PH_PRE) or text[ro:ro + 2] in PH_PRE:
                    bonus = PH_BONUS
                if lnoun and lw[0] >= 1 and text[lw[0] - 1] == "的":
                    bonus = max(bonus, PH_BONUS)
                sc = -bonus
        out[i] = (sc, why)
        off += len(t)
    return out


def _phrase_cost(toks):
    """_split_dp 用的切點成本 i -> 分數(phrase_mode 才用);不可用回傳 None。"""
    ps = _phrase_score(toks)
    return None if ps is None else {i: v[0] for i, v in ps.items()}


def _split_dp(toks, legal, n, score=None):
    """在合法切點中選 n-1 個,使各段寬度與平均的平方差最小,每段在 [SPLIT_MIN_W, SUB_MAX_W]。無解回傳 None。
    score(i -> 分數,_phrase_cost)給了就加進主成本(片語扣分/偏好),原本的虛詞偏好不用;None = 舊行為。"""
    m = len(toks)
    pre = [0.0]
    for t in toks:
        pre.append(pre[-1] + _tw(t))
    avg = pre[m] / n

    def pref(i):  # 切點是否貼著虛詞(越小越好)
        return 0 if (toks[i - 1] in PREF_AROUND or toks[i] in PREF_AROUND) else 1

    pts = sorted(legal)
    INF = (float("inf"), 0)
    # best[k][i]: 前 k 段、第 k 段結束在切點 i(或 m)的最佳 (平方差, 偏好罰分)與前一切點
    best = {(0, 0): ((0.0, 0), None)}
    ends = pts + [m]
    for k in range(1, n + 1):
        for e in ends:
            if k < n and e == m:
                continue
            if k == n and e != m:
                continue
            cand = INF, None
            for (kk, s), (c, _) in list(best.items()):
                if kk != k - 1:
                    continue
                w = pre[e] - pre[s]
                if w > SUB_MAX_W or w < SPLIT_MIN_W:
                    continue
                if score is not None:
                    cost = (c[0] + (w - avg) ** 2 + (score.get(e, 0) if e < m else 0), 0)
                else:
                    cost = (c[0] + (w - avg) ** 2, c[1] + (pref(e) if e < m else 0))
                if cost < cand[0]:
                    cand = cost, s
            if cand[1] is not None:
                best[(k, e)] = cand
    if (n, m) not in best:
        return None
    cuts, e, k = [], m, n
    while k > 0:
        s = best[(k, e)][1]
        cuts.append(s)
        e, k = s, k - 1
    cuts = sorted(c for c in cuts if c > 0)
    bounds = [0] + cuts + [m]
    return [toks[a:b] for a, b in zip(bounds, bounds[1:])]


def _relax_rank(why):
    """放寬順序(F2-3b):0 = 本來就可切、1 = 數字與量詞/中文數字串、2 = 其他(詞中間、段首黏前字)、3 = 書名號內;
    括號或空白永遠不切(None)。"""
    if why is None:
        return 0
    if why == "括號或空白":
        return None
    if why in ("數字與量詞", "中文數字串"):
        return 1
    return 3 if why == "書名號內" else 2


def _split_long(toks):
    total = _dw(toks)
    n0 = math.ceil(total / SUB_MAX_W)
    score = _phrase_cost(toks) if SEG.phrase_mode() else None   # 每片詞表模式:片語評分選切點(沒有 words.txt 的片不變)

    def solve(legal):
        for n in range(n0, n0 + 3):
            parts = _split_dp(toks, legal, n, score)
            if parts:
                return parts
        return None

    for cross in (True, False):     # 加上跨界詞檢查無解時,退回只看 jieba 斷詞
        legal = _legal_cuts(toks, cross)
        parts = legal and solve(legal)
        if parts:
            return parts
    why = _cut_reasons(toks, False)  # 仍無解:依 _relax_rank 逐級放寬(數字與量詞 -> 其他 -> 書名號內);再無解才逐字切(sub_seams 會列出來)
    if why:
        for lv in (1, 2, 3):
            legal = {i for i, w in why.items() if (r := _relax_rank(w)) is not None and r <= lv}
            parts = legal and solve(legal)
            if parts:
                return parts
    return _split_long_greedy(toks)


def _split_long_greedy(toks):
    total = _dw(toks)
    n = math.ceil(total / SUB_MAX_W)
    target = total / n
    parts, cur, cw = [], [], 0.0
    for i, t in enumerate(toks):
        if cur:
            prev = toks[i - 1]
            ok = prev not in OPENERS and t not in CLOSERS and not t.isspace()
            if ok and len(parts) < n - 1 and (cw + _tw(t) > SUB_MAX_W or cw >= target):
                parts.append(cur)
                cur, cw = [], 0.0
        cur.append(t)
        cw += _tw(t)
    if cur:
        parts.append(cur)
    return parts


def _title_colon_spans(toks):
    """《…》(有成對、不巢狀)內含冒號(: 或 :)的書名,回傳 [(《的位置, 》的位置)](token 索引)。
    這種書名(《惡靈古堡:安魂曲》)的冒號不是斷句點、書名也不可從中間拆開(配音端同樣把冒號刪掉連著唸,見 tts_pron.drop_title_colon)。"""
    out, a = [], None
    for i, t in enumerate(toks):
        if t == "《":
            a = i
        elif t == "》" and a is not None:
            if any(x in (":", "：") for x in toks[a + 1:i]):
                out.append((a, i))
            a = None
    return out


def _sub_pieces(text):
    """依標點切出的各段 token(含段尾標點);「、」連接的短詞併成一段。書名號內的冒號不斷句。"""
    toks = TOKEN_RE.findall(text.replace("\n", " "))
    tcolon = {i for a, b in _title_colon_spans(toks) for i in range(a + 1, b) if toks[i] in (":", "：")}
    pieces, cur = [], []
    for i, t in enumerate(toks):
        cur.append(t)
        if _is_punct(t) and i not in tcolon:
            pieces.append(cur)
            cur = []
    if cur:
        pieces.append(cur)
    merged = []  # 「、」連接的短詞合併成一段(退款、取消預購),避免字幕閃爍
    for p in pieces:
        if merged and merged[-1][-1] == "、" and _dw(_strip(merged[-1] + p)) <= 14:
            merged[-1] = merged[-1] + p
        else:
            merged.append(p)
    return merged


def split_phrases(text):
    """回傳 [(顯示文字, 權重)]。依標點切段,數字/英文單字不拆,顯示去頭尾標點。"""
    out = []
    for p in _sub_pieces(text):
        pause = 0.5 if _is_punct(p[-1]) else 0.0
        core = _strip(p)
        if not core:
            continue
        parts = _split_long(core) if _dw(core) > SUB_MAX_W else [core]
        for k, part in enumerate(parts):
            part = _strip(part)
            txt = _clean_sub(part)
            if not txt:
                continue
            w = _dw(part) + (pause if k == len(parts) - 1 else 0.0)
            out.append((txt, max(w, 0.5)))
    return out


def sub_seams(text, judge=None):
    """字幕拆段的接縫檢查:回傳 [(左段, 右段, 原因)]。只看超過上限、在沒有標點處切開的接縫(_split_long);
    判準與 _cut_reasons 相同(詞被切開、段首黏前字、數字與量詞)。judge = 判讀用斷詞器(None = 與拆段同一個;sub_scan 比較用,另一個斷詞器當裁判)。"""
    out = []
    for p in _sub_pieces(text):
        core = _strip(p)
        if not core or _dw(core) <= SUB_MAX_W:
            continue
        why = _cut_reasons(core, seg=judge) or {}
        parts, i = _split_long(core), 0
        for a, b in zip(parts, parts[1:]):
            i += len(a)
            if why.get(i):
                out.append((_clean_sub(_strip(a)), _clean_sub(_strip(b)), why[i]))
    return out


def sub_phrase_seams(text):
    """字幕拆段的片語接縫(2026-10-29):只看超寬段在沒有標點處的接縫,詞沒切開(sub_seams 沒列)但落在 _phrase_score 扣分處
    (功能詞後、數量詞組、英文名中間、英文與名詞、「的」字結構內)。回傳 [(左段, 右段, 原因)];不算錯誤,另計一欄。"""
    out = []
    for p in _sub_pieces(text):
        core = _strip(p)
        if not core or _dw(core) <= SUB_MAX_W:
            continue
        why = _cut_reasons(core) or {}
        ps = _phrase_score(core) or {}
        parts, i = _split_long(core), 0
        for a, b in zip(parts, parts[1:]):
            i += len(a)
            if not why.get(i) and ps.get(i, (0, None))[1]:
                out.append((_clean_sub(_strip(a)), _clean_sub(_strip(b)), ps[i][1]))
    return out


def check_sub_seams(lines):
    """渲染前檢查:全片字幕拆段不可把詞切開。"""
    return [f"句{ln['idx']}: 字幕拆段切開了{why}:「{a}」|「{b}」(改寫句子或把詞加進 pipeline/sub_words.txt)"
            for ln in lines for a, b, why in sub_seams(ln["text"])]


def _ass_t(x):
    cs = max(0, round(x * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


_sub_font = None


def set_sub_profile(name):
    """切換字幕組(landscape / portrait):改寫 SUB_* 全域並重算 SUB_EM、SUB_PAD_X、清掉量寬字型快取。"""
    global SUB_EM, SUB_PAD_X, SUB_PROFILE, _sub_font
    globals().update(SUB_PROFILES[name])
    SUB_EM = SUB_FS / 1.448
    SUB_PAD_X = 0.45 * SUB_EM
    SUB_PROFILE = name
    _sub_font = None


def sub_text_width(text):
    """字幕文字在 libass 的前進寬度(px):以同字型、換算後的字級用 Pillow 量。"""
    global _sub_font
    if _sub_font is None:
        _sub_font = ImageFont.truetype(SUB_FONT, SUB_EM)
    return _sub_font.getlength(text)


def _spread(ph, s0, e0, end):
    """把字幕段依權重分配在 [s0, e0];最後一段延到 end(接上句後靜音)。回傳 [(文字, 起, 迄)]。"""
    tot = sum(w for _, w in ph) or 1.0
    out, acc = [], 0.0
    for k, (text, w) in enumerate(ph):
        s = s0 + (e0 - s0) * acc / tot
        acc += w
        out.append((text, s, end if k == len(ph) - 1 else s0 + (e0 - s0) * acc / tot))
    return out


SUB_LEAD = 0.04        # 字幕段比該段第一個字的實測發音時間提早這麼多秒出現
SUB_MIN_SEG = 0.25     # 實測時間算出的字幕段短於這個長度視為對齊失敗,該配音單位退回等比例
_SUB_STAT = dict(aligned=0, prop=0)   # 本次執行:單位內第 2 段起的字幕段,用實測時間 / 退回等比例的段數(write_ass 記錄用)


def _say_units(s):
    """送配音文字的音節數估計(字幕時間等比例分配的權重):中文字與數字每字 1,英文單字依母音群。"""
    return sum(max(1, len(re.findall(r"[aeiouy]+", t.lower()))) if t.isascii() and t.isalpha() else 1
               for t in re.findall(r"[A-Za-z]+|[0-9]|[\u4e00-\u9fff]", s))


def _phrase_spans(text, ph):
    """split_phrases 的各字幕段在 text 中的 (起, 迄) 字元位置:以非標點字元依序對位;對不上回傳 None。"""
    idx = [i for i, c in enumerate(text) if c.isalnum()]
    spans, n = [], 0
    for t, _ in ph:
        cs = [c for c in t if c.isalnum()]
        if not cs or cs != [text[i] for i in idx[n: n + len(cs)]]:
            return None
        spans.append((idx[n], idx[n + len(cs) - 1] + 1))
        n += len(cs)
    return spans if n == len(idx) else None


def _phrase_times(text, say, say_t, s0, e0, end, legacy=False):
    """一個配音單位(整行或一個子句)的字幕段起訖 [(文字, 起, 迄)]。[s0, e0] = 該單位語音在片中的起訖,最後一段延到 end。
    say = 實際送配音的文字(@say 替換後);say_t = 品管對齊出的「say 每個字元位置在音檔中的秒數」(tts_chattts.align_info)。
    有 say_t:各段起點 = 該段第一個字的實測發音時間 - SUB_LEAD(接在句中標點後的段 = 停頓結束時)。
    沒有或算出來不合理:等比例,權重用該段「送配音的字數」(@say 把 EA 換成四個字就照四個字算),不是顯示字數。
    legacy=True:舊算法(顯示字寬等比例),只供 write_ass 比較差距。"""
    ph = split_phrases(text)
    spans = None if legacy or len(ph) < 2 else _phrase_spans(text, ph)
    if not spans:
        return _spread(ph, s0, e0, end)
    pos = TPA.char_map(text, say)
    if say_t and len(say_t) == len(say) + 1:
        st = [s0] + [s0 + say_t[pos[a]] - SUB_LEAD for a, _ in spans[1:]]
        if all(b - a >= SUB_MIN_SEG for a, b in zip(st, st[1:] + [e0])):
            _SUB_STAT["aligned"] += len(ph) - 1
            return [(t, st[k], st[k + 1] if k + 1 < len(st) else end) for k, (t, _) in enumerate(ph)]
    _SUB_STAT["prop"] += len(ph) - 1
    wts = [(t, max(0.5, _say_units(say[pos[a]: pos[b]]) + (0.5 if text[b:].lstrip()[:1] in SUB_PUNCT else 0.0)))
           for (t, _), (a, b) in zip(ph, spans)]
    return _spread(wts, s0, e0, end)


def _line_units(ln):
    """一行的配音單位 [(送配音文字, 語音起, 語音迄, say_t)](成片秒,時間軸上的實際起訖);沒拆子句的行是一個單位。"""
    v0, cl = ln["vstart"], ln.get("clauses")
    if not cl:
        return [((ln.get("say") or ln["text"]).strip(), v0, v0 + ln["dur"], (ln.get("qc") or {}).get("say_t"))]
    return [(c["text"], v0 + c["start"], v0 + c["end"], c.get("say_t")) for c in cl]


def _unit_refs(text, units, ph):
    """各字幕段起點的參考時間 [(秒, 種類)];字幕段對不回 text 時回傳 None。每段依它第一個字在送配音文字中的位置歸到所屬配音單位:
    位於單位開頭 -> 該單位語音起點(unit);單位內有品管對齊時間 -> 該字實測發音時間 - SUB_LEAD(align);
    沒有對齊時間 -> 只在該單位範圍內依音節等比例(prop)。"""
    spans = _phrase_spans(text, ph)
    if not spans:
        return None
    pos = TPA.char_map(text, "".join(u[0] for u in units))
    offs = [0]
    for u in units:
        offs.append(offs[-1] + len(u[0]))
    out = []
    for a, _ in spans:
        k = max(i for i in range(len(units)) if offs[i] <= pos[a])
        say, s0, e0, say_t = units[k]
        r = pos[a] - offs[k]
        if _say_units(say[:r]) == 0:
            out.append((s0, "unit"))
        elif say_t and len(say_t) == len(say) + 1:
            out.append((s0 + say_t[r] - SUB_LEAD, "align"))
        else:
            out.append((s0 + (e0 - s0) * _say_units(say[:r]) / max(1, _say_units(say)), "prop"))
    return out


def hl_word_time(ln, kws):
    """這行 kws 中最早被唸到的詞的片中秒數(hl 底線卡詞用);詞不在旁白、所屬配音單位沒有品管對齊時間一律回傳 None(不用等比例)。
    kw 在 ln["text"] 的找法同 find_hl_boxes(忽略空白與大小寫),換算到配音單位的方式同 _unit_refs;任何例外都回傳 None,不讓渲染中止。"""
    try:
        text, units = ln["text"], _line_units(ln)
        seq = [(i, c.lower()) for i, c in enumerate(text) if not c.isspace()]
        flat = "".join(c for _, c in seq)
        pos = TPA.char_map(text, "".join(u[0] for u in units))
        offs = [0]
        for u in units:
            offs.append(offs[-1] + len(u[0]))
        out = []
        for kw in kws:
            k = re.sub(r"\s+", "", kw).lower()
            i = flat.find(k) if k else -1
            if i < 0:
                continue
            a = pos[seq[i][0]]
            u = max(j for j in range(len(units)) if offs[j] <= a)
            say, s0, _, say_t = units[u]
            if say_t and len(say_t) == len(say) + 1:
                out.append(s0 + say_t[a - offs[u]])
        return min(out) if out else None
    except Exception:
        return None


def line_phrase_times(ln, legacy=False):
    """一行的字幕段與起訖秒。拆成子句的行(ln["clauses"])逐子句處理;每個配音單位內的分段時間見 _phrase_times
    (品管對齊的實測時間優先)。硬性保證:每個配音單位的第一個字幕段從該單位語音起點開始(時間軸上的實際起訖),
    單位內對齊失敗只在該單位範圍內等比例。字幕文字的子句數與配音單位數對不上(@say 改了句界)時,各段依第一個字歸到所屬單位
    (_unit_refs),不再整行等比例。"""
    units = _line_units(ln)
    v1 = ln["vstart"] + ln["dur"]
    tparts = TS.split_clauses(ln["text"])
    if len(units) == 1 or (legacy and len(tparts) != len(units)):
        say = (ln.get("say") or ln["text"]).strip()
        return _phrase_times(ln["text"], say, units[0][3] if len(units) == 1 else None, ln["vstart"], v1, v1, legacy)
    if len(tparts) == len(units):
        out = []
        for k, ((say, s0, e0, say_t), (tt, _)) in enumerate(zip(units, tparts)):
            out += _phrase_times(tt, say, say_t, s0, e0, units[k + 1][1] if k + 1 < len(units) else v1, legacy)
        return out
    ph = split_phrases(ln["text"])
    refs = _unit_refs(ln["text"], units, ph)
    if not refs:
        return _spread(ph, ln["vstart"], v1, v1)
    st = []
    for t, _ in refs:
        st.append(max(t, st[-1] + 0.01) if st else t)
    return [(t, st[k], st[k + 1] if k + 1 < len(st) else v1) for k, (t, _) in enumerate(ph)]


SUB_SYNC_TOL = 0.15    # 字幕段起點與語音參考時間相差超過這麼多秒就列出


def sub_sync(lines, timed_fn=None):
    """全片每個字幕段的起點與語音的時間差 [dict(idx, text, start, ref, diff)](diff 正 = 字幕晚出現);參考時間見 _unit_refs。
    需要 tts_all + build_timeline 之後的 lines(有 clauses / qc)。"""
    rows = []
    for ln in lines:
        timed = (timed_fn or line_phrase_times)(ln)
        refs = _unit_refs(ln["text"], _line_units(ln), [(t, 0) for t, _, _ in timed])
        for (text, st, _), (ref, kind) in zip(timed, refs or []):
            rows.append(dict(idx=ln["idx"], text=text, start=st, ref=kind, diff=st - ref))
    return rows


AUDIO_FRAME_TOL = 1.5  # 成片音軌相鄰封包的時間差超過這麼多個封包長度視為缺口


def audio_gaps(path):
    """成片音軌的時間戳缺口 [(缺口前秒, 缺口後秒)]。有缺口 = 混音中途掉了聲音(播放器會把之後的聲音提早播,字幕與畫面對不上)。"""
    out = run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "packet=pts_time,duration_time",
               "-of", "csv=p=0", path]).decode()
    pk = [tuple(float(x) for x in r.split(",")[:2]) for r in out.split() if r and "N/A" not in r]
    return [(a, b) for (a, d), (b, _) in zip(pk, pk[1:]) if b - a > AUDIO_FRAME_TOL * d]


# 影片片段鏡頭右上角的出處小字(script 每句 note;2_文案 弱狀態句畫面必須有小字)。與字幕同一份 subs.ass(最後合成階段燒入),
# 不進鏡頭快取;截圖/閱讀卡/anim/quote/compare 本身有出處,不畫;直式略過。
NOTE_STYLE = "Note"
NOTE_PX = 32                              # 字高(全形字寬,px)
NOTE_FS = round(NOTE_PX * 1.448)          # libass Fontsize(行高 = 1.448 em)
NOTE_MARGIN_R, NOTE_MARGIN_V = 48, 40     # 離右緣 / 上緣(不碰頂端、不進字幕帶)
NOTE_ALPHA = "1A"                         # 字色透明度(約 10% 透明)
NOTE_MAX_PX = 900                         # 單行寬上限,超過在空白(沒有就字數中點)處斷成兩行
_note_font = None


def note_text_width(text):
    global _note_font
    if _note_font is None:
        _note_font = ImageFont.truetype(SUB_FONT, NOTE_PX)
    return _note_font.getlength(text)


def note_wrap(text):
    """note 超過 NOTE_MAX_PX 時斷成兩行(\\N);優先在最接近中點的空白斷,沒空白就字數中點。"""
    text = " ".join(str(text).split())
    if note_text_width(text) <= NOTE_MAX_PX:
        return text
    cuts = [i for i, c in enumerate(text) if c == " "] or [len(text) // 2]
    i = min(cuts, key=lambda k: abs(k - len(text) / 2))
    return f"{text[:i].rstrip()}\\N{text[i:].lstrip()}"


def note_events(lines, shots):
    """每句 note 要畫的時段:該句畫面區間 [f0, f1) 與「影片片段鏡頭」(kind=video 且非 special)重疊的部分,相鄰併成一段。
    回傳 [(起秒, 迄秒, note)]。"""
    vids = [(s["f0"], s["f0"] + s["frames"]) for s in shots if s.get("kind") == "video" and not s.get("special")]
    out = []
    for ln in lines:
        note = " ".join(str(ln.get("note") or "").split())
        if not note or "f0" not in ln:
            continue
        segs = []
        for a, b in vids:
            a, b = max(a, ln["f0"]), min(b, ln["f1"])
            if b > a:
                if segs and a <= segs[-1][1]:
                    segs[-1][1] = max(segs[-1][1], b)
                else:
                    segs.append([a, b])
        out += [(a / FPS, b / FPS, note) for a, b in segs]
    return out


def write_ass(lines, path, shots=None):
    head = (
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {SUB_PLAY[0]}\nPlayResY: {SUB_PLAY[1]}\nWrapStyle: 2\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{SUB_FONT_NAME},{SUB_FS},&H00FFFFFF,&H00FFFFFF,&H00000000,&H{SUB_SHADOW_ALPHA}000000,0,0,0,0,"
        f"100,100,0,0,1,{SUB_OUTLINE},{SUB_SHADOW},5,0,0,0,1\n"
        f"Style: {NOTE_STYLE},{SUB_FONT_NAME},{NOTE_FS},&H{NOTE_ALPHA}FFFFFF,&H{NOTE_ALPHA}FFFFFF,&H00000000,&H60000000,0,0,0,0,"
        f"100,100,0,0,1,1.5,0,9,0,{NOTE_MARGIN_R},{NOTE_MARGIN_V},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, Effect, Text\n"
    )
    ev = []
    max_w = 0.0
    shift = 0.0
    _SUB_STAT.update(aligned=0, prop=0)
    for ln in lines:
        timed = line_phrase_times(ln)
        old = line_phrase_times(ln, legacy=True)
        if len(old) == len(timed):
            shift = max([shift] + [abs(a[1] - b[1]) for a, b in zip(timed, old)])
        ln["phrases"] = [x[0] for x in timed]
        for text, s, e in timed:
            if e - s < 0.15:
                e = s + 0.15
            safe = text.replace("{", "(").replace("}", ")")
            bw = sub_text_width(text) + 2 * SUB_PAD_X
            max_w = max(max_w, bw)
            # 無底框(2026-10-09 起):白字 + 黑描邊 + 右下陰影;bw 只用來檢查寬度
            ev.append(f"Dialogue: 1,{_ass_t(s)},{_ass_t(e)},Default,,,{{\\an5\\pos({SUB_CX},{SUB_CY + SUB_INK_DY:.1f})}}{safe}\n")
    notes = note_events(lines, shots) if shots and SUB_PROFILE == "landscape" else []
    for s, e, text in notes:
        safe = note_wrap(text).replace("{", "(").replace("}", ")")
        ev.append(f"Dialogue: 0,{_ass_t(s)},{_ass_t(e)},{NOTE_STYLE},,,{safe}\n")
    if notes:
        log(f"出處小字: 影片片段鏡頭 {len(notes)} 段(右上角)")
    if max_w > SUB_MAX_PX:
        log(f"警告: 字幕最寬 {max_w:.0f}px 超過畫面寬 {SUB_MAX_FRAC:.0%}({SUB_MAX_FRAC * W:.0f}px),請下修 SUB_MAX_W"
            if SUB_PROFILE == "landscape" else f"錯誤: 直式字幕最寬 {max_w:.0f}px 超過安全框 {SUB_MAX_PX:.0f}px")
    log(f"字幕時間: 配音單位內第 2 段起的字幕段,用品管對齊的實測時間 {_SUB_STAT['aligned']} 段、退回等比例 {_SUB_STAT['prop']} 段;"
        f"段起點與舊算法(顯示字數等比例)最大相差 {shift:.2f}s")
    sync = sub_sync(lines)
    off = [r for r in sync if abs(r["diff"]) > SUB_SYNC_TOL]
    log(f"字幕同步: {len(sync)} 段,起點與語音(單位起點/對齊時間)相差 > {SUB_SYNC_TOL:.2f}s 的 {len(off)} 段"
        + "".join(f"; 句{r['idx']} {r['diff']:+.2f}s" for r in off[:8]))
    log(f"字幕: {SUB_FONT_NAME} 字級 {SUB_FS}  中心 y={SUB_CY}  最寬 {max_w:.0f}px ({max_w / W:.1%})")
    path.write_text(head + "".join(ev), encoding="utf-8")


# ---------------------------------------------------------------- 鏡頭
BG_DIM = 0.38          # 圖片鏡頭的模糊底圖亮度
IMG_BOTTOM_KEEP = 240  # 圖片鏡頭底部保留給字幕的高度(輸出像素);只有「重點區」不能進這一帶,圖片其餘部分可延伸到字幕後面
CARD_DIM = 0.60        # 卡片底圖亮度
CARD_FADE = 0.15       # 卡片淡入淡出秒數

# 圖片版面:不縮圖避字幕,而是平移讓重點區落在字幕帶以上
IMG_FILL_TILT = 0.92      # tilt 時圖寬占畫面寬的下限(兩側以模糊底圖補)
IMG_FILL_TILT_MAX = 0.96  # tilt 圖高不足畫面高時,為了填高最多放大到這個寬度比例
IMG_FILL_FLAT = 1.0       # zoom/none 時圖寬占畫面寬
SAFE_Y_FLAT = (16, H - IMG_BOTTOM_KEEP - 10)  # zoom/none 的重點區可用垂直範圍(畫布座標;zoom 末段放大 3% 已含在內)
SAFE_Y_TILT = (48, 810)   # tilt 近側會被透視放大,上下各多留一點
FOCUS_MARGIN_X = 0.04     # 重點區左右各留的邊距(畫面寬比例)
FOCUS_DEFAULT = (0.0, 0.0, 1.0, 0.6)  # 沒有 hl 也沒有 focus 時的重點區(圖片相對座標)
TEXT_MIN_PX = 34          # 重點區文字行高(換算到畫面)低於此值就放大
TEXT_TARGET_PX = 40       # 放大的目標行高
TEXT_UP_MAX = 3.0         # 相對下限倍率,最多放大幾倍
LABEL_SCALE = 1.2         # 「中文翻譯 · 原文」標籤重貼時的放大倍率
LABEL_MARGIN = 18
CONTENT_MARGIN_X = 0.03   # 有 .boxes.json 的圖:文字內容寬左右各留的邊距(畫面寬比例);水平不可裁到任何文字
ZOOM_END = 1.03           # zoom 鏡頭結束時的放大倍率上限(實際倍率與錨點由 _zoom_fit 依文字範圍決定,存在 layout["zoom"])
TEXT_EDGE_TOP = 24        # 完整在畫面內的文字框離成片上緣的最小距離(fx 動態全程);放不下就整行推出畫面,不可切半行
TEXT_EDGE_X = 40          # 文字框離成片左右邊的最小距離(fx 動態全程)
FX_U = (0.0, 0.5, 1.0)    # 驗文字框位置時取樣的動態進度(起點、中點、終點)
PUSH_Z = 1.02             # 鏡頭間輕推移(2026-10-22 六項 D):靜態→靜態交界,新鏡頭前 PUSH_S 秒以畫面中心 1.00 → PUSH_Z(ease-out),之後維持
PUSH_S = 0.2
PUSH_MIN = 1.004          # 為保文字離邊而減小後低於此倍率(< 約 4px)就不推
TILT_INSET = 0.02         # tilt:目的四角左右各內縮的畫面寬比例
TILT_NEAR = 0.04          # tilt:近側上下各外擴的畫面高比例(乘 TILT_AMP)
TILT_FAR = 0.06           # tilt:遠側上下各內縮的畫面高比例(乘 TILT_AMP)
TILT_AMP = (0.9, 0.2)     # tilt:幅度 = 起點 + 增量 * 進度
TILT_DRIFT = 0.012        # tilt:整個鏡頭期間左右漂移的畫面寬比例
ZOOM_PAD_MAX = 96         # text 組補邊寬度上限(1x px)
EDGE_STD_WARN = 12        # text 組補邊:圖左右邊色逐列標準差超過此值(不是純底色的圖)就警告
TILT_EDGE = 2             # tilt 前景畫布最外圈留透明的像素(prep_image)
LAYOUT_VER = "layout9-botpad"  # 版面/底線演算法版本;改動時換字串,render_shot 的快取簽章會跟著失效


def _cover(im, w, h):
    sc = max(w / im.width, h / im.height)
    r = im.resize((max(w, round(im.width * sc)), max(h, round(im.height * sc))), Image.BICUBIC)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def _cover_at(im, w, h, ax=0.5, ay=0.0):
    """cover 裁切,可指定裁切位置(ax/ay: 0=靠左/上, 1=靠右/下)。"""
    sc = max(w / im.width, h / im.height)
    r = im.resize((max(w, round(im.width * sc)), max(h, round(im.height * sc))), Image.LANCZOS)
    x, y = round((r.width - w) * ax), round((r.height - h) * ay)
    return r.crop((x, y, x + w, y + h))


def _blit(canvas, sprite, x, y):
    """把 RGBA 小圖 alpha 合成到 canvas(可超出邊界,自動裁掉)。"""
    x, y = int(round(x)), int(round(y))
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.width, x + sprite.width), min(canvas.height, y + sprite.height)
    if x1 <= x0 or y1 <= y0:
        return
    canvas.alpha_composite(sprite.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def split_label(im, fs=22):
    """圖右下角烤進去的「中文翻譯 · 原文:…」標籤(assets_lib.add_label:黑底圓角、白字)。
    fs = add_label 的字級(橫式圖 22;窄版截圖 P_LABEL_FS = news_lib.NARROW_LABEL_FS,標籤較大)。
    偵測到就回傳 (抹掉標籤的圖, 標籤 RGBA 小圖);沒有則 (原圖, None)。標籤由 build 另行貼在安全區右下角。"""
    w, h = im.size
    if w < 600 or h < 200:
        return im, None
    px = im.load()
    y, x = h - 26 - fs, w - 20
    if max(px[x, y]) > 10:
        return im, None
    while x > max(1, w - 900 * fs / 22) and max(px[x - 1, y]) <= 10:
        x -= 1
    xl = x - 3
    box = (xl, h - 28 - fs, w - 15, h - 13)
    if not 100 <= box[2] - box[0] <= 760 * fs / 22:
        return im, None
    patch = im.crop(box).convert("RGBA")
    if sum(1 for p in patch.getdata() if min(p[:3]) > 200) < 20:  # 沒有白字,不是標籤
        return im, None
    ss = 4
    m = Image.new("L", (patch.width * ss, patch.height * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, (patch.width - 2) * ss, (patch.height - 1) * ss), 8 * ss, fill=255)
    patch.putalpha(m.resize(patch.size, Image.LANCZOS))
    clean = im.copy()
    cd = ImageDraw.Draw(clean)
    for yy in range(box[1] - 1, box[3] + 1):  # 用標籤左側的頁面顏色逐列補平
        cd.line((box[0] - 1, yy, w, yy), fill=px[max(0, xl - 6), yy])
    return clean, patch


def _paste_label(canvas, label, right, bottom, scale):
    lab = label.resize((round(label.width * scale), round(label.height * scale)), Image.LANCZOS)
    _blit(canvas, lab, right - lab.width, bottom - lab.height)


# ---------------------------------------------------------------- 重點標記(紅色底線)
HL_DELAY = 0.30       # 重點標記在句子起點後開始畫的延遲秒數(卡詞對不到時的時序,也是起點的下限)
HL_WORD_LEAD = 0.10   # 底線比該詞實測發音提早開始的秒數
HL_MIN_SHOW = 1.0     # 底線至少留這麼多秒才被下一段換掉或鏡頭結束
HL_MAX = 4            # 同一關鍵字最多標幾處
HL_UL_GAP = 0.12      # 底線上緣離文字框下緣(倍行高)
HL_UL_W = 0.14        # 底線粗細(倍行高)
HL_UL_MINW = 6        # 底線最細(輸出像素)
HL_UL_EXT = 0.6       # 底線比文字左右各多延伸(倍行高)
HL_UL_MINLEN = 4.0    # 底線最短(倍行高)
HL_UL_EDGE = 2        # 深色外緣(輸出像素)
HL_UL_DUR = 0.35      # 每條底線由左至右畫出的秒數(ease-out)
HL_UL_TOTAL = 1.4     # 同一組標記全部畫完的秒數上限(條數多時縮短每條)
HL_UL_FADE_OUT = 0.15
HL_UL_COLOR = (255, 0, 0, 255)
HL_UL_EDGE_COLOR = (24, 24, 28, 255)
_box_cache = {}


def _load_boxes(media, img):
    if img not in _box_cache:
        f = media / "images" / f"{img}.boxes.json"
        _box_cache[img] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    return _box_cache[img]


def find_hl_boxes(entries, kw):
    """在 sidecar 文字區塊中找關鍵字(忽略空白與大小寫,可跨行),回傳原圖像素框清單。"""
    seq = [(ei, ci, ch.lower()) for ei, e in enumerate(entries) for ci, ch in enumerate(e["text"]) if not ch.isspace()]
    flat = "".join(c for _, _, c in seq)
    k = re.sub(r"\s+", "", kw).lower()
    out, pos = [], 0
    while k and len(out) < HL_MAX:
        i = flat.find(k, pos)
        if i < 0:
            break
        pos = i + len(k)
        per = {}
        for ei, ci, _ in seq[i:i + len(k)]:
            per.setdefault(ei, []).append(ci)
        for ei, cis in per.items():
            e = entries[ei]
            x0, y0, x1, y1 = e["box"]
            if e.get("chars"):
                x0, x1 = min(e["chars"][c][0] for c in cis), max(e["chars"][c][1] for c in cis)
            out.append((x0, y0, x1, y1))
    return out


def _ul_span(box, entries, imw):
    """底線的橫向範圍(原圖像素):文字左右各延伸 HL_UL_EXT 倍行高,最短 HL_UL_MINLEN 倍行高;
    同一行上與命中文字不重疊的鄰近文字區塊(例如旁邊的欄位)是邊界,不得越過;也不出圖。"""
    x0, y0, x1, y1 = box
    lh = y1 - y0
    lo, hi = 2.0, imw - 2.0
    for e in entries or []:
        ex0, ey0, ex1, ey1 = e["box"]
        if min(y1, ey1) - max(y0, ey0) < 0.5 * lh or (ex0 < x1 and ex1 > x0):
            continue
        if ex1 <= x0:
            lo = max(lo, ex1 + 2)
        else:
            hi = min(hi, ex0 - 2)
    ux0, ux1 = max(lo, x0 - HL_UL_EXT * lh), min(hi, x1 + HL_UL_EXT * lh)
    short = HL_UL_MINLEN * lh - (ux1 - ux0)
    if short > 0:  # 太短:兩側各補一半,一側撞到邊界就由另一側補
        gl = min(short / 2, max(0.0, ux0 - lo))
        gr = min(short - gl, max(0.0, hi - ux1))
        gl = min(short - gr, max(0.0, ux0 - lo))
        ux0, ux1 = ux0 - gl, ux1 + gr
    return ux0, ux1


_ink_cache = {}


def _ink_bottom(media, img, box):
    """命中框內文字墨跡的下緣(原圖 y);框內找不到與底色差異明顯的像素就回傳 None。
    行高設得很大的標題,文字框下緣離字很遠,底線要跟著字走,不是跟著框走。"""
    if img not in _ink_cache:
        _ink_cache[img] = np.asarray(Image.open(media / "images" / f"{img}.png").convert("L"), dtype=np.int16)
    g = _ink_cache[img]
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    reg = g[max(0, y0):y1, max(0, x0):x1]
    if reg.size == 0:
        return None
    rows = (np.abs(reg - int(np.median(reg))) > 48).sum(axis=1) >= 2
    if not rows.any():
        return None
    return max(0, y0) + int(np.nonzero(rows)[0][-1]) + 1


def _hl_hits(s, media, imw):
    """s["hls"] 各段的命中框(原圖像素,含底線範圍);回傳 (與 hls 同序的清單, 找不到的 [(句, 關鍵字)])。"""
    entries = _load_boxes(media, s["img"])
    hits, missing = [], []
    for h in s.get("hls") or []:
        one = []
        for kw in h["kws"]:
            found = find_hl_boxes(entries, kw) if entries else []
            if not found:
                missing.append((h["line"], kw, bool(entries)))
            for b in found:
                ux0, ux1 = _ul_span(b, entries, imw)
                gap = HL_UL_GAP * (b[3] - b[1])
                ink = _ink_bottom(media, s["img"], b)
                uy = b[3] + gap if ink is None else min(b[3], ink) + gap  # 底線上緣(原圖 y)
                one.append(dict(box=tuple(b), ux0=ux0, ux1=ux1, uy=uy))
        hits.append(one)
    return hits, missing


def _tilt_quad(fx, u):
    """_tilt_filter 在進度 u(0 = 第一格,1 = 最後一格)的目的四角:左上、右上、左下、右下(成片像素)。"""
    d = 1 if fx == "tilt_l" else -1
    amp = TILT_AMP[0] + TILT_AMP[1] * u
    near, far = TILT_NEAR * amp, TILT_FAR * amp
    xl, xr = W * TILT_INSET + W * TILT_DRIFT * (u - 0.5) * d, W * (1 - TILT_INSET) + W * TILT_DRIFT * (u - 0.5) * d
    lt, lb = (-H * near, H * (1 + near)) if d == 1 else (H * far, H * (1 - far))
    rt, rb = (H * far, H * (1 - far)) if d == 1 else (-H * near, H * (1 + near))
    return (xl, lt), (xr, rt), (xl, lb), (xr, rb)


def _zoomish(fx):
    """zoom 類 fx(zoom、text 組的 drift_l / drift_r):用 2x 畫布 + _zoom_filter。"""
    return fx == "zoom" or fx.startswith("drift")


def _zoom_params(fx):
    """(終點倍率上限, 水平漂移 px:鏡頭期間由 -dx 移到 +dx)。非 zoom 類回傳 (1.0, 0)。"""
    if fx == "zoom":
        return ZOOM_END, 0
    if fx == "drift_r":
        return ZOOM_END_TEXT, DRIFT_PX
    if fx == "drift_l":
        return ZOOM_END_TEXT, -DRIFT_PX
    return 1.0, 0


def fx_map(fx, u, zoom=None):
    """fx 動態在進度 u 時「畫布座標 -> 成片座標」的函式;與 shot_cmd 的 _zoom_filter、_tilt_filter 同一組參數。
    zoom = (終點倍率, 錨點 ax, ay),錨點是放大時不動的那一點(畫面比例);drift 類另加水平漂移 dx * (2u - 1)。"""
    if _zoomish(fx):
        zmax, dx = _zoom_params(fx)
        ze, ax, ay = zoom or (zmax, 0.5, 0.5)
        z = 1 + (ze - 1) * u
        sx = dx * (2 * u - 1)
        return lambda x, y: (x * z - (z - 1) * W * ax + sx, y * z - (z - 1) * H * ay)
    if fx in ("tilt_l", "tilt_r"):
        rows, rhs = [], []
        for (x, y), (X, Y) in zip(((0, 0), (W, 0), (0, H), (W, H)), _tilt_quad(fx, u)):
            rows += [[x, y, 1, 0, 0, 0, -X * x, -X * y], [0, 0, 0, x, y, 1, -Y * x, -Y * y]]
            rhs += [X, Y]
        h = np.linalg.solve(np.array(rows, dtype=float), np.array(rhs, dtype=float))

        def persp(x, y):
            w = h[6] * x + h[7] * y + 1
            return float((h[0] * x + h[1] * y + h[2]) / w), float((h[3] * x + h[4] * y + h[5]) / w)
        return persp
    return lambda x, y: (x, y)


def _zoom_pad(s):
    """zoom 類(含 drift)鏡頭動態全程,成片左右邊會取樣到畫布外多少 px(1x,含 4px 餘裕);0 = 不會露出畫布外。
    prep_image 把畫布左右各補這麼寬(圖的邊色延伸),_zoom_filter 用同一個值定位。"""
    if not _zoomish(s["fx"]):
        return 0
    zmax, dx = _zoom_params(s["fx"])
    ze, ax, _ = (s.get("layout") or {}).get("zoom") or (zmax, 0.5, 0.5)
    over = 0.0
    for u in FX_U:
        z = 1 + (ze - 1) * u
        sx = dx * (2 * u - 1)
        over = max(over, -(-sx + (z - 1) * W * ax) / z, (W - sx + (z - 1) * W * ax) / z - W)
    return math.ceil(over) + 4 if over > 0 else 0


def _extend_sides(comp, dx0, dx1, dy0, dy1, pad):
    """text 組畫布左右補邊(A 法):圖(畫布內 dx0-dx1 x dy0-dy1)沒蓋到的左右兩側,用圖最外 4 欄每列的中位數色逐列延伸到畫布邊;
    再把整張畫布左右各複製邊欄 pad px(漂移/放大時成片邊緣會取樣到畫布外)。回傳 (新畫布 RGB, 邊色逐列標準差最大值)。"""
    a = np.asarray(comp.convert("RGB")).copy()
    sd = 0.0
    if dx0 > 0:
        col = np.median(a[dy0:dy1, dx0:dx0 + 4], axis=1)
        a[dy0:dy1, :dx0] = col[:, None, :]
        sd = max(sd, float(col.std(axis=0).max()))
    if dx1 < a.shape[1]:
        col = np.median(a[dy0:dy1, dx1 - 4:dx1], axis=1)
        a[dy0:dy1, dx1:] = col[:, None, :]
        sd = max(sd, float(col.std(axis=0).max()))
    if pad:
        a = np.pad(a, ((0, 0), (pad, pad), (0, 0)), mode="edge")
    return Image.fromarray(a), sd


def _extend_vert(comp, dy0, dy1):
    """text 組畫布上下補邊(2026-10-22):圖(畫布內 dy0-dy1 列)沒蓋到畫布底/頂時(字幕帶下方露出模糊底圖的黑帶),
    用圖最下/最上 4 列每欄的中位數色延伸到畫布邊(須在 _extend_sides 之後:左右已補滿,整列寬度都有圖色)。
    邊色欄間標準差 > EDGE_STD_WARN(不是純底色)的那一側不延伸。回傳 (新畫布 RGB, 被略過的 [(側, 標準差)])。"""
    a = np.asarray(comp.convert("RGB")).copy()
    skipped = []
    for side, cond, rows in (("下", dy1 < a.shape[0], slice(dy1 - 4, dy1)), ("上", dy0 > 0, slice(dy0, dy0 + 4))):
        if not cond:
            continue
        row = np.median(a[rows], axis=0)
        sd = float(row.std(axis=0).max())
        if sd > EDGE_STD_WARN:
            skipped.append((side, sd))
        elif side == "下":
            a[dy1:] = row[None]
        else:
            a[:dy0] = row[None]
    return Image.fromarray(a), skipped


def _fx_maps(fx, zoom=None):
    return [fx_map(fx, u, zoom) for u in FX_U]


def _zoom_fit(c0, c1, zmax=ZOOM_END, drift=0):
    """zoom 鏡頭的 (終點倍率, 錨點 ax, ay):錨點放在文字內容寬(畫布 x 範圍 c0-c1)的中心,
    倍率上限 zmax(drift 類另扣水平漂移 drift px),放大後內容左右仍離邊 TEXT_EDGE_X;放不下就降低倍率,最低到不放大(1.0)。"""
    anc = min(float(W), max(0.0, (c0 + c1) / 2))
    z = zmax
    m = TEXT_EDGE_X + abs(drift)
    if c0 < anc:
        z = min(z, (anc - m) / (anc - c0))
    if c1 > anc:
        z = min(z, (W - m - anc) / (c1 - anc))
    return max(1.0, math.floor(z * 1e4) / 1e4), round(anc / W, 4), 0.5


def _side_margin(c0, c1, maps):
    """畫布 x 範圍 c0-c1 在 fx 動態全程離成片左右邊的最小距離。"""
    return min(min(m(c0, H / 2)[0], W - m(c1, H / 2)[0]) for m in maps)


def _top_limits(x0, x1, maps, edge):
    """文字框(畫布 x 範圍 x0-x1)對畫面上緣的兩個門檻(畫布 y):框頂 >= vis 時整行在畫面內且留足 TEXT_EDGE_TOP;
    框底 <= out 時整行在畫面外。成片 y 對畫布 y 是一次式(zoom 與左右傾斜的透視都是),取兩點反推。
    edge = 畫布上緣不顯示的像素(tilt 的透明外圈):畫布本身也會裁字,所以 vis 不小於它、框底在它以上就算出畫面。"""
    vis, out = float(edge), 1e9
    for m in maps:
        for x in (x0, x1):
            b = m(x, 0.0)[1]
            a = (m(x, float(H))[1] - b) / H
            vis = max(vis, (TEXT_EDGE_TOP - b) / a)
            out = min(out, -b / a)
    return vis, max(out, float(edge))


def text_clip(ents, sc, pos, fx, zoom=None):
    """每個文字框(.boxes.json)在 fx 動態全程(FX_U)的成片位置,驗「畫面邊緣不裁字」:
    文字框要嘛完整在畫面內(離上緣 >= TEXT_EDGE_TOP),要嘛整行在畫面上方之外;畫面內的框離左右邊 >= TEXT_EDGE_X;下緣不限。
    回傳 dict(top = 畫面內的框離上緣的最小距離, side = 離左右邊的最小距離(沒有畫面內的框時為 None),
    out = 整行在上方之外的框數, bad = [(邊「上/左/右」, 差幾 px, 文字開頭)])。"""
    px, py = pos
    maps = _fx_maps(fx, zoom)
    edge = TILT_EDGE if fx.startswith("tilt") else 0
    res = dict(top=None, side=None, out=0, bad=[])
    for e in ents:
        x0, y0, x1, y1 = (px + e["box"][0] * sc, py + e["box"][1] * sc, px + e["box"][2] * sc, py + e["box"][3] * sc)
        tops = [m(x, y0)[1] for m in maps for x in (x0, x1)]
        if y1 <= edge or max(m(x, y1)[1] for m in maps for x in (x0, x1)) <= 0:
            res["out"] += 1
            continue
        if min(tops) >= H:  # 整行在畫面下方之外
            continue
        # 畫布邊緣(tilt 的透明外圈)先裁到字的,算成不足的距離
        top = min(min(tops), TEXT_EDGE_TOP - (edge - y0) if y0 < edge else 1e9)
        left = min(min(m(x0, y)[0] for m in maps for y in (y0, y1)), TEXT_EDGE_X - (edge - x0) if x0 < edge else 1e9)
        right = min(W - max(m(x1, y)[0] for m in maps for y in (y0, y1)),
                    TEXT_EDGE_X - (x1 - (W - edge)) if x1 > W - edge else 1e9)
        res["top"] = top if res["top"] is None else min(res["top"], top)
        res["side"] = min(left, right) if res["side"] is None else min(res["side"], left, right)
        txt = re.sub(r"\s+", "", e.get("text", ""))[:8]
        for name, val, need in (("上", top, TEXT_EDGE_TOP), ("左", left, TEXT_EDGE_X), ("右", right, TEXT_EDGE_X)):
            if val < need - 0.5:
                res["bad"].append((name, need - val, txt))
    return res


def layout_image(s, media, im_size):
    """圖片鏡頭版面:決定縮放 sc 與圖片左上角 pos(輸出像素)。
    縮放下限是圖寬填滿畫面(tilt 為 IMG_FILL_TILT),不為了避字幕而縮小;
    重點區(hl 命中框聯集 > s["focus"] > FOCUS_DEFAULT)用平移放到字幕帶以上的安全區,
    文字太小(行高 < TEXT_MIN_PX)時在放得下的前提下放大到 TEXT_TARGET_PX。放不下就維持下限倍率並回報 too_big。
    有 .boxes.json 的圖另外保證畫面邊緣不裁字(text_clip 的規則,含 fx 動態):優先順序是
    重點區在字幕帶以上 > 文字塊頂端完整在畫面內 > 放大倍率;放不下所有行時,以整行為單位把上方的行推出畫面(推出的行數最少)。
    zoom 的終點倍率與錨點由 _zoom_fit 決定,存在回傳值的 zoom。"""
    imw, imh = im_size
    tilt = s["fx"].startswith("tilt")
    y_lo, y_hi = SAFE_Y_TILT if tilt else SAFE_Y_FLAT
    cy_t = (y_lo + y_hi) / 2
    hits, missing = _hl_hits(s, media, imw)
    hit_all = [h for hs in hits for h in hs]
    focus = s.get("focus") or []
    strict = bool(hit_all or focus)  # 預設重點區(上方 60%)只定位,不做放不放得下的判斷

    s0 = (IMG_FILL_TILT if tilt else IMG_FILL_FLAT) * W / imw
    ents = _load_boxes(media, s["img"]) or []
    content = None  # 所有文字框的聯集(原圖像素 x0,x1);有的話水平方向以「內容寬」置中,倍率上限讓內容寬完整入鏡
    cap = None
    if ents:
        content = (min(e["box"][0] for e in ents), max(e["box"][2] for e in ents))
        zmax, ddx = _zoom_params(s["fx"])
        cap = (W - 2 * (CONTENT_MARGIN_X * W + abs(ddx))) / ((content[1] - content[0]) * zmax)
        s0 = min(s0, cap)
    if imh * s0 < H:  # 高度不足畫面:能放大填高就填高(受寬度上限約束),否則維持寬度並讓模糊底圖補空白
        s0 = max(s0, min(H / imh, (IMG_FILL_TILT_MAX if tilt else 1.0) * W / imw, cap or 1e9))

    lh_ref = None
    if hit_all:
        hs = sorted(h["box"][3] - h["box"][1] for h in hit_all)
        lh_ref = hs[len(hs) // 2]
    elif focus:
        fx0, fy0, fx1, fy1 = [min(f[i] for f in focus) if i < 2 else max(f[i] for f in focus) for i in range(4)]
        hs = sorted(e["box"][3] - e["box"][1] for e in (_load_boxes(media, s["img"]) or [])
                    if fx0 * imw <= (e["box"][0] + e["box"][2]) / 2 <= fx1 * imw
                    and fy0 * imh <= (e["box"][1] + e["box"][3]) / 2 <= fy1 * imh)
        lh_ref = hs[len(hs) // 2] if hs else None

    def region(sc):
        if hit_all:
            rx0 = ry0 = 1e9
            rx1 = ry1 = -1e9
            for h in hit_all:
                x0, y0, x1, y1 = h["box"]
                lh = y1 - y0
                yb = h["uy"] + (max(HL_UL_MINW, HL_UL_W * lh * sc) + 2 * HL_UL_EDGE) / sc
                rx0, ry0 = min(rx0, x0, h["ux0"]), min(ry0, y0)
                rx1, ry1 = max(rx1, x1, h["ux1"]), max(ry1, yb)
            return rx0, ry0, rx1, ry1
        fs = focus or [FOCUS_DEFAULT]
        return (min(f[0] for f in fs) * imw, min(f[1] for f in fs) * imh,
                max(f[2] for f in fs) * imw, max(f[3] for f in fs) * imh)

    def place(sc):
        iw, ih = imw * sc, imh * sc
        rx0, ry0, rx1, ry1 = region(sc)
        cx, cy = (rx0 + rx1) / 2 * sc, (ry0 + ry1) / 2 * sc
        zp = _zoom_params(s["fx"])
        zoom = (zp[0], 0.5, 0.5) if _zoomish(s["fx"]) else None
        side_ok = True
        if content:  # 內容寬置中;圖寬 >= 畫面時盡量不露出圖邊,但露邊與裁字(含 fx 動態後離邊不足 TEXT_EDGE_X)衝突時以不裁字為準
            lc = W / 2 - (content[0] + content[1]) / 2 * sc
            best = None
            for cand in (max(W - iw, min(0.0, lc)) if iw >= W else max(0.0, min(W - iw, lc)), lc):
                cand = round(cand)
                c0, c1 = cand + content[0] * sc, cand + content[1] * sc
                zm = _zoom_fit(c0, c1, zp[0], zp[1]) if zoom else None
                fits = _side_margin(c0, c1, _fx_maps(s["fx"], zm)) >= TEXT_EDGE_X - 0.5
                if best is None or fits > best[0]:  # 不露圖邊的位置放得下(zoom 可降倍率)就用它,否則改成內容置中
                    best = (fits, cand, zm)
            side_ok, left, zoom = best
        else:
            left = (W - iw) / 2 if iw <= W else min(0.0, max(W - iw, W / 2 - cx))
        ok = ok_h = not strict or ((rx1 - rx0) * sc + 2 * FOCUS_MARGIN_X * W <= W
                                   and left + rx0 * sc >= 0 and left + rx1 * sc <= W)
        safe_h = H - IMG_BOTTOM_KEEP
        top = None
        for lim in (H, safe_h):  # 先要求圖片蓋滿畫面;重點區放不進去才讓圖底縮進字幕帶(圖底邊緣不會出現在安全區內)
            if ih < lim:
                continue
            t = min(0.0, max(lim - ih, cy_t - cy))
            if top is None:
                top = t
            if y_lo <= t + ry0 * sc and t + ry1 * sc <= y_hi:
                top = t
                break
        else:
            if top is not None and strict:
                ok = False
        if top is None:  # 圖比安全區矮:放在安全區內(重點區優先對中,其餘置中)
            top = (safe_h - ih) / 2
            if strict:
                top = min(safe_h - ih, max(0.0, cy_t - cy))
                ok = ok and y_lo <= top + ry0 * sc and top + ry1 * sc <= y_hi
        left, top, n_out = round(left), round(top), 0
        if ents:  # 垂直:畫面上緣不切半行。每個文字框有一段「會被上緣切到」的 top 區間,從剩下的區間裡挑
            maps = _fx_maps(s["fx"], zoom)
            edge = TILT_EDGE if tilt else 0
            rows = []  # (框頂, 框底, vis, out):畫布 y = top + 框頂/框底
            for e in ents:
                vis, out = _top_limits(left + e["box"][0] * sc, left + e["box"][2] * sc, maps, edge)
                rows.append((e["box"][1] * sc, e["box"][3] * sc, vis, out))
            t_all = max(vis - y0 for y0, _, vis, _ in rows)  # top >= t_all 時所有行都在畫面內
            lo, hi = (safe_h - ih, 0.0) if ih >= safe_h else (0.0, safe_h - ih)  # 圖底不高於字幕帶上緣、圖頂不低於畫面上緣
            full_lo = H - ih if ih >= H else lo                                 # 圖片蓋滿畫面的範圍下限
            hi_ext = max(hi, math.ceil(t_all))  # 第一行太靠圖頂(tilt 近側上緣在畫面外)時,寧可讓圖頂往下露出模糊底
            segs, p = [], lo
            for a, b in sorted((out - y1, vis - y0) for y0, y1, vis, out in rows):  # top 在 (a, b) 之間 = 這一行被切
                if b <= a:
                    continue
                if min(a, hi_ext) >= p:
                    segs.append((p, min(a, hi_ext)))
                p = max(p, b)
            if p <= hi_ext:
                segs.append((p, hi_ext))
            r0, r1 = (y_lo - ry0 * sc, y_hi - ry1 * sc) if strict else (-1e9, 1e9)  # 重點區落在安全區內的 top 範圍
            want = top if not strict else cy_t - cy
            pick = None
            for p, q in segs:
                for a, b, hl_ok in ((max(p, r0), min(q, r1), True), (p, q, False)):
                    for fa, fb, full in ((max(a, full_lo), min(b, hi), True), (a, b, False)):
                        fa, fb = math.ceil(fa - 1e-6), math.floor(fb + 1e-6)
                        if fa > fb:
                            continue
                        t = min(fb, max(fa, round(want)))
                        n = sum(1 for _, y1, _, out in rows if t + y1 <= out)
                        key = (not hl_ok, n, not full, abs(t - want))
                        if pick is None or key < pick[0]:
                            pick = (key, t, n)
            if pick is not None:  # 沒有不切行的位置(行與行重疊或可移動範圍太小)時維持原位置,由渲染前檢查 check_text_clip 報錯
                top, n_out = pick[1], pick[2]
                ok = ok_h and not (strict and pick[0][0])
        return dict(ok=ok, side_ok=side_ok, pos=(left, top), zoom=zoom, n_out=n_out)

    s_want = s0
    if strict and lh_ref and lh_ref * s0 < TEXT_MIN_PX:
        s_want = min(max(s0, TEXT_TARGET_PX / lh_ref), s0 * TEXT_UP_MAX, cap or 1e9)
    cands = []
    sc = s_want
    while sc > s0 * 1.005:
        cands.append(sc)
        sc /= 1.03
    cands.append(s0)
    cands += [s0 * 1.03 ** i for i in range(1, 17) if cap is None or s0 * 1.03 ** i <= cap] if strict else []  # 下限倍率放不進去時,放大反而有更多平移空間
    chosen = None  # 放得下的候選裡:左右不裁字 > 推出畫面的行數最少 > 候選順序(原本想要的倍率優先)
    for i, sc in enumerate(cands):
        pl = place(sc)
        key = (not pl["side_ok"], pl["n_out"], i)
        if pl["ok"] and (chosen is None or key < chosen[0]):
            chosen = (key, sc, pl)
    too_big = chosen is None
    if too_big:
        chosen = (None, s0, place(s0))
    _, sc, pl = chosen
    return dict(sc=sc, pos=pl["pos"], zoom=pl["zoom"], n_out=pl["n_out"], hits=hits, missing=missing, too_big=too_big,
                base=s0, size=im_size)


_hlseq_cache = {}


def _load_hlseq(media, img):
    """截圖時一起產出的底線序列索引 images/<img>.hl.json(news_lib 計畫 §2C);沒有、或尺寸與原圖不符 -> None(走舊畫法)"""
    if img not in _hlseq_cache:
        f, d = media / "images" / f"{img}.hl.json", None
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            with Image.open(media / "images" / f"{img}.png") as im:
                if tuple(d.get("size", ())) != im.size:
                    print(f"  [紅線] {img}.hl.json 尺寸與原圖不符,改用舊畫法", flush=True)
                    d = None
        _hlseq_cache[img] = d
    return _hlseq_cache[img]


def _hl_seq_bars(media, seq, kws, sc, px, py, k):
    """瀏覽器出的底線序列 -> [(各 p 的 sprite 清單, x, y)](畫布座標);任一詞在序列裡找不到就回傳 None(整段走舊畫法)"""
    bars = []
    for kw in kws:
        q = re.sub(r"\s+", "", kw).lower()
        rows = [b for b in seq["bars"] if re.sub(r"\s+", "", b["kw"]).lower() == q][:HL_MAX]
        if not rows:
            return None
        for b in rows:
            w_, h_ = max(1, round(b["w"] * sc * k)), max(1, round(b["h"] * sc * k))
            sprs = [Image.open(media / "images" / fn).convert("RGBA").resize((w_, h_), Image.LANCZOS) for fn in b["files"]]
            bars.append((sprs, round((px + b["x"] * sc) * k), round((py + b["y"] * sc) * k)))
    return bars


def hl_starts(hs, shot_f0, shot_frames):
    """各段 hl 離鏡頭開頭的起點秒數;hs = 依序的 {"f0", "tw"}(tw = hl_word_time 的結果,可缺或 None)。
    基準 = 該句起點 + HL_DELAY;有 tw 時改在該詞發音前 HL_WORD_LEAD 開始,再由後往前夾,每段至少留 HL_MIN_SHOW 秒給下一段或鏡頭結束。
    夾完一律不小於基準:只會比基準晚,不會早;沒有 tw 的段維持基準。"""
    base = [(h["f0"] - shot_f0) / FPS + HL_DELAY for h in hs]
    out = [b if h.get("tw") is None else max(b, h["tw"] - HL_WORD_LEAD - shot_f0 / FPS) for h, b in zip(hs, base)]
    lim = shot_frames / FPS
    for i in reversed(range(len(out))):
        out[i] = max(base[i], min(out[i], lim - HL_MIN_SHOW))
        lim = out[i]
    return out


def prep_hl(s, stem, bw, bh, k, lay, media=None):
    """依 s["hls"] 的命中框畫紅色底線,每段 hl 輸出一組逐格 PNG(與前景同畫布座標):
    各底線依序由左至右擦出(ease-out),全部畫完的最後一格會被 ffmpeg 延長到該標記結束。存入 s["hl_layers"]。
    起點見 hl_starts(旁白唸到該詞才開始畫,對不到退回句子起點 + HL_DELAY);下一段開始時淡出前一段。
    圖有 images/<img>.hl.json(瀏覽器排版時一起出的底線序列,p = 0…1)就用序列:ease-out 進度對到最近的 p;
    沒有序列(舊圖)或該段的詞不在序列裡,才走下面的 Pillow 畫線(_ul_span/_ink_bottom/find_hl_boxes 為 fallback)。"""
    s["hl_layers"] = []
    sc, (px, py) = lay["sc"], lay["pos"]
    seq = _load_hlseq(media, s["img"]) if media else None
    for i, (h, hits) in enumerate(zip(s.get("hls") or [], lay["hits"])):
        if not hits:
            continue
        sbars = _hl_seq_bars(media, seq, h["kws"], sc, px, py, k) if seq else None
        if sbars:
            per = min(HL_UL_DUR, HL_UL_TOTAL / len(sbars))
            bf = max(3, round(per * FPS))
            nfr = len(sbars) * bf + 1
            sig = sha1(json.dumps(["seq", [(x, y, sp[0].size) for sp, x, y in sbars], bf, bw, bh, h["kws"],
                                   (media / "images" / f"{s['img']}.hl.json").stat().st_mtime]))
            pat = f"{stem}_hl{i}_%03d.png"
            sigf = Path(f"{stem}_hl{i}.sig")
            files = [Path(pat % f) for f in range(nfr)]
            if not (sigf.exists() and sigf.read_text(encoding="utf-8") == sig and all(f.exists() for f in files)):
                for old in Path(stem).parent.glob(f"{Path(stem).name}_hl{i}_*.png"):
                    old.unlink()
                for f in range(nfr):
                    canvas = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
                    for j, (sprs, bx, by) in enumerate(sbars):
                        u = min(1.0, max(0.0, (f - j * bf) / bf))
                        pi = round((1 - (1 - u) ** 3) * (len(sprs) - 1))  # ease-out cubic -> 最近的 p
                        if pi > 0:
                            _blit(canvas, sprs[pi], bx, by)
                    canvas.save(files[f], compress_level=1)
                sigf.write_text(sig, encoding="utf-8")
            s["hl_layers"].append(dict(pat=pat, files=files, f0=h["f0"], tw=h.get("tw"), t0=0.0, t1=None))
            continue
        bars = []
        for hit in hits:
            x0, y0, x1, y1 = hit["box"]
            lh = y1 - y0
            th = max(HL_UL_MINW, HL_UL_W * lh * sc) * k
            e = HL_UL_EDGE * k
            bx0, bx1 = (px + hit["ux0"] * sc) * k, (px + hit["ux1"] * sc) * k
            by0 = (py + hit["uy"] * sc) * k
            ss = 3  # 超取樣畫圓頭
            w_, h_ = max(2, round(bx1 - bx0 + 2 * e)), max(2, round(th + 2 * e))
            spr = Image.new("RGBA", (w_ * ss, h_ * ss), (0, 0, 0, 0))
            d = ImageDraw.Draw(spr)
            d.rounded_rectangle((0, 0, w_ * ss - 1, h_ * ss - 1), h_ * ss / 2, fill=HL_UL_EDGE_COLOR)
            d.rounded_rectangle((e * ss, e * ss, (w_ - e) * ss - 1, (h_ - e) * ss - 1), th * ss / 2, fill=HL_UL_COLOR)
            bars.append((spr.resize((w_, h_), Image.LANCZOS), round(bx0 - e), round(by0 - e)))
        per = min(HL_UL_DUR, HL_UL_TOTAL / len(bars))
        bf = max(3, round(per * FPS))
        nfr = len(bars) * bf + 1
        sig = sha1(json.dumps([[(b[1], b[2], b[0].size) for b in bars], bf, bw, bh, HL_UL_COLOR, HL_UL_EDGE_COLOR]))
        pat = f"{stem}_hl{i}_%03d.png"
        sigf = Path(f"{stem}_hl{i}.sig")
        files = [Path(pat % f) for f in range(nfr)]
        if not (sigf.exists() and sigf.read_text() == sig and all(f.exists() for f in files)):
            for old in Path(stem).parent.glob(f"{Path(stem).name}_hl{i}_*.png"):
                old.unlink()
            for f in range(nfr):
                canvas = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
                for j, (spr, bx, by) in enumerate(bars):
                    u = min(1.0, max(0.0, (f - j * bf) / bf))
                    shown = round(spr.width * (1 - (1 - u) ** 3))  # ease-out cubic
                    if shown > 0:
                        _blit(canvas, spr.crop((0, 0, shown, spr.height)), bx, by)
                canvas.save(files[f], compress_level=1)
            sigf.write_text(sig)
        s["hl_layers"].append(dict(pat=pat, files=files, f0=h["f0"], tw=h.get("tw"), t0=0.0, t1=None))
    ts = hl_starts(s["hl_layers"], s["f0"], s["frames"])
    for i, L in enumerate(s["hl_layers"]):
        L["t0"] = ts[i]
        if i + 1 < len(ts):
            L["t1"] = ts[i + 1]


_label_cache = {}


def _label_info(media, img):
    """((圖寬, 圖高), 重貼前的標籤 (w, h) 或 None),依 split_label 的偵測結果;每張圖只開一次。"""
    if img not in _label_cache:
        with Image.open(media / "images" / f"{img}.png") as im0:
            im = im0.convert("RGB")
        _, lab = split_label(im)
        _label_cache[img] = (im.size, (lab.width, lab.height) if lab else None)
    return _label_cache[img]


def _place_label(s, media, im_size, label_wh, lay):
    """烤在圖上的「中文翻譯 · 原文」標籤重貼的位置(成片像素、k=1):回傳 (右緣, 下緣, 外框 (x0, y0, x1, y1))。
    預設在圖右下(超出安全區就貼安全區),與文字框重疊就改右上。zoom 類 fx(含 drift)另外保證標籤也離成片左右邊 >= TEXT_EDGE_X、
    離上緣 >= TEXT_EDGE_TOP(fx 動態全程,與文字框同規則;2026-10-22 標籤被水平漂移推出右緣):右緣往內縮、上緣往下移。"""
    px, py = lay["pos"]
    sc = lay["sc"]
    tilt = s["fx"].startswith("tilt")
    y_lo, y_hi = SAFE_Y_TILT if tilt else SAFE_Y_FLAT
    imw, imh = im_size
    lw, lh_ = label_wh[0] * LABEL_SCALE, label_wh[1] * LABEL_SCALE
    r_ = min(px + imw * sc, W) - LABEL_MARGIN
    b_ = min(py + imh * sc, y_hi) - LABEL_MARGIN * 0.6
    t_ = max(py, y_lo) + LABEL_MARGIN * 0.6
    if _zoomish(s["fx"]):
        maps = _fx_maps(s["fx"], lay.get("zoom"))
        r_ = min([r_] + [(W - TEXT_EDGE_X - m(0, 0)[0]) / (m(1, 0)[0] - m(0, 0)[0]) for m in maps])
        t_ = max([t_] + [(TEXT_EDGE_TOP - m(0, 0)[1]) / (m(0, 1)[1] - m(0, 0)[1]) for m in maps])
    boxes = _load_boxes(media, s["img"]) or []

    def overlap(rc):
        return sum(max(0.0, min(rc[2], px + e["box"][2] * sc) - max(rc[0], px + e["box"][0] * sc))
                   * max(0.0, min(rc[3], py + e["box"][3] * sc) - max(rc[1], py + e["box"][1] * sc)) for e in boxes)
    if overlap((r_ - lw, b_ - lh_, r_, b_)) > 0:  # 右下與文字框重疊 -> 右上
        b_ = t_ + lh_
    return r_, b_, (r_ - lw, b_ - lh_, r_, b_)


LABEL_STYLES = ("lower", "corner")
_TAG_DATE_RE = re.compile(r"\s+(\d{4}(?:/\d{1,2}){0,2})$")


def split_tag_text(t):
    """.layout.json 的 tag_text(例「中文翻譯 · 原文:Press Start 2026/05/29」)拆成 lower 的 (主字, 副字):
    主字「原文:Press Start」(48px 粗體,讀者要找的出處)、副字「中文翻譯 · 2026/05/29」(36px,說明語言與日期)。
    不是「中文翻譯 · 原文:」格式(site 以 = 開頭原樣顯示的)就整串當主字、沒有副字。"""
    pre = "中文翻譯 · 原文:"
    if not t.startswith(pre):
        return t, ""
    rest = t[len(pre):].strip()
    m = _TAG_DATE_RE.search(rest)
    name, date = (rest[:m.start()], m.group(1)) if m else (rest, "")
    return f"原文:{name}", "中文翻譯" + (f" · {date}" if date else "")


def _tag_text(media, img):
    """news_lib 在 .layout.json 寫的出處標籤字串;舊圖沒有回傳 None。"""
    f = media / "images" / f"{img}.layout.json"
    try:
        return (json.loads(f.read_text(encoding="utf-8")).get("tag_text") or "").strip() or None
    except (OSError, ValueError):
        return None


def decide_labels(shots, lines, media, cli_style="lower", top_style=None):
    """截圖鏡頭的出處標籤要用哪一種(2026-10-22):預設 lower = 抹掉烤在圖上的右下角標、改自動加一個 kit lower 下標籤(s["label_lower"]);
    corner = 舊角標重貼。優先序:該鏡頭句子的 label_style > script 頂層 label_style > --label-style > lower。
    退回 corner 的情況:設定 corner / 圖上偵測不到角標(閱讀卡)/ 該鏡頭已有使用者寫的 lower(保留角標當出處,避免兩個 lower)/ 圖沒有 tag_text(舊圖)。
    回傳錯誤(label_style 值不認得)。"""
    errs, noted = [], set()
    by_idx = {ln["idx"]: ln for ln in lines}
    for s in shots:
        s["label_lower"] = None
        if s["kind"] != "image" or s.get("special") or not (media / "images" / f"{s['img']}.png").exists():
            continue
        rng = [by_idx[i] for i in range(s["line"], (s.get("last_line") or s["line"]) + 1) if i in by_idx]
        style = next((ln["label_style"] for ln in rng if ln.get("label_style")), None) or top_style or cli_style or "lower"
        if style not in LABEL_STYLES:
            errs.append(f"{_line_span(s)}: label_style「{style}」不認得(可用:{'、'.join(LABEL_STYLES)})")
            continue
        if style == "corner" or not _label_info(media, s["img"])[1]:
            continue
        if any(isinstance(it, dict) and it.get("type") == "lower" for ln in rng
               for it in (ln.get("kit") if isinstance(ln.get("kit"), list) else [])):
            continue
        t = _tag_text(media, s["img"])
        if not t:
            if s["img"] not in noted:
                noted.add(s["img"])
                log(f"資訊: {s['img']} 的 .layout.json 沒有 tag_text(舊圖),出處標籤退回右下角標;重截一次(news_lib)就會改用 lower 下標籤")
            continue
        main, sub = split_tag_text(t)
        s["label_lower"] = dict(text=main, **({"sub": sub} if sub else {}))
    return errs


def _label_ent(s, media, lay):
    """標籤當成一個不可裁的「文字框」(原圖像素座標,格式同 .boxes.json)供 text_clip 驗證;沒有標籤或非 zoom 類 fx(tilt 舊片不動)回傳 None。"""
    if not _zoomish(s["fx"]) or s.get("label_lower"):   # 標籤已改成 lower 下標籤(小件自己避讓)
        return None
    im_size, wh = _label_info(media, s["img"])
    if not wh:
        return None
    x0, y0, x1, y1 = _place_label(s, media, im_size, wh, lay)[2]
    px, py = lay["pos"]
    sc = lay["sc"]
    return dict(text="出處標籤", box=[(x0 - px) / sc, (y0 - py) / sc, (x1 - px) / sc, (y1 - py) / sc])



def prep_image(s, media, outdir):
    """圖片鏡頭素材:依 layout_image 的縮放/平移放圖(其餘以同圖模糊壓暗填滿),烤在圖裡的「中文翻譯」標籤改貼在安全區右下角。
    tilt 另存前景(透明畫布)供 perspective。"""
    im = Image.open(media / "images" / f"{s['img']}.png").convert("RGB")
    tilt = s["fx"].startswith("tilt")
    k = 2 if _zoomish(s["fx"]) else 1  # zoom 類(含 drift)用 2x 解析度避免抖動
    bw, bh = W * k, H * k
    lay = s.get("layout") or layout_image(s, media, im.size)
    s["layout"] = lay
    sc, (px, py) = lay["sc"], lay["pos"]
    bg = _cover(im, 320, 180).filter(ImageFilter.GaussianBlur(5)).resize((bw, bh), Image.BICUBIC)
    bg = ImageEnhance.Brightness(bg).enhance(BG_DIM)
    clean, label = split_label(im)
    if s.get("label_lower"):   # 出處改由 lower 下標籤顯示,不重貼角標
        label = None
    iw, ih = im.width * sc * k, im.height * sc * k
    # 只縮放會落在畫布內的那一塊(放大很多倍時不必產生整張超大圖)
    dx0, dy0 = max(0, round(px * k)), max(0, round(py * k))
    dx1, dy1 = min(bw, round(px * k + iw)), min(bh, round(py * k + ih))
    box = ((dx0 - px * k) / (sc * k), (dy0 - py * k) / (sc * k), (dx1 - px * k) / (sc * k), (dy1 - py * k) / (sc * k))
    box = (max(0.0, box[0]), max(0.0, box[1]), min(float(im.width), box[2]), min(float(im.height), box[3]))
    fg = clean.resize((dx1 - dx0, dy1 - dy0), Image.LANCZOS, box=box).convert("RGBA")
    outdir.mkdir(parents=True, exist_ok=True)
    stem = outdir / f"{s['n']:04d}"
    lab_right = lab_bottom = None
    if label:
        lab_right, lab_bottom = (v * k for v in _place_label(s, media, im.size, (label.width, label.height), lay)[:2])
    if tilt:
        canvas = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        canvas.alpha_composite(fg, (dx0, dy0))
        if label:
            _paste_label(canvas, label, lab_right, lab_bottom, LABEL_SCALE * k)
        e = 2 * k  # 畫布最外圈留透明:perspective 對範圍外取樣會把邊緣像素拉出條紋,圖滿版時邊緣不能有內容
        cd = ImageDraw.Draw(canvas)
        for r in ((0, 0, bw, e - 1), (0, bh - e, bw, bh), (0, 0, e - 1, bh), (bw - e, 0, bw, bh)):
            cd.rectangle(r, fill=(0, 0, 0, 0))
        s["aux"] = [Path(f"{stem}_bg.png"), Path(f"{stem}_fg.png")]
        bg.save(s["aux"][0])
        canvas.save(s["aux"][1])
    else:
        comp = bg.convert("RGBA")
        comp.alpha_composite(fg, (dx0, dy0))
        if label:
            _paste_label(comp, label, lab_right, lab_bottom, LABEL_SCALE * k)
        pad = _zoom_pad(s) * k if k == 2 else 0
        if pad:  # 補邊:圖左右沒蓋到的地方用圖的邊色延伸,畫布左右再補 pad(漂移全程成片兩側都是圖的底色,不露畫布底)
            comp, sd = _extend_sides(comp, dx0, dx1, dy0, dy1, pad)
            if sd > EDGE_STD_WARN:
                print(f"警告: {_line_span(s)} {s['img']} 左右邊色不均勻(逐列標準差 {sd:.0f}),補邊為逐列延伸", flush=True)
        if k == 2:  # zoom 類(text 組):圖上下沒蓋到畫布頂/底的地方同樣用邊色延伸(不露出模糊底圖的黑帶)
            comp, skipped = _extend_vert(comp, dy0, dy1)
            for side, sd in skipped:
                print(f"警告: {_line_span(s)} {s['img']} {side}緣邊色不均勻(欄間標準差 {sd:.0f}),不延伸上下補邊", flush=True)
        s["aux"] = [Path(f"{stem}_comp.png")]
        comp.convert("RGB").save(s["aux"][0])
    prep_hl(s, stem, bw, bh, k, lay, media)


# ---------------------------------------------------------------- 引言卡 / 左右對比(script 的 quote / compare 欄位)
NO_LINE_START = set("，。？！、：；,.;:?!」』》）)…—")


def _wrap_text(text, font, max_w):
    """引言卡/對比卡斷行(2026-10-22):只在詞與詞之間換行(text_wrap.break_groups,jieba+專案詞表);行首不可是黏前字/標點;
    最後一行 <=2 字時把上一行最後一個詞帶下來(放得下才帶)。單一詞比行寬還長時才逐字切。"""
    from text_wrap import break_groups
    out = []
    for para in text.split("\n"):
        lines, cur = [], []     # 每行是詞清單
        for g in (break_groups(para) if para else []):
            if cur and font.getlength("".join(cur) + g) > max_w and g[0] not in NO_LINE_START:
                lines.append(cur)
                cur = [g.lstrip()]
            else:
                cur.append(g)
            while len(cur) == 1 and font.getlength(cur[0]) > max_w and len(cur[0]) > 1:   # 單詞過長:逐字切
                k = max(1, next((i for i in range(1, len(cur[0]) + 1) if font.getlength(cur[0][:i]) > max_w), len(cur[0])) - 1)
                lines.append([cur[0][:k]])
                cur = [cur[0][k:]]
        lines.append(cur)
        if len(lines) >= 2 and len("".join(lines[-1]).strip()) <= 2 and len(lines[-2]) > 1:
            moved = lines[-2][-1]
            if font.getlength(moved + "".join(lines[-1])) <= max_w:
                lines[-1] = [moved] + lines[-1]
                lines[-2] = lines[-2][:-1]
        out.extend("".join(l).rstrip() for l in lines)
    return out


def _blur_bg(media, img, dim):
    if not img:
        return Image.new("RGB", (W, H), (12, 14, 20))
    im = Image.open(media / "images" / f"{img}.png").convert("RGB")
    bg = _cover(im, 320, 180).filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BICUBIC)
    return ImageEnhance.Brightness(bg).enhance(dim)


def make_quote(q, img, media, path, portrait=False):
    """引言卡:模糊壓暗的同圖(沒有圖就純深色)+ 深色半透明底板 + 上方說話者身分(q["who"],選填)+ 大字引文 + 右下來源。文字不進字幕帶。
    portrait=True:直式畫面窗原生 1080x1080(底板寬 <= 安全框 860、所有字 >= P_FS_MIN)。回傳用到的最小字級(px)。"""
    comp = _blur_bg(media, img, BG_DIM * 0.8).convert("RGBA")
    if portrait:
        comp = comp.crop(((W - P_NAT) // 2, 0, (W + P_NAT) // 2, H)).resize((P_NAT, P_NAT))
    cw_, ch_ = comp.size
    text = q["text"]
    y_lo, y_hi = (P_SAFE[1], P_SAFE[3]) if portrait else (50, H - IMG_BOTTOM_KEEP - 24)
    pad_x = P_QUOTE_PADX if portrait else 90
    max_w = (P_NAT - 2 * P_QUOTE_MX - 2 * pad_x) if portrait else int(W * 0.70)
    size, s_min = (P_QUOTE_FS, P_QUOTE_FS_MIN) if portrait else (96, 40)
    fs_min, fw_min = (P_FS_MIN, P_FS_MIN) if portrait else (30, 44)
    while True:
        f = ImageFont.truetype(FONT, size, index=0)
        fs = ImageFont.truetype(FONT, max(fs_min, int(size * 0.42)), index=0)
        lines = _wrap_text(text, f, max_w)
        lh = int(size * 1.45)
        src = f"—— {q['src']}" if q.get("src") else ""
        who = q.get("who") or ""
        fw = ImageFont.truetype(FONT, max(fw_min, int(size * 0.6)), index=0)
        src_lines = [src]
        if portrait:   # 出處太長時縮字到放得下(不低於下限),仍放不下就換行
            while src and fs.size > P_FS_MIN and fs.getlength(src) > max_w:
                fs = ImageFont.truetype(FONT, fs.size - 2, index=0)
            if src and fs.getlength(src) > max_w:
                src_lines = _wrap_text(src, fs, max_w)
        who_h = int(fw.size * 1.3) + 26 if who else 0
        block = who_h + lh * len(lines) + (int(fs.size * 1.3) * len(src_lines) + 30 if src else 0)
        pad_y = 56
        if block + 2 * pad_y <= y_hi - y_lo or size <= s_min:
            break
        size -= 4
    tw = max([f.getlength(l) for l in lines] + [fs.getlength(x) for x in src_lines if src] + [fw.getlength(who) if who else 0])
    pw, ph = int(tw + 2 * pad_x), block + 2 * pad_y
    x0 = int((P_NAT - pw) / 2) if portrait else (W - pw) // 2
    y0 = int((y_lo + y_hi - ph) / 2)
    ov = Image.new("RGBA", (cw_, ch_), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), 28, fill=(8, 10, 16, 215))
    d.rectangle((x0, y0 + 28, x0 + 8, y0 + ph - 28), fill=(255, 212, 121, 255))
    y = y0 + pad_y
    if who:
        d.text((x0 + pad_x, y), who, font=fw, fill=(255, 212, 121, 255), anchor="lt",
               stroke_width=2, stroke_fill=(16, 16, 16, 255))
        y += who_h
    for l in lines:
        d.text((x0 + pad_x, y + lh / 2), l, font=f, fill=(255, 255, 255, 255), anchor="lm",
               stroke_width=3, stroke_fill=(16, 16, 16, 255))
        y += lh
    if src:
        for i, sl in enumerate(src_lines):
            d.text((x0 + pw - pad_x, y + 30 + i * int(fs.size * 1.3)), sl, font=fs, fill=(255, 212, 121, 255), anchor="rt",
                   stroke_width=2, stroke_fill=(16, 16, 16, 255))
    comp.alpha_composite(ov)
    path.parent.mkdir(parents=True, exist_ok=True)
    comp.convert("RGB").save(path)
    return min(f.size, fs.size if src else f.size, fw.size if who else f.size)


COMPARE_GAP = 6
COMPARE_BAR_H = 76
COMPARE_ACCENT = ((255, 212, 121), (122, 200, 255))


def make_compare(cmp_, media, path, portrait=False):
    """左右並排:各半滿版 cover 裁切(靠上),中間 COMPARE_GAP px 分隔線,上方各一個標籤條;圖上烤的翻譯標籤改貼在各半右下角。
    portrait=True:直式畫面窗原生 1080x1080,改上下並排(left 在上),標籤字 P_CMP_FS、翻譯標籤靠安全框右緣。回傳最小字級。"""
    if portrait:
        return _make_compare_p(cmp_, media, path)
    hw = (W - COMPARE_GAP) // 2
    comp = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    f = ImageFont.truetype(FONT, 42, index=0)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for side, x0, accent in (("left", 0, COMPARE_ACCENT[0]), ("right", W - hw, COMPARE_ACCENT[1])):
        cfg = cmp_[side]
        im = Image.open(media / "images" / f"{cfg['img']}.png").convert("RGB")
        clean, label = split_label(im)
        half = _cover_at(clean, hw, H, cfg.get("x", 0.5), cfg.get("y", 0.0)).convert("RGBA")
        comp.alpha_composite(half, (x0, 0))
        if label:
            _paste_label(comp, label, x0 + hw - LABEL_MARGIN, H - IMG_BOTTOM_KEEP - 10, LABEL_SCALE)
        d.rectangle((x0, 0, x0 + hw - 1, COMPARE_BAR_H), fill=(0, 0, 0, 205))
        d.rectangle((x0, COMPARE_BAR_H - 5, x0 + hw - 1, COMPARE_BAR_H), fill=accent + (255,))
        d.text((x0 + hw / 2, (COMPARE_BAR_H - 5) / 2), cfg.get("label", ""), font=f, fill=(255, 255, 255, 255),
               anchor="mm", stroke_width=2, stroke_fill=(16, 16, 16, 255))
    comp.alpha_composite(ov)
    path.parent.mkdir(parents=True, exist_ok=True)
    comp.convert("RGB").save(path)


def _make_compare_p(cmp_, media, path):
    hh = (P_NAT - COMPARE_GAP) // 2
    comp = Image.new("RGBA", (P_NAT, P_NAT), (255, 255, 255, 255))
    f = ImageFont.truetype(FONT, P_CMP_FS, index=0)
    ov = Image.new("RGBA", (P_NAT, P_NAT), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for side, y0, accent in (("left", 0, COMPARE_ACCENT[0]), ("right", P_NAT - hh, COMPARE_ACCENT[1])):
        cfg = cmp_[side]
        im = Image.open(media / "images" / f"{cfg['img']}.png").convert("RGB")
        clean, label = split_label(im)
        comp.alpha_composite(_cover_at(clean, P_NAT, hh, cfg.get("x", 0.5), cfg.get("y", 0.0)).convert("RGBA"), (0, y0))
        if label:
            _paste_label(comp, label, P_SAFE[2], y0 + hh - 12, P_FS_MIN / max(1, label.height - 14))
        d.rectangle((0, y0, P_NAT - 1, y0 + P_CMP_BAR_H), fill=(0, 0, 0, 205))
        d.rectangle((0, y0 + P_CMP_BAR_H - 5, P_NAT - 1, y0 + P_CMP_BAR_H), fill=accent + (255,))
        d.text((P_CX, y0 + (P_CMP_BAR_H - 5) / 2), cfg.get("label", ""), font=f, fill=(255, 255, 255, 255),
               anchor="mm", stroke_width=2, stroke_fill=(16, 16, 16, 255))
    comp.alpha_composite(ov)
    path.parent.mkdir(parents=True, exist_ok=True)
    comp.convert("RGB").save(path)
    return P_CMP_FS


def prep_special(s, media, outdir):
    """quote / compare 鏡頭:各自產一張完整畫面 PNG,走 fx=none 的靜態路徑。"""
    outdir.mkdir(parents=True, exist_ok=True)
    s["hl_layers"] = []
    png = outdir / f"{s['n']:04d}_{s['special']}.png"
    if s["special"] == "quote":
        make_quote(s["quote"], s.get("bg_img"), media, png)
    else:
        make_compare(s["compare"], media, png)
    s["aux"] = [png]


def _tilt_filter(fx, N):
    """3D 透視傾斜(約 8-12 度,隨影格極慢漂移)。fg 為透明畫布,用 perspective 的 destination 四角。"""
    d = 1 if fx == "tilt_l" else -1
    A = f"({TILT_AMP[0]}+{TILT_AMP[1]}*on/{N})"  # 四角算式與 _tilt_quad 相同(版面與渲染前檢查用它驗文字位置),要一起改
    near, far = f"{TILT_NEAR}*{A}", f"{TILT_FAR}*{A}"
    dx = f"W*{TILT_DRIFT}*(on/{N}-0.5)*{d}"
    xl, xr = f"W*{TILT_INSET}+{dx}", f"W*{1 - TILT_INSET}+{dx}"
    yl0, yl2 = (f"-H*{near}", f"H*(1+{near})") if d == 1 else (f"H*{far}", f"H*(1-{far})")
    yr0, yr2 = (f"H*{far}", f"H*(1-{far})") if d == 1 else (f"-H*{near}", f"H*(1+{near})")
    return (f"format=rgba,perspective=x0='{xl}':y0='{yl0}':x1='{xr}':y1='{yr0}':"
            f"x2='{xl}':y2='{yl2}':x3='{xr}':y3='{yr2}':sense=destination:eval=frame")


def _zoom_filter(s, N, pad_in=False):
    """zoom 鏡頭:perspective 把畫布四角送到 fx_map 的位置(次像素內插,不會像 zoompan 逐格取整而抖動),
    輸入是 2x 畫布,最後縮回成片尺寸。倍率與錨點同 fx_map。
    畫布左右有補邊(_zoom_pad > 0)時輸入寬 = 2x 畫布 + 左右各 pad:四角改用補邊後的座標,perspective 後 crop 回 2x 畫布寬;
    pad_in=True 表示輸入是沒補邊的(底線序列),先用 ffmpeg 透明補寬。"""
    zmax, dx = _zoom_params(s["fx"])
    ze, ax, ay = (s.get("layout") or {}).get("zoom") or (zmax, 0.5, 0.5)
    k = 2
    pk = _zoom_pad(s) * k
    wb = W * k   # 2x 畫布寬(未補邊)
    z = f"(1+{ze - 1:.6f}*on/{max(1, N - 1)})"
    sh = f"+({dx * k})*(2*on/{max(1, N - 1)}-1)" if dx else ""   # drift 類:水平漂移 dx px(同 fx_map;2x 畫布所以乘 k)
    xl = f"{pk}-{pk}*{z}-({z}-1)*{wb}*{ax:.6f}{sh}"
    xr = f"{pk}+({wb + pk})*{z}-({z}-1)*{wb}*{ax:.6f}{sh}"
    yt, yb = f"-({z}-1)*H*{ay:.6f}", f"H*{z}-({z}-1)*H*{ay:.6f}"
    pre = f"format=rgba,pad={wb + 2 * pk}:{H * k}:{pk}:0:color=0x00000000," if pk and pad_in else "format=rgba,"
    post = f",crop={wb}:{H * k}:{pk}:0" if pk else ""
    return (f"{pre}perspective=x0='{xl}':y0='{yt}':x1='{xr}':y1='{yt}':x2='{xl}':y2='{yb}':x3='{xr}':y3='{yb}':"
            f"interpolation=cubic:sense=destination:eval=frame{post},scale={W}:{H}:flags=area")


# ---------------------------------------------------------------- 動態小件(kit;pipeline/kit.py + templates/kit/kit.html)
def attach_kits(shots, lines):
    """把各句 kit 分到「小件出現時刻」所在的鏡頭:s["kits"] 每項加 t(相對鏡頭起點秒)與 line,s["punch"] = punch 時刻。
    回傳錯誤(欄位、同句 <= 2、punch <= 1、同鏡頭 <= 4、spotlight 不可用在 tilt)。"""
    errs = []
    for s in shots:
        s["kits"], s["punch"] = [], []
    for ln in lines:
        items = ln.get("kit")
        if not items:
            continue
        errs += [f"句{ln['idx']}: kit {e}" for e in KIT.line_errors(items)]
        for it in items if isinstance(items, list) else []:
            if KIT.item_errors(it):
                continue
            f = ln["f0"] + round(KIT.item_start(it) * FPS)
            s = next((s for s in shots if s["f0"] <= f < s["f0"] + s["frames"]), None)
            if s is None:
                errs.append(f"句{ln['idx']}: kit {it['type']} 的 t0 超出鏡頭範圍")
                continue
            t = (f - s["f0"]) / FPS
            if it["type"] == "punch":
                s["punch"].append(t)
            s["kits"].append(dict(it, t=t, line=ln["idx"]))
    for s in shots:
        if s["kits"]:
            errs += [f"{_line_span(s)}: {e}" for e in KIT.shot_errors(s["kits"], (s.get("fx") or "").startswith("tilt"))]
    return errs


def attach_label_lowers(shots):
    """decide_labels 決定改用 lower 的鏡頭:在鏡頭起點(t=0,滑入 0.4 秒、整個鏡頭不淡出)加一個自動 lower。
    在 attach_kits 的節制檢查之後才加,所以不算進「同鏡頭 <= 4 個小件」(不擋使用者的 kit)。"""
    for s in shots:
        if s.get("label_lower"):
            s["kits"].append(dict(s["label_lower"], type="lower", t=0.0, line=s["line"], auto=True))


def _kit_base(s, ox):
    """zoom 小件的來源畫面(頁面座標):text 組 = 補邊後的 2x 合成圖、tilt = 透明前景畫布、其餘圖片鏡頭 = 整張畫面。"""
    if s["kind"] != "image" or s.get("special") == "anim" or not s.get("aux"):
        return None
    if s["fx"].startswith("tilt"):
        return dict(path=str(s["aux"][1]), x=0, y=0, w=W, h=H)
    return dict(path=str(s["aux"][0]), x=0, y=0, w=W + 2 * ox, h=H)


def _kit_obstacles(s, media, entries, ox, follow):
    """該鏡頭文字框(.boxes.json 全部行 + 出處標籤)的小件障礙物外框 [x, y, w, h]。
    follow = 畫布座標(含 text 組補邊 ox);否則換成成片座標(fx 全程 u = 0 / 0.5 / 1 掃過的外接框,小件不跟著動)。"""
    lay = s.get("layout")
    if not entries or not lay:
        return []
    boxes = [e["box"] for e in entries]
    lab = _label_ent(s, media, lay)
    if lab:
        boxes.append(lab["box"])
    if follow:
        return [KIT.to_canvas(b, lay["sc"], lay["pos"], ox) for b in boxes]
    fs = [fx_map(s["fx"], u, lay.get("zoom")) for u in (0.0, 0.5, 1.0)]
    out = []
    for b in boxes:
        c = KIT.to_canvas(b, lay["sc"], lay["pos"], 0.0)
        rs = [KIT.map_rect(c, f) for f in fs]
        x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
        out.append([x0, y0, max(r[0] + r[2] for r in rs) - x0, max(r[1] + r[3] for r in rs) - y0])
    return out


def plan_kits(shots, media):
    """每個有小件的鏡頭產 1-2 個圖層(跟隨 / 固定),擺放避開障礙物;回傳 (渲染工作清單, 警告)。存入 s["kit_layers"]。
    跟隨圖層 = 圖片類鏡頭裡 at.text / at.box 的小件,畫在畫布座標(text 組頁面左右各加 _zoom_pad 補邊),shot_cmd 套與底圖相同的 fx 濾鏡;
    固定圖層 = 影片片段、動畫鏡頭(at.el)、沒有 at 的 lower / pop / progress / badge,成片座標不變形。
    障礙物 = 文字框 + 出處標籤(圖片鏡頭)/ 圖表所有文字與色塊(動畫鏡頭,由 anim_web 量 DOM 後才擺)+ 字幕安全區 + 其他已放小件;
    有 el 目標或圖表障礙物的圖層在 anim_web 擺放(放不下的警告在渲染時印出),其餘在這裡就擺好(--check-only 也能預先警告)。"""
    work, warns = [], []
    for s in shots:
        s["kit_layers"] = []
        items = [it for it in s.get("kits") or [] if it["type"] != "punch"]
        if not items:
            continue
        img = s["kind"] == "image" and s.get("special") != "anim"
        ox = _zoom_pad(s) if img and _zoomish(s["fx"]) else 0
        entries = _load_boxes(media, s["img"]) if img and not s.get("special") else None
        a0 = s["parts"][-1]["anim"] if s.get("special") == "anim" else {}
        web_chart = a0.get("type") in AW.DATA_FN and a0.get("type") != "timeline" and anim_engine(a0) == "web"
        follow, screen, ids = [], [], []
        for it in items:
            at = it.get("at") or {}
            d = {k: v for k, v in it.items() if k not in ("at", "t0")}
            if "text" in at:
                b = KIT.find_text_rect(entries, at["text"]) if entries and s.get("layout") else None
                if b is None:
                    warns.append(f"句{it['line']} kit {it['type']} 找不到文字「{at['text']}」(只有截圖 / 閱讀卡的 .boxes.json 可用 text),略過")
                    continue
                d["rect"] = KIT.to_canvas(b, s["layout"]["sc"], s["layout"]["pos"], ox)
            elif "box" in at:
                d["rect"] = KIT.pct_rect(at["box"], (W, H), ox if img else 0)
            elif "el" in at:
                if not web_chart:
                    warns.append(f"句{it['line']} kit {it['type']} 的 at.el 只能用在網頁圖表鏡頭(timeline 除外),略過")
                    continue
                d["el"] = at["el"] if at["el"].startswith("#") else "#" + at["el"]
                ids.append(d["el"])
            (follow if img and ("text" in at or "box" in at) else screen).append(d)
        for layer, fol in ((follow, True), (screen, False)):
            if not layer:
                continue
            delay = round(min(d["t"] for d in layer) * FPS)
            for d in layer:
                d["t"] = round(d["t"] - delay / FPS, 4)
                if d["type"] == "arrow":          # 箭尾持續輕微浮動:圖層渲到鏡頭結束
                    d["hold"] = round(max(0.0, s["frames"] / FPS - delay / FPS - d["t"]), 3)
            x0 = ox if fol else 0
            base = _kit_base(s, ox) if any(d["type"] == "zoom" for d in layer) else None
            probe = None
            if web_chart and not fol:
                pj = AW.segment({k: v for k, v in s["parts"][-1]["anim"].items() if k != "step"}, n=1, icon_root=media / "anim")
                probe = dict(type=pj["type"], data=pj["data"], size=pj["size"], ids=ids, all=True)
            obs = _kit_obstacles(s, media, entries, ox, fol)
            job = KIT.job(layer, (W + 2 * x0, H), (x0, 0, x0 + W, H - IMG_BOTTOM_KEEP), base, probe, FPS, obs)
            warns += job["warns"]
            s["kit_layers"].append(dict(follow=fol, pad=x0, delay=delay, key=job["key"], pat=str(Path(job["dir"]) / "%04d.png"),
                                        boxes=[r["box"] for r in ((job.get("data") or {}).get("layout") or {}).get("records", [])]))
            work.append(job)
    return work, warns


def cap_push_for_kits(shots):
    """kit 離邊(2026-10-22 計畫 #5):小件圖層框(plan_kits 擺好的 boxes)在 push 推移(中心縮放)與 fx 動態全程後,
    離成片左右邊 >= TEXT_EDGE_X、離上緣 >= TEXT_EDGE_TOP;不足就把該鏡頭的 s["push"] 減小(同 _push_cap),低於 PUSH_MIN 就不推。回傳說明清單。"""
    notes, cx, cy = [], W / 2, H / 2
    for s in shots:
        if not s.get("push"):
            continue
        lay, cap = s.get("layout"), s["push"]
        maps = _fx_maps(s["fx"], lay.get("zoom")) if lay and s.get("fx") else [lambda x, y: (x, y)]
        for L in s.get("kit_layers") or []:
            for bx, by, bw, bh in L.get("boxes") or []:
                x0 = bx - L.get("pad", 0)
                pts = [m(x, y) for m in (maps if L.get("follow") else [lambda x, y: (x, y)]) for x in (x0, x0 + bw) for y in (by, by + bh)]
                if max(p[1] for p in pts) <= 0 or min(p[1] for p in pts) >= H:
                    continue
                xl, xr, yt = min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts)
                if xl < cx:
                    cap = min(cap, (cx - TEXT_EDGE_X) / (cx - xl))
                if xr > cx:
                    cap = min(cap, (cx - TEXT_EDGE_X) / (xr - cx))
                if cy > yt >= 0:
                    cap = min(cap, (cy - TEXT_EDGE_TOP) / (cy - yt))
        if cap < s["push"]:
            z = cap if cap >= PUSH_MIN else 0.0
            notes.append(f"{_line_span(s)}: 小件離邊限制,推移 {s['push']} → {round(z, 5) or '不推'}")
            s["push"] = round(z, 5) if z else 0.0
    return notes


def check_web_capacity(shots, tlmeta, media, portrait=False):
    """動畫容量(2026-10-22 計畫 #5):網頁渲染的動畫鏡頭以模板實際排版量測(anim_web.measure:播到底取 problems 與元素外框),
    文字太小(< 44px,出處 / 單位註記 < 30px)、元素超出安全區(左右 < 40、上 < 24、下進字幕安全帶)、文字框重疊、模板 problems 都列錯誤。
    量測在子行程跑,結果快取在 build\_anim_web\_measure;量測本身失敗只警告不擋。
    portrait=True(--portrait):AW.PORTRAIT_OK 的類型改以直式畫面窗 1080x1080 量(安全區左 80 / 右 140 / 上下 40),其餘型別維持橫式量測(直式會整張縮放)。"""
    jobs, meta = [], []
    for s in shots:
        if s.get("special") != "anim":
            continue
        a0 = s["parts"][0]["anim"]
        if anim_engine(a0) != "web" or a0["type"] not in AW.DATA_FN:
            continue
        try:
            if a0["type"] == "timeline":
                spec = tl_web_spec(a0, tlmeta, len(tl_meta(a0, tlmeta)["points"]) - 1)
                job = AW.segment(spec, spec["step"], spec["step"] + 1, n=1)
            else:
                job = AW.segment({k: v for k, v in a0.items() if k != "step"}, n=1, icon_root=media / "anim",
                                 size=(AL.PORTRAIT_SET["W"], AL.PORTRAIT_SET["H"]) if portrait and a0["type"] in AW.PORTRAIT_OK else None)
        except Exception as e:
            return [f"{_line_span(s)}: {a0['type']} 容量量測失敗 {e!r}"]
        jobs.append(job)
        meta.append(s)
    if not jobs:
        return []
    try:
        res = AW.measure(jobs)
    except Exception as e:
        log(f"警告: 動畫容量量測失敗,略過: {e!r}")
        return []
    return [f"{_line_span(s)}: {s['parts'][0]['anim']['type']} {m}" for s, r in zip(meta, res) for m in r["errors"] + r["problems"]]


def plan_kit_portrait(s, media):
    """直式原生動畫鏡頭(s["pwin"]["native"] == "anim")的小件圖層(計畫 #5c):1080x1080 畫面窗座標,可放區 = KIT.PORTRAIT_VIS(文字安全框),
    字幕在窗外所以不留字幕帶;at.el 以直式圖表頁量外框(同 plan_kits 的 probe,size 1080x1080),at.box = 窗內百分比,沒有 at 的 lower / pop / badge / progress 自由擺放。
    at.text 只有截圖 / 閱讀卡有(直式動畫沒有)略過並警告;timeline 的 el 不支援(同橫式)。回傳 (render 工作 或 None, 警告, 層資訊 或 None)。"""
    items = [it for it in s.get("kits") or [] if it["type"] != "punch"]
    if not items:
        return None, [], None
    a0 = s["parts"][-1]["anim"]
    web_chart = a0.get("type") in AW.DATA_FN and a0.get("type") != "timeline" and anim_engine(a0) == "web"
    layer, ids, warns = [], [], []
    for it in items:
        at = it.get("at") or {}
        d = {k: v for k, v in it.items() if k not in ("at", "t0")}
        if "text" in at:
            warns.append(f"句{it['line']} kit {it['type']} 的 at.text 只能用在截圖 / 閱讀卡,直式動畫略過")
            continue
        if "box" in at:
            d["rect"] = KIT.pct_rect(at["box"], (P_NAT, P_NAT), 0)
        elif "el" in at:
            if not web_chart:
                warns.append(f"句{it['line']} kit {it['type']} 的 at.el 只能用在網頁圖表鏡頭(timeline 除外),略過")
                continue
            d["el"] = at["el"] if at["el"].startswith("#") else "#" + at["el"]
            ids.append(d["el"])
        layer.append(d)
    if not layer:
        return None, warns, None
    delay = round(min(d["t"] for d in layer) * FPS)
    for d in layer:
        d["t"] = round(d["t"] - delay / FPS, 4)
        if d["type"] == "arrow":
            d["hold"] = round(max(0.0, s["frames"] / FPS - delay / FPS - d["t"]), 3)
    probe = None
    if web_chart:
        pj = AW.segment({k: v for k, v in a0.items() if k != "step"}, n=1, icon_root=media / "anim", size=(P_NAT, P_NAT))
        probe = dict(type=pj["type"], data=pj["data"], size=pj["size"], ids=ids, all=True)
    job = KIT.job(layer, (P_NAT, P_NAT), KIT.PORTRAIT_VIS, None, probe, FPS, [], portrait=True)
    warns += job["warns"]
    return job, warns, dict(pat=str(Path(job["dir"]) / "%04d.png"), delay=delay, key=job["key"])


def prep_kits(shots, media):
    """plan_kits 後把圖層交 anim_web 一次渲完。"""
    work, warns = plan_kits(shots, media)
    for m in warns:
        log(f"警告: {m}")
    if work:
        log(f"小件: {len(work)} 個圖層")
        AW.render(work)


def _punch_filter(times, push=0.0):
    """punch:整個鏡頭畫面以中心 1.0 -> PUNCH_SCALE -> 1.0(半個 sin,PUNCH_S 秒),多次相加。
    push > 1:再加鏡頭間輕推移(六項 D)——同一個中心縮放,前 PUSH_S 秒 1.0 -> push(ease-out 三次方),之後維持。"""
    pf = max(1, round(KIT.PUNCH_S * FPS))
    z = "(1" + "".join(f"+{KIT.PUNCH_SCALE - 1:.4f}*sin(PI*clip((on-{round(t * FPS)})/{pf},0,1))" for t in times)
    if push and push > 1:
        pp = max(1, round(PUSH_S * FPS))
        z += f"+{push - 1:.5f}*(1-pow(1-clip(on/{pp},0,1),3))"
    z += ")"

    def lo(a):
        return f"{a}/2-{a}/2*{z}"

    def hi(a):
        return f"{a}/2+{a}/2*{z}"
    return (f"perspective=x0='{lo('W')}':y0='{lo('H')}':x1='{hi('W')}':y1='{lo('H')}':x2='{lo('W')}':y2='{hi('H')}':"
            f"x3='{hi('W')}':y3='{hi('H')}':interpolation=cubic:sense=destination:eval=frame")


def shot_cmd(s, media, out_mp4, out_pcm):
    N = s["frames"]
    D = f"{N / FPS:.6f}"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    nin = 0
    cur = "b"  # 目前的底圖 label(疊重點標記後會換成 bhN)
    if s["kind"] == "video":
        cmd += ["-ss", f"{s['start']:.3f}", "-i", media / "raw" / f"{s['src']}.mp4"]
        nin = 1
        g = lift_gamma(s.get("luma"))
        vf = (f"[0:v]fps={FPS},{s['frame']['vf']},"
              f"setsar=1,{f'eq=gamma={g:.2f},' if g else ''}tpad=stop_mode=clone:stop={N},format=yuv420p[b]")
        has_a = s["has_audio"] and not s.get("mute")
    else:
        has_a = False
        fx = s["fx"]
        if _zoomish(fx):
            cmd += ["-loop", "1", "-framerate", str(FPS), "-i", s["aux"][0]]
            nin = 1
            vf = f"[0:v]{_zoom_filter(s, N)},setsar=1,format=yuv420p[b]"
        elif fx == "none" and s.get("tl_n"):  # 動畫鏡頭(不透明 mp4,格數與鏡頭相同;tpad 只是保險)
            cmd += ["-i", s["aux"][0]]
            nin = 1
            vf = f"[0:v]fps={FPS},scale={W}:{H},setsar=1,tpad=stop_mode=clone:stop={N},format=yuv420p[b]"
        elif fx == "none":
            cmd += ["-loop", "1", "-framerate", str(FPS), "-i", s["aux"][0]]
            nin = 1
            vf = "[0:v]setsar=1,format=yuv420p[b]"
        else:
            cmd += ["-loop", "1", "-framerate", str(FPS), "-i", s["aux"][0],
                    "-loop", "1", "-framerate", str(FPS), "-i", s["aux"][1]]
            nin = 2
            vf = f"[1:v]{_tilt_filter(fx, N)}[f];[0:v][f]overlay=0:0:format=auto,setsar=1,format=yuv420p[b]"
        for i, L in enumerate(s.get("hl_layers") or []):
            # 底線逐格 PNG 序列:先把第一格(全透明)停 t0 秒,最後一格延長到鏡頭結束,再走和前景同一個變形
            cmd += ["-framerate", str(FPS), "-i", L["pat"]]
            pre = f"format=rgba,loop=loop={round(L['t0'] * FPS)}:size=1:start=0,tpad=stop={N}:stop_mode=clone"
            if _zoomish(fx):
                pre += f",{_zoom_filter(s, N, pad_in=True)},format=rgba"
            elif fx.startswith("tilt"):
                pre += "," + _tilt_filter(fx, N)
            fade = "null"
            if L["t1"] is not None:
                fade = f"fade=t=out:st={L['t1']:.3f}:d={HL_UL_FADE_OUT}:alpha=1"
            vf += (f";[{nin}:v]{pre},{fade}[h{i}];[{cur}][h{i}]overlay=0:0:format=auto,format=yuv420p[bh{i}]")
            cur = f"bh{i}"
            nin += 1
    fx = s.get("fx") or ""
    for i, L in enumerate(s.get("kit_layers") or []):
        # 小件圖層(在 hl 底線之上、卡片與字幕之下):第一格停 delay 格、最後一格延長到鏡頭結束;
        # 跟隨圖層走與底圖相同的 fx(text 組先放大成 2x 補邊畫布再進 _zoom_filter;tilt 走 _tilt_filter)
        cmd += ["-framerate", str(FPS), "-start_number", "1", "-i", L["pat"]]
        pre = f"format=rgba,loop=loop={L['delay']}:size=1:start=0,tpad=stop={N}:stop_mode=clone"
        if L["follow"] and _zoomish(fx):
            pre += f",scale={(W + 2 * L['pad']) * 2}:{H * 2}:flags=bicubic,{_zoom_filter(s, N)},format=rgba"
        elif L["follow"] and fx.startswith("tilt"):
            pre += "," + _tilt_filter(fx, N)
        vf += f";[{nin}:v]{pre}[k{i}];[{cur}][k{i}]overlay=0:0:format=auto,format=yuv420p[bk{i}]"
        cur = f"bk{i}"
        nin += 1
    if s.get("punch") or s.get("push"):
        vf += f";[{cur}]{_punch_filter(s.get('punch') or [], s.get('push') or 0.0)},format=yuv420p[pu]"
        cur = "pu"
    silent_idx = None
    if not has_a:
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo"]
        silent_idx = nin
        nin += 1
    ain = f"[{silent_idx}:a]" if silent_idx is not None else "[0:a:0]"
    for ci, c in enumerate(s.get("cards") or []):  # 一個鏡頭可能先後疊兩張卡片(前一張的尾巴 + 下一張)
        cmd += ["-loop", "1", "-framerate", str(FPS), "-i", c["png"]]
        cidx = nin
        nin += 1
        pct = f"val*{CARD_DIM}"
        vf += (f";[{cur}]split[o{ci}][d{ci}];[d{ci}]boxblur=4:1,format=gbrp,lutrgb=r={pct}:g={pct}:b={pct},"
               f"format=yuv420p[dd{ci}];[dd{ci}][{cidx}:v]overlay=0:0:format=auto,format=yuva420p")
        if c["fin"]:
            vf += f",fade=t=in:st={c['t0']:.3f}:d={CARD_FADE}:alpha=1"
        if c["fout"]:
            vf += f",fade=t=out:st={max(0.0, c['t1'] - CARD_FADE):.3f}:d={CARD_FADE}:alpha=1"
        vf += f"[df{ci}];[o{ci}][df{ci}]overlay=0:0:format=auto,format=yuv420p[cd{ci}]"
        cur = f"cd{ci}"
    vf += f";[{cur}]null[v]"
    af = (f"{ain}aformat=sample_rates={SR}:channel_layouts=stereo,apad=whole_dur={D},"
          f"atrim=end={D},asplit=2[a1][a2]")
    cmd += ["-filter_complex", f"{vf};{af}",
            "-map", "[v]", "-map", "[a1]", "-frames:v", str(N), "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), "-ac", "2", "-f", "mp4", out_mp4,
            "-map", "[a2]", "-f", "s16le", "-acodec", "pcm_s16le", "-ar", str(SR), "-ac", "2", out_pcm]
    return cmd


def render_shot(s, media):
    mp4, pcm = s["file"], s["pcm"]
    part_mp4, part_pcm = mp4.with_suffix(".part.mp4"), pcm.with_suffix(".part.pcm")
    cmd = shot_cmd(s, media, part_mp4, part_pcm)
    if s["kind"] == "video":
        src = media / "raw" / f"{s['src']}.mp4"
    elif s.get("special"):  # quote / compare:沒有單一來源圖,簽章看產生的畫面 PNG
        src = Path(s["aux"][0])
    else:
        src = media / "images" / f"{s['img']}.png"
    extra = ([Path(p) for p in s.get("aux", [])] + [f for L in s.get("hl_layers") or [] for f in L["files"]]
             + [Path(c["png"]) for c in s.get("cards") or []])
    # 版面/底線參數(layout 的縮放與位置、底線常數)也算進簽章,避免吃到舊版快取
    lay = s.get("layout")
    params = [LAYOUT_VER, lay and [round(lay["sc"], 4), lay["pos"]], s.get("special"),
              [HL_UL_GAP, HL_UL_W, HL_UL_MINW, HL_UL_EXT, HL_UL_MINLEN, HL_UL_EDGE, HL_UL_DUR, HL_UL_TOTAL, HL_DELAY],
              [L["key"] for L in s.get("kit_layers") or []], s.get("punch"), KIT.PUNCH_S, KIT.PUNCH_SCALE]
    # 指令裡的路徑一律換成相對於素材根的寫法(P.rel),簽章不含絕對路徑
    key = sha1(json.dumps([P.rel(c) for c in cmd], ensure_ascii=False) + file_sig(src) + json.dumps(params)
               + "".join(hashlib.sha1(p.read_bytes()).hexdigest() for p in extra))
    keyf = mp4.with_suffix(".key")
    if mp4.exists() and pcm.exists() and keyf.exists() and keyf.read_text() == key:
        return
    run(cmd)
    part_mp4.replace(mp4)
    part_pcm.replace(pcm)
    keyf.write_text(key)


# ---------------------------------------------------------------- 音訊
def write_wav(path, chunks):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        for c in chunks:
            w.writeframes(c)


def build_voice(lines, total_frames, path):
    with ThreadPoolExecutor(4) as ex:
        pcms = list(ex.map(lambda l: run(["ffmpeg", "-v", "error", "-i", l["wav"], "-f", "s16le",
                                          "-ar", str(SR), "-ac", "2", "-"]), lines))
    buf = bytearray(total_frames * SPF * 4)
    for ln, pcm in zip(lines, pcms):
        off = round(ln["vstart"] * SR) * 4
        pcm = pcm[: max(0, len(buf) - off)]
        buf[off:off + len(pcm)] = pcm
    write_wav(path, [bytes(buf)])


VOICE_EQ_PRESETS = {
    # 配音略尖銳的細微修正:去齒音 -> 3.5kHz -2.5dB -> 8kHz 以上 -2dB -> 220Hz +1dB;最後 -0.2dB 讓整體響度與處理前相同(實測 +0.2 LU)
    "soft": ("deesser=i=0.4:f=0.5,equalizer=f=3500:t=q:w=1.2:g=-2.5,highshelf=f=8000:g=-2,"
             "equalizer=f=220:t=q:w=1:g=1,volume=-0.2dB"),
}


def voice_eq_filter(spec):
    """--voice-eq 的值 -> ffmpeg 濾鏡字串(空字串=不處理)。"""
    return VOICE_EQ_PRESETS.get(spec, spec) if spec else ""


BED_TARGET_DB = -46.0        # 素材原聲混入後的響度上限(dBFS RMS;每個影片鏡頭量它實際用到的那一段)
BED_BELOW_VOICE_DB = 24.0    # 原聲至少比配音低這麼多 dB(配音 = voice.wav 有聲部分的 RMS)
BED_BELOW_BGM_DB = 8.0       # 原聲至少比 BGM 低這麼多 dB(BGM = 乘上 --bgm-vol 之後、被配音壓低之前的 RMS)
BED_ACTIVE_DB = -50.0        # 量響度只算 50ms 區塊 RMS 高於此值的部分(略過停頓與無聲);整段都低於它 = 量不到聲音


def rms_db(pcm):
    """s16le 雙聲道 PCM 的有聲部分 RMS(dBFS);量不到聲音回傳 None。"""
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32768.0
    n = SR // 20 * 2
    if len(x) < n:
        return None
    pw = np.mean(x[: len(x) // n * n].reshape(-1, n) ** 2, axis=1)
    act = pw[pw > 10 ** (BED_ACTIVE_DB / 10)]
    return float(10 * np.log10(act.mean())) if len(act) else None


def track_db(path, seconds=None):
    """音檔(前 seconds 秒)的有聲部分 RMS(dBFS)。"""
    cmd = ["ffmpeg", "-v", "error"] + (["-t", f"{seconds:.3f}"] if seconds else []) + [
        "-i", path, "-vn", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-"]
    return rms_db(run(cmd))


def track_win_db(path, w=3.0):
    """音檔的 w 秒窗(不重疊)RMS(dBFS)分布:(p10, p50, p90, max);略過 < -60 dB 的靜音窗;量不到回 None。"""
    x = np.frombuffer(run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-"]),
                      dtype="<i2").astype(np.float64) / 32768.0     # 單聲道(與定案時量的數字可比)
    n = int(SR * w)
    if len(x) < n:
        return None
    pw = np.mean(x[: len(x) // n * n].reshape(-1, n) ** 2, axis=1)
    db = 10 * np.log10(np.maximum(pw, 1e-12))
    db = db[db >= -60.0]
    if not len(db):
        return None
    return tuple(float(v) for v in (*np.percentile(db, [10, 50, 90]), db.max()))


def bed_target(voice_db, bgm_db):
    """原聲的目標響度(dBFS RMS):BED_TARGET_DB、配音 - BED_BELOW_VOICE_DB、BGM - BED_BELOW_BGM_DB 三者取最低。"""
    return min([BED_TARGET_DB] + ([voice_db - BED_BELOW_VOICE_DB] if voice_db is not None else [])
               + ([bgm_db - BED_BELOW_BGM_DB] if bgm_db is not None else []))


def bed_gain(db, target, cap):
    """一個鏡頭的原聲增益:把量到的響度 db 壓到 target;不超過 cap(--bed,舊的固定增益),所以小聲的來源不會被放大。
    量不到聲音(db=None)用 cap。"""
    return cap if db is None else min(cap, 10 ** ((target - db) / 20))


def build_bed(shots, path, target, cap):
    """各鏡頭的原聲接成 bed.wav。固定增益會讓大聲的預告(Diablo IV)蓋過 BGM,所以每個影片鏡頭先量響度再各自調(bed_gain);
    增益已乘進 bed.wav,混音時不再調音量。回傳 [dict(n, src, db, gain, out_db)](只列影片鏡頭)。"""
    stats = []

    def gen():
        for s in shots:
            need = s["frames"] * SPF * 4
            data = s["pcm"].read_bytes()[:need]
            if s["kind"] == "video" and any(data):
                db = rms_db(data)
                g = bed_gain(db, target, cap)
                stats.append(dict(n=s["n"], src=s.get("src"), db=db and round(db, 1), gain=round(g, 4),
                                  out_db=db and round(db + 20 * math.log10(g), 1)))
                data = np.clip(np.frombuffer(data, dtype="<i2") * g, -32768, 32767).astype("<i2").tobytes()
            yield data + b"\0" * (need - len(data))
    write_wav(path, gen())
    return stats


# ---------------------------------------------------------------- QA
def make_qa(shots, bdir):
    tmp = bdir / "qa_tmp"
    tmp.mkdir(exist_ok=True)
    for old in bdir.glob("qa_*.jpg"):
        old.unlink()

    def grab(s):
        out = tmp / f"{s['n']:04d}.png"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{s['frames'] / FPS / 2:.3f}",
             "-i", s["file"], "-frames:v", "1", "-vf", "scale=320:180", out])
        return out

    with ThreadPoolExecutor(8) as ex:
        pngs = list(ex.map(grab, shots))
    font = ImageFont.truetype(FONT, 18, index=0)
    per, cols = 36, 6
    sheets = []
    for k in range(0, len(shots), per):
        chunk = list(zip(shots[k:k + per], pngs[k:k + per]))
        rows = math.ceil(len(chunk) / cols)
        sheet = Image.new("RGB", (cols * 320, rows * 180), (0, 0, 0))
        d = ImageDraw.Draw(sheet)
        for i, (s, p) in enumerate(chunk):
            x, y = (i % cols) * 320, (i // cols) * 180
            sheet.paste(Image.open(p).convert("RGB"), (x, y))
            label = f"{s['line']}-{s['j'] + 1}"
            d.rectangle([x, y, x + 12 + 11 * len(label), y + 24], fill=(0, 0, 0))
            d.text((x + 6, y + 2), label, font=font, fill=(255, 255, 0))
        out = bdir / f"qa_{k // per + 1:02d}.jpg"
        sheet.save(out, quality=88)
        sheets.append(out)
    shutil.rmtree(tmp, ignore_errors=True)
    return sheets


# ---------------------------------------------------------------- 渲染前檢查
def clauses_abs(ln):
    """子句在成片時間軸上的起訖秒與句後停頓(單句的行為 None);--tts-only 與 timeline.json 用。"""
    if not ln.get("clauses"):
        return None
    return [dict(text=c["text"], start=round(ln["vstart"] + c["start"], 3), end=round(ln["vstart"] + c["end"], 3), gap=c["gap"])
            for c in ln["clauses"]]


def load_timeline(lines, path):
    """--check-only:用既有 timeline.json 補上每句的時間(vstart/vend/dur/f0/f1),不跑 TTS。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tl = {t["idx"]: t for t in data["lines"]}
    for ln in lines:
        t = tl.get(ln["idx"])
        if t is None:
            sys.exit(f"timeline 缺句 {ln['idx']}")
        if t.get("text") is not None and t["text"] != ln["text"]:
            sys.exit(f"timeline 第 {ln['idx']} 句文字與 script 不同(文案改過,請先重跑 --tts-only)")
        ln["vstart"], ln["vend"], ln["dur"] = t["start"], t["end"], t["end"] - t["start"]
        ln["f0"], ln["f1"] = round(t["visual_start"] * FPS), round(t["visual_end"] * FPS)
    return data.get("total")


def _line_span(s):
    a, b = s["line"], s.get("last_line") or s["line"]
    return f"句{a}" if a == b else f"句{a}-{b}"


def precheck_images(shots, media):
    """每個圖片鏡頭算一次版面(存進 s["layout"]);回傳錯誤清單(hl 找不到、重點區過大)。"""
    errs = []
    for s in shots:
        if s["kind"] != "image" or s.get("special"):
            continue
        f = media / "images" / f"{s['img']}.png"
        if not f.exists():
            continue
        with Image.open(f) as im:
            size = im.size
        lay = s["layout"] = layout_image(s, media, size)
        if lay["too_big"]:
            errs.append(f"{_line_span(s)}: 重點區過大,請拆成兩張截圖({s['img']})")
        for ln_, kw, has_boxes in lay["missing"]:
            errs.append(f"句{ln_}: hl「{kw}」在 {s['img']} 找不到" + ("" if has_boxes else "(無 .boxes.json)"))
    return errs


def check_text_clip(shots, media):
    """截圖鏡頭的文字不可被畫面邊緣切到:用實際的版面(precheck_images 算好的 s["layout"])與 fx 參數,
    算每個文字框在動態起點到終點的成片座標(text_clip)。沒有 .boxes.json 的圖略過。
    數值存進 s["text_clip"](寫入 plan.json);回傳錯誤清單(句號、圖名、哪一邊、差幾 px)。"""
    errs = []
    for s in shots:
        lay = s.get("layout")
        ents = _load_boxes(media, s["img"]) if s["kind"] == "image" and not s.get("special") and lay else None
        if not ents:
            continue
        le = _label_ent(s, media, lay)  # 烤在圖上的出處標籤也不可被裁
        c = text_clip(ents + [le] if le else ents, lay["sc"], lay["pos"], s["fx"], lay.get("zoom"))
        s["text_clip"] = dict(fx=s["fx"], sc=round(lay["sc"], 4), pos=list(lay["pos"]), zoom_end=(lay.get("zoom") or [None])[0],
                         top=c["top"] and round(c["top"], 1), side=c["side"] and round(c["side"], 1), out_top=c["out"])
        for edge, px, txt in c["bad"]:
            errs.append(f"{_line_span(s)}: {s['img']} {edge}緣裁到文字「{txt}」,差 {px:.0f}px({s['fx']})")
    return errs


def _is_static(s):
    """底圖靜態的鏡頭(截圖、閱讀卡、引言卡、對比):圖片鏡頭且不是動畫鏡頭。"""
    return s["kind"] == "image" and s.get("special") != "anim"


def _push_cap(s, media):
    """該鏡頭在輕推移放大後,所有畫面內的文字框(含出處標籤)仍離左右邊 >= TEXT_EDGE_X、離上緣 >= TEXT_EDGE_TOP 的最大倍率
    (以畫面中心縮放;fx 動態全程 FX_U 取最壞,推移完成後維持,所以取全程)。沒有 .boxes.json 的鏡頭不限(回傳 PUSH_Z)。"""
    lay = s.get("layout")
    ents = _load_boxes(media, s["img"]) if not s.get("special") and lay else None
    if not ents:
        return PUSH_Z
    le = _label_ent(s, media, lay)
    sc, (px, py) = lay["sc"], lay["pos"]
    maps = _fx_maps(s["fx"], lay.get("zoom"))
    cap, cx, cy = PUSH_Z, W / 2, H / 2
    for e in ents + ([le] if le else []):
        x0, y0, x1, y1 = (px + e["box"][0] * sc, py + e["box"][1] * sc, px + e["box"][2] * sc, py + e["box"][3] * sc)
        pts = [m(x, y) for m in maps for x in (x0, x1) for y in (y0, y1)]
        if max(p[1] for p in pts) <= 0 or min(p[1] for p in pts) >= H:   # 整行在畫面上 / 下方之外:不受影響
            continue
        xl, xr, yt = min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts)
        if xl < cx:
            cap = min(cap, (cx - TEXT_EDGE_X) / (cx - xl))
        if xr > cx:
            cap = min(cap, (cx - TEXT_EDGE_X) / (xr - cx))
        if cy > yt >= 0:
            cap = min(cap, (cy - TEXT_EDGE_TOP) / (cy - yt))
    return cap


def plan_push(shots, lines, media, enabled=True):
    """鏡頭間 0.2 秒輕推移(2026-10-22 六項 D):只在「靜態 → 靜態」交界(前一個鏡頭與本鏡頭都是 _is_static),
    s["push"] = 終點倍率(0 = 不推)。--no-push(enabled=False)全關;該鏡頭任一句 push: false 關閉。
    文字離邊不足時自動把倍率減小到成立(_push_cap),低於 PUSH_MIN 就不推。回傳交界清單
    [(前句, 本句, 前種類, 本種類, 倍率, 原因)]。"""
    by_idx = {ln["idx"]: ln for ln in lines}
    out = []
    for i, s in enumerate(shots):
        s["push"] = 0.0
        if i == 0 or not (_is_static(s) and _is_static(shots[i - 1])):
            continue
        p = shots[i - 1]
        rng = [by_idx[k] for k in range(s["line"], (s.get("last_line") or s["line"]) + 1) if k in by_idx]
        note = ""
        if not enabled:
            z, note = 0.0, "--no-push"
        elif any(ln.get("push") is False for ln in rng):
            z, note = 0.0, "push:false"
        else:
            z = min(PUSH_Z, _push_cap(s, media))
            if z < PUSH_Z:
                note = f"文字離邊限制,減為 {z:.4f}"
            if z < PUSH_MIN:
                z, note = 0.0, note + "→不推"
        s["push"] = round(z, 5) if z else 0.0
        out.append((p.get("last_line") or p["line"], s["line"], f"{kind_name(p)}/{p.get('fx')}", f"{kind_name(s)}/{s.get('fx')}",
                    s["push"], note))
    return out


def check_text_pad(shots):
    """text 組(drift/zoom)截圖鏡頭動態全程會取樣到畫布外時,prep_image 自動把畫布左右補邊(A 法:圖邊色延伸),
    這裡驗補邊寬度在上限內(ZOOM_PAD_MAX,超過代表漂移量/倍率設定不合理,補不了才列錯誤);寬度存進 s["edge_pad"]。"""
    errs = []
    for s in shots:
        if s["kind"] != "image" or s.get("special") or not _zoomish(s["fx"]):
            continue
        pad = _zoom_pad(s)
        s["edge_pad"] = pad
        if pad > ZOOM_PAD_MAX:
            errs.append(f"{_line_span(s)}: {s['img']} {s['fx']} 動態會露出畫布外 {pad}px,超過補邊上限 {ZOOM_PAD_MAX}px")
    return errs


def check_image_runs(lines, img_min):
    """同一張圖(quote 的底圖、compare 的左右圖也算)連續出現:句數 <= IMG_MAX_UNITS、總長 <= IMG_MAX 秒。
    句數的算法:依序累加,滿 img_min 秒算 1 句(為了湊最短時長而併在一起的短句算 1 句),尾端不足的併入前一句。"""
    groups = []  # [共同圖片集合, [句]]
    for ln in lines:
        if ln.get("anim"):
            keys = set()
        elif ln.get("quote") or ln.get("compare"):
            keys = set(special_imgs(ln))
        else:
            keys = {ln["img"]} if ln.get("img") else set()
        if keys and groups and groups[-1][2] == ln["idx"] - 1 and groups[-1][0] & keys:
            groups[-1][0] &= keys
            groups[-1][1].append(ln)
            groups[-1][2] = ln["idx"]
        elif keys:
            groups.append([keys, [ln], ln["idx"]])
    errs = []
    for keys, ls, _ in groups:
        total = (ls[-1]["f1"] - ls[0]["f0"]) / FPS
        units, acc = 0, 0.0
        for ln in ls:
            acc += (ln["f1"] - ln["f0"]) / FPS
            if acc >= img_min:
                units, acc = units + 1, 0.0
        units = max(1, units)
        span = f"句{ls[0]['idx']}" + (f"-{ls[-1]['idx']}" if len(ls) > 1 else "")
        if units > IMG_MAX_UNITS:
            errs.append(f"{span}: 同圖({'/'.join(sorted(keys))})連續超過 {IMG_MAX_UNITS} 句(短句合併後仍有 {units} 句)")
        if total > IMG_MAX + 1e-6:
            errs.append(f"{span}: 同圖({'/'.join(sorted(keys))})連續 {total:.1f} 秒 > {IMG_MAX:.0f} 秒")
    return errs


def timing_only_check(lines, secs, tlmeta, args, media):
    """--check-only --timing-only:配音後的時長預檢,不需任何素材(圖、片段、clips 都可以不存在)。回傳錯誤數。
    保留:同圖連續(check_image_runs)、鏡頭最短時長與影片上限(check_durations)、動畫(check_anim:每步秒數 / 停留 / timeline 節點)、
    動畫容量(check_web_capacity,模板量測不讀素材)。
    跳過:缺畫面/缺片段(影片鏡頭不挑片段,只照 pick_videos 的規則等分,以標籤當占位)、亮度、文字裁切、硬切、小件擺放、字幕縫、卡片、轉場。"""
    shots, errs = layout_shots(lines)
    errors = [e for e in errs if "缺畫面" not in e]   # 缺畫面是素材/標註問題(lint 負責),不是時長問題
    stitch_min(shots, args.img_min)
    split, out = round(VIDEO_SPLIT * FPS), []
    for s in shots:   # 超過 VIDEO_SPLIT 的影片鏡頭等分(同 pick_videos 的基本段數)
        n = math.ceil(s["frames"] / split) if s["kind"] == "video" and not s.get("manual") else 1
        out += [s] if n <= 1 else [dict(s, j=j, f0=s["f0"] + s["frames"] * j // n,
                                         frames=s["frames"] * (j + 1) // n - s["frames"] * j // n) for j in range(n)]
    shots = out
    for n, s in enumerate(shots, 1):
        s["n"] = n
    errors += check_image_runs(lines, args.img_min)
    errs, _ = check_durations(shots, args.img_min)
    errors += errs
    del ANIM_WARNS[:]
    errors += check_anim(lines, shots, secs, tlmeta)
    warns = list(ANIM_WARNS)
    errors += check_web_capacity(shots, tlmeta, media, portrait=args.portrait)
    for m in warns:
        log(f"警告: {m}")
    for m in errors:
        log(f"錯誤: {m}")
    log(f"時長預檢(--timing-only,不看素材): 鏡頭 {len(shots)} 個 | 動畫鏡頭 {sum(1 for s in shots if s.get('special') == 'anim')} 個 | "
        f"警告 {len(warns)} | 錯誤 {len(errors)}")
    return len(errors)


def check_cuts(shots):
    """影片鏡頭內不可有離頭尾不到 VIDEO_MIN 秒的來源硬切(會變成一閃而過的畫面)。回傳 (錯誤, 有硬切資料的鏡頭數)。"""
    errs, n = [], 0
    for s in shots:
        if s["kind"] != "video" or s.get("missing") or "cuts" not in (s.get("clip") or {}):
            continue
        n += 1
        bad = cut_violations(s["clip"], s["start"], s["frames"] / FPS)
        if bad:
            errs.append(f"{_line_span(s)}: 影片鏡頭 {s['src']}@{s['start']:.2f}(長 {s['frames'] / FPS:.2f}s)內有離頭尾不到 "
                        f"{VIDEO_MIN} 秒的硬切: " + ", ".join(f"{c:.2f}" for c in bad))
    return errs, n


def check_durations(shots, img_min):
    """每個鏡頭的時長:低於最短時長、影片片段超過 VIDEO_MAX 都是錯誤;並印出時長分佈。"""
    errs, by = [], defaultdict(list)
    for s in shots:
        d, k = s["frames"] / FPS, kind_name(s)
        mn = shot_min_frames(s, img_min)
        by[k].append((d, s["frames"] < mn))
        if s["frames"] < mn:
            errs.append(f"{_line_span(s)}: {k}鏡頭 {d:.2f} 秒 < 最短 {mn / FPS:.1f} 秒")
        if s["kind"] == "video" and d > VIDEO_MAX + 1e-6:
            errs.append(f"{_line_span(s)}: 同一影片片段 {d:.2f} 秒 > {VIDEO_MAX:.0f} 秒")
    alld = [d for v in by.values() for d, _ in v]
    log(f"鏡頭時長: 共 {len(alld)} 個 | 最短 {min(alld):.2f} 秒 | 最長 {max(alld):.2f} 秒 | "
        f"低於最短時長 {sum(1 for v in by.values() for _, bad in v if bad)} 個")
    for k, v in by.items():
        ds = [d for d, _ in v]
        log(f"  {k}: {len(v)} 個,最短 {min(ds):.2f} / 最長 {max(ds):.2f} / 平均 {sum(ds) / len(ds):.2f} 秒,"
            f"低於門檻 {sum(1 for _, bad in v if bad)} 個")
    return errs, dict(n=len(alld), min=min(alld), max=max(alld))


CARD_BORROW = 0.3    # 卡片差不到這麼多秒就滿最短時長時,提早出現(向前一句借時間)補足


def plan_cards(lines, shots, card_min, total_frames):
    """卡片顯示區間:連續句子的卡片內容相同就是同一張(不重複淡入淡出);至少 card_min 秒,不足時延續到後面的鏡頭,
    下一張卡片開始時結束。卡片不可蓋到動畫 / quote / compare 鏡頭。回傳 (spans, errors);span = dict(card, line, f0, f1)。"""
    spans = []
    for ln in lines:
        if not ln.get("card"):
            continue
        if spans and spans[-1]["last"] == ln["idx"] - 1 and spans[-1]["card"] == ln["card"]:
            spans[-1].update(last=ln["idx"], end=ln["f1"])
        else:
            spans.append(dict(card=ln["card"], line=ln["idx"], last=ln["idx"], f0=ln["f0"], end=ln["f1"]))
    errs = []
    need = round(card_min * FPS)
    for i, sp in enumerate(spans):
        c1 = max(sp["end"], sp["f0"] + need)
        if i + 1 < len(spans):
            c1 = min(c1, spans[i + 1]["f0"])
        c1 = min(c1, total_frames)
        for s in shots:  # 不蓋到獨立畫面(動畫、引言、對比)
            if s.get("special") and sp["f0"] < s["f0"] + s["frames"] and s["f0"] < c1:
                if s["f0"] > sp["f0"]:
                    c1 = min(c1, s["f0"])
                else:
                    errs.append(f"句{sp['line']}: 卡片疊在{kind_name(s)}鏡頭上(卡片只能配影片或截圖)")
        sp["f1"] = c1
        lack = need - (c1 - sp["f0"])
        if 0 < lack < CARD_BORROW * FPS:  # 差一點:提早出現(向前一句借時間);借的那幾格不可落在獨立畫面或上一張卡片上
            f0 = sp["f0"] - lack
            if f0 >= (spans[i - 1]["f1"] if i else 0) and not any(
                    s.get("special") and s["f0"] < sp["f0"] and f0 < s["f0"] + s["frames"] for s in shots):
                log(f"卡片 句{sp['line']}: 只能顯示 {(c1 - sp['f0']) / FPS:.2f} 秒,提早 {lack / FPS:.2f} 秒出現,補足最短 {card_min:.1f} 秒")
                sp.update(f0=f0, early=lack)
        if c1 - sp["f0"] < need:
            errs.append(f"句{sp['line']}: 卡片只能顯示 {(c1 - sp['f0']) / FPS:.2f} 秒 < 最短 {card_min:.1f} 秒")
    return spans, errs


# ---------------------------------------------------------------- 動畫(一律是獨立鏡頭,自帶深色底;不疊在素材畫面上)
TL_SEG_S, TL_Q_S = 1.2, 2.0         # timeline 每個節點 / 問號的動畫秒數
TL_Q_POP_S = 0.4                    # 問號彈出的秒數(之後是原地跳動的循環)
EMO_ANIM_S = 2.0                    # emoji 一輪動作的秒數(彈入 + 主體循環)
PUZZLE_S, STAMP_S = 2.5, 0.6
ANIM_PAD = 0.5                      # emoji(原地循環)鏡頭至少要比動畫本身長這麼多秒
ANIM_HOLD = 1.5                     # 其餘動畫:最後一步完全顯示後到切鏡至少停留這麼多秒(不足時 build_timeline 補句後靜音)
ANIM_CENTER = (960, 430)            # 安全區(字幕帶以上)中央
EMO_SOLO = 420                      # 獨立鏡頭的 emoji 主體邊長(px)
TL_COLORS = ["#E53935", "#F2F2F2", "#B3001B", "#FFB74D", "#7AC8FF", "#9CCC65"]
ANIM_TYPES = ("timeline", "emoji", "puzzle", "stamp", "span", "bars", "list", "versus", "flow", "cols", "share", "num", "line", "table", "kpi")
LEVEL_TYPES = ("bars", "versus", "flow", "cols", "share", "num", "line", "table", "kpi")     # 有逐步模式(各句 step 對應「已顯示到第幾步」)的類型
ANIM_CACHE = P.BUILD / "_anim"
ANIM_BG = "none"                    # 動畫鏡頭的底:none = 純深色底(re9);star = 光點星座動態背景(--anim-bg)
TRANS_VALID = ("wipe", "title", "glitch", "none")
TRANS_MID = {"wipe": 0.25, "title": 0.65, "glitch": 0.175}  # 特效中點(秒);中點對齊段落交界
GLITCH_MAX = 2


WEB_ONLY_TYPES = ("line", "table", "kpi")     # 只有網頁模板、沒有 pillow 版的圖表(計畫 #3b)
ANIM_WARNS = []     # parse_anim 的警告(非錯誤);由檢查流程在 check_anim 後併入 warns
ANIM_ENGINES = ("web", "pillow")    # anim 的 engine 欄位:預設 web(anim_web 網頁模板);pillow = 舊 anim_lib(舊片重渲染用)
_WEB_FALLBACK = set()


def anim_engine(a):
    """這個 anim 實際用的渲染器:engine 省略 = web;web 但該類型還沒有網頁模板(或直式)時退回 pillow,每型印一次。"""
    if a.get("engine", "web") == "pillow":
        return "pillow"
    if not AW.has_template(a["type"], portrait=AL.PORTRAIT):      # 直式只有 AW.PORTRAIT_OK 的類型走網頁
        k = (a["type"], AL.PORTRAIT)
        if k not in _WEB_FALLBACK:
            _WEB_FALLBACK.add(k)
            print(f"[anim] {a['type']} 尚無{'直式' if AL.PORTRAIT else ''}網頁模板,改用 pillow")
        return "pillow"
    return "web"


def tl_meta(a, tlmeta):
    """這個 timeline anim 用的節點組:anim 自帶 points 就用它(question_between 也只看 anim 自己的),否則退回頂層 timeline。"""
    if isinstance(a, dict) and "points" in a:
        return {"points": a["points"], "question_between": a.get("question_between")}
    return tlmeta or {}


_DATE_RE = re.compile(r"^\s*(\d{4}([/\-.]\d{1,2}){0,2}|\d{1,2}/\d{1,2})\s*$")


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _parse_web_only(a, i, errs):
    """line / table / kpi(只有網頁版)的欄位檢查;通過回傳 a,否則記錯誤回傳 None。step:省略 = 一次播,"title" 或 0..n-1(line = 第 k 條線、table = 第 k 列、kpi = 第 k 格)。"""
    t, bad = a["type"], None
    ne = lambda v: isinstance(v, str) and v.strip()
    if anim_engine(a) != "web":
        errs.append(f"句{i}: anim {t} 只有網頁渲染(橫式、engine 預設 web),沒有 pillow 版;請移除 engine: pillow(直式只支援 anim_web.PORTRAIT_OK 的類型)")
        return None
    if not ne(a.get("title")):
        bad = "須有字串 title"
    elif "unit" in a and not isinstance(a["unit"], str):
        bad = "unit 須為字串"
    elif t == "line":
        xs, ls, pts = a.get("x"), a.get("lines"), a.get("points", [])
        names = [l.get("name") for l in ls] if isinstance(ls, list) and all(isinstance(l, dict) for l in ls) else []
        if not (isinstance(xs, list) and 2 <= len(xs) <= 24 and all((ne(x) or _is_num(x)) for x in xs)):
            bad = "須有 x(2–24 個類別或日期標籤)"
        elif not (isinstance(ls, list) and 1 <= len(ls) <= AW.LINE_MAX and len(names) == len(ls)):
            bad = f"須有 lines(1–{AW.LINE_MAX} 條)=[{{name?, data:[數字…]}}, ...];超過 {AW.LINE_MAX} 條請拆成兩張"
        elif not all(isinstance(l.get("data"), list) and len(l["data"]) == len(xs) and all(_is_num(v) for v in l["data"]) for l in ls):
            bad = f"每條線的 data 須為與 x 等長({len(xs)})的數字陣列"
        elif len(ls) > 1 and not all(ne(n) for n in names):
            bad = "多條線時每條都要有 name(圖例用)"
        elif a.get("scale") not in (None, "time"):
            bad = f"scale 只能省略或 \"time\",收到 {a.get('scale')!r}"
        elif a.get("scale") == "time" and not all(_DATE_RE.match(str(x)) for x in xs):
            bad = "scale:time 時 x 須為日期(YYYY、YYYY/M、YYYY/M/D)"
        elif not (isinstance(pts, list) and len(pts) <= 5 and all(
                isinstance(p, list) and len(p) == 2 and (ne(p[0]) or _is_num(p[0])) and ne(p[1]) and len(p[1]) <= 10 for p in pts)):
            bad = "points 須為最多 5 個 [x, 短標籤(≤10 字)]"
        elif a.get("scale") != "time" and not all(str(p[0]) in [str(x) for x in xs] for p in pts):
            bad = "類別 x 軸時,points 的 x 必須是 x 裡的標籤"
        elif a.get("scale") == "time" and not all(_DATE_RE.match(str(p[0])) for p in pts):
            bad = "scale:time 時 points 的 x 須為日期"
        elif any(k in a and not _is_num(a[k]) for k in ("ymin", "ymax")):
            bad = "ymin / ymax 須為數字"
        elif "area" in a and not isinstance(a["area"], bool):
            bad = "area 須為 true / false"
        elif "hi" in a and not ((isinstance(a["hi"], int) and not isinstance(a["hi"], bool) and 0 <= a["hi"] < len(ls)) or a["hi"] in names):
            bad = f"hi 須為線序號 0..{len(ls) - 1} 或線名稱"
        n = len(ls) if isinstance(ls, list) else 0
    elif t == "table":
        cols, rows, hi = a.get("cols"), a.get("rows"), a.get("hi")
        if not (isinstance(cols, list) and 1 <= len(cols) <= AW.TBL_COLS_MAX and all(ne(c) for c in cols)):
            bad = f"須有 cols(1–{AW.TBL_COLS_MAX} 個表頭字串,不含首欄項目名);超過請拆成兩張"
        elif not (isinstance(rows, list) and 1 <= len(rows) <= AW.TBL_ROWS_MAX):
            bad = f"須有 rows(1–{AW.TBL_ROWS_MAX} 列)=[[項目, 格…], ...];超過請拆成兩張"
        elif not all(isinstance(r, list) and len(r) == len(cols) + 1 and ne(r[0]) for r in rows):
            bad = f"每列須是 [項目名, 格…],格數與 cols 相同({len(cols)})"
        elif not all(isinstance(v, bool) or _is_num(v) or ne(v) for r in rows for v in r[1:]):
            bad = "格子須為 true / false(或 ✓ / ✗)、數字或短字串"
        elif "corner" in a and not isinstance(a["corner"], str):
            bad = "corner(首欄表頭)須為字串"
        elif hi is not None and not (isinstance(hi, dict) and len(hi) == 1 and (
                ("row" in hi and isinstance(hi["row"], int) and not isinstance(hi["row"], bool) and 0 <= hi["row"] < len(rows))
                or ("col" in hi and isinstance(hi["col"], int) and not isinstance(hi["col"], bool) and 0 <= hi["col"] < len(cols)))):
            bad = "hi 須為 {\"row\": 列序號} 或 {\"col\": 欄序號}(0 起算,只能二選一)"
        n = len(rows) if isinstance(rows, list) else 0
    else:
        cells, hi = a.get("cells"), a.get("hi")
        if not (isinstance(cells, list) and AW.KPI_MIN <= len(cells) <= AW.KPI_MAX and all(isinstance(c, dict) for c in cells)):
            bad = f"須有 cells({AW.KPI_MIN}–{AW.KPI_MAX} 格)=[{{label, value, unit?, delta?, better?, note?}}, ...]"
        elif not all(ne(c.get("label")) and (_is_num(c.get("value")) or ne(c.get("value"))) for c in cells):
            bad = "每格須有字串 label 與 value(數字或字串)"
        elif not all(all(k not in c or (isinstance(c[k], str)) for k in ("unit", "delta", "note")) for c in cells):
            bad = "每格的 unit / delta / note 須為字串"
        elif not all(c.get("better") in (None, "up", "down") for c in cells):
            bad = 'better 須為 "up"(預設,上升是好事)或 "down"(下降是好事,例如負評比例)'
        elif hi is not None and not (isinstance(hi, int) and not isinstance(hi, bool) and 0 <= hi < len(cells)):
            bad = f"hi 須為格序號 0..{len(cells) - 1}"
        n = len(cells) if isinstance(cells, list) else 0
    if bad:
        errs.append(f"句{i}: anim {t} {bad}")
        return None
    st = a.get("step")
    if "step" not in a or st == "title" or (isinstance(st, int) and not isinstance(st, bool) and 0 <= st < n):
        return a
    unit = {"line": "條線", "table": "列", "kpi": "格"}[t]
    errs.append(f"句{i}: anim {t} step 錯誤: {st!r}(省略 = 一次播;逐步須為 \"title\" 或 0..{n - 1},step k = 顯示到第 k {unit})")
    return None


def _ref_ok(r):
    return isinstance(r, dict) and _is_num(r.get("value")) and isinstance(r.get("label"), str) and r["label"].strip() != ""


def _shock_bad(a, its):
    """bars / cols 的 shock(軸暴衝)選項檢查:true = 數值最大的一項、整數 = 指定項;單系列、無 stack / ref / 負值,
    暴衝項須 >= 其他項最大值的 AW.SHOCK_RATIO 倍(否則不是「遠大於」,重縮放只會讓畫面怪)。沒問題回傳 None。"""
    s = a.get("shock")
    if s is None or s is False:
        return None
    ok = isinstance(its, list) and its and all(isinstance(x, list) and len(x) >= 2 for x in its)
    n = len(its) if ok else 0
    if not (s is True or (isinstance(s, int) and not isinstance(s, bool) and 0 <= s < n)):
        return f"shock 須為 true(數值最大的一項)或項序號 0..{max(n - 1, 0)}"
    if a.get("series") or a.get("stack") or "ref" in a:
        return "shock(軸暴衝)只支援單系列,不可搭 series / stack / ref"
    vals = [x[1] for x in its]
    if not all(_is_num(v) and v >= 0 for v in vals):
        return "shock(軸暴衝)的數值須為非負數字(單系列)"
    j = vals.index(max(vals)) if s is True else s
    others = [v for k, v in enumerate(vals) if k != j]
    if not others or max(others) <= 0 or vals[j] < AW.SHOCK_RATIO * max(others):
        return f"shock 項的數值須 >= 其他項最大值的 {AW.SHOCK_RATIO:g} 倍(目前 {vals[j]:g} vs {max(others, default=0):g};差距不夠大就不要開軸暴衝)"
    return None


def _chart_ext(a, i, errs, t, its):
    """bars / cols 共用的新欄位檢查(計畫 #3c):stack 需要 series 且不可有負值、ref = {value, label}、負值;新欄位只有網頁渲染支援。回傳 False = 已記錯誤。"""
    ser, bad = a.get("series"), None
    flat = []
    for x in (its if isinstance(its, list) else []):
        if isinstance(x, list) and len(x) >= 2:
            flat += x[1] if isinstance(x[1], list) else [x[1]]
    neg = any(_is_num(v) and v < 0 for v in flat)
    if "stack" in a and not isinstance(a["stack"], bool):
        bad = "stack 須為 true / false"
    elif a.get("stack") and not ser:
        bad = "stack:true 需要 series(2–3 個系列名稱,每項數值為各系列數值陣列)"
    elif a.get("stack") and neg:
        bad = "堆疊(stack)不支援負值;要正負分歧請去掉 stack"
    elif "ref" in a and not _ref_ok(a["ref"]):
        bad = 'ref 須為 {"value": 數字, "label": 非空字串}(例 {"value": 80, "label": "80% 門檻"})'
    elif anim_engine(a) != "web" and (a.get("stack") or "ref" in a or neg or a.get("shock")):
        bad = "stack / ref / 負值 / shock 只有網頁渲染支援,請移除 engine: pillow"
    else:
        bad = _shock_bad(a, its)
    if bad:
        errs.append(f"句{i}: anim {t} {bad}")
    return not bad


def parse_anim(ln, tlmeta, errs):
    """檢查一句的 anim 欄位;有錯就記進 errs 並回傳 None。"""
    a = ln.get("anim")
    if a is None:
        return None
    t = a.get("type") if isinstance(a, dict) else None
    i = ln["idx"]
    if isinstance(a, dict) and "src" in a and not (isinstance(a["src"], str) and a["src"].strip()):
        errs.append(f"句{i}: anim src 須為非空字串(右下角出處小字),收到 {a['src']!r}")
        return None
    if isinstance(a, dict) and a.get("engine", "web") not in ANIM_ENGINES:
        errs.append(f"句{i}: anim engine 須為 {'/'.join(ANIM_ENGINES)},收到 {a['engine']!r}")
        return None
    if t == "timeline":
        step = a.get("step")
        tm = tl_meta(a, tlmeta)
        pts = tm.get("points")
        if "points" in a and not (isinstance(pts, list) and pts and all(
                isinstance(x, list) and len(x) >= 2 and isinstance(x[0], str) and isinstance(x[1], str) for x in pts)):
            errs.append(f"句{i}: anim timeline points 須為 [[日期, 說明], ...] 非空陣列")
        elif not pts:
            errs.append(f"句{i}: anim timeline 但沒有 points(anim 自帶 points 或 script 頂層 timeline.points)")
        elif step == "q":
            if tm.get("question_between"):
                return a
            errs.append(f"句{i}: anim timeline step 'q' 但 timeline 沒有 question_between")
        elif isinstance(step, int) and not isinstance(step, bool) and 0 <= step < len(pts):
            return a
        else:
            errs.append(f"句{i}: anim timeline step 錯誤: {step!r}(須為 0..{len(pts) - 1} 或 'q')")
    elif t in WEB_ONLY_TYPES:
        return _parse_web_only(a, i, errs)
    elif t == "emoji":
        if a.get("name") in AL.EMOJI:
            return a
        errs.append(f"句{i}: anim emoji 名稱不存在: {a.get('name')!r}(可用: {'/'.join(AL.EMOJI)})")
    elif t == "puzzle":
        return a
    elif t == "stamp":
        if isinstance(a.get("text"), str) and a["text"].strip():
            return a
        errs.append(f"句{i}: anim stamp 缺 text")
    elif t == "span":
        if all(isinstance(a.get(k), str) and a[k].strip() for k in ("from", "to", "big")) and \
                isinstance(a.get("ticks", 8), int) and a.get("ticks", 8) >= 0:
            return a
        errs.append(f"句{i}: anim span 須有字串 from / to / big(ticks 為非負整數,可省略)")
    elif t == "bars":
        its = bars_flat(a)
        ser = a.get("series")
        if ser is not None:
            if not (isinstance(ser, list) and 2 <= len(ser) <= AW.SERIES_MAX and all(isinstance(x, str) for x in ser)):
                errs.append(f"句{i}: anim bars series 須為 2..{AW.SERIES_MAX} 個系列名稱字串")
                return None
            if anim_engine(a) != "web":
                errs.append(f"句{i}: anim bars series(多系列)只有 engine web 支援")
                return None

        web = anim_engine(a) == "web"
        if not _chart_ext(a, i, errs, "bars", its):
            return None

        def num_ok(v):      # 網頁版允許 0 與負值(以 0 為中線分歧);pillow 版仍須為正數
            return _is_num(v) and (web or v > 0)

        def vals_ok(v):     # 多系列:[v1, v2…] 與 series 等長,缺值 null,至少一個有值
            if ser is None:
                return num_ok(v)
            return isinstance(v, list) and len(v) == len(ser) and any(x is not None for x in v) \
                and all(x is None or num_ok(x) for x in v)
        if isinstance(a.get("title"), str) and isinstance(its, list) and its and all(
                isinstance(x, list) and len(x) >= 2 and isinstance(x[0], str) and vals_ok(x[1])
                and (len(x) < 4 or (isinstance(x[3], dict) and all(isinstance(v, bool) if k == "hi" else isinstance(v, str) for k, v in x[3].items())))
                for x in its):
            st = a.get("step")
            if web and len(its) > AW.BARS_MAX:
                errs.append(f"句{i}: anim bars 有 {len(its)} 條,網頁版最多 {AW.BARS_MAX} 條,請拆成兩張")
                return None
            if "step" not in a or st == "title" or (isinstance(st, int) and not isinstance(st, bool) and 0 <= st < len(its)):
                return a
            errs.append(f"句{i}: anim bars step 錯誤: {st!r}(省略 = 整組一次播;逐步模式須為 \"title\" 或 0..{len(its) - 1},"
                        f"step k = 顯示第 0..k 條)")
            return None
        errs.append(f"句{i}: anim bars 須有 title 與 items=[[標籤, 正數, 單位, {{color?, icon?}}?], ...],"
                    f"或 groups=[{{title, bars:[同 items]}}, ...](組標題為字串)")
    elif t == "list":
        its, step = a.get("items"), a.get("step", "all")
        if not (isinstance(a.get("title"), str) and isinstance(its, list) and its and all(isinstance(x, str) for x in its)):
            errs.append(f"句{i}: anim list 須有 title 與字串陣列 items")
        elif step == "all" or (isinstance(step, int) and not isinstance(step, bool) and 0 <= step < len(its)):
            if len(its) > AL.LIST_MAX_ITEMS:
                w = f"句{i}: anim list 有 {len(its)} 項(超過 {AL.LIST_MAX_ITEMS} 項太擠,建議拆成兩張)"
                if w not in ANIM_WARNS:
                    ANIM_WARNS.append(w)
            return a
        else:
            errs.append(f"句{i}: anim list step 錯誤: {step!r}(須為 0..{len(its) - 1} 或 \"all\")")
    elif t == "versus":
        step = a.get("step")
        sides = [a.get(k) for k in ("left", "right")]
        if not (isinstance(a.get("title"), str) and all(
                isinstance(sd, dict) and isinstance(sd.get("head"), str) and isinstance(sd.get("lines"), list)
                and 1 <= len(sd["lines"]) <= 2 and all(isinstance(x, str) and x for x in sd["lines"])
                and sd.get("mark") in (None, "yes", "no") for sd in sides)):
            errs.append(f"句{i}: anim versus 須有 title、left / right = {{head, lines(1..2 個字串), mark?(yes/no)}}")
        elif isinstance(step, int) and not isinstance(step, bool) and 0 <= step <= 2:
            return a
        else:
            errs.append(f"句{i}: anim versus step 錯誤: {step!r}(須為 0 / 1 / 2:標題欄標題 / 左欄 / 右欄)")
    elif t == "flow":
        step, nodes = a.get("step"), a.get("nodes")
        if not (isinstance(a.get("title"), str) and isinstance(nodes, list) and 2 <= len(nodes) <= 4
                and all(isinstance(x, str) and x for x in nodes)):
            errs.append(f"句{i}: anim flow 須有 title 與 nodes(2..4 個字串,3 個為標準)")
        elif isinstance(step, int) and not isinstance(step, bool) and 0 <= step < len(nodes):
            return a
        else:
            errs.append(f"句{i}: anim flow step 錯誤: {step!r}(須為 0..{len(nodes) - 1},step n = 顯示到第 n 個節點)")
    elif t == "cols":
        its, st, ser, web = a.get("items"), a.get("step"), a.get("series"), anim_engine(a) == "web"
        if ser is not None and not (isinstance(ser, list) and 2 <= len(ser) <= AW.SERIES_MAX and all(isinstance(x, str) and x.strip() for x in ser)):
            errs.append(f"句{i}: anim cols series 須為 2..{AW.SERIES_MAX} 個系列名稱字串")
            return None
        if ser is not None and not web:
            errs.append(f"句{i}: anim cols series(多系列)只有 engine web 支援")
            return None
        if not _chart_ext(a, i, errs, "cols", its):
            return None

        def v_ok(v):        # 單系列:數字(web 允許 0 / 負值,pillow 須為正);多系列:與 series 等長的陣列,缺值 null,至少一個有值
            if ser is None:
                return _is_num(v) and (web or v > 0)
            return isinstance(v, list) and len(v) == len(ser) and any(x is not None for x in v) and all(x is None or _is_num(x) for x in v)
        mx = AW.COLS_MAX if web else AL.COLS_MAX
        if not (isinstance(a.get("title"), str) and isinstance(its, list) and 2 <= len(its) <= mx and all(
                isinstance(x, list) and len(x) >= 2 and isinstance(x[0], str) and v_ok(x[1]) and (len(x) < 3 or isinstance(x[2], str))
                and (len(x) < 4 or (isinstance(x[3], dict) and all(isinstance(v, bool) for v in x[3].values()))) for x in its)):
            errs.append(f"句{i}: anim cols 須有 title 與 items(2–{mx} 根)=[[標籤, 數值, 單位?, {{hi?: true/false}}?], ...];有 series 時數值為各系列的數值陣列(缺值 null)")
        elif "step" not in a or st == "title" or (isinstance(st, int) and not isinstance(st, bool) and 0 <= st < len(its)):
            return a
        else:
            errs.append(f"句{i}: anim cols step 錯誤: {st!r}(省略 = 一次播;逐步須為 \"title\" 或 0..{len(its) - 1},step k = 顯示第 0..k 根)")
    elif t == "share":
        rows, st = a.get("rows"), a.get("step")
        bad = None
        if not (isinstance(a.get("title"), str) and isinstance(rows, list) and 1 <= len(rows) <= 4):
            bad = "須有 title 與 rows(1–4 列)=[{label, parts:[[名稱, 數值, 顏色?], ...]}, ...]"
        elif "unit" in a and not isinstance(a["unit"], str):
            bad = "unit 須為字串"
        elif "style" in a and a["style"] not in ("bar", "donut"):
            bad = f"style 須為 \"bar\"(100% 堆疊條,預設)或 \"donut\"(甜甜圈),收到 {a['style']!r}"
        elif "style" in a and anim_engine(a) != "web":
            bad = "style 只有網頁渲染支援,請移除 engine: pillow"
        elif a.get("style") == "donut" and len(rows) != 1:
            bad = f"style:donut 只限單列(收到 {len(rows)} 列);多列請用 style:bar 或拆成多張"
        else:
            for ri, r in enumerate(rows):
                ps = r.get("parts") if isinstance(r, dict) else None
                if not (isinstance(r, dict) and isinstance(r.get("label"), str) and isinstance(ps, list) and 2 <= len(ps) <= 4 and all(
                        isinstance(x, list) and len(x) >= 2 and isinstance(x[0], str) and isinstance(x[1], (int, float))
                        and not isinstance(x[1], bool) and x[1] > 0 and (len(x) < 3 or x[2] is None or isinstance(x[2], str)) for x in ps)):
                    bad = f"第 {ri + 1} 列須有 label 與 parts(2–4 段,每段 [名稱, 正數, 顏色?])"
                    break
                tot = sum(x[1] for x in ps)
                if not 99 <= tot <= 101:
                    bad = f"第 {ri + 1} 列數值總和須在 99–101 之間(收到 {tot:g})"
                    break
                try:
                    for x in ps:
                        if len(x) > 2 and x[2]:
                            AL._bar_color(x[2], None)
                except Exception:
                    bad = f"第 {ri + 1} 列顏色錯誤(可用 {'/'.join(AL.BAR_COLORS)} 或色碼)"
                    break
        if bad:
            errs.append(f"句{i}: anim share {bad}")
        elif "step" not in a or st == "title" or (isinstance(st, int) and not isinstance(st, bool) and 0 <= st < len(rows)):
            return a
        else:
            errs.append(f"句{i}: anim share step 錯誤: {st!r}(省略 = 一次播;逐步須為 \"title\" 或 0..{len(rows) - 1},step k = 顯示到第 k 列)")
    elif t == "num":
        st, cmp_ = a.get("step"), a.get("compare")
        if not (isinstance(a.get("big"), str) and a["big"].strip()):
            errs.append(f"句{i}: anim num 須有字串 big(label / compare / tone / step 可省略)")
        elif a.get("label") is not None and not isinstance(a["label"], str):
            errs.append(f"句{i}: anim num label 若有須為字串(可省略或空字串 = 不畫頂端 label)")
        elif cmp_ is not None and not (isinstance(cmp_, str) and cmp_.strip()):
            errs.append(f"句{i}: anim num compare 須為非空字串")
        elif a.get("tone") not in (None, "up", "down", "none"):
            errs.append(f"句{i}: anim num tone 須為 up / down / none: {a.get('tone')!r}")
        elif "step" in a and (isinstance(st, bool) or st not in (0, 1) or (st == 1 and not cmp_)):
            errs.append(f"句{i}: anim num step 錯誤: {st!r}(省略 = 依序播完;0 = 只有 label 與 big;1 = compare 出現,須有 compare)")
        else:
            return a
    else:
        errs.append(f"句{i}: anim 類型錯誤: {t!r}(可用 {'/'.join(ANIM_TYPES)})")
    return None


def _list_stepped(a):
    return a["type"] == "list" and a.get("step", "all") != "all"


def bars_flat(a):
    """bars 的所有條(跨組依序,step 的編號就是這個順序)。有 groups 時由 groups 展開;格式不對回傳 None。"""
    gs = a.get("groups")
    if gs is None:
        return a.get("items")
    if not (isinstance(gs, list) and gs and all(isinstance(g, dict) and isinstance(g.get("title"), str)
                                                and isinstance(g.get("bars"), list) and g["bars"] for g in gs)):
        return None
    return [b for g in gs for b in g["bars"]]


def _level_stepped(a):
    """逐步顯示的類型(bars 逐步模式 / versus / flow):各句的 step 對應一個「已顯示到第幾步」(level),動畫由前一句的 level 播到這句的。"""
    return a["type"] in LEVEL_TYPES and "step" in a


def anim_level(a):
    """這一句結束時的 level:bars = 條數("title" = 0)、versus = step(0 標題 / 1 左 / 2 右)、flow = 節點數。"""
    st = a["step"]
    if a["type"] == "versus":
        return st
    return 0 if st == "title" else st + 1


def level_seconds(a, prev, shown):
    """逐步類型一段動畫(prev -> shown)的長度(秒)。"""
    if a["type"] == "num":
        return AL.num_step_seconds(prev, shown, a["big"])
    if a["type"] in WEB_ONLY_TYPES:
        return AW.new_step_seconds(a, prev, shown)
    return {"bars": AL.bars_step_seconds, "versus": AL.versus_step_seconds, "flow": AL.flow_step_seconds,
            "cols": AL.cols_step_seconds, "share": AL.share_step_seconds}[a["type"]](prev, shown) + AW.shock_extra(a, prev, shown)


def level_plan(parts):
    """逐步各句的 (prev, shown, first):shown = 這句結束時的 level,prev = 動畫起點已到的 level;
    與前一句同 step 的後續句凍結(first=False,prev=shown)。"""
    plan, last = [], 0
    for i, p in enumerate(parts):
        st = p["anim"]["step"]
        shown = anim_level(p["anim"])
        first = i == 0 or parts[i - 1]["anim"]["step"] != st
        plan.append((last if first else shown, shown, first))
        last = shown
    return plan


def anim_finish(items):
    """一個動畫鏡頭(連續句合併後)「最後一步完全顯示」的時間(秒,從鏡頭開頭算)。
    items = [{"anim": …, "t0": 該句開頭離鏡頭開頭的秒數}, …]。每一步都在該句開頭開始出現,
    所以 = 最後一個「出現動畫的句子」的開頭 + 該步動畫長度。同時回傳需要的停留秒數 (finish, hold)。"""
    a0 = items[0]["anim"]
    t = a0["type"]
    if t == "timeline":
        last = items[-1]
        return last["t0"] + ((TL_Q_POP_S + 0.3) if last["anim"].get("step") == "q" else TL_SEG_S), ANIM_HOLD
    if _list_stepped(a0):
        fin = 0.0
        for it, first in zip(items, list_firsts(items)):
            if first:
                fin = it["t0"] + anim_seconds(it["anim"])
        return fin, ANIM_HOLD
    if _level_stepped(a0):
        fin = 0.0
        for it, (prev, shown, first) in zip(items, level_plan(items)):
            if first:
                fin = it["t0"] + level_seconds(a0, prev, shown) - (AL.STEP_TAIL_S if shown > prev else 0.0)
        return fin, ANIM_HOLD
    return anim_seconds(a0), (ANIM_PAD if t == "emoji" else ANIM_HOLD)


def list_firsts(parts):
    """stepped list 的各句:是否為該 step 的第一句(第一句播出現動畫,同 step 的後續句凍結)。"""
    return [i == 0 or parts[i - 1]["anim"].get("step") != p["anim"].get("step") for i, p in enumerate(parts)]


def list_plan(parts):
    """stepped list 的各句 (prev, shown, first)(網頁渲染用,同 level_plan 的形狀):step k = 第 k 項彈出,prev = k、shown = k + 1;
    與前一句同 step 的後續句凍結(prev = shown)。"""
    out = []
    for p, first in zip(parts, list_firsts(parts)):
        k = p["anim"]["step"]
        out.append((k if first else k + 1, k + 1, first))
    return out


def anim_seconds(a):
    """這段動畫本身的長度(秒)。"""
    t = a["type"]
    if t == "timeline":
        return TL_Q_S if a.get("step") == "q" else TL_SEG_S
    if t == "list":
        return AL.list_seconds(len(a["items"]), bool(a.get("note")), a.get("step", "all"))
    if t == "cols":
        return AL.cols_step_seconds(0, len(a["items"])) + AW.shock_extra(a)
    if t == "share":
        return AL.share_step_seconds(0, len(a["rows"]))
    if t == "num":
        return AL.num_step_seconds(0, 2 if a.get("compare") else 1, a["big"])
    if t in WEB_ONLY_TYPES:
        return AW.new_step_seconds(a, 0, AW.new_levels(a))
    return {"emoji": EMO_ANIM_S, "puzzle": PUZZLE_S, "stamp": STAMP_S, "span": AL.SPAN_S, "bars": AL.BARS_S}[t] + (AW.shock_extra(a) if t == "bars" else 0)


def _check_src(a, s, tlmeta=None):
    """動畫版面檢查:bars 的 src 出處小字與各文字墨跡框重疊、排不下(有 src 時最後一條下緣上限 AL.BARS_BOTTOM_SRC);
    timeline / span / list / versus / flow 用 AL.anim_problems(內容下緣 <= 800,有 src 時 <= 768;左右離邊 >= 96)。"""
    if a["type"] in ("timeline", "span", "list", "versus", "flow", "cols", "share", "num") and not (
            a["type"] in ("cols", "share") and anim_engine(a) == "web"):      # cols / share 的網頁模板自行縮放排版,pillow 版面檢查只用於 engine pillow
        try:
            probs = AL.anim_problems(a, tl_meta(a, tlmeta).get("points"))
        except (KeyError, TypeError, ValueError) as e:
            probs = [f"版面計算失敗 {e!r}"]
        return [f"{_line_span(s)}: {a['type']} {m}" for m in probs]
    if a["type"] != "bars" or anim_engine(a) == "web":     # 網頁模板自行縮放排版;容量檢查待派工 #5
        return []
    try:
        lay = AL._BarsLayout(a.get("items"), a.get("groups"), None, a.get("src"))
    except ValueError as e:
        return [f"{_line_span(s)}: bars {e}" + ("(有 src 時下緣上限 752)" if a.get("src") else "")]
    if not a.get("src"):
        return []
    sb = AL.src_place(a["src"])[2]
    boxes = [(f"{nm}{k}", lay.place(k)[nm][1]) for k in range(lay.n) for nm in ("label", "val")]
    boxes += [(f"組標題{g}", lay.group_place(g)[1]) for g in range(len(lay.gspr))]
    hit = [n for n, b in boxes if b[0] < sb[2] and sb[0] < b[2] and b[1] < sb[3] and sb[1] < b[3]]
    return [f"{_line_span(s)}: bars 的 src 出處小字與 {'、'.join(hit)} 重疊"] if hit else []


def check_anim(lines, shots, secs, tlmeta):
    """動畫與轉場的檢查,回傳錯誤清單:emo 欄位已停用;anim 規格;動畫鏡頭(連續句合併後)的最後一步完全顯示後至少停留 ANIM_HOLD 秒(emoji 為 ANIM_PAD),
    且 timeline 每個節點的動畫要在自己那一句內播完(不加速、不截斷)。"""
    errs = []
    bad = set()
    for ln in lines:
        if ln.get("emo") is not None:
            errs.append(f"句{ln['idx']}: emo 欄位已停用(動畫不可疊在素材畫面上;要用表情請改成 anim {{\"type\":\"emoji\"}} 獨立鏡頭)")
        if ln.get("anim") is not None and parse_anim(ln, tlmeta, errs) is None:
            bad.add(ln["idx"])
    for sec in secs:
        tr = sec.get("trans", "none")
        if tr not in TRANS_VALID:
            errs.append(f"段落「{sec.get('name', '')}」trans 值錯誤: {tr!r}(可用 {'/'.join(TRANS_VALID)})")
    for s in shots:
        if s.get("special") != "anim" or any(p["line"] in bad for p in s["parts"]):
            continue
        d = s["frames"] / FPS
        a0 = s["parts"][0]["anim"]
        if a0["type"] == "timeline":
            for p in s["parts"]:
                q = p["anim"].get("step") == "q"
                lim = (TL_Q_POP_S + 0.3) if q else TL_SEG_S
                if p["frames"] < round(lim * FPS):
                    errs.append(f"句{p['line']}: timeline {'問號' if q else '節點'}動畫需要 {lim:.1f} 秒,該句只有 "
                                f"{p['frames'] / FPS:.2f} 秒(不可加速或截斷)")
        elif _list_stepped(a0):
            for p, first in zip(s["parts"], list_firsts(s["parts"])):
                lim = anim_seconds(p["anim"])
                if first and p["frames"] < round(lim * FPS):
                    errs.append(f"句{p['line']}: list 第 {p['anim']['step'] + 1} 項動畫需要 {lim:.1f} 秒,該句只有 "
                                f"{p['frames'] / FPS:.2f} 秒(不可加速或截斷)")
        elif _level_stepped(a0):
            for p, (prev, shown, first) in zip(s["parts"], level_plan(s["parts"])):
                lim = level_seconds(a0, prev, shown)
                if first and p["frames"] < round(lim * FPS):
                    errs.append(f"句{p['line']}: {a0['type']} step {p['anim']['step']!r} 動畫需要 {lim:.1f} 秒,該句只有 "
                                f"{p['frames'] / FPS:.2f} 秒(不可加速或截斷)")
        errs += _check_src(a0, s, tlmeta)
        items, t0 = [], 0
        for p in s["parts"]:
            items.append(dict(anim=p["anim"], t0=t0 / FPS))
            t0 += p["frames"]
        fin, hold = anim_finish(items)
        if d < fin + hold - 1e-6:   # 最後一步完全顯示後的停留(build_timeline 會自動補靜音;--check-only 讀舊時間軸時才會觸發)
            errs.append(f"{_line_span(s)}: 動畫鏡頭 {d:.2f} 秒,最後一步在 {fin:.2f} 秒才完全顯示,只停留 {d - fin:.2f} 秒 < {hold:.1f} 秒")
    return errs


def _over(bg, fr, x=0, y=0):
    """straight-alpha RGBA(ndarray)疊到 RGB 底圖的 (x, y),回傳新的 RGB ndarray。"""
    out = bg.copy()
    h, w = fr.shape[:2]
    a = fr[..., 3:4].astype(np.uint16)
    reg = out[y:y + h, x:x + w].astype(np.uint16)
    out[y:y + h, x:x + w] = ((reg * (255 - a) + fr[..., :3].astype(np.uint16) * a + 127) // 255).astype(np.uint8)
    return out


def _anim_frames(s, tlmeta, media):
    """動畫鏡頭逐格(HxWx3 uint8),剛好 s["frames"] 格:動畫播完後停在最後一格(emoji / 問號是原地循環)。
    ANIM_BG == "star":動畫格以透明底產生,逐格疊到星座背景;背景時間 = 成片絕對時間(s["f0"] + 鏡頭內格序),
    所以動畫凍結時背景仍在動,相鄰動畫鏡頭的背景也連續。"""
    if ANIM_BG == "star":
        for k, f in enumerate(_anim_layers(s, tlmeta, media, "alpha")):
            yield AL.over_star(f, (s["f0"] + k) / FPS)
        return
    yield from _anim_layers(s, tlmeta, media, "dark")


def tl_web_spec(a, tlmeta, step=None):
    """timeline 的網頁資料來源:自帶 points -> 只用 anim 自己的 points / question_between / scale / tracks;
    否則併入頂層共用 timeline(points、question_between、scale、tracks;anim 自己寫了 scale / tracks 則優先)。"""
    tm = tl_meta(a, tlmeta)
    return {"type": "timeline", "points": tm["points"], "question_between": tm.get("question_between"),
            "scale": a.get("scale", tm.get("scale")), "tracks": a.get("tracks", tm.get("tracks")),
            "src": a.get("src"), "step": step}


def _web_layers(s, media, bgm, tlmeta=None):
    """網頁渲染(anim_web)的逐格:逐步模式每句一段(prev -> shown;同 step 的後續句只取終態一格),否則整鏡一段;
    段落播完停在最後一格。bgm == "alpha" 回傳 RGBA(交給 over_star),"dark" 疊到深色底。
    timeline:每句一段(step k -> prev=k, shown=k+1;"q" -> 問號段),與前一句同 step 的後續句凍結在該段終態。"""
    parts = s["parts"]
    a0 = parts[0]["anim"]
    icons = media / "anim"
    if a0["type"] == "timeline":
        plan, jobs, prev_st = [], [], object()
        for p in parts:
            st = p["anim"]["step"]
            spec = tl_web_spec(a0, tlmeta, st)
            first = st != prev_st
            k = 0 if st == "q" else st
            jobs.append(AW.segment(spec, k, k + 1, n=p["frames"] if first else 10 ** 6))   # 後續句取整段的最後一格(終態)
            plan.append((p["frames"], first))
            prev_st = st
    elif _level_stepped(a0) or _list_stepped(a0):
        lp = list_plan(parts) if _list_stepped(a0) else level_plan(parts)
        plan = [(p["frames"], first) for p, (_, _, first) in zip(parts, lp)]
        jobs = [AW.segment(a0, prev, shown, title_in=(i == 0), n=p["frames"] if first else 1, icon_root=icons)
                for i, (p, (prev, shown, first)) in enumerate(zip(parts, lp))]
    else:
        plan, jobs = [(s["frames"], True)], [AW.segment(a0, n=s["frames"], icon_root=icons)]
    dark = None if bgm == "alpha" else np.asarray(AL._dark_bg().convert("RGB"))
    cur, cur_img = None, None
    for (n, first), files in zip(plan, AW.render(jobs)):
        for j in range(n):
            f = files[min(j, len(files) - 1)] if first else files[-1]
            if f != cur:        # 定格時不重讀、不重疊
                cur = f
                im = AW.load(f)
                cur_img = im if dark is None else _over(dark, im)
            yield cur_img


def _anim_layers(s, tlmeta, media, bgm):
    """逐格 ndarray:bgm == "dark" 時為 HxWx3(含深色底);"alpha" 時為 HxWx4 straight alpha(動畫本體,不含底)。"""
    star = bgm == "alpha"
    cut = (lambda f: f) if star else (lambda f: f[..., :3])
    parts = s["parts"]
    a0 = parts[0]["anim"]
    if a0["type"] == "timeline" and anim_engine(a0) == "web":
        yield from _web_layers(s, media, bgm, tlmeta)
        return
    if a0["type"] == "timeline":
        tm = tl_meta(a0, tlmeta)
        pts = [(p[0], p[1], p[2] if len(p) > 2 else TL_COLORS[i % len(TL_COLORS)]) for i, p in enumerate(tm["points"])]
        qb = tm.get("question_between")
        segs = {g["name"]: g["frames"] for g in AL.make_timeline(pts, tuple(qb) if qb else None, bg=bgm,
                                                                seg_seconds=TL_SEG_S, q_seconds=TL_Q_S, src=a0.get("src"))}
        lp = round(TL_Q_POP_S * FPS)
        for p in parts:
            st = p["anim"]["step"]
            fr = segs["q" if st == "q" else f"seg{st}"]
            for i in range(p["frames"]):
                if i < len(fr):
                    f = fr[i]
                elif st == "q":
                    f = fr[lp + (i - lp) % (len(fr) - lp)]
                else:
                    f = fr[-1]
                yield cut(f)
        return
    N = s["frames"]
    if anim_engine(a0) == "web":
        yield from _web_layers(s, media, bgm)
        return
    if _level_stepped(a0):
        for i, (p, (prev, shown, first)) in enumerate(zip(parts, level_plan(parts))):
            if a0["type"] == "cols":
                fr = AL.make_cols_step(a0["title"], a0["items"], shown, prev, title_in=(i == 0), bg=bgm, src=a0.get("src"))
            elif a0["type"] == "share":
                fr = AL.make_share_step(a0["title"], a0["rows"], shown, prev, title_in=(i == 0), bg=bgm, unit=a0.get("unit", "%"), src=a0.get("src"))
            elif a0["type"] == "num":
                fr = AL.make_num_step(a0.get("label"), a0["big"], a0.get("compare"), a0.get("tone"), shown, prev, title_in=(i == 0), bg=bgm, src=a0.get("src"))
            elif a0["type"] == "versus":
                fr = AL.make_versus_step(a0["title"], a0["left"], a0["right"], shown, prev, title_in=(i == 0), bg=bgm, src=a0.get("src"))
            elif a0["type"] == "flow":
                fr = AL.make_flow_step(a0["title"], a0["nodes"], shown, prev, title_in=(i == 0), bg=bgm, src=a0.get("src"))
            else:
                fr = AL.make_bars_step(a0["title"], a0.get("items"), shown, prev, title_in=(i == 0), bg=bgm,
                                       groups=a0.get("groups"), icon_root=str(media / "anim"), src=a0.get("src"))
            for j in range(p["frames"]):
                yield cut(fr[min(j, len(fr) - 1) if first else len(fr) - 1])
        return
    if a0["type"] in ("cols", "share", "num"):      # 省略 step = 一次播完
        if a0["type"] == "cols":
            fr = AL.make_cols_step(a0["title"], a0["items"], len(a0["items"]), 0, title_in=True, bg=bgm, src=a0.get("src"))
        elif a0["type"] == "share":
            fr = AL.make_share_step(a0["title"], a0["rows"], len(a0["rows"]), 0, title_in=True, bg=bgm, unit=a0.get("unit", "%"), src=a0.get("src"))
        else:
            fr = AL.make_num_step(a0.get("label"), a0["big"], a0.get("compare"), a0.get("tone"), None, 0, title_in=True, bg=bgm, src=a0.get("src"))
        for i in range(N):
            yield cut(fr[min(i, len(fr) - 1)])
        return
    if a0["type"] in ("span", "bars"):
        fr = AL.make_span(a0["from"], a0["to"], a0.get("ticks", 8), a0["big"], a0.get("caption", ""), bg=bgm, src=a0.get("src")) \
            if a0["type"] == "span" else AL.make_bars(a0["title"], a0.get("items"), bg=bgm, groups=a0.get("groups"),
                                                      icon_root=str(media / "anim"), src=a0.get("src"))
        for i in range(N):
            yield cut(fr[min(i, len(fr) - 1)])
        return
    if a0["type"] == "list":
        if not _list_stepped(a0):
            fr = AL.make_list(a0["title"], a0["items"], "all", a0.get("note"), bg=bgm, src=a0.get("src"))[0]["frames"]
            for i in range(N):
                yield cut(fr[min(i, len(fr) - 1)])
            return
        segs = {g["name"]: g["frames"] for g in AL.make_list(a0["title"], a0["items"], a0["step"], a0.get("note"), bg=bgm, src=a0.get("src"))}
        for p, first in zip(parts, list_firsts(parts)):
            fr = segs[f"seg{p['anim']['step']}"]
            for i in range(p["frames"]):
                yield cut(fr[min(i, len(fr) - 1) if first else len(fr) - 1])
        return
    bg = np.asarray(AL._dark_bg().convert("RGB"))
    if a0["type"] == "emoji":
        fr = AL.make_emoji(a0["name"], N / FPS + 1.0, str(media / "anim" / "_src"), base=EMO_SOLO, fade_out=False)
        px = fr[0].shape[0]
        x, y = ANIM_CENTER[0] - px // 2, ANIM_CENTER[1] - px // 2
        for i in range(N):
            if star:    # 透明整張畫布,emoji 貼在中央
                lay = np.zeros((H, W, 4), np.uint8)
                lay[y:y + px, x:x + px] = fr[i]
                yield lay
            else:
                yield _over(bg, fr[i], x, y)
        return
    fr = AL.make_puzzle(PUZZLE_S, center=ANIM_CENTER) if a0["type"] == "puzzle" else         AL.make_stamp(a0["text"], ANIM_CENTER, hold=0.0)
    last = None
    for i in range(N):
        if star:
            yield fr[min(i, len(fr) - 1)]
            continue
        if i < len(fr) or last is None:
            last = _over(bg, fr[min(i, len(fr) - 1)])
        yield last


def build_anim_shot(s, tlmeta, media):
    """動畫鏡頭 -> 不透明 mp4(快取在 ANIM_CACHE),格數 = 鏡頭格數。"""
    ANIM_CACHE.mkdir(parents=True, exist_ok=True)
    sig = _jkey([[(p["frames"], p["anim"]) for p in s["parts"]], tlmeta, AL.LIB_VERSION, ANIM_CENTER, EMO_SOLO,
                 TL_SEG_S, TL_Q_S, TL_Q_POP_S, PUZZLE_S, s["frames"], AL.NEWANIM_VER]
                 + ([ANIM_BG, AL.STAR_VER, s["f0"] % AL.STAR_N] if ANIM_BG == "star" else [])
                 + (["portrait", AL.P_LAYOUT_VER] if AL.PORTRAIT else [])
                 + (["web", AW.sig(a0["type"])] if anim_engine(a0 := s["parts"][0]["anim"]) == "web" else []))
    p = ANIM_CACHE / f"shot{'p' if AL.PORTRAIT else ''}_{hashlib.md5(sig.encode('utf8')).hexdigest()[:12]}.mp4"
    if not p.exists():
        part = p.with_name(p.stem + ".part.mp4")
        proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                 "-s", f"{AL.W}x{AL.H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                                 "-crf", "14", "-pix_fmt", "yuv420p", str(part)], stdin=subprocess.PIPE)
        n = 0
        for f in _anim_frames(s, tlmeta, media):
            proc.stdin.write(np.ascontiguousarray(f).tobytes())
            n += 1
        proc.stdin.close()
        if proc.wait() != 0 or n != s["frames"]:
            raise RuntimeError(f"動畫鏡頭輸出失敗({_line_span(s)}:{n}/{s['frames']} 格)")
        part.replace(p)
    return p


# ---- 段落轉場(預設 none;規則:有素材畫面時不疊動畫,所以正式影片不使用,只保留功能)
def _cached_asset(stem, frames_fn, alpha=True):
    """素材快取:ANIM_CACHE/<stem>_v<LIB_VERSION>.mov|mp4,旁邊的 .n 記錄格數。回傳 (路徑, 格數)。"""
    ANIM_CACHE.mkdir(parents=True, exist_ok=True)
    p = ANIM_CACHE / f"{stem}_v{AL.LIB_VERSION}{'.mov' if alpha else '.mp4'}"
    nf = p.with_suffix(".n")
    if not (p.exists() and nf.exists()):
        frames = frames_fn()
        part = p.with_name(p.stem + ".part" + p.suffix)
        AL.save_mov(frames, str(part), FPS, alpha)
        part.replace(p)
        nf.write_text(str(len(frames)))
    return p, int(nf.read_text())


def plan_trans(lines, secs):
    """段落轉場清單(作用在「進入這一段」的交界);段落沒寫 trans 就是 none。回傳 (items, warnings)。"""
    items, warns = [], []
    for i in range(1, len(lines)):
        if lines[i]["sec"] == lines[i - 1]["sec"]:
            continue
        sec = secs[lines[i]["sec"]]
        tr = sec.get("trans", "none")
        name = sec.get("title") or sec.get("name") or ""
        if tr not in TRANS_VALID or tr == "none":
            continue
        if tr == "title" and not name:
            tr = "wipe"
        items.append(dict(kind=tr, t0=lines[i]["f0"] / FPS - TRANS_MID[tr], text=name if tr == "title" else None))
    if items:
        warns.append(f"使用了 {len(items)} 個段落轉場(會疊在素材畫面上;專案規則是全片 none)")
    if sum(1 for it in items if it["kind"] == "glitch") > GLITCH_MAX:
        warns.append(f"glitch 轉場超過上限 {GLITCH_MAX}")
    return items, warns


def materialize_trans(items):
    for it in items:
        if it["kind"] == "wipe":
            it["path"], it["n"] = _cached_asset("wipe", AL.make_wipe)
        elif it["kind"] == "title":
            h = hashlib.md5(it["text"].encode("utf8")).hexdigest()[:8]
            it["path"], it["n"] = _cached_asset(f"title_{h}", lambda it=it: AL.make_title_wipe(it["text"]))


def trans_filters(items, first_in, in_label):
    """把轉場接在 [in_label] 之後:先 glitch(真的位移畫面),再疊 wipe/title。
    回傳 (額外輸入檔清單, filter 字串清單, 最後的 label)。first_in 為第一個額外輸入的 ffmpeg 輸入序號。"""
    inputs, fl, cur = [], [], in_label
    for gi, it in enumerate(i for i in items if i["kind"] == "glitch"):
        out = f"gl{gi}o"
        fl.append(AL.glitch_vf(it["t0"], 0.35, cur, out, prefix=f"gl{gi}_"))
        cur = out
    for j, it in enumerate(sorted((i for i in items if i["kind"] in ("wipe", "title")), key=lambda i: i["t0"])):
        idx = first_in + len(inputs)
        inputs.append(it["path"])
        t0, t1 = max(0.0, it["t0"]), it["t0"] + it["n"] / FPS
        fl.append(f"[{idx}:v]format=rgba,setpts=PTS-STARTPTS+{it['t0']:.4f}/TB[ov{j}]")
        out = f"ovo{j}"
        fl.append(f"[{cur}][ov{j}]overlay=x=0:y=0:format=auto:eof_action=pass:enable='between(t,{t0:.4f},{t1:.4f})'[{out}]")
        cur = out
    return inputs, fl, cur


# ---------------------------------------------------------------- 主流程
# ---------------------------------------------------------------- 直式(Shorts,--portrait;規格 projects/framework/shorts_spec.md)
PW, PH = 1080, 1920
P_WIN = {1080: (1080, 260), 1440: (810, 395), 1920: (608, 496)}   # 取景寬 -> (窗高, 窗上緣 y);窗寬一律 1080
P_MARGIN = 40          # 文字框聯集 / 卡片外框左右各留的邊(來源座標)
P_BG_DIM = 0.45        # 窗外模糊底圖亮度
P_BG_BLUR = 10         # 底圖在 1/4 解析度做的 boxblur 半徑
P_WIN_MAX_S = 5.0      # 單一畫面窗連續超過這麼多秒列警告
HOOK_MAX = 10          # 鉤子字數上限
HOOK_W, HOOK_FS_MAX = 860, 100   # 字級 = min(100, floor(860 / 字數))
HOOK_CX, HOOK_CY = 510, 195      # 墨跡中心
HOOK_OUTLINE, HOOK_SHADOW, HOOK_SHADOW_A = 4, 5, 0.62
# 直式原生畫面(F3-4):動畫(AL.P_NATIVE)、引言卡、對比、窄版截圖(images/<img>_p.png,news_lib --narrow)直接以畫面窗 1080x1080 繪製,
# 放在窗 y 260-1340(同影片);其餘鏡頭維持橫式成品取景。窗內座標的文字安全框 = 成片 x 80-940、y 300-1300。
P_NAT = 1080
P_SAFE = (80, 40, 940, 1040)     # 窗內文字安全框 (x0, y0, x1, y1)
P_CX = (P_SAFE[0] + P_SAFE[2]) / 2   # 510
P_FS_MIN = 48                    # 原生畫面文字字級下限
P_QUOTE_FS, P_QUOTE_FS_MIN, P_QUOTE_PADX = 72, 52, 52
P_CMP_FS, P_CMP_BAR_H = 56, 88
P_TXT_X0, P_TXT_X1 = 60, 940     # 窄版截圖文字欄(行框 x 聯集)在窗內的左右緣(右緣 <= 940:Shorts 右側按鈕區 x>940;左留 >= 60)
P_BTN_X, P_BTN_Y0, P_BTN_Y1 = 940, 700, 1660   # Shorts 右側介面保留區(spec §1):x > 940 且畫布 y 700-1660 不可有重要文字
P_WIN_Y = 260                    # 畫面窗上緣(畫布 y)
P_LABEL_FS = 54                  # 窄版截圖標籤字級(同 news_lib.NARROW_LABEL_FS;split_label 偵測用)
P_TOP_TOL = 2                    # 窄版截圖上緣切點落在行框內的容許誤差(原圖 px)
P_QUOTE_MX = 60                  # 直式引言卡底板左右離窗邊(底板水平置中於 540)


def parse_len(spec):
    a, b = (float(x) for x in spec.split("-"))
    return a, b


def make_hook(text, path):
    """標題帶鉤子字 PNG(1080x1920 透明):白字、黑描邊 4px、右下陰影 5px(62% 黑),墨跡中心 (510,195)。"""
    fs = min(HOOK_FS_MAX, HOOK_W // len(text))
    font = ImageFont.truetype(SUB_FONT, fs)
    l, t, r, b = font.getbbox(text, anchor="ls")
    x, y = HOOK_CX - (l + r) / 2, HOOK_CY - (t + b) / 2
    kw = dict(font=font, anchor="ls", stroke_width=HOOK_OUTLINE, stroke_fill=(0, 0, 0, 255))
    sh = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x + HOOK_SHADOW, y + HOOK_SHADOW), text, fill=(0, 0, 0, 255), **kw)
    sh.putalpha(sh.getchannel("A").point(lambda v: round(v * HOOK_SHADOW_A)))
    img = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    img.alpha_composite(sh)
    ImageDraw.Draw(img).text((x, y), text, fill=(255, 255, 255, 255), **kw)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _img_text_span(s, media):
    """圖片鏡頭的文字框聯集(含「中文翻譯·原文」標籤)在橫式成片的 x 範圍;fx 動態全程取聯集,只算落在畫面內的框。
    沒有 .boxes.json 或沒有畫面內的框回傳 None。"""
    lay = s.get("layout")
    ents = _load_boxes(media, s["img"]) if lay else None
    if not ents:
        return None
    sc, (px, py) = lay["sc"], lay["pos"]
    rects = [(px + e["box"][0] * sc, py + e["box"][1] * sc, px + e["box"][2] * sc, py + e["box"][3] * sc) for e in ents]
    im = Image.open(media / "images" / f"{s['img']}.png").convert("RGB")
    _, label = split_label(im)
    if label:  # 與 prep_image 相同的右下位置(右上替代位置的 x 範圍相同)
        lw, lh = label.width * LABEL_SCALE, label.height * LABEL_SCALE
        r_ = min(px + im.width * sc, W) - LABEL_MARGIN
        b_ = min(py + im.height * sc, (SAFE_Y_TILT if s["fx"].startswith("tilt") else SAFE_Y_FLAT)[1]) - LABEL_MARGIN * 0.6
        rects.append((r_ - lw, b_ - lh, r_, b_))
    xs = []
    for m in _fx_maps(s["fx"], lay.get("zoom")):
        for x0, y0, x1, y1 in rects:
            pts = [m(x, y) for x in (x0, x1) for y in (y0, y1)]
            if max(p[1] for p in pts) <= 0 or min(p[1] for p in pts) >= H:
                continue
            xs += [max(0.0, min(p[0] for p in pts)), min(float(W), max(p[0] for p in pts))]
    return (min(xs), max(xs)) if xs else None


def _card_span(png):
    bb = Image.open(png).getchannel("A").getbbox()
    return (bb[0], bb[2]) if bb else None


def _p_native_png(s, ln, media):
    """直式原生畫面(引言卡 / 對比 / 窄版截圖)-> (畫面檔, 最小字級, 說明);引言、對比是 png,窄版截圖是 mp4(底線畫出動畫);不適用回傳 None。"""
    out = s["file"].parent.parent / "native_p"
    if s.get("special") in ("quote", "compare"):
        png = out / f"{s['n']:04d}_{s['special']}.png"
        fs = make_quote(s["quote"], s.get("bg_img"), media, png, portrait=True) if s["special"] == "quote" \
            else make_compare(s["compare"], media, png, portrait=True)
        return png, fs, f"{s['special']}(原生)"
    if s["kind"] == "image" and not s.get("special") and (media / "images" / f"{s['img']}_p.png").exists():
        mp4, fs = make_img_p(s, media, out / f"{s['n']:04d}_img.png")
        return mp4, fs, "圖片(窄版原生)"
    return None


def _img_p_geom(img, groups, media):
    """窄版截圖在直式畫面窗(1080x1080)的幾何。文字欄(全部行框的 x 聯集)縮放到 P_TXT_X0-P_TXT_X1;
    垂直:圖高於窗時把 hl 命中處(沒有就頂端)放在窗高 42% 附近,上下切點都落在行與行之間(不切半行字):
    在「0 / 行框上緣 / 行框下緣 / 圖底對齊點」這些候選切點裡,挑上下緣都不在行框內、hl 命中框全在窗內、離理想位置最近的;
    窗下緣以下(含標籤列)用底色蓋掉。groups = 各段 hl 的關鍵字清單。
    回傳 dict(clean, label, k, ox, oy, ents, groups=各段命中框(原圖 px), bot=下切點(原圖 px,沒有下切時 None))。"""
    im = Image.open(media / "images" / f"{img}_p.png").convert("RGB")
    clean, label = split_label(im, P_LABEL_FS)
    ents = _load_boxes(media, f"{img}_p") or []
    tx0, tx1 = (min(e["box"][0] for e in ents), max(e["box"][2] for e in ents)) if ents else (0, im.width)
    k = (P_TXT_X1 - P_TXT_X0) / max(1, tx1 - tx0)
    hits = [[b for kw in g for b in find_hl_boxes(ents, kw)] for g in groups]
    flat = [b for g in hits for b in g]
    ch = clean.height * k
    bot = None
    if ch > P_NAT:
        vis = (P_NAT - (label.height * k + 24 if label else 0)) / k   # 窗內可放內容的高度(原圖 px;下面留標籤列)
        cmax = max(0.0, clean.height - vis)
        fy = (sum((b[1] + b[3]) / 2 for b in flat) / len(flat) * k) if flat else 0
        ideal = min(cmax, max(0.0, (fy - P_NAT * 0.42) / k))
        inside = lambda y: any(e["box"][1] + P_TOP_TOL < y < e["box"][3] - P_TOP_TOL for e in ents)
        cands = sorted({0.0, cmax} | {float(min(cmax, max(0, v))) for e in ents for v in (e["box"][1], e["box"][3])})
        good = [c for c in cands if not inside(c) and (c >= cmax - 0.5 or not inside(c + vis))]
        full = [c for c in good if all(b[1] >= c - 1 and b[3] <= c + vis + 1 for b in flat)]
        cut = min(full or good or [ideal], key=lambda c: abs(c - ideal))
        oy = -cut * k
        bot = None if cut >= cmax - 0.5 else cut + vis
    else:
        oy = (P_NAT - ch) / 2
    return dict(clean=clean, label=label, k=k, ox=P_TXT_X0 - tx0 * k, oy=oy, ents=ents, groups=hits, bot=bot)


def _img_p_cut(g):
    """窄版截圖幾何中被窗上緣或下切點切到半行的行(文字)清單;渲染前檢查用。"""
    k, oy = g["k"], g["oy"]
    edges = [0.0] + ([oy + g["bot"] * k] if g.get("bot") is not None else [])
    return [e["text"] for e in g["ents"] for y in edges
            if oy + (e["box"][1] + P_TOP_TOL) * k < y < oy + (e["box"][3] - P_TOP_TOL) * k]


def _img_p_zone(g):
    """窄版截圖進入 Shorts 右側按鈕區的文字框清單(畫布座標;窗內可見的行框與標籤);渲染前檢查用。"""
    k, ox, oy = g["k"], g["ox"], g["oy"]
    ymax = (oy + g["bot"] * k) if g.get("bot") is not None else P_NAT
    bad = []
    for e in g["ents"]:
        x1, y0, y1 = ox + e["box"][2] * k, oy + e["box"][1] * k, oy + e["box"][3] * k
        if x1 > P_BTN_X + 0.5 and y1 > 0 and y0 < ymax and y1 + P_WIN_Y > P_BTN_Y0 and y0 + P_WIN_Y < P_BTN_Y1:
            bad.append((e["text"][:12], round(x1)))
    if g["label"] and P_TXT_X1 > P_BTN_X + 0.5:
        bad.append(("標籤", P_TXT_X1))
    return bad


def _img_p_base(g):
    """窄版截圖直式窗底圖(RGBA 1080x1080):縮放後的截圖、下切點以下蓋底色、標籤貼在窗右下(右緣 P_TXT_X1、離窗底 16)。"""
    k, ox, oy, clean = g["k"], g["ox"], g["oy"], g["clean"]
    base = Image.new("RGBA", (P_NAT, P_NAT), clean.getpixel((2, 2)) + (255,))
    base.paste(clean.resize((round(clean.width * k), round(clean.height * k)), Image.LANCZOS), (round(ox), round(oy)))
    if g.get("bot") is not None:   # 下切點以下蓋底色(切點在行與行之間),標籤放在這一帶
        ImageDraw.Draw(base).rectangle((0, round(oy + g["bot"] * k), P_NAT, P_NAT), fill=base.getpixel((2, 2)))
    if g["label"]:
        _paste_label(base, g["label"], P_TXT_X1, P_NAT - 16, k)
    return base


def _img_p_label_box(g):
    """標籤在窗內的外框 (x0, y0, x1, y1);沒有標籤 None。"""
    if not g["label"]:
        return None
    w, h = round(g["label"].width * g["k"]), round(g["label"].height * g["k"])
    return (P_TXT_X1 - w, P_NAT - 16 - h, P_TXT_X1, P_NAT - 16)


def _img_p_label_errs(g, base):
    """標籤檢查(渲染前):有標籤必須畫出來(框內要有白字墨跡)、右緣 <= P_BTN_X、在窗內且 y 不進字幕帶(畫布 y > 1340)、不壓到可見的文字框。"""
    bx = _img_p_label_box(g)
    if bx is None:
        return []
    errs = []
    x0, y0, x1, y1 = bx
    if x1 > P_BTN_X + 0.5:
        errs.append(f"標籤右緣 {x1} > {P_BTN_X}")
    if x0 < 0 or y0 < 0 or y1 > P_NAT or y1 + P_WIN_Y > 1340:
        errs.append(f"標籤超出畫面窗或進入字幕帶 {bx}")
    ink = sum(1 for p in base.crop(bx).convert("L").getdata() if p > 200)
    if ink < 20:
        errs.append(f"標籤沒畫出來(框 {bx} 內白字像素 {ink})")
    k, ox, oy = g["k"], g["ox"], g["oy"]
    ymax = (oy + g["bot"] * k) if g.get("bot") is not None else P_NAT
    for e in g["ents"]:
        ex0, ey0, ex1, ey1 = ox + e["box"][0] * k, oy + e["box"][1] * k, ox + e["box"][2] * k, oy + e["box"][3] * k
        if ey1 > 0 and ey0 < ymax and ex0 < x1 and ex1 > x0 and ey0 < y1 and ey1 > y0:
            errs.append(f"標籤壓到文字框「{e['text'][:12]}」")
            break
    return errs


def _ul_sprite(w, th, e):
    """紅色底線貼圖(圓頭、深色外緣;樣式同 prep_hl)。"""
    ss = 3
    w_, h_ = max(2, round(w + 2 * e)), max(2, round(th + 2 * e))
    spr = Image.new("RGBA", (w_ * ss, h_ * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(spr)
    d.rounded_rectangle((0, 0, w_ * ss - 1, h_ * ss - 1), h_ * ss / 2, fill=HL_UL_EDGE_COLOR)
    d.rounded_rectangle((e * ss, e * ss, (w_ - e) * ss - 1, (h_ - e) * ss - 1), th * ss / 2, fill=HL_UL_COLOR)
    return spr.resize((w_, h_), Image.LANCZOS)


def make_img_p(s, media, path):
    """窄版截圖 -> 直式畫面窗 1080x1080 的 mp4(長度 = 鏡頭格數):幾何見 _img_p_geom;翻譯標籤移到窗右下。
    hl 底線時序同橫式 prep_hl:各段起點見 hl_starts(旁白唸到該詞才開始畫)、各條依序由左至右畫出(ease-out),下一段開始時換掉前一段。
    path = 底線畫完的最終狀態 PNG(QA 用)。回傳 (mp4 路徑, 最小字級(.layout.json 的 fs,沒有就用行框高))。"""
    hls = s.get("hls") or []
    g = _img_p_geom(s["img"], [h["kws"] for h in hls], media)
    k, ox, oy, ents = g["k"], g["ox"], g["oy"], g["ents"]
    base = _img_p_base(g)
    drawn = []
    for h, hits in zip(hls, g["groups"]):
        bars = []
        for b in hits:
            x0, y0, x1, y1 = (ox + b[0] * k, oy + b[1] * k, ox + b[2] * k, oy + b[3] * k)
            lh = y1 - y0
            ux0, ux1 = max(P_MARGIN, x0 - lh * HL_UL_EXT), min(P_BTN_X, x1 + lh * HL_UL_EXT)
            bars.append((_ul_sprite(ux1 - ux0, max(HL_UL_MINW, lh * HL_UL_W), HL_UL_EDGE),
                         round(ux0 - HL_UL_EDGE), round(y1 + lh * HL_UL_GAP - HL_UL_EDGE)))
        if bars:
            bf = max(3, round(min(HL_UL_DUR, HL_UL_TOTAL / len(bars)) * FPS))
            drawn.append((h, bf, bars))
    ts = hl_starts([d[0] for d in drawn], s["f0"], s["frames"])
    layers = [(round(t * FPS), bf, bars) for t, (_, bf, bars) in zip(ts, drawn)]

    def frame(f):
        cur = [L for L in layers if L[0] <= f]
        img = base.copy()
        if cur:
            f0, bf, bars = cur[-1]
            for j, (spr, bx, by) in enumerate(bars):
                u = min(1.0, max(0.0, (f - f0 - j * bf) / bf))
                shown = round(spr.width * (1 - (1 - u) ** 3))
                if shown > 0:
                    _blit(img, spr.crop((0, 0, shown, spr.height)), bx, by)
        return img

    path.parent.mkdir(parents=True, exist_ok=True)
    N = s["frames"]
    frame(N + 10 ** 6).convert("RGB").save(path)
    sig = sha1(json.dumps([hashlib.sha1(base.tobytes()).hexdigest(), N, FPS,
                           [(f0, bf, [(bx, by, spr.size) for spr, bx, by in bars]) for f0, bf, bars in layers]]))
    mp4 = path.with_name(f"{path.stem}_{sig[:10]}.mp4")
    if not mp4.exists():
        part = mp4.with_suffix(".part.mp4")
        pr = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s", f"{P_NAT}x{P_NAT}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                               "-crf", "16", "-pix_fmt", "yuv420p", "-f", "mp4", str(part)], stdin=subprocess.PIPE)
        prev = None
        for f in range(N):   # 只在底線畫出期間與換段時重畫,其餘沿用上一格
            if prev is None or any(L[0] <= f <= L[0] + L[1] * len(L[2]) + 1 for L in layers):
                prev = frame(f).convert("RGB").tobytes()
            pr.stdin.write(prev)
        pr.stdin.close()
        if pr.wait():
            raise RuntimeError(f"窄版截圖 mp4 失敗: {mp4}")
        part.replace(mp4)
    lj = media / "images" / f"{s['img']}_p.layout.json"
    ymax = oy + g["bot"] * k if g.get("bot") is not None else P_NAT
    vis = [i for i, e in enumerate(ents) if 0 <= oy + e["box"][1] * k and oy + e["box"][3] * k <= ymax]
    if lj.exists():
        runs = json.loads(lj.read_text(encoding="utf-8"))["runs"]
        return mp4, (round(min(runs[i]["fs"] for i in vis) * k, 1) if vis and len(runs) == len(ents) else None)
    return mp4, (round(min(ents[i]["box"][3] - ents[i]["box"][1] for i in vis) * k, 1) if vis else None)


def _card_p(png):
    """卡片(1920x1080 透明 PNG)-> 直式原生窗 1080x1080:墨跡範圍左右各加 P_MARGIN 放得進 1080 就裁該段,
    否則等比縮到 1080 寬並垂直置中。輸出 <卡片>_p.png。"""
    out = Path(png).with_name(Path(png).stem + "_p.png")
    im = Image.open(png).convert("RGBA")
    bb = im.getchannel("A").getbbox() or (0, 0, W, H)
    cx, need = (bb[0] + bb[2]) / 2, bb[2] - bb[0] + 2 * P_MARGIN
    if need <= P_NAT:
        x0 = round(min(W - P_NAT, max(0, cx - P_NAT / 2)))
        res = im.crop((x0, 0, x0 + P_NAT, H))
    else:
        x0 = round(cx - need / 2)
        sm = im.crop((x0, 0, x0 + need, H)).resize((P_NAT, round(H * P_NAT / need)), Image.LANCZOS)
        res = Image.new("RGBA", (P_NAT, P_NAT), (0, 0, 0, 0))
        res.alpha_composite(sm, (0, (P_NAT - sm.height) // 2))
    res.save(out)
    return out


def portrait_window(s, ln, media):
    """鏡頭的直式取景(spec §3):回傳 dict(x0, cw, wh, wy, why[, native, fs])。來源 = 橫式成品鏡頭,取 cw x 1080 縮到 1080 x wh 放在 y=wy。
    原生鏡頭(F3-4)不取景:native = 原生畫面檔(動畫先標 "anim",render_portrait_shot 時才產 mp4),窗 1080x1080 放在 y=260。"""
    wh0, wy0 = P_WIN[1080]
    if s.get("special") == "anim":
        typ = s["parts"][0]["anim"]["type"]
        if typ in AL.P_NATIVE or (AW.has_template(typ, portrait=True) and s["parts"][0]["anim"].get("engine", "web") == "web"):
            return dict(x0=None, cw=None, wh=wh0, wy=wy0, why=f"動畫 {typ}(原生)", native="anim")
        log(f"警告: {_line_span(s)} 動畫型別 {typ} 直式未支援原生繪製,退回橫式整張縮放")
    nat = _p_native_png(s, ln, media)
    if nat:
        return dict(x0=None, cw=None, wh=wh0, wy=wy0, why=nat[2], native=str(nat[0]), fs=nat[1])
    req = []
    if s["kind"] == "video":
        center, widths, why = float(ln.get("cx", 0.5)) * W, (1080, 1440, 1920), "影片"
    elif s["kind"] == "image" and not s.get("special"):
        sp = _img_text_span(s, media)
        if sp:
            req.append((sp[0] - P_MARGIN, sp[1] + P_MARGIN))
            center, widths, why = (sp[0] + sp[1]) / 2, (1440, 1920), "圖片"
        else:
            center, widths, why = W / 2, (1920,), "圖片(無文字框)"
    else:
        center, widths, why = W / 2, (1920,), s.get("special") or "其他"
    for c in s.get("cards") or []:
        sp = _card_span(c["png"])
        if sp:
            req.append((sp[0] - P_MARGIN, sp[1] + P_MARGIN))
            why += "+卡片"
    for cw in widths:
        lo = max([0] + [b - cw for a, b in req])
        hi = min([W - cw] + [a for a, b in req])
        if cw == W or lo <= hi:
            x0 = 0 if cw == W else round(min(hi, max(lo, center - cw / 2)))
            wh, wy = P_WIN[cw]
            return dict(x0=x0, cw=cw, wh=wh, wy=wy, why=why)


def check_portrait(lines, shots, total, len_rng, hook, media=None):
    """直式額外檢查(spec §5):回傳 (錯誤, 警告)。窄版截圖另查上緣是否切到半行字。"""
    errs, warns = [], []
    if not len_rng[0] <= total <= len_rng[1]:
        errs.append(f"直式總長 {total:.1f} 秒不在 {len_rng[0]:g}-{len_rng[1]:g} 秒內")
    if hook and len(hook) > HOOK_MAX:
        errs.append(f"鉤子「{hook}」{len(hook)} 字 > {HOOK_MAX} 字")
    seen = set()
    for ln in lines:
        for t in [ln["text"]] + [c for c, _ in TS.split_clauses(ln["text"])]:
            for txt, _ in split_phrases(t):
                w = sub_text_width(txt) + 2 * SUB_PAD_X
                if w > SUB_MAX_PX + 0.5 and txt not in seen:
                    seen.add(txt)
                    errs.append(f"句{ln['idx']}: 直式字幕段「{txt}」寬 {w:.0f}px 超出安全框 {SUB_MAX_PX:.0f}px")
    for s in shots:
        if media and s["kind"] == "image" and not s.get("special") and (media / "images" / f"{s['img']}_p.png").exists():
            g = _img_p_geom(s["img"], [h["kws"] for h in s.get("hls") or []], media)
            cut = _img_p_cut(g)
            if cut:
                errs.append(f"{_line_span(s)}: 直式窄版截圖上下緣切到半行字「{cut[0][:12]}」")
            for m in _img_p_label_errs(g, _img_p_base(g)):
                errs.append(f"{_line_span(s)}: 直式窄版截圖{m}")
            zone = _img_p_zone(g)
            if zone:
                errs.append(f"{_line_span(s)}: 直式窄版截圖文字框進入右側按鈕區(x>{P_BTN_X}):{zone[0][0]} 右緣 {zone[0][1]}")
        if s["frames"] / FPS > P_WIN_MAX_S + 1e-6:
            warns.append(f"{_line_span(s)}: 直式畫面窗連續 {s['frames'] / FPS:.1f} 秒 > {P_WIN_MAX_S:g} 秒")
    if not lines[-1]["text"].rstrip().endswith(("?", "?")):
        warns.append(f"句{lines[-1]['idx']}: 直式最後一句不是問號結尾")
    return errs, warns


def portrait_cmd(s, win, hook_png, out):
    """橫式成品鏡頭 -> 直式鏡頭:cover 底圖在 1/4 解析度 boxblur 後放大、亮度 x0.45;畫面窗靜態取景;疊鉤子。不含聲音。"""
    d = f"val*{P_BG_DIM}"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", s["file"]]
    nat = win.get("native")
    cards = (s.get("cards") or []) if nat else []
    if nat:   # 原生畫面(png 靜態 / mp4)當前景;底圖仍取橫式成品鏡頭。卡片改疊在前景上(橫式成品上的卡片不在前景裡)
        cmd += (["-loop", "1", "-framerate", str(FPS)] if nat.endswith(".png") else []) + ["-i", nat]
        kit = win.get("kit")      # 直式動畫的小件圖層(plan_kit_portrait):疊在動畫上、卡片之下;輸入排在卡片之後
        kidx = 2 + len(cards)
        bg_in, cur = "[0:v]", "f0"
        fg = (f"[1:v]scale={PW}:{win['wh']},setsar=1,format=yuv420p[f00];"
              f"[{kidx}:v]format=rgba,loop=loop={kit['delay']}:size=1:start=0,tpad=stop={s['frames']}:stop_mode=clone[kk];"
              f"[f00][kk]overlay=0:0:format=auto,format=yuv420p[f0];") if kit else              f"[1:v]scale={PW}:{win['wh']},setsar=1,format=yuv420p[f0];"
        pct = f"val*{CARD_DIM}"
        for ci, c in enumerate(cards):   # 同橫式 build_cmd:底圖模糊壓暗 + 卡片,整組淡入淡出
            cmd += ["-loop", "1", "-framerate", str(FPS), "-i", str(_card_p(c["png"]))]
            fg += (f"[{cur}]split[co{ci}][cd{ci}];[cd{ci}]boxblur=4:1,format=gbrp,lutrgb=r={pct}:g={pct}:b={pct},"
                   f"format=yuv420p[cdd{ci}];[cdd{ci}][{2 + ci}:v]overlay=0:0:format=auto,format=yuva420p")
            if c["fin"]:
                fg += f",fade=t=in:st={c['t0']:.3f}:d={CARD_FADE}:alpha=1"
            if c["fout"]:
                fg += f",fade=t=out:st={max(0.0, c['t1'] - CARD_FADE):.3f}:d={CARD_FADE}:alpha=1"
            fg += f"[cdf{ci}];[co{ci}][cdf{ci}]overlay=0:0:format=auto,format=yuv420p[f{ci + 1}];"
            cur = f"f{ci + 1}"
        fg += f"[{cur}]null[fg];"
        if kit:
            cmd += ["-framerate", str(FPS), "-start_number", "1", "-i", kit["pat"]]
    else:
        bg_in, fg = "[0:v]split=2[a][b];[a]", f"[b]crop={win['cw']}:{H}:{win['x0']}:0,scale={PW}:{win['wh']},setsar=1[fg];"
    vf = (f"{bg_in}scale=-2:{PH // 4},crop={PW // 4}:{PH // 4},boxblur={P_BG_BLUR}:1,scale={PW}:{PH},"
          f"format=gbrp,lutrgb=r={d}:g={d}:b={d},format=yuv420p[bg];"
          f"{fg}"
          f"[bg][fg]overlay=0:{win['wy']}:format=auto")
    if hook_png:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-i", hook_png]
        vf += f"[o];[o][{2 + len(cards) + (1 if win.get('kit') else 0) if nat else 1}:v]overlay=0:0:format=auto"
    vf += ",setsar=1,format=yuv420p[v]"
    cmd += ["-filter_complex", vf, "-map", "[v]", "-frames:v", str(s["frames"]), "-r", str(FPS), "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-f", "mp4", out]
    return cmd


def render_portrait_shot(s, hook_png, tlmeta=None, media=None):
    """呼叫前須 AL.set_profile("portrait")(原生動畫用直式常數組;main 在平行渲染前後切換)。"""
    out = s["file"].parent.parent / "shots_p" / s["file"].name
    part = out.with_suffix(".part.mp4")
    if s["pwin"].get("native") == "anim":
        s["pwin"]["native"] = str(build_anim_shot(s, tlmeta, media))
    cmd = portrait_cmd(s, s["pwin"], hook_png, part)
    nat = s["pwin"].get("native")
    key = sha1(json.dumps([P.rel(c) for c in cmd], ensure_ascii=False) + s["file"].with_suffix(".key").read_text()
               + (hashlib.sha1(Path(hook_png).read_bytes()).hexdigest() if hook_png else "")
               + (hashlib.sha1(Path(nat).read_bytes()).hexdigest() if nat and nat.endswith(".png") else ""))
    keyf = out.with_suffix(".key")
    if not (out.exists() and keyf.exists() and keyf.read_text() == key):
        run(cmd)
        part.replace(out)
        keyf.write_text(key)
    s["pfile"] = out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--rate", default="+10%")
    ap.add_argument("--gap", type=float, default=0.04, help="句間停頓秒數")
    ap.add_argument("--section-gap", type=float, default=0.15, help="段落間停頓秒數")
    ap.add_argument("--tts-engine", default="edge")
    ap.add_argument("--tts-cmd", help="非 edge 引擎的外部批次合成指令(後面接 jobs.json --voice V --rate R)")
    ap.add_argument("--spk", help="chattts 的音色檔(SPEAKERS 內的檔名,如 F_seed_2456.pt);給了就不必寫 --tts-cmd,"
                                  "指令由 paths.py 的 TTS_ENV / SPEAKERS 組出")
    ap.add_argument("--comma-profile", choices=sorted(TPA.PROFILES), default="std",
                    help="逗號停頓側寫:std = 現行(預設);long = 長句逗號停頓較長(僅供本機 A/B 試聽;只重做停頓後處理,不重錄)")
    ap.add_argument("--cosy-speed", default="1.18", help="--tts-engine cosy3 的 speed(2026-10-17 使用者定案 1.18)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True, help="只給檔名 -> OUTPUT/<tag>/<檔名>;其他相對路徑以素材根為基準")
    ap.add_argument("--lines")
    ap.add_argument("--clips", help="clips json;auto = 專案檔 projects/<tag>/clips_<tag>.json")
    ap.add_argument("--bed", type=float, default=0.06,
                    help="素材原聲的增益上限(0 = 不混入);每個影片鏡頭另依量到的響度壓到 BED_TARGET_DB 以下")
    ap.add_argument("--max-per-src", type=float, default=90)
    ap.add_argument("--media", default=str(P.ROOT), help="素材根(預設由 paths.py 決定;一般不必給)")
    ap.add_argument("--card-min", type=float, default=2.6, help="卡片最短顯示秒數(不足時延續到後面鏡頭)")
    ap.add_argument("--img-min", type=float, default=3.2, help="圖片鏡頭最短顯示秒數(不足時向相鄰影片鏡頭借時間)")
    ap.add_argument("--bgm", help="背景音樂檔(不足長度自動循環,頭尾淡入淡出 2 秒,配音時 sidechain 壓低)")
    ap.add_argument("--bgm-vol", type=float, default=None,
                    help="舊算法(舊片重渲染用):增益 = 此值 × bgm_norm(整首對齊 BGM_REF_DB);不給 = 預設算法(對齊配音響度:"
                         "BGM 3 秒窗 p90 = 配音 - 5.7 dB、最大窗至少比配音低 5.0 dB)")
    ap.add_argument("--bgm-db", type=float, default=0.0, help="預設算法再加減幾 dB(使用者要求「大聲 X dB」時用;給 --bgm-vol 時無效)")
    ap.add_argument("--voice-eq", default="", help="只對配音軌在最終混音前加的 ffmpeg 濾鏡字串;預設關閉,具名預設:soft(不影響 TTS 快取)")
    ap.add_argument("--seg", choices=SEG.NAMES, default=None,
                    help="字幕/換行斷詞器(T2):jieba|ckip;預設看環境變數 CV_SEG,再預設 jieba。ckip 需 pip install ckip-transformers,載入失敗退回 jieba;sub_words.txt 兩邊都吃")
    ap.add_argument("--anim-bg", choices=("none", "star"), default="none",
                    help="獨立深色底動畫鏡頭(list/bars/timeline/span/stamp/emoji/puzzle)的底:none = 純深色(預設,re9);"
                         "star = 光點星座動態背景(取樣時間 = 成片絕對時間)")
    ap.add_argument("--legacy-tilt", action="store_true",
                    help="舊片重渲染保持原外觀:沒有 layout kind 的文字截圖(有 .boxes.json)也輪用 tilt(預設改用 text 組 zoom+漂移,不傾斜)")
    ap.add_argument("--label-style", choices=LABEL_STYLES, default=None,
                    help="截圖出處標籤:lower = kit 下標籤(預設,左下滑入、整鏡頭留著);corner = 舊的右下角標重貼(舊片重渲染用)。"
                         "script 頂層或單句的 label_style 優先於本參數")
    ap.add_argument("--no-push", action="store_true",
                    help="關閉鏡頭間 0.2 秒輕推移(靜態→靜態交界新鏡頭 1.00→1.02;單句 push: false 只關該鏡頭;直式不套)")
    ap.add_argument("--no-anim", action="store_true", help="不疊段落轉場(動畫鏡頭是鏡頭本身,不受影響)")
    ap.add_argument("--no-synth", action="store_true",
                    help="配音只准用快取:有任何一句需要合成或重新檢驗就中止(重建既有版本時用,保證配音不被重錄)")
    ap.add_argument("--frozen", nargs="?", const="", default=None, metavar="TAG",
                    help="凍結後禁新合成:TAG(省略 = --tag;shorts 傳母片 tag)的 projects\\<TAG>\\freeze.json 存在時,"
                         "配音有任何快取未命中(文案/讀音表/英文表改)就逐句列出並 exit 2,不動音檔;沒有 freeze.json 則不限制。"
                         "make_version 非 --tts-review 一律傳;--tts-review 不傳")
    ap.add_argument("--tts-only", action="store_true", help="只跑到 TTS(含裁靜音、時間軸)就結束,並寫出 timeline_tts.json")
    ap.add_argument("--check-only", action="store_true",
                    help="只做渲染前檢查(鏡頭規劃與時長、缺畫面、片段不足、hl、同圖連續、卡片、動畫),不合成不渲染;需 --timeline")
    ap.add_argument("--timeline", help="--check-only 用:既有 timeline.json / timeline_tts.json,提供每句的時間(省掉 TTS)")
    ap.add_argument("--timing-only", action="store_true",
                    help="只能與 --check-only 併用:配音後的時長預檢,不需任何素材(缺圖/缺片段不算錯,影片鏡頭以標籤當占位)。"
                         "只跑 同圖連續(秒/句數)、鏡頭最短時長/影片上限、動畫(每步秒數/停留/timeline 節點)、動畫容量;"
                         "跳過亮度、文字裁切、硬切、小件擺放、字幕縫、片段挑選;不寫 plan.json")
    ap.add_argument("--force", action="store_true", help="渲染前檢查有錯誤仍繼續渲染(缺畫面除外)")
    ap.add_argument("--portrait", action="store_true", help="直式 Shorts 1080x1920(鏡頭照橫式渲染後轉直式,字幕用直式組)")
    ap.add_argument("--hook", default="", help="直式標題帶的鉤子字(<= 10 字、不加標點;省略 = 不畫)")
    ap.add_argument("--len", default="25-45", help="直式總長檢查秒數 a-b(只在 --portrait 生效)")
    args = ap.parse_args()
    if args.seg:
        SEG.set_seg(args.seg)
    SEG.set_tag(args.tag)   # build\<tag>\words.txt(沒有就不動,已凍結片不產)
    if args.timing_only and not args.check_only:
        ap.error("--timing-only 只能與 --check-only 併用")
    if args.portrait:
        global VIDEO_MAX, VIDEO_SPLIT
        VIDEO_MAX, VIDEO_SPLIT = P_VIDEO_MAX, P_VIDEO_SPLIT  # 直式影片鏡頭較短,長鏡頭自動分段(橫式維持 8 / 6.5)
        set_sub_profile("portrait")
        args.hook = args.hook.strip()
    global ANIM_BG, LEGACY_TILT
    ANIM_BG = args.anim_bg
    LEGACY_TILT = args.legacy_tilt
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    media = Path(args.media)
    out_path = P.out_file(args.out, args.tag)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bdir = P.build_dir(args.tag)
    args.script = P.find(args.script, P.REPO)
    if args.timing_only:
        args.clips = None   # 時長預檢不挑片段,clips 不存在也不影響
    if args.clips:
        args.clips = P.clips_file(args.tag) if args.clips == "auto" else P.find(args.clips)
    if args.timeline:
        args.timeline = P.find(args.timeline)
    tts_cmd = shlex.split(args.tts_cmd, posix=False) if args.tts_cmd else None
    if args.spk:
        if args.tts_engine != "chattts" or tts_cmd:
            sys.exit("--spk 只用於 --tts-engine chattts,且不可與 --tts-cmd 同時給")
        spk = P.speaker(args.spk)
        if not spk.exists():
            sys.exit(f"找不到音色檔: {spk}")
        tts_cmd = [P.TTS_ENV, P.REPO / "pipeline" / "tts_chattts.py", "--spk-pt", spk]
    if args.tts_engine == "cosy3" and not tts_cmd:  # CosyVoice3 零樣本複製(參考音 = paths.COSY_REF;參考音檔名與 speed 進快取鍵)
        tts_cmd = [P.TTS_ENV, P.REPO / "pipeline" / "tts_cosy3.py", "--ref", P.COSY_REF, "--speed", args.cosy_speed]
    for sub in (P.TTS_SUBDIR.get(args.tts_engine, "tts"), "shots", "cards", "fonts"):
        (bdir / sub).mkdir(parents=True, exist_ok=True)

    all_lines = load_lines(args.script)
    secs, tlmeta = load_meta(args.script)
    a, b = parse_range(args.lines, len(all_lines))
    lines = [l for l in all_lines if a <= l["idx"] <= b]
    if not lines:
        sys.exit("沒有選到任何句子")
    clips = json.loads(Path(args.clips).read_text(encoding="utf-8")) if args.clips else None

    if not clips and not args.tts_only and not args.timing_only:  # 沒給 clips:提早檢查缺畫面
        miss = [l["idx"] for l in lines if not (l.get("shots") or l.get("img") or l.get("quote") or l.get("compare")
                                                or l.get("anim"))]
        if miss:
            sys.exit(f"缺畫面的句子編號 (未提供 --clips): {miss}")

    if args.check_only:
        if not args.timeline:
            sys.exit("--check-only 需要 --timeline")
        total = load_timeline(lines, args.timeline)
        total_frames = lines[-1]["f1"]
        total = total or total_frames / FPS
        if args.timing_only:
            sys.exit(1 if timing_only_check(lines, secs, tlmeta, args, media) else 0)
    else:
        ftag = (args.frozen or args.tag) if args.frozen is not None else None
        tts_all(lines, args.voice, args.rate, P.tts_dir(args.tag, args.tts_engine), args.tts_engine, tts_cmd, args.no_synth,
                frozen=ftag if ftag and FZ.load(ftag) else None, comma_profile=args.comma_profile)
        total, total_frames = build_timeline(lines, args.gap, args.section_gap, tlmeta, args.card_min, args.img_min)
    if args.tts_only:
        # 只含時間的 timeline,給 --check-only --timeline 用(不必先渲染一次)
        tl = dict(fps=FPS, total=total, total_frames=total_frames, voice=args.voice, rate=args.rate,
                  lines=[dict(idx=ln["idx"], text=ln["text"], start=ln["vstart"], end=ln["vend"],
                              visual_start=ln["f0"] / FPS, visual_end=ln["f1"] / FPS, clauses=clauses_abs(ln))
                         for ln in lines])
        (bdir / "timeline_tts.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"TTS 完成: {len(lines)} 句,語音+停頓總長 {total:.2f} 秒;快取在 {bdir / 'tts'}")
        return

    # ---- 鏡頭規劃:排時間 -> 不足最短時長的向相鄰影片借 -> 挑影片片段
    load_luma_cache(bdir / "luma_cache.json")
    errors, warns = [], []
    shots, errs = layout_shots(lines, lambda im: img_kind(media, im))
    errors += errs
    stitch_min(shots, args.img_min)
    shots, errs, w, usage, fixn = pick_videos(shots, media, clips, args.max_per_src, load_fallback(args.script))
    save_luma_cache()
    errors += errs
    warns += w
    missing = [s for s in shots if s.get("missing")]
    audio_cache = {}
    for n, s in enumerate(shots, 1):
        s.update(n=n, cards=[], file=bdir / "shots" / f"{n:04d}.mp4", pcm=bdir / "shots" / f"{n:04d}.pcm")
        if s["kind"] == "video":
            if s.get("missing"):
                continue
            p = media / "raw" / f"{s['src']}.mp4"
            if not p.exists():
                errors.append(f"{_line_span(s)}: raw/{s['src']}.mp4 不存在")
                s["missing"] = True
                missing.append(s)
                continue
            if s["src"] not in audio_cache:
                audio_cache[s["src"]] = False if args.check_only else probe_has_audio(p)
            s["has_audio"] = audio_cache[s["src"]]
            s["frame"] = frame_spec(media, s["src"], s.get("clip"))
            if s["frame"]["leak"] >= 3:
                warns.append(f"{_line_span(s)}: {s['src']} 放大到 {ZOOM_MAX} 倍仍有 {s['frame']['leak']:.0f}px 的字幕/浮水印區在畫面內")
        elif s.get("special") in ("quote", "compare"):
            ln = lines[s["line"] - lines[0]["idx"]]
            for name in special_imgs(ln):
                if not (media / "images" / f"{name}.png").exists():
                    errors.append(f"句{s['line']}: images/{name}.png 不存在")
        elif not s.get("special") and not (media / "images" / f"{s['img']}.png").exists():
            errors.append(f"{_line_span(s)}: images/{s['img']}.png 不存在")

    if args.portrait:
        for s in shots:
            s["label_lower"] = None
    else:
        top_style = json.loads(Path(args.script).read_text(encoding="utf-8")).get("label_style")
        errors += decide_labels(shots, lines, media, args.label_style, top_style)
    errors += precheck_images(shots, media)
    errors += check_text_clip(shots, media)
    errors += check_text_pad(shots)
    pushes = plan_push(shots, lines, media, enabled=not args.no_push and not args.portrait)
    if pushes:
        log(f"鏡頭推移: 靜態→靜態交界 {len(pushes)} 個,實際推移 {sum(1 for p in pushes if p[4])} 個"
            + ("(--no-push)" if args.no_push else ""))
        for pl, nl, pk, nk, z, note in pushes:
            log(f"  推移 句{pl}→句{nl} {pk} → {nk} 倍率 {z or '無'} {note}".rstrip())
    errors += check_image_runs(lines, args.img_min)
    errors += check_sub_seams(lines)
    errs, ncut = check_cuts(shots)
    errors += errs
    log(f"硬切檢查: 影片鏡頭 {sum(1 for s in shots if s['kind'] == 'video')} 個,有硬切資料 {ncut} 個,違反 {len(errs)} 個")
    errs, dstat = check_durations(shots, args.img_min)
    errors += errs
    del ANIM_WARNS[:]
    errors += check_anim(lines, shots, secs, tlmeta)
    warns += ANIM_WARNS
    spans, errs = plan_cards(lines, shots, args.card_min, total_frames)
    errors += errs
    trans, w = plan_trans(lines, secs)
    warns += w
    over = {src: u for src, u in usage.items() if u > args.max_per_src + 1e-6}
    for src, u in over.items():
        errors.append(f"來源 {src} 使用 {u:.1f} 秒 > 上限 {args.max_per_src:.0f} 秒")
    top = sorted(usage.items(), key=lambda kv: -kv[1])[:3]
    log("來源使用秒數(前三): " + ", ".join(f"{k} {v:.1f}" for k, v in top) + f" | 上限 {args.max_per_src:.0f}")
    if args.portrait:
        errs, w = check_portrait(lines, shots, total_frames / FPS, parse_len(args.len), args.hook, media)
        errors += errs
        warns += w
        if json.loads(Path(args.script).read_text(encoding="utf-8")).get("spoiler"):
            warns.append("直式不放劇透牌(script 有 spoiler,已略過)")
        if trans and not args.no_anim:
            warns.append(f"直式不疊段落轉場({len(trans)} 處已略過)")
    for s in shots:
        if s.get("special") == "anim":
            a0 = s["parts"][0]["anim"]
            log(f"動畫鏡頭 {_line_span(s)} [{a0.get('type')}]: {s['f0'] / FPS:.2f} - {(s['f0'] + s['frames']) / FPS:.2f} 秒"
                f"({s['frames'] / FPS:.2f} 秒)")
    errors += attach_kits(shots, lines)   # 小件分配到鏡頭 + 節制規則
    attach_label_lowers(shots)             # 截圖出處標籤改 lower 下標籤(不計入節制規則)
    errors += check_web_capacity(shots, tlmeta, media, portrait=args.portrait)   # 動畫容量:字級、安全區、重疊(模板實際排版量測)
    if any(s.get("kits") for s in shots):
        try:
            warns += [f"小件擺放: {m}" for m in plan_kits(shots, media)[1]]   # 放不下 / 找不到文字(圖表 el 的在渲染時才算)
            for m in cap_push_for_kits(shots):                                  # 小件離邊:push 推移減小
                log(f"  推移調整 {m}")
        except Exception as e:                                                 # 檢查失敗不擋渲染前檢查
            warns.append(f"小件擺放檢查失敗: {e}")
    for m in warns:
        log(f"警告: {m}")
    for m in errors:
        log(f"錯誤: {m}")
    log(f"渲染前檢查自動補救: 分段 {fixn['split']} 處 | 備援 {fixn['fallback']} 處 | 重用 {fixn['reuse']} 處 | "
        f"卡片提早 {sum(1 for sp in spans if sp.get('early'))} 處")
    log(f"渲染前檢查: 鏡頭 {len(shots)} 個 | 卡片 {len(spans)} 張 | 動畫鏡頭 {sum(1 for s in shots if s.get('special') == 'anim')} 個 | "
        f"警告 {len(warns)} | 錯誤 {len(errors)}")
    hl_tw = [h.get("tw") for s in shots for h in s.get("hls") or []]
    hl_hit = sum(1 for t in hl_tw if t is not None)
    log(f"底線卡詞: {hl_hit} 段對到詞、{len(hl_tw) - hl_hit} 段退回句首"
        + ("(--check-only 沒有品管對齊時間,全數退回不代表正式渲染)" if args.check_only else ""))
    # 鏡頭計畫存檔(--check-only 也寫):每個鏡頭的句子範圍、標籤、挑到的片段與其備註,方便渲染前對照旁白
    (bdir / "plan.json").write_text(json.dumps([dict(
        n=s["n"], lines=[s["line"], s.get("last_line") or s["line"]], start=round(s["f0"] / FPS, 2),
        dur=round(s["frames"] / FPS, 2), kind=kind_name(s), tag=s.get("tag"), src=s.get("src") or s.get("img"),
        src_start=s.get("start"), note=(s.get("clip") or {}).get("note"), zoom=(s.get("frame") or {}).get("zoom"),
        text_clip=s.get("text_clip"),
        text="".join(l["text"] for l in lines if s["line"] <= l["idx"] <= (s.get("last_line") or s["line"])))
        for s in shots], ensure_ascii=False, indent=1), encoding="utf-8")
    if args.check_only:
        sys.exit(1 if errors else 0)
    if missing:
        sys.exit("缺畫面,無法渲染(見上方錯誤)")
    if errors and not args.force:
        sys.exit("渲染前檢查有錯誤,未渲染(確定要渲染請加 --force)")

    # ---- 圖片 / 引言 / 對比 / 動畫鏡頭的素材
    for s in shots:
        if s["kind"] == "image":
            if s.get("special") == "anim":
                s["hl_layers"] = []
                s["aux"], s["tl_n"] = [build_anim_shot(s, tlmeta, media)], s["frames"]
            else:
                (prep_special if s.get("special") else prep_image)(s, media, bdir / "fx")
    prep_kits(shots, media)

    # ---- 卡片:每個顯示區間一張 PNG,疊在區間內的每個鏡頭上
    for sp in spans:
        png = bdir / "cards" / f"{sp['line']:03d}.png"
        make_card(sp["card"], png)
        c0, c1 = sp["f0"], sp["f1"]
        for s in shots:
            s0, s1 = s["f0"], s["f0"] + s["frames"]
            if s0 < c1 and s1 > c0:
                s["cards"].append(dict(png=png, t0=max(0, c0 - s0) / FPS, t1=(min(s1, c1) - s0) / FPS,
                                       fin=c0 >= s0, fout=c1 <= s1))

    # ---- timeline.json
    def shot_rec(s):
        return dict(n=s["n"], kind=s["kind"], special=s.get("special"), tag=s.get("tag"),
                    src=s.get("src") or s.get("img"), src_start=s.get("start"), line=s["line"],
                    last_line=s.get("last_line") or s["line"], start=s["f0"] / FPS,
                    end=(s["f0"] + s["frames"]) / FPS, frames=s["frames"],
                    anim=[p["anim"] for p in s["parts"]] if s.get("special") == "anim" else None,
                    zoom=(s.get("frame") or {}).get("zoom"))
    tl = dict(fps=FPS, total=total, total_frames=total_frames, voice=args.voice, rate=args.rate,
              shot_stats=dstat, shots=[shot_rec(s) for s in shots],
              cards=[dict(line=sp["line"], last_line=sp["last"], card=sp["card"], start=sp["f0"] / FPS,
                          end=sp["f1"] / FPS) for sp in spans], lines=[])
    for ln in lines:
        tl["lines"].append(dict(
            idx=ln["idx"], text=ln["text"], say=ln.get("say"), start=ln["vstart"], end=ln["vend"],
            visual_start=ln["f0"] / FPS, visual_end=ln["f1"] / FPS, card=ln.get("card"), hl=ln.get("hl"),
            clauses=clauses_abs(ln),
            shots=[s["n"] for s in shots if s["f0"] < ln["f1"] and s["f0"] + s["frames"] > ln["f0"]]))

    # 字幕 + 字型
    for stale in (bdir / "fonts").glob("*"):  # 只留字幕字型,避免 libass 選到舊檔
        stale.unlink()
    shutil.copy(SUB_FONT, bdir / "fonts" / Path(SUB_FONT).name)
    write_ass(lines, bdir / "subs.ass", shots)
    for t, ln in zip(tl["lines"], lines):
        t["phrases"] = ln["phrases"]
    (bdir / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")

    # 鏡頭
    log(f"鏡頭: 渲染 {len(shots)} 個 (4 平行)")
    with ThreadPoolExecutor(SHOT_WORKERS) as ex:
        for i, _ in enumerate(ex.map(lambda s: render_shot(s, media), shots), 1):
            if i % 20 == 0:
                log(f"  {i}/{len(shots)}")
    if args.portrait:
        hook_png = None
        if args.hook:
            hook_png = bdir / "hook.png"
            make_hook(args.hook, hook_png)
        (bdir / "shots_p").mkdir(exist_ok=True)
        for s in shots:
            s["pwin"] = portrait_window(s, lines[s["line"] - lines[0]["idx"]], media)
        kit_jobs = []
        for s in shots:           # 直式動畫鏡頭的小件(計畫 #5c):圖層在畫面窗 1080x1080 座標,疊在動畫上
            if s["pwin"].get("native") == "anim":
                kj, kw, ki = plan_kit_portrait(s, media)
                for m in kw:
                    log(f"警告: {m}")
                if kj:
                    s["pwin"]["kit"] = ki
                    kit_jobs.append(kj)
        if kit_jobs:
            log(f"直式小件: {len(kit_jobs)} 個圖層")
            AW.render(kit_jobs)
        AL.set_profile("portrait")      # 原生動畫用直式常數組(此階段不產橫式動畫)
        try:
            with ThreadPoolExecutor(SHOT_WORKERS) as ex:
                list(ex.map(lambda s: render_portrait_shot(s, hook_png, tlmeta, media), shots))
        finally:
            AL.set_profile("landscape")
        (bdir / "portrait.json").write_text(json.dumps([dict(
            n=s["n"], kind=kind_name(s), start=round(s["f0"] / FPS, 2), end=round((s["f0"] + s["frames"]) / FPS, 2), **s["pwin"])
            for s in shots], ensure_ascii=False, indent=1), encoding="utf-8")
        log("直式畫面窗: " + "; ".join(f"#{s['n']} {s['pwin']['why']} x0={s['pwin']['x0']} cw={s['pwin']['cw']} "
                                     f"y={s['pwin']['wy']}-{s['pwin']['wy'] + s['pwin']['wh']}" for s in shots))

    # 音訊
    build_voice(lines, total_frames, bdir / "voice.wav")
    voice_db = track_db(bdir / "voice.wav")
    bgm_vol = args.bgm_vol
    if args.bgm:
        bgm_path = P.find(args.bgm)
        if args.bgm_vol is not None:                  # 舊算法:明確給 --bgm-vol
            bgm_raw = track_db(bgm_path)              # 整首量,樣片與整支用同一個倍率
            bgm_vol = args.bgm_vol * bgm_norm(bgm_raw)
            log(f"BGM(舊算法): 原始 {bgm_raw if bgm_raw is None else round(bgm_raw, 1)} dBFS -> 對齊 {BGM_REF_DB} 後乘 {args.bgm_vol},實際增益 {bgm_vol:.4f}")
        else:                                         # 預設:對齊配音響度(整首量 3 秒窗,樣片與整支用同一個倍率)
            win = track_win_db(str(bgm_path))
            if win is None or voice_db is None:
                bgm_vol = 0.25 * bgm_norm(track_db(bgm_path))
                log(f"BGM: 量不到配音或曲子的響度,退回 0.25 × bgm_norm,實際增益 {bgm_vol:.4f}")
            else:
                side_db = bgm_sidecar_db(bgm_path)
                bgm_vol, g_db, which = bgm_gain_auto(voice_db, win, side_db + args.bgm_db)
                p10, p50, p90, mx = win
                log(f"BGM: 配音 RMS {voice_db:.1f} dBFS;曲 3 秒窗 p10/p50/p90/max = "
                    f"{p10:.1f}/{p50:.1f}/{p90:.1f}/{mx:.1f};套用 {'p90 條款(配音 - ' + str(BGM_BELOW_VOICE_DB) + ')' if which == 'p90' else '峰值上限(最大窗 ≤ 配音 - ' + str(BGM_PEAK_BELOW_VOICE_DB) + ')'};"
                    f"側檔 {side_db:+g} dB、命令列 --bgm-db {args.bgm_db:+g} dB;實際增益 {bgm_vol:.4f}({g_db:+.2f} dB);增益後 p90 比配音低 {voice_db - (p90 + g_db):.1f} dB、"
                    f"max 比配音低 {voice_db - (mx + g_db):.1f} dB")
                if p90 - p10 > BGM_DYN_P90_P10_DB or mx - p50 > BGM_DYN_MAX_P50_DB:
                    log("BGM 動態大(安靜段會幾乎聽不到/大聲段已被峰值上限壓住),評論片建議換平穩的曲子")
    if args.bed > 0:
        bgm_db = track_db(P.find(args.bgm), total_frames / FPS) if args.bgm else None
        if bgm_db is not None:
            bgm_db += 20 * math.log10(bgm_vol)
        target = bed_target(voice_db, bgm_db)
        bst = build_bed(shots, bdir / "bed.wav", target, args.bed)
        (bdir / "bed_gain.json").write_text(json.dumps(bst, ensure_ascii=False, indent=1), encoding="utf-8")
        gs = [b["gain"] for b in bst] or [0.0]
        outs = [b["out_db"] for b in bst if b["out_db"] is not None] or [0.0]
        fmt = lambda v: "無" if v is None else f"{v:.1f}"   # noqa: E731
        log(f"原聲: 目標 {target:.1f} dBFS(配音 {fmt(voice_db)}、BGM {fmt(bgm_db)});有原聲的影片鏡頭 {len(bst)} 個,"
            f"增益 最小 {min(gs):.4f} / 最大 {max(gs):.4f}(上限 {args.bed}),混入後最大 {max(outs):.1f} dBFS")

    # 合成
    with open(bdir / "concat.txt", "w", encoding="utf-8") as fh:
        fh.write("ffconcat version 1.0\n")
        for s in shots:
            fh.write(f"file '{'shots_p' if args.portrait else 'shots'}/{s['file'].name}'\nduration {s['frames'] / FPS:.6f}\n")
    T = total_frames / FPS
    # 圖片鏡頭與影片鏡頭的色彩標記不同(unknown / bt709),ffmpeg 遇到第一個不同的鏡頭會重建濾鏡圖,同一個圖裡緩衝中的聲音整段丟掉
    # (dei v1 在 0:16 少了 0.5 秒聲音,之後聲音提早、字幕對不上)。所以:concat 輸入加 -reinit_filter 0,聲音另開一個濾鏡圖。
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-reinit_filter", "0", "-f", "concat", "-safe", "0", "-i", "concat.txt", "-i", "voice.wav"]
    nxt = 2
    mix = []
    fc = ""
    veq = voice_eq_filter(args.voice_eq) or "anull"
    if args.bgm:
        fc += f"[1:a]{veq},asplit=2[vo][vsc];"
        mix.append("[vo]")
    else:
        fc += f"[1:a]{veq}[vo];"
        mix.append("[vo]")
    if args.bed > 0:
        cmd += ["-i", "bed.wav"]
        fc += f"[{nxt}:a]anull[b];"   # 每個鏡頭的增益已在 build_bed 乘進去
        mix.append("[b]")
        nxt += 1
    if args.bgm:
        cmd += ["-stream_loop", "-1", "-i", str(P.find(args.bgm))]
        fc += (f"[{nxt}:a]aresample={SR},aformat=channel_layouts=stereo,atrim=0:{T:.3f},asetpts=PTS-STARTPTS,"
               f"volume={bgm_vol:.5f},afade=t=in:st=0:d=2,afade=t=out:st={max(0.0, T - 2):.3f}:d=2[g0];"
               "[g0][vsc]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=600[gd];")
        mix.append("[gd]")
        nxt += 1
    fc += f"{''.join(mix)}amix=inputs={len(mix)}:duration=longest:normalize=0,alimiter=limit=0.97[a]"
    fv = ""
    # 影像:concat -> (段落轉場,預設沒有)-> 字幕(最上層)
    vlabel = "0:v"
    if not args.no_anim and trans and not args.portrait:   # 直式不疊段落轉場(檢查時已列警告)
        materialize_trans(trans)
        ex_in, vfl, vlabel = trans_filters(trans, nxt, "0:v")
        for pth in ex_in:
            cmd += ["-i", str(pth)]
        fv = ";".join(vfl) + ";" + fv
    sp_cfg = json.loads(Path(args.script).read_text(encoding="utf-8")).get("spoiler")
    if sp_cfg and not args.portrait:  # 劇透警告牌疊在字幕下層(直式不放,檢查時已列警告)(牌在畫面上方,不碰字幕帶)
        sp_in, sp_f = spoiler_filters(sp_cfg, bdir / "spoiler.png", nxt + (len(ex_in) if (not args.no_anim and trans) else 0),
                                      vlabel, "vsp")
        cmd += sp_in
        fv = sp_f + ";" + fv
        vlabel = "vsp"
    fv = (f"[{vlabel}]subtitles=subs.ass:fontsdir=fonts[v];" + fv).rstrip(";")
    (bdir / "final.fcs").write_text(fv, encoding="utf-8")  # 輸入檔多時命令列會過長,filter 改走檔案
    (bdir / "final_a.fcs").write_text(fc, encoding="utf-8")
    cmd += ["-filter_complex_script", "final.fcs", "-filter_complex_script", "final_a.fcs",
            "-map", "[v]", "-map", "[a]", "-t", f"{T:.6f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-movflags", "+faststart", out_path]
    log("合成最終影片...")
    run(cmd, cwd=bdir)
    gaps = audio_gaps(out_path)
    log(f"成片音軌時間戳缺口: {len(gaps)} 處" + "".join(f"; {a:.2f}s -> {b:.2f}s" for a, b in gaps[:5]))
    if gaps:
        log("錯誤: 成片音軌有缺口(混音掉了聲音,字幕與配音會對不上),不可交付(結束碼 1)")

    sheets = make_qa(shots, bdir)
    dur = probe_duration(out_path)
    log(f"總長度: {dur:.2f} 秒 (時間軸 {total:.2f})  句數: {len(lines)}  鏡頭數: {len(shots)}")
    log(f"QA 圖: {len(sheets)} 張 ({bdir})")
    log(f"輸出: {out_path}")
    if gaps:   # D20:成片已渲染完、檔留著供查,但結束碼非 0,make_version 收到即中止(不出 QA 圖、不交付)
        sys.exit(1)


if __name__ == "__main__":
    main()
