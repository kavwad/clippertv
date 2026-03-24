"""Data processing functions for ClipperTV dashboard.

Expects the unified DataFrame format from TursoStore.load_data():
- Transaction Date (datetime)
- Category (str) — simple names like "BART", "Muni Bus"
- Fare (float) — single fare amount per trip
- Plus optional: Start Location, End Location, Operator, etc.
"""

import pandas as pd

from ..config import config


def _reorder_columns(pivot: pd.DataFrame, fill_value=0) -> pd.DataFrame:
    """Reorder pivot columns: known display categories first, then extras."""
    known = [c for c in config.transit_categories.display_categories if c in pivot.columns]
    extra = [c for c in pivot.columns if c not in known and c != "Reload"]
    return pivot.reindex(columns=known + extra, fill_value=fill_value)


def create_pivot_year(df: pd.DataFrame) -> pd.DataFrame:
    """Create yearly pivot table of trips by category."""
    pivot = df.pivot_table(
        index=df["Transaction Date"].dt.year,
        columns="Category",
        values="Transaction Date",
        aggfunc="count",
        fill_value=0,
    )
    pivot.sort_index(ascending=False, inplace=True)
    pivot.index.name = "Year"
    return _reorder_columns(pivot).astype(int)


def create_pivot_month(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly pivot table of trips by category."""
    pivot = (
        df.groupby([pd.Grouper(key="Transaction Date", freq="ME"), "Category"])
        .size()
        .unstack(fill_value=0)
    )
    pivot.sort_index(ascending=False, inplace=True)
    pivot.index.name = "Month"
    return _reorder_columns(pivot).astype(int)


def create_pivot_year_cost(df: pd.DataFrame) -> pd.DataFrame:
    """Create yearly pivot table of costs by category."""
    pivot = df.pivot_table(
        index=df["Transaction Date"].dt.year,
        columns="Category",
        values="Fare",
        aggfunc="sum",
        fill_value=0,
    )
    pivot.sort_index(ascending=False, inplace=True)
    pivot.index.name = "Year"
    return _reorder_columns(pivot)


def create_pivot_month_cost(df: pd.DataFrame) -> pd.DataFrame:
    """Create monthly pivot table of costs by category."""
    pivot = (
        df.groupby([pd.Grouper(key="Transaction Date", freq="ME"), "Category"])["Fare"]
        .sum()
        .unstack(fill_value=0)
    )
    pivot.sort_index(ascending=False, inplace=True)
    pivot.index.name = "Month"
    return _reorder_columns(pivot)


def process_data(df: pd.DataFrame):
    """Process data into pivot tables for display."""
    pivot_year = create_pivot_year(df)
    pivot_month = create_pivot_month(df)
    pivot_year_cost = create_pivot_year_cost(df)
    pivot_month_cost = create_pivot_month_cost(df)

    free_xfers = (df["Fare"] == 0).sum()

    return pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, free_xfers


def calculate_summary_stats(
    pivot_month: pd.DataFrame,
    pivot_month_cost: pd.DataFrame,
    df: pd.DataFrame,
) -> dict:
    """Calculate summary statistics for the dashboard."""
    current_month_trips = pivot_month.iloc[0]
    current_month_costs = pivot_month_cost.iloc[0]
    trips_this_month = current_month_trips.sum()
    cost_this_month = current_month_costs.sum().round().astype(int)

    has_previous = len(pivot_month) > 1
    prev_trips = pivot_month.iloc[1].sum() if has_previous else trips_this_month
    prev_costs = (
        pivot_month_cost.iloc[1].sum().round().astype(int) if has_previous else cost_this_month
    )

    trip_diff = prev_trips - trips_this_month
    cost_diff = prev_costs - cost_this_month

    most_recent_date = df["Transaction Date"].max()

    return {
        "trips_this_month": trips_this_month,
        "cost_this_month": cost_this_month,
        "trip_diff": trip_diff,
        "trip_diff_text": "fewer" if trip_diff >= 0 else "more",
        "cost_diff": cost_diff,
        "cost_diff_text": "less" if cost_diff >= 0 else "more",
        "most_recent_date": most_recent_date,
        "most_used_mode": current_month_trips.idxmax(),
        "pass_upshot": None,  # Legacy — Caltrain pass logic deferred
    }
