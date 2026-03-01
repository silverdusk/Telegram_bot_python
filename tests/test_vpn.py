"""Tests for VPN functionality.

Covers:
  - _fmt_bytes helper
  - VPNClient._authenticate, _request (including re-auth on 401)
  - VPNClient.list_clients, create_client, delete_client,
    enable_client, disable_client, get_qrcode, get_config
  - get_vpn_client() factory (None when unconfigured, singleton when configured)
  - HTTP routes: /admin/vpn (GET), /admin/vpn/clients (POST),
    /admin/vpn/clients/{id}/delete|enable|disable (POST),
    /admin/vpn/clients/{id}/qrcode|config (GET)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import app.services.vpn_client as vpn_module
from app.api.v1.admin import AdminAuthMiddleware, _fmt_bytes, admin_router
from app.services.vpn_client import VPNAPIError, VPNClient

# ── Shared test constants ──────────────────────────────────────────────────────

_SECRET = "test_jwt_secret_for_tests_only_32ch"
_USER = "admin"
_PASSWORD = "testpass"


def _mock_settings(**kwargs):
    s = MagicMock()
    s.web_admin_user = _USER
    s.web_admin_password = _PASSWORD
    s.web_admin_jwt_secret = _SECRET
    s.vpn_api_url = kwargs.get("vpn_api_url", "http://localhost:51821")
    s.vpn_api_password = kwargs.get("vpn_api_password", "secret")
    return s


def _make_token() -> str:
    return jwt.encode(
        {"sub": _USER, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        _SECRET,
        algorithm="HS256",
    )


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    a = FastAPI()
    a.add_middleware(AdminAuthMiddleware)
    a.include_router(admin_router)
    return a


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=True, follow_redirects=False)


@pytest.fixture
def authed_client(client):
    client.cookies.set("admin_token", _make_token())
    return client


@pytest.fixture(autouse=True)
def reset_vpn_singleton():
    """Reset the module-level VPNClient singleton before every test."""
    vpn_module._vpn_client = None
    yield
    vpn_module._vpn_client = None


# ── Mock helpers ───────────────────────────────────────────────────────────────

def _make_ctx(status_code: int = 200, json_data=None, content: bytes = b"", cookies=None):
    """Build a mock httpx.AsyncClient context manager.

    Returns (ctx, inner_client, response).
    ctx   – the object returned by httpx.AsyncClient(...)
    inner – the client yielded by 'async with ctx'
    resp  – the response object returned by inner.request / inner.post
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else []
    resp.content = content
    resp.cookies = cookies if cookies is not None else {}
    resp.raise_for_status = MagicMock()

    inner = MagicMock()
    inner.request = AsyncMock(return_value=resp)
    inner.post = AsyncMock(return_value=resp)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=inner)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, inner, resp


def _vpn_with_cookie() -> VPNClient:
    """VPNClient with a pre-set cookie so _authenticate is never called."""
    c = VPNClient("http://localhost:51821", "password")
    c._cookie = {"connect.sid": "test-session"}
    return c


def _mock_vpn(**method_overrides):
    """Return a mock VPNClient whose async methods succeed by default."""
    m = MagicMock()
    m.list_clients = AsyncMock(return_value=method_overrides.get("list_clients_rv", []))
    m.create_client = AsyncMock(
        return_value=method_overrides.get("create_client_rv", {"id": "new-id", "name": "test"})
    )
    m.delete_client = AsyncMock(return_value=None)
    m.enable_client = AsyncMock(return_value=None)
    m.disable_client = AsyncMock(return_value=None)
    m.get_qrcode = AsyncMock(return_value=b"<svg></svg>")
    m.get_config = AsyncMock(return_value=b"[Interface]\nPrivateKey = ...\n")

    for name, exc in method_overrides.items():
        if name.endswith("_raises") and isinstance(exc, Exception):
            method_name = name[: -len("_raises")]
            getattr(m, method_name).side_effect = exc

    return m


def _sample_client(**overrides) -> dict:
    base = {
        "id": "uuid-1",
        "name": "laptop",
        "enabled": True,
        "address": "10.8.0.2",
        "transferRx": 1024 * 1024,
        "transferTx": 512 * 1024,
        "latestHandshakeAt": "2024-06-01T15:30:00.000Z",
    }
    base.update(overrides)
    return base


