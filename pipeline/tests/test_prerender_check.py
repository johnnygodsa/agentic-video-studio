"""P3 B 段預渲染檢查(prerender_check.py):python -X utf8 pipeline/tests/test_prerender_check.py
假片放 repo tmp/ 下暫存目錄;build 子行程以 runner 注入假輸出,不真跑 build、不吃 GPU。失敗結束碼非 0。"""
import json
import shutil
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import paths  # noqa: E402
import prerender_check as PC  # noqa: E402
from gates import specs  # noqa: E402

TAG = "demo_pre"
DOOR_D = ("錯誤: 句8: 標籤「sweet_door」挑不到 4.9 秒的片段(片段不足、太短或來源已達使用上限)\n"
          "錯誤: 句32: 重點區過大,請拆成兩張截圖(door_fb2)\n"
          "錯誤: 句14: 標籤「cta」挑不到 6.2 秒的片段(clips 沒有這個標籤)\n"
          "錯誤: 句46-48: 重點區過大,請拆成兩張截圖(ps5own_n_f20)\n"
          "錯誤: 句15: 同一影片片段 8.20 秒 > 8 秒\n"
          "錯誤: 句3: images/door_x.png 不存在\n"
          "錯誤: 句4-5: raw/re2_trailer.mp4 不存在\n"
          "錯誤: 句6: 標籤「door_hd」挑不到 3.0 秒的片段(clips 沒有這個標籤)\n"
          "錯誤: 句7: anim emoji 名稱不存在: 'zzz'(可用: a/b)\n"
          "錯誤: 句9: hl「鎖門」在 door_fb2 找不到\n"
          "渲染前檢查: 鏡頭 69 個 | 卡片 2 張 | 動畫鏡頭 2 個 | 警告 38 | 錯誤 10\n")


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    root = base / f"test_pre_{uuid.uuid4().hex[:8]}"
    root.mkdir()
    for attr, sub in (("PROJECTS", "projects"), ("BUILD", "build"), ("TMP", "tmp")):
        monkeypatch.setattr(paths, attr, root / sub)
    monkeypatch.setattr(paths, "REPO", root)
    sc = root / TAG / "script.json"
    sc.parent.mkdir(parents=True)
    sc.write_text(json.dumps({"title": "t", "sections": [
        {"name": "a", "lines": [{"text": "字" * 30, "v": "door_hd"}, {"text": "字" * 60, "img": "x", "pause": 1.0}]},
        {"name": "b", "lines": [{"text": "字" * 15, "say": "字" * 45, "v": "cta"}]}]}, ensure_ascii=False), encoding="utf-8")
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _by(errors, kind):
    return [e for e in errors if e["kind"] == kind]


def test_classify_d_stage_messages():
    errs, other, done = PC.parse(DOOR_D)
    assert done and other == ["句9: hl「鎖門」在 door_fb2 找不到"]
    assert {e["kind"] for e in errs} == set(PC.KINDS)
    big = _by(errs, "hl_too_big")
    assert [(e["line"], e["line_end"], e["label"], e["fix"]) for e in big] == [(32, 32, "door_fb2", "asset"), (46, 48, "ps5own_n_f20", "asset")]
    miss = {(e["line"], e["label"]): e["fix"] for e in _by(errs, "clip_tag_miss")}
    assert miss == {(8, "sweet_door"): "asset", (4, "re2_trailer"): "asset", (6, "door_hd"): "line"}
    cta = _by(errs, "cta_anim_missing")
    assert [(e["line"], e["label"], e["fix"]) for e in cta] == [(14, "cta", "asset"), (7, "'zzz'(可用:", "line")] or \
        [(e["line"], e["fix"]) for e in cta] == [(14, "asset"), (7, "line")]
    assert [(e["line"], e["fix"]) for e in _by(errs, "clip_too_long")] == [(15, "line")]
    assert [(e["label"], e["fix"]) for e in _by(errs, "image_missing")] == [("door_x", "asset")]
    assert all(e["msg"] and not e["msg"].startswith("錯誤") for e in errs)


def test_parse_no_summary_is_failure():
    res = dict(errors=[], other=[], rc=1, done=False, timeline="", tail=["timeline 缺句 3"])
    assert PC.exit_code(res) == 2 and "沒跑完" in PC.summary(res)


def test_est_timeline_shape_and_total(env):
    tl = PC.est_timeline(env / TAG / "script.json")
    ls = tl["lines"]
    assert [l["idx"] for l in ls] == [1, 2, 3] and ls[2]["text"] == "字" * 15  # text 要與 script 同(build.load_timeline 會比對)
    assert ls[1]["start"] - ls[0]["end"] == pytest.approx(PC.GAP, abs=1e-3)
    assert ls[2]["start"] - ls[1]["end"] == pytest.approx(1.0, abs=1e-3)       # pause 1.0 > 段間 0.30
    assert ls[0]["visual_end"] == ls[1]["start"] and ls[2]["visual_end"] == tl["total"]
    assert (ls[2]["end"] - ls[2]["start"]) > (ls[0]["end"] - ls[0]["start"])     # say 45 字 > text 30 字
    speech = ls[-1]["end"] - ls[0]["start"]
    assert speech == pytest.approx(135 / specs.SPEECH_CPM * 60, rel=0.01)       # 整段(含停頓)= 字數 ÷ CPM


