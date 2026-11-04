"""句畫檢查與逐句畫面表(不需要 spec.json,只讀 <tag>\\script.txt;timeline.json 選用)。

python -X utf8 pipeline\\visual_check.py --tag <tag> [--timeline <timeline.json>] [--table] [--all]
     [--script <script.txt>] [--compare <visual_table.md>]

警告代號(門檻與泛用標籤判定集中在 CFG):
  A  數字句配片段:旁白有數據數字(日期以外),標籤是影片片段;Ad = 只有日期的數字句(較輕)
  B  具體物件配片段:旁白有人名/公司/產品/書名號/英文專名,片段標籤的說明(# 影片標籤:)沒提到它
  C  同一片段標籤連續 >= CFG.same_tag_run 句(每段只列一次)
  P  純片段(任何片段標籤、中間沒有截圖/動畫/卡片)連續 >= CFG.pure_clip_run 句
  H  hl 的字不在旁白(正規化、全半形、中文數字換算後仍沒有,且 bigram 重疊 < CFG.hl_min_overlap)
  M  anim 步驟與旁白沒有共同的數字或名詞(動畫內容與這句無關)
  N  anim 有秀數字但句內較大的數字(>= CFG.anim_missing_min)沒在動畫文字裡
  S  (給 timeline 才有)動畫最後一步出現後的停留 < CFG.anim_dwell_min 秒
  D  同一張圖連續的估計秒數(字數 × CFG.est_sec_per_char)> CFG.img_est_max_sec,或句數 > CFG.img_est_max_lines(寫稿時預擋 build 的同圖 9 秒 / 2 句錯誤)
  E  動畫步(同一步的後續句不算)那一句的估計秒數 < 該步動畫需要的秒數(build.anim_seconds;量不到的類型略過)
  O  開場前 CFG.open_lines 句內,文字卡(截圖 img: 與引言卡 quote:)連續 >= CFG.open_text_run 張(3_製作 開場 30 秒、2_文案 §6;每片只列一次)
  Q  引言卡(@def quote:)沒有 who(說話者身分,2_文案 §6;build.make_quote 的 q["who"] 選填,但真人引言要標)
  K1 逐句畫面表的 kit 欄寫了小件、script 該句沒有;K2 script 該句有 kit、畫面表沒寫(只在既有 visual_table.md 有 kit 欄時比對種類;
     先比對、再用 --table 依 script 重寫整張表)
錯誤:E1 hl 指到的 img 標籤找不到(圖檔或 # 截圖 清單,能判定時才報);E2 引用了未定義的 @def。
--table 另寫 projects\\<tag>\\visual_table.md(逐句畫面表,寫稿時看的「句畫同步表」)。
結尾一行「[visual_check] 警告 N 項、錯誤 M 項」;有錯誤結束碼 1(make_version 只印摘要不中止)。
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pace  # noqa: E402
import paths  # noqa: E402
import script_txt2json as s2j  # noqa: E402

# ---- 門檻與判定集中於此(2026-10-20 訂;依據 channel\research_文案優化_2026-10-20\30_句畫_*.md 的「可自動化檢查」)----
CFG = {
    "card_kinds": ("quote", "cmp", "compare", "card", "versus", "num", "bars", "list", "timeline", "cols", "share", "span", "flow"),
    "img_kinds": ("img",),
    "anim_kinds": ("anim",),
    # 除了 @fallback 的備援目標以外,另外視為泛用的片段標籤(例:通用空鏡)
    "generic_clip_tags": ("broll", "gameplay", "generic"),
    "same_tag_run": 3,       # C:同標籤連續幾句起警告
    "pure_clip_run": 4,      # P:純片段連續幾句起警告(研究建議 3 警告/5 錯誤;先取 4 避免洗版,實測後再調)
    "anim_dwell_min": 1.5,   # S:動畫最後一步後停留秒數下限(規則_畫面 §1)
    "hl_min_overlap": 0.5,   # H:hl 與旁白 bigram 重疊比例,>= 即視為近義命中
    "anim_missing_min": 10,  # N:句內數字小於此值(三個、五億)不要求出現在動畫文字
    "est_sec_per_char": 1 / pace.CHARS_PER_SEC,  # = 1/5.5 ≈ 0.1818(單一出處 pace.py)。D/E 與畫面表「估秒」欄:旁白字數 × 此值 = 估計秒數(寫稿時預估,實際以配音後的時長預檢為準)
    "img_est_max_sec": 9.0,  # D:同圖連續估計秒數上限(= build.IMG_MAX)
    "img_est_max_lines": 2,  # D:同圖連續句數上限(= build.IMG_MAX_UNITS)
    "open_lines": 6,         # O:開場檢查的句數(第 1–6 句)
    "open_text_run": 3,      # O:開場文字卡連續幾張起警告
    "text_card_kinds": ("quote",),  # O:除了截圖(vt=img)外算文字卡的卡片種類
    "show_per_code": 8,      # 預設每種代號最多印幾項(--all 全印)
    # B/M 比對用:太泛的詞不算「具體物件」或「共同名詞」
    "obj_pos": ("nr", "nt"),  # B 用的 jieba 詞性(nz 雜訊太多:太久、精華;英文專名與書名號另用 regex)
    "weak_cn_max": 2,        # A:中文數字(兩年、一個)值 <= 此數不算數字句
    "stop_words": ("遊戲", "玩家", "公司", "系列", "影片", "官方", "預告", "大家", "我們", "他們", "這個", "那個", "因為", "所以",
                   "媒體", "報導", "消息", "時間", "問題", "東西", "團隊", "作品", "內容", "結果", "原因", "平台", "主機"),
}

UNIT_AR = r"(?:年|月|日|號|歲|美金|美元|元|塊|萬|億|千|百|%|％|人|名|位|場|次|則|分|秒|倍|成|套|個|款|張|台|小時|週|天|點)"
CN = "零〇一二兩三四五六七八九十百千"
RE_CN = re.compile(rf"(?<!第)([{CN}萬億]+(?:點[{CN}]+)?)[多幾餘]?(?:年|月|日|號|歲|倍|套|成|人|名|位|場|次|集|天|週|禮拜|分|秒|小時|個|種|句|美金|元|塊|萬|億)")
RE_DATE = re.compile(rf"(?:\d{{4}}|[零〇一二三四五六七八九]{{4}})\s*年|(?:\d{{1,2}}|[{CN}]{{1,3}})\s*[月日號]")
RE_TITLE_NUM = re.compile(rf"(?:[一-鿿]{{2,}}|[A-Za-z]+\s?)\d+(?![\d,\.]*\s*{UNIT_AR})")
RE_ORD = re.compile(r"第\s*\d+\s*(?:個|步|種|章|部|代|款|篇|條)")
RE_PUNCT = re.compile(r"[\s" + re.escape(",.;:!?「」『』《》()[]\"'“”‘’·・-—…~/、。") + "]")  # NFKC 後全形標點已變半形
DIG = {c: i for i, c in enumerate("零一二三四五六七八九")}
DIG.update({"〇": 0, "兩": 2})


def cn2int(s):
    if all(c in DIG for c in s):
        return int("".join(str(DIG[c]) for c in s))
    total = cur = 0
    for c in s:
        if c in DIG:
            cur = DIG[c]
        elif c in "十百千":
            total += (cur or 1) * {"十": 10, "百": 100, "千": 1000}[c]
            cur = 0
    return total + cur


def cn_to_arabic(t):
    """旁白裡的中文數字換成阿拉伯(三十九點九九 -> 39.99;五億 -> 5億)。只換含數字字元的連續段。"""
    t = re.sub(rf"([{CN}]+)點([{CN}]+)", lambda m: f"{cn2int(m.group(1))}." + "".join(str(DIG.get(c, 0)) for c in m.group(2)), t)
    return re.sub(rf"[{CN}]+", lambda m: str(cn2int(m.group(0))), t)


def norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    s = RE_PUNCT.sub("", s.replace("的", "").replace("個", ""))
    return s


def variants(s):
    return {norm(s), norm(cn_to_arabic(s))}


def canon_num(tok):
    tok = tok.replace(",", "")
    try:
        f = float(tok)
    except ValueError:
        return tok
    return str(int(f)) if f == int(f) else str(f)


def strip_titles(t):
    """去掉書名號內容、書名/產品裡的數字(現代戰爭4、PS5)、序數(第3個),剩下才是數據數字的判斷對象。"""
    t = re.sub(r"《[^》]*》", "", t)
    t = RE_ORD.sub("", t)
    return RE_TITLE_NUM.sub("", t)


def cn_parse(s):
    """中文數字(含萬/億、小數「點」)轉數值:三萬一千 -> 31000;三十九點九九 -> 39.99。"""
    if "點" in s:
        i, _, d = s.partition("點")
        return cn_parse(i or "零") + float("0." + "".join(str(DIG.get(c, 0)) for c in d))
    if "億" in s:
        x, _, y = s.partition("億")
        return cn_parse(x or "一") * 1e8 + (cn_parse(y) if y else 0)
    if "萬" in s:
        x, _, y = s.partition("萬")
        return cn_parse(x or "一") * 1e4 + (cn_parse(y) if y else 0)
    return cn2int(s)


def canon_val(v):
    return str(int(v)) if float(v) == int(v) else str(round(float(v), 4))


def number_values(text, strip=True):
    """回傳 [(數值, 是否日期)]。阿拉伯數字認 萬/億 單位;中文數字(值 <= weak_cn_max 的兩年、一個略過)。"""
    t = strip_titles(text) if strip else text
    date_spans = [m.span() for m in RE_DATE.finditer(t)]
    out = []
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)[\s\"']*([萬億])?", t):
        v = float(m.group(1).replace(",", "")) * {"萬": 1e4, "億": 1e8}.get(m.group(2), 1)
        out.append((v, any(x <= m.start() < y for x, y in date_spans)))
    for m in RE_CN.finditer(t):
        core = m.group(1)
        if core == "一" or not re.search(f"[{CN}]", core):
            continue
        v = cn_parse(core)
        if v > CFG["weak_cn_max"]:
            out.append((v, any(x <= m.start() < y for x, y in date_spans)))
    return out


def number_tokens(text):
    return [(canon_val(v), d) for v, d in number_values(text)]


def num_in(v, pool):
    """v 是否在 pool 裡(完全相等,或近似:v >= 100 差 10% 內如三萬一千多對 31517;v >= 10 差 3% 內如 72% 對 71.9)。"""
    tol = 0.1 if v >= 100 else 0.03 if v >= 10 else 0
    return any(abs(n - v) <= tol * max(n, v) for n in pool)


# ---- jieba(延遲載入;沒裝就只用 regex)----
_POS = None


def pos_words(text):
    global _POS
    if _POS is None:
        try:
            import warnings
            warnings.filterwarnings("ignore")
            import jieba
            import jieba.posseg as pseg
            jieba.setLogLevel(60)
            _POS = pseg
        except Exception:  # noqa: BLE001
            _POS = False
    return list(_POS.cut(text)) if _POS else []


def objects(text):
    """具體物件(非數字):書名號、英文專名、jieba nr/nt/nz。"""
    out = []
    for m in re.finditer(r"《([^》]+)》", text):
        out.append(m.group(1))
    t = re.sub(r"《[^》]*》", " ", text)
    for m in re.finditer(r"[A-Z][A-Za-z0-9]{2,}(?:\s[A-Z][A-Za-z0-9]+)*", t):
        if m.group(0) not in ("The", "And", "But"):
            out.append(m.group(0))
    for w in pos_words(t):
        if w.flag in CFG["obj_pos"] and len(w.word) >= 2 and w.word not in CFG["stop_words"] and not w.word.isdigit():
            out.append(w.word)
    seen, res = set(), []
    for o in out:
        if o.lower() not in seen:
            seen.add(o.lower())
            res.append(o)
    return res


def nouns(text):
    out = [w.word for w in pos_words(text) if (w.flag.startswith("n") or w.flag == "eng") and len(w.word) >= 2
           and w.word not in CFG["stop_words"]]
    out += re.findall(r"[A-Za-z]{3,}", text)
    return out


# ---- 讀 script.txt ----
def load(tag, src=None):
    src = Path(src) if src else paths.ROOT / tag / "script.txt"
    if not src.exists():
        sys.exit(f"找不到 {src}")
    try:
        title, says, sections, top, defs, skipped = s2j.parse(src.read_text(encoding="utf-8-sig"))
    except SystemExit as e:
        sys.exit(f"script.txt 解析失敗:{e}")
    notes = [s["name"] for s in sections] + [s["name"] for s in skipped]
    lines, idx = [], 0
    for sec in sections:
        for no, tg, text, extra in sec["rows"]:
            idx += 1
            kind, _, arg = tg.partition(":")
            vt = ("img" if kind in CFG["img_kinds"] and arg else "anim" if kind in CFG["anim_kinds"]
                  else "card" if kind in CFG["card_kinds"] else "clip")
            lines.append(dict(idx=idx, no=no, tag=tg, kind=kind, arg=arg, vt=vt, text=text, extra=extra, sec=sec["name"]))
    return top, defs, notes, lines


def tag_descs(notes):
    d = {}
    for n in notes:
        if "影片標籤" in n:
            for m in re.finditer(r"([A-Za-z][A-Za-z0-9_]*)=([^/]+)", n.split(":", 1)[-1]):
                d[m.group(1)] = m.group(2).strip()
    return d


def shot_tags(notes):
    """# 截圖 說明行列出的圖名(tgb_tax=…):用來判斷 img 標籤是否有定義。"""
    out = set()
    for n in notes:
        if "截圖" in n or "對照圖" in n:
            out |= set(re.findall(r"(?:^|[\s/:;,、])([A-Za-z][A-Za-z0-9_]*)=", n))
    return out


