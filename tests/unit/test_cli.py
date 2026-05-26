from __future__ import annotations

from hadsync.cli import _panel_title_sort_key


class TestPanelTitleSortKey:
    def test_null_title_becomes_empty_string(self) -> None:
        assert _panel_title_sort_key({"title": None}) == ""

    def test_missing_title_becomes_empty_string(self) -> None:
        assert _panel_title_sort_key({}) == ""

    def test_string_title_unchanged(self) -> None:
        assert _panel_title_sort_key({"title": "custom dashboard"}) == "custom dashboard"


class TestPanelSorting:
    def test_sort_with_null_title_does_not_raise(self) -> None:
        # get("title", "") does not help when HA returns "title": null — the key exists.
        panels = {
            "lovelace": {"title": None, "url_path": "lovelace"},
            "custom-dashboard": {"title": "custom dashboard", "url_path": "custom-dashboard"},
            "map": {"title": "Map", "url_path": "map"},
        }
        result = sorted(panels.items(), key=lambda x: _panel_title_sort_key(x[1]))
        assert [k for k, _ in result] == ["lovelace", "custom-dashboard", "map"]
