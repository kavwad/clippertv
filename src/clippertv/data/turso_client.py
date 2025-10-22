"""Turso database client initialization and management."""

import os
from typing import Optional

try:
    import libsql
except ImportError:
    libsql = None


def get_turso_client():
    """Get or create Turso database client.

    Returns:
        libsql.Connection: Initialized Turso connection

    Raises:
        ImportError: If libsql is not installed
        ValueError: If required environment variables are not set
    """
    if libsql is None:
        raise ImportError(
            "libsql is not installed. "
            "Install it with: uv add libsql"
        )

    # Get configuration from environment variables or Streamlit secrets
    db_url = os.environ.get("TURSO_DATABASE_URL")
    auth_token = os.environ.get("TURSO_AUTH_TOKEN")

    # Try Streamlit secrets as fallback
    if not db_url or not auth_token:
        try:
            import streamlit as st
            db_url = db_url or st.secrets.get("turso", {}).get("database_url")
            auth_token = auth_token or st.secrets.get("turso", {}).get("auth_token")
        except (ImportError, FileNotFoundError, AttributeError):
            pass

    if not db_url:
        raise ValueError(
            "TURSO_DATABASE_URL not set. "
            "Set it via environment variable or Streamlit secrets."
        )

    if not auth_token:
        raise ValueError(
            "TURSO_AUTH_TOKEN not set. "
            "Set it via environment variable or Streamlit secrets."
        )

    # Connect directly to remote (simpler, no cache issues)
    conn = libsql.connect(db_url, auth_token=auth_token)
    return conn


def initialize_database() -> None:
    """Initialize Turso database with required tables.

    Creates tables if they don't exist:
    - riders
    - transit_modes
    - trips
    """
    conn = get_turso_client()

    # Create riders table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS riders (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Create transit_modes table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transit_modes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            color TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Create trips table
    conn.execute("""
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
    """)

    # Create indices
    conn.execute("CREATE INDEX IF NOT EXISTS trips_rider_id_idx ON trips(rider_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS trips_transaction_date_idx ON trips(transaction_date)")

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
                [name, display_name, color]
            )

    # Commit changes
    conn.commit()
