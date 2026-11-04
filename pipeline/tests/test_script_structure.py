"""script_structure / pace 測試:PYTHONPATH=<repo> python3 -X utf8 -m pytest pipeline/tests/test_script_structure.py -q
fixture 在 tests/fixtures/structure/:good.txt(照規則寫;配 good_timeline.json,秒數是為了湊塊長編的,所以字/分、事實/分一定超標)、
bad.txt(事件宣告開場 + 中立聲明 + 無 cta + 無判斷句)。CLI 測試用 CLAUDE_VIDEO_ROOT 指到暫存目錄,build/ 不污染 repo。"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
REPO = PIPE.parent
FX = HERE / "fixtures" / "structure"
sys.path.insert(0, str(PIPE))
import pace  # noqa: E402
import script_structure as S  # noqa: E402

GOOD = (FX / "good.txt").read_text(encoding="utf-8")
BAD = (FX / "bad.txt").read_text(encoding="utf-8")
GOOD_TL = FX / "good_timeline.json"


def codes(r):
    return [w["code"] for w in r["warnings"]]


def mini(*rows, head="# 一、段\n"):
    return "@title t\n" + head + "\n".join(f"clip|{x}" for x in rows) + "\n"


def write_tl(tmp_path, spans):
    p = tmp_path / "tl.json"
    p.write_text(json.dumps({"lines": [dict(idx=i + 1, start=a, end=b) for i, (a, b) in enumerate(spans)]}), encoding="utf-8")
    return p


# ---- pace
def test_pace():
    assert pace.CHARS_PER_MIN == 330 and pace.CHARS_PER_SEC == 5.5
    assert pace.count_chars("你好,世界! ABC 12") == 9
    assert pace.est_seconds("一二三四五六七八九十一") == pytest.approx(2.0)
    assert pace.est_seconds("一二三四五六", pause=0.5) == pytest.approx(6 / 5.5 + 0.5)
    assert pace.minutes(660) == pytest.approx(2.0)


def test_lint_uses_pace():
    import script_lint as L
    assert L.T["chars_per_sec"] == pace.CHARS_PER_SEC == 5.5


# ---- 開場四型
@pytest.mark.parametrize("rows,want", [
    (["你花的 70 美金,到底買到什麼。", "這支片來回答。", "先講背景。"], "觀眾利害"),
    (["這支遊戲賣了 230 萬份。", "結果評價只有一半好評。", "原因很多。"], "反差"),
    (["官方昨天發了公告。", "這次改了介面。", "也改了平衡。"], "事件宣告"),
    (["10 月 25 日有一份更新說明。", "裡面列了三項。", "全部都跟介面有關。"], "事件宣告"),
    (["這個系列從十年前開始。", "後來換了幾次製作團隊。", "現在由新團隊接手。"], "背景交代"),
])
def test_hook_types(rows, want):
    r = S.analyze(mini(*rows))
    assert r["hook_type"] == want
    assert ("HOOK_TYPE" in codes(r)) == (want in ("事件宣告", "背景交代"))


def test_classify_hook_single_source():
    c = S.classify_hook
    assert c(["這款遊戲賣 70 美金。", "可是上市第一個禮拜,大部分在玩的人都沒付這筆錢。"])[0] == "反差"
    assert c(["十月一號,魔獸世界永恆的 Beta,更新說明多了一句話。", "副本任務多給的經驗,砍一半。"]) == ("事件宣告", ["事件宣告"])
    assert c(["《魔獸世界:永恆》的測試期,台灣玩家等了一個多月的亞洲伺服器,官方只排了一次。", "x。"])[0] == "觀眾利害"
    assert c(["測試期到了。", "沒什麼事。", "你覺得呢。"])[0] == "背景交代"      # 第 3 句有你 → 不算事件宣告
    assert c(["Beta 開始了。", "今天沒有消息。"])[0] == "事件宣告"
    assert c(["二零一九年有一件事。", "結果沒人注意。"])[0] == "反差"            # 中文數字也算數字
    assert c(["這系列有十年了。", "最近換了團隊。"])[0] == "背景交代"
    assert c([]) == ("背景交代", [])


@pytest.mark.parametrize("tag,want", [("wow_stress", "觀眾利害"), ("gow_sales", "反差"), ("wow_forever", "事件宣告")])
def test_real_scripts_hook(tag, want):
    sp = REPO / tag / "script.txt"
    if not sp.exists():
        pytest.skip("no script")
    assert S.analyze(sp.read_text(encoding="utf-8-sig"))["hook_type"] == want


def test_event_with_turn_is_not_event():
    r = S.analyze(mini("官方公布了 230 萬份。", "結果沒人買。", "原因如下。"))
    assert r["hook_type"] == "反差"


# ---- 中立聲明
def test_neutral():
    r = S.analyze(BAD)
    hits = [w for w in r["warnings"] if w["code"] == "NEUTRAL"]
    assert len(hits) == 1 and hits[0]["line"] == 6
    assert "NEUTRAL" not in codes(S.analyze(GOOD))


# ---- 第一判斷句
def test_judge_sec_timeline_and_estimate():
    r = S.analyze(GOOD, [GOOD_TL])
    assert r["timeline_used"] and r["judge_sec"] == 6.0 and "JUDGE_LATE" not in codes(r)
    r = S.analyze(GOOD)   # 估算:第一句 33 字 ÷ 5.5 = 6.0 秒
    assert not r["timeline_used"] and r["judge_sec"] == pytest.approx(pace.count_chars("這款遊戲上市第一週賣出 230 萬份,可是你身邊多數人都沒付那 70 美金。") / 5.5, abs=0.1)
    assert S.analyze(BAD)["judge_sec"] is None and "JUDGE_NONE" in codes(S.analyze(BAD))


def test_judge_late_with_timeline(tmp_path):
    p = write_tl(tmp_path, [(0, 10), (10, 25), (25, 30)])
    r = S.analyze(mini("先講背景。", "再講背景。", "我覺得這根本不對。"), [p])
    assert r["judge_sec"] == 25.0 and "JUDGE_LATE" in codes(r)


# ---- 塊與新料間隔、落到觀眾
def test_blocks_good():
    r = S.analyze(GOOD, [GOOD_TL])
    assert [b["name"] for b in r["blocks"]] == ["二、錢從哪來", "三、玩家去哪了", "四、微軟沒講的事", "五、該怎麼辦"]   # 開場/結尾段排除
    assert [round(b["end_s"] - b["start_s"]) for b in r["blocks"]] == [90, 100, 132, 90]
    assert all(b["lands_on_viewer"] for b in r["blocks"])
    for c in ("BLOCK_COUNT", "BLOCK_SEC", "FACT_GAP", "NO_LANDING"):
        assert c not in codes(r)


def test_fact_gap_and_no_landing(tmp_path):
    src = mini("先講背景,沒有數字。", "這裡有 12 個人。", "中間都是描述。", "又出現 99 個人。", "最後一句收尾。")
    p = write_tl(tmp_path, [(0, 10), (10, 20), (20, 80), (80, 90), (90, 100)])
    r = S.analyze(src, [p])
    gap = [w for w in r["warnings"] if w["code"] == "FACT_GAP"]
    assert len(gap) == 1 and "70 秒" in gap[0]["text"]   # 新料起點 10→80
    assert "NO_LANDING" in codes(r) and r["blocks"][0]["new_facts"] == 2 and not r["blocks"][0]["lands_on_viewer"]


def test_new_fact_kinds():
    src = ('@title t\n@def quote:q={"text":"原話","src":"某人"}\n# 一、段\nquote:q|他這樣說。\n'
           'img:a|沒有 hl 的圖。\nimg:b|有 hl 的圖。 ;; {"hl":"圖"}\nclip|一般句。\n')
    r = S.analyze(src)
    assert r["blocks"][0]["new_facts"] == 2


# ---- 最強證據
def test_strongest_pos():
    r = S.analyze(GOOD, [GOOD_TL])
    assert 55 <= r["strongest_pos_pct"] <= 75 and "STRONGEST_POS" not in codes(r)   # 3 億所在句
    assert "STRONGEST_POS" in codes(S.analyze(BAD))
    assert any(c["kind"] == "quote" for c in r["strongest_candidates"])


# ---- CTA
def test_cta():
    r = S.analyze(GOOD, [GOOD_TL])
    assert r["cta_pos_pct"] == pytest.approx(106 / 523 * 100, abs=0.2) and "CTA_POS" not in codes(r)
    b = S.analyze(BAD)
    assert b["cta_pos_pct"] is None and "CTA_POS" not in codes(b) and any("cta" in n for n in b["notes"])
    early = GOOD.replace("clip|可是滿意的人是誰", "cta|想看每週爭議,記得訂閱。\nclip|可是滿意的人是誰")
    assert "CTA_POS" in codes(S.analyze(early))   # 第一塊還沒講完就插 cta
    late = GOOD.replace('cta|想看每週的遊戲爭議拆解,記得訂閱。 ;; {"pause": 0.9}\n', "") + "cta|想看更多就訂閱。\n"
    assert late.rstrip().endswith("訂閱。")
    assert "CTA_POS" in codes(S.analyze(late))   # 放片尾


# ---- 結尾
def test_ending():
    e = S.analyze(GOOD, [GOOD_TL])["ending"]
    assert (e["questions"], e["judgment"], e["callback"], e["new_fact"]) == (2, True, True, True)
    assert "230萬" in e["callback_hits"] and "4500" in e["new_numbers"]
    e = S.analyze(BAD)["ending"]
    assert (e["questions"], e["judgment"], e["callback"], e["new_fact"]) == (0, False, False, False)
    assert {"END_QUESTIONS", "END_JUDGMENT", "END_CALLBACK", "END_NEWFACT"} <= set(codes(S.analyze(BAD)))


# ---- 字/分
def test_chars_per_min_two_paths():
    chars = sum(pace.count_chars(x.partition("|")[2].partition(" ;; ")[0]) for x in GOOD.splitlines() if "|" in x and x[0] != "@" and x[0] != "#")
    r = S.analyze(GOOD, [GOOD_TL])
    assert r["timeline_used"] and r["metrics"]["chars"] == chars
    assert r["chars_per_min"] == pytest.approx(chars / 523 * 60, abs=0.1) and "CPM" in codes(r)
    r = S.analyze(GOOD)
    assert not r["timeline_used"] and r["chars_per_min"] == pytest.approx(330, abs=0.1) and "CPM" not in codes(r)   # 估算恆為 330,不檢查
    assert r["facts_per_min"] == pytest.approx(r["metrics"]["new_fact_sentences"] / (chars / 330), abs=0.05)


def test_timeline_length_mismatch_falls_back():
    r = S.analyze(BAD, [GOOD_TL])
    assert not r["timeline_used"] and any("句數" in n for n in r["notes"])


# ---- CLI
def run_cli(root, *args):
    return subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "script_structure.py"), *args],
                          env=dict(os.environ, CLAUDE_VIDEO_ROOT=str(root)), capture_output=True, text=True, encoding="utf-8")


@pytest.fixture
def root(tmp_path):
    for tag, f in (("good", "good.txt"), ("bad", "bad.txt")):
        (tmp_path / tag).mkdir()
        shutil.copy(FX / f, tmp_path / tag / "script.txt")
    return tmp_path


def test_cli_writes_structure_json(root):
    p = run_cli(root, "good", "--timeline", str(GOOD_TL))
    assert p.returncode == 0, p.stderr
    d = json.loads((root / "build" / "good" / "structure.json").read_text(encoding="utf-8"))
    for k in ("metrics", "warnings", "hook_type", "judge_sec", "blocks", "strongest_pos_pct", "cta_pos_pct", "ending", "chars_per_min", "facts_per_min", "timeline_used"):
        assert k in d
    assert d["timeline_used"] is True and set(d["warnings"][0]) == {"code", "line", "text"}
    assert set(d["blocks"][0]) >= {"name", "start_s", "end_s", "new_facts", "lands_on_viewer"}
    assert len(p.stdout.strip().splitlines()) <= 25


def test_cli_finds_keep_timeline_and_json_flag(root):
    (root / "keep" / "good").mkdir(parents=True)
    shutil.copy(GOOD_TL, root / "keep" / "good" / "timeline.json")
    p = run_cli(root, "good", "--json")
    assert json.loads(p.stdout)["timeline_used"] is True


def test_cli_strict_exit_code(root):
    assert run_cli(root, "bad").returncode == 0
    assert run_cli(root, "bad", "--strict").returncode == 1
    assert run_cli(root, "nope").returncode != 0


# ---- repo 現有文案不得拋例外
SCRIPTS = sorted(REPO.glob("*/script.txt"))


@pytest.mark.parametrize("sp", SCRIPTS, ids=lambda p: p.parent.name)
def test_all_repo_scripts_run(sp, tmp_path):
    tag = sp.parent.name
    (tmp_path / tag).mkdir()
    shutil.copy(sp, tmp_path / tag / "script.txt")
    tl = REPO / "keep" / tag / "timeline.json"
    if tl.exists():
        (tmp_path / "keep" / tag).mkdir(parents=True)
        shutil.copy(tl, tmp_path / "keep" / tag / "timeline.json")
    p = run_cli(tmp_path, tag)
    assert p.returncode == 0, p.stderr[-300:]
