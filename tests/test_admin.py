"""Tests for web admin panel (app/api/v1/admin.py).

Covers:
  - JWT helpers (_create_token, _validate_token)
  - AdminAuthMiddleware dispatch logic
  - HTTP routes: login, logout, dashboard, users, items, settings
  - Settings persistence helpers (_save_to_json, _save_to_env)
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.admin import (
    AdminAuthMiddleware,
    _create_token,
    _save_to_env,
    _save_to_json,
    _validate_token,
    admin_router,
)

# ── Test constants ─────────────────────────────────────────────────────────────

_SECRET = "test_jwt_secret_for_tests_only_32ch"
_USER = "admin"
_PASSWORD = "testpass"


def _mock_settings():
    s = MagicMock()
    s.web_admin_user = _USER
    s.web_admin_password = _PASSWORD
    s.web_admin_jwt_secret = _SECRET
    s.min_len_str = 1
    s.max_len_str = 255
    s.max_item_amount = 1_000_000
    s.max_item_price = 999_999.99
    s.allowed_types = ["spare part", "miscellaneous"]
    s.skip_working_hours = True
    return s


def _make_token(secret: str = _SECRET, expire_delta: timedelta = timedelta(hours=1)) -> str:
    return jwt.encode(
        {"sub": _USER, "exp": datetime.now(timezone.utc) + expire_delta},
        secret,
        algorithm="HS256",
    )


def _mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _wrap_session(session):
    """Return a mock get_db_session that yields the given session as an async context manager."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_get_db_session():
        yield session

    return _fake_get_db_session


def _scalar_result(value):
    r = MagicMock()
    r.scalar.return_value = value
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_result(items):
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    r.scalars.return_value.unique.return_value.all.return_value = items
    return r


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


# ── JWT helpers ────────────────────────────────────────────────────────────────

class TestAdminJWT:

    def test_create_token_is_valid(self):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            token = _create_token(_USER)
        payload = jwt.decode(token, _SECRET, algorithms=["HS256"])
        assert payload["sub"] == _USER

    def test_validate_token_true_for_valid(self):
        token = _make_token()
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            assert _validate_token(token) is True

    def test_validate_token_false_for_none(self):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            assert _validate_token(None) is False

    def test_validate_token_false_for_empty_string(self):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            assert _validate_token("") is False

    def test_validate_token_false_for_garbage(self):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            assert _validate_token("not.a.jwt") is False

    def test_validate_token_false_for_wrong_secret(self):
        token = _make_token(secret="wrong_secret")
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            assert _validate_token(token) is False

    def test_validate_token_false_for_expired(self):
        token = _make_token(expire_delta=timedelta(seconds=-1))
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            assert _validate_token(token) is False


# ── AdminAuthMiddleware ────────────────────────────────────────────────────────

class TestAdminAuthMiddleware:

    def _make_request(self, path: str, cookie: str | None = None):
        request = MagicMock()
        request.url.path = path
        request.cookies = {"admin_token": cookie} if cookie else {}
        return request

    def test_non_admin_path_passes_through(self):
        middleware = AdminAuthMiddleware(app=MagicMock())
        request = self._make_request("/webhook/health")
        sentinel = MagicMock()
        call_next = AsyncMock(return_value=sentinel)
        result = asyncio.run(middleware.dispatch(request, call_next))
        call_next.assert_called_once_with(request)
        assert result is sentinel

    def test_login_path_passes_through_without_cookie(self):
        middleware = AdminAuthMiddleware(app=MagicMock())
        request = self._make_request("/admin/login")
        sentinel = MagicMock()
        call_next = AsyncMock(return_value=sentinel)
        result = asyncio.run(middleware.dispatch(request, call_next))
        call_next.assert_called_once_with(request)
        assert result is sentinel

    def test_protected_path_redirects_without_cookie(self):
        middleware = AdminAuthMiddleware(app=MagicMock())
        request = self._make_request("/admin")
        call_next = AsyncMock()
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            result = asyncio.run(middleware.dispatch(request, call_next))
        call_next.assert_not_called()
        assert result.status_code == 303
        assert result.headers["location"] == "/admin/login"

    def test_protected_path_passes_with_valid_cookie(self):
        middleware = AdminAuthMiddleware(app=MagicMock())
        token = _make_token()
        request = self._make_request("/admin", cookie=token)
        sentinel = MagicMock()
        call_next = AsyncMock(return_value=sentinel)
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            result = asyncio.run(middleware.dispatch(request, call_next))
        call_next.assert_called_once_with(request)
        assert result is sentinel

    def test_protected_path_redirects_with_expired_cookie(self):
        middleware = AdminAuthMiddleware(app=MagicMock())
        token = _make_token(expire_delta=timedelta(seconds=-1))
        request = self._make_request("/admin/users", cookie=token)
        call_next = AsyncMock()
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            result = asyncio.run(middleware.dispatch(request, call_next))
        call_next.assert_not_called()
        assert result.status_code == 303


