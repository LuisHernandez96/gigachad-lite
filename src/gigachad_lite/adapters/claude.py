"""Claude adapter (``claude -p --output-format json``).

The final message is the ``result`` field of the JSON document on stdout. The worker's
real exit code is reported by the caller and is never coerced here.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from gigachad_lite.adapters.base import Adapter, AgentCommand, ParsedResult, child_env

READ_ONLY_TOOLS = "Read,Glob,Grep"


class ClaudeAdapter(Adapter):
    name = "claude"

    def build(
        self, model: str, mode: str, job_dir: Path, extra_args: Sequence[str], env: Mapping[str, str]
    ) -> AgentCommand:
        argv = ["claude", "-p", "--model", model, "--output-format", "json"]
        if mode == "read-only":
            argv += ["--tools", READ_ONLY_TOOLS, "--strict-mcp-config"]
        else:
            argv.append("--dangerously-skip-permissions")
        argv += extra_args
        return AgentCommand(argv=argv, env=child_env(env))

    def parse(self, job_dir: Path, stdout: str) -> ParsedResult:
        try:
            data = json.loads(stdout)
            if not isinstance(data, dict):
                raise TypeError("expected a JSON object")
        except (ValueError, TypeError) as exc:
            return ParsedResult(final_message="", is_error=True, extras={"parse_error": str(exc)})
        extras = {k: data[k] for k in ("session_id", "total_cost_usd") if k in data}
        return ParsedResult(
            final_message=str(data.get("result", "")),
            is_error=bool(data.get("is_error", False)),
            extras=extras,
        )
