#!/usr/bin/env python3
r"""B 段預渲染檢查(PLAN_全流程優化_2026-11-05 §2 P3):不配音、不渲染、不吃 GPU 鎖,提早抓 D 段渲染前檢查會報的素材錯。

python -X utf8 pipeline\prerender_check.py <tag> [--json] [--script <script.json>] [--clips <clips.json>] [--work-tag <名>]

1. 由 <tag>\script.json 以 specs.SPEECH_CPM 估每句秒數(字數 = pace.count_chars(say 或 text);整片估秒扣掉句間/段間停頓,
   停頓同 make_version:句間 GAP、段間 SECTION_GAP,行尾 pause 取大)→ build\<work>\timeline_est.json(格式同 timeline_tts.json)。
   未計 build 的補靜音(動畫停留、鏡頭最短時長),只影響「太短」類,本檢查不收那些。
2. 子行程跑 `run.py build --check-only --timeline <est>`(參數同 make_version 的「檢查」步,不給 --bgm;檢查邏輯與門檻全在 build.py)。
   build 會照常寫 build\<work>\plan.json / luma_cache.json;--out 指到 tmp\prerender\,不建 output\<tag>\。
3. 只收「錯誤:」行並分類(classify):hl_too_big(重點區過大)、clip_tag_miss(標籤挑不到片段 / raw 不存在)、
   clip_too_long(同一影片片段 > VIDEO_MAX 秒)、image_missing(images\*.png 不存在)、cta_anim_missing(cta 標籤無片段、anim 素材名不存在);
   每筆 {kind, line, line_end, label, msg, fix};fix = "asset"(補截圖/拆兩張/多備片段)或 "line"(換標籤、改句)。
   其他錯誤(hl 找不到、同圖連續、動畫規格、字幕縫等)列 other,不算進結束碼(D 段正式檢查照擋)。
--work-tag:build 以這個 tag 跑(build\<work>\ 放產物),素材仍讀 <tag> 的 script.json 與 clips;驗收已交付的片時用,不動原片的 build\。
結束碼:有錯(五類)1、無錯 0、build 沒跑完(沒有「渲染前檢查:」摘要行)2。
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pace  # noqa: E402
import paths as P  # noqa: E402
from gates import specs  # noqa: E402

GAP, SECTION_GAP = 0.12, 0.30   # 與 make_version.build 的 --gap / --section-gap 同
TAIL = 1.0                      # build.TAIL
KINDS = ("hl_too_big", "clip_tag_miss", "clip_too_long", "image_missing", "cta_anim_missing")
CTA_TAGS = ("cta",)
_SPAN = r"句(\d+)(?:-(\d+))?: "
RULES = (   # (kind, regex, label 群組名, fix);依序比對,第一個中的算
    ("hl_too_big", re.compile(_SPAN + r"重點區過大,請拆成兩張截圖\((?P<label>[^)]+)\)"), "asset"),
    ("clip_too_long", re.compile(_SPAN + r"同一影片片段 [\d.]+ 秒 > \d+ 秒"), "line"),
    ("clip_tag_miss", re.compile(_SPAN + r"標籤「(?P<label>[^」]+)」挑不到 [\d.]+ 秒的片段[(（](?P<why>[^)）]*)[)）]"), None),
    ("clip_tag_miss", re.compile(_SPAN + r"raw/(?P<label>.+)\.mp4 不存在"), "asset"),
    ("image_missing", re.compile(_SPAN + r"images/(?P<label>.+)\.png 不存在"), "asset"),
    ("cta_anim_missing", re.compile(_SPAN + r"anim \w+ 名稱不存在: '?(?P<label>[^'(\s]+)"), "line"),
)


def est_timeline(script_path, cpm=None):
    """script.json → timeline dict(lines[{idx,text,start,end,visual_start,visual_end}], total, est=True)。"""
    data = json.loads(Path(script_path).read_text(encoding="utf-8"))
    rows = [(si, ln) for si, sec in enumerate(data["sections"]) for ln in sec["lines"]]
    if not rows:
        raise ValueError("script.json 沒有句子")
    cps = (cpm or specs.SPEECH_CPM) / 60.0
    base = [max(pace.count_chars(ln.get("say") or ln.get("text") or ""), 1) / cps for _, ln in rows]
    gaps = []
    for i, (si, ln) in enumerate(rows):
        if i + 1 == len(rows):
            gaps.append(0.0)
            continue
        g = SECTION_GAP if rows[i + 1][0] != si else GAP
        gaps.append(max(g, float(ln.get("pause") or 0.0)))
    # SPEECH_CPM 是整段(含停頓)的字/分:唸字秒數按比例扣掉停頓,總長才對得上
    k = max(0.5, (sum(base) - sum(gaps)) / sum(base))
    out, t = [], 0.0
    for i, (_, ln) in enumerate(rows):
        d = base[i] * k
        out.append(dict(idx=i + 1, text=ln["text"], start=round(t, 3), end=round(t + d, 3)))
        t += d + gaps[i]
    total = out[-1]["end"] + TAIL
    for i, row in enumerate(out):
        row["visual_start"] = row["start"]
        row["visual_end"] = out[i + 1]["start"] if i + 1 < len(out) else round(total, 3)
    return dict(fps=30, total=round(total, 3), est=True, cpm=cpm or specs.SPEECH_CPM, lines=out)


def classify(msg):
    """一則 build「錯誤:」訊息 → {kind, line, line_end, label, msg, fix};不屬五類回 None。"""
    for kind, rx, fix in RULES:
        m = rx.search(msg)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        gd = m.groupdict()
        label = gd.get("label")
        if kind == "clip_tag_miss" and "why" in gd:
            if label in CTA_TAGS:
                kind, fix = "cta_anim_missing", "asset"
            else:   # clips 根本沒有這個標籤 → 句子換標籤;有但不夠 → 多備片段
                fix = "line" if gd["why"] == "clips 沒有這個標籤" else "asset"
        return dict(kind=kind, line=a, line_end=b, label=label, msg=msg, fix=fix)
    return None


def parse(text):
    """build 輸出 → (errors 五類, other 其他錯誤訊息, 有沒有摘要行)。"""
    errors, other, done = [], [], False
    for raw in (text or "").splitlines():
        s = raw.strip()
        if s.startswith("渲染前檢查:"):
            done = True
        if not s.startswith("錯誤:"):
            continue
        msg = s[len("錯誤:"):].strip()
        c = classify(msg)
        if c:
            errors.append(c)
        else:
            other.append(msg)
    return errors, other, done


def _run(cmd):
    r = subprocess.run(cmd, cwd=str(P.REPO), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def build_cmd(tag, script, timeline, clips, work):
    out = P.TMP / "prerender" / f"{work}.mp4"
    return [sys.executable, "-X", "utf8", str(P.REPO / "pipeline" / "run.py"), "build", "--script", str(script),
            "--voice", "M", "--tts-engine", "cosy3", "--tag", work, *(["--clips", str(clips)] if clips else []),
            "--max-per-src", "120", "--gap", str(GAP), "--section-gap", str(SECTION_GAP), "--anim-bg", "star",
            "--check-only", "--timeline", str(timeline), "--out", str(out)]


def check(tag, script=None, clips=None, work_tag=None, runner=None):
    """估 timeline → build --check-only → 分類。回 {errors, other, rc, done, timeline, tail};runner 測試注入(cmd → (rc, text))。"""
    work = work_tag or tag
    script = Path(script) if script else P.REPO / tag / "script.json"
    if clips is None:
        cf = P.clips_file(tag)
        clips = cf if cf.exists() else None
    bdir = P.build_dir(work)
    bdir.mkdir(parents=True, exist_ok=True)
    tl = bdir / "timeline_est.json"
    tl.write_text(json.dumps(est_timeline(script), ensure_ascii=False, indent=1), encoding="utf-8")
    if work != tag:   # 驗收用工作 tag:亮度快取從原片唯讀複製一份,省掉重新探測
        src, dst = P.build_dir(tag) / "luma_cache.json", bdir / "luma_cache.json"
        if src.exists() and not dst.exists():
            shutil.copyfile(src, dst)
    (P.TMP / "prerender").mkdir(parents=True, exist_ok=True)
    rc, text = (runner or _run)(build_cmd(tag, script, tl, clips, work))
    errors, other, done = parse(text)
    tail = [l for l in text.splitlines() if l.strip()][-5:]
    return dict(errors=errors, other=other, rc=rc, done=done, timeline=str(tl), tail=tail)


def exit_code(res):
    if not res["done"]:
        return 2
    return 1 if res["errors"] else 0


def summary(res, limit=5):
    """一行摘要(director Block 訊息用):各類筆數 + 前幾筆。"""
    if not res["done"]:
        return "build 檢查沒跑完:" + " | ".join(res["tail"][-2:])
    cnt = {}
    for e in res["errors"]:
        cnt[e["kind"]] = cnt.get(e["kind"], 0) + 1
    head = "、".join(f"{k} {n}" for k, n in cnt.items()) or "0"
    return f"預渲染錯誤 {head}:" + " | ".join(e["msg"] for e in res["errors"][:limit])


def main():
    ap = argparse.ArgumentParser(description="B 段預渲染檢查(估秒 timeline + build --check-only,只收五類素材錯)")
    ap.add_argument("tag")
    ap.add_argument("--json", action="store_true", help="結果印成 JSON")
    ap.add_argument("--script", help="script.json(預設 <tag>\\script.json)")
    ap.add_argument("--clips", help="clips json(預設 projects\\<tag>\\clips_<tag>.json,沒有就不給)")
    ap.add_argument("--work-tag", help="build 以此 tag 跑(產物在 build\\<work>\\),不動原片 build\\")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    res = check(a.tag, a.script, a.clips, a.work_tag)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        for e in res["errors"]:
            span = f"句{e['line']}" + (f"-{e['line_end']}" if e["line_end"] != e["line"] else "")
            print(f"[{e['kind']}] {span} {e['label'] or ''} → {e['fix']}:{e['msg']}")
        print(f"其他錯誤(不計){len(res['other'])} 條" if res["other"] else "其他錯誤 0")
        print(summary(res) if res["errors"] or not res["done"] else f"預渲染檢查:五類錯誤 0(timeline {res['timeline']})")
    sys.exit(exit_code(res))


if __name__ == "__main__":
    main()
