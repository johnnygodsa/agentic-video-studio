#!/usr/bin/env python3
r"""spec.json 檢查(channel/_archive/plans/PLAN_FRAMEWORK.md §0.2):查證表對得到旁白、規格達成表。

  python -X utf8 pipeline/spec_check.py --tag onimusha [--spec <spec.json>]

句號 = script.txt 旁白句依序 1-based 編號(與 script_txt2json 輸出順序一致,不含 # 說明行與 @ 指令)。
事實覆蓋:spec.json 的 facts 缺或空、且 projects\<tag>\facts*.md 存在時,略過下面的「沒有 fact 涵蓋」檢查並印「事實覆蓋改由 facts_check 檢查」(不報錯)。
錯誤(exit 1):facts[].lines 缺/越界;含數字、引號引言、spec.names 人名的句子沒有 fact 涵蓋;
  標題 facts id 不存在;unverified fact 的句子沒有 anim/quote src 標「未證實」。
譯名表(PLAN_TTS_FLOW R5):spec.tw_names 為 dict {原文: 譯名 或 {"tw": 譯名, "avoid": [他譯]}} 時,字幕/say 含 avoid 他譯、
  或含原文卻同句沒有譯名 → 錯誤。spec.names 仍是真人姓名清單(舊用法,不變,與 tw_names 無關)。
警告(只印不中止):片長、判斷句秒數、話題數、橋接比例、自製畫面比例;數字句沒數字畫面(F2-2)。
F2-2 畫面檢查(visual_suggest.line_visual):數字句的畫面不是 num/bars/cols/share/timeline/span、card、quote/compare、截圖 hl → 警告;
  anim 同句又帶 v/img/shots/quote/compare(素材畫面疊動畫;build 以 anim 優先、悄悄忽略素材)→ 錯誤。
package(F1-3,有標題或封面才檢查):標題 5 個、字數、禁用寫法、前 3 切角不同;封面 3 組(方案1 face/action、方案2 collage、方案3 = 方案1 另一版,副/補字須與方案1 不同),都三行;
  標題 5 個都要含 package.subject(本片主體作品名);封面主/副文字要含主體名;ChannelA另查攻擊詞(依據 channel\規則\4_交付發片.md §4 與頻道檔)。
  警告:方案 N 的封面三行(去主體名後)與第 N 個標題的最長共同字句 ≥4 全形字 -> 重複字句(4_交付發片 §4.2,2026-11-03)。

封面人像跨片重複(SOP §4,2026-10-19;不靠 spec.json,讀說明檔「發片資料」的 方案1/2/3 段,跨專案共用格式不加欄位):
  python -X utf8 pipeline/spec_check.py --tag <tag> --notes <說明檔.md>   (給 --notes 只跑這項;--tag 用來排除自己)
  python -X utf8 pipeline/spec_check.py --tag <tag> --notes <說明檔.md> --record   方案1、3 寫進 channel\cover_persona_log.jsonl(同 tag+plan 覆寫)
  python -X utf8 pipeline/spec_check.py --recent-sheet <新圖>   最近 8 張 Youtube AD 方案1 底圖(唯讀)+新圖 -> tmp\cover_recent_sheet.jpg
從 主體/場景/視覺構圖 以關鍵字抽 kind 與六格(性別/年齡層/髮型/服裝/場景/手勢)+色彩,抽不到記 None;對 log 中其他 tag 最近 10 筆原創玩家:
  六格相同 ≥3、手勢同最近 3 筆、場景同最近 2 筆、方案1 與 3 都是原創玩家且不同格 <4 → 錯誤(exit 1);原創玩家六格缺值、
  最近 5 筆方案1 已有 ≥2 筆原創玩家 → 警告。
"""
import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pace  # noqa: E402
import paths  # noqa: E402
import script_txt2json as s2j  # noqa: E402

CPS = pace.CHARS_PER_SEC  # 每秒字數(單一出處 pace.py,已含停頓),只用來估計

# 「數字」判斷(保守:寧可漏報也不要把「一個、一直、第一場」當數據):
#  1) 阿拉伯數字 [0-9]
#  2) 中文數字 + 單位。單位只收年月日歲倍套萬億公尺公里成人名位場次集天週分秒小時;
#     不收 個/件/種/款/代(二代、三個論點不是數據)。
#  3) 純「一」+ 單位(一年、一次)略過;前面是「第」(第一場)略過。
_NUM = r"[零〇一二兩三四五六七八九十百千萬億]"
_UNIT = r"(?:年|月|日|歲|倍|套|萬|億|公尺|公里|成|人|名|位|場|次|集|天|週|分|秒|小時)"
RE_CN = re.compile(rf"(?<!第)({_NUM}+)[多幾餘]?{_UNIT}")
RE_QUOTE = re.compile(r"[「」『』]")


def has_number(text):
    if re.search(r"[0-9]", text):
        return True
    return any(m.group(1) != "一" for m in RE_CN.finditer(text))


# 畫面檢查用:日期(年份、幾月幾日)是敘事不是數據,先去掉再判斷;期間(二十年)仍算。
RE_DATE = re.compile(rf"(?:[0-9]{{4}}|[零〇一二三四五六七八九]{{4}})\s*年|(?:[0-9]{{1,2}}|{_NUM}{{1,3}})\s*[月日號]")


def has_data_number(text):
    return has_number(RE_DATE.sub("", text))


def load_lines(tag):
    src = paths.ROOT / tag / "script.txt"
    title, says, sections, top, defs, _ = s2j.parse(src.read_text(encoding="utf-8-sig"))
    lines = []
    for sec in sections:
        lines.extend(s2j.build_lines(sec["rows"], defs))
    return lines


def mark_ok(extra, key):
    d = extra.get(key)
    return isinstance(d, dict) and "未證實" in str(d.get("src", ""))


