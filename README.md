# KAUST Weather (Home Assistant Integration)

Custom Home Assistant integration for real-time weather and air quality data from the KAUST Weather station.

Provides:
- live meteorological data (temperature, wind, humidity, solar, precipitation)
- air quality index (AQI) and pollutant breakdown
- derived rainfall totals (daily, monthly, accumulated)
- Home Assistant weather entity

---

## Features

### Weather data
- Temperature (Â°C)
- Humidity (%)
- Wind speed (m/s)
- Wind direction (Â° + compass)
- Solar radiation (W/mÂ²)
- Precipitation rate (mm/h)

### Air quality
- AQI (station index)
- AQI status (Good â†’ Hazardous)
- Pollutant indices:
  - O3, CO, SO2, NO2
  - PM2.5, PM10
- Raw pollutant values (ppb / ppm / Âµg/mÂ³)

### Rainfall (derived â€” no setup required)
- Rain accumulated (mm)
- Rain today (mm)
- Rain this month (mm)

These are calculated internally from precipitation rate â€” no helpers, templates, or YAML required.

---

## Installation

### HACS (Custom Repository)

1. Open HACS
2. Go to **Integrations**
3. Click the top-right menu, then **Custom repositories**
4. Add this repository URL:
   `https://github.com/trevorw87/ha-kaust-weather`
5. Select **Integration** as the category
6. Install **KAUST Weather**
7. Restart Home Assistant

### Manual

Copy:

`custom_components/kaust_weather/`

into your Home Assistant config folder under:

`<config>/custom_components/`

Then restart Home Assistant.

---

## Configuration

1. Go to **Settings â†’ Devices & Services**
2. Click **Add Integration**
3. Search for **KAUST Weather**
4. Add it

No configuration is currently required.

---

## Entities

### Core sensors

| Entity | Description |
|------|--------|
| Temperature | Air temperature |
| Humidity | Relative humidity |
| Wind Speed | Wind speed |
| Wind Direction | Degrees |
| Wind Compass | N / NE / etc |
| Solar Radiation | W/mÂ² |
| Precipitation | Rain rate (mm/h) |

### AQI

| Entity | Description |
|------|--------|
| AQI | Station AQI |
| AQI Status | Text label |
| O3 / CO / SO2 / NO2 indices | Pollutant AQI |
| PM2.5 / PM10 indices | Particulate AQI |

### Pollutants

| Entity | Unit |
|------|------|
| NO, NO2, SO2, O3, H2S | ppb |
| CO | ppm |
| PM10, PM2.5 | Âµg/mÂ³ |

### Rain (derived)

| Entity | Description |
|------|--------|
| Rain Accumulated | Lifetime accumulation |
| Rain Today | Daily total |
| Rain Month | Monthly total |

---

## Weather Entity

Provides a Home Assistant weather entity with:
- Temperature
- Humidity
- Wind speed / bearing
- Observation timestamps and air-quality context

The station does not provide sky conditions. The weather condition is therefore unknown; temperature, humidity and wind remain available. AQI is reported separately and never translated into sunny/cloudy/foggy conditions.

---

## Update Interval

Default polling interval: 10 minutes.

---

## Data Source

https://kaustweather.kaust.edu.sa/

---

## Attribution

Data provided by KAUST Weather.

---

## Limitations

- Rain totals are estimates from sampled intensity, not measured station accumulations.
- Gaps longer than 30 minutes, unavailable readings, and restart gaps are excluded rather than filled. Missed rainfall cannot be recovered.
- Daily and monthly totals reset at midnight in Asia/Riyadh, independent of Home Assistant timezone.

- Sky condition is unknown because the station does not supply it.

---

## Roadmap

Potential future improvements:
- configurable scan interval
- forecast support, if the API allows it
- improved weather condition mapping
- historical rainfall recovery if an authoritative accumulation endpoint becomes available

---

## Contributing

Pull requests and suggestions are welcome.

---

## License

MIT

---

## Support

If you encounter issues, please open an issue here:

https://github.com/trevorw87/ha-kaust-weather/issues

Include logs and relevant entity states where possible.

---

## Version

Current version: 0.3.0

## 0.3.0 changes and data definitions

Existing entity unique IDs are preserved. Previously accumulated rain totals are
retained when their Saudi calendar period still matches; historical errors are
not corrected retroactively. The first observation after startup establishes a
new baseline and does not estimate rain during downtime. Each newer observation
integrates the previous valid rate across at most 30 minutes. Daily/monthly
intervals crossing midnight are clipped to the new Saudi calendar period.
`estimated`, `reset_timezone`, and `last_reset` describe this behavior.

AQI status uses the six standard categories: Good (0–50), Moderate (51–100),
Unhealthy for Sensitive Groups (101–150), Unhealthy (151–200), Very Unhealthy
(201–300), and Hazardous (301+). AQI and its sub-indices remain station-provided;
they are not recomputed from concentration samples. AQI sensors expose
observation time, freshness, dominant pollutant(s), and a link to KAUST guidance.
Pollutant sub-indices include the documented averaging period.

KAUST documents three-hour weighted particulate nearcasting, one-hour NO2/SO2,
and eight-hour O3/CO averaging. Exact correspondence between additional API
“Short”/“Shorter Average” fields and the main indices remains unverified; no new
sensors are created for them. CO remains ppm pending clarification of conflicting
API header/sample unit metadata. H2S missing sentinel values remain unknown,
never zero. Missing flags, non-finite numbers and -9999 sentinels are rejected.

API times without an offset are interpreted as Asia/Riyadh station time.
Observations older than 45 minutes (three documented 15-minute update cycles),
or more than five minutes in the future, are treated as unknown. This freshness
policy is an integration choice, not a KAUST guarantee. Endpoints are fetched
independently; a failed endpoint's readings become unknown while other endpoints
continue updating. Total endpoint failure makes coordinator entities unavailable.

Definitions and references:
- https://hse.kaust.edu.sa/environment/weathers/air-quality-index
- https://hse.kaust.edu.sa/environment/weathers/weather-monitoring-equipment
- https://www.airnow.gov/aqi/aqi-basics/

## Development checks

Run `python -m unittest discover -s tests -v` and
`python -m compileall -q custom_components`. Tests cover observation parsing,
AQI boundaries, missing data, Saudi calendar boundaries, and rainfall intervals.
These dependency-free tests do not replace an installed Home Assistant smoke test.
