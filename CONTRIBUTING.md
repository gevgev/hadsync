# Contributing to hadsync

Contributions are welcome — bug reports, feature requests, and pull requests.

## Before you open a PR

- Check [open issues](https://github.com/gevgev/hadsync/issues) to avoid duplicate work
- For anything beyond a small fix, open an issue first to discuss the approach

## Development setup

```bash
git clone https://github.com/gevgev/hadsync.git
cd hadsync
uv tool install --editable .   # or: pip install -e ".[dev]"
pytest tests/
```

## Running tests

```bash
uv run pytest tests/       # full suite, no HA connection required
uv run pytest tests/unit/  # unit tests only
```

Unit tests use no live HA instance. If you change `ha_ws.py`, please also test manually against a real HA instance — the WebSocket API has version-specific behavior that mocks cannot fully capture.

## Branch and PR workflow

Every fix or feature — no matter how small — goes through a branch and pull request. No direct commits to `main`.

```
main                     ← protected; only receives squash-merges from PRs
  └─ fix/short-description    ← one branch per issue/feature
  └─ feat/short-description
```

1. Create a branch: `git checkout -b fix/short-description`
2. Make changes, run tests
3. Add a line to the `[Unreleased]` section of `CHANGELOG.md`
4. Push and open a PR — title should match `fix:` / `feat:` / `chore:` / `docs:` prefix
5. Assign the PR to the current open [milestone](https://github.com/gevgev/hadsync/milestones)
6. Squash-merge via GitHub UI; delete the branch after merge

CI runs the full test matrix (Python 3.11 / 3.12 / 3.13 + TypeScript compile) on every PR automatically.

## Release process

Releases are **batched** — multiple fixes accumulate on `main` before a version tag is pushed. The goal is one release per meaningful batch, not one per fix.

### Day-to-day (every merged PR)

Add a line to the `[Unreleased]` section at the top of `CHANGELOG.md`:

```markdown
## [Unreleased]

### Fixed
- Brief description of the fix (#issue-number)

### Added
- Brief description of the new feature (#issue-number)
```

Also add a line to `vscode-hadsync/CHANGELOG.md` if the VS Code extension behaviour changed.

### Cutting a release

When the `[Unreleased]` section has enough to be worth shipping:

1. Close the current [GitHub Milestone](https://github.com/gevgev/hadsync/milestones) — verify all planned issues are resolved or moved to the next milestone
2. Run the release script from the repo root:

```bash
python scripts/release.py 0.X.Y
```

The script will:
- Validate the working tree is clean and `[Unreleased]` is non-empty
- Bump `version` in `pyproject.toml` and `vscode-hadsync/package.json` / `package-lock.json`
- Rename `[Unreleased]` → `[v0.X.Y] — today` in both changelogs and insert the release link
- Re-add a fresh empty `[Unreleased]` section for the next batch
- Commit, tag `v0.X.Y`, push — the CI release workflow takes over from here

3. Create the next milestone on GitHub for the next batch (e.g., `v0.X+1.0`)

### What CI does on a version tag

- Runs the full test suite
- Publishes the Python package to [PyPI](https://pypi.org/project/hadsync/)
- Builds the VS Code extension `.vsix`
- Creates a GitHub Release with the changelog entry as body and the `.vsix` attached

### VS Code Marketplace (manual)

Marketplace publishing requires an Azure DevOps PAT. When you have one:

```bash
cd vscode-hadsync
npx @vscode/vsce publish --no-dependencies --pat <your-token>
```

## HA version compatibility

hadsync is tested against **Home Assistant 2026.5**. Please note the HA version you tested against in your PR description.

> **Note:** The WS commands used differ from common documentation. See [HA API Notes](README.md#ha-api-notes) in the README before touching the WebSocket client.

## Code style

- Python 3.11+, type annotations throughout
- No comments describing *what* the code does — only *why* when non-obvious
- Keep modules focused: CLI routing lives in `cli.py`, HA communication in `ha_ws.py` / `ha_rest.py`, etc.

## Reporting bugs

Please use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) and include your HA version — it matters for reproducing WS API issues.
