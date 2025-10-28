#!/usr/bin/env python3
"""
Setup users with Clipper credentials in the database.
Run this once to initialize user accounts for the scheduler.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clippertv.auth.service import AuthService
from clippertv.auth.crypto import CredentialEncryption
from clippertv.data.user_store import UserStore
from clippertv.data.models import UserCreate, ClipperCardCreate
from clippertv.data.turso_client import get_turso_client


def main():
    print("Setting up ClipperTV users...")

    # Get keys from environment
    jwt_secret = os.getenv("JWT_SECRET_KEY")
    encryption_key = os.getenv("ENCRYPTION_KEY")

    if not jwt_secret or not encryption_key:
        print("ERROR: JWT_SECRET_KEY and ENCRYPTION_KEY must be set in environment")
        print("Run with: JWT_SECRET_KEY=... ENCRYPTION_KEY=... python scripts/setup_users.py")
        sys.exit(1)

    # Initialize services
    client = get_turso_client()
    auth = AuthService(secret_key=jwt_secret)
    crypto = CredentialEncryption(encryption_key=encryption_key)
    user_store = UserStore(client, auth, crypto)

    # User data from secrets.toml
    users = [
        {
            "name": "Bree",
            "email": "bbaccaglini@gmail.com",
            "password": "muniforever",  # App password
            "cards": [
                {
                    "card_number": "1215697747",
                    "rider_name": "Bree Card 1",
                    "clipper_email": "bbaccaglini@gmail.com",
                    "clipper_password": "dockes-woxziv-Cufpi3"
                },
                {
                    "card_number": "1208039841",
                    "rider_name": "Bree Card 2",
                    "clipper_email": "bbaccaglini@gmail.com",
                    "clipper_password": "dockes-woxziv-Cufpi3"
                }
            ]
        },
        {
            "name": "Kaveh",
            "email": "kavwad@gmail.com",
            "password": "muniforever",  # App password
            "cards": [
                {
                    "card_number": "1202425091",
                    "rider_name": "Kaveh Card 1",
                    "clipper_email": "kavwad@gmail.com",
                    "clipper_password": "byxTuw-tenpuw-1vospo"
                },
                {
                    "card_number": "1401491737",
                    "rider_name": "Kaveh Card 2",
                    "clipper_email": "kavwad@gmail.com",
                    "clipper_password": "byxTuw-tenpuw-1vospo"
                }
            ]
        }
    ]

    for user_data in users:
        email = user_data["email"]
        name = user_data["name"]

        # Check if user already exists
        existing = user_store.get_user_by_email(email)
        if existing:
            print(f"✓ User '{name}' ({email}) already exists (ID: {existing.id})")
            user_id = existing.id
        else:
            # Create user
            print(f"Creating user '{name}' ({email})...")
            user_create = UserCreate(
                email=email,
                name=name,
                password=user_data["password"]
            )
            user = user_store.create_user(user_create)
            print(f"✓ Created user '{name}' (ID: {user.id})")
            user_id = user.id

        # Add Clipper cards
        for card_data in user_data["cards"]:
            card_number = card_data["card_number"]

            # Check if card already exists
            existing_cards = user_store.get_user_clipper_cards(user_id)
            if any(c.card_number == card_number for c in existing_cards):
                print(f"  ✓ Card {card_number} already exists")
            else:
                print(f"  Adding card {card_number}...")
                card_create = ClipperCardCreate(
                    card_number=card_number,
                    rider_name=card_data["rider_name"],
                    credentials={
                        "username": card_data["clipper_email"],
                        "password": card_data["clipper_password"]
                    }
                )
                user_store.add_clipper_card(user_id, card_create)
                print(f"  ✓ Added card {card_number}")

    print("\n✅ Setup complete!")
    print("\nUser accounts:")
    print("  - Email: bbaccaglini@gmail.com, Password: muniforever")
    print("  - Email: kavwad@gmail.com, Password: muniforever")


if __name__ == "__main__":
    main()
