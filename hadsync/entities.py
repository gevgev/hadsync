from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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


def cache_age_days(workspace: Path) -> Optional[float]:
    """Return the age of the entity cache in days, or None if cache is missing."""
    refreshed_at = load_entity_cache(workspace).get("refreshed_at")
    if not refreshed_at:
        return None
    try:
        ts = datetime.fromisoformat(refreshed_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds() / 86400
    except Exception:
        return None


def search_entities(workspace: Path, filter_term: str = "") -> dict[str, dict]:
    """Return entities whose entity_id or friendly_name contain filter_term."""
    entities = load_entity_cache(workspace).get("entities", {})
    if not filter_term:
        return entities
    term = filter_term.lower()
    return {
        eid: info for eid, info in entities.items()
        if term in eid.lower() or term in (info.get("friendly_name") or "").lower()
    }


# ---------------------------------------------------------------------------
# Entity ID extraction from Lovelace configs
# ---------------------------------------------------------------------------

def _get_line(container: object, key_or_idx: int | str) -> Optional[int]:
    """Best-effort: return 1-based line number of a key/item from ruamel.yaml."""
    try:
        lc = getattr(container, "lc", None)
        if lc is None:
            return None
        if isinstance(key_or_idx, int):
            return lc.item(key_or_idx)[0] + 1
        return lc.key(key_or_idx)[0] + 1
    except Exception:
        return None


def _is_entity_id(value: object) -> bool:
    return isinstance(value, str) and "." in value and not value.startswith("#")


def _walk(obj: object, results: list[tuple[str, Optional[int]]]) -> None:
    if isinstance(obj, dict):
        # entity: light.lamp
        if "entity" in obj:
            v = obj["entity"]
            if _is_entity_id(v):
                results.append((v, _get_line(obj, "entity")))

        # entities: ["light.lamp", {entity: sensor.temp}]
        if "entities" in obj:
            items = obj["entities"]
            if isinstance(items, list):
                for i, item in enumerate(items):
                    if _is_entity_id(item):
                        results.append((item, _get_line(items, i)))
                    elif isinstance(item, dict) and "entity" in item:
                        v = item["entity"]
                        if _is_entity_id(v):
                            results.append((v, _get_line(item, "entity")))

        # Recurse into all other values (cards, sections, elements, card, conditions…)
        for key, val in obj.items():
            if key not in ("entity", "entities"):
                _walk(val, results)

    elif isinstance(obj, list):
        for item in obj:
            _walk(item, results)


def extract_entity_ids(config: object) -> list[tuple[str, Optional[int]]]:
    """Walk a Lovelace config (raw ruamel.yaml dict) and return (entity_id, line) pairs.

    Handles entity/entities fields at any nesting depth (cards, sections, elements,
    conditional conditions, stack cards, etc.).
    """
    results: list[tuple[str, Optional[int]]] = []
    _walk(config, results)
    return results
