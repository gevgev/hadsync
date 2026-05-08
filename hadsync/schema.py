from __future__ import annotations

from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# Known standard Lovelace card types → list of required field names.
# An empty list means the card has no required fields beyond 'type'.
# ---------------------------------------------------------------------------
KNOWN_CARD_TYPES: dict[str, list[str]] = {
    "alarm-panel":       ["entity"],
    "attribute":         [],
    "button":            [],
    "calendar":          [],
    "cast":              [],
    "conditional":       ["conditions", "card"],
    "divider":           [],
    "entities":          ["entities"],
    "entity":            ["entity"],
    "entity-filter":     ["entities", "conditions"],
    "gauge":             ["entity"],
    "glance":            ["entities"],
    "grid":              ["cards"],
    "heading":           [],
    "history-graph":     ["entities"],
    "horizontal-stack":  ["cards"],
    "humidifier":        ["entity"],
    "iframe":            ["url"],
    "light":             ["entity"],
    "logbook":           [],
    "map":               [],
    "markdown":          ["content"],
    "media-control":     ["entity"],
    "picture":           [],
    "picture-elements":  [],
    "picture-entity":    ["entity"],
    "picture-glance":    ["entities"],
    "plant-status":      ["entity"],
    "sensor":            ["entity"],
    "shopping-list":     [],
    "statistic":         ["entity", "stat_type"],
    "statistics-graph":  ["entities"],
    "thermostat":        ["entity"],
    "tile":              ["entity"],
    "todo-list":         [],
    "vertical-stack":    ["cards"],
    "weather-forecast":  ["entity"],
    # HA 2024+
    "area":              ["area"],
    "energy-date-selection": [],
    "input-button":      ["entity"],
}


def _walk_cards(obj: object) -> Iterator[dict]:
    """Yield every card dict in a Lovelace config, at any nesting depth.

    Descends into cards[], sections[].cards[], card (conditional),
    and row (entity-filter template).
    Views are iterated but view-level fields are not yielded as cards.
    """
    if isinstance(obj, dict):
        for view in obj.get("views", []):
            if isinstance(view, dict):
                yield from _walk_cards(view)

        for card in obj.get("cards", []):
            if isinstance(card, dict):
                yield card
                yield from _walk_cards(card)

        for section in obj.get("sections", []):
            if isinstance(section, dict):
                for card in section.get("cards", []):
                    if isinstance(card, dict):
                        yield card
                        yield from _walk_cards(card)

        if "card" in obj and isinstance(obj["card"], dict):
            yield obj["card"]
            yield from _walk_cards(obj["card"])

        if "row" in obj and isinstance(obj["row"], dict):
            yield obj["row"]
            yield from _walk_cards(obj["row"])

    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_cards(item)


def _get_line(container: object, key: str) -> Optional[int]:
    try:
        lc = getattr(container, "lc", None)
        if lc is None:
            return None
        return lc.key(key)[0] + 1
    except Exception:
        return None


def validate_cards(
    config: object,
    custom_card_types: list[str] | None = None,
) -> list[tuple[str, str, Optional[int]]]:
    """Walk all cards and return (severity, message, line) tuples.

    Checks:
      - Each card has a 'type' field
      - Known card types have their required fields present
      - Unknown card types (not custom:*) are flagged

    custom_card_types: extra type prefixes to treat as valid beyond 'custom:'.
    """
    extra_prefixes = tuple(custom_card_types or [])
    issues: list[tuple[str, str, Optional[int]]] = []

    for card in _walk_cards(config):
        card_type = card.get("type")

        if card_type is None:
            issues.append(("WARN", "Card is missing required 'type' field", _get_line(card, "type")))
            continue

        # custom:* and user-allowlisted prefixes — skip schema check
        if card_type.startswith("custom:") or (extra_prefixes and card_type.startswith(extra_prefixes)):
            continue

        if card_type not in KNOWN_CARD_TYPES:
            line = _get_line(card, "type")
            issues.append(("WARN", f"Unknown card type: '{card_type}'", line))
            continue

        for required in KNOWN_CARD_TYPES[card_type]:
            if required not in card:
                line = _get_line(card, "type")
                issues.append(("WARN", f"Card '{card_type}' is missing field '{required}'", line))

    return issues
