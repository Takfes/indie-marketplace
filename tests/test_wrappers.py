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
    catalog: true
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
    catalog: true
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
    catalog: true
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


def test_command_env_with_no_real_command_fails_cleanly(project):
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
      - name: broken
        command: env
        args: ["FOO=${BAR}"]
        env:
          BAR: null
""",
    )
    result = run_build(project)
    assert result.returncode != 0
    assert "broken" in result.stdout
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


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
    catalog: true
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
    catalog: true
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
    catalog: true
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


# ---------------------------------------------------------------------------
# last30days — the one hardcoded skills:-level wrapper (issue #85)
# ---------------------------------------------------------------------------

L30D_BUNDLES = """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: web-search
    skills:
      - name: last30days
        source: community
        repo: "https://example.invalid/last30days-skill"
        path: "skills/last30days"
        env:
          SCRAPECREATORS_API_KEY: { required: false }
"""

L30D_PYTHON_GATE = (
    "\"${LAST30DAYS_PYTHON}\" -c 'import sys; raise SystemExit(0 if sys.version_info "
    ">= (3, 12) else 1)' || {\n"
    '  echo "ERROR: LAST30DAYS_PYTHON must point to Python 3.12+." >&2\n'
    "  exit 1\n"
    "}\n"
)

# The invocation shapes build.py rewrites, and how many of each the vendored
# files carry. Mirrors build.py's own table on purpose: these counts are the
# contract, and a build that silently patches a different number of sites is
# the failure this whole feature guards against.
L30D_ENGINE_CALLS = [
    ('"${LAST30DAYS_PYTHON}" "${SKILL_DIR}/scripts/last30days.py"', 8),
    ('"${LAST30DAYS_PYTHON:-python3}" "${SKILL_DIR}/scripts/last30days.py"', 5),
    ('"${LAST30DAYS_PYTHON:-python3}" skills/last30days/scripts/last30days.py', 10),
    ("python3 scripts/last30days.py --", 2),
    ("python3 scripts/last30days.py queue ", 2),
]
L30D_BRIEF_CALLS = [('"${LAST30DAYS_PYTHON}" "${SKILL_ROOT}/scripts/last30days.py"', 2)]

# Prose *about* invocations, which must survive a build untouched — SKILL.md
# has plenty of it and rewriting any of it would corrupt the skill's rules.
L30D_PROSE = [
    "a bare `python3 scripts/last30days.py` path-discovery loop is a LAW violation",
    'A bare `python3 scripts/last30days.py "$TOPIC" --emit=compact` is a LAW 7 violation.',
    "direct CLI invocations (`python3 scripts/last30days.py ...`) without `--save-dir` still save",
    "Before running any `last30days.py` command in this skill, resolve a Python 3.12+ interpreter",
    "if [ ! -f \"$SKILL_DIR/scripts/last30days.py\" ]; then",
    "set LAST30DAYS_PYTHON to a supported interpreter",
]


def _l30d_file(calls: list, prose: list) -> str:
    lines = ["# vendored fixture\n"]
    lines += [f"{p}\n" for p in prose]
    for target, count in calls:
        for n in range(count):
            lines.append(f"{target} run-{n} --flag\n")
    return "".join(lines)


def make_last30days_skill(project: Path) -> Path:
    """A stand-in for the vendored upstream skill: the invocation shapes
    build.py patches, the prose it must leave alone, and a stub engine at the
    path the generated wrapper execs."""
    skill = project / "plugins/web-search/skills/last30days"
    (skill / "references").mkdir(parents=True)
    (skill / "scripts").mkdir()
    (skill / "SKILL.md").write_text(
        L30D_PYTHON_GATE + _l30d_file(L30D_ENGINE_CALLS, L30D_PROSE)
    )
    (skill / "references/save-html-brief.md").write_text(_l30d_file(L30D_BRIEF_CALLS, []))
    (skill / "scripts/last30days.py").write_text(STUB_DUMP)
    return skill


def test_last30days_wrapper_generated_and_exports_the_resolved_key(project, tmp_path):
    make_last30days_skill(project)
    write_bundles(project, L30D_BUNDLES)
    result = run_build(project)
    assert result.returncode == 0, result.stdout

    wrapper = project / "plugins/web-search/bin/last30days"
    assert wrapper.exists()
    assert is_executable(wrapper)
    assert (project / "plugins/web-search/bin/resolver.py").read_bytes() == RESOLVER_SRC.read_bytes()

    store = make_store(tmp_path, {"SCRAPECREATORS_API_KEY": "sc-test-value"})
    proc = subprocess.run(
        [str(wrapper), "some topic", "--emit=compact"],
        env=wrapper_env(make_stub_bin(tmp_path), tmp_path / "home", store),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    observed = json.loads(proc.stdout)
    assert observed["argv"] == ["some topic", "--emit=compact"]
    assert observed["env"]["SCRAPECREATORS_API_KEY"] == "sc-test-value"


def test_last30days_wrapper_still_runs_when_the_key_is_unset(project, tmp_path):
    """The key is optional — the engine works without it, so an empty store
    must reach the engine rather than failing the way a required var does."""
    make_last30days_skill(project)
    write_bundles(project, L30D_BUNDLES)
    assert run_build(project).returncode == 0

    proc = subprocess.run(
        [str(project / "plugins/web-search/bin/last30days"), "topic"],
        env=wrapper_env(
            make_stub_bin(tmp_path), tmp_path / "home", tmp_path / "home/.indie-marketplace"
        ),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "SCRAPECREATORS_API_KEY" not in json.loads(proc.stdout)["env"]


def test_last30days_build_points_vendored_invocations_at_the_wrapper(project):
    skill = make_last30days_skill(project)
    write_bundles(project, L30D_BUNDLES)
    assert run_build(project).returncode == 0

    skill_md = (skill / "SKILL.md").read_text()
    brief = (skill / "references/save-html-brief.md").read_text()

    for target, _ in L30D_ENGINE_CALLS:
        assert target not in skill_md
    for target, _ in L30D_BRIEF_CALLS:
        assert target not in brief

    assert skill_md.count('"${SKILL_DIR}/../../bin/last30days"') == 17
    assert skill_md.count("bin/last30days run-") == 10
    assert brief.count('"${SKILL_ROOT}/../../bin/last30days"') == 2

    # The preflight's interpreter is exported so the wrapper — a child
    # process — runs it instead of falling back to bare python3.
    assert skill_md.count("export LAST30DAYS_PYTHON") == 1

    for prose in L30D_PROSE:
        assert prose in skill_md


def test_last30days_patch_is_idempotent_across_builds(project):
    skill = make_last30days_skill(project)
    write_bundles(project, L30D_BUNDLES)
    assert run_build(project).returncode == 0
    once = (skill / "SKILL.md").read_text(), (skill / "references/save-html-brief.md").read_text()

    assert run_build(project).returncode == 0
    twice = (skill / "SKILL.md").read_text(), (skill / "references/save-html-brief.md").read_text()
    assert once == twice


def test_last30days_patch_fails_loudly_when_the_target_text_drifted(project):
    """A --fetch restores upstream's text; if upstream moved, the build must
    stop and say so rather than shipping a wrapper nothing calls."""
    skill = make_last30days_skill(project)
    skill_md = skill / "SKILL.md"
    target = L30D_ENGINE_CALLS[0][0]
    skill_md.write_text(skill_md.read_text().replace(f"{target} run-0", "python3 upstream-moved.py run-0", 1))
    write_bundles(project, L30D_BUNDLES)

    result = run_build(project)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "SKILL.md" in output
    assert target in output
    assert "found 7 unpatched" in output
    assert "Traceback" not in output


def test_last30days_patch_fails_loudly_when_a_vendored_file_is_gone(project):
    skill = make_last30days_skill(project)
    (skill / "references/save-html-brief.md").unlink()
    write_bundles(project, L30D_BUNDLES)

    result = run_build(project)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "save-html-brief.md" in output
    assert "Traceback" not in output


def test_other_skills_level_env_declarations_still_get_no_wrapper(project):
    """No generic skills:-level mechanism was introduced: last30days is
    hardcoded, and every other skill declaring env: stays catalog-only."""
    write_bundles(
        project,
        """
