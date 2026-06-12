"""Optional authentication tests."""

from fastapi.testclient import TestClient

AUTH_CONFIG = """\
app:
  name: "SHIAB Test"
  host: "127.0.0.1"
  port: 8000
database:
  path: "data/shiab.db"
theme:
  active: "default"
auth:
  enabled: true
  password: "s3cret"
modules:
  timedate:
    enabled: true
    settings: {timezone: "UTC", format_24h: true}
"""


def _auth_client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(AUTH_CONFIG)
    (tmp_path / "data").mkdir(exist_ok=True)
    from app.main import app
    return TestClient(app)


def test_auth_disabled_by_default_allows_access(client):
    # `client` fixture (conftest) uses the no-auth config.
    assert client.get("/").status_code == 200


def test_protected_page_redirects_to_login(tmp_path, monkeypatch):
    with _auth_client(tmp_path, monkeypatch) as c:
        resp = c.get("/", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"].startswith("/login")


def test_protected_api_returns_401(tmp_path, monkeypatch):
    with _auth_client(tmp_path, monkeypatch) as c:
        assert c.get("/api/modules", follow_redirects=False).status_code == 401


def test_static_allowed_without_auth(tmp_path, monkeypatch):
    with _auth_client(tmp_path, monkeypatch) as c:
        assert c.get("/static/css/main.css").status_code == 200


def test_login_flow(tmp_path, monkeypatch):
    with _auth_client(tmp_path, monkeypatch) as c:
        assert c.post("/login", data={"password": "wrong"},
                      follow_redirects=False).status_code == 401
        ok = c.post("/login", data={"password": "s3cret"}, follow_redirects=False)
        assert ok.status_code == 303
        assert c.get("/").status_code == 200  # session cookie now set


def test_login_blocks_open_redirect(tmp_path, monkeypatch):
    with _auth_client(tmp_path, monkeypatch) as c:
        resp = c.post("/login", data={"password": "s3cret", "next": "//evil.com"},
                      follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"
