"""director run 與 gates 測試:python -X utf8 -m pytest pipeline/tests/test_director_run.py -q
假造產物放 repo tmp/ 下暫存目錄(paths 各根目錄、CV_BOARD_DIR、UPLOAD_V_DIR 以 monkeypatch 指過去);不真跑配音/渲染。"""
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import director as D  # noqa: E402
import freeze  # noqa: E402
import paths  # noqa: E402
from gates import gate_c, gate_d, gate_e  # noqa: E402

TAG, VER = "demo", "v1"


def _w(p, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _old(p, secs=100):
    t = time.time() - secs
    os.utime(p, (t, t))


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    root = base / f"test_director_run_{uuid.uuid4().hex[:8]}"
    root.mkdir()
    for attr, sub in (("PROJECTS", "projects"), ("BUILD", "build"), ("OUTPUT", "output"), ("TMP", "tmp")):
        monkeypatch.setattr(paths, attr, root / sub)
    monkeypatch.setattr(paths, "REPO", root / "repo")
    monkeypatch.setattr(paths, "ROOT", root)
    monkeypatch.setenv("CV_BOARD_DIR", str(root / "channel"))
    monkeypatch.setenv("UPLOAD_V_DIR", str(root / "V"))
    monkeypatch.setattr(freeze, "check", lambda tag: None)
    monkeypatch.setattr(gate_d, "probe_secs", lambda p: 600.0)
    (root / "channel").mkdir()
    (root / "repo" / TAG).mkdir(parents=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _board(root, **rec):
    (root / "channel" / "board.json").write_text(json.dumps({TAG: rec}, ensure_ascii=False), encoding="utf-8")


def _bad(items):
    return {i["id"] for i in items if not i["ok"]}


def _make_c(env):
    pd, bd = env / "projects" / TAG, env / "build" / TAG
    _w(env / "repo" / TAG / "script.txt")
    _w(pd / "c0_report.json", json.dumps({"wrong": 0}))
    _w(bd / "tts_review.json", json.dumps({"failed": [], "timing_errors": []}))
    _w(pd / "freeze.json", "{}")
    _w(env / "output" / TAG / f"listen_{VER}.txt")
    _w(pd / f"ear_e4_{VER}.json", "{}")


def _make_d(env):
    out = env / "output" / TAG
    _w(env / "build" / TAG / "timeline_tts.json", "{}")
    _w(out / f"{TAG}_{VER}.mp4")
    _w(out / f"make_{VER}.log", "渲染前檢查: 鏡頭 60 個 | 警告 2 | 錯誤 3\n渲染前檢查: 鏡頭 60 個 | 警告 2 | 錯誤 0\n")
    _w(out / f"qa_{VER}_01.png")
    _w(out / f"look_{VER}.md")
    _w(env / "projects" / TAG / f"eye_{VER}.json", json.dumps({"ok": True, "items": [{"id": "黑幀", "ok": True}]}))


NOTES = "## 發片資料\n```text\n【YouTube章節摘要】\n00:00 開場\n【影片標題】\n{t}\n```\n"


def _make_e(env, title="片名"):
    _w(env / "output" / TAG / f"{VER}_說明.md", NOTES.format(t="標題一"))
    _w(env / "V" / f"{title}_{VER}.claude.json", json.dumps({"tag": TAG, "ver": VER, "title": title}, ensure_ascii=False))
    _board(env, stage="已排程", channel="ChannelA")


def _args(*extra):
    return ["run", TAG, "--from", "C", "--to", "E", "--ver", VER, *extra]


def test_gate_c_reasons(env, monkeypatch):
    _make_c(env)
    pd = env / "projects" / TAG
    assert not _bad(gate_c.run(TAG, VER))
    _w(pd / "c0_report.json", json.dumps({"wrong": 2}))
    assert _bad(gate_c.run(TAG, VER)) == {"C0試配"}
    _w(pd / "c0_report.json", json.dumps({"wrong": 0}))
    _w(env / "build" / TAG / "tts_review.json", json.dumps({"failed": [3], "timing_errors": []}))
    assert _bad(gate_c.run(TAG, VER)) == {"品管"}
    _w(env / "build" / TAG / "tts_review.json", json.dumps({"failed": [], "timing_errors": [], "new_synth": 2}))
    items = gate_c.run(TAG, VER)
    assert _bad(items) == {"品管"} and "新合成 2" in items[1]["note"]
    _w(env / "build" / TAG / "tts_review.json", json.dumps({"failed": [], "timing_errors": []}))
    monkeypatch.setattr(freeze, "check", lambda tag: "配音文本已改")
    items = gate_c.run(TAG, VER)
    assert _bad(items) == {"freeze"} and items[2]["note"] == "配音文本已改"
    monkeypatch.setattr(freeze, "check", lambda tag: None)
    (env / "output" / TAG / f"listen_{VER}.txt").unlink()
    (pd / f"ear_e4_{VER}.json").unlink()
    assert _bad(gate_c.run(TAG, VER)) == {"listen", "ear_e4"}


def test_gate_c_pron_undecided(env):
    _make_c(env)
    dec = env / "output" / TAG / f"decide_{VER}.md"
    items = gate_c.run(TAG, VER)  # 沒有 decide 檔 = 舊片相容
    assert not _bad(items) and items[-1]["id"] == "唸法" and "舊片相容" in items[-1]["note"]
    _w(dec, "# x\n\n英文唸法 0 筆|讀音標注 0 筆|疑似誤讀 3 筆(前 15;未跑)\n")
    assert not _bad(gate_c.run(TAG, VER))  # 疑似誤讀不算未定
    _w(dec, "# x\n\n英文唸法 1 筆|讀音標注 2 筆|疑似誤讀 0 筆\n")
    items = gate_c.run(TAG, VER)
    assert _bad(items) == {"唸法"} and "未定 3(英文 1、讀音 2)" in items[-1]["note"]
    _w(dec, "壞檔")
    assert _bad(gate_c.run(TAG, VER)) == {"唸法"}


def test_gate_e_spec_check(env, monkeypatch):
    _make_e(env)
    ctx = {"title": "片名", "board": {"stage": "已排程"}, "prod": {}}
    items = gate_e.run(TAG, VER, ctx)
    assert not _bad(items) and items[-1]["id"] == "spec_check" and "略過" in items[-1]["note"]
    _w(env / "projects" / TAG / "spec.json", "{}")

    class R:
        def __init__(self, rc, out):
            self.returncode, self.stdout, self.stderr = rc, out, ""
    monkeypatch.setattr(gate_e.subprocess, "run", lambda *a, **k: R(0, "spec_check demo\n警告 2 項、錯誤 0 項\n"))
    items = gate_e.run(TAG, VER, ctx)
    assert not _bad(items) and "警告 2" in items[-1]["note"]
    monkeypatch.setattr(gate_e.subprocess, "run", lambda *a, **k: R(1, "警告 0 項、錯誤 2 項\n  錯誤:標題缺名字\n"))
    items = gate_e.run(TAG, VER, ctx)
    assert _bad(items) == {"spec_check"} and "錯誤 2" in items[-1]["note"] and "標題缺名字" in items[-1]["note"]


def test_gate_d(env, monkeypatch):
    _make_d(env)
    assert not _bad(gate_d.run(TAG, VER, {"channel": "ChannelA"}))
    _w(env / "projects" / TAG / f"eye_{VER}.json", json.dumps({"ok": False, "items": [{"id": "黑幀", "ok": False}]}))
    items = gate_d.run(TAG, VER, {"channel": "ChannelA"})
    assert _bad(items) == {"eye"} and "黑幀" in items[-1]["note"]
    (env / "projects" / TAG / f"eye_{VER}.json").unlink()
    items = gate_d.run(TAG, VER, {})
    assert items[-1]["note"] == f"eye_{VER}.json 沒有"
    (env / "output" / TAG / f"{TAG}_{VER}.mp4").unlink()
    assert {"成片mp4", "片長"} <= _bad(gate_d.run(TAG, VER, {"channel": "ChannelA"}))
    # 片長:ChannelC不限;找不到 ffprobe 不過
    _make_d(env)
    monkeypatch.setattr(gate_d, "probe_secs", lambda p: 390.0)
    items = gate_d.run(TAG, VER, {"channel": "ChannelA"})
    assert not _bad(items) and "低於目標 7 分" in items[1]["note"]
    monkeypatch.setattr(gate_d, "probe_secs", lambda p: 330.0)
    assert not _bad(gate_d.run(TAG, VER, {"channel": "ChannelB"}))  # ChannelB考據片下限 5
    monkeypatch.setattr(gate_d, "probe_secs", lambda p: 348.0)
    items = gate_d.run(TAG, VER, {"channel": "ChannelA"})
    assert _bad(items) == {"片長"} and "<6,需使用者決定" in items[1]["note"]
    assert not _bad(gate_d.run(TAG, VER, {"channel": "ChannelC"}))
    monkeypatch.setattr(gate_d, "probe_secs", lambda p: None)
    items = gate_d.run(TAG, VER, {"channel": "ChannelB"})
    assert _bad(items) == {"片長"} and "ffprobe" in items[1]["note"]


def test_gate_d_precheck_errors(env):
    _make_d(env)
    _w(env / "output" / TAG / f"make_{VER}.log", "渲染前檢查: 鏡頭 1 個 | 錯誤 2\n")
    assert _bad(gate_d.run(TAG, VER, {"channel": "ChannelA"})) == {"渲染前檢查"}


def test_gate_e(env):
    _make_e(env)
    ctx = {"title": "片名", "board": {"stage": "已排程"}, "prod": {}}
    assert not _bad(gate_e.run(TAG, VER, ctx))
    _w(env / "output" / TAG / f"{VER}_說明.md", NOTES.format(t="(待填)"))
    items = gate_e.run(TAG, VER, ctx)
    assert _bad(items) == {"發片資料"} and "1 處" in items[0]["note"]
    # 不給 title:掃 yt_inbox 的 sidecar,tag 相符即命中並寫回 production.json.title
    c3 = {**ctx, "title": ""}
    assert "sidecar" not in _bad(gate_e.run(TAG, VER, c3)) and c3["title"] == "片名"
    assert json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))["title"] == "片名"
    _w(env / "V" / f"片名_{VER}.claude.json", json.dumps({"tag": "other"}))
    assert "sidecar" in _bad(gate_e.run(TAG, VER, {**ctx, "title": "", "board": {}}))
    # sidecar 被後端收走:有 video_id 或 board 已排程即算
    items = gate_e.run(TAG, VER, {**ctx, "title": "", "board": {}, "prod": {"artifacts": {"video_id": "VIDEO000001"}}})
    assert "sidecar" not in _bad(items) and "後端收走" in items[1]["note"]
    assert "sidecar" not in _bad(gate_e.run(TAG, VER, {**ctx, "title": ""}))
    # board 未排程但 production.json 有 video_id 與 publish_at 也算
    ctx2 = {"title": "片名", "board": {"stage": "E自審"}, "prod": {"artifacts": {"video_id": "VIDEO000002"}, "publish_at": "2026-11-02T18:00"}}
    assert "已排程" not in _bad(gate_e.run(TAG, VER, ctx2))
    assert "已排程" in _bad(gate_e.run(TAG, VER, {**ctx2, "prod": {}}))


