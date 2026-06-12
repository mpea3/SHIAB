"""Regression tests for webhook SSRF protection."""

import app.routers.automations as autos


def test_blocked_ip_ranges():
    for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254",
               "::1", "0.0.0.0"):
        assert autos._is_blocked_ip(ip) is True
    for ip in ("93.184.216.34", "1.1.1.1", "2606:4700:4700::1111"):
        assert autos._is_blocked_ip(ip) is False


def test_validate_webhook_url_rejects_private(monkeypatch):
    monkeypatch.setattr(autos, "_resolve_host_ips", lambda h: ["192.168.1.50"])
    ip, err = autos._validate_webhook_url("http://intranet.local/hook")
    assert err is not None

def test_validate_webhook_url_allows_public(monkeypatch):
    monkeypatch.setattr(autos, "_resolve_host_ips", lambda h: ["93.184.216.34"])
    ip, err = autos._validate_webhook_url("https://example.com/hook")
    assert err is None

def test_validate_webhook_url_rejects_bad_scheme():
    ip, err = autos._validate_webhook_url("ftp://example.com/x")
    assert err is not None


def test_create_automation_rejects_private_webhook(client, monkeypatch):
    monkeypatch.setattr(autos, "_resolve_host_ips", lambda h: ["127.0.0.1"])
    body = {
        "name": "evil", "trigger_module": "weather", "trigger_key": "temperature",
        "trigger_operator": "gt", "trigger_value": "0", "action_type": "webhook",
        "action_payload": {"url": "http://localhost/admin"},
    }
    resp = client.post("/api/automations", json=body)
    assert resp.status_code == 400