def name_rules(spec):
    """spec.tw_names 為 dict 時回傳 [(原文, 台灣譯名, [avoid...])];缺或非 dict → [](不碰 names 人名清單)。
    值可為純字串(譯名)或 {"tw": 譯名, "avoid": [他譯...]};只有 avoid 沒有 tw 也接受。"""
    names = spec.get("tw_names")
    if not isinstance(names, dict):
        return []
    out = []
    for key, v in names.items():
        if isinstance(v, dict):
            tw, avoid = str(v.get("tw") or ""), v.get("avoid") or []
        else:
            tw, avoid = str(v or ""), []
        if isinstance(avoid, str):
            avoid = [avoid]
        out.append((str(key), tw, [str(a) for a in avoid if str(a).strip()]))
    return out


def _has_term(term, text):
    """ASCII 原文不分大小寫且前後不可接英數(避免 AI 命中 FAIR);中文詞直接子字串。"""
    if term.isascii():
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, re.I) is not None
    return term in text


def check_names(spec, lines):
    """譯名表(PLAN_TTS_FLOW R5):字幕/旁白(text 與 @say 後的 say)出現 avoid 他譯 → 錯誤;
    出現原文 key 但同句沒有台灣譯名 → 錯誤(字幕可保留原文,只要同句 say 或字幕有譯名)。"""
    errs = []
    rules = name_rules(spec)
    for i, ln in enumerate(lines, 1):
        parts = [ln.get("text") or "", ln.get("say") or ""]
        blob = " ".join(parts)
        for key, tw, avoid in rules:
            clean = blob.replace(tw, "") if tw else blob  # 譯名本身含他譯字樣時不誤判
            for a in avoid:
                if a in clean:
                    errs.append(f"句{i} 含他譯「{a}」,譯名表要用「{tw or key}」:{parts[0][:24]}")
            if tw and _has_term(key, blob) and tw not in blob:
                errs.append(f"句{i} 含原文「{key}」但同句沒有譯名「{tw}」:{parts[0][:24]}")
    return errs


def facts_md_exists(tag):
    """projects\\<tag>\\facts*.md 存在 -> True(spec.json 的 facts 空時,事實覆蓋改由 facts_check 檢查)。"""
    return bool(tag) and any(p.is_file() for p in (paths.PROJECTS / tag).glob("facts*.md"))


def check(spec, lines, skip_fact_cover=False):
    """skip_fact_cover=True:略過「數字/引言/人名句要有 fact 涵蓋」(spec.facts 空且有 facts*.md,改由 facts_check)。"""
    errs, n = [], len(lines)
    facts = spec.get("facts", [])
    covered = {}  # 句號 -> [fact id]
    ids = set()
    for f in facts:
        fid = f.get("id", "?")
        ids.add(fid)
        ls = f.get("lines")
        if not ls or not isinstance(ls, list):
            errs.append(f"{fid} 缺 lines")
            continue
        for k in ls:
            if not isinstance(k, int) or not 1 <= k <= n:
                errs.append(f"{fid} lines 句{k} 不存在(共 {n} 句)")
            else:
                covered.setdefault(k, []).append(fid)
        if f.get("status") not in ("confirmed", "partial", "single", "unverified"):
            errs.append(f"{fid} status 不合法: {f.get('status')}")
    names = spec.get("names", [])
    errs += check_names(spec, lines)
    for i, ln in enumerate(lines, 1):
        t = ln["text"]
        why = []
        if has_number(t):
            why.append("數字")
        if RE_QUOTE.search(t):
            why.append("引言")
        hit = [x for x in names if x in t]
        if hit:
            why.append("人名:" + "/".join(hit))
        if why and i not in covered and not skip_fact_cover:
            errs.append(f"句{i} 含{'、'.join(why)}但沒有 fact 涵蓋:{t[:24]}")
    for f in facts:
        if f.get("status") != "unverified":
            continue
        for k in f.get("lines") or []:
            if isinstance(k, int) and 1 <= k <= n:
                ex = lines[k - 1]
                if not (mark_ok(ex, "anim") or mark_ok(ex, "quote")):
                    errs.append(f"{f['id']} 未證實,但句{k} 的 anim/quote src 沒有「未證實」")
    for ti in spec.get("package", {}).get("titles", []):
        for fid in ti.get("facts", []):
            if fid not in ids:
                errs.append(f"標題「{ti.get('text', '')[:12]}」引用不存在的 fact {fid}")
    for s in spec.get("sections", []):
        a, b = s.get("lines", [0, 0])
        if not (1 <= a <= b <= n):
            errs.append(f"段落 {s.get('name')} lines {a}-{b} 超出 1-{n}")
    return errs


# ---- package(封面標題)檢查。依據 channel\規則\4_交付發片.md §3–§4(舊章節號見 channel\_archive6-10-22_重整\發片資料_規則.md) ----
# §3.1 長度:目標 14–24 全形字(半形計 0.5),上限 28
TITLE_W_MIN, TITLE_W_MAX, TITLE_W_HARD = 14, 24, 28
# §3.3 禁用寫法(不用【】括號、emoji、逗號頓號、「……」截斷、農場套板、極限詞);§2 不用 | - 串詞
TITLE_BAN_CHARS = "【】()（）[]［］〔〕｛｝,，、;；|｜"
TITLE_BAN_PHRASES = ["……", "...", "…", "一次看懂", "真相曝光", "你能接受嗎", "我整個傻眼", "結果出乎意料",
                     "下巴掉了", "史上最爛", "全面崩盤"]
