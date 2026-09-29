# Changelog

## 0.1.1

- Jobs now record `depth` in `meta.json`.
- Jobs killed on timeout/cancel are attributed via `killed_by`/`signal`; the text result says `killed by <reason> via <signal>`.
- Malformed depth env vars warn instead of crashing.
- Added a local CI script, `scripts/ci.sh`.
- Added CODEOWNERS and CONTRIBUTING.
- No hosted CI.

## 0.1.0

- Initial release: execute-only delegation CLI, codex/claude adapters, job store + supervisor, Claude Code and Codex plugins.
