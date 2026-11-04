"""耳朵 E3(Gemini 審聽)測試:全 mock / 假呼叫,不連網、不需金鑰、不需顯示卡。
涵蓋:JSON 解析與正規化、期望讀音格式、真值召回與誤報計算、整片斷點續跑、重試與備援。
python -X utf8 -m pytest pipeline/tests/test_ear_e3.py"""
import json
import struct
import sys
import wave
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
sys.path.insert(0, str(PIPE / "senses"))
import paths  # noqa: E402
import ear_e3_gemini as E  # noqa: E402


def make_wav(p, sec=0.5):
    p.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<h", 0) * int(16000 * sec))
    return p


def args(*extra):
    return E.build_parser().parse_args(list(extra))


GOOD = {"pronunciation": {"score": 5, "issues": []}, "pauses": {"score": 5, "issues": []}, "rate": {"score": 4},
        "clarity": {"score": 5, "issues": []}, "english_terms": [], "overall_pass": True, "rationale": "ok"}
BAD = {"pronunciation": {"score": 2, "issues": [{"char": "著", "pos": "5", "heard_as_pinyin": "zhu4",
                                                  "expected_pinyin": "zhe5", "kind": "polyphone"}]},
       "pauses": {"score": 3, "issues": [{"after_char": "三", "kind": "runon"}]}, "rate": {"score": 9},
       "clarity": {"score": 4, "issues": ["robotic"]}, "english_terms": [{"term": "EA", "ok": False, "heard_as": "耶"}],
       "overall_pass": False, "rationale": "著讀成住"}


def test_parse_fenced_and_extra_text():
    assert E.parse_json_text("```json\n" + json.dumps(GOOD) + "\n```")["rationale"] == "ok"
    assert E.parse_json_text("好的,結果:" + json.dumps(GOOD) + " 以上")["overall_pass"] is True
    with pytest.raises(ValueError):
        E.parse_json_text("沒有 json")
    with pytest.raises(ValueError):
        E.parse_json_text("[1,2]")


def test_normalize_clamps_and_flattens():
    r = E.normalize(BAD)
    assert r["rate"]["score"] == 5                      # 9 夾到 5
    assert r["pronunciation"]["issues"][0]["pos"] == 5  # 字串位置轉 int
    kinds = {(i["src"], i["kind"]) for i in E.flat_issues(r)}
    assert kinds == {("pron", "polyphone"), ("pause", "runon"), ("clarity", "robotic"), ("english", "english")}


def test_normalize_derives_overall_pass_and_tolerates_junk():
    d = dict(GOOD)
    d.pop("overall_pass")
    assert E.normalize(d)["overall_pass"] is True
    d["pronunciation"] = {"score": 3, "issues": []}
    assert E.normalize(d)["overall_pass"] is False
    r = E.normalize({"pronunciation": "x", "english_terms": "y"})
    assert r["overall_pass"] is False and r["pronunciation"]["issues"] == []


def test_norm_expect_formats_and_prompt():
    t = "我們著手處理"
    assert E.norm_expect('{"2":"zhe5"}', t) == [dict(pos=2, char="著", pinyin="zhe5")]
    assert E.norm_expect([{"pos": 2, "pinyin": "zhe5"}], t)[0]["char"] == "著"
    assert E.norm_expect("", t) == [] and E.norm_expect(None, t) == []
    p = E.build_prompt(t, E.norm_expect('{"2":"zhe5"}', t))
    assert "第 2 字「著」應讀 zhe5" in p and t in p and "overall_pass" in p
    assert "期望讀音" not in E.build_prompt(t, [])


def test_truth_recall_and_false_alarm():
    iss_res = E.normalize(BAD)
    ok_res = E.normalize(GOOD)
    by_char = dict(label="bad", defects=[{"char": "著", "pos": 99, "kind": "x"}])
    by_pos = dict(label="bad", defects=[{"char": "zz", "pos": 5, "kind": "x"}])
    by_kind = dict(label="bad", defects=[{"char": "zz", "pos": 99, "kind": "runon"}])
    miss = dict(label="bad", defects=[{"char": "zz", "pos": 99, "kind": "slur"}])
    no_def = dict(label="bad", defects=[])
    assert [E.judge_item(x, iss_res)["hit"] for x in (by_char, by_pos, by_kind, miss, no_def)] == [True, True, True, False, True]
    assert E.judge_item(no_def, ok_res)["hit"] is False
    good = dict(label="good", defects=[])
    assert E.judge_item(good, ok_res)["fa"] is False
    assert E.judge_item(good, iss_res)["fa"] is True
    soft = dict(GOOD, pronunciation={"score": 5, "issues": [{"char": "的", "pos": 1, "kind": "tone"}]})
    j = E.judge_item(good, E.normalize(soft))
    assert j["fa"] is False and j["fa_strict"] is True
    rows = [dict(label="bad", **E.judge_item(x, iss_res)) for x in (by_char, miss)]
    rows += [dict(label="good", **E.judge_item(good, r)) for r in (ok_res, ok_res, ok_res, iss_res)]
    st = E.truth_stats(rows)
    assert st["recall"] == 0.5 and st["fa"] == 0.25 and (st["n_bad"], st["n_good"]) == (2, 4)
    assert E.truth_stats([])["recall"] is None


