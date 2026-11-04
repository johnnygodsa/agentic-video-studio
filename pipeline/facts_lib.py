#!/usr/bin/env python3
r"""事實核對表(projects\<tag>\facts*.md)的機器可讀解析與數字正規化(PLAN 文案資料驅動 §3.7)。只用標準函式庫。

  from facts_lib import parse, find_files, numbers_in, fact_numbers

表格:表頭同時含 `#`(或 `編號`)與 `主張` 的 Markdown 表才算;欄位用關鍵字對應(第一個符合的欄位勝出):
  主張->claim、狀態->status、原句/依據->quote、絕對值/幅度->magnitude、來源/網址->source、反面/限制/注意->counter
  (「幅度/反面」同欄算 magnitude)。id 取第一欄的 F\d+ 或純數字(F12a 這類也收);其餘列(說明文字、別種表)略過。
  儲存格內含未跳脫的 | (例:Xbox Series X|S)時,依狀態欄回推合併多出來的格子。
狀態正規化(status_raw 為原文):confirmed 一手 / secondary 轉述、媒體 / player_quote 玩家原話、留言 / derived 推算 /
  single 單一 / unverified 查無、未經證實、未證實 / unknown 其餘。含多個關鍵字時取較弱者(未證實 > 推算 > 單一 > 轉述 > 玩家 > 一手)。
數字:numbers_in(text) 抽阿拉伯數字(含小數、千分位、%、萬/億/M/B/K 倍數)與中文數字(二十三萬、七十美金、兩百一十二分鐘),
  正規化成可比字串:"二十三萬"、"23 萬"、"230,000" 都是 "230000";"6.39%" 是 "6.39%"。
  時間與日期先抽出(其數字不再另算):"八點四十"、"8:40"、"08:40" 都是 "08:40";"五點"、"5點"、"05:00" 是 "05:00";
  "六點到九點" 是 "06:00" 與 "09:00";"十一月五號"、"11/5"、"11-05"、"11 月 5 日" 是 "11-05";"2026-10-26" 是 "2026" 與 "10-26"。
  "一千多"、"兩百多"(以千/百/萬結尾加 多/餘)當近似值收成 "1000"、"200"(與事實端的 1000 同鍵)。
  句子端用 sentence_numbers(text):中文數字只收「後面接年月日號點歲倍人場次美金元…」或以萬/億結尾者(避免「一個、一直、第一場」),
  「百分之六」得 "6%"。事實表端用 fact_numbers(fact):claim+quote+magnitude+source(去掉網址)的 numbers_in(strict=True) 聯集,
  百分比同時收裸數字("20%" 也收 "20")。
"""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

STATUSES = ("confirmed", "secondary", "player_quote", "derived", "single", "unverified", "unknown")
WEAK = ("derived", "single", "unverified", "secondary")

# 較弱者優先(同一格寫了「一手 + 轉述」就當轉述)
_STATUS_RULES = [
    ("unverified", ("查無", "未經證實", "未證實", "未證", "無法證實", "無出處", "爆料")),
    ("derived", ("推算", "推論", "推估", "估算", "自算")),
    ("single", ("單一", "單方", "孤證")),
    ("secondary", ("轉述", "媒體", "二手", "報導", "多家")),
    ("player_quote", ("玩家原話", "玩家", "留言", "原話", "網友")),
    ("confirmed", ("一手", "官方", "已證實", "證實", "確認", "資料庫", "逐字", "已核")),
]

_COLS = [  # 欄位名稱 -> 標題關鍵字(依序比對,每個欄位只取第一個符合的標題)
    ("claim", ("主張",)),
    ("status", ("狀態", "核對")),
    ("quote", ("原句", "依據")),
    ("magnitude", ("絕對值", "幅度")),
    ("source", ("來源", "網址")),
    ("counter", ("反面", "限制", "注意")),
]

