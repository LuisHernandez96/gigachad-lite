# gigachad-lite

Execute-only delegation between coding agents, in both directions: Claude Code → Codex workers and Codex → Claude workers. An orchestrating agent hands gigachad-lite a prompt; it runs the worker (`claude` or `codex` CLI) as a tracked background job and returns the worker's final message and real exit status. It does **not** plan, write task files, run tests or lint, review, validate, or commit — the orchestrator owns all of that.

Python ≥ 3.9, standard library only. The CLI is available as `gigachad-lite` and `gcl`.

## Install

Prerequisites: `python3` ≥ 3.9, and the worker CLIs you want to use (`claude`, `codex`) installed and logged in.

**Claude Code**

```
/plugin marketplace add LuisHernandez96/gigachad-lite
/plugin install gigachad-lite@gigachad-lite
```

**Codex**

```
codex plugin marketplace add LuisHernandez96/gigachad-lite
codex plugin add gigachad-lite@gigachad-lite
```

**Standalone CLI**

```
pipx install git+https://github.com/LuisHernandez96/gigachad-lite
# or: pip install --user git+https://github.com/LuisHernandez96/gigachad-lite
```

## Quick start

```
gcl start --agent codex --model gpt-6-luna --prompt-file task.md   # prints a job id
gcl wait <id>                                                      # blocks, prints the final message
gcl result <id>
```

`gcl run` does start + wait in one step.

## CLI reference

| Command | Purpose | Key flags |
| --- | --- | --- |
| `start` | Start a background job, print its id | `--agent {claude,codex}`, `--model`, `--prompt` or `--prompt-file` (`-` for stdin), `--cwd`, `--mode {write,read-only}`, `--timeout`, `--json` |
| `run` | Start a job, wait, print the result | same as `start` |
| `status` | Show one job, or the jobs of the current directory | `[job_id]`, `--json` |
| `list` | List jobs of the current directory | `--all`, `--json` |
| `wait` | Wait for a job and print its result | `--timeout`, `--json` |
| `result` | Print the result of a finished job | `--json` |
| `logs` | Print a job's transcript | `--tail N` |
| `cancel` | Cancel a running job (kills the whole process group) | |
| `models` | List models available for delegation | `--agent {claude,codex}`, `--json` |

Arguments after `--` are passed through to the worker CLI.

Exit codes of `run`, `wait` and `result` mirror the job state:

| Code | Meaning |
| --- | --- |
| 0 | succeeded |
| 1 | failed (worker's real exit code is reported in the job record) |
| 2 | usage error |
| 3 | job not finished yet |
| 124 | timed out |
| 130 | cancelled |

## How it works

- Jobs live in `<GIGACHAD_LITE_HOME>/jobs/<id>/` (default `~/.local/state/gigachad-lite`).
- `start` spawns a detached supervisor (`python -m gigachad_lite.supervise <job_dir>`) that runs the worker in its own process group, so timeout and cancel kill the whole tree, and records the worker's real exit code (never altered). A job killed on timeout or cancel also records `killed_by` (`timeout` or `cancel`) and `signal` (`SIGTERM`, or `SIGKILL` if the worker outlived the grace period); both are `null` otherwise, and the result line reads `killed by <killed_by> via <signal>` instead of `exit <code>`.
- The final message comes from a dedicated source, never from scanning the output stream: for Codex the file written by `codex exec -o <file>`; for Claude the `result` field of its JSON output.
- Worker environment: `CLAUDECODE` is removed (nested `claude` refuses to start otherwise), `GIGACHAD_AGENT_CHILD=1` is set (disables orchestrator hooks of installed plugins), and `GIGACHAD_LITE_DEPTH` is incremented.

## Safety

- `--mode write` (default) runs workers with permission prompts bypassed (`--dangerously-bypass-approvals-and-sandbox` for Codex, `--dangerously-skip-permissions` for Claude). Only use it on repositories you trust. Use `--mode read-only` for reviews and analysis.
- Recursion guard: a job refuses to start when `GIGACHAD_LITE_DEPTH` has reached `GIGACHAD_LITE_MAX_DEPTH` (default 1), so workers cannot spawn workers.
- Environment variables: `GIGACHAD_LITE_HOME` (job store root), `GIGACHAD_LITE_DEPTH` (current depth, unset = 0), `GIGACHAD_LITE_MAX_DEPTH` (default 1).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). There is no hosted CI; run `scripts/ci.sh` locally before opening a PR.

## Relationship to Gigachad

gigachad-lite is the small execute-only core. For the full TDD loop (planning, sprints, tests, review, commits) see [Gigachad](https://github.com/LuisHernandez96/GigachadDev).
