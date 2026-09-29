# Changelog

## 0.1.4

- The delegate skill documents `--prompt` / `--prompt-file -` for hosts that cannot write files (found by plugin smoke test).

## 0.1.3

Fixes found by a second gpt-6-astra review and hands-on orchestrator testing.

- Orphan cleanup escalates to SIGKILL group-wide, so no descendants survive once the group leader exits.
- The supervisor pid is persisted at start, so `wait()` no longer hangs if the supervisor dies before claiming the job.
- Reconciliation recovers a finished job from `result.json` when the supervisor died before updating `meta.json`.
- The worker is cleaned up if the supervisor errors after spawning it.
- `list`/`status` skip incomplete job dirs (no `meta.json`) instead of crashing.
- `models` reads only the root `model` key of the TOML config (single or double quotes).
- `run`/`wait`/`result --json` share one schema, including `duration_s`, `extras`, and `stderr_path`.

## 0.1.2

Fixes found by a gpt-6-astra review.

- Read-only Claude workers are limited to Read/Glob/Grep, without MCP.
- The prompt is delivered via a file handle, so a blocking stdin write can no longer defeat timeout/cancel.
- Claude stderr is kept out of result parsing; it goes to `stderr.log` and is shown by `gcl logs`.
- The job-store home is now absolute, fixing the codex `-o` path with `--cwd`.
- An early cancel is honored instead of being overwritten by supervisor startup.
- Reconciliation never overwrites a finished job with a stale "supervisor died" record.
- Orphaned workers are killed when the supervisor dies (`killed_by: supervisor_died`).
- Zombie supervisors are detected, so `wait()` no longer hangs forever.

## 0.1.1

- Jobs now record `depth` in `meta.json`.
- Jobs killed on timeout/cancel are attributed via `killed_by`/`signal`; the text result says `killed by <reason> via <signal>`.
- Malformed depth env vars warn instead of crashing.
- Added a local CI script, `scripts/ci.sh`.
- Added CODEOWNERS and CONTRIBUTING.
- No hosted CI.

## 0.1.0

- Initial release: execute-only delegation CLI, codex/claude adapters, job store + supervisor, Claude Code and Codex plugins.
