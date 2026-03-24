"""FastAPI routes for ClipperTV dashboard."""

from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from clippertv.config import config, load_rider_mapping
from clippertv.data.factory import get_data_store
from clippertv.viz.data_processing import (
    process_data,
    calculate_summary_stats,
    create_pivot_month,
    create_pivot_month_cost,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Cache data store
_data_store = None

RIDER_COLORS = ["#0099CC", "#00A55E", "#FDB813", "#BA0C2F", "#6C6C6C", "#4DD0E1"]

# rider_id → display name mapping (from clipper.toml)
_rider_map = load_rider_mapping()


def _display_name(rider_id: str) -> str:
    """Resolve a rider_id to a capitalized display name."""
    name = _rider_map.get(rider_id, rider_id)
    return name.capitalize() if name.isalpha() else name


def _rider_ids_for(display_name: str) -> list[str]:
    """Get all rider_ids that map to a given display name."""
    lower = display_name.lower()
    return [rid for rid, name in _rider_map.items() if name.lower() == lower]


def get_store():
    """Get cached data store instance."""
    global _data_store
    if _data_store is None:
        _data_store = get_data_store()
    return _data_store


def get_riders(store) -> list[str]:
    """Get deduplicated display names for all riders in the database."""
    raw_ids = store.list_riders()
    seen = {}
    for rid in raw_ids:
        name = _display_name(rid)
        if name not in seen:
            seen[name] = rid
    return list(seen.keys())


def _load_rider_df(store, rider: str) -> pd.DataFrame:
    """Load and concatenate data for all rider_ids behind a display name."""
    raw_ids = _rider_ids_for(rider)
    # Also include the display name itself in case it's used directly as a rider_id
    if rider not in raw_ids:
        raw_ids.append(rider)
    # Only query IDs that actually exist in the DB
    db_ids = set(store.list_riders())
    query_ids = [rid for rid in raw_ids if rid in db_ids]
    if not query_ids:
        return pd.DataFrame(columns=[
            "Transaction Date", "Category", "Fare",
        ])
    data = store.load_multiple_riders(query_ids)
    frames = [df for df in data.values() if not df.empty]
    if not frames:
        return pd.DataFrame(columns=[
            "Transaction Date", "Category", "Fare",
        ])
    return pd.concat(frames, ignore_index=True)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, rider: str = ""):
    """Render the main dashboard page."""
    store = get_store()
    riders = get_riders(store)
    if not riders:
        return templates.TemplateResponse("dashboard.html", {
            "request": request, "rider": None, "riders": [],
            "stats": None, "pivot_month": None, "pivot_year": None,
            "pivot_year_cost": None, "color_map": config.transit_categories.color_map,
        })
    if rider not in riders:
        rider = riders[0]

    df = _load_rider_df(store, rider)

    pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, free_xfers = process_data(df)
    stats = calculate_summary_stats(pivot_month, pivot_month_cost, df)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "rider": rider,
            "riders": riders,
            "stats": stats,
            "pivot_month": pivot_month,
            "pivot_year": pivot_year,
            "pivot_year_cost": pivot_year_cost,
            "color_map": config.transit_categories.color_map,
        }
    )


@router.get("/api/trips/{rider}")
async def get_trip_data(rider: str):
    """Return trip chart data as JSON for Chart.js."""
    store = get_store()
    df = _load_rider_df(store, rider)
    pivot_month = create_pivot_month(df)

    # Sort chronologically for chart (oldest first)
    pivot_month = pivot_month.sort_index(ascending=True)

    # Format for Chart.js stacked bar chart
    labels = [d.strftime("%b %Y") for d in pivot_month.index]
    datasets = []

    for category in pivot_month.columns:
        color = config.transit_categories.get_color(category)
        datasets.append({
            "label": category,
            "data": pivot_month[category].tolist(),
            "backgroundColor": color,
        })

    return {
        "labels": labels,
        "datasets": datasets,
    }


