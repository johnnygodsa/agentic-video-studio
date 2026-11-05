## What changed

## Why

## How I verified it
- [ ] `python -X utf8 pipeline/demo/run_demo.py --tts none --out demo_out` renders
- [ ] `python -X utf8 .github/run_ci_tests.py` passes
- [ ] New behaviour has a test (added to `.github/ci_tests.txt` if it runs offline)
- [ ] No secrets, absolute paths, voices or media added