RE_TITLE_BAN = [(re.compile(r"以為.{1,12}其實"), "以為X其實Y"), (re.compile(r"\s[-－—]+\s"), "用 - 串詞")]
RE_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
ANGLES = set("判數引損問反身矛")  # §3.2 切角代號
# 封面 3 組(channel\規則\4_交付發片.md §4.5;方案3 = 方案1 的另一版:不同人物、不同三行字)
PLAN1_COMPOSITIONS = {"face", "action"}  # 方案1 字優先:大臉 / 半身動作(一定有人像,2026-10-17 拿掉 object)
PLAN2_COMPOSITION = "collage"            # 方案2 漫畫拼貼破框
COVER_PLANS = ("1", "2", "3")
# 兩方案都固定三行:主文字=主體名、副文字=嗆聲判語、補充字=最刺的數字或後果(全形 1、半形 0.5,去空白)
COVER_LINE_W = {"main": (2, 6), "sub": (4, 9), "supp": (3, 8)}
COVER_TOTAL_MAX = 16
# ChannelC(sci)分支沿用舊規則,不動(channel\規則_科普片.md)
SCI_COVER_CHARS_MAX, SCI_COVER_MAIN, SCI_COVER_TAG_MAX = 10, (2, 5), 4
# ChannelA封面與標題要有攻擊性(SOP v3 2026-10-17);ChannelB不查
ATTACK_WORDS = ["坑", "騙", "爛", "擺爛", "翻車", "吃相", "割韭菜", "背刺", "打臉", "搶錢", "完蛋", "別買", "糞", "垃圾",
                "雙標", "當盤子", "破防", "砸", "嗆", "搞爛", "爛貨", "下架", "退款", "炸鍋", "出包", "摳", "貪"]
TITLE_ATTACK_MIN = 3   # 5 個標題至少幾個含攻擊詞
TITLE_SUBJECT_POS = 8  # 第 1 個標題的主體名要出現在前幾個全形字內
# §4 色票(色名與色碼成對)
PALETTE = {"亮黃": "#FFD400", "純白": "#FFFFFF", "亮青": "#38BDF8", "亮紅": "#FF3B3B",
           "亮橘": "#FF8A00", "亮綠": "#22C55E", "亮粉": "#FF4FA3", "墨黑": "#1B1414"}
RE_QMARK = re.compile(r"[?？]")


def text_width(s):
    """全形(含中日韓)計 1、半形計 0.5。"""
    return sum(1 if unicodedata.east_asian_width(c) in "WF" else 0.5 for c in s)


def package_empty(pkg):
    return not (pkg.get("titles") or pkg.get("thumbs"))


COVER_TITLE_DUP_MIN = 4  # 封面一行與同號標題的最長共同字句 ≥ 幾個全形字 → 警告


def strip_subject(s, subj):
    """去掉主體名(長的先去),回傳剩下的文字。"""
    for w in sorted(subj, key=len, reverse=True):
        s = s.replace(w, " ")
    return s


def longest_common(a, b):
    """a、b 依標點/空白切段後,最長(以全形字寬計)的共同子字串;沒有回 ""。"""
    segs_b = [x for x in re.split(r"[\W_]+", b) if x]
    best = ""
    for seg in (x for x in re.split(r"[\W_]+", a) if x):
        for i in range(len(seg)):
            for j in range(i + 1, len(seg) + 1):
                sub = seg[i:j]
                if text_width(sub) > text_width(best) and any(sub in sb for sb in segs_b):
                    best = sub
    return best


