"""script_lint.check_sentences 句級子集測試:python -X utf8 -m pytest pipeline/tests/test_lint_sentences.py -q"""
import subprocess
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
import paths as P  # noqa: E402
import script_lint as L  # noqa: E402

SCRIPT = (
    "@title T\n# 一\n"
    "a|這個遊戲做得很好,玩家都很喜歡。\n"              # L3 乾淨
    "b|那個角色耶,真的很強。\n"                        # L4 BAD_PARTICLE(block)
    "c|這一條說法站不住腳,因為資料對不上。\n"          # L5 VERDICT(block)
    "d|隨著時代發展,遊戲產業也在改變。\n"              # L6 CLICHE
    "e|這個人先做了一件事,後來又做了另一件,然後是第三件,接著還有第四件,最後還有第五件事。\n"   # L7 PRONOUN + CLAUSES
    "\n@say x=y\n"
    "f|不是靠運氣,是靠準備。 ;; {\"hl\": [\"準備\"]}\n"   # L10 NOT_BUT
)


def mk(tmp_path, monkeypatch, body=SCRIPT):
    monkeypatch.setattr(P, "ROOT", tmp_path)
    (tmp_path / "t").mkdir(exist_ok=True)
    (tmp_path / "t" / "script.txt").write_text(body, encoding="utf-8")


def by_line(r):
    out = {}
    for x in r:
        out.setdefault(x["line"], []).append(x)
    return out


def test_shape_and_codes(tmp_path, monkeypatch):
    mk(tmp_path, monkeypatch)
    r = by_line(L.check_sentences("t"))
    assert 3 not in r
    assert {(x["code"], x["block"]) for x in r[4]} == {("BAD_PARTICLE", True)}
    assert ("VERDICT", True) in {(x["code"], x["block"]) for x in r[5]}
    assert {x["code"] for x in r[6]} == {"CLICHE"}
    assert {"PRONOUN", "CLAUSES"} <= {x["code"] for x in r[7]}
    assert "NOT_BUT" in {x["code"] for x in r[10]}
    assert all(set(x) == {"line", "code", "block", "why"} for v in r.values() for x in v)


def test_line_nos_filter(tmp_path, monkeypatch):
    mk(tmp_path, monkeypatch)
    r = L.check_sentences("t", [4, 6])
    assert sorted({x["line"] for x in r}) == [4, 6]
    assert L.check_sentences("t", [3]) == []
    assert L.check_sentences("t", []) == []


def test_neighbor_checks_use_full_script(tmp_path, monkeypatch):
    mk(tmp_path, monkeypatch, "# 一\na|這裡根本不是故障\nb|是刻意設計好的樣子。\n")
    assert [x["code"] for x in L.check_sentences("t", [2])] == ["NOT_BUT"]   # 只問第 2 行,下一行仍讀得到
    mk(tmp_path, monkeypatch, "# 一\na|一邊說他很認真地做\nb|另一邊說他很認真地做。\n")
    assert "PARALLEL" in [x["code"] for x in L.check_sentences("t", [2])]


def test_sentence_hits_pure_function():
    h = L.sentence_hits(1, "這件事說不過去。")
    assert any(x["code"] == "VERDICT" and x["block"] for x in h)
    assert L.sentence_hits(1, "遊戲做得很用心,玩家也買單。") == []


def test_cli_exit_code_unchanged(tmp_path):
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "script.txt").write_text("# 一\na|那個角色耶,真的很強。\n", encoding="utf-8")
    import os
    env = dict(os.environ, CLAUDE_VIDEO_ROOT=str(tmp_path))
    r = subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "script_lint.py"), "t"], capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 1 and "超標 1 項" in r.stdout   # 配音唸不出的語助詞 = 1 -> 超標,舊行為不變
