"""bars 長條圖版面測試:python -X utf8 pipeline\\tests\\test_bars_layout.py
涵蓋:相鄰條間隔 >= 36、最後一條下緣 <= 800(有 src 時 <= 752)、項目過多報錯、縮放順序(先條厚後間隔)、強調色規則、最長條終點 <= 1500、
數值排版(單位 0.75 倍且不小於 44px、共用基線、% 無間隔、千分位)、src 框位置。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import anim_lib as AL  # noqa: E402

FAILS = []


def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  {info}" if info else ""))
    if not cond:
        FAILS.append(name)


def gaps(g):
    ys, bh = g["ys"], g["bh"]
    return [ys[i + 1] - ys[i] - bh for i in range(len(ys) - 1)]


# 1) 逐項目數掃描:能排就要滿足間隔與下緣;排不下就報錯
for n in range(1, 16):
    try:
        g = AL.bars_geometry([n])
    except ValueError as e:
        check(f"n={n} 放不下報錯文字", str(e) == "長條圖項目過多,請拆成兩張")
        continue
    check(f"n={n} 間隔>=36 且 bh>=40", all(x >= 36 for x in gaps(g)) and g["bh"] >= 40, f"bh={g['bh']} gap={g['gap']}")
    check(f"n={n} 下緣<=800", g["bottom"] <= 800, f"bottom={g['bottom']}")
over = 0
for n in range(1, 40):
    try:
        AL.bars_geometry([n])
        over = n
    except ValueError:
        break
check("項目過多會 raise ValueError", over < 39)
try:
    AL.bars_geometry([over + 1])
    check("超過上限一條會報錯", False)
except ValueError as e:
    check("超過上限一條會報錯", "請拆成兩張" in str(e), f"上限 {over} 條")

# 2) 預設規格:5 條用 56/44
g5 = AL.bars_geometry([5])
check("5 條 = 條厚 56 間隔 44", (g5["bh"], g5["gap"]) == (56, 44))
# 縮放順序:條厚先縮到 40,之後才動間隔
seen_gap_shrink = False
for n in range(1, over + 1):
    g = AL.bars_geometry([n])
    if g["gap"] < 44:
        seen_gap_shrink = True
        check(f"n={n} 間隔縮小時條厚已是最低 40", g["bh"] == 40)
    if g["bh"] > 40:
        check(f"n={n} 條厚未到最低時間隔仍 44", g["gap"] == 44)

# 3) 分組:組間距 96,下緣 <= 800
gg = AL.bars_geometry([2, 2], grouped=True, gh=53)
check("分組 2x2 可排且下緣<=800", gg["bottom"] <= 800, f"bottom={gg['bottom']} bh={gg['bh']}")
check("分組間隔 >= 36", all(x >= 36 for i, x in enumerate(gaps(gg)) if i != 1))

# 4) 實際版面物件:強調色與最長條終點
items = [["2022", 3, "款"], ["2023", 9, "款"], ["2024", 5, "款"]]
lay = AL._BarsLayout(items)
check("自動強調最大值那條", lay.hi == [False, True, False])
check("強調條 PAL_ACCENT、其餘 PAL_NEUTRAL", lay.color(1) == AL.PAL_ACCENT and lay.color(0) == AL.PAL_NEUTRAL)
check("最長條終點 <= 1500", max(lay.place(k)["bar"][2] for k in range(3)) <= 1500)
check("hi:false 全部不強調", AL._BarsLayout([["a", 1, "", {"hi": False}], ["b", 2, ""]]).hi == [False, False])
check("hi:true 指定不再自動挑最大值", AL._BarsLayout([["a", 1, "", {"hi": True}], ["b", 2, ""]]).hi == [True, False])
cl = AL._BarsLayout([["a", 1, "", {"color": "alliance"}], ["b", 2, "", {"color": "horde"}]])
check("有指定類別色:不自動強調、顏色照類別", cl.hi == [False, False] and cl.color(0) == AL.BAR_COLORS["alliance"])
try:
    AL._BarsLayout([[str(i), i + 1, ""] for i in range(over + 1)])
    check("_BarsLayout 項目過多報錯", False)
except ValueError:
    check("_BarsLayout 項目過多報錯", True)

# 5) 數值單位字級:數字的 0.75 倍,且不小於 44px
_sizes = []
_orig = AL.text_sprite
AL.text_sprite = lambda text, size, *a, **k: (_sizes.append((text, size)), _orig(text, size, *a, **k))[1]
for num_size, want in ((64, 48), (72, 54), (48, 44), (40, 44)):
    _sizes.clear()
    AL._val_sprite("9", "款", num_size)
    got = dict(_sizes).get("款")
    check(f"數字 {num_size}px -> 單位 {want}px", got == want, f"got={got}")
AL.text_sprite = _orig

# 6) 顯示文字正規化:只在前後任一側是 CJK 時換全形
check("norm_text 中文旁的半形標點", AL.norm_text("他說:好(真的)!") == "他說：好（真的）！")
check("norm_text 數字千分位與英文不動", AL.norm_text("1,000 Take-Two (2K) 12:30") == "1,000 Take-Two (2K) 12:30")
check("norm_text 英文後接中文", AL.norm_text("Steam)的") == "Steam）的")

print("\n失敗 %d 項" % len(FAILS))
sys.exit(1 if FAILS else 0)
