"""Turso-based data access layer for ClipperTV."""

from functools import lru_cache
from typing import Dict, Optional, Any, List, Tuple

import pandas as pd

from clippertv.data.turso_client import (
    get_turso_client,
    initialize_database,
    reset_turso_client,
)


class TursoStore:
    """Data storage and retrieval using Turso for ClipperTV."""

    def __init__(self):
        initialize_database()
        self.conn = get_turso_client()
        self._cache: Dict[str, pd.DataFrame] = {}
        self._cache_tokens: Dict[str, Tuple[str, str, int]] = {}
        self._transit_ids = self._get_transit_mode_ids()

    def _reset_connection(self) -> None:
        """Reset the Turso connection if the stream is stale."""
        reset_turso_client()
        self.conn = get_turso_client()

    def _execute(self, *args, **kwargs):
        """Execute a query with automatic stream-not-found recovery."""
        try:
            return self.conn.execute(*args, **kwargs)
        except ValueError as exc:
            if "stream not found" in str(exc).lower():
                self._reset_connection()
                return self.conn.execute(*args, **kwargs)
            raise

    def _commit(self) -> None:
        """Commit with stream-not-found recovery."""
        try:
            self.conn.commit()
        except ValueError as exc:
            if "stream not found" in str(exc).lower():
                self._reset_connection()
                self.conn.commit()
                return
            raise

    @lru_cache(maxsize=1)
    def _get_transit_mode_ids(self) -> Dict[str, int]:
        """Get mapping of transit mode names to IDs."""
        result = self._execute("SELECT id, name FROM transit_modes")
        return {row[1]: row[0] for row in result.fetchall()}

    def _ensure_rider_exists(self, rider_id: str) -> None:
        """Ensure the rider exists in the database, create if not."""
        result = self._execute(
            "SELECT * FROM riders WHERE id = ?", [rider_id]
        )
        if not result.fetchone():
            self._execute(
                "INSERT INTO riders (id, name, email) VALUES (?, NULL, NULL)",
                [rider_id],
            )
            self._commit()

    # --- Load ---

    def load_data(self, rider_id: str, user_id: Optional[str] = None) -> pd.DataFrame:
        """Load a rider's data from Turso."""
        return self.load_multiple_riders([rider_id], user_id=user_id)[rider_id]

    def _fetch_cache_token(self, rider_id: str) -> Tuple[str, str, int]:
        """Return a token describing the current DB state for a rider."""
        result = self._execute(
            """
            SELECT
                COALESCE(MAX(updated_at), ''),
                COALESCE(MAX(transaction_date), ''),
                COUNT(*)
            FROM trips
            WHERE rider_id = ?
            """,
            [rider_id],
        )
        row = result.fetchone()
        if not row:
            return ("", "", 0)
        return (row[0] or "", row[1] or "", int(row[2] or 0))

    def load_multiple_riders(
        self, rider_ids: List[str], user_id: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Load data for multiple riders, normalizing old PDF rows on read."""
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

        if missing:
            for rider_id in missing:
                self._ensure_rider_exists(rider_id)

            placeholders = ",".join("?" for _ in missing)
            query_params = list(missing)
            user_filter = ""
            if user_id:
                user_filter = " AND t.user_id = ?"
                query_params.append(user_id)

            query = f"""
                SELECT
                    t.rider_id,
                    t.transaction_date,
                    t.transaction_type,
                    tm.name as transit_mode,
                    COALESCE(t.start_location, t.location) as start_location,
                    t.end_location,
                    COALESCE(t.fare, t.debit) as fare,
                    t.operator,
                    t.pass_type,
                    t.trip_id,
                    t.end_datetime,
                    t.source,
                    t.category as stored_category,
                    t.location,
                    t.route,
                    t.debit,
                    t.credit,
                    t.balance,
                    t.product
                FROM trips t
                LEFT JOIN transit_modes tm ON t.transit_id = tm.id
                WHERE t.rider_id IN ({placeholders}){user_filter}
                ORDER BY t.rider_id, t.transaction_date DESC
            """

            result = self._execute(query, query_params)
            rows = result.fetchall()

            grouped: Dict[str, List[Dict[str, Any]]] = {r: [] for r in missing}
            for row in rows:
                rider_id = row[0]
                transaction_date = pd.to_datetime(row[1], utc=True).tz_convert(None)
                transaction_type = row[2]
                transit_mode = row[3]
                stored_category = row[12]

                if stored_category:
                    category = stored_category
                else:
                    raw = self._reconstruct_category(transit_mode, transaction_type)
                    if raw.endswith(" Entrance"):
                        category = raw[:-9]
                    elif raw.endswith(" Exit"):
                        category = raw[:-5]
                    else:
                        category = raw

                grouped[rider_id].append({
                    "Transaction Date": transaction_date,
                    "Category": category,
                    "Fare": row[6],
                    "Start Location": row[4],
                    "End Location": row[5],
                    "Operator": row[7],
                    "Trip ID": row[9],
                    "End Datetime": row[10],
                    "Pass Type": row[8],
                    "Source": row[11],
                    "Transaction Type": transaction_type,
                    "Debit": row[15],
                    "Credit": row[16],
                    "Balance": row[17],
                    "Product": row[18],
                    "Location": row[13],
                    "Route": row[14],
                })

            for rider_id in missing:
                rider_rows = grouped.get(rider_id, [])
                if rider_rows:
                    df = pd.DataFrame(rider_rows)
                else:
                    df = pd.DataFrame(columns=[
                        "Transaction Date", "Category", "Fare",
                        "Start Location", "End Location", "Operator",
                        "Trip ID", "End Datetime", "Pass Type", "Source",
                        "Transaction Type", "Debit", "Credit", "Balance",
                        "Product", "Location", "Route",
                    ])
                    df["Transaction Date"] = pd.to_datetime(df["Transaction Date"])

                self._cache[rider_id] = df
                self._cache_tokens[rider_id] = self._fetch_cache_token(rider_id)

        return {rider_id: self._cache[rider_id] for rider_id in rider_ids}

    def _reconstruct_category(
        self, transit_mode: Optional[str], transaction_type: str
    ) -> str:
        """Reconstruct category from old PDF-era transit_mode + transaction_type."""
        if transaction_type == "reload":
            return "Reload"
        if not transit_mode:
            return "Unknown"
        dual_tag_modes = {"BART", "Caltrain", "Ferry"}
        if transit_mode in dual_tag_modes:
            if transaction_type == "entry":
                return f"{transit_mode} Entrance"
            elif transaction_type == "exit":
                return f"{transit_mode} Exit"
        return transit_mode

    # --- Save ---

    def save_csv_transactions(
        self, rider_id: str, df: pd.DataFrame, user_id: Optional[str] = None
    ) -> int:
        """Save CSV-sourced transactions using trip_id for deduplication.

        Returns number of new rows inserted.
        """
        self._ensure_rider_exists(rider_id)

        result = self._execute(
            "SELECT trip_id FROM trips WHERE rider_id = ? AND trip_id IS NOT NULL",
            [rider_id],
        )
        existing_trip_ids = {row[0] for row in result.fetchall()}

        new_rows = df[~df["trip_id"].isin(existing_trip_ids)]
        if new_rows.empty:
            return 0

        def _nullable(val):
            return None if pd.isna(val) else val

        inserted = 0
        for _, row in new_rows.iterrows():
            transaction_date = row["transaction_date"]
            if pd.isna(transaction_date):
                continue
            end_dt = _nullable(row.get("end_datetime"))
            self._execute(
                """
                INSERT INTO trips (
                    rider_id, trip_id, transaction_date, end_datetime,
                    start_location, end_location, fare, operator,
                    pass_type, category, source, user_id, transaction_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'csv', ?, 'trip')
                """,
                [
                    rider_id,
                    row["trip_id"],
                    pd.Timestamp(transaction_date).isoformat(),
                    pd.Timestamp(end_dt).isoformat() if end_dt is not None else None,
                    _nullable(row.get("start_location")),
                    _nullable(row.get("end_location")),
                    float(row["fare"]) if pd.notna(row.get("fare")) else None,
                    row.get("operator"),
                    _nullable(row.get("pass_type")),
                    row.get("category"),
                    user_id,
                ],
            )
            inserted += 1

        self._commit()
        self.invalidate_cache(rider_id)
        return inserted

    # --- Queries ---

    def list_riders(self) -> list[str]:
        """Get distinct rider IDs from the database."""
        result = self._execute(
            "SELECT DISTINCT rider_id FROM trips ORDER BY rider_id"
        )
        return [row[0] for row in result.fetchall()]

    def invalidate_cache(self, rider_id: Optional[str] = None) -> None:
        """Clear the cache for a specific rider or all riders."""
        if rider_id:
            self._cache.pop(rider_id, None)
            self._cache_tokens.pop(rider_id, None)
        else:
            self._cache.clear()
            self._cache_tokens.clear()
