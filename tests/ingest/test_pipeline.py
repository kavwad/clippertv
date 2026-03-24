"""Tests for the ingestion pipeline orchestrator."""

import pandas as pd
from unittest.mock import MagicMock

from clippertv.ingest.pipeline import ingest


def _sample_csv_df() -> pd.DataFrame:
    """Create a sample CSV-parsed DataFrame."""
    return pd.DataFrame([
        {
            "account_number": "100005510894",
            "transaction_date": pd.Timestamp("2026-02-28 23:45:19"),
            "end_datetime": None,
            "start_location": "Haight/Noriega",
            "end_location": None,
            "fare": 2.85,
            "operator": "Muni",
            "pass_type": "Cash Value",
            "trip_id": "11052564",
        },
        {
            "account_number": "100005510894",
            "transaction_date": pd.Timestamp("2026-02-28 21:16:16"),
            "end_datetime": pd.Timestamp("2026-02-28 22:00:43"),
            "start_location": "Fruitvale",
            "end_location": "16th Street / Mission",
            "fare": 5.35,
            "operator": "BART",
            "pass_type": "Cash Value",
            "trip_id": "11047705",
        },
    ])


def test_ingest_adds_category_column():
    """Pipeline adds category column via categorization."""
    store = MagicMock()
    store.save_csv_transactions.return_value = 2

    count = ingest(_sample_csv_df(), rider_id="K", user_id="u1", store=store)

    call_args = store.save_csv_transactions.call_args
    df_saved = call_args[0][1]  # second positional arg
    assert "category" in df_saved.columns
    assert df_saved.iloc[0]["category"] == "Muni Bus"
    assert df_saved.iloc[1]["category"] == "BART"


def test_ingest_returns_count():
    """Pipeline returns the count from store."""
    store = MagicMock()
    store.save_csv_transactions.return_value = 2

    count = ingest(_sample_csv_df(), rider_id="K", user_id="u1", store=store)
    assert count == 2


def test_ingest_passes_rider_and_user():
    """Pipeline passes rider_id and user_id through to store."""
    store = MagicMock()
    store.save_csv_transactions.return_value = 0

    ingest(_sample_csv_df(), rider_id="K", user_id="u1", store=store)

    call_args = store.save_csv_transactions.call_args
    assert call_args[0][0] == "K"  # rider_id
    assert call_args[1]["user_id"] == "u1"
