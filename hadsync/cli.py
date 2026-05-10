from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from hadsync import __version__
import hadsync.output as output
from hadsync.config import (
    CONFIG_FILENAME, WORKSPACE_ENV_VAR, ConfigError, discover_config, load_config, save_config,
)
from hadsync.ha_rest import HARestError, get_ha_info
from hadsync.ha_ws import HAAuthError, HAWebSocketClient, HAWebSocketError


@dataclass
class _State:
    config_path: Optional[Path] = None
    dry_run: bool = False
    verbose: bool = False
    quiet: bool = False
    json_output: bool = False
    yes: bool = False


_state = _State()

app = typer.Typer(
    name="hadsync",
    help="Home Assistant Dashboard Sync — manage Lovelace dashboards as code.",
    no_args_is_help=True,
    add_completion=False,
)
entities_app = typer.Typer(help="Entity cache management.", no_args_is_help=True)
config_app = typer.Typer(help="Configuration management.", no_args_is_help=True)
app.add_typer(entities_app, name="entities")
app.add_typer(config_app, name="config")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"hadsync {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version and exit."),
    ] = None,
    config: Annotated[Optional[str], typer.Option("--config", help="Path to .hadsync.yaml.")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would happen; do not execute.")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Increase output verbosity.")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress all output except errors.")] = False,
    json_output: Annotated[bool, typer.Option("--json-output", help="Output results as JSON.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompts.")] = False,
) -> None:
    _state.config_path = Path(config) if config else None
    _state.dry_run = dry_run
    _state.verbose = verbose
    _state.quiet = quiet
    _state.json_output = json_output
    _state.yes = yes


def _not_implemented(name: str) -> None:
    output.warn(f"'{name}' is not yet implemented.")
    raise typer.Exit(1)


@app.command()
def init() -> None:
    """Interactive setup: HA URL, token env var, workspace directory."""
    existing = discover_config()
    if existing is not None and existing.parent == Path.cwd():
        if not typer.confirm(f"Config already exists at {existing}. Overwrite?", default=False):
            raise typer.Exit()

    ha_url = typer.prompt("Home Assistant URL", default="http://homeassistant.local:8123").rstrip("/")

    output.info("Enter the NAME of the environment variable that holds your HA long-lived token.")
    output.info("Example: if you run  export HA_TOKEN=eyJ...  then enter  HA_TOKEN")
    while True:
        token_var = typer.prompt("Token environment variable name", default="HA_TOKEN").strip()
        # Catch the common mistake of pasting the token value instead of the var name
        if "." in token_var or token_var.startswith("eyJ") or len(token_var) > 64:
            output.error(
                "That looks like a token value, not a variable name. "
                "Enter just the name, e.g.  HA_TOKEN"
            )
            continue
        if not token_var.replace("_", "").isalnum() or token_var[0].isdigit():
            output.error("Variable name must contain only letters, digits, and underscores, and not start with a digit.")
            continue
        break

    workspace_str = typer.prompt(
        f"Local workspace directory\n  (or set {WORKSPACE_ENV_VAR} env var to override at runtime)",
        default=".",
    )

    token = os.environ.get(token_var)
    if token is None:
        output.warn(f"${token_var} is not set — skipping connection test.")
        output.info(f"Set it before using hadsync:  export {token_var}=<long-lived-token>")
    else:
        try:
            ha_info = get_ha_info(ha_url, token)
            output.success(f"Connection verified (HA {ha_info.get('version', 'unknown')})")
        except HARestError as e:
            output.error(str(e))
            raise typer.Exit(1)

    config_path = Path.cwd() / CONFIG_FILENAME
    raw: dict = {
        "ha_url": ha_url,
        "ha_token": f"${{{token_var}}}",
        "workspace": workspace_str,
        "pull": {"refresh_entities": True, "dashboards": "all"},
        "push": {"require_validation": True, "confirm": True},
        "validation": {"warn_on_unknown_entities": True, "entity_cache_max_age_days": 7},
    }
    save_config(raw, config_path)
    output.success(f"Config saved to {config_path}")

    workspace = Path(workspace_str)
    if not workspace.is_absolute():
        workspace = Path.cwd() / workspace
    workspace.mkdir(parents=True, exist_ok=True)
    output.success(f"Workspace ready: {workspace}")

    gitignore = workspace / ".gitignore"
    entries = [".hadsync-state.json", ".ha-entities.json"]
    existing_lines: set[str] = set()
    if gitignore.exists():
        existing_lines = set(gitignore.read_text().splitlines())
    new_entries = [e for e in entries if e not in existing_lines]
    if new_entries:
        with gitignore.open("a") as f:
            f.write("\n".join(new_entries) + "\n")
        verb = "updated" if existing_lines else "created"
        output.success(f".gitignore {verb} in {workspace_str}/")


