#!/usr/bin/env python3
r"""口味回歸:channel\taste\cases\T01–T46 一鍵跑(使用者過去提過的每條意見,各案壞例要被抓到、好例不誤報)。

python -X utf8 pipeline/taste_run.py [--case T02[,T05]] [--json] [--audio] [--scan [N]]
  結果五種:pass(壞例抓到且好例不誤報)/ fail(壞例沒抓到或好例誤報、例外)/ llm(只能靠代理:editor-review/player-review)/
           audio(要 GPU 或原音檔;只有 --audio 才跑,預設不跑、不佔 GPU)/ gap(程式還沒有這項檢查;不算 pass)。
  結束碼:有 fail = 1,否則 0。--json 印機器可讀結果。--scan 掃最近 N(預設 10)支 script.txt 的新 lint 命中數(誤報率校準用)。
  每案一個函式(見 CASES),直接呼叫現成檢查函式(script_lint / spec_check / tts_cosy_text / terms_check / freeze / deliver / build…),
  不用 LLM、不碰 GPU。需要檔案的案例只在 tmp\taste\<T>\ 建,清理只刪完整明確路徑(_rm 只認 tmp\taste 的直接子目錄)。
  用配音環境 python(jieba、pytest 在內):tts_env_chattts\Scripts\python.exe -X utf8 pipeline/taste_run.py
索引與案例說明:channel\taste\README.md、channel\taste\cases\。規格:PLAN_工作室v2 §7。
"""
import argparse
import contextlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

PIPE = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPE))
import paths as P  # noqa: E402

FIX = PIPE / "tests" / "fixtures"
TMP = P.TMP / "taste"
STATUSES = ("pass", "fail", "llm", "audio", "gap")
CASES = {}   # id -> dict(title, fn, audio=(指令清單 or None))
_made = []   # 這次建過的工作目錄(結束時逐一刪)


def case(tid, title, audio=None):
    def deco(fn):
        CASES[tid] = dict(title=title, fn=fn, audio=audio)
        return fn
    return deco


# ---- 結果與工具 ----
def llm(note):
    return "llm", note


def gap(note):
    return "gap", note


def judge(*checks, note=""):
    """checks = [(說明, 是否成立)];全成立 pass,否則 fail 並列出哪幾條不成立。"""
    bad = [w for w, ok in checks if not ok]
    return ("fail", "不成立:" + "；".join(bad)) if bad else ("pass", note)


def _rm(d):
    """只刪 tmp\\taste 的直接子目錄(完整明確路徑,不比對名稱)。"""
    d = Path(d)
    if d.parent != TMP:
        raise RuntimeError(f"拒絕刪除 {d}:不是 {TMP} 的直接子目錄")
    if d.is_dir():
        shutil.rmtree(d)


def workdir(tid):
    d = TMP / tid
    _rm(d)
    d.mkdir(parents=True)
    _made.append(d)
    return d


def cleanup():
    for d in _made:
        _rm(d)
    with contextlib.suppress(OSError):
        TMP.rmdir()   # 只在空的時候才會成功


def numbered(texts):
    return [(i + 1, t) for i, t in enumerate(texts)]


def fixture_lines(name):
    """tests/fixtures/taste/<name>:script.txt 格式(標籤|字幕),略過 # 與空行 -> (行號, 字幕);另回段落標題行號。"""
    out, starts = [], []
    for n, raw in enumerate((FIX / "taste" / name).read_text(encoding="utf-8").splitlines(), 1):
        if raw.startswith("#"):
            starts.append(n)
        elif "|" in raw and raw.strip():
            out.append((n, raw.split("|", 1)[1].strip()))
    return out, starts


def names_of(warns):
    return " / ".join(w[0] for w in warns)


@contextlib.contextmanager
def patched(mod, **attrs):
    keep = {k: getattr(mod, k) for k in attrs}
    for k, v in attrs.items():
        setattr(mod, k, v)
    try:
        yield
    finally:
        for k, v in keep.items():
            setattr(mod, k, v)


def run_pytest(*files):
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider", *[str(PIPE / "tests" / f) for f in files]],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(P.REPO), timeout=600)
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return r.returncode == 0, tail


# ================= B 段:文案 =================
@case("T01", "開場前五句把全片論點都塞進去")
def t01():
    import script_lint as L
    v1, _ = fixture_lines("pbz_review_v1.txt")
    v2, _ = fixture_lines("pbz_review_v2.txt")
    return judge(("pbz_review v1 開場應報 OPEN_LOAD", bool(L.opening_load(v1))), ("pbz_review v2 開場不應報", not L.opening_load(v2)),
                 note="名詞數門檻未校準(v1=19、v2=10),警告項")


