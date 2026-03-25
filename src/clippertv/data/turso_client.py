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
    """Initialize database with v2 schema tables."""
    global _db_initialized

    if _db_initialized and not force:
        return

    conn = get_turso_client()

    with _conn_lock:
        if _db_initialized and not force:
            return
        from clippertv.data.schema import create_tables, seed_category_rules
        create_tables(conn)
        seed_category_rules(conn)
        _db_initialized = True
