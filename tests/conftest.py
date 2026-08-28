import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILD_PY = ROOT / "build.py"
RESOLVER_PY = ROOT / "shared" / "resolver.py"
INDIE_STORE_PY = ROOT / "shared" / "indie_store.py"


@pytest.fixture
def project(tmp_path):
    """A temp dir with its own build.py and shared/{resolver,indie_store}.py,
    so ROOT (= build.py's own dirname) resolves inside it and every
    generated path stays isolated from the real repo."""
    shutil.copy2(BUILD_PY, tmp_path / "build.py")
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()
    shutil.copy2(RESOLVER_PY, shared_dir / "resolver.py")
    shutil.copy2(INDIE_STORE_PY, shared_dir / "indie_store.py")
    return tmp_path
