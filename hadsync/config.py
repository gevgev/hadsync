from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, field_validator, ValidationError
from ruamel.yaml import YAML

CONFIG_FILENAME = ".hadsync.yaml"
WORKSPACE_ENV_VAR = "HADSYNC_WORKSPACE"
_ENV_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class ConfigError(Exception):
    pass


class PullSettings(BaseModel):
    refresh_entities: bool = True
    dashboards: Union[str, list[str]] = "all"


class PushSettings(BaseModel):
    require_validation: bool = True
    confirm: bool = True


class ValidationSettings(BaseModel):
    warn_on_unknown_entities: bool = True
    entity_cache_max_age_days: int = 7


class Config(BaseModel):
    ha_url: str
    ha_token: str
    workspace: Path = Path(".")
    pull: PullSettings = PullSettings()
    push: PushSettings = PushSettings()
    validation: ValidationSettings = ValidationSettings()

    @field_validator("ha_token", mode="before")
    @classmethod
    def resolve_token(cls, v: str) -> str:
        m = _ENV_RE.match(str(v))
        if m:
            var_name = m.group(1)
            token = os.environ.get(var_name)
            if token is None:
                raise ValueError(f"Environment variable '{var_name}' is not set")
            return token
        return v

    @field_validator("ha_url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        return v.rstrip("/")

    def masked_token(self) -> str:
        t = self.ha_token
        if len(t) <= 8:
            return "****"
        return f"{t[:4]}...{t[-4:]}"


_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.default_flow_style = False


def discover_config(start: Optional[Path] = None) -> Optional[Path]:
    current = Path(start or Path.cwd()).resolve()
    while True:
        candidate = current / CONFIG_FILENAME
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    global_cfg = Path.home() / CONFIG_FILENAME
    return global_cfg if global_cfg.exists() else None


def load_config(path: Optional[Path] = None) -> tuple[Config, Path]:
    config_path = path or discover_config()
    if config_path is None:
        raise ConfigError("No .hadsync.yaml found. Run 'hadsync init' to create one.")
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")
    try:
        data = _yaml.load(config_path)
    except Exception as e:
        raise ConfigError(f"Failed to parse {config_path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{config_path} is not a valid YAML mapping.")
    try:
        cfg = Config.model_validate(data)
    except ValidationError as e:
        raise ConfigError(f"Invalid config in {config_path}:\n{e}") from e

    # Workspace resolution priority:
    #   1. HADSYNC_WORKSPACE env var
    #   2. workspace in config (relative → resolved against config file's directory)
    #   3. default (.) → resolves to CWD
    env_ws = os.environ.get(WORKSPACE_ENV_VAR)
    if env_ws:
        workspace = Path(env_ws).expanduser().resolve()
    elif not cfg.workspace.is_absolute():
        workspace = (config_path.parent / cfg.workspace).resolve()
    else:
        workspace = cfg.workspace.resolve()

    cfg = cfg.model_copy(update={"workspace": workspace})
    return cfg, config_path


def save_config(raw: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        _yaml.dump(raw, f)
