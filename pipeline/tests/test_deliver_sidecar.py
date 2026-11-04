"""deliver.py sidecar 單元測試(不碰真實下載資料夾,全部在 tmp\test_deliver):python -X utf8 pipeline\tests\test_deliver_sidecar.py"""
import json
import shutil
import struct
import sys
import threading
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import os  # noqa: E402
import deliver as D  # noqa: E402
import yt_queue as Q  # noqa: E402
import paths as P  # noqa: E402

FAILS = []
TMP = ROOT / "tmp" / "test_deliver"
DS = "【YouTube章節摘要】\n00:00 開場\n【影片標題】\n標題一\n【輸出完畢】"
CREDIT = 'Music: "Wallpaper" Kevin MacLeod (incompetech.com)\nLicensed under CC BY 4.0'
NOTES = f"# t v1\n\n## 已知問題\n- x\n\n## 說明欄署名\n```text\n{CREDIT}\n```\n\n## 發片資料\n```text\n{DS}\n```\n"


def expect(name, cond, detail=""):
    print(("通過" if cond else "失敗"), name, detail)
    if not cond:
        FAILS.append(name)


def make_png(path, w, h):
    """最小合法 PNG(單色),只為了測檔頭。"""
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x10\x20\x30" * w for _ in range(h))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def run(argv, inbox, outdir):
    """以 monkeypatch 跑 deliver.main;回傳 (退出訊息或 None)。"""
    P.yt_inbox = lambda: inbox
    P.output_dir = lambda tag: outdir
    D.video_size = lambda p: (1920, 1080)
    old = sys.argv
    if "--channel" not in argv and "--no-channel" not in argv:
        argv = argv + ["--channel", "ChannelA"]
    argv = [x for x in argv if x != "--no-channel"]
    if "--enqueue" in argv and "--skip-gate-d" not in argv:  # --enqueue 先過 gate_d(Phase 3);本測試只測 sidecar/入佇列,gate_d 另有測試
        argv = argv + ["--skip-gate-d"]
    sys.argv = ["deliver.py"] + argv
    try:
        D.main()
        return None
    except SystemExit as e:
        return str(e.code)
    finally:
        sys.argv = old


class FakeBackend(BaseHTTPRequestHandler):
    code = 200
    seen = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
        FakeBackend.seen.append((self.path, json.loads(body)))
        self.send_response(FakeBackend.code)
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *a):
        pass


