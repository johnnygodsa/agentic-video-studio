"""動態小件(kit;計畫 PLAN_動態小件與圖表 §3):欄位檢查、目標定位換算、渲染工作(交給 anim_web 逐格 seek)。

script 句子行尾 `kit:[{type, at:{text|box|el}, t0?, …}]`;t0 = 相對句子起點秒數(預設 T0)。
- 圖片 / 引言 / 對比鏡頭:有 at.text / at.box 的小件畫在「畫布座標」的跟隨圖層,與底圖套同一組 fx 濾鏡(zoom/drift/tilt);
  其餘(影片片段、動畫鏡頭、沒有 at 的 lower/pop/progress/badge)畫在成片座標的固定圖層。
- punch 不產圖層:build 對整個鏡頭畫面做 1.0 -> PUNCH_SCALE 再回來的縮放。
純函式(find_text_rect、to_canvas、pct_rect、map_rect、各檢查)不碰瀏覽器,tests/test_kit.py 測。
"""
import hashlib
import json
import math
from pathlib import Path

import paths as P

VERSION = 2            # 改本檔的資料轉換時 +1(kit.html、tokens、gsap 內容已在快取鍵內)
TPL = Path(__file__).with_name("templates") / "kit" / "kit.html"
T0 = 0.3               # 預設:句子開始後 0.3 秒出現
LINE_MAX, SHOT_MAX, PUNCH_PER_LINE = 2, 4, 1      # 節制規則(§3 / §9.2)
PUNCH_S, PUNCH_SCALE = 0.25, 1.06
# 小件 -> 必要欄位;DUR = 進場動態長度(秒,渲染格數由最晚結束的小件決定)
REQUIRED = {"callout": ("at",), "arrow": ("at",), "zoom": ("at",), "spotlight": ("at",), "pop": ("text",),
            "badge": ("text",), "lower": ("text",), "tick": ("at",), "cross": ("at",), "progress": ("value",), "punch": ()}
DUR = {"callout": 0.5, "arrow": 0.5, "zoom": 0.45, "spotlight": 0.3, "pop": 0.45, "badge": 0.8, "lower": 0.6,
       "tick": 0.3, "cross": 0.3, "progress": 0.9, "punch": PUNCH_S}
AT_KEYS = ("text", "box", "el")
# 擺放(自由擺放的小件不可蓋到文字與圖表元素;2026-10-22):與障礙物的最小間距(px)
MARGIN = 24            # pop
BADGE_MARGIN = 8
LOWER_MARGIN = 16
ARROW_CLEAR = 12       # 箭身中心線離障礙物(線寬 10 的半寬 5 + 餘裕 7)
HEAD_CLEAR = 3
TIP_GAP = 8            # 箭頭尖端離目標框
ARROW_FAR = (140, 180, 220, 250, 120)    # 箭尾離目標框的距離候選(規格 120-260px)
ARROW_DIRS = ((0.8, -0.6), (-0.8, -0.6), (0.8, 0.6), (-0.8, 0.6),          # 優先右上、左上、右下、左下
              (0, -1), (0, 1), (0.5, -0.87), (-0.5, -0.87), (0.5, 0.87), (-0.5, 0.87),
              (0.95, -0.31), (-0.95, -0.31), (0.95, 0.31), (-0.95, 0.31), (1, 0), (-1, 0))
WOBBLE_PX, WOBBLE_S = 3, 2.4           # 箭尾浮動 +-3px、週期 2.4 秒(>= 2 秒,§9 輕微浮動)
POP_SCALES = (1.0, 0.85, 0.72, 0.6)    # pop 字級最多縮小 3 級
PORTRAIT_VIS = (80, 40, 940, 1040)     # 直式畫面窗 1080x1080 的可放區 = 文字安全框(build.P_SAFE;字幕在窗外,不留字幕帶)
LOWER_SCALES = (1.0, 0.8)              # lower 縮小一級