@case("T02", "「這條不成立」判決腔")
def t02():
    import script_lint as L
    bad = ["這條不成立。", "這條算說對一半。", "這個說法站不住腳。", "說不過去。"]
    good = ["她確實拿隻狼比,但也寫到節奏快得多。", "兩邊的數字都對得上。"]
    hit = lambda t: any(x["code"] == "VERDICT" and x["block"] for x in L.sentence_hits(1, t, None, None))
    return judge(*[(f"壞例「{t}」應被 VERDICT 擋", hit(t)) for t in bad], *[(f"好例「{t}」不應誤報", not hit(t)) for t in good])


@case("T03", "同一個分數換四種說法重講")
def t03():
    return llm("換說法重講只能靠 editor-review 代理判;下限(同一 F 被 >=3 句引用)未建")


@case("T04", "「她」出現時觀眾還不知道她是誰")
def t04():
    import script_lint as L
    bad = ["這個分數很低。", "她給了三顆星。", "Emma Kent 是 Eurogamer 的評論者。"]
    good = ["Emma Kent 是 Eurogamer 的評論者。", "她給了三顆星。", "這個分數很低。"]
    plural = ["其他玩家也這樣想。", "他們一起罵了一輪。"]
    return judge(("她先於人名應警告", bool(L.pronoun_before_name(numbered(bad)))), ("人名在前不應警告", not L.pronoun_before_name(numbered(good))),
                 ("他們/其他不算代名詞", not L.pronoun_before_name(numbered(plural))))


@case("T05", "旁白唸出處、交代怎麼查")
def t05():
    import script_lint as L
    bad = ["這款遊戲這次改了難度。", "巴哈有玩家說後期怪物變很硬。", "暴雪論壇上也有人問過同一件事。", "某媒體九月十八號就寫了這件事。", "補丁之後怪物的血量少了兩成。"]
    good = ["這款遊戲這次改了難度。", "後期怪物的血量變多了。", "補丁之後怪物的血量少了兩成。"]
    verify = ["我把資料翻過一遍。", "我能確定的是這個數字。"]
    return judge(("連 3 句來源起句應報 SOURCE_LEAD", "SOURCE_LEAD" in names_of(L.fluency_warnings(numbered(bad)))),
                 ("事實起句不應報", "SOURCE_LEAD" not in names_of(L.fluency_warnings(numbered(good)))),
                 ("「我把資料翻過一遍」類應報交代查證", "交代查證" in names_of(L.v2_warnings(numbered(verify)))))


@case("T06", "連續句互不相干(旁白流暢度)")
def t06():
    import script_lint as L
    bad = ["今天天氣很好。", "鋼琴總共有八十八個鍵。", "火星比地球小得多。", "咖啡豆大多產在熱帶地區。", "貓會在夜裡到處亂跑。"]
    good = ["這款遊戲的難度很高。", "所以很多玩家卡在第一個頭目。", "可是頭目的血量其實不多。", "結果大家都在找補丁。"]
    return judge(("互不相干連續句應報 CHAIN_BREAK", "CHAIN_BREAK" in names_of(L.fluency_warnings(numbered(bad)))),
                 ("句句接住不應報", "CHAIN_BREAK" not in names_of(L.fluency_warnings(numbered(good)))))


@case("T07", "一句塞太多子句與數字")
def t07():
    import script_lint as L
    bad = ["北韓打進首爾,韓戰到現在沒結束,只是停火,雙方還在對峙,美軍也沒撤走,所以邊界很緊張。"]
    bad_n = ["首週賣了 200 萬套,營收 1 億美金,評分 88 分。"]
    good = ["背景是北韓打進首爾。", "韓戰到今天都還沒正式結束,只是停火而已。"]
    return judge(("5 子句以上應報 CLAUSES", "CLAUSES" in names_of(L.fluency_warnings(numbered(bad)))),
                 ("3 組數字應報 NUMS", "NUMS" in names_of(L.fluency_warnings(numbered(bad_n)))),
                 ("拆句後不應報", not any(k in names_of(L.fluency_warnings(numbered(good))) for k in ("CLAUSES", "NUMS"))))


@case("T08", "價格只有美金、沒有台幣")
def t08():
    import script_lint as L
    bad = [(1, "二零二一年直升一隻 39.99 美金。")]
    ok_nt = [(1, "二零二一年直升一隻 39.99 美金,折合台幣一千兩百多。")]
    rev = [(1, "財報營收一共 5 億美金。")]
    vbad = [(1, {"text": "x", "img": "card:價格 $39.99", "f": []})]
    vgood = [(1, {"text": "x", "img": "card:價格 $39.99 NT$999", "f": []})]
    return judge(("只有美金應報缺台幣", bool(L.price_twd_missing(bad))), ("句內有台幣不應報", not L.price_twd_missing(ok_nt)),
                 ("財報營收維持美金不應報", not L.price_twd_missing(rev)),
                 ("畫面卡有 $ 無 NT$ 應報", bool(L.price_twd_missing([(1, "價格如畫面。")], vbad))),
                 ("畫面卡補 NT$ 不應報", not L.price_twd_missing([(1, "價格如畫面。")], vgood)))


