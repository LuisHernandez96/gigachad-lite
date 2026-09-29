---
sprint: 4
name: v0.1.3 — second astra review fixes
status: pending
---

# Sprint 4: v0.1.3 — second review fixes

## Context

A second codex `gpt-6-astra` review (validated by a read-only Claude Sonnet job run through gigachad-lite itself)
plus hands-on orchestrator testing found 7 real issues:

- **US-X (lifecycle robustness):**
  #0 orphan cleanup skips SIGKILL once the group leader exits; #1 supervisor_pid never persisted → wait hangs if the
  supervisor dies before claiming the job; #2 supervisor dies between result.json and meta.json → job stuck running;
  #3 exception after worker spawn leaves the worker running; #4 list/status crash on a job dir without meta.json.
- **US-Y (output contracts):** #8 `models` default detection scans all TOML tables and ignores single-quoted strings;
  #9 `run --json` / `wait --json` return raw job metadata while `result --json` returns result.json (missing duration_s,
  extras such as claude session_id/total_cost_usd, stderr_path).

Principles unchanged: stdlib only, Python ≥ 3.9, POSIX, never coerce worker exit codes, execute-only, local CI only
(`scripts/ci.sh`), all race tests bounded and deterministic (use test hooks, never hang the suite).

## Task Index

| # | ID | Section | Depends On | Status | Description |
|---|-----|---------|-----------|--------|-------------|
| 1 | UT-X-1 | RED | — | pending | Tests: lifecycle robustness #0–#4 |
| 2 | T-X-1 | GREEN | UT-X-1 | pending | Fix #0–#4 |
| 3 | UT-Y-1 | RED | T-X-1 | pending | Tests: models default + unified JSON result |
| 4 | T-Y-1 | GREEN | UT-Y-1 | pending | Fix #8 #9 + docs |
| 5 | T-V-2 | GREEN | T-Y-1 | pending | Version 0.1.3 + CHANGELOG |
