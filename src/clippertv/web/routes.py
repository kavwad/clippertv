"""FastAPI routes for ClipperTV dashboard."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from clippertv.analytics.categories import collapse_categories
from clippertv.analytics.comparison import align_riders
from clippertv.analytics.pass_costs import apply_pass_costs
from clippertv.analytics.summary import compute_summary
from clippertv.config import config, load_account_mapping, load_display_categories
from clippertv.data.domain import AggregateBucket
from clippertv.data.queries import QueryLayer
from clippertv.data.turso_client import get_turso_client, initialize_database

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

RIDER_COLORS = ["#0099CC", "#00A55E", "#FDB813", "#BA0C2F", "#6C6C6C", "#4DD0E1"]

_account_map: dict[str, list[str]] | None = None
_display_categories: list[str] | None = None
_display_categories_loaded: bool = False
_ql: QueryLayer | None = None


def _get_ql() -> QueryLayer:
    global _ql
    if _ql is None:
        initialize_database()
        _ql = QueryLayer(get_turso_client())
    return _ql


def _get_account_map() -> dict[str, list[str]]:
    global _account_map
    if _account_map is None:
        _account_map = load_account_mapping()
    return _account_map


def _accounts_for(rider: str) -> list[str]:
    """Resolve display name to account numbers."""
    acct_map = _get_account_map()
    return acct_map.get(rider.lower(), acct_map.get(rider, [rider]))


def _display_name(name: str) -> str:
    """Capitalize a rider name for display."""
    return name.capitalize() if name.isalpha() else name


def get_riders() -> list[str]:
    """Get rider display names from config."""
    return [_display_name(n) for n in _get_account_map()]


def _keep_categories() -> list[str] | None:
    global _display_categories, _display_categories_loaded
    if not _display_categories_loaded:
        _display_categories = load_display_categories()
        _display_categories_loaded = True
    return _display_categories


def _dashboard_context(rider: str) -> dict:
    """Build template context for a given rider."""
    ql = _get_ql()
    accounts = _accounts_for(rider)
    keep = _keep_categories()

    monthly = collapse_categories(
        ql.monthly_by_category(accounts, include_manual=True),
        keep=keep,
    )

    # Current and previous month for summary
    all_periods = sorted({b.period for b in monthly})
    current_period = all_periods[-1] if all_periods else None
    prev_period = all_periods[-2] if len(all_periods) > 1 else None

    current_buckets = (
        [b for b in monthly if b.period == current_period] if current_period else []
    )
    prev_buckets = (
        [b for b in monthly if b.period == prev_period] if prev_period else []
    )
    recent_date = ql.most_recent_date(accounts)
    stats = compute_summary(
        current_buckets,
        prev_buckets,
        most_recent_date=recent_date,
    )

    most_used_count = 0
    if current_buckets:
        top = max(current_buckets, key=lambda b: b.count)
        most_used_count = top.count

    # Yearly totals — fetch once, derive both trip and cost views
    raw_yearly = ql.yearly_by_category(accounts, include_manual=True)
    yearly = collapse_categories(raw_yearly, keep=keep)
    pass_m = ql.pass_months(accounts)
    yearly_cost = collapse_categories(
        apply_pass_costs(raw_yearly, pass_m),
        keep=keep,
    )

    recent_dt = datetime.strptime(recent_date, "%Y-%m-%d") if recent_date else None
    year_str = str(recent_dt.year if recent_dt else datetime.now().year)

    yearly_trip_total = sum(b.count for b in yearly if b.period == year_str)
    yearly_cost_total = round(
        sum(b.total_fare for b in yearly_cost if b.period == year_str),
    )

    stats_dict = dataclasses.asdict(stats)
    stats_dict["pass_upshot"] = None

    if recent_dt:
        stats_dict["most_recent_month"] = recent_dt.strftime("%B")
        stats_dict["most_recent_month_is_january"] = recent_dt.month == 1
    else:
        stats_dict["most_recent_month"] = ""
        stats_dict["most_recent_month_is_january"] = False

    return {
        "rider": rider,
        "stats": stats_dict,
        "most_used_count": most_used_count,
        "yearly_trip_total": yearly_trip_total,
        "yearly_cost_total": yearly_cost_total,
        "color_map": config.transit_categories.color_map,
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, rider: str = ""):
    """Render the main dashboard page."""
    riders = get_riders()
    if not riders:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "rider": None,
                "riders": [],
                "stats": None,
                "color_map": config.transit_categories.color_map,
            },
        )
    if rider not in riders:
        rider = riders[0]

    ctx = _dashboard_context(rider)
    ctx["riders"] = riders
    return templates.TemplateResponse(request, "dashboard.html", ctx)


@router.get("/partials/dashboard", response_class=HTMLResponse)
async def dashboard_partial(request: Request, rider: str = ""):
    """Return dashboard content partial for HTMX swap."""
    riders = get_riders()
    if not riders:
        return templates.TemplateResponse(
            request,
            "partials/dashboard_content.html",
            {"rider": None, "stats": None},
        )
    if rider not in riders:
        rider = riders[0]

    ctx = _dashboard_context(rider)
    return templates.TemplateResponse(
        request,
        "partials/dashboard_content.html",
        ctx,
    )


@router.get("/api/trips/{rider}")
async def get_trip_data(rider: str):
    """Return trip chart data as JSON for Chart.js."""
    ql = _get_ql()
    accounts = _accounts_for(rider)
    keep = _keep_categories()
    buckets = collapse_categories(
        ql.monthly_by_category(accounts, include_manual=True),
        keep=keep,
    )
    return _buckets_to_chartjs(buckets, value="count")


@router.get("/api/costs/{rider}")
async def get_cost_data(rider: str):
    """Return cost chart data as JSON for Chart.js."""
    ql = _get_ql()
    accounts = _accounts_for(rider)
    keep = _keep_categories()

    buckets = ql.monthly_by_category(accounts, include_manual=True)
    pass_m = ql.pass_months(accounts)
    buckets = apply_pass_costs(buckets, pass_m)
    buckets = collapse_categories(buckets, keep=keep)
    return _buckets_to_chartjs(buckets, value="fare")


@router.get("/api/comparison")
async def get_comparison_data():
    """Return comparison chart data as JSON for Chart.js."""
    ql = _get_ql()
    riders = get_riders()
    if not riders:
        return {"labels": [], "datasets": []}

    rider_counts: dict[str, list[tuple[str, int]]] = {}
    for name in riders:
        accounts = _accounts_for(name)
        rider_counts[name] = ql.monthly_trip_counts(accounts)

    points = align_riders(rider_counts)
    if not points:
        return {"labels": [], "datasets": []}

    periods = sorted({p.period for p in points})
    labels = [_format_period(p) for p in periods]
    datasets = []

    for i, name in enumerate(riders):
        color = RIDER_COLORS[i % len(RIDER_COLORS)]
        rider_points = {p.period: p.count for p in points if p.rider_name == name}
        datasets.append(
            {
                "label": name,
                "data": [rider_points.get(p, 0) for p in periods],
                "borderColor": color,
                "backgroundColor": color,
                "fill": False,
                "tension": 0.3,
            }
        )

    return {"labels": labels, "datasets": datasets}


def _table_context(rider: str) -> dict:
    """Build table data for a rider, shared by JSON and HTML endpoints."""
    ql = _get_ql()
    accounts = _accounts_for(rider)
    keep = _keep_categories()
    pass_m = ql.pass_months(accounts)

    raw_monthly = ql.monthly_by_category(accounts, include_manual=True)
    monthly = collapse_categories(raw_monthly, keep=keep)
    monthly_cost = collapse_categories(
        apply_pass_costs(raw_monthly, pass_m),
        keep=keep,
    )

    raw_yearly = ql.yearly_by_category(accounts, include_manual=True)
    yearly = collapse_categories(raw_yearly, keep=keep)
    yearly_cost = collapse_categories(
        apply_pass_costs(raw_yearly, pass_m),
        keep=keep,
    )

    return {
        "yearly_trips": _buckets_to_table(yearly, "count"),
        "yearly_costs": _buckets_to_table(yearly_cost, "fare"),
        "monthly_trips": _buckets_to_table(monthly, "count"),
        "monthly_costs": _buckets_to_table(monthly_cost, "fare"),
    }


@router.get("/api/tables/{rider}")
async def get_table_data(rider: str):
    """Return pivot table data for display."""
    return _table_context(rider)


@router.get("/partials/tables/{rider}", response_class=HTMLResponse)
async def get_table_html(request: Request, rider: str):
    """Return pre-rendered table HTML for HTMX swap."""
    return templates.TemplateResponse(
        request,
        "partials/tables.html",
        _table_context(rider),
    )


# --- Helpers ---


def _format_period(period: str) -> str:
    """'2026-03' -> 'Mar 2026', '2026' -> '2026'."""
    try:
        dt = datetime.strptime(period, "%Y-%m")
        return dt.strftime("%b %Y")
    except ValueError:
        return period


def _pivot_buckets(
    buckets: list[AggregateBucket],
    value: str,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Group buckets into a period->category->value dict,
    preserving category order."""
    by_period: dict[str, dict[str, float]] = defaultdict(dict)
    seen: set[str] = set()
    categories: list[str] = []
    for b in buckets:
        if b.category not in seen:
            seen.add(b.category)
            categories.append(b.category)
        by_period[b.period][b.category] = b.total_fare if value == "fare" else b.count
    return by_period, categories


