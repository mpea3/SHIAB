"""Settings router - application and module settings page."""

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render the settings page."""
    registry = request.app.state.module_registry
    config = request.app.state.config
    templates = request.app.state.templates

    # Use cached theme list from startup
    available_themes = request.app.state.available_themes

    # Build module info for the settings form
    modules_info = []
    for module in registry.get_all():
        modules_info.append({
            "name": module.name,
            "display_name": module.display_name,
            "description": module.description,
            "enabled": module.enabled,
            "config": module.config,
            "config_schema": module.get_config_schema(),
        })

    return templates.TemplateResponse(request, "settings.html", {
        "config": config,
        "theme": config.theme.active,
        "available_themes": available_themes,
        "modules": modules_info,
        "app_name": config.name,
    })


@router.post("/settings", response_class=HTMLResponse)
async def save_settings(request: Request):
    """Process settings form submission."""
    config = request.app.state.config
    registry = request.app.state.module_registry
    form = await request.form()

    # Update theme
    new_theme = form.get("theme", config.theme.active)
    config.theme.active = new_theme

    # Update module enabled/disabled states and settings
    for module in registry.get_all():
        # Update enabled state
        field_name = f"module_{module.name}_enabled"
        module.enabled = field_name in form

        # Update module settings
        schema = module.get_config_schema()
        if schema:
            for setting_name, setting_info in schema.items():
                form_field_name = f"{module.name}_{setting_name}"

                # Handle boolean fields: check if checkbox is present
                if setting_info.get("type") == "boolean":
                    module.config[setting_name] = form_field_name in form
                # Handle other fields only if they appear in form
                elif form_field_name in form:
                    value = form.get(form_field_name, "")

                    # Handle password fields: only update if value is not empty
                    if setting_info.get("type") == "password":
                        if value.strip():  # Only update if not empty
                            module.config[setting_name] = value
                        # If empty, keep the old value (don't update)

                    # Handle number fields
                    elif setting_info.get("type") == "number":
                        try:
                            module.config[setting_name] = int(value) if value else 0
                        except ValueError:
                            module.config[setting_name] = 0
                    else:
                        # Text, select and other types
                        module.config[setting_name] = value

    # Write updated config back to config.yaml
    _save_config(config, registry)

    return RedirectResponse(url="/settings", status_code=303)


def _save_config(config, registry):
    """Write the current config state back to config.yaml."""
    modules_dict = {}
    for module in registry.get_all():
        modules_dict[module.name] = {
            "enabled": module.enabled,
            "settings": module.config,
        }

    output = {
        "app": {
            "name": config.name,
            "host": config.host,
            "port": config.port,
        },
        "database": {
            "path": config.database.path,
        },
        "theme": {
            "active": config.theme.active,
        },
        "auth": {
            "enabled": config.auth.enabled,
            "password": config.auth.password,
        },
        "modules": modules_dict,
    }

    with open("config.yaml", "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False)
