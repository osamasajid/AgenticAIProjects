"""Weather MCP server (real external API: Open-Meteo, no key).

Exposes get_weather(location, date) as an MCP tool. Demonstrates a self-contained,
reusable capability behind the MCP protocol — the agent (MCP client) discovers and
calls it without knowing it wraps Open-Meteo.

Run: python -m mcp_servers.weather_server   (stdio transport)
"""
from __future__ import annotations

import datetime as _dt

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather")

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"


@mcp.tool()
def get_weather(location: str, date: str | None = None) -> str:
    """Get the weather forecast for a location on an optional ISO date (YYYY-MM-DD).

    Use this before recommending or scheduling OUTDOOR activities (lawn work,
    picnic, tennis, backyard maintenance) to check if conditions are suitable.
    """
    try:
        with httpx.Client(timeout=15.0) as c:
            g = c.get(GEOCODE, params={"name": location, "count": 1}).json()
            results = g.get("results") or []
            if not results:
                return f"Could not find location '{location}'."
            loc = results[0]
            lat, lon, name = loc["latitude"], loc["longitude"], loc.get("name", location)

            params = {
                "latitude": lat, "longitude": lon,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
            }
            if date:
                params["start_date"] = date
                params["end_date"] = date
            f = c.get(FORECAST, params=params).json()
            daily = f.get("daily", {})
            days = daily.get("time", [])
            if not days:
                return f"No forecast available for {name}."
            i = 0
            tmax = daily["temperature_2m_max"][i]
            tmin = daily["temperature_2m_min"][i]
            precip = daily["precipitation_probability_max"][i]
            code = daily["weather_code"][i]
            desc = _WMO.get(code, f"code {code}")
            outdoor_ok = precip is not None and precip < 40
            verdict = "good for outdoor plans" if outdoor_ok else "not ideal for outdoor plans (rain likely)"
            return (
                f"{name} on {days[i]}: {desc}, {tmin}–{tmax}°C, "
                f"{precip}% chance of precipitation — {verdict}."
            )
    except Exception as e:  # noqa: BLE001
        return f"Weather lookup failed: {e}"


# Minimal WMO weather-code map for readable descriptions.
_WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 61: "light rain",
    63: "rain", 65: "heavy rain", 71: "snow", 80: "rain showers", 95: "thunderstorm",
}


def _today() -> str:
    return _dt.date.today().isoformat()


if __name__ == "__main__":
    mcp.run()
