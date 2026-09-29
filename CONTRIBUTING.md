# Contributing

1. Fork the repo and create a branch.
2. Open a pull request against `main`.

Direct pushes, force-pushes and deletions of `main` are blocked by repository rulesets.

## CI

There is no hosted CI. Run the local script (after `pip install -e ".[dev]"`):

```sh
scripts/ci.sh
```

Paste its final `CI PASSED` line in the PR description. The maintainer re-runs it locally before merging (squash or rebase).

## Scope

Keep the tool execute-only and stdlib-only.
