"""文案「AI 感」檢查:python -X utf8 pipeline/script_lint.py <tag> [--all]
讀 <tag>/script.txt 的旁白行(標籤|字幕),只印摘要與超標項目(--all 列出每一筆命中)。
門檻是 2026-10-10 依《永恆》經驗片(被觀眾說 AI 感重的那支)當反例訂的初值,不是校準過的標準;規則說明見 CLAUDE.md「文案:去 AI 感」。
v2(2026-10-20):新增 7 組警告檢查(重講、代稱、暖場、交代查證、免責唸出口、同骨架、第一個判斷句),長句比例與句長變異係數降為警告;
警告不影響結束碼,加 --strict 才與超標同等(門檻在檔頭 T)。make_version 只讀「超標 N 項」與結束碼,輸出契約不變。
"""
import argparse
import json
import re
import statistics
import sys
import warnings

import locale_cfg
import pace
import paths as P

# 所有門檻集中在這裡(2026-10-20 規則_文案 v2 調整:判斷句 25 秒、字速 5.5、語助詞不設下限、反應句降為警告)。「既有」= 2026-10-10 依《永恆》經驗片訂的初值;「v2 新增」= 2026-10-20 診斷
# (channel/research_文案優化_2026-10-20/00_診斷.md §1.1、§3;60_規則_工具_流程落差.md 表 1)的初值,皆未校準。
T = dict(
    # 既有(超標算錯誤,make_version 中止)
    signpost_ratio=0.05, not_but=2, formal=2, triple=1, parallel=2, bad_particle=0, summary=1, self_qa=3, telegram=1, verdict=0,
    particle_hi=0.35, react=0.04,   # 2026-10-20 規則_文案 v2:語助詞比例不設下限(§1.3),只留上限
    # cv_min 2026-10-20 R\92:規則 v2 已無長短句依據,0.28 → 0.22,只擋極端
    # 既有但 2026-10-20 降為警告(--strict 才算錯誤):規則_文案「越白話越好…衝突時以本條為準」(2026-10-13 使用者指定)優先於節奏不齊
    cv_min=0.22, long_chars=24, long_ratio=0.10,
    # v2 新增(全是警告;--strict 才算錯誤)
    num_repeat=3,                  # 同一個數字字串在旁白出現次數 >= 此值
    pair_overlap=0.6, pair_min_kw=4, pair_min_hit=3,   # 非相鄰兩句名詞/動詞關鍵詞重疊率 >= 0.6(以較少的一句為分母;至少 4 個關鍵詞、交集 >= 3)
    pronoun_max=0, pronoun_run=3,  # 代稱命中數上限;句首「他/她/它」連續句數 >=
    warmup_max=0, verify_max=0, disclaimer_max=0,
    skeleton_ratio=0.80, skeleton_clauses=(2, 3), skeleton_len=(15, 999),   # 同骨架:子句 2-3 且 >= 15 字的句子佔比 > 0.80(任務原訂 15-30,但 xbox_elephant 加上限 30 只剩 42/100,與診斷的 92/100 不符,故不設上限)
    judge_sec=15, chars_per_sec=pace.CHARS_PER_SEC,   # 2026-10-20 規則_文案 v2:第一個判斷句換算秒數 > 15 警告(§1.5;83b:25 → 15,話癆紳 4 支 5–16 秒);字速約每分鐘 330 字
    subj_run=3, subj_win=5, num_run=4,   # 2026-10-20 R\92 §4:subj_win 句內同一句首主語 >= subj_run 次;連續 num_run 句含阿拉伯數字
    react_pat=2,                   # 同一反應句型(我看到這個/組數字、我第一眼)全片出現次數 >= 此值
    repeat_filler=2,               # 同一口頭語全片出現次數 > 此值警告
    # 2026-10-20 規則_文案「留空」:行尾 "pause" 的節奏(只有片子用了 pause 才檢查;秒數以字數 ÷ chars_per_sec 估)
    pause_mid=0.5, pause_per_min=(2, 4),   # >= 0.5 秒的 pause 每分鐘次數範圍
    pause_long=0.8, pause_span=120,        # 連續 pause_span 秒沒有 >= 0.8 秒的停頓
    pause_intro=25, pause_intro_max=1,     # 前 25 秒 >= 0.5 秒的 pause 最多 1 次
    # 2026-10-22 畫面優化 E(PLAN_畫面優化六項):連續幾個鏡頭同類、同一張圖連續幾句 → 警告
    vis_run=3, img_run=2, shock_hint_ratio=3,
    # 2026-10-23 對照 humanizer-zh:套話與拔高(警告)
    cliche=0,
    # 2026-10-26 旁白連貫(PLAN_階段閘門):來源起句、子句過多、一句數字過多、沒接住上一句(全是警告;初值依 wow_stress 被罵「旁白流暢度是災難」與 horror_stalker/re9_leon 對照訂,未校準)
    source_lead_block=1, source_lead_ratio=0.10,   # 同一塊來源起句 > 1 句;全片來源起句比例 > 10%
    clauses_max=4,                                 # 一句子句(,;)數 >= 5
    # 2026-10-29 長子句(PLAN_配音對齊 §2.7):三支片實測配音引擎的多餘停頓(每子句)5–9 字 0.22、10–14 字 0.39、15–19 字 0.60、
    # 20 字以上 0.6–1.0 處 → 子句(以 ,,、;;::。?!?! 切)>= 15 發音單位算長;長子句佔全部子句 > 20% 才警告
    clause_chars=15, clause_long_ratio=0.20,
    nums_max=2,                                    # 一句數字群 >= 3
    chain_run=3,                                   # 同一塊內連續 >= 3 句沒接住上一句
    report_ratio=0.30, report_block=0.50, report_block_min=3,   # 轉述句(來源在句中)全片比例 > 0.30 警告;單一塊(>= report_block_min 句)比例 > 0.50 警告
    # 2026-10-31 口味回歸補洞(channel/taste T01):開場前 open_sents 句裡「只講一次、之後才再出現」的名詞 > open_defer_max 警告
    # (pbz_review v1 = 19、v2 = 10;近 10 支 0~19,只當警告)
    open_sents=9, open_defer_max=17,
    # 2026-11-05 PLAN_全流程優化 P4:配音品管失敗型態回饋 B 段(只在句級警告 sentence_hits,block=False;不進 main 的超標與 --strict 判定)。
    # 依 pipeline/tools/qc_fail_stats.py(1698 句 tts_qc 嘗試紀錄):句內逗號 0/1/2/3 個 → comma_short 曾失敗 1%/47%/62%/72%(>=3 時 72% vs <=2 時 54%,但最近 10 支稿 28% 行命中太吵,11-05 調到 4:命中 1.5%、n=15 曾失敗 comma_short 67%);
    # 短句(CTA「留言告訴我」類)n=5 全部要 >=4 次嘗試、失敗碼 tail_abrupt/speaker/pitch;句尾英文 n=6 平均 3.4 次嘗試(speaker/tail_rise)。
    short_chars=8, comma_warn=4, en_tail=True,   # 去標點後 < short_chars 字;句內逗號(,,)>= comma_warn;句尾(去標點後)是英文字母
)

# 報幕句:像簡報在唸大綱(第一個論點、接下來聽、先講…)
SIGNPOST = re.compile(
    r"^(第[一二三四五六七八九十]+[個步種點項件]?|首先|其次|再來|最後講|接下來|先講|先聽|先把|先看|然後,?是|好,|"
    r"這一派|這件事一樣|整件事分|解法分|請記住|這個數字先放著|原文是這樣|還有一件事)"
    r"|(怎麼說|是這樣|講到這裡|留給你|一條一條攤開)[。.]?$")
# 「不是 A,是 B」「不只是 A,是 B」
NOT_BUT = re.compile(r"(不是|不只是|並不是|並非)[^。?!]{1,18}[,,。]\s*(而是|是|就是|更是)")
# 書面轉接與套話
FORMAL = re.compile(r"意思是|也就是說|換句話說|值得注意|值得一提|總的來說|總而言之|簡單來說|綜上|此外|然而|因此|與此同時|"
                    r"不僅|進行|例如|在這個脈絡|這意味著|不可否認|毫無疑問|眾所周知|聲量|代表性|論點|讓我們")
