import os
from pathlib import Path

import pytest

FAKES_DIR = Path(__file__).parent / "fakes"


@pytest.fixture
def fake_agents(monkeypatch, tmp_path):
    """Put fake codex/claude first on PATH, isolate the job store, return a FAKE_* env setter."""
    monkeypatch.setenv("PATH", str(FAKES_DIR) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("GIGACHAD_LITE_HOME", str(tmp_path / "home"))

    def set_fake(**knobs):
        for name, value in knobs.items():
            monkeypatch.setenv(f"FAKE_{name.upper()}", str(value))

    return set_fake


def pytest_configure(config):
    config.addinivalue_line("markers", "red_phase: tests written before their implementation exists")