# ── _fmt_bytes ─────────────────────────────────────────────────────────────────

class TestFmtBytes:

    def test_none_returns_dash(self):
        assert _fmt_bytes(None) == "—"

    def test_zero_bytes(self):
        assert _fmt_bytes(0) == "0 B"

    def test_small_bytes(self):
        assert _fmt_bytes(500) == "500 B"

    def test_1023_bytes(self):
        assert _fmt_bytes(1023) == "1023 B"

    def test_exactly_1_kb(self):
        assert _fmt_bytes(1024) == "1.0 KB"

    def test_1_5_kb(self):
        assert _fmt_bytes(int(1.5 * 1024)) == "1.5 KB"

    def test_exactly_1_mb(self):
        assert _fmt_bytes(1024 * 1024) == "1.0 MB"

    def test_exactly_1_gb(self):
        assert _fmt_bytes(1024 ** 3) == "1.0 GB"


# ── VPNClient unit tests ───────────────────────────────────────────────────────

class TestVPNClient:

    def test_authenticate_success_stores_cookie(self):
        vpn = VPNClient("http://localhost:51821", "password")
        ctx, inner, resp = _make_ctx(status_code=200, cookies={"connect.sid": "sess123"})

        with patch("app.services.vpn_client.httpx.AsyncClient", return_value=ctx):
            asyncio.run(vpn._authenticate())

        assert vpn._cookie == {"connect.sid": "sess123"}
        inner.post.assert_called_once()

    def test_authenticate_204_accepted(self):
        """wg-easy may return 204 on successful login."""
        vpn = VPNClient("http://localhost:51821", "password")
        ctx, _, _ = _make_ctx(status_code=204, cookies={"connect.sid": "s"})

        with patch("app.services.vpn_client.httpx.AsyncClient", return_value=ctx):
            asyncio.run(vpn._authenticate())

        assert vpn._cookie is not None

    def test_authenticate_wrong_password_raises(self):
        vpn = VPNClient("http://localhost:51821", "bad")
        ctx, _, _ = _make_ctx(status_code=401)

        with patch("app.services.vpn_client.httpx.AsyncClient", return_value=ctx):
            with pytest.raises(VPNAPIError, match="VPN auth failed"):
                asyncio.run(vpn._authenticate())

    def test_list_clients_returns_parsed_json(self):
        vpn = _vpn_with_cookie()
        clients = [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]
        ctx, inner, _ = _make_ctx(status_code=200, json_data=clients)

        with patch("app.services.vpn_client.httpx.AsyncClient", return_value=ctx):
            result = asyncio.run(vpn.list_clients())

        assert result == clients
        inner.request.assert_called_once_with(
            "GET", "http://localhost:51821/api/wireguard/client", timeout=10.0
        )

    def test_create_client_sends_correct_payload(self):
        vpn = _vpn_with_cookie()
        new = {"id": "new-id", "name": "my-client"}
        ctx, inner, _ = _make_ctx(status_code=200, json_data=new)

        with patch("app.services.vpn_client.httpx.AsyncClient", return_value=ctx):
            result = asyncio.run(vpn.create_client("my-client"))

        assert result == new
        inner.request.assert_called_once_with(
            "POST",
            "http://localhost:51821/api/wireguard/client",
            timeout=10.0,
            json={"name": "my-client"},
        )

    def test_delete_client_sends_delete_method(self):
        vpn = _vpn_with_cookie()
        ctx, inner, _ = _make_ctx(status_code=204)

        with patch("app.services.vpn_client.httpx.AsyncClient", return_value=ctx):
            asyncio.run(vpn.delete_client("uuid-1"))

        inner.request.assert_called_once_with(
            "DELETE",
            "http://localhost:51821/api/wireguard/client/uuid-1",
            timeout=10.0,
        )

    def test_enable_client_sends_put(self):
        vpn = _vpn_with_cookie()
        ctx, inner, _ = _make_ctx(status_code=204)

        with patch("app.services.vpn_client.httpx.AsyncClient", return_value=ctx):
            asyncio.run(vpn.enable_client("uuid-1"))

        inner.request.assert_called_once_with(
            "PUT",
            "http://localhost:51821/api/wireguard/client/uuid-1/enable",
            timeout=10.0,
        )

    def test_disable_client_sends_put(self):
        vpn = _vpn_with_cookie()
        ctx, inner, _ = _make_ctx(status_code=204)

        with patch("app.services.vpn_client.httpx.AsyncClient", return_value=ctx):
            asyncio.run(vpn.disable_client("uuid-1"))

        inner.request.assert_called_once_with(
            "PUT",
            "http://localhost:51821/api/wireguard/client/uuid-1/disable",
            timeout=10.0,
        )

    def test_get_qrcode_returns_bytes(self):
        vpn = _vpn_with_cookie()
        svg = b"<svg>QR</svg>"
        ctx, _, _ = _make_ctx(status_code=200, content=svg)

        with patch("app.services.vpn_client.httpx.AsyncClient", return_value=ctx):
            result = asyncio.run(vpn.get_qrcode("uuid-1"))

        assert result == svg

    def test_get_config_returns_bytes(self):
        vpn = _vpn_with_cookie()
        conf = b"[Interface]\nPrivateKey = abc\n"
        ctx, _, _ = _make_ctx(status_code=200, content=conf)

        with patch("app.services.vpn_client.httpx.AsyncClient", return_value=ctx):
            result = asyncio.run(vpn.get_config("uuid-1"))

        assert result == conf

    def test_request_authenticates_lazily_on_first_call(self):
        """When no cookie is set, _request should call _authenticate first."""
        vpn = VPNClient("http://localhost:51821", "password")
        assert vpn._cookie is None

        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.cookies = {"connect.sid": "fresh-session"}

        data_resp = MagicMock()
        data_resp.status_code = 200
        data_resp.json.return_value = []
        data_resp.raise_for_status = MagicMock()

        auth_inner = MagicMock()
        auth_inner.post = AsyncMock(return_value=auth_resp)
        auth_ctx = MagicMock()
        auth_ctx.__aenter__ = AsyncMock(return_value=auth_inner)
        auth_ctx.__aexit__ = AsyncMock(return_value=None)

        data_inner = MagicMock()
        data_inner.request = AsyncMock(return_value=data_resp)
        data_ctx = MagicMock()
        data_ctx.__aenter__ = AsyncMock(return_value=data_inner)
        data_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.services.vpn_client.httpx.AsyncClient",
            side_effect=[auth_ctx, data_ctx],
        ):
            result = asyncio.run(vpn.list_clients())

        assert result == []
        assert vpn._cookie == {"connect.sid": "fresh-session"}

    def test_request_reauthenticates_on_401(self):
        """On 401, the client re-authenticates transparently and retries."""
        vpn = _vpn_with_cookie()

        # Three sequential AsyncClient instantiations:
        # 1. First request → 401
        ctx_unauth, inner_unauth, _ = _make_ctx(status_code=401)

        # 2. _authenticate → 200 with new cookie
        ctx_auth, inner_auth, _ = _make_ctx(
            status_code=200, cookies={"connect.sid": "new-session"}
        )

        # 3. Retry request → 200 with data
        clients = [{"id": "1", "name": "retry-ok"}]
        ctx_retry, inner_retry, _ = _make_ctx(status_code=200, json_data=clients)

        with patch(
            "app.services.vpn_client.httpx.AsyncClient",
            side_effect=[ctx_unauth, ctx_auth, ctx_retry],
        ):
            result = asyncio.run(vpn.list_clients())

        assert result == clients
        # Reauth: POST /api/session was called
        inner_auth.post.assert_called_once()
        # Retry request was made
        assert inner_retry.request.call_count == 1


