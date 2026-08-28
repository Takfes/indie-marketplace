#!/usr/bin/env python3
"""Local HTTP server for editing indie-marketplace credential profiles.

Claude launches this process and reads its stdout — the single line it
prints is the only thing that stream ever carries, so no code path here may
print anything else to stdout (logging, tracebacks, output of any kind all
go to stderr instead).

This file is copied into the secrets-manager skill's installed plugin
directory alongside its one runtime dependency, indie_store.py (see
build.py's build_local_skill) — Python standard library only, no other file
in this repository is reachable from here at runtime.

Usage: server.py [--idle-timeout SECONDS]

Binds 127.0.0.1 on a kernel-assigned port, mints a random per-run token, and
prints exactly one line to stdout: the URL (including the token) to open in
a browser. Exits on POST /api/shutdown or after `idle_timeout` seconds with
no authenticated request (default 15 minutes) — a forgotten process serving
credentials on loopback is the failure that guards against.

API:
  GET    /api/catalog          -> [{plugin, name, type, env:[{name, required,
                                    description}]}] — names only, never values
  GET    /api/profiles         -> {profile: {projects, values: {VAR: state}}}
                                    state is one of set-here/inherited/unset
  GET    /api/value?profile=&name= -> {"value": "..." | null}
  POST   /api/profile/<name>   <- {"values": {VAR: "..."|null}, "projects": [...]}
                                    null clears an override; "" stores an
                                    empty string
  POST   /api/profile/<name>/rename <- {"to": "new-name"}
  DELETE /api/profile/<name>
  POST   /api/active           <- {"profile": "client-a"}
  POST   /api/shutdown
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indie_store  # noqa: E402

DEFAULT_IDLE_TIMEOUT = 15 * 60
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


# ---------------------------------------------------------------------------
# Catalog discovery — every installed and enabled plugin's catalog.json
# ---------------------------------------------------------------------------


def _claude_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))


def _enabled_plugin_keys() -> set[str]:
    path = _claude_config_dir() / "settings.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    return {key for key, value in data.get("enabledPlugins", {}).items() if value}


def _installed_plugin_paths() -> dict[str, Path]:
    """plugin name -> install path, for every enabled and installed plugin.

    installed_plugins.json keys are "<plugin>@<marketplace>"; a plugin with
    multiple install records (e.g. user + project scope) is resolved to the
    record with the newest lastUpdated.
    """
    path = _claude_config_dir() / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if data.get("version") != 2:
        return {}

    enabled_keys = _enabled_plugin_keys()
    result: dict[str, Path] = {}
    for key, records in data.get("plugins", {}).items():
        if key not in enabled_keys or not records:
            continue
        newest = max(records, key=lambda r: r.get("lastUpdated", ""))
        install_path = newest.get("installPath")
        if install_path:
            result[key.split("@", 1)[0]] = Path(install_path)
    return result


def build_catalog() -> list[dict]:
    """[{plugin, name, type, env}] for every credential-bearing entry across
    every installed and enabled plugin. Names only, never values."""
    catalog: list[dict] = []
    for plugin_name, install_path in sorted(_installed_plugin_paths().items()):
        catalog_file = install_path / ".claude-plugin" / "catalog.json"
        try:
            entries = json.loads(catalog_file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for entry in entries:
            catalog.append({"plugin": plugin_name, **entry})
    return catalog


def _catalog_var_names(catalog: list[dict]) -> set[str]:
    return {var["name"] for entry in catalog for var in entry.get("env", [])}


# ---------------------------------------------------------------------------
# Profile views and resolution
# ---------------------------------------------------------------------------


def _resolve_value(profiles: dict, profile_name: str, name: str) -> str | None:
    values = profiles.get(profile_name, {}).get("values", {})
    if name in values:
        value = values[name]
        if value:
            return value
    base_values = profiles.get(indie_store.BASE_PROFILE, {}).get("values", {})
    return base_values.get(name) or None


def build_profiles_view() -> dict:
    """Profile names, projects, and per-variable state (masked) — never a
    value, only whether it is set-here, inherited from base, or unset."""
    data = indie_store.load_profiles()
    profiles = data.get("profiles", {})
    var_names = sorted(_catalog_var_names(build_catalog()))
    base_values = profiles.get(indie_store.BASE_PROFILE, {}).get("values", {})

    view = {}
    for name, profile in profiles.items():
        values = profile.get("values", {})
        state = {}
        for var in var_names:
            if var in values:
                state[var] = "set-here"
            elif name != indie_store.BASE_PROFILE and var in base_values:
                state[var] = "inherited"
            else:
                state[var] = "unset"
        view[name] = {"projects": profile.get("projects", []), "values": state}
    return view


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "SecretsManager/1"

    def _send_json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _token_from_request(self, query: dict) -> str | None:
        token = query.get("token", [None])[0]
        if token is not None:
            return token
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[len("Bearer ") :]
        return None

    def _guard(self, query: dict) -> bool:
        if self.headers.get("Host") != self.server.expected_host:
            self._send_json(400, {"error": "bad host"})
            return False
        token = self._token_from_request(query)
        if token is None or not secrets.compare_digest(token, self.server.token):
            self._send_json(401, {"error": "unauthorized"})
            return False
        self.server.last_activity = time.monotonic()
        return True

    def _read_json_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return None

    # -- routing --------------------------------------------------------

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if not self._guard(query):
            return

        if parsed.path == "/":
            self._send_html(200, PLACEHOLDER_PAGE)
        elif parsed.path == "/api/catalog":
            self._send_json(200, build_catalog())
        elif parsed.path == "/api/profiles":
            self._send_json(200, build_profiles_view())
        elif parsed.path == "/api/value":
            self._handle_get_value(query)
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if not self._guard(query):
            return

        path = parsed.path
        if path == "/api/shutdown":
            self._send_json(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        body = self._read_json_body()
        if body is None:
            return

        if path == "/api/active":
            self._handle_set_active(body)
        elif path.startswith("/api/profile/") and path.endswith("/rename"):
            name = urllib.parse.unquote(path[len("/api/profile/") : -len("/rename")])
            self._handle_rename(name, body)
        elif path.startswith("/api/profile/"):
            name = urllib.parse.unquote(path[len("/api/profile/") :])
            self._handle_write_profile(name, body)
        else:
            self._send_json(404, {"error": "not found"})

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if not self._guard(query):
            return

        if parsed.path.startswith("/api/profile/"):
            name = urllib.parse.unquote(parsed.path[len("/api/profile/") :])
            self._handle_delete_profile(name)
        else:
            self._send_json(404, {"error": "not found"})

    # -- handlers ---------------------------------------------------------

    def _handle_get_value(self, query: dict) -> None:
        profile = query.get("profile", [None])[0]
        name = query.get("name", [None])[0]
        if not profile or not name:
            self._send_json(400, {"error": "profile and name are required"})
            return
        profiles = indie_store.load_profiles().get("profiles", {})
        if profile not in profiles:
            self._send_json(404, {"error": "unknown profile"})
            return
        self._send_json(200, {"value": _resolve_value(profiles, profile, name)})

    def _handle_write_profile(self, name: str, body: dict) -> None:
        if not SLUG_RE.match(name):
            self._send_json(400, {"error": "invalid profile name"})
            return

        values = body.get("values") or {}
        projects = body.get("projects")

        catalog_vars = _catalog_var_names(build_catalog())
        unknown = sorted(k for k in values if k not in catalog_vars)
        if unknown:
            self._send_json(400, {"error": f"unknown variable(s): {', '.join(unknown)}"})
            return

        bad_values = sorted(k for k, v in values.items() if v is not None and "\n" in v)
        if bad_values:
            self._send_json(400, {"error": f"value cannot contain a newline: {', '.join(bad_values)}"})
            return

        if projects is not None:
            bad_projects = [p for p in projects if not Path(p).is_absolute()]
            if bad_projects:
                self._send_json(400, {"error": f"projects must be absolute paths: {', '.join(bad_projects)}"})
                return

        data = indie_store.load_profiles()
        profiles = data.setdefault("profiles", {})
        profile = profiles.setdefault(name, {"projects": [], "values": {}})
        for key, value in values.items():
            if value is None:
                profile["values"].pop(key, None)
            else:
                profile["values"][key] = value
        if projects is not None:
            profile["projects"] = projects

        indie_store.save_profiles(data)
        self._send_json(200, {"profile": name})

    def _handle_rename(self, name: str, body: dict) -> None:
        if name == indie_store.BASE_PROFILE:
            self._send_json(400, {"error": "base cannot be renamed"})
            return
        new_name = body.get("to")
        if not new_name or not SLUG_RE.match(new_name):
            self._send_json(400, {"error": "invalid new name"})
            return

        data = indie_store.load_profiles()
        profiles = data.get("profiles", {})
        if name not in profiles:
            self._send_json(404, {"error": "unknown profile"})
            return
        if new_name in profiles:
            self._send_json(400, {"error": "a profile with that name already exists"})
            return

        profiles[new_name] = profiles.pop(name)
        indie_store.save_profiles(data)
        if indie_store.read_active() == name:
            indie_store.write_active(new_name)
        self._send_json(200, {"profile": new_name})

    def _handle_delete_profile(self, name: str) -> None:
        if name == indie_store.BASE_PROFILE:
            self._send_json(400, {"error": "base cannot be deleted"})
            return

        data = indie_store.load_profiles()
        profiles = data.get("profiles", {})
        if name not in profiles:
            self._send_json(404, {"error": "unknown profile"})
            return

        del profiles[name]
        indie_store.save_profiles(data)
        if indie_store.read_active() == name:
            indie_store.write_active(indie_store.BASE_PROFILE)
        self._send_json(200, {"deleted": name})

    def _handle_set_active(self, body: dict) -> None:
        name = body.get("profile")
        profiles = indie_store.load_profiles().get("profiles", {})
        if not name or name not in profiles:
            self._send_json(400, {"error": "unknown profile"})
            return
        indie_store.write_active(name)
        self._send_json(200, {"active": name})


PLACEHOLDER_PAGE = (
    b"<!doctype html><title>secrets-manager</title>"
    b"<p>Placeholder UI \xe2\x80\x94 the real page ships in a later change.</p>"
)


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], token: str, idle_timeout: int):
        super().__init__(address, handler)
        self.token = token
        self.idle_timeout = idle_timeout
        self.last_activity = time.monotonic()
        self.expected_host = f"127.0.0.1:{self.server_address[1]}"


def _watch_idle(httpd: Server) -> None:
    while True:
        time.sleep(1)
        if time.monotonic() - httpd.last_activity > httpd.idle_timeout:
            httpd.shutdown()
            return


def run(idle_timeout: int = DEFAULT_IDLE_TIMEOUT) -> None:
    token = secrets.token_urlsafe(32)
    httpd = Server(("127.0.0.1", 0), Handler, token, idle_timeout)
    port = httpd.server_address[1]

    threading.Thread(target=_watch_idle, args=(httpd,), daemon=True).start()

    print(f"http://127.0.0.1:{port}/?token={token}", flush=True)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def main(argv: list[str]) -> int:
    idle_timeout = DEFAULT_IDLE_TIMEOUT
    if len(argv) >= 2 and argv[0] == "--idle-timeout":
        idle_timeout = int(argv[1])
    run(idle_timeout=idle_timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
