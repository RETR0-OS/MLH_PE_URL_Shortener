"""Integration tests for /urls endpoints."""
import json


def _seed_user(client, uid=1):
    """Create a user via the API and return its id."""
    resp = client.post(
        "/users",
        data=json.dumps({"username": f"user{uid}", "email": f"user{uid}@x.com"}),
        content_type="application/json",
    )
    return resp.get_json()["id"]


def _create_url(client, user_id, title="My URL"):
    return client.post(
        "/urls",
        data=json.dumps(
            {"user_id": user_id, "original_url": "https://example.com", "title": title}
        ),
        content_type="application/json",
    )


class TestCreateUrl:
    def test_success(self, client):
        uid = _seed_user(client)
        resp = _create_url(client, uid)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user_id"] == uid
        assert len(data["short_code"]) == 6
        assert data["is_active"] is True
        assert "created_at" in data
        assert "updated_at" in data

    def test_event_created(self, client):
        uid = _seed_user(client)
        _create_url(client, uid)
        events = client.get("/events").get_json()
        assert len(events) == 1
        assert events[0]["event_type"] == "created"
        assert events[0]["user_id"] == uid
        assert "short_code" in events[0]["details"]

    def test_nonexistent_user(self, client):
        resp = _create_url(client, 99999)
        assert resp.status_code == 400

    def test_missing_fields(self, client):
        resp = client.post(
            "/urls", data=json.dumps({}), content_type="application/json"
        )
        assert resp.status_code in (400, 422)

    def test_short_code_unique(self, client):
        uid = _seed_user(client)
        codes = set()
        for i in range(10):
            resp = _create_url(client, uid, title=f"url{i}")
            codes.add(resp.get_json()["short_code"])
        assert len(codes) == 10


class TestListUrls:
    def test_empty(self, client):
        resp = client.get("/urls")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_array(self, client):
        uid = _seed_user(client)
        _create_url(client, uid, "a")
        _create_url(client, uid, "b")
        data = client.get("/urls").get_json()
        assert len(data) == 2

    def test_filter_by_user_id(self, client):
        u1 = _seed_user(client, 1)
        u2 = _seed_user(client, 2)
        _create_url(client, u1, "u1-url")
        _create_url(client, u2, "u2-url")
        filtered = client.get(f"/urls?user_id={u1}").get_json()
        assert len(filtered) == 1
        assert filtered[0]["user_id"] == u1


class TestGetUrl:
    def test_found(self, client):
        uid = _seed_user(client)
        url_id = _create_url(client, uid).get_json()["id"]
        resp = client.get(f"/urls/{url_id}")
        assert resp.status_code == 200
        assert resp.get_json()["id"] == url_id

    def test_not_found(self, client):
        resp = client.get("/urls/99999")
        assert resp.status_code == 404


class TestUpdateUrl:
    def test_update_title(self, client):
        uid = _seed_user(client)
        url_id = _create_url(client, uid).get_json()["id"]
        resp = client.put(
            f"/urls/{url_id}",
            data=json.dumps({"title": "New Title"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "New Title"

    def test_update_is_active(self, client):
        uid = _seed_user(client)
        url_id = _create_url(client, uid).get_json()["id"]
        resp = client.put(
            f"/urls/{url_id}",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["is_active"] is False

    def test_updated_at_changes(self, client):
        uid = _seed_user(client)
        url_data = _create_url(client, uid).get_json()
        original_updated = url_data["updated_at"]
        import time

        time.sleep(0.01)
        resp = client.put(
            f"/urls/{url_data['id']}",
            data=json.dumps({"title": "Changed"}),
            content_type="application/json",
        )
        assert resp.get_json()["updated_at"] != original_updated

    def test_not_found(self, client):
        resp = client.put(
            "/urls/99999",
            data=json.dumps({"title": "x"}),
            content_type="application/json",
        )
        assert resp.status_code == 404
