"""tts_asr 測試(不載模型、不用顯示卡):介面、多音字位置讀音回查(pron_pos_bad / pron_rule_bad 擴充)、雙辨識重錄判定。
python -X utf8 -m pytest pipeline/tests/test_tts_asr.py;沒裝 pytest 時直接執行(tts_env_chattts 的 python 跑得到
pron_rule_bad 那一項,它會 import tts_chattts)。"""
import contextlib
import importlib
import sys
from concurrent.futures import Future
from pathlib import Path

import numpy as np

try:
    import pytest
except ImportError:  # 沒裝 pytest:只補本檔用到的三個
    class pytest:  # noqa: N801
        class _Skip(Exception):
            pass

        @staticmethod
        @contextlib.contextmanager
        def raises(exc):
            try:
                yield
            except exc:
                return
            raise AssertionError(f"沒有拋出 {exc.__name__}")

        @staticmethod
        def importorskip(name):
            try:
                return importlib.import_module(name)
            except ImportError as e:
                raise pytest._Skip(name) from e

        @staticmethod
        def fail(msg):
            raise AssertionError(msg)

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))

import tts_asr as TA  # noqa: E402


# ------------------------------------------------------------ 介面
def test_parse_spec():
    assert TA.parse_spec("qwen06") == ("qwen06", None)
    assert TA.parse_spec(None) == ("qwen06", None)
    assert TA.parse_spec("fun_nano") == ("fun_nano", None)
    assert TA.parse_spec("whisper:medium") == ("whisper", "medium")
    assert TA.parse_spec("medium") == ("whisper", "medium")  # 舊參數 --asr-model medium
    with pytest.raises(ValueError):
        TA.parse_spec("belle")


def _done(v):
    f = Future()
    f.set_result(v)
    return f


class FakeWorker:
    def __init__(self, table):
        self.table = table

    def submit(self, x):
        return _done(self.table["x"])


class FakeTS:
    def transcribe(self, x):
        return "時間戳辨識的字", [("部長", 0.1, 0.5), ("說", 0.5, 0.7)]


def test_asr_transcribe_text_from_primary_words_from_ts():
    a = object.__new__(TA.ASR)
    a.wh, a.worker, a.ts = None, FakeWorker({"x": "部长说"}), FakeTS()
    text, words = a.transcribe(np.zeros(16000, dtype=np.float32))
    assert text == "部长说"  # 文字用主辨識器
    assert words[0] == ("部長", 0.1, 0.5)  # 字詞時間用時間戳辨識


class FakeFAWorker(FakeWorker):
    def __init__(self, table, words):
        super().__init__(table)
        self.words, self.sent = words, []

    def submit_align(self, x, text):
        self.sent.append(text)
        return _done((self.table["x"], self.words))


def _fa_asr(worker, ts=FakeTS()):
    a = object.__new__(TA.ASR)
    a.wh, a.worker, a.ts, a.fa, a.ts_size = None, worker, ts, True, "small"
    return a


def test_asr_transcribe_words_from_aligner():
    wk = FakeFAWorker({"x": "部长说"}, [["部", 0.1, 0.3], ["长", 0.3, 0.5], ["说", 0.5, 0.7]])
    a = _fa_asr(wk)
    text, words = a.transcribe(np.zeros(16000, dtype=np.float32), "部长说")
    assert text == "部长说" and wk.sent == ["部长说"]
    assert words == [("部", 0.1, 0.3), ("长", 0.3, 0.5), ("说", 0.5, 0.7)] and a.last_ts == "qwen3-fa"


def test_asr_transcribe_aligner_fallback():
    a = _fa_asr(FakeFAWorker({"x": "部长说"}, None))   # 對齊失敗 words = null -> whisper
    text, words = a.transcribe(np.zeros(16000, dtype=np.float32), "部长说")
    assert text == "部长说" and words[0] == ("部長", 0.1, 0.5) and a.last_ts == "whisper-small"
    wk = FakeFAWorker({"x": "部长说"}, [["部", 0.1, 0.3]])
    a = _fa_asr(wk)
    text, words = a.transcribe(np.zeros(16000, dtype=np.float32))   # 沒給 text -> whisper(舊路徑)
    assert wk.sent == [] and words[0] == ("部長", 0.1, 0.5) and a.last_ts == "whisper-small"


