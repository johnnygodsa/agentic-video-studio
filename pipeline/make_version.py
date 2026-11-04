#!/usr/bin/env python3
r"""一個指令做完一版:txt2json -> 文案檢查 -> 英文詞對照 [-> C0 試配(--tts-review)] -> 配音(含全部品管) -> 渲染前檢查 -> 渲染完整版 [-> 720p 預覽]
-> QA 總覽圖 -> tts_report -> 優先聽清單(純文字) [-> 聽審頁 HTML] -> 說明檔骨架 [-> 交付]
2026-10-21 使用者指定:每版只需要樣片(--lines)與完整版,預設不出 720p 預覽與聽審頁 HTML;要時加 --preview / --listen。

python pipeline/run.py make_version --tag re9_online --ver sample1 [--lines 1-6] [--voice M|F] [--bgm 檔名] [--skip-tts]
                                    [--img-prefix re9o_] [--title 中文片名] [--channel ChannelA|ChannelB|ChannelC] [--enqueue [--publish-at [ISO|HH:MM|auto]]]
                                    [--cover 封面.png] [--specs assets_xxx_specs] [--dry-run] [--skip-checks] [--checks-only]
                                    [--preview] [--listen] [--tts-review [--freeze] [--skip-c0]]
--engine cosy3:CosyVoice3 零樣本複製(tts_cosy3.py;參考音 B、貼耳感後製、speed 1.18;快取 build\<tag>\tts_cosy3,不動 chattts 的 tts\);
  英文詞對照改用 cosy_terms.json。2026-10-18 起預設 cosy3(使用者指定);ChatTTS 要加 --engine chattts。
--tts-review:只做 txt2json -> 檢查 -> 英文詞對照 -> 配音 -> 時長預檢(build --check-only --timing-only,不需素材;錯誤不中止,記入 tts_review.json 的 timing_errors) -> 配音報告 -> 聽審頁(不渲染;聽審頁時間點取 timeline_tts.json;維持原行為,一律出 HTML)。
--freeze(只能配 --tts-review,不可配 --lines):tts_review.json 寫完後 FZ.review_problems(tag) 為空 -> 自動凍結配音文本(FZ.freeze,理由「自動凍結:品管未過 0、時長預檢 0、配音鍵已記」)、
  印「已自動凍結 …」、進度板設「已凍結」;不為空 -> 逐條印原因、結束碼 3(不凍結,進度板為 C配音)。
--preview:加回 720p 預覽步驟(預設不跑)。--listen:加回聽審頁 HTML(預設不跑)。預設一律寫純文字 output\<tag>\listen_<ver>.txt
  (「## 必聽」節在最前、每行 `mm:ss|句號|原因|句子原文`;「## 其他」節只給類別、句數與句號;判定同聽審頁,見 listen_page.make_text)。
參數沿用 keep/wow_forever_interview/build_args.sh:語速 +18%、句間 0.12、段間 0.30、ChatTTS、男聲 M_seed_402.pt(女聲 F_seed_2456.pt 並加 --voice-eq soft)、
  --max-per-src 120、渲染加 --anim-bg star --bgm bgm/<檔>(BGM 音量預設對齊配音響度:曲的 3 秒窗 p90 = 配音 - 5.7 dB、最大窗至少比配音低 5.0 dB,2026-10-18;
  --bgm-db ±X 微調;明確給 --bgm-vol 才走舊算法 bgm_norm × vol)。--preview 的 720p 預覽同 deliver_preview.sh(兩段式、< 29,000,000 bytes)。
--lines:視為樣片,輸出只放 output\<tag>\,不交付、不產說明檔。沒給 --lines 且有 --title 才會呼叫 deliver.py 交付到下載資料夾(不給 --title 只提示)。
--bgm 不給 = 依頻道選定案曲(--channel;沒給讀 projects/<tag>/spec.json 的 channel;都沒有退回 Lightless_Dawn 並警告,2026-10-22)。
--channel / --enqueue / --cover:原樣傳給 deliver.py(--enqueue 必須同時給 --channel)。
--publish-at [ISO|HH:MM|auto](G-6,需 --enqueue):原樣傳給 deliver.py;佇列完成後自動呼叫後端 schedule 設發布時間(不給值 = 頻道預設檔次:ChannelA 18:00、ChannelB 21:00)。
  會阻塞到佇列完成(上限 --schedule-wait-min,預設 120 分鐘),失敗只警告並印手動補排程指令。
說明檔骨架:output\<tag>\<ver>_說明.md 不存在且 projects\<tag>\spec.json 存在才呼叫 re9_notes.py 產生(--specs 給截圖規格模組,預設 re9_notes 的 assets_re9_specs);
  已存在不覆寫、無 spec.json 印「略過」(都不算錯誤)。交付前若說明檔缺「發片資料」```text 區塊(deliver 解析不到),不呼叫 deliver,印「未交付:…」並以 exit 0 收場。
  交付前另跑 spec_check.py --tag <tag> --notes <說明檔>(封面人像跨片重複,SOP §4);有錯誤同樣「未交付:…」exit 0,deliver 成功後 --record 登錄到 channel\cover_persona_log.jsonl。
--skip-tts:略過配音步驟(要已有 build\<tag>\timeline_tts.json 與全部配音快取;渲染一律加 --no-synth,不會偷偷重錄)。
--img-prefix:script.txt 的 img: 前綴;re9_online 預設 re9o_,其他片不給時讀 script.txt 說明行的「前綴 xx_」,都沒有才必須給。
每步只印一行摘要,失敗時印該步最後 15 行(渲染前檢查改列出全部「錯誤」行);完整 log 寫 output\<tag>\make_<ver>.log。--dry-run 只印各步指令。
txt2json 後、配音前先跑文案檢查六項:script_lint -> sub_scan -> spec_check -> visual_check(C7),任一項有錯誤即中止(exit 1);script_structure、facts_check 只警告不中止
  (facts*.md 不存在就不跑 facts_check;projects\<tag>\spec.json 不存在就略過 spec_check,不回溯舊片)。
再跑「英文詞對照」(tts_terms.py 對照 say_terms.json):已登錄唸法未套用或未登錄英文詞即中止(exit 1),直接唸英文的詞只列為資訊。
C0 試配(--tts-review、完整版、cosy3、未凍結):projects\<tag>\c0_report.json 不存在或比 <tag>\script.txt 舊 -> 跑 tts_c0.py(本機;它自己走 gpu_lock)
  唸錯 > 0 即中止(exit 3,同品管未過);合成不完整/崩潰 exit 1;已有新報告(含 Kaggle/Colab 匯回後)不重跑;已凍結、--lines 樣片、--skip-tts、--skip-c0 略過。
--skip-checks:緊急略過文案檢查與英文詞對照(摘要會明顯標示);--checks-only:只做 txt2json、文案檢查與英文詞對照就結束(不配音不渲染)。
非核心步驟(E4耳朵 C21、優先聽 C22、唸法清單 C23、聽審頁 C24、優先看 D26、審閱彙整、C7/C8/C9 崩潰、進度板)失敗一律不中止整版,
  印一行並追加 {at, step, msg} 到 projects\<tag>\production.json 的 warns(log_warn)。
每步秒數也寫進 log(output\<tag>\make_<ver>.log 的 `[i/n] 步驟 OK/失敗 N.Ns` 行)。
配音步驟包在全機 GPU 鎖內(gpu_lock.py:依 board.json 的 publish 排隊,輪到且 nvidia-smi 已用 <= 3000 MiB 才跑)。
文案凍結(freeze.py):凍結只鎖「配音文本」(每句送配音的文字序列的 narration_sha;畫面標籤/hl/kit/anim/pause/note/f 等凍結後可自由改);
  projects\<tag>\freeze.json 存在且配音文本不符(舊凍結沒有 narration_sha 才比整檔 sha256),非 --tts-review 一律中止。
完成後自動更新進度板(board.py):--tts-review -> C配音(--freeze 凍結成功 -> 已凍結);完整版(無 --lines)-> E自審(現階段是「改版」不動);
  --lines 樣片不動;--enqueue 交付成功 -> 已排程。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import board
import decide_list as DL
import freeze as FZ
from audio_consts import BGM_BY_CHANNEL, DEFAULT_BGM, bgm_for_channel, channel_kind  # noqa: F401  (單一來源;BGM_BY_CHANNEL/DEFAULT_BGM 供測試與 shorts_build 取用)
import gpu_lock as GL
import listen_page as LP
import look_list as LK
import paths as P
import review_md as RV

PY = sys.executable
RUN = str(P.REPO / "pipeline" / "run.py")
PREVIEW_LIMIT = 29_000_000
GPU_MAX_MIB = GL.GPU_MAX_MIB
IMG_PREFIX = {"re9_online": "re9o_"}
VOICES = {"M": ("seed402", "M_seed_402.pt"), "F": ("seed2456", "F_seed_2456.pt")}


def script_img_prefix(tag):
    """script.txt 前 20 行說明(# 截圖(前綴 ain_…) / 圖檔前綴:xx_)裡的圖片前綴;沒有回 None。
    director 的 C 段改句迴圈呼叫 make_version 不帶 --img-prefix,靠這個找回。"""
    try:
        head = (P.REPO / tag / "script.txt").read_text(encoding="utf-8-sig").splitlines()[:20]
    except OSError:
        return None
    for l in head:
        if l.lstrip().startswith("#"):
            m = re.search(r"前綴\s*[:：]?\s*([A-Za-z0-9_]*[A-Za-z0-9]_)", l)  # 前綴可含底線(rc_3days_)
            if m:
                return m.group(1)
    return None


def pick_bgm(bgm, channel, tag, spec_channel=None):
    """BGM 檔名與來源說明 -> (檔名, 來源)。優先序:使用者 --bgm > --channel > spec.json 的 channel > 舊預設。
    第三頻道三首以 tag 的 crc32 取餘輪用(穩定,同一支片每版都同一首)。"""
    if bgm:
        return bgm, "使用者指定"
    for ch in (channel, spec_channel):
        name = bgm_for_channel(ch, tag)
        if name:
            return name, f"依頻道 {channel_kind(ch)}"
    return DEFAULT_BGM, "舊預設"


def spec_channel_of(tag):
    """projects/<tag>/spec.json 的 channel 欄位;檔案不存在或壞掉 = None。"""
    try:
        return json.loads((P.PROJECTS / tag / "spec.json").read_text(encoding="utf-8")).get("channel")
    except (OSError, ValueError):
        return None


def precheck_cmds(tag):
    """文案檢查各項(名稱, 指令);spec.json 不存在時 spec_check 為 None(略過)。"""
    spec = P.PROJECTS / tag / "spec.json"
    cmds = [
        ("script_lint", [PY, "-X", "utf8", str(P.REPO / "pipeline" / "script_lint.py"), tag]),
        ("sub_scan", [PY, "-X", "utf8", str(P.REPO / "pipeline" / "sub_scan.py"), "--tag", tag]),
        ("spec_check", [PY, "-X", "utf8", str(P.REPO / "pipeline" / "spec_check.py"), "--tag", tag] if spec.exists() else None),
        ("visual_check", [PY, "-X", "utf8", str(P.REPO / "pipeline" / "visual_check.py"), "--tag", tag, "--table"]),  # 句畫檢查:錯誤(結束碼 1)中止,警告不中止
        ("script_structure", [PY, "-X", "utf8", str(P.REPO / "pipeline" / "script_structure.py"), tag]),  # 文案結構檢查,只警告不中止
    ]
    # facts_check:程式與 projects/<tag>/facts*.md 都在才排入(只警告不中止)
    if (P.REPO / "pipeline" / "facts_check.py").exists() and any((P.PROJECTS / tag).glob("facts*.md")):
        cmds.append(("facts_check", [PY, "-X", "utf8", str(P.REPO / "pipeline" / "facts_check.py"), tag]))
    return cmds


LINT_WARN_RE = r"\[lint\] 警告 (\d+) 項"
SUB_WARN_RE = r"警告 (\d+) 項"
STRUCT_WARN_RE = r"\[structure\] 警告 (\d+) 項"


def _warn_count(out, pattern, default="?"):
    """從檢查項 stdout 讀實際警告數;讀不到回 default(不再寫死 0)。"""
    for l in reversed(out):
        m = re.search(pattern, l)
        if m:
            return m.group(1)
    return default


def visual_error_lines(out, name="visual_check"):
    """visual_check stdout -> 「錯誤 Exx xN」區塊下的明細行(最多 5 行),供中止時印出。"""
    res, inside = [], False
    for l in out:
        if re.match(r"\s+錯誤 E\d+", l):
            inside = True
            res.append(f"    [{name}] {l.strip()[:110]}")
        elif re.match(r"\s+警告 ", l) or l.startswith("  最長") or l.startswith("[visual_check]"):
            inside = False
        elif inside and l.strip():
            res.append(f"    [{name}] {l.strip()[:110]}")
    return res[:5] or [f"    [{name}] 錯誤(見 projects/<tag>/visual_table.md)"]


def run_prechecks(tag, log):
    """依序跑三項;回傳 (是否全過, 摘要行 list, 錯誤項 list)。有錯誤仍把三項跑完,方便一次看全。"""
    summ, errs, ok = [], [], True
    for name, cmd in precheck_cmds(tag):
        if cmd is None:
            summ.append(f"  {name}: 無 spec,略過")
            continue
        rc, out = run_cmd(cmd, log)
        if name == "script_lint":
            m = next((re.search(r"超標 (\d+) 項", l) for l in reversed(out) if "超標" in l and "[lint]" in l), None)
            e = int(m.group(1)) if m else (1 if rc else 0)
            detail = [l.strip() for l in out if l.strip().startswith("超標")]
            summ.append(f"  {name}: {'通過' if not rc else '失敗'} | 錯誤(超標) {e} | 警告 {_warn_count(out, LINT_WARN_RE)}")
        elif name == "sub_scan":
            m = next((re.search(r"接縫 (\d+) 筆", l) for l in out if "接縫" in l), None)
            e = int(m.group(1)) if m else (1 if rc else 0)
            detail = [l.strip() for l in out if l.startswith("  句")]
            summ.append(f"  {name}: {'通過' if not rc else '失敗'} | 錯誤(切詞接縫) {e} | 警告 {_warn_count(out, SUB_WARN_RE, '-')}")   # sub_scan 無警告分級,印 -
        elif name == "visual_check":   # C7:結束碼 1 = 錯誤(@def 未定義、hl 找不到)中止;警告不中止;其他結束碼(崩潰)只標執行失敗不中止
            m = next((re.search(r"警告 (\d+) 項、錯誤 (\d+) 項", l) for l in out if "[visual_check] 警告" in l), None)
            if rc == 1:
                ok = False
                summ.append(f"  {name}: 警告 {m.group(1) if m else '?'} | 錯誤 {m.group(2) if m else '?'}(明細 projects/{tag}/visual_table.md,中止)")
                errs += visual_error_lines(out, name)
                continue
            summ.append(f"  {name}: 警告 {m.group(1)} | 錯誤 {m.group(2)}(明細 projects/{tag}/visual_table.md,警告不中止)" if m else f"  {name}: 執行失敗(不中止)")
            if not m:
                log_warn(tag, "C7 visual_check", f"執行失敗 rc={rc}(不中止)")
            continue
        elif name == "script_structure":
            summ.append(f"  {name}: 警告 {_warn_count(out, STRUCT_WARN_RE)}(明細 build/{tag}/structure.json,不中止)" if rc in (0, 1) else f"  {name}: 執行失敗(不中止)")
            if rc not in (0, 1):
                log_warn(tag, "C8 script_structure", f"執行失敗 rc={rc}(不中止)")
            continue
        elif name == "facts_check":
            last = next((l.strip() for l in reversed(out) if l.strip().startswith("[facts_check]")), None)
            summ.append(f"  {name}: {last[len('[facts_check]'):].strip()}(不中止)" if last else f"  {name}: 執行失敗或無摘要(不中止)")
            if not last:
                log_warn(tag, "C9 facts_check", f"執行失敗或無摘要 rc={rc}(不中止)")
            continue
        else:
            m = next((re.search(r"警告 (\d+) 項、錯誤 (\d+) 項", l) for l in out if "警告" in l and "錯誤" in l), None)
            w, e = (int(m.group(1)), int(m.group(2))) if m else (0, 1 if rc else 0)
            detail = [l.strip() for l in out if l.strip().startswith("錯誤:")]
            summ.append(f"  {name}: {'通過' if not rc else '失敗'} | 錯誤 {e} | 警告 {w}")
        if rc:
            ok = False
            if not detail:
                detail = [l.strip() for l in out if l.strip()][-5:]
            errs += [f"    [{name}] {d[:110]}" for d in detail[:5]]
    return ok, summ, errs


def log_warn(tag, step, msg):
    """非核心步驟失敗不中止整版:印一行並追加 {at, step, msg} 到 projects/<tag>/production.json 的 warns(director._append,同一份檔)。
    寫 production.json 失敗也只印,絕不讓警告本身中止整版。"""
    msg = str(msg)[:300]
    print(f"警告:{step}:{msg}")
    try:
        import director as DR
        DR._append(tag, "warns", {"at": DR.now_iso(), "step": step, "msg": msg})
    except Exception as e:  # noqa: BLE001
        print(f"警告:warns 未寫入 production.json({type(e).__name__}: {e})")


class Step:
    def __init__(self, name, cmds=None, fn=None, desc=""):
        self.name, self.cmds, self.fn, self.desc = name, cmds or [], fn, desc


gpu_used_mib = GL.gpu_used_mib  # 共用查法(舊呼叫點相容)


def freeze_check(tag, tts_review=False):
    """文案凍結檢查:回傳中止訊息(None = 可繼續);--tts-review(聽審用)不受限。"""
    return None if tts_review else FZ.check(tag)


def timing_errors_of(rc, tail):
    """時長預檢(build --check-only --timing-only)的輸出 -> 錯誤清單:取「錯誤:」行;結束碼非 0 卻沒有任何錯誤行(例如 timeline 不存在、崩潰)
    記一筆執行失敗,免得預檢沒跑成卻當作通過。"""
    errs = [l.strip()[len("錯誤:"):].strip() for l in tail if l.strip().startswith("錯誤:")]
    if rc and not errs:
        errs = ["時長預檢執行失敗: " + next((l.strip() for l in reversed(tail) if l.strip()), "無輸出")[:200]]
    return errs


def parse_new_synth(tail):
    """配音步驟(build --tts-only)輸出 -> 本次新合成句數(int);解析不到 None。
    build.tts_all 印「TTS[引擎]: 重新檢驗既有音檔 N 個、新合成 M 個」(edge 引擎印「產生 M 句」);沒有待合成單位時只印
    「命中 X、需合成或重新檢驗 0」,視為 0。多行加總。"""
    n, hit = 0, False
    for l in tail or []:
        m = re.search(r"新合成 (\d+) 個", l) or re.search(r"TTS\[edge\]: 產生 (\d+) 句", l)
        if m:
            n, hit = n + int(m.group(1)), True
        elif re.search(r"需合成或重新檢驗 0", l):
            hit = True
    return n if hit else None


def write_tts_review(tag, engine, timing_errors=None, new_synth=None):
    """--tts-review 配音後寫 build/<tag>/tts_review.json(freeze.py 的凍結門檻讀它)。
    units / failed / no_qc 取自 build.write_qc_report 寫的 tts_qc.json(不重算品管);timing_errors = 「時長預檢」步的錯誤清單(沒跑 = 空);
    new_synth = 配音步驟新合成句數(parse_new_synth;解析不到 None)。"""
    qf = P.build_dir(tag) / "tts_qc.json"
    if not qf.exists():
        raise FileNotFoundError(f"找不到 {qf}(此引擎沒有品管報告?)")
    qc = json.loads(qf.read_text(encoding="utf-8"))
    rec = dict(script_sha256=FZ.sha256(FZ.script_path(tag)), narration_sha=FZ.narration_sha(tag), at=time.strftime("%Y-%m-%dT%H:%M:%S"), units=qc.get("units"),
               failed=[dict(idx=f.get("idx"), fails=f.get("fails")) for f in (qc.get("failed") or [])],
               no_qc=list(qc.get("no_qc") or []), timing_errors=list(timing_errors or []), tts_keys_sha=FZ.tts_keys_sha(tag, engine), engine=engine,
               new_synth=new_synth)
    out = FZ.review_path(tag)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return out, rec


def qc_gate_problems(tag):
    """C15:完整渲染前的品管硬擋。tts_qc.json 有品管未過單位且 freeze.json 不存在 -> 回中止訊息行 list;其餘(已凍結、品管全過、
    沒有 tts_qc.json)回 []。已凍結的片不受影響(凍結即定案,門檻在凍結當下已過)。"""
    if FZ.freeze_path(tag).exists():
        return []
    try:
        qc = json.loads((P.build_dir(tag) / "tts_qc.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    failed = qc.get("failed") or []
    if not failed:
        return []
    names = [f"句{f.get('idx')}:{'/'.join(str(x) for x in (f.get('fails') or []))}" for f in failed]
    return [f"配音品管未過 {len(failed)} 個單位且未凍結,不渲染(C15):", *[f"  {x}" for x in names[:20]],
            *([f"  …另 {len(names) - 20} 項"] if len(names) > 20 else []),
            "改句重錄 → --tts-review 品管過 → --freeze 後再渲染(不可放寬別名過關)"]


def board_after(tag, a, sample, delivered, frozen=False):
    """make_version 完成後更新進度板;失敗只警告。frozen = --tts-review --freeze 已自動凍結。"""
    try:
        if a.tts_review:
            stage = "已凍結" if frozen else "C配音"
        elif a.enqueue and delivered:
            stage = "已排程"
        elif a.checks_only:
            return
        elif sample:  # 樣片(--lines)不動階段
            stage = None
        else:  # 完整版:現階段是「改版」不動,否則 E自審
            stage = None if (board.get(tag) or {}).get("stage") == "改版" else "E自審"
        kw = {"channel": a.channel} if a.channel else {}
        if stage:
            board.set_stage(tag, stage, force=True, **kw)  # 自動流程本來就在門檻過後才設,不被 board 前置條件重複卡住
        elif kw or board.get(tag) is None:
            board.update(tag, **kw)
    except Exception as e:  # noqa: BLE001
        log_warn(tag, "E13 進度板", f"未更新({type(e).__name__}: {e})")


def probe_duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def preview_cmds(src, dst, bdir, dur):
    """同 deliver_preview.sh:目標 27.3 MiB,扣音訊 96k 與餘量 20k 後全給影像,兩段式。"""
    vk = min(4000, int(27.3 * 8 * 1024 * 1024 / dur / 1000 - 96 - 20))   # 短片(樣片)不需要把預算用完,兩段式會超出目標
    base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vf", "scale=1280:720:flags=lanczos",
            "-c:v", "libx264", "-preset", "slow", "-b:v", f"{vk}k", "-passlogfile", str(bdir / "prev2pass")]
    p1 = base + ["-pass", "1", "-an", "-f", "null", "-"]
    p2 = base + ["-pass", "2", "-c:a", "aac", "-b:a", "96k", "-ar", "48000", "-movflags", "+faststart", str(dst)]
    return [p1, p2]


def terms_cmd(tag, engine="chattts"):
    return [PY, "-X", "utf8", str(P.REPO / "pipeline" / "tts_terms.py"), tag, "--engine", engine]


def c0_needed(tag):
    """--tts-review 是否要先跑 C0 試配 -> (要跑?, 原因)。已凍結 = 否;c0_report.json 不存在或比 <tag>/script.txt 舊 = 要;
    其餘(含 Kaggle/Colab 匯回後已有較新報告)= 否。只比檔案時間,稿或讀音表的 script_sha 是否相符由 tts_dispatch 的 C0 閘門另查。"""
    if FZ.freeze_path(tag).exists():
        return False, "已凍結"
    rep, scr = P.PROJECTS / tag / "c0_report.json", P.REPO / tag / "script.txt"
    if not rep.exists():
        return True, "沒有 c0_report.json"
    if scr.exists() and rep.stat().st_mtime < scr.stat().st_mtime:
        return True, "c0_report.json 比 script.txt 舊"
    return False, "已有報告"


def c0_cmd(tag):
    return [str(P.TTS_ENV), "-X", "utf8", str(P.REPO / "pipeline" / "tts_c0.py"), tag]


def notes_cmd(a, prefix, tl, bdir, video, prev, notes):
    """re9_notes 指令;無 projects\\<tag>\\spec.json 回傳 None(略過)。"""
    spec = P.PROJECTS / a.tag / "spec.json"
    if not spec.exists():
        return None
    c = [PY, "-X", "utf8", str(P.REPO / "pipeline" / "re9_notes.py"), "--spec", str(spec), "--timeline", str(tl),
         "--qc", str(bdir / "tts_qc.json"), "--script", f"{a.tag}/script.json", "--video", str(video), "--preview", str(prev),
         "--ver", a.ver, "--bgm", Path(a.bgm).stem.replace("_", " "), "--out", str(notes), "--img-prefix", prefix]
    return c + (["--specs", a.specs] if a.specs else [])


def deliver_cmd(a):
    c = [PY, str(P.REPO / "pipeline" / "deliver.py"), "--tag", a.tag, "--ver", a.ver, "--title", a.title]
    if a.channel:
        c += ["--channel", a.channel]
    if a.enqueue:
        c.append("--enqueue")
    if a.cover:
        c += ["--cover", a.cover]
    if getattr(a, "publish_at", None) is not None:
        c += ["--publish-at", a.publish_at]
        if getattr(a, "schedule_wait_min", None):
            c += ["--schedule-wait-min", str(a.schedule_wait_min)]
    return c


def persona_cmd(tag, notes, record=False):
    """spec_check 封面人像跨片重複檢查(--notes);record=True 時把方案1、3 登錄到 cover_persona_log.jsonl。"""
    c = [PY, "-X", "utf8", str(P.REPO / "pipeline" / "spec_check.py"), "--tag", tag, "--notes", str(notes)]
    return c + ["--record"] if record else c


def has_release_block(notes):
    """說明檔存在且 deliver.py 能解析出「發片資料」區塊。"""
    if not notes.exists():
        return False
    import deliver as D
    return D.parse_notes(notes.read_text(encoding="utf-8"))[0] is not None


def run_cmd(cmd, log):
    """執行並把輸出附加到 log;回傳 (returncode, 輸出行 list)。"""
    log.write("\n$ " + " ".join(str(c) for c in cmd) + "\n")
    r = subprocess.run([str(c) for c in cmd], cwd=P.REPO, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    out = (r.stdout or "") + (r.stderr or "")
    log.write(out)
    log.flush()
    return r.returncode, out.splitlines()


def main():
    ap = argparse.ArgumentParser(description="一個指令做完一版(見檔頭說明)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ver", required=True, help="版本名,例如 sample1、v1")
    ap.add_argument("--lines", help="只做第 a-b 句(樣片;不交付)")
    ap.add_argument("--voice", choices=("M", "F"), default="M", help="M = 男聲(預設)、F = 女聲(加 --voice-eq soft);只用於 chattts")
    ap.add_argument("--engine", choices=("chattts", "cosy3"), default="cosy3",
                    help="配音引擎(預設 cosy3,2026-10-18);cosy3 = CosyVoice3 零樣本複製(參考音 paths.COSY_REF、speed 1.18,快取在 build\<tag>\tts_cosy3)")
    ap.add_argument("--bgm", default=None, help="bgm 資料夾內的檔名;不給 = 依 --channel(或 spec.json 的 channel)選定案曲:ChannelA ai_C2_light、ChannelB ai_D2_reflective、第三頻道 ai_E1/E2/E3_mystery 依 tag 輪用;都查不到退回 " + DEFAULT_BGM)
    ap.add_argument("--bgm-vol", default=None,
                    help="舊算法(舊片重渲染用):BGM 增益 = 此值 × 整首響度對齊倍率;不給 = 預設算法(對齊配音響度,見 build.py BGM_BELOW_VOICE_DB)")
    ap.add_argument("--label-style", choices=("lower", "corner"), default=None,
                    help="截圖出處標籤:預設 lower 下標籤;corner = 舊右下角標(舊片重渲染用,轉傳給 build.py;script 的 label_style 優先)")
    ap.add_argument("--no-push", action="store_true", help="關閉鏡頭間 0.2 秒輕推移(轉傳給 build.py;舊片重渲染保持原外觀用)")
    ap.add_argument("--legacy-tilt", action="store_true", help="舊片重渲染保持原外觀:轉傳給 build.py,沒有 layout kind 的文字截圖也輪用 tilt")
    ap.add_argument("--bgm-db", default=None, help="預設算法再加減幾 dB(使用者要求「大聲 X dB」時用,例 3 或 -2)")
    ap.add_argument("--comma-profile", choices=("std", "long"), default="std",
                    help="逗號停頓側寫(轉傳給 build.py):std = 現行(預設);long = 長句逗號停頓較長,僅供本機 A/B 試聽(只重做停頓後處理,不重錄)")
    ap.add_argument("--cosy-speed", type=float, default=None,
                    help="cosy3 語速(轉傳給 build.py --cosy-speed);不給 = 沿用 build 預設 1.18。會進音檔鍵,改了會重錄")
    ap.add_argument("--skip-tts", action="store_true", help="略過配音(用既有 timeline_tts.json 與快取)")
    ap.add_argument("--img-prefix", help="script.txt 的 img: 前綴(re9_online 預設 re9o_)")
    ap.add_argument("--title", help="中文片名;完整版(無 --lines)給了才交付到下載資料夾")
    ap.add_argument("--channel", help="ChannelA|ChannelB|ChannelC;原樣傳給 deliver.py(--enqueue 必填)")
    ap.add_argument("--enqueue", action="store_true", help="交付成功後送進 Youtube AD 佇列(傳給 deliver.py)")
    ap.add_argument("--publish-at", nargs="?", const="auto", default=None, metavar="ISO|HH:MM|auto",
                    help="需 --enqueue:傳給 deliver.py,佇列完成後呼叫後端 schedule;不給值 = 頻道預設檔次(ChannelA 18:00、ChannelB 21:00)")
    ap.add_argument("--schedule-wait-min", type=int, default=None, help="等佇列完成的上限(分鐘);預設 120")
    ap.add_argument("--cover", help="封面 PNG;傳給 deliver.py(預設由 deliver 找 output\\<tag>\\<tag>_thumb.png)")
    ap.add_argument("--specs", help="截圖規格模組(傳給 re9_notes.py,例 assets_dei_specs;預設 assets_re9_specs)")
    ap.add_argument("--tts-review", action="store_true", help="只配音並出聽審頁(不渲染、不出預覽與 QA 圖)")
    ap.add_argument("--freeze", action="store_true", help="只能配 --tts-review:審核紀錄全過(品管未過 0、時長預檢 0)就自動凍結配音文本,否則逐條印原因、結束碼 3")
    ap.add_argument("--preview", action="store_true", help="加出 720p 預覽(預設不出,2026-10-21)")
    ap.add_argument("--listen", action="store_true", help="加出聽審頁 HTML(預設只出純文字 listen_<ver>.txt,2026-10-21)")
    ap.add_argument("--dry-run", action="store_true", help="只印出將執行的各步指令")
    ap.add_argument("--skip-checks", action="store_true", help="緊急用:略過文案檢查與英文詞對照")
    ap.add_argument("--skip-c0", action="store_true", help="只用於 --tts-review:略過 C0 試配(預設報告缺或比 script.txt 舊就先跑)")
    ap.add_argument("--checks-only", action="store_true", help="只做 txt2json、文案檢查與英文詞對照就結束(不配音不渲染)")
    ap.add_argument("--polyset", choices=("rules", "risk", "all"), default=None, help="E1 all 模式的多音字集合:設 COSY_POLYSET(預設 risk)")
    ap.add_argument("--annotate", choices=("table", "all"), default=None,
                    help="cosy3 拼音標注模式(E1 pilot,docs/tts.md §4.7):設環境變數 COSY_ANNOTATE 給子行程;不給 = 沿用環境變數,預設 table")
    a = ap.parse_args()
    if a.annotate:
        os.environ["COSY_ANNOTATE"] = a.annotate
    if a.polyset:
        os.environ["COSY_POLYSET"] = a.polyset
    if a.enqueue and not a.channel:
        ap.error("--enqueue 必須同時給 --channel")
    if a.publish_at is not None and not a.enqueue:
        ap.error("--publish-at 必須同時給 --enqueue")
    if a.freeze and not a.tts_review:
        ap.error("--freeze 只能配 --tts-review")
    if a.freeze and a.lines:
        ap.error("--freeze 不能配 --lines(樣片不寫 tts_review.json)")
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")

    tag, ver = a.tag, a.ver
    prefix = a.img_prefix or IMG_PREFIX.get(tag) or script_img_prefix(tag)
    if not prefix:
        sys.exit(f"{tag} 沒有預設圖片前綴,請加 --img-prefix <前綴>_")
    if not (P.REPO / tag / "script.txt").exists():
        sys.exit(f"找不到 {tag}/script.txt")
    fz_msg = freeze_check(tag, a.tts_review)
    if fz_msg:
        sys.exit(fz_msg)
    if a.tts_review and os.environ.get("CV_REFREEZE_OK") != "1":   # 開跑前:配音稿與凍結一致(未凍結 = 通過)
        if subprocess.run([sys.executable, "-X", "utf8", str(P.REPO / "pipeline" / "tts_script.py"), tag, "--verify"]).returncode:
            sys.exit(f"配音文本與凍結不一致,不配音。查:python -X utf8 pipeline\\tts_script.py {tag} --verify"
                     "(確定要改稿重錄:設 CV_REFREEZE_OK=1 再跑)")
    a.bgm, bgm_src = pick_bgm(a.bgm, a.channel, tag, None if a.channel else spec_channel_of(tag))
    bgm_line = f"BGM:{a.bgm}({bgm_src})"
    if bgm_src == "舊預設":
        bgm_line += "\n警告:BGM 用舊預設(未給 --channel)"
    print(bgm_line)
    bgm = P.BGM / a.bgm
    if not bgm.exists():
        sys.exit(f"找不到 BGM: {bgm}")
    voice, spk = VOICES[a.voice]
    if a.engine == "cosy3":
        if a.voice != "M":
            sys.exit("cosy3(預設引擎)只有一個聲音(參考音 B);要女聲請加 --engine chattts --voice F")
        voice, spk = "cosyB", None
    odir, bdir = P.output_dir(tag), P.build_dir(tag)
    out_name = f"{tag}_{ver}.mp4"
    video, prev = odir / out_name, odir / f"{tag}_{ver}_720p.mp4"
    tl_tts, tl = bdir / "timeline_tts.json", bdir / "timeline.json"
    sample = bool(a.lines)
    notes = odir / f"{ver}_說明.md"

    def build(*extra):
        c = [PY, RUN, "build", "--script", f"{tag}/script.json", "--voice", voice, "--rate", "+18%", "--gap", "0.12",
             "--section-gap", "0.30", "--tts-engine", a.engine, *(["--spk", spk] if spk else []), "--tag", tag, "--clips", "auto",
             "--max-per-src", "120"]
        if a.lines:
            c += ["--lines", a.lines]
        if a.cosy_speed is not None:
            c += ["--cosy-speed", str(a.cosy_speed)]
        if a.comma_profile != "std":
            c += ["--comma-profile", a.comma_profile]
        return c + list(extra)

    render_opts = ["--anim-bg", "star", "--bgm", f"bgm/{a.bgm}"]
    if a.bgm_vol is not None:
        render_opts += ["--bgm-vol", a.bgm_vol]
    if a.bgm_db is not None:
        render_opts += ["--bgm-db", a.bgm_db]
    if a.legacy_tilt:
        render_opts += ["--legacy-tilt"]
    if a.label_style:
        render_opts += ["--label-style", a.label_style]
    if a.no_push:
        render_opts += ["--no-push"]
    if a.voice == "F" and a.engine == "chattts":
        render_opts += ["--voice-eq", "soft"]

    steps = [Step("txt2json", [[PY, RUN, "script_txt2json", f"{tag}/script.txt", "--img-prefix", prefix]],
                  desc="文案轉 script.json")]
    if not a.skip_checks:
        steps.append(Step("文案檢查", fn="prechecks", desc="script_lint -> sub_scan -> spec_check(任一錯誤即中止)-> visual_check/script_structure/facts_check(只警告)"))
        steps.append(Step("英文詞對照", [terms_cmd(tag, a.engine)],
                          desc=f"英文專有名詞對照 {'cosy_terms' if a.engine == 'cosy3' else 'say_terms'}.json(未登錄/未套用即中止)"))
    c0_run = False
    if a.tts_review and not sample and not a.skip_tts and a.engine == "cosy3":
        c0_run, c0_why = False, "--skip-c0" if a.skip_c0 else None
        if not a.skip_c0:
            c0_run, c0_why = c0_needed(tag)
        if c0_run:
            steps.append(Step("C0試配", fn="c0", desc=f"C0 風險句試配(tts_c0.py,走 gpu_lock;{c0_why};唸錯>0 中止 exit 3)"))
        else:
            print(f"C0 試配:略過({c0_why})")
    if not a.skip_tts:
        steps.append(Step("配音", [build("--tts-only", "--out", out_name, *([] if a.tts_review else ["--frozen"]))],
                          desc="配音+全部品管+時間軸(查 nvidia-smi);已凍結的片非 --tts-review 禁新合成(build --frozen,有快取未命中即 exit 2)"))
    if a.tts_review:   # 配音後、配音報告前:不需素材的時長預檢(同圖 >9 秒/>2 句、鏡頭最短時長、動畫步秒數/停留、動畫容量)
        steps.append(Step("時長預檢", [build("--check-only", "--timing-only", "--timeline", str(tl_tts), "--out", out_name)],
                          desc="時長預檢(build --check-only --timing-only,缺素材不算錯);錯誤>0 不中止,摘要標紅並記入 tts_review.json 的 timing_errors"))
    steps += [
        Step("檢查", [build("--check-only", "--timeline", str(tl_tts),
                            "--out", out_name, *render_opts)], desc="渲染前檢查(錯誤>0 即停)"),
        Step("渲染", [build("--no-synth", *render_opts, "--out", out_name)], desc="完整版 1080p(配音只用快取)"),
        *([Step("預覽", fn="preview", desc="720p 預覽 < 29,000,000 bytes(--preview)")] if a.preview else []),
        Step("QA圖", [[PY, RUN, "qa_sheet", str(video), str(tl), str(odir / f"qa_{ver}"), "--every", "6"]],
             desc="QA 總覽圖(每 6 秒一格)"),
        Step("配音報告", [[PY, RUN, "tts_report", tag]], desc="句間停頓診斷"),
        Step("E4耳朵", [[str(P.TTS_ENV), "-X", "utf8", str(P.REPO / "pipeline" / "senses" / "ear_e4_pinyin_ctc.py"), "--tag", tag, "--ver", ver]],
             desc="E4 拼音級耳朵(多音字/聲調/輕聲/逗號停頓旗標)寫 projects/<tag>/ear_e4_<ver>.json,優先聽清單讀它;失敗不中斷"),
        Step("優先聽", fn="listen_txt", desc="優先聽清單 listen_<ver>.txt(必聽節逐句 mm:ss|句號|原因|原文,其他節只給類別與句號)"),
        Step("優先看", fn="look_list", desc="畫面優先看清單 look_<ver>.md(時間點+原因+看什麼;失敗不中斷)"),
        Step("審閱彙整", fn="review_md", desc="聽/看/決定三節併成 review_<ver>.md(只彙整不取代三份清單;失敗不中斷)"),
        *([Step("聽審頁", fn="listen", desc="配音聽審頁 listen_<ver>.html(優先聽的句子+全部句子;--listen)")] if a.listen else []),
    ]
    if not sample:
        steps.append(Step("說明檔骨架", fn="notes", desc="re9_notes.py 產生 <ver>_說明.md(已存在不覆寫、無 spec.json 略過)"))
    if a.checks_only:
        steps = [st for st in steps if st.name in ("txt2json", "文案檢查", "英文詞對照")]
    elif a.tts_review:
        steps = [st for st in steps if st.name in ("txt2json", "文案檢查", "英文詞對照", "C0試配", "配音", "時長預檢", "配音報告", "E4耳朵")]
        if not sample:  # 樣片(--lines)只有部分句,不能當凍結依據
            steps.append(Step("審核紀錄", fn="tts_review_json", desc="寫 build/<tag>/tts_review.json(凍結門檻:script sha、品管未過/無紀錄、keys sha)"))
        steps.append(Step("唸法清單", fn="decide_list", desc="要你決定的唸法 decide_<ver>.md(cosy_terms 未驗證英文詞、未驗證讀音標注、tts_polyphone 前 15 筆;失敗不中斷)"))
        steps.append(Step("審閱彙整", fn="review_md", desc="聽/看/決定併成 review_<ver>.md(--tts-review 只有聽與決定兩節;失敗不中斷)"))
        steps.append(Step("聽審頁", fn="listen", desc="配音聽審頁 listen_<ver>.html(優先聽的句子+全部句子)"))
    elif not sample and a.title:
        steps.append(Step("交付", fn="deliver", desc="說明檔有發片資料區塊才呼叫 deliver.py 交付到下載資料夾"))

    n = len(steps)
    if a.dry_run:
        print(f"[dry-run] {tag} {ver} 聲音={a.voice} bgm={a.bgm} lines={a.lines or '全部'} 樣片={sample}")
        for i, st in enumerate(steps, 1):
            if st.fn == "preview":
                print(f"[{i}/{n}] {st.name}: ffmpeg 兩段式 scale=1280:720 -b:v <由總長算出>k (同 deliver_preview.sh) -> {prev.name}")
            elif st.fn == "prechecks":
                print(f"[{i}/{n}] {st.name}: " + " -> ".join(
                    n_ if c else f"{n_}(無 spec,略過)" for n_, c in [(x[0], x[1]) for x in precheck_cmds(tag)]))
            elif st.fn == "c0":
                print(f"[{i}/{n}] {st.name}: " + " ".join(f'"{x}"' if " " in str(x) else str(x) for x in c0_cmd(tag)))
            elif st.fn == "tts_review_json":
                print(f"[{i}/{n}] {st.name}: write_tts_review({tag}, {a.engine}) -> {FZ.review_path(tag)}")
            elif st.fn == "decide_list":
                print(f"[{i}/{n}] {st.name}: decide_list.run({tag}, {ver}) -> {odir / f'decide_{ver}.md'}")
            elif st.fn == "review_md":
                print(f"[{i}/{n}] {st.name}: review_md.run({tag}, {ver}) -> {odir / f'review_{ver}.md'}")
            elif st.fn == "listen_txt":
                print(f"[{i}/{n}] {st.name}: listen_page.make_text({tag}, {ver}) -> {odir / f'listen_{ver}.txt'}")
            elif st.fn == "look_list":
                print(f"[{i}/{n}] {st.name}: look_list.run({tag}, {ver}) -> {odir / f'look_{ver}.md'}")
            elif st.fn == "listen":
                print(f"[{i}/{n}] {st.name}: listen_page.make({tag}, {ver}) -> {odir / f'listen_{ver}.html'}")
            elif st.fn == "notes":
                c = notes_cmd(a, prefix, tl, bdir, video, prev, notes)
                print(f"[{i}/{n}] {st.name}: " + (f"{notes.name} 已存在則不覆寫;" if notes.exists() else "") +
                      ("略過(無 spec.json)" if c is None else " ".join(f'"{x}"' if " " in str(x) else str(x) for x in c)))
            elif st.fn == "deliver":
                print(f"[{i}/{n}] {st.name}: 說明檔含發片資料區塊才執行:" + " ".join(f'"{x}"' if " " in str(x) else str(x) for x in deliver_cmd(a)))
            else:
                for c in st.cmds:
                    print(f"[{i}/{n}] {st.name}: " + " ".join(f'"{x}"' if " " in str(x) else str(x) for x in c))
        g = gpu_used_mib()
        print(f"nvidia-smi 顯存已用 {g} MiB({'上限 ' + str(GPU_MAX_MIB) if GPU_MAX_MIB else '門檻關閉'});樣片不交付={sample}" + ("" if (sample or a.title) else ";無 --title 不交付"))
        return

    odir.mkdir(parents=True, exist_ok=True)
    bdir.mkdir(parents=True, exist_ok=True)
    logp = odir / f"make_{ver}.log"
    t_all = time.time()
    delivered, glock = False, None
    timing_errors, synth_tail = [], None
    with open(logp, "w", encoding="utf-8") as log:
        log.write(bgm_line + "\n")
        for i, st in enumerate(steps, 1):
            t0 = time.time()
            if st.name == "配音":  # 只有配音段上 GPU:排隊拿全機鎖(子行程 build/tts_cosy3 沿用同一把)
                glock = GL.gpu_lock(tag, "make_version配音").acquire()
                t0 = time.time()
            tail, rc = [], 0
            if st.fn == "preview":
                dur = probe_duration(video)
                for c in preview_cmds(video, prev, bdir, dur):
                    rc, tail = run_cmd(c, log)
                    if rc:
                        break
                if not rc and prev.stat().st_size >= PREVIEW_LIMIT:
                    rc, tail = 1, [f"預覽 {prev.stat().st_size} bytes >= {PREVIEW_LIMIT}"]
            elif st.fn == "prechecks":
                ok, summ, errs = run_prechecks(tag, log)
                tail = summ + errs
                if not ok:
                    rc = 1
            elif st.fn == "c0":   # C0 試配閘門:唸錯 > 0 = exit 3(同品管未過);合成不完整/崩潰 = exit 1(落到下面的失敗處理)
                rc, tail = run_cmd(c0_cmd(tag), log)
                if rc == 3:
                    log.write(f"\n[{i}/{n}] {st.name} 唸錯 {time.time() - t0:.1f}s\n")
                    print(f"[{i}/{n}] {st.name} 唸錯,已中止(未配音)")
                    print("\n".join(l for l in tail if l.startswith(("唸錯", "C0 "))))
                    print(f"改唸錯的句子後重跑;報告 projects/{tag}/c0_report.md(不可放寬別名過關;確定略過才加 --skip-c0)")
                    sys.exit(3)
            elif st.fn == "notes":
                c = notes_cmd(a, prefix, tl, bdir, video, prev, notes)
                if notes.exists():
                    tail = [f"{notes.name} 已存在,不覆寫"]
                elif c is None:
                    tail = ["略過(無 spec.json)"]
                else:
                    rc, tail = run_cmd(c, log)
            elif st.fn == "deliver":
                if has_release_block(notes):
                    prc, pout = run_cmd(persona_cmd(tag, notes), log)
                    if prc:  # 封面人像跨片重複有錯誤:不交付,exit 0
                        cmd_s = " ".join(f'"{x}"' if " " in str(x) else str(x) for x in deliver_cmd(a))
                        tail = ["未交付:封面人像跨片重複檢查有錯誤 → 改說明檔方案1/3 主體(SOP §4)後跑 " + cmd_s] + [l for l in pout if "錯誤" in l or "警告:" in l]
                        log.write("\n" + tail[0] + "\n")
                    else:
                        rc, tail = run_cmd(deliver_cmd(a), log)
                        if not rc:
                            delivered = True
                            run_cmd(persona_cmd(tag, notes, record=True), log)  # 交付成功才登錄人像紀錄
                else:
                    cmd_s = " ".join(f'"{x}"' if " " in str(x) else str(x) for x in deliver_cmd(a))
                    tail = [f"未交付:說明檔缺發片資料區塊 → 補完後跑 {cmd_s}"]
                    log.write("\n" + tail[0] + "\n")
            elif st.name == "E4耳朵":   # 旗標耳朵失敗不中斷整版:優先聽清單少 E4 原因而已
                rc, tail = run_cmd(st.cmds[0], log)
                if rc:
                    tail, rc = [f"E4耳朵失敗(不中斷): {tail[-1] if tail else ''}"], 0
                    log_warn(tag, "C21 E4耳朵", tail[0])
            elif st.name == "時長預檢":   # 錯誤不中止其他步:記下來,摘要標紅,審核紀錄寫 timing_errors
                rc, tail = run_cmd(st.cmds[0], log)
                timing_errors, rc = timing_errors_of(rc, tail), 0
            elif st.fn == "tts_review_json":
                try:
                    ns = parse_new_synth(synth_tail)
                    if ns is None:
                        print("警告:配音輸出找不到「新合成 N 個」字樣(或略過配音),tts_review.json 的 new_synth 寫 null")
                    rp, rv = write_tts_review(tag, a.engine, timing_errors, ns)
                    bad = rv['failed'] or rv['no_qc'] or rv['timing_errors']
                    tail = [f"tts_review.json:{rv['units']} 單位|品管未過 {len(rv['failed'])}|無紀錄 {len(rv['no_qc'])}|"
                            f"時長預檢錯誤 {len(rv['timing_errors'])}|"
                            f"keys {rv['tts_keys_sha'][:10]}…|{'可凍結' if not bad else '尚不可凍結(清到 0 才能 freeze.py)'}"]
                except Exception as e:
                    rc, tail = 1, [f"{type(e).__name__}: {e}"]
                log.write("\n[審核紀錄] " + "\n".join(tail) + "\n")
            elif st.fn == "listen_txt":
                try:
                    tail = [LP.make_text(tag, ver)]
                except Exception as e:   # 清單寫檔失敗不中斷整版(C22)
                    tail = [f"優先聽清單失敗(不中斷): {type(e).__name__}: {e}"]
                    log_warn(tag, "C22 優先聽", tail[0])
                log.write("\n[優先聽] " + "\n".join(tail) + "\n")
            elif st.fn == "decide_list":
                try:
                    tail = [DL.run(tag, ver)]
                except Exception as e:   # 清單失敗不中斷整版
                    tail = [f"唸法清單失敗(不中斷): {type(e).__name__}: {e}"]
                    log_warn(tag, "C23 唸法清單", tail[0])
                log.write("\n[唸法清單] " + "\n".join(tail) + "\n")
            elif st.fn == "look_list":
                try:
                    tail = [LK.run(tag, ver)]
                except Exception as e:   # 清單失敗不中斷整版
                    tail = [f"優先看清單失敗(不中斷): {type(e).__name__}: {e}"]
                    log_warn(tag, "D26 優先看", tail[0])
                log.write("\n[優先看] " + "\n".join(tail) + "\n")
            elif st.fn == "review_md":
                try:
                    if a.tts_review:   # --tts-review 沒有「優先聽」步驟:先補出純文字清單(用 timeline_tts),聽節才有內容
                        LP.make_text(tag, ver, prefer_tts=True)
                    tail = [RV.run(tag, ver)]
                except Exception as e:   # 彙整失敗不中斷整版
                    tail = [f"審閱彙整失敗(不中斷): {type(e).__name__}: {e}"]
                    log_warn(tag, "審閱彙整", tail[0])
                log.write("\n[審閱彙整] " + "\n".join(tail) + "\n")
            elif st.fn == "listen":
                try:
                    tail = [LP.make(tag, ver, prefer_tts=a.tts_review)]
                except Exception as e:  # 聽審頁寫檔失敗不中斷整版(C24;已有清單與品管紀錄,頁面只是方便聽)
                    tail = [f"聽審頁失敗(不中斷): {type(e).__name__}: {e}"]
                    log_warn(tag, "C24 聽審頁", tail[0])
                log.write("\n[聽審頁] " + "\n".join(tail) + "\n")
            else:
                if st.name == "檢查" and not a.tts_review and not sample:   # C15:完整渲染前,品管未過且未凍結 = 中止(已凍結即定案)
                    qmsg = qc_gate_problems(tag)
                    if qmsg:
                        log.write("\n[C15] " + "\n".join(qmsg) + "\n")
                        print("\n".join(qmsg))
                        sys.exit(1)
                for c in st.cmds:
                    rc, tail = run_cmd(c, log)
                    if rc:
                        break
                if st.name == "配音":
                    synth_tail = tail
            dt = time.time() - t0
            if glock:
                glock.release()
                glock = None
            log.write(f"\n[{i}/{n}] {st.name} {'失敗' if rc else 'OK'} {dt:.1f}s\n")
            log.flush()
            if rc:
                print(f"[{i}/{n}] {st.name} 失敗({dt:.0f}s),完整 log: {logp}")
                if st.name == "文案檢查":
                    print("\n".join(tail))
                    print("文案檢查有錯誤,已中止(未配音)。緊急可加 --skip-checks")
                elif st.name == "英文詞對照":
                    print("\n".join(tail))
                    print("英文詞對照有錯誤,已中止(未配音)。未登錄詞請決定唸法後登錄 pipeline\\say_terms.json 並在 script.txt 加 @say;緊急可加 --skip-checks"
                          if a.engine == "chattts" else "英文詞對照有錯誤,已中止(未配音)。未登錄詞請決定寫法後登錄 pipeline\\cosy_terms.json(直接唸英文放 _direct);緊急可加 --skip-checks")
                elif st.name == "檢查":
                    errs = [l for l in tail if "錯誤" in l]
                    print("\n".join((errs or tail)[-15:]))
                elif st.name == "渲染":   # D20:成片音軌缺口 build 回結束碼 1(檔留著);不出 QA 圖與交付
                    errs = [l for l in tail if "錯誤" in l]
                    print("\n".join((errs or tail)[-15:]))
                    print("渲染結束碼非 0,已中止(未出 QA 圖、未交付);成片檔留在 output 供查")
                else:
                    print("\n".join(tail[-15:]))
                sys.exit(1)
            if st.name in ("文案檢查", "英文詞對照"):
                print(f"[{i}/{n}] {st.name} OK {dt:.0f}s")
                print("\n".join(tail))
                continue
            if st.name == "時長預檢" and timing_errors:   # 摘要標紅(ANSI);錯誤清單列在下面
                print(f"\033[31m[{i}/{n}] {st.name} 錯誤 {len(timing_errors)}(改稿/拆句後重跑 --tts-review;不清完不能凍結){dt:.0f}s\033[0m")
                print("\n".join(f"\033[31m  {e}\033[0m" for e in timing_errors[:15]))
                if len(timing_errors) > 15:
                    print(f"\033[31m  …另 {len(timing_errors) - 15} 項(見 {logp})\033[0m")
                continue
            print(f"[{i}/{n}] {st.name} OK {dt:.0f}s | {summarize(st, tail, video, prev, tl)}")
        if a.skip_checks:
            print("!!! 已用 --skip-checks 略過文案檢查(script_lint/sub_scan/spec_check)!!!")
        if a.checks_only:
            print(f"--checks-only:{tag} 檢查階段結束(未配音、未渲染)")
            return
        if a.tts_review:
            frozen, fz_problems = False, []
            if a.freeze:
                fz_problems = FZ.review_problems(tag)
                if not fz_problems:
                    try:
                        rec = FZ.freeze(tag, reason="自動凍結:品管未過 0、時長預檢 0、配音鍵已記")
                        frozen = True
                        print(f"已自動凍結 {tag}:narration_sha {rec['narration_sha'][:12]}… -> {FZ.freeze_path(tag)}")
                    except Exception as e:  # noqa: BLE001
                        fz_problems = [f"凍結失敗:{type(e).__name__}: {e}"]
            board_after(tag, a, sample, delivered, frozen=frozen)
            print(f"--tts-review:{tag} 配音與聽審頁完成(未渲染)| {odir / ('listen_' + ver + '.html')} | 配音皆未聽審")
            if fz_problems:
                print(f"--freeze:{tag} 不能自動凍結:")
                print("\n".join(f"  - {x}" for x in fz_problems))
                sys.exit(3)
            return
    if a.skip_checks:
        print("!!! 本版未跑文案檢查(--skip-checks)!!!")
    with open(logp, "a", encoding="utf-8") as lg:
        lg.write(f"\n[總計] {time.time() - t_all:.1f}s\n")
    print(f"完成 {tag} {ver}(共 {time.time() - t_all:.0f}s)| 完整版 {video} | {('預覽 ' + str(prev) + ' | ') if a.preview else ''}QA {odir / ('qa_' + ver)}_NN.png | log {logp}")
    board_after(tag, a, sample, delivered)
    if sample:
        print("樣片:未交付到下載資料夾。配音皆未聽審,邊緣句看 build\\%s\\tts_qc.json / tts_report" % tag)
    elif not a.title:
        print("未交付:要交付到下載資料夾請加 --title <中文片名>(或另跑 deliver.py)")


def summarize(st, tail, video, prev, tl):
    """每步一行摘要(取輸出中有意義的最後一行或檔案大小)。"""
    if st.name == "渲染":
        return f"{video.stat().st_size / 1e6:.1f} MB {probe_duration(video):.1f}s"
    if st.name == "時長預檢":
        return next((l.strip()[-120:] for l in reversed(tail) if "時長預檢" in l), "無錯誤")
    if st.name == "C0試配":
        return next((l.strip() for l in tail if l.startswith("C0 ")), "完成")[:140]
    if st.name in ("聽審頁", "優先聽", "優先看", "審閱彙整", "審核紀錄", "唸法清單", "E4耳朵"):
        return tail[-1] if tail else "完成"
    if st.name == "預覽":
        return f"{prev.stat().st_size / 1e6:.2f} MB (< {PREVIEW_LIMIT / 1e6:.0f})"
    if st.name == "檢查":
        return next((l.strip()[-120:] for l in reversed(tail) if "渲染前檢查" in l), "無錯誤")
    keys = {"txt2json": "句數", "配音": "配音", "QA圖": "", "配音報告": "", "交付": "", "說明檔骨架": ""}
    key = keys.get(st.name, "")
    cand = [l.strip() for l in tail if l.strip() and (not key or key in l)]
    return (cand[-1] if cand else "完成")[:140]


if __name__ == "__main__":
    main()