# ---------------------------------------------------------------- 檢查(script_lint 與 build 共用)
def item_errors(it):
    """單一小件的欄位錯誤(中文)。"""
    if not isinstance(it, dict):
        return ["kit 每一項要是 {type, …} 物件"]
    t = it.get("type")
    if t not in REQUIRED:
        return [f"沒有這種小件「{t}」(可用:{'、'.join(REQUIRED)})"]
    errs = [f"{t} 缺必要欄位 {k}" for k in REQUIRED[t] if it.get(k) in (None, "", [])]
    at = it.get("at")
    if at is not None:
        ks = [k for k in AT_KEYS if k in (at if isinstance(at, dict) else {})]
        if len(ks) != 1:
            errs.append(f"{t} 的 at 要剛好一種:text / box / el")
        elif ks[0] == "box" and not (isinstance(at["box"], list) and len(at["box"]) == 4
                                    and all(isinstance(v, (int, float)) for v in at["box"])):
            errs.append(f"{t} 的 at.box 要是 [x, y, w, h](畫面百分比)")
    if "t0" in it and not isinstance(it["t0"], (int, float)):
        errs.append(f"{t} 的 t0 要是秒數")
    return errs


def line_errors(items):
    """同一句:每項欄位、同句 <= LINE_MAX 個、punch <= PUNCH_PER_LINE。"""
    if not isinstance(items, list):
        return ["kit 要是清單 [ {…}, … ]"]
    errs = [e for it in items for e in item_errors(it)]
    if len(items) > LINE_MAX:
        errs.append(f"同一句小件 {len(items)} 個 > 上限 {LINE_MAX}")
    n = sum(1 for it in items if isinstance(it, dict) and it.get("type") == "punch")
    if n > PUNCH_PER_LINE:
        errs.append(f"同一句 punch {n} 次 > 上限 {PUNCH_PER_LINE}")
    return errs


def shot_errors(items, tilt):
    """同一鏡頭(可跨句):<= SHOT_MAX 個、spotlight 不可用在 tilt 鏡頭(photo 組)。"""
    errs = []
    if len(items) > SHOT_MAX:
        errs.append(f"同一鏡頭小件 {len(items)} 個 > 上限 {SHOT_MAX}")
    if tilt and any(isinstance(it, dict) and it.get("type") == "spotlight" for it in items):
        errs.append("spotlight 不可用在會傾斜的 photo 組鏡頭(改用 callout,或明寫 fx 為 zoom / none)")
    return errs


# ---------------------------------------------------------------- 定位換算
def find_text_rect(entries, kw):
    """在 .boxes.json 文字區塊找 kw(同 hl:忽略空白大小寫、可跨行),取第一個命中;回傳原圖像素外框 (x0, y0, x1, y1) 或 None。"""
    seq = [(ei, ci) for ei, e in enumerate(entries or []) for ci, ch in enumerate(e["text"]) if not ch.isspace()]
    flat = "".join(entries[ei]["text"][ci].lower() for ei, ci in seq)
    k = "".join(kw.split()).lower()
    i = flat.find(k) if k else -1
    if i < 0:
        return None
    xs0, ys0, xs1, ys1 = [], [], [], []
    for ei, ci in seq[i:i + len(k)]:
        e = entries[ei]
        x0, y0, x1, y1 = e["box"]
        if e.get("chars"):
            x0, x1 = e["chars"][ci][0], e["chars"][ci][1]
        xs0.append(x0), ys0.append(y0), xs1.append(x1), ys1.append(y1)
    return min(xs0), min(ys0), max(xs1), max(ys1)


def to_canvas(box, sc, pos, ox=0.0):
    """原圖像素框 -> 畫布(1x)[x, y, w, h];ox = 頁面左側補邊(text 組 zoom 類的 _zoom_pad)。"""
    x0, y0, x1, y1 = box
    return [pos[0] + x0 * sc + ox, pos[1] + y0 * sc, (x1 - x0) * sc, (y1 - y0) * sc]


def pct_rect(box, size, ox=0.0):
    """at.box(畫面百分比 [x, y, w, h])-> 像素 [x, y, w, h]。"""
    w, h = size
    return [box[0] / 100 * w + ox, box[1] / 100 * h, box[2] / 100 * w, box[3] / 100 * h]


def map_rect(rect, f, ox=0.0):
    """畫布矩形經 fx 映射函式 f(畫布 -> 成片,build.fx_map 回傳值)後的外接框 [x, y, w, h];ox 為頁面補邊(映射前扣掉)。"""
    x, y, w, h = rect
    pts = [f(px - ox, py) for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h))]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def item_start(it):
    return float(it.get("t0", T0))


