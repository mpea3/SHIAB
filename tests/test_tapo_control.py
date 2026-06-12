"""Unit tests for Tapo device control (mocked — no real hardware needed)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def _make_tapo(devices=None, email="user@example.com", password="secret"):
    """Build a TapoModule with a fake PyP100 — no network calls."""
    config = {
        "email": email,
        "password": password,
        "devices": devices or [{"name": "MyPlug", "ip": "10.0.0.50", "type": "plug"}],
    }

    # Patch PyP100 import so the module can be imported without the library
    fake_p100 = MagicMock()
    fake_p100.handshake = MagicMock()
    fake_p100.turnOn = MagicMock()
    fake_p100.turnOff = MagicMock()
    fake_p100.getDeviceInfo = MagicMock(return_value={"device_type": "plug"})
    fake_p100.getDeviceState = MagicMock(return_value={"device_on": True})

    with patch.dict("sys.modules", {"PyP100": MagicMock(), "PyP100.PyP100": MagicMock(P100=MagicMock(return_value=fake_p100))}):
        import importlib
        import sys
        # Remove cached module to force reimport with the patch
        for key in list(sys.modules.keys()):
            if "tapo" in key and "test" not in key:
                del sys.modules[key]

        import importlib.util
        from pathlib import Path
        spec = importlib.util.spec_from_file_location(
            "tapo_test_mod",
            str(Path(__file__).parent.parent / "modules_external" / "tapo.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        instance = mod.TapoModule(config)
        instance._device_instances["10.0.0.50"] = fake_p100
        return instance, fake_p100


def test_set_device_power_on_calls_turnOn():
    module, fake_p100 = _make_tapo()
    result = asyncio.run(module._set_device_power("MyPlug", on=True))
    assert result.get("status") == "ok"
    assert result.get("on") is True
    fake_p100.turnOn.assert_called_once()


def test_set_device_power_off_calls_turnOff():
    module, fake_p100 = _make_tapo()
    result = asyncio.run(module._set_device_power("MyPlug", on=False))
    assert result.get("status") == "ok"
    assert result.get("on") is False
    fake_p100.turnOff.assert_called_once()


def test_set_device_power_unknown_device():
    module, _ = _make_tapo()
    result = asyncio.run(module._set_device_power("NoSuchDevice", on=True))
    assert "error" in result


def test_set_device_power_no_credentials():
    module, _ = _make_tapo(email="", password="")
    result = asyncio.run(module._set_device_power("MyPlug", on=True))
    assert "error" in result


def test_get_routes_registers_on_and_off():
    module, _ = _make_tapo()
    router = module.get_routes()
    assert router is not None
    paths = {r.path for r in router.routes}
    assert "/devices/{device_name}/on" in paths
    assert "/devices/{device_name}/off" in paths
