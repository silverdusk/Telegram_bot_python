"""Page Object Model for the Admin login page (/admin/login).

HTML structure (login.html):
    <input id="username" name="username">
    <input id="password" name="password">
    <button type="submit">Sign in</button>
    <div class="flash flash-error">…</div>   ← shown on bad credentials
"""
from playwright.sync_api import Page
from pages.base_page import BasePage


class LoginPage(BasePage):
    """Admin login page."""

    PATH = "/admin/login"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # Locators — keep in sync with app/templates/login.html
        self.username_input = page.locator("#username")
        self.password_input = page.locator("#password")
        self.submit_button = page.get_by_role("button", name="Sign in")
        self.error_banner = page.locator(".flash.flash-error")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def navigate(self) -> None:
        """Open the login page."""
        super().navigate(self.PATH)

    def login(self, username: str, password: str) -> None:
        """Fill the credentials form and submit it."""
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.submit_button.click()

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def get_error_text(self) -> str:
        """Return the text of the error flash banner (may be empty)."""
        return self.error_banner.inner_text()

    def has_error(self) -> bool:
        """Return True if an error banner is currently visible."""
        return self.error_banner.is_visible()

    def is_on_login_page(self) -> bool:
        """Return True when the browser is still on the login path."""
        return self.PATH in self.page.url
