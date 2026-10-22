"""Validated station observations; timestamps without offsets are Saudi local time."""
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any

STATION_TZ = timezone(timedelta(hours=3))
MAX_AGE = timedelta(minutes=45)


def number(value: Any) -> float | None:
    """Reject missing sentinels, booleans and non-finite numbers."""
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if isfinite(result) and result != -9999 else None


def timestamp(value: Any) -> datetime | None:
    """Parse an API observation time."""
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        return None
    return result if result.tzinfo else result.replace(tzinfo=STATION_TZ)


def fresh(value: Any, now: datetime | None = None) -> bool:
    observed = timestamp(value)
    now = now or datetime.now(timezone.utc)
    return observed is not None and timedelta(minutes=-5) <= now - observed <= MAX_AGE


def live_response(data: dict) -> dict:
    node = data
    for key in ("live", "aqi", "response"):
        if not isinstance(node, dict):
            return {}
        node = node.get(key)
    return node if isinstance(node, dict) else {}


def items(response: dict, key: str) -> list[dict]:
    value = response.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def usable_timestamp(value: Any) -> bool:
    """Allow delayed observations for display, but reject invalid/future times."""
    observed = timestamp(value)
    return observed is not None and observed <= datetime.now(timezone.utc) + timedelta(minutes=5)


def valid_item(item: dict, *, require_fresh: bool = False) -> bool:
    check_time = fresh if require_fresh else usable_timestamp
    return item.get("missing", 0) in (0, False, "0") and check_time(item.get("time_stamp"))


def meteorology_item(data: dict, item_id: int) -> dict:
    return next((item for item in items(live_response(data), "meteorology")
                 if item.get("id") == item_id), {})


def meteorology(data: dict, item_id: int, *, require_fresh: bool = False) -> float | None:
    item = meteorology_item(data, item_id)
    return number(item.get("value")) if valid_item(item, require_fresh=require_fresh) else None


def aqi(data: dict) -> float | None:
    item = live_response(data)
    value = number(item.get("station_index")) if valid_item(item) else None
    return value if value is not None and value >= 0 else None


def aqi_status(data: dict) -> str | None:
    value = aqi(data)
    if value is None:
        return None
    for limit, label in ((50, "Good"), (100, "Moderate"),
                         (150, "Unhealthy for Sensitive Groups"), (200, "Unhealthy"),
                         (300, "Very Unhealthy")):
        if value <= limit:
            return label
    return "Hazardous"


def reading_attributes(value: Any) -> dict:
    """Expose observation age so delayed values cannot be mistaken for live data."""
    observed = timestamp(value)
    age = (datetime.now(timezone.utc) - observed).total_seconds() / 60 if observed else None
    return {
        "observation_time": observed.isoformat() if observed else None,
        "observation_age_minutes": round(max(0, age), 1) if age is not None else None,
        "data_stale": not fresh(value),
    }


def observation_attributes(data: dict) -> dict:
    response = live_response(data)
    indices = [(number(item.get("pollutant_index")), item.get("shortname"))
               for item in items(response, "poll_index") if valid_item(item)]
    indices = [(value, name) for value, name in indices
               if value is not None and value >= 0 and isinstance(name, str)]
    highest = max((value for value, _ in indices), default=None)
    return {
        **reading_attributes(response.get("time_stamp")),
        "dominant_pollutants": [name for value, name in indices if value == highest],
        "guidance_url": "https://hse.kaust.edu.sa/environment/weathers/air-quality-index",
    }
