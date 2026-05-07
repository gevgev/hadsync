# hadsync

**Home Assistant Dashboard Sync** — pull, edit, and push Lovelace dashboards as code.

HA stores Lovelace dashboard configs in its internal storage layer. There is no supported workflow for editing dashboards locally in a code editor, tracking changes with git, and pushing updates back safely. `hadsync` bridges that gap via the HA WebSocket API.

---

## Features

- Pull any or all Lovelace dashboards from a live HA instance to local YAML
- Push locally edited YAML back to HA with pre-push validation
- Diff local state vs live HA state before pushing
- Entity ID validation against a cached HA entity registry (Phase 2)
- Git-friendly: plain YAML files that work naturally with version control

## Installation

```bash
pip install hadsync          # once published to PyPI
```

Requires Python 3.11+.

### Install from source

```bash
# with pip
pip install -e ".[dev]"

# with uv (faster, manages virtualenv automatically)
uv sync --extra dev
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
  refresh_entities: true
  dashboards: all              # or list: [lovelace, battery-status]

push:
  require_validation: true
  confirm: true

validation:
  warn_on_unknown_entities: true
  entity_cache_max_age_days: 7
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
| `hadsync list` | List all dashboards on the HA instance |
| `hadsync pull [ID]` | Pull one or all dashboards from HA to local YAML |
| `hadsync push [ID]` | Push local YAML to HA (validates first, asks confirmation) |
| `hadsync diff [ID]` | Compare local YAML vs current HA state |
| `hadsync validate [ID]` | Run validation on local YAML without pushing |
| `hadsync status` | Show sync status for all dashboards |
| `hadsync entities refresh` | Refresh the local entity cache from HA |
| `hadsync entities list [filter]` | List cached entities |
| `hadsync config show` | Print resolved config (token masked) |

**Global flags:** `--dry-run`, `--verbose / -v`, `--quiet / -q`, `--yes / -y`, `--json-output`, `--config PATH`

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
# Install with dev dependencies (uv — recommended)
uv sync --extra dev

# or with pip
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run against a real HA instance
export HA_TOKEN=eyJ...
hadsync list
```

## Implementation Status

| Phase | Description | Status |
|---|---|---|
| 1 — Core CLI | pull / push / validate / diff / status / state tracking | ✅ Complete |
| 2 — Entity Validation | entity cache, ID validation in YAML | Planned |
| 3 — Schema Validation & Watch | Lovelace card schema, watch mode | Planned |
| 4 — VS Code Extension | palette commands, inline diagnostics | Planned |

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
