"""Tests for schema creation and category rules seeding."""

import sqlite3

import pytest

from clippertv.data.schema import create_tables, seed_category_rules


@pytest.fixture
def db():
    """In-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    return conn


def test_trips_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trips'")
    assert cursor.fetchone() is not None


def test_manual_trips_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='manual_trips'")
    assert cursor.fetchone() is not None


def test_category_rules_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='category_rules'")
    assert cursor.fetchone() is not None


def test_seed_category_rules_populates(db):
    seed_category_rules(db)
    count = db.execute("SELECT COUNT(*) FROM category_rules").fetchone()[0]
    # 30 metro + 14 cable car + 1 muni fallback + operator-level rules
    assert count > 40


def test_category_rules_muni_metro(db):
    seed_category_rules(db)
    row = db.execute(
        "SELECT category FROM category_rules WHERE operator = 'Muni' AND location = 'Embarcadero'"
    ).fetchone()
    assert row[0] == "Muni Metro"


def test_category_rules_cable_car(db):
    seed_category_rules(db)
    row = db.execute(
        "SELECT category FROM category_rules WHERE operator = 'Muni' AND location = 'Hyde/Beach'"
    ).fetchone()
    assert row[0] == "Cable Car"


def test_category_rules_muni_fallback(db):
    seed_category_rules(db)
    row = db.execute(
        "SELECT category FROM category_rules WHERE operator = 'Muni' AND location = ''"
    ).fetchone()
    assert row[0] == "Muni Bus"


def test_category_rules_ferry_consolidation(db):
    seed_category_rules(db)
    row = db.execute(
        "SELECT category FROM category_rules WHERE operator = 'WETA' AND location = ''"
    ).fetchone()
    assert row[0] == "Ferry"


def test_category_rules_passthrough(db):
    seed_category_rules(db)
    row = db.execute(
        "SELECT category FROM category_rules WHERE operator = 'BART' AND location = ''"
    ).fetchone()
    assert row[0] == "BART"


def test_seed_is_idempotent(db):
    seed_category_rules(db)
    count1 = db.execute("SELECT COUNT(*) FROM category_rules").fetchone()[0]
    seed_category_rules(db)
    count2 = db.execute("SELECT COUNT(*) FROM category_rules").fetchone()[0]
    assert count1 == count2


def test_trip_id_unique_index_allows_null(db):
    """Legacy rows have NULL trip_id — multiple NULLs must be allowed."""
    db.execute(
        "INSERT INTO trips (account_number, start_datetime, operator) VALUES ('A', '2024-01-01', 'BART')"
    )
    db.execute(
        "INSERT INTO trips (account_number, start_datetime, operator) VALUES ('A', '2024-01-02', 'BART')"
    )
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    assert count == 2


def test_trip_id_unique_index_prevents_dupes(db):
    db.execute(
        "INSERT INTO trips (account_number, trip_id, start_datetime, operator) VALUES ('A', 'T1', '2024-01-01', 'BART')"
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO trips (account_number, trip_id, start_datetime, operator) VALUES ('A', 'T1', '2024-01-02', 'BART')"
        )
