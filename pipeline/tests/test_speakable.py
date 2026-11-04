"""speakable 可唸性預檢測試(不合成、不用 GPU、不呼叫 LLM):python -X utf8 -m pytest pipeline/tests/test_speakable.py -q"""
import json
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
import paths as P  # noqa: E402
import pron_memory as PM  # noqa: E402
import speakable as S  # noqa: E402


def codes(hits, sev=None):
    return [h["code"] for h in hits if sev is None or h["severity"] == sev]


def no_registry(monkeypatch):
    """記憶、backlog、未登錄英文都換成空的,讓測試只看被測的那一項。"""
    monkeypatch.setattr(S, "_unregistered", lambda say: [])
    monkeypatch.setattr(S, "_backlog_rows", lambda: [])
    monkeypatch.setattr(PM, "scan", lambda text, path=None: [])


GOOD = "這一款大作的預購,要不要按下去,算完這筆帳再決定。"


def test_plain_sentence_has_no_hits(monkeypatch):
    no_registry(monkeypatch)
    assert S.check_line(GOOD) == []


def test_hit_shape(monkeypatch):
    no_registry(monkeypatch)
    h = S.check_line("EA 也是。")[0]
    assert set(h) == {"code", "severity", "span", "why"} and h["severity"] in ("err", "warn")


def test_short_line_warns(monkeypatch):
    no_registry(monkeypatch)
    assert "line_short" in codes(S.check_line("也是這樣。"), "warn")
    assert "line_short" not in codes(S.check_line(GOOD))


def test_unregistered_english_is_err(monkeypatch):
    no_registry(monkeypatch)
    monkeypatch.setattr(S, "_unregistered", lambda say: ["Zxqvt"])
    assert codes(S.check_line(GOOD + "Zxqvt。"), "err") == ["en_unregistered"]


def test_unregistered_english_real_registry():
    # 沒有 mock:cosy_terms 一定沒有這個亂碼詞
    assert "en_unregistered" in codes(S.check_line("這是一個很長很長的測試句子裡面放了 Zxqvtwk 這個字。"), "err")


def test_memory_bad_rewrite_is_err_but_undetermined_is_silent(monkeypatch):
    no_registry(monkeypatch)
    bad = PM.make_entry("戲", "遊", "規", state="bad", fix=dict(type="rewrite", value="x"), note="唸成 xi4")
    und = PM.make_entry("得", "覺", "她", state="undetermined", fix=dict(type="mark", value="的"))
    monkeypatch.setattr(PM, "scan", lambda text, path=None: [(0, bad)])
    h = S.check_line(GOOD)
    assert codes(h, "err") == ["memory_bad"] and h[0]["span"] == "遊戲規"
    monkeypatch.setattr(PM, "scan", lambda text, path=None: [(0, und)])
    assert "memory_bad" not in codes(S.check_line(GOOD)) and codes(S.check_line(GOOD), "err") == []


def test_bad_with_mark_fix_is_auto_applied_not_err(monkeypatch):
    no_registry(monkeypatch)
    e = PM.make_entry("戲", "遊", "規", state="bad", fix=dict(type="mark", value="[x][ì]"))
    monkeypatch.setattr(PM, "scan", lambda text, path=None: [(0, e)])
    assert codes(S.check_line(GOOD), "err") == []


def test_backlog_pending_context_warns(monkeypatch):
    no_registry(monkeypatch)
    monkeypatch.setattr(S, "_backlog_rows", lambda: [("打", "快打二", "2", "sf_dying×2")])
    h = S.check_line("這一段的快打二連擊要按對時間才打得出來。")
    assert [x["code"] for x in h if x["code"] == "backlog"] == ["backlog"] and h[0]["span"] == "快打二"


def test_backlog_rows_only_pending(tmp_path, monkeypatch):
    f = tmp_path / "pron_backlog.md"
    f.write_text("| 字 | 語境詞 | 證據 | 命中次數 | 狀態 | 來源片 | 日期 |\n|---|---|---|---|---|---|---|\n"
                 "| 打 | 快打二 | polyphone strong | 2 | 待規則 | sf×2 | 2026-10-29 |\n"
                 "| 哩 | 咕哩 | polyphone strong | 7 | 已規則 | dei×7 | 2026-10-29 |\n", encoding="utf-8")
    monkeypatch.setattr(S.C, "BACKLOG_FILE", f)
    assert S._backlog_rows() == [("打", "快打二", "2", "sf×2")]


def test_digits_dense_warns(monkeypatch):
    no_registry(monkeypatch)
    assert "num_dense" in codes(S.check_line("這個伺服器同時線上有 123456 位玩家而且還在一直往上漲喔。"))
    assert "num_dense" not in codes(S.check_line("這個伺服器同時線上有 12 位玩家而且還在一直往上漲喔你看。"))


def test_say_replacement_removes_digits(monkeypatch):
    no_registry(monkeypatch)
    t = "這個伺服器同時線上有 123456 位玩家而且還在一直往上漲喔。"
    assert "num_dense" not in codes(S.check_line(t, [("123456 位", "十二萬三千四百五十六位")]))


def test_clause_and_line_long(monkeypatch):
    no_registry(monkeypatch)
    h = codes(S.check_line("這是一個完全沒有任何標點符號而且長度明顯超過二十個字的超級超級長的一整段子句。"))
    assert "clause_long" in h
    long_line = ",".join(["這一段有十二個字的短子句"] * 5) + "。"
    h = codes(S.check_line(long_line))
    assert "line_long" in h and "clause_long" not in h


