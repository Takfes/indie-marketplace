import subprocess
import sys
from pathlib import Path

import pytest

from shared import indie_store

RESOLVER = Path(__file__).resolve().parent.parent / "shared" / "resolver.py"


def run_resolver(store_home, *args, cwd=None, profile=None):
    env = {"HOME": str(Path.home()), indie_store.STORE_ENV_VAR: str(store_home)}
    if profile is not None:
        env["INDIE_PROFILE"] = profile
    return subprocess.run(
        [sys.executable, str(RESOLVER), *args],
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def store_home(tmp_path, monkeypatch):
    home = tmp_path / "store"
    monkeypatch.setenv(indie_store.STORE_ENV_VAR, str(home))
    return home


def test_no_store_required_var_fails(store_home, tmp_path):
    result = run_resolver(store_home, "PGQUERY_URI", cwd=tmp_path)
    assert result.returncode == 1
    assert "PGQUERY_URI" in result.stderr
    assert "base" in result.stderr
    assert result.stdout == ""


def test_no_store_optional_var_succeeds_with_no_output(store_home, tmp_path):
    result = run_resolver(store_home, "ZOTERO_API_KEY?", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""


def test_resolves_from_base_profile(store_home, tmp_path):
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {"base": {"projects": [], "values": {"ZOTERO_API_KEY": "zk-1"}}},
        }
    )
    result = run_resolver(store_home, "ZOTERO_API_KEY", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == "ZOTERO_API_KEY=zk-1\n"


def test_named_profile_overrides_base_via_active_file(store_home, tmp_path):
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {"PGQUERY_URI": "postgres://base"}},
                "client-a": {"projects": [], "values": {"PGQUERY_URI": "postgres://client-a"}},
            },
        }
    )
    indie_store.write_active("client-a")
    result = run_resolver(store_home, "PGQUERY_URI", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == "PGQUERY_URI=postgres://client-a\n"


def test_named_profile_inherits_unset_var_from_base(store_home, tmp_path):
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {"ZOTERO_API_KEY": "zk-base"}},
                "client-a": {"projects": [], "values": {"PGQUERY_URI": "postgres://client-a"}},
            },
        }
    )
    indie_store.write_active("client-a")
    result = run_resolver(store_home, "ZOTERO_API_KEY", "PGQUERY_URI", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == "ZOTERO_API_KEY=zk-base\nPGQUERY_URI=postgres://client-a\n"


def test_empty_string_value_falls_back_to_base(store_home, tmp_path):
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {"PGQUERY_URI": "postgres://base"}},
                "client-a": {"projects": [], "values": {"PGQUERY_URI": ""}},
            },
        }
    )
    indie_store.write_active("client-a")
    result = run_resolver(store_home, "PGQUERY_URI", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == "PGQUERY_URI=postgres://base\n"


def test_indie_profile_env_overrides_active_file(store_home, tmp_path):
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {}},
                "client-a": {"projects": [], "values": {"PGQUERY_URI": "postgres://client-a"}},
                "client-b": {"projects": [], "values": {"PGQUERY_URI": "postgres://client-b"}},
            },
        }
    )
    indie_store.write_active("client-a")
    result = run_resolver(store_home, "PGQUERY_URI", cwd=tmp_path, profile="client-b")
    assert result.returncode == 0
    assert result.stdout == "PGQUERY_URI=postgres://client-b\n"


def test_indie_profile_env_unknown_profile_is_hard_error(store_home, tmp_path):
    result = run_resolver(store_home, "PGQUERY_URI", cwd=tmp_path, profile="ghost")
    assert result.returncode == 1
    assert "ghost" in result.stderr
    assert result.stdout == ""


def test_cwd_project_binding_selects_profile(store_home, tmp_path):
    project_dir = tmp_path / "client-a"
    project_dir.mkdir()
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {}},
                "client-a": {
                    "projects": [str(project_dir)],
                    "values": {"PGQUERY_URI": "postgres://client-a"},
                },
            },
        }
    )
    result = run_resolver(store_home, "PGQUERY_URI", cwd=project_dir)
    assert result.returncode == 0
    assert result.stdout == "PGQUERY_URI=postgres://client-a\n"


def test_cwd_project_binding_does_not_match_sibling_with_shared_prefix(store_home, tmp_path):
    (tmp_path / "client-a").mkdir()
    sibling = tmp_path / "client-abc"
    sibling.mkdir()
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {"PGQUERY_URI": "postgres://base"}},
                "client-a": {
                    "projects": [str(tmp_path / "client-a")],
                    "values": {"PGQUERY_URI": "postgres://client-a"},
                },
            },
        }
    )
    result = run_resolver(store_home, "PGQUERY_URI", cwd=sibling)
    assert result.returncode == 0
    assert result.stdout == "PGQUERY_URI=postgres://base\n"


def test_cwd_project_binding_longest_match_wins(store_home, tmp_path):
    parent = tmp_path / "work"
    child = parent / "proj"
    grandchild = child / "sub"
    grandchild.mkdir(parents=True)
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {}},
                "broad": {
                    "projects": [str(parent)],
                    "values": {"PGQUERY_URI": "postgres://broad"},
                },
                "narrow": {
                    "projects": [str(child)],
                    "values": {"PGQUERY_URI": "postgres://narrow"},
                },
            },
        }
    )
    result = run_resolver(store_home, "PGQUERY_URI", cwd=grandchild)
    assert result.returncode == 0
    assert result.stdout == "PGQUERY_URI=postgres://narrow\n"


def test_cwd_project_binding_beats_active_file(store_home, tmp_path):
    project_dir = tmp_path / "client-a"
    project_dir.mkdir()
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {
                "base": {"projects": [], "values": {}},
                "client-a": {
                    "projects": [str(project_dir)],
                    "values": {"PGQUERY_URI": "postgres://client-a"},
                },
                "client-b": {"projects": [], "values": {"PGQUERY_URI": "postgres://client-b"}},
            },
        }
    )
    indie_store.write_active("client-b")
    result = run_resolver(store_home, "PGQUERY_URI", cwd=project_dir)
    assert result.returncode == 0
    assert result.stdout == "PGQUERY_URI=postgres://client-a\n"


def test_multiple_names_mixed_required_optional(store_home, tmp_path):
    indie_store.save_profiles(
        {
            "version": 1,
            "profiles": {"base": {"projects": [], "values": {"PGQUERY_URI": "postgres://base"}}},
        }
    )
    result = run_resolver(store_home, "PGQUERY_URI", "ZOTERO_API_KEY?", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == "PGQUERY_URI=postgres://base\n"


def test_multiple_missing_required_vars_report_all(store_home, tmp_path):
    result = run_resolver(store_home, "PGQUERY_URI", "MYSQL_MCP_PASS", cwd=tmp_path)
    assert result.returncode == 1
    assert "PGQUERY_URI" in result.stderr
    assert "MYSQL_MCP_PASS" in result.stderr


def test_no_args_prints_usage(store_home, tmp_path):
    result = run_resolver(store_home, cwd=tmp_path)
    assert result.returncode == 2
    assert "usage" in result.stderr
