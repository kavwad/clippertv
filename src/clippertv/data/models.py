"""Data models for ClipperTV."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """User account model — identity is a Clipper account."""

    id: str = Field(..., description="Unique user identifier")
    email: EmailStr = Field(..., description="Clipper account email")
    name: str | None = Field(None, description="User's display name")
    credentials_encrypted: str | None = Field(
        None, description="Fernet-encrypted Clipper password for scraping"
    )
    needs_reauth: bool = Field(
        default=False, description="Set when scheduler detects stale credentials"
    )
    display_categories: list[str] | None = Field(
        None, description="Ordered list of transit categories to show on dashboard"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Account creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )

    class Config:
        from_attributes = True


class ClipperCard(BaseModel):
    """Clipper card associated with user."""

    id: str = Field(..., description="Unique card identifier")
    user_id: str = Field(..., description="ID of the user who owns this card")
    account_number: str = Field(
        ..., description="Clipper account number (long form, e.g. '100005510894')"
    )
    rider_name: str = Field(
        ..., description="Friendly name for this card (e.g., 'Card 1')"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Card registration timestamp"
    )

    class Config:
        from_attributes = True


class AuthToken(BaseModel):
    """JWT authentication token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
