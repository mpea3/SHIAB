"""End-to-end smoke tests through the ASGI app."""


def test_dashboard_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    for name in ("system_stats", "timedate", "weather", "wifi"):
        assert f'data-module="{name}"' in resp.text


def test_list_modules(client):
    resp = client.get("/api/modules")
    assert resp.status_code == 200
    by_name = {m["name"]: m for m in resp.json()}
    assert by_name["weather"]["enabled"] is True
    assert by_name["calendar"]["enabled"] is False


def test_module_data_endpoint(client):
    resp = client.get("/api/modules/weather/data")
    assert resp.status_code == 200
    assert resp.json()["demo"] is True


def test_other_pages_render(client):
    for path in ("/settings", "/automations", "/notifications"):
        assert client.get(path).status_code == 200


def test_notifications_crud(client):
    created = client.post("/api/notifications", json={"title": "Hello"})
    assert created.status_code == 200
    nid = created.json()["id"]
    listing = client.get("/api/notifications").json()
    assert any(n["id"] == nid for n in listing)


def test_automation_create_and_delete(client):
    body = {
        "name": "Hot", "trigger_module": "weather", "trigger_key": "temperature",
        "trigger_operator": "gt", "trigger_value": "0", "action_type": "notify",
        "action_payload": {"message": "warm"},
    }
    created = client.post("/api/automations", json=body)
    assert created.status_code == 200
    aid = created.json()["id"]
    assert client.delete(f"/api/automations/{aid}").status_code == 200
