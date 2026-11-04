"""多音字規則實測回查(PLAN_多音字規則_2026-10-21 §3 #2):對 pron_rules.json 每條「非預設讀音」規則,取命中它的真實文案句子
(沒有就用規則詞造句,標 synthetic)× 多個 seed 用 CosyVoice3 合成,再用雙辨識(tts_asr 主 / 副)回查,每個規則位置判定:
  唸錯       主或副辨識把該字聽成「它另一個讀音」的字(著 -> 住,應讀 zháo)
  唸對       辨識成預期讀音的其他同音字,或兩個辨識的相似度都過且無 pron_bad
  無法判定   辨識回原字(文字層看不出聲調),或相似度沒過、對位失敗
寫 tmp\\pron_verify_<日期>.md(唸錯的規則排最前面);工作檔在 tmp\\pron_verify\\<日期>\\,不寫 build\\ 快取。
判定結果同時寫進語境讀音記憶(pron_memory.record_tests,與 tts_c0 共用;--judge-only 重跑不重複累計)。

用法(tts_env_chattts 的 python):
  python -X utf8 pipeline\\tts_pron_verify.py --date 2026-10-21 --dry-run      只印規則/句數/預估時間,不碰模型
  python -X utf8 pipeline\\tts_pron_verify.py --date 2026-10-21                 合成 + 回查 + 報告(顯示卡不空會中止)
  python -X utf8 pipeline\\tts_pron_verify.py --date 2026-10-21 --judge-only    只讀已有的 qc 紀錄重出報告
  --only 著,得  只驗這幾個字;--max-retry N  tts_cosy3 的重錄上限(預設 0 = 看第一個 seed 的原始讀音,不讓品管換 seed 蓋掉)
判定純函式(judge_record)不載模型,測試見 tests\\test_tts_pron_verify.py。"""
import argparse
import difflib
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gpu_lock as GL  # noqa: E402
import paths as P  # noqa: E402
import pron_memory as PM  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import tts_pron  # noqa: E402

SEC_PER_SENT = 15          # 預估每句(含雙辨識)秒數
VRAM_BUSY = 3000           # MiB,同 tts_cosy3.VRAM_MAX
SIM_MIN = 0.85
SENT_MIN, SENT_MAX = 8, 40
SYNTH_TEMPLATES = ("大家都在討論{w}這件事。", "這時候最重要的就是{w}。", "他剛剛提到了{w}這個說法。")
GPU_PROC_RE = r"cosy3_worker|make_version|tts_cosy3|tts_chattts"
VERDICT_ORDER = {"wrong": 0, "undetermined": 1, "right": 2}
LABEL = {"wrong": "唸錯", "undetermined": "無法判定", "right": "唸對"}


# ------------------------------------------------------------ 讀音與正規化(可注入假的,測試不用 pypinyin/opencc)
class PyPhon:
    """真正的讀音查詢(pypinyin,走 tts_asr 的 _one / _key,與 pron_pos_bad 同一套鍵)。"""

    def __init__(self):
        import tts_asr as TA
        self.TA = TA

    def one(self, c):
        return self.TA._one(c)

    def all(self, c):
        from pypinyin import Style, pinyin
        return set(pinyin(c, style=Style.TONE3, heteronym=True, neutral_tone_with_five=True)[0])

    def key(self, c, py=None):
        return self.TA._key(c, py)


def default_norm(s):
    """與品管同一個正規化(tts_chattts.norm_text:繁轉簡、去標點與數字)。"""
    import tts_chattts
    return tts_chattts.norm_text(s)


_CC = []


def simp(c):
    if not _CC:
        from opencc import OpenCC
        _CC.append(OpenCC("t2s"))
    return _CC[0].convert(c)


