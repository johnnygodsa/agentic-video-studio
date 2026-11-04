#!/usr/bin/env python3
r"""Shorts 一個指令出片(F2-3b;規格 projects/framework/shorts_spec.md §6、channel/_archive/plans/PLAN_FRAMEWORK.md §2.4/§2.7)。
python -X utf8 pipeline/shorts_build.py --tag <母片> --id s1 --ver v1 [--lines a-b] [--hook 文字] [--len 25-45]
    [--cx 句號=0.3,…] [--bgm 檔名] [--voice M|F] [--force] [--dry-run]
  句子來源優先序:<tag>\shorts_<id>.txt(存在就用;--cx 句號 = Short 內第幾句)> --lines > projects\<tag>\spec.json 的 shorts[id].lines
    (後兩者 --cx 句號 = 母片句號,同 spec 句號定義 README §11)。hook/len_s/cx 同樣是 CLI > spec(spec 欄位 hook_text、len_s、cx {句號: 0-1})。
  工作 tag <tag>_<id>:script.json 放 build\<tag>_<id>\(圖片句一律 fx none、寫入 cx;不帶 spoiler;保留母片 fallback 等頂層欄位)。
  配音:母片 build\<tag>\tts\ 依文字對到的句子把快取檔複製成新句號(sub\ 子句快取以音檔鍵命名,整個複製),全部對到就 --no-synth;
    有新句(或快取沒命中)才排隊拿全機 GPU 鎖(gpu_lock.py,含 nvidia-smi <= 3000 MiB)並合成。
  參數跟母片一致:讀 output\<tag>\make_*.log 最新一份的 build 指令(聲音、語速、句間、BGM、音量、動畫底、--voice-eq)與 txt2json 的 --img-prefix;
    --voice / --bgm 可覆寫。clips 用 projects\<tag>\clips_<tag>.json。
  步驟:txt2json -> 配音 -> 渲染前檢查(--check-only,錯誤 > 0 停,--force 照渲)-> 渲染(--portrait)-> QA 總覽(每 3 秒一格)-> 說明檔骨架。
  輸出:output\<tag>\<tag>_<id>_<ver>.mp4、qa_<id>_<ver>.png、<id>_<ver>_說明.md(已存在不覆寫);完整 log output\<tag>\make_<id>_<ver>.log。
  交付:deliver.py --tag <tag> --ver <id>_<ver> --title <片名> --shorts。
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import gpu_lock as GL
import make_version as MV
import paths as P

PY, RUN = MV.PY, MV.RUN
LONG_LINK = "長片連結:(長片發布後填)"
# 從母片 build 指令沿用的選項(其餘由本程式決定)
INHERIT = ("--voice", "--rate", "--gap", "--section-gap", "--tts-engine", "--spk", "--max-per-src", "--bed",
           "--anim-bg", "--bgm", "--bgm-vol", "--voice-eq")
DEFAULTS = {"--voice": "seed402", "--rate": "+18%", "--gap": "0.12", "--section-gap": "0.30", "--tts-engine": "chattts",
            "--spk": "M_seed_402.pt", "--max-per-src": "120", "--anim-bg": "star", "--bgm": f"bgm/{MV.DEFAULT_BGM}",
            "--bgm-vol": "0.25"}
RENDER_ONLY = ("--anim-bg", "--bgm", "--bgm-vol", "--voice-eq", "--bed")


def parent_make(tag):
    """最新一份 make_*.log(不含 Shorts 自己的 make_s*_*.log)-> (build 選項 dict, img 前綴, log 路徑)。"""
    logs = [p for p in P.output_dir(tag).glob("make_*.log") if not re.match(r"make_s\d+_", p.name)]
    if not logs:
        return dict(DEFAULTS), None, None
    logp = max(logs, key=lambda p: p.stat().st_mtime)
    opts, prefix = dict(DEFAULTS), None
    for ln in logp.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.startswith("$ "):
            continue
        tok = ln[2:].split()
        if "script_txt2json" in tok and "--img-prefix" in tok:
            prefix = tok[tok.index("--img-prefix") + 1]
        if "build" in tok and "--tts-only" not in tok and "--check-only" not in tok:
            found = {}
            for i, t in enumerate(tok[:-1]):
                if t in INHERIT and not tok[i + 1].startswith("--"):
                    found[t] = tok[i + 1]
            opts = {**DEFAULTS, **found}
    return opts, prefix, logp


def txt2json(src, dst, prefix, log):
    cmd = [PY, RUN, "script_txt2json", str(src), str(dst)] + (["--img-prefix", prefix] if prefix else [])
    rc, out = MV.run_cmd(cmd, log)
    if rc:
        sys.exit(f"txt2json 失敗({src}):\n" + "\n".join(out[-8:]))
    return json.loads(Path(dst).read_text(encoding="utf-8"))


def flat(data):
    """[(段名, 句)],依 spec 句號順序(sections[].lines 攤平)。"""
    return [(s.get("name", ""), l) for s in data["sections"] for l in s["lines"]]


def parse_range(s):
    a, _, b = str(s).partition("-")
    return int(a), int(b or a)


def parse_cx(s):
    out = {}
    for part in filter(None, (x.strip() for x in (s or "").split(","))):
        k, _, v = part.partition("=")
        out[int(k)] = float(v)
    return out


def say_of(l):
    return l.get("say") or l["text"]


def copy_tts(pairs, ptts, wtts):
    """pairs = [(新句號, 母片句號)]:把母片 NNN.* 快取複製成新句號;sub\\ 整個複製(檔名是音檔鍵,與句號無關)。回傳複製句數。"""
    wtts.mkdir(parents=True, exist_ok=True)
    n = 0
    for new, old in pairs:
        files = list(ptts.glob(f"{old:03d}.*"))
        for f in files:
            shutil.copy2(f, wtts / (f"{new:03d}" + f.name[3:]))
        n += bool(files)
    if (ptts / "sub").is_dir():
        shutil.copytree(ptts / "sub", wtts / "sub", dirs_exist_ok=True)
    return n


def check_counts(out):
    m = next((re.search(r"警告 (\d+) \| 錯誤 (\d+)", l) for l in reversed(out) if l.startswith("渲染前檢查: 鏡頭")), None)
    shots = next((re.search(r"鏡頭 (\d+) 個", l) for l in reversed(out) if l.startswith("渲染前檢查: 鏡頭")), None)
    warns = [l[3:].strip() for l in out if l.startswith("警告:")]
    errs = [l[3:].strip() for l in out if l.startswith("錯誤:")]
    return (int(shots.group(1)) if shots else None, int(m.group(1)) if m else len(warns),
            int(m.group(2)) if m else len(errs), warns, errs)


def probe_wh(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return r.stdout.strip()


def notes_skeleton(path, tag, sid, ver, rng_desc, hook, dur, warns, parent_notes):
    """說明檔骨架(deliver 能解析的格式);署名區塊沿用母片說明檔的,第一行是長片連結。已存在不覆寫。"""
    if path.exists():
        return False
    sig = ""
    if parent_notes and parent_notes.exists():
        import deliver as D
        sig = D._section_block(parent_notes.read_text(encoding="utf-8"), "說明欄署名") or ""
    lines = [f"# {tag}_{sid} {ver} 說明(Shorts)", "",
             f"- 句子來源:{rng_desc};鉤子:{hook or '(無)'};總長 {dur:.1f} 秒;配音未聽審",
             "- 已知問題:" + ("無" if not warns else ""), *[f"  - {w}" for w in warns], "",
             "## 說明欄署名", "```text", LONG_LINK, *([sig] if sig else []), "```", "",
             "## 發片資料", "```text", "【YouTube章節摘要】", "(Shorts 無章節;標題、說明待填)", "【輸出完畢】", "```", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="母片 tag")
    ap.add_argument("--id", required=True, help="Shorts id,例如 s1")
    ap.add_argument("--ver", required=True)
    ap.add_argument("--lines", help="母片句號 a-b(沒有 shorts_<id>.txt 時用;優先於 spec)")
    ap.add_argument("--hook", help="鉤子字(<= 10 字);優先於 spec 的 hook_text")
    ap.add_argument("--len", help="總長檢查秒數 a-b;優先於 spec 的 len_s(預設 25-45)")
    ap.add_argument("--cx", help="影片取景中心 句號=0-1,逗號分隔;優先於 spec 的 cx")
    ap.add_argument("--bgm", help="bgm 資料夾內的檔名(預設沿用母片)")
    ap.add_argument("--voice", choices=("M", "F"), help="預設沿用母片")
    ap.add_argument("--force", action="store_true", help="渲染前檢查有錯誤仍渲染")
    ap.add_argument("--dry-run", action="store_true", help="只產 script.json 並印出各步指令")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")

    tag, sid, ver = a.tag, a.id, a.ver
    work = f"{tag}_{sid}"
    odir, wdir, pdir = P.output_dir(tag), P.build_dir(work), P.build_dir(tag)
    odir.mkdir(parents=True, exist_ok=True)
    wdir.mkdir(parents=True, exist_ok=True)
    spec_f = P.PROJECTS / tag / "spec.json"
    sspec = {}
    if spec_f.exists():
        sspec = next((x for x in json.loads(spec_f.read_text(encoding="utf-8")).get("shorts", []) if x.get("id") == sid), {})
    opts, prefix, plog = parent_make(tag)
    if a.voice:
        voice, spk = MV.VOICES[a.voice]
        opts.update({"--voice": voice, "--spk": spk})
        opts.pop("--voice-eq", None)
        if a.voice == "F":
            opts["--voice-eq"] = "soft"
    if a.bgm:
        opts["--bgm"] = f"bgm/{a.bgm}"
    if not (P.ROOT / opts["--bgm"]).exists():
        sys.exit(f"找不到 BGM: {opts['--bgm']}")
    hook = (a.hook if a.hook is not None else sspec.get("hook_text", "")).strip()
    ls = a.len or ("-".join(str(x) for x in sspec["len_s"]) if sspec.get("len_s") else "25-45")
    cx = parse_cx(a.cx) if a.cx else {int(k): float(v) for k, v in (sspec.get("cx") or {}).items()}

    logp = odir / f"make_{sid}_{ver}.log"
    t_all = time.time()
    msgs = []
    with open(logp, "w", encoding="utf-8") as log:
        # ---- 句子
        stxt = P.ROOT / tag / f"shorts_{sid}.txt"
        parent = txt2json(P.ROOT / tag / "script.txt", wdir / "parent_script.json", prefix, log)
        pflat = flat(parent)
        if stxt.exists():
            src = txt2json(stxt, wdir / "shorts_src.json", prefix, log)
            sel = [(k + 1, sec, l) for k, (sec, l) in enumerate(flat(src))]
            rng_desc = f"{stxt.name}({len(sel)} 句)"
        else:
            rng = a.lines or ("-".join(str(x) for x in sspec["lines"]) if sspec.get("lines") else None)
            if not rng:
                sys.exit(f"沒有 {stxt.name}、沒給 --lines,spec 也沒有 shorts[{sid}].lines")
            lo, hi = parse_range(rng)
            if not (1 <= lo <= hi <= len(pflat)):
                sys.exit(f"句號 {lo}-{hi} 越界(母片 {len(pflat)} 句)")
            sel = [(n, *pflat[n - 1]) for n in range(lo, hi + 1)]
            rng_desc = f"母片句 {lo}-{hi}"
        if parent.get("spoiler"):
            msgs.append("警告: 母片有 spoiler,Shorts 不帶劇透牌")
        data = {k: v for k, v in parent.items() if k not in ("sections", "spoiler")}
        data["title"] = f"{parent.get('title', tag)} {sid}"
        data["sections"], pairs, new_says = [], [], []
        by_say = {}
        for n, (_, l) in enumerate(pflat, 1):
            by_say.setdefault(say_of(l), n)
        for k, (num, sec, l) in enumerate(sel, 1):
            l = json.loads(json.dumps(l))
            if l.get("img") or l.get("v") == "img":
                l["fx"] = "none"
            if num in cx:
                l["cx"] = cx[num]
            if not data["sections"] or data["sections"][-1]["name"] != sec:
                data["sections"].append({"name": sec, "lines": []})
            data["sections"][-1]["lines"].append(l)
            pn = by_say.get(say_of(l))
            if pn:
                pairs.append((k, pn))
            else:
                new_says.append(k)
        script = wdir / "script.json"
        script.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        copied = copy_tts(pairs, pdir / "tts", wdir / "tts")

        out_rel = f"output/{tag}/{tag}_{sid}_{ver}.mp4"
        video = P.ROOT / out_rel
        tl_tts, tl = wdir / "timeline_tts.json", wdir / "timeline.json"
        render_opts = [x for o in RENDER_ONLY if o in opts for x in (o, opts[o])]
        base = [PY, RUN, "build", "--script", str(script), "--tag", work, "--clips", str(P.clips_file(tag)), "--portrait",
                "--len", ls] + [x for o in INHERIT if o in opts and o not in RENDER_ONLY for x in (o, opts[o])]
        base += ["--hook", hook] if hook else []
        tts_cmd = base + ["--frozen", tag, "--tts-only", "--out", out_rel]   # 母片已凍結(freeze.json)時禁新合成(build 內判斷)
        check_cmd = base + ["--check-only", "--timeline", str(tl_tts), "--out", out_rel] + render_opts
        render_cmd = base + ["--no-synth"] + render_opts + (["--force"] if a.force else []) + ["--out", out_rel]
        print(f"{work} {ver} | {rng_desc} | 鉤子「{hook}」| 長度 {ls} 秒 | 參數來源 {plog.name if plog else '預設'}")
        print(f"配音快取: 依文字沿用 {copied}/{len(sel)} 句,新句 {len(new_says)}" + (f"(句 {new_says[:10]})" if new_says else ""))
        if a.dry_run:
            for name, c in (("配音", tts_cmd), ("檢查", check_cmd), ("渲染", render_cmd)):
                print(f"[dry-run] {name}: " + " ".join(str(x) for x in c))
            return

        # ---- 配音
        t0 = time.time()
        if new_says and MV.FZ.load(tag):   # 母片已凍結:新句等於要新合成,不排 GPU 鎖直接擋下(其餘情形 build --frozen 會擋)
            sys.exit(f"凍結後禁止新合成:母片 {tag} 已凍結,Shorts 有 {len(new_says)} 句在母片配音快取找不到(句 {new_says[:10]}),已中止。"
                     f"確需新配音:先取得使用者同意,再 `python -X utf8 pipeline\\freeze.py {tag} --refreeze --reason \"<使用者同意的理由>\"`,並重走 make_version --tts-review")
        rc, out = (1, []) if new_says else MV.run_cmd(tts_cmd[:-2] + ["--no-synth"] + tts_cmd[-2:], log)
        synth = bool(rc)
        if rc:
            with GL.gpu_lock(work, "shorts_build配音"):  # 只包合成段
                rc, out = MV.run_cmd(tts_cmd, log)
            if rc:
                sys.exit("配音失敗:\n" + "\n".join(out[-10:]) + f"\n完整 log {logp}")
        tts_line = next((l.strip() for l in out if l.startswith("TTS 快取[")), "")
        print(f"[1/4] 配音 OK {time.time() - t0:.0f}s | {'有合成' if synth else '全部沿用快取(--no-synth)'} | {tts_line[-60:]}")

        # ---- 渲染前檢查
        t0 = time.time()
        rc, out = MV.run_cmd(check_cmd, log)
        nshot, nw, ne, warns, errs = check_counts(out)
        warns = [m[3:].strip() for m in msgs] + warns
        print(f"[2/4] 檢查 {'OK' if not rc else '有錯誤'} {time.time() - t0:.0f}s | 鏡頭 {nshot} | 警告 {nw + len(msgs)} | 錯誤 {ne}")
        for w in warns[:6]:
            print(f"    警告: {w[:110]}")
        for e in errs[:6]:
            print(f"    錯誤: {e[:110]}")
        if rc and not a.force:
            sys.exit(f"渲染前檢查有錯誤,未渲染(--force 照渲);完整 log {logp}")

        # ---- 渲染
        t0 = time.time()
        rc, out = MV.run_cmd(render_cmd, log)
        if rc:
            sys.exit("渲染失敗:\n" + "\n".join(out[-10:]) + f"\n完整 log {logp}")
        dur, wh = MV.probe_duration(video), probe_wh(video)
        print(f"[3/4] 渲染 OK {time.time() - t0:.0f}s | {wh} | {dur:.1f}s | {video.stat().st_size / 1e6:.1f} MB")

        # ---- QA 總覽(直式格 216x384,每 3 秒一格)與說明檔
        qa = odir / f"qa_{sid}_{ver}"
        code = ("import sys; sys.path.insert(0, 'pipeline'); import qa_sheet as Q; Q.CW, Q.CH = 216, 384; "
                f"sys.argv = ['qa_sheet', {str(video)!r}, {str(tl)!r}, {str(qa)!r}, '--every', '3', '--cols', '10', '--per', '40']; Q.main()")
        rc, out = MV.run_cmd([PY, "-X", "utf8", "-c", code], log)
        qa_png = qa.with_name(qa.name + ".png")
        if not rc and qa.with_name(qa.name + "_01.png").exists():
            qa.with_name(qa.name + "_01.png").replace(qa_png)
        kinds = Counter(s.get("kind") for s in json.loads((wdir / "plan.json").read_text(encoding="utf-8")))
        notes = odir / f"{sid}_{ver}_說明.md"
        pn = max(odir.glob("v*_說明.md"), key=lambda f: f.stat().st_mtime, default=None)
        made = notes_skeleton(notes, tag, sid, ver, rng_desc, hook, dur, warns, pn)
        print(f"[4/4] QA {'OK' if not rc else '失敗'} | 說明檔{'骨架已寫' if made else '已存在,未覆寫'}")
        print("鏡頭種類: " + "、".join(f"{k} {v}" for k, v in kinds.most_common()))
    print(f"完成 {work} {ver}(共 {time.time() - t_all:.0f}s)")
    print(f"  成片 {video}\n  QA {qa_png}\n  說明 {notes}\n  log {logp}")
    print(f"  交付:deliver.py --tag {tag} --ver {sid}_{ver} --title <片名> --shorts(配音未聽審)")


if __name__ == "__main__":
    main()
