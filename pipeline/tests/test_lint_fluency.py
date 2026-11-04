"""script_lint 旁白連貫警告測試(來源起句 / 子句過多 / 一句數字過多 / 沒接住上一句):python3 -X utf8 -m pytest pipeline/tests/test_lint_fluency.py -q
fixture 用 tmp_path + CLAUDE_VIDEO_ROOT;沒裝 jieba 時走字元二字組退回路徑(本機實測路徑)。"""
import os
import subprocess
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
import script_lint as L  # noqa: E402


def mk(*sents):
    return [(i + 1, s) for i, s in enumerate(sents)]


def names(w):
    return [x[0] for x in w]


def has(w, code):
    return any(code in n for n in names(w))


# 報告體:一塊 8 句,每句換一個來源開頭、互不承接
REPORT = [
    "巴哈有玩家說伺服器當天晚上很卡。",
    "暴雪論壇上也有玩家在問怎麼沒有週末場。",
    "Warcraft Tavern 九月十八號就寫了測試期延後。",
    "媒體報的價格是六十美金。",
    "製作團隊在聯訪裡提到火把會造成延遲。",
    "德國那邊的紀錄寫到敵人全部消失。",
    "官方公告寫明帳號可能被誤鎖。",
    "另一則回覆嗆說喊誤鎖的多半在演。",
]
# 梯子體:每句接住上一句的名詞或承接詞,來源 <= 1
LADDER = [
    "壓測那天伺服器很卡。",
    "伺服器卡的原因是排隊人數太多。",
    "排隊人數太多,所以官方臨時加開一台。",
    "那一台開起來之後,延遲掉了一半。",
    "延遲一掉,玩家就能組隊了。",
    "組隊成功之後才發現副本會當機。",
]


def test_report_style_hits_source_and_chain():
    w = L.fluency_warnings(mk(*REPORT))
    assert has(w, "SOURCE_LEAD") and has(w, "CHAIN_BREAK")
    assert any("比例" in n for n in names(w))


def test_ladder_style_clean():
    assert L.fluency_warnings(mk(*LADDER)) == []


def test_clauses_five():
    w = L.fluency_warnings(mk("官方先開,歐洲晚上七點,北美下午兩點,台灣清晨,然後才輪到亞洲。"))
    assert has(w, "CLAUSES")
    assert not has(L.fluency_warnings(mk("官方先開,歐洲晚上七點,北美下午,台灣清晨。")), "CLAUSES")   # 4 子句
    assert not has(L.fluency_warnings(mk("劍、盾、弓、杖、斧、錘、槍是七種武器。")), "CLAUSES")   # 頓號不算


def test_clause_long_ratio():
    long_s = "十一月五號開服建角色之前最好先對一次你選的種族,被動改成什麼樣。"   # 23 字長子句 + 7 字短子句
    st = {}
    w = L.fluency_warnings(mk(long_s, "官方說好。"), stats=st)
    hit = [x for x in w if "CLAUSE_LONG" in x[0]]
    assert hit and st["clause_long"] == (1, 3) and hit[0][1][0][0] == 1 and "23 字" in hit[0][1][0][1]
    if L.clause_cut("十一月五號開服建角色之前") is not None:   # 有 jieba 才給切點
        assert "建議切在" in hit[0][1][0][1]
    # 長子句 1/5 = 20% 不超過門檻;頓號、冒號也算子句界
    assert not has(L.fluency_warnings(mk(long_s, "劍、盾、弓。")), "CLAUSE_LONG")


def test_nums_three_groups():
    w = L.fluency_warnings(mk("十月二十二號早上五點到九點。"))
    assert has(w, "NUMS")
    assert len(L.num_groups("十月二十二號早上五點到九點")) == 3
    assert L.num_groups("二零一九年的壓測") == ["二零一九年"]


def test_not_numbers():
    assert L.num_groups("一樣一起一次一下一點一直一定一些一邊一堆十分萬一一旦一半一句") == []
    assert not has(L.fluency_warnings(mk("他們一樣一起一直一定要等一下。")), "NUMS")


def test_one_generic_not_counted():
    assert L.num_groups("換了一款遊戲") == []
    assert L.num_groups("一天上班") == []


def test_one_time_unit_counted():
    assert L.num_groups("下午一點整開始") == ["一點"]
    assert L.num_groups("一點都不怕") == []


def test_title_number_not_counted():
    assert L.num_groups("《真人快打2》今年首週") == []


def test_block_split_and_ratio():
    # 同一塊 2 句來源起句 → 警告;以 starts 切成兩塊各 1 句 → 無「同一塊」警告
    ls = mk("巴哈有玩家說很卡。", "底下也有人說很卡。")
    assert any("同一塊" in n for n in names(L.fluency_warnings(ls)))
    assert not any("同一塊" in n for n in names(L.fluency_warnings(ls, starts=[2])))


def test_report_block_hits():
    ls = mk("官網第一段寫的是多元跟包容。", "Kotaku 那篇的標題寫他們沒說謊。", "內文更重,說這是誤導。", "新聞稿直接寫營收偏低。", "我看了很久。")
    w = L.fluency_warnings(ls)
    assert has(w, "REPORT_RATIO") and any("單一塊" in n for n in names(w))
    assert not has(L.fluency_warnings(mk("官網第一段寫的是多元。", "天氣很好。", "我們去散步。", "路上很安靜。")), "單一塊")


def test_report_exclusions():
    for t in ("說公道話,這款遊戲沒那麼糟。", "你說這是轉型嗎?", "我說真的,玩家都累了。", "也就是說,公司沒打算改。"):
        assert not L.report_sentence(t), t


def test_cli_prints_fluency(tmp_path):
    d = tmp_path / "t"
    d.mkdir()
    body = "# 一、段\n" + "\n".join(f"clip|{s}" for s in REPORT) + "\n"
    (d / "script.txt").write_text("@title t\n" + body, encoding="utf-8")
    env = dict(os.environ, CLAUDE_VIDEO_ROOT=str(tmp_path))
    r = subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "script_lint.py"), "t"], capture_output=True, text=True, encoding="utf-8", env=env)
    assert "SOURCE_LEAD" in r.stdout and "CHAIN_BREAK" in r.stdout and "接住比例" in r.stdout
    assert r.returncode == 0   # 全是警告,不加 --strict 不擋
    r2 = subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "script_lint.py"), "t", "--strict"], capture_output=True, text=True, encoding="utf-8", env=env)
    assert r2.returncode == 1
