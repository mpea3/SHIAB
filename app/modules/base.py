"""Abstract base class for all SHIAB modules."""

from abc import ABC, abstractmethod
from typing import Any

from fastapi import APIRouter


class Module(ABC):
    """Base class all SHIAB modules must inherit from.

    To create a module:
    1. Create a Python file in app/modules/ or modules_external/
    2. Define a class that inherits from Module
    3. Set the class attributes (name, display_name, etc.)
    4. Implement get_data() to return widget data
    5. Optionally implement get_routes() for custom API endpoints
    """

    # Module metadata - override in subclass
    name: str = ""
    display_name: str = ""
    description: str = ""
    version: str = "0.1.0"
    icon: str = ""

    # Widget configuration
    widget_template: str = ""  # e.g. "widgets/weather.html"
    widget_size: str = "medium"  # "small", "medium", "large"
    refresh_interval: int = 60  # seconds between auto-refresh

    def __init__(self, config: dict[str, Any]):
        """Initialize with module-specific config from config.yaml."""
        self.config = config
        self.enabled = True

    @abstractmethod
    async def get_data(self) -> dict[str, Any]:
        """Return data dict to be passed to the widget template.

        Must handle errors gracefully - return {"error": True, "error_message": "..."}
        rather than raising exceptions.
        """
        ...

    def get_routes(self) -> APIRouter | None:
        """Optionally return a FastAPI APIRouter with custom endpoints.

        The router will be mounted at /api/modules/{self.name}/
        """
        return None

    async def on_startup(self, db_engine) -> None:
        """Called once during app startup. Use for setup tasks."""
        pass

    async def on_enable(self) -> None:
        """Called when the module is enabled at runtime."""
        pass

    async def on_disable(self) -> None:
        """Called when the module is disabled at runtime."""
        pass

    def get_config_schema(self) -> dict[str, dict]:
        """Return a dict describing configurable fields for the settings UI.

        Format: {"field_name": {"type": "string", "label": "API Key", "required": True}}
        """
        return {}
