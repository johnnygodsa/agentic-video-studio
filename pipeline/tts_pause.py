"""句中停頓(逗號、頓號、分號、冒號)的量測與修整,以及「辨識字詞時間 -> 原文每個字的時間」對齊。
只用 numpy 與標準函式庫(不需顯示卡;build.py 與 tts_chattts.py 都會載入)。

背景(2026-10-11 使用者聽 dei 樣片):一個配音單位是一個句子,句中逗號由 ChatTTS 自己決定停不停,常常前後黏在一起。
作法:品管本來就會跑的語音辨識給出字詞時間 -> 與已知文本對齊(辨識結果只拿來取時間,不當顯示文字)-> 找出每個句中標點
在音檔裡的位置 -> 在該位置附近量靜音長度 -> 太短先換 seed 重錄(tts_chattts 的重錄迴圈),仍不足就在靜音/能量最低點插入靜音,
太長就從靜音中段剪掉。對齊得到的每字時間另存進品管紀錄(say_t),build.py 的字幕分段用它取代等比例分配。

2026-10-11 使用者聽 dei v1 後補的兩項(都作用在最終音檔):
  多餘停頓(stray):不在句中標點位置的靜音 >= STRAY_MIN 秒(「聽聽看 就好」「當 一次」)。find_strays 量測 -> 先換 seed 重錄,
    仍有就 fix_strays 把那段靜音剪到 STRAY_KEEP 秒,接點做 STRAY_FADE 秒交叉淡化。
    實測使用者指出的那兩處只有 0.10 與 0.09 秒(門檻 = 峰值 - 35dB),所以另設 STRAY_TRIM_MIN:
    STRAY_TRIM_MIN 以上、未達 STRAY_MIN 的不重錄(聲音會變),只剪短。
  停頓內的雜音:[uv_break] 處模型會產生換氣聲/雜音(低於靜音門檻所以量測時算在停頓內,聽得到)。clean_pauses 把每個
    句中停頓的內部換成數位靜音(兩端各留 PAUSE_EDGE 秒淡出淡入);clean_tail 處理句尾(犧牲尾綴切除處)能量回升的雜音。
"""
import difflib
import json
import re

import numpy as np

COMMA_MIN = 0.10        # 句中停頓的實際靜音下限(秒);不足 -> comma_short(重錄,仍不足就插入靜音)
COMMA_MAX = 0.22        # 上限;超過就從靜音中段剪到這個長度
COMMA_TARGET = 0.20     # 插入靜音時補到這個長度(cosy3)。靠插入補的逗號沒有韻律邊界,要比自然中位(0.155)長(2026-10-31 由 0.14 上調)
COMMA_TARGET_CHATTTS = 0.14   # tts_chattts 維持舊值(有 [uv_break]、行為不變)
COMMA_RUNON_MIN = 0.05  # 非頓號句中標點的原始靜音(後處理前)低於這個長度 = 模型連讀(comma_runon,cosy3):插靜音救不回韻律,換 seed 重錄,用完仍有 = 未過
RUNON_PENALTY = 0.3     # comma_runon 每處扣的品管分數
# 逗號停頓側寫(--comma-profile):std = 上面三個常數(預設,行為不變);long = 長句(子句 >= 3 或 >= 35 字)用較長的停頓,
# 2026-10-26 觀眾說旁白「流暢度是災難」(長句句內太趕),僅供本機 A/B 試聽,使用者聽過再決定是否採用。
PROFILES = {"std": dict(COMMA_MIN=0.10, COMMA_MAX=0.22, COMMA_TARGET=0.20),
            "long": dict(COMMA_MIN=0.16, COMMA_MAX=0.38, COMMA_TARGET=0.26)}
