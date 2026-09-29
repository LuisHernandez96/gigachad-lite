import io
import json
import re

import pytest


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    path = tmp_path / "work"
    path.mkdir()
    monkeypatch.chdir(path)
    return path


def run_cli(capsys, *argv):
    from gigachad_lite import cli

    try:
        code = cli.main([str(a) for a in argv])
    except SystemExit as exc:  # argparse usage errors exit instead of returning
        code = exc.code
    out = capsys.readouterr()
    return code, out.out, out.err


def start_job(capsys, *extra, agent="codex", prompt="do it"):
    code, out, _ = run_cli(capsys, "start", "--agent", agent, "--model", "m", "--prompt", prompt, *extra)
    assert code == 0
    return out.strip()


def test_version_still_works(capsys):
    from gigachad_lite import cli

    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "0.1.0" in capsys.readouterr().out


class TestCli:
    def test_start_prints_job_id(self, fake_agents, workdir, capsys):
        job_id = start_job(capsys)
        assert re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{4}", job_id)

    def test_start_json_then_wait_json_succeeds(self, fake_agents, workdir, capsys):
        fake_agents(last_message="all good")
        code, out, _ = run_cli(
            capsys, "start", "--agent", "codex", "--model", "m", "--prompt", "hi", "--json"
        )
        assert code == 0
        started = json.loads(out)
        assert set(started) >= {"id", "state", "job_dir"}

        code, out, _ = run_cli(capsys, "wait", started["id"], "--json")
        assert code == 0
        result = json.loads(out)
        assert result["state"] == "succeeded"

    def test_start_prompt_file(self, fake_agents, workdir, capsys, tmp_path):
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("prompt from file")
        args_file = tmp_path / "args.json"
        fake_agents(args_file=args_file)
        code, _, _ = run_cli(
            capsys, "run", "--agent", "codex", "--model", "m", "--prompt-file", prompt_file
        )
        assert code == 0
        assert json.loads(args_file.read_text())["stdin"] == "prompt from file"

    def test_start_prompt_file_stdin(self, fake_agents, workdir, capsys, monkeypatch, tmp_path):
        args_file = tmp_path / "args.json"
        fake_agents(args_file=args_file)
        monkeypatch.setattr("sys.stdin", io.StringIO("prompt from stdin"))
        code, _, _ = run_cli(
            capsys, "run", "--agent", "codex", "--model", "m", "--prompt-file", "-"
        )
        assert code == 0
        assert json.loads(args_file.read_text())["stdin"] == "prompt from stdin"

    def test_missing_prompt_is_usage_error(self, fake_agents, workdir, capsys):
        code, _, err = run_cli(capsys, "start", "--agent", "codex", "--model", "m")
        assert code == 2
        assert "--prompt" in err

    def test_run_success_prints_header_and_final_message(self, fake_agents, workdir, capsys):
        fake_agents(last_message="the final answer")
        code, out, _ = run_cli(
            capsys, "run", "--agent", "codex", "--model", "gpt-5", "--prompt", "hi"
        )
        assert code == 0
        lines = out.splitlines()
        assert re.fullmatch(
            r"\d{8}-\d{6}-[0-9a-f]{4} succeeded \(codex/gpt-5, [\d.]+s, exit 0\)", lines[0]
        )
        assert "the final answer" in "\n".join(lines[1:])

    def test_run_claude_agent(self, fake_agents, workdir, capsys):
        fake_agents(last_message="claude says hi")
        code, out, _ = run_cli(
            capsys, "run", "--agent", "claude", "--model", "sonnet", "--prompt", "hi"
        )
        assert code == 0
        assert "succeeded (claude/sonnet" in out

    def test_run_failed_exits_1(self, fake_agents, workdir, capsys):
        fake_agents(rc=1)
        code, out, _ = run_cli(capsys, "run", "--agent", "codex", "--model", "m", "--prompt", "hi")
        assert code == 1
        assert " failed (" in out.splitlines()[0]
        assert "exit 1)" in out.splitlines()[0]

    def test_run_timeout_exits_124(self, fake_agents, workdir, capsys, monkeypatch):
        fake_agents(sleep=30)
        monkeypatch.setenv("GIGACHAD_LITE_KILL_GRACE", "1")
        code, out, _ = run_cli(
            capsys, "run", "--agent", "codex", "--model", "m", "--prompt", "hi", "--timeout", "1"
        )
        assert code == 124
        assert " timed_out (" in out.splitlines()[0]

    def test_extra_args_after_double_dash_reach_agent(self, fake_agents, workdir, capsys, tmp_path):
        args_file = tmp_path / "args.json"
        fake_agents(args_file=args_file)
        code, _, _ = run_cli(
            capsys, "run", "--agent", "codex", "--model", "m", "--prompt", "hi", "--", "--extra-flag", "xyz"
        )
        assert code == 0
        argv = json.loads(args_file.read_text())["argv"]
        assert "--extra-flag" in argv
        assert argv[argv.index("--extra-flag") + 1] == "xyz"

    def test_read_only_mode_for_codex(self, fake_agents, workdir, capsys, tmp_path):
        args_file = tmp_path / "args.json"
        fake_agents(args_file=args_file)
        code, _, _ = run_cli(
            capsys, "run", "--agent", "codex", "--model", "m", "--prompt", "hi", "--mode", "read-only"
        )
        assert code == 0
        argv = json.loads(args_file.read_text())["argv"]
        assert argv[argv.index("-s") + 1] == "read-only"

    def test_cwd_option_sets_worker_directory(self, fake_agents, workdir, capsys, tmp_path):
        target = tmp_path / "elsewhere"
        target.mkdir()
        args_file = tmp_path / "args.json"
        fake_agents(args_file=args_file)
        code, _, _ = run_cli(
            capsys, "run", "--agent", "codex", "--model", "m", "--prompt", "hi", "--cwd", target
        )
        assert code == 0
        assert json.loads(args_file.read_text())["cwd"] == str(target.resolve())

    def test_status_with_id(self, fake_agents, workdir, capsys):
        fake_agents(sleep=30)
        job_id = start_job(capsys)
        code, out, _ = run_cli(capsys, "status", job_id)
        assert code == 0
        assert job_id in out
        run_cli(capsys, "cancel", job_id)

    def test_status_with_id_json(self, fake_agents, workdir, capsys):
        job_id = start_job(capsys)
        run_cli(capsys, "wait", job_id)
        code, out, _ = run_cli(capsys, "status", job_id, "--json")
        assert code == 0
        data = json.loads(out)
        assert data["id"] == job_id
        assert data["state"] == "succeeded"

    def test_status_without_id_lists_jobs_for_current_dir(self, fake_agents, workdir, capsys, tmp_path, monkeypatch):
        here = start_job(capsys)
        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.chdir(other)
        there = start_job(capsys)
        monkeypatch.chdir(workdir)

        code, out, _ = run_cli(capsys, "status")
        assert code == 0
        assert here in out
        assert there not in out
        assert "codex" in out
        assert "m" in out

    def test_list_current_dir_and_all(self, fake_agents, workdir, capsys, tmp_path, monkeypatch):
        here = start_job(capsys)
        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.chdir(other)
        there = start_job(capsys)
        monkeypatch.chdir(workdir)

        code, out, _ = run_cli(capsys, "list")
        assert code == 0
        assert here in out
        assert there not in out

        code, out, _ = run_cli(capsys, "list", "--all")
        assert code == 0
        assert here in out
        assert there in out

    def test_list_json(self, fake_agents, workdir, capsys):
        job_id = start_job(capsys)
        code, out, _ = run_cli(capsys, "list", "--json")
        assert code == 0
        assert [job["id"] for job in json.loads(out)] == [job_id]

    def test_wait_prints_result(self, fake_agents, workdir, capsys):
        fake_agents(last_message="waited message")
        job_id = start_job(capsys)
        code, out, _ = run_cli(capsys, "wait", job_id)
        assert code == 0
        assert out.splitlines()[0].startswith(f"{job_id} succeeded (codex/m,")
        assert "waited message" in out

    def test_wait_timeout_option(self, fake_agents, workdir, capsys):
        fake_agents(sleep=30)
        job_id = start_job(capsys)
        code, _, _ = run_cli(capsys, "wait", job_id, "--timeout", "1")
        assert code != 0
        run_cli(capsys, "cancel", job_id)

    def test_result_after_finish(self, fake_agents, workdir, capsys):
        fake_agents(last_message="result message")
        job_id = start_job(capsys)
        run_cli(capsys, "wait", job_id)
        code, out, _ = run_cli(capsys, "result", job_id)
        assert code == 0
        assert "result message" in out

    def test_result_not_finished_exits_3(self, fake_agents, workdir, capsys):
        fake_agents(sleep=30)
        job_id = start_job(capsys)
        code, _, _ = run_cli(capsys, "result", job_id)
        assert code == 3
        run_cli(capsys, "cancel", job_id)

    def test_unknown_job_exits_2(self, fake_agents, workdir, capsys):
        for command in ("status", "wait", "result", "logs", "cancel"):
            code, _, err = run_cli(capsys, command, "no-such-job")
            assert code == 2, command
            assert "no-such-job" in err and "job" in err.replace("no-such-job", "").lower(), command

    def test_cancel_then_result_exits_130(self, fake_agents, workdir, capsys):
        fake_agents(sleep=30)
        job_id = start_job(capsys)
        code, _, _ = run_cli(capsys, "cancel", job_id)
        assert code == 0

        code, out, _ = run_cli(capsys, "wait", job_id)
        assert code == 130
        assert f"{job_id} cancelled (" in out.splitlines()[0]

    def test_logs_and_tail(self, fake_agents, workdir, capsys):
        job_id = start_job(capsys, prompt="unique-prompt-text")
        run_cli(capsys, "wait", job_id)

        code, out, _ = run_cli(capsys, "logs", job_id)
        assert code == 0
        assert "codex working" in out

        code, tail, _ = run_cli(capsys, "logs", job_id, "--tail", "1")
        assert code == 0
        assert len(tail.splitlines()) == 1
        assert tail.strip() in out

    def test_recursion_guard_blocks_start_and_run(self, fake_agents, workdir, capsys, monkeypatch):
        monkeypatch.setenv("GIGACHAD_LITE_DEPTH", "1")
        for command in ("start", "run"):
            code, out, err = run_cli(
                capsys, command, "--agent", "codex", "--model", "m", "--prompt", "hi"
            )
            assert code == 2, command
            assert "GIGACHAD_LITE_MAX_DEPTH" in out + err

    def test_recursion_guard_allows_higher_max_depth(self, fake_agents, workdir, capsys, monkeypatch):
        monkeypatch.setenv("GIGACHAD_LITE_DEPTH", "1")
        monkeypatch.setenv("GIGACHAD_LITE_MAX_DEPTH", "2")
        code, _, _ = run_cli(capsys, "run", "--agent", "codex", "--model", "m", "--prompt", "hi")
        assert code == 0
