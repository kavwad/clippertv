"""Data access layer for ClipperTV."""

import json
from typing import Dict, Optional, Any, List
import pandas as pd
import streamlit as st

from clippertv.config import config
from clippertv.data.models import RiderData


class DataStore:
    """Data storage and retrieval for ClipperTV."""
    
    def __init__(self, gcs_key: Optional[Dict[str, Any]] = None):
        """Initialize DataStore with Google Cloud Storage credentials."""
        if gcs_key is not None:
            self.gcs_key = gcs_key
        else:
            raw_credentials = (
                st.secrets.get("connections", {})
                .get("gcs", {})
                .get("credentials_json")
            )
            if not raw_credentials:
                raise ValueError(
                    "Google Cloud Storage credentials not configured. "
                    "Add [connections.gcs].credentials_json to secrets.toml "
                    "or pass gcs_key explicitly."
                )
            self.gcs_key = json.loads(raw_credentials)
        self.data_bucket = config.data_bucket
        self._cache: Dict[str, pd.DataFrame] = {}  # Cache for dataframes
    
    def _get_data_path(self, rider_id: str) -> str:
        """Generate the path for a rider's data file."""
        return f"gcs://{self.data_bucket}/{config.data_file_template.format(rider_id.lower())}"
    
    def load_data(self, rider_id: str) -> pd.DataFrame:
        """Load a rider's data from Google Cloud Storage."""
        # Check cache first
        if rider_id in self._cache:
            return self._cache[rider_id]
        
        # Load from GCS
        path = self._get_data_path(rider_id)
        df = pd.read_csv(
            path,
            parse_dates=['Transaction Date'],
            storage_options={'token': self.gcs_key}
        )
        
        # Cache the result
        self._cache[rider_id] = df
        return df

    def load_multiple_riders(self, rider_ids: List[str]) -> Dict[str, pd.DataFrame]:
        """Load multiple riders' data (helper for parity with Turso store)."""
        return {rider_id: self.load_data(rider_id) for rider_id in rider_ids}
    
    def save_data(self, rider_id: str, df: pd.DataFrame) -> None:
        """Save a rider's data to Google Cloud Storage."""
        path = self._get_data_path(rider_id)
        df.to_csv(
            path,
            index=False,
            storage_options={'token': self.gcs_key}
        )
        
        # Update cache
        self._cache[rider_id] = df
    
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


# Global instance removed - create via factory.get_data_store() instead
# data_store = DataStore()
