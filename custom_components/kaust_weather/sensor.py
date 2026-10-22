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
    UnitOfDensity,
    PERCENTAGE,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN, METEO_IDS
from .coordinator import KaustWeatherCoordinator
from .data import (STATION_TZ, aqi, aqi_status, items, live_response, meteorology,
                   meteorology_item, number, observation_attributes, reading_attributes,
                   timestamp, usable_timestamp, valid_item)
from .rain import increment, period_marker


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
            UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        ),
        KaustWeatherSensor(
            entry.entry_id,
            coordinator,
            "pm25",
            "PM2.5",
            UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
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
    return live_response(data)


def _meteorology_value(data: dict[str, Any], item_id: int) -> Any:
    return meteorology(data, item_id)


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
    for item in items(_live_response(data), "poll_index"):
        if item.get("shortname") == shortname:
            return number(item.get("pollutant_index")) if valid_item(item) else None
    return None


def _graph_latest_point(data: dict[str, Any], graph_key: str) -> dict:
    """Find the latest timestamped point without assuming response order."""
    graph = data.get(graph_key) or []
    if not isinstance(graph, list):
        return {}
    points = [point for section in graph if isinstance(section, dict)
              for point in items(section, "airpointer_data")
              if timestamp(point.get("date_time")) is not None]
    if not points:
        return {}
    return max(points, key=lambda point: timestamp(point.get("date_time")))


def _graph_latest_value(data: dict[str, Any], graph_key: str, pollutant_name: str) -> Any:
    """Keep delayed station readings visible with explicit age metadata."""
    latest = _graph_latest_point(data, graph_key)
    if not usable_timestamp(latest.get("date_time")):
        return None
    for item in items(latest, "parameter"):
        if item.get("name") == pollutant_name:
            return number(item.get("value")) if item.get("missing", 0) in (0, False, "0") else None
    return None


def _safe_float(value: Any) -> float | None:
    return number(value)


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
        attrs = {"attribution": ATTRIBUTION}
        if self._sensor_key in METEO_IDS or self._sensor_key == "wind_compass":
            key = "wind_direction" if self._sensor_key == "wind_compass" else self._sensor_key
            item = meteorology_item(self.coordinator.data, METEO_IDS[key])
            attrs.update(reading_attributes(item.get("time_stamp")))
        elif self._sensor_key in {"no", "no2", "co", "o3", "so2", "h2s", "pm10", "pm25"}:
            graph_key = "graph3" if self._sensor_key in {"pm10", "pm25"} else "graph2"
            point = _graph_latest_point(self.coordinator.data, graph_key)
            attrs.update(reading_attributes(point.get("date_time")))
        if self._sensor_key in {"aqi", "aqi_status"} or self._sensor_key.endswith("_index"):
            attrs.update(observation_attributes(self.coordinator.data))
            if self._sensor_key.startswith(("pm25", "pm10")):
                attrs["averaging_period"] = "3 hours, weighted toward latest hour (KAUST documentation)"
            elif self._sensor_key.startswith(("o3", "co")):
                attrs["averaging_period"] = "8 hours"
            elif self._sensor_key.startswith(("so2", "no2")):
                attrs["averaging_period"] = "1 hour"
        return attrs

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
            return aqi(data)

        if self._sensor_key == "aqi_status":
            return aqi_status(data)

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
        self._previous_rate: float | None = None

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
    def last_reset(self) -> datetime | None:
        """Identify daily/monthly resets for long-term statistics."""
        if not self._reset_cycle or not self._last_period_marker:
            return None
        marker = self._last_period_marker
        if self._reset_cycle == "monthly":
            marker += "-01"
        return datetime.fromisoformat(marker).replace(tzinfo=STATION_TZ)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes used for restore and debugging."""
        return {
            "attribution": ATTRIBUTION,
            "estimated": True,
            "calculation": "sampled precipitation intensity; gaps over 30 minutes excluded",
            "reset_timezone": "Asia/Riyadh",
            "reset_cycle": self._reset_cycle or "none",
            "last_calc_utc": self._last_calc_utc.isoformat() if self._last_calc_utc else None,
            "last_period_marker": self._last_period_marker,
        }

    async def async_added_to_hass(self) -> None:
        """Restore previous state after restart."""
        await super().async_added_to_hass()

        if self._reset_cycle:
            # Station calendar is Saudi local time, independent of HA's timezone.
            self.async_on_remove(async_track_utc_time_change(
                self.hass, self._async_reset_period, hour=21, minute=0, second=0
            ))

        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        restored_value = _safe_float(last_state.state)
        if restored_value is not None:
            self._value = restored_value

        attrs = last_state.attributes

        last_period_marker = attrs.get("last_period_marker")
        if isinstance(last_period_marker, str):
            self._last_period_marker = last_period_marker

        self._async_reset_period(dt_util.utcnow())

    @callback
    def _async_reset_period(self, now: datetime) -> None:
        """Reset at station midnight even when observations stop."""
        marker = self._current_period_marker(now)
        if self._reset_cycle and marker != self._last_period_marker:
            self._value = 0.0
            self._last_period_marker = marker
            self.async_write_ha_state()

    def _current_period_marker(self, now: datetime) -> str | None:
        """Return current reset marker for daily/monthly sensors."""
        return period_marker(now, self._reset_cycle)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Integrate each station observation once; never fill outages with rain."""
        now = dt_util.utcnow()
        marker = self._current_period_marker(now)
        if self._reset_cycle and marker != self._last_period_marker:
            self._value = 0.0
            self._last_period_marker = marker

        item = meteorology_item(self.coordinator.data, METEO_IDS["precipitation"])
        observed = timestamp(item.get("time_stamp"))
        rate = meteorology(self.coordinator.data, METEO_IDS["precipitation"], require_fresh=True)
        if not self.coordinator.last_update_success or rate is None or rate < 0:
            self._last_calc_utc = None
            self._previous_rate = None
        elif observed is not None and (self._last_calc_utc is None or observed > self._last_calc_utc):
            # A delayed pre-midnight observation must not enter today's total.
            if not self._reset_cycle or period_marker(observed, self._reset_cycle) == marker:
                self._value += increment(self._last_calc_utc, observed,
                                         self._previous_rate, self._reset_cycle)
            self._last_calc_utc = observed
            self._previous_rate = rate
        self.async_write_ha_state()
