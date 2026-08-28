import json
import os
import stat
import subprocess
from pathlib import Path

RESOLVER_SRC = Path(__file__).resolve().parent.parent / "shared" / "resolver.py"

STUB_DUMP = """#!/usr/bin/env python3
import json
import os
import sys

print(json.dumps({"argv": sys.argv[1:], "env": dict(os.environ)}))
"""


def write_bundles(project: Path, yaml_text: str) -> None:
    (project / "bundles.yaml").write_text(yaml_text)


def run_build(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(project / "build.py"), *args],
        cwd=project,
        capture_output=True,
        text=True,
    )


def make_stub_bin(tmp_path: Path) -> Path:
    """A PATH-injectable dir holding a `probe` executable that dumps its
    own argv and environment as JSON — the "real command" a wrapper execs."""
    stub_dir = tmp_path / "stub_bin"
    stub_dir.mkdir()
    probe = stub_dir / "probe"
    probe.write_text(STUB_DUMP)
    probe.chmod(0o755)
    return stub_dir


def make_store(tmp_path: Path, values: dict) -> Path:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    store = home / ".indie-marketplace"
    store.mkdir(mode=0o700)
    profiles = {"version": 1, "profiles": {"base": {"projects": [], "values": values}}}
    (store / "profiles.json").write_text(json.dumps(profiles))
    return store


def is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_IXUSR)


def wrapper_env(stub_dir: Path, home: Path, store: Path) -> dict:
    """The real environment (so /bin/sh builtins like `dirname` resolve),
    with PATH fronted by the stub dir and the store vars pinned."""
    return {
        **os.environ,
        "PATH": f"{stub_dir}:{os.environ['PATH']}",
        "HOME": str(home),
        "INDIE_MARKETPLACE_HOME": str(store),
    }


# ---------------------------------------------------------------------------
# Seam 1 — build.py output
# ---------------------------------------------------------------------------


def test_wrapper_generated_only_for_credential_bearing_entries(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    mcp:
      - name: svc-cred
        command: probe
        args: ["--flag", "${MY_VAR}"]
        env:
          MY_VAR: null
      - name: svc-plain
        command: echo
        args: ["hi"]
    deps:
      - command: probe-cli
        env:
          DEP_VAR: null
      - command: ls
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stdout

    bin_dir = project / "plugins/alpha/bin"
    assert (bin_dir / "svc-cred").exists()
    assert is_executable(bin_dir / "svc-cred")
    assert not (bin_dir / "svc-plain").exists()
    assert (bin_dir / "probe-cli").exists()
    assert is_executable(bin_dir / "probe-cli")
    assert not (bin_dir / "ls").exists()

    resolver_copy = bin_dir / "resolver.py"
    assert resolver_copy.exists()
    assert is_executable(resolver_copy)
    assert resolver_copy.read_bytes() == RESOLVER_SRC.read_bytes()


def test_plugin_with_no_credential_bearing_entries_gets_no_bin_dir(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    mcp:
      - name: svc-plain
        command: echo
        args: ["hi"]
    deps:
      - command: ls
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stdout
    assert not (project / "plugins/alpha/bin").exists()


def test_mcp_json_points_credential_entries_at_wrapper(project):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    mcp:
      - name: svc-cred
        command: probe
        args: ["--flag", "${MY_VAR}"]
        env:
          MY_VAR: null
      - name: svc-plain
        command: echo
        args: ["hi"]
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stdout
    mcp = json.loads((project / "plugins/alpha/.mcp.json").read_text())
    assert mcp["mcpServers"]["svc-cred"] == {
        "command": "${CLAUDE_PLUGIN_ROOT}/bin/svc-cred",
        "args": [],
    }
    assert mcp["mcpServers"]["svc-plain"] == {"command": "echo", "args": ["hi"]}

    vscode = json.loads((project / "plugins/alpha/vscode-mcp.json").read_text())
    assert vscode["servers"]["svc-cred"] == {
        "type": "stdio",
        "command": "${CLAUDE_PLUGIN_ROOT}/bin/svc-cred",
        "args": [],
    }
    assert vscode["servers"]["svc-plain"] == {
        "type": "stdio",
        "command": "echo",
        "args": ["hi"],
    }
    assert "inputs" not in vscode


# ---------------------------------------------------------------------------
# Seam 3 — observable environment
# ---------------------------------------------------------------------------


def test_wrapper_resolves_secrets_and_keeps_them_out_of_argv(project, tmp_path):
    secret_value = "a`b$(c)d;e|f'g\"h"
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
        command: probe
        args: ["-e", "SECRET=${MY_VAR}", "--flag", "${OTHER_VAR}", "literal"]
        env:
          MY_VAR: null
          OTHER_VAR: { required: false }
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stdout

    stub_dir = make_stub_bin(tmp_path)
    store = make_store(tmp_path, {"MY_VAR": secret_value, "OTHER_VAR": "plain123"})

    proc = subprocess.run(
        [str(project / "plugins/alpha/bin/svc")],
        env=wrapper_env(stub_dir, tmp_path / "home", store),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    observed = json.loads(proc.stdout)

    assert observed["argv"] == ["-e", "SECRET", "--flag", "plain123", "literal"]
    assert observed["env"]["SECRET"] == secret_value
    assert all(secret_value not in token for token in observed["argv"])


def test_wrapper_propagates_resolver_failure_on_missing_required_var(project, tmp_path):
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
        command: probe
        args: ["--flag", "${MY_VAR}"]
        env:
          MY_VAR: null
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stdout

    stub_dir = make_stub_bin(tmp_path)
    store = tmp_path / "home" / ".indie-marketplace"

    proc = subprocess.run(
        [str(project / "plugins/alpha/bin/svc")],
        env=wrapper_env(stub_dir, tmp_path / "home", store),
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "MY_VAR" in proc.stderr
    assert proc.stdout == ""


def test_scoped_launcher_forwards_args_and_resolves_credentials(project, tmp_path):
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    deps:
      - command: probe
        env:
          DEP_VAR: null
""",
    )
    result = run_build(project)
    assert result.returncode == 0, result.stdout

    stub_dir = make_stub_bin(tmp_path)
    store = make_store(tmp_path, {"DEP_VAR": "dep-secret"})

    proc = subprocess.run(
        [str(project / "plugins/alpha/bin/probe"), "arg1", "--flag=x", "arg with spaces"],
        env=wrapper_env(stub_dir, tmp_path / "home", store),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    observed = json.loads(proc.stdout)

    assert observed["argv"] == ["arg1", "--flag=x", "arg with spaces"]
    assert observed["env"]["DEP_VAR"] == "dep-secret"
