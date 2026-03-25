"""Source-agnostic ingestion pipeline.

Takes a normalized DataFrame (from any source) and stores via TursoStore.
Category derivation happens at query time via category_rules table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from clippertv.data.turso_store import TursoStore


def ingest(
    df: pd.DataFrame,
    rider_id: str,
    user_id: str | None,
    store: TursoStore,
) -> int:
    """Dedup and store transactions.

    Args:
        df: Normalized DataFrame with columns from CSV parsing.
        rider_id: Account number (from card-to-user lookup).
        user_id: User ID (from card-to-user lookup).
        store: TursoStore instance.

    Returns:
        Number of new rows inserted.
    """
    if df.empty:
        return 0

    return store.save_csv_transactions(rider_id, df, user_id=user_id)
