from __future__ import annotations

from pathlib import Path

import pytest

from hadsync.schema import validate_cards, KNOWN_CARD_TYPES
from hadsync.validator import validate_schema


# ---------------------------------------------------------------------------
# validate_cards (pure dict input)
# ---------------------------------------------------------------------------

class TestValidateCards:
    def test_known_type_with_required_fields_passes(self) -> None:
        config = {"views": [{"cards": [{"type": "entity", "entity": "light.lamp"}]}]}
        assert validate_cards(config) == []

    def test_missing_type_warns(self) -> None:
        config = {"views": [{"cards": [{"entity": "light.lamp"}]}]}
        issues = validate_cards(config)
        assert any("missing" in msg and "type" in msg for _, msg, _ in issues)

    def test_unknown_type_warns(self) -> None:
        config = {"views": [{"cards": [{"type": "totally-unknown-card"}]}]}
        issues = validate_cards(config)
        assert any("Unknown card type" in msg for _, msg, _ in issues)

    def test_custom_prefix_skipped(self) -> None:
        config = {"views": [{"cards": [{"type": "custom:button-card", "entity": "light.x"}]}]}
        assert validate_cards(config) == []

    def test_custom_allowlist_prefix_skipped(self) -> None:
        config = {"views": [{"cards": [{"type": "my-prefix:special-card"}]}]}
        assert validate_cards(config, custom_card_types=["my-prefix:"]) == []

    def test_missing_required_field_warns(self) -> None:
        # gauge requires 'entity'
        config = {"views": [{"cards": [{"type": "gauge", "name": "temp"}]}]}
        issues = validate_cards(config)
        assert any("missing field 'entity'" in msg for _, msg, _ in issues)

    def test_nested_stack_cards_checked(self) -> None:
        config = {"views": [{"cards": [
            {"type": "vertical-stack", "cards": [
                {"type": "gauge"},  # missing entity
            ]},
        ]}]}
        issues = validate_cards(config)
        assert any("gauge" in msg and "entity" in msg for _, msg, _ in issues)

    def test_conditional_card_checked(self) -> None:
        config = {"views": [{"cards": [
            {"type": "conditional", "conditions": [], "card": {"type": "gauge"}},
        ]}]}
        issues = validate_cards(config)
        # gauge inside conditional is missing 'entity'
        assert any("gauge" in msg and "entity" in msg for _, msg, _ in issues)

    def test_sections_layout_cards_checked(self) -> None:
        config = {"views": [{"type": "sections", "sections": [
            {"cards": [{"type": "entity", "entity": "light.lamp"}]},
        ]}]}
        assert validate_cards(config) == []

    def test_all_real_dashboard_types_known(self) -> None:
        # All card types observed in live dashboards should be known or custom:
        real_types = [
            "button", "entities", "gauge", "glance", "grid", "heading",
            "history-graph", "horizontal-stack", "logbook", "map", "markdown",
            "media-control", "picture-entity", "picture-glance", "sensor",
            "statistics-graph", "thermostat", "tile", "vertical-stack", "weather-forecast",
        ]
        for card_type in real_types:
            assert card_type in KNOWN_CARD_TYPES, f"{card_type!r} not in KNOWN_CARD_TYPES"

    def test_view_type_not_treated_as_card(self) -> None:
        # masonry and sections are view types — should not generate card issues
        config = {"views": [{"type": "masonry", "cards": [
            {"type": "entities", "entities": ["light.lamp"]},
        ]}]}
        assert validate_cards(config) == []


# ---------------------------------------------------------------------------
# validate_schema (reads from file)
# ---------------------------------------------------------------------------

class TestValidateSchema:
    def test_valid_file_no_issues(self, tmp_path: Path) -> None:
        p = tmp_path / "lovelace.yaml"
        p.write_text("views:\n  - cards:\n      - type: entities\n        entities: [light.lamp]\n")
        assert validate_schema(p) == []

    def test_unknown_card_type_returns_warn(self, tmp_path: Path) -> None:
        from hadsync.validator import Severity
        p = tmp_path / "lovelace.yaml"
        p.write_text("views:\n  - cards:\n      - type: no-such-card\n")
        issues = validate_schema(p)
        assert any(i.severity == Severity.WARN and "Unknown card type" in i.message for i in issues)

    def test_custom_type_no_issue(self, tmp_path: Path) -> None:
        p = tmp_path / "lovelace.yaml"
        p.write_text("views:\n  - cards:\n      - type: custom:mushroom-entity-card\n        entity: light.x\n")
        assert validate_schema(p) == []

    def test_syntax_error_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "lovelace.yaml"
        p.write_text("views: [unclosed\n")
        # Phase 1 catches syntax; Phase 3 returns empty on parse failure
        assert validate_schema(p) == []
