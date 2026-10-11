"""Minimal async client for the local BEAAM API (http://<beaam>/api/)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp

from .const import COMMAND_OK_STATUSES

REQUEST_TIMEOUT = 10


class BeaamError(Exception):
    """Base error for the BEAAM API."""


class BeaamConnectionError(BeaamError):
    """The BEAAM could not be reached or returned an unexpected response."""


class BeaamAuthError(BeaamError):
    """The API key was rejected."""


class BeaamNotFoundError(BeaamError):
    """The requested thing does not exist (or has no such resource)."""


class BeaamCommandError(BeaamError):
    """A command or setting update was rejected by the BEAAM."""


def normalize_host(host: str) -> str:
    """Turn '192.168.1.28' or 'http://beaam.local/' into a base URL."""
    host = host.strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    return host


class BeaamApiClient:
    """Talks to the BEAAM local API using a bearer API key (sk_beaam_...)."""

    def __init__(self, session: aiohttp.ClientSession, host: str, api_key: str) -> None:
        self._session = session
        self.base_url = normalize_host(host)
        self._headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        payload: Any = None,
    ) -> tuple[int, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with (
                asyncio.timeout(REQUEST_TIMEOUT),
                self._session.request(
                    method, url, headers=self._headers, params=params, json=payload
                ) as resp,
            ):
                status = resp.status
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BeaamConnectionError(
                f"Error communicating with BEAAM at {self.base_url}: {err!r}"
            ) from err

        if status in (401, 403):
            raise BeaamAuthError("BEAAM rejected the API key")
        if status == 404:
            raise BeaamNotFoundError(f"{method} {path} returned 404")

        data: Any = None
        if text:
            try:
                data = json.loads(text)
            except ValueError:
                data = text
        return status, data

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        status, data = await self._request("GET", path, params=params)
        if status >= 400:
            raise BeaamConnectionError(f"GET {path} failed with HTTP {status}")
        return data

    # ── Read ────────────────────────────────────────────────────────────────

    async def get_site_configuration(self) -> dict[str, Any]:
        """Return the site configuration (things, data points, energy flow meta)."""
        data = await self._get("/api/v1/site/configuration")
        if not isinstance(data, dict) or "siteId" not in data:
            raise BeaamConnectionError("Unexpected site configuration response")
        return data

    async def get_site_state(self) -> list[dict[str, Any]]:
        """Return the energy flow states of the site."""
        data = await self._get("/api/v1/site/state")
        try:
            return data["energyFlow"]["states"]
        except (KeyError, TypeError) as err:
            raise BeaamConnectionError("Unexpected site state response") from err

    async def get_thing_states(self, thing_id: str) -> list[dict[str, Any]]:
        """Return the current states of all data points of a thing."""
        data = await self._get(f"/api/v1/things/{thing_id}/states")
        try:
            return data["states"]
        except (KeyError, TypeError) as err:
            raise BeaamConnectionError("Unexpected thing state response") from err

    async def get_thing_settings(self, thing_id: str) -> list[dict[str, Any]]:
        """Return the settings of a thing."""
        data = await self._get(f"/api/v1/things/{thing_id}/settings")
        try:
            return data["settings"]
        except (KeyError, TypeError) as err:
            raise BeaamConnectionError("Unexpected thing settings response") from err

    # ── Write ───────────────────────────────────────────────────────────────

    async def send_commands(
        self, thing_id: str, commands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Send commands (e.g. [{"key": "TARGET_POWER", "value": 5000}]) to a thing."""
        path = f"/api/v1/things/{thing_id}/commands"
        status, data = await self._request("POST", path, payload=commands)
        results = data if isinstance(data, list) else []
        failed = [
            r for r in results
            if isinstance(r, dict) and r.get("status") not in COMMAND_OK_STATUSES
        ]
        if failed:
            raise BeaamCommandError(
                "; ".join(
                    f"{r.get('key')}: {r.get('status')}"
                    + (f" ({r['message']})" if r.get("message") else "")
                    for r in failed
                )
            )
        if status >= 400:
            raise BeaamCommandError(f"Command failed with HTTP {status}: {data}")
        return results

    async def update_settings(self, thing_id: str, settings: list[dict[str, Any]]) -> None:
        """Update settings (e.g. [{"key": "PRIORITY", "value": 1}]) of a thing."""
        path = f"/api/v1/things/{thing_id}/settings"
        status, data = await self._request("PUT", path, payload=settings)
        if status >= 400:
            raise BeaamCommandError(f"Setting update failed with HTTP {status}: {data}")

    async def push_states(self, thing_id: str, states: list[dict[str, Any]]) -> None:
        """Ingest states for a 'Generic' thing configured on connect.neoom.com."""
        path = f"/api/v1/things/{thing_id}/states"
        status, data = await self._request("POST", path, payload=states)
        if status >= 400:
            raise BeaamCommandError(f"State ingest failed with HTTP {status}: {data}")
