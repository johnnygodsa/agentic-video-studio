"""字幕斷句測試:python -X utf8 pipeline\tests\test_sub_split.py [tag](預設 turtle)"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import build as B  # noqa: E402
import seg as SEG  # noqa: E402


def norm(s):
    return re.sub(r"[\s，。？！、：；「」『』《》（）()…·—\-,;:?!\"“”‘’~～]", "", s)


def run(fn, text):
    old = B._split_long
    B._split_long = fn
    try:
        return B.split_phrases(text)
    finally:
        B._split_long = old


def test_title_colon():
    """書名號內的冒號:字幕顯示成空格、不斷段、書名不拆;書名號外的冒號照舊。"""
    ph = [t for t, _ in B.split_phrases("結果《惡靈古堡:安魂曲》有一半在玩里昂,這一半根本不是用來嚇你的。")]
    hit = [t for t in ph if "惡靈古堡" in t]
    assert len(hit) == 1 and "惡靈古堡 安魂曲" in hit[0], ph
    assert not any(c in B.SUB_PUNCT for t in ph for c in t), ph
    ph = [t for t, _ in B.split_phrases("《異形:孤立》更狠。")]
    assert ph == ["異形 孤立 更狠"], ph
    assert [t for t, _ in B.split_phrases("總監說:不行")] == ["總監說", "不行"]
    assert [t for t, _ in B.split_phrases("總監說:《異形》不行")] == ["總監說", "異形 不行"]
    # 全形冒號同樣處理
    assert [t for t, _ in B.split_phrases("《惡靈古堡：安魂曲》好玩")] == ["惡靈古堡 安魂曲 好玩"]
    # 超過一段上限時,切點不可落在書名裡(書名本身 <= SUB_MAX_W)
    long = "我昨天晚上在家裡認真地把《惡靈古堡:安魂曲》從頭到尾玩完了而且還玩了兩遍"
    segs = [t for t, _ in B.split_phrases(long)]
    assert len(segs) > 1 and any("惡靈古堡 安魂曲" in t for t in segs), segs
    assert not B.sub_seams(long) or all("書名" not in x[2] for x in B.sub_seams(long))


def test_relax_order():
    """F2-3b:合法切點無解要放寬時,先放寬數字與量詞、再放寬其他,書名號內最後(直式 10 字上限)。"""
    B.set_sub_profile("portrait")
    try:
        segs = [t for t, _ in B.split_phrases("這是 Kotaku 10 月 7 日寫《戰爭機器:事變日》的文章")]
        assert any("戰爭機器 事變日" in t for t in segs), segs
        assert all(B._dw(B.TOKEN_RE.findall(t)) <= B.SUB_MAX_W for t in segs), segs
        assert [B._relax_rank(w) for w in (None, "數字與量詞", "詞「地方」", "書名號內", "括號或空白")] == [0, 1, 2, 3, None]
    finally:
        B.set_sub_profile("landscape")


# ---- T2:可切換斷詞器(jieba 預設;ckip 用假 ws 驗介面與 sub_words 合併,真模型不可用就 skip)----
SEG_TEXT = "我昨天晚上在家裡認真地玩完了星塵獵犬而且還玩了兩遍真的很好玩"      # jieba 會切在「了|星塵」


def _fake_ws(lexicon):
    """假的 CkipWordSegmenter:最長詞優先,其餘單字;可模擬模型吃掉空白(drop_space)。介面同 ws(list[str], **kw) -> list[list[str]]。"""
    lex = sorted(lexicon, key=len, reverse=True)

    def ws(texts, **kw):
        out = []
        for t in texts:
            words, i = [], 0
            while i < len(t):
                w = next((x for x in lex if t.startswith(x, i)), t[i])
                words.append(w)
                i += len(w)
            out.append([x for x in words if not x.isspace()])      # 模擬模型吃掉空白,讓 align_words 對回原文
        return out
    return ws


def _with_seg(name, ckip=None):
    old = (SEG._name, SEG._OBJS.get("ckip", "unset"))
    SEG.set_seg(name)
    if ckip is not None:
        SEG._OBJS["ckip"] = ckip
    return old


def _restore_seg(old):
    SEG._name = old[0]
    if old[1] == "unset":
        SEG._OBJS.pop("ckip", None)
    else:
        SEG._OBJS["ckip"] = old[1]


def test_seg_default_is_jieba():
    """預設斷詞器 = jieba(沒設 CV_SEG);cut 回傳詞 join == 原文,且吃 sub_words.txt。"""
    import os
    assert os.environ.get(SEG.ENV_SEG, "") in ("", "jieba") and SEG.seg_name() == "jieba"
    sg = SEG.segmenter()
    assert sg.name == "jieba"
    for t in ("至於它後來怎麼從人事部門一路管到遊戲裡的角色", "這家公司去年才剛請了一位多元長專門負責這件事", "2000 年元旦開幕"):
        w = sg.cut(t)
        assert "".join(w) == t, w
    assert "多元長" in sg.cut("請了一位多元長專門負責")
    segs = [t for t, _ in B.split_phrases(SEG_TEXT)]
    assert len(segs) == 2 and segs[0].endswith("玩完了") and segs[1].startswith("星塵"), segs     # jieba:切在「了|星塵」


def test_seg_ckip_mock():
    """ckip 介面(假 ws):sub_words 後處理併詞、模型吃空白能對回原文、拆段切點尊重 ckip 的詞、接縫判讀可換斷詞器。"""
    ck = SEG.CkipSeg(ws=_fake_ws(["了星", "多", "元", "長"]), sub_words_list=["多元長"])
    old = _with_seg("ckip", ck)
    try:
        sg = SEG.segmenter()
        assert sg is ck and sg.name == "ckip"
        w = sg.cut("請了一位多元長專門")
        assert "".join(w) == "請了一位多元長專門" and "多元長" in w, w            # 「多|元|長」被 sub_words 併成一詞
        assert "".join(sg.cut("2000 年 元旦")) == "2000 年 元旦"                   # 假模型吃掉空白,仍對回原文
        assert sg.fallback_calls == 0
        segs = [t for t, _ in B.split_phrases(SEG_TEXT)]
        assert all(("了" in s and "星" in s) is False or "了星" in s for s in segs), segs      # 假詞「了星」不可被切開
        assert not any(a.endswith("了") and b.startswith("星") for a, b in zip(segs, segs[1:])), segs
        assert "".join(segs) == SEG_TEXT, segs
        toks = B.TOKEN_RE.findall(SEG_TEXT)
        why = B._cut_reasons(toks)
        assert "了星" in (why[toks.index("星")] or ""), why                          # 原因註明 ckip 詞
        assert B._cut_reasons(toks, seg="jieba")[toks.index("星")] is None          # 同一位置 jieba 判讀可切
        # 另一個判讀斷詞器:ckip 拆的段用 jieba 判讀,不報錯
        assert isinstance(B.sub_seams(SEG_TEXT, judge="jieba"), list)
    finally:
        _restore_seg(old)


def test_seg_merge_and_align():
    assert SEG.merge_sub_words("請多元長來", ["請", "多", "元", "長", "來"], ["多元長"]) == ["請", "多元長", "來"]
    assert SEG.merge_sub_words("請多元長來", ["請多", "元長來"], ["多元長"]) == ["請多元長來"]    # 詞兩端不合的邊界詞整個併
    assert SEG.merge_sub_words("abc", ["a", "bc"], []) == ["a", "bc"]
    assert SEG.align_words("我 愛 你", ["我", "愛", "你"]) == ["我 ", "愛 ", "你"]
    assert SEG.align_words("我愛你", ["我", "恨", "你"]) is None


def test_seg_ckip_unavailable_falls_back():
    """ckip 載入失敗(沒裝/下載不到)-> 警告後退回 jieba,拆段結果與 jieba 相同。"""
    base = [t for t, _ in B.split_phrases(SEG_TEXT)]
    old = _with_seg("ckip", None)
    SEG._OBJS["ckip"] = None            # 模擬 _load_ckip 失敗
    try:
        assert SEG.segmenter().name == "jieba"
        assert [t for t, _ in B.split_phrases(SEG_TEXT)] == base
    finally:
        _restore_seg(old)


def test_seg_ckip_real():
    """真模型(CPU):本機裝了 ckip-transformers 且模型取得到才跑,否則 skip。"""
    try:
        import pytest
    except ImportError:             # 以腳本執行時沒有 pytest:直接略過
        print("略過 test_seg_ckip_real(無 pytest)")
        return
    pytest.importorskip("ckip_transformers")
    old = _with_seg("ckip", None)
    SEG._OBJS.pop("ckip", None)
    try:
        sg = SEG.segmenter("ckip")
        if sg.name != "ckip":
            pytest.skip("ckip 模型載入失敗(沒網路/沒快取)")
        t = "至於它後來怎麼從人事部門一路管到遊戲裡的角色"
        assert "".join(sg.cut(t)) == t
        assert B.sub_seams(t) == []
    finally:
        _restore_seg(old)



# ---- 片語切點評分(2026-10-29;seg.phrase_mode,有 build/<tag>/words.txt 才開)----
PHRASE_CASES = [  # (文字, 必須同段的片語, 不可當段尾的字串)
    ("因為 BioWare 早在《闇龍紀元:紗障守護者》那一年", ("闇龍紀元 紗障守護者",), ("早在", "因為")),    # 功能詞後
    ("BioWare 巔峰時期三間工作室超過 400 名員工", ("三間工作室", "400 名員工"), ()),                  # 數量詞組
    ("被裁的人裡有 50 個人後來告 BioWare 要求更多補償", ("50 個人",), ()),
    ("做異端審判的總監 Mike Laidlaw,2017 年就走了", ("Mike Laidlaw",), ()),                          # 英文全名
    ("加拿大新民主黨黨魁 Avi Lewis 甚至提議", ("Avi Lewis",), ()),
    ("會說該怪的是 EA,Kotaku 記者 Zack Zwiezen 就是這樣看", ("Kotaku 記者", "Zack Zwiezen"), ()),     # 英文單位 + 中文名詞
    ("他自己就跟一些立場完全相反的朋友一起做過遊戲", ("立場完全相反的朋友",), ()),                    # 的字結構內
]


def test_phrase_split():
    assert not SEG.phrase_mode()            # 預設關(沒有 words.txt 的片拆段不變)
    SEG.set_phrase(True)
    try:
        for text, keep, no_end in PHRASE_CASES:
            segs = [t for t, _ in B.split_phrases(text)]
            assert len(segs) > 1, segs
            for k in keep:
                assert any(k in t for t in segs), f"{k} 被拆開: {segs}"
            for e in no_end:
                assert not any(t.endswith(e) for t in segs[:-1]), f"切在「{e}」後: {segs}"
            assert all(B._dw(B.TOKEN_RE.findall(t)) <= B.SUB_MAX_W for t in segs), segs
        sc = B._phrase_score(B._strip(B.TOKEN_RE.findall("總監 Mike Laidlaw 說")))
        assert any(v == (B.PH_HARD, "英文名中間") for v in sc.values()), sc
    finally:
        SEG.set_phrase(False)

def test_no_stray_punct():
    """2026-11-05 性質測試反例:半形句點、【】〈〉、單引號原樣留在字幕(數字小數點與英數詞內的點照留)。"""
    for text, want in (("Hello. World is big.", ["Hello World is big"]), ("【公告】玩家〈回應〉", ["公告 玩家 回應"]),
                       ("這是 'quoted' 字", ["這是 quoted 字"]), ("U.S. 售價 3.5 倍", ["U.S 售價 3.5 倍"])):
        got = [t for t, _ in B.split_phrases(text)]
        assert got == want, (text, got)


def main():
    test_title_colon()
    test_relax_order()
    test_phrase_split()
    test_seg_default_is_jieba()
    test_seg_ckip_mock()
    test_seg_merge_and_align()
    test_seg_ckip_unavailable_falls_back()
    try:
        test_seg_ckip_real()
    except BaseException as e:      # noqa: BLE001  pytest 的 Skipped 是 BaseException:真模型不可用就略過
        if type(e).__name__ != "Skipped":
            raise
        print("略過 test_seg_ckip_real:", e)
    test_no_stray_punct()
    tag = sys.argv[1] if len(sys.argv) > 1 else "turtle"
    # 實例
    segs = [t for t, _ in B.split_phrases("在煙囪 120 公尺高的地方蓋了一間旋轉餐廳")]
    print("實例:", " / ".join(segs))
    for w in ("地方", "旋轉餐廳", "120 公尺"):
        assert any(w in s for s in segs), f"{w} 被拆開: {segs}"

    # 詞不可被拆開:jieba 詞典是簡體,繁體要先轉簡體再斷(人事部/門);自訂詞表 sub_words.txt(多元長)
    cases = [("至於它後來怎麼從人事部門一路管到遊戲裡的角色,那又是另一段故事。", ("人事部門", "部門")),
             ("這家公司去年才剛請了一位多元長專門負責這件事情的所有細節", ("多元長",)),
             ("才過幾個月,動視暴雪就承諾十年內要砸兩億五千萬美金,用在培養多元人才上。", ("十年內", "兩億五千萬美金"))]
    for text, words in cases:
        segs = [t for t, _ in B.split_phrases(text)]
        print("實例:", " / ".join(segs))
        assert len(segs) > 1, segs
        for w in words:
            assert any(w in s for s in segs), f"{w} 被拆開: {segs}"
        assert B.sub_seams(text) == [], B.sub_seams(text)
    toks = B.TOKEN_RE.findall("怎麼從人事部門一路管到遊戲裡的角色")
    why = B._cut_reasons(toks)
    assert "部門" in why[toks.index("門")] and "人事部門" in why[toks.index("部")], why   # 人事部|門、人事|部門 都不可切
    assert B._cross_word("人事部門", B._simp("人事部門"), 3) == "部門"                # 跨界字串(左1右1)是詞
    old = B._split_long                                                             # 掃描要抓得到舊切法的錯
    B._split_long = lambda t: [t[:t.index("門")], t[t.index("門"):]]
    try:
        bad = B.sub_seams("至於它後來怎麼從人事部門一路管到遊戲裡的角色")
    finally:
        B._split_long = old
    assert len(bad) == 1 and "部門" in bad[0][2], bad

    sj = ROOT / tag / "script.json"
    if not sj.is_file():  # 副本專案(KC)沒有這支片:只跑上面的單元測試
        print(f"略過實例測試:{sj} 不存在")
        return
    data = json.loads(sj.read_text(encoding="utf8"))
    lines = [l["text"] for s in data["sections"] for l in s["lines"]]
    diff, errs = [], 0
    for text in lines:
        new = run(B._split_long, text)
        old = run(B._split_long_greedy, text)
        got = [t for t, _ in new]
        if norm("".join(got)) != norm(text):
            errs += 1; print("內容不符:", text)
        if any(B._dw(B.TOKEN_RE.findall(t)) > B.SUB_MAX_W or not t for t in got):
            errs += 1; print("超寬/空段:", got)
        if [t for t, _ in old] != got:
            diff.append((text, [t for t, _ in old], got))
    seams = [(text, x) for text in lines for x in B.sub_seams(text)]
    print(f"句數 {len(lines)},切法不同 {len(diff)},錯誤 {errs},切開詞的接縫 {len(seams)}")
    assert not seams, seams[:5]
    for text, o, n in diff[:5]:
        print("  前:", " / ".join(o)); print("  後:", " / ".join(n)); print()
    assert errs == 0


if __name__ == "__main__":
    main()
