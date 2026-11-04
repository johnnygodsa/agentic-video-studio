#!/usr/bin/env python3
r"""破音字誤讀偵測:拿品管已有的語音辨識結果,逐字比對「預期讀音」與「辨識到的讀音」(含聲調),不重新合成、不需顯示卡。

用法(用 tts_env_chattts 的 python,需要 pypinyin、opencc):
  tts_env_chattts\Scripts\python.exe -X utf8 pipeline\tts_polyphone.py <tag>
  讀 build\<tag>\tts_qc.json(每個配音單位的 text 與 asr),寫 projects\<tag>\polyphone_report.json,並印出前 15 筆。

背景(2026-10-11 使用者問「是否把所有破音字都換成同音不同字」):不做全面換字(會打亂詞語語境與連讀變調,
而且大多數破音字模型本來就唸對);改成每版配音後跑這支,只把「真的被唸成另一個讀音」的字加進 tts_pron.py。

作法:
  預期讀音 = 送配音的文字(tts_chattts.prep_text:發音表換字後、數字已轉中文)用 pypinyin 依詞語語境取的帶調拼音;
    發音表換過的字以換上去的字為準(那就是我們要的讀音,例:多元長 -> 掌 zhang3)。
  辨識讀音 = 辨識文字同樣用 pypinyin 取帶調拼音。
  兩邊以不帶調的模糊拼音對齊(difflib);等長的替換區段逐字配對,所以「長 -> 腸」這種聲母不同的也配得到。
  只列原字是多音字、且兩邊讀音不同的;只差輕聲的不列。
限制(判讀時要知道):
  辨識器是依語意選字,不是記音:它寫回同一個多音字時,讀音是 pypinyin 從字面猜的,沒有聲學根據(evidence=weak)。
  辨識成別的字才是比較可信的線索(evidence=strong);其中辨識讀音正好是原字的另一個讀音的
  (kind=alt)最像破音字誤讀,排最前面。strong 但 kind=other 的多半是辨識器聽錯字。最後仍要人耳確認。
"""
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402
import tts_pron  # noqa: E402
import listen_page  # noqa: E402

TOP_N = 15
_HAN = re.compile(r"[一-鿿]+")
_SAME = "著着者"   # 助詞「著」換字:只在辨識成 zhù 時才列


def toned(s):
    """字串每個位置的帶調拼音(非中文字 = None);同一段連續中文字一起取,保留詞語語境。"""
    from pypinyin import Style, pinyin
    out = [None] * len(s)
    for m in _HAN.finditer(s):
        ps = pinyin(m.group(), style=Style.TONE3, neutral_tone_with_five=True)
        if len(ps) == len(m.group()):
            for k, x in enumerate(ps):
                out[m.start() + k] = x[0]
    return out


def readings(c):
    from pypinyin import Style, pinyin
    return set(pinyin(c, style=Style.TONE3, heteronym=True, neutral_tone_with_five=True)[0])


def _key(p):
    """對齊用:去聲調、平翹舌與前後鼻音不分。"""
    return re.sub(r"ng$", "n", re.sub(r"^([zcs])h", r"\1", p[:-1]))


def scan_unit(TC, text, asr):
    """一個配音單位 -> [dict(char, said, expect, heard, heard_char, kind, evidence, pos)]。"""
    prep = TC.prep_text(text)
    saved = tts_pron.apply
    try:   # 不套發音表的同一段文字:長度相同時用來對照「原字」
        tts_pron.apply = lambda t: t
        orig = TC.prep_text(text)
    finally:
        tts_pron.apply = saved
    if len(orig) != len(prep):
        orig = prep
    hyp = TC._cc.convert(asr or "")
    exp, got = toned(prep), toned(hyp)
    ri = [i for i, p in enumerate(exp) if p]
    hi = [j for j, p in enumerate(got) if p]
    sm = difflib.SequenceMatcher(None, [_key(exp[i]) for i in ri], [_key(got[j]) for j in hi], autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if not (tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1)):
            continue
        for d in range(i2 - i1):
            i, j = ri[i1 + d], hi[j1 + d]
            e, h = exp[i], got[j]
            oc, rd = orig[i], readings(orig[i])
            if e == h or len(rd) < 2 or e[:-1] == h[:-1] and "5" in (e[-1], h[-1]):
                continue
            if oc in _SAME and not h.startswith("zhu"):
                continue
            out.append(dict(char=oc, said=prep[i], expect=e, heard=h, heard_char=hyp[j], pos=i,
                            kind="alt" if h in rd else "other",
                            evidence="weak" if hyp[j] in (oc, prep[i]) else "strong"))
    return out


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    tag = sys.argv[1]
    import tts_chattts as TC   # 只用 prep_text / _cc(會載入 torch,不載模型)
    bd = P.build_dir(tag)
    qc = json.loads((bd / "tts_qc.json").read_text(encoding="utf-8"))
    tl_lines = {}
    for name in ("timeline.json", "timeline_tts.json"):
        if (bd / name).exists():
            tl_lines = {ln["idx"]: ln for ln in json.loads((bd / name).read_text(encoding="utf-8"))["lines"]}
            break
    items = []
    for r in qc["records"]:
        t = listen_page.unit_time(tl_lines, r["idx"]) if tl_lines else None
        for it in scan_unit(TC, r["text"], r.get("asr")):
            items.append(dict(idx=r["idx"], time=listen_page.mmss(t) if t is not None else None, **it,
                              text=r["text"], asr=r.get("asr")))
    rank = lambda it: (it["evidence"] != "strong" or it["kind"] != "alt", it["kind"] != "alt", it["evidence"] != "strong")
    items.sort(key=rank)
    out = P.project_file(tag, "polyphone_report.json")
    Path(out).write_text(json.dumps(dict(
        tag=tag, qc_ver=qc.get("qc_ver"), units=len(qc["records"]), n=len(items),
        n_alt_strong=sum(1 for x in items if x["kind"] == "alt" and x["evidence"] == "strong"),
        n_alt_weak=sum(1 for x in items if x["kind"] == "alt" and x["evidence"] == "weak"),
        n_other=sum(1 for x in items if x["kind"] == "other"),
        note="alt=辨識讀音是原字的另一個讀音;strong=辨識成別的字(weak=寫回同一個字,讀音只是從字面猜的)。辨識器依語意選字,最後仍要人耳確認。",
        items=items), ensure_ascii=False, indent=1), encoding="utf-8")
    try:   # 常讀錯字累積表(alt+strong 自動 upsert;channel/_archive/plans/PLAN_流程嚴謹化_2026-10-29.md §4.3)
        import pron_backlog as PB
        PB.upsert(PB.polyphone_items({"items": items}), tag)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] pron_backlog 更新失敗: {e}")
    print(f"破音字報告 {tag}: {len(items)} 筆(alt+strong {sum(1 for x in items if x['kind'] == 'alt' and x['evidence'] == 'strong')}、"
          f"alt+weak {sum(1 for x in items if x['kind'] == 'alt' and x['evidence'] == 'weak')}、"
          f"other {sum(1 for x in items if x['kind'] == 'other')})-> {out}")
    for x in items[:TOP_N]:
        print(f"  {x['time'] or '--:--'} 單位{x['idx']} 「{x['char']}」預期 {x['expect']} 辨識 {x['heard']}({x['heard_char']})"
              f" {x['kind']}/{x['evidence']} | {x['text'][:14]}")


if __name__ == "__main__":
    main()
