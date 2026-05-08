from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest

from hadsync.entities import (
    cache_age_days,
    entity_id_exists,
    extract_entity_ids,
    load_entity_cache,
    search_entities,
    write_entity_cache,
    CACHE_FILENAME,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_cache(workspace: Path, entities: dict[str, dict], age_days: float = 0) -> None:
    ts = datetime.now(timezone.utc) - timedelta(days=age_days)
    cache = {"refreshed_at": ts.isoformat(), "entities": entities}
    (workspace / CACHE_FILENAME).write_text(json.dumps(cache))


# ---------------------------------------------------------------------------
# extract_entity_ids
# ---------------------------------------------------------------------------

class TestExtractEntityIds:
    def test_simple_entity_field(self) -> None:
        config = {"views": [{"cards": [{"type": "entity", "entity": "light.lamp"}]}]}
        ids = [e for e, _ in extract_entity_ids(config)]
        assert "light.lamp" in ids

    def test_entities_list_of_strings(self) -> None:
        config = {"views": [{"cards": [{"type": "entities", "entities": ["light.a", "sensor.b"]}]}]}
        ids = [e for e, _ in extract_entity_ids(config)]
        assert "light.a" in ids
        assert "sensor.b" in ids

    def test_entities_list_of_dicts(self) -> None:
        config = {"views": [{"cards": [{"type": "entities", "entities": [
            {"entity": "light.kitchen", "name": "Kitchen"},
            {"entity": "switch.fan"},
        ]}]}]}
        ids = [e for e, _ in extract_entity_ids(config)]
        assert "light.kitchen" in ids
        assert "switch.fan" in ids

    def test_entities_mixed_list(self) -> None:
        config = {"views": [{"cards": [{"type": "glance", "entities": [
            "sensor.temp",
            {"entity": "sensor.humidity", "name": "Humidity"},
        ]}]}]}
        ids = [e for e, _ in extract_entity_ids(config)]
        assert "sensor.temp" in ids
        assert "sensor.humidity" in ids

    def test_nested_in_vertical_stack(self) -> None:
        config = {"views": [{"cards": [
            {"type": "vertical-stack", "cards": [
                {"type": "entity", "entity": "light.nested"},
            ]}
        ]}]}
        ids = [e for e, _ in extract_entity_ids(config)]
        assert "light.nested" in ids

    def test_conditional_card_entity(self) -> None:
        config = {"views": [{"cards": [
            {"type": "conditional",
             "conditions": [{"entity": "input_boolean.show", "state": "on"}],
             "card": {"type": "entity", "entity": "light.living_room"}}
        ]}]}
        ids = [e for e, _ in extract_entity_ids(config)]
        assert "input_boolean.show" in ids
        assert "light.living_room" in ids

    def test_skips_non_entity_strings(self) -> None:
        config = {"views": [{"title": "Home", "cards": [{"type": "markdown", "content": "hello"}]}]}
        ids = [e for e, _ in extract_entity_ids(config)]
        assert ids == []

    def test_no_false_positive_on_plain_strings(self) -> None:
        # strings without dots, or comment-like strings, should not be extracted
        config = {"views": [{"entities": ["not-an-entity", "#comment"]}]}
        ids = [e for e, _ in extract_entity_ids(config)]
        assert not any("not-an-entity" in e or "#comment" in e for e in ids)

    def test_deduplication_not_done_at_extraction(self) -> None:
        # extract_entity_ids returns all occurrences; dedup is the caller's job
        config = {"views": [{"cards": [
            {"entity": "light.lamp"},
            {"entity": "light.lamp"},
        ]}]}
        ids = [e for e, _ in extract_entity_ids(config)]
        assert ids.count("light.lamp") == 2

    def test_line_numbers_returned(self) -> None:
        # Line numbers may be None for plain dicts but should be int for ruamel CommentedMaps
        config = {"views": [{"cards": [{"type": "entity", "entity": "light.x"}]}]}
        results = extract_entity_ids(config)
        assert len(results) == 1
        assert results[0][0] == "light.x"
        # line can be None (plain dict) or int — both are valid


# ---------------------------------------------------------------------------
# cache_age_days
# ---------------------------------------------------------------------------

class TestCacheAgeDays:
    def test_returns_none_when_no_cache(self, tmp_path: Path) -> None:
        assert cache_age_days(tmp_path) is None

    def test_fresh_cache_near_zero(self, tmp_path: Path) -> None:
        _write_cache(tmp_path, {"light.lamp": {"domain": "light", "friendly_name": "Lamp"}}, age_days=0)
        age = cache_age_days(tmp_path)
        assert age is not None
        assert age < 0.1

    def test_old_cache_returns_correct_days(self, tmp_path: Path) -> None:
        _write_cache(tmp_path, {}, age_days=8)
        age = cache_age_days(tmp_path)
        assert age is not None
        assert 7.9 < age < 8.1


# ---------------------------------------------------------------------------
# search_entities
# ---------------------------------------------------------------------------

class TestSearchEntities:
    def _setup(self, tmp_path: Path) -> None:
        _write_cache(tmp_path, {
            "light.living_room": {"domain": "light", "friendly_name": "Living Room"},
            "sensor.temperature": {"domain": "sensor", "friendly_name": "Temperature Sensor"},
            "switch.fan": {"domain": "switch", "friendly_name": "Ceiling Fan"},
        })

    def test_no_filter_returns_all(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        result = search_entities(tmp_path, "")
        assert len(result) == 3

    def test_filter_by_domain(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        result = search_entities(tmp_path, "light")
        assert "light.living_room" in result
        assert "sensor.temperature" not in result

    def test_filter_by_friendly_name(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        result = search_entities(tmp_path, "ceiling")
        assert "switch.fan" in result

    def test_filter_case_insensitive(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        assert "sensor.temperature" in search_entities(tmp_path, "TEMP")

    def test_no_match_returns_empty(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        assert search_entities(tmp_path, "nonexistent_xyz") == {}


# ---------------------------------------------------------------------------
# validate_entities integration
# ---------------------------------------------------------------------------

class TestValidateEntities:
    def test_unknown_entity_returns_warn(self, tmp_path: Path) -> None:
        from hadsync.validator import Severity, validate_entities
        yaml_path = tmp_path / "lovelace.yaml"
        yaml_path.write_text("views:\n  - title: Home\n    cards:\n      - entity: light.nonexistent\n")
        _write_cache(tmp_path, {"light.real": {"domain": "light", "friendly_name": "Real"}})
        issues = validate_entities(yaml_path, tmp_path, warn_on_unknown=True)
        unknowns = [i for i in issues if "nonexistent" in i.message]
        assert len(unknowns) == 1
        assert unknowns[0].severity == Severity.WARN

    def test_known_entity_no_issue(self, tmp_path: Path) -> None:
        from hadsync.validator import validate_entities
        yaml_path = tmp_path / "lovelace.yaml"
        yaml_path.write_text("views:\n  - title: Home\n    cards:\n      - entity: light.real\n")
        _write_cache(tmp_path, {"light.real": {"domain": "light", "friendly_name": "Real"}})
        issues = validate_entities(yaml_path, tmp_path)
        assert issues == []

    def test_no_cache_returns_empty(self, tmp_path: Path) -> None:
        from hadsync.validator import validate_entities
        yaml_path = tmp_path / "lovelace.yaml"
        yaml_path.write_text("views:\n  - cards:\n      - entity: light.x\n")
        # no cache file written
        issues = validate_entities(yaml_path, tmp_path)
        assert issues == []

    def test_stale_cache_returns_warn(self, tmp_path: Path) -> None:
        from hadsync.validator import Severity, validate_entities
        yaml_path = tmp_path / "lovelace.yaml"
        yaml_path.write_text("views: []\n")
        _write_cache(tmp_path, {"light.real": {}}, age_days=10)
        issues = validate_entities(yaml_path, tmp_path, max_age_days=7)
        age_warns = [i for i in issues if "old" in i.message]
        assert len(age_warns) == 1
        assert age_warns[0].severity == Severity.WARN

    def test_warn_on_unknown_false_returns_error(self, tmp_path: Path) -> None:
        from hadsync.validator import Severity, validate_entities
        yaml_path = tmp_path / "lovelace.yaml"
        yaml_path.write_text("views:\n  - cards:\n      - entity: light.missing\n")
        _write_cache(tmp_path, {"light.real": {}})
        issues = validate_entities(yaml_path, tmp_path, warn_on_unknown=False)
        unknowns = [i for i in issues if "missing" in i.message]
        assert unknowns[0].severity == Severity.ERROR
