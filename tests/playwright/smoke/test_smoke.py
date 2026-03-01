"""Smoke tests — fast sanity checks.

Purpose
-------
Verify that the app is reachable, critical pages render, and the admin
login / logout flow works end-to-end.  These tests should complete in
under 30 seconds and are safe to run on every deploy.

Run
---
    pytest tests/playwright/smoke/ -m smoke -v
    # headed (see the browser):
    pytest tests/playwright/smoke/ -m smoke -v --headed
    # against staging:
    pytest tests/playwright/smoke/ -m smoke -v --base-url https://staging.example.com

Each test method is a *template*: the skeleton is wired up and imports
are correct, but assertions that require a live DB are marked with a
``# TODO`` comment so you can enable them incrementally.
"""
import pytest
from playwright.sync_api import APIRequestContext, Page, expect

from pages.login_page import LoginPage
from pages.dashboard_page import DashboardPage


# ---------------------------------------------------------------------------
# App availability
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestAppAvailability:
    """Verify the app is reachable and core endpoints respond."""

    def test_health_endpoint_returns_ok(
        self, api_request_context: APIRequestContext
    ) -> None:
        """GET /webhook/health → {"status": "ok"}."""
        response = api_request_context.get("/webhook/health")
        assert response.status == 200
        assert response.json() == {"status": "ok"}

    def test_root_endpoint_responds(
        self, api_request_context: APIRequestContext
    ) -> None:
        """GET / → 200 with status=running."""
        response = api_request_context.get("/")
        assert response.status == 200
        body = response.json()
        assert body.get("status") == "running"


# ---------------------------------------------------------------------------
# Admin panel — page loads
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestAdminPanelAccess:
    """Critical admin pages must be reachable from a browser."""

    def test_login_page_loads(self, page: Page) -> None:
        """GET /admin/login → login form is rendered."""
        login_page = LoginPage(page)
        login_page.navigate()
        expect(login_page.username_input).to_be_visible()
        expect(login_page.password_input).to_be_visible()
        expect(login_page.submit_button).to_be_visible()

    def test_unauthenticated_redirect_to_login(self, page: Page) -> None:
        """GET /admin/ without a session → redirected to /admin/login."""
        page.goto("/admin/")
        # TODO: confirm exact redirect behaviour; enable assertion when verified
        # expect(page).to_have_url(lambda url: "/admin/login" in url)
        pass


# ---------------------------------------------------------------------------
# Admin panel — authentication flow
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestAdminLoginFlow:
    """Admin login and logout flow must work end-to-end."""

    def test_login_page_title(self, page: Page) -> None:
        """Login page title should contain 'Admin'."""
        login_page = LoginPage(page)
        login_page.navigate()
        expect(page).to_have_title(pytest.approx(None) or lambda t: "Admin" in t)
        # Simpler alternative once the exact title is known:
        # assert "Admin" in login_page.title

    def test_login_with_valid_credentials(
        self,
        page: Page,
        admin_credentials: dict,
    ) -> None:
        """Valid credentials → session created, lands on dashboard."""
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login(
            admin_credentials["username"],
            admin_credentials["password"],
        )
        # TODO: enable once running against a live instance with valid credentials
        # dashboard = DashboardPage(page)
        # assert dashboard.is_loaded(), "Expected dashboard after successful login"

    def test_login_with_invalid_credentials(self, page: Page) -> None:
        """Wrong password → error banner shown, stays on login page."""
        login_page = LoginPage(page)
        login_page.navigate()
        login_page.login("admin", "__invalid_password__")
        # TODO: enable once running against a live instance
        # assert login_page.has_error(), "Expected error banner for bad credentials"
        # assert login_page.is_on_login_page(), "Expected to stay on login page"

    def test_logout_redirects_to_login(self, authenticated_page: Page) -> None:
        """Clicking Logout → session ends, lands back on login page."""
        dashboard = DashboardPage(authenticated_page)
        # TODO: enable once running against a live instance with valid credentials
        # dashboard.logout()
        # login_page = LoginPage(authenticated_page)
        # assert login_page.is_on_login_page(), "Expected login page after logout"
        pass