def test_run_truth_mock(tmp_path, capsys):
    w = make_wav(tmp_path / "a.wav")
    tf = tmp_path / "truth.json"
    tf.write_text(json.dumps({"items": [
        {"id": "b1", "wav": str(w), "text": "測試著", "label": "bad", "defects": [{"char": "著", "kind": "polyphone"}]},
        {"id": "g1", "wav": str(w), "text": "測試", "label": "good"}]}), encoding="utf-8")
    st = E.run_truth(args("--truth", str(tf), "--mock", "--out", str(tmp_path / "o.json")))
    assert st["n_bad"] == 1 and st["n_good"] == 1 and st["fa"] == 0.0
    assert st["recall"] == 0.0                       # mock 固定回應永遠通過 -> 壞例漏抓
    assert json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))["stats"]["n_good"] == 1
    assert "召回" in capsys.readouterr().out


@pytest.fixture
def fake_tag(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "BUILD", tmp_path / "build")
    monkeypatch.setattr(paths, "PROJECTS", tmp_path / "projects")
    d = paths.build_dir("t1")
    d.mkdir(parents=True)
    (d / "timeline_tts.json").write_text(json.dumps({"lines": [{"idx": i, "text": f"第{i}句"} for i in (1, 2, 3, 4)]}),
                                         encoding="utf-8")
    tdir = d / "tts"
    for i in (1, 2, 3, 4):
        make_wav(tdir / f"{i:03d}.trim.wav", 0.2)
    make_wav(tdir / "002.line.wav", 0.3)           # 多子句行:line.wav 優先
    return "t1"


def test_line_wav_prefers_line_wav(fake_tag):
    assert E.line_wav(fake_tag, 2).name == "002.line.wav"
    assert E.line_wav(fake_tag, 1).name == "001.trim.wav"
    assert E.line_wav(fake_tag, 9) is None


def test_parse_lines():
    assert E.parse_lines("1-3,7") == {1, 2, 3, 7} and E.parse_lines(None) is None


def test_run_tag_mock_outputs_and_resume(fake_tag):
    out = E.run_tag(args("--tag", fake_tag, "--ver", "v1", "--mock", "--lines", "1-3", "--no-expect"))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(data["results"]) == ["1", "2", "3"]
    assert data["results"]["1"]["usage"]["total"] > 0 and data["results"]["1"]["mock"] is True
    md = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "已審 3 句" in md and "mock" in md
    calls = []

    def counting(wav, text, exp, a, lim):
        calls.append(text)
        return E.call_model(wav, text, exp, a, lim)

    # 斷點續跑:1-3 已有結果跳過,只新審第 4 句
    E.run_tag(args("--tag", fake_tag, "--ver", "v1", "--mock", "--no-expect"), call=counting)
    assert calls == ["第4句"]
    # --redo 全重審
    calls.clear()
    E.run_tag(args("--tag", fake_tag, "--ver", "v1", "--mock", "--no-expect", "--redo"), call=counting)
    assert len(calls) == 4
    # 音檔換了(重錄)也重審
    make_wav(paths.tts_dir(fake_tag) / "003.trim.wav", 0.4)
    calls.clear()
    E.run_tag(args("--tag", fake_tag, "--ver", "v1", "--mock", "--no-expect"), call=counting)
    assert calls == ["第3句"]


def test_run_tag_records_error_and_retries_next_time(fake_tag):
    def boom(wav, text, exp, a, lim):
        raise E.ApiError(500, "壞掉")

    out = E.run_tag(args("--tag", fake_tag, "--ver", "v2", "--mock", "--lines", "1", "--no-expect"), call=boom)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "error" in data["results"]["1"]
    E.run_tag(args("--tag", fake_tag, "--ver", "v2", "--mock", "--lines", "1", "--no-expect"))
    assert "error" not in json.loads(out.read_text(encoding="utf-8"))["results"]["1"]


def test_retry_then_fallback(tmp_path, monkeypatch):
    w = make_wav(tmp_path / "x.wav")
    monkeypatch.setenv(E.KEY_ENV, "dummy-key")
    monkeypatch.setattr(E, "_sleep", lambda s: None)
    seen = []

    def fake_gen(model, wav, prompt, key):
        seen.append(model)
        if model == "primary":
            raise E.ApiError(429, '{"retryDelay":"3s"}')
        return json.dumps(GOOD), dict(prompt=10, output=5, thoughts=0, total=15)

    monkeypatch.setattr(E, "_generate", fake_gen)
    r = E.call_model(w, "測", [], args("--model", "primary", "--fallback-model", "backup"))
    assert seen == ["primary"] * 3 + ["backup"] and r["model"] == "backup" and r["usage"]["total"] == 15
    # 非重試錯誤(400)不重試
    seen.clear()

    def bad_request(*a):
        raise E.ApiError(400, "bad")

    monkeypatch.setattr(E, "_generate", bad_request)
    with pytest.raises(E.ApiError):
        E.call_model(w, "測", [], args("--model", "p", "--fallback-model", ""))


def test_no_key_exits(tmp_path, monkeypatch):
    monkeypatch.delenv(E.KEY_ENV, raising=False)
    with pytest.raises(SystemExit):
        E.call_model(make_wav(tmp_path / "x.wav"), "測", [], args())


def test_rate_limiter_waits(monkeypatch):
    waits = []
    monkeypatch.setattr(E, "_sleep", waits.append)
    lim = E.RateLimiter(60)      # 1 秒間隔
    lim.wait()
    lim.wait()
    assert len(waits) == 1 and 0 < waits[0] <= 1.0
    assert E.RateLimiter(0).gap == 0
