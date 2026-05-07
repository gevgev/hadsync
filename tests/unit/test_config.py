from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from hadsync.config import Config, ConfigError, discover_config, load_config, save_config

_yaml = YAML()


def _write_config(path: Path, data: dict) -> None:
    with path.open("w") as f:
        _yaml.dump(data, f)


class TestDiscoverConfig:
    def test_finds_config_in_start_dir(self, tmp_path: Path) -> None:
        cfg = tmp_path / ".hadsync.yaml"
        cfg.touch()
        assert discover_config(tmp_path) == cfg

    def test_walks_up_to_find_config(self, tmp_path: Path) -> None:
        cfg = tmp_path / ".hadsync.yaml"
        cfg.touch()
        subdir = tmp_path / "sub" / "dir"
        subdir.mkdir(parents=True)
        assert discover_config(subdir) == cfg

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        home_cfg = Path.home() / ".hadsync.yaml"
        if home_cfg.exists():
            pytest.skip("~/.hadsync.yaml exists; cannot test absence")
        assert discover_config(tmp_path) is None


class TestLoadConfig:
    def test_resolves_env_token(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HA_TOKEN", "secret-abc")
        _write_config(tmp_path / ".hadsync.yaml", {
            "ha_url": "http://ha.local:8123",
            "ha_token": "${HA_TOKEN}",
            "workspace": "dashboards",
        })
        cfg, path = load_config(tmp_path / ".hadsync.yaml")
        assert cfg.ha_token == "secret-abc"
        assert path == tmp_path / ".hadsync.yaml"

    def test_raises_on_missing_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MY_HA_TOKEN", raising=False)
        _write_config(tmp_path / ".hadsync.yaml", {
            "ha_url": "http://ha.local:8123",
            "ha_token": "${MY_HA_TOKEN}",
            "workspace": ".",
        })
        with pytest.raises(ConfigError, match="MY_HA_TOKEN"):
            load_config(tmp_path / ".hadsync.yaml")

    def test_raises_when_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / ".hadsync.yaml")

    def test_resolves_workspace_relative_to_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HA_TOKEN", "tok")
        _write_config(tmp_path / ".hadsync.yaml", {
            "ha_url": "http://ha.local:8123",
            "ha_token": "${HA_TOKEN}",
            "workspace": "./dashboards",
        })
        cfg, _ = load_config(tmp_path / ".hadsync.yaml")
        assert cfg.workspace == (tmp_path / "dashboards").resolve()
        assert cfg.workspace.is_absolute()

    def test_strips_trailing_slash_from_url(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HA_TOKEN", "tok")
        _write_config(tmp_path / ".hadsync.yaml", {
            "ha_url": "http://ha.local:8123/",
            "ha_token": "${HA_TOKEN}",
            "workspace": ".",
        })
        cfg, _ = load_config(tmp_path / ".hadsync.yaml")
        assert not cfg.ha_url.endswith("/")

    def test_invalid_yaml_raises_config_error(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / ".hadsync.yaml"
        cfg_path.write_text("key: [unclosed\n")
        with pytest.raises(ConfigError):
            load_config(cfg_path)


class TestMaskedToken:
    def test_short_token_fully_masked(self) -> None:
        cfg = Config(ha_url="http://ha.local:8123", ha_token="short", workspace=Path("."))
        assert cfg.masked_token() == "****"

    def test_long_token_shows_prefix_and_suffix(self) -> None:
        cfg = Config(ha_url="http://ha.local:8123", ha_token="abcdefghijklmnop", workspace=Path("."))
        masked = cfg.masked_token()
        assert masked.startswith("abcd")
        assert masked.endswith("mnop")
        assert "..." in masked


class TestSaveConfig:
    def test_writes_yaml_file(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / ".hadsync.yaml"
        save_config({"ha_url": "http://ha.local:8123", "ha_token": "${HA_TOKEN}"}, cfg_path)
        assert cfg_path.exists()
        data = _yaml.load(cfg_path)
        assert data["ha_url"] == "http://ha.local:8123"
        assert data["ha_token"] == "${HA_TOKEN}"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "nested" / "dir" / ".hadsync.yaml"
        save_config({"ha_url": "http://ha.local:8123"}, cfg_path)
        assert cfg_path.exists()
