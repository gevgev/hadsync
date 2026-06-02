# Changelog

## [v0.2.4] — 2026-06-02

### Fixed

- **`hadsync push --yes` rejected when flag placed after subcommand** — `--yes` / `-y` was only wired to the global callback, so `hadsync push --yes <id>` (the form used by the VS Code extension) was rejected by typer. Added as a local option on `push`; both `hadsync --yes push` and `hadsync push --yes` now work. (Closes #5)
- **NULL / missing title crash in `hadsync status` sort** — dashboard entries with no title caused an unhandled `None` comparison during sort. Fixed with a safe fallback key.

### Added

- **Tests for CLI helpers** — `test_cli.py` covering `_panel_title_sort_key` and related helpers; `cli.py` gained a small testability helper extracted from the sort logic.

[v0.2.4]: https://github.com/gevgev/hadsync/releases/tag/v0.2.4

---

## [v0.2.3] — 2026-05-11

### Fixed

- **False-positive "modified" in `hadsync status` after a clean pull** — macOS APFS can commit a file's mtime a few microseconds after Python records `last_pull`, making `mtime > last_pull` by a sub-second amount even though the pull itself wrote the file. Fixed by comparing timestamps at whole-second granularity: a difference of less than one second means the pull wrote the file, not a user edit. Applied in `hadsync status`, `hadsync diff` conflict detection, and the VS Code status bar.

[v0.2.3]: https://github.com/gevgev/hadsync/releases/tag/v0.2.3

---

## [v0.2.2] — 2026-05-10

### Fixed — VS Code Extension

- **Stale diagnostics after external pull** — Problems panel no longer retains old errors after `hadsync pull` is run from the terminal. A `FileSystemWatcher` on `**/lovelace.yaml` now re-validates automatically when any file changes on disk, regardless of whether the change came from VS Code or an external process.
- **Incorrect "N modified" in status bar** — The status bar was counting every dashboard that had never been pushed as "modified", showing e.g. `13 modified` immediately after a clean pull. Fixed to use the same mtime-vs-last_pull comparison as `hadsync status` in the CLI — "modified" now means the local file was actually edited since the last pull.

[v0.2.2]: https://github.com/gevgev/hadsync/releases/tag/v0.2.2

---

## [v0.2.1] — 2026-05-10

### Added — Phase 1b (Conflict Detection)

- **`hadsync diff` conflict detection** — stores a hash of the HA config at every pull; diff now classifies each divergence into one of four verdicts:
  - **CONFLICT** — both local and HA changed since last pull (shown in red with explicit next-step options)
  - **HA changed only** — warns and suggests `hadsync pull <id>`
  - **Local changed only** — warns and suggests `hadsync push <id>`
  - **No baseline** — generic message when dashboard was never pulled with the new hash tracking
- **Pull timestamp in diff output** — `Last pull: 2026-05-10 18:19  (2h ago)` shown for each dashboard
- **Annotated change summary** — HA and local card counts now show `← changed since pull` or `(unchanged since pull)` tags
- **`ha_config_hash`** field in `.hadsync-state.json` — 16-char SHA-256 prefix of the normalized HA config stored on every pull; enables HA-side change detection without keeping a full config snapshot

### Fixed

- **Error handling gaps (community review)** — VS Code extension now shows `showErrorMessage()` popups on command failure; detects `hadsync not found` at activation with an Open Settings link; `onDidSaveTextDocument` wrapped in try/catch; 60-second subprocess timeout prevents VS Code freeze
- **Python error messages** — `ha_ws.py` now distinguishes connection refused, DNS failure, timeout, and auth_invalid with targeted, actionable messages including next-step hints (e.g. where to generate a long-lived token in HA)
- **Watch mode resilience** — `watcher.py` event handler wrapped in try/catch so an unexpected crash no longer silently kills the watchdog observer thread

[v0.2.1]: https://github.com/gevgev/hadsync/releases/tag/v0.2.1

---

## [v0.2.0] — 2026-05-09

Phases 2, 3, and 4 complete. All four design phases are now implemented.

### Added — Phase 2 (Entity Validation)

- **`hadsync entities refresh`** — fetches all entity states from HA `/api/states` and writes `.ha-entities.json`
- **`hadsync entities list [filter]`** — lists cached entities with domain and friendly name, filtered by substring
- **Entity ID extraction** — recursive walk of any Lovelace config depth; handles `entity:`, `entities:` (strings and dicts), conditional conditions, stack nesting, picture-elements, and any other nesting pattern
- **Phase 2 validation** — unknown entity IDs reported with line numbers; silently skipped if cache is absent (no friction before first `entities refresh`)
- **Cache age warning** — warns when entity cache exceeds `validation.entity_cache_max_age_days` (default: 7)
- **`validation.warn_on_unknown_entities`** config flag — controls whether unknown IDs are warnings (default) or errors that block push

### Added — Phase 3 (Schema Validation & Watch)

- **`hadsync watch [ID] [--auto-push]`** — watches workspace for `lovelace.yaml` saves; runs Phase 1+2+3 validation on every change; pushes to HA automatically when validation passes if `--auto-push` is set
- **Phase 3 card schema validation** — 35 standard Lovelace card types with required-field checks; `custom:*` always passes; unknown non-custom types warn rather than block; extra prefixes configurable via `validation.custom_card_types`
- **Enhanced `hadsync diff`** — view-by-view change summary (`+ added`, `- removed`, `~ N cards changed`) shown before the optional unified diff
- **`validation.custom_card_types`** config field — list of additional type prefixes treated as valid alongside `custom:*`

### Added — Phase 4 (VS Code Extension)

- **`vscode-hadsync/`** — VS Code extension written in TypeScript; activates on any workspace containing `.hadsync.yaml`
- **11 palette commands** (`Cmd+Shift+P`): pull (all / active), push (all / active, with confirmation dialog), validate (all / active), diff, status, list, entities refresh, entities search
- **Inline diagnostics** — on `lovelace.yaml` save, runs `hadsync --json-output validate`; errors and warnings appear in the Problems panel and as editor squiggles with correct line numbers
- **Status bar** — bottom-left item shows last pull time or modified-dashboard count; reads `.hadsync-state.json` directly; click opens status table
- **Entity ID autocomplete** — completion items from `.ha-entities.json` triggered by `entity: ` and list item patterns; includes friendly name and domain in detail
- **Context menu** — validate / push / diff available on right-click in any `lovelace.yaml` editor
- **Settings**: `hadsync.executablePath`, `hadsync.validateOnSave` (default: true), `hadsync.autoPushOnSave` (default: false)

### Changed

- **`hadsync validate --json-output`** — emits structured JSON (per-dashboard file path, passed flag, issue list with severity/message/line); used by the VS Code extension for diagnostics; human output unchanged when flag is absent
- **Validation pipeline** — `hadsync validate` and `hadsync push` pre-push validation now run Phase 1 + Phase 2 + Phase 3 in sequence
- **`hadsync diff`** — now includes view-level summary before optional unified diff

### Notes

- Tested against **Home Assistant 2026.5.0**
- VS Code extension requires `hadsync` on PATH or `hadsync.executablePath` setting; `HA_TOKEN` must be in the environment VS Code inherits

---

## [v0.1.0] — 2026-05-08

Initial release. Phase 1 (Core CLI) complete.

### Added

- **`hadsync init`** — interactive setup: HA URL, token env var (with validation to catch pasted token values), workspace directory. Tests live HA connection.
- **`hadsync list`** — discovers all storage-mode Lovelace dashboards on the HA instance.
- **`hadsync pull [ID]`** — downloads one or all dashboards from HA as local YAML; auto-refreshes entity cache (`.ha-entities.json`); skips strategy-based dashboards with a warning.
- **`hadsync push [ID]`** — uploads local YAML to HA with layered safety: pre-push validation, no-op guard (skips if already in sync), change summary (view/card counts), destructive-change warnings, explicit per-dashboard confirmation, and `--dry-run` mode.
- **`hadsync validate [ID]`** — standalone YAML validation (syntax + structure) with PASS / WARN / FAIL per dashboard and line numbers on errors. Safe for CI pipelines — no HA connection required.
- **`hadsync status`** — sync status table: last pull time, last push time, local state (clean / modified / never pulled). No HA connection required.
- **`hadsync diff [ID] [--show]`** — compares local YAML against live HA state. `--show` renders a coloured unified diff (red = HA, green = local).
- **`hadsync config show`** — displays resolved config with masked token and workspace source.
- **`HADSYNC_WORKSPACE` env var** — overrides the workspace directory at runtime without editing config.

### Notes

- Tested against **Home Assistant 2026.5.0**.
- The HA WebSocket commands referenced in common documentation (`lovelace/dashboards`, `lovelace/save_config`) do not exist in HA 2026.5. This release uses the correct equivalents: `get_panels` (filtered by `component_name=lovelace`) and `lovelace/config/save`.
- Strategy-based dashboards (auto-generated by HA, e.g. the default Overview using `original-states` strategy) are detected during pull and skipped — they cannot be meaningfully round-tripped as static YAML.

[v0.2.0]: https://github.com/gevgev/hadsync/releases/tag/v0.2.0
[v0.1.0]: https://github.com/gevgev/hadsync/releases/tag/v0.1.0
