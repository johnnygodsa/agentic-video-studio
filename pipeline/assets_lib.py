"""畫面素材共用工具:長截圖 -> 固定構圖 1920x1080 並中文化(只用 Pillow)。

座標一律用「顯示座標」(Read 看到的 1200 寬縮圖座標,x1.6 = 原圖像素)。
"""
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import paths as P

MEDIA = P.ROOT
IMG = P.IMAGES
FONT_B = str(P.FONT_BOLD)   # 2026-10-22 起 Noto Sans TC(新 spec 的標籤/合成圖字);舊片 Page 版面仍用下面的微軟正黑體
FONT_R = str(P.FONT_REG)
FONT_B_LEGACY = r"C:\Windows\Fonts\msjhbd.ttc"
FONT_R_LEGACY = r"C:\Windows\Fonts\msjh.ttc"
K = 1.6
FW, FH = 1920, 1080
_fc = {}


def font(size, bold=False, legacy=False):
    key = (round(size), bold, legacy)
    if key not in _fc:
        path = (FONT_B_LEGACY if bold else FONT_R_LEGACY) if legacy else (FONT_B if bold else FONT_R)
        _fc[key] = ImageFont.truetype(path, round(size))
    return _fc[key]


_TOK = re.compile(r"[A-Za-z0-9][A-Za-z0-9.:'’\-/%+@_|]*|—+|.", re.S)
_NOSTART = set("，。、；：！？）」』》,.;:!?)%—")
_NOEND = set("（「『《(")


def wrap(draw, text, fnt, width):
    lines = []
    for para in text.split("\n"):
        cur, curw = "", 0
        for tok in _TOK.findall(para):
            w = draw.textlength(tok, font=fnt)
            if cur and curw + w > width and tok[0] not in _NOSTART:
                if cur[-1] in _NOEND and len(cur) > 1:
                    lines.append(cur[:-1])
                    cur, curw = cur[-1], draw.textlength(cur[-1], font=fnt)
                else:
                    lines.append(cur)
                    cur, curw = "", 0
                if tok == " ":
                    continue
            cur += tok
            curw += w
        lines.append(cur)
    return lines


