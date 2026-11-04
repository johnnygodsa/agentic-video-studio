#!/usr/bin/env python3
r"""逗號連讀(comma_runon,tts_pause.COMMA_RUNON_MIN)的離線報告與沙盒實測;tts_env_chattts 執行。
離線(只讀 build\<tag>\tts_qc.json,不改檔):
  tts_env_chattts\Scripts\python.exe -X utf8 pipeline\tts_runon.py <tag>... | --all
  舊紀錄用 pause_fix.before;沒有 soft 欄位的紀錄(2026-10-29 前)由文字補判頓號,要載 tts_chattts。
沙盒(真合成、要 GPU,排全機鎖;只寫 tmp\comma_runon_test\,不碰 build\):
  tts_env_chattts\Scripts\python.exe -X utf8 pipeline\tts_runon.py --sandbox <tag> --lines 5,15,24
  取該片 tts_qc.json 的文字與 _qc_base_cosy3.json 基準,用片子同 seed、同 speed 跑 tts_cosy3,印每句嘗試次數與最後 comma_runon。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paths as P  # noqa: E402
import tts_pause as TP  # noqa: E402

BOX = P.TMP / "comma_runon_test"


def load_recs(tag):
    return json.loads((P.build_dir(tag) / "tts_qc.json").read_text(encoding="utf-8"))["records"]


def fill_soft(rec):
    """舊紀錄的 pauses 沒有 soft:同 tts_chattts.align_info 由文字判頓號。"""
    import tts_chattts as TC
    text = rec.get("measure_text") or rec["text"]
    prep, simp = TC.prep_text(text), TC._cc.convert(text)
    cmap = TP.char_map(simp, prep)
    soft_at = {cmap[q] for q, c in enumerate(simp) if c in TP.SOFT_MARKS}
    us = TP.units(prep)
    for p in rec.get("pauses") or []:
        if p["i"] + 1 < len(us):
            marks = [q for q in range(us[p["i"]][2], us[p["i"] + 1][1]) if prep[q] in TP.PAUSE_MARKS]
            p["soft"] = all(prep[q] in TP.SOFT_MARKS or q in soft_at for q in marks)


def replay(tag):
    """-> (句數, [(句號, [dict(at, before)])])。"""
    recs = load_recs(tag)
    for r in recs:
        if any("soft" not in p for p in r.get("pauses") or []):
            fill_soft(r)
    hits = [(r["idx"], TP.runon_from_rec(r)) for r in recs]
    return len(recs), [x for x in hits if x[1]]


def report(tags):
    total = 0
    for tag in tags:
        n, hits = replay(tag)
        total += len(hits)
        print(f"{tag}: {len(hits)}/{n} 句 " + " ".join(f"{i}({'、'.join(x['at'] for x in xs)})" for i, xs in hits))
    print(f"合計 {total} 句")


def sandbox(tag, lines, max_retry):
    recs = {str(r["idx"]): r for r in load_recs(tag)}
    miss = [x for x in lines if x not in recs]
    if miss:
        sys.exit(f"[runon] {tag} 沒有這些句號: {miss}")
    if BOX.exists():
        shutil.rmtree(BOX)
    BOX.mkdir(parents=True)
    speed = "1.18"
    base = P.tts_dir(tag, "cosy3") / "_qc_base_cosy3.json"
    if base.exists():   # 小批次沿用整片基準(音高/聲紋/語速),判定才與片子相同
        shutil.copy(base, BOX / base.name)
        speed = str(json.loads(base.read_text(encoding="utf-8"))["speed"])
    jf = BOX / "jobs.json"
    jobs = [dict(idx=recs[x]["idx"], text=recs[x]["text"], out=str(BOX / f"{x.replace('.', '_')}.wav"), verify=False) for x in lines]
    jf.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    cmd = [str(P.TTS_ENV), "-X", "utf8", str(HERE / "tts_cosy3.py"), str(jf), "--ref", str(P.COSY_REF), "--speed", speed,
           "--voice", P.COSY_REF.name, "--max-retry", str(max_retry)]
    rc = subprocess.run(cmd, env=dict(os.environ, TEMP=str(P.TMP), TMP=str(P.TMP))).returncode
    if rc:
        sys.exit(f"[runon] tts_cosy3 結束碼 {rc}")
    rep = json.loads((BOX / "jobs.qc.json").read_text(encoding="utf-8"))
    for r in rep["lines"]:
        print(f"{r['idx']}: 嘗試 {len(r['attempts'])} 次(連讀 {sum('comma_runon' in a['fails'] for a in r['attempts'])} 次)"
              f" passed={r['passed']} fails={r['fails']} comma_runon={r['comma_runon']}")
    print(f"未過 {rep['failed']};音檔在 {BOX}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", nargs="*")
    ap.add_argument("--all", action="store_true", help="離線報告:build 下所有有 tts_qc.json 的片")
    ap.add_argument("--sandbox", metavar="TAG", help="沙盒實測(真合成)")
    ap.add_argument("--lines", help="沙盒句號,逗號分隔")
    ap.add_argument("--max-retry", type=int, default=6)
    a = ap.parse_args()
    if a.sandbox:
        if not a.lines:
            ap.error("--sandbox 要給 --lines")
        sandbox(a.sandbox, a.lines.split(","), a.max_retry)
        return
    tags = sorted(f.parent.name for f in P.BUILD.glob("*/tts_qc.json")) if a.all else a.tags
    if not tags:
        ap.error("要給片名或 --all")
    report(tags)


if __name__ == "__main__":
    main()
