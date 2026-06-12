"""Dashboard router - serves the main dashboard page."""

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.database import get_session_factory
from app.models import Setting
from app.routers.api import DASHBOARD_LAYOUT_KEY

router = APIRouter()

_VALID_SIZES = {"small", "medium", "large"}


async def _get_module_data_safe(module) -> dict:
    """Call module.get_data() with error isolation."""
    try:
        return await module.get_data()
    except Exception as e:
        return {"error": True, "error_message": str(e)}


async def _load_saved_layout() -> list[dict]:
    """Return the saved [{module, size}, ...] layout, or [] if none/invalid."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == DASHBOARD_LAYOUT_KEY)
        )
        setting = result.scalar_one_or_none()
    if not setting:
        return []
    try:
        data = json.loads(setting.value)
    except (json.JSONDecodeError, TypeError):
        return []
    return data if isinstance(data, list) else []


def _apply_layout(modules_data: list[dict], layout: list[dict]) -> list[dict]:
    """Reorder modules_data per layout and override widget sizes.

    Modules named in the layout appear first, in layout order, with the
    layout's size (when valid). Enabled modules not in the layout are appended
    afterwards so newly enabled modules still show up.
    """
    if not layout:
        return modules_data

    by_name = {m["name"]: m for m in modules_data}
    ordered: list[dict] = []
    seen: set[str] = set()
    for item in layout:
        if not isinstance(item, dict):
            continue
        name = item.get("module")
        md = by_name.get(name)
        if md is None or name in seen:
            continue
        size = item.get("size")
        if size in _VALID_SIZES:
            md = {**md, "widget_size": size}
        ordered.append(md)
        seen.add(name)

    for md in modules_data:
        if md["name"] not in seen:
            ordered.append(md)
    return ordered


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main dashboard with all enabled module widgets."""
    registry = request.app.state.module_registry
    config = request.app.state.config
    templates = request.app.state.templates

    enabled_modules = registry.get_enabled()

    data_results = await asyncio.gather(
        *(_get_module_data_safe(m) for m in enabled_modules)
    )

    modules_data = [
        {
            "name": module.name,
            "display_name": module.display_name,
            "icon": module.icon,
            "widget_template": module.widget_template,
            "widget_size": module.widget_size,
            "refresh_interval": module.refresh_interval,
            "data": data,
        }
        for module, data in zip(enabled_modules, data_results)
    ]

    layout = await _load_saved_layout()
    modules_data = _apply_layout(modules_data, layout)

    return templates.TemplateResponse(request, "dashboard.html", {
        "modules": modules_data,
        "theme": config.theme.active,
        "app_name": config.name,
    })
