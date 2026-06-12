"""Automation rules engine - trigger conditions → actions."""

import asyncio
import ipaddress
import json
import logging
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select

from app.database import get_session_factory
from app.models import Automation

logger = logging.getLogger("shiab.automations")

router = APIRouter()

_VALID_OPERATORS = frozenset({"gt", "gte", "lt", "lte", "eq", "ne", "contains"})
_VALID_ACTIONS = frozenset({"notify", "webhook"})


def _parse_payload(raw: str | None) -> dict:
    """Safely parse action_payload JSON, returning empty dict on failure."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _is_blocked_ip(ip: str) -> bool:
    """True if an IP must not be a webhook target (non-public ranges)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # unparseable → treat as unsafe
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _resolve_host_ips(host: str) -> list[str]:
    """Resolve a hostname to all of its IP addresses (blocking)."""
    infos = socket.getaddrinfo(host, None)
    return list({info[4][0] for info in infos})


def _validate_webhook_url(url: str) -> tuple[str | None, str | None]:
    """Return (safe_ip, error_string). If safe, error is None."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None, "Webhook URL must use http or https"
    host = parsed.hostname
    if not host:
        return None, "Webhook URL has no host"
    try:
        ips = _resolve_host_ips(host)
    except socket.gaierror:
        return None, f"Could not resolve webhook host: {host}"
    
    # We choose the first resolved IP for connection
    if not ips or any(_is_blocked_ip(ip) for ip in ips):
        return None, "Webhook URL must resolve to a public address (no private, loopback, or link-local hosts)"
    
    return ips[0], None


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@router.get("/automations", response_class=HTMLResponse)
async def automations_page(request: Request):
    """Render the automations management page."""
    templates = request.app.state.templates
    config = request.app.state.config
    registry = request.app.state.module_registry

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Automation).order_by(Automation.created_at.desc())
        )
        automations = result.scalars().all()

    module_names = [m.name for m in registry.get_all()]

    return templates.TemplateResponse(
        request,
        "automations.html",
        {
            "automations": automations,
            "module_names": module_names,
            "theme": config.theme.active,
            "app_name": config.name,
        },
    )


# ---------------------------------------------------------------------------
# CRUD API
# ---------------------------------------------------------------------------

@router.get("/api/automations")
async def list_automations():
    """List all automations."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Automation).order_by(Automation.created_at.desc())
        )
        automations = result.scalars().all()
    return [_to_dict(a) for a in automations]


@router.post("/api/automations")
async def create_automation(request: Request):
    """Create a new automation rule."""
    body = await request.json()
    err = _validate_automation_body(body, require_all=True)
    if err:
        return JSONResponse({"error": err}, status_code=400)

    factory = get_session_factory()
    async with factory() as session:
        automation = Automation(
            name=body["name"].strip(),
            description=body.get("description"),
            enabled=body.get("enabled", True),
            trigger_module=body["trigger_module"],
            trigger_key=body["trigger_key"],
            trigger_operator=body["trigger_operator"],
            trigger_value=str(body["trigger_value"]),
            action_type=body["action_type"],
            action_payload=json.dumps(body.get("action_payload", {})),
            cooldown_seconds=max(0, int(body.get("cooldown_seconds", 300))),
        )
        session.add(automation)
        await session.commit()
        await session.refresh(automation)
        return _to_dict(automation)


@router.put("/api/automations/{automation_id}")
async def update_automation(automation_id: int, request: Request):
    """Update an automation."""
    body = await request.json()
    err = _validate_automation_body(body, require_all=False)
    if err:
        return JSONResponse({"error": err}, status_code=400)

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Automation).where(Automation.id == automation_id)
        )
        automation = result.scalar_one_or_none()
        if not automation:
            return JSONResponse({"error": "Not found"}, status_code=404)

        if "name" in body:
            automation.name = body["name"]
        if "description" in body:
            automation.description = body["description"]
        if "trigger_module" in body:
            automation.trigger_module = body["trigger_module"]
        if "trigger_key" in body:
            automation.trigger_key = body["trigger_key"]
        if "trigger_operator" in body:
            automation.trigger_operator = body["trigger_operator"]
        if "trigger_value" in body:
            automation.trigger_value = str(body["trigger_value"])
        if "action_type" in body:
            automation.action_type = body["action_type"]
        if "enabled" in body:
            automation.enabled = bool(body["enabled"])
        if "action_payload" in body:
            automation.action_payload = json.dumps(body["action_payload"])
        if "cooldown_seconds" in body:
            automation.cooldown_seconds = max(0, int(body["cooldown_seconds"]))

        await session.commit()
        await session.refresh(automation)
        return _to_dict(automation)


@router.delete("/api/automations/{automation_id}")
async def delete_automation(automation_id: int):
    """Delete an automation."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Automation).where(Automation.id == automation_id)
        )
        automation = result.scalar_one_or_none()
        if not automation:
            return JSONResponse({"error": "Not found"}, status_code=404)
        await session.delete(automation)
        await session.commit()
    return {"status": "deleted", "id": automation_id}


@router.post("/api/automations/{automation_id}/toggle")
async def toggle_automation(automation_id: int):
    """Toggle enabled/disabled state."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Automation).where(Automation.id == automation_id)
        )
        automation = result.scalar_one_or_none()
        if not automation:
            return JSONResponse({"error": "Not found"}, status_code=404)
        automation.enabled = not automation.enabled
        await session.commit()
        return {"id": automation_id, "enabled": automation.enabled}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_automation_body(body: dict, *, require_all: bool) -> str | None:
    """Return an error string, or None when valid."""
    if require_all:
        name = body.get("name", "").strip() if isinstance(body.get("name"), str) else ""
        if not name:
            return "name is required"
        for field in ("trigger_module", "trigger_key", "trigger_operator",
                      "trigger_value", "action_type"):
            if not body.get(field):
                return f"{field} is required"

    op = body.get("trigger_operator")
    if op is not None and op not in _VALID_OPERATORS:
        return f"Invalid operator: {op}"

    action = body.get("action_type")
    if action is not None and action not in _VALID_ACTIONS:
        return f"Invalid action_type: {action}"

    # Validate webhook URL (scheme + resolves to a public address)
    if action == "webhook" or (action is None and not require_all):
        payload = body.get("action_payload", {})
        url = payload.get("url", "") if isinstance(payload, dict) else ""
        if url:
            _, err = _validate_webhook_url(url)
            if err:
                return err

    return None


