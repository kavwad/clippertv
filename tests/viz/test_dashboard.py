"""Tests for dashboard data processing with unified data format."""

import pandas as pd
import pytest

from clippertv.viz.data_processing import (
    apply_pass_costs,
    calculate_summary_stats,
    create_pivot_month,
    create_pivot_month_cost,
)


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Helper that fills in defaults for the unified format."""
    defaults = {
        "Transaction Date": pd.Timestamp("2026-02-15"),
        "Category": "BART",
        "Fare": 5.00,
        "Start Location": None,
        "End Location": None,
        "Source": "csv",
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def test_pivot_month_groups_by_category():
    df = _make_df([
        {"Transaction Date": pd.Timestamp("2026-02-01"), "Category": "BART"},
        {"Transaction Date": pd.Timestamp("2026-02-02"), "Category": "Muni Bus"},
        {"Transaction Date": pd.Timestamp("2026-02-03"), "Category": "BART"},
    ])
    pivot = create_pivot_month(df)
    assert pivot.iloc[0].get("BART", 0) == 2
    assert pivot.iloc[0].get("Muni Bus", 0) == 1


def test_pivot_month_cost_sums_fare():
    df = _make_df([
        {"Transaction Date": pd.Timestamp("2026-02-01"), "Category": "BART", "Fare": 5.35},
        {"Transaction Date": pd.Timestamp("2026-02-02"), "Category": "BART", "Fare": 2.25},
    ])
    pivot = create_pivot_month_cost(df)
    assert pivot.iloc[0].get("BART", 0) == pytest.approx(7.60)


def test_free_transfer_counted():
    from clippertv.viz.data_processing import process_data

    df = _make_df([
        {"Fare": 2.85, "Category": "Muni Bus"},
        {"Fare": 0.00, "Category": "Muni Bus"},
        {"Fare": 0.00, "Category": "Muni Bus"},
    ])
    _, _, _, _, free_xfers = process_data(df)
    assert free_xfers == 2


def test_summary_stats_basic():
    df = _make_df([
        {"Transaction Date": pd.Timestamp("2026-02-01"), "Category": "BART", "Fare": 5.00},
        {"Transaction Date": pd.Timestamp("2026-02-02"), "Category": "Muni Bus", "Fare": 2.85},
    ])
    pivot_month = create_pivot_month(df)
    pivot_month_cost = create_pivot_month_cost(df)
    stats = calculate_summary_stats(pivot_month, pivot_month_cost, df)
    assert stats["trips_this_month"] == 2
    assert stats["cost_this_month"] == 8


def _make_pass_df() -> pd.DataFrame:
    """Build a DataFrame mimicking CSV-sourced Caltrain pass + cash rides."""
    rows = [
        # Oct 2023: pass ride (fare=0, Pass Type set)
        {"Transaction Date": pd.Timestamp("2023-10-02"), "Category": "Caltrain",
         "Fare": 0.0, "Pass Type": "Caltrain Adult 3 Zone Monthly"},
        # Oct 2023: one BART ride (unaffected)
        {"Transaction Date": pd.Timestamp("2023-10-05"), "Category": "BART",
         "Fare": 5.35, "Pass Type": None},
        # Nov 2023: Caltrain ride paid with cash (no pass)
        {"Transaction Date": pd.Timestamp("2023-11-07"), "Category": "Caltrain",
         "Fare": 7.70, "Pass Type": None},
    ]
    return pd.DataFrame(rows)


def test_apply_pass_costs_replaces_fare_in_pass_months():
    df = _make_pass_df()
    result = apply_pass_costs(df)
    # Oct 2023 Caltrain fares should be zeroed, replaced by $184.80 pass
    oct_caltrain = result[
        (result["Category"] == "Caltrain")
        & (result["Transaction Date"].dt.month == 10)
    ]
    assert oct_caltrain["Fare"].sum() == pytest.approx(184.80)


def test_apply_pass_costs_leaves_cash_months_alone():
    df = _make_pass_df()
    result = apply_pass_costs(df)
    # Nov 2023 Caltrain ride is not a pass month → fare unchanged
    nov_caltrain = result[
        (result["Category"] == "Caltrain")
        & (result["Transaction Date"].dt.month == 11)
    ]
    assert nov_caltrain["Fare"].sum() == pytest.approx(7.70)


def test_apply_pass_costs_leaves_other_categories_alone():
    df = _make_pass_df()
    result = apply_pass_costs(df)
    bart = result[result["Category"] == "BART"]
    assert bart["Fare"].sum() == pytest.approx(5.35)
