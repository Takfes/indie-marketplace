import stat

import pytest

from shared import indie_store


@pytest.fixture(autouse=True)
def store_home(tmp_path, monkeypatch):
    home = tmp_path / "store"
    monkeypatch.setenv(indie_store.STORE_ENV_VAR, str(home))
    return home


def test_load_profiles_on_missing_store_returns_empty_base():
    data = indie_store.load_profiles()
    assert data == {"version": 1, "profiles": {"base": {"projects": [], "values": {}}}}


def test_save_then_load_round_trips(store_home):
    data = {
        "version": 1,
        "profiles": {
            "base": {"projects": [], "values": {"ZOTERO_API_KEY": "abc"}},
            "client-a": {"projects": ["/work/client-a"], "values": {"PGQUERY_URI": "postgres://x"}},
        },
    }
    indie_store.save_profiles(data)
    assert indie_store.load_profiles() == data


def test_save_profiles_creates_store_dir_mode_0700(store_home):
    indie_store.save_profiles(indie_store.load_profiles())
    mode = stat.S_IMODE(store_home.stat().st_mode)
    assert mode == 0o700


def test_save_profiles_writes_file_mode_0600(store_home):
    indie_store.save_profiles(indie_store.load_profiles())
    path = store_home / indie_store.PROFILES_FILE
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_save_profiles_fixes_loose_dir_permissions(store_home):
    store_home.mkdir(parents=True)
    store_home.chmod(0o755)
    indie_store.save_profiles(indie_store.load_profiles())
    mode = stat.S_IMODE(store_home.stat().st_mode)
    assert mode == 0o700


def test_read_active_on_missing_file_returns_none():
    assert indie_store.read_active() is None


def test_read_active_on_blank_file_returns_none(store_home):
    store_home.mkdir(parents=True)
    (store_home / indie_store.ACTIVE_FILE).write_text("   \n")
    assert indie_store.read_active() is None


def test_write_then_read_active_round_trips(store_home):
    indie_store.write_active("client-a")
    assert indie_store.read_active() == "client-a"


def test_write_active_file_mode_0600(store_home):
    indie_store.write_active("client-a")
    path = store_home / indie_store.ACTIVE_FILE
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600
