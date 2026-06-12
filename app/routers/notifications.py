"""Notification system - in-app alerts and messages."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func, select, update

from app.database import get_session_factory
from app.models import Notification

logger = logging.getLogger("shiab.notifications")

router = APIRouter()


async def create_notification(
    title: str,
    message: str,
    level: str = "info",
    module_name: str | None = None,
) -> int:
    """Create a notification record and return its ID. Safe to call from anywhere."""
    factory = get_session_factory()
    async with factory() as session:
        notif = Notification(
            title=title,
            message=message,
            level=level,
            module_name=module_name,
        )
        session.add(notif)
        await session.commit()
        await session.refresh(notif)
        logger.info(f"Notification [{level}]: {title}")
        return notif.id


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    """Render the notifications page."""
    templates = request.app.state.templates
    config = request.app.state.config

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Notification).order_by(Notification.created_at.desc()).limit(200)
        )
        notifications = result.scalars().all()

    return templates.TemplateResponse(
        request,
        "notifications.html",
        {
            "notifications": notifications,
            "theme": config.theme.active,
            "app_name": config.name,
        },
    )


@router.get("/api/notifications")
async def list_notifications(limit: int = 50, unread_only: bool = False):
    """List recent notifications."""
    limit = max(1, min(limit, 200))
    factory = get_session_factory()
    async with factory() as session:
        query = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
        if unread_only:
            query = query.where(Notification.read.is_(False))
        result = await session.execute(query)
        notifications = result.scalars().all()

    return [_notif_to_dict(n) for n in notifications]


@router.get("/api/notifications/unread-count")
async def unread_count():
    """Get count of unread notifications for the badge."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.read.is_(False))
        )
        count = result.scalar_one()
    return {"count": count}


@router.post("/api/notifications/{notif_id}/read")
async def mark_read(notif_id: int):
    """Mark a notification as read."""
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            update(Notification).where(Notification.id == notif_id).values(read=True)
        )
        await session.commit()
    return {"status": "ok", "id": notif_id}


@router.post("/api/notifications/read-all")
async def mark_all_read():
    """Mark all notifications as read."""
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(update(Notification).values(read=True))
        await session.commit()
    return {"status": "ok"}


@router.delete("/api/notifications/{notif_id}")
async def delete_notification(notif_id: int):
    """Delete a notification."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Notification).where(Notification.id == notif_id)
        )
        notif = result.scalar_one_or_none()
        if not notif:
            return JSONResponse({"error": "Not found"}, status_code=404)
        await session.delete(notif)
        await session.commit()
    return {"status": "deleted", "id": notif_id}


@router.post("/api/notifications")
async def create_notification_api(request: Request):
    """Manually create a notification."""
    body = await request.json()
    title = body.get("title", "").strip()
    if not title:
        return JSONResponse({"error": "title is required"}, status_code=400)

    notif_id = await create_notification(
        title=title,
        message=body.get("message", ""),
        level=body.get("level", "info"),
        module_name=body.get("module_name"),
    )
    return {"id": notif_id, "status": "created"}


def _notif_to_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "level": n.level,
        "read": n.read,
        "module_name": n.module_name,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }
