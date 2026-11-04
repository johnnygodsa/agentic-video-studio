r"""配音引擎比武 IndexTTS2 vs CosyVoice3(channel/_archive/plans/PLAN_工具升級_2026-10-26.md T1)、BreezyVoice vs CosyVoice3(2026-11-04,--suite breezy)。
tts_env_chattts 的 python 執行(run.py 會選對):

  python pipeline\run.py tts_bakeoff/cli probe   [--n 8] [--no-fp16] [--dry-run]     第 1 步:IndexTTS2 冷啟顯存與每句秒數;
         峰值 > 3500 MiB 或不穩定(合成失敗/子行程中止)-> 寫 report.md 結案紀錄、結束碼 3,不往下做
         [--from-json 檔]  改讀外部 probe 結果(本機 indextts2_probe.py 的輸出,鍵見 import_probe)判定
  python pipeline\run.py tts_bakeoff/cli corpus  [--tags a,b,..] [--per-tag 60] [--dry-run]   第 2 步:語料 corpus.jsonl
  python pipeline\run.py tts_bakeoff/cli synth --engine cosy3      [--dry-run]           第 3 步:兩引擎各合成一遍(單次,seed 固定)
  python pipeline\run.py tts_bakeoff/cli synth --engine indextts2  [--dry-run]
  python pipeline\run.py tts_bakeoff/cli synth --engine indextts2 --dur [--dur-source cosy|prod]   時長控制:目標 = CosyVoice 同句時長
  python pipeline\run.py tts_bakeoff/cli judge   [--engine all] [--metrics-only] [--dry-run]   現有品管鏈 + 指標 -> metrics.json
  python pipeline\run.py tts_bakeoff/cli report                                        report.md + listen.md
工作檔全部在 tmp\tts_bakeoff\(--work 可改),不寫 build\ 快取;用顯示卡的步驟(probe/synth/judge)先排全機 gpu_lock。

BreezyVoice 比武(2026-11-04;三組 cosy3 / breezy / breezy_ann;工作目錄 --suite breezy = tmp\tts_bakeoff\breezy_2026-11-04\,不蓋舊 IndexTTS2 結果):
  python pipeline\run.py tts_bakeoff/cli --suite breezy corpus --focus hard [--size 80] [--tags a,b,..] [--dry-run]   難句約 80 句
  python pipeline\run.py tts_bakeoff/cli --suite breezy smoke --engine breezy [--text ...]    CPU 單句冒煙測試(只用 CPU,不排 gpu_lock、不碰顯示卡)
  python pipeline\run.py tts_bakeoff/cli --suite breezy synth --engine cosy3|breezy|breezy_ann [--limit N] [--dry-run]   GPU(排 gpu_lock)
  python pipeline\run.py tts_bakeoff/cli --suite breezy judge [--engine all]    GPU(品管鏈);all = 有合成結果的引擎
  python pipeline\run.py tts_bakeoff/cli --suite breezy report                   report.md(三組 + 成對差異 + 多音字錯誤數)+ listen.md(三方盲聽 20 句)
judge:兩引擎原始輸出都先做出片同款裁靜音 + 貼耳感 FX,再以 tts_cosy3 驗證模式(jobs verify=true、--max-retry 0、--rate-seeds 0,
不重錄)跑完整品管(雙辨識、尾切、停頓、語速、聲紋),每句 <n>.qc.json 在 tmp\tts_bakeoff\judge\<引擎>\。
"""
import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
if sys.path and Path(sys.path[0] or ".").resolve() == HERE:   # 當腳本執行時,別讓本資料夾的 corpus/metrics/report 等短名蓋過第三方套件
    sys.path.pop(0)
if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))
import paths as P  # noqa: E402
from tts_bakeoff import corpus as C  # noqa: E402
from tts_bakeoff import engines as EN  # noqa: E402
from tts_bakeoff import metrics as M  # noqa: E402
from tts_bakeoff import report as R  # noqa: E402

WORK = P.TMP / "tts_bakeoff"
BREEZY_WORK = WORK / "breezy_2026-11-04"
VRAM_LIMIT = R.VRAM_LIMIT
PROBE_TEXTS = ("今天我們來聊一聊這款遊戲到底值不值得買。", "這個問題很多人都問過,答案其實沒有那麼簡單。",
               "執行長在財報會議上說,今年的營收會比去年更好。", "玩家最在意的還是價格,還有遊戲本身好不好玩。",
               "官方後來又發了一篇公告,說這次的調整只是暫時的。", "如果你也覺得這件事情很奇怪,歡迎在留言區告訴我。",
               "說到底,這款遊戲的問題不是畫面,而是內容太少。", "我們下一支影片見。")
EST = {"cosy3": 4.0, "indextts2": 8.0, "breezy": 6.0, "breezy_ann": 6.0, "judge": 7.0}   # dry-run 預估秒/句(粗估,實際看 synth 摘要)


def today():
    return datetime.date.today().isoformat()


def lock(job):
    import gpu_lock as GL
    return GL.gpu_lock("tts_bakeoff", job)


def gpu_used():
    import gpu_lock as GL
    return GL.gpu_used_mib()


def engine_text(mtext):
    import tts_cosy3 as T3   # torch 等只在真的要產生送引擎文字時才載
    return T3.engine_text(mtext)


