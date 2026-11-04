"""terms_check:英文詞判斷單一來源(say_terms 版、cosy 版、未驗證、直送未決)。
tts_env_chattts\\Scripts\\python.exe -X utf8 -m pytest pipeline/tests/test_terms_check.py -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import terms_check as TC  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import tts_term_qc as TQ  # noqa: E402
import tts_terms  # noqa: E402


def test_analyze_default_terms_equals_explicit():
    texts = ["Creative Assembly 與 CAD 都是詞。", "沒有英文"]
    assert TC.analyze(texts) == TC.analyze(texts, TC.load_terms())
    assert tts_terms.analyze is TC.analyze and tts_terms.load_terms is TC.load_terms   # tts_terms 只剩 CLI 外殼


def test_analyze_unapplied_and_direct():
    terms = [{"term": "Xbox", "say": "艾克斯"}, {"term": "Steam", "say": None}]
    r = TC.analyze(["Xbox 上的 Steam", "已套用艾克斯"], terms)
    assert r["unapplied"] == {"Xbox": {"say": "艾克斯", "lines": [1]}}
    assert r["direct"] == {"Steam": {"say": None, "lines": [1]}} and r["unregistered"] == {}


def _patch(monkeypatch, terms, direct, verified):
    monkeypatch.setattr(CT, "TERMS", terms)
    monkeypatch.setattr(CT, "DIRECT", direct)
    monkeypatch.setattr(CT, "TERMS_VERIFIED", verified)


def test_unregistered_cosy(monkeypatch):
    _patch(monkeypatch, {"BioWare": "生軟"}, ["Steam"], set())
    texts = ["BioWare 與 Steam", "Foo Bar 說", "又是 Foo Bar 與 Baz"]
    assert TC.unregistered(texts) == ["Foo Bar", "Baz"]
    assert TC.unregistered_by_line(texts) == {2: ["Foo Bar"], 3: ["Foo Bar", "Baz"]}
    assert TC.unregistered(["只有中文"]) == []


def test_registered_unverified(monkeypatch):
    _patch(monkeypatch, {"BioWare": "生軟", "EA": "藝電"}, ["Steam"], {"EA"})
    assert TC.registered_unverified("BioWare 與 EA 與 Steam") == ["BioWare", "Steam"]
    assert TC.registered_unverified("") == []


def test_direct_open_shared_with_term_qc(monkeypatch):
    _patch(monkeypatch, {}, ["Foo Bar", "Baz Qux", "Kotaku", "B"], {"Kotaku"})
    texts = ["Foo Bar 說", "Kotaku 與 B 級", "又是 Foo Bar", "Baz Qux 一次"]
    assert TC.direct_open(texts) == {"Foo Bar": [1, 3], "Baz Qux": [4]}
    assert TQ.direct_open(texts) == TC.direct_open(texts)


def test_still_en_term_with_chinese_spelling(monkeypatch):
    _patch(monkeypatch, {"BioWare": "生軟"}, ["BioWare", "Steam"], set())
    assert TC.still_en("Steam") and not TC.still_en("BioWare")
    assert TC.direct_open(["BioWare 與 Steam", "Steam"]) == {"Steam": [1, 2]}