# ------------------------------------------------------------ 規則索引:規則(pron_rules.json rules 的一項)<-> 命中事件
class Rule:
    """is_default=True:always 字的「預設標注」(model_default;id `得#default`),命中 = 沒被任何非預設規則標到的該字位置。"""

    def __init__(self, ch, idx, entry, default, is_default=False):
        self.ch, self.py, self.default, self.is_default = ch, entry["py"], default, is_default
        self.id = f"{ch}#default" if is_default else f"{ch}#{idx}"
        self.words = list(entry.get("words", []))
        self.regs = [re.compile(entry["re"])] if "re" in entry else []
        self.unverified = bool(entry.get("unverified"))
        self.desc = "預設標注(always)" if is_default else ("、".join(self.words[:6]) + (f"…共{len(self.words)}詞" if len(self.words) > 6 else "")) if self.words \
            else "re:" + entry["re"][:46]

    @property
    def kind(self):
        return "預設標注" if self.is_default else "非預設規則"


def build_rules(raw=None):
    """規則清單:每個 always 字的預設標注(model_default,`<字>#default`)+ 非預設讀音規則(略過 keep、py 等於 model_default 的)。"""
    raw = CT.RULES_RAW if raw is None else raw
    out = []
    for ch, e in raw.items():
        if ch.startswith("_"):
            continue
        if e.get("always") and e.get("model_default"):
            out.append(Rule(ch, -1, dict(py=e["model_default"]), e["model_default"], is_default=True))
        for i, r in enumerate(e.get("rules", [])):
            if r.get("keep") or not r.get("py") or r["py"] == e.get("model_default"):
                continue
            out.append(Rule(ch, i, r, e.get("model_default")))
    return out


def rule_of(rules, text, event):
    """命中事件(CT.rule_events 的一項)屬於哪條規則。word 事件用「詞→標注」鍵;re 事件找檔內順序第一條涵蓋該位置的(與 rule_events 同樣取 t 群組)。"""
    p, ch, py, key, src, _unv = event
    if src == "default":
        return next((r for r in rules if r.is_default and r.ch == ch), None)
    if src == "word":
        w = key.split("→")[0]
        for r in rules:
            if r.ch == ch and r.py == py and w in r.words:
                return r
    elif src == "re":
        for r in rules:
            if r.ch != ch or r.py != py:
                continue
            for pat in r.regs:
                for m in pat.finditer(text):
                    a, b = m.span("t") if "t" in pat.groupindex else m.span()
                    if a <= p < b and text[p] == ch:
                        return r
    return None


def rule_hits(rules, mtext):
    """一句(測量文字)命中的規則 -> {規則 id: ([位置], 命中鍵)}(含 always 字的預設標注 `<字>#default`)。用 CT 的事件,不自己比對。"""
    out = {}
    for ev in CT._live_events(mtext, CT._word_spans(mtext)[0]):
        if not ev[2]:
            continue
        r = rule_of(rules, mtext, ev)
        if r:
            pos, key = out.setdefault(r.id, ([], ev[3]))
            pos.append(ev[0])
    return out


# ------------------------------------------------------------ 取句
def corpus():
    """所有 <片名>\\script.txt 的句子 -> [(片名, 測量文字 mtext, say 文字)];依 。！？ 切,去重。"""
    import script_txt2json
    seen, rows = set(), []
    for f in sorted(P.ROOT.glob("*/script.txt")):
        try:
            _t, says, sections, *_ = script_txt2json.parse(f.read_text(encoding="utf-8-sig"))
        except Exception as e:  # noqa: BLE001  壞檔不擋全部
            print(f"略過 {f.parent.name}: {e}", file=sys.stderr)
            continue
        for sec in sections:
            for _no, _tag, text, _extra in sec["rows"]:
                say = text
                for k, v in says:
                    say = say.replace(k, v)
                for s in re.findall(r"[^。！？!?]+[。！？!?]?", say):
                    s = s.strip()
                    m = CT.unsay(s)
                    if not (SENT_MIN <= len(m) <= SENT_MAX) or re.search(r"[A-Za-z0-9\[\]]", m) or m in seen:
                        continue
                    seen.add(m)
                    rows.append((f.parent.name, m, s))
    return rows


try:
    import re._parser as _sp
    import re._constants as _sc
except ImportError:  # Python < 3.11
    import sre_constants as _sc
    import sre_parse as _sp
FILLER = "我們一些大家很多"


