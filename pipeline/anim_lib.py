"""動畫素材庫:可 import 的函式(動態 emoji、段落轉場、時間軸/拼圖/印章)。

約定:
- 畫布 1920x1080、30fps;emoji 為 360x360。所有 make_* 回傳 list[np.ndarray(H,W,4) uint8 RGBA](straight alpha)。
- 存檔用 save_mov()(qtrle+alpha,可被 ffmpeg overlay)與 save_png_seq()。
- 全部自己寫 ease 與合成;文字一律 Pillow(微軟正黑體粗體),不用 ffmpeg drawtext。
- 與 build.py 無相依,獨立可用。
"""
import collections
import hashlib
import json
import math
import os
import random
import re
import struct
import subprocess
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

LIB_VERSION = 5          # 改動素材外觀時 +1,anim_make 會因此重產
W, H, FPS = 1920, 1080, 30
CX = W / 2              # 內容水平中心(直式組改 510,見 set_profile)
PORTRAIT = False        # set_profile("portrait") 時為 True
FONT_BOLD = r"C:\Windows\Fonts\msjhbd.ttc"
SAFE_H = int(H * 0.77)   # 下方 23% 留給字幕(字幕文字含描邊上緣約 y=895;v2 實測動畫內容最低 y=812)
RED = (179, 0, 27)
STAMP_RED = (196, 16, 36)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
# 共用色票(ANIM_DESIGN.md §3):白/灰 + 一個強調色;紅色只留給負面語意。對 _dark_bg 平均色 (14,10,15) 的對比:NEUTRAL 4.81:1、ACCENT 10.70:1、TEXT2 9.40:1
PAL_TEXT = (255, 255, 255)
PAL_TEXT2 = (0xAE, 0xB4, 0xBE)       # 次要文字(出處、標題底下短橫條)
PAL_NEUTRAL = (0x6F, 0x7E, 0x9E)     # 非強調的資料色
PAL_ACCENT = (0xFF, 0xB0, 0x00)      # 強調色
PAL_NEG = (229, 57, 53)              # 負面 / 否定 / 警告
PAL_LINE = (200, 200, 205)           # 基線、細線

# ---------------------------------------------------------------- ease / 工具
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x

def lerp(a, b, t):
    return a + (b - a) * t

def ease_out_quad(t):
    t = clamp(t); return 1 - (1 - t) ** 2

def ease_in_quad(t):
    t = clamp(t); return t * t

def ease_out_cubic(t):
    t = clamp(t); return 1 - (1 - t) ** 3

def ease_in_cubic(t):
    t = clamp(t); return t ** 3

def ease_in_out_cubic(t):
    t = clamp(t); return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2

def ease_out_back(t, s=1.70158):
    t = clamp(t); return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2

_font_cache = {}
def font(size):
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(FONT_BOLD, size, index=0)
    return _font_cache[size]

def parse_color(c):
    if isinstance(c, str):
        c = c.lstrip("#"); return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c[:3])

def to_np(img):
    return np.asarray(img.convert("RGBA"), dtype=np.uint8)

def resize_rgba(img, size, resample=Image.LANCZOS):
    """預乘 alpha 縮放,避免透明邊緣的白邊/黑邊。"""
    size = (max(1, int(size[0])), max(1, int(size[1])))
    return img.convert("RGBa").resize(size, resample).convert("RGBA")

def scale_alpha(img, a):
    if a >= 0.999:
        return img
    arr = np.asarray(img, dtype=np.float32).copy()
    arr[..., 3] *= a
    return Image.fromarray(arr.round().astype(np.uint8), "RGBA")

def paste_center(canvas, sprite, cx, cy):
    """straight-alpha 疊合;sprite 可超出畫布。"""
    x, y = int(round(cx - sprite.width / 2)), int(round(cy - sprite.height / 2))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(sprite, (x, y))
    return Image.alpha_composite(canvas, layer)

def text_sprite(text, size, fill=WHITE, stroke=0, stroke_fill=BLACK, shadow=False):
    if PORTRAIT:
        P_SIZES.append(size)
    f = font(size)
    pad = stroke + 8 + (6 if shadow else 0)
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    w, h = r - l + 2 * pad, b - t + 2 * pad
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - l + 4, pad - t + 5), text, font=f, fill=(0, 0, 0, 150),
                                stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(4)))
        d = ImageDraw.Draw(img)
    d.text((pad - l, pad - t), text, font=f, fill=tuple(fill) + (255,),
           stroke_width=stroke, stroke_fill=tuple(stroke_fill) + (255,))
    return img

def wrap_text(text, f, max_w):
    lines, cur = [], ""
    for ch in text:
        if f.getlength(cur + ch) > max_w and cur:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines

_NO_START, _NO_END = set("」』）)、,。:;!?》，：；！？"), set("「『（(《")

_FULLWIDTH = {",": "，", "(": "（", ")": "）", ":": "：", ";": "；", "?": "？", "!": "！"}
_CJK_RE = re.compile(r"[　-〿㐀-鿿＀-￯]")


def norm_text(s):
    """動畫內顯示文字的標點正規化:半形 , ( ) : ; ? ! 在前後任一側是 CJK 字(含全形標點)時換成全形;
    純英數之間(1,000 / Take-Two (2K) / 12:30)不動。"""
    if not isinstance(s, str) or not s:
        return s
    out = []
    for i, ch in enumerate(s):
        if ch in _FULLWIDTH:
            prev = out[-1] if out else ""      # 用已轉換的前一字(「)!」連續時第二個也算在 CJK 旁)
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if _CJK_RE.match(prev or " ") or _CJK_RE.match(nxt or " "):
                ch = _FULLWIDTH[ch]
        out.append(ch)
    return "".join(out)


def wrap_kinsoku(text, f, max_w):
    """逐字換行 + 避頭尾:收括號 / 頓號 / 標點不放行首(寧可略超寬),開括號不放行尾。"""
    lines, cur = [], ""
    for ch in text:
        if cur and f.getlength(cur + ch) > max_w and ch not in _NO_START:
            if cur[-1] in _NO_END and len(cur) > 1:
                lines.append(cur[:-1])
                cur = cur[-1] + ch
            else:
                lines.append(cur)
                cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines

# ---------------------------------------------------------------- 存檔 / 讀檔
def save_png_seq(frames, outdir):
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        if f.endswith(".png"):
            os.remove(os.path.join(outdir, f))
    for i, fr in enumerate(frames, 1):
        Image.fromarray(fr, "RGBA").save(os.path.join(outdir, "%04d.png" % i), compress_level=6)

