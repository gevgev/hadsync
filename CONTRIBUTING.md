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
pytest tests/          # 43 unit tests, no HA connection required
pytest tests/unit/     # unit tests only
```

Unit tests use no live HA instance. If you change `ha_ws.py`, please also test manually against a real HA instance — the WebSocket API has version-specific behavior that mocks cannot fully capture.

## HA version compatibility

hadsync is tested against **Home Assistant 2026.5**. Please note the HA version you tested against in your PR description.

> **Note:** The WS commands used differ from common documentation. See [HA API Notes](README.md#ha-api-notes) in the README before touching the WebSocket client.

## Code style

- Python 3.11+, type annotations throughout
- No comments describing *what* the code does — only *why* when non-obvious
- Keep modules focused: CLI routing lives in `cli.py`, HA communication in `ha_ws.py` / `ha_rest.py`, etc.

## Reporting bugs

Please use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) and include your HA version — it matters for reproducing WS API issues.
