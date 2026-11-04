#!/usr/bin/env python3
r"""耳朵 E2 聲調偵測(PLAN_工作室v2_2026-10-31 §6.3;本機 CPU、0 token):估一句配音每個字的實際聲調,與期望讀音比。
- 單句:python -X utf8 pipeline/senses/ear_e2.py --wav <f> --text <t> [--expect '{"5": "zhi2"}'] [--device cpu|cuda]
  對齊走 ear_e2_align.align_wav(tts_env_asr 子行程);--expect = {字位置(0 起、對原文): 期望拼音 tone3}(值也可是清單,任一調符合即可)。
  印 JSON:每字 {i, ch, tone, conf, probs} 與 mismatches。
- 整片:python -X utf8 pipeline/senses/ear_e2.py --tag <tag> --ver <ver>
  讀 build/<tag>/tts_cosy3(或 tts)/NNN.qc.json 的 say_t 當對齊(免跑對齊器),期望讀音 = tts_g2p.expected(規則表收的多音字位置),
  -> projects/<tag>/ear_e2_<ver>.json + 印摘要與前 15 筆不符。
不符判定:期望調 != 估計第一名,且模型給期望調的機率 < FLAG_P。聲調估計只是線索(人耳仍是最後一關,PLAN §6.3 上線門檻)。
(tts_env_chattts 的 python;模型 tts_models/ear_e2_tone.pkl 由 ear_e2_tone.py --train 產生)
"""
import argparse
import json
import pickle
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for _p in (HERE.parent, HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import paths  # noqa: E402
import ear_e2_align as AL  # noqa: E402
import ear_e2_tone as T  # noqa: E402

FLAG_P = 0.2
_MODEL = []


def load_model(path=None):
    if not _MODEL:
        p = Path(path or T.MODEL)
        if not p.exists():
            sys.exit(f"沒有模型 {p}:先跑 ear_e2_tone.py --build-data --train")
        m = pickle.loads(p.read_bytes())
        if m.get("feat_ver") != T.FEAT_VER:
            sys.exit(f"模型特徵版本 {m.get('feat_ver')} != {T.FEAT_VER}:重跑 ear_e2_tone.py --train")
        _MODEL.append(m)
    return _MODEL[0]


def predict_X(X, model=None):
    """特徵矩陣 -> 機率矩陣 [n, 5](欄序 = T.TONES)。"""
    clf = (model or load_model())["clf"]
    if not len(X):
        return np.zeros((0, len(T.TONES)))
    pr = clf.predict_proba(X)
    out = np.zeros((len(X), len(T.TONES)))
    for j, c in enumerate(clf.classes_):
        out[:, T.TONES.index(str(c))] = pr[:, j]
    return out


def analyze(wav, spans, model=None):
    """音檔 + [(字, 起, 迄)] -> 每個有時間的漢字 {i, ch, tone, conf, probs}。"""
    idx, X = T.features(T.load_audio(wav), spans)
    P = predict_X(X, model)
    rows = []
    for k, i in enumerate(idx):
        j = int(P[k].argmax())
        rows.append({"i": i, "ch": spans[i][0], "tone": T.TONES[j], "conf": round(float(P[k, j]), 3),
                     "probs": {t: round(float(P[k, m]), 3) for m, t in enumerate(T.TONES)}})
    return rows


def _exp_tones(v):
    vs = v if isinstance(v, (list, tuple)) else [v]
    return {T.tone_of(str(x)) for x in vs if x}


def compare(rows, expect):
    """rows + {位置: 期望拼音} -> 每個期望位置的比對結果(含 flag)。位置對不到時間的記 tone=None。"""
    by = {r["i"]: r for r in rows}
    out = []
    for pos, py in sorted(((int(k), v) for k, v in (expect or {}).items()), key=lambda kv: kv[0]):
        exp = _exp_tones(py)
        r = by.get(pos)
        if r is None:
            out.append({"pos": pos, "expect": py, "tone": None, "flag": False, "note": "無對齊時間"})
            continue
        p_exp = max(r["probs"].get(t, 0.0) for t in exp) if exp else 0.0
        out.append({"pos": pos, "ch": r["ch"], "expect": py, "tone": r["tone"], "conf": r["conf"],
                    "p_expect": round(p_exp, 3), "flag": r["tone"] not in exp and p_exp < FLAG_P})
    return out


def cache_dir(tag):
    for sub in T.CACHE_DIRS:
        d = paths.BUILD / tag / sub
        if d.is_dir() and any(d.glob("*.qc.json")):
            return d
    return None


def run_tag(tag, ver):
    import tts_g2p
    d = cache_dir(tag)
    if d is None:
        sys.exit(f"build/{tag} 沒有配音快取")
    model = load_model()
    units, skipped = [], []
    for q in sorted(d.glob("*.qc.json"), key=lambda p: p.name):
        stem = q.name[:-len(".qc.json")]
        if not re.fullmatch(r"\d+(_\d+)?", stem):
            continue
        qc = json.loads(q.read_text(encoding="utf-8"))
        text, spans = AL.from_qc(qc)
        wav = q.with_name(f"{stem}.wav")
        if not spans or not wav.exists():
            skipped.append(stem)
            continue
        exp = {p: rd for p, (ch, rd, src) in tts_g2p.expected(text).items()}
        rows = analyze(wav, spans, model)
        cmp_ = compare(rows, exp)
        units.append({"unit": stem, "text": text, "passed": bool(qc.get("passed")),
                      "tones": "".join(r["tone"] for r in rows), "poly": cmp_})
    flags = [(u["unit"], u["text"], c) for u in units for c in u["poly"] if c["flag"]]
    out = {"tag": tag, "ver": ver, "cache": d.relative_to(paths.ROOT).as_posix(), "flag_p": FLAG_P,
           "model": {k: load_model()[k] for k in ("n_sent", "n_char", "trained")},
           "units": len(units), "skipped": skipped, "poly_positions": sum(len(u["poly"]) for u in units),
           "mismatches": len(flags), "items": units}
    dst = paths.PROJECTS / tag / f"ear_e2_{ver}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{tag} {ver}:{len(units)} 句(略過 {len(skipped)}),多音字位置 {out['poly_positions']},不符 {len(flags)} -> {dst}")
    for unit, text, c in sorted(flags, key=lambda f: f[2]["p_expect"])[:15]:
        ctx = text[max(0, c["pos"] - 4):c["pos"] + 5]
        print(f"  {unit} 「{ctx}」 {c['ch']} 期望 {c['expect']} 估 {c['tone']} 聲 (信心 {c['conf']},期望調機率 {c['p_expect']})")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav")
    ap.add_argument("--text")
    ap.add_argument("--expect", help='JSON {"位置": "tone3 拼音"}')
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    ap.add_argument("--tag")
    ap.add_argument("--ver", default="cur")
    a = ap.parse_args()
    if a.tag:
        run_tag(a.tag, a.ver)
    elif a.wav and a.text:
        spans = AL.align_wav(a.wav, a.text, a.device)
        rows = analyze(a.wav, spans)
        res = {"text": a.text, "tones": rows}
        if a.expect:
            res["compare"] = compare(rows, json.loads(a.expect))
            res["mismatches"] = [c for c in res["compare"] if c["flag"]]
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