def save_mov(frames, path, fps=FPS, alpha=True):
    """alpha=True:qtrle(argb)mov;alpha=False:h264 mp4(不透明)。"""
    h, w = frames[0].shape[:2]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if alpha:
        enc = ["-c:v", "qtrle", "-pix_fmt", "argb"]
        pin = "rgba"
    else:
        enc = ["-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p"]
        pin = "rgba"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", pin, "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-", *enc, path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in frames:
        p.stdin.write(np.ascontiguousarray(fr).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg 失敗: " + path)

def read_frames(path, w, h, want=None):
    """用 ffmpeg 解 mov/mp4 為 RGBA ndarray 的 generator;want=index 集合時只回傳那些格。"""
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgba", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * 4
    i = 0
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        if want is None or i in want:
            yield i, np.frombuffer(buf, np.uint8).reshape(h, w, 4).copy()
        i += 1
    p.stdout.close(); p.wait()

# ================================================================ A. 動態 emoji
NOTO_URL = "https://fonts.gstatic.com/s/e/notoemoji/latest/{cp}/512.webp"   # 僅限 Google 官方網域
EMOJI = {   # 名稱: (codepoint, 說明)
    "disappointed": ("1f61e", "失望/嘆氣"),
    "confused":     ("1f615", "困惑"),
    "speechless":   ("1f611", "心涼/無言"),
    "shocked":      ("1f632", "驚訝"),
    "eyeroll":      ("1f644", "翻白眼"),
    "heartbreak":   ("1f494", "心碎"),
    "clap":         ("1f44f", "鼓掌"),
    "pray":         ("1f64f", "祈禱/期待"),
    "moneyfly":     ("1f4b8", "錢飛走"),
    "warning":      ("26a0",  "警告"),
    "magnify":      ("1f50e", "放大鏡"),
    "hourglass":    ("23f3",  "沙漏/等待"),
}
EMOJI_CANVAS, EMOJI_BASE = 360, 320   # 畫布 360;主體 320(留 10% 給 1.1 倍彈出)
POP_T, OUT_T = 0.25, 0.20

def fetch_noto_webp(cp, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, cp + ".webp")
    if not os.path.exists(path) or os.path.getsize(path) < 2000:
        url = NOTO_URL.format(cp=cp)
        assert url.startswith("https://fonts.gstatic.com/")
        urllib.request.urlretrieve(url, path)
    return path

def _webp_durations_ms(path):
    d = open(path, "rb").read()
    p, out = 12, []
    while p < len(d):
        tag, sz = d[p:p + 4], struct.unpack("<I", d[p + 4:p + 8])[0]
        if tag == b"ANMF":
            out.append(int.from_bytes(d[p + 8 + 12:p + 8 + 15], "little"))
        p += 8 + sz + (sz & 1)
    return out

def decode_webp_30fps(path):
    """動態 webp -> 30fps 等間隔的 RGBA(512) 序列(依各格 duration 展開;Pillow 已處理 blend/dispose)。"""
    im = Image.open(path)
    durs = _webp_durations_ms(path)
    frames = []
    for i in range(im.n_frames):
        im.seek(i)
        frames.append(im.convert("RGBA").copy())
    seq = []
    for fr, d in zip(frames, durs):
        seq.extend([fr] * max(1, round(d / 30.0)))     # Noto 的單位格 = 30ms ≈ 1/30s
    return seq

def make_emoji(name, seconds, cache_dir, base=EMOJI_BASE, fade_out=True):
    """彈入 0.25s(0→1.1→1 ease-out)+ 主體循環 + 0.2s 縮小淡出;最後一格全透明。
    base:主體邊長(px),畫布依 EMOJI_CANVAS/EMOJI_BASE 等比放大;fade_out=False:不做結尾淡出(獨立鏡頭用,停在主體循環)。"""
    canvas_px = int(round(base * EMOJI_CANVAS / EMOJI_BASE))
    cp = EMOJI[name][0]
    src = decode_webp_30fps(fetch_noto_webp(cp, cache_dir))
    n_src, n = len(src), int(round(seconds * FPS))
    cache, out = {}, []
    for i in range(n):
        t = i / FPS
        # 彈入
        if t < POP_T:
            p = t / POP_T
            s = 1.1 * ease_out_cubic(p / 0.6) if p < 0.6 else 1.1 - 0.1 * ease_in_out_cubic((p - 0.6) / 0.4)
            a = clamp(t / 0.08)
        else:
            s, a = 1.0, 1.0
        # 淡出
        t_out = seconds - OUT_T
        if fade_out and t > t_out:
            q = clamp((t - t_out) / (OUT_T - 1.0 / FPS))
            s *= 1 - 0.3 * ease_in_quad(q)
            a *= (1 - ease_out_quad(q)) if q < 1 else 0.0
        canvas = np.zeros((canvas_px, canvas_px, 4), np.uint8)
        px = int(round(base * s))
        if px >= 2 and a > 0.003:
            key = (i % n_src, px)
            if key not in cache:
                cache[key] = resize_rgba(src[i % n_src], (px, px))
            sp = np.asarray(scale_alpha(cache[key], a))
            ox = (canvas_px - px) // 2
            if px <= canvas_px:
                canvas[ox:ox + px, ox:ox + px] = sp
            else:
                c = (px - canvas_px) // 2
                canvas[:] = sp[c:c + canvas_px, c:c + canvas_px]
        out.append(canvas)
    return out

# ================================================================ B. 段落轉場
_SLANT = 200          # 斜帶上下緣水平位移(半幅)
_BAND_B = 2520        # 黑帶寬(須 >= W+2*slant 才能全遮)
_BAND_G = 70          # 深紅帶比黑帶每側多出的寬度
_TRI_RED = RED

def _band_mask(cx, width, ss=2):
    m = Image.new("L", (W * ss, H * ss), 0)
    s = _SLANT * ss
    pts = [(cx * ss - width * ss / 2 + s, 0), (cx * ss + width * ss / 2 + s, 0),
           (cx * ss + width * ss / 2 - s, H * ss), (cx * ss - width * ss / 2 - s, H * ss)]
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return np.asarray(m.resize((W, H), Image.LANCZOS), dtype=np.float32) / 255.0

def _wipe_c(tau, tA, tB, D):
    """斜帶中心 x 隨時間:快速掃入 -> 中段全遮(微漂移)-> 掃出。"""
    bw_r = _BAND_B + 2 * _BAND_G
    c0 = -bw_r / 2 - _SLANT - 30
    c1 = W + bw_r / 2 + _SLANT + 30
    cm = W / 2
    if tau <= tA:
        return lerp(c0, cm - 40, ease_out_quad(tau / tA))
    if tau <= tB:
        return lerp(cm - 40, cm + 40, (tau - tA) / (tB - tA))
    return lerp(cm + 40, c1, ease_in_quad((tau - tB) / (D - tB)))

def _wipe_frames(D, tA, tB, text=None):
    n = int(round(D * FPS)) + 1          # 首尾格都是全透明
    tsp = text_sprite(text, _fit_title_size(text), WHITE) if text else None
    bar = None
    if text:
        bar = Image.new("RGBA", (180, 8), STAMP_RED + (255,))
    out = []
    for i in range(n):
        tau = i / (n - 1) * D
        c = _wipe_c(tau, tA, tB, D)
        m_r = _band_mask(c, _BAND_B + 2 * _BAND_G)
        m_w = _band_mask(c, _BAND_B + 8)
        m_b = _band_mask(c, _BAND_B)
        # 由下往上疊(premultiplied):紅 -> 白細線(70%)-> 黑
        pm = np.zeros((H, W, 3), np.float32); al = np.zeros((H, W), np.float32)
        for color, m, op in ((_TRI_RED, m_r, 1.0), (WHITE, m_w, 0.7), (BLACK, m_b, 1.0)):
            a = m * op
            pm = pm * (1 - a)[..., None] + np.array(color, np.float32) * a[..., None]
            al = al * (1 - a) + a
        rgba = np.zeros((H, W, 4), np.uint8)
        nz = al > 1e-4
        rgba[..., :3][nz] = np.clip(pm[nz] / al[nz][:, None], 0, 255).round().astype(np.uint8)
        rgba[..., 3] = (al * 255).round().astype(np.uint8)
        if text:
            ta = clamp((tau - (tA - 0.05)) / 0.1) * clamp(((tB + 0.05) - tau) / 0.1)
            if ta > 0.003:
                img = Image.fromarray(rgba, "RGBA")
                rise = (1 - ease_out_cubic((tau - (tA - 0.05)) / 0.35)) * 26
                img = Image.alpha_composite(img, _pos_layer(scale_alpha(tsp, ta), 960, 500 + rise))
                img = Image.alpha_composite(img, _pos_layer(scale_alpha(bar, ta), 960, 500 + tsp.height / 2 + 22 + rise))
                rgba = np.asarray(img)
        out.append(rgba)
    return out

def _pos_layer(sprite, cx, cy):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(sprite, (int(round(cx - sprite.width / 2)), int(round(cy - sprite.height / 2))))
    return layer

def _fit_title_size(text):
    size = 170
    while size > 60 and font(size).getlength(text) > 1500:
        size -= 6
    return size

def make_wipe():
    """trans_wipe:0.5s,深紅+黑雙層斜帶掃過;約第 0.2~0.3s 全遮(3 格)供換場。1920x1080 RGBA,首尾格全透明。"""
    return _wipe_frames(0.5, 0.2, 0.3)

def make_title_wipe(text):
    """帶段落標題版:1.3s,全遮約 0.25~1.05s;中央白色大字可見約 0.9s(淡入淡出各 0.1s)。"""
    return _wipe_frames(1.3, 0.25, 1.05, text=text)

def make_glitch(seconds=0.35, seed=7):
    """trans_glitch 疊加版:黑/白/深紅的橫向切片條 + 細掃描線,中段最強。
    注意:疊加層無法真正位移底下的畫面;要真正的 RGB 分離+切片位移請用 glitch_vf()。"""
    n = int(round(seconds * FPS))
    rng = random.Random(seed)
    out = []
    for k in range(n):
        env = math.sin(math.pi * (k + 0.5) / n)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for _ in range(int(2 + 9 * env)):
            y = rng.randrange(0, H - 80, 2); hh = rng.choice([6, 10, 16, 28, 44, 70])
            w = rng.randrange(260, 1500); x0 = rng.randrange(-100, W - w + 100)
            col, a = rng.choice([(STAMP_RED, 150), (WHITE, 95), (BLACK, 170), (STAMP_RED, 110)])
            d.rectangle([x0, y, x0 + w, y + hh], fill=tuple(col) + (int(a * (0.5 + env / 2)),))
            if rng.random() < 0.5:   # 同列的紅/白錯位邊,模擬 RGB 分離
                dx = int(10 + 24 * env) * rng.choice([-1, 1])
                d.rectangle([x0 + dx, y, x0 + w + dx, y + 3], fill=(255, 255, 255, 120))
                d.rectangle([x0 - dx, y + hh - 3, x0 + w - dx, y + hh], fill=STAMP_RED + (150,))
        for y in range(0, H, 6):
            d.line([(0, y), (W, y)], fill=(0, 0, 0, int(34 * env)), width=1)
        out.append(to_np(img))
    return out

def glitch_vf(t0, seconds=0.35, in_label="in", out_label="out", w=W, h=H, seed=7, prefix="g"):
    """回傳 filter_complex 片段:對 [in_label] 在 [t0, t0+seconds] 做真正的 RGB 分離+橫向切片位移,輸出 [out_label]。
    用法:ffmpeg -i v.mp4 -filter_complex "<此字串>" -map "[out]" ...
    同一個 filter_complex 內呼叫多次時,各次用不同 prefix 避免中間 label 撞名。"""
    n = int(round(seconds * FPS)); rng = random.Random(seed)
    steps, cur, uid = [], in_label, 0
    for k in range(n):
        a, b = t0 + k / FPS, t0 + (k + 1) / FPS
        en = f"between(t,{a:.4f},{b - 0.0005:.4f})"
        env = math.sin(math.pi * (k + 0.5) / n)
        r = max(2, int(round(16 * env * (w / 1920))))
        nxt = f"{prefix}{uid}"; uid += 1
        steps.append(f"[{cur}]rgbashift=rh={r}:bh={-r}:gv={r // 3}:enable='{en}'[{nxt}]"); cur = nxt
        for _ in range(1 if env < 0.5 else 2):
            sh = rng.choice([16, 28, 44, 70]) * h // 1080 // 2 * 2
            y = rng.randrange(0, h - sh, 2)
            dx = int((20 + 110 * env) * rng.choice([-1, 1]) * w / 1920)
            sa, sb, sc = f"{prefix}{uid}a", f"{prefix}{uid}b", f"{prefix}{uid}c"; nxt = f"{prefix}{uid}"; uid += 1
            steps.append(f"[{cur}]split[{sa}][{sb}]")
            steps.append(f"[{sb}]crop={w}:{sh}:0:{y}[{sc}]")
            steps.append(f"[{sa}][{sc}]overlay=x={dx}:y={y}:enable='{en}'[{nxt}]"); cur = nxt
    steps.append(f"[{cur}]null[{out_label}]")
    return ";".join(steps)

# ================================================================ C. 主題動畫
def _circle_sprite(r, fill, ring=WHITE, ring_w=5, ss=4):
    d = (r + 2) * 2
    img = Image.new("RGBA", (d * ss, d * ss), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    c = d * ss // 2
    dr.ellipse([c - r * ss, c - r * ss, c + r * ss, c + r * ss], fill=tuple(ring) + (255,))
    ri = r - ring_w
    dr.ellipse([c - ri * ss, c - ri * ss, c + ri * ss, c + ri * ss], fill=tuple(fill) + (255,))
    return img.resize((d, d), Image.LANCZOS)

def _dark_bg():
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    x = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
    v = 1 - 0.35 * (x ** 2 * 0.6 + (y - 0.5) ** 2 * 2)
    base = np.stack([14 * v + 4 * y, 12 * v, 16 * v + 2 * y], -1) * np.ones((H, W, 1), np.float32)
    a = np.concatenate([np.clip(base, 0, 255), np.full((H, W, 1), 255, np.float32)], -1)
    return Image.fromarray(a.round().astype(np.uint8), "RGBA")

TL_LINE_Y = 400
TL_DESC_SIZES = (56, 54, 52, 50)       # 說明字級:先試 56,放不下才逐級降到 50
TL_DESC_TOP = 62                       # 節點線 -> 說明貼圖上緣
TL_DESC_MAX_LINES, TL_DESC_MIN_GAP = 3, 24
TL_EDGE = 96                           # 內容離畫面左右邊下限


def _wrap_even(text, f, max_w, min_chars=2, toks=None):
    """平衡換行:先用貪心算出最少行數 n,再在 n(不行就 n+1、n+2)行裡找「最長行最短」的切法;
    每行至少 min_chars 個字(只有一行時不限)、行首不是收括號/標點、行尾不是開括號;不拆英數字詞,英數詞後直接接中文時扣分。"""
    toks = toks or _TOK_RE.findall(text)   # toks:呼叫端給的不可拆 token(直式用詞),join 須等於 text
    m = len(toks)
    has_ascii = bool(re.search(r"[A-Za-z0-9]", text))
    n0 = len(wrap_kinsoku(text, f, max_w))
    if n0 <= 1 or m < 2:
        return wrap_kinsoku(text, f, max_w)

    def line_ok(i, j, first, last):
        s = "".join(toks[i:j]).strip()
        if not s or f.getlength(s) > max_w:
            return None
        if len(s) < min_chars or (not first and s[0] in _NO_START) or (not last and s[-1] in _NO_END):
            return None
        pen = 0
        if j < m:
            nxt = next((tk for tk in toks[j:] if not tk.isspace()), "")
            if re.match(r"[A-Za-z0-9,.%+]", s[-1]) and not toks[j].isascii():
                pen += 80       # 英數字詞後直接接中文(如「G 團」「40 人」)
            elif nxt and nxt[0].isascii() and re.match(r"[A-Za-z0-9]", s[-1]) and re.match(r"[A-Za-z0-9]", nxt[0]):
                pen += 300      # 英文詞組中間(如 Riot | Games)盡量不斷
            elif nxt and not nxt[0].isascii() and re.match(r"[0-9%+.,]", s[-1]):
                pen += 80       # 數字與它的單位(2.5 | 億)
            elif has_ascii and nxt and not nxt[0].isascii() and not s[-1].isascii():
                pen += 120      # 含英文的說明:優先在中英交界斷,不在中文詞中間斷
        return f.getlength(s) + pen

    for n in range(n0, n0 + 3):
        INF = (float("inf"), 0.0)
        best = [[INF] * (m + 1) for _ in range(n + 1)]
        prev = [[None] * (m + 1) for _ in range(n + 1)]
        best[0][0] = (0.0, 0.0)
        for k in range(1, n + 1):
            for j in range(k, m + 1):
                for i in range(k - 1, j):
                    if best[k - 1][i][0] == float("inf"):
                        continue
                    w = line_ok(i, j, k == 1, k == n and j == m)
                    if w is None:
                        continue
                    cand = (max(best[k - 1][i][0], w), best[k - 1][i][1] + w * w)
                    if cand < best[k][j]:
                        best[k][j], prev[k][j] = cand, i
        if best[n][m][0] < float("inf"):
            cuts, j = [], m
            for k in range(n, 0, -1):
                i = prev[k][j]
                cuts.append((i, j))
                j = i
            return ["".join(toks[i:j]).strip() for i, j in reversed(cuts)]
    return wrap_kinsoku(text, f, max_w)


def timeline_layout(points):
    """timeline 版面(純幾何,可單獨測試)。points = [(年份, 說明, 色)…](色欄位已不用)。
    回傳 dict:xs 節點 x、ysz 年份字級、dsz 說明字級(56 起,放不下才降到 50)、descs 說明貼圖、lines 各說明行、
    dboxes / yboxes 說明 / 年份最終狀態的墨跡框、bounds 全部內容墨跡 (l,t,r,b)、bottom、degraded(字級低於 56 時 True)、ok(行數與相鄰說明間距都合格)。"""
    n = len(points)
    pts = [(norm_text(p[0]), norm_text(p[1])) for p in points]
    x0, x1 = (300, 1620) if n > 1 else (960, 960)
    xs = [x0 + i * (x1 - x0) / max(1, n - 1) for i in range(n)]
    spacing = (xs[1] - xs[0]) if n > 1 else 700
    ysz = 112     # 年份字級:節點間距放不下時縮小(不超過間距 - 24),避免相鄰年份重疊
    while ysz > 56 and n > 1 and max(font(ysz).getlength(p[0]) for p in pts) > spacing - 24:
        ysz -= 4
    dw = int(min(spacing - 50, 620, 2 * (min(xs[0], W - xs[-1]) - TL_EDGE)))
    yboxes = []
    for p, x in zip(pts, xs):
        sp = text_sprite(p[0], ysz, PAL_TEXT, stroke=2)
        l, t, r, b = _ink(sp)
        top = TL_LINE_Y - 105 - sp.height / 2
        yboxes.append((int(round(x - sp.width / 2)) + l, int(round(top)) + t, int(round(x - sp.width / 2)) + r, int(round(top)) + b))
    res = None
    for dsz in TL_DESC_SIZES:
        f, pitch = font(dsz), round(dsz * 1.32)
        descs, lines, dboxes = [], [], []
        for p, x in zip(pts, xs):
            ls = _wrap_even(p[1], f, dw)
            img = Image.new("RGBA", (dw + 40, pitch * len(ls) + 16), (0, 0, 0, 0))
            for li, ln in enumerate(ls):
                s = text_sprite(ln, dsz, WHITE, stroke=2)
                img.alpha_composite(s, ((img.width - s.width) // 2, li * pitch))
            l, t, r, b = _ink(img)
            ox, oy = int(round(x - img.width / 2)), int(round(TL_LINE_Y + TL_DESC_TOP))
            descs.append(img), lines.append(ls), dboxes.append((ox + l, oy + t, ox + r, oy + b))
        gaps_ok = all(dboxes[i + 1][0] - dboxes[i][2] >= TL_DESC_MIN_GAP for i in range(n - 1))
        ok = gaps_ok and max(len(ls) for ls in lines) <= TL_DESC_MAX_LINES
        res = dict(dsz=dsz, descs=descs, lines=lines, dboxes=dboxes, ok=ok)
        if ok:
            break
    boxes = yboxes + res["dboxes"]
    bounds = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return dict(xs=xs, ysz=ysz, pts=pts, yboxes=yboxes, bounds=bounds, bottom=bounds[3], degraded=res["dsz"] < TL_DESC_SIZES[0], **res)


def _mix(c0, c1, u):
    u = clamp(u)
    return tuple(int(round(a + (b - a) * u)) for a, b in zip(c0, c1))


def make_timeline(points, question_between=None, bg="alpha", seg_seconds=1.2, q_seconds=2.0, src=None):
    """points=[(年份字串, 說明字串, 顏色(已不用,欄位保留)), ...];question_between=(i,j):在第 i、j 節點之間出現跳動紅色問號(PAL_NEG)。
    節點 / 年份:已出現的用 PAL_TEXT,「目前這一步剛出現的」用 PAL_ACCENT,下一步出現時它在 0.3 秒內變回 PAL_TEXT。
    回傳 list[dict(name, frames, hold, loop)]:seg0..seg{n-1} 每新增一個節點一段(各段起點=前段終點狀態;
    hold=True 表可凍結最後一格拉長),最後 q(若有 question_between;loop=True 可循環)。
    bg='alpha':透明;bg='dark':自帶深色底(不透明)。版面見 timeline_layout。"""
    if PORTRAIT:
        return _make_timeline_p(points, question_between, bg, seg_seconds, q_seconds, src)
    n = len(points)
    lay = timeline_layout(points)
    xs, ysz, pts, desc_sp = lay["xs"], lay["ysz"], lay["pts"], lay["descs"]
    line_y = TL_LINE_Y
    x_start = max(120, (300 if n > 1 else 960) - 180)
    cache = {}

    def year_at(i, col):
        k = ("y", i, col)
        if k not in cache:
            cache[k] = text_sprite(pts[i][0], ysz, col, stroke=2)
        return cache[k]

    def node_at(col):
        k = ("n", col)
        if k not in cache:
            cache[k] = _circle_sprite(26, col, ring=col)
        return cache[k]

    base = _dark_bg() if bg == "dark" else Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def render(line_end, node_p, year_p, desc_p, cols, q=None, src_p=1.0):
        img = base.copy()
        d = ImageDraw.Draw(img)
        _src_note(img, src, src_p)
        if line_end is not None and line_end > x_start:
            # 線:先畫黑色描邊(透明底也看得清),再畫白線
            d.rectangle([x_start, line_y - 7, line_end, line_y + 7], fill=(0, 0, 0, 170))
            d.rectangle([x_start, line_y - 4, line_end, line_y + 4], fill=(235, 235, 235, 255))
        for i in range(n):
            if node_p[i] > 0:
                s = ease_out_back(node_p[i]) if node_p[i] < 1 else 1.0
                nsp = node_at(cols[i])
                sp = resize_rgba(nsp, (nsp.width * max(s, 0.02),) * 2)
                img = paste_center(img, sp, xs[i], line_y)
            if year_p[i] > 0:
                e = ease_out_cubic(year_p[i])
                img = paste_center(img, scale_alpha(year_at(i, cols[i]), e), xs[i], line_y - 105 + (1 - e) * 22)
            if desc_p[i] > 0:
                e = ease_out_cubic(desc_p[i])
                img = paste_center(img, scale_alpha(desc_sp[i], e), xs[i], line_y + TL_DESC_TOP + desc_sp[i].height / 2 + (1 - e) * 22)
        if q is not None:
            img = q(img)
        return to_np(img)

    def colors(k, t):
        """第 k 段 t 秒時各節點顏色:k 以前的 PAL_TEXT,k-1 由 PAL_ACCENT 退回 PAL_TEXT,k 為 PAL_ACCENT(k >= n 時沒有新節點)。"""
        cs = [PAL_TEXT] * n
        if 0 <= k < n:
            cs[k] = PAL_ACCENT
        if 1 <= k <= n:
            cs[k - 1] = _mix(PAL_ACCENT, PAL_TEXT, t / 0.3)
        return cs

    segs, fn = [], int(round(seg_seconds * FPS))
    state_prev_end = x_start
    for k in range(n):
        line_to = xs[k]
        frames = []
        for f in range(fn):
            t = f / FPS
            le = lerp(state_prev_end, line_to, ease_in_out_cubic(t / 0.5))
            node_p = [1.0] * k + [clamp((t - 0.42) / 0.3)] + [0.0] * (n - k - 1)
            year_p = [1.0] * k + [clamp((t - 0.5) / 0.3)] + [0.0] * (n - k - 1)
            desc_p = [1.0] * k + [clamp((t - 0.65) / 0.35)] + [0.0] * (n - k - 1)
            frames.append(render(le, node_p, year_p, desc_p, colors(k, t), src_p=clamp(t / 0.4) if k == 0 else 1.0))
        segs.append({"name": f"seg{k}", "frames": frames, "hold": True, "loop": False})
        state_prev_end = line_to
    if question_between:
        i, j = question_between
        qx = (xs[i] + xs[j]) / 2
        qsp = text_sprite("?", 250, PAL_NEG, stroke=10)
        ones = [1.0] * n
        frames = []
        for f in range(int(round(q_seconds * FPS))):
            t = f / FPS
            def q(img, t=t):
                if t < 0.4:
                    s, dy = ease_out_back(t / 0.4), 0.0
                else:
                    ph = ((t - 0.4) % 0.8) / 0.8
                    dy = -abs(math.sin(math.pi * ph)) * 34
                    s = 1.0 + 0.07 * math.sin(2 * math.pi * ph)
                sp = resize_rgba(qsp, (qsp.width * max(s, 0.02), qsp.height * max(s, 0.02)))
                return paste_center(img, sp, qx, line_y - 150 + dy)
            frames.append(render(xs[-1], ones, ones, ones, [PAL_TEXT] * n, q))
        segs.append({"name": "q", "frames": frames, "hold": False, "loop": True})
    return segs

# ---- puzzle
def _knob(d, edge, cell, pad, r, fill):
    """在 piece 局部座標(0,0 為 cell 左上,已含 pad 偏移)畫一個邊上的 knob(向外凸)或 notch(向內凹,fill=0)。"""
    cx = pad + cell / 2; cy = pad + cell / 2
    out = 1.15 * r
    nk = 0.55 * r
    if edge == "r":
        d.rectangle([pad + cell - 2, cy - nk, pad + cell + out, cy + nk], fill=fill)
        d.ellipse([pad + cell + out - r, cy - r, pad + cell + out + r, cy + r], fill=fill)
    elif edge == "l":
        d.rectangle([pad - out, cy - nk, pad + 2, cy + nk], fill=fill)
        d.ellipse([pad - out - r, cy - r, pad - out + r, cy + r], fill=fill)
    elif edge == "b":
        d.rectangle([cx - nk, pad + cell - 2, cx + nk, pad + cell + out], fill=fill)
        d.ellipse([cx - r, pad + cell + out - r, cx + r, pad + cell + out + r], fill=fill)
    elif edge == "t":
        d.rectangle([cx - nk, pad - out, cx + nk, pad + 2], fill=fill)
        d.ellipse([cx - r, pad - out - r, cx + r, pad - out + r], fill=fill)

def _puzzle_piece_mask(rr, cc, cell, ss=2):
    r = cell * 0.15
    pad = int(math.ceil(2.4 * r))
    S = (cell + 2 * pad) * ss
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    sc = lambda v: v * ss
    # 邊方向表:hk[r][c]=+1 表示 (r,c) 向右凸出;vk[r][c]=+1 表示 (r,c) 向下凸出
    hk = [[1, -1], [-1, 1], [1, -1]]
    vk = [[-1, 1, -1], [1, -1, 1]]
    d.rectangle([sc(pad), sc(pad), sc(pad + cell) - 1, sc(pad + cell) - 1], fill=255)
    class _D:   # 座標縮放包裝
        def rectangle(self, b, fill): d.rectangle([sc(v) for v in b], fill=fill)
        def ellipse(self, b, fill): d.ellipse([sc(v) for v in b], fill=fill)
    D = _D()
    edges = []
    if cc < 2: edges.append(("r", hk[rr][cc]))
    if cc > 0: edges.append(("l", -hk[rr][cc - 1]))
    if rr < 2: edges.append(("b", vk[rr][cc]))
    if rr > 0: edges.append(("t", -vk[rr - 1][cc]))
    for e, s in edges:
        if s < 0: _knob(D, e, cell, pad, r, 0)       # 先挖凹
    for e, s in edges:
        if s > 0: _knob(D, e, cell, pad, r, 255)     # 再補凸
    return m, pad

def _puzzle_sprites(cell):
    sprites, ss = {}, 2
    for rr in range(3):
        for cc in range(3):
            m, pad = _puzzle_piece_mask(rr, cc, cell, ss)
            er = m.filter(ImageFilter.MinFilter(7))
            fillmask = m.resize((m.width // ss, m.height // ss), Image.LANCZOS)
            inner = er.resize(fillmask.size, Image.LANCZOS)
            sz = fillmask.size
            body = Image.new("RGBA", sz, (0, 0, 0, 0))
            yy = np.linspace(0, 1, sz[1], dtype=np.float32)[:, None] * np.ones((1, sz[0]), np.float32)
            g = (44 + 22 * (1 - yy)).astype(np.uint8)
            body.paste(Image.fromarray(np.stack([g, g + 2, g + 8, np.full_like(g, 255)], -1), "RGBA"), (0, 0), fillmask)
            edge = Image.new("RGBA", sz, (225, 225, 225, 255))
            edge.putalpha(Image.fromarray(np.clip(np.asarray(fillmask, np.int16) - np.asarray(inner, np.int16), 0, 255).astype(np.uint8), "L"))
            body = Image.alpha_composite(body, edge)
            inner_r = m.filter(ImageFilter.MinFilter(23)).resize(sz, Image.LANCZOS)   # 紅框較粗(約 5px)
            red = Image.new("RGBA", sz, STAMP_RED + (255,))
            red.putalpha(Image.fromarray(np.clip(np.asarray(fillmask, np.int16) - np.asarray(inner_r, np.int16), 0, 255).astype(np.uint8), "L"))
            fill_red = Image.new("RGBA", sz, STAMP_RED + (255,)); fill_red.putalpha(inner_r)
            sprites[(rr, cc)] = (body, red, fill_red, pad)
    return sprites

def make_puzzle(seconds=2.5, center=(960, 400), cell=190):
    """3x3 拼圖依序拼上,最後中央一片缺著並閃紅框(結尾停在紅框亮)。1920x1080 RGBA。"""
    sprites = _puzzle_sprites(cell)
    order = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (2, 1), (2, 0), (1, 0)]
    ox, oy = center[0] - 1.5 * cell, center[1] - 1.5 * cell
    n = int(round(seconds * FPS))
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle([ox - 36, oy - 36, ox + 3 * cell + 36, oy + 3 * cell + 36], 22, fill=(0, 0, 0, 105))
    out = []
    for f in range(n):
        t = f / FPS
        img = panel.copy()
        for k, (rr, cc) in enumerate(order):
            u = (t - (0.10 + 0.15 * k)) / 0.38
            if u <= 0:
                continue
            body, _, _, pad = sprites[(rr, cc)]
            e = ease_out_cubic(u)
            cxp = ox + cc * cell + cell / 2; cyp = oy + rr * cell + cell / 2
            vx, vy = cxp - center[0], cyp - center[1]
            L = math.hypot(vx, vy) or 1
            off = (1 - e) * 300
            sc = 1 + 0.25 * (1 - e)
            sp = resize_rgba(body, (body.width * sc, body.height * sc), Image.BICUBIC) if sc > 1.003 else body
            sp = scale_alpha(sp, clamp(u * 3))
            img = paste_center(img, sp, cxp + vx / L * off, cyp + vy / L * off)
        t_flash = t - 1.6
        if t_flash >= 0:
            a = 0.5 + 0.5 * math.cos(2 * math.pi * 3 * t_flash / 0.9)
            _, red, fill_red, pad = sprites[(1, 1)]
            cxp = ox + 1.5 * cell; cyp = oy + 1.5 * cell
            img = paste_center(img, scale_alpha(fill_red, 0.30 * a), cxp, cyp)
            img = paste_center(img, scale_alpha(red, 0.35 + 0.65 * a), cxp, cyp)
        out.append(to_np(img))
    return out

# ---- stamp
def make_stamp(text, center=(960, 420), hold=1.0, angle=-8, color=STAMP_RED):
    """紅色印章:放大落下 -> 輕微震動 -> 定住,動畫 0.6s;之後凍結最後一格 hold 秒。1920x1080 RGBA。"""
    rng = np.random.RandomState(int(hashlib.md5(text.encode("utf8")).hexdigest()[:8], 16))
    size = 170
    while size > 60 and font(size).getlength(text) > 1100:
        size -= 6
    t_sp = text_sprite(text, size, color)
    pad = 38
    bw, bh = t_sp.width + 2 * pad, t_sp.height + 2 * pad - 20
    sp = Image.new("RGBA", (bw + 40, bh + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    d.rounded_rectangle([20, 20, 20 + bw, 20 + bh], 26, outline=tuple(color) + (255,), width=11)
    d.rounded_rectangle([20 + 22, 20 + 22, 20 + bw - 22, 20 + bh - 22], 14, outline=tuple(color) + (255,), width=4)
    sp.alpha_composite(t_sp, ((sp.width - t_sp.width) // 2, (sp.height - t_sp.height) // 2 - 6))
    # 斑駁:隨機小缺口(約 7%),保持乾淨克制
    noise = rng.rand(sp.height // 3 + 1, sp.width // 3 + 1)
    nm = Image.fromarray((noise * 255).astype(np.uint8), "L").resize(sp.size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.2))
    nm = np.asarray(nm, np.float32) / 255
    keep = np.clip((nm - 0.30) * 12, 0, 1)
    arr = np.asarray(sp, np.float32).copy(); arr[..., 3] *= keep
    sp = Image.fromarray(arr.round().astype(np.uint8), "RGBA").rotate(angle, resample=Image.BICUBIC, expand=True)
    shadow = sp.copy(); sa = np.asarray(shadow, np.float32).copy(); sa[..., :3] = 0; sa[..., 3] *= 0.35
    shadow = Image.fromarray(sa.round().astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(5))
    n_anim = int(round(0.6 * FPS)); out = []
    for f in range(n_anim):
        t = f / FPS
        if t < 0.16:                       # 落下:2.3 倍 -> 1 倍
            u = t / 0.16; s = lerp(2.3, 1.0, ease_in_quad(u)); a = clamp(t / 0.07); ox = oy = 0.0
        else:
            tt = t - 0.16; a = 1.0
            amp = 15 * math.exp(-tt * 9)
            ox = amp * math.sin(tt * 70); oy = amp * 0.7 * math.cos(tt * 62)
            s = 1.0 - 0.05 * math.exp(-tt * 16) * math.sin(math.pi * clamp(tt / 0.12))   # 觸地瞬間微縮
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh = resize_rgba(shadow, (shadow.width * s, shadow.height * s), Image.BICUBIC)
        st = resize_rgba(sp, (sp.width * s, sp.height * s), Image.BICUBIC)
        img = paste_center(img, scale_alpha(sh, a * (0.4 + 0.6 * (1 - clamp((s - 1) / 1.3)))), center[0] + ox + 7, center[1] + oy + 8)
        img = paste_center(img, scale_alpha(st, a), center[0] + ox, center[1] + oy)
        out.append(to_np(img))
    out.extend([out[-1]] * int(round(hold * FPS)))
    return out

# ---- span / bars / list(獨立深色底鏡頭用;內容全在 SAFE_H 以內)
NEWANIM_VER = 6          # 改動 span / bars / list / versus / flow / timeline / cols / share / num 外觀時 +1(build 的鏡頭快取簽章會用到)
SPAN_S, BARS_S = 2.5, 2.6
LIST_POP_S, LIST_NOTE_S = 0.35, 0.3   # 項目彈出 / 備註淡入秒數
LIST_ALL_STEP_S = 0.8                 # list "all":每個項目的間隔(每個項目至少停留 0.8 秒)
GREY = (90, 90, 102)
RED_HI = PAL_NEG
TITLE_BAR_ALPHA = 0.6               # 標題底下短橫條的不透明度
SRC_FS, SRC_RIGHT, SRC_BOTTOM = 44, 1824, 824   # src 出處小字:字級 / 墨跡右緣 x / 墨跡下緣 y


def _blit(img, sp, cx, cy):
    """就地疊合(中心座標;自動裁切超出畫布的部分)。"""
    _blit_xy(img, sp, int(round(cx - sp.width / 2)), int(round(cy - sp.height / 2)))


def _blit_xy(img, sp, x, y):
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(sp.width, img.width - x), min(sp.height, img.height - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    if (sx0, sy0, sx1, sy1) != (0, 0, sp.width, sp.height):
        sp = sp.crop((sx0, sy0, sx1, sy1))
    img.alpha_composite(sp, (x + sx0, y + sy0))


def _base(bg):
    return _dark_bg() if bg == "dark" else Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _title_block(img, title, cy, p, size=84):
    """標題 + 其下的中性色短橫條(PAL_TEXT2,60% 不透明);p=0..1 淡入並由下方滑入。"""
    if p <= 0:
        return
    e = ease_out_cubic(p)
    if PORTRAIT:
        size = _fit_size(norm_text(title), size, P_TEXT_W, P_FS_MIN)
    sp = text_sprite(norm_text(title), size, WHITE, stroke=2)
    _blit(img, scale_alpha(sp, e), CX, cy + (1 - e) * 20)
    bw = int(sp.width * 0.5 * e)
    if bw > 2:
        bar = Image.new("RGBA", (bw + 1, 9), PAL_TEXT2 + (int(255 * TITLE_BAR_ALPHA * e),))
        img.alpha_composite(bar, (int(CX) - bw // 2, cy + sp.height // 2 + 4))


def src_place(text):
    """src 出處小字的 (貼圖, 左上 xy, 墨跡 bbox):墨跡右緣 x=SRC_RIGHT、下緣 y=SRC_BOTTOM。"""
    sp = text_sprite(norm_text(text), SRC_FS, PAL_TEXT2, stroke=2)
    l, t, r, b = _ink(sp)
    x, y = SRC_RIGHT - r, SRC_BOTTOM - b
    return sp, (x, y), (x + l, y + t, x + r, y + b)


def _src_note(img, text, p=1.0):
    """右下角出處小字(任何動畫類型共用;p=0..1 淡入,隨標題一起出現後常駐)。text 為空就不畫。"""
    if not text or p <= 0:
        return
    sp, xy, _ = src_place(text)
    _blit_xy(img, scale_alpha(sp, ease_out_cubic(p)), *xy)


def _split_num(s):
    """'7 個月' -> ('', 7, ' 個月');沒有數字回傳 None。"""
    m = re.match(r"^(\D*?)(\d+)(.*)$", s, re.S)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else None


SPAN_CAP_Y = {False: 740, True: 700}    # caption 中心 y(有 src 時上移,墨跡下緣 <= 768)


def _fit_size(text, size, max_w, min_size):
    """字級由 size 往下縮到墨跡寬度 <= max_w(不小於 min_size)。"""
    while size > min_size and _ink(text_sprite(text, size, WHITE, stroke=2))[2] - _ink(text_sprite(text, size, WHITE, stroke=2))[0] > max_w:
        size -= 2
    return size


def span_layout(frm, to, big, caption=""):
    """span 文字版面:兩端標籤(字級 80 起,太長先把中心往內夾到離邊 96px,兩標籤互碰再縮字)、大字(210 起縮到 <= W-192)、說明(62 起縮到 <= W-192,下限 50)。
    回傳 dict:lab = (字級, 左中心 x, 右中心 x)、bsz、csz。"""
    x0, x1, edge = 300, 1620, CONTENT_EDGE
    lsz = 80
    while True:
        wf, wt = [(_ink(sp)[2] - _ink(sp)[0]) for sp in (text_sprite(frm, lsz, WHITE, stroke=2), text_sprite(to, lsz, WHITE, stroke=2))]
        cl, cr = max(x0, edge + wf / 2), min(x1, W - edge - wt / 2)
        if cl + wf / 2 + 48 <= cr - wt / 2 or lsz <= 56:
            break
        lsz -= 2
    return dict(lab=(lsz, cl, cr), bsz=_fit_size(big, 210, W - 2 * edge, 120), csz=_fit_size(caption, 62, W - 2 * edge, 50) if caption else 62)


def span_bounds(frm, to, big, caption="", src=None):
    """span 全部內容的墨跡 (l, t, r, b)(最終狀態;大字以目標數字計)。"""
    frm, to, big, caption = norm_text(frm), norm_text(to), norm_text(big), norm_text(caption)
    L = span_layout(frm, to, big, caption)
    boxes = []
    for txt, size, cx, cy in ((frm, L["lab"][0], L["lab"][1], 620), (to, L["lab"][0], L["lab"][2], 620), (big, L["bsz"], W / 2, 285),
                              (caption, L["csz"], W / 2, SPAN_CAP_Y[bool(src)])):
        if not txt:
            continue
        sp = text_sprite(txt, size, WHITE, stroke=2)
        l, t, r, b = _ink(sp)
        ox, oy = int(round(cx - sp.width / 2)), int(round(cy - sp.height / 2))
        boxes.append((ox + l, oy + t, ox + r, oy + b))
    boxes.append((300 - 26, 520 - 28, 1620 + 26, 520 + 28))     # 軸與兩端節點
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def make_span(frm, to, ticks, big, caption="", bg="alpha", seconds=SPAN_S, src=None):
    """橫軸 from -> to,中間 ticks 個刻度由左至右逐格亮起(約 1.6s),大字 big 的數字同步由 0 數到目標,最後 caption 淡入。"""
    ticks = max(0, int(ticks))
    frm, to, big, caption = norm_text(frm), norm_text(to), norm_text(big), norm_text(caption)
    x0, x1, ay = 300, 1620, 520
    t_on, t_len = 0.3, 1.6
    base = _base(bg)
    L = span_layout(frm, to, big, caption)
    lsz, cxl, cxr = L["lab"]
    big_sp = text_sprite(big, L["bsz"], WHITE, stroke=2)
    parts = _split_num(big)
    lab_f, lab_t = text_sprite(frm, lsz, WHITE, stroke=2), text_sprite(to, lsz, WHITE, stroke=2)
    cap_sp = text_sprite(caption, L["csz"], (225, 225, 225), stroke=2) if caption else None
    node_lit = _circle_sprite(26, PAL_ACCENT)
    node_off = _circle_sprite(26, GREY, ring=(130, 130, 142))
    tick_lit = _circle_sprite(15, PAL_ACCENT, ring_w=4)
    tick_off = _circle_sprite(15, (60, 60, 70), ring=(120, 120, 132), ring_w=4)
    fr_ticks = [(i + 1) / (ticks + 1) for i in range(ticks)]
    out = []
    for f in range(int(round(seconds * FPS))):
        t = f / FPS
        p = clamp((t - t_on) / t_len)
        img = base.copy()
        d = ImageDraw.Draw(img)
        _src_note(img, src, t / 0.35)
        d.rectangle([x0, ay - 4, x1, ay + 4], fill=GREY + (255,))
        xe = x0 + (x1 - x0) * p
        if xe > x0:
            d.rectangle([x0, ay - 6, xe, ay + 6], fill=PAL_ACCENT + (255,))

        def pop(t_lit, sp_on, sp_off, x):
            if t < t_lit:
                _blit(img, sp_off, x, ay)
            else:
                s = ease_out_back((t - t_lit) / 0.22) if t - t_lit < 0.22 else 1.0
                _blit(img, resize_rgba(sp_on, (sp_on.width * max(s, 0.05),) * 2), x, ay)
        for fr_ in fr_ticks:
            pop(t_on + t_len * fr_, tick_lit, tick_off, x0 + (x1 - x0) * fr_)
        pop(0.0, node_lit, node_off, x0)
        pop(t_on + t_len, node_lit, node_off, x1)
        e0 = ease_out_cubic(t / 0.35)
        _blit(img, scale_alpha(lab_f, e0), cxl, ay + 100)
        _blit(img, scale_alpha(lab_t, e0), cxr, ay + 100)
        if parts:
            pre, num, suf = parts
            sp = text_sprite(f"{pre}{int(round(num * p))}{suf}", L["bsz"], WHITE, stroke=2)
            _blit_xy(img, scale_alpha(sp, ease_out_cubic(t / 0.25)), int(W / 2 - big_sp.width / 2), 285 - sp.height // 2)
        else:
            _blit(img, scale_alpha(big_sp, ease_out_cubic(t / 0.4)), W / 2, 285)
        if cap_sp is not None:
            e = ease_out_cubic((t - (t_on + t_len + 0.05)) / 0.45)
            if e > 0:
                _blit(img, scale_alpha(cap_sp, e), W / 2, SPAN_CAP_Y[bool(src)] + (1 - e) * 16)
        out.append(to_np(img))
    return out


def _fmt_num(v, shown):
    if float(v) == int(v):
        return str(int(round(shown)))
    d = len(repr(float(v)).split(".")[1])      # 保留原值的小數位數(499.99 不可變 500.0)
    return f"{shown:.{d}f}"


BARS_STEP_LEAD_S, BARS_STEP_GROW_S, BARS_STEP_GAP_S = 0.05, 0.5, 0.5   # bars 逐步模式:起點延遲 / 每條長出秒數 / 條與條間隔
BARS_STEP_TAIL_S = 0.1


def bars_step_seconds(prev, shown):
    """bars 逐步模式一段動畫的長度(秒):由顯示 prev 條變成 shown 條(shown=0:只有標題)。shown == prev = 凍結(0.1 秒)。"""
    if shown <= 0:
        return 0.5
    if shown <= prev:
        return 0.1
    return BARS_STEP_LEAD_S + BARS_STEP_GAP_S * (shown - prev - 1) + BARS_STEP_GROW_S + BARS_STEP_TAIL_S


BAR_COLORS = {"alliance": (47, 111, 214), "horde": (200, 50, 43)}   # 類別色:不同色相(藍 / 紅),同類別固定同色

# ---- bars 版面 / 顏色常數(2026-10-11 重做:靠左、條間留白、單色加強調色)。座標單位 px,1920x1080。
BARS_LABEL_RIGHT = 420        # 類別標籤右對齊的 x
BARS_BASE_X = 460             # 長條共同基線 x(條的起點)
BARS_END_MAX = 1500           # 最長條的終點 x 上限
BARS_VAL_GAP = 24             # 數值距條尾
BARS_BH, BARS_BH_MIN = 56, 40         # 條厚(放不下先縮到最低)
BARS_GAP, BARS_GAP_MIN = 44, 36       # 條間隔(條厚縮到最低後才縮;任何情況不小於 36)
BARS_GROUP_GAP = 96           # 組與組間隔(上一組最後一條下緣 -> 下一組標題上緣)
BARS_GTITLE_GAP = 16          # 組標題下緣 -> 該組第一條上緣
BARS_TITLE_TO_FIRST = 70      # 標題(含底下紅線)下緣 -> 第一條(分組時為第一個組標題)上緣
BARS_BOTTOM_MAX = 800         # 最後一條下緣上限(字幕帶以上)
BARS_BOTTOM_SRC = 752         # 有 src 出處小字時的上限(src 墨跡上緣約 780,留 28px)
BARS_CORNER = 10              # 資料端圓角,基線端直角
BARS_LABEL_FS, BARS_VAL_FS, BARS_VAL_FS_HI, BARS_GTITLE_FS = 56, 64, 72, 52
BARS_UNIT_RATIO, BARS_UNIT_GAP, BARS_UNIT_MIN = 0.75, 8, 44   # 單位字級 = 數字的 0.75 倍(不小於 44px),與數字共用基線,間隔 8px(% 不留間隔)
BARS_TITLE_CY, BARS_TITLE_FS = 150, 84
BARS_BASELINE_W, BARS_BASELINE_RGBA = 2, (200, 200, 205, 102)   # 基線:2px、40% 不透明淺灰
BARS_COLOR, BARS_HI_COLOR = PAL_NEUTRAL, PAL_ACCENT   # 非強調條中性色 / 強調琥珀(共用色票)
BARS_LABEL_RGB, BARS_VAL_RGB = (0xE7, 0xE9, 0xEA), PAL_TEXT   # 文字不用資料色
BARS_VAL_AT = 0.8             # 條長到 80% 時數值淡入
BARS_TOO_MANY = "長條圖項目過多,請拆成兩張"


def _bar_color(spec, default):
    if not spec:
        return default
    if isinstance(spec, str) and spec in BAR_COLORS:
        return BAR_COLORS[spec]
    return parse_color(spec)


def _bar_opt(it):
    return it[3] if len(it) > 3 and isinstance(it[3], dict) else {}


def _ink(sp):
    """sprite 的不透明區域 bbox (l, t, r, b)。"""
    return sp.getchannel("A").getbbox() or (0, 0, sp.width, sp.height)


_bars_tb = []


def bars_title_bottom():
    """標題(含其下紅線)下緣 y;以 CJK 參考字串量,版面不隨標題字串變動。"""
    if not _bars_tb:
        _bars_tb.append(BARS_TITLE_CY + text_sprite("標題國gjpy(", BARS_TITLE_FS, WHITE, stroke=2).height // 2 + 12)
    return _bars_tb[0]


def _thousands(num):
    """整數部分 >= 1000 加千分位逗號('12345.5' -> '12,345.5')。"""
    m = re.fullmatch(r"(\d{4,})(\.\d+)?", num)
    return f"{int(m.group(1)):,}{m.group(2) or ''}" if m else num


def _baseline(txt, size, stroke=2):
    """text_sprite(txt, size, stroke) 貼圖內的字型基線 y。"""
    f = font(size)
    return (stroke + 8 - f.getbbox(txt, stroke_width=stroke)[1]) + f.getmetrics()[0]


def _rel_lum(rgb):
    """sRGB 色的相對亮度 0..1(WCAG)。"""
    c = [v / 255.0 for v in rgb[:3]]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _val_sprite(num, unit, size, rgb=None):
    """bars 數值貼圖:數字 size px、單位 size*0.75 px(不小於 44),共用基線(底緣對齊),間隔 8px(單位為 % 時 0);整數 >= 1000 加千分位。
    rgb = 文字色(預設 BARS_VAL_RGB)。"""
    rgb = rgb or BARS_VAL_RGB
    num = _thousands(num)
    ns = text_sprite(num, size, rgb, stroke=2)
    if not unit:
        return ns
    usz = max(BARS_UNIT_MIN, round(size * BARS_UNIT_RATIO))
    us = text_sprite(unit, usz, rgb, stroke=2)
    nr, ul = _ink(ns)[2], _ink(us)[0]
    x_u = nr + (0 if unit.strip() == "%" else BARS_UNIT_GAP) - ul
    nb, ub = _baseline(num, size), _baseline(unit, usz)
    dn, du = max(0, ub - nb), max(0, nb - ub)          # 兩者基線對齊所需的垂直位移
    out = Image.new("RGBA", (max(ns.width, x_u + us.width), max(dn + ns.height, du + us.height)), (0, 0, 0, 0))
    out.alpha_composite(ns, (0, dn))
    out.alpha_composite(us, (x_u, du))
    return out


def bars_geometry(sizes, grouped=False, gh=0, bottom_max=BARS_BOTTOM_MAX):
    """純幾何(可單獨測試)。sizes = 每組條數(未分組 = [n]);gh = 組標題字高(分組時)。
    回傳 dict(bh, gap, ys=每條中心 y, tops=每組第一條上緣, bottom=最後一條下緣)。bottom_max = 最後一條下緣上限(有 src 時用 BARS_BOTTOM_SRC)。條厚 56/間隔 44;放不下先縮條厚到 40 再縮間隔到 36,
    仍放不下 raise ValueError(BARS_TOO_MANY)。"""
    ng, y0 = len(sizes), bars_title_bottom() + BARS_TITLE_TO_FIRST
    head = (gh + BARS_GTITLE_GAP) if grouped else 0
    cands = [(bh, BARS_GAP) for bh in range(BARS_BH, BARS_BH_MIN - 1, -1)] + [(BARS_BH_MIN, g) for g in range(BARS_GAP - 1, BARS_GAP_MIN - 1, -1)]
    for bh, gap in cands:
        total = sum(head + s * bh + (s - 1) * gap for s in sizes) + (ng - 1) * BARS_GROUP_GAP
        if y0 + total <= bottom_max:
            break
    else:
        raise ValueError(BARS_TOO_MANY)
    y, ys, tops = y0 + head, [], []
    for i, s in enumerate(sizes):
        tops.append(y)
        for _ in range(s):
            ys.append(y + bh / 2)
            y += bh + gap
        y += BARS_GROUP_GAP - gap + head
    return dict(bh=bh, gap=gap, ys=ys, tops=tops, bottom=ys[-1] + bh / 2)


class _BarsLayout:
    """bars 的版面(make_bars / make_bars_step 共用)。items = [[標籤, 數值, 單位?, {"color"?, "icon"?, "hi"?}?], ...];
    groups = [{"title", "bars": [同上]}, ...] 時改為分組(items 被忽略):每組有組標題(左對齊基線),逐步模式的 step 仍是跨組的「第幾條」。
    顏色:有 color 的照類別色;其餘單一藍色,最大值那條(或 hi:true 指定的條)用琥珀;任何一條帶 "hi" 鍵就不自動挑最大值。"""

    def __init__(self, items, groups=None, icon_root=None, src=None):
        self.src = src
        self.grouped = bool(groups)
        if self.grouped:
            self.items = [b for g in groups for b in g["bars"]]
            self.gidx = []          # 每條所屬的組
            for gi, g in enumerate(groups):
                self.gidx += [gi] * len(g["bars"])
            self.gtitles = [norm_text(g["title"]) for g in groups]
            sizes = [len(g["bars"]) for g in groups]
        else:
            self.items = list(items)
            self.gidx, self.gtitles = [0] * len(self.items), []
            sizes = [len(self.items)]
        self.n = len(self.items)
        self.vmax = max(float(it[1]) for it in self.items)
        self.lmax = BARS_END_MAX - BARS_BASE_X
        self.gspr = [text_sprite(t, BARS_GTITLE_FS, BARS_LABEL_RGB, stroke=2) for t in self.gtitles]
        gh = max((_ink(sp)[3] - _ink(sp)[1] for sp in self.gspr), default=0)
        geo = self.geo = bars_geometry(sizes, self.grouped, gh, BARS_BOTTOM_SRC if src else BARS_BOTTOM_MAX)
        self.bh, self.ys = geo["bh"], geo["ys"]
        self.gtop = geo["tops"] if self.grouped else []     # 每組第一條上緣(組標題下緣 = 此值 - 16)
        opts = [_bar_opt(it) for it in self.items]
        explicit = any("hi" in o for o in opts)
        auto = not explicit and not any(o.get("color") for o in opts) and len({float(it[1]) for it in self.items}) > 1
        self.hi = [bool(o.get("hi")) if explicit else (auto and float(it[1]) == self.vmax) for it, o in zip(self.items, opts)]
        self.labels = [text_sprite(norm_text(it[0]), BARS_LABEL_FS, BARS_LABEL_RGB, stroke=2) for it in self.items]
        self.vals = []
        for it, hi in zip(self.items, self.hi):
            unit = norm_text(it[2]) if len(it) > 2 and isinstance(it[2], str) else ""
            self.vals.append(_val_sprite(_fmt_num(it[1], float(it[1])), unit, BARS_VAL_FS_HI if hi else BARS_VAL_FS))
        self.icons = []
        for it in self.items:
            ic, name = None, _bar_opt(it).get("icon")
            if name and icon_root and os.path.exists(os.path.join(icon_root, name)):
                im = Image.open(os.path.join(icon_root, name)).convert("RGBA")
                ic = im.resize((max(1, round(im.width * 64 / im.height)), 64), Image.LANCZOS)
            self.icons.append(ic)

    def color(self, k):
        if self.hi[k]:
            return BARS_HI_COLOR
        return _bar_color(_bar_opt(self.items[k]).get("color"), BARS_COLOR)

    def first_of(self, g):
        return self.gidx.index(g)

    def place(self, k, e=1.0):
        """第 k 條在長度進度 e(0..1)時的位置:dict(bar=條矩形, L=條長, label/icon/val=(貼圖左上 xy, 墨跡 bbox))。"""
        y, L = self.ys[k], self.lmax * float(self.items[k][1]) / self.vmax * e
        out = dict(bar=(BARS_BASE_X, y - self.bh / 2, BARS_BASE_X + L, y + self.bh / 2), L=L)

        def put(sp, x_ink, right=False):
            l, t, r, b = _ink(sp)
            x = int(round(x_ink - (r if right else l)))
            yy = int(round(y - (t + b) / 2))
            return (x, yy), (x + l, yy + t, x + r, yy + b)
        out["label"] = put(self.labels[k], BARS_LABEL_RIGHT, right=True)
        ic = self.icons[k]
        if ic is not None:
            ix, iy = out["label"][1][0] - 14 - ic.width, int(round(y - ic.height / 2))
            out["icon"] = ((ix, iy), (ix, iy, ix + ic.width, iy + ic.height))
        out["val"] = put(self.vals[k], BARS_BASE_X + L + BARS_VAL_GAP)
        return out

    def group_place(self, g):
        sp = self.gspr[g]
        l, t, r, b = _ink(sp)
        x, y = BARS_BASE_X - l, int(round(self.gtop[g] - BARS_GTITLE_GAP - b))
        return (x, y), (x + l, y + t, x + r, y + b)

    def axes(self, img, shown, prev, t, full):
        """基線:未分組一條;分組時每組一條(只畫到該組已出現的最後一條)。full=True:整組一次播(舊 make_bars,基線全長)。"""
        for g in (sorted(set(self.gidx)) if self.grouped else [0]):
            ks = [k for k in range(self.n) if self.gidx[k] == g]
            vis = ks if full else [k for k in ks if k < shown]
            if not vis:
                continue
            lo, end = ks[0], vis[-1]
            y_end = self.ys[end]
            if not full and prev > 0 and end >= prev and lo <= prev - 1 < end:
                y_end = lerp(self.ys[prev - 1], self.ys[end], clamp(t / 0.3))
            y0, y1 = int(round(self.ys[lo] - self.bh / 2)), int(round(y_end + self.bh / 2))
            img.alpha_composite(Image.new("RGBA", (BARS_BASELINE_W, y1 - y0), BARS_BASELINE_RGBA), (BARS_BASE_X - BARS_BASELINE_W, y0))

    def group_title(self, img, d, g, q):
        q = clamp(q)
        if q <= 0:
            return
        (x, y), _ = self.group_place(g)
        _blit_xy(img, scale_alpha(self.gspr[g], ease_out_cubic(q)), x, y)

    def bar(self, img, d, k, e, lt):
        pl = self.place(k, e)
        _blit_xy(img, scale_alpha(self.labels[k], lt), *pl["label"][0])
        if "icon" in pl:
            _blit_xy(img, scale_alpha(self.icons[k], lt), *pl["icon"][0])
        x0, y0, x1, y1 = pl["bar"]
        if pl["L"] > 2:
            r = min(BARS_CORNER, int(pl["L"]) // 2)
            fill = self.color(k) + (255,)
            if r >= 2:
                d.rounded_rectangle([x0, y0, x1, y1], r, fill=fill, corners=(False, True, True, False))
            else:
                d.rectangle([x0, y0, x1, y1], fill=fill)
        va = clamp((e - BARS_VAL_AT) / (1 - BARS_VAL_AT))
        if va > 0:
            _blit_xy(img, scale_alpha(self.vals[k], va), *pl["val"][0])


def make_bars(title, items, bg="alpha", seconds=BARS_S, groups=None, icon_root=None, src=None):
    """標題先出,各條橫向長條依序由左長出(長度依數值比例),條尾顯示 數值+單位(數字同步遞增)。
    items=[[標籤, 數值, 單位, {"color": 類別名或色碼, "icon": anim 資料夾下的圖檔}?], ...];groups=[{"title", "bars"}] 時分組。"""
    lay = _BarsLayout(items, groups, icon_root, src)
    base = _base(bg)
    t_title, t0, step, grow = 0.4, 0.5, 0.7, 0.7
    out = []
    for f in range(int(round(seconds * FPS))):
        t = f / FPS
        img = base.copy()
        d = ImageDraw.Draw(img)
        _title_block(img, title, BARS_TITLE_CY, t / t_title)
        _src_note(img, src, t / t_title)
        lay.axes(img, lay.n, 0, t, True)
        for g in range(len(lay.gspr)):
            lay.group_title(img, d, g, (t - (t0 + step * lay.first_of(g))) / 0.25)
        for k in range(lay.n):
            s = t0 + step * k
            if t >= s:
                lay.bar(img, d, k, ease_out_cubic((t - s) / grow), clamp((t - s) / 0.25))
        out.append(to_np(img))
    return out


def make_bars_step(title, items, shown, prev=0, title_in=False, bg="alpha", groups=None, icon_root=None, src=None):
    """bars 逐步顯示(時間的純函式):前 prev 條已在畫面上,第 prev..shown-1 條依序長出。長度比例以全部條的最大值為準(各段一致)。
    shown=0 = 只有標題(title_in=True 時標題淡入);title_in=False = 標題已在畫面上。groups / 顏色 / 圖示見 make_bars。"""
    lay = _BarsLayout(items, groups, icon_root, src)
    base = _base(bg)
    out = []
    for f in range(int(round(bars_step_seconds(prev, shown) * FPS))):
        t = f / FPS
        img = base.copy()
        d = ImageDraw.Draw(img)
        _title_block(img, title, BARS_TITLE_CY, t / 0.4 if title_in else 1.0)
        _src_note(img, src, t / 0.4 if title_in else 1.0)
        if shown > 0:
            lay.axes(img, shown, prev, t, False)
            for g in range(len(lay.gspr)):      # 組標題:該組第一條出現時淡入
                k0 = lay.first_of(g)
                if k0 < shown:
                    lay.group_title(img, d, g, 1.0 if k0 < prev else (t - (BARS_STEP_LEAD_S + BARS_STEP_GAP_S * (k0 - prev))) / 0.25)
        for k in range(shown):
            if k < prev:
                e, lt = 1.0, 1.0
            else:
                s = BARS_STEP_LEAD_S + BARS_STEP_GAP_S * (k - prev)
                if t < s:
                    continue
                e, lt = ease_out_cubic((t - s) / BARS_STEP_GROW_S), clamp((t - s) / 0.25)
            lay.bar(img, d, k, e, lt)
        out.append(to_np(img))
    return out


def list_seconds(n, has_note, step="all"):
    """list 動畫本身的長度(秒):"all" = 全部依序彈出 + 備註;整數 step = 該項彈出(第 0 項含標題)+ 最後一項的備註。"""
    note = LIST_NOTE_S if has_note else 0.0
    if step == "all":
        return 0.35 + LIST_ALL_STEP_S * (n - 1) + LIST_POP_S + note
    last = step == n - 1
    return (0.35 if step == 0 else 0.1) + LIST_POP_S + (note if last else 0.0)


LIST_DOT_R, LIST_TEXT_GAP = 34, 40          # 編號圓點半徑 / 圓點與文字間距
LIST_DOT_TXT = (27, 20, 20)                 # 圓點上的序號(深色字)
LIST_MAX_ITEMS = 5                          # 超過就警告(parse_anim)
LIST_NOTE_BOTTOM = {False: 790, True: 768}  # note 墨跡下緣(有 src 時 <= 768)
LIST_TITLE_CY, LIST_DOT_FS = 150, 44        # 標題中心 y / 圓點序號字級


def list_layout(items, note=None, src=None):
    """list 版面(純幾何)。整個清單區塊(圓點加最寬項目)水平置中於 x=960,區塊內文字靠左(對齊墨跡左緣)。
    回傳 dict:items(已正規化)、size、sps、ys、tx(各項貼圖左上 x)、dot_x、boxes(各項最終狀態墨跡框,含圓點)、
    note_sp / note_cy / note_box、bounds、bottom、note_overlap(note 墨跡上緣離最後一項下緣 < 24)。"""
    if PORTRAIT:
        return _list_layout_p(items, note, src)
    items = [norm_text(x) for x in items]
    n = len(items)
    gap = min(150, 450 / max(n, 1))
    ys = [350 + k * gap for k in range(n)]
    size = 70
    while size > 44 and max(font(size).getlength(x) for x in items) > 1400:
        size -= 2
    sps = [text_sprite(x, size, WHITE, stroke=2) for x in items]
    inks = [_ink(sp) for sp in sps]
    d_ink = 2 * LIST_DOT_R
    blk = d_ink + LIST_TEXT_GAP + max(i[2] - i[0] for i in inks)
    x_left = CX - blk / 2
    t_left = x_left + d_ink + LIST_TEXT_GAP
    tx = [int(round(t_left - i[0])) for i in inks]
    dot_x = x_left + LIST_DOT_R
    boxes = []
    for k in range(n):
        oy = int(round(ys[k] - sps[k].height // 2))
        boxes.append((int(round(x_left)), min(oy + inks[k][1], int(ys[k] - LIST_DOT_R)),
                      tx[k] + inks[k][2], max(oy + inks[k][3], int(ys[k] + LIST_DOT_R))))
    note_sp, note_cy, note_box = None, None, None
    if note:
        note_sp = text_sprite(norm_text(note), 50, (210, 210, 210), stroke=2)
        l, t, r, b = _ink(note_sp)
        note_cy = LIST_NOTE_BOTTOM[bool(src)] - b + note_sp.height / 2
        oy, ox = int(round(note_cy - note_sp.height / 2)), int(round(CX - note_sp.width / 2))
        note_box = (ox + l, oy + t, ox + r, oy + b)
    allb = boxes + ([note_box] if note_box else [])
    bounds = (min(b[0] for b in allb), min(b[1] for b in allb), max(b[2] for b in allb), max(b[3] for b in allb))
    return dict(items=items, size=size, sps=sps, ys=ys, tx=tx, dot_x=dot_x, boxes=boxes, note_sp=note_sp, note_cy=note_cy,
                note_box=note_box, bounds=bounds, bottom=bounds[3],
                note_overlap=bool(note_box and boxes and note_box[1] < boxes[-1][3] + 24))


def make_list(title, items, step="all", note=None, bg="alpha", src=None):
    """標題下方項目逐一彈出(PAL_ACCENT 圓點+序號)。回傳 list[dict(name, frames)]:
    step="all" -> [all];否則 seg0..seg{n-1}(segk 起點=前一段終點:標題與前 k 項已在畫面上,只播第 k 項的出現動畫)。版面見 list_layout。"""
    n = len(items)
    base = _base(bg)
    lay = list_layout(items, note, src)
    ys, sps, tx, note_sp = lay["ys"], lay["sps"], lay["tx"], lay["note_sp"]
    dots = []
    for k in range(n):
        dot = _circle_sprite(LIST_DOT_R, PAL_ACCENT, ring=PAL_ACCENT)
        ImageDraw.Draw(dot).text((dot.width / 2, dot.height / 2 + 1), str(k + 1), font=font(LIST_DOT_FS), fill=LIST_DOT_TXT + (255,),
                                 anchor="mm")
        dots.append(dot)

    def render(title_p, item_p, note_p):
        img = base.copy()
        _title_block(img, title, lay.get("title_cy", LIST_TITLE_CY), title_p)
        _src_note(img, src, title_p)
        for k in range(n):
            q = item_p[k]
            if q <= 0:
                continue
            e = ease_out_cubic(q)
            s = ease_out_back(q) if q < 1 else 1.0
            _blit(img, resize_rgba(dots[k], (dots[k].width * max(s, 0.05),) * 2), lay["dot_x"], ys[k] + (1 - e) * 22)
            _blit_xy(img, scale_alpha(sps[k], e), tx[k], int(ys[k] + (1 - e) * 22 - sps[k].height // 2))
        if note_sp is not None and note_p > 0:
            e = ease_out_cubic(note_p)
            _blit(img, scale_alpha(note_sp, e), CX, lay["note_cy"] + (1 - e) * 12)
        return to_np(img)

    def seg(sec, tp, ip, npf):
        return [render(tp(i / FPS), [g(i / FPS) for g in ip], npf(i / FPS)) for i in range(int(round(sec * FPS)))]

    one = lambda v: 1.0
    zero = lambda v: 0.0
    pop = lambda t0: (lambda t: clamp((t - t0) / LIST_POP_S))
    if step == "all":
        t_end = 0.35 + LIST_ALL_STEP_S * (n - 1) + LIST_POP_S
        frames = seg(list_seconds(n, bool(note)), lambda t: clamp(t / 0.3),
                     [pop(0.35 + LIST_ALL_STEP_S * k) for k in range(n)], lambda t: clamp((t - t_end) / LIST_NOTE_S))
        return [dict(name="all", frames=frames)]
    segs = []
    for k in range(n):
        t_pop = 0.35 if k == 0 else 0.1
        ip = [one] * k + [pop(t_pop)] + [zero] * (n - k - 1)
        npf = (lambda t, te=t_pop + LIST_POP_S: clamp((t - te) / LIST_NOTE_S)) if (note_sp is not None and k == n - 1) else zero
        segs.append(dict(name=f"seg{k}", frames=seg(list_seconds(n, bool(note), k),
                                                    (lambda t: clamp(t / 0.3)) if k == 0 else one, ip, npf)))
    return segs


# ---- versus(左右兩欄對照)/ flow(由左至右的流程圖):逐步模式,與 bars 同一套 prev / shown 機制
# 步驟(level):versus 0 = 標題+兩欄標題、1 = 左欄內容、2 = 右欄內容;flow = 已顯示的節點數(1..n)。
# 一段動畫 = 由 prev 變成 shown(shown == prev:凍結 0.1 秒);每一步的出現都從該句開頭起算,不等句尾。
GREEN = (67, 160, 71)
STEP_TAIL_S = 0.1
VS_HEAD_S, VS_STEP_S, VS_LEAD_S = 0.6, 0.55, 0.05      # versus:標題+欄標題 / 每欄內容一步 / prev>0 時的起點延遲
FLOW_NODE0_S, FLOW_ARROW_S, FLOW_POP_S = 0.3, 0.25, 0.3  # flow:第一個節點起點 / 箭頭畫出 / 節點彈出
FLOW_LEAD_S = 0.05
VS_PANEL = (96, 262, 912, 800)                           # 左欄面板 (x0, y0, x1, y1);右欄鏡射(x -> W - x);y1 在有 src 時改 VS_BOTTOM_SRC
VS_BOTTOM_SRC = 752
VS_FILL = (28, 31, 42)                                   # 面板填色(約 92% 不透明,不描外框)
VS_LINE_SIZE, VS_LINE_MIN, VS_HEAD_SIZE = 72, 56, 66      # 內容字上限 / 下限(由 _fit_rows 縮到放得下);欄標題字
FLOW_BOX_Y, FLOW_BOX_H, FLOW_TEXT_SIZE = 380, 300, 70
FLOW_EDGE = 96                                           # 節點區離畫面左右邊下限
FLOW_FILL = (28, 31, 42, 235)                            # 節點面板填色(不描外框;最後一個節點加 PAL_ACCENT 3px 外框)


def versus_step_seconds(prev, shown):
    if shown <= 0:
        return VS_HEAD_S + STEP_TAIL_S
    if shown <= prev:
        return STEP_TAIL_S
    return (VS_HEAD_S if prev <= 0 else VS_LEAD_S) + VS_STEP_S * (shown - max(prev, 0)) + STEP_TAIL_S


def flow_step_seconds(prev, shown):
    if shown <= prev:
        return STEP_TAIL_S
    t = FLOW_NODE0_S if prev <= 0 else FLOW_LEAD_S
    for k in range(prev, shown):
        t += FLOW_POP_S if k == 0 else FLOW_ARROW_S + FLOW_POP_S
    return t + STEP_TAIL_S


def _mark_sprite(kind, r=52, ss=4):
    """綠色圓底白勾("yes")/ 紅色圓底白叉("no")。"""
    col = GREEN if kind == "yes" else RED_HI
    d = (r + 2) * 2
    img = Image.new("RGBA", (d * ss, d * ss), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    c = d * ss // 2
    dr.ellipse([c - r * ss, c - r * ss, c + r * ss, c + r * ss], fill=WHITE + (255,))
    ri = (r - 5) * ss
    dr.ellipse([c - ri, c - ri, c + ri, c + ri], fill=col + (255,))
    u, lw = r * ss / 52, int(9 * ss)
    if kind == "yes":
        pts = [(c - 24 * u, c + 2 * u), (c - 7 * u, c + 20 * u), (c + 26 * u, c - 18 * u)]
        dr.line(pts, fill=WHITE + (255,), width=lw, joint="curve")
        for p in (pts[0], pts[-1]):
            dr.ellipse([p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2], fill=WHITE + (255,))
    else:
        for a, b in (((-20, -20), (20, 20)), ((-20, 20), (20, -20))):
            p, q = (c + a[0] * u, c + a[1] * u), (c + b[0] * u, c + b[1] * u)
            dr.line([p, q], fill=WHITE + (255,), width=lw)
            for e in (p, q):
                dr.ellipse([e[0] - lw / 2, e[1] - lw / 2, e[0] + lw / 2, e[1] + lw / 2], fill=WHITE + (255,))
    return img.resize((d, d), Image.LANCZOS)


_TOK_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9,.:%+/\-]*|\s+|.", re.S)


def _wrap_balanced(text, f, max_w):
    """換行不拆英數字詞(如 4,000 / G);只需兩行時選「最長行最短」的切點,且偏好在空白處切。"""
    toks = _TOK_RE.findall(text)
    lines, cur = [], ""
    for tk in toks:
        if cur and f.getlength((cur + tk).rstrip()) > max_w:
            lines.append(cur.strip())
            cur = tk.lstrip()
        else:
            cur += tk
    if cur.strip():
        lines.append(cur.strip())
    if len(lines) == 2:
        best = None
        for i in range(1, len(toks)):
            a, b = "".join(toks[:i]).strip(), "".join(toks[i:]).strip()
            if not a or not b:
                continue
            pa, nb = a[-1], b[0]
            if re.match(r"[A-Za-z0-9,.%+]", pa) and not nb.isascii():   # 英數字詞後直接接中文(如「G 團」「40 人」)不拆開
                continue
            w = max(f.getlength(a), f.getlength(b))
            if w > max_w:
                continue
            cost = w + (0 if (toks[i - 1].isspace() or toks[i].isspace()) else 80)
            if best is None or cost < best[0]:
                best = (cost, [a, b])
        if best:
            lines = best[1]
    return lines


def _fit_rows(text, size, max_w, min_size):
    """一行文字:先縮字級(不小於 min_size),還放不下就換行。回傳 (字級, [列])。"""
    while size > min_size and font(size).getlength(text) > max_w:
        size -= 2
    return size, (_wrap_balanced(text, font(size), max_w) if font(size).getlength(text) > max_w else [text])


def versus_layout(left, right, src=None):
    """versus 版面(純幾何)。回傳 dict:panel (x0,y0,x1,y1)、cols(每欄 head / rows 貼圖、ys、cx、mark)、size(內文起始字級)、
    bounds(面板加內容墨跡 (l,t,r,b))、bottom、rows_inside(內文墨跡是否都在面板內)。"""
    px0, py0, px1, py1 = VS_PANEL
    if src:
        py1 = VS_BOTTOM_SRC
    inner = (px1 - px0) - 90
    has_mark = bool(left.get("mark") or right.get("mark"))
    zone = (575 if has_mark else 440, py1 - 20)
    for start in range(VS_LINE_SIZE, VS_LINE_MIN - 1, -2):
        cols, fits = [], True
        for side, d in ((0, left), (1, right)):
            hs = VS_HEAD_SIZE
            head_txt = norm_text(d["head"])
            while hs > 48 and font(hs).getlength(head_txt) > inner:
                hs -= 2
            head = text_sprite(head_txt, hs, WHITE, stroke=2)
            rows, szs = [], []
            for ln_ in d["lines"]:
                sz, parts = _fit_rows(norm_text(ln_), start, inner, VS_LINE_MIN)
                rows += [text_sprite(p_, sz, WHITE, stroke=2) for p_ in parts]
                szs += [sz] * len(parts)
            pitch = round(max(szs) * 1.34)
            y0 = (zone[0] + zone[1]) / 2 - pitch * (len(rows) - 1) / 2
            ys = [y0 + pitch * i for i in range(len(rows))]
            cx = (px0 + px1) / 2 if side == 0 else W - (px0 + px1) / 2
            inks = [_ink(r) for r in rows]
            top = ys[0] - rows[0].height // 2 + inks[0][1]
            bot = ys[-1] - rows[-1].height // 2 + inks[-1][3]
            fits = fits and top >= zone[0] - 10 and bot <= py1 - 12
            cols.append(dict(head=head, rows=rows, ys=ys, cx=cx, mark=_mark_sprite(d["mark"]) if d.get("mark") else None,
                             ink_x=[(cx - r.width / 2 + i[0], cx - r.width / 2 + i[2]) for r, i in zip(rows, inks)], row_bottom=bot))
        if fits or start == VS_LINE_MIN:
            break
    l = min([px0] + [x for c in cols for x0_, _ in c["ink_x"] for x in (x0_,)])
    r = max([W - px0] + [x for c in cols for _, x1_ in c["ink_x"] for x in (x1_,)])
    bottom = max([py1] + [c["row_bottom"] for c in cols])
    return dict(panel=(px0, py0, px1, py1), cols=cols, size=start, bounds=(l, py0, r, bottom), bottom=bottom, rows_inside=bool(fits))


def make_versus_step(title, left, right, shown, prev=0, title_in=False, bg="alpha", src=None):
    """versus 逐步顯示(時間的純函式)。left / right = {"head", "lines"[1..2], "mark"?}。
    shown / prev 為步驟(0 = 標題與欄標題,1 = 左欄內容,2 = 右欄內容);prev 以前的步驟已在畫面上。
    面板填色不描外框;欄標題下是 PAL_TEXT2 短橫條;沒有中間的 VS 標記。"""
    base = _base(bg)
    lay = versus_layout(left, right, src)
    px0, py0, px1, py1 = lay["panel"]
    cols = lay["cols"]
    out = []
    for f in range(int(round(versus_step_seconds(prev, shown) * FPS))):
        t = f / FPS
        img = base.copy()
        d = ImageDraw.Draw(img)
        _title_block(img, title, BARS_TITLE_CY, t / 0.4 if title_in else 1.0)
        _src_note(img, src, t / 0.4 if title_in else 1.0)
        hp = clamp((t - 0.15) / 0.35) if title_in else 1.0
        if hp > 0:
            e = ease_out_cubic(hp)
            for side, c in enumerate(cols):
                x0, x1 = (px0, px1) if side == 0 else (W - px1, W - px0)
                dy = int((1 - e) * 20)
                d.rounded_rectangle([x0, py0 + dy, x1, py1 + dy], 26, fill=VS_FILL + (int(235 * e),))
                _blit(img, scale_alpha(c["head"], e), c["cx"], py0 + 88 + dy)
                bw = int(210 * e)
                if bw > 2:
                    d.rectangle([c["cx"] - bw // 2, py0 + 142, c["cx"] + bw // 2, py0 + 150], fill=PAL_TEXT2 + (255,))
        for lvl, c in ((1, cols[0]), (2, cols[1])):
            if lvl > shown:
                continue
            if lvl <= prev:
                tp = 1.0
            else:
                st = (VS_HEAD_S if prev <= 0 else VS_LEAD_S) + VS_STEP_S * (lvl - max(prev, 0) - 1)
                tp = clamp((t - st) / 0.3)
                mp = clamp((t - st - 0.2) / 0.3)
            if tp <= 0:
                continue
            e = ease_out_cubic(tp)
            for sp, y in zip(c["rows"], c["ys"]):
                _blit(img, scale_alpha(sp, e), c["cx"], y + (1 - e) * 18)
            if c["mark"] is not None:
                q = 1.0 if lvl <= prev else mp
                if q > 0:
                    s = ease_out_back(q) if q < 1 else 1.0
                    _blit(img, resize_rgba(c["mark"], (c["mark"].width * max(s, 0.05),) * 2), c["cx"], 508)
        out.append(to_np(img))
    return out


def _flow_geom(n):
    bw = int(min(520, (W - 2 * FLOW_EDGE - (n - 1) * 120) / n))
    gap = 120 if n >= 3 else 200
    total = n * bw + (n - 1) * gap
    x0 = (W - total) / 2
    return bw, gap, [x0 + bw / 2 + k * (bw + gap) for k in range(n)]


def flow_bounds(nodes):
    """flow 全部節點的墨跡 (l,t,r,b)(面板外框;節點內文字必在面板內)。"""
    bw, gap, cxs = _flow_geom(len(nodes))
    return (int(round(cxs[0] - bw / 2)), FLOW_BOX_Y, int(round(cxs[-1] + bw / 2)), FLOW_BOX_Y + FLOW_BOX_H)


def make_flow_step(title, nodes, shown, prev=0, title_in=False, bg="alpha", src=None):
    """flow 逐步顯示:節點 prev..shown-1 依序出現(第 2 個起,箭頭先畫出再彈出節點);前 prev 個已在畫面上。
    nodes = 字串陣列(2..4 個;可含 \\n);shown / prev = 已顯示的節點數。"""
    nodes = [norm_text(x) for x in nodes]
    n = len(nodes)
    bw, gap, cxs = _flow_geom(n)
    bh, cy = FLOW_BOX_H, FLOW_BOX_Y + FLOW_BOX_H / 2
    inner = bw - 56
    sprites = []
    for k, s in enumerate(nodes):
        rows, size = [], FLOW_TEXT_SIZE
        for seg in s.split("\n"):
            sz, parts = _fit_rows(seg, size, inner, size)    # 節點字級一律相同:放不下就換行,不縮字
            rows += [(p_, sz) for p_ in parts]
        pitch = int(max(sz for _, sz in rows) * 1.28)
        sp = Image.new("RGBA", (bw + 12, bh + 12), (0, 0, 0, 0))
        dr = ImageDraw.Draw(sp)
        if k == n - 1:
            dr.rounded_rectangle([6, 6, bw + 5, bh + 5], 28, fill=FLOW_FILL, outline=PAL_ACCENT + (255,), width=3)
        else:
            dr.rounded_rectangle([6, 6, bw + 5, bh + 5], 28, fill=FLOW_FILL)
        y0 = sp.height / 2 - pitch * (len(rows) - 1) / 2
        for i, (p_, sz) in enumerate(rows):
            ts = text_sprite(p_, sz, WHITE, stroke=2)
            sp.alpha_composite(ts, (int(sp.width / 2 - ts.width / 2), int(y0 + i * pitch - ts.height / 2)))
        sprites.append(sp)
    # 每個新節點的時間:(箭頭起點, 節點起點)
    sched, t = {}, (FLOW_NODE0_S if prev <= 0 else FLOW_LEAD_S)
    for k in range(max(prev, 0), shown):
        if k == 0:
            sched[k] = (None, t)
            t += FLOW_POP_S
        else:
            sched[k] = (t, t + FLOW_ARROW_S)
            t += FLOW_ARROW_S + FLOW_POP_S
    base = _base(bg)
    out = []
    for f in range(int(round(flow_step_seconds(prev, shown) * FPS))):
        tt = f / FPS
        img = base.copy()
        d = ImageDraw.Draw(img)
        _title_block(img, title, 150, tt / 0.4 if title_in else 1.0)
        _src_note(img, src, tt / 0.4 if title_in else 1.0)
        for k in range(shown):
            ap, npg = (1.0, 1.0) if k < prev else (None, None)
            if k >= prev:
                a_t, n_t = sched[k]
                ap = 1.0 if a_t is None else clamp((tt - a_t) / FLOW_ARROW_S)
                npg = clamp((tt - n_t) / FLOW_POP_S)
            if k > 0 and ap > 0:                       # 箭頭:由左至右畫出
                xa, xb = cxs[k - 1] + bw / 2 + 16, cxs[k] - bw / 2 - 16
                xe = xa + (xb - xa) * ease_out_cubic(ap)
                if xe - xa > 4:
                    d.rectangle([xa, cy - 5, max(xa, xe - 22), cy + 5], fill=PAL_TEXT2 + (255,))
                    d.polygon([(xe, cy), (xe - 36, cy - 28), (xe - 36, cy + 28)], fill=PAL_TEXT2 + (255,))
            if npg > 0:
                s = ease_out_back(npg) if npg < 1 else 1.0
                sp = resize_rgba(scale_alpha(sprites[k], ease_out_cubic(npg)),
                                 (sprites[k].width * max(s, 0.05), sprites[k].height * max(s, 0.05)))
                _blit(img, sp, cxs[k], cy)
        out.append(to_np(img))
    return out


# ---- cols 直條圖 / share 佔比堆疊條 / num 數字卡(2026-10-13;規格見 ANIM_DESIGN.md §1、README §5)
COLS_BASE_Y, COLS_TOP_Y = 700, 330      # 基線 y / 最高柱頂 y
COLS_SLOT_MAX, COLS_AREA_W, COLS_BW_MAX, COLS_BW_RATIO = 280, 1500, 150, 0.6
COLS_CORNER, COLS_LABEL_GAP, COLS_VAL_GAP, COLS_LINE_PAD = 10, 18, 16, 24
COLS_MIN, COLS_MAX = 2, 7
SHARE_LABEL_RIGHT, SHARE_X0, SHARE_W = 420, 460, 1280
SHARE_BH, SHARE_GAP, SHARE_SEG_GAP, SHARE_CORNER = 96, 72, 4, 10
SHARE_VAL_FS, SHARE_LEGEND_FS, SHARE_LEGEND_CY, SHARE_SW, SHARE_ITEM_GAP = 60, 48, 275, 28, 56
SHARE_ROWS_TOP, SHARE_STEP_S, SHARE_LEAD_S = 340, 0.6, 0.05
SHARE_VAL_DARK, SHARE_LUM_DARK = (27, 20, 20), 0.45     # 段底相對亮度 > 0.45 時段內數值用深字
SHARE_SEQ = [PAL_NEUTRAL, PAL_ACCENT, (0x4C, 0x8D, 0xFF), (0xC8, 0x32, 0x2B)]
NUM_LABEL_FS, NUM_LABEL_CY, NUM_BIG_FS, NUM_UNIT_RATIO, NUM_BIG_CY, NUM_MAX_W = 72, 230, 300, 0.45, 450, 1728
NUM_CMP_FS, NUM_CMP_CY, NUM_TRI_W, NUM_TRI_H, NUM_TRI_GAP = 64, 660, 44, 38, 20
NUM_LABEL_IN_S, NUM_BIG_T0, NUM_COUNT_S, NUM_FADE_S, NUM_CMP_DELAY_S, NUM_CMP_FADE_S = 0.4, 0.3, 0.8, 0.35, 0.4, 0.35


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _title_box(title, cy=BARS_TITLE_CY, size=BARS_TITLE_FS):
    """標題(含底下短橫條)的墨跡框(最終狀態)。"""
    sp = text_sprite(norm_text(title), size, WHITE, stroke=2)
    l, t, r, b = _ink(sp)
    x, y = int(round(W / 2 - sp.width / 2)), int(round(cy - sp.height / 2))
    return (x + l, y + t, x + r, max(y + b, cy + sp.height // 2 + 13))


def _put_ink(sp, x_ink, y_ink, anchor="l"):
    """貼圖左上 xy 與墨跡框:anchor l = 墨跡左緣在 x_ink、r = 右緣、c = 水平中心;y_ink = 墨跡垂直中心。"""
    l, t, r, b = _ink(sp)
    x = x_ink - (l if anchor == "l" else r if anchor == "r" else (l + r) / 2)
    y = y_ink - (t + b) / 2
    x, y = int(round(x)), int(round(y))
    return (x, y), (x + l, y + t, x + r, y + b)


class _ColsLayout:
    """cols 直條圖版面。items = [[標籤, 正數, 單位?, {"hi"?}?], ...]。基線 y=700,最高柱頂 y=330;柱寬 min(150, 槽寬*0.6),槽寬 min(280, 1500/n)。
    顏色:hi:true 的 PAL_ACCENT、其餘 PAL_NEUTRAL;沒有任何 hi 鍵時自動強調最大值(數值全相同則不強調)。"""

    def __init__(self, title, items, src=None):
        n = len(items)
        if not COLS_MIN <= n <= COLS_MAX:
            raise ValueError(f"直條圖須有 {COLS_MIN}–{COLS_MAX} 根(收到 {n} 根)")
        self.title, self.items, self.src, self.n = title, list(items), src, n
        self.slot = min(COLS_SLOT_MAX, COLS_AREA_W / n)
        self.bw = min(COLS_BW_MAX, self.slot * COLS_BW_RATIO)
        self.x0 = (W - n * self.slot) / 2
        vals = [float(it[1]) for it in self.items]
        self.vmax = max(vals)
        opts = [_bar_opt(it) for it in self.items]
        explicit = any("hi" in o for o in opts)
        auto = not explicit and len(set(vals)) > 1
        self.hi = [bool(o.get("hi")) if explicit else (auto and v == self.vmax) for o, v in zip(opts, vals)]
        self.labels = [text_sprite(norm_text(it[0]), BARS_LABEL_FS, BARS_LABEL_RGB, stroke=2) for it in self.items]
        for it, sp in zip(self.items, self.labels):
            w = _ink(sp)[2] - _ink(sp)[0]
            if w > self.slot:
                raise ValueError(f"直條圖標籤過長:「{it[0]}」寬 {w}px 超過槽寬 {self.slot:.0f}px(縮短標籤或減少根數)")
        self.vals = []
        for it, hi in zip(self.items, self.hi):
            unit = norm_text(it[2]) if len(it) > 2 and isinstance(it[2], str) else ""
            self.vals.append(_val_sprite(_fmt_num(it[1], float(it[1])), unit, BARS_VAL_FS_HI if hi else BARS_VAL_FS))
        self.line = (max(CONTENT_EDGE, int(self.x0 - COLS_LINE_PAD)), min(W - CONTENT_EDGE, int(self.x0 + n * self.slot + COLS_LINE_PAD)))
        self.boxes, bars = [("title", _title_box(title))], []
        for k in range(n):
            pl = self.place(k)
            bars.append(tuple(int(round(x)) for x in pl["bar"]))
            self.boxes += [(f"label{k}", pl["label"][1]), (f"val{k}", pl["val"][1])]
        self.bounds = _union([b for _, b in self.boxes] + bars + [(self.line[0], COLS_BASE_Y, self.line[1], COLS_BASE_Y + BARS_BASELINE_W)])

    def color(self, k):
        return BARS_HI_COLOR if self.hi[k] else BARS_COLOR

    def place(self, k, e=1.0):
        cx = self.x0 + self.slot * (k + 0.5)
        h = (COLS_BASE_Y - COLS_TOP_Y) * float(self.items[k][1]) / self.vmax * e
        out = dict(bar=(cx - self.bw / 2, COLS_BASE_Y - h, cx + self.bw / 2, COLS_BASE_Y), h=h)
        l, t, r, b = _ink(self.labels[k])
        x, y = int(round(cx - (l + r) / 2)), int(round(COLS_BASE_Y + COLS_LABEL_GAP - t))
        out["label"] = ((x, y), (x + l, y + t, x + r, y + b))
        l, t, r, b = _ink(self.vals[k])
        x, y = int(round(cx - (l + r) / 2)), int(round(COLS_BASE_Y - h - COLS_VAL_GAP - b))
        out["val"] = ((x, y), (x + l, y + t, x + r, y + b))
        return out

    def axis(self, img):
        img.alpha_composite(Image.new("RGBA", (self.line[1] - self.line[0], BARS_BASELINE_W), PAL_LINE + (255,)), (self.line[0], COLS_BASE_Y))

    def col(self, img, d, k, e, lt):
        pl = self.place(k, e)
        _blit_xy(img, scale_alpha(self.labels[k], lt), *pl["label"][0])
        x0, y0, x1, y1 = pl["bar"]
        if pl["h"] > 2:
            fill = self.color(k) + (255,)
            if pl["h"] >= 2 * COLS_CORNER:
                d.rounded_rectangle([x0, y0, x1, y1], COLS_CORNER, fill=fill, corners=(True, True, False, False))
            else:
                d.rectangle([x0, y0, x1, y1], fill=fill)
        va = clamp((e - BARS_VAL_AT) / (1 - BARS_VAL_AT))
        if va > 0:
            _blit_xy(img, scale_alpha(self.vals[k], va), *pl["val"][0])


def cols_step_seconds(prev, shown):
    return bars_step_seconds(prev, shown)


def make_cols_step(title, items, shown, prev=0, title_in=False, bg="alpha", src=None):
    """cols 逐步顯示(時間的純函式):前 prev 根已在畫面上,第 prev..shown-1 根依序長出(每根 0.5 秒 ease-out,長到 80% 數值淡入);比例尺固定用全部最大值。shown=0 = 只有標題。"""
    lay = _ColsLayout(title, items, src)
    base = _base(bg)
    out = []
    for f in range(int(round(cols_step_seconds(prev, shown) * FPS))):
        t = f / FPS
        img = base.copy()
        d = ImageDraw.Draw(img)
        _title_block(img, title, BARS_TITLE_CY, t / 0.4 if title_in else 1.0)
        _src_note(img, src, t / 0.4 if title_in else 1.0)
        if shown > 0:
            lay.axis(img)
        for k in range(shown):
            if k < prev:
                e, lt = 1.0, 1.0
            else:
                s = BARS_STEP_LEAD_S + BARS_STEP_GAP_S * (k - prev)
                if t < s:
                    continue
                e, lt = ease_out_cubic((t - s) / BARS_STEP_GROW_S), clamp((t - s) / 0.25)
            lay.col(img, d, k, e, lt)
        out.append(to_np(img))
    return out


# ---- share
def share_step_seconds(prev, shown):
    if shown <= 0:
        return 0.5
    if shown <= prev:
        return 0.1
    return SHARE_LEAD_S + SHARE_STEP_S * (shown - prev - 1) + SHARE_STEP_S + 0.1


class _ShareLayout:
    """share 佔比堆疊條版面。rows = [{label, parts:[[名稱, 數值, 顏色?], ...]}, ...](1–4 列,每列 2–4 段,數值總和 99–101)。
    條左端 x=460、寬 1280;條厚 96 / 列距 72,放不下(有 src 或 4 列)時兩者等比縮小(下限約 0.55 倍,再不行報錯);同一名稱所有列同色(以第一次出現為準)。"""

    def __init__(self, title, rows, unit="%", src=None):
        r = len(rows)
        if not 1 <= r <= 4:
            raise ValueError(f"佔比堆疊條須有 1–4 列(收到 {r} 列)")
        self.title, self.rows, self.src, self.n = title, rows, src, r
        self.unit = norm_text(unit) if unit else ""
        self.cmap, order, used = {}, [], []
        for row in rows:
            for i, p in enumerate(row["parts"]):
                if p[0] in self.cmap:
                    continue
                spec = p[2] if len(p) > 2 and p[2] else None
                c = _bar_color(spec, None) if spec else next((s for s in SHARE_SEQ[i % 4:] + SHARE_SEQ if s not in used), SHARE_SEQ[i % 4])
                self.cmap[p[0]] = c
                used.append(c)
                order.append(p[0])
        self.names = order
        self.legend, self.boxes = [], [("title", _title_box(title))]
        tsp = [text_sprite(norm_text(nm), SHARE_LEGEND_FS, PAL_TEXT, stroke=2) for nm in order]
        wid = [SHARE_SW + 14 + _ink(sp)[2] - _ink(sp)[0] for sp in tsp]
        x = (W - (sum(wid) + SHARE_ITEM_GAP * (len(wid) - 1))) / 2
        leg_bottom = SHARE_LEGEND_CY
        for nm, sp, w in zip(order, tsp, wid):
            y0 = int(round(SHARE_LEGEND_CY - SHARE_SW / 2))
            sw = (int(round(x)), y0, int(round(x)) + SHARE_SW, y0 + SHARE_SW)
            xy, bb = _put_ink(sp, x + SHARE_SW + 14, SHARE_LEGEND_CY, "l")
            self.legend.append(dict(name=nm, sw=sw, sp=sp, xy=xy))
            self.boxes += [(f"圖例色塊{nm}", sw), (f"圖例{nm}", bb)]
            leg_bottom = max(leg_bottom, bb[3])
            x += w + SHARE_ITEM_GAP
        bottom_max = BARS_BOTTOM_SRC if src else BARS_BOTTOM_MAX
        top_min = max(SHARE_ROWS_TOP, leg_bottom + 40)
        avail, s = bottom_max - top_min, 1.0
        while True:
            bh, gap = round(SHARE_BH * s), round(SHARE_GAP * s)
            total = r * bh + (r - 1) * gap
            if total <= avail:
                break
            s -= 0.02
            if s < 0.55:
                raise ValueError("佔比堆疊條排不下(列數過多或有 src 時空間不足)")
        self.bh, self.gap = bh, gap
        y0 = top_min + (avail - total) / 2
        self.tops = [int(round(y0 + i * (bh + gap))) for i in range(r)]
        self.segs, self.lbl = [], []
        for i, row in enumerate(rows):
            ps = row["parts"]
            tot = float(sum(p[1] for p in ps))
            usable = SHARE_W - SHARE_SEG_GAP * (len(ps) - 1)
            row_segs, xa = [], 0.0
            for p in ps:
                xb = xa + usable * float(p[1]) / tot
                seg_rgb = SHARE_VAL_DARK if _rel_lum(self.cmap[p[0]]) > SHARE_LUM_DARK else None   # 亮底(琥珀)配深字
                vs = _val_sprite(_fmt_num(p[1], float(p[1])), self.unit, SHARE_VAL_FS, seg_rgb)
                l, t, r_, b_ = _ink(vs)
                xy = (int(round(SHARE_X0 + (xa + xb) / 2 - (l + r_) / 2)), int(round(self.tops[i] + bh / 2 - (t + b_) / 2)))
                bb = (xy[0] + l, xy[1] + t, xy[0] + r_, xy[1] + b_)
                show = (r_ - l) + 32 <= (xb - xa)
                row_segs.append(dict(name=p[0], x0=xa, x1=xb, vs=vs, show=show, xy=xy, bb=bb))
                if show:
                    self.boxes.append((f"值{i}{p[0]}", bb))
                xa = xb + SHARE_SEG_GAP
            self.segs.append(row_segs)
            lsp = text_sprite(norm_text(row["label"]), BARS_LABEL_FS, BARS_LABEL_RGB, stroke=2)
            xy, bb = _put_ink(lsp, SHARE_LABEL_RIGHT, self.tops[i] + bh / 2, "r")
            self.lbl.append(dict(sp=lsp, xy=xy, bb=bb))
            self.boxes.append((f"列標籤{i}", bb))
        self.bounds = _union([b for _, b in self.boxes] + [(SHARE_X0, self.tops[0], SHARE_X0 + SHARE_W, self.tops[-1] + bh)])

    def row_layer(self, i, e):
        """第 i 列在展開進度 e(0..1)的貼圖(左上 = (SHARE_X0, tops[i]));由左至右展開並裁切;展不到的段數值不畫。"""
        lay = Image.new("RGBA", (SHARE_W, self.bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        rx, ns = e * SHARE_W, len(self.segs[i])
        for j, sg in enumerate(self.segs[i]):
            fill = self.cmap[sg["name"]] + (255,)
            box = [sg["x0"], 0, sg["x1"] - 1, self.bh - 1]
            if j == ns - 1:
                d.rounded_rectangle(box, SHARE_CORNER, fill=fill, corners=(False, True, True, False))
            else:
                d.rectangle(box, fill=fill)
            if sg["show"]:
                w = sg["x1"] - sg["x0"]
                va = clamp((rx - sg["x0"] - w * 0.6) / (w * 0.4))
                if va > 0:
                    _blit_xy(lay, scale_alpha(sg["vs"], va), sg["xy"][0] - SHARE_X0, sg["xy"][1] - self.tops[i])
        cw = int(round(rx))
        return lay.crop((0, 0, cw, self.bh)) if cw > 0 else None


def make_share_step(title, rows, shown, prev=0, title_in=False, bg="alpha", unit="%", src=None):
    """share 逐步顯示:前 prev 列已在畫面上,第 prev..shown-1 列依序由左至右展開(每列 0.6 秒)。shown=0 = 標題與圖例。"""
    lay = _ShareLayout(title, rows, unit, src)
    base = _base(bg)
    out = []
    for f in range(int(round(share_step_seconds(prev, shown) * FPS))):
        t = f / FPS
        img = base.copy()
        p = t / 0.4 if title_in else 1.0
        _title_block(img, title, BARS_TITLE_CY, p)
        _src_note(img, src, p)
        pe = ease_out_cubic(clamp(p))
        if pe > 0:
            for lg in lay.legend:
                sw = Image.new("RGBA", (SHARE_SW, SHARE_SW), lay.cmap[lg["name"]] + (int(255 * pe),))
                img.alpha_composite(sw, (lg["sw"][0], lg["sw"][1]))
                _blit_xy(img, scale_alpha(lg["sp"], pe), *lg["xy"])
        for i in range(shown):
            if i < prev:
                e, lt = 1.0, 1.0
            else:
                s = SHARE_LEAD_S + SHARE_STEP_S * (i - prev)
                if t < s:
                    continue
                e, lt = ease_out_cubic((t - s) / SHARE_STEP_S), clamp((t - s) / 0.25)
            _blit_xy(img, scale_alpha(lay.lbl[i]["sp"], lt), *lay.lbl[i]["xy"])
            rl = lay.row_layer(i, e)
            if rl is not None:
                img.alpha_composite(rl, (SHARE_X0, lay.tops[i]))
        out.append(to_np(img))
    return out


# ---- num
_NUM_TOK = re.compile(r"\d[\d,]*(?:\.\d+)?|→|[^\d→\s]+|\s+")


def _num_runs(big):
    """big 拆成 [dict(text, kind=num|unit, gap=與前一段的間距)]:數字與 → 為 num(300px),其餘為 unit(0.45 倍)。"""
    runs, ws = [], False
    for tk in _NUM_TOK.findall(big):
        if tk.isspace():
            ws = True
            continue
        kind = "num" if (tk[0].isdigit() or tk == "→") else "unit"
        gap = 0 if not runs else (12 if not ws else (28 if kind == "unit" or runs[-1]["kind"] == "unit" else 40))
        runs.append(dict(text=tk, kind=kind, gap=gap))
        ws = False
    return runs


def num_is_count(big):
    """big 開頭是單一數字(可含千分位與小數)且沒有「→」:數字由 0 數到目標。"""
    runs = _num_runs(big)
    return bool(runs) and "→" not in big and runs[0]["kind"] == "num" and re.fullmatch(r"\d[\d,]*(\.\d+)?", runs[0]["text"]) is not None


def num_step_seconds(prev, shown, big=""):
    """num 逐步:level 1 = label + big、level 2 = compare。shown <= prev:0.1 秒凍結。"""
    if shown <= prev:
        return 0.1
    if prev <= 0:
        t = NUM_BIG_T0 + (NUM_COUNT_S if num_is_count(big) else NUM_FADE_S)
        if shown >= 2:
            t += NUM_CMP_DELAY_S + NUM_CMP_FADE_S
    else:
        t = 0.05 + NUM_CMP_FADE_S
    return t + 0.1


def _tri_sprite(up, color, ss=4):
    w, h = NUM_TRI_W, NUM_TRI_H
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    pts = [(w / 2, 0), (0, h), (w, h)] if up else [(0, 0), (w, 0), (w / 2, h)]
    ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y in pts], fill=color + (255,))
    return im.resize((w, h), Image.LANCZOS)


class _NumLayout:
    """num 數字卡版面:label(可省略)72px 中心 y=230、big 數字 300px(單位 0.45 倍,共用基線,整行置中於 y=450,超過 1728 等比縮小)、compare 64px 中心 y=660(tone up/down 加三角)。"""

    def __init__(self, label, big, compare=None, tone=None, src=None):
        self.label, self.big, self.compare, self.tone, self.src = label, big, compare, tone, src
        self.runs = _num_runs(norm_text(big))
        if not self.runs:
            raise ValueError("num 的 big 不可為空")
        S = NUM_BIG_FS
        self._layout(S)
        for _ in range(30):
            if self.total <= NUM_MAX_W or S <= 60:
                break
            S = max(60, int(S * NUM_MAX_W / self.total * 0.99))
            self._layout(S)
        self.size = S
        self.count = num_is_count(big)
        self.boxes = [("big", self.big_box)]
        self.lsp = self.lxy = None      # label 可省略(None / 空字串):不畫頂端 label,其餘版面不變
        if label and label.strip():
            self.lsp = text_sprite(norm_text(label), NUM_LABEL_FS, PAL_TEXT2, stroke=2)
            self.lxy, lbb = _put_ink(self.lsp, W / 2, NUM_LABEL_CY, "c")
            self.boxes.insert(0, ("label", lbb))
        self.csp = self.tri = None
        if compare:
            self.csp = text_sprite(norm_text(compare), NUM_CMP_FS, PAL_TEXT, stroke=2)
            l, t, r, b = _ink(self.csp)
            has_tri = tone in ("up", "down")
            gx = W / 2 - ((r - l) + ((NUM_TRI_W + NUM_TRI_GAP) if has_tri else 0)) / 2
            if has_tri:
                self.tri = _tri_sprite(tone == "up", PAL_ACCENT if tone == "up" else PAL_NEG)
                self.txy = (int(round(gx)), int(round(NUM_CMP_CY - NUM_TRI_H / 2)))
                self.boxes.append(("三角", (self.txy[0], self.txy[1], self.txy[0] + NUM_TRI_W, self.txy[1] + NUM_TRI_H)))
                gx += NUM_TRI_W + NUM_TRI_GAP
            self.cxy, cbb = _put_ink(self.csp, gx, NUM_CMP_CY, "l")
            self.boxes.append(("compare", cbb))
        self.bounds = _union([b for _, b in self.boxes])

    def _layout(self, S):
        """依字級 S 排 big 各段:self.items(貼圖、左上 xy、基線列 bl)、total = 墨跡總寬、big_box = 墨跡框(垂直中心 = NUM_BIG_CY)。"""
        sizes = [S if r["kind"] == "num" else max(20, round(S * NUM_UNIT_RATIO)) for r in self.runs]
        sps = [text_sprite(r["text"], sz, WHITE, stroke=2) for r, sz in zip(self.runs, sizes)]
        bls = [_baseline(r["text"], sz) for r, sz in zip(self.runs, sizes)]
        B = max(bls)
        xs, x = [], 0
        for r, sp in zip(self.runs, sps):
            l, _, rr, _ = _ink(sp)
            x += r["gap"]
            xs.append(x - l)
            x += rr - l
        self.total = x
        top = min(B - bl + _ink(sp)[1] for bl, sp in zip(bls, sps))
        bot = max(B - bl + _ink(sp)[3] for bl, sp in zip(bls, sps))
        x_off, y_off = (W - x) / 2, NUM_BIG_CY - (top + bot) / 2
        self.items, ib = [], []
        for r, sz, sp, bl, xx in zip(self.runs, sizes, sps, bls, xs):
            xy = (int(round(x_off + xx)), int(round(y_off + B - bl)))
            l, t, rr, b = _ink(sp)
            self.items.append(dict(text=r["text"], size=sz, sp=sp, xy=xy, bl=bl))
            ib.append((xy[0] + l, xy[1] + t, xy[0] + rr, xy[1] + b))
        self.big_box, self.ink_boxes = _union(ib), ib

    def count_sprite(self, e):
        """count-up 中第一段數字的貼圖與左上 xy(墨跡右緣對齊終值右緣、基線不變)。e = 0..1(已 ease)。"""
        it, ib = self.items[0], self.ink_boxes[0]
        txt = it["text"]
        dec = len(txt.split(".")[1]) if "." in txt else 0
        v = float(txt.replace(",", "")) * e
        s = f"{v:,.{dec}f}" if "," in txt else f"{v:.{dec}f}"
        sp = text_sprite(s, it["size"], WHITE, stroke=2)
        return sp, (ib[2] - _ink(sp)[2], it["xy"][1] + it["bl"] - _baseline(s, it["size"]))


def make_num_step(label, big, compare=None, tone=None, shown=None, prev=0, title_in=False, bg="alpha", src=None):
    """num 逐步顯示(時間的純函式):level 1 = label + big(數字由 0 數到目標,或淡入);level 2 = compare(big 到位 0.4 秒後淡入)。shown 省略 = 全部。"""
    if shown is None:
        shown = 2 if compare else 1
    lay = _NumLayout(label, big, compare, tone, src)
    base = _base(bg)
    dur_big = NUM_COUNT_S if lay.count else NUM_FADE_S
    big_end = NUM_BIG_T0 + dur_big
    out = []
    for f in range(int(round(num_step_seconds(prev, shown, big) * FPS))):
        t = f / FPS
        img = base.copy()
        p = clamp(t / NUM_LABEL_IN_S) if (title_in and prev <= 0) else 1.0
        if lay.lsp is not None:
            _blit_xy(img, scale_alpha(lay.lsp, ease_out_cubic(p)), *lay.lxy)
        _src_note(img, src, p)
        pb = 1.0 if prev >= 1 else clamp((t - NUM_BIG_T0) / dur_big)
        if pb > 0:
            if lay.count:
                sp, xy = lay.count_sprite(ease_out_cubic(pb)) if pb < 1 else (None, None)
                for k, it in enumerate(lay.items):
                    if k == 0 and sp is not None:
                        _blit_xy(img, sp, *[int(round(v)) for v in xy])
                    else:
                        _blit_xy(img, it["sp"], *it["xy"])
            else:
                for it in lay.items:
                    _blit_xy(img, scale_alpha(it["sp"], ease_out_cubic(pb)), *it["xy"])
        if shown >= 2 and lay.csp is not None:
            c0 = (big_end + NUM_CMP_DELAY_S) if prev <= 0 else SHARE_LEAD_S
            pc = 1.0 if prev >= 2 else ease_out_cubic(clamp((t - c0) / NUM_CMP_FADE_S))
            if pc > 0:
                if lay.tri is not None:
                    _blit_xy(img, scale_alpha(lay.tri, pc), *lay.txy)
                _blit_xy(img, scale_alpha(lay.csp, pc), *lay.cxy)
        out.append(to_np(img))
    return out


def new_layout(a):
    """cols / share / num 的版面物件(含 .boxes / .bounds);規格不合會 raise ValueError。"""
    t = a["type"]
    if t == "cols":
        return _ColsLayout(a["title"], a["items"], a.get("src"))
    if t == "share":
        return _ShareLayout(a["title"], a["rows"], a.get("unit", "%"), a.get("src"))
    return _NumLayout(a.get("label"), a["big"], a.get("compare"), a.get("tone"), a.get("src"))


# ---- 內容邊界(版面檢查用;build._check_src 呼叫)
CONTENT_BOTTOM, SRC_CONTENT_BOTTOM, CONTENT_EDGE = 800, 768, 96     # 內容下緣上限 / 有 src 時 / 左右離邊下限


def anim_bounds(a, points=None):
    """timeline / span / list / versus / flow 的內容墨跡框 (l,t,r,b)(最終狀態);其他類型回傳 None。points = timeline.points。"""
    t = a.get("type")
    if t == "timeline":
        return timeline_layout(points)["bounds"] if points else None
    if t == "span":
        return span_bounds(a["from"], a["to"], a["big"], a.get("caption", ""), a.get("src"))
    if t == "list":
        return list_layout(a["items"], a.get("note"), a.get("src"))["bounds"]
    if t == "versus":
        return versus_layout(a["left"], a["right"], a.get("src"))["bounds"]
    if t == "flow":
        return flow_bounds(a["nodes"])
    if t in ("cols", "share", "num"):
        return new_layout(a).bounds
    return None


def anim_problems(a, points=None):
    """版面問題清單(字串;空 = 合格):下緣超過 800(有 src 時 768)、左右離畫面邊 < 96,以及各類型專屬項目
    (timeline 說明放不下 / list 備註貼到最後一項 / versus 內文超出面板)。"""
    try:
        bb = anim_bounds(a, points)
    except ValueError as e:     # cols 標籤過長、share 排不下等
        return [str(e)]
    if bb is None:
        return []
    t, probs = a["type"], []
    lim = SRC_CONTENT_BOTTOM if a.get("src") else CONTENT_BOTTOM
    if bb[3] > lim:
        probs.append(f"內容下緣 y={bb[3]} 超過 {lim}" + ("(有 src)" if a.get("src") else ""))
    if bb[0] < CONTENT_EDGE or bb[2] > W - CONTENT_EDGE:
        probs.append(f"內容左右 x={bb[0]}..{bb[2]} 離畫面邊不足 {CONTENT_EDGE}px")
    if t == "timeline" and not timeline_layout(points)["ok"]:
        probs.append("timeline 說明降到 50px 仍放不下(超過 3 行或相鄰說明相距 < 24px)")
    if t == "list" and list_layout(a["items"], a.get("note"), a.get("src"))["note_overlap"]:
        probs.append("list 的 note 離最後一項不足 24px")
    if t == "versus" and not versus_layout(a["left"], a["right"], a.get("src"))["rows_inside"]:
        probs.append("versus 內文放不進面板(字級 56 仍超出)")
    if t in ("cols", "share", "num"):
        boxes = list(new_layout(a).boxes)
        if a.get("src"):
            boxes.append(("src", src_place(a["src"])[2]))
        probs += [f"文字框重疊: {x}/{y}" for i, (x, bx) in enumerate(boxes) for y, by in boxes[i + 1:] if _hit(bx, by)]
    return probs


# ---- 通用動畫背景「光點星座」(獨立深色底鏡頭用;時間的純函式:固定種子、無時鐘、無跨格狀態)
# 金色光點各自小幅正弦漂移、細線連成星座、亮度輕微閃爍、模糊大光斑更慢漂移;中央文字區與字幕帶壓暗。
# 取樣時間 t = 該格在「成片中的絕對時間」(由 build 傳入),相鄰動畫鏡頭的背景因此連續;週期 STAR_LOOP 秒。
STAR_VER = 1
STAR_LOOP = 5.0
_STAR_GOLD = np.array([212, 168, 75], np.float32)
_STAR_OP = 0.34
_TAU = 2 * math.pi


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


STAR_W, STAR_H = W, H        # 星座背景固定橫式尺寸(直式由 over_star 裁中段),不隨 set_profile 變


class _StarBG:
    def __init__(self):
        xx, yy = np.meshgrid(np.arange(STAR_W, dtype=np.float32), np.arange(STAR_H, dtype=np.float32))
        rng = np.random.RandomState(5)
        pts, tries = [], 0
        while len(pts) < 46 and tries < 5000:
            tries += 1
            x, y = rng.uniform(30, STAR_W - 30), rng.uniform(30, 870)
            if all((x - a) ** 2 + (y - b) ** 2 > 190 ** 2 for a, b in pts):
                pts.append((x, y))
        self.pts = pts
        edges = set()
        for i, (x, y) in enumerate(pts):
            ds = sorted(range(len(pts)), key=lambda j: (pts[j][0] - x) ** 2 + (pts[j][1] - y) ** 2)[1:3]
            for j in ds:
                if math.hypot(pts[j][0] - x, pts[j][1] - y) < 380:
                    edges.add((min(i, j), max(i, j)))
        self.edges = sorted(edges)
        self.rad = [rng.choice([3, 4, 5, 7]) for _ in pts]
        self.bok = [(rng.uniform(0, STAR_W), rng.uniform(0, 860), rng.uniform(70, 150), rng.uniform(70, 140)) for _ in range(9)]
        mr = np.random.RandomState(21)
        self.mot = []
        for _ in pts:
            n = 1 if mr.rand() < 0.65 else 2
            amp = mr.uniform(11, 19) if n == 1 else mr.uniform(5, 9)
            self.mot.append((n, amp, _TAU * mr.rand(), _TAU * mr.rand(), _TAU * mr.rand()))
        self.bmot = [(mr.uniform(8, 13), _TAU * mr.rand(), _TAU * mr.rand(), _TAU * mr.rand()) for _ in self.bok]
        d = np.sqrt(((xx - 960) / 760) ** 2 + ((yy - 430) / 330) ** 2)
        center = 1 - 0.55 * (1 - _smooth(0.6, 1.5, d))
        band = _smooth(840, 880, yy) * (1 - _smooth(970, 1010, yy))
        self.w = (center * (1 - 0.9 * band)).astype(np.float32)
        self.base = np.asarray(_dark_bg().convert("RGB"), np.float32)

    def intensity(self, t):
        """0..1 強度圖(已含壓暗權重與不透明度)。"""
        ss = 2
        img = Image.new("L", (STAR_W * ss, STAR_H * ss), 0)
        d = ImageDraw.Draw(img)
        glow = Image.new("L", (STAR_W, STAR_H), 0)
        dg = ImageDraw.Draw(glow)
        pos, tw = [], []
        for (x, y), (n, amp, px, py, pt) in zip(self.pts, self.mot):
            a = _TAU * n * t / STAR_LOOP
            pos.append((x + amp * math.sin(a + px), y + amp * math.cos(a + py)))
            tw.append(1.0 + 0.18 * math.sin(_TAU * t / STAR_LOOP + pt))
        for i, j in self.edges:
            k = 0.5 * (tw[i] + tw[j])
            d.line([pos[i][0] * ss, pos[i][1] * ss, pos[j][0] * ss, pos[j][1] * ss], fill=int(130 * k), width=2)
        for (x, y), r, k in zip(pos, self.rad, tw):
            d.ellipse([(x - r) * ss, (y - r) * ss, (x + r) * ss, (y + r) * ss], fill=int(min(255, 255 * k)))
            dg.ellipse([x - r * 3, y - r * 3, x + r * 3, y + r * 3], fill=int(120 * k))
        p = np.asarray(img.reduce(ss), np.float32) / 255.0
        p += np.asarray(glow.filter(ImageFilter.GaussianBlur(9)), np.float32) / 255.0 * 0.7
        q = 4                                  # 模糊光斑在 1/4 解析度算,再放大
        bok = Image.new("L", (STAR_W // q, STAR_H // q), 0)
        db = ImageDraw.Draw(bok)
        a = _TAU * t / STAR_LOOP
        for (x, y, r, v), (amp, p1, p2, p3) in zip(self.bok, self.bmot):
            bx, by = x + amp * math.sin(a + p1), y + amp * math.cos(a + p2)
            k = 1 + 0.10 * math.sin(a + p3)
            db.ellipse([(bx - r) / q, (by - r) / q, (bx + r) / q, (by + r) / q], fill=int(v * k))
        bok = bok.filter(ImageFilter.GaussianBlur(28 / q)).resize((STAR_W, STAR_H), Image.BICUBIC)
        p += np.asarray(bok, np.float32) / 255.0 * 0.55
        return np.clip(p, 0, 1) * self.w * _STAR_OP

    def frame(self, t):
        a = self.intensity(t)[..., None]
        rgb = self.base * (1 - a) + _STAR_GOLD[None, None, :] * a
        return np.clip(rgb, 0, 255).round().astype(np.uint8)


_STAR = None
STAR_N = int(round(STAR_LOOP * FPS))      # 一個循環的格數(150);背景只跟「格索引 mod STAR_N」有關
_STAR_MEM_MAX = 60                        # 同行程記憶體快取上限(每張 HxWx3 uint8 約 6.2MB,60 張約 373MB)
_star_mem = collections.OrderedDict()     # 格索引餘數 -> 背景 ndarray(LRU)


def _star_compute(t):
    """原本的逐格即時計算(不經快取);快取內容與逐像素比對的基準。"""
    global _STAR
    if _STAR is None:
        _STAR = _StarBG()
    return _STAR.frame(float(t))


def _star_dir():
    import paths as _P
    return _P.BUILD / "_anim" / f"star_v{STAR_VER}"


def _star_cached(k):
    """第 k(0..STAR_N-1)格的背景:記憶體 -> 磁碟 PNG(無損)-> 重算並寫入。寫檔先寫暫存檔再改名(平行算圖安全)。"""
    bg = _star_mem.get(k)
    if bg is not None:
        _star_mem.move_to_end(k)
        return bg
    p = _star_dir() / f"{k:03d}.png"
    try:
        with Image.open(p) as im:
            bg = np.array(im if im.mode == "RGB" else im.convert("RGB"))
        if bg.shape != (STAR_H, STAR_W, 3):
            bg = None
    except Exception:
        bg = None
    if bg is None:
        bg = _star_compute(k / FPS)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(f"{p.stem}.{os.getpid()}.tmp")
            Image.fromarray(bg).save(tmp, "PNG", compress_level=3)
            os.replace(tmp, p)
        except OSError:
            pass                            # 寫不進去不影響結果,下次再算
    bg.setflags(write=False)
    _star_mem[k] = bg
    while len(_star_mem) > _STAR_MEM_MAX:
        _star_mem.popitem(last=False)
    return bg


def make_star_bg(t):
    """時間 t(秒,成片絕對時間)的星座背景,回傳 HxWx3 uint8(深色底 + 光點星座;唯讀,勿就地修改)。同一個 t 必得同一張圖。
    t 落在整數格上時走快取(格索引 mod STAR_N,與即時計算逐像素相同);非整數格維持即時計算。"""
    t = float(t)
    f = t * FPS
    if abs(f - round(f)) < 1e-6:
        return _star_cached(int(round(f)) % STAR_N)
    return _star_compute(t)


def over_star(fg, t):
    """straight-alpha RGBA ndarray(整張 HxWx4,bg='alpha' 產的動畫格)疊到 t 時刻的星座背景,回傳 HxWx3 uint8。
    只算 alpha > 0 的像素(其餘直接是背景),alpha = 255 的直接取前景;結果與全圖公式逐像素相同。"""
    bg = make_star_bg(t)
    if bg.shape[:2] != fg.shape[:2]:     # 直式原生畫面窗:裁背景中段(同高、置中)
        fh, fw = fg.shape[:2]
        y0, x0 = (STAR_H - fh) // 2, (STAR_W - fw) // 2
        bg = bg[y0:y0 + fh, x0:x0 + fw]
    a = fg[..., 3]
    out = bg.copy()
    idx = a > 0
    if idx.any():
        aa = a[idx].astype(np.uint16)[:, None]
        out[idx] = ((bg[idx].astype(np.uint16) * (255 - aa) + fg[..., :3][idx].astype(np.uint16) * aa + 127) // 255).astype(np.uint8)
    return out


def _over_star_ref(fg, t):
    """原本的全圖公式(供逐像素比對)。"""
    bg = _star_compute(t)
    a = fg[..., 3:4].astype(np.uint16)
    return ((bg.astype(np.uint16) * (255 - a) + fg[..., :3].astype(np.uint16) * a + 127) // 255).astype(np.uint8)


# ---------------------------------------------------------------- 直式原生畫面(F3-4,Shorts;規格 projects/framework/shorts_spec.md)
# 畫布 = 直式畫面窗 1080x1080(成片 y 260-1340);文字安全 x 80-940、y 40-1040(窗內座標)。原生支援 timeline / list / bars,
# 其餘型別由 build 退回橫式整張縮放並印警告。set_profile 只改 PORTRAIT_SET 列的模組常數;橫式值在 import 時記下,切回時原樣還原。
P_NATIVE = ("timeline", "list", "bars")
P_LAYOUT_VER = 4                 # 改直式版面時 +1(build 的直式動畫快取簽章)
P_X0, P_X1, P_Y0, P_Y1 = 80, 940, 40, 1040
P_TEXT_W = P_X1 - P_X0           # 860
P_FS_MIN = 48                    # 直式文字字級下限(px)
P_SIZES = []                     # 直式期間 text_sprite 用過的字級(量測用;set_profile 清空)
TLP_LINE_DX = 60                 # 直式時間軸:縱線在文字墨跡左緣左邊 60px(整組水平置中以文字墨跡外框計,縱線隨文字)
TLP_WRAP_W = 740                 # 年份 / 說明換行寬(墨跡寬上限)
TLP_TOP, TLP_BOTTOM = 70, 1010   # 內容上下界(有 src 時下界 960);整組文字墨跡在此範圍垂直置中(離窗上下緣 >= 60)
TLP_DESC_SIZES = (72, 68, 64, 60, 56, 52, 48)   # 節點少時用大字(上限 72 比照 list,下限 48),逐級降到列間距 >= TLP_ROW_GAP_MIN
TLP_YEAR_MAX = 72                # 年份字級 = min(說明 + 12, 72)
TLP_ROW_GAP_MIN = 24
TLP_GAP_MAX = 160                # 節點少時列間距放大的上限
LISTP_GAP = 48                   # 直式清單項目間距
LISTP_SIZES = (72, 68, 64, 60, 56, 52, 48)   # 項目少時用大字(上限 72,shorts_spec 未訂,主對話看圖後修正)
LISTP_X1 = 1020                 # 直式清單換行右界(窗內 x,離右緣 60)
WORD_TOKS = None                 # 直式換行斷詞:text -> 不可拆 token 清單(join = text);build import 時注入 jieba 版

PORTRAIT_SET = dict(W=1080, H=1080, CX=510.0, PORTRAIT=True, SAFE_H=1040,
                    SRC_FS=48, SRC_RIGHT=940, SRC_BOTTOM=1030,
                    BARS_LABEL_RIGHT=300, BARS_BASE_X=330, BARS_END_MAX=660, BARS_BOTTOM_MAX=960, BARS_BOTTOM_SRC=940,
                    BARS_TITLE_CY=110, BARS_UNIT_MIN=48, LIST_TITLE_CY=110, LIST_DOT_R=40, LIST_DOT_FS=52)
_LANDSCAPE_SET = {k: globals()[k] for k in PORTRAIT_SET}


def set_profile(name):
    """切換版面常數組:"landscape"(預設,1920x1080)/ "portrait"(直式畫面窗 1080x1080)。非執行緒安全:切換期間不可同時產橫式動畫。"""
    globals().update(PORTRAIT_SET if name == "portrait" else _LANDSCAPE_SET)
    _bars_tb.clear()
    P_SIZES.clear()


def _stack_lines(lines, size, fill=WHITE, pitch=None):
    """多行左對齊貼圖(各行 text_sprite 疊起來,行距 pitch)。"""
    pitch = pitch or round(size * 1.3)
    sps = [text_sprite(ln, size, fill, stroke=2) for ln in lines]
    img = Image.new("RGBA", (max(sp.width for sp in sps), pitch * (len(sps) - 1) + sps[-1].height), (0, 0, 0, 0))
    for i, sp in enumerate(sps):
        img.alpha_composite(sp, (0, i * pitch))
    return img


def _list_layout_p(items, note=None, src=None):
    """直式 list 版面:圓點靠左 x=80,文字自動換行(寬 <= 940 - 文字左緣),字級 64 起逐級降到 48;回傳鍵同 list_layout。"""
    items = [norm_text(x) for x in items]
    n = len(items)
    x_left = P_X0
    t_left = x_left + 2 * LIST_DOT_R + 28
    max_w = LISTP_X1 - t_left
    note_sp = note_b = None
    if note:
        nsz = _fit_size(norm_text(note), 52, P_TEXT_W, P_FS_MIN)
        note_sp = text_sprite(norm_text(note), nsz, (210, 210, 210), stroke=2)
        note_b = 960 if src else P_Y1 - 10
    lim = (note_b - (_ink(note_sp)[3] - _ink(note_sp)[1]) - 40) if note_sp is not None else (940 if src else P_Y1 - 30)
    top = LIST_TITLE_CY + 110
    for size in LISTP_SIZES:
        wraps = [_wrap_p(x, font(size), max_w) for x in items]
        pitch = round(size * 1.3)
        hs = [pitch * len(w) for w in wraps]
        if top + sum(hs) + LISTP_GAP * (n - 1) <= lim:
            break
    sps = [_stack_lines(w, size, pitch=pitch) for w in wraps]
    inks = [_ink(sp) for sp in sps]
    tx = [int(round(t_left - i[0])) for i in inks]
    sh = max(0, (lim - (top + sum(hs) + LISTP_GAP * (n - 1))) // 2)   # 項目少:標題 + 項目整組往下移到垂直置中
    ys, y = [], top + sh
    for h in hs:
        ys.append(y + h / 2)
        y += h + LISTP_GAP
    dot_x = x_left + LIST_DOT_R
    boxes = []
    for k in range(n):
        oy = int(round(ys[k] - sps[k].height // 2))
        boxes.append((int(round(x_left)), min(oy + inks[k][1], int(ys[k] - LIST_DOT_R)),
                      tx[k] + inks[k][2], max(oy + inks[k][3], int(ys[k] + LIST_DOT_R))))
    note_cy = note_box = None
    if note_sp is not None:
        l, t, r, b = _ink(note_sp)
        note_cy = note_b - b + note_sp.height / 2
        oy, ox = int(round(note_cy - note_sp.height / 2)), int(round(CX - note_sp.width / 2))
        note_box = (ox + l, oy + t, ox + r, oy + b)
    allb = boxes + ([note_box] if note_box else [])
    bounds = (min(b[0] for b in allb), min(b[1] for b in allb), max(b[2] for b in allb), max(b[3] for b in allb))
    return dict(items=items, size=size, sps=sps, ys=ys, tx=tx, dot_x=dot_x, boxes=boxes, note_sp=note_sp, note_cy=note_cy,
                note_box=note_box, bounds=bounds, bottom=bounds[3], title_cy=LIST_TITLE_CY + sh,
                note_overlap=bool(note_box and boxes and note_box[1] < boxes[-1][3] + 24))


def _wrap_p(text, f, max_w):
    """直式換行:換行點只落在詞與詞之間(WORD_TOKS:jieba 詞、英數詞與括號整段);有 token 比行寬還寬時退回預設 token。"""
    toks = WORD_TOKS(text) if WORD_TOKS else None
    if toks and ("".join(toks) != text or max(f.getlength(t) for t in toks) > max_w):
        toks = None
    return _wrap_even(text, f, max_w, toks=toks)


def timeline_layout_p(points, src=None):
    """直式 timeline 版面(縱向):縱線在文字左 60px,每個節點一列,年份在上、說明在下(皆靠左,說明自動換行)。
    說明字級 72 起逐級降到 48(年份 = min(說明 + 12, 72)),直到列間距 >= 24;節點少時列間距放大到 <= TLP_GAP_MAX。
    整組(最終版面,全部節點出現後)以文字墨跡外框水平置中於窗、垂直置中於 [TLP_TOP, 下界]。
    回傳 dict(ysz, dsz, ny 節點 y, rows=[(年份 top, 說明 top)], descs, bottom, tx 文字墨跡左緣, lx 縱線 x, ink 墨跡外框)。"""
    pts = [(norm_text(p[0]), norm_text(p[1])) for p in points]
    n = len(pts)
    bot = 960 if src else TLP_BOTTOM
    for dsz in TLP_DESC_SIZES:
        ysz, pitch = min(dsz + 12, TLP_YEAR_MAX), round(dsz * 1.3)
        yh = round(ysz * 1.25)
        wraps = [_wrap_p(p[1], font(dsz), TLP_WRAP_W) for p in pts]
        hs = [yh + pitch * len(w) for w in wraps]
        gap = (bot - TLP_TOP - sum(hs)) / max(1, n - 1)
        if gap >= TLP_ROW_GAP_MIN:
            break
    gap = min(gap, TLP_GAP_MAX) if n > 1 else 0
    y = float(TLP_TOP)
    rows, ny = [], []
    for h in hs:
        rows.append((y, y + yh))
        ny.append(y + yh / 2)
        y += h + gap
    descs = [_stack_lines(w, dsz, pitch=pitch) for w in wraps]
    ysps = [text_sprite(p[0], ysz, PAL_TEXT, stroke=2) for p in pts]
    yink, dink = [_ink(sp) for sp in ysps], [_ink(sp) for sp in descs]
    # 墨跡外框(以首列年份上緣、末列說明下緣、最寬一行;x 以墨跡左緣 = 0 計寬)
    top = ny[0] - ysps[0].height / 2 + yink[0][1]
    btm = rows[-1][1] + dink[-1][3]
    ink_w = max([i[2] - i[0] for i in yink] + [i[2] - i[0] for i in dink])
    dy = (TLP_TOP + bot) / 2 - (top + btm) / 2
    rows = [(a + dy, b + dy) for a, b in rows]
    ny = [v + dy for v in ny]
    tx = int(round((W - ink_w) / 2))
    ink = (tx, int(round(top + dy)), tx + ink_w, int(round(btm + dy)))
    return dict(pts=pts, ysz=ysz, dsz=dsz, yh=yh, ny=ny, rows=rows, descs=descs, bottom=btm + dy, tx=tx, lx=tx - TLP_LINE_DX, ink=ink)


def _left_at(img, sp, x_ink, cy, a):
    """墨跡左緣對齊 x_ink、垂直置中 cy 貼上(a = 不透明度)。"""
    _blit_xy(img, scale_alpha(sp, a), int(round(x_ink - _ink(sp)[0])), int(round(cy - sp.height / 2)))


def _make_timeline_p(points, question_between=None, bg="alpha", seg_seconds=1.2, q_seconds=2.0, src=None):
    """直式 timeline(make_timeline 在 PORTRAIT 時轉呼叫;回傳格式與動畫時序同橫式:線長到節點 -> 節點彈出 -> 年份 -> 說明)。"""
    n = len(points)
    lay = timeline_layout_p(points, src)
    pts, ny, rows, descs = lay["pts"], lay["ny"], lay["rows"], lay["descs"]
    y_start = ny[0]                  # 軸線從第一個節點開始(不留線頭)
    tx, lx = lay["tx"], lay["lx"]
    cache = {}

    def year_at(i, col):
        k = ("y", i, col)
        if k not in cache:
            cache[k] = text_sprite(pts[i][0], lay["ysz"], col, stroke=2)
        return cache[k]

    def node_at(col):
        k = ("n", col)
        if k not in cache:
            cache[k] = _circle_sprite(24, col, ring=col)
        return cache[k]

    base = _dark_bg() if bg == "dark" else Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def render(line_end, node_p, year_p, desc_p, cols, q=None, src_p=1.0):
        img = base.copy()
        d = ImageDraw.Draw(img)
        _src_note(img, src, src_p)
        if line_end is not None and line_end > y_start:
            d.rectangle([lx - 7, y_start, lx + 7, line_end], fill=(0, 0, 0, 170))
            d.rectangle([lx - 4, y_start, lx + 4, line_end], fill=(235, 235, 235, 255))
        for i in range(n):
            if node_p[i] > 0:
                s = ease_out_back(node_p[i]) if node_p[i] < 1 else 1.0
                nsp = node_at(cols[i])
                img = paste_center(img, resize_rgba(nsp, (nsp.width * max(s, 0.02),) * 2), lx, ny[i])
            if year_p[i] > 0:
                e = ease_out_cubic(year_p[i])
                _left_at(img, year_at(i, cols[i]), tx + (1 - e) * 22, ny[i], e)
            if desc_p[i] > 0:
                e = ease_out_cubic(desc_p[i])
                _left_at(img, descs[i], tx + (1 - e) * 22, rows[i][1] + descs[i].height / 2, e)
        if q is not None:
            img = q(img)
        return to_np(img)

    def colors(k, t):
        cs = [PAL_TEXT] * n
        if 0 <= k < n:
            cs[k] = PAL_ACCENT
        if 1 <= k <= n:
            cs[k - 1] = _mix(PAL_ACCENT, PAL_TEXT, t / 0.3)
        return cs

    segs, fn = [], int(round(seg_seconds * FPS))
    prev_end = y_start
    for k in range(n):
        frames = []
        for f in range(fn):
            t = f / FPS
            le = lerp(prev_end, ny[k], ease_in_out_cubic(t / 0.5))
            node_p = [1.0] * k + [clamp((t - 0.42) / 0.3)] + [0.0] * (n - k - 1)
            year_p = [1.0] * k + [clamp((t - 0.5) / 0.3)] + [0.0] * (n - k - 1)
            desc_p = [1.0] * k + [clamp((t - 0.65) / 0.35)] + [0.0] * (n - k - 1)
            frames.append(render(le, node_p, year_p, desc_p, colors(k, t), src_p=clamp(t / 0.4) if k == 0 else 1.0))
        segs.append({"name": f"seg{k}", "frames": frames, "hold": True, "loop": False})
        prev_end = ny[k]
    if question_between:
        i, j = question_between
        qy = (ny[i] + ny[j]) / 2
        qsp = text_sprite("?", 160, PAL_NEG, stroke=8)
        ones = [1.0] * n
        frames = []
        for f in range(int(round(q_seconds * FPS))):
            t = f / FPS

            def q(img, t=t):
                if t < 0.4:
                    s, dx = ease_out_back(t / 0.4), 0.0
                else:
                    ph = ((t - 0.4) % 0.8) / 0.8
                    dx = abs(math.sin(math.pi * ph)) * 24
                    s = 1.0 + 0.07 * math.sin(2 * math.pi * ph)
                sp = resize_rgba(qsp, (qsp.width * max(s, 0.02), qsp.height * max(s, 0.02)))
                return paste_center(img, sp, P_X1 - 90 + dx, qy)
            frames.append(render(ny[-1], ones, ones, ones, [PAL_TEXT] * n, q))
        segs.append({"name": "q", "frames": frames, "hold": False, "loop": True})
    return segs
