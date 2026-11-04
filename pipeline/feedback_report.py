#!/usr/bin/env python3
r"""成效分析報告:channel\outcomes.jsonl -> channel\成效分析.md(描述性統計,不做因果結論)。

  python -X utf8 pipeline\feedback_report.py [--outcomes channel\outcomes.jsonl] [--out channel\成效分析.md]

規則(見 pipeline\docs\feedback.md):
  - 只用 is_self、不含已交出的「ChannelC」;比較只在「同頻道 x 同片長帶(≤10 分 / >10 分)」內(每個組合一節)。
  - 成效窗口固定 7d(不混 48h);沒有 7d 數據的片(未滿 7 天)不進分層表,等滿 7 天再跑;指標:曝光、CTR、均看%、30 秒留存、訂閱/千次觀看。
  - 因子表每格 n、中位、IQR(四分位距,線性內插);n < MIN_N(8) 的格只印「資料不足(n=…)」。
  - Spearman(自實作,平均秩)只在 n >= 10 時算。
  - A/B 教訓(末節):只用 status 為 winner/same/inconclusive 的測試,同頻道各一節;標題模式用同場觀看占比差(場數<8 印樣本不足),封面模式每個版本算一次參賽、label=winner 算勝、n<8 只印資料不足。
  - 全頻道標題測試(A/B 教訓之後):來源 Youtube AD channel_latest.json 每片 ab(含搬運片),mode=title 且 status 為完成者(both 只列場數);標題特徵用同場觀看占比差 + 95% 自助區間 + 最近 20 場勝出對照 + 自製/搬運分開統計。
  - 教訓:某因子兩組都 n >= 8 且中位差 > 兩組 IQR 均值 / 2 才寫一句事實;否則(兩組 n >= 3 且差距過同樣門檻)列候選假設。
"""
import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402
import feedback as FB  # noqa: E402

WINDOW = "7d"                       # 成效窗口固定 7d,不混 48h
LONG_SEC = 600                      # 片長帶:≤10 分 / >10 分
EXCLUDED_CHANNELS = ("ChannelC",)   # 已交出,不單獨成節
MIN_N = 8
MIN_CAND = 3
MIN_SPEARMAN = 10
UNKNOWN = "未知"
BIASES = (
    "published_at:Youtube AD 2026-10-26 之前登記的排程片記的是上傳時間(偏早 15–40 小時),之後為實際公開時間;舊列可用後端 repair-published 修。",
    "CTR 為封面 A/B 測試的混合值(各方案曝光比例不固定),不代表單一封面的點閱率。",
    "YouTube 的 typical 區間對短片不公平(以頻道同長度近期片為準,短片區間偏窄),本報告不用 typical。",
    "均看% 的分母是「互動觀看」(engaged views),不是全部觀看,與 Studio 平均觀看百分比口徑略有不同。",
)
# (欄名, 取值函式) 取值函式吃 outcomes 的一行,回傳 float 或 None
METRICS = (
    ("曝光", lambda r: _pv(r, "impressions")),
    ("CTR%", lambda r: _pv(r, "ctr_pct")),
    ("均看%", lambda r: _pv(r, "avg_view_pct")),
    ("30秒留存%", lambda r: r.get("retention_30s_pct")),
    ("訂閱/千次", lambda r: _subs_k(r)),
)


def _pv(r, key):
    b = (r.get("perf") or {}).get(WINDOW)
    v = (b or {}).get(key)
    return v if isinstance(v, (int, float)) else None


def _subs_k(r):
    v, s = _pv(r, "views"), _pv(r, "subs_net")
    return None if v is None or s is None or v <= 0 else s / v * 1000


# ---------------------------------------------------------------- 統計
def quantile(vals, q):
    s = sorted(vals)
    if not s:
        return None
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def median(vals):
    return quantile(vals, 0.5)


def iqr(vals):
    return quantile(vals, 0.75) - quantile(vals, 0.25)


