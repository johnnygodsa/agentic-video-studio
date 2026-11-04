"""spec_check 標題檢查:第 1 個標題三段以上(>=2 個空格)只 warn、不 error。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import spec_check as S  # noqa: E402


def _spec(first):
    titles = [{"text": first, "angle": "判"}] + [{"text": f"蝙蝠俠第{i}個標題大家都想看", "angle": a} for i, a in ((2, "數"), (3, "問"), (4, "反"), (5, "身"))]
    return {"channel": "ChannelA", "package": {"titles": titles, "thumbs": [], "subject": ["蝙蝠俠"]}}


def test_three_segment_title_warns_only():
    errs, warns = S.check_package(_spec("蝙蝠俠 我玩了3天 結果被騙"))
    assert any("三段以上標題平均扣 1.4–1.9 點" in w for w in warns)
    assert not any("三段以上" in e for e in errs)


def test_two_segment_title_no_warn():
    _, warns = S.check_package(_spec("蝙蝠俠 我玩了3天結果被騙"))
    assert not any("三段以上" in w for w in warns)