def main():
    if TMP.exists():
        shutil.rmtree(TMP)
    inbox, out = TMP / "V", TMP / "out"
    out.mkdir(parents=True)
    ad = TMP / "ad"
    (ad / "data").mkdir(parents=True)
    (ad / "data" / "channels.json").write_text(json.dumps([
        {"name": "ChannelA", "token_slot": ""}, {"name": "ChannelB", "token_slot": "c"},
        {"name": "ChannelC", "token_slot": "d"}], ensure_ascii=False), encoding="utf-8")
    os.environ["YOUTUBE_AD_ROOT"] = str(ad)
    # parse_notes
    ds, ex = D.parse_notes(NOTES)
    expect("parse 發片資料", ds == DS, repr(ds)[:40])
    expect("parse 署名", ex == CREDIT)
    ds2, ex2 = D.parse_notes(NOTES.replace("## 說明欄署名", "## 其他"))
    expect("署名缺 -> 空字串", ds2 == DS and ex2 == "")
    ds3, _ = D.parse_notes(NOTES.replace("【輸出完畢】", ""))
    expect("發片資料不完整 -> None", ds3 is None)
    ds4, _ = D.parse_notes(NOTES.replace("## 發片資料", "## 別的"))
    expect("沒有發片資料 -> None", ds4 is None)
    ds5, ex5 = D.parse_notes(NOTES.replace("\n", "\r\n"))
    expect("CRLF 說明檔", ds5 == DS and ex5 == CREDIT)

    # 完整交付
    (out / "tg_v1.mp4").write_bytes(b"video-bytes-1")
    (out / "v1_說明.md").write_text(NOTES, encoding="utf-8")
    msg = run(["--tag", "tg", "--ver", "v1", "--title", "測試片"], inbox, out)
    mp4, sc = inbox / "測試片_v1.mp4", inbox / "測試片_v1.claude.json"
    expect("交付無錯誤", msg is None, str(msg))
    expect("mp4 複製", mp4.exists() and mp4.read_bytes() == b"video-bytes-1")
    j = json.loads(sc.read_text(encoding="utf-8")) if sc.exists() else {}
    expect("sidecar 欄位", j == {"source": "Claude_Video", "tag": "tg", "ver": "v1", "title": "測試片",
                              "deepseek_text": DS, "desc_extra": CREDIT, "channel": "ChannelA", "token_slot": ""}, str(list(j)))
    expect("無殘留 .part", not list(inbox.glob("*.part")))

    # 相同內容再交付:sidecar 仍更新
    (out / "v1_說明.md").write_text(NOTES.replace("標題一", "標題二"), encoding="utf-8")
    msg = run(["--tag", "tg", "--ver", "v1", "--title", "測試片"], inbox, out)
    j = json.loads(sc.read_text(encoding="utf-8"))
    expect("同內容仍更新 sidecar", msg is None and "標題二" in j["deepseek_text"])

    # dry-run 不寫
    (out / "v1_說明.md").write_text(NOTES, encoding="utf-8")
    run(["--tag", "tg", "--ver", "v1", "--title", "測試片", "--dry-run"], inbox, out)
    expect("dry-run 不寫 sidecar", "標題二" in json.loads(sc.read_text(encoding="utf-8"))["deepseek_text"])

    # 不同內容無 --force 中止,sidecar 不動
    (out / "tg_v1.mp4").write_bytes(b"video-bytes-2")
    msg = run(["--tag", "tg", "--ver", "v1", "--title", "測試片"], inbox, out)
    expect("內容不同需 --force", msg is not None and "--force" in msg)
    msg = run(["--tag", "tg", "--ver", "v1", "--title", "測試片", "--force"], inbox, out)
    expect("--force 覆蓋", msg is None and mp4.read_bytes() == b"video-bytes-2"
           and "標題一" in json.loads(sc.read_text(encoding="utf-8"))["deepseek_text"])

    # 沒有發片資料:中止且不交付
    (out / "tg_v1.mp4").write_bytes(b"x")
    (out / "v2_說明.md").write_text("# no\n", encoding="utf-8")
    (out / "tg_v2.mp4").write_bytes(b"v2")
    msg = run(["--tag", "tg", "--ver", "v2", "--title", "測試片"], inbox, out)
    expect("缺發片資料中止", msg is not None and not (inbox / "測試片_v2.mp4").exists()
           and not (inbox / "測試片_v2.claude.json").exists(), str(msg)[:30])
    # --notes 另指定 + 署名缺
    (out / "other.md").write_text(NOTES.replace("## 說明欄署名", "## 其他"), encoding="utf-8")
    msg = run(["--tag", "tg", "--ver", "v2", "--title", "測試片", "--notes", str(out / "other.md")], inbox, out)
    j = json.loads((inbox / "測試片_v2.claude.json").read_text(encoding="utf-8"))
    expect("--notes 與署名缺", msg is None and j["desc_extra"] == "")
    # 說明檔不存在
    (out / "tg_v3.mp4").write_bytes(b"v3")
    msg = run(["--tag", "tg", "--ver", "v3", "--title", "測試片"], inbox, out)
    expect("說明檔不存在中止", msg is not None and not (inbox / "測試片_v3.mp4").exists())

    # 封面:沒有封面時 sidecar 無 cover 欄位
    expect("無封面不加 cover", "cover" not in json.loads(sc.read_text(encoding="utf-8")))
    # --cover 指定 1280x720
    (out / "tg_v4.mp4").write_bytes(b"v4")
    (out / "v4_說明.md").write_text(NOTES, encoding="utf-8")
    make_png(out / "c.png", 1280, 720)
    msg = run(["--tag", "tg", "--ver", "v4", "--title", "測試片", "--cover", str(out / "c.png")], inbox, out)
    j = json.loads((inbox / "測試片_v4.claude.json").read_text(encoding="utf-8"))
    expect("--cover 複製並寫檔名", msg is None and j.get("cover") == "測試片_v4_封面.png"
           and (inbox / "測試片_v4_封面.png").read_bytes() == (out / "c.png").read_bytes(), str(msg))
    expect("cover 只存檔名", "/" not in j["cover"] and chr(92) not in j["cover"])
    expect("封面無殘留 .part", not list(inbox.glob("*.part")))
    # 自動找 <tag>_thumb.png(1920x1080)
    (out / "tg_v5.mp4").write_bytes(b"v5")
    (out / "v5_說明.md").write_text(NOTES, encoding="utf-8")
    make_png(out / "tg_thumb.png", 1920, 1080)
    msg = run(["--tag", "tg", "--ver", "v5", "--title", "測試片"], inbox, out)
    j = json.loads((inbox / "測試片_v5.claude.json").read_text(encoding="utf-8"))
    expect("自動找 _thumb.png", msg is None and j.get("cover") == "測試片_v5_封面.png"
           and (inbox / "測試片_v5_封面.png").exists(), str(msg))
    # dry-run 不複製封面
    (out / "tg_v6.mp4").write_bytes(b"v6")
    (out / "v6_說明.md").write_text(NOTES, encoding="utf-8")
    run(["--tag", "tg", "--ver", "v6", "--title", "測試片", "--dry-run"], inbox, out)
    expect("dry-run 不複製封面", not (inbox / "測試片_v6_封面.png").exists())
    # 尺寸不符中止,不交付
    make_png(out / "bad.png", 800, 600)
    msg = run(["--tag", "tg", "--ver", "v6", "--title", "測試片", "--cover", str(out / "bad.png")], inbox, out)
    expect("封面尺寸不符中止", msg is not None and "1920x1080" in msg and not (inbox / "測試片_v6.mp4").exists(), str(msg))
    # 非 PNG 中止
    (out / "fake.png").write_bytes(b"not a png at all, just text bytes here")
    msg = run(["--tag", "tg", "--ver", "v6", "--title", "測試片", "--cover", str(out / "fake.png")], inbox, out)
    expect("非 PNG 中止", msg is not None and "PNG" in msg and not (inbox / "測試片_v6.mp4").exists(), str(msg))
    # 指定的封面不存在中止
    msg = run(["--tag", "tg", "--ver", "v6", "--title", "測試片", "--cover", str(out / "nope.png")], inbox, out)
    expect("封面不存在中止", msg is not None and "不存在" in msg)

    # channel / token_slot
    for i, (arg, full, slot) in enumerate([("ChannelA", "ChannelA", ""), ("ChannelB", "ChannelB", "c"), ("ChannelB", "ChannelB", "c")]):
        v = f"c{i}"
        (out / f"tg_{v}.mp4").write_bytes(v.encode())
        (out / f"{v}_說明.md").write_text(NOTES, encoding="utf-8")
        run(["--tag", "tg", "--ver", v, "--title", "測試片", "--channel", arg], inbox, out)
        j = json.loads((inbox / f"測試片_{v}.claude.json").read_text(encoding="utf-8"))
        expect(f"channel {arg}", j.get("channel") == full and j.get("token_slot") == slot, str(j.get("token_slot")))
    msg = run(["--tag", "tg", "--ver", "v1", "--title", "測試片", "--channel", "路人"], inbox, out)
    expect("不認得的頻道中止", msg is not None and "--channel" in msg)
    # ChannelC:無封面中止、有封面通過(此時 out 內有 tg_thumb.png,先移除)
    (out / "tg_thumb.png").unlink()
    (out / "tg_k1.mp4").write_bytes(b"k1")
    (out / "k1_說明.md").write_text(NOTES, encoding="utf-8")
    msg = run(["--tag", "tg", "--ver", "k1", "--title", "科普片", "--channel", "ChannelC"], inbox, out)
    expect("ChannelC無封面中止", msg is not None and "封面" in msg and not (inbox / "科普片_k1.mp4").exists(), str(msg))
    make_png(out / "tg_thumb.png", 1920, 1080)
    msg = run(["--tag", "tg", "--ver", "k1", "--title", "科普片", "--channel", "ChannelC"], inbox, out)
    j = json.loads((inbox / "科普片_k1.claude.json").read_text(encoding="utf-8"))
    expect("ChannelC有封面", msg is None and j["token_slot"] == "d" and j["channel"] == "ChannelC" and j["cover"], str(msg))
    os.environ["YOUTUBE_AD_ROOT"] = str(TMP / "nope")
    msg = run(["--tag", "tg", "--ver", "k1", "--title", "科普片", "--channel", "ChannelB"], inbox, out)
    expect("channels.json 讀不到中止", msg is not None and "token_slot" in msg, str(msg)[:40])
    os.environ["YOUTUBE_AD_ROOT"] = str(ad)

    # 不給 --channel:sidecar 無 channel/token_slot、ChannelC封面不檢查;--enqueue 必須有 --channel
    (out / "tg_n1.mp4").write_bytes(b"n1")
    (out / "n1_說明.md").write_text(NOTES, encoding="utf-8")
    msg = run(["--tag", "tg", "--ver", "n1", "--title", "測試片", "--no-channel"], inbox, out)
    j = json.loads((inbox / "測試片_n1.claude.json").read_text(encoding="utf-8"))
    expect("無 --channel 不寫 channel/token_slot", msg is None and "channel" not in j and "token_slot" not in j, str(msg))
    (out / "tg_n2.mp4").write_bytes(b"n2")
    (out / "n2_說明.md").write_text(NOTES, encoding="utf-8")
    msg = run(["--tag", "tg", "--ver", "n2", "--title", "測試片", "--no-channel", "--enqueue"], inbox, out)
    expect("--enqueue 無 --channel 中止", msg is not None and "--channel" in msg and not (inbox / "測試片_n2.mp4").exists(), str(msg))

    # --enqueue 說明檔資料不齊:結束碼 2,不複製、不寫 sidecar
    bad = {"署名子標題": NOTES.replace("```text\n" + CREDIT + "\n```", "### 音樂\n- x"),
           "發片資料待填": NOTES.replace("標題一", "(待填)")}
    for i, (nm, txt) in enumerate(bad.items()):
        v = f"q{i}"
        (out / f"tg_{v}.mp4").write_bytes(b"q")
        (out / f"{v}_說明.md").write_text(txt, encoding="utf-8")
        msg = run(["--tag", "tg", "--ver", v, "--title", "測試片", "--enqueue"], inbox, out)
        expect(f"enqueue 擋 {nm}", msg == "2" and not (inbox / f"測試片_{v}.mp4").exists()
               and not (inbox / f"測試片_{v}.claude.json").exists(), str(msg))
    msg = run(["--tag", "tg", "--ver", "q0", "--title", "測試片"], inbox, out)
    expect("不帶 --enqueue 署名缺只警告", msg is None and (inbox / "測試片_q0.mp4").exists(), str(msg))

    # --enqueue:連不上 -> 2(成片仍已交付)
    (out / "tg_e1.mp4").write_bytes(b"e1")
    (out / "e1_說明.md").write_text(NOTES, encoding="utf-8")
    os.environ["YT_QUEUE_URL"] = "http://127.0.0.1:9"
    msg = run(["--tag", "tg", "--ver", "e1", "--title", "測試片", "--enqueue"], inbox, out)
    expect("enqueue 連不上結束碼 2", msg == "2" and (inbox / "測試片_e1.mp4").exists(), str(msg))
    srv = HTTPServer(("127.0.0.1", 0), FakeBackend)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["YT_QUEUE_URL"] = f"http://127.0.0.1:{srv.server_port}"
    for code, want in ((200, "0"), (409, "0"), (500, "1")):
        FakeBackend.code = code
        FakeBackend.seen.clear()
        msg = run(["--tag", "tg", "--ver", "e1", "--title", "測試片", "--enqueue"], inbox, out)
        expect(f"enqueue HTTP {code} -> {want}", msg == want, str(msg))
    expect("enqueue 送出 mp4 絕對路徑", FakeBackend.seen == [("/api/claude_queue/enqueue", {"path": str(inbox / "測試片_e1.mp4")})],
           str(FakeBackend.seen)[:80])
    FakeBackend.code = 200
    FakeBackend.seen.clear()
    run(["--tag", "tg", "--ver", "e1", "--title", "測試片", "--enqueue", "--dry-run"], inbox, out)
    expect("dry-run 不 enqueue", not FakeBackend.seen)
    expect("retry 結束碼 0 並帶路徑", Q.action("/api/claude_queue/retry", Q.video_path("測試片_e1.mp4")) == 0
           and FakeBackend.seen[0][0] == "/api/claude_queue/retry")
    row = Q.fmt_row({"path": "X:\\V\\片_v1.mp4", "channel": "ChannelB", "step": "cover", "status": "running", "error": "e" * 80})
    expect("status 列格式", row == "片_v1 | ChannelB | cover | running | " + "e" * 60 + " | -", row)
    expect("status 寬鬆解析", len(Q._items({"items": [{}]})) == 1 and len(Q._items({"a": {"x": 1}})) == 1 and Q._items(None) == [])
    srv.shutdown()

    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n失敗 {len(FAILS)} 項" if FAILS else "\n全部通過")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