# ---------------------------------------------------------------- 擺放(障礙物避讓;純函式,tests/test_kit.py 測)
def gap(a, b):
    """兩個 [x, y, w, h] 外框的最短距離(重疊或相貼 = 0)。"""
    dx = max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]), 0.0)
    dy = max(b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]), 0.0)
    return math.hypot(dx, dy)


def overlap_area(a, b):
    return max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])) * max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))


def nearest_gap(r, obs):
    """r 離最近障礙物的距離(沒有障礙物 = 9999)。"""
    return min((gap(r, o) for o in obs), default=9999.0)


def pt_gap(p, r):
    """點到 [x, y, w, h] 的距離。"""
    return math.hypot(max(r[0] - p[0], 0.0, p[0] - r[0] - r[2]), max(r[1] - p[1], 0.0, p[1] - r[1] - r[3]))


def subtract(r, hole):
    """r 扣掉 hole 後剩下的矩形(最多 4 塊);不相交回傳 [r]。"""
    if overlap_area(r, hole) <= 0:
        return [r]
    x0, y0, x1, y1 = r[0], r[1], r[0] + r[2], r[1] + r[3]
    hx0, hy0, hx1, hy1 = max(x0, hole[0]), max(y0, hole[1]), min(x1, hole[0] + hole[2]), min(y1, hole[1] + hole[3])
    out = []
    for q in ((x0, y0, x1, hy0), (x0, hy1, x1, y1), (x0, hy0, hx0, hy1), (hx1, hy0, x1, hy1)):
        if q[2] - q[0] > 0.5 and q[3] - q[1] > 0.5:
            out.append([q[0], q[1], q[2] - q[0], q[3] - q[1]])
    return out


def _free_spots(w, h, dom, obs, margin, step=16):
    """w x h 的框放在 dom=(x0,y0,x1,y1) 內、離每個障礙物 >= margin 的所有左上角(依序列掃描)。"""
    inf = [(o[0] - margin, o[1] - margin, o[0] + o[2] + margin, o[1] + o[3] + margin) for o in obs]
    y = dom[1]
    while y + h <= dom[3] + 1e-6:
        x = dom[0]
        while x + w <= dom[2] + 1e-6:
            if not any(x < i[2] and x + w > i[0] and y < i[3] and y + h > i[1] for i in inf):
                yield x, y
            x += step
        y += step


def _nearest_spot(w, h, dom, obs, margin, center, step=16):
    best, bd = None, 1e18
    for x, y in _free_spots(w, h, dom, obs, margin, step):
        d = (x + w / 2 - center[0]) ** 2 + (y + h / 2 - center[1]) ** 2
        if d < bd:
            best, bd = (x, y), d
    return best


def _cost_spot(w, h, dom, obs, margin, center, step=16):
    """沒有完全空白的位置時:重疊(含邊距)面積最小者,同分取離 center 近的。"""
    best, bc = None, (1e18, 1e18)
    y = dom[1]
    while y + h <= dom[3] + 1e-6:
        x = dom[0]
        while x + w <= dom[2] + 1e-6:
            r = [x - margin, y - margin, w + 2 * margin, h + 2 * margin]
            c = (sum(overlap_area(r, o) for o in obs), (x + w / 2 - center[0]) ** 2 + (y + h / 2 - center[1]) ** 2)
            if c < bc:
                best, bc = (x, y), c
            x += step
        y += step
    return best or (dom[0], dom[1])


_FONTS = {}


def text_width(txt, px, bold=True):
    """Pillow 量字寬(與 kit.html 同字型);粗估即可,擺放另留邊距。"""
    from PIL import ImageFont
    k = (bold, px)
    if k not in _FONTS:
        _FONTS[k] = ImageFont.truetype(str(P.FONT_BOLD if bold else P.FONT_REG), px)
    return _FONTS[k].getlength(txt)


def pop_size(it, scale=1.0):
    """pop 外框(含 8px 描邊)寬高;字級 = (it.size 或 120) * scale。回傳 (字級, 寬, 高)。"""
    px = max(24, round((it.get("size") or 120) * scale))
    return px, text_width(it["text"], px) + 8, px * 1.1 + 8


def badge_size(it):
    px = it.get("size") or 56
    arrow = "▲ " if it.get("dir") == "up" else "▼ " if it.get("dir") == "down" else ""
    h = round(px * 1.43) if it.get("size") else 80
    return text_width(arrow + str(it["text"]), px) + 52, h