# ── Login / Logout ─────────────────────────────────────────────────────────────

class TestAdminLogin:

    def test_get_login_page_returns_200(self, client):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            resp = client.get("/admin/login")
        assert resp.status_code == 200
        assert b"Bot Admin" in resp.content

    def test_logged_in_user_redirected_from_login(self, client):
        token = _make_token()
        client.cookies.set("admin_token", token)
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            resp = client.get("/admin/login")
        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin"

    def test_valid_credentials_redirect_to_dashboard(self, client):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            resp = client.post("/admin/login", data={"username": _USER, "password": _PASSWORD})
        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin"
        assert "admin_token" in resp.cookies

    def test_wrong_password_returns_401(self, client):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            resp = client.post("/admin/login", data={"username": _USER, "password": "wrong"})
        assert resp.status_code == 401
        assert b"Invalid" in resp.content

    def test_wrong_username_returns_401(self, client):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            resp = client.post("/admin/login", data={"username": "hacker", "password": _PASSWORD})
        assert resp.status_code == 401

    def test_empty_password_in_settings_always_fails(self, client):
        """If WEB_ADMIN_PASSWORD is not set (empty), login always fails."""
        settings = _mock_settings()
        settings.web_admin_password = ""
        with patch("app.api.v1.admin.get_settings", return_value=settings):
            resp = client.post("/admin/login", data={"username": _USER, "password": ""})
        assert resp.status_code == 401

    def test_logout_clears_cookie_and_redirects(self, authed_client):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            resp = authed_client.post("/admin/logout")
        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin/login"
        # Cookie deleted (max_age=0 or set to empty)
        assert "admin_token" not in resp.cookies or resp.cookies.get("admin_token") == ""


# ── Dashboard ──────────────────────────────────────────────────────────────────

class TestAdminDashboard:

    def test_dashboard_returns_200_with_counts(self, authed_client):
        session = _mock_session()
        # Three COUNT(*) queries: users, all items, available items
        session.execute = AsyncMock(side_effect=[
            _scalar_result(3),
            _scalar_result(10),
            _scalar_result(4),
        ])
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.get("/admin")
        assert resp.status_code == 200
        assert b"3" in resp.content
        assert b"10" in resp.content
        assert b"4" in resp.content

    def test_unauthenticated_dashboard_redirects(self, client):
        with patch("app.api.v1.admin.get_settings", return_value=_mock_settings()):
            resp = client.get("/admin")
        assert resp.status_code == 303
        assert "/admin/login" in resp.headers["location"]


# ── Users ──────────────────────────────────────────────────────────────────────