class _FakeProc:
    def __init__(self, lines):
        import io
        self.stdout, self.stdin = iter(lines), io.StringIO()


def test_worker_protocol_text_and_words():
    w = object.__new__(TA.Worker)
    w.backend, w.log_path, w.ready = "qwen06", "x.log", None
    w.p = _FakeProc(['@@READY {"aligner": "cpu"}\n', 'noise\n',
                     '@@RES {"ok": true, "text": "你好", "sec": 0.1, "words": [["你", 0.0, 0.2], ["好", 0.2, 0.4]]}\n',
                     '@@RES {"ok": true, "text": "你好", "sec": 0.1}\n'])
    assert w._call_align(np.zeros(160, dtype=np.float32), "你好") == ("你好", [["你", 0.0, 0.2], ["好", 0.2, 0.4]])
    assert '"text": "你好"' in w.p.stdin.getvalue()
    assert w._call_align(np.zeros(160, dtype=np.float32), "你好") == ("你好", None)   # 子行程沒有對齊器


def test_asr2_device_env():
    got = []
    keep_w, keep_env = TA.Worker, TA.os.environ.get("TTS_ASR2_DEVICE")
    TA.Worker = lambda backend, device: got.append((backend, device))
    try:
        TA.os.environ.pop("TTS_ASR2_DEVICE", None)
        TA.ASR("fun_nano", ts=None)
        TA.os.environ["TTS_ASR2_DEVICE"] = "cuda"
        TA.ASR("fun_nano", ts=None)
        TA.ASR("qwen06", device="cpu", ts=None)   # 主辨識器不受這個變數影響
    finally:
        TA.Worker = keep_w
        if keep_env is None:
            TA.os.environ.pop("TTS_ASR2_DEVICE", None)
        else:
            TA.os.environ["TTS_ASR2_DEVICE"] = keep_env
    assert got == [("fun_nano", "cpu"), ("fun_nano", "cuda"), ("qwen06", "cpu")]


# ------------------------------------------------------------ 多音字位置讀音回查
def test_token_reading():
    assert TA.token_reading("[zh][ǎng]") == "zhang3"
    assert TA.token_reading("[zh][ù]") == "zhu4"
    assert TA.token_reading("着") == "zhe5"
    assert TA.token_reading("掌") == "zhang3"


def test_pron_pos_bad():
    tg = {1: ("长", "zhang3")}
    assert TA.pron_pos_bad("部长说", "部肠说", tg) == [1]  # 聽成另一個讀音 chang2 的字
    assert TA.pron_pos_bad("部长说", "部长说", tg) == []   # 同字:文字層看不出
    assert TA.pron_pos_bad("部长说", "部掌说", tg) == []   # 應讀的同音字
    assert TA.pron_pos_bad("部长说", "部场说", tg) == []   # 不相干的音(chang3)交給相似度
    assert TA.pron_pos_bad("他部长说", "部肠说", {2: ("长", "zhang3")}) == [2]  # 漏字時仍對得到位置


def test_pron_pos_bad_strict_always():
    # always 字(第三項 strict):辨識成非同音的字也記 bad
    tg = {1: ("得", "de5", True)}
    assert TA.pron_pos_bad("看得到", "看不到", tg) == [1]   # 不相干的音
    assert TA.pron_pos_bad("看得到", "看猛到", tg) == [1]
    assert TA.pron_pos_bad("看得到", "看么到", tg) == [1]
    assert TA.pron_pos_bad("看得到", "看的到", tg) == []    # 應讀的同音字
    assert TA.pron_pos_bad("看得到", "看德到", tg) == []    # 同音不同調(輕聲聽不出)
    assert TA.pron_pos_bad("看得到", "看得到", tg) == []
    assert TA.pron_pos_bad("看得到", "看到", tg) == []      # 漏字:交給相似度
    assert TA.pron_pos_bad("盯着我", "盯著我", {1: ("着", "zhe5", True)}) == []   # 著/着同字
    assert TA.pron_pos_bad("盯着我", "盯了我", {1: ("着", "zhe5", True)}) == [1]
    # 非 always 字維持原邏輯(2 項或 strict=False):長 -> 場 不記;得 無旗標也不記
    assert TA.pron_pos_bad("部长说", "部场说", {1: ("长", "zhang3")}) == []
    assert TA.pron_pos_bad("部长说", "部场说", {1: ("长", "zhang3", False)}) == []
    assert TA.pron_pos_bad("看得到", "看不到", {1: ("得", "de5")}) == []
    assert TA.pron_pos_bad("部长说", "部肠说", {1: ("长", "zhang3", False)}) == [1]   # 另一讀音仍記


