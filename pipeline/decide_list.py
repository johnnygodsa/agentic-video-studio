#!/usr/bin/env python3
r"""唸法清單(PLAN_TTS_FLOW T5 / R4):--tts-review 時列出「要使用者決定的唸法」,寫 output\<tag>\decide_<ver>.md。
python -X utf8 pipeline\decide_list.py <tag> <ver>        (讀 <tag>\script.json;不配音、不用 GPU;破音字掃描要 build\<tag>\tts_qc.json)

三類(都只列、不改任何判定,不擋其他步驟):
  ① 英文唸法:本片用到、在 cosy_terms.json 有登錄(含 _direct)但不在 cosy_terms._verified 的英文詞。
  ② 讀音標注:本片送配音文字命中、且未定案的條目:
       cosy_pron.json 的詞 -> 不在 cosy_pron._verified;
       pron_rules.json 的規則 -> 不在 pron_rules._verified(鍵 = 命中鍵「詞→標注」「字→標注」;新增規則預設未驗),或規則/預設標了 unverified。
  ③ 疑似誤讀:tts_polyphone.py(tts_env_chattts)前 15 筆;沒跑成記一行「未跑:原因」。
使用者定案後:英文詞加進 cosy_terms.json 的 _verified;讀音詞加進 cosy_pron.json 的 _verified;規則鍵加進 pron_rules.json 的 _verified(皆主對話寫入,附日期說明)。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paths as P  # noqa: E402
import terms_check as TC  # noqa: E402
import tts_cosy_text as CT  # noqa: E402
import tts_terms  # noqa: E402

TOP_N = 15
POLY_TIMEOUT = 600


def _add(d, key, idx, text, **extra):
    e = d.setdefault(key, dict(lines=[], sample=text, **extra))
    if idx not in e["lines"]:
        e["lines"].append(idx)


def en_undecided(texts):
    """① 英文詞:{詞: {lines, sample, say}};say = cosy_terms 登錄的寫法(_direct = None,直接唸英文)。"""
    out = {}
    for i, raw in enumerate(texts, 1):
        for w in TC.registered_unverified(raw):
            _add(out, w, i, raw, say=CT.TERMS.get(w))
    return out


def pron_undecided(texts):
    """② 讀音標注:{鍵: {lines, sample, src}};src = cosy_pron | pron_rules。"""
    rules_verified = set(CT.RULES_RAW.get("_verified", []))
    out = {}
    for i, raw in enumerate(texts, 1):
        t = CT.unsay(raw or "")
        spans, hits = CT._word_spans(t)
        for w in hits:
            if w not in CT.PRON_VERIFIED:
                _add(out, w, i, raw, src="cosy_pron", value=CT.PRON.get(w))
        for _p, _ch, _py, key, _src, unv in CT._live_events(t, spans):
            if unv or key not in rules_verified:
                _add(out, key, i, raw, src="pron_rules", value=_py)
    return out


def polyphone(tag):
    """③ 跑 tts_polyphone.py:回傳 (前 TOP_N 筆 list, 一行說明);失敗回 ([], "未跑:原因")。不中止。"""
    try:
        if not P.TTS_ENV.exists():
            return [], f"未跑:找不到配音環境 {P.TTS_ENV}"
        if not (P.build_dir(tag) / "tts_qc.json").exists():
            return [], "未跑:build\\%s\\tts_qc.json 不存在(尚未配音)" % tag
        r = subprocess.run([str(P.TTS_ENV), "-X", "utf8", str(HERE / "tts_polyphone.py"), tag], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=POLY_TIMEOUT, cwd=str(P.REPO))
        if r.returncode:
            last = next((l.strip() for l in reversed((r.stdout + r.stderr).splitlines()) if l.strip()), "無輸出")
            return [], f"未跑:tts_polyphone 結束碼 {r.returncode}({last[:160]})"
        rep = json.loads(Path(P.project_file(tag, "polyphone_report.json")).read_text(encoding="utf-8"))
        return rep["items"][:TOP_N], f"共 {rep['n']} 筆(alt+strong {rep['n_alt_strong']}、alt+weak {rep['n_alt_weak']}、other {rep['n_other']}),列前 {TOP_N}"
    except Exception as e:
        return [], f"未跑:{type(e).__name__}: {str(e)[:160]}"


def _ln(lines):
    return "、".join(str(x) for x in lines[:8]) + (f"…(共 {len(lines)} 句)" if len(lines) > 8 else "")


def render(tag, ver, en, pron, poly, poly_note):
    n = len(en) + len(pron)
    L = [f"# 要你決定的唸法|{tag} {ver}", "",
         f"英文唸法 {len(en)} 筆|讀音標注 {len(pron)} 筆|疑似誤讀 {len(poly)} 筆(前 {TOP_N};{poly_note})", "",
         "定案後:英文詞 -> cosy_terms.json `_verified`;讀音詞 -> cosy_pron.json `_verified`;規則鍵 -> pron_rules.json `_verified`;再重跑 --tts-review(只重錄受影響句)。", ""]
    L += [f"## ① 英文唸法(cosy_terms 未驗證){len(en)} 筆", ""]
    L += [f"- {w}:{'直接唸英文' if e['say'] is None else '寫法 ' + e['say']}|句 {_ln(e['lines'])}|{e['sample'][:40]}" for w, e in en.items()] or ["(無)"]
    L += ["", f"## ② 讀音標注(未驗證)共 {len(pron)} 筆", ""]
    L += [f"- [{e['src']}] {k}|句 {_ln(e['lines'])}|{e['sample'][:40]}" for k, e in pron.items()] or ["(無)"]
    L += ["", f"## ③ 疑似誤讀(tts_polyphone)", "", poly_note, ""]
    L += [f"- {x.get('time') or '--:--'} 單位{x['idx']} 「{x['char']}」預期 {x['expect']} 辨識 {x['heard']}({x['heard_char']}) {x['kind']}/{x['evidence']}|{x['text'][:20]}"
          for x in poly]
    return "\n".join(L) + "\n", n


def count_undecided(tag, ver):
    r"""讀 output\<tag>\decide_<ver>.md 的摘要行(render 寫的「英文唸法 N 筆|讀音標注 M 筆」);回 (英文, 讀音);檔不存在或讀不出 = None。
    疑似誤讀(③)只是線索,不算未定。"""
    f = P.output_dir(tag) / f"decide_{ver}.md"
    try:
        m = re.search(r"英文唸法 (\d+) 筆\|讀音標注 (\d+) 筆", f.read_text(encoding="utf-8"))
    except OSError:
        return None
    return (int(m.group(1)), int(m.group(2))) if m else None


def run(tag, ver, texts=None, with_polyphone=True):
    """產生 decide_<ver>.md;回傳一行摘要「要你決定的唸法 N 筆(英文 a|讀音 b|疑似誤讀 c)→ 路徑」。"""
    texts = tts_terms.script_texts(tag) if texts is None else texts
    en, pron = en_undecided(texts), pron_undecided(texts)
    poly, note = polyphone(tag) if with_polyphone else ([], "未跑:略過")
    body, n = render(tag, ver, en, pron, poly, note)
    out = P.output_dir(tag) / f"decide_{ver}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    return f"要你決定的唸法 {n} 筆(英文 {len(en)}|讀音 {len(pron)})|疑似誤讀 {len(poly)} 筆" + (f"({note})" if not poly else "") + f" -> {out}"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(run(sys.argv[1], sys.argv[2]))
