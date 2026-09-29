from gigachad_lite.adapters.base import Adapter
from gigachad_lite.adapters.claude import ClaudeAdapter
from gigachad_lite.adapters.codex import CodexAdapter

AGENTS = ("claude", "codex")

_ADAPTERS = {"claude": ClaudeAdapter, "codex": CodexAdapter}


def get_adapter(name: str) -> Adapter:
    try:
        return _ADAPTERS[name]()
    except KeyError:
        raise ValueError(f"unknown agent {name!r}; supported: {', '.join(AGENTS)}") from None
