"""Turso database client initialization and management."""

import os
from threading import Lock
from typing import Any, Optional

try:
    import libsql
except ImportError:
    libsql = None  # ty: ignore[invalid-assignment]


_conn_lock = Lock()
_cached_conn: Optional[Any] = None
_db_initialized = False


def _create_turso_client():
    """Create a new Turso client connection."""
    if libsql is None:
        raise ImportError("libsql is not installed. Install it with: uv add libsql")

    # Get configuration from environment variables
    db_url = os.environ.get("TURSO_DATABASE_URL")
    auth_token = os.environ.get("TURSO_AUTH_TOKEN")

    if not db_url:
        raise ValueError(
            "TURSO_DATABASE_URL not set. "
            "Set it via the TURSO_DATABASE_URL environment variable."
        )

    if not auth_token:
        raise ValueError(
            "TURSO_AUTH_TOKEN not set. "
            "Set it via the TURSO_AUTH_TOKEN environment variable."
        )

    # Connect directly to remote (simpler, no cache issues)
    return libsql.connect(db_url, auth_token=auth_token)  # ty: ignore[unresolved-attribute]


def get_turso_client():
    """Get or create Turso database client.

    Returns:
        libsql.Connection: Initialized Turso connection

    Raises:
        ImportError: If libsql is not installed
        ValueError: If required environment variables are not set
    """
    global _cached_conn

    if _cached_conn is not None:
        return _cached_conn

    with _conn_lock:
        if _cached_conn is None:
            _cached_conn = _create_turso_client()

    return _cached_conn


def reset_turso_client() -> None:
    """Reset the cached Turso client (for broken streams)."""
    global _cached_conn
    with _conn_lock:
        if _cached_conn is not None:
            try:
                _cached_conn.close()
            except Exception:
                pass
            _cached_conn = None


def initialize_database(force: bool = False) -> None:
    """Initialize Turso database with required tables.

    Creates tables if they don't exist:
    - riders
    - transit_modes
    - trips
    """
    global _db_initialized

    if _db_initialized and not force:
        return

    conn = get_turso_client()

    with _conn_lock:
        if _db_initialized and not force:
            return

        # Create riders table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS riders (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # Create transit_modes table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transit_modes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                color TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # Create trips table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trips (
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
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (rider_id) REFERENCES riders(id),
                FOREIGN KEY (transit_id) REFERENCES transit_modes(id)
            )
            """
        )

        trips_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(trips)").fetchall()
        }
        if "content_hash" not in trips_columns:
            conn.execute("ALTER TABLE trips ADD COLUMN content_hash TEXT")

        if "user_id" not in trips_columns:
            conn.execute("ALTER TABLE trips ADD COLUMN user_id TEXT")

        # CSV migration columns
        csv_columns = {
            "trip_id": "TEXT",
            "end_datetime": "TEXT",
            "start_location": "TEXT",
            "end_location": "TEXT",
            "fare": "REAL",
            "operator": "TEXT",
            "pass_type": "TEXT",
            "source": "TEXT",
            "category": "TEXT",
        }
        for col_name, col_type in csv_columns.items():
            if col_name not in trips_columns:
                conn.execute(f"ALTER TABLE trips ADD COLUMN {col_name} {col_type}")

        # Backfill source for existing rows
        conn.execute(
            "UPDATE trips SET source = 'pdf' WHERE source IS NULL"
            " AND transaction_date IS NOT NULL AND trip_id IS NULL"
        )

        # Index for trip_id dedup
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_trip_id
            ON trips(trip_id) WHERE trip_id IS NOT NULL
            """
        )

        # Create indices
        conn.execute("CREATE INDEX IF NOT EXISTS trips_rider_id_idx ON trips(rider_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS trips_transaction_date_idx ON trips(transaction_date)"
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS trips_rider_hash_idx
            ON trips(rider_id, content_hash)
            WHERE content_hash IS NOT NULL
            """
        )

        # Seed transit modes if empty
        result = conn.execute("SELECT COUNT(*) as count FROM transit_modes")
        count = result.fetchone()[0] if result else 0

        if count == 0:
            # Insert default transit modes
            transit_modes = [
                ("Muni Bus", "Muni Bus", "#BA0C2F"),
                ("Muni Metro", "Muni Metro", "#FDB813"),
                ("BART", "BART", "#0099CC"),
                ("Cable Car", "Cable Car", "#8B4513"),
                ("Caltrain", "Caltrain", "#6C6C6C"),
                ("AC Transit", "AC Transit", "#00A55E"),
                ("Ferry", "Ferry", "#4DD0E1"),
                ("SamTrans", "SamTrans", "#D3D3D3"),
            ]

            for name, display_name, color in transit_modes:
                conn.execute(
                    "INSERT INTO transit_modes (name, display_name, color) VALUES (?, ?, ?)",
                    [name, display_name, color],
                )

        # Commit changes once all setup is done
        conn.commit()
        _db_initialized = True
