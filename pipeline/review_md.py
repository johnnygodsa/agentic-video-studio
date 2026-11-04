#!/usr/bin/env python3
r"""審閱彙整:把既有三份清單併成一份 output\<tag>\review_<ver>.md,三節「聽/看/決定」(Phase 2b 項 3)。
python -X utf8 pipeline\review_md.py --tag <tag> --ver <ver>
  聽 = listen_<ver>.txt(必聽節在最前逐句列、其他節折疊只給類別與句號;舊格式整份原樣)+ projects\<tag>\tts_report.json 的警告項(below_min / rate_out_of_range / asr2_bad / failed_qc,有值才列)。
  看 = look_<ver>.md 全文 + build\<tag>\structure.json 的 warnings(script_structure)+ facts_check 的警告(有 facts*.md 才跑,唯讀)。
  決定 = decide_<ver>.md 全文。
缺哪份寫「(無)」。只彙整、不取代:原三份清單照舊產生。make_version 在「優先看」步驟後呼叫 run()(失敗不中斷;--tts-review 也跑)。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import paths as P

NONE = "(無)"
TTS_WARN_KEYS = (("below_min", "句間靜音低於下限"), ("rate_out_of_range", "語速偏差超範圍"),
                 ("asr2_bad", "二次辨識未過"), ("failed_qc", "品管未過"))


def _read(p):
    try:
        return Path(p).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def tts_warnings(report):
    """tts_report.json(dict)-> 警告行 list;只列非空的警告欄位。"""
    out = []
    for key, label in TTS_WARN_KEYS:
        v = (report or {}).get(key)
        if v:
            items = v if isinstance(v, list) else [v]
            out.append(f"- {label}({key}){len(items)} 項:" + "; ".join(json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x for x in items[:15])
                       + (f" …另 {len(items) - 15} 項" if len(items) > 15 else ""))
    return out


def structure_warnings(st):
    """structure.json(dict)-> 警告行 list(code / 句號 / 說明)。"""
    return [f"- [{w.get('code')}] 句{w.get('line')}:{w.get('text')}" for w in ((st or {}).get("warnings") or [])]


def facts_warnings(lines):
    """facts_check stdout 行 -> 警告行 list:「警告 … N 句」N>0 的行、摘要行中 未連結/狀態不符/錯誤/無出處/引矛盾 任一 >0。"""
    out = []
    for l in lines:
        s = l.strip()
        m = re.match(r"警告 .*?(\d+) 句", s)
        if m and int(m.group(1)) > 0:
            out.append(f"- {s}")
        elif s.startswith("[facts_check]"):
            n = {k: int(v) for k, v in re.findall(r"(未連結|狀態不符|錯誤|無出處|引矛盾) (\d+)", s)}
            if any(n.values()):
                out.append(f"- {s}")
    return out


def run_facts_check(tag):
    """有 facts*.md 才跑 facts_check.py(唯讀);回傳 stdout 行 list,跑不成回 []。"""
    script = P.REPO / "pipeline" / "facts_check.py"
    if not script.exists() or not any((P.PROJECTS / tag).glob("facts*.md")):
        return []
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", str(script), tag], cwd=P.REPO, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError):
        return []
    return (r.stdout or "").splitlines()


def split_listen(text):
    """listen_<ver>.txt 全文 -> (必聽行 list, 其他行 list);沒有「## 必聽」標題(舊版純清單)回 (None, None)。標題行本身不收。"""
    if "## 必聽" not in (text or ""):
        return None, None
    must, other, cur = [], [], None
    for l in text.splitlines():
        if l.startswith("## 必聽"):
            cur = must
        elif l.startswith("## 其他"):
            cur = other
        elif cur is not None and l.strip():
            cur.append(l)
    return must, other


def listen_blocks(listen, ver):
    """「聽」節的清單區塊 list:新格式 = 必聽(逐句,放最前)+ 其他(折疊,只有類別與句號);舊格式 = 整份原樣。"""
    if not listen:
        return []
    must, other = split_listen(listen)
    if must is None:
        return [f"### 優先聽清單(listen_{ver}.txt:`mm:ss|句號|原因|原文`)\n\n```text\n{listen}\n```"]
    head = f"### 必聽({len(must)} 句;listen_{ver}.txt:`mm:ss|句號|原因|原文`)\n\n"
    blocks = [head + ("```text\n" + "\n".join(must) + "\n```" if must else "(沒有)")]
    if other:
        blocks.append("<details><summary>其他待聽(語速、讀音記憶待聽、逗號靠插入等,不必逐句聽;類別(句數):句號)</summary>\n\n```text\n"
                      + "\n".join(other) + "\n```\n\n</details>")
    return blocks


def build(tag, ver, facts_lines=None):
    """組出 review_<ver>.md 全文(字串)。facts_lines 給 None = 實際跑 facts_check。"""
    od = P.output_dir(tag)
    listen = _read(od / f"listen_{ver}.txt")
    look = _read(od / f"look_{ver}.md")
    decide = _read(od / f"decide_{ver}.md")
    tw = tts_warnings(_load(P.PROJECTS / tag / "tts_report.json"))
    sw = structure_warnings(_load(P.build_dir(tag) / "structure.json"))
    fw = facts_warnings(run_facts_check(tag) if facts_lines is None else facts_lines)

    def sec(title, *blocks):
        body = [b for b in blocks if b]
        return f"## {title}\n\n" + ("\n\n".join(body) if body else NONE) + "\n"

    parts = [f"# 審閱彙整|{tag} {ver}\n",
             "三節各自的原清單照舊在 output 內(listen_ / look_ / decide_),本檔只彙整。\n",
             sec("聽", *listen_blocks(listen, ver),
                 ("### 配音報告警告(projects/%s/tts_report.json)\n\n" % tag + "\n".join(tw)) if tw else ""),
             sec("看", f"### 畫面優先看(look_{ver}.md)\n\n{look}" if look else "",
                 ("### 文案結構警告(build/%s/structure.json)\n\n" % tag + "\n".join(sw)) if sw else "",
                 ("### 事實核對表警告(facts_check)\n\n" + "\n".join(fw)) if fw else ""),
             sec("決定", decide)]
    return "\n".join(parts)


def run(tag, ver):
    """make_version 用:寫 review_<ver>.md,回傳一行摘要。"""
    out = P.output_dir(tag) / f"review_{ver}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = build(tag, ver)
    out.write_text(text, encoding="utf-8")
    empty = [t for t in ("聽", "看", "決定") if re.search(rf"## {t}\n\n{re.escape(NONE)}\n", text)]
    return f"審閱彙整 {out.name}" + (f"(無內容:{'、'.join(empty)})" if empty else "")


def main():
    ap = argparse.ArgumentParser(description="彙整聽/看/決定三份清單成 review_<ver>.md")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ver", required=True)
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    print(run(a.tag, a.ver))
    print(P.output_dir(a.tag) / f"review_{a.ver}.md")


if __name__ == "__main__":
    main()