_RE_ID = re.compile(r"^F?\d+[a-z]?$", re.I)
_RE_SEP = re.compile(r"^:?-{2,}:?$")


@dataclass
class Fact:
    id: str
    claim: str = ""
    source: str = ""
    quote: str = ""
    status_raw: str = ""
    status: str = "unknown"
    magnitude: str = ""
    counter: str = ""
    file: str = ""
    line: int = 0


def norm_status(raw):
    s = raw or ""
    for name, kws in _STATUS_RULES:
        if any(k in s for k in kws):
            return name
    return "unknown"


_RE_HTTP = re.compile(r"https?://|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|tw|tv|gg|io|jp|cn|co|kr|uk|de|fr|info)\b", re.I)   # 含裸網域
_RE_FREF = re.compile(r"(?<![A-Za-z0-9])F\d+[a-z]?(?![A-Za-z0-9])")
_RE_LOCAL = re.compile(r"comments_ref|\.(?:md|json)", re.I)
_RE_QUOTE_NONE = re.compile(r"^[\s\-—–無]*(?:查無|n/?a)?[\s\-—–]*$|^查無", re.I)


def source_gaps(fact):
    """事實列缺什麼出處:[] = 齊;可含「來源無網址/F參照/本機檔」「原句空或查無」。
    來源要有 http(s) 網址、或引用其他 F 編號、或本機檔(comments_ref\、.md、.json);原句不可空/查無。
    狀態 derived(推算)的列原句可空(依據是算式),來源仍要有網址或 F 參照。"""
    out = []
    src = fact.source or ""
    own = canon_id(fact.id)
    refs = [m for m in _RE_FREF.findall(src) if canon_id(m) != own]
    if not (_RE_HTTP.search(src) or refs or _RE_LOCAL.search(src)):
        out.append("來源無網址/F參照/本機檔")
    if fact.status != "derived" and _RE_QUOTE_NONE.search((fact.quote or "").strip()):
        out.append("原句空或查無")
    return out


def canon_id(fid):
    """F12 / f12 / 12 -> 'F12'(比對用)。"""
    s = str(fid).strip().upper()
    return s if s.startswith("F") else "F" + s


def find_files(project_dir):
    """projects\\<tag>\\facts*.md;facts.md 排最前,其餘依檔名。"""
    fs = sorted(Path(project_dir).glob("facts*.md"), key=lambda p: (p.name != "facts.md", p.name))
    return [p for p in fs if p.is_file()]


# ---------------------------------------------------------------- 表格解析
def _split_row(line):
    s = line.strip().replace("\\|", "\x00")
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip().replace("\x00", "|") for c in s.split("|")]


def _map_header(cells):
    """回傳 {欄位名: 欄索引};不是 fact 表(缺 # 或 主張)回 None。"""
    if not cells or cells[0].strip() not in ("#", "編號") or not any("主張" in c for c in cells):
        return None
    cols = {}
    for name, kws in _COLS:
        for i, c in enumerate(cells):
            if i not in cols.values() and any(k in c for k in kws):
                cols[name] = i
                break
    return cols if "claim" in cols else None


def _fix_cells(cells, ncols, cols):
    """欄數比表頭多(內文有未跳脫的 |)時,把多出的格子併回去:優先併進讓「狀態欄」仍像狀態的那一段。"""
    extra = len(cells) - ncols
    if extra <= 0:
        return cells
    si = cols.get("status")
    order = [cols[k] for k in ("quote", "source", "claim") if k in cols] + list(range(ncols))
    for start in order:
        merged = cells[:start] + ["|".join(cells[start:start + extra + 1])] + cells[start + extra + 1:]
        if len(merged) != ncols:
            continue
        if si is None or norm_status(merged[si]) != "unknown":
            return merged
    start = order[0]
    return cells[:start] + ["|".join(cells[start:start + extra + 1])] + cells[start + extra + 1:]


