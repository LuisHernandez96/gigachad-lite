import json
import os
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GCL = REPO_ROOT / "bin" / "gcl"
FAKES_DIR = REPO_ROOT / "tests" / "fakes"

pytestmark = pytest.mark.integration


@pytest.fixture
def gcl(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    env = {
        **os.environ,
        "PATH": str(FAKES_DIR) + os.pathsep + os.environ.get("PATH", ""),
        "GIGACHAD_LITE_HOME": str(tmp_path / "home"),
        "GIGACHAD_LITE_KILL_GRACE": "1",
    }
    env.pop("GIGACHAD_LITE_DEPTH", None)

    def run(*args, cwd=project, **extra_env):
        return subprocess.run(
            [str(GCL), *map(str, args)],
            cwd=cwd,
            env={**env, **extra_env},
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    run.project = project
    run.env = env
    return run


def start(gcl, agent="codex", **extra_env):
    proc = gcl("start", "--agent", agent, "--model", "m", "--prompt", "hello", **extra_env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_full_lifecycle(gcl):
    job_id = start(gcl, FAKE_SLEEP="3", FAKE_LAST_MESSAGE="final answer")

    assert gcl("status", job_id).stdout.split()[1] == "running"

    waited = gcl("wait", job_id)
    assert waited.returncode == 0, waited.stderr

    result = json.loads(gcl("result", job_id, "--json").stdout)
    assert result["state"] == "succeeded"
    assert result["final_message"] == "final answer"
    assert "codex working" in gcl("logs", job_id).stdout


def test_parallel_jobs_listed_for_this_cwd_only(gcl, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    proc = gcl("start", "--agent", "codex", "--model", "m", "--prompt", "x", cwd=other)
    other_id = proc.stdout.strip()

    ids = [start(gcl, "codex", FAKE_SLEEP="1"), start(gcl, "claude", FAKE_SLEEP="1")]
    listed = gcl("status").stdout
    assert all(job_id in listed for job_id in ids)
    assert other_id not in listed

    for job_id in ids + [other_id]:
        assert gcl("wait", job_id).returncode == 0


def test_cancel_kills_worker(gcl):
    job_id = start(gcl, FAKE_SLEEP="30")
    time.sleep(1)
    worker_pid = json.loads(gcl("status", job_id, "--json").stdout)["worker_pid"]
    assert worker_pid and pid_alive(worker_pid)

    assert gcl("cancel", job_id).returncode == 0
    assert gcl("wait", job_id).returncode == 130

    deadline = time.time() + 5
    while pid_alive(worker_pid) and time.time() < deadline:
        time.sleep(0.1)
    assert not pid_alive(worker_pid)


def test_run_timeout_exits_124(gcl):
    proc = gcl("run", "--agent", "codex", "--model", "m", "--prompt", "x", "--timeout", "1", FAKE_SLEEP="30")
    assert proc.returncode == 124


def test_recursion_guard_refuses_start(gcl):
    proc = gcl("start", "--agent", "codex", "--model", "m", "--prompt", "x", GIGACHAD_LITE_DEPTH="1")
    assert proc.returncode == 2


def test_job_survives_orchestrator_shell_exit(gcl):
    started = subprocess.run(
        ["sh", "-c", f'"{GCL}" start --agent codex --model m --prompt x'],
        cwd=gcl.project,
        env={**gcl.env, "FAKE_SLEEP": "1", "FAKE_LAST_MESSAGE": "survived"},
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    job_id = started.stdout.strip()

    assert gcl("wait", job_id).returncode == 0
    assert json.loads(gcl("result", job_id, "--json").stdout)["final_message"] == "survived"
