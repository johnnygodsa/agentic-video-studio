"""P2 改稿回歸守門:歸屬與確定程度詞不得被刪(director_ab.regress_why e 項):python -X utf8 pipeline/tests/test_regress_attrib.py
範例句取自 projects/door_load 的 editor_review_r3 條目(line 18「拿掉『有位玩家說』」、line 33/39「可能」)。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director_ab as AB  # noqa: E402

OLD = "有位玩家說,一扇門要是只演 2 秒左右,你就會覺得被騙了。"
NEW = "一扇門要是只演 2 秒左右,你就會覺得被騙了。"


def test_dropped_attribution_is_rejected():
    why = AB.regress_why(OLD, NEW, reason="連貫:這句沒接住上一句")
    assert why and "歸屬詞不見了" in why and "玩家說" in why
    why2 = AB.regress_why("開太快會暴露位置,開太慢又可能被抓,以前你在等。", "開太快會暴露位置,開太慢又被抓,以前你在等。", reason="代稱")
    assert why2 and "可能" in why2


def test_reason_mentions_attribution_passes():
    assert AB.regress_why(OLD, NEW, reason="歸屬改放畫面小字,旁白不唸") is None
    assert AB.regress_why(OLD, NEW, reason="這是推論不是玩家原話") is None
    assert AB.regress_why(OLD, NEW, reason="確定程度已在上一句交代") is None


def test_kept_attribution_passes():
    assert AB.regress_why(OLD, "有位玩家說,一扇門只演 2 秒左右,你就會覺得被騙了。", reason="連貫") is None
    assert AB.regress_why("開太快會暴露位置,開太慢又可能被抓。", "開太快會暴露位置,開太慢也可能被抓。", reason="代稱") is None


def test_yue_false_positives():
    # 「約定」「簽約」不算確定程度詞;刪掉不該被退
    assert AB.regress_why("兩邊的約定寫得很死,雙方簽約後就不能改了。", "兩邊的規定寫得很死,雙方簽字後就不能改了。", reason="換詞") is None
    # 「大約」改「約」:改後仍有「約」,不算消失
    assert AB.regress_why("大約三個月後才有消息,官方沒說細節。", "約三個月後才有消息,官方沒說細節。", reason="換詞") is None
    # 真的「約」(大概)被刪才退
    assert "歸屬詞不見了" in (AB.regress_why("約三個月後才有消息,官方沒說細節。", "三個月後才有消息,官方沒說細節。", reason="換詞") or "")


def test_revise_prompt_has_hedge_rule(monkeypatch):
    seen = {}
    monkeypatch.setattr(AB, "_need", lambda r, what: r)
    monkeypatch.setattr(AB, "_llm", lambda tag, fn, prompt, **kw: seen.setdefault("p", prompt) and type("R", (), {"data": {}})())
    AB._revise_call("x", [], (), "審稿條目", "B")
    assert "不得刪除或弱化句中的歸屬與確定程度詞" in seen["p"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
