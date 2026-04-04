"""User and Clipper card data access layer."""

import uuid
from datetime import datetime

from ..auth.crypto import CredentialEncryption
from ..auth.service import AuthService
from .models import ClipperCard, ClipperCardCreate, User, UserCreate


def _parse_dt(val) -> datetime:
    return datetime.fromisoformat(val) if val else datetime.now()


def _row_to_user(row, *, created_at_idx: int = 3, updated_at_idx: int = 4) -> User:
    return User(
        id=row[0],
        email=row[1],
        name=row[2],
        created_at=_parse_dt(row[created_at_idx]),
        updated_at=_parse_dt(row[updated_at_idx]),
    )


def _row_to_card(row) -> ClipperCard:
    return ClipperCard(
        id=row[0],
        user_id=row[1],
        account_number=row[2],
        card_serial=row[3],
        rider_name=row[4],
        credentials_encrypted=row[5],
        is_primary=bool(row[6]),
        created_at=_parse_dt(row[7]),
    )


_CARD_COLUMNS = (
    "id, user_id, account_number, card_serial, rider_name,"
    " credentials_encrypted, is_primary, created_at"
)


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

    def create_user(self, user_data: UserCreate) -> User | None:
        """Register new user account."""
        existing = self.get_user_by_email(user_data.email)
        if existing:
            raise ValueError(f"User with email {user_data.email} already exists")

        user_id = str(uuid.uuid4())
        password_hash = self.auth.hash_password(user_data.password)
        now = datetime.now().isoformat()

        self.client.execute(
            """
            INSERT INTO users (id, email, password_hash, name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [user_id, user_data.email, password_hash, user_data.name, now, now],
        )
        self.client.commit()
        return self.get_user_by_id(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        """Find user by email address."""
        result = self.client.execute(
            "SELECT id, email, name, created_at, updated_at FROM users WHERE email = ?",
            [email],
        )
        row = result.fetchone()
        return _row_to_user(row) if row else None

    def get_user_by_id(self, user_id: str) -> User | None:
        """Find user by ID."""
        result = self.client.execute(
            "SELECT id, email, name, created_at, updated_at FROM users WHERE id = ?",
            [user_id],
        )
        row = result.fetchone()
        return _row_to_user(row) if row else None

    def verify_user_credentials(self, email: str, password: str) -> User | None:
        """Authenticate user with email and password."""
        result = self.client.execute(
            "SELECT id, email, name, password_hash, created_at, updated_at"
            " FROM users WHERE email = ?",
            [email],
        )
        row = result.fetchone()
        if not row:
            return None
        if not self.auth.verify_password(password, row[3]):
            return None
        return _row_to_user(row, created_at_idx=4, updated_at_idx=5)

    # --- Clipper Cards ---

    def add_clipper_card(
        self, user_id: str, card_data: ClipperCardCreate
    ) -> ClipperCard | None:
        """Associate Clipper card with user account."""
        existing = self.client.execute(
            "SELECT id FROM clipper_cards WHERE user_id = ? AND account_number = ?",
            [user_id, card_data.account_number],
        ).fetchone()
        if existing:
            raise ValueError(
                f"Card {card_data.account_number} already exists for this user"
            )

        card_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        credentials_encrypted = None
        if card_data.credentials:
            credentials_encrypted = self.crypto.encrypt_credentials(
                card_data.credentials["username"],
                card_data.credentials["password"],
            )

        if card_data.is_primary:
            self.client.execute(
                "UPDATE clipper_cards SET is_primary = 0 WHERE user_id = ?",
                [user_id],
            )

        self.client.execute(
            """
            INSERT INTO clipper_cards
                (id, user_id, account_number, card_serial, rider_name,
                 credentials_encrypted, is_primary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                card_id,
                user_id,
                card_data.account_number,
                card_data.card_serial,
                card_data.rider_name,
                credentials_encrypted,
                card_data.is_primary,
                now,
            ],
        )
        self.client.commit()
        return self.get_clipper_card(card_id)

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
            " WHERE user_id = ? ORDER BY is_primary DESC, created_at ASC",
            [user_id],
        )
        return [_row_to_card(row) for row in result.fetchall()]

    def get_all_cards_with_credentials(self) -> list[ClipperCard]:
        """Get all clipper cards that have stored credentials."""
        result = self.client.execute(
            f"SELECT {_CARD_COLUMNS} FROM clipper_cards"
            " WHERE credentials_encrypted IS NOT NULL"
            " ORDER BY user_id, created_at ASC",
        )
        return [_row_to_card(row) for row in result.fetchall()]

    def decrypt_card_credentials(self, card: ClipperCard) -> dict | None:
        """Decrypt Clipper credentials from a card object."""
        if not card.credentials_encrypted:
            return None
        return self.crypto.decrypt_credentials(card.credentials_encrypted)

    def get_decrypted_credentials(self, card_id: str) -> dict | None:
        """Get decrypted Clipper credentials by card ID."""
        card = self.get_clipper_card(card_id)
        if not card:
            return None
        return self.decrypt_card_credentials(card)

    def update_card_credentials(
        self, card_id: str, username: str, password: str
    ) -> None:
        """Encrypt and store new Clipper credentials for a card."""
        encrypted = self.crypto.encrypt_credentials(username, password)
        self.client.execute(
            "UPDATE clipper_cards SET credentials_encrypted = ? WHERE id = ?",
            [encrypted, card_id],
        )
        self.client.commit()

    def update_clipper_card_primary(self, card_id: str, is_primary: bool) -> None:
        """Update primary status of a Clipper card."""
        card = self.get_clipper_card(card_id)
        if not card:
            raise ValueError(f"Card {card_id} not found")
        if is_primary:
            self.client.execute(
                "UPDATE clipper_cards SET is_primary = 0 WHERE user_id = ?",
                [card.user_id],
            )
        self.client.execute(
            "UPDATE clipper_cards SET is_primary = ? WHERE id = ?",
            [is_primary, card_id],
        )
        self.client.commit()

    def delete_clipper_card(self, card_id: str) -> None:
        """Delete a Clipper card."""
        self.client.execute("DELETE FROM clipper_cards WHERE id = ?", [card_id])
        self.client.commit()