def lower_size(it, ls=1.0):
    m = text_width(it["text"], round(48 * ls))
    w = m
    h = 14 * ls + 18 * ls + 48 * ls * 1.2 + 14 * ls          # 上下 padding + 主字 + 底線(margin-top 10 + 4)
    if it.get("sub"):
        w = max(m, text_width(it["sub"], round(36 * ls), bold=False))
        h += 36 * ls * 1.25
    return w + 56 * ls, h


def place_pop(it, rect, obs, dom):
    """pop 放在離目標最近、不碰任何障礙物(邊距 MARGIN)的空白處;字級最多縮 3 級。回傳 (框, 字級, ok)。"""
    c = (rect[0] + rect[2] / 2, rect[1] + rect[3] / 2)
    for sc in POP_SCALES:
        px, w, h = pop_size(it, sc)
        sp = _nearest_spot(w, h, dom, obs, MARGIN, c)
        if sp:
            return [sp[0], sp[1], w, h], px, True
    px, w, h = pop_size(it, POP_SCALES[-1])
    top = (dom[0], dom[1], dom[2], min(dom[3], dom[1] + 260))      # 找不到:畫面中上方、重疊最少的位置
    sp = _cost_spot(w, h, top, obs, MARGIN, ((dom[0] + dom[2]) / 2, dom[1]))
    return [sp[0], sp[1], w, h], px, False


def place_badge(it, rect, obs, dom):
    """badge 放目標外側:右 > 上 > 左 > 下,離障礙物 >= BADGE_MARGIN;四側都沒有就找全畫面最近的空白。回傳 (框, ok)。"""
    w, h = badge_size(it)
    x0, y0, x1, y1 = rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]
    c = ((x0 + x1) / 2, (y0 + y1) / 2)
    ks = sorted(range(-8, 9), key=abs)
    for off in (12, 20, 32):
        sides = (lambda k: (x1 + off, y0 - h * 0.35 + k * 12), lambda k: (c[0] - w / 2 + k * 16, y0 - off - h),
                 lambda k: (x0 - off - w, y0 - h * 0.35 + k * 12), lambda k: (c[0] - w / 2 + k * 16, y1 + off))
        for f in sides:
            for k in ks:
                x, y = f(k)
                b = [x, y, w, h]
                if x >= dom[0] and y >= dom[1] and x + w <= dom[2] and y + h <= dom[3] and nearest_gap(b, obs) >= BADGE_MARGIN:
                    return b, True
    sp = _nearest_spot(w, h, dom, obs, BADGE_MARGIN, c)
    if sp:
        return [sp[0], sp[1], w, h], True
    sp = _cost_spot(w, h, dom, obs, BADGE_MARGIN, c)
    return [sp[0], sp[1], w, h], False


def place_lower(it, anchor, obs, dom):
    """lower 固定在左下字幕安全線上方;與文字框重疊先往上找空白帶,再縮小一級,仍重疊才 ok=False。回傳 (框, 縮放, ok)。
    anchor = (x, 下緣 y) 或 None(左 dom[0]+56、下緣 dom[3]-16)。"""
    ax, ab = anchor or (dom[0] + 56, dom[3] - 16)
    for ls in LOWER_SCALES:
        w, h = lower_size(it, ls)
        y = ab - h
        while y >= dom[1] - 1e-6:
            b = [ax, y, w, h]
            if nearest_gap(b, obs) >= LOWER_MARGIN:
                return b, ls, True
            y -= 12
    w, h = lower_size(it, LOWER_SCALES[-1])
    return [ax, ab - h, w, h], LOWER_SCALES[-1], False


def arrow_geom(rect, u, dist, gap_tip=TIP_GAP, head=30):
    """從目標中心往 u 方向:尖端停在目標框外 gap_tip,箭尾離目標框 >= dist。回傳 (tip, tail, 單位向量)。"""
    n = math.hypot(*u)
    ux, uy = u[0] / n, u[1] / n
    cx, cy = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
    k = min((rect[2] / 2 + gap_tip) / abs(ux) if ux else 1e9, (rect[3] / 2 + gap_tip) / abs(uy) if uy else 1e9)
    tip = (cx + ux * k, cy + uy * k)
    L = head + 10
    while pt_gap((tip[0] + ux * L, tip[1] + uy * L), rect) < dist and L < 600:
        L += 4
    return tip, (tip[0] + ux * L, tip[1] + uy * L), (ux, uy)


