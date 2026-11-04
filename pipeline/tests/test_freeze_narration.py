"""凍結只鎖配音文本(freeze.narration_sha)測試:畫面欄位可改、改字/@say 會擋、舊凍結比整檔、board 舊階段名轉換、--freeze 門檻。
假 script.txt 寫在 tmp\\test_freeze_narration\\。python -X utf8 pipeline/tests/test_freeze_narration.py 或 pytest。"""
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import paths as P  # noqa: E402

BASE = P.TMP / "test_freeze_narration"

import board  # noqa: E402
import freeze as FZ  # noqa: E402

SCRIPT = """@title 測試
@say Steam=史迪姆
# 開場
img:a|這是第一句 Steam 很好。 ;; {"hl":"第一句"}
card:大字 小字|這是第二句。
img:b|這是第三句。 ;; {"pause":0.5,"note":"先看這裡"}
"""


class Env:
    def __enter__(self):
        shutil.rmtree(BASE, ignore_errors=True)
        BASE.mkdir(parents=True)
        self.sp, self.fp, self.rp = BASE / "script.txt", BASE / "freeze.json", BASE / "tts_review.json"
        self.tts = BASE / "tts"
        self.tts.mkdir()
        (self.tts / "001.key").write_text("k1|qc7")
        self.old = (FZ.script_path, FZ.freeze_path, FZ.review_path, P.tts_dir, P.build_dir)
        FZ.script_path, FZ.freeze_path, FZ.review_path = (lambda tag: self.sp), (lambda tag: self.fp), (lambda tag: self.rp)
        P.tts_dir, P.build_dir = (lambda tag, engine=None: self.tts), (lambda tag: BASE)
        self.sp.write_text(SCRIPT, encoding="utf-8")
        return self

    def __exit__(self, *exc):
        FZ.script_path, FZ.freeze_path, FZ.review_path, P.tts_dir, P.build_dir = self.old

    def review(self, **over):
        rec = dict(script_sha256=FZ.sha256(self.sp), narration_sha=FZ.narration_sha("t"), at="2026-10-26T10:00:00", units=3,
                   failed=[], no_qc=[], timing_errors=[], tts_keys_sha=FZ.tts_keys_sha("t", "cosy3"), engine="cosy3")
        rec.update(over)
        self.rp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")


def test_lines_use_say():
    with Env():
        assert FZ.narration_lines("t") == ["這是第一句 史迪姆 很好。", "這是第二句。", "這是第三句。"]


def test_screen_fields_dont_change_sha():
    with Env() as env:
        base = FZ.narration_sha("t")
        env.review()
        FZ.freeze("t", "測試")
        assert FZ.check("t") is None
        env.sp.write_text(SCRIPT.replace("img:a", "img:zzz").replace('"hl":"第一句"', '"hl":"很好","kit":[{"type":"badge","text":"X"}]')
                          .replace("card:大字 小字", "card:另一張").replace('"pause":0.5,"note":"先看這裡"', '"pause":1.2,"note":"換備註","f":3'),
                          encoding="utf-8")
        assert FZ.sha256(env.sp) != json.loads(env.fp.read_text(encoding="utf-8"))["sha256"]   # 整檔值確實變了
        assert FZ.narration_sha("t") == base and FZ.check("t") is None
        assert not FZ.review_problems("t")   # review 的 narration_sha 也相符


def test_text_or_say_change_aborts():
    with Env() as env:
        env.review()
        FZ.freeze("t", "測試")
        env.sp.write_text(SCRIPT.replace("這是第二句", "這是第二句話"), encoding="utf-8")
        msg = FZ.check("t")
        assert msg and "配音文本已改" in msg and "--refreeze" in msg
        env.sp.write_text(SCRIPT.replace("@say Steam=史迪姆", "@say Steam=斯蒂姆"), encoding="utf-8")   # 只改 @say
        assert FZ.check("t") and "配音文本已改" in FZ.check("t")
        assert any("配音文本" in x for x in FZ.review_problems("t"))


def test_legacy_freeze_uses_whole_file_sha():
    with Env() as env:
        env.review()
        rec = FZ.freeze("t", "測試")
        rec.pop("narration_sha")   # 舊凍結:沒有 narration_sha
        env.fp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        assert FZ.check("t") is None
        env.sp.write_text(SCRIPT.replace('"hl":"第一句"', '"hl":"很好"'), encoding="utf-8")   # 只改畫面欄位也要擋(舊規則)
        assert FZ.check("t") and "配音文本已改" in FZ.check("t")
        # 舊 tts_review(無 narration_sha)同樣比 script_sha256
        env.review()
        rv = json.loads(env.rp.read_text(encoding="utf-8"))
        rv.pop("narration_sha")
        rv["script_sha256"] = "0" * 64
        env.rp.write_text(json.dumps(rv), encoding="utf-8")
        assert any("不符" in x for x in FZ.review_problems("t"))


