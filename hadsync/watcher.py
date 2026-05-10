from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import hadsync.output as output
from hadsync.config import Config
from hadsync.converter import LOVELACE_FILENAME, count_cards, normalize, yaml_file_to_config
from hadsync.validator import Severity, has_errors, validate, validate_entities, validate_schema


class _DashboardHandler(FileSystemEventHandler):
    def __init__(
        self,
        cfg: Config,
        auto_push: bool,
        filter_id: Optional[str],
    ) -> None:
        self._cfg = cfg
        self._auto_push = auto_push
        self._filter_id = filter_id
        self._last: dict[str, float] = {}
        self._debounce = 1.5  # seconds — absorbs rapid consecutive save events

    def on_modified(self, event) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.name != LOVELACE_FILENAME:
            return

        url_path = path.parent.name
        if self._filter_id and url_path != self._filter_id:
            return

        now = time.monotonic()
        key = str(path)
        if now - self._last.get(key, 0) < self._debounce:
            return
        self._last[key] = now

        self._handle(path, url_path)

    def _handle(self, yaml_path: Path, url_path: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        output.console.print(f"\n[dim]{ts}[/dim]  [bold cyan]{url_path}[/bold cyan]  saved")

        try:
            self._validate_and_push(yaml_path, url_path)
        except Exception as e:
            # Catch unexpected errors so the watchdog observer thread keeps running.
            # A crash here would silently stop all future watch events.
            output.error(f"  Watch handler crashed unexpectedly: {e}")

    def _validate_and_push(self, yaml_path: Path, url_path: str) -> None:
        cfg = self._cfg
        issues = validate(yaml_path)
        issues += validate_entities(
            yaml_path, cfg.workspace,
            warn_on_unknown=cfg.validation.warn_on_unknown_entities,
            max_age_days=cfg.validation.entity_cache_max_age_days,
        )
        issues += validate_schema(yaml_path, cfg.validation.custom_card_types)

        if not issues:
            output.success("  Validation passed")
        else:
            for issue in issues:
                fn = output.error if issue.severity == Severity.ERROR else output.warn
                fn(f"  {issue}")

        if self._auto_push and not has_errors(issues):
            try:
                asyncio.run(self._push(yaml_path, url_path))
            except Exception as e:
                output.error(f"  Auto-push failed: {e}")

    async def _push(self, yaml_path: Path, url_path: str) -> None:
        from hadsync.ha_ws import HAWebSocketClient
        from hadsync.state import record_push

        local_config = normalize(yaml_file_to_config(yaml_path))
        async with HAWebSocketClient(self._cfg.ha_url, self._cfg.ha_token) as client:
            ha_config = normalize(await client.get_dashboard_config(url_path))
            if local_config == ha_config:
                output.info("  Already up to date — nothing pushed")
                return
            await client.save_dashboard_config(url_path, local_config)
            record_push(self._cfg.workspace, url_path)
            n_views, n_cards = count_cards(local_config)
            output.success(f"  Auto-pushed ({n_views} views, {n_cards} cards)")


def run_watch(cfg: Config, auto_push: bool, filter_id: Optional[str]) -> None:
    """Start the filesystem watcher. Blocks until Ctrl-C."""
    handler = _DashboardHandler(cfg, auto_push, filter_id)
    observer = Observer()
    observer.schedule(handler, str(cfg.workspace), recursive=True)
    observer.start()

    mode = "validate + auto-push" if auto_push else "validate on save"
    output.success(f"Watching {cfg.workspace}  [{mode}]")
    output.info("Press Ctrl-C to stop.")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        output.console.print("\n[dim]Watch stopped.[/dim]")
