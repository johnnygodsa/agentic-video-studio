r"""報告:tmp\tts_bakeoff\report.md(指標 (a)–(f) 表 + 證據強度 + 結論欄位留給主對話)與 listen.md(20 句 A/B 盲聽,答案在檔尾)。
輸入 = cli judge 寫的 metrics.json(全部是 JSON 可序列化的 dict);純字串處理,測試用假資料。"""
import random
from pathlib import Path

from tts_bakeoff import metrics as M

NAMES = {"cosy3": "CosyVoice3", "indextts2": "IndexTTS2", "breezy": "BreezyVoice", "breezy_ann": "BreezyVoice+注音標注"}
TRIO = ("cosy3", "breezy", "breezy_ann")     # BreezyVoice 比武(2026-11-04)的三組
VRAM_LIMIT = 3500


def _pct(x, d=2):
    return "-" if x is None else f"{x * 100:.{d}f}%"


def _num(x, fmt="{:.2f}"):
    return "-" if x is None else fmt.format(x)


def _ci(c, pct=True):
    if not c or c[0] is None:
        return "-"
    f = (lambda v: f"{v * 100:+.2f}pt") if pct else (lambda v: f"{v:+.2f}")
    if c[1] is None:
        return f(c[0])
    return f"{f(c[0])}({f(c[1])} ~ {f(c[2])})"


def probe_lines(pr):
    """冷啟量測表(第 1 步)。pr = probe.json。"""
    if not pr:
        return ["(沒有 probe.json:第 1 步未跑)"]
    ts = pr.get("time") or {}
    L = ["| 項目 | 數值 |", "|---|---|",
         f"| 載入秒數 | {_num(pr.get('load_s'), '{:.1f}')} |",
         f"| 載入後顯存(torch reserved / allocated)| {_num(pr.get('load_reserved_mib'), '{:.0f}')} / {_num(pr.get('load_alloc_mib'), '{:.0f}')} MiB |",
         f"| 峰值顯存(torch 峰值 / nvidia-smi 增量 / 取大)| {_num(pr.get('torch_peak_mib'), '{:.0f}')} / {_num(pr.get('smi_delta_mib'), '{:.0f}')} / **{_num(pr.get('vram_peak_mib'), '{:.0f}')}** MiB(門檻 {pr.get('limit_mib', VRAM_LIMIT)}) |",
         f"| 句數(成功 / 失敗)| {pr.get('n_ok', 0)} / {pr.get('n_fail', 0)}{';子行程中止:' + str(pr['crashed'])[:80] if pr.get('crashed') else ''} |",
         f"| 每句秒數(平均 / 中位 / p90)| {_num(ts.get('mean'))} / {_num(ts.get('median'))} / {_num(ts.get('p90'))} |",
         f"| RTF(合成秒 / 音長)| {_num(ts.get('rtf'))} |",
         f"| 時長控制參數 | {'支援:' + str(pr.get('dur_kwarg')) + '(' + str(pr.get('dur_unit')) + ')' if pr.get('dur_supported') else '此版 infer() 未找到(本機確認)'} |",
         f"| 判定 | **{'通過,往下做' if pr.get('passed') else '結案:' + '; '.join(pr.get('reasons') or [])}** |"]
    if pr.get("source"):
        L.append(f"\n來源:{pr['source']}")
    return L


def write_closure(path, pr, date):
    """顯存不夠/不穩定:只有冷啟量測與結案理由的 report.md。"""
    L = [f"# 配音引擎比武 IndexTTS2 vs CosyVoice3 — 結案紀錄 {date}", "",
         "第 1 步冷啟量測未過(channel/_archive/plans/PLAN_工具升級_2026-10-26.md T1:顯存 > 3.5 GB 或無法在 8 GB 卡上穩定跑,直接記錄後結案,不往下做)。", "",
         "## 冷啟量測", "", *probe_lines(pr), "",
         "## 結論(主對話填)", "",
         "- 結論:顯存不夠(腳本自動判定,待主對話確認)",
         f"- 結案理由:{'; '.join(pr.get('reasons') or [])}",
         f"- 證據強度:{M.evidence(pr.get('n_ok', 0) + pr.get('n_fail', 0), kind='single')}", ""]
    Path(path).write_text("\n".join(L), encoding="utf-8")


