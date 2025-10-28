"""Integration tests for user store."""

import pytest
from clippertv.data.user_store import UserStore
from clippertv.data.models import UserCreate, ClipperCardCreate
from clippertv.auth.service import AuthService
from clippertv.auth.crypto import CredentialEncryption
from clippertv.data.turso_client import get_turso_client


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
    return UserStore(
        client=db_client,
        auth_service=auth_service,
        crypto=crypto_service
    )


@pytest.fixture
def test_user_data():
    """Create test user data."""
    return UserCreate(
        email=f"test_{pytest.test_counter}@example.com",
        password="secure_password_123",
        name="Test User"
    )


# Counter for unique test emails
pytest.test_counter = 0


class TestUserStore:
    """Integration tests for UserStore."""

    def test_create_user(self, user_store, test_user_data):
        """Test creating a new user."""
        pytest.test_counter += 1

        user = user_store.create_user(test_user_data)

        assert user.id
        assert user.email == test_user_data.email
        assert user.name == test_user_data.name
        assert user.created_at
        assert user.updated_at

    def test_create_duplicate_user_raises_error(self, user_store):
        """Test that creating duplicate user raises error."""
        pytest.test_counter += 1

        user_data = UserCreate(
            email=f"duplicate_{pytest.test_counter}@example.com",
            password="password123",
            name="Duplicate User"
        )

        # Create first user
        user_store.create_user(user_data)

        # Attempt to create duplicate should raise error
        with pytest.raises(ValueError, match="already exists"):
            user_store.create_user(user_data)

    def test_get_user_by_email(self, user_store):
        """Test retrieving user by email."""
        pytest.test_counter += 1

        # Create user
        user_data = UserCreate(
            email=f"findme_{pytest.test_counter}@example.com",
            password="password123",
            name="Find Me"
        )
        created_user = user_store.create_user(user_data)

        # Retrieve user
        found_user = user_store.get_user_by_email(user_data.email)

        assert found_user is not None
        assert found_user.id == created_user.id
        assert found_user.email == user_data.email

    def test_get_user_by_email_not_found(self, user_store):
        """Test retrieving non-existent user returns None."""
        user = user_store.get_user_by_email("nonexistent@example.com")
        assert user is None

    def test_get_user_by_id(self, user_store):
        """Test retrieving user by ID."""
        pytest.test_counter += 1

        # Create user
        user_data = UserCreate(
            email=f"findbyid_{pytest.test_counter}@example.com",
            password="password123"
        )
        created_user = user_store.create_user(user_data)

        # Retrieve user by ID
        found_user = user_store.get_user_by_id(created_user.id)

        assert found_user is not None
        assert found_user.id == created_user.id
        assert found_user.email == user_data.email

    def test_verify_user_credentials_success(self, user_store):
        """Test successful credential verification."""
        pytest.test_counter += 1

        # Create user
        user_data = UserCreate(
            email=f"verify_{pytest.test_counter}@example.com",
            password="correct_password"
        )
        created_user = user_store.create_user(user_data)

        # Verify correct credentials
        verified_user = user_store.verify_user_credentials(
            email=user_data.email,
            password="correct_password"
        )

        assert verified_user is not None
        assert verified_user.id == created_user.id

    def test_verify_user_credentials_wrong_password(self, user_store):
        """Test credential verification with wrong password."""
        pytest.test_counter += 1

        # Create user
        user_data = UserCreate(
            email=f"wrongpass_{pytest.test_counter}@example.com",
            password="correct_password"
        )
        user_store.create_user(user_data)

        # Verify with wrong password
        verified_user = user_store.verify_user_credentials(
            email=user_data.email,
            password="wrong_password"
        )

        assert verified_user is None

    def test_verify_user_credentials_nonexistent_email(self, user_store):
        """Test credential verification with non-existent email."""
        verified_user = user_store.verify_user_credentials(
            email="nonexistent@example.com",
            password="any_password"
        )

        assert verified_user is None


