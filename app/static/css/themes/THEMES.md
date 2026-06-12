# Creating CSS Themes for SHIAB

SHIAB uses CSS custom properties (variables) for theming. To create a new theme, you only need to override the `:root` variables defined in the default theme.

## Quick Start

1. Create a new CSS file in `app/static/css/themes/` (e.g. `ocean.css`)
2. Override the CSS custom properties under `:root`
3. Set `theme.active` in `config.yaml` to your theme filename (without `.css`)

```yaml
theme:
  active: "ocean"
```

4. Restart SHIAB

## Available Variables

### Colors

| Variable | Purpose | Default (light) |
|---|---|---|
| `--color-bg` | Page background | `#f0f2f5` |
| `--color-surface` | Card/panel background | `#ffffff` |
| `--color-primary` | Primary accent colour | `#2563eb` |
| `--color-primary-hover` | Primary colour on hover | `#1d4ed8` |
| `--color-primary-light` | Light tint of primary (active nav, focus rings) | `#dbeafe` |
| `--color-text` | Main text colour | `#1f2937` |
| `--color-text-muted` | Secondary/dimmed text | `#6b7280` |
| `--color-text-inverse` | Text on primary-coloured backgrounds | `#ffffff` |
| `--color-border` | Borders and dividers | `#e5e7eb` |
| `--color-error` | Error text and icons | `#ef4444` |
| `--color-error-light` | Error background tint | `#fef2f2` |
| `--color-success` | Success/online indicators | `#22c55e` |
| `--color-success-light` | Success background tint | `#f0fdf4` |
| `--color-warning` | Warning text and icons | `#f59e0b` |
| `--color-warning-light` | Warning background tint | `#fffbeb` |

### Typography

| Variable | Purpose | Default |
|---|---|---|
| `--font-family` | Base font stack | `'Segoe UI', system-ui, ...` |
| `--font-size-xs` | Extra small text | `0.75rem` |
| `--font-size-sm` | Small text | `0.875rem` |
| `--font-size-base` | Body text | `1rem` |
| `--font-size-lg` | Large text | `1.25rem` |
| `--font-size-xl` | Extra large text | `1.5rem` |
| `--font-size-2xl` | Heading size | `2rem` |
| `--font-size-3xl` | Large value display | `3rem` |
| `--font-weight-normal` | Normal weight | `400` |
| `--font-weight-medium` | Medium weight | `500` |
| `--font-weight-semibold` | Semi-bold weight | `600` |
| `--font-weight-bold` | Bold weight | `700` |

### Spacing

| Variable | Purpose | Default |
|---|---|---|
| `--spacing-xs` | Tiny gaps | `0.25rem` |
| `--spacing-sm` | Small gaps | `0.5rem` |
| `--spacing-md` | Medium gaps | `1rem` |
| `--spacing-lg` | Large gaps | `1.5rem` |
| `--spacing-xl` | Extra large gaps | `2rem` |
| `--spacing-2xl` | Section spacing | `3rem` |

### Layout

| Variable | Purpose | Default |
|---|---|---|
| `--border-radius` | Card/panel corners | `0.75rem` |
| `--border-radius-sm` | Button/input corners | `0.375rem` |
| `--shadow` | Default card shadow | `0 1px 3px ...` |
| `--shadow-lg` | Elevated shadow | `0 4px 12px ...` |
| `--shadow-hover` | Hover state shadow | `0 8px 24px ...` |
| `--header-height` | Navigation bar height | `60px` |
| `--transition` | Default animation timing | `0.2s ease` |

## Example: Minimal Theme

```css
/* SHIAB Ocean Theme */
:root {
    --color-bg: #e8f4f8;
    --color-surface: #ffffff;
    --color-primary: #0891b2;
    --color-primary-hover: #0e7490;
    --color-primary-light: #cffafe;
    --color-text: #164e63;
    --color-text-muted: #64748b;
    --color-text-inverse: #ffffff;
    --color-border: #cbd5e1;
}
```

You only need to override the variables you want to change. Any variables you omit will fall back to the default theme values.

## Tips

- Look at `themes/dark.css` for a complete dark mode example that overrides colours and shadows.
- The dark theme only overrides colour and shadow variables; typography, spacing, and layout stay the same.
- Use browser dev tools to test changes live before saving your theme file.
- All widgets use the same CSS variables, so your theme applies consistently everywhere.
- Widget templates use standard CSS classes (`.widget-card`, `.widget-header`, `.widget-body`, etc.) documented in `dashboard.css`.
