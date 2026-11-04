#!/usr/bin/env python3
r"""配音前預檢(C 段開跑前;不配音、不用顯示卡、不動快取):把每句照正式流程轉成「實際送進 CosyVoice3 的文字」
(tts_script.script_lines 取 @say 後的句 -> tts_cosy_text.unsay -> tts_cosy3.engine_text),找文案上看不出來、但會讓模型吞字或唸錯的風險。
邏輯參考 KC 的 tts_precheck(2026-10-31 newton 聽審抓到的類型),依 CV 慣例重寫。

python -X utf8 pipeline\tts_precheck.py <tag>      (用 tts_env_chattts 的 python:要 torch / pypinyin / opencc;結束碼 error>0 = 1、稿不存在 = 2)
輸出:projects\<tag>\tts_precheck.json(items = 行號/句/送引擎文字/level/code/msg)+ 簡短 stdout。

error(會吞字,一定要改):
  A 重複音   送引擎文字相鄰兩個一模一樣的拼音標記(例「同一期期刊」-> [q][í][q][í],模型吞掉一個);修法:第二個換同音字 @say 同一期期刊=同一期旗刊
warn(列給寫稿者判斷,不擋):
  B 得→的    「得」被多音字規則換成「的」;句首/逗號後/接在 我你他就還也都…之後常是 děi;修法 @say 得照=[d][ěi]照
  B2 得→děi  「V得C」(解得開、看得懂)的得被標成 [d][ěi];修法 @say 解得開=解的開
  E 數字頓號 約數「兩、三點」的頓號送引擎變逗號、唸出停頓;修法 @say 兩、三=兩三
  C 多音字   讀音表/規則/@say 沒標、上下文讀音不是該字最常見讀音(pypinyin 猜),模型可能唸成常見的
  D 觀察名單 tts_precheck_watch.json(聽審實際唸錯過的字詞,遇到新的就加)
director C 段第一步呼叫(結束碼 1 -> 卡點「預檢」,reason 用 block_reason 列句);頂層只 import 標準庫,重依賴在函式內。
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paths as P  # noqa: E402

WATCH = HERE / "tts_precheck_watch.json"
SKIP_POLY = set("的了着著一不地得和呢吗嗎啊呀吧么麼个個们們子过過还還都为為")   # 虛詞另有規則/變調處理
TOKEN = re.compile(r"\[[^\[\]\s]+\]")
INITIALS = {f"[{x}]" for x in "b p m f d t n l g k h j q x zh ch sh r z c s y w".split()}
DEI_PREV = set("我你他她它們们就還还也都總总才又只先所人誰谁")   # 「X得+動詞」常是 děi(必須)
BREAKS = set(",,。!?;;:「『")
LEVEL = {"A": "error"}   # 其餘一律 warn


def out_path(tag):
    return P.PROJECTS / tag / "tts_precheck.json"


def units(engine):
    """送引擎文字切成「音節單位」:一個拼音音節(聲母標記+韻母標記,或單一韻母標記)算一個,其他每個字一個。"""
    out, i, k = [], 0, 0
    toks = [(m.start(), m.end(), m.group(0)) for m in TOKEN.finditer(engine)]
    while i < len(engine):
        if k < len(toks) and toks[k][0] == i:
            _, e0, t0 = toks[k]
            if t0 in INITIALS and k + 1 < len(toks) and toks[k + 1][0] == e0:
                out.append(t0 + toks[k + 1][2])
                i, k = toks[k + 1][1], k + 2
            else:
                out.append(t0)
                i, k = e0, k + 1
        else:
            out.append(engine[i])
            i += 1
    return out


def load_watch():
    if not WATCH.exists():
        return {}
    return {k: v for k, v in json.loads(WATCH.read_text(encoding="utf-8")).items() if not k.startswith("_")}


def _align(simp, us):
    """量測文字(簡體)位置 -> 送引擎單位索引(拼音標記組當一個字)。"""
    import difflib
    ue = [u if not u.startswith("[") else "□" for u in us]
    pos = {}
    for tg, i1, i2, j1, _j2 in difflib.SequenceMatcher(None, simp, "".join(ue), autojunk=False).get_opcodes():
        if tg in ("equal", "replace") and i2 - i1 == _j2 - j1:
            for k in range(i2 - i1):
                pos[i1 + k] = j1 + k
    return pos


def check_line(mtext, eng, watch=None):
    """單句檢查。mtext = 量測用文字(unsay 後)、eng = engine_text 結果。回傳 [(code, level, msg)]。
    B/B2/C 需要 opencc(對位用);C 另需 pypinyin;缺套件就略過該項(CLI 在 tts_env_chattts 跑,兩者都有)。"""
    hits = []
    us = units(eng)
    for a, b in zip(us, us[1:]):   # A 重複音:只抓拼音標記(疊字如「謝謝」通常沒事,不列)
        if a == b and a.startswith("["):
            hits.append(("A", "error", f"送引擎有相鄰的「{a}{b}」:拼音標記重複,模型幾乎一定吞掉一個;第二個換同音字"))
    for m in re.finditer(r"[一二兩三四五六七八九十]、[一二三四五六七八九十]", mtext):   # E 數字頓號
        hits.append(("E", "warn", f"「{m.group(0)}」的頓號會唸出停頓(約數不該斷開):@say {m.group(0)}={m.group(0).replace('、', '')}"))
    try:
        from opencc import OpenCC
        simp = OpenCC("t2s").convert(mtext)
    except ImportError:
        simp = None
    pos = _align(simp, us) if simp is not None and len(simp) == len(mtext) else {}
    for i, ch in enumerate(mtext):   # B / B2 得
        if ch != "得" or i not in pos:
            continue
        u, before = us[pos[i]], mtext[:i].rstrip()
        if u == "的":
            lead = not before or before[-1] in BREAKS
            if lead or before[-1] in DEI_PREV:   # 其他(覺得、聽得懂、跑得快)本來就唸 de
                nxt = mtext[i + 1:i + 3]
                hits.append(("B", "warn", f"「{before[-1:]}得{nxt}」送引擎變成「的{nxt}」" + ("(句首/逗號後)" if lead else "")
                             + f",很可能該唸 děi(必須);是的話 @say 得{nxt}=[d][ěi]{nxt}"))
        elif u == "[d][ěi]" and i and mtext[i - 1] not in DEI_PREV | set("己") | BREAKS:
            w = mtext[i - 1:i + 2]
            hits.append(("B2", "warn", f"「{w}」送引擎標成 děi;若是「V得C」(解得開、看得懂)該唸 de:@say {w}={w.replace('得', '的')}"))
    try:
        from pypinyin import Style, lazy_pinyin, pinyin
    except ImportError:
        pinyin = None
    if pinyin and pos:   # C 多音字
        ctx = {}   # 字位置 -> 上下文讀音(每段連續中文各自斷詞逐字對齊)
        for m in re.finditer(r"[一-鿿]+", mtext):   # 用簡體斷詞:pypinyin 的詞組表是簡體,繁體「銀行」會落到單字讀音
            for j, py in enumerate(lazy_pinyin(simp[m.start():m.end()], style=Style.TONE)):
                ctx[m.start() + j] = py
        for i, ch in enumerate(mtext):
            if not re.fullmatch(r"[一-鿿]", ch) or ch in SKIP_POLY:
                continue
            if i in pos and us[pos[i]].startswith("["):
                continue   # 讀音表/規則/@say 已標
            rs = pinyin(ch, style=Style.TONE, heteronym=True)[0]
            if len(rs) > 1 and i in ctx and ctx[i] != rs[0] and ctx[i] in rs:
                hits.append(("C", "warn", f"「{ch}」在「{mtext[max(0, i - 2):i + 3]}」:上下文應唸 {ctx[i]},常見讀音是 {rs[0]}"
                             f"(全部 {'/'.join(rs)});模型可能唸成 {rs[0]}"))
    for word, note in (watch or {}).items():   # D 觀察名單
        if word in mtext:
            hits.append(("D", "warn", f"「{word}」:{note[:120]}"))
    return hits


def check_lines(pairs, watch=None):
    """pairs = [(行號, 句文字, mtext, eng)] -> items(dict 清單,error 排前面)。"""
    items = []
    for idx, text, mtext, eng in pairs:
        for code, level, msg in check_line(mtext, eng, watch):
            items.append({"line": idx, "text": text, "engine": eng, "level": level, "code": code, "msg": msg})
    items.sort(key=lambda x: (x["level"] != "error", x["line"]))
    return items


def run(tag, write=True):
    """讀 script.txt(與 tts_script 同源)-> 檢查 -> 寫 projects\\<tag>\\tts_precheck.json。回傳報告 dict。需要 tts_env_chattts。"""
    import tts_cosy3 as T
    import tts_script as TS
    pairs = []
    for idx, (ln, say) in enumerate(TS.script_lines(tag), 1):
        mtext = T.CT.unsay(say)
        pairs.append((idx, ln["text"], mtext, T.engine_text(mtext)))
    items = check_lines(pairs, load_watch())
    rep = {"tag": tag, "lines": len(pairs), "errors": sum(i["level"] == "error" for i in items),
           "warns": sum(i["level"] == "warn" for i in items), "items": items}
    if write:
        f = out_path(tag)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def block_reason(tag, cap=800):
    """director 卡點原因:讀既有 tts_precheck.json,列 error 句(行號 + 句首 + 原因);沒有檔回 None。"""
    try:
        rep = json.loads(out_path(tag).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    errs = [i for i in rep.get("items", []) if i.get("level") == "error"]
    if not errs:
        return None
    s = f"配音前預檢 error {len(errs)} 項(會吞字,改稿或 @say 後重跑;詳見 projects\\{tag}\\tts_precheck.json):" + ";".join(
        f"第 {i['line']} 行「{i['text'][:20]}」{i['msg'][:60]}" for i in errs)
    return s if len(s) <= cap else s[:cap - 1] + "…"


def main(argv=None):
    if len(argv if argv is not None else sys.argv[1:]) != 1:
        print(__doc__.split("\n")[2], file=sys.stderr)
        return 2
    tag = (argv if argv is not None else sys.argv[1:])[0]
    try:
        rep = run(tag)
    except FileNotFoundError as e:
        print(f"{tag}:找不到稿 {e}", file=sys.stderr)
        return 2
    by = {}
    for i in rep["items"]:
        by[i["code"]] = by.get(i["code"], 0) + 1
    print(f"{tag} 配音前預檢:{rep['lines']} 句,error {rep['errors']}、warn {rep['warns']}"
          + (f"({'、'.join(f'{k} {v}' for k, v in sorted(by.items()))})" if by else "") + f" -> {out_path(tag)}")
    for i in rep["items"]:
        if i["level"] == "error":
            print(f"  ERROR 第 {i['line']} 行 {i['code']}:{i['msg']}\n    送引擎:{i['engine']}")
    return 1 if rep["errors"] else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        _s.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
