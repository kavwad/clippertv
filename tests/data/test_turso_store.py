"""Tests for TursoStore incremental persistence."""

from __future__ import annotations

import sqlite3
from typing import Tuple

import pandas as pd
import pytest

from clippertv.data import turso_store as store_module
from clippertv.data.turso_store import TursoStore


def _setup_schema(conn: sqlite3.Connection) -> None:
    """Create a minimal schema compatible with TursoStore."""
    conn.execute(
        """
        CREATE TABLE riders (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE transit_modes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            color TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rider_id TEXT NOT NULL,
            transit_id INTEGER,
            transaction_type TEXT NOT NULL,
            transaction_date TEXT NOT NULL,
            location TEXT,
            route TEXT,
            debit REAL,
            credit REAL,
            balance REAL,
            product TEXT,
            content_hash TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    for mode in ("Caltrain", "Muni Bus"):
        conn.execute(
            "INSERT INTO transit_modes (name, display_name, color) VALUES (?, ?, ?)",
            (mode, mode, "#000000"),
        )
    conn.commit()


def _base_transactions() -> pd.DataFrame:
    """Return a small DataFrame representing two Caltrain taps."""
    return pd.DataFrame(
        [
            {
                "Transaction Date": pd.Timestamp("2024-02-01T08:00:00"),
                "Transaction Type": "entry",
                "Category": "Caltrain Entrance",
                "Location": "CAL",
                "Route": None,
                "Debit": 15.40,
                "Credit": 0.0,
                "Balance": None,
                "Product": None,
            },
            {
                "Transaction Date": pd.Timestamp("2024-02-01T09:00:00"),
                "Transaction Type": "exit",
                "Category": "Caltrain Exit",
                "Location": "CAL",
                "Route": None,
                "Debit": 0.0,
                "Credit": 7.70,
                "Balance": None,
                "Product": None,
            },
        ]
    )


@pytest.fixture
def memory_store(monkeypatch: pytest.MonkeyPatch) -> Tuple[TursoStore, sqlite3.Connection]:
    """Provide a TursoStore wired to an in-memory sqlite database."""
    conn = sqlite3.connect(":memory:")
    _setup_schema(conn)

    monkeypatch.setattr(store_module, "initialize_database", lambda force=False: None)
    monkeypatch.setattr(store_module, "get_turso_client", lambda: conn)

    store = TursoStore()
    store.conn = conn
    store._transit_ids = store._get_transit_mode_ids()
    return store, conn


def test_save_data_skips_rows_with_known_hashes(memory_store: Tuple[TursoStore, sqlite3.Connection]) -> None:
    """Calling save_data twice with the same frame should not duplicate rows."""
    store, conn = memory_store
    df = _base_transactions()

    store.save_data("B", df)
    first_count = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    assert first_count == len(df)

    hashed_count = conn.execute(
        "SELECT COUNT(*) FROM trips WHERE content_hash IS NOT NULL"
    ).fetchone()[0]
    assert hashed_count == len(df)

    store.save_data("B", df)
    second_count = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    assert second_count == len(df)


def test_save_data_only_persists_new_transactions(memory_store: Tuple[TursoStore, sqlite3.Connection]) -> None:
    """Only the newly added transaction should be inserted on the second pass."""
    store, conn = memory_store
    df = _base_transactions()
    store.save_data("B", df)

    new_row = pd.DataFrame(
        [
            {
                "Transaction Date": pd.Timestamp("2024-03-05T08:30:00"),
                "Transaction Type": "entry",
                "Category": "Muni Bus",
                "Location": "SFM bus",
                "Route": "N",
                "Debit": 2.50,
                "Credit": 0.0,
                "Balance": None,
                "Product": None,
            }
        ]
    )

    store.save_data("B", pd.concat([df, new_row], ignore_index=True))

    total_trips = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    assert total_trips == len(df) + 1

    new_hash_count = conn.execute(
        "SELECT COUNT(*) FROM trips WHERE content_hash IS NOT NULL"
    ).fetchone()[0]
    assert new_hash_count == len(df) + 1
