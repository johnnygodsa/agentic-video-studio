"""review_md 測試:tmp 目錄假三份清單,驗三節與「(無)」;警告項彙整。python -X utf8 -m pytest pipeline/tests/test_review_md.py -q"""
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import review_md as RV  # noqa: E402


def _stub(monkeypatch, tmp_path):
    od, bd, pj = tmp_path / "out", tmp_path / "build", tmp_path / "projects"
    for d in (od, bd, pj / "t"):
        d.mkdir(parents=True)
    fake = types.SimpleNamespace(output_dir=lambda tag: od, build_dir=lambda tag: bd, PROJECTS=pj, REPO=tmp_path)
    monkeypatch.setattr(RV, "P", fake)
    return od, bd, pj / "t"


def test_three_sections_full(monkeypatch, tmp_path):
    od, bd, pj = _stub(monkeypatch, tmp_path)
    (od / "listen_v1.txt").write_text("00:07|2|逗號靠插入|彭博報導\n", encoding="utf-8")
    (od / "look_v1.md").write_text("# t v1 畫面優先看清單\n- 00:10 句3 x\n", encoding="utf-8")
    (od / "decide_v1.md").write_text("# 要你決定的唸法\n英文唸法 0 筆\n", encoding="utf-8")
    (pj / "tts_report.json").write_text(json.dumps({"below_min": [{"unit": 3}], "rate_out_of_range": [], "failed_qc": []}), encoding="utf-8")
    (bd / "structure.json").write_text(json.dumps({"warnings": [{"code": "BLOCK_SEC", "line": 66, "text": "75 秒"}]}), encoding="utf-8")
    txt = RV.build("t", "v1", facts_lines=["  警告 弱狀態無小字 2 句", "[facts_check] 連結 28/30 句、未連結 2、狀態不符 0、錯誤 0"])
    i1, i2, i3 = txt.index("## 聽"), txt.index("## 看"), txt.index("## 決定")
    assert i1 < i2 < i3
    assert "00:07|2|逗號靠插入|彭博報導" in txt[i1:i2] and "below_min" in txt[i1:i2]
    assert "畫面優先看清單" in txt[i2:i3] and "[BLOCK_SEC] 句66" in txt[i2:i3]
    assert "弱狀態無小字 2 句" in txt[i2:i3] and "未連結 2" in txt[i2:i3]
    assert "要你決定的唸法" in txt[i3:]


def test_missing_look_says_none_and_run_writes_file(monkeypatch, tmp_path):
    od, bd, pj = _stub(monkeypatch, tmp_path)
    (od / "listen_v1.txt").write_text("00:01|1|x|y\n", encoding="utf-8")
    (od / "decide_v1.md").write_text("決定內容\n", encoding="utf-8")   # --tts-review:沒有 look
    monkeypatch.setattr(RV, "run_facts_check", lambda tag: [])
    txt = RV.build("t", "v1", facts_lines=[])
    assert "## 看\n\n(無)" in txt and "決定內容" in txt
    msg = RV.run("t", "v1")
    assert (od / "review_v1.md").exists() and "無內容:看" in msg


def test_all_missing(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path)
    txt = RV.build("t", "v9", facts_lines=[])
    assert txt.count("(無)") == 3


def test_facts_warnings_filters_zero():
    assert RV.facts_warnings(["  警告 弱狀態無小字 0 句", "[facts_check] 連結 30/30 句 (100%)、未連結 0、狀態不符 0、錯誤 0"]) == []


def test_listen_new_format_must_first_other_folded(monkeypatch, tmp_path):
    od, bd, pj = _stub(monkeypatch, tmp_path)
    (od / "listen_v1.txt").write_text(
        "## 必聽(2 句:x)\n00:20|4|品管重錄過|原文四\n01:22|15|E4耳朵:runon 市後沒停|原文十五\n"
        "## 其他(3 句:y)\n語速(1):1\n逗號靠插入(2):2,3\n", encoding="utf-8")
    txt = RV.build("t", "v1", facts_lines=[])
    h = txt[txt.index("## 聽"):txt.index("## 看")]
    assert "### 必聽(2 句" in h and "01:22|15|" in h and "原文四" in h
    assert h.index("### 必聽") < h.index("<details>") < h.index("逗號靠插入(2):2,3")   # 必聽在最前、其他折疊在後
    assert "原文" not in h[h.index("<details>"):]   # 其他節不逐句列原文
    assert "\n## 必聽" not in h and "\n## 其他" not in h   # 原始標題行不外漏(只剩 ### 小節)


def test_split_listen_legacy_and_empty():
    assert RV.split_listen("00:07|2|逗號靠插入|彭博報導\n") == (None, None)
    assert RV.listen_blocks("", "v1") == []
    must, other = RV.split_listen("## 必聽(0 句)\n## 其他(0 句)\n")
    assert must == [] and other == []
    assert "(沒有)" in RV.listen_blocks("## 必聽(0 句)\n## 其他(0 句)\n", "v1")[0]
