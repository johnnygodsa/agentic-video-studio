#!/usr/bin/env python3
r"""常讀錯字累積表 pipeline\pron_backlog.md(channel/_archive/plans/PLAN_流程嚴謹化_2026-10-29.md §4.3;只用標準函式庫)。

表格欄:字 | 語境詞 | 證據 | 命中次數 | 狀態 | 來源片 | 日期
- 鍵 = (字, 語境詞);upsert 同鍵累計:來源片記 `片名×次數`,同片重跑取較大值(不重複累加),命中次數 = 各片次數總和。
- 證據:polyphone strong(tts_polyphone kind=alt+strong)/ g2p 不一致 / pron_rules 未驗證 / 使用者抽聽 / 留言旁白抱怨(後兩種手寫)。
- 狀態:待規則 -> 已規則 -> 已驗證;只升不降(程式寫入一律「待規則」,已規則/已驗證保留);主對話手改狀態。
寫入者:tts_script.py(g2p 不一致、pron_rules unverified 命中)、tts_polyphone.py(alt+strong)、`--init` 回填 projects\*\polyphone_report.json。
CLI:python -X utf8 pipeline\pron_backlog.py --init | --top N
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import paths as P

FILE = Path(__file__).resolve().parent / "pron_backlog.md"
COLS = ["字", "語境詞", "證據", "命中次數", "狀態", "來源片", "日期"]
STATES = ["待規則", "已規則", "已驗證"]
HEAD = ("# 讀音待辦 pron_backlog(程式自動 upsert;規則見 pipeline/pron_backlog.py 檔頭、docs/tts.md §4.5)\n\n"
        "每支片主對話只處理「待規則」命中最多的前 3 條(`tts_script.py --backlog-top 3`);登 `_verified` 要有證據。\n\n")
_SRC = re.compile(r"([^\s,×]+)×(\d+)")


def context(text, pos, w=1):
    """語境詞:pos 前後各 w 字(去掉標點與空白)。"""
    seg = text[max(0, pos - w):pos + w + 1]
    return re.sub(r"[^\w]", "", seg) or text[pos]


def _esc(s):
    return str(s).replace("|", "\\|")


def load(path=FILE):
    rows = []
    if not Path(path).exists():
        return rows
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        if not ln.startswith("|") or ln.startswith("|---") or ln.startswith("| 字 |"):
            continue
        cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", ln.strip())[1:-1]]
        if len(cells) != len(COLS):
            continue
        r = dict(zip(COLS, cells))
        r["src"] = {m.group(1): int(m.group(2)) for m in _SRC.finditer(r["來源片"])}
        rows.append(r)
    return rows


def save(rows, path=FILE):
    rows = sorted(rows, key=lambda r: (STATES.index(r["狀態"]) if r["狀態"] in STATES else 9, -int(r["命中次數"]), r["字"]))
    out = [HEAD, "| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
    for r in rows:
        r["來源片"] = ", ".join(f"{k}×{v}" for k, v in sorted(r["src"].items()))
        r["命中次數"] = str(sum(r["src"].values()))
        out.append("| " + " | ".join(_esc(r[c]) for c in COLS) + " |")
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")


def upsert(items, tag, path=FILE, today=None):
    """items = [(字, 語境詞, 證據)](同一片一次跑的全部;同鍵出現幾次 = 本片次數)。回傳 (新增, 更新) 筆數。"""
    today = today or date.today().isoformat()
    rows = load(path)
    idx = {(r["字"], r["語境詞"]): r for r in rows}
    cnt, ev = {}, {}
    for ch, ctx, why in items:
        cnt[(ch, ctx)] = cnt.get((ch, ctx), 0) + 1
        ev.setdefault((ch, ctx), []).append(why)
    new = upd = 0
    for k, n in cnt.items():
        r = idx.get(k)
        if r is None:
            r = idx[k] = dict(字=k[0], 語境詞=k[1], 證據="", 命中次數="0", 狀態="待規則", 來源片="", 日期=today, src={})
            rows.append(r)
            new += 1
        else:
            upd += 1
        have = [e for e in r["證據"].split("、") if e]
        r["證據"] = "、".join(dict.fromkeys(have + ev[k]))
        if n > r["src"].get(tag, 0):
            r["src"][tag] = n
            r["日期"] = today
    save(rows, path)
    return new, upd


def _report_items(report):
    for v in report.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "char" in v[0]:
            return v
    return []


def polyphone_items(report):
    """polyphone_report.json -> upsert items(只取 kind=alt 且 evidence=strong)。"""
    return [(u["char"], context(u.get("text") or u["char"], u.get("pos", 0)), "polyphone strong")
            for u in _report_items(report) if u.get("kind") == "alt" and u.get("evidence") == "strong"]


def init(path=FILE):
    tot = 0
    for f in sorted(P.PROJECTS.glob("*/polyphone_report.json")):
        rep = json.loads(f.read_text(encoding="utf-8"))
        items = polyphone_items(rep)
        if items:
            upsert(items, rep.get("tag") or f.parent.name, path)
            tot += len(items)
    print(f"回填 polyphone alt+strong {tot} 筆 -> {path.name}({len(load(path))} 列)")


def top(n=3, path=FILE):
    rows = [r for r in load(path) if r["狀態"] == "待規則"]
    return sorted(rows, key=lambda r: -int(r["命中次數"]))[:n]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--init" in sys.argv:
        init()
    elif "--top" in sys.argv:
        for r in top(int(sys.argv[sys.argv.index("--top") + 1])):
            print(f"{r['字']} | {r['語境詞']} | {r['證據']} | {r['命中次數']} | {r['來源片']}")
    else:
        sys.exit(__doc__)
