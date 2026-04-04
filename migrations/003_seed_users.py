#!/usr/bin/env python3
"""Seed users and clipper cards from clipper.toml.

Usage:
    uv run python migrations/003_seed_users.py

This script creates users using Clipper credentials from clipper.toml.
The Clipper password becomes the ClipperTV password (identity merge).
"""

from __future__ import annotations

import sys
import tomllib

from dotenv import load_dotenv

load_dotenv()

from clippertv.data.user_store import UserStore  # noqa: E402


def _load_toml(path: str = "clipper.toml") -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed users from clipper.toml")
    parser.add_argument("--config", default="clipper.toml", help="Path to clipper.toml")
    parser.add_argument(
        "--clean-test-data",
        action="store_true",
        help="Remove test users (emails matching *@example.com)",
    )
    args = parser.parse_args()

    config = _load_toml(args.config)
    store = UserStore.from_env()

    if args.clean_test_data:
        _clean_test_data(store)

    for account in config.get("accounts", []):
        name = account["name"]
        email = account["email"]
        clipper_password = account.get("password", "")
        account_numbers = account.get("accounts", [])

        if not clipper_password:
            print(f"  Skipping {name} (no password in config)")
            continue

        existing = store.get_user_by_email(email)
        if existing:
            print(f"  User {name} ({email}) exists — updating credentials")
            store.update_user_credentials(existing.id, email, clipper_password)
            user = existing
        else:
            print(f"  Creating user {name} ({email})")
            user = store.create_user(email, clipper_password)

        # Sync cards from config
        if account_numbers:
            store.discover_and_sync_cards(user.id, account_numbers)
            print(f"    Synced {len(account_numbers)} card(s)")

    print("\nDone.")


def _clean_test_data(store: UserStore):
    """Remove test users and their cards."""
    result = store.client.execute(
        "SELECT id, email FROM users WHERE email LIKE '%@example.com'"
    )
    test_users = result.fetchall()
    if not test_users:
        print("No test data to clean.")
        return

    for user_id, _email in test_users:
        store.client.execute("DELETE FROM clipper_cards WHERE user_id = ?", [user_id])
        store.client.execute("DELETE FROM users WHERE id = ?", [user_id])
    store.client.commit()
    print(f"Cleaned {len(test_users)} test users.")


if __name__ == "__main__":
    sys.exit(main() or 0)
