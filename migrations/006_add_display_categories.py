#!/usr/bin/env python3
"""Add display_categories column to users table.

Stores a JSON array of transit category names that controls which
categories appear on the dashboard (vs being folded into "Other").

Usage:
    uv run python migrations/006_add_display_categories.py          # dry run
    uv run python migrations/006_add_display_categories.py --apply  # apply
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply migration")
    args = parser.parse_args(argv)

    initialize_database()
    client = get_turso_client()

    if _column_exists(client, "users", "display_categories"):
        print("display_categories column already exists — nothing to do")
        return 0

    if not args.apply:
        print("[DRY RUN] Would add display_categories TEXT to users")
        return 0

    client.execute("ALTER TABLE users ADD COLUMN display_categories TEXT")
    print("Added display_categories column to users table")
    return 0


if __name__ == "__main__":
    sys.exit(main())