# 口語語助詞與口頭語(白名單依 output/particle_test 的實測結果維護)
PARTICLE = re.compile(r"[啦吧嘛呀喔咧嘞欸]|呢[,,]|呢$|老實說|說真的|講真的|好啦|對啊|就是說啊|你想想看|我自己是覺得|結果一看|講白了|那個,|(所以|然後)勒")
# 使用者聽審否決或 ChatTTS 唸不出的(2026-10-10,M_seed_402;清單與理由見 CLAUDE.md「文案:去 AI 感」)
BAD_PARTICLE = re.compile(r"[啊阿][。?!?!]?$|耶|蛤|齁|嗯|[說對錯]阿[,,]|[^看][喔哦][,,]")
# 段末總結句、升華句、講解腔(中國大陸去 AI 味指南列為最高頻;來源見 CLAUDE.md)
SUMMARY = re.compile(r"^(這說明|這代表|可以看出|由此可見|到這裡|這就是|說到底|總之|總而言之|所以說|歸根究柢|一句話|簡而言之|事實講到)"
                     r"|真正(關鍵|重要|的問題)|你要先(明白|知道)|請記住|關鍵在於|這背後|值得我們")
# 套話、意義拔高、籠統歸因、客服腔(2026-10-23 對照 humanizer-zh 補)
CLICHE = re.compile(
    r"標誌著|里程碑|新時代|新紀元|彰顯|充分體現|具有重要意義|意義重大|深遠影響"
    r"|堪稱|神作|夢幻|史詩級|震撼|顛覆|完美詮釋"
    r"|業界普遍|專家(認為|指出|表示)|不少(玩家|人)(都)?(覺得|認為)|普遍認為|有人說"
    r"|至關重要|賦能|閉環|一體化|生態系|底層邏輯|核心競爭力|痛點"
    r"|^(隨著|在這個|在當今|在如今)"
    r"|拭目以待|期待更多|值得期待|希望對你|不妨|讓我們一起|未來可期"
    r"|(也許|可能|大概|應該|或許)[，,]?\s*(也許|可能|大概|應該|或許)"
    r"|密切關聯|息息相關|有著千絲萬縷")
SELF_QA = re.compile(r"[??]\s*\S")  # 同一句裡自己問完馬上答
REACT = re.compile(r"我(覺得|看|以為|本來|一開始|第一眼|自己|是真的|還|也|就)")
SEG = re.compile(r"[,,、]")


