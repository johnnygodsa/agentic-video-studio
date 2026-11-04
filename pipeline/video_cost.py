#!/usr/bin/env python3
r"""每支影片的 token 總量:director 子程序 LLM(production.json llm_calls)+ Claude Code 對話(主對話 + 子代理)。

對話紀錄只讀 ~/.claude/projects/<project-slug>*(含 worktree),不寫任何檔到 C 槽;解析結果依檔案 mtime+size
快取在 tmp\video_cost_cache.json。權重重用 director.MODEL_W;eq = input + cache_creation + 5×output + 0.1×cache_read,
w = eq × 模型權重。

逐則歸屬:主對話依時間走,遇到可辨識的 tag(projects\<tag> 實存目錄)就切換「目前 tag」,之後的 assistant 訊息記到該 tag;
第一個 tag 之前記 (未歸屬)。唯讀查詢指令(READONLY_*)不切換。子代理:首則 prompt 帶寫入/製作語境的
路徑或指令(同樣排除唯讀指令)才算自有 tag,否則繼承父對話在它啟動時的目前 tag(父為未歸屬就未歸屬)。

用量快照與百分比:官方「占上限 %」只有主對話能讀(桌面 App 的 get_usage),程式讀不到,所以由主對話用 --snap 把數字寫進
channel\usage_snapshots.jsonl,程式拿快照校準:視窗起點(重設時間 − 7 天 / − 5 小時)用量視為 0%,算起點到快照時間內帳號
**全部** w(~/.claude/projects 下所有專案的主對話+子代理、加本專案 production.json 的 llm_calls)→「每 1% = 多少 w」,
週與五小時各取最近 5 筆快照的中位數(用量 <3% 的快照不納入)。w 轉 % 即 w ÷ 係數。
已知偏差:(1) 別的專案若用 `claude -p --no-session-persistence` 不留對話紀錄,帳號全部 w 被低估 → 係數偏大、片的 % 偏小;
(2) Fable 權重(director.MODEL_W 的 fable)是暫定;(3) 快照少、用量小時係數雜訊大;(4) 非 Claude Code 的用量(網頁版等)也吃額度但算不到。
中文片名:channel\tag_names.json {tag: 中文短名},輸出一律「中文短名(tag)」,沒有就只顯示 tag。

用法:
  python -X utf8 pipeline\video_cost.py <tag> [--json]            單片明細
  python -X utf8 pipeline\video_cost.py --all [--since YYYY-MM-DD]  跨片總表,寫 channel\token_ledger.md/.json
  python -X utf8 pipeline\video_cost.py --snap --h5 19 --h5-reset 2026-11-04T20:39:59Z --week 32 --week-reset 2026-11-10T01:59:59Z [--fable 4]
  python -X utf8 pipeline\video_cost.py --now                      最新快照 + 自快照後估計又用了多少 %
"""
import argparse
import bisect
import collections
import glob
import json
import os
import re
import sys
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402

UNATTR = "(未歸屬)"
CONV_ROOT = Path.home() / ".claude" / "projects"
CONV_GLOB = "<project-slug>*"
CACHE_PATH = P.TMP / "video_cost_cache.json"
CACHE_VER = 3
CV_PREFIX = "<project-slug>"       # 本專案(含 worktree)的對話目錄前綴;其餘專案只讀用量(輕量解析)
SNAP_PATH = P.REPO / "channel" / "usage_snapshots.jsonl"
NAMES_PATH = P.REPO / "channel" / "tag_names.json"
MIN_PCT = 3        # 用量低於此 % 的快照不納入校準
CALIB_N = 5        # 係數取最近 N 筆快照的中位數
_WORD = re.compile(r"[a-z][a-z0-9_]{2,}")
_PY_ARGS = re.compile(r"\.py\b((?:[ \t]+[^\s\"']+){1,4})")
_PATH_TAG = re.compile(r"(?:projects|build|keep|output|raw|images)[\\/]+([A-Za-z][A-Za-z0-9_]*)")
_TAG_OPT = re.compile(r"--tag[ \t=]+['\"]?([A-Za-z][A-Za-z0-9_]*)")
_SCRIPT = re.compile(r"([A-Za-z][A-Za-z0-9_]*)[\\/]+script")
_SYSREM = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


# ---------- 權重 ----------

def _director():
    import director
    return director


def model_w(model_id):
    return _director().model_w(model_id)


def eq_of(i, cc, cr, o):
    return i + cc + 5.0 * o + 0.1 * cr


def known_tags():
    d = P.PROJECTS
    return {x.name for x in d.iterdir() if x.is_dir() and not x.name.startswith("_")} if d.is_dir() else set()


