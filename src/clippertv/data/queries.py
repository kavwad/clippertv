"""SQL query layer for ClipperTV. Returns typed domain objects."""

from __future__ import annotations

from datetime import datetime

from clippertv.data.domain import AggregateBucket, Trip

_CATEGORY_JOIN = """
    LEFT JOIN category_rules cr_exact
        ON cr_exact.operator = t.operator
        AND cr_exact.location = t.start_location
    LEFT JOIN category_rules cr_fallback
        ON cr_fallback.operator = t.operator
        AND cr_fallback.location = ''
"""

_CATEGORY_EXPR = "COALESCE(cr_exact.category, cr_fallback.category, t.operator)"


def _placeholders(n: int) -> str:
    return ", ".join(["?"] * n)


class QueryLayer:
    """Thin SQL query builder returning typed domain objects."""

    def __init__(self, conn):
        self.conn = conn

    def monthly_by_category(
        self,
        account_numbers: list[str],
        *,
        include_manual: bool = False,
    ) -> list[AggregateBucket]:
        """Monthly trip counts and fare sums, grouped by derived category."""
        return self._aggregate_by_category("%Y-%m", account_numbers, include_manual)

    def yearly_by_category(
        self,
        account_numbers: list[str],
        *,
        include_manual: bool = False,
    ) -> list[AggregateBucket]:
        """Yearly trip counts and fare sums, grouped by derived category."""
        return self._aggregate_by_category("%Y", account_numbers, include_manual)

    def _aggregate_by_category(
        self,
        time_fmt: str,
        account_numbers: list[str],
        include_manual: bool,
    ) -> list[AggregateBucket]:
        source = self._source_clause(account_numbers, include_manual)
        query = f"""
            SELECT period, category,
                   COUNT(*) AS count, COALESCE(SUM(fare), 0.0) AS total_fare
            FROM (
                SELECT
                    strftime('{time_fmt}', t.start_datetime) AS period,
                    {_CATEGORY_EXPR} AS category,
                    t.fare
                FROM ({source}) t
                {_CATEGORY_JOIN}
            )
            GROUP BY period, category
            ORDER BY period, category
        """
        params = account_numbers * (2 if include_manual else 1)
        rows = self.conn.execute(query, params).fetchall()
        return [
            AggregateBucket(period=r[0], category=r[1], count=r[2], total_fare=r[3])
            for r in rows
        ]

    def pass_months(self, account_numbers: list[str]) -> set[str]:
        """Return set of YYYY-MM strings where rider had a Monthly pass.

        Checks both trips and manual_trips, since manual entries
        may be the only record of pass usage in some months.
        """
        ph = _placeholders(len(account_numbers))
        query = f"""
            SELECT DISTINCT strftime('%Y-%m', start_datetime) AS period
            FROM (
                SELECT start_datetime, pass_type
                FROM trips WHERE account_number IN ({ph})
                UNION ALL
                SELECT start_datetime, pass_type
                FROM manual_trips WHERE account_number IN ({ph})
            )
            WHERE pass_type LIKE '%Monthly%'
        """
        rows = self.conn.execute(query, account_numbers * 2).fetchall()
        return {r[0] for r in rows}

    def monthly_trip_counts(self, account_numbers: list[str]) -> list[tuple[str, int]]:
        """Monthly total trip counts (all categories combined). For comparison chart."""
        ph = _placeholders(len(account_numbers))
        query = f"""
            SELECT strftime('%Y-%m', start_datetime) AS period, COUNT(*) AS count
            FROM trips
            WHERE account_number IN ({ph})
            GROUP BY period
            ORDER BY period
        """
        rows = self.conn.execute(query, account_numbers).fetchall()
        return [(r[0], r[1]) for r in rows]

    def load_trips(self, account_numbers: list[str]) -> list[Trip]:
        """Load individual trip records with derived category."""
        ph = _placeholders(len(account_numbers))
        query = f"""
            SELECT
                t.id, t.account_number, t.trip_id, t.start_datetime, t.end_datetime,
                t.start_location, t.end_location, t.fare, t.operator, t.pass_type,
                {_CATEGORY_EXPR} AS category
            FROM trips t
            {_CATEGORY_JOIN}
            WHERE t.account_number IN ({ph})
            ORDER BY t.start_datetime DESC
        """
        rows = self.conn.execute(query, account_numbers).fetchall()
        return [
            Trip(
                id=r[0],
                account_number=r[1],
                trip_id=r[2],
                start_datetime=datetime.fromisoformat(r[3]),
                end_datetime=datetime.fromisoformat(r[4]) if r[4] else None,
                start_location=r[5],
                end_location=r[6],
                fare=r[7],
                operator=r[8],
                pass_type=r[9],
                category=r[10],
            )
            for r in rows
        ]

    def most_recent_date(self, account_numbers: list[str]) -> str | None:
        """Return ISO date string of the most recent trip."""
        ph = _placeholders(len(account_numbers))
        row = self.conn.execute(
            f"SELECT MAX(DATE(start_datetime)) FROM trips"
            f" WHERE account_number IN ({ph})",
            account_numbers,
        ).fetchone()
        return row[0] if row and row[0] else None

    def _source_clause(self, account_numbers: list[str], include_manual: bool) -> str:
        ph = _placeholders(len(account_numbers))
        base = f"SELECT * FROM trips WHERE account_number IN ({ph})"
        if not include_manual:
            return base
        return (
            f"{base} UNION ALL"
            f" SELECT * FROM manual_trips WHERE account_number IN ({ph})"
        )
