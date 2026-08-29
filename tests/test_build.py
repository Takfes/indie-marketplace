import json
import subprocess
from pathlib import Path


def write_bundles(project: Path, yaml_text: str) -> None:
    (project / "bundles.yaml").write_text(yaml_text)


def run_build(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(project / "build.py"), *args],
        cwd=project,
        capture_output=True,
        text=True,
    )


def test_null_env_value_is_required_and_undescribed_in_catalog(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: svc
        command: docker
        env:
          FOO_KEY: null
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stderr
    catalog = json.loads((project / "plugins/alpha/.claude-plugin/catalog.json").read_text())
    assert catalog == [
        {"name": "svc", "type": "mcp", "env": [{"name": "FOO_KEY", "required": True, "description": None}]},
        {
            "name": "docker",
            "type": "cli",
            "command": "docker",
            "install": "brew install --cask docker",
            "manual": "https://docs.docker.com/get-docker/",
            "source": "mcp",
            "required_by": ["svc"],
            "env": [],
        },
    ]


def test_env_metadata_reaches_catalog_json(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: svc
        command: docker
        env:
          ZOTERO_API_KEY: { required: false, description: "Zotero Web API key" }
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stderr
    catalog = json.loads((project / "plugins/alpha/.claude-plugin/catalog.json").read_text())
    assert catalog[0]["env"] == [
        {"name": "ZOTERO_API_KEY", "required": False, "description": "Zotero Web API key"}
    ]


def test_duplicate_env_var_across_plugins_fails_build(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: svc
        command: docker
        env:
          SHARED_KEY: null
  - name: beta
    env:
      SHARED_KEY: null
""",
    )
    result = run_build(project)
    assert result.returncode != 0
    assert "SHARED_KEY" in result.stdout
    assert "alpha" in result.stdout
    assert "beta" in result.stdout


def test_duplicate_check_runs_on_scoped_plugin_build(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: svc
        command: docker
        env:
          SHARED_KEY: null
  - name: beta
    env:
      SHARED_KEY: null
""",
    )
    result = run_build(project, "--plugin", "alpha")
    assert result.returncode != 0
    assert "SHARED_KEY" in result.stdout
    assert "alpha" in result.stdout
    assert "beta" in result.stdout


def test_same_var_within_one_plugin_is_not_a_duplicate(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: svc-a
        command: docker
        env:
          DB_URI: null
      - name: svc-b
        command: docker
        env:
          DB_URI: null
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# type: "cli" catalog entries — see docs/cli-installation-architecture.md
# ---------------------------------------------------------------------------


def _cli_entries(project: Path, plugin: str = "alpha") -> list[dict]:
    catalog = json.loads((project / f"plugins/{plugin}/.claude-plugin/catalog.json").read_text())
    return [entry for entry in catalog if entry["type"] == "cli"]


def test_mcp_commands_become_one_deduped_cli_entry(project):
    """The database/docker shape: four servers, one docker dependency."""
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: pgquery
        command: docker
      - name: dbtools
        command: docker
      - name: mysql-mcp
        command: docker
      - name: mssql-mcp
        command: docker
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stderr
    assert _cli_entries(project) == [
        {
            "name": "docker",
            "type": "cli",
            "command": "docker",
            "install": "brew install --cask docker",
            "manual": "https://docs.docker.com/get-docker/",
            "source": "mcp",
            "required_by": ["pgquery", "dbtools", "mysql-mcp", "mssql-mcp"],
            "env": [],
        }
    ]


def test_env_prefixed_mcp_command_is_unwrapped_to_the_real_binary(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: svc
        command: env
        args: ["A=1", "B=2", "realcmd", "--flag"]
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stderr
    entries = _cli_entries(project)
    assert [e["command"] for e in entries] == ["realcmd"]
    assert entries[0]["required_by"] == ["svc"]


def test_env_prefixed_mcp_command_with_no_real_command_fails_the_build(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: svc
        command: env
        args: ["A=1", "B=2"]
""",
    )
    result = run_build(project)
    assert result.returncode != 0
    assert "no real command" in result.stdout


def test_placeholder_mcp_command_yields_no_cli_entry(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: azaks
        command: ${AZAKS_BIN}
        env:
          AZAKS_BIN: null
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stderr
    assert _cli_entries(project) == []


def test_mcp_entry_without_a_command_still_stops_at_write_mcp_json(project):
    """A command-less `mcp:` entry is the future remote/SSE shape. Catalog
    generation skips it rather than crashing, but .mcp.json generation
    still can't express one and raises first — so that guard has no
    positive test yet. Pinned here so the ordering stays deliberate: when
    remote entries land, this is the test that flips."""
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: remote
""",
    )
    result = run_build(project)
    assert result.returncode != 0
    assert "write_mcp_json" in result.stderr


def test_deps_entry_install_hint_overrides_the_fallback_table(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    deps:
      - command: docker
        install: colima start
        manual: https://example.invalid/docker
    mcp:
      - name: svc
        command: docker
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stderr
    assert _cli_entries(project) == [
        {
            "name": "docker",
            "type": "cli",
            "command": "docker",
            "install": "colima start",
            "manual": "https://example.invalid/docker",
            # reached eagerly through svc, so it ranks as the mcp: requirement
            "source": "mcp",
            "required_by": ["svc"],
            "env": [],
        }
    ]


def test_command_with_no_hint_anywhere_still_surfaces(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    mcp:
      - name: svc
        command: notebooklm-mcp
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stderr
    entry = _cli_entries(project)[0]
    assert entry["command"] == "notebooklm-mcp"
    assert entry["install"] is None
    assert entry["manual"] is None


def test_deps_entries_keep_their_lazy_source(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    deps:
      - command: yt-dlp
        install: brew install yt-dlp
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stderr
    entry = _cli_entries(project)[0]
    assert entry["source"] == "deps"
    assert entry["required_by"] == []


# ---------------------------------------------------------------------------
# deps:/mcp: ⟹ catalog: true
# ---------------------------------------------------------------------------


def test_deps_without_catalog_fails_the_build(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    deps:
      - command: yt-dlp
""",
    )
    result = run_build(project)
    assert result.returncode != 0
    assert "alpha" in result.stdout
    assert "`deps:`" in result.stdout
    assert "catalog: true" in result.stdout


def test_mcp_without_catalog_fails_the_build(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    mcp:
      - name: svc
        command: docker
""",
    )
    result = run_build(project)
    assert result.returncode != 0
    assert "alpha" in result.stdout
    assert "`mcp:`" in result.stdout


def test_catalog_invariant_runs_on_scoped_plugin_build(project):
    """The whole reason this validator is config-level: a scoped build of a
    different plugin must still fail on the offender."""
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    skills: []
  - name: beta
    deps:
      - command: yt-dlp
""",
    )
    result = run_build(project, "--plugin", "alpha")
    assert result.returncode != 0
    assert "beta" in result.stdout
    assert "catalog: true" in result.stdout


def test_plugin_with_catalog_and_both_blocks_passes(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    deps:
      - command: yt-dlp
    mcp:
      - name: svc
        command: docker
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stdout


# ---------------------------------------------------------------------------
# validate_deps — no prior coverage in this suite
# ---------------------------------------------------------------------------


def test_deps_entry_without_a_command_fails_the_build(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    deps:
      - install: brew install yt-dlp
""",
    )
    result = run_build(project)
    assert result.returncode != 0
    assert "missing required `command`" in result.stdout
