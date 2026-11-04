#!/usr/bin/env python3
r"""ChatTTS 發音修正表(只用標準函式庫)。

【用途】ChatTTS 對某些多音字常讀錯。文案遇到多音字誤讀,**優先加進這個檔案**(通用表 WORDS 或規則),
而不是改寫句子;只有加表也救不了才改文案。修正只作用在「送進 ChatTTS 的文字」(tts_chattts.prep_text 呼叫 apply),
字幕、script.txt、script.json 的 text 都保持原字。

【著】(2026-10 診斷,F_seed_2456、+18%、12 句 x 3 seed,Whisper 回查)
  OpenCC t2s 不改「著」(著->著;只有「着」本身維持「着」),所以送進模型的就是「著」,模型有 24/42 把助詞「著」唸成 zhù(住),
  睡著(zháo)有 11/18 唸成 zhù。換字後:
    助詞(看著、等著、接著、跟著...)-> 「者」:zhù 0/42,整句辨識保真度最高(差句 2/36,「着」7/36、「著」14/36),輕聲特徵
      (字長中位數為同句其他字的 0.89 倍、能量相當)與「着」相同,所以選「者」。
    zháo(睡著、找著、睡不著...)-> 「着」:zhù 0/18(原字 11/18)。
  例外詞(著名、顯著、執著...)保持原字,讀本來的音。

【職稱的「長」】(2026-10-11 dei v1 使用者聽審:「多元長」唸成 cháng,辨識結果是「多元腸」)
  「職務名 + 長」(TITLE_STEMS:多元、執行、營運、財務、公關、董事…)的「長」換成只有 zhǎng 一讀的「掌」。只收兩字以上的職務名;
  後面接 期久達途遠度…(TITLE_NOT_NEXT,長期、長久、長達、長度)的不換。校長、市長這類兩字常用詞不收(會誤傷「學校長期」)。
【動詞的「量」】(同日:「一項一項量」唸成 liàng)
  liáng 讀法換成只有 liáng 一讀的「良」:詞表 MEASURE_WORDS(測量、丈量、量體溫…)、「一 X 一 X 量」、「來/去/再/怎麼… + 量」在子句尾或
  接「了/過/一/出…」、「量 + 一下/一次/出來…」。前一字是「數力大質能流銷…」(LIANG_NOUN_PREV,名詞 X量)的不換。
  兩條規則尚未以「原句 3 seed + 語音辨識」回查(2026-10-11 顯示卡被別的程式佔用);回查後把結果補在這裡,唸不對就換別的同音字。
【快取鍵】tts_key.audio_key 對 chattts 用 key_text(say):沒有被替換的句子鍵與以前完全相同;含「著」被替換的句子,
  鍵用替換後文字計算(換字改了,舊快取就會重錄)。
【品管】tts_chattts.measure 用 qc_pair 把「著/着/者」視為同一字再比對,並檢查被替換位置是否被辨識成 zhù 字。
"""
import difflib
import re

# 助詞「著」送進 TTS 的寫法 / zháo 讀法的「著」送進 TTS 的寫法
PARTICLE = "者"
ZHAO = "着"

# 「著」保持原字(讀本來的音)的詞;以「詞中含著的位置」比對
EXCEPTION_WORDS = [
    "著名", "著作", "著稱", "顯著", "卓著", "著手", "著急", "著力", "著眼", "著想", "著重", "著陸", "執著", "著迷",
    "著火", "著涼", "著實", "著述", "土著", "昭著", "著色",
    "附著", "名著", "巨著", "專著", "編著", "譯著", "論著", "原著", "著者", "著錄", "著書", "著裝", "著落", "著墨",
    "著床", "著魔", "著慌", "著惱", "著意", "著緊",
]
EXCEPTION_NOT_NEXT = {"譯著": "色"}   # 「編譯著色器」的「譯著」不算例外詞(與 pron_rules.json 的 譯著(?!色) 一致)
# zháo 讀法:動詞 + 著,且後面是「了/沒/過/標點/句尾」,或「動詞 + 不/得 + 著」
ZHAO_VERBS = "睡找猜碰摸夠撞燒"
_ZHAO_NEXT = set("了沒過。，,.!?！？；;：:、…~～」』 ") | set("\n")

