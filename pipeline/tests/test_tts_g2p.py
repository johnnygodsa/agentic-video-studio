"""tts_g2p(g2pW 第三意見,T3)測試:用假的 g2pW 預測器,不載模型、不需顯示卡、不連網。
涵蓋:拼音/注音/標注 -> tone3 轉換、predict 只輸出規則收的多音字(含位置)、規則表讀音(expected)、不一致判定(含輕聲寬鬆)、
模型不可用退回 None(只警告一次、不丟例外)、聽審頁旗標、準確率報告。
需要 pypinyin(單字預設讀音,如「着」「的」);沒裝就略過。
python -X utf8 pipeline/tests/test_tts_g2p.py(或 -m pytest;沒裝 pytest 時直接執行,跟其他 tests 一樣)"""
import contextlib
import io
import os
import sys
import threading
import time
from pathlib import Path

PIPE =Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import tts_g2p as G  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import listen_page as LP  # noqa: E402

try:
    import pypinyin  # noqa: F401
    HAVE_PY = True
except ImportError:
    HAVE_PY = False


class FakeG2PW:
    """假的 G2PWConverter:字 -> 讀音 dict(沒列的字回 None,同真的非中文字);可指定整句覆寫 {(句, 位置): 讀音}。
    輸出格式可切換 pinyin(hong2)/ 注音(ㄏㄨㄥ2)。"""

    def __init__(self, table=None, override=None, fmt="pinyin"):
        self.table, self.override, self.fmt, self.calls = table or {}, override or {}, fmt, []

    def __call__(self, sentences):
        self.calls.append(list(sentences))
        out = []
        for s in sentences:
            row = []
            for i, c in enumerate(s):
                row.append(self.override.get((s, i), self.table.get(c)))
            out.append(row)
        return out


def reset():
    G.set_converter(None)


# ------------------------------------------------------------ 拼音格式轉換
def test_norm_py_formats():
    same = ["zhang3", "zhǎng", "ㄓㄤˇ", "ㄓㄤ3", "[zh][ǎng]"]
    assert {G.norm_py(x) for x in same} == {"zhang3"}
    assert {G.norm_py(x) for x in ["hong2", "hóng", "ㄏㄨㄥˊ", "ㄏㄨㄥ2"]} == {"hong2"}
    assert {G.norm_py(x) for x in ["de5", "˙ㄉㄜ", "ㄉㄜ˙", "[d][e]", "de"]} == {"de5"}
    assert G.norm_py("[x][uè]") == G.norm_py("xue4") == G.norm_py("ㄒㄩㄝˋ") == "xue4"
    assert G.norm_py("[l][iǎo]") == "liao3" and G.norm_py("[w][éi]") == "wei2" and G.norm_py("[y][ì]") == "yi4"
    assert G.norm_py("lǜ") == G.norm_py("lv4") == G.norm_py("lü4") == G.norm_py("ㄌㄩˋ") == "lv4"
    assert G.norm_py("ㄓ") == "zhi1" and G.norm_py("ㄧㄠˋ") == "yao4" and G.norm_py("ㄨㄥ") == "weng1"
    assert G.norm_py("ㄍㄨㄣˇ") == "gun3" and G.norm_py("ㄉㄧㄡ") == "diu1" and G.norm_py("ㄐㄩㄥ") == "jiong1"
    assert G.norm_py("") is None and G.norm_py(None) is None and G.norm_py("???") is None


def test_norm_py_matches_pypinyin():
    if not HAVE_PY:
        return
    from pypinyin import Style, pinyin
    n = 0
    for cp in range(0x4E00, 0x9FFF, 7):
        c = chr(cp)
        t3 = pinyin(c, style=Style.TONE3, heteronym=True, neutral_tone_with_five=True)[0]
        bp = pinyin(c, style=Style.BOPOMOFO, heteronym=True)[0]
        tm = pinyin(c, style=Style.TONE, heteronym=True)[0]
        for a, b, m in zip(t3, bp, tm):
            if len(a) <= 1 or a.startswith(("hm", "hng", "ng", "m", "n")) and not a.startswith(("ni", "na", "ne", "nu", "nv", "nao", "nei", "nen", "nan", "nang", "neng", "mi", "ma", "me", "mu", "mo", "mai", "mei", "mao", "mou", "man", "men", "mang", "meng")):
                continue   # 嗯、呣 之類只有聲母的嘆詞,注音寫法特殊,不處理
            exp = G.norm_py(a)
            assert G.norm_py(m) == exp, (c, a, m)
            if not b.startswith("˙"):
                assert G.norm_py(b) == exp, (c, a, b)
            n += 1
    assert n > 500


