"""Encryption utilities for sensitive data."""

from cryptography.fernet import Fernet
from typing import Optional
import json


class CredentialEncryption:
    """Encrypt/decrypt Clipper credentials."""

    def __init__(self, encryption_key: str):
        """
        Initialize credential encryption.

        Args:
            encryption_key: Fernet encryption key (base64 encoded)
        """
        self.cipher = Fernet(encryption_key.encode())

    def encrypt_credentials(self, username: str, password: str) -> str:
        """
        Encrypt Clipper login credentials.

        Args:
            username: Clipper account username
            password: Clipper account password

        Returns:
            Encrypted credentials as base64 string
        """
        data = json.dumps({"username": username, "password": password})
        encrypted = self.cipher.encrypt(data.encode())
        return encrypted.decode()

    def decrypt_credentials(self, encrypted: str) -> Optional[dict]:
        """
        Decrypt Clipper login credentials.

        Args:
            encrypted: Encrypted credentials string

        Returns:
            Dictionary with username and password, or None if decryption fails
        """
        try:
            decrypted = self.cipher.decrypt(encrypted.encode())
            data = json.loads(decrypted.decode())
            return data
        except Exception:
            return None

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64 encoded encryption key
        """
        return Fernet.generate_key().decode()