def _ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(xs, ys):
    """Spearman 等級相關(平均秩 + Pearson);其中一邊全部相同(無變異)回 None。"""
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    return None if sxx == 0 or syy == 0 else sxy / (sxx * syy) ** 0.5


# ---------------------------------------------------------------- 因子分組
def _band(v, edges, labels):
    if v is None:
        return UNKNOWN
    for e, lab in zip(edges, labels):
        if v <= e:
            return lab
    return labels[-1]


def _seq(r):
    v = r.get("same_event_seq")
    return UNKNOWN if v is None else ("1" if v <= 1 else "2" if v == 2 else "≥3")


def _comp(r):
    v = r.get("competitor_videos_7d")
    return UNKNOWN if v is None else ("0" if v <= 0 else "1-3" if v <= 3 else "≥4")


def _judge(r):
    v = r.get("judge_sec")
    return UNKNOWN if v is None else ("≤15秒" if v <= 15 else "15-30秒" if v <= 30 else ">30秒")


def _txt(key):
    return lambda r: str(r[key]) if r.get(key) not in (None, "") else UNKNOWN


FACTORS = (
    ("鉤子型態 hook_type", _txt("hook_type")),
    ("判斷秒帶 judge_sec", _judge),
    ("第 1 標題切角 title_angle", _txt("title_angle")),
    ("封面方案 thumb_plan", _txt("thumb_plan")),
    ("題材 subject", _txt("subject")),
    ("同事件第幾支 same_event_seq", _seq),
    ("競品支數帶 competitor_videos_7d", _comp),
)
NUMERIC = (("judge_sec", "judge_sec"), ("competitor_videos_7d", "competitor_videos_7d"), ("same_event_seq", "same_event_seq"),
           ("chars_per_min", "chars_per_min"), ("facts_per_min", "facts_per_min"), ("blocks", "blocks"))


def _f(v, nd=1):
    if v is None:
        return "—"
    return f"{v:.{nd}f}".rstrip("0").rstrip(".") if abs(v) < 1000 else f"{v:,.0f}"


def _med_cell(vals):
    if len(vals) < MIN_N:
        return f"資料不足(n={len(vals)})"
    return f"{_f(median(vals))} [IQR {_f(iqr(vals))}]"


def dur_band(r):
    d = r.get("duration_s")
    return UNKNOWN if not isinstance(d, (int, float)) or d <= 0 else ("≤10分" if d <= LONG_SEC else ">10分")


def has_window(r):
    return FB.has_data((r.get("perf") or {}).get(WINDOW))


def strata(rows):
    g = defaultdict(list)
    for r in rows:
        g[(r.get("channel") or UNKNOWN, dur_band(r))].append(r)
    return dict(sorted(g.items()))


def factor_table(rows, name, fn):
    groups = defaultdict(list)
    for r in rows:
        groups[fn(r)].append(r)
    keys = sorted(groups, key=lambda k: (k == UNKNOWN, k))
    out = [f"**{name}**", "", "| 值 | n | " + " | ".join(m for m, _ in METRICS) + " |", "|---|---|" + "---|" * len(METRICS)]
    for k in keys:
        g = groups[k]
        if len(g) < MIN_N:
            out.append(f"| {k} | {len(g)} | 資料不足(n={len(g)}) |" + " — |" * (len(METRICS) - 1))
            continue
        cells = []
        for _, mf in METRICS:
            vals = [x for x in (mf(r) for r in g) if x is not None]
            cells.append(_med_cell(vals))
        out.append(f"| {k} | {len(g)} | " + " | ".join(cells) + " |")
    return out, groups


