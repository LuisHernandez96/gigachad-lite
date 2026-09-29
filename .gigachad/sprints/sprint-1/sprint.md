---
sprint: 1
name: gigachad-lite v0.1 — execute-only delegation CLI
status: complete
---

# Sprint 1: gigachad-lite v0.1

## Context

gigachad-lite is a tiny, **execute-only** tool. An orchestrating agent (Claude Code or Codex) hands a
worker agent (Claude via `claude` CLI, or OpenAI models via `codex` CLI) a prompt. gigachad-lite runs it as a
background job, tracks it, and returns the worker's final message and exit status. It does NOTHING else: no
planning, task files, tests, lint, review, validation, git or commits — the orchestrator owns all of that.

It works in both directions: Claude Code → codex workers, and Codex → claude workers. It ships as a
Python package (stdlib only, Python ≥ 3.9) plus a Claude Code plugin and a Codex plugin sharing one skill.

### Hard-won lessons (MUST follow)
1. **codex echoes the prompt** into its output streams. Never scan the stream for markers. The worker's final answer
   comes ONLY from the file passed via `codex exec -o <file>`.
2. **Never coerce exit codes.** Report the worker's real exit code.
3. Nested `claude` refuses to start when `CLAUDECODE` is set — remove it from the child env.
4. Children get `GIGACHAD_AGENT_CHILD=1` (disables orchestrator hooks of installed plugins) and
   `GIGACHAD_LITE_DEPTH=<parent depth + 1>` (recursion guard).
5. Workers run in their own process group so timeout/cancel can kill the whole tree.

### Package layout (target)
```
src/gigachad_lite/__init__.py      # __version__ = "0.1.0"
src/gigachad_lite/__main__.py      # python -m gigachad_lite → cli.main()
src/gigachad_lite/adapters/base.py, codex.py, claude.py, __init__.py (get_adapter)
src/gigachad_lite/jobs.py          # JobStore, job lifecycle, cancel, status reconciliation
src/gigachad_lite/supervise.py     # detached supervisor process: python -m gigachad_lite.supervise <job_dir>
src/gigachad_lite/models.py        # list_models()
src/gigachad_lite/cli.py           # argparse CLI: start run status wait result logs cancel list models
tests/fakes/codex, tests/fakes/claude   # fake agent executables used by tests
```

### Environment variables
- `GIGACHAD_LITE_HOME` — job store root (default `~/.local/state/gigachad-lite`); jobs live in `<home>/jobs/<id>/`.
- `GIGACHAD_LITE_DEPTH` — current delegation depth (unset = 0). `GIGACHAD_LITE_MAX_DEPTH` — default 1.

### Reference implementation (read-only, other repo)
- `/home/luis/Documents/GigachadDev/src/gigachad/agents/codex.py` — codex command/-o handling (port the ideas, not the Gigachad marker logic)
- `/home/luis/Documents/GigachadDev/src/gigachad/agents/claude.py` — claude command + CLAUDECODE stripping
- `/home/luis/Documents/GigachadDev/src/gigachad/core/models.py` — model listing to port
- `/home/luis/Documents/GigachadDev/plugin/skills/delegate/SKILL.md` — style reference for the skill

## Task Index

| # | ID | Section | Depends On | Status | Description |
|---|-----|---------|-----------|--------|-------------|
| 1 | T-S-1 | GREEN | — | complete | Project scaffold |
| 2 | UT-B-1 | RED | T-S-1 | complete | Fake agents + adapter tests |
| 3 | T-B-1 | GREEN | UT-B-1 | complete | Codex and Claude adapters |
| 4 | UT-A-1 | RED | T-B-1 | complete | Job store + supervisor tests |
| 5 | T-A-1 | GREEN | UT-A-1 | complete | Job store + supervisor |
| 6 | UT-C-1 | RED | T-A-1 | complete | CLI tests |
| 7 | T-C-1 | GREEN | UT-C-1 | complete | CLI |
| 8 | T-D-1 | GREEN | T-C-1 | complete | models command |
| 9 | T-E-1 | GREEN | T-D-1 | complete | Plugins, bin wrapper, shared skill |
| 10 | T-E-2 | GREEN | T-E-1 | complete | README |
| 11 | IT-1 | INTEGRATION | T-E-2 | complete | End-to-end with fake agents |
