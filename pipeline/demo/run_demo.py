#!/usr/bin/env python3
r"""離線示範:不用 GPU、模型、外部後端或 LLM,把 sample_script.txt 走過正式產線的模組做成一支短片。

python -X utf8 pipeline/demo/run_demo.py [--tts none|piper] [--out demo_out] [--script 檔] [--lang auto|zh|en][--theme midnight|paper|neon|bold|x.json](預設英文範例 sample_script_en.txt)

串到的正式模組(只呼叫,不改行為):
  script_txt2json.parse / build_lines  文案格式解析(@title、@say、@def anim、# 段落、標籤|旁白)
  script_lint.sentence_hits            句級「AI 感」檢查(硬擋項命中就停)
  tts_cosy_text.apply_pron             讀音標注(只印出標注結果,示範不送配音引擎)
  pace.est_seconds                     依字數估時長(--tts none 的靜音軌長度)
  text_wrap.break_groups               畫面大字換行點(詞邊界、行首禁則)
  build.split_phrases / check_sub_seams / parse_anim / _spread   字幕切段(無標點、不拆詞)、接縫檢查、anim 欄位檢查、字幕時間分配
  director._item                       gate 項目格式(同 pipeline/gates/*.py 的 run 回傳)
  qa_sheet.grab                        從成片抽格做 QA 總覽圖
畫面用 Pillow 畫(標題卡、長條圖、一般畫面,字幕燒進畫面;--theme 換背景、配色、排版,見 themes.py),ffmpeg 合成 mp4,另附 demo.srt。
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

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont  # noqa: E402

import build as B  # noqa: E402
import director as D  # noqa: E402
import pace  # noqa: E402
import qa_sheet  # noqa: E402
import script_lint as SL  # noqa: E402
import script_txt2json as S2J  # noqa: E402
import text_wrap as TW  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
from themes import THEMES, load_theme  # noqa: E402

W, H = 1280, 720
GAP = 0.35            # 句與句之間的靜音(秒)
DUR_RANGE = (20, 40)  # 示範片長度範圍(gate 檢查)
SR_NONE = 24000
PIPER_VOICE = "zh_CN-huayan-medium"
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/"
T = THEMES["midnight"]   # 目前畫面主題(--theme;資料在 themes.py)
THEME_NAME = "midnight"
_BG = None            # 背景底圖快取(換主題時清掉)
LANG = "zh"           # main() 依 --lang 設定;en = 英文文案(略過中文專用的 lint 與讀音、依字數改依單字估時長、字幕依單字切)
EN_WPS = 2.6          # 英文旁白每秒單字數(估時長用)
EN_SUB_MAX = 42       # 英文字幕每段上限字元數


def detect_lang(lines):
    """CJK 字少於字母的 1/3 視為英文文案。"""
    t = "".join(ln["text"] for ln in lines)
    cjk = sum(1 for ch in t if "一" <= ch <= "鿿")
    latin = sum(1 for ch in t if ch.isascii() and ch.isalpha())
    return "en" if cjk * 3 < latin else "zh"


def en_strip(text):
    """英文字幕去標點(與中文字幕同規格:無標點);字內撇號保留。"""
    return "".join(ch for ch in text if ch == "'" or unicodedata.category(ch)[0] != "P").strip()


def en_phrases(text, cap=EN_SUB_MAX):
    """英文字幕切段:只在單字邊界切,每段 <= cap 字元。"""
    out = [""]
    for w in en_strip(text).split():
        if out[-1] and len(out[-1]) + 1 + len(w) > cap:
            out.append(w)
        else:
            out[-1] = f"{out[-1]} {w}".strip()
    return [(x, float(len(x))) for x in out if x]   # 同 build.split_phrases 回傳 (文字, 權重)


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
    if LANG == "en":
        log("lint", "英文文案:script_lint 規則是中文專用,略過(正式產線請換成你語言的規則)")
        return []
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
    if LANG == "en":
        (out / "pron.txt").write_text("".join(f"{ln['idx']}\t{ln['say']}\t\n" for ln in lines), encoding="utf-8")
        log("pron", "英文文案:中文多音字標注略過")
        return
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
    if LANG == "en":
        return [(max(1.0, len(ln["say"].split()) / EN_WPS), None) for ln in lines], SR_NONE
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
        ph = en_phrases(ln["text"]) if LANG == "en" else B.split_phrases(ln["text"])
        end = starts[i + 1] if i + 1 < len(lines) else total
        for text, s, e in B._spread(ph, starts[i], starts[i] + durs[i], end):
            cues.append(dict(line=ln["idx"], text=text, start=s, end=e))
    log("subs", f"{len(cues)} 段字幕(每段上限 " + (f"{EN_SUB_MAX} 字元)" if LANG == "en" else f"{B.SUB_MAX_W} 全形字)"))
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
    seams = [] if LANG == "en" else B.check_sub_seams(lines)   # 接縫詞檢查是中文斷詞;英文字幕只在單字邊界切
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


# ---- 畫面 ----(顏色與版面依 --theme;主題資料在 themes.py,T = 目前主題)
def set_theme(spec):
    global T, THEME_NAME, _BG
    THEME_NAME, T = load_theme(spec)
    _BG = None
    log("theme", THEME_NAME)


def fit(dr, text, F, size, max_w, lo=28):
    """字級由 size 往下縮到 text 放得進 max_w。"""
    while size > lo and dr.textlength(text, font=F(size)) > max_w:
        size -= 2
    return size


def text_center(dr, y, text, font, fill):
    w = dr.textlength(text, font=font)
    dr.text(((W - w) / 2, y), text, font=font, fill=fill)


def glow(im, fn, radius=10):
    """fn(draw) 畫在黑底圖層,高斯模糊後加亮疊回 im(發光);之後在 im 上再畫的線條就是清晰的芯。"""
    layer = Image.new("RGB", im.size, (0, 0, 0))
    fn(ImageDraw.Draw(layer))
    im.paste(ImageChops.add(im, layer.filter(ImageFilter.GaussianBlur(radius))))


def overlay(im, fn):
    """fn(draw) 畫在透明 RGBA 圖層(可用半透明色),再 alpha 合成回 im。"""
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(ov))
    im.paste(Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB"))


def _make_bg():
    kind, top, bot = T["bg"], T["bg_top"], T["bg_bot"]
    if kind == "gradient":   # 上淡下深
        im = Image.new("RGB", (W, H), T["base"])
        dr = ImageDraw.Draw(im)
        for y in range(H):
            k = y / H
            dr.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(top, bot)))
        return im
    if kind == "paper":   # 紙色 + 細格線
        im = Image.new("RGB", (W, H), T["base"])
        dr = ImageDraw.Draw(im)
        for x in range(0, W, 40):
            dr.line([(x, 0), (x, H)], fill=T["grid"], width=1)
        for y in range(0, H, 40):
            dr.line([(0, y), (W, y)], fill=T["grid"], width=1)
        return im
    if kind == "neon":   # 對角漸層 + 兩團模糊光暈
        small = Image.new("L", (64, 36))
        small.putdata([int(255 * (x / 63 + y / 35) / 2) for y in range(36) for x in range(64)])
        im = Image.composite(Image.new("RGB", (W, H), bot), Image.new("RGB", (W, H), top), small.resize((W, H), Image.BILINEAR))
        layer = Image.new("RGB", (W, H), (0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse([-260, -240, 520, 340], fill=tuple(c // 4 for c in T["glow1"]))
        ld.ellipse([780, 420, 1500, 960], fill=tuple(c // 5 for c in T["glow2"]))
        im.paste(ImageChops.add(im, layer.filter(ImageFilter.GaussianBlur(120))))
        return im
    return Image.new("RGB", (W, H), T["base"])   # flat


def bg_canvas():
    global _BG
    if _BG is None:
        _BG = _make_bg()
    return _BG.copy()


def draw_title(F, title, sub):
    im = bg_canvas()
    dr = ImageDraw.Draw(im)
    st = T["title"]
    if st == "center":
        dr.rectangle([W / 2 - 60, 230, W / 2 + 60, 238], fill=T["accent"])
        size = 84
        while size > 40 and dr.textlength(title, font=F(size)) > W - 160:   # 長標題(英文)縮字到放得下
            size -= 4
        text_center(dr, 260 + (84 - size) // 2, title, F(size), T["text_hi"])
        text_center(dr, 380, sub, F(32), T["text_dim"])
    elif st == "left":   # 編輯風:粗色塊線 + 靠左標題 + 細底線
        dr.rectangle([100, 200, 660, 218], fill=T["accent"])
        size = fit(dr, title, F, 84, W - 200, 40)
        dr.text((100, 256), title, font=F(size), fill=T["text_hi"])
        dr.text((100, 256 + size + 40), sub, font=F(32), fill=T["text_dim"])
        dr.line([(100, 500), (W - 100, 500)], fill=T["text"], width=2)
    elif st == "card":   # 霓虹:置中外框卡片
        box = [120, 150, W - 120, 500]
        glow(im, lambda d: d.rounded_rectangle(box, 34, outline=T["accent"], width=10), 16)
        overlay(im, lambda d: d.rounded_rectangle(box, 34, fill=T["card_fill"]))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle(box, 34, outline=T["accent"], width=3)
        dr.rounded_rectangle([box[0] + 14, box[1] + 14, box[2] - 14, box[3] - 14], 24, outline=T["accent2"], width=1)
        glow(im, lambda d: d.rounded_rectangle([W / 2 - 70, 200, W / 2 + 70, 210], 5, fill=T["accent"]), 8)
        dr.rounded_rectangle([W / 2 - 70, 200, W / 2 + 70, 210], 5, fill=T["accent"])
        size = fit(dr, title, F, 80, W - 360, 40)
        tw = dr.textlength(title, font=F(size))
        glow(im, lambda d: d.text(((W - tw) / 2, 262 + (80 - size) // 2), title, font=F(size), fill=T["accent2"]), 12)
        text_center(dr, 262 + (80 - size) // 2, title, F(size), T["text_hi"])
        text_center(dr, 392, sub, F(30), T["text_dim"])
    else:   # poster:上方黑色大塊 + 紅帶,標題靠左白字,副標在黃底
        dr.rectangle([0, 0, W, 440], fill=T["block"])
        dr.rectangle([0, 440, W, 466], fill=T["accent"])
        dr.rectangle([80, 90, 80 + 150, 90 + 18], fill=T["accent"])
        size = fit(dr, title, F, 96, W - 160, 40)
        dr.text((80, 330 - size), title, font=F(size), fill=T["text_hi"])
        dr.text((80, 488), sub, font=F(34), fill=T["text"])
    return im


def wrap_groups(dr, text, font, max_w):
    """text_wrap.break_groups 的切點貪婪排行(中文只在詞邊界換行)。"""
    rows = [""]
    for g in ([w + " " for w in text.split()] if LANG == "en" else TW.break_groups(text)):
        if rows[-1] and dr.textlength(rows[-1] + g, font=font) > max_w:
            rows.append(g.lstrip())
        else:
            rows[-1] += g
    return rows


def draw_plain(F, sec_name, idx, n, text):
    im = bg_canvas()
    dr = ImageDraw.Draw(im)
    st = T["plain"]
    f = F(60)
    if st == "rail":   # 左側細條 + 段名在左上、進度點在右上
        rows = wrap_groups(dr, text, f, W - 320)
        y = (H - 140 - 84 * len(rows)) / 2 + 40
        for r in rows:
            dr.text((160, y), r, font=f, fill=T["text"])
            y += 84
        dr.rectangle([120, (H - 140 - 84 * len(rows)) / 2 + 48, 128, y - 20], fill=T["accent"])
        dr.text((60, 48), sec_name, font=F(40), fill=T["accent"])
        dr.text((60, 100), f"{idx} / {n}", font=F(26), fill=T["text_mute"])
        for k in range(n):   # 進度點
            x = W - 60 - (n - k) * 28
            dr.ellipse([x, 60, x + 16, 76], fill=T["accent"] if k < idx else T["track"])
    elif st == "editorial":   # 段名 + 頁碼在細線上,細線下是分段進度,引言粗條靠左
        rows = wrap_groups(dr, text, f, W - 330)
        y0 = 130 + (H - 170 - 130 - 84 * len(rows)) / 2
        for k, r in enumerate(rows):
            dr.text((150, y0 + 84 * k), r, font=f, fill=T["text"])
        dr.rectangle([100, y0 + 8, 114, y0 + 84 * len(rows) - 12], fill=T["accent"])
        dr.text((100, 44), sec_name, font=F(40), fill=T["accent"])
        pg = f"{idx} / {n}"
        dr.text((W - 100 - dr.textlength(pg, font=F(28)), 54), pg, font=F(28), fill=T["text_dim"])
        gap = 8
        sw = (W - 200 - gap * (n - 1)) / n
        for k in range(n):
            x = 100 + k * (sw + gap)
            dr.rectangle([x, 106, x + sw, 111], fill=T["text"] if k < idx else T["track"])
    elif st == "glow":   # 段名膠囊 + 發光圓點 + 圓角發光引言條
        rows = wrap_groups(dr, text, f, W - 380)
        y0 = 130 + (H - 170 - 130 - 84 * len(rows)) / 2
        for k, r in enumerate(rows):
            dr.text((170, y0 + 84 * k), r, font=f, fill=T["text"])
        pw = dr.textlength(sec_name, font=F(36)) + 44
        pill = [60, 40, 60 + pw, 100]
        qbar = [120, y0 + 6, 130, y0 + 84 * len(rows) - 10]
        dots = [(W - 60 - (n - k) * 30, 62) for k in range(idx)]

        def lights(d):
            d.rounded_rectangle(pill, 30, outline=T["accent2"], width=4)
            d.rounded_rectangle(qbar, 5, fill=T["accent"])
            for x, y in dots:
                d.ellipse([x, y, x + 16, y + 16], fill=T["accent"])
        glow(im, lights, 10)
        dr.rounded_rectangle(pill, 30, outline=T["accent2"], width=2)
        dr.text((82, 46), sec_name, font=F(36), fill=T["accent2"])
        dr.rounded_rectangle(qbar, 5, fill=T["accent"])
        dr.text((64, 114), f"{idx} / {n}", font=F(26), fill=T["text_mute"])
        for k in range(n):
            x, y = W - 60 - (n - k) * 30, 62
            dr.ellipse([x, y, x + 16, y + 16], fill=T["accent"] if k < idx else T["track"])
    else:   # side:左側黑欄(段名色塊標籤、大頁碼、方塊進度),右側粗字
        bw = 280
        dr.rectangle([0, 0, bw, H], fill=T["block"])
        s = fit(dr, sec_name, F, 36, bw - 40 - 32, 24)
        tw = dr.textlength(sec_name, font=F(s))
        dr.rectangle([40, 60, 40 + tw + 32, 60 + s + 28], fill=T["tag_bg"])
        dr.text((56, 74), sec_name, font=F(s), fill=T["tag_fg"])
        dr.text((40, 190), f"{idx:02d}", font=F(130), fill=T["base"])
        dr.text((44, 350), f"/ {n:02d}", font=F(32), fill=T["dot_off"])
        step = min(28, (bw - 80) // n)
        for k in range(n):
            x = 40 + k * step
            dr.rectangle([x, H - 210, x + step - 8, H - 210 + step - 8], fill=T["base"] if k < idx else T["dot_off"])
        rows = wrap_groups(dr, text, F(64), W - 360 - 80)
        y0 = 50 + (H - 180 - 50 - 84 * len(rows)) / 2
        for k, r in enumerate(rows):
            dr.text((370, y0 + 84 * k), r, font=F(64), fill=T["text"])
        dr.rectangle([334, y0 + 6, 350, y0 + 84 * len(rows) - 10], fill=T["accent"])
    return im


def draw_bars(F, a):
    """anim bars(items = [[標籤, 數值], …]);step 語意同 build.parse_anim:k = 顯示第 0..k 條,"title" = 只有標題,省略 = 全部。"""
    items = B.bars_flat(a) or []
    step = a.get("step")
    shown = 0 if step == "title" else len(items) if not isinstance(step, int) else max(0, min(step + 1, len(items)))
    im = bg_canvas()
    dr = ImageDraw.Draw(im)
    st = T["bars"]
    title = a.get("title", "")
    vmax = max((v for _, v in items), default=1) or 1
    nd = 0 if all(float(v).is_integer() for _, v in items) else 1   # 有小數就全部同位數(4.0 不顯示成 4)
    src = (f"Source: {a['src']}" if LANG == "en" else f"來源:{a['src']}") if a.get("src") else ""
    col = lambda v: T["bar_hi"] if v == vmax else T["bar"]   # noqa: E731
    if st == "classic":
        text_center(dr, 50, title, F(44), T["text_hi"])
        x0, x1, y0, row = 260, W - 180, 170, 110
        for k, (label, v) in enumerate(items):
            y = y0 + k * row
            dr.text((x0 - 30 - dr.textlength(label, font=F(40)), y + 8), label, font=F(40), fill=T["label"])
            dr.rectangle([x0, y, x1, y + 64], outline=T["track"], width=2)
            if k < shown:
                dr.rectangle([x0, y, x0 + (x1 - x0) * v / vmax, y + 64], fill=col(v))
                dr.text((x0 + (x1 - x0) * v / vmax + 14, y + 10), f"{v:.{nd}f}", font=F(36), fill=T["bar_text"])
        if src:
            dr.text((60, H - 180), src, font=F(24), fill=T["src"])
    elif st == "thin":   # 標籤在細長條上方,數值在條尾
        dr.text((100, 44), title, font=F(fit(dr, title, F, 44, W - 200)), fill=T["text_hi"])
        dr.line([(100, 112), (W - 100, 112)], fill=T["text"], width=2)
        x0, x1, y0, row = 100, W - 220, 150, 112
        for k, (label, v) in enumerate(items):
            y = y0 + k * row
            dr.text((x0, y), label, font=F(32), fill=T["label"])
            dr.rectangle([x0, y + 52, x1, y + 70], fill=T["track"])
            if k < shown:
                xe = x0 + (x1 - x0) * v / vmax
                dr.rectangle([x0, y + 52, xe, y + 70], fill=col(v))
                dr.text((xe + 16, y + 42), f"{v:.{nd}f}", font=F(32), fill=T["bar_text"])
        if src:
            dr.text((100, H - 210), src, font=F(24), fill=T["src"])
    elif st == "round":   # 圓角長條 + 發光
        ts = fit(dr, title, F, 44, W - 200)
        tw = dr.textlength(title, font=F(ts))
        glow(im, lambda d: d.text(((W - tw) / 2, 50), title, font=F(ts), fill=T["accent2"]), 12)
        text_center(dr, 50, title, F(ts), T["text_hi"])
        x0, x1, y0, row = 260, W - 180, 170, 110
        rects = [(k, v, [x0, y0 + k * row, x0 + max((x1 - x0) * v / vmax, 64), y0 + k * row + 64]) for k, (_, v) in enumerate(items) if k < shown]
        glow(im, lambda d: [d.rounded_rectangle(r, 32, fill=col(v)) for _, v, r in rects], 14)
        dr = ImageDraw.Draw(im)
        for k, (label, v) in enumerate(items):
            y = y0 + k * row
            dr.text((x0 - 30 - dr.textlength(label, font=F(40)), y + 8), label, font=F(40), fill=T["label"])
            dr.rounded_rectangle([x0, y, x1, y + 64], 32, outline=T["track"], width=3)
        for k, v, r in rects:
            dr.rounded_rectangle(r, 32, fill=col(v))
            dr.text((r[2] + 14, r[1] + 10), f"{v:.{nd}f}", font=F(36), fill=T["bar_text"])
        if src:
            dr.text((60, H - 205), src, font=F(24), fill=T["src"])
    else:   # block:上方黑帶放標題,方形長條,數值寫在條內
        dr.rectangle([0, 0, W, 130], fill=T["block"])
        dr.rectangle([0, 130, W, 144], fill=T["accent"])
        dr.text((60, 65), title, font=F(fit(dr, title, F, 52, W - 120)), fill=T["text_hi"], anchor="lm")
        x0, x1, y0, row = 290, W - 80, 180, 110
        for k, (label, v) in enumerate(items):
            y = y0 + k * row
            dr.text((x0 - 24 - dr.textlength(label, font=F(40)), y + 12), label, font=F(40), fill=T["label"])
            dr.rectangle([x0, y, x1, y + 76], outline=T["track"], width=5)
            if k < shown:
                xe = x0 + (x1 - x0) * v / vmax
                dr.rectangle([x0, y, xe, y + 76], fill=col(v))
                vt = f"{v:.{nd}f}"
                tw = dr.textlength(vt, font=F(46))
                if xe - x0 > tw + 50:
                    dr.text((xe - 24 - tw, y + 38), vt, font=F(46), fill=T["bar_text"], anchor="lm")
                else:
                    dr.text((xe + 14, y + 38), vt, font=F(46), fill=T["text"], anchor="lm")
        if src:
            dr.text((60, H - 215), src, font=F(26), fill=T["src"])
    return im


def burn_sub(F, im, text):
    im = im.copy()
    dr = ImageDraw.Draw(im)
    st = T["sub"]
    if st == "stroke":
        f = F(46)
        w = dr.textlength(text, font=f)
        dr.text(((W - w) / 2, H - 110), text, font=f, fill=T["sub_fg"], stroke_width=4, stroke_fill=T["sub_stroke"])
        return im
    f = F(fit(dr, text, F, 46, W - 140, 30))
    if st == "pill":   # 半透明圓角底 + 青色細邊
        w = dr.textlength(text, font=f)
        box = [(W - w) / 2 - 38, H - 160, (W + w) / 2 + 38, H - 80]
        overlay(im, lambda d: d.rounded_rectangle(box, 30, fill=T["sub_bg"]))
        glow(im, lambda d: d.rounded_rectangle(box, 30, outline=T["sub_edge"], width=3), 6)
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle(box, 30, outline=T["sub_edge"], width=2)
        dr.text((W / 2, H - 120), text, font=f, fill=T["sub_fg"], anchor="mm")
    else:   # band(白底黑字帶)/ slab(黑底白字帶):全幅色帶,上方一條線
        y0 = H - 160   # 字幕帶整體上移,留出 QA 總覽圖右下角的時間標籤
        dr.rectangle([0, y0 - 6, W, y0], fill=T["sub_rule"])
        dr.rectangle([0, y0, W, y0 + 80], fill=T["sub_bg"][:3])
        if st == "band":
            dr.rectangle([0, y0 + 80, W, y0 + 86], fill=T["sub_rule"])
        dr.text((W / 2, y0 + 40), text, font=f, fill=T["sub_fg"], anchor="mm")
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
        dr.rectangle([x + cw - 80, y + ch - 30, x + cw, y + ch], fill=T["qa_bg"][:3])
        dr.text((x + cw - 74, y + ch - 28), f"{t:4.1f}s", font=F(20), fill=T["qa_fg"])
    sheet.save(path, optimize=True)
    log("qa", f"{path.name} {n} 格")


def main():
    ap = argparse.ArgumentParser(description="離線示範片(不需 GPU / 模型 / 外部後端)")
    ap.add_argument("--tts", choices=("none", "piper"), default="none")
    ap.add_argument("--out", default="demo_out")
    ap.add_argument("--script", default=str(HERE / "sample_script_en.txt"), help="預設英文範例;中文範例 sample_script.txt")
    ap.add_argument("--theme", default="midnight", help="畫面風格:" + "|".join(THEMES) + " 或 json 路徑(json 以 base 指定底,其餘鍵覆寫)")
    ap.add_argument("--lang", choices=("auto", "zh", "en"), default="auto", help="文案語言;auto 依字元判斷")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    fdir = out / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg"):
        sys.exit("[render] 找不到 ffmpeg(請先安裝並加入 PATH)")

    set_theme(a.theme)
    global LANG
    title, lines = load_script(Path(a.script))
    LANG = detect_lang(lines) if a.lang == "auto" else a.lang
    log("script", f"[{LANG}] 《{title}》{len(lines)} 句、{len({ln['sec'] for ln in lines})} 段")
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
