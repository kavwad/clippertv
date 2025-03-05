"""Data models for ClipperTV."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


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
