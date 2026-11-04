"""截圖鏡頭「畫面邊緣不裁字」幾何測試:python -X utf8 pipeline\\tests\\test_text_clip.py
涵蓋 fx_map(zoom 錨點、tilt 四角)、text_clip(上/左/右與整行出畫面的判定)、_zoom_fit、layout_image 的整行推出。"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import build as B  # noqa: E402

W, H = B.W, B.H
FAILS = []


def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  {info}" if info else ""))
    if not cond:
        FAILS.append(name)


def ent(x0, y0, x1, y1, text="測試文字"):
    return dict(text=text, box=[x0, y0, x1, y1])


def bad_set(c):
    return {(a, round(b)) for a, b, _ in c["bad"]}


def test_fx_map():
    for fx in ("tilt_l", "tilt_r"):
        for u in B.FX_U:
            m = B.fx_map(fx, u)
            err = max(abs(a - b) for (x, y), d in zip(((0, 0), (W, 0), (0, H), (W, H)), B._tilt_quad(fx, u))
                      for a, b in zip(m(x, y), d))
            check(f"{fx} u={u} 四角對到 _tilt_quad", err < 1e-6, f"誤差 {err:.2e}")
    m = B.fx_map("zoom", 1.0, (1.03, 0.25, 0.5))
    check("zoom 錨點不動、其餘向外", abs(m(W * 0.25, H * 0.5)[0] - W * 0.25) < 1e-9 and abs(m(0, 0)[0] + 0.03 * W * 0.25) < 1e-9)
    check("none 不變形", B.fx_map("none", 1.0)(123, 456) == (123, 456))


def test_text_clip():
    # none:上緣切半行 14px、整行在上方之外 1 行、左 10px、右 20px;下緣不限
    c = B.text_clip([ent(100, 10, 800, 90), ent(100, -120, 800, -2), ent(30, 300, 1900, 380), ent(100, 1000, 800, 1200)],
                    1.0, (0, 0), "none")
    check("none 上/左/右", bad_set(c) == {("上", 14), ("左", 10), ("右", 20)} and c["out"] == 1, str(c["bad"]))
    # zoom:起點離上緣 30px,放大 3% 後剩 14.7px -> 錯;40px -> 25.0px 可
    c = B.text_clip([ent(200, 30, 1700, 110)], 1.0, (0, 0), "zoom", (1.03, 0.5, 0.5))
    check("zoom 終點上緣不足", bad_set(c) == {("上", 9)}, str(c["bad"]))
    c = B.text_clip([ent(200, 40, 1700, 120)], 1.0, (0, 0), "zoom", (1.03, 0.5, 0.5))
    check("zoom 終點上緣足夠", not c["bad"] and abs(c["top"] - 25.0) < 0.01, f"top={c['top']}")
    # tilt:近側上緣在畫面外,同樣的畫布 y 近側被切、遠側不會;畫布上緣切到的字遠側也算
    near, far = ent(100, 30, 500, 110), ent(1400, 30, 1800, 110)
    for fx, cut, keep in (("tilt_l", near, far), ("tilt_r", far, near)):
        check(f"{fx} 近側被切", [a for a, _, _ in B.text_clip([cut], 1.0, (0, 0), fx)["bad"]] == ["上"])
        check(f"{fx} 遠側完整", not B.text_clip([keep], 1.0, (0, 0), fx)["bad"])
        c = B.text_clip([dict(keep, box=[keep["box"][0], -20, keep["box"][2], 60])], 1.0, (0, 0), fx)
        check(f"{fx} 畫布上緣切到遠側的字", [a for a, _, _ in c["bad"]] == ["上"], str(c["bad"]))
        c = B.text_clip([dict(keep, box=[keep["box"][0], -90, keep["box"][2], -10])], 1.0, (0, 0), fx)
        check(f"{fx} 整行在畫布外", not c["bad"] and c["out"] == 1)


def test_zoom_fit():
    z = B._zoom_fit(50, 1870)
    m = B._side_margin(50, 1870, B._fx_maps("zoom", z))
    check("_zoom_fit 降倍率後左右仍 >= 40", 1.0 < z[0] < B.ZOOM_END and m >= B.TEXT_EDGE_X - 0.5, f"z={z} side={m:.1f}")
    check("_zoom_fit 放不下就不放大", B._zoom_fit(30, 1890)[0] == 1.0)
    check("_zoom_fit 夠寬就用上限", B._zoom_fit(300, 1500)[0] == B.ZOOM_END)


def test_layout():
    # 假截圖:6 行(行距 160、行高 80),hl 在最後一行 -> 整張要上移,第一行必須整行出畫面而不是切一半
    ents = [ent(60, 60 + 160 * i, 1860, 140 + 160 * i, f"第{i}行內容文字" + ("目標" if i == 5 else "")) for i in range(6)]
    for e in ents:  # 逐字框:hl 只命中關鍵字那幾個字,不是整行
        cw = (e["box"][2] - e["box"][0]) / len(e["text"])
        e["chars"] = [[e["box"][0] + j * cw, e["box"][0] + (j + 1) * cw] for j in range(len(e["text"]))]
    B._box_cache["_t"] = ents
    B._ink_cache["_t"] = np.zeros((1080, 1920), dtype=np.int16)
    for kw, want_out in (("目標", 1), ("第0行", 0)):
        for fx in ("none", "zoom", "tilt_l", "tilt_r"):
            s = dict(fx=fx, img="_t", hls=[dict(line=1, kws=[kw])])
            lay = B.layout_image(s, Path("."), (1920, 1080))
            c = B.text_clip(ents, lay["sc"], lay["pos"], fx, lay.get("zoom"))
            hb = lay["hits"][0][0]["box"]
            m = B.fx_map(fx, 1.0, lay.get("zoom"))
            bottom = max(m(lay["pos"][0] + x * lay["sc"], lay["pos"][1] + hb[3] * lay["sc"])[1] for x in (hb[0], hb[2]))
            check(f"layout hl={kw} {fx}", not lay["too_big"] and not c["bad"] and c["out"] == want_out == lay["n_out"]
                  and bottom <= H - B.IMG_BOTTOM_KEEP,
                  f"sc={lay['sc']:.3f} pos={lay['pos']} zoom={lay.get('zoom')} top={c['top']:.1f} side={c['side']:.1f} "
                  f"out={c['out']} hl底={bottom:.0f} bad={c['bad']}")


def main():
    test_fx_map()
    test_text_clip()
    test_zoom_fit()
    test_layout()
    print(f"失敗 {len(FAILS)} 項" + (": " + "、".join(FAILS) if FAILS else ""))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
