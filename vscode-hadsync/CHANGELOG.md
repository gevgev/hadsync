# Changelog

## [0.2.6] — 2026-06-03

### Fixed

- **False-positive "modified" in status bar after `git pull`** — the extension status bar reads `.hadsync-state.json` which now stores a content hash at pull time; `hadsync status` uses hash comparison instead of mtime, so `git pull` re-writing identical YAML no longer shows spurious "N modified" in the status bar. (Closes #7)

---

## [0.2.4] — 2026-06-02

### Fixed

- **`hadsync push --yes` rejected when flag placed after subcommand** — the VS Code extension calls `hadsync push --yes <id>`; this form was previously rejected. Both placements now work. (Closes #5)

---

## [0.2.3] — 2026-05-11

### Fixed

- **False-positive "modified" after a clean pull** — macOS APFS can commit a file's mtime a few microseconds after Python records `last_pull`, causing `mtime > last_pull` even though the pull wrote the file. Fixed by comparing timestamps at whole-second granularity; sub-second differences are treated as a pull, not a user edit. Affects status bar and `hadsync status`.

---

## [0.2.2] — 2026-05-10

### Fixed

- **Stale diagnostics after external pull** — Problems panel no longer retains old errors after `hadsync pull` is run from the terminal. A `FileSystemWatcher` on `**/lovelace.yaml` now re-validates automatically when any file changes on disk, regardless of whether the change came from VS Code or an external process.
- **Incorrect "N modified" in status bar** — The status bar was counting every dashboard that had never been pushed as "modified". Fixed to use the same mtime-vs-last_pull comparison as `hadsync status` in the CLI.

---

## [0.2.1] — 2026-05-10

### Fixed

- **Error messages on command failure** — Commands now show `showErrorMessage()` popups instead of silently failing.
- **`hadsync not found` at activation** — Extension detects a missing executable at startup and shows a notification with an Open Settings link.
- **VS Code freeze on slow HA** — `onDidSaveTextDocument` handler is wrapped in try/catch; subprocess calls have a 60-second timeout.

---

## [0.2.0] — 2026-05-09

### Added (Phase 4 — Initial Release)

- 11 Command Palette commands: pull, push, validate, diff, status, list, entities refresh, entities search (all/active variants where applicable)
- **Inline diagnostics** — runs `hadsync --json-output validate` on every `lovelace.yaml` save; errors and warnings appear in the Problems panel with correct line numbers
- **Status bar** — shows last pull time or modified-dashboard count; reads `.hadsync-state.json` directly; click opens the status table
- **Entity autocomplete** — completion items from `.ha-entities.json` triggered by `entity: ` and list-item patterns
- **Context menu** — validate / push / diff available on right-click in any `lovelace.yaml` editor
- **Settings**: `hadsync.executablePath`, `hadsync.validateOnSave` (default: true), `hadsync.autoPushOnSave` (default: false)