def _weak_ok(tag):
    """沒有底線也沒有數字的片名(framework、pearl、salary)是普通英文字,只認強模式,不從使用者白話文抓。"""
    return "_" in tag or any(c.isdigit() for c in tag)


# ---------- 解析單檔(只存候選字串,與 known 無關,快取才可重用) ----------

def _strings(o, out):
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            _strings(v, out)
    elif isinstance(o, list):
        for v in o:
            _strings(v, out)


# 唯讀查詢指令:只是看數字,不代表在做那支片,不切換目前 tag。日後增補改這兩個常數。
READONLY_SCRIPTS = {"video_cost", "stats", "session_usage"}
READONLY_DIRECTOR_SUBS = {"cost", "usage", "status", "log", "--explain"}   # director brief/run/intervene/feedback 照常切換
_SEG_SPLIT = re.compile(r"\n|;|\||&&")
_SCRIPT_CALL = re.compile(r"([A-Za-z0-9_]+)\.py\b((?:[ \t]+[^\s\"']+){0,4})")


def _readonly_segment(seg):
    for m in _SCRIPT_CALL.finditer(seg):
        name, toks = m.group(1), m.group(2).split()
        if name in READONLY_SCRIPTS:
            return True
        if name == "director" and any(t in READONLY_DIRECTOR_SUBS for t in toks[:1] + [t for t in toks if t == "--explain"]):
            return True
    return False