def _gen(items, rng):
    """由正規式語法樹造一段會比對成功的字串 -> (前文, 本體, 後文);正向 lookbehind 補在前、lookahead 補在後,否定斷言與錨點忽略
    (成不成立由呼叫端用 rule_hits 驗)。碰到不會處理的語法回 None。"""
    pre, body, post = "", "", ""
    for op, av in items:
        if op == _sc.LITERAL:
            body += chr(av)
        elif op == _sc.IN:
            neg = any(o == _sc.NEGATE for o, _ in av)
            chars = []
            for o, v in av:
                if o == _sc.LITERAL:
                    chars.append(chr(v))
                elif o == _sc.RANGE:
                    chars += [chr(c) for c in range(v[0], v[1] + 1)]
            if neg:
                chars = [c for c in FILLER if c not in chars]
            words_only = [c for c in chars if "一" <= c <= "鿿"]   # 有漢字就不挑標點(造出的句子才像話)
            chars = words_only or chars
            if not chars:
                return None
            body += rng.choice(chars)
        elif op in (_sc.MAX_REPEAT, _sc.MIN_REPEAT):
            lo, hi, sub = av
            for _ in range(lo if lo > 0 else rng.choice([0, 1])):
                g = _gen(sub, rng)
                if g is None:
                    return None
                body += "".join(g)
        elif op == _sc.SUBPATTERN:
            g = _gen(av[-1], rng)
            if g is None:
                return None
            pre, body, post = pre + g[0], body + g[1], g[2] + post
        elif op == _sc.BRANCH:
            g = _gen(rng.choice(av[1]), rng)
            if g is None:
                return None
            pre, body, post = pre + g[0], body + g[1], g[2] + post
        elif op == _sc.ASSERT:
            g = _gen(av[1], rng)
            if g is None:
                return None
            if av[0] == 1:
                post += "".join(g)
            else:
                pre = "".join(g) + pre
        elif op in (_sc.ASSERT_NOT, _sc.AT):
            continue
        else:
            return None
    return pre, body, post


def synth_sentences(rule, rules, used, n):
    """用規則造句(最多 n 句;造出的句子都經 rule_hits 確認真的被這條規則命中):words 型規則用詞套句型,re 型規則由正規式反推。
    -> [(句, 位置, 鍵)]。"""
    if n <= 0:
        return []
    out, seen, bodies = [], set(used), set()
    cands = []
    if rule.words:
        cands = ((w, t.format(w=w)) for w in rule.words for t in SYNTH_TEMPLATES)
    elif rule.regs:
        rng = random.Random(rule.id)
        tree = _sp.parse(rule.regs[0].pattern)

        def draws():
            for _ in range(80):
                g = _gen(list(tree), rng)
                if g:
                    x = "".join(g)
                    for t in ("他說{x}。", "我們剛剛看到{x}。", "{x}。"):
                        yield x, t.format(x=x)
        cands = draws()
    for body, s in cands:
        if s in seen or body in bodies:
            continue
        h = rule_hits(rules, CT.unsay(s)).get(rule.id)
        if h:
            out.append((s, h[0], h[1]))
            bodies.add(body)
            if len(out) >= n:
                break
    return out


def plan(per_rule=2, only=None, seed=20261021):
    """-> (items, rules, stats)。item = dict(id, rule, ch, py, mtext, say, tag, positions, key, synthetic)。"""
    rules = [r for r in build_rules() if not only or r.ch in only]
    by_rule = defaultdict(list)
    for tag, m, s in corpus():
        for rid, (pos, key) in rule_hits(rules, m).items():
            by_rule[rid].append(dict(tag=tag, mtext=m, say=s, positions=pos, key=key))
    rng = random.Random(seed)
    items, used, stats = [], set(), dict(real=0, synth=0, none=0, partial=0)
    for r in rules:
        c = by_rule.get(r.id, [])
        rng.shuffle(c)
        c.sort(key=lambda x: len(x["positions"]) != 1)   # 一句只有一處規則位置的優先(對位簡單)
        chosen, seen_k, seen_t = [], set(), set()
        for strict in (True, False):
            for x in c:
                if len(chosen) >= per_rule:
                    break
                if x in chosen or x["mtext"] in used or (strict and (x["key"] in seen_k or x["tag"] in seen_t)):
                    continue
                chosen.append(x)
                seen_k.add(x["key"])
                seen_t.add(x["tag"])
        real_n = len(chosen)
        for s, pos, key in synth_sentences(r, rules, used | {x["mtext"] for x in chosen}, per_rule - real_n):
            chosen.append(dict(tag="synthetic", mtext=CT.unsay(s), say=s, positions=pos, key=key, synthetic=True))
        for x in chosen:
            used.add(x["mtext"])
            items.append(dict(x, rule=r.id, ch=r.ch, py=r.py, synthetic=bool(x.get("synthetic")), id=len(items)))
        n_syn = sum(1 for x in chosen if x.get("synthetic"))
        stats["real" if real_n and not n_syn else "synth" if n_syn and not real_n else "partial" if chosen else "none"] += 1
    return items, rules, stats


