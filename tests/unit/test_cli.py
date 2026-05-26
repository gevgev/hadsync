from __future__ import annotations

from hadsync.cli import _panel_title_sort_key


class TestPanelTitleSortKey:
    def test_null_title_becomes_empty_string(self) -> None:
        assert _panel_title_sort_key({"title": None}) == ""

    def test_missing_title_becomes_empty_string(self) -> None:
        assert _panel_title_sort_key({}) == ""

    def test_string_title_unchanged(self) -> None:
        assert _panel_title_sort_key({"title": "Custom Dashboard"}) == "Custom Dashboard"


class TestPanelSorting:
    def test_sort_with_null_title_does_not_raise(self) -> None:
        # We only assert sorted() completes. Not key order, which depends on title
        # strings and may be intended behaviour
        panels = {
            "lovelace": {"title": None, "url_path": "lovelace"},
            "custom-dashboard": {"title": "Custom Dashboard", "url_path": "custom-dashboard"},
            "map": {"title": "Map", "url_path": "map"},
        }
        result = sorted(panels.items(), key=lambda x: _panel_title_sort_key(x[1]))
        assert len(result) == len(panels)
