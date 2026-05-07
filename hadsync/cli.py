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
        LOVELACE_FILENAME, config_to_yaml_file, count_cards, is_strategy_dashboard,
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
                record_pull(cfg.workspace, url_path)

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
    _not_implemented("push")


@app.command()
def diff(
    dashboard_id: Annotated[Optional[str], typer.Argument(help="Dashboard ID to diff (omit for all).")] = None,
    show: Annotated[bool, typer.Option("--show", help="Print unified diff.")] = False,
) -> None:
    """Compare local YAML vs current HA state."""
    _not_implemented("diff")


@app.command()
def validate(
    dashboard_id: Annotated[Optional[str], typer.Argument(help="Dashboard ID to validate (omit for all).")] = None,
) -> None:
    """Validate local YAML files without pushing."""
    _not_implemented("validate")


@app.command()
def status() -> None:
    """Show sync status for all dashboards."""
    _not_implemented("status")


@entities_app.command("refresh")
def entities_refresh() -> None:
    """Refresh the local entity cache from HA /api/states."""
    _not_implemented("entities refresh")


@entities_app.command("list")
def entities_list(
    filter_term: Annotated[Optional[str], typer.Argument(help="Filter by domain or name.")] = None,
) -> None:
    """List cached entities, optionally filtered."""
    _not_implemented("entities list")


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
