"""網頁動畫渲染器(計畫 PLAN_動態小件與圖表 §2):Playwright 無頭 Edge 開 templates/anim/<type>.html,
注入資料後以 GSAP 時間軸逐格 seek 截圖,產出 straight-alpha RGBA PNG 序列(透明底)。

- 產物:build/_anim_web/<type>_<鍵>/0001.png…,旁邊 done 檔記格數;build.py 的 _anim_layers 讀回逐格,
  星座背景(--anim-bg star)仍由 AL.over_star 合成、深色底由 build._over 疊 AL._dark_bg()(模板不畫底)。
- 快取鍵 = 模板 + tokens.css + gsap.min.js 內容雜湊 + VERSION + 資料 JSON + 尺寸 + fps + 格數。
- 確定性:模板只能用 GSAP 時間軸(禁 requestAnimationFrame / Date.now 自跑);每格 tl.pause().seek(t, false)。
  seek 第二參數一定要 false(不壓制事件),否則 count-up 的 onUpdate 不觸發、數字停在 0。
- 並行:build 在執行緒池建鏡頭,sync Playwright 不能跨執行緒共用,所以 render() 把沒命中快取的段落交給子行程
  (python anim_web.py --jobs <檔>)一次渲完;測試與單機呼叫可用 inproc=True。
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

import anim_lib as AL
import kit as KIT
import paths as P
from text_wrap import zwsp

VERSION = 5            # 改本檔的資料轉換或截圖流程時 +1(模板、tokens、gsap 內容已在快取鍵內)
TYPES = ("bars", "list", "num", "versus", "span", "stamp", "flow", "timeline", "line", "table", "kpi", "cols", "share")   # 有網頁模板的類型(has_template 另外要求模板檔存在);其餘由 build 退回 pillow
STAMP_S, STAMP_CENTER = 0.6, (960, 430)     # 同 build.STAMP_S / ANIM_CENTER(印章 0.6 秒後定格,中心在安全區中央)
GSAP = P.VENDOR / "gsap.min.js"
TOKENS = P.ANIM_TPL / "tokens.css"
PORTRAIT_OK = ("bars", "cols", "line", "share", "table", "kpi", "list", "num", "versus", "span", "stamp", "flow", "timeline")    # 有直式(原生畫面窗 1080x1080,W <= H)版面的類型;其餘直式退回 pillow / 橫式縮放(build.anim_engine)
SERIES_MAX = 3
BARS_MAX, COLS_MAX = 10, 12     # 網頁版 bars / cols 的項目上限(build.parse_anim 擋;pillow 版 bars 7、cols 7)
TL_STEP_S, TL_Q_S = 1.2, 2.0      # timeline 每個節點 / 問號的段長(同 build.TL_SEG_S / TL_Q_S)
BARS_ALL_T0, BARS_ALL_GROW, BARS_ALL_STEP = 0.5, 0.7, 0.7   # 一次全播:與 AL.make_bars 相同的起點 / 長出 / 條距(條多時壓縮到 BARS_S 內)

_sig_cache = {}


def has_template(t, portrait=False):
    """有網頁模板;portrait=True 時還要在 PORTRAIT_OK 內。"""
    return t in TYPES and (not portrait or t in PORTRAIT_OK) and (P.ANIM_TPL / f"{t}.html").exists()


def sig(t):
    """模板版本簽章:模板 + tokens + gsap 內容雜湊 + VERSION(build 的鏡頭快取簽章也用它)。"""
    if t not in _sig_cache:
        h = hashlib.md5(str(VERSION).encode())
        for p in (P.ANIM_TPL / f"{t}.html", TOKENS, GSAP):
            h.update(p.read_bytes())
        sw = Path(__file__).with_name("sub_words.txt")      # 共用斷詞詞表改了,鏡頭快取要失效
        h.update(sw.read_bytes() if sw.exists() else b"")
        import seg as _seg                                  # 換斷詞器(--seg ckip)換斷點,鏡頭快取要失效;預設 jieba 不加,舊快取鍵不變
        if _seg.seg_name() != "jieba":
            h.update(_seg.seg_name().encode())
        _sig_cache[t] = h.hexdigest()[:12]
    return _sig_cache[t]


def _hex(c):
    return "#%02x%02x%02x" % tuple(c[:3])


def _color(c):
    if isinstance(c, str) and c in AL.BAR_COLORS:
        return _hex(AL.BAR_COLORS[c])
    return c if isinstance(c, str) and c.startswith("#") else None


def _dec(v):
    """數值的小數位數(照文案寫法:499.99 -> 2、30 -> 0),最多 3 位。"""
    s = repr(float(v))
    return 0 if s.endswith(".0") or "e" in s else min(3, len(s.split(".")[1]))


def bars_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """bars 定義 -> 模板資料。items / groups 舊欄位原樣;series=[名稱…](≤3)時每條數值為 [v1, v2…](缺值 null)。
    item 第 4 欄 {color, icon, hi}:hi 在多系列時只強調該條最後一個有值的系列。prev is None = 一次全播。"""
    W, H = size or (AL.W, AL.H)
    gs = a.get("groups")
    groups = gs if gs else [{"title": None, "bars": a["items"]}]
    rows = []
    for gi, g in enumerate(groups):
        for x in g["bars"]:
            opt = x[3] if len(x) > 3 and isinstance(x[3], dict) else {}
            vals = x[1] if isinstance(x[1], list) else [x[1]]
            icon = None
            if opt.get("icon") and icon_root:
                ip = Path(icon_root) / opt["icon"]
                icon = ip.as_uri() if ip.exists() else None
            rows.append(dict(label=zwsp(x[0]), vals=[None if v is None else float(v) for v in vals],
                             dec=[0 if v is None else _dec(v) for v in vals], unit=x[2] if len(x) > 2 else "",
                             color=_color(opt.get("color")), hi=bool(opt.get("hi")), icon=icon,
                             group=gi if gs else None))
    n = len(rows)
    if prev is None:
        step = min(BARS_ALL_STEP, (AL.BARS_S - 0.1 - BARS_ALL_T0 - BARS_ALL_GROW) / max(1, n - 1))
        tm = dict(prev=0, shown=n, lead=BARS_ALL_T0, gap=step, grow=BARS_ALL_GROW, dur=AL.BARS_S)
    else:
        tm = dict(prev=prev, shown=shown, lead=AL.BARS_STEP_LEAD_S, gap=AL.BARS_STEP_GAP_S,
                  grow=AL.BARS_STEP_GROW_S, dur=AL.bars_step_seconds(prev, shown))
    return dict(title=zwsp(a["title"]), src=a.get("src"), series=a.get("series"), rows=rows, stack=bool(a.get("stack")), ref=_ref(a),
                groups=[zwsp(g["title"]) for g in gs] if gs else [], title_in=bool(title_in), W=W, H=H, **dict(tm, **shock_fields(a, rows, tm)))


def _ref(a):
    """目標線 ref={value, label} -> 模板資料(label 走半形標點正規化 + 斷詞)。"""
    r = a.get("ref")
    return dict(value=float(r["value"]), label=zwsp(AL.norm_text(r.get("label", "")))) if r else None


def _nt(s):
    return AL.norm_text(s) if isinstance(s, str) else s     # 動畫內半形標點正規化(同 anim_lib)


def _wt(s):
    """顯示文字:半形標點正規化 + 共用斷詞(詞與詞之間插 U+200B,模板 CSS word-break:keep-all 只在詞邊界換行;見 text_wrap)。"""
    return zwsp(_nt(s))


def _head_data(a, title_in, size):
    W, H = size or (AL.W, AL.H)
    return dict(title=_wt(a.get("title")), src=a.get("src"), title_in=bool(title_in), W=W, H=H)


def list_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """list:prev is None = 一次全播("all");逐步模式 step k = 第 k 項彈出(prev=k, shown=k+1;prev == shown 凍結)。"""
    items, n = [_wt(x) for x in a["items"]], len(a["items"])
    note = _wt(a["note"]) if a.get("note") else None
    if prev is None:
        prev, shown, step, start, gap = 0, n, "all", 0.35, AL.LIST_ALL_STEP_S
    else:
        step = shown - 1
        start, gap = (0.35 if step == 0 else 0.1), 0.0
    return dict(_head_data(a, title_in, size), items=items, note=note, prev=prev, shown=shown, start=start, gap=gap,
                pop=AL.LIST_POP_S, note_s=AL.LIST_NOTE_S, dur=AL.list_seconds(n, bool(note), step))


def num_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """num:level 1 = label + big、level 2 = compare;prev is None = 一次全播。"""
    W, H = size or (AL.W, AL.H)
    big, cmp_ = _nt(a["big"]), _wt(a.get("compare"))
    if prev is None:
        prev, shown = 0, (2 if cmp_ else 1)
    return dict(W=W, H=H, src=a.get("src"), title_in=bool(title_in), label=_wt(a.get("label")), compare=cmp_, tone=a.get("tone"),
                runs=AL._num_runs(big), count=AL.num_is_count(a["big"]), prev=prev, shown=shown,
                big_fs=AL.NUM_BIG_FS, unit_ratio=AL.NUM_UNIT_RATIO, max_w=AL.NUM_MAX_W, label_cy=AL.NUM_LABEL_CY,
                big_cy=AL.NUM_BIG_CY, cmp_cy=AL.NUM_CMP_CY, label_s=AL.NUM_LABEL_IN_S, big_t0=AL.NUM_BIG_T0,
                count_s=AL.NUM_COUNT_S, fade_s=AL.NUM_FADE_S, cmp_delay_s=AL.NUM_CMP_DELAY_S, cmp_fade_s=AL.NUM_CMP_FADE_S,
                lead=AL.SHARE_LEAD_S, dur=AL.num_step_seconds(prev, shown, a["big"]))


def versus_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """versus:level 0 = 標題 + 欄標題、1 = 左欄、2 = 右欄;prev is None = 一次全播(0 -> 2)。"""
    if prev is None:
        prev, shown = 0, 2

    def side(sd):
        return dict(head=_wt(sd["head"]), lines=[_wt(x) for x in sd["lines"]], mark=sd.get("mark"))
    return dict(_head_data(a, title_in, size), left=side(a["left"]), right=side(a["right"]), prev=prev, shown=shown,
                head_s=AL.VS_HEAD_S, step_s=AL.VS_STEP_S, lead=AL.VS_LEAD_S, dur=AL.versus_step_seconds(prev, shown))


def flow_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """flow:prev / shown = 已顯示的節點數;prev is None = 一次全播。"""
    nodes = [_wt(x) for x in a["nodes"]]
    if prev is None:
        prev, shown = 0, len(nodes)
    return dict(_head_data(a, title_in, size), nodes=nodes, prev=prev, shown=shown, node0_s=AL.FLOW_NODE0_S,
                arrow_s=AL.FLOW_ARROW_S, pop_s=AL.FLOW_POP_S, lead=AL.FLOW_LEAD_S, dur=AL.flow_step_seconds(prev, shown))


def span_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    W, H = size or (AL.W, AL.H)
    big = _nt(a["big"])
    parts = AL._split_num(big)
    return dict(W=W, H=H, src=a.get("src"), frm=_nt(a["from"]), to=_nt(a["to"]), big=big, caption=_wt(a.get("caption", "")),
                ticks=max(0, int(a.get("ticks", 8))), numparts=list(parts) if parts else None, dur=AL.SPAN_S)


def stamp_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    W, H = size or (AL.W, AL.H)
    seed = int(hashlib.md5(a["text"].encode("utf8")).hexdigest()[:8], 16) % 10000
    return dict(W=W, H=H, text=a["text"], seed=seed, color=_hex(AL.STAMP_RED), cx=STAMP_CENTER[0], cy=STAMP_CENTER[1],
                dur=STAMP_S)


def timeline_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """timeline:a 須已帶 points(自帶或 build 併入頂層共用 timeline);scale / tracks / question_between 照傳。
    step k -> prev=k, shown=k+1(1.2 秒);step "q" -> prev=shown=節點數、q=true(2.0 秒);無 step 且 prev None = 全播(prev 省略)。
    點的第 3 欄原樣傳({track}/舊版色碼由模板判讀);日期走 norm_text,說明加斷詞點。"""
    W, H = size or (AL.W, AL.H)
    pts = [[_nt(p[0]), _wt(p[1])] + list(p[2:3]) for p in a["points"]]
    n = len(pts)
    d = dict(points=pts, scale=a.get("scale"), tracks=a.get("tracks"), question_between=a.get("question_between"),
             src=a.get("src"), W=W, H=H, gap=TL_STEP_S, lead=0)
    if a.get("step") == "q":
        d.update(prev=n, shown=n, q=True, dur=TL_Q_S)
    elif prev is not None:
        d.update(prev=prev, shown=shown, dur=TL_STEP_S)
    else:
        d.update(dur=TL_STEP_S * n)         # 全播:prev 省略
    return d


# ---------------------------------------------------------------- line / table / kpi(計畫 #3b;只有網頁版,沒有 pillow 版)
LINE_MAX, TBL_ROWS_MAX, TBL_COLS_MAX, KPI_MIN, KPI_MAX = 3, 5, 4, 2, 4     # 容量上限(build.parse_anim 擋)
NEW_LEAD_FIRST, NEW_LEAD, NEW_TAIL = 0.5, 0.05, 0.1     # 第一段(含軸 / 表頭淡入)與續段的起點延遲;段尾留白
LINE_DRAW_S, LINE_STAG_S, LINE_NOTE_S = 1.2, 0.35, 0.45  # 一條線由左畫到右 / 同段多條線的起點間隔 / 標註點彈入
TBL_ROW_S, TBL_GAP_S, TBL_HI_S = 0.45, 0.3, 0.4          # 一列(含 ✓✗ 畫出)/ 列間隔 / hi 外框彈入
KPI_CELL_S, KPI_GAP_S = 1.0, 0.35                        # 一格(彈入 + count-up)/ 格間隔
NEW_INTRO_S = 0.6                                        # level 0(只有標題與軸 / 表頭)的段長


def new_levels(a):
    """line = 線數、table = 列數、kpi = 格數(step k = 顯示到第 k 項,level = k + 1;"title" = level 0)。"""
    t = a["type"]
    return len(a["lines"]) if t == "line" else len(a["rows"]) if t == "table" else len(a["cells"])


def new_step_seconds(a, prev, shown):
    """line / table / kpi 一段動畫(prev -> shown)的長度(秒);shown == prev = 凍結。build.level_seconds / anim_seconds 與 *_data 共用。"""
    t = a["type"]
    if shown <= 0:
        return NEW_INTRO_S
    if shown <= prev:
        return NEW_TAIL
    k, lead = shown - prev, (NEW_LEAD_FIRST if prev <= 0 else NEW_LEAD)
    if t == "line":
        dur = lead + LINE_STAG_S * (k - 1) + LINE_DRAW_S
        if a.get("points") and shown >= new_levels(a):
            dur += LINE_NOTE_S
    elif t == "table":
        dur = lead + TBL_GAP_S * (k - 1) + TBL_ROW_S + (TBL_HI_S if a.get("hi") else 0)
    else:
        dur = lead + KPI_GAP_S * (k - 1) + KPI_CELL_S
    return dur + NEW_TAIL


# ---------------------------------------------------------------- bars / cols 軸暴衝(2026-11-05,外部設計參考:video-shotcraft axis-rescale-shock)
SHOCK_EXTRA_S = 1.4        # 軸暴衝多出的段長:停頓 0.1 + 衝出 0.28 + 懸停 0.22 + 重縮放 0.7 + 收尾
SHOCK_RATIO = 2.0          # 暴衝項須 >= 其他項最大值的幾倍(build.parse_anim 擋)
SHOCK_T = dict(pause=0.1, burst=0.28, hang=0.22, rescale=0.7, pre=0.55)    # 各階段秒數;pre = 舊比例尺下「其他項最大值」佔繪圖區的比例


def shock_fields(a, rows, tm):
    """bars / cols 開軸暴衝時的額外資料(沒開回傳 {},資料與快取鍵不變):shock = 暴衝項序號(該項強制 hi = 金色)、shock_t = 各階段秒數,
    段長 dur 加 shock_extra(暴衝項在這段長出才加)。rows 為模板資料列(會被就地加 hi)。"""
    j = shock_index(a)
    if j is None:
        return {}
    rows[j]["hi"] = True
    return dict(shock=j, shock_t=SHOCK_T, dur=tm["dur"] + shock_extra(a, tm["prev"], tm["shown"]))


def flat_items(a):
    """bars(items 或 groups 展開)/ cols 的所有項(step 的序號就是這個順序)。"""
    gs = a.get("groups")
    return [b for g in gs for b in g["bars"]] if gs else a["items"]


def shock_index(a):
    """bars / cols 的 shock 選項 -> 暴衝項序號;沒開(省略 / false)回傳 None。true = 數值最大的一項(並列取第一個),整數 = 指定項(0 起算)。"""
    s = a.get("shock")
    if s is None or s is False:
        return None
    if s is True:
        vals = [x[1] if isinstance(x[1], (int, float)) else float("-inf") for x in flat_items(a)]
        return vals.index(max(vals))
    return int(s)


def shock_extra(a, prev=None, shown=None):
    """這段動畫(prev -> shown;None = 一次全播)要加的暴衝秒數:暴衝項在這段長出才算,沒開 = 0。"""
    j = shock_index(a) if a.get("type") in ("bars", "cols") else None
    if j is None:
        return 0.0
    n = len(flat_items(a))
    prev, shown = (0, n) if prev is None else (prev, shown)
    return SHOCK_EXTRA_S if prev <= j < shown else 0.0


def _span(a, prev, shown):
    n = new_levels(a)
    return (0, n) if prev is None else (prev, shown)


def line_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """line:x = 類別或日期標籤、lines = [{name, data}]、scale "time" 時按日期比例;points = [[x, 短標籤]] 標註點(最後一條線畫完時依序彈入)。
    hi = 線序號或名稱(該線加粗、末點數字金色)。step k = 畫出第 k 條線。"""
    prev, shown = _span(a, prev, shown)
    names = [l.get("name", "") for l in a["lines"]]
    hi = a.get("hi")
    hi = names.index(hi) if isinstance(hi, str) and hi in names else (hi if isinstance(hi, int) and not isinstance(hi, bool) else None)
    lead = NEW_LEAD_FIRST if prev <= 0 else NEW_LEAD
    dec = min(1, max(_dec(v) for l in a["lines"] for v in l["data"]))      # 同一張圖所有數值同一個小數位數(資料中最多的,上限 1)
    return dict(_head_data(a, title_in, size), x=[_nt(str(x)) for x in a["x"]],
                lines=[dict(name=_wt(l.get("name", "")), data=[float(v) for v in l["data"]], dec=dec) for l in a["lines"]],
                scale=a.get("scale"), area=bool(a.get("area")), unit=_nt(a.get("unit", "")), hi=hi,
                ymin=a.get("ymin"), ymax=a.get("ymax"),
                points=[[_nt(str(p[0])), _wt(p[1])] for p in a.get("points") or []], prev=prev, shown=shown, lead=lead,
                draw=LINE_DRAW_S, stag=LINE_STAG_S, note_s=LINE_NOTE_S, dur=new_step_seconds(a, prev, shown))


_TBL_YES, _TBL_NO = ("✓", "✔", "✅"), ("✗", "✘", "✕", "❌")


def _tbl_cell(v):
    """表格格子 -> {k: yes|no|text, t}:True / ✓ 系 = yes、False / ✗ 系 = no,數字與字串原樣(整數 >= 1000 加千分位)。"""
    if v is True or (isinstance(v, str) and v.strip() in _TBL_YES):
        return dict(k="yes", t="")
    if v is False or (isinstance(v, str) and v.strip() in _TBL_NO):
        return dict(k="no", t="")
    if isinstance(v, (int, float)):
        return dict(k="text", t=f"{v:,}" if isinstance(v, int) and abs(v) >= 1000 else f"{v:g}")
    return dict(k="text", t=_wt(v))


def table_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """table:cols = 表頭(≤4 欄,不含首欄)、rows = [[項目, 格…]](≤5 列);hi = {"row": k} 或 {"col": j}(金色外框)。step k = 顯示到第 k 列。"""
    prev, shown = _span(a, prev, shown)
    lead = NEW_LEAD_FIRST if prev <= 0 else NEW_LEAD
    return dict(_head_data(a, title_in, size), cols=[_wt(c) for c in a["cols"]],
                rows=[dict(name=_wt(r[0]), cells=[_tbl_cell(v) for v in r[1:]]) for r in a["rows"]],
                corner=_wt(a.get("corner", "")), hi=a.get("hi"), prev=prev, shown=shown, lead=lead,
                row_s=TBL_ROW_S, gap=TBL_GAP_S, hi_s=TBL_HI_S, dur=new_step_seconds(a, prev, shown))


def _kpi_value(v):
    """kpi 數字 -> {num, dec, comma, pre, suf}(可 count-up)或 {text}(無數字,直接顯示)。字串取第一段數字,前後文字當前 / 後綴。"""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return dict(num=float(v), dec=_dec(v), comma=abs(v) >= 10000, pre="", suf="")
    m = re.match(r"^(\D*?)(-?\d[\d,]*(?:\.\d+)?)(.*)$", str(v).strip())
    if not m:
        return dict(text=_nt(str(v)))
    ns = m.group(2).replace(",", "")
    return dict(num=float(ns), dec=_dec(float(ns)), comma="," in m.group(2) or abs(float(ns)) >= 10000, pre=_nt(m.group(1)), suf=_nt(m.group(3)))


def kpi_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """kpi:cells = [{label, value, unit?, delta?, note?}](2–4 格);頂層 unit 是各格預設單位;hi = 格序號(金色外框)。step k = 顯示到第 k 格。"""
    prev, shown = _span(a, prev, shown)
    lead = NEW_LEAD_FIRST if prev <= 0 else NEW_LEAD
    cells = [dict(label=_wt(c["label"]), val=_kpi_value(c["value"]), unit=_nt(c.get("unit", a.get("unit", ""))),
                  delta=_nt(c["delta"]) if c.get("delta") else None, better=c.get("better", "up"), note=_wt(c.get("note"))) for c in a["cells"]]
    return dict(_head_data(a, title_in, size), cells=cells, hi=a.get("hi"), prev=prev, shown=shown, lead=lead,
                cell_s=KPI_CELL_S, gap=KPI_GAP_S, dur=new_step_seconds(a, prev, shown))


# ---------------------------------------------------------------- cols / share(計畫 #3c)
def _step_range(n, prev, shown):
    """逐步類型的 (prev, shown, 起點延遲, 間隔, 長出秒數, 段長):prev is None = 一次全播(0 -> n),節奏同 AL.bars_step_seconds。"""
    if prev is None:
        prev, shown = 0, n
    return prev, shown


def cols_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """cols:items=[[標籤, 數值或[各系列數值], 單位?, {hi?}?]];series(≤3)/ stack / ref / 負值 / 年份 x 軸(類別等距)。
    舊欄位相容:單系列沒有任何 hi 鍵時自動強調最大值(數值全相同則不強調)。step k = 顯示到第 k 組。"""
    items, n = a["items"], len(a["items"])
    prev, shown = _step_range(n, prev, shown)
    opts = [x[3] if len(x) > 3 and isinstance(x[3], dict) else {} for x in items]
    vals = [x[1] if isinstance(x[1], list) else [x[1]] for x in items]
    flat = [v for vs in vals for v in vs if v is not None]
    explicit = any("hi" in o for o in opts)
    auto = not explicit and not a.get("series") and len(set(flat)) > 1
    rows = []
    for x, o, vs in zip(items, opts, vals):
        hi = bool(o.get("hi")) if explicit else (auto and max(v for v in vs if v is not None) == max(flat))
        rows.append(dict(label=_wt(x[0]), vals=[None if v is None else float(v) for v in vs],
                         dec=[0 if v is None else _dec(v) for v in vs], unit=_nt(x[2]) if len(x) > 2 and isinstance(x[2], str) else "", hi=hi))
    unit = next((r["unit"] for r in rows if r["unit"]), "")
    tm = dict(prev=prev, shown=shown, lead=AL.BARS_STEP_LEAD_S, gap=AL.BARS_STEP_GAP_S, grow=AL.BARS_STEP_GROW_S,
              dur=AL.cols_step_seconds(prev, shown))
    return dict(title=_wt(a["title"]), src=a.get("src"), series=a.get("series"), rows=rows, stack=bool(a.get("stack")), ref=_ref(a),
                unit=unit, title_in=bool(title_in), W=(size or (AL.W, AL.H))[0], H=(size or (AL.W, AL.H))[1],
                **dict(tm, **shock_fields(a, rows, tm)))


def share_data(a, prev=None, shown=None, title_in=True, icon_root=None, size=None):
    """share:rows=[{label, parts:[[名稱, 數值, 顏色?]…]}];style "bar"(100% 堆疊條,預設)/ "donut"(單列);unit 預設 %。
    同名稱全部列同色(以第一次出現為準);沒給色碼的依序取 --series-1..4。"""
    rows_in = a["rows"]
    prev, shown = _step_range(len(rows_in), prev, shown)
    names, colors = [], []
    for r in rows_in:
        for p in r["parts"]:
            if p[0] not in names:
                names.append(p[0])
                colors.append(_color(p[2]) if len(p) > 2 and p[2] else None)
    rows = [dict(label=_wt(r["label"]), parts=[dict(name=_wt(p[0]), v=float(p[1]), dec=_dec(p[1]), ci=names.index(p[0])) for p in r["parts"]])
            for r in rows_in]
    W, H = size or (AL.W, AL.H)
    return dict(title=_wt(a["title"]), src=a.get("src"), rows=rows, names=[_wt(x) for x in names], colors=colors,
                style=a.get("style", "bar"), unit=_nt(a.get("unit", "%")), title_in=bool(title_in), W=W, H=H,
                prev=prev, shown=shown, lead=AL.SHARE_LEAD_S, step=AL.SHARE_STEP_S, dur=AL.share_step_seconds(prev, shown))


DATA_FN = {"bars": bars_data, "list": list_data, "num": num_data, "versus": versus_data, "flow": flow_data,
           "span": span_data, "stamp": stamp_data, "timeline": timeline_data, "line": line_data, "table": table_data, "kpi": kpi_data,
           "cols": cols_data, "share": share_data}


def segment(a, prev=None, shown=None, title_in=True, n=1, icon_root=None, fps=AL.FPS, size=None):
    """一段動畫的渲染工作:格數 = min(n, 段長 × fps 無條件進位 + 1),之後由呼叫端停在最後一格。"""
    t = a["type"]
    size = tuple(size or (AL.W, AL.H))
    data = DATA_FN[t](a, prev, shown, title_in, icon_root, size)
    count = max(1, min(int(n), math.ceil(data["dur"] * fps - 1e-6) + 1))
    key = hashlib.md5(json.dumps([sig(t), t, data, size, fps, count], ensure_ascii=False, sort_keys=True)
                      .encode("utf8")).hexdigest()[:16]
    return dict(type=t, data=data, size=list(size), fps=fps, count=count, key=key,
                dir=str(P.ANIM_WEB_CACHE / f"{t}_{key}"))


def _frames(job):
    d = Path(job["dir"])
    return [d / f"{i + 1:04d}.png" for i in range(job["count"])]


def _done(job):
    f = Path(job["dir"]) / "done"
    return f.exists() and f.read_text() == str(job["count"])


def render(jobs, inproc=False):
    """渲染(或取快取)多段,回傳每段的 PNG 路徑清單。未命中的段落預設交給子行程一次渲完。"""
    todo = list({j["key"]: j for j in jobs if not _done(j)}.values())
    if todo:
        P.ANIM_WEB_CACHE.mkdir(parents=True, exist_ok=True)
        if inproc:
            run_jobs(todo)
        else:
            jf = P.ANIM_WEB_CACHE / f"_jobs_{os.getpid()}_{threading.get_ident()}.json"
            jf.write_text(json.dumps(todo, ensure_ascii=False), encoding="utf8")
            try:
                subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--jobs", str(jf)], check=True)
            finally:
                jf.unlink(missing_ok=True)
        bad = [j["key"] for j in todo if not _done(j)]
        if bad:
            raise RuntimeError(f"anim_web 渲染失敗:{bad}")
    return [_frames(j) for j in jobs]


def load(path):
    """PNG -> HxWx4 uint8(straight alpha)。"""
    return np.asarray(Image.open(path).convert("RGBA"))


# ---------------------------------------------------------------- 瀏覽器端
def _font_css():
    return ("@font-face{font-family:'AWBold';src:url('%s');font-weight:normal}"
            "@font-face{font-family:'AWReg';src:url('%s');font-weight:normal}"
            % (P.FONT_BOLD.as_uri(), P.FONT_REG.as_uri()))


def open_job(browser, job):
    """開一頁、注入字型 / tokens / gsap、build(data)。回傳 (context, page, build 結果)。"""
    w, h = job["size"]
    data = job["data"]
    if job.get("probe"):        # kit 的 el 目標:先開圖表頁播到底,量元素外框(成片座標);再依圖表元素擺放自由小件
        rects, obs = probe_rects(browser, job["probe"])
        obstacles = (data.get("obstacles") or []) + obs
        items, recs, warns = KIT.layout(data["items"], data["vis"], obstacles, rects, portrait=bool(data.get("portrait")))
        data = dict(data, rects=rects, items=items, obstacles=obstacles)
        job["_layout"] = dict(vis=data["vis"], obstacles=obstacles, records=recs)
        job["_warns"] = warns
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto((Path(job["tpl"]) if job.get("tpl") else P.ANIM_TPL / f"{job['type']}.html").as_uri())   # kit 小件另給 tpl
    page.add_style_tag(content=_font_css())
    page.add_style_tag(path=str(TOKENS))
    page.evaluate("([w, h]) => { document.documentElement.style.setProperty('--W', w + 'px'); document.documentElement.style.setProperty('--H', h + 'px');"
                  " document.documentElement.classList.toggle('portrait', w <= h); }", [w, h])      # 直式 = 寬 <= 高(原生畫面窗 1080x1080 也算)
    page.add_script_tag(path=str(GSAP))
    res = page.evaluate("""async d => {
        await document.fonts.load("52px AWBold", "字0"); await document.fonts.load("32px AWReg", "字0");
        await document.fonts.ready; return window.build(d); }""", data)
    page.wait_for_function("[...document.images].every(i => i.complete)")
    # 時間軸第一次 seek(0) 不會套用位置 0 的 tl.set(終態項目 / 前段已出現的項目),第 0 格會缺東西(逐段只取第 0 格的凍結段整張空白);
    # 先播到底再回 0,讓位置 0 的 set 先生效(2026-10-22 計畫 #5c 直式端到端時發現)
    page.evaluate("() => { const t = window.tl; if (t) { t.pause().seek(t.duration(), false); t.seek(0, false); } }")
    return ctx, page, res


# 量圖表頁所有「看得到的東西」外框:有自己文字的元素(用 Range 量字)、有底色 / 圖 / 邊框的元素(長條、線、色塊);略過接近全畫面的容器
_OBS_JS = """() => {
  const W = innerWidth, H = innerHeight, out = [];
  for (const e of document.body.querySelectorAll("*")) {
    if (["SCRIPT", "STYLE", "defs", "stop"].includes(e.tagName)) continue;
    const cs = getComputedStyle(e);
    if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) < 0.05) continue;
    const add = r => { if (r.width >= 4 && r.height >= 4 && r.width * r.height < 0.4 * W * H) out.push([r.x, r.y, r.width, r.height]); };
    const own = [...e.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim());
    if (own.length) { const g = document.createRange(); g.selectNodeContents(e); add(g.getBoundingClientRect()); continue; }
    const bg = cs.backgroundColor, vis = bg && !/rgba\(\d+, \d+, \d+, 0\)|transparent/.test(bg);
    if (vis || cs.backgroundImage !== "none" || parseFloat(cs.borderTopWidth) > 0 || ["IMG", "CANVAS", "rect", "line", "path", "circle", "polygon", "polyline"].includes(e.tagName))
      add(e.getBoundingClientRect());
  }
  return out;
}"""


def probe_rects(browser, pr):
    """圖表頁(pr = {type, data, size, ids, all?})播到底後:各 id 的外框 {id: [x, y, w, h]}(找不到的不列)、
    pr["all"] 時另回傳所有文字 / 色塊元素外框(障礙物)。回傳 (rects, obstacles)。"""
    ctx, page, _ = open_job(browser, dict(pr, probe=None))
    page.evaluate("() => { window.tl.pause().seek(window.tl.duration(), false); }")
    r = page.evaluate("""ids => Object.fromEntries(ids.map(i => [i, document.querySelector(i)]).filter(p => p[1])
        .map(([i, e]) => { const b = e.getBoundingClientRect(); return [i, [b.x, b.y, b.width, b.height]]; }))""", pr["ids"])
    obs = page.evaluate(_OBS_JS) if pr.get("all") else []
    ctx.close()
    return r, [[round(v, 1) for v in o] for o in obs]


def seek_shot(page, t, path=None):
    page.evaluate("t => { window.tl.pause().seek(t, false); }", t)   # false = 不壓制事件(count-up 的 onUpdate 要觸發)
    return page.screenshot(path=str(path) if path else None, omit_background=True)


def render_job(browser, job, out_dir):
    """逐格截圖到 out_dir/NNNN.png;回傳 (每格毫秒, build 結果)。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx, page, res = open_job(browser, job)
    for m in job.get("_warns") or []:
        print(f"[anim_web] kit 警告:{m}")
    lay = job.get("_layout") or job["data"].get("layout")
    if lay:         # 每件小件最終位置與離最近障礙物的距離(檢查與除錯用)
        (out_dir / "kit_layout.json").write_text(json.dumps(lay, ensure_ascii=False, indent=1), encoding="utf8")
    t0 = time.perf_counter()
    for i in range(job["count"]):
        seek_shot(page, i / job["fps"], out_dir / f"{i + 1:04d}.png")
    ms = (time.perf_counter() - t0) * 1000 / job["count"]
    ctx.close()
    return ms, res