@app.command("list")
def list_dashboards() -> None:
    """List all dashboards on the HA instance."""
    asyncio.run(_list_async())


async def _list_async() -> None:
    from rich.table import Table

    try:
        cfg, _ = load_config(_state.config_path)
    except ConfigError as e:
        output.error(str(e))
        raise typer.Exit(1)

    try:
        async with HAWebSocketClient(cfg.ha_url, cfg.ha_token) as client:
            panels = await client.get_panels()
    except HAAuthError as e:
        output.error(f"Authentication failed: {e}")
        raise typer.Exit(1)
    except HAWebSocketError as e:
        output.error(f"Connection error: {e}")
        raise typer.Exit(1)

    table = Table(title=f"Dashboards on {cfg.ha_url}")
    table.add_column("ID", style="bold cyan", no_wrap=True)
    table.add_column("Title")
    table.add_column("URL Path", style="dim")
    table.add_column("Mode", style="dim")

    for panel_key, panel in sorted(panels.items(), key=lambda x: x[1].get("title", "")):
        url_path = panel.get("url_path", panel_key)
        title = panel.get("title") or url_path
        mode = (panel.get("config") or {}).get("mode", "storage")
        table.add_row(url_path, title, f"/{url_path}", mode)

    output.console.print()
    output.console.print(table)
    output.console.print(f"\n[dim]{len(panels)} dashboard(s) found[/dim]")


@app.command()
def pull(
    dashboard_id: Annotated[Optional[str], typer.Argument(help="Dashboard ID to pull (omit for all).")] = None,
    no_cache: Annotated[bool, typer.Option("--no-cache", help="Skip entity cache refresh.")] = False,
) -> None:
    """Pull dashboards from HA to local YAML."""
    asyncio.run(_pull_async(dashboard_id, no_cache))


async def _pull_async(dashboard_id: Optional[str], no_cache: bool) -> None:
    from hadsync.converter import (
        LOVELACE_FILENAME, config_hash, config_to_yaml_file, count_cards,
        is_strategy_dashboard, normalize,
    )
    from hadsync.state import record_pull
    from hadsync.ha_rest import HARestError, get_entity_states
    from hadsync.entities import write_entity_cache

    try:
        cfg, _ = load_config(_state.config_path)
    except ConfigError as e:
        output.error(str(e))
        raise typer.Exit(1)

    try:
        async with HAWebSocketClient(cfg.ha_url, cfg.ha_token) as client:
            panels = await client.get_panels()

            # Resolve target dashboards
            if dashboard_id:
                url_paths = {v.get("url_path", k) for k, v in panels.items()}
                if dashboard_id not in url_paths:
                    output.error(
                        f"Dashboard '{dashboard_id}' not found. "
                        "Run 'hadsync list' to see available dashboards."
                    )
                    raise typer.Exit(1)
                targets = {k: v for k, v in panels.items() if v.get("url_path", k) == dashboard_id}
            elif cfg.pull.dashboards == "all":
                targets = panels
            else:
                wanted = set(cfg.pull.dashboards) if isinstance(cfg.pull.dashboards, list) else set()
                targets = {k: v for k, v in panels.items() if v.get("url_path", k) in wanted}

            pulled, skipped = 0, 0
            for panel_key, panel in sorted(targets.items(), key=lambda x: x[1].get("title", "")):
                url_path = panel.get("url_path", panel_key)
                title = panel.get("title", url_path)
                try:
                    config = await client.get_dashboard_config(url_path)
                except Exception as e:
                    output.warn(f"Skipped {url_path} — fetch failed: {e}")
                    skipped += 1
                    continue

                if is_strategy_dashboard(config):
                    output.warn(f"Skipped {url_path} ({title}) — strategy dashboard is read-only")
                    skipped += 1
                    continue

                yaml_path = cfg.workspace / url_path / LOVELACE_FILENAME
                config_to_yaml_file(config, yaml_path)
                record_pull(
                    cfg.workspace, url_path,
                    ha_config_hash=config_hash(normalize(config)),
                )

                n_views, n_cards = count_cards(config)
                try:
                    display = yaml_path.relative_to(Path.cwd())
                except ValueError:
                    display = yaml_path
                output.success(f"Pulled {url_path}  →  {display}  ({n_views} views, {n_cards} cards)")
                pulled += 1

    except HAAuthError as e:
        output.error(f"Authentication failed: {e}")
        raise typer.Exit(1)
    except HAWebSocketError as e:
        output.error(f"Connection error: {e}")
        raise typer.Exit(1)

    # Entity cache refresh
    if not no_cache and cfg.pull.refresh_entities:
        try:
            states = get_entity_states(cfg.ha_url, cfg.ha_token)
            count = write_entity_cache(cfg.workspace, states)
            output.success(f"Entity cache refreshed  →  .ha-entities.json  ({count} entities)")
        except HARestError as e:
            output.warn(f"Entity cache refresh failed: {e}")

    if pulled or skipped:
        parts = []
        if pulled:
            parts.append(f"{pulled} pulled")
        if skipped:
            parts.append(f"{skipped} skipped")
        output.console.print(f"\n[dim]{', '.join(parts)}[/dim]")


