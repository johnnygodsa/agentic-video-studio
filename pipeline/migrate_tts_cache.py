"""把舊版 <素材根>/build/<old>/tts 的配音快取依「朗讀文字(say 或 text)」對應到新腳本的句編號,複製到 build/<new>/tts。
python pipeline/migrate_tts_cache.py <old_tag> <new_tag> [--script <新腳本,預設 <new_tag>/script.json>] [--force 子字串 ...]
含 --force 子字串的句子不複製(讓 build.py 重新合成)。.key 內容是不含路徑的快取鍵(見 tts_key.py),
參數不變時可直接沿用;對不上的 build.py 會自動重錄。(--force 必須放在最後)
"""
import json
import shutil
import sys
from pathlib import Path

import paths as P


def main():
    old, new = sys.argv[1], sys.argv[2]
    force = sys.argv[sys.argv.index("--force") + 1:] if "--force" in sys.argv else []
    script = sys.argv[sys.argv.index("--script") + 1] if "--script" in sys.argv else str(Path(new) / "script.json")
    tl = json.loads((P.build_dir(old) / "timeline.json").read_text(encoding="utf-8"))
    by_say = {}
    for ln in tl["lines"]:
        by_say.setdefault(ln.get("say") or ln["text"], ln["idx"])
    data = json.loads(P.find(script, P.REPO).read_text(encoding="utf-8"))
    dst = P.build_dir(new) / "tts"
    dst.mkdir(parents=True, exist_ok=True)
    idx = copied = forced = 0
    for sec in data["sections"]:
        for ln in sec["lines"]:
            idx += 1
            say = ln.get("say") or ln["text"]
            if any(f in ln["text"] for f in force):
                forced += 1
                continue
            o = by_say.get(say)
            if o is None:
                continue
            for suf in (".wav", ".key", ".qc.json", ".trim.wav", ".trim.key"):
                s = P.build_dir(old) / "tts" / f"{o:03d}{suf}"
                if s.exists():
                    shutil.copy2(s, dst / f"{idx:03d}{suf}")
            copied += 1
    print(f"複製 {copied} 句;強制重錄 {forced} 句;其餘 {idx - copied - forced} 句文字/say 有變,build 時自動重錄")


if __name__ == "__main__":
    main()
