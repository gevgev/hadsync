from __future__ import annotations

import asyncio
import json

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException


class HAWebSocketError(Exception):
    pass


class HAAuthError(HAWebSocketError):
    pass


class HACommandError(HAWebSocketError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _ws_url(ha_url: str) -> str:
    if ha_url.startswith("https://"):
        return "wss://" + ha_url[8:] + "/api/websocket"
    return "ws://" + ha_url[7:] + "/api/websocket"


class HAWebSocketClient:
    """Async context manager for the HA WebSocket API.

    Correct commands for HA 2026.5+:
      list dashboards  → get_panels (filter component_name=lovelace)
      fetch config     → lovelace/config  with explicit url_path
      save config      → lovelace/config/save  with explicit url_path
    """

    def __init__(self, ha_url: str, token: str, timeout: float = 15.0) -> None:
        self._url = _ws_url(ha_url)
        self._token = token
        self._timeout = timeout
        self._ws = None
        self._msg_id = 0

    async def __aenter__(self) -> HAWebSocketClient:
        try:
            self._ws = await connect(self._url, open_timeout=self._timeout)
        except TimeoutError:
            raise HAWebSocketError(f"Connection timed out: {self._url}")
        except (OSError, WebSocketException) as e:
            raise HAWebSocketError(f"Cannot connect to {self._url}: {e}") from e

        async with asyncio.timeout(self._timeout):
            first = json.loads(await self._ws.recv())
            if first.get("type") != "auth_required":
                raise HAWebSocketError(f"Expected auth_required, got: {first.get('type')}")

            await self._ws.send(json.dumps({"type": "auth", "access_token": self._token}))
            auth_resp = json.loads(await self._ws.recv())

        if auth_resp.get("type") == "auth_invalid":
            raise HAAuthError(auth_resp.get("message", "Authentication failed"))
        if auth_resp.get("type") != "auth_ok":
            raise HAWebSocketError(f"Unexpected auth response: {auth_resp.get('type')}")

        return self

    async def __aexit__(self, *args: object) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def _command(self, **payload: object) -> object:
        msg_id = self._next_id()
        await self._ws.send(json.dumps({"id": msg_id, **payload}))
        async with asyncio.timeout(self._timeout):
            while True:
                raw = await self._ws.recv()
                msg = json.loads(raw)
                if msg.get("id") != msg_id:
                    continue  # skip push messages or earlier responses
                if not msg.get("success"):
                    err = msg.get("error", {})
                    raise HACommandError(
                        err.get("code", "unknown"),
                        err.get("message", str(err)),
                    )
                return msg.get("result")

    async def get_panels(self) -> dict[str, dict]:
        """Return all Lovelace dashboard panels keyed by panel id."""
        result = await self._command(type="get_panels")
        return {
            k: v
            for k, v in (result or {}).items()
            if isinstance(v, dict) and v.get("component_name") == "lovelace"
        }

    async def get_dashboard_config(self, url_path: str) -> dict:
        """Fetch the full Lovelace config for a dashboard by its url_path."""
        result = await self._command(type="lovelace/config", url_path=url_path)
        return result or {}

    async def save_dashboard_config(self, url_path: str, config: dict) -> None:
        """Overwrite the Lovelace config for a dashboard by its url_path."""
        await self._command(type="lovelace/config/save", url_path=url_path, config=config)