def check_package(spec):
    """回傳 (errs, warns)。DEI 系列等頻道特例不檢查。"""
    pkg = spec.get("package") or {}
    errs, warns = [], []
    titles, thumbs = pkg.get("titles", []), pkg.get("thumbs", [])
    # ---- 標題(§3、§8)----
    if len(titles) != 5:
        errs.append(f"標題需 5 個,目前 {len(titles)}")
    for i, ti in enumerate(titles, 1):
        t = ti.get("text", "")
        tag = f"標題{i}「{t[:10]}」"
        w = text_width(t)
        if w > TITLE_W_HARD:
            errs.append(f"{tag} {w:g} 字,超過上限 {TITLE_W_HARD}")
        elif not TITLE_W_MIN <= w <= TITLE_W_MAX:
            warns.append(f"{tag} {w:g} 字,不在目標 {TITLE_W_MIN}-{TITLE_W_MAX}")
        bad = sorted({c for c in t if c in TITLE_BAN_CHARS})
        bad += [p for p in TITLE_BAN_PHRASES if p in t and not (p in ("…", "...") and "……" in t)]
        bad += [name for rx, name in RE_TITLE_BAN if rx.search(t)]
        if RE_EMOJI.search(t):
            bad.append("emoji")
        if bad:
            errs.append(f"{tag} 含禁用寫法:{' '.join(bad)}")
        if ti.get("angle") and ti["angle"] not in ANGLES:
            warns.append(f"{tag} 切角代號 {ti['angle']} 不在 {''.join(sorted(ANGLES))}")
        if i == 1 and RE_QMARK.search(t):
            warns.append(f"{tag} 第 1 名是問句(§3.1 不放第 1 名)")
        if i == 1 and t.count(" ") >= 2:
            warns.append(f"{tag} 三段以上標題平均扣 1.4–1.9 點,改兩段(4_交付發片 §3.1)")
    if sum(1 for ti in titles if RE_QMARK.search(ti.get("text", ""))) > 1:
        warns.append("問句標題超過 1 個(§3.1)")
    if titles and sum(1 for ti in titles if has_number(ti.get("text", ""))) < 2:
        warns.append("含具體數字的標題少於 2 個(§3.1)")
    if len(titles) >= 3:
        ang = [ti.get("angle") for ti in titles[:3]]
        if None in ang:
            warns.append("前 3 個標題缺 angle,無法檢查切角是否不同")
        elif len(set(ang)) < 3:
            errs.append(f"前 3 個標題切角需不同:{'/'.join(ang)}")
    # ---- 主體名(SOP §3,2026-10-17):標題與封面一定要有本片主體作品名;sci 不查 ----
    sci = spec.get("channel") == "ChannelC" or spec.get("form") == "sci"
    kuang = spec.get("channel") == "ChannelA"
    subj = [str(x) for x in pkg.get("subject") or [] if str(x).strip()]
    if not sci:
        if not subj:
            errs.append("package 缺 subject(本片主體作品名,見 封面提示詞_SOP §3)")
        else:
            for i, ti in enumerate(titles, 1):
                t = ti.get("text", "")
                if not any(x in t for x in subj):
                    errs.append(f"標題「{t[:12]}」沒有主體名 {subj[0]}")
                elif i == 1:
                    pos = min(t.index(x) for x in subj if x in t)
                    if text_width(t[:pos]) >= TITLE_SUBJECT_POS:
                        warns.append(f"標題1 主體名在第 {text_width(t[:pos]):g} 字之後,建議出現在前 {TITLE_SUBJECT_POS} 字內")
    if kuang and titles:
        n_atk = sum(1 for ti in titles if any(w in ti.get("text", "") for w in ATTACK_WORDS))
        if n_atk < TITLE_ATTACK_MIN:
            warns.append(f"含攻擊詞的標題 {n_atk} 個,少於 {TITLE_ATTACK_MIN}(ChannelA標題要有攻擊性)")
    # ---- 封面(§4、§5.3)----
    want = 1 if sci else 3
    if len(thumbs) != want:
        errs.append(f"封面方案需 {want} 個,目前 {len(thumbs)}")
    for p in thumbs:
        tag = f"封面方案{p.get('plan', '?')}"
        if not sci and str(p.get("plan")) not in COVER_PLANS:
            errs.append(f"{tag} 不存在(SOP v4 只有方案1、2、3)")
        ls = [str(x).strip() for x in p.get("lines", [])]
        if len(ls) != 3:
            errs.append(f"{tag} lines 需三行,目前 {len(ls)}")
            continue
        if sci:  # 舊規則不動
            n = sum(text_width(re.sub(r"\s", "", x)) for x in ls[:2])
            if n > SCI_COVER_CHARS_MAX:
                errs.append(f"{tag} 主文字加副文字合計 {n:g} 字(半形 0.5),超過 {SCI_COVER_CHARS_MAX}")
            if ls[2] and text_width(ls[2]) > SCI_COVER_TAG_MAX:
                errs.append(f"{tag} 第 3 行「{ls[2]}」{text_width(ls[2]):g} 字,只能是 ≤{SCI_COVER_TAG_MAX} 字的標籤(§4.2)")
            if not ls[0] or not ls[1]:
                errs.append(f"{tag} 主文字與副文字不可為空")
            elif not SCI_COVER_MAIN[0] <= text_width(ls[0]) <= SCI_COVER_MAIN[1]:
                warns.append(f"{tag} 主文字「{ls[0]}」{text_width(ls[0]):g} 字,建議 {SCI_COVER_MAIN[0]}-{SCI_COVER_MAIN[1]}")
        else:
            ws = [text_width(re.sub(r"\s", "", x)) for x in ls]
            for key, nm, x, w in zip(("main", "sub", "supp"), ("主文字", "副文字", "補充字"), ls, ws):
                lo, hi = COVER_LINE_W[key]
                if not x:
                    errs.append(f"{tag} {nm}不可為空(兩方案都固定三行)")
                elif not lo <= w <= hi:
                    errs.append(f"{tag} {nm}「{x}」{w:g} 字,需 {lo}-{hi}")
            if sum(ws) > COVER_TOTAL_MAX:
                errs.append(f"{tag} 三行合計 {sum(ws):g} 字(半形 0.5),超過 {COVER_TOTAL_MAX}")
            if subj and not any(w in ls[0] or w in ls[1] for w in subj):
                errs.append(f"{tag} 主文字與副文字都沒有主體名")
            if kuang and not any(w in ls[1] for w in ATTACK_WORDS):
                warns.append(f"{tag} 副文字沒有攻擊詞")
        if any(RE_QMARK.search(x) for x in ls):
            errs.append(f"{tag} 封面字含問號(§4 不用問號)")
        cols = p.get("colors")
        if cols:
            for c in cols:
                nm, _, code = str(c).partition(" ")
                if PALETTE.get(nm) != code.upper():
                    errs.append(f"{tag} 顏色「{c}」不在色票")
            used = [c for c, x in zip(cols, ls) if x] if len(cols) == len(ls) else list(cols)
            if len(set(used)) < len(used):
                warns.append(f"{tag} 各行顏色有重複(§4 各行不同色)")
    if thumbs and not sci:
        for p in thumbs:
            c, pl = p.get("composition"), str(p.get("plan"))
            if pl in ("1", "3") and c not in PLAN1_COMPOSITIONS:
                errs.append(f"封面方案{pl} composition 需為 {'/'.join(sorted(PLAN1_COMPOSITIONS))},目前 {c}")
            elif pl == "2" and c != PLAN2_COMPOSITION:
                errs.append(f"封面方案2 composition 需為 {PLAN2_COMPOSITION},目前 {c}")
        by = {str(p.get("plan")): [str(x).strip() for x in p.get("lines", [])] for p in thumbs}
        if len(by.get("1", [])) == 3 and len(by.get("3", [])) == 3:
            for i, nm in ((1, "副文字"), (2, "補充字")):
                if by["1"][i] and by["1"][i] == by["3"][i]:
                    errs.append(f"封面方案3 {nm}「{by['3'][i]}」跟方案1 相同(方案3 要不同的文字內容)")
        # 方案3 切角可跟方案1 相同(使用者 2026-10-17),只查方案1、2
        ang = [p["angle"] for p in thumbs if p.get("angle") and str(p.get("plan")) != "3"]
        if len(ang) != len(set(ang)):
            warns.append(f"封面方案切角有重複:{'/'.join(ang)}")
        # 封面三行不與同號標題用同一組字句(主體名除外;第 N 個標題配方案 N,4_交付發片 §3.4、§4.2)
        for p in thumbs:
            pl = str(p.get("plan"))
            if pl not in COVER_PLANS or len(titles) < int(pl):
                continue
            t = titles[int(pl) - 1].get("text", "")
            for nm, x in zip(("主文字", "副文字", "補充字"), p.get("lines", [])):
                common = longest_common(strip_subject(str(x), subj), strip_subject(t, subj))
                if text_width(common) >= COVER_TITLE_DUP_MIN:
                    warns.append(f"封面方案{pl} {nm}「{str(x).strip()}」與標題{pl}重複字句「{common}」(封面三行不與同號標題同組字句,§4.2)")
    return errs, warns