def test_legacy_stages():
    old_env = os.environ.get("CV_BOARD_DIR")
    os.environ["CV_BOARD_DIR"] = str(BASE / "board")   # 只在本測試內改,免得影響同批其他測試的 board 目錄
    try:
        _legacy_stages()
    finally:
        if old_env is None:
            os.environ.pop("CV_BOARD_DIR", None)
        else:
            os.environ["CV_BOARD_DIR"] = old_env


def _legacy_stages():
    shutil.rmtree(BASE / "board", ignore_errors=True)
    (BASE / "board").mkdir(parents=True)
    old = {"段1查證": "A資料", "段1文案": "B文案", "聽審中": "C配音", "段2素材": "D畫面", "段2樣片": "D畫面", "段2成片": "E自審", "段3改版": "改版"}
    assert board.LEGACY_STAGES == old
    assert board.STAGES == ("A資料", "B文案", "C配音", "已凍結", "D畫面", "E自審", "已排程", "改版", "結案")
    (BASE / "board" / "board.json").write_text(json.dumps({f"t{i}": {"stage": k} for i, k in enumerate(old)}, ensure_ascii=False), encoding="utf-8")
    d = board.load()
    assert [d[f"t{i}"]["stage"] for i in range(len(old))] == list(old.values())
    assert board.set_stage("n", "段2成片")["stage"] == "E自審" and board.update("n", stage="聽審中")["stage"] == "C配音"
    assert board.get("t0")["stage"] == "A資料"
    try:
        board.update("n", stage="亂寫")
        raise AssertionError("不合法 stage 應報錯")
    except ValueError:
        pass


def test_make_version_freeze_flag():
    """--freeze 只能配 --tts-review;make_version 的 write_tts_review 寫 narration_sha(import 失敗 = Linux 缺 GPU 鎖,略過)。"""
    try:
        import make_version as MV
    except SystemExit:
        return
    with Env() as env:
        (BASE / "tts_qc.json").write_text(json.dumps(dict(units=3, failed=[], no_qc=[])), encoding="utf-8")
        _, rec = MV.write_tts_review("t", "cosy3")
        assert rec["narration_sha"] == FZ.narration_sha("t") and not FZ.review_problems("t")
        env.sp.write_text(SCRIPT.replace('"hl":"第一句"', '"hl":"x"'), encoding="utf-8")
        assert not FZ.review_problems("t")   # 畫面欄位改了 review 仍有效


def test_all_sites_agree_on_narration_sha():
    """凍結 sha 單一來源:freeze.check / review_problems / tts_script --verify / make_version.write_tts_review / pack_for_colab
    對同一片的判斷一致(畫面欄位改 = 全部仍相符;改字 = 全部不符)。"""
    import tts_script as TS
    with Env() as env:
        env.review()
        rec = FZ.freeze("t", "測試")
        sha = FZ.narration_sha("t")
        assert rec["narration_sha"] == sha and FZ.text_same("t", rec)
        import hashlib
        assert sha == hashlib.sha256(chr(10).join(say for _, say in TS.script_lines("t")).encode("utf-8")).hexdigest()
        outs = []

        def verdicts():
            return (FZ.check("t") is None, not FZ.review_problems("t"), TS.verify("t", out=outs.append) == 0)
        assert verdicts() == (True, True, True)
        env.sp.write_text(SCRIPT.replace("img:a", "img:zzz"), encoding="utf-8")   # 只改畫面
        assert FZ.narration_sha("t") == sha and verdicts() == (True, True, True)
        env.sp.write_text(SCRIPT.replace("這是第三句", "這是第三句話"), encoding="utf-8")   # 改字
        assert FZ.narration_sha("t") != sha and verdicts() == (False, False, False)
        try:
            from colab import pack_for_colab as PK
        except (ImportError, SystemExit):
            return
        assert PK.refreeze_reason("t") is not None   # 文本與凍結不符 -> 放行重錄的理由
        env.sp.write_text(SCRIPT, encoding="utf-8")
        assert PK.refreeze_reason("t") is None


TESTS = [test_lines_use_say, test_screen_fields_dont_change_sha, test_text_or_say_change_aborts,
         test_legacy_freeze_uses_whole_file_sha, test_legacy_stages, test_make_version_freeze_flag,
         test_all_sites_agree_on_narration_sha]

if __name__ == "__main__":
    bad = 0
    for fn in TESTS:
        try:
            fn()
            print("OK  ", fn.__name__)
        except Exception as e:  # noqa: BLE001
            bad += 1
            print("FAIL", fn.__name__, type(e).__name__, e)
    shutil.rmtree(BASE, ignore_errors=True)
    sys.exit(1 if bad else 0)
