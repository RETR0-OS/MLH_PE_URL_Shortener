"""Integration tests for /events endpoint."""

import json
import time


class TestListEvents:
    def test_empty(self, client):
        resp = client.get("/events")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_event_from_url_creation(self, client):
        user = client.post(
            "/users",
            data=json.dumps({"username": "eu", "email": "eu@x.com"}),
            content_type="application/json",
        ).get_json()
        url = client.post(
            "/urls",
            data=json.dumps(
                {
                    "user_id": user["id"],
                    "original_url": "https://example.com",
                    "title": "T",
                }
            ),
            content_type="application/json",
        ).get_json()

        time.sleep(0.5)
        events = client.get("/events").get_json()
        assert len(events) == 1
        evt = events[0]
        assert evt["url_id"] == url["id"]
        assert evt["user_id"] == user["id"]
        assert evt["event_type"] == "created"
        assert evt["details"]["short_code"] == url["short_code"]
        assert evt["details"]["original_url"] == "https://example.com"
        assert "timestamp" in evt


class TestResponseFormat:
    """Verify JSON response fields match the OpenAPI spec exactly."""

    def test_user_fields(self, client):
        resp = client.post(
            "/users",
            data=json.dumps({"username": "rf", "email": "rf@x.com"}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert set(data.keys()) == {"id", "username", "email", "created_at"}
        assert isinstance(data["id"], int)
        assert isinstance(data["username"], str)
        assert "T" in data["created_at"]
        assert "Z" not in data["created_at"]

    def test_url_fields(self, client):
        uid = client.post(
            "/users",
            data=json.dumps({"username": "uf", "email": "uf@x.com"}),
            content_type="application/json",
        ).get_json()["id"]
        resp = client.post(
            "/urls",
            data=json.dumps(
                {"user_id": uid, "original_url": "https://x.com", "title": "T"}
            ),
            content_type="application/json",
        )
        data = resp.get_json()
        expected_keys = {
            "id",
            "user_id",
            "short_code",
            "original_url",
            "title",
            "is_active",
            "created_at",
            "updated_at",
        }
        assert set(data.keys()) == expected_keys
        assert isinstance(data["is_active"], bool)

    def test_event_fields(self, client):
        uid = client.post(
            "/users",
            data=json.dumps({"username": "ef", "email": "ef@x.com"}),
            content_type="application/json",
        ).get_json()["id"]
        client.post(
            "/urls",
            data=json.dumps(
                {"user_id": uid, "original_url": "https://x.com", "title": "T"}
            ),
            content_type="application/json",
        )
        time.sleep(0.5)
        evt = client.get("/events").get_json()[0]
        expected_keys = {
            "id",
            "url_id",
            "user_id",
            "event_type",
            "timestamp",
            "details",
        }
        assert set(evt.keys()) == expected_keys
        assert isinstance(evt["details"], dict)

    def test_error_format_404(self, client):
        resp = client.get("/users/99999")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_error_format_json_not_html(self, client):
        resp = client.get("/nonexistent-path")
        assert resp.status_code == 404
        assert resp.content_type.startswith("application/json")

    def test_post_returns_201(self, client):
        resp = client.post(
            "/users",
            data=json.dumps({"username": "s201", "email": "s201@x.com"}),
            content_type="application/json",
        )
        assert resp.status_code == 201
