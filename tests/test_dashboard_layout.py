"""Tests for dashboard layout persistence and application."""

import re


def _order(html):
    return re.findall(r'data-module="([a-z_]+)"', html)


def _size_class(html, module):
    m = re.search(r'class="widget-card widget-(\w+)"\s+data-module="' + module + '"', html)
    return m.group(1) if m else None


def test_partial_layout_appends_unlisted_modules(client):
    full = _order(client.get("/").text)
    assert len(full) >= 3
    chosen = [full[1], full[0]]
    layout = [{"module": m, "size": "medium"} for m in chosen]
    client.post("/api/dashboard/layout", json={"layout": layout})
    got = _order(client.get("/").text)
    assert got[:2] == chosen
    assert set(got) == set(full)  # the rest are appended, none lost


def test_layout_overrides_widget_size(client):
    order = _order(client.get("/").text)
    target = order[0]
    client.post("/api/dashboard/layout", json={"layout": [{"module": target, "size": "large"}]})
    assert _size_class(client.get("/").text, target) == "large"


def test_unknown_module_in_layout_is_ignored(client):
    order = _order(client.get("/").text)
    layout = [{"module": "does_not_exist", "size": "medium"}] + \
             [{"module": m, "size": "medium"} for m in order]
    client.post("/api/dashboard/layout", json={"layout": layout})
    got = _order(client.get("/").text)
    assert "does_not_exist" not in got
    assert set(got) == set(order)


def test_reset_restores_default_order(client):
    default = _order(client.get("/").text)
    client.post("/api/dashboard/layout",
                json={"layout": [{"module": m, "size": "medium"} for m in reversed(default)]})
    assert client.delete("/api/dashboard/layout").status_code == 200
    assert _order(client.get("/").text) == default
