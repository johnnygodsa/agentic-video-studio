#!/usr/bin/env python3
r"""C 段 `decide` 步(PLAN_全流程優化_2026-11-05 §2 P5):唸法清單由 director 決定並登錄,主對話只在卡點接手。
規格:pipeline\docs\director_ab.md「C 段 decide」、docs\build.md 唸法清單(T5)。

流程(run):重讀詞表 → decide_list 算「未定」候選(① cosy_terms 未驗證英文詞、② cosy_pron 詞/pron_rules 規則鍵未驗證)
  → 0 條:不叫 LLM → 否則 Sonnet(agent pron-review 同型,tools 只給 Read)一次決定 → 程式寫入:
       decision(可選,只補「缺的」條目)走 pron_apply.apply(只新增);「已決」的鍵走 pron_apply.verify 寫進各檔 `_verified`
       (pron_rules 另把該規則 unverified 旗標清掉;其餘既有值不動、寫後自驗)
  → 重算,LLM 最多 2 輪;仍有未定 → Block(主對話接手)。
已決條目記在 projects\<tag>\decide_<ver>.json,重產 decide_<ver>.md 時列成「④ 已決定」,listen_page 列進優先聽(director_decided)。
不放寬:LLM 回不完整/回「未決」/寫入被拒 = 仍未定;pron_apply 不改既有條目(verify 只清 unverified 旗標與加 `_verified`)。
say_terms.json 是 ChatTTS 舊引擎表(無 _verified),不在本步範圍;預設引擎 CosyVoice3 看 cosy_terms/cosy_pron/pron_rules。
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import director_ab as AB  # noqa: E402
import paths as P  # noqa: E402
import pron_apply as PA  # noqa: E402

MAX_ROUNDS = 2          # LLM 最多兩輪;之後只重算
LOOKUP_LINES = 14       # 每個候選附的辭典行數上限
MEMORY_PER_CHAR = 6
DECISION = {**AB._DEC, "required": []}
DECIDE_SCHEMA = {"type": "object", "required": ["items"], "properties": {
    "items": AB._ARR({"src": AB._STR, "key": AB._STR, "status": AB._STR, "decision": DECISION, "basis": AB._STR},
                     ["src", "key", "status", "basis"])}}
SRC_FILE = {"cosy_terms": "cosy_terms", "cosy_pron": "cosy_pron", "pron_rules": "pron_rules"}


# ---------------------------------------------------------------- 詞表(讀目前檔案,寫入後要重讀)
def refresh_tables():
    """依 director_ab._pron_path 指的檔重設 tts_cosy_text 的詞表全域(寫入後 decide_list 才看得到新的 _verified;測試/dry-run 指到 tmp 副本)。"""
    import tts_cosy_text as CT

    def rd(name):
        return json.loads(AB._pron_path(name).read_text(encoding="utf-8"))
    p, t, raw = rd("cosy_pron.json"), rd("cosy_terms.json"), rd("pron_rules.json")
    CT.PRON, CT.PRON_VERIFIED = {k: v for k, v in p.items() if not k.startswith("_")}, set(p.get("_verified", []))
    CT.TERMS, CT.TERMS_VERIFIED, CT.DIRECT = {k: v for k, v in t.items() if not k.startswith("_")}, set(t.get("_verified", [])), list(t.get("_direct", []))
    CT.RULES_RAW = raw
    CT.RULE_CHARS, CT.RULE_WORDS, CT.RULE_REGS = CT._compile_rules(raw)
    return CT


def _lookup(q):
    try:
        import tts_moe
        return [l for l in tts_moe.lookup(q)][:LOOKUP_LINES]
    except Exception as e:  # noqa: BLE001
        return [f"(查辭典失敗:{type(e).__name__})"]


def _memory(chars):
    """pron_memory.json 裡這些字的條目(精簡);讀不到 = []。"""
    try:
        import pron_memory as PM
        rows = [e for e in PM.load()["entries"] if e.get("char") in chars and not e.get("tombstone")]
    except Exception:  # noqa: BLE001
        return []
    out, cnt = [], {}
    for e in rows:
        cnt[e["char"]] = cnt.get(e["char"], 0) + 1
        if cnt[e["char"]] <= MEMORY_PER_CHAR:
            out.append({k: e.get(k) for k in ("char", "left", "right", "py", "state", "evidence")})
    return out


def _han(s):
    return [c for c in dict.fromkeys(s) if "一" <= c <= "鿿"]


def candidates(texts):
    """未定候選 [{src, key, lines, sample, current, lookup, memory}](順序:英文 → cosy_pron → pron_rules)。"""
    import decide_list as DL
    en, pron = DL.en_undecided(texts), DL.pron_undecided(texts)
    out = []
    for w, e in en.items():
        out.append({"src": "cosy_terms", "key": w, "lines": e["lines"], "sample": e["sample"][:60],
                    "current": "直接唸英文(_direct)" if e["say"] is None else f"寫法 {e['say']}", "lookup": [], "memory": []})
    for k, e in pron.items():
        left = k.split("→", 1)[0]
        chars = _han(left)
        out.append({"src": e["src"], "key": k, "lines": e["lines"], "sample": e["sample"][:60],
                    "current": f"標注 {e.get('value')}", "lookup": _lookup(left) if chars else [], "memory": _memory(set(chars))})
    return out


# ---------------------------------------------------------------- LLM
def _prompt(tag, ver, cands, n, note=""):
    import tts_cosy_text as CT
    ver_terms = {k: CT.TERMS.get(k) for k in sorted(CT.TERMS_VERIFIED)[:15]}
    ver_pron = {k: CT.PRON.get(k) for k in sorted(CT.PRON_VERIFIED)[:10]}
    return (
        f"唸法清單決定(第 {n} 輪)|片 {tag} {ver}。以下每個候選是本片送配音文字用到、但還沒定案(不在各表 `_verified`)的唸法。"
        "你是唸法決定者:逐條判斷「現有登錄」對 CosyVoice3 配音是否正確、合台灣習慣;正確 = 已決,不確定或有錯 = 未決。\n"
        "判斷依據只用下面附的資料(辭典 lookup = 教育部審訂表 + 重編國語辭典;pron_memory 實測記憶;已驗證條目示範寫法),不要 Bash、不要自己查網路。\n"
        "規則:\n"
        "- src=cosy_terms(英文詞):現有「寫法」要讓引擎唸出台灣慣用唸法(字母縮寫逐唸或慣用中文唸法;直接唸英文=該詞英文本來就唸得出來,例 Switch)。"
        "使用者已定案:英文人名只唸姓氏音譯、廠商唸中文名(EA 藝電、BioWare 生軟);無台灣譯名用大陸通用名。\n"
        "- src=cosy_pron(整詞標注)與 pron_rules(規則鍵「詞→標注」「字→標注」):標注讀音必須等於這句語境該唸的台灣讀音(教育部審訂表為準;"
        "使用者已定案:血=xiě、和=hé、關卡=kǎ、主角/配角/角色唸 jiǎo、著 助詞用「着」、輕聲不用拼音 token 改同音字)。lookup 對不上或語境不確定 → 未決。\n"
        "- 「已決」= 現有登錄正確(basis 寫依據一句,引 lookup/記憶/慣例)。現有登錄錯、或你沒把握 → 「未決」並在 basis 寫原因(程式不能改既有條目,由主對話接手;不要硬判已決)。\n"
        "- decision 預設給 {};只在「還缺一筆互補條目」時才給(格式見下),且 decision 只新增、驗 py token,錯的退回。\n"
        f"{AB.PRON3_FORMAT.split('items 每筆')[0]}"
        "回傳 JSON:items 每個候選一筆 {src, key, status(已決|未決), decision, basis};src、key 照抄候選。\n"
        + (f"{note}\n" if note else "")
        + f"已驗證條目示範(寫法參考):cosy_terms {json.dumps(ver_terms, ensure_ascii=False)};cosy_pron {json.dumps(ver_pron, ensure_ascii=False)}\n"
        f"候選:\n{json.dumps(cands, ensure_ascii=False)}")


def _check(res):
    bad = []
    for i in (res.data or {}).get("items") or []:
        if i.get("status") not in ("已決", "未決"):
            bad.append(f"{i.get('key')} status 只能是 已決/未決")
        d = i.get("decision") or {}
        if d and d.get("kind") not in ("rule", "word", "term", "sub_word", "backlog"):
            bad.append(f"{i.get('key')} decision.kind 不認得:{d.get('kind')}")
    return "；".join(bad[:5]) or None


def _review(tag, ver, cands, n, note=""):
    r = AB._need(AB._llm(tag, f"decide_r{n}", _prompt(tag, ver, cands, n, note), agent="pron-review", model="sonnet", tools=("Read",),
                         schema=DECIDE_SCHEMA, seg="C", validate=_check), "decide(pron-review)")
    return (r.data or {}).get("items") or []


# ---------------------------------------------------------------- 寫入
def _new_keys(d):
    """decision 新增的條目對應的 verify 鍵 [(file, key)]。"""
    k = d.get("kind")
    if k == "term" and d.get("word"):
        return [("cosy_terms", d["word"])]
    if k == "word" and d.get("word"):
        return [("cosy_pron", d["word"])]
    if k == "rule" and d.get("char") and d.get("py"):
        return [("pron_rules", f"{w}→{d['py']}") for w in (d.get("words") or [])] or [("pron_rules", f"{d['char']}→{d['py']}")]
    return []


def _soft(e):
    return re.search(r"已存在|已有", e)


def _apply(tag, cands, items):
    """逐條套 LLM 的決定。回傳 (嘗試登錄的 [(候選, 回覆)], 錯誤 list)。只處理「已決」;decision 先 pron_apply.apply(只新增),
    verify 鍵最後一次寫(pron_apply.verify)。是否真的定案由呼叫端重算候選判斷(寫入被拒的條目仍在候選裡)。"""
    by = {(c["src"], c["key"]): c for c in cands}
    by_key = {}
    for c in cands:
        by_key.setdefault(c["key"], []).append(c)
    tried, flat, errs, seen = [], [], [], set()
    for it in items:
        c = by.get((it.get("src"), it.get("key"))) or (by_key[it["key"]][0] if len(by_key.get(it.get("key"), [])) == 1 else None)
        if not c or (c["src"], c["key"]) in seen or it.get("status") != "已決":
            continue
        seen.add((c["src"], c["key"]))
        note = (it.get("basis") or "")[:80]
        ents = [(c["src"], c["key"])]
        d = it.get("decision") or {}
        if d:
            res = PA.apply([d], tag)
            hard = [e for e in res["errors"] if not _soft(e)]
            if hard:
                errs.append(f"{c['key']}:decision 被拒:{'；'.join(hard)}")
                continue
            ents += _new_keys(d)
        tried.append((c, it))
        flat += [{"file": f, "key": k, "note": note} for f, k in ents]
    if flat:
        res = PA.verify(flat, tag)
        errs += res["errors"]
    return tried, errs


def _record(c, it, rnd):
    return {"src": c["src"], "key": c["key"], "lines": c["lines"], "sample": c["sample"], "current": c["current"],
            "basis": (it.get("basis") or "")[:160], "round": rnd, "at": date.today().isoformat()}


def _save(tag, ver, recs):
    """projects\\<tag>\\decide_<ver>.json:同 (src,key) 後者蓋前者。"""
    import decide_list as DL
    f = DL.decided_path(tag, ver)
    old = {(x.get("src"), x.get("key")): x for x in DL.load_decided(tag, ver)}
    for r in recs:
        old[(r["src"], r["key"])] = r
    f.parent.mkdir(parents=True, exist_ok=True)
    AB._write_json(f, {"tag": tag, "ver": ver, "items": list(old.values())})


# ---------------------------------------------------------------- 主流程
def run(tag, ver, texts=None):
    """見檔頭。回傳 {before, rounds, decided, left};未定仍在 → raise AB.Block。"""
    import decide_list as DL
    import tts_terms
    texts = tts_terms.script_texts(tag) if texts is None else texts
    refresh_tables()
    c = candidates(texts)
    first, decided, calls, note = len(c), [], 0, ""
    for n in range(1, MAX_ROUNDS + 1):
        if not c:
            break
        calls += 1
        items = _review(tag, ver, c, n, note)
        tried, errs = _apply(tag, c, items)
        refresh_tables()
        left = candidates(texts)
        still = {(x["src"], x["key"]) for x in left}
        recs = [_record(cc, it, n) for cc, it in tried if (cc["src"], cc["key"]) not in still]
        decided += recs
        _save(tag, ver, recs)
        print(f"decide 第 {n} 輪:候選 {len(c)}、LLM 回 {len(items)} 筆、已決並登錄 {len(recs)}、仍未定 {len(left)}" + (f"、被拒 {len(errs)}" if errs else ""))
        c = left
        note = ("上一輪被拒或未過(請補回;不確定就維持未決,不要硬判已決):" + "；".join(errs[:5])) if errs else "上一輪仍有候選沒回覆或回未決:沒回覆的請補回;上一輪回未決的,證據沒變就維持未決,不要為了讓清單變空而硬判已決。"
    DL.run(tag, ver, texts, with_polyphone=False)   # 重產 decide_<ver>.md(含「④ 已決定」);完整版由 make_version --tts-review 再產
    if c:
        ks = [f"{x['key']}({x['src']})" for x in c]
        raise AB.Block(f"唸法未定 {len(c)}(英文 {sum(x['src'] == 'cosy_terms' for x in c)}、讀音 {sum(x['src'] != 'cosy_terms' for x in c)}):{'、'.join(ks[:8])}"
                       f"({calls} 輪 LLM;director 決不了,主對話接手:看 output\\{tag}\\decide_{ver}.md,定案後寫各表 _verified)")
    return {"before": first, "rounds": calls, "decided": decided, "left": []}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("python -X utf8 pipeline\\decide_step.py <tag> <ver>   (真寫詞表與 decide_<ver>.json;dry-run 見 tests\\test_decide_step.py)")
    try:
        r = run(sys.argv[1], sys.argv[2])
        print(f"唸法清單:候選 {r['before']} → 已決 {len(r['decided'])}、未定 0({r['rounds']} 輪 LLM)")
    except AB.Block as b:
        sys.exit(f"卡點:{b.reason}")