def test_check_only_writes(env, capsys):
    _make_c(env)
    _w(env / "output" / TAG / f"{TAG}_{VER}.mp4")  # D 不完整
    assert D.main(_args("--check-only", "--title", "片名")) == 3
    d = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))
    assert d["gates"]["C"]["passed"] is True and d["gates"]["C"]["at"]
    assert d["gates"]["D"]["passed"] is False and d["gates"]["D"]["attempts"] == 1
    assert [b["seg"] for b in d["blocks"]] == ["D", "E"] and all(b["step"] == "gate" for b in d["blocks"])
    assert "卡點 D/gate" in capsys.readouterr().out
    _make_d(env)
    _make_e(env)
    assert D.main(_args("--check-only", "--title", "片名")) == 0
    d = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))
    assert all(d["gates"][s]["passed"] for s in "CDE") and len(d["blocks"]) == 2


def test_dry_run_sequence(env, capsys):
    assert D.main(_args("--dry-run", "--title", "片名", "--channel", "ChannelA")) == 0
    out = capsys.readouterr().out
    order = [out.index(k) for k in ("tts_c0.py", "tts_dispatch.py", "--tts-review --freeze", "senses/eye.py", "deliver.py")]
    assert order == sorted(order) and "--enqueue --publish-at auto" in out
    assert not D.prod_path(TAG).exists()


