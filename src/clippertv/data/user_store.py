"""User and Clipper card data access layer."""

from typing import Optional, List
from datetime import datetime
import uuid
from .models import User, UserCreate, ClipperCard, ClipperCardCreate
from ..auth.service import AuthService
from ..auth.crypto import CredentialEncryption


class UserStore:
    """Manage user accounts and Clipper cards."""

    def __init__(
        self,
        client,
        auth_service: AuthService,
        crypto: CredentialEncryption
    ):
        """
        Initialize user store.

        Args:
            client: Turso database client
            auth_service: Authentication service for password hashing
            crypto: Credential encryption service
        """
        self.client = client
        self.auth = auth_service
        self.crypto = crypto

    def create_user(self, user_data: UserCreate) -> User:
        """
        Register new user account.

        Args:
            user_data: User registration data

        Returns:
            Created User instance

        Raises:
            ValueError: If email already exists
        """
        # Check if user already exists
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
            [user_id, user_data.email, password_hash, user_data.name, now, now]
        )
        self.client.commit()

        return self.get_user_by_id(user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Find user by email address.

        Args:
            email: User email address

        Returns:
            User instance if found, None otherwise
        """
        result = self.client.execute(
            "SELECT id, email, name, created_at, updated_at FROM users WHERE email = ?",
            [email]
        )
        row = result.fetchone()

        if not row:
            return None

        return User(
            id=row[0],
            email=row[1],
            name=row[2],
            created_at=datetime.fromisoformat(row[3]) if row[3] else datetime.now(),
            updated_at=datetime.fromisoformat(row[4]) if row[4] else datetime.now()
        )

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Find user by ID.

        Args:
            user_id: Unique user identifier

        Returns:
            User instance if found, None otherwise
        """
        result = self.client.execute(
            "SELECT id, email, name, created_at, updated_at FROM users WHERE id = ?",
            [user_id]
        )
        row = result.fetchone()

        if not row:
            return None

        return User(
            id=row[0],
            email=row[1],
            name=row[2],
            created_at=datetime.fromisoformat(row[3]) if row[3] else datetime.now(),
            updated_at=datetime.fromisoformat(row[4]) if row[4] else datetime.now()
        )

    def verify_user_credentials(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user with email and password.

        Args:
            email: User email address
            password: Plain text password

        Returns:
            User instance if credentials are valid, None otherwise
        """
        result = self.client.execute(
            "SELECT id, email, name, password_hash, created_at, updated_at FROM users WHERE email = ?",
            [email]
        )
        row = result.fetchone()

        if not row:
            return None

        password_hash = row[3]

        if not self.auth.verify_password(password, password_hash):
            return None

        return User(
            id=row[0],
            email=row[1],
            name=row[2],
            created_at=datetime.fromisoformat(row[4]) if row[4] else datetime.now(),
            updated_at=datetime.fromisoformat(row[5]) if row[5] else datetime.now()
        )

    def add_clipper_card(
        self,
        user_id: str,
        card_data: ClipperCardCreate
    ) -> ClipperCard:
        """
        Associate Clipper card with user account.

        Args:
            user_id: ID of the user
            card_data: Clipper card registration data

        Returns:
            Created ClipperCard instance

        Raises:
            ValueError: If card already exists for this user
        """
        # Check if card already exists for this user
        existing = self.client.execute(
            "SELECT id FROM clipper_cards WHERE user_id = ? AND card_number = ?",
            [user_id, card_data.card_number]
        ).fetchone()

        if existing:
            raise ValueError(f"Card {card_data.card_number} already exists for this user")

        card_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # Encrypt credentials if provided
        credentials_encrypted = None
        if card_data.credentials:
            credentials_encrypted = self.crypto.encrypt_credentials(
                card_data.credentials["username"],
                card_data.credentials["password"]
            )

        # If this is primary card, unset other primary cards for this user
        if card_data.is_primary:
            self.client.execute(
                "UPDATE clipper_cards SET is_primary = 0 WHERE user_id = ?",
                [user_id]
            )

        self.client.execute(
            """
            INSERT INTO clipper_cards (id, user_id, card_number, rider_name, credentials_encrypted, is_primary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [card_id, user_id, card_data.card_number, card_data.rider_name, credentials_encrypted, card_data.is_primary, now]
        )
        self.client.commit()

        return self.get_clipper_card(card_id)

    def get_clipper_card(self, card_id: str) -> Optional[ClipperCard]:
        """
        Get Clipper card by ID.

        Args:
            card_id: Unique card identifier

        Returns:
            ClipperCard instance if found, None otherwise
        """
        result = self.client.execute(
            """
            SELECT id, user_id, card_number, rider_name, credentials_encrypted, is_primary, created_at
            FROM clipper_cards WHERE id = ?
            """,
            [card_id]
        )
        row = result.fetchone()

        if not row:
            return None

        return ClipperCard(
            id=row[0],
            user_id=row[1],
            card_number=row[2],
            rider_name=row[3],
            credentials_encrypted=row[4],
            is_primary=bool(row[5]),
            created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now()
        )

    def get_user_clipper_cards(self, user_id: str) -> List[ClipperCard]:
        """
        Get all Clipper cards for a user.

        Args:
            user_id: Unique user identifier

        Returns:
            List of ClipperCard instances
        """
        result = self.client.execute(
            """
            SELECT id, user_id, card_number, rider_name, credentials_encrypted, is_primary, created_at
            FROM clipper_cards WHERE user_id = ? ORDER BY is_primary DESC, created_at ASC
            """,
            [user_id]
        )

        cards = []
        for row in result.fetchall():
            cards.append(ClipperCard(
                id=row[0],
                user_id=row[1],
                card_number=row[2],
                rider_name=row[3],
                credentials_encrypted=row[4],
                is_primary=bool(row[5]),
                created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now()
            ))

        return cards

    def get_decrypted_credentials(self, card_id: str) -> Optional[dict]:
        """
        Get decrypted Clipper credentials for automated downloads.

        Args:
            card_id: Unique card identifier

        Returns:
            Dictionary with username and password if credentials exist, None otherwise
        """
        card = self.get_clipper_card(card_id)
        if not card or not card.credentials_encrypted:
            return None

        return self.crypto.decrypt_credentials(card.credentials_encrypted)

    def update_clipper_card_primary(self, card_id: str, is_primary: bool) -> None:
        """
        Update primary status of a Clipper card.

        Args:
            card_id: Unique card identifier
            is_primary: Whether this should be the primary card
        """
        card = self.get_clipper_card(card_id)
        if not card:
            raise ValueError(f"Card {card_id} not found")

        # If setting as primary, unset other primary cards for this user
        if is_primary:
            self.client.execute(
                "UPDATE clipper_cards SET is_primary = 0 WHERE user_id = ?",
                [card.user_id]
            )

        self.client.execute(
            "UPDATE clipper_cards SET is_primary = ? WHERE id = ?",
            [is_primary, card_id]
        )
        self.client.commit()

    def delete_clipper_card(self, card_id: str) -> None:
        """
        Delete a Clipper card.

        Args:
            card_id: Unique card identifier
        """
        self.client.execute(
            "DELETE FROM clipper_cards WHERE id = ?",
            [card_id]
        )
        self.client.commit()
