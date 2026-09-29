import json
import os
import subprocess
from pathlib import Path

import pytest


class TestGetAdapter:
    def test_known_agents(self):
        from gigachad_lite.adapters import get_adapter

        assert get_adapter("codex") is not None
        assert get_adapter("claude") is not None

    def test_unknown_agent_lists_supported(self):
        from gigachad_lite.adapters import get_adapter

        with pytest.raises(ValueError) as exc:
            get_adapter("gemini")
        assert "codex" in str(exc.value)
        assert "claude" in str(exc.value)


class TestCodexBuild:
    def test_write_mode_argv(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        cmd = get_adapter("codex").build("gpt-5", "write", tmp_path, ["--foo"], {})
        assert cmd.argv == [
            "codex", "exec", "-m", "gpt-5", "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "-o", str(tmp_path / "last-message.txt"), "--foo", "-",
        ]

    def test_read_only_mode_argv(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        cmd = get_adapter("codex").build("gpt-5", "read-only", tmp_path, [], {})
        assert cmd.argv == [
            "codex", "exec", "-m", "gpt-5", "--skip-git-repo-check", "-s", "read-only",
            "-o", str(tmp_path / "last-message.txt"), "-",
        ]

    @pytest.mark.parametrize(
        "alias,full",
        [("luna", "gpt-6-luna"), ("sol", "gpt-6-sol"), ("astra", "gpt-6-astra"), ("other-model", "other-model")],
    )
    def test_model_aliases(self, tmp_path, alias, full):
        from gigachad_lite.adapters import get_adapter

        cmd = get_adapter("codex").build(alias, "write", tmp_path, [], {})
        assert cmd.argv[cmd.argv.index("-m") + 1] == full

    def test_prompt_not_in_argv(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        cmd = get_adapter("codex").build("gpt-5", "write", tmp_path, [], {})
        assert cmd.argv[-1] == "-"


class TestClaudeBuild:
    def test_write_mode_argv(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        cmd = get_adapter("claude").build("sonnet", "write", tmp_path, ["--foo"], {})
        assert cmd.argv == [
            "claude", "-p", "--model", "sonnet", "--output-format", "json",
            "--dangerously-skip-permissions", "--foo",
        ]


class TestBuildEnv:
    @pytest.mark.parametrize("agent", ["codex", "claude"])
    def test_env_sanitised(self, tmp_path, agent):
        from gigachad_lite.adapters import get_adapter

        env = {"CLAUDECODE": "1", "GIGACHAD_LITE_DEPTH": "2", "KEEP": "me"}
        cmd = get_adapter(agent).build("m", "write", tmp_path, [], env)
        assert "CLAUDECODE" not in cmd.env
        assert cmd.env["GIGACHAD_AGENT_CHILD"] == "1"
        assert cmd.env["GIGACHAD_LITE_DEPTH"] == "3"
        assert cmd.env["KEEP"] == "me"
        assert "CLAUDECODE" in env  # input not mutated

    @pytest.mark.parametrize("agent", ["codex", "claude"])
    def test_depth_defaults_to_one(self, tmp_path, agent):
        from gigachad_lite.adapters import get_adapter

        cmd = get_adapter(agent).build("m", "write", tmp_path, [], {})
        assert cmd.env["GIGACHAD_LITE_DEPTH"] == "1"


class TestCodexParse:
    def test_reads_last_message_file_not_stdout(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        (tmp_path / "last-message.txt").write_text("  final answer \n")
        result = get_adapter("codex").parse(tmp_path, "echo TASK_COMPLETE\n")
        assert result.final_message == "final answer"
        assert result.is_error is False

    def test_missing_file_gives_empty_message(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        result = get_adapter("codex").parse(tmp_path, "TASK_COMPLETE")
        assert result.final_message == ""

    def test_fake_codex_end_to_end(self, fake_agents, tmp_path):
        from gigachad_lite.adapters import get_adapter

        fake_agents(last_message="the real answer")
        adapter = get_adapter("codex")
        cmd = adapter.build("gpt-5", "write", tmp_path, [], dict(os.environ))
        proc = subprocess.run(
            cmd.argv, input="please finish with TASK_COMPLETE", env=cmd.env,
            capture_output=True, text=True, check=False,
        )
        assert "TASK_COMPLETE" in proc.stdout
        assert adapter.parse(tmp_path, proc.stdout).final_message == "the real answer"


class TestClaudeParse:
    def test_parses_json_result(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        stdout = json.dumps(
            {"type": "result", "result": "hello", "is_error": False, "session_id": "sess-1", "total_cost_usd": 0.01}
        )
        result = get_adapter("claude").parse(tmp_path, stdout)
        assert result.final_message == "hello"
        assert result.is_error is False
        assert result.extras["session_id"] == "sess-1"
        assert result.extras["total_cost_usd"] == 0.01

    def test_is_error_propagated(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        stdout = json.dumps({"type": "result", "result": "boom", "is_error": True})
        assert get_adapter("claude").parse(tmp_path, stdout).is_error is True

    def test_bad_json(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        result = get_adapter("claude").parse(tmp_path, "not json")
        assert result.final_message == ""
        assert result.is_error is True
        assert "parse_error" in result.extras

    def test_fake_claude_end_to_end(self, fake_agents, tmp_path):
        from gigachad_lite.adapters import get_adapter

        fake_agents(last_message="claude says hi")
        adapter = get_adapter("claude")
        cmd = adapter.build("sonnet", "write", tmp_path, [], dict(os.environ))
        proc = subprocess.run(cmd.argv, input="hi", env=cmd.env, capture_output=True, text=True, check=False)
        assert adapter.parse(Path(tmp_path), proc.stdout).final_message == "claude says hi"


class TestClaudeReadOnlyLockdown:
    def test_read_only_argv_restricts_tools_and_mcp(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        cmd = get_adapter("claude").build("sonnet", "read-only", tmp_path, ["--foo"], {})
        assert cmd.argv == [
            "claude", "-p", "--model", "sonnet", "--output-format", "json",
            "--tools", "Read,Glob,Grep", "--strict-mcp-config", "--foo",
        ]

    def test_read_only_has_no_permission_bypass_or_denylist(self, tmp_path):
        from gigachad_lite.adapters import get_adapter

        argv = get_adapter("claude").build("sonnet", "read-only", tmp_path, [], {}).argv
        assert "--dangerously-skip-permissions" not in argv
        assert "--disallowedTools" not in argv
