"""Calendar module - manages and displays upcoming events."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.database import get_session_factory
from app.models import CalendarEvent
from app.modules.base import Module


class CalendarModule(Module):
    name = "calendar"
    display_name = "Calendar"
    description = "Track and display upcoming events"
    icon = "&#128197;"
    widget_template = "widgets/calendar.html"
    widget_size = "medium"
    refresh_interval = 120

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.max_upcoming = config.get("max_upcoming", 5)

    async def get_data(self) -> dict[str, Any]:
        try:
            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    select(CalendarEvent)
                    .where(CalendarEvent.start_time >= datetime.now(tz=timezone.utc))
                    .order_by(CalendarEvent.start_time)
                    .limit(self.max_upcoming)
                )
                events = result.scalars().all()

                upcoming = []
                for event in events:
                    upcoming.append({
                        "id": event.id,
                        "title": event.title,
                        "description": event.description,
                        "start_time": event.start_time.isoformat(),
                        "end_time": event.end_time.isoformat() if event.end_time else None,
                        "all_day": event.all_day,
                    })

                return {
                    "upcoming_events": upcoming,
                    "today": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
                    "max_upcoming": self.max_upcoming,
                }
        except Exception as e:
            return {"error": True, "error_message": str(e)}

    def get_routes(self) -> APIRouter:
        router = APIRouter()

        @router.post("/events")
        async def create_event(request: Request):
            body = await request.json()
            title = body.get("title")
            if not title:
                return JSONResponse({"error": "Title is required"}, status_code=400)

            try:
                start_time = datetime.fromisoformat(body["start_time"])
            except (KeyError, ValueError):
                return JSONResponse({"error": "Invalid or missing start_time"}, status_code=400)
            try:
                end_time = datetime.fromisoformat(body["end_time"]) if body.get("end_time") else None
            except ValueError:
                return JSONResponse({"error": "Invalid end_time format"}, status_code=400)

            factory = get_session_factory()
            async with factory() as session:
                event = CalendarEvent(
                    title=title,
                    description=body.get("description"),
                    start_time=start_time,
                    end_time=end_time,
                    all_day=body.get("all_day", False),
                )
                session.add(event)
                await session.commit()
                await session.refresh(event)

                return {
                    "id": event.id,
                    "title": event.title,
                    "start_time": event.start_time.isoformat(),
                }

        @router.delete("/events/{event_id}")
        async def delete_event(event_id: int):
            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    select(CalendarEvent).where(CalendarEvent.id == event_id)
                )
                event = result.scalar_one_or_none()
                if not event:
                    return JSONResponse({"error": "Event not found"}, status_code=404)
                await session.delete(event)
                await session.commit()
                return {"status": "deleted", "id": event_id}

        return router

    def get_config_schema(self) -> dict[str, dict]:
        return {
            "max_upcoming": {
                "type": "number",
                "label": "Max upcoming events",
                "required": False,
            },
        }
