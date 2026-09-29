"""Defensive parsing of the delegation-depth environment variables."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

DEFAULT_MAX_DEPTH = 1
_warned: set = set()


def reset_warnings() -> None:
    _warned.clear()


def _int_var(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, "")
    if not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        if name not in _warned:
            _warned.add(name)
            print(f"warning: ignoring malformed {name}={raw!r}; using {default}", file=sys.stderr)
        return default


def current_depth(env: Mapping[str, str] | None = None) -> int:
    return _int_var(os.environ if env is None else env, "GIGACHAD_LITE_DEPTH", 0)


def max_depth(env: Mapping[str, str] | None = None) -> int:
    return _int_var(os.environ if env is None else env, "GIGACHAD_LITE_MAX_DEPTH", DEFAULT_MAX_DEPTH)
