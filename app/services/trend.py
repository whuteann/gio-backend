"""Progress Trend chart data — a Python port of gio-member-app/lib/trend.ts."""

from datetime import date as date_type, timedelta

from app.models.reflection import InnerStateSnapshot
from app.services.content import DIMENSION_KEYS
from app.services.gamification import week_start


def build_trend_range(period: str, today: date_type) -> list[dict]:
    if period == "weekly":
        start = week_start(today)
        return [
            {"date": start + timedelta(days=i), "label": (start + timedelta(days=i)).strftime("%a")}
            for i in range(7)
        ]
    first = today.replace(day=1)
    next_month = first.replace(year=first.year + 1, month=1) if first.month == 12 else first.replace(month=first.month + 1)
    days_in_month = (next_month - first).days
    return [{"date": first + timedelta(days=i), "label": str(i + 1)} for i in range(days_in_month)]


def build_trend_series(points: list[dict], snapshots: list[InnerStateSnapshot], today: date_type) -> dict[str, list[int | None]]:
    by_day: dict[date_type, InnerStateSnapshot] = {}
    for s in snapshots:
        day = s.created_at.date()
        if day not in by_day or s.created_at > by_day[day].created_at:
            by_day[day] = s

    sorted_snaps = sorted(snapshots, key=lambda s: s.created_at)
    range_start = points[0]["date"] if points else None
    last_known: InnerStateSnapshot | None = None
    if range_start:
        for s in sorted_snaps:
            if s.created_at.date() < range_start:
                last_known = s
            else:
                break

    result: dict[str, list[int | None]] = {k: [] for k in DIMENSION_KEYS}
    for point in points:
        if point["date"] > today:
            for k in DIMENSION_KEYS:
                result[k].append(None)
            continue
        snap = by_day.get(point["date"])
        if snap:
            last_known = snap
        for k in DIMENSION_KEYS:
            result[k].append(getattr(last_known, k) if last_known else None)
    return result
