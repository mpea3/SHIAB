"""SHIAB - Smart Home in a Box. FastAPI application entry point."""

import asyncio
import logging
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import func, select

from app import __version__
from app.config import load_config
from app.database import dispose_engine, get_session_factory, init_db
from app.models import Notification, SensorReading
from app.modules.loader import load_all_modules
from app.routers import api, dashboard, settings
from app.routers import automations, history, notifications

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("shiab")

# Background task intervals (seconds)
DATA_LOG_INTERVAL = 60
AUTOMATION_EVAL_INTERVAL = 30
WS_BROADCAST_INTERVAL = 10


# ---------------------------------------------------------------------------
# Jinja2 filters
# ---------------------------------------------------------------------------

_ICON_PATTERN = re.compile(r"^(&#\d+;)+$")


def _safe_icon_filter(value: str) -> str:
    """Allow only HTML numeric-entity icons (e.g. &#128197;). Blocks arbitrary HTML."""
    from markupsafe import Markup
    if _ICON_PATTERN.match(value):
        return Markup(value)
    # Not a recognised entity pattern — escape and return as plain text
    return value


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class _ConnectionManager:
    """Thread-safe WebSocket connection manager."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    @property
    def has_clients(self) -> bool:
        return bool(self._connections)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            try:
                self._connections.remove(ws)
            except ValueError:
                pass

    async def broadcast(self, data: dict) -> None:
        async with self._lock:
            stale: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_json(data)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                try:
                    self._connections.remove(ws)
                except ValueError:
                    pass


ws_manager = _ConnectionManager()


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

async def _data_logger(app: FastAPI) -> None:
    """Log numeric sensor readings from enabled modules periodically."""
    await asyncio.sleep(DATA_LOG_INTERVAL // 2)
    while True:
        try:
            registry = app.state.module_registry
            factory = get_session_factory()
            for module in registry.get_enabled():
                try:
                    data = await asyncio.wait_for(
                        module.get_data(), timeout=10.0,
                    )
                    if data.get("error"):
                        continue
                    readings = [
                        SensorReading(
                            module_name=module.name,
                            key=key,
                            value=float(value),
                        )
                        for key, value in data.items()
                        if isinstance(value, (int, float))
                        and not isinstance(value, bool)
                    ]
                    if readings:
                        async with factory() as session:
                            session.add_all(readings)
                            await session.commit()
                            
                    if ws_manager.has_clients:
                        await ws_manager.broadcast({
                            "type": "module_update",
                            "module": module.name,
                            "data": data,
                        })
                except asyncio.TimeoutError:
                    logger.debug("Data logger: %s timed out", module.name)
                except Exception as e:
                    logger.debug("Data logger skipped %s: %s", module.name, e)
        except Exception as e:
            logger.warning("Data logger cycle error: %s", e)
        await asyncio.sleep(DATA_LOG_INTERVAL)


async def _automation_evaluator(app: FastAPI) -> None:
    """Evaluate automation rules periodically."""
    await asyncio.sleep(AUTOMATION_EVAL_INTERVAL // 2)
    while True:
        try:
            await automations.evaluate_automations(app)
        except Exception as e:
            logger.warning("Automation evaluator error: %s", e)
        await asyncio.sleep(AUTOMATION_EVAL_INTERVAL)


_ws_cached_unread: int = 0


async def _ws_broadcaster(app: FastAPI) -> None:
    """Push notification count to WebSocket clients periodically."""
    global _ws_cached_unread
    while True:
        await asyncio.sleep(WS_BROADCAST_INTERVAL)
        if not ws_manager.has_clients:
            continue
        try:
            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    select(func.count())
                    .select_from(Notification)
                    .where(Notification.read.is_(False))
                )
                unread = result.scalar_one()

            if unread != _ws_cached_unread:
                _ws_cached_unread = unread
                await ws_manager.broadcast({
                    "type": "status",
                    "unread_notifications": unread,
                })
        except Exception as e:
            logger.debug("WS broadcaster error: %s", e)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # --- STARTUP ---
    logger.info("Starting SHIAB v%s", __version__)

    config = load_config()
    app.state.config = config
    logger.info("Configuration loaded (theme: %s)", config.theme.active)

    engine = await init_db(config.database.path)
    app.state.db_engine = engine
    logger.info("Database initialized at %s", config.database.path)

    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    templates.env.globals["version"] = __version__
    templates.env.filters["safe_icon"] = _safe_icon_filter
    app.state.templates = templates

    # Cache available themes at startup
    themes_dir = Path(__file__).parent / "static" / "css" / "themes"
    app.state.available_themes = sorted(
        f.stem for f in themes_dir.glob("*.css")
    ) if themes_dir.exists() else []

    registry = await load_all_modules(config, engine)
    app.state.module_registry = registry
    logger.info(
        "Loaded %d modules (%d enabled)",
        len(registry.get_all()),
        len(registry.get_enabled()),
    )

    for module in registry.get_all():
        custom_routes = module.get_routes()
        if custom_routes:
            app.include_router(
                custom_routes,
                prefix=f"/api/modules/{module.name}",
                tags=[module.display_name],
            )
            logger.info("Mounted custom routes for module: %s", module.name)

    # Start background tasks
    bg_tasks = [
        asyncio.create_task(_data_logger(app)),
        asyncio.create_task(_automation_evaluator(app)),
        asyncio.create_task(_ws_broadcaster(app)),
    ]
    app.state.bg_tasks = bg_tasks

    yield

    # --- SHUTDOWN ---
    logger.info("Shutting down SHIAB")
    for task in bg_tasks:
        task.cancel()
    await asyncio.gather(*bg_tasks, return_exceptions=True)
    await dispose_engine()


# ---------------------------------------------------------------------------
# Create application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SHIAB",
    description=(
        "**Smart Home in a Box** — a self-hosted, modular smart home hub.\n\n"
        "Core endpoints:\n"
        "- `/api/modules` — list all modules and their status\n"
        "- `/api/modules/{name}/data` — fetch live data from a module\n"
        "- `/api/modules/{name}/enable|disable` — toggle a module\n"
        "- `/api/automations` — CRUD for trigger→action rules\n"
        "- `/api/notifications` — in-app notification management\n"
        "- `/api/dashboard/layout` — save/reset the widget layout\n"
        "- `/api/history/{module}/{key}` — time-series sensor readings\n\n"
        "Interactive docs: `/docs` (Swagger UI) · `/redoc` (ReDoc)"
    ),
    version=__version__,
    lifespan=lifespan,
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ---------------------------------------------------------------------------
# Optional authentication
# ---------------------------------------------------------------------------

# Stable across restarts only if SHIAB_SECRET_KEY is set; otherwise sessions
# reset on restart (users simply log in again).
_SECRET_KEY = os.environ.get("SHIAB_SECRET_KEY") or secrets.token_hex(32)


def _safe_next(url: str) -> str:
    """Allow only same-site relative redirect targets (no open redirects)."""
    if url.startswith("/") and not url.startswith("//"):
        return url
    return "/"


def _is_public_path(path: str) -> bool:
    return (
        path in ("/login", "/logout", "/docs", "/redoc", "/openapi.json")
        or path.startswith("/static/")
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Gate all routes behind a session login when auth is enabled."""

    async def dispatch(self, request: Request, call_next):
        config = getattr(request.app.state, "config", None)
        auth = getattr(config, "auth", None)
        if not auth or not auth.enabled:
            return await call_next(request)

        path = request.url.path
        if _is_public_path(path) or request.session.get("authed"):
            return await call_next(request)

        if path.startswith("/api") or path.startswith("/ws"):
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        return RedirectResponse(url="/login?next=" + quote(path), status_code=303)


