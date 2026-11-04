"""facts_lib / facts_check / spec_check 事實覆蓋改由 facts_check 的單元與整合測試(不連網,fixture 在 tests/fixtures/facts/)。

  PYTHONPATH=<repo> python3 -X utf8 -m pytest pipeline/tests/test_facts_check.py -q -p no:cacheprovider -s
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
REPO = PIPE.parent
FIX = Path(__file__).resolve().parent / "fixtures" / "facts"
sys.path.insert(0, str(PIPE))
import facts_check as FC  # noqa: E402
import facts_lib as FL  # noqa: E402
import script_txt2json as s2j  # noqa: E402


def _lines(text):
    _, _, sections, _, defs, _ = s2j.parse(text)
    out = []
    for sec in sections:
        out.extend(s2j.build_lines(sec["rows"], defs))
    return out


def _root(tmp_path, script="script.txt"):
    """建一個素材根:tmp/projects/ft/(facts.md、spec.json)與 tmp/ft/script.txt。"""
    (tmp_path / "projects" / "ft").mkdir(parents=True)
    (tmp_path / "ft").mkdir()
    shutil.copy(FIX / "proj" / "facts.md", tmp_path / "projects" / "ft" / "facts.md")
    shutil.copy(FIX / "proj" / "spec.json", tmp_path / "projects" / "ft" / "spec.json")
    shutil.copy(FIX / "proj" / script, tmp_path / "ft" / "script.txt")
    return tmp_path


def _run(script_name, root, tag, *args, cli="facts_check.py"):
    env = dict(os.environ, CLAUDE_VIDEO_ROOT=str(root), PYTHONIOENCODING="utf-8")
    cmd = [sys.executable, "-X", "utf8", str(PIPE / cli)] + ([tag] if cli == "facts_check.py" else ["--tag", tag]) + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(REPO))


# ---------------------------------------------------------------- facts_lib
def test_parse_three_headers():
    wow = FL.parse(FIX / "style_wow.md")
    assert [f.id for f in wow] == ["F1", "F2", "F3", "F4"]
    assert wow[0].claim.startswith("壓測台灣場") and "24302072" in wow[0].source
    assert "05:00 CST" in wow[0].quote and wow[0].magnitude == "週四由日曆推得"

    sf = FL.parse(FIX / "style_sf.md")
    assert [f.id for f in sf] == ["F1", "F2", "F3", "F4", "F49", "12"]   # 非事實表、說明文字不算
    assert sf[0].magnitude == "$30,775,377" and sf[0].source.startswith("The Numbers")
    assert sf[0].counter == "媒體四捨五入不同"
    assert sf[0].line == 5 and sf[0].file.endswith("style_sf.md")

    cp = FL.parse(FIX / "style_cp.md")
    assert [f.id for f in cp] == ["F1", "F2"]
    assert cp[0].status == "confirmed" and cp[0].magnitude == "10/22"
    assert "Series X|S" in cp[0].quote                      # 內文的 | 併回原句欄
    assert cp[1].magnitude == "16 首" and cp[1].status == "secondary"


def test_parse_dir_and_find_files():
    fs = FL.parse(FIX / "proj")
    assert len(fs) == 7 and fs[0].id == "F1"
    assert [p.name for p in FL.find_files(FIX / "proj")] == ["facts.md"]


def test_status_normalize():
    cases = {"一手": "confirmed", "一手資料庫": "confirmed", "轉述": "secondary", "媒體轉述 + 玩家一手": "secondary",
             "玩家原話": "player_quote", "留言": "player_quote", "推算": "derived", "單一來源": "single",
             "查無": "unverified", "未經證實": "unverified", "未證實": "unverified", "": "unknown", "隨便": "unknown"}
    for raw, want in cases.items():
        assert FL.norm_status(raw) == want, raw
    assert FL.canon_id("12") == "F12" and FL.canon_id("f3") == "F3"


def test_numbers_normalize():
    n = FL.numbers_in
    assert n("二十三萬") == {"230000"} and n("23 萬") == {"230000"} and n("230,000") == {"230000"}
    assert n("七十美金") == {"70"} and FL.sentence_numbers("七十美金") == {"70"}
    assert n("2019 年") == {"2019"} and n("二零一九年") == {"2019"}
    assert n("6.39%") == {"6.39%"} and FL.sentence_numbers("百分之六") == {"6%"}
    assert n("兩百一十二分鐘") == {"212"} and n("一萬兩千人") == {"12000"}
    assert n("3,077 萬美金") == {"30770000"} and n("$51.1M") == {"51100000"}
    assert n("05:00") == {"05:00"} and n("10/22") == {"10-22"}
    assert FL.sentence_numbers("第一場一個多月") == set()         # 句子端不收「第一、一個」
    assert FL.sentence_numbers("十一月五號") == {"11-05"}
    f = FL.Fact(id="F1", claim="年增 20%", source="https://example.com/a/123456", magnitude="3 秒")
    assert {"20%", "20", "3"} <= FL.fact_numbers(f) and "123456" not in FL.fact_numbers(f)


def test_numbers_time_date_approx():
    n, sn = FL.numbers_in, FL.sentence_numbers
    assert n("八點四十") == n("8:40") == n("08:40") == sn("八點四十分") == n("8點40") == {"08:40"}
    assert n("五點") == n("05:00") == n("5點") == n("5:00 AM") == sn("早上五點") == {"05:00"}
    assert sn("六點到九點") == {"06:00", "09:00"} and sn("八點半") == {"08:30"}
    assert n("十一月五號") == n("11/5") == n("11-05") == n("11 月 5 日") == sn("十一月五號") == {"11-05"}
    assert n("2026-10-26") == {"2026", "10-26"} and sn("2019 年八月八號") == {"2019", "08-08"}
    assert sn("十月二十二號早上五點") == n("10/22 05:00 CST") == {"10-22", "05:00"}
    assert sn("一千多") == n("1,000") == {"1000"} and sn("兩百多人") == {"200"}
    assert sn("兩天") == {"2"} and n("2 天") == {"2"}
    assert sn("有一點慢") == set() and sn("清晨一點") == {"01:00"}          # 一點只在時段詞後算時間
    assert n("3-5 人") == {"3", "5"} and n("3/5 款") == {"3", "5"} and n("3-5") == {"03-05"}    # 後接量詞不當日期
    assert n("3.5") == {"3.5"} and n("12:30:45") == {"12", "30", "45"}     # 小數、時分秒不誤判
    f = FL.Fact(id="F1", claim="台灣場 10/22 05:00 CST 開始", magnitude="1000 Mbps")
    assert sn("十月二十二號早上五點") <= FL.fact_numbers(f) and sn("一千多") <= FL.fact_numbers(f)


# ---------------------------------------------------------------- script_txt2json 的 f 鍵
def test_f_key_passthrough():
    lines = _lines((FIX / "proj" / "script.txt").read_text(encoding="utf-8"))
    assert lines[0]["f"] == ["F1"] and "f" not in lines[1]
    assert lines[6]["f"] == ["F6"] and lines[6]["anim"]["src"] == "未證實爆料"   # anim 簡寫字串 + f


# ---------------------------------------------------------------- analyze
def _analyze():
    lines = _lines((FIX / "proj" / "script.txt").read_text(encoding="utf-8"))
    facts = FL.parse(FIX / "proj")
    return FC.analyze(lines, facts, ["Asmongold"])


def test_link_unlinked_mismatch_weak():
    r = _analyze()
    s = {x["i"]: x for x in r["sentences"]}
    assert s[1]["linked"] and not s[1]["auto"] and s[1]["f"] == ["F1"]          # 有 f 且數字都在
    assert s[2]["linked"] and s[2]["auto"] and s[2]["f"] == ["F2"] and not s[2]["weak"]   # auto,derived 但有 note
    assert s[3]["linked"] and s[3]["f"] == ["F3"]
    assert s[4]["linked"] and s[4]["weak"] and "F4" in s[4]["weak"][0]          # secondary 無小字 -> 警告
    assert not s[5]["linked"] and s[5]["mismatch"] and "99" in s[5]["mismatch"][0]   # 數字不符
    assert s[6]["auto"] and s[6]["f"] == ["F5"]                                  # 引言自動配對
    assert s[7]["linked"] and not s[7]["weak"]                                   # unverified,anim src 有「未證實」
    assert s[8]["linked"] and s[8]["weak"]                                       # unverified 無小字
    assert not s[9]["need"]
    assert s[10]["need"] and not s[10]["linked"] and not s[10]["f"] and s[10]["reason"]   # 未連結
    assert s[11]["errors"] and "F99" in s[11]["errors"][0]                       # 引用不存在的 F
    assert s[12]["auto"] and s[12]["f"] == ["F7"]                                # 人名自動配對
    assert (r["need"], r["linked"], r["unlinked"], r["mismatch"], r["errors"]) == (11, 8, 1, 1, 1)
    assert FC.summary_line(r) == "[facts_check] 連結 8/11 句 (73%)、未連結 1、狀態不符 1、錯誤 1、無出處 8、引矛盾 0"


def test_auto_ambiguous_is_unlinked():
    facts = FL.parse_text("| # | 主張 | 來源 | 原句 | 狀態 |\n|---|---|---|---|---|\n"
                          "| F1 | 賣了 50 萬套 | a | q | 一手 |\n| F2 | 也是 50 萬人 | b | q | 一手 |\n")
    r = FC.analyze([{"text": "賣了五十萬套。"}], facts)
    assert r["unlinked"] == 1 and "F1/F2" in r["sentences"][0]["reason"]
    r = FC.analyze([{"text": "賣了五十萬套。", "f": "F2"}], facts)               # 字串形式的 f 也收
    assert r["linked"] == 1


def test_no_source_and_contradiction():
    rows = ["| # | 主張 | 來源 | 原句 | 狀態 |", "|---|---|---|---|---|",
            '| F1 | 賣了 50 萬套 | https://a.com/x | "sold 500k" | 一手 |',
            "| F2 | 賣了 60 萬套 | 查無 | 查無 | 查無 |",
            "| F3 | 賣了 70 萬套 | 由 F1 推算 | | 推算 |",            # derived:原句可空,來源有 F 參照
            "| F4 | 賣了 80 萬套 | 無 | | 推算 |",                  # derived 但來源也沒有
            "| F5 | 賣了 90 萬套 | comments_ref/x.jsonl | 「好」 | 矛盾 |",   # 本機檔算有出處;矛盾
            "| F6 | 賣了 10 萬套 | https://b.com | 查無逐字 | 轉述 |"]   # 有網址但原句查無
    tbl = "\n".join(rows) + "\n"
    facts = FL.parse_text(tbl)
    sents = [{"text": f"賣了{n}萬套。", "f": [f"F{k}"]} for k, n in ((1, 50), (2, 60), (3, 70), (4, 80), (5, 90), (6, 10))]
    r = FC.analyze(sents, facts)
    s = {x["i"]: x for x in r["sentences"]}
    assert not s[1]["no_source"] and not s[1]["contra"]
    assert "來源無網址" in s[2]["no_source"][0] and "原句空或查無" in s[2]["no_source"][0]
    assert not s[3]["no_source"]                                             # derived:原句可空
    assert "F4" in s[4]["no_source"][0] and "原句" not in s[4]["no_source"][0]
    assert not s[5]["no_source"] and s[5]["contra"] and "F5" in s[5]["contra"][0]
    assert "原句空或查無" in s[6]["no_source"][0] and "來源" not in s[6]["no_source"][0]
    assert (r["no_source"], r["contra"]) == (3, 1)
    assert FC.summary_line(r).endswith("、無出處 3、引矛盾 1") and FC.bad_count(r) == 4
    # 表級:狀態不是查無、卻缺出處 -> F4、F6(F2 狀態查無不列;F3 derived 有 F 參照)
    assert [k for k, _ in r["table_gaps"]] == ["F4", "F6"]
    out = FC.report("t", r, [])
    assert any("無出處 句2" in l for l in out) and any("引矛盾 句5" in l for l in out) and any("表內缺出處(只警告)2 條" in l for l in out)


def test_strict_exit_on_no_source(tmp_path):
    root = _root(tmp_path, "script_ok.txt")     # fixture 來源是裸名稱 -> 無出處 > 0
    p = _run("script_ok.txt", root, "ft", "--strict")
    assert p.returncode == 1 and "無出處 2" in p.stdout.strip().splitlines()[-1]
    assert _run("script_ok.txt", root, "ft").returncode == 0


# ---------------------------------------------------------------- CLI
def test_cli_summary_and_strict(tmp_path):
    root = _root(tmp_path)
    p = _run("script.txt", root, "ft")
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip().splitlines()[-1] == "[facts_check] 連結 8/11 句 (73%)、未連結 1、狀態不符 1、錯誤 1、無出處 8、引矛盾 0"
    assert "弱狀態無小字 2 句" in p.stdout and "狀態不符 句5" in p.stdout and "未連結 句10" in p.stdout
    assert _run("script.txt", root, "ft", "--strict").returncode == 1
    j = _run("script.txt", root, "ft", "--json")
    assert j.returncode == 0 and json.loads(j.stdout[:j.stdout.index("facts_check ft:")])["linked"] == 8


def test_cli_strict_clean(tmp_path):
    root = _root(tmp_path, "script_ok.txt")
    fp = root / "projects" / "ft" / "facts.md"       # fixture 的來源是裸名稱,補成網址/F 參照才算有出處
    fp.write_text(fp.read_text(encoding="utf-8").replace("| news.example.com/a/1 |", "| https://news.example.com/a/1 |")
                  .replace("| mein |", "| 由 F1 算出 |").replace("| techradar |", "| https://techradar.com/x |").replace("| src |", "| https://src.com/x |"), encoding="utf-8")
    p = _run("script_ok.txt", root, "ft", "--strict")
    assert p.returncode == 0, p.stdout
    assert p.stdout.strip().splitlines()[-1] == "[facts_check] 連結 3/3 句 (100%)、未連結 0、狀態不符 0、錯誤 0、無出處 0、引矛盾 0"


def test_write_spec(tmp_path):
    root = _root(tmp_path)
    p = _run("script.txt", root, "ft", "--write-spec")
    assert p.returncode == 0, p.stderr
    spec = json.loads((root / "projects" / "ft" / "spec.json").read_text(encoding="utf-8"))
    assert spec["names"] == ["Asmongold"] and spec["channel"] == "ChannelA"      # 其他鍵保留
    facts = {f["id"]: f for f in spec["facts"]}
    assert {k: (v["lines"], v["status"]) for k, v in facts.items()} == {
        "F1": ([1], "confirmed"), "F2": ([2], "partial"), "F3": ([3], "confirmed"), "F4": ([4], "partial"),
        "F5": ([6], "single"), "F6": ([7, 8], "unverified"), "F7": ([12], "confirmed")}   # 句5(不符)不寫入
    assert facts["F1"]["src"] == "projects/ft/facts.md" and facts["F1"]["claim"].startswith("壓測台灣場")
    # spec.json 不存在 -> 建最小檔
    (root / "projects" / "ft" / "spec.json").unlink()
    assert _run("script.txt", root, "ft", "--write-spec").returncode == 0
    spec = json.loads((root / "projects" / "ft" / "spec.json").read_text(encoding="utf-8"))
    assert spec["tag"] == "ft" and len(spec["facts"]) == 6    # 沒有 spec.names,人名句 12 不需核對


def test_spec_check_skips_fact_cover(tmp_path):
    root = _root(tmp_path)
    p = _run("script.txt", root, "ft", cli="spec_check.py")
    assert "事實覆蓋改由 facts_check 檢查" in p.stdout, p.stdout + p.stderr
    assert "沒有 fact 涵蓋" not in p.stdout
    # 有 facts[] 時照舊檢查(句子沒被涵蓋 -> 報錯)
    sp = root / "projects" / "ft" / "spec.json"
    sp.write_text(json.dumps({"names": ["Asmongold"], "facts": [{"id": "a", "lines": [1], "status": "confirmed"}]}),
                  encoding="utf-8")
    p = _run("script.txt", root, "ft", cli="spec_check.py")
    assert "事實覆蓋改由 facts_check" not in p.stdout and "沒有 fact 涵蓋" in p.stdout and p.returncode == 1
    # 沒有 facts*.md 時也照舊
    sp.write_text(json.dumps({"names": ["Asmongold"]}), encoding="utf-8")
    (root / "projects" / "ft" / "facts.md").unlink()
    p = _run("script.txt", root, "ft", cli="spec_check.py")
    assert "沒有 fact 涵蓋" in p.stdout and p.returncode == 1


# ---------------------------------------------------------------- 真實專案(只驗不當機,印連結率)
def test_real_projects_link_rate():
    env = dict(os.environ, CLAUDE_VIDEO_ROOT=str(REPO), PYTHONIOENCODING="utf-8")
    for tag in ("wow_stress", "cp2077_25", "sf_movie"):
        if not (REPO / "projects" / tag / "facts.md").exists():
            continue
        p = subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "facts_check.py"), tag], capture_output=True,
                           text=True, encoding="utf-8", env=env, cwd=str(REPO))
        assert p.returncode == 0, p.stdout + p.stderr
        last = p.stdout.strip().splitlines()[-1]
        assert re.match(r"\[facts_check\] 連結 \d+/\d+ 句 \(\d+%\)、未連結 \d+、狀態不符 \d+、錯誤 \d+、無出處 \d+、引矛盾 \d+$", last), last
        print(f"連結率 {tag}: {last}")


# ---------------------------------------------------------------- spec_check:封面三行與同號標題重複字句(警告)
def test_cover_title_duplicate_warn():
    import spec_check as SC
    titles = [{"text": "戰神預算被砍一半 玩家傻眼", "angle": "判"}, {"text": "戰神做了三億美金還是翻車", "angle": "數"},
              {"text": "戰神開發商吃相難看", "angle": "損"}, {"text": "戰神x", "angle": "問"}, {"text": "戰神y", "angle": "反"}]
    thumbs = [{"plan": 1, "lines": ["戰神", "預算被砍一半", "三億美金"], "composition": "face"},
              {"plan": 2, "lines": ["戰神", "吃相難看", "三億美金"], "composition": "collage"},   # 方案2 對標題2:三億美金 重複
              {"plan": 3, "lines": ["戰神", "吃相難看", "砍預算"], "composition": "face"}]        # 吃相難看 在標題3,不是同號...是同號
    spec = {"channel": "ChannelA", "package": {"subject": ["戰神"], "titles": titles, "thumbs": thumbs}}
    _, warns = SC.check_package(spec)
    dup = [w for w in warns if "重複字句" in w]
    assert any("方案1 副文字" in w and "預算被砍一半" in w for w in dup), dup
    assert any("方案2 補充字" in w and "三億美金" in w for w in dup), dup
    assert any("方案3 副文字" in w and "吃相難看" in w for w in dup), dup
    assert not any("方案1 補充字" in w or "方案2 副文字" in w for w in dup), dup   # 跨號、或不足 4 字不算
    assert SC.longest_common(SC.strip_subject("戰神很爛", ["戰神"]), SC.strip_subject("戰神很爛", ["戰神"])) == "很爛"
