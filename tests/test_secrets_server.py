import http.client
import json
import os
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

SKILL_SRC = Path(__file__).resolve().parent.parent / "skills" / "secrets-manager"

BUNDLES = """
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
          OTHER_VAR: { required: false }
  - name: essentials
    skills:
      - name: secrets-manager
        source: local
"""


def run_build(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(project / "build.py"), *args],
        cwd=project,
        capture_output=True,
        text=True,
    )


class LiveServer:
    def __init__(self, proc: subprocess.Popen, base_url: str, token: str):
        self.proc = proc
        self.base_url = base_url
        self.token = token

    def get(self, path: str):
        return self._do(urllib.request.Request(f"{self.base_url}{path}", headers=self._headers()))

    def post(self, path: str, body: dict | None = None):
        data = json.dumps(body if body is not None else {}).encode()
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method="POST",
            headers={**self._headers(), "Content-Type": "application/json"},
        )
        return self._do(req)

    def delete(self, path: str):
        return self._do(urllib.request.Request(f"{self.base_url}{path}", method="DELETE", headers=self._headers()))

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def _do(self, req: urllib.request.Request):
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.post("/api/shutdown")
            except OSError:
                pass
            self.proc.wait(timeout=5)


def build_fixture(project: Path, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build the fixture project and fake an installed-and-enabled `alpha`
    plugin against it. Returns (claude_dir, store_home, home) — shared setup
    for anything that needs the generated secrets-manager skill directory
    (the HTTP server, or the value-blind status.py CLI)."""
    (project / "bundles.yaml").write_text(BUNDLES)
    (project / "skills").mkdir(exist_ok=True)
    shutil.copytree(SKILL_SRC, project / "skills" / "secrets-manager")

    result = run_build(project)
    assert result.returncode == 0, result.stdout

    claude_dir = tmp_path / "claude_config"
    (claude_dir / "plugins").mkdir(parents=True)
    (claude_dir / "settings.json").write_text(json.dumps({"enabledPlugins": {"alpha@test": True}}))
    installed = {
        "version": 2,
        "plugins": {
            "alpha@test": [
                {
                    "scope": "user",
                    "installPath": str(project / "plugins" / "alpha"),
                    "lastUpdated": "2026-01-01T00:00:00Z",
                }
            ]
        },
    }
    (claude_dir / "plugins" / "installed_plugins.json").write_text(json.dumps(installed))

    store_home = tmp_path / "store"
    home = tmp_path / "home"
    home.mkdir()
    return claude_dir, store_home, home


def _start_server(project: Path, tmp_path: Path, idle_timeout: int = 30) -> tuple[subprocess.Popen, Path]:
    """Build the fixture and launch the generated secrets-manager server
    against it. Returns (proc, store_home)."""
    claude_dir, store_home, home = build_fixture(project, tmp_path)

    server_py = project / "plugins" / "essentials" / "skills" / "secrets-manager" / "server.py"
    proc = subprocess.Popen(
        [sys.executable, str(server_py), "--idle-timeout", str(idle_timeout)],
        env={
            **os.environ,
            "HOME": str(home),
            "CLAUDE_CONFIG_DIR": str(claude_dir),
            "INDIE_MARKETPLACE_HOME": str(store_home),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc, store_home


@pytest.fixture
def live_server(project, tmp_path):
    proc, store_home = _start_server(project, tmp_path)
    url_line = proc.stdout.readline().strip()
    assert url_line.startswith("http://127.0.0.1:"), (url_line, proc.stderr.read())
    base, _, token = url_line.partition("?token=")

    server = LiveServer(proc, base.rstrip("/"), token)
    yield server, store_home
    server.close()


# ---------------------------------------------------------------------------
# Request hardening
# ---------------------------------------------------------------------------


def test_missing_token_rejected(live_server):
    server, _ = live_server
    req = urllib.request.Request(f"{server.base_url}/api/catalog")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 401


def test_mismatched_host_rejected(live_server):
    server, _ = live_server
    parsed = urllib.parse.urlparse(server.base_url)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        conn.request("GET", f"/api/catalog?token={server.token}", headers={"Host": "evil.example:9999"})
        resp = conn.getresponse()
        assert resp.status == 400
        resp.read()
    finally:
        conn.close()


def test_response_has_no_store_and_no_cors_headers(live_server):
    server, _ = live_server
    req = urllib.request.Request(f"{server.base_url}/api/catalog", headers=server._headers())
    resp = urllib.request.urlopen(req, timeout=5)
    assert resp.headers.get("Cache-Control") == "no-store"
    assert resp.headers.get("Access-Control-Allow-Origin") is None


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------


def test_catalog_lists_credential_bearing_entry(live_server):
    server, _ = live_server
    status, body = server.get("/api/catalog")
    assert status == 200
    assert body == [
        {
            "plugin": "alpha",
            "name": "svc",
            "type": "mcp",
            "env": [
                {"name": "MY_VAR", "required": True, "description": None},
                {"name": "OTHER_VAR", "required": False, "description": None},
            ],
        },
        {
            "plugin": "alpha",
            "name": "probe",
            "type": "cli",
            "command": "probe",
            "install": None,
            "manual": None,
            "source": "mcp",
            "required_by": ["svc"],
            "env": [],
        },
    ]


def test_profiles_view_never_returns_an_unmasked_value(live_server):
    server, _ = live_server
    server.post("/api/profile/base", {"values": {"MY_VAR": "base-secret-xyz"}})
    server.post("/api/profile/client-a", {"values": {"OTHER_VAR": "other-secret-abc"}, "projects": ["/work/client-a"]})

    status, body = server.get("/api/profiles")
    assert status == 200
    assert body["base"]["values"]["MY_VAR"] == "set-here"
    assert body["client-a"]["values"]["MY_VAR"] == "inherited"
    assert body["client-a"]["values"]["OTHER_VAR"] == "set-here"
    assert body["client-a"]["projects"] == ["/work/client-a"]

    dump = json.dumps(body)
    assert "base-secret-xyz" not in dump
    assert "other-secret-abc" not in dump


def test_value_endpoint_resolves_inheritance_from_base(live_server):
    server, _ = live_server
    server.post("/api/profile/base", {"values": {"MY_VAR": "base-value"}})
    server.post("/api/profile/client-a", {"values": {}})

    status, body = server.get("/api/value?profile=client-a&name=MY_VAR")
    assert status == 200
    assert body["value"] == "base-value"


def test_value_endpoint_unknown_profile_is_404(live_server):
    server, _ = live_server
    status, body = server.get("/api/value?profile=nope&name=MY_VAR")
    assert status == 404


def test_active_get_endpoint_reflects_current_state(live_server):
    server, _ = live_server
    status, body = server.get("/api/active")
    assert status == 200
    assert body["active"] is None

    server.post("/api/profile/client-a", {"values": {}})
    server.post("/api/active", {"profile": "client-a"})
    status, body = server.get("/api/active")
    assert status == 200
    assert body["active"] == "client-a"


# ---------------------------------------------------------------------------
# Static UI
# ---------------------------------------------------------------------------


def test_index_page_serves_the_real_ui(live_server):
    server, _ = live_server
    req = urllib.request.Request(f"{server.base_url}/", headers=server._headers())
    resp = urllib.request.urlopen(req, timeout=5)
    assert resp.status == 200
    assert resp.headers.get("Content-Type", "").startswith("text/html")
    assert resp.headers.get("Cache-Control") == "no-store"
    body = resp.read().decode()
    assert "Secrets Manager" in body
    assert "Placeholder" not in body


def test_index_page_requires_auth(live_server):
    server, _ = live_server
    req = urllib.request.Request(f"{server.base_url}/")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 401


# ---------------------------------------------------------------------------
# Write API
# ---------------------------------------------------------------------------


def test_valid_write_lands_with_mode_0600(live_server):
    server, store_home = live_server
    status, body = server.post("/api/profile/base", {"values": {"MY_VAR": "x"}})
    assert status == 200
    mode = stat.S_IMODE((store_home / "profiles.json").stat().st_mode)
    assert mode == 0o600


def test_unknown_variable_is_rejected_not_stored(live_server):
    server, store_home = live_server
    status, body = server.post("/api/profile/base", {"values": {"NOT_IN_CATALOG": "x"}})
    assert status == 400
    assert "NOT_IN_CATALOG" in body["error"]
    assert not (store_home / "profiles.json").exists()


def test_null_clears_override_distinct_from_empty_string(live_server):
    server, store_home = live_server
    server.post("/api/profile/client-a", {"values": {"MY_VAR": "override"}})
    data = json.loads((store_home / "profiles.json").read_text())
    assert data["profiles"]["client-a"]["values"]["MY_VAR"] == "override"

    server.post("/api/profile/client-a", {"values": {"MY_VAR": ""}})
    data = json.loads((store_home / "profiles.json").read_text())
    assert data["profiles"]["client-a"]["values"]["MY_VAR"] == ""

    server.post("/api/profile/client-a", {"values": {"MY_VAR": None}})
    data = json.loads((store_home / "profiles.json").read_text())
    assert "MY_VAR" not in data["profiles"]["client-a"]["values"]


def test_value_with_newline_is_rejected(live_server):
    server, _ = live_server
    status, body = server.post("/api/profile/base", {"values": {"MY_VAR": "line1\nline2"}})
    assert status == 400


def test_project_must_be_absolute_path(live_server):
    server, _ = live_server
    status, body = server.post("/api/profile/client-a", {"values": {}, "projects": ["relative/path"]})
    assert status == 400


def test_non_string_value_is_rejected_cleanly_not_a_crash(live_server):
    server, store_home = live_server
    status, body = server.post("/api/profile/base", {"values": {"MY_VAR": 123}})
    assert status == 400
    assert not (store_home / "profiles.json").exists()

    status, body = server.post("/api/profile/base", {"values": {"MY_VAR": "ok"}, "projects": "not-a-list"})
    assert status == 400
    assert not (store_home / "profiles.json").exists()

    # the connection must still be usable afterward — a crashed handler
    # thread must not have corrupted server state
    status, body = server.get("/api/catalog")
    assert status == 200


def test_non_string_active_profile_is_rejected_cleanly(live_server):
    server, _ = live_server
    status, body = server.post("/api/active", {"profile": ["not", "a", "string"]})
    assert status == 400


def test_non_string_rename_target_is_rejected_cleanly(live_server):
    server, _ = live_server
    server.post("/api/profile/client-a", {"values": {}})
    status, body = server.post("/api/profile/client-a/rename", {"to": 123})
    assert status == 400


def test_non_object_request_body_is_rejected_cleanly(live_server):
    server, _ = live_server
    data = json.dumps(["not", "an", "object"]).encode()
    req = urllib.request.Request(
        f"{server.base_url}/api/profile/base",
        data=data,
        method="POST",
        headers={**server._headers(), "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "expected HTTPError"
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_base_cannot_be_renamed_or_deleted(live_server):
    server, _ = live_server
    status, _ = server.post("/api/profile/base/rename", {"to": "renamed"})
    assert status == 400
    status, _ = server.delete("/api/profile/base")
    assert status == 400


def test_rename_preserves_values_and_projects(live_server):
    server, _ = live_server
    server.post("/api/profile/client-a", {"values": {"MY_VAR": "v1"}, "projects": ["/work/a"]})
    status, body = server.post("/api/profile/client-a/rename", {"to": "client-b"})
    assert status == 200
    assert body["profile"] == "client-b"

    status, profiles = server.get("/api/profiles")
    assert "client-a" not in profiles
    assert profiles["client-b"]["projects"] == ["/work/a"]
    assert profiles["client-b"]["values"]["MY_VAR"] == "set-here"


def test_delete_profile_removes_it(live_server):
    server, _ = live_server
    server.post("/api/profile/client-a", {"values": {}})
    status, body = server.delete("/api/profile/client-a")
    assert status == 200
    status, profiles = server.get("/api/profiles")
    assert "client-a" not in profiles


def test_active_endpoint_writes_expected_file(live_server):
    server, store_home = live_server
    server.post("/api/profile/client-a", {"values": {}})
    status, body = server.post("/api/active", {"profile": "client-a"})
    assert status == 200
    assert (store_home / "active").read_text().strip() == "client-a"


def test_active_rejects_unknown_profile(live_server):
    server, store_home = live_server
    status, body = server.post("/api/active", {"profile": "does-not-exist"})
    assert status == 400
    assert not (store_home / "active").exists()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_shutdown_endpoint_stops_the_process(live_server):
    server, _ = live_server
    status, body = server.post("/api/shutdown")
    assert status == 200
    server.proc.wait(timeout=5)
    assert server.proc.returncode == 0


def test_idle_timeout_shuts_down_an_untouched_server(project, tmp_path):
    proc, _ = _start_server(project, tmp_path, idle_timeout=1)
    try:
        url_line = proc.stdout.readline().strip()
        assert url_line.startswith("http://127.0.0.1:"), (url_line, proc.stderr.read())
        proc.wait(timeout=5)
        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.kill()