def test_pron_rule_bad_strict_always_positions():
    tc = pytest.importorskip("tts_chattts")
    text = "他看得到遠方。"
    tg = tc.pron_targets(text, rules=True)
    assert tg[2][:2] == ("得", "de5") and tg[2][2] is True      # 得 預設標注 的 -> de5,always
    assert tc.pron_rule_bad(text, "他看不到遠方", rules=True) == 1
    assert tc.pron_rule_bad(text, "他看的到遠方", rules=True) == 0
    assert tc.pron_rule_bad(text, "他看德到遠方", rules=True) == 0
    assert tc.pron_rule_bad(text, "他看得到遠方", rules=True) == 0
    t2 = "他慢慢地走進來。"   # 地:非 always,規則送「的」;辨識成不相干的音仍不記
    tg = tc.pron_targets(t2, rules=True)
    assert tg[3][:2] == ("地", "de5") and tg[3][2] is False
    assert tc.pron_rule_bad(t2, "他慢慢不走進來", rules=True) == 0


def test_pron_rule_bad_rules_positions():
    tc = pytest.importorskip("tts_chattts")
    text = "他一路盯著模型看。"
    tg = tc.pron_targets(text, rules=True)
    assert 4 in tg and tg[4][1] == "zhe5"  # pron_rules.json「著」always -> 着
    assert tc.pron_rule_bad(text, "他一路盯住模型看", rules=True) == 1
    assert tc.pron_rule_bad(text, "他一路盯着模型看", rules=True) == 0


# ------------------------------------------------------------ 雙辨識判定
def test_is_bad2_and_fields():
    assert TA.is_bad2(0.80, 0, 0.85) and TA.is_bad2(0.95, 1, 0.85) and not TA.is_bad2(0.90, 0, 0.85)
    assert TA.fields({}) == dict(asr2=None, asr2_sim=None, asr2_bad=False)


class FakeASR2:
    """副辨識器:wav 就是「它會聽成的文字」。"""
    name = "fake2"

    def __init__(self):
        self.n = 0

    def submit(self, x):
        self.n += 1
        return _done(x)


def judge(text, hyp):
    return (1.0 if hyp == text else 0.5), 0


def _row(w, ok=True, n_tries=1):
    m = dict(seed=1)
    return dict(job=dict(text="好"), w=w, m=m, ok=ok, tries=[m] * n_tries)


def _sec():
    return TA.Second(judge, 0.85, asr=FakeASR2())


def test_dual_phase_agree_no_retry():
    sec, r = _sec(), _row("好")
    calls = []
    n, bad = TA.dual_phase([r], sec, lambda r_: calls.append(1), 6, lambda r_: "好", lambda w: w)
    assert (n, bad, calls) == (0, 0, []) and r["m"]["asr2"] == "好" and r["m"]["asr2_bad"] is False


def test_dual_phase_retry_until_agree():
    sec, r = _sec(), _row("壞")
    takes = iter([("壞壞", dict(seed=2), False), ("好", dict(seed=3), True)])  # 第一次沒過主品管:不跑副辨識
    n, bad = TA.dual_phase([r], sec, lambda r_: next(takes), 6, lambda r_: "好", lambda w: w)
    assert (n, bad) == (2, 0) and r["w"] == "好" and r["m"]["seed"] == 3 and len(r["tries"]) == 3
    assert "asr2" not in r["tries"][1] and sec.asr.n == 2


