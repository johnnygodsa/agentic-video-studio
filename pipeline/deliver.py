#!/usr/bin/env python3
r"""正式交付:把完整版 1080p 成片複製到 Youtube AD 的影片資料夾(paths.yt_inbox() = 下載\V),並寫 sidecar。

python pipeline/deliver.py --tag re9 --ver v3 --title "生化危機9_DLC史賓賽" [--channel ChannelA|ChannelB|ChannelC] [--enqueue [--publish-at [ISO|HH:MM|auto]]] [--dry-run] [--src <成片>] [--force] [--notes <說明檔>] [--cover <png>]
  來源:預設 OUTPUT\<tag>\<tag>_<ver>.mp4(--src 可另指定;相對路徑以素材根為基準)
  目的:yt_inbox()\<title>_<ver>.mp4,旁邊同主檔名 <title>_<ver>.claude.json
  sidecar 欄位:source/tag/ver/title/deepseek_text(說明檔「發片資料」區塊,【YouTube章節摘要】到【輸出完畢】)/desc_extra(「說明欄署名」區塊)。
  頻道:--channel 選填,--enqueue 時必填(ChannelA/ChannelB/ChannelC,亦接受 ChannelA/ChannelB);sidecar 加 "channel"(全名)與 "token_slot"(讀 paths.yt_ad_root()\data\channels.json,讀不到中止)。
    ChannelC沒有封面就中止(其他頻道不需要封面)。
  --enqueue:先過 gates.gate_d.run(tag, ver)(任一項不 ok 印各項、結束碼 2、不複製不入佇列;--skip-gate-d 緊急繞過只印警告;gates 載入失敗視為不過);交付成功後 POST 後端佇列(yt_queue.py);後端沒開印訊息並以 2 結束,409 視為已在佇列(0)。
  --publish-at(G-6,需 --enqueue):enqueue 成功後輪詢佇列到這支 done,再呼叫後端 POST /api/videos/<id>/schedule 設發布時間。
    值:ISO(無時區=台北)| HH:MM(下一個該時刻,至少 30 分鐘後)| auto 或不給值(頻道預設檔次:ChannelA 18:00、ChannelB 21:00,至少 3 小時後;其他頻道要明確給)。
    --schedule-wait-min 為輪詢上限(預設 120);逾時/佇列失敗/排程失敗只警告(印手動補排程指令 yt_queue.py --schedule),結束碼仍依 enqueue。
  口味回歸(taste T41/T44,2026-10-31):改版(ver 非 v1)且 yt_inbox 有同 tag 上一版 sidecar,沒帶 --cover 或 --title 與上一版不同 -> 印警告;
    projects\<tag>\handoff.md 寫了「使用者自己排時間/手動排」卻帶 --publish-at -> 中止(schedule_conflict)。
  封面:--cover <png>(相對路徑以素材根為基準);沒給就找 OUTPUT\<tag>\<tag>_thumb.png,存在就用。必須是 1920x1080 或 1280x720 的 PNG,否則中止。
    複製到 mp4 同資料夾 <title>_<ver>_封面.png,sidecar 加 "cover": "<檔名>"(只存檔名);沒有封面就不加欄位。
  說明檔預設 OUTPUT\<tag>\<ver>_說明.md(--notes 另指定);找不到發片資料區塊就中止,署名區塊可缺(警告)。
  --enqueue 時署名為空、發片資料缺/不完整、或發片資料含「(待填)」:印錯誤(缺哪段、檔案路徑)、結束碼 2,不複製、不寫 sidecar、不入佇列。
--shorts(F2-3b):來源須為 1080x1920,sidecar 加 "shorts": true,其餘欄位與行為不變;不可搭 --enqueue(後端尚未支援 Shorts 佇列);
  說明檔仍是「長片連結:(長片發布後填)」時印警告。Shorts 的 --ver 寫 <id>_<ver>(例 s1_v1,來源 <tag>_s1_v1.mp4、說明 s1_v1_說明.md)。
720p 預覽、notes、QA 圖留在 OUTPUT\<tag>\,不搬。目的已有內容相同的檔案就略過複製(sidecar 仍會更新);內容不同要加 --force 才覆蓋。
只用標準函式庫與 ffprobe,系統的 python 即可執行。
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import paths as P
import yt_queue as Q


def mb(p):
    return p.stat().st_size / 1e6


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def video_size(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def _section_block(md, heading):
    """取 `## heading` 之後第一個 ```text 區塊內容;沒有回傳 None。"""
    md = md.replace("\r\n", "\n")
    m = re.search(r"^##[ \t]+" + re.escape(heading) + r"[ \t]*\n(.*?)(?=^##[ \t]|\Z)", md, re.S | re.M)
    if not m:
        return None
    b = re.search(r"```text[ \t]*\n(.*?)^```", m.group(1), re.S | re.M)
    return b.group(1).strip() if b else None


def parse_notes(md):
    """回傳 (deepseek_text, desc_extra);發片資料缺或不完整 deepseek_text 為 None,署名缺 desc_extra 為 ''。"""
    ds = _section_block(md, "發片資料")
    if ds is not None and not (ds.lstrip().startswith("【YouTube章節摘要】") and ds.rstrip().endswith("【輸出完畢】")):
        ds = None
    return ds, _section_block(md, "說明欄署名") or ""


TODO_MARK = "(待填)"


def enqueue_missing(deepseek_text, desc_extra):
    """--enqueue 前檢查說明檔,回傳缺漏說明清單(空 = 齊全):署名為空、發片資料缺/不完整、發片資料仍含(待填)。"""
    miss = []
    if not desc_extra:
        miss.append("「## 說明欄署名」沒有 ```text 區塊(desc_extra 為空,說明欄會沒有資料來源)")
    if deepseek_text is None:
        miss.append("「## 發片資料」沒有完整的 ```text 區塊(【YouTube章節摘要】到【輸出完畢】)")
    elif TODO_MARK in deepseek_text:
        miss.append(f"「## 發片資料」仍含{TODO_MARK}")
    return miss