def img_prefix(notes):
    for n in notes:
        m = re.search(r"前綴\s*[:：]?\s*([A-Za-z0-9]+_)", n)
        if m:
            return m.group(1)
    return None


def hl_list(extra):
    h = extra.get("hl")
    if isinstance(h, str):
        return [h]
    if isinstance(h, list):
        return [x if isinstance(x, str) else str(x.get("text", "")) for x in h if x]
    return []


def anim_of(ln, defs):
    """回傳 (anim dict 或 None, 引用字串, 錯誤)。"""
    a = ln["extra"].get("anim")
    if ln["vt"] != "anim" or a is None:
        return None, "", None
    if isinstance(a, dict):
        return a, a.get("type", "?"), None
    name, _, step = str(a).partition("#")
    d = defs.get("anim:" + name)
    return d, f"{name}#{step}" if step else name, (None if d else f"anim:{name}")


def anim_blob(a):
    b = {k: v for k, v in a.items() if k not in ("src", "step")}
    return json.dumps(b, ensure_ascii=False).replace(",", "")


# ---- 檢查 ----
def check(tag, top, defs, notes, lines, tl):
    W, E = [], []  # (code, idx, 訊息)
    descs = tag_descs(notes)
    generic = set(CFG["generic_clip_tags"])
    for v in (top.get("fallback") or {}).values():
        generic |= set(v)
    pre = img_prefix(notes)
    listed = shot_tags(notes)
    have_files = bool(pre and list(paths.IMAGES.glob(pre + "*")))
    for ln in lines:
        t, i, ex = ln["text"], ln["idx"], ln["extra"]
        ln["codes"] = []
        ln["est"] = round(len(t) * CFG["est_sec_per_char"], 1)

        def warn(code, msg):
            W.append((code, i, msg))
            ln["codes"].append(code)
        ntok = number_tokens(t)
        data = [v for v, is_date in ntok if not is_date]
        ln["nums"] = [v for v, _ in ntok]
        ln["objs"] = objects(t)
        if ln["vt"] == "clip":
            if data:
                warn("A", f"數字句配片段 {ln['tag']}:{'、'.join(data[:4])}")
            elif ntok:
                warn("Ad", f"日期句配片段 {ln['tag']}")
            if ln["objs"]:
                d = descs.get(ln["tag"])
                if d is not None or ln["tag"] in generic:
                    d = (d or "").lower() + " " + ln["tag"].lower()
                    miss = [o for o in ln["objs"] if o.lower() not in d]
                    if miss:
                        warn("B", f"物件配片段 {ln['tag']}:{'、'.join(miss[:3])}")
        # hl
        ln["hl"] = hl_list(ex)
        tv = variants(t)
        tbig = {s[k:k + 2] for s in tv for k in range(len(s) - 1)}
        for h in ln["hl"]:
            hv = variants(h)
            if any(x and x in y for x in hv for y in tv) or any(y and y in x for x in hv for y in tv):
                continue
            big = [x[k:k + 2] for x in hv for k in range(len(x) - 1)]
            if big and sum(b in tbig for b in big) / len(big) >= CFG["hl_min_overlap"]:
                continue
            warn("H", f"hl「{h}」不在旁白")
        if ln["vt"] == "img" and ln["hl"]:
            name = ln["arg"]
            found = name in listed or (have_files and any(paths.IMAGES.glob(f"{pre}{name}*")))
            if not found and (listed or have_files):
                E.append(("E1", i, f"img:{name} 有 hl 但圖檔與 # 截圖 清單都找不到"))
                ln["codes"].append("E1")
        # anim
        a, ref, miss_def = anim_of(ln, defs)
        ln["anim_ref"] = ref
        ln["anim_a"] = a
        if miss_def:
            E.append(("E2", i, f"用到未定義的 @def {miss_def}"))
            ln["codes"].append("E2")
        if ln["vt"] == "card" and ln["kind"] in ("quote", "cmp") and ln["tag"] not in defs:
            E.append(("E2", i, f"用到未定義的 @def {ln['tag']}"))
            ln["codes"].append("E2")
        if a and set(a) - {"type", "src", "step"}:  # 只有 type 沒內容的骨架動畫略過
            blob = anim_blob(a)
            pool = [v for v, _ in number_values(blob, strip=False)]
            sv = [v for v, _ in number_values(t)]
            common_noun = [n for n in set(nouns(t)) if n.lower() in blob.lower()]
            if not any(num_in(v, pool) for v in sv) and not common_noun:
                warn("M", f"動畫 {ref} 與旁白無共同數字/名詞")
            miss = [canon_val(v) for v, d in number_values(t) if not d and v >= CFG["anim_missing_min"] and not num_in(v, pool)]
            if miss:
                warn("N", f"動畫 {ref} 缺數字:{'、'.join(miss[:4])}")
    # 連續
    run_tag = run_pure = 0
    prev = None
    stats = {"same_tag_max": 0, "pure_max": 0}
    for k, ln in enumerate(lines):
        if ln["vt"] != "clip":
            run_tag = run_pure = 0
            prev = None
            continue
        run_tag = run_tag + 1 if ln["tag"] == prev else 1
        run_pure += 1
        prev = ln["tag"]
        stats["same_tag_max"] = max(stats["same_tag_max"], run_tag)
        stats["pure_max"] = max(stats["pure_max"], run_pure)
        nxt = lines[k + 1] if k + 1 < len(lines) else None
        end_tag = not (nxt and nxt["vt"] == "clip" and nxt["tag"] == ln["tag"])
        end_pure = not (nxt and nxt["vt"] == "clip")
        if end_tag and run_tag >= CFG["same_tag_run"]:
            first = lines[k - run_tag + 1]
            W.append(("C", first["idx"], f"{ln['tag']} 連續 {run_tag} 句(句 {first['idx']}-{ln['idx']})"))
            for x in lines[k - run_tag + 1:k + 1]:
                x["codes"].append("C")
        if end_pure and run_pure >= CFG["pure_clip_run"]:
            first = lines[k - run_pure + 1]
            W.append(("P", first["idx"], f"純片段連續 {run_pure} 句(句 {first['idx']}-{ln['idx']})"))
            for x in lines[k - run_pure + 1:k + 1]:
                x["codes"].append("P")
    W += opening_checks(lines, defs)
    W += estimate_checks(lines)
    W += timeline_checks(lines, tl, stats)
    return W, E, stats