def test_dual_phase_still_bad_keeps_best_and_respects_max_retry():
    sec, r = _sec(), _row("壞")
    n, bad = TA.dual_phase([r], sec, lambda r_: ("壞", dict(seed=9), True), 3, lambda r_: "好", lambda w: w)
    assert (n, bad) == (3, 1) and len(r["tries"]) - 1 == 3 and r["m"]["asr2_bad"] is True


def test_dual_phase_budget_used_and_failed_rows():
    sec = _sec()
    used, failed = _row("壞", n_tries=7), _row("壞", ok=False)
    n, bad = TA.dual_phase([used, failed], sec, lambda r_: pytest.fail("不該重錄"), 6, lambda r_: "好", lambda w: w)
    assert (n, bad) == (0, 1) and used["m"]["asr2_bad"] and "asr2" not in failed["m"]


def test_final_check_only_missing():
    sec = _sec()
    a, b = _row("好"), _row("壞")
    a["m"].update(asr2="好", asr2_sim=1.0, asr2_bad=False)
    TA.final_check([a, b], sec, lambda r_: "好", lambda w: w)
    assert sec.asr.n == 1 and b["m"]["asr2_bad"] is True


def test_final_check_runs_on_not_ok_rows_without_touching_ok_fails():
    sec = _sec()
    r = _row("壞", ok=False)
    r["m"]["fails"] = ["stray_pause"]
    TA.final_check([r], sec, lambda r_: "好", lambda w: w)
    assert sec.asr.n == 1 and r["m"]["asr2"] == "壞" and r["m"]["asr2_bad"] is True and "asr2_sim" in r["m"]
    assert r["ok"] is False and r["m"]["fails"] == ["stray_pause"]


# ------------------------------------------------------------ 句中多唸字(common_inserts / Second.post)
def test_common_inserts_v1_samples():
    # ai_nextfest v1 三句(engine_text | 主辨識 | 副辨識;辨識已簡體+數字正規化):兩套都多出字 -> 抓到
    e1 = "十月,一位独立开发者在推特贴出自己做到一半的游[x][ì],隔天 罗布乐思 上就冒出一款长的[j][ī]乎一样的。"
    assert TA.common_inserts(e1, "十月上，一位独立开发者在推特贴出自己做到一半的游戏。隔天，罗布洛斯上就冒出一款长的几乎一样的。",
                             "十月上一位独立开发者在推特贴出自己做到一半的游戏。隔天，罗布乐思上就冒出一款长的几乎一样的。")[0]["asr"] == "上"
    e11 = "ARC Raiders部[f][èn]语音用 AI 合成,被骂了一轮,到今年 一月一样卖了 一千两百四十万套。"
    r = TA.common_inserts(e11, "ARC Readers G五，分语音用AI合成，被骂了一轮，到今年一月，一样卖了一千两百四十万套。",
                          "ARC RAIDERS G五泛语音用AI合成，被骂了一轮，到今年一月一样卖了一千两百四十万套。")
    assert len(r) == 1 and "G五" in r[0]["asr"]
    e35 = "怕被抄的开发者已经先动手了,日本一款愿望清单超过 五十万的恐怖喝酒游[x][ì]。"
    assert TA.common_inserts(e35, "怕被抄的开发者已经先动手了。他日本一款愿望清单超过五十万的恐怖喝酒游戏。",
                             "怕被抄的开发者已经先动手了。他日本一款愿望清单超过五十万的恐怖喝酒游戏。")[0]["asr"] == "他"


