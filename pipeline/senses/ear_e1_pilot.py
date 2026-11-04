#!/usr/bin/env python3
r"""E1 強制讀音 pilot(PLAN_工作室v2_2026-10-31 §6.3;docs/tts.md §4.7):同一批句子出「table(現行只標詞表/規則/記憶)」與
「all(每個多音字都標)」兩版送引擎文字,量差多少。不合成音檔、不碰 GPU、不動快取。

用法(g2pW 只在 tts_env_chattts 有;預設 python 沒裝會退回 pypinyin,沒有 pypinyin 就只剩記憶來源):
  tts_env_chattts\Scripts\python.exe -X utf8 pipeline\senses\ear_e1_pilot.py --tag ea_me5 --n 50
  ... --tag ea_me5 --lines 10-40
句子來源 = freeze.narration_lines(與 script_txt2json 產 script.json、build.tts_all 同源的送配音文字,@say 已套)。
--polyset rules|risk|all 選多音字集合(預設 risk);輸出 tmp\ear_e1\<tag>\texts.json(risk)/ texts_<集合>.json:
  lines[] = {line, say, table, all, changed, poly[{pos, ch, value, src, new}]}
    pos = 在 pron_source(say)(unsay + 英文寫法 + 書名號冒號)上的位置;src = table|rule|memory|zhe(現行)、memory|g2pw|pypinyin|none(all 新增)
  stats = 多音字總數、原本已標、新增標注、沒標(none)、來源分布、文字有變的句數
並印同樣的統計。

合成比對怎麼跑(之後由 tester 用 GPU 跑,本腳本不做):
  1. 先 `python -X utf8 <EXTERNAL_BACKEND>\_shared\gpu_lock.py status`,輪到才跑(tts_pron_verify.synth 內部也會取 gpu_lock)。
  2. texts.json 兩版各當一批:item 的 say = 該句 say、送引擎文字分別用 table / all 欄(all 版跑時設 COSY_ANNOTATE=all,
     tts_cosy3.engine_text 會產生同一份 all 文字;或直接把 all 欄當 engine 文字餵 cosy3_worker)。
     合成用既有單句流程 `tts_pron_verify.synth(items, seeds, work, max_retry=0)`(與 tts_c0 共用;tts_cosy3 子行程、`--max-retry 0`
     看第一個 seed 的原始讀音,不讓品管換 seed 蓋掉),工作檔放 tmp\ear_e1\<tag>\<table|all>\。
  3. 每句 qc 紀錄已含雙辨識(tts_asr 主 asr / 副 asr2、sim、asr2_sim、pron_bad):兩版各算
     一致率 = 主副辨識都過相似度門檻的句數 / 總句數、品管通過率(qc passed)、
     多音字位置判定 = tts_pron_verify.judge_record(rec, targets) 的 right / wrong / undetermined(targets 取 poly 的 value 轉 tone3,
     tts_g2p.norm_py)。
  4. 出表 tmp\ear_e1\<tag>\compare.md:句 | table 一致/品管 | all 一致/品管 | 唸錯位置;末列兩版一致率、通過率、唸錯數。
     all 版變差的句子(evil_corp「異次元」那類)逐句列出,決定 E1 是否上線。
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import freeze as FZ  # noqa: E402
import paths as P  # noqa: E402
import tts_cosy_text as CT  # noqa: E402


def pick(says, n=50, lines=None):
    """-> [(行號 1 起, say)];lines = "a-b"(含兩端)優先於 n。"""
    if lines:
        a, _, b = lines.partition("-")
        a, b = int(a), int(b or a)
        return [(i, s) for i, s in enumerate(says, 1) if a <= i <= b]
    return list(enumerate(says, 1))[:n]


def line_record(i, say, polyset=None):
    """一句的兩版送引擎文字與多音字位置(polyset = rules|risk|all,見 tts_cosy_text.polyphone_chars)。"""
    src = CT.pron_source(say)
    table, _ = CT.apply_pron(src, "table")
    allt, _ = CT.apply_pron(src, "all", polyset)
    poly = [dict(pos=p, ch=ch, value=v, src=s, new=new) for p, ch, v, s, new in CT.poly_marks(src, "all", polyset=polyset)]
    return dict(line=i, say=say, table=table, all=allt, changed=table != allt, poly=poly)


def stats(recs):
    poly = [m for r in recs for m in r["poly"]]
    return dict(
        lines=len(recs),
        changed_lines=sum(r["changed"] for r in recs),
        polyphones=len(poly),
        already=sum(1 for m in poly if not m["new"]),
        added=sum(1 for m in poly if m["new"] and m["value"]),
        unmarked=sum(1 for m in poly if m["new"] and not m["value"]),
        sources=dict(Counter(m["src"] for m in poly).most_common()),
        added_sources=dict(Counter(m["src"] for m in poly if m["new"] and m["value"]).most_common()),
    )


def run(tag, n=50, lines=None, out_dir=None, polyset=None):
    polyset = CT.polyset_name(polyset)
    recs = [line_record(i, s, polyset) for i, s in pick(FZ.narration_lines(tag), n, lines)]
    st = dict(polyset=polyset, polyset_size=len(CT.polyphone_chars(polyset)), **stats(recs))
    out = Path(out_dir or P.TMP / "ear_e1" / tag)
    out.mkdir(parents=True, exist_ok=True)
    name = "texts.json" if polyset == "risk" else f"texts_{polyset}.json"
    (out / name).write_text(json.dumps(dict(tag=tag, stats=st, lines=recs), ensure_ascii=False, indent=1), encoding="utf-8")
    return out / name, st


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--n", type=int, default=50, help="取前 N 句(預設 50)")
    ap.add_argument("--lines", help="a-b:只取第 a–b 句(優先於 --n)")
    ap.add_argument("--polyset", choices=CT.POLYSETS, default=None, help="多音字集合(預設 risk 或環境變數 COSY_POLYSET)")
    a = ap.parse_args(argv)
    path, st = run(a.tag, a.n, a.lines, polyset=a.polyset)
    print(f"{path}")
    print(f"{a.tag} [{st['polyset']} {st['polyset_size']} 字]: {st['lines']} 句、文字有變 {st['changed_lines']} 句;多音字 {st['polyphones']} 處 = 原本已標 {st['already']}"
          f" + 新增標注 {st['added']} + 沒標 {st['unmarked']}")
    print("來源分布: " + "、".join(f"{k} {v}" for k, v in st["sources"].items()))
    print("新增標注來源: " + ("、".join(f"{k} {v}" for k, v in st["added_sources"].items()) or "無"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