def opening_checks(lines, defs):
    """O 開場文字卡連續 >= open_text_run;Q 引言卡 @def 缺 who(每個 def 只報第一次出現的句)。"""
    W, run, seen = [], [], set()
    for ln in lines[:CFG["open_lines"]]:
        if ln["vt"] == "img" or ln["kind"] in CFG["text_card_kinds"]:
            run.append(ln)
            continue
        if len(run) >= CFG["open_text_run"]:
            break
        run = []
    if len(run) >= CFG["open_text_run"]:
        W.append(("O", run[0]["idx"], f"開場文字卡連續 {len(run)} 張(句 {run[0]['idx']}-{run[-1]['idx']}:{'、'.join(x['tag'] for x in run)})"))
        for x in run:
            x["codes"].append("O")
    for ln in lines:
        if ln["kind"] != "quote" or ln["tag"] in seen:
            continue
        seen.add(ln["tag"])
        d = defs.get(ln["tag"])
        if isinstance(d, dict) and not str(d.get("who") or "").strip():
            W.append(("Q", ln["idx"], f"引言卡 {ln['tag']} 沒有 who(說話者身分)"))
            ln["codes"].append("Q")
    return W


_BUILD = []


def _anim_need(a, ref):
    """該步動畫需要的秒數(build.anim_seconds;build 載不進來或該類型量不到就回傳 None)。"""
    try:
        if not _BUILD:
            import build  # noqa: PLC0415 (重:只在有動畫句時才載入)
            _BUILD.append(build)
        step = ref.partition("#")[2] or a.get("step")
        if step not in (None, ""):
            a = dict(a, step=int(step) if str(step).lstrip("-").isdigit() else step)
        return float(_BUILD[0].anim_seconds(a))
    except Exception:  # noqa: BLE001
        return None


