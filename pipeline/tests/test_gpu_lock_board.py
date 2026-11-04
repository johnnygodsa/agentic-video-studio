"""gpu_lock / board / freeze 測試。python -X utf8 pipeline/tests/test_gpu_lock_board.py(這台沒 pytest,直接執行)。
暫存一律在 paths.TMP\\test_gpu_lock_board\\(不碰真的 _shared\\.gpu_lock 與 channel\\board.json)。"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import paths as P  # noqa: E402

BASE = P.TMP / "test_gpu_lock_board"
LOCK = BASE / "lock"
BOARD = BASE / "board"
os.environ.update(YT_GPU_LOCK_DIR=str(LOCK), CV_BOARD_DIR=str(BOARD), YT_GPU_LOCK_NOSMI="1", YT_GPU_LOCK_POLL="0.2")
os.environ.pop("YT_GPU_LOCK", None)

import board  # noqa: E402
import freeze as FZ  # noqa: E402
import gpu_lock as GL  # noqa: E402

CHILD = r"""
import json, sys, time
sys.path.insert(0, sys.argv[1])
import gpu_lock as GL
tag, hold, out = sys.argv[2], float(sys.argv[3]), sys.argv[4]
with GL.gpu_lock(tag, "test"):
    t1 = time.time()
    time.sleep(hold)
    t2 = time.time()
