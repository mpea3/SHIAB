"""Characterization tests: these PIN CURRENT (BUGGY) BEHAVIOUR.

Plan 003 (dashboard layout) flips `test_saved_layout_*`.
Plan 004 (module-state persistence) flips `test_module_disable_*`.
Do not "fix" these here — they document the baseline.
"""

import re

from fastapi.testclient import TestClient


def _module_order(html: str) -> list[str]:
    return re.findall(r'data-module="([a-z_]+)"', html)


def test_saved_layout_IS_applied_on_render(client):
    default_order = _module_order(client.get("/").text)
    reversed_layout = [{"module": m, "size": "medium"} for m in reversed(default_order)]
    assert client.post("/api/dashboard/layout", json={"layout": reversed_layout}).status_code == 200
    assert _module_order(client.get("/").text) == list(reversed(default_order))


def test_module_disable_IS_persisted_across_restart(app_env):
    from app.main import app
    with TestClient(app) as c:
        assert c.post("/api/modules/weather/disable").status_code == 200
        weather = next(m for m in c.get("/api/modules").json() if m["name"] == "weather")
        assert weather["enabled"] is False
    # Restart (same working dir → same config.yaml). State must persist.
    with TestClient(app) as c:
        weather = next(m for m in c.get("/api/modules").json() if m["name"] == "weather")
        assert weather["enabled"] is False