# ---------------------------------------------------------------------------
# Evaluation engine (called by background task in main.py)
# ---------------------------------------------------------------------------

def _get_nested(data: dict, key_path: str):
    """Get a value from nested dict/list using dot notation."""
    current = data
    for part in key_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (IndexError, ValueError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


def _evaluate(actual, operator: str, threshold: str) -> bool:
    """Return True when the trigger condition is satisfied."""
    if actual is None:
        return False

    # Numeric comparison
    try:
        a = float(str(actual))
        t = float(threshold)
        ops = {
            "gt": a > t, "gte": a >= t, "lt": a < t, "lte": a <= t,
            "eq": a == t, "ne": a != t,
        }
        if operator in ops:
            return ops[operator]
    except (ValueError, TypeError):
        pass

    # String fallback
    a_str = str(actual).lower()
    t_str = threshold.lower()
    if operator == "eq":
        return a_str == t_str
    if operator == "ne":
        return a_str != t_str
    if operator == "contains":
        return t_str in a_str
    return False


async def evaluate_automations(app) -> None:
    """Evaluate all enabled automations. Called by the background task."""
    from app.routers.notifications import create_notification

    registry = app.state.module_registry
    factory = get_session_factory()
    now = datetime.now(timezone.utc)

    async with factory() as session:
        result = await session.execute(
            select(Automation).where(Automation.enabled.is_(True))
        )
        automations = result.scalars().all()

    if not automations:
        return

    # Fetch module data once per module per evaluation cycle (not once per automation).
    module_data_cache: dict[str, dict] = {}

    for auto in automations:
        # Respect cooldown
        if auto.last_triggered:
            elapsed = (now - auto.last_triggered.replace(tzinfo=timezone.utc)).total_seconds()
            if elapsed < auto.cooldown_seconds:
                continue

        module = registry.get(auto.trigger_module)
        if not module or not module.enabled:
            continue

        try:
            if auto.trigger_module not in module_data_cache:
                module_data_cache[auto.trigger_module] = await module.get_data()
            data = module_data_cache[auto.trigger_module]
            if data.get("error"):
                continue

            actual = _get_nested(data, auto.trigger_key)
            if actual is None:
                continue

            if not _evaluate(actual, auto.trigger_operator, auto.trigger_value):
                continue

            # Condition met — execute action then update timestamp in one session
            await _execute_action(auto, actual, create_notification)

            async with factory() as session:
                result = await session.execute(
                    select(Automation).where(Automation.id == auto.id)
                )
                obj = result.scalar_one_or_none()
                if obj:
                    obj.last_triggered = now
                    await session.commit()

        except Exception as e:
            logger.warning("Automation %d (%s) error: %s", auto.id, auto.name, e)


async def _execute_action(auto: Automation, actual_value, create_notification) -> None:
    """Perform the automation action."""
    payload = _parse_payload(auto.action_payload)

    if auto.action_type == "notify":
        title = payload.get("title") or f"Automation triggered: {auto.name}"
        message = payload.get("message") or (
            f"{auto.trigger_module}.{auto.trigger_key} "
            f"{auto.trigger_operator} {auto.trigger_value} "
            f"(current value: {actual_value})"
        )
        level = payload.get("level", "warning")
        await create_notification(title, message, level, module_name=auto.trigger_module)
        logger.info("Automation '%s' fired notification: %s", auto.name, title)

    elif auto.action_type == "webhook":
        url = payload.get("url")
        if not url:
            return
        safe_ip, err = await asyncio.to_thread(_validate_webhook_url, url)
        if err:
            logger.warning("Automation '%s': unsafe webhook URL rejected (%s)", auto.name, err)
            return

        import httpx
        parsed = urlparse(url)
        port = f":{parsed.port}" if parsed.port else ""
        safe_url = f"{parsed.scheme}://{safe_ip}{port}{parsed.path}"
        if parsed.query: safe_url += f"?{parsed.query}"

        # Using the resolved IP prevents DNS rebinding (TOCTOU).
        # We pass the original hostname in headers.
        headers = {"Host": parsed.hostname}

        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                await client.post(
                    safe_url,
                    headers=headers,
                    json={
                        "automation": auto.name,
                        "trigger_module": auto.trigger_module,
                        "trigger_key": auto.trigger_key,
                        "actual_value": actual_value,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            logger.info("Automation '%s' webhook sent to %s (via %s)", auto.name, url, safe_ip)
        except Exception as e:
            logger.warning("Automation '%s' webhook error: %s", auto.name, e)


def _to_dict(a: Automation) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "description": a.description,
        "enabled": a.enabled,
        "trigger_module": a.trigger_module,
        "trigger_key": a.trigger_key,
        "trigger_operator": a.trigger_operator,
        "trigger_value": a.trigger_value,
        "action_type": a.action_type,
        "action_payload": _parse_payload(a.action_payload),
        "cooldown_seconds": a.cooldown_seconds,
        "last_triggered": a.last_triggered.isoformat() if a.last_triggered else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
