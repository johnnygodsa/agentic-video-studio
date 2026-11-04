#!/usr/bin/env python3
r"""文案(script.txt)轉 build.py 用的 script.json。

用法: python -X utf8 pipeline/script_txt2json.py re9/script.txt [re9/script.json] [--img-prefix re9_]

格式:
  @title 標題
  @say 原字=唸法            全域替換表(依檔內順序套用);套用後與 text 不同才寫入該句 say
  @json {…}                 併入輸出 JSON 頂層(例如 timeline)
  @def quote:id={…}         定義引言卡 {text, src[, img]};資料行標籤寫 quote:id
  @def cmp:id={…}           定義左右對比 {left:{img,label}, right:{img,label}};資料行標籤寫 cmp:id
  @def anim:名稱={…}        定義動畫(不含 step);句子行尾寫 ` ;; anim:名稱#步驟` 展開成 {"anim": {…定義…, "step": 步驟}}
                            (#步驟 省略就不加 step;#後是整數,或 all / title / q 等字串;名稱不存在報錯)。
                            也可寫 ` ;; {"anim": "名稱#2"}`(anim 值為字串時同樣展開)
  @spoiler [秒數|]文字      開場劇透警告:script.json 頂層 "spoiler": {"text": "…", "dur": 秒數(預設 6.0)}。
                            文字以 | 分兩行(第一行紅色標題,第二行白色說明),例:@spoiler 劇透警告|本片含…;
                            只有一段(不含 | )時第一行用「劇透警告」;開頭是數字加 | 時為秒數,例:@spoiler 8|劇透警告|本片含…
  # 段落名 [;; {json}]      開新 section,{json} 併入該 section(例如 {"trans":"glitch"})。
                            沒有任何資料行的 # 行(含以「格式:」開頭者)視為說明,略過
  標籤|字幕文字 [;; {json}]  {json} 併入該句(hl / emo / anim / focus / fx / shots / note / f …;f = 事實核對表列 ["F12","F13"],原樣帶到 script.json,給 facts_check 用)
標籤:
  xxx          -> {"v": "xxx"}
  img:name     -> {"v": "img", "img": "re9_name"}
  card:文字    -> 沿用上一句(同段落,沒有就用下一句)的 v/img,加 {"card": {"big", "small"}};
                  文字以空白分段,第一段為 big,其餘合併為 small
                  行尾 ;; {"v": "標籤"} 可改指定卡片底下的影片標籤(此時不沿用鄰句的圖)
  quote:id     -> {"quote": {text, src}};def 內有 img 時同時寫入該句 img(引言卡的模糊底圖)
  cmp:id       -> {"compare": {…}}
  anim         -> 不輸出 v;該句是獨立的動畫鏡頭,由行尾 anim 欄位指定(timeline / emoji / puzzle / stamp / span / bars / list / versus / flow / cols / share / num / line / table / kpi;欄位檢查在 build.parse_anim)
                  逐步類型(list / bars / versus / flow)連續句要寫成同一個鏡頭時,每句的 anim 欄位(除 step)必須完全相同;
                  timeline 的節點寫在 @json {"timeline":{"points":[[日期,說明],…]}},各句只寫 {"type":"timeline","step":n}
                  versus: {title, left:{head,lines[1..2],mark?:yes|no}, right:{…}, step:0|1|2}(0 標題與欄標題 / 1 左欄 / 2 右欄)
                  flow:   {title, nodes:[2..4 個字串,可含換行], step:n}(step n = 顯示到第 n 個節點,箭頭先畫再出節點)
                  動畫每一步在該句開頭開始出現;最後一步顯示完後須停留 1.5 秒(build 會在該鏡頭最後一句後補靜音)
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import kit as KIT

IMG_PREFIX = "re9_"
TAIL_WARN = "了啊欸嗎呢吧"
TAIL_STRIP = "。,.!?!?、;;:: …—-」』)）\"'"
EXTRA_SEP = " ;; "


def _json_obj(s, no, what):
    try:
        d = json.loads(s)
    except ValueError as e:
        sys.exit(f"第 {no} 行 {what} 的 JSON 解析失敗: {e}\n  {s}")
    if not isinstance(d, dict):
        sys.exit(f"第 {no} 行 {what} 必須是 JSON 物件: {s}")
    return d


def split_extra(s, no, strict):
    """拆出行尾「 ;; {json}」。strict=False(段落行)時,解析不了就當作沒有額外欄位。"""
    head, sep, tail = s.rpartition(EXTRA_SEP)
    if sep and strict and re.fullmatch(r"anim:[^\s#{}]+(#\S+)?", tail.strip()):
        return head.rstrip(), {"anim": tail.strip()[5:]}  # 簡寫:名稱#步驟,build_lines 展開
    if not sep or not tail.lstrip().startswith("{"):
        return s, {}
    if strict:
        return head.rstrip(), _json_obj(tail.strip(), no, "行尾 ;;")
    try:
        d = json.loads(tail.strip())
    except ValueError:
        return s, {}
    return (head.rstrip(), d) if isinstance(d, dict) else (s, {})


def parse_spoiler(arg, no):
    """@spoiler [秒數|]標題|說明 或 [秒數|]文字 -> {"text": "標題|說明", "dur": 秒}。"""
    dur = 6.0
    head, sep, rest = arg.partition("|")
    if sep and re.fullmatch(r"\d+(\.\d+)?", head.strip()):
        dur, arg = float(head), rest
    arg = arg.strip()
    if not arg:
        sys.exit(f"第 {no} 行 @spoiler 缺少文字")
    return {"text": arg, "dur": dur}


def expand_anim(ref, defs, no):
    """anim 欄位為字串 '名稱#步驟' 時,展開成 @def anim:名稱 的內容加 step。"""
    name, sep, step = ref.partition("#")
    d = defs.get("anim:" + name)
    if d is None:
        sys.exit(f"第 {no} 行用到未定義的動畫 anim:{name}(缺 @def anim:{name}=…)")
    out = dict(d)
    if sep:
        out["step"] = int(step) if step.lstrip("-").isdigit() else step
    return out


def parse(src):
    title, says, sections, top, defs = "", [], [], {}, {}
    cur = None
    for no, raw in enumerate(src.splitlines(), 1):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("@title"):
            title = s[6:].strip()
        elif s.startswith("@say"):
            k, _, v = s[4:].strip().partition("=")
            if not _:
                sys.exit(f"第 {no} 行 @say 缺少 '=': {raw}")
            says.append((k.strip(), v.strip()))
        elif s.startswith("@spoiler"):
            top["spoiler"] = parse_spoiler(s[8:].strip(), no)
        elif s.startswith("@fallback"):
            k, _, v = s[9:].strip().partition("=")
            tags = [x.strip() for x in v.split(",") if x.strip()]
            if not _ or not k.strip() or not tags:
                sys.exit(f"第 {no} 行 @fallback 格式應為 @fallback 標籤=備援標籤[,備援標籤…]: {raw}")
            top.setdefault("fallback", {})[k.strip()] = tags
        elif s.startswith("@json"):
            top.update(_json_obj(s[5:].strip(), no, "@json"))
        elif s.startswith("@def"):
            k, _, v = s[4:].strip().partition("=")
            kind, c, did = k.strip().partition(":")
            if not _ or not c or kind not in ("quote", "cmp", "anim") or not did:
                sys.exit(f"第 {no} 行 @def 格式應為 @def quote:id={{…}}、@def cmp:id={{…}} 或 @def anim:名稱={{…}}: {raw}")
            defs[f"{kind}:{did}"] = _json_obj(v.strip(), no, "@def")
        elif s.startswith("@"):
            sys.exit(f"第 {no} 行不認得的指令: {raw}")
        elif s.startswith("#"):
            name, extra = split_extra(s[1:].strip(), no, strict=False)
            cur = dict(name=name, extra=extra, rows=[], no=no)
            sections.append(cur)
        else:
            body, extra = split_extra(s, no, strict=True)
            tag, sep, text = body.partition("|")
            if not sep:
                sys.exit(f"第 {no} 行缺少 '|': {raw}")
            if cur is None:
                cur = dict(name="", extra={}, rows=[], no=no)
                sections.append(cur)
            cur["rows"].append((no, tag.strip(), text.strip(), extra))
    skipped = [s for s in sections if not s["rows"]]  # 沒有資料行的 # 行 = 說明
    return title, says, [s for s in sections if s["rows"]], top, defs, skipped


def split_card(t):
    parts = t.split()
    d = {"big": parts[0] if parts else ""}
    if len(parts) > 1:
        d["small"] = " ".join(parts[1:])
    return d


def build_lines(rows, defs):
    """先處理一般標籤,再回頭補 card(需要鄰句的 v)。"""
    out = []
    for no, tag, text, extra in rows:
        if isinstance(extra.get("anim"), str):
            extra = dict(extra, anim=expand_anim(extra["anim"], defs, no))
        if "kit" in extra:   # 動態小件:單一物件也收,轉成清單;欄位錯直接擋(數量上限由 script_lint 報)
            kits = [extra["kit"]] if isinstance(extra["kit"], dict) else extra["kit"]
            errs = [e for it in kits for e in KIT.item_errors(it)] if isinstance(kits, list) else ["kit 要是清單 [ {…}, … ]"]
            if errs:
                sys.exit(f"第 {no} 行 kit 欄位錯誤:{';'.join(errs)}")
            extra = dict(extra, kit=kits)
        ln = dict(text=text)
        kind, _, arg = tag.partition(":")
        if kind == "img" and arg:
            ln.update(v="img", img=IMG_PREFIX + arg)
        elif kind == "card":
            ln["_card"] = arg
        elif kind in ("quote", "cmp"):
            d = defs.get(tag)
            if d is None:
                sys.exit(f"第 {no} 行用到未定義的 {tag}(缺 @def {tag}=…)")
            if kind == "quote":
                ln["quote"] = {k: v for k, v in d.items() if k != "img"}
                if d.get("img"):
                    ln["img"] = d["img"]
            else:
                ln["compare"] = d
        elif kind == "anim" and not arg:
            if not isinstance(extra.get("anim"), dict):
                sys.exit(f"第 {no} 行標籤 anim 但行尾沒有 anim 欄位")
        else:
            ln["v"] = tag
        ln["_extra"] = extra
        out.append(ln)

    def src(i, step):
        j = i + step
        while 0 <= j < len(out):
            if "v" in out[j]:
                return out[j]
            j += step
        return None

    for i, ln in enumerate(out):
        if "_card" in ln:
            ref = src(i, -1) or src(i, 1)
            if ref is None:
                if ln["_extra"].get("v"):   # 全段都是 anim/quote 時,行尾指定的 v 就夠了
                    continue
                sys.exit(f"找不到可沿用 v 的鄰句: {ln['text']}")
            ln["v"] = ref["v"]
            if "img" in ref:
                ln["img"] = ref["img"]
    for ln in out:
        extra = ln.pop("_extra")
        if "_card" in ln:
            ln["card"] = split_card(ln.pop("_card"))
            if extra.get("v") not in (None, "img") and "img" not in extra:
                ln.pop("img", None)  # 行尾指定了卡片底下的影片標籤:不沿用鄰句的圖
        ln.update(extra)
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    global IMG_PREFIX
    argv = sys.argv[1:]
    if "--img-prefix" in argv:  # img:name -> images/<prefix>name.png(預設 re9_;新影片用自己的前綴,例如 wow_)
        i = argv.index("--img-prefix")
        IMG_PREFIX = argv[i + 1]
        del argv[i:i + 2]
    inp = Path(argv[0])
    outp = Path(argv[1]) if len(argv) > 1 else inp.with_suffix(".json")
    title, says, sections, top, defs, skipped = parse(inp.read_text(encoding="utf-8-sig"))

    data = dict(title=title)
    data.update(top)
    data["sections"] = []
    all_lines = []
    for sec in sections:
        lines = build_lines(sec["rows"], defs)
        for ln in lines:
            say = ln["text"]
            for k, v in says:
                say = say.replace(k, v)
            if say != ln["text"]:
                ln_new = dict(text=ln["text"], say=say)
                ln_new.update({k: v for k, v in ln.items() if k != "text"})
                ln.clear()
                ln.update(ln_new)
            all_lines.append(ln)
        sd = dict(name=sec["name"])
        sd.update(sec["extra"])
        sd["lines"] = lines
        data["sections"].append(sd)
    outp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 統計
    tags = Counter()
    for sec in sections:
        for _, tag, _, _ in sec["rows"]:
            k, _, a = tag.partition(":")
            tags[k + (":*" if a else "")] += 1
    extras = Counter(k for l in all_lines for k in ("hl", "emo", "anim", "quote", "compare", "card", "focus", "shots", "kit", "f")
                     if k in l)
    print(f"輸出 {outp}")
    print(f"標題: {title}")
    print(f"段落 {len(data['sections'])}、句數 {len(all_lines)}、總字數 {sum(len(l['text']) for l in all_lines)}、"
          f"含 say 句數 {sum(1 for l in all_lines if 'say' in l)}")
    print("標籤次數:", ", ".join(f"{k}={n}" for k, n in tags.most_common()))
    print("欄位句數:", ", ".join(f"{k}={n}" for k, n in extras.most_common()))
    print("頂層欄位:", ", ".join(k for k in data if k != "sections"),
          "| 段落額外欄位:", ", ".join(f"{s['name']}={json.dumps(s['extra'], ensure_ascii=False)}"
                                 for s in sections if s["extra"]) or "無")
    for s in skipped:
        print(f"略過說明行(第 {s['no']} 行): # {s['name'][:40]}")
    unused = [k for k in defs if not any(tag == k for sec in sections for _, tag, _, _ in sec["rows"])]
    if unused:
        print("未使用的 @def:", ", ".join(unused))

    # ---- 朗讀檢查(只警告)
    warns = []
    for i, ln in enumerate(all_lines, 1):
        spoken = ln.get("say") or ln["text"]
        why = []
        if re.search(r"[A-Za-z]", spoken):
            why.append("含英文字母")
        if re.search(r"[0-9]", spoken):
            why.append("含阿拉伯數字")
        tail = spoken.rstrip(TAIL_STRIP)
        if tail and tail[-1] in TAIL_WARN:
            why.append(f"句尾「{tail[-1]}」")
        if why:
            warns.append((i, "/".join(why), spoken))
    print(f"\n朗讀警告 {len(warns)} 句:")
    for i, w, t in warns:
        print(f"  句{i} [{w}] {t}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