# ---- 負面判語 14 天重複(channel\規則\4_交付發片.md §3.3)----
# 同一負面判語 14 天內同頻道最多 1 支標題、1 張封面;對照 Youtube AD 頻道匯出 channel_latest.json(只讀)同 slot 近 14 天的標題。
NEG_PHRASES = ["吃相難看", "吃相太難看", "盤子", "雙標", "翻車", "割韭菜", "背刺", "打臉", "破防", "自殺式", "下架"]
NEG_DAYS = 14
CHANNEL_SLOT = {"ChannelA": "", "ChannelB": "c"}  # own_video.slot;第三頻道('d')的 spec 頻道名不固定,不在表內就略過


def check_neg_repeat(spec, tag):
    """回傳 (errs, warns)。本片標題/封面字含判語、且近 14 天同 slot 其他片標題含同一判語 → 錯誤。"""
    errs, warns = [], []
    slot = CHANNEL_SLOT.get(spec.get("channel"))
    if slot is None:
        return errs, warns
    pkg = spec.get("package") or {}
    mine = [(f"標題{i}", ti.get("text", "")) for i, ti in enumerate(pkg.get("titles", []), 1)]
    mine += [(f"封面方案{p.get('plan', '?')}", " ".join(str(x) for x in p.get("lines", []))) for p in pkg.get("thumbs", [])]
    hit = [(w, where) for where, t in mine for w in NEG_PHRASES if w in t]
    if not hit:
        return errs, warns
    try:
        # 讀 Youtube AD 頻道匯出 channel_latest.json(該 slot 的 videos,含非自製;不開 own.db)
        data = json.loads(paths.ytad_channel_export_latest().read_text(encoding="utf-8"))
        rows = [(v.get("title"), v.get("published_at")) for ch in data.get("channels", []) if ch.get("slot") == slot
                for v in ch.get("videos", []) if v.get("tag") != tag]
    except Exception as e:  # noqa: BLE001
        warns.append(f"無法讀 channel_latest.json,略過判語檢查({type(e).__name__})")
        return errs, warns
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEG_DAYS)
    recent = []
    for title, pub in rows:
        try:
            if datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(timezone.utc) >= cutoff:
                recent.append((title or "", pub[:10]))
        except (ValueError, AttributeError):
            continue
    for w, where in dict.fromkeys(hit):
        for title, day in sorted(recent, key=lambda x: x[1], reverse=True):
            if w in title:
                errs.append(f"{where}含判語「{w}」,近 {NEG_DAYS} 天同頻道已用過:{day}《{title}》(§3.1 同判語最多 1 支標題、1 張封面)")
    return errs, warns


# 數字句可接受的畫面:這些 anim 類型本身就把數字放大秀出來
NUM_ANIMS = ("num", "bars", "cols", "share", "timeline", "span")


def anim_shows_numbers(ln):
    """list/versus/flow 等文字型 anim:句中的阿拉伯數字全都出現在該 anim 的欄位文字裡 = 數字有秀在畫面上。"""
    a = ln.get("anim")
    toks = re.findall(r"\d[\d,\.]*\d|\d", ln["text"])
    if not isinstance(a, dict) or not toks:
        return False
    blob = json.dumps(a, ensure_ascii=False).replace(",", "")
    return all(t.replace(",", "") in blob for t in toks)


def check_visuals(spec, lines):
    """回傳 (errs, warns, custom_ratio)。畫面 = script 欄位 + spec.visual_plan(visual_suggest.line_visual)。"""
    import visual_suggest as vs  # 延遲匯入:visual_suggest 反過來匯入本模組
    plan = spec.get("visual_plan") or {}
    errs, warns, custom = [], [], 0
    for i, ln in enumerate(lines, 1):
        d = vs.line_visual(ln, vs._plan_get(plan, i))
        k = d["kind"]
        if d["overlay"]:
            errs.append(f"句{i} 素材畫面疊動畫(anim 同句又帶 v/img/shots/quote/compare):{ln['text'][:20]}")
        if k.startswith(("anim", "quote")):
            custom += 1
        if has_data_number(ln["text"]):
            ok = (k.startswith("anim:") and (k[5:] in NUM_ANIMS or anim_shows_numbers(ln))) or d["card"] or k in ("quote", "compare")                 or (k == "shot" and d["hl"])
            if not ok:
                warns.append(f"句{i} 數字句沒數字畫面(目前 {vs.describe(d)}):{ln['text'][:20]}")
    return errs, warns, (custom / len(lines) if lines else 0)


