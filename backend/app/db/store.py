"""
SQLite-backed FHIR Bundle store using aiosqlite.

Schema:
  fhir_bundles(mrn TEXT PK, bundle_json TEXT, created_at TEXT, updated_at TEXT)
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path(__file__).parent.parent.parent / "data" / "ehr.db"


def _get_conn() -> sqlite3.Connection:
    # Read DB_PATH at call time so tests can monkeypatch it
    import app.db.store as _self
    path = _self.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fhir_bundles (
                mrn        TEXT PRIMARY KEY,
                bundle_json TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS summary_cache (
                cache_key   TEXT PRIMARY KEY,
                mrn         TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """)
        conn.commit()


def upsert_bundle(mrn: str, bundle_dict: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    bundle_json = json.dumps(bundle_dict)
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO fhir_bundles (mrn, bundle_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(mrn) DO UPDATE SET
                bundle_json = excluded.bundle_json,
                updated_at  = excluded.updated_at
        """, (mrn, bundle_json, now, now))
        conn.commit()


def get_bundle(mrn: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT bundle_json FROM fhir_bundles WHERE mrn = ?", (mrn,)
        ).fetchone()
    return json.loads(row["bundle_json"]) if row else None


def list_mrns() -> list[str]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT mrn FROM fhir_bundles").fetchall()
    return [r["mrn"] for r in rows]


def get_summary_cache(cache_key: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT summary_json FROM summary_cache WHERE cache_key = ?", (cache_key,)
        ).fetchone()
    return json.loads(row["summary_json"]) if row else None


def set_summary_cache(cache_key: str, mrn: str, summary_dict: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO summary_cache (cache_key, mrn, summary_json, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET summary_json = excluded.summary_json
        """, (cache_key, mrn, json.dumps(summary_dict), now))
        conn.commit()
