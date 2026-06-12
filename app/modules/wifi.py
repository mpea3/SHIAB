"""WiFi/IP module - monitors network devices by IP address."""

import asyncio
import socket
import time
from typing import Any

from app.modules.base import Module


class WiFiModule(Module):
    name = "wifi"
    display_name = "Network Devices"
    description = "Monitor IP devices on your network"
    icon = "&#128225;"
    widget_template = "widgets/wifi.html"
    widget_size = "medium"
    refresh_interval = 60

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.devices_config = config.get("devices", [])
        self.check_interval = config.get("check_interval", 60)

    async def _check_device(self, device: dict) -> dict:
        """Check if a device is reachable via TCP connection and measure latency."""
        ip = device.get("ip", "")
        port = device.get("port", 80)
        name = device.get("name", ip)

        try:
            start = time.monotonic()
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=2.0,
            )
            latency_ms = round((time.monotonic() - start) * 1000)
            writer.close()
            await writer.wait_closed()
            return {
                "name": name,
                "ip": ip,
                "port": port,
                "online": True,
                "latency_ms": latency_ms,
            }
        except Exception:
            return {
                "name": name,
                "ip": ip,
                "port": port,
                "online": False,
                "latency_ms": None,
            }

    async def get_data(self) -> dict[str, Any]:
        # If no devices configured, show demo data
        if not self.devices_config:
            devices = [
                {"name": "Example Camera", "ip": "192.168.1.100", "port": 80, "online": False, "latency_ms": None},
            ]
            message = "No devices configured - add devices in config.yaml"
        else:
            # Check all devices concurrently
            tasks = [self._check_device(d) for d in self.devices_config]
            devices = await asyncio.gather(*tasks)
            message = None

        # Get local network info
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            hostname = "unknown"
            local_ip = "unknown"

        return {
            "devices": devices,
            "network_info": {
                "hostname": hostname,
                "local_ip": local_ip,
            },
            "message": message,
        }

    def get_config_schema(self) -> dict[str, dict]:
        return {
            "check_interval": {
                "type": "number",
                "label": "Check interval (seconds)",
            },
        }
