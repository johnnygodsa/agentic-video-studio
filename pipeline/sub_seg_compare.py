#!/usr/bin/env python3
r"""T2 斷詞比較(jieba vs ckip),一鍵對多支片各跑兩種分詞,輸出 markdown 比較表:
python -X utf8 pipeline\run.py sub_seg_compare --tags tagA tagB tagC tagD tagE      # 指定 5 支片
python -X utf8 pipeline\run.py sub_seg_compare                                       # 不指定 = script.json 最近修改的 5 支
選項:--n 5(自動挑幾支)  --out <md>(預設 tmp\sub_seg_compare.md)  --segs jieba ckip

每個 (tag, 斷詞器) 開一個子行程跑 `sub_scan.py --seg X --judge <另一個>`(CPU 秒數才不會互相污染快取),表內欄位:
  自判接縫 = 用同一個斷詞器拆段又判讀;互判接縫 = 同一份拆段改用另一個斷詞器判讀(避免「自己切自己判」,看拆段是否也守得住對方的詞);
  放寬 = 超寬段中嚴格切點無解而要放寬的個數/超寬段數(接縫數常兩邊都 0,看這欄);可切點 = 合法切點/候選切點(越少代表詞併得越大);
  分段 CPU = 批次斷詞 + split_phrases 的 process_time(不含模型載入;載入秒數另列)。
判定(channel/_archive/plans/PLAN_工具升級_2026-10-26.md T2 第 4 步):ckip 接縫數較少的片數 >= 4/5 才建議把預設改 ckip;自判與互判兩種都列,結論以兩者皆過為準。
注意:跨界字串檢查查的是 jieba 詞典(與斷詞器無關);ckip 沒裝或模型下載失敗時 sub_scan 會警告並退回 jieba,表內「實際」欄會看到,此時比較無效。
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import paths as P


def pick_tags(n):
    cands = [(p.stat().st_mtime, p.parent.name) for p in P.REPO.glob("*/script.json") if not p.parent.name.startswith(("_", "."))]
    return [t for _, t in sorted(cands, reverse=True)[:n]]


def run_one(tag, seg, judge, tmpdir):
    out = Path(tmpdir) / f"{tag}_{seg}.json"
    cmd = [sys.executable, "-X", "utf8", str(Path(__file__).resolve().parent / "sub_scan.py"), "--tag", tag, "--seg", seg,
           "--judge", judge, "--json", str(out), "--show", "0"]
    r = subprocess.run(cmd, cwd=P.REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not out.exists():
        return {"error": (r.stderr or r.stdout).strip().splitlines()[-1:] or ["無輸出"]}
    d = json.loads(out.read_text(encoding="utf-8"))
    d["warn"] = [ln for ln in r.stdout.splitlines() if ln.startswith("[warn]")]
    return d


def table(tags, segs, res):
    a, b = segs
    h = ["| tag | 句 | 段 | " + " | ".join(f"{s} 自判 | {s} 互判 | {s} 放寬 | {s} 可切點 | {s} CPU秒" for s in segs) + " | 實際斷詞器 |", "|" + "---|" * (3 + 5 * len(segs) + 1)]
    for t in tags:
        ra, rb = res[(t, a)], res[(t, b)]
        if "error" in ra or "error" in rb:
            h.append(f"| {t} | 錯誤: {ra.get('error') or rb.get('error')} |" + " |" * (5 * len(segs) + 2))
            continue
        cells = []
        for r in (ra, rb):
            cells += [str(r["seams"]), str(r.get("seams_judge", "-")), f"{r.get('relaxed', '-')}/{r.get('long_pieces', '-')}",
                      f"{r.get('legal_cuts', '-')}/{r.get('cut_positions', '-')}", f"{r['cpu_s']:.2f}"]
        h.append(f"| {t} | {ra['lines']} | {ra['segments']} | " + " | ".join(cells) + f" | {ra['seg']}/{rb['seg']} |")
    return "\n".join(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="*", help="片名(資料夾名),預設 script.json 最近修改的 --n 支")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--segs", nargs=2, default=["jieba", "ckip"], metavar=("BASE", "NEW"))
    ap.add_argument("--out", help="輸出 md(預設 tmp\\sub_seg_compare.md)")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tags = args.tags or pick_tags(args.n)
    segs = args.segs
    res = {}
    with tempfile.TemporaryDirectory() as td:
        for t in tags:
            for s in segs:
                other = segs[1] if s == segs[0] else segs[0]
                print(f"[run] {t} / {s} ...", flush=True)
                res[(t, s)] = run_one(t, s, other, td)
    ok = [t for t in tags if "error" not in res[(t, segs[0])] and "error" not in res[(t, segs[1])]]
    fb = [t for t in ok if res[(t, segs[1])]["seg"] != segs[1]]
    lines = [f"# 字幕斷詞比較 {segs[0]} vs {segs[1]}", "", table(tags, segs, res), ""]
    if ok:
        def tot(s, k):
            return sum(res[(t, s)].get(k, 0) for t in ok)
        win_self = sum(1 for t in ok if res[(t, segs[1])]["seams"] < res[(t, segs[0])]["seams"])
        win_x = sum(1 for t in ok if res[(t, segs[1])].get("seams_judge", 0) < res[(t, segs[0])].get("seams_judge", 0))
        lines += [f"合計接縫(自判):{segs[0]} {tot(segs[0], 'seams')}、{segs[1]} {tot(segs[1], 'seams')};"
                  f"(互判):{segs[0]} {tot(segs[0], 'seams_judge')}、{segs[1]} {tot(segs[1], 'seams_judge')}",
                  f"分段 CPU 合計:{segs[0]} {tot(segs[0], 'cpu_s'):.2f}s、{segs[1]} {tot(segs[1], 'cpu_s'):.2f}s;"
                  f"{segs[1]} 載入 {max(res[(t, segs[1])].get('load_s', 0) for t in ok):.1f}s/次",
                  f"{segs[1]} 接縫較少的片數:自判 {win_self}/{len(ok)}、互判 {win_x}/{len(ok)}"
                  f"(PLAN 門檻:>= 4/5 才改預設;兩者都過再改)"]
    if fb:
        lines.append(f"**無效比較**:{', '.join(fb)} 的 {segs[1]} 實際退回 jieba(沒裝或模型載入失敗)")
    lines.append("證據強度:單一機器、5 支片自家語料的接縫數;接縫數不等於觀看品質,贏了也只是「值得換」的弱證據,需抽看字幕斷點。")
    text = "\n".join(lines)
    print("\n" + text)
    out = Path(args.out) if args.out else P.TMP / "sub_seg_compare.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"\n已寫入 {out}")


if __name__ == "__main__":
    main()