@case("T09", "用了中國譯名")
def t09():
    import spec_check as S
    names = {"Phantom Liberty": {"tw": "自由幻局", "avoid": ["往日之影"]}}
    run = lambda t: S.check({"tw_names": names}, [{"text": t}])
    return judge(("含他譯應報錯", len(run("這次資料片叫往日之影,玩家很期待")) == 1), ("用台灣譯名不應報", run("這次資料片叫自由幻局,玩家很期待") == []))


@case("T10", "同一事件日期各來源矛盾")
def t10():
    return llm("來源矛盾只能靠 player-review 代理;下限(facts 表同事件日期不一致)未建")


@case("T11", "成片數字與來源不符")
def t11():
    d = workdir("T11")
    (d / "projects" / "ft").mkdir(parents=True)
    (d / "ft").mkdir()
    src = FIX / "facts" / "proj"
    shutil.copy(src / "facts.md", d / "projects" / "ft" / "facts.md")
    shutil.copy(src / "spec.json", d / "projects" / "ft" / "spec.json")
    env = dict(os.environ, CLAUDE_VIDEO_ROOT=str(d), PYTHONIOENCODING="utf-8")

    def run(script):
        shutil.copy(src / script, d / "ft" / "script.txt")
        return subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "facts_check.py"), "ft", "--strict"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, cwd=str(P.REPO), timeout=120)
    bad, good = run("script.txt"), run("script_ok.txt")
    return judge(("錯數字 script 應 exit 1", bad.returncode == 1), ("正確 script 應 exit 0", good.returncode == 0),
                 note="用 tests/fixtures/facts 的壞/好 script(非 cod_tax 原句)")


@case("T12", "幅度誇大、無出處的動機推論")
def t12():
    return llm("誇大與動機推論只能靠 player-review 代理")


@case("T13", "玩家審抓到的語意與算式錯")
def t13():
    return llm("數字語意與時間算式只能靠 player-review 代理")


@case("T14", "使用者沒玩過卻寫第一人稱遊玩經歷")
def t14():
    import script_lint as L
    d = workdir("T14")
    (d / "handoff.md").write_text("- 使用者沒玩過;沒有使用者提供的話。\n", encoding="utf-8")
    played = workdir("T14b")
    (played / "handoff.md").write_text("- 使用者有玩,通關兩次。\n", encoding="utf-8")
    bad = numbered(["我玩了 12 小時,後期真的很硬。", "我通關了一次。", "我打了 5 小時才過。", "我看了 9 分鐘就睡著了。"])
    good = numbered(["我看了預告,畫面很漂亮。", "我看了兩遍才敢相信。", "這是我玩過最好的遊戲,標題這樣寫。", "我看了 3 分鐘直播。"])
    return judge(("handoff 寫沒玩過 -> not_played", L.not_played(str(d))), ("handoff 沒寫沒玩過 -> 不擋", not L.not_played(str(played))),
                 ("沒玩過 + 第一人稱時數句應擋(4 句)", len(L.played_claims(bad, False)) == 4), ("看預告/看兩遍/引述標題不應擋", not L.played_claims(good, False)),
                 ("有玩過就不查", not L.played_claims(bad, True)), note="「我看了 9 分鐘」類只有帶數字單位才擋,看預告/直播除外")


@case("T15", "預防針、免責、中立聲明句")
def t15():
    import script_lint as L
    bad = ["這個平均不是虛的。", "我不選邊,你自己判斷。", "先說清楚,這只是整理。", "我不站隊。"]
    good = ["九十分以上的評論有二十七篇。", "先看平均,再看那兩篇。", "他自己判斷了很久才出手。"]
    return judge(*[(f"壞例「{t}」應報免責", bool(L.DISCLAIMER.search(t))) for t in bad], *[(f"好例「{t}」不應誤報", not L.DISCLAIMER.search(t)) for t in good],
                 ("v2_warnings 帶出免責項", "免責" in names_of(L.v2_warnings(numbered(bad)))))


# ================= C 段:配音 =================
@case("T16", "助詞「著」被唸成「住」", audio=["tts_c0.py", "cod_tax_rw", "--dry-run"])
def t16():
    import tts_cosy_text as CT
    t1, h1 = CT.pron_text("她跟著我走。")
    t2, h2 = CT.pron_text("著名的人。")
    return judge(("助詞著不得標成 [zh][ù]", "[zh][ù]" not in t1), ("助詞著套規則(著→着)", any("著→着" in h for h in h1)), ("著名仍標 zhù", "[zh][ù]名" in t2),
                 note="文字層;唸對與否(ASR 回查)要 --audio 或真跑 C0")