@app.command()
def push(
    dashboard_id: Annotated[Optional[str], typer.Argument(help="Dashboard ID to push (omit for all).")] = None,
    skip_validation: Annotated[
        bool, typer.Option("--skip-validation", help="Skip pre-push validation (not recommended).")
    ] = False,
) -> None:
    """Push local YAML dashboards to HA."""
    asyncio.run(_push_async(dashboard_id, skip_validation))


async def _push_async(dashboard_id: Optional[str], skip_validation: bool) -> None:
    from rich.table import Table
    from hadsync.converter import LOVELACE_FILENAME, count_cards, normalize, yaml_file_to_config
    from hadsync.validator import Severity, has_errors, validate
    from hadsync.state import record_push

    try:
        cfg, _ = load_config(_state.config_path)
    except ConfigError as e:
        output.error(str(e))
        raise typer.Exit(1)

    try:
        async with HAWebSocketClient(cfg.ha_url, cfg.ha_token) as client:
            panels = await client.get_panels()
            panel_by_path = {v.get("url_path", k): v for k, v in panels.items()}

            # Resolve targets from local workspace or explicit arg
            if dashboard_id:
                targets = [dashboard_id]
            else:
                targets = sorted(
                    url_path for url_path in panel_by_path
                    if (cfg.workspace / url_path / LOVELACE_FILENAME).exists()
                )

            if not targets:
                output.warn("No local dashboard files found. Run 'hadsync pull' first.")
                raise typer.Exit(0)

            pushed = skipped = 0

            for url_path in targets:
                title = (panel_by_path.get(url_path) or {}).get("title", url_path)
                output.console.print(f"\n[bold cyan]{url_path}[/bold cyan]  ({title})")

                yaml_path = cfg.workspace / url_path / LOVELACE_FILENAME

                if not yaml_path.exists():
                    output.warn(f"  No local file — run 'hadsync pull {url_path}' first.")
                    skipped += 1
                    continue

                if url_path not in panel_by_path:
                    output.error(f"  Dashboard not found in HA — cannot push.")
                    skipped += 1
                    continue

                # --- Validation (Phase 1 + 2 + 3) ---
                if not skip_validation:
                    from hadsync.validator import validate_entities, validate_schema
                    issues = validate(yaml_path)
                    issues += validate_entities(
                        yaml_path, cfg.workspace,
                        warn_on_unknown=cfg.validation.warn_on_unknown_entities,
                        max_age_days=cfg.validation.entity_cache_max_age_days,
                    )
                    issues += validate_schema(yaml_path, cfg.validation.custom_card_types)
                    for issue in issues:
                        fn = output.error if issue.severity == Severity.ERROR else output.warn
                        fn(f"  {issue}")
                    if has_errors(issues):
                        output.error("  Blocked by validation errors.")
                        skipped += 1
                        continue

                # --- Load local config and normalize ---
                try:
                    local_raw = yaml_file_to_config(yaml_path)
                except Exception as e:
                    output.error(f"  Cannot read local file: {e}")
                    skipped += 1
                    continue
                local_config = normalize(local_raw)

                # --- Fetch current HA state ---
                try:
                    ha_config = normalize(await client.get_dashboard_config(url_path))
                except Exception as e:
                    output.error(f"  Cannot fetch current HA state: {e}")
                    skipped += 1
                    continue

                # --- No-op guard ---
                if local_config == ha_config:
                    output.info("  Already up to date — no changes to push.")
                    skipped += 1
                    continue

                # --- Change summary ---
                ha_views, ha_cards = count_cards(ha_config)
                local_views, local_cards = count_cards(local_config)

                summary = Table(show_header=True, box=None, padding=(0, 2))
                summary.add_column("", style="dim")
                summary.add_column("Views", justify="right")
                summary.add_column("Cards", justify="right")
                summary.add_row("Current HA", str(ha_views), str(ha_cards))
                summary.add_row("Local (to push)", str(local_views), str(local_cards))
                output.console.print(summary)

                if local_views < ha_views:
                    output.warn(f"  ⚠  Will REMOVE {ha_views - local_views} view(s) from HA.")
                if local_cards < ha_cards:
                    output.warn(f"  ⚠  Will REMOVE {ha_cards - local_cards} card(s) from HA.")
                if local_views == 0 and ha_views > 0 and not skip_validation:
                    output.error(
                        "  Refusing to push: local config has 0 views but HA has "
                        f"{ha_views}. This would wipe the dashboard. "
                        "Use --skip-validation to override."
                    )
                    skipped += 1
                    continue

                # --- Dry run ---
                if _state.dry_run:
                    output.info(f"  [dry-run] Would push {local_views} views, {local_cards} cards — not sent.")
                    continue

                # --- Confirm ---
                if cfg.push.confirm and not _state.yes:
                    confirmed = typer.confirm(f"  Push '{url_path}' to HA?", default=False)
                    if not confirmed:
                        output.info("  Skipped.")
                        skipped += 1
                        continue

                # --- Push ---
                await client.save_dashboard_config(url_path, local_config)
                record_push(cfg.workspace, url_path)
                output.success(f"  Pushed  ({local_views} views, {local_cards} cards)")
                pushed += 1

    except HAAuthError as e:
        output.error(f"Authentication failed: {e}")
        raise typer.Exit(1)
    except HAWebSocketError as e:
        output.error(f"Connection error: {e}")
        raise typer.Exit(1)

    output.console.print(f"\n[dim]{pushed} pushed, {skipped} skipped[/dim]")


