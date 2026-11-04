#!/usr/bin/env python3
r"""啟動器:用配音環境的 python(paths.TTS_ENV)執行 pipeline 內的腳本,任何工作目錄、任何 shell 都能下同一行指令。

python pipeline/run.py build --script re9/script.json --tag re9 ...     # = <TTS_ENV> -X utf8 pipeline/build.py ...
python pipeline/run.py re9_notes ...   /   qa_sheet ...   /   assets_re9_clips --check
本身只用標準函式庫,系統的 python 即可執行;子行程的工作目錄固定為 repo 根、輸出固定 UTF-8。
"""
import os
import subprocess
import sys
from pathlib import Path

import paths as P


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python pipeline/run.py <腳本名(不含 .py)> [參數...]")
    script = Path(__file__).resolve().parent / (sys.argv[1].removesuffix(".py") + ".py")
    if not script.exists():
        sys.exit(f"沒有這個腳本: {script}")
    if not P.TTS_ENV.exists():
        sys.exit(f"找不到配音環境的 python: {P.TTS_ENV}(素材根 {P.ROOT};可用環境變數 CLAUDE_VIDEO_ROOT 指定)")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    sys.exit(subprocess.run([str(P.TTS_ENV), "-X", "utf8", str(script)] + sys.argv[2:], cwd=P.REPO, env=env).returncode)


if __name__ == "__main__":
    main()
