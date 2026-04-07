"""FastAPI routes for ClipperTV dashboard."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from clippertv.analytics.categories import collapse_categories
from clippertv.analytics.comparison import align_riders
from clippertv.analytics.pass_costs import apply_pass_costs
from clippertv.analytics.summary import compute_summary
from clippertv.config import config
from clippertv.data.domain import AggregateBucket
from clippertv.data.models import User
from clippertv.data.queries import QueryLayer
from clippertv.data.turso_client import get_turso_client, initialize_database
from clippertv.web.auth import get_user_store, require_auth

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

RIDER_COLORS = ["#0099CC", "#00A55E", "#FDB813", "#BA0C2F", "#6C6C6C", "#4DD0E1"]

_ql: QueryLayer | None = None


def _get_ql() -> QueryLayer:
    global _ql
    if _ql is None:
        initialize_database()
        _ql = QueryLayer(get_turso_client())
    return _ql


def _get_user_accounts(user: User) -> list[str]:
    """Get all account numbers for an authenticated user."""
    store = get_user_store()
    cards = store.get_user_clipper_cards(user.id)
    return [c.account_number for c in cards]


def _dashboard_context(user: User) -> dict:
    """Build template context for the authenticated user."""
    ql = _get_ql()
    accounts = _get_user_accounts(user)
    keep = user.display_categories
    rider = user.name or user.email

    if not accounts:
        return {
            "rider": rider,
            "stats": None,
            "most_used_count": 0,
            "yearly_trip_total": 0,
            "yearly_cost_total": 0,
            "color_map": config.transit_categories.color_map,
        }

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
async def dashboard(request: Request, user: User = Depends(require_auth)):
    """Render the main dashboard page."""
    ctx = _dashboard_context(user)
    ctx["user"] = user
    return templates.TemplateResponse(request, "dashboard.html", ctx)


@router.get("/partials/dashboard", response_class=HTMLResponse)
async def dashboard_partial(request: Request, user: User = Depends(require_auth)):
    """Return dashboard content partial for HTMX swap."""
    ctx = _dashboard_context(user)
    return templates.TemplateResponse(
        request,
        "partials/dashboard_content.html",
        ctx,
    )


@router.get("/api/trips")
async def get_trip_data(user: User = Depends(require_auth)):
    """Return trip chart data as JSON for Chart.js."""
    ql = _get_ql()
    accounts = _get_user_accounts(user)
    keep = user.display_categories
    buckets = collapse_categories(
        ql.monthly_by_category(accounts, include_manual=True),
        keep=keep,
    )
    return _buckets_to_chartjs(buckets, value="count")


@router.get("/api/costs")
async def get_cost_data(user: User = Depends(require_auth)):
    """Return cost chart data as JSON for Chart.js."""
    ql = _get_ql()
    accounts = _get_user_accounts(user)
    keep = user.display_categories

    buckets = ql.monthly_by_category(accounts, include_manual=True)
    pass_m = ql.pass_months(accounts)
    buckets = apply_pass_costs(buckets, pass_m)
    buckets = collapse_categories(buckets, keep=keep)
    return _buckets_to_chartjs(buckets, value="fare")


@router.get("/api/comparison")
async def get_comparison_data(user: User = Depends(require_auth)):
    """Return comparison chart data as JSON for Chart.js.

    Compares the authenticated user's cards grouped by rider_name.
    """
    ql = _get_ql()
    store = get_user_store()
    cards = store.get_user_clipper_cards(user.id)
    if not cards:
        return {"labels": [], "datasets": []}

    # Group cards by rider_name for comparison
    rider_accounts: dict[str, list[str]] = defaultdict(list)
    for card in cards:
        rider_accounts[card.rider_name].append(card.account_number)

    rider_names = list(rider_accounts.keys())
    rider_counts: dict[str, list[tuple[str, int]]] = {}
    for name in rider_names:
        rider_counts[name] = ql.monthly_trip_counts(rider_accounts[name])

    points = align_riders(rider_counts)
    if not points:
        return {"labels": [], "datasets": []}

    periods = sorted({p.period for p in points})
    labels = [_format_period(p) for p in periods]
    datasets = []

    for i, name in enumerate(rider_names):
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


@router.get("/api/tables")
async def get_table_data(user: User = Depends(require_auth)):
    """Return pivot table data for display."""
    return _table_context(user)


@router.get("/partials/tables", response_class=HTMLResponse)
async def get_table_html(request: Request, user: User = Depends(require_auth)):
    """Return pre-rendered table HTML for HTMX swap."""
    return templates.TemplateResponse(
        request,
        "partials/tables.html",
        _table_context(user),
    )


def _table_context(user: User) -> dict:
    """Build table data for the user's accounts."""
    ql = _get_ql()
    accounts = _get_user_accounts(user)
    keep = user.display_categories
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
