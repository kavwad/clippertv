"""Tests for summary stats computation."""

from clippertv.analytics.summary import compute_summary
from clippertv.data.domain import AggregateBucket, RiderSummary


def test_basic_summary():
    current = [
        AggregateBucket(period="2026-03", category="BART", count=10, total_fare=45.50),
        AggregateBucket(
            period="2026-03", category="Muni Bus", count=5, total_fare=12.50
        ),
    ]
    previous = [
        AggregateBucket(period="2026-02", category="BART", count=8, total_fare=36.40),
    ]
    result = compute_summary(current, previous, most_recent_date="2026-03-15")
    assert isinstance(result, RiderSummary)
    assert result.trips_this_month == 15
    assert result.cost_this_month == 58.0
    assert result.most_used_mode == "BART"


def test_diff_text_fewer():
    current = [
        AggregateBucket(period="2026-03", category="BART", count=5, total_fare=20.0)
    ]
    previous = [
        AggregateBucket(period="2026-02", category="BART", count=10, total_fare=40.0)
    ]
    result = compute_summary(current, previous, most_recent_date="2026-03-15")
    assert result.trip_diff == 5
    assert result.trip_diff_text == "fewer"
    assert result.cost_diff_text == "less"


def test_diff_text_more():
    current = [
        AggregateBucket(period="2026-03", category="BART", count=10, total_fare=40.0)
    ]
    previous = [
        AggregateBucket(period="2026-02", category="BART", count=5, total_fare=20.0)
    ]
    result = compute_summary(current, previous, most_recent_date="2026-03-15")
    assert result.trip_diff_text == "more"
    assert result.cost_diff_text == "more"


def test_no_previous_month():
    current = [
        AggregateBucket(period="2026-03", category="BART", count=10, total_fare=40.0)
    ]
    result = compute_summary(current, [], most_recent_date="2026-03-15")
    # No previous month: trips_prev=0, trips_now=10 → diff=10, "more"
    assert result.trip_diff == 10
    assert result.trip_diff_text == "more"
