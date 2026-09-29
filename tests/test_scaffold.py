import os
import re
import subprocess
import sys
from pathlib import Path

from gigachad_lite import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_version_flag_prints_version():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "gigachad_lite", "--version"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"gigachad-lite {__version__}"


def test_version_matches_pyproject():
    text = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match and match.group(1) == __version__
