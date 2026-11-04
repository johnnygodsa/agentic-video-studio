"""逗號連讀 comma_runon 的單元測試(假資料、不載模型,tts_env_chattts 跑):python -X utf8 -m pytest pipeline/tests/test_tts_comma_runon.py -q
1. 判定:原始靜音 < COMMA_RUNON_MIN 才算,頓號不算;後處理重量測沿用,插入靜音過不了關;舊紀錄用 pause_fix.before,都沒有不判。
2. 重錄迴圈:不因 comma_only 提早停、挑連讀少的、用完仍有 = 未過(計入 max_retry)。
3. 插入目標:cosy3 0.20、tts_chattts 維持 0.14;插到 0.20 不超過 COMMA_MAX。
4. 優先聽:靠插入補的逗號列「逗號靠插入」,頓號不列。"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import listen_page as LP  # noqa: E402
import tts_cosy3 as TCY  # noqa: E402
import tts_pause as TP  # noqa: E402

SR = 24000


def pause(at="市|匿", sil=0.0, dip=20.0, soft=False, i=0):
    return dict(i=i, at=at, est=1.0, t0=1.0, t1=1.0 + sil, sil=sil, dip=dip, soft=soft)


def test_runon_threshold_and_soft():
    ps = [pause("甲|乙", 0.0), pause("丙|丁", 0.049), pause("戊|己", TP.COMMA_RUNON_MIN), pause("庚|辛", 0.0, soft=True)]
    assert TP.comma_runon(ps) == [dict(at="甲|乙", before=0.0), dict(at="丙|丁", before=0.049)]
    assert TP.comma_runon(None) == []


def judged(pauses, **kw):
    m = dict(pauses=pauses, fails=[], score=0.0, **kw)
    TP.judge_runon(m)
    return m


def test_judge_survives_post_processing():
    m = judged([pause(sil=0.0)])
    assert m["fails"] == ["comma_runon"] and m["comma_runon"] == [dict(at="市|匿", before=0.0)]
    assert m["score"] == -TP.RUNON_PENALTY
    m2 = dict(m, pauses=[pause(sil=0.2)], fails=[], score=0.0)   # 同 remeasure:插入後重量測、check 重算 fails
    TP.judge_runon(m2)
    assert m2["fails"] == ["comma_runon"]


def test_judge_clean_and_cached_not_judged():
    assert judged([pause(sil=0.06)])["fails"] == []
    assert judged([pause(sil=0.0)], comma_runon=[])["fails"] == []   # verify 舊音檔無紀錄:from_cache 放 [],不判


def test_runon_from_rec():
    ps = [pause("甲|乙", 0.2), pause("丙|丁", 0.2, soft=True), pause("戊|己", 0.2)]
    fix = [dict(at="甲|乙", act="insert", before=0.0, after=0.2), dict(at="丙|丁", act="insert", before=0.0, after=0.2),
           dict(at="戊|己", act="insert", before=0.07, after=0.2)]
    assert TP.runon_from_rec(dict(pauses=ps, pause_fix=fix)) == [dict(at="甲|乙", before=0.0)]
    assert TP.runon_from_rec(dict(pauses=ps, pause_fix=fix, comma_runon=[])) == []
    assert TP.runon_from_rec(dict(pauses=[pause(sil=0.0)])) == []
    assert TP.runon_from_rec(None) == []


def attempts(*ms):
    """依序回傳假嘗試的 attempt(r);記呼叫次數。"""
    q = list(ms)

    def attempt(r):
        m = q.pop(0)
        return "w", m, not m["fails"]

    attempt.left = q
    return attempt


def mm(fails, score=-0.1, runon=0, sil=0.07):
    return dict(fails=list(fails), score=score, comma_runon=[dict(at="市|匿", before=0.0)] * runon,
                pauses=[pause(sil=sil)])


def start(m):
    return dict(w="w0", m=m, ok=not m["fails"], tries=[m])


def test_retry_not_stopped_and_exhausted_fails():
    first = mm(["comma_short", "comma_runon"], runon=1, sil=0.0)
    assert not TCY.TC.comma_only(first)
    r = start(first)
    TP.retry_best(r, attempts(*[mm(["comma_short", "comma_runon"], runon=1, sil=0.0) for _ in range(3)]), 3, TCY.stop_retry)
    assert len(r["tries"]) == 4 and r["ok"] is False and "comma_runon" in r["m"]["fails"]


def test_comma_only_still_stops_without_runon():
    r = start(mm(["comma_short"]))
    attempt = attempts(mm([]))
    TP.retry_best(r, attempt, 6, TCY.stop_retry)
    assert len(r["tries"]) == 1 and len(attempt.left) == 1   # 只差補得起來的停頓:行為不變,不換 seed


def test_retry_prefers_fewer_runon_then_stops():
    r = start(mm(["comma_runon"], score=-0.3, runon=2, sil=0.0))
    better = mm(["comma_short"], score=-0.9)                     # 分數較低但沒有連讀:換上,且 comma_only 為真、不再重錄
    TP.retry_best(r, attempts(better, mm([])), 6, TCY.stop_retry)
    assert r["m"] is better and len(r["tries"]) == 2 and r["ok"] is False


def test_retry_keeps_higher_score_when_runon_equal():
    best = mm(["comma_runon"], score=-0.3, runon=1, sil=0.0)
    r = start(best)
    TP.retry_best(r, attempts(mm(["comma_runon", "speaker"], score=-0.8, runon=1, sil=0.0)), 1, TCY.stop_retry)
    assert r["m"] is best


def test_retry_passes():
    r = start(mm(["comma_runon"], runon=1, sil=0.0))
    clean = mm([], score=0.0)
    TP.retry_best(r, attempts(clean), 6, TCY.stop_retry)
    assert r["ok"] is True and r["m"] is clean and len(r["tries"]) == 2


def test_insert_targets():
    assert TP.COMMA_TARGET == 0.20 <= TP.COMMA_MAX and TP.COMMA_TARGET_CHATTTS == 0.14
    w = np.ones(SR * 2, dtype=np.float32)
    p = [pause(sil=0.0)]
    cosy, _ = TP.fix_pauses(w, SR, p)
    chat, _ = TP.fix_pauses(w, SR, p, std_target=TP.COMMA_TARGET_CHATTTS)
    assert abs((len(cosy) - len(w)) / SR - 0.20) < 0.001 and abs((len(chat) - len(w)) / SR - 0.14) < 0.001
    long_text = "啊啊，啊啊，啊啊。"
    assert TP.comma_params(long_text, "long", 0.14)["COMMA_TARGET"] == 0.26   # long 側寫不動


def test_listen_reason():
    rec = dict(idx=15, text="甲乙。", passed=True, pauses=[pause("市|匿", 0.2), pause("丙|丁", 0.2, soft=True)],
               pause_fix=[dict(at="市|匿", act="insert", before=0.07, after=0.2), dict(at="丙|丁", act="insert", before=0.0, after=0.2)])
    assert LP.pick_reasons([rec])[15] == [("comma_insert", "逗號靠插入:市|匿")]
    assert LP.pick_reasons([dict(rec, pause_fix=[])]) == {}
