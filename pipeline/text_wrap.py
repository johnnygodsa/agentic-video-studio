"""共用斷詞與換行點(閱讀卡、anim_web 各網頁模板共用):jieba + 專案詞表 pipeline/sub_words.txt。
- card_cut(text)  -> 詞清單(英數詞整段不拆;黏前字併入前詞)
- break_groups(text) -> 「換行時不可再切開」的字串清單(行首/行尾禁則、英數+單位已併入)
- wbr_html(text)  -> 跳脫後以 <wbr> 連接(閱讀卡用 innerHTML)
- zwsp(text)      -> 以 U+200B 連接(textContent 即可用;搭 CSS word-break:keep-all,中文只在詞邊界換行;canvas 量寬為 0)
"""
import re

_NO_BREAK_BEFORE = set("，。、：；！？」』）》〉】…—·%％,.:;!?)]}\"'’”")   # 行首禁則:這些字前面不插 <wbr>
_NO_BREAK_AFTER = set("「『（《〈【([{“‘")                                # 這些字後面不插 <wbr>
_UNIT_HEAD = set("個年月日號%％公萬億千百元美分秒時次名位種支款人場歲倍成度克斤磅")        # 數字/英文詞後接單位,不拆


_STICKY = set("的了著過們嗎呢吧啦")   # 不可當詞首的黏前字(同 build.py STICKY_HEAD)


def card_cut(text):
    """斷詞(同 build.py 作法,斷詞器共用 seg.py:預設 jieba〔詞典是簡體,先逐字轉簡體斷再切回原字〕,--seg ckip / CV_SEG=ckip 換 ckip;
    專案自訂詞表 sub_words.txt 兩邊都吃;英數詞整段不拆;黏前字併入前詞)"""
    import seg as SEG
    sg = SEG.segmenter()
    if not sg:
        raise RuntimeError("斷詞器不可用(jieba 沒裝?)")
    out = []
    for m in re.finditer(r"[A-Za-z0-9][A-Za-z0-9 ,.:%+/\-']*[A-Za-z0-9%]|[A-Za-z0-9]|\s+|[^\sA-Za-z0-9]+", text):
        seg = m.group(0)
        if re.match(r"[\sA-Za-z0-9]", seg):
            out.append(seg)
            continue
        for w in sg.cut(seg):
            if out and w[0] in _STICKY and not out[-1].isspace():
                out[-1] += w
            else:
                out.append(w)
    return out


ZWSP = "\u200B"


def break_groups(text):
    """在詞與詞之間可換行的切法:回傳不可再切開的字串清單(串起來 = 原文)。
    不在行首禁則字之前、開括號之後、英數詞與後接英數/連字號/單位之間切。"""
    toks = [t for t in card_cut(text) if t]
    out = []
    for i, t in enumerate(toks):
        if i and not _may_break(toks[i - 1], t):
            out[-1] += t
        else:
            out.append(t)
    return out


def _may_break(t, nx):
    if nx[0] in _NO_BREAK_BEFORE or t[-1] in _NO_BREAK_AFTER or t[-1] == "-" or t[-1].isspace() or nx[0].isspace():
        return False
    if t[-1].isascii() and t[-1].isalnum() and (nx[0].isascii() and (nx[0].isalnum() or nx[0] == "-") or nx[0] in _UNIT_HEAD):
        return False
    return True


def wbr_html(text):
    """跳脫後在詞與詞之間插 <wbr>(搭 CSS word-break:keep-all,中文換行切點只落在詞邊界)"""
    import html as H
    return "<wbr>".join(H.escape(g) for g in break_groups(text))


def zwsp(text):
    """詞與詞之間插 U+200B(給 textContent 用的換行點);已含 U+200B 的字串原樣回傳(避免重複注入)。"""
    if not isinstance(text, str) or not text or ZWSP in text:
        return text
    return ZWSP.join(break_groups(text))
