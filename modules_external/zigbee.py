"""Zigbee module - discovers and monitors Zigbee devices via a coordinator."""

import asyncio
import logging
from typing import Any

import zigpy.device
import zigpy.group
import zigpy.serial
import zigpy.types
from zigpy.application import ControllerApplication

from app.modules.base import Module

logger = logging.getLogger(__name__)


class ZigbeeModule(Module):
    name = "zigbee"
    display_name = "Zigbee"
    description = "Monitor and control Zigbee smart home devices"
    icon = "&#128161;"
    widget_template = "widgets/zigbee.html"
    widget_size = "medium"
    refresh_interval = 30

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.coordinator_port = config.get("coordinator_port", "")
        self.coordinator_type = config.get("coordinator_type", "cc2531")
        self.channel = config.get("channel", 15)
        self.permit_join = config.get("permit_join", False)
        self._devices: list[dict] = []
        self._app: ControllerApplication | None = None
        self._connected = False

    async def _connect_coordinator(self) -> bool:
        """Connect to the Zigbee coordinator."""
        if not self.coordinator_port or self._connected:
            return self._connected

        try:
            # Map coordinator types to zigpy radio types
            radio_type_map = {
                "cc2531": "zigpy_cc.types.RadioType.CC2531",
                "conbee": "zigpy_deconz.types.RadioType.ConBee",
                "xbee": "zigpy_xbee.types.RadioType.XBEE_S2",
                "sonoff": "zigpy_zigate.types.RadioType.SONOFF",
            }

            # Import appropriate coordinator driver
            try:
                if self.coordinator_type == "cc2531":
                    try:
                        from zigpy_cc import zigpy_cc
                        self._app = await zigpy_cc.connect(
                            {
                                "port": self.coordinator_port,
                                "baudrate": 115200,
                            }
                        )
                    except (ImportError, AttributeError):
                        # Fallback for older zigpy-cc versions
                        logger.warning("zigpy-cc connect method not available, using basic initialization")
                        self._app = None
                        self._connected = False
                        return False

                elif self.coordinator_type == "conbee":
                    try:
                        from zigpy_deconz import zigpy_deconz
                        self._app = await zigpy_deconz.connect(
                            {
                                "device": {"path": self.coordinator_port},
                            }
                        )
                    except (ImportError, AttributeError):
                        logger.warning("zigpy-deconz connect method not available")
                        self._app = None
                        self._connected = False
                        return False

                elif self.coordinator_type == "xbee":
                    try:
                        from zigpy_xbee import zigpy_xbee
                        self._app = await zigpy_xbee.connect(
                            {
                                "port": self.coordinator_port,
                            }
                        )
                    except (ImportError, AttributeError):
                        logger.warning("zigpy-xbee connect method not available")
                        self._app = None
                        self._connected = False
                        return False
                else:
                    logger.warning(f"Unknown coordinator type: {self.coordinator_type}")
                    return False

                if self._app:
                    self._connected = True
                    logger.info(f"Connected to Zigbee coordinator on {self.coordinator_port}")
                    return True
                return False

            except (ImportError, ModuleNotFoundError) as e:
                logger.error(f"Coordinator driver not installed: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to Zigbee coordinator: {e}")
            return False

    async def _get_devices(self) -> list[dict]:
        """Get list of Zigbee devices."""
        if not self._app or not self._connected:
            return []

        try:
            devices = []
            for device in self._app.devices.values():
                device_dict = {
                    "name": device.name or f"Device {device.ieee}",
                    "ieee": str(device.ieee),
                    "nwk": device.nwk,
                    "type": device.device_type.name if hasattr(device, "device_type") else "unknown",
                    "online": device.status == zigpy.device.Status.ZDO_INIT,
                    "battery_level": None,
                    "last_seen": device.last_seen if hasattr(device, "last_seen") else None,
                }

                # Try to get battery level from device
                if hasattr(device, "endpoints") and 1 in device.endpoints:
                    endpoint = device.endpoints[1]
                    if hasattr(endpoint, "power"):
                        battery_cluster = endpoint.power
                        if hasattr(battery_cluster, "battery_percentage_remaining"):
                            device_dict["battery_level"] = getattr(battery_cluster, "battery_percentage_remaining", None)

                devices.append(device_dict)

            self._devices = devices
            return devices
        except Exception as e:
            logger.error(f"Failed to get Zigbee devices: {e}")
            return []

    async def get_data(self) -> dict[str, Any]:
        if not self.coordinator_port:
            return {
                "devices": [
                    {
                        "name": "Demo Bulb",
                        "ieee": "00:11:22:33:44:55:66:01",
                        "type": "light",
                        "online": True,
                        "battery": None,
                    },
                    {
                        "name": "Motion Sensor",
                        "ieee": "00:11:22:33:44:55:66:02",
                        "type": "sensor",
                        "online": True,
                        "battery": 87,
                    },
                    {
                        "name": "Door Contact",
                        "ieee": "00:11:22:33:44:55:66:03",
                        "type": "sensor",
                        "online": False,
                        "battery": 12,
                    },
                ],
                "coordinator": {
                    "connected": False,
                    "port": "Not configured",
                    "channel": self.channel,
                },
                "permit_join": self.permit_join,
                "message": "No coordinator configured - showing demo data",
            }

        # Attempt to connect if not connected
        if not self._connected:
            await self._connect_coordinator()

        # Get devices
        devices = await self._get_devices()

        return {
            "devices": devices,
            "coordinator": {
                "connected": self._connected,
                "port": self.coordinator_port,
                "channel": self.channel,
                "type": self.coordinator_type,
            },
            "permit_join": self.permit_join,
            "device_count": len(devices),
            "online_count": sum(1 for d in devices if d.get("online", False)),
            "message": None if self._connected else "Coordinator not reachable - check connection",
        }

    def get_config_schema(self) -> dict[str, dict]:
        return {
            "coordinator_port": {
                "type": "string",
                "label": "Coordinator serial port",
                "placeholder": "e.g /dev/ttyUSB0 or COM3",
            },
            "coordinator_type": {
                "type": "select",
                "label": "Coordinator type",
                "options": {
                    "cc2531": "CC2531",
                    "conbee": "ConBee II",
                    "xbee": "XBee",
                    "sonoff": "SONOFF ZBDongle",
                },
                "default": "cc2531",
            },
            "channel": {
                "type": "number",
                "label": "Zigbee channel (11-26)",
                "default": 15,
                "min": 11,
                "max": 26,
            },
            "permit_join": {
                "type": "boolean",
                "label": "Allow new devices to join",
                "default": False,
            },
        }
