#!/usr/bin/env python3
"""Run the CI test list (.github/ci_tests.txt) one file at a time.

Files containing pytest-style `def test_` functions run under pytest; the rest are
standalone scripts (exit code 0 = pass). Prints one line per file and a summary;
exit code is non-zero if any file fails.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "pipeline" / "tests"


def names():
    for raw in (ROOT / ".github" / "ci_tests.txt").read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            yield s


def run(name):
    f = TESTS / name
    pytest_style = re.search(r"^\s*def test_", f.read_text(encoding="utf-8"), re.M)
    cmd = ([sys.executable, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider", str(f)] if pytest_style
           else [sys.executable, "-X", "utf8", str(f)])
    t = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, time.time() - t, "pytest" if pytest_style else "script", p.stdout + p.stderr


def main():
    failed = []
    todo = list(names())
    for name in todo:
        rc, sec, kind, out = run(name)
        print(f"{'PASS' if rc == 0 else 'FAIL'} {kind:6s} {sec:5.1f}s {name}", flush=True)
        if rc != 0:
            failed.append(name)
            print("\n".join(out.strip().splitlines()[-40:]), flush=True)
    print(f"\n{len(todo) - len(failed)}/{len(todo)} passed")
    if failed:
        print("failed: " + ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
