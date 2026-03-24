"""Source-agnostic ingestion pipeline.

Takes a normalized DataFrame (from any source), categorizes transactions,
and stores them via TursoStore.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from clippertv.ingest.categories import categorize

if TYPE_CHECKING:
    from clippertv.data.turso_store import TursoStore


def ingest(
    df: pd.DataFrame,
    rider_id: str,
    user_id: str | None,
    store: TursoStore,
) -> int:
    """Categorize, dedup, and store transactions.

    Args:
        df: Normalized DataFrame with columns from CSV parsing.
        rider_id: Rider identifier (from card-to-user lookup).
        user_id: User ID (from card-to-user lookup).
        store: TursoStore instance.

    Returns:
        Number of new rows inserted.
    """
    if df.empty:
        return 0

    df = categorize(df)
    return store.save_csv_transactions(rider_id, df, user_id=user_id)
