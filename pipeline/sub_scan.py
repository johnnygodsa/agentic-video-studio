#!/usr/bin/env python3
r"""字幕檢查(不渲染):
python -X utf8 pipeline\run.py sub_scan --tag <tag>           掃全片字幕拆段,列出把詞切開的接縫(渲染前檢查也會做)
python -X utf8 pipeline\run.py sub_scan --tag <tag> --sync    字幕段起點與語音的時間差(需要配音快取;見 build.sub_sync)
python -X utf8 pipeline\run.py sub_scan --tag <tag> --seg ckip [--judge jieba] [--json out.json]
    T2 比較用:指定拆段斷詞器(預設看環境變數 CV_SEG,再預設 jieba);印接縫數與分段 CPU 秒數(不含模型載入);
    --judge = 另用該斷詞器重判同一份拆段結果的接縫數(交叉判讀,避免「自己切自己判」);--json 寫出機器可讀結果(sub_seg_compare.py 用)。
    2026-10-29(channel/_archive/plans/PLAN_流程嚴謹化_2026-10-29.md §4.2):--judge 預設 ckip;ckip 沒裝(預設 python 沒有,tts_env_chattts 有)退回 jieba 自判,第一行印「judge=jieba(ckip 未安裝)」。
    載入每片詞表 build/<tag>/words.txt(--words 可指定別的檔;沒有就不載,行為不變)。拆段或判讀任一有接縫 -> 結束碼 1。
    2026-10-29:另計「片語切開」(build.sub_phrase_seams:功能詞後、數量詞組、英文名中間、英文與名詞、「的」字結構內),只印不影響結束碼。
結束碼:有問題 1,沒有 0。"""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import build as B
import paths as P
import seg as SEG