@app.command()
def diff(
    dashboard_id: Annotated[Optional[str], typer.Argument(help="Dashboard ID to diff (omit for all).")] = None,
    show: Annotated[bool, typer.Option("--show", help="Print unified diff.")] = False,
) -> None:
    """Compare local YAML vs current HA state."""
    asyncio.run(_diff_async(dashboard_id, show))


def _view_key(view: dict, idx: int) -> str:
    return view.get("path") or view.get("title") or f"view_{idx}"


def _print_view_diff(ha_config: dict, local_config: dict) -> None:
    """Print a view-by-view change summary between HA and local configs."""
    ha_views = {_view_key(v, i): v for i, v in enumerate(ha_config.get("views", []))}
    local_views = {_view_key(v, i): v for i, v in enumerate(local_config.get("views", []))}

    from hadsync.converter import count_cards

    all_keys = list(dict.fromkeys(list(ha_views) + list(local_views)))  # preserve order
    for key in all_keys:
        in_ha = key in ha_views
        in_local = key in local_views
        if in_ha and not in_local:
            output.console.print(f"  [red]  - {key}[/red] (removed)")
        elif in_local and not in_ha:
            output.console.print(f"  [green]  + {key}[/green] (added)")
        elif ha_views[key] != local_views[key]:
            _, ha_c = count_cards(ha_views[key])
            _, lc = count_cards(local_views[key])
            delta = f"{lc - ha_c:+d} cards" if ha_c != lc else "content changed"
            output.console.print(f"  [yellow]  ~ {key}[/yellow] ({delta})")