marketplace:
  name: test
  owner: { name: tester }
plugins:
  - name: alpha
    catalog: true
    skills:
      - name: some-cli-skill
        source: local
        env:
          SOME_CLI_KEY: null
""",
    )
    (project / "skills/some-cli-skill").mkdir(parents=True)
    (project / "skills/some-cli-skill/SKILL.md").write_text("# stub\n")

    result = run_build(project)
    assert result.returncode == 0, result.stdout
    assert not (project / "plugins/alpha/bin").exists()
    catalog = json.loads((project / "plugins/alpha/.claude-plugin/catalog.json").read_text())
    assert catalog == [
        {
            "name": "some-cli-skill",
            "type": "skill",
            "env": [{"name": "SOME_CLI_KEY", "required": True, "description": None}],
        }
    ]


def test_last30days_bare_form_invocations_are_patched_but_prose_is_not(project):
    """The follow-up-intent bullets say "invoke the engine with `python3
    scripts/last30days.py --drill ...`" — genuine commands, and --drill and
    --verify-freshness refetch sources, so they need the key. The same bare
    string also appears in LAW text and in a note about direct CLI use, which
    must survive verbatim."""
    skill = make_last30days_skill(project)
    write_bundles(project, L30D_BUNDLES)
    assert run_build(project).returncode == 0

    skill_md = (skill / "SKILL.md").read_text()
    assert "python3 scripts/last30days.py --" not in skill_md
    assert "python3 scripts/last30days.py queue " not in skill_md
    assert skill_md.count('"${SKILL_DIR}/../../bin/last30days" --') == 2
    assert skill_md.count('"${SKILL_DIR}/../../bin/last30days" queue ') == 2

    assert "a bare `python3 scripts/last30days.py` path-discovery loop" in skill_md
    assert 'A bare `python3 scripts/last30days.py "$TOPIC" --emit=compact`' in skill_md
    assert "(`python3 scripts/last30days.py ...`)" in skill_md


def test_last30days_bare_form_patch_fails_loudly_when_a_site_disappears(project):
    skill = make_last30days_skill(project)
    skill_md = skill / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text().replace("python3 scripts/last30days.py -- run-0", "moved-upstream", 1)
    )
    write_bundles(project, L30D_BUNDLES)

    result = run_build(project)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "python3 scripts/last30days.py --" in output
    assert "found 1 unpatched" in output
    assert "Traceback" not in output