def lessons(rows, label):
    """回傳 (教訓句 list, 候選假設句 list)。"""
    sure, cand = [], []
    for fname, fn in FACTORS:
        groups = defaultdict(list)
        for r in rows:
            k = fn(r)
            if k != UNKNOWN:
                groups[k].append(r)
        for (ka, ga), (kb, gb) in combinations(sorted(groups.items()), 2):
            for mname, mf in METRICS:
                va = [x for x in (mf(r) for r in ga) if x is not None]
                vb = [x for x in (mf(r) for r in gb) if x is not None]
                if min(len(va), len(vb)) < MIN_CAND:
                    continue
                ma, mb = median(va), median(vb)
                gate = (iqr(va) + iqr(vb)) / 2 / 2
                if abs(ma - mb) <= gate or abs(ma - mb) == 0:
                    continue
                s = (f"{label}:{fname} 的「{ka}」(n={len(va)},{mname}中位 {_f(ma)})與「{kb}」(n={len(vb)},中位 {_f(mb)})"
                     f"相差 {_f(abs(ma - mb))},超過兩組 IQR 均值的一半({_f(gate)})。")
                (sure if min(len(va), len(vb)) >= MIN_N else cand).append(s)
    return sure, cand


def spearman_table(rows):
    out = ["**數值因子 Spearman**(n≥10 才算)", "", "| 因子 | " + " | ".join(m for m, _ in METRICS) + " |", "|---|" + "---|" * len(METRICS)]
    for label, key in NUMERIC:
        cells = []
        for _, mf in METRICS:
            pairs = [(r[key], mf(r)) for r in rows if isinstance(r.get(key), (int, float)) and mf(r) is not None]
            if len(pairs) < MIN_SPEARMAN:
                cells.append(f"資料不足(n={len(pairs)})")
                continue
            rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
            cells.append(f"n={len(pairs)} ρ=無變異" if rho is None else f"n={len(pairs)} ρ={rho:+.2f}")
        out.append(f"| {label} | " + " | ".join(cells) + " |")
    return out


# ---------------------------------------------------------------- 同場觀看占比比較(標題特徵)
# 每場各版本「超額 = share_pct - 該場平均」;特徵在同場有差時取「有的平均超額 - 沒有的平均超額」;跨場平均後自助抽樣取 95% 區間。
SHARE_BOOT, SHARE_SEED = 2000, 1
_NEG = "翻車|擺爛|吃相|盤子|韭菜|雙標|打臉|崩|慘|爛|罵|噴|嗆|怒|破防|騙|割|坑|毒|甩鍋|白蓮花|屎|倒|死|砍|裁|閉嘴|荼毒|放生|摳"
_PLAYER = "玩家|老玩家|萌新|新手|粉絲|觀眾|酸民|國服|台服"
_COMPANY = ("暴雪|動視|微軟|索尼|任天堂|EA|藝電|育碧|卡普空|頑皮狗|BioWare|生軟|Kotaku|IGN|SBI|騰訊|網易|拳頭|Bethesda|CDPR|"
            "史克威爾|SE|萬代|Valve|Steam")
# (特徵名, 判斷函式(乾淨標題), 場次過濾函式(該場全部標題)或 None)
SHARE_FEATURES = (
    ("含數字", lambda t: bool(re.search(r"\d|[一二三四五六七八九十百千萬兩]+(倍|年|天|小時|分|萬|人|支|款|關|隻|個|種|代|成)", t)), None),
    ("阿拉伯數字", lambda t: bool(re.search(r"\d", t)), None),
    ("問句(？/嗎/為什麼)", lambda t: bool(re.search(r"[？?]|為什麼|為何|嗎|怎麼", t)), None),
    ("為什麼開頭", lambda t: t.startswith(("為什麼", "為何")), None),
    ("第一人稱我", lambda t: "我" in t, None),
    ("經驗框(我看/玩/跑/打/等/查)", lambda t: bool(re.search(r"我(看|玩|跑|打|等|查)", t)), None),
    ("負面判語詞", lambda t: bool(re.search(_NEG, t)), None),
    ("點名玩家群", lambda t: bool(re.search(_PLAYER, t)), None),
    ("點名公司/媒體", lambda t: bool(re.search(_COMPANY, t)), None),
    ("引號「」", lambda t: "「" in t, None),
    ("其他標點(！，、：)", lambda t: bool(re.search(r"[！!，,、：:]", t)), None),
    ("結果/轉折詞(卻/竟/結果/但/還)", lambda t: bool(re.search(r"卻|竟|結果|但|還是|照樣|反而", t)), None),
    ("價格錢", lambda t: bool(re.search(r"美金|元|塊|台幣|\$|鎂|價", t)), None),
    ("長度>22", lambda t: len(t) > 22, None),
    ("長度≤16", lambda t: len(t) <= 16, None),
    ("空格分段≥2", lambda t: t.count(" ") >= 2, None),
    ("三段以上 vs 兩段(只看全版本都有空格的場)", lambda t: t.count(" ") >= 2, lambda ts: all(" " in t for t in ts)),
)