LONG_CLAUSES = 3        # long 側寫:一個配音單位的子句數(以 ,，;； 切)達到這個數,或字數 >= LONG_CHARS,視為長句
LONG_CHARS = 35
COMMA_WIN = 0.15        # 在對齊位置前後這麼多秒內找停頓
COMMA_REL_DB = 35.0     # 低於該句峰值這麼多 dB 算靜音(與語速品管的有聲判定同一條線)
COMMA_DIP_DB = 12.0     # 完全沒有靜音時,能量最低點至少比附近語音低這麼多 dB 才算「有低谷」可以插入靜音;否則 comma_bad
COMMA_FADE = 0.012      # 插入/剪除處兩側的淡出淡入秒數
COMMA_RETRY = 3         # 只差句中停頓且補得起來的單位,最多為它重錄幾次(計入 --max-retry);補不起來的照常錄到 --max-retry
HEAD_SEC = 1.5          # 插入位置驗證:辨識插入靜音中點之前這麼多秒(結尾要對到停頓標點前的字;2026-10-30 bioware_dei 001 插錯位置)
STRAY_MIN = 0.12        # 非標點處的靜音達到這個長度 = 多餘停頓(stray_pause:先換 seed 重錄,仍有就剪短)
STRAY_TRIM_MIN = 0.085  # 達到這個長度就剪短(不重錄);dei v1 使用者指出的兩處實測 0.10、0.09 秒
STRAY_KEEP = 0.04       # 多餘停頓剪短後留下的靜音長度
STRAY_WB_KEEP = 0.10    # 詞邊界(word_bounds)的靜音:<= 這個長度是自然斷口不算多餘停頓;超過的只剪到這個長度、不算品管未過(2026-10-29)
STRAY_WB_FAIL = 0.20    # 詞邊界的靜音 >= 這個長度 = 自發長停頓(像多出一個逗號):tts_cosy3 記 stray_pause 未過、先換 seed 重錄;
                        # 重錄用完仍有,剪到 STRAY_WB_KEEP 但仍算未過(2026-10-30,依據見 docs/tts.md §4.1)
STRAY_FADE = 0.012      # 剪接點交叉淡化的秒數
STRAY_UNSURE = 0.40     # 某個句中標點找不到靜音(對齊位置不可信)時,它前後這麼多秒內的靜音不當多餘停頓(可能就是那個逗號)
PAUSE_EDGE = 0.015      # 清除停頓內部雜音時,兩端各留這麼長做淡出/淡入
PAUSE_CLEAN_DB = -55.0  # 清除後停頓內部的 RMS 應低於這個值(dBFS;品管紀錄 pause_clean 的 after)
TAIL_RISE_DB = 6.0      # 句尾靜音區內,能量比先前的最低點回升這麼多 dB 以上 = 換氣聲/雜音,從回升處起清掉
TAIL_FLOOR_DB = -60.0   # 低於這個值(dBFS)的起伏不算回升
HOP = 0.005
PAUSE_MARKS = set("，,、；;：:")
# 軟停頓(2026-10-29):列舉的頓號(人類、矮人、獸人)引擎常不停,是自然唸法;不足時有低谷(fixable)才插靜音,沒有就略過,
# 不算 comma_short / comma_bad(對齊改用 Qwen3-ForcedAligner 後位置準了才抓得到,不該為它重錄)
SOFT_MARKS = set("、")
_UNIT_RE = re.compile(r"[A-Za-z]+|[0-9]|[一-鿿]")
_DIG = dict(zip("0123456789", "零一二三四五六七八九"))


# ------------------------------------------------------------ 對齊
def units(text):
    """發音單位 [(字串, 起始字元位置, 結束字元位置)]:中文一字一個、英文一個單字一個、數字一位一個;標點與空白不算。"""
    return [(m.group(), m.start(), m.end()) for m in _UNIT_RE.finditer(text)]


def hyp_units(words):
    """辨識字詞 [(字詞, 起, 迄)] -> [(單位, 起, 迄)]:一個字詞內的各單位等分它的時間;阿拉伯數字換成中文數字方便對位。"""
    out = []
    for word, s, e in words:
        us = _UNIT_RE.findall(word)
        for k, u in enumerate(us):
            out.append((_DIG.get(u, u), s + (e - s) * k / len(us), s + (e - s) * (k + 1) / len(us)))
    return out


