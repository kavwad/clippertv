"""FastAPI routes for ClipperTV dashboard."""

from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from clippertv.config import config
from clippertv.data.factory import get_data_store
from clippertv.viz.data_processing import (
    process_data,
    calculate_summary_stats,
    create_pivot_month,
    create_pivot_year,
    create_pivot_month_cost,
    create_pivot_year_cost,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Cache data store
_data_store = None


def get_store():
    """Get cached data store instance."""
    global _data_store
    if _data_store is None:
        _data_store = get_data_store()
    return _data_store


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, rider: str = "B"):
    """Render the main dashboard page."""
    if rider not in config.riders:
        rider = config.riders[0]

    store = get_store()
    df = store.load_data(rider)

    pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, free_xfers = process_data(df)
    stats = calculate_summary_stats(pivot_month, pivot_month_cost, df)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "rider": rider,
            "riders": config.riders,
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
    df = store.load_data(rider)
    pivot_month = create_pivot_month(df)

    # Sort chronologically for chart (oldest first)
    pivot_month = pivot_month.sort_index(ascending=True)

    # Format for Chart.js stacked bar chart
    labels = [d.strftime("%b %Y") for d in pivot_month.index]
    datasets = []

    for category in pivot_month.columns:
        color = config.transit_categories.color_map.get(category, "#888888")
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
    df = store.load_data(rider)
    pivot_month_cost = create_pivot_month_cost(df)

    # Sort chronologically for chart (oldest first)
    pivot_month_cost = pivot_month_cost.sort_index(ascending=True)

    # Format for Chart.js stacked bar chart
    labels = [d.strftime("%b %Y") for d in pivot_month_cost.index]
    datasets = []

    for category in pivot_month_cost.columns:
        color = config.transit_categories.color_map.get(category, "#888888")
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
    rider_data = store.load_multiple_riders(config.riders)

    # Find date range
    start_date = None
    latest_date = None

    for rider, df in rider_data.items():
        rider_first = df["Transaction Date"].min()
        rider_last = df["Transaction Date"].max()
        if start_date is None or rider_first < start_date:
            start_date = rider_first
        if latest_date is None or rider_last > latest_date:
            latest_date = rider_last

    start_date = start_date.to_period("M").to_timestamp(how="start")
    latest_date = latest_date.to_period("M").to_timestamp(how="end")
    complete_index = pd.date_range(start=start_date, end=latest_date, freq="MS")

    labels = [d.strftime("%b %Y") for d in complete_index]

    chart_colors = {
        "K": config.transit_categories.color_map["Muni Metro"],
        "B": config.transit_categories.color_map["AC Transit"],
    }

    datasets = []
    for rider in config.riders:
        df = rider_data[rider]
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
            "borderColor": chart_colors.get(rider, "#000000"),
            "backgroundColor": chart_colors.get(rider, "#000000"),
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
    df = store.load_data(rider)

    pivot_year = create_pivot_year(df)
    pivot_month = create_pivot_month(df)
    pivot_year_cost = create_pivot_year_cost(df)
    pivot_month_cost = create_pivot_month_cost(df)

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