def parse_text(text, file=""):
    facts, cols, ncols = [], None, 0
    for no, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s.startswith("|"):
            cols = None
            continue
        cells = _split_row(s)
        if cols is None:
            cols = _map_header(cells)
            ncols = len(cells)
            continue
        if all(_RE_SEP.match(c) or not c for c in cells):
            continue
        cells = _fix_cells(cells, ncols, cols)
        if not _RE_ID.match(cells[0].strip()):
            continue

        def cell(name):
            i = cols.get(name)
            return cells[i] if i is not None and i < len(cells) else ""

        st = cell("status")
        facts.append(Fact(id=cells[0].strip(), claim=cell("claim"), source=cell("source"), quote=cell("quote"),
                          status_raw=st, status=norm_status(st), magnitude=cell("magnitude"),
                          counter=cell("counter"), file=file, line=no))
    return facts


def parse(paths):
    """paths:檔案路徑或其清單(也接受目錄 -> 該目錄的 facts*.md)。回傳 Fact 清單(檔案順序、列順序)。"""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    out = []
    for p in paths:
        p = Path(p)
        for f in (find_files(p) if p.is_dir() else [p]):
            out.append((f, f.read_text(encoding="utf-8-sig")))
    res = []
    for f, t in out:
        res += parse_text(t, str(f))
    return res


# ---------------------------------------------------------------- 數字
_CN_DIG = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_SMALL = {"十": 10, "百": 100, "千": 1000}
_CN_CH = "零〇一二兩三四五六七八九十百千萬億"
_CN_UNITS = ("年", "月", "日", "號", "歲", "倍", "套", "公尺", "公里", "公斤", "成", "人", "名", "位", "場", "次", "集",
             "天", "週", "周", "分", "秒", "小時", "點", "美金", "美元", "元", "塊", "折")
_CN_UNIT_RE = "(?:" + "|".join(sorted(_CN_UNITS, key=len, reverse=True)) + ")"
_KEEP_ONE = ("月", "日", "號")   # 單獨的「一」只在這些單位前才算數(一月、一號),一年/一次不算;一點由時間規則處理

_RE_PCT_CN = re.compile(rf"百分之([{_CN_CH}]+|\d+(?:\.\d+)?)")
_RE_CN = re.compile(rf"(?<![第{_CN_CH}])([{_CN_CH}]+)([多幾餘]?)(?:({_CN_UNIT_RE}))?")
_RE_AR = re.compile(
    r"(?<!\d)(?<!\d\.)(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?"
    r"(?:(\s*%)|(\s*[萬億])|(\s*(?:million|billion|[MBK])(?![A-Za-z])))?", re.I)
_MULT = {"萬": 10 ** 4, "億": 10 ** 8, "k": 10 ** 3, "m": 10 ** 6, "million": 10 ** 6, "b": 10 ** 9, "billion": 10 ** 9}


def _fmt(d):
    d = d.normalize() if d != 0 else Decimal(0)
    s = format(d, "f")
    return s


def cn_to_int(s):
    """中文數字字串 -> int;無法解析回 None。支援 二十三、兩百一十二、一萬兩千、二零一九。"""
    if not s or any(c not in _CN_CH for c in s):
        return None
    if not any(c in "十百千萬億" for c in s):                      # 二零一九 這種逐位
        return int("".join(str(_CN_DIG[c]) for c in s))

    def section(t):                                                # 不含萬/億的一段
        total, cur = 0, 0
        for c in t:
            if c in _CN_DIG:
                cur = _CN_DIG[c]
            else:
                total += (cur or 1) * _CN_SMALL[c]
                cur = 0
        return total + cur

    def big(t):
        if "億" in t:
            a, _, b = t.partition("億")
            return (big(a) if a else 1) * 10 ** 8 + (big(b) if b else 0)
        if "萬" in t:
            a, _, b = t.partition("萬")
            return (section(a) if a else 1) * 10 ** 4 + (section(b) if b else 0)
        return section(t)

    try:
        return big(s)
    except (KeyError, ValueError):
        return None


