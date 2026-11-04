"""影片片段硬切測試:python -X utf8 pipeline\tests\test_clip_cuts.py
鏡頭用到的素材區段內,來源硬切離頭尾都要 >= VIDEO_MIN 秒(build.cut_violations / ClipPicker / check_cuts)。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import build as B  # noqa: E402


def main():
    B.brightness = lambda *a, **k: 100.0      # 不讀影片
    clip = dict(src="x", start=0.0, end=20.0, tags=["t"], cuts=[3.5])
    # dei v1 句 77:3.63 秒的鏡頭在結束前 0.13 秒遇到硬切
    assert B.cut_violations(clip, 0.0, 3.63) == [3.5]
    assert B.cut_violations(clip, 3.5, 3.63) == [3.5]          # 起點貼著硬切(誤差餘量內)也算
    assert B.cut_violations(clip, 3.6, 3.63) == []             # 從硬切後 0.1 秒起
    assert B.cut_violations(clip, 0.5, 6.0) == []              # 硬切離頭尾各 3 秒
    assert B.cut_violations(clip, 1.5, 6.0) == [3.5]           # 離起點只有 2 秒
    assert B.cut_violations(dict(clip, cuts=None), 0.0, 3.63) == []
    assert B.cut_violations({"src": "x"}, 0.0, 3.63) == []     # 沒建檔的片段不檢查

    clips = [dict(src="x", start=0.0, end=12.0, tags=["t"], cuts=[4.0, 8.0])]
    for seed in range(60):
        pk = B.ClipPicker(clips, 120, ROOT, seed=seed)
        c, start, _ = pk.pick("t", 3.6)
        assert not B.cut_violations(c, start, 3.6), (seed, start)
        assert 0.0 <= start and start + 3.6 <= 12.0, (seed, start)
    # 每秒一個硬切的片段放不下 3 秒的鏡頭 -> 換片段(這裡沒有別的 -> None)
    fast = [dict(src="y", start=0.0, end=12.0, tags=["t"], cuts=[float(k) for k in range(1, 12)])]
    assert B.ClipPicker(fast, 120, ROOT).pick("t", 3.0) is None
    # 兩個來源:硬切密的不用,用乾淨的那個
    both = fast + [dict(src="z", start=0.0, end=12.0, tags=["t"], cuts=[])]
    for seed in range(20):
        c, start, _ = B.ClipPicker(both, 120, ROOT, seed=seed).pick("t", 3.0)
        assert c["src"] == "z", seed
    # 重用也要避開
    pk = B.ClipPicker(clips, 120, ROOT)
    pk.at = (500.0, 503.6)
    r = pk.pick_reuse("t", 3.6)
    assert r and not B.cut_violations(r[0], r[1], 3.6), r

    shots = [dict(kind="video", line=77, src="x", start=0.0, frames=109, clip=clip),
             dict(kind="video", line=78, src="x", start=3.6, frames=109, clip=clip),
             dict(kind="video", line=79, src="x", start=0.0, frames=109, clip={"src": "x"}),
             dict(kind="image", line=80, img="a", frames=109)]
    errs, n = B.check_cuts(shots)
    assert n == 2 and len(errs) == 1 and "句77" in errs[0] and "3.50" in errs[0], errs
    print("全部通過")


if __name__ == "__main__":
    main()
