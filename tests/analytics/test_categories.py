"""Tests for category collapsing (top N / Other)."""

from clippertv.analytics.categories import collapse_categories
from clippertv.data.domain import AggregateBucket


def _buckets(*pairs):
    """Shorthand: pairs of (category, count)."""
    return [AggregateBucket(period="2026-02", category=c, count=n, total_fare=0.0) for c, n in pairs]


def test_keeps_explicit_list():
    buckets = _buckets(("BART", 10), ("Muni Bus", 5), ("Caltrain", 3), ("Ferry", 1))
    result = collapse_categories(buckets, keep=["BART", "Muni Bus"])
    cats = {b.category for b in result}
    assert "BART" in cats
    assert "Muni Bus" in cats
    assert "Other" in cats
    assert "Caltrain" not in cats


def test_other_sums_correctly():
    buckets = _buckets(("BART", 10), ("Muni Bus", 5), ("Caltrain", 3), ("Ferry", 1))
    result = collapse_categories(buckets, keep=["BART", "Muni Bus"])
    other = [b for b in result if b.category == "Other"][0]
    assert other.count == 4


def test_top_n_auto():
    buckets = _buckets(("BART", 10), ("Muni Bus", 5), ("Caltrain", 3), ("Ferry", 1))
    result = collapse_categories(buckets, max_categories=2)
    cats = {b.category for b in result}
    assert "BART" in cats
    assert "Muni Bus" in cats
    assert "Other" in cats


def test_no_other_when_all_kept():
    buckets = _buckets(("BART", 10), ("Muni Bus", 5))
    result = collapse_categories(buckets, max_categories=5)
    cats = {b.category for b in result}
    assert "Other" not in cats


def test_multiple_periods():
    buckets = [
        AggregateBucket(period="2026-02", category="BART", count=10, total_fare=0.0),
        AggregateBucket(period="2026-02", category="Ferry", count=1, total_fare=0.0),
        AggregateBucket(period="2026-03", category="BART", count=8, total_fare=0.0),
        AggregateBucket(period="2026-03", category="Ferry", count=2, total_fare=0.0),
    ]
    result = collapse_categories(buckets, keep=["BART"])
    feb_other = [b for b in result if b.period == "2026-02" and b.category == "Other"]
    mar_other = [b for b in result if b.period == "2026-03" and b.category == "Other"]
    assert feb_other[0].count == 1
    assert mar_other[0].count == 2


def test_other_sums_fares_too():
    buckets = [
        AggregateBucket(period="2026-02", category="Caltrain", count=2, total_fare=15.40),
        AggregateBucket(period="2026-02", category="Ferry", count=1, total_fare=7.00),
    ]
    result = collapse_categories(buckets, keep=[])
    other = [b for b in result if b.category == "Other"][0]
    assert other.total_fare == 22.40
