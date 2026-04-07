"""User and Clipper card data access layer."""

import uuid
from datetime import datetime

from ..auth.crypto import CredentialEncryption
from ..auth.service import AuthService
from .models import ClipperCard, User


def _parse_dt(val) -> datetime:
    return datetime.fromisoformat(val) if val else datetime.now()


def _parse_display_categories(val) -> list[str] | None:
    if not val:
        return None
    import json

    try:
        cats = json.loads(val)
        return cats if isinstance(cats, list) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _row_to_user(row) -> User:
    """Map a row from the full user SELECT to a User model.

    Expected columns: id, email, name, credentials_encrypted,
    needs_reauth, display_categories, created_at, updated_at
    """
    return User(
        id=row[0],
        email=row[1],
        name=row[2],
        credentials_encrypted=row[3],
        needs_reauth=bool(row[4]),
        display_categories=_parse_display_categories(row[5]),
        created_at=_parse_dt(row[6]),
        updated_at=_parse_dt(row[7]),
    )


_USER_COLUMNS = (
    "id, email, name, credentials_encrypted, needs_reauth,"
    " display_categories, created_at, updated_at"
)


def _row_to_card(row) -> ClipperCard:
    return ClipperCard(
        id=row[0],
        user_id=row[1],
        account_number=row[2],
        rider_name=row[3],
        created_at=_parse_dt(row[4]),
    )


_CARD_COLUMNS = "id, user_id, account_number, rider_name, created_at"


