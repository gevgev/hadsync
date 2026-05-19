# Project Guidelines

## ESPHome Workflows

- When flashing devices, always use `--no-logs` flag to prevent the command from hanging
- Verify ESPHome version compatibility before suggesting advanced YAML features like `!override` tags
- For dashboard YAML files (lovelace.yaml), map to 'home-assistant' file type, not generic 'yaml'
- Before editing any ESPHome YAML, check the device's framework (esp-idf or arduino) and the installed ESPHome version — only suggest features compatible with both; if unsure, ask first

## Home Assistant Deployment

- Confirm HA_TOKEN env var is set before attempting HA deployments
- Only use valid Lovelace card types (tile, button, entities, etc.) — verify before writing 'type: cover' or similar uncommon types
- Never commit files in gitignored folders; check `.gitignore` before staging

## Pre-Flight Checks

Before any deploy or flash action:

- Verify `HA_TOKEN` is exported (`echo $HA_TOKEN` — abort if empty)
- Confirm all Lovelace card types in the diff are valid (tile, button, entities, etc.)
- Ensure flash commands include `--no-logs`
- Check the target file is not in `.gitignore` before staging

Report any issues before proceeding.

## Verification Loops

- After framework-related YAML changes (esp-idf vs arduino), test compile before declaring done
- For bug fixes touching multiple files/labels (e.g., off-by-one arrays), grep for all occurrences first
- Before fixing any bug, grep the repo for all occurrences of the buggy pattern (same array indexing, same string, same function call) — list them all, then fix in one pass
