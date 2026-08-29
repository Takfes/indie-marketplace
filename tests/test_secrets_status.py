import subprocess
import sys
from pathlib import Path

import pytest

from shared import indie_store
from tests.test_secrets_server import build_fixture


@pytest.fixture
def status_env(project, tmp_path, monkeypatch):
    """Build the fixture and fake CLAUDE_CONFIG_DIR/INDIE_MARKETPLACE_HOME,
    returning (status_py, env, store_home) — status.py is invoked directly,
    one subcommand per subprocess, unlike the long-running HTTP server.
    Also points this test process's own indie_store calls (used to seed
    profiles.json directly, as test_resolver.py does) at store_home."""
    claude_dir, store_home, home = build_fixture(project, tmp_path)
    monkeypatch.setenv(indie_store.STORE_ENV_VAR, str(store_home))
    status_py = project / "plugins" / "essentials" / "skills" / "plugin-setup" / "status.py"
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(claude_dir),
        "INDIE_MARKETPLACE_HOME": str(store_home),
    }
    return status_py, env, store_home


def run_status(status_py, env, *args, cwd=None, profile=None):
    full_env = dict(env)
    if profile is not None:
        full_env["INDIE_PROFILE"] = profile
    return subprocess.run(
        [sys.executable, str(status_py), *args],
        cwd=str(cwd) if cwd else None,
        env=full_env,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# unset
# ---------------------------------------------------------------------------


def test_unset_lists_required_and_optional_gaps(status_env, tmp_path):
    status_py, env, store_home = status_env
    result = run_status(status_py, env, "unset", "--profile", "base", cwd=tmp_path)
    assert result.returncode == 0
    assert "MY_VAR" in result.stdout
    assert "OTHER_VAR" in result.stdout
    assert "required" in result.stdout
    assert "optional" in result.stdout


def test_unset_reflects_inheritance_from_base(status_env, tmp_path):
    status_py, env, store_home = status_env
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {"MY_VAR": "base-value"}},
                "client-a": {"projects": [], "values": {}},
            },
        }
    )
    result = run_status(status_py, env, "unset", "--profile", "client-a", cwd=tmp_path)
    assert result.returncode == 0
    assert "MY_VAR" not in result.stdout
    assert "OTHER_VAR" in result.stdout


def test_unset_never_prints_a_value(status_env, tmp_path):
    status_py, env, store_home = status_env
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {"base": {"projects": [], "values": {"MY_VAR": "super-secret-xyz"}}},
        }
    )
    result = run_status(status_py, env, "unset", "--profile", "base", cwd=tmp_path)
    assert "super-secret-xyz" not in result.stdout


def test_unset_defaults_profile_to_resolved_directory(status_env, tmp_path):
    status_py, env, store_home = status_env
    project_dir = tmp_path / "client-a"
    project_dir.mkdir()
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {}},
                "client-a": {"projects": [str(project_dir)], "values": {"MY_VAR": "v", "OTHER_VAR": "o"}},
            },
        }
    )
    result = run_status(status_py, env, "unset", cwd=project_dir)
    assert result.returncode == 0
    assert "every declared variable is set" in result.stdout


def test_unset_unknown_profile_is_an_error(status_env, tmp_path):
    status_py, env, store_home = status_env
    result = run_status(status_py, env, "unset", "--profile", "ghost", cwd=tmp_path)
    assert result.returncode == 1
    assert "ghost" in result.stderr


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------


def test_resolve_reports_base_fallback(status_env, tmp_path):
    status_py, env, store_home = status_env
    result = run_status(status_py, env, "resolve", str(tmp_path), cwd=tmp_path)
    assert result.returncode == 0
    assert "'base'" in result.stdout
    assert "base fallback" in result.stdout


def test_resolve_reports_active_file(status_env, tmp_path):
    status_py, env, store_home = status_env
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {"base": {"projects": [], "values": {}}, "client-a": {"projects": [], "values": {}}},
        }
    )
    indie_store.write_active("client-a")
    result = run_status(status_py, env, "resolve", str(tmp_path), cwd=tmp_path)
    assert result.returncode == 0
    assert "'client-a'" in result.stdout
    assert "active file" in result.stdout


def test_resolve_reports_bound_project_path(status_env, tmp_path):
    status_py, env, store_home = status_env
    project_dir = tmp_path / "client-a"
    project_dir.mkdir()
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {}},
                "client-a": {"projects": [str(project_dir)], "values": {}},
            },
        }
    )
    indie_store.write_active("base")
    result = run_status(status_py, env, "resolve", str(project_dir), cwd=tmp_path)
    assert result.returncode == 0
    assert "'client-a'" in result.stdout
    assert "bound project path" in result.stdout


def test_resolve_reports_indie_profile_override(status_env, tmp_path):
    status_py, env, store_home = status_env
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {"base": {"projects": [], "values": {}}, "client-b": {"projects": [], "values": {}}},
        }
    )
    result = run_status(status_py, env, "resolve", str(tmp_path), cwd=tmp_path, profile="client-b")
    assert result.returncode == 0
    assert "'client-b'" in result.stdout
    assert "INDIE_PROFILE" in result.stdout


def test_resolve_defaults_path_to_cwd(status_env, tmp_path):
    status_py, env, store_home = status_env
    result = run_status(status_py, env, "resolve", cwd=tmp_path)
    assert result.returncode == 0
    assert str(tmp_path.resolve()) in result.stdout


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def test_doctor_reports_no_problems_on_a_clean_store(status_env, tmp_path):
    status_py, env, store_home = status_env
    indie_store.save_profiles({"version": 1, "profiles": {"base": {"projects": [], "values": {}}}})
    result = run_status(status_py, env, "doctor", cwd=tmp_path)
    assert result.returncode == 0
    assert "no problems found" in result.stdout


def test_doctor_flags_a_dead_bound_project_path(status_env, tmp_path):
    status_py, env, store_home = status_env
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {}},
                "ghost": {"projects": ["/does/not/exist/anywhere"], "values": {}},
            },
        }
    )
    result = run_status(status_py, env, "doctor", cwd=tmp_path)
    assert result.returncode == 1
    assert "/does/not/exist/anywhere" in result.stdout


def test_doctor_flags_an_orphaned_variable(status_env, tmp_path):
    status_py, env, store_home = status_env
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {"base": {"projects": [], "values": {"NOT_IN_ANY_CATALOG": "x"}}},
        }
    )
    result = run_status(status_py, env, "doctor", cwd=tmp_path)
    assert result.returncode == 1
    assert "NOT_IN_ANY_CATALOG" in result.stdout


def test_doctor_never_prints_a_value(status_env, tmp_path):
    status_py, env, store_home = status_env
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {"base": {"projects": [], "values": {"NOT_IN_ANY_CATALOG": "super-secret-xyz"}}},
        }
    )
    result = run_status(status_py, env, "doctor", cwd=tmp_path)
    assert "super-secret-xyz" not in result.stdout


def test_doctor_flags_bad_permissions(status_env, tmp_path):
    status_py, env, store_home = status_env
    indie_store.save_profiles({"version": 1, "profiles": {"base": {"projects": [], "values": {}}}})
    (store_home / "profiles.json").chmod(0o644)
    result = run_status(status_py, env, "doctor", cwd=tmp_path)
    assert result.returncode == 1
    assert "0o644" in result.stdout or "profiles.json" in result.stdout
