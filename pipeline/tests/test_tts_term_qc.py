"""英文詞品管 tts_term_qc 與詞界長停頓 tts_pause.wb_long(純函式、不需顯示卡;音近要 pypinyin):
tts_env_chattts\Scripts\python.exe -X utf8 pipeline\tests\test_tts_term_qc.py"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tts_cosy_text as CT  # noqa: E402
import tts_pause as TP  # noqa: E402
import tts_term_qc as TQ  # noqa: E402

FAILS = []


def expect(name, cond, detail=""):
    print(("通過" if cond else "失敗"), name, detail)
    if not cond:
        FAILS.append(name)


def test_direct_open():
    d, v = CT.DIRECT, CT.TERMS_VERIFIED
    CT.DIRECT, CT.TERMS_VERIFIED = ["Foo Bar", "Baz Qux", "Kotaku", "B"], {"Kotaku"}
    try:
        got = TQ.direct_open(["Foo Bar 說", "Kotaku 與 B 級", "又是 Foo Bar", "Baz Qux 一次", "Kotaku"])
    finally:
        CT.DIRECT, CT.TERMS_VERIFIED = d, v
    expect("未驗證多次/單次都列,已驗證與單一字母不列", got == {"Foo Bar": [1, 3], "Baz Qux": [4]}, str(got))


def test_build_script_marks_direct():
    """配音稿:多次 = 未決 + 標「建議音譯」,單次 = 警告、不算未決(假資料,寫 tmp\;不跑 g2p/backlog)。"""
    import freeze as FZ
    import paths as P
    import pron_backlog as PB
    import seg as SEG
    import tts_g2p as G
    import tts_script as TS
    tmp = P.TMP / "test_tts_term_qc"
    says = ["Foo Bar 說的。", "又是 Foo Bar。", "Baz Qux 一次。"]
    saved = (TS.script_lines, FZ.freeze_path, P.build_dir, G.predict_many, PB.upsert, SEG.set_tag, CT.DIRECT)
    TS.script_lines = lambda tag: [(dict(text=s), s) for s in says]
    FZ.freeze_path = lambda tag: tmp / "none.json"
    P.build_dir = lambda tag: tmp
    G.predict_many = lambda texts: None
    PB.upsert = lambda *a: (0, 0)
    SEG.set_tag = lambda tag: None
    CT.DIRECT = ["Foo Bar", "Baz Qux"]
    try:
        n = TS.build_script("__t", write_words=False)
        md = (tmp / "tts_script.md").read_text(encoding="utf-8")
    finally:
        TS.script_lines, FZ.freeze_path, P.build_dir, G.predict_many, PB.upsert, SEG.set_tag, CT.DIRECT = saved
        shutil.rmtree(tmp, ignore_errors=True)
    head = next(x for x in md.splitlines() if x.startswith("| 行"))
    row = next(x for x in md.splitlines() if x.startswith("| 1 "))
    expect("未決只算多次的詞", n == 1, str(n))
    expect("多次標建議音譯", "Foo Bar(英文直送多次:建議音譯)" in row, row)
    expect("單次標警告", "Baz Qux(英文直送單次)" in md and "英文直送單次(警告)1 詞" in md)
    expect("表頭與列欄數相同", head.count(" | ") == row.count(" | "), f"{head.count(' | ')} {row.count(' | ')}")


def test_frag():
    t = "替 BioWare 說話的人"
    expect("前後錨點取片段(繁簡不同)", TQ.frag(t, "替沈软说话的人", 2, 9) == "沈软")
    expect("整段沒唸回空字串", TQ.frag(t, "替说话的人", 2, 9) == "")
    expect("對不準回 None", TQ.frag("甲 Ab 乙", "甲" + "丙" * 30 + "乙", 2, 4) is None)


def test_loose():
    cases = {"做出 Kotaku 的報導": "做出白先生的报导", "評論 IGN 給分": "评论白先生给分"}
    for text, hyp in cases.items():
        r = TQ.loose_misses(text, hyp)
        expect(f"聽成無關字 = 唸錯:{text}", len(r) == 1 and r[0]["kind"] == "loose" and r[0]["src"] == "asr", str(r))
    expect("別名命中不算", TQ.loose_misses("做出 Kotaku 的報導", "做出口塔库的报导") == [])
    expect("拼寫辨識出來不算", TQ.loose_misses("做出 Kotaku 的報導", "做出kotaku的报导") == [])
    expect("音近(不在別名)不算", TQ.loose_misses("做出 Kotaku 的報導", "做出扣塔库的报导") == [])
    expect("中文寫法音近不算(生軟→沈软)", TQ.loose_misses("替 BioWare 說話", "替沈软说话") == [])
    expect("縮寫逐字母音譯不算", TQ.loose_misses("評論 IGN 給分", "评论艾吉恩给分") == [])
    expect("沒有辨識文字不判", TQ.loose_misses("做出 Kotaku", "") == [])


def test_inconsistent():
    t = "我們看 Eurogamer 的評語"
    items = [(1, t, "我们看eurogamer的评语"), (2, t, "我们看eurogamer的评语"), (3, t, "我们看白先生的评语")]
    bad, listen, majors = TQ.inconsistent(items)
    expect("多數寫法 + 差異大 = 命中", list(bad) == [3] and bad[3][0]["term"] == "Eurogamer" and "Eurogamer" in majors, str(bad))
    expect("重錄後回到多數寫法 = 通過", TQ.off_major(t, "我们看eurogamer的评语", majors) == [])
    expect("重錄後仍不同 = 未過", len(TQ.off_major(t, "我们看白先生的评语", majors)) == 1)
    bad, listen, majors = TQ.inconsistent(items[1:])
    expect("兩句各一種 = 無多數,不擋、不像原詞的列優先聽", not bad and list(listen) == [3] and not majors, str((bad, listen)))
    bad, listen, _ = TQ.inconsistent(items[2:])
    expect("只有 1 句不擋、列優先聽", not bad and list(listen) == [3], str((bad, listen)))
    items2 = items[:2] + [(3, t, "我们看优若嘎么的评语")]
    bad, _, _ = TQ.inconsistent(items2 + [(4, t, "我们看eurogamer的评语")])
    expect("少數寫法仍音近原詞 = 不命中", not bad, str(bad))


def test_wb_long():
    ss = [dict(at="a|b", sil=0.19, kind="wb"), dict(at="c|d", sil=0.20, kind="wb"), dict(at="e|f", sil=0.3, kind="mid")]
    expect("只算詞界 >= STRAY_WB_FAIL", TP.wb_long(ss) == ["c|d"], str(TP.wb_long(ss)))
    expect("None 容忍", TP.wb_long(None) == [])


if __name__ == "__main__":
    for f in (test_direct_open, test_build_script_marks_direct, test_frag, test_loose, test_inconsistent, test_wb_long):
        f()
    print("失敗:", FAILS if FAILS else "無")
    sys.exit(1 if FAILS else 0)
