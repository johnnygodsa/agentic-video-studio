"""tts_pron_verify 測試(不載模型、不用顯示卡、不需 pypinyin/opencc):判定純函式三種結果、規則索引、取句/造句。
python -X utf8 pipeline/tests/test_tts_pron_verify.py(或 -m pytest;沒裝 pytest 時直接執行,跟其他 tests 一樣)"""
import re
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import tts_pron_verify as V  # noqa: E402

READ = {"著": "zhe5", "住": "zhu4", "者": "zhe3", "抓": "zhua1", "著名": "x", "的": "de5", "德": "de2", "不": "bu4", "地": "di4"}
ALL = {"著": {"zhe5", "zhu4", "zhuo2", "zhao2"}, "得": {"de2", "de5", "dei3"}, "地": {"di4", "de5"}}


class FakePhon:
    """只認測試用的幾個字;其餘字讀音 = 自己(對位鍵同 tts_asr._key:去調、zh/ch/sh 模糊、ng -> n)。"""

    def one(self, c):
        return READ.get(c, c)

    def all(self, c):
        return ALL.get(c, {self.one(c)})

    def key(self, c, py=None):
        s = re.sub(r"\d", "", py or self.one(c))
        return re.sub(r"^([zcs])h", r"\1", s).replace("ng", "n")


def norm(s):  # 去標點(保留 MARK),不做繁簡
    return re.sub(r"[，。！？、\s]+", "", s)


def rec(text, asr, asr2="same", sim=0.95, asr2_sim=0.95, pron_bad=0):
    r = dict(text=text, measure_text=text, asr=asr, sim=sim, pron_bad=pron_bad, asr2_bad=False)
    if asr2 != "none":
        r.update(asr2=text if asr2 == "same" else asr2, asr2_sim=asr2_sim)
    return r


def J(r, tg, **kw):
    return V.judge_record(r, tg, norm=norm, ph=FakePhon(), **kw)


# ------------------------------------------------------------ 判定三種結果
def test_right_homophone():
    # 「這部著作」應讀 zhù:辨識成 住(zhu4)= 預期讀音的同音字 -> 唸對
    t = "這部著作很有名"
    j = J(rec(t, "這部住作很有名", asr2="這部住作很有名"), {2: ("著", "zhu4")})
    assert j["result"] == "right" and j["positions"][0]["main"] == "right" and j["positions"][0]["hyp_main"] == "住"


def test_wrong_other_reading():
    # 「睡著了」應讀 zháo:主辨識聽成 住(zhu4,著的另一個讀音)-> 唸錯;副辨識回原字也一樣唸錯(任一即算)
    t = "他終於睡著了"
    j = J(rec(t, "他終於睡住了"), {4: ("著", "zhao2")})
    assert j["result"] == "wrong" and j["positions"][0]["main"] == "wrong" and j["positions"][0]["second"] == "same"
    j = J(rec(t, t, asr2="他終於睡住了"), {4: ("著", "zhao2")})
    assert j["result"] == "wrong" and j["positions"][0]["second"] == "wrong"


def test_undetermined_same_char():
    # 兩個辨識都回原字 -> 無法判定(即使相似度全過);著/着視為同字
    t = "他終於睡著了"
    j = J(rec(t, t), {4: ("著", "zhao2")})
    assert j["result"] == "undetermined"
    j = J(rec(t, "他終於睡着了", asr2="他終於睡著了"), {4: ("著", "zhao2")})
    assert j["result"] == "undetermined"
    j = J(rec(t, t, asr2="none"), {4: ("著", "zhao2")})   # 只有主辨識也一樣
    assert j["result"] == "undetermined" and "沒有副辨識" in j["note"]


def test_other_char_uses_similarity():
    t = "他很執著於此事"
    r = rec(t, "他很執抓於此事", asr2="他很執抓於此事")   # 抓 zhua1:不是著的讀音,也不是預期 -> other,看相似度
    assert J(r, {3: ("著", "zhuo2")})["result"] == "right"
    r = rec(t, "他很執抓於此事", asr2="他很執抓於此事", sim=0.5)
    assert J(r, {3: ("著", "zhuo2")})["result"] == "undetermined"
    r = rec(t, "他很執抓於此事", asr2="他很執抓於此事", pron_bad=1)
    assert J(r, {3: ("著", "zhuo2")})["result"] == "undetermined"


def test_alignment_with_punct_and_worst_of_positions():
    # 句中標點被正規化吃掉也要對得上位置;兩個位置取最差
    t = "他睡著了，也睡著了"
    tg = {2: ("著", "zhao2"), 7: ("著", "zhao2")}
    j = J(rec(t, "他睡著了也睡住了"), tg)
    assert [p["main"] for p in j["positions"]] == ["same", "wrong"] and j["result"] == "wrong"
    assert [p["pos"] for p in j["positions"]] == [2, 7]


