"""Domain objects for the ClipperTV data pipeline."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Trip:
    """Single trip record from the database."""
    id: int
    account_number: str
    trip_id: str | None
    start_datetime: datetime
    end_datetime: datetime | None
    start_location: str | None
    end_location: str | None
    fare: float | None
    operator: str
    pass_type: str | None
    category: str  # derived via category_rules at query time


@dataclass(frozen=True)
class AggregateBucket:
    """A single cell in an aggregation: period × category → value."""
    period: str        # "2026-03", "2026", etc.
    category: str
    count: int
    total_fare: float


@dataclass(frozen=True)
class RiderSummary:
    """Summary statistics for a rider over a time range."""
    trips_this_month: int
    cost_this_month: float
    trip_diff: int
    trip_diff_text: str
    cost_diff: float
    cost_diff_text: str
    most_used_mode: str
    most_recent_date: str


@dataclass(frozen=True)
class ComparisonPoint:
    """Single data point in a cross-rider comparison."""
    period: str
    rider_name: str
    count: int
