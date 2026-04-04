#!/usr/bin/env python3
"""Merge Clipper identity with ClipperTV identity.

Adds credentials_encrypted and needs_reauth columns to the users table,
then copies Clipper credentials from clipper_cards to users.

Usage:
    uv run python migrations/004_clipper_identity.py          # dry run
    uv run python migrations/004_clipper_identity.py --apply   # apply
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from clippertv.data.turso_client import (  # noqa: E402
    get_turso_client,
    initialize_database,
)


def _column_exists(client, table: str, column: str) -> bool:
    result = client.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in result.fetchall())


def migrate(client, *, dry_run: bool = True) -> None:
    # Add new columns to users
    for col, typedef in [
        ("credentials_encrypted", "TEXT"),
        ("needs_reauth", "INTEGER DEFAULT 0"),
    ]:
        if _column_exists(client, "users", col):
            print(f"  Column users.{col} already exists — skipping")
        elif dry_run:
            print(f"  Would add column users.{col} ({typedef})")
        else:
            client.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")
            print(f"  Added column users.{col}")

    # Copy credentials from first card to user
    users = client.execute("SELECT id, email FROM users").fetchall()
    for user_id, email in users:
        has_creds = client.execute(
            "SELECT credentials_encrypted FROM users WHERE id = ?", [user_id]
        ).fetchone()
        if has_creds and has_creds[0]:
            print(f"  User {email}: already has credentials — skipping")
            continue

        card_creds = client.execute(
            "SELECT credentials_encrypted FROM clipper_cards"
            " WHERE user_id = ? AND credentials_encrypted IS NOT NULL"
            " LIMIT 1",
            [user_id],
        ).fetchone()
        if not card_creds:
            print(f"  User {email}: no card credentials to copy")
            continue

        if dry_run:
            print(f"  Would copy credentials from card to user {email}")
        else:
            client.execute(
                "UPDATE users SET credentials_encrypted = ? WHERE id = ?",
                [card_creds[0], user_id],
            )
            print(f"  Copied credentials to user {email}")

    if not dry_run:
        client.commit()
        print("\nMigration applied.")
    else:
        print("\nDry run complete. Pass --apply to execute.")


def main():
    parser = argparse.ArgumentParser(description="Merge Clipper identity migration")
    parser.add_argument("--apply", action="store_true", help="Apply the migration")
    args = parser.parse_args()

    initialize_database()
    client = get_turso_client()
    migrate(client, dry_run=not args.apply)


if __name__ == "__main__":
    sys.exit(main() or 0)
