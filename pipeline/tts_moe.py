#!/usr/bin/env python3
r"""教育部讀音資料(channel/_archive/plans/PLAN_流程嚴謹化_2026-10-29.md §4.3;只供 pron-review 核對與 tts_script 斷詞詞表,不接進配音流程、不改送引擎文字)。

來源:g0v moedict-data `dict-revised.json.xz`(《重編國語辭典修訂本》,CC BY-ND 3.0 TW),詳見 pipeline\moe\README.md。
精簡檔(進 git):
  moe\moe_pron.json   字 -> [{bopomofo, pinyin, words:[例詞 ≤10], note?}](多音字列全部讀音;例詞 = 該字在 2–4 字詞條中讀這個音的詞)
  moe\moe_word_pron.json  含多音字的 2–4 字詞條 -> 注音(lookup 詞時用)
  moe\words_moe.txt   2–4 字純中文詞條,一行一詞(tts_script 只取「實際出現在本片 script」的詞進 build\<tag>\words.txt)
指令:
  python -X utf8 pipeline\tts_moe.py lookup <字|詞>       讀音(注音+拼音)與例詞;詞:辭典詞條讀音,不在辭典就逐字列
  python -X utf8 pipeline\tts_moe.py --polyphones [--top 50]   多讀音字數與前 N(依例詞數排序)
  python -I -X utf8 pipeline\tts_moe.py --build tmp\moe_dl\dict-revised.json.xz   重建精簡檔(下載檔用 python -I 解析)
"""
import argparse
import json
import lzma
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOE_DIR = HERE / "moe"
PRON_FILE = MOE_DIR / "moe_pron.json"
WORDS_FILE = MOE_DIR / "words_moe.txt"
WORD_PRON_FILE = MOE_DIR / "moe_word_pron.json"
MAX_EX = 10
_CJK = re.compile(r"^[㐀-鿿豈-﫿]+$")
_NOTE = re.compile(r"(\([一二三四五六七八九十]+\)之(?:讀音|語音|又音))")


def _open(path):
    path = Path(path)
    return lzma.open(path, "rt", encoding="utf-8") if path.suffix == ".xz" else path.open(encoding="utf-8")


def compact(entries):
    """辭典條目 list -> (pron dict, words list, word_pron dict)。純函式(測試用小 fixture)。"""
    pron, words, word_pron = {}, set(), {}
    for e in entries:
        title = e.get("title") or ""
        if not _CJK.match(title):
            continue
        for h in e.get("heteronyms") or []:
            bp, py = (h.get("bopomofo") or "").strip(), (h.get("pinyin") or "").strip()
            if not bp:
                continue
            if len(title) == 1:
                rec = {"bopomofo": bp, "pinyin": py, "words": []}
                defs = " ".join(d.get("def", "") for d in h.get("definitions") or [])
                m = _NOTE.search(defs)
                if m:
                    rec["note"] = m.group(1)
                lst = pron.setdefault(title, [])
                if all(r["bopomofo"] != bp for r in lst):
                    lst.append(rec)
            elif 2 <= len(title) <= 4:
                words.add(title)
    for e in entries:                       # 第二輪:多音字的例詞(詞條注音逐字對到讀音)
        title = e.get("title") or ""
        if not (_CJK.match(title) and 2 <= len(title) <= 4):
            continue
        for h in e.get("heteronyms") or []:
            syl = (h.get("bopomofo") or "").split()
            if len(syl) != len(title):
                continue
            for ch, s in zip(title, syl):
                lst = pron.get(ch)
                if not lst or len(lst) < 2:
                    continue
                word_pron.setdefault(title, " ".join(syl))
                for r in lst:
                    if r["bopomofo"] == s and len(r["words"]) < MAX_EX and title not in r["words"]:
                        r["words"].append(title)
    return pron, sorted(words), word_pron