@case("T17", "卡在 qiǎ、炸 zhá 這類同字異音", audio=["tts_c0.py", "cod_tax_rw", "--dry-run"])
def t17():
    import tts_cosy_text as CT
    t, _ = CT.pron_text("卡在這裡,這一炸很兇。")
    return judge(("卡在 -> [k][ǎ]", "[k][ǎ]在" in t), ("炸 -> [zh][à]", "[zh][à]" in t), note="文字層;真唸要 tts_pron_verify/人耳")


@case("T18", "輕聲「得」被拼音記號弄壞")
def t18():
    import tts_cosy_text as CT
    a, _ = CT.apply_rules("那裡看得到,做得出。")
    return judge(("得 -> 的(共用規則)", a == "那裡看的到,做的出。"), note="文字層;ASR 是否回「看得到」要真跑")


@case("T19", "同一人名每句唸法不同")
def t19():
    import terms_check as TC
    import tts_cosy_text as CT
    import tts_term_qc as TQ
    t = "我們看 Eurogamer 的評語"
    ok = [(1, t, "我们看eurogamer的评语"), (2, t, "我们看eurogamer的评语"), (3, t, "我们看eurogamer的评语")]
    bad = ok[:2] + [(3, t, "我们看白先生的评语")]
    with patched(CT, TERMS={}, DIRECT=["Steam"], TERMS_VERIFIED=set()):
        unreg = TC.unregistered(["Avellone 說了一句。", "Avellone 又說。"])
    b, _, majors = TQ.inconsistent(bad)
    g, _, _ = TQ.inconsistent(ok)
    return judge(("多數寫法 + 差異大應命中 term_inconsistent", list(b) == [3]), ("三句一致不應命中", not g), ("未登錄英文人名配音前被擋", unreg == ["Avellone"]))


@case("T20", "EA 唸成「E欸」,廠商唸中文名")
def t20():
    import tts_cosy_text as CT
    out = CT.apply_terms("EA 宣布關閉 BioWare。")
    return judge(("EA -> 藝電(送引擎文字帶拼音 yìdiàn)", "EA" not in out and ("藝電" in out or "[d][iàn]" in out)), ("BioWare -> 生軟", "生軟" in out and "BioWare" not in out))


@case("T21", "BioWare 的 ware 唸「哇」;英文名唸不對")
def t21():
    import terms_check as TC
    import tts_cosy_text as CT
    import tts_term_qc as TQ
    with patched(CT, TERMS={}, DIRECT=[], TERMS_VERIFIED=set()):
        before = TC.unregistered(["BioWare 關門了。"])
    with patched(CT, TERMS={"BioWare": "生軟"}, DIRECT=[], TERMS_VERIFIED=set()):
        after = TC.unregistered(["BioWare 關門了。"])
    return judge(("未登錄 BioWare 配音前被擋", before == ["BioWare"]), ("登錄後不再擋", after == []), ("沒辨識文字不判", TQ.loose_misses("做出 Kotaku", "") == []),
                 note="詞內拆讀(哇)靠寬鬆比對放過=已知漏網,人耳才聽得出")


@case("T22", "SBI、DEI、IGN 縮寫與品牌唸法")
def t22():
    import terms_check as TC
    import tts_cosy_text as CT
    with patched(CT, TERMS={"IGN": "艾吉恩"}, DIRECT=[], TERMS_VERIFIED=set()):
        reg = CT.apply_terms("IGN 給了九分。")
        unreg = TC.unregistered(["Sweet Baby Inc 做的。"])
    return judge(("登錄的縮寫被套用", "艾吉恩" in reg), ("未登錄品牌配音前被擋", unreg == ["Sweet Baby Inc"]), note="現行表有 IGN/DEI,無 Sweet Baby Inc;偏好本身要使用者聽過才登錄")


@case("T23", "逗號處模型連讀")
def t23():
    import tts_pause as TP
    mk = lambda at, sil, soft=False: dict(at=at, sil=sil, soft=soft)
    return judge(("原始靜音 0.0 = comma_runon", TP.comma_runon([mk("市|匿", 0.0)]) == [dict(at="市|匿", before=0.0)]),
                 ("0.20 秒不算連讀", TP.comma_runon([mk("市|匿", 0.20)]) == []), ("頓號不算", TP.comma_runon([mk("甲|乙", 0.0, True)]) == []),
                 ("門檻 0.05", TP.COMMA_RUNON_MIN == 0.05), note="合成紀錄;ea_me5 句 15 原音檔重驗要 GPU/音檔")


