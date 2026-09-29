"""Job store: one directory per job under ``<home>/jobs/<id>/``.

Files: ``meta.json`` (state), ``prompt.md``, ``transcript.log`` (worker output),
``result.json`` (final outcome), and a ``cancel`` marker when cancellation is requested.
"""

from __future__ import annotations

import json
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

TERMINAL_STATES = ("succeeded", "failed", "timed_out", "cancelled")
DEFAULT_TIMEOUT = 3600
CANCEL_MARKER = "cancel"


def default_home() -> Path:
    home = os.environ.get("GIGACHAD_LITE_HOME")
    return Path(home) if home else Path.home() / ".local" / "state" / "gigachad-lite"


def write_json(path: Path, data: Any) -> None:
    """Atomically replace ``path`` with ``data`` as JSON."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass
class Job:
    id: str
    agent: str
    model: str
    cwd: str
    job_dir: Path
    mode: str = "write"
    timeout: int = DEFAULT_TIMEOUT
    extra_args: list = field(default_factory=list)
    state: str = "queued"
    created_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None
    supervisor_pid: int | None = None
    worker_pid: int | None = None
    exit_code: int | None = None
    error: str | None = None
    final_message: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @classmethod
    def load(cls, job_dir: Path) -> Job:
        meta = json.loads((job_dir / "meta.json").read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)} - {"job_dir"}
        return cls(job_dir=job_dir, **{k: v for k, v in meta.items() if k in known})

    def save(self) -> None:
        meta = asdict(self)
        del meta["job_dir"]
        write_json(self.job_dir / "meta.json", meta)


class JobStore:
    def __init__(self, home: Path | None = None) -> None:
        self.jobs_dir = (Path(home) if home else default_home()) / "jobs"

    def create(
        self,
        agent: str,
        model: str,
        prompt: str,
        cwd: Path,
        mode: str = "write",
        timeout: int = DEFAULT_TIMEOUT,
        extra_args: tuple = (),
    ) -> Job:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        while True:
            job_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"
            try:
                (self.jobs_dir / job_id).mkdir()
                break
            except FileExistsError:
                continue
        job = Job(
            id=job_id,
            agent=agent,
            model=model,
            cwd=str(cwd),
            job_dir=self.jobs_dir / job_id,
            mode=mode,
            timeout=timeout,
            extra_args=list(extra_args),
            created_at=time.time(),
        )
        (job.job_dir / "prompt.md").write_text(prompt, encoding="utf-8")
        job.save()
        return job

    def start(self, job: Job) -> Job:
        if os.name != "posix":
            raise NotImplementedError("gigachad-lite v0.1 supports POSIX systems only")
        package_root = str(Path(__file__).resolve().parent.parent)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_root, env.get("PYTHONPATH")]))
        proc = subprocess.Popen(
            [sys.executable, "-m", "gigachad_lite.supervise", str(job.job_dir)],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        job.supervisor_pid = proc.pid
        return job

    def get(self, job_id: str) -> Job:
        job_dir = self._resolve(job_id)
        job = Job.load(job_dir)
        if not job.is_terminal and job.supervisor_pid and not pid_alive(job.supervisor_pid):
            job.state = "failed"
            job.error = "supervisor died"
            job.finished_at = time.time()
            job.save()
        return job

    def list(self, cwd: Path | None = None) -> list[Job]:
        if not self.jobs_dir.is_dir():
            return []
        jobs = [self.get(p.name) for p in sorted(self.jobs_dir.iterdir(), reverse=True) if p.is_dir()]
        if cwd is not None:
            wanted = os.path.realpath(cwd)
            jobs = [j for j in jobs if os.path.realpath(j.cwd) == wanted]
        return jobs

    def wait(self, job_id: str, timeout: float | None = None) -> Job:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            job = self.get(job_id)
            if job.is_terminal:
                return job
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(f"job {job.id} still {job.state} after {timeout}s")
            time.sleep(0.1)

    def cancel(self, job_id: str) -> Job:
        job = Job.load(self._resolve(job_id))
        if job.is_terminal:
            return job
        (job.job_dir / CANCEL_MARKER).touch()
        if not pid_alive(job.supervisor_pid):
            if job.worker_pid:
                try:
                    os.killpg(job.worker_pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            job.state = "cancelled"
            job.finished_at = time.time()
            job.save()
        return job

    def _resolve(self, job_id: str) -> Path:
        if (self.jobs_dir / job_id / "meta.json").is_file():
            return self.jobs_dir / job_id
        matches = []
        if self.jobs_dir.is_dir():
            matches = [p for p in self.jobs_dir.iterdir() if p.name.startswith(job_id)]
        if len(matches) != 1:
            raise KeyError(job_id)
        return matches[0]