def build(src):
    with _open(src) as f:
        entries = json.load(f)
    pron, words, word_pron = compact(entries)
    MOE_DIR.mkdir(exist_ok=True)
    WORD_PRON_FILE.write_text(json.dumps(word_pron, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    PRON_FILE.write_text(json.dumps(pron, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    WORDS_FILE.write_text("\n".join(words) + "\n", encoding="utf-8")
    poly = sum(1 for v in pron.values() if len(v) > 1)
    print(f"辭典條目 {len(entries)};字 {len(pron)}(多音 {poly});2–4 字詞 {len(words)}")
    for f in (PRON_FILE, WORD_PRON_FILE, WORDS_FILE):
        print(f"  {f.relative_to(HERE.parent)} {f.stat().st_size / 1e6:.2f} MB")


_PRON = None
_WORDSET = None
_WORD_PRON = None


def load_word_pron():
    global _WORD_PRON
    if _WORD_PRON is None:
        _WORD_PRON = json.loads(WORD_PRON_FILE.read_text(encoding="utf-8")) if WORD_PRON_FILE.exists() else {}
    return _WORD_PRON


def load_pron():
    global _PRON
    if _PRON is None:
        _PRON = json.loads(PRON_FILE.read_text(encoding="utf-8")) if PRON_FILE.exists() else {}
    return _PRON


def load_words():
    global _WORDSET
    if _WORDSET is None:
        _WORDSET = set(WORDS_FILE.read_text(encoding="utf-8").split()) if WORDS_FILE.exists() else set()
    return _WORDSET


def lookup(q, pron=None, words=None, word_pron=None):
    """回傳可印的行(list[str])。"""
    pron = load_pron() if pron is None else pron
    words = load_words() if words is None else words
    word_pron = load_word_pron() if word_pron is None else word_pron
    if not pron:
        return [f"沒有 {PRON_FILE.name}(先跑 tts_moe.py --build,見 pipeline/moe/README.md)"]
    lines = []
    if len(q) > 1:
        lines.append(f"{q}:{'辭典詞條' if q in words else '不在 2–4 字詞條'}" + (f" 讀 {word_pron[q]}" if q in word_pron else ""))
        if q in word_pron and len(word_pron[q].split()) == len(q):
            for ch, bp in zip(q, word_pron[q].split()):
                if len(pron.get(ch, [])) > 1:
                    py = next((r["pinyin"] for r in pron[ch] if r["bopomofo"] == bp), "")
                    lines.append(f"  {ch} 在「{q}」讀 {bp} {py}")
    for ch in dict.fromkeys(q):
        rs = pron.get(ch)
        if not rs:
            lines.append(f"{ch}:辭典無單字條目")
            continue
        tag = "多音" if len(rs) > 1 else "單音"
        lines.append(f"{ch}({tag})")
        for r in rs:
            note = f" [{r['note']}]" if r.get("note") else ""
            ex = "、".join(r["words"]) if r["words"] else "-"
            lines.append(f"  {r['bopomofo']} {r['pinyin']}{note} 例:{ex}")
    return lines


def polyphones(pron=None, top=50):
    pron = load_pron() if pron is None else pron
    poly = {c: v for c, v in pron.items() if len(v) > 1}
    rank = sorted(poly, key=lambda c: -sum(len(r["words"]) for r in poly[c]))
    out = [f"多讀音字 {len(poly)} / 單字條目 {len(pron)};前 {min(top, len(rank))}(依例詞數):"]
    for c in rank[:top]:
        out.append(f"  {c}: " + " / ".join(f"{r['bopomofo']} {r['pinyin']}" for r in poly[c]))
    return out


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", choices=["lookup"])
    ap.add_argument("query", nargs="?")
    ap.add_argument("--build", metavar="SRC", help="dict-revised.json(.xz) 下載檔")
    ap.add_argument("--polyphones", action="store_true")
    ap.add_argument("--top", type=int, default=50)
    a = ap.parse_args(argv)
    if a.build:
        build(a.build)
    elif a.polyphones:
        print("\n".join(polyphones(top=a.top)))
    elif a.cmd == "lookup" and a.query:
        print("\n".join(lookup(a.query)))
    else:
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
