"""visual_check 估秒欄與警告 D(同圖估計過久/過多句)、E(動畫步估計不足)測試(PLAN_TTS_FLOW T3):
python -X utf8 pipeline/tests/test_visual_estimate.py(或 -m pytest);script.txt 寫在 tmp\test_visual_estimate\。"""
import shutil
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import pace  # noqa: E402
import visual_check as VC  # noqa: E402

TMP = PIPE.parent / "tmp" / "test_visual_estimate"
LONG = "字" * 50    # 50 字 ÷ 5.5 字/秒(pace.py)= 9.1 秒 > 9
SCRIPT = f"""# 測試 T
@def anim:lst={{"type":"list","title":"清單","items":["甲","乙","丙"]}}
# 一
img:a|{LONG}
img:b|短短一句。
img:c|三字句。
img:c|三字句。
img:c|三字句。
anim|短短。 ;; anim:lst#0
anim|{'字' * 40}。 ;; anim:lst#0
anim|短。 ;; anim:lst#1
"""


def _run(monkeypatch, need=3.0):
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True)
    src = TMP / "script.txt"
    src.write_text(SCRIPT, encoding="utf-8")
    top, defs, notes, lines = VC.load("t", src)
    seen = []

    class FakeBuild:
        @staticmethod
        def anim_seconds(a):
            seen.append(a.get("step"))
            return need
    monkeypatch.setitem(sys.modules, "build", FakeBuild)
    monkeypatch.setattr(VC, "_BUILD", [FakeBuild])
    W, E, stats = VC.check("t", top, defs, notes, lines, None)
    return lines, W, E, seen


def test_est_column_and_cfg(monkeypatch):
    lines, W, E, _ = _run(monkeypatch)
    assert VC.CFG["est_sec_per_char"] == 1 / pace.CHARS_PER_SEC
    assert lines[0]["est"] == 9.1 and lines[2]["est"] == round(len("三字句。") / pace.CHARS_PER_SEC, 1)
    out = VC.write_table("t", lines, W, E, None, "", TMP / "vt.md").read_text(encoding="utf-8")
    head = next(l for l in out.splitlines() if l.startswith("| 句#"))
    assert head.split(" | ")[3] == "估秒" and "D 同圖估計" in out
    row = next(l for l in out.splitlines() if l.startswith("| 1 |"))
    assert row.split(" | ")[3] == "9.1", row


def test_warning_d_same_image(monkeypatch):
    lines, W, E, _ = _run(monkeypatch)
    d = [(i, m) for c, i, m in W if c == "D"]
    assert [i for i, _ in d] == [1, 3], d             # 句1 單句估計 9.1 秒 > 9;句3-5 同圖 3 句 > 2
    assert "9.1 秒" in d[0][1] and "連續 3 句" in d[1][1]
    assert "D" in lines[0]["codes"] and all("D" in lines[k]["codes"] for k in (2, 3, 4)) and "D" not in lines[1]["codes"]


def test_warning_e_anim_step(monkeypatch):
    lines, W, E, seen = _run(monkeypatch, need=3.0)
    e = [i for c, i, _ in W if c == "E"]
    assert e == [6, 8], e                             # 句6 估 0.8<3、句7 與句6 同一步 → 後續句不算、句8 另一步 估 0.2<3
    assert seen == [0, 1]                             # 步數有帶進 anim_seconds
    lines, W, E, _ = _run(monkeypatch, need=0.5)
    assert [i for c, i, _ in W if c == "E"] == [8]    # 句6 估 0.8 >= 0.5 不警告


if __name__ == "__main__":
    class MP:
        def setitem(self, d, k, v):
            d[k] = v

        def setattr(self, o, k, v):
            setattr(o, k, v)
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(MP())
            print("OK", n)