# ── get_vpn_client factory ─────────────────────────────────────────────────────

class TestGetVpnClient:
    # get_settings is imported inside get_vpn_client(), so patch the source.

    def test_returns_none_when_url_not_configured(self):
        s = _mock_settings(vpn_api_url="", vpn_api_password="secret")
        with patch("app.core.config.get_settings", return_value=s):
            assert vpn_module.get_vpn_client() is None

    def test_returns_none_when_password_not_configured(self):
        s = _mock_settings(vpn_api_url="http://localhost:51821", vpn_api_password="")
        with patch("app.core.config.get_settings", return_value=s):
            assert vpn_module.get_vpn_client() is None

    def test_returns_client_when_both_configured(self):
        s = _mock_settings()
        with patch("app.core.config.get_settings", return_value=s):
            result = vpn_module.get_vpn_client()
        assert isinstance(result, VPNClient)
        assert result.base_url == "http://localhost:51821"

    def test_returns_same_instance_on_repeated_calls(self):
        """Singleton: multiple calls return the exact same object."""
        s = _mock_settings()
        with patch("app.core.config.get_settings", return_value=s):
            first = vpn_module.get_vpn_client()
            second = vpn_module.get_vpn_client()
        assert first is second


# ── /admin/vpn GET ─────────────────────────────────────────────────────────────

