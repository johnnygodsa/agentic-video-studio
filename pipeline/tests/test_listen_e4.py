"""listen_page.pick_reasons 併入 E4 耳朵旗標(子句以整句 idx 比對;無檔不影響)。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import listen_page as LP  # noqa: E402
import paths  # noqa: E402


def _recs():
    return [{"idx": i, "text": "測試句", "passed": True} for i in ("3", "3.1", "5")]


def test_e4_reasons(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROJECTS", tmp_path)
    (tmp_path / "t1").mkdir()
    flags = {"3": {"idx": 3, "flags": [{"kind": "poly", "pos": 2, "char": "為", "expected": "wei4", "heard": "bei4"},
                                       {"kind": "runon", "pos": 5, "char": "市", "expected": "pause", "heard": ""}]},
             "5": {"idx": 5, "flags": []}}
    (tmp_path / "t1" / "ear_e4_v1.json").write_text(json.dumps({"meta": {}, "results": flags}), encoding="utf-8")
    out = LP.pick_reasons(_recs(), "t1", "v1")
    assert "5" not in out
    for k in ("3", "3.1"):
        txt = [w for c, w in out[k] if c == "e4"][0]
        assert txt == "E4耳朵:poly 為(wei4→bei4);runon 市後沒停"


def test_no_file_or_no_tag(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROJECTS", tmp_path)
    assert LP.pick_reasons(_recs(), "nope", "v1") == {}
    assert LP.pick_reasons(_recs()) == {}


# ---- 優先聽分層:必聽 vs 其他 ----
def _must_recs():
    base = {"passed": True, "text": "測試句"}
    return [dict(base, idx="1", retries=6),                                   # 重錄達門檻 = 必聽
            dict(base, idx="2", passed=False, fails=["rate"]),                # 品管未過 = 必聽
            dict(base, idx="3", tail_ok=False),                               # 句尾未過 = 必聽
            dict(base, idx="4", hard_cut=True),                               # 硬切 = 必聽
            dict(base, idx="5", asr2_bad=True, asr2="x", asr2_sim=0.5),       # 副辨識不一致 = 必聽
            dict(base, idx="6", rate_ok=False, rate_dev=0.2),                 # 語速 = 其他
            dict(base, idx="7", spk_sim=0.60, spk_thr=0.62),                  # 聲紋邊緣 = 其他
            dict(base, idx="8", text="這是 Steam 句"),                         # 含 Steam = 其他
            dict(base, idx="9")]                                              # 沒命中


def test_tier_split_must_vs_other():
    recs = _must_recs()
    reasons = LP.pick_reasons(recs)
    items = [(float(i), r, "m") for i, r in enumerate(recs)]
    must, other, rest = LP.tier_split(items, reasons)
    assert [x[1]["idx"] for x in must] == ["1", "2", "3", "4", "5"]
    assert [x[1]["idx"] for x in other] == ["6", "7", "8"]
    assert [x[1]["idx"] for x in rest] == ["9"]


def test_e4_must_kinds_and_garble_is_other(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROJECTS", tmp_path)
    (tmp_path / "t1").mkdir()
    flags = {"3": {"flags": [{"kind": "runon", "pos": 1, "char": "市", "expected": "pause", "heard": ""}]},
             "5": {"flags": [{"kind": "particle", "pos": 1, "char": "了", "expected": "le5", "heard": "liao3"}]},
             "7": {"flags": [{"kind": "poly", "pos": 1, "char": "為", "expected": "wei4", "heard": "bei4"}]},
             "8": {"flags": [{"kind": "garble", "pos": 1, "char": "為", "expected": "wei4", "heard": "bei4"}]}}
    (tmp_path / "t1" / "ear_e4_v1.json").write_text(json.dumps({"results": flags}), encoding="utf-8")
    recs = [{"idx": str(i), "text": "測試句", "passed": True} for i in (3, 5, 7, 8)]
    out = LP.pick_reasons(recs, "t1", "v1")
    assert all(LP.is_must(out[k]) for k in ("3", "5", "7"))
    assert [c for c, _ in out["8"]] == ["e4_other"] and not LP.is_must(out["8"])
    assert LP.e4_flags("t1", "v1")[8] == "garble 為(wei4→bei4)"


def test_text_lines_must_first_other_compact():
    recs = _must_recs()
    reasons = LP.pick_reasons(recs)
    tl = {int(r["idx"]): {"start": float(r["idx"]) * 5, "idx": int(r["idx"])} for r in recs}
    lines, n_must, n_other = LP.text_lines(tl, recs, reasons)
    assert (n_must, n_other) == (5, 3)
    assert lines[0].startswith(LP.MUST_HEAD) and lines[1].split("|")[1] == "1"
    oi = next(i for i, l in enumerate(lines) if l.startswith(LP.OTHER_HEAD))
    assert oi == 1 + n_must   # 標題 + 必聽各句之後才是其他節
    other = lines[oi + 1:]
    assert "語速(1):6" in other and "聲紋貼近門檻(1):7" in other and "含 Steam(1):8" in other
    assert all("|" not in l for l in other)   # 其他節不逐句列原文
