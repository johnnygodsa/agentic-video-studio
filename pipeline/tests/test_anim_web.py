"""anim_web 確定性:同一鏡頭第 N 格「連續渲染」與「獨立 seek 兩次(中間先跳到別處)」像素完全相同。不需 GPU。
執行:python -X utf8 pipeline/tests/test_anim_web.py(或 pytest)。輸出只寫 tmp/aw1/test_det。"""
import io
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import anim_web as AW  # noqa: E402
import paths as P  # noqa: E402

SPEC = {"type": "bars", "title": "確定性測試", "src": "測試資料",
        "series": ["2024", "2025"],
        "items": [["甲主機", [120, 150.5], "萬台"], ["乙主機", [None, 80], "萬台", {"hi": True}], ["丙主機", [60, 90], "萬台"]]}


def _arr(png_bytes):
    return np.asarray(Image.open(io.BytesIO(png_bytes)).convert("RGBA"))


def test_seek_deterministic():
    _det(SPEC, "test_det")


def test_seek_deterministic_new_charts():
    """line / table / kpi(計畫 #3b)各驗一次:同一格兩次獨立 seek(中間跳到別處)像素相同,且與連續渲染相同。"""
    for t in ("line", "table", "kpi", "cols", "share", "share_donut", "cols_stack", "bars_ref"):
        _det(TYPE_SPECS[t], f"test_det_{t}")


def test_seek_deterministic_shock():
    """軸暴衝(bars / cols):衝出途中與重縮放途中各驗一格,獨立 seek 兩次與連續渲染相同。"""
    _det(TYPE_SPECS["bars_shock"], "test_det_bars_shock", picks=(85, 100), n=999)
    _det(TYPE_SPECS["cols_shock"], "test_det_cols_shock", picks=(68, 90), n=999)


def test_shock_off_same_data():
    """不開軸暴衝時模板資料與舊版逐欄相同(沒有 shock 鍵;shock:false 等於省略),所以輸出像素差 0。"""
    for t in ("bars_shock", "cols_shock"):
        base = {k: v for k, v in TYPE_SPECS[t].items() if k != "shock"}
        d0, d1 = AW.segment(base, n=999)["data"], AW.segment(dict(base, shock=False), n=999)["data"]
        assert d0 == d1 and "shock" not in d0 and "shock_t" not in d0, t
        d2 = AW.segment(TYPE_SPECS[t], n=999)["data"]
        assert d2["shock"] == 3 and d2["dur"] == d0["dur"] + AW.SHOCK_EXTRA_S and d2["rows"][3]["hi"]


def test_shock_true_targets_max():
    """shock:true 指向數值最大的一項(最大項不在最後也一樣);整數仍指定該項;並列取第一個。"""
    items = [["甲", 150, "萬"], ["乙", 12, "萬"], ["丙", 18, "萬"], ["丁", 9, "萬"]]
    for t, its in (("bars", items), ("cols", items)):
        spec = {"type": t, "title": "最大項不在最後", "src": "測試", "shock": True, "items": its}
        d = AW.segment(spec, n=999)["data"]
        assert d["shock"] == 0 and d["rows"][0]["hi"] and not any(r["hi"] for r in d["rows"][1:]), t
        assert AW.segment(dict(spec, shock=2), n=999)["data"]["shock"] == 2, t
    assert AW.shock_index({"type": "bars", "shock": True, "items": [["a", 5], ["b", 50], ["c", 7]]}) == 1


