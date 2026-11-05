#!/usr/bin/env python3
r"""配音聽審頁:把「請優先聽」的配音單位挑出來,每句一個播放鈕、原文、成片時間點、勾選「不行」與備註,產生靜態 HTML。

python pipeline/run.py listen_page --tag re9_online --ver v1
輸入:build/<tag>/tts_qc.json(每個配音單位的品管紀錄)、build/<tag>/timeline.json(沒有則 timeline_tts.json)、tts 快取內的 *.trim.wav
輸出:output/<tag>/listen_<ver>.html、output/<tag>/listen_<ver>_audio/<單位>.mp3(64k;HTML 用相對路徑)
配音單位 = 品管單位:單句行 = 句編號;一行拆成子句者 = "句.子句序"(與 tts_qc.json 的 idx 相同)。音檔用「裁切後實際進影片」的 trim.wav。

請優先聽的條件(2026-10-14 F1-2:只列真的需要人聽的句子;命中任一項才列,其餘句子收進摺疊的「其他句子」,仍可點播):
  門檻(模組常數):
  - 聲紋(相對值,兩者任一):spk_sim < 該句 spk_thr + SPK_EDGE_MARGIN(0.06),或 spk_sim < 全片 spk_sim 中位數 - SPK_MEDIAN_DROP(0.12)
  - 語速未過:rate_ok 為 False,或 |rate_dev| >= RATE_FAIL(0.12 = 品管語速門檻)
  - 句尾未過:tail_ok 為 False
  - 句尾硬切:hard_cut 為真
  - 品管未過:passed 為 False(final 紀錄理應沒有,留作保險)
  - CosyVoice3(紀錄有 engine=cosy3 的欄位):用到未聽審的讀音標注(cosy_pron_unverified)或英文唸法(cosy_en_unverified)、
    陳述句句尾斜率 > TAIL_RISE_EDGE(8 半音/秒,品管門檻 12)
  - g2pW 第三意見不一致:g2p_disagree 非空(g2pW 與規則表對某個多音字的讀音不同;T3,2026-10-27,只當提醒,不代表誰對)
  - 副辨識不一致:asr2_bad 為真(Fun-ASR-Nano 與文案不符、重錄後仍不一致;2026-10-21)
  - 語境讀音記憶待聽:這句命中 state=undetermined 的記憶(C0 測過但辨識看不出,pron_memory.py)
  - 逗號靠插入:這句有逗號是後處理插靜音補的(模型原本幾乎沒停,tts_pause.comma_inserted;頓號不算;2026-10-31)
  - E4 耳朵旗標:projects/<tag>/ear_e4_<ver>.json 該句有 flags(poly/garble/particle/runon;子句 "12.1" 以整句 12 比對;檔案不在則略過;2026-10-31)
  例外(CLAUDE.md 既有規則,一律列):含 Steam / 句尾是英文字母 / 書名號內有冒號的遊戲名(《X:Y》)/ 因品管重錄達 RETRY_LIST_MIN 次
分層(2026-10-31,Phase 3 項 4):命中的句子再分兩層。必聽(MUST_CATS)= E4 耳朵 poly/particle/runon + 品管邊緣(品管未過、句尾未過、句尾硬切、
  副辨識不一致、重錄達 RETRY_LIST_MIN 次);其他待聽 = 其餘命中者(聲紋貼近門檻、語速、句尾上揚、讀音記憶待聽、逗號靠插入、g2p 不一致、
  未聽審標注/英文唸法、Steam/英文句尾/書名號冒號、E4 garble)。listen_<ver>.txt 必聽節在最前(逐句列),其他節只給類別、句數與句號;
  HTML 必聽在最前,其他待聽折疊。
"""
import argparse
import html
import json
import re
import statistics
import subprocess
import sys

import paths as P
import pron_memory as PM
import tts_pause as TP

