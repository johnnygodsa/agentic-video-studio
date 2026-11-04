"""director cost / usage / model_w 測試:python -X utf8 -m pytest pipeline/tests/test_director_cost.py -q
production.json 用 tmp_path 假檔(monkeypatch prod_path),usage_for_tag 以假函式取代(不讀 C 槽)。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director as D  # noqa: E402


def _call(fn, seg, model, tin, tout, cache=0, cw=True):
    cost = round(tin + 5 * tout + 0.1 * cache, 1)
    r = {"fn": fn, "seg": seg, "model": model, "input_tokens": tin, "output_tokens": tout, "cache_read": cache, "cost_eq": cost}
    if cw:
        r["cost_w"] = round(cost * D.model_w(model), 1)
    return r


def _setup(monkeypatch, tmp_path, data):
    p = tmp_path / "production.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(D, "prod_path", lambda tag: p)
    return p


def test_model_w():
    assert D.model_w("claude-opus-4-1") == 5.0
    assert D.model_w("claude-sonnet-5-5") == 1.0
    assert abs(D.model_w("claude-haiku-5") - 1 / 3) < 1e-9
    assert D.model_w("gpt-x") == 1.0 and D.model_w(None) == 1.0


def test_log_call_adds_cost_w(monkeypatch, tmp_path):
    p = _setup(monkeypatch, tmp_path, {"tag": "t", "llm_calls": []})
    D.log_call("t", "f", "claude-opus-5", 1000, 100, 0)
    rec = json.loads(p.read_text(encoding="utf-8"))["llm_calls"][0]
    assert rec["cost_eq"] == 1500.0 and rec["cost_w"] == 7500.0


def test_cost_groups_and_totals(monkeypatch, tmp_path):
    calls = [
        _call("a", "A", "claude-sonnet-5-5", 1000, 100, 0),            # 1500
        _call("a", "A", "claude-sonnet-5-5", 2000, 200, 1000),         # 3100
        _call("b", "A", "claude-opus-5", 100, 10, 0),                  # 150 -> w 750
        _call("c", "B", "claude-haiku-5", 300, 0, 0, cw=False),        # 300, 舊紀錄現算 w 100
        _call("d", "B", "claude-sonnet-5-5", 10, 1, 0),                # 15
    ]
    _setup(monkeypatch, tmp_path, {"tag": "t", "llm_calls": calls})
    rep = D.cost_report("t")
    assert [s["seg"] for s in rep["segs"]] == ["A", "B"]
    a = rep["segs"][0]
    assert [r["fn"] for r in a["rows"]] == ["a", "b"]  # cost_eq 大到小
    assert a["rows"][0]["n"] == 2 and a["rows"][0]["cost_eq"] == 4600.0
    assert a["subtotal"]["cost_eq"] == 4750.0 and a["subtotal"]["cost_w"] == 4600.0 + 750.0
    b = rep["segs"][1]
    assert b["rows"][0]["fn"] == "c" and b["rows"][0]["cost_w"] == 100.0
    assert rep["total"]["cost_eq"] == 5065.0 and rep["total"]["n"] == 5
    assert "合計" in D.render_cost(rep)
    assert D.main(["cost", "t", "--json"]) == 0


def test_cost_empty(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, {"tag": "t"})
    rep = D.cost_report("t")
    assert rep["segs"] == [] and rep["total"]["cost_eq"] == 0


def test_usage_writes_session(monkeypatch, tmp_path):
    p = _setup(monkeypatch, tmp_path, {"tag": "t", "gates": {"A": {"passed": True}}, "interventions": [{"what": "x"}, {"what": "y"}]})
    monkeypatch.setattr(D, "_usage_tag", lambda tag, since=None, sessions=None: dict(sessions=["abcd1234"], turns=10, input=100, cache_creation=1000,
                                                          cache_read=10000, output=200, main_eq=5000, sub_eq=2000))
    rec = D.write_session("t")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["session"] == rec and d["gates"] == {"A": {"passed": True}}
    assert rec["sessions"] == ["abcd1234"] and rec["turns"] == 10
    assert rec["cost_eq"] == 100 + 1000 + 5 * 200 + 0.1 * 10000 == 3100.0
    assert rec["main_eq"] == 5000 and rec["sub_eq"] == 2000 and rec["interventions"] == 2


def test_usage_not_found(monkeypatch, tmp_path):
    p = _setup(monkeypatch, tmp_path, {"tag": "t"})
    monkeypatch.setattr(D, "_usage_tag", lambda tag, since=None, sessions=None: dict(sessions=[]))
    D.write_session("t")
    s = json.loads(p.read_text(encoding="utf-8"))["session"]
    assert s["sessions"] == [] and s["note"] == "找不到對話"


def test_quiet_swallows_errors(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, {"tag": "t"})

    def boom(tag):
        raise RuntimeError("x")
    monkeypatch.setattr(D, "_usage_tag", boom)
    D._write_session_quiet("t")
    assert "警告" in capsys.readouterr().err


def test_usage_total_w_and_legacy_args(monkeypatch, tmp_path):
    """session 欄:main_w/sub_w/cost_w 來自 video_cost,total_w = llm_calls cost_w 合計 + 對話 w;--since/--sessions 已不影響歸屬。"""
    calls = [_call("a", "A", "claude-opus-5", 100, 10, 0)]  # cost_eq 150 -> w 750
    p = _setup(monkeypatch, tmp_path, {"tag": "t", "llm_calls": calls})
    monkeypatch.setattr(D, "_usage_tag", lambda tag, since=None, sessions=None: dict(
        sessions=["abcd1234"], turns=1, input=1, cache_creation=0, cache_read=0, output=0, main_eq=1, sub_eq=0, main_w=100.0, sub_w=50.0))
    r = D.write_session("t", since="2026-11-01", sessions=["x"])
    assert r["main_w"] == 100.0 and r["sub_w"] == 50.0 and r["cost_w"] == 150.0 and r["total_w"] == 900.0
    assert json.loads(p.read_text(encoding="utf-8"))["session"]["total_w"] == 900.0


def test_usage_not_found_keeps_llm_total_w(monkeypatch, tmp_path):
    p = _setup(monkeypatch, tmp_path, {"tag": "t", "llm_calls": [_call("a", "A", "claude-opus-5", 100, 10, 0)]})
    monkeypatch.setattr(D, "_usage_tag", lambda tag, since=None, sessions=None: dict(sessions=[]))
    D.write_session("t")
    assert json.loads(p.read_text(encoding="utf-8"))["session"]["total_w"] == 750.0


def test_conv_cost_line_fallback(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, {"tag": "t", "session": {"cost_w": 1500.0, "total_w": 2500.0}})
    import video_cost as VC

    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(VC, "usage_for_tag", boom)
    assert D.conv_cost_line("t") == "對話 w / 全片總 w:1,500 / 2,500"


def test_usage_for_tag_filters(monkeypatch):
    sys.path.insert(0, str(D.P.REPO / "channel" / "fable_token_review" / "scripts"))
    import session_usage as SU

    def mk(i, t0, kind="main", parent=None, tag="t"):
        return dict(id=i, kind=kind, parent=parent, t0=t0, tag=tag, turns=1, inp=1, cc=0, cr=0, out=0, eq=10.0)
    allx = [mk("aaaaaaaa1", "2026-10-01T00:00:00"), mk("bbbbbbbb1", "2026-11-02T00:00:00"),
            mk("sub1", "2026-11-02T00:00:00", "sub", "bbbbbbbb1", "(無)"), mk("cccccccc1", "2026-11-02T00:00:00", tag="other")]
    monkeypatch.setattr(SU, "load_all", lambda: allx)
    monkeypatch.setattr(SU, "summ", lambda s: s)
    assert SU.usage_for_tag("t")["sessions"] == ["aaaaaaaa", "bbbbbbbb"]
    r = SU.usage_for_tag("t", since="2026-10-30")
    assert r["sessions"] == ["bbbbbbbb"] and r["sub_eq"] == 10 and r["main_eq"] == 10
    assert SU.usage_for_tag("t", sessions=["cccccccc"])["sessions"] == ["cccccccc"]
