"""自製片文體指標(程式量測,不下結論):python -X utf8 pipeline/style_metrics.py --tags a,b,c | --all
輸出 output\\_style\\style_metrics.md 與 .json。2026-10-20 由 scratchpad 版搬入,量法不變;路徑一律取自 paths.py。
--tags 指定 tag;--all = 21 支已知樣本(SAMPLES,有頻道與均看% 標註)加其餘有 script.txt 的資料夾。
"""
import argparse, re, sys, json, statistics as st, subprocess, collections, warnings
import paths as P
import pace
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import jieba
jieba.setLogLevel(60)
from script_lint import SIGNPOST, SUMMARY, FORMAL
ROOT = str(P.ROOT)
OUT_DIR = P.OUTPUT / "_style"
SAMPLES = [("gow_sales","ChannelA","65.9% 7d"),("wow_races","ChannelA","62.6% 48h"),("dei_tracer","ChannelA","57.3% 48h"),("re9_leon","ChannelB","56.9% 48h"),("dei_gta5","ChannelA","56.8% 48h"),("dei_gamersdead","ChannelA","56.1% 48h"),("shogun2_ce","ChannelA","55.9% 48h"),("dei","ChannelA","54.5% 7d"),("wow_ban","ChannelA","52.6% 48h"),("gta6_trailer","ChannelA","51.6% 48h"),("survive3","ChannelB","50.4% 7d"),("castlevania_bc","ChannelB","50% 48h"),("wow_forever","ChannelA","48.7% 7d"),("sf_dying","ChannelB","48.7% 48h"),("onimusha","ChannelB","45.6% 48h"),("cod_tax","ChannelA","44.3% 48h"),("xbox_elephant","ChannelA","43.2% 48h"),("wow_forever_interview","ChannelA","41.6% 7d"),("re9","ChannelB","39.9% 7d"),("re9_online","ChannelB","38.3% 7d"),("cod2026","ChannelA","無(未發布)")]
WARM = re.compile(r"放在一起看|更怪的是|重點來了|先講|我們先看|問題來了|有意思的是")
PRON = re.compile(r"這個人|這家公司|該公司|同一家|你操作的|這招|這件事|這款|這東西")
JUDGE = re.compile(r"我覺得|根本|太|有夠|不該|離譜|冤枉|扯|難看|可惜")
GEN_NOT = re.compile(r"^(img:|anim|quote|compare|card|versus|num|bars|list|timeline)")
SEGH = re.compile(r"^#\s*[一二三四五六七八九十]+、")
PUNCT = re.compile(r"[\W_]", re.U)
def clen(s): return len(PUNCT.sub("", s))
ap = argparse.ArgumentParser()
ap.add_argument("--tags", help="逗號分隔的 tag")
ap.add_argument("--all", action="store_true", help="全部樣本加其餘有 script.txt 的資料夾")
args = ap.parse_args()
META = {t: (c, v) for t, c, v in SAMPLES}
if args.all:
    extra = sorted(d.name for d in P.ROOT.iterdir() if (d / "script.txt").is_file() and d.name not in META)
    RUN = list(SAMPLES) + [(t, "-", "-") for t in extra]
elif args.tags:
    RUN = [(t, *META.get(t, ("-", "-"))) for t in args.tags.split(",") if t.strip()]
else:
    sys.exit("需要 --tags a,b,c 或 --all")
