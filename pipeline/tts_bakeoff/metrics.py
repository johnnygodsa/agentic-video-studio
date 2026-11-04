"""比武指標純函式(標準函式庫;讀音/正規化/多音字判定都由呼叫端注入,測試不需 pypinyin/opencc/模型)。

(a) 字元 CER / 拼音 CER   語料層 micro:sum(編輯距離) / sum(參考長度);ref = 量測文字(measure_text),hyp = 主/副辨識文字,兩邊同一個正規化
(b) 多音字讀對率          pron_rules.json 命中位置的判定(tts_pron_verify.judge_record 的 positions):對 / (對 + 錯),另列無法判定數
(c) 品管未過句數          tts_cosy3 驗證後 qc 紀錄 passed=False 的句數與原因分布
(d) 每句秒數             合成牆鐘秒數(子行程回應時間)
(e) 顯存峰值             子行程 torch 峰值與 nvidia-smi 取樣差值取大者
(f) 時長控制誤差          (實際 - 目標) / 目標;目標 = 同句 CosyVoice 實際時長
兩引擎的差異用成對 bootstrap(同一批句子重抽)給 95% 區間,證據強度依樣本數、區間是否含 0、是否為辨識器代理指標判定。
"""
import random
import statistics


# ------------------------------------------------------------ 編輯距離與 CER
def edit_distance(a, b):
    """Levenshtein(替換/插入/刪除各 1);a、b 可以是字串或 list。"""
    a, b = list(a), list(b)
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def cer_counts(ref, hyp, norm=None):
    """-> (編輯數, 參考長度);hyp 為 None(沒有辨識結果)回 None。"""
    if hyp is None:
        return None
    norm = norm or (lambda s: s)
    r, h = norm(ref), norm(hyp)
    return edit_distance(r, h), len(r)


def pinyin_cer_counts(ref, hyp, py_seq, norm=None):
    """拼音含聲調 CER:正規化後逐字轉 tone3 音節序列再算編輯距離。py_seq(str) -> [音節]。"""
    if hyp is None:
        return None
    norm = norm or (lambda s: s)
    r, h = py_seq(norm(ref)), py_seq(norm(hyp))
    return edit_distance(r, h), len(r)


def micro(counts):
    """[(編輯, 長度) | None] -> 比率(忽略 None;總長 0 回 None)。"""
    c = [x for x in counts if x]
    n = sum(x[1] for x in c)
    return sum(x[0] for x in c) / n if n else None


# ------------------------------------------------------------ 多音字
def poly_summary(verdicts):
    """位置級判定 list(right / wrong / undetermined)-> dict(right, wrong, undetermined, n, rate);rate = 對 / (對 + 錯)。"""
    c = {k: sum(1 for v in verdicts if v == k) for k in ("right", "wrong", "undetermined")}
    dec = c["right"] + c["wrong"]
    return dict(c, n=len(verdicts), rate=c["right"] / dec if dec else None)


# ------------------------------------------------------------ 時長控制
def dur_error(target, actual):
    """相對誤差 (實際 - 目標) / 目標;任一缺或目標 <= 0 回 None。"""
    if not target or actual is None or target <= 0:
        return None
    return (actual - target) / target


def _pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def dur_summary(errs):
    """相對誤差 list -> dict(n, mean_abs, median_abs, p90_abs, mean_signed, within5, within10)(比例,非百分比)。"""
    e = [x for x in errs if x is not None]
    if not e:
        return dict(n=0)
    a = [abs(x) for x in e]
    return dict(n=len(e), mean_abs=statistics.fmean(a), median_abs=statistics.median(a), p90_abs=_pct(a, 0.9),
                mean_signed=statistics.fmean(e), within5=sum(x <= 0.05 for x in a) / len(a),
                within10=sum(x <= 0.10 for x in a) / len(a))


# ------------------------------------------------------------ 區間與證據強度
def bootstrap_ci(items, stat, b=2000, seed=20261027, alpha=0.05):
    """items 重抽(放回)b 次,stat(子樣本) 的 (點估計, 下界, 上界);stat 回 None 的抽樣略過。items 空回 (None, None, None)。"""
    if not items:
        return None, None, None
    point = stat(items)
    rng = random.Random(seed)
    n, vals = len(items), []
    for _ in range(b):
        v = stat([items[rng.randrange(n)] for _ in range(n)])
        if v is not None:
            vals.append(v)
    if not vals:
        return point, None, None
    return point, _pct(vals, alpha / 2), _pct(vals, 1 - alpha / 2)


def paired_diff_ci(pairs, stat, **kw):
    """成對差異:pairs = [(A 的單句資料, B 的單句資料)],stat(list) -> 值;回傳 B - A 的 (點估計, 下界, 上界)。"""
    def d(sub):
        a, b = stat([p[0] for p in sub]), stat([p[1] for p in sub])
        return None if a is None or b is None else b - a
    return bootstrap_ci(pairs, d, **kw)


