from __future__ import annotations

import json
from pathlib import Path

from hadsync.state import (
    STATE_FILENAME,
    get_all_states,
    get_dashboard_state,
    record_pull,
    record_push,
)


class TestRecordPull:
    def test_writes_last_pull_timestamp(self, tmp_path: Path) -> None:
        record_pull(tmp_path, "battery-status")
        state = json.loads((tmp_path / STATE_FILENAME).read_text())
        ts = state["dashboards"]["battery-status"].get("last_pull", "")
        assert ts.startswith("2026-") or ts.startswith("20")  # valid ISO timestamp

    def test_preserves_existing_push_timestamp(self, tmp_path: Path) -> None:
        record_push(tmp_path, "battery-status")
        push_time = get_dashboard_state(tmp_path, "battery-status")["last_push"]
        record_pull(tmp_path, "battery-status")
        assert get_dashboard_state(tmp_path, "battery-status")["last_push"] == push_time

    def test_multiple_dashboards_tracked_independently(self, tmp_path: Path) -> None:
        record_pull(tmp_path, "alpha")
        record_pull(tmp_path, "beta")
        states = get_all_states(tmp_path)
        assert "alpha" in states
        assert "beta" in states


class TestRecordPush:
    def test_writes_last_push_timestamp(self, tmp_path: Path) -> None:
        record_push(tmp_path, "lovelace")
        ds = get_dashboard_state(tmp_path, "lovelace")
        assert "last_push" in ds

    def test_preserves_existing_pull_timestamp(self, tmp_path: Path) -> None:
        record_pull(tmp_path, "lovelace")
        pull_time = get_dashboard_state(tmp_path, "lovelace")["last_pull"]
        record_push(tmp_path, "lovelace")
        assert get_dashboard_state(tmp_path, "lovelace")["last_pull"] == pull_time


class TestGetDashboardState:
    def test_returns_empty_dict_for_unknown_dashboard(self, tmp_path: Path) -> None:
        assert get_dashboard_state(tmp_path, "nonexistent") == {}

    def test_returns_empty_on_missing_state_file(self, tmp_path: Path) -> None:
        assert get_all_states(tmp_path) == {}