@case("T24", "停頓斷在語意錯的位置")
def t24():
    import tts_pause as TP
    mk = lambda sil: [dict(at="宣布|關門", sil=sil, soft=False)]
    return judge(("逗號靜音 0.03 < COMMA_MIN 應報 comma_bad", TP.comma_bad(mk(0.03)) == ["宣布|關門"]), ("0.15 秒不報", TP.comma_bad(mk(0.15)) == []),
                 note="只涵蓋靜音長度;語意該不該斷靠 pron-review 代理,stray_pause 要音檔")


@case("T25", "音節被吞、種族名逐字停頓")
def t25():
    return gap("吞音沒有人耳校準門檻,現行 content/asr_loose 放過(wow_eternal_pre v1 句 4/6);音節數對齊檢查未建")


@case("T26", "句中或句間多唸一個字", audio=["tts_cosy3.py", "--requal", "ai_nextfest", "--dry-run"])
def t26():
    import tts_cosy3 as C3
    return judge(("兩個辨識都多出「大」應報 asr_insert", bool(C3.asr_inserts("這個反派很強", "這個大反派很強", "這個大反派很強"))),
                 ("辨識與送出文字相同不報", not C3.asr_inserts("這個反派很強", "這個反派很強", "這個反派很強")), note="合成辨識結果;--requal 離線重算要 --audio")


@case("T27", "為了讓某句過品管,把辨識錯的寫法加進 _asr_alias")
def t27():
    import freeze as FZ
    base = {"EA": ["藝電"]}
    cur = {"EA": ["藝電", "易電"], "Kotaku": ["口他口"]}
    text = "EA 宣布 Kotaku 的報導。"
    return judge(("新增別名且本片用到應擋(2 筆)", len(FZ.alias_problems("x", cur=cur, base=base, text=text)) == 2),
                 ("沒新增不擋", FZ.alias_problems("x", cur=base, base=base, text=text) == []),
                 ("新增別名但本片沒用到不擋", FZ.alias_problems("x", cur=cur, base=base, text="今天天氣很好。") == []),
                 note="freeze() 整合(--alias-ok 放行)見 tests/test_taste_run.py")


@case("T28", "C0 試配「無法判定」被當成通過")
def t28():
    import tts_c0 as C0
    ok = C0.OUTCOME == {"right": "唸對", "wrong": "唸錯", "undetermined": "無法判定"}
    return gap(("三類計數已輸出(OUTCOME 三項齊),但" if ok else "OUTCOME 標籤變了;且") + "無法判定>0 時 handoff 必須列位置與『未聽審』的檢查未建")


@case("T29", "BGM 太小聲")
def t29():
    import build as B
    return judge(("BGM_BELOW_VOICE_DB 在 5.2–6.2", 5.2 <= B.BGM_BELOW_VOICE_DB <= 6.2), note="只驗常數;實際比配音低幾 dB 要看 build log『BGM:』行")


@case("T30", "改讀音表後配音快取不失效")
def t30():
    import build as B
    import tts_cosy_text as CT
    import tts_key as TK
    say = "這個差距很大幅。"
    rec = {"pron_hits": CT.pron_hits(say), "term_hits": CT.term_hits(say)}
    unchanged = not CT.pron_changed(rec, say)
    with patched(CT, PRON={**CT.PRON, "大幅": "大[f][ǔ]"}):
        changed = CT.pron_changed(rec, say)
    with patched(CT, TERMS={**CT.TERMS, "Roblox": "Row blocks"}):
        tchanged = CT.terms_changed({"term_hits": {"Roblox": "Roblox"}}, "他在 Roblox 上做。")
    src = inspect.getsource(B.tts_all) if hasattr(B, "tts_all") else ""
    return judge(("讀音表沒改:不重錄", unchanged), ("cosy_pron 改「大幅」讀音:pron_changed", changed), ("cosy_terms 改寫法:terms_changed", tchanged),
                 ("build.tts_all 用 _pron_changed 讓舊音檔作廢重錄", "_pron_changed(engine, u" in src),
                 ("chattts 快取鍵含修正後文字", TK.audio_key("chattts", "s", "v", 1, "跟著我") != TK.audio_key("chattts", "s", "v", 1, "跟我")),
                 note="cosy3 的 audio_key 不含讀音文本(鍵不變),靠 .qc.json 的 pron_hits/term_hits 比對在 build.tts_all 作廢;不需改鍵")


# ================= D 段:畫面 =================
def _img_lines(specs, fps=None):
    import build as B
    fps = fps or B.FPS
    out, t = [], 0.0
    for i, (kind, key, sec) in enumerate(specs, 1):
        ln = dict(idx=i, f0=round(t * fps), f1=round((t + sec) * fps))
        ln[kind] = key if kind == "img" else ({"x": 1} if kind == "quote" else key)
        if kind == "quote":
            ln["img"] = key
        t += sec
        out.append(ln)
    return out