class Page:
    def __init__(self, src, x0, x1, bg, name, pad=0, s_max=1.6):
        self.src = Image.open(IMG / f"{src}.png").convert("RGB")
        self.x0, self.x1 = round(x0 * K), round(x1 * K)
        self.bg = bg
        self.name = name
        self.pad = pad
        self.s_max = s_max
        self.strips = []  # (y0_orig, y1_orig, dest_y)
        self.h = 0
        self.canvas = None
        self.texts = []
        self.flows = []
        self.marks = []  # 手動標記 (文字, 顯示座標框):供 hl 紅框定位(畫布上非 Page 繪製的原圖文字)
        self.runs = []   # 渲染時記錄的文字行 {"text","box","chars"}(輸出 1920x1080 像素)
        self.w = self.x1 - self.x0

    def strip(self, y0, y1, gap=0, x0=None, x1=None):
        y0, y1 = round(y0 * K), round(y1 * K)
        self.h += gap
        self.strips.append((y0, y1, self.h))
        self.h += y1 - y0

    def _build(self):
        if self.canvas is not None:
            return
        self.canvas = Image.new("RGB", (self.w, self.h), self.bg)
        for y0, y1, dy in self.strips:
            self.canvas.paste(self.src.crop((self.x0, y0, self.x1, y1)), (0, dy))

    def cb(self, x0, y0, x1, y1):
        """顯示座標 -> 畫布像素框"""
        oy0, oy1 = round(y0 * K), round(y1 * K)
        for s0, s1, dy in self.strips:
            if s0 <= oy0 < s1:
                return (round(x0 * K) - self.x0, oy0 - s0 + dy,
                        round(x1 * K) - self.x0, min(oy1, s1) - s0 + dy)
        raise ValueError(f"y {y0} 不在任何 strip 內")

    def cbs(self, x0, y0, x1, y1):
        """同 cb,但框跨多個 strip 時逐段回傳(落在 strip 外的部分略過)"""
        oy0, oy1 = round(y0 * K), round(y1 * K)
        for s0, s1, dy in self.strips:
            a, b = max(oy0, s0), min(oy1, s1)
            if a < b:
                yield (round(x0 * K) - self.x0, a - s0 + dy, round(x1 * K) - self.x0, b - s0 + dy)

    def fill(self, x0, y0, x1, y1, color):
        self._build()
        d = ImageDraw.Draw(self.canvas)
        for b in self.cbs(x0, y0, x1, y1):
            d.rectangle(b, fill=color)

    def smear(self, x0, y0, x1, y1):
        """以框左右兩側像素橫向漸層填滿(適合平滑底色)"""
        self._build()
        X0, Y0, X1, Y1 = self.cb(x0, y0, x1, y1)
        w, h = X1 - X0, Y1 - Y0
        c = self.canvas
        left = c.crop((max(X0 - 3, 0), Y0, max(X0 - 2, 1), Y1)).resize((w, h))
        right = c.crop((min(X1 + 2, c.width - 2), Y0, min(X1 + 3, c.width - 1), Y1)).resize((w, h))
        mask = Image.linear_gradient("L").rotate(90).resize((w, h))  # 左白 -> 右黑
        c.paste(Image.composite(left, right, mask), (X0, Y0))

    def fitfill(self, box, refs):
        """以 refs(顯示座標框,需為乾淨背景)的像素擬合二次曲面,填滿 box(適合斜向漸層底色)"""
        import numpy as np
        self._build()
        c = np.asarray(self.canvas, dtype=float)
        xs, ys, cols = [], [], []
        for r in refs:
            for X0, Y0, X1, Y1 in self.cbs(*r):
                yy, xx = np.mgrid[Y0:Y1:2, X0:X1:2]
                xs.append(xx.ravel())
                ys.append(yy.ravel())
                cols.append(c[yy.ravel(), xx.ravel()])
        xs, ys, cols = np.concatenate(xs), np.concatenate(ys), np.concatenate(cols)

        def basis(x, y):
            x, y = x / self.w, y / self.h
            return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], 1)

        coef = np.linalg.lstsq(basis(xs, ys), cols, rcond=None)[0]
        for X0, Y0, X1, Y1 in self.cbs(*box):
            yy, xx = np.mgrid[Y0:Y1, X0:X1].astype(float)
            out = (basis(xx.ravel(), yy.ravel()) @ coef).clip(0, 255).reshape(Y1 - Y0, X1 - X0, 3)
            self.canvas.paste(Image.fromarray(out.astype("uint8")), (X0, Y0))

    def shade(self, x0, y0, x1, y1, color=(14, 14, 14), solid_from=0.3):
        """框內由上往下漸暗至 color(蓋在圖片上方放標題用)"""
        self._build()
        X0, Y0, X1, Y1 = self.cb(x0, y0, x1, y1)
        w, h = X1 - X0, Y1 - Y0
        grad = Image.linear_gradient("L").resize((w, h))
        a = grad.point(lambda v: min(255, int(v / (255 * solid_from) * 255)))
        self.canvas.paste(Image.new("RGB", (w, h), color), (X0, Y0), a)

    def text(self, box, txt, size, color, bold=False, line=1.5, align="l", pad=0):
        """box: 顯示座標 (x0,y0,x1,y1);size: 畫布像素(渲染時乘縮放)"""
        self.texts.append((self.cb(*box), txt, size, color, bold, line, align))

    def mark(self, txt, box):
        """登記一個 hl 可定位的區塊(顯示座標框),例如保留原樣的英文名稱"""
        self.marks.append((txt, self.cb(*box)))

    def _rec(self, d, ln, f, x, y):
        """記錄一行文字的逐字水平範圍與墨水垂直範圍"""
        _, t, _, b = d.textbbox((x, y), ln, font=f)
        xs = [x + d.textlength(ln[:i], font=f) for i in range(len(ln) + 1)]
        self.runs.append(dict(text=ln, box=[round(xs[0]), round(t), round(xs[-1]), round(b)],
                              chars=[[round(xs[i]), round(xs[i + 1])] for i in range(len(ln))]))

    def px(self, x, y):
        return self.src.getpixel((round(x * K), round(y * K)))

    def flow(self, box, items, gap=14):
        """box 內由上往下依序排版多段文字;items=[(txt,size,color,bold,line)]"""
        self.flows.append((self.cb(*box), items, gap))

    def render(self, label, out=None):
        self._build()
        s = min(FW / self.w, (FH - self.pad) / self.h, self.s_max)
        cw, ch = round(self.w * s), round(self.h * s)
        big = self.canvas.resize((cw, ch), Image.LANCZOS)
        out_img = Image.new("RGB", (FW, FH), self.bg)
        ox, oy = (FW - cw) // 2, (FH - ch) // 2
        out_img.paste(big, (ox, oy))
        d = ImageDraw.Draw(out_img)
        for (X0, Y0, X1, Y1), txt, size, color, bold, line, align in self.texts:
            f = font(size * s, bold, legacy=True)
            x0, y0, x1 = ox + X0 * s, oy + Y0 * s, ox + X1 * s
            lines = wrap(d, txt, f, x1 - x0)
            lh = size * s * line
            for i, ln in enumerate(lines):
                if align == "c":
                    x = x0 + (x1 - x0 - d.textlength(ln, font=f)) / 2
                elif align == "r":
                    x = x1 - d.textlength(ln, font=f)
                else:
                    x = x0
                d.text((x, y0 + i * lh), ln, font=f, fill=color)
                self._rec(d, ln, f, x, y0 + i * lh)
        for (X0, Y0, X1, Y1), items, gap in self.flows:
            x0, y, x1 = ox + X0 * s, oy + Y0 * s, ox + X1 * s
            for txt, size, color, bold, line in items:
                f = font(size * s, bold, legacy=True)
                for ln in wrap(d, txt, f, x1 - x0):
                    d.text((x0, y), ln, font=f, fill=color)
                    self._rec(d, ln, f, x0, y)
                    y += size * s * line
                y += gap * s
        add_label(out_img, label)
        out = out or IMG / f"zh_{self.name}.png"
        out_img.save(out)
        for txt, (X0, Y0, X1, Y1) in self.marks:
            self.runs.append(dict(text=txt, box=[round(ox + X0 * s), round(oy + Y0 * s),
                                                 round(ox + X1 * s), round(oy + Y1 * s)]))
        save_boxes(out, self.runs)
        return out_img


