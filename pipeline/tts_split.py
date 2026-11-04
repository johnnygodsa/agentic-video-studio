"""配音單位切分(只用標準函式庫):文案一行含多個句子時,依「。?!」拆成子句,各自合成、各自過品管,再以停頓接起來。

規則(2026-10-10 使用者指定):句號後 CLAUSE_GAP_PERIOD 秒、問號與驚嘆號後 CLAUSE_GAP_QUESTION 秒。
- 引號 / 括號內的句末標點不拆(「悲報,金團復活了。」整個留在同一單位);標點後緊跟的收引號歸前一句。
- 一行只有一個句子 -> 回傳 [整行原文](快取鍵、音檔與沒有這個機制時完全相同)。
- 沒有任何字(只剩標點)的片段併回前一句。
- 切完的子句各自帶標點原樣交給合成(prep_text 之後的處理與整行時相同);@say 替換發生在拆句之前(傳入的就是替換後的 say)。
"""
import re

CLAUSE_GAP_PERIOD = 0.12
CLAUSE_GAP_QUESTION = 0.20
_END = set("。?!？！")
_OPEN = {"「": "」", "『": "』", "（": "）", "(": ")", "“": "”"}
_CLOSE = set(_OPEN.values())
_WORD = re.compile(r"[一-鿿A-Za-z0-9]")


def split_clauses(say):
    """回傳 [(子句文字, 句後停頓秒)];最後一句的停頓為 0(行與行之間的停頓由時間軸負責)。"""
    s = say.strip()
    out, cur, stack, i, n = [], "", [], 0, len(s)
    while i < n:
        ch = s[i]
        cur += ch
        i += 1
        if ch in _OPEN:
            stack.append(_OPEN[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
        elif ch in _END and not stack:
            while i < n and (s[i] in _END or s[i] in _CLOSE):   # 連續標點與緊跟的收引號歸這一句
                cur += s[i]
                i += 1
            out.append(cur.strip())
            cur = ""
    if cur.strip():
        out.append(cur.strip())
    merged = []
    for c in out:
        if merged and not _WORD.search(c):
            merged[-1] += c
        else:
            merged.append(c)
    if len(merged) <= 1:
        return [(s, 0.0)]
    res = []
    for k, c in enumerate(merged):
        core = c.rstrip("".join(_CLOSE) + " ")
        gap = CLAUSE_GAP_QUESTION if core[-1:] in set("?!？！") else CLAUSE_GAP_PERIOD
        res.append((c, gap if k + 1 < len(merged) else 0.0))
    return res


if __name__ == "__main__":
    import sys
    for t in sys.argv[1:] or ["金團到底該不該禁?台服不禁,對台灣玩家是好事還是壞事?", "標題叫「悲報,金團復活了」。", "他說:「好。不好。」然後走了。哦!"]:
        print(t, "->", split_clauses(t))
