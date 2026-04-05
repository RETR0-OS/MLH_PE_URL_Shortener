"""Integration tests for all untested routes and edge cases."""

import json
import time


def _make_user(client, suffix="1"):
    return client.post(
        "/users",
        data=json.dumps(
            {"username": f"user{suffix}", "email": f"user{suffix}@test.com"}
        ),
        content_type="application/json",
    ).get_json()


def _make_url(client, user_id, title="Test URL"):
    return client.post(
        "/urls",
        data=json.dumps(
            {"user_id": user_id, "original_url": "https://example.com", "title": title}
        ),
        content_type="application/json",
    ).get_json()


def _make_event(client, url_id, user_id, event_type="click", details=None):
    return client.post(
        "/events",
        data=json.dumps(
            {
                "url_id": url_id,
                "user_id": user_id,
                "event_type": event_type,
                "details": details or {},
            }
        ),
        content_type="application/json",
    )


# ===================================================================
# 1. DELETE /urls/<url_id>
# ===================================================================
class TestDeleteUrl:
    def test_successful_deletion_returns_204(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        time.sleep(0.5)
        resp = client.delete(f"/urls/{url['id']}")
        assert resp.status_code == 204

    def test_nonexistent_url_returns_404(self, client):
        resp = client.delete("/urls/99999")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "URL not found"

    def test_get_after_deletion_returns_404(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        time.sleep(0.5)
        client.delete(f"/urls/{url['id']}")
        resp = client.get(f"/urls/{url['id']}")
        assert resp.status_code == 404

    def test_events_url_id_nullified_on_cascade(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        time.sleep(0.5)

        events_before = client.get("/events").get_json()
        assert len(events_before) >= 1
        assert events_before[0]["url_id"] == url["id"]

        client.delete(f"/urls/{url['id']}")

        events_after = client.get("/events").get_json()
        for evt in events_after:
            assert evt["url_id"] is None


# ===================================================================
# 2. GET /urls/<short_code>/redirect
# ===================================================================
class TestRedirectShortCode:
    def test_successful_redirect_returns_302(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        resp = client.get(f"/urls/{url['short_code']}/redirect", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://example.com"

    def test_nonexistent_short_code_returns_404(self, client):
        resp = client.get("/urls/ZZZZZZ/redirect")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Not found"

    def test_deactivated_url_returns_410(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        client.put(
            f"/urls/{url['id']}",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
        )
        resp = client.get(f"/urls/{url['short_code']}/redirect", follow_redirects=False)
        assert resp.status_code == 410
        assert resp.get_json()["error"] == "URL is deactivated"


# ===================================================================
# 3. DELETE /users/<user_id>
# ===================================================================
class TestDeleteUser:
    def test_successful_deletion_returns_204(self, client):
        user = _make_user(client)
        resp = client.delete(f"/users/{user['id']}")
        assert resp.status_code == 204

    def test_nonexistent_user_returns_404(self, client):
        resp = client.delete("/users/99999")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "User not found"

    def test_get_after_deletion_returns_404(self, client):
        user = _make_user(client)
        client.delete(f"/users/{user['id']}")
        resp = client.get(f"/users/{user['id']}")
        assert resp.status_code == 404

    def test_users_urls_deleted_on_cascade(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        time.sleep(0.5)
        client.delete(f"/users/{user['id']}")
        resp = client.get(f"/urls/{url['id']}")
        assert resp.status_code == 404

    def test_events_nullified_on_cascade(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        time.sleep(0.5)

        events_before = client.get("/events").get_json()
        assert len(events_before) >= 1
        assert events_before[0]["user_id"] == user["id"]
        assert events_before[0]["url_id"] == url["id"]

        client.delete(f"/users/{user['id']}")

        events_after = client.get("/events").get_json()
        for evt in events_after:
            assert evt["user_id"] is None
            assert evt["url_id"] is None


# ===================================================================
# 4. GET /events/<event_id>
# ===================================================================
class TestGetEvent:
    def test_found_event_returns_200(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        time.sleep(0.5)
        events = client.get("/events").get_json()
        event_id = events[0]["id"]

        resp = client.get(f"/events/{event_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == event_id
        assert data["url_id"] == url["id"]
        assert data["user_id"] == user["id"]
        assert data["event_type"] == "created"
        assert "timestamp" in data
        assert "details" in data

    def test_nonexistent_event_returns_404(self, client):
        resp = client.get("/events/99999")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Event not found"


# ===================================================================
# 5. PUT /events/<event_id>
# ===================================================================
class TestUpdateEvent:
    def _seed_event(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        time.sleep(0.5)
        events = client.get("/events").get_json()
        return events[0], user, url

    def test_update_event_type(self, client):
        evt, _, _ = self._seed_event(client)
        resp = client.put(
            f"/events/{evt['id']}",
            data=json.dumps({"event_type": "clicked"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["event_type"] == "clicked"

    def test_update_details(self, client):
        evt, _, _ = self._seed_event(client)
        new_details = {"source": "email"}
        resp = client.put(
            f"/events/{evt['id']}",
            data=json.dumps({"details": new_details}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["details"] == new_details

    def test_update_url_id_with_valid_url(self, client):
        evt, user, _ = self._seed_event(client)
        url2 = _make_url(client, user["id"], title="Second URL")
        resp = client.put(
            f"/events/{evt['id']}",
            data=json.dumps({"url_id": url2["id"]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["url_id"] == url2["id"]

    def test_update_user_id_with_valid_user(self, client):
        evt, _, _ = self._seed_event(client)
        user2 = _make_user(client, suffix="update_uid")
        resp = client.put(
            f"/events/{evt['id']}",
            data=json.dumps({"user_id": user2["id"]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["user_id"] == user2["id"]

    def test_not_found_returns_404(self, client):
        resp = client.put(
            "/events/99999",
            data=json.dumps({"event_type": "x"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_no_json_body_returns_400(self, client):
        evt, _, _ = self._seed_event(client)
        resp = client.put(
            f"/events/{evt['id']}", data="not json", content_type="text/plain"
        )
        assert resp.status_code == 400
        assert "JSON" in resp.get_json()["error"]

    def test_empty_event_type_returns_400(self, client):
        evt, _, _ = self._seed_event(client)
        resp = client.put(
            f"/events/{evt['id']}",
            data=json.dumps({"event_type": "  "}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_string_event_type_returns_400(self, client):
        evt, _, _ = self._seed_event(client)
        resp = client.put(
            f"/events/{evt['id']}",
            data=json.dumps({"event_type": 123}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_integer_url_id_returns_400(self, client):
        evt, _, _ = self._seed_event(client)
        resp = client.put(
            f"/events/{evt['id']}",
            data=json.dumps({"url_id": "abc"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_integer_user_id_returns_400(self, client):
        evt, _, _ = self._seed_event(client)
        resp = client.put(
            f"/events/{evt['id']}",
            data=json.dumps({"user_id": "abc"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_nonexistent_url_id_returns_404(self, client):
        evt, _, _ = self._seed_event(client)
        resp = client.put(
            f"/events/{evt['id']}",
            data=json.dumps({"url_id": 99999}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_nonexistent_user_id_returns_404(self, client):
        evt, _, _ = self._seed_event(client)
        resp = client.put(
            f"/events/{evt['id']}",
            data=json.dumps({"user_id": 99999}),
            content_type="application/json",
        )
        assert resp.status_code == 404


# ===================================================================
# 6. POST /events
# ===================================================================
class TestCreateEvent:
    def test_successful_creation_returns_201(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        resp = _make_event(client, url["id"], user["id"], "click")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["event_type"] == "click"
        assert data["url_id"] == url["id"]
        assert data["user_id"] == user["id"]
        assert "id" in data
        assert "timestamp" in data

    def test_missing_body_returns_400(self, client):
        resp = client.post("/events", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_missing_url_id_returns_400(self, client):
        user = _make_user(client)
        resp = client.post(
            "/events",
            data=json.dumps({"user_id": user["id"], "event_type": "click"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_missing_user_id_returns_400(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        resp = client.post(
            "/events",
            data=json.dumps({"url_id": url["id"], "event_type": "click"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_missing_event_type_returns_400(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        resp = client.post(
            "/events",
            data=json.dumps({"url_id": url["id"], "user_id": user["id"]}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_integer_url_id_returns_400(self, client):
        user = _make_user(client)
        resp = client.post(
            "/events",
            data=json.dumps(
                {"url_id": "abc", "user_id": user["id"], "event_type": "click"}
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_integer_user_id_returns_400(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        resp = client.post(
            "/events",
            data=json.dumps(
                {"url_id": url["id"], "user_id": "abc", "event_type": "click"}
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_string_event_type_returns_400(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        resp = client.post(
            "/events",
            data=json.dumps(
                {"url_id": url["id"], "user_id": user["id"], "event_type": 123}
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_dict_details_returns_400(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        resp = client.post(
            "/events",
            data=json.dumps(
                {
                    "url_id": url["id"],
                    "user_id": user["id"],
                    "event_type": "click",
                    "details": "not a dict",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_nonexistent_url_id_returns_404(self, client):
        user = _make_user(client)
        resp = client.post(
            "/events",
            data=json.dumps(
                {"url_id": 99999, "user_id": user["id"], "event_type": "click"}
            ),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_nonexistent_user_id_returns_404(self, client):
        user = _make_user(client)
        url = _make_url(client, user["id"])
        resp = client.post(
            "/events",
            data=json.dumps(
                {"url_id": url["id"], "user_id": 99999, "event_type": "click"}
            ),
            content_type="application/json",
        )
        assert resp.status_code == 404


# ===================================================================
# 7. Filters and pagination
# ===================================================================
class TestUrlFilters:
    def test_is_active_true_filter(self, client):
        user = _make_user(client)
        url1 = _make_url(client, user["id"], title="active")
        url2 = _make_url(client, user["id"], title="inactive")
        client.put(
            f"/urls/{url2['id']}",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
        )
        filtered = client.get("/urls?is_active=true").get_json()
        ids = [u["id"] for u in filtered]
        assert url1["id"] in ids
        assert url2["id"] not in ids

    def test_is_active_false_filter(self, client):
        user = _make_user(client)
        url1 = _make_url(client, user["id"], title="active")
        url2 = _make_url(client, user["id"], title="inactive")
        client.put(
            f"/urls/{url2['id']}",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
        )
        filtered = client.get("/urls?is_active=false").get_json()
        ids = [u["id"] for u in filtered]
        assert url2["id"] in ids
        assert url1["id"] not in ids

    def test_cursor_returns_ids_greater_than_n(self, client):
        user = _make_user(client)
        url1 = _make_url(client, user["id"], title="first")
        url2 = _make_url(client, user["id"], title="second")
        url3 = _make_url(client, user["id"], title="third")
        filtered = client.get(f"/urls?cursor={url1['id']}").get_json()
        ids = [u["id"] for u in filtered]
        assert url1["id"] not in ids
        assert url2["id"] in ids
        assert url3["id"] in ids

    def test_cursor_with_per_page_limits_results(self, client):
        user = _make_user(client)
        _make_url(client, user["id"], title="a")
        _make_url(client, user["id"], title="b")
        _make_url(client, user["id"], title="c")
        all_urls = client.get("/urls").get_json()
        first_id = all_urls[0]["id"]
        filtered = client.get(f"/urls?cursor={first_id}&per_page=1").get_json()
        assert len(filtered) == 1


class TestUserFilters:
    def test_cursor_returns_ids_greater_than_n(self, client):
        u1 = _make_user(client, suffix="cu1")
        u2 = _make_user(client, suffix="cu2")
        u3 = _make_user(client, suffix="cu3")
        filtered = client.get(f"/users?cursor={u1['id']}").get_json()
        ids = [u["id"] for u in filtered]
        assert u1["id"] not in ids
        assert u2["id"] in ids
        assert u3["id"] in ids


class TestEventFilters:
    def _seed_multiple_events(self, client):
        user = _make_user(client)
        url1 = _make_url(client, user["id"], title="url-a")
        url2 = _make_url(client, user["id"], title="url-b")
        time.sleep(0.5)
        _make_event(client, url1["id"], user["id"], "click")
        _make_event(client, url2["id"], user["id"], "view")
        return user, url1, url2

    def test_filter_by_url_id(self, client):
        user, url1, url2 = self._seed_multiple_events(client)
        filtered = client.get(f"/events?url_id={url1['id']}").get_json()
        for evt in filtered:
            assert evt["url_id"] == url1["id"]

    def test_filter_by_user_id(self, client):
        user, _, _ = self._seed_multiple_events(client)
        user2 = _make_user(client, suffix="other")
        filtered = client.get(f"/events?user_id={user2['id']}").get_json()
        assert len(filtered) == 0

        all_events = client.get(f"/events?user_id={user['id']}").get_json()
        assert len(all_events) > 0
        for evt in all_events:
            assert evt["user_id"] == user["id"]

    def test_filter_by_event_type(self, client):
        self._seed_multiple_events(client)
        filtered = client.get("/events?event_type=created").get_json()
        for evt in filtered:
            assert evt["event_type"] == "created"

    def test_cursor_paginates(self, client):
        self._seed_multiple_events(client)
        all_events = client.get("/events").get_json()
        assert len(all_events) >= 2
        first_id = all_events[0]["id"]
        filtered = client.get(f"/events?cursor={first_id}").get_json()
        for evt in filtered:
            assert evt["id"] > first_id


# ===================================================================
# 8. V1 prefix routes
# ===================================================================
class TestV1Prefix:
    def test_v1_get_users(self, client):
        _make_user(client)
        resp = client.get("/v1/users")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_v1_post_urls(self, client):
        user = _make_user(client)
        resp = client.post(
            "/v1/urls",
            data=json.dumps(
                {
                    "user_id": user["id"],
                    "original_url": "https://example.com",
                    "title": "V1 URL",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "V1 URL"
        assert len(data["short_code"]) == 6