def strict_stats(lines):
    """超寬段中「嚴格合法切點(含跨界字串檢查)就能解」之外要放寬的個數,與可切點/候選切點總數(可切點越少 = 斷詞器把詞併得越大)。
    接縫數常常兩種斷詞器都是 0(因為會逐級放寬),這幾個數字才看得出差別。"""
    relaxed = n_long = n_leg = n_pos = 0
    for ln in lines:
        for p in B._sub_pieces(ln["text"]):
            core = B._strip(p)
            if not core or B._dw(core) <= B.SUB_MAX_W:
                continue
            n_long += 1
            legal = B._legal_cuts(core, True)
            if legal is None:
                continue
            n_leg += len(legal)
            n_pos += max(len(core) - 1, 0)
            n0 = -(-B._dw(core) // B.SUB_MAX_W)
            if not any(B._split_dp(core, legal, n) for n in range(int(n0), int(n0) + 3)):
                relaxed += 1
    return relaxed, n_long, n_leg, n_pos


def _seam_list(bad, sg):
    """[(句, 左段, 右段, 原因)] -> [{line,a,b,why,word,token}];word = 原因「詞「X」」的 X,token = 斷詞器把 X 切成單一 token(pron_pre 可直接寫進每片詞表)。"""
    import re
    out = []
    for idx, a, b, why in bad:
        m = re.search(r"詞「(.+?)」", why)
        word = m.group(1) if m else None
        tok = False
        if word and sg is not None:
            try:
                tok = word in set(sg.cut(a + b))
            except Exception:  # noqa: BLE001
                tok = False
        out.append({"line": idx, "a": a, "b": b, "why": why, "word": word, "token": tok})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--script", help="預設 <tag>/script.json")
    ap.add_argument("--sync", action="store_true", help="改查字幕段起點與語音的時間差(以下配音參數要與成片相同,預設為定案男聲)")
    ap.add_argument("--voice", default="seed402")
    ap.add_argument("--rate", default="+18%")
    ap.add_argument("--gap", type=float, default=0.12)
    ap.add_argument("--section-gap", type=float, default=0.30)
    ap.add_argument("--spk", default="M_seed_402.pt")
    ap.add_argument("--tol", type=float, default=0.15)
    ap.add_argument("--show", type=int, default=20, help="最多列幾筆")
    ap.add_argument("--seg", choices=SEG.NAMES, default=None, help="拆段斷詞器 jieba|ckip(預設看 CV_SEG,再預設 jieba)")
    ap.add_argument("--judge", choices=SEG.NAMES, default="ckip", help="另用此斷詞器重判拆段結果的接縫數(交叉判讀;預設 ckip,沒裝退回 jieba)")
    ap.add_argument("--words", help="每片詞表檔(預設 build/<tag>/words.txt,沒有就不載)")
    ap.add_argument("--json", help="把結果(接縫數、CPU 秒數…)寫成 JSON")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    script = P.find(args.script or f"{args.tag}/script.json", P.REPO)
    lines = B.load_lines(script)
    if args.seg:
        SEG.set_seg(args.seg)
    SEG.set_tag(args.tag, args.words)
    if not args.sync:
        if args.judge == "ckip" and importlib.util.find_spec("ckip_transformers") is None:
            args.judge = "jieba"
            print("judge=jieba(ckip 未安裝;tts_env_chattts 的 python 有 ckip_transformers)")
        t0 = time.process_time()
        sg = SEG.segmenter()                      # 先載入(ckip 模型載入時間另計,不算進分段 CPU 秒數)
        load_s = time.process_time() - t0
        used = sg.name if sg else "none"
        if used != SEG.seg_name():
            print(f"[warn] 要求斷詞器 {SEG.seg_name()},實際用 {used}")
        c0, w0 = time.process_time(), time.perf_counter()
        if sg:      # ckip 批次送模型(比逐句快很多);jieba 為 no-op
            sg.prefetch(["".join(core) for ln in lines for p in B._sub_pieces(ln["text"])
                         if (core := B._strip(p)) and B._dw(core) > B.SUB_MAX_W])
        nseg = sum(len(B.split_phrases(ln["text"])) for ln in lines)
        cpu_s, wall_s = time.process_time() - c0, time.perf_counter() - w0
        bad = [(ln["idx"], a, b, why) for ln in lines for a, b, why in B.sub_seams(ln["text"])]
        relaxed, n_long, n_leg, n_pos = strict_stats(lines)
        pbad = [(ln["idx"], a, b, why) for ln in lines for a, b, why in B.sub_phrase_seams(ln["text"])]
        print(f"字幕拆段[{used}]: {len(lines)} 句 {nseg} 段,切開詞的接縫 {len(bad)} 筆、片語切開 {len(pbad)} 筆(超寬段 {n_long} 個,嚴格切點無解而放寬 {relaxed} 個,可切點 {n_leg}/{n_pos}),分段 CPU {cpu_s:.2f}s(牆鐘 {wall_s:.2f}s,斷詞器載入 {load_s:.2f}s)")
        res = {"tag": args.tag, "seg_req": SEG.seg_name(), "seg": used, "lines": len(lines), "segments": nseg,
               "seams": len(bad), "phrase_seams": len(pbad), "long_pieces": n_long, "relaxed": relaxed, "legal_cuts": n_leg, "cut_positions": n_pos, "cpu_s": round(cpu_s, 3), "wall_s": round(wall_s, 3), "load_s": round(load_s, 3)}
        if args.judge:
            jg = SEG.segmenter(args.judge)
            res["judge"] = jg.name if jg else "none"
            if jg is not None and jg.name != args.judge:
                print(f"[warn] 判讀斷詞器 {args.judge} 不可用,實際用 {jg.name}")
            jbad = [(ln["idx"], a, b, why) for ln in lines for a, b, why in B.sub_seams(ln["text"], judge=args.judge)]
            res["seams_judge"] = len(jbad)
            print(f"  以 {res['judge']} 判讀同一份拆段: 接縫 {len(jbad)} 筆")
        res["seam_list"] = _seam_list(bad, sg)       # pron_pre.py 用:每個接縫的詞與「是否為斷詞器的單一 token」
        if args.judge and jg is not None:
            res["seam_list_judge"] = _seam_list(jbad, jg)
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        for idx, a, b, why in bad[:args.show]:
            print(f"  句{idx} {why}: {a} | {b}")
        for idx, a, b, why in pbad[:args.show]:
            print(f"  句{idx} 片語切開 {why}: {a} | {b}")
        sys.exit(1 if bad or res.get("seams_judge") else 0)
    bdir = P.build_dir(args.tag)
    _, tlmeta = B.load_meta(script)
    tts_cmd = [P.TTS_ENV, P.REPO / "pipeline" / "tts_chattts.py", "--spk-pt", P.speaker(args.spk)]
    B.tts_all(lines, args.voice, args.rate, bdir / "tts", "chattts", tts_cmd, no_synth=True)
    B.build_timeline(lines, args.gap, args.section_gap, tlmeta)
    rows = B.sub_sync(lines)
    bad = [r for r in rows if abs(r["diff"]) > args.tol]
    src = {k: sum(1 for r in rows if r["ref"] == k) for k in ("unit", "align", "prop")}
    print(f"字幕同步: {len(rows)} 段(單位起點 {src['unit']}、對齊時間 {src['align']}、單位內等比例 {src['prop']}),"
          f"與語音相差 > {args.tol:.2f}s 的 {len(bad)} 段")
    for r in sorted(bad, key=lambda r: -abs(r["diff"]))[:args.show]:
        print(f"  句{r['idx']} {r['start']:.2f}s {r['diff']:+.2f}s [{r['ref']}] {r['text']}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