# 通用表:詞 -> 送進 TTS 的寫法(其他多音字誤讀,例如 重、行、了,遇到就加在這裡;長詞優先)
# 例:WORDS = {"重新": "從新"}  # 只是示意;換字後要用診斷(同一句多 seed + Whisper 回查)確認真的唸對
WORDS = {
    "亂傳": "亂船",   # 2026-10-10:「亂傳」3 個 seed 全被唸成「亂串/亂轉」,換字後 3/3 辨識為「傳」;流傳、一直傳沒問題,不必換
    "欸": "誒",       # 「欸」不在模型字表,會被唸成「哀」;使用者聽過句首「誒」可以(句尾仍不可用,見 CLAUDE.md)
    "咧": "嘞",       # 「然後咧」被唸成別的字;使用者聽過「嘞」可以
    "所以勒": "所以嘞",
    "然後勒": "然後嘞",
    # 2026-10-11 snack:「從 85 元調到 89 元」的「調」被唸成 diào(使用者聽審);價格調整義一律換成只有 tiáo 讀音的「條」
    "調到": "條到", "調漲": "條漲", "調高": "條高", "調降": "條降", "調整": "條整", "調回": "條回",
    # 2026-10-14 dei_tracer:「角色」被唸成 jué sè(使用者聽審),要唸 jiǎo sè;換成「腳色」
    "角色": "腳色",
}

# 職稱「X長」-> zhǎng(見檔頭)。要加職稱就加在 TITLE_STEMS(兩字以上;「內容、產品、設計」這類後面常接形容詞「長」的不收)
TITLE_CHAR = "掌"
TITLE_STEMS = ["多元", "執行", "營運", "財務", "公關", "技術", "行銷", "資訊", "策略", "創意", "人資", "法務", "永續", "數位", "投資",
               "營收", "董事", "理事", "秘書", "祕書", "檢察", "幕僚", "參謀", "隱私", "風控", "共融", "多樣", "研發", "商務", "供應",
               "採購", "會計", "稽核", "傳播", "人事", "總務", "教務", "學務", "審計", "監察", "分局", "分隊", "小隊", "大隊", "中隊", "委員"]
TITLE_NOT_NEXT = "期久達途遠度短足紅線尾河"
_TITLE_RE = re.compile("(%s)長(?![%s])" % ("|".join(sorted(TITLE_STEMS, key=len, reverse=True)), TITLE_NOT_NEXT))

# 動詞「量」-> liáng(見檔頭)
MEASURE_CHAR = "良"
MEASURE_WORDS = ["測量", "丈量", "量測", "衡量", "量一量", "量量看", "量體溫", "量血壓", "量體重", "量身高", "量身", "量尺寸", "量腰圍",
                 "量杯", "量尺", "量筒", "量角器", "量表"]
LIANG_NOUN_PREV = "數力大質能流銷容重份劑產音含分熱膽酒聲考盡少過適定批海雨肚度氣運載用總儲存變向當較雅體限增減微巨足全輕飯食水電風光商思打估掂酌胃藥要"
_END = "。，,.!?！？；;：:、…~～」』）) 了過一出完看起到得不"
_LIANG_RES = [
    re.compile("(?<![%s])(?:%s)" % (LIANG_NOUN_PREV, "|".join(sorted(MEASURE_WORDS, key=len, reverse=True)))),
    re.compile(r"一(.)一\1量(?=$|[%s])" % _END),
    re.compile("(?:來|去|再|怎麼|拿去|拿來|用尺|重新|親自|逐一|逐項|一一|慢慢|仔細|好好)量(?=$|[%s])" % _END),
    re.compile("(?<![%s])量[了過]?(?:一下|一次|一遍|看看|出來|起來|不出|得出)" % LIANG_NOUN_PREV),
]

# 品管用:被視為同一個字的寫法
EQUIV = "著着者"
ZHU_CHARS = set("住注柱主助驻祝筑铸蛀拄炷贮伫駐築鑄")
_MARK = "Ζ"  # 希臘大寫 Zeta(\w,不會被品管的標點過濾掉)
MARK = _MARK
NO_CHECK = set("誒嘞")   # 語助詞換字:辨識寫法不固定,不做讀音回查


def _mark_and_fix(text):
    """回傳 (送進 TTS 的文字, 被替換的「著」位置 {索引: 替換字})。通用表 WORDS 在最後套用(不產生位置紀錄)。"""
    out, rep = list(text), {}
    for i, ch in enumerate(text):
        if ch != "著":
            continue
        if any(text[i - w.index("著"):][:len(w)] == w and not text.startswith(EXCEPTION_NOT_NEXT.get(w, "\x00"), i - w.index("著") + len(w))
               for w in EXCEPTION_WORDS if i >= w.index("著")):
            continue
        prev = text[i - 1] if i else ""
        nxt = text[i + 1] if i + 1 < len(text) else ""
        zhao = (prev in ZHAO_VERBS and (nxt == "" or nxt in _ZHAO_NEXT)) or \
            (prev != "" and prev in "不得" and i >= 2 and text[i - 2] in ZHAO_VERBS)
        out[i] = rep[i] = ZHAO if zhao else PARTICLE
    t = "".join(out)
    for w in sorted(WORDS, key=len, reverse=True):
        t = t.replace(w, WORDS[w])
    t = _TITLE_RE.sub(lambda m: m.group(1) + TITLE_CHAR, t)
    for rx in _LIANG_RES:
        t = rx.sub(lambda m: m.group().replace("量", MEASURE_CHAR), t)
    return t, rep


