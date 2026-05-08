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


# ---------------------------------------------------------------------------
# Phase 1 — YAML syntax + structural checks
# ---------------------------------------------------------------------------

def validate(path: Path) -> list[ValidationIssue]:
    """Phase 1: YAML syntax + structural checks. No HA connection required."""
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


# ---------------------------------------------------------------------------
# Phase 2 — Entity ID existence checks against local cache
# ---------------------------------------------------------------------------

def validate_entities(
    path: Path,
    workspace: Path,
    warn_on_unknown: bool = True,
    max_age_days: int = 7,
) -> list[ValidationIssue]:
    """Phase 2: check entity_id references in a lovelace.yaml against the cache.

    Returns an empty list if the entity cache does not exist (Phase 2 silently
    skipped — user must run 'hadsync entities refresh' to enable this check).
    """
    from hadsync.entities import (
        cache_age_days, entity_id_exists, extract_entity_ids, load_entity_cache,
    )

    issues: list[ValidationIssue] = []

    # Require an existing cache — skip silently if absent (not an error)
    cache = load_entity_cache(workspace)
    if not cache.get("entities"):
        return []

    age = cache_age_days(workspace)
    if age is not None and age > max_age_days:
        issues.append(ValidationIssue(
            Severity.WARN,
            f"Entity cache is {age:.0f} day(s) old (limit: {max_age_days}) — "
            "run 'hadsync entities refresh'",
        ))

    # Load raw YAML to keep ruamel.yaml line info for reporting
    from ruamel.yaml import YAML
    _yaml = YAML()
    try:
        config = _yaml.load(path)
    except Exception:
        return issues  # syntax errors are caught by Phase 1 validate()

    if not isinstance(config, dict):
        return issues

    seen: set[str] = set()
    severity = Severity.WARN if warn_on_unknown else Severity.ERROR

    for entity_id, line in extract_entity_ids(config):
        if entity_id in seen:
            continue
        seen.add(entity_id)
        if not entity_id_exists(workspace, entity_id):
            issues.append(ValidationIssue(
                severity,
                f"Unknown entity: {entity_id}",
                line,
            ))

    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(i.severity == Severity.ERROR for i in issues)
