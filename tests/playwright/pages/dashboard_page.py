"""Page Object Model for the Admin dashboard page (/admin or /admin/).

HTML structure (dashboard.html + base.html):
    <nav class="navbar">
        <a href="/admin">Dashboard</a>
        <a href="/admin/users">Users</a>
        <a href="/admin/items">Items</a>
        <a href="/admin/settings">Settings</a>
        <a href="/admin/vpn">VPN</a>
        <button … >Logout</button>
    </nav>
    <h1>Dashboard</h1>
    <div class="stat-card">…</div>  × 3  (total_users, total_items, available_items)
"""
from playwright.sync_api import Page
from pages.base_page import BasePage


class DashboardPage(BasePage):
    """Admin dashboard page."""

    PATH = "/admin/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # Locators — keep in sync with app/templates/dashboard.html + base.html
        self.heading = page.get_by_role("heading", name="Dashboard")
        self.nav_users = page.get_by_role("link", name="Users")
        self.nav_items = page.get_by_role("link", name="Items")
        self.nav_settings = page.get_by_role("link", name="Settings")
        self.nav_vpn = page.get_by_role("link", name="VPN")
        self.logout_button = page.get_by_role("button", name="Logout")
        # Stat cards (order: total_users, total_items, available_items)
        self.stat_cards = page.locator(".stat-card")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self) -> None:
        """Open the dashboard page."""
        super().navigate(self.PATH)

    def go_to_users(self) -> None:
        self.nav_users.click()

    def go_to_items(self) -> None:
        self.nav_items.click()

    def go_to_settings(self) -> None:
        self.nav_settings.click()

    def go_to_vpn(self) -> None:
        self.nav_vpn.click()

    def logout(self) -> None:
        self.logout_button.click()

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_loaded(self) -> bool:
        """Return True when the Dashboard heading is visible."""
        return self.heading.is_visible()

    def stat_value(self, index: int) -> str:
        """Return the numeric value text from stat card at *index* (0-based)."""
        return self.stat_cards.nth(index).locator(".value").inner_text()
