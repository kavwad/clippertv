"""Tests for dashboard summary logic and pivot builders."""

from __future__ import annotations

import pandas as pd
import pytest

from clippertv.viz.dashboard import (
    calculate_summary_stats,
    create_pivot_month,
    create_pivot_month_cost,
)


def _caltrain_pass_dataframe(pass_rides: int) -> pd.DataFrame:
    """Create a DataFrame with Caltrain pass purchase, manual rides, and extra taps."""
    rows = []
    base_date = pd.Timestamp("2024-02-01 08:00:00")
    for index in range(pass_rides):
        rows.append(
            {
                "Transaction Date": base_date + pd.Timedelta(minutes=index),
                "Transaction Type": "Manual entry",
                "Category": "Caltrain Entrance",
                "Location": None,
                "Route": None,
                "Debit": 0.0,
                "Credit": 0.0,
                "Balance": None,
                "Product": None,
            }
        )

    rows.extend(
        [
            {
                "Transaction Date": pd.Timestamp("2024-02-01 00:00:00"),
                "Transaction Type": "Manual entry",
                "Category": "Reload",
                "Location": None,
                "Route": None,
                "Debit": 0.0,
                "Credit": 184.80,
                "Balance": None,
                "Product": "Caltrain Adult 3 Zone Monthly Pass",
            },
            {
                "Transaction Date": pd.Timestamp("2024-02-03 09:00:00"),
                "Transaction Type": "entry",
                "Category": "Caltrain Entrance",
                "Location": "CAL",
                "Route": None,
                "Debit": 15.40,
                "Credit": 0.0,
                "Balance": None,
                "Product": None,
            },
            {
                "Transaction Date": pd.Timestamp("2024-02-03 10:00:00"),
                "Transaction Type": "exit",
                "Category": "Caltrain Exit",
                "Location": "CAL",
                "Route": None,
                "Debit": 0.0,
                "Credit": 7.70,
                "Balance": None,
                "Product": None,
            },
        ]
    )

    return pd.DataFrame(rows)


def test_create_pivot_month_cost_accounts_for_pass_reload() -> None:
    """Ensure Caltrain costs include pass reload charges."""
    df = _caltrain_pass_dataframe(pass_rides=0)
    pivot_cost = create_pivot_month_cost(df)
    caltrain_value = pivot_cost.iloc[0]["Caltrain"]
    assert caltrain_value == pytest.approx(192.5)


def test_calculate_summary_stats_handles_single_month_with_pass() -> None:
    """Summary stats should provide pass math even with a single month of data."""
    ride_count = 30
    df = _caltrain_pass_dataframe(pass_rides=ride_count)
    pivot_month = create_pivot_month(df)
    pivot_month_cost = create_pivot_month_cost(df)

    stats = calculate_summary_stats(pivot_month, pivot_month_cost, df)

    assert stats["trips_this_month"] == ride_count + 1
    assert stats["trip_diff"] == 0
    assert stats["cost_diff"] == 0

    expected_upshot = int(round(-ride_count * 7.70 + 184.80 + 7.70, 0))
    assert stats["pass_upshot"] == expected_upshot