SPK_EDGE_MARGIN = 0.06  # spk_sim < 該句品管 spk_thr + 此值 -> 貼近門檻,列入
SPK_MEDIAN_DROP = 0.12  # spk_sim < 全片中位數 - 此值 -> 明顯偏離全片,列入(與上一條取聯集 = 取寬)
RATE_FAIL = 0.12        # |rate_dev| 達此值視為語速未過(與 tts_chattts 品管門檻相同)
TAIL_RISE_EDGE = 8.0    # CosyVoice3:陳述句句尾 F0 斜率超過此值(品管門檻 12 半音/秒)列入
RETRY_LIST_MIN = 6      # 換 seed 重錄達這個次數才列入(2026-10-11:原本重錄 1 次就列,dei v1 的 169 句列了 110 句)
TAIL_STRIP = "。?!?!,,、;;::…」』》)) \"'“”？！，：；）"
BOOK_COLON = re.compile(r"《[^》]*[:：][^》]*》")
# 優先聽分層(Phase 3 項 4,2026-10-31):必聽 = E4 耳朵 poly/particle/runon + 品管邊緣;其餘命中的句子 = 其他待聽(不必逐句聽)。
# 品管邊緣 = 品管未過(qc_fail,passed 為 False)、句尾未過(tail,tail_ok 為 False)、句尾硬切(hard_cut)、副辨識不一致(asr2,asr2_bad)、
#            品管重錄達 RETRY_LIST_MIN 次(retry,max(retries, rate_retried))。聲紋貼近門檻、語速、句尾上揚、讀音記憶待聽、逗號靠插入、
#            g2p 不一致、未聽審標注/英文唸法、Steam/英文句尾/書名號冒號、E4 garble 等 = 其他。
MUST_CATS = ("qc_fail", "tail", "hard_cut", "asr2", "retry", "e4")
E4_MUST_KINDS = ("poly", "particle", "runon")
CAT_LABEL = {"spk_thr": "聲紋貼近門檻", "spk_med": "聲紋偏低", "rate": "語速", "tail_rise": "句尾上揚", "cosy_pron": "讀音標注未聽審",
             "cosy_en": "英文唸法未聽審", "term_listen": "英文詞辨識不像", "g2p_disagree": "g2p 不一致", "mem_pending": "讀音記憶待聽",
             "comma_insert": "逗號靠插入", "steam": "含 Steam", "en_tail": "句尾英文", "book_colon": "書名號冒號", "e4_other": "E4 其他旗標",
             "director_decided": "唸法 director 已決(抽聽)", "qc_fail": "品管未過", "tail": "句尾未過", "hard_cut": "句尾硬切", "asr2": "副辨識不一致", "retry": "重錄多次", "e4": "E4 耳朵"}


def mmss(t):
    t = max(0.0, float(t))
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def trim_wav(tts_dir, rec):
    """單位的 trim.wav:單句行在 tts/<句3位>.trim.wav,子句在 tts/sub/<音檔鍵>.trim.wav(鍵 = rec['key'] 去掉 |版本)。"""
    idx = str(rec["idx"])
    if "." in idx:
        return tts_dir / "sub" / (str(rec["key"]).split("|")[0] + ".trim.wav")
    return tts_dir / f"{int(idx):03d}.trim.wav"


def unit_time(tl_lines, idx):
    """成片時間點(秒):子句取子句起點,否則取該行起點。"""
    s = str(idx)
    line_no, _, k = s.partition(".")
    ln = tl_lines.get(int(line_no))
    if not ln:
        return None
    cl = ln.get("clauses")
    if k and cl and int(k) <= len(cl):
        return cl[int(k) - 1]["start"]
    return ln["start"]


def g2p_text(d):
    """g2p_disagree 一項(tts_g2p.compare 的 dict:ch/pos/rule/g2p)-> 「字(規則 xx / g2pW yy)」;容忍舊/殘缺紀錄。"""
    if not isinstance(d, dict):
        return str(d)
    return f"{d.get('ch', '?')}(規則 {d.get('rule', '?')} / g2pW {d.get('g2p', '?')})"


def memory_pending(text):
    """這句命中 undetermined 記憶的位置 -> ["穿著打", …](表空不載讀音表)。"""
    if not PM.has_entries():
        return []
    import tts_cosy_text as CT
    return [PM.ctx_label(e) for _, e in PM.scan(CT.pron_source(text)) if e["state"] == "undetermined"]


def e4_items(tag, ver):
    """讀 projects/<tag>/ear_e4_<ver>.json -> {整句idx(int): [(kind, "poly 為(wei4→bei4)"), …]};無檔/壞檔回 {}。"""
    if not tag or not ver:
        return {}
    f = P.PROJECTS / tag / f"ear_e4_{ver}.json"
    try:
        res = json.loads(f.read_text(encoding="utf-8")).get("results", {})
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in res.items():
        parts = []
        for fl in v.get("flags") or []:
            kind = fl.get("kind", "?")
            if kind in ("poly", "garble", "particle"):
                parts.append((kind, f"{kind} {fl.get('char', '')}({fl.get('expected', '?')}→{fl.get('heard', '?')})"))
            else:
                parts.append((kind, f"{kind} {fl.get('char', '')}後沒停" if kind == "runon" else f"{kind} {fl.get('char', '')}"))
        if parts:
            out.setdefault(int(str(k).split(".")[0]), []).extend(parts)
    return out


