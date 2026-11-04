#!/usr/bin/env python3
r"""配音前英文專有名詞對照:全片的英文詞對照 say_terms.json 登錄表,未登錄者擋下來由主對話決定。

python -X utf8 pipeline/tts_terms.py <tag> [--json] [--root 目錄]
每句取 `say or text`(<tag>/script.json 的 sections[].lines[])。
  錯誤 已登錄唸法未套用:登錄表 say 非 null 的 term 仍出現在送配音的文字裡(script.txt 沒加 @say)
  錯誤 未登錄英文詞:拉丁字母詞(含單一空格接的多字詞如 Xbox 360)不在登錄表
  資訊 直接唸英文(優先聽):登錄表 say 為 null 的詞
有錯誤 exit 1,否則 0。登錄表 pipeline/say_terms.json(新詞由主對話決定後登錄,附日期)。
"""
import argparse
import json
import sys
from pathlib import Path

import terms_check as TC

HERE = Path(__file__).resolve().parent
TERMS_FILE = TC.TERMS_FILE
MAX_LINES = 25
# 判斷邏輯在 terms_check.py(單一來源);這裡只留 CLI 與報告,舊名稱轉出供既有呼叫與測試
load_terms, is_latin, analyze = TC.load_terms, TC.is_latin, TC.analyze


def script_texts(tag, root=None):
    sp = Path(root or HERE.parent) / tag / "script.json"
    d = json.loads(sp.read_text(encoding="utf-8-sig"))
    return [(l.get("say") or l.get("text") or "") for s in d["sections"] for l in s["lines"]]


def has_error(res):
    return bool(res["unapplied"] or res["unregistered"])


def report(res, n):
    ua, ur, dr = res["unapplied"], res["unregistered"], res["direct"]
    out = [f"[terms] {n} 句 | 錯誤:未套用 {len(ua)} 項、未登錄 {len(ur)} 項 | 直接唸英文 {len(dr)} 項"]
    if ua:
        out.append(f"錯誤 已登錄唸法未套用({len(ua)}):")
        for term, e in ua.items():
            out.append(f"  第 {e['lines'][0]} 句起共 {len(e['lines'])} 句 {term} → 建議 `@say {term}={e['say']}`")
    if ur:
        out.append(f"錯誤 未登錄英文詞({len(ur)}):")
        for term, e in sorted(ur.items(), key=lambda kv: kv[1]["lines"][0]):
            out.append(f"  {term} ×{len(e['lines'])} 句,首見第 {e['lines'][0]} 句")
    if dr:
        out.append(f"資訊 直接唸英文(優先聽)({len(dr)}):")
        out.append("  " + "、".join(f"{t}×{len(e['lines'])}" for t, e in dr.items()))
    do = res.get("direct_open") or {}
    multi = {t: ls for t, ls in do.items() if len(ls) >= 2}
    if multi:   # 配音稿(tts_script.py)算未決、不得配音;這裡只列(結束碼不變,舊片重渲染不擋)
        out.append(f"未決 英文直送多次且未驗證(建議音譯)({len(multi)}):" + "、".join(f"{t}×{len(ls)}" for t, ls in multi.items()))
    if len(do) > len(multi):
        out.append("警告 英文直送單次且未驗證:" + "、".join(t for t in do if t not in multi))
    if len(out) > MAX_LINES:
        out = out[:MAX_LINES - 1] + [f"  …(另有 {len(out) - MAX_LINES + 1} 行省略,用 --json 看全部)"]
    return out


def main():
    ap = argparse.ArgumentParser(description="配音前英文詞對照(見檔頭說明)")
    ap.add_argument("tag")
    ap.add_argument("--json", action="store_true", help="輸出完整 JSON")
    ap.add_argument("--root", help="script.json 所在的上層目錄(預設 repo 根;測試用)")
    ap.add_argument("--engine", choices=("chattts", "cosy3"), default="cosy3",
                    help="cosy3 = 對照 cosy_terms.json(tts_cosy_text.analyze;寫法由引擎自動套,只擋未登錄詞)")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    texts = script_texts(a.tag, a.root)
    if a.engine == "cosy3":
        res = TC.analyze_cosy(texts)
        res["direct_open"] = TC.direct_open(texts)
    else:
        res = TC.analyze(texts)
    if a.json:
        print(json.dumps(dict(res, sentences=len(texts), errors=has_error(res)), ensure_ascii=False, indent=1))
    else:
        print("\n".join(report(res, len(texts))))
    sys.exit(1 if has_error(res) else 0)


if __name__ == "__main__":
    main()
