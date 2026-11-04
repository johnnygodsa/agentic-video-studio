#!/usr/bin/env python3
r"""科普頻道音色試聽:從 chattts_speaker\evaluation_results.csv 挑青年/少年感候選,各合成三句,做試聽網頁。
可重跑:python -X utf8 pipeline\sci\voice_audition.py  (已合成的音色會沿用,--force 全部重做)
  產出:chattts_speaker\candidates\<M|F>_seed_<id>.pt、output\channel\voice_audition.html、
        output\channel\voice_audition_audio\*.mp3、tmp\voice_audition\(合成中間檔與品管報告)
挑選:性別標籤單一方 >= 90%、年齡主標籤;依 rank_long/rank_multi/rank_single 平均高者優先;排除現行兩個定案音色。
自動改用 tts_env_chattts 的 python 執行(要 torch / soundfile)。不印、不存 emb_data 以外的內容到螢幕。
"""
import csv
import html
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gpu_lock as GL  # noqa: E402
import paths  # noqa: E402

if Path(sys.executable).resolve() != Path(paths.TTS_ENV).resolve() and not os.environ.get("VA_CHILD"):
    sys.exit(subprocess.call([str(paths.TTS_ENV), "-X", "utf8", __file__] + sys.argv[1:], env={**os.environ, "VA_CHILD": "1"}))

import base64  # noqa: E402
import io  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402

CSV = paths.ROOT / "chattts_speaker" / "evaluation_results.csv"
CAND = paths.ROOT / "chattts_speaker" / "candidates"
WORK = paths.TMP / "voice_audition"
OUT = paths.OUTPUT / "channel"
AUDIO = OUT / "voice_audition_audio"
TTS = paths.ROOT / "pipeline" / "tts_chattts.py"
CUR = [("M", 402, "現行-男聲"), ("F", 2456, "現行-女聲")]
SENT = ["你有沒有想過一件很蠢的事?",
        "長到一半,它決定掉頭往上,朝太陽的方向彎過去。",
        ["這對你的人生有幫助嗎?", "一點幫助都沒有。"]]  # 第三句拆兩個合成單位,以 0.20 秒停頓接起來
GAP = 0.20
SR = 24000
RATE = "+18%"
# (組名, 性別, 年齡標籤優先序, 數量)
GROUPS = [("男青年", "男", ["青年"], 4), ("女青年", "女", ["青年"], 4),
          ("男少年", "男", ["少年", "少儿"], 2), ("女少年", "女", ["少年", "少儿"], 2)]


def top(s):
    d = {}
    for p in (s or "").split(";"):
        if ":" in p:
            k, v = p.split(":")
            d[k.strip()] = float(v)
    return max(d.items(), key=lambda x: x[1]) if d else (None, 0.0)


