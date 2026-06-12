"""SHIAB configuration loader. Reads config.yaml into validated Pydantic models."""

import os
import shutil
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    path: str = "data/shiab.db"


class ThemeConfig(BaseModel):
    active: str = "default"


class AuthConfig(BaseModel):
    enabled: bool = False
    password: str = ""


class ModuleConfig(BaseModel):
    enabled: bool = True
    settings: dict[str, Any] = {}


class AppConfig(BaseModel):
    name: str = "SHIAB"
    host: str = "0.0.0.0"
    port: int = 8000
    database: DatabaseConfig = DatabaseConfig()
    theme: ThemeConfig = ThemeConfig()
    auth: AuthConfig = AuthConfig()
    modules: dict[str, ModuleConfig] = {}
    modules_external_dir: str = "modules_external"


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """Load configuration from YAML file. Falls back to config.example.yaml."""
    config_file = Path(config_path)
    example_file = Path("config.example.yaml")

    if not config_file.exists() and example_file.exists():
        shutil.copy(example_file, config_file)

    if not config_file.exists():
        return AppConfig()

    with open(config_file, "r") as f:
        raw = yaml.safe_load(f) or {}

    # Flatten the 'app' key into top-level fields
    app_section = raw.get("app", {})
    database_section = raw.get("database", {})
    theme_section = raw.get("theme", {})
    auth_section = raw.get("auth", {})
    modules_section = raw.get("modules", {})

    # Parse module configs
    parsed_modules = {}
    for mod_name, mod_data in modules_section.items():
        if isinstance(mod_data, dict):
            parsed_modules[mod_name] = ModuleConfig(**mod_data)

    # Apply environment variable overrides (SHIAB_ prefix)
    host = os.environ.get("SHIAB_HOST", app_section.get("host", "0.0.0.0"))
    port = int(os.environ.get("SHIAB_PORT", app_section.get("port", 8000)))

    auth_enabled_env = os.environ.get("SHIAB_AUTH_ENABLED")
    if auth_enabled_env is not None:
        auth_enabled = auth_enabled_env.strip().lower() in ("1", "true", "yes", "on")
    else:
        auth_enabled = bool(auth_section.get("enabled", False))
    auth_password = os.environ.get("SHIAB_AUTH_PASSWORD", auth_section.get("password", ""))

    return AppConfig(
        name=app_section.get("name", "SHIAB"),
        host=host,
        port=port,
        database=DatabaseConfig(**database_section) if database_section else DatabaseConfig(),
        theme=ThemeConfig(**theme_section) if theme_section else ThemeConfig(),
        auth=AuthConfig(enabled=auth_enabled, password=str(auth_password)),
        modules=parsed_modules,
        modules_external_dir=raw.get("modules_external_dir", "modules_external"),
    )
