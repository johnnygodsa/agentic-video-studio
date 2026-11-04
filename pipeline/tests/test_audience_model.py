"""觀眾模型:python -X utf8 -m pytest pipeline/tests/test_audience_model.py -q
全部用 tmp_path 假 root 與假 Youtube AD 目錄,不碰真實資料。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import audience_model as AM  # noqa: E402


def _w(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _c(i, text, like, author):
    return {"id": i, "parent": None, "text": text, "like_count": like, "author": author}


def _setup(tmp_path):
    root, yt = tmp_path / "root", tmp_path / "yt"
    (root / "channel").mkdir(parents=True)
    (root / "channel" / "outcomes.jsonl").write_text(
        json.dumps({"channel": "ChannelA", "tag": "demo", "video_id": "VID_OWN", "title_angle": "判"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    _w(root / "projects" / "demo" / "spec.json", {"channel": "ChannelA"})
    _w(root / "projects" / "rival" / "spec.json", {"channel": "ChannelB"})
    # YT AD own_comments 格式
    own = {"video_id": "VID_OWN", "title": "自製片標題標題標題標題標題標題", "channel": "ChannelA",
           "captured_at": "2026-10-29T01:00:00+08:00", "n_total": 3, "status": "ok", "summary": {},
           "comments": [_c("a", "你這AI配音聽起來很怪 資訊錯誤太多", 9, "@u1"),
                        _c("b", "說得對 就不買了", 30, "@u2"),
                        _c("a2", "說得對 就不買了", 5, "@u2")]}  # 與 b 同鍵 → 去重
    _w(yt / "VID_OWN.json", own)
    # 同一支自製片在 comments_ref 又存一份(要被去重)
    _w(root / "projects" / "demo" / "comments_ref" / "VID_OWN.comments.json", own)
    # yt-dlp info.json(競品,專案 demo → ChannelA)
    info = {"id": "VID_RIVAL", "title": "Rival Video", "channel": "IGN", "epoch": 1790000000,
            "comments": [{"id": "x", "parent": "root", "text": "沒玩過還亂講", "like_count": 100, "author": "@r1"},
                         {"id": "y", "parent": "root", "text": "great review wrong price", "like_count": 3, "author": "@r2"}]}
    _w(root / "projects" / "demo" / "comments_ref" / "VID_RIVAL.info.json", info)
    # yt-dlp 純陣列(專案 rival → ChannelB)+ 旁邊的 info.json 提供標題
    _w(root / "projects" / "rival" / "comments_ref" / "VID_LIST.comments.json",
       [{"id": "z", "parent": "root", "text": "遊戲優化真的很差", "like_count": 7, "author": "@l1"}])
    _w(root / "projects" / "rival" / "comments_ref" / "VID_LIST.info.json", {"id": "VID_LIST", "title": "List Title", "epoch": 1790000000})
    return root, yt


def test_parse_formats(tmp_path):
    root, yt = _setup(tmp_path)
    a = AM.parse_file(yt / "VID_OWN.json")
    assert a["kind"] == "own" and a["video_id"] == "VID_OWN" and len(a["comments"]) == 3
    b = AM.parse_file(root / "projects/demo/comments_ref/VID_RIVAL.info.json")
    assert b["kind"] == "info" and b["video_id"] == "VID_RIVAL" and b["captured_at"].endswith("+08:00")
    c = AM.parse_file(root / "projects/rival/comments_ref/VID_LIST.comments.json")
    assert c["kind"] == "list" and c["video_id"] == "VID_LIST" and c["title"] == "List Title"


def test_flags_and_axis():
    lex = AM.load_lexicon()
    r = AM.classify("你這AI配音聽起來很怪 資訊錯誤太多", lex)
    assert "AI" in r["flags"] and "資訊錯誤" in r["flags"] and r["axis"] == "video"
    assert AM.classify("今天天氣真好", lex)["flags"] == [AM.OTHER]
    assert AM.classify("遊戲優化真的很差", lex)["axis"] == "game"


def test_run_dedupe_channels_idempotent(tmp_path):
    root, yt = _setup(tmp_path)
    out = tmp_path / "out"
    rows, meta, jp, sp = AM.run("ChannelA", root=root, ytad_dir=yt, out_dir=out)
    # 自製 2(b/a2 同鍵去重、comments_ref 重複檔去重)+ 競品 2;ChannelB的 VID_LIST 不計入
    assert len(rows) == 4 and sum(r["is_own"] for r in rows) == 2
    assert {r["video_id"] for r in rows} == {"VID_OWN", "VID_RIVAL"}
    dup = [r for r in rows if r["text"].startswith("說得對")]
    assert len(dup) == 1 and dup[0]["like"] == 30  # 同鍵取較大讚數
    assert all(r["tag"] == "demo" for r in rows)
    assert (jp.name, sp.name) == ("ChannelA_comments.jsonl", "ChannelA_stats.md")
    first = (jp.read_bytes(), sp.read_bytes())
    AM.run("ChannelA", update=True, root=root, ytad_dir=yt, out_dir=out)
    assert (jp.read_bytes(), sp.read_bytes()) == first  # 冪等
    txt = sp.read_text(encoding="utf-8")
    assert txt.splitlines()[1].startswith("as_of ") and "n=4" in txt
    assert "資訊錯誤 旗標原句(自製片全部 1 則)" in txt and "判" in txt
    rows2, *_ = AM.run("ChannelB", root=root, ytad_dir=yt, out_dir=out)
    assert len(rows2) == 1 and rows2[0]["title"] == "List Title"


def test_update_keeps_vanished_rows(tmp_path):
    root, yt = _setup(tmp_path)
    out = tmp_path / "out"
    AM.run("ChannelA", root=root, ytad_dir=yt, out_dir=out)
    (yt / "VID_OWN.json").unlink()
    (root / "projects/demo/comments_ref/VID_OWN.comments.json").unlink()
    rows, *_ = AM.run("ChannelA", update=True, root=root, ytad_dir=yt, out_dir=out)
    assert len(rows) == 4
    rows, *_ = AM.run("ChannelA", update=False, root=root, ytad_dir=yt, out_dir=out)
    assert len(rows) == 2


def test_polarity_and_bigram():
    assert AM.polarity("說得對") == "pos"
    assert AM.polarity("你亂講") == "neg"
    assert AM.polarity("這遊戲不錯") == "pos"
    assert "玩家" in AM.bigrams("玩家真的很生氣") and "的玩" not in AM.bigrams("玩家的")
    assert AM.bigrams("游戏") == AM.bigrams("遊戲")  # 簡繁同一


# ───────────── persona_status ─────────────
from datetime import datetime  # noqa: E402

NOW = datetime(2026, 10, 29)


def _persona_setup(tmp_path, n_own=100, as_of="2026-10-29", n_now=100, body="切角 判 數", outcomes=None, meta=True, angles=None):
    root = tmp_path / "root"
    ad = root / "channel" / "audience"
    ad.mkdir(parents=True)
    ang = "" if angles is None else ',"angles":' + json.dumps(angles, ensure_ascii=False)
    head = '<!-- persona_meta: {"as_of":"%s","n_own":%d,"n_all":999%s} -->\n' % (as_of, n_own, ang) if meta else ""
    (ad / "ChannelA_personas.md").write_text(head + "# 人設\n" + body + "\n", encoding="utf-8")
    (ad / "ChannelA_stats.md").write_text(f"# ChannelA 觀眾模型統計\nas_of x｜n=999(自製片 {n_now}、競品 1)｜x\n", encoding="utf-8")
    if outcomes:
        (root / "channel" / "outcomes.jsonl").write_text(
            "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in outcomes), encoding="utf-8")
    return root


def test_persona_status_ok(tmp_path):
    root = _persona_setup(tmp_path, n_own=100, n_now=120, outcomes=[
        {"channel": "ChannelA", "published_at": "2026-10-20T00:00:00Z", "title_angle": "判"}])
    st = AM.persona_status("ChannelA", root=root, now=NOW)
    assert st["status"] == "OK" and st["n_now"] == 120 and st["n_persona"] == 100


def test_persona_status_grown_30pct_expired(tmp_path):
    root = _persona_setup(tmp_path, n_own=100, n_now=130)
    st = AM.persona_status("ChannelA", root=root, now=NOW)
    assert st["status"] == "過期" and "100→130" in st["reason"]


def test_persona_status_missing_file_expired(tmp_path):
    root = tmp_path / "root"
    (root / "channel" / "audience").mkdir(parents=True)
    st = AM.persona_status("ChannelA", root=root, now=NOW)
    assert st["status"] == "過期" and "不存在" in st["reason"]


def test_persona_status_old_noMeta_and_new_angle(tmp_path):
    assert "天" in AM.persona_status("ChannelA", root=_persona_setup(tmp_path / "a", as_of="2026-07-01"), now=NOW)["reason"]
    assert "persona_meta" in AM.persona_status("ChannelA", root=_persona_setup(tmp_path / "b", meta=False), now=NOW)["reason"]
    root = _persona_setup(tmp_path / "c", outcomes=[
        {"channel": "ChannelA", "published_at": "2026-10-20T00:00:00Z", "title_angle": "獵奇", "video_id": "V9"},
        {"channel": "ChannelA", "published_at": "2026-08-01T00:00:00Z", "title_angle": "舊切角"},   # 超過 30 天不算
        {"channel": "ChannelB", "published_at": "2026-10-20T00:00:00Z", "title_angle": "別頻道"}])
    (root / "channel" / "audience" / "ChannelA_comments.jsonl").write_text('{"video_id": "V9"}' + chr(10), encoding="utf-8")
    st = AM.persona_status("ChannelA", root=root, now=NOW)
    assert st["status"] == "過期" and "新切角:獵奇" in st["reason"] and "舊切角" not in st["reason"] and "別頻道" not in st["reason"]


def test_persona_status_angles_in_meta(tmp_path):
    oc = [{"channel": "ChannelA", "published_at": "2026-10-20T00:00:00Z", "title_angle": "判", "video_id": "V1"},
          {"channel": "ChannelA", "published_at": "2026-10-21T00:00:00Z", "title_angle": "獵奇", "video_id": "V2"}]

    def comments(root, *vids):   # 該 video_id 的留言已在 comments.jsonl
        (root / "channel" / "audience" / "ChannelA_comments.jsonl").write_text(
            "".join(json.dumps({"video_id": v, "is_own": True}) + chr(10) for v in vids), encoding="utf-8")

    # 有 angles 鍵:只比對 angles,正文有沒有提都不算
    ok = _persona_setup(tmp_path / "a", angles=["判", "獵奇"], body="正文沒切角", outcomes=oc)
    comments(ok, "V1", "V2")
    assert AM.persona_status("ChannelA", root=ok, now=NOW)["status"] == "OK"
    # 新切角但該片留言已在模型 -> 過期
    bad = _persona_setup(tmp_path / "b", angles=["判"], body="正文提到 獵奇", outcomes=oc)
    comments(bad, "V1", "V2")
    assert "新切角:獵奇" in AM.persona_status("ChannelA", root=bad, now=NOW)["reason"]
    # 新切角但該片還沒抓留言 -> 不過期,只提示
    pend = _persona_setup(tmp_path / "d", angles=["判"], outcomes=oc)
    comments(pend, "V1")
    st = AM.persona_status("ChannelA", root=pend, now=NOW)
    assert st["status"] == "OK" and "切角 獵奇 的片尚無留言檔:結案 24h 抓後再更新" in st["reason"]
    # n_own=0 且樣本不足 -> 過期並註明樣本不足
    z = _persona_setup(tmp_path / "c", n_own=0, n_now=0, angles=[], outcomes=oc)
    st = AM.persona_status("ChannelA", root=z, now=NOW)
    assert st["status"] == "樣本不足" and "不重寫" in st["reason"]
