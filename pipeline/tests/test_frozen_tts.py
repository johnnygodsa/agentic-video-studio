"""凍結後禁新合成(PLAN_TTS_FLOW T4)測試:build.tts_all(frozen=<tag>) 快取未命中即逐句列出並 exit 2。
假 wav/.key/.qc.json 寫在 tmp\\test_frozen_tts\\;讀音表用替身(不碰 cosy_pron.json);合成函式全部 mock,不需顯示卡。
python -X utf8 pipeline/tests/test_frozen_tts.py(或 -m pytest)"""
import contextlib
import io
import json
import shutil
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import build as B  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import tts_key as TK  # noqa: E402

TMP = PIPE.parent / "tmp" / "test_frozen_tts"
SAY = "這款遊戲的主角很帥。"
SAY2 = "這款遊戲的配角很帥。"
CMD = ["py", "tts_cosy3.py", "--ref", "ref_b.wav", "--speed", "1.18"]
PRON = {"遊戲": "遊[x][ì]", "主角": "主[j][iǎo]"}
TAG = "片X"


class Synthed(Exception):
    pass


def mk_cache(name, engine, say=SAY, rec_extra=None):
    d = TMP / name / "tts"
    shutil.rmtree(d.parent, ignore_errors=True)
    d.mkdir(parents=True)
    ext = "mp3" if engine == "edge" else "wav"
    raw = d / f"001.{ext}"
    if engine == "edge":
        raw.write_bytes(b"fake")
        raw.with_suffix(".key").write_text(TK.audio_key("edge", TK.cmd_sig(None), "V", "R", say))
        return d
    B.write_wav(raw, [b"\0" * 4800 * 4])
    key = TK.full_key(TK.audio_key(engine, TK.cmd_sig(CMD), "V", "R", say), B.QC_VER)
    raw.with_suffix(".key").write_text(key)
    rec = dict(qc_ver=B.QC_VER, key=key, wav_sha1=B.file_sha1(raw), text=say, passed=True, final=False,
               engine=engine, idx=1, **(rec_extra or {}))
    raw.with_suffix(".qc.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return d


def run(d, engine, say, frozen):
    """跑 tts_all(合成/裁切/接檔/報告全 mock);回傳 (exit code 或 None, stdout)。合成被呼叫 -> Synthed。"""
    def boom(*a, **k):
        raise Synthed()
    keep = B._trim_one, B.assemble_line, B._synth_external, B._synth_edge, B.write_qc_report
    B._trim_one, B.assemble_line = (lambda u: u.update(wav=u["raw"])), (lambda ln, td: None)
    B._synth_external = B._synth_edge = boom
    B.write_qc_report = lambda *a, **k: []
    buf, code = io.StringIO(), None
    try:
        with contextlib.redirect_stdout(buf):
            B.tts_all([dict(idx=1, text=say, say=say)], "V", "R", d, engine=engine,
                      tts_cmd=CMD if engine != "edge" else None, frozen=frozen)
    except SystemExit as e:
        code = e.code
    finally:
        B._trim_one, B.assemble_line, B._synth_external, B._synth_edge, B.write_qc_report = keep
    return code, buf.getvalue()


def pron(table):
    class Ctx:
        def __enter__(self):
            self.keep, CT.PRON = CT.PRON, dict(table)

        def __exit__(self, *a):
            CT.PRON = self.keep
    return Ctx()


def test_frozen_unchanged_passes():
    with pron(PRON):
        d = mk_cache("same", "cosy3", rec_extra=dict(pron_hits=CT.pron_hits(SAY)))
        code, out = run(d, "cosy3", SAY, TAG)
    assert code is None and "凍結後禁止" not in out


def test_frozen_text_change_exit2_lists_line():
    with pron(PRON):
        d = mk_cache("text", "cosy3", rec_extra=dict(pron_hits=CT.pron_hits(SAY)))
        code, out = run(d, "cosy3", SAY2, TAG)
    assert code == 2
    assert "句1:文字" in out and "凍結後禁止新合成" in out
    assert f"freeze.py {TAG} --refreeze --reason" in out and "--tts-review" in out


def test_frozen_pron_change_exit2_lists_line():
    with pron(PRON):
        d = mk_cache("pron", "cosy3", rec_extra=dict(pron_hits=CT.pron_hits(SAY)))
    with pron(dict(PRON, 主角="主[j][ué]")):
        code, out = run(d, "cosy3", SAY, TAG)
    assert code == 2 and "句1:讀音表改" in out


def test_frozen_terms_change_exit2():
    tsay = "他在Roblox上做了一款遊戲。"
    keep = CT.TERMS
    try:
        CT.TERMS = {"Roblox": "Roblox"}
        d = mk_cache("terms", "cosy3", say=tsay, rec_extra=dict(term_hits=CT.term_hits(tsay)))
        CT.TERMS = {"Roblox": "Row blocks"}
        code, out = run(d, "cosy3", tsay, TAG)
    finally:
        CT.TERMS = keep
    assert code == 2 and "句1:英文表改" in out


def test_frozen_qc_ver_change_reused():
    """凍結:音檔鍵相符、只有 QC_VER 變 -> 命中沿用,不中止、不合成、不改 .key。"""
    with pron(PRON):
        d = mk_cache("qcver", "cosy3", rec_extra=dict(pron_hits=CT.pron_hits(SAY)))
        key_before = (d / "001.key").read_text()
        keep = B.QC_VER
        B.QC_VER = keep + "-new"
        try:
            code, out = run(d, "cosy3", SAY, TAG)
            assert code is None and "凍結後禁止" not in out
            (d / "001.qc.json").unlink()    # 連紀錄都沒有也一樣沿用
            code, out = run(d, "cosy3", SAY, TAG)
            assert code is None
            # 沒凍結時才會重新檢驗(走到合成)
            try:
                run(d, "cosy3", SAY, None)
                raise AssertionError("未凍結應重新檢驗")
            except Synthed:
                pass
        finally:
            B.QC_VER = keep
    assert (d / "001.key").read_text() == key_before


def test_frozen_no_cache_new_line():
    d = TMP / "empty" / "tts"
    shutil.rmtree(d.parent, ignore_errors=True)
    code, out = run(d, "cosy3", SAY, TAG)
    assert code == 2 and "句1:無快取" in out


def test_not_frozen_still_synthesizes():
    with pron(PRON):
        d = mk_cache("free", "cosy3", rec_extra=dict(pron_hits=CT.pron_hits(SAY)))
    try:
        run(d, "cosy3", SAY2, None)
        raise AssertionError("沒有凍結時文字改應走到合成")
    except Synthed:
        pass


def test_frozen_edge_text_change():
    d = mk_cache("edge", "edge")
    assert run(d, "edge", SAY, TAG)[0] is None
    code, out = run(d, "edge", SAY2, TAG)
    assert code == 2 and "句1:文字" in out


def test_no_synth_path_unchanged():
    """--no-synth 的中止訊息與 exit(字串)不變,先於凍結檢查。"""
    d = TMP / "nosynth" / "tts"
    shutil.rmtree(d.parent, ignore_errors=True)
    keep = B._trim_one, B.assemble_line
    B._trim_one, B.assemble_line = (lambda u: u.update(wav=u["raw"])), (lambda ln, td: None)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            B.tts_all([dict(idx=1, text=SAY, say=SAY)], "V", "R", d, engine="cosy3", tts_cmd=CMD, no_synth=True, frozen=TAG)
        raise AssertionError("應中止")
    except SystemExit as e:
        assert isinstance(e.code, str) and e.code.startswith("--no-synth")
    finally:
        B._trim_one, B.assemble_line = keep


if __name__ == "__main__":
    tests = [(n, f) for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for n, f in tests:
        f()
        print("ok", n)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"{len(tests)} passed")