def arrow_cost(tip, tail, u, obs, dom, head=30, hw=15):
    """箭身(尖端到箭尾的線段 + 三角箭頭)侵入障礙物 / 超出範圍的程度;0 = 完全避開。回傳 (cost, 最近距離)。"""
    ux, uy = u
    base = (tip[0] + ux * head, tip[1] + uy * head)
    mid = (tip[0] + ux * head / 2, tip[1] + uy * head / 2)
    cost, near = 0.0, 9999.0
    n = max(2, int(math.hypot(tail[0] - base[0], tail[1] - base[1]) / 6))
    pts = [(base[0] + (tail[0] - base[0]) * i / n, base[1] + (tail[1] - base[1]) * i / n, ARROW_CLEAR) for i in range(n + 1)]
    pts += [(tip[0], tip[1], HEAD_CLEAR), (base[0] - uy * hw, base[1] + ux * hw, HEAD_CLEAR), (base[0] + uy * hw, base[1] - ux * hw, HEAD_CLEAR),
            (mid[0] - uy * hw * 0.5, mid[1] + ux * hw * 0.5, HEAD_CLEAR), (mid[0] + uy * hw * 0.5, mid[1] - ux * hw * 0.5, HEAD_CLEAR)]
    for x, y, need in pts:
        for o in obs:
            d = pt_gap((x, y), o)
            near = min(near, d - (5 if need == ARROW_CLEAR else 0))
            if d < need:
                cost += need - d
        cost += 2 * (max(dom[0] - x, 0.0) + max(x - dom[2], 0.0) + max(dom[1] - y, 0.0) + max(y - dom[3], 0.0))
    return cost, near


def place_arrow(rect, obs, dom, frames=()):
    """arrow:在目標周圍找「箭尾離目標 120-260px、整條箭身不穿過任何障礙物」的位置(右上 > 左上 > 右下 > 左下 > 其他方向)。
    目標所在的文字框先扣掉目標本身(同一行其餘的字仍是障礙物)。frames = 與目標同框的 callout 外框(尖端改停在它外面)。
    回傳 dict(tip, tail, u, ok, near)。"""
    ob = [q for o in obs for q in subtract(o, [rect[0] - 1, rect[1] - 1, rect[2] + 2, rect[3] + 2])]
    x0, y0, x1, y1 = rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]
    for f in frames:
        x0, y0, x1, y1 = min(x0, f[0]), min(y0, f[1]), max(x1, f[0] + f[2]), max(y1, f[1] + f[3])
    tr = [x0, y0, x1 - x0, y1 - y0]
    best = None
    for u in ARROW_DIRS:
        for dist in ARROW_FAR:
            tip, tail, un = arrow_geom(tr, u, dist)
            if not 120 <= pt_gap(tail, rect) <= 260:
                continue
            cost, near = arrow_cost(tip, tail, un, ob, dom)
            if cost == 0:
                return dict(tip=list(tip), tail=list(tail), u=list(un), ok=True, near=near)
            if best is None or cost < best[0]:
                best = (cost, tip, tail, un, near)
    _, tip, tail, un, near = best
    return dict(tip=list(tip), tail=list(tail), u=list(un), ok=False, near=near)


def _fixed_box(it, vis):
    """callout / tick / cross / zoom / progress 本來就框目標或固定位置,不移動;回傳它們佔的外框 [x, y, w, h](沒有 = None)。"""
    r, t = it.get("rect"), it["type"]
    if t == "progress":
        r = r or [vis[0] + 120, vis[3] - 52, vis[2] - vis[0] - 240, 12]
        lab = 64 if it.get("label") else 0
        return [r[0], r[1] - lab, r[2], r[3] + lab]
    if not r:
        return None
    if t == "callout":
        p = (it.get("pad") or 12) + (it.get("width") or 3) / 2 + 2
        return [r[0] - p, r[1] - p, r[2] + 2 * p, r[3] + 2 * p]
    if t in ("tick", "cross"):
        S = it.get("size") or min(120, max(56, r[3] * 1.2))
        side = it.get("side") or "right"
        mx = r[0] - 16 - S / 2 if side == "left" else r[0] + r[2] / 2 if side == "center" else r[0] + r[2] + 16 + S / 2
        return [mx - S / 2, r[1] + r[3] / 2 - S / 2, S, S]
    if t == "zoom":                     # 放大鏡圈(與 kit.html 同算法)
        cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
        R = it.get("r") or 170
        ux, uy = (-0.8 if cx > (vis[0] + vis[2]) / 2 else 0.8), (-0.6 if cy > (vis[1] + vis[3]) / 2 else 0.6)
        dist = R + math.hypot(r[2], r[3]) * 0.3 + 30
        lx = min(max(cx + ux * dist, vis[0] + R + 24), vis[2] - R - 24)
        ly = min(max(cy + uy * dist, vis[1] + R + 24), vis[3] - R - 8)
        return [lx - R, ly - R, 2 * R, 2 * R]
    return None


