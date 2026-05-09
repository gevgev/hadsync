# hadsync

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Tested on HA 2026.5](https://img.shields.io/badge/Home%20Assistant-2026.5-41BDF5?logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)

**Home Assistant Dashboard Sync** — pull, edit, and push Lovelace dashboards as code.

HA stores Lovelace dashboard configs in its internal storage layer. There is no supported workflow for editing dashboards locally in a code editor, tracking changes with git, and pushing updates back safely. `hadsync` bridges that gap via the HA WebSocket API.

---

## Features

- Pull any or all Lovelace dashboards from a live HA instance to local YAML
- Push locally edited YAML back to HA — change summary, destructive-change warnings, explicit confirmation
- Three-phase validation (syntax → entity IDs → card schema) run before every push
- Diff local YAML vs live HA state with view-level change summary and optional unified diff
- Entity ID validation against a cached HA entity registry (621 entities on a typical instance)
- Card schema validation — 35 standard Lovelace card types, `custom:*` always allowed
- Watch mode — validates on every file save; optional auto-push when validation passes
- Status table — last pull/push timestamps and local change detection per dashboard
- **VS Code extension** — inline diagnostics, command palette, status bar, entity ID autocomplete
- Git-friendly: plain YAML files, one directory per dashboard named by `url_path`

## Installation

```bash
pip install hadsync          # once published to PyPI
```

Requires Python 3.11+.

### Install from source

**With uv — installs `hadsync` globally so it works from any directory:**

```bash
# production install (run from anywhere after this)
uv tool install /path/to/hadsync

# editable install — code changes take effect immediately, no reinstall needed
uv tool install --editable /path/to/hadsync

# update after pulling new commits (non-editable)
uv tool install --reinstall /path/to/hadsync
```

**With pip:**

```bash
pip install -e ".[dev]"
```

## Two-Repo Setup (Recommended)

hadsync is designed to keep two things separate:

- **`hadsync/`** — this repo ([github.com/gevgev/hadsync](https://github.com/gevgev/hadsync)), CLI tool source code only
- **`home-assistant-dashboards/`** — a dedicated repo for your dashboard YAML files

This means your dashboard history is independent of the tool version history, and you can share or back up dashboards without exposing tool internals.

## Quick Start

```bash
# 1. Set your HA long-lived access token
export HA_TOKEN=eyJ...

# 2. Create and enter your dashboards repo
mkdir home-assistant-dashboards && cd home-assistant-dashboards
git init

# 3. Initialize hadsync (creates .hadsync.yaml here, workspace defaults to .)
hadsync init

# 4. List available dashboards on your HA instance
hadsync list

# 5. Pull all dashboards to local YAML
hadsync pull

# 6. Edit in VS Code (or any editor)
code .

# 7. Validate before pushing
hadsync validate

# 8. Push back to HA
hadsync push
```

Alternatively, keep `.hadsync.yaml` anywhere and point to the dashboards folder via env var:

```bash
export HA_TOKEN=eyJ...
export HADSYNC_WORKSPACE=~/home-assistant-dashboards
hadsync pull   # works from any directory
```

## Configuration

`hadsync init` creates `.hadsync.yaml` in the current directory:

```yaml
ha_url: http://homeassistant.local:8123
ha_token: ${HA_TOKEN}          # env var reference — never store the token literally
workspace: .                   # path to dashboard YAML files; defaults to current directory

pull:
  refresh_entities: true       # refresh entity cache on every pull
  dashboards: all              # or list: [lovelace, battery-status]

push:
  require_validation: true     # block push on validation errors
  confirm: true                # ask for confirmation before each push

validation:
  warn_on_unknown_entities: true        # Phase 2: warn vs error for unknown entity IDs
  entity_cache_max_age_days: 7          # warn if entity cache is older than this
  custom_card_types: []                 # Phase 3: extra type prefixes treated as valid
                                        # e.g. ["my-custom:"] alongside custom:*
```

### Environment Variables

| Variable | Description |
|---|---|
| `HA_TOKEN` | HA long-lived access token (referenced as `${HA_TOKEN}` in config) |
| `HADSYNC_WORKSPACE` | Override the workspace directory at runtime — takes priority over config |

The token is always referenced via an environment variable. Never embed it in the config file.

## Commands

| Command | Description |
|---|---|
| `hadsync init` | Interactive setup: URL, token env var, workspace dir |
| `hadsync list` | List all storage-mode dashboards on the HA instance |
| `hadsync pull [ID]` | Pull one or all dashboards from HA to local YAML; refreshes entity cache |
| `hadsync push [ID]` | Push local YAML to HA — validates (P1+P2+P3), shows change summary, confirms |
| `hadsync push [ID] --dry-run` | Show what would be sent without pushing |
| `hadsync diff [ID]` | Compare local vs HA — view-level change summary |
| `hadsync diff [ID] --show` | As above, plus coloured unified diff |
| `hadsync validate [ID]` | Run Phase 1+2+3 validation without pushing |
| `hadsync watch [ID]` | Watch for file saves and validate automatically |
| `hadsync watch [ID] --auto-push` | Watch and push to HA when validation passes |
| `hadsync status` | Table: last pull, last push, local change state per dashboard |
| `hadsync entities refresh` | Fetch all entity IDs from HA and update local cache |
| `hadsync entities list [filter]` | List cached entities, filtered by domain or friendly name |
| `hadsync config show` | Print resolved config (token masked, workspace source shown) |
| `hadsync config set KEY VALUE` | Set a config value |

**Global flags:** `--dry-run`, `--verbose / -v`, `--quiet / -q`, `--yes / -y`, `--json-output`, `--config PATH`

## Validation

`hadsync validate` (and pre-push validation in `hadsync push`) runs three phases:

| Phase | What it checks |
|---|---|
| 1 — Syntax & structure | YAML parse errors (with line numbers), `views` key present and a list, no non-mapping view entries |
| 2 — Entity IDs | Every `entity:` / `entities:` reference checked against `.ha-entities.json` cache; warns on unknowns; skipped if cache absent |
| 3 — Card schema | Each card's `type` is a known standard type; required fields are present; `custom:*` cards always pass |

Phase 2 is silently skipped if the entity cache doesn't exist yet — run `hadsync entities refresh` to enable it. Phase 3 warns on unknown types rather than blocking, so HACS cards never cause failures.

## Workspace Layout

```
home-assistant-dashboards/      # dashboards repo — committed to git
  .hadsync.yaml                 # connection config (workspace: .)
  .gitignore                    # excludes state/cache files
  battery-status/
    lovelace.yaml
  lovelace-cameras/
    lovelace.yaml
  dashboard-security/
    lovelace.yaml
  ...                           # one directory per dashboard (named by url_path)
```

Files excluded from git (auto-added to `.gitignore` by `hadsync init`):
- `.hadsync-state.json` — last pull/push timestamps per dashboard
- `.ha-entities.json` — entity ID cache (refreshed on every pull)

## Development

```bash
# Install globally so hadsync works from any directory
uv tool install --editable /path/to/hadsync

# Install dev dependencies for running tests
uv sync --extra dev
uv run pytest tests/

# Run against a real HA instance
export HA_TOKEN=eyJ...
hadsync list
```

## VS Code Extension

The `vscode-hadsync/` directory contains a VS Code extension that wraps the CLI.

**Install:**
```bash
cd vscode-hadsync
npm install && npm run compile
# Then: VS Code → Extensions → "..." → Install from VSIX
# Or press F5 to open an Extension Development Host
```

**Features:**
- **Inline diagnostics** — validates every `lovelace.yaml` on save; errors and warnings appear in the Problems panel and as editor squiggles
- **Command palette** (`Cmd+Shift+P`) — pull, push (with confirmation), validate, diff, status, list, entities refresh/search
- **Status bar** — shows last pull time or modified-dashboard count; click for full status table
- **Entity autocomplete** — `entity: ` triggers completions from `.ha-entities.json` with friendly name and domain

**Settings:** `hadsync.executablePath`, `hadsync.validateOnSave` (default: true), `hadsync.autoPushOnSave` (default: false)

## Implementation Status

| Phase | Description | Status |
|---|---|---|
| 1 — Core CLI | pull / push / validate / diff / status / state tracking | ✅ Complete |
| 2 — Entity Validation | entity cache, entity ID existence checks in YAML | ✅ Complete |
| 3 — Schema Validation & Watch | card type schema, watch mode, auto-push, enhanced diff | ✅ Complete |
| 4 — VS Code Extension | palette commands, inline diagnostics, entity autocomplete | ✅ Complete |

## HA API Notes

Tested against **Home Assistant 2026.5**. Key WS commands used:

| Operation | Command |
|---|---|
| List dashboards | `get_panels` (filter `component_name=lovelace`) |
| Fetch dashboard config | `lovelace/config` with `url_path` |
| Save dashboard config | `lovelace/config/save` with `url_path` |
| Fetch entity list | `GET /api/states` (REST) |

> **Note:** The design document references `lovelace/dashboards` and `lovelace/save_config` — these commands do not exist in HA 2026.5. The correct commands are listed above.

## License

MIT
