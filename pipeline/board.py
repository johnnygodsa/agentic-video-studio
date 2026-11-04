#!/usr/bin/env python3
r"""多支片共用進度板:channel\board.json(資料)+ channel\board.md(由本檔產生,不手改)。

python -X utf8 pipeline/board.py set <tag> [--stage S] [--next ...] [--blocked ...] [--publish YYYY-MM-DD]
                                     [--channel C] [--gpu 0|1] [--session ID] [--force]   只更新給的欄,tag 不存在就新增;--force 繞過階段前置條件
python -X utf8 pipeline/board.py show       印表(publish 升冪、無日期在後,再依 updated)
python -X utf8 pipeline/board.py rm <tag>
Python API:board.set_stage(tag, stage, force=False, **kw)、board.update(tag, force=False, **kw)、board.get(tag)、board.load()。
階段前置條件(2026-10-31):設「已凍結」要 gates.gate_c.run 全 ok、設「已排程」要 gates.gate_e.run 全 ok(「已排程」項本身除外,它檢查的就是這個階段);
  不過就印各項並結束碼 2(SystemExit);--force / force=True 繞過(印警告)。找不到該片 output 的版本號 = 略過檢查並印警告。make_version / freeze 自動流程傳 force=True。
寫檔:board.lock(O_EXCL)互斥讀改寫,暫存檔 + os.replace 覆蓋,避免兩個 session 同時寫壞檔。
階段(2026-10-26 改名):A資料 -> B文案 -> C配音 -> 已凍結(配音文本鎖定,畫面可改) -> D畫面 -> E自審 -> 已排程 -> 改版 -> 結案。
舊名(段1查證/段1文案/聽審中/段2素材/段2樣片/段2成片/段3改版)見 LEGACY_STAGES:load() 讀到自動換,set_stage/update 收到也換。
測試可用環境變數 CV_BOARD_DIR 改資料夾。
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P  # noqa: E402

STAGES = ("A資料", "B文案", "C配音", "已凍結", "D畫面", "E自審", "已排程", "改版", "結案")
# 舊階段名 -> 新階段名(2026-10-26 改名;load() 讀到舊值自動換,set_stage/update 收到舊名也換)
LEGACY_STAGES = {"段1查證": "A資料", "段1文案": "B文案", "聽審中": "C配音", "段2素材": "D畫面", "段2樣片": "D畫面",
                 "段2成片": "E自審", "段3改版": "改版"}
FIELDS = ("channel", "stage", "next", "blocked", "publish", "gpu", "session", "updated")
LOCK_STALE_S = 30


def board_dir():
    return Path(os.environ.get("CV_BOARD_DIR") or (P.REPO / "channel"))


def json_path():
    return board_dir() / "board.json"


def md_path():
    return board_dir() / "board.md"


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def norm_stage(v):
    """舊階段名換成新名;其他原樣。"""
    return LEGACY_STAGES.get(v, v)


def _norm_data(data):
    for r in data.values():
        if isinstance(r, dict) and r.get("stage") in LEGACY_STAGES:
            r["stage"] = LEGACY_STAGES[r["stage"]]
    return data


def load():
    p = json_path()
    if not p.exists():
        return {}
    for _ in range(5):  # 別人正在 os.replace 時可能短暫讀不到
        try:
            return _norm_data(json.loads(p.read_text(encoding="utf-8") or "{}"))
        except (OSError, json.JSONDecodeError):
            time.sleep(0.2)
    return _norm_data(json.loads(p.read_text(encoding="utf-8") or "{}"))


def get(tag):
    return load().get(tag)


def _atomic_write(path, text):
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    for i in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows:目標正被別的行程讀取
            time.sleep(0.1 * (i + 1))
    os.replace(tmp, path)


class _Mutex:
    """board.lock 互斥(超過 LOCK_STALE_S 秒視為殘留)。"""

    def __init__(self):
        self.p = board_dir() / "board.lock"

    def __enter__(self):
        self.p.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                os.close(os.open(self.p, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.p.stat().st_mtime > LOCK_STALE_S:
                        self.p.unlink()
                        continue
                except FileNotFoundError:
                    continue
                time.sleep(0.1)

    def __exit__(self, *exc):
        try:
            self.p.unlink()
        except FileNotFoundError:
            pass


def sort_key(item):
    tag, r = item
    return (0 if r.get("publish") else 1, r.get("publish") or "", r.get("updated") or "", tag)


def ordered(data):
    return sorted(data.items(), key=sort_key)


def _cell(v):
    if isinstance(v, bool):
        return "是" if v else ""
    return str(v or "").replace("|", "/").replace("\n", " ")


HEAD = ("tag", "頻道", "階段", "下一步", "卡住", "發布", "GPU", "session", "更新")
KEYS = ("tag", "channel", "stage", "next", "blocked", "publish", "gpu", "session", "updated")


def render_md(data):
    lines = ["<!-- 由 board.py 產生,不手改(python -X utf8 pipeline/board.py set/rm) -->", "# 進度板", "",
             "| " + " | ".join(HEAD) + " |", "|" + "---|" * len(HEAD)]
    for tag, r in ordered(data):
        row = dict(r, tag=tag)
        lines.append("| " + " | ".join(_cell(row.get(k)) for k in KEYS) + " |")
    return "\n".join(lines) + "\n"


def _save(data):
    board_dir().mkdir(parents=True, exist_ok=True)
    _atomic_write(json_path(), json.dumps(data, ensure_ascii=False, indent=1))
    _atomic_write(md_path(), render_md(data))


def _clean(kw):
    out = {}
    for k, v in kw.items():
        if v is None:
            continue
        if k not in FIELDS or k == "updated":
            raise ValueError(f"board 沒有欄位 {k}")
        if k == "stage" and v:
            v = norm_stage(v)
        if k == "stage" and v and v not in STAGES:
            raise ValueError(f"stage 必須是 {'/'.join(STAGES)} 之一,收到 {v}")
        if k == "publish" and v:
            datetime.strptime(v, "%Y-%m-%d")
        if k == "gpu":
            v = bool(int(v)) if isinstance(v, str) else bool(v)
        out[k] = v
    return out


GATED_STAGES = {"已凍結": "gates.gate_c", "已排程": "gates.gate_e"}
GATE_SELF_ITEM = {"已排程": "已排程"}   # gate 內檢查「board 已是此階段」的項目:設階段前一定不過,略過它


def latest_ver(tag):
    """該片 output 最新版的版本號字串(v3 之類):從 {tag}_v*.mp4、listen_v*.txt、v*_說明.md 的 v<數字> 取最大;找不到回 None。"""
    import re
    d = P.output_dir(tag)
    best = 0
    for pat in (f"{tag}_v*.mp4", "listen_v*.txt", "v*_說明.md"):
        for f in (d.glob(pat) if d.is_dir() else ()):
            m = re.search(r"(?:^|_)v(\d+)(?=[_.])", f.name)
            if m:
                best = max(best, int(m.group(1)))
    return f"v{best}" if best else None


def stage_problems(tag, stage):
    """設 stage 的前置條件:回傳 [未過項的說明](空 = 可設)。非受控階段、找不到版本號 = 空(後者印警告)。"""
    mod = GATED_STAGES.get(stage)
    if not mod:
        return []
    ver = latest_ver(tag)
    if not ver:
        print(f"警告:找不到 {tag} 的 output 版本,略過「{stage}」前置條件檢查")
        return []
    import importlib
    gate = importlib.import_module(mod)
    ctx = {"board": get(tag) or {}} if stage == "已排程" else None
    items = gate.run(tag, ver, ctx) if ctx is not None else gate.run(tag, ver)
    skip = GATE_SELF_ITEM.get(stage)
    return [f"{it['id']}:{it.get('note') or '未過'}" for it in items if not it.get("ok") and it.get("id") != skip]


def update(tag, force=False, **kw):
    """只更新給的欄(None 不動);tag 不存在就新增。回傳更新後該筆。
    kw 含受控 stage(已凍結/已排程)時先驗前置條件:不過印各項並 SystemExit(2);force=True 繞過(印警告)。"""
    kw = _clean(kw)
    st = kw.get("stage")
    if st in GATED_STAGES:
        bad = stage_problems(tag, st)
        if bad and force:
            print(f"警告:{tag} 設「{st}」前置條件未過,已用 force 繞過:" + "; ".join(bad))
        elif bad:
            print(f"錯誤:{tag} 不能設階段「{st}」,{GATED_STAGES[st].split('.')[-1]} 未全過:")
            for b in bad:
                print(f"  - {b}")
            print("(確定要硬設才加 --force)")
            sys.exit(2)
    with _Mutex():
        data = load()
        r = data.get(tag) or {k: ("" if k != "gpu" else False) for k in FIELDS}
        r.update(kw)
        r["updated"] = now_iso()
        data[tag] = r
        _save(data)
    return r


def set_stage(tag, stage, force=False, **kw):
    return update(tag, force=force, stage=stage, **kw)


def remove(tag):
    with _Mutex():
        data = load()
        hit = data.pop(tag, None) is not None
        _save(data)
    return hit


def show_text(data=None):
    data = load() if data is None else data
    if not data:
        return "(進度板是空的)"
    rows = [HEAD] + [tuple(_cell(dict(r, tag=t).get(k)) for k in KEYS) for t, r in ordered(data)]
    return "\n".join(" | ".join(c for c in row) for row in rows)


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="多支片共用進度板(見檔頭)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set")
    s.add_argument("tag")
    s.add_argument("--stage", choices=STAGES + tuple(LEGACY_STAGES), help="舊階段名也收(自動換新名)")
    s.add_argument("--next")
    s.add_argument("--blocked")
    s.add_argument("--publish", help="YYYY-MM-DD;給空字串清除")
    s.add_argument("--channel")
    s.add_argument("--gpu", choices=("0", "1"))
    s.add_argument("--session")
    s.add_argument("--force", action="store_true", help="繞過階段前置條件(已凍結要 gate_c 全過、已排程要 gate_e 全過)")
    sub.add_parser("show")
    r = sub.add_parser("rm")
    r.add_argument("tag")
    a = ap.parse_args()
    if a.cmd == "set":
        try:
            rec = update(a.tag, stage=a.stage, next=a.next, blocked=a.blocked, publish=a.publish,
                         channel=a.channel, gpu=a.gpu, session=a.session, force=a.force)
        except ValueError as e:
            sys.exit(f"錯誤:{e}")
        print(f"{a.tag}: {rec['stage'] or '(無階段)'} | 下一步 {rec['next'] or '-'} | 發布 {rec['publish'] or '-'}")
    elif a.cmd == "show":
        print(show_text())
    elif a.cmd == "rm":
        print(f"已移除 {a.tag}" if remove(a.tag) else f"{a.tag} 不在進度板")


if __name__ == "__main__":
    main()
