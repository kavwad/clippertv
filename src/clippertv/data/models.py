"""Data models for ClipperTV."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """User account model."""

    id: str = Field(..., description="Unique user identifier")
    email: EmailStr = Field(..., description="User email address")
    name: str | None = Field(None, description="User's display name")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Account creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """User registration payload."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ..., description="User password (will be hashed before storage)", min_length=8
    )
    name: str | None = Field(None, description="User's display name")


class UserLogin(BaseModel):
    """User login payload."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class ClipperCard(BaseModel):
    """Clipper card associated with user."""

    id: str = Field(..., description="Unique card identifier")
    user_id: str = Field(..., description="ID of the user who owns this card")
    account_number: str = Field(
        ..., description="Clipper account number (long form, e.g. '100005510894')"
    )
    card_serial: str | None = Field(
        None, description="Physical card serial number (short form, e.g. '1202425091')"
    )
    rider_name: str = Field(
        ..., description="Friendly name for this card (e.g., 'Work Card')"
    )
    credentials_encrypted: str | None = Field(
        None, description="Encrypted Clipper account credentials"
    )
    is_primary: bool = Field(
        default=False, description="Whether this is the user's primary card"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Card registration timestamp"
    )

    class Config:
        from_attributes = True


class ClipperCardCreate(BaseModel):
    """Clipper card registration payload."""

    account_number: str = Field(
        ..., description="Clipper account number (long form, e.g. '100005510894')"
    )
    card_serial: str | None = Field(
        None, description="Physical card serial number (optional)"
    )
    rider_name: str = Field(..., description="Friendly name for this card")
    credentials: dict[str, str] | None = Field(
        None, description="Clipper account credentials (username, password)"
    )
    is_primary: bool = Field(
        default=False, description="Whether this is the primary card"
    )


class AuthToken(BaseModel):
    """JWT authentication token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