def align(ref, hyp, dur, key=None):
    """ref = 原文的單位字串清單,hyp = hyp_units 的結果。回傳 (每個原文單位的 [起, 迄], 是否對到辨識字)。
    對不到的單位(辨識漏字、寫成別的字)在前後對得到的單位之間等分。key:比對用的鍵(tts_chattts 傳拼音,同音字也算對到)。"""
    key = key or (lambda u: u.lower())
    sm = difflib.SequenceMatcher(None, [key(u) for u in ref], [key(u) for u, _, _ in hyp], autojunk=False)
    n = len(ref)
    t = [None] * n
    for i, j, size in sm.get_matching_blocks():
        for d in range(size):
            t[i + d] = (hyp[j + d][1], hyp[j + d][2])
    matched = [x is not None for x in t]
    head = min(hyp[0][1], dur) if hyp else 0.0
    tail = min(hyp[-1][2], dur) if hyp else dur
    i = 0
    while i < n:
        if t[i] is not None:
            i += 1
            continue
        j = i
        while j < n and t[j] is None:
            j += 1
        lo = t[i - 1][1] if i else head
        hi = max(lo, t[j][0] if j < n else tail)
        for d in range(i, j):
            t[d] = (lo + (hi - lo) * (d - i) / (j - i), lo + (hi - lo) * (d - i + 1) / (j - i))
        i = j
    out, prev = [], 0.0
    for s, e in t:
        s = min(max(s, prev), dur)
        out.append([s, min(max(e, s), dur)])
        prev = s
    return out, matched


