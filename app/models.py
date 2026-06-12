"""SHIAB database models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CalendarEvent(Base):
    """Calendar events for the Calendar module."""
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Setting(Base):
    """General key-value settings store."""
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)


class SensorReading(Base):
    """Time-series sensor data logged from modules (for historical graphs)."""
    __tablename__ = "sensor_readings"

    __table_args__ = (
        Index("ix_sensor_module_key_ts", "module_name", "key", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_name: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class Notification(Base):
    """In-app notifications and alerts."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(20), default="info")  # info, success, warning, error
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    module_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )


class Automation(Base):
    """Automation rules: trigger condition → action."""
    __tablename__ = "automations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Trigger
    trigger_module: Mapped[str] = mapped_column(String(100))
    trigger_key: Mapped[str] = mapped_column(String(200))
    trigger_operator: Mapped[str] = mapped_column(String(20))  # gt, lt, gte, lte, eq, ne, contains
    trigger_value: Mapped[str] = mapped_column(String(500))
    # Action
    action_type: Mapped[str] = mapped_column(String(50))  # notify, webhook
    action_payload: Mapped[str] = mapped_column(Text, default="{}")
    # Cooldown
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300)
    last_triggered: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Scene(Base):
    """Saved scenes — named collections of device states to activate at once."""
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(10), default="🎬")
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