OCR_ENGINES = ("win", "rapid")
_rapid = None
_warned = set()


def _warn_once(key, msg):
    if key not in _warned:
        _warned.add(key)
        print(f"[assets_lib.ocr] 警告:{msg}", file=sys.stderr)


def _default_engine():
    """預設引擎:Windows 用 win(Windows OCR 有 zh-Hant-TW 語言包,繁中字形正確);其他平台用 rapid。
    RapidOCR 內建模型是簡體為主,等本機比較表(ocr_compare.py)出來再決定 Windows 是否改預設 rapid(T4)。"""
    return "win" if os.name == "nt" else "rapid"


def ocr_engine():
    """目前使用的 OCR 引擎:環境變數 OCR_ENGINE=win|rapid 可覆蓋,沒設用 _default_engine();
    rapid 但 rapidocr_onnxruntime 沒裝時自動退回 win 並警告一次(T4)。"""
    eng = (os.environ.get("OCR_ENGINE") or _default_engine()).strip().lower()
    if eng not in OCR_ENGINES:
        raise ValueError(f"OCR_ENGINE 只接受 {'|'.join(OCR_ENGINES)},收到 {eng!r}")
    if eng == "rapid":
        try:
            import rapidocr_onnxruntime  # noqa: F401
        except ImportError:
            _warn_once("fallback", "rapidocr_onnxruntime 未安裝,退回 Windows OCR(pip install rapidocr-onnxruntime)")
            return "win"
    return eng