def layout(items, vis, obstacles, rects=None, portrait=False):
    """自由擺放小件:依障礙物算出每件的最終位置。
    items = 小件 dict 清單(有 rect;el 目標由 rects 補);vis = (x0, y0, x1, y1) 字幕帶以上的可見區(字幕安全區以 vis[3] 為界);
    obstacles = [[x, y, w, h], …](文字框、圖表元素外框)。回傳 (新 items, 紀錄, 警告)。
    紀錄每件:type、box、nearest(離最近障礙物或其他小件的距離)、ok。順序:固定框的 -> lower -> badge -> pop -> arrow。
    portrait=True(直式畫面窗 1080x1080,計畫 #5c):vis 直接就是文字安全框 PORTRAIT_VIS(x 80–940、y 40–1040;字幕在窗外,下方不留字幕帶),
    可放區 dom = vis(不再內縮)、箭頭不可出框、lower 無目標時貼安全框左下。"""
    dom = tuple(vis) if portrait else (vis[0] + 40, vis[1] + 24, vis[2] - 40, vis[3])
    mid = [(vis[0] + vis[2]) / 2 - 1, (vis[1] + vis[3]) * 0.42, 2, 2]
    out, recs, warns, placed, frames = [], [], [], [], {}
    for it in items:
        it = dict(it)
        if it.get("el") and rects:
            it["rect"] = rects.get(it["el"])
        if not it.get("rect") and not it.get("el") and it["type"] in ("pop", "badge"):
            it["rect"] = mid                      # 沒給目標:可見區中上(同 kit.html)
        out.append(it)
    obs = [list(o) for o in obstacles]

    def rec(it, box, ok, extra=None):
        near = nearest_gap(box, obs + [b for b in placed if b is not box])
        recs.append(dict(type=it["type"], line=it.get("line"), box=[round(v, 1) for v in box], nearest=round(near, 1), ok=ok, **(extra or {})))
        if not ok:
            warns.append(f"句{it.get('line')} kit {it['type']} 放不下(離最近障礙物 {near:.0f}px,已盡量避開)")
    for it in out:
        b = _fixed_box(it, vis)
        if b:
            placed.append(b)
            if it["type"] in ("callout", "tick", "cross"):
                frames.setdefault(tuple(it["rect"]), []).append(b)
            recs.append(dict(type=it["type"], line=it.get("line"), box=[round(v, 1) for v in b], nearest=None, ok=True, fixed=True))
    mv = lambda t: [it for it in out if it["type"] == t]
    for it in mv("arrow"):                        # 先排箭頭(最需要一條長的空白通道),其餘小件再避開箭身
        if not it.get("rect"):
            continue
        fr = frames.get(tuple(it["rect"]), [])
        a = place_arrow(it["rect"], obs + [p for p in placed if p not in fr], dom if portrait else (dom[0] - 24, dom[1] - 8, dom[2] + 24, dom[3]), fr)
        it["tip"], it["tail"], it["u"] = [round(v, 1) for v in a["tip"]], [round(v, 1) for v in a["tail"]], [round(v, 4) for v in a["u"]]
        it["wobble"] = [WOBBLE_PX, WOBBLE_S]
        xs, ys = [a["tip"][0], a["tail"][0]], [a["tip"][1], a["tail"][1]]
        b = [min(xs) - 15, min(ys) - 15, max(xs) - min(xs) + 30, max(ys) - min(ys) + 30]
        recs.append(dict(type="arrow", line=it.get("line"), box=[round(v, 1) for v in b], nearest=round(a["near"], 1), ok=a["ok"],
                         tip=it["tip"], tail=it["tail"]))
        n = max(2, int(math.hypot(a["tail"][0] - a["tip"][0], a["tail"][1] - a["tip"][1]) / 14))
        for i in range(n + 1):                    # 箭身佔用:沿線的一串小方塊(不用外接框,斜線的外接框太浪費)
            cx, cy = a["tip"][0] + (a["tail"][0] - a["tip"][0]) * i / n, a["tip"][1] + (a["tail"][1] - a["tip"][1]) * i / n
            h = 17 if i * 14 > 40 else 20
            placed.append([cx - h, cy - h, 2 * h, 2 * h])
        if not a["ok"]:
            warns.append(f"句{it.get('line')} kit arrow 放不下(箭身離最近障礙物 {a['near']:.0f}px,已選最少侵入的方向)")
    for it in mv("lower"):
        anchor = (it["rect"][0], it["rect"][1] + it["rect"][3]) if it.get("rect") else ((dom[0], dom[3] - 16) if portrait else None)
        b, ls, ok = place_lower(it, anchor, obs + placed, dom)
        it["pos"], it["ls"] = [round(b[0], 1), round(b[1], 1)], ls
        placed.append(b)
        rec(it, b, ok, dict(ls=ls))
    for it in mv("badge"):
        if not it.get("rect"):
            continue
        b, ok = place_badge(it, it["rect"], obs + placed, dom)
        it["pos"] = [round(b[0], 1), round(b[1], 1)]
        placed.append(b)
        rec(it, b, ok)
    for it in mv("pop"):
        b, px, ok = place_pop(it, it["rect"], obs + placed, dom)
        it["pos"], it["size"] = [round(b[0], 1), round(b[1], 1)], px
        placed.append(b)
        rec(it, b, ok, dict(size=px))
    return out, recs, warns