def _buckets_to_chartjs(
    buckets: list[AggregateBucket],
    *,
    value: str,
) -> dict:
    """Convert AggregateBuckets to Chart.js format."""
    by_period, categories = _pivot_buckets(buckets, value)
    periods = sorted(by_period.keys())
    labels = [_format_period(p) for p in periods]

    datasets = []
    for cat in categories:
        color = config.transit_categories.get_color(cat)
        data = [by_period[p].get(cat, 0) for p in periods]
        if value == "fare":
            data = [round(v, 2) for v in data]
        datasets.append(
            {
                "label": cat,
                "data": data,
                "backgroundColor": color,
            }
        )

    return {"labels": labels, "datasets": datasets}


def _buckets_to_table(
    buckets: list[AggregateBucket],
    value_type: str,
) -> dict:
    """Convert AggregateBuckets to table format for the frontend."""
    by_period, categories = _pivot_buckets(buckets, value_type)
    periods = sorted(by_period.keys(), reverse=True)
    columns = ["Period"] + categories
    data = []
    for p in periods:
        record: dict[str, str | int] = {"label": _format_period(p)}
        for cat in categories:
            val = by_period[p].get(cat, 0)
            if value_type == "fare":
                record[cat] = f"${val:.0f}" if val else "-"
            else:
                record[cat] = int(val) if val else "-"
        data.append(record)

    return {"columns": columns, "data": data}
