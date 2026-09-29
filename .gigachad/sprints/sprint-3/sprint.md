---
sprint: 3
name: v0.1.2 — fixes from gpt-6-astra review
status: complete
---

# Sprint 3: v0.1.2 — review fixes

## Context

A full-project review by codex `gpt-6-astra` (validated by Claude Sonnet) found 8 real bugs. Two groups:
- **US-R (I/O & adapters):** #0 claude read-only mode still has Bash/MCP; #1 blocking stdin write defeats timeout/cancel;
  #2 claude stderr merged into the JSON it parses; #7 relative `GIGACHAD_LITE_HOME` breaks codex `-o` path with `--cwd`.
- **US-L (job lifecycle races):** #3 early cancel overwritten by supervisor startup; #4 `get()` overwrites a just-finished
  job with a stale "supervisor died" record; #5 supervisor death leaves the worker running unkillable; #6 zombie supervisor
  looks alive so `wait()` can hang forever.

Principles unchanged: stdlib only, Python ≥ 3.9, POSIX, never coerce worker exit codes, execute-only.
Local CI only (`scripts/ci.sh`); do not add hosted CI.

## Task Index

| # | ID | Section | Depends On | Status | Description |
|---|-----|---------|-----------|--------|-------------|
| 1 | UT-R-1 | RED | — | complete | Tests: read-only claude, stdin, stderr split, absolute home |
| 2 | T-R-1 | GREEN | UT-R-1 | complete | Fix #0 #1 #2 #7 |
| 3 | UT-L-1 | RED | T-R-1 | complete | Tests: lifecycle races (#3 #4 #5 #6) |
| 4 | T-L-1 | GREEN | UT-L-1 | complete | Fix #3 #4 #5 #6 |
| 5 | T-V-1 | GREEN | T-L-1 | complete | Version 0.1.2 + CHANGELOG |