def _rapid_engine():
    """RapidOCR 單例。OCR_RAPID_REC=<繁體(或其他)辨識模型 .onnx> 可換掉內建的簡體為主辨識模型;
    該 .onnx 沒有內嵌字元表(metadata 'character')時,另用 OCR_RAPID_KEYS=<字典 txt,一行一字,如 PaddleOCR 的 chinese_cht_dict.txt>。
    rapidocr-onnxruntime 1.2.x 的 rec_keys_path 參數不會傳到辨識器(只認 config 的 keys_path),所以這裡建好引擎後替換 text_recognizer。"""
    global _rapid
    if _rapid is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapid = RapidOCR()
        rec = (os.environ.get("OCR_RAPID_REC") or "").strip()
        if rec:
            if not Path(rec).is_file():
                raise FileNotFoundError(f"OCR_RAPID_REC 找不到模型檔:{rec}")
            keys = (os.environ.get("OCR_RAPID_KEYS") or "").strip()
            if keys and not Path(keys).is_file():
                raise FileNotFoundError(f"OCR_RAPID_KEYS 找不到字典檔:{keys}")
            import rapidocr_onnxruntime as _ro
            from rapidocr_onnxruntime import utils as _ru
            root = Path(_ro.__file__).resolve().parent
            try:                                    # 1.4.x:rec 模組 ch_ppocr_rec、config 用 update_model_path / rec_keys_path
                from rapidocr_onnxruntime.ch_ppocr_rec import TextRecognizer
                cfg = _ru.update_model_path(_ru.read_yaml(str(root / "config.yaml")))["Rec"]
                keys_key, attr = "rec_keys_path", "text_rec"
            except ImportError:                     # 1.2.x:ch_ppocr_v3_rec、concat_model_path / keys_path
                from rapidocr_onnxruntime.ch_ppocr_v3_rec import TextRecognizer
                cfg = _ru.concat_model_path(_ru.read_yaml(str(root / "config.yaml")))["Rec"]
                keys_key, attr = "keys_path", "text_recognizer"
            cfg["model_path"] = rec
            if keys:
                cfg[keys_key] = keys
            setattr(_rapid, attr, TextRecognizer(cfg))
    return _rapid


_s2t = None
S2T_KEEP = "台"      # 台灣用字:OpenCC 會把「台」轉成「臺」,台灣慣用「台」,一律保留


def _s2t_convert(text):
    """簡體 -> 繁體(OpenCC s2tw,只轉字形,用語不轉)。OCR_S2T=0 關閉;opencc 沒裝時警告一次並原樣回傳。
    只改「原字本身是簡體字」的位置:OpenCC 以詞為單位轉時會連繁體輸入也改(宣布 -> 宣佈、台 -> 臺),
    所以用逐字轉換(c(o)==o 代表 o 不是簡體字)把繁體輸入還原,保留台灣用字。已知限制:「里」固定轉「裡」(鄰里 會變 鄰裡)。"""
    global _s2t
    if (os.environ.get("OCR_S2T") or "1").strip().lower() in ("0", "false", "no", "off"):
        return text
    if _s2t is None:
        try:
            import opencc
            _s2t = opencc.OpenCC("s2tw").convert
        except Exception:      # noqa: BLE001  ImportError、設定檔缺失都算沒有
            _warn_once("s2t", "opencc 未安裝,RapidOCR 輸出不做簡轉繁(pip install opencc-python-reimplemented,或 OCR_S2T=0 關閉此警告)")
            _s2t = False
    if not _s2t:
        return text
    conv = _s2t(text)
    if len(conv) != len(text):
        return conv
    return "".join(o if (q != o and (o in S2T_KEEP or _s2t(o) == o)) else q for o, q in zip(text, conv))


