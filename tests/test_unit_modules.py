"""Unit tests for modules with zero coverage:
auth, middleware, logging_config, event_writer, shortcode edge cases, validation edge cases.
"""

import datetime
import logging
import os
import uuid
from unittest.mock import patch

import pytest

from app.utils.shortcode import generate_short_code
from app.utils.validation import (
    validate_url_create,
    validate_url_update,
    validate_user_create,
)


# ---------------------------------------------------------------------------
# 1. app/auth.py – API Key Authentication
# ---------------------------------------------------------------------------
class TestApiKeyAuth:
    """Needs its own Flask app since the session-scoped app has no API_KEY."""

    @pytest.fixture()
    def auth_app(self):
        old = os.environ.get("API_KEY")
        os.environ["API_KEY"] = "test-secret-key"
        from app import create_app

        application = create_app()
        application.config["TESTING"] = True
        yield application
        if old is None:
            os.environ.pop("API_KEY", None)
        else:
            os.environ["API_KEY"] = old

    @pytest.fixture()
    def auth_client(self, auth_app):
        return auth_app.test_client()

    def test_no_api_key_env_allows_requests(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_missing_key_returns_401(self, auth_client):
        resp = auth_client.get("/health/ready")
        assert resp.status_code == 200
        resp = auth_client.get("/users")
        assert resp.status_code == 401

    def test_wrong_key_returns_401(self, auth_client):
        resp = auth_client.get("/users", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_correct_key_succeeds(self, auth_client):
        resp = auth_client.get("/users", headers={"X-API-Key": "test-secret-key"})
        assert resp.status_code != 401

    def test_exempt_paths_bypass_auth(self, auth_client):
        for path in ("/health", "/health/ready"):
            resp = auth_client.get(path)
            assert resp.status_code == 200, f"{path} should be exempt"


# ---------------------------------------------------------------------------
# 2. app/middleware.py – Request ID & Timing
# ---------------------------------------------------------------------------
class TestMiddleware:
    def test_response_contains_request_id(self, client):
        resp = client.get("/health")
        assert "X-Request-ID" in resp.headers

    def test_client_request_id_propagated(self, client):
        custom_id = "my-custom-request-id"
        resp = client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.headers["X-Request-ID"] == custom_id

    def test_auto_generated_request_id_is_uuid(self, client):
        resp = client.get("/health")
        rid = resp.headers["X-Request-ID"]
        parsed = uuid.UUID(rid)
        assert parsed.hex == rid.replace("-", "")

    def test_checkpoint_outside_request_context_is_noop(self, app):
        from app.middleware import checkpoint

        with app.app_context():
            result = checkpoint("test")
            assert result is None


# ---------------------------------------------------------------------------
# 3. app/logging_config.py
# ---------------------------------------------------------------------------
class TestLoggingConfig:
    def test_setup_configures_json_formatter(self):
        from pythonjsonlogger.json import JsonFormatter

        from app.logging_config import setup_logging

        setup_logging()
        root = logging.getLogger()
        assert len(root.handlers) >= 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_setup_sets_werkzeug_to_warning(self):
        from app.logging_config import setup_logging

        setup_logging()
        assert logging.getLogger("werkzeug").level == logging.WARNING

    def test_custom_level_parameter(self):
        from app.logging_config import setup_logging

        setup_logging(level=logging.DEBUG)
        root = logging.getLogger()
        assert root.level == logging.DEBUG


# ---------------------------------------------------------------------------
# 4. app/event_writer.py
# ---------------------------------------------------------------------------
class TestEventWriter:
    @patch("app.event_writer._executor")
    def test_log_event_submits_to_executor(self, mock_executor):
        from app.event_writer import log_event

        log_event(url_id=1, user_id=2, event_type="click")
        mock_executor.submit.assert_called_once()
        args = mock_executor.submit.call_args
        assert args[0][0].__name__ == "_write_event"

    @patch("app.event_writer._executor")
    def test_log_event_payload_structure(self, mock_executor):
        from app.event_writer import log_event

        log_event(url_id=10, user_id=20, event_type="create", details={"foo": "bar"})
        payload = mock_executor.submit.call_args[0][1]
        assert payload["url_id"] == 10
        assert payload["user_id"] == 20
        assert payload["event_type"] == "create"
        assert payload["details"] == {"foo": "bar"}
        assert isinstance(payload["timestamp"], datetime.datetime)

    @patch("app.event_writer.logger")
    def test_write_event_exception_logs_error(self, mock_logger):
        from app.event_writer import _write_event

        with patch("app.models.event.Event") as MockEvent:
            MockEvent.create.side_effect = RuntimeError("db down")
            _write_event({"url_id": 1, "event_type": "x"})

        mock_logger.exception.assert_called_once_with("Failed to log event")


# ---------------------------------------------------------------------------
# 5. Shortcode edge cases
# ---------------------------------------------------------------------------
class TestShortcodeEdgeCases:
    def test_length_zero_returns_empty(self):
        assert generate_short_code(length=0) == ""

    def test_length_one_returns_single_char(self):
        code = generate_short_code(length=1)
        assert len(code) == 1
        assert code.isalnum()


# ---------------------------------------------------------------------------
# 6. Validation edge cases
# ---------------------------------------------------------------------------
class TestValidationEdgeCases:
    def test_url_create_non_string_original_url(self):
        errors = validate_url_create(
            {"user_id": 1, "original_url": 12345, "title": "t"}
        )
        assert "original_url" in errors

    def test_url_update_empty_dict_no_errors(self):
        errors = validate_url_update({})
        assert errors == {}

    def test_user_create_empty_string_username(self):
        errors = validate_user_create({"username": "", "email": "a@b.com"})
        assert "username" in errors
