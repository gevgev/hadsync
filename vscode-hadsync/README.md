# hadsync VS Code Extension

VS Code integration for [hadsync](https://github.com/gevgev/hadsync) — Home Assistant Dashboard Sync.

Activates automatically in any workspace that contains a `.hadsync.yaml` file.

---

## Requirements

- The `hadsync` CLI must be installed and on your `PATH`:
  ```bash
  uv tool install --editable /path/to/hadsync
  ```
- `HA_TOKEN` environment variable must be set (inherited by VS Code from your shell)

---

## Features

### Command Palette (`Cmd+Shift+P`)

| Command | Description |
|---|---|
| `hadsync: Pull Dashboards from HA` | Pull all dashboards |
| `hadsync: Pull This Dashboard` | Pull the dashboard for the open lovelace.yaml |
| `hadsync: Push Dashboards to HA` | Push all (with confirmation dialog) |
| `hadsync: Push This Dashboard` | Push the active dashboard (with confirmation) |
| `hadsync: Validate All Dashboards` | Run full validation (Phase 1+2+3) |
| `hadsync: Validate This Dashboard` | Validate the active dashboard |
| `hadsync: Diff This Dashboard vs HA` | Show coloured diff in output panel |
| `hadsync: Show Sync Status` | Show last pull/push table |
| `hadsync: List HA Dashboards` | List all storage-mode dashboards on HA |
| `hadsync: Refresh Entity Cache` | Fetch entity IDs from HA |
| `hadsync: Search Entities` | Filter entity cache by domain or name |

### Inline Diagnostics

When a `lovelace.yaml` file is saved, hadsync runs Phase 1+2+3 validation and shows errors and warnings directly in the **Problems** panel (`Cmd+Shift+M`) and as squiggly underlines in the editor.

### Status Bar

The bottom-left status bar shows the last pull time and whether any dashboards have been locally modified since the last pull. Click it to show the full status table.

### Entity Autocomplete

Typing `entity: ` or `- ` inside a `lovelace.yaml` file triggers entity ID completions from the local `.ha-entities.json` cache. Run `hadsync: Refresh Entity Cache` to populate it.

---

## Settings

| Setting | Default | Description |
|---|---|---|
| `hadsync.executablePath` | `""` | Full path to hadsync binary. Leave blank to use PATH. |
| `hadsync.validateOnSave` | `true` | Validate automatically on every lovelace.yaml save. |
| `hadsync.autoPushOnSave` | `false` | Push to HA automatically after a clean validation on save. |

---

## Installation

```bash
# 1. Enter this directory
cd vscode-hadsync

# 2. Install dependencies and compile
npm install
npm run compile

# 3. Package into a .vsix file
npx @vscode/vsce package --no-dependencies
# → produces  hadsync-0.2.3.vsix  in this directory

# 4. Install in VS Code
code --install-extension hadsync-0.2.3.vsix
```

Restart VS Code. The extension activates automatically in any workspace containing `.hadsync.yaml`.

**VS Code UI alternative:** `Cmd+Shift+P` → `Extensions: Install from VSIX...` → select `hadsync-0.2.3.vsix`.

## Updating

After pulling new commits:

```bash
npm run compile
npx @vscode/vsce package --no-dependencies
code --install-extension hadsync-0.2.3.vsix
```

## Development

```bash
npm install
npm run watch   # recompiles on every TypeScript change
```

Press **F5** in VS Code (with this folder open) to launch an Extension Development Host — lets you test changes without installing the VSIX.
