from __future__ import annotations

from pathlib import Path

import pytest

from hadsync.converter import (
    config_to_yaml_file,
    count_cards,
    is_strategy_dashboard,
    yaml_file_to_config,
)

_SIMPLE_CONFIG = {
    "title": "Test Dashboard",
    "views": [
        {
            "title": "Home",
            "path": "home",
            "cards": [
                {"type": "entities", "title": "Lights", "entities": ["light.lamp"]},
                {"type": "weather-forecast", "entity": "weather.home"},
            ],
        },
        {
            "title": "Empty",
            "path": "empty",
            "cards": [],
        },
    ],
}

_STRATEGY_CONFIG = {
    "strategy": {"type": "original-states", "areas": {}},
    "views": [],
}

_SECTIONS_CONFIG = {
    "views": [
        {
            "title": "Main",
            "type": "sections",
            "sections": [
                {"cards": [{"type": "tile"}, {"type": "tile"}]},
                {"cards": [{"type": "tile"}]},
            ],
        }
    ]
}


class TestIsStrategyDashboard:
    def test_true_for_strategy_key(self) -> None:
        assert is_strategy_dashboard(_STRATEGY_CONFIG) is True

    def test_false_for_storage_dashboard(self) -> None:
        assert is_strategy_dashboard(_SIMPLE_CONFIG) is False

    def test_false_for_empty_config(self) -> None:
        assert is_strategy_dashboard({}) is False


class TestCountCards:
    def test_counts_classic_cards(self) -> None:
        views, cards = count_cards(_SIMPLE_CONFIG)
        assert views == 2
        assert cards == 2  # only first view has cards; second is empty

    def test_counts_sections_cards(self) -> None:
        views, cards = count_cards(_SECTIONS_CONFIG)
        assert views == 1
        assert cards == 3  # 2 + 1 across sections

    def test_empty_config(self) -> None:
        assert count_cards({}) == (0, 0)


class TestRoundTrip:
    def test_write_and_read_produces_identical_dict(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "lovelace.yaml"
        config_to_yaml_file(_SIMPLE_CONFIG, yaml_path)
        assert yaml_path.exists()
        result = yaml_file_to_config(yaml_path)
        assert result["title"] == _SIMPLE_CONFIG["title"]
        assert len(result["views"]) == len(_SIMPLE_CONFIG["views"])
        assert result["views"][0]["cards"][0]["type"] == "entities"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "sub" / "dir" / "lovelace.yaml"
        config_to_yaml_file({"views": []}, yaml_path)
        assert yaml_path.exists()

    def test_yaml_file_to_config_raises_on_non_mapping(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError):
            yaml_file_to_config(bad)
