# Contributing

Thanks for your interest! Bug reports, new animation templates, themes, rule packs for other languages and TTS/ASR engine adapters are all welcome.

## Quick start for contributors

```bash
git clone https://github.com/johnnygodsa/agentic-video-studio
cd agentic-video-studio
pip install -r requirements-ci.txt
python -X utf8 pipeline/demo/run_demo.py --tts none --out demo_out   # should end with "[done]"
python -X utf8 .github/run_ci_tests.py                                # the offline test suite CI runs
```

No GPU, model or API key is needed for any of the above.

## Ground rules

- **Gates stay hard.** A change must not let a stage start before its gate passes. If you add a check, add it to the gate of the stage that produces the artifact (`pipeline/gates/`).
- **Tests come with code.** New behaviour gets a test in `pipeline/tests/` that runs offline. If it can run in CI, add the file name to `.github/ci_tests.txt`.
- **No absolute paths.** Resolve paths through `pipeline/paths.py`.
- **No secrets, voices or media in the repo.** Models, reference audio, fonts, footage and API keys stay outside version control.
- **Keep language-specific logic switchable.** Regional conventions belong behind `studio.json` (`pipeline/locale_cfg.py`); language-specific lint or pronunciation rules belong in rule files, not in the orchestration code.

## Good first contributions

- A new animation template in `pipeline/templates/anim/` (HTML + GSAP timeline, seek-deterministic; see `pipeline/ANIM_DESIGN.md`)
- A new demo theme (`pipeline/demo/run_demo.py --theme`)
- A rule pack and pronunciation lexicon for another language
- An adapter for another TTS engine (`pipeline/tts_dispatch.py`) or LLM CLI (`pipeline/llm.py`)
- Translating the rule files in `channel/規則/` or the agent prompts in `.claude/agents/`

## Pull requests

1. Open an issue first for anything larger than a bug fix, so we can agree on the approach.
2. Keep each PR to one topic.
3. Make sure the demo still renders and `.github/run_ci_tests.py` passes.
4. Describe what changed and how you verified it (the PR template asks for this).

## Code style

Python 3.10+, standard library first. `ruff check --select F,E9` should be clean on files you touch. Comments in English or Chinese are both fine.

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