def char_map(a, b):
    """a 的每個字元位置(0..len(a))對到 b 的字元位置:相同的區段一對一,被替換的區段(@say、發音表、數字讀法)依比例。"""
    pos = [0] * (len(a) + 1)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        for p in range(i1, i2):
            pos[p] = j1 + (p - i1 if tag == "equal" else (p - i1) * (j2 - j1) // (i2 - i1))
    pos[len(a)] = len(b)
    return pos


def char_starts(text, times, dur, pauses=()):
    """text 每個字元位置的秒數(長度 len(text)+1):發音單位 = 它開始的時間(英文單字內依字母等分);標點與空白 = 前一個單位結束;
    句中停頓量到靜音時,標點 = 靜音開始、其後第一個字 = 靜音結束(字幕在下一段開口時換)。最後一項 = dur。"""
    us = units(text)
    st = [list(t) for t in times]
    for p in pauses:
        if p["sil"] > 0 and p["i"] + 1 < len(st):
            st[p["i"]][1], st[p["i"] + 1][0] = p["t0"], p["t1"]
    out = [0.0] * (len(text) + 1)
    prev, q = (st[0][0] if st else 0.0), 0
    for k, (_, a, b) in enumerate(us):
        for c in range(q, a):
            out[c] = prev
        s, e = st[k]
        for c in range(a, b):
            out[c] = s + (e - s) * (c - a) / (b - a)
        prev, q = e, b
    for c in range(q, len(text)):
        out[c] = prev
    out[len(text)] = dur
    for c in range(1, len(out)):
        out[c] = max(out[c], out[c - 1])
    return out


# ------------------------------------------------------------ 停頓量測
def comma_params(text, profile="std", std_target=None):
    """該單位文字適用的 dict(COMMA_MIN, COMMA_MAX, COMMA_TARGET)。std 一律回現行常數;long 只在長句(子句數 >= LONG_CLAUSES
    或字數 >= LONG_CHARS)回 long 值,短句仍回 std 值。std_target:覆寫 std 值的插入目標(tts_chattts 傳 COMMA_TARGET_CHATTTS)。"""
    if profile not in PROFILES:
        raise ValueError(f"unknown comma profile: {profile}")
    std = dict(COMMA_MIN=COMMA_MIN, COMMA_MAX=COMMA_MAX, COMMA_TARGET=std_target or COMMA_TARGET)
    if profile == "std" or not text:
        return std
    clauses = [c for c in re.split(r"[,，;；]", text) if units(c)]
    if len(clauses) >= LONG_CLAUSES or len(units(text)) >= LONG_CHARS:
        return dict(PROFILES[profile])
    return std


def soft_skip(p):
    """軟停頓(頓號)不足且補不起來(沒有低谷):不插、不列 comma_short / comma_bad。"""
    return bool(p.get("soft")) and not fixable(p)


def out_of_range(pauses, text=None, profile="std"):
    """有任何一處句中停頓不在該單位適用的 [COMMA_MIN, COMMA_MAX] 內(決定要不要跑 fix_pauses;soft_skip 的不算)。"""
    cp = comma_params(text, profile)
    return any(not cp["COMMA_MIN"] <= p["sil"] <= cp["COMMA_MAX"] for p in pauses
               if not (p["sil"] < cp["COMMA_MIN"] and soft_skip(p)))


def comma_bad(pauses, text=None, profile="std"):
    """修整後仍低於該單位適用下限的停頓位置 ["前一字|後一字"];軟停頓(頓號)不算。"""
    lo = comma_params(text, profile)["COMMA_MIN"]
    return [p["at"] for p in pauses if p["sil"] < lo and not p.get("soft")]


def comma_runon(pauses):
    """模型連讀的句中標點 [dict(at, before)]:原始音檔(後處理前)的靜音 < COMMA_RUNON_MIN;頓號(soft)不算。"""
    return [dict(at=p["at"], before=p["sil"]) for p in pauses or [] if p["sil"] < COMMA_RUNON_MIN and not p.get("soft")]


def runon_from_rec(rec):
    """既有品管紀錄的連讀處(最終音檔已插過靜音,不能重量):有 comma_runon 欄位就用它;舊紀錄用 pause_fix 的 before
    (與 pauses 逐筆對應,soft 從 pauses 取);都沒有回 [](不判)。"""
    if not rec:
        return []
    if "comma_runon" in rec:
        return rec["comma_runon"] or []
    return comma_runon([dict(at=x["at"], sil=x["before"], soft=p.get("soft"))
                        for x, p in zip(rec.get("pause_fix") or [], rec.get("pauses") or [])])


def judge_runon(m):
    """品管項 comma_runon(check 算完 fails/score 後呼叫):只在原始音檔量一次,後處理重量測的 m 沿用,插入靜音過不了關;
    verify 舊音檔由呼叫端先放好 runon_from_rec 的結果。不在 POST_FIXABLE,comma_only 為假,重錄迴圈不提早停。"""
    if "comma_runon" not in m:
        m["comma_runon"] = comma_runon(m.get("pauses"))
    if m["comma_runon"]:
        m["fails"].append("comma_runon")
        m["score"] = round(m["score"] - RUNON_PENALTY * len(m["comma_runon"]), 3)


def comma_inserted(rec):
    """靠插入靜音補的逗號位置 ["前一字|後一字"](品管紀錄;頓號不算),listen_page 優先聽用。"""
    ats = inserted_ats(rec)
    return [p["at"] for p in rec.get("pauses") or [] if p["at"] in ats and not p.get("soft")]


def attempt_rank(m):
    """挑最佳嘗試的排序鍵(大者佳):連讀處數少的優先,其次品管分數。"""
    return -len(m.get("comma_runon") or []), m["score"]


def retry_best(r, attempt, max_retry, stop):
    """主品管重錄迴圈:r = dict(w, m, ok, tries)。attempt(r) -> (w, m, ok) 合成並判定一次新嘗試,stop(m, 已重錄次數) 為真就不再換 seed;
    通過或 attempt_rank 較佳才換上。"""
    tries = 0
    while not r["ok"] and tries < max_retry:
        if stop(r["m"], tries):
            break
        w, m, ok = attempt(r)
        r["tries"].append(m)
        if ok or attempt_rank(m) > attempt_rank(r["m"]):
            r["w"], r["m"] = w, m
        r["ok"] = ok
        tries += 1


def frame_db(w, sr, hop=HOP):
    n = int(sr * hop)
    m = len(w) // n
    if m == 0:
        return np.zeros(0)
    return 10 * np.log10((np.asarray(w[: m * n], dtype=np.float64).reshape(m, n) ** 2).mean(axis=1) + 1e-12)


def find_pause(env, lo_t, hi_t, hop=HOP):
    """在 [lo_t, hi_t] 內找停頓:有靜音段(低於峰值 - COMMA_REL_DB)就取與這段時間重疊的最長那段(塞音閉鎖比真正的停頓短);
    沒有就取能量最低點(sil = 0)。dip = 該處比前後 0.3 秒內語音(第 90 百分位)低多少 dB。碰到檔頭/檔尾的靜音不算句中停頓。"""
    m = len(env)
    a, b = max(1, int(lo_t / hop)), min(m - 1, int(hi_t / hop) + 1)
    if b <= a:
        return dict(t0=lo_t, t1=lo_t, sil=0.0, dip=0.0)
    quiet = env < env.max() - COMMA_REL_DB
    best, k = None, a
    while k < b:
        if not quiet[k]:
            k += 1
            continue
        i = j = k
        while i > 0 and quiet[i - 1]:
            i -= 1
        while j < m and quiet[j]:
            j += 1
        if i > 0 and j < m and (best is None or j - i > best[1] - best[0]):
            best = (i, j)
        k = j
    if best:
        i, j = best
        kmin = i + int(np.argmin(env[i:j]))
    else:
        kmin = a + int(np.argmin(env[a:b]))
        i = j = kmin
    r = int(0.3 / hop)
    dip = float(np.percentile(env[max(0, kmin - r): kmin + r], 90) - env[kmin])
    if not best and (kmin == 0 or kmin >= m - 1 or quiet[kmin]):
        dip = 0.0   # 落在檔頭/檔尾的靜音上:對齊位置不可信,不拿來插入靜音
    return dict(t0=i * hop, t1=j * hop, sil=(j - i) * hop, dip=dip)


def measure_pauses(w, sr, text, times, soft_at=()):
    """text = 送配音的文字(prep_text 的結果),times = align 得到的各單位 [起, 迄]。
    每個句中停頓標點回傳一筆:i = 標點前那個單位的序號,at = "前一字|後一字",est = 對齊估計的交界秒,
    t0/t1 = 靜音起訖(沒有靜音時兩者都是能量最低點),sil = 靜音長度,dip 見 find_pause,
    soft = 兩單位之間的停頓標點只有頓號(SOFT_MARKS,或位置在 soft_at 內:prep_text 已把頓號換成逗號,由呼叫端從原文對回)。"""
    us = units(text)
    env = frame_db(w, sr)
    out = []
    for k in range(len(us) - 1):
        a, b = us[k][2], us[k + 1][1]
        marks = [q for q in range(a, b) if text[q] in PAUSE_MARKS]
        if not marks:
            continue
        soft = all(text[q] in SOFT_MARKS or q in soft_at for q in marks)
        end, start = times[k][1], times[k + 1][0]
        p = find_pause(env, min(end, start) - COMMA_WIN, max(end, start) + COMMA_WIN) if len(env) else \
            dict(t0=end, t1=end, sil=0.0, dip=0.0)
        out.append(dict(i=k, at=us[k][0] + "|" + us[k + 1][0], est=round((end + start) / 2, 3), t0=round(p["t0"], 3),
                        t1=round(p["t1"], 3), sil=round(p["sil"], 3), dip=round(p["dip"], 1), soft=soft))
    return out


def fixable(p):
    """停頓不足時能不能用插入靜音補:該處有(短的)靜音,或至少有明顯的能量低谷。兩字連音、沒有低谷的不補(會切在字中間)。"""
    return p["sil"] > 0 or p["dip"] >= COMMA_DIP_DB


def _join(a, b, sr, gap=0):
    a, b = a.copy(), b.copy()
    f = min(int(COMMA_FADE * sr), len(a), len(b))
    if f:
        ramp = np.linspace(1.0, 0.0, f, dtype=np.float32)
        a[-f:] *= ramp
        b[:f] *= ramp[::-1]
    return np.concatenate([a, np.zeros(gap, dtype=a.dtype), b])


def fix_pauses(w, sr, pauses, text=None, profile="std", edits=None, std_target=None):
    """依 measure_pauses 的結果修整波形(由後往前,前面的時間不受影響)。回傳 (新波形, {停頓的 i: "insert" | "trim"})。
    太短且 fixable -> 在靜音中點(沒有靜音就是能量最低點)插入靜音補到 COMMA_TARGET;太長 -> 從靜音中段剪到 COMMA_MAX。
    切點兩側各做 COMMA_FADE 秒淡出淡入。text/profile/std_target:見 comma_params(預設 std = 現行常數)。
    edits:給 list 就逐筆附上 dict(i, act, c = 原波形切點樣本, delta = 長度變化樣本數),給 insert_mids 算插入點在新波形的位置。"""
    cp = comma_params(text, profile, std_target)
    c_min, c_max, c_target = cp["COMMA_MIN"], cp["COMMA_MAX"], cp["COMMA_TARGET"]
    acts = {}
    for p in sorted(pauses, key=lambda p: -p["t0"]):
        c = int(round(((p["t0"] + p["t1"]) / 2 + (HOP / 2 if p["sil"] <= 0 else 0.0)) * sr))
        if p["sil"] < c_min:
            if not fixable(p) or not 0 < c < len(w):
                continue
            gap = int(round((c_target - p["sil"]) * sr))
            w = _join(w[:c], w[c:], sr, gap)
            acts[p["i"]] = "insert"
            if edits is not None:
                edits.append(dict(i=p["i"], act="insert", c=c, delta=gap))
        elif p["sil"] > c_max:
            cut = int(round((p["sil"] - c_max + HOP) * sr))   # 多剪一格,重新量測時不會因為取整又超過上限
            w = _join(w[: c - cut // 2], w[c - cut // 2 + cut:], sr)
            acts[p["i"]] = "trim"
            if edits is not None:
                edits.append(dict(i=p["i"], act="trim", c=c, delta=-cut))
    return w, acts


def insert_mids(edits, sr):
    """fix_pauses(edits=) 的紀錄 -> {停頓的 i: 插入的靜音中點在新波形中的秒數}(前面各處插入/剪除造成的位移已計入)。"""
    out = {}
    for e in edits:
        if e["act"] == "insert":
            shift = sum(x["delta"] for x in edits if x["c"] < e["c"])
            out[e["i"]] = (e["c"] + shift + e["delta"] / 2) / sr
    return out


def load_qc(path):
    """品管紀錄 .qc.json;沒有或壞掉回 None。"""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def inserted_ats(rec):
    """舊品管紀錄裡插入過靜音的停頓位置 {"前一字|後一字"}(pause_fix act=insert,與驗證過的 pause_verify);
    verify=true 重驗舊音檔時用它決定要不要做插入位置驗證(沒插過的不驗、不重錄)。"""
    if not rec:
        return set()
    return {x["at"] for x in rec.get("pause_fix") or [] if x.get("act") == "insert"} |         {x["at"] for x in rec.get("pause_verify") or []}


def _weight(u):
    """單位的份量:英文算字母數,中文字算 3(約一個音節的字母數;同 tts_chattts._weight)。"""
    return len(u) if u.isascii() else 3


def head_match(ref, hyp, key=None):
    """插入位置驗證(純函式):插入的靜音之前那段音檔的辨識結尾,是否對到原文該停頓標點前的字。
    ref = 原文從句首到標點前那個字的發音單位(units 的字串),hyp = 前段辨識結果的單位(英文別名已換回原文詞)。
    key = 比對鍵(tts_cosy3 傳 tts_chattts._align_key 拼音模糊化,同音字也算對到)。回傳 True / False(插錯位置)/ None(判斷不了)。
    結尾是中文字:辨識最後一個單位要與它同鍵。結尾是英文詞(可連續數個):辨識結尾的英文與它相似度 >= 0.6;
    或英文前那個中文字在辨識裡找得到(取最後一次),其後的份量在英文字母數的 0.5 倍到 1.6 倍 + 3 之間(音譯,同 tail_ok);
    那個中文字找不到、或整段都是英文對不上 -> None。辨識空白 -> None。"""
    key = key or (lambda u: u.lower())
    if not ref or not hyp:
        return None
    if not ref[-1].isascii():
        return key(hyp[-1]) == key(ref[-1])
    k = max((n for n, u in enumerate(ref) if not u.isascii()), default=None)
    en = "".join(ref[(-1 if k is None else k) + 1:]).lower()
    n_en = 0
    while n_en < len(hyp) and hyp[len(hyp) - 1 - n_en].isascii():
        n_en += 1
    tail_en = "".join(hyp[len(hyp) - n_en:]).lower()
    if tail_en and difflib.SequenceMatcher(None, en, tail_en[-len(en) * 2:]).ratio() >= 0.6:
        return True
    if k is None:
        return None
    j = max((n for n, u in enumerate(hyp) if key(u) == key(ref[k])), default=None)
    if j is None:
        return None
    return 0.5 * len(en) <= sum(_weight(u) for u in hyp[j + 1:]) <= 1.6 * len(en) + 3


# ------------------------------------------------------------ 多餘停頓(非標點處)
def inner_runs(env):
    """句內的靜音段 [(起格, 迄格)]:低於峰值 - COMMA_REL_DB,且不碰檔頭/檔尾。"""
    if not len(env):
        return []
    quiet = env < env.max() - COMMA_REL_DB
    out, k, m = [], 0, len(env)
    while k < m:
        if not quiet[k]:
            k += 1
            continue
        j = k
        while j < m and quiet[j]:
            j += 1
        if k > 0 and j < m:
            out.append((k, j))
        k = j
    return out


def word_bounds(text):
    """詞邊界:jieba 斷 units(text) 串起來的字串,回傳發音單位序號集合 {k: 單位 k 與 k+1 之間是詞邊界};
    英文單字、數字各一個單位(只看單位交界,jieba 切在單位內部的不算)。jieba 不可用回 None(find_strays 照舊)。"""
    jb = _jieba()
    if jb is None:
        return None
    us = [u[0] for u in units(text)]
    ends, pos = set(), 0
    for tok in jb.cut("".join(us)):
        pos += len(tok)
        ends.add(pos)
    out, pos = set(), 0
    for k, u in enumerate(us[:-1]):
        pos += len(u)
        if pos in ends:
            out.add(k)
    return out


_JB = []


def _jieba():
    """延遲載入 jieba(只載一次);字典快取放 repo 的 tmp\\(不寫 C 槽)。失敗回 None。"""
    if not _JB:
        try:
            import logging
            import os
            import jieba
            jieba.setLogLevel(logging.WARNING)
            tmp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp")
            os.makedirs(tmp, exist_ok=True)
            jieba.dt.tmp_dir = tmp
            _JB.append(jieba)
        except Exception:  # noqa: BLE001  沒裝或載入失敗:退回不分詞
            _JB.append(None)
    return _JB[0]


def stray_keep(s):
    """該筆多餘停頓剪短後留下的靜音長度:詞邊界 STRAY_WB_KEEP,詞中 STRAY_KEEP。"""
    return STRAY_WB_KEEP if s.get("kind") == "wb" else STRAY_KEEP


def wb_long(strays):
    """詞界自發長停頓(kind="wb"、sil >= STRAY_WB_FAIL)的位置 [at];tts_cosy3 記 stray_pause 未過、先換 seed。"""
    return [x["at"] for x in strays or [] if x.get("kind") == "wb" and x["sil"] >= STRAY_WB_FAIL - 1e-9]


def find_strays(w, sr, text, times, pauses, min_sil=STRAY_TRIM_MIN, bounds=None):
    """不在句中標點位置的靜音(>= min_sil 秒;其中 sil >= STRAY_MIN 的才算品管未過)。text/times/pauses 與 measure_pauses 相同。
    算「在標點位置」:與該標點量到的靜音 [t0, t1] 重疊,或落在對齊估計位置 est 前後 COMMA_WIN 秒內;
    標點沒量到靜音時(sil = 0,對齊可能偏掉)放寬到 est 前後 STRAY_UNSURE 秒。
    bounds(word_bounds 的結果):靜音落在詞邊界(單位 k 與 k+1 之間、k 在 bounds 內)的 kind="wb",<= STRAY_WB_KEEP 不列;
    其餘 kind="mid"。bounds=None 時全部是 mid(與舊版相同)。
    回傳 [dict(at="前一字|後一字", t0, t1, sil, kind)]。"""
    us = units(text)
    out = []
    for i, j in inner_runs(frame_db(w, sr)):
        t0, t1 = i * HOP, j * HOP
        if t1 - t0 < min_sil - 1e-9:
            continue
        at_mark = False
        for p in pauses:
            win = COMMA_WIN if p["sil"] > 0 else STRAY_UNSURE
            lo, hi = p["est"] - win, p["est"] + win
            if p["sil"] > 0:
                lo, hi = min(lo, p["t0"]), max(hi, p["t1"])
            if t0 < hi and t1 > lo:
                at_mark = True
                break
        if at_mark:
            continue
        mid = (t0 + t1) / 2
        k = max((n for n in range(len(times)) if times[n][0] < mid), default=0)
        at = us[k][0] + "|" + (us[k + 1][0] if k + 1 < len(us) else "") if us else ""
        kind = "wb" if bounds is not None and k + 1 < len(us) and k in bounds else "mid"
        if kind == "wb" and t1 - t0 <= STRAY_WB_KEEP + 1e-9:
            continue
        out.append(dict(at=at, t0=round(t0, 3), t1=round(t1, 3), sil=round(t1 - t0, 3), kind=kind))
    return out


def fix_strays(w, sr, strays):
    """把多餘停頓剪到 stray_keep 秒(詞中 STRAY_KEEP、詞邊界 STRAY_WB_KEEP;由後往前):從靜音中段拿掉多的部分,
    接點做 STRAY_FADE 秒交叉淡化。回傳 (新波形, 實際剪了幾處)。"""
    f = int(STRAY_FADE * sr)
    n = 0
    for s in sorted(strays, key=lambda s: -s["t0"]):
        cut = int(round((s["sil"] - stray_keep(s)) * sr))
        a = int(round((s["t0"] + s["t1"]) / 2 * sr)) - (cut - f) // 2
        b = a + cut - f
        if cut <= f or a < f or len(w) - b < f:
            continue
        ramp = np.linspace(1.0, 0.0, f, dtype=np.float32)
        w = np.concatenate([w[: a - f], w[a - f: a] * ramp + w[b: b + f] * ramp[::-1], w[b + f:]]).astype(w.dtype)
        n += 1
    return w, n


# ------------------------------------------------------------ 停頓內的雜音
def rms_db(x):
    """dBFS;空的或全零回傳 -120。"""
    return float(10 * np.log10(float(np.mean(np.asarray(x, dtype=np.float64) ** 2)) + 1e-12)) if len(x) else -120.0


def clean_pauses(w, sr, pauses):
    """把每個量到靜音的句中停頓 [t0, t1] 內部換成數位靜音,兩端各留 PAUSE_EDGE 秒淡出/淡入(長度不變)。
    回傳 (新波形, [dict(at, before, after)]):before/after = 內部(不含兩端淡化區)處理前後的 RMS dBFS。太短的不動、不列。"""
    e = int(PAUSE_EDGE * sr)
    out, log = w.copy(), []
    ramp = np.linspace(1.0, 0.0, e, dtype=np.float32)
    for p in pauses:
        a, b = int(round(p["t0"] * sr)), int(round(p["t1"] * sr))
        if p["sil"] <= 0 or b - a <= 2 * e or a < 0 or b > len(out):
            continue
        before = rms_db(out[a + e: b - e])
        out[a: a + e] *= ramp
        out[a + e: b - e] = 0.0
        out[b - e: b] *= ramp[::-1]
        log.append(dict(at=p.get("at", ""), before=round(before, 1), after=round(rms_db(out[a + e: b - e]), 1)))
    return out, log


def clean_tail(w, sr):
    """句尾靜音區(最後一段語音之後)若能量先降後升(比先前最低點高 TAIL_RISE_DB 以上,且高於 TAIL_FLOOR_DB)= 換氣聲或
    犧牲尾綴切除處的雜音:從回升處前 PAUSE_EDGE 秒起淡出,其後換成數位靜音(長度不變)。回傳 (新波形, 清掉的毫秒數;0 = 沒動)。"""
    env = frame_db(w, sr)
    m = len(env)
    if m < 4:
        return w, 0
    quiet = env < env.max() - COMMA_REL_DB
    k = m
    while k > 0 and quiet[k - 1]:
        k -= 1
    if k == 0 or k >= m - 1:
        return w, 0
    low = env[k]
    for i in range(k + 1, m):
        if env[i] > low + TAIL_RISE_DB and env[i] > TAIL_FLOOR_DB:
            c = int(i * HOP * sr)
            e = min(int(PAUSE_EDGE * sr), c)
            out = w.copy()
            out[c - e: c] *= np.linspace(1.0, 0.0, e, dtype=np.float32)
            out[c:] = 0.0
            return out, int(round((len(w) - c) / sr * 1000))
        low = min(low, env[i])
    return w, 0
