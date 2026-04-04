import io
import json


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


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


def test_create_user_duplicate(client):
    client.post("/users", json={"username": "dup", "email": "dup@example.com"})
    resp = client.post("/users", json={"username": "dup", "email": "dup2@example.com"})
    assert resp.status_code == 409


def test_list_users(client):
    client.post("/users", json={"username": "u1", "email": "u1@example.com"})
    client.post("/users", json={"username": "u2", "email": "u2@example.com"})
    resp = client.get("/users")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2


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


def test_bulk_load_users(client):
    csv_data = "username,email,created_at\nbulk1,bulk1@example.com,2025-01-01T00:00:00\nbulk2,bulk2@example.com,2025-01-02T00:00:00\n"
    data = {"file": (io.BytesIO(csv_data.encode()), "users.csv")}
    resp = client.post("/users/bulk", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.get_json()["count"] == 2


def test_create_url(client):
    user_resp = client.post("/users", json={"username": "urlowner", "email": "urlowner@example.com"})
    uid = user_resp.get_json()["id"]
    resp = client.post("/urls", json={"user_id": uid, "original_url": "https://example.com", "title": "Test"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["original_url"] == "https://example.com"
    assert data["short_code"]
    assert data["is_active"] is True


def test_create_url_missing_user(client):
    resp = client.post("/urls", json={"user_id": 9999, "original_url": "https://example.com", "title": "Test"})
    assert resp.status_code == 404


def test_list_urls(client):
    user_resp = client.post("/users", json={"username": "lister", "email": "lister@example.com"})
    uid = user_resp.get_json()["id"]
    client.post("/urls", json={"user_id": uid, "original_url": "https://a.com", "title": "A"})
    client.post("/urls", json={"user_id": uid, "original_url": "https://b.com", "title": "B"})
    resp = client.get("/urls")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2


def test_list_urls_filter_by_user(client):
    u1 = client.post("/users", json={"username": "f1", "email": "f1@example.com"}).get_json()["id"]
    u2 = client.post("/users", json={"username": "f2", "email": "f2@example.com"}).get_json()["id"]
    client.post("/urls", json={"user_id": u1, "original_url": "https://a.com", "title": "A"})
    client.post("/urls", json={"user_id": u2, "original_url": "https://b.com", "title": "B"})
    resp = client.get(f"/urls?user_id={u1}")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_get_url_by_id(client):
    user_resp = client.post("/users", json={"username": "getter", "email": "getter@example.com"})
    uid = user_resp.get_json()["id"]
    url_resp = client.post("/urls", json={"user_id": uid, "original_url": "https://x.com", "title": "X"})
    url_id = url_resp.get_json()["id"]
    resp = client.get(f"/urls/{url_id}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "X"


def test_update_url(client):
    user_resp = client.post("/users", json={"username": "updater", "email": "updater@example.com"})
    uid = user_resp.get_json()["id"]
    url_resp = client.post("/urls", json={"user_id": uid, "original_url": "https://y.com", "title": "Y"})
    url_id = url_resp.get_json()["id"]
    resp = client.put(f"/urls/{url_id}", json={"title": "Updated", "is_active": False})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["is_active"] is False


def test_events_created_on_url_create(client):
    user_resp = client.post("/users", json={"username": "evtuser", "email": "evtuser@example.com"})
    uid = user_resp.get_json()["id"]
    client.post("/urls", json={"user_id": uid, "original_url": "https://evt.com", "title": "Evt"})
    resp = client.get("/events")
    assert resp.status_code == 200
    events = resp.get_json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "created"


def test_404_returns_json(client):
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    assert "error" in resp.get_json()