class TestAdminUsers:

    def _make_user(self, tid: int, role_name: str = "user"):
        u = MagicMock()
        u.id = tid
        u.telegram_user_id = tid
        u.created_at = datetime(2024, 1, 1)
        u.role = MagicMock()
        u.role.name = role_name
        return u

    def test_users_page_returns_200(self, authed_client):
        user = self._make_user(111)
        session = _mock_session()
        session.execute = AsyncMock(return_value=_scalars_result([user]))
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.get("/admin/users")
        assert resp.status_code == 200
        assert b"111" in resp.content

    def test_add_user_success(self, authed_client):
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None  # user not found
        role = MagicMock()
        role.id = 1
        role_result = MagicMock()
        role_result.scalar_one_or_none.return_value = role
        session = _mock_session()
        session.execute = AsyncMock(side_effect=[existing_result, role_result])
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.post("/admin/users", data={"telegram_id": "999", "role": "user"})
        assert resp.status_code == 303
        assert "msg=" in resp.headers["location"]
        assert "error" not in resp.headers["location"]

    def test_add_user_duplicate_returns_error(self, authed_client):
        existing = MagicMock()
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing  # already exists
        session = _mock_session()
        # list_users call + get_by_telegram_id call
        session.execute = AsyncMock(return_value=existing_result)
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.post("/admin/users", data={"telegram_id": "111", "role": "user"})
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]

    def test_add_user_invalid_id_returns_error(self, authed_client):
        session = _mock_session()
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.post("/admin/users", data={"telegram_id": "notanumber", "role": "user"})
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]

    def test_add_user_invalid_role_returns_error(self, authed_client):
        session = _mock_session()
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.post("/admin/users", data={"telegram_id": "123", "role": "superadmin"})
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]

    def test_set_role_success(self, authed_client):
        mock_user = MagicMock()
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = mock_user
        role = MagicMock()
        role.id = 2
        role_result = MagicMock()
        role_result.scalar_one_or_none.return_value = role
        session = _mock_session()
        session.execute = AsyncMock(side_effect=[user_result, role_result])
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.post("/admin/users/role", data={"telegram_id": "111", "role": "admin"})
        assert resp.status_code == 303
        assert "error" not in resp.headers["location"]

    def test_set_role_user_not_found_returns_error(self, authed_client):
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = None
        session = _mock_session()
        session.execute = AsyncMock(return_value=user_result)
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.post("/admin/users/role", data={"telegram_id": "999", "role": "admin"})
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]

    def test_delete_user_success(self, authed_client):
        del_result = MagicMock()
        del_result.rowcount = 1
        session = _mock_session()
        session.execute = AsyncMock(return_value=del_result)
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.post("/admin/users/delete", data={"telegram_id": "111"})
        assert resp.status_code == 303
        assert "error" not in resp.headers["location"]

    def test_delete_user_not_found_returns_error(self, authed_client):
        del_result = MagicMock()
        del_result.rowcount = 0
        session = _mock_session()
        session.execute = AsyncMock(return_value=del_result)
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.post("/admin/users/delete", data={"telegram_id": "999"})
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]


# ── Items ──────────────────────────────────────────────────────────────────────

class TestAdminItems:

    def _make_item(self, i: int = 1):
        item = MagicMock()
        item.id = i
        item.item_name = f"item_{i}"
        item.item_type = "spare part"
        item.item_amount = 5
        item.item_price = 9.99
        item.availability = True
        item.timestamp = datetime(2024, 1, i)
        item.chat_id = 100
        item.created_by_user_id = None
        return item

    def test_items_page_returns_200(self, authed_client):
        items = [self._make_item(i) for i in range(1, 4)]
        count_res = _scalar_result(3)
        items_res = MagicMock()
        items_res.scalars.return_value.all.return_value = items
        session = _mock_session()
        session.execute = AsyncMock(side_effect=[count_res, items_res])
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.get("/admin/items")
        assert resp.status_code == 200
        assert b"item_1" in resp.content

    def test_items_page_defaults_to_page_1(self, authed_client):
        count_res = _scalar_result(0)
        items_res = MagicMock()
        items_res.scalars.return_value.all.return_value = []
        session = _mock_session()
        session.execute = AsyncMock(side_effect=[count_res, items_res])
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.get("/admin/items")
        assert resp.status_code == 200
        assert b"Page 1" in resp.content

    def test_items_filter_params_passed_through(self, authed_client):
        count_res = _scalar_result(1)
        items_res = MagicMock()
        items_res.scalars.return_value.all.return_value = [self._make_item(1)]
        session = _mock_session()
        session.execute = AsyncMock(side_effect=[count_res, items_res])
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.get("/admin/items?search=widget&avail=yes")
        assert resp.status_code == 200
        assert b"widget" in resp.content

    def test_items_page_clamped_to_valid_range(self, authed_client):
        count_res = _scalar_result(5)
        items_res = MagicMock()
        items_res.scalars.return_value.all.return_value = []
        session = _mock_session()
        session.execute = AsyncMock(side_effect=[count_res, items_res])
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.get_db_session", _wrap_session(session)),
        ):
            resp = authed_client.get("/admin/items?page=999")
        assert resp.status_code == 200


