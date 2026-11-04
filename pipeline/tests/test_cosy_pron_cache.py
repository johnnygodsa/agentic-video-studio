"""cosy3 讀音表變更 -> 快取失效測試(假 wav/.key/.qc.json 寫在 tmp\\test_cosy_pron_cache\\;讀音表用替身,不碰 cosy_pron.json)。
python -X utf8 pipeline/tests/test_cosy_pron_cache.py(或 -m pytest;不需顯示卡,不合成)"""
import json
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import build as B  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import tts_key as TK  # noqa: E402

TMP = PIPE.parent / "tmp" / "test_cosy_pron_cache"
SAY = "這款遊戲的主角很帥。"
CMD = ["py", "tts_cosy3.py", "--ref", "ref_b.wav", "--speed", "1.18"]
QC_VER = B.QC_VER
OLD_PRON = {"遊戲": "遊[x][ì]", "主角": "主[j][iǎo]"}


@contextmanager
def pron(table):
    keep = CT.PRON
    CT.PRON = dict(table)
    try:
        yield
    finally:
        CT.PRON = keep


@contextmanager
def terms(table):
    keep = CT.TERMS
    CT.TERMS = dict(table)
    try:
        yield
    finally:
        CT.TERMS = keep


TSAY = "他在Roblox上做了一款遊戲。"
OLD_TERMS = {"Roblox": "Roblox"}   # 舊寫法(直接唸英文);新寫法 Row blocks


def engine_text(say):
    """模擬舊紀錄的 engine_text(token 原樣保留,其餘字不影響比對)。"""
    return CT.pron_text(say)[0]


