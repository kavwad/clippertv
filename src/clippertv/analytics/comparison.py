"""Cross-rider comparison alignment."""

from __future__ import annotations

from clippertv.data.domain import ComparisonPoint


def align_riders(
    rider_counts: dict[str, list[tuple[str, int]]],
) -> list[ComparisonPoint]:
    """Align multiple riders onto a common month range, filling gaps with zeros."""
    all_periods: set[str] = set()
    for counts in rider_counts.values():
        for period, _ in counts:
            all_periods.add(period)

    if not all_periods:
        return []

    sorted_periods = sorted(all_periods)
    filled_periods = _fill_month_gaps(sorted_periods)

    result = []
    for rider_name, counts in rider_counts.items():
        count_map = dict(counts)
        for period in filled_periods:
            result.append(
                ComparisonPoint(
                    period=period,
                    rider_name=rider_name,
                    count=count_map.get(period, 0),
                )
            )
    return result


def _fill_month_gaps(sorted_periods: list[str]) -> list[str]:
    """Given sorted YYYY-MM strings, fill in any missing months."""
    if len(sorted_periods) <= 1:
        return sorted_periods

    start_y, start_m = map(int, sorted_periods[0].split("-"))
    end_y, end_m = map(int, sorted_periods[-1].split("-"))

    result = []
    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        result.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return result