# ── Settings ───────────────────────────────────────────────────────────────────

class TestAdminSettings:

    def test_settings_page_returns_200(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.os.path.exists", return_value=False),
        ):
            resp = authed_client.get("/admin/settings")
        assert resp.status_code == 200
        assert b"allowed_types" in resp.content.lower() or b"spare part" in resp.content

    def test_settings_page_shows_config_json_note_when_absent(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.os.path.exists", return_value=False),
        ):
            resp = authed_client.get("/admin/settings")
        assert b"config.json" in resp.content

    def test_save_settings_valid_persists_and_redirects(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.os.path.exists", return_value=False),
            patch("app.api.v1.admin._save_to_env") as mock_save,
            patch("app.core.config") as _,
        ):
            resp = authed_client.post("/admin/settings", data={
                "allowed_types": "spare part\nmiscellaneous",
                "min_len_str": "1",
                "max_len_str": "255",
                "max_item_amount": "1000000",
                "max_item_price": "999999.99",
            })
        assert resp.status_code == 303
        assert "error" not in resp.headers["location"]
        mock_save.assert_called_once()

    def test_save_settings_to_json_when_config_json_exists(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.os.path.exists", return_value=True),
            patch("app.api.v1.admin._save_to_json") as mock_save,
            patch("app.core.config") as _,
        ):
            resp = authed_client.post("/admin/settings", data={
                "allowed_types": "spare part",
                "min_len_str": "1",
                "max_len_str": "255",
                "max_item_amount": "500",
                "max_item_price": "100.00",
            })
        assert resp.status_code == 303
        mock_save.assert_called_once()

    def test_save_settings_empty_allowed_types_returns_422(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.os.path.exists", return_value=False),
        ):
            resp = authed_client.post("/admin/settings", data={
                "allowed_types": "   ",
                "min_len_str": "1",
                "max_len_str": "255",
                "max_item_amount": "1000",
                "max_item_price": "100.00",
            })
        assert resp.status_code == 422

    def test_save_settings_invalid_length_range_returns_422(self, authed_client):
        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.os.path.exists", return_value=False),
        ):
            resp = authed_client.post("/admin/settings", data={
                "allowed_types": "spare part",
                "min_len_str": "100",
                "max_len_str": "10",   # max < min
                "max_item_amount": "1000",
                "max_item_price": "100.00",
            })
        assert resp.status_code == 422

    def test_save_settings_skip_hours_checkbox_off(self, authed_client):
        """When skip_working_hours checkbox is absent (unchecked), saved value is False."""
        saved = {}

        def capture_save(path, values):
            saved.update(values)

        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.os.path.exists", return_value=False),
            patch("app.api.v1.admin._save_to_env", side_effect=capture_save),
            patch("app.core.config") as _,
        ):
            authed_client.post("/admin/settings", data={
                "allowed_types": "spare part",
                "min_len_str": "1",
                "max_len_str": "255",
                "max_item_amount": "100",
                "max_item_price": "10.00",
                # skip_working_hours NOT submitted (unchecked)
            })
        assert saved.get("skip_working_hours") is False

    def test_save_settings_skip_hours_checkbox_on(self, authed_client):
        saved = {}

        def capture_save(path, values):
            saved.update(values)

        with (
            patch("app.api.v1.admin.get_settings", return_value=_mock_settings()),
            patch("app.api.v1.admin.os.path.exists", return_value=False),
            patch("app.api.v1.admin._save_to_env", side_effect=capture_save),
            patch("app.core.config") as _,
        ):
            authed_client.post("/admin/settings", data={
                "allowed_types": "spare part",
                "min_len_str": "1",
                "max_len_str": "255",
                "max_item_amount": "100",
                "max_item_price": "10.00",
                "skip_working_hours": "on",
            })
        assert saved.get("skip_working_hours") is True


# ── _save_to_json ──────────────────────────────────────────────────────────────

