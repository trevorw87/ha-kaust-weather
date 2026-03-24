DOMAIN = "kaust_weather"

LIVE_URL = "https://kaustweather.kaust.edu.sa/api/aqi/LiveData"
GRAPH2_URL = "https://kaustweather.kaust.edu.sa/api/aqi/Graph2Data"
GRAPH3_URL = "https://kaustweather.kaust.edu.sa/api/aqi/Graph3Data"

PLATFORMS = ["sensor", "weather"]

DEFAULT_SCAN_INTERVAL = 600  # seconds (10 minutes)

ATTRIBUTION = "Data provided by KAUST Weather"

METEO_IDS = {
    "wind_direction": 1,
    "wind_speed": 2,
    "temperature": 3,
    "humidity": 5,
    "solar_radiation": 6,
    "precipitation": 7,
}