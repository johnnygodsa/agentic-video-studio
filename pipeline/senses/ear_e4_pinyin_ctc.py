"""E4 本機拼音級 ASR 耳朵:wav2vec2 CTC 直接輸出「聲母 + 帶調韻母」(無語言模型,不會被字面拉回正確讀音),
再用 ear_e3_blind.compare 與參考文字的 pypinyin 對齊,抓同字異音、聲調、多唸漏唸、停頓(用 CTC 幀時間的空白段)。
模型:snu-nia-12/wav2vec2-large-xlsr-53_nia12_phone-pinyin_chinese(HF,詞表 218:聲母、帶調韻母、y 開頭整音節、u: = ü)
放 tts_models\\ear_e4_pinyin_ctc\\(不進 git)。0 token、本機 GPU 或 CPU 都能跑(1.2 GB 模型,顯存約 2 GB)。

用法
  python -X utf8 pipeline\\senses\\ear_e4_pinyin_ctc.py --wav f.wav --text "參考文字"
  python -X utf8 pipeline\\senses\\ear_e4_pinyin_ctc.py --truth channel\\taste\\ear\\truth.json --out tmp\\ear_e4.json [--rescore]
快取:tmp\\ear_e4_cache.json 以 wav sha1 為鍵存轉寫(音節、起訖時間);--rescore 只重算評分。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402
from senses import ear_e3_blind as blind  # noqa: E402
from senses import ear_e3_gemini as g  # noqa: E402

MODEL_DIR = paths.ROOT / "tts_models" / "ear_e4_pinyin_ctc"
FRAME_SEC = 0.02  # wav2vec2 每幀 20 ms
PAUSE_MIN = 0.1

_model = None
_proc = None


def load_model(device=None):
    global _model, _proc
    if _model is None:
        import torch
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        _proc = Wav2Vec2Processor.from_pretrained(str(MODEL_DIR))
        _model = Wav2Vec2ForCTC.from_pretrained(str(MODEL_DIR)).eval()
        dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
        _model.to(dev)
    return _model, _proc


def load_audio(path, sr=16000):
    import librosa
    y, _ = librosa.load(str(path), sr=sr, mono=True)
    return y


def norm_syl(s):
    return (s or "").lower().replace("u:", "v").replace("ü", "v")


def ctc_decode(ids, blank_id, vocab_inv):
    """CTC 貪婪解碼 -> [(token, start_frame, end_frame)](合併重複、去空白)。"""
    out = []
    prev = None
    start = 0
    for f, i in enumerate(ids):
        if i != prev:
            if prev is not None and prev != blank_id:
                out.append((vocab_inv[prev], start, f))
            start = f
            prev = i
    if prev is not None and prev != blank_id:
        out.append((vocab_inv[prev], start, len(ids)))
    return out


def tokens_to_syllables(toks):
    """聲母 + 韻母 token 串 -> [{pinyin, start, end}];落單聲母記 orphan。"""
    syls, orphans = [], []
    pend = None
    for tok, s, e in toks:
        if re.search(r"\d$", tok) or tok in ("a",) or tok.startswith(("y",)) and tok != "y":
            if tok == "a":
                tok = "a5"
            py = norm_syl((pend[0] if pend else "") + tok)
            syls.append(dict(pinyin=py, start=(pend[1] if pend else s), end=e))
            pend = None
        else:
            if pend:
                orphans.append(dict(token=pend[0], start=pend[1]))
            pend = (tok, s)
    if pend:
        orphans.append(dict(token=pend[0], start=pend[1]))
    return syls, orphans


def transcribe(wav):
    import torch
    model, proc = load_model()
    y = load_audio(wav)
    inputs = proc(y, sampling_rate=16000, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values.to(model.device)).logits[0]
    probs = torch.softmax(logits.float(), dim=-1)
    ids = logits.argmax(-1).tolist()
    vocab_inv = {v: k for k, v in proc.tokenizer.get_vocab().items()}
    blank = proc.tokenizer.pad_token_id
    toks = ctc_decode(ids, blank, vocab_inv)
    # 每個 token 的平均信心(用來標 unclear)
    conf = []
    for tok, s, e in toks:
        conf.append(float(probs[s:e].max(-1).values.mean()) if e > s else 0.0)
    syls, orphans = tokens_to_syllables(toks)
    # 停頓:相鄰音節之間的幀距
    pauses = []
    for k in range(1, len(syls)):
        gap = (syls[k]["start"] - syls[k - 1]["end"]) * FRAME_SEC
        if gap >= PAUSE_MIN:
            pauses.append(dict(after_index=k - 1, sec=round(gap, 2)))
    return dict(syllables=syls, orphans=orphans, pauses=pauses, tok_conf=[round(c, 3) for c in conf],
                n_frames=len(ids), tokens=[t for t, _, _ in toks])


def to_blind(rec):
    """轉成 ear_e3_blind.compare 吃的格式(char 用佔位中文字)。"""
    return dict(transcript=" ".join(s["pinyin"] for s in rec["syllables"]),
                syllables=[dict(char="字", pinyin=s["pinyin"]) for s in rec["syllables"]],
                pauses=rec["pauses"], unclear=[])


def analyze(wav, text, cache=None, rescore=False):
    key = g.sha1_of(wav)
    if cache is not None and key in cache:
        rec = cache[key]
    elif rescore:
        return None
    else:
        rec = transcribe(wav)
        if cache is not None:
            cache[key] = rec
    cmp = blind.compare(text, to_blind(rec))
    cmp["pinyin"] = rec["syllables"] and " ".join(s["pinyin"] for s in rec["syllables"])
    return cmp


def run_truth(args):
    cache_p = paths.ROOT / "tmp" / "ear_e4_cache.json"
    cache = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.exists() else {}
    rows = json.loads(Path(paths.find(args.truth)).read_text(encoding="utf-8"))
    rows = rows.get("items", rows) if isinstance(rows, dict) else rows
    out = []
    for tr in rows:
        wav = tr.get("audio") or tr.get("wav")
        wav = paths.find(wav) if wav else None
        if not wav or not Path(wav).exists():
            continue
        cmp = analyze(wav, tr.get("text") or "", cache, args.rescore)
        if cmp is None:
            continue
        strict, loose = blind.truth_hit(tr, cmp, tr) if tr.get("kind") == "bad" else (None, None)
        out.append(dict(id=tr.get("id"), kind=tr.get("kind"), issue=tr.get("issue"), char=tr.get("char"), pos=tr.get("pos"),
                        flags=cmp["flags"], hit=strict, hit_loose=loose, issues=cmp["issues"], pinyin=cmp["pinyin"]))
        mark = ("命中" if strict else "寬鬆" if loose else "漏抓") if tr.get("kind") == "bad" else ("誤報" if cmp["flags"] else "OK")
        print(f"[{tr.get('id')}] {mark} {','.join(cmp['flags'])}  {tr.get('issue') or ''}", flush=True)
    cache_p.parent.mkdir(parents=True, exist_ok=True)
    cache_p.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    stats = blind.score(out)
    if args.out:
        g.save_json(paths.find(args.out), dict(stats=stats, model="wav2vec2-pinyin-ctc", items=out))
    blind.print_stats(stats)


# ------------------------------------------------------------ 生產用:窄而準的旗標(多音字位置、的/得輕聲、逗號停頓)
import difflib  # noqa: E402

from pypinyin import Style, pinyin  # noqa: E402

PARTICLES = {"的": "de5", "得": "de5"}


def _base(p):
    return blind.split_py(norm_syl(p))[0]


def _fuzzy(b):
    """台灣國語口音不算讀錯:捲舌/平舌(zh/z、ch/c、sh/s)、eng/en、ing/in、f/h 不分。只用在 poly/garble 比對。"""
    b = re.sub(r"^(zh|ch|sh)", lambda m: m.group(1)[0], b)
    b = re.sub(r"(eng|ing)$", lambda m: m.group(1)[:-1], b)
    return b


def _readings(ch):
    return {_base(r) for r in pinyin(ch, style=Style.TONE3, heteronym=True, neutral_tone_with_five=True)[0]}


def align_heard(text, heard):
    """參考文字位置 -> 聽到的音節(只取一對一對齊的部分)。"""
    ref = blind.ref_tokens(text)
    a = [blind.split_py(p)[0] for _, _, p in ref]
    b = [blind.split_py(p)[0] for p in heard]
    m = {}
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            for d in range(i2 - i1):
                m[ref[i1 + d][0]] = heard[j1 + d]
    return m


def targeted_flags(text, rec):
    """真值實測(2026-10-31):多音字位置誤報 4.7%(句級)、的/得輕聲 95% 穩、逗號停頓 runon 誤報 1%。
    -> [{kind: poly|garble|particle|runon, pos, char, expected, heard}]"""
    heard = [norm_syl(s["pinyin"]) for s in rec["syllables"]]
    m = align_heard(text, heard)
    out = []
    spec = {int(e["pos"]): norm_syl(str(e["pinyin"])) for e in g.auto_expect(text)}
    for pos, exp in spec.items():
        h = m.get(pos)
        if not h or _fuzzy(_base(h)) == _fuzzy(_base(exp)):
            continue
        kind = "poly" if _fuzzy(_base(h)) in {_fuzzy(r) for r in _readings(text[pos])} else "garble"
        out.append(dict(kind=kind, pos=pos, char=text[pos], expected=exp, heard=h))
    for pos, ch in enumerate(text):
        if ch in PARTICLES and pos not in spec:
            h = m.get(pos)
            if h and h != PARTICLES[ch] and _base(h) in ("de", "di", "dei"):
                out.append(dict(kind="particle", pos=pos, char=ch, expected=PARTICLES[ch], heard=h))
    cmp = blind.compare(text, to_blind(rec))
    out += [dict(kind="runon", pos=i["ref_pos"], char=i["ref_char"], expected="pause", heard="") for i in cmp["issues"] if i["kind"] == "runon"]
    return out


def run_tag(args):
    tag, ver = args.tag, args.ver or "v1"
    out_p = paths.PROJECTS / tag / f"ear_e4_{ver}.json"
    data = json.loads(out_p.read_text(encoding="utf-8")) if out_p.exists() and not args.redo else dict(meta=dict(tag=tag, ver=ver), results={})
    want = set(g.parse_lines(args.lines)) if args.lines else None
    flagged = 0
    for idx, text in g.tag_lines(tag):
        if want and idx not in want:
            continue
        wav = g.line_wav(tag, idx)
        if wav is None:
            continue
        sha = g.sha1_of(wav)
        old = data["results"].get(str(idx))
        if old and old.get("wav_sha1") == sha and not args.redo:
            flagged += bool(old["flags"])
            continue
        rec = transcribe(wav)
        fl = targeted_flags(text, rec)
        data["results"][str(idx)] = dict(idx=idx, text=text, wav=str(wav.relative_to(paths.ROOT)), wav_sha1=sha, flags=fl,
                                         pinyin=" ".join(s["pinyin"] for s in rec["syllables"]))
        flagged += bool(fl)
        if fl:
            print(f"句 {idx:3d}: " + "; ".join(f"{f['kind']}:{f['char']}({f['expected']}→{f['heard']})" if f['kind'] != 'runon' else f"runon:{f['char']}後沒停" for f in fl))
    g.save_json(out_p, data)
    n = len(data["results"])
    print(f"完成:{n} 句,{flagged} 句有旗標 -> {out_p}")
    md = [f"# E4 耳朵 {tag} {ver}(多音字位置/的得輕聲/逗號停頓;旗標 = 必聽與重錄候選,不自動擋)", "",
          f"- 句數 {n},有旗標 {flagged}", ""]
    for k in sorted(data["results"], key=int):
        r = data["results"][k]
        if r["flags"]:
            md.append(f"- 句 {k}:" + ";".join(f"{f['kind']} {f['char']} 期望 {f['expected']} 聽到 {f['heard'] or '無停頓'}" for f in r["flags"]) + f"  ‖ {r['text'][:40]}")
    out_p.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth")
    ap.add_argument("--out")
    ap.add_argument("--wav")
    ap.add_argument("--text", default="")
    ap.add_argument("--tag")
    ap.add_argument("--ver")
    ap.add_argument("--lines", help="例 1-3,7")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--rescore", action="store_true")
    args = ap.parse_args(argv)
    if args.truth:
        run_truth(args)
        return 0
    if args.tag:
        run_tag(args)
        return 0
    cmp = analyze(paths.find(args.wav), args.text)
    print(json.dumps(cmp, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
