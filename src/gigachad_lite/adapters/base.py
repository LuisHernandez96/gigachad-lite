"""Adapter contract shared by the worker CLIs, plus the sanitised child environment.

Lessons encoded here:
- Nested ``claude`` refuses to start when ``CLAUDECODE`` is set, so it is dropped.
- Children get ``GIGACHAD_AGENT_CHILD=1`` and an incremented ``GIGACHAD_LITE_DEPTH``.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentCommand:
    argv: list[str]
    env: dict[str, str]


@dataclass
class ParsedResult:
    final_message: str
    is_error: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


def child_env(env: Mapping[str, str]) -> dict[str, str]:
    child = {k: v for k, v in env.items() if k != "CLAUDECODE"}
    child["GIGACHAD_AGENT_CHILD"] = "1"
    try:
        depth = int(env.get("GIGACHAD_LITE_DEPTH", "0"))
    except ValueError:
        depth = 0
    child["GIGACHAD_LITE_DEPTH"] = str(depth + 1)
    return child


class Adapter:
    """Builds a worker command (prompt is always delivered on stdin) and parses its output."""

    name = ""

    def build(
        self, model: str, mode: str, job_dir: Path, extra_args: Sequence[str], env: Mapping[str, str]
    ) -> AgentCommand:
        raise NotImplementedError

    def parse(self, job_dir: Path, stdout: str) -> ParsedResult:
        raise NotImplementedError