# ------------------------------------------------------------ 判定(純函式)
def locate(ref, hyp, targets, ph):
    """ref / hyp 已正規化;targets {ref 位置: (原字, 應讀 tone3)}。回傳 {ref 位置: 辨識文字對到的字或 None}。對位法同 tts_asr.pron_pos_bad。"""
    rk = [ph.key(c, targets[i][1] if i in targets else None) for i, c in enumerate(ref)]
    sm = difflib.SequenceMatcher(None, rk, [ph.key(c) for c in hyp], autojunk=False)
    out = dict.fromkeys(targets)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for d in range(i2 - i1):
                if i1 + d in targets:
                    out[i1 + d] = hyp[j1 + d]
    return out


def verdict(h, oc, want, ph, strict=False):
    """辨識到的字 h 對原字 oc、應讀 want(tone3):miss 沒對上 / same 原字(看不出聲調)/ right 預期讀音的同音字 / wrong 另一個讀音的字 / other。
    strict(always 字:著、得、曝…):other(不相干的音)改判 wrong,但 h 有任一讀音(不計聲調)等於應讀音(得 -> 地 de5)仍算 right;ASCII 不比。"""
    if h is None:
        return "miss"
    if h == oc or {h, oc} <= {"著", "着"}:
        return "same"
    r = ph.one(h)
    if r == want or (want.endswith("5") and r.rstrip("012345") == want.rstrip("012345")):   # 輕聲:同音不同調的字(得 -> 德)聲調聽不出,算對
        return "right"
    if r in ph.all(oc) - {want}:
        return "wrong"
    if strict and not h.isascii():
        if re.sub(r"\d", "", want) in {re.sub(r"\d", "", x) for x in ph.all(h)}:
            return "right"
        return "wrong"
    return "other"


def combine(vs, sims_ok):
    """主/副辨識的字級判定 -> wrong | undetermined | right。"""
    vs = [v for v in vs if v is not None]
    if "wrong" in vs:
        return "wrong"
    if vs and all(v == "same" for v in vs):
        return "undetermined"
    if "right" in vs or sims_ok:
        return "right"
    return "undetermined"


def prepare(text, targets_by_pos, norm):
    """文案標出規則位置 -> (正規化後的 ref, {ref 位置: (原字, 應讀)}, [原文位置]);位置數對不上(正規化吃掉)回 None。"""
    marked = "".join(tts_pron.MARK if i in targets_by_pos else c for i, c in enumerate(text))
    ref_n = norm(marked)
    if ref_n.count(tts_pron.MARK) != len(targets_by_pos):
        return None
    order = sorted(targets_by_pos)
    it = iter(order)
    targets, ref = {}, []
    for k, c in enumerate(ref_n):
        if c == tts_pron.MARK:
            targets[k] = targets_by_pos[next(it)]
            c = targets[k][0]
        ref.append(c)
    return "".join(ref), targets, order