def _split_words(text, x, y, w, h):
    """把一行的框 (x,y,w,h) 依字元寬度估算切成詞框 [{t,x,y,w,h}]。
    RapidOCR(rapidocr-onnxruntime 1.2.x)只給行框、沒有詞/字框,所以用等分估算:
    連續英數視為一個詞,其他非空白字元(中日文、標點)各算一個詞;寬度權重 全形字=2、半形字=1,依權重比例分配行寬。
    與 Windows OCR 的詞框相比只是近似(目前 repo 內沒有程式使用 words 的座標,只有 ocr_batch 取行文字)。"""
    ms = list(re.finditer(r"[0-9A-Za-z]+|\S", text))
    if not ms:
        return []
    wt = [sum(1 if ord(c) < 0x2E80 else 2 for c in m.group()) for m in ms]
    gap = [1 if i and ms[i].start() > ms[i - 1].end() else 0 for i in range(len(ms))]   # 詞間原文有空白 -> 補 1 個半形寬
    total = sum(wt) + sum(gap)
    words, cx = [], float(x)
    for m, k, g in zip(ms, wt, gap):
        cx += w * g / total
        ww = w * k / total
        words.append(dict(t=m.group(), x=int(round(cx)), y=int(y), w=int(round(ww)), h=int(h)))
        cx += ww
    return words


def _rapid_to_lines(result):
    """RapidOCR 輸出 [[四角點, 文字, 信心], …](或 None)-> [{"text","words":[{t,x,y,w,h}]}],與 ocr_win.ps1 同格式"""
    lines = []
    for item in result or []:
        box, text = item[0], _s2t_convert(str(item[1]).strip())
        if not text:
            continue
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        x0, y0 = min(xs), min(ys)
        lines.append(dict(text=text, words=_split_words(text, int(x0), int(y0), int(max(xs) - x0), int(max(ys) - y0))))
    return lines


def ocr(path, lang="en-US"):
    """OCR,回傳 [{"text","words":[{t,x,y,w,h}]}]。引擎由 OCR_ENGINE=win|rapid 決定(預設:Windows=win,其他=rapid;rapid 沒裝則退回 win)。
    win:Windows 內建 OCR(ocr_win.ps1,lang 有作用);rapid:RapidOCR(中英混合模型,lang 忽略;輸出預設簡轉繁,OCR_S2T=0 關;
    OCR_RAPID_REC / OCR_RAPID_KEYS 可換繁體辨識模型,見 _rapid_engine)。"""
    if ocr_engine() == "rapid":
        res, _ = _rapid_engine()(str(path))
        return _rapid_to_lines(res)
    import subprocess
    import tempfile
    fd, name = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    out = Path(name)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(Path(__file__).with_name("ocr_win.ps1")), str(path), lang, str(out)], check=True)
    data = json.loads(out.read_text(encoding="utf-8-sig"))
    out.unlink()
    return data


def ocr_batch(folder):
    """資料夾內所有 *.jpg 做 OCR,回傳 {檔名: 全文(行以換行相接)}(clip_scan / gd_crowd_scan 用,輸出同舊 ocr_batch.ps1)。
    rapid:逐張呼叫 ocr();win:呼叫 ocr_batch.ps1(en-US,一次行程處理整個資料夾,比逐張起 PowerShell 快)。"""
    folder = Path(folder)
    if ocr_engine() == "rapid":
        return {f.name: "\n".join(ln["text"] for ln in ocr(f)) for f in sorted(folder.glob("*.jpg"))}
    import subprocess
    import tempfile
    fd, name = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    out = Path(name)
    subprocess.run(["powershell", "-NoProfile", "-File", str(Path(__file__).with_name("ocr_batch.ps1")),
                    str(folder), str(out)], check=True)
    data = json.loads(out.read_text(encoding="utf-8-sig"))
    out.unlink()
    return data


