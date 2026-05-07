from __future__ import annotations

from pathlib import Path

import pytest

from hadsync.validator import Severity, ValidationIssue, has_errors, validate


def _write(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


class TestValidate:
    def test_valid_dashboard_passes(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "lovelace.yaml", "views:\n  - title: Home\n    cards: []\n")
        issues = validate(p)
        assert not has_errors(issues)
        assert issues == []

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        issues = validate(tmp_path / "missing.yaml")
        assert has_errors(issues)
        assert "not found" in issues[0].message

    def test_yaml_syntax_error_returns_error_with_line(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "lovelace.yaml", "views:\n  - title: [unclosed\n")
        issues = validate(p)
        assert has_errors(issues)
        assert issues[0].severity == Severity.ERROR
        assert "syntax" in issues[0].message.lower()
        assert issues[0].line is not None

    def test_empty_file_returns_error(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "lovelace.yaml", "")
        issues = validate(p)
        assert has_errors(issues)

    def test_non_mapping_returns_error(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "lovelace.yaml", "- item1\n- item2\n")
        issues = validate(p)
        assert has_errors(issues)
        assert "mapping" in issues[0].message

    def test_missing_views_key_returns_error(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "lovelace.yaml", "title: My Dashboard\n")
        issues = validate(p)
        assert has_errors(issues)
        assert "views" in issues[0].message

    def test_views_not_list_returns_error(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "lovelace.yaml", "views: not-a-list\n")
        issues = validate(p)
        assert has_errors(issues)

    def test_empty_views_returns_warning_not_error(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "lovelace.yaml", "views: []\n")
        issues = validate(p)
        assert not has_errors(issues)
        assert len(issues) == 1
        assert issues[0].severity == Severity.WARN
        assert "wipe" in issues[0].message.lower()

    def test_non_dict_view_entry_returns_error(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "lovelace.yaml", "views:\n  - just-a-string\n")
        issues = validate(p)
        assert has_errors(issues)

    def test_valid_with_title_and_cards(self, tmp_path: Path) -> None:
        content = (
            "title: Battery Status\n"
            "views:\n"
            "  - title: Batteries\n"
            "    path: batteries\n"
            "    cards:\n"
            "      - type: entities\n"
            "        entities:\n"
            "          - entity: sensor.battery_level\n"
        )
        p = _write(tmp_path / "lovelace.yaml", content)
        assert validate(p) == []


class TestNormalize:
    def test_normalize_converts_commented_map(self, tmp_path: Path) -> None:
        from hadsync.converter import normalize, yaml_file_to_config

        p = _write(tmp_path / "lovelace.yaml", "views:\n  - title: Home\n    cards: []\n")
        raw = yaml_file_to_config(p)
        result = normalize(raw)
        assert type(result) is dict
        assert type(result["views"]) is list
        assert type(result["views"][0]) is dict

    def test_normalize_round_trip_matches_original(self, tmp_path: Path) -> None:
        from hadsync.converter import normalize, yaml_file_to_config

        content = "title: Test\nviews:\n  - title: Home\n    path: home\n    cards:\n      - type: entities\n"
        p = _write(tmp_path / "lovelace.yaml", content)
        raw = yaml_file_to_config(p)
        result = normalize(raw)
        assert result == {"title": "Test", "views": [{"title": "Home", "path": "home", "cards": [{"type": "entities"}]}]}
