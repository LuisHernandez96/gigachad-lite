import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from gigachad_lite import __version__

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_MANIFESTS = [".claude-plugin/plugin.json", ".codex-plugin/plugin.json"]
MARKETPLACES = [".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"]
BIN_WRAPPERS = ["bin/gigachad-lite", "bin/gcl"]


def load(relative):
    return json.loads((ROOT / relative).read_text())


@pytest.mark.parametrize("manifest", PLUGIN_MANIFESTS)
def test_plugin_manifest_matches_package(manifest):
    data = load(manifest)
    assert data["name"] == "gigachad-lite"
    assert data["version"] == __version__
    assert (ROOT / data["skills"]).is_dir()


@pytest.mark.parametrize("marketplace", MARKETPLACES)
def test_marketplace_lists_plugin(marketplace):
    data = load(marketplace)
    assert data["name"] == "gigachad-lite"
    assert [plugin["name"] for plugin in data["plugins"]] == ["gigachad-lite"]
    assert (ROOT / data["plugins"][0]["source"]).is_dir()


@pytest.mark.parametrize("wrapper", BIN_WRAPPERS)
def test_bin_wrapper_runs_without_install(wrapper):
    path = ROOT / wrapper
    assert os.access(path, os.X_OK)
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run([str(path), "--version"], capture_output=True, text=True, env=env, check=False)
    assert result.returncode == 0
    assert result.stdout.strip() == f"gigachad-lite {__version__}"


def test_bin_wrapper_follows_symlinks(tmp_path):
    link = tmp_path / "gcl"
    link.symlink_to(ROOT / "bin" / "gcl")
    result = subprocess.run([str(link), "--version"], capture_output=True, text=True, check=False)
    assert result.returncode == 0


def test_skill_frontmatter_and_body():
    text = (ROOT / "skills/delegate/SKILL.md").read_text()
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    assert match
    frontmatter, body = match.groups()
    assert re.search(r"^name: delegate$", frontmatter, re.MULTILINE)
    assert re.search(r"^description: \S", frontmatter, re.MULTILINE)
    description = re.search(r"^description: (.*)$", frontmatter, re.MULTILINE).group(1)
    assert len(description) <= 600
    for phrase in ("astra", "sonnet", "gcl models", "subagent"):
        assert phrase in description
    assert "Never tell the user a model is unavailable" in body
    for phrase in ("gcl start", "gcl wait", "git diff", "--mode read-only", "--prompt-file", '--prompt "', "--prompt-file -"):
        assert phrase in body


def test_readme_documents_install_and_every_subcommand():
    text = (ROOT / "README.md").read_text()
    assert "/plugin marketplace add LuisHernandez96/gigachad-lite" in text
    assert "codex plugin marketplace add LuisHernandez96/gigachad-lite" in text
    for command in ("start", "run", "status", "wait", "result", "logs", "cancel", "list", "models"):
        assert f"`{command}`" in text


def test_ci_script_is_local_and_executable():
    script = ROOT / "scripts/ci.sh"
    assert os.access(script, os.X_OK)
    text = script.read_text()
    assert "ruff check src tests" in text
    assert "pytest" in text
    assert not (ROOT / ".github/workflows").exists()


def test_contributor_policy_files():
    assert "@LuisHernandez96" in (ROOT / ".github/CODEOWNERS").read_text()
    assert "scripts/ci.sh" in (ROOT / "CONTRIBUTING.md").read_text()