def e4_flags(tag, ver):
    """同 e4_items,但每句合成一段文字 {整句idx(int): "poly 為(wei4→bei4);runon 市後沒停"}。"""
    return {i: ";".join(t for _, t in its) for i, its in e4_items(tag, ver).items()}


def _decided_lines(tag, ver):
    """{句號: [鍵(來源)]}:projects/<tag>/decide_<ver>.json 的 director 已決定唸法;沒有檔或讀不出 = {}(不影響舊片)。"""
    if not (tag and ver):
        return {}
    try:
        import decide_list as DL
        return DL.decided_lines(tag, ver)
    except Exception:  # noqa: BLE001
        return {}


def pick_reasons(recs, tag=None, ver=None):
    """回傳 {單位idx: [(類別, 說明)…]};沒命中任何門檻或例外的單位不在結果裡。tag/ver 給了才併入 E4 耳朵旗標。"""
    out = {}
    e4 = e4_items(tag, ver)
    dec = _decided_lines(tag, ver)
    sims =[r["spk_sim"] for r in recs if r.get("spk_sim") is not None]
    med = statistics.median(sims) if sims else None
    thrs = [r["spk_thr"] for r in recs if r.get("spk_thr") is not None]
    med_thr = statistics.median(thrs) if thrs else None
    for r in recs:
        why = []
        text = r.get("text", "")
        if r.get("passed") is False:
            why.append(("qc_fail", "品管未過:" + "/".join(r.get("fails") or [])))
        sim = r.get("spk_sim")
        if sim is not None:
            thr = r.get("spk_thr") if r.get("spk_thr") is not None else med_thr
            if thr is not None and sim < thr + SPK_EDGE_MARGIN:
                why.append(("spk_thr", f"聲紋貼近門檻({sim:.2f} / 門檻 {thr:.2f})"))
            if med is not None and sim < med - SPK_MEDIAN_DROP:
                why.append(("spk_med", f"聲紋明顯低於全片中位數({sim:.2f} / 中位 {med:.2f})"))
        dev = r.get("rate_dev") or 0
        if r.get("rate_ok") is False or abs(dev) >= RATE_FAIL:
            why.append(("rate", f"語速未過(偏差 {dev:+.0%})"))
        if r.get("tail_ok") is False:
            why.append(("tail", "句尾未過"))
        if r.get("hard_cut"):
            why.append(("hard_cut", "句尾硬切"))
        if r.get("cosy_pron_unverified"):
            why.append(("cosy_pron", "讀音標注未聽審:" + "、".join(r["cosy_pron_unverified"])))
        if r.get("cosy_en_unverified"):
            why.append(("cosy_en", "英文唸法未聽審:" + "、".join(r["cosy_en_unverified"])))
        if r.get("term_listen"):
            why.append(("term_listen", "英文詞辨識寫法不像原詞(跨句無多數,未擋):" + "、".join(f"{x['term']}「{x['got']}」" for x in r["term_listen"])))
        if r.get("g2p_disagree"):
            why.append(("g2p_disagree", "g2pW 與規則表讀音不一致:" + "、".join(g2p_text(d) for d in r["g2p_disagree"])))
        pending = memory_pending(text)
        if pending:
            why.append(("mem_pending", "讀音記憶待聽(測過但看不出):" + "、".join(pending)))
        inserted = TP.comma_inserted(r)
        if inserted:
            why.append(("comma_insert", "逗號靠插入:" + "、".join(inserted)))
        if r.get("asr2_bad"):
            why.append(("asr2", f"副辨識不一致(Fun-ASR 聽成「{r.get('asr2') or ''}」,相似度 {r.get('asr2_sim')})"))
        ts = r.get("tail_slope")
        if r.get("statement") and ts is not None and ts > TAIL_RISE_EDGE:
            why.append(("tail_rise", f"句尾略上揚({ts:+.0f} 半音/秒,門檻 12)"))
        if re.search(r"steam", text, re.I):
            why.append(("steam", "含 Steam(英文唸法不穩)"))
        t = text.rstrip(TAIL_STRIP)
        if t and re.match(r"[A-Za-z]", t[-1]):
            why.append(("en_tail", "句尾是英文"))
        if BOOK_COLON.search(text):
            why.append(("book_colon", "書名號內有冒號的遊戲名"))
        n_re = max(r.get("retries") or 0, r.get("rate_retried") or 0)
        if n_re >= RETRY_LIST_MIN:
            why.append(("retry", f"品管重錄過(換 seed {n_re} 次)"))
        e4t = e4.get(int(str(r["idx"]).split(".")[0]))
        if e4t:   # poly/particle/runon = 必聽(類別 e4);只有 garble 等其他旗標 = 其他(e4_other)
            why.append(("e4" if any(k in E4_MUST_KINDS for k, _ in e4t) else "e4_other", "E4耳朵:" + ";".join(t for _, t in e4t)))
        dl = dec.get(int(str(r["idx"]).split(".")[0]))
        if dl:   # P5:唸法清單由 director 決定並登錄,這些句列進優先聽(其他待聽)給使用者想抽聽用
            why.append(("director_decided", "唸法由 director 決定(抽聽):" + "、".join(dl)))
        if why:
            out[r["idx"]] = why
    return out


