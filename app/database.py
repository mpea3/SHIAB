"""SHIAB database layer. Async SQLAlchemy with aiosqlite."""

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base

_engine = None
_session_factory = None


async def init_db(db_path: str = "data/shiab.db"):
    """Initialize the database engine and create all tables."""
    global _engine, _session_factory

    # Ensure the data directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    _engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Enable WAL mode for better concurrent read performance
        await conn.execute(text("PRAGMA journal_mode=WAL"))

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory. Must call init_db first."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _session_factory


async def get_session():
    """Async generator that yields a database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine():
    """Dispose of the database engine."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
