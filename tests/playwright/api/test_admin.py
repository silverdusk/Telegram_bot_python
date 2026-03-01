"""API regression tests — admin panel endpoints.

These tests hit the admin HTTP routes directly (no browser).  Two
request contexts are used:

* ``api_request_context`` (from conftest) — *unauthenticated*, shared
  across the session.  Used to verify that protected routes reject
  anonymous requests.

* ``admin_api_context`` — *authenticated*, module-scoped.  Performs a
  login via POST /admin/login once and reuses the resulting session
  cookie for all authenticated-route tests.

Run
---
    pytest tests/playwright/api/test_admin.py -m regression -v

Override credentials (defaults match .env.example):
    WEB_ADMIN_USER=admin WEB_ADMIN_PASSWORD=changeme pytest …
"""
import os

import pytest
from playwright.sync_api import Playwright, APIRequestContext


# ---------------------------------------------------------------------------
# Module-scoped authenticated context
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def admin_api_context(
    playwright: Playwright, base_url: str
) -> APIRequestContext:
    """Authenticated API context for admin-panel regression tests.

    Logs in once (module scope) and stores the session cookie so that
    all subsequent requests in this module are pre-authenticated.
    """
    username = os.environ.get("WEB_ADMIN_USER", "admin")
    password = os.environ.get("WEB_ADMIN_PASSWORD", "changeme")

    context = playwright.request.new_context(base_url=base_url)
    response = context.post(
        "/admin/login",
        form={"username": username, "password": password},
    )
    # A successful login redirects (3xx) → Playwright follows it → 200.
    # Any 2xx/3xx is acceptable at this point; an exact assertion would be
    # too brittle against redirect chains.
    assert response.status < 400, (
        f"Admin login failed (HTTP {response.status}). "
        "Check WEB_ADMIN_USER / WEB_ADMIN_PASSWORD env vars."
    )
    yield context
    context.dispose()


# ---------------------------------------------------------------------------
# Unauthenticated access — protected routes must reject anonymous requests
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestAdminUnauthenticated:
    """Protected admin routes must not be accessible without a session."""

    @pytest.mark.parametrize(
        "path",
        [
            "/admin/",
            "/admin/users",
            "/admin/items",
            "/admin/settings",
            "/admin/vpn",
        ],
    )
    def test_route_requires_auth(
        self,
        api_request_context: APIRequestContext,
        path: str,
    ) -> None:
        """GET *path* without a session must not return the page content.

        Acceptable outcomes:
        * HTTP 3xx redirect to /admin/login (before Playwright follows it)
        * HTTP 200 that is the *login page* (after redirect is followed)
        * HTTP 401 / 403

        Not acceptable: 200 with the actual protected page content.
        """
        response = api_request_context.get(path)
        # After Playwright follows any redirect the URL should be the login page.
        is_redirected_to_login = "/admin/login" in response.url
        is_rejected = response.status in (401, 403)
        assert is_redirected_to_login or is_rejected, (
            f"Expected redirect to login or 401/403 for {path}, "
            f"got HTTP {response.status} at {response.url}"
        )


# ---------------------------------------------------------------------------
# Login endpoint
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestAdminLogin:
    """POST /admin/login input-validation and error handling."""

    def test_invalid_credentials_render_login_page(
        self, api_request_context: APIRequestContext
    ) -> None:
        """Wrong password → login page re-rendered with an error (HTTP 200)."""
        response = api_request_context.post(
            "/admin/login",
            form={"username": "admin", "password": "__wrong__"},
        )
        assert response.status == 200
        # TODO: assert error text in response body once confirmed:
        # assert "Invalid" in response.text() or "error" in response.text().lower()

    def test_empty_form_returns_error(
        self, api_request_context: APIRequestContext
    ) -> None:
        """Submitting an empty form → login page with error or 400/422."""
        response = api_request_context.post("/admin/login", form={})
        assert response.status in (200, 400, 422), (
            f"Unexpected status {response.status} for empty login form"
        )


# ---------------------------------------------------------------------------
# Authenticated pages — must return HTTP 200 with content
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestAdminAuthenticatedPages:
    """All authenticated admin pages must respond with HTTP 200."""

    def test_dashboard_loads(self, admin_api_context: APIRequestContext) -> None:
        """GET /admin/ → 200."""
        response = admin_api_context.get("/admin/")
        assert response.status == 200
        # TODO: assert "Dashboard" in response.text()

    def test_users_page_loads(self, admin_api_context: APIRequestContext) -> None:
        """GET /admin/users → 200."""
        response = admin_api_context.get("/admin/users")
        assert response.status == 200

    def test_items_page_loads(self, admin_api_context: APIRequestContext) -> None:
        """GET /admin/items → 200."""
        response = admin_api_context.get("/admin/items")
        assert response.status == 200

    def test_settings_page_loads(self, admin_api_context: APIRequestContext) -> None:
        """GET /admin/settings → 200."""
        response = admin_api_context.get("/admin/settings")
        assert response.status == 200

    def test_vpn_page_loads(self, admin_api_context: APIRequestContext) -> None:
        """GET /admin/vpn → 200."""
        response = admin_api_context.get("/admin/vpn")
        assert response.status == 200


# ---------------------------------------------------------------------------
# User management POST endpoints
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestAdminUserEndpoints:
    """POST endpoints for user management — input validation."""

    def test_add_user_missing_fields(
        self, admin_api_context: APIRequestContext
    ) -> None:
        """POST /admin/users with empty body → 400 or re-renders with error."""
        response = admin_api_context.post("/admin/users", form={})
        assert response.status in (200, 400, 422), (
            f"Unexpected status {response.status}"
        )

    def test_set_role_missing_fields(
        self, admin_api_context: APIRequestContext
    ) -> None:
        """POST /admin/users/role with empty body → 400 or re-renders."""
        response = admin_api_context.post("/admin/users/role", form={})
        assert response.status in (200, 400, 422)

    def test_delete_user_missing_fields(
        self, admin_api_context: APIRequestContext
    ) -> None:
        """POST /admin/users/delete with empty body → 400 or re-renders."""
        response = admin_api_context.post("/admin/users/delete", form={})
        assert response.status in (200, 400, 422)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestAdminLogout:
    """POST /admin/logout should invalidate the session."""

    def test_logout_redirects_to_login(
        self, admin_api_context: APIRequestContext
    ) -> None:
        """POST /admin/logout → redirect to /admin/login (or 200 login page)."""
        response = admin_api_context.post("/admin/logout")
        assert response.status < 400, f"Logout failed: HTTP {response.status}"
        # After logout the session cookie is cleared; subsequent requests should
        # redirect to the login page.
        # TODO: assert "/admin/login" in response.url after Playwright follows redirect
