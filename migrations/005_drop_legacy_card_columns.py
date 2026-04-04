#!/usr/bin/env python3
"""Drop vestigial columns from clipper_cards.

Removes card_serial, credentials_encrypted, and is_primary — these moved
to the users table or were dropped entirely in the identity merge.

Usage:
    uv run python migrations/005_drop_legacy_card_columns.py          # dry run
    uv run python migrations/005_drop_legacy_card_columns.py --apply   # apply
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
    for col in ("card_serial", "credentials_encrypted", "is_primary"):
        if not _column_exists(client, "clipper_cards", col):
            print(f"  Column clipper_cards.{col} already gone — skipping")
        elif dry_run:
            print(f"  Would drop column clipper_cards.{col}")
        else:
            client.execute(f"ALTER TABLE clipper_cards DROP COLUMN {col}")
            print(f"  Dropped column clipper_cards.{col}")

    if not dry_run:
        client.commit()
        print("\nMigration applied.")
    else:
        print("\nDry run complete. Pass --apply to execute.")


def main():
    parser = argparse.ArgumentParser(description="Drop legacy card columns")
    parser.add_argument("--apply", action="store_true", help="Apply the migration")
    args = parser.parse_args()

    initialize_database()
    client = get_turso_client()
    migrate(client, dry_run=not args.apply)


if __name__ == "__main__":
    sys.exit(main() or 0)