async def _diff_async(dashboard_id: Optional[str], show: bool) -> None:
    import difflib
    from datetime import datetime, timezone
    from io import StringIO
    from ruamel.yaml import YAML as _YAML
    from hadsync.converter import (
        LOVELACE_FILENAME, config_hash, count_cards, normalize, yaml_file_to_config,
    )
    from hadsync.state import get_dashboard_state

    try:
        cfg, _ = load_config(_state.config_path)
    except ConfigError as e:
        output.error(str(e))
        raise typer.Exit(1)

    if dashboard_id:
        targets = [dashboard_id]
    else:
        if not cfg.workspace.exists():
            output.warn("Workspace directory does not exist. Run 'hadsync pull' first.")
            raise typer.Exit(1)
        targets = sorted(
            d.name for d in cfg.workspace.iterdir()
            if d.is_dir() and (d / LOVELACE_FILENAME).exists()
        )

    if not targets:
        output.warn("No local dashboard files found. Run 'hadsync pull' first.")
        raise typer.Exit(0)

    def _fmt_pull_ts(ts: str) -> str:
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - dt
            mins = int(delta.total_seconds() / 60)
            if mins < 60:
                age = f"{mins}m ago"
            elif mins < 1440:
                age = f"{mins // 60}h ago"
            else:
                age = f"{mins // 1440}d ago"
            return f"{dt.strftime('%Y-%m-%d %H:%M')}  ({age})"
        except Exception:
            return ts[:16]

    try:
        async with HAWebSocketClient(cfg.ha_url, cfg.ha_token) as client:
            changed = clean = 0

            for url_path in targets:
                yaml_path = cfg.workspace / url_path / LOVELACE_FILENAME
                output.console.print(f"\n[bold cyan]{url_path}[/bold cyan]")

                if not yaml_path.exists():
                    output.warn("  No local file.")
                    continue

                try:
                    local_config = normalize(yaml_file_to_config(yaml_path))
                except Exception as e:
                    output.error(f"  Cannot read local file: {e}")
                    continue

                try:
                    ha_config = normalize(await client.get_dashboard_config(url_path))
                except Exception as e:
                    output.error(f"  Cannot fetch from HA: {e}")
                    continue

                # --- Pull context ---
                ds = get_dashboard_state(cfg.workspace, url_path)
                last_pull = ds.get("last_pull")
                stored_hash = ds.get("ha_config_hash")

                if last_pull:
                    output.console.print(f"  [dim]Last pull: {_fmt_pull_ts(last_pull)}[/dim]")

                # --- In-sync fast path ---
                if local_config == ha_config:
                    output.success("  In sync — local matches HA.")
                    clean += 1
                    continue

                changed += 1

                # --- Conflict classification ---
                # Local modified: file mtime > last_pull timestamp
                local_modified = False
                if last_pull and yaml_path.exists():
                    try:
                        pull_dt = datetime.fromisoformat(last_pull)
                        if pull_dt.tzinfo is None:
                            pull_dt = pull_dt.replace(tzinfo=timezone.utc)
                        mtime = datetime.fromtimestamp(
                            yaml_path.stat().st_mtime, tz=timezone.utc
                        )
                        local_modified = mtime > pull_dt
                    except Exception:
                        pass

                # HA modified: current hash differs from stored pull-time hash
                ha_modified = (
                    stored_hash is not None and config_hash(ha_config) != stored_hash
                )

                # --- Change summary ---
                ha_views, ha_cards = count_cards(ha_config)
                local_views, local_cards = count_cards(local_config)

                ha_tag = (
                    "  [yellow]← changed since pull[/yellow]" if ha_modified
                    else "  [dim](unchanged since pull)[/dim]" if stored_hash
                    else ""
                )
                local_tag = (
                    "  [yellow]← modified since pull[/yellow]" if local_modified
                    else "  [dim](clean since pull)[/dim]" if last_pull
                    else ""
                )

                output.console.print(f"  HA:    {ha_views} views, {ha_cards} cards{ha_tag}")
                output.console.print(f"  Local: {local_views} views, {local_cards} cards{local_tag}")
                _print_view_diff(ha_config, local_config)

                # --- Verdict ---
                if local_modified and ha_modified:
                    output.error(
                        "  CONFLICT — both sides changed since last pull."
                    )
                    output.console.print(
                        f"  [dim]  hadsync push {url_path}[/dim]"
                        "  — overwrite HA with local  [dim](discards HA edits)[/dim]"
                    )
                    output.console.print(
                        f"  [dim]  hadsync pull {url_path}[/dim]"
                        "  — overwrite local with HA  [dim](discards local edits)[/dim]"
                    )
                elif ha_modified:
                    output.warn(
                        f"  HA changed since last pull — run "
                        f"'hadsync pull {url_path}' to update local."
                    )
                elif local_modified:
                    output.warn(
                        f"  Local modified since pull — run "
                        f"'hadsync push {url_path}' to apply to HA."
                    )
                else:
                    output.warn(
                        "  Local differs from HA — "
                        "run 'hadsync push' to apply or 'hadsync pull' to discard."
                    )

                # --- Unified diff (--show) ---
                if show:
                    _yaml = _YAML()
                    _yaml.default_flow_style = False
                    _yaml.width = 4096
                    ha_buf, local_buf = StringIO(), StringIO()
                    _yaml.dump(ha_config, ha_buf)
                    _yaml.dump(local_config, local_buf)
                    diff_lines = list(difflib.unified_diff(
                        ha_buf.getvalue().splitlines(keepends=True),
                        local_buf.getvalue().splitlines(keepends=True),
                        fromfile=f"ha/{url_path}",
                        tofile=f"local/{url_path}",
                        lineterm="",
                    ))
                    output.console.print()
                    for line in diff_lines[:200]:
                        if line.startswith("+++") or line.startswith("---"):
                            output.console.print(f"[bold]{line}[/bold]", highlight=False)
                        elif line.startswith("+"):
                            output.console.print(f"[green]{line}[/green]", highlight=False)
                        elif line.startswith("-"):
                            output.console.print(f"[red]{line}[/red]", highlight=False)
                        elif line.startswith("@@"):
                            output.console.print(f"[cyan]{line}[/cyan]", highlight=False)
                        else:
                            output.console.print(line, highlight=False)
                    if len(diff_lines) > 200:
                        output.warn(
                            f"  ... {len(diff_lines) - 200} more lines (diff truncated to 200)"
                        )

    except HAAuthError as e:
        output.error(f"Authentication failed: {e}")
        raise typer.Exit(1)
    except HAWebSocketError as e:
        output.error(f"Connection error: {e}")
        raise typer.Exit(1)

    output.console.print(f"\n[dim]{changed} changed, {clean} unchanged[/dim]")