def test_same_reading_neutral_loose():
    assert G.same_reading("zhang3", "[zh][ǎng]")
    assert not G.same_reading("zhang3", "chang2")
    assert G.same_reading("de5", "de2") and not G.same_reading("de5", "de2", neutral_loose=False)   # 輕聲寬鬆
    assert not G.same_reading("le5", "liao3")                                                       # 不同音節一定不同
    assert G.same_reading("zhang3", "???")                                                          # 解析不了不亂報


# ------------------------------------------------------------ predict
def test_predict_filters_polyphones_and_keeps_positions():
    conv = FakeG2PW({"他": "ta1", "望": "wang4", "著": "zhe5", "遠": "yuan3", "方": "fang1"})
    text = "他望著遠方"   # 原用「看」,2026-11-01 起 看 進 pron_rules,改用不在規則檔的「望」
    assert G.predict(text, conv) == [(2, "著", "zhe5")]            # 他/望/遠/方 不是 pron_rules 的字,不輸出
    assert conv.calls == [[text]]


def test_predict_accepts_bopomofo_and_skips_none():
    conv = FakeG2PW({"血": "ㄒㄧㄝˇ", "條": "ㄊㄧㄠˊ", "還": None}, override={("血條,了還", 3): "˙ㄌㄜ"})
    assert G.predict("血條,了還", conv) == [(0, "血", "xie3"), (3, "了", "le5")]   # 還 沒給讀音(None)-> 略過


def test_predict_many_batches():
    conv = FakeG2PW({"還": "hai2", "給": "gei3"})
    out = G.predict_many(["還有", "給你"], conv)
    assert out == [[(0, "還", "hai2")], [(0, "給", "gei3")]] and len(conv.calls) == 1


# ------------------------------------------------------------ 規則表讀音
def test_expected_sources():
    if not HAVE_PY:
        return
    assert G.expected("這部著作很有名")[2] == ("著", "zhu4", "rule")            # pron_rules 非預設規則
    assert G.expected("他看著遠方發呆")[2] == ("著", "zhe5", "default")          # always 字的預設標注「着」
    assert G.expected("他還有三個問題")[1] == ("還", "hai2", "default")          # 沒命中:model_default
    assert G.expected("我們還給他錢")[2] == ("還", "huan2", "rule")
    e = G.expected("新任執行長說了算")
    assert e[4] == ("長", "zhang3", "pron")                                      # cosy_pron 詞表標注「執行[zh][ǎng]」
    assert 3 not in e and 2 not in e                                              # 詞表裡原字保留的位置(執、行)不輸出
    assert G.expected("他受不了")[3] == ("了", "liao3", "rule")


# ------------------------------------------------------------ 不一致判定
def test_disagreements_flags_only_different_reading():
    if not HAVE_PY:
        return
    ok = FakeG2PW({"著": "zhe5", "還": "hai2"})
    assert G.disagreements("他看著遠方", ok) == []                                 # 一致
    bad = FakeG2PW({"著": "zhu4"})
    d = G.disagreements("他看著遠方", bad)
    assert d == [dict(pos=2, ch="著", rule="zhe5", g2p="zhu4", src="default")]
    # 規則命中非預設讀音,g2pW 給預設 -> 不一致,來源 rule
    d = G.disagreements("我們還給他錢", FakeG2PW({"還": "hai2", "給": "gei3"}))
    assert d == [dict(pos=2, ch="還", rule="huan2", g2p="hai2", src="rule")]
    # 注音輸出同樣能比
    assert G.disagreements("我們還給他錢", FakeG2PW({"還": "ㄏㄨㄢˊ", "給": "ㄍㄟˇ"})) == []
    # 輕聲寬鬆:g2pW 給 de2、規則給 de5(得 的預設)不報;嚴格模式才報
    assert G.disagreements("他覺得很好", FakeG2PW({"得": "de2", "覺": "jue2", "好": "hao3"})) == []
    assert G.disagreements("他覺得很好", FakeG2PW({"得": "de2", "覺": "jue2", "好": "hao3"}), neutral_loose=False)
    # cosy_pron 詞表:規則表給 zhang3,g2pW 給 chang2 -> 不一致,來源 pron
    d = G.disagreements("新任執行長說了算", FakeG2PW({"長": "chang2", "說": "shuo1", "了": "le5"}))
    assert d == [dict(pos=4, ch="長", rule="zhang3", g2p="chang2", src="pron")]


