"""Weather module - displays current weather from OpenWeatherMap."""

import time
from typing import Any

import httpx

from app.modules.base import Module


class WeatherModule(Module):
    name = "weather"
    display_name = "Weather"
    description = "Current weather conditions via OpenWeatherMap"
    icon = "&#9925;"
    widget_template = "widgets/weather.html"
    widget_size = "medium"
    refresh_interval = 300  # 5 minutes

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.city = config.get("city", "London")
        self.units = config.get("units", "metric")
        self.refresh_minutes = config.get("refresh_minutes", 15)
        self._cache: dict[str, Any] | None = None
        self._cache_time: float = 0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a reusable httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def get_data(self) -> dict[str, Any]:
        # Return demo data if no API key configured
        if not self.api_key:
            return {
                "city": self.city,
                "temperature": 18.5,
                "feels_like": 17.2,
                "description": "Partly cloudy",
                "humidity": 65,
                "wind_speed": 12.3,
                "icon": "02d",
                "units": self.units,
                "demo": True,
                "message": "Configure an API key in settings to see live weather",
            }

        # Check cache
        now = time.time()
        if self._cache and (now - self._cache_time) < (self.refresh_minutes * 60):
            return self._cache

        # Fetch from OpenWeatherMap
        try:
            client = await self._get_client()
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "q": self.city,
                    "appid": self.api_key,
                    "units": self.units,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            result = {
                "city": data.get("name", self.city),
                "temperature": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "description": data["weather"][0]["description"].capitalize(),
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
                "icon": data["weather"][0]["icon"],
                "units": self.units,
                "demo": False,
            }

            self._cache = result
            self._cache_time = now
            return result

        except Exception as e:
            # Return cached data if available, otherwise error
            if self._cache:
                return self._cache
            return {
                "error": True,
                "error_message": f"Weather API error: {e}",
            }

    def get_config_schema(self) -> dict[str, dict]:
        return {
            "api_key": {
                "type": "text",
                "label": "OpenWeatherMap API Key",
                "required": True,
                "placeholder": "Your API key",
            },
            "city": {
                "type": "text",
                "label": "City",
                "required": True,
                "placeholder": "e.g. London, New York",
            },
            "units": {
                "type": "select",
                "label": "Units",
                "options": ["metric", "imperial"],
            },
        }
