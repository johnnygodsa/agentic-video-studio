"""配音前預檢 tts_precheck:合成小稿涵蓋 A/B/B2/E/C/D 與 director 卡點原因。
用 tts_env_chattts 的 python 跑(C 項要 pypinyin、B/B2/C 要 opencc,缺套件的項目自動 skip):
tts_env_chattts\\Scripts\\python.exe -X utf8 -m pytest pipeline/tests/test_tts_precheck.py -q"""
import json
import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
import tts_precheck as PC  # noqa: E402


def codes(mtext, eng, watch=None):
    return [(c, lv) for c, lv, _ in PC.check_line(mtext, eng, watch)]


def test_units_pairs_initial_and_final():
    assert PC.units("同[q][í][q][í]刊") == ["同", "[q][í]", "[q][í]", "刊"]
    assert PC.units("[ér]好") == ["[ér]", "好"]


def test_a_repeated_pinyin_token_is_error():
    hits = codes("同一期期刊", "同一[q][í][q][í]刊。")
    assert ("A", "error") in hits


def test_a_plain_reduplication_not_flagged():
    assert codes("謝謝你", "谢谢你。") == []


def test_a_non_adjacent_same_token_ok():
    assert codes("期刊和旗子", "[q][í]刊和[q][í]子。") == []


def test_e_number_enumeration_comma():
    hits = codes("大概兩、三點", "大概两，三点。")
    assert ("E", "warn") in hits and all(lv == "warn" for c, lv in hits)
    assert codes("一、二是什麼", "一，二是什么。")[0][0] == "E"   # 規則只看數字+頓號+數字
    assert codes("第一,再來", "第一，再来。") == []


def test_d_watchlist():
    watch = {"拚": "口語唸 pīn"}
    hits = PC.check_line("他那麼拚", "他那么拚。", watch)
    assert [(c, lv) for c, lv, _ in hits if c == "D"] == [("D", "warn")]
    assert not [h for h in PC.check_line("他那麼拼", "他那么拼。", watch) if h[0] == "D"]


def test_b_de_replaced_by_di_after_break_or_pronoun():
    pytest.importorskip("opencc")
    # 句首/逗號後的「得」被規則換成「的」
    hits = PC.check_line("先看,得照第二期的速度", "先看，的照第二期的速度。")
    assert ("B", "warn") in [(c, lv) for c, lv, _ in hits]
    # 「覺得」本來就唸 de,不列
    assert not [h for h in PC.check_line("我覺得很好", "我觉得很好。") if h[0] == "B"]


def test_b2_v_de_c_marked_dei():
    pytest.importorskip("opencc")
    hits = PC.check_line("就解得開", "就解[d][ěi]开。")
    assert ("B2", "warn") in [(c, lv) for c, lv, _ in hits]
    assert not [h for h in PC.check_line("你得走了", "你[d][ěi]走了。") if h[0] == "B2"]   # 你得 = děi,正常


def test_c_polyphone_context_reading():
    pytest.importorskip("pypinyin")
    pytest.importorskip("opencc")
    hits = PC.check_line("他的行為很奇怪", "他的行为很奇怪。")
    assert not [h for h in hits if h[0] == "C" and "行" in h[2]]   # 行為 xíng 是常見讀音,不列
    hits = PC.check_line("重新開始", "重新开始。")
    assert [h for h in hits if h[0] == "C" and "「重」" in h[2]]     # 重 chóng 不是最常見讀音(zhòng)
    hits = PC.check_line("[ch][óng]新開始", "[ch][óng]新开始。")
    assert not [h for h in hits if h[0] == "C" and "「重」" in h[2]]   # 已標拼音,不列


def test_check_lines_error_first_and_block_reason(tmp_path, monkeypatch):
    items = PC.check_lines([(1, "大概兩、三點", "大概兩、三點", "大概两，三点。"),
                            (2, "同一期期刊", "同一期期刊", "同一[q][í][q][í]刊。")])
    assert [i["level"] for i in items][0] == "error" and items[0]["line"] == 2
    monkeypatch.setattr(PC.P, "PROJECTS", tmp_path)
    assert PC.block_reason("t1") is None   # 沒有報告
    f = PC.out_path("t1")
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    r = PC.block_reason("t1")
    assert "error 1 項" in r and "第 2 行" in r and "第 1 行" not in r   # warn 不進卡點原因
    f.write_text(json.dumps({"items": [i for i in items if i["level"] == "warn"]}), encoding="utf-8")
    assert PC.block_reason("t1") is None


def test_run_end_to_end_with_engine(tmp_path, monkeypatch):
    """真走 script_lines + engine_text(要 torch,系統 python 沒有就 skip);用 CV 既有片的稿。"""
    pytest.importorskip("torch")
    pytest.importorskip("opencc")
    import paths
    tag = next((t for t in ("wow_realm", "gow_budget") if (paths.REPO / t / "script.txt").exists()), None)
    if not tag:
        pytest.skip("沒有可用的既有稿")
    monkeypatch.setattr(PC.P, "PROJECTS", tmp_path)
    rep = PC.run(tag)
    assert rep["lines"] > 0 and rep["errors"] + rep["warns"] == len(rep["items"])
    assert json.loads(PC.out_path(tag).read_text(encoding="utf-8"))["lines"] == rep["lines"]
