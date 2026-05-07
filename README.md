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
# or from source:
pip install -e .
```

Requires Python 3.11+.

## Quick Start

```bash
# 1. Set your HA long-lived access token
export HA_TOKEN=eyJ...

# 2. Initialize — connects to HA and creates .hadsync.yaml
hadsync init

# 3. List available dashboards
hadsync list

# 4. Pull all dashboards to local YAML
hadsync pull

# 5. Edit in VS Code (or any editor)
code ha-dashboards/

# 6. Validate before pushing
hadsync validate

# 7. Push back to HA
hadsync push
```

## Configuration

`hadsync init` creates `.hadsync.yaml` in the current directory:

```yaml
ha_url: http://homeassistant.local:8123
ha_token: ${HA_TOKEN}          # env var reference — never store the token literally
workspace: ./ha-dashboards

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
ha-dashboards/                  # committed to git
  .hadsync.yaml                 # connection config
  .gitignore                    # auto-generated (excludes state/cache files)
  lovelace/
    lovelace.yaml               # Overview dashboard
  battery-status/
    lovelace.yaml
  lovelace-cameras/
    lovelace.yaml
  ...
```

Files excluded from git (listed in `.gitignore`):
- `.hadsync-state.json` — sync state (last pull time, HA version)
- `.ha-entities.json` — entity ID cache

## Development

```bash
# Install with dev dependencies
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
| 1 — Core CLI | pull / push / validate / diff / state tracking | 🔨 In progress |
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
