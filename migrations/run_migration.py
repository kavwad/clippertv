"""Database migration script for Phase 1: Multi-User Backend."""

import os
import sys
from pathlib import Path

# Add parent directory to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.clippertv.data.turso_client import get_turso_client


def check_column_exists(client, table_name: str, column_name: str) -> bool:
    """
    Check if a column exists in a table.

    Args:
        client: Database client
        table_name: Name of the table
        column_name: Name of the column

    Returns:
        True if column exists, False otherwise
    """
    result = client.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in result.fetchall()}
    return column_name in columns


def run_migration():
    """Run Phase 1 migration to add multi-user support."""
    print("Starting Phase 1 migration: Multi-User Backend")
    print("=" * 60)

    client = get_turso_client()

    print("\n1. Creating users table...")
    try:
        client.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        print("   ✓ Created users table")
    except Exception as e:
        print(f"   ⚠ Warning: {e}")

    print("\n2. Creating index on users.email...")
    try:
        client.execute("CREATE INDEX IF NOT EXISTS users_email_idx ON users(email)")
        print("   ✓ Created index on users.email")
    except Exception as e:
        print(f"   ⚠ Warning: {e}")

    print("\n3. Creating clipper_cards table...")
    try:
        client.execute("""
            CREATE TABLE IF NOT EXISTS clipper_cards (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                card_number TEXT NOT NULL,
                rider_name TEXT NOT NULL,
                credentials_encrypted TEXT,
                is_primary INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        print("   ✓ Created clipper_cards table")
    except Exception as e:
        print(f"   ⚠ Warning: {e}")

    print("\n4. Creating indices on clipper_cards...")
    try:
        client.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS clipper_cards_user_card_idx
            ON clipper_cards(user_id, card_number)
        """)
        print("   ✓ Created unique index on clipper_cards(user_id, card_number)")
    except Exception as e:
        print(f"   ⚠ Warning: {e}")

    try:
        client.execute("CREATE INDEX IF NOT EXISTS clipper_cards_user_id_idx ON clipper_cards(user_id)")
        print("   ✓ Created index on clipper_cards.user_id")
    except Exception as e:
        print(f"   ⚠ Warning: {e}")

    # Add user_id to riders table if it doesn't exist
    print("\n5. Adding user_id column to riders table...")
    if not check_column_exists(client, "riders", "user_id"):
        client.execute("ALTER TABLE riders ADD COLUMN user_id TEXT")
        print("   ✓ Added user_id column to riders")
    else:
        print("   ⚠ Column user_id already exists in riders")

    # Add clipper_card_id to riders table if it doesn't exist
    print("\n6. Adding clipper_card_id column to riders table...")
    if not check_column_exists(client, "riders", "clipper_card_id"):
        client.execute("ALTER TABLE riders ADD COLUMN clipper_card_id TEXT")
        print("   ✓ Added clipper_card_id column to riders")
    else:
        print("   ⚠ Column clipper_card_id already exists in riders")

    # Add user_id to trips table if it doesn't exist
    print("\n7. Adding user_id column to trips table...")
    if not check_column_exists(client, "trips", "user_id"):
        client.execute("ALTER TABLE trips ADD COLUMN user_id TEXT")
        print("   ✓ Added user_id column to trips")
    else:
        print("   ⚠ Column user_id already exists in trips")

    # Create index on trips.user_id for performance
    print("\n8. Creating index on trips.user_id...")
    try:
        client.execute("CREATE INDEX IF NOT EXISTS trips_user_id_idx ON trips(user_id)")
        print("   ✓ Created index on trips.user_id")
    except Exception as e:
        print(f"   ⚠ Warning: {e}")

    # Commit all changes
    client.commit()
    print("\n" + "=" * 60)
    print("✓ Migration completed successfully!")
    print("\nNext steps:")
    print("1. Generate JWT_SECRET_KEY: openssl rand -hex 32")
    print("2. Generate ENCRYPTION_KEY: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
    print("3. Add these to your .env file")


if __name__ == "__main__":
    run_migration()