def clean_title(t):
    """去掉【…】標記。"""
    return re.sub(r"【[^】]*】", "", t or "").strip()


def share_tests(version_lists):
    """version_lists = 每場的版本 dict 清單 -> [[(乾淨標題, 超額)]];有 title 與數值 share_pct 的版本 >=2 且標題 >=2 種才算一場。"""
    out = []
    for vers in version_lists:
        vs = [v for v in (vers or []) if isinstance(v, dict) and v.get("title") and isinstance(v.get("share_pct"), (int, float))]
        if len(vs) < 2 or len({v["title"] for v in vs}) < 2:
            continue
        m = sum(v["share_pct"] for v in vs) / len(vs)
        out.append([(clean_title(v["title"]), v["share_pct"] - m) for v in vs])
    return out


def share_contrast(tests, f, test_ok=None):
    """回傳 (有差異的場數, 平均占比差, 95% 下界, 上界);場數 < MIN_N 時後三項為 None。"""
    per = []
    for vs in tests:
        if test_ok and not test_ok([t for t, _ in vs]):
            continue
        on = [e for t, e in vs if f(t)]
        off = [e for t, e in vs if not f(t)]
        if on and off:
            per.append(sum(on) / len(on) - sum(off) / len(off))
    if len(per) < MIN_N:
        return len(per), None, None, None
    rng = random.Random(SHARE_SEED)
    bs = sorted(sum(rng.choice(per) for _ in per) / len(per) for _ in range(SHARE_BOOT))
    return len(per), sum(per) / len(per), bs[int(SHARE_BOOT * 0.025)], bs[int(SHARE_BOOT * 0.975) - 1]


def share_feature_table(tests):
    """標題特徵占比差表(list of lines);場數 < MIN_N 的特徵不印。"""
    rows = []
    for name, f, ok in SHARE_FEATURES:
        n, m, lo, hi = share_contrast(tests, f, ok)
        if m is None:
            continue
        verdict = "加分" if lo > 0 else "扣分" if hi < 0 else "沒差"
        rows.append(f"| {name} | {n} | {m:+.1f} | [{lo:+.1f}, {hi:+.1f}] | {verdict} |")
    if not rows:
        return [f"樣本不足(可比較的測試 {len(tests)} 場,每個特徵需 ≥{MIN_N} 場同場有差),不下結論。", ""]
    return ["占比差 = 有該特徵的版本比沒有的,同場觀看占比多幾個百分點(跨場平均);95% 區間不跨 0 才判加分 / 扣分。", "",
            "| 特徵 | 場數 | 占比差 | 95% 區間 | 判讀 |", "|---|---|---|---|---|"] + rows + [""]


def share_gap_line(tests):
    """場內最高 - 最低占比差的中位 / P75。"""
    if not tests:
        return ""
    gaps = sorted(max(e for _, e in vs) - min(e for _, e in vs) for vs in tests)
    return f"場內最高-最低占比差:中位 {gaps[len(gaps) // 2]:.1f}、P75 {gaps[int(len(gaps) * .75)]:.1f}(百分點,{len(gaps)} 場)。"


# ---------------------------------------------------------------- A/B 教訓
AB_FINAL = ("winner", "same", "inconclusive")   # stopped(手動停止)不算完成的測試,不參賽、不算勝
AB_NOTE = ("寫標題與封面前讀本節,只採 n≥8 的格;封面表:勝率 = 勝 / 參賽(每個版本算一次參賽,label=winner 算勝);"
           "標題表:同場觀看占比差(有該特徵的版本比沒有的多幾點),場數 <8 不印;描述性統計,不代表因果。")


