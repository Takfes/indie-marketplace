"""Storage primitives for ~/.indie-marketplace: profiles.json and the active file.

Used by tests and, later, by the secrets-manager web server. The resolver
(shared/resolver.py) does NOT import this module — it is copied standalone
into credential-bearing plugins and carries its own read-only copy of the
parts of this contract it needs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

STORE_ENV_VAR = "INDIE_MARKETPLACE_HOME"
DEFAULT_STORE_DIR = ".indie-marketplace"
PROFILES_FILE = "profiles.json"
ACTIVE_FILE = "active"
BASE_PROFILE = "base"


def store_root() -> Path:
    override = os.environ.get(STORE_ENV_VAR)
    return Path(override) if override else Path.home() / DEFAULT_STORE_DIR


def _empty_profiles() -> dict:
    return {"version": 1, "profiles": {BASE_PROFILE: {"projects": [], "values": {}}}}


def _atomic_write(path: Path, data: bytes, mode: int) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    os.chmod(parent, 0o700)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def load_profiles() -> dict:
    path = store_root() / PROFILES_FILE
    if not path.exists():
        return _empty_profiles()
    return json.loads(path.read_text())


def save_profiles(data: dict) -> None:
    payload = json.dumps(data, indent=2).encode() + b"\n"
    _atomic_write(store_root() / PROFILES_FILE, payload, 0o600)


def read_active() -> str | None:
    path = store_root() / ACTIVE_FILE
    if not path.exists():
        return None
    name = path.read_text().strip()
    return name or None


def write_active(name: str) -> None:
    _atomic_write(store_root() / ACTIVE_FILE, (name + "\n").encode(), 0o600)