def estimate_checks(lines):
    """D:同圖連續估計 > img_est_max_sec 秒或 > img_est_max_lines 句;E:動畫步(第一句)估計秒數 < 該步動畫秒數。"""
    W = []
    k = 0
    while k < len(lines):
        ln = lines[k]
        if ln["vt"] == "img":
            j = k
            while j + 1 < len(lines) and lines[j + 1]["vt"] == "img" and lines[j + 1]["arg"] == ln["arg"]:
                j += 1
            run = lines[k:j + 1]
            est, n = sum(x["est"] for x in run), len(run)
            if est > CFG["img_est_max_sec"] or n > CFG["img_est_max_lines"]:
                span = f"句 {run[0]['idx']}-{run[-1]['idx']}" if n > 1 else f"句 {run[0]['idx']}"
                W.append(("D", run[0]["idx"], f"同圖 {ln['arg']} 連續 {n} 句、估計 {est:.1f} 秒"
                          f"(上限 {CFG['img_est_max_sec']:g} 秒 / {CFG['img_est_max_lines']} 句;{span})" if n > 1 else
                          f"同圖 {ln['arg']} 單句估計 {est:.1f} 秒 > {CFG['img_est_max_sec']:g} 秒"))
                for x in run:
                    x["codes"].append("D")
            k = j + 1
            continue
        a = ln.get("anim_a")
        if a is not None:
            prev = lines[k - 1] if k else None
            stepped = "#" in ln["anim_ref"] or a.get("step") is not None
            if not (stepped and prev and prev.get("anim_a") is not None and prev["anim_ref"] == ln["anim_ref"]):   # 同一步的後續句凍結,不算
                need = _anim_need(a, ln["anim_ref"])
                if need is not None and ln["est"] < need - 1e-6:
                    W.append(("E", ln["idx"], f"動畫 {ln['anim_ref']} 需要 {need:.1f} 秒,這句估計只有 {ln['est']:.1f} 秒"))
                    ln["codes"].append("E")
        k += 1
    return W