_TITLE_COLON_RE = re.compile(r"《[^《》]*》")


def drop_title_colon(text):
    """書名號內的冒號(半形與全形)直接刪掉:「《惡靈古堡:安魂曲》」連著唸,不產生停頓(prep_text 會把冒號換成逗號 = 停頓)。
    書名號外的冒號不動。會改變字數,所以只在 apply 的最後一步做;換字位置(rule_positions/changes)用 _fixed_same_len。"""
    return _TITLE_COLON_RE.sub(lambda m: re.sub("[:：]", "", m.group()), text)


def apply(text):
    """送進 ChatTTS 的文字(繁體,尚未轉簡體)。沒有要修正的字時原樣回傳。"""
    return drop_title_colon(_mark_and_fix(text)[0])


def _fixed_same_len(text):
    """換字後、尚未刪書名號冒號的文字(與 text 逐字對位,供 rule_positions/changes 使用)。"""
    return _mark_and_fix(text)[0]


def rule_positions(text):
    """「著」以外被換字的位置 {text 的索引: 換上去的字}(通用表、職稱「長」、動詞「量」;語助詞 NO_CHECK 除外)。
    tts_chattts.pron_rule_bad 拿來回查讀音;換字前後長度不同(表裡有不等長的詞)時無法對位,回傳空的。
    書名號內刪冒號不算換字(用 _fixed_same_len,不列入也不影響對位)。"""
    fixed = _fixed_same_len(text)
    if len(fixed) != len(text):
        return {}
    return {i: b for i, (a, b) in enumerate(zip(text, fixed)) if a != b and a != "著" and b not in NO_CHECK}


def changes(text):
    """聽審頁用:「著」以外的換字清單,如 ["多元長→掌"]。書名號內刪冒號不列入(同「著→者」,不是需要人耳確認的換字)。"""
    fixed = _fixed_same_len(text)
    if len(fixed) != len(text):
        return ["(整句)"] if fixed != text else []
    return [text[max(0, i - 2): i + 1] + "→" + b for i, (a, b) in enumerate(zip(text, fixed)) if a != b and a != "著"]


def key_text(text):
    """快取鍵用的文字:沒被修正的句子就是原文(鍵與沒有這個機制時完全相同);被修正的句子用修正後文字。"""
    return apply(text)


def qc_pair(text, hyp, norm):
    """品管比對用。norm = tts_chattts.norm_text。
    回傳 (ref, hyp, bad):句中有被替換的「著」時,ref/hyp 內所有 著/着/者 視為同一字(辨識成其中任何一個都算對),
    bad = 被替換位置在辨識結果中對到 zhù 字(住注柱...)的個數;沒有被替換的「著」時原樣回傳 (text, hyp, 0)。"""
    fixed, rep = _mark_and_fix(text)
    if not rep:
        return text, hyp, 0
    marked = "".join(_MARK if i in rep else c for i, c in enumerate(text))
    ref_n = norm(marked)
    rep_idx = [i for i, c in enumerate(ref_n) if c == _MARK]
    canon = lambda s: re.sub("[%s]" % EQUIV, _MARK, s)
    ref_c, hyp_n = canon(ref_n), norm(hyp)
    hyp_c = canon(hyp_n)
    bad = 0
    mp = {}
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref_c, hyp_c, autojunk=False).get_opcodes():
        if tag in ("equal", "replace"):
            for i in range(i1, i2):
                if j2 > j1:
                    mp[i] = min(j2 - 1, j1 + (i - i1) * (j2 - j1) // max(1, i2 - i1)) if tag == "replace" else j1 + i - i1
    for i in rep_idx:
        if mp.get(i) is not None and hyp_n[mp[i]] in ZHU_CHARS:
            bad += 1
    return ref_c, hyp_c, bad


if __name__ == "__main__":
    import sys
    for s in sys.argv[1:] or ["他看著我,什麼都沒說。", "著名的作品", "睡著了", "我睡不著", "摸著石頭過河", "請了第一位多元長。", "一項一項量。"]:
        print(s, "->", apply(s))
