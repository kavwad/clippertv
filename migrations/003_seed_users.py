#!/usr/bin/env python3
"""Seed users and clipper card credentials from clipper.toml.

Usage:
    uv run python migrations/003_seed_users.py \
        --password kaveh:PASS --password bree:PASS

Or interactively (will prompt for each user's app password):
    uv run python migrations/003_seed_users.py
"""

from __future__ import annotations

import argparse
import getpass
import sys
import tomllib

from dotenv import load_dotenv

load_dotenv()

from clippertv.data.models import ClipperCardCreate, UserCreate  # noqa: E402
from clippertv.data.user_store import UserStore  # noqa: E402


def _load_toml(path: str = "clipper.toml") -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def main():
    parser = argparse.ArgumentParser(description="Seed users from clipper.toml")
    parser.add_argument(
        "--password",
        action="append",
        default=[],
        help="name:password pair (e.g. kaveh:mypass). Prompted if omitted.",
    )
    parser.add_argument(
        "--config",
        default="clipper.toml",
        help="Path to clipper.toml",
    )
    parser.add_argument(
        "--clean-test-data",
        action="store_true",
        help="Remove test users (emails matching *@example.com)",
    )
    args = parser.parse_args()

    # Parse --password flags into dict
    passwords: dict[str, str] = {}
    for p in args.password:
        if ":" not in p:
            sys.exit(f"Invalid --password format: {p!r} (expected name:password)")
        name, pw = p.split(":", 1)
        passwords[name.lower()] = pw

    config = _load_toml(args.config)
    store = UserStore.from_env()

    if args.clean_test_data:
        _clean_test_data(store)

    for account in config.get("accounts", []):
        name = account["name"]
        email = account["email"]
        account_numbers = account.get("accounts", [])
        card_serials = account.get("cards", [])
        clipper_password = account.get("password", "")

        # Get or prompt for app password
        app_password = passwords.get(name.lower())
        if not app_password:
            app_password = getpass.getpass(f"App password for {name} ({email}): ")
            if not app_password:
                print(f"  Skipping {name} (no password)")
                continue

        # Create or update user
        existing = store.get_user_by_email(email)
        if existing:
            print(f"  User {name} ({email}) exists — updating password")
            pw_hash = store.auth.hash_password(app_password)
            store.client.execute(
                "UPDATE users SET password_hash = ?, name = ? WHERE id = ?",
                [pw_hash, name.capitalize(), existing.id],
            )
            store.client.commit()
            user = existing
        else:
            print(f"  Creating user {name} ({email})")
            user = store.create_user(
                UserCreate(
                    email=email,
                    password=app_password,
                    name=name.capitalize(),
                )
            )

        # Add clipper cards (one per account number)
        for i, acct_num in enumerate(account_numbers):
            serial = card_serials[i] if i < len(card_serials) else None

            # Check if card already exists
            existing_cards = store.get_user_clipper_cards(user.id)
            if any(c.account_number == acct_num for c in existing_cards):
                # Update credentials on existing card
                card = next(c for c in existing_cards if c.account_number == acct_num)
                if clipper_password and email:
                    store.update_card_credentials(card.id, email, clipper_password)
                    print(f"    Card {acct_num} — updated credentials")
                else:
                    print(f"    Card {acct_num} — already exists, skipped")
                continue

            rider_name = f"{name.capitalize()} Card {i + 1}"
            creds = (
                {"username": email, "password": clipper_password}
                if clipper_password
                else None
            )
            card_data = ClipperCardCreate(
                account_number=acct_num,
                card_serial=serial,
                rider_name=rider_name,
                credentials=creds,
                is_primary=(i == 0),
            )
            store.add_clipper_card(user.id, card_data)
            print(f"    Card {acct_num} (serial {serial}) — created")

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
    main()
