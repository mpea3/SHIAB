"""Time/Date module - displays current time and date with timezone support."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.modules.base import Module


class TimeDateModule(Module):
    name = "timedate"
    display_name = "Time & Date"
    description = "Displays current time and date with timezone support"
    icon = "&#128339;"
    widget_template = "widgets/timedate.html"
    widget_size = "small"
    refresh_interval = 60  # Client-side JS handles per-second updates

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.timezone = config.get("timezone", "UTC")
        self.format_24h = config.get("format_24h", True)

    async def get_data(self) -> dict[str, Any]:
        try:
            tz = ZoneInfo(self.timezone)
        except Exception:
            tz = ZoneInfo("UTC")

        now = datetime.now(tz)

        if self.format_24h:
            time_str = now.strftime("%H:%M:%S")
        else:
            time_str = now.strftime("%I:%M:%S %p")

        date_str = f"{now.strftime('%A')}, {now.day} {now.strftime('%B %Y')}"

        return {
            "time": time_str,
            "date": date_str,
            "timezone": self.timezone,
            "format_24h": self.format_24h,
            "timestamp": int(now.timestamp()),
        }

    def get_config_schema(self) -> dict[str, dict]:
        return {
            "timezone": {
                "type": "text",
                "label": "Timezone",
                "required": True,
                "placeholder": "e.g. Europe/London, US/Eastern",
            },
            "format_24h": {
                "type": "boolean",
                "label": "24-hour format",
            },
        }
