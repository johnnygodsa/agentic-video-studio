"""科普片合成:配音時間軸 + 多個動畫場景 + 字幕 + BGM → 一支 mp4,並出 QA 總覽圖。

用法:python -X utf8 pipeline\\sci\\make_film.py --tag sci_sample --ver v1 [--only N] [--strict] [--portrait]
輸入:<tag>\\film.json、build\\<tag>\\timeline_tts.json、build\\<tag>\\tts\\NNN.trim.wav
輸出:build\\<tag>\\film_timeline.json、output\\<tag>\\<tag>_<ver>.mp4、qa_<ver>.png(只印 30 行內摘要)
--only N 只重算第 N 個場景(從 1 起),其餘沿用 tmp\\film_<tag>_NN 已有的序列;--strict 場景檢查未過就中止。
模板場景:film.json 寫 {"tpl":"list","lines":[a,b],"data":{…}}(見 README §10.5);check 錯誤 → 摘要標「模板錯誤」、該場景放佔位畫面。
直式(Shorts):film.json 頂層 "portrait": true 或 --portrait → 1080x1920;版面數值取自 kit.js 的 LAYOUT.portrait(待 Shorts 實測修正)。
"""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import audio_consts as AC  # noqa: E402
import build as B  # noqa: E402  (字幕斷句、SUB_* 常數、響度量測)
import paths as P  # noqa: E402

FPS_SEQ, FPS_OUT, SR = 10, 30, 48000
SUB_OUTLINE, SUB_SHADOW = 6, 5                 # 科普頻道樣式(2026-10 定案)
SUB_OUTLINE_BGR = "&H00141B1B"                 # 墨色 #1B1414
BGM_VOL, BGM_FADE = 0.25, 1.5
SFX_VOL = 0.6                                    # 片頭/結語音效(channel\sfx\intro.wav、outro.wav;pipeline\sci\make_sfx.py 產生)
DOT_PUNCT = set(B.SUB_PUNCT) | set("。.")
# 直式字幕【判,待 Shorts 實測修正】:Fontsize 106(橫式 85 的 1.25 倍)、描邊 7、陰影 6、中心 (535,1400)(右側留 ≥140 給按鈕),
# 每段上限 11 個全形字(寬約 807px);build.SUB_MAX_W 是模組全域,直式時暫時改掉(不需改 build.py)
PORTRAIT_SUB = {"w": 1080, "h": 1920, "fs": 106, "outline": 7, "shadow": 6, "cx": 535, "cy": 1400, "max_w": 11}
LANDSCAPE_SUB = {"w": 1920, "h": 1080, "fs": B.SUB_FS, "outline": SUB_OUTLINE, "shadow": SUB_SHADOW, "cx": B.W // 2, "cy": B.SUB_CY,
                 "max_w": B.SUB_MAX_W}


def bgm_mix_filter(total, bgm_vol, duck=False):
    """BGM 增益 + 淡出 + 與配音混音的濾鏡字串(接在 [0:v] 之後;輸入 1 = 配音、2 = BGM,輸出 [a])。
    duck=True(只給有側檔的 AI 曲):與 build.py 同順序(增益 → 淡出 → sidechaincompress,參數相同),配音另分一路當側鏈。"""
    g = (f"[2:a]aresample={SR},aformat=channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
         f"volume={bgm_vol},afade=t=out:st={max(0.0, total - BGM_FADE):.3f}:d={BGM_FADE}[g];")
    if not duck:
        return g + "[1:a][g]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97[a]"
    return ("[1:a]asplit=2[vo][vsc];" + g + "[g][vsc]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=600[gd];"
            "[vo][gd]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97[a]")


def sub_clean(text):
    """字幕純文字:標點換半形空格(數字內的小數點保留),連續空格併一個、頭尾去空格。"""
    out = []
    for i, ch in enumerate(text):
        if ch == "." and 0 < i < len(text) - 1 and text[i - 1].isdigit() and text[i + 1].isdigit():
            out.append(ch)
        elif ch in DOT_PUNCT or ch.isspace():
            out.append(" ")
        else:
            out.append(ch)
    return re.sub(r" {2,}", " ", "".join(out)).strip()