@case("T31", "同一張圖連續超過 9 秒或 2 句")
def t31():
    import build as B
    bad = _img_lines([("img", "a.png", 5.0), ("img", "a.png", 5.0)])
    ok = _img_lines([("img", "a.png", 4.0), ("img", "a.png", 4.0), ("img", "b.png", 4.0)])
    many = _img_lines([("img", "a.png", 3.0)] * 3)
    return judge(("同圖連續 10 秒應報", any("9" in e for e in B.check_image_runs(bad, 2.5))), ("同圖 8 秒不報", not B.check_image_runs(ok, 2.5)),
                 ("同圖連續 3 句應報", bool(B.check_image_runs(many, 2.5))))


@case("T32", "hl 的字不在旁白、或在圖中找不到")
def t32():
    import build as B
    import visual_check as VC
    d = workdir("T32")
    # 旁白端:visual_check H(hl 不在旁白)
    def codes(hl):
        (d / "script.txt").write_text("# 測試" + chr(10) + "# 一" + chr(10) + f'img:a|工作室宣布裁員三成。 ;; {{"hl": ["{hl}"]}}' + chr(10), encoding="utf-8")
        top, defs, notes, lines = VC.load("t32", d / "script.txt")
        return [c for c, _i, _m in VC.check("t32", top, defs, notes, lines, None)[0]]
    # 圖端:build.precheck_images(hl 在 .boxes.json 找不到 → 錯誤)
    (d / "images").mkdir()
    try:
        from PIL import Image
    except ImportError:
        return gap("缺 PIL,圖端 precheck_images 無法實測")
    Image.new("RGB", (1200, 800), "white").save(d / "images" / "a.png")
    (d / "images" / "a.boxes.json").write_text(json.dumps([{"text": "裁員三成", "box": [100, 100, 500, 160]}], ensure_ascii=False), encoding="utf-8")

    def img_errs(kw):
        B._box_cache.clear()
        shot = dict(kind="image", img="a", fx="zoom", hls=[dict(line=1, kws=[kw])], focus=None, special=None)
        try:
            return B.precheck_images([shot], d)
        finally:
            B._box_cache.clear()
    try:
        bad_img, ok_img = img_errs("鬼打牆"), img_errs("裁員三成")
    except Exception as e:  # shot 欄位不齊時退回只量 _hl_hits
        return gap(f"precheck_images 假鏡頭欄位不齊,圖端未實測({type(e).__name__}: {e})")
    return judge(("hl 不在旁白應報 H", "H" in codes("鬼打牆")), ("hl 在旁白不報 H", "H" not in codes("裁員三成")),
                 ("hl 在圖上找不到應報 precheck_images 錯誤", any("找不到" in e for e in bad_img)), ("hl 在圖上命中不報", not ok_img),
                 note="壞例/好例實測:visual_check H + build.precheck_images(假圖+.boxes.json)")


@case("T33", "截圖文字被畫面邊緣切到")
def t33():
    ok, tail = run_pytest("test_text_clip.py")
    return judge(("既有單元測試 test_text_clip.py 通過", ok), note=f"沿用既有測試,非原案例畫面({tail})")


@case("T34", "出處小標籤壓到評論截圖的字")
def t34():
    return gap("build.py 標籤壓文字框檢查只在直式 portrait;橫式只查邊緣裁切,標籤框×boxes 重疊檢查未建(需圖與 boxes.json)")


@case("T35", "字幕拆段把詞切開、黏前字")
def t35():
    import build as B
    longs = ["我昨天晚上在家裡認真地玩完了星塵獵犬而且還玩了兩遍真的很好玩", "他花了二十五萬三千塊買下那台全新的遊戲主機結果發現根本沒有遊戲可以玩"]
    ok, tail = run_pytest("test_sub_split.py")
    return judge(("長句拆段後無接縫(拆段器已避開切詞)", not B.check_sub_seams([dict(idx=i, text=t) for i, t in enumerate(longs, 1)])),
                 ("既有單元測試 test_sub_split.py(含切詞壞例)通過", ok), note=f"壞例由既有測試覆蓋,非原案例句({tail})")


@case("T36", "引言卡過長、同圖撐出畫面")
def t36():
    import build as B
    bad = _img_lines([("quote", "q.png", 5.0), ("quote", "q.png", 5.0)])
    return judge(("quote 底圖同圖連續 10 秒應報", any("9" in e for e in B.check_image_runs(bad, 2.5))),
                 note="只涵蓋同圖時長;src 80 字網址撐出畫面無獨立檢查")