def _ns(**kw):
    import argparse
    base = dict(ver=VER, backend=None, title="片名", channel="ChannelA", publish_at="auto", cover=None)
    base.update(kw)
    return argparse.Namespace(**base)


def _step(steps, name):
    return next(s for s in steps if s["step"] == name)


def test_skip_conditions(env):
    a = _ns()
    ctx = D.run_ctx(TAG, a)
    sc = _w(env / "repo" / TAG / "script.txt")
    c0 = _w(env / "projects" / TAG / "c0_report.json", json.dumps({"wrong": 0}))
    _old(c0)
    steps = D.plan_steps(TAG, "C", ctx, a)
    assert not _step(steps, "c0")["skip"] and not _step(steps, "配音凍結")["skip"]
    assert _step(steps, "後端")["status_only"]
    _old(sc, 200)
    _w(env / "projects" / TAG / "freeze.json", "{}")
    _w(env / "build" / TAG / "tts_review.json", json.dumps({"failed": []}))
    steps = D.plan_steps(TAG, "C", ctx, a)
    assert _step(steps, "c0")["skip"] and _step(steps, "配音凍結")["skip"] and _step(steps, "後端")["skip"]
    # D:mp4 比 timeline_tts.json 新才略過
    mp = _w(env / "output" / TAG / f"{TAG}_{VER}.mp4")
    tl = _w(env / "build" / TAG / "timeline_tts.json", "{}")
    _old(mp)
    assert not _step(D.plan_steps(TAG, "D", ctx, a), "出片")["skip"]
    _old(tl, 200)
    assert _step(D.plan_steps(TAG, "D", ctx, a), "出片")["skip"]
    # E:sidecar 在且 board 已排程才略過;沒有 title 卡點
    _make_e(env)
    ctx = D.run_ctx(TAG, a)
    assert _step(D.plan_steps(TAG, "E", ctx, a), "交付排程")["skip"]
    a2 = _ns(title=None)
    assert _step(D.plan_steps(TAG, "E", D.run_ctx(TAG, a2), a2), "交付排程")["skip"]  # sidecar 掃得到,不需 --title
    (env / "V" / f"片名_{VER}.claude.json").unlink()
    st = _step(D.plan_steps(TAG, "E", D.run_ctx(TAG, a2), a2), "交付排程")
    assert not st["skip"] and st["block"] == "需要 --title"


