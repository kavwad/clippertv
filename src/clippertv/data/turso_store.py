"""Turso-based data access layer for ClipperTV."""

import pandas as pd

from clippertv.data.turso_client import (
    get_turso_client,
    initialize_database,
    reset_turso_client,
)


def _normalize_pass_type(val) -> str | None:
    """Normalize pass_type: N/A and empty string become None."""
    if pd.isna(val) or val in ("N/A", ""):
        return None
    return val


class TursoStore:
    """Data storage and retrieval using Turso for ClipperTV."""

    def __init__(self):
        initialize_database()
        self.conn = get_turso_client()

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

    def save_csv_transactions(
        self,
        account_number: str,
        df: pd.DataFrame,
        user_id: str | None = None,
    ) -> int:
        """Save CSV-sourced transactions using trip_id for deduplication."""
        result = self._execute("SELECT trip_id FROM trips WHERE trip_id IS NOT NULL")
        existing_trip_ids = {row[0] for row in result.fetchall()}

        new_rows = df[~df["trip_id"].isin(existing_trip_ids)]
        if new_rows.empty:
            return 0

        def _nullable(val):
            return None if pd.isna(val) else val

        inserted = 0
        for _, row in new_rows.iterrows():
            start_dt = row.get("transaction_date") or row.get("start_datetime")
            if pd.isna(start_dt):
                continue
            end_dt = _nullable(row.get("end_datetime"))
            self._execute(
                """INSERT INTO trips
                   (account_number, trip_id, start_datetime, end_datetime,
                    start_location, end_location, fare, operator, pass_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    account_number,
                    row["trip_id"],
                    pd.Timestamp(start_dt).isoformat(),
                    pd.Timestamp(end_dt).isoformat() if end_dt else None,
                    _nullable(row.get("start_location")),
                    _nullable(row.get("end_location")),
                    float(row["fare"]) if pd.notna(row.get("fare")) else None,
                    row.get("operator"),
                    _normalize_pass_type(row.get("pass_type")),
                ],
            )
            inserted += 1

        self._commit()
        return inserted

    def list_riders(self) -> list[str]:
        """Get distinct account numbers from the database."""
        result = self._execute(
            "SELECT DISTINCT account_number FROM trips ORDER BY account_number"
        )
        return [row[0] for row in result.fetchall()]
