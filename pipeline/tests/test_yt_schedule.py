"""G-6:--publish-at(yt_queue.resolve_publish_at / wait_video_id / schedule_after_queue,deliver 串接);全部 mock Q.call,不打真後端。
python -X utf8 pipeline\\tests\\test_yt_schedule.py"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import os  # noqa: E402
if (ROOT / "_shared" / "gpu_lock.py").exists():          # 容器/雲端沒有 <EXTERNAL_BACKEND>\_shared 時,make_version 匯入 gpu_lock 需要它
    os.environ.setdefault("YT_SHARED_DIR", str(ROOT / "_shared"))
import deliver as D  # noqa: E402
import paths as P  # noqa: E402
import yt_queue as Q  # noqa: E402

FAILS = []
TZ = Q.TAIPEI


def expect(name, cond, detail=""):
    print(("通過" if cond else "失敗"), name, detail)
    if not cond:
        FAILS.append(name)


def now_at(h, m=0, d=27):
    return datetime(2026, 10, d, h, m, tzinfo=TZ)


class Fake:
    """依序回放 GET /api/claude_queue 的狀態;記錄所有呼叫。"""
    def __init__(self, states, sched=(202, '{"job_id":"j1"}')):
        self.states, self.sched, self.calls, self.i = list(states), sched, [], 0

    def __call__(self, method, endpoint, body=None, timeout=15):
        self.calls.append((method, endpoint, body))
        if method == "GET":
            s = self.states[min(self.i, len(self.states) - 1)]
            self.i += 1
            if s is None:
                return None, "refused"
            return 200, json.dumps({"items": [s] if isinstance(s, dict) else []})
        return self.sched


def item(status, vid=None, step="studio", err=None):
    return {"name": "片_v1.mp4", "path": r"X:\V\片_v1.mp4", "status": status, "step": step, "video_id": vid, "error": err}


def run_sched(fake, wait_min=120):
    Q.call = fake
    t = [0.0]
    clock = lambda: t[0]                      # noqa: E731
    def sleep(s): t[0] += s                   # noqa: E301
    return Q.schedule_after_queue(r"X:\V\片_v1.mp4", "2026-10-28T18:00:00+08:00", wait_min, 30, sleep, clock)


def main():
    R = Q.resolve_publish_at
    # 解析
    expect("auto ChannelA 10:00 -> 今天 18:00", R("auto", "ChannelA", now_at(10)) == "2026-10-27T18:00:00+08:00")
    expect("auto ChannelA 15:30(<3h)-> 明天 18:00", R("auto", "ChannelA", now_at(15, 30)) == "2026-10-28T18:00:00+08:00")
    expect("auto ChannelB -> 21:00", R("", "ChannelB", now_at(10)) == "2026-10-27T21:00:00+08:00")
    expect("auto ChannelC 無預設 -> ValueError", _raises(lambda: R("auto", "ChannelC", now_at(10))))
    expect("HH:MM 18:00 在 17:45 -> 明天", R("18:00", None, now_at(17, 45)) == "2026-10-28T18:00:00+08:00")
    expect("HH:MM 9:05", R("9:05", None, now_at(7)) == "2026-10-27T09:05:00+08:00")
    expect("HH:MM 25:00 不合法", _raises(lambda: R("25:00", None, now_at(7))))
    expect("ISO 無時區視為台北", R("2026-10-28T18:00", None, now_at(10)) == "2026-10-28T18:00:00+08:00")
    expect("ISO Z 轉 +08:00", R("2026-10-28T10:00:00Z", None, now_at(10)) == "2026-10-28T18:00:00+08:00")
    expect("ISO 太近 -> ValueError", _raises(lambda: R("2026-10-27T10:10", None, now_at(10))))
    expect("亂字串 -> ValueError", _raises(lambda: R("明天", None, now_at(10))))

    # 等佇列:running -> done -> 排程
    f = Fake([item("running"), item("running"), item("done", "VID123")])
    rc = run_sched(f)
    posts = [c for c in f.calls if c[0] == "POST"]
    expect("running->done 後排程", rc == 0 and posts == [("POST", "/api/videos/VID123/schedule", {"publish_at": "2026-10-28T18:00:00+08:00"})], str(posts))
    expect("輪詢 3 次", len([c for c in f.calls if c[0] == "GET"]) == 3)
    # 失敗/取消不排程
    f = Fake([item("running"), item("failed", None, "upload", "boom")])
    expect("佇列 failed 不排程", run_sched(f) == 1 and not [c for c in f.calls if c[0] == "POST"])
    f = Fake([item("cancelled")])
    expect("佇列 cancelled 不排程", run_sched(f) == 1 and not [c for c in f.calls if c[0] == "POST"])
    # done 但無 video_id
    f = Fake([item("done", None)])
    expect("done 無 video_id 不排程", run_sched(f) == 1 and not [c for c in f.calls if c[0] == "POST"])
    # 逾時
    f = Fake([item("running")])
    expect("逾時不排程且有限次輪詢", run_sched(f, wait_min=2) == 1 and len(f.calls) <= 6 and not [c for c in f.calls if c[0] == "POST"], str(len(f.calls)))
    # 後端連不上 3 次放棄;偶發失敗可恢復
    f = Fake([None])
    expect("連不上 3 次放棄", run_sched(f) == 1 and len(f.calls) == 3)
    f = Fake([None, item("done", "V2")])
    expect("偶發連不上可恢復", run_sched(f) == 0)
    # 佇列裡沒有這支(先找不到再出現)
    f = Fake([{}, item("done", "V3")])
    expect("暫時找不到項目續等", run_sched(f) == 0 and f.calls[-1][1] == "/api/videos/V3/schedule")
    # 排程端點回錯誤:警告、回 1
    f = Fake([item("done", "V4")], sched=(400, '{"detail":"too soon"}'))
    expect("schedule 400 -> 1", run_sched(f) == 1)
    f = Fake([item("done", "V5")], sched=(None, "refused"))
    expect("schedule 連不上 -> 1", run_sched(f) == 1)

    # deliver 串接(mock enqueue / schedule_after_queue)
    tmp = ROOT / "tmp" / "test_yt_schedule"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    ad = tmp / "ad"
    (ad / "data").mkdir(parents=True)
    (ad / "data" / "channels.json").write_text(json.dumps([{"name": "ChannelA", "token_slot": ""}, {"name": "ChannelB", "token_slot": "c"}], ensure_ascii=False), encoding="utf-8")
    os.environ["YOUTUBE_AD_ROOT"] = str(ad)
    P.yt_inbox = lambda: tmp / "V"
    P.output_dir = lambda tag: tmp / "out"
    D.video_size = lambda p: (1920, 1080)
    (tmp / "out").mkdir()
    (tmp / "out" / "tg_v1.mp4").write_bytes(b"v")
    ds = "【YouTube章節摘要】\n00:00 開場\n【輸出完畢】"
    (tmp / "out" / "v1_說明.md").write_text(f"## 說明欄署名\n```text\n本片資料來源:測試\n```\n\n## 發片資料\n```text\n{ds}\n```\n", encoding="utf-8")
    calls = {"enq": [], "sch": []}
    Q.enqueue = lambda p: (calls["enq"].append(str(p)), 0)[1]
    Q.schedule_after_queue = lambda p, w, m=120, *a, **k: (calls["sch"].append((Path(p).name, w, m)), 1)[1]   # 排程失敗也不影響結束碼

    def go(argv):
        old = sys.argv
        sys.argv = ["deliver.py", "--tag", "tg", "--ver", "v1", "--title", "片"] + argv
        if "--enqueue" in argv:  # --enqueue 先過 gate_d(Phase 3);本測試只測排程串接,gate_d 另有測試
            sys.argv.append("--skip-gate-d")
        try:
            D.main()
            return None
        except SystemExit as e:
            return str(e.code)
        finally:
            sys.argv = old

    msg = go(["--channel", "ChannelA", "--enqueue", "--publish-at", "2099-01-01T18:00"])
    expect("deliver --publish-at 串接,排程失敗不改結束碼", msg == "0" and calls["sch"] == [("片_v1.mp4", "2099-01-01T18:00:00+08:00", 120)], f"{msg} {calls}")
    calls["sch"].clear()
    msg = go(["--channel", "ChannelB", "--enqueue", "--publish-at", "--schedule-wait-min", "5"])
    expect("--publish-at 不給值 = auto(ChannelB 21:00)", msg == "0" and calls["sch"] and calls["sch"][0][1].endswith("T21:00:00+08:00") and calls["sch"][0][2] == 5, str(calls["sch"]))
    calls["sch"].clear()
    msg = go(["--channel", "ChannelA", "--publish-at", "18:00"])
    expect("沒 --enqueue 中止", msg is not None and "--enqueue" in msg and not calls["sch"], str(msg))
    msg = go(["--channel", "ChannelA", "--enqueue", "--publish-at", "亂寫"])
    expect("時間格式錯中止、不 enqueue", msg is not None and "未交付" in msg and not calls["sch"], str(msg))
    n = len(calls["enq"])
    msg = go(["--channel", "ChannelA", "--enqueue"])
    expect("不給 --publish-at 行為不變(不排程)", msg == "0" and len(calls["enq"]) == n + 1 and not calls["sch"])
    Q.enqueue = lambda p: 2
    calls["sch"].clear()
    msg = go(["--channel", "ChannelA", "--enqueue", "--publish-at", "auto"])
    expect("enqueue 失敗(2)不排程、保留結束碼", msg == "2" and not calls["sch"], str(msg))

    # make_version.deliver_cmd 透傳
    import argparse
    import make_version as MV
    ns = argparse.Namespace(tag="t", ver="v1", title="片", channel="ChannelA", enqueue=True, cover=None, publish_at="auto", schedule_wait_min=None)
    c = MV.deliver_cmd(ns)
    expect("make_version 透傳 --publish-at", c[-2:] == ["--publish-at", "auto"], str(c))
    ns.publish_at, ns.schedule_wait_min = None, 30
    expect("沒給則不帶旗標", "--publish-at" not in MV.deliver_cmd(ns) and "--schedule-wait-min" not in MV.deliver_cmd(ns))

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n全部通過" if not FAILS else f"\n失敗 {len(FAILS)}: {FAILS}")
    sys.exit(1 if FAILS else 0)


def _raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


if __name__ == "__main__":
    main()
