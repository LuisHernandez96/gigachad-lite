---
sprint: 2
name: v0.1.1 — honest job records + CI and contributor policy
status: complete
---

# Sprint 2: v0.1.1

## Context

Live checks of v0.1 found two recorded-data bugs, and the public repo has no CI. This sprint fixes both
bugs and adds a local CI script + contributor policy files (no hosted CI: GitHub Actions is disabled).

1. `depth` is never recorded on jobs (meta.json shows `None`).
2. A job killed on timeout/cancel reports `exit 0` (codex exits 0 on SIGTERM), which reads as success-ish.

Principles (unchanged from Sprint 1): stdlib only, Python ≥ 3.9, never coerce worker exit codes, execute-only scope.

## Task Index

| # | ID | Section | Depends On | Status | Description |
|---|-----|---------|-----------|--------|-------------|
| 1 | UT-F-1 | RED | — | pending | Tests: depth recording + kill attribution |
| 2 | T-F-1 | GREEN | UT-F-1 | pending | Record depth; record killed_by/signal |
| 3 | T-G-1 | GREEN | T-F-1 | pending | Local CI script, CODEOWNERS, CONTRIBUTING |
