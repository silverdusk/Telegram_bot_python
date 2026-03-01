"""Base Page Object Model.

All page classes inherit from ``BasePage``.  It provides the Playwright
``page`` instance and common navigation / wait helpers.
"""
from playwright.sync_api import Page


class BasePage:
    """Minimal base page with navigation helpers."""

    def __init__(self, page: Page) -> None:
        self.page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, path: str = "/") -> None:
        """Go to *path* relative to the configured base URL and wait for
        the DOM to be interactive."""
        self.page.goto(path)
        self.page.wait_for_load_state("domcontentloaded")

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def current_url(self) -> str:
        return self.page.url

    @property
    def title(self) -> str:
        return self.page.title()