open(out, "w", encoding="utf-8").write(json.dumps(dict(tag=tag, got=t1, rel=t2)))
"""


def reset():
    shutil.rmtree(BASE, ignore_errors=True)
    BASE.mkdir(parents=True)


def spawn(tag, hold, name):
    out = BASE / f"{name}.json"
    p = subprocess.Popen([sys.executable, "-X", "utf8", "-c", CHILD, str(HERE), tag, str(hold), str(out)], env=dict(os.environ))
    return p, out


def wait_queue(n, timeout=20):
    t0 = time.time()
    while len(list((LOCK / "queue").glob("*.json"))) < n:
        assert time.time() - t0 < timeout, "排隊檔沒出現"
        time.sleep(0.1)


def test_two_procs():
    reset()
    pa, oa = spawn("a", 1.5, "a")
    pb, ob = spawn("b", 0.2, "b")
    assert pa.wait(30) == 0 and pb.wait(30) == 0
    ra, rb = (json.loads(o.read_text(encoding="utf-8")) for o in (oa, ob))
    first, second = sorted((ra, rb), key=lambda r: r["got"])
    assert second["got"] >= first["rel"] - 0.01, (first, second)  # 後者等前者釋放才拿到
    assert not (LOCK / "holder.json").exists()


def test_stale_lock():
    reset()
    (LOCK / "queue").mkdir(parents=True)
    (LOCK / "holder.json").write_text(json.dumps(dict(tag="ghost", job="x", pid=999999, token="ghost|x|999999")), encoding="utf-8")
    t0 = time.time()
    with GL.gpu_lock("me", "test", timeout=10):
        assert GL.holder()["tag"] == "me"
    assert time.time() - t0 < 5
    assert not (LOCK / "holder.json").exists()


def test_priority():
    reset()
    board.update("late", publish="2026-12-01")
    board.update("early", publish="2026-11-01")
    (LOCK / "queue").mkdir(parents=True)
    tok = f"blocker|x|{os.getpid()}"  # 以本行程(活著)當持有者,讓兩個子行程都排隊
    (LOCK / "holder.json").write_text(json.dumps(dict(tag="blocker", job="x", pid=os.getpid(), token=tok)), encoding="utf-8")
    pl, ol = spawn("late", 0.5, "late")
    wait_queue(1)
    pe, oe = spawn("early", 0.5, "early")
    wait_queue(2)
    (LOCK / "holder.json").unlink()
    assert pl.wait(30) == 0 and pe.wait(30) == 0
    rl, re_ = (json.loads(o.read_text(encoding="utf-8")) for o in (ol, oe))
    assert re_["got"] < rl["got"], "publish 早者應先拿到"


class _FreezeEnv:
    """把 freeze 的 script / freeze.json / tts_review.json / tts 快取目錄全導到 tmp/test_gpu_lock_board/(不碰真片目錄)。"""

    def __enter__(self):
        reset()
        self.sp, self.fp = BASE / "script.txt", BASE / "freeze.json"
        self.rp, self.tts, self.bd = BASE / "tts_review.json", BASE / "tts", BASE / "build"
        self.tts.mkdir()
        self.bd.mkdir()
        self.old = (FZ.script_path, FZ.freeze_path, FZ.review_path, P.tts_dir, P.build_dir)
        FZ.script_path, FZ.freeze_path, FZ.review_path = (lambda tag: self.sp), (lambda tag: self.fp), (lambda tag: self.rp)
        P.tts_dir, P.build_dir = (lambda tag, engine=None: self.tts), (lambda tag: self.bd)
        self.sp.write_text("x|第一句\n", encoding="utf-8")
        (self.tts / "001.key").write_text("k1|qc7")
        (self.tts / "002.key").write_text("k2|qc7")
        return self

    def __exit__(self, *exc):
        FZ.script_path, FZ.freeze_path, FZ.review_path, P.tts_dir, P.build_dir = self.old

    def review(self, **over):
        rec = dict(script_sha256=FZ.sha256(self.sp), at="2026-10-23T10:00:00", units=2, failed=[], no_qc=[], timing_errors=[],
                   tts_keys_sha=FZ.tts_keys_sha("t", "cosy3"), engine="cosy3")
        rec.update(over)
        self.rp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")


def _refused(tag, **kw):
    try:
        FZ.freeze(tag, "測試", **kw)
    except FZ.FreezeRefused as e:
        return " ".join(e.args[0])
    return None


def test_freeze_mismatch():
    with _FreezeEnv() as env:
        import make_version as MV
        assert MV.freeze_check("t") is None  # 未凍結
        env.review()
        FZ.freeze("t", "測試")
        assert MV.freeze_check("t") is None  # 相符
        env.sp.write_text("x|第一句改了\n", encoding="utf-8")
        msg = MV.freeze_check("t")
        assert msg and "配音文本已改" in msg and "--refreeze" in msg
        assert MV.freeze_check("t", tts_review=True) is None  # 聽審不受限


def test_freeze_gate():
    with _FreezeEnv() as env:
        assert "找不到" in _refused("t") and not env.fp.exists()  # 無 review -> 拒
        env.review(failed=[dict(idx="3", fails=["asr"])])
        assert "品管未過 1" in _refused("t") and not env.fp.exists()
        env.review(no_qc=["5"])
        assert "沒有品管紀錄" in _refused("t")
        env.review(timing_errors=["同圖 >9 秒"])
        assert "時長預檢" in _refused("t")
        env.review(script_sha256="0" * 64)
        assert "不符" in _refused("t") and not env.fp.exists()  # sha 不符 -> 拒
        env.review()
        rec = FZ.freeze("t", "聽審通過")  # 全過 -> 通過並記錄 keys / engine / review_at
        assert rec["tts_keys_sha"] == FZ.tts_keys_sha("t", "cosy3") and rec["engine"] == "cosy3" and rec["review_at"] == "2026-10-23T10:00:00"
        assert not rec.get("forced") and json.loads(env.fp.read_text(encoding="utf-8"))["tts_keys_sha"] == rec["tts_keys_sha"]
        # --status 用的 keys 比對:改一個 key -> 不相符
        assert FZ.tts_keys_sha("t", rec["engine"]) == rec["tts_keys_sha"]
        (env.tts / "002.key").write_text("k2-changed|qc7")
        assert FZ.tts_keys_sha("t", rec["engine"]) != rec["tts_keys_sha"]
        # refreeze 走同門檻
        env.review(failed=[dict(idx="1", fails=["x"])])
        assert _refused("t") is not None


def test_freeze_force():
    with _FreezeEnv() as env:
        try:
            FZ.freeze("t", "", force=True)
            raise AssertionError("--force 沒給 reason 應報錯")
        except ValueError:
            pass
        assert not env.fp.exists()
        rec = FZ.freeze("t", "使用者同意先凍結", force=True)  # 無 review 也能強制
        saved = json.loads(env.fp.read_text(encoding="utf-8"))
        assert saved["forced"] is True and saved["reason"] == "使用者同意先凍結" and "找不到" in " ".join(saved["forced_problems"]), saved
        assert rec["tts_keys_sha"] == saved["tts_keys_sha"]


def test_write_tts_review():
    """make_version.write_tts_review:欄位齊全,failed / no_qc 取自 tts_qc.json,keys sha 與 freeze 算法一致。"""
    with _FreezeEnv() as env:
        import make_version as MV
        (env.bd / "tts_qc.json").write_text(json.dumps(dict(
            units=2, checked=1, failed=[dict(idx="2", fails=["asr_sim"], text="x", asr="y")], no_qc=["1"], records=[])), encoding="utf-8")
        out, rec = MV.write_tts_review("t", "cosy3")
        saved = json.loads(out.read_text(encoding="utf-8"))
        assert out == env.rp and saved == rec
        assert saved["script_sha256"] == FZ.sha256(env.sp) and saved["units"] == 2 and saved["engine"] == "cosy3"
        assert saved["failed"] == [dict(idx="2", fails=["asr_sim"])] and saved["no_qc"] == ["1"] and saved["timing_errors"] == []
        assert saved["tts_keys_sha"] == FZ.tts_keys_sha("t", "cosy3") and saved["at"]
        assert saved["narration_sha"] == FZ.narration_sha("t")
        assert "品管未過 1" in _refused("t")  # 接 freeze 門檻


def test_board_roundtrip():
    reset()
    board.set_stage("x1", "B文案", channel="ChannelA", next="寫稿", gpu=True)
    board.update("x2", publish="2026-11-05", stage="D畫面")
    board.update("x1", next="聽審")
    d = board.load()
    assert d["x1"]["stage"] == "B文案" and d["x1"]["next"] == "聽審" and d["x1"]["channel"] == "ChannelA" and d["x1"]["gpu"] is True
    assert [t for t, _ in board.ordered(d)] == ["x2", "x1"]  # 有日期在前
    md = (BOARD / "board.md").read_text(encoding="utf-8")
    assert md.startswith("<!-- 由 board.py 產生,不手改") and "| x1 |" in md
    assert "x2" in board.show_text()
    try:
        board.update("x1", stage="亂寫")
        raise AssertionError("不合法 stage 應報錯")
    except ValueError:
        pass
    assert board.remove("x2") and "x2" not in board.load()


def test_board_after_stages():
    """make_version.board_after 新規則:tts-review -> C配音(凍結成功 -> 已凍結);樣片不動;完整版 -> E自審(改版不動);enqueue 成功 -> 已排程。"""
    reset()
    import make_version as MV
    from types import SimpleNamespace

    def ns(**kw):
        return SimpleNamespace(**dict(dict(tts_review=False, enqueue=False, checks_only=False, channel=None), **kw))
    board.set_stage("s1", "已凍結")
    board.set_stage("s2", "D畫面")
    board.set_stage("s3", "改版")
    for t in ("s1", "s2", "s3"):
        MV.board_after(t, ns(), True, False)   # 樣片:全部不動
    d = board.load()
    assert d["s1"]["stage"] == "已凍結" and d["s2"]["stage"] == "D畫面" and d["s3"]["stage"] == "改版", d
    MV.board_after("s1", ns(), False, False)   # 完整版 -> E自審
    MV.board_after("s3", ns(), False, False)   # 改版不動
    assert board.get("s1")["stage"] == "E自審" and board.get("s3")["stage"] == "改版"
    MV.board_after("s2", ns(tts_review=True), False, False)
    assert board.get("s2")["stage"] == "C配音"
    MV.board_after("s2", ns(tts_review=True), False, False, frozen=True)
    assert board.get("s2")["stage"] == "已凍結"
    MV.board_after("s1", ns(enqueue=True), False, True)
    assert board.get("s1")["stage"] == "已排程"
    MV.board_after("s3", ns(enqueue=True), False, False)   # 未交付成功 -> 照完整版規則(改版不動)
    assert board.get("s3")["stage"] == "改版"


def test_yad_due_today_first():
    """YAD 今天到期的排隊檔排在 board publish 為明天的 CV 前面(到期日制)。"""
    from datetime import date, timedelta
    reset()
    today = date.today()
    board.update("tomorrow", publish=(today + timedelta(days=1)).isoformat())
    (LOCK / "queue").mkdir(parents=True)
    me = os.getpid()
    enq = time.time()
    yad = dict(project="yad", tag="字幕轉錄", job="x.mp4", pid=me, pid_start=GL._S.proc_start(me), enq=enq,
               since=time.strftime("%Y-%m-%dT%H:%M:%S"), due=today.isoformat())
    yf = LOCK / "queue" / f"{enq:.6f}_{me}.json"
    yf.write_text(json.dumps(yad, ensure_ascii=False), encoding="utf-8")
    p, _ = spawn("tomorrow", 0.1, "tomorrow")
    try:
        wait_queue(2)
        q = [e for _, e in GL.queue()]
        assert [e.get("project") for e in q] == ["yad", "cv"], q
        assert q[1].get("tag") == "tomorrow" and q[1].get("due") == (today + timedelta(days=1)).isoformat(), q
    finally:
        p.kill()
        p.wait(30)
        yf.unlink(missing_ok=True)


TESTS = [("①兩子行程互斥", test_two_procs), ("②殘留鎖清除", test_stale_lock), ("③publish 優先序", test_priority),
         ("④freeze 不符中止", test_freeze_mismatch), ("④b凍結門檻(review)", test_freeze_gate),
         ("④c--force 記 reason", test_freeze_force), ("④dtts_review.json 欄位", test_write_tts_review),
         ("⑤board 往返", test_board_roundtrip),
         ("⑥board_after 新階段規則", test_board_after_stages), ("⑦YAD 今天到期排在 CV 明天前", test_yad_due_today_first)]

if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    bad = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"OK   {name}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    shutil.rmtree(BASE, ignore_errors=True)
    sys.exit(1 if bad else 0)
