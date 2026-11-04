"""line_fix 改句測試:注入假 call,不呼叫 LLM、不用 GPU。python -X utf8 -m pytest pipeline/tests/test_line_fix.py -q"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
import line_fix as LF  # noqa: E402
import paths as P  # noqa: E402
import pron_memory as PM  # noqa: E402
import speakable as S  # noqa: E402

OLD_B = "那個角色耶,在 2024 年賣出了 150 萬套的銷量,真的很驚人。"
FIXED_B = "那個角色,在 2024 年賣出了 150 萬套的銷量,真的很驚人。"
TAIL_B = ' ;; {"hl": ["150 萬套"], "f": ["F1"]}'
CLICHE_D = "隨著時代發展,這款遊戲的表現讓人覺得很可惜,畫面也還可以。"
SCRIPT = (
    "# 一\n"                                                          # L1
    "@say 2024 年=二零二四年\n"                                       # L2
    "@say 150 萬套=一百五十萬套\n"                                    # L3
    "a|這款遊戲的畫面做得很細緻,玩家們都說戰鬥打起來很爽快。\n"      # L4 乾淨
    f"b|{OLD_B}{TAIL_B}\n"                                            # L5 BAD_PARTICLE
    "c|最後這一句是乾淨的收尾,沒有任何問題可以挑剔的地方。\n"        # L6 乾淨
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    monkeypatch.setattr(P, "REPO", tmp_path)
    monkeypatch.setattr(P, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(S, "_backlog_rows", lambda: [])
    monkeypatch.setattr(PM, "scan", lambda text, path=None: [])
    monkeypatch.setattr(S, "_unregistered", lambda say: ["Zxqvt"] if "Zxqvt" in say else [])
    (tmp_path / "t").mkdir()
    f = tmp_path / "t" / "script.txt"
    f.write_bytes(SCRIPT.encode("utf-8"))
    return f


def R(fixes, ok=True, error="", limited=False):
    return SimpleNamespace(ok=ok, data={"fixes": fixes}, error=error, limited=limited)


class Fake:
    """依序回覆(最後一個重複使用);記下每次的 prompt 與參數。"""
    def __init__(self, *replies):
        self.replies, self.prompts, self.kw = list(replies), [], []

    def __call__(self, tag, fn, prompt, **kw):
        self.prompts.append(prompt)
        self.kw.append((tag, fn, kw))
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return r(prompt) if callable(r) else r


def fix(items, mode="lint", **kw):
    return LF.fix_lines("t", items, mode, **kw)


def fb(text, note="x", line=5):
    return R([dict(line=line, new_text=text, note=note)])


def test_happy_path_only_changes_text(env):
    before = env.read_bytes().decode("utf-8").split("\n")
    fk = Fake(fb(FIXED_B, "拿掉耶"))
    r = fix([dict(line=5, reasons=["BAD_PARTICLE 配音唸不出的語助詞"])], call=fk)
    assert r["fixed"] == [dict(line=5, old=OLD_B, new=FIXED_B)] and r["unresolved"] == []
    after = env.read_bytes().decode("utf-8").split("\n")
    assert len(before) == len(after) and [i for i, (a, b) in enumerate(zip(before, after)) if a != b] == [4]
    assert after[4] == "b|" + FIXED_B + TAIL_B   # 標籤與行尾 json 原樣
    tag, fn, kw = fk.kw[0]
    assert (tag, fn, kw["model"]) == ("t", "line_fix", "sonnet") and kw["schema"] is LF.SCHEMA and len(fk.prompts) == 1


def test_warn_log_keys(env):
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=Fake(fb(FIXED_B, "拿掉耶")))
    w = r["warn_log"]
    assert [x["key"] for x in w] == ["lint:5:BAD_PARTICLE"] and w[0]["action"] == "fixed" and w[0]["reason"] == "拿掉耶" and w[0]["at"]


def test_prompt_has_context_and_only_targets(env):
    fk = Fake(fb(FIXED_B))
    fix([dict(line=5, reasons=["耶"])], call=fk)
    p = fk.prompts[0]
    assert "這款遊戲的畫面做得很細緻" in p and "最後這一句是乾淨的收尾" in p   # 前後各一句
    items = json.loads(p[p.index("[\n"):p.rindex("\n]") + 2])
    assert [i["line"] for i in items] == [5] and items[0]["must_keep"] == ["150 萬套"] and "150 萬套" in items[0]["say_keys"]


def test_crlf_preserved(env):
    env.write_bytes(SCRIPT.replace("\n", "\r\n").encode("utf-8"))
    fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=Fake(fb(FIXED_B)))
    data = env.read_bytes()
    assert data.count(b"\r\n") == SCRIPT.count("\n") and b"\n" not in data.replace(b"\r\n", b"")
    assert data.decode("utf-8").replace("\r\n", "\n") == SCRIPT.replace(OLD_B, FIXED_B)


def test_bom_preserved(env):
    env.write_bytes(b"\xef\xbb\xbf" + SCRIPT.encode("utf-8"))
    fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=Fake(fb(FIXED_B)))
    assert env.read_bytes().startswith(b"\xef\xbb\xbf# ") and FIXED_B in env.read_text(encoding="utf-8")


def test_number_change_rejected_then_retried_with_reason(env):
    fk = Fake(fb("那個角色在 2024 年賣出了 180 萬套的銷量,真的很驚人。"), fb(FIXED_B))
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=fk)
    assert len(fk.prompts) == 2 and "數字集合不同" in fk.prompts[1] and "上一版被退回" in fk.prompts[1]
    assert [f["line"] for f in r["fixed"]] == [5]


def test_unresolved_after_max_rounds_writes_nothing(env):
    before = env.read_bytes()
    fk = Fake(fb("那個角色在 2024 年賣出了 180 萬套,真的很驚人。"))
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=fk)
    assert len(fk.prompts) == LF.MAX_ROUNDS and r["fixed"] == [] and r["warn_log"] == []
    assert r["unresolved"][0]["line"] == 5 and "數字集合不同" in r["unresolved"][0]["why"]
    assert env.read_bytes() == before


@pytest.mark.parametrize("new, key", [
    ("那個角色在 2024 年賣出了很多的銷量,真的很驚人。", "數字集合不同"),                          # 丟了 150 萬套
    (OLD_B, "仍有硬項"),                                                                        # 耶還在
    ("那個角色在 2024 年賣出了 150 萬套的銷量,真的很驚人 Zxqvt。", "en_unregistered"),           # 新增未登錄英文
    ("那個角色在 2024 年賣出了 150 萬套的銷量\n,真的很驚人。", "不可含"),                          # 換行
    ("那個角色在 2024 年賣出了 150 萬套的銷量 ;; {}真的很驚人。", "不可含"),                       # 夾帶行尾
    ("", "空的"),
])
def test_hard_checks_reject(env, new, key):
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=Fake(fb(new)))
    assert r["fixed"] == [] and key in r["unresolved"][0]["why"]


def test_hl_must_survive(env):
    env.write_bytes(SCRIPT.replace('"hl": ["150 萬套"]', '"hl": ["真的很驚人"]').encode("utf-8"))
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=Fake(fb("那個角色在 2024 年賣出了 150 萬套的銷量,讓人嚇一跳。")))
    assert "hl 必留" in r["unresolved"][0]["why"]


def test_new_lint_code_rejected(env):
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=Fake(fb("那個角色在 2024 年賣出了 150 萬套的銷量,這標誌著新時代。")))
    assert "新增了原本沒有" in r["unresolved"][0]["why"] and "CLICHE" in r["unresolved"][0]["why"]


def test_named_reason_must_clear(env):
    env.write_bytes((SCRIPT + f"d|{CLICHE_D}\n").encode("utf-8"))
    r = fix([dict(line=7, reasons=["CLICHE 套話"])], call=Fake(fb(CLICHE_D.replace("時代發展", "版本更新"), line=7)))
    assert r["fixed"] == [] and "CLICHE" in r["unresolved"][0]["why"]   # 開頭「隨著」還在 -> CLICHE 沒消


def test_named_reason_cleared_is_fixed(env):
    env.write_bytes((SCRIPT + f"d|{CLICHE_D}\n").encode("utf-8"))
    new = "版本更新以後,這款遊戲的表現讓人覺得很可惜,畫面也還可以。"
    r = fix([dict(line=7, reasons=["CLICHE 套話"])], call=Fake(fb(new, line=7)))
    assert [f["new"] for f in r["fixed"]] == [new] and ("lint:7:CLICHE", "fixed") in [(w["key"], w["action"]) for w in r["warn_log"]]


def test_keep_requires_note_and_no_block(env):
    env.write_bytes((SCRIPT + f"d|{CLICHE_D}\n").encode("utf-8"))
    r = fix([dict(line=7, reasons=["CLICHE 套話"])], call=Fake(fb(CLICHE_D, "", line=7)))
    assert "note" in r["unresolved"][0]["why"]
    r = fix([dict(line=7, reasons=["CLICHE 套話"])], call=Fake(fb(CLICHE_D, "這句是引述原文,不改", line=7)))
    assert r["fixed"] == [] and r["kept"] == [dict(line=7, note="這句是引述原文,不改")] and r["unresolved"] == []
    assert [(w["key"], w["action"]) for w in r["warn_log"]] == [("lint:7:CLICHE", "kept")]
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=Fake(fb(OLD_B, "想留")))
    assert r["kept"] == [] and "仍有硬項" in r["unresolved"][0]["why"]   # 有 block 不能用保留混過


def test_frozen_refused(env):
    d = env.parent.parent / "projects" / "t"
    d.mkdir(parents=True)
    (d / "freeze.json").write_text(json.dumps(dict(narration_sha="x", frozen_at="2026-10-30T00:00:00")), encoding="utf-8")
    before = env.read_bytes()
    fk = Fake(R([]))
    r = fix([dict(line=5, reasons=["x"])], call=fk)
    assert r["refused"] and fk.prompts == [] and r["fixed"] == [] and r["unresolved"][0]["line"] == 5 and env.read_bytes() == before


def test_dry_run_does_not_write(env):
    before = env.read_bytes()
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=Fake(fb(FIXED_B)), dry_run=True)
    assert [f["line"] for f in r["fixed"]] == [5] and env.read_bytes() == before


def test_not_spoken_line_and_say_field(env):
    env.write_bytes((SCRIPT + 'd|很長很長的一句旁白用來測試行尾 say 欄位不能改字幕,後面還要再補一些字。 ;; {"say": "唸法"}\n').encode("utf-8"))
    fk = Fake(R([]))
    r = fix([dict(line=1, reasons=["x"]), dict(line=7, reasons=["x"]), dict(line=99, reasons=["x"])], call=fk)
    assert fk.prompts == [] and {u["line"] for u in r["unresolved"]} == {1, 7, 99}
    assert "say" in [u for u in r["unresolved"] if u["line"] == 7][0]["why"]


def test_call_failure_and_garbage(env):
    fk = Fake(R(None, ok=False, error="用量上限", limited=True))
    r = fix([dict(line=5, reasons=["x"])], call=fk)
    assert len(fk.prompts) == 1 and r["unresolved"][0]["why"] == "用量上限"
    fk = Fake(SimpleNamespace(ok=True, data={"nope": 1}, error="", limited=False))
    r = fix([dict(line=5, reasons=["x"])], call=fk)
    assert len(fk.prompts) == LF.MAX_ROUNDS and "fixes" in r["unresolved"][0]["why"]


def test_plain_list_reply_accepted(env):
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=Fake([dict(line=5, new_text=FIXED_B, note="x")]))
    assert [f["line"] for f in r["fixed"]] == [5]


def test_missing_line_in_reply_retried(env):
    fk = Fake(R([]), fb(FIXED_B))
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=fk)
    assert "沒有回這句" in fk.prompts[1] and [f["line"] for f in r["fixed"]] == [5]


def test_only_pending_lines_resent(env):
    env.write_bytes((SCRIPT + f"d|{CLICHE_D}\n").encode("utf-8"))
    good_d = "版本更新以後,這款遊戲的表現讓人覺得很可惜,畫面也還可以。"
    fk = Fake(R([dict(line=5, new_text=FIXED_B, note="x"), dict(line=7, new_text=CLICHE_D, note="")]),
              R([dict(line=7, new_text=good_d, note="x")]))
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"]), dict(line=7, reasons=["CLICHE"])], call=fk)
    assert sorted(f["line"] for f in r["fixed"]) == [5, 7] and len(fk.prompts) == 2
    p2 = fk.prompts[1]
    assert [i["line"] for i in json.loads(p2[p2.index("[\n"):p2.rindex("\n]") + 2])] == [7]


def test_file_changed_during_call_is_not_overwritten(env):
    def sneaky(prompt):
        env.write_bytes(SCRIPT.replace("真的很驚人", "有夠驚人").encode("utf-8"))
        return fb(FIXED_B)
    r = fix([dict(line=5, reasons=["BAD_PARTICLE"])], call=Fake(sneaky))
    assert r["fixed"] == [] and "被改動" in r["unresolved"][0]["why"] and r["warn_log"] == []
    assert "有夠驚人" in env.read_text(encoding="utf-8")


def test_bad_mode_and_items_merge(env):
    with pytest.raises(ValueError):
        fix([dict(line=5, reasons=["x"])], "nope", call=Fake(R([])))
    fk = Fake(fb(FIXED_B))
    r = fix([dict(line=5, reasons=["a"]), dict(line=5, reasons=["BAD_PARTICLE"])], call=fk)   # 同一句兩筆合併成一筆
    assert len(r["fixed"]) == 1 and '"a"' in fk.prompts[0]


def test_qc_mode_segment(env):
    fk = Fake(fb(FIXED_B))
    fix([dict(line=5, reasons=["品管未過 content"])], "qc", call=fk)
    assert fk.kw[0][2]["seg"] == "C" and "配音品管未過" in fk.prompts[0]


def test_cli_dry_run(env, monkeypatch, capsys):
    monkeypatch.setattr(LF, "_default_call", lambda: Fake(fb(FIXED_B)))
    assert LF.main(["t", "--lines", "5", "--reason", "拿掉耶", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "(dry-run)" in out and FIXED_B in out and "未寫檔" in out
    monkeypatch.setattr(LF, "_default_call", lambda: Fake(R([])))
    assert LF.main(["t", "--lines", "5", "--reason", "x"]) == 1
