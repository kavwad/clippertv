"""Configuration management for ClipperTV."""

import hashlib
import os
import tomllib
from pathlib import Path

from pydantic import BaseModel


def _hash_color(name: str) -> str:
    """Generate a deterministic, visually distinct color from a string."""
    h = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)
    hue = h % 360
    saturation = 45 + (h >> 12) % 25  # 45-69%
    lightness = 35 + (h >> 20) % 20  # 35-54%
    return _hsl_to_hex(hue, saturation, lightness)


def _hsl_to_hex(h: int, s: int, l: int) -> str:  # noqa: E741
    """Convert HSL (0-360, 0-100, 0-100) to hex color string."""
    s_f, l_f = s / 100, l / 100
    c = (1 - abs(2 * l_f - 1)) * s_f
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l_f - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return f"#{int((r + m) * 255):02X}{int((g + m) * 255):02X}{int((b + m) * 255):02X}"


class TransitCategories(BaseModel):
    """Transit category display configuration."""

    color_map: dict[str, str] = {
        "Muni Bus": "#BA0C2F",
        "Muni Metro": "#FDB813",
        "BART": "#0099D8",
        "Cable Car": "#8B4513",
        "Caltrain": "#6C6C6C",
        "Ferry": "#4DD0E1",
        "AC Transit": "#006B54",
        "SamTrans": "#D3D3D3",
        "VTA": "#29588C",
        "Golden Gate Transit": "#F04A00",
        "Unknown": "#888888",
        "Other": "#888888",
    }

    def get_color(self, category: str) -> str:
        """Get color for a category, hashing unknown names as fallback."""
        return self.color_map.get(category, _hash_color(category))


class AppConfig(BaseModel):
    """Main application configuration."""

    app_title: str = "ClipperTV"
    transit_categories: TransitCategories = TransitCategories()


config = AppConfig()


class EnvConfig:
    """Environment-based configuration for authentication and database."""

    # Database
    TURSO_DATABASE_URL: str | None = os.getenv("TURSO_DATABASE_URL")
    TURSO_AUTH_TOKEN: str | None = os.getenv("TURSO_AUTH_TOKEN")

    # Authentication
    JWT_SECRET_KEY: str | None = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_DAYS: int = 7

    # Encryption
    ENCRYPTION_KEY: str | None = os.getenv("ENCRYPTION_KEY")

    # Email (for Phase 1.5)
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "resend")
    EMAIL_API_KEY: str | None = os.getenv("EMAIL_API_KEY")
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
                "  ENCRYPTION_KEY: python -c"
                ' "from cryptography.fernet import Fernet;'
                ' print(Fernet.generate_key().decode())"'
            )


env_config = EnvConfig()


def load_display_categories(config_path: str = "clipper.toml") -> list[str] | None:
    """Load explicit display categories from clipper.toml, if configured."""
    path = Path(config_path)
    if not path.exists():
        return None
    with open(path, "rb") as f:
        data = tomllib.load(f)
    display = data.get("display", {})
    cats = display.get("categories")
    return list(cats) if cats else None


def load_rider_mapping(config_path: str = "clipper.toml") -> dict[str, str]:
    """Build rider_id → display name mapping from clipper.toml.

    Maps card numbers, account numbers, and aliases to the rider name.
    """
    path = Path(config_path)
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    mapping: dict[str, str] = {}
    for account in data.get("accounts", []):
        name = account["name"]
        for key in ("cards", "accounts", "aliases"):
            for val in account.get(key, []):
                mapping[val] = name
    return mapping


def load_account_mapping(config_path: str = "clipper.toml") -> dict[str, list[str]]:
    """Build display name → account numbers mapping from clipper.toml.

    Returns a dict like {"kaveh": ["100005510894", "100005510902"], ...}.
    """
    path = Path(config_path)
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    mapping: dict[str, list[str]] = {}
    for account in data.get("accounts", []):
        name = account["name"]
        mapping[name] = list(account.get("accounts", []))
    return mapping