def launch(pw):
    return pw.chromium.launch(channel="msedge", headless=True)


def run_jobs(jobs):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = launch(pw)
        try:
            for job in jobs:
                final = Path(job["dir"])
                part = final.with_name(f"{final.name}.part{os.getpid()}")
                shutil.rmtree(part, ignore_errors=True)
                ms, res = render_job(browser, job, part)
                for m in res.get("problems") or []:
                    print(f"[anim_web] {job['type']} 警告:{m}")
                (part / "done").write_text(str(job["count"]))
                if _done(job):          # 別的執行緒已經渲完同一段
                    shutil.rmtree(part, ignore_errors=True)
                else:
                    shutil.rmtree(final, ignore_errors=True)
                    part.replace(final)
                print(f"[anim_web] {job['type']} {job['count']} 格 {ms:.1f} ms/格 共 {ms * job['count'] / 1000:.1f} 秒")
        finally:
            browser.close()


# ---------------------------------------------------------------- 容量量測(渲染前檢查,2026-10-22 計畫 #5)
SAFE_X, SAFE_TOP, SAFE_BOTTOM_KEEP, FS_MIN, NOTE_FS_MIN = 40, 24, 240, 44, 30   # 左右 / 上離邊、底部字幕安全帶(同 build.IMG_BOTTOM_KEEP)、文字下限(px)

