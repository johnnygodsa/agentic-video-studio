r"""B 段確定性檢查回歸:對已發片最終稿跑 gates\gate_b.run 的機械項,與基線比,基線 ok=true 變 false 才算回歸。
改 director / script_lint / facts_check / visual_check / speakable 之前先跑,防「工具假錯」。

  python -X utf8 pipeline\tests\replay_b.py [--tags a,b] [--update-baseline]

結束碼 1 = 有回歸。只讀 build\<tag>、projects\<tag>、<tag>;跑前後比對這三處,若被改(目前實測沒有工具會寫)就還原並報告。
"""
import argparse
import json
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
import paths as P  # noqa: E402
from gates import gate_b  # noqa: E402

DEFAULT_TAGS = ("door_load", "headshot_hp", "pbz_week1", "wow_realm", "gow_budget")
MECH_IDS = ("lint擋0", "warn_log", "facts_check", "visual_check", "標籤實檔", "speakable硬項")
BASELINE = Path(__file__).resolve().parent / "fixtures" / "replay_b_baseline.json"
KEEP_LIMIT = 4_000_000  # 小於此大小的檔留一份內容,被改就還原


def watched(tag):
    return [P.build_dir(tag), P.PROJECTS / tag, P.REPO / tag]


def snapshot(tag):
    snap = {}
    for d in watched(tag):
        for f in Path(d).rglob("*") if Path(d).exists() else []:
            if f.is_file() and "__pycache__" not in f.parts:
                st = f.stat()
                snap[f] = (st.st_mtime_ns, st.st_size, f.read_bytes() if st.st_size < KEEP_LIMIT else None)
    return snap


def restore(before, tag):
    """跑後與跑前比對;被改的還原、新增的刪除,回報清單。"""
    changed = []
    now = {f for d in watched(tag) if Path(d).exists() for f in Path(d).rglob("*")
           if f.is_file() and "__pycache__" not in f.parts}
    for f in sorted(now - set(before)):
        f.unlink()
        changed.append(f"新增→已刪 {f}")
    for f, (mt, size, data) in before.items():
        if not f.exists():
            if data is not None:
                f.write_bytes(data)
            changed.append(f"消失→{'已還原' if data is not None else '無法還原'} {f}")
            continue
        st = f.stat()
        if (st.st_mtime_ns, st.st_size) != (mt, size):
            if data is not None:
                f.write_bytes(data)
            changed.append(f"被改→{'已還原' if data is not None else '無法還原'} {f}")
    return changed


def replay(tag):
    """回 ({id: {ok, note}}, 被工具改動的檔案清單)。"""
    before = snapshot(tag)
    try:
        items = gate_b.run(tag)
    finally:
        changed = restore(before, tag)
    return {i["id"]: {"ok": i["ok"], "note": i["note"]} for i in items if i["id"] in MECH_IDS}, changed


def compare(results, baseline):
    """基線 ok=true、現在 ok=false → 回歸清單 [(tag, id, note)]。基線沒有的項不算。"""
    reg = []
    for tag, items in results.items():
        for iid, r in items.items():
            if (baseline.get(tag) or {}).get(iid) is True and not r["ok"]:
                reg.append((tag, iid, r["note"]))
    return reg


def load_baseline():
    return json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}


def run_tags(tags):
    results, touched = {}, []
    for t in tags:
        results[t], ch = replay(t)
        touched += ch
    return results, touched


def main(argv=None):
    ap = argparse.ArgumentParser(description="B 段確定性檢查回歸")
    ap.add_argument("--tags", default=",".join(DEFAULT_TAGS))
    ap.add_argument("--update-baseline", action="store_true", help="把目前各片各項 ok 寫進基線")
    a = ap.parse_args(argv)
    tags = [t for t in a.tags.split(",") if t]
    results, touched = run_tags(tags)
    base = load_baseline()
    print("片 | 項 | ok | note")
    for t, items in results.items():
        for iid, r in items.items():
            print(f"{t} | {iid} | {r['ok']} | {r['note']}")
    for c in touched:
        print("[警告] 工具寫了檔:", c)
    if a.update_baseline:
        base.update({t: {iid: r["ok"] for iid, r in items.items()} for t, items in results.items()})
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(base, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"基線已更新:{BASELINE}")
        return 0
    reg = compare(results, base)
    for t, iid, note in reg:
        print(f"[回歸] {t} {iid}:{note}")
    print(f"回歸 {len(reg)} 項" + ("" if base else "(沒有基線,先跑 --update-baseline)"))
    return 1 if reg else 0


if __name__ == "__main__":
    sys.exit(main())
