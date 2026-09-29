---
sprint: 6
name: v0.1.5 — skill triggers on model names
status: complete
---

# Sprint 6: v0.1.5

## Context

A user asked a Claude Code session "can you delegate work to an astra agent?". The session only saw the skill's
one-line description ("…OpenAI/Codex models via codex CLI"), concluded the skill "has no Astra option", and never ran
`gcl models` — which lists `gpt-6-astra`. Hosts load a skill body only when the description matches, so the
description must name model families/aliases and say that "<model> agent/subagent/worker" phrasing means this skill.

## Task Index

| # | ID | Section | Depends On | Status | Description |
|---|-----|---------|-----------|--------|-------------|
| 1 | T-D-2 | GREEN | — | complete | Skill description names models + never-deny rule; v0.1.5 |
