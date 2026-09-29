from __future__ import annotations

import argparse

from gigachad_lite import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gigachad-lite")
    parser.add_argument("--version", action="version", version=f"gigachad-lite {__version__}")
    parser.parse_args(argv)
    return 0
