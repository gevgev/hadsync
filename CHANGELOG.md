# Changelog

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
