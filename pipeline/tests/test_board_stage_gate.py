"""board.set_stage 前置條件(已凍結 -> gate_c、已排程 -> gate_e):假 gates 模組,寫到 tmp\test_board_stage_gate\。
python -X utf8 pipeline/tests/test_board_stage_gate.py 或 pytest。"""
import json
import os
import shutil
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import board  # noqa: E402
import paths as P  # noqa: E402

BASE = P.TMP / "test_board_stage_gate"


class Env:
    """CV_BOARD_DIR 指到暫存、gates.gate_c/gate_e 換成假模組、latest_ver 固定。"""

    def __init__(self, c_items=(), e_items=(), ver="v1"):
        self.c_items, self.e_items, self.ver = list(c_items), list(e_items), ver
        self.calls = []

    def __enter__(self):
        shutil.rmtree(BASE, ignore_errors=True)
        BASE.mkdir(parents=True)
        self.old_env = os.environ.get("CV_BOARD_DIR")
        os.environ["CV_BOARD_DIR"] = str(BASE)
        self.old_mods = {k: sys.modules.get(k) for k in ("gates", "gates.gate_c", "gates.gate_e")}
        pkg = types.ModuleType("gates")
        pkg.__path__ = []
        gc, ge = types.ModuleType("gates.gate_c"), types.ModuleType("gates.gate_e")
        gc.run = lambda tag, ver, ctx=None: self.calls.append(("c", tag, ver)) or self.c_items
        ge.run = lambda tag, ver, ctx=None: self.calls.append(("e", tag, ver)) or self.e_items
        sys.modules.update({"gates": pkg, "gates.gate_c": gc, "gates.gate_e": ge})
        self.old_lv, board.latest_ver = board.latest_ver, (lambda tag: self.ver)
        return self

    def __exit__(self, *exc):
        board.latest_ver = self.old_lv
        for k, v in self.old_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        if self.old_env is None:
            os.environ.pop("CV_BOARD_DIR", None)
        else:
            os.environ["CV_BOARD_DIR"] = self.old_env
        shutil.rmtree(BASE, ignore_errors=True)


def item(iid, ok, note=""):
    return {"id": iid, "ok": ok, "note": note, "path": None}


def refused(fn):
    try:
        fn()
    except SystemExit as e:
        return e.code
    return None


def test_frozen_needs_gate_c():
    with Env(c_items=[item("C0試配", True), item("listen", False, "listen_v1.txt 沒有")]) as env:
        assert refused(lambda: board.set_stage("t", "已凍結")) == 2
        assert board.get("t") is None                      # 沒寫進去
        assert env.calls == [("c", "t", "v1")]
        board.set_stage("t", "已凍結", force=True)          # --force 繞過
        assert board.get("t")["stage"] == "已凍結"
    with Env(c_items=[item("C0試配", True), item("freeze", True)]) as env:
        assert board.set_stage("t2", "已凍結")["stage"] == "已凍結"


def test_scheduled_needs_gate_e_but_not_self_item():
    ok_but_self = [item("發片資料", True), item("sidecar", True), item("已排程", False, "board 階段 E自審")]
    with Env(e_items=ok_but_self):
        assert board.set_stage("t", "已排程")["stage"] == "已排程"   # 「已排程」項本身不算
    with Env(e_items=[item("發片資料", False, "(待填) 2 處"), item("已排程", False)]):
        assert refused(lambda: board.set_stage("t", "已排程")) == 2


def test_other_stages_and_no_ver_skip_gates():
    with Env(c_items=[item("x", False)]) as env:
        board.set_stage("t", "D畫面")
        board.set_stage("t", "E自審")
        assert env.calls == []
    with Env(c_items=[item("x", False)], ver=None) as env:   # 找不到版本 = 略過(印警告)
        assert board.set_stage("t", "已凍結")["stage"] == "已凍結" and env.calls == []


def test_update_other_fields_unaffected():
    with Env(c_items=[item("x", False)]) as env:
        board.update("t", next="x", blocked="y")
        assert env.calls == [] and json.loads((BASE / "board.json").read_text(encoding="utf-8"))["t"]["next"] == "x"


TESTS = [test_frozen_needs_gate_c, test_scheduled_needs_gate_e_but_not_self_item, test_other_stages_and_no_ver_skip_gates,
         test_update_other_fields_unaffected]

if __name__ == "__main__":
    bad = 0
    for fn in TESTS:
        try:
            fn()
            print("OK  ", fn.__name__)
        except Exception as e:  # noqa: BLE001
            bad += 1
            print("FAIL", fn.__name__, type(e).__name__, e)
    sys.exit(1 if bad else 0)