@case("T37", "要官網/貼文原圖,不要示意動畫")
def t37():
    return gap("visual_check A/B 不認得『官網/貼文/頁面』,原圖 vs 示意動畫檢查未建")


@case("T38", "素材片段有浮水印、黑場、分級標")
def t38():
    return gap("只有人工裁切與 build log 浮水印區警告;逐幀黑場/分級標/浮水印檢查未建(需影片)")


# ================= E 段:封面、交付 =================
@case("T39", "封面三行字太多")
def t39():
    import spec_check as S
    mk = lambda ls: {"package": {"titles": [], "thumbs": [{"plan": 1, "lines": ls}]}}
    bad = S.check_package(mk(["影之刃零評分", "三顆星扣分爭議真多", "官網看得到"]))[0]
    good = S.check_package(mk(["影之刃零", "評分爭議", "三顆星"]))[0]
    return judge(("三行合計超過 16 字應報錯", any("三行合計" in e for e in bad)), ("11 字不應報合計", not any("三行合計" in e for e in good)))


@case("T40", "封面人物與最近 10 張撞臉")
def t40():
    import spec_check as S
    d = workdir("T40")
    notes = lambda subj, scene: f"方案1\n主體:虛構原創玩家,{subj}\n場景:{scene}\n視覺構圖:紫粉色字\n"
    old = dict(tag="old", plan="1", kind="原創玩家", gender="男", age="二十多歲", hair="短髮", outfit="帽T", scene="電競房", gesture="食指指鏡頭", color="紫粉")
    same, other = d / "same.md", d / "other.md"
    same.write_text(notes("男生二十多歲短髮穿帽T,食指指鏡頭", "電競房"), encoding="utf-8")
    other.write_text(notes("女生三十多歲馬尾穿西裝,拍桌", "網咖"), encoding="utf-8")
    with patched(S, load_persona_log=lambda: [old]):
        e1 = S.check_persona("new", same)[0]
        e2 = S.check_persona("new", other)[0]
    return judge(("六格全同應報人像重複", bool(e1)), ("換人物不報", not e2))


@case("T41", "改版重作封面、標題與排程被改掉")
def t41():
    import deliver as D
    d = workdir("T41")
    (d / "a.claude.json").write_text(json.dumps(dict(tag="x", ver="v1", title="影之刃零評分爭議", cover="影之刃零評分爭議_v1_封面.png"), ensure_ascii=False), encoding="utf-8")
    ri = lambda ver, title, cover: D.revision_issues("x", ver, title, cover, inbox=d)
    return judge(("v2 沒帶 --cover 應警告", len(ri("v2", "影之刃零評分爭議", None)) == 1), ("v2 標題不同應警告", len(ri("v2", "別的標題", "c.png")) == 1),
                 ("v2 帶封面、同標題不警告", ri("v2", "影之刃零評分爭議", "c.png") == []), ("v1 不查", ri("v1", "別的標題", None) == []),
                 note="排程(發布時間不變)未查:本機沒有上一版排程資料")


@case("T42", "說明檔署名區塊缺、空、或重複")
def t42():
    import deliver as D
    ds = "【YouTube章節摘要】\n0:00 開場\n【輸出完畢】"
    md = lambda sig: f"## 發片資料\n```text\n{ds}\n```\n{sig}"
    full = md("## 說明欄署名\n```text\n資料來源:x\n```\n")
    dup = md("## 說明欄署名\n(待補)\n\n## 說明欄署名\n```text\n資料來源:x\n```\n")
    empty = md("## 說明欄署名\n")
    miss = lambda m: D.enqueue_missing(*D.parse_notes(m))
    return judge(("齊全不缺", miss(full) == []), ("署名空應報缺", bool(miss(empty))), ("第一個署名空、第二個有(重複)應報缺", bool(miss(dup))),
                 note="「重複區塊」目前以第一個為準(第一個空就擋),沒有獨立的重複警告")


@case("T43", "說明檔發片資料沒有換行(缺 ```text 區塊)")
def t43():
    import deliver as D
    sig = "## 說明欄署名\n```text\n資料來源:x\n```\n"
    nofence = "## 發片資料\n【YouTube章節摘要】\n0:00 開場\n【輸出完畢】\n" + sig
    fenced = "## 發片資料\n```text\n【YouTube章節摘要】\n0:00 開場\n【輸出完畢】\n```\n" + sig
    miss = lambda m: D.enqueue_missing(*D.parse_notes(m))
    return judge(("發片資料沒包 ```text 應報缺", any("發片資料" in x for x in miss(nofence))), ("有包不報", miss(fenced) == []))


