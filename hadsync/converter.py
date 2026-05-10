from __future__ import annotations

import hashlib
import json as _json
from pathlib import Path

from ruamel.yaml import YAML

LOVELACE_FILENAME = "lovelace.yaml"

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.width = 4096          # prevent wrapping long strings (markdown cards etc.)
_yaml.best_sequence_indent = 2
_yaml.best_map_indent = 2


def is_strategy_dashboard(config: dict) -> bool:
    """True when the dashboard is auto-generated via a strategy (read-only in hadsync)."""
    return "strategy" in config


def count_cards(config: dict) -> tuple[int, int]:
    """Return (view_count, card_count) for a dashboard config.

    Handles both classic (cards) and sections-layout views.
    """
    views = config.get("views", [])
    cards = 0
    for view in views:
        cards += len(view.get("cards", []))
        for section in view.get("sections", []):
            cards += len(section.get("cards", []))
    return len(views), cards


def config_to_yaml_file(config: dict, path: Path) -> None:
    """Write a Lovelace config dict to a YAML file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        _yaml.dump(config, f)


def yaml_file_to_config(path: Path) -> dict:
    """Read a YAML file and return a Lovelace config dict."""
    data = _yaml.load(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a YAML mapping")
    return data


def config_hash(config: dict) -> str:
    """Return a short stable hash of a normalized config dict.

    Used to detect HA-side changes between pulls without storing the full config.
    Sorting keys ensures the hash is independent of insertion order.
    """
    return hashlib.sha256(
        _json.dumps(config, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def normalize(obj: object) -> object:
    """Recursively convert ruamel.yaml CommentedMap/Seq to plain dict/list.

    Used to produce a clean JSON-serialisable dict for pushing to HA and for
    equality comparisons between local YAML and the current HA state.
    """
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return obj