# ---------------------------------------------------------------- 渲染工作
def _sig():
    h = hashlib.md5(str(VERSION).encode())
    for p in (TPL, P.ANIM_TPL / "tokens.css", P.VENDOR / "gsap.min.js"):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def job(items, size, vis, base=None, probe=None, fps=30, obstacles=None, portrait=False):
    """一個圖層的渲染工作(格式同 anim_web.segment,另帶 tpl / probe)。items 的 t 已是相對圖層起點秒數。
    base = zoom 的來源畫面 {path, x, y, w, h};probe = 圖表頁 {type, data, size, ids, all?}(el 目標與圖表元素外框由 anim_web 量 DOM,
    量完才擺放);obstacles = 本圖層已知的障礙物外框(文字框等)。沒有 probe 時在這裡就擺好,job["warns"] = 放不下的警告。
    portrait=True:直式畫面窗(size 1080x1080、vis = PORTRAIT_VIS),見 layout。"""
    obstacles = [[round(v, 1) for v in o] for o in obstacles or []]
    warns, lay = [], None
    if not probe:
        items, recs, warns = layout(items, vis, obstacles, portrait=portrait)
        lay = dict(vis=list(vis), obstacles=obstacles, records=recs)
    dur = max(it["t"] + max(DUR[it["type"]], it.get("hold") or 0) for it in items) + 0.05
    data = dict(size=list(size), vis=[round(v, 2) for v in vis], items=items, dur=round(dur, 3), obstacles=obstacles)
    if portrait:
        data["portrait"] = True
    if lay:
        data["layout"] = lay
    stamp = None
    if base:
        bp = Path(base["path"])
        data["base"] = dict(url=bp.resolve().as_uri(), x=base["x"], y=base["y"], w=base["w"], h=base["h"])
        st = bp.stat()
        stamp = [P.rel(bp), st.st_size, st.st_mtime_ns]
    count = max(1, math.ceil(dur * fps - 1e-6) + 1)
    key = hashlib.md5(json.dumps([_sig(), {k: v for k, v in data.items() if k != "base"}, data.get("base", {}).get("w"),
                                  stamp, probe and [probe["type"], probe["data"], probe["ids"], probe.get("all")], size, fps, count],
                                 ensure_ascii=False, sort_keys=True, default=str).encode("utf8")).hexdigest()[:16]
    return dict(type="kit", tpl=str(TPL), data=data, size=list(size), fps=fps, count=count, key=key, probe=probe,
                dir=str(P.ANIM_WEB_CACHE / f"kit_{key}"), warns=warns)
