#!/usr/bin/env python3
r"""配音自查報告(只用 numpy):子句句界實際靜音(從最終混音前的配音軌 voice.wav 量)、語速偏差、重錄單位。

python -X utf8 pipeline/tts_report.py <tag> [--min-gap 0.10] [--top 10]   (用 run.py:python pipeline/run.py tts_report <tag>)
輸入:build/<tag>/timeline.json(要有 clauses)、build/<tag>/voice.wav、build/<tag>/tts/_jobs.qc.json。
--tts-only(--tts-review)只寫 timeline_tts.json、不產 voice.wav:timeline.json 不存在或比 timeline_tts.json 舊時改讀 timeline_tts.json,
配音軌由各行的 <句3位>.line.wav(多子句行,含句後停頓)依時間軸起點拼成(只拼有 clauses 的行,量測只需要這些)。
句界靜音 = 句界中點往兩側延伸、連續低於該行峰值 -40dB(5ms 影格)的長度。
輸出:印出摘要,完整資料寫 projects/<tag>/tts_report.json。
"""
import argparse
import json
import statistics
import wave

import numpy as np

import paths as P
import tts_pause as TP

HOP = 0.005
REL_DB = 40.0


def frame_db(x, sr):
    n = int(sr * HOP)
    m = len(x) // n
    return 10 * np.log10((x[: m * n].reshape(m, n) ** 2).mean(axis=1) + 1e-12)


def _newer(a, b):
    """a 存在且不比 b 舊(b 不存在視為 a 較新)。"""
    return a.exists() and (not b.exists() or a.stat().st_mtime >= b.stat().st_mtime)


def _read_wav(path):
    with wave.open(str(path), "rb") as w:
        return w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, 2).mean(axis=1) / 32768.0