def _same(a, b, max_px=8, max_d=40):
    """像素相同,容許文字邊緣 AA 的光柵雜訊:Chromium 對同一 DOM 狀態,「連續播過來」與「獨立 seek」偶爾在字形邊緣
    差 1 個 alpha<=10 的像素(已查:DOM style 兩邊逐字相同、換 --disable-gpu / 軟體光柵 / force3D / 整頁重繪都不能消除,
    屬 Chromium 層光柵的歷史相依)。容許 <= max_px 個像素、預乘 alpha 後每通道差 <= max_d;真正的非確定性(數字、位置、形狀)會差一大片。"""
    if a.shape != b.shape:
        return False
    pm = lambda x: np.concatenate([x[..., :3].astype(int) * x[..., 3:].astype(int) // 255, x[..., 3:].astype(int)], -1)     # 預乘 alpha:alpha 近 0 的像素 RGB 不比較
    d = np.abs(pm(a) - pm(b)).max(-1)
    _same.last = f"{int((d > 0).sum())} 個像素不同、最大差 {int(d.max())}"
    return int((d > 0).sum()) <= max_px and int(d.max()) <= max_d


def _det(spec, folder, picks=None, n=60):
    _det_job(AW.segment(spec, n=n), folder, picks)


def _det_job(job, folder, picks=None):
    from playwright.sync_api import sync_playwright
    out = P.TMP / "aw1" / folder
    shutil.rmtree(out, ignore_errors=True)
    fps = job["fps"]
    with sync_playwright() as pw:
        b = AW.launch(pw)
        try:
            for n in (picks or (min(15, job["count"] // 2), min(40, job["count"] - 1))):      # 數字 count-up 中段、全部長完之後(短鏡頭取較小格序)
                AW.render_job(b, job, out)
                cont = AW.load(out / f"{n + 1:04d}.png")
                ctx, page, _ = AW.open_job(b, job)
                AW.seek_shot(page, job["data"]["dur"])
                x1 = _arr(AW.seek_shot(page, n / fps))
                AW.seek_shot(page, 0)
                x2 = _arr(AW.seek_shot(page, n / fps))
                ctx.close()
                assert x1[..., 3].any(), "畫面全透明"
                assert _same(x1, x2), f"{folder} 第 {n} 格兩次獨立 seek 不同({_same.last})"
                assert _same(x1, cont), f"{folder} 第 {n} 格獨立 seek 與連續渲染不同({_same.last})"
        finally:
            b.close()
    shutil.rmtree(out, ignore_errors=True)


# 每型一個最小定義:seek 到末格不報 JS 錯、畫面非全透明、模板回報的版面問題為空(bars 另有多系列)
TYPE_SPECS = {
    "bars": SPEC,
    "list": {"type": "list", "title": "清單", "items": ["第一項", "第二項"], "note": "備註", "src": "測試"},
    "num": {"type": "num", "label": "標籤", "big": "1,234 萬", "compare": "比較基準", "tone": "up"},
    "versus": {"type": "versus", "title": "對照", "left": {"head": "左", "lines": ["甲", "乙"], "mark": "yes"},
               "right": {"head": "右", "lines": ["丙"], "mark": "no"}, "step": 2},
    "span": {"type": "span", "from": "起點", "to": "終點", "big": "7 個月", "caption": "說明", "ticks": 3},
    "stamp": {"type": "stamp", "text": "查無此事"},
    "flow": {"type": "flow", "title": "流程", "nodes": ["甲" + chr(10) + "乙", "丙", "丁"], "step": 2},
    "line": {"type": "line", "title": "折線", "unit": "萬", "area": True, "x": ["2020", "2021", "2022", "2023"],
             "lines": [{"name": "甲", "data": [10, 25.5, 18, 40]}, {"name": "乙", "data": [5, 8, 30, 22]}], "points": [["2021", "改版"]]},
    "table": {"type": "table", "title": "比較", "cols": ["甲", "乙"], "rows": [["功能一", True, False], ["價格", "$60", 70], ["功能三", "✓", "✗"]],
              "hi": {"row": 1}},
    "cols": {"type": "cols", "title": "直條", "src": "測試", "items": [["2022 年 6 月", 1000, "款"], ["2026 年 6 月", 4382, "款"], ["2026 年 10 月", 8011, "款", {"hi": True}]]},
    "cols_stack": {"type": "cols", "title": "堆疊直條", "series": ["甲", "乙"], "stack": True, "ref": {"value": 150, "label": "150 目標"},
                   "items": [["2023", [40, 60], "億"], ["2024", [50, 70], "億"], ["2025", [60, 90], "億"]]},
    "share": {"type": "share", "title": "占比", "rows": [{"label": "2024", "parts": [["甲", 60], ["乙", 38], ["丙", 2]]}, {"label": "2025", "parts": [["甲", 50], ["乙", 50]]}]},
    "share_donut": {"type": "share", "title": "甜甜圈", "style": "donut", "rows": [{"label": "2025", "parts": [["甲", 62], ["乙", 24], ["丙", 11], ["丁", 3]]}]},
    "bars_ref": {"type": "bars", "title": "目標線與負值", "ref": {"value": 10, "label": "10% 門檻"},
                 "items": [["甲", 24.5, "%"], ["乙", -8.5, "%"], ["丙", 3, "%"]]},
    "bars_shock": {"type": "bars", "title": "各平台月活躍", "src": "公開財報", "shock": True,
                   "items": [["甲平台", 12, "萬"], ["乙平台", 18, "萬"], ["丙平台", 9, "萬"], ["丁平台", 150, "萬"]]},
    "cols_shock": {"type": "cols", "title": "每月新增玩家", "src": "公開財報", "shock": True,
                   "items": [["8 月", 12, "萬"], ["9 月", 18, "萬"], ["10 月", 15, "萬"], ["11 月", 160, "萬"]]},
    "kpi": {"type": "kpi", "title": "數字", "cells": [{"label": "銷量", "value": 320, "unit": "萬", "delta": "+12%"},
                                                   {"label": "負評比例", "value": "18%", "delta": "+6%", "better": "down", "note": "註"}], "hi": 0},
}


def test_all_types_seek_last():
    from playwright.sync_api import sync_playwright
    errs = []
    with sync_playwright() as pw:
        b = AW.launch(pw)
        try:
            for t, spec in TYPE_SPECS.items():
                job = AW.segment(spec, **({"prev": 0, "shown": spec["step"] + 1 if t == "flow" else spec["step"]}
                                          if "step" in spec else {}), n=999)
                ctx, page, res = AW.open_job(b, job)
                page.on("pageerror", lambda e, t=t: errs.append(f"{t}: {e}"))
                png = AW.seek_shot(page, job["data"]["dur"])
                ctx.close()
                assert _arr(png)[..., 3].any(), f"{t} 末格全透明"
                assert not res.get("problems"), f"{t} 版面問題:{res['problems']}"
        finally:
            b.close()
    assert not errs, errs


def test_portrait_all_types():
    """直式(畫面窗 1080x1080,計畫 #5c):所有網頁型別都在 PORTRAIT_OK;七個新型別各量一次容量,錯誤與 problems 都要 0。"""
    assert set(AW.TYPES) == set(AW.PORTRAIT_OK)
    from playwright.sync_api import sync_playwright
    bad = []
    with sync_playwright() as pw:
        b = AW.launch(pw)
        try:
            for t in ("list", "num", "versus", "span", "stamp", "flow", "timeline", "bars_shock", "cols_shock"):
                spec = TYPE_SPECS.get(t) or {"type": "timeline", "points": [["1998", "浣熊市毀滅"], ["2001", "收養葛蕾絲"], ["2006", "我有資格當神"]], "question_between": [1, 2]}
                kw = {"prev": 0, "shown": spec["step"] + 1 if t == "flow" else spec["step"]} if "step" in spec else {}
                job = AW.segment({k: v for k, v in spec.items() if k != "step"} if t == "timeline" else spec, n=999, size=(1080, 1080), **kw)
                ctx, page, res = AW.open_job(b, job)
                page.evaluate("t => { window.tl.pause().seek(t, false); }", job["data"]["dur"])
                r = AW.analyze(page.evaluate(AW._MEASURE_JS), 1080, 1080)
                ctx.close()
                bad += [f"{t}: {m}" for m in r["errors"] + list(res.get("problems") or [])]
        finally:
            b.close()
    assert not bad, bad


if __name__ == "__main__":
    test_seek_deterministic()
    test_seek_deterministic_new_charts()
    test_seek_deterministic_shock()
    test_shock_off_same_data()
    test_shock_true_targets_max()
    test_all_types_seek_last()
    test_portrait_all_types()
    print("test_anim_web: PASS")