@router.get("/api/costs/{rider}")
async def get_cost_data(rider: str):
    """Return cost chart data as JSON for Chart.js."""
    store = get_store()
    df = _load_rider_df(store, rider)
    pivot_month_cost = create_pivot_month_cost(df)

    # Sort chronologically for chart (oldest first)
    pivot_month_cost = pivot_month_cost.sort_index(ascending=True)

    # Format for Chart.js stacked bar chart
    labels = [d.strftime("%b %Y") for d in pivot_month_cost.index]
    datasets = []

    for category in pivot_month_cost.columns:
        color = config.transit_categories.get_color(category)
        datasets.append({
            "label": category,
            "data": [round(v, 2) for v in pivot_month_cost[category].tolist()],
            "backgroundColor": color,
        })

    return {
        "labels": labels,
        "datasets": datasets,
    }


@router.get("/api/comparison")
async def get_comparison_data():
    """Return comparison chart data as JSON for Chart.js."""
    store = get_store()
    riders = get_riders(store)
    if not riders:
        return {"labels": [], "datasets": []}

    # Load consolidated data per display name
    rider_dfs = {name: _load_rider_df(store, name) for name in riders}

    # Find date range
    start_date = None
    latest_date = None

    for rider, df in rider_dfs.items():
        if df.empty:
            continue
        rider_first = df["Transaction Date"].min()
        rider_last = df["Transaction Date"].max()
        if start_date is None or rider_first < start_date:
            start_date = rider_first
        if latest_date is None or rider_last > latest_date:
            latest_date = rider_last

    if start_date is None:
        return {"labels": [], "datasets": []}

    start_date = start_date.to_period("M").to_timestamp(how="start")
    latest_date = latest_date.to_period("M").to_timestamp(how="end")
    complete_index = pd.date_range(start=start_date, end=latest_date, freq="MS")

    labels = [d.strftime("%b %Y") for d in complete_index]

    datasets = []
    for i, rider in enumerate(riders):
        df = rider_dfs[rider]
        color = RIDER_COLORS[i % len(RIDER_COLORS)]
        if df.empty:
            datasets.append({
                "label": rider,
                "data": [0] * len(complete_index),
                "borderColor": color,
                "backgroundColor": color,
                "fill": False,
                "tension": 0.3,
            })
            continue
        pivot = (
            df.groupby([pd.Grouper(key="Transaction Date", freq="ME"), "Category"])
            .size()
            .unstack(fill_value=0)
        )
        total = pivot.sum(axis=1)
        total.index = total.index.to_period("M").to_timestamp(how="start")
        total = total.reindex(complete_index, fill_value=0)

        datasets.append({
            "label": rider,
            "data": total.tolist(),
            "borderColor": color,
            "backgroundColor": color,
            "fill": False,
            "tension": 0.3,
        })

    return {
        "labels": labels,
        "datasets": datasets,
    }


@router.get("/api/tables/{rider}")
async def get_table_data(rider: str):
    """Return pivot table data for display."""
    store = get_store()
    df = _load_rider_df(store, rider)

    pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, _ = process_data(df)

    def df_to_records(pivot, is_cost=False):
        records = []
        for idx, row in pivot.iterrows():
            if isinstance(idx, pd.Timestamp):
                label = idx.strftime("%b %Y")
            else:
                label = str(idx)
            record = {"label": label}
            for col in pivot.columns:
                val = row[col]
                if is_cost:
                    record[col] = f"${val:.0f}" if val else "-"
                else:
                    record[col] = int(val) if val else "-"
            records.append(record)
        return records

    return {
        "yearly_trips": {
            "columns": ["Year"] + list(pivot_year.columns),
            "data": df_to_records(pivot_year),
        },
        "monthly_trips": {
            "columns": ["Month"] + list(pivot_month.columns),
            "data": df_to_records(pivot_month),
        },
        "yearly_costs": {
            "columns": ["Year"] + list(pivot_year_cost.columns),
            "data": df_to_records(pivot_year_cost, is_cost=True),
        },
        "monthly_costs": {
            "columns": ["Month"] + list(pivot_month_cost.columns),
            "data": df_to_records(pivot_month_cost, is_cost=True),
        },
    }
