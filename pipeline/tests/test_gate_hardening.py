"""Phase 2b 閘門補強測試:new_synth 解析(A)、C7 visual_check 錯誤中止、C15 品管未過硬擋、deliver 的 gate_d 判斷(B)。
不配音、不渲染、不用顯示卡。python -X utf8 -m pytest pipeline/tests/test_gate_hardening.py -q"""
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deliver as D  # noqa: E402
import make_version as MV  # noqa: E402


# ---- A:new_synth ----
def test_new_synth_cosy():
    tail = ["TTS 快取[cosy3]: 94 行 = 94 個配音單位;命中 80、需合成或重新檢驗 14",
            "TTS[cosy3]: 重新檢驗既有音檔 9 個、新合成 5 個 (cosyB +18%, qc9)"]
    assert MV.parse_new_synth(tail) == 5


def test_new_synth_all_cached_is_zero():
    assert MV.parse_new_synth(["TTS 快取[cosy3]: 94 行 = 94 個配音單位;命中 94、需合成或重新檢驗 0"]) == 0


def test_new_synth_edge_and_sum():
    assert MV.parse_new_synth(["TTS[edge]: 產生 7 句 (v +18%)"]) == 7
    assert MV.parse_new_synth(["新合成 2 個", "新合成 3 個"]) == 5


def test_new_synth_unparsable_is_none():
    assert MV.parse_new_synth(["沒有相關字樣"]) is None
    assert MV.parse_new_synth(None) is None


# ---- B:C7 ----
def test_visual_error_lines():
    out = ["[visual_check] t:3 句 | x 1", "  錯誤 E1 x2", "    句3(行9) @def 未定義", "    句5(行11) hl 找不到",
           "  警告 W2 x1", "    句1(行2) 小問題", "[visual_check] 警告 1 項、錯誤 2 項"]
    got = MV.visual_error_lines(out)
    assert len(got) == 3 and "未定義" in got[1] and "小問題" not in "".join(got)


def test_prechecks_visual_rc1_aborts_but_warning_does_not(monkeypatch):
    monkeypatch.setattr(MV, "precheck_cmds", lambda tag: [("visual_check", ["x"])])
    err_out = ["  錯誤 E1 x1", "    句3(行9) @def 未定義", "[visual_check] 警告 0 項、錯誤 1 項"]
    monkeypatch.setattr(MV, "run_cmd", lambda cmd, log: (1, err_out))
    ok, summ, errs = MV.run_prechecks("t", None)
    assert not ok and any("未定義" in e for e in errs) and "中止" in summ[0]
    warn_out = ["  警告 W1 x1", "    句1(行2) x", "[visual_check] 警告 1 項、錯誤 0 項"]
    monkeypatch.setattr(MV, "run_cmd", lambda cmd, log: (0, warn_out))
    ok, summ, errs = MV.run_prechecks("t", None)
    assert ok and not errs
    warns = []
    monkeypatch.setattr(MV, "log_warn", lambda tag, step, msg: warns.append((tag, step)))   # 不寫真的 production.json
    monkeypatch.setattr(MV, "run_cmd", lambda cmd, log: (2, ["Traceback"]))   # 崩潰:只標執行失敗,不中止
    ok, summ, errs = MV.run_prechecks("t", None)
    assert ok and "執行失敗" in summ[0] and warns == [("t", "C7 visual_check")]


# ---- B:C15 ----
def _fake_dirs(monkeypatch, tmp_path, failed, frozen):
    (tmp_path / "tts_qc.json").write_text(json.dumps({"failed": failed}), encoding="utf-8")
    fz = tmp_path / "freeze.json"
    if frozen:
        fz.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(MV.P, "build_dir", lambda tag: tmp_path)
    monkeypatch.setattr(MV.FZ, "freeze_path", lambda tag: fz)


def test_c15_failed_unfrozen_blocks(monkeypatch, tmp_path):
    _fake_dirs(monkeypatch, tmp_path, [{"idx": "5.2", "fails": ["asr", "voice"]}], frozen=False)
    msg = "\n".join(MV.qc_gate_problems("t"))
    assert "5.2" in msg and "asr/voice" in msg


def test_c15_frozen_or_clean_passes(monkeypatch, tmp_path):
    _fake_dirs(monkeypatch, tmp_path, [{"idx": 1, "fails": ["asr"]}], frozen=True)
    assert MV.qc_gate_problems("t") == []
    (tmp_path / "freeze.json").unlink()
    (tmp_path / "tts_qc.json").write_text(json.dumps({"failed": []}), encoding="utf-8")
    assert MV.qc_gate_problems("t") == []
    (tmp_path / "tts_qc.json").unlink()
    assert MV.qc_gate_problems("t") == []   # 沒有品管檔不擋(交給其他步驟)


# ---- B:deliver gate_d ----
def _fake_gates(monkeypatch, items=None, exc=None):
    gd = types.ModuleType("gates.gate_d")

    def run(tag, ver, ctx=None):
        if exc:
            raise exc
        return items
    gd.run = run
    pkg = types.ModuleType("gates")
    pkg.gate_d = gd
    monkeypatch.setitem(sys.modules, "gates", pkg)
    monkeypatch.setitem(sys.modules, "gates.gate_d", gd)


def test_gate_d_all_ok(monkeypatch):
    _fake_gates(monkeypatch, [dict(id="a", ok=True, note="n"), dict(id="b", ok=True, note="")])
    assert D.gate_d_check("t", "v1") is True


def test_gate_d_one_bad_blocks_and_prints(monkeypatch, capsys):
    _fake_gates(monkeypatch, [dict(id="a", ok=True, note=""), dict(id="片長", ok=False, note="5.8 分")])
    assert D.gate_d_check("t", "v1") is False
    assert "不過 片長: 5.8 分" in capsys.readouterr().out


def test_gate_d_import_failure_is_not_ok(monkeypatch):
    monkeypatch.setitem(sys.modules, "gates", None)   # import 會 ImportError
    monkeypatch.delitem(sys.modules, "gates.gate_d", raising=False)
    assert D.gate_d_check("t", "v1") is False


def test_gate_d_exception_is_not_ok(monkeypatch):
    _fake_gates(monkeypatch, exc=RuntimeError("boom"))
    assert D.gate_d_check("t", "v1") is False


def test_gate_d_skip(monkeypatch, capsys):
    _fake_gates(monkeypatch, [dict(id="x", ok=False, note="")])
    assert D.gate_d_check("t", "v1", skip=True) is True
    assert "--skip-gate-d" in capsys.readouterr().err
