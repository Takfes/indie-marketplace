import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "plugins" / "essentials" / "scripts" / "cli-startup-check.py"

# A login shell that reports nothing and exits cleanly: the hook's probe runs
# to completion, so a command missing from PATH is genuinely missing. Tests
# that need the probe to *find* something override SHELL with a stub.
SILENT_SHELL = "/bin/sh"


def _write_catalog(install_dir: Path, entries: list[dict]) -> None:
    (install_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (install_dir / ".claude-plugin" / "catalog.json").write_text(json.dumps(entries))


def _write_installed_plugins(claude_dir: Path, plugins: dict[str, Path]) -> None:
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "settings.json").write_text(json.dumps({"enabledPlugins": {f"{name}@test": True for name in plugins}}))
    (claude_dir / "plugins").mkdir(exist_ok=True)
    data = {
        "version": 2,
        "plugins": {
            f"{name}@test": [{"scope": "user", "installPath": str(path), "lastUpdated": "2026-01-01T00:00:00Z"}]
            for name, path in plugins.items()
        },
    }
    (claude_dir / "plugins" / "installed_plugins.json").write_text(json.dumps(data))


def cli_entry(command: str, source: str = "mcp", **extra) -> dict:
    entry = {
        "name": command,
        "type": "cli",
        "command": command,
        "install": None,
        "manual": None,
        "source": source,
        "required_by": [],
        "env": [],
    }
    entry.update(extra)
    return entry


def make_bin(path_dir: Path, name: str) -> Path:
    """A stub executable, standing in for an installed binary."""
    path_dir.mkdir(parents=True, exist_ok=True)
    binary = path_dir / name
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    return binary


def make_probe_shell(tmp_path: Path, resolves: dict[str, str], *, hang: bool = False, fail: bool = False) -> Path:
    """A stand-in for the user's login shell, so the probe is deterministic
    and never touches the developer's own dotfiles. It answers `$SHELL -lc
    <script>` by printing the hook's own `<command>\\tab<path>` lines for
    `resolves`, plus the sentinel that marks a completed probe."""
    shell = tmp_path / "probe-shell.sh"
    if hang:
        body = "sleep 30\n"
    elif fail:
        # Exits before the sentinel: a probe that did not run to completion.
        body = "echo 'profile blew up' >&2\nexit 1\n"
    else:
        lines = "".join(f"printf '{name}\\t{path}\\n'\n" for name, path in resolves.items())
        body = lines + "printf '__indie_probe_done__\\n'\n"
    shell.write_text("#!/bin/sh\n" + body)
    shell.chmod(0o755)
    return shell


def run_hook(claude_dir: Path, path_dirs: list[Path], *, shell: str = SILENT_SHELL, extra_env: dict | None = None):
    env = {
        "PATH": os.pathsep.join(str(p) for p in path_dirs),
        "HOME": str(claude_dir.parent),
        "CLAUDE_CONFIG_DIR": str(claude_dir),
        "SHELL": shell,
    }
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"hook_event_name": "SessionStart"}),
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def context_of(result) -> str:
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


@pytest.fixture
def fixture(tmp_path):
    """(claude_dir, install_dir, path_dir) — one enabled+installed plugin
    'alpha' with an empty catalog, and an empty fake PATH directory."""
    claude_dir = tmp_path / "claude_config"
    install_dir = tmp_path / "plugins" / "alpha"
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()
    _write_catalog(install_dir, [])
    _write_installed_plugins(claude_dir, {"alpha": install_dir})
    return claude_dir, install_dir, path_dir


# ---------------------------------------------------------------------------
# The two headline behaviours
# ---------------------------------------------------------------------------


def test_missing_cli_nudges_naming_plugin_and_tool(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(
        install_dir,
        [cli_entry("dockerish", required_by=["pgquery", "dbtools"], install="brew install --cask docker")],
    )
    result = run_hook(claude_dir, [path_dir])
    assert result.returncode == 0
    ctx = context_of(result)
    assert json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "alpha/dockerish" in ctx
    assert "pgquery" in ctx and "dbtools" in ctx
    assert "brew install --cask docker" in ctx
    assert "INDIE_MARKETPLACE_SKIP_CLI_CHECK" in ctx


def test_all_present_is_silent(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])
    make_bin(path_dir, "toolish")
    result = run_hook(claude_dir, [path_dir])
    assert result.returncode == 0
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# PATH divergence — the failure the whole design exists to avoid
# ---------------------------------------------------------------------------


def test_binary_invisible_to_which_but_found_by_the_probe_is_silent(fixture, tmp_path):
    """shutil.which sees a bare launchd-style PATH; the user's login shell
    sees /opt/homebrew/bin. Finding it there must not nudge."""
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])
    elsewhere = make_bin(tmp_path / "homebrew_bin", "toolish")
    shell = make_probe_shell(tmp_path, {"toolish": str(elsewhere)})

    result = run_hook(claude_dir, [path_dir], shell=str(shell))
    assert result.returncode == 0
    assert result.stdout == ""


def test_probe_that_errors_is_silent(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])
    shell = make_probe_shell(tmp_path, {}, fail=True)

    result = run_hook(claude_dir, [path_dir], shell=str(shell))
    assert result.returncode == 0
    assert result.stdout == ""


def test_probe_that_times_out_is_silent(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])
    shell = make_probe_shell(tmp_path, {}, hang=True)

    result = run_hook(claude_dir, [path_dir], shell=str(shell))
    assert result.returncode == 0
    assert result.stdout == ""