def load_timeline(path, lines):
    """回傳 dict(lines=[每句 dict],shots=[...]) 或 None;句數對不上時回傳 (None, 原因)。"""
    try:
        tl = json.loads(Path(path).read_text(encoding="utf-8"))
        tlines, shots = tl["lines"], tl["shots"]
    except Exception as e:  # noqa: BLE001
        return None, f"timeline 讀取失敗:{e}"
    if len(tlines) != len(lines):
        return None, f"timeline 句數 {len(tlines)} 與文案 {len(lines)} 不符(不同版本?),不計秒數"
    return dict(lines=tlines, shots=shots), None


def timeline_checks(lines, tl, stats):
    W = []
    if not tl:
        return W
    tlines, shots = tl["lines"], tl["shots"]
    for k, ln in enumerate(lines):
        tln = tlines[k]
        ln["dur"] = round(tln["end"] - tln["start"], 1) if "end" in tln and "start" in tln else None
        ln["nshots"] = len(tln.get("shots") or [])
    for s in shots:
        span = s["last_line"] - s["line"] + 1
        for n in range(s["line"], s["last_line"] + 1):
            if 1 <= n <= len(lines):
                lines[n - 1]["span"] = max(lines[n - 1].get("span", 1), span)
        if s.get("anim"):
            last = tlines[s["last_line"] - 1] if 1 <= s["last_line"] <= len(tlines) else None
            st = last.get("visual_start", last.get("start")) if last else None
            if st is None or "end" not in s:
                stats["dwell_unmeasurable"] = stats.get("dwell_unmeasurable", 0) + 1
                continue
            dwell = s["end"] - st
            lines[s["last_line"] - 1].setdefault("dwell", dwell)
            lines[s["last_line"] - 1]["anim_last"] = True
            if dwell < CFG["anim_dwell_min"]:
                W.append(("S", s["last_line"], f"動畫最後一步後停留 {dwell:.1f} 秒 < {CFG['anim_dwell_min']}"))
                lines[s["last_line"] - 1]["codes"].append("S")
    return W


