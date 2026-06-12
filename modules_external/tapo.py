"""TP-Link Tapo module - monitor and control Tapo smart home devices."""

import asyncio
import logging
from typing import Any

from PyP100.PyP100 import P100

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.modules.base import Module

logger = logging.getLogger(__name__)


class TapoModule(Module):
    name = "tapo"
    display_name = "TP-Link Tapo"
    description = "Monitor and control TP-Link Tapo smart devices"
    icon = "&#128268;"
    widget_template = "widgets/tapo.html"
    widget_size = "medium"
    refresh_interval = 30

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.email = config.get("email", "")
        self.password = config.get("password", "")
        self.devices_config = config.get("devices", [])
        self._device_instances: dict[str, Any] = {}

    async def _initialize_device(self, device: dict) -> Any:
        """Initialize a PyP100 device instance."""
        ip = device.get("ip", "")
        device_id = device.get("id", ip)

        if device_id in self._device_instances:
            return self._device_instances[device_id]

        try:
            p100 = P100(
                ip,
                self.email,
                self.password,
            )
            await asyncio.to_thread(p100.handshake)
            self._device_instances[device_id] = p100
            return p100
        except Exception as e:
            logger.error(f"Failed to initialize device {ip}: {e}")
            return None

    async def _get_device_status(self, device: dict) -> dict:
        """Get the status of a Tapo device."""
        ip = device.get("ip", "")
        name = device.get("name", ip)
        device_id = device.get("id", ip)

        if not self.email or not self.password:
            # Fallback to simple reachability check
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, 80),
                    timeout=2.0,
                )
                writer.close()
                await writer.wait_closed()
                return {
                    "name": name,
                    "ip": ip,
                    "reachable": True,
                    "on": None,
                    "type": device.get("type", "plug"),
                    "authenticated": False,
                }
            except Exception:
                return {
                    "name": name,
                    "ip": ip,
                    "reachable": False,
                    "on": None,
                    "type": device.get("type", "plug"),
                    "authenticated": False,
                }

        try:
            p100 = await self._initialize_device(device)
            if not p100:
                return {
                    "name": name,
                    "ip": ip,
                    "reachable": False,
                    "on": None,
                    "type": device.get("type", "plug"),
                    "authenticated": True,
                    "error": "Failed to initialize device",
                }

            # Get device info
            device_info = await asyncio.to_thread(p100.getDeviceInfo)
            device_state = await asyncio.to_thread(p100.getDeviceState)

            device_type = device_info.get("device_type", device.get("type", "plug"))
            power_on = device_state.get("device_on", None)

            result = {
                "name": name,
                "ip": ip,
                "reachable": True,
                "on": power_on,
                "type": device_type,
                "authenticated": True,
            }

            # Add type-specific data
            if "brightness" in device_state:
                result["brightness"] = device_state["brightness"]
            if "color_temp" in device_state:
                result["color_temp"] = device_state["color_temp"]
            if "current" in device_info:
                result["current_ma"] = device_info["current"]
            if "power" in device_info:
                result["power_w"] = device_info["power"]

            return result
        except Exception as e:
            logger.error(f"Error getting status for device {ip}: {e}")
            return {
                "name": name,
                "ip": ip,
                "reachable": False,
                "on": None,
                "type": device.get("type", "plug"),
                "authenticated": True,
                "error": str(e),
            }

    async def get_data(self) -> dict[str, Any]:
        if not self.devices_config:
            return {
                "devices": [
                    {
                        "name": "Living Room Plug",
                        "ip": "192.168.1.50",
                        "reachable": False,
                        "on": True,
                        "type": "plug",
                        "authenticated": False,
                    },
                    {
                        "name": "Desk Lamp",
                        "ip": "192.168.1.51",
                        "reachable": False,
                        "on": False,
                        "type": "bulb",
                        "authenticated": False,
                    },
                ],
                "authenticated": False,
                "message": "No devices configured - showing demo data",
            }

        # Get status of all configured devices
        tasks = [self._get_device_status(d) for d in self.devices_config]
        devices = await asyncio.gather(*tasks)

        authenticated = bool(self.email and self.password)

        return {
            "devices": devices,
            "authenticated": authenticated,
            "device_count": len(devices),
            "online_count": sum(1 for d in devices if d.get("reachable", False)),
            "message": None
            if authenticated
            else "Credentials not configured - limited to reachability checks",
        }

    async def _set_device_power(self, device_name: str, on: bool) -> dict:
        """Turn a named device on or off. Returns status dict."""
        device = next(
            (d for d in self.devices_config if d.get("name") == device_name),
            None,
        )
        if device is None:
            return {"error": f"Device '{device_name}' not found"}

        if not self.email or not self.password:
            return {"error": "Tapo credentials not configured"}

        try:
            p100 = await self._initialize_device(device)
            if p100 is None:
                return {"error": f"Could not connect to device '{device_name}'"}
            if on:
                await asyncio.to_thread(p100.turnOn)
            else:
                await asyncio.to_thread(p100.turnOff)
            return {"device": device_name, "on": on, "status": "ok"}
        except Exception as e:
            logger.error("Tapo control error for '%s': %s", device_name, e)
            return {"error": str(e)}

    def get_routes(self) -> APIRouter | None:
        router = APIRouter()
        module_ref = self

        @router.post("/devices/{device_name}/on")
        async def turn_on(device_name: str):
            """Turn a Tapo device on."""
            result = await module_ref._set_device_power(device_name, on=True)
            if "error" in result:
                return JSONResponse(result, status_code=400)
            return result

        @router.post("/devices/{device_name}/off")
        async def turn_off(device_name: str):
            """Turn a Tapo device off."""
            result = await module_ref._set_device_power(device_name, on=False)
            if "error" in result:
                return JSONResponse(result, status_code=400)
            return result

        return router

    def get_config_schema(self) -> dict[str, dict]:
        return {
            "email": {
                "type": "string",
                "label": "TP-Link account email",
                "placeholder": "your@email.com",
            },
            "password": {
                "type": "password",
                "label": "TP-Link account password",
            },
        }