res = {}; ex = collections.defaultdict(list)
for tag, ch, view in RUN:
    raw = (P.ROOT / tag / "script.txt").read_text(encoding="utf-8").splitlines()
    segs = sum(1 for r in raw if SEGH.match(r))
    lines = []
    for n, r in enumerate(raw, 1):
        if not r.strip() or r[0] in "@#" or "|" not in r: continue
        lab, rest = r.split("|", 1)
        lines.append((n, lab.strip(), rest.split(" ;; ")[0].strip()))
    S = []
    for ln, lab, t in lines:
        for m in re.finditer(r"([^。?!？！]+)([。?!？！]?)", t):
            s = m.group(1).strip()
            if s: S.append((ln, lab, s, m.group(2) in ("?", "？")))
    lens = [clen(s[2]) for s in S]
    chars = sum(lens); nS = len(S)
    d = dict(channel=ch, view=view, lines=len(lines), sentences=nS, chars=chars, est_min=round(chars/pace.CHARS_PER_SEC/60, 1), segments=segs,
             sent_per_seg=round(nS/segs, 1) if segs else None, len_mean=round(st.mean(lens), 1), len_sd=round(st.pstdev(lens), 1),
             le9=round(sum(x <= 9 for x in lens)/nS, 3), ge24=round(sum(x >= 24 for x in lens)/nS, 3),
             question=round(sum(s[3] for s in S)/nS, 3), wo_per_k=round(sum(s[2].count("我") for s in S)/chars*1000, 1))
    fw = collections.Counter()
    for _, _, s, _ in S:
        w = [x for x in jieba.lcut(s) if x.strip() and not re.match(r"^\W+$", x)]
        if w: fw[w[0]] += 1
    d["first_words"] = fw.most_common(10)
    for key, rx in (("signpost", SIGNPOST), ("warmup", WARM), ("pronoun", PRON), ("summary", SUMMARY), ("formal", FORMAL)):
        hit = [(ln, t) for ln, _, t in lines if rx.search(t)]
        d[key] = len(hit)
        for ln, t in hit: ex[key].append((tag, ln, t))
    cum = 0; d["judge_idx"] = None; d["judge_sec"] = None
    for i, (ln, lab, s, q) in enumerate(S, 1):
        if JUDGE.search(s):
            d["judge_idx"] = i; d["judge_sec"] = round(cum/pace.CHARS_PER_SEC); break
        cum += clen(s)
    nums = [s for s in S if re.search(r"\d", s[2])]
    d["num_sent"] = round(len(nums)/nS, 3); d["num_n"] = len(nums)
    gen = [s for s in nums if not GEN_NOT.match(s[1])]
    d["num_generic"] = round(len(gen)/len(nums), 3) if nums else None
    for s in gen: ex["num_generic"].append((tag, s[0], s[2], clen(s[2])))
    for s in S:
        c = clen(s[2]); ex["longest"].append((tag, s[0], s[2], c))
        if s[3]: ex["question"].append((tag, s[0], s[2], c))
        if s[2].count("我") >= 2: ex["wo"].append((tag, s[0], s[2], s[2].count("我")))
    out = subprocess.run([sys.executable, "-X", "utf8", str(P.REPO / "pipeline" / "script_lint.py"), tag], capture_output=True, text=True, encoding="utf-8", cwd=ROOT).stdout
    bad = [re.sub(r"^\s*超標\s*", "", l).strip() for l in out.splitlines() if l.strip().startswith("超標")]
    d["lint_bad_n"] = len(bad); d["lint_bad"] = bad
    res[tag] = d
E = {}
def top(items, key=None, rev=True, n=3):
    it = sorted(items, key=key, reverse=rev) if key else items
    return [f"{a} L{b}: {c}" for a, b, c, *_ in it[:n]]
E["最長句"] = top(ex["longest"], lambda x: x[3])
E["最短句(>=2字)"] = top([x for x in ex["longest"] if x[3] >= 2], lambda x: x[3], False)
E["問句(最長)"] = top(ex["question"], lambda x: x[3])
E["一句內我最多"] = top(ex["wo"], lambda x: x[3])
E["含數字且畫面為泛用片段(最長)"] = top(ex["num_generic"], lambda x: x[3])
for k, nm in (("signpost", "報幕"), ("warmup", "暖場"), ("pronoun", "代稱"), ("summary", "段末總結/講解腔"), ("formal", "書面轉接")):
    E[nm] = [f"{a} L{b}: {c}" for a, b, c in ex[k][:3]]