def test_common_inserts_no_false_positive():
    ref = "今年一月宣布,先停用生成式 AI,价格是 一千两百四十万套。"
    same = "今年一月宣布，先停用生成式AI，价格是一千两百四十万套。"
    assert TA.common_inserts(ref, same, same) == []
    assert TA.common_inserts(ref, same.replace("今年", "我今年"), same) == []         # 只有一套多出字
    assert TA.common_inserts(ref, same.replace("今年", "我今年"), same.replace("今年", "不今年")) == []   # 兩套各聽成不同字:辨識幻覺
    assert TA.common_inserts(ref, same.replace("宣布", "宣布了"), same.replace("先停", "先先停")) == []   # 位置不同
    assert TA.common_inserts(ref, same.replace("今年", "今天年"), same.replace("宣布", "宣")) == []        # 一套漏字不算
    assert TA.common_inserts(ref, same.replace("生成式AI", "生成式 A I"), same.replace("生成式AI", "生成式A.I")) == []   # 英文斷詞差異
    # 英文詞聽成單一字母(App -> F)或音譯成中文,不算多出
    e = "红的那年,App Store 排[h][áng]榜也被仿作洗过版。"
    assert TA.common_inserts(e, "红的那年，F Store排行榜也被仿作洗过版。", "红的那年，F Store排行榜也被仿作洗过版。") == []
    e2 = "他在 Row blocks 上做了一款游戏。"
    assert TA.common_inserts(e2, "他在罗布洛克斯上做了一款游戏。", "他在罗布洛克斯上做了一款游戏。") == []
    # 拼音 token 與辨識出的同音字視為相同音節
    assert TA.common_inserts("这部[f][èn]很好。", "这部分很好。", "这部分很好。") == []


def test_requal_marks_and_drops_key():
    import json
    import shutil
    c3 = pytest.importorskip("tts_cosy3")
    d = Path(__file__).resolve().parent.parent.parent / "tmp" / "test_requal" / "tts_cosy3"
    shutil.rmtree(d.parent, ignore_errors=True)
    d.mkdir(parents=True)
    e = "怕被抄的开发者已经先动手了,日本一款愿望清单超过 五十万的恐怖喝酒游[x][ì]。"
    bad = "怕被抄的开发者已经先动手了。他日本一款愿望清单超过五十万的恐怖喝酒游戏。"
    ok = "怕被抄的开发者已经先动手了。日本一款愿望清单超过五十万的恐怖喝酒游戏。"
    for name, hyp in (("001", bad), ("002", ok)):
        (d / f"{name}.key").write_text("k")
        (d / f"{name}.qc.json").write_text(json.dumps(dict(engine="cosy3", idx=int(name), engine_text=e, asr=hyp, asr2=hyp, passed=True, fails=[])), encoding="utf-8")
    keep = c3.P.tts_dir
    c3.P.tts_dir = lambda tag, engine=None: d
    try:
        assert [h[0] for h in c3.requal("t", dry_run=True)] == ["1"] and (d / "001.key").exists()
        assert [h[0] for h in c3.requal("t")] == ["1"]
    finally:
        c3.P.tts_dir = keep
    rec = json.loads((d / "001.qc.json").read_text(encoding="utf-8"))
    assert rec["passed"] is False and rec["fails"] == ["asr_insert"] and rec["asr_insert"][0]["asr"] == "他"
    assert not (d / "001.key").exists() and (d / "002.key").exists()
    shutil.rmtree(d.parent, ignore_errors=True)


def test_second_post_marks_asr2_bad():
    sec = TA.Second(judge, 0.85, asr=FakeASR2(), post=lambda m, text, hyp: m.update(asr_insert=["x"]) or True)
    r = _row("好")
    TA.final_check([r], sec, lambda r_: "好", lambda w: w)
    assert r["m"]["asr2_bad"] is True and r["m"]["asr_insert"] == ["x"] and r["m"]["asr2_sim"] == 1.0
    sec = TA.Second(judge, 0.85, asr=FakeASR2(), post=lambda m, text, hyp: False)
    r = _row("好")
    TA.final_check([r], sec, lambda r_: "好", lambda w: w)
    assert r["m"]["asr2_bad"] is False


if __name__ == "__main__":
    SKIP_EXC = pytest.skip.Exception if hasattr(getattr(pytest, "skip", None), "Exception") else pytest._Skip   # pytest 9 沒有 _Skip
    n = skip = 0
    for k, fn in list(globals().items()):
        if k.startswith("test_") and callable(fn):
            try:
                fn()
                n += 1
            except SKIP_EXC as e:
                skip += 1
                print("skip", k, e)
    print(f"test_tts_asr: {n} 項通過,{skip} 項略過")