@app.command()
def validate(
    dashboard_id: Annotated[Optional[str], typer.Argument(help="Dashboard ID to validate (omit for all).")] = None,
) -> None:
    """Validate local YAML files without pushing."""
    from hadsync.converter import LOVELACE_FILENAME
    from hadsync.validator import Severity, has_errors, validate as _validate

    try:
        cfg, _ = load_config(_state.config_path)
    except ConfigError as e:
        output.error(str(e))
        raise typer.Exit(1)

    if dashboard_id:
        targets = [dashboard_id]
    else:
        if not cfg.workspace.exists():
            output.warn("Workspace directory does not exist. Run 'hadsync pull' first.")
            raise typer.Exit(1)
        targets = sorted(
            d.name for d in cfg.workspace.iterdir()
            if d.is_dir() and (d / LOVELACE_FILENAME).exists()
        )

    if not targets:
        output.warn("No local dashboard files found. Run 'hadsync pull' first.")
        raise typer.Exit(0)

    from hadsync.validator import validate_entities, validate_schema
    import json as _json

    # Collect all issues before output so --json-output can emit them atomically
    all_issues: dict[str, list] = {}
    total_errors = total_warnings = 0

    for url_path in targets:
        yaml_path = cfg.workspace / url_path / LOVELACE_FILENAME
        issues = _validate(yaml_path)
        issues += validate_entities(
            yaml_path, cfg.workspace,
            warn_on_unknown=cfg.validation.warn_on_unknown_entities,
            max_age_days=cfg.validation.entity_cache_max_age_days,
        )
        issues += validate_schema(yaml_path, cfg.validation.custom_card_types)
        all_issues[url_path] = issues
        total_errors += sum(1 for i in issues if i.severity == Severity.ERROR)
        total_warnings += sum(1 for i in issues if i.severity == Severity.WARN)

    if _state.json_output:
        result = {
            "dashboards": {
                url_path: {
                    "file": str(cfg.workspace / url_path / LOVELACE_FILENAME),
                    "passed": not any(i.severity == Severity.ERROR for i in issues),
                    "issues": [
                        {"severity": i.severity.value, "message": i.message, "line": i.line}
                        for i in issues
                    ],
                }
                for url_path, issues in all_issues.items()
            },
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        }
        print(_json.dumps(result))
        raise typer.Exit(1 if total_errors else 0)

    for url_path, issues in all_issues.items():
        n_err = sum(1 for i in issues if i.severity == Severity.ERROR)
        n_warn = sum(1 for i in issues if i.severity == Severity.WARN)

        if not issues:
            label = "[green]PASS[/green]"
        elif n_err:
            label = f"[red]FAIL ({n_err} error(s))[/red]"
        else:
            label = f"[yellow]WARN ({n_warn} warning(s))[/yellow]"

        output.console.print(f"  {label}  {url_path}")
        for issue in issues:
            fn = output.error if issue.severity == Severity.ERROR else output.warn
            fn(f"       {issue}")

    output.console.print()
    if total_errors:
        output.error(f"{total_errors} error(s), {total_warnings} warning(s) — not safe to push")
        raise typer.Exit(1)
    elif total_warnings:
        output.warn(f"0 errors, {total_warnings} warning(s) — review before pushing")
    else:
        output.success(f"All {len(targets)} dashboard(s) passed")


