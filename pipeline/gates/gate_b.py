r"""段 B gate(文案)。規格:pipeline\docs\director_ab.md §5–§6。"""
import hashlib
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import director as D  # noqa: E402
import paths as P  # noqa: E402
from gates import gate_a, specs  # noqa: E402

IDS = ("lint擋0", "warn_log", "facts_check", "visual_check", "標籤實檔", "speakable硬項", "編輯審", "玩家審", "ask_user", "估片長")
PIPE = Path(__file__).resolve().parents[1]
GENERIC_LABELS = ("", "anim", "cta")  # 不對應素材檔的標籤;quote:/cmp: 等卡片由 visual_check E2 查 @def
LOOSE_TYPES = ("連貫",)
HARD_PLAYER = ("錯", "關掉")


def status(tag, ctx):
    """director status 用(原 director.check_b,行為不變)。"""
    pd = P.PROJECTS / tag
    sc = P.REPO / tag / "script.txt"
    vt = pd / "visual_table.md"
    pr = D._first(D._glob(pd, "player_review*.md"))
    return [D._item("script.txt", sc.exists(), f"{tag}\\script.txt 沒有", sc),
            D._item("visual_table", vt.exists(), "visual_table.md 沒有", vt),
            D._item("玩家審", pr, "player_review*.md 沒有", pr)]


