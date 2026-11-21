"""
Shared pytest fixtures.

Redirects the SQLite DB to a fresh temp file for every test so
summarizer cache tests don't bleed into each other.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Give each test its own SQLite file and initialize tables fresh."""
    import app.db.store as store_mod
    db_file = tmp_path / "test_ehr.db"
    monkeypatch.setattr(store_mod, "DB_PATH", db_file)
    store_mod.init_db()
    yield