# ---------- 時間軸 ----------
def plan(film, tts):
    """回傳 (scenes, lines_final, total)。邊界一律落在 0.1 秒格線(整數 ds);句子音檔仍放在真實時間。"""
    byidx = {l["idx"]: l for l in tts["lines"]}
    sc = film["scenes"]
    shift = 0.0
    items = []  # 每個場景:raw_t0(秒,含 shift)、lines、dur(僅 dur 場景)
    for i, s in enumerate(sc):
        if "lines" in s:
            a, b = s["lines"]
            ls = [byidx[k] for k in range(a, b + 1)]
            items.append({"raw": ls[0]["start"] + shift, "ls": ls, "shift": shift})
            shift += math.ceil(s.get("tail", 0.0) * 10 - 1e-6) / 10
        else:
            nxt = next((x for x in sc[i + 1:] if "lines" in x), None)
            if nxt:
                raw = byidx[nxt["lines"][0]]["start"] + shift
            else:
                prev = next((it for it in reversed(items) if it["ls"]), None)
                raw = (prev["ls"][-1]["end"] + prev["shift"]) if prev else 0.0
                raw += math.ceil(sc[i - 1].get("tail", 0.0) * 10 - 1e-6) / 10 if i and "lines" in sc[i - 1] else 0.0
            d = round(s["dur"] * 10) / 10
            items.append({"raw": raw, "ls": [], "shift": shift, "dur": d})
            shift += d
    last = items[-1]
    if last["ls"]:
        end = last["ls"][-1]["end"] + last["shift"] + math.ceil(sc[-1].get("tail", 0.0) * 10 - 1e-6) / 10
    else:
        end = last["raw"] + last["dur"]
    t0s = [int(math.floor(it["raw"] * 10 + 1e-6)) for it in items]
    t0s[0] = 0
    total_ds = max(int(math.ceil(end * 10 - 1e-6)), t0s[-1] + 1)
    scenes, flines = [], []
    for i, (s, it) in enumerate(zip(sc, items)):
        t0 = t0s[i] / 10
        t1 = (t0s[i + 1] if i + 1 < len(items) else total_ds) / 10
        ent = {"i": i + 1, "scene": s.get("scene") or f"tpl_{s['tpl']}", "t0": t0, "t1": t1, "dur": round(t1 - t0, 1), "lines": []}
        if "tpl" in s:                               # 模板場景(F4-0):算 scenes	pl.js,params 多帶 tpl、data
            ent["tpl"], ent["data"] = s["tpl"], s.get("data", {})
        for l in it["ls"]:
            st, en = l["start"] + it["shift"], l["end"] + it["shift"]
            ent["lines"].append({"idx": l["idx"], "text": l["text"], "start": round(st - t0, 3), "end": round(en - t0, 3)})
            flines.append({"idx": l["idx"], "scene": i + 1, "text": l["text"], "start": round(st, 3), "end": round(en, 3)})
        scenes.append(ent)
    return scenes, flines, total_ds / 10


# ---------- 算圖 ----------
def placeholder(frames, n, name, hue, size=(1920, 1080)):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(B.SUB_FONT, 120)
    img = Image.new("RGB", size, (36, 40, 52))
    d = ImageDraw.Draw(img)
    w = d.textlength(name, font=font)
    d.text(((size[0] - w) / 2, size[1] * 0.37), name, font=font, fill=(235, 235, 235))
    frames.mkdir(parents=True, exist_ok=True)
    for k in range(n):
        img.save(frames / f"f_{k:03d}.png")


def render_scene(tag, ent, hue, portrait=False):
    """回傳 (frames 目錄, 狀態字串, 失敗細節列表)。"""
    name = f"film_{tag}_{ent['i']:02d}"
    frames = P.TMP / name
    n = round(ent["dur"] * FPS_SEQ)
    scene = "tpl" if ent.get("tpl") else ent["scene"]
    if not (HERE / "scenes" / f"{scene}.js").exists():
        if frames.exists():
            shutil.rmtree(frames)
        placeholder(frames, n, ent["scene"], hue, (1080, 1920) if portrait else (1920, 1080))
        return frames, "佔位", []
    params = {"lines": [{k: l[k] for k in ("idx", "text", "start", "end")} for l in ent["lines"]]}
    if ent.get("tpl"):
        params.update(tpl=ent["tpl"], data=ent["data"])
    r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "render_clip.py"), scene, "--dur", str(ent["dur"]),
                        "--hue", str(hue), "--params", json.dumps(params, ensure_ascii=False), "--out", name, "--frames-only"] + (["--portrait"] if portrait else []),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout.splitlines() + r.stderr.splitlines()
    terr = [x.strip() for x in out if x.strip().startswith("模板錯誤")]
    if terr:                                         # 模板 check 錯誤:不論 --strict 都中止該場景,改放佔位畫面
        placeholder(frames, n, "模板錯誤 " + ent["scene"], hue, (1080, 1920) if portrait else (1920, 1080))
        return frames, "模板錯誤", terr[:3]
    warn = [x.strip() for x in out if x.strip().startswith("模板警告")]
    bad = [x.strip() for x in out if x.strip().startswith("未過") or "console 錯誤" in x and "錯誤 0" not in x
           or "Traceback" in x or x.strip().startswith(("Error", "ModuleNotFound", "FileNotFound"))]
    ok = r.returncode == 0 and len(list(frames.glob("f_*.png"))) == n
    return frames, "通過" if ok else "未過", bad[:3] if not ok else warn[:2]