def table(spec, lines, custom_ratio=None):
    tg, rows = spec.get("targets", {}), []
    lens = [len(l["text"]) for l in lines]
    total = sum(lens)
    est = total / CPS

    def row(name, target, actual, ok):
        rows.append((name, target, actual, "ok" if ok is True else ("警告" if ok is False else "—")))

    lo, hi = tg.get("len_s", [None, None]) if tg.get("len_s") else (None, None)
    if lo is not None:
        row("估計片長", f"{lo}-{hi}s", f"{est:.0f}s({total}字)", lo <= est <= hi)
    jl, jb = spec.get("judgment_line"), tg.get("judgment_by_s")
    if jl and jb and 1 <= jl <= len(lines):
        t = sum(lens[:jl]) / CPS
        row("判斷句秒數", f"句{jl} ≤{jb}s", f"約{t:.0f}s", t <= jb)
    elif jb:
        row("判斷句秒數", f"≤{jb}s", "未指定 judgment_line", None)
    secs = spec.get("sections", [])
    if tg.get("topics"):
        nt = sum(1 for s in secs if s.get("role") == "topic")
        a, b = tg["topics"]
        row("話題數", f"{a}-{b}", str(nt), a <= nt <= b)
    if tg.get("bridge_min") is not None:
        br = sum(sum(lens[s["lines"][0] - 1:s["lines"][1]]) for s in secs
                 if s.get("bridge") and 1 <= s["lines"][0] <= s["lines"][1] <= len(lines))
        r = br / total if total else 0
        row("橋接比例(字數)", f"≥{tg['bridge_min']:.2f}", f"{r:.2f}", r >= tg["bridge_min"])
    if tg.get("custom_visual_min") is not None and custom_ratio is not None:
        r = custom_ratio
        row("自製畫面比例(句數)", f"≥{tg['custom_visual_min']:.2f}", f"{r:.2f}", r >= tg["custom_visual_min"])
    return rows


# ---- 封面人像跨片重複檢查(channel\規則\4_交付發片.md §4.3)----
# 讀說明檔「發片資料」的 方案1/2/3 段(主體/場景/視覺構圖 行),用關鍵字抽六格,比對 channel\cover_persona_log.jsonl。
PERSONA_LOG = paths.ROOT / "channel" / "cover_persona_log.jsonl"
COVERS_DIR = paths.yt_ad_root() / "data" / "covers"  # Youtube AD 封面圖資料夾(只讀,不可寫入)
PERSONA_CELLS = ("gender", "age", "hair", "outfit", "scene", "gesture")
CELL_NAME = {"gender": "性別", "age": "年齡層", "hair": "髮型", "outfit": "服裝", "scene": "場景", "gesture": "手勢"}
PERSONA_RECENT, GESTURE_RECENT, SCENE_RECENT, SAME_CELLS_MAX = 10, 3, 2, 3
PLAN1_RECENT, PLAN1_ORIG_WARN = 5, 2
SAME_NOTE_DIFF_MIN = 4
_CN_DEC = {"1": "十", "2": "二十", "3": "三十", "4": "四十", "5": "五十"}
# (正規表示式, 正規值) 依序;取文字中位置最前的命中(髮型/服裝/手勢),場景也同
_COLOR_RE = "[黑白灰紅藍綠黃粉紫]"
HAIR_PAT = [(r"馬尾", "馬尾"), (r"平頭", "平頭"), (r"中分", "中分"), (r"[捲卷]髮", "捲髮"), (r"鮑伯", "短鮑伯"),
            (r"染(?:金|紅|黃|成金|成紅)|金髮|紅髮", "染金或染紅"), (r"毛帽|棒球帽|鴨舌帽|戴帽", "戴毛帽或棒球帽"),
            (r"短黑髮|黑短髮|黑色短髮|黑色?短髮", "短黑髮"), (r"短髮", "短髮")]
OUTFIT_PAT = [(r"格子襯衫|格紋襯衫", "格子襯衫"), (r"襯衫", "襯衫"), (r"西裝", "西裝外套"), (r"運動外套", "運動外套"),
              (r"背心", "背心"), (r"睡衣", "睡衣")]
SCENE_PAT = [(r"電競房|電競室|電競椅", "電競房"), (r"客廳|沙發", "客廳沙發"), (r"網咖", "網咖"), (r"便利商店|超商|便利店", "便利商店"),
             (r"捷運", "捷運車廂"), (r"辦公室|工位", "辦公室工位"), (r"臥室|床上", "臥室床上"),
             (r"遊戲展|展會|展場", "遊戲展會場"), (r"賣場|貨架", "主機賣場貨架前")]
GESTURE_PAT = [(r"指[著向]?鏡頭", "食指指鏡頭"), (r"拍桌|拍打桌", "拍桌"), (r"揉爛[^,，;；]{0,6}收據", "揉爛收據"),
               (r"倒讚|拇指(?:向|朝)下", "倒讚"), (r"抱頭|抱住頭", "雙手抱頭"), (r"比叉|打叉|比\s?[xX]", "雙手比叉"),
               (r"舉[^,，;；。]{0,8}(?:臉旁|臉頰旁|臉邊)", "舉起衝突物到臉旁"), (r"攤手|攤開|[兩雙]手一攤", "攤手")]
PLAN_COLORS = ("黑紅", "黑黃", "黑金", "藍金", "紫粉")
RE_PLAN_HEAD = re.compile(r"^\s*方案\s*([123])\s*$")
RE_FIELD = re.compile(r"^\s*(視覺構圖|場景|主體)\s*[：:]\s*(.*)$")


def _first(pats, *texts):
    """依序在各段文字找,取第一段有命中者中位置最前的正規值;都沒有 None。"""
    for t in texts:
        best = None
        for rx, val in pats:
            m = re.search(rx, t or "")
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), val)
        if best:
            return best[1]
    return None


def _outfit(t):
    if not t:
        return None
    m = re.search(rf"(?:({_COLOR_RE})色?(?:的)?)?(?:連帽|帽[Tt踢衫])", t)
    if m:
        return (m.group(1) or "") + "帽T"
    m = re.search(rf"({_COLOR_RE})色?(?:的)?[Tt](?:恤|shirt)?", t)
    if m:
        return m.group(1) + "T"
    if re.search(r"T恤|短袖", t):
        return "T恤"
    return _first(OUTFIT_PAT, t)


