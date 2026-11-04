"""語速常數(單一出處):channel/規則/2_文案.md §2「字數換算」——約每分鐘 330 字(含停頓),8 分鐘約 2,600 字。

330 字/分 = 5.5 字/秒;這個數字已經把句間、段間停頓算進去,所以用它估秒數時不要再另加 pause
(`est_seconds(text, pause)` 的 pause 參數是給「確定要多留白」的呼叫者,預設 0)。
有 timeline 的片一律用實際秒,這裡只負責無 timeline 時的預估。
script_lint.py、script_structure.py、spec_check.py、style_metrics.py、visual_check.py 都 import 本檔(2026-10-27 統一)。
"""
import re

CHARS_PER_MIN = 330
CHARS_PER_SEC = 5.5   # = CHARS_PER_MIN / 60

_NON_CHAR = re.compile(r"[\W_]+")   # 標點、空白、符號(\W 在 Python 3 對 unicode 為非字詞字元;底線一併去掉)


def count_chars(text):
    """字數:不含標點與空白(同 script_lint.clen,另把底線也排除)。"""
    return len(_NON_CHAR.sub("", text or ""))


def est_seconds(text, pause=0.0):
    """預估唸完這段文字的秒數 = 字數 ÷ CHARS_PER_SEC + pause。"""
    return count_chars(text) / CHARS_PER_SEC + float(pause or 0.0)


def minutes(chars):
    """字數換算成分鐘(以 CHARS_PER_MIN)。"""
    return chars / CHARS_PER_MIN