class TestSaveToJson:

    def _new_values(self, **overrides):
        base = {
            "allowed_types": ["spare part"],
            "min_len_str": 2,
            "max_len_str": 100,
            "max_item_amount": 500,
            "max_item_price": 99.99,
            "skip_working_hours": True,
        }
        base.update(overrides)
        return base

    def test_updates_specified_keys(self):
        data = {
            "bot_token": "secret",
            "allowed_types": ["old"],
            "min_len_str": 1,
            "max_len_str": 255,
            "max_item_amount": 1_000_000,
            "max_item_price": 999_999.99,
            "skip_working_hours": "False",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            _save_to_json(path, self._new_values())
            with open(path) as f:
                saved = json.load(f)
            assert saved["allowed_types"] == ["spare part"]
            assert saved["min_len_str"] == 2
            assert saved["max_len_str"] == 100
            assert saved["max_item_amount"] == 500
            assert saved["max_item_price"] == 99.99
        finally:
            os.unlink(path)

    def test_preserves_unrelated_keys(self):
        data = {"bot_token": "secret", "allowed_types": ["old"], "min_len_str": 1,
                "max_len_str": 255, "max_item_amount": 100, "max_item_price": 10.0,
                "skip_working_hours": "True"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            _save_to_json(path, self._new_values())
            with open(path) as f:
                saved = json.load(f)
            assert saved["bot_token"] == "secret"
        finally:
            os.unlink(path)

    def test_skip_working_hours_stored_as_string(self):
        data = {"allowed_types": [], "min_len_str": 1, "max_len_str": 255,
                "max_item_amount": 100, "max_item_price": 10.0, "skip_working_hours": "True"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            _save_to_json(path, self._new_values(skip_working_hours=False))
            with open(path) as f:
                saved = json.load(f)
            assert saved["skip_working_hours"] == "False"
        finally:
            os.unlink(path)

    def test_adds_missing_keys_to_existing_file(self):
        """Keys absent from original file (like max_item_amount) are added."""
        data = {"bot_token": "x", "allowed_types": [], "min_len_str": 1,
                "max_len_str": 255, "skip_working_hours": "True"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            _save_to_json(path, self._new_values())
            with open(path) as f:
                saved = json.load(f)
            assert "max_item_amount" in saved
            assert "max_item_price" in saved
        finally:
            os.unlink(path)


# ── _save_to_env ───────────────────────────────────────────────────────────────

class TestSaveToEnv:

    def _new_values(self):
        return {
            "allowed_types": ["widget"],
            "min_len_str": 3,
            "max_len_str": 200,
            "max_item_amount": 999,
            "max_item_price": 49.99,
            "skip_working_hours": False,
        }

    def test_updates_existing_keys(self):
        content = "BOT_TOKEN=abc\nALLOWED_TYPES=[\"old\"]\nMIN_LEN_STR=1\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            _save_to_env(path, self._new_values())
            with open(path) as f:
                result = f.read()
            assert 'ALLOWED_TYPES=["widget"]' in result
            assert "MIN_LEN_STR=3" in result
        finally:
            os.unlink(path)

    def test_preserves_unrelated_keys(self):
        content = "BOT_TOKEN=mysecrettoken\nALLOWED_TYPES=[\"old\"]\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            _save_to_env(path, self._new_values())
            with open(path) as f:
                result = f.read()
            assert "BOT_TOKEN=mysecrettoken" in result
        finally:
            os.unlink(path)

    def test_appends_missing_keys(self):
        content = "BOT_TOKEN=abc\n"  # none of the target keys present
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            _save_to_env(path, self._new_values())
            with open(path) as f:
                result = f.read()
            assert "MAX_LEN_STR=200" in result
            assert "MAX_ITEM_AMOUNT=999" in result
            assert "SKIP_WORKING_HOURS=false" in result
        finally:
            os.unlink(path)

    def test_preserves_comments(self):
        content = "# my comment\nBOT_TOKEN=abc\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            _save_to_env(path, self._new_values())
            with open(path) as f:
                result = f.read()
            assert "# my comment" in result
        finally:
            os.unlink(path)

    def test_creates_file_if_not_exists(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "new.env")
            _save_to_env(path, self._new_values())
            assert os.path.exists(path)
            with open(path) as f:
                result = f.read()
            assert "ALLOWED_TYPES" in result

    def test_skip_working_hours_stored_as_lowercase(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("")
            path = f.name
        try:
            _save_to_env(path, {**self._new_values(), "skip_working_hours": True})
            with open(path) as f:
                result = f.read()
            assert "SKIP_WORKING_HOURS=true" in result
        finally:
            os.unlink(path)
