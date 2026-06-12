"""API router - JSON endpoints for module data and control."""

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.database import get_session_factory
from app.models import Setting

router = APIRouter(prefix="/api")

DASHBOARD_LAYOUT_KEY = "dashboard_layout"


@router.get("/modules")
async def list_modules(request: Request):
    """List all modules with their status."""
    registry = request.app.state.module_registry
    return [
        {
            "name": module.name,
            "display_name": module.display_name,
            "description": module.description,
            "version": module.version,
            "icon": module.icon,
            "enabled": module.enabled,
            "widget_size": module.widget_size,
        }
        for module in registry.get_all()
    ]


@router.get("/modules/{module_name}/data")
async def get_module_data(module_name: str, request: Request):
    """Get data from a specific module."""
    registry = request.app.state.module_registry
    module = registry.get(module_name)

    if module is None:
        return JSONResponse({"error": "Module not found"}, status_code=404)

    if not module.enabled:
        return JSONResponse({"error": "Module is disabled"}, status_code=400)

    try:
        data = await module.get_data()
        return data
    except Exception as e:
        return JSONResponse({"error": True, "error_message": str(e)}, status_code=500)


async def _set_module_enabled(module_name: str, request: Request, enabled: bool):
    """Shared logic for enabling/disabling a module."""
    registry = request.app.state.module_registry
    module = registry.get(module_name)

    if module is None:
        return JSONResponse({"error": "Module not found"}, status_code=404)

    module.enabled = enabled
    if enabled:
        await module.on_enable()
    else:
        await module.on_disable()

    from app.routers.settings import _save_config
    _save_config(request.app.state.config, registry)

    return {"status": "ok", "module": module_name, "enabled": enabled}


@router.post("/modules/{module_name}/enable")
async def enable_module(module_name: str, request: Request):
    """Enable a module."""
    return await _set_module_enabled(module_name, request, True)


@router.post("/modules/{module_name}/disable")
async def disable_module(module_name: str, request: Request):
    """Disable a module."""
    return await _set_module_enabled(module_name, request, False)


@router.post("/modules/{module_name}/config")
async def update_module_config(module_name: str, request: Request):
    """Update a module's configuration."""
    registry = request.app.state.module_registry
    module = registry.get(module_name)

    if module is None:
        return JSONResponse({"error": "Module not found"}, status_code=404)

    body = await request.json()
    module.config.update(body)

    from app.routers.settings import _save_config
    _save_config(request.app.state.config, registry)

    return {"status": "ok", "module": module_name, "config": module.config}


@router.post("/dashboard/layout")
async def save_dashboard_layout(request: Request):
    """Save custom dashboard layout to database."""
    body = await request.json()
    layout = body.get("layout", [])

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == DASHBOARD_LAYOUT_KEY)
        )
        setting = result.scalar_one_or_none()
        layout_json = json.dumps(layout)
        if setting:
            setting.value = layout_json
        else:
            session.add(Setting(key=DASHBOARD_LAYOUT_KEY, value=layout_json))
        await session.commit()

    return {"status": "ok", "message": "Layout saved"}


@router.delete("/dashboard/layout")
async def reset_dashboard_layout(request: Request):
    """Reset dashboard layout to default."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == DASHBOARD_LAYOUT_KEY)
        )
        setting = result.scalar_one_or_none()
        if setting:
            await session.delete(setting)
            await session.commit()

    return {"status": "ok", "message": "Layout reset to default"}
