---
sprint: 5
name: v0.1.4 — skill works under restricted permissions
status: complete
---

# Sprint 5: v0.1.4

## Context

Plugin smoke test: a Claude Code session with restricted permissions (Bash limited to `gcl`, no Write tool) could not
create a prompt file, so it fell back to `--prompt` on its own. The skill only documents `--prompt-file`. Document all
three prompt-delivery options so orchestrators pick the right one without trial and error.

## Task Index

| # | ID | Section | Depends On | Status | Description |
|---|-----|---------|-----------|--------|-------------|
| 1 | T-K-1 | GREEN | — | complete | Skill: prompt delivery options + version 0.1.4 |
