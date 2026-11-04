#!/usr/bin/env python3
r"""一次性遷移:把 build/<tag>/tts 的配音快取鍵從舊格式(含 --tts-cmd 全文與絕對路徑)改成不含路徑的新格式(tts_key.py)。
音檔本身(NNN.wav / NNN.trim.wav)完全不動,只改 NNN.key、NNN.qc.json 的 key 欄、NNN.trim.key、_qc_base.json 的 voice 欄,
以及 build/<tag>/tts_qc.json 各紀錄的 key 欄。

python pipeline/migrate_tts_keys.py --tag re9 --voice seed2456 --rate +18% --engine chattts \
       --old-cmd "<舊的 --tts-cmd 全文>" --new-cmd "<直譯器> pipeline/tts_chattts.py --spk-pt <音色檔>" [--script re9/script.json] [--apply]

做法:依文案逐句算出舊鍵與新鍵;每一句都必須「NNN.key == 舊鍵、qc.json 的 key == 舊鍵、wav_sha1 == 音檔實際雜湊」才算可遷移。
只要有一句不符就整批不動並列出原因。不加 --apply 只檢查。遷移前請先備份整個 tts 目錄與 tts_qc.json。
已是新格式的句子(重跑時)視為完成,略過。
"""
import argparse
import hashlib
import json
import os
import shlex
import sys

import paths as P
import tts_key as TK
from tts_tail import QC_VER, TRIM_VER


def file_sha1(p):
    return hashlib.sha1(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--script")
    ap.add_argument("--engine", default="chattts")
    ap.add_argument("--voice", required=True)
    ap.add_argument("--rate", required=True)
    ap.add_argument("--old-cmd", required=True, help="舊快取鍵裡的 --tts-cmd 全文(一字不差)")
    ap.add_argument("--new-cmd", required=True, help="新的合成指令(只取其中的參數簽章,路徑只留檔名)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")

    bdir = P.build_dir(a.tag)
    tts = bdir / "tts"
    data = json.loads(P.find(a.script or f"{a.tag}/script.json", P.REPO).read_text(encoding="utf-8"))
    says = [ln.get("say") or ln["text"] for sec in data["sections"] for ln in sec["lines"]]
    sig = TK.cmd_sig(shlex.split(a.new_cmd, posix=False))
    print(f"目錄: {tts}\n句數: {len(says)};引擎參數簽章: {sig!r};品管版本: {QC_VER}")

    plan, done, bad = [], 0, []
    for idx, say in enumerate(says, 1):
        wav, keyf, qf, tkf = (tts / f"{idx:03d}{suf}" for suf in (".wav", ".key", ".qc.json", ".trim.key"))
        old = TK.legacy_key(a.engine, a.old_cmd, a.voice, a.rate, say)
        new = TK.full_key(TK.audio_key(a.engine, sig, a.voice, a.rate, say), QC_VER)
        if not (wav.exists() and keyf.exists() and qf.exists()):
            bad.append((idx, "缺 wav / key / qc.json"))
            continue
        cur, rec, sha = keyf.read_text(), json.loads(qf.read_text(encoding="utf-8")), file_sha1(wav)
        if rec.get("wav_sha1") != sha:
            bad.append((idx, "qc.json 的 wav_sha1 與音檔不符"))
        elif cur == new and rec.get("key") == new:
            done += 1
        elif cur != old:
            bad.append((idx, ".key 不是預期的舊鍵(文字或參數與錄音時不同)"))
        elif rec.get("key") != old or rec.get("qc_ver") != QC_VER:
            bad.append((idx, "qc.json 的 key / qc_ver 不是預期值"))
        else:
            final = bool(rec.get("final"))
            trim_new = None  # 裁切鍵:舊值正確才換成新值(.trim.wav 不重轉);不正確就留著,build 會自己重轉
            if tkf.exists() and tkf.read_text() == TK.legacy_trim_key(old, sha, TRIM_VER, final):
                trim_new = TK.trim_key(new, sha, TRIM_VER, final)
            plan.append((idx, keyf, qf, tkf, rec, new, trim_new))
    print(f"可遷移 {len(plan)} 句;已是新格式 {done} 句;不符 {len(bad)} 句"
          f";其中裁切鍵一併換新 {sum(1 for p in plan if p[6])} 句")
    for idx, why in bad:
        print(f"  句{idx}: {why}")
    if bad:
        sys.exit("有不符的句子,整批不動")
    if not a.apply:
        print("(只檢查;加 --apply 才寫入)")
        return

    newkeys = {}
    for idx, keyf, qf, tkf, rec, new, trim_new in plan:
        rec["key"] = new
        qf.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        if trim_new:
            tkf.write_text(trim_new)
        keyf.write_text(new)  # 最後才換 .key:中途中斷時這一句仍是完整的舊格式,重跑可接續
        newkeys[idx] = new
    bf = tts / "_qc_base.json"
    if bf.exists():
        b = json.loads(bf.read_text(encoding="utf-8"))
        if b.get("voice"):
            b["voice"] = os.path.basename(b["voice"].replace("\\", "/"))
            bf.write_text(json.dumps(b, indent=1), encoding="utf-8")
    rf = bdir / "tts_qc.json"
    if rf.exists():
        rep = json.loads(rf.read_text(encoding="utf-8"))
        for r in rep.get("records", []):
            if r.get("idx") in newkeys:
                r["key"] = newkeys[r["idx"]]
        rf.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已遷移 {len(plan)} 句(音檔未動)")


if __name__ == "__main__":
    main()
