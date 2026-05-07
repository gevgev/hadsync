from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_FILENAME = ".hadsync-state.json"


def _load(workspace: Path) -> dict:
    path = workspace / STATE_FILENAME
    if not path.exists():
        return {"dashboards": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"dashboards": {}}


def _save(workspace: Path, state: dict) -> None:
    path = workspace / STATE_FILENAME
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def record_pull(workspace: Path, url_path: str) -> None:
    state = _load(workspace)
    existing = state["dashboards"].get(url_path, {})
    state["dashboards"][url_path] = {
        **existing,
        "last_pull": datetime.now(timezone.utc).isoformat(),
    }
    _save(workspace, state)


def record_push(workspace: Path, url_path: str) -> None:
    state = _load(workspace)
    existing = state["dashboards"].get(url_path, {})
    state["dashboards"][url_path] = {
        **existing,
        "last_push": datetime.now(timezone.utc).isoformat(),
    }
    _save(workspace, state)


def get_dashboard_state(workspace: Path, url_path: str) -> dict:
    return _load(workspace)["dashboards"].get(url_path, {})


def get_all_states(workspace: Path) -> dict[str, dict]:
    return _load(workspace).get("dashboards", {})
