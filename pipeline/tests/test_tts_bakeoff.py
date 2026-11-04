"""tts_bakeoff 測試(T1 配音引擎比武;不載模型、不用顯示卡、不跑子行程):指標(CER、拼音 CER、多音字讀對率、時長誤差、區間與證據強度)、
拼音 token 轉 IndexTTS 寫法、語料抽樣、probe 判定、合成批次(假子行程)、報告與聽審清單產生。全部假資料。
2026-11-04 BreezyVoice 比武:拼音 token 轉注音、BreezyVoice 文字、難句抽樣、三組報告與三方盲聽、--suite 保護。
python -X utf8 pipeline/tests/test_tts_bakeoff.py(或 -m pytest)"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
if not Path(r"<EXTERNAL_BACKEND>\_shared\gpu_lock.py").is_file() and not os.environ.get("YT_SHARED_DIR"):
    os.environ["YT_SHARED_DIR"] = str(PIPE.parent / "_shared")   # 非 Windows 本機:用 repo 內的共用模組副本(只為了 import)
from tts_bakeoff import cli as CLI  # noqa: E402
from tts_bakeoff import corpus as C  # noqa: E402
from tts_bakeoff import engines as EN  # noqa: E402
from tts_bakeoff import metrics as M  # noqa: E402
from tts_bakeoff import report as R  # noqa: E402

PY = {"是": "shi4", "事": "shi4", "十": "shi2", "長": "zhang3", "掌": "zhang3", "腸": "chang2", "大": "da4", "家": "jia1", "好": "hao3"}


def py_seq(s):
    return [PY.get(c, c) for c in s]


def norm(s):
    return re.sub(r"[，。！？、,.!?\s]+", "", s)


# ------------------------------------------------------------ 指標
def test_edit_distance_and_cer():
    assert M.edit_distance("abc", "abc") == 0
    assert M.edit_distance("abc", "axc") == 1
    assert M.edit_distance("abc", "ab") == 1
    assert M.edit_distance("", "abc") == 3
    assert M.edit_distance(["shi4", "da4"], ["shi2", "da4"]) == 1
    assert M.cer_counts("大家好。", "大家好", norm) == (0, 3)
    assert M.cer_counts("大家好", "大好", norm) == (1, 3)
    assert M.cer_counts("大家好", None, norm) is None
    assert M.micro([(1, 10), None, (2, 10)]) == 0.15
    assert M.micro([None]) is None


def test_pinyin_cer_homophone_free():
    """同音別字:字元 CER 算錯,拼音 CER 不算錯;不同調算錯。"""
    assert M.cer_counts("是大", "事大", norm) == (1, 2)
    assert M.pinyin_cer_counts("是大", "事大", py_seq, norm) == (0, 2)
    assert M.pinyin_cer_counts("是大", "十大", py_seq, norm) == (1, 2)


def test_poly_summary_rate():
    s = M.poly_summary(["right", "right", "wrong", "undetermined"])
    assert (s["right"], s["wrong"], s["undetermined"], s["n"]) == (2, 1, 1, 4)
    assert abs(s["rate"] - 2 / 3) < 1e-9            # 無法判定不進分母
    assert M.poly_summary(["undetermined"])["rate"] is None
    assert M.poly_summary([])["rate"] is None


def test_poly_verdicts_fake_judge_and_fallback():
    tg = {3: ("长", "zhang3", False), 7: ("长", "zhang3", False)}
    j = lambda rec, t, **kw: dict(positions=[dict(result="right"), dict(result="wrong")])  # noqa: E731
    assert CLI.poly_verdicts({}, tg, j) == ["right", "wrong"]
    j2 = lambda rec, t, **kw: dict(result="undetermined", positions=[])  # noqa: E731  對位失敗
    assert CLI.poly_verdicts({}, tg, j2) == ["undetermined", "undetermined"]
    assert CLI.poly_verdicts({}, {}, j) == []


class FakePhon:
    def one(self, c):
        return PY.get(c, c)

    def all(self, c):
        return {"長": {"zhang3", "chang2"}}.get(c, {self.one(c)})

    def key(self, c, py=None):
        s = re.sub(r"\d", "", py or self.one(c))
        return re.sub(r"^([zcs])h", r"\1", s).replace("ng", "n")


def test_poly_with_real_judge_record():
    """tts_pron_verify.judge_record 接得上:長 被聽成「腸」(另一讀音)= 錯;聽成應讀音的同音字「掌」= 對;兩邊都聽回原字 = 無法判定。"""
    from tts_pron_verify import judge_record
    tg = {1: ("長", "zhang3", False)}
    bad = dict(text="大長好", measure_text="大長好", asr="大腸好", asr2="大長好", sim=0.9, asr2_sim=0.95, pron_bad=0)
    ok = dict(bad, asr="大掌好")
    same = dict(bad, asr="大長好")
    assert CLI.poly_verdicts(bad, tg, judge_record, norm=norm, ph=FakePhon()) == ["wrong"]
    assert CLI.poly_verdicts(ok, tg, judge_record, norm=norm, ph=FakePhon()) == ["right"]
    assert CLI.poly_verdicts(same, tg, judge_record, norm=norm, ph=FakePhon()) == ["undetermined"]


def test_duration_error():
    assert M.dur_error(2.0, 2.2) is not None and abs(M.dur_error(2.0, 2.2) - 0.1) < 1e-9
    assert abs(M.dur_error(2.0, 1.9) + 0.05) < 1e-9
    assert M.dur_error(0, 1.0) is None and M.dur_error(2.0, None) is None
    s = M.dur_summary([0.02, -0.04, 0.08, -0.2, None])
    assert s["n"] == 4
    assert abs(s["mean_abs"] - 0.085) < 1e-9
    assert s["within5"] == 0.5 and s["within10"] == 0.75
    assert abs(s["mean_signed"] - (-0.035)) < 1e-9
    assert M.dur_summary([None]) == dict(n=0)


def test_paired_ci_and_evidence():
    a = [dict(failed=False) for _ in range(100)]
    b = [dict(failed=i % 2 == 0) for i in range(100)]            # B 一半未過
    pt, lo, hi = M.paired_diff_ci(list(zip(a, b)), M.STATS["fail_rate"], b=500)
    assert abs(pt - 0.5) < 1e-9 and lo > 0
    assert M.evidence(100, (pt, lo, hi), "asr").startswith("中")
    assert M.evidence(300, (0.1, 0.05, 0.2), "measured").startswith("強")
    assert M.evidence(300, (0.1, -0.05, 0.2), "measured").startswith("弱")
    assert M.evidence(10, None, "measured").startswith("弱")
    assert M.evidence(0).startswith("無")
    assert M.evidence(300, kind="single").startswith("中")
    same = [dict(failed=False)] * 50
    pt2, lo2, hi2 = M.paired_diff_ci(list(zip(same, same)), M.STATS["fail_rate"], b=200)
    assert pt2 == 0 and lo2 == 0 and hi2 == 0


def test_time_summary():
    t = M.time_summary([1.0, 2.0, 3.0, None], [2.0, 2.0, 2.0])
    assert t["n"] == 3 and t["mean"] == 2.0 and t["median"] == 2.0 and t["rtf"] == 1.0
    assert M.time_summary([]) == dict(n=0)


# ------------------------------------------------------------ 拼音寫法
def test_to_indextts():
    assert C.to_indextts("执行[zh][ǎng]说") == "执行ZHANG3说"
    assert C.to_indextts("[t][iáo][zh][ǎng]价格") == "TIAO2ZHANG3价格"
    assert C.to_indextts("[y][ì]走进") == "YI4走进"
    assert C.to_indextts("[l][ǜ]色", upper=False) == "lv4色"
    assert C.to_indextts("跟着[d][e]") == "跟着DE5"                      # 無調號 = 輕聲
    assert C.to_indextts("没有标注。") == "没有标注。"
    assert C.marked_to_tone3("iǎo") == "iao3"


# ------------------------------------------------------------ 語料
def _recs(tag, n_fail, n_heard, n_plain):
    out, k = [], 0
    for cls, n in (("fail", n_fail), ("heard", n_heard), ("plain", n_plain)):
        for _ in range(n):
            out.append(dict(idx=k, text=f"{tag}第{k}句{'聽審詞' if cls == 'heard' else ''}的測試文字", passed=cls != "fail",
                            fails=["pitch"] if cls == "fail" else [], engine="cosy3", dur=2.0 + k / 100))
            k += 1
    return out


HEARD = lambda t: "聽審詞" in t  # noqa: E731
IDENT = lambda t: t  # noqa: E731


def test_sample_tag_priority_and_caps():
    recs = _recs("甲", 10, 30, 100)
    out = C.sample_tag("甲", recs, HEARD, IDENT, set(), per_tag=60, fail_max=20, heard_max=20)
    assert len(out) == 60
    assert sum(x["prod_passed"] is False for x in out) == 10        # 品管未過全收(少於上限)
    assert sum(HEARD(x["text"]) for x in out) >= 20                 # 聽審改過至少收到上限
    assert len({x["mtext"] for x in out}) == 60
    assert {x["cls"] for x in out} <= set(C.CLS_ORDER)
    again = C.sample_tag("甲", recs, HEARD, IDENT, set(), per_tag=60, fail_max=20, heard_max=20)
    assert [x["idx"] for x in out] == [x["idx"] for x in again]     # 同 seed 可重現


def test_sample_tag_fail_cap_and_short_skip():
    recs = _recs("乙", 40, 0, 40) + [dict(idx=999, text="好。", passed=False, engine="cosy3")]
    out = C.sample_tag("乙", recs, HEARD, IDENT, set(), per_tag=30, fail_max=5, heard_max=5)
    assert len(out) == 30 and all(x["idx"] != 999 for x in out)     # 太短的句子不收
    assert sum(x["cls"] == "qc_fail" for x in out) >= 5


def test_build_corpus_dedupe_and_texts():
    a = _recs("丙", 2, 2, 10)
    b = [dict(r) for r in a[:5]] + _recs("丁", 0, 0, 10)            # 丁 前 5 句與丙重複(同量測文字)
    items = C.build_corpus([("丙", a), ("丁", b)], lambda m: "[zh][ǎng]" + m, HEARD, IDENT, per_tag=8, fail_max=2, heard_max=2)
    assert [x["n"] for x in items] == list(range(len(items)))
    assert len({x["mtext"] for x in items}) == len(items)
    assert all(x["engine"].startswith("[zh][ǎng]") and x["itext"].startswith("ZHANG3") for x in items)
    st = C.stats(items)
    assert sum(st["丙"].values()) == 8


def test_find_tags():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for tag, eng in (("a", "cosy3"), ("b", "chattts"), ("test_x", "cosy3"), ("c", "cosy3")):
            (d / tag).mkdir()
            (d / tag / "tts_qc.json").write_text(json.dumps(dict(records=[dict(engine=eng, text="x")])), encoding="utf-8")
        os.utime(d / "a" / "tts_qc.json", (1, 1))
        assert C.find_tags(d, 5) == ["c", "a"]
        assert C.find_tags(d, 1) == ["c"]


# ------------------------------------------------------------ probe / 合成批次
def test_probe_verdict():
    ok, why = CLI.probe_verdict(dict(vram_peak_mib=3200, n_ok=8, n_fail=0))
    assert ok and not why
    ok, why = CLI.probe_verdict(dict(vram_peak_mib=5200, n_ok=8, n_fail=0))
    assert not ok and "5200" in why[0]
    ok, why = CLI.probe_verdict(dict(vram_peak_mib=3000, n_ok=3, n_fail=0, crashed="OOM"))
    assert not ok and "中止" in why[0]
    assert not CLI.probe_verdict(dict(vram_peak_mib=None, n_ok=8))[0]


def test_import_probe():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "p.json"
        f.write_text(json.dumps(dict(max_memory_allocated_mib=4100, load_s=30, sec_per_sentence=[2.0, 4.0])), encoding="utf-8")
        pr = CLI.import_probe(f)
        assert pr["vram_peak_mib"] == 4100 and pr["n_ok"] == 2 and pr["time"]["mean"] == 3.0
        assert not CLI.probe_verdict(pr)[0]


class FakeWorker:
    calls = []

    def __init__(self, cmd, env, log_path):
        self.ready = dict(vram_alloc_mib=1500, vram_reserved_mib=1800, load_s=9.0, dur_supported=True)

    def call(self, **job):
        FakeWorker.calls.append(job)
        if "壞" in job["text"]:
            return dict(ok=False, err="boom")
        Path(job["out"]).write_bytes(b"RIFF")
        return dict(ok=True, dur=2.0, sec=1.5, wall_s=1.6, vram_reserved_mib=2600, vram_alloc_mib=2400)

    def close(self):
        pass


def test_run_batch_resume_and_peaks():
    items = [dict(n=i, engine=f"句{i}", itext=("壞" if i == 2 else "") + f"句{i}") for i in range(4)]
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        FakeWorker.calls = []
        used = iter([1000, 3000, 3100] + [3100] * 100)
        s = EN.run_batch("indextts2", items, d / "wav", [], {}, d / "w.log", d / "rows.jsonl",
                         gpu_used=lambda: next(used), worker_cls=FakeWorker)
        assert (s["n_ok"], s["n_fail"]) == (3, 1)
        assert s["torch_peak_mib"] == 2600 and s["baseline_mib"] == 1000
        assert s["vram_peak_mib"] >= 2600
        assert all("speed" not in j for j in FakeWorker.calls)
        FakeWorker.calls = []
        s2 = EN.run_batch("indextts2", items, d / "wav", [], {}, d / "w.log", d / "rows.jsonl", worker_cls=FakeWorker,
                          targets={0: 2.5, 2: 1.0, 3: 2.0})
        assert s2["skipped"] == 3 and [j["text"] for j in FakeWorker.calls] == ["壞句2"]   # 只重做失敗的那句
        assert FakeWorker.calls[0]["target_sec"] == 1.0
        FakeWorker.calls = []
        EN.run_batch("cosy3", items[:1], d / "c", [], {}, d / "c.log", d / "c.jsonl", worker_cls=FakeWorker)
        assert FakeWorker.calls[0]["speed"] == EN.COSY_SPEED and FakeWorker.calls[0]["text"] == "句0"


def test_worker_cmd():
    c = EN.worker_cmd("indextts2", "r.wav", "r.txt", dict(fp16=False, dur_kwarg="target_tokens", dur_unit="tokens"))
    assert "--no-fp16" in c and c[c.index("--dur-kwarg") + 1] == "target_tokens" and c[c.index("--dur-unit") + 1] == "tokens"
    assert c[3].endswith("indextts2_worker.py")
    assert EN.worker_cmd("cosy3", "r.wav", "r.txt")[3].endswith("cosy3_worker.py")


# ------------------------------------------------------------ 指標彙總 / 報告 / 聽審
def _write_qc(work, eng, items, bad_every, cer_bad):
    d = work / "judge" / eng
    d.mkdir(parents=True, exist_ok=True)
    for x in items:
        n = x["n"]
        asr = x["mtext"][:-1] + "錯" if n % cer_bad == 0 else x["mtext"]
        rec = dict(text=x["text"], measure_text=x["mtext"], asr=asr, asr2=x["mtext"], passed=n % bad_every != 0,
                   fails=["pitch"] if n % bad_every == 0 else [], spk_sim=0.6, dur=2.0, sim=0.95, asr2_sim=0.95)
        (d / f"{n}.qc.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        (d / f"{n}.wav").write_bytes(b"")


def test_metrics_report_listen_end_to_end():
    items = [dict(n=i, tag="甲", text=f"第{i}句大家好測試", mtext=f"第{i}句大家好測試", cls="plain") for i in range(60)]
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        _write_qc(work, "cosy3", items, bad_every=10, cer_bad=7)
        _write_qc(work, "indextts2", items, bad_every=3, cer_bad=2)
        tg = lambda m: {1: ("大", "da4", False)}  # noqa: E731
        judge = lambda rec, t, **kw: dict(positions=[dict(result="wrong" if "錯" in rec["asr"] else "right")])  # noqa: E731
        rows = {e: CLI.engine_rows(work, e, items, norm, py_seq, tg, judge) for e in EN.ENGINES}
        assert len(rows["cosy3"]) == 60
        synth = {"cosy3": dict(time=M.time_summary([3.0] * 60, [2.0] * 60), torch_peak_mib=3400, smi_delta_mib=3600,
                               vram_peak_mib=3600, n_fail=0),
                 "indextts2": dict(time=M.time_summary([6.0] * 60, [2.0] * 60), torch_peak_mib=3300, smi_delta_mib=3450,
                                   vram_peak_mib=3450, n_fail=0)}
        dur = dict(M.dur_summary([0.03, -0.06, 0.12] * 20), supported=True, target_src="CosyVoice 同句時長")
        probe = dict(load_s=40, vram_peak_mib=3300, n_ok=8, n_fail=0, passed=True, reasons=[], time=M.time_summary([5.0] * 8))
        mt = CLI.build_metrics(work, items, rows, synth, probe, dict(n=60, tags=["甲"], per_tag=60, plain=60), dur)
        mt = json.loads(json.dumps(mt, ensure_ascii=False))           # 經過 metrics.json 往返
        e = mt["engines"]
        assert e["cosy3"]["failed"] == 6 and e["indextts2"]["failed"] == 20
        assert e["indextts2"]["cer"] > e["cosy3"]["cer"] > 0
        assert e["indextts2"]["poly"]["wrong"] == 30 and e["cosy3"]["poly"]["wrong"] == 9
        assert mt["compare"]["fail_rate"][1] > 0                        # IndexTTS2 未過較多,區間不含 0
        R.write_report(work / "report.md", mt, "2026-10-27")
        rep = (work / "report.md").read_text(encoding="utf-8")
        for k in ("(a) 字元 CER", "(a) 拼音 CER", "(b) 多音字讀對率", "(c) 品管未過句數", "(d) 每句秒數", "(e) 顯存峰值",
                  "(f) 時長控制誤差", "證據強度", "## 結論(主對話填)", "冷啟量測"):
            assert k in rep, k
        assert "6 / 60" in rep and "20 / 60" in rep
        rws = CLI.load_rows(mt)
        picks = R.pick_listen(rws["cosy3"], rws["indextts2"], k=20)
        assert len(picks) == 20 and len(set(picks)) == 20
        R.write_listen(work / "listen.md", picks, items, rws["cosy3"], rws["indextts2"], lambda en, n: work / en / f"{n}.wav")
        lis = (work / "listen.md").read_text(encoding="utf-8")
        assert lis.count("](file:///") == 40 and "答案" in lis
        assert len(re.findall(r"^\| \d+ \| A=", lis, re.M)) == 20


def test_report_dur_unsupported_and_closure():
    mt = dict(engines={}, compare={}, n_common=0, synth={}, dur=dict(supported=False, note="無參數"), corpus={})
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "r.md"
        R.write_report(p, mt, "2026-10-27")
        assert "無時長參數" in p.read_text(encoding="utf-8")
        pr = dict(load_s=50, vram_peak_mib=5200, torch_peak_mib=5000, smi_delta_mib=5200, n_ok=8, n_fail=0, passed=False,
                  reasons=["顯存峰值 5200 MiB > 3500"], time=M.time_summary([4.0] * 8, [3.0] * 8))
        R.write_closure(p, pr, "2026-10-27")
        t = p.read_text(encoding="utf-8")
        assert "結案" in t and "5200" in t and "顯存不夠" in t and "每句秒數" in t


def test_cli_dry_runs():
    with tempfile.TemporaryDirectory() as d:
        assert CLI.main(["--work", d, "probe", "--dry-run"]) == 0
        assert CLI.main(["--work", d, "synth", "--engine", "cosy3", "--dry-run"]) == 2   # 沒語料
        C.write_jsonl(Path(d) / "corpus.jsonl", [dict(n=0, mtext="大家好", itext="大家好", engine="大家好", text="大家好")])
        assert CLI.main(["--work", d, "synth", "--engine", "cosy3", "--dry-run"]) == 0
        assert CLI.main(["--work", d, "synth", "--engine", "indextts2", "--dry-run"]) == 3   # probe 未過/未跑
        assert CLI.main(["--work", d, "judge", "--dry-run"]) == 0
        assert not any(Path(d).glob("*.md"))


# ------------------------------------------------------------ BreezyVoice 比武(2026-11-04)
def test_zhuyin_conversion():
    z = C.run_to_zhuyin
    assert z("[zh][ǎng]") == "ㄓㄤ3" and z("[y][ì]") == "ㄧ4" and z("[l][ǜ]") == "ㄌㄩ4" and z("[j][iǎo]") == "ㄐㄧㄠ3"
    assert z("[x][iě]") == "ㄒㄧㄝ3" and z("[w][ǒ]") == "ㄨㄛ3" and z("[w][èi]") == "ㄨㄟ4" and z("[y][ǔ]") == "ㄩ3"
    assert z("[j][ū]") == "ㄐㄩ1" and z("[y][è]") == "ㄧㄝ4" and z("[y][ōng]") == "ㄩㄥ1" and z("[n][üè]") == "ㄋㄩㄝ4"
    assert z("[zh][ī]") == "ㄓ1" and z("[s][ì]") == "ㄙ4"           # 空韻
    assert z("[d][e]") == "ㄉㄜ5" and z("[e]") == "ㄜ5" and z("[ǎ]") == "ㄚ3"   # 無調號 = 輕聲 5
    assert z("[zh]") is None and z("[ǎng][zh]") is None and z("[zh][ǎng][x]") is None and z("着") is None
    assert C.syllable_to_zhuyin("zh", "ang3") == "ㄓㄤ3" and C.syllable_to_zhuyin("", "ang") is None


def test_zhuyin_all_cosy_tokens_map_and_in_breezy_vocab():
    """讀音表詞表與多音字規則的每個拼音標注都能轉注音;BreezyVoice 本機有 utils/word_utils.py 時,注音還要在它的 char2phn 詞彙內。"""
    import tts_cosy_text as CT
    vals = {py for _w, _c, _o, py, _u in CT.RULE_WORDS} | {py for _p, _c, py, _u in CT.RULE_REGS} | {e["model_default"] for e in CT.RULE_CHARS.values()}
    vals |= {u for v in CT.PRON.values() for u in C.unit_split(v) if u}
    toks = [v for v in vals if v and "[" in v]
    assert toks and all(C.run_to_zhuyin(v) for v in toks), [v for v in toks if not C.run_to_zhuyin(v)]
    wu = PIPE.parent / "tts_models" / "BreezyVoice" / "utils" / "word_utils.py"
    if wu.is_file():
        import importlib.util
        spec = importlib.util.spec_from_file_location("breezy_word_utils", wu)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        vocab = {s for v in m.char2phn.values() for s in v}
        assert all(C.run_to_zhuyin(v) in vocab for v in toks), [v for v in toks if C.run_to_zhuyin(v) not in vocab]


def test_unit_split_and_marks():
    assert C.unit_split("執行[zh][ǎng]") == [None, None, "[zh][ǎng]"]
    assert C.unit_split("[j][iǎo]色") == ["[j][iǎo]", None]
    assert C.unit_split("[y][ì][d][iàn]") == ["[y][ì]", "[d][iàn]"]
    marks, bad = C.span_marks([(2, 5, "執行[zh][ǎng]"), (7, 9, "[y][ì]")], [(0, "重", "[ch][óng]", "k", "word", False), (6, "着", "着", "k", "default", False)])
    assert marks == {4: "[zh][ǎng]", 0: "[ch][óng]"} and bad == [(7, 9, "[y][ì]")]   # 區段單位數對不上 -> bad;非 token 的換字略過
    ann, n, bad = C.annotate_zhuyin("重製版的執行長", {0: "[ch][óng]", 6: "[zh][ǎng]", 3: "[zh]"})
    assert ann == "重[:ㄔㄨㄥ2]製版的執行長[:ㄓㄤ3]" and n == 2 and bad == [(3, "的", "[zh]")]


def test_revert_term_annot_and_tidy_punct():
    ta = {"藝電": "[y][ì][d][iàn]"}
    t, ex = C.revert_term_annot("宣布[y][ì][d][iàn]關門,又說[y][ì][d][iàn]", ta)
    assert t == "宣布藝電關門,又說藝電" and ex == {2: "[y][ì]", 3: "[d][iàn]", 9: "[y][ì]", 10: "[d][iàn]"}
    assert C.revert_term_annot("沒有", ta) == ("沒有", {}) and C.revert_term_annot("x", {}) == ("x", {})
    assert C.tidy_punct("看《遊戲》,他說:好!(是嗎?)") == "看遊戲，他說，好！，是嗎？，"
    assert C.tidy_punct("好[:ㄏㄠ3],對[:ㄉㄨㄟ4]!") == "好[:ㄏㄠ3]，對[:ㄉㄨㄟ4]！"    # 注音標注裡的冒號不動、標注後的半形逗號也轉全形
    assert C.tidy_punct("Hello, world") == "Hello, world" and C.tidy_punct("3,000、四") == "3,000、四"


def test_breezy_text_fake_marks():
    marks = lambda t: ({t.index("長"): "[zh][ǎng]"}, [])  # noqa: E731
    plain, ann, n, bad = C.breezy_text("執行長說,[怎麼]辦.", source_fn=lambda m: m, marks_fn=marks, term_annot={})
    assert plain == "執行長說，怎麼辦。" and ann == "執行長[:ㄓㄤ3]說，怎麼辦。" and n == 1 and bad == []
    plain, ann, n, bad = C.breezy_text("好嗎?", source_fn=lambda m: m, marks_fn=lambda t: ({0: "[zh]"}, [(5, 6, "x")]), term_annot={})
    assert plain == ann == "好嗎？" and n == 0 and bad == [(0, "好", "[zh]"), (5, 6, "x")]
    p2, a2, n2, _ = C.breezy_text("宣布EA。", source_fn=lambda m: m.replace("EA", "[y][ì][d][iàn]"), marks_fn=lambda t: ({}, []),
                                  term_annot={"藝電": "[y][ì][d][iàn]"})
    assert p2 == "宣布藝電。" and a2 == "宣布藝[:ㄧ4]電[:ㄉㄧㄢ4]。" and n2 == 2


def test_breezy_text_real_front_end():
    """真的 cosy_pron / pron_rules / cosy_terms:不載模型,只驗結構(標注都是「字[:注音]」、拿掉標注後等於純文字、不含拼音 token)。"""
    for m in ("重製版的時間點又不一樣。", "執行長說這件事很重要,Steam 上也有。", "他跟著大家走進去,為了什麼?"):
        plain, ann, n, bad = C.breezy_text(m)
        assert bad == [] and "[ch]" not in ann and "[zh]" not in ann
        assert re.sub(r"\[:[^\]]*\]", "", ann) == plain and ann.count("[:") == n
        assert plain[-1] in "。？！"
    assert C.breezy_text("重製版的時間點。")[1].startswith("重[:ㄔㄨㄥ2]製版")


def _hard_pool(n_fail=40, n_poly=60, n_en=40, n_plain=30):
    pool, k = [], 0
    for cls, n in (("fail", n_fail), ("poly", n_poly), ("en", n_en), ("plain", n_plain)):
        for i in range(n):
            pool.append(dict(tag=f"t{k % 3}", idx=k, text=f"{cls}{k}測試句子文字", mtext=f"{cls}{k}測試句子文字", prod_passed=False if cls == "fail" else True,
                             prod_fails=[], prod_dur=2.0, rank=k % 3, fail=cls == "fail", poly=(2 + i % 5) if cls == "poly" else 0,
                             en=(2 + i % 4) if cls == "en" else 0))
            k += 1
    return pool


def test_select_hard_quota_and_repro():
    pool = _hard_pool()
    out = C.select_hard(pool, size=80)
    assert len(out) == 80 and len({x["mtext"] for x in out}) == 80
    cnt = {c: sum(x["cls"] == c for x in out) for c in C.HARD_CLS}
    assert cnt["qc_fail"] >= 24 and cnt["poly"] >= 32 and cnt["english"] >= 18 and sum(cnt.values()) == 80   # 各類先吃到配額,其餘依總分補
    assert [x["idx"] for x in out] == [x["idx"] for x in C.select_hard(pool, size=80)]    # 同 seed 可重現
    assert min(x["poly"] for x in out if x["cls"] == "poly") >= 2
    small = C.select_hard(_hard_pool(3, 4, 2, 2), size=80)
    assert len(small) == 11                                                                # 候選不足就全收


def test_hard_scores_and_qc_dir():
    assert C.poly_score(dict(pron_hits={"長→zhǎng": "x", "重": "y"}, g2p_disagree=[1, 2, 3])) == 5 and C.poly_score({}) == 0
    assert C.en_score("在 Steam 和 Battle net,Game Pass 上的 EA 版本") == 6 and C.en_score("沒有英文 123") == 0
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "sub").mkdir()
        for name, rec in (("020.qc.json", dict(engine="cosy3", text="壞的一句話", passed=False)), ("021.qc.json", dict(engine="cosy3", text="好的", passed=True)),
                          ("sub/003.qc.json", dict(engine="cosy3", text="子句沒過", passed=False)), ("abc123.qc.json", dict(engine="cosy3", text="雜湊名不收", passed=False)),
                          ("022.qc.json", dict(engine="chattts", text="別的引擎", passed=False))):
            (d / name).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        (d / "023.qc.json").write_text("{壞掉", encoding="utf-8")
        assert sorted(r["text"] for r in C.load_qc_dir(d)) == ["壞的一句話", "子句沒過"]
        assert C.load_qc_dir(d / "none") == []


def test_build_hard_fields():
    recs = [dict(idx=i, text=f"第{i}句{'長' * (i % 3)}測試文字", passed=i % 4 != 0, fails=[], engine="cosy3") for i in range(30)]
    items = C.build_hard([("甲", recs)], lambda m: "E:" + m, unsay_fn=lambda t: t, size=10,
                         breezy_fn=lambda m: (m, m + "[:ㄅ]", 1, [(1, "x", "y")]))
    assert len(items) == 10 and [x["n"] for x in items] == list(range(10))
    assert all(x["engine"] == "E:" + x["mtext"] and x["btext"] == x["mtext"] and x["bann_n"] == 1 and x["bann_unmapped"] == [[1, "x", "y"]] for x in items)
    assert all("rank" not in x and "fail" not in x for x in items)
    assert sum(C.stats(items)["甲"].values()) == 10


def test_engines_breezy_wiring():
    c = EN.worker_cmd("breezy", "r.wav", "r.txt", dict(device="cpu"))
    assert c[0].endswith("python.exe") and "tts_env_breezy" in c[0] and c[3].endswith("breezy_worker.py") and c[c.index("--device") + 1] == "cpu"
    assert c[c.index("--model-dir") + 1].endswith("BreezyVoice-300M") and c[c.index("--g2pw-dir") + 1].endswith("G2PWModel")
    assert EN.worker_cmd("breezy_ann", "r.wav", "r.txt")[3].endswith("breezy_worker.py")
    env = EN.worker_env("breezy")
    assert "PYTHONPATH" not in env and env["HF_HOME"].endswith("BreezyVoice_cache") and "breezy_home" in env["USERPROFILE"]
    assert EN.env_python("breezy_ann") == EN.BREEZY_ENV and EN.TEXT_KEY["breezy_ann"] == "bann" and EN.TEXT_KEY["breezy"] == "btext"
    items = [dict(n=0, engine="簡", itext="i", btext="純文字", bann="標[:ㄅ]注")]
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for eng, want in (("breezy", "純文字"), ("breezy_ann", "標[:ㄅ]注")):
            FakeWorker.calls = []
            EN.run_batch(eng, items, d / eng / "wav", [], {}, d / "w.log", d / f"{eng}.jsonl", worker_cls=FakeWorker)
            assert FakeWorker.calls[0]["text"] == want and "speed" not in FakeWorker.calls[0]


def test_pron_fail_count_and_summary():
    base = dict(cer=None, pcer=None, cer2=None, pcer2=None, spk_sim=None, asr2_bad=False)
    rows = [dict(base, failed=True, fails=["pron", "rate"], poly=["wrong"]), dict(base, failed=True, fails=["rate"], poly=[]),
            dict(base, failed=False, fails=[], poly=["right"])]
    assert M.pron_fail_count(rows) == 1 and M.engine_summary(rows)["pron_fail"] == 1


def test_three_way_report_and_listen():
    items = [dict(n=i, tag="甲", text=f"第{i}句大家好測試", mtext=f"第{i}句大家好測試", cls="plain") for i in range(60)]
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        _write_qc(work, "cosy3", items, bad_every=10, cer_bad=7)
        _write_qc(work, "breezy", items, bad_every=3, cer_bad=2)
        _write_qc(work, "breezy_ann", items, bad_every=5, cer_bad=3)
        tg = lambda m: {1: ("大", "da4", False)}  # noqa: E731
        judge = lambda rec, t, **kw: dict(positions=[dict(result="wrong" if "錯" in rec["asr"] else "right")])  # noqa: E731
        rows = {e: CLI.engine_rows(work, e, items, norm, py_seq, tg, judge) for e in EN.ENGINES}
        assert CLI.active_engines(work) == ["cosy3", "indextts2"]                    # 沒有 rows.jsonl:退回舊比武兩組
        for e in ("cosy3", "breezy"):
            C.write_jsonl(work / e / "rows.jsonl", [dict(n=0, ok=True)])
        assert CLI.active_engines(work) == ["cosy3", "breezy"]
        synth = {e: dict(time=M.time_summary([5.0] * 60, [2.0] * 60), torch_peak_mib=2500, smi_delta_mib=2600, vram_peak_mib=2600, n_fail=0) for e in R.TRIO}
        mt = CLI.build_metrics(work, items, rows, synth, None, dict(n=60, tags=["甲"], focus="hard", classes={"qc_fail": 20, "poly": 40}), {})
        mt = json.loads(json.dumps(mt, ensure_ascii=False))
        e = mt["engines"]
        assert e["breezy"]["failed"] == 20 and e["breezy_ann"]["failed"] == 12 and e["cosy3"]["failed"] == 6
        assert set(mt["compare_by"]) == {"breezy_vs_cosy3", "breezy_ann_vs_cosy3", "breezy_ann_vs_breezy"} and mt["n_common_by"]["breezy_vs_cosy3"] == 60
        assert mt["compare_by"]["breezy_vs_cosy3"]["fail_rate"][1] > 0
        R.write_report_multi(work / "report.md", mt, "2026-11-04")
        rep = (work / "report.md").read_text(encoding="utf-8")
        for k in ("BreezyVoice+注音標注", "(a) 字元 CER", "(b) 多音字讀對率", "多音字錯誤數", "(c) 品管未過句數", "(d) 每句秒數", "(e) 顯存峰值",
                  "成對差異", "BreezyVoice+注音標注 − BreezyVoice", "## 結論(主對話填)", "focus=hard"):
            assert k in rep, k
        assert "20 / 60" in rep and "12 / 60" in rep and "6 / 60" in rep
        rws = CLI.load_rows(mt)
        picks = R.pick_listen_multi(rws, R.TRIO, k=20)
        assert len(picks) == 20 and len(set(picks)) == 20
        R.write_listen_multi(work / "listen.md", picks, items, rws, lambda en, n: work / en / f"{n}.wav")
        lis = (work / "listen.md").read_text(encoding="utf-8")
        assert lis.count("](file:///") == 60 and "3 方盲聽" in lis and len(re.findall(r"^\| \d+ \| A=", lis, re.M)) == 20
        assert all(f"{lab}=" in lis for lab in "ABC")


def test_cli_breezy_guards_and_dry_runs():
    with tempfile.TemporaryDirectory() as d:
        w = Path(d)
        C.write_jsonl(w / "corpus.jsonl", [dict(n=0, mtext="大家好", itext="大家好", engine="大家好", text="大家好", btext="大家好。", bann="大家好。")])
        assert CLI.main(["--work", d, "synth", "--engine", "breezy", "--dry-run"]) == 0       # 指了 --work = 不會蓋預設目錄
        assert CLI.main(["--work", d, "synth", "--engine", "breezy_ann", "--dry-run"]) == 0
        C.write_jsonl(w / "corpus.jsonl", [dict(n=0, mtext="大家好", itext="大家好", engine="大家好", text="大家好")])
        assert CLI.main(["--work", d, "synth", "--engine", "breezy", "--dry-run"]) == 2       # 舊語料沒有 btext
        assert CLI.main(["--work", d, "smoke", "--engine", "breezy_ann", "--dry-run"]) == 0
        assert CLI.main(["--work", d, "judge", "--dry-run"]) == 0
        assert CLI.main(["--work", d, "report", "--dry-run"]) == 2 and not any(w.glob("*.md"))
    assert CLI.parser().parse_args(["synth", "--engine", "breezy"]).work is None               # 沒指 --suite / --work:預設目錄,breezy 要被擋
    assert CLI.main(["synth", "--engine", "breezy", "--dry-run"]) == 2 and CLI.main(["corpus", "--focus", "hard", "--dry-run"]) == 2


if __name__ == "__main__":
    n = 0
    for k, fn in list(globals().items()):
        if k.startswith("test_") and callable(fn):
            fn()
            n += 1
    print(f"test_tts_bakeoff: {n} 項通過")
