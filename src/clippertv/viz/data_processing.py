"""Data processing functions for ClipperTV dashboard.

Expects the unified DataFrame format from TursoStore.load_data():
- Transaction Date (datetime)
- Category (str) — simple names like "BART", "Muni Bus"
- Fare (float) — single fare amount per trip
- Plus optional: Start Location, End Location, Operator, etc.
"""

from typing import List, Optional

import pandas as pd

from ..config import load_display_categories

DEFAULT_MAX_CATEGORIES = 8


CALTRAIN_MONTHLY_PASS_COST = 184.80


def apply_pass_costs(df: pd.DataFrame) -> pd.DataFrame:
    """Inject monthly pass cost for months with at least one pass ride.

    Detects pass months via the ``Pass Type`` column (set by the CSV export
    for rides covered by a monthly pass, where ``Fare`` is already 0).
    For each such month, zeroes out any remaining per-ride Caltrain fares
    (e.g. from duplicate manual/PDF rows) and injects a single row carrying
    the flat pass cost.

    Only affects Fare values — the returned DataFrame should be used for cost
    pivots, not trip-count pivots.
    """
    if "Pass Type" not in df.columns:
        return df

    pass_type = df["Pass Type"].fillna("")
    is_pass_ride = pass_type.str.contains("Monthly", case=False)

    if not is_pass_ride.any():
        return df

    # Identify months with at least one pass ride
    pass_months = set(df.loc[is_pass_ride, "Transaction Date"].dt.to_period("M"))

    cost_df = df.copy()
    is_caltrain = cost_df["Category"] == "Caltrain"
    in_pass_month = cost_df["Transaction Date"].dt.to_period("M").isin(pass_months)

    # Zero out per-ride fares in pass months (CSV rows are already 0,
    # but duplicate manual/PDF rows may carry stale fare values)
    cost_df.loc[is_caltrain & in_pass_month, "Fare"] = 0.0

    # Inject one row per pass month carrying the flat pass cost
    pass_rows = pd.DataFrame([
        {"Transaction Date": m.to_timestamp(), "Category": "Caltrain",
         "Fare": CALTRAIN_MONTHLY_PASS_COST}
        for m in sorted(pass_months)
    ])
    return pd.concat([cost_df, pass_rows], ignore_index=True)


def _top_categories(pivot: pd.DataFrame, max_categories: int) -> List[str]:
    """Return the top N categories by total value across all rows."""
    totals = pivot.sum(axis=0)
    totals = totals.drop(["Reload", "Unknown"], errors="ignore")
    return totals.nlargest(max_categories).index.tolist()


def _collapse_categories(
    pivot: pd.DataFrame,
    keep: Optional[List[str]] = None,
    max_categories: int = DEFAULT_MAX_CATEGORIES,
    fill_value=0,
) -> pd.DataFrame:
    """Keep top categories, fold the rest into 'Other'.

    If `keep` is provided (from clipper.toml), use that list exactly.
    Otherwise, pick the top `max_categories` by total volume.
    """
    if keep is None:
        keep = _top_categories(pivot, max_categories)
    # keep list defines the order (TOML explicit, or by volume from _top_categories)
    ordered = [c for c in keep if c in pivot.columns]

    other_cols = [c for c in pivot.columns if c not in ordered and c != "Reload"]
    result = pivot.reindex(columns=ordered, fill_value=fill_value).copy()
    if other_cols:
        result["Other"] = pivot[other_cols].sum(axis=1)
    return result


def create_pivot_year(
    df: pd.DataFrame, keep: Optional[List[str]] = None,
) -> pd.DataFrame:
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
    return _collapse_categories(pivot, keep=keep).astype(int)


def _complete_month_index(pivot: pd.DataFrame) -> pd.DataFrame:
    """Reindex a month-indexed pivot to include all months in the range."""
    if pivot.empty:
        return pivot
    full_range = pd.date_range(
        start=pivot.index.min(), end=pivot.index.max(), freq="ME",
    )
    return pivot.reindex(full_range, fill_value=0)


def create_pivot_month(
    df: pd.DataFrame, keep: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Create monthly pivot table of trips by category."""
    unstacked = (
        df.groupby([pd.Grouper(key="Transaction Date", freq="ME"), "Category"])
        .size()
        .unstack(fill_value=0)
    )
    assert isinstance(unstacked, pd.DataFrame)
    pivot = _complete_month_index(unstacked)
    pivot.sort_index(ascending=False, inplace=True)
    pivot.index.name = "Month"
    return _collapse_categories(pivot, keep=keep).astype(int)


def create_pivot_year_cost(
    df: pd.DataFrame, keep: Optional[List[str]] = None,
) -> pd.DataFrame:
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
    return _collapse_categories(pivot, keep=keep)


def create_pivot_month_cost(
    df: pd.DataFrame, keep: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Create monthly pivot table of costs by category."""
    pivot = (
        df.groupby([pd.Grouper(key="Transaction Date", freq="ME"), "Category"])["Fare"]
        .sum()
        .unstack(fill_value=0)
    )
    pivot = _complete_month_index(pivot)
    pivot.sort_index(ascending=False, inplace=True)
    pivot.index.name = "Month"
    return _collapse_categories(pivot, keep=keep)


def process_data(df: pd.DataFrame):
    """Process data into pivot tables for display."""
    toml_override = load_display_categories()

    # Determine which categories to keep: TOML override, or top N by trip count
    if toml_override is not None:
        keep = toml_override
    else:
        raw_month = (
            df.groupby([pd.Grouper(key="Transaction Date", freq="ME"), "Category"])
            .size()
            .unstack(fill_value=0)
        )
        assert isinstance(raw_month, pd.DataFrame)
        keep = _top_categories(raw_month, DEFAULT_MAX_CATEGORIES)

    pivot_year = create_pivot_year(df, keep=keep)
    pivot_month = create_pivot_month(df, keep=keep)

    cost_df = apply_pass_costs(df)
    pivot_year_cost = create_pivot_year_cost(cost_df, keep=keep)
    pivot_month_cost = create_pivot_month_cost(cost_df, keep=keep)

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
        "pass_upshot": None,
    }
