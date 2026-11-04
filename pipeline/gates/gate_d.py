r"""段 D gate(畫面)。規格:pipeline\docs\director.md「run:C→E 串接」。"""
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import director as D  # noqa: E402
import paths as P  # noqa: E402
from gates import specs  # noqa: E402

IDS = ("成片mp4", "片長", "渲染前檢查", "qa圖", "look清單", "eye")


def status(tag, ctx):
    """director status 用(原 director.check_d,行為不變)。"""
    mp = D.mp4_list(tag)
    look = D._first(sorted(D._glob(P.output_dir(tag), "look_v*.md"), key=D._ver_no, reverse=True))
    return [D._item("成片mp4", mp, f"output\\<tag>\\{tag}_v*.mp4 沒有", mp[-1] if mp else None),
            D._item("look清單", look, "look_v*.md 沒有", look)]


def probe_secs(p):
    """ffprobe 時長(秒);找不到 ffprobe 回 None,讀不到回 0。"""
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip() or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def precheck_errors(log):
    """make_<ver>.log 最後一行「渲染前檢查:… 錯誤 N」的 N;沒有這行回 None。"""
    n = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"渲染前檢查:.*錯誤\s*(\d+)", line)
        if m:
            n = int(m.group(1))
    return n


def run(tag, ver, ctx=None):
    """硬擋:mp4 有且 ≥ specs 片型下限(下限到目標下緣之間過但註明;不設下限的片型不限);渲染前檢查 錯誤 0;qa 圖;look 清單;eye_<ver>.json 全 ok。"""
    channel = (ctx or {}).get("channel") or ""
    sp = specs.spec(channel, (D._read_json(P.PROJECTS / tag / "brief.json") or {}).get("format"))
    out_d = P.output_dir(tag)
    mp = out_d / f"{tag}_{ver}.mp4"
    out = [D._item("成片mp4", mp.exists(), f"{tag}_{ver}.mp4 沒有", mp)]
    if sp["floor"] is None:
        out.append(D._item("片長", True, f"{channel} 不限片長"))
    elif not mp.exists():
        out.append(D._item("片長", False, "沒有 mp4,無法量片長"))
    else:
        secs = probe_secs(mp)
        if secs is None:
            out.append(D._item("片長", False, "找不到 ffprobe(環境問題),無法量片長"))
        else:
            m = secs / 60
            note = (f"片長 {m:.1f} 分 <{sp['floor']},需使用者決定補素材/併題/照發" if m < sp["floor"]
                    else f"片長 {m:.1f} 分,低於目標 {sp['target'][0]} 分" if m < sp["target"][0] else f"片長 {m:.1f} 分")
            brief = D._read_json(P.PROJECTS / tag / "brief.json") or {}
            short_ok = m < sp["floor"] and brief.get("allow_short")
            out.append(D._item("片長", m >= sp["floor"] or bool(short_ok), note + (",brief.allow_short 放行" if short_ok else ""), mp))
    log = out_d / f"make_{ver}.log"
    if not log.exists():
        out.append(D._item("渲染前檢查", False, f"make_{ver}.log 沒有"))
    else:
        n = precheck_errors(log)
        note = f"make_{ver}.log 沒有渲染前檢查紀錄" if n is None else f"渲染前檢查 錯誤 {n}"
        out.append(D._item("渲染前檢查", n == 0, note, log))
    qa = D._first(D._glob(out_d, f"qa_{ver}*.png"))
    out.append(D._item("qa圖", qa, f"qa_{ver}*.png 沒有", qa))
    look = out_d / f"look_{ver}.md"
    out.append(D._item("look清單", look.exists(), f"look_{ver}.md 沒有", look))
    ej = P.PROJECTS / tag / f"eye_{ver}.json"
    d = D._read_json(ej)
    if d is None:
        out.append(D._item("eye", False, f"eye_{ver}.json 沒有"))
    else:
        bad = [str(i.get("id", "?")) for i in d.get("items") or [] if not i.get("ok")]
        ok = d.get("ok") is True and not bad
        out.append(D._item("eye", ok, "eye 全 ok" if ok else f"eye 不過:{'、'.join(bad) or 'ok=false'}", ej))
    return out
