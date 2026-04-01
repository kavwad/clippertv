"""Tests for cross-rider comparison alignment."""

from clippertv.analytics.comparison import align_riders


def test_fills_gaps_with_zeros():
    rider_counts = {
        "kaveh": [("2026-01", 5), ("2026-03", 3)],
        "bree": [("2026-02", 2)],
    }
    result = align_riders(rider_counts)
    kaveh_feb = [p for p in result if p.rider_name == "kaveh" and p.period == "2026-02"]
    assert len(kaveh_feb) == 1
    assert kaveh_feb[0].count == 0


def test_all_riders_all_months():
    rider_counts = {
        "kaveh": [("2026-01", 5), ("2026-02", 3)],
        "bree": [("2026-01", 2), ("2026-02", 4)],
    }
    result = align_riders(rider_counts)
    assert len(result) == 4  # 2 riders × 2 months


def test_empty_rider():
    rider_counts = {
        "kaveh": [("2026-01", 5)],
        "bree": [],
    }
    result = align_riders(rider_counts)
    bree = [p for p in result if p.rider_name == "bree"]
    assert len(bree) == 1
    assert bree[0].count == 0