def _text_cands(text):
    """一段文字(指令、檔案路徑、prompt)→ 候選 tag 字串清單(強模式);含唯讀查詢指令的片段整段略過。"""
    c = []
    segs = _SEG_SPLIT.split(text)
    ro = [_readonly_segment(g) for g in segs]
    for seg, is_ro in zip(segs, ro):
        if is_ro:
            continue
        for m in _PY_ARGS.finditer(seg):
            c += [t.strip("\"'") for t in m.group(1).split() if not t.startswith("-")]
        # 整個指令含唯讀查詢時,其餘片段的路徑(如順手讀 production.json)也不算,只認指令/--tag
        for rx in ((_TAG_OPT,) if any(ro) else (_PATH_TAG, _TAG_OPT, _SCRIPT)):
            c += rx.findall(seg)
    return [x for x in c if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", x)][:40]


def _tool_cands(inp):
    """tool_use input → 候選 tag 字串清單。"""
    parts = []
    _strings(inp, parts)
    return _text_cands("\n".join(parts))


def _user_text(m, d):
    """使用者真實輸入文字;tool_result、meta、壓縮摘要、任務通知回 ''。"""
    c = m.get("content")
    if isinstance(c, list):
        if all(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return ""
        c = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(c, str) or d.get("isMeta") or d.get("isCompactSummary"):
        return ""
    c = _SYSREM.sub("", c).strip()
    if c.startswith(("This session is being continued", "<task-notification", "<local-command", "<command-")):
        return ""
    return c


def _words(text):
    seen = []
    for w in _WORD.findall(text):
        if w not in seen:
            seen.append(w)
        if len(seen) >= 300:
            break
    return seen


def parse_file(path, light=False):
    """回傳 {t0,t1,ev,first_user}。ev 依檔案順序:
    ['a', ts, mid, model, in, cc, cr, out, tool_cands]  assistant 訊息(同 id 串流分段合併,取最大用量)
    ['u', ts, words]                                    使用者輸入文字
    light=True(非本專案對話,只算用量):不抽 tool 候選字串與使用者文字,只留 'a' 事件的用量。"""
    ev, idx = [], {}
    t0 = t1 = None
    first_user = None
    with open(path, encoding="utf8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts = d.get("timestamp")
            if ts:
                t0 = min(t0 or ts, ts)
                t1 = max(t1 or ts, ts)
            t = d.get("type")
            m = d.get("message")
            if not isinstance(m, dict):
                continue
            if t == "assistant":
                mid = m.get("id") or d.get("uuid")
                u = m.get("usage") or {}
                nums = [u.get("input_tokens", 0) or 0, u.get("cache_creation_input_tokens", 0) or 0,
                        u.get("cache_read_input_tokens", 0) or 0, u.get("output_tokens", 0) or 0]
                cands = []
                for b in [] if light else (m.get("content") or []):
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        cands += _tool_cands(b.get("input", {}))
                if mid in idx:
                    e = ev[idx[mid]]
                    if sum(nums) >= sum(e[4:8]):
                        e[4:8] = nums
                    e[8] = e[8] + cands
                else:
                    idx[mid] = len(ev)
                    ev.append(["a", ts, mid, m.get("model"), *nums, cands])
            elif t == "user" and not light:
                txt = _user_text(m, d)
                if txt:
                    w = _words(txt)
                    ev.append(["u", ts, w])
                    if first_user is None:
                        first_user = _text_cands(txt)   # 子代理自有 tag 只認強模式(路徑/指令),且唯讀指令不算
    return {"t0": t0, "t1": t1, "ev": ev, "first_user": first_user or []}


# ---------- 快取 ----------

def _load_cache(cache_path):
    try:
        c = json.loads(Path(cache_path).read_text(encoding="utf-8"))
        if c.get("ver") == CACHE_VER:
            return c
    except Exception:
        pass
    return {"ver": CACHE_VER, "files": {}}


def _save_cache(cache_path, cache):
    p = Path(cache_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, p)


def all_conv_dirs():
    """帳號下所有專案的對話目錄(校準用)。"""
    return sorted(d for d in glob.glob(str(CONV_ROOT / "*")) if os.path.isdir(d))


def load_files(conv_dirs=None, cache_path=CACHE_PATH, stats=None, light_other=False):
    """掃所有對話目錄,回傳 [{id,kind,parent,meta,path,t0,t1,ev,first_user}]。未變的檔(mtime+size)取快取。"""
    if conv_dirs is None:
        conv_dirs = sorted(glob.glob(str(CONV_ROOT / CONV_GLOB)))
    cache = _load_cache(cache_path)
    old = cache["files"]
    new, out, hit, miss = {}, [], 0, 0
    jobs = []
    for root in conv_dirs:
        rn = os.path.basename(os.path.normpath(root))
        for p in sorted(glob.glob(os.path.join(root, "*.jsonl"))):
            u = os.path.basename(p)[:-6]
            jobs.append((p, "main", u, None, rn))
            for sp in sorted(glob.glob(os.path.join(root, u, "subagents", "agent-*.jsonl"))):
                jobs.append((sp, "sub", os.path.basename(sp)[6:-6], u, rn))
    for p, kind, fid, parent, rn in jobs:
        try:
            stt = os.stat(p)
        except OSError:
            continue
        light = light_other and not rn.startswith(CV_PREFIX)   # light_other:非本專案目錄只讀用量
        key = f"{stt.st_mtime_ns}:{stt.st_size}" + (":L" if light else "")
        ent = old.get(p)
        if ent and ent.get("key") == key:
            hit += 1
        else:
            ent = dict(parse_file(p, light), key=key)
            miss += 1
        new[p] = ent
        meta = {}
        if kind == "sub":
            mp = p[:-6] + ".meta.json"
            if os.path.exists(mp):
                try:
                    meta = json.loads(Path(mp).read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
        out.append(dict(id=fid, kind=kind, parent=parent, meta=meta, path=p, root=rn, t0=ent["t0"], t1=ent["t1"],
                        ev=ent["ev"], first_user=ent["first_user"]))
    if miss or set(old) != set(new):
        cache["files"] = new
        _save_cache(cache_path, cache)
    if stats is not None:
        stats.update(hit=hit, miss=miss)
    return out


# ---------- 歸屬 ----------

def _pick(cands, known, weak):
    """候選字串 → 最常出現(平手取最先)的已知 tag;weak=True 時沒底線沒數字的片名不收。"""
    cnt = collections.Counter(c for c in cands if c in known and (not weak or _weak_ok(c)))
    if not cnt:
        return None
    first = {}
    for i, c in enumerate(cands):
        first.setdefault(c, i)
    return min(cnt, key=lambda c: (-cnt[c], first[c]))


def _day(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date().isoformat()
    except Exception:
        return (ts or "")[:10]


def _blank():
    return dict(turns=0, input=0, cc=0, cr=0, out=0, eq=0.0, w=0.0)


def _add(b, e):
    i, cc, cr, o = e[4], e[5], e[6], e[7]
    q = eq_of(i, cc, cr, o)
    b["turns"] += 1
    b["input"] += i
    b["cc"] += cc
    b["cr"] += cr
    b["out"] += o
    b["eq"] += q
    b["w"] += q * model_w(e[3])


def _owners(files):
    """message.id → 擁有它的檔(t0 最早者);跨檔去重用。"""
    owner = {}
    for f in sorted(files, key=lambda x: (x["t0"] or "", x["kind"] != "main", x["path"])):
        for e in f["ev"]:
            if e[0] == "a":
                owner.setdefault(e[2], f["path"])
    return owner


def attribute(files, known):
    """回傳 {tags:{tag:{main,subs:{type:{...}},sessions:set,t0,t1}}, unattr_days:{day:{...}}}。
    跨檔去重:同 message.id 只算 t0 最早的檔(fork/resume 會複製舊訊息)。"""
    owner = _owners(files)
    res = {"tags": {}, "unattr_days": {}}

    def slot(tag):
        return res["tags"].setdefault(tag, dict(main=_blank(), subs={}, sessions=set(), t0=None, t1=None))

    def put(tag, e, who, sub_type, sess):
        if tag is None:
            b = res["unattr_days"].setdefault(_day(e[1]), dict(main=_blank(), sub=_blank()))
            _add(b["main" if who == "main" else "sub"], e)
            return
        s = slot(tag)
        _add(s["main"] if who == "main" else s["subs"].setdefault(sub_type, _blank()), e)
        s["sessions"].add(sess)
        s["t0"] = min(s["t0"] or e[1], e[1])
        s["t1"] = max(s["t1"] or e[1], e[1])

    # 先走主對話,留下 (ts, tag) 切換點供子代理查
    timeline = {}
    for f in files:
        if f["kind"] != "main":
            continue
        cur, sw = None, []
        for e in f["ev"]:
            if e[0] == "u":
                t = _pick(e[2], known, True)
            else:
                t = _pick(e[8], known, False)
            if t:
                cur = t
                sw.append((e[1] or "", t))
            if e[0] != "a" or owner.get(e[2]) != f["path"]:
                continue
            put(cur, e, "main", None, f["id"][:8])
        sw.sort()
        timeline[f["id"]] = ([x[0] for x in sw], [x[1] for x in sw])
    for f in files:
        if f["kind"] != "sub":
            continue
        own = _pick(f["first_user"], known, False)
        ts_list, tg_list = timeline.get(f["parent"], ([], []))
        stype = f["meta"].get("agentType") or "?"
        for e in f["ev"]:
            if e[0] != "a" or owner.get(e[2]) != f["path"]:
                continue
            tag = own
            if tag is None:
                i = bisect.bisect_right(ts_list, f["t0"] or "") - 1
                tag = tg_list[i] if i >= 0 else None
            put(tag, e, "sub", stype, (f["parent"] or f["id"])[:8])
    return res


def analyze(conv_dirs=None, cache_path=CACHE_PATH, known=None, stats=None):
    files = load_files(conv_dirs, cache_path, stats)
    return attribute(files, known_tags() if known is None else known)


# ---------- 每片總量(合併 director llm_calls) ----------

def conv_totals(rec):
    """tags[tag] → 對話合計 dict(main_w/sub_w/main_eq/sub_eq/turns/input/cc/cr/out)。rec=None → 全 0。"""
    z = dict(main_w=0.0, sub_w=0.0, main_eq=0.0, sub_eq=0.0, turns=0, input=0, cache_creation=0, cache_read=0, output=0,
             sessions=[], t0=None, t1=None)
    if not rec:
        return z
    m = rec["main"]
    subs = rec["subs"].values()
    z.update(main_w=m["w"], main_eq=m["eq"], sub_w=sum(s["w"] for s in subs), sub_eq=sum(s["eq"] for s in subs),
             turns=m["turns"] + sum(s["turns"] for s in subs), input=m["input"] + sum(s["input"] for s in subs),
             cache_creation=m["cc"] + sum(s["cc"] for s in subs), cache_read=m["cr"] + sum(s["cr"] for s in subs),
             output=m["out"] + sum(s["out"] for s in subs), sessions=sorted(rec["sessions"]), t0=rec["t0"], t1=rec["t1"])
    return z


def usage_for_tag(tag, res=None, **kw):
    """給 director.write_session 用:該片對話合計(sessions=id 前 8 碼清單;main_w/sub_w 加權)。res 可傳入已算好的 analyze 結果。"""
    c = conv_totals((res or analyze(**kw))["tags"].get(tag))
    return dict(sessions=c["sessions"], turns=c["turns"], input=c["input"], cache_creation=c["cache_creation"],
                cache_read=c["cache_read"], output=c["output"], main_eq=round(c["main_eq"]), sub_eq=round(c["sub_eq"]),
                main_w=round(c["main_w"], 1), sub_w=round(c["sub_w"], 1))


def director_totals(tag):
    rep = _director().cost_report(tag)
    return rep, rep["total"]


def tag_report(tag, res):
    rep, dt = director_totals(tag)
    c = conv_totals(res["tags"].get(tag))
    rec = res["tags"].get(tag)
    return dict(tag=tag, director=rep, director_w=dt["cost_w"], director_eq=dt["cost_eq"],
                conv=c, subs={k: v for k, v in (rec["subs"] if rec else {}).items()},
                main=rec["main"] if rec else _blank(),
                total_w=round(dt["cost_w"] + c["main_w"] + c["sub_w"], 1),
                total_eq=round(dt["cost_eq"] + c["main_eq"] + c["sub_eq"], 1))


def mm(x):
    return f"{x / 1e6:,.2f}M"


# ---------- 中文片名 ----------

def load_names(path=None):
    try:
        d = json.loads(Path(path or NAMES_PATH).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def disp(tag, names=None):
    """「中文短名(tag)」;沒有中文名只回 tag。"""
    n = (load_names() if names is None else names).get(tag)
    return f"{n}({tag})" if n else tag


def ensure_name(tag, topic, path=None):
    """tag 還沒有中文名且有 topic → 用 topic 前 12 字寫入(director brief 呼叫,主對話之後可再改)。回傳是否新增。"""
    p = Path(path or NAMES_PATH)
    names = load_names(p)
    name = (topic or "").strip()[:12].strip()
    if not tag or not name or tag in names:
        return False
    names[tag] = name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(sorted(names.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


# ---------- 用量快照與校準(每 1% = 多少 w) ----------

def _utc(s):
    """ISO 字串(Z 或 ±hh:mm;無時區視為 UTC)→ aware UTC datetime。"""
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _key(d):
    """datetime → 秒精度 UTC 鍵字串,與事件 ts[:19] 同格式,可直接字串比較。"""
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _iso(d):
    return _key(d) + "Z"


def llm_events(projects_dir=None):
    """本專案所有 production.json 的 llm_calls → [(鍵, w)]。at 無時區 = 本機時間。"""
    out = []
    root = Path(projects_dir or P.PROJECTS)
    if not root.is_dir():
        return out
    for pj in root.glob("*/production.json"):
        if pj.parent.name.startswith("_"):
            continue
        try:
            d = json.loads(pj.read_text(encoding="utf-8"))
        except Exception:
            continue
        for c in d.get("llm_calls") or []:
            try:
                dt = datetime.fromisoformat(str(c["at"]).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.astimezone()
                w = c.get("cost_w")
                if w is None:
                    w = (c.get("cost_eq") or 0) * model_w(c.get("model"))
                out.append((_key(dt), float(w)))
            except Exception:
                continue
    return out


def build_w_index(files, extra=None):
    """帳號全部 w 的時間索引:所有對話檔的 assistant 訊息(跨檔去重)+ extra [(鍵,w)]。回傳 (keys, 累計 w)。"""
    owner = _owners(files)
    mw, items = {}, list(extra or [])
    for f in files:
        for e in f["ev"]:
            if e[0] != "a" or not e[1] or owner.get(e[2]) != f["path"]:
                continue
            w = mw.get(e[3])
            if w is None:
                w = mw[e[3]] = model_w(e[3])
            items.append((e[1][:19], eq_of(e[4], e[5], e[6], e[7]) * w))
    items.sort(key=lambda x: x[0])
    keys = [k for k, _ in items]
    cum = [0.0]
    for _, w in items:
        cum.append(cum[-1] + w)
    return keys, cum


def w_between(idx, a, b):
    """鍵 a ≤ ts ≤ b 的 w 合計。"""
    keys, cum = idx
    return cum[bisect.bisect_right(keys, b)] - cum[bisect.bisect_left(keys, a)]


def add_snapshot(h5, h5_reset, week, week_reset, fable=None, now=None, path=None):
    rec = dict(at=_iso(now or datetime.now(timezone.utc)), h5=int(h5), h5_reset=_iso(_utc(h5_reset)),
               week=int(week), week_reset=_iso(_utc(week_reset)))
    if fable is not None:
        rec["fable"] = int(fable)
    p = Path(path or SNAP_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_snapshots(path=None):
    p = Path(path or SNAP_PATH)
    out = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                _utc(d["at"])
                out.append(d)
            except Exception:
                continue
    out.sort(key=lambda d: d["at"])
    return out


KINDS = (("week", "week", "week_reset", 7 * 24, "週"), ("h5", "h5", "h5_reset", 5, "五小時"))


def calibrate(snaps, idx, n=CALIB_N, min_pct=MIN_PCT):
    """{kind: {coef(每 1% 的 w), rows:[{at,pct,w,coef}]}};該類沒有可用快照就不出現。
    視窗起點 = 重設 − 7 天/5 小時,起點用量 = 0%;快照時間不在視窗內、用量 < min_pct 的不納入;取最近 n 筆係數的中位數。"""
    out = {}
    for kind, pk, rk, hours, _ in KINDS:
        rows = []
        for s in snaps:
            try:
                pct, at = s.get(pk), _utc(s["at"])
                reset = _utc(s[rk])
            except Exception:
                continue
            start = reset - timedelta(hours=hours)
            if pct is None or pct < min_pct or not (start <= at <= reset):
                continue
            w = w_between(idx, _key(start), _key(at))
            if w > 0:
                rows.append(dict(at=s["at"], pct=pct, w=w, coef=w / pct))
        rows = rows[-n:]
        if rows:
            out[kind] = dict(coef=statistics.median(r["coef"] for r in rows), rows=rows)
    return out


def pct_of(w, cal, kind="week"):
    c = (cal or {}).get(kind)
    return w / c["coef"] if c else None


def fmt_pct(w, cal, kind="week"):
    p = pct_of(w, cal, kind)
    return "-" if p is None else f"{p:.1f}%"


def calib_note(cal):
    parts = []
    for kind, _, _, _, label in KINDS:
        c = (cal or {}).get(kind)
        if c:
            ats = "、".join(_utc(r["at"]).astimezone().strftime("%m-%d %H:%M") + f"({r['pct']}%)" for r in c["rows"])
            parts.append(f"{label}:每 1% = {mm(c['coef'])} w(取 {len(c['rows'])} 筆快照中位數:{ats})")
    return ";".join(parts)


def _remain(td):
    s = int(td.total_seconds())
    if s <= 0:
        return "已過重設"
    d, r = divmod(s, 86400)
    h, m = divmod(r, 3600)
    return (f"{d}d{h}h" if d else f"{h}h{m // 60:02d}m")


def now_line(snaps, idx, cal, now=None):
    """最新快照 + 自快照後估計又用了多少 %(同係數推估)。一行。"""
    if not snaps:
        return "尚無用量快照:先用 --snap --h5 .. --h5-reset .. --week .. --week-reset .. 寫入"
    now = now or datetime.now(timezone.utc)
    s = snaps[-1]
    at = _utc(s["at"])
    w = w_between(idx, _key(at + timedelta(seconds=1)), _key(now))
    out = [f"快照 {at.astimezone():%m-%d %H:%M}"]
    for kind, pk, rk, _, label in KINDS[::-1]:
        left = _utc(s[rk]) - now
        base = s.get(pk)
        add = pct_of(w, cal, kind)
        if left.total_seconds() <= 0:
            out.append(f"{label} 快照視窗已重設(舊值 {base}% 作廢)")
        elif add is None:
            out.append(f"{label} {base}%(重設剩 {_remain(left)};無係數)")
        else:
            out.append(f"{label} {base}% → 約 {base + add:.0f}%(+{add:.1f}%,重設剩 {_remain(left)})")
    return ";".join(out) + f";自快照後新增 {mm(w)} w"


# ---------- 輸出 ----------

def render_tag(r, cal=None, names=None):
    c = r["conv"]
    has = bool((cal or {}).get("week"))
    hdr = "來源 | 次/回合 | eq | w" + (" | 占週上限" if has else "")

    def row(label, n, eq, w):
        return f"{label} | {n} | {mm(eq)} | {mm(w)}" + (f" | {fmt_pct(w, cal)}" if has else "")

    L = [f"{disp(r['tag'], names)} token 總量(eq=in+cc+5out+0.1cr;w=eq×模型權重;M=百萬)", hdr]
    for s in r["director"]["segs"]:
        st = s["subtotal"]
        L.append(row(f"director LLM {s['seg']} 段", st['n'], st['cost_eq'], st['cost_w']))
    L.append(row("director LLM 小計", r['director']['total']['n'], r['director_eq'], r['director_w']))
    m = r["main"]
    L.append(row("主對話", m['turns'], m['eq'], m['w']))
    for k, v in sorted(r["subs"].items(), key=lambda kv: -kv[1]["w"]):
        L.append(row(f"子代理 {k}", v['turns'], v['eq'], v['w']))
    L.append(row("對話小計", c['turns'], c['main_eq'] + c['sub_eq'], c['main_w'] + c['sub_w']))
    tot = row("合計", "-", r['total_eq'], r['total_w'])
    h5 = pct_of(r["total_w"], cal, "h5")
    if h5 is not None:
        tot += f"(≈ {h5 / 100:.1f} 個五小時額度)"
    L.append(tot)
    L.append(f"期間 {c['t0'] or '-'} → {c['t1'] or '-'};對話 {', '.join(c['sessions']) or '-'}")
    L.append(("校準 " + calib_note(cal)) if has else "尚無用量快照,只輸出 w:先用 --snap 寫入官方百分比(見 video_cost.py 檔頭)")
    return "\n".join(L)


def _channel(tag):
    for name in ("production.json", "brief.json", "spec.json"):
        try:
            d = json.loads((P.PROJECTS / tag / name).read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("channel"):
            return d["channel"]
    return ""


def _created(tag, rec):
    try:
        d = json.loads((P.PROJECTS / tag / "production.json").read_text(encoding="utf-8"))
        if d.get("created"):
            return d["created"][:10]
    except Exception:
        pass
    return _day(rec["t0"]) if rec and rec["t0"] else ""


def ledger(res, since=None, known=None, cal=None, names=None):
    names = load_names() if names is None else names
    rows = []
    for tag in sorted(known_tags() if known is None else known):
        rec = res["tags"].get(tag)
        try:
            rep, dt = director_totals(tag)
        except Exception:
            rep, dt = None, dict(cost_w=0, cost_eq=0)
        if not rec and not dt["cost_w"]:
            continue
        start = _created(tag, rec)
        if since and start < since:
            continue
        c = conv_totals(rec)
        cw = c["main_w"] + c["sub_w"]
        row = dict(tag=tag, name=names.get(tag, ""), channel=_channel(tag), start=start, director_w=dt["cost_w"], conv_w=cw,
                   total_w=dt["cost_w"] + cw, total_eq=dt["cost_eq"] + c["main_eq"] + c["sub_eq"],
                   sessions=len(c["sessions"]))
        wp = pct_of(row["total_w"], cal, "week")
        if wp is not None:
            row["week_pct"] = round(wp, 2)
        rows.append(row)
    rows.sort(key=lambda r: (r["start"], r["tag"]))
    un = {d: v for d, v in sorted(res["unattr_days"].items()) if not since or d >= since}
    return rows, un


def render_ledger(rows, un, since=None, cal=None, names=None):
    has = bool((cal or {}).get("week"))
    L = [f"# token 總表(每片:director 子程序 LLM + 對話)", "",
         f"產生 {datetime.now():%Y-%m-%d %H:%M};`python -X utf8 pipeline\\video_cost.py --all`" + (f" --since {since}" if since else "")
         + "。週 % = 占週上限(總 w ÷ 每 1% 的 w);w = eq×模型權重(opus 5/sonnet 1/haiku 1/3/fable 暫定 5);M = 百萬。"
         "對話歸屬為逐則訊息依 tag 切換,見 pipeline\\video_cost.py 檔頭。", ""]
    L.append(("校準:" + calib_note(cal) + "。偏差:別專案用 `claude -p --no-session-persistence` 不留紀錄 → 係數偏大、片的 % 偏小;Fable 權重暫定。")
             if has else "尚無用量快照,只輸出 w:先用 `video_cost.py --snap ...` 寫入官方百分比。")
    L.append("")
    if has:
        L += ["| 片 | 頻道 | 開工日 | 週 % | director w | 對話 w | 總 eq | 對話數 | 總 w |", "|---|---|---|---|---|---|---|---|---|"]
    else:
        L += ["| 片 | 頻道 | 開工日 | director w | 對話 w | 總 w | 總 eq | 對話數 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        nm = disp(r["tag"], names)
        if has:
            L.append(f"| {nm} | {r['channel'] or '-'} | {r['start'] or '-'} | {fmt_pct(r['total_w'], cal)} | {mm(r['director_w'])} | "
                     f"{mm(r['conv_w'])} | {mm(r['total_eq'])} | {r['sessions']} | {mm(r['total_w'])} |")
        else:
            L.append(f"| {nm} | {r['channel'] or '-'} | {r['start'] or '-'} | {mm(r['director_w'])} | {mm(r['conv_w'])} | "
                     f"{mm(r['total_w'])} | {mm(r['total_eq'])} | {r['sessions']} |")
    tw = sum(r['total_w'] for r in rows)
    if has:
        L.append(f"| **合計** | | | {fmt_pct(tw, cal)} | {mm(sum(r['director_w'] for r in rows))} | {mm(sum(r['conv_w'] for r in rows))} | "
                 f"{mm(sum(r['total_eq'] for r in rows))} | | {mm(tw)} |")
    else:
        L.append(f"| **合計** | | | {mm(sum(r['director_w'] for r in rows))} | {mm(sum(r['conv_w'] for r in rows))} | "
                 f"{mm(tw)} | {mm(sum(r['total_eq'] for r in rows))} | |")
    L += ["", f"## {UNATTR} 依日小計(對話,未能對到任何片;含改程式、規劃、選題等)", ""]
    L += (["| 日 | 週 % | 主對話 w | 子代理 w | 合計 w | 合計 eq |", "|---|---|---|---|---|---|"] if has
          else ["| 日 | 主對話 w | 子代理 w | 合計 w | 合計 eq |", "|---|---|---|---|---|"])
    for d, v in un.items():
        tot = v['main']['w'] + v['sub']['w']
        pc = f"{fmt_pct(tot, cal)} | " if has else ""
        L.append(f"| {d} | {pc}{mm(v['main']['w'])} | {mm(v['sub']['w'])} | {mm(tot)} | {mm(v['main']['eq'] + v['sub']['eq'])} |")
    uw = sum(v["main"]["w"] + v["sub"]["w"] for v in un.values())
    L.append(f"| **合計** | {fmt_pct(uw, cal) + ' | ' if has else ''}| | {mm(uw)} | |")
    return "\n".join(L) + "\n"


def write_ledger(res, since=None, cal=None):
    names = load_names()
    rows, un = ledger(res, since, cal=cal, names=names)
    md = render_ledger(rows, un, since, cal, names)
    out = P.REPO / "channel" / "token_ledger.md"
    out.write_text(md, encoding="utf-8")
    cal_j = {k: dict(coef=v["coef"], rows=v["rows"]) for k, v in (cal or {}).items()}
    (out.with_suffix(".json")).write_text(json.dumps(dict(since=since, calibration=cal_j, rows=rows, unattributed_days=un),
                                                     ensure_ascii=False, indent=1), encoding="utf-8")
    return rows, un, out


def main(argv=None):
    ap = argparse.ArgumentParser(description="每支影片 token 總量(director LLM + 對話),可換算成占上限 %")
    ap.add_argument("tag", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="跨片總表,寫 channel\\token_ledger.md/.json")
    ap.add_argument("--since", help="YYYY-MM-DD;只列開工日 >= 此日的片與未歸屬日")
    ap.add_argument("--snap", action="store_true", help="寫一筆用量快照到 channel\\usage_snapshots.jsonl(需 --h5 --h5-reset --week --week-reset)")
    ap.add_argument("--h5", type=int, help="五小時視窗已用 %%")
    ap.add_argument("--h5-reset", help="五小時視窗重設時間 ISO(UTC)")
    ap.add_argument("--week", type=int, help="週視窗已用 %%")
    ap.add_argument("--week-reset", help="週視窗重設時間 ISO(UTC)")
    ap.add_argument("--fable", type=int, help="Fable 週用量 %%(只記錄,不參與校準)")
    ap.add_argument("--now", action="store_true", help="印最新快照與自快照後估計又用了多少 %%")
    a = ap.parse_args(argv)
    if a.snap:
        if None in (a.h5, a.h5_reset, a.week, a.week_reset):
            ap.error("--snap 要同時給 --h5 --h5-reset --week --week-reset")
        rec = add_snapshot(a.h5, a.h5_reset, a.week, a.week_reset, a.fable)
        print(f"已寫快照 {rec} → {SNAP_PATH}")
        return 0
    if not a.tag and not a.all and not a.now:
        ap.error("要給 <tag>、--all、--now 或 --snap")
    st = {}
    snaps = load_snapshots()
    # 有快照(或要 --now)才掃帳號下所有專案(校準);否則只掃本專案
    files = load_files(all_conv_dirs() if (snaps or a.now) else None, stats=st, light_other=True)
    idx = build_w_index(files, llm_events()) if snaps else None
    cal = calibrate(snaps, idx) if snaps else None
    if a.now:
        print(now_line(snaps, idx, cal))
        return 0
    res = attribute([f for f in files if f.get("root", CV_PREFIX).startswith(CV_PREFIX)], known_tags())
    if a.all:
        rows, un, out = write_ledger(res, a.since, cal)
        print(render_ledger(rows, un, a.since, cal))
        print(f"已寫 {out}(快取 命中 {st['hit']} / 重解析 {st['miss']})")
        return 0
    r = tag_report(a.tag, res)
    if a.json:
        r["name"] = load_names().get(a.tag, "")
        if cal and cal.get("week"):
            r["week_pct"] = round(pct_of(r["total_w"], cal), 2)
        print(json.dumps(r, ensure_ascii=False, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o)))
    else:
        print(render_tag(r, cal))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