# ---------- 聲音 ----------
def read_wav(path):
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getsampwidth() == 2, f"{path} 格式非 48k/16bit"
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
        return a.reshape(-1, w.getnchannels()) if w.getnchannels() > 1 else np.stack([a, a], 1)


def build_voice(flines, tts_dir, total, out, sfx=()):
    buf = np.zeros((int(total * SR) + SR, 2), np.float32)
    for l in flines:
        f = tts_dir / f"{l['idx']:03d}.trim.wav"
        if not f.exists():                           # 一行拆成子句時 build 只輸出 .line.wav
            f = tts_dir / f"{l['idx']:03d}.line.wav"
        a = read_wav(f)
        s = int(round(l["start"] * SR))
        buf[s:s + len(a)] += a[:len(buf) - s]
    for t, path in sfx:                              # 音效:(成片秒數, wav)
        a = read_wav(path) * SFX_VOL
        s = int(round(t * SR))
        buf[s:s + len(a)] += a[:len(buf) - s]
    pcm = (np.clip(buf[:int(total * SR)], -1, 1) * 32767).astype("<i2")
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------- 字幕 ----------
def write_ass(flines, path, S=LANDSCAPE_SUB):
    head = (
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {S['w']}\nPlayResY: {S['h']}\nWrapStyle: 2\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{B.SUB_FONT_NAME},{S['fs']},&H00FFFFFF,&H00FFFFFF,{SUB_OUTLINE_BGR},&H{B.SUB_SHADOW_ALPHA}000000,0,0,0,0,"
        f"100,100,0,0,1,{S['outline']},{S['shadow']},5,0,0,0,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, Effect, Text\n"
    )
    ev, texts = [], []
    B.SUB_MAX_W = S["max_w"]                         # split_phrases 讀這個模組全域
    for l in flines:
        ph = [(sub_clean(t), w) for t, w in B.split_phrases(l["text"])]
        ph = [(t, w) for t, w in ph if t]
        for text, s, e in B._spread(ph, l["start"], l["end"], l["end"]):
            texts.append(text)
            safe = text.replace("{", "(").replace("}", ")")
            ev.append(f"Dialogue: 1,{B._ass_t(s)},{B._ass_t(max(e, s + 0.15))},Default,,,"
                      f"{{\\an5\\pos({S['cx']},{S['cy'] + B.SUB_INK_DY * S['fs'] / B.SUB_FS:.1f})}}{safe}\n")
    path.write_text(head + "".join(ev), encoding="utf-8")
    return texts


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"指令失敗:{cmd[0]}\n{r.stderr[-1500:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ver", required=True)
    ap.add_argument("--only", type=int)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--portrait", action="store_true", help="直式 1080x1920(也可在 film.json 頂層寫 portrait: true)")
    a = ap.parse_args()
    film = json.loads((P.REPO / a.tag / "film.json").read_text(encoding="utf-8"))
    both = [i + 1 for i, s in enumerate(film["scenes"]) if ("scene" in s) == ("tpl" in s)]
    if both:
        sys.exit(f"film.json 場景 {both}:scene 與 tpl 必須擇一")
    bdir, odir = P.build_dir(a.tag), P.output_dir(a.tag)
    tts = json.loads((bdir / "timeline_tts.json").read_text(encoding="utf-8"))
    odir.mkdir(parents=True, exist_ok=True)
    scenes, flines, total = plan(film, tts)
    hue = film.get("hue", 46)
    portrait = bool(a.portrait or film.get("portrait"))
    S = PORTRAIT_SUB if portrait else LANDSCAPE_SUB
    (bdir / "film_timeline.json").write_text(
        json.dumps({"total": total, "scenes": scenes, "lines": flines}, ensure_ascii=False, indent=1), encoding="utf-8")

    summary, seq, fails = [], [], 0
    for ent in scenes:
        name = f"film_{a.tag}_{ent['i']:02d}"
        frames = P.TMP / name
        n = round(ent["dur"] * FPS_SEQ)
        if a.only and ent["i"] != a.only and len(list(frames.glob("f_*.png"))) == n:
            status, bad = "沿用", []
        else:
            frames, status, bad = render_scene(a.tag, ent, hue, portrait)
        if status in ("未過", "模板錯誤"):
            fails += 1
        summary.append(f"[{ent['i']}] {ent['scene']} {ent['t0']:.1f}–{ent['t1']:.1f}({ent['dur']:.1f}s) {status}"
                       + (":" + ";".join(bad) if bad else ""))
        seq += [frames / f"f_{k:03d}.png" for k in range(n)]
        if status == "未過" and a.strict:
            print("\n".join(summary))
            sys.exit("--strict:場景檢查未過")

    # 影像清單
    lst = ["ffconcat version 1.0"]
    for f in seq:
        lst.append(f"file '{f.as_posix()}'\nduration {1 / FPS_SEQ}")
    lst.append(f"file '{seq[-1].as_posix()}'")
    (bdir / "film_frames.txt").write_text("\n".join(lst), encoding="utf-8")
    sfx = []                                         # intro 開頭、outro 最後一句(「ChannelC?」)開頭
    for sc_ in scenes:
        w = P.ROOT / "channel" / "sfx" / f"{sc_['scene']}.wav"
        if sc_["scene"] in ("intro", "outro") and w.exists():
            ls_ = sc_.get("lines") or []
            sfx.append((sc_["t0"] + (ls_[-1]["start"] if sc_["scene"] == "outro" and ls_ else 0.0), w))
    build_voice(flines, bdir / "tts", total, bdir / "film_voice.wav", sfx)
    texts = write_ass(flines, bdir / "film_subs.ass", S)
    (bdir / "fonts").mkdir(exist_ok=True)
    for stale in (bdir / "fonts").glob("*"):
        stale.unlink()
    shutil.copy(B.SUB_FONT, bdir / "fonts" / Path(B.SUB_FONT).name)

    bgm = film.get("bgm")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", "film_frames.txt",
           "-i", "film_voice.wav"]
    fc = f"[0:v]fps={FPS_OUT},subtitles=film_subs.ass:fontsdir=fonts,format=yuv420p[v];"
    if bgm:
        bp = P.BGM / bgm
        bp = bp if bp.exists() else P.find(bgm)
        cmd += ["-stream_loop", "-1", "-i", str(bp)]
        bgm_vol = film.get("bgm_vol", BGM_VOL)
        side = AC.bgm_sidecar(bp)
        if "bgm_vol" not in film and "bgm_db" in side:   # 有側檔(AI 曲):與 build.py 同一套預設算法 + 側檔偏移
            voice_db, win = B.track_db(str(bdir / "film_voice.wav")), B.track_win_db(str(bp))
            if voice_db is not None and win is not None:
                bgm_vol, g_db, _ = AC.bgm_gain_auto(voice_db, win, AC.sidecar_db(side))
                print(f"BGM: 配音 RMS {voice_db:.1f} dBFS、側檔 {AC.sidecar_db(side):+g} dB、閃避 {'開' if side.get('duck', True) else '關'},實際增益 {bgm_vol:.4f}({g_db:+.2f} dB)")
        duck = AC.sidecar_duck(side)   # 有側檔的曲子才閃避(側檔 duck:false 可關)
        fc += bgm_mix_filter(total, bgm_vol, duck)
    else:
        fc += "[1:a]anull[a]"
    (bdir / "film_final.fcs").write_text(fc, encoding="utf-8")
    mp4 = odir / f"{a.tag}_{a.ver}.mp4"
    cmd += ["-filter_complex_script", "film_final.fcs", "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS_OUT),
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-movflags", "+faststart", str(mp4)]
    run(cmd, cwd=bdir)
    qa = odir / f"qa_{a.ver}.png"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4), "-vf",
         f"fps=1,scale=384:-1,tile=8x{math.ceil(total / 8)}", "-frames:v", "1", str(qa)])

    punct = [t for t in texts if any(c in B.SUB_PUNCT or c == "。" for c in t)]
    print(f"make_film {a.tag} {a.ver}{'(直式 1080x1920)' if portrait else ''}:總長 {total:.1f}s,{len(scenes)} 場景,{len(flines)} 句,{len(texts)} 段字幕")
    print("\n".join(summary))
    print(f"場景檢查未過 {fails} 個;字幕含標點 {len(punct)} 段;BGM {bgm or '無'}")
    print(f"→ {P.rel(mp4)}、{P.rel(qa)}、{P.rel(bdir / 'film_timeline.json')}")


if __name__ == "__main__":
    main()