def _poly_cell(p):
    if not p or not p.get("n"):
        return "-"
    return f"{_pct(p['rate'], 1)}(對 {p['right']} / 錯 {p['wrong']} / 無法判定 {p['undetermined']})"


def write_report(path, mt, date):
    """mt = metrics.json。表格 (a)–(f) + 補充 + 結論欄位(留給主對話)。"""
    E = mt.get("engines") or {}
    a, b = E.get("cosy3") or {}, E.get("indextts2") or {}
    cmp_, nc = mt.get("compare") or {}, mt.get("n_common", 0)
    S = mt.get("synth") or {}
    sa, sb = S.get("cosy3") or {}, S.get("indextts2") or {}
    ta, tb = sa.get("time") or {}, sb.get("time") or {}
    du = mt.get("dur") or {}
    co = mt.get("corpus") or {}

    def row(label, va, vb, key=None, kind="asr", pct=True, n=None):
        c = cmp_.get(key) if key else None
        return f"| {label} | {va} | {vb} | {_ci(c, pct) if c else '-'} | {M.evidence(n if n is not None else nc, c, kind)} |"

    L = [f"# 配音引擎比武 IndexTTS2 vs CosyVoice3 {date}", "",
         f"語料:{co.get('n', '-')} 句({'、'.join(co.get('tags') or [])};每支 {co.get('per_tag', '-')} 句,"
         f"品管未過 {co.get('qc_fail', 0)}、聽審改過 {co.get('heard', 0)}、其餘 {co.get('plain', 0)});兩引擎送同一份文字"
         f"(tts_cosy_text 處理;IndexTTS2 只換拼音寫法)。兩邊都有結果的句子 {nc} 句。", "",
         "品管:兩引擎的原始輸出都先做出片同款「裁靜音 + 貼耳感 FX」,再用 tts_cosy3 驗證模式(不重錄:--max-retry 0、--rate-seeds 0)跑現有品管鏈"
         "(主 Qwen3-ASR / 副 Fun-ASR-Nano 雙辨識、tts_tail 尾切、句中停頓、語速、聲紋);單次合成(seed 固定)比原始品質,不是出片的重錄後結果。",
         "差異欄 = IndexTTS2 − CosyVoice3(成對 bootstrap 95% 區間;CER/比率以百分點 pt)。", "",
         "## 第 1 步 冷啟量測(IndexTTS2)", "", *probe_lines(mt.get("probe")), "",
         "## 指標 (a)–(f)", "",
         "| 指標 | CosyVoice3 | IndexTTS2 | 差(IndexTTS2−CosyVoice3) | 證據強度 |", "|---|---|---|---|---|",
         row("(a) 字元 CER(主辨識)", _pct(a.get("cer")), _pct(b.get("cer")), "cer"),
         row("(a) 拼音 CER(主辨識)", _pct(a.get("pcer")), _pct(b.get("pcer")), "pcer"),
         row("(a) 字元 CER(副辨識)", _pct(a.get("cer2")), _pct(b.get("cer2")), "cer2"),
         row("(a) 拼音 CER(副辨識)", _pct(a.get("pcer2")), _pct(b.get("pcer2")), "pcer2"),
         row("(b) 多音字讀對率(pron_rules 命中位置)", _poly_cell(a.get("poly")), _poly_cell(b.get("poly")), "poly_rate",
             n=min((a.get("poly") or {}).get("n", 0), (b.get("poly") or {}).get("n", 0))),
         row("(c) 品管未過句數", f"{a.get('failed', '-')} / {a.get('n', '-')}({_pct(a.get('fail_rate'), 1)})",
             f"{b.get('failed', '-')} / {b.get('n', '-')}({_pct(b.get('fail_rate'), 1)})", "fail_rate"),
         row("(d) 每句秒數(平均 / 中位;RTF)", f"{_num(ta.get('mean'))} / {_num(ta.get('median'))};{_num(ta.get('rtf'))}",
             f"{_num(tb.get('mean'))} / {_num(tb.get('median'))};{_num(tb.get('rtf'))}", kind="measured",
             n=min(ta.get("n", 0), tb.get("n", 0))),
         row("(e) 顯存峰值 MiB(torch / smi 增量 → 取大)",
             f"{_num(sa.get('torch_peak_mib'), '{:.0f}')} / {_num(sa.get('smi_delta_mib'), '{:.0f}')} → {_num(sa.get('vram_peak_mib'), '{:.0f}')}",
             f"{_num(sb.get('torch_peak_mib'), '{:.0f}')} / {_num(sb.get('smi_delta_mib'), '{:.0f}')} → {_num(sb.get('vram_peak_mib'), '{:.0f}')}",
             kind="single", n=min(ta.get("n", 0), tb.get("n", 0))),
         ]
    if du.get("supported") is False:
        L.append(f"| (f) 時長控制誤差 | (不適用) | 此版 IndexTTS2 infer() 無時長參數(本機確認:{du.get('note', '')}) | - | 無 |")
    elif du.get("n"):
        L.append(f"| (f) 時長控制誤差(目標 = {du.get('target_src', 'CosyVoice 同句時長')})| (不適用) | "
                 f"平均 |誤差| {_pct(du.get('mean_abs'), 1)}、中位 {_pct(du.get('median_abs'), 1)}、p90 {_pct(du.get('p90_abs'), 1)}、"
                 f"平均偏差 {_pct(du.get('mean_signed'), 1)};±5% 內 {_pct(du.get('within5'), 0)}、±10% 內 {_pct(du.get('within10'), 0)} | - | "
                 f"{M.evidence(du['n'], kind='measured')} |")
    else:
        L.append("| (f) 時長控制誤差 | (不適用) | 未跑(synth --engine indextts2 --dur) | - | 無 |")
    L += ["", "## 補充", "",
          "| 項目 | CosyVoice3 | IndexTTS2 |", "|---|---|---|",
          f"| 聲紋相似度中位數(對參考音 ref_b)| {_num(a.get('spk_sim_median'), '{:.3f}')} | {_num(b.get('spk_sim_median'), '{:.3f}')} |",
          f"| 副辨識不一致(asr2_bad)句數 | {a.get('asr2_bad', '-')} | {b.get('asr2_bad', '-')} |",
          f"| 合成失敗句數 | {sa.get('n_fail', '-')} | {sb.get('n_fail', '-')} |",
          f"| 品管未過原因(前 8)| {_reasons(a)} | {_reasons(b)} |", "",
          "注意:(a)(b)(c) 是辨識器文字層代理(聽不到電音感、語氣自然度;多音字吐回原字時判不出聲調),不等於人耳;自然度要靠 listen.md 抽聽。"
          "證據強度規則:n < 30 弱;差異區間含 0 弱;辨識器代理指標上限中;直接量測 n >= 200 且區間不含 0 才強;顯存為單次峰值。", "",
          "## 結論(主對話填)", "",
          "- 結論:<換 / 不換 / 只當第二引擎 / 顯存不夠>",
          "- 理由:",
          "- 各項證據強度摘要:",
          "- 若「只當第二引擎」:適用句型 / 觸發條件:", ""]
    Path(path).write_text("\n".join(L), encoding="utf-8")


