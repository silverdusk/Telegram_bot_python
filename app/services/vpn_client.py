"""Async client for the amnezia-wg-easy / wg-easy REST API."""
from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)


class VPNAPIError(Exception):
    """Raised when the VPN API returns an unexpected error."""


class VPNClient:
    """Thin async wrapper around the wg-easy HTTP API."""

    def __init__(self, base_url: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.password = password
        self._cookie: httpx.Cookies | None = None
        self._lock = asyncio.Lock()

    # ── Authentication ─────────────────────────────────────────────────────────

    async def _authenticate(self) -> None:
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(
                f"{self.base_url}/api/session",
                json={"password": self.password},
                timeout=10.0,
            )
        if resp.status_code not in (200, 204):
            raise VPNAPIError(f"VPN auth failed: HTTP {resp.status_code}")
        self._cookie = resp.cookies
        logger.debug("VPN session established")

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an authenticated request, re-authenticating once on 401/403."""
        if self._cookie is None:
            async with self._lock:
                if self._cookie is None:
                    await self._authenticate()

        async with httpx.AsyncClient(cookies=self._cookie, verify=False) as client:
            resp = await client.request(
                method, f"{self.base_url}{path}", timeout=10.0, **kwargs
            )

        if resp.status_code in (401, 403):
            async with self._lock:
                self._cookie = None
                await self._authenticate()
            async with httpx.AsyncClient(cookies=self._cookie, verify=False) as client:
                resp = await client.request(
                    method, f"{self.base_url}{path}", timeout=10.0, **kwargs
                )

        return resp

    # ── Public API ─────────────────────────────────────────────────────────────

    async def list_clients(self) -> list[dict]:
        resp = await self._request("GET", "/api/wireguard/client")
        resp.raise_for_status()
        return resp.json()

    async def create_client(self, name: str) -> dict:
        resp = await self._request(
            "POST", "/api/wireguard/client", json={"name": name}
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_client(self, client_id: str) -> None:
        resp = await self._request("DELETE", f"/api/wireguard/client/{client_id}")
        resp.raise_for_status()

    async def enable_client(self, client_id: str) -> None:
        resp = await self._request("PUT", f"/api/wireguard/client/{client_id}/enable")
        resp.raise_for_status()

    async def disable_client(self, client_id: str) -> None:
        resp = await self._request("PUT", f"/api/wireguard/client/{client_id}/disable")
        resp.raise_for_status()

    async def get_qrcode(self, client_id: str) -> bytes:
        resp = await self._request("GET", f"/api/wireguard/client/{client_id}/qrcode.svg")
        resp.raise_for_status()
        return resp.content

    async def get_config(self, client_id: str) -> bytes:
        resp = await self._request(
            "GET", f"/api/wireguard/client/{client_id}/configuration"
        )
        resp.raise_for_status()
        return resp.content


# Module-level singleton
_vpn_client: VPNClient | None = None


def get_vpn_client() -> VPNClient | None:
    """Return a shared VPNClient if VPN is configured, else None."""
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.vpn_api_url or not settings.vpn_api_password:
        return None

    global _vpn_client
    if _vpn_client is None:
        _vpn_client = VPNClient(settings.vpn_api_url, settings.vpn_api_password)
    return _vpn_client
