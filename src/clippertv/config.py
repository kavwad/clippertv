"""Configuration management for ClipperTV."""

import os
import tomllib
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel


class TransitCategories(BaseModel):
    """Transit category display configuration."""

    display_categories: List[str] = [
        "Muni Bus", "Muni Metro", "BART", "Cable Car",
        "Caltrain", "Ferry", "AC Transit", "SamTrans",
    ]

    color_map: Dict[str, str] = {
        "Muni Bus": "#BA0C2F",
        "Muni Metro": "#FDB813",
        "BART": "#0099CC",
        "Cable Car": "#8B4513",
        "Caltrain": "#6C6C6C",
        "AC Transit": "#00A55E",
        "Ferry": "#4DD0E1",
        "SamTrans": "#D3D3D3",
    }

    fallback_color: str = "#888888"

    def get_color(self, category: str) -> str:
        """Get color for a category, with fallback for unknown ones."""
        return self.color_map.get(category, self.fallback_color)


class AppConfig(BaseModel):
    """Main application configuration."""

    app_title: str = "ClipperTV"
    transit_categories: TransitCategories = TransitCategories()


config = AppConfig()


class EnvConfig:
    """Environment-based configuration for authentication and database."""

    # Database
    TURSO_DATABASE_URL: Optional[str] = os.getenv("TURSO_DATABASE_URL")
    TURSO_AUTH_TOKEN: Optional[str] = os.getenv("TURSO_AUTH_TOKEN")

    # Authentication
    JWT_SECRET_KEY: Optional[str] = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_DAYS: int = 7

    # Encryption
    ENCRYPTION_KEY: Optional[str] = os.getenv("ENCRYPTION_KEY")

    # Email (for Phase 1.5)
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "resend")
    EMAIL_API_KEY: Optional[str] = os.getenv("EMAIL_API_KEY")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "ClipperTV <reports@clippertv.app>")

    # App
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8501")

    @classmethod
    def validate(cls) -> None:
        """
        Validate required configuration.

        Raises:
            ValueError: If required environment variables are missing
        """
        required = [
            ("TURSO_DATABASE_URL", cls.TURSO_DATABASE_URL),
            ("TURSO_AUTH_TOKEN", cls.TURSO_AUTH_TOKEN),
        ]

        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")

    @classmethod
    def validate_auth(cls) -> None:
        """
        Validate authentication configuration.

        Raises:
            ValueError: If authentication variables are missing
        """
        required = [
            ("JWT_SECRET_KEY", cls.JWT_SECRET_KEY),
            ("ENCRYPTION_KEY", cls.ENCRYPTION_KEY),
        ]

        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(
                f"Missing required auth config: {', '.join(missing)}\n"
                "Generate keys with:\n"
                "  JWT_SECRET_KEY: openssl rand -hex 32\n"
                "  ENCRYPTION_KEY: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )


env_config = EnvConfig()


def load_rider_mapping(config_path: str = "clipper.toml") -> Dict[str, str]:
    """Build rider_id → display name mapping from clipper.toml.

    Maps card numbers, account numbers, and aliases to the rider name.
    """
    path = Path(config_path)
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    mapping: Dict[str, str] = {}
    for account in data.get("accounts", []):
        name = account["name"]
        for key in ("cards", "accounts", "aliases"):
            for val in account.get(key, []):
                mapping[val] = name
    return mapping
