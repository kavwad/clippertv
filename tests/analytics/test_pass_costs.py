"""Tests for Caltrain pass cost injection."""

import pytest

from clippertv.analytics.pass_costs import CALTRAIN_MONTHLY_PASS_COST, apply_pass_costs
from clippertv.data.domain import AggregateBucket


def test_pass_month_replaces_caltrain_fare():
    buckets = [
        AggregateBucket(period="2026-02", category="Caltrain", count=1, total_fare=0.0),
        AggregateBucket(period="2026-02", category="BART", count=3, total_fare=13.65),
    ]
    pass_months = {"2026-02"}
    result = apply_pass_costs(buckets, pass_months)
    caltrain = [b for b in result if b.category == "Caltrain"]
    assert len(caltrain) == 1
    assert caltrain[0].total_fare == pytest.approx(CALTRAIN_MONTHLY_PASS_COST)


def test_non_pass_month_unchanged():
    buckets = [
        AggregateBucket(
            period="2026-03", category="Caltrain", count=2, total_fare=15.40
        ),
    ]
    pass_months = {"2026-02"}
    result = apply_pass_costs(buckets, pass_months)
    assert result[0].total_fare == pytest.approx(15.40)


def test_other_categories_unaffected():
    buckets = [
        AggregateBucket(period="2026-02", category="BART", count=3, total_fare=13.65),
    ]
    pass_months = {"2026-02"}
    result = apply_pass_costs(buckets, pass_months)
    assert result[0].total_fare == pytest.approx(13.65)


def test_empty_pass_months():
    buckets = [
        AggregateBucket(
            period="2026-02", category="Caltrain", count=2, total_fare=15.40
        ),
    ]
    result = apply_pass_costs(buckets, set())
    assert result[0].total_fare == pytest.approx(15.40)


def test_multiple_pass_months():
    buckets = [
        AggregateBucket(period="2026-02", category="Caltrain", count=1, total_fare=0.0),
        AggregateBucket(period="2026-03", category="Caltrain", count=1, total_fare=0.0),
        AggregateBucket(
            period="2026-04", category="Caltrain", count=3, total_fare=23.10
        ),
    ]
    pass_months = {"2026-02", "2026-03"}
    result = apply_pass_costs(buckets, pass_months)
    feb = [b for b in result if b.period == "2026-02" and b.category == "Caltrain"][0]
    mar = [b for b in result if b.period == "2026-03" and b.category == "Caltrain"][0]
    apr = [b for b in result if b.period == "2026-04" and b.category == "Caltrain"][0]
    assert feb.total_fare == pytest.approx(CALTRAIN_MONTHLY_PASS_COST)
    assert mar.total_fare == pytest.approx(CALTRAIN_MONTHLY_PASS_COST)
    assert apr.total_fare == pytest.approx(23.10)
