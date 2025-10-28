"""Authentication service using JWT tokens."""

from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
from ..data.models import AuthToken


class AuthService:
    """Handles user authentication and token management."""

    def __init__(self, secret_key: str, algorithm: str = "HS256", token_expiry_days: int = 7):
        """
        Initialize authentication service.

        Args:
            secret_key: Secret key for JWT encoding/decoding
            algorithm: JWT algorithm (default: HS256)
            token_expiry_days: Number of days until token expires (default: 7)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry = timedelta(days=token_expiry_days)

    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Plain text password
            password_hash: Hashed password to compare against

        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except Exception:
            return False

    def create_access_token(self, user_id: str, email: str) -> AuthToken:
        """
        Generate JWT access token.

        Args:
            user_id: Unique user identifier
            email: User email address

        Returns:
            AuthToken containing access token and metadata
        """
        now = datetime.now(timezone.utc)
        expire = now + self.token_expiry

        payload = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "iat": now
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        return AuthToken(
            access_token=token,
            expires_in=int(self.token_expiry.total_seconds())
        )

    def verify_token(self, token: str) -> Optional[dict]:
        """
        Verify and decode JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def get_user_id_from_token(self, token: str) -> Optional[str]:
        """
        Extract user ID from token.

        Args:
            token: JWT token string

        Returns:
            User ID if token is valid, None otherwise
        """
        payload = self.verify_token(token)
        if payload:
            return payload.get("sub")
        return None
