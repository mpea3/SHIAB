# External Modules

Place custom SHIAB module files in this directory. Each module is a single `.py` file containing a class that inherits from `Module`.

## Quick Start

1. Create a new `.py` file in this directory (e.g., `my_module.py`)
2. Import and inherit from the base module class:

```python
from app.modules.base import Module

class MyModule(Module):
    name = "my_module"
    display_name = "My Module"
    description = "A custom module"
    icon = "&#9889;"
    widget_template = "widgets/my_module.html"
    widget_size = "medium"
    refresh_interval = 60

    async def get_data(self):
        return {"message": "Hello from my module!"}
```

3. Create a matching widget template at `app/templates/widgets/my_module.html`
4. Add a config entry in `config.yaml`:

```yaml
modules:
  my_module:
    enabled: true
    settings: {}
```

5. Restart SHIAB

## Module API

- `name` -- Machine-readable name (used in URLs and config)
- `display_name` -- Human-readable name shown in the UI
- `description` -- One-line description
- `icon` -- HTML entity or emoji for the widget header
- `widget_template` -- Path to the Jinja2 template (relative to templates/)
- `widget_size` -- `"small"`, `"medium"`, or `"large"` (controls grid column span)
- `refresh_interval` -- Seconds between auto-refresh polls
- `get_data()` -- Async method that returns a dict of data for the template
- `get_routes()` -- Optional: return a FastAPI `APIRouter` for custom endpoints
- `get_config_schema()` -- Optional: return field definitions for the settings UI
