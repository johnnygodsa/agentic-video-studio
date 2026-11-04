#!/usr/bin/env python3
r"""導演層骨架(Phase 0):每支片的 production.json,從既有產物推斷五段狀態。規格:pipeline\docs\director.md。

python -X utf8 pipeline/director.py init <tag> [--channel ChannelA]
python -X utf8 pipeline/director.py status <tag> [--json] [--write]
python -X utf8 pipeline/director.py log <tag> --fn NAME --model M --in N --out N [--cache N] [--cost X]
python -X utf8 pipeline/director.py intervene <tag> --what "一句"
python -X utf8 pipeline/director.py feedback <tag> --text "一句" [--case T12]
python -X utf8 pipeline/director.py brief <tag> --topic T --angle A --channel ChannelA --format 評論片 [--publish ... --url U ...]
python -X utf8 pipeline/director.py run <tag> --from A|B|B4|C|D|E --to A|B|B4|C|D|E [--ver vN] [--backend local|kaggle|colab]
      [--title 片名 --channel 頻道] [--publish-at ISO|HH:MM|auto] [--cover png] [--check-only] [--dry-run] [--max-attempts 3]
python -X utf8 pipeline/director.py --explain A|B|B4|C|D|E      印該段 gate 項目
status/init/log 等不驅動流程、只讀產物;run 照順序跑步驟並評 gates\gate_*;A/B/B4 與 C 段改句走 director_ab.py(規格 docs\director_ab.md)。
run 只寫 projects\<tag>\production.json、output\<tag>\director_<ver>.log 與各步產物;A/B/B4 過 gate 時 commit。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P  # noqa: E402

SEGMENTS = ("0", "A", "B", "B4", "C", "D", "E")
SEG_NAME = {"0": "0 選題", "A": "A 資料", "B": "B 文案", "B4": "B4 配音稿", "C": "C 配音", "D": "D 畫面", "E": "E 自審上片"}
SEG_STAGE = {"A": "A資料", "B": "B文案", "B4": "B4配音稿", "C": "C配音", "D": "D畫面", "E": "E自審"}
STAGES = ("0選題", "A資料", "B文案", "B4配音稿", "C配音", "已凍結", "D畫面", "E自審", "已排程", "結案")
DONE, PART, NONE = "完成", "進行中", "未開始"
CACHE_W, OUT_W = 0.1, 5.0  # cost_eq = in + 5*out + 0.1*cache_read
MODEL_W = {"opus": 5.0, "fable": 5.0, "sonnet": 1.0, "haiku": 1 / 3}  # 依 API 單價比;model id 含該字串即套用,都不含 = 1.0。fable 暫定 5.0(單價未知,video_cost 對話統計用)
_LOCK = threading.Lock()  # assets 兩呼叫平行,log_call 不可互蓋


def model_w(model_id):
    m = (model_id or "").lower()
    return next((w for k, w in MODEL_W.items() if k in m), 1.0)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def prod_path(tag):
    return P.PROJECTS / tag / "production.json"


def _read_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def board_rec(tag):
    try:
        import board
        return board.get(tag) or {}
    except Exception:  # noqa: BLE001  board 讀不到不擋 status
        return {}


def guess_channel(tag, given=None):
    if given:
        return given
    prod = _read_json(prod_path(tag)) or {}
    if prod.get("channel"):
        return prod["channel"]
    ch = board_rec(tag).get("channel")
    if ch:
        return ch
    spec = _read_json(P.PROJECTS / tag / "spec.json") or {}
    return spec.get("channel") or ""


# ---------- 讀檔小工具 ----------

def _rel(p):
    p = Path(p)
    for base in (P.ROOT, P.REPO):
        try:
            return p.relative_to(base).as_posix()
        except ValueError:
            continue
    return p.as_posix()


def _item(iid, ok, note="", path=None):
    return {"id": iid, "ok": bool(ok), "note": note, "path": _rel(path) if path and ok else None}


def _glob(d, pat):
    try:
        return sorted(Path(d).glob(pat))
    except OSError:
        return []


def _first(paths):
    return paths[0] if paths else None


def count_pending_facts(p):
    """facts 表格內狀態欄是「待查」的列數(圖例行不是表格列,不計)。"""
    n = 0
    for line in Path(p).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("|") and any(c.strip().startswith("待查") for c in line.strip("|").split("|")):
            n += 1
    return n


def _ver_no(p):
    m = re.search(r"(?:^|_)v(\d+)(?=[_.])", Path(p).name)
    return int(m.group(1)) if m else 0


def mp4_list(tag):
    return sorted((p for p in _glob(P.output_dir(tag), f"{tag}_v*.mp4") if "_720p" not in p.name), key=_ver_no)


def _count(v):
    return len(v) if isinstance(v, (list, tuple, dict)) else int(v or 0)


def find_video_id(tag, prod):
    vid = ((prod or {}).get("artifacts") or {}).get("video_id")
    if vid:
        return vid
    h = P.PROJECTS / tag / "handoff.md"
    if h.exists():
        m = re.search(r"video_id\W{0,4}([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])", h.read_text(encoding="utf-8", errors="replace"))
        if m:
            return m.group(1)
    return None


# ---------- 各段檢查:回傳 items ----------

def check_0(tag, ctx):
    ch = ctx["channel"]
    out = []
    for kind in ("scout", "critic"):
        fs = [p for p in _glob(P.TMP, f"{kind}_*") if not ch or ch in p.name]
        out.append(_item(f"{kind}檔", fs, f"tmp\\{kind}_*{ch}* 沒有", _first(fs)))
    return out


def check_a(tag, ctx):
    from gates import gate_a
    return gate_a.status(tag, ctx)


def check_b(tag, ctx):
    from gates import gate_b
    return gate_b.status(tag, ctx)


def check_b4(tag, ctx):
    from gates import gate_b4
    return gate_b4.status(tag, ctx)


def check_c(tag, ctx):
    from gates import gate_c
    return gate_c.status(tag, ctx)


def check_d(tag, ctx):
    from gates import gate_d
    return gate_d.status(tag, ctx)


def check_e(tag, ctx):
    from gates import gate_e
    return gate_e.status(tag, ctx)


CHECKS = {"0": check_0, "A": check_a, "B": check_b, "B4": check_b4, "C": check_c, "D": check_d, "E": check_e}


def seg_state(items):
    ok = sum(1 for i in items if i["ok"])
    return DONE if ok == len(items) else PART if ok else NONE


def infer_stage(states, board_stage):
    if board_stage == "結案":
        return "結案"
    last = next((s for s in ("E", "D", "C", "B4", "B", "A") if states[s] != NONE), None)
    if last is None:
        return "0選題"
    if last == "C" and states["C"] == DONE:
        return "已凍結"
    if last == "E" and (states["E"] == DONE or board_stage == "已排程"):
        return "已排程"
    return SEG_STAGE[last]


def collect(tag, channel=None):
    """推斷結果 dict:tag/channel/stage/board_stage/gates/artifacts/versions(只讀,不寫任何檔)。"""
    prod = _read_json(prod_path(tag)) or {}
    ctx = {"channel": guess_channel(tag, channel), "board": board_rec(tag), "video_id": find_video_id(tag, prod)}
    gates, states = {}, {}
    old_gates = prod.get("gates") or {}
    for seg in SEGMENTS:
        items = CHECKS[seg](tag, ctx)
        states[seg] = seg_state(items)
        gates[seg] = {"passed": states[seg] == DONE, "state": states[seg], "items": items,
                      "attempts": (old_gates.get(seg) or {}).get("attempts", 0)}
    out = P.output_dir(tag)
    pd = P.PROJECTS / tag
    mp = mp4_list(tag)

    def art(*cands):
        p = _first([c for c in cands if c and Path(c).exists()])
        return _rel(p) if p else None

    thumb = art(*(_glob(out, "*_thumb*.png") + _glob(out, "*cover*.png")))
    artifacts = {"script": art(P.REPO / tag / "script.txt"), "facts": art(pd / "facts.md"),
                 "visual_table": art(pd / "visual_table.md"), "tts_script": art(P.build_dir(tag) / "tts_script.md"),
                 "freeze": art(pd / "freeze.json"), "timeline": art(P.build_dir(tag) / "timeline_tts.json"),
                 "mp4": _rel(mp[-1]) if mp else None, "cover": thumb, "video_id": ctx["video_id"]}
    versions = [{"ver": f"v{_ver_no(p)}", "mp4": _rel(p),
                 "look": art(out / f"look_v{_ver_no(p)}.md"), "notes": art(out / f"v{_ver_no(p)}_說明.md")} for p in mp]
    return {"tag": tag, "channel": ctx["channel"], "stage": infer_stage(states, ctx["board"].get("stage")),
            "board_stage": ctx["board"].get("stage"), "states": states, "gates": gates,
            "artifacts": artifacts, "versions": versions}


# ---------- production.json ----------

def _blank(tag, channel):
    return {"tag": tag, "channel": channel, "created": now_iso(), "stage": "0選題", "gates": {}, "llm_calls": [],
            "interventions": [], "feedback": [], "artifacts": {}, "versions": []}


def load_prod(tag):
    return _read_json(prod_path(tag))


def init(tag, channel=None):
    """不存在才建;回傳 (資料, 是否新建)。"""
    cur = load_prod(tag)
    if cur is not None:
        return cur, False
    data = _blank(tag, guess_channel(tag, channel))
    _atomic_write(prod_path(tag), data)
    return data, True


def write_back(tag, res):
    data, _ = init(tag, res["channel"])
    at = now_iso()
    data["stage"] = res["stage"]
    if res["channel"]:
        data["channel"] = res["channel"]
    for seg, g in res["gates"].items():
        prev = (data.get("gates") or {}).get(seg) or {}
        keep_at = prev.get("at") if prev.get("passed") == g["passed"] and prev.get("at") else at
        data.setdefault("gates", {})[seg] = {"passed": g["passed"], "at": keep_at, "state": g["state"],
                                             "items": [{k: i[k] for k in ("id", "ok", "note")} for i in g["items"]],
                                             "attempts": g["attempts"]}
    data["artifacts"] = res["artifacts"]
    data["versions"] = res["versions"]
    _atomic_write(prod_path(tag), data)  # llm_calls/interventions/feedback 是讀進來再原樣寫回
    return data


def _append(tag, key, rec):
    with _LOCK:
        data, _ = init(tag)
        data.setdefault(key, []).append(rec)
        _atomic_write(prod_path(tag), data)
    return rec


def log_call(tag, fn, model, tin, tout, cache=0, cost=None, secs=None, ok=None, seg=None, agent=None):
    """secs/ok/seg/agent 由 llm.py 帶,沒給就不寫(舊呼叫相容)。"""
    if cost is None:
        cost = round(tin + OUT_W * tout + CACHE_W * cache, 1)
    rec = {"at": now_iso(), "fn": fn, "model": model, "input_tokens": tin, "output_tokens": tout, "cache_read": cache, "cost_eq": cost,
           "cost_w": round(cost * model_w(model), 1)}
    rec.update({k: v for k, v in (("secs", secs), ("ok", ok), ("seg", seg), ("agent", agent)) if v is not None})
    return _append(tag, "llm_calls", rec)


def intervene(tag, what):
    return _append(tag, "interventions", {"at": now_iso(), "who": "user", "what": what, "resolved": False})


def feedback(tag, text, case=None):
    return _append(tag, "feedback", {"at": now_iso(), "text": text, "taste_case": case})


# ---------- run:C→E 串接(規格 docs\director.md「run」一節) ----------

RUN_SEGS = ("A", "B", "B4", "C", "D", "E")
VER_SEGS = ("C", "D", "E")  # 這幾段要 --ver
SCHEDULED = ("已排程", "結案")


def _gate_mod(seg):
    from gates import get
    return get(seg)


def _py():
    return [str(P.TTS_ENV), "-X", "utf8"]


def _sys():
    return [sys.executable, "-X", "utf8"]


def _script(*parts):
    return _rel(P.REPO.joinpath("pipeline", *parts))


def _newer(a, b):
    """a 存在且比 b 新(b 不存在也算)。"""
    a, b = Path(a), Path(b)
    return a.exists() and (not b.exists() or a.stat().st_mtime > b.stat().st_mtime)


def run_ctx(tag, a):
    prod = load_prod(tag) or {}
    return {"tag": tag, "ver": a.ver, "channel": guess_channel(tag, a.channel), "title": a.title or prod.get("title") or "",
            "board": board_rec(tag), "prod": prod, "video_id": find_video_id(tag, prod)}


def _refresh(tag, ctx):
    ctx["prod"] = load_prod(tag) or {}
    ctx["board"] = board_rec(tag)
    ctx["video_id"] = find_video_id(tag, ctx["prod"])
    return ctx


def _voice_frozen(tag):
    """配音凍結步的跳過條件:freeze.json 存在且 tts_review.json 品管未過 0。"""
    rv = _read_json(P.build_dir(tag) / "tts_review.json")
    return (P.PROJECTS / tag / "freeze.json").exists() and rv is not None and _count(rv.get("failed")) == 0


def plan_steps(tag, seg, ctx, a):
    """本段步驟:[{step, cmd, skip, block, status_only}];skip/block 是原因字串或 None。"""
    ver, steps = a.ver, []
    if seg in ("A", "B", "B4"):
        import director_ab as AB
        return AB.steps(tag, seg, ctx, a)

    def add(step, cmd, skip=None, block=None, status_only=False, fn=None, desc=""):
        steps.append({"step": step, "cmd": cmd, "skip": skip, "block": block, "status_only": status_only, "fn": fn, "desc": desc})

    if seg == "C":
        frozen0 = "已凍結且品管未過 0" if _voice_frozen(tag) else None
        add("預檢", _py() + [_script("tts_precheck.py"), tag],   # 配音前預檢:error>0(會吞字)結束碼 1 -> 卡點;已凍結片不跑
            skip=frozen0 or ("CV_SKIP_PRECHECK=1" if os.environ.get("CV_SKIP_PRECHECK") else None))
        c0 = P.PROJECTS / tag / "c0_report.json"
        add("c0", _py() + [_script("tts_c0.py"), tag],
            skip="c0_report.json 比 script.txt 新" if _newer(c0, P.REPO / tag / "script.txt") else None)
        frozen = "已凍結且品管未過 0" if _voice_frozen(tag) else None
        disp = _sys() + [_script("tts_dispatch.py"), tag]
        if a.backend is None:
            add("後端", disp, skip=frozen, status_only=True)
        elif a.backend == "kaggle":
            add("後端", disp + ["--prefer", "kaggle", "--foreground"], skip=frozen)
        elif a.backend == "colab":
            add("後端", None, skip=frozen, block="Colab 要使用者上傳")
        import director_ab as AB
        add("改句迴圈", None, skip=frozen, fn=lambda: AB.step_qc(tag, ctx, a),
            desc="make_version --tts-review → 品管/時長/E4 有句 → line_fix(qc) → 重跑,≤3 輪")
        add("配音凍結", _sys() + [_script("make_version.py"), "--tag", tag, "--ver", ver, "--tts-review", "--freeze"],
            skip=frozen)
    elif seg == "D":
        mp = P.output_dir(tag) / f"{tag}_{ver}.mp4"
        extra = (["--title", ctx["title"]] if ctx["title"] else []) + (["--channel", ctx["channel"]] if ctx["channel"] else [])
        add("出片", _sys() + [_script("make_version.py"), "--tag", tag, "--ver", ver] + extra,
            skip=f"{mp.name} 比 timeline_tts.json 新" if _newer(mp, P.build_dir(tag) / "timeline_tts.json") else None)
        add("眼睛", _py() + [_script("senses", "eye.py"), "--tag", tag, "--ver", ver])
    elif seg == "E":
        from gates import gate_e
        sc, found = gate_e.find_sidecar(tag, ver, ctx["title"])
        title, ch = ctx["title"] or found, ctx["channel"]
        done = (sc is not None or ctx["video_id"]) and ctx["board"].get("stage") in SCHEDULED  # sidecar 上傳後會被後端收走
        cmd = _sys() + [_script("deliver.py"), "--tag", tag, "--ver", ver, "--title", title or "<title?>",
                        "--channel", ch or "<channel?>", "--enqueue", "--publish-at", a.publish_at]
        if a.cover:
            cmd += ["--cover", a.cover]
        block = "需要 --title" if not title else "需要 --channel" if not ch else None
        add("交付排程", cmd, skip="sidecar 已存在且 board 已排程" if done else None, block=None if done else block)
    return steps


def _block(tag, seg, step, reason, rc=None, log=None, count=True):
    data, _ = init(tag)
    data.setdefault("blocks", []).append({"at": now_iso(), "seg": seg, "step": step, "reason": reason, "rc": rc, "log": log})
    g = data.setdefault("gates", {}).setdefault(seg, {})
    g["passed"] = False
    if count:
        g["attempts"] = g.get("attempts", 0) + 1
    _atomic_write(prod_path(tag), data)
    print(f"卡點 {seg}/{step}:{reason}")


def _warn(tag, seg, step, note):
    print(f"warn {seg}/{step}:{note}")
    return _append(tag, "warns", {"at": now_iso(), "seg": seg, "step": step, "note": note})


def _tail(text, n=3, cap=300):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return " | ".join(lines[-n:])[-cap:] or "(無輸出)"


def eval_gate(tag, seg, ctx):
    """評本段 gate、寫回 gates[seg];不過則記卡點。回傳 (passed, items)。"""
    items = _gate_mod(seg).run(tag, ctx["ver"], _refresh(tag, ctx))
    passed = all(i["ok"] for i in items)
    data, _ = init(tag)
    g = data.setdefault("gates", {}).setdefault(seg, {})
    g.update(passed=passed, state=seg_state(items), items=[{k: i[k] for k in ("id", "ok", "note")} for i in items])
    if passed:
        g["at"] = now_iso()
    g.setdefault("attempts", 0)
    _atomic_write(prod_path(tag), data)
    if not passed:
        _block(tag, seg, "gate", ";".join(f"{i['id']}:{i['note']}" for i in items if not i["ok"]))
    return passed, items


def _exec(tag, ver, seg, step, cmd):
    """跑一步:輸出追加到 output\\<tag>\\director_<ver>.log,runs 記 rc 與秒數。回傳 (rc, 本段輸出, 段落標記)。"""
    log = P.output_dir(tag) / f"director_{ver}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    marker = f"=== {seg}/{step} {now_iso()}"
    line = subprocess.list2cmdline(cmd)
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{marker}\n{line}\n")
    start = log.stat().st_size
    t0 = time.time()
    with open(log, "ab") as f:
        try:
            rc = subprocess.run(cmd, cwd=P.ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
        except OSError as e:
            f.write(f"無法執行:{e}\n".encode("utf-8"))
            rc = -1
    secs = round(time.time() - t0, 1)
    with open(log, "rb") as f:
        f.seek(start)
        text = f.read().decode("utf-8", "replace")
    _append(tag, "runs", {"at": now_iso(), "seg": seg, "step": step, "cmd": line, "rc": rc, "secs": secs, "log": marker})
    return rc, text, marker


def _precheck(tag, seg, ctx):
    """前置 gate:A 無;C 看 B4 完成(寬鬆,舊片沒有新 gate 的產物);B/B4/D/E 看上一段 gate。回傳不過原因或 None。"""
    if seg == "A":
        return None
    if seg == "C":
        items = check_b4(tag, ctx)
    else:
        prev = RUN_SEGS[RUN_SEGS.index(seg) - 1]
        items = _gate_mod(prev).run(tag, ctx["ver"], _refresh(tag, ctx))
    bad = [i["note"] for i in items if not i["ok"]]
    return f"前置未過:{';'.join(bad)}" if bad else None


def _skip(st):
    """步驟略過原因;A/B 段依前一步產物,callable 在執行前才評。"""
    return st["skip"]() if callable(st["skip"]) else st["skip"]


def print_plan(tag, segs, ctx, a):
    print(f"{tag} run {segs[0]}→{segs[-1]} {a.ver or ''}(dry-run,不執行;cwd {P.ROOT})")
    for seg in segs:
        for st in plan_steps(tag, seg, ctx, a):
            cmd = subprocess.list2cmdline(st["cmd"]) if st["cmd"] else st.get("desc") or "-"
            skip = _skip(st)
            tail = (f"  [略過:{skip}]" if skip else f"  [卡點:{st['block']}]" if st["block"]
                    else "  [只印狀態,結束碼 4 → 卡點 待選後端]" if st["status_only"] else "")
            print(f"{seg}/{st['step']}: {cmd}{tail}")
        print(f"{seg}/gate: {'、'.join(_gate_mod(seg).IDS)}")

def _run_fn(tag, seg, st):
    """跑 fn 步(LLM / 改句);回傳卡點原因或 None。"""
    import director_ab as AB
    t0 = time.time()
    try:
        st["fn"]()
        why = None
    except AB.Block as b:
        why = b.reason
    _append(tag, "runs", {"at": now_iso(), "seg": seg, "step": st["step"], "cmd": st["desc"], "rc": 3 if why else 0,
                          "secs": round(time.time() - t0, 1), "log": None})
    return why


def run(tag, a):
    """回傳結束碼:0 全過、3 卡點、2 參數錯。"""
    i0, i1 = RUN_SEGS.index(a.from_), RUN_SEGS.index(a.to)
    if i0 > i1:
        print(f"--from {a.from_} 在 --to {a.to} 之後", file=sys.stderr)
        return 2
    segs = RUN_SEGS[i0:i1 + 1]
    if not a.ver and any(s in VER_SEGS for s in segs):
        print("C/D/E 段要 --ver", file=sys.stderr)
        return 2
    ctx = run_ctx(tag, a)
    if a.dry_run:
        print_plan(tag, segs, ctx, a)
        return 0
    if a.check_only:
        rc = 0
        for seg in segs:
            passed, items = eval_gate(tag, seg, ctx)
            print(f"gate {seg}:{'過' if passed else '不過'}")
            for i in items:
                print(f"  ok  {i['id']}:{i['path'] or i['note']}" if i["ok"] else f"  NG  {i['id']}:{i['note']}")
            rc = rc if passed else 3
        return rc
    for n, seg in enumerate(segs):
        g = ((load_prod(tag) or {}).get("gates") or {}).get(seg) or {}
        if not g.get("passed") and g.get("attempts", 0) >= a.max_attempts:
            _block(tag, seg, "attempts", f"已試 {g['attempts']} 次(--max-attempts {a.max_attempts})", count=False)
            return 3
        if n == 0:
            why = _precheck(tag, seg, ctx)
            if why:
                _block(tag, seg, "前置", why)
                return 3
        for st in plan_steps(tag, seg, ctx, a):
            skip = _skip(st)
            if skip:
                print(f"略過 {seg}/{st['step']}:{skip}")
                continue
            if st["block"]:
                _block(tag, seg, st["step"], st["block"])
                return 3
            if st.get("fn"):
                print(f"執行 {seg}/{st['step']}:{st['desc']}")
                why = _run_fn(tag, seg, st)
                if why:
                    _block(tag, seg, st["step"], why)
                    return 3
                continue
            print(f"執行 {seg}/{st['step']}:{subprocess.list2cmdline(st['cmd'])}")
            rc, text, marker = _exec(tag, a.ver or "ab", seg, st["step"], st["cmd"])
            if st["status_only"]:
                _block(tag, seg, st["step"], "待選後端:" + (text.strip()[-2000:] or "(無輸出)"), rc, marker)
                return 3
            if rc != 0:
                reason = f"結束碼 {rc}:{_tail(text)}"
                if st["step"] == "預檢" and rc == 1:
                    import tts_precheck as PC
                    reason = PC.block_reason(tag) or reason
                if st["step"] == "配音凍結" and rc == 3:
                    bad = [i for i in _gate_mod("C").run(tag, a.ver, _refresh(tag, ctx)) if not i["ok"]]
                    reason = "品管未過:" + (";".join(f"{i['id']}:{i['note']}" for i in bad) or _tail(text))
                _block(tag, seg, st["step"], reason, rc, marker)
                return 3
            if st["step"] == "交付排程" and a.publish_at not in (None, "auto"):
                data, _ = init(tag)
                data["publish_at"] = a.publish_at
                m = re.search(r"已排程 ([A-Za-z0-9_-]{11}) ->", text or "")
                if m:  # sidecar 上傳後被後端收走,video_id 才是 gate_e 的憑證
                    data.setdefault("artifacts", {})["video_id"] = m.group(1)
                _atomic_write(prod_path(tag), data)
        passed, _ = eval_gate(tag, seg, ctx)
        print(f"gate {seg}:{'過' if passed else '不過'}")
        if not passed:
            return 3
        if seg == "E":
            _write_session_quiet(tag)
        if seg in ("A", "B", "B4"):
            import director_ab as AB
            AB.commit_seg(tag, seg)
    return 0


def explain(seg):
    mod = _gate_mod(seg)
    print(f"{SEG_NAME[seg]} gate 項目:{'、'.join(mod.IDS)}")
    print((mod.run.__doc__ or "").strip())


def write_brief(a):
    from gates import specs
    if not specs.known(a.channel, a.format):
        print(f"片型不在 specs.FORMATS:{a.channel}/{a.format}", file=sys.stderr)
        return 2
    import director_ab as AB
    d = AB.write_brief(a.tag, {"channel": a.channel, "format": a.format, "topic": a.topic, "angle": a.angle, "spoiler": a.spoiler,
                               "played": a.played, "one_line": a.one_line, "publish": a.publish, "urls": a.url,
                               "event": a.event, "query": a.query, "allow_short": a.allow_short or None, "flow": a.flow})
    print(f"{a.tag}: brief.json 已寫({d['channel']} {d['format']})")
    if a.topic:   # 中文片名:channel	ag_names.json 還沒有這個 tag 就用 topic 前 12 字(主對話之後可再改);best-effort
        try:
            import video_cost
            video_cost.ensure_name(a.tag, a.topic)
        except Exception:
            pass
    return 0


# ---------- cost / usage:每片 token 量測(計畫 PLAN_token重設計 §5.1) ----------

_SUMK = ("n", "input", "output", "cache_read", "cost_eq", "cost_w")


def cost_report(tag):
    """production.json llm_calls 依 (seg, fn) 分組。舊紀錄沒有 cost_w 的用 model_w 現算,不回寫。"""
    calls = (load_prod(tag) or {}).get("llm_calls") or []
    groups = {}
    for c in calls:
        g = groups.setdefault((c.get("seg") or "-", c.get("fn") or "-"), dict.fromkeys(_SUMK, 0))
        ce = c.get("cost_eq") or 0
        cw = c.get("cost_w")
        g["n"] += 1
        g["input"] += c.get("input_tokens") or 0
        g["output"] += c.get("output_tokens") or 0
        g["cache_read"] += c.get("cache_read") or 0
        g["cost_eq"] += ce
        g["cost_w"] += cw if cw is not None else ce * model_w(c.get("model"))
    order = {s: i for i, s in enumerate(SEGMENTS)}
    segs = {}
    for (seg, fn), g in groups.items():
        segs.setdefault(seg, []).append(dict(fn=fn, **g))
    rep = {"tag": tag, "segs": []}
    tot = dict.fromkeys(_SUMK, 0)
    for seg in sorted(segs, key=lambda s: order.get(s, 99)):
        rows = sorted(segs[seg], key=lambda r: -r["cost_eq"])
        sub = {k: sum(r[k] for r in rows) for k in _SUMK}
        rep["segs"].append({"seg": seg, "rows": rows, "subtotal": sub})
        for k in _SUMK:
            tot[k] += sub[k]
    rep["total"] = tot
    for r in [r for s in rep["segs"] for r in s["rows"] + [s["subtotal"]]] + [tot]:
        r["cost_eq"], r["cost_w"] = round(r["cost_eq"], 1), round(r["cost_w"], 1)
    return rep


def render_cost(rep):
    def row(a, b, r):
        return f"{a} | {b} | {r['n']} | {r['input']:,} | {r['output']:,} | {r['cache_read']:,} | {r['cost_eq']:,.0f} | {r['cost_w']:,.0f}"
    lines = [f"{rep['tag']} llm_calls 成本", "段 | fn | 次 | in | out | cache_read | cost_eq | cost_w"]
    for s in rep["segs"]:
        lines += [row(s["seg"], r["fn"], r) for r in s["rows"]]
        lines.append(row(f"{s['seg']} 小計", "-", s["subtotal"]))
    lines.append(row("合計", "-", rep["total"]))
    return "\n".join(lines)


def _default_since(tag):
    """production.json 的 created 減 1 天(ISO 日期);沒有 created 回 None。"""
    c = (load_prod(tag) or {}).get("created")
    try:
        return (datetime.fromisoformat(c) - timedelta(days=1)).date().isoformat() if c else None
    except ValueError:
        return None


def _usage_tag(tag, since=None, sessions=None):
    """本片對話用量(video_cost 逐則歸屬,含 worktree、子代理、模型加權;只讀 C 槽對話紀錄)。獨立函式方便測試 monkeypatch。
    since / sessions 為舊介面,已不使用(歸屬改逐則訊息,不再整個對話歸一片)。"""
    import video_cost as VC
    return VC.usage_for_tag(tag)


def write_session(tag, since=None, sessions=None):
    """本片對話用量寫進 production.json 頂層 session 欄位(不動其他欄位)。回傳寫入的 dict。
    main_eq/sub_eq/cost_eq 為未加權(cache_creation×1);main_w/sub_w 依模型加權;total_w = llm_calls cost_w 合計 + 對話 w。"""
    u = _usage_tag(tag, since, sessions)
    llm_w = cost_report(tag)["total"]["cost_w"]
    rec = {"at": now_iso()}
    if not u.get("sessions"):
        rec.update(sessions=[], note="找不到對話", main_w=0, sub_w=0, cost_w=0, total_w=round(llm_w, 1))
        print(f"警告:{tag} 找不到對話,session 欄位寫空", file=sys.stderr)
    else:
        with _LOCK:
            data, _ = init(tag)
        mw, sw = u.get("main_w", 0), u.get("sub_w", 0)
        rec.update(sessions=u["sessions"], turns=u["turns"], input=u["input"], cache_creation=u["cache_creation"],
                   cache_read=u["cache_read"], output=u["output"], main_eq=u["main_eq"], sub_eq=u["sub_eq"],
                   cost_eq=round(u["input"] + u["cache_creation"] + OUT_W * u["output"] + CACHE_W * u["cache_read"], 1),
                   main_w=round(mw, 1), sub_w=round(sw, 1), cost_w=round(mw + sw, 1), total_w=round(llm_w + mw + sw, 1),
                   interventions=len(data.get("interventions") or []))
    with _LOCK:
        data, _ = init(tag)
        data["session"] = rec
        _atomic_write(prod_path(tag), data)
    return rec


def conv_cost_line(tag):
    """cost 輸出最後一行:對話 w / 全片總 w(即時算 video_cost;失敗退回 production.json 的 session 欄)。"""
    try:
        import video_cost as VC
        u = VC.usage_for_tag(tag)
        cw = u["main_w"] + u["sub_w"]
        tw = cost_report(tag)["total"]["cost_w"] + cw
    except Exception:  # noqa: BLE001  量測 best-effort
        s = (load_prod(tag) or {}).get("session") or {}
        if s.get("total_w") is None:
            return "對話 w / 全片總 w:- / -(video_cost 無法讀取對話紀錄)"
        cw, tw = s.get("cost_w") or 0, s["total_w"]
    return f"對話 w / 全片總 w:{cw:,.0f} / {tw:,.0f}"


def _write_session_quiet(tag):
    try:
        write_session(tag)
    except Exception as e:  # noqa: BLE001  量測 best-effort,不改結束碼
        print(f"警告:session 用量寫入失敗:{e}", file=sys.stderr)


# ---------- 輸出 ----------

def render_table(res):
    lines = [f"{res['tag']} | 頻道 {res['channel'] or '-'} | 推斷階段 {res['stage']} | board {res['board_stage'] or '-'}",
             "段 | 推斷狀態 | 依據檔 | 缺什麼"]
    for seg in SEGMENTS:
        items = res["gates"][seg]["items"]
        have = "、".join(i["path"] for i in items if i["ok"] and i["path"]) or "-"
        miss = ";".join(i["note"] for i in items if not i["ok"]) or "-"
        lines.append(f"{SEG_NAME[seg]} | {res['gates'][seg]['state']} | {have} | {miss}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="導演層骨架:production.json 與五段狀態推斷")
    ap.add_argument("--explain", choices=RUN_SEGS, help="印該段 gate 項目")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("init", help="建 production.json(不存在才建)")
    s.add_argument("tag")
    s.add_argument("--channel")
    s = sub.add_parser("status", help="從既有產物推斷每段狀態")
    s.add_argument("tag")
    s.add_argument("--channel")
    s.add_argument("--json", action="store_true")
    s.add_argument("--write", action="store_true", help="推斷結果寫回 production.json(保留 llm_calls/interventions/feedback)")
    s = sub.add_parser("cost", help="llm_calls 依段/fn 分組的成本表")
    s.add_argument("tag")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("usage", help="對話 token 用量寫進 production.json 的 session 欄位")
    s.add_argument("tag")
    s.add_argument("--since", help="已不使用(舊介面,video_cost 逐則歸屬)")
    s.add_argument("--sessions", help="已不使用(舊介面)")
    s = sub.add_parser("log", help="追加一筆 llm_calls")
    s.add_argument("tag")
    s.add_argument("--fn", required=True)
    s.add_argument("--model", required=True)
    s.add_argument("--in", dest="tin", type=int, required=True)
    s.add_argument("--out", dest="tout", type=int, required=True)
    s.add_argument("--cache", type=int, default=0)
    s.add_argument("--cost", type=float, help="cost_eq 覆寫;預設 in+5*out+0.1*cache")
    s = sub.add_parser("intervene", help="追加一筆使用者介入")
    s.add_argument("tag")
    s.add_argument("--what", required=True)
    s = sub.add_parser("feedback", help="追加一筆使用者回饋")
    s.add_argument("tag")
    s.add_argument("--text", required=True)
    s.add_argument("--case")
    s = sub.add_parser("brief", help="寫開工資料 projects\\<tag>\\brief.json(已有就合併)")
    s.add_argument("tag")
    for k in ("--topic", "--angle", "--channel", "--format"):
        s.add_argument(k, required=True)
    for k in ("--spoiler", "--played", "--one-line", "--publish", "--event", "--query"):
        s.add_argument(k)
    s.add_argument("--url", action="append", help="同題片網址,可多次")
    s.add_argument("--allow-short", action="store_true", help="估片長低於下限也放行(使用者同意照發)")
    s.add_argument("--flow", choices=("v2", "v3"), help="流程版本:v3 = 2026-11-03 省 token 流程(新片一律加);缺 = v2 原路徑")
    s = sub.add_parser("run", help="A→E 串接:照順序跑步驟、每段後評 gate(卡點結束碼 3)")
    s.add_argument("tag")
    s.add_argument("--from", dest="from_", choices=RUN_SEGS, required=True)
    s.add_argument("--to", choices=RUN_SEGS, required=True)
    s.add_argument("--ver", help="C/D/E 段必填")
    s.add_argument("--backend", choices=("local", "kaggle", "colab"))
    s.add_argument("--title")
    s.add_argument("--channel")
    s.add_argument("--publish-at", default="auto", metavar="ISO|HH:MM|auto")
    s.add_argument("--cover")
    s.add_argument("--check-only", action="store_true", help="不跑指令,只對既有產物評各段 gate")
    s.add_argument("--dry-run", action="store_true", help="只印將跑的指令與 gate")
    s.add_argument("--max-attempts", type=int, default=3)
    a = ap.parse_args(argv)

    if a.explain:
        explain(a.explain)
    elif not a.cmd:
        ap.error("要指定子指令或 --explain")
    elif a.cmd == "init":
        data, new = init(a.tag, a.channel)
        print(f"{a.tag}: {'已建立' if new else '已存在,未動'} {prod_path(a.tag)}(頻道 {data.get('channel') or '-'})")
    elif a.cmd == "status":
        res = collect(a.tag, a.channel)
        if a.write:
            write_back(a.tag, res)
            _write_session_quiet(a.tag)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            print(render_table(res))
            if a.write:
                print(f"已寫回 {prod_path(a.tag)}")
    elif a.cmd == "cost":
        rep = cost_report(a.tag)
        print(json.dumps(rep, ensure_ascii=False, indent=1) if a.json else render_cost(rep) + "\n" + conv_cost_line(a.tag))
    elif a.cmd == "usage":
        rec = write_session(a.tag, a.since, a.sessions.split(",") if a.sessions else None)
        print(f"{a.tag}: session 已寫入 {json.dumps(rec, ensure_ascii=False)}")
    elif a.cmd == "log":
        r = log_call(a.tag, a.fn, a.model, a.tin, a.tout, a.cache, a.cost)
        print(f"{a.tag}: llm_calls +1({r['fn']} {r['model']} cost_eq {r['cost_eq']})")
    elif a.cmd == "intervene":
        intervene(a.tag, a.what)
        print(f"{a.tag}: interventions +1")
    elif a.cmd == "feedback":
        feedback(a.tag, a.text, a.case)
        print(f"{a.tag}: feedback +1")
    elif a.cmd == "brief":
        return write_brief(a)
    elif a.cmd == "run":
        return run(a.tag, a)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
