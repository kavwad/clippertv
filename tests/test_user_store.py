"""Integration tests for user store."""

from uuid import uuid4

import pytest

from clippertv.auth.crypto import CredentialEncryption
from clippertv.auth.service import AuthService
from clippertv.data.turso_client import get_turso_client
from clippertv.data.user_store import UserStore


@pytest.fixture
def db_client():
    """Get database client for testing."""
    try:
        client = get_turso_client()
        return client
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@pytest.fixture
def auth_service():
    """Create auth service for testing."""
    return AuthService(secret_key="test-secret-key-for-user-store-testing")


@pytest.fixture
def crypto_service():
    """Create crypto service for testing."""
    test_key = CredentialEncryption.generate_key()
    return CredentialEncryption(encryption_key=test_key)


@pytest.fixture
def user_store(db_client, auth_service, crypto_service):
    """Create user store for testing."""
    return UserStore(client=db_client, auth_service=auth_service, crypto=crypto_service)


def _unique_email(prefix: str = "test") -> str:
    return f"{prefix}_{uuid4().hex[:8]}@example.com"


class TestUserStore:
    """Integration tests for UserStore."""

    def test_create_user(self, user_store):
        """Test creating a new user with Clipper credentials."""
        email = _unique_email("create")
        user = user_store.create_user(email, "clipper_password_123")

        assert user.id
        assert user.email == email
        assert user.credentials_encrypted is not None
        assert user.needs_reauth is False

    def test_create_duplicate_user_raises_error(self, user_store):
        """Test that creating duplicate user raises error."""
        email = _unique_email("duplicate")
        user_store.create_user(email, "password123")

        with pytest.raises(ValueError, match="already exists"):
            user_store.create_user(email, "password123")

    def test_get_user_by_email(self, user_store):
        """Test retrieving user by email."""
        email = _unique_email("findme")
        created = user_store.create_user(email, "password123")

        found = user_store.get_user_by_email(email)
        assert found is not None
        assert found.id == created.id

    def test_get_user_by_email_not_found(self, user_store):
        """Test retrieving non-existent user returns None."""
        assert user_store.get_user_by_email("nonexistent@example.com") is None

    def test_get_user_by_id(self, user_store):
        """Test retrieving user by ID."""
        email = _unique_email("findbyid")
        created = user_store.create_user(email, "password123")

        found = user_store.get_user_by_id(created.id)
        assert found is not None
        assert found.email == email

    def test_verify_user_credentials_success(self, user_store):
        """Test successful credential verification."""
        email = _unique_email("verify")
        created = user_store.create_user(email, "correct_password")

        verified = user_store.verify_user_credentials(email, "correct_password")
        assert verified is not None
        assert verified.id == created.id

    def test_verify_user_credentials_wrong_password(self, user_store):
        """Test credential verification with wrong password."""
        email = _unique_email("wrongpass")
        user_store.create_user(email, "correct_password")

        assert user_store.verify_user_credentials(email, "wrong_password") is None

    def test_verify_user_credentials_nonexistent_email(self, user_store):
        """Test credential verification with non-existent email."""
        assert user_store.verify_user_credentials("nope@example.com", "any") is None

    def test_update_user_credentials(self, user_store):
        """Test updating credentials after Clipper re-auth."""
        email = _unique_email("update_creds")
        user = user_store.create_user(email, "old_password")

        user_store.update_user_credentials(user.id, email, "new_password")

        # Old password should fail, new should pass
        assert user_store.verify_user_credentials(email, "old_password") is None
        assert user_store.verify_user_credentials(email, "new_password") is not None

        # Encrypted creds should also be updated
        updated = user_store.get_user_by_id(user.id)
        creds = user_store.decrypt_user_credentials(updated)
        assert creds["password"] == "new_password"

    def test_set_needs_reauth(self, user_store):
        """Test toggling needs_reauth flag."""
        email = _unique_email("reauth")
        user = user_store.create_user(email, "password123")
        assert user.needs_reauth is False

        user_store.set_needs_reauth(user.id, True)
        updated = user_store.get_user_by_id(user.id)
        assert updated.needs_reauth is True

        user_store.set_needs_reauth(user.id, False)
        updated = user_store.get_user_by_id(user.id)
        assert updated.needs_reauth is False

    def test_get_all_users_with_credentials(self, user_store):
        """Test retrieving users that have stored credentials."""
        email = _unique_email("with_creds")
        user_store.create_user(email, "password123")

        users = user_store.get_all_users_with_credentials()
        assert any(u.email == email for u in users)

    def test_decrypt_user_credentials(self, user_store):
        """Test decrypting stored Clipper credentials."""
        email = _unique_email("decrypt")
        user = user_store.create_user(email, "my_clipper_pass")

        creds = user_store.decrypt_user_credentials(user)
        assert creds is not None
        assert creds["username"] == email
        assert creds["password"] == "my_clipper_pass"


class TestClipperCardStore:
    """Integration tests for Clipper card operations."""

    def test_discover_and_sync_cards(self, user_store):
        """Test auto-discovery of cards from account numbers."""
        email = _unique_email("discover")
        user = user_store.create_user(email, "password123")

        cards = user_store.discover_and_sync_cards(user.id, ["111111111", "222222222"])

        assert len(cards) == 2
        assert cards[0].rider_name == "Card 1"
        assert cards[1].rider_name == "Card 2"
        assert cards[0].account_number == "111111111"

    def test_discover_skips_existing_cards(self, user_store):
        """Test that discovery doesn't duplicate existing cards."""
        email = _unique_email("no_dup")
        user = user_store.create_user(email, "password123")

        # First discovery
        user_store.discover_and_sync_cards(user.id, ["111111111"])

        # Second discovery with overlap + new
        cards = user_store.discover_and_sync_cards(user.id, ["111111111", "333333333"])

        assert len(cards) == 2
        assert cards[1].rider_name == "Card 2"

    def test_update_card_rider_name(self, user_store):
        """Test renaming a card."""
        email = _unique_email("rename")
        user = user_store.create_user(email, "password123")
        cards = user_store.discover_and_sync_cards(user.id, ["123456789"])

        user_store.update_card_rider_name(cards[0].id, "My BART Card")

        updated = user_store.get_clipper_card(cards[0].id)
        assert updated.rider_name == "My BART Card"

    def test_delete_clipper_card(self, user_store):
        """Test deleting a Clipper card."""
        email = _unique_email("delete")
        user = user_store.create_user(email, "password123")
        cards = user_store.discover_and_sync_cards(user.id, ["555555555"])

        user_store.delete_clipper_card(cards[0].id)
        assert user_store.get_clipper_card(cards[0].id) is None

    def test_get_user_clipper_cards_empty(self, user_store):
        """Test getting cards for user with no cards."""
        email = _unique_email("nocards")
        user = user_store.create_user(email, "password123")

        cards = user_store.get_user_clipper_cards(user.id)
        assert cards == []