@case("T44", "發布時間:該由使用者自己排的片被排程")
def t44():
    import deliver as D
    a, b = workdir("T44"), workdir("T44b")
    (a / "handoff.md").write_text("- **發布時間使用者自己手動排**:E 段上傳後保持私人。\n", encoding="utf-8")
    (b / "handoff.md").write_text("- 塊間因果:原因是動視自己排的節奏。\n", encoding="utf-8")
    return judge(("使用者自己排 + --publish-at 應擋", bool(D.schedule_conflict(str(a), "auto"))), ("沒帶 --publish-at 不擋", D.schedule_conflict(str(a), None) is None),
                 ("無關的「自己排」不誤擋", D.schedule_conflict(str(b), "auto") is None))


@case("T45", "改版後舊版未設私人/取消排程")
def t45():
    return gap("需後端 API(查上一版 video_id 的 privacyStatus/publish_at);本機無資料可驗,刪片仍人工(digest §2 #6)")


@case("T46", "B 站搬運候選不是夥伴、是 AI 動畫、含電影畫面")
def t46():
    return gap("candidates 沒有夥伴/AI 動畫/電影畫面的結構化欄位,僅人工篩;無資料可驗")


# ---- 執行 ----
def run_audio(c):
    """--audio:另外跑案例的音檔層指令(CPU dry-run、不合成);回 (ok, 說明)。"""
    cmd = [sys.executable, "-X", "utf8", str(PIPE / c["audio"][0]), *c["audio"][1:]]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(P.REPO), timeout=900)
    return r.returncode == 0, "exit " + str(r.returncode) + (":" + (r.stderr.strip().splitlines() or [""])[-1][:80] if r.returncode else "")


def run_case(tid, audio=False):
    c = CASES[tid]
    try:
        st, note = c["fn"]()
    except Exception as e:  # noqa: BLE001
        st, note = "fail", f"例外 {type(e).__name__}: {e}" + "|" + traceback.format_exc().strip().splitlines()[-3].strip()[:90]
    assert st in STATUSES, (tid, st)
    if c["audio"]:
        if audio and st == "pass":
            ok, why = run_audio(c)
            st, note = ("pass", f"{note};音檔層 OK({why})") if ok else ("fail", f"音檔層失敗:{why}")
        elif not audio:
            note = (note + ";" if note else "") + "音檔層未跑(--audio)"
    return dict(id=tid, title=c["title"], status=st, note=note)


def scan_recent(n=10):
    """最近 n 支 script.txt 的新 lint 命中數(誤報率校準用)。"""
    import script_lint as L
    tags = sorted((p.parent.name for p in P.REPO.glob("*/script.txt")), key=lambda t: -(P.REPO / t / "script.txt").stat().st_mtime)[:n]
    rows = []
    for t in tags:
        lines = L.spoken_lines(t)
        rows.append(dict(tag=t, sentences=len(lines), OPEN_LOAD=len(L.opening_load(lines)), PRONOUN_FIRST=len(L.pronoun_before_name(lines, L.spec_names(t))),
                         PRICE_TWD=len(L.price_twd_missing(lines, L.visual_lines(t, lines))), DISCLAIMER=sum(1 for _, x in lines if L.DISCLAIMER.search(x)),
                         PLAYED_CLAIM=len(L.played_claims(lines, not L.not_played(t)))))
    return rows


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="口味回歸(見檔頭)")
    ap.add_argument("--case", help="只跑指定案例,逗號分隔(例 T02,T05)")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    ap.add_argument("--audio", action="store_true", help="也跑音檔層指令(CPU dry-run,不合成)")
    ap.add_argument("--scan", nargs="?", type=int, const=10, metavar="N", help="掃最近 N 支 script.txt 的新 lint 命中數後結束")
    a = ap.parse_args(argv)
    if a.scan:
        rows = scan_recent(a.scan)
        print(json.dumps(rows, ensure_ascii=False, indent=1) if a.json else "\n".join(" ".join(f"{k}={v}" for k, v in r.items()) for r in rows))
        return 0
    ids = [x.strip().upper() for x in a.case.split(",")] if a.case else sorted(CASES)
    bad = [i for i in ids if i not in CASES]
    if bad:
        print(f"沒有這個案例:{','.join(bad)}", file=sys.stderr)
        return 2
    try:
        res = [run_case(i, a.audio) for i in ids]
    finally:
        cleanup()
    count = {s: sum(1 for r in res if r["status"] == s) for s in STATUSES}
    if a.json:
        print(json.dumps(dict(results=res, count=count), ensure_ascii=False, indent=1))
    else:
        for r in res:
            print(f"{r['id']} {r['status']:<5} {r['title'][:30]}" + (f"  — {r['note']}" if r["note"] else ""))
        print("統計:" + " / ".join(f"{s} {count[s]}" for s in STATUSES) + f"(共 {len(res)} 案;gap 不算 pass)")
    return 1 if count["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
