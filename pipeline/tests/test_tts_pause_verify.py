"""句中停頓「插入位置驗證」的單元測試(不需顯示卡、不載辨識器;假辨識結果):python -X utf8 pipeline\\tests\\test_tts_pause_verify.py
1. head_match:插入點前段辨識的結尾對不對得到停頓標點前的字(中文、同音字、英文詞與音譯)。
2. insert_mids:fix_pauses 的紀錄換算插入靜音在新波形的中點(前面有剪短/插入的位移)。
3. inserted_ats:舊品管紀錄裡插過靜音的位置(verify=true 重驗用;沒插過的不驗)。"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import tts_pause as TP  # noqa: E402

SR = 24000
FAILS = []
# 假拼音鍵(測試環境沒有 pypinyin):只列測到的同音字,其餘用字本身
_PY = {"门": "men", "们": "men", "關": "guan", "关": "guan", "門": "men"}


def key(u):
    return u.lower() if u.isascii() else _PY.get(u, u)


def expect(name, cond, detail=""):
    print(("通過" if cond else "失敗"), name, detail)
    if not cond:
        FAILS.append(name)


def hu(hyp):
    """辨識文字 -> 單位字串(同 tts_cosy3.verify_inserts)。"""
    return [u for u, _, _ in TP.hyp_units([(hyp, 0.0, 1.0)])]


def ref_upto(text, at_unit):
    """原文從句首到第 at_unit 個單位(含)。"""
    return [u[0] for u in TP.units(text)][: at_unit + 1]


def test_head_match():
    text = "十月二十一号，做出质量效应的BioWare宣布关门，下一代质量效应也跟着喊停。"
    us = [u[0] for u in TP.units(text)]
    i = us.index("门")
    ref = ref_upto(text, i)
    # bioware_dei 001 實例:靜音插在 布|关(前段結尾「宣布」)= 插錯;插在 门|下(結尾「关门」)= 對
    expect("中文:結尾對到", TP.head_match(ref, hu("的百奥瓦宣布关门"), key) is True)
    expect("中文:插錯位置(宣布)", TP.head_match(ref, hu("的百奥瓦宣布"), key) is False)
    expect("中文:插太後面(门下)", TP.head_match(ref, hu("宣布关门下"), key) is False)
    expect("中文:同音字容忍", TP.head_match(ref, hu("宣布关们"), key) is True)
    expect("中文:繁體辨識也算", TP.head_match(ref, hu("宣布關門"), key) is True)
    expect("辨識空白:判斷不了", TP.head_match(ref, [], key) is None)
    expect("原文空白:判斷不了", TP.head_match([], hu("关门"), key) is None)

    t2 = "做出质量效应的BioWare，宣布关门。"
    r2 = ref_upto(t2, [u[0] for u in TP.units(t2)].index("BioWare"))
    expect("英文:辨識寫英文", TP.head_match(r2, hu("质量效应的Bioware"), key) is True)
    expect("英文:別名換回後", TP.head_match(r2, hu("的BioWare"), key) is True)
    expect("英文:音譯份量相當", TP.head_match(r2, hu("质量效应的百奥瓦"), key) is True)
    expect("英文:插在英文前(結尾「的」)", TP.head_match(r2, hu("质量效应的"), key) is False)
    expect("英文:音譯過長(多唸到下一句)", TP.head_match(r2, hu("的百奥瓦宣布关门"), key) is False)
    expect("英文:前一個中文字找不到 -> 判斷不了", TP.head_match(r2, hu("百奥瓦"), key) is None)

    t3 = "Final Fantasy，回來了。"
    r3 = ref_upto(t3, 1)
    expect("整段英文:對到", TP.head_match(r3, hu("final fantasy"), key) is True)
    expect("整段英文:對不上 -> 判斷不了", TP.head_match(r3, hu("翻到饭"), key) is None)
    expect("預設鍵:字元相同", TP.head_match(list("关门"), list("宣布关门")) is True)


def test_insert_mids():
    tone = lambda s: (0.5 * np.sin(2 * np.pi * 180 * np.arange(int(s * SR)) / SR)).astype(np.float32)  # noqa: E731
    zero = lambda s: np.zeros(int(s * SR), dtype=np.float32)  # noqa: E731
    w = np.concatenate([tone(0.5), zero(0.40), tone(0.5), zero(0.03), tone(0.5), zero(0.2)])
    ps = [dict(i=0, at="a|b", t0=0.5, t1=0.9, sil=0.40, dip=40.0),    # 太長 -> 剪短(在插入點之前,位移為負)
          dict(i=1, at="c|d", t0=1.4, t1=1.43, sil=0.03, dip=40.0)]   # 太短 -> 插入
    edits = []
    w2, acts = TP.fix_pauses(w, SR, ps, edits=edits)
    mids = TP.insert_mids(edits, SR)
    expect("紀錄:兩筆動作", acts == {0: "trim", 1: "insert"} and len(edits) == 2, str(edits))
    t = mids.get(1)
    run = (lambda k: (k, k))(int(t * SR)) if t else (0, 0)
    a, b = run
    while a > 0 and w2[a - 1] == 0:
        a -= 1
    while b < len(w2) and w2[b] == 0:
        b += 1
    expect("中點落在插入的靜音中央", t is not None and w2[int(t * SR)] == 0 and abs((a + b) / 2 / SR - t) < 0.01
           and abs((b - a) / SR - TP.COMMA_TARGET) < 0.03, f"t={t} run={a / SR:.3f}-{b / SR:.3f}")
    expect("只有插入算中點", set(mids) == {1})
    w3, _ = TP.fix_pauses(w, SR, ps)
    expect("edits 不給時行為不變", np.array_equal(w2, w3))


def test_inserted_ats():
    rec = dict(pause_fix=[dict(at="号|做", act="trim"), dict(at="门|下", act="insert")],
               pause_verify=[dict(at="说|这", ok=True)])
    expect("舊紀錄:插入 + 驗證過的位置", TP.inserted_ats(rec) == {"门|下", "说|这"})
    expect("沒插過:不驗", TP.inserted_ats(dict(pause_fix=[dict(at="号|做", act="trim")])) == set())
    expect("沒有紀錄", TP.inserted_ats(None) == set() and TP.load_qc(ROOT / "tmp" / "_no_such.qc.json") is None)


if __name__ == "__main__":
    test_head_match()
    test_insert_mids()
    test_inserted_ats()
    print("全部通過" if not FAILS else f"失敗 {len(FAILS)}: {FAILS}")
    sys.exit(1 if FAILS else 0)