# ---------------------------------------------------------------- 時間與日期("HH:MM"、"MM-DD")
_CN_N = "零〇一二兩三四五六七八九十"
_TOD = ("凌晨", "清晨", "早上", "早晨", "上午", "中午", "下午", "傍晚", "晚上", "半夜", "深夜", "午夜", "當天", "隔天")
_AFTER_MIN_BAD = set("個次人場倍位名套集天週周年月日號歲成折塊元萬億美秒")
_RE_FULLDATE = re.compile(r"(?<![\d/\-.:])(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?![\d/\-.:])")
_RE_MD_CJK = re.compile(r"(?<!\d)(\d{1,2})\s?月\s?(\d{1,2})\s?[日號号]")
_RE_MD_CN = re.compile(rf"(?<![{_CN_CH}])([{_CN_N}]{{1,3}})月([{_CN_N}]{{1,3}})[日號号]")
_RE_MD_SLASH = re.compile(r"(?<![\d/\-.:])(\d{1,2})[/\-](\d{1,2})(?![\d/\-.:]|\s?(?:人|個|次|年|分|秒|倍|場|週|周|天|小時|萬|億|%|％|支|款|名|位|隻|張|條|組|份))")
_RE_HHMM = re.compile(r"(?<![\d:.])(\d{1,2}):(\d{2})(?![\d:])")
_RE_DIAN_AR = re.compile(r"(?<![\d.])(\d{1,2})\s?點(?:\s?(\d{1,2})(?!\d)\s?分?|半)?")
_RE_DIAN_CN = re.compile(rf"(?<![{_CN_CH}])([{_CN_N}]{{1,3}})點(半|[{_CN_N}]{{1,3}}分?)?")


def _hm(h, m):
    return f"{h:02d}:{m:02d}" if 0 <= h <= 24 and 0 <= m <= 59 else None


def _md(mo, d):
    return f"{mo:02d}-{d:02d}" if 1 <= mo <= 12 and 1 <= d <= 31 else None


def _dian_cn(m, text):
    """「X點[Y分]」→ (HH:MM, 結束位置);小數點(三點五)與「一點點」回 None。"""
    h = cn_to_int(m.group(1))
    if h is None:
        return None
    end, minute = m.end(), 0
    tail = m.group(2)
    if tail == "半":
        minute = 30
    elif tail:
        has_fen = tail.endswith("分")
        mm = cn_to_int(tail.rstrip("分"))
        if mm is None:
            return None
        if has_fen:
            minute = mm
        elif len(tail) == 1:                                   # 三點五:小數,不是時間
            return None
        else:
            nxt = text[m.end():m.end() + 1]
            if nxt and (nxt in _AFTER_MIN_BAD or nxt in _CN_CH):
                return None
            minute = mm
    elif m.group(1) == "一":                                    # 「有一點、差一點」:只在時段詞後才當 1 點
        if not text[:m.start()].endswith(_TOD):
            return None
    t = _hm(h, minute)
    return (t, end) if t else None