def _age(t):
    m = re.search(r"(十|二十|三十|四十|五十|[1-5]0)\s*(?:多|幾|出頭|來)?\s*歲", t or "")
    if not m:
        return None
    d = m.group(1)
    return _CN_DEC.get(d[0], d) + "多歲" if d[0].isdigit() else d + "多歲"


def _gender(t):
    m = re.search(r"([男女])(?:性|生|子|人|孩|玩家|戰士)", t or "")
    return m.group(1) if m else None


def parse_notes_plans(text):
    """回傳 {'1': {field: 行文字}, ...};只讀 方案N 單獨一行起到下一個方案/區塊結尾。"""
    plans, cur = {}, None
    for ln in text.splitlines():
        m = RE_PLAN_HEAD.match(ln)
        if m:
            cur = plans.setdefault(m.group(1), {})
            continue
        if cur is None:
            continue
        if ln.strip().startswith("```") or ln.lstrip().startswith("【"):
            cur = None
            continue
        f = RE_FIELD.match(ln)
        if f and f.group(1) not in cur:
            cur[f.group(1)] = f.group(2).strip()
    return plans


def extract_persona(fields):
    """從 主體/場景/視覺構圖 抽 kind 與六格、色彩方向;抽不到的格 None。"""
    subj, scene_t, comp = fields.get("主體", ""), fields.get("場景", ""), fields.get("視覺構圖", "")
    all_t = subj + "\n" + comp
    kind = "原創玩家" if re.search(r"虛構|原創玩家", all_t) else "角色"
    color = next((c for c in PLAN_COLORS if c in comp), None)
    if color is None:
        m = re.search(r"字[,，]\s*([^,，。、;；\s]{2})[。,，]", comp)
        color = m.group(1) if m else None
    return {"kind": kind, "gender": _gender(subj) or _gender(comp), "age": _age(subj) or _age(comp),
            "hair": _first(HAIR_PAT, subj), "outfit": _outfit(subj),
            "scene": _first(SCENE_PAT, scene_t, comp, subj), "gesture": _first(GESTURE_PAT, subj, comp), "color": color}


def load_persona_log():
    rows = []
    if PERSONA_LOG.exists():
        for ln in PERSONA_LOG.read_text(encoding="utf-8-sig").splitlines():
            if ln.strip():
                try:
                    rows.append(json.loads(ln))
                except ValueError:
                    pass
    return rows


def _same(a, b):
    return a is not None and a == b


def check_persona(tag, notes_path):
    """回傳 (errs, warns, personas);personas = {plan: 抽取結果}。"""
    text = Path(notes_path).read_text(encoding="utf-8-sig")
    plans = parse_notes_plans(text)
    per = {p: extract_persona(f) for p, f in plans.items()}
    errs, warns = [], []
    if "1" not in per or "3" not in per:
        warns.append(f"說明檔找不到 {'、'.join('方案' + p for p in ('1', '3') if p not in per)}(人像檢查略過該方案)")
    log = [r for r in load_persona_log() if r.get("tag") != tag]
    orig = [r for r in log if r.get("kind") == "原創玩家"]
    recent = orig[-PERSONA_RECENT:]
    for p in ("1", "3"):
        d = per.get(p)
        if not d or d["kind"] != "原創玩家":
            continue
        pn = f"方案{p}"
        miss = [CELL_NAME[c] for c in PERSONA_CELLS if d[c] is None]
        if miss:
            warns.append(f"{pn} 主體描述缺 {'、'.join(miss)},SOP §4 六格要寫明")
        for r in recent:
            same = [c for c in PERSONA_CELLS if _same(d[c], r.get(c))]
            if len(same) >= SAME_CELLS_MAX:
                errs.append(f"{pn} 與 {r.get('tag')} 方案{r.get('plan')} 六格相同 {len(same)} 格({'、'.join(CELL_NAME[c] + ':' + d[c] for c in same)}),請換人物")
        g = [r for r in orig[-GESTURE_RECENT:] if _same(d["gesture"], r.get("gesture"))]
        if g:
            errs.append(f"{pn} 手勢「{d['gesture']}」與最近 {GESTURE_RECENT} 筆相同({'、'.join(r.get('tag', '?') for r in g)})")
        s = [r for r in orig[-SCENE_RECENT:] if _same(d["scene"], r.get("scene"))]
        if s:
            errs.append(f"{pn} 場景「{d['scene']}」與最近 {SCENE_RECENT} 筆相同({'、'.join(r.get('tag', '?') for r in s)})")
    d1 = per.get("1")
    if d1 and d1["kind"] == "原創玩家":
        p1 = [r for r in log if str(r.get("plan")) == "1"][-PLAN1_RECENT:]
        if sum(1 for r in p1 if r.get("kind") == "原創玩家") >= PLAN1_ORIG_WARN:
            warns.append(f"最近 {PLAN1_RECENT} 筆方案1 有 {sum(1 for r in p1 if r.get('kind') == '原創玩家')} 筆是原創玩家,優先用本作不戴頭盔的角色")
    d3 = per.get("3")
    if d1 and d3 and d1["kind"] == d3["kind"] == "原創玩家":
        diff = sum(1 for c in PERSONA_CELLS if d1[c] is not None and d3[c] is not None and d1[c] != d3[c])
        if diff < SAME_NOTE_DIFF_MIN:
            errs.append(f"方案1、3 都是原創玩家但六格只有 {diff} 格不同(至少 {SAME_NOTE_DIFF_MIN})")
    return errs, warns, per


