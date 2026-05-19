# Project Guidelines

## ESPHome Workflows

- When flashing devices, always use `--no-logs` flag to prevent the command from hanging
- Verify ESPHome version compatibility before suggesting advanced YAML features like `!override` tags
- For dashboard YAML files (lovelace.yaml), map to 'home-assistant' file type, not generic 'yaml'

## Home Assistant Deployment

- Confirm HA_TOKEN env var is set before attempting HA deployments
- Only use valid Lovelace card types (tile, button, entities, etc.) — verify before writing 'type: cover' or similar uncommon types
- Never commit files in gitignored folders; check `.gitignore` before staging

## Verification Loops

- After framework-related YAML changes (esp-idf vs arduino), test compile before declaring done
- For bug fixes touching multiple files/labels (e.g., off-by-one arrays), grep for all occurrences first