def mk_cache(tag, engine, rec_extra, say=SAY):
    """tts 目錄放一句 001.wav + 正確的 .key + 目前 QC 版本的 .qc.json(rec_extra 決定讀音欄位)。"""
    d = TMP / tag / "tts"
    shutil.rmtree(d.parent, ignore_errors=True)
    d.mkdir(parents=True)
    raw = d / "001.wav"
    B.write_wav(raw, [b"\0" * 4800 * 4])
    key = TK.full_key(TK.audio_key(engine, TK.cmd_sig(CMD), "V", "R", say), QC_VER)
    raw.with_suffix(".key").write_text(key)
    rec = dict(qc_ver=QC_VER, key=key, wav_sha1=B.file_sha1(raw), text=say, passed=True, final=False, **rec_extra)
    raw.with_suffix(".qc.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return d



def run_tts(d, engine, say=SAY):
    """no_synth=True:沒命中就 SystemExit(不動音檔);命中則回傳該句的品管紀錄(裁切/接檔換成空操作)。"""
    lines = [dict(idx=1, text=say, say=say)]
    keep = B._trim_one, B.assemble_line
    B._trim_one, B.assemble_line = (lambda u: u.update(wav=u["raw"])), (lambda ln, td: None)
    try:
        B.tts_all(lines, "V", "R", d, engine=engine, tts_cmd=CMD, no_synth=True)
    finally:
        B._trim_one, B.assemble_line = keep
    return lines[0]["units"][0]


def hit_say(d, say):
    try:
        run_tts(d, "cosy3", say)
        return True
    except SystemExit:
        return False


def hit(d, engine):
    try:
        run_tts(d, engine)
        return True
    except SystemExit:
        return False


# ------------------------------------------------------------ tts_cosy_text
def test_pron_changed_by_hits():
    with pron(OLD_PRON):
        rec = dict(pron_hits=CT.pron_hits(SAY))
        assert rec["pron_hits"] == OLD_PRON
        assert not CT.pron_changed(rec, SAY)
    with pron(dict(OLD_PRON, 主角="主[j][ué]")):
        assert CT.pron_changed(rec, SAY)
    with pron({"遊戲": "遊[x][ì]"}):  # 刪掉一條
        assert CT.pron_changed(rec, SAY)
    with pron(dict(OLD_PRON, 帥="[sh][uài]")):  # 新增一條且這句有用到
        assert CT.pron_changed(rec, SAY)
    with pron(dict(OLD_PRON, 回血="回[x][iě]")):  # 新增一條但這句沒用到
        assert not CT.pron_changed(rec, SAY)


def test_pron_changed_by_engine_text():
    with pron(OLD_PRON):
        rec = dict(engine_text=engine_text(SAY))
        assert not CT.pron_changed(rec, SAY)
    with pron(dict(OLD_PRON, 主角="主[j][ué]")):
        assert CT.pron_changed(rec, SAY)
    with pron(dict(OLD_PRON, 回血="回[x][iě]")):
        assert not CT.pron_changed(rec, SAY)


def test_no_pron_fields_is_consistent():
    with pron(dict(OLD_PRON, 主角="主[j][ué]")):
        assert not CT.pron_changed(dict(text=SAY), SAY)
        assert not CT.pron_changed(None, SAY)


def test_audit_cache():
    with pron(OLD_PRON):
        d = mk_cache("audit", "cosy3", dict(engine="cosy3", idx=1, engine_text=engine_text(SAY)))
        assert CT.audit_cache(d) == []
    with pron(dict(OLD_PRON, 主角="主[j][ué]")):
        assert CT.audit_cache(d) == [("1", SAY)]


def test_terms_changed_by_hits():
    with terms(OLD_TERMS):
        rec = dict(term_hits=CT.term_hits(TSAY))
        assert rec["term_hits"] == {"Roblox": "Roblox"} and not CT.terms_changed(rec, TSAY)
    with terms({"Roblox": "Row blocks"}):
        assert CT.terms_changed(rec, TSAY)
    with terms(dict(OLD_TERMS, Steam="Steam 平台")):   # 新增一條但這句沒用到
        assert not CT.terms_changed(rec, TSAY)
    with terms({}):                                    # 刪掉一條
        assert CT.terms_changed(rec, TSAY)


def test_terms_changed_by_engine_text():
    # 舊紀錄只有 engine_text:比英文單字序列(去拼音 token)
    with terms(OLD_TERMS):
        rec = dict(engine_text=engine_text(TSAY))
        assert not CT.terms_changed(rec, TSAY)
    with terms({"Roblox": "Row blocks"}):
        assert CT.terms_changed(rec, TSAY)
    with terms(dict(OLD_TERMS, Steam="Steam 平台")):
        assert not CT.terms_changed(rec, TSAY)
    # 數字/標點正規化、拼音 token、簡體轉換不造成誤判
    say = "2022年的《Game Pass》賣了530萬份，遊戲好玩。"
    with pron(OLD_PRON), terms({"Game Pass": "Game Pass"}):
        r2 = dict(engine_text="二零二二年的Game Pass卖了五百三十万份，游[x][ì]好玩。")
        assert not CT.terms_changed(r2, say)
        assert not CT.terms_changed(dict(text=say), say) and not CT.terms_changed(None, say)


def test_audit_cache_terms():
    with terms(OLD_TERMS):
        d = mk_cache("audit_t", "cosy3", dict(engine="cosy3", idx=1, term_hits=CT.term_hits(TSAY)), say=TSAY)
        assert CT.audit_cache(d) == []
    with terms({"Roblox": "Row blocks"}):
        assert CT.audit_cache(d) == [("1", TSAY)]


# ------------------------------------------------------------ build.tts_all
def test_tts_all_cosy3_unchanged_hits():
    with pron(OLD_PRON):
        d = mk_cache("same", "cosy3", dict(engine="cosy3", engine_text=engine_text(SAY)))
        u = run_tts(d, "cosy3")
        assert u["qc"] is not None


def test_tts_all_cosy3_changed_rerecords():
    with pron(OLD_PRON):
        d = mk_cache("changed", "cosy3", dict(engine="cosy3", pron_hits=CT.pron_hits(SAY)))
    with pron(dict(OLD_PRON, 主角="主[j][ué]")):
        assert not hit(d, "cosy3")


def test_tts_all_cosy3_old_record_without_fields_hits():
    d = mk_cache("legacy", "cosy3", dict(engine="cosy3"))
    with pron(dict(OLD_PRON, 主角="主[j][ué]")):
        assert hit(d, "cosy3")


def test_tts_all_cosy3_terms_changed_rerecords():
    with terms(OLD_TERMS):
        d = mk_cache("terms", "cosy3", dict(engine="cosy3", term_hits=CT.term_hits(TSAY)), say=TSAY)
        assert hit_say(d, TSAY)
    with terms({"Roblox": "Row blocks"}):
        assert not hit_say(d, TSAY)
    with terms(dict(OLD_TERMS, Steam="Steam 平台")):
        assert hit_say(d, TSAY)


def test_tts_all_chattts_unaffected():
    with pron(OLD_PRON):
        d = mk_cache("chattts", "chattts", dict(engine_text=engine_text(SAY), pron_hits=CT.pron_hits(SAY)))
    with pron(dict(OLD_PRON, 主角="主[j][ué]")):
        assert hit(d, "chattts")


if __name__ == "__main__":
    tests = [(n, f) for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for n, f in tests:
        f()
        print("ok", n)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"{len(tests)} passed")