def test_disagreements_uses_unsay_text_positions():
    if not HAVE_PY:
        return
    conv = FakeG2PW({"著": "zhu4"})
    t = "看著"
    assert G.disagreements(t, conv)[0]["pos"] == 1 and conv.calls[-1] == [CT.unsay(t)]


# ------------------------------------------------------------ 模型不可用
def test_unavailable_returns_none_and_warns_once():
    reset()
    old = os.environ.get("G2PW_MODEL_DIR")
    os.environ["G2PW_MODEL_DIR"] = str(PIPE / "__no_such_g2pw_model__")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            assert G.predict("他看著遠方") is None
            assert G.disagreements("他看著遠方") is None
            assert G.predict_many(["a", "b"]) is None
    finally:
        reset()
        if old is None:
            os.environ.pop("G2PW_MODEL_DIR", None)
        else:
            os.environ["G2PW_MODEL_DIR"] = old
    assert buf.getvalue().count("g2pW 不可用") == 1                                # 只警告一次


def test_inference_error_returns_none():
    reset()

    def boom(_):
        raise RuntimeError("onnx failed")
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        assert G.predict("他看著", boom) is None
        assert G.disagreements("他看著", boom) is None
    reset()
    assert "推論失敗" in buf.getvalue()


# ------------------------------------------------------------ 聽審頁
def _rec(idx, **kw):
    return dict(idx=idx, text="他看著遠方", passed=True, **kw)


def test_listen_page_lists_g2p_disagree():
    dis = [dict(pos=2, ch="著", rule="zhe5", g2p="zhu4", src="default")]
    reasons = LP.pick_reasons([_rec(1, g2p_disagree=dis), _rec(2, g2p_disagree=[]), _rec(3)])
    assert set(reasons) == {1}                                                     # 空清單 / 沒欄位 = 不列
    cat, txt = reasons[1][0]
    assert cat == "g2p_disagree" and "著" in txt and "zhe5" in txt and "zhu4" in txt
    assert LP.summarize([], reasons) == {"g2p_disagree": 1}
    assert "g2pW" in LP.card(_rec(1, g2p_disagree=dis), 12.0, reasons[1], "a.mp3")   # 卡片顯示原因
    assert LP.pick_reasons([_rec(4, g2p_disagree=["字串殘缺紀錄"])])[4][0][0] == "g2p_disagree"   # 容忍舊/殘缺格式


# ------------------------------------------------------------ 準確率工具
def test_eval_report_counts():
    if not HAVE_PY:
        return
    sents = ["這部著作很有名", "他看著遠方發呆", "新任執行長說了算", "他受不了了"]
    # g2pW:著作 錯成 zhe5、看著 錯成 zhu4(兩個都有 _verified 答案,規則表對)、受不了 對、執行長 對
    conv = FakeG2PW({"著": "zhe5", "長": "zhang3", "了": "liao3", "說": "shuo1"},
                    override={("他看著遠方發呆", 2): "zhu4", ("他受不了了", 4): "le5"})
    ev = G.evaluate(sents, conv)
    assert ev["n_sent"] == 4 and ev["secs"] >= 0
    by = {(c["text"], c["pos"]): c for c in ev["cases"]}
    assert by[("這部著作很有名", 2)]["ans"] == "zhu4" and by[("這部著作很有名", 2)]["g2p"] == "zhe5"
    md = G.eval_report(ev, sents)
    assert "| **合計** |" in md and "規則表對、g2pW 錯 | 2 |" in md and "g2pW 對、規則表錯 | 0 |" in md
    assert "他看著遠方發呆" in md                                                   # 全語料不一致清單
    # 沒有模型時回 None
    assert G.evaluate(sents, lambda s: (_ for _ in ()).throw(RuntimeError("x"))) is None
    reset()


def test_label_cases_tsv(tmp_path=None):
    import tempfile
    d = Path(tmp_path) if tmp_path else Path(tempfile.mkdtemp())
    f = d / "labels.tsv"
    f.write_text("# 註解\n血條掉了\t0\tㄒㄧㄝˇ\n壞行\n", encoding="utf-8")
    assert G.label_cases(f) == [dict(text="血條掉了", pos=0, ch="血", ans="xie3", src="labels")]