class TestAdminVPNPage:

    def test_unauthenticated_redirects_to_login(self, client):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            resp = client.get("/admin/vpn")
        assert resp.status_code == 303
        assert "/admin/login" in resp.headers["location"]

    def test_vpn_not_configured_shows_error(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=None),
        ):
            resp = authed_client.get("/admin/vpn")
        assert resp.status_code == 200
        assert b"not configured" in resp.content.lower()

    def test_api_error_shows_error_message(self, authed_client):
        mock_vpn = _mock_vpn()
        mock_vpn.list_clients.side_effect = Exception("connection refused")
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn")
        assert resp.status_code == 200
        assert b"connection refused" in resp.content

    def test_success_renders_client_names(self, authed_client):
        clients = [_sample_client(name="laptop"), _sample_client(id="uuid-2", name="phone", enabled=False)]
        mock_vpn = _mock_vpn(list_clients_rv=clients)
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn")
        assert resp.status_code == 200
        assert b"laptop" in resp.content
        assert b"phone" in resp.content

    def test_success_shows_correct_stats_counts(self, authed_client):
        clients = [
            _sample_client(id="1", enabled=True),
            _sample_client(id="2", enabled=True),
            _sample_client(id="3", enabled=False),
        ]
        mock_vpn = _mock_vpn(list_clients_rv=clients)
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn")
        body = resp.content
        assert b"3" in body  # total
        assert b"2" in body  # enabled
        assert b"1" in body  # disabled

    def test_bytes_are_formatted_in_response(self, authed_client):
        clients = [_sample_client(transferRx=1024 * 1024, transferTx=512)]
        mock_vpn = _mock_vpn(list_clients_rv=clients)
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn")
        assert b"1.0 MB" in resp.content
        assert b"512 B" in resp.content

    def test_handshake_timestamp_formatted(self, authed_client):
        clients = [_sample_client(latestHandshakeAt="2024-06-01T15:30:00.000Z")]
        mock_vpn = _mock_vpn(list_clients_rv=clients)
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn")
        assert b"2024-06-01 15:30:00" in resp.content

    def test_null_handshake_shown_as_dash(self, authed_client):
        clients = [_sample_client(latestHandshakeAt=None)]
        mock_vpn = _mock_vpn(list_clients_rv=clients)
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn")
        assert "—".encode() in resp.content

    def test_empty_client_list_shows_no_clients_message(self, authed_client):
        mock_vpn = _mock_vpn(list_clients_rv=[])
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn")
        assert resp.status_code == 200
        assert b"No clients" in resp.content


# ── POST /admin/vpn/clients ────────────────────────────────────────────────────

class TestAdminVPNCreate:

    def test_create_success_redirects_with_name(self, authed_client):
        mock_vpn = _mock_vpn()
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.post("/admin/vpn/clients", data={"name": "new-phone"})
        assert resp.status_code == 303
        assert "error" not in resp.headers["location"]
        assert "new-phone" in resp.headers["location"]
        mock_vpn.create_client.assert_called_once_with("new-phone")

    def test_empty_name_returns_error_redirect(self, authed_client):
        mock_vpn = _mock_vpn()
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.post("/admin/vpn/clients", data={"name": "   "})
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]
        mock_vpn.create_client.assert_not_called()

    def test_not_configured_returns_error_redirect(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=None),
        ):
            resp = authed_client.post("/admin/vpn/clients", data={"name": "test"})
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]

    def test_api_error_returns_error_redirect(self, authed_client):
        mock_vpn = _mock_vpn()
        mock_vpn.create_client.side_effect = Exception("timeout")
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.post("/admin/vpn/clients", data={"name": "test"})
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]


