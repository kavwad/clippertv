"""Tests for the SQL query layer."""

import sqlite3

import pytest

from clippertv.data.domain import AggregateBucket, Trip
from clippertv.data.queries import QueryLayer
from clippertv.data.schema import create_tables, seed_category_rules


@pytest.fixture
def ql():
    """QueryLayer backed by an in-memory SQLite database with seed data."""
    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    seed_category_rules(conn)
    _insert_test_data(conn)
    return QueryLayer(conn)


def _insert_test_data(conn):
    """Insert test trips spanning two months and two accounts."""
    trips = [
        # Account A: BART trips in Feb + Mar 2026
        (
            "A",
            "T1",
            "2026-02-01T08:00:00",
            "2026-02-01T08:30:00",
            "Rockridge",
            "Embarcadero",
            4.55,
            "BART",
            None,
        ),
        (
            "A",
            "T2",
            "2026-02-15T18:00:00",
            "2026-02-15T18:25:00",
            "Embarcadero",
            "Rockridge",
            4.55,
            "BART",
            None,
        ),
        (
            "A",
            "T3",
            "2026-03-01T08:00:00",
            "2026-03-01T08:30:00",
            "Rockridge",
            "Embarcadero",
            4.55,
            "BART",
            None,
        ),
        # Account A: Muni Metro trip (location = metro station)
        ("A", "T4", "2026-02-10T09:00:00", None, "Powell", None, 2.50, "Muni", None),
        # Account A: Muni Bus trip (location = bus stop)
        (
            "A",
            "T5",
            "2026-02-12T17:00:00",
            None,
            "Haight/Noriega",
            None,
            2.50,
            "Muni",
            None,
        ),
        # Account B: Caltrain with pass
        (
            "B",
            "T6",
            "2026-02-05T07:30:00",
            "2026-02-05T08:15:00",
            "San Francisco",
            "Palo Alto",
            0.0,
            "Caltrain",
            "Caltrain Adult 3 Zone Monthly",
        ),
        # Account B: Caltrain cash ride in March
        (
            "B",
            "T7",
            "2026-03-10T07:30:00",
            "2026-03-10T08:15:00",
            "San Francisco",
            "Palo Alto",
            7.70,
            "Caltrain",
            None,
        ),
    ]
    for t in trips:
        conn.execute(
            """INSERT INTO trips
               (account_number, trip_id, start_datetime, end_datetime,
                start_location, end_location, fare, operator, pass_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            t,
        )
    conn.commit()


def test_monthly_by_category_returns_buckets(ql):
    result = ql.monthly_by_category(["A"])
    assert all(isinstance(b, AggregateBucket) for b in result)
    assert len(result) > 0


def test_monthly_by_category_groups_correctly(ql):
    result = ql.monthly_by_category(["A"])
    feb_bart = [b for b in result if b.period == "2026-02" and b.category == "BART"]
    assert len(feb_bart) == 1
    assert feb_bart[0].count == 2
    assert feb_bart[0].total_fare == pytest.approx(9.10)


def test_monthly_by_category_resolves_muni_metro(ql):
    result = ql.monthly_by_category(["A"])
    feb_metro = [
        b for b in result if b.period == "2026-02" and b.category == "Muni Metro"
    ]
    assert len(feb_metro) == 1
    assert feb_metro[0].count == 1


def test_monthly_by_category_resolves_muni_bus(ql):
    result = ql.monthly_by_category(["A"])
    feb_bus = [b for b in result if b.period == "2026-02" and b.category == "Muni Bus"]
    assert len(feb_bus) == 1
    assert feb_bus[0].count == 1


def test_monthly_by_category_multi_account(ql):
    result = ql.monthly_by_category(["A", "B"])
    feb_all = [b for b in result if b.period == "2026-02"]
    total_count = sum(b.count for b in feb_all)
    # A has 4 trips in Feb, B has 1
    assert total_count == 5


def test_yearly_by_category(ql):
    result = ql.yearly_by_category(["A"])
    y2026 = [b for b in result if b.period == "2026"]
    total = sum(b.count for b in y2026)
    assert total == 5  # A has 5 trips total


def test_pass_months(ql):
    result = ql.pass_months(["B"])
    assert "2026-02" in result
    assert "2026-03" not in result


def test_monthly_trip_counts_for_comparison(ql):
    result = ql.monthly_trip_counts(["A"])
    feb = [r for r in result if r[0] == "2026-02"]
    assert len(feb) == 1
    assert feb[0][1] == 4  # A has 4 trips in Feb


def test_load_trips(ql):
    result = ql.load_trips(["A"])
    assert all(isinstance(t, Trip) for t in result)
    assert len(result) == 5


def test_most_recent_date(ql):
    result = ql.most_recent_date(["A"])
    assert result == "2026-03-01"
