"""P4 一次性統計(只讀):配音品管失敗代碼 × 句型特徵,決定 script_lint 的 B 段警告門檻。
  python -X utf8 pipeline/tools/qc_fail_stats.py
資料:build/*/tts_qc.json 的 records(每句每次嘗試的 fails;idx、text、final fails)、
      build/*/tts_review.json 的 failed、projects/*/production.json blocks「品管未過到第 3 輪:句 [...]」的 script.txt 行(現況文字)。
句型特徵(與 script_lint T 同義):短句 = 去標點後 < short_chars 字;句內逗號 >= comma_n;句尾英文 = 句末(去標點)是英文字母。"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import paths as P  # noqa: E402

SHORT = 8
COMMAS = 3
PUNCT = "[\s,，。?？!！、;；:：「」『』()（）《》\"'…—-]"


def feats(text, short=SHORT, commas=COMMAS):
    """text -> 命中的特徵名 list。"""
    core = re.sub(PUNCT, "", text)
    out = []
    if core and len(core) < short:
        out.append("短句")
    if len(re.findall("[,，]", text)) >= commas:
        out.append("逗號>=%d" % commas)
    if re.search(r"[A-Za-z]$", core):
        out.append("句尾英文")
    return out


def _json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


base = Counter()   # 全部句子的特徵分布(基準率),scan_qc 填


def scan_qc():
    """-> (attempt 次數 Counter[code], final 失敗 Counter[code], {code: Counter[特徵]}, 掃到句數, 失敗句數)。"""
    att, fin, byf = Counter(), Counter(), {}
    sents = bad = 0
    base.clear()
    for f in sorted(P.BUILD.glob("*/tts_qc.json")) if hasattr(P, "BUILD") else sorted((P.ROOT / "build").glob("*/tts_qc.json")):
        for r in (_json(f) or {}).get("records") or []:
            text = r.get("text") or ""
            sents += 1
            for ft in feats(text) or ["(無特徵)"]:
                base[ft] += 1
            codes = set()
            for a in r.get("attempts") or []:
                codes.update(a.get("fails") or [])
            codes.update(r.get("fails") or [])
            if codes:
                bad += 1
            for c in codes:
                att[c] += 1
                for ft in feats(text) or ["(無特徵)"]:
                    byf.setdefault(c, Counter())[ft] += 1
            for c in r.get("fails") or []:
                fin[c] += 1
    return att, fin, byf, sents, bad


def scan_blocks():
    """production.json 卡點句:-> (卡點句數, Counter[特徵])。行號取 script.txt 現況文字;'12.1' 這種取整數部分。"""
    ft, n = Counter(), 0
    for f in sorted((P.ROOT / "projects").glob("*/production.json")):
        tag = f.parent.name
        sc = P.ROOT / tag / "script.txt"
        try:
            lines = sc.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        for b in (_json(f) or {}).get("blocks") or []:
            if "品管未過到" not in b.get("reason", ""):
                continue
            for m in re.findall(r"'?(\d+)(?:\.\d+)?'?", b["reason"].partition("句")[2]):
                i = int(m) - 1
                if 0 <= i < len(lines) and "|" in lines[i]:
                    n += 1
                    text = lines[i].partition("|")[2].rpartition(" ;; ")[0] if " ;; " in lines[i] else lines[i].partition("|")[2]
                    for x in feats(text) or ["(無特徵)"]:
                        ft[x] += 1
    return n, ft


def main():
    att, fin, byf, sents, bad = scan_qc()
    print(f"[qc_fail_stats] tts_qc records {sents} 句,曾失敗(任一次嘗試) {bad} 句")
    print("失敗代碼(曾出現的句數;括號 = 最終仍失敗):")
    for c, n in att.most_common(12):
        top = "、".join(f"{k}:{v}" for k, v in byf[c].most_common(4))
        print(f"  {c:18s} {n:5d}({fin.get(c, 0)})  特徵 {top}")
    n, ft = scan_blocks()
    print(f"production.json 卡點句(現況文字) {n} 句:" + "、".join(f"{k}:{v}" for k, v in ft.most_common()))
    allf = Counter()
    for c in byf.values():
        allf.update(c)
    print("全部失敗句特徵分布:" + "、".join(f"{k}:{v}" for k, v in allf.most_common()))
    print(f"基準(全部 {sents} 句)特徵分布:" + "、".join(f"{k}:{v}" for k, v in base.most_common()))
    for k in (k for k in base if k != "(無特徵)"):
        print(f"  {k}: 基準率 {base[k] / sents:.1%},曾失敗句中 {allf[k] / max(bad, 1):.1%}")


if __name__ == "__main__":
    main()
