"""re9_notes 說明檔承接上一版(署名 + 發片資料):python -X utf8 pipeline\tests\test_notes_carry.py"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import re9_notes as N  # noqa: E402
import deliver as D  # noqa: E402

TMP = ROOT / "tmp" / "test_notes_carry"
DS = "【YouTube章節摘要】\n00:00 開場\n01:23 重點\n【影片標題】\n標題一\n【輸出完畢】"
CREDIT = '"Wallpaper" Kevin MacLeod (incompetech.com)'
V1 = f"# t v1\n\n## 配音品管\n舊品管\n\n## 說明欄署名\n```text\n{CREDIT}\n```\n\n## 發片資料\n```text\n{DS}\n```\n"
FAILS = []


def expect(name, cond, detail=""):
    print(("通過" if cond else "失敗"), name, detail)
    if not cond:
        FAILS.append(name)


def main():
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    out = TMP / "v3_說明.md"
    c, p, n = N.carry_sections(out, "v3")
    expect("沒有上一版 -> 不承接", (c, p, n) == (None, None, None))
    (TMP / "v1_說明.md").write_text(V1, encoding="utf-8")
    (TMP / "v4_說明.md").write_text("# 更新的版本不可取\n", encoding="utf-8")
    c, p, n = N.carry_sections(out, "v3")
    expect("取最新的更早版本(v1)", n == 1 and CREDIT in c and "舊品管" not in c + p)
    expect("註解在 ```text 之前", p.index("<!-- 承接 v1,章節時間請對 timeline_tts.json 重算 -->") < p.index("```text"), p[:80])
    md = "# new\n\n## 配音品管\n新品管\n\n" + c + "\n\n" + p + "\n"
    ds, ex = D.parse_notes(md)
    expect("承接後 deliver 可解析", ds == DS and ex == CREDIT, repr(ds)[:30])
    (TMP / "v3_說明.md").write_text(md, encoding="utf-8")
    c2, p2, n2 = N.carry_sections(TMP / "v5_說明.md", "v5")
    expect("承接 v4 缺段 -> 該段 None", n2 == 4 and c2 is None and p2 is None)
    (TMP / "v4_說明.md").unlink()
    c3, p3, n3 = N.carry_sections(TMP / "v5_說明.md", "v5")
    expect("再承接不疊註解", n3 == 3 and p3.count("<!-- 承接") == 1 and "承接 v3" in p3 and "承接 v1" not in p3)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n失敗 {len(FAILS)} 項" if FAILS else "\n全部通過")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
