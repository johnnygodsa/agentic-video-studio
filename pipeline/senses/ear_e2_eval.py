#!/usr/bin/env python3
r"""耳朵 E2 評估(PLAN_工作室v2_2026-10-31 §6.3)。
1) 留出集:ear_e2_tone 以 wav_sha1 雜湊留出的 10% 句子(不進訓練),非多音字聲調準確率、5×5 混淆矩陣、每調 P/R/F1。
2) ground truth(有檔才跑):channel/taste/ear/truth.json(另一代理建)。讀得懂的格式:
   清單或 {"items": [...]},每項含
     wav(相對 repo 根或絕對)或 tag + unit(-> build/<tag>/tts_cosy3/<unit>.wav 與 .qc.json 的 say_t);
     text(沒給就用 qc.json 的 text);pos(原文字位置,0 起)、expect(期望拼音 tone3);
     bad / label("bad"|"good"):bad = 使用者聽出唸錯的壞例,good = 已通過句。
   壞例被 flag = 命中(召回),好例被 flag = 誤報。沒有 pos/expect 的項目(吞音、逗號連讀等非聲調問題)略過並計數。
   門檻(PLAN §6.3):E2+E3 召回 ≥80%、誤報 ≤10%。
python -X utf8 pipeline/senses/ear_e2_eval.py [--truth <json>]   (tts_env_chattts 的 python)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for _p in (HERE.parent, HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import paths  # noqa: E402
import ear_e2 as E  # noqa: E402
import ear_e2_align as AL  # noqa: E402
import ear_e2_tone as T  # noqa: E402

TRUTH = paths.ROOT / "channel" / "taste" / "ear" / "truth.json"


def eval_holdout():
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
    X, y, n = T.stack(T.load_dataset(), "test")
    if not len(y):
        print("留出集是空的:先跑 ear_e2_tone.py --build-data --train")
        return None
    P = E.predict_X(X)
    pred = np.array([T.TONES[j] for j in P.argmax(1)])
    acc = float((pred == y).mean())
    cm = confusion_matrix(y, pred, labels=T.TONES)
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=T.TONES, zero_division=0)
    print(f"留出集 {n} 句、{len(y)} 字(非多音字):聲調準確率 {acc:.1%}")
    print("混淆矩陣(列 = 答案,欄 = 估計;5 = 輕聲)")
    print("      " + "".join(f"{t:>7}" for t in T.TONES))
    for t, row in zip(T.TONES, cm):
        print(f"  {t}:  " + "".join(f"{v:>7}" for v in row))
    print("  調   P      R      F1     數")
    for k, t in enumerate(T.TONES):
        print(f"  {t}   {p[k]:.3f}  {r[k]:.3f}  {f[k]:.3f}  {s[k]}")
    return {"n_sent": n, "n_char": int(len(y)), "acc": acc, "cm": cm.tolist(),
            "f1": {t: float(f[k]) for k, t in enumerate(T.TONES)}}


def _truth_items(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d.get("items", d.get("cases", [])) if isinstance(d, dict) else d


def _resolve(it):
    """truth 項目 -> (wav, text, spans);找不到回 None。"""
    if it.get("tag") and it.get("unit") is not None:
        d = E.cache_dir(it["tag"])
        stem = f"{int(it['unit']):03d}" if str(it["unit"]).isdigit() else str(it["unit"])
        if d is not None and (d / f"{stem}.qc.json").exists():
            qc = json.loads((d / f"{stem}.qc.json").read_text(encoding="utf-8"))
            text, spans = AL.from_qc(qc)
            if spans and (not it.get("text") or it["text"] == text):
                return d / f"{stem}.wav", text, spans
    if it.get("wav") and it.get("text"):
        w = Path(it["wav"])
        w = w if w.is_absolute() else paths.ROOT / w
        if w.exists():
            return w, it["text"], AL.align_wav(w, it["text"])
    return None


def eval_truth(path):
    if not Path(path).exists():
        print(f"沒有 {path}:略過 ground truth 評估")
        return None
    hit = bad_n = fa = good_n = skip = 0
    for it in _truth_items(path):
        bad = bool(it.get("bad")) or it.get("label") == "bad"
        if it.get("pos") is None or not it.get("expect"):
            skip += 1
            continue
        r = _resolve(it)
        if r is None:
            skip += 1
            continue
        wav, text, spans = r
        c = E.compare(E.analyze(wav, spans), {int(it["pos"]): it["expect"]})
        flag = bool(c and c[0]["flag"])
        if bad:
            bad_n, hit = bad_n + 1, hit + flag
        else:
            good_n, fa = good_n + 1, fa + flag
    rec = hit / bad_n if bad_n else None
    far = fa / good_n if good_n else None
    print(f"ground truth:壞例 {bad_n}(命中 {hit},召回 {rec if rec is None else f'{rec:.0%}'});"
          f"好例 {good_n}(誤報 {fa},{far if far is None else f'{far:.0%}'});略過 {skip}(非聲調問題或找不到音檔)")
    return {"recall": rec, "false_alarm": far, "bad": bad_n, "good": good_n, "skipped": skip}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", default=str(TRUTH))
    a = ap.parse_args()
    eval_holdout()
    eval_truth(a.truth)


if __name__ == "__main__":
    main()
