"""Data models for ClipperTV."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class TransitTransaction(BaseModel):
    """Model for a single transit transaction."""
    
    transaction_date: datetime = Field(..., description="Date and time of the transaction")
    transaction_type: str = Field(..., description="Type of transaction")
    category: Optional[str] = Field(None, description="Transit category")
    location: Optional[str] = Field(None, description="Location of transaction")
    route: Optional[str] = Field(None, description="Transit route")
    debit: Optional[float] = Field(None, description="Amount debited (spent)")
    credit: Optional[float] = Field(None, description="Amount credited (refunded/loaded)")
    balance: Optional[float] = Field(None, description="Card balance after transaction")
    product: Optional[str] = Field(None, description="Product purchased (e.g., pass type)")

    class Config:
        """Pydantic model configuration."""
        from_attributes = True


class RiderData(BaseModel):
    """Model for a rider's transit data."""
    
    rider_id: str = Field(..., description="Rider identifier (e.g., 'B' or 'K')")
    transactions: List[TransitTransaction] = Field(default_factory=list, 
                                                description="List of transit transactions")
    
    def to_dataframe(self) -> "pd.DataFrame":
        """Convert rider data to pandas DataFrame."""
        import pandas as pd
        
        # Convert to dict and then to DataFrame
        transactions_dict = [t.model_dump() for t in self.transactions]
        df = pd.DataFrame(transactions_dict)
        
        # Rename columns to match existing format
        column_mapping = {
            'transaction_date': 'Transaction Date',
            'transaction_type': 'Transaction Type',
            'category': 'Category',
            'location': 'Location',
            'route': 'Route',
            'debit': 'Debit',
            'credit': 'Credit',
            'balance': 'Balance',
            'product': 'Product'
        }
        
        return df.rename(columns=column_mapping)
    
    @classmethod
    def from_dataframe(cls, rider_id: str, df: "pd.DataFrame") -> "RiderData":
        """Create RiderData instance from pandas DataFrame."""
        import pandas as pd

        # Rename columns to match model
        column_mapping = {
            'Transaction Date': 'transaction_date',
            'Transaction Type': 'transaction_type',
            'Category': 'category',
            'Location': 'location',
            'Route': 'route',
            'Debit': 'debit',
            'Credit': 'credit',
            'Balance': 'balance',
            'Product': 'product'
        }

        df_renamed = df.rename(columns=column_mapping)

        # Create transactions list
        transactions = []
        for _, row in df_renamed.iterrows():
            transaction_data = {}
            for field_name, value in row.items():
                if field_name not in TransitTransaction.model_fields:
                    continue
                if pd.isna(value):
                    continue
                transaction_data[field_name] = value
            transactions.append(TransitTransaction(**transaction_data))
        
        return cls(rider_id=rider_id, transactions=transactions)


class MonthlyStats(BaseModel):
    """Model for monthly transit statistics."""
    
    month: datetime = Field(..., description="Month (as datetime)")
    trips: Dict[str, int] = Field(default_factory=dict, 
                                 description="Number of trips by category")
    costs: Dict[str, float] = Field(default_factory=dict, 
                                   description="Cost of trips by category")
    
    @property
    def total_trips(self) -> int:
        """Get total number of trips for the month."""
        return sum(self.trips.values())
    
    @property
    def total_cost(self) -> float:
        """Get total cost for the month."""
        return sum(self.costs.values())


class YearlyStats(BaseModel):
    """Model for yearly transit statistics."""
    
    year: int = Field(..., description="Year")
    trips: Dict[str, int] = Field(default_factory=dict, 
                                 description="Number of trips by category")
    costs: Dict[str, float] = Field(default_factory=dict, 
                                   description="Cost of trips by category")
    monthly_stats: List[MonthlyStats] = Field(default_factory=list, 
                                            description="Monthly statistics for the year")
    
    @property
    def total_trips(self) -> int:
        """Get total number of trips for the year."""
        return sum(self.trips.values())
    
    @property
    def total_cost(self) -> float:
        """Get total cost for the year."""
        return sum(self.costs.values())


# Authentication and Multi-User Models

class User(BaseModel):
    """User account model."""

    id: str = Field(..., description="Unique user identifier")
    email: EmailStr = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="User's display name")
    created_at: datetime = Field(default_factory=datetime.now, description="Account creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")

    class Config:
        """Pydantic model configuration."""
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
        """Pydantic model configuration."""
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
