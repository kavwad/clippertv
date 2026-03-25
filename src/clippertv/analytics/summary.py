"""Summary stats computation for the dashboard."""

from __future__ import annotations

from clippertv.data.domain import AggregateBucket, RiderSummary


def compute_summary(
    current_month: list[AggregateBucket],
    previous_month: list[AggregateBucket],
    *,
    most_recent_date: str | None,
) -> RiderSummary:
    """Compute dashboard summary stats from current and previous month buckets."""
    trips_now = sum(b.count for b in current_month)
    cost_now = round(sum(b.total_fare for b in current_month))

    trips_prev = sum(b.count for b in previous_month)
    cost_prev = round(sum(b.total_fare for b in previous_month))

    trip_diff = trips_prev - trips_now
    cost_diff = cost_prev - cost_now

    most_used = max(current_month, key=lambda b: b.count).category if current_month else "N/A"

    return RiderSummary(
        trips_this_month=trips_now,
        cost_this_month=float(cost_now),
        trip_diff=abs(trip_diff),
        trip_diff_text="fewer" if trip_diff >= 0 else "more",
        cost_diff=abs(float(cost_diff)),
        cost_diff_text="less" if cost_diff >= 0 else "more",
        most_used_mode=most_used,
        most_recent_date=most_recent_date or "",
    )