def record_persona(tag, notes_path, personas):
    """方案1、3 各寫一筆;同 tag+plan 已存在就覆寫那一行(不重複)。"""
    import datetime
    new = {}
    for p in ("1", "3"):
        d = personas.get(p)
        if d:
            new[p] = {"date": datetime.date.today().isoformat(), "tag": tag, "plan": p, "kind": d["kind"],
                      **{c: d[c] for c in PERSONA_CELLS}, "color": d["color"], "note": Path(notes_path).name}
    out = []
    old = PERSONA_LOG.read_text(encoding="utf-8-sig").splitlines() if PERSONA_LOG.exists() else []
    for ln in old:
        try:
            r = json.loads(ln)
        except ValueError:
            out.append(ln)
            continue
        p = str(r.get("plan"))
        if r.get("tag") == tag and p in new:
            if new[p] is not None:
                out.append(json.dumps(new[p], ensure_ascii=False))
                new[p] = None
            continue  # 重複的同 tag+plan 行丟掉
        out.append(ln)
    out += [json.dumps(v, ensure_ascii=False) for v in new.values() if v is not None]
    PERSONA_LOG.write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(out)


def recent_sheet(new_img, n=8, cols=3, cell=(480, 270)):
    """最近 n 張 Youtube AD 方案1 底圖(只讀)加新圖拼成 contact sheet,新圖第一格紅框;回傳輸出路徑。"""
    from PIL import Image, ImageDraw, ImageOps
    olds = sorted(COVERS_DIR.glob("*/plan1_doubao.png"), key=lambda p: p.stat().st_mtime, reverse=True)[:n]
    imgs = [Path(new_img)] + olds
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell[0], rows * cell[1]), (20, 20, 20))
    for i, p in enumerate(imgs):
        with Image.open(p) as im:
            t = ImageOps.fit(im.convert("RGB"), cell)
        if i == 0:
            ImageDraw.Draw(t).rectangle([0, 0, cell[0] - 1, cell[1] - 1], outline=(255, 0, 0), width=8)
        sheet.paste(t, ((i % cols) * cell[0], (i // cols) * cell[1]))
    out = paths.TMP / "cover_recent_sheet.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out, sheet.size


def run_persona(a):
    errs, warns, per = check_persona(a.tag, a.notes)
    print(f"spec_check 人像 {a.tag}: {Path(a.notes).name}")
    for p in sorted(per):
        d = per[p]
        print(f"  方案{p} {d['kind']}  " + " ".join(f"{CELL_NAME[c]}={d[c]}" for c in PERSONA_CELLS) + f"  色={d['color']}")
    print(f"警告 {len(warns)} 項、錯誤 {len(errs)} 項")
    for w in warns:
        print("  警告:" + w)
    for e in errs:
        print("  錯誤:" + e)
    return errs, per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag")
    ap.add_argument("--spec", help="指定 spec.json 路徑(預設 projects/<tag>/spec.json)")
    ap.add_argument("--notes", help="說明檔 .md:只檢查封面人像跨片重複(方案1/3 對 channel\\cover_persona_log.jsonl)")
    ap.add_argument("--record", action="store_true", help="把 --notes 的方案1、3 寫進 cover_persona_log.jsonl(需 --tag)")
    ap.add_argument("--recent-sheet", metavar="新圖", help="最近 8 張 Youtube AD 方案1 底圖加新圖拼 tmp\\cover_recent_sheet.jpg")
    a = ap.parse_args()
    if a.recent_sheet:
        out, size = recent_sheet(a.recent_sheet)
        print(f"{out} ({size[0]}x{size[1]})")
        if not (a.tag or a.notes):
            return
    if a.record:
        if not (a.tag and a.notes):
            ap.error("--record 需要 --tag 與 --notes")
        per = {p: extract_persona(f) for p, f in parse_notes_plans(Path(a.notes).read_text(encoding="utf-8-sig")).items()}
        print(f"已記錄 {a.tag}(方案{'、'.join(p for p in ('1', '3') if p in per)}),{PERSONA_LOG.name} 共 {record_persona(a.tag, a.notes, per)} 行")
        return
    if a.notes:
        if not a.tag:
            ap.error("--notes 需要 --tag(自己不跟自己比)")
        errs, _ = run_persona(a)
        sys.exit(1 if errs else 0)
    if not a.tag:
        ap.error("需要 --tag")
    sp = Path(a.spec) if a.spec else paths.PROJECTS / a.tag / "spec.json"
    spec = json.loads(sp.read_text(encoding="utf-8-sig"))
    lines = load_lines(a.tag)
    skip_cover = not spec.get("facts") and facts_md_exists(a.tag)
    errs = check(spec, lines, skip_fact_cover=skip_cover)
    ve, vw, custom = check_visuals(spec, lines)
    errs += ve
    print(f"spec_check {a.tag}: 旁白 {len(lines)} 句、fact {len(spec.get('facts', []))} 筆")
    if skip_cover:
        print("  事實覆蓋改由 facts_check 檢查(spec.json 無 facts,projects/%s/facts*.md 存在)" % a.tag)
    rows = table(spec, lines, custom)
    for name, target, actual, flag in rows:
        print(f"  {name:<14}{target:<16}{actual:<24}{flag}")
    pw = list(vw)
    if package_empty(spec.get("package") or {}):
        print("  package        無 package,略過")
    else:
        pe, pw0 = check_package(spec)
        ne, nw = check_neg_repeat(spec, a.tag)
        pw += pw0 + nw
        errs += pe + ne
        pe = pe + ne
        print(f"  package        標題 {len((spec['package']).get('titles', []))}、封面 {len((spec['package']).get('thumbs', []))}  錯誤 {len(pe)}、警告 {len(pw)}")
    warns = sum(1 for r in rows if r[3] == "警告") + len(pw)
    print(f"警告 {warns} 項、錯誤 {len(errs)} 項")
    for w in pw[:12]:
        print("  警告:" + w)
    if len(pw) > 12:
        print(f"  …另 {len(pw) - 12} 項警告")
    for e in errs[:20]:
        print("  錯誤:" + e)
    if len(errs) > 20:
        print(f"  …另 {len(errs) - 20} 項")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