# ---- kit 欄(逐句畫面表)----
def _kit_items(extra):
    k = (extra or {}).get("kit")
    k = [k] if isinstance(k, dict) else k
    return [it for it in k if isinstance(it, dict) and it.get("type")] if isinstance(k, list) else []


def kit_cell(extra):
    """該句 script 的 kit -> 畫面表 kit 欄文字:`callout:一團亂, arrow`(種類:對象文字;對象與前一項相同就省略)。"""
    out, prev = [], None
    for it in _kit_items(extra):
        lab = str(it.get("text") or (it.get("at") or {}).get("text") or "")
        out.append(it["type"] + (f":{lab}" if lab and lab != prev else ""))
        prev = lab or prev
    return ", ".join(out)


def _cell_types(cell):
    return {x.split(":", 1)[0].strip() for x in re.split(r"[,、]", cell) if x.strip()}


def kit_compare(lines, table_path):
    """既有畫面表有 kit 欄時,與 script 的 kit 種類逐句比對:K1 表有 script 無、K2 script 有表無。表不存在或沒有 kit 欄回傳 []。"""
    p = Path(table_path)
    if not p.exists():
        return []
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.startswith("|")]
    head = next((r for r in rows if "句#" in r), None)
    if not head or "kit" not in head:
        return []
    ik, ii = head.index("kit"), head.index("句#")
    table = {int(r[ii]): r[ik] if ik < len(r) else "" for r in rows if len(r) > ii and r[ii].isdigit()}
    W = []
    for ln in lines:
        if ln["idx"] not in table:
            continue
        want, have = _cell_types(table[ln["idx"]]), {it["type"] for it in _kit_items(ln["extra"])}
        new = []
        if want - have:
            new.append(("K1", ln["idx"], f"畫面表 kit 欄寫了 {'、'.join(sorted(want - have))},script 這句沒有"))
        if have - want:
            new.append(("K2", ln["idx"], f"script 有 kit {'、'.join(sorted(have - want))},畫面表 kit 欄沒寫"))
        ln["codes"] += [c for c, _, _ in new]
        W += new
    return W