def test_prepare_mismatch():
    j = V.judge_record(dict(text="他睡著了", asr="他睡著了", sim=1.0), {2: ("著", "zhao2")}, norm=lambda s: s.replace("Ζ", ""), ph=FakePhon())
    assert j["result"] == "undetermined" and "對位失敗" in j["note"]


# ------------------------------------------------------------ 規則索引與取句(用真的 pron_rules.json,只看資料,不合成)
def test_build_rules_skips_keep_and_default():
    rules = V.build_rules()
    assert rules and all(r.py and r.py != r.default for r in rules if not r.is_default)
    assert len({r.id for r in rules}) == len(rules)


def test_build_rules_always_defaults():
    # always 字的預設標注各算一條規則(id `<字>#default`);非 always 字(地)沒有
    d = {r.id: r for r in V.build_rules() if r.is_default}
    assert {"得#default", "著#default", "曝#default"} <= set(d) and "地#default" not in d
    assert d["得#default"].py == "的" and d["得#default"].kind == "預設標注" and d["得#default"].ch == "得"
    assert all(r.kind == "非預設規則" for r in V.build_rules() if not r.is_default)


def test_default_rule_hits_and_only():
    rules = V.build_rules()
    h = V.rule_hits(rules, "他看得到遠方")   # 看得 = keep 詞,擋掉非預設規則 -> 落到預設標注
    assert h["得#default"][0] == [2]
    h = V.rule_hits(rules, "他終於獲得勝利")   # 獲得 = 非預設規則 [d][é],不算預設
    assert "得#default" not in h and any(k.startswith("得#") for k in h)
    items, only_rules, _ = V.plan(2, only={"得"})
    assert {r.ch for r in only_rules} == {"得"} and any(r.is_default for r in only_rules)
    dflt = [i for i in items if i["rule"] == "得#default"]
    assert dflt and len(dflt) <= 2 and all(i["py"] == "的" for i in dflt)


def test_strict_default_judgement():
    # always 字的預設標注:辨識成不相干的音 -> 唸錯(不靠相似度放行);的/德/地(有 de 讀音)-> 唸對
    t = "他看得到遠方"
    tg = {2: ("得", "de5", True)}
    assert J(rec(t, "他看不到遠方", asr2="他看不到遠方"), tg)["result"] == "wrong"
    assert J(rec(t, "他看的到遠方", asr2="他看的到遠方"), tg)["result"] == "right"
    assert J(rec(t, "他看德到遠方", asr2="他看德到遠方"), tg)["result"] == "right"
    assert J(rec(t, "他看地到遠方", asr2="他看地到遠方"), tg)["result"] == "right"
    assert J(rec(t, t), tg)["result"] == "undetermined"
    # 無旗標(非 always)維持 other -> 看相似度
    assert J(rec(t, "他看不到遠方", asr2="他看不到遠方"), {2: ("得", "de5")})["result"] == "right"


def test_rule_of_word_and_re():
    rules = V.build_rules()
    h = V.rule_hits(rules, "這部著作很有名")
    assert len(h) == 1
    rid = next(iter(h))
    r = next(x for x in rules if x.id == rid)
    assert r.ch == "著" and "著作" in r.words and h[rid][0] == [2]
    h = V.rule_hits(rules, "他終於睡著了")
    r = next(x for x in rules if x.id == next(iter(h)))
    assert r.regs and r.py == "[zh][áo]" and next(iter(h.values()))[0] == [4]
    assert list(V.rule_hits(rules, "他看著遠方發呆")) == ["著#default"]   # 預設讀音(着)只命中預設標注規則,沒有非預設規則


def test_synth_hits_own_rule():
    rules = V.build_rules()
    for r in rules[:60]:
        for s, pos, key in V.synth_sentences(r, rules, set(), 2):
            assert V.rule_hits(rules, V.CT.unsay(s)).get(r.id, ([],))[0] == pos
    r = next(x for x in rules if x.regs and x.ch == "著" and "睡" in x.regs[0].pattern)
    assert V.synth_sentences(r, rules, set(), 2)   # re 型規則也造得出句


def test_plan_counts_and_deterministic():
    a, rules, st = V.plan(2)
    b, _, _ = V.plan(2)
    assert [(i["rule"], i["mtext"]) for i in a] == [(i["rule"], i["mtext"]) for i in b]
    assert all(1 <= sum(1 for i in a if i["rule"] == r.id) <= 2 for r in rules if r.id in {i["rule"] for i in a})
    assert len({i["mtext"] for i in a}) == len(a)            # 句子不重複
    assert all(i["synthetic"] == (i["tag"] == "synthetic") for i in a)
    assert st["real"] + st["synth"] + st["partial"] + st["none"] == len(rules)


if __name__ == "__main__":
    n = 0
    for k, fn in list(globals().items()):
        if k.startswith("test_") and callable(fn):
            fn()
            n += 1
    print(f"test_tts_pron_verify: {n} 項通過")
