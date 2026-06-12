"""Bluetooth module - discovers nearby Bluetooth devices."""

import logging
import time
from typing import Any

from bleak import BleakScanner

from app.modules.base import Module

logger = logging.getLogger(__name__)


class BluetoothModule(Module):
    name = "bluetooth"
    display_name = "Bluetooth"
    description = "Discover and monitor nearby Bluetooth devices"
    icon = "&#128246;"
    widget_template = "widgets/bluetooth.html"
    widget_size = "medium"
    refresh_interval = 30

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.scan_duration = config.get("scan_duration", 10)
        self.auto_scan = config.get("auto_scan", False)
        self._last_scan_results: list[dict] = []
        self._last_scan_time: float = 0
        self._scanning = False

    async def _scan_ble_devices(self) -> list[dict]:
        """Scan for BLE devices using bleak."""
        if self._scanning:
            return self._last_scan_results

        try:
            self._scanning = True
            devices = await BleakScanner.discover(timeout=self.scan_duration)

            self._last_scan_results = [
                {
                    "name": device.name or "Unknown",
                    "address": device.address,
                    "rssi": device.rssi,
                    "tx_power": getattr(device, "tx_power", None),
                }
                for device in devices
            ]
            self._last_scan_time = time.monotonic()
            return self._last_scan_results
        except Exception as e:
            logger.error(f"Error scanning for BLE devices: {e}")
            return self._last_scan_results
        finally:
            self._scanning = False

    async def get_data(self) -> dict[str, Any]:
        # Use cached results if scan is still fresh (within refresh_interval)
        cache_age = time.monotonic() - self._last_scan_time
        if self._last_scan_results and cache_age < self.refresh_interval:
            devices = self._last_scan_results
        elif self.auto_scan:
            devices = await self._scan_ble_devices()
        else:
            devices = self._last_scan_results

        return {
            "available": True,
            "devices": devices,
            "last_scan": self._last_scan_time if self._last_scan_time else None,
            "scanning": self._scanning,
            "device_count": len(devices),
            "scan_duration": self.scan_duration,
        }

    def get_config_schema(self) -> dict[str, dict]:
        return {
            "scan_duration": {
                "type": "number",
                "label": "Scan duration (seconds)",
                "default": 10,
                "min": 1,
                "max": 60,
            },
            "auto_scan": {
                "type": "boolean",
                "label": "Auto-scan on refresh",
                "default": False,
            },
        }
