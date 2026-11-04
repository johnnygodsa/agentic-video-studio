"""OCR 引擎切換(T4):OCR_ENGINE=win|rapid、RapidOCR 輸出格式轉換、rapid 未安裝時退回 win、clip_scan 走 assets_lib.ocr_batch。
python -X utf8 pipeline\\tests\\test_ocr_engine.py      (pytest 也能跑;真跑 RapidOCR 的測試在沒裝 rapidocr-onnxruntime 時 skip)"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import assets_lib as AL  # noqa: E402
import clip_scan as CS  # noqa: E402

# RapidOCR 輸出:[[四角點, 文字, 信心], …]
FAKE = [
    [[[100, 400], [500, 402], [498, 440], [101, 438]], "Press Start", "0.98"],
    [[[200.4, 480], [680, 480], [680, 530.6], [200.4, 530.6]], "官方宣布 2027", "0.95"],
    [[[0, 0], [10, 0], [10, 10], [0, 10]], "  ", "0.5"],         # 空白行要丟掉
]


@contextlib.contextmanager
def engine(value, fake=None, missing=False):
    """暫設 OCR_ENGINE / 假的 RapidOCR / 假裝沒裝 rapidocr_onnxruntime;結束還原"""
    old_env = os.environ.get("OCR_ENGINE")
    old_rapid, old_warned, old_mod = AL._rapid, set(AL._warned), sys.modules.get("rapidocr_onnxruntime", "absent")
    if value is None:
        os.environ.pop("OCR_ENGINE", None)
    else:
        os.environ["OCR_ENGINE"] = value
    AL._warned.clear()
    if fake is not None:
        AL._rapid = lambda img: (fake, [0, 0, 0])
        sys.modules.setdefault("rapidocr_onnxruntime", type(sys)("rapidocr_onnxruntime"))   # 讓 import 檢查過關
    if missing:
        sys.modules["rapidocr_onnxruntime"] = None            # import 會丟 ImportError
    try:
        yield
    finally:
        if old_env is None:
            os.environ.pop("OCR_ENGINE", None)
        else:
            os.environ["OCR_ENGINE"] = old_env
        AL._rapid = old_rapid
        AL._warned.clear()
        AL._warned.update(old_warned)
        if old_mod == "absent":
            sys.modules.pop("rapidocr_onnxruntime", None)
        else:
            sys.modules["rapidocr_onnxruntime"] = old_mod


def test_default_by_platform_and_switch():
    real = AL._default_engine
    try:
        for name, want in (("nt", "win"), ("posix", "rapid")):
            real_name, AL.os.name = AL.os.name, name        # 只在這一小段暫改,避免影響 pathlib 以外的東西
            try:
                with engine(None, fake=FAKE):
                    assert AL.ocr_engine() == want, (name, AL.ocr_engine())
                    os.environ["OCR_ENGINE"] = "rapid" if want == "win" else "win"      # 環境變數覆蓋預設
                    assert AL.ocr_engine() == ("rapid" if want == "win" else "win")
            finally:
                AL.os.name = real_name
    finally:
        AL._default_engine = real
    with engine("win", fake=FAKE):
        assert AL.ocr_engine() == "win"
    with engine("RAPID ", fake=FAKE):
        assert AL.ocr_engine() == "rapid"
    with engine("tesseract", fake=FAKE):
        try:
            AL.ocr_engine()
        except ValueError:
            pass
        else:
            raise AssertionError("未知引擎要丟 ValueError")


def test_rapid_format_conversion():
    with engine("rapid", fake=FAKE):
        out = AL.ocr("whatever.png")
    assert [ln["text"] for ln in out] == ["Press Start", "官方宣布 2027"]
    for ln in out:
        assert set(ln) == {"text", "words"}
        for w in ln["words"]:
            assert set(w) == {"t", "x", "y", "w", "h"} and all(isinstance(w[k], int) for k in "xywh")
    l1, l2 = out
    assert [w["t"] for w in l1["words"]] == ["Press", "Start"]
    assert [w["t"] for w in l2["words"]] == ["官", "方", "宣", "布", "2027"]
    # 詞框落在行框內、由左到右、不重疊
    for ln, (x0, x1, y0, h) in ((l1, (100, 500, 400, 40)), (l2, (200, 680, 480, 50))):
        xs = [(w["x"], w["x"] + w["w"]) for w in ln["words"]]
        assert xs[0][0] >= x0 - 1 and xs[-1][1] <= x1 + 1, xs
        assert all(a[1] <= b[0] + 1 for a, b in zip(xs, xs[1:])), xs
        assert all(w["y"] == y0 and w["h"] == h for w in ln["words"]), ln
    assert AL._rapid_to_lines(None) == [] and AL._rapid_to_lines([]) == []


def test_s2t_on_by_default_and_switch():
    fake = [[[[0, 0], [100, 0], [100, 20], [0, 20]], "玩家评价两极 预告片", "0.9"]]
    old = os.environ.get("OCR_S2T")
    try:
        os.environ.pop("OCR_S2T", None)
        with engine("rapid", fake=fake):
            out = AL.ocr("a.png")
        assert out[0]["text"] == "玩家評價兩極 預告片", out
        assert [w["t"] for w in out[0]["words"]][:2] == ["玩", "家"]
        # 繁體輸入不被 OpenCC 的詞級轉換改壞(宣布 -> 宣佈、台灣 -> 臺灣),簡體詞照轉
        for src, want in (("官方宣布 台灣 皇后", "官方宣布 台灣 皇后"), ("台湾 头发 后面 为什么", "台灣 頭髮 後面 為什麼"),
                          ("Press Start 2027", "Press Start 2027")):
            with engine("rapid", fake=[[[[0, 0], [9, 0], [9, 9], [0, 9]], src, "0.9"]]):
                assert AL.ocr("a.png")[0]["text"] == want, (src, AL.ocr("a.png")[0]["text"])
        os.environ["OCR_S2T"] = "0"
        with engine("rapid", fake=fake):
            assert AL.ocr("a.png")[0]["text"] == "玩家评价两极 预告片"
        os.environ.pop("OCR_S2T", None)
        with engine("rapid", fake=FAKE):        # 繁體/英文不被改壞
            assert AL.ocr("a.png")[1]["text"] == "官方宣布 2027"
    finally:
        if old is None:
            os.environ.pop("OCR_S2T", None)
        else:
            os.environ["OCR_S2T"] = old


def test_s2t_missing_opencc_warns_and_passes_through():
    real_s2t = AL._s2t
    real_mod = sys.modules.get("opencc", "absent")
    AL._s2t = None
    sys.modules["opencc"] = None
    buf = io.StringIO()
    try:
        with engine("rapid", fake=[[[[0, 0], [9, 0], [9, 9], [0, 9]], "预告", "0.9"]]), contextlib.redirect_stderr(buf):
            assert AL.ocr("a.png")[0]["text"] == "预告"
            AL.ocr("a.png")
    finally:
        AL._s2t = real_s2t
        if real_mod == "absent":
            sys.modules.pop("opencc", None)
        else:
            sys.modules["opencc"] = real_mod
    assert buf.getvalue().count("[assets_lib.ocr] 警告") == 1 and "opencc" in buf.getvalue(), repr(buf.getvalue())


def test_rapid_rec_option_validation_and_swap():
    try:
        import rapidocr_onnxruntime as ro
    except ImportError:
        raise unittest.SkipTest("rapidocr-onnxruntime 未安裝")
    real_env = {k: os.environ.get(k) for k in ("OCR_RAPID_REC", "OCR_RAPID_KEYS")}
    cands = sorted((Path(ro.__file__).parent / "models").glob("*_rec_infer.onnx"))
    if not cands:
        raise unittest.SkipTest("rapidocr-onnxruntime 套件內找不到 *_rec_infer.onnx")
    model = cands[0]
    old_rapid = AL._rapid
    try:
        AL._rapid = None
        os.environ["OCR_RAPID_REC"] = "/no/such/model.onnx"
        try:
            AL._rapid_engine()
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("模型檔不存在要丟 FileNotFoundError")
        AL._rapid = None
        os.environ["OCR_RAPID_REC"] = str(model)
        os.environ["OCR_RAPID_KEYS"] = "/no/such/keys.txt"
        try:
            AL._rapid_engine()
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("字典檔不存在要丟 FileNotFoundError")
        # 用內建模型當「自訂模型」:機制能換掉 text_recognizer 且仍可辨識(內嵌字元表優先,keys 可省)
        AL._rapid = None
        os.environ.pop("OCR_RAPID_KEYS", None)
        eng = AL._rapid_engine()
        rec = getattr(eng, "text_rec", None) or eng.text_recognizer      # 1.4.x 叫 text_rec,1.2.x 叫 text_recognizer
        assert rec.session.session._model_path == str(model)
    finally:
        AL._rapid = old_rapid
        for k, v in real_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_fallback_to_win_when_not_installed():
    buf = io.StringIO()
    with engine("rapid", missing=True), contextlib.redirect_stderr(buf):
        assert AL.ocr_engine() == "win"
        assert AL.ocr_engine() == "win"
    assert buf.getvalue().count("警告") == 1 and "rapidocr" in buf.getvalue()     # 只警告一次
    with engine("win", missing=True), contextlib.redirect_stderr(io.StringIO()) as e:
        assert AL.ocr_engine() == "win"
    assert e.getvalue() == ""                                                       # 明確選 win 不警告


class _FakeRun:
    """取代 subprocess.run:模擬 ocr_win.ps1 / ocr_batch.ps1 寫出 json"""
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def __call__(self, cmd, check=True, **kw):
        self.calls.append(cmd)
        Path(cmd[-1]).write_text(json.dumps(self.payload), encoding="utf-8-sig")


def test_win_path_calls_powershell():
    import subprocess
    payload = [{"text": "Hello", "words": [{"t": "Hello", "x": 1, "y": 2, "w": 3, "h": 4}]}]
    fake, real = _FakeRun(payload), subprocess.run
    subprocess.run = fake
    try:
        with engine("win", fake=FAKE):
            assert AL.ocr("a.png", "zh-Hant-TW") == payload
    finally:
        subprocess.run = real
    cmd = fake.calls[0]
    assert cmd[0] == "powershell" and cmd[cmd.index("-File") + 1].endswith("ocr_win.ps1") and "zh-Hant-TW" in cmd


def test_ocr_batch_both_engines():
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "0001.jpg").write_bytes(b"x")
        (d / "0002.jpg").write_bytes(b"x")
        (d / "skip.png").write_bytes(b"x")
        with engine("rapid", fake=FAKE):
            r = AL.ocr_batch(d)
        assert r == {"0001.jpg": "Press Start\n官方宣布 2027", "0002.jpg": "Press Start\n官方宣布 2027"}
        fake, real = _FakeRun({"0001.jpg": "WIN"}), subprocess.run
        subprocess.run = fake
        try:
            with engine("win"):
                assert AL.ocr_batch(d) == {"0001.jpg": "WIN"}
        finally:
            subprocess.run = real
        assert fake.calls[0][fake.calls[0].index("-File") + 1].endswith("ocr_batch.ps1")


def test_clip_scan_uses_assets_lib_not_powershell():
    from PIL import Image
    assert not hasattr(CS, "OCR_PS1")
    src_text = (ROOT / "pipeline" / "clip_scan.py").read_text(encoding="utf-8")
    assert "powershell" not in src_text and "ocr_batch.ps1" not in src_text
    texts = {"0001.jpg": "", "0002.jpg": "SUBSCRIBE FOR MORE", "0003.jpg": "", "0004.jpg": "", "0005.jpg": "",
             "0006.jpg": "", "0007.jpg": ""}

    def fake_run(cmd, check=True, **kw):      # 取代 ffmpeg:在 work 資料夾寫 7 張灰圖(第 1 張全黑)
        work = Path(cmd[-1]).parent
        for i in range(1, 8):
            Image.new("L", (64, 36), 0 if i == 1 else 128).save(work / f"{i:04d}.jpg")

    real_run, real_ocr, real_tmp = CS.subprocess.run, AL.ocr_batch, CS.P.TMP
    with tempfile.TemporaryDirectory() as td:
        CS.subprocess.run, CS.P.TMP = fake_run, Path(td)
        AL.ocr_batch = lambda folder: texts
        try:
            r = CS.scan("x", min_run=3)
        finally:
            CS.subprocess.run, AL.ocr_batch, CS.P.TMP = real_run, real_ocr, real_tmp
    # 第 1 格過暗、第 2 格字卡 -> 第 3~7 格連續乾淨(5 秒,兩端內縮 0.5)
    assert r["bad"] == {"亮度": 1, "文字": 1}, r
    assert [[a, b] for a, b, _ in r["runs"]] == [[2.5, 6.5]], r


def test_real_rapid_smoke():
    """真跑 RapidOCR(wheel 內含模型):合成一張英文+中文字幕圖,要認出英文字卡"""
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except ImportError:
        raise unittest.SkipTest("rapidocr-onnxruntime 未安裝")
    from PIL import Image, ImageDraw
    with tempfile.TemporaryDirectory() as td:
        im = Image.new("RGB", (960, 540), (40, 40, 60))
        d = ImageDraw.Draw(im)
        d.text((40, 30), "Press Start to continue", font=AL.font(30), fill=(255, 255, 255))
        d.text((200, 450), "這個遊戲的劇情真的很扯", font=AL.font(36, True), fill=(255, 255, 255))
        p = Path(td) / "a.jpg"
        im.save(p)
        with engine("rapid"):
            AL._rapid = None
            out = AL.ocr(p)
            batch = AL.ocr_batch(td)
        txt = "".join(ln["text"] for ln in out)
        assert "Press" in txt and "Start" in txt, txt
        assert sum("一" <= c <= "鿿" for c in txt) >= 6, txt
        assert all(ln["words"] for ln in out)
        assert set(batch) == {"a.jpg"} and "Press" in batch["a.jpg"]


def main():
    skipped = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except unittest.SkipTest as e:
                skipped += 1
                print(f"skip {name}: {e}")
    print("全部通過" + (f"(skip {skipped})" if skipped else ""))


if __name__ == "__main__":
    main()
