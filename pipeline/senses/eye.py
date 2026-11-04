"""眼睛 eye.py:D 段成片後的機械檢查(0 token,只用 ffmpeg/ffprobe + 標準函式庫)。
用法:python -X utf8 pipeline\\senses\\eye.py --tag <tag> --ver <ver> [--json]
輸出 projects\\<tag>\\eye_<ver>.json {ok, items:[{id, ok, note, at}], mp4, at};任一項不 ok 結束碼 1。
六項:black / freeze / lufs / sync / tail / chapters,規格見 pipeline\\docs\\senses.md「眼睛 eye.py 機械項」。"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402

# 門檻(pipeline 內找不到 loudnorm/LUFS/ebur128 常數,故用 -14 ±1.5)
# LUFS 目標 = 2026-10-31 實測最近 6 支已交付成片(ea_me5 v1、wow_return v2、ally_ai v1、bioware_dei v4、fog_still v1、
# horror_sound v1)integrated LUFS 的中位數:-18.9 -19.0 -19.3 -19.0 -19.1 -19.2 -> -19.05;±1.5 為帶
LUFS_TARGET, LUFS_TOL = -19.05, 1.5
LUFS_SRC = "近 6 支成片中位數,見 senses.md"
BLACK_HEAD, BLACK_TAIL, BLACK_MIN = 1.0, 2.0, 0.5
FREEZE_MIN = 10.0
SILENCE_ARGS = "n=-35dB:d=0.25"
SYNC_TOL, SYNC_RATIO = 0.3, 0.95
TAIL_TOL = 3.0
CHAPTER_TOL = 2.0


# ---------- ffmpeg 呼叫與 stderr 解析 ----------
def run_ff(args, timeout=1800):
    """回傳 (returncode, stderr);執行失敗(找不到 ffmpeg、逾時)也回傳而不拋例外。"""
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, r.stderr or ""
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {e}"


def probe_duration(mp4):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                            str(mp4)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return float(r.stdout.strip())
    except Exception:  # noqa: BLE001
        return None


def parse_blackdetect(text):
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+)\s+black_end:([\d.]+)", text)]


def parse_freezedetect(text, total=None):
    """[(start, duration)];檔尾仍凍結而沒有 duration 時用 total - start。"""
    out, start = [], None
    for m in re.finditer(r"freeze_(start|duration):\s*([\d.]+)", text):
        if m.group(1) == "start":
            if start is not None and total:
                out.append((start, max(0.0, total - start)))
            start = float(m.group(2))
        elif start is not None:
            out.append((start, float(m.group(2))))
            start = None
    if start is not None and total:
        out.append((start, max(0.0, total - start)))
    return out


def parse_silencedetect(text):
    """[(silence_start, silence_end|None)]"""
    out, cur = [], None
    for m in re.finditer(r"silence_(start|end):\s*(-?[\d.]+)", text):
        v = float(m.group(2))
        if m.group(1) == "start":
            cur = v
        elif cur is not None:
            out.append((cur, v))
            cur = None
        else:
            out.append((0.0, v))
    if cur is not None:
        out.append((cur, None))
    return out


def speech_starts(silences, total):
    """非靜音段起點:0(若開頭不是靜音)+ 每段靜音結束點。"""
    st = []
    if not silences or silences[0][0] > 0.05:
        st.append(0.0)
    for _, e in silences:
        if e is not None and (total is None or e < total - 0.05):
            st.append(e)
    return st


def parse_ebur128(text):
    """Summary 區塊的 integrated loudness(LUFS);找不到回 None。"""
    i = text.rfind("Summary:")
    m = re.search(r"\bI:\s*(-?[\d.]+)\s*LUFS", text[i:] if i >= 0 else text)
    return float(m.group(1)) if m else None


# ---------- 各項檢查 ----------
def _tail200(s):
    return s.strip()[-200:]


def check_black(mp4, dur):
    rc, err = run_ff(["-i", str(mp4), "-an", "-vf", "blackdetect=d=0.5:pic_th=0.98", "-f", "null", "-"])
    if rc != 0:
        return False, f"ffmpeg 失敗:{_tail200(err)}"
    lo, hi = BLACK_HEAD, (dur - BLACK_TAIL if dur else float("inf"))
    bad = []
    for s, e in parse_blackdetect(err):
        s2, e2 = max(s, lo), min(e, hi)
        if e2 - s2 >= BLACK_MIN:
            bad.append((s2, e2))
    if bad:
        return False, f"{len(bad)} 段黑場:" + "、".join(f"{s:.1f}-{e:.1f}s" for s, e in bad[:5])
    return True, "0 段黑場(片頭 1s、片尾 2s 內不算)"


def check_freeze(mp4, dur):
    rc, err = run_ff(["-i", str(mp4), "-an", "-vf", f"freezedetect=n=-60dB:d={FREEZE_MIN:g}", "-f", "null", "-"])
    if rc != 0:
        return False, f"ffmpeg 失敗:{_tail200(err)}"
    segs = [(s, d) for s, d in parse_freezedetect(err, dur) if d >= FREEZE_MIN]
    if segs:
        return False, f"{len(segs)} 段靜止 >{FREEZE_MIN:g}s:" + "、".join(f"{s:.1f}s 起 {d:.1f}s" for s, d in segs[:5])
    return True, f"0 段靜止 >{FREEZE_MIN:g}s"


def check_lufs(mp4):
    rc, err = run_ff(["-i", str(mp4), "-vn", "-af", "ebur128", "-f", "null", "-"])
    if rc != 0:
        return False, f"ffmpeg 失敗:{_tail200(err)}"
    v = parse_ebur128(err)
    if v is None:
        return False, f"解析不到 integrated LUFS:{_tail200(err)}"
    ok = abs(v - LUFS_TARGET) <= LUFS_TOL
    return ok, f"{v:.1f} LUFS(目標 {LUFS_TARGET:g}±{LUFS_TOL:g};{LUFS_SRC})"


def load_timeline(tag):
    for n in ("timeline_tts.json", "timeline.json"):
        f = paths.build_dir(tag) / n
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8")), n
    return None, None


def check_sync(mp4, dur, tl, voice=None):
    lines = [ln for ln in (tl or {}).get("lines", []) if "start" in ln]
    if not lines:
        return False, "timeline 沒有 lines"
    use_voice = bool(voice and Path(voice).exists())
    src = str(voice) if use_voice else str(mp4)
    rc, err = run_ff(["-i", src, "-vn", "-af", f"silencedetect={SILENCE_ARGS}", "-f", "null", "-"])
    if rc != 0:
        return False, f"ffmpeg 失敗:{_tail200(err)}"
    starts = speech_starts(parse_silencedetect(err), dur)
    if not starts:
        return False, "成片偵測不到語音段"
    vad_note = "(純人聲軌 voice.wav)" if use_voice else "(混音,結果僅供參考)"
    if len(starts) < len(lines) / 3:
        vad_note += f"(語音段僅 {len(starts)} 個、少於句數 1/3:成片混 BGM 時 silencedetect 絕對門檻偵測不到停頓,此項 VAD 可能無效)"
    offs = [min((s - ln["start"] for s in starts), key=abs) for ln in lines]
    good = sum(1 for o in offs if abs(o) <= SYNC_TOL)
    ratio = good / len(offs)
    worst = sorted(zip(offs, (ln["idx"] for ln in lines)), key=lambda x: -abs(x[0]))[:3]
    note = f"{good}/{len(offs)} 句偏移 ≤{SYNC_TOL}s({ratio:.0%},門檻 {SYNC_RATIO:.0%});最大偏移 " + \
        "、".join(f"句{i} {o:+.2f}s" for o, i in worst) + vad_note
    return ratio >= SYNC_RATIO, note


def check_tail(dur, tl):
    lines = (tl or {}).get("lines", [])
    if dur is None or not lines:
        return False, "缺成片長度或 timeline lines"
    exp = tl.get("total") or lines[-1]["end"]
    src = "timeline.total" if tl.get("total") else "最後一句 end"
    d = dur - exp
    return abs(d) <= TAIL_TOL, f"成片 {dur:.1f}s vs {src} {exp:.1f}s,差 {d:+.1f}s(門檻 ±{TAIL_TOL:g}s)"


def parse_chapters(md):
    """說明檔「【YouTube章節摘要】」到下一個【…】之間的 mm:ss(或 h:mm:ss)行 → [(秒, 標題)]。"""
    i = md.find("【YouTube章節摘要】")
    if i < 0:
        return []
    out = []
    for ln in md[i + len("【YouTube章節摘要】"):].splitlines():
        s = ln.strip()
        if s.startswith("【"):
            break
        m = re.match(r"^(?:(\d+):)?(\d{1,2}):(\d{2})\s+(.+)$", s)
        if m:
            out.append((int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3)), m.group(4)))
    return out


def check_chapters(tag, ver, tl):
    f = paths.output_dir(tag) / f"{ver}_說明.md"
    if not f.exists():
        return True, f"略過:沒有說明檔 {f.name}"
    chs = parse_chapters(f.read_text(encoding="utf-8", errors="replace"))
    if not chs:
        return True, "略過:說明檔沒有章節行"
    starts = [ln["start"] for ln in (tl or {}).get("lines", []) if "start" in ln]
    if not starts:
        return False, "timeline 沒有 lines"
    bad = []
    for t, title in chs:
        d = min((t - s for s in starts), key=abs)
        if abs(d) > CHAPTER_TOL:
            bad.append(f"{t // 60:02d}:{t % 60:02d} {title[:10]} 差 {d:+.1f}s")
    if bad:
        return False, f"{len(bad)}/{len(chs)} 章對不上句首(>{CHAPTER_TOL:g}s):" + "、".join(bad[:4])
    return True, f"{len(chs)} 章皆對上句首(±{CHAPTER_TOL:g}s)"


# ---------- 主流程 ----------
def run(tag, ver):
    mp4 = paths.output_dir(tag) / f"{tag}_{ver}.mp4"

    def now():
        return time.strftime("%Y-%m-%d %H:%M:%S")

    items = []

    def add(i, res):
        items.append({"id": i, "ok": bool(res[0]), "note": res[1], "at": now()})

    if not mp4.exists():
        add("mp4", (False, f"找不到成片 {mp4}"))
        return {"ok": False, "items": items, "mp4": str(mp4), "at": now()}
    dur = probe_duration(mp4)
    tl, _ = load_timeline(tag)
    no_tl = (False, f"找不到 {paths.build_dir(tag)}\\timeline_tts.json")
    add("black", check_black(mp4, dur))
    add("freeze", check_freeze(mp4, dur))
    add("lufs", check_lufs(mp4))
    add("sync", check_sync(mp4, dur, tl, paths.build_dir(tag) / "voice.wav") if tl else no_tl)
    add("tail", check_tail(dur, tl) if tl else no_tl)
    add("chapters", check_chapters(tag, ver, tl) if tl else no_tl)
    return {"ok": all(i["ok"] for i in items), "items": items, "mp4": str(mp4), "at": now()}


def main(argv=None):
    ap = argparse.ArgumentParser(description="成片機械檢查(眼睛)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ver", required=True)
    ap.add_argument("--json", action="store_true", help="另外把完整 JSON 印到 stdout")
    a = ap.parse_args(argv)
    res = run(a.tag, a.ver)
    out = paths.PROJECTS / a.tag / f"eye_{a.ver}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        for i in res["items"]:
            print(f"{'ok  ' if i['ok'] else 'FAIL'} {i['id']:<9} {i['note']}")
        print(f"eye {a.tag} {a.ver}: {'ok' if res['ok'] else '有項目不 ok'} -> {out}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