def _reasons(e):
    r = e.get("fail_reasons") or {}
    return "、".join(f"{k} {v}" for k, v in list(r.items())[:8]) or "-"


# ------------------------------------------------------------ 三組報告(BreezyVoice 比武,2026-11-04)
def _pron_cell(e):
    p = e.get("poly") or {}
    return f"未過句 {e.get('pron_fail', '-')} / 位置判錯 {p.get('wrong', '-')}"


def write_report_multi(path, mt, date, engines=TRIO):
    """三組以上比武報告:各引擎並列 + 各組對 CosyVoice3 / 注音標注對純文字的成對差異表 + 結論欄。mt = metrics.json(compare_by = {名稱: {指標: 區間}})。"""
    E, S, co = mt.get("engines") or {}, mt.get("synth") or {}, mt.get("corpus") or {}
    CB, NB = mt.get("compare_by") or {}, mt.get("n_common_by") or {}
    es = [E.get(e) or {} for e in engines]
    ts = [(S.get(e) or {}).get("time") or {} for e in engines]
    ss = [S.get(e) or {} for e in engines]
    head = "| 指標 | " + " | ".join(NAMES[e] for e in engines) + " |"
    sep = "|---|" + "---|" * len(engines)

    def line(label, cells):
        return f"| {label} | " + " | ".join(cells) + " |"

    L = [f"# 配音引擎比武 {' vs '.join(NAMES[e] for e in engines)} {date}", "",
         f"語料:{co.get('n', '-')} 句({'、'.join(co.get('tags') or [])};focus={co.get('focus', '-')};"
         f"{'、'.join(f'{k} {v}' for k, v in (co.get('classes') or {}).items())})。"
         "CosyVoice3 送 tts_cosy3.engine_text(簡體、拼音 token);BreezyVoice 送繁體 + 同一份 cosy_terms 英文寫法,"
         "breezy 只靠它內建 g2pW 補注音,breezy_ann 再加我們的讀音標注(cosy_pron 詞表 + pron_rules + 語境記憶,轉成「字[:ㄓㄤ3]」)。", "",
         "品管:各引擎原始輸出都先做出片同款「裁靜音 + 貼耳感 FX」,再用 tts_cosy3 驗證模式(不重錄:--max-retry 0、--rate-seeds 0)跑現有品管鏈"
         "(主 Qwen3-ASR / 副 Fun-ASR-Nano 雙辨識、尾切、句中停頓、語速、聲紋);單次合成(seed 固定)比原始品質,不是出片的重錄後結果。"
         "語速/音高基準是各引擎自己整批的中位數(BreezyVoice 本身沒有 speed 參數,cosy3 用出片的 1.18)。", "",
         "## 指標", "", head, sep,
         line("(a) 字元 CER(主辨識)", [_pct(x.get("cer")) for x in es]),
         line("(a) 拼音 CER(主辨識)", [_pct(x.get("pcer")) for x in es]),
         line("(a) 字元 CER(副辨識)", [_pct(x.get("cer2")) for x in es]),
         line("(a) 拼音 CER(副辨識)", [_pct(x.get("pcer2")) for x in es]),
         line("(b) 多音字讀對率(pron_rules 命中位置)", [_poly_cell(x.get("poly")) for x in es]),
         line("(b) 多音字錯誤數(pron 類品管未過句數 / 位置判錯數)", [_pron_cell(x) for x in es]),
         line("(c) 品管未過句數", [f"{x.get('failed', '-')} / {x.get('n', '-')}({_pct(x.get('fail_rate'), 1)})" for x in es]),
         line("(d) 每句秒數(平均 / 中位;RTF)", [f"{_num(t.get('mean'))} / {_num(t.get('median'))};{_num(t.get('rtf'))}" for t in ts]),
         line("(e) 顯存峰值 MiB(torch / smi 增量 → 取大)",
              [f"{_num(x.get('torch_peak_mib'), '{:.0f}')} / {_num(x.get('smi_delta_mib'), '{:.0f}')} → {_num(x.get('vram_peak_mib'), '{:.0f}')}" for x in ss]),
         line("聲紋相似度中位數(對參考音 ref_b)", [_num(x.get("spk_sim_median"), "{:.3f}") for x in es]),
         line("副辨識不一致(asr2_bad)句數", [str(x.get("asr2_bad", "-")) for x in es]),
         line("合成失敗句數", [str(x.get("n_fail", "-")) for x in ss]),
         line("品管未過原因(前 8)", [_reasons(x) for x in es]), ""]
    pairs = [(f"{e}_vs_cosy3", f"{NAMES[e]} − CosyVoice3") for e in engines if e != "cosy3"]
    if "breezy" in engines and "breezy_ann" in engines:
        pairs.append(("breezy_ann_vs_breezy", f"{NAMES['breezy_ann']} − {NAMES['breezy']}"))
    L += ["## 成對差異(同句比較;成對 bootstrap 95% 區間;CER/比率以百分點 pt;括號後為證據強度)", "",
          "| 指標 | " + " | ".join(f"{lab}(n={NB.get(k, 0)})" for k, lab in pairs) + " |", "|---|" + "---|" * len(pairs)]
    for key, label in (("cer", "字元 CER(主)"), ("pcer", "拼音 CER(主)"), ("cer2", "字元 CER(副)"), ("pcer2", "拼音 CER(副)"),
                       ("poly_rate", "多音字讀對率"), ("fail_rate", "品管未過率")):
        L.append(line(label, [f"{_ci((CB.get(k) or {}).get(key))} / {M.evidence(NB.get(k, 0), (CB.get(k) or {}).get(key), 'asr').split('(')[0]}"
                              for k, _ in pairs]))
    L += ["", "注意:(a)(b)(c) 是辨識器文字層代理(聽不到電音感、語氣自然度;多音字吐回原字時判不出聲調),不等於人耳;自然度要靠 listen.md 三方盲聽。"
          "證據強度規則:n < 30 弱;差異區間含 0 弱;辨識器代理指標上限中;顯存為單次峰值。各組句數不同時,差異只用兩邊都有結果的句子。", "",
          "## 結論(主對話填)", "",
          "- 結論:<換 / 不換 / 只當第二引擎 / 注音標注有沒有用>",
          "- 理由:",
          "- 各項證據強度摘要:",
          "- 若「只當第二引擎」:適用句型 / 觸發條件:", ""]
    Path(path).write_text("\n".join(L), encoding="utf-8")


