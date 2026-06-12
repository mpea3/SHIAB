"""Module discovery, loading, and registry for SHIAB."""

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Any

from app.config import AppConfig
from app.modules.base import Module

logger = logging.getLogger("shiab.loader")


class ModuleRegistry:
    """Holds all discovered module instances, keyed by name."""

    def __init__(self):
        self._modules: dict[str, Module] = {}

    def register(self, module: Module) -> None:
        self._modules[module.name] = module

    def get(self, name: str) -> Module | None:
        return self._modules.get(name)

    def get_enabled(self) -> list[Module]:
        return [m for m in self._modules.values() if m.enabled]

    def get_all(self) -> list[Module]:
        return list(self._modules.values())


def _load_module_from_file(py_file: Path, config: AppConfig) -> Module | None:
    """Dynamically import a Python file and find the Module subclass in it."""
    try:
        spec = importlib.util.spec_from_file_location(
            f"shiab_module_{py_file.stem}", str(py_file)
        )
        if spec is None or spec.loader is None:
            logger.warning(f"Could not load spec for {py_file}")
            return None

        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Find the class that inherits from Module (but is not Module itself)
        module_class = None
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, Module) and obj is not Module:
                module_class = obj
                break

        if module_class is None:
            logger.warning(f"No Module subclass found in {py_file}")
            return None

        # Get module-specific config
        module_name = module_class.name
        mod_config: dict[str, Any] = {}
        if module_name in config.modules:
            mod_config = config.modules[module_name].settings

        instance = module_class(mod_config)

        # Apply enabled state from config
        if module_name in config.modules:
            instance.enabled = config.modules[module_name].enabled

        return instance

    except Exception as e:
        logger.error(f"Failed to load module from {py_file}: {e}")
        return None


async def load_all_modules(config: AppConfig, db_engine) -> ModuleRegistry:
    """Discover and load all built-in and external modules."""
    registry = ModuleRegistry()

    # Built-in modules
    builtin_dir = Path(__file__).parent
    exclude = {"base.py", "loader.py", "__init__.py"}

    for py_file in sorted(builtin_dir.glob("*.py")):
        if py_file.name in exclude:
            continue
        instance = _load_module_from_file(py_file, config)
        if instance:
            await instance.on_startup(db_engine)
            registry.register(instance)
            logger.info(f"Loaded built-in module: {instance.name}")

    # External modules
    ext_dir = Path(config.modules_external_dir)
    if ext_dir.exists():
        for py_file in sorted(ext_dir.glob("*.py")):
            instance = _load_module_from_file(py_file, config)
            if instance:
                await instance.on_startup(db_engine)
                registry.register(instance)
                logger.info(f"Loaded external module: {instance.name}")

    return registry
