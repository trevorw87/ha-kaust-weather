from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN, METEO_IDS
from .coordinator import KaustWeatherCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KAUST Weather sensors."""
    coordinator: KaustWeatherCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        # Core weather
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "temperature",
            "Temperature",
            UnitOfTemperature.CELSIUS,
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "humidity",
            "Humidity",
            PERCENTAGE,
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "wind_speed",
            "Wind Speed",
            UnitOfSpeed.METERS_PER_SECOND,
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "wind_direction",
            "Wind Direction",
            "°",
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "wind_compass",
            "Wind Compass",
            None,
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "solar_radiation",
            "Solar Radiation",
            "W/m²",
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "precipitation",
            "Precipitation",
            "mm/h",
        ),
        # AQI summary
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "aqi",
            "AQI",
            "AQI",
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "aqi_status",
            "AQI Status",
            None,
        ),
        # AQI sub-indices
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "o3_index",
            "O3 AQI Index",
            "AQI",
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "co_index",
            "CO AQI Index",
            "AQI",
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "so2_index",
            "SO2 AQI Index",
            "AQI",
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "no2_index",
            "NO2 AQI Index",
            "AQI",
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "pm25_index",
            "PM2.5 AQI Index",
            "AQI",
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "pm10_index",
            "PM10 AQI Index",
            "AQI",
        ),
        # Pollutants
        KaustWeatherSensor(entry.entry_id, coordinator, "no", "NO", "ppb"),
        KaustWeatherSensor(entry.entry_id, coordinator, "no2", "NO2", "ppb"),
        KaustWeatherSensor(entry.entry_id, coordinator, "co", "CO", "ppm"),
        KaustWeatherSensor(entry.entry_id, coordinator, "o3", "O3", "ppb"),
        KaustWeatherSensor(entry.entry_id, coordinator, "so2", "SO2", "ppb"),
        KaustWeatherSensor(entry.entry_id, coordinator, "h2s", "H2S", "ppb"),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "pm10",
            "PM10",
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "pm25",
            "PM2.5",
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        # Derived rainfall totals
        KaustWeatherDerivedRainSensor(
            entry.entry_id,
            coordinator,
            "rain_accumulated",
            "Rain Accumulated",
            reset_cycle=None,
        ),
        KaustWeatherDerivedRainSensor(
            entry.entry_id,
            coordinator,
            "rain_today",
            "Rain Today",
            reset_cycle="daily",
        ),
        KaustWeatherDerivedRainSensor(
            entry.entry_id,
            coordinator,
            "rain_month",
            "Rain Month",
            reset_cycle="monthly",
        ),
    ]

    async_add_entities(entities)


def _live_response(data: dict[str, Any]) -> dict[str, Any]:
    """Return the nested live AQI response payload."""
    return data.get("live", {}).get("aqi", {}).get("response", {})


def _meteorology_value(data: dict[str, Any], item_id: int) -> Any:
    """Extract meteorology value by item id."""
    items = _live_response(data).get("meteorology", [])
    for item in items:
        if item.get("id") == item_id:
            return item.get("value")
    return None


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


def _pollutant_index(data: dict[str, Any], shortname: str) -> Any:
    """Extract AQI pollutant index by shortname."""
    items = _live_response(data).get("poll_index", [])
    for item in items:
        if item.get("shortname") == shortname:
            return item.get("pollutant_index")
    return None


def _graph_latest_value(data: dict[str, Any], graph_key: str, pollutant_name: str) -> Any:
    """Extract latest pollutant value from graph data."""
    graph = data.get(graph_key, [])
    if len(graph) < 2:
        return None

    points = graph[1].get("airpointer_data", [])
    if not points:
        return None

    latest = points[-1]
    for item in latest.get("parameter", []):
        if item.get("name") == pollutant_name:
            value = item.get("value")
            if value in (-9999, -9999.0):
                return None
            return value

    return None


def _safe_float(value: Any) -> float | None:
    """Safely convert a value to float."""
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class KaustWeatherSensor(CoordinatorEntity[KaustWeatherCoordinator], SensorEntity):
    """KAUST Weather raw sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry_id: str,
        coordinator: KaustWeatherCoordinator,
        sensor_key: str,
        name: str,
        unit: str | None,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._sensor_key = sensor_key
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{sensor_key}"
        self._attr_native_unit_of_measurement = unit

        numeric_measurement_keys = {
            "temperature",
            "humidity",
            "wind_speed",
            "wind_direction",
            "solar_radiation",
            "precipitation",
            "aqi",
            "o3_index",
            "co_index",
            "so2_index",
            "no2_index",
            "pm25_index",
            "pm10_index",
            "no",
            "no2",
            "co",
            "o3",
            "so2",
            "h2s",
            "pm10",
            "pm25",
        }
        if sensor_key in numeric_measurement_keys:
            self._attr_state_class = SensorStateClass.MEASUREMENT

        # Only numeric sensors get display precision/device classes
        if sensor_key == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_suggested_display_precision = 1
        elif sensor_key == "humidity":
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_suggested_display_precision = 0
        elif sensor_key == "wind_speed":
            self._attr_device_class = SensorDeviceClass.WIND_SPEED
            self._attr_suggested_display_precision = 1
        elif sensor_key == "precipitation":
            self._attr_device_class = SensorDeviceClass.PRECIPITATION_INTENSITY
            self._attr_suggested_display_precision = 2
        elif sensor_key == "solar_radiation":
            self._attr_suggested_display_precision = 0
        elif sensor_key == "aqi":
            self._attr_suggested_display_precision = 0
        elif sensor_key in {"o3_index", "co_index", "so2_index", "no2_index", "pm25_index", "pm10_index"}:
            self._attr_suggested_display_precision = 0
        elif sensor_key == "pm25":
            self._attr_device_class = SensorDeviceClass.PM25
            self._attr_suggested_display_precision = 0
        elif sensor_key in {"pm10", "no", "no2", "co", "o3", "so2", "h2s"}:
            self._attr_suggested_display_precision = 0

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "KAUST Weather",
            "manufacturer": "KAUST",
            "model": "Weather API",
        }

    @property
    def icon(self) -> str | None:
        """Return an icon for non-device-class sensors."""
        icons = {
            "wind_direction": "mdi:compass-outline",
            "wind_compass": "mdi:compass",
            "solar_radiation": "mdi:white-balance-sunny",
            "aqi": "mdi:blur",
            "aqi_status": "mdi:air-filter",
            "o3_index": "mdi:molecule",
            "co_index": "mdi:molecule-co",
            "so2_index": "mdi:molecule",
            "no2_index": "mdi:molecule",
            "pm25_index": "mdi:blur",
            "pm10_index": "mdi:blur",
            "no": "mdi:molecule",
            "no2": "mdi:molecule",
            "co": "mdi:molecule-co",
            "o3": "mdi:molecule",
            "so2": "mdi:molecule",
            "h2s": "mdi:molecule",
            "pm10": "mdi:blur",
            "pm25": "mdi:blur",
        }
        return icons.get(self._sensor_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return {"attribution": ATTRIBUTION}

    @property
    def native_value(self) -> Any:
        """Return sensor state."""
        data = self.coordinator.data

        if self._sensor_key == "temperature":
            return _meteorology_value(data, METEO_IDS["temperature"])

        if self._sensor_key == "humidity":
            return _meteorology_value(data, METEO_IDS["humidity"])

        if self._sensor_key == "wind_speed":
            return _meteorology_value(data, METEO_IDS["wind_speed"])

        if self._sensor_key == "wind_direction":
            return _meteorology_value(data, METEO_IDS["wind_direction"])

        if self._sensor_key == "wind_compass":
            return _wind_compass(_meteorology_value(data, METEO_IDS["wind_direction"]))

        if self._sensor_key == "solar_radiation":
            return _meteorology_value(data, METEO_IDS["solar_radiation"])

        if self._sensor_key == "precipitation":
            return _meteorology_value(data, METEO_IDS["precipitation"])

        if self._sensor_key == "aqi":
            return _live_response(data).get("station_index")

        if self._sensor_key == "aqi_status":
            return _live_response(data).get("label")

        if self._sensor_key == "o3_index":
            return _pollutant_index(data, "O3")

        if self._sensor_key == "co_index":
            return _pollutant_index(data, "CO")

        if self._sensor_key == "so2_index":
            return _pollutant_index(data, "SO2")

        if self._sensor_key == "no2_index":
            return _pollutant_index(data, "NO2")

        if self._sensor_key == "pm25_index":
            return _pollutant_index(data, "PM 2.5")

        if self._sensor_key == "pm10_index":
            return _pollutant_index(data, "PM 10")

        if self._sensor_key == "no":
            return _graph_latest_value(data, "graph2", "NO")

        if self._sensor_key == "no2":
            return _graph_latest_value(data, "graph2", "NO2")

        if self._sensor_key == "co":
            return _graph_latest_value(data, "graph2", "CO")

        if self._sensor_key == "o3":
            return _graph_latest_value(data, "graph2", "O3")

        if self._sensor_key == "so2":
            return _graph_latest_value(data, "graph2", "SO2")

        if self._sensor_key == "h2s":
            return _graph_latest_value(data, "graph2", "H2S")

        if self._sensor_key == "pm10":
            return _graph_latest_value(data, "graph3", "PM10")

        if self._sensor_key == "pm25":
            return _graph_latest_value(data, "graph3", "PM2.5")

        return None


class KaustWeatherDerivedRainSensor(
    CoordinatorEntity[KaustWeatherCoordinator], RestoreEntity, SensorEntity
):
    """Derived rainfall total sensor calculated from precipitation rate."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "mm"
    _attr_device_class = SensorDeviceClass.PRECIPITATION
    _attr_icon = "mdi:weather-rainy"
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        entry_id: str,
        coordinator: KaustWeatherCoordinator,
        sensor_key: str,
        name: str,
        reset_cycle: str | None,
    ) -> None:
        """Initialise the derived rain sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._sensor_key = sensor_key
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{sensor_key}"
        self._reset_cycle = reset_cycle

        self._value: float = 0.0
        self._last_calc_utc: datetime | None = None
        self._last_period_marker: str | None = None

        if reset_cycle is None:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:
            self._attr_state_class = SensorStateClass.TOTAL

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "KAUST Weather",
            "manufacturer": "KAUST",
            "model": "Weather API",
        }

    @property
    def native_value(self) -> float:
        """Return sensor state."""
        return round(self._value, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes used for restore and debugging."""
        return {
            "attribution": ATTRIBUTION,
            "source_entity": "sensor.kaust_weather_precipitation",
            "reset_cycle": self._reset_cycle or "none",
            "last_calc_utc": self._last_calc_utc.isoformat() if self._last_calc_utc else None,
            "last_period_marker": self._last_period_marker,
        }

    async def async_added_to_hass(self) -> None:
        """Restore previous state after restart."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        restored_value = _safe_float(last_state.state)
        if restored_value is not None:
            self._value = restored_value

        attrs = last_state.attributes

        last_calc_raw = attrs.get("last_calc_utc")
        if isinstance(last_calc_raw, str):
            parsed = dt_util.parse_datetime(last_calc_raw)
            if parsed is not None:
                self._last_calc_utc = parsed

        last_period_marker = attrs.get("last_period_marker")
        if isinstance(last_period_marker, str):
            self._last_period_marker = last_period_marker

    def _current_period_marker(self, now: datetime) -> str | None:
        """Return current reset marker for daily/monthly sensors."""
        if self._reset_cycle == "daily":
            return now.date().isoformat()

        if self._reset_cycle == "monthly":
            return f"{now.year:04d}-{now.month:02d}"

        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update totals when fresh coordinator data arrives."""
        now = dt_util.utcnow()
        current_marker = self._current_period_marker(now)

        if self._reset_cycle is not None and self._last_period_marker is None:
            self._last_period_marker = current_marker

        if (
            self._reset_cycle is not None
            and current_marker is not None
            and self._last_period_marker is not None
            and current_marker != self._last_period_marker
        ):
            self._value = 0.0
            self._last_period_marker = current_marker
            self._last_calc_utc = now
            self.async_write_ha_state()
            return

        rate_mm_per_hour = _safe_float(
            _meteorology_value(self.coordinator.data, METEO_IDS["precipitation"])
        )

        if self._last_calc_utc is None:
            self._last_calc_utc = now
            self.async_write_ha_state()
            return

        if rate_mm_per_hour is not None and rate_mm_per_hour >= 0:
            elapsed_hours = (now - self._last_calc_utc).total_seconds() / 3600.0
            if elapsed_hours > 0:
                self._value += rate_mm_per_hour * elapsed_hours

        self._last_calc_utc = now
        self.async_write_ha_state()