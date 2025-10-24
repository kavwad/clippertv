"""Database schema definitions for ClipperTV."""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class TransitMode(str, Enum):
    """Enum for transit modes."""
    MUNI_BUS = "Muni Bus"
    MUNI_METRO = "Muni Metro"
    BART = "BART"
    CABLE_CAR = "Cable Car"
    CALTRAIN = "Caltrain"
    FERRY = "Ferry"
    AC_TRANSIT = "AC Transit"
    SAMTRANS = "SamTrans"


class TransactionType(str, Enum):
    """Enum for transaction types."""
    ENTRY = "entry"
    EXIT = "exit"
    RELOAD = "reload"
    MANUAL = "manual"
    PASS_PURCHASE = "pass_purchase"
    

class Rider(BaseModel):
    """Schema for rider table."""
    id: str = Field(..., description="Rider identifier")
    name: Optional[str] = Field(None, description="Rider's name")
    email: Optional[str] = Field(None, description="Rider's email")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class Transit(BaseModel):
    """Schema for transit modes table."""
    id: int = Field(..., description="Transit mode ID")
    name: str = Field(..., description="Transit mode name")
    display_name: str = Field(..., description="Display name for UI")
    color: str = Field(..., description="Color for charts")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class Trip(BaseModel):
    """Schema for trip table."""
    id: int = Field(..., description="Trip ID")
    rider_id: str = Field(..., description="Rider ID")
    transit_id: int = Field(..., description="Transit mode ID")
    transaction_type: str = Field(..., description="Transaction type")
    transaction_date: str = Field(..., description="Transaction date and time")
    location: Optional[str] = Field(None, description="Transaction location")
    route: Optional[str] = Field(None, description="Transit route")
    debit: Optional[float] = Field(None, description="Amount debited")
    credit: Optional[float] = Field(None, description="Amount credited")
    balance: Optional[float] = Field(None, description="Balance after transaction")
    product: Optional[str] = Field(None, description="Product purchased")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")