class UserStore:
    """Manage user accounts and Clipper cards."""

    def __init__(self, client, auth_service: AuthService, crypto: CredentialEncryption):
        self.client = client
        self.auth = auth_service
        self.crypto = crypto

    @classmethod
    def from_env(cls) -> "UserStore":
        """Build a UserStore from environment config."""
        from ..config import EnvConfig
        from .turso_client import get_turso_client, initialize_database

        initialize_database()
        key = EnvConfig.JWT_SECRET_KEY
        enc_key = EnvConfig.ENCRYPTION_KEY
        if not key or not enc_key:
            raise ValueError("JWT_SECRET_KEY and ENCRYPTION_KEY must be set")
        return cls(
            client=get_turso_client(),
            auth_service=AuthService(
                secret_key=key,
                algorithm=EnvConfig.JWT_ALGORITHM,
                token_expiry_days=EnvConfig.JWT_EXPIRY_DAYS,
            ),
            crypto=CredentialEncryption(encryption_key=enc_key),
        )

    # --- Users ---

    def create_user(self, email: str, password: str) -> User:
        """Register new user from Clipper credentials."""
        existing = self.get_user_by_email(email)
        if existing:
            raise ValueError(f"User with email {email} already exists")

        user_id = str(uuid.uuid4())
        password_hash = self.auth.hash_password(password)
        credentials_encrypted = self.crypto.encrypt_credentials(email, password)
        now = datetime.now().isoformat()

        self.client.execute(
            """
            INSERT INTO users
                (id, email, password_hash, name, credentials_encrypted,
                 needs_reauth, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """,
            [user_id, email, password_hash, None, credentials_encrypted, now, now],
        )
        self.client.commit()
        user = self.get_user_by_id(user_id)
        assert user is not None
        return user

    def get_user_by_email(self, email: str) -> User | None:
        """Find user by email address."""
        result = self.client.execute(
            f"SELECT {_USER_COLUMNS} FROM users WHERE email = ?",
            [email],
        )
        row = result.fetchone()
        return _row_to_user(row) if row else None

    def get_user_by_id(self, user_id: str) -> User | None:
        """Find user by ID."""
        result = self.client.execute(
            f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?",
            [user_id],
        )
        row = result.fetchone()
        return _row_to_user(row) if row else None

    def verify_user_credentials(self, email: str, password: str) -> User | None:
        """Authenticate user with email and password (bcrypt check)."""
        result = self.client.execute(
            f"SELECT password_hash, {_USER_COLUMNS} FROM users WHERE email = ?",
            [email],
        )
        row = result.fetchone()
        if not row:
            return None
        if not self.auth.verify_password(password, row[0]):
            return None
        # User columns start at index 1 (after password_hash)
        return _row_to_user(row[1:])

    def update_user_credentials(self, user_id: str, email: str, password: str) -> None:
        """Update both bcrypt hash and encrypted creds (after Clipper re-auth)."""
        password_hash = self.auth.hash_password(password)
        credentials_encrypted = self.crypto.encrypt_credentials(email, password)
        now = datetime.now().isoformat()
        self.client.execute(
            "UPDATE users SET password_hash = ?, credentials_encrypted = ?,"
            " needs_reauth = 0, updated_at = ? WHERE id = ?",
            [password_hash, credentials_encrypted, now, user_id],
        )
        self.client.commit()

    def update_display_categories(
        self, user_id: str, categories: list[str] | None
    ) -> None:
        """Update the user's display category preferences."""
        import json

        val = json.dumps(categories) if categories else None
        now = datetime.now().isoformat()
        self.client.execute(
            "UPDATE users SET display_categories = ?, updated_at = ? WHERE id = ?",
            [val, now, user_id],
        )
        self.client.commit()

    def set_needs_reauth(self, user_id: str, value: bool) -> None:
        """Toggle the needs_reauth flag on a user."""
        self.client.execute(
            "UPDATE users SET needs_reauth = ? WHERE id = ?",
            [int(value), user_id],
        )
        self.client.commit()

    def get_all_users_with_credentials(self) -> list[User]:
        """Get all users that have stored Clipper credentials."""
        result = self.client.execute(
            f"SELECT {_USER_COLUMNS} FROM users"
            " WHERE credentials_encrypted IS NOT NULL"
            " ORDER BY created_at ASC",
        )
        return [_row_to_user(row) for row in result.fetchall()]

    def decrypt_user_credentials(self, user: User) -> dict | None:
        """Decrypt Clipper credentials from a User object."""
        if not user.credentials_encrypted:
            return None
        return self.crypto.decrypt_credentials(user.credentials_encrypted)

    # --- Clipper Cards ---

    def discover_and_sync_cards(
        self, user_id: str, account_numbers: list[str]
    ) -> list[ClipperCard]:
        """Create card records for newly discovered account numbers.

        Skips account numbers that already exist for this user.
        New cards get auto-generated rider names ("Card 1", "Card 2", ...).
        Returns all cards for the user after sync.
        """
        existing = self.get_user_clipper_cards(user_id)
        existing_accounts = {c.account_number for c in existing}
        next_num = len(existing) + 1

        for acct in account_numbers:
            if acct in existing_accounts:
                continue
            card_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            self.client.execute(
                """
                INSERT INTO clipper_cards
                    (id, user_id, account_number, rider_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [card_id, user_id, acct, f"Card {next_num}", now],
            )
            next_num += 1

        self.client.commit()
        return self.get_user_clipper_cards(user_id)

    def get_clipper_card(self, card_id: str) -> ClipperCard | None:
        """Get Clipper card by ID."""
        result = self.client.execute(
            f"SELECT {_CARD_COLUMNS} FROM clipper_cards WHERE id = ?",
            [card_id],
        )
        row = result.fetchone()
        return _row_to_card(row) if row else None

    def get_user_clipper_cards(self, user_id: str) -> list[ClipperCard]:
        """Get all Clipper cards for a user."""
        result = self.client.execute(
            f"SELECT {_CARD_COLUMNS} FROM clipper_cards"
            " WHERE user_id = ? ORDER BY created_at ASC",
            [user_id],
        )
        return [_row_to_card(row) for row in result.fetchall()]

    def update_card_rider_name(self, card_id: str, rider_name: str) -> None:
        """Rename a Clipper card."""
        self.client.execute(
            "UPDATE clipper_cards SET rider_name = ? WHERE id = ?",
            [rider_name, card_id],
        )
        self.client.commit()

    def delete_clipper_card(self, card_id: str) -> None:
        """Delete a Clipper card."""
        self.client.execute("DELETE FROM clipper_cards WHERE id = ?", [card_id])
        self.client.commit()
