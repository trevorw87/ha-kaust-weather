"""Exercise entity callbacks with a minimal HA boundary (no running instance)."""
import ast
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import types
import unittest
from unittest.mock import AsyncMock

from test_observations import ROOT, data, rain


class Entity:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator):
        self.coordinator = coordinator

    def async_write_ha_state(self):
        pass

    async def async_added_to_hass(self):
        pass

    def async_on_remove(self, remove):
        pass


class Restore:
    pass


class Sensor:
    pass


def load_definitions(filename, namespace):
    """Run production definitions while replacing only framework imports."""
    tree = ast.parse((ROOT / filename).read_text())
    tree.body = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    exec(compile(tree, filename, "exec"), namespace)
    return namespace


def sensor_namespace(now):
    ns = dict(vars(data))
    ns.update({"Any": object, "CoordinatorEntity": Entity, "SensorEntity": Sensor,
               "RestoreEntity": Restore, "KaustWeatherCoordinator": object,
               "SensorDeviceClass": types.SimpleNamespace(PRECIPITATION="precipitation"),
               "SensorStateClass": types.SimpleNamespace(TOTAL="total", TOTAL_INCREASING="total_increasing"),
               "callback": lambda fn: fn, "dt_util": types.SimpleNamespace(utcnow=lambda: now),
               "METEO_IDS": {"precipitation": 7}, "increment": rain.increment,
               "period_marker": rain.period_marker})
    # Postponed annotations keep HA type hints outside this lightweight boundary.
    ns["__builtins__"] = __builtins__
    tree = ast.parse((ROOT / "sensor.py").read_text())
    tree.body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + [
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    ast.fix_missing_locations(tree)
    exec(compile(tree, "sensor.py", "exec"), ns)
    return ns


class EntityTests(unittest.TestCase):
    def test_duplicate_failure_recovery_and_midnight(self):
        now = datetime.now(timezone.utc).replace(hour=21, minute=10, second=0, microsecond=0)
        ns = sensor_namespace(now)
        item = {"id": 7, "value": 6, "time_stamp": now.isoformat()}
        coordinator = types.SimpleNamespace(last_update_success=True, data={
            "live": {"aqi": {"response": {"meteorology": [item]}}}})
        # Freeze parsing freshness too, since test dates deliberately sit at midnight.
        ns["meteorology"] = lambda payload, key: 6
        sensor = ns["KaustWeatherDerivedRainSensor"]("entry", coordinator, "rain_today", "Rain Today", "daily")
        sensor._value = 10
        sensor._last_period_marker = rain.period_marker(now - timedelta(days=1), "daily")
        sensor._last_calc_utc = now - timedelta(minutes=15)
        sensor._previous_rate = 6
        sensor._handle_coordinator_update()
        self.assertEqual(sensor.native_value, 1)
        sensor._handle_coordinator_update()
        self.assertEqual(sensor.native_value, 1)
        coordinator.last_update_success = False
        sensor._handle_coordinator_update()
        self.assertIsNone(sensor._last_calc_utc)
        coordinator.last_update_success = True
        sensor._handle_coordinator_update()
        self.assertEqual(sensor.native_value, 1)
        sensor._async_reset_period(now + timedelta(days=1))
        self.assertEqual(sensor.native_value, 0)

    def test_graph_order_and_sentinel(self):
        now = datetime.now(timezone.utc)
        ns = sensor_namespace(now)
        latest = {"date_time": now.isoformat(), "parameter": [{"name": "H2S", "value": "-9999"}]}
        older = {"date_time": (now - timedelta(minutes=5)).isoformat(),
                 "parameter": [{"name": "H2S", "value": 10}]}
        self.assertIsNone(ns["_graph_latest_value"]({"graph2": [{"airpointer_data": [latest, older]}]}, "graph2", "H2S"))

    def test_condition_is_never_inferred_from_aqi(self):
        tree = ast.parse((ROOT / "weather.py").read_text())
        condition = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "condition")
        condition.decorator_list = []
        ns = {}
        exec(compile(ast.Module(body=[condition], type_ignores=[]), "weather.py", "exec"), ns)
        self.assertIsNone(ns["condition"](object()))


class EndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_restore_total_but_not_downtime_cursor(self):
        now = datetime.now(timezone.utc)
        ns = sensor_namespace(now)
        registrations = []
        def track(hass, action, *, hour, minute, second):
            registrations.append((hour, minute, second))
            return lambda: None
        ns["async_track_utc_time_change"] = track
        coordinator = types.SimpleNamespace(data={}, last_update_success=True)
        sensor = ns["KaustWeatherDerivedRainSensor"]("entry", coordinator, "rain_today", "Rain Today", "daily")
        sensor.hass = object()
        sensor.async_get_last_state = AsyncMock(return_value=types.SimpleNamespace(
            state="12.5", attributes={"last_period_marker": rain.period_marker(now, "daily"),
                                      "last_calc_utc": (now - timedelta(hours=6)).isoformat()}))
        await sensor.async_added_to_hass()
        self.assertEqual(sensor.native_value, 12.5)
        self.assertIsNone(sensor._last_calc_utc)
        self.assertIsNone(sensor._previous_rate)
        self.assertEqual(registrations, [(21, 0, 0)])

    async def test_partial_and_total_failure(self):
        class UpdateFailed(Exception):
            pass
        ns = {"Any": object, "HomeAssistant": object, "DataUpdateCoordinator": Entity,
              "asyncio": asyncio, "UpdateFailed": UpdateFailed, "_LOGGER": logging.getLogger("test"),
              "LIVE_URL": "live", "GRAPH2_URL": "graph2", "GRAPH3_URL": "graph3"}
        load_definitions("coordinator.py", ns)
        coordinator = object.__new__(ns["KaustWeatherCoordinator"])
        coordinator._fetch_json = AsyncMock(side_effect=[{"aqi": {}}, TimeoutError(), []])
        result = await coordinator._async_update_data()
        self.assertEqual(result["live"], {"aqi": {}})
        self.assertEqual(result["graph2"], [])
        self.assertIn("graph2", result["endpoint_errors"])
        coordinator._fetch_json = AsyncMock(side_effect=TimeoutError())
        with self.assertRaises(UpdateFailed):
            await coordinator._async_update_data()
