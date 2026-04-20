"""
Tool: get_weather
Fetches current weather for a given city using OpenWeatherMap free API.
Sign up at https://openweathermap.org/api to get a free API key,
then set it as environment variable: WEATHER_API_KEY=your_key_here
Optional: set RESTAURANT_CITY to your restaurant's city (default: London)
"""

import os
import logging
import httpx

logger = logging.getLogger("tool.weather")

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "d3707d1fc4f7ece5d1d2dd407a2d4c00")
RESTAURANT_CITY = os.getenv("RESTAURANT_CITY", "Italy")
BASE_URL        = "https://api.openweathermap.org/data/2.5/weather"

# Tool schema — for documentation and LLM awareness
TOOL_SCHEMA = {
    "name":        "get_weather",
    "description": "Fetch current weather for a city. Use when customer asks about weather or outdoor seating conditions.",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name, e.g. 'London'"}
        },
        "required": ["city"]
    }
}


def get_weather(city: str = RESTAURANT_CITY) -> dict:
    """
    Returns current weather for *city*.
    Always returns a dict with 'status': 'ok' or 'status': 'error'.
    """
    if not WEATHER_API_KEY:
        logger.warning("[WEATHER] WEATHER_API_KEY not set — tool disabled.")
        return {
            "status":  "error",
            "message": "Weather service is not configured. Please ask the staff about outdoor seating."
        }

    try:
        resp = httpx.get(
            BASE_URL,
            params={"q": city, "appid": WEATHER_API_KEY, "units": "metric"},
            timeout=4.0
        )
        resp.raise_for_status()
        data = resp.json()

        weather_id  = data["weather"][0]["id"]
        description = data["weather"][0]["description"]

        # OpenWeatherMap: 800 = clear sky, 8xx = clouds, <800 = precipitation/storm
        outdoor_ok = weather_id >= 800

        return {
            "status":           "ok",
            "city":             data["name"],
            "temperature_c":    round(data["main"]["temp"], 1),
            "feels_like_c":     round(data["main"]["feels_like"], 1),
            "description":      description,
            "humidity_pct":     data["main"]["humidity"],
            "outdoor_suitable": outdoor_ok,
            "outdoor_note": (
                "Outdoor seating looks great today!"
                if outdoor_ok
                else "We recommend indoor seating given the current weather."
            )
        }

    except httpx.TimeoutException:
        logger.error("[WEATHER] Request timed out.")
        return {"status": "error", "message": "Weather service timed out. Please try again."}

    except httpx.HTTPStatusError as e:
        logger.error(f"[WEATHER] HTTP {e.response.status_code}")
        return {"status": "error", "message": f"Weather service unavailable (HTTP {e.response.status_code})."}

    except Exception as e:
        logger.error(f"[WEATHER] Unexpected error: {e}")
        return {"status": "error", "message": "Could not fetch weather information."}