def is_must(why):
    """這句的原因清單 [(類別, 說明)…] 有沒有命中必聽類別(MUST_CATS)。"""
    return any(c in MUST_CATS for c, _ in why)


def tier_split(items, reasons):
    """items = [(秒, rec, …)](rec 有 idx)已依時間排好 -> (必聽 list, 其他待聽 list, 沒列入的 list);reasons = pick_reasons 結果。"""
    must = [x for x in items if x[1]["idx"] in reasons and is_must(reasons[x[1]["idx"]])]
    other = [x for x in items if x[1]["idx"] in reasons and not is_must(reasons[x[1]["idx"]])]
    rest = [x for x in items if x[1]["idx"] not in reasons]
    return must, other, rest


def other_summary(rows, reasons):
    """其他待聽句的類別彙整 -> [(類別標籤, [句號…])];一句多類別各算一次,依句數多到少。rows = [(秒, rec)]。"""
    by = {}
    for _t, r in rows:
        for c in dict.fromkeys(c for c, _ in reasons[r["idx"]]):
            by.setdefault(CAT_LABEL.get(c, c), []).append(r["idx"])
    return sorted(by.items(), key=lambda kv: -len(kv[1]))


def summarize(recs, reasons):
    """各類別命中句數 {類別: n}(一句可命中多類)。"""
    c = {}
    for ws in reasons.values():
        for k in {k for k, _ in ws}:
            c[k] = c.get(k, 0) + 1
    return c


def to_mp3(wav, mp3):
    if mp3.exists() and mp3.stat().st_mtime >= wav.stat().st_mtime:
        return
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1",
                        "-c:a", "libmp3lame", "-b:a", "64k", str(mp3)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg 轉 mp3 失敗 {wav.name}: {r.stderr.strip()[-200:]}")


CSS = """
body{background:#15202b;color:#e7e9ea;font-family:'Microsoft JhengHei',sans-serif;margin:0;padding:24px 28px 90px;max-width:960px;margin:auto}
h1{font-size:24px;margin:0 0 6px}h2{font-size:19px;margin:28px 0 10px;border-bottom:1px solid #38444d;padding-bottom:6px}
.warn{background:#5a1f1f;border:1px solid #ff4d4d;color:#ffd7d7;padding:8px 12px;border-radius:6px;margin:10px 0;font-weight:bold}
.meta{color:#8b98a5;font-size:14px}
.u{background:#1e2732;border:1px solid #38444d;border-radius:8px;padding:10px 14px;margin:10px 0}
.u.bad{border-color:#ff4d4d;background:#2a2227}
.hd{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
.tm{font-family:Consolas,monospace;color:#f4c542;font-size:17px}.id{color:#8b98a5;font-size:13px}
.tx{font-size:18px;margin:6px 0;line-height:1.5}
.why{color:#ffb454;font-size:14px;margin-bottom:6px}
audio{width:100%;height:36px}
.row{display:flex;gap:12px;align-items:center;margin-top:6px}
.row label{white-space:nowrap;font-weight:bold;color:#ff8a8a;cursor:pointer}
.row input[type=text]{flex:1;background:#15202b;color:#e7e9ea;border:1px solid #38444d;border-radius:4px;padding:5px 8px;font-size:14px}
details{margin-top:24px}summary{cursor:pointer;font-size:19px;padding:6px 0}
.bar{position:fixed;left:0;right:0;bottom:0;background:#0d141b;border-top:1px solid #38444d;padding:10px 28px;display:flex;gap:14px;align-items:center}
button{background:#1d9bf0;color:#fff;border:0;border-radius:18px;padding:8px 20px;font-size:15px;cursor:pointer}
#st{color:#8b98a5;font-size:14px}
"""