def pick_listen_multi(rows, engines=TRIO, k=20, seed=20261027):
    """各引擎都有結果的句子中挑 k 句:品管未過與否不一致 > 多音字判錯不一致 > 主辨識 CER 差距最大;不足隨機補。rows = {引擎: {n: 單句列}} -> [n]。"""
    common = sorted(set.intersection(*(set(rows[e]) for e in engines))) if engines else []

    def cer(r):
        c = r.get("cer")
        return c[0] / c[1] if c and c[1] else 0.0

    def score(n):
        rs = [rows[e][n] for e in engines]
        s = 0.0
        if len({r["failed"] for r in rs}) > 1:
            s += 3
        if len({"wrong" in r["poly"] for r in rs}) > 1:
            s += 2
        return s + max(cer(r) for r in rs) - min(cer(r) for r in rs)

    ranked = sorted(common, key=lambda n: (-score(n), n))
    top = [n for n in ranked if score(n) > 0][:k]
    rest = [n for n in common if n not in top]
    random.Random(seed).shuffle(rest)
    return sorted(top + rest[:k - len(top)])


def write_listen_multi(path, picks, items, rows, wav_of, engines=TRIO, seed=20261027):
    """多方盲聽清單:每句 A/B/C 三個音檔(引擎對應每句隨機),答案表在檔尾。wav_of(engine, n) -> 路徑。"""
    by_n = {x["n"]: x for x in items}
    rng = random.Random(seed)
    labels = "ABCDEFG"[:len(engines)]
    L = [f"# 配音引擎比武 {len(engines)} 方盲聽清單({len(picks)} 句)", "",
         f"同一句 {'、'.join(labels)} 對應哪個引擎每句隨機(先聽再看檔尾答案)。聽審不是必要條件;想抽聽就聽,記下哪個最自然、哪個唸錯。", "",
         "| # | 句子 | " + " | ".join(labels) + " | 你覺得最好 | 備註 |", "|---|---|" + "---|" * len(labels) + "---|---|"]
    key = []
    for i, n in enumerate(picks, 1):
        order = list(engines)
        rng.shuffle(order)
        txt = by_n.get(n, {}).get("mtext", "").replace("|", "／")
        L.append(f"| {i} | {txt} | " + " | ".join(f"[{lab}]({_uri(wav_of(e, n))})" for lab, e in zip(labels, order)) + " |  |  |")
        key.append(f"| {i} | " + "、".join(f"{lab}={NAMES[e]}" for lab, e in zip(labels, order)) + " | "
                   + " | ".join(_brief(rows[e][n]) for e in engines) + " |")
    L += ["", "## 答案與程式判定(聽完再看)", "", "| # | 對應 | " + " | ".join(NAMES[e] for e in engines) + " |",
          "|---|---|" + "---|" * len(engines), *key, ""]
    Path(path).write_text("\n".join(L), encoding="utf-8")