def _ver_no(ver):
    m = re.fullmatch(r"v(\d+)", ver or "")
    return int(m.group(1)) if m else None


def prev_sidecar(tag, ver, inbox=None):
    """同 tag 上一版(版號 < ver 的最大者)的 sidecar dict;沒有回 None。inbox 預設 paths.yt_inbox()。"""
    n = _ver_no(ver)
    inbox = Path(inbox) if inbox else P.yt_inbox()
    if n is None or n <= 1 or not inbox.is_dir():
        return None
    best = None
    for f in inbox.glob("*.claude.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        k = _ver_no(d.get("ver")) if isinstance(d, dict) and d.get("tag") == tag else None
        if k is not None and k < n and (best is None or k > best[0]):
            best = (k, d)
    return best[1] if best else None


def revision_issues(tag, ver, title, cover_arg, inbox=None):
    """T41:改版(ver 非 v1)且同 tag 已有上一版 sidecar:沿用封面與標題(4_交付發片 §1)。回警告清單(空 = 沒問題)。
    上一版有封面而這版沒帶 --cover、或 --title 與上一版 sidecar 的 title 不同。"""
    prev = prev_sidecar(tag, ver, inbox)
    if not prev:
        return []
    out = []
    if prev.get("cover") and not cover_arg:
        out.append(f"改版 {ver} 沒帶 --cover:上一版({prev.get('ver')})有封面 {prev.get('cover')},改版沿用上一版封面、不重作")
    if prev.get("title") and title != prev["title"]:
        out.append(f"改版 {ver} 的 --title「{title}」與上一版({prev.get('ver')})的「{prev['title']}」不同:改版沿用標題")
    return out


USER_SCHEDULES = re.compile(r"(?:使用者|我)自己(?:手動)?排(?:時間|程)?|使用者(?:自己)?手動排|時間我自己排|私人、不排程")


def schedule_conflict(tag, publish_at):
    """T44:handoff.md 寫了「使用者自己排時間」卻帶了 --publish-at -> 回錯誤訊息;否則 None。handoff 讀不到視為沒有限制。"""
    if publish_at is None:
        return None
    try:
        md = (P.PROJECTS / tag / "handoff.md").read_text(encoding="utf-8")
    except OSError:
        return None
    m = USER_SCHEDULES.search(md)
    return (f"projects/{tag}/handoff.md 寫了「{m.group(0)}」(發布時間由使用者自己排),不可帶 --publish-at;"
            "上傳後保持私人、不排程(要覆蓋請拿掉 --publish-at 或先改 handoff)") if m else None


def sidecar_path(video):
    return video.with_name(video.stem + ".claude.json")


def png_size(p):
    """讀 PNG 檔頭回傳 (w, h);不是 PNG 回傳 None。"""
    with open(p, "rb") as fh:
        head = fh.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def resolve_cover(arg, tag):
    """回傳封面來源 Path 或 None;--cover 指定的不存在或規格不符直接中止,自動找到的規格不符也中止。"""
    if arg:
        cov = P.find(arg)
        if not cov.exists():
            sys.exit(f"封面不存在: {cov}")
    else:
        cov = P.output_dir(tag) / f"{tag}_thumb.png"
        if not cov.exists():
            return None
    wh = png_size(cov)
    if wh is None:
        sys.exit(f"封面不是 PNG: {cov}")
    if wh not in ((1920, 1080), (1280, 720)):
        sys.exit(f"封面是 {wh[0]}x{wh[1]},必須是 1920x1080 或 1280x720: {cov}")
    return cov


def cover_name(title, ver):
    return f"{title}_{ver}_封面.png"


def copy_cover(cov, dst_dir, name):
    """封面複製到 dst_dir/name(.part 再 replace);回傳檔名。"""
    dst_dir.mkdir(parents=True, exist_ok=True)
    out = dst_dir / name
    part = out.with_name(out.name + ".part")
    shutil.copy2(cov, part)
    part.replace(out)
    return name


LONG_LINK_TODO = "長片連結:(長片發布後填)"

CHANNELS = {"ChannelA": "ChannelA", "ChannelA": "ChannelA", "ChannelB": "ChannelB", "ChannelB": "ChannelB",
            "ChannelC": "ChannelC", "ChannelC": "ChannelC"}
SCI_SLOT = "d"   # ChannelC = ChannelC(舊名/新名互為別名);實際寫入的名稱以 channels.json 裡 slot d 那筆為準
SCI = "ChannelC"


def resolve_channel(arg):
    """回傳 (頻道全名, token_slot);頻道不認得或 channels.json 讀不到/沒有該頻道就中止。"""
    name = CHANNELS.get(arg.strip())
    if not name:
        sys.exit(f"--channel 只接受 ChannelA/ChannelB/ChannelC/ChannelC(或 ChannelA/ChannelB),收到: {arg}")
    f = P.yt_ad_root() / "data" / "channels.json"
    try:
        rows = json.loads(f.read_text(encoding="utf-8"))
        if name == SCI:
            row = next(r for r in rows if r.get("token_slot") == SCI_SLOT or r.get("name") in ("ChannelC", "ChannelC"))
            return row["name"], row.get("token_slot") or ""
        slot = next(r["token_slot"] for r in rows if r.get("name") == name)
    except (OSError, ValueError, StopIteration, KeyError, TypeError) as e:
        sys.exit(f"讀不到 {name} 的 token_slot({f}: {type(e).__name__} {e}),中止,未交付")
    return name, slot or ""


def write_sidecar(dst, tag, ver, title, deepseek_text, desc_extra, cover=None, channel=None, token_slot="", shorts=False):
    sc = sidecar_path(dst)
    sc.parent.mkdir(parents=True, exist_ok=True)
    data = {"source": "Claude_Video", "tag": tag, "ver": ver, "title": title,
            "deepseek_text": deepseek_text, "desc_extra": desc_extra}
    if channel:
        data["channel"] = channel
        data["token_slot"] = token_slot
    if cover:
        data["cover"] = cover
    if shorts:
        data["shorts"] = True
    part = sc.with_name(sc.name + ".part")
    part.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    part.replace(sc)
    return sc


def gate_d_items(tag, ver, channel=None):
    """--enqueue 前的 gate_d 硬擋:呼叫 gates.gate_d.run(tag, ver)(回 [item{id, ok, note, path}]);
    gates 模組 import 失敗、執行例外都視為不 ok(回一筆 ok=False 的 item)。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from gates import gate_d
        try:
            return list(gate_d.run(tag, ver, ctx={"channel": channel or ""}))   # 頻道給片長規則(ChannelC不限片長)
        except TypeError:   # 舊介面沒有 ctx
            return list(gate_d.run(tag, ver))
    except Exception as e:  # noqa: BLE001
        return [dict(id="gate_d", ok=False, note=f"gate_d 載入或執行失敗({type(e).__name__}: {e}),視為不通過", path=None)]


def gate_d_check(tag, ver, skip=False, channel=None):
    """印各項;回傳是否可交付。skip(--skip-gate-d 緊急繞過)只印警告,一律放行。"""
    if skip:
        print("警告: --skip-gate-d 已略過 gate_d(片長/渲染前檢查/音軌缺口/LUFS 等),緊急用,責任自負", file=sys.stderr)
        return True
    items = gate_d_items(tag, ver, channel)
    for it in items:
        print(f"  gate_d {'OK  ' if it.get('ok') else '不過'} {it.get('id')}" + ("" if it.get("ok") else f": {it.get('note') or ''}"))
    return all(it.get("ok") for it in items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--channel", help="ChannelA|ChannelB|ChannelC(亦接受 ChannelA/ChannelB);--enqueue 時必填")
    ap.add_argument("--enqueue", action="store_true", help="交付成功後送進 Youtube AD 後端佇列")
    ap.add_argument("--publish-at", nargs="?", const="auto", default=None, metavar="ISO|HH:MM|auto",
                    help="需 --enqueue:佇列完成後呼叫後端 schedule 設發布時間;不給值 = 依頻道預設檔次(ChannelA 18:00、ChannelB 21:00)")
    ap.add_argument("--schedule-wait-min", type=int, default=Q.SCHEDULE_WAIT_MIN, help="等佇列完成的上限(分鐘),預設 120")
    ap.add_argument("--ver", required=True)
    ap.add_argument("--title", required=True, help="交付檔名(不含版本與副檔名)")
    ap.add_argument("--src", help="完整版成片;預設 OUTPUT\\<tag>\\<tag>_<ver>.mp4")
    ap.add_argument("--notes", help="說明檔;預設 OUTPUT/<tag>/<ver>_說明.md")
    ap.add_argument("--cover", help="封面 PNG(1920x1080 或 1280x720);預設 OUTPUT/<tag>/<tag>_thumb.png(存在才用)")
    ap.add_argument("--dry-run", action="store_true", help="只顯示來源與目的,不複製")
    ap.add_argument("--shorts", action="store_true", help="Shorts 直式成片(1080x1920);sidecar 加 shorts: true;不可搭 --enqueue")
    ap.add_argument("--force", action="store_true", help="目的已有內容不同的同名檔時覆蓋")
    ap.add_argument("--skip-gate-d", action="store_true", help="緊急繞過:--enqueue 前不檢查 gates.gate_d(只印警告)")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    if a.shorts and a.enqueue:
        sys.exit("Youtube AD 後端尚未支援 Shorts 佇列,中止,未交付(拿掉 --enqueue 只交付到資料夾)")
    if a.enqueue and not a.channel:
        sys.exit("--enqueue 必須同時給 --channel(sidecar 需要 channel/token_slot 才能入佇列),中止,未交付")
    if a.enqueue and not gate_d_check(a.tag, a.ver, a.skip_gate_d, a.channel):
        print("錯誤: gate_d 未過,未交付、未入佇列(結束碼 2)。修好上述項目;緊急才加 --skip-gate-d", file=sys.stderr)
        sys.exit(2)
    when = None
    if a.publish_at is not None:
        conflict = schedule_conflict(a.tag, a.publish_at)
        if conflict:
            sys.exit(conflict + ",中止,未交付")
        if not a.enqueue:
            sys.exit("--publish-at 必須同時給 --enqueue(排程要等佇列上傳完成),中止,未交付")
        try:
            when = Q.resolve_publish_at(a.publish_at, CHANNELS.get(a.channel.strip()))
        except ValueError as e:
            sys.exit(f"{e},中止,未交付")
        print(f"發布時間: {when}(佇列完成後排程)")
    dst = deliver(a)
    if a.enqueue and dst is not None and not a.dry_run:
        rc = Q.enqueue(dst)
        if when and rc == 0:
            Q.schedule_after_queue(dst, when, a.schedule_wait_min)   # 失敗只警告(已印手動補排程指令)
        sys.exit(rc)


def deliver(a):
    """交付;回傳目的 mp4 Path(dry-run 回傳 None);失敗直接 sys.exit。"""
    channel, token_slot = resolve_channel(a.channel) if a.channel else (None, "")

    src = P.find(a.src) if a.src else P.output_dir(a.tag) / f"{a.tag}_{a.ver}.mp4"
    dst = P.yt_inbox() / f"{a.title}_{a.ver}.mp4"
    notes = P.find(a.notes) if a.notes else P.output_dir(a.tag) / f"{a.ver}_說明.md"
    print(f"來源: {src}" + (f"({mb(src):.1f} MB)" if src.exists() else "(不存在)"))
    print(f"目的: {dst}" + (f"(已存在,{mb(dst):.1f} MB)" if dst.exists() else ""))
    print(f"說明檔: {notes}")
    if not notes.exists():
        sys.exit("說明檔不存在,無法產生 sidecar(先寫 output/<tag>/<ver>_說明.md,或用 --notes 指定)")
    cov = resolve_cover(a.cover, a.tag)
    cname = cover_name(a.title, a.ver) if cov else None
    for w in revision_issues(a.tag, a.ver, a.title, a.cover):
        print(f"警告: {w}", file=sys.stderr)
    print(f"封面: {cov}" if cov else "封面: 無(不加 cover 欄位)")
    print(f"頻道: {channel}(token_slot={token_slot!r})" if channel else "頻道: 未指定(sidecar 不寫 channel/token_slot)")
    if channel in (SCI, "ChannelC") and not cov:
        sys.exit("ChannelC(ChannelC)必須有封面(--cover <png> 或 output/<tag>/<tag>_thumb.png),中止,未交付")
    deepseek_text, desc_extra = parse_notes(notes.read_text(encoding="utf-8"))
    if a.enqueue:   # 要上傳的版本資料必須齊全,缺了就不複製、不寫 sidecar、不入佇列
        miss = enqueue_missing(deepseek_text, desc_extra)
        if miss:
            print(f"錯誤: --enqueue 但說明檔資料不齊,未交付、未入佇列(結束碼 2)\n  說明檔: {notes}\n"
                  + "\n".join(f"  - {m}" for m in miss), file=sys.stderr)
            sys.exit(2)
    if deepseek_text is None:
        sys.exit("說明檔找不到完整的「## 發片資料」```text 區塊(【YouTube章節摘要】到【輸出完畢】),中止,未交付")
    if not desc_extra:
        print("警告: 說明檔沒有「## 說明欄署名」區塊,desc_extra 留空", file=sys.stderr)
    if a.shorts and LONG_LINK_TODO in desc_extra + (deepseek_text or ""):
        print(f"警告: 說明檔仍是「{LONG_LINK_TODO}」,長片發布後要補上連結", file=sys.stderr)
    def finish_sidecar():
        if cov:
            copy_cover(cov, dst.parent, cname)
        return write_sidecar(dst, a.tag, a.ver, a.title, deepseek_text, desc_extra, cname, channel, token_slot, a.shorts)

    if not src.exists():
        if dst.exists():
            print("來源已不在 OUTPUT,目的已有成片:視為已交付,只更新 sidecar。")
            if not a.dry_run:
                print(f"sidecar: {finish_sidecar()}")
                return dst
            return None
        sys.exit("來源不存在,無法交付(先渲染完整版,或用 --src 指定)")
    w, h = video_size(src)
    want = (1080, 1920) if a.shorts else (1920, 1080)
    if (w, h) != want:
        sys.exit(f"來源是 {w}x{h},不是 {want[0]}x{want[1]}{' Shorts' if a.shorts else ' 完整版'},不交付")
    if dst.exists():
        if dst.stat().st_size == src.stat().st_size and sha1(dst) == sha1(src):
            print("目的已有內容相同的檔案:已交付,略過複製。")
            if a.dry_run:
                print("dry-run: 會更新 sidecar")
            else:
                print(f"sidecar: {finish_sidecar()}")
                return dst
            return None
        if not a.force:
            sys.exit("目的已有內容不同的同名檔;確定要覆蓋請加 --force")
    if a.dry_run:
        print("dry-run: 會複製 來源 -> 目的" + ("(覆蓋)" if dst.exists() else "") + (",複製封面" if cov else "") + ",並寫 sidecar")
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    shutil.copy2(src, part)
    if part.stat().st_size != src.stat().st_size:
        part.unlink()
        sys.exit("複製後大小不符,已中止")
    part.replace(dst)
    print(f"已交付: {dst}({mb(dst):.1f} MB)")
    print(f"sidecar: {finish_sidecar()}")
    return dst


if __name__ == "__main__":
    main()
