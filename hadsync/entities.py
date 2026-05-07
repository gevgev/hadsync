from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CACHE_FILENAME = ".ha-entities.json"


def write_entity_cache(workspace: Path, states: list[dict]) -> int:
    """Build and write the entity cache from a /api/states response list.

    Returns the number of entities written.
    """
    entities: dict[str, dict] = {}
    for state in states:
        entity_id = state.get("entity_id")
        if not entity_id:
            continue
        domain = entity_id.split(".")[0]
        friendly_name = (state.get("attributes") or {}).get("friendly_name", "")
        entities[entity_id] = {"friendly_name": friendly_name, "domain": domain}

    cache = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "entities": entities,
    }
    path = workspace / CACHE_FILENAME
    path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return len(entities)


def load_entity_cache(workspace: Path) -> dict:
    """Return the raw cache dict, or an empty structure if not found."""
    path = workspace / CACHE_FILENAME
    if not path.exists():
        return {"entities": {}, "refreshed_at": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"entities": {}, "refreshed_at": None}


def entity_id_exists(workspace: Path, entity_id: str) -> bool:
    return entity_id in load_entity_cache(workspace).get("entities", {})