def _vtxt(key):
    return lambda v: str(v[key]) if v.get(key) not in (None, "") else UNKNOWN


AB_THUMB_FACTORS = (
    ("封面切角", _vtxt("cover_angle")),
    ("封面類型 kind", _vtxt("cover_kind")),
    ("封面手勢 gesture", _vtxt("cover_gesture")),
    ("封面主色 color", _vtxt("cover_color")),
    ("封面版型 layout", _vtxt("cover_layout")),
)


def _is_win(r, v):
    return v.get("label") == "winner" or (r.get("ab_winner_idx") is not None and v.get("idx") == r.get("ab_winner_idx"))


def ab_factor_table(entries, name, fn):
    """entries = [(row, version)];每格 參賽 n、勝 n、勝率;n<8 只印資料不足。"""
    g = defaultdict(lambda: [0, 0])
    for r, v in entries:
        k = fn(v)
        g[k][0] += 1
        g[k][1] += 1 if _is_win(r, v) else 0
    out = [f"**{name}**", "", "| 值 | 參賽 n | 勝 n | 勝率 |", "|---|---|---|---|"]
    for k in sorted(g, key=lambda k: (k == UNKNOWN, k)):
        n, w = g[k]
        out.append(f"| {k} | {n} | — | 資料不足(n={n}) |" if n < MIN_N else f"| {k} | {n} | {w} | {w / n * 100:.0f}% |")
    return out


def ab_section(rows):
    """回傳 A/B 教訓節(list of lines);沒有任何 A/B 資料印「尚無 A/B 資料」。"""
    out = ["## A/B 教訓", ""]
    done = [r for r in rows if r.get("ab_status") in AB_FINAL and isinstance(r.get("ab_versions"), list)]
    if not done:
        return out + ["尚無 A/B 資料(匯出沒有 ab,或測試都還沒結束)。", ""]
    out += [AB_NOTE, ""]
    by_ch = defaultdict(list)
    for r in done:
        by_ch[r.get("channel") or UNKNOWN].append(r)
    for ch in sorted(by_ch):
        grp = by_ch[ch]
        cnt = Counter((r.get("ab_mode") or "null", r["ab_status"]) for r in grp)
        out += [f"### {ch}(完成的測試 {len(grp)} 支)", "",
                "模式×結果:" + "、".join(f"{m}/{s} {n}" for (m, s), n in sorted(cnt.items())), ""]
        tt = [r for r in grp if r.get("ab_mode") == "title"]
        if tt:
            tests = share_tests(r["ab_versions"] for r in tt)
            out += [f"#### 標題模式({len(tt)} 支,可比較 {len(tests)} 場;同場占比差)", ""] + share_feature_table(tests)
        sub = [(r, v) for r in grp if r.get("ab_mode") == "thumb" for v in r["ab_versions"]]
        if sub:
            out += [f"#### 封面模式({len({id(r) for r, _ in sub})} 支,{len(sub)} 個參賽版本)", ""]
            for fname, fn in AB_THUMB_FACTORS:
                out += ab_factor_table(sub, fname, fn) + [""]
        both = [r for r in grp if r.get("ab_mode") == "both"]
        if both:
            out += ["#### 合測(不能歸因,只列勝出組合)", "", "| 發布 | tag | 結果 | 勝出組合 |", "|---|---|---|---|"]
            for r in sorted(both, key=lambda x: x.get("published_at") or ""):
                w = next((v for v in r["ab_versions"] if _is_win(r, v)), None)
                combo = (f"標題#{w['idx']}({w.get('title_angle') or UNKNOWN})+封面方案{w.get('thumb_plan')}" if w else "無勝出")
                out.append(f"| {(r.get('published_at') or '')[:10]} | {r.get('tag')} | {r['ab_status']} | {combo} |")
            out.append("")
    return out