def tool(script, *args):
    """跑 pipeline 下的檢查程式,回 (rc, stdout+stderr)。"""
    r = subprocess.run([sys.executable, "-X", "utf8", str(PIPE / script), *args], cwd=P.ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def module(name):
    """平行開發中的模組延遲載入;還沒有 = None(gate 記不過,不中止)。"""
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def lint_over(tag):
    """script_lint 的超標數;程式出錯回 None。"""
    rc, text = tool("script_lint.py", tag)
    m = re.search(r"超標\s*(\d+)\s*項", text)
    return int(m.group(1)) if m else (0 if rc == 0 else None)


def facts_stat(tag):
    """facts_check 摘要 (未連結, 狀態不符, 錯誤);解析不到回 None。"""
    _, text = tool("facts_check.py", tag)
    m = re.search(r"未連結\s*(\d+)、狀態不符\s*(\d+)、錯誤\s*(\d+)", text)
    return tuple(int(x) for x in m.groups()) if m else None


def visual_errors(tag, *extra):
    """visual_check 錯誤數;解析不到回 None。"""
    _, text = tool("visual_check.py", "--tag", tag, *extra)
    m = re.search(r"\[visual_check\].*錯誤\s*(\d+)\s*項", text)
    return int(m.group(1)) if m else None


def sentence_hits(tag):
    """script_lint.check_sentences 全片;模組或函式還沒有回 None。"""
    m = module("script_lint")
    return m.check_sentences(tag) if m and hasattr(m, "check_sentences") else None


def speak_report(tag):
    """speakable.check_tag;模組還沒有回 None。"""
    m = module("speakable")
    return m.check_tag(tag) if m else None


def sha8(text):
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()[:8]


def narration(tag):
    """[(script.txt 行號, 旁白文字, 段標題, 行尾 extra)],與 script_txt2json 同源;解析失敗 raise ValueError。"""
    import script_txt2json as T2J
    try:
        _, _, sections, *_ = T2J.parse((P.REPO / tag / "script.txt").read_text(encoding="utf-8-sig"))
    except SystemExit as e:
        raise ValueError(str(e.code)) from None
    return [(no, text, sec["name"], extra) for sec in sections for no, _tg, text, extra in sec["rows"]]


def narration_hashes(tag):
    """每句旁白的雜湊;不含標籤與行尾 json,改 @say、hl、畫面標籤不變。讀不到回 []。"""
    try:
        return [sha8(r[1]) for r in narration(tag)]
    except (ValueError, OSError):
        return []


def warn_mark(check, line, rows):
    """警告鍵的雜湊來源:句文字;structure 沒有對應句就用所在段標題。其他情況 None(退回行號鍵)。"""
    if not rows:
        return None
    for no, text, *_ in rows:
        if no == line:
            return text
    if check != "structure":
        return None
    prior = [r[2] for r in rows if r[0] <= line]
    return prior[-1] if prior else ""


def warnings(tag):
    """本次所有警告:[{key, legacy, check, line, code, why}];key = <檢查>:<sha8>:<代碼>,legacy = 舊的行號鍵。
    lint / speakable 未就緒回 None(結構警告讀 structure.json,沒跑過 = 無)。"""
    sent, speak = sentence_hits(tag), speak_report(tag)
    if sent is None or speak is None:
        return None
    out = []
    try:
        rows = narration(tag)
    except (ValueError, OSError):
        rows = []

    def add(check, line, code, why):
        legacy, mark = f"{check}:{line}:{code}", warn_mark(check, line, rows)
        out.append({"key": legacy if mark is None else f"{check}:{sha8(mark)}:{code}", "legacy": legacy,
                    "check": check, "line": line, "code": code, "why": why})

    for s in sent:
        if not s.get("block"):
            add("lint", s["line"], s["code"], s.get("why", ""))
    for row in speak.get("lines") or []:
        for h in row.get("hits") or []:
            if h.get("severity") != "err":
                add("speak", row["line"], h["code"], h.get("why", ""))
    st = D._read_json(P.build_dir(tag) / "structure.json") or {}
    for w in st.get("warnings") or []:
        add("structure", w.get("line", 0), w.get("code", "?"), w.get("text", ""))
    return out


def warn_log(tag):
    return D._read_json(P.PROJECTS / tag / "warn_log.json") or {}


def unrecorded(tag, warns=None):
    """還在的警告裡沒有 kept+理由 的(記 fixed 但警告還在 = 沒修掉,也算沒紀錄);新鍵優先,舊的行號鍵也認。"""
    log = warn_log(tag)
    warns = warnings(tag) if warns is None else warns

    def kept(w):
        e = log.get(w["key"]) or log.get(w.get("legacy")) or {}
        return e.get("action") == "kept" and e.get("reason")

    return [w for w in warns or [] if not kept(w)]


def missing_labels(tag):
    """旁白行標籤對不到實檔的清單:img:x = images 下有 x 或 *_x;片段標籤 = clips tags 有。解析失敗 raise ValueError。"""
    import script_txt2json as T2J
    from visual_check import CFG
    try:
        _, _, sections, *_ = T2J.parse((P.REPO / tag / "script.txt").read_text(encoding="utf-8-sig"))
    except SystemExit as e:
        raise ValueError(str(e.code)) from None
    tags = set()
    pd = P.PROJECTS / tag
    for f in (P.clips_file(tag), pd / "clips.json"):
        for c in D._read_json(f) or []:
            tags.update((c.get("tags") or []) if isinstance(c, dict) else [])
    cards = set(CFG["card_kinds"]) | set(CFG["anim_kinds"])
    bad = []
    for sec in sections:
        for row in sec["rows"]:
            label = (row[1] or "").strip()
            kind, _, arg = label.partition(":")
            if label in GENERIC_LABELS or kind in cards:
                continue
            if kind == "img":
                if not (D._glob(P.IMAGES, f"{arg}.*") or D._glob(P.IMAGES, f"*_{arg}.*")):
                    bad.append(label)
            elif label not in tags:
                bad.append(label)
    return sorted(set(bad))


def latest_review(tag, kind):
    """(輪次, 資料, 路徑) 取 <kind>_review_r<n>.json 最大輪;沒有 (0, None, None)。"""
    best = (0, None)
    for p in D._glob(P.PROJECTS / tag, f"{kind}_review_r*.json"):
        m = re.search(r"_r(\d+)\.json$", p.name)
        if m and int(m.group(1)) >= best[0]:
            best = (int(m.group(1)), p)
    return (best[0], D._read_json(best[1]), best[1]) if best[1] else (0, None, None)


def open_items(data, types):
    """報告裡 type 命中 types、句號不在 revised(已交 revise 改過)的條目。"""
    done = set(data.get("revised") or [])
    return [i for i in data.get("items") or [] if i.get("type") in types and i.get("line") not in done]


def ask_user(tag):
    return D._read_json(P.PROJECTS / tag / "ask_user.json") or []


def review_items(tag):
    """flow v2:編輯審連貫斷點 0(已交 revise 的不算);玩家審最新一輪 錯/關掉 0。"""
    out = []
    rn, data, path = latest_review(tag, "editor")
    if data is None:
        out.append(D._item("編輯審", False, "editor_review_r<n>.json 沒有"))
    else:
        left = open_items(data, LOOSE_TYPES)
        out.append(D._item("編輯審", not left, f"r{rn} 連貫斷點未處理 {len(left)}", path))
    rn, data, path = latest_review(tag, "player")
    if data is None:
        out.append(D._item("玩家審", False, "player_review_r<n>.json 沒有"))
    else:
        left = open_items(data, HARD_PLAYER)
        out.append(D._item("玩家審", not left, f"r{rn} 錯/關掉 {len(left)}", path))
    return out


def review_items_v3(tag):
    """flow v3(review 步):編輯審 r1 存在且每條 revised 或 kept;review_state 完成且 open_hard 空
    (被判錯/關掉的句一定經過改與驗,仍在就進 ask_user,主對話清空後才結案)。"""
    pd = P.PROJECTS / tag
    ed = D._read_json(pd / "editor_review_r1.json")
    if ed is None:
        item = D._item("編輯審", False, "editor_review_r1.json 沒有")
    else:
        done = set(ed.get("revised") or []) | {k.get("line") for k in ed.get("kept") or [] if k.get("reason")}
        left = [i for i in ed.get("items") or [] if i.get("line") not in done]
        item = D._item("編輯審", "revised" in ed and not left, f"r1 未處理 {len(left)}" + ("" if "revised" in ed else "(還沒合併改稿)"),
                       pd / "editor_review_r1.json")
    st = D._read_json(pd / "review_state.json") or {}
    hard = st.get("open_hard") or []
    return [item, D._item("玩家審", bool(st.get("done")) and not hard,
                          f"錯/關掉未結 {len(hard)}" if st.get("done") else "review_state 未完成", pd / "review_state.json")]


def run(tag, ver=None, ctx=None):
    """lint 擋 0;warn_log 齊;facts_check 未連結/狀態不符/錯誤 0;visual_check 錯誤 0;每句標籤對到實檔;speakable 硬項 0;
    編輯審連貫斷點 0(已交 revise 的不算);玩家審 錯/關掉 0;ask_user 空;估片長 ≥ 下限(allow_short 放行,低於目標只 note)。
    另:write 步驟寫完即先查估片長 < 下限且無 allow_short → 擴寫一次,仍不足 → Block(問使用者),早於 speak/lint/review。
    另:lint 後、review 前 prerender 步(prerender_check:估秒 timeline + build --check-only)重點區過大/標籤挑不到/片段 >8 秒/images 不存在/cta、anim 無素材 → asset-collector 補或 line_fix(visual) 換標籤,≤2 輪,仍有 → Block。"""
    pd = P.PROJECTS / tag
    sc = P.REPO / tag / "script.txt"
    if not sc.exists():
        return [D._item(i, False, f"{tag}\\script.txt 沒有") for i in IDS]
    n = lint_over(tag)
    out = [D._item("lint擋0", n == 0, "script_lint 出錯" if n is None else f"超標 {n}", sc)]
    warns = warnings(tag)
    if warns is None:
        out.append(D._item("warn_log", False, "script_lint.check_sentences / speakable 未就緒"))
    else:
        left = unrecorded(tag, warns)
        names = "、".join(w["key"] for w in left[:5])
        out.append(D._item("warn_log", not left, f"警告 {len(warns)} 條,沒紀錄 {len(left)}" + (f":{names}" if names else ""), pd / "warn_log.json"))
    fs = facts_stat(tag)
    out.append(D._item("facts_check", fs == (0, 0, 0), "facts_check 無摘要(script/facts 有問題)" if fs is None
                       else f"未連結 {fs[0]}、狀態不符 {fs[1]}、錯誤 {fs[2]}"))
    ve = visual_errors(tag)
    out.append(D._item("visual_check", ve == 0, "visual_check 無摘要" if ve is None else f"錯誤 {ve}"))
    try:
        miss = missing_labels(tag)
        out.append(D._item("標籤實檔", not miss, f"對不到:{'、'.join(miss[:8]) or '無'}"))
    except ValueError as e:
        out.append(D._item("標籤實檔", False, f"script.txt 解析失敗:{e}"))
    sp = speak_report(tag)
    out.append(D._item("speakable硬項", sp is not None and sp.get("errors") == 0,
                       "speakable 未就緒" if sp is None else f"硬項 {sp.get('errors')}"))
    out += review_items_v3(tag) if specs.flow(tag) == "v3" else review_items(tag)
    ask = ask_user(tag)
    out.append(D._item("ask_user", not ask, f"待問使用者 {len(ask)} 條", pd / "ask_user.json"))
    brief = D._read_json(pd / "brief.json") or {}
    sp2 = specs.spec((ctx or {}).get("channel") or brief.get("channel"), brief.get("format"))
    out.append(gate_a._short_item("估片長", specs.est_minutes(tag), sp2, brief))
    return out