def test_en_tail(monkeypatch):
    no_registry(monkeypatch)
    assert "en_tail" in codes(S.check_line("這個遊戲只在其他平台上推出沒有在這邊上市,主要是為了 Steam"))
    assert "en_tail" not in codes(S.check_line("這個遊戲只在其他平台上推出沒有在這邊上市,主要是為了 Steam 玩家。"))


def test_features_poly_uses_rules_memory_and_skips_common(monkeypatch):
    no_registry(monkeypatch)
    f = S.features("你要的卡片在這裡")
    chars = {c for _p, c in f["poly"]}
    assert "要" not in chars   # 高頻字略過
    assert "卡" in chars
    # 詞表蓋到的位置不算未覆蓋
    f2 = S.features("這個遊戲很好玩")
    assert "戲" not in {c for _p, c in f2["poly"]}


def test_explain_short():
    s = S.explain()
    assert 0 < len(s.splitlines()) <= 40 and "err" in s


def write_script(root, tag, body):
    d = root / tag
    d.mkdir(parents=True, exist_ok=True)
    (d / "script.txt").write_text(body, encoding="utf-8")


def test_check_tag_line_numbers_and_say(tmp_path, monkeypatch):
    no_registry(monkeypatch)
    monkeypatch.setattr(S, "known_chars", lambda: set())   # 不吃實際 pron_backlog/記憶(會隨資料長出 上/有/一 等字),只看行號與 @say
    monkeypatch.setattr(P, "ROOT", tmp_path)
    write_script(tmp_path, "t", "@title T\n@say 123456 位=十二萬三千四百五十六位\n# 一\n"
                                "a|線上同時有 123456 位玩家,而且還在一直往上漲喔,真的很誇張。\n"
                                "b|也是。 ;; {\"hl\": [\"也是\"]}\n")
    r = S.check_tag("t")
    assert r["n_lines"] == 2 and r["errors"] == 0 and r["warns"] == 1
    assert [x["line"] for x in r["lines"]] == [5] and codes(r["lines"][0]["hits"]) == ["line_short"]


def test_main_json_and_exit_code(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    monkeypatch.setattr(S, "_backlog_rows", lambda: [])
    monkeypatch.setattr(S, "_unregistered", lambda say: ["Zxqvt"])
    write_script(tmp_path, "t", "# 一\na|這一款大作的預購,要不要按下去,算完這筆帳再決定。\n")
    assert S.main(["t", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["errors"] == 1 and out["lines"][0]["hits"][0]["code"] == "en_unregistered"


def test_calibrate_counts_goals(tmp_path, monkeypatch):
    no_registry(monkeypatch)
    d = tmp_path / "x"
    d.mkdir()
    recs = [dict(text="也是這樣。", retries=3, sim=0.9, attempts=[dict(fails=["content"])]),
            dict(text=GOOD, retries=0, sim=1.0, attempts=[dict(fails=[])])]
    (d / "tts_qc.json").write_text(json.dumps(dict(records=recs)), encoding="utf-8")
    res = S.calibrate(tmp_path)
    assert res["n"] == 2 and res["base"]["retry3"] == (1, 2) and res["base"]["text"] == (1, 2) and res["base"]["sim"] == (1, 2)
    short = [r for r in res["rows"] if r[0] == "units" and r[1] == "[0,16)"][0]
    assert short[2] == 1 and short[3]["text"] == (1, 1)


# ---------- 片名、主體名豁免 ----------

def test_backlog_inside_title_not_reported(monkeypatch):
    no_registry(monkeypatch)
    monkeypatch.setattr(S, "_backlog_rows", lambda: [("之", "影之", "2", "pbz×2")])
    assert "backlog" not in codes(S.check_line("開賣第三天《影之刃零》的同時在線還在往上走沒有停下來。"))
    assert "backlog" not in codes(S.check_line("開賣第三天影之刃零的同時在線還在往上走沒有停下來。", names=["影之刃零"]))
    assert "backlog" in codes(S.check_line("開賣第三天影之刃零的同時在線還在往上走沒有停下來。"))
    assert "backlog" in codes(S.check_line("《影之刃零》開賣以後影之兩個字到處都看得到真的很誇張。"))  # 片名外還有一處


def test_poly_unmarked_skips_title_positions(monkeypatch):
    no_registry(monkeypatch)
    monkeypatch.setattr(S, "known_chars", lambda: set("甲乙丙"))
    assert "poly_unmarked" not in codes(S.check_line("這一支片講的是《甲乙丙》開賣之後大家到底怎麼看待它的評價。"))
    assert "poly_unmarked" in codes(S.check_line("這一支片講的是甲乙丙開賣之後大家到底怎麼看待它的評價。"))


def test_title_exemption_keeps_hard_items(monkeypatch):
    no_registry(monkeypatch)
    monkeypatch.setattr(S, "_unregistered", lambda say: ["Zxqvtwk"])
    assert "en_unregistered" in codes(S.check_line("這一支片要講的就是《Zxqvtwk》開賣之後大家到底怎麼看待它。"), "err")


def test_subject_names_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(S.P, "PROJECTS", tmp_path)
    pd = tmp_path / "t"
    pd.mkdir()
    assert S.subject_names("t") == []
    (pd / "brief.json").write_text(json.dumps({"topic": "影之刃零開賣後評價"}, ensure_ascii=False), encoding="utf-8")
    assert S.subject_names("t") == ["影之刃零"]   # 沒有 package:topic 開頭
    (pd / "brief.json").write_text(json.dumps({"topic": "談《甲乙丙》的評價"}, ensure_ascii=False), encoding="utf-8")
    (pd / "spec.json").write_text(json.dumps({"package": {"subject": ["影之刃零", "Eurogamer"]}}, ensure_ascii=False), encoding="utf-8")
    assert S.subject_names("t") == ["影之刃零", "Eurogamer", "甲乙丙"]