# Order matters: SessionMiddleware must wrap AuthMiddleware so request.session
# exists when AuthMiddleware runs. The LAST add_middleware call is outermost.
app.add_middleware(AuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=_SECRET_KEY,
    same_site="lax",
    https_only=False,
)


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    """Show the login page (or redirect to / when auth is off)."""
    config = request.app.state.config
    if not config.auth.enabled:
        return RedirectResponse(url="/", status_code=303)
    return request.app.state.templates.TemplateResponse(request, "login.html", {
        "app_name": config.name,
        "theme": config.theme.active,
        "error": None,
        "next": _safe_next(request.query_params.get("next", "/")),
    })


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request):
    """Validate password and set session cookie."""
    config = request.app.state.config
    form = await request.form()
    password = str(form.get("password", ""))
    next_url = _safe_next(str(form.get("next", "/")))

    if config.auth.password and secrets.compare_digest(password, config.auth.password):
        request.session["authed"] = True
        return RedirectResponse(url=next_url, status_code=303)

    return request.app.state.templates.TemplateResponse(request, "login.html", {
        "app_name": config.name,
        "theme": config.theme.active,
        "error": "Incorrect password",
        "next": next_url,
    }, status_code=401)


@app.get("/logout")
async def logout(request: Request):
    """Clear the session and redirect to login."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


app.include_router(dashboard.router)
app.include_router(api.router)
app.include_router(settings.router)
app.include_router(history.router)
app.include_router(notifications.router)
app.include_router(automations.router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(websocket)
