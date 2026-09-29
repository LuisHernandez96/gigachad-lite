#!/bin/sh
# Local CI. Requires: pip install -e ".[dev]"
set -eu
cd "$(dirname "$0")/.."
ruff check src tests
pytest -q
echo "CI PASSED"
