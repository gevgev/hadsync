from __future__ import annotations

import httpx


class HARestError(Exception):
    pass


def get_ha_info(ha_url: str, token: str, timeout: float = 10.0) -> dict:
    """Fetch HA instance info from REST API. Returns dict with 'version', 'location_name', etc."""
    try:
        resp = httpx.get(
            f"{ha_url}/api/config",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HARestError("Authentication failed — token is invalid or expired.") from e
        raise HARestError(f"HA returned HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise HARestError(f"Connection failed: {e}") from e


def get_entity_states(ha_url: str, token: str, timeout: float = 30.0) -> list[dict]:
    """Fetch all entity states from HA REST API for entity cache population."""
    try:
        resp = httpx.get(
            f"{ha_url}/api/states",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HARestError(f"HA returned HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise HARestError(f"Connection failed: {e}") from e
