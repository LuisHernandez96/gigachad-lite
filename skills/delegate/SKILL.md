---
name: delegate
description: Delegate a coding task to another AI agent (Claude via claude CLI, or OpenAI/Codex models via codex CLI) as a tracked background job with gigachad-lite. Use when the user asks to delegate, hand off, or get a second model to implement or review something.
---

# Delegate work with gigachad-lite

gigachad-lite is execute-only: it runs a prompt on a worker agent as a background job and returns the worker's final message and exit status. You (the orchestrator) own planning, verification, tests, review and git. The worker does none of that for you.

## 1. Setup

Find the CLI, in this order:

1. `gcl` on PATH.
2. `<directory containing this SKILL.md>/../../bin/gcl`.
3. Install it: `python3 -m pip install --user git+https://github.com/LuisHernandez96/gigachad-lite`

## 2. Pick a worker

Run `gcl models --json`. If the user hasn't named a worker, ask them, offering a Claude model and a codex model; delegating across vendors is the point. The agent is `claude` for Claude models and `codex` for codex models.

## 3. Write a self-contained prompt file

The worker has none of your context. Include the goal, the relevant files, constraints, the definition of done, "do not commit", and "finish with a short summary of what you changed".

## 4. Start the job

```
gcl start --agent <a> --model <m> --prompt-file <f> --json
```

Add `--mode read-only` for reviews and second opinions, and `--timeout <seconds>` for long tasks. Record the job id.

## 5. Monitor

Run `gcl wait <id> --json` in your host's background or long-running command facility, or poll `gcl status <id>` periodically. Keep the user updated (state, elapsed time). Use `gcl logs <id> --tail 50` to peek and `gcl cancel <id>` to stop.

## 6. Finish

Run `gcl result <id> --json`, then VERIFY yourself before telling the user it is done: check `git diff` and run the tests and linters. If the job failed or the result is wrong, refine the prompt and start a new job rather than hand-editing silently.

## Rules

- **Parallelism:** independent jobs may run concurrently in different directories or worktrees; never run two writers in the same tree.
- **Recursion:** workers cannot delegate further (depth guard). `GIGACHAD_LITE_MAX_DEPTH` raises the limit.

## Exit codes (`gcl run` / `gcl wait` / `gcl result`)

| Code | Meaning |
|------|---------|
| 0 | job succeeded |
| 1 | job failed (worker's own exit status is in the result) |
| 2 | usage error |
| 3 | job not finished yet (`wait --timeout` elapsed, or `result` on a running job) |
| 124 | job timed out |
| 130 | job cancelled |
