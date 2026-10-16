from __future__ import annotations

import logging
import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, GRAPH2_URL, GRAPH3_URL, LIVE_URL

_LOGGER = logging.getLogger(__name__)

HEADERS = {
    "Accept": "*/*",
    "Referer": "https://kaustweather.kaust.edu.sa/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}


class KaustWeatherCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch KAUST weather and AQI data."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._session = async_get_clientsession(hass)

    async def _fetch_json(self, url: str) -> Any:
        """Fetch a JSON endpoint."""
        async with self._session.get(url, headers=HEADERS, timeout=15) as response:
            response.raise_for_status()
            return await response.json()

    async def _async_update_data(self) -> dict[str, Any]:
        endpoints = {"live": LIVE_URL, "graph2": GRAPH2_URL, "graph3": GRAPH3_URL}
        results = await asyncio.gather(
            *(self._fetch_json(url) for url in endpoints.values()),
            return_exceptions=True,
        )
        data: dict[str, Any] = {}
        errors = {}
        for key, result in zip(endpoints, results):
            expected = dict if key == "live" else list
            if isinstance(result, Exception) or not isinstance(result, expected):
                errors[key] = str(result) if isinstance(result, Exception) else "Invalid response shape"
                data[key] = {} if key == "live" else []
                _LOGGER.warning("KAUST %s endpoint unavailable: %s", key, errors[key])
            else:
                data[key] = result
        if len(errors) == len(endpoints):
            raise UpdateFailed("All KAUST station endpoints failed")
        data["endpoint_errors"] = errors
        return data
