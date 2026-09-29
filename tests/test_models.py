"""Tests for the `models` subcommand and `gigachad_lite.models.list_models`."""

import json
from pathlib import Path

CLAUDE_ENTRIES = [
    {"agent": "claude", "id": "sonnet", "default": False},
    {"agent": "claude", "id": "opus", "default": False},
    {"agent": "claude", "id": "haiku", "default": False},
    {"agent": "claude", "id": "fable", "default": False},
]


def _which_both(name):
    return f"/usr/bin/{name}" if name in ("claude", "codex") else None


def _which_only(*present):
    return lambda name: f"/usr/bin/{name}" if name in present else None


def _codex_home(tmp_path: Path, cache=None, config=None, raw_cache=None) -> Path:
    home = tmp_path / "codex"
    home.mkdir()
    if raw_cache is not None:
        (home / "models_cache.json").write_text(raw_cache)
    elif cache is not None:
        (home / "models_cache.json").write_text(json.dumps(cache))
    if config is not None:
        (home / "config.toml").write_text(config)
    return home


class TestListModels:
    def test_claude_entries_in_order_when_only_claude_available(self, tmp_path):
        from gigachad_lite.models import list_models

        result = list_models(codex_home=tmp_path / "missing", which=_which_only("claude"))

        assert result == CLAUDE_ENTRIES

    def test_no_entries_when_no_cli_available(self, tmp_path):
        from gigachad_lite.models import list_models

        assert list_models(codex_home=tmp_path, which=_which_only()) == []

    def test_codex_entries_from_cache_preserve_file_order(self, tmp_path):
        from gigachad_lite.models import list_models

        home = _codex_home(
            tmp_path,
            cache={"models": [{"slug": "gpt-6-sol"}, {"slug": "gpt-6-luna"}, {"slug": "gpt-6-astra"}]},
        )

        result = list_models(codex_home=home, which=_which_only("codex"))

        assert result == [
            {"agent": "codex", "id": "gpt-6-sol", "default": False},
            {"agent": "codex", "id": "gpt-6-luna", "default": False},
            {"agent": "codex", "id": "gpt-6-astra", "default": False},
        ]

    def test_codex_cache_accepts_id_instead_of_slug(self, tmp_path):
        from gigachad_lite.models import list_models

        home = _codex_home(tmp_path, cache={"models": [{"id": "gpt-5.6-luna"}]})

        result = list_models(codex_home=home, which=_which_only("codex"))

        assert result == [{"agent": "codex", "id": "gpt-5.6-luna", "default": False}]

    def test_default_codex_model_marked_from_config_toml(self, tmp_path):
        from gigachad_lite.models import list_models

        home = _codex_home(
            tmp_path,
            cache={"models": [{"slug": "gpt-6-sol"}, {"slug": "gpt-6-luna"}]},
            config='approval_policy = "never"\nmodel = "gpt-6-luna"\n',
        )

        result = list_models(codex_home=home, which=_which_only("codex"))

        assert result == [
            {"agent": "codex", "id": "gpt-6-sol", "default": False},
            {"agent": "codex", "id": "gpt-6-luna", "default": True},
        ]

    def test_no_default_when_config_toml_missing(self, tmp_path):
        from gigachad_lite.models import list_models

        home = _codex_home(tmp_path, cache={"models": [{"slug": "gpt-6-sol"}]})

        result = list_models(codex_home=home, which=_which_only("codex"))

        assert result == [{"agent": "codex", "id": "gpt-6-sol", "default": False}]

    def test_missing_cache_yields_no_codex_entries(self, tmp_path):
        from gigachad_lite.models import list_models

        home = _codex_home(tmp_path, config='model = "gpt-6-luna"\n')

        result = list_models(codex_home=home, which=_which_both)

        assert result == CLAUDE_ENTRIES

    def test_corrupt_cache_yields_no_codex_entries(self, tmp_path):
        from gigachad_lite.models import list_models

        home = _codex_home(tmp_path, raw_cache="{not json")

        result = list_models(codex_home=home, which=_which_both)

        assert result == CLAUDE_ENTRIES

    def test_claude_entries_precede_codex_entries(self, tmp_path):
        from gigachad_lite.models import list_models

        home = _codex_home(tmp_path, cache={"models": [{"slug": "gpt-6-luna"}]})

        result = list_models(codex_home=home, which=_which_both)

        assert result == [*CLAUDE_ENTRIES, {"agent": "codex", "id": "gpt-6-luna", "default": False}]

    def test_codex_home_defaults_to_codex_home_env(self, tmp_path, monkeypatch):
        from gigachad_lite.models import list_models

        home = _codex_home(tmp_path, cache={"models": [{"slug": "gpt-6-astra"}]})
        monkeypatch.setenv("CODEX_HOME", str(home))

        result = list_models(which=_which_only("codex"))

        assert result == [{"agent": "codex", "id": "gpt-6-astra", "default": False}]

    def test_codex_home_defaults_to_dot_codex_in_home(self, tmp_path, monkeypatch):
        from gigachad_lite.models import list_models

        monkeypatch.delenv("CODEX_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        dot_codex = tmp_path / ".codex"
        dot_codex.mkdir()
        (dot_codex / "models_cache.json").write_text(json.dumps({"models": [{"slug": "gpt-6-sol"}]}))

        result = list_models(which=_which_only("codex"))

        assert result == [{"agent": "codex", "id": "gpt-6-sol", "default": False}]


class TestModelsCommand:
    def _run(self, capsys, monkeypatch, tmp_path, *args, cache=None, config=None):
        from gigachad_lite import cli

        home = _codex_home(
            tmp_path,
            cache=cache if cache is not None else {"models": [{"slug": "gpt-6-sol"}, {"slug": "gpt-6-luna"}]},
            config=config if config is not None else 'model = "gpt-6-luna"\n',
        )
        monkeypatch.setenv("CODEX_HOME", str(home))
        code = cli.main(["models", *args])
        return code, capsys.readouterr().out

    def test_json_flag_prints_json_list(self, fake_agents, capsys, monkeypatch, tmp_path):
        code, out = self._run(capsys, monkeypatch, tmp_path, "--json")

        assert code == 0
        assert json.loads(out) == [
            *CLAUDE_ENTRIES,
            {"agent": "codex", "id": "gpt-6-sol", "default": False},
            {"agent": "codex", "id": "gpt-6-luna", "default": True},
        ]

    def test_agent_filter_limits_json_to_codex(self, fake_agents, capsys, monkeypatch, tmp_path):
        code, out = self._run(capsys, monkeypatch, tmp_path, "--agent", "codex", "--json")

        assert code == 0
        assert json.loads(out) == [
            {"agent": "codex", "id": "gpt-6-sol", "default": False},
            {"agent": "codex", "id": "gpt-6-luna", "default": True},
        ]

    def test_text_output_one_line_per_model_with_default_starred(self, fake_agents, capsys, monkeypatch, tmp_path):
        code, out = self._run(capsys, monkeypatch, tmp_path)

        assert code == 0
        lines = [ln for ln in out.splitlines() if ln.strip()]
        for model_id in ("sonnet", "opus", "haiku", "fable", "gpt-6-sol", "gpt-6-luna"):
            assert len([ln for ln in lines if model_id in ln]) == 1
        starred = [ln for ln in lines if "*" in ln]
        assert len(starred) == 1
        assert "gpt-6-luna" in starred[0]

    def test_text_output_groups_by_agent(self, fake_agents, capsys, monkeypatch, tmp_path):
        code, out = self._run(capsys, monkeypatch, tmp_path)

        assert code == 0
        assert out.index("claude:") < out.index("sonnet") < out.index("fable") < out.index("codex:")
        assert out.index("codex:") < out.index("gpt-6-sol")

    def test_agent_filter_excludes_other_agent_in_text(self, fake_agents, capsys, monkeypatch, tmp_path):
        code, out = self._run(capsys, monkeypatch, tmp_path, "--agent", "codex")

        assert code == 0
        assert "gpt-6-sol" in out
        assert "sonnet" not in out
