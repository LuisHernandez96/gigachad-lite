"""Codex adapter (``codex exec``).

``codex`` echoes the prompt into its output streams, so the stream is never scanned for
markers: the worker's final message comes ONLY from the file passed via ``-o``. The
worker's real exit code is reported by the caller and is never coerced here.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import ClassVar

from gigachad_lite.adapters.base import Adapter, AgentCommand, ParsedResult, child_env

LAST_MESSAGE_FILE = "last-message.txt"


class CodexAdapter(Adapter):
    name = "codex"

    MODEL_ALIASES: ClassVar[dict[str, str]] = {
        "luna": "gpt-6-luna",
        "sol": "gpt-6-sol",
        "astra": "gpt-6-astra",
    }

    def build(
        self, model: str, mode: str, job_dir: Path, extra_args: Sequence[str], env: Mapping[str, str]
    ) -> AgentCommand:
        argv = ["codex", "exec", "-m", self.MODEL_ALIASES.get(model, model), "--skip-git-repo-check"]
        if mode == "read-only":
            argv += ["-s", "read-only"]
        else:
            argv.append("--dangerously-bypass-approvals-and-sandbox")
        argv += ["-o", str(Path(job_dir) / LAST_MESSAGE_FILE), *extra_args, "-"]
        return AgentCommand(argv=argv, env=child_env(env))

    def parse(self, job_dir: Path, stdout: str) -> ParsedResult:
        try:
            text = (Path(job_dir) / LAST_MESSAGE_FILE).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        return ParsedResult(final_message=text.strip())
