"""List models the orchestrator can delegate to."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Callable

CLAUDE_MODELS = ("sonnet", "opus", "haiku", "fable")

_MODEL_LINE = re.compile(r"""^\s*model\s*=\s*("([^"\\]|\\.)*"|'[^']*')""")


def _resolve_codex_home(codex_home: Path | None) -> Path:
    if codex_home is not None:
        return codex_home
    env_home = os.environ.get("CODEX_HOME")
    return Path(env_home) if env_home else Path.home() / ".codex"


def _read_codex_default(home: Path) -> str | None:
    try:
        lines = (home / "config.toml").read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        if line.lstrip().startswith("["):
            return None
        match = _MODEL_LINE.match(line)
        if match:
            return match.group(1)[1:-1]
    return None


def _read_codex_ids(home: Path) -> list[str]:
    try:
        data = json.loads((home / "models_cache.json").read_text())
        entries = data["models"]
        return [str(entry.get("slug") or entry["id"]) for entry in entries]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


def list_models(
    codex_home: Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> list[dict]:
    """Return delegatable models as ``{"agent", "id", "default"}`` entries."""
    models: list[dict] = []
    if which("claude"):
        models.extend({"agent": "claude", "id": model_id, "default": False} for model_id in CLAUDE_MODELS)
    if which("codex"):
        home = _resolve_codex_home(codex_home)
        default_id = _read_codex_default(home)
        models.extend(
            {"agent": "codex", "id": model_id, "default": model_id == default_id}
            for model_id in _read_codex_ids(home)
        )
    return models
