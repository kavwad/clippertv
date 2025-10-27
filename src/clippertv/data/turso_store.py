"""Turso-based data access layer for ClipperTV."""

import hashlib
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

    _HASH_FIELDS: Tuple[str, ...] = (
        'Transaction Date',
        'Transaction Type',
        'Category',
        'Location',
        'Route',
        'Debit',
        'Credit',
        'Balance',
        'Product'
    )

    def __init__(self):
        """Initialize TursoStore with Turso client."""
        # Initialize the database if needed
        initialize_database()

        # Get the Turso connection
        self.conn = get_turso_client()

        # Set up cache
        self._cache: Dict[str, pd.DataFrame] = {}
        self._cache_tokens: Dict[str, Tuple[str, str, int]] = {}

        # Get transit mode mappings
        self._transit_ids = self._get_transit_mode_ids()

    @lru_cache(maxsize=1)
    def _get_transit_mode_ids(self) -> Dict[str, int]:
        """Get mapping of transit mode names to IDs."""
        result = self.conn.execute("SELECT id, name FROM transit_modes")
        rows = result.fetchall()
        return {row[1]: row[0] for row in rows}  # name -> id

    @staticmethod
    def _serialize_for_hash(value: Any) -> Any:
        """Normalize values so they are stable for hashing."""
        if isinstance(value, pd.Timestamp):
            timestamp = value
        elif isinstance(value, datetime):
            timestamp = pd.Timestamp(value)
        else:
            timestamp = None

        if timestamp is not None:
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert(None)
            return timestamp.isoformat()

        if pd.isna(value):
            return None

        return value

    def _compute_row_hash(self, rider_id: str, row: pd.Series) -> str:
        """Compute a deterministic hash for a transaction row."""
        payload = {'rider_id': rider_id}
        for field in self._HASH_FIELDS:
            payload[field] = self._serialize_for_hash(row.get(field))

        serialized = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

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
        return self.load_multiple_riders([rider_id])[rider_id]

    def _fetch_cache_token(self, rider_id: str) -> Tuple[str, str, int]:
        """Return a token describing the current DB state for a rider."""
        result = self.conn.execute(
            """
            SELECT
                COALESCE(MAX(updated_at), ''),
                COALESCE(MAX(transaction_date), ''),
                COUNT(*)
            FROM trips
            WHERE rider_id = ?
            """,
            [rider_id]
        )
        row = result.fetchone()
        if not row:
            return ('', '', 0)
        updated_at, latest_trip, row_count = row
        return (
            updated_at or '',
            latest_trip or '',
            int(row_count or 0)
        )

    def load_multiple_riders(self, rider_ids: List[str]) -> Dict[str, pd.DataFrame]:
        """Load data for multiple riders with a single query where possible."""
        missing: List[str] = []
        for rider_id in rider_ids:
            if rider_id not in self._cache:
                missing.append(rider_id)
                continue

            cached_token = self._cache_tokens.get(rider_id)
            current_token = self._fetch_cache_token(rider_id)
            if cached_token != current_token:
                self.invalidate_cache(rider_id)
                missing.append(rider_id)

        # Separate which rider data we already have cached

        if missing:
            for rider_id in missing:
                self._ensure_rider_exists(rider_id)

            placeholders = ",".join("?" for _ in missing)
            query = f"""
                SELECT
                    t.rider_id,
                    t.transaction_date,
                    t.transaction_type,
                    tm.name as transit_mode,
                    t.location,
                    t.route,
                    t.debit,
                    t.credit,
                    t.balance,
                    t.product
                FROM trips t
                LEFT JOIN transit_modes tm ON t.transit_id = tm.id
                WHERE t.rider_id IN ({placeholders})
                ORDER BY t.rider_id, t.transaction_date DESC
            """

            result = self.conn.execute(query, missing)
            rows = result.fetchall()

            grouped: Dict[str, List[Dict[str, Any]]] = {r: [] for r in missing}
            for row in rows:
                rider_id = row[0]
                transaction_date = pd.to_datetime(row[1], utc=True).tz_convert(None)
                transaction_type = row[2]
                transit_mode = row[3]
                location = row[4]
                route = row[5]
                debit = row[6]
                credit = row[7]
                balance = row[8]
                product = row[9]

                category = self._reconstruct_category(transit_mode, transaction_type)

                grouped[rider_id].append({
                    'Transaction Date': transaction_date,
                    'Transaction Type': transaction_type,
                    'Category': category,
                    'Location': location,
                    'Route': route,
                    'Debit': debit,
                    'Credit': credit,
                    'Balance': balance,
                    'Product': product
                })

            for rider_id in missing:
                rider_rows = grouped.get(rider_id, [])
                if rider_rows:
                    df = pd.DataFrame(rider_rows)
                else:
                    df = pd.DataFrame(columns=[
                        'Transaction Date', 'Transaction Type', 'Category',
                        'Location', 'Route', 'Debit', 'Credit', 'Balance', 'Product'
                    ])
                    df['Transaction Date'] = pd.to_datetime(df['Transaction Date'])

                self._cache[rider_id] = df
                self._cache_tokens[rider_id] = self._fetch_cache_token(rider_id)

        return {rider_id: self._cache[rider_id] for rider_id in rider_ids}

    def _reconstruct_category(self, transit_mode: Optional[str], transaction_type: str) -> str:
        """Reconstruct the category name from transit mode and transaction type.

        This converts normalized database values back to the format expected by the app:
        - BART + entry -> "BART Entrance"
        - BART + exit -> "BART Exit"
        - Muni Bus + entry -> "Muni Bus"
        - etc.
        """
        if not transit_mode:
            return 'Unknown'

        # Transit modes that need Entrance/Exit suffixes
        dual_tag_modes = {'BART', 'Caltrain', 'Ferry'}

        if transit_mode in dual_tag_modes:
            if transaction_type == 'entry':
                return f"{transit_mode} Entrance"
            elif transaction_type == 'exit':
                return f"{transit_mode} Exit"

        # All other modes don't use entrance/exit in their category name
        return transit_mode

    def save_data(self, rider_id: str, df: pd.DataFrame) -> None:
        """Save a rider's data to Turso."""
        import sys
        # Ensure rider exists
        print(f"    Ensuring rider {rider_id} exists...", file=sys.stderr)
        self._ensure_rider_exists(rider_id)

        normalized_df = df.copy()
        normalized_df['Transaction Date'] = pd.to_datetime(
            normalized_df['Transaction Date'],
            utc=True,
            errors='coerce'
        ).dt.tz_convert(None)

        print(f"    Processing {len(normalized_df)} rows...", file=sys.stderr)
        normalized_df['_content_hash'] = normalized_df.apply(
            lambda row: self._compute_row_hash(rider_id, row),
            axis=1
        )

        existing_hashes = self._get_existing_hashes(rider_id)
        known_hashes = set(existing_hashes.keys())
        rows_to_persist = normalized_df[
            ~normalized_df['_content_hash'].isin(known_hashes)
        ].copy()
        rows_to_persist = rows_to_persist[
            ~rows_to_persist['_content_hash'].duplicated()
        ]

        cache_df = normalized_df.drop(columns=['_content_hash'])

        if rows_to_persist.empty:
            print("    No new or updated transactions detected.", file=sys.stderr)
            self._cache[rider_id] = cache_df
            self._cache_tokens[rider_id] = self._fetch_cache_token(rider_id)
            return

        print(f"    {len(rows_to_persist)} rows require persistence.", file=sys.stderr)
        existing_trips = self._get_existing_trips(rider_id)
        print(f"    Loaded {len(existing_trips)} existing trip keys for comparison.", file=sys.stderr)

        processed_count = 0
        for _, row in rows_to_persist.iterrows():
            processed_count += 1
            if processed_count % 50 == 0:
                print(f"      Upserting {processed_count}/{len(rows_to_persist)} rows...", file=sys.stderr)

            timestamp = row['Transaction Date']
            if pd.isna(timestamp):
                continue

            transaction_date = pd.Timestamp(timestamp).isoformat()
            category = row.get('Category')
            transit_id, normalized_transaction_type = self._parse_category(category)
            transaction_type = normalized_transaction_type or row.get('Transaction Type', 'manual')
            location = None if pd.isna(row.get('Location')) else row.get('Location')
            route = None if pd.isna(row.get('Route')) else row.get('Route')
            debit = None if pd.isna(row.get('Debit')) else float(row.get('Debit'))
            credit = None if pd.isna(row.get('Credit')) else float(row.get('Credit'))
            balance = None if pd.isna(row.get('Balance')) else float(row.get('Balance'))
            product = None if pd.isna(row.get('Product')) else row.get('Product')
            row_hash = row['_content_hash']

            key = (transaction_date, transaction_type, location, debit, credit)
            trip_id = existing_trips.get(key)

            if trip_id:
                self.conn.execute("""
                    UPDATE trips
                    SET transit_id = ?, location = ?, route = ?,
                        debit = ?, credit = ?, balance = ?, product = ?,
                        content_hash = ?, updated_at = datetime('now')
                    WHERE id = ?
                """, [transit_id, location, route, debit, credit, balance,
                      product, row_hash, trip_id])
            else:
                cursor = self.conn.execute("""
                    INSERT INTO trips (
                        rider_id, transit_id, transaction_type, transaction_date,
                        location, route, debit, credit, balance, product, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [rider_id, transit_id, transaction_type, transaction_date,
                      location, route, debit, credit, balance, product, row_hash])
                if cursor.lastrowid:
                    existing_trips[key] = cursor.lastrowid

        print(f"    Committing changes to database...", file=sys.stderr)
        self.conn.commit()
        print(f"    Committed successfully!", file=sys.stderr)

        self._cache[rider_id] = cache_df
        self._cache_tokens[rider_id] = self._fetch_cache_token(rider_id)

    def _parse_category(self, category: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
        """Parse a category string to extract transit mode ID and transaction type.

        Converts app format back to normalized database format:
        - "BART Entrance" -> (BART_id, "entry")
        - "BART Exit" -> (BART_id, "exit")
        - "Muni Bus" -> (Muni_Bus_id, "entry")
        - etc.

        Returns:
            Tuple of (transit_id, transaction_type)
        """
        if not category or pd.isna(category):
            return (None, None)

        # Check for entrance/exit suffixes
        if category.endswith(' Entrance'):
            transit_name = category[:-9]  # Remove ' Entrance'
            transit_id = self._get_transit_id(transit_name)
            return (transit_id, 'entry')
        elif category.endswith(' Exit'):
            transit_name = category[:-5]  # Remove ' Exit'
            transit_id = self._get_transit_id(transit_name)
            return (transit_id, 'exit')
        else:
            # No suffix, it's a regular single-tag transit mode
            transit_id = self._get_transit_id(category)
            return (transit_id, 'entry')

    def _get_existing_trips(self, rider_id: str) -> Dict[Tuple[str, str, str, float, float], int]:
        """Get existing trips with their IDs for a rider.

        Returns a dict mapping (transaction_date, transaction_type, location, debit, credit) -> id
        """
        result = self.conn.execute("""
            SELECT id, transaction_date, transaction_type, location, debit, credit
            FROM trips
            WHERE rider_id = ?
        """, [rider_id])

        rows = result.fetchall()

        # Map (transaction_date, transaction_type, location, debit, credit) -> id
        return {
            (row[1], row[2], row[3], row[4], row[5]): row[0]
            for row in rows
        }

    def _get_existing_hashes(self, rider_id: str) -> Dict[str, int]:
        """Return mapping of content hashes to trip IDs for a rider."""
        result = self.conn.execute(
            """
            SELECT content_hash, id
            FROM trips
            WHERE rider_id = ? AND content_hash IS NOT NULL
            """,
            [rider_id]
        )
        return {row[0]: row[1] for row in result.fetchall()}

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
        import sys

        new_transactions_df = new_transactions_df.copy()
        if new_transactions_df.empty:
            print(f"  No new transactions to add", file=sys.stderr)
            return self.load_data(rider_id)

        print(f"  Normalizing {len(new_transactions_df)} new transactions...", file=sys.stderr)
        new_transactions_df['Transaction Date'] = (
            pd.to_datetime(new_transactions_df['Transaction Date'], utc=True)
            .dt.tz_convert(None)
        )

        # Save only the new transactions
        print(f"  Saving new transactions to database...", file=sys.stderr)
        self.save_data(rider_id, new_transactions_df)

        # Invalidate cache so next load will fetch fresh data
        print(f"  Invalidating cache...", file=sys.stderr)
        self.invalidate_cache(rider_id)

        # Return the combined dataset
        print(f"  Loading updated data...", file=sys.stderr)
        return self.load_data(rider_id)

    def invalidate_cache(self, rider_id: Optional[str] = None) -> None:
        """Clear the cache for a specific rider or all riders."""
        if rider_id:
            if rider_id in self._cache:
                del self._cache[rider_id]
            if rider_id in self._cache_tokens:
                del self._cache_tokens[rider_id]
        else:
            self._cache.clear()
            self._cache_tokens.clear()