# ── POST /admin/vpn/clients/{id}/delete ───────────────────────────────────────

class TestAdminVPNDelete:

    def test_delete_success_redirects(self, authed_client):
        mock_vpn = _mock_vpn()
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.post("/admin/vpn/clients/uuid-1/delete")
        assert resp.status_code == 303
        assert "error" not in resp.headers["location"]
        mock_vpn.delete_client.assert_called_once_with("uuid-1")

    def test_delete_not_configured_returns_error(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=None),
        ):
            resp = authed_client.post("/admin/vpn/clients/uuid-1/delete")
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]

    def test_delete_api_error_returns_error_redirect(self, authed_client):
        mock_vpn = _mock_vpn()
        mock_vpn.delete_client.side_effect = Exception("not found")
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.post("/admin/vpn/clients/uuid-1/delete")
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]


# ── POST /admin/vpn/clients/{id}/enable|disable ───────────────────────────────

class TestAdminVPNToggle:

    def test_enable_success_redirects(self, authed_client):
        mock_vpn = _mock_vpn()
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.post("/admin/vpn/clients/uuid-1/enable")
        assert resp.status_code == 303
        assert "error" not in resp.headers["location"]
        mock_vpn.enable_client.assert_called_once_with("uuid-1")

    def test_enable_not_configured_returns_error(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=None),
        ):
            resp = authed_client.post("/admin/vpn/clients/uuid-1/enable")
        assert "error" in resp.headers["location"]

    def test_disable_success_redirects(self, authed_client):
        mock_vpn = _mock_vpn()
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.post("/admin/vpn/clients/uuid-1/disable")
        assert resp.status_code == 303
        assert "error" not in resp.headers["location"]
        mock_vpn.disable_client.assert_called_once_with("uuid-1")

    def test_disable_api_error_returns_error_redirect(self, authed_client):
        mock_vpn = _mock_vpn()
        mock_vpn.disable_client.side_effect = Exception("server error")
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.post("/admin/vpn/clients/uuid-1/disable")
        assert "error" in resp.headers["location"]


# ── GET /admin/vpn/clients/{id}/qrcode ────────────────────────────────────────

class TestAdminVPNQRCode:

    def test_qrcode_returns_svg_content(self, authed_client):
        svg = b"<svg><rect/></svg>"
        mock_vpn = _mock_vpn()
        mock_vpn.get_qrcode.return_value = svg
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn/clients/uuid-1/qrcode")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/svg+xml"
        assert resp.content == svg
        mock_vpn.get_qrcode.assert_called_once_with("uuid-1")

    def test_qrcode_not_configured_returns_503(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=None),
        ):
            resp = authed_client.get("/admin/vpn/clients/uuid-1/qrcode")
        assert resp.status_code == 503

    def test_qrcode_api_error_returns_502(self, authed_client):
        mock_vpn = _mock_vpn()
        mock_vpn.get_qrcode.side_effect = Exception("timeout")
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn/clients/uuid-1/qrcode")
        assert resp.status_code == 502


# ── GET /admin/vpn/clients/{id}/config ────────────────────────────────────────

class TestAdminVPNConfig:

    def test_config_returns_file_download(self, authed_client):
        conf = b"[Interface]\nPrivateKey = test\nAddress = 10.8.0.2/32\n"
        mock_vpn = _mock_vpn()
        mock_vpn.get_config.return_value = conf
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn/clients/uuid-1/config")
        assert resp.status_code == 200
        assert resp.content == conf
        assert "attachment" in resp.headers["content-disposition"]
        assert "uuid-1.conf" in resp.headers["content-disposition"]
        mock_vpn.get_config.assert_called_once_with("uuid-1")

    def test_config_not_configured_returns_503(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=None),
        ):
            resp = authed_client.get("/admin/vpn/clients/uuid-1/config")
        assert resp.status_code == 503

    def test_config_api_error_returns_502(self, authed_client):
        mock_vpn = _mock_vpn()
        mock_vpn.get_config.side_effect = Exception("not found")
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.services.vpn_client.get_vpn_client", return_value=mock_vpn),
        ):
            resp = authed_client.get("/admin/vpn/clients/uuid-1/config")
        assert resp.status_code == 502
