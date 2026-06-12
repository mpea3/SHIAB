"""Unit tests for pure helper functions (no DB, no network)."""

import asyncio

from app.routers.automations import (
    _evaluate, _get_nested, _parse_payload, _validate_automation_body,
)
from app.main import _safe_icon_filter


def test_evaluate_numeric_operators():
    assert _evaluate(10, "gt", "5") is True
    assert _evaluate(3, "gt", "5") is False
    assert _evaluate(5, "gte", "5") is True
    assert _evaluate(4, "lt", "5") is True
    assert _evaluate(5, "eq", "5") is True
    assert _evaluate(5, "ne", "6") is True


def test_evaluate_string_fallback_and_none():
    assert _evaluate("Cloudy", "contains", "loud") is True
    assert _evaluate("on", "eq", "ON") is True   # case-insensitive
    assert _evaluate(None, "gt", "0") is False


def test_get_nested():
    data = {"a": {"b": [10, 20]}}
    assert _get_nested(data, "a.b.1") == 20
    assert _get_nested(data, "a.missing") is None
    assert _get_nested(data, "a.b.9") is None  # index out of range


def test_parse_payload():
    assert _parse_payload('{"x": 1}') == {"x": 1}
    assert _parse_payload("not json") == {}
    assert _parse_payload(None) == {}


def test_validate_automation_body_requires_fields():
    assert _validate_automation_body({}, require_all=True) is not None
    good = {
        "name": "x", "trigger_module": "weather", "trigger_key": "temperature",
        "trigger_operator": "gt", "trigger_value": "20", "action_type": "notify",
    }
    assert _validate_automation_body(good, require_all=True) is None


def test_validate_automation_body_rejects_bad_operator_and_action():
    assert _validate_automation_body({"trigger_operator": "bogus"}, require_all=False)
    assert _validate_automation_body({"action_type": "rm-rf"}, require_all=False)


def test_validate_automation_body_rejects_non_http_webhook():
    body = {"action_type": "webhook", "action_payload": {"url": "ftp://x/y"}}
    assert _validate_automation_body(body, require_all=False) is not None


def test_safe_icon_filter_allows_entities_blocks_html():
    from markupsafe import Markup
    assert isinstance(_safe_icon_filter("&#128197;"), Markup)
    # Arbitrary HTML is NOT returned as Markup (so Jinja will escape it):
    assert not isinstance(_safe_icon_filter("<b>x</b>"), Markup)


def test_load_config_reads_yaml_and_env_override(tmp_path, monkeypatch):
    from app.config import load_config
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "app:\n  name: Demo\n  port: 9000\ntheme:\n  active: dark\n"
    )
    cfg = load_config()
    assert cfg.name == "Demo"
    assert cfg.theme.active == "dark"
    monkeypatch.setenv("SHIAB_PORT", "1234")
    assert load_config().port == 1234


def test_weather_demo_data_no_api_key():
    from app.modules.weather import WeatherModule
    data = asyncio.run(WeatherModule({}).get_data())
    assert data["demo"] is True
    assert "temperature" in data


def test_timedate_returns_time_and_date():
    from app.modules.timedate import TimeDateModule
    data = asyncio.run(TimeDateModule({"timezone": "UTC"}).get_data())
    assert "time" in data and "date" in data
