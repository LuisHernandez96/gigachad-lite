"""Detached supervisor: ``python -m gigachad_lite.supervise <job_dir>``.

Runs one worker in its own process group, enforces the timeout and the cancel marker,
then records the outcome in ``result.json`` and ``meta.json``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

from gigachad_lite.adapters import get_adapter
from gigachad_lite.jobs import CANCEL_MARKER, Job, write_json

POLL_INTERVAL = 0.2
DEFAULT_KILL_GRACE = 10.0


def kill_group(proc: subprocess.Popen, grace: float) -> str:
    """SIGTERM the worker's process group, then SIGKILL it once ``grace`` seconds have passed.

    Returns the name of the signal that ended the worker.
    """
    ended_by = "SIGTERM"
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        ended_by = "SIGKILL"
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()
    return ended_by


def run_worker(job: Job) -> None:
    prompt = (job.job_dir / "prompt.md").read_text(encoding="utf-8")
    adapter = get_adapter(job.agent)
    command = adapter.build(job.model, job.mode, job.job_dir, job.extra_args, os.environ)
    grace = float(os.environ.get("GIGACHAD_LITE_KILL_GRACE", DEFAULT_KILL_GRACE))
    transcript = job.job_dir / "transcript.log"

    job.state = "running"
    job.started_at = time.time()
    job.save()

    with open(transcript, "wb") as out:
        proc = subprocess.Popen(
            command.argv,
            cwd=job.cwd,
            env=command.env,
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        job.worker_pid = proc.pid
        job.save()
        try:
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
        except BrokenPipeError:
            pass

        deadline = time.monotonic() + job.timeout
        outcome = None
        while proc.poll() is None:
            if (job.job_dir / CANCEL_MARKER).exists():
                outcome = "cancelled"
            elif time.monotonic() >= deadline:
                outcome = "timed_out"
            if outcome:
                job.killed_by = "cancel" if outcome == "cancelled" else "timeout"
                job.signal = kill_group(proc, grace)
                break
            time.sleep(POLL_INTERVAL)

    job.exit_code = proc.returncode
    job.finished_at = time.time()
    parsed = adapter.parse(job.job_dir, transcript.read_text(encoding="utf-8", errors="replace"))
    job.final_message = parsed.final_message

    if outcome:
        job.state = outcome
    elif job.exit_code != 0:
        job.state, job.error = "failed", f"worker exited with exit code {job.exit_code}"
    elif parsed.is_error:
        job.state, job.error = "failed", "agent reported an error"
    elif not parsed.final_message:
        job.state, job.error = "failed", "empty final message"
    else:
        job.state = "succeeded"

    write_json(
        job.job_dir / "result.json",
        {
            "id": job.id,
            "state": job.state,
            "exit_code": job.exit_code,
            "killed_by": job.killed_by,
            "signal": job.signal,
            "final_message": job.final_message,
            "error": job.error,
            "agent": job.agent,
            "model": job.model,
            "duration_s": job.finished_at - job.started_at,
            "extras": parsed.extras,
        },
    )
    job.save()


def main(argv: list[str]) -> int:
    job = Job.load(Path(argv[0]))
    job.supervisor_pid = os.getpid()
    job.save()
    try:
        run_worker(job)
    except Exception:  # noqa: BLE001 - any failure must still be recorded on the job
        job.state = "failed"
        job.error = traceback.format_exc().strip().splitlines()[-1]
        job.finished_at = time.time()
        job.save()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
