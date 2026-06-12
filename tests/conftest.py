"""Shared pytest fixtures: run SHIAB in an isolated working dir."""

import pytest
from fastapi.testclient import TestClient

# Only built-in modules load (no modules_external/ in the temp CWD).
# calendar + bluetooth are present-but-disabled so the enabled set is
# deterministic: system_stats, timedate, weather, wifi (in loader order).
CONFIG_YAML = """\
app:
  name: "SHIAB Test"
  host: "127.0.0.1"
  port: 8000
database:
  path: "data/shiab.db"
theme:
  active: "default"
modules:
  system_stats:
    enabled: true
    settings: {}
  timedate:
    enabled: true
    settings: {timezone: "UTC", format_24h: true}
  weather:
    enabled: true
    settings: {api_key: "", city: "London", units: "metric"}
  wifi:
    enabled: true
    settings: {devices: [], check_interval: 60}
  calendar:
    enabled: false
    settings: {max_upcoming: 5}
  bluetooth:
    enabled: false
    settings: {}
"""


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """Isolated working dir containing config.yaml and a data/ folder."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(CONFIG_YAML)
    (tmp_path / "data").mkdir(exist_ok=True)
    return tmp_path


@pytest.fixture
def client(app_env):
    """A TestClient bound to the real app. Entering the context manager runs
    the app's full startup lifespan (config load, DB init, module load)."""
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client