def load_rows():
    csv.field_size_limit(10**7)
    rows = []
    with open(CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            r["g"], r["gp"] = top(r["gender"])
            r["a"], r["ap"] = top(r["age"])
            r["stab"] = sum(float(r[k]) for k in ("rank_long", "rank_multi", "rank_single")) / 3
            rows.append(r)
    return rows


def emb_tensor(row):
    return torch.load(io.BytesIO(base64.b64decode(row["emb_data"])), map_location="cpu", weights_only=True).float()


def pick(rows):
    excl = {f"seed_{c[1]}" for c in CUR}
    chosen = []  # (code, group, row)
    for gname, g, ages, n in GROUPS:
        pool = [r for r in rows if r["g"] == g and r["gp"] >= 90 and r["seed_id"] not in excl]
        if gname.endswith("青年"):
            pool = [r for r in pool if r["a"] == "青年" and r["ap"] >= 90]
        else:
            pool = [r for r in pool if r["a"] in ages and r["ap"] >= 90]
            pool.sort(key=lambda r: (ages.index(r["a"]), -r["stab"]))  # 少年優先於少儿,同標籤依穩定度
        if gname.endswith("青年"):
            pool.sort(key=lambda r: -r["stab"])
        for i, r in enumerate(pool[:n], 1):
            chosen.append((f"{'M' if g == '男' else 'F'}-{gname[1:]}-{i}", gname, r))
    return chosen


def synth_voice(code, pt, force):
    """回傳 dict(f0s, passed, total, secs);音檔 wav 放 WORK\\<code>\\"""
    d = WORK / code
    d.mkdir(parents=True, exist_ok=True)
    units = [SENT[0], SENT[1], *SENT[2]]
    jobs = [dict(text=t, out=str(d / f"u{i}.wav"), idx=i) for i, t in enumerate(units)]
    rep = d / "report.json"
    if force or not rep.exists() or any(not Path(j["out"]).exists() for j in jobs):
        (d / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        subprocess.run([str(paths.TTS_ENV), "-X", "utf8", str(TTS), str(d / "jobs.json"), "--spk-pt", str(pt),
                        "--rate", RATE, "--report", str(rep), "--max-retry", "2", "--rate-seeds", "0"],
                       check=True, stderr=open(d / "log.txt", "w", encoding="utf-8"))
    lines = json.loads(rep.read_text(encoding="utf-8"))["lines"]
    return d, lines


def to_mp3(wav, mp3):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-b:a", "64k", str(mp3)], check=True)


def build_audio(code, d):
    w = lambda i: sf.read(str(d / f"u{i}.wav"))[0].astype(np.float32)
    parts = [w(0), w(1), np.concatenate([w(2), np.zeros(int(GAP * SR), np.float32), w(3)])]
    secs = []
    for k, p in enumerate(parts, 1):
        tmp = d / f"s{k}.wav"
        sf.write(str(tmp), p, SR)
        to_mp3(tmp, AUDIO / f"{code}_{k}.mp3")
        secs.append(len(p) / SR)
    return secs


PAGE = """<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>科普頻道音色試聽</title>
<style>
body{background:#14161c;color:#e8e8e8;font:22px/1.5 "Microsoft JhengHei",sans-serif;margin:0;padding:24px 32px}
h1{font-size:34px;margin:0 0 6px}p.n{color:#9aa;font-size:19px;margin:0 0 18px}
h2{font-size:26px;margin:28px 0 8px;color:#f5c542;border-bottom:1px solid #333;padding-bottom:4px}
table{border-collapse:collapse;width:100%}td{padding:10px 12px;border-bottom:1px solid #2a2d36;vertical-align:middle}
td.c{font-size:26px;font-weight:bold;white-space:nowrap}td.m{color:#aab;font-size:18px}
tr.cur{background:#1f2a1f}.tag{background:#f5c542;color:#000;border-radius:6px;padding:2px 8px;font-size:17px;margin-left:8px}
button{background:#2b3a55;color:#fff;border:0;border-radius:8px;font-size:21px;padding:12px 20px;margin:2px 6px 2px 0;cursor:pointer}
button:hover{background:#3d5380}button.on{background:#c0392b}
.s{color:#9aa;font-size:16px;display:block;margin-top:2px}
</style>
<h1>科普頻道音色試聽</h1>
<p class="n">每個音色三句(語速 +18%)。1:@S1@　2:@S2@　3:@S3@<br>音高為成品平均 f0;品管為三句(共四個合成單位)通過數,未必重錄到過,請以耳朵為準。</p>
@BODY@
<audio id="a"></audio>
<script>
const a=document.getElementById('a');let cur=null;
function p(b,f){if(cur){cur.classList.remove('on')}if(cur===b&&!a.paused){a.pause();cur=null;return}
a.src=f;a.play();b.classList.add('on');cur=b;a.onended=()=>{b.classList.remove('on');cur=null}}
</script></html>
"""


def page(rowsinfo):
    body, last = [], None
    for it in rowsinfo:
        if it["group"] != last:
            if last is not None:
                body.append("</table>")
            body.append(f"<h2>{html.escape(it['group'])}</h2><table>")
            last = it["group"]
        btns = "".join(f"<button onclick=\"p(this,'voice_audition_audio/{it['code']}_{k}.mp3')\">▶ 第{k}句"
                       f" <span class='s'>{it['secs'][k - 1]:.1f} 秒</span></button>" for k in (1, 2, 3))
        tag = "<span class='tag'>現行</span>" if it["cur"] else ""
        body.append(f"<tr class='{'cur' if it['cur'] else ''}'><td class='c'>{html.escape(it['code'])}{tag}</td>"
                    f"<td class='m'>seed {it['seed']}<br>{html.escape(it['meta'])}<br>{html.escape(it['qc'])}</td><td>{btns}</td></tr>")
    body.append("</table>")
    s = [SENT[0], SENT[1], "".join(SENT[2])]
    return (PAGE.replace("@BODY@", "\n".join(body)).replace("@S1@", html.escape(s[0]))
            .replace("@S2@", html.escape(s[1])).replace("@S3@", html.escape(s[2])))


def main():
    force = "--force" in sys.argv
    rows = load_rows()
    byid = {r["seed_id"]: r for r in rows}
    # 1 驗證 csv 解碼 = 現行 pt
    for g, sid, _ in CUR:
        pt = torch.load(paths.SPEAKERS / f"{g}_seed_{sid}.pt", map_location="cpu", weights_only=True).float()
        same = torch.equal(emb_tensor(byid[f"seed_{sid}"]), pt)
        print(f"csv seed_{sid} == {g}_seed_{sid}.pt: {same}")
        if not same:
            sys.exit("csv 與現行音色檔對不上,停止")
    # 2 挑候選
    chosen = pick(rows)
    CAND.mkdir(parents=True, exist_ok=True)
    AUDIO.mkdir(parents=True, exist_ok=True)
    items = []
    for g, sid, label in CUR:
        r = byid[f"seed_{sid}"]
        items.append(dict(code=label, group="現行定案(對照)", seed=sid, row=r, pt=paths.SPEAKERS / f"{g}_seed_{sid}.pt", cur=True))
    for code, gname, r in chosen:
        sid = int(r["seed_id"].split("_")[1])
        pt = CAND / f"{code[0]}_seed_{sid}.pt"
        if not pt.exists():
            torch.save(emb_tensor(r), pt)
        items.append(dict(code=code, group=gname, seed=sid, row=r, pt=pt, cur=False))
    print("候選:", [(i["code"], i["seed"]) for i in items if not i["cur"]])
    # 3 排隊拿全機 GPU 鎖(gpu_lock.py,含顯存 <= 3000 MiB)
    glock = GL.gpu_lock("voice_audition", "voice_audition").acquire()
    # 4 合成
    total_secs, info = 0.0, []
    for n, it in enumerate(items, 1):
        d, lines = synth_voice(it["code"], it["pt"], force)
        secs = build_audio(it["code"], d)
        total_secs += sum(secs)
        f0s = [l["f0"] for l in lines if l.get("f0")]
        npass = sum(1 for l in lines if l["passed"])
        r = it["row"]
        qc = f"品管 {npass}/{len(lines)} 單位通過;f0 平均 {np.mean(f0s):.0f} Hz" if f0s else f"品管 {npass}/{len(lines)}"
        info.append(dict(code=it["code"], group=it["group"], seed=it["seed"], cur=it["cur"], secs=secs, qc=qc,
                         meta=f"性別 {r['gender']}｜年齡 {r['age']}｜特色 {r['feature']}", npass=npass, nunit=len(lines),
                         f0=float(np.mean(f0s)) if f0s else 0.0, failed=[l["text"] for l in lines if not l["passed"]]))
        print(f"[{n}/{len(items)}] {it['code']} seed{it['seed']} {qc}", flush=True)
    glock.release()
    (OUT / "voice_audition.html").write_text(page(info), encoding="utf-8")
    (WORK / "summary.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成:{len(info)} 個音色,音檔合計 {total_secs:.0f} 秒 -> {OUT / 'voice_audition.html'}")


if __name__ == "__main__":
    main()
