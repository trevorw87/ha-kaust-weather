"""Dependency-free tests of station parsing and rainfall arithmetic."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "kaust_weather"
package = types.ModuleType("kaust_test")
package.__path__ = [str(ROOT)]
sys.modules["kaust_test"] = package
for name in ("data", "rain"):
    spec = importlib.util.spec_from_file_location(f"kaust_test.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from kaust_test import data, rain


class ObservationTests(unittest.TestCase):
    def test_invalid_numbers(self):
        for value in (None, "", "None", -9999, "-9999", "nan", "inf", True):
            with self.subTest(value=value):
                self.assertIsNone(data.number(value))
        self.assertEqual(data.number("0.02"), 0.02)
        self.assertEqual(data.number(0), 0)

    def test_station_timezone(self):
        self.assertEqual(data.timestamp("2026-10-16T00:00:00").astimezone(timezone.utc),
                         datetime(2026, 10, 15, 21, tzinfo=timezone.utc))
        self.assertIsNone(data.timestamp("invalid"))

    def test_freshness(self):
        now = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
        self.assertTrue(data.fresh("2026-10-16T15:00:00", now))
        self.assertFalse(data.fresh("2026-10-16T14:00:00", now))
        self.assertFalse(data.fresh("2026-10-16T16:00:00", now))
        self.assertFalse(data.fresh(None, now))

    def test_missing_meteorology(self):
        item = {"id": 3, "time_stamp": datetime.now(timezone.utc).isoformat(),
                "value": 32, "missing": 1}
        payload = {"live": {"aqi": {"response": {"meteorology": [item]}}}}
        self.assertIsNone(data.meteorology(payload, 3))
        item["missing"] = 0
        self.assertEqual(data.meteorology(payload, 3), 32)
        item["value"] = "-9999"
        self.assertIsNone(data.meteorology(payload, 3))

    def test_aqi_category_boundaries(self):
        response = {"time_stamp": datetime.now(timezone.utc).isoformat()}
        payload = {"live": {"aqi": {"response": response}}}
        for value, expected in ((0, "Good"), (50, "Good"), (51, "Moderate"),
                                (100, "Moderate"), (101, "Unhealthy for Sensitive Groups"),
                                (150, "Unhealthy for Sensitive Groups"), (151, "Unhealthy"),
                                (200, "Unhealthy"), (201, "Very Unhealthy"),
                                (300, "Very Unhealthy"), (301, "Hazardous")):
            response["station_index"] = value
            self.assertEqual(data.aqi_status(payload), expected)
        response["missing"] = 1
        self.assertIsNone(data.aqi_status(payload))

    def test_dominant_ties_and_invalid_indices(self):
        stamp = datetime.now(timezone.utc).isoformat()
        response = {"time_stamp": stamp, "poll_index": [
            {"shortname": name, "pollutant_index": value, "time_stamp": stamp}
            for name, value in (("PM 2.5", 110), ("PM 10", 110), ("O3", -9999))]}
        attrs = data.observation_attributes({"live": {"aqi": {"response": response}}})
        self.assertEqual(attrs["dominant_pollutants"], ["PM 2.5", "PM 10"])
        self.assertFalse(attrs["data_stale"])


class RainTests(unittest.TestCase):
    def test_saudi_midnight(self):
        before = datetime(2026, 10, 15, 20, 59, tzinfo=timezone.utc)
        self.assertEqual(rain.period_marker(before, "daily"), "2026-10-15")
        self.assertEqual(rain.period_marker(before + timedelta(minutes=1), "daily"), "2026-10-16")

    def test_saudi_month_boundary(self):
        end = data.timestamp("2026-11-01T00:05:00")
        self.assertEqual(rain.period_marker(end, "monthly"), "2026-11")
        self.assertEqual(rain.period_marker(end - timedelta(minutes=10), "monthly"), "2026-10")

    def test_integrate_valid_interval(self):
        end = data.timestamp("2026-10-16T12:15:00")
        self.assertEqual(rain.increment(end - timedelta(minutes=15), end, 4, None), 1)

    def test_do_not_fill_downtime_or_first_sample(self):
        end = data.timestamp("2026-10-16T12:15:00")
        self.assertEqual(rain.increment(None, end, 4, None), 0)
        self.assertEqual(rain.increment(end - timedelta(hours=6), end, 4, None), 0)

    def test_duplicate_backwards_or_missing_sample(self):
        end = data.timestamp("2026-10-16T12:15:00")
        for start, rate in ((end, 4), (end + timedelta(minutes=1), 4),
                            (end - timedelta(minutes=15), None),
                            (end - timedelta(minutes=15), -1)):
            self.assertEqual(rain.increment(start, end, rate, None), 0)

    def test_clip_daily_boundary_keep_lifetime(self):
        start = data.timestamp("2026-10-15T23:55:00")
        end = data.timestamp("2026-10-16T00:10:00")
        self.assertEqual(rain.increment(start, end, 6, "daily"), 1)
        self.assertEqual(rain.increment(start, end, 6, None), 1.5)

    def test_clip_month_boundary(self):
        start = data.timestamp("2026-10-31T23:55:00")
        end = data.timestamp("2026-11-01T00:10:00")
        self.assertEqual(rain.increment(start, end, 6, "monthly"), 1)


if __name__ == "__main__":
    unittest.main()
