import io
import json


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Users – CRUD
# ---------------------------------------------------------------------------


def test_create_user(client):
    resp = client.post("/users", json={"username": "alice", "email": "alice@example.com"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert "id" in data
    assert "created_at" in data


def test_create_user_invalid(client):
    resp = client.post("/users", json={"username": 123, "email": "bad"})
    assert resp.status_code == 400


def test_create_user_missing_body(client):
    resp = client.post("/users", content_type="application/json")
    assert resp.status_code == 400


def test_create_user_missing_fields(client):
    resp = client.post("/users", json={"username": "only_name"})
    assert resp.status_code == 400
    assert "email" in resp.get_json()["error"]


def test_create_user_empty_username(client):
    resp = client.post("/users", json={"username": "  ", "email": "a@b.com"})
    assert resp.status_code == 400


def test_create_user_empty_email(client):
    resp = client.post("/users", json={"username": "valid", "email": "  "})
    assert resp.status_code == 400


def test_create_user_duplicate(client):
    client.post("/users", json={"username": "dup", "email": "dup@example.com"})
    resp = client.post("/users", json={"username": "dup", "email": "dup2@example.com"})
    assert resp.status_code == 409


def test_create_user_duplicate_email(client):
    client.post("/users", json={"username": "u_a", "email": "same@example.com"})
    resp = client.post("/users", json={"username": "u_b", "email": "same@example.com"})
    assert resp.status_code == 409


def test_list_users(client):
    client.post("/users", json={"username": "u1", "email": "u1@example.com"})
    client.post("/users", json={"username": "u2", "email": "u2@example.com"})
    resp = client.get("/users")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2


def test_list_users_pagination(client):
    for i in range(5):
        client.post("/users", json={"username": f"pg{i}", "email": f"pg{i}@x.com"})
    resp = client.get("/users?page=1&per_page=2")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2

    resp2 = client.get("/users?page=3&per_page=2")
    assert resp2.status_code == 200
    assert len(resp2.get_json()) == 1


def test_list_users_pagination_clamped(client):
    client.post("/users", json={"username": "clamp", "email": "clamp@x.com"})
    resp = client.get("/users?page=-1&per_page=0")
    assert resp.status_code == 200
    assert len(resp.get_json()) >= 1


def test_get_user_by_id(client):
    create_resp = client.post("/users", json={"username": "bob", "email": "bob@example.com"})
    uid = create_resp.get_json()["id"]
    resp = client.get(f"/users/{uid}")
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "bob"


def test_get_user_not_found(client):
    resp = client.get("/users/9999")
    assert resp.status_code == 404


def test_update_user(client):
    create_resp = client.post("/users", json={"username": "carol", "email": "carol@example.com"})
    uid = create_resp.get_json()["id"]
    resp = client.put(f"/users/{uid}", json={"username": "carol_updated"})
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "carol_updated"


def test_update_user_email(client):
    create_resp = client.post("/users", json={"username": "em", "email": "em@example.com"})
    uid = create_resp.get_json()["id"]
    resp = client.put(f"/users/{uid}", json={"email": "em_new@example.com"})
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "em_new@example.com"


def test_update_user_not_found(client):
    resp = client.put("/users/9999", json={"username": "ghost"})
    assert resp.status_code == 404


def test_update_user_no_body(client):
    cr = client.post("/users", json={"username": "nb", "email": "nb@x.com"})
    uid = cr.get_json()["id"]
    resp = client.put(f"/users/{uid}", content_type="application/json")
    assert resp.status_code == 400


def test_update_user_invalid_username(client):
    cr = client.post("/users", json={"username": "iv", "email": "iv@x.com"})
    uid = cr.get_json()["id"]
    resp = client.put(f"/users/{uid}", json={"username": ""})
    assert resp.status_code == 400


def test_update_user_invalid_email(client):
    cr = client.post("/users", json={"username": "ie", "email": "ie@x.com"})
    uid = cr.get_json()["id"]
    resp = client.put(f"/users/{uid}", json={"email": ""})
    assert resp.status_code == 400


def test_update_user_duplicate_conflict(client):
    client.post("/users", json={"username": "taken", "email": "taken@x.com"})
    cr = client.post("/users", json={"username": "free", "email": "free@x.com"})
    uid = cr.get_json()["id"]
    resp = client.put(f"/users/{uid}", json={"username": "taken"})
    assert resp.status_code == 409


def test_delete_user(client):
    cr = client.post("/users", json={"username": "del", "email": "del@x.com"})
    uid = cr.get_json()["id"]
    resp = client.delete(f"/users/{uid}")
    assert resp.status_code == 204
    assert client.get(f"/users/{uid}").status_code == 404


def test_delete_user_not_found(client):
    resp = client.delete("/users/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Users – Bulk
# ---------------------------------------------------------------------------


def test_bulk_load_users(client):
    csv_data = "username,email,created_at\nbulk1,bulk1@example.com,2025-01-01T00:00:00\nbulk2,bulk2@example.com,2025-01-02T00:00:00\n"
    data = {"file": (io.BytesIO(csv_data.encode()), "users.csv")}
    resp = client.post("/users/bulk", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.get_json()["count"] == 2


def test_bulk_load_no_file(client):
    resp = client.post("/users/bulk", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert "file" in resp.get_json()["error"].lower() or "No file" in resp.get_json()["error"]


def test_bulk_load_skips_empty_rows(client):
    csv_data = "username,email,created_at\n,empty@x.com,\nvalid,valid@x.com,2025-01-01T00:00:00\n"
    data = {"file": (io.BytesIO(csv_data.encode()), "users.csv")}
    resp = client.post("/users/bulk", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.get_json()["count"] == 1


def test_bulk_load_with_duplicates(client):
    client.post("/users", json={"username": "pre", "email": "pre@x.com"})
    csv_data = "username,email,created_at\npre,pre@x.com,2025-01-01T00:00:00\nnewguy,new@x.com,2025-01-01T00:00:00\n"
    data = {"file": (io.BytesIO(csv_data.encode()), "users.csv")}
    resp = client.post("/users/bulk", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.get_json()["count"] >= 1


# ---------------------------------------------------------------------------
# URLs – CRUD
# ---------------------------------------------------------------------------


def _make_user(client, name="owner"):
    return client.post("/users", json={"username": name, "email": f"{name}@x.com"}).get_json()["id"]


def test_create_url(client):
    uid = _make_user(client)
    resp = client.post("/urls", json={"user_id": uid, "original_url": "https://example.com", "title": "Test"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["original_url"] == "https://example.com"
    assert data["short_code"]
    assert data["is_active"] is True


def test_create_url_missing_user(client):
    resp = client.post("/urls", json={"user_id": 9999, "original_url": "https://example.com", "title": "Test"})
    assert resp.status_code == 404


def test_create_url_no_body(client):
    resp = client.post("/urls", content_type="application/json")
    assert resp.status_code == 400


def test_create_url_missing_user_id(client):
    resp = client.post("/urls", json={"original_url": "https://x.com"})
    assert resp.status_code == 400


def test_create_url_bad_user_id_type(client):
    resp = client.post("/urls", json={"user_id": "abc", "original_url": "https://x.com"})
    assert resp.status_code == 400


def test_create_url_empty_original_url(client):
    uid = _make_user(client, "emp")
    resp = client.post("/urls", json={"user_id": uid, "original_url": "  "})
    assert resp.status_code == 400


def test_create_url_title_defaults_empty(client):
    uid = _make_user(client, "notitle")
    resp = client.post("/urls", json={"user_id": uid, "original_url": "https://notitle.com"})
    assert resp.status_code == 201


def test_create_url_non_string_title(client):
    uid = _make_user(client, "badtitle")
    resp = client.post("/urls", json={"user_id": uid, "original_url": "https://x.com", "title": 42})
    assert resp.status_code == 201
    assert resp.get_json()["title"] == ""


def test_list_urls(client):
    uid = _make_user(client, "lister")
    client.post("/urls", json={"user_id": uid, "original_url": "https://a.com", "title": "A"})
    client.post("/urls", json={"user_id": uid, "original_url": "https://b.com", "title": "B"})
    resp = client.get("/urls")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2


def test_list_urls_filter_by_user(client):
    u1 = _make_user(client, "f1")
    u2 = _make_user(client, "f2")
    client.post("/urls", json={"user_id": u1, "original_url": "https://a.com", "title": "A"})
    client.post("/urls", json={"user_id": u2, "original_url": "https://b.com", "title": "B"})
    resp = client.get(f"/urls?user_id={u1}")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_list_urls_filter_is_active(client):
    uid = _make_user(client, "actfilter")
    r1 = client.post("/urls", json={"user_id": uid, "original_url": "https://a.com", "title": "A"})
    url_id = r1.get_json()["id"]
    client.post("/urls", json={"user_id": uid, "original_url": "https://b.com", "title": "B"})
    client.put(f"/urls/{url_id}", json={"is_active": False})

    active = client.get("/urls?is_active=true").get_json()
    inactive = client.get("/urls?is_active=false").get_json()
    assert len(active) == 1
    assert len(inactive) == 1


def test_get_url_by_id(client):
    uid = _make_user(client, "getter")
    url_resp = client.post("/urls", json={"user_id": uid, "original_url": "https://x.com", "title": "X"})
    url_id = url_resp.get_json()["id"]
    resp = client.get(f"/urls/{url_id}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "X"


def test_get_url_not_found(client):
    resp = client.get("/urls/9999")
    assert resp.status_code == 404


def test_update_url(client):
    uid = _make_user(client, "updater")
    url_resp = client.post("/urls", json={"user_id": uid, "original_url": "https://y.com", "title": "Y"})
    url_id = url_resp.get_json()["id"]
    resp = client.put(f"/urls/{url_id}", json={"title": "Updated", "is_active": False})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["is_active"] is False


def test_update_url_original_url(client):
    uid = _make_user(client, "upd_url")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://old.com", "title": "O"})
    url_id = r.get_json()["id"]
    resp = client.put(f"/urls/{url_id}", json={"original_url": "https://new.com"})
    assert resp.status_code == 200
    assert resp.get_json()["original_url"] == "https://new.com"


def test_update_url_not_found(client):
    resp = client.put("/urls/9999", json={"title": "ghost"})
    assert resp.status_code == 404


def test_update_url_no_body(client):
    uid = _make_user(client, "unb")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://x.com", "title": "X"})
    url_id = r.get_json()["id"]
    resp = client.put(f"/urls/{url_id}", content_type="application/json")
    assert resp.status_code == 400


def test_update_url_invalid_is_active(client):
    uid = _make_user(client, "boolbad")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://x.com", "title": "X"})
    url_id = r.get_json()["id"]
    resp = client.put(f"/urls/{url_id}", json={"is_active": "nope"})
    assert resp.status_code == 400


def test_update_url_empty_original_url(client):
    uid = _make_user(client, "emptyurl")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://x.com", "title": "X"})
    url_id = r.get_json()["id"]
    resp = client.put(f"/urls/{url_id}", json={"original_url": "  "})
    assert resp.status_code == 400


def test_delete_url(client):
    uid = _make_user(client, "delu")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://x.com", "title": "X"})
    url_id = r.get_json()["id"]
    resp = client.delete(f"/urls/{url_id}")
    assert resp.status_code == 204
    assert client.get(f"/urls/{url_id}").status_code == 404


def test_delete_url_not_found(client):
    resp = client.delete("/urls/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# URLs – Redirect
# ---------------------------------------------------------------------------


def test_redirect_short_code(client):
    from app.event_writer import flush_pending

    uid = _make_user(client, "rdr")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://rdr.com", "title": "R"})
    short = r.get_json()["short_code"]
    resp = client.get(f"/urls/{short}/redirect")
    assert resp.status_code == 302
    assert "rdr.com" in resp.headers["Location"]

    flush_pending()
    events = client.get("/events?event_type=redirect").get_json()
    assert len(events) >= 1


def test_redirect_not_found(client):
    resp = client.get("/urls/ZZZZZZ/redirect")
    assert resp.status_code == 404


def test_redirect_inactive_url(client):
    uid = _make_user(client, "inact")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://gone.com", "title": "G"})
    url_id = r.get_json()["id"]
    short = r.get_json()["short_code"]
    client.put(f"/urls/{url_id}", json={"is_active": False})
    resp = client.get(f"/urls/{short}/redirect")
    assert resp.status_code == 410


# ---------------------------------------------------------------------------
# Events – auto-created
# ---------------------------------------------------------------------------


def test_events_created_on_url_create(client):
    from app.event_writer import flush_pending

    uid = _make_user(client, "evtuser")
    client.post("/urls", json={"user_id": uid, "original_url": "https://evt.com", "title": "Evt"})
    flush_pending()
    resp = client.get("/events")
    assert resp.status_code == 200
    events = resp.get_json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "created"


def test_events_created_on_url_update(client):
    from app.event_writer import flush_pending

    uid = _make_user(client, "evtupd")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://evt2.com", "title": "E2"})
    url_id = r.get_json()["id"]
    client.put(f"/urls/{url_id}", json={"title": "Changed"})
    flush_pending()
    events = client.get("/events?event_type=updated").get_json()
    assert len(events) >= 1


# ---------------------------------------------------------------------------
# Events – CRUD
# ---------------------------------------------------------------------------


def test_create_event(client):
    uid = _make_user(client, "evtcr")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://e.com", "title": "E"})
    url_id = r.get_json()["id"]
    resp = client.post("/events", json={
        "url_id": url_id,
        "user_id": uid,
        "event_type": "custom",
        "details": {"key": "value"},
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["event_type"] == "custom"
    assert data["details"]["key"] == "value"


def test_create_event_no_body(client):
    resp = client.post("/events", content_type="application/json")
    assert resp.status_code == 400


def test_create_event_missing_fields(client):
    resp = client.post("/events", json={"url_id": 1})
    assert resp.status_code == 400


def test_create_event_bad_url_id(client):
    resp = client.post("/events", json={"url_id": "bad", "user_id": 1, "event_type": "x"})
    assert resp.status_code == 400


def test_create_event_bad_user_id(client):
    resp = client.post("/events", json={"url_id": 1, "user_id": "bad", "event_type": "x"})
    assert resp.status_code == 400


def test_create_event_empty_event_type(client):
    resp = client.post("/events", json={"url_id": 1, "user_id": 1, "event_type": ""})
    assert resp.status_code == 400


def test_create_event_url_not_found(client):
    uid = _make_user(client, "nourl")
    resp = client.post("/events", json={"url_id": 9999, "user_id": uid, "event_type": "x"})
    assert resp.status_code == 404


def test_create_event_user_not_found(client):
    uid = _make_user(client, "evtnu")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://x.com", "title": "X"})
    url_id = r.get_json()["id"]
    resp = client.post("/events", json={"url_id": url_id, "user_id": 9999, "event_type": "x"})
    assert resp.status_code == 404


def test_list_events_filter_by_url_id(client):
    uid = _make_user(client, "furl")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://f.com", "title": "F"})
    url_id = r.get_json()["id"]
    client.post("/events", json={"url_id": url_id, "user_id": uid, "event_type": "click"})
    resp = client.get(f"/events?url_id={url_id}")
    assert resp.status_code == 200
    for ev in resp.get_json():
        assert ev["url_id"] == url_id


def test_list_events_filter_by_user_id(client):
    uid = _make_user(client, "fuser")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://fu.com", "title": "FU"})
    url_id = r.get_json()["id"]
    client.post("/events", json={"url_id": url_id, "user_id": uid, "event_type": "test"})
    resp = client.get(f"/events?user_id={uid}")
    assert resp.status_code == 200
    for ev in resp.get_json():
        assert ev["user_id"] == uid


def test_list_events_filter_by_event_type(client):
    uid = _make_user(client, "ftype")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://ft.com", "title": "FT"})
    url_id = r.get_json()["id"]
    client.post("/events", json={"url_id": url_id, "user_id": uid, "event_type": "special"})
    resp = client.get("/events?event_type=special")
    assert resp.status_code == 200
    assert all(e["event_type"] == "special" for e in resp.get_json())


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


def test_404_returns_json(client):
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# Utils – encode_base62
# ---------------------------------------------------------------------------


def test_encode_base62_zero():
    from app.utils import encode_base62
    assert encode_base62(0) == "a"


def test_encode_base62_positive():
    from app.utils import encode_base62
    result = encode_base62(1)
    assert isinstance(result, str)
    assert len(result) >= 1


def test_encode_base62_large():
    from app.utils import encode_base62
    result = encode_base62(999999)
    assert isinstance(result, str)
    assert len(result) >= 1


def test_encode_base62_deterministic():
    from app.utils import encode_base62
    assert encode_base62(42) == encode_base62(42)


# ---------------------------------------------------------------------------
# Event writer – unit-level
# ---------------------------------------------------------------------------


def test_flush_pending_empty():
    from app.event_writer import flush_pending
    flush_pending()


def test_log_event_with_extra(client):
    from app.event_writer import log_event, flush_pending

    uid = _make_user(client, "extra")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://ex.com", "title": "EX"})
    url_id = r.get_json()["id"]
    log_event(url_id, uid, "custom_extra", short_code="abc", original_url="https://ex.com",
              extra={"browser": "Chrome"})
    flush_pending()
    events = client.get("/events?event_type=custom_extra").get_json()
    assert len(events) >= 1
    assert events[0]["details"]["browser"] == "Chrome"


# ---------------------------------------------------------------------------
# Delete user cascades URLs and events
# ---------------------------------------------------------------------------


def test_delete_user_cascades(client):
    from app.event_writer import flush_pending

    uid = _make_user(client, "cascade")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://c.com", "title": "C"})
    url_id = r.get_json()["id"]
    flush_pending()

    client.delete(f"/users/{uid}")

    assert client.get(f"/urls/{url_id}").status_code == 404


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_duplicate_url_same_user_returns_409(client):
    uid = _make_user(client, "twin")
    r1 = client.post("/urls", json={"user_id": uid, "original_url": "https://twin.com", "title": "T"})
    assert r1.status_code == 201
    r2 = client.post("/urls", json={"user_id": uid, "original_url": "https://twin.com", "title": "T again"})
    assert r2.status_code == 409
    assert r2.get_json()["short_code"] == r1.get_json()["short_code"]


def test_different_users_same_url_ok(client):
    u1 = _make_user(client, "twin_a")
    u2 = _make_user(client, "twin_b")
    r1 = client.post("/urls", json={"user_id": u1, "original_url": "https://shared.com", "title": "S"})
    r2 = client.post("/urls", json={"user_id": u2, "original_url": "https://shared.com", "title": "S"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.get_json()["short_code"] != r2.get_json()["short_code"]


def test_redirect_creates_event(client):
    from app.event_writer import flush_pending

    uid = _make_user(client, "observer")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://obs.com", "title": "O"})
    short = r.get_json()["short_code"]
    url_id = r.get_json()["id"]

    resp = client.get(f"/urls/{short}/redirect")
    assert resp.status_code == 302

    flush_pending()
    events = client.get(f"/events?url_id={url_id}&event_type=redirect").get_json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "redirect"


def test_inactive_redirect_no_event(client):
    uid = _make_user(client, "sleeper")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://sleep.com", "title": "Z"})
    url_id = r.get_json()["id"]
    short = r.get_json()["short_code"]
    client.put(f"/urls/{url_id}", json={"is_active": False})

    events_before = client.get(f"/events?url_id={url_id}&event_type=redirect").get_json()

    resp = client.get(f"/urls/{short}/redirect")
    assert resp.status_code == 410

    events_after = client.get(f"/events?url_id={url_id}&event_type=redirect").get_json()
    assert len(events_after) == len(events_before)


def test_array_body_rejected_users(client):
    resp = client.post("/users", data="[1,2,3]", content_type="application/json")
    assert resp.status_code == 400


def test_array_body_rejected_urls(client):
    resp = client.post("/urls", data="[1,2,3]", content_type="application/json")
    assert resp.status_code == 400


def test_array_body_rejected_events(client):
    resp = client.post("/events", data="[1,2,3]", content_type="application/json")
    assert resp.status_code == 400


def test_array_body_rejected_update_user(client):
    cr = client.post("/users", json={"username": "arr", "email": "arr@x.com"})
    uid = cr.get_json()["id"]
    resp = client.put(f"/users/{uid}", data="[1,2,3]", content_type="application/json")
    assert resp.status_code == 400


def test_array_body_rejected_update_url(client):
    uid = _make_user(client, "arr_url")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://arr.com", "title": "A"})
    url_id = r.get_json()["id"]
    resp = client.put(f"/urls/{url_id}", data="[1,2,3]", content_type="application/json")
    assert resp.status_code == 400


def test_event_details_rejects_string(client):
    uid = _make_user(client, "scroll")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://scr.com", "title": "S"})
    url_id = r.get_json()["id"]
    resp = client.post("/events", json={
        "url_id": url_id, "user_id": uid, "event_type": "trick",
        "details": "just a string",
    })
    assert resp.status_code == 400


def test_event_details_rejects_number(client):
    uid = _make_user(client, "numscr")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://ns.com", "title": "N"})
    url_id = r.get_json()["id"]
    resp = client.post("/events", json={
        "url_id": url_id, "user_id": uid, "event_type": "trick",
        "details": 42,
    })
    assert resp.status_code == 400


def test_event_details_rejects_array(client):
    uid = _make_user(client, "arrscr")
    r = client.post("/urls", json={"user_id": uid, "original_url": "https://as.com", "title": "A"})
    url_id = r.get_json()["id"]
    resp = client.post("/events", json={
        "url_id": url_id, "user_id": uid, "event_type": "trick",
        "details": [1, 2, 3],
    })
    assert resp.status_code == 400
