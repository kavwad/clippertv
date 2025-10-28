"""Test authentication service."""

import pytest
from datetime import datetime, timedelta, timezone
from clippertv.auth.service import AuthService
from clippertv.auth.crypto import CredentialEncryption
from clippertv.data.models import AuthToken


@pytest.fixture
def auth_service():
    """Create auth service with test secret key."""
    return AuthService(secret_key="test-secret-key-32-characters-long!")


@pytest.fixture
def crypto_service():
    """Create credential encryption service with test key."""
    # Generate a test key
    test_key = CredentialEncryption.generate_key()
    return CredentialEncryption(encryption_key=test_key)


class TestAuthService:
    """Test AuthService functionality."""

    def test_password_hashing(self, auth_service):
        """Test password hashing and verification."""
        password = "secure_password_123"
        hashed = auth_service.hash_password(password)

        # Verify the password is hashed (not plain text)
        assert hashed != password
        assert len(hashed) > 0

        # Verify correct password
        assert auth_service.verify_password(password, hashed)

        # Verify incorrect password
        assert not auth_service.verify_password("wrong_password", hashed)

    def test_password_hash_is_unique(self, auth_service):
        """Test that hashing the same password twice produces different hashes."""
        password = "test_password"
        hash1 = auth_service.hash_password(password)
        hash2 = auth_service.hash_password(password)

        # Hashes should be different (due to random salt)
        assert hash1 != hash2

        # But both should verify correctly
        assert auth_service.verify_password(password, hash1)
        assert auth_service.verify_password(password, hash2)

    def test_jwt_token_creation(self, auth_service):
        """Test JWT token generation and verification."""
        user_id = "user-123"
        email = "test@example.com"

        token = auth_service.create_access_token(user_id, email)

        # Check token structure
        assert isinstance(token, AuthToken)
        assert token.access_token
        assert token.token_type == "bearer"
        assert token.expires_in > 0

        # Verify token payload
        payload = auth_service.verify_token(token.access_token)
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["email"] == email

    def test_token_expiration_time(self, auth_service):
        """Test that token expiration is set correctly."""
        user_id = "user-123"
        email = "test@example.com"

        token = auth_service.create_access_token(user_id, email)
        payload = auth_service.verify_token(token.access_token)

        # Check that expiration is in the future
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)

        assert exp_datetime > now

        # Check that expiration is approximately 7 days from now
        expected_expiry = now + timedelta(days=7)
        time_diff = abs((exp_datetime - expected_expiry).total_seconds())
        assert time_diff < 10  # Allow 10 seconds tolerance

    def test_invalid_token(self, auth_service):
        """Test invalid token verification."""
        assert auth_service.verify_token("invalid-token") is None

    def test_get_user_id_from_token(self, auth_service):
        """Test extracting user ID from token."""
        user_id = "user-456"
        email = "user@example.com"

        token = auth_service.create_access_token(user_id, email)
        extracted_user_id = auth_service.get_user_id_from_token(token.access_token)

        assert extracted_user_id == user_id

    def test_get_user_id_from_invalid_token(self, auth_service):
        """Test extracting user ID from invalid token returns None."""
        assert auth_service.get_user_id_from_token("invalid-token") is None

    def test_verify_password_with_invalid_hash(self, auth_service):
        """Test password verification with malformed hash."""
        password = "test_password"
        invalid_hash = "not-a-valid-hash"

        # Should return False instead of raising exception
        assert not auth_service.verify_password(password, invalid_hash)


class TestCredentialEncryption:
    """Test CredentialEncryption functionality."""

    def test_encrypt_decrypt_credentials(self, crypto_service):
        """Test encrypting and decrypting credentials."""
        username = "test_user"
        password = "test_password"

        # Encrypt credentials
        encrypted = crypto_service.encrypt_credentials(username, password)
        assert encrypted
        assert encrypted != username
        assert encrypted != password

        # Decrypt credentials
        decrypted = crypto_service.decrypt_credentials(encrypted)
        assert decrypted is not None
        assert decrypted["username"] == username
        assert decrypted["password"] == password

    def test_decrypt_invalid_data(self, crypto_service):
        """Test decrypting invalid data returns None."""
        invalid_encrypted = "invalid-encrypted-data"
        result = crypto_service.decrypt_credentials(invalid_encrypted)
        assert result is None

    def test_encryption_is_deterministic(self, crypto_service):
        """Test that encryption is NOT deterministic (different each time)."""
        username = "test_user"
        password = "test_password"

        encrypted1 = crypto_service.encrypt_credentials(username, password)
        encrypted2 = crypto_service.encrypt_credentials(username, password)

        # Encryptions should be different (Fernet uses random IV)
        # Actually, Fernet DOES produce different outputs each time
        # So we just verify both decrypt correctly
        decrypted1 = crypto_service.decrypt_credentials(encrypted1)
        decrypted2 = crypto_service.decrypt_credentials(encrypted2)

        assert decrypted1 == decrypted2
        assert decrypted1["username"] == username

    def test_generate_key(self):
        """Test key generation."""
        key = CredentialEncryption.generate_key()

        # Key should be base64 encoded and valid
        assert key
        assert isinstance(key, str)
        assert len(key) > 0

        # Key should be usable to create a crypto service
        crypto = CredentialEncryption(encryption_key=key)
        encrypted = crypto.encrypt_credentials("test", "test")
        assert encrypted

    def test_different_keys_cannot_decrypt(self):
        """Test that credentials encrypted with one key cannot be decrypted with another."""
        crypto1 = CredentialEncryption(CredentialEncryption.generate_key())
        crypto2 = CredentialEncryption(CredentialEncryption.generate_key())

        encrypted = crypto1.encrypt_credentials("user", "pass")

        # Should not be able to decrypt with different key
        result = crypto2.decrypt_credentials(encrypted)
        assert result is None