def spoken_lines(tag):
    out = []
    for n, raw in enumerate((P.ROOT / tag / "script.txt").read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw[0] in "@#" or "|" not in raw:
            continue
        out.append((n, raw.split("|", 1)[1].split(" ;; ")[0].strip()))
    return out


def triple(text):
    """同一句裡三段以上並列且開頭同字(有認,有改,有給時間)。"""
    segs = [s for s in SEG.split(re.sub(r"[。?!?!]", ",", text)) if s]
    return any(segs[i][0] == segs[i + 1][0] == segs[i + 2][0] for i in range(len(segs) - 2))


def parallel(a, b):
    """相鄰兩句對仗:開頭或結尾連續 3 字以上相同(一邊說/另一邊說、像不像那張照片)。"""
    a, b = re.sub(r"\W", "", a), re.sub(r"\W", "", b)
    return len(a) >= 5 and len(b) >= 5 and (a[:3] == b[:3] or a[-3:] == b[-3:])


# ---- v2 新增警告檢查(2026-10-20)----
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?(?:\s?[萬億千百%％倍])?")
PRONOUN = re.compile(r"這個人|這家公司|該公司|同一家|這家|你操作的|這招|這件事|這款|這東西|這位|他們的做法")
WARMUP = re.compile(r"放在一起看|更怪的是|重點來了|先講|我們先看|問題來了|有意思的是|接下來|等等會講|稍後|後面會說|這個我們一會兒")
VERIFY = re.compile(r"我把.*翻過一遍|我查了|我不想把話講得太滿|要先說清楚|我得補一句|我能確定的是|查不到的我會|先說明一下|這裡要說明|根據.{0,12}(統計|報告|整理)")
# 規則檔範例原句,旁白照抄就是沒自己寫(規則_文案 v2 §1.3 範例)
COPIED = re.compile(r"我看了三遍|第一眼以為看錯|我第一眼還以為少打了一個零")
FILLERS = ("講白了", "老實說", "說真的", "好啦")
DISCLAIMER = re.compile(r"未經證實|這是估計|沒有出處|以上是.*的說法|這條沒有|不是虛的|先說清楚|我不選邊|我不站隊|不選邊|你自己判斷|自己判斷就好")   # 2026-10-31 taste T15:加預防針/中立聲明詞
JUDGE = re.compile(r"我覺得|根本|太.{0,3}了|有夠|不該|離譜|扯|難看|可惜|沒道理")
# 判決腔:對玩家說法宣判(2_文案 §1.1「不當裁判」);判斷留給並排事實,擋 = 0
VERDICT = re.compile(r"(這|那|此)(一)?(條|句|點|派|說法)(不|算|就|才|並不|根本不)?(成立|站得住|站不住|說對|說錯|說不過去|打臉)|不成立|說對一半|站不住腳?|說不過去|打臉|冤枉")
SENT_SPLIT = re.compile(r"[^。?!？！]+")
CLAUSE_SPLIT = re.compile(r"[,，]")
WEAK_WORDS = set("沒有 可以 已經 知道 覺得 出來 起來 這個 那個 什麼 我們 你們 他們 自己 因為 所以 但是 如果 就是 還是 不是 一個 一下 開始 出現 成為 需要 看到 發現 表示 進行 使用 真的 可能 其實 現在 時候".split())


MULT = re.compile(r"\d[\d,]*(?:\.\d+)?\s*倍|[一二三四五六七八九十兩半]+倍")   # 倍數:只提示核對,不判對錯
REACT_PATS = (("我看到這(個|組)數字", re.compile(r"我看到這(個|組)數字")), ("我第一眼", re.compile(r"我第一眼")))


def lead_subjects(pseg, sents):
    """每句的句首主語:全片出現過的人名/機構/專名(nr/nt/nz/ns/eng,2-4 字)中,該句開頭吻合的最長者;沒有則 None。"""
    names = {w.word for _, t in sents for w in pseg.cut(t) if w.flag in ("nr", "nt", "nz", "ns", "eng") and 2 <= len(w.word) <= 4}
    out = []
    for _, t in sents:
        m = [n for n in names if t.startswith(n)]
        out.append(max(m, key=len) if m else None)
    return out


def subject_runs(pseg, sents):
    """任一連續 subj_win 句內,同一句首主語出現 >= subj_run 次(R\92 原訂 3 句內 3 次只抓得到連續三句,抓不到 cod_tax_rw 132-152 隔句再起手,故窗放寬為 5 句)。"""
    sub = lead_subjects(pseg, sents)
    hit, seen = [], set()
    for i in range(len(sub)):
        win = sub[i:i + T["subj_win"]]
        for s in set(x for x in win if x):
            idx = [i + j for j, x in enumerate(win) if x == s]
            if len(idx) >= T["subj_run"] and (s, idx[0]) not in seen:
                seen.add((s, idx[0]))
                hit.append((sents[idx[0]][0], f"「{s}」在 {T['subj_win']} 句內當句首主語 {len(idx)} 次(L{','.join(str(sents[k][0]) for k in idx)})"))
    return hit


def number_runs(sents):
    hit, run = [], []
    for ln, t in sents + [(0, "")]:
        if re.search(r"\d", t):
            run.append((ln, t))
            continue
        if len(run) >= T["num_run"]:
            hit.append((run[0][0], f"連續 {len(run)} 句含數字(L{run[0][0]}–{run[-1][0]}):{run[0][1][:24]}"))
        run = []
    return hit


_PSEG = []   # _pseg() 的單例(各檢查共用同一份斷詞記憶)


def _pseg():
    """jieba 詞性斷詞;沒裝就回 None(相關檢查退回字數規則)。"""
    if _PSEG:
        return _PSEG[0]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import jieba
            import jieba.posseg as pseg
        jieba.setLogLevel(60)
        _PSEG.append(_MemoPseg(pseg))
        return _PSEG[0]
    except Exception:
        return None


class _MemoPseg:
    """jieba.posseg 包一層記憶:同一句在 keywords / lead_subjects / _chain_words 會各斷一次(承接檢查每句還斷兩次),
    整支片 lint 有 7 成時間在重複斷詞;cut 回傳 list(可重複疊代),結果與直接呼叫相同。"""

    def __init__(self, mod):
        self._mod, self._memo = mod, {}

    def cut(self, text):
        r = self._memo.get(text)
        if r is None:
            r = self._memo[text] = list(self._mod.cut(text))
        return r


def clen(t):
    return len(re.sub(r"\W", "", t))


def sentences(lines):
    return [(ln, x.strip()) for ln, t in lines for x in SENT_SPLIT.findall(t) if x.strip()]


def keywords(pseg, text):
    """名詞/動詞/英文關鍵詞集合(2 字以上、排除弱詞)。"""
    return {w.word for w in pseg.cut(text) if len(w.word) >= 2 and w.word not in WEAK_WORDS and w.flag[:1] in ("n", "v", "e") and not re.match(r"^\W+$", w.word)}


def repeated_numbers(lines):
    pos = {}
    for ln, t in lines:
        for m in NUM.finditer(t):
            k = re.sub(r"\s", "", m.group(0)).rstrip(",")
            if re.fullmatch(r"\d{1,2}", k) or (re.fullmatch(r"\d{4}", k) and 1990 <= int(k) <= 2035):   # 無單位的 1-2 位數(月、日、排名)與年份不算
                continue
            pos.setdefault(k, []).append(ln)
    return [(v[0], f"{k} 出現 {len(v)} 次(L{','.join(map(str, v[:6]))})") for k, v in pos.items() if len(v) >= T["num_repeat"]]


def repeated_pairs(pseg, sents):
    if pseg is None:
        return []
    kws = [keywords(pseg, t) for _, t in sents]
    out = []
    for i in range(len(sents)):
        for j in range(i + 2, len(sents)):   # 非相鄰
            a, b = kws[i], kws[j]
            lo = min(len(a), len(b))
            if lo < T["pair_min_kw"]:
                continue
            inter = len(a & b)
            if inter >= T["pair_min_hit"] and inter / lo >= T["pair_overlap"]:
                out.append((sents[i][0], f"L{sents[i][0]} {sents[i][1][:22]} / L{sents[j][0]} {sents[j][1][:22]}"))
    return out


def pronoun_hits(sents):
    out = [(ln, t) for ln, t in sents if PRONOUN.search(t)]
    run = []
    for ln, t in sents + [(0, "x")]:
        if t[0] in "他她它":
            run.append((ln, t))
            continue
        if len(run) >= T["pronoun_run"]:
            out.append((run[0][0], f"句首他/她/它連續 {len(run)} 句:" + " / ".join(x[:12] for _, x in run)))
        run = []
    return out


def warmup_hits(pseg, sents):
    """暖場與單句預告;同一句內後面已接上事實名詞者不算。"""
    out = []
    for ln, t in sents:
        for m in WARMUP.finditer(t):
            rest = re.sub(r"^\W+|\W+$", "", t[m.end():])
            if pseg is not None:
                has_fact = bool(re.search(r"\d", rest)) or any(len(w.word) >= 2 and w.flag[:1] in ("n", "e") for w in pseg.cut(rest))
            else:
                has_fact = len(rest) >= 4
            if not has_fact:
                out.append((ln, t))
                break
    return out


def skeleton(sents):
    lo, hi = T["skeleton_clauses"]
    llo, lhi = T["skeleton_len"]
    same = sum(1 for _, t in sents if lo <= len([c for c in CLAUSE_SPLIT.split(t) if c.strip()]) <= hi and llo <= clen(t) <= lhi)
    return same, len(sents)


def first_judgment(sents):
    """回傳 (第幾句, 換算秒數);全片沒有判斷詞回 (None, None)。"""
    cum = 0
    for i, (_, t) in enumerate(sents, 1):
        if JUDGE.search(t):
            return i, cum / T["chars_per_sec"]
        cum += clen(t)
    return None, None


def v2_warnings(lines):
    """回傳 [(名稱, 命中 list[(行, 文字)], 是否超標)];命中為空的不回。"""
    pseg = _pseg()
    sents = sentences(lines)
    w = []

    def add(name, hit, over=None):
        if hit:
            w.append((name, hit, len(hit) > 0 if over is None else over))
    add("同一件事講兩次(數字重複)", repeated_numbers(lines))
    add("同一件事講兩次(非相鄰兩句關鍵詞重疊)", repeated_pairs(pseg, sents))
    ph = pronoun_hits(sents)
    add("代稱", ph, len(ph) > T["pronoun_max"])
    wh = warmup_hits(pseg, sents)
    add("暖場與單句預告", wh, len(wh) > T["warmup_max"])
    vh = [(ln, t) for ln, t in sents if VERIFY.search(t)]
    add("交代查證與打預防針", vh, len(vh) > T["verify_max"])
    dh = [(ln, t) for ln, t in sents if DISCLAIMER.search(t)]
    add("免責唸出口(免責只放畫面)", dh, len(dh) > T["disclaimer_max"])
    ch = [(ln, t) for ln, t in sents if COPIED.search(t)]
    add("照抄規則範例句", ch)
    ftxt = chr(10).join(t for _, t in sents)
    fh = [(0, f"{k} 出現 {ftxt.count(k)} 次(門檻 <= {T['repeat_filler']})") for k in FILLERS if ftxt.count(k) > T["repeat_filler"]]
    add("同一口頭語重複", fh)
    same, tot = skeleton(sents)
    if tot and same / tot > T["skeleton_ratio"]:
        w.append(("同骨架比例", [(0, f"子句 2-3 個且 15 字以上的句子 {same}/{tot}({same / tot:.0%},門檻 <= {T['skeleton_ratio']:.0%})")], True))
    # 2026-10-20 R\92 §4 新增(皆警告)
    if pseg:
        add("同一句首主語(5 句內 >= 3 次)", subject_runs(pseg, sents))
    add("連續數字句(>= 4 句)", number_runs(sents))
    add("倍數核對(請對原始數字確認,不判對錯)", [(ln, t[:60]) for ln, t in sents if MULT.search(t)])
    for nm, pat in REACT_PATS:
        rh = [(ln, t) for ln, t in sents if pat.search(t)]
        if len(rh) >= T["react_pat"]:
            add(f"同一反應句型「{nm}」", rh)
    idx, sec = first_judgment(sents)
    if idx is None:
        w.append(("第一個判斷句位置", [(0, "全片沒有判斷詞")], True))
    elif sec > T["judge_sec"]:
        w.append(("第一個判斷句位置", [(sents[idx - 1][0], f"第 {idx} 句約 {sec:.0f} 秒才出現(門檻 <= {T['judge_sec']} 秒):{sents[idx - 1][1][:30]}")], True))
    return w


# ---- 旁白連貫警告(2026-10-26,PLAN_階段閘門;全是警告)----
_SRC = (r"玩家|網友|巴哈|論壇|PTT|Steam|留言|評論|外媒|媒體|記者|官方|公告|暴雪|紀錄|報告|報導|心得|聯訪|訪談|新聞|製作團隊|開發團隊|開發者|團隊|"
        r"Tavern|MeinMMO|TechRadar|Wowhead|Reddit|推特|Twitter|粉專|頻道|實況主|影片")
_SRC_VERB = r"說|寫|問|提到|回報|指出|轉述|留言|公告|報導|報的"
SOURCE_VERB = re.compile(rf"(?:{_SRC})[^,，。;；]{{0,8}}?(?:{_SRC_VERB})")
SOURCE_HEAD = re.compile(
    r"^(?:也)?(?:有玩家|有人|同一串|同一篇|另一則|另一個玩家|另一篇|底下|留言區|論壇上|巴哈|PTT|Steam 評論|外媒|媒體|記者|官方公告|官方新聞|製作團隊|根據|據)"
    r"|^[^,，。;；]{1,8}的(?:留言區|報告影片底下)|^[^,，。;；]{1,8}的[^,，。;；]{0,6}影片底下")
CLAUSE_SPLIT2 = re.compile(r"[,，;；]")
CLAUSE_SPLIT3 = re.compile(r"[,，、;；:：。?!？！]")   # 長子句用:配音時會停的標點都算子句界
_UNIT_RE = re.compile(r"[A-Za-z]+|[0-9]|[一-鿿]")      # 發音單位(同 tts_pause.units:中文一字、英文一詞、數字一位)


def clause_cut(c):
    """長子句的建議切點「前|後」:jieba 斷詞後最接近中點(以字元位置計)的詞邊界;沒有 jieba 或沒有內部詞邊界回 None。"""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import jieba
        jieba.setLogLevel(60)
    except Exception:
        return None
    pos, ends = 0, []
    for tok in jieba.cut(c):
        pos += len(tok)
        if pos < len(c):
            ends.append(pos)
    if not ends:
        return None
    k = min(ends, key=lambda e: abs(e - len(c) / 2))
    return c[:k] + "|" + c[k:]
_UNITS = ("分鐘|公里|公尺|小時|美金|美元|GB|MB|FPS|點|號|日|月|年|分|秒|個|人|次|萬|億|元|倍|成|％|%|天|週|塊|款|支|場|隻|位|名|層|級|代|集|關|歲|份|家|台|顆|張|篇|則|樓|G")
_NCH = "零一二兩三四五六七八九十百千萬億"
NUM_GROUP = re.compile(rf"(?:\d[\d,]*(?:\.\d+)?(?![\d》」』])\s?(?:{_UNITS})?|[{_NCH}]+?(?:{_UNITS}))+")
NUM_EXCL = {"一樣", "一起", "一次", "一下", "一點", "一直", "一定", "一些", "一邊", "一堆", "十分", "萬一", "一旦", "一半", "一句"}
CHAIN_HEAD = re.compile(
    r"^(?:但|可是|不過|所以|結果|等於|也就是|那|這|他|她|它|他們|同一|另一|反而|偏偏|更|還|也|而|因為|後來|接著|然後|先|再|最後|等到|到了|直到|換句話|這樣|這個|那個|這些|那些|"
    r"這件|那件|這句|這場|這次|那次|這筆|同樣|一樣|其中|裡面|之後|之前|當時|那時|這時|現在|當年|隔年|同年|第二|第三|你|我)")
# 句首 8 字內回指上一句的代詞片語(看到這句我愣了一下、做了這件事):也算接住
CHAIN_ANAPHOR = re.compile(r"^.{0,4}?(?:這句|這件事|這種|這套|這點|這份|這段|這招|這位|這款|這些|那些|這個|那個)")
# 無 jieba 時的功能詞二字組停用表(玩家、遊戲太泛,不算承接)
CHAIN_STOP = set("這個 那個 可是 就是 但是 因為 所以 我們 你們 他們 的話 什麼 這樣 那樣 這些 那些 還是 就算 如果 已經 沒有 不是 也是 可以 這場 這次 那次 一個 一樣 一起 現在 時候 玩家 遊戲".split())


# 轉述句 REPORT_RATIO:來源名詞與轉述動詞在句中相距 <= 8 字(來源起句抓不到「官網寫、標題寫、Kotaku 也寫了」這種來源在句中的轉述)
_REP_SRC = (r"官網|首頁|網站|新聞稿|公告|標題|內文|那篇|這篇|報導|媒體|記者|外媒|論壇|巴哈|PTT|留言|網友|玩家|總監|製作人|製作團隊|官方|"
            r"Kotaku|IGN|CBC|Sony|Steam|Reddit|Twitter|Eurogamer|GameSpot|Polygon|PC Gamer|Wowhead|Tavern|MeinMMO|TechRadar|Dexerto|Bloomberg|Reuters|"
            r"微軟|任天堂|索尼|卡普空|育碧|華納|暴雪|公共廣播|公司|X 上|X上|"
            r"網址|頁面|計畫|介紹|聲明|貼文|文章|名單|第一句|第一段|下一句|原話|影片|報告|資料|文件|簡介|條款|訪談|採訪|評測|心得|評論|紀錄|說法|代表作品|版面")
_REP_VERB = r"寫著|寫的是|寫了|寫|說|講|提到|指出|回報|報導|回(?![來去到合家頭歸收升復購])|公布|承認|宣布|轉述|留言說"
REPORT_SENT = re.compile(rf"(?:{_REP_SRC})[^。?!？！]{{0,8}}?(?:{_REP_VERB})|(?:{_REP_VERB})[^。?!？！]{{0,8}}?(?:{_REP_SRC})")   # 來源與動詞不分先後(寫在官網)
REPORT_EXCL = re.compile(r"說公道話|你說|我說|也就是說|說真的|說白了|換句話說|講真的|講白了|老實說|簡單來說|說到底|說起來|說實話|不用說|別說|再說|來說|而言|寫作|說明|說服|說故事|小說|傳說|劇本")


def report_sentence(t):
    return bool(REPORT_SENT.search(REPORT_EXCL.sub("□", t)))


def block_starts(tag):
    """script.txt 裡「# 」段落標題的行號(升冪);旁白以此切塊。"""
    return [n for n, raw in enumerate((P.ROOT / tag / "script.txt").read_text(encoding="utf-8").splitlines(), 1) if raw.startswith("#")]


def source_lead(t):
    t = t.lstrip("「『《(( ")
    return bool(SOURCE_HEAD.search(t) or SOURCE_VERB.search(t[:14]))


NUM_ONE_GENERIC = re.compile(r"一(?:個|款|天|次|場|位|名|張|篇|則|家|台|顆|支|隻|份|句|下|塊|層|級|代|集|關|種|批|組|套|招|步|格|條|段|回|輪|波|類|件|項|部|作)")   # 「一」+一般量詞 = 不定指,不算數字(一+時間/金錢單位照算)


def num_groups(t):
    out = []
    for m in NUM_GROUP.finditer(t):
        g = m.group(0).strip()
        if g == "一點" and t[m.end():m.end() + 1] and t[m.end()] in "整半多到鐘":   # 一點整/一點半 是鐘點,照算;一點都不 不算
            out.append(g)
        elif g not in NUM_EXCL and not NUM_ONE_GENERIC.fullmatch(g):
            out.append(g)
    return out


def _chain_words(pseg, t):
    """一句的「承接用實詞」集合:有 jieba 取 n*/v*/eng 2 字以上;沒有就取 CJK 二字組與 >= 2 字母的英文詞。兩者都排除功能詞停用表。"""
    if pseg is not None:
        ws = {w.word for w in pseg.cut(t) if len(w.word) >= 2 and w.flag[:1] in ("n", "v", "e") and not re.match(r"^\W+$", w.word)}
    else:
        ws = {r[i:i + 2] for r in re.findall(r"[一-鿿]+", t) for i in range(len(r) - 1)}
        ws |= {w.lower() for w in re.findall(r"[A-Za-z]{2,}", t)}
    return ws - CHAIN_STOP


def _chain_caught(pseg, prev, t):
    t0 = t.lstrip("「『《(( ")
    return bool(CHAIN_HEAD.search(t0) or CHAIN_ANAPHOR.search(t0)) or bool(_chain_words(pseg, prev) & _chain_words(pseg, t))


def fluency_warnings(lines, starts=(), stats=None):
    """旁白連貫四組警告(來源起句、子句過多、一句數字過多、沒接住上一句);格式同 v2_warnings。
    starts = 段落標題行號(block_starts),沒給就整片當一塊;stats 給 dict 時填入 src(命中,總句)、chain(接住,判斷句數)。"""
    import bisect
    pseg = _pseg()
    sents = sentences(lines)
    blk = lambda ln: bisect.bisect_right(list(starts), ln)
    blocks = []   # [[(行, 句), ...], ...]
    last = None
    for ln, t in sents:
        b = blk(ln)
        if b != last:
            blocks.append([])
            last = b
        blocks[-1].append((ln, t))
    w = []
    # 1. 來源起句
    total = hits = 0
    for bl in blocks:
        h = [(ln, t) for ln, t in bl if source_lead(t)]
        total += len(bl)
        hits += len(h)
        if len(h) > T["source_lead_block"]:
            w.append(("來源起句(同一塊 > %d 句,SOURCE_LEAD)" % T["source_lead_block"], [(ln, t) for ln, t in h], True))
    if total and hits / total > T["source_lead_ratio"]:
        w.append(("來源起句比例(SOURCE_LEAD)", [(0, f"全片 {hits}/{total}({hits / total:.0%},門檻 <= {T['source_lead_ratio']:.0%})")], True))
    # 2. 子句過多
    ch = [(ln, f"{len([c for c in CLAUSE_SPLIT2.split(t) if c.strip()])} 子句:{t}") for ln, t in sents if len([c for c in CLAUSE_SPLIT2.split(t) if c.strip()]) > T["clauses_max"]]
    if ch:
        w.append(("子句過多(>= %d 個,CLAUSES)" % (T["clauses_max"] + 1), ch, True))
    # 2b. 長子句
    cl = [(ln, c.strip()) for ln, t in sents for c in CLAUSE_SPLIT3.split(t) if _UNIT_RE.search(c)]
    lh = [(ln, c) for ln, c in cl if len(_UNIT_RE.findall(c)) >= T["clause_chars"]]
    if cl and len(lh) / len(cl) > T["clause_long_ratio"]:
        w.append(("長子句(>= %d 字的子句佔 %d/%d = %.1f%%,門檻 <= %.0f%%,CLAUSE_LONG)" % (
            T["clause_chars"], len(lh), len(cl), 100 * len(lh) / len(cl), 100 * T["clause_long_ratio"]),
            [(ln, f"{len(_UNIT_RE.findall(c))} 字:{c}" + (f" → 建議切在 {cut}" if (cut := clause_cut(c)) else "")) for ln, c in lh],
            True))
    # 3. 一句數字過多
    nh = [(ln, f"{len(g)} 群({'/'.join(g)}):{t}") for ln, t in sents for g in [num_groups(t)] if len(g) > T["nums_max"]]
    if nh:
        w.append(("一句數字過多(>= %d 群,NUMS)" % (T["nums_max"] + 1), nh, True))
    # 4. 沒接住上一句
    judged = caught = 0
    run_hits = []
    for bl in blocks:
        run = []
        for i in range(1, len(bl) + 1):
            ok = True
            if i < len(bl):
                ok = _chain_caught(pseg, bl[i - 1][1], bl[i][1])
                judged += 1
                caught += ok
            if not ok:
                run.append(bl[i])
                continue
            if len(run) >= T["chain_run"]:
                run_hits.append((run[0][0], f"連續 {len(run)} 句沒接住上一句(L{run[0][0]}–{run[-1][0]}):{run[0][1][:24]}"))
            run = []
    if run_hits:
        w.append(("沒接住上一句(連續 >= %d 句,CHAIN_BREAK)" % T["chain_run"], run_hits, True))
    # 5. 轉述句比例(REPORT_RATIO)
    rep_n = rep_tot = 0
    for bl in blocks:
        h = [(ln, t) for ln, t in bl if report_sentence(t)]
        rep_n += len(h)
        rep_tot += len(bl)
        if len(bl) >= T["report_block_min"] and len(h) / len(bl) > T["report_block"]:
            w.append((f"轉述句佔單一塊過半(> {T['report_block']:.0%},REPORT_RATIO)", [(ln, t) for ln, t in h], True))
    if rep_tot and rep_n / rep_tot > T["report_ratio"]:
        w.append(("轉述句比例(REPORT_RATIO)", [(0, f"全片 {rep_n}/{rep_tot}({rep_n / rep_tot:.0%},門檻 <= {T['report_ratio']:.0%})")], True))
    if stats is not None:
        stats.update(src=(hits, total), chain=(caught, judged), report=(rep_n, rep_tot), clause_long=(len(lh), len(cl)))
    return w


def pause_lines(tag):
    """[(行號, 估計句末秒數, pause 或 None)];行尾 json 解析不了的當作沒有 pause(格式錯誤由 script_txt2json 報)。"""
    out, t = [], 0.0
    for n, raw in enumerate((P.ROOT / tag / "script.txt").read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw[0] in "@#" or "|" not in raw:
            continue
        s = raw.split("|", 1)[1]
        tail = s.rpartition(" ;; ")[2] if " ;; " in s else ""   # 同 script_txt2json.split_extra:只認最後一段
        t += clen(s.split(" ;; ")[0]) / T["chars_per_sec"]
        try:
            p = json.loads(tail).get("pause") if tail.strip() else None
        except (ValueError, AttributeError):
            p = None
        out.append((n, t, float(p) if isinstance(p, (int, float)) else None))
    return out


def pause_warnings(tag):
    """行尾 pause 的節奏警告(格式同 v2_warnings);全片沒用 pause 回 []。"""
    pl = pause_lines(tag)
    if not any(p is not None for _, _, p in pl):
        return []
    total = pl[-1][1]
    w = []
    mid = [(n, s) for n, s, p in pl if p is not None and p >= T["pause_mid"]]
    lo, hi = T["pause_per_min"]
    rate = len(mid) / (total / 60) if total else 0.0
    if not lo <= rate <= hi:
        w.append((f"pause >= {T['pause_mid']} 秒的頻率", [(0, f"每分鐘 {rate:.1f} 次({len(mid)} 次 / 約 {total / 60:.1f} 分,建議 {lo}–{hi})")], True))
    marks = [(0, 0.0)] + [(n, s) for n, s, p in pl if p is not None and p >= T["pause_long"]] + [(pl[-1][0], total)]
    long_ = [(b[0], f"約 {a[1]:.0f}–{b[1]:.0f} 秒連續 {b[1] - a[1]:.0f} 秒沒有 >= {T['pause_long']} 秒的停頓")
             for a, b in zip(marks, marks[1:]) if b[1] - a[1] > T["pause_span"]]
    if long_:
        w.append((f"連續 {T['pause_span']} 秒無長停頓", long_, True))
    intro = [(n, f"約 {s:.0f} 秒") for n, s in mid if s <= T["pause_intro"]]
    if len(intro) > T["pause_intro_max"]:
        w.append((f"前 {T['pause_intro']} 秒 pause 過多(<= {T['pause_intro_max']})", intro, True))
    return w


VIS_KINDS = dict(anim="動畫", shots="片段", quote="引言卡", compare="對比卡", img="圖", v="片段", card="卡片")


def visual_key(ln):
    """script.json 一句的畫面 → (類別, 鏡頭鍵);鍵相同的相鄰句算同一個鏡頭(簡化自 build.visual_key,優先序 anim > shots > quote > compare > img > v > card)。
    截圖與閱讀卡在 script 欄位上都是 img(layout.json 沒有可靠的 mode 欄位)→ 併為「圖」;card 只是疊在鏡頭上的字卡,沒有其他畫面時才自成一類。"""
    a = ln.get("anim")
    if isinstance(a, dict):   # 同一組動畫的各 step 是同一個連續鏡頭
        return "動畫", "anim:" + json.dumps({k: v for k, v in a.items() if k != "step"}, sort_keys=True, ensure_ascii=False)
    for k in ("shots", "quote", "compare"):
        if ln.get(k):
            return VIS_KINDS[k], k + ":" + json.dumps([ln[k], ln.get("img")], sort_keys=True, ensure_ascii=False)
    if ln.get("img"):
        return "圖", "img:" + str(ln["img"])
    if ln.get("v"):
        return "片段", "v:" + str(ln["v"])
    if ln.get("card"):
        return "卡片", "card:" + json.dumps(ln["card"], sort_keys=True, ensure_ascii=False)
    return "其他", "none"


def visual_warnings(vlines):
    """畫面單調警告(不擋)。vlines = [(行號, script.json 句 dict)];格式同 v2_warnings。
    1. 連續 >= vis_run 個鏡頭同類(片段類不報,評論片連用片段正常;「其他」不報)
    2. 同一張圖連用 >= img_run 句(build 另有 check_image_runs 擋 > IMG_MAX_UNITS 句,這裡提早提醒)
    3. 單系列 bars / cols 沒寫 shock 且最大值 >= 次大值 shock_hint_ratio 倍 → 建議加 "shock":true(只提示)"""
    shots = []   # [類別, 鍵, 首行號, 末行號, 句數]
    for ln, d in vlines:
        kind, key = visual_key(d)
        if shots and shots[-1][1] == key:
            shots[-1][3] = ln
            shots[-1][4] += 1
        else:
            shots.append([kind, key, ln, ln, 1])
    w, hit = [], []
    i = 0
    while i < len(shots):
        j = i
        while j + 1 < len(shots) and shots[j + 1][0] == shots[i][0]:
            j += 1
        if j - i + 1 >= T["vis_run"] and shots[i][0] not in ("片段", "其他"):
            hit.append((shots[i][2], f"至 L{shots[j][3]} 連續 {j - i + 1} 個鏡頭都是「{shots[i][0]}」"))
        i = j + 1
    if hit:
        w.append((f"連續 {T['vis_run']} 個鏡頭同類畫面", hit, True))
    hit = [(a, f"至 L{b} 同一張圖「{key[4:]}」連用 {n} 句") for kind, key, a, b, n in shots if kind == "圖" and n >= T["img_run"]]
    if hit:
        w.append((f"同一張圖連用 {T['img_run']} 句以上", hit, True))
    hit, seen = [], set()
    for ln, d in vlines:       # 3. 單系列 bars / cols 最大項 >= 次大項 SHOCK_HINT_RATIO 倍卻沒開軸暴衝(建議級;同一組動畫只提示一次)
        an = d.get("anim")
        if not isinstance(an, dict) or an.get("type") not in ("bars", "cols") or not (an.get("shock") is None or an.get("shock") is False):
            continue
        key = visual_key(d)[1]
        if key in seen or an.get("series") or an.get("stack") or "ref" in an:
            continue
        seen.add(key)
        its = [x for g in an["groups"] for x in g.get("bars", [])] if isinstance(an.get("groups"), list) else an.get("items")
        vals = [x[1] for x in its if isinstance(x, list) and len(x) > 1] if isinstance(its, list) else []
        if len(vals) < 2 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 for v in vals):
            continue
        top, nxt = sorted(vals, reverse=True)[:2]
        if nxt > 0 and top >= T["shock_hint_ratio"] * nxt:
            hit.append((ln, f"{an['type']}「{str(an.get('title', ''))[:12]}」最大值 {top:g} >= 次大值 {nxt:g} 的 {T['shock_hint_ratio']} 倍,可加 \"shock\":true"))
    if hit:
        w.append((f"單系列長條 / 直條最大值遠大於次大值(建議,不擋)", hit, True))
    return w


def _may_tilt(d):
    """這句的圖片鏡頭可能傾斜嗎:明寫 fx 照 fx;沒寫時 photo 組(layout.json kind=photo,或沒有 .boxes.json 的圖)會輪到 tilt。"""
    if d.get("anim") or d.get("quote") or d.get("compare") or d.get("shots") or not d.get("img"):
        return False
    if d.get("fx"):
        return str(d["fx"]).startswith("tilt")
    img = P.ROOT / "images" / str(d["img"])
    try:
        kind = json.loads(img.with_suffix(".layout.json").read_text(encoding="utf-8")).get("kind")
    except (OSError, ValueError):
        kind = None
    return kind == "photo" or (kind is None and not img.with_suffix(".boxes.json").exists())


def kit_errors(vlines):
    """動態小件(kit)檢查,一律算超標(PLAN_畫面優化六項 F):名稱存在、必要欄位、同句 <= 2、punch 每句 <= 1、
    同一鏡頭 <= 4(鏡頭用 visual_key 合併相鄰句)、spotlight 不可用在 photo 組 tilt 鏡頭。回傳 [(行號, 訊息)]。"""
    import kit as KIT
    hit, shots = [], []   # shots: [鍵, [(行號, items)], 可能傾斜]
    for ln, d in vlines:
        items = d.get("kit")
        if items:
            hit += [(ln, e) for e in KIT.line_errors(items)]
        key = visual_key(d)[1]
        if shots and shots[-1][0] == key:
            shots[-1][1].append((ln, items or []))
            shots[-1][2] = shots[-1][2] or _may_tilt(d)
        else:
            shots.append([key, [(ln, items or [])], _may_tilt(d)])
    for _, lst, tilt in shots:
        items = [it for _, its in lst if isinstance(its, list) for it in its]
        if items:
            hit += [(lst[0][0], f"至 L{lst[-1][0]} {e}") for e in KIT.shot_errors(items, tilt)]
    return hit


def visual_lines(tag, lines):
    """讀 <tag>/script.json 的逐句畫面欄位,對上 script.txt 的行號;沒有 script.json 或句數對不上回 []。"""
    f = P.ROOT / tag / "script.json"
    if not f.exists():
        return []
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        js = [ln for sec in d["sections"] for ln in sec["lines"]]
    except (ValueError, KeyError, TypeError):
        return []
    if len(js) != len(lines):
        return []   # script.json 過期(script.txt 改了還沒轉檔):行號對不上就不查
    return [(n, j) for (n, _), j in zip(lines, js)]


# ---- 口味回歸補洞(2026-10-31,channel/taste T01/T04/T08/T14;T14 硬擋,其餘警告;回傳格式同 v2_warnings)----
def opening_load(lines, pseg=None):
    """T01:開場前 T.open_sents 句裡出現一次、到後面塊才再出現的名詞(= 開場塞了留給後面塊解釋的論點);超過 T.open_defer_max 回命中。"""
    pseg = pseg or _pseg()
    sents = sentences(lines)
    n = T["open_sents"]
    if not pseg or len(sents) <= n:
        return []
    cnt = {}
    for _, t in sents[:n]:
        for w in keywords(pseg, t):
            cnt[w] = cnt.get(w, 0) + 1
    rest = "".join(t for _, t in sents[n:])
    deferred = sorted(w for w, c in cnt.items() if c == 1 and w in rest)
    if len(deferred) <= T["open_defer_max"]:
        return []
    return [(sents[0][0], f"開場前 {n} 句有 {len(deferred)} 個名詞只講一次、後面才再出現(門檻 <= {T['open_defer_max']},OPEN_LOAD):" + "/".join(deferred[:10]))]


PRON_HE = re.compile(r"(?<!其)[她他](?![們人方山鄉])")
PERSON_CUE = re.compile(r"[A-Za-z]{3,}|·|總監|製作人|導演|創辦人|執行長|主播|評論者|作者|記者|設計師|編劇|演員|玩家|網友|老闆|社長|總裁|主管|編輯|實況主|創作者|發言人|CEO")


def pronoun_before_name(lines, names=()):
    """T04:第一個「她/他」之前(同句前段或前 3 句內)沒有人名或人物詞(英文專名、作者/總監…、spec names)-> 命中;只看第一個。"""
    sents = sentences(lines)
    cue = lambda x: bool(PERSON_CUE.search(x)) or any(nm and nm in x for nm in names)
    for i, (ln, t) in enumerate(sents):
        m = PRON_HE.search(t)
        if m:
            ctx = t[:m.start()] + "".join(x for _, x in sents[max(0, i - 3):i])
            return [] if cue(ctx) else [(ln, f"「{m.group(0)}」出現時前 3 句沒有人名,觀眾還不知道是誰(PRONOUN_FIRST):{t[:40]}")]
    return []


PRICE_USD = re.compile(r"(?:US)?\$\s?\d|\d\s*(?:美金|美元)|美金|美元|USD", re.I)
PRICE_TWD = re.compile(locale_cfg.get("local_currency_regex"), re.I)   # 本地幣辨識,studio.json locale 可改(預設台幣)
PRICE_EXEMPT = re.compile(r"[億萬]\s?(?:美金|美元)|價值|營收|財報|營業|收入|銷售額|市值|估值|罰款|賠償|投資|募資|資金|獲利|利潤|虧損|成本|預算|薪資|年薪|薪水|身價|資產|股價|裁員|收購|併購|和解|訴訟|開發費|製作費|籌")   # 財報/企業金額維持美金(price-twd-primary)


def price_twd_missing(lines, vlines=()):
    """T08:句子或畫面欄位有美金價格,同句與同句畫面都沒有台幣(NT$/台幣)-> 命中;財報營收類(PRICE_EXEMPT)不算。vlines = visual_lines() 的 [(行, json)]。"""
    vmap = {n: json.dumps({k: v for k, v in j.items() if k != "text"}, ensure_ascii=False) for n, j in vlines}
    out = []
    for ln, t in lines:
        blob = t + " " + vmap.get(ln, "")
        if PRICE_USD.search(blob) and not PRICE_TWD.search(blob) and not PRICE_EXEMPT.search(t):
            out.append((ln, f"美金價格沒有{locale_cfg.get('local_currency_name')}(PRICE_TWD,2_文案「價格」):{t[:44]}"))
    return out


PLAY_CLAIM = re.compile(r"我(?:已經|還|也|又|先|整整|總共|一共|前後)?(?:玩了|(?:玩過|打過)(?!最)|通關|打通|通了|刷了|肝了|試玩了|實際玩|親自玩|親手玩)|我打了(?!電話|招呼|個)|我(?:看|玩|打)了\s*[0-9一二三四五六七八九十兩半幾百]+\s*(?:個)?(?:小時|分鐘|章|場|關)(?!的?(?:預告|直播|影片|實測|測試|試玩|評測|實況|留言|資料|評論|報導))")
NOT_PLAYED = re.compile(r"(?:使用者|我|他)?沒(?:有)?(?:玩過|打過|看過)|未(?:玩過|看過)")


def not_played(tag):
    """T14:projects/<tag>/brief.json 的 played 為 false,或 handoff.md 寫了沒玩過/沒看過 -> True。"""
    pd = P.PROJECTS / tag
    try:
        b = json.loads((pd / "brief.json").read_text(encoding="utf-8"))
        if b.get("played") is False:
            return True
    except (OSError, ValueError, AttributeError):
        pass
    try:
        return bool(NOT_PLAYED.search((pd / "handoff.md").read_text(encoding="utf-8")))
    except OSError:
        return False


def played_claims(lines, played=False):
    """T14:使用者沒玩過(played=False 以外都不查)而旁白寫第一人稱遊玩經歷(我玩了/我通關/我打了 N 小時…)-> 命中(硬擋)。"""
    if played:
        return []
    return [(ln, f"使用者沒玩過卻寫第一人稱遊玩經歷(PLAYED_CLAIM,4_交付發片「第一人稱經驗框」):{t[:44]}") for ln, t in lines if PLAY_CLAIM.search(t)]


def taste_warnings(lines, tag):
    """T01/T04/T08 警告三項;格式同 v2_warnings。"""
    w = []
    for name, hit in (("開場塞太多留給後面塊的名詞(OPEN_LOAD)", opening_load(lines)),
                      ("「她/他」先於人名(PRONOUN_FIRST)", pronoun_before_name(lines, spec_names(tag))),
                      ("美金價格沒有台幣(PRICE_TWD)", price_twd_missing(lines, visual_lines(tag, lines))
                       if locale_cfg.enabled("price_local_currency") else [])):
        if hit:
            w.append((name, hit, True))
    return w


def spec_names(tag):
    """projects/<tag>/spec.json 的 names(人名/專名清單);沒有回 ()。"""
    try:
        n = json.loads((P.PROJECTS / tag / "spec.json").read_text(encoding="utf-8")).get("names")
        return tuple(x if isinstance(x, str) else str(x.get("name", "")) for x in n) if isinstance(n, (list, tuple)) else ()
    except (OSError, ValueError, AttributeError):
        return ()


# ---- 句級檢查子集(2026-10-31,director_ab §8;line_fix 與 director 用,不改 main 的輸出與結束碼)----
# block=True:單句命中就算超標(T 門檻為 0 的硬擋項:判決腔、配音唸不出的語助詞);False:main 裡是計次/警告項,這裡只指出哪句有
def sentence_hits(ln, text, nxt=None, pseg=None):
    """一行旁白(text)的句級命中 -> [{line, code, block, why}];nxt = 下一行文字(對仗、「不是 A」接「是 B」要看鄰句)。"""
    out = []

    def add(code, block, why):
        out.append(dict(line=ln, code=code, block=block, why=why))
    if VERDICT.search(text):
        add("VERDICT", True, "判決腔(對玩家說法宣判,2_文案 §1.1);判斷留給並排事實")
    if BAD_PARTICLE.search(text):
        add("BAD_PARTICLE", True, "配音唸不出的語助詞(耶/蛤/齁/嗯、句尾啊、主詞後喔);改寫成白名單語助詞或刪掉")
    for code, pat, why in (("CLICHE", CLICHE, "套話與拔高"), ("SIGNPOST", SIGNPOST, "報幕句"), ("FORMAL", FORMAL, "書面轉接與套話"),
                           ("SUMMARY", SUMMARY, "總結與講解腔"), ("SELF_QA", SELF_QA, "自問自答")):
        if pat.search(text):
            add(code, False, why)
    if NOT_BUT.search(text) or (nxt is not None and re.search(r"不是", text) and re.match(r"(它|而|那)?是", nxt)):
        add("NOT_BUT", False, "不是A是B")
    if triple(text):
        add("TRIPLE", False, "三連排比")
    if nxt is not None and parallel(text, nxt):
        add("PARALLEL", False, "與下一句對仗(開頭或結尾連續 3 字相同)")
    sents = sentences([(ln, text)])
    if PRONOUN.search(text):
        add("PRONOUN", False, "代稱(這個人/這家公司/該公司…),改回名字")
    if warmup_hits(pseg, sents):
        add("WARMUP", False, "暖場與單句預告")
    if VERIFY.search(text):
        add("VERIFY", False, "交代查證與打預防針")
    if DISCLAIMER.search(text):
        add("DISCLAIMER", False, "免責唸出口(免責只放畫面)")
    if COPIED.search(text):
        add("COPIED", False, "照抄規則範例句")
    for _, t in sents:
        n = len([c for c in CLAUSE_SPLIT2.split(t) if c.strip()])
        if n > T["clauses_max"]:
            add("CLAUSES", False, f"一句 {n} 個子句(> {T['clauses_max']})")
            break
    longc = [c.strip() for c in CLAUSE_SPLIT3.split(text) if len(_UNIT_RE.findall(c)) >= T["clause_chars"]]
    if longc:
        add("CLAUSE_LONG", False, f"子句 >= {T['clause_chars']} 字:{longc[0][:20]}")
    if len(num_groups(text)) > T["nums_max"]:
        add("NUMS", False, f"一句數字群 > {T['nums_max']}")
    out += qc_prone_hits(ln, text)
    return out


# P4:配音品管易失敗句型(警告,B 段 line_fix 先改;不動意思、數字)
_QC_STRIP = re.compile(r"[\s,，。.?？!！、;；:：「」『』()（）《》\"'…—-]")


def qc_prone_hits(ln, text):
    """-> [{line, code, block=False, why}]:SHORT_LINE 短句、COMMA_MANY 句內逗號過多、EN_TAIL 句尾英文;門檻見 T(short_chars/comma_warn/en_tail)。"""
    core = _QC_STRIP.sub("", text)
    out = []
    if core and len(core) < T["short_chars"]:
        out.append(dict(line=ln, code="SHORT_LINE", block=False, why=f"短句(< {T['short_chars']} 字):配音易尾音突兀、聲線飄;併進前後句或補足語意"))
    n = len(re.findall("[,，]", text))
    if n >= T["comma_warn"]:
        out.append(dict(line=ln, code="COMMA_MANY", block=False, why=f"句內 {n} 個逗號(>= {T['comma_warn']}):配音逗號停頓過短/連讀;拆短或減逗號"))
    if T["en_tail"] and re.search(r"[A-Za-z]$", core):
        out.append(dict(line=ln, code="EN_TAIL", block=False, why="句尾是英文詞:配音易聲線漂移、尾音升調;句尾改接中文詞(如「…的 PvP 玩法」)"))
    return out


def check_sentences(tag, line_nos=None):
    """script.txt 句級檢查子集 -> [{line, code, block, why}](依行號);line_nos 給了只回那些行(鄰句仍讀全片)。不含全片比例、連貫、畫面類檢查。"""
    lines = spoken_lines(tag)
    want = None if line_nos is None else set(line_nos)
    pseg = _pseg()
    out = []
    for i, (ln, t) in enumerate(lines):
        if want is None or ln in want:
            out += sentence_hits(ln, t, lines[i + 1][1] if i + 1 < len(lines) else None, pseg)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--all", action="store_true", help="列出每一筆命中(預設每項只列前 5 筆)")
    ap.add_argument("--strict", action="store_true", help="警告也算超標(結束碼非 0)")
    a = ap.parse_args()
    lines = spoken_lines(a.tag)
    n = len(lines)
    if not n:
        sys.exit("沒有旁白行")
    hits = dict(報幕句=[], 不是A是B=[], 書面轉接=[], 三連排比=[], 相鄰對仗=[], 配音唸不出的語助詞=[], 總結與講解腔=[], 判決腔=[], 自問自答=[], 電報體=[], 套話與拔高=[])
    for i, (ln, t) in enumerate(lines):
        if CLICHE.search(t):
            hits["套話與拔高"].append((ln, t))
        if SIGNPOST.search(t):
            hits["報幕句"].append((ln, t))
        if NOT_BUT.search(t) or (i + 1 < n and re.search(r"不是", t) and re.match(r"(它|而|那)?是", lines[i + 1][1])):
            hits["不是A是B"].append((ln, t))
        if FORMAL.search(t):
            hits["書面轉接"].append((ln, t))
        if BAD_PARTICLE.search(t):
            hits["配音唸不出的語助詞"].append((ln, t))
        if SUMMARY.search(t):
            hits["總結與講解腔"].append((ln, t))
        if VERDICT.search(t):
            hits["判決腔"].append((ln, t))
        if SELF_QA.search(t):
            hits["自問自答"].append((ln, t))
        if triple(t):
            hits["三連排比"].append((ln, t))
        if i + 1 < n and parallel(t, lines[i + 1][1]):
            hits["相鄰對仗"].append((ln, t + " / " + lines[i + 1][1]))
    # 電報體:連續 4 個以上、每個不超過 9 字的短句
    sents = [(ln, x) for ln, t in lines for x in re.split(r"[。?!?!]", t) if x.strip()]
    run = []
    for ln, x in sents + [(0, "x" * 99)]:
        if len(re.sub(r"\W", "", x)) <= 9:
            run.append((ln, x))
            continue
        if len(run) >= 4:
            hits["電報體"].append((run[0][0], "。".join(x for _, x in run)))
        run = []
    lens = [len(re.sub(r"\W", "", t)) for _, t in lines]
    cv = statistics.pstdev(lens) / statistics.mean(lens)
    part = sum(1 for _, t in lines if PARTICLE.search(t))
    react = sum(1 for _, t in lines if REACT.search(t))
    long_ = sum(1 for x in lens if x >= T["long_chars"])
    # (名稱, 實際值, 是否超標, 門檻說明, 是否降為警告)
    rows = [
        ("報幕句比例", len(hits["報幕句"]) / n, len(hits["報幕句"]) / n > T["signpost_ratio"], f"<= {T['signpost_ratio']:.0%}", False),
        ("不是A是B 次數", len(hits["不是A是B"]), len(hits["不是A是B"]) > T["not_but"], f"<= {T['not_but']}", False),
        ("書面轉接 次數", len(hits["書面轉接"]), len(hits["書面轉接"]) > T["formal"], f"<= {T['formal']}", False),
        ("三連排比 次數", len(hits["三連排比"]), len(hits["三連排比"]) > T["triple"], f"<= {T['triple']}", False),
        ("相鄰對仗 次數", len(hits["相鄰對仗"]), len(hits["相鄰對仗"]) > T["parallel"], f"<= {T['parallel']}", False),
        ("配音唸不出的語助詞 次數", len(hits["配音唸不出的語助詞"]), len(hits["配音唸不出的語助詞"]) > T["bad_particle"], f"= {T['bad_particle']}", False),
        ("總結與講解腔 次數", len(hits["總結與講解腔"]), len(hits["總結與講解腔"]) > T["summary"], f"<= {T['summary']}", False),
        ("判決腔 次數", len(hits["判決腔"]), len(hits["判決腔"]) > T["verdict"], f"= {T['verdict']}", False),
        ("自問自答 次數", len(hits["自問自答"]), len(hits["自問自答"]) > T["self_qa"], f"<= {T['self_qa']}", False),
        ("電報體 段數", len(hits["電報體"]), len(hits["電報體"]) > T["telegram"], f"<= {T['telegram']}", False),
        ("套話與拔高 次數", len(hits["套話與拔高"]), len(hits["套話與拔高"]) > T["cliche"], f"<= {T['cliche']}", True),
        ("含語助詞/口頭語的句子", part / n, part / n > T["particle_hi"], f"<= {T['particle_hi']:.0%}", False),
        ("第一人稱反應句", react / n, react / n < T["react"], f">= {T['react']:.0%}", True),   # 2026-10-20 降為警告:反應句黏在事實上,不補段尾短評
        # 2026-10-13 由 0.40 下修:使用者指定文案越白話越直接越好,不為了節奏硬加長句與插話;2026-10-20 再降為警告(與規則_文案「以本條為準」一致)
        ("句長變異係數", cv, cv < T["cv_min"], f">= {T['cv_min']}", True),
        ("24 字以上長句", long_ / n, long_ / n < T["long_ratio"], f">= {T['long_ratio']:.0%}", True),
    ]
    bad = warn = 0
    print(f"[lint] {a.tag}: 旁白 {n} 句,平均 {statistics.mean(lens):.1f} 字")
    for name, v, over, thr, soft in rows:
        label = " ok "
        if over:
            if soft and not a.strict:
                label, warn = "警告", warn + 1
            else:
                label, bad = "超標", bad + 1
        val = f"{v:.0%}" if isinstance(v, float) and name != "句長變異係數" else (f"{v:.2f}" if isinstance(v, float) else str(v))
        print(f"  {label} {name}: {val}(門檻 {thr})")
    for k, v in hits.items():
        if v:
            print(f"- {k} {len(v)} 筆:")
            for ln, t in (v if a.all else v[:5]):
                print(f"    L{ln} {t[:44]}")
    # v2 新增警告檢查
    fstats = {}
    fw = fluency_warnings(lines, block_starts(a.tag), fstats)
    for name, hit, over in v2_warnings(lines) + fw + pause_warnings(a.tag) + visual_warnings(visual_lines(a.tag, lines)) + taste_warnings(lines, a.tag):
        label = " ok "
        if over:
            label, bad, warn = ("超標", bad + 1, warn) if a.strict else ("警告", bad, warn + 1)
        print(f"  {label} {name} {len(hit)} 筆")
        for ln, t in (hit if a.all else hit[:5]):
            print(f"    {'L%d ' % ln if ln else ''}{t[:60]}")
    (sh, st), (ch_, cj), (rn, rt) = fstats["src"], fstats["chain"], fstats["report"]
    print(f"  資訊 旁白連貫:來源起句比例 {sh / st if st else 0:.0%}({sh}/{st}),接住比例 {ch_ / cj if cj else 1:.0%}({ch_}/{cj}),轉述句比例 {rn / rt if rt else 0:.0%}({rn}/{rt})")
    pc = played_claims(lines, not not_played(a.tag))
    if pc:
        bad += 1
        print(f"  超標 使用者沒玩過卻寫第一人稱遊玩經歷 {len(pc)} 筆(PLAYED_CLAIM)")
        for ln, t in pc:
            print(f"    L{ln} {t[:60]}")
    khit = kit_errors(visual_lines(a.tag, lines))
    if khit:
        bad += 1
        print(f"  超標 動態小件(kit) {len(khit)} 筆")
        for ln, t in khit:
            print(f"    L{ln} {t}")
    print(f"[lint] 警告 {warn} 項(不中止;--strict 才算超標)")
    print(f"[lint] 超標 {bad} 項")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
