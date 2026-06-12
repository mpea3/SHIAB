"""Module enable/disable + config persistence across restart."""

from fastapi.testclient import TestClient


def test_enable_persists_across_restart(app_env):
    from app.main import app
    with TestClient(app) as c:
        # calendar starts disabled in the test config; enable it.
        assert c.post("/api/modules/calendar/enable").status_code == 200
    with TestClient(app) as c:
        cal = next(m for m in c.get("/api/modules").json() if m["name"] == "calendar")
        assert cal["enabled"] is True


def test_config_update_persists_across_restart(app_env):
    from app.main import app
    with TestClient(app) as c:
        resp = c.post("/api/modules/weather/config", json={"city": "Berlin"})
        assert resp.status_code == 200
        assert resp.json()["config"]["city"] == "Berlin"
    with TestClient(app) as c:
        import yaml
        with open("config.yaml") as f:
            saved = yaml.safe_load(f)
        assert saved["modules"]["weather"]["settings"]["city"] == "Berlin"