def save_boxes(png, runs):
    """文字區塊座標 sidecar(images/<name>.boxes.json),build.py 的 hl 紅框用"""
    Path(png).with_suffix(".boxes.json").write_text(json.dumps(runs, ensure_ascii=False), encoding="utf-8")


def add_label(img, site, size=22):
    """右下角來源標籤「中文翻譯 · 原文:site」(site 以 = 開頭才原樣顯示,翻譯過的網頁截圖不可用);回傳標籤外框"""
    d = ImageDraw.Draw(img)
    f = font(size, True)
    t = site[1:] if site.startswith("=") else f"中文翻譯 · 原文:{site}"
    w = d.textlength(t, font=f)
    x1, y1 = img.width - 16, img.height - 14
    d.rounded_rectangle((x1 - w - 22, y1 - size - 14, x1, y1), 8, fill=(0, 0, 0))
    d.text((x1 - w - 11, y1 - size - 9), t, font=f, fill=(255, 255, 255))
    return (int(x1 - w - 22), y1 - size - 14, x1, y1)


def ink_check(img, runs, skip=(), edge=40, top=24, tol=8, thr=45):
    """看 PNG 像素驗文字框(不是只信 .boxes.json)。背景 = 每個框所在列的局部中位數色,非純色底、含圖片的頁面也能用。
    回傳 dict(left/right/top = 文字墨跡離邊最小值, off = 框與墨跡的系統偏移(左, 右;中位數), over = 墨跡超出框的最大值, errs)。
    錯誤:離左右 < edge、離上 < top、框內無墨跡、首/尾字缺墨、框外左右 40px 內有像文字的墨跡(框漏字或錯位)、系統偏移 > tol。
    skip = 不檢查的矩形(來源標籤)"""
    import numpy as np
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    H, W = a.shape[:2]
    dead = np.zeros((H, W), bool)
    for x0, y0, x1, y1 in skip:
        dead[max(0, y0 - 2):y1 + 2, max(0, x0 - 2):x1 + 2] = True
    cover = np.zeros((H, W), bool)   # 所有文字框(相鄰的框不算「框外墨跡」)
    for r in runs:
        x0, y0, x1, y1 = r["box"]
        cover[max(0, y0):max(0, y1), max(0, x0 - 3):max(0, x1 + 3)] = True

    def spans(mask, gap):
        idx = np.flatnonzero(mask)
        if not len(idx):
            return []
        cut = np.flatnonzero(np.diff(idx) > gap + 1)
        return list(zip(np.r_[idx[0], idx[cut + 1]].tolist(), np.r_[idx[cut], idx[-1]].tolist()))

    def raw(ya, yb, xa, xb, ra, rb):
        """(墨跡遮罩, 與背景的色差);背景 = 這幾列在欄 [ra, rb) 的中位數色(逐列取會被粗體大標的橫筆畫翻轉)"""
        d = a[ya:yb, xa:xb] - np.median(a[ya:yb, ra:rb].reshape(-1, 3), axis=0)
        return (np.abs(d).max(axis=2) > thr) & ~dead[ya:yb, xa:xb], d

    def textlike(ink, d):
        """像文字的墨跡欄:排除太窄(邊線)、太矮(項目符號、底線)、圖片或色塊(幾乎填滿,或顏色不在同一條「底色 -> 字色」線上)"""
        keep = np.zeros(ink.shape[1], bool)
        for s, e in spans(ink.sum(axis=0) >= 2, 6):
            seg = ink[:, s:e + 1]
            rows = np.flatnonzero(seg.any(axis=1))
            if e - s + 1 < 6 or rows[-1] - rows[0] + 1 < 0.35 * ink.shape[0]:
                continue
            if e - s + 1 >= 14:
                v = d[:, s:e + 1][seg].astype(float)
                u = v.mean(axis=0)
                u /= np.linalg.norm(u) or 1
                if seg[rows[0]:rows[-1] + 1].mean() > 0.72 or np.percentile(np.linalg.norm(v - np.outer(v @ u, u), axis=1), 75) > 40:
                    continue
            keep[s:e + 1] = True
        return keep

    errs, left, right, topm, over, offl, offr = [], W, W, H, 0, [], []
    for r in runs:
        t = r["text"]
        x0, y0, x1, y1 = r["box"]
        x0, x1, y0, y1 = max(0, x0), min(W, x1), max(0, y0), min(H, y1)
        m = round((y1 - y0) * 0.12)
        ya, yb = y0 + m, y1 - m
        if not t.strip() or yb - ya < 6 or x1 - x0 < 2:
            continue
        tag = t.strip()[:10]
        xa, xb = max(0, x0 - 40), min(W, x1 + 40)
        ink, d = raw(ya, yb, xa, xb, xa, xb)
        ins = np.flatnonzero(ink[:, x0 - xa:x1 - xa].sum(axis=0) >= 2) + x0
        if not len(ins):
            errs.append(f"框內無墨跡:{tag}")
            continue
        left, right = min(left, ins[0]), min(right, W - 1 - ins[-1])
        fr = np.flatnonzero(raw(y0, y1, x0, x1, xa, xb)[0].sum(axis=1) >= 2)
        if len(fr):
            topm = min(topm, y0 + fr[0])
        ch = r.get("chars") or []
        vis = [i for i, c in enumerate(t) if not c.isspace()] if len(ch) == len(t) else []
        if vis:
            for i, lab in ((vis[0], "首"), (vis[-1], "尾")):
                if not ((ins >= ch[i][0] - 2) & (ins <= ch[i][1] + 2)).any():
                    errs.append(f"{lab}字缺墨:{tag}")
            if vis[0] == 0 and "一" <= t[0] <= "鿿":
                offl.append(ins[0] - x0)
            if vis[-1] == len(t) - 1 and "一" <= t[-1] <= "鿿":
                offr.append(x1 - 1 - ins[-1])
        out = ink.copy()   # 框外:扣掉自己(含容許誤差)與其他框
        out[:, cover[ya:yb, xa:xb].any(axis=0)] = False
        out[:, max(0, x0 - tol - xa):x1 + tol - xa] = False
        oc = np.flatnonzero(textlike(out, d)) + xa
        if len(oc):
            ol, orr = max(0, x0 - oc[0]), max(0, oc[-1] + 1 - x1)
            over = max(over, ol, orr)
            left, right = min(left, oc[0]), min(right, W - 1 - oc[-1])
            errs.append(f"框外有字(左{ol}/右{orr}):{tag}")
        for xs, xe, ra, rb in ((0, edge, 0, min(W, 160)), (W - edge, W, max(0, W - 160), W)):   # 畫面左右邊緣帶
            ec = np.flatnonzero(textlike(*raw(ya, yb, xs, xe, ra, rb))) + xs
            if len(ec):
                left, right = (min(left, ec[0]), right) if xs == 0 else (left, min(right, W - 1 - ec[-1]))
    ml, mr = (float(np.median(v)) if len(v) >= 3 else 0.0 for v in (offl, offr))
    if left < edge:
        errs.append(f"文字離左邊 {left} < {edge}")
    if right < edge:
        errs.append(f"文字離右邊 {right} < {edge}")
    if topm < top:
        errs.append(f"文字離上邊 {topm} < {top}")
    if abs(ml) > tol or abs(mr) > tol:
        errs.append(f"框與墨跡系統偏移 左{ml:+.0f}/右{mr:+.0f} > {tol}")
    return dict(left=int(left), right=int(right), top=int(topm), off=(ml, mr), over=int(over), errs=errs)


PAGES = {}


def page(fn):
    PAGES[fn.__name__] = fn
    return fn


def entry(name, site, title_en, title_zh, notes=""):
    return dict(name=f"zh_{name}.png", site=site, title_en=title_en, title_zh=title_zh, notes=notes)