# 播到底後量:每個文字節點(外框 + 字級)與所有看得到的色塊 / 線外框;略過近乎全畫面的容器
_MEASURE_JS = """() => {
  const W = innerWidth, H = innerHeight, texts = [], shapes = [];
  const vis = e => e.checkVisibility ? e.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}) : true;
  for (const e of document.body.querySelectorAll("*")) {
    if (["SCRIPT", "STYLE", "defs", "stop", "clipPath"].includes(e.tagName) || !vis(e)) continue;
    const cs = getComputedStyle(e);
    let any = false;
    for (const n of e.childNodes) {
      if (n.nodeType !== 3) continue;
      const tx = n.textContent.replace(/[\u200B\s]/g, "");
      if (!tx) continue;
      const g = document.createRange(); g.selectNodeContents(n);
      const r = g.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      texts.push({t: tx.slice(0, 10), r: [r.x, r.y, r.width, r.height], fs: parseFloat(cs.fontSize), note: !!e.closest(\".src\")}); any = true;
    }
    if (any) continue;
    const bg = cs.backgroundColor, has = bg && !/rgba\(\d+, \d+, \d+, 0\)|transparent/.test(bg);
    if (has || cs.backgroundImage !== "none" || ["IMG", "CANVAS", "rect", "line", "path", "circle", "polygon", "polyline"].includes(e.tagName)) {
      const r = e.getBoundingClientRect();
      if (r.width >= 4 && r.height >= 4 && r.width * r.height < 0.4 * W * H) shapes.push([r.x, r.y, r.width, r.height]);
    }
  }
  return {texts, shapes};
}"""