class TestClipperCardStore:
    """Integration tests for Clipper card operations."""

    def test_add_clipper_card(self, user_store):
        """Test adding a Clipper card to a user."""
        pytest.test_counter += 1

        # Create user first
        user_data = UserCreate(
            email=f"carduser_{pytest.test_counter}@example.com",
            password="password123"
        )
        user = user_store.create_user(user_data)

        # Add clipper card
        card_data = ClipperCardCreate(
            card_number="123456789",
            rider_name="Test Card",
            is_primary=True
        )
        card = user_store.add_clipper_card(user.id, card_data)

        assert card.id
        assert card.user_id == user.id
        assert card.card_number == "123456789"
        assert card.rider_name == "Test Card"
        assert card.is_primary is True

    def test_add_clipper_card_with_credentials(self, user_store):
        """Test adding Clipper card with encrypted credentials."""
        pytest.test_counter += 1

        # Create user
        user_data = UserCreate(
            email=f"credcard_{pytest.test_counter}@example.com",
            password="password123"
        )
        user = user_store.create_user(user_data)

        # Add card with credentials
        card_data = ClipperCardCreate(
            card_number="987654321",
            rider_name="Card with Creds",
            credentials={"username": "clipper_user", "password": "clipper_pass"}
        )
        card = user_store.add_clipper_card(user.id, card_data)

        assert card.credentials_encrypted is not None

        # Verify credentials can be decrypted
        decrypted = user_store.get_decrypted_credentials(card.id)
        assert decrypted is not None
        assert decrypted["username"] == "clipper_user"
        assert decrypted["password"] == "clipper_pass"

    def test_add_duplicate_card_raises_error(self, user_store):
        """Test that adding duplicate card raises error."""
        pytest.test_counter += 1

        # Create user
        user_data = UserCreate(
            email=f"dupcard_{pytest.test_counter}@example.com",
            password="password123"
        )
        user = user_store.create_user(user_data)

        # Add first card
        card_data = ClipperCardCreate(
            card_number="111222333",
            rider_name="First Card"
        )
        user_store.add_clipper_card(user.id, card_data)

        # Attempt to add duplicate
        with pytest.raises(ValueError, match="already exists"):
            user_store.add_clipper_card(user.id, card_data)

    def test_get_user_clipper_cards(self, user_store):
        """Test retrieving all cards for a user."""
        pytest.test_counter += 1

        # Create user
        user_data = UserCreate(
            email=f"multicards_{pytest.test_counter}@example.com",
            password="password123"
        )
        user = user_store.create_user(user_data)

        # Add multiple cards
        card1 = ClipperCardCreate(
            card_number="111111111",
            rider_name="Card 1",
            is_primary=False
        )
        card2 = ClipperCardCreate(
            card_number="222222222",
            rider_name="Card 2",
            is_primary=True
        )

        user_store.add_clipper_card(user.id, card1)
        user_store.add_clipper_card(user.id, card2)

        # Get all cards
        cards = user_store.get_user_clipper_cards(user.id)

        assert len(cards) == 2
        # Primary card should be first
        assert cards[0].is_primary is True
        assert cards[0].rider_name == "Card 2"

    def test_update_primary_card(self, user_store):
        """Test updating primary card status."""
        pytest.test_counter += 1

        # Create user
        user_data = UserCreate(
            email=f"primarycard_{pytest.test_counter}@example.com",
            password="password123"
        )
        user = user_store.create_user(user_data)

        # Add two cards
        card1_data = ClipperCardCreate(
            card_number="333333333",
            rider_name="Card 1",
            is_primary=True
        )
        card2_data = ClipperCardCreate(
            card_number="444444444",
            rider_name="Card 2",
            is_primary=False
        )

        card1 = user_store.add_clipper_card(user.id, card1_data)
        card2 = user_store.add_clipper_card(user.id, card2_data)

        # Update card2 to be primary
        user_store.update_clipper_card_primary(card2.id, True)

        # Verify card2 is now primary and card1 is not
        updated_card2 = user_store.get_clipper_card(card2.id)
        updated_card1 = user_store.get_clipper_card(card1.id)

        assert updated_card2.is_primary is True
        assert updated_card1.is_primary is False

    def test_delete_clipper_card(self, user_store):
        """Test deleting a Clipper card."""
        pytest.test_counter += 1

        # Create user
        user_data = UserCreate(
            email=f"deletecard_{pytest.test_counter}@example.com",
            password="password123"
        )
        user = user_store.create_user(user_data)

        # Add card
        card_data = ClipperCardCreate(
            card_number="555555555",
            rider_name="Card to Delete"
        )
        card = user_store.add_clipper_card(user.id, card_data)

        # Delete card
        user_store.delete_clipper_card(card.id)

        # Verify card is deleted
        deleted_card = user_store.get_clipper_card(card.id)
        assert deleted_card is None