def test_unusable_shell_is_silent(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])

    result = run_hook(claude_dir, [path_dir], shell=str(tmp_path / "no-such-shell"))
    assert result.returncode == 0
    assert result.stdout == ""


def test_probe_reporting_the_command_absent_still_nudges(fixture, tmp_path):
    """The other side of the rule: a probe that ran to completion and found
    nothing is an answer, not an uncertainty."""
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])
    shell = make_probe_shell(tmp_path, {"toolish": ""})

    result = run_hook(claude_dir, [path_dir], shell=str(shell))
    assert result.returncode == 0
    assert "alpha/toolish" in context_of(result)


# ---------------------------------------------------------------------------
# Plugin bin/ shadowing
# ---------------------------------------------------------------------------


def test_launcher_in_a_plugins_own_bin_is_not_proof_of_presence(fixture, tmp_path):
    """build.py names a scoped launcher exactly after the command it wraps,
    and Claude Code puts every plugin's bin/ on PATH."""
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])
    make_bin(install_dir / "bin", "toolish")

    result = run_hook(claude_dir, [install_dir / "bin", path_dir])
    assert result.returncode == 0
    assert "alpha/toolish" in context_of(result)


def test_probe_hit_inside_a_plugins_own_bin_is_also_rejected(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])
    launcher = make_bin(install_dir / "bin", "toolish")
    shell = make_probe_shell(tmp_path, {"toolish": str(launcher)})

    result = run_hook(claude_dir, [path_dir], shell=str(shell))
    assert result.returncode == 0
    assert "alpha/toolish" in context_of(result)


# ---------------------------------------------------------------------------
# Which entries the nudge covers
# ---------------------------------------------------------------------------


def test_lazily_required_deps_cli_never_nudges(fixture, tmp_path):
    """Decision (b): source: "deps" fails loudly at first use on its own —
    the doctor reports it, the nudge does not."""
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish", source="deps")])
    result = run_hook(claude_dir, [path_dir])
    assert result.returncode == 0
    assert result.stdout == ""


def test_non_cli_catalog_entries_are_ignored(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(
        install_dir,
        [{"name": "svc", "type": "mcp", "env": [{"name": "REQ", "required": True}]}],
    )
    result = run_hook(claude_dir, [path_dir])
    assert result.returncode == 0
    assert result.stdout == ""


def test_missing_tool_with_no_hint_says_so(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])
    result = run_hook(claude_dir, [path_dir])
    assert "no declared install hint" in context_of(result)


def test_manual_url_is_shown_when_there_is_no_install_command(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish", manual="https://example.invalid/install")])
    assert "https://example.invalid/install" in context_of(run_hook(claude_dir, [path_dir]))


def test_never_runs_an_install_command(fixture, tmp_path):
    """The install hint is text in the report, never something executed."""
    claude_dir, install_dir, path_dir = fixture
    marker = tmp_path / "installed.marker"
    _write_catalog(install_dir, [cli_entry("toolish", install=f"touch {marker}")])
    result = run_hook(claude_dir, [path_dir])
    assert str(marker) in context_of(result)
    assert not marker.exists()


# ---------------------------------------------------------------------------
# Opt-out and resilience — never blocks session start
# ---------------------------------------------------------------------------


def test_skip_env_var_silences_the_check(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])
    result = run_hook(claude_dir, [path_dir], extra_env={"INDIE_MARKETPLACE_SKIP_CLI_CHECK": "1"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_one_malformed_catalog_does_not_silence_other_plugins(tmp_path):
    claude_dir = tmp_path / "claude_config"
    broken_dir = tmp_path / "plugins" / "broken"
    good_dir = tmp_path / "plugins" / "good"
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()

    (broken_dir / ".claude-plugin").mkdir(parents=True)
    (broken_dir / ".claude-plugin" / "catalog.json").write_text("{not valid json")
    _write_catalog(good_dir, [cli_entry("toolish")])
    _write_installed_plugins(claude_dir, {"broken": broken_dir, "good": good_dir})

    result = run_hook(claude_dir, [path_dir])
    assert result.returncode == 0
    assert "good/toolish" in context_of(result)


def test_missing_installed_plugins_json_is_silent_not_error(tmp_path):
    claude_dir = tmp_path / "claude_config"
    claude_dir.mkdir()
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()
    result = run_hook(claude_dir, [path_dir])
    assert result.returncode == 0
    assert result.stdout == ""


def test_disabled_plugin_is_never_checked(tmp_path):
    claude_dir = tmp_path / "claude_config"
    install_dir = tmp_path / "plugins" / "alpha"
    path_dir = tmp_path / "fake_path"
    path_dir.mkdir()
    _write_catalog(install_dir, [cli_entry("toolish")])
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(json.dumps({"enabledPlugins": {"alpha@test": False}}))
    (claude_dir / "plugins").mkdir()
    (claude_dir / "plugins" / "installed_plugins.json").write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "alpha@test": [{"scope": "user", "installPath": str(install_dir), "lastUpdated": "2026-01-01T00:00:00Z"}]
                },
            }
        )
    )
    result = run_hook(claude_dir, [path_dir])
    assert result.returncode == 0
    assert result.stdout == ""


def test_malformed_stdin_is_silent_not_error(fixture, tmp_path):
    claude_dir, install_dir, path_dir = fixture
    _write_catalog(install_dir, [cli_entry("toolish")])
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not valid json",
        env={"PATH": str(path_dir), "HOME": str(tmp_path), "CLAUDE_CONFIG_DIR": str(claude_dir), "SHELL": SILENT_SHELL},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0