# ---------------------------------------------------------------- 全頻道標題測試(含搬運)
CH_MODES = ("title", "both")        # 標題有參與的測試(thumb 模式標題相同,不比);both 只計場數、不納入占比比較
CH_RECENT = 20
CH_STATUS_LABEL = (("winner", "勝出"), ("same", "相同"), ("inconclusive", "無法判定"))


def load_channel_export(path=None):
    """讀 channel_latest.json(同 spec_check:paths.ytad_channel_export_latest());讀不到回 None。"""
    try:
        return json.loads(Path(path or P.ytad_channel_export_latest()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _ch_tests(ch):
    """該頻道完成的標題測試 -> [(video, ab)];缺 ab / ab 為 null / versions 非 list 一律略過。"""
    out = []
    for v in (ch.get("videos") or []):
        ab = v.get("ab")
        if (isinstance(ab, dict) and ab.get("status") in AB_FINAL and ab.get("mode") in CH_MODES
                and isinstance(ab.get("versions"), list) and ab["versions"]):
            out.append((v, ab))
    return out


def _ab_win(ab, ver):
    return ver.get("label") == "winner" or (ab.get("winner_idx") is not None and ver.get("idx") == ab.get("winner_idx"))


def _share(ver):
    s = ver.get("share_pct")
    return f"{s:.0f}%" if isinstance(s, (int, float)) else "—"


def _ch_stat_line(tests):
    c = Counter(ab["status"] for _, ab in tests)
    return "、".join(f"{lab} {c.get(k, 0)}" for k, lab in CH_STATUS_LABEL)


def channel_ab_section(data):
    """全頻道標題測試節(list of lines);data = channel_latest.json 解析結果或 None。"""
    out = ["## 全頻道標題測試(含搬運,來源 channel_latest.json)", ""]
    if not isinstance(data, dict):
        return out + ["讀不到 channel_latest.json,略過本節。", ""]
    chans = [(ch, _ch_tests(ch)) for ch in (data.get("channels") or []) if ch.get("name") not in EXCLUDED_CHANNELS]
    chans = [(ch, t) for ch, t in chans if t]
    if not chans:
        return out + ["尚無標題測試資料(匯出沒有 ab,或測試都還沒結束)。", ""]
    out += ["只用 status 為 winner / same / inconclusive 的測試(stopped 不算);標題因子只從標題文字算(去掉【…】);"
            "比較法 = 同場觀看占比差(各版本 share_pct 減該場平均,有該特徵的版本比沒有的,跨場平均,自助抽樣 2000 次取 95% 區間);"
            "mode=both 的場只列場數、不納入;場數 <8 的特徵不印;描述性統計,不代表因果。", ""]
    for ch, alltests in chans:
        tests = [t for t in alltests if t[1]["mode"] == "title"]
        nboth = len(alltests) - len(tests)
        out += [f"### {ch.get('name') or ch.get('slot') or UNKNOWN}(完成的標題測試 {len(tests)} 場"
                + (f";另 mode=both {nboth} 場不納入" if nboth else "") + ")", ""]
        if not tests:
            out += ["沒有 mode=title 的完成測試,不比較。", ""]
            continue
        out += ["結果:" + _ch_stat_line(tests), ""]
        flagged = [t for t in tests if "is_self" in t[0] and t[0]["is_self"] is not None]
        if flagged:
            selfs = [t for t in flagged if t[0]["is_self"]]
            others = [t for t in flagged if not t[0]["is_self"]]
            unk = len(tests) - len(flagged)
            line = f"自製 {len(selfs)} 場({_ch_stat_line(selfs)});搬運 {len(others)} 場({_ch_stat_line(others)})"
            out += [line + (f";未標示 {unk} 場" if unk else ""), ""]
        else:
            out += ["channel_latest 沒有 is_self 欄,自製與搬運全部合計。", ""]
        stests = share_tests(ab["versions"] for _, ab in tests)
        out += [f"**標題特徵(同場觀看占比差;可比較 {len(stests)} 場)**", ""] + share_feature_table(stests)
        if stests:
            out += [share_gap_line(stests), ""]
        wins = [(v, ab) for v, ab in tests if ab["status"] == "winner"]
        wins.sort(key=lambda t: (t[0].get("published_at") or "", t[0].get("video_id") or ""), reverse=True)
        out += [f"**勝出對照(最近 {min(len(wins), CH_RECENT)} 場 winner;勝出標題(占比)/ 落敗標題(占比))**", ""]
        if not wins:
            out += ["- 尚無 winner。", ""]
            continue
        for v, ab in wins[:CH_RECENT]:
            w = [x for x in ab["versions"] if _ab_win(ab, x)]
            lo = [x for x in ab["versions"] if not _ab_win(ab, x)]
            fmt = lambda x: f"「{x.get('title') or '(無標題)'}」({_share(x)})"  # noqa: E731
            out.append(f"- {(v.get('published_at') or '')[:10] or '未知日'} 勝 " + ("、".join(fmt(x) for x in w) or "—")
                       + " / 敗 " + ("、".join(fmt(x) for x in lo) or "—"))
        out.append("")
    return out


def build_report(all_rows, channel_data=None):
    selfs = [r for r in all_rows if r.get("is_self", 1) and r.get("channel") not in EXCLUDED_CHANNELS]
    rows = [r for r in selfs if has_window(r)]
    out = ["# 成效分析(自動產生,勿手改)", "",
           f"來源 `channel\\outcomes.jsonl`;自製片 {len(selfs)} 支(不含已交出的ChannelC);成效窗口固定 {WINDOW},"
           f"有 {WINDOW} 數據者 {len(rows)} 支進分層表(未滿 7 天或匯出沒有 7d 的 {len(selfs) - len(rows)} 支等滿窗口再算)。", "",
           "## 已知偏差", ""] + [f"- {b}" for b in BIASES]
    out += ["", "比較只在「同頻道 × 同片長帶(≤10 分 / >10 分)」內;每格 n<8 一律「資料不足」,不下結論;描述性統計,不代表因果。", ""]
    all_sure, all_cand = [], []
    body = []
    for (ch, db), g in strata(rows).items():
        label = f"{ch}/{db}"
        body += [f"## {label}(n={len(g)})", ""]
        for fname, fn in FACTORS:
            t, _ = factor_table(g, fname, fn)
            body += t + [""]
        body += spearman_table(g) + [""]
        s, c = lessons(g, label)
        all_sure += s
        all_cand += c
    out += ["## 教訓(事實句;兩組皆 n≥8 且中位差 > 兩組 IQR 均值/2)", ""]
    out += [f"- {s}" for s in all_sure] or ["- 目前沒有符合門檻的因子(資料累積中)。"]
    out += ["", "## 候選假設(待 n≥8;兩組 n≥3 且差距過同門檻,僅供下次取樣參考)", ""]
    cap = 20
    out += [f"- {s}" for s in all_cand[:cap]] or ["- 無。"]
    if len(all_cand) > cap:
        out.append(f"- …另 {len(all_cand) - cap} 條略。")
    out += [""] + (body or ["(沒有 is_self 的 outcomes 資料)", ""])
    out += ab_section(selfs)
    out += channel_ab_section(channel_data)
    return "\n".join(out).rstrip("\n") + "\n"


def main(argv):
    ap = argparse.ArgumentParser(description="outcomes.jsonl -> 成效分析.md")
    ap.add_argument("--outcomes", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--channel-export", default=None, help="channel_latest.json 路徑(預設 paths.ytad_channel_export_latest())")
    a = ap.parse_args(argv)
    src = Path(a.outcomes) if a.outcomes else FB.outcomes_path()
    dst = Path(a.out) if a.out else P.ROOT / "channel" / "成效分析.md"
    rows = list(FB.read_outcomes(src).values())
    text = build_report(rows, load_channel_export(a.channel_export))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    print(f"{len(rows)} 筆 outcomes -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1:])
