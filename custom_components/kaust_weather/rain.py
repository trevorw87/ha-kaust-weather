"""Conservative integration of sampled rainfall intensity."""
from datetime import datetime, timedelta
from .data import STATION_TZ

MAX_GAP = timedelta(minutes=30)


def period_marker(now: datetime, cycle: str | None) -> str | None:
    local = now.astimezone(STATION_TZ)
    if cycle == "daily":
        return local.date().isoformat()
    if cycle == "monthly":
        return local.strftime("%Y-%m")
    return None


def increment(start: datetime | None, end: datetime, rate: float | None,
              cycle: str | None) -> float:
    """Use the previous valid rate only across short, consecutive observations.

    Clip to the current local calendar period after resetting its total.
    The lifetime sensor retains the entire interval across the boundary.
    """
    if start is None or rate is None or rate < 0:
        return 0.0
    elapsed = end - start
    if elapsed <= timedelta(0) or elapsed > MAX_GAP:
        return 0.0
    if cycle:
        local = end.astimezone(STATION_TZ)
        boundary = local.replace(hour=0, minute=0, second=0, microsecond=0)
        if cycle == "monthly":
            boundary = boundary.replace(day=1)
        start = max(start, boundary)
    return rate * (end - start).total_seconds() / 3600
