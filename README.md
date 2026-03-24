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
- Temperature (°C)
- Humidity (%)
- Wind speed (m/s)
- Wind direction (° + compass)
- Solar radiation (W/m²)
- Precipitation rate (mm/h)

### Air quality
- AQI (station index)
- AQI status (Good → Hazardous)
- Pollutant indices:
  - O3, CO, SO2, NO2
  - PM2.5, PM10
- Raw pollutant values (ppb / ppm / µg/m³)

### Rainfall (derived — no setup required)
- Rain accumulated (mm)
- Rain today (mm)
- Rain this month (mm)

These are calculated internally from precipitation rate — no helpers, templates, or YAML required.

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

1. Go to **Settings → Devices & Services**
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
| Solar Radiation | W/m² |
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
| PM10, PM2.5 | µg/m³ |

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
- AQI-based condition mapping

Note: the weather condition is derived from AQI status, not traditional meteorological conditions.

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

- Rain totals are calculated from rate data. Small inaccuracies may occur during:
  - Home Assistant downtime
  - restart near midnight or month boundary

- Weather condition is AQI-based, not cloud/precipitation based.

---

## Roadmap

Potential future improvements:
- configurable scan interval
- forecast support, if the API allows it
- improved weather condition mapping
- historical rainfall smoothing

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

Current version: 0.2.0
