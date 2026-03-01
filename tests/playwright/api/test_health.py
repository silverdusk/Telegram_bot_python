"""API regression tests — health-check and root endpoints.

These are pure API tests (no browser UI).  They use the session-scoped
``api_request_context`` fixture from ``conftest.py``.

Run
---
    pytest tests/playwright/api/test_health.py -m regression -v
"""
import pytest
from playwright.sync_api import APIRequestContext


# ---------------------------------------------------------------------------
# GET /webhook/health
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestHealthEndpoint:
    """Regression suite for GET /webhook/health."""

    def test_status_200(self, api_request_context: APIRequestContext) -> None:
        """Should return HTTP 200."""
        response = api_request_context.get("/webhook/health")
        assert response.status == 200

    def test_body_equals_ok(self, api_request_context: APIRequestContext) -> None:
        """Body should be exactly {"status": "ok"}."""
        response = api_request_context.get("/webhook/health")
        assert response.json() == {"status": "ok"}

    def test_content_type_is_json(self, api_request_context: APIRequestContext) -> None:
        """Content-Type header should indicate JSON."""
        response = api_request_context.get("/webhook/health")
        assert "application/json" in response.headers.get("content-type", "")

    def test_post_method_not_allowed(self, api_request_context: APIRequestContext) -> None:
        """POST to /webhook/health should return 405."""
        response = api_request_context.post("/webhook/health", data={})
        assert response.status == 405


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestRootEndpoint:
    """Regression suite for GET /."""

    def test_status_200(self, api_request_context: APIRequestContext) -> None:
        """Root endpoint should return HTTP 200."""
        response = api_request_context.get("/")
        assert response.status == 200

    def test_has_status_running(self, api_request_context: APIRequestContext) -> None:
        """Body should contain {"status": "running"}."""
        body = api_request_context.get("/").json()
        assert body.get("status") == "running"

    def test_has_message_field(self, api_request_context: APIRequestContext) -> None:
        """Body should contain a non-empty "message" field."""
        body = api_request_context.get("/").json()
        assert "message" in body
        assert body["message"]

    def test_content_type_is_json(self, api_request_context: APIRequestContext) -> None:
        """Content-Type header should indicate JSON."""
        response = api_request_context.get("/")
        assert "application/json" in response.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# POST /webhook/telegram
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestWebhookEndpoint:
    """Regression suite for POST /webhook/telegram (input validation only).

    Note: these tests intentionally send malformed payloads.  They do NOT
    send real Telegram updates — that would require a valid bot token and
    a live Telegram connection.
    """

    def test_rejects_empty_json_object(
        self, api_request_context: APIRequestContext
    ) -> None:
        """Empty JSON object should return 422 (missing required Telegram fields)."""
        response = api_request_context.post("/webhook/telegram", json={})
        assert response.status == 422

    def test_rejects_non_json_body(
        self, api_request_context: APIRequestContext
    ) -> None:
        """Non-JSON body should return 422."""
        response = api_request_context.post(
            "/webhook/telegram",
            data="not-json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 422

    def test_get_method_not_allowed(
        self, api_request_context: APIRequestContext
    ) -> None:
        """GET /webhook/telegram should return 405."""
        response = api_request_context.get("/webhook/telegram")
        assert response.status == 405