def test_check_runs_build_check_only(env):
    seen = []

    def runner(cmd):
        seen.append(cmd)
        return 1, DOOR_D
    res = PC.check(TAG, runner=runner)
    cmd = seen[0]
    assert "--check-only" in cmd and "--timeline" in cmd and "--tts-only" not in cmd and "--force" not in cmd
    assert cmd[cmd.index("--tag") + 1] == TAG and "--clips" not in cmd           # 沒有 clips 檔就不給
    assert Path(cmd[cmd.index("--timeline") + 1]) == paths.BUILD / TAG / "timeline_est.json"
    assert Path(cmd[cmd.index("--out") + 1]).parent == paths.TMP / "prerender"
    assert PC.exit_code(res) == 1 and len(res["errors"]) == 9 and len(res["other"]) == 1


def test_work_tag_keeps_original_build(env):
    (paths.BUILD / TAG).mkdir(parents=True)
    (paths.BUILD / TAG / "luma_cache.json").write_text("{}", encoding="utf-8")
    seen = []
    res = PC.check(TAG, work_tag="_pre_x", runner=lambda c: (seen.append(c), (0, "渲染前檢查: 鏡頭 3 個 | 錯誤 0\n"))[1])
    assert seen[0][seen[0].index("--tag") + 1] == "_pre_x" and PC.exit_code(res) == 0
    assert sorted(p.name for p in (paths.BUILD / TAG).iterdir()) == ["luma_cache.json"]   # 原片 build 不多檔
    assert (paths.BUILD / "_pre_x" / "timeline_est.json").exists()


# ---------------------------------------------------------------- director B 段 prerender 步
def _err(kind, line, fix, label="x"):
    return dict(kind=kind, line=line, line_end=line, label=label, msg=f"句{line}: {kind} {label}", fix=fix)


def _res(errs):
    return dict(errors=errs, other=[], rc=1 if errs else 0, done=True, timeline="", tail=[])


@pytest.fixture
def ab(monkeypatch):
    import director_ab as AB
    from gates import gate_b
    log = dict(llm=[], fix=[], checks=0)
    monkeypatch.setattr(AB, "_txt2json", lambda tag: (0, ""))
    monkeypatch.setattr(AB, "script_rows", lambda tag: {i: i + 10 for i in range(1, 100)})
    monkeypatch.setattr(AB, "flow", lambda tag: "v3")
    monkeypatch.setattr(gate_b, "narration_hashes", lambda tag: ["h1", "h2"])

    def call(tag, fn, prompt, **kw):
        log["llm"].append((fn, kw.get("agent"), prompt))
        return SimpleNamespace(ok=True, data={"items": []}, limited=False, error="", text="")
    monkeypatch.setattr(AB, "CALL", call)
    monkeypatch.setattr(AB, "_fix", lambda tag, items, mode: log["fix"].append((items, mode)) or {})
    return AB, log


def _seq(monkeypatch, AB, log, results):
    it = iter(results)

    def pre(tag):
        log["checks"] += 1
        return next(it)
    monkeypatch.setattr(AB, "_prerender", pre)


def test_step_fixes_then_passes_round2(ab, monkeypatch):
    AB, log = ab
    _seq(monkeypatch, AB, log, [_res([_err("hl_too_big", 32, "asset", "door_fb2"), _err("clip_tag_miss", 6, "line", "door_hd"),
                                     _err("clip_too_long", 15, "line")]), _res([])])
    AB.step_prerender(TAG)
    assert log["checks"] == 2
    assert [(fn, ag) for fn, ag, _ in log["llm"]] == [("prerender_assets", "asset-collector")]
    assert "door_fb2" in log["llm"][0][2] and "--check" in log["llm"][0][2] and "第 42 行" in log["llm"][0][2]
    items, mode = log["fix"][0]
    assert mode == "visual" and sorted(i["line"] for i in items) == [16, 25]   # 句號 → script.txt 行號


def test_step_clean_no_llm(ab, monkeypatch):
    AB, log = ab
    _seq(monkeypatch, AB, log, [_res([])])
    AB.step_prerender(TAG)
    assert log["checks"] == 1 and not log["llm"] and not log["fix"]


def test_step_blocks_after_two_rounds(ab, monkeypatch):
    AB, log = ab
    e = _err("image_missing", 3, "asset", "door_x")
    _seq(monkeypatch, AB, log, [_res([e])] * 3)
    with pytest.raises(AB.Block) as bk:
        AB.step_prerender(TAG)
    assert log["checks"] == 3 and len(log["llm"]) == 2 and "2 輪未清" in bk.value.reason and "image_missing 1" in bk.value.reason


def test_step_blocks_when_assets_touch_narration(ab, monkeypatch):
    AB, log = ab
    from gates import gate_b
    h = iter([["a"], ["b"]])
    monkeypatch.setattr(gate_b, "narration_hashes", lambda tag: next(h))
    _seq(monkeypatch, AB, log, [_res([_err("hl_too_big", 2, "asset")])])
    with pytest.raises(AB.Block) as bk:
        AB.step_prerender(TAG)
    assert "旁白被改動" in bk.value.reason


def test_step_build_not_finished_blocks(ab, monkeypatch):
    AB, log = ab
    _seq(monkeypatch, AB, log, [dict(errors=[], other=[], rc=1, done=False, timeline="", tail=["timeline 缺句 3"])])
    with pytest.raises(AB.Block) as bk:
        AB.step_prerender(TAG)
    assert "沒跑完" in bk.value.reason


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
