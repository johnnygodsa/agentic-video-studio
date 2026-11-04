#!/usr/bin/env python3
r"""離線示範:不用 GPU、模型、外部後端或 LLM,把 sample_script.txt 走過正式產線的模組做成一支短片。

python -X utf8 pipeline/demo/run_demo.py [--tts none|piper] [--out demo_out] [--script 檔]

串到的正式模組(只呼叫,不改行為):
  script_txt2json.parse / build_lines  文案格式解析(@title、@say、@def anim、# 段落、標籤|旁白)
  script_lint.sentence_hits            句級「AI 感」檢查(硬擋項命中就停)
  tts_cosy_text.apply_pron             讀音標注(只印出標注結果,示範不送配音引擎)
  pace.est_seconds                     依字數估時長(--tts none 的靜音軌長度)
  text_wrap.break_groups               畫面大字換行點(詞邊界、行首禁則)
  build.split_phrases / check_sub_seams / parse_anim / _spread   字幕切段(無標點、不拆詞)、接縫檢查、anim 欄位檢查、字幕時間分配
  director._item                       gate 項目格式(同 pipeline/gates/*.py 的 run 回傳)
  qa_sheet.grab                        從成片抽格做 QA 總覽圖
畫面用 Pillow 畫(標題卡、長條圖、一般畫面,字幕燒進畫面),ffmpeg 合成 mp4,另附 demo.srt。
--tts piper:選用 piper-tts(CPU、免費),中文聲音從 rhasspy/piper-voices 下載到 <out>/cache;沒裝或下載失敗退回 none。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import unicodedata
import urllib.request
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
sys.path.insert(0, str(PIPE))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import build as B  # noqa: E402
import director as D  # noqa: E402
import pace  # noqa: E402
import qa_sheet  # noqa: E402
import script_lint as SL  # noqa: E402
import script_txt2json as S2J  # noqa: E402
import text_wrap as TW  # noqa: E402
import tts_cosy_text as CT  # noqa: E402

W, H = 1280, 720
GAP = 0.35            # 句與句之間的靜音(秒)
DUR_RANGE = (20, 40)  # 示範片長度範圍(gate 檢查)
SR_NONE = 24000
PIPER_VOICE = "zh_CN-huayan-medium"
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/"
BG = (18, 22, 30)
ACCENT = (255, 196, 0)


def log(stage, msg):
    print(f"[{stage}] {msg}", flush=True)


# ---- 字型 ----
def find_font():
    """Linux:Noto Sans CJK;Windows:微軟正黑體;都沒有 -> None(PIL 預設字型,中文會缺字)。"""
    cands = [PIPE.parent / "fonts" / "NotoSansTC-SubBold.ttf"]
    if os.name == "nt":
        fd = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        cands += [fd / "msjhbd.ttc", fd / "msjh.ttc"]
    else:
        for d in (Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts"):
            if d.is_dir():
                cands += sorted(d.rglob("NotoSansCJK*Bold.ttc")) + sorted(d.rglob("NotoSansCJK*.ttc")) + sorted(d.rglob("NotoSans*CJK*.otf"))
    for p in cands:
        if p.is_file():
            return p
    return None


def font_index(path):
    """ttc 裡挑繁中(TC)那一套;沒有就 0。"""
    if path.suffix.lower() != ".ttc":
        return 0
    for i in range(8):
        try:
            if "TC" in " ".join(ImageFont.truetype(str(path), 20, index=i).getname()):
                return i
        except OSError:
            break
    return 0


class Fonts:
    def __init__(self):
        self.path = find_font()
        self.idx = font_index(self.path) if self.path else 0
        self.cache = {}
        if self.path:
            log("font", f"{self.path.name}(index {self.idx})")
        else:
            log("font", "警告:找不到 Noto Sans CJK / 微軟正黑體,改用 PIL 預設字型(中文會缺字)")

    def __call__(self, size):
        if size not in self.cache:
            self.cache[size] = (ImageFont.truetype(str(self.path), size, index=self.idx) if self.path
                                else ImageFont.load_default(size=size))
        return self.cache[size]


# ---- 文案 ----
def load_script(path):
    """同 script_txt2json.main:parse -> build_lines -> 套 @say;回傳 (標題, 句子 list,每句帶 idx / sec / sec_name)。"""
    title, says, sections, _top, defs, _skipped = S2J.parse(path.read_text(encoding="utf-8-sig"))
    lines = []
    for si, sec in enumerate(sections):
        for ln in S2J.build_lines(sec["rows"], defs):
            say = ln["text"]
            for k, v in says:
                say = say.replace(k, v)
            lines.append(dict(ln, say=say, idx=len(lines) + 1, sec=si, sec_name=sec["name"]))
    return title, lines


def stage_lint(lines):
    pseg = SL._pseg()
    hits = []
    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["text"] if i + 1 < len(lines) else None
        hits += SL.sentence_hits(ln["idx"], ln["text"], nxt, pseg)
    block = [h for h in hits if h["block"]]
    log("lint", f"{len(lines)} 句,命中 {len(hits)}(硬擋 {len(block)})")
    for h in hits:
        log("lint", f"  句{h['line']} {h['code']}{'(硬擋)' if h['block'] else ''}:{h['why']}")
    return block


def stage_pron(lines, out):
    rows = []
    for ln in lines:
        text, keys = CT.apply_pron(ln["say"])
        rows.append(f"{ln['idx']}\t{text}\t{','.join(keys)}")
        if keys:
            log("pron", f"句{ln['idx']} {len(keys)} 處:{'、'.join(keys)}")
    (out / "pron.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    log("pron", f"標注結果 -> {out.name}/pron.txt")


# ---- 配音 ----
def tts_none(lines):
    return [(pace.est_seconds(ln["say"]), None) for ln in lines], SR_NONE


def _download(url, dst):
    tmp = dst.with_suffix(dst.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.replace(dst)


def tts_piper(lines, cache):
    """每句 -> (秒數, 16-bit PCM bytes);任何失敗回傳 None(呼叫端退回 none)。"""
    try:
        from piper import PiperVoice
    except ImportError:
        log("tts", "警告:piper-tts 沒裝(pip install piper-tts),退回 none")
        return None
    cache.mkdir(parents=True, exist_ok=True)
    onnx = cache / f"{PIPER_VOICE}.onnx"
    try:
        for p in (onnx, cache / f"{PIPER_VOICE}.onnx.json"):
            if not p.is_file():
                log("tts", f"下載 {p.name}")
                _download(PIPER_BASE + p.name, p)
        voice = PiperVoice.load(str(onnx))
        out, sr = [], None
        for ln in lines:
            wp = cache / f"line_{ln['idx']:02d}.wav"
            with wave.open(str(wp), "wb") as wf:
                if hasattr(voice, "synthesize_wav"):
                    voice.synthesize_wav(ln["say"], wf)
                else:
                    voice.synthesize(ln["say"], wf)
            with wave.open(str(wp), "rb") as wf:
                sr = wf.getframerate()
                pcm = wf.readframes(wf.getnframes())
            out.append((len(pcm) / 2 / sr, pcm))
        return out, sr
    except Exception as e:  # noqa: BLE001 — 選用功能:任何失敗都退回 none
        log("tts", f"警告:piper 失敗({type(e).__name__}: {e}),退回 none")
        return None


def write_voice(path, clips, starts, total, sr):
    buf = bytearray(int(total * sr) * 2)
    for (_d, pcm), s in zip(clips, starts):
        if pcm:
            a = int(s * sr) * 2
            buf[a:a + len(pcm)] = pcm[:max(0, len(buf) - a)]
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(bytes(buf))


# ---- 字幕 ----
def stage_subs(lines, starts, durs, total):
    """build.split_phrases 切段(無標點、不拆詞),build._spread 依權重分配到該句時長;最後一段延到下一句開始。"""
    cues = []
    for i, ln in enumerate(lines):
        ph = B.split_phrases(ln["text"])
        end = starts[i + 1] if i + 1 < len(lines) else total
        for text, s, e in B._spread(ph, starts[i], starts[i] + durs[i], end):
            cues.append(dict(line=ln["idx"], text=text, start=s, end=e))
    log("subs", f"{len(cues)} 段字幕(每段上限 {B.SUB_MAX_W} 全形字)")
    return cues


def srt_time(x):
    ms = round(x * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(path, cues):
    path.write_text("".join(f"{k}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{c['text']}\n\n"
                            for k, c in enumerate(cues, 1)), encoding="utf-8")


# ---- gate ----
def stage_gate(lines, cues, block, total):
    """同 pipeline/gates/*.py 的 run():回傳 [item{id, ok, note, path}],全部 ok 才進下一段(渲染)。"""
    errs = []
    for ln in lines:
        if "anim" in ln:
            B.parse_anim(ln, None, errs)
    seams = B.check_sub_seams(lines)
    punct = [c["text"] for c in cues if any(unicodedata.category(ch)[0] == "P" and ch not in B.SUB_SYMBOLS for ch in c["text"])]
    items = [
        D._item("lint硬擋", not block, f"{len(block)} 句命中硬擋項"),
        D._item("anim欄位", not errs, ";".join(errs)),
        D._item("字幕接縫", not seams, ";".join(seams)),
        D._item("字幕無標點", not punct, "、".join(punct)),
        D._item("片長", DUR_RANGE[0] <= total <= DUR_RANGE[1], f"{total:.1f}s 不在 {DUR_RANGE[0]}–{DUR_RANGE[1]}s"),
    ]
    for it in items:
        log("gate", f"  {'ok ' if it['ok'] else 'NG '} {it['id']}{'' if it['ok'] else ':' + it['note']}")
    ok = all(it["ok"] for it in items)
    log("gate", f"D(demo) {'通過' if ok else '未過,停在渲染前'}:{sum(it['ok'] for it in items)}/{len(items)}")
    return ok


# ---- 畫面 ----
def text_center(dr, y, text, font, fill):
    w = dr.textlength(text, font=font)
    dr.text(((W - w) / 2, y), text, font=font, fill=fill)


def bg_canvas():
    im = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(im)
    for y in range(H):   # 上淡下深的漸層
        k = y / H
        dr.line([(0, y), (W, y)], fill=(int(30 - 12 * k), int(38 - 16 * k), int(54 - 24 * k)))
    return im


def draw_title(F, title, sub):
    im = bg_canvas()
    dr = ImageDraw.Draw(im)
    dr.rectangle([W / 2 - 60, 230, W / 2 + 60, 238], fill=ACCENT)
    text_center(dr, 260, title, F(84), (255, 255, 255))
    text_center(dr, 380, sub, F(32), (170, 180, 200))
    return im


def wrap_groups(dr, text, font, max_w):
    """text_wrap.break_groups 的切點貪婪排行(中文只在詞邊界換行)。"""
    rows = [""]
    for g in TW.break_groups(text):
        if rows[-1] and dr.textlength(rows[-1] + g, font=font) > max_w:
            rows.append(g.lstrip())
        else:
            rows[-1] += g
    return rows


def draw_plain(F, sec_name, idx, n, text):
    im = bg_canvas()
    dr = ImageDraw.Draw(im)
    f = F(60)
    rows = wrap_groups(dr, text, f, W - 320)
    y = (H - 140 - 84 * len(rows)) / 2 + 40
    for r in rows:
        dr.text((160, y), r, font=f, fill=(235, 238, 245))
        y += 84
    dr.rectangle([120, (H - 140 - 84 * len(rows)) / 2 + 48, 128, y - 20], fill=ACCENT)
    dr.text((60, 48), sec_name, font=F(40), fill=ACCENT)
    dr.text((60, 100), f"{idx} / {n}", font=F(26), fill=(150, 160, 180))
    for k in range(n):   # 進度點
        x = W - 60 - (n - k) * 28
        dr.ellipse([x, 60, x + 16, 76], fill=ACCENT if k < idx else (70, 80, 100))
    return im


def draw_bars(F, a):
    """anim bars(items = [[標籤, 數值], …]);step 語意同 build.parse_anim:k = 顯示第 0..k 條,"title" = 只有標題,省略 = 全部。"""
    items = B.bars_flat(a) or []
    step = a.get("step")
    shown = 0 if step == "title" else len(items) if not isinstance(step, int) else max(0, min(step + 1, len(items)))
    im = bg_canvas()
    dr = ImageDraw.Draw(im)
    text_center(dr, 50, a.get("title", ""), F(44), (255, 255, 255))
    vmax = max((v for _, v in items), default=1) or 1
    x0, x1, y0, row = 260, W - 180, 170, 110
    for k, (label, v) in enumerate(items):
        y = y0 + k * row
        dr.text((x0 - 30 - dr.textlength(label, font=F(40)), y + 8), label, font=F(40), fill=(220, 225, 235))
        dr.rectangle([x0, y, x1, y + 64], outline=(70, 80, 100), width=2)
        if k < shown:
            dr.rectangle([x0, y, x0 + (x1 - x0) * v / vmax, y + 64], fill=ACCENT if v == vmax else (90, 150, 230))
            dr.text((x0 + (x1 - x0) * v / vmax + 14, y + 10), f"{v:g}", font=F(36), fill=(255, 255, 255))
    if a.get("src"):
        dr.text((60, H - 180), f"來源:{a['src']}", font=F(24), fill=(140, 150, 170))
    return im


def burn_sub(F, im, text):
    im = im.copy()
    dr = ImageDraw.Draw(im)
    f = F(46)
    w = dr.textlength(text, font=f)
    dr.text(((W - w) / 2, H - 110), text, font=f, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    return im


def stage_frames(F, title, lines, cues, total, fdir):
    """每段字幕一張畫面(鏡頭底圖 + 燒字幕);回傳 [(檔名, 秒數)]。"""
    shots = {}
    for ln in lines:
        if "anim" in ln and ln["anim"].get("type") == "bars":
            shots[ln["idx"]] = draw_bars(F, ln["anim"])
        elif ln.get("v") == "title":
            shots[ln["idx"]] = draw_title(F, title, "agentic video studio · offline demo")
        else:
            shots[ln["idx"]] = draw_plain(F, ln["sec_name"], ln["idx"], len(lines), ln["text"])
    seq = []
    for k, c in enumerate(cues):
        name = f"f{k:03d}.png"
        burn_sub(F, shots[c["line"]], c["text"]).save(fdir / name)
        end = cues[k + 1]["start"] if k + 1 < len(cues) else total
        seq.append((name, max(end - c["start"], 1 / 30)))
    kinds = {"bars": sum(1 for ln in lines if "anim" in ln), "title": sum(1 for ln in lines if ln.get("v") == "title")}
    log("frames", f"{len(seq)} 張(標題卡 {kinds['title']} 句、長條圖 {kinds['bars']} 句、其餘一般畫面)")
    return seq


def stage_render(seq, fdir, voice, mp4):
    lst = "".join(f"file '{n}'\nduration {d:.3f}\n" for n, d in seq) + f"file '{seq[-1][0]}'\n"
    (fdir / "list.txt").write_text(lst, encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-i", str(voice.resolve()),
           "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", str(mp4.resolve())]
    subprocess.run(cmd, cwd=fdir, check=True)
    log("render", f"{mp4.name} {mp4.stat().st_size / 1024:.0f} KB")


def stage_qa(mp4, total, path, F, n=8, cols=4):
    """qa_sheet.grab 等距抽 n 格,拼成一張總覽圖(左上標時間)。"""
    cw, ch = qa_sheet.CW, qa_sheet.CH
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cw * cols, ch * rows), (0, 0, 0))
    dr = ImageDraw.Draw(sheet)
    for k in range(n):
        t = total * (k + 0.5) / n
        x, y = k % cols * cw, k // cols * ch
        sheet.paste(qa_sheet.grab(mp4, t), (x, y))
        dr.rectangle([x + cw - 80, y + ch - 30, x + cw, y + ch], fill=(0, 0, 0))
        dr.text((x + cw - 74, y + ch - 28), f"{t:4.1f}s", font=F(20), fill=ACCENT)
    sheet.save(path, optimize=True)
    log("qa", f"{path.name} {n} 格")


def main():
    ap = argparse.ArgumentParser(description="離線示範片(不需 GPU / 模型 / 外部後端)")
    ap.add_argument("--tts", choices=("none", "piper"), default="none")
    ap.add_argument("--out", default="demo_out")
    ap.add_argument("--script", default=str(HERE / "sample_script.txt"))
    a = ap.parse_args()
    out = Path(a.out).resolve()
    fdir = out / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg"):
        sys.exit("[render] 找不到 ffmpeg(請先安裝並加入 PATH)")

    title, lines = load_script(Path(a.script))
    log("script", f"《{title}》{len(lines)} 句、{len({ln['sec'] for ln in lines})} 段")
    (out / "script.json").write_text(json.dumps(dict(title=title, lines=lines), ensure_ascii=False, indent=1), encoding="utf-8")
    block = stage_lint(lines)
    stage_pron(lines, out)

    got = tts_piper(lines, out / "cache") if a.tts == "piper" else None
    engine = "piper" if got else "none"
    clips, sr = got or tts_none(lines)
    durs = [d for d, _ in clips]
    starts, t = [], 0.3
    for d in durs:
        starts.append(t)
        t += d + GAP
    total = t
    voice = out / "voice.wav"
    write_voice(voice, clips, starts, total, sr)
    log("tts", f"{engine}:{total:.1f}s({'依字數估時長的靜音軌' if engine == 'none' else PIPER_VOICE})")

    cues = stage_subs(lines, starts, durs, total)
    write_srt(out / "demo.srt", cues)
    if not stage_gate(lines, cues, block, total):
        sys.exit(2)

    F = Fonts()
    seq = stage_frames(F, title, lines, cues, total, fdir)
    mp4 = out / "demo.mp4"
    stage_render(seq, fdir, voice, mp4)
    stage_qa(mp4, total, out / "contact_sheet.png", F)
    log("done", f"{out.name}/demo.mp4、demo.srt、contact_sheet.png")


if __name__ == "__main__":
    main()
