"""Shared fixtures for all Playwright tests.

Usage
-----
Run smoke tests:
    pytest tests/playwright/ -m smoke -v

Run regression tests:
    pytest tests/playwright/ -m regression -v

Run everything:
    pytest tests/playwright/ -v

Override the base URL:
    PLAYWRIGHT_BASE_URL=http://staging.example.com pytest tests/playwright/ -v
    # or via CLI:
    pytest tests/playwright/ --base-url http://staging.example.com -v

Override admin credentials:
    WEB_ADMIN_USER=myadmin WEB_ADMIN_PASSWORD=secret pytest tests/playwright/ -v
"""
import os
import sys
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Playwright, APIRequestContext, Page

# ---------------------------------------------------------------------------
# Path bootstrap
# Make `pages/` importable as a top-level package from anywhere inside
# tests/playwright/ without requiring __init__.py files.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_request_context(
    playwright: Playwright, base_url: str
) -> Generator[APIRequestContext, None, None]:
    """Session-scoped API request context.

    Shares a single context across the entire test session — suitable for
    stateless endpoint tests (health, root, unauthenticated admin routes).

    For tests that require an authenticated session, use
    ``admin_api_context`` defined in ``tests/playwright/api/test_admin.py``.
    """
    context = playwright.request.new_context(base_url=base_url)
    yield context
    context.dispose()


@pytest.fixture
def admin_credentials() -> dict:
    """Admin panel credentials.

    Reads from environment variables so CI secrets are never hard-coded.
    Falls back to the defaults from ``.env.example``.
    """
    return {
        "username": os.environ.get("WEB_ADMIN_USER", "admin"),
        "password": os.environ.get("WEB_ADMIN_PASSWORD", "changeme"),
    }


@pytest.fixture
def authenticated_page(page: Page, admin_credentials: dict) -> Page:
    """Browser ``Page`` fixture already logged in to the admin panel.

    Use this instead of the plain ``page`` fixture in any test that
    requires an active admin session.

    Example::

        def test_dashboard_heading(authenticated_page: Page) -> None:
            authenticated_page.goto("/admin/")
            expect(authenticated_page.locator("h1")).to_have_text("Dashboard")
    """
    from pages.login_page import LoginPage  # noqa: PLC0415

    login = LoginPage(page)
    login.navigate()
    login.login(admin_credentials["username"], admin_credentials["password"])
    return page