# ------------------------------------------------------------ 批次與背景執行緒(tts_cosy3 用)
BATCH = ["他看著遠方", "他還在", "他看著遠方", "沒有多音字"]


def test_many_same_as_single_one_inference():
    if not HAVE_PY:
        return
    conv = FakeG2PW({"著": "zhu4", "還": "hai2"})
    res = G.disagreements_many(BATCH, conv)
    assert set(res) == set(BATCH) and len(conv.calls) == 1 and len(conv.calls[0]) == 3   # 一次推論、同文字只算一次
    assert res == {t: G.disagreements(t, conv) for t in BATCH}
    assert res["他看著遠方"] and res["他還在"] == []


def test_many_inference_error_all_none():
    def boom(_):
        raise RuntimeError("onnx failed")
    with contextlib.redirect_stderr(io.StringIO()):
        G.set_converter(None)
        assert G.disagreements_many(BATCH, boom) == dict.fromkeys(BATCH)
    reset()


def test_many_compare_error_only_that_sentence():
    if not HAVE_PY:
        return
    conv = FakeG2PW({"著": "zhu4", "還": "hai2"})
    real = G.compare

    def flaky(text, preds, neutral_loose=True):
        if "還" in text:
            raise ValueError("bad")
        return real(text, preds, neutral_loose)
    G.compare = flaky
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            res = G.disagreements_many(BATCH, conv)
    finally:
        G.compare = real
    assert res["他還在"] is None and res["他看著遠方"]


def test_background_same_as_many_and_logs_once():
    if not HAVE_PY:
        return
    conv, logs = FakeG2PW({"著": "zhu4", "還": "hai2"}), []
    res = G.Background(BATCH, logs.append, conv).wait()
    assert res == G.disagreements_many(BATCH, conv)
    assert len(logs) == 1 and "3 句" in logs[0]


def test_background_unavailable_none_and_no_field():
    reset()
    old = os.environ.get("G2PW_MODEL_DIR")
    os.environ["G2PW_MODEL_DIR"] = str(PIPE / "__no_such_g2pw_model__")
    buf, logs = io.StringIO(), []
    try:
        with contextlib.redirect_stderr(buf):
            res = G.Background(BATCH, logs.append).wait()
    finally:
        os.environ.pop("G2PW_MODEL_DIR") if old is None else os.environ.update(G2PW_MODEL_DIR=old)
        reset()
    assert set(res.values()) == {None} and G.record_fields(res, BATCH[0]) == {}
    assert buf.getvalue().count("略過第三意見") == 1 and "有結果 0 句" in logs[0]


def test_background_exception_swallowed():
    real, logs = G.disagreements_many, []

    def boom(*a, **k):
        raise RuntimeError("thread died")
    G.disagreements_many = boom
    try:
        res = G.Background(BATCH, logs.append).wait()
    finally:
        G.disagreements_many = real
    assert res == {} and G.record_fields(res, BATCH[0]) == {} and "thread died" in logs[0]


def test_background_timeout_does_not_hang():
    release, logs = threading.Event(), []

    def slow(_):
        release.wait(10)
        return [[] for _ in BATCH]

    class Short(G.Background):
        JOIN_BASE, JOIN_PER_TEXT = 0.05, 0.0

    bg = Short(BATCH, logs.append, slow)
    t = time.perf_counter()
    res = bg.wait()
    assert res == {} and time.perf_counter() - t < 5 and "逾時" in logs[0]
    assert bg.thread.daemon                                                        # 不擋行程結束
    release.set()
    bg.thread.join(5)
    assert res == {}                                                               # 逾時後才算完也不採用


def test_record_fields_semantics():
    dis = [dict(pos=2, ch="著", rule="zhe5", g2p="zhu4", src="default")]
    res = {"a": dis, "b": [], "c": None}
    assert G.record_fields(res, "a") == {"g2p_disagree": dis}
    assert G.record_fields(res, "b") == {"g2p_disagree": []}                       # 全一致也寫(同舊行為)
    assert G.record_fields(res, "c") == {} and G.record_fields(res, "沒算到") == {}


if __name__ == "__main__":
    n = 0
    for k, fn in list(globals().items()):
        if k.startswith("test_") and callable(fn):
            fn()
            n += 1
    print(f"test_tts_g2p: {n} 項通過")
