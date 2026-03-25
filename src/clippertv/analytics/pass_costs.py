"""Caltrain pass cost injection for cost views."""

from clippertv.data.domain import AggregateBucket

CALTRAIN_MONTHLY_PASS_COST = 184.80


def apply_pass_costs(
    buckets: list[AggregateBucket],
    pass_months: set[str],
) -> list[AggregateBucket]:
    """Replace Caltrain fares with flat pass cost in pass months."""
    if not pass_months:
        return list(buckets)

    result = []
    for b in buckets:
        if b.category == "Caltrain" and b.period in pass_months:
            result.append(AggregateBucket(
                period=b.period,
                category=b.category,
                count=b.count,
                total_fare=CALTRAIN_MONTHLY_PASS_COST,
            ))
        else:
            result.append(b)
    return result
