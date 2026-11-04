"""tts_terms 三類各一例(假 script.json 寫在 tmp\\test_tts_terms\\)。python -X utf8 pipeline/tests/test_tts_terms.py"""
import json
import subprocess
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))
import tts_terms as T  # noqa: E402

TMP = PIPE.parent / "tmp" / "test_tts_terms"


def mk(tag, lines):
    d = TMP / tag
    d.mkdir(parents=True, exist_ok=True)
    (d / "script.json").write_text(json.dumps({"title": tag, "sections": [{"name": "s", "lines": lines}]},
                                              ensure_ascii=False), encoding="utf-8")


def run(tag):
    return subprocess.run([sys.executable, "-X", "utf8", str(PIPE / "tts_terms.py"), tag, "--root", str(TMP)],
                          capture_output=True, text=True, encoding="utf-8")


def main():
    mk("t_all", [
        {"text": "EA 昨天宣布了。"},                                    # 1 已登錄唸法未套用
        {"text": "在 Steam 上賣得很好。"},                              # 2 直接唸英文
        {"text": "用 Creative Assembly 的引擎。"},                      # 3 未登錄
        {"text": "EA 宣布", "say": "伊誒宣布,Xbox 三六零也是。"},       # 4 已套用:不報(Xbox 三六零整段遮掉)
        {"text": "C.A. 很大,CAD 不是 CA。"},                           # 5 C.A. 已套用;CAD 未登錄;CA 未套用
        {"text": "Xbox 360 老了。"},                                    # 6 多字詞整詞命中
        {"text": "蚵仔麵線很好吃。"},                                    # 7 非拉丁條目未套用
    ])
    r = run("t_all")
    assert r.returncode == 1, r.stdout
    res = T.analyze(T.script_texts("t_all", TMP), T.load_terms())
    assert set(res["unapplied"]) == {"EA", "CA", "Xbox 360", "蚵仔麵線"}, res["unapplied"]
    assert res["unapplied"]["EA"]["lines"] == [1] and res["unapplied"]["CA"]["lines"] == [5]
    assert set(res["unregistered"]) == {"Creative Assembly", "CAD"}, res["unregistered"]
    assert res["unregistered"]["Creative Assembly"]["lines"] == [3]
    assert set(res["direct"]) == {"Steam"} and res["direct"]["Steam"]["lines"] == [2], res["direct"]
    out = T.report(res, 7)
    assert len(out) <= T.MAX_LINES and any("@say EA=伊誒" in l for l in out), out

    mk("t_ok", [{"text": "在 Steam 買 Xbox 三六零。"}, {"text": "EA", "say": "伊誒"}])
    r = run("t_ok")
    assert r.returncode == 0, r.stdout
    print("test_tts_terms OK")


if __name__ == "__main__":
    main()
