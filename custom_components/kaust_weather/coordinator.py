from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientError

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
        try:
            live = await self._fetch_json(LIVE_URL)
            graph2 = await self._fetch_json(GRAPH2_URL)
            graph3 = await self._fetch_json(GRAPH3_URL)

            return {
                "live": live,
                "graph2": graph2,
                "graph3": graph3,
            }

        except ClientError as err:
            raise UpdateFailed(
                f"HTTP error communicating with KAUST weather API: {err}"
            ) from err
        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error communicating with KAUST weather API: {err}"
            ) from err