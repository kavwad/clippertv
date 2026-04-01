"""Category collapsing: keep top N categories, fold rest into Other."""

from __future__ import annotations

from collections import defaultdict

from clippertv.data.domain import AggregateBucket

DEFAULT_MAX_CATEGORIES = 8


def collapse_categories(
    buckets: list[AggregateBucket],
    *,
    keep: list[str] | None = None,
    max_categories: int = DEFAULT_MAX_CATEGORIES,
) -> list[AggregateBucket]:
    """Collapse categories to `keep` list or top N, folding rest into Other."""
    if keep is None:
        keep = _top_categories(buckets, max_categories)
    keep_set = set(keep)

    by_period: dict[str, list[AggregateBucket]] = defaultdict(list)
    for b in buckets:
        by_period[b.period].append(b)

    result = []
    for period, period_buckets in sorted(by_period.items()):
        other_count = 0
        other_fare = 0.0
        for b in period_buckets:
            if b.category in keep_set:
                result.append(b)
            else:
                other_count += b.count
                other_fare += b.total_fare
        if other_count > 0:
            result.append(
                AggregateBucket(
                    period=period,
                    category="Other",
                    count=other_count,
                    total_fare=other_fare,
                )
            )
    return result


def _top_categories(buckets: list[AggregateBucket], n: int) -> list[str]:
    """Return top N categories by total count across all periods."""
    totals: dict[str, int] = defaultdict(int)
    for b in buckets:
        if b.category not in ("Reload", "Unknown"):
            totals[b.category] += b.count
    return sorted(totals, key=lambda k: totals[k], reverse=True)[:n]