E["第一句判斷詞最晚(tag,秒,第幾句)"] = [str(x) for x in sorted([(t, d["judge_sec"], d["judge_idx"]) for t, d in res.items() if d["judge_idx"]], key=lambda x: -x[1])[:3]]
E["全片無判斷詞"] = [t for t, d in res.items() if not d["judge_idx"]]
rank = [t for t, _, v in SAMPLES if v[0].isdigit() and t in res]   # 以均看% 由高到低排的樣本
top7, bot7 = rank[:7], rank[-7:]
HAS_GRP = len(rank) >= 14   # 少於 14 支就不分前後 7(--tags 只跑幾支時)
keys = ["est_min", "segments", "sent_per_seg", "len_mean", "len_sd", "le9", "ge24", "question", "wo_per_k", "signpost", "warmup", "pronoun", "summary", "formal", "judge_sec", "num_sent", "num_generic", "lint_bad_n"]
def avg(g, k):
    v = [res[t][k] for t in g if res[t][k] is not None]
    return round(st.mean(v), 3) if v else None
grp = {k: (avg(top7, k), avg(bot7, k)) for k in keys} if HAS_GRP else {}
OUT_DIR.mkdir(parents=True, exist_ok=True)
json.dump(dict(per_tag=res, groups=dict(top7=top7, bot7=bot7, means=grp), examples=E), open(OUT_DIR / "style_metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
M = ["# 自製片文體指標(程式量測,不下結論)", "", f"量測日 2026-10-20;腳本 pipeline\\style_metrics.py。句=以 。?! 切;字數不含標點;估片長=字數/{pace.CHARS_PER_SEC:g} 秒(pace.py)。均看% 受片長與題材影響大,弱證據。數字句只算阿拉伯數字;報幕/總結/書面 regex 沿用 script_lint.py,以行為單位。", "",
     "| tag | 頻道 | 均看 | 估長(分) | 句數 | 段 | 句/段 | 句長均 | 句長SD | <=9字 | >=24字 | 問句 | 我/千字 | 報幕 | 暖場 | 代稱 | 總結 | 書面 | 判斷詞(句/秒) | 數字句 | 數字句泛用標籤 | lint超標 |", "|" + "---|"*22]
p = lambda x: "-" if x is None else f"{x:.0%}"
for tag, ch, v in RUN:
    d = res[tag]
    M.append(f"| {tag} | {ch} | {v} | {d['est_min']} | {d['sentences']} | {d['segments']} | {d['sent_per_seg']} | {d['len_mean']} | {d['len_sd']} | {p(d['le9'])} | {p(d['ge24'])} | {p(d['question'])} | {d['wo_per_k']} | {d['signpost']} | {d['warmup']} | {d['pronoun']} | {d['summary']} | {d['formal']} | {d['judge_idx']}/{d['judge_sec']} | {p(d['num_sent'])} | {p(d['num_generic'])} | {d['lint_bad_n']} |")
if HAS_GRP:
    M += ["", "## 均看前 7 與後 7(弱證據;cod2026 未發布不計;n=7 對 7)", f"前 7:{', '.join(top7)}", f"後 7:{', '.join(bot7)}", "", "| 指標 | 前7平均 | 後7平均 |", "|---|---|---|"]
    for k, (a, b) in grp.items(): M.append(f"| {k} | {a} | {b} |")
M += ["", "## 各片 lint 超標項"]
for tag, _, _ in RUN: M.append(f"- {tag}({res[tag]['lint_bad_n']}):{'; '.join(res[tag]['lint_bad']) or '無'}")
M += ["", "## 句首第一個詞前 10 名"]
for tag, _, _ in RUN: M.append(f"- {tag}:{' '.join(f'{w}{c}' for w, c in res[tag]['first_words'])}")
M += ["", "## 極端例句(各 3 句)"]
for k, v in E.items():
    M.append(f"### {k}"); M += [f"- {x}" for x in v]
(OUT_DIR / "style_metrics.md").write_text("\n".join(M), encoding="utf-8")
print(f"ok {len(RUN)} 支 -> {P.rel(OUT_DIR)}")