# ---- 輸出 ----
VT_NAME = {"clip": "片段", "img": "截圖", "anim": "動畫", "card": "卡片"}


def write_table(tag, lines, W, E, tl, note, out_path=None):
    has_tl = bool(tl)
    head = ["句#", "行號", "旁白(前30字)", "估秒", "標籤", "畫面類型", "句內數字/具體物件", "hl", "kit", "警告"]
    if has_tl:
        head += ["句秒", "鏡頭數", "同鏡頭跨句", "動畫停留"]
    out = [f"# {tag} 句畫同步表", "",
           f"自動產生(pipeline\\visual_check.py --table);警告 {len(W)} 項、錯誤 {len(E)} 項。"
           "代號:A 數字句配片段、Ad 日期句配片段、B 物件配片段、C 同標籤連續、P 純片段連續、H hl 不在旁白、M 動畫與旁白無共同詞、"
           "N 動畫缺數字、S 動畫停留不足、D 同圖估計過久/過多句、E 動畫步估計秒數不足(估秒 = 字數 × " + f"{CFG['est_sec_per_char']:g} 秒)、O 開場文字卡連續、Q 引言卡缺 who、K1 表有 kit script 無、K2 script 有 kit 表無、E1 圖/E2 def 找不到。" + (f" 備註:{note}" if note else ""), "",
           "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    sec = None
    for ln in lines:
        if ln["sec"] != sec:
            sec = ln["sec"]
            out.append("| | | **" + sec.replace("|", "/") + "** |" + " |" * (len(head) - 3))
        vt = VT_NAME[ln["vt"]] + (f"({ln['anim_ref']})" if ln.get("anim_ref") else "")
        items = ln["nums"][:4] + [o for o in ln["objs"][:3]]
        row = [str(ln["idx"]), str(ln["no"]), ln["text"][:30].replace("|", "/"), f"{ln['est']:.1f}", ln["tag"], vt,
               "、".join(items).replace("|", "/"), "、".join(ln["hl"]).replace("|", "/"), kit_cell(ln["extra"]).replace("|", "/"),
               " ".join(dict.fromkeys(ln["codes"]))]
        if has_tl:
            d = ln.get("dwell")
            row += [str(ln.get("dur", "")), str(ln.get("nshots", "")), str(ln.get("span", 1)),
                    f"{d:.1f}" if d is not None else ("無法量" if ln.get("anim_last") else "")]
        out.append("| " + " | ".join(row) + " |")
    p = Path(out_path) if out_path else paths.PROJECTS / tag / "visual_table.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return p


def main():
    ap = argparse.ArgumentParser(description="句畫檢查與逐句畫面表(見檔頭說明)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--timeline", help="timeline.json(shots[] 有 line/last_line/start/end);不給就不算秒數")
    ap.add_argument("--table", action="store_true", help="寫 projects\\<tag>\\visual_table.md")
    ap.add_argument("--script", help="script.txt 路徑(預設 <tag>\script.txt;測試用)")
    ap.add_argument("--compare", help="kit 欄比對用的既有畫面表(預設 projects\<tag>\visual_table.md)")
    ap.add_argument("--table-out", help="--table 的輸出路徑(預設 projects\<tag>\visual_table.md;測試用)")
    ap.add_argument("--all", action="store_true", help="每種代號全部列出(預設各最多 %d 項)" % CFG["show_per_code"])
    a = ap.parse_args()
    top, defs, notes, lines = load(a.tag, a.script)
    tl, note = (None, "")
    if a.timeline:
        tl, note = load_timeline(a.timeline, lines)
        if tl is None:
            print(f"[visual_check] {note}")
    W, E, stats = check(a.tag, top, defs, notes, lines, tl)
    W += kit_compare(lines, a.compare or paths.PROJECTS / a.tag / "visual_table.md")   # 在 --table 重寫之前比對
    n = len(lines)
    cnt = {k: sum(1 for ln in lines if ln["vt"] == k) for k in VT_NAME}
    print(f"[visual_check] {a.tag}:{n} 句 | " + " ".join(f"{VT_NAME[k]} {v}({v * 100 // max(n, 1)}%)" for k, v in cnt.items()))
    by = {}
    for code, i, msg in sorted(W + E, key=lambda x: (x[0], x[1])):
        by.setdefault(code, []).append((i, msg))
    for code, items in by.items():
        lim = len(items) if a.all else CFG["show_per_code"]
        print(f"  {'錯誤' if code.startswith('E') else '警告'} {code} x{len(items)}")
        for i, msg in items[:lim]:
            print(f"    句{i}(行{lines[i - 1]['no']}) {msg}")
        if len(items) > lim:
            print(f"    …另 {len(items) - lim} 項(--all 全列)")
    print(f"  最長同標籤連續 {stats['same_tag_max']} 句、最長純片段連續 {stats['pure_max']} 句"
          + (f"、動畫停留無法量 {stats['dwell_unmeasurable']} 處" if stats.get("dwell_unmeasurable") else "")
          + ("" if tl else "、無 timeline(秒數未量)"))
    if a.table:
        print(f"  逐句畫面表:{write_table(a.tag, lines, W, E, tl, note, a.table_out)}")
    print(f"[visual_check] 警告 {len(W)} 項、錯誤 {len(E)} 項")
    sys.exit(1 if E else 0)


if __name__ == "__main__":
    main()
