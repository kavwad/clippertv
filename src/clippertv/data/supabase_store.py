"""Supabase-based data access layer for ClipperTV."""

import json
from datetime import datetime
from functools import lru_cache
from typing import Dict, Optional, Any, List, Tuple

import pandas as pd
from supabase import Client

from clippertv.config import config
from clippertv.data.models import RiderData, TransitTransaction
from clippertv.data.supabase_client import get_supabase_client, initialize_database


class SupabaseStore:
    """Data storage and retrieval using Supabase for ClipperTV."""
    
    def __init__(self):
        """Initialize SupabaseStore with Supabase client."""
        # Initialize the database if needed
        initialize_database()
        
        # Get the Supabase client
        self.client = get_supabase_client()
        
        # Set up cache
        self._cache: Dict[str, pd.DataFrame] = {}
        
        # Get transit mode mappings 
        self._transit_ids = self._get_transit_mode_ids()
    
    @lru_cache(maxsize=1)
    def _get_transit_mode_ids(self) -> Dict[str, int]:
        """Get mapping of transit mode names to IDs."""
        result = self.client.table("transit_modes").select("id,name").execute()
        return {item["name"]: item["id"] for item in result.data}
    
    def _get_transit_id(self, transit_name: str) -> Optional[int]:
        """Get the transit mode ID for a given name."""
        return self._transit_ids.get(transit_name)
    
    def _ensure_rider_exists(self, rider_id: str) -> None:
        """Ensure the rider exists in the database, create if not."""
        result = self.client.table("riders").select("*").eq("id", rider_id).execute()
        
        if not result.data:
            # Rider doesn't exist, create it
            self.client.table("riders").insert({
                "id": rider_id,
                "name": None,
                "email": None,
            }).execute()
    
    def load_data(self, rider_id: str) -> pd.DataFrame:
        """Load a rider's data from Supabase."""
        # Check cache first
        if rider_id in self._cache:
            return self._cache[rider_id]
        
        # Ensure rider exists
        self._ensure_rider_exists(rider_id)
        
        # Query trips for the rider
        result = (self.client
                 .table("trips")
                 .select("*, transit_modes(name)")
                 .eq("rider_id", rider_id)
                 .execute())
        
        # Convert to DataFrame
        if not result.data:
            # Return empty DataFrame with correct columns
            df = pd.DataFrame(columns=[
                'Transaction Date', 'Transaction Type', 'Category', 
                'Location', 'Route', 'Debit', 'Credit', 'Balance', 'Product'
            ])
            df['Transaction Date'] = pd.to_datetime(df['Transaction Date'])
            self._cache[rider_id] = df
            return df
        
        # Process data into expected format
        trip_data = []
        for trip in result.data:
            # Get transit mode name
            transit_mode = trip.get("transit_modes", {}).get("name", "Unknown")
            
            trip_data.append({
                'Transaction Date': pd.to_datetime(trip['transaction_date']),
                'Transaction Type': trip['transaction_type'],
                'Category': transit_mode,
                'Location': trip['location'],
                'Route': trip['route'],
                'Debit': trip['debit'],
                'Credit': trip['credit'],
                'Balance': trip['balance'],
                'Product': trip['product']
            })
        
        df = pd.DataFrame(trip_data)
        df = df.sort_values('Transaction Date', ascending=False).reset_index(drop=True)
        
        # Cache the result
        self._cache[rider_id] = df
        return df
    
    def save_data(self, rider_id: str, df: pd.DataFrame) -> None:
        """Save a rider's data to Supabase."""
        # This is no longer a direct save operation - we need to convert the dataframe
        # to individual records and perform upserts
        
        # Ensure rider exists
        self._ensure_rider_exists(rider_id)
        
        # Get existing trip data to determine what to insert/update
        existing_trips = self._get_existing_trips(rider_id)
        
        # Process the dataframe into trips
        for _, row in df.iterrows():
            # Skip if transaction date is missing
            if pd.isna(row['Transaction Date']):
                continue
                
            # Get the transit ID
            transit_id = None
            if not pd.isna(row.get('Category')):
                transit_name = row['Category']
                transit_id = self._get_transit_id(transit_name)
            
            # Create trip record
            trip = {
                "rider_id": rider_id,
                "transit_id": transit_id,
                "transaction_type": row.get('Transaction Type', ''),
                "transaction_date": row['Transaction Date'].isoformat(),
                "location": None if pd.isna(row.get('Location')) else row.get('Location'),
                "route": None if pd.isna(row.get('Route')) else row.get('Route'),
                "debit": None if pd.isna(row.get('Debit')) else row.get('Debit'),
                "credit": None if pd.isna(row.get('Credit')) else row.get('Credit'),
                "balance": None if pd.isna(row.get('Balance')) else row.get('Balance'),
                "product": None if pd.isna(row.get('Product')) else row.get('Product'),
            }
            
            # Check if trip already exists by matching transaction date and type
            transaction_date = row['Transaction Date'].isoformat()
            transaction_type = row.get('Transaction Type', '')
            
            key = (transaction_date, transaction_type)
            if key in existing_trips:
                # Update existing trip
                trip_id = existing_trips[key]
                self.client.table("trips").update(trip).eq("id", trip_id).execute()
            else:
                # Insert new trip
                self.client.table("trips").insert(trip).execute()
        
        # Update cache
        self._cache[rider_id] = df
    
    def _get_existing_trips(self, rider_id: str) -> Dict[Tuple[str, str], int]:
        """Get existing trips with their IDs for a rider."""
        result = (self.client
                 .table("trips")
                 .select("id, transaction_date, transaction_type")
                 .eq("rider_id", rider_id)
                 .execute())
        
        # Map (transaction_date, transaction_type) -> id
        return {
            (trip['transaction_date'], trip['transaction_type']): trip['id']
            for trip in result.data
        }
    
    def get_rider_data(self, rider_id: str) -> RiderData:
        """Get rider data as a RiderData model."""
        df = self.load_data(rider_id)
        return RiderData.from_dataframe(rider_id, df)
    
    def save_rider_data(self, rider_data: RiderData) -> None:
        """Save RiderData model to storage."""
        df = rider_data.to_dataframe()
        self.save_data(rider_data.rider_id, df)
    
    def add_transactions(self, rider_id: str, new_transactions_df: pd.DataFrame) -> pd.DataFrame:
        """Add new transactions to a rider's data and save."""
        current_df = self.load_data(rider_id)
        
        # Combine existing and new data
        combined_df = pd.concat([current_df, new_transactions_df])
        
        # Sort by transaction date and reset index
        combined_df = (combined_df
                      .sort_values('Transaction Date', ascending=False)
                      .reset_index(drop=True))
        
        # Save the updated data
        self.save_data(rider_id, combined_df)
        return combined_df
    
    def invalidate_cache(self, rider_id: Optional[str] = None) -> None:
        """Clear the cache for a specific rider or all riders."""
        if rider_id:
            if rider_id in self._cache:
                del self._cache[rider_id]
        else:
            self._cache.clear()


# Create a global instance
supabase_store = SupabaseStore()