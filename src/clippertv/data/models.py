"""Data models for ClipperTV."""

from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    """User account model."""

    id: str = Field(..., description="Unique user identifier")
    email: EmailStr = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="User's display name")
    created_at: datetime = Field(default_factory=datetime.now, description="Account creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """User registration payload."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password (will be hashed before storage)", min_length=8)
    name: Optional[str] = Field(None, description="User's display name")


class UserLogin(BaseModel):
    """User login payload."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class ClipperCard(BaseModel):
    """Clipper card associated with user."""

    id: str = Field(..., description="Unique card identifier")
    user_id: str = Field(..., description="ID of the user who owns this card")
    card_number: str = Field(..., description="Clipper card number (last 9 digits)")
    rider_name: str = Field(..., description="Friendly name for this card (e.g., 'Work Card')")
    credentials_encrypted: Optional[str] = Field(None, description="Encrypted Clipper account credentials")
    is_primary: bool = Field(default=False, description="Whether this is the user's primary card")
    created_at: datetime = Field(default_factory=datetime.now, description="Card registration timestamp")

    class Config:
        from_attributes = True


class ClipperCardCreate(BaseModel):
    """Clipper card registration payload."""

    card_number: str = Field(..., description="Clipper card number (last 9 digits)")
    rider_name: str = Field(..., description="Friendly name for this card")
    credentials: Optional[Dict[str, str]] = Field(None, description="Clipper account credentials (username, password)")
    is_primary: bool = Field(default=False, description="Whether this is the primary card")


class AuthToken(BaseModel):
    """JWT authentication token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
