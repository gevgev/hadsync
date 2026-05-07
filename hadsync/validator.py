from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"


@dataclass
class ValidationIssue:
    severity: Severity
    message: str
    line: Optional[int] = None

    def __str__(self) -> str:
        loc = f" (line {self.line})" if self.line else ""
        return f"[{self.severity.value}] {self.message}{loc}"


def validate(path: Path) -> list[ValidationIssue]:
    """Phase 1 validation: YAML syntax + structural checks on a lovelace.yaml file."""
    if not path.exists():
        return [ValidationIssue(Severity.ERROR, f"File not found: {path}")]

    from ruamel.yaml import YAML
    _yaml = YAML()
    try:
        config = _yaml.load(path)
    except Exception as e:
        mark = getattr(getattr(e, "problem_mark", None), "line", None)
        line = mark + 1 if mark is not None else None
        problem = getattr(e, "problem", str(e))
        return [ValidationIssue(Severity.ERROR, f"YAML syntax error: {problem}", line)]

    if config is None:
        return [ValidationIssue(Severity.ERROR, "File is empty")]

    if not isinstance(config, dict):
        return [ValidationIssue(Severity.ERROR, "Config must be a YAML mapping, not a list or scalar")]

    issues: list[ValidationIssue] = []

    if "views" not in config:
        issues.append(ValidationIssue(Severity.ERROR, "Missing required key: 'views'"))
        return issues

    views = config["views"]
    if not isinstance(views, list):
        issues.append(ValidationIssue(Severity.ERROR, "'views' must be a list"))
        return issues

    if len(views) == 0:
        issues.append(ValidationIssue(
            Severity.WARN,
            "Dashboard has 0 views — pushing will wipe all content from this dashboard in HA",
        ))

    for i, view in enumerate(views):
        if not isinstance(view, dict):
            issues.append(ValidationIssue(Severity.ERROR, f"views[{i}] must be a mapping"))

    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(i.severity == Severity.ERROR for i in issues)