def test_run_blocks_on_precheck_error(env, monkeypatch):
    """配音前預檢結束碼 1 -> 卡點「預檢」(reason 列出報告裡的 error 句),後面的步驟不跑;CV_SKIP_PRECHECK 略過。"""
    import tts_precheck as PC
    _w(env / "build" / TAG / "tts_script.md")
    _w(env / "projects" / TAG / "pron_review.md")
    calls = []

    def fake_exec(tag, ver, seg, step, cmd):
        calls.append(step)
        _w(env / "projects" / TAG / "tts_precheck.json",
           json.dumps({"items": [{"line": 7, "text": "同一期期刊", "level": "error", "code": "A", "msg": "拼音標記重複"}]}, ensure_ascii=False))
        return (1, "", "=== m") if step == "預檢" else (0, "", "=== m")

    monkeypatch.setattr(D, "_exec", fake_exec)
    monkeypatch.setattr(PC.P, "PROJECTS", env / "projects")
    assert D.main(_args()) == 3
    b = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))["blocks"][-1]
    assert calls == ["預檢"] and b["step"] == "預檢" and "第 7 行" in b["reason"] and "error 1 項" in b["reason"]
    calls.clear()
    monkeypatch.setenv("CV_SKIP_PRECHECK", "1")
    D.main(_args())
    assert "預檢" not in calls


def test_run_blocks_backend(env, monkeypatch, capsys):
    """未給 --backend:tts_dispatch 只印狀態 -> 卡點 待選後端;colab -> 卡點不跑。"""
    _w(env / "build" / TAG / "tts_script.md")
    _w(env / "projects" / TAG / "pron_review.md")
    calls = []

    def fake_exec(tag, ver, seg, step, cmd):
        calls.append(step)
        return (4, "Colab 可用\nKaggle 可用\n本機 可用", "=== m") if step == "後端" else (0, "", "=== m")

    monkeypatch.setattr(D, "_exec", fake_exec)
    assert D.main(_args()) == 3
    d = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))
    assert calls == ["預檢", "c0", "後端"] and d["blocks"][-1]["reason"].startswith("待選後端:Colab 可用")
    assert d["gates"]["C"]["attempts"] == 1 and "卡點 C/後端" in capsys.readouterr().out
    calls.clear()
    assert D.main(_args("--backend", "colab")) == 3
    assert calls == ["預檢", "c0"] and json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))["blocks"][-1]["reason"] == "Colab 要使用者上傳"
    # 達 --max-attempts 不再跑
    calls.clear()
    assert D.main(_args("--max-attempts", "2")) == 3 and calls == []


def test_run_precheck_and_rc(env, monkeypatch):
    """前置 B4 未完成 -> 卡點;配音凍結結束碼 3 -> 品管未過原因。"""
    monkeypatch.setattr(D, "_exec", lambda *a: (0, "", "=== m"))
    assert D.main(_args("--backend", "local")) == 3
    d = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))
    assert d["blocks"][-1]["step"] == "前置"
    _w(env / "build" / TAG / "tts_script.md")
    _w(env / "projects" / TAG / "pron_review.md")
    _w(env / "build" / TAG / "tts_review.json", json.dumps({"failed": [5], "timing_errors": []}))
    monkeypatch.setattr(D, "_exec", lambda tag, ver, seg, step, cmd: (3 if step == "配音凍結" else 0, "", "=== m"))
    import director_ab as AB  # 改句迴圈另測(test_director_ab),這裡只看配音凍結結束碼
    monkeypatch.setattr(AB, "step_qc", lambda *a: None)
    assert D.main(_args("--backend", "local", "--max-attempts", "9")) == 3
    b = json.loads(D.prod_path(TAG).read_text(encoding="utf-8"))["blocks"][-1]
    assert b["step"] == "配音凍結" and b["rc"] == 3 and b["reason"].startswith("品管未過:") and "品管未過 1" in b["reason"]