def load_timeline_voice(tag):
    """回傳 (timeline dict, 配音軌單聲道 float, 取樣率)。完整渲染過 = timeline.json + voice.wav;只配音(--tts-only)= timeline_tts.json + 拼接。"""
    bd = P.BUILD / tag
    tlf, tts_tl, vf = bd / "timeline.json", bd / "timeline_tts.json", bd / "voice.wav"
    if _newer(tlf, tts_tl) and vf.exists() and _newer(vf, tlf):
        tl = json.loads(tlf.read_text(encoding="utf-8"))
        sr, x = _read_wav(vf)
        return tl, x, sr
    if not tts_tl.exists():
        if tlf.exists() and vf.exists():   # 沒有 timeline_tts.json:退回舊檔
            sr, x = _read_wav(vf)
            return json.loads(tlf.read_text(encoding="utf-8")), x, sr
        raise FileNotFoundError(f"{tts_tl} 與 {tlf}/{vf} 都沒有,請先跑配音(build --tts-only)")
    tl = json.loads(tts_tl.read_text(encoding="utf-8"))
    td = P.tts_dir(tag)
    sr, x = None, None
    for ln in tl["lines"]:
        if not ln.get("clauses"):
            continue
        f = td / f"{int(ln['idx']):03d}.line.wav"
        if not f.exists():
            raise FileNotFoundError(f"缺 {f}(多子句行的拼接配音),請重跑配音(build --tts-only)")
        s_r, y = _read_wav(f)
        if sr is None:
            sr = s_r
            x = np.zeros(int(round((tl.get("total") or 0) * sr)) + sr)
        off = int(round(ln["start"] * sr))
        if off + len(y) > len(x):
            x = np.concatenate([x, np.zeros(off + len(y) - len(x))])
        x[off:off + len(y)] = y
    if x is None:   # 沒有任何子句行
        sr, x = 48000, np.zeros(48000)
    return tl, x, sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--min-gap", type=float, default=0.10)
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()
    tl, x, sr = load_timeline_voice(a.tag)
    db = frame_db(x, sr)
    bounds = []
    for ln in tl["lines"]:
        cl = ln.get("clauses")
        if not cl:
            continue
        i0, i1 = int(ln["start"] / HOP), int((ln["end"] + 0.05) / HOP)
        thr = db[i0:i1].max() - REL_DB
        for k in range(len(cl) - 1):
            mid = (cl[k]["end"] + cl[k + 1]["start"]) / 2
            c = int(mid / HOP)
            l = r = c
            while l > 0 and db[l - 1] < thr:
                l -= 1
            while r < len(db) - 1 and db[r + 1] < thr:
                r += 1
            sil = (r - l + 1) * HOP if db[c] < thr else 0.0
            bounds.append(dict(line=ln["idx"], boundary=k + 1, at=round(mid, 2), configured_gap=cl[k]["gap"],
                               silence_s=round(sil, 3), after=cl[k]["text"][-8:], before=cl[k + 1]["text"][:8]))
    jq = P.tts_dir(a.tag) / "_jobs.qc.json"
    if jq.exists():
        rep = json.loads(jq.read_text(encoding="utf-8"))
    else:   # Colab 配音匯回(底線開頭的工作檔不打包)且本機全命中快取:由每單位的 .qc.json 組回
        L0 = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(P.tts_dir(a.tag).glob("**/*.qc.json"))
              if not f.name.startswith("_")]
        rep = dict(lines=L0, failed=[x_["idx"] for x_ in L0 if not x_.get("passed")])
    L = rep["lines"]
    med = statistics.median(x_["cps"] for x_ in L)
    worst = sorted(L, key=lambda x_: -abs(x_["cps"] / med - 1))
    out = dict(
        split_lines=len({b["line"] for b in bounds}), boundaries=len(bounds),
        min_silence=min((b["silence_s"] for b in bounds), default=None),
        below_min=[b for b in bounds if b["silence_s"] < a.min_gap],
        boundary_list=bounds,
        units=len(L), rate_median=round(med, 3),
        rate_out_of_range=[dict(unit=x_["idx"], dev=x_["rate_dev"], text=x_["text"]) for x_ in L if not x_["rate_ok"]],
        rate_top=[dict(unit=x_["idx"], dev=round(x_["cps"] / med - 1, 3), cps=x_["cps"], text=x_["text"]) for x_ in worst[: a.top]],
        rerecorded_for_rate=[x_["idx"] for x_ in L if x_.get("rate_retried")],
        rerecorded_units=[x_["idx"] for x_ in L if x_["source"] != "cache"],
        asr2_bad=[dict(idx=x_["idx"], text=x_["text"], asr=x_.get("asr"), asr2=x_.get("asr2"), asr2_sim=x_.get("asr2_sim"))
                  for x_ in L if x_.get("asr2_bad")],
        comma_runon=[dict(idx=x_["idx"], at=[y["at"] for y in TP.runon_from_rec(x_)]) for x_ in L if TP.runon_from_rec(x_)],
        kept_from_cache=[x_["idx"] for x_ in L if x_["source"] == "cache"],
        comma_profile=sorted({x_.get("comma_profile") or "std" for x_ in L}),
        failed_qc=rep.get("failed"))
    dst = P.PROJECTS / a.tag / "tts_report.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"拆句的行 {out['split_lines']},句界 {out['boundaries']},最小靜音 {out['min_silence']}s,低於 {a.min_gap}s: {len(out['below_min'])}")
    print(f"副辨識不一致(優先聽) {len(out['asr2_bad'])}:" + "、".join(str(x_["idx"]) for x_ in out["asr2_bad"]))
    print(f"逗號連讀(comma_runon) {len(out['comma_runon'])} 句:" + "、".join(str(x_["idx"]) for x_ in out["comma_runon"]))
    print(f"單位 {out['units']},語速中位數 {out['rate_median']},超範圍 {len(out['rate_out_of_range'])},語速重錄 {len(out['rerecorded_for_rate'])},新錄 {len(out['rerecorded_units'])},逗號側寫 {'/'.join(out['comma_profile'])}")
    print(f"報告: {dst}")


if __name__ == "__main__":
    main()
