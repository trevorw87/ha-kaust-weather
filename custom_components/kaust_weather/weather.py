from __future__ import annotations

from typing import Any

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, METEO_IDS
from .coordinator import KaustWeatherCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KAUST Weather weather entity."""
    coordinator: KaustWeatherCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KaustWeatherEntity(entry.entry_id, coordinator)])


def _live(data: dict[str, Any]) -> dict[str, Any]:
    """Return the nested live AQI response payload."""
    return data.get("live", {}).get("aqi", {}).get("response", {})


def _meteorology(data: dict[str, Any], item_id: int) -> Any:
    """Extract meteorology value by item id."""
    items = _live(data).get("meteorology", [])
    for item in items:
        if item.get("id") == item_id:
            return item.get("value")
    return None


def _aqi_status(data: dict[str, Any]) -> str | None:
    """Return AQI status label."""
    return _live(data).get("label")


def _wind_compass(degrees: float | int | None) -> str | None:
    """Convert wind direction degrees to compass direction."""
    if degrees is None:
        return None

    directions = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW",
    ]
    index = int((float(degrees) + 11.25) / 22.5) % 16
    return directions[index]


class KaustWeatherEntity(CoordinatorEntity[KaustWeatherCoordinator], WeatherEntity):
    """KAUST Weather entity."""

    _attr_has_entity_name = True
    _attr_name = "KAUST Weather"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND

    def __init__(self, entry_id: str, coordinator: KaustWeatherCoordinator) -> None:
        """Initialise the weather entity."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_weather"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "KAUST Weather",
            "manufacturer": "KAUST",
            "model": "Weather API",
        }

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success and bool(self.coordinator.data)

    @property
    def native_temperature(self) -> float | None:
        """Return current temperature."""
        return _meteorology(self.coordinator.data, METEO_IDS["temperature"])

    @property
    def humidity(self) -> float | None:
        """Return current humidity."""
        return _meteorology(self.coordinator.data, METEO_IDS["humidity"])

    @property
    def native_wind_speed(self) -> float | None:
        """Return current wind speed."""
        return _meteorology(self.coordinator.data, METEO_IDS["wind_speed"])

    @property
    def wind_bearing(self) -> float | None:
        """Return wind bearing in degrees."""
        return _meteorology(self.coordinator.data, METEO_IDS["wind_direction"])

    @property
    def condition(self) -> str:
        """Map AQI status to a Home Assistant weather condition."""
        status = (_aqi_status(self.coordinator.data) or "").lower()

        if "hazardous" in status:
            return "exceptional"
        if "very unhealthy" in status:
            return "fog"
        if "unhealthy" in status:
            return "cloudy"
        if "moderate" in status:
            return "partlycloudy"
        if "good" in status:
            return "sunny"

        return "partlycloudy"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional weather attributes."""
        aqi = _live(self.coordinator.data).get("station_index")
        status = _aqi_status(self.coordinator.data)
        wind_bearing = _meteorology(self.coordinator.data, METEO_IDS["wind_direction"])

        return {
            "attribution": ATTRIBUTION,
            "aqi": aqi,
            "aqi_status": status,
            "wind_compass": _wind_compass(wind_bearing),
            "solar_radiation": _meteorology(self.coordinator.data, METEO_IDS["solar_radiation"]),
            "precipitation": _meteorology(self.coordinator.data, METEO_IDS["precipitation"]),
        }