JS = """
function sel(){return [...document.querySelectorAll('.u')].filter(u=>u.querySelector('input[type=checkbox]').checked);}
function cnt(){document.getElementById('st').textContent='已勾 '+sel().length+' 句';}
document.addEventListener('change',cnt);
async function copyOut(){
  const t=sel().map(u=>'['+u.dataset.tm+'] 單位'+u.dataset.id+' 「'+u.dataset.tx+'」'+(u.querySelector('input[type=text]').value?' - '+u.querySelector('input[type=text]').value:'')).join('\\n');
  const out=t?('配音聽審「不行」('+sel().length+' 句):\\n'+t):'(沒有勾選)';
  try{await navigator.clipboard.writeText(out);}catch(e){const a=document.createElement('textarea');a.value=out;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove();}
  document.getElementById('st').textContent='已複製 '+sel().length+' 句到剪貼簿';
}
document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(b!==a)b.pause();})));
"""


def card(rec, tm, why, mp3rel):
    e = html.escape
    cls = "u bad" if rec.get("passed") is False else "u"
    why_html = f'<div class="why">列入原因:{e(";".join(w for _, w in why))}</div>' if why else ""
    return (f'<div class="{cls}" data-id="{e(str(rec["idx"]))}" data-tm="{mmss(tm) if tm is not None else "--:--"}" '
            f'data-tx="{e(rec["text"], quote=True)}">'
            f'<div class="hd"><span class="tm">{mmss(tm) if tm is not None else "--:--"}</span>'
            f'<span class="id">單位 {e(str(rec["idx"]))}</span></div>'
            f'<div class="tx">{e(rec["text"])}</div>{why_html}'
            f'<audio controls preload="none" src="{e(mp3rel)}"></audio>'
            f'<div class="row"><label><input type="checkbox"> 不行</label><input type="text" placeholder="備註(哪裡怪)"></div></div>')


def make(tag, ver, prefer_tts=False):
    """產生聽審頁;回傳一行摘要。prefer_tts:時間點取 timeline_tts.json(只配音未渲染時,timeline.json 可能是舊版)。"""
    bd, od = P.build_dir(tag), P.output_dir(tag)
    qc = json.loads((bd / "tts_qc.json").read_text(encoding="utf-8"))
    recs = qc["records"]
    tlf = bd / "timeline.json"
    if prefer_tts or not tlf.exists():
        tlf = bd / "timeline_tts.json"
    tl = json.loads(tlf.read_text(encoding="utf-8"))
    tl_lines = {ln["idx"]: ln for ln in tl["lines"]}
    # --lines 的樣片只有部分句子:取時間軸裡有的單位
    recs = [r for r in recs if int(str(r["idx"]).split(".")[0]) in tl_lines]
    reasons = pick_reasons(recs, tag, ver)

    adir = od / f"listen_{ver}_audio"
    adir.mkdir(parents=True, exist_ok=True)
    tts_dir = P.tts_dir(tag)
    items = []
    for r in recs:
        wav = trim_wav(tts_dir, r)
        if not wav.exists():
            raise FileNotFoundError(f"找不到配音快取 {wav}")
        name = "u" + str(r["idx"]).replace(".", "_").rjust(3, "0") + ".mp3"
        to_mp3(wav, adir / name)
        items.append((unit_time(tl_lines, r["idx"]) or 0.0, r, f"listen_{ver}_audio/{name}"))
    items.sort(key=lambda x: x[0])
    pri, other, rest = tier_split(items, reasons)

    pct = len(pri) / len(items) if items else 0.0
    body = [f"<h1>配音聽審:{html.escape(tag)} {html.escape(ver)}</h1>",
            '<div class="warn">配音未經人耳聽審:以下挑選只依品管數值與規則,請實際聽過。</div>',
            f'<div class="meta">共 {len(items)} 個配音單位(一個句子一個單位);必聽 {len(pri)} 句({pct:.0%}),其他待聽 {len(other)} 句(折疊);'
            f'品管版本 {html.escape(str(qc.get("qc_ver")))};時間點為成片 mm:ss。聽到不對就勾「不行」,最後按底下按鈕複製結果貼回聊天室。</div>',
            f"<h2>必聽({len(pri)} 句:E4 耳朵 poly/particle/runon、品管邊緣)</h2>"]
    body += [card(r, t, reasons[r["idx"]], m) for t, r, m in pri] or ["<div class='meta'>(沒有)</div>"]
    if other:
        body.append(f"<details><summary>其他待聽({len(other)} 句:語速、讀音記憶待聽、逗號靠插入等,不必逐句聽)</summary>")
        body += [card(r, t, reasons[r["idx"]], m) for t, r, m in other]
        body.append("</details>")
    body.append(f"<details><summary>其他句子({len(rest)} 句)</summary>")
    body += [card(r, t, [], m) for t, r, m in rest]
    body.append("</details>")
    page = (f'<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8"><title>配音聽審 {html.escape(tag)} {html.escape(ver)}</title>'
            f'<style>{CSS}</style></head><body>' + "\n".join(body) +
            '<div class="bar"><button onclick="copyOut()">複製勾選結果</button><span id="st">已勾 0 句</span></div>'
            f"<script>{JS}</script></body></html>")
    out = od / f"listen_{ver}.html"
    out.write_text(page, encoding="utf-8")
    return f"必聽 {len(pri)}/其他待聽 {len(other)}/總 {len(items)}({pct:.0%}) | {out}"


