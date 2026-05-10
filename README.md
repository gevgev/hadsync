# hadsync

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Tested on HA 2026.5](https://img.shields.io/badge/Home%20Assistant-2026.5-41BDF5?logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)

**Home Assistant Dashboard Sync** — pull, edit, and push Lovelace dashboards as code.

HA stores Lovelace dashboard configs in its internal storage layer. There is no supported workflow for editing dashboards locally in a code editor, tracking changes with git, and pushing updates back safely. `hadsync` bridges that gap via the HA WebSocket API.

![hadsync VS Code extension — dashboard explorer, entity autocomplete, and sync status table](docs/vscode-screenshot.jpg)
*Dashboard explorer, entity ID autocomplete, and hadsync sync status — all in VS Code.*

![Hovering over an entity ID shows live state, last-changed time, and attributes from your running HA instance](docs/vscode-entities-screenshot.jpg)
*Hover any entity ID to see its live value and attributes, courtesy of the HA Config Helper extension.*

---

[Features](#features) · [Quick Start](#quick-start) · [Commands](#commands) · [In Action](#in-action) · [Conflict Detection](#conflict-detection) · [Validation](#validation) · [VS Code Extension](#vs-code-extension) · [Configuration](#configuration) · [Installation](#installation)

---

## Features

- Pull any or all Lovelace dashboards from a live HA instance to local YAML
- Push locally edited YAML back to HA — change summary, destructive-change warnings, explicit confirmation
- Three-phase validation (syntax → entity IDs → card schema) run before every push
- Diff local YAML vs live HA state — conflict detection, view-level summary, coloured unified diff
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
| `hadsync diff [ID]` | Compare local vs HA — conflict detection, pull timestamp, view-level summary |
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

## Conflict Detection

Every `hadsync pull` stores a hash of the HA config in `.hadsync-state.json`. `hadsync diff` uses this to classify divergences:

| Situation | HA hash | Local mtime | Verdict |
|---|---|---|---|
| Both changed since pull | changed | > last pull | **CONFLICT** — explicit next-step options shown |
| HA changed, local clean | changed | ≤ last pull | Suggests `hadsync pull <id>` |
| Local changed, HA untouched | same | > last pull | Suggests `hadsync push <id>` |
| Never pulled / old state | no hash | — | Diff shown without classification |

Example CONFLICT output:
```
battery-status
  Last pull: 2026-05-10 18:19  (2h ago)
  HA:    1 views, 5 cards  ← changed since pull
  Local: 1 views, 5 cards  ← modified since pull
    ~ Battery Status: content changed

  ✗  CONFLICT — both sides changed since last pull.
       hadsync push battery-status  — overwrite HA with local (discards HA edits)
       hadsync pull battery-status  — overwrite local with HA (discards local edits)
```

## In Action

### `hadsync diff` — conflict summary

![hadsync diff showing a CONFLICT: HA has 6 views 33 cards, local has 6 views 32 cards, both changed since last pull](docs/diff-conflict-summary.jpg)

*Both HA and local changed since the last pull — hadsync detects the conflict, identifies the modified view, and shows the two resolution options with their consequences.*

### `hadsync diff --show` — unified diff

![hadsync diff --show displaying the full coloured unified diff below the conflict summary](docs/diff-show-flag.jpg)

*The `--show` flag appends a full coloured unified diff beneath the conflict summary: red lines are what HA currently has, green lines are what your local file contains. Changes are shown at the YAML level so you can see exactly which card fields or view titles were edited on each side.*

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

### Installation (one-time)

```bash
# 1. Enter the extension directory
cd /path/to/hadsync/vscode-hadsync

# 2. Install Node dependencies and compile TypeScript
npm install
npm run compile        # produces vscode-hadsync/out/

# 3. Package into a .vsix installer file
npx @vscode/vsce package --no-dependencies
# → creates  vscode-hadsync/hadsync-0.1.0.vsix

# 4. Install in VS Code (command line — easiest)
code --install-extension hadsync-0.1.0.vsix
```

After step 4, restart VS Code. The extension activates automatically in any workspace folder that contains a `.hadsync.yaml` file.

**Alternative (VS Code UI):** `Cmd+Shift+P` → `Extensions: Install from VSIX...` → navigate to `vscode-hadsync/hadsync-0.1.0.vsix` → Open.

### Updating after CLI changes

Re-run steps 2–4 whenever you pull new commits to the hadsync CLI:

```bash
cd vscode-hadsync
npm run compile && npx @vscode/vsce package --no-dependencies
code --install-extension hadsync-0.1.0.vsix
```

### Features

- **Inline diagnostics** — validates every `lovelace.yaml` on save; errors and warnings appear in the Problems panel (`Cmd+Shift+M`) and as editor squiggles with line numbers
- **Command palette** (`Cmd+Shift+P`) — pull, push (with VS Code confirmation dialog), validate, diff, status, list, entities refresh/search
- **Status bar** — bottom-left shows last pull time or modified-dashboard count; click for full status table
- **Entity autocomplete** — typing `entity: ` triggers completions from `.ha-entities.json` with friendly name and domain
- **Right-click context menu** — validate / push / diff available directly in any `lovelace.yaml` editor

Pair hadsync with the [Home Assistant Config Helper](https://marketplace.visualstudio.com/items?itemName=keesschollaart.vscode-home-assistant) extension for a complete live editing experience: hover over any entity ID to see its **current state, last-changed timestamp, and attributes** pulled directly from your running HA instance — while hadsync validation ensures every referenced entity actually exists.

### Settings

| Setting | Default | Description |
|---|---|---|
| `hadsync.executablePath` | `""` | Full path to hadsync binary. Leave blank to use PATH. |
| `hadsync.validateOnSave` | `true` | Validate automatically when a lovelace.yaml is saved. |
| `hadsync.autoPushOnSave` | `false` | Push to HA automatically after a clean validation on save. |

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