def read_json(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def write_json(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def ref_text():
    return P.COSY_REF.with_suffix(".txt")


def env_status():
    return {"tts_env_cosy3": EN.COSY_ENV.exists(), "tts_env_indextts2": EN.INDEX_ENV.exists(),
            "tts_models/IndexTTS2/config.yaml": (EN.INDEX_MODEL / "config.yaml").exists(),
            "tts_models/index-tts(原始碼)": EN.INDEX_REPO.exists(), "cosy_voice/ref_b.wav": P.COSY_REF.exists(),
            "tts_env_breezy": EN.BREEZY_ENV.exists(), "tts_models/BreezyVoice-300M/llm.pt": (EN.BREEZY_MODEL / "llm.pt").exists(),
            "tts_models/BreezyVoice(原始碼)": (EN.BREEZY_REPO / "single_inference.py").exists(),
            "tts_models/BreezyVoice_cache/G2PWModel": (EN.BREEZY_G2PW / "version").exists()}


# ------------------------------------------------------------ 第 1 步 probe
def probe_verdict(summ, limit=VRAM_LIMIT):
    """-> (通過?, [理由])。不穩定 = 有合成失敗或子行程中止;顯存 = vram_peak_mib(torch 峰值與 smi 增量取大)。"""
    reasons = []
    peak = summ.get("vram_peak_mib")
    if summ.get("crashed"):
        reasons.append(f"子行程中止({str(summ['crashed'])[:80]})")
    if summ.get("n_fail"):
        reasons.append(f"合成失敗 {summ['n_fail']} 句")
    if not summ.get("n_ok"):
        reasons.append("沒有任何一句合成成功")
    if peak is None:
        reasons.append("量不到顯存峰值")
    elif peak > limit:
        reasons.append(f"顯存峰值 {peak:.0f} MiB > {limit}")
    return not reasons, reasons


def import_probe(src):
    """外部 probe 結果(本機 indextts2_probe.py 的 JSON)-> 本工具 probe 格式。認得的鍵:
    vram_peak_mib | peak_mib | max_memory_allocated_mib | max_memory_reserved_mib(取最大)、load_s、n_ok、n_fail、crashed、
    sec_per_sentence(list 或數字)、dur_supported、dur_kwarg。"""
    d = read_json(src) or {}
    peaks = [d.get(k) for k in ("vram_peak_mib", "peak_mib", "max_memory_allocated_mib", "max_memory_reserved_mib")]
    peaks = [float(x) for x in peaks if x is not None]
    secs = d.get("sec_per_sentence")
    secs = secs if isinstance(secs, list) else [secs] if secs is not None else []
    out = dict(source=f"外部 probe:{src}", load_s=d.get("load_s"), torch_peak_mib=max(peaks) if peaks else None,
               vram_peak_mib=max(peaks) if peaks else None, n_ok=d.get("n_ok", len(secs)), n_fail=d.get("n_fail", 0),
               crashed=d.get("crashed"), time=M.time_summary(secs), dur_supported=d.get("dur_supported"),
               dur_kwarg=d.get("dur_kwarg"))
    return out


def cmd_probe(a):
    items = C.read_jsonl(a.work / "corpus.jsonl")[:a.n]
    if not items:
        items = [dict(n=i, mtext=t, itext=None) for i, t in enumerate(PROBE_TEXTS[:a.n])]
    if a.dry_run:
        print(f"probe:IndexTTS2 冷啟 + {len(items)} 句({'corpus.jsonl' if items[0].get('itext') else '內建句'}),門檻 {a.limit_mib} MiB")
        for k, v in env_status().items():
            print(f"  {'有' if v else '缺'}  {k}")
        return 0
    if a.from_json:
        pr = import_probe(a.from_json)
    else:
        for x in items:
            if not x.get("itext"):
                x["itext"] = C.to_indextts(engine_text(x["mtext"]))
        d = a.work / "probe"
        if d.exists():
            shutil.rmtree(d)
        opts = dict(fp16=not a.no_fp16, dur_kwarg=a.dur_kwarg, dur_unit=a.dur_unit, tokens_per_sec=a.tokens_per_sec)
        with lock("bakeoff_probe"):
            summ = EN.run_batch("indextts2", items, d / "wav", EN.worker_cmd("indextts2", P.COSY_REF, ref_text(), opts),
                                EN.worker_env("indextts2"), d / "worker.log", d / "rows.jsonl", gpu_used=gpu_used)
        rows = C.read_jsonl(d / "rows.jsonl")
        ready = summ.get("ready") or {}
        pr = dict(summ, time=M.time_summary([r["sec"] for r in rows if r["ok"]], [r["dur"] for r in rows if r["ok"]]),
                  load_alloc_mib=ready.get("vram_alloc_mib"), load_reserved_mib=ready.get("vram_reserved_mib"),
                  dur_supported=ready.get("dur_supported"), dur_kwarg=ready.get("dur_kwarg"), dur_unit=ready.get("dur_unit"),
                  fp16=not a.no_fp16)
    pr["limit_mib"] = a.limit_mib
    pr["passed"], pr["reasons"] = probe_verdict(pr, a.limit_mib)
    pr["date"] = today()
    write_json(a.work / "probe.json", pr)
    print(f"probe:峰值 {pr.get('vram_peak_mib')} MiB、成功 {pr.get('n_ok')} / 失敗 {pr.get('n_fail')}、"
          f"每句 {(pr.get('time') or {}).get('mean')} 秒、時長參數 {pr.get('dur_kwarg') if pr.get('dur_supported') else '無'}")
    if not pr["passed"]:
        R.write_closure(a.work / "report.md", pr, today())
        print(f"結案:{'; '.join(pr['reasons'])}\n結案紀錄 {a.work / 'report.md'}")
        return 3
    print("通過,下一步:corpus")
    return 0


# ------------------------------------------------------------ 第 2 步 corpus
def cmd_corpus(a):
    hard = a.focus == "hard"
    if hard and not a.suite_given:
        print("--focus hard 要加 --suite breezy(或 --work 指到新目錄),免得蓋掉舊 IndexTTS2 語料")
        return 2
    tags = [t for t in (a.tags or "").split(",") if t.strip()] or C.find_tags(P.BUILD, C.HARD_TAGS if hard else C.N_TAGS)
    if not tags:
        print(f"找不到 cosy3 引擎的 build\\<tag>\\tts_qc.json(素材根 {P.ROOT})")
        return 2
    tag_recs = []
    for t in tags:
        recs = C.load_records(P.build_dir(t) / "tts_qc.json")
        if hard:   # 逐句 qc 檔裡沒過的(定稿後 tts_qc.json 常常全過)也算難句
            recs = recs + C.load_qc_dir(P.tts_dir(t, "cosy3"))
        tag_recs.append((t, recs))
    eng = (lambda m: m) if a.dry_run else engine_text
    if hard:
        items = C.build_hard(tag_recs, eng, size=a.size, breezy_fn=C.breezy_text, seed=a.seed)
    else:
        items = C.build_corpus(tag_recs, eng, per_tag=a.per_tag, fail_max=a.fail_max, heard_max=a.heard_max, seed=a.seed,
                               breezy_fn=C.breezy_text)
    st = C.stats(items)
    classes = {}
    for v in st.values():
        for c, n in v.items():
            classes[c] = classes.get(c, 0) + n
    for t in tags:
        s = st.get(t, {})
        print(f"  {t}: {sum(s.values())} 句({'、'.join(f'{c} {n}' for c, n in s.items())})")
    n_ann = sum(x.get("bann_n", 0) for x in items)
    unmapped = [(x["n"], u) for x in items for u in x.get("bann_unmapped", [])]
    print(f"共 {len(items)} 句:{classes};breezy_ann 注音標注 {n_ann} 處、{sum(1 for x in items if x.get('bann_n'))} 句有標注;"
          f"無法對應注音的標注 {len(unmapped)} 處{(' ' + str(unmapped[:5])) if unmapped else ''}")
    if a.dry_run:
        return 0
    C.write_jsonl(a.work / "corpus.jsonl", items)
    write_json(a.work / "corpus_meta.json", dict(tags=tags, per_tag=a.per_tag, n=len(items), date=today(), focus=a.focus,
                                                 classes=classes, n_ann=n_ann, n_unmapped=len(unmapped),
                                                 **({} if hard else {c: classes.get(c, 0) for c in C.CLS_ORDER})))
    print(f"寫入 {a.work / 'corpus.jsonl'}")
    return 0


# ------------------------------------------------------------ 第 3 步 synth
def dur_targets(a, items):
    """時長控制的目標秒數 {n: 秒}:cosy = 本比武 CosyVoice 同句原始輸出長度;prod = 正式配音品管紀錄的 dur。"""
    if a.dur_source == "prod":
        return {x["n"]: x["prod_dur"] for x in items if x.get("prod_dur")}
    rows = C.read_jsonl(a.work / "cosy3" / "rows.jsonl")
    return {r["n"]: r["dur"] for r in rows if r.get("ok") and r.get("dur")}


def cmd_synth(a):
    items = C.read_jsonl(a.work / "corpus.jsonl")
    if not items:
        print("沒有 corpus.jsonl,先跑 corpus")
        return 2
    if a.limit:
        items = items[:a.limit]
    eng = a.engine
    if eng in EN.BREEZY:
        if not a.suite_given:
            print("BreezyVoice 要加 --suite breezy(或 --work 指到新目錄),免得蓋掉舊 IndexTTS2 結果")
            return 2
        if not all(x.get(EN.TEXT_KEY[eng]) for x in items):
            print(f"corpus.jsonl 沒有 {EN.TEXT_KEY[eng]} 欄(先用新版 corpus 重產)")
            return 2
    if a.dur and eng != "indextts2":
        print("--dur 只用在 indextts2")
        return 2
    pr = read_json(a.work / "probe.json")
    if eng == "indextts2" and not a.force and not (pr and pr.get("passed")):
        print("probe 未通過或未跑(先跑 probe;要硬跑加 --force)")
        return 3
    targets = None
    name = eng + ("_dur" if a.dur else "")
    if a.dur:
        if pr and pr.get("dur_supported") is False and not a.dur_kwarg:
            write_json(a.work / "dur_status.json", dict(supported=False, note="probe 時 infer() 沒有可辨認的時長參數;本機確認後用 --dur-kwarg 指定"))
            print("此版 IndexTTS2 infer() 沒有可辨認的時長參數 -> (f) 記為不支援(本機確認後可用 --dur-kwarg 指定再跑)")
            return 0
        targets = dur_targets(a, items)
        if not targets:
            print("沒有目標時長(--dur-source cosy 要先跑 synth --engine cosy3)")
            return 2
    n_todo = len(targets) if targets is not None else len(items)
    if a.dry_run:
        print(f"synth {name}:{n_todo} 句 -> {a.work / name}\\wav;預估 {n_todo * EST[eng] / 60:.0f} 分鐘(每句 {EST[eng]} 秒,粗估)")
        for k, v in env_status().items():
            print(f"  {'有' if v else '缺'}  {k}")
        return 0
    d = a.work / name
    opts = dict(fp16=not a.no_fp16, dur_kwarg=a.dur_kwarg, dur_unit=a.dur_unit, tokens_per_sec=a.tokens_per_sec)
    print(f"synth {name}:{n_todo} 句,排 gpu_lock ...", flush=True)
    with lock(f"bakeoff_{name}"):
        summ = EN.run_batch(eng, items, d / "wav", EN.worker_cmd(eng, P.COSY_REF, ref_text(), opts), EN.worker_env(eng),
                            d / "worker.log", d / "rows.jsonl", gpu_used=gpu_used, seed=a.seed, targets=targets)
    rows = [r for r in C.read_jsonl(d / "rows.jsonl") if r.get("ok")]
    old = read_json(d / "summary.json", {})
    for k in ("torch_peak_mib", "smi_delta_mib", "vram_peak_mib"):   # 續跑:峰值取歷次最大
        vals = [v for v in (old.get(k), summ.get(k)) if v is not None]
        summ[k] = max(vals) if vals else None
    summ.update(time=M.time_summary([r["sec"] for r in rows], [r["dur"] for r in rows]), n_rows=len(rows))
    if a.dur:
        summ["dur_target_src"] = a.dur_source
        if (summ.get("ready") or {}).get("dur_supported") is False and not rows:
            write_json(a.work / "dur_status.json", dict(supported=False, note="worker 回報 dur_unsupported"))
    write_json(d / "summary.json", summ)
    print(f"synth {name}:成功 {summ['n_ok']}、失敗 {summ['n_fail']}、略過(已有){summ['skipped']};峰值 {summ.get('vram_peak_mib')} MiB;"
          f"每句 {summ['time'].get('mean')} 秒{';子行程中止:' + str(summ['crashed']) if summ.get('crashed') else ''}")
    return 1 if summ.get("crashed") else 0


# ------------------------------------------------------------ smoke(CPU 單句冒煙測試)
SMOKE_TEXT = "執行長在財報會議上說,今年的營收會比去年更好。"


def cmd_smoke(a):
    """BreezyVoice 單句合成,只用 CPU(worker --device cpu 隱藏顯示卡;不排 gpu_lock):確認環境、權重、前端、參考音都通。"""
    eng = a.engine
    item = dict(n=0, **C.breezy_fields(a.text))
    d = a.work / "smoke" / eng
    print(f"smoke {eng}(CPU):{item[EN.TEXT_KEY[eng]]}")
    if a.dry_run:
        for k, v in env_status().items():
            print(f"  {'有' if v else '缺'}  {k}")
        return 0
    summ = EN.run_batch(eng, [item], d / "wav", EN.worker_cmd(eng, P.COSY_REF, ref_text(), dict(device="cpu")), EN.worker_env(eng),
                        d / "worker.log", d / "rows.jsonl")
    rows = C.read_jsonl(d / "rows.jsonl")
    write_json(d / "summary.json", dict(summ, ready={k: v for k, v in (summ.get("ready") or {}).items() if k != "prompt_text"}))
    ok = bool(rows and rows[-1].get("ok"))
    print(f"smoke {eng}:{'成功' if ok else '失敗'};載入 {summ.get('load_s')} 秒、合成 {rows[-1].get('sec') if rows else '-'} 秒、"
          f"音長 {rows[-1].get('dur') if rows else '-'} 秒;{(rows[-1].get('err') or '') if rows else summ.get('crashed')}\n"
          f"  實際送進模型的文字:{rows[-1].get('final_text') if rows else '-'}\n  音檔 {d / 'wav' / '0.wav'};log {d / 'worker.log'}")
    return 0 if ok else 1


# ------------------------------------------------------------ judge
def prep_wav(src, dst):
    """出片同款後製:load_mono(24 kHz)-> gentle_trim -> 貼耳感 FX(ffmpeg),與 tts_cosy3.make 相同順序。"""
    import soundfile as sf
    import tts_cosy3 as T3
    from tts_tail import gentle_trim
    w = gentle_trim(T3.load_mono(src), T3.SR)[0]
    tmp = Path(dst).with_suffix(".trim.wav")
    sf.write(str(tmp), w, T3.SR, subtype="FLOAT")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-af", T3.FX, "-c:a", "pcm_f32le", str(dst)], check=True)
    tmp.unlink()


def verify_engine(a, eng, items):
    """一個引擎:原始輸出 -> 後製 -> tts_cosy3 驗證模式(不重錄)。缺任何一句的 qc 就整批重跑(語速/音高基準是整批中位數)。"""
    rows = [r for r in C.read_jsonl(a.work / eng / "rows.jsonl") if r.get("ok")]
    by_n = {x["n"]: x for x in items}
    rows = [r for r in rows if r["n"] in by_n and (a.work / eng / "wav" / f"{r['n']}.wav").exists()]
    jd = a.work / "judge" / eng
    if not rows:
        print(f"judge {eng}:沒有合成結果,略過")
        return
    if not a.redo and all((jd / f"{r['n']}.qc.json").exists() for r in rows):
        print(f"judge {eng}:{len(rows)} 句都已有品管紀錄,略過(--redo 重跑)")
        return
    if jd.exists():
        shutil.rmtree(jd)
    jd.mkdir(parents=True)
    jobs = []
    for r in rows:
        out = jd / f"{r['n']}.wav"
        prep_wav(a.work / eng / "wav" / f"{r['n']}.wav", out)
        jobs.append(dict(idx=r["n"], text=by_n[r["n"]]["text"], out=str(out), verify=True))
    jf = jd / "jobs.json"
    write_json(jf, jobs)
    cmd = [str(P.TTS_ENV), "-X", "utf8", str(PIPE / "tts_cosy3.py"), str(jf), "--ref", str(P.COSY_REF),
           "--speed", str(EN.COSY_SPEED), "--voice", P.COSY_REF.name, "--seed", str(EN.SEED),
           "--max-retry", "0", "--rate-seeds", "0", "--asr2", "fun_nano"]
    print(f"judge {eng}:品管 {len(jobs)} 句 ...", flush=True)
    with open(jd / "run.log", "w", encoding="utf-8") as lf:
        rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=lf, cwd=str(P.REPO)).returncode
    if rc != 0:
        print(f"judge {eng}:tts_cosy3 結束碼 {rc}(見 {jd / 'run.log'})")


def default_norm():
    import tts_chattts as TC
    return TC.norm_text


def default_py_seq():
    from pypinyin import Style, lazy_pinyin
    return lambda s: lazy_pinyin(s, style=Style.TONE3, neutral_tone_with_five=True) if s else []


def poly_targets(mtext):
    """量測文字裡 pron_rules.json 的命中位置 -> {位置: (簡體原字, 應讀 tone3, strict)}(同 tts_pron_verify.targets_for)。"""
    import tts_asr as TA
    import tts_cosy_text as CT
    from tts_pron_verify import simp
    return {ev[0]: (simp(ev[1]), TA.token_reading(ev[2]), ev[1] in CT.RULE_ALWAYS)
            for ev in CT._live_events(mtext, CT._word_spans(mtext)[0]) if ev[2]}


def poly_verdicts(rec, targets, judge=None, **kw):
    """一句的多音字位置判定 list;judge_record 對位失敗(positions 空)時每個位置記 undetermined。"""
    if not targets:
        return []
    if judge is None:
        from tts_pron_verify import judge_record as judge
    j = judge(rec, targets, **kw)
    res = [p["result"] for p in j.get("positions") or []]
    return res or ["undetermined"] * len(targets)


def engine_rows(work, eng, items, norm, py_seq, targets_fn=poly_targets, judge=None):
    r"""judge\<eng>\<n>.qc.json -> {n: 單句列}。"""
    out = {}
    for x in items:
        rec = read_json(Path(work) / "judge" / eng / f"{x['n']}.qc.json")
        if not rec:
            continue
        rec.setdefault("measure_text", x["mtext"])
        out[x["n"]] = M.sentence_row(rec, norm, py_seq, poly_verdicts(rec, targets_fn(x["mtext"]), judge))
    return out


def dur_metrics(work):
    st = read_json(Path(work) / "dur_status.json")
    if st and st.get("supported") is False:
        return st
    rows = [r for r in C.read_jsonl(Path(work) / "indextts2_dur" / "rows.jsonl") if r.get("ok")]
    if not rows:
        return {}
    s = M.dur_summary([M.dur_error(r.get("target_sec"), r.get("dur")) for r in rows])
    sm = read_json(Path(work) / "indextts2_dur" / "summary.json", {})
    src = sm.get("dur_target_src", "cosy")
    s.update(supported=True, target_src="CosyVoice 同句時長(本比武原始輸出)" if src == "cosy" else "正式配音品管紀錄 dur")
    return s


def build_metrics(work, items, rows, synth, probe, corpus_meta, dur):
    E = {e: M.engine_summary(list(rows.get(e, {}).values())) for e in EN.ENGINES}
    cmp_, nc = M.compare(rows.get("cosy3", {}), rows.get("indextts2", {}))
    by, nby = {}, {}   # BreezyVoice 比武:各組對 cosy3、注音標注對純文字
    for key, (ea, eb) in {"breezy_vs_cosy3": ("cosy3", "breezy"), "breezy_ann_vs_cosy3": ("cosy3", "breezy_ann"),
                          "breezy_ann_vs_breezy": ("breezy", "breezy_ann")}.items():
        if rows.get(ea) and rows.get(eb):
            by[key], nby[key] = M.compare(rows[ea], rows[eb])
    return dict(date=today(), engines=E, compare=cmp_, n_common=nc, compare_by=by, n_common_by=nby, synth=synth, probe=probe,
                corpus=corpus_meta, dur=dur, rows={e: {str(n): r for n, r in rows.get(e, {}).items()} for e in rows})


def active_engines(work):
    """有合成結果(rows.jsonl)的引擎;一個都沒有 = 舊比武的兩個。"""
    got = [e for e in EN.ENGINES if C.read_jsonl(Path(work) / e / "rows.jsonl")]
    return got or ["cosy3", "indextts2"]


def cmd_judge(a):
    items = C.read_jsonl(a.work / "corpus.jsonl")
    engs = active_engines(a.work) if a.engine == "all" else [a.engine]
    if a.dry_run:
        for e in engs:
            n = len([r for r in C.read_jsonl(a.work / e / "rows.jsonl") if r.get("ok")])
            print(f"judge {e}:{n} 句;預估 {n * EST['judge'] / 60:.0f} 分鐘(粗估)")
        return 0
    if not a.metrics_only:
        with lock("bakeoff_judge"):
            for e in engs:
                verify_engine(a, e, items)
    norm, py_seq = default_norm(), default_py_seq()
    rows = {e: engine_rows(a.work, e, items, norm, py_seq) for e in EN.ENGINES}
    synth = {}
    for e in EN.ENGINES:
        s = read_json(a.work / e / "summary.json")
        if s:
            synth[e] = s
    mt = build_metrics(a.work, items, rows, synth, read_json(a.work / "probe.json"), read_json(a.work / "corpus_meta.json", {}),
                       dur_metrics(a.work))
    write_json(a.work / "metrics.json", mt)
    print("metrics.json:" + ";".join(f"{e} {len(rows[e])} 句" for e in EN.ENGINES if rows[e] or e in engs) + ";下一步 report")
    return 0


# ------------------------------------------------------------ report
def load_rows(mt):
    return {e: {int(n): r for n, r in (mt.get("rows") or {}).get(e, {}).items()} for e in EN.ENGINES}


def cmd_report(a):
    mt = read_json(a.work / "metrics.json")
    if not mt:
        print("沒有 metrics.json,先跑 judge")
        return 2
    if a.dry_run:
        print(f"report:會寫 {a.work / 'report.md'}、{a.work / 'listen.md'}")
        return 0
    rows = load_rows(mt)
    items = C.read_jsonl(a.work / "corpus.jsonl")

    def wav_of(e, n):
        f = a.work / "judge" / e / f"{n}.wav"
        return f if f.exists() else a.work / e / "wav" / f"{n}.wav"
    if any(rows.get(e) for e in EN.BREEZY):   # BreezyVoice 比武:三組報告 + 三方盲聽
        engs = [e for e in R.TRIO if rows.get(e)]
        R.write_report_multi(a.work / "report.md", mt, mt.get("date") or today(), engs)
        picks = R.pick_listen_multi(rows, engs, k=a.listen)
        R.write_listen_multi(a.work / "listen.md", picks, items, rows, wav_of, engs)
    else:
        R.write_report(a.work / "report.md", mt, mt.get("date") or today())
        picks = R.pick_listen(rows["cosy3"], rows["indextts2"], k=a.listen)
        R.write_listen(a.work / "listen.md", picks, items, rows["cosy3"], rows["indextts2"], wav_of)
    print(f"寫入 {a.work / 'report.md'}、{a.work / 'listen.md'}({len(picks)} 句)")
    return 0


# ------------------------------------------------------------ main
def parser():
    ap = argparse.ArgumentParser(description="配音引擎比武 IndexTTS2 vs CosyVoice3(T1)")
    ap.add_argument("--work", type=Path, help=f"工作目錄(預設 {WORK};--suite breezy = {BREEZY_WORK})")
    ap.add_argument("--suite", choices=["indextts2", "breezy"], default="indextts2", help="breezy = BreezyVoice 比武的工作目錄")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--dry-run", action="store_true", help="只印要做什麼與數字,不載模型、不排 GPU、不寫檔")
        return p

    def idx_opts(p):
        p.add_argument("--no-fp16", action="store_true", help="IndexTTS2 不用 fp16(預設 fp16 省顯存)")
        p.add_argument("--dur-kwarg", help="IndexTTS2 infer() 的時長參數名(本機依版本確認;不給 = 自動找)")
        p.add_argument("--dur-unit", choices=["sec", "ms", "tokens"])
        p.add_argument("--tokens-per-sec", type=float, default=50.0)
        return p

    p = idx_opts(common(sub.add_parser("probe", help="第 1 步:IndexTTS2 冷啟顯存與每句秒數")))
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--limit-mib", type=float, default=VRAM_LIMIT)
    p.add_argument("--from-json", help="改讀外部 probe 結果 JSON(本機 indextts2_probe.py)")
    p = common(sub.add_parser("corpus", help="第 2 步:抽語料"))
    p.add_argument("--tags", help="逗號分隔;不給 = 最近 5 支 cosy3 片")
    p.add_argument("--per-tag", type=int, default=C.PER_TAG)
    p.add_argument("--fail-max", type=int, default=C.FAIL_MAX)
    p.add_argument("--heard-max", type=int, default=C.HEARD_MAX)
    p.add_argument("--seed", type=int, default=C.SEED)
    p.add_argument("--focus", choices=["sample", "hard"], default="sample", help="hard = 難句(品管未過、多音字命中多、英文詞多),BreezyVoice 比武用")
    p.add_argument("--size", type=int, default=C.HARD_SIZE, help="--focus hard 的總句數")
    p = common(sub.add_parser("smoke", help="BreezyVoice CPU 單句冒煙測試(不碰顯示卡)"))
    p.add_argument("--engine", choices=EN.BREEZY, default="breezy")
    p.add_argument("--text", default=SMOKE_TEXT)
    p = common(sub.add_parser("synth", help="第 3 步:合成"))
    idx_opts(p)
    p.add_argument("--engine", choices=EN.ENGINES, required=True)
    p.add_argument("--dur", action="store_true", help="IndexTTS2 指定目標時長合成(量 (f))")
    p.add_argument("--dur-source", choices=["cosy", "prod"], default="cosy")
    p.add_argument("--seed", type=int, default=EN.SEED)
    p.add_argument("--limit", type=int, help="只做前 N 句(試跑)")
    p.add_argument("--force", action="store_true", help="probe 未過也跑 indextts2")
    p = common(sub.add_parser("judge", help="現有品管鏈 + 指標"))
    p.add_argument("--engine", choices=("all",) + EN.ENGINES, default="all")
    p.add_argument("--metrics-only", action="store_true", help="不跑品管,只讀既有 qc 紀錄算指標")
    p.add_argument("--redo", action="store_true", help="已有品管紀錄也整批重跑")
    p = common(sub.add_parser("report", help="report.md + listen.md"))
    p.add_argument("--listen", type=int, default=20)
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    a.suite_given = a.suite == "breezy" or a.work is not None   # 指定了工作目錄(不是預設的舊比武目錄)
    a.work = Path(a.work) if a.work else BREEZY_WORK if a.suite == "breezy" else WORK
    return {"probe": cmd_probe, "corpus": cmd_corpus, "smoke": cmd_smoke, "synth": cmd_synth, "judge": cmd_judge,
            "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
