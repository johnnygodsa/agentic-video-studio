# AGENTS.md — for OpenAI Codex and other AGENTS.md-aware agents

This repository is driven by an LLM "lead" session plus role-specific sub-agents. It was first built on Claude Code, and the same rules apply to Codex.

## Where the rules are

- `CLAUDE.md`: the per-turn project rules and a routing table ("to do X, read section Y"). **Read it first; it applies to you too.**
- `channel/規則/0_流程.md` … `4_交付發片.md`: workflow, topic selection, scripting & fact gates, production/TTS/QA, delivery.
- `.claude/agents/<role>.md`: role prompts (researcher, script-writer, fact-check, editor-review, pron-review, …).
- `pipeline/README.md`: the entry point for code changes.

## Running the pipeline with Codex

The director calls every sub-agent through `pipeline/llm.py`. Switch the backend to Codex in either of two ways:

```bash
STUDIO_LLM=codex python -X utf8 pipeline/director.py run <tag> --from A --to D
```

or in `studio.json`:

```json
{ "llm": { "backend": "codex", "codex_models": { "opus": "<strong model>", "sonnet": "<default model>", "haiku": "<fast model>" } } }
```

- Each call runs `codex exec --sandbox read-only|workspace-write -o <file> -`, and the prompt is sent on stdin.
- The role prompt from `.claude/agents/<role>.md` is placed before the task, with its frontmatter stripped.
- If a role needs Write, Edit or Bash, the call gets the `workspace-write` sandbox. Every other role runs read-only.
- If you leave out `codex_models`, Codex uses your own default model.
- JSON answers are validated against the schema embedded in the prompt. To also pass `--output-schema`, set `"codex_output_schema": true`. This only works with strict schemas.

## Ground rules for agents

- Never start a stage before its gate passes (`pipeline/gates/`), and never weaken a gate to get a pass.
- Do not invent facts. Every claim in a script must trace back to the fact table (`facts.md`).
- Do not nest sub-agents.
- Offline checks to run before you finish: `python -X utf8 .github/run_ci_tests.py` and the demo (`pipeline/demo/run_demo.py`).