def judge_record(rec, targets_by_pos, norm=None, ph=None, sim_min=SIM_MIN):
    """一筆 tts_cosy3 qc 紀錄(rec:measure_text/text、asr、asr2、sim、asr2_sim、asr2_bad、pron_bad)對文案裡的規則位置
    {原文位置: (原字, 應讀 tone3)} 判定。回傳 dict(result, sims_ok, note, positions=[每個位置的 main/second 字級判定與辨識到的字])。
    整句結果取最差:wrong > undetermined > right。"""
    norm = norm or default_norm
    ph = ph or PyPhon()
    text = rec.get("measure_text") or rec["text"]
    prep = prepare(text, targets_by_pos, norm)
    sims_ok = (rec.get("sim", 0) >= sim_min and not rec.get("pron_bad")
               and (rec.get("asr2") is None or (rec.get("asr2_sim", 0) >= sim_min and not rec.get("asr2_bad"))))
    if prep is None:
        return dict(result="undetermined", sims_ok=sims_ok, note="對位失敗(正規化吃掉規則位置)", positions=[])
    ref, targets, order = prep
    hyps = [rec.get("asr"), rec.get("asr2")]
    loc = [locate(ref, norm(h), targets, ph) if h else None for h in hyps]
    positions, results = [], []
    for k, pos in zip(sorted(targets), order):
        oc, want, *rest = targets[k]
        vs = [verdict(l[k], oc, want, ph, bool(rest and rest[0])) if l else None for l in loc]
        res = combine(vs, sims_ok)
        positions.append(dict(pos=pos, ch=oc, want=want, main=vs[0], second=vs[1],
                              hyp_main=loc[0][k] if loc[0] else None, hyp_second=loc[1][k] if loc[1] else None, result=res))
        results.append(res)
    worst = min(results, key=VERDICT_ORDER.get) if results else "undetermined"
    return dict(result=worst, sims_ok=sims_ok, note="" if rec.get("asr2") is not None else "沒有副辨識(主品管未過)", positions=positions)


def targets_for(item):
    """item 的規則位置 -> {位置: (簡體原字, 應讀 tone3, strict)};strict = always 字(同 tts_chattts.pron_targets)。"""
    import tts_asr as TA
    return {p: (simp(item["ch"]), TA.token_reading(item["py"]), item["ch"] in CT.RULE_ALWAYS) for p in item["positions"]}


# ------------------------------------------------------------ 執行
def busy_reason():
    """顯示卡已用 >3000 MiB 或有別的配音/出片行程就回原因字串,空閒回 None。"""
    try:
        used = GL.gpu_used_mib()
        if used is None:
            raise RuntimeError("無輸出")
        if used > VRAM_BUSY:
            return f"顯示卡已用 {used} MiB (>{VRAM_BUSY})"
    except Exception as e:  # noqa: BLE001
        return f"nvidia-smi 查不到({e})"
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.ProcessId -ne %d -and "
          "$_.CommandLine -match '%s' } | ForEach-Object { '{0} {1}' -f $_.ProcessId, $_.CommandLine.Substring(0, [Math]::Min(120, $_.CommandLine.Length)) }"
          % (os.getpid(), GPU_PROC_RE))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
    procs = [x for x in r.stdout.splitlines() if x.strip()]
    if procs:
        return "有別的配音/出片行程在跑: " + " | ".join(procs[:3])
    return None


def out_wav(work, seed, item):
    return work / f"seed{seed}" / "wav" / f"{item['id']}.wav"


def synth(items, seeds, work, max_retry):
    """每個 seed 一批呼叫 tts_cosy3(子行程);已有 .qc.json 的單位不重錄。-> 失敗的 seed list。"""
    env = dict(os.environ, TEMP=str(P.TMP), TMP=str(P.TMP))
    bad = []
    for s in seeds:
        todo = [it for it in items if not out_wav(work, s, it).with_suffix(".qc.json").exists()]
        sd = work / f"seed{s}"
        (sd / "wav").mkdir(parents=True, exist_ok=True)
        if not todo:
            print(f"seed {s}: 全部已有紀錄,略過")
            continue
        jobs = [{"idx": it["id"], "text": it["say"], "out": str(out_wav(work, s, it)), "verify": False} for it in todo]
        jf = sd / "jobs.json"
        jf.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        cmd = [str(P.TTS_ENV), "-X", "utf8", str(HERE / "tts_cosy3.py"), str(jf), "--ref", str(P.COSY_REF), "--speed", "1.18",
               "--voice", P.COSY_REF.name, "--seed", str(s), "--asr2", "fun_nano", "--max-retry", str(max_retry), "--rate-seeds", "0"]
        print(f"seed {s}: 合成 {len(todo)} 句 ...", flush=True)
        with open(sd / "run.log", "w", encoding="utf-8") as lf:
            rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=lf, env=env).returncode
        if rc != 0:
            print(f"seed {s}: tts_cosy3 結束碼 {rc}(見 {sd / 'run.log'})")
            bad.append(s)
    return bad