@app.command()
def watch(
    dashboard_id: Annotated[Optional[str], typer.Argument(help="Dashboard ID to watch (omit for all).")] = None,
    auto_push: Annotated[bool, typer.Option("--auto-push", help="Push to HA automatically after validation passes.")] = False,
) -> None:
    """Monitor local YAML files and validate on every save (Phase 1+2+3).

    With --auto-push: pushes to HA automatically when validation passes.
    """
    from hadsync.watcher import run_watch

    try:
        cfg, _ = load_config(_state.config_path)
    except ConfigError as e:
        output.error(str(e))
        raise typer.Exit(1)

    if not cfg.workspace.exists():
        output.error(f"Workspace does not exist: {cfg.workspace}")
        raise typer.Exit(1)

    run_watch(cfg, auto_push=auto_push, filter_id=dashboard_id)


@app.command()
def status() -> None:
    """Show sync status for all local dashboards."""
    from datetime import datetime, timezone
    from rich.table import Table
    from hadsync.converter import LOVELACE_FILENAME
    from hadsync.state import get_all_states

    try:
        cfg, _ = load_config(_state.config_path)
    except ConfigError as e:
        output.error(str(e))
        raise typer.Exit(1)

    states = get_all_states(cfg.workspace)

    local_dirs: set[str] = set()
    if cfg.workspace.exists():
        local_dirs = {
            d.name for d in cfg.workspace.iterdir()
            if d.is_dir() and (d / LOVELACE_FILENAME).exists()
        }

    all_dashboards = sorted(set(states.keys()) | local_dirs)

    if not all_dashboards:
        output.warn("No local dashboards found. Run 'hadsync pull' first.")
        raise typer.Exit(0)

    def _fmt(ts: Optional[str]) -> str:
        if not ts:
            return "[dim]—[/dim]"
        try:
            return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return ts[:16]

    def _local_label(url_path: str, last_pull: Optional[str]) -> str:
        yaml_path = cfg.workspace / url_path / LOVELACE_FILENAME
        if not yaml_path.exists():
            return "[red]no file[/red]"
        if not last_pull:
            return "[yellow]never pulled[/yellow]"
        try:
            pull_dt = datetime.fromisoformat(last_pull)
            if pull_dt.tzinfo is None:
                pull_dt = pull_dt.replace(tzinfo=timezone.utc)
            mtime = datetime.fromtimestamp(yaml_path.stat().st_mtime, tz=timezone.utc)
            return "[yellow]modified[/yellow]" if mtime > pull_dt else "[green]clean[/green]"
        except Exception:
            return "[dim]unknown[/dim]"

    table = Table(show_header=True, header_style="bold")
    table.add_column("Dashboard", style="bold cyan", no_wrap=True)
    table.add_column("Last Pull")
    table.add_column("Last Push")
    table.add_column("Local")

    for url_path in all_dashboards:
        s = states.get(url_path, {})
        table.add_row(
            url_path,
            _fmt(s.get("last_pull")),
            _fmt(s.get("last_push")),
            _local_label(url_path, s.get("last_pull")),
        )

    output.console.print()
    output.console.print(table)
    output.console.print(f"\n[dim]Workspace: {cfg.workspace}[/dim]")


