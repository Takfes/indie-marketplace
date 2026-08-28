import json
import subprocess
import sys
from pathlib import Path

import pytest

from shared import indie_store

HOOK = Path(__file__).resolve().parent.parent / "plugins" / "essentials" / "scripts" / "secrets-startup-check.py"


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


def _write_profiles(store_home: Path, data: dict) -> None:
    store_home.mkdir(parents=True, exist_ok=True)
    (store_home / "profiles.json").write_text(json.dumps(data))


def run_hook(claude_dir: Path, store_home: Path, cwd: Path, hook_input: dict | None = None) -> subprocess.CompletedProcess:
    payload = json.dumps(hook_input if hook_input is not None else {"cwd": str(cwd), "hook_event_name": "SessionStart"})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(Path.home()),
            "CLAUDE_CONFIG_DIR": str(claude_dir),
            indie_store.STORE_ENV_VAR: str(store_home),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.fixture
def fixture(tmp_path):
    """(claude_dir, store_home, install_dir) — a single enabled+installed
    plugin 'alpha' with an empty catalog by default; tests populate it."""
    claude_dir = tmp_path / "claude_config"
    store_home = tmp_path / "store"
    install_dir = tmp_path / "plugins" / "alpha"
    _write_catalog(install_dir, [])
    _write_installed_plugins(claude_dir, {"alpha": install_dir})
    return claude_dir, store_home, install_dir


def test_partial_tool_nudges_with_missing_var_named(fixture, tmp_path):
    claude_dir, store_home, install_dir = fixture
    _write_catalog(
        install_dir,
        [{"name": "svc", "type": "mcp", "env": [{"name": "REQ_1", "required": True}, {"name": "REQ_2", "required": True}]}],
    )
    _write_profiles(store_home, {"version": 1, "profiles": {"base": {"projects": [], "values": {"REQ_1": "x"}}}})

    result = run_hook(claude_dir, store_home, tmp_path)
    assert result.returncode == 0
    output = json.loads(result.stdout)
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "alpha/svc" in ctx
    assert "REQ_2" in ctx
    assert "REQ_1" not in ctx.split("missing:")[1].split("\n")[0]
    assert "secrets-manager" in ctx
    assert "essentials" in ctx


def test_fully_configured_tool_is_silent(fixture, tmp_path):
    claude_dir, store_home, install_dir = fixture
    _write_catalog(
        install_dir,
        [{"name": "svc", "type": "mcp", "env": [{"name": "REQ_1", "required": True}]}],
    )
    _write_profiles(store_home, {"version": 1, "profiles": {"base": {"projects": [], "values": {"REQ_1": "x"}}}})

    result = run_hook(claude_dir, store_home, tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""


def test_entirely_unconfigured_tool_is_silent(fixture, tmp_path):
    claude_dir, store_home, install_dir = fixture
    _write_catalog(
        install_dir,
        [{"name": "svc", "type": "mcp", "env": [{"name": "REQ_1", "required": True}, {"name": "REQ_2", "required": True}]}],
    )
    # no profiles.json at all — nothing set anywhere
    result = run_hook(claude_dir, store_home, tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""


def test_tool_with_no_required_vars_never_nudges(fixture, tmp_path):
    claude_dir, store_home, install_dir = fixture
    _write_catalog(
        install_dir,
        [{"name": "svc", "type": "mcp", "env": [{"name": "OPT_1", "required": False}]}],
    )
    result = run_hook(claude_dir, store_home, tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""


def test_multiple_partial_tools_each_named(fixture, tmp_path):
    claude_dir, store_home, install_dir = fixture
    _write_catalog(
        install_dir,
        [
            {"name": "svc-a", "type": "mcp", "env": [{"name": "A_1", "required": True}, {"name": "A_2", "required": True}]},
            {"name": "svc-b", "type": "mcp", "env": [{"name": "B_1", "required": True}, {"name": "B_2", "required": True}]},
        ],
    )
    _write_profiles(
        store_home,
        {"version": 1, "profiles": {"base": {"projects": [], "values": {"A_1": "x", "B_1": "y"}}}},
    )
    result = run_hook(claude_dir, store_home, tmp_path)
    assert result.returncode == 0
    ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "alpha/svc-a" in ctx and "A_2" in ctx
    assert "alpha/svc-b" in ctx and "B_2" in ctx


def test_never_prints_a_value(fixture, tmp_path):
    claude_dir, store_home, install_dir = fixture
    _write_catalog(
        install_dir,
        [{"name": "svc", "type": "mcp", "env": [{"name": "REQ_1", "required": True}, {"name": "REQ_2", "required": True}]}],
    )
    _write_profiles(
        store_home,
        {"version": 1, "profiles": {"base": {"projects": [], "values": {"REQ_1": "super-secret-xyz"}}}},
    )
    result = run_hook(claude_dir, store_home, tmp_path)
    assert "super-secret-xyz" not in result.stdout


def test_inherited_from_base_counts_as_set(fixture, tmp_path):
    claude_dir, store_home, install_dir = fixture
    _write_catalog(
        install_dir,
        [{"name": "svc", "type": "mcp", "env": [{"name": "REQ_1", "required": True}]}],
    )
    _write_profiles(
        store_home,
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {"REQ_1": "base-value"}},
                "client-a": {"projects": [str(tmp_path)], "values": {}},
            },
        },
    )
    result = run_hook(claude_dir, store_home, tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# Never blocks session start
# ---------------------------------------------------------------------------


def test_missing_installed_plugins_json_is_silent_not_error(tmp_path):
    claude_dir = tmp_path / "claude_config"
    claude_dir.mkdir()
    store_home = tmp_path / "store"
    result = run_hook(claude_dir, store_home, tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""


def test_malformed_stdin_is_silent_not_error(fixture, tmp_path):
    claude_dir, store_home, install_dir = fixture
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not valid json",
        env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "CLAUDE_CONFIG_DIR": str(claude_dir), indie_store.STORE_ENV_VAR: str(store_home)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0


def test_empty_stdin_is_silent_not_error(fixture, tmp_path):
    claude_dir, store_home, install_dir = fixture
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="",
        env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "CLAUDE_CONFIG_DIR": str(claude_dir), indie_store.STORE_ENV_VAR: str(store_home)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0


def test_disabled_plugin_is_never_checked(tmp_path):
    claude_dir = tmp_path / "claude_config"
    store_home = tmp_path / "store"
    install_dir = tmp_path / "plugins" / "alpha"
    _write_catalog(
        install_dir,
        [{"name": "svc", "type": "mcp", "env": [{"name": "REQ_1", "required": True}, {"name": "REQ_2", "required": True}]}],
    )
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
    _write_profiles(store_home, {"version": 1, "profiles": {"base": {"projects": [], "values": {"REQ_1": "x"}}}})
    result = run_hook(claude_dir, store_home, tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""