def read_rec(work, seed, item):
    f = out_wav(work, seed, item).with_suffix(".qc.json")
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def judge_all(items, seeds, work):
    """-> [dict(item, seed, rec, judge|None)]。"""
    ph, out = PyPhon(), []
    for it in items:
        tg = targets_for(it)
        for s in seeds:
            rec = read_rec(work, s, it)
            out.append(dict(item=it, seed=s, rec=rec, judge=judge_record(rec, tg, ph=ph) if rec else None))
    return out


def record_memory(results, run, ph=None):
    """判定結果寫進語境讀音記憶(rule_hits 的位置以 mtext 為準)。-> Counter(動作)。"""
    rows = {}
    for r in results:
        it, j = r["item"], r["judge"]
        for p in (j or {}).get("positions", []):
            row = rows.setdefault((it["id"], p["pos"]), dict(text=it["mtext"], pos=p["pos"], ch=it["ch"], py=it["py"], results=[],
                                                             tag=it["tag"], rewrite=it["say"]))
            row["results"].append(p)
    return PM.record_tests(list(rows.values()), run, ph or PyPhon())


# ------------------------------------------------------------ 報告
def _cell(s, n=60):
    return (s or "").replace("|", "／").replace("\n", " ")[:n]


def write_report(path, date, rules, items, results, seeds, args_note=""):
    by_rule = defaultdict(list)
    for r in results:
        by_rule[r["item"]["rule"]].append(r)
    rows = []
    for rule in rules:
        rs = by_rule.get(rule.id, [])
        c = Counter(r["judge"]["result"] if r["judge"] else "missing" for r in rs)
        n_sent = len({r["item"]["id"] for r in rs})
        syn = sum(1 for i in {r["item"]["id"]: r["item"] for r in rs}.values() if i["synthetic"])
        pick = next((r for r in rs if r["judge"] and r["judge"]["result"] == "wrong"), None) or (rs[0] if rs else None)
        rows.append(dict(rule=rule, c=c, n_sent=n_sent, syn=syn, pick=pick, rs=rs))
    wrong = [x for x in rows if x["c"]["wrong"]]
    wrong.sort(key=lambda x: -x["c"]["wrong"])
    L = [f"# 多音字規則實測回查 {date}", "",
         f"規則 {len(rules)} 條(預設標注 {sum(r.is_default for r in rules)}、非預設讀音 {sum(not r.is_default for r in rules)});句子 {len(items)}(真句 {sum(1 for i in items if not i['synthetic'])}、造句 {sum(1 for i in items if i['synthetic'])});"
         f"seed {','.join(map(str, seeds))};合成 {len([r for r in results if r['rec']])} 筆。{args_note}",
         "判定:唸錯 = 主或副辨識把該字聽成它另一讀音的字;唸對 = 辨識成預期讀音的同音字,或雙辨識相似度都過且無 pron_bad;"
         "無法判定 = 辨識回原字(文字層看不出聲調)或相似度未過。**皆為未聽審的文字層回查,不等於耳朵聽過。**", ""]
    L.append(f"## 唸錯的規則清單({len(wrong)} 條)")
    if not wrong:
        L.append("(無)")
    for x in wrong:
        r = x["rule"]
        L.append(f"- **{r.id}**({r.kind}) {r.ch} → {r.py} ({_cell(r.desc, 70)}):唸錯 {x['c']['wrong']}/{sum(x['c'].values())} 筆")
        for rr in x["rs"]:
            if rr["judge"] and rr["judge"]["result"] == "wrong":
                L.append(f"  - seed {rr['seed']}{' (造句)' if rr['item']['synthetic'] else ''}:{rr['item']['mtext']}"
                         f"  | asr:{_cell(rr['rec'].get('asr'), 70)} | asr2:{_cell(rr['rec'].get('asr2'), 70)}")
    L += ["", "## 全部規則", "",
          "| 規則 | 類型 | 字 | 讀音 | 內容 | 句數(造) | 對 | 錯 | 無法判定 | 缺 | asr 摘錄 | asr2 摘錄 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in sorted(rows, key=lambda x: (-x["c"]["wrong"], x["rule"].id)):
        r, c, p = x["rule"], x["c"], x["pick"]
        a1 = _cell(p["rec"].get("asr")) if p and p["rec"] else ""
        a2 = _cell(p["rec"].get("asr2")) if p and p["rec"] else ""
        L.append(f"| {r.id}{'※' if r.unverified else ''} | {r.kind} | {r.ch} | {r.py} | {_cell(r.desc, 36)} | {x['n_sent']}({x['syn']}) | "
                 f"{c['right']} | {c['wrong']} | {c['undetermined']} | {c['missing']} | {a1} | {a2} |")
    nores = [x["rule"].id for x in rows if not x["rs"]]
    if nores:
        L += ["", f"## 沒有句子可驗的規則({len(nores)} 條:文案沒命中、又不是 words 型規則,造不出句)", "", "、".join(nores)]
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")
    return len(wrong)


# ------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", required=True, help="YYYY-MM-DD,決定工作資料夾與報告檔名")
    ap.add_argument("--per-rule", type=int, default=2)
    ap.add_argument("--seeds", default="2024,7")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--judge-only", action="store_true", help="不合成,只讀既有 qc 紀錄重出報告")
    ap.add_argument("--only", nargs="+", help="只驗這幾個字(例:著,得 或 著 得;含該字的預設標注 <字>#default)")
    ap.add_argument("--max-retry", type=int, default=0)
    a = ap.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        sys.exit("--date 要 YYYY-MM-DD")
    seeds = [int(x) for x in a.seeds.split(",") if x.strip()]
    items, rules, st = plan(a.per_rule, set(re.sub(r"[,\s]", "", "".join(a.only))) if a.only else None)
    n_syn = sum(1 for i in items if i["synthetic"])
    total = len(items) * len(seeds)
    if a.dry_run:
        print(f"規則 {len(rules)} 條(預設標注 {sum(r.is_default for r in rules)}、非預設讀音 {sum(not r.is_default for r in rules)};{len({r.ch for r in rules})} 個字)")
        print(f"  全真句 {st['real']} 條、全造句 {st['synth']} 條、真句+造句 {st['partial']} 條、無句可驗 {st['none']} 條")
        print(f"句子 {len(items)}(真句 {len(items) - n_syn}、造句 {n_syn});× {len(seeds)} seed = 合成 {total} 句")
        print(f"預估 {total * SEC_PER_SENT / 60:.0f} 分鐘(每句 {SEC_PER_SENT} 秒)")
        return
    work = P.TMP / "pron_verify" / a.date
    work.mkdir(parents=True, exist_ok=True)
    (work / "manifest.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    if not a.judge_only:
        with GL.gpu_lock("pron_verify", "tts_pron_verify"):  # 排隊拿全機 GPU 鎖(取代 busy_reason 的直接中止)
            bad = synth(items, seeds, work, a.max_retry)
        if bad:
            print(f"注意:seed {bad} 的 tts_cosy3 非正常結束,報告只含已完成的句子")
    results = judge_all(items, seeds, work)
    (work / "results.json").write_text(json.dumps(
        [dict(id=r["item"]["id"], rule=r["item"]["rule"], seed=r["seed"], result=r["judge"] and r["judge"]["result"],
              positions=r["judge"] and r["judge"]["positions"]) for r in results], ensure_ascii=False, indent=1), encoding="utf-8")
    acts = record_memory(results, f"verify:{a.date}:{a.seeds}")
    print("語境讀音記憶:" + ("、".join(f"{k} {v}" for k, v in acts.items()) or "沒有可寫的結果"))
    rp = P.TMP / f"pron_verify_{a.date}.md"
    n_wrong = write_report(rp, a.date, rules, items, results, seeds, f"max-retry {a.max_retry}。")
    c = Counter(r["judge"]["result"] if r["judge"] else "missing" for r in results)
    print(f"完成:唸對 {c['right']}、唸錯 {c['wrong']}、無法判定 {c['undetermined']}、缺 {c['missing']};唸錯的規則 {n_wrong} 條\n報告 {rp}")


if __name__ == "__main__":
    main()