def _dates_times(text):
    """抽出日期/時間 → [(鍵, (起, 訖))];互不重疊,先抽日期再抽時間。"""
    found, used = [], []

    def free(a, b):
        return all(b <= x or a >= y for x, y in used)

    def add(key, a, b):
        if key and free(a, b):
            found.append((key, (a, b)))
            used.append((a, b))

    for m in _RE_FULLDATE.finditer(text):
        mo, d = int(m.group(2)), int(m.group(3))
        if _md(mo, d) and free(*m.span()):
            found.append((m.group(1), m.span(1)))
            found.append((_md(mo, d), (m.start(2), m.end(3))))
            used.append(m.span())
    for m in _RE_MD_CJK.finditer(text):
        add(_md(int(m.group(1)), int(m.group(2))), *m.span())
    for m in _RE_MD_CN.finditer(text):
        a, b = cn_to_int(m.group(1)), cn_to_int(m.group(2))
        if a is not None and b is not None:
            add(_md(a, b), *m.span())
    for m in _RE_HHMM.finditer(text):
        add(_hm(int(m.group(1)), int(m.group(2))), *m.span())
    for m in _RE_MD_SLASH.finditer(text):
        add(_md(int(m.group(1)), int(m.group(2))), *m.span())
    for m in _RE_DIAN_AR.finditer(text):
        minute = 30 if m.group(0).endswith("半") else int(m.group(2) or 0)
        add(_hm(int(m.group(1)), minute), *m.span())
    for m in _RE_DIAN_CN.finditer(text):
        r = _dian_cn(m, text)
        if r:
            add(r[0], m.start(), r[1])
    return found


def _arabic(text):
    """回傳 [(正規化字串, 是否百分比, 起訖)]。"""
    out = []
    for m in _RE_AR.finditer(text):
        try:
            d = Decimal(m.group(1).replace(",", "") + ("." + m.group(2) if m.group(2) else ""))
        except InvalidOperation:
            continue
        pct = bool(m.group(3))
        if m.group(4):
            d *= _MULT[m.group(4).strip()]
        elif m.group(5):
            d *= _MULT[m.group(5).strip().lower()]
        out.append((_fmt(d) + ("%" if pct else ""), pct, m.span()))
    return out


def _chinese(text, strict):
    """strict=True(句子端):只收接單位或以萬/億結尾的中文數字。回傳 (集合, 百分之N 集合)。"""
    res = set()
    for m in _RE_PCT_CN.finditer(text):
        v = m.group(1)
        n = cn_to_int(v) if v[0] in _CN_CH else Decimal(v)
        if n is not None:
            res.add(_fmt(Decimal(n)) + "%")
    text = _RE_PCT_CN.sub(" ", text)
    for m in _RE_CN.finditer(text):
        run, unit = m.group(1), m.group(3)
        ends_big = run[-1] in "萬億"
        approx = m.group(2) in ("多", "餘") and run[-1] in "百千" and len(run) > 1     # 一千多、兩百多:近似值取下限
        if strict:
            if not (unit or ends_big or approx):
                continue
            if run == "一" and not ends_big and unit not in _KEEP_ONE:
                continue
        n = cn_to_int(run)
        if n is None:
            continue
        if not strict and len(run) == 1 and run in "零〇":
            continue
        res.add(str(n))
    return res


def numbers_in(text, strict=False):
    """文字中的數字(正規化字串集合)。strict=True 用於旁白句(中文數字只收有單位者)。"""
    text = text or ""
    res = set()
    masked = text
    for key, (a, b) in _dates_times(text):
        res.add(key)
        masked = masked[:a] + " " * (b - a) + masked[b:]
    for s, _, (a, b) in _arabic(masked):
        res.add(s)
        masked = masked[:a] + " " * (b - a) + masked[b:]   # 「23 萬」的萬已算進阿拉伯數字,中文端不再重算
    res |= _chinese(masked, strict)
    return res


def sentence_numbers(text):
    return numbers_in(text, strict=True)


_RE_URL = re.compile(r"(?:https?://)?[\w.-]+\.(?:com|net|org|tv|gg|io|jp|kr|tw|co)\b[^\s,;)」]*|https?://\S+", re.I)


def fact_numbers(fact, with_source=True):
    """事實表一列可對得上的數字集合:claim+quote+magnitude(+source 去網址)。百分比同時收裸數字。"""
    parts = [fact.claim, fact.quote, fact.magnitude]
    if with_source:
        parts.append(_RE_URL.sub(" ", fact.source or ""))
    res = set()
    for p in parts:
        res |= numbers_in(p, strict=True)
    res |= {n[:-1] for n in res if n.endswith("%")}
    return res