@entities_app.command("refresh")
def entities_refresh() -> None:
    """Refresh the local entity cache from HA /api/states."""
    from hadsync.ha_rest import HARestError, get_entity_states
    from hadsync.entities import write_entity_cache

    try:
        cfg, _ = load_config(_state.config_path)
    except ConfigError as e:
        output.error(str(e))
        raise typer.Exit(1)

    try:
        output.info("Fetching entity states from HA...")
        states = get_entity_states(cfg.ha_url, cfg.ha_token)
        count = write_entity_cache(cfg.workspace, states)
        output.success(f"Entity cache refreshed — {count} entities → {cfg.workspace / '.ha-entities.json'}")
    except HARestError as e:
        output.error(str(e))
        raise typer.Exit(1)


@entities_app.command("list")
def entities_list(
    filter_term: Annotated[Optional[str], typer.Argument(help="Filter by domain or name.")] = None,
) -> None:
    """List cached entities, optionally filtered by domain or name."""
    from rich.table import Table
    from hadsync.entities import cache_age_days, load_entity_cache, search_entities

    try:
        cfg, _ = load_config(_state.config_path)
    except ConfigError as e:
        output.error(str(e))
        raise typer.Exit(1)

    total = len(load_entity_cache(cfg.workspace).get("entities", {}))
    if total == 0:
        output.warn("Entity cache is empty. Run 'hadsync entities refresh' first.")
        raise typer.Exit(1)

    matched = search_entities(cfg.workspace, filter_term or "")

    if not matched:
        output.warn(f"No entities matching '{filter_term}'.")
        raise typer.Exit(0)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Entity ID", style="bold cyan", no_wrap=True)
    table.add_column("Friendly Name")
    table.add_column("Domain", style="dim")

    for entity_id, info in sorted(matched.items()):
        table.add_row(
            entity_id,
            info.get("friendly_name") or "—",
            info.get("domain", entity_id.split(".")[0]),
        )

    age = cache_age_days(cfg.workspace)
    age_str = f"{age:.0f}d old" if age is not None else "unknown age"
    filter_note = f" matching '{filter_term}'" if filter_term else f" of {total} total"

    output.console.print()
    output.console.print(table)
    output.console.print(f"\n[dim]{len(matched)} entities{filter_note} — cache {age_str}[/dim]")


@config_app.command("show")
def config_show() -> None:
    """Print resolved config (token masked)."""
    from rich.table import Table

    try:
        cfg, path = load_config(_state.config_path)
    except ConfigError as e:
        output.error(str(e))
        raise typer.Exit(1)

    import os as _os
    ws_source = f"({WORKSPACE_ENV_VAR} env var)" if _os.environ.get(WORKSPACE_ENV_VAR) else "(config)"

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()
    for key, val in [
        ("ha_url", cfg.ha_url),
        ("ha_token", cfg.masked_token()),
        ("workspace", f"{cfg.workspace}  {ws_source}"),
        ("pull.refresh_entities", str(cfg.pull.refresh_entities).lower()),
        ("pull.dashboards", str(cfg.pull.dashboards)),
        ("push.require_validation", str(cfg.push.require_validation).lower()),
        ("push.confirm", str(cfg.push.confirm).lower()),
        ("validation.warn_on_unknown_entities", str(cfg.validation.warn_on_unknown_entities).lower()),
        ("validation.entity_cache_max_age_days", f"{cfg.validation.entity_cache_max_age_days} days"),
    ]:
        table.add_row(key, val)

    output.console.print(f"\n[bold]Config:[/bold] {path}\n")
    output.console.print(table)
    output.console.print()


@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Config key (e.g. ha_url, pull.refresh_entities).")],
    value: Annotated[str, typer.Argument(help="New value.")],
) -> None:
    """Set a config value."""
    _not_implemented("config set")
