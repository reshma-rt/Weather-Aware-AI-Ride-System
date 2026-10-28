
"""Current-location context for MOVIO customer care."""

import math
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

VERSION = "customer-care-context-0.1"
TZ = ZoneInfo("Asia/Kolkata")

def valid_coordinates(lat, lng):
    if isinstance(lat, bool) or isinstance(lng, bool):
        raise ValueError("Invalid coordinates")
    lat, lng = float(lat), float(lng)
    if not (
        math.isfinite(lat) and math.isfinite(lng)
        and -90 <= lat <= 90
        and -180 <= lng <= 180
    ):
        raise ValueError("Invalid coordinates")
    return lat, lng

def current_weather(lat, lng, getter=None):
    lat, lng = valid_coordinates(lat, lng)
    getter = getter or requests.get

    try:
        response = getter(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lng,
                "current": (
                    "temperature_2m,apparent_temperature,"
                    "weather_code,precipitation"
                ),
                "hourly": "precipitation_probability",
                "forecast_days": 1,
                "timezone": "Asia/Kolkata",
            },
            timeout=(3, 6),
        )
        response.raise_for_status()
        payload = response.json()

        current = payload.get("current")
        hourly = payload.get("hourly")

        if not isinstance(current, dict):
            raise ValueError("Missing current weather")

        def number(value, low, high):
            if isinstance(value, bool):
                return None
            try:
                value = float(value)
            except (TypeError, ValueError):
                return None
            return value if math.isfinite(value) and low <= value <= high else None

        code = number(current.get("weather_code"), 0, 99)
        temp = number(current.get("temperature_2m"), -90, 65)
        feels = number(current.get("apparent_temperature"), -100, 80)

        if code is None or not code.is_integer() or temp is None:
            raise ValueError("Incomplete current weather")

        probability = None
        observed_time = current.get("time")

        if isinstance(hourly, dict) and isinstance(observed_time, str):
            times = hourly.get("time")
            probabilities = hourly.get("precipitation_probability")

            if isinstance(times, list) and isinstance(probabilities, list):
                try:
                    observation = datetime.fromisoformat(observed_time)
                    candidates = []
                    for i, value in enumerate(times):
                        if not isinstance(value, str) or i >= len(probabilities):
                            continue
                        forecast_time = datetime.fromisoformat(value)
                        delta = (forecast_time - observation).total_seconds()
                        if 0 <= delta <= 7200:
                            candidates.append((delta, i))
                    if candidates:
                        _, index = min(candidates)
                        probability = number(probabilities[index], 0, 100)
                except (ValueError, TypeError, OverflowError):
                    probability = None

        return {
            "status": "ok",
            "source": "Open-Meteo",
            "weather_code": int(code),
            "temperature_2m": temp,
            "apparent_temperature": feels,
            "precipitation_probability": probability,
            "observed_at": observed_time,
            "fetched_at": time.time(),
        }

    except (requests.RequestException, ValueError, TypeError, KeyError):
        return {
            "status": "unavailable",
            "source": "Open-Meteo",
        }

def dashboard_context(lat, lng, reverse_address, getter=None):
    lat, lng = valid_coordinates(lat, lng)

    locality = None
    try:
        result = reverse_address(lat, lng)
        if isinstance(result, dict):
            locality = (
                result.get("locality")
                or result.get("area")
                or result.get("name")
            )
        elif isinstance(result, (tuple, list)) and result:
            locality = result[0]
        elif isinstance(result, str):
            locality = result

        if not isinstance(locality, str) or not locality.strip():
            locality = None
    except Exception:
        locality = None

    return {
        "locality": locality,
        "weather": current_weather(lat, lng, getter=getter),
        "time_of_day": datetime.now(TZ).hour,
    }
