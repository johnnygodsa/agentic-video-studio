r"""段 E gate(自審上片)。規格:pipeline\docs\director.md「run:C→E 串接」。"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import director as D  # noqa: E402
import paths as P  # noqa: E402

IDS = ("發片資料", "sidecar", "已排程", "spec_check")
PENDING = ("(待填)", "（待填）")  # 半形、全形括號都算
SCHEDULED = ("已排程", "結案")


def status(tag, ctx):
    """director status 用(原 director.check_e,行為不變)。"""
    notes = D._first(sorted(D._glob(P.output_dir(tag), "*_說明.md"), key=D._ver_no, reverse=True))
    vid = ctx["video_id"]
    st = ctx["board"].get("stage")
    return [D._item("說明檔", notes, "output\\<tag>\\*_說明.md 沒有", notes),
            D._item("video_id", vid, "video_id 沒有(handoff.md / production.json)"),
            D._item("已排程", st in SCHEDULED, f"board 階段 {st or '(無)'},非已排程")]


def release_block(text):
    """說明檔「發片資料」```text 區塊的內容(區塊含【YouTube章節摘要】或緊接在「發片資料」標題下);沒有回 None。"""
    text = text.replace("\r\n", "\n")
    for m in re.finditer(r"```text\n(.*?)```", text, re.S):
        head = text[:m.start()].rstrip().splitlines()[-1:]
        if "【YouTube章節摘要】" in m.group(1) or (head and "發片資料" in head[0]):
            return m.group(1)
    return None


def sidecar_path(title, ver):
    return P.yt_inbox() / f"{title}_{ver}.claude.json"


def find_sidecar(tag, ver, title=None):
    """回傳 (sidecar 路徑, title) 或 (None, None):有 title 先找 <title>_<ver>.claude.json,
    否則掃 yt_inbox 的 *_<ver>.claude.json,JSON 的 tag 等於 tag 即命中(title 取 JSON 的 title 或檔名)。"""
    if title and sidecar_path(title, ver).exists():
        return sidecar_path(title, ver), title
    suffix = f"_{ver}.claude.json"
    for p in D._glob(P.yt_inbox(), f"*{suffix}"):
        d = D._read_json(p) or {}
        if d.get("tag") == tag:
            return p, d.get("title") or p.name[:-len(suffix)]
    return None, None


def spec_item(tag):
    r"""spec_check 錯誤 0:呼叫既有 spec_check.py --tag(結束碼 1 = 有錯誤);projects\<tag>\spec.json 不存在就略過(同 make_version,舊片相容)。"""
    spec = P.PROJECTS / tag / "spec.json"
    if not spec.exists():
        return D._item("spec_check", True, "spec.json 不存在,略過(舊片相容)")
    r = subprocess.run([sys.executable, "-X", "utf8", str(P.REPO / "pipeline" / "spec_check.py"), "--tag", tag], cwd=P.ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"警告 (\d+) 項、錯誤 (\d+) 項", text)
    if r.returncode == 0:
        return D._item("spec_check", True, f"spec_check 錯誤 0" + (f"(警告 {m.group(1)})" if m else ""), spec)
    first = next((l.strip() for l in text.splitlines() if "錯誤:" in l), "") or D._tail(text)
    return D._item("spec_check", False, f"spec_check 錯誤 {m.group(2) if m else '?'}:{first[:120]}")


def _save_title(tag, title):
    """production.json 沒有 title 才寫。"""
    data, _ = D.init(tag)
    if not data.get("title"):
        data["title"] = title
        D._atomic_write(D.prod_path(tag), data)


def run(tag, ver, ctx=None):
    """硬擋:<ver>_說明.md 有發片資料區塊且無(待填);sidecar 存在;board 已排程(或 production.json 有 video_id 與 publish_at);spec_check 錯誤 0(有 spec.json 才跑)。"""
    ctx = ctx or {}
    notes = P.output_dir(tag) / f"{ver}_說明.md"
    if not notes.exists():
        out = [D._item("發片資料", False, f"{ver}_說明.md 沒有")]
    else:
        blk = release_block(notes.read_text(encoding="utf-8", errors="replace"))
        if blk is None:
            out = [D._item("發片資料", False, f"{ver}_說明.md 沒有發片資料 text 區塊")]
        else:
            n = sum(blk.count(p) for p in PENDING)
            out = [D._item("發片資料", n == 0, f"發片資料 (待填) {n} 處", notes)]
    prod = ctx.get("prod") or {}
    st = (ctx.get("board") or {}).get("stage")
    vid = D.find_video_id(tag, prod)
    sc, title = find_sidecar(tag, ver, ctx.get("title"))
    if sc:
        _save_title(tag, title)
        ctx["title"] = title
        out.append(D._item("sidecar", True, "", sc))
    elif vid or st in SCHEDULED:  # 已交付的 sidecar 會被 Youtube AD 後端收走
        out.append(D._item("sidecar", True, f"sidecar 已被後端收走,以 video_id 為證({vid or 'board ' + st})"))
    else:
        out.append(D._item("sidecar", False, f"yt_inbox 沒有 tag={tag} 的 *_{ver}.claude.json,也沒有 video_id"))
    ok = st in SCHEDULED or bool(vid and prod.get("publish_at"))
    out.append(D._item("已排程", ok, f"board 階段 {st or '(無)'};video_id {vid or '無'};publish_at {prod.get('publish_at') or '無'}"))
    out.append(spec_item(tag))
    return out
