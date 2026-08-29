import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_cli_startup_hook import cli_entry, make_bin, make_probe_shell
from tests.test_secrets_server import BUNDLES, SKILL_SRC, run_build

SILENT_SHELL = "/bin/sh"


@pytest.fixture
def doctor(project, tmp_path):
    """(run, claude_dir, plugins_root) — `run` invokes the *generated*
    deps.py (the one shipped inside the built plugin, next to server.py and
    indie_store.py) against a fake CLAUDE_CONFIG_DIR and a fake PATH.

    Tests declare installed plugins by calling `install(...)` with the
    catalog entries they want; nothing here depends on the real machine."""
    (project / "bundles.yaml").write_text(BUNDLES)
    (project / "skills").mkdir(exist_ok=True)
    shutil.copytree(SKILL_SRC, project / "skills" / "secrets-manager")
    result = run_build(project)
    assert result.returncode == 0, result.stdout

    deps_py = project / "plugins" / "essentials" / "skills" / "secrets-manager" / "deps.py"
    claude_dir = tmp_path / "claude_config"
    (claude_dir / "plugins").mkdir(parents=True)
    plugins_root = tmp_path / "installed"

    def install(catalogs: dict[str, list[dict]]) -> None:
        (claude_dir / "settings.json").write_text(
            json.dumps({"enabledPlugins": {f"{name}@test": True for name in catalogs}})
        )
        records = {}
        for name, entries in catalogs.items():
            install_dir = plugins_root / name
            (install_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (install_dir / ".claude-plugin" / "catalog.json").write_text(json.dumps(entries))
            records[f"{name}@test"] = [
                {"scope": "user", "installPath": str(install_dir), "lastUpdated": "2026-01-01T00:00:00Z"}
            ]
        (claude_dir / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": records})
        )

    def run(path_dirs: list[Path], *, shell: str = SILENT_SHELL) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(deps_py), "doctor"],
            env={
                "PATH": os.pathsep.join(str(p) for p in path_dirs),
                "HOME": str(tmp_path / "home"),
                "CLAUDE_CONFIG_DIR": str(claude_dir),
                "INDIE_MARKETPLACE_HOME": str(tmp_path / "store"),
                "SHELL": shell,
            },
            capture_output=True,
            text=True,
            timeout=30,
        )

    return install, run, plugins_root


def test_missing_tool_is_reported_with_its_install_hint_and_exit_1(doctor, tmp_path):
    install, run, _ = doctor
    install({"database": [cli_entry("dockerish", required_by=["pgquery"], install="brew install --cask docker")]})
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()

    result = run([path_dir])
    assert result.returncode == 1
    assert "dockerish" in result.stdout
    assert "missing" in result.stdout
    assert "database (pgquery)" in result.stdout
    assert "brew install --cask docker" in result.stdout


def test_everything_present_exits_0(doctor, tmp_path):
    install, run, _ = doctor
    install({"database": [cli_entry("toolish")]})
    path_dir = tmp_path / "fake_path"
    make_bin(path_dir, "toolish")

    result = run([path_dir])
    assert result.returncode == 0
    assert "every declared CLI tool is present" in result.stdout
    assert "present" in result.stdout


def test_one_command_across_plugins_is_one_deduped_line(doctor, tmp_path):
    """npx is one line naming three plugins, not three lines."""
    install, run, _ = doctor
    install(
        {
            "pythonista": [cli_entry("npxish", required_by=["context7"])],
            "azdevops": [cli_entry("npxish", required_by=["azcloud", "azkusto"])],
            "web-search": [cli_entry("npxish", required_by=["exa"])],
        }
    )
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()

    result = run([path_dir])
    assert result.returncode == 1
    npx_lines = [line for line in result.stdout.splitlines() if "npxish" in line]
    assert len(npx_lines) == 1
    for plugin in ("pythonista", "azdevops", "web-search"):
        assert plugin in npx_lines[0]
    assert "context7" in npx_lines[0] and "azcloud, azkusto" in npx_lines[0] and "exa" in npx_lines[0]


def test_eager_and_lazy_tools_are_grouped_eager_first(doctor, tmp_path):
    install, run, _ = doctor
    install(
        {
            "database": [cli_entry("dockerish", required_by=["pgquery"])],
            "web-search": [cli_entry("firecrawlish", source="deps")],
        }
    )
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()

    result = run([path_dir])
    out = result.stdout
    assert out.index("Required at session start") < out.index("Required on first use")
    assert out.index("dockerish") < out.index("firecrawlish")


def test_lazy_only_tools_are_still_reported(doctor, tmp_path):
    """The nudge skips source: "deps"; the doctor must not."""
    install, run, _ = doctor
    install({"web-search": [cli_entry("firecrawlish", source="deps", install="npm i -g firecrawl-cli")]})
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()

    result = run([path_dir])
    assert result.returncode == 1
    assert "firecrawlish" in result.stdout
    assert "npm i -g firecrawl-cli" in result.stdout


def test_binary_found_only_via_the_login_shell_counts_as_present(doctor, tmp_path):
    install, run, _ = doctor
    install({"database": [cli_entry("toolish")]})
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()
    elsewhere = make_bin(tmp_path / "homebrew_bin", "toolish")
    shell = make_probe_shell(tmp_path, {"toolish": str(elsewhere)})

    result = run([path_dir], shell=str(shell))
    assert result.returncode == 0
    assert "every declared CLI tool is present" in result.stdout


def test_probe_failure_never_reports_a_tool_missing(doctor, tmp_path):
    install, run, _ = doctor
    install({"database": [cli_entry("toolish")]})
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()
    shell = make_probe_shell(tmp_path, {}, fail=True)

    result = run([path_dir], shell=str(shell))
    assert result.returncode == 0
    assert "every declared CLI tool is present" in result.stdout


def test_launcher_in_a_plugins_own_bin_is_reported_missing(doctor, tmp_path):
    install, run, plugins_root = doctor
    install({"browser": [cli_entry("toolish", source="deps")]})
    bin_dir = plugins_root / "browser" / "bin"
    make_bin(bin_dir, "toolish")
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()

    result = run([bin_dir, path_dir])
    assert result.returncode == 1
    assert "toolish" in result.stdout
    assert "missing" in result.stdout


def test_daemon_caveat_is_stated(doctor, tmp_path):
    install, run, _ = doctor
    install({"database": [cli_entry("toolish")]})
    path_dir = tmp_path / "fake_path"
    make_bin(path_dir, "toolish")

    assert "daemon is running" in run([path_dir]).stdout


def test_never_runs_an_install_command(doctor, tmp_path):
    install, run, _ = doctor
    marker = tmp_path / "installed.marker"
    install({"database": [cli_entry("toolish", install=f"touch {marker}")]})
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()

    result = run([path_dir])
    assert str(marker) in result.stdout
    assert not marker.exists()


def test_malformed_catalog_does_not_hide_other_plugins(doctor, tmp_path):
    install, run, plugins_root = doctor
    install({"broken": [], "good": [cli_entry("toolish")]})
    (plugins_root / "broken" / ".claude-plugin" / "catalog.json").write_text("{not valid json")
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()

    result = run([path_dir])
    assert result.returncode == 1
    assert "good" in result.stdout


def test_no_declared_clis_exits_0(doctor, tmp_path):
    install, run, _ = doctor
    install({"alpha": [{"name": "svc", "type": "mcp", "env": []}]})
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()

    result = run([path_dir])
    assert result.returncode == 0
    assert "no installed, enabled plugin declares a CLI tool" in result.stdout