MUST_HEAD, OTHER_HEAD = "## 必聽", "## 其他"


def text_lines(tl_lines, recs, reasons):
    """純文字清單內容(list of str):必聽節每行 `mm:ss|句號|原因|句子原文`(依時間);其他節只列「類別(句數):句號,…」。
    判定同 make(pick_reasons / tier_split)。"""
    rows = sorted(((unit_time(tl_lines, r["idx"]) or 0.0, r) for r in recs if r["idx"] in reasons), key=lambda x: x[0])
    must = [x for x in rows if is_must(reasons[x[1]["idx"]])]
    other = [x for x in rows if not is_must(reasons[x[1]["idx"]])]
    lines = [f"{MUST_HEAD}({len(must)} 句:E4 耳朵 poly/particle/runon、品管邊緣;請逐句聽)"]
    lines += [f"{mmss(t)}|{r['idx']}|{';'.join(w for _, w in reasons[r['idx']])}|{r.get('text', '')}" for t, r in must]
    lines.append(f"{OTHER_HEAD}({len(other)} 句:語速、讀音記憶待聽、逗號靠插入等;不必逐句聽,有空抽聽。下列為類別(句數):句號)")
    lines += [f"{lab}({len(ids)}):{','.join(str(i) for i in ids)}" for lab, ids in other_summary(other, reasons)]
    return lines, len(must), len(other)


def make_text(tag, ver, prefer_tts=False):
    """只輸出「請優先聽」純文字清單 output/<tag>/listen_<ver>.txt(不出 HTML、不轉 mp3);
    「## 必聽」節在最前,每行 `mm:ss|句號|原因|句子原文`;「## 其他」節只給類別、句數與句號。判定同 make(pick_reasons)。回傳一行摘要。"""
    bd, od = P.build_dir(tag), P.output_dir(tag)
    qc = json.loads((bd / "tts_qc.json").read_text(encoding="utf-8"))
    tlf = bd / "timeline.json"
    if prefer_tts or not tlf.exists():
        tlf = bd / "timeline_tts.json"
    tl = json.loads(tlf.read_text(encoding="utf-8"))
    tl_lines = {ln["idx"]: ln for ln in tl["lines"]}
    recs = [r for r in qc["records"] if int(str(r["idx"]).split(".")[0]) in tl_lines]
    reasons = pick_reasons(recs, tag, ver)
    lines, n_must, n_other = text_lines(tl_lines, recs, reasons)
    out = od / f"listen_{ver}.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"必聽 {n_must}/其他待聽 {n_other}/總 {len(recs)} | {out}"


def main():
    ap = argparse.ArgumentParser(description="產生配音聽審頁(見檔頭說明)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ver", required=True)
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    print(make(a.tag, a.ver))


if __name__ == "__main__":
    main()
