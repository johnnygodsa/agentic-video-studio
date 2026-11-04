"""寫稿上下文組裝器:python -X utf8 -m pytest pipeline/tests/test_context_pack.py -q
不連網、不跑 Youtube AD:_run_cli 以 monkeypatch 回傳 fixture;輸出寫 repo tmp/ 下暫存目錄。"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import context_pack as CP  # noqa: E402
import paths  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "context_pack"
TAG = "ctx_demo"


@pytest.fixture
def env(monkeypatch):
    base = paths.REPO / "tmp"
    base.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="test_context_pack_", dir=base))
    proj = tmp / "projects" / TAG
    shutil.copytree(FIX / "project", proj)
    ytad = tmp / "ytad"
    (ytad / "tools").mkdir(parents=True)
    (ytad / "tools" / "intel_query.py").write_text("# stub\n", encoding="utf-8")
    shutil.copytree(FIX / "ytad_comments", ytad / "data" / "own" / "comments")
    shutil.copy(FIX / "outcomes.jsonl", tmp / "outcomes.jsonl")
    monkeypatch.setenv("YTAD_ROOT", str(ytad))
    monkeypatch.setattr(CP, "project_dir", lambda tag: tmp / "projects" / tag)
    monkeypatch.setattr(CP, "outcomes_file", lambda: tmp / "outcomes.jsonl")
    monkeypatch.setattr(CP, "_jieba", None)   # 本機有沒有 jieba 都走同一條路(fallback)
    calls = []
    brief_text = (FIX / "brief.json").read_text(encoding="utf-8")

    def ok(cmd, timeout, cwd):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="log line\n" + brief_text, stderr="")
    monkeypatch.setattr(CP, "_run_cli", ok)
    yield SimpleNamespace(tmp=tmp, proj=proj, ytad=ytad, calls=calls, monkeypatch=monkeypatch)
    shutil.rmtree(tmp, ignore_errors=True)


def _sections(md):
    out, cur = {}, None
    for line in md.splitlines():
        if line.startswith("## "):
            cur = line[3:]
            out[cur] = []
        elif cur and line.strip():
            out[cur].append(line)
    return out


def _run(env, *extra):
    data = CP.main(["--tag", TAG, "--channel", "ChannelA", "--event", "wowstress", *extra])
    md = (env.proj / "context.md").read_text(encoding="utf-8")
    js = json.loads((env.proj / "context.json").read_text(encoding="utf-8"))
    return data, md, js


def test_paths_ytad(env):
    assert paths.ytad_root() == env.ytad
    assert paths.ytad_export_latest() == env.ytad / "data" / "own" / "export" / "latest.json"
    assert paths.ytad_comments_dir() == env.ytad / "data" / "own" / "comments"


def test_normal_path_sections_and_json(env):
    _, md, js = _run(env)
    cmd = env.calls[0]
    assert cmd[3].endswith("intel_query.py") and cmd[4:] == ["brief", "wowstress", "--slot", "main", "--query", "魔獸永恆", "--json"]
    secs = _sections(md)
    assert list(secs) == list(CP.SECTIONS)
    for title in CP.SECTIONS:
        first = secs[title][0]
        assert first.startswith("來源:") and "|as_of:" in first and "|n:" in first, (title, first)
    assert "Stress Test Schedule" in "\n".join(secs["1 事件事實與一手來源"])
    assert any("own 資料落後" in x for x in secs["0 摘要與警示"])
    assert any("loyalty" in x for x in secs["7 待查疑點與資料缺口"])
    assert js["event_id"] == "evt_20261022_wowstress"
    assert js["competitor_videos_7d"] == 5
    assert js["same_event_seq"] == 3
    assert js["generated_at"] and js["ytad"]["ok"] is True
    # outcomes:同 subject 1 支 + 標題關鍵字 1 支,n<3 → 資料不足
    assert [m["tag"] for m in js["outcomes"]["matches"]] == ["wow_ban", "wow_old"]
    assert any("資料不足(n=2<3)" in x for x in secs["5 本頻道可比片與教訓"])


def test_brief_fields_section8(env):
    _, md, js = _run(env)
    lines = _sections(md)["8 brief 必填欄"]
    assert any(x.startswith("- 事件 ID:evt_20261022_wowstress") for x in lines)
    assert any("heat 3.2" in x and "來源 2 筆" in x and "報導量" in x for x in lines)
    assert any("官方預告:有" in x and "Stress Test Schedule" in x for x in lines)
    assert any("同事件近 7 天已發:3 支" in x and "搬運 1" in x for x in lines)
    bf = js["brief_fields"]
    assert bf["official"] is True and bf["same_event_7d"] == 3 and bf["n_sources"] == 2


@pytest.mark.parametrize("mode", ["timeout", "exit", "garbage"])
def test_ytad_unavailable_degrades(env, mode):
    def bad(cmd, timeout, cwd):
        if mode == "timeout":
            raise subprocess.TimeoutExpired(cmd, timeout)
        if mode == "exit":
            return SimpleNamespace(returncode=2, stdout="", stderr="Traceback\nKeyError: x")
        return SimpleNamespace(returncode=0, stdout="not json", stderr="")
    env.monkeypatch.setattr(CP, "_run_cli", bad)
    _, md, js = _run(env)
    secs = _sections(md)
    assert list(secs) == list(CP.SECTIONS)
    for title in ("1 事件事實與一手來源", "2 需求與競品覆蓋", "3 飽和度", "6 受眾輪廓", "8 brief 必填欄"):
        assert secs[title] == [secs[title][0]] and secs[title][0].startswith("無資料:Youtube AD 不可用:"), title
    assert js["ytad"]["ok"] is False and js["event_id"] == "wowstress"
    assert js["same_event_seq"] is None and js["competitor_videos_7d"] is None
    assert secs["4 玩家共識候選"][0].startswith("來源:")   # 留言仍照做
    want = {"timeout": "逾時", "exit": "結束碼 2:KeyError: x", "garbage": "解析失敗"}[mode]
    assert want in js["ytad"]["error"]


def test_no_ytad_flag_and_missing_script(env):
    _, md, js = _run(env, "--no-ytad")
    assert env.calls == [] and "--no-ytad" in js["ytad"]["error"]
    (env.ytad / "tools" / "intel_query.py").unlink()
    _, md, js = _run(env)
    assert "找不到" in js["ytad"]["error"] and env.calls == []


def test_comments_lang_split_and_quota(env):
    _, md, js = _run(env)
    cm = js["comments"]
    assert cm["n_raw"] == 23
    # a3 在兩片同 id、b2 正規化後同字 → 一則讚 30;純表情剔除;無關影片 ZZZunrelated 不讀
    assert cm["n_total"] == 20 and cm["n_other"] == 0
    assert cm["ytad_files"] == ["OWNvid00001.json"]
    assert cm["method"] == "字 bigram"
    assert js["comments_zh_n"] == 8 and js["comments_en_n"] == 12
    zh, en = cm["zh"], cm["en"]
    # 中文不足 20 則 → 全列,依讚數排序
    assert zh["listed_all"] and len(zh["items"]) == 8 and zh["groups"] == []
    assert zh["items"][0]["like_count"] == 30 and zh["items"][0]["videos"] == ["AAAAAAAAAAA", "BBBBBBBBBBB"]
    assert [x["like_count"] for x in zh["items"]] == sorted((x["like_count"] for x in zh["items"]), reverse=True)
    # 英文片 12 則只取前 10 則(每片配額),分群後列前 8 群
    assert not en["listed_all"] and en["n_sampled"] == CP.PER_VIDEO and en["n_groups"] == 10
    assert len(en["groups"]) == CP.MAX_GROUPS and min(g["likes"] for g in en["groups"]) == 93
    assert all(g["videos"] == ["CCCCCCCCCCC"] for g in en["groups"])
    assert all(len(x["rep"]) <= CP.REP_CHARS for x in en["groups"])
    src = {r["video_id"]: r for r in js["comment_sources"]}
    assert set(src) == {"AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC", "OWNvid00001"}
    assert [src[v]["lang"] for v in ("AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC", "OWNvid00001")] == ["zh", "zh", "en", "zh"]
    c = src["CCCCCCCCCCC"]
    assert (c["title"], c["channel"], c["view_count"], c["comment_count"], c["upload_date"]) == \
        ("WoW Forever Stress Test Recap", "EnglishTuber", 250000, 12, "2026-10-23")
    sec = "\n".join(_sections(md)["4 玩家共識候選"])
    assert sec.index("- 來源影片 4 支") < sec.index("### 4a 中文玩家") < sec.index("### 4b 英文玩家")
    assert "CCCCCCCCCCC|WoW Forever Stress Test Recap|EnglishTuber|觀看 250000|留言 12|上傳 2026-10-23|en" in sec


def test_cluster_merges_similar():
    top = [{"text": "上班日早上5點到9點 這個壓力個毛線", "like_count": 24, "videos": {"A"}, "flags": []},
           {"text": "上班日早上5點到9點 這壓力個毛線啦", "like_count": 3, "videos": {"A"}, "flags": []},
           {"text": "台服PVP蠻多人的", "like_count": 1, "videos": {"B"}, "flags": []}]
    groups, n = CP.cluster(top)
    assert n == 2 and groups[0]["likes"] == 27 and groups[0]["n"] == 2


def test_zh_many_uses_quota(monkeypatch):
    monkeypatch.setattr(CP, "_jieba", None)
    zh = ["".join(chr(0x4e00 + i * 11 + j) for j in range(5)) for i in range(25)]
    raw = {"ref_files": [], "ytad_files": [], "sources": [], "as_of": None,
           "comments": [{"id": f"z{i}", "text": t, "like_count": 100 - i, "videos": {"V1"}} for i, t in enumerate(zh)]
           + [{"id": "w1", "text": "另一支片的留言", "like_count": 1, "videos": {"V2"}}]}
    part = CP.analyze_comments(raw)["zh"]
    assert part["n"] == 26 and not part["listed_all"]
    assert part["n_sampled"] == CP.PER_VIDEO + 1 and len(part["groups"]) == CP.MAX_GROUPS


def test_lang_of():
    assert CP.lang_of("台服PVP蠻多人的") == "zh" and CP.lang_of("骂ai的视频") == "zh"
    assert CP.lang_of("Hardcore mode please") == "en"
    assert CP.lang_of("666 👍") == "other" and CP.lang_of("こんにちは") == "other"


def test_flags(env):
    _, md, js = _run(env)
    cm = js["comments"]
    zh, en = cm["zh"], cm["en"]
    assert zh["by_flag"]["AI"] == 1 and zh["by_flag"]["邏輯"] == 1 and zh["by_flag"]["標題誇大"] == 1
    assert zh["by_flag"]["沒玩過"] == 1 and zh["by_flag"]["立場附和"] == 1
    assert zh["credibility_total"] == 3 and en["credibility_total"] == 1 and en["by_flag"] == {"沒玩過": 1}
    assert cm["by_flag"]["沒玩過"] == 2 and cm["credibility_total"] == 4
    # 旗標範例只列中文;英文只給計數
    assert "flagged_examples" not in en
    assert all("CCCCCCCCCCC" not in e["videos"] for ex in zh["flagged_examples"].values() for e in ex)
    sec = _sections(md)["4 玩家共識候選"]
    assert any(x.startswith("  - 沒玩過|讚 4|OWNvid00001") for x in sec)
    assert not any(x.startswith("  - 沒玩過|讚 96") for x in sec)
    assert any("旗標(英文全部 12 則" in x and "沒玩過 1" in x for x in sec)
    assert "可信度抱怨 中文 3/8、英文 1/12" in "\n".join(_sections(md)["0 摘要與警示"])
    lex, cred = CP.load_lexicon()
    assert "立場附和" in lex and "立場附和" not in cred
    assert json.loads(CP.LEXICON.read_text(encoding="utf-8"))["_note"]


def test_cluster_cap_and_clip(monkeypatch):
    monkeypatch.setattr(CP, "_jieba", None)
    texts = ["甲乙丙丁戊", "子丑寅卯辰", "天地玄黃宇", "日月盈昃辰宿", "寒來暑往秋收", "金生麗水玉出",
             "劍號巨闕珠稱", "果珍李柰菜重", "海鹹河淡鱗潛", "龍師火帝鳥官" + "長" * 200]
    top = [{"text": t, "like_count": 10 - i, "videos": {"v"}, "flags": []} for i, t in enumerate(texts)]
    groups, n = CP.cluster(top)
    assert n == 10 and len(groups) == CP.MAX_GROUPS
    long = CP.cluster([top[-1]])[0][0]["rep"]
    assert len(long) == CP.REP_CHARS and long.endswith("…")


def test_tokens_fallback_and_jieba(monkeypatch):
    monkeypatch.setattr(CP, "_jieba", None)
    assert CP.tokens("AI 配音!") == {"ai", "配音"}
    assert CP.tokens("上班日5點 the fire") == {"上班", "班日", "5", "點", "the", "fire"}
    assert CP.token_method() == "字 bigram"
    fake = SimpleNamespace(lcut=lambda s: ["AI配音", " ", "!"])
    monkeypatch.setattr(CP, "_jieba", fake)
    assert CP.tokens("AI 配音!") == {"ai配音"} and CP.token_method() == "jieba 詞重疊"


def test_parse_brief_wrapped():
    doc = json.loads((FIX / "brief.json").read_text(encoding="utf-8"))
    assert CP._parse_brief(json.dumps({"doc": doc, "path": "x"}))["event"]["id"] == doc["event"]["id"]
    with pytest.raises(ValueError):
        CP._parse_brief('{"foo": 1}')


def test_missing_sources_write_no_data(env):
    shutil.rmtree(env.proj / "comments_ref")
    shutil.rmtree(env.ytad / "data")
    (env.tmp / "outcomes.jsonl").unlink()
    (env.proj / "spec.json").unlink()
    _, md, js = _run(env, "--no-ytad")
    secs = _sections(md)
    for title in CP.SECTIONS[1:7] + CP.SECTIONS[8:]:
        assert len(secs[title]) == 1 and secs[title][0].startswith("無資料:"), title
    assert js["comments"] is None and js["outcomes"]["exists"] is False
    assert any("spec.json 不存在" in g for g in js["gaps"])
