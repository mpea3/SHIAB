"""Historical sensor data API - time-series readings for Chart.js graphs."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import delete, func, select

from app.database import get_session_factory
from app.models import SensorReading

logger = logging.getLogger("shiab.history")

router = APIRouter(prefix="/api/history")


@router.get("/{module_name}/{key}")
async def get_history(module_name: str, key: str, hours: int = 24, points: int = 120):
    """Get historical readings for a module/key combination.

    Uses SQL-level row counting to decide whether to subsample, and fetches
    at most ``points`` evenly-spaced rows so memory stays bounded.
    """
    hours = max(1, min(hours, 168))
    points = max(10, min(points, 500))

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    factory = get_session_factory()
    async with factory() as session:
        # Fast count to decide strategy
        count_result = await session.execute(
            select(func.count())
            .select_from(SensorReading)
            .where(
                SensorReading.module_name == module_name,
                SensorReading.key == key,
                SensorReading.timestamp >= since,
            )
        )
        total = count_result.scalar_one()

        if total == 0:
            return {"module": module_name, "key": key, "readings": [], "hours": hours}

        if total <= points:
            # Few enough rows — return them all
            result = await session.execute(
                select(SensorReading.timestamp, SensorReading.value)
                .where(
                    SensorReading.module_name == module_name,
                    SensorReading.key == key,
                    SensorReading.timestamp >= since,
                )
                .order_by(SensorReading.timestamp)
            )
        else:
            # Subsample: pick every Nth row using a modulo on rowid
            step = max(1, total // points)
            result = await session.execute(
                select(SensorReading.timestamp, SensorReading.value)
                .where(
                    SensorReading.module_name == module_name,
                    SensorReading.key == key,
                    SensorReading.timestamp >= since,
                    SensorReading.id % step == 0,
                )
                .order_by(SensorReading.timestamp)
                .limit(points)
            )

        rows = result.all()

    return {
        "module": module_name,
        "key": key,
        "hours": hours,
        "readings": [
            {"timestamp": row.timestamp.isoformat(), "value": row.value}
            for row in rows
        ],
    }


@router.get("/{module_name}")
async def get_module_keys(module_name: str):
    """List all tracked keys for a module."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(SensorReading.key)
            .where(SensorReading.module_name == module_name)
            .distinct()
        )
        keys = [row[0] for row in result.all()]

    return {"module": module_name, "keys": keys}


@router.delete("/purge")
async def purge_old_data(days: int = 30):
    """Delete sensor readings older than N days."""
    days = max(1, min(days, 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            delete(SensorReading).where(SensorReading.timestamp < cutoff)
        )
        await session.commit()

    return {"status": "ok", "deleted": result.rowcount, "cutoff": cutoff.isoformat()}