def analyze(m, w, h, bottom_keep=SAFE_BOTTOM_KEEP):
    """量測結果 -> 錯誤訊息:文字 < FS_MIN、元素出安全區(左右 SAFE_X、上 SAFE_TOP、下進字幕安全帶)、文字框互相重疊。
    註記例外(下限 NOTE_FS_MIN):出處 .src 內的字、單位 / 刻度這類 <= 4 字的短字。同時回傳最低元素下緣 bottom。"""
    sx, sr, st = SAFE_X, SAFE_X, SAFE_TOP
    if w <= h:      # 直式畫面窗 1080x1080:文字安全框 x 80–940、y 40–1040(同 build.P_SAFE),字幕在窗外所以下方不留字幕帶
        sx, sr, st, bottom_keep = 80, 140, 40, 40
    errs, lim_b = [], h - bottom_keep
    small = sorted({(round(t["fs"]), t["t"]) for t in m["texts"]
                    if t["fs"] < (NOTE_FS_MIN if t.get("note") or len(t["t"]) <= 4 else FS_MIN) - 0.5})
    errs += [f"文字 {fs}px 太小(下限 {FS_MIN}px,註記 {NOTE_FS_MIN}px)「{t}」" for fs, t in small[:3]]
    out = []
    for lab, r in [(t["t"], t["r"]) for t in m["texts"]] + [("圖形", r) for r in m["shapes"]]:
        x, y, rw, rh = r
        if x < sx - 1 or x + rw > w - sr + 1 or y < st - 1 or y + rh > lim_b + 1:
            out.append(f"「{lab}」({x:.0f},{y:.0f},{x + rw:.0f},{y + rh:.0f})")
    if out:
        errs.append(f"元素超出安全區(左 >= {sx}、右 >= {sr}、上 >= {st}、下緣 <= {lim_b}): " + "、".join(out[:4]) + (f" 等 {len(out)} 處" if len(out) > 4 else ""))
    tx, hit = m["texts"], []
    for i in range(len(tx)):
        for j in range(i + 1, len(tx)):
            a, b = [(r[0], r[1] + r[3] * 0.2, r[2], r[3] * 0.6) for r in (tx[i]["r"], tx[j]["r"])]   # 字框含行距,取中間 60% 近似墨跡
            if min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]) > 6 and min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]) > 6:
                hit.append(f"「{tx[i]['t']}」×「{tx[j]['t']}」")
    if hit:
        errs.append("標籤重疊: " + "、".join(hit[:4]))
    allb = [r[1] + r[3] for r in m["shapes"]] + [t["r"][1] + t["r"][3] for t in m["texts"]]
    return dict(errors=errs, bottom=round(max(allb), 1) if allb else 0)


def measure_jobs(jobs):
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as pw:
        browser = launch(pw)
        try:
            for job in jobs:
                ctx, page, res = open_job(browser, job)
                page.evaluate("t => { window.tl.pause().seek(t, false); }", res.get("dur", 0))
                r = analyze(page.evaluate(_MEASURE_JS), *job["size"])
                r["problems"] = list(res.get("problems") or [])
                out[job["key"]] = r
                ctx.close()
        finally:
            browser.close()
    return out


def measure(jobs):
    """對 segment() 產的工作播到底量版面:回傳每項 {errors, problems, bottom}(同 key 的快取在 build\_anim_web\_measure)。
    未命中的工作交子行程(同 render,sync Playwright 不能跨執行緒)。"""
    cdir = P.ANIM_WEB_CACHE / "_measure"
    cdir.mkdir(parents=True, exist_ok=True)
    ver = sig("bars")
    res, todo = {}, []
    for j in jobs:
        f = cdir / f"{j['key']}_{ver}.json"
        if f.exists():
            res[j["key"]] = json.loads(f.read_text(encoding="utf8"))
        elif j["key"] not in [t["key"] for t in todo]:
            todo.append(j)
    if todo:
        jf = cdir / f"_jobs_{os.getpid()}.json"
        of = cdir / f"_out_{os.getpid()}.json"
        jf.write_text(json.dumps(todo, ensure_ascii=False), encoding="utf8")
        try:
            subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--jobs", str(jf), "--measure", str(of)], check=True)
            got = json.loads(of.read_text(encoding="utf8"))
        finally:
            jf.unlink(missing_ok=True)
            of.unlink(missing_ok=True)
        for k, v in got.items():
            (cdir / f"{k}_{ver}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf8")
            res[k] = v
    return [res[j["key"]] for j in jobs]


def main():
    ap = argparse.ArgumentParser(description="anim_web 子行程:渲染 jobs 檔裡的段落")
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--measure", help="改成量測模式:結果 JSON 寫到此檔")
    args = ap.parse_args()
    jobs = json.loads(Path(args.jobs).read_text(encoding="utf8"))
    if args.measure:
        Path(args.measure).write_text(json.dumps(measure_jobs(jobs), ensure_ascii=False), encoding="utf8")
    else:
        run_jobs(jobs)


if __name__ == "__main__":
    main()
