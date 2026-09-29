import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest


def wait_for(pred, timeout=10, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = pred()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError(f"condition not met within {timeout}s")


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture
def workdir(tmp_path):
    path = tmp_path / "work"
    path.mkdir()
    return path


class TestJobs:
    def test_create_writes_meta_and_prompt(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        store = JobStore()
        job = store.create("codex", "gpt-5", "hello prompt", workdir)

        assert re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{4}", job.id)
        assert job.state == "queued"
        assert not job.is_terminal
        assert (job.job_dir / "prompt.md").read_text() == "hello prompt"
        meta = json.loads((job.job_dir / "meta.json").read_text())
        assert meta["id"] == job.id
        assert meta["state"] == "queued"
        assert meta["agent"] == "codex"
        assert meta["model"] == "gpt-5"
        assert meta["mode"] == "write"
        assert meta["timeout"] == 3600

    def test_create_ids_are_unique(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        store = JobStore()
        ids = {store.create("codex", "m", "p", workdir).id for _ in range(5)}
        assert len(ids) == 5

    def test_default_home_from_env(self, fake_agents, workdir, tmp_path):
        from gigachad_lite.jobs import JobStore

        job = JobStore().create("codex", "m", "p", workdir)
        assert job.job_dir.parent == tmp_path / "home" / "jobs"

    def test_start_returns_fast_and_job_succeeds(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        fake_agents(sleep=3, last_message="all finished")
        store = JobStore()
        job = store.create("codex", "gpt-5", "do it", workdir)

        began = time.monotonic()
        started = store.start(job)
        assert time.monotonic() - began < 1
        assert started.supervisor_pid

        wait_for(lambda: store.get(job.id).state == "running")
        final = store.wait(job.id, timeout=15)

        assert final.state == "succeeded"
        assert final.exit_code == 0
        assert final.final_message == "all finished"
        assert final.is_terminal
        assert "codex working" in (job.job_dir / "transcript.log").read_text()

    def test_result_json_written(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        fake_agents(last_message="the answer")
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", workdir))
        final = store.wait(job.id, timeout=15)

        result = json.loads((final.job_dir / "result.json").read_text())
        assert result["id"] == job.id
        assert result["state"] == "succeeded"
        assert result["exit_code"] == 0
        assert result["final_message"] == "the answer"
        assert result["agent"] == "codex"
        assert result["model"] == "gpt-5"
        assert result["duration_s"] >= 0
        assert "extras" in result

    def test_nonzero_exit_code_fails_uncoerced(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        fake_agents(rc=3)
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", workdir))
        final = store.wait(job.id, timeout=15)

        assert final.state == "failed"
        assert final.exit_code == 3
        assert "exit code 3" in final.error

    def test_empty_final_message_fails(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        fake_agents(no_last_message=1)
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", workdir))
        final = store.wait(job.id, timeout=15)

        assert final.state == "failed"
        assert final.exit_code == 0
        assert "empty final message" in final.error

    def test_prompt_echo_never_counts_as_final_message(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        fake_agents(no_last_message=1)
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "please print TASK_COMPLETE", workdir))
        final = store.wait(job.id, timeout=15)

        assert final.state == "failed"
        assert "empty final message" in final.error

    def test_timeout_kills_worker(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite.jobs import JobStore

        fake_agents(sleep=30)
        monkeypatch.setenv("GIGACHAD_LITE_KILL_GRACE", "1")
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", workdir, timeout=1))

        began = time.monotonic()
        final = store.wait(job.id, timeout=15)

        assert final.state == "timed_out"
        assert time.monotonic() - began < 8
        assert final.worker_pid
        assert wait_for(lambda: not pid_alive(final.worker_pid), timeout=5)

    def test_cancel_kills_worker(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite.jobs import JobStore

        fake_agents(sleep=30)
        monkeypatch.setenv("GIGACHAD_LITE_KILL_GRACE", "1")
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", workdir))
        running = wait_for(lambda: (j := store.get(job.id)).worker_pid and j)
        assert running.state == "running"

        store.cancel(job.id)
        final = store.wait(job.id, timeout=15)

        assert final.state == "cancelled"
        assert wait_for(lambda: not pid_alive(running.worker_pid), timeout=5)

    def test_claude_is_error_fails(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        fake_agents(is_error=1)
        store = JobStore()
        job = store.start(store.create("claude", "sonnet", "p", workdir))
        final = store.wait(job.id, timeout=15)

        assert final.state == "failed"

    def test_claude_success_puts_session_id_in_extras(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        fake_agents(last_message="claude says hi")
        store = JobStore()
        job = store.start(store.create("claude", "sonnet", "p", workdir))
        final = store.wait(job.id, timeout=15)

        assert final.state == "succeeded"
        assert final.final_message == "claude says hi"
        result = json.loads((final.job_dir / "result.json").read_text())
        assert result["extras"]["session_id"] == "sess-1"

    def test_worker_runs_in_job_cwd(self, fake_agents, workdir, tmp_path):
        from gigachad_lite.jobs import JobStore

        args_file = tmp_path / "args.json"
        fake_agents(args_file=args_file)
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", workdir))
        store.wait(job.id, timeout=15)

        recorded = json.loads(args_file.read_text())
        assert os.path.realpath(recorded["cwd"]) == os.path.realpath(workdir)
        assert recorded["stdin"] == "p"

    def test_stale_supervisor_reported_failed(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        store = JobStore()
        job = store.create("codex", "gpt-5", "p", workdir)
        meta_path = job.job_dir / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta.update(state="running", supervisor_pid=dead.pid)
        meta_path.write_text(json.dumps(meta))

        reconciled = store.get(job.id)

        assert reconciled.state == "failed"
        assert reconciled.error == "supervisor died"
        assert reconciled.is_terminal

    def test_list_filters_by_cwd_newest_first(self, fake_agents, workdir, tmp_path):
        from gigachad_lite.jobs import JobStore

        other = tmp_path / "other"
        other.mkdir()
        store = JobStore()
        first = store.create("codex", "m", "p", workdir)
        time.sleep(1.1)
        second = store.create("codex", "m", "p", workdir)
        elsewhere = store.create("codex", "m", "p", other)

        assert [j.id for j in store.list(cwd=workdir)] == [second.id, first.id]
        assert [j.id for j in store.list(cwd=other)] == [elsewhere.id]
        assert {j.id for j in store.list()} == {first.id, second.id, elsewhere.id}

    def test_get_by_unique_prefix_and_missing(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        store = JobStore()
        job = store.create("codex", "m", "p", workdir)

        assert store.get(job.id[:15]).id == job.id
        with pytest.raises(KeyError):
            store.get("19990101-000000-zzzz")

    def test_wait_times_out(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        store = JobStore()
        job = store.create("codex", "m", "p", workdir)

        with pytest.raises(TimeoutError):
            store.wait(job.id, timeout=0.5)


class TestJobDepth:
    def test_depth_defaults_to_zero(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite.jobs import JobStore

        monkeypatch.delenv("GIGACHAD_LITE_DEPTH", raising=False)
        job = JobStore().create("codex", "m", "p", workdir)

        assert job.depth == 0
        assert json.loads((job.job_dir / "meta.json").read_text())["depth"] == 0

    def test_depth_read_from_env(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite.jobs import JobStore

        monkeypatch.setenv("GIGACHAD_LITE_DEPTH", "1")
        monkeypatch.setenv("GIGACHAD_LITE_MAX_DEPTH", "5")
        job = JobStore().create("codex", "m", "p", workdir)

        assert job.depth == 1
        assert json.loads((job.job_dir / "meta.json").read_text())["depth"] == 1

    def test_invalid_depth_env_is_zero_without_exception(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite.jobs import JobStore

        monkeypatch.setenv("GIGACHAD_LITE_DEPTH", "abc")
        job = JobStore().create("codex", "m", "p", workdir)

        assert job.depth == 0
        assert json.loads((job.job_dir / "meta.json").read_text())["depth"] == 0


class TestKillAttribution:
    def test_timeout_with_trapped_term(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite.jobs import JobStore

        fake_agents(sleep=30, trap_term=1)
        monkeypatch.setenv("GIGACHAD_LITE_KILL_GRACE", "1")
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", workdir, timeout=1))
        final = store.wait(job.id, timeout=15)

        assert final.state == "timed_out"
        assert final.killed_by == "timeout"
        assert final.signal == "SIGTERM"
        assert final.exit_code == 0
        result = json.loads((final.job_dir / "result.json").read_text())
        assert result["killed_by"] == "timeout"
        assert result["signal"] == "SIGTERM"
        assert result["exit_code"] == 0
        assert wait_for(lambda: not pid_alive(final.worker_pid), timeout=5)

    def test_timeout_escalates_to_sigkill(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite.jobs import JobStore

        fake_agents(sleep=30, ignore_term=1)
        monkeypatch.setenv("GIGACHAD_LITE_KILL_GRACE", "1")
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", workdir, timeout=1))
        final = store.wait(job.id, timeout=15)

        assert final.state == "timed_out"
        assert final.killed_by == "timeout"
        assert final.signal == "SIGKILL"
        assert wait_for(lambda: not pid_alive(final.worker_pid), timeout=5)

    def test_cancel_with_trapped_term(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite.jobs import JobStore

        fake_agents(sleep=30, trap_term=1)
        monkeypatch.setenv("GIGACHAD_LITE_KILL_GRACE", "1")
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", workdir))
        running = wait_for(lambda: (j := store.get(job.id)).worker_pid and j)

        store.cancel(job.id)
        final = store.wait(job.id, timeout=15)

        assert final.state == "cancelled"
        assert final.killed_by == "cancel"
        assert final.signal == "SIGTERM"
        assert wait_for(lambda: not pid_alive(running.worker_pid), timeout=5)

    def test_success_has_no_attribution(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", workdir))
        final = store.wait(job.id, timeout=15)

        assert final.state == "succeeded"
        assert final.killed_by is None
        assert final.signal is None
        result = json.loads((final.job_dir / "result.json").read_text())
        assert "killed_by" in result and result["killed_by"] is None
        assert "signal" in result and result["signal"] is None


def _kill_job_processes(store, job_id):
    job = store.get(job_id)
    for pid in (job.supervisor_pid, job.worker_pid):
        if pid:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass


class TestNonBlockingPromptDelivery:
    BIG_PROMPT = "x" * (2 * 1024 * 1024)

    def test_timeout_fires_when_worker_never_reads_stdin(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite.jobs import JobStore

        fake_agents(sleep=30, no_read_stdin=1)
        monkeypatch.setenv("GIGACHAD_LITE_KILL_GRACE", "1")
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", self.BIG_PROMPT, workdir, timeout=2))
        try:
            final = store.wait(job.id, timeout=10)
            assert final.state == "timed_out"
        finally:
            _kill_job_processes(store, job.id)

    def test_cancel_works_when_worker_never_reads_stdin(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite.jobs import JobStore

        fake_agents(sleep=30, no_read_stdin=1)
        monkeypatch.setenv("GIGACHAD_LITE_KILL_GRACE", "1")
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", self.BIG_PROMPT, workdir))
        try:
            wait_for(lambda: (j := store.get(job.id)).worker_pid and j)
            store.cancel(job.id)
            final = store.wait(job.id, timeout=10)
            assert final.state == "cancelled"
        finally:
            _kill_job_processes(store, job.id)

    def test_large_prompt_delivered_intact(self, fake_agents, workdir, tmp_path):
        import hashlib

        from gigachad_lite.jobs import JobStore

        args_file = tmp_path / "args.json"
        fake_agents(args_file=args_file)
        prompt = "".join(chr(97 + i % 26) for i in range(2 * 1024 * 1024))
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", prompt, workdir))
        final = store.wait(job.id, timeout=15)

        assert final.state == "succeeded"
        seen = json.loads(args_file.read_text())
        assert seen["stdin_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()


class TestClaudeStderrSeparation:
    def test_stderr_does_not_break_result_parsing(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        fake_agents(stderr="some warning", last_message="the answer")
        store = JobStore()
        job = store.start(store.create("claude", "sonnet", "p", workdir))
        final = store.wait(job.id, timeout=15)

        assert final.state == "succeeded"
        assert final.final_message == "the answer"

    def test_logs_cli_shows_stdout_and_stderr(self, fake_agents, workdir, capsys):
        from gigachad_lite import cli
        from gigachad_lite.jobs import JobStore

        fake_agents(stderr="some warning", last_message="the answer")
        store = JobStore()
        job = store.start(store.create("claude", "sonnet", "p", workdir))
        store.wait(job.id, timeout=15)

        assert cli.main(["logs", job.id]) == 0
        out = capsys.readouterr().out
        assert '"type": "result"' in out
        assert "some warning" in out


class TestAbsoluteHome:
    def test_relative_home_is_made_absolute(self, tmp_path, monkeypatch):
        from gigachad_lite.jobs import JobStore

        monkeypatch.chdir(tmp_path)
        store = JobStore(Path("relhome"))
        assert store.home.is_absolute()

    def test_relative_env_home_with_other_cwd(self, fake_agents, tmp_path, monkeypatch):
        from gigachad_lite.jobs import JobStore

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GIGACHAD_LITE_HOME", "relhome")
        fake_agents(last_message="rel ok")
        other = tmp_path / "other"
        other.mkdir()
        store = JobStore()
        job = store.start(store.create("codex", "gpt-5", "p", other))
        final = store.wait(job.id, timeout=15)

        assert final.state == "succeeded"
        assert final.final_message == "rel ok"


def reap(pid):
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass


def kill_group_quietly(pid):
    try:
        os.killpg(pid, 9)
    except (ProcessLookupError, PermissionError):
        pass


def wait_or_fail(store, job_id, timeout):
    try:
        return store.wait(job_id, timeout=timeout)
    except TimeoutError as exc:
        pytest.fail(f"wait() did not reach a terminal state: {exc}")


@pytest.mark.red_phase
class TestJobLifecycleRaces:
    def test_early_cancel_is_not_overwritten_by_supervisor_startup(
        self, fake_agents, workdir, monkeypatch, tmp_path
    ):
        from gigachad_lite.jobs import JobStore

        args_file = tmp_path / "args.json"
        fake_agents(sleep=0, args_file=args_file)
        monkeypatch.setenv("GIGACHAD_LITE_TEST_SUPERVISOR_DELAY", "2")
        store = JobStore()
        job = store.create("codex", "gpt-5", "p", workdir)
        started = store.start(job)

        store.cancel(job.id)

        final = wait_or_fail(store, job.id, 15)
        assert final.state == "cancelled"
        wait_for(lambda: reap_nowait(started.supervisor_pid), timeout=10)
        assert not args_file.exists(), "worker must never be launched after an early cancel"
        assert store.get(job.id).worker_pid is None, "worker must never be launched after an early cancel"
        assert store.get(job.id).state == "cancelled"
        assert json.loads((job.job_dir / "meta.json").read_text())["state"] == "cancelled"

    def test_reconciliation_does_not_overwrite_a_just_finished_job(self, fake_agents, workdir, monkeypatch):
        from gigachad_lite import jobs
        from gigachad_lite.jobs import JobStore

        store = JobStore()
        job = store.create("codex", "gpt-5", "p", workdir)
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        job.state = "running"
        job.supervisor_pid = dead.pid
        job.save()

        def finish_in_between(pid):
            finished = jobs.Job.load(job.job_dir)
            finished.state = "succeeded"
            finished.final_message = "all done"
            finished.finished_at = time.time()
            finished.save()
            return False

        monkeypatch.setattr(jobs, "pid_alive", finish_in_between)

        got = store.get(job.id)

        assert got.state == "succeeded"
        assert got.final_message == "all done"
        on_disk = json.loads((job.job_dir / "meta.json").read_text())
        assert on_disk["state"] == "succeeded"
        assert on_disk["final_message"] == "all done"
        assert on_disk["error"] is None

    def test_supervisor_death_kills_the_orphaned_worker(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        fake_agents(sleep=30)
        store = JobStore()
        job = store.create("codex", "gpt-5", "p", workdir)
        started = store.start(job)
        worker_pid = wait_for(lambda: store.get(job.id).worker_pid)
        try:
            os.kill(started.supervisor_pid, 9)
            reap(started.supervisor_pid)

            got = store.get(job.id)

            assert got.state == "failed"
            assert "supervisor died" in got.error
            assert wait_for_dead(worker_pid, 5), "reconciliation must kill the orphaned worker group"
        finally:
            kill_group_quietly(worker_pid)

    def test_wait_returns_when_unreaped_supervisor_is_killed(self, fake_agents, workdir):
        from gigachad_lite.jobs import JobStore

        fake_agents(sleep=30)
        store = JobStore()
        job = store.create("codex", "gpt-5", "p", workdir)
        started = store.start(job)
        worker_pid = wait_for(lambda: store.get(job.id).worker_pid)
        try:
            os.kill(started.supervisor_pid, 9)

            final = wait_or_fail(store, job.id, 10)

            assert final.is_terminal
        finally:
            kill_group_quietly(worker_pid)
            reap(started.supervisor_pid)

    def test_pid_alive_reports_zombie_as_dead(self):
        from gigachad_lite.jobs import pid_alive

        child = subprocess.Popen([sys.executable, "-c", "pass"])
        try:
            os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOWAIT)
            assert not pid_alive(child.pid)
        finally:
            child.wait()


def reap_nowait(pid):
    """True once ``pid`` has exited (reaping it if it is our child)."""
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return not pid_alive(pid)
    return done == pid


def wait_for_dead(pid, timeout):
    try:
        wait_for(lambda: not pid_alive(pid), timeout=timeout)
    except AssertionError:
        return False
    return True