def evidence(n, ci=None, kind="asr"):
    """證據強度標籤。kind:asr = 辨識器文字層代理(上限「中」);measured = 直接量測(秒數、時長);single = 單次量測(顯存峰值)。
    ci = (點, 下, 上) 的差異區間;區間含 0 = 弱。"""
    if not n:
        return "無(沒有資料)"
    if n < 30:
        return f"弱(n={n} < 30)"
    if kind == "single":
        return f"中(單次峰值實測,n={n} 句同一行程)"
    if ci is not None:
        lo, hi = ci[1], ci[2]
        if lo is None or hi is None:
            return f"弱(n={n},區間算不出)"
        if lo <= 0 <= hi:
            return f"弱(n={n},差異 95% 區間含 0)"
        if kind == "asr":
            return f"中(n={n},差異 95% 區間不含 0;辨識器文字層代理,非人耳)"
        return f"強(n={n},差異 95% 區間不含 0,實測)" if n >= 200 else f"中(n={n},差異 95% 區間不含 0,實測)"
    if kind == "asr":
        return f"中(n={n};辨識器文字層代理,非人耳)"
    return f"強(n={n},實測)" if n >= 200 else f"中(n={n},實測)"


# ------------------------------------------------------------ 單句列與引擎彙總
def sentence_row(rec, norm, py_seq, poly=None):
    """一筆 tts_cosy3 qc 紀錄 -> 單句指標列。poly = 該句多音字位置判定 list。"""
    ref = rec.get("measure_text") or rec.get("text") or ""
    return dict(cer=cer_counts(ref, rec.get("asr"), norm), pcer=pinyin_cer_counts(ref, rec.get("asr"), py_seq, norm),
                cer2=cer_counts(ref, rec.get("asr2"), norm), pcer2=pinyin_cer_counts(ref, rec.get("asr2"), py_seq, norm),
                failed=not rec.get("passed"), fails=list(rec.get("fails") or []), poly=list(poly or []),
                spk_sim=rec.get("spk_sim"), dur=rec.get("dur"), asr2_bad=bool(rec.get("asr2_bad")))


def _fail_rate(rows):
    return sum(r["failed"] for r in rows) / len(rows) if rows else None


def _poly_rate(rows):
    return poly_summary([v for r in rows for v in r["poly"]])["rate"]


STATS = {   # 指標鍵 -> 由單句列算整體值的函式(成對 bootstrap 共用)
    "cer": lambda rows: micro(r["cer"] for r in rows),
    "pcer": lambda rows: micro(r["pcer"] for r in rows),
    "cer2": lambda rows: micro(r["cer2"] for r in rows),
    "pcer2": lambda rows: micro(r["pcer2"] for r in rows),
    "fail_rate": _fail_rate,
    "poly_rate": _poly_rate,
}


def pron_fail_count(rows):
    """品管未過原因裡有 pron 類(pron = 單句 pron_rule_bad 位置回查失敗)的句數。"""
    return sum(any(f.startswith("pron") for f in r["fails"]) for r in rows)


def engine_summary(rows):
    """單句列 list -> 引擎整體指標。"""
    fails = {}
    for r in rows:
        for f in r["fails"]:
            fails[f] = fails.get(f, 0) + 1
    spk = [r["spk_sim"] for r in rows if r["spk_sim"] is not None]
    return dict(n=len(rows), **{k: f(rows) for k, f in STATS.items()},
                failed=sum(r["failed"] for r in rows), pron_fail=pron_fail_count(rows), fail_reasons=dict(sorted(fails.items(), key=lambda x: -x[1])),
                poly=poly_summary([v for r in rows for v in r["poly"]]), asr2_bad=sum(r["asr2_bad"] for r in rows),
                spk_sim_median=statistics.median(spk) if spk else None)


def compare(rows_a, rows_b):
    """兩引擎同一批句子(dict n -> 單句列)-> {指標: (B-A 點估計, 下界, 上界)},只用兩邊都有的句子。"""
    common = sorted(set(rows_a) & set(rows_b))
    pairs = [(rows_a[n], rows_b[n]) for n in common]
    return {k: paired_diff_ci(pairs, f) for k, f in STATS.items()}, len(common)


def time_summary(secs, durs=None):
    """每句合成秒數 -> dict(n, mean, median, p90, rtf);durs 給了就算 RTF = 總合成秒 / 總音長。"""
    s = [x for x in secs if x is not None]
    if not s:
        return dict(n=0)
    out = dict(n=len(s), mean=statistics.fmean(s), median=statistics.median(s), p90=_pct(s, 0.9))
    if durs:
        d = sum(x for x in durs if x)
        out["rtf"] = sum(s) / d if d else None
    return out