# ------------------------------------------------------------ 聽審清單
def pick_listen(rows_a, rows_b, k=20, seed=20261027):
    """兩引擎都有結果的句子中挑 k 句:品管一過一不過 > 多音字一邊判錯 > 主辨識 CER 差最大;不足隨機補。-> [n]。"""
    common = sorted(set(rows_a) & set(rows_b))

    def cer(r):
        c = r.get("cer")
        return c[0] / c[1] if c and c[1] else 0.0

    def score(n):
        a, b = rows_a[n], rows_b[n]
        s = 0.0
        if a["failed"] != b["failed"]:
            s += 3
        if ("wrong" in a["poly"]) != ("wrong" in b["poly"]):
            s += 2
        return s + abs(cer(a) - cer(b))

    ranked = sorted(common, key=lambda n: (-score(n), n))
    top = [n for n in ranked if score(n) > 0][:k]
    rest = [n for n in common if n not in top]
    random.Random(seed).shuffle(rest)
    return sorted(top + rest[:k - len(top)])


def write_listen(path, picks, items, rows_a, rows_b, wav_of, seed=20261027):
    """A/B 盲聽清單:每句 A、B 兩個音檔(引擎隨機對應),答案表在檔尾。wav_of(engine, n) -> 路徑字串。"""
    by_n = {x["n"]: x for x in items}
    rng = random.Random(seed)
    L = ["# 配音引擎比武 A/B 抽聽清單(20 句)", "",
         "同一句兩個引擎並列,A/B 對應哪個引擎每句隨機(先聽再看檔尾答案)。聽審不是必要條件;想抽聽就聽,記下哪邊比較自然、哪邊唸錯。", "",
         "| # | 句子 | A | B | 你覺得較好(A/B/一樣) | 備註 |", "|---|---|---|---|---|---|"]
    key = []
    for i, n in enumerate(picks, 1):
        swap = rng.random() < 0.5
        ea, eb = ("indextts2", "cosy3") if swap else ("cosy3", "indextts2")
        txt = by_n.get(n, {}).get("mtext", "").replace("|", "／")
        L.append(f"| {i} | {txt} | [A]({_uri(wav_of(ea, n))}) | [B]({_uri(wav_of(eb, n))}) |  |  |")
        ra, rb = (rows_a[n], rows_b[n])
        key.append(f"| {i} | A={NAMES[ea]}、B={NAMES[eb]} | {_brief(ra)} | {_brief(rb)} |")
    L += ["", "## 答案與程式判定(聽完再看)", "", "| # | 對應 | CosyVoice3 | IndexTTS2 |", "|---|---|---|---|", *key, ""]
    Path(path).write_text("\n".join(L), encoding="utf-8")


def _uri(p):
    return "file:///" + str(p).replace("\\", "/").lstrip("/")


def _brief(r):
    c = r.get("cer")
    cer = f"CER {c[0] / c[1] * 100:.0f}%" if c and c[1] else "CER -"
    q = "品管未過:" + ",".join(r["fails"][:3]) if r["failed"] else "品管過"
    p = f";多音字錯 {r['poly'].count('wrong')}" if "wrong" in r["poly"] else ""
    return f"{q};{cer}{p}"
