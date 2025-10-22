"""Turso-based data access layer for ClipperTV."""

import json
from datetime import datetime
from functools import lru_cache
from typing import Dict, Optional, Any, List, Tuple

import pandas as pd

from clippertv.config import config
from clippertv.data.models import RiderData, TransitTransaction
from clippertv.data.turso_client import get_turso_client, initialize_database


class TursoStore:
    """Data storage and retrieval using Turso for ClipperTV."""

    def __init__(self):
        """Initialize TursoStore with Turso client."""
        # Initialize the database if needed
        initialize_database()

        # Get the Turso connection
        self.conn = get_turso_client()

        # Set up cache
        self._cache: Dict[str, pd.DataFrame] = {}

        # Get transit mode mappings
        self._transit_ids = self._get_transit_mode_ids()

    @lru_cache(maxsize=1)
    def _get_transit_mode_ids(self) -> Dict[str, int]:
        """Get mapping of transit mode names to IDs."""
        result = self.conn.execute("SELECT id, name FROM transit_modes")
        rows = result.fetchall()
        return {row[1]: row[0] for row in rows}  # name -> id

    def _get_transit_id(self, transit_name: str) -> Optional[int]:
        """Get the transit mode ID for a given name."""
        return self._transit_ids.get(transit_name)

    def _ensure_rider_exists(self, rider_id: str) -> None:
        """Ensure the rider exists in the database, create if not."""
        result = self.conn.execute(
            "SELECT * FROM riders WHERE id = ?",
            [rider_id]
        )

        if not result.fetchone():
            # Rider doesn't exist, create it
            self.conn.execute(
                "INSERT INTO riders (id, name, email) VALUES (?, NULL, NULL)",
                [rider_id]
            )
            self.conn.commit()

    def load_data(self, rider_id: str) -> pd.DataFrame:
        """Load a rider's data from Turso."""
        # Check cache first
        if rider_id in self._cache:
            return self._cache[rider_id]

        # Ensure rider exists
        self._ensure_rider_exists(rider_id)

        # Query trips for the rider with transit mode names
        result = self.conn.execute("""
            SELECT
                t.transaction_date,
                t.transaction_type,
                tm.name as category,
                t.location,
                t.route,
                t.debit,
                t.credit,
                t.balance,
                t.product
            FROM trips t
            LEFT JOIN transit_modes tm ON t.transit_id = tm.id
            WHERE t.rider_id = ?
            ORDER BY t.transaction_date DESC
        """, [rider_id])

        rows = result.fetchall()

        # Convert to DataFrame
        if not rows:
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
        for row in rows:
            trip_data.append({
                'Transaction Date': pd.to_datetime(row[0]),
                'Transaction Type': row[1],
                'Category': row[2] if row[2] else 'Unknown',
                'Location': row[3],
                'Route': row[4],
                'Debit': row[5],
                'Credit': row[6],
                'Balance': row[7],
                'Product': row[8]
            })

        df = pd.DataFrame(trip_data)

        # Cache the result
        self._cache[rider_id] = df
        return df

    def save_data(self, rider_id: str, df: pd.DataFrame) -> None:
        """Save a rider's data to Turso."""
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

            # Convert datetime to ISO string
            transaction_date = row['Transaction Date'].isoformat()
            transaction_type = row.get('Transaction Type', '')

            # Create trip data
            location = None if pd.isna(row.get('Location')) else row.get('Location')
            route = None if pd.isna(row.get('Route')) else row.get('Route')
            debit = None if pd.isna(row.get('Debit')) else float(row.get('Debit'))
            credit = None if pd.isna(row.get('Credit')) else float(row.get('Credit'))
            balance = None if pd.isna(row.get('Balance')) else float(row.get('Balance'))
            product = None if pd.isna(row.get('Product')) else row.get('Product')

            # Check if trip already exists
            key = (transaction_date, transaction_type)
            if key in existing_trips:
                # Update existing trip
                trip_id = existing_trips[key]
                self.conn.execute("""
                    UPDATE trips
                    SET transit_id = ?, location = ?, route = ?,
                        debit = ?, credit = ?, balance = ?, product = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                """, [transit_id, location, route, debit, credit, balance, product, trip_id])
            else:
                # Insert new trip
                self.conn.execute("""
                    INSERT INTO trips (
                        rider_id, transit_id, transaction_type, transaction_date,
                        location, route, debit, credit, balance, product
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [rider_id, transit_id, transaction_type, transaction_date,
                      location, route, debit, credit, balance, product])

        # Commit changes
        self.conn.commit()

        # Update cache
        self._cache[rider_id] = df

    def _get_existing_trips(self, rider_id: str) -> Dict[Tuple[str, str], int]:
        """Get existing trips with their IDs for a rider."""
        result = self.conn.execute("""
            SELECT id, transaction_date, transaction_type
            FROM trips
            WHERE rider_id = ?
        """, [rider_id])

        rows = result.fetchall()

        # Map (transaction_date, transaction_type) -> id
        return {
            (row[1], row[2]): row[0]
            for row in rows
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
turso_store = TursoStore()
