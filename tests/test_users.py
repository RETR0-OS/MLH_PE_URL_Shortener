"""Integration tests for /users endpoints."""

import io
import json


def _create_user(client, username="testuser", email="test@example.com"):
    return client.post(
        "/users",
        data=json.dumps({"username": username, "email": email}),
        content_type="application/json",
    )


class TestCreateUser:
    def test_success(self, client):
        resp = _create_user(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert "id" in data
        assert "created_at" in data

    def test_missing_fields(self, client):
        resp = client.post(
            "/users", data=json.dumps({}), content_type="application/json"
        )
        assert resp.status_code in (400, 422)

    def test_integer_username(self, client):
        resp = client.post(
            "/users",
            data=json.dumps({"username": 123, "email": "x@y.com"}),
            content_type="application/json",
        )
        assert resp.status_code in (400, 422)

    def test_duplicate_username(self, client):
        _create_user(client, "dup", "a@b.com")
        resp = _create_user(client, "dup", "c@d.com")
        assert resp.status_code in (400, 409, 422)

    def test_duplicate_email(self, client):
        _create_user(client, "u1", "same@e.com")
        resp = _create_user(client, "u2", "same@e.com")
        assert resp.status_code in (400, 409, 422)

    def test_invalid_email_format(self, client):
        resp = _create_user(client, "u", "not-an-email")
        assert resp.status_code in (400, 422)


class TestListUsers:
    def test_empty(self, client):
        resp = client.get("/users")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_array(self, client):
        _create_user(client, "a", "a@a.com")
        _create_user(client, "b", "b@b.com")
        data = client.get("/users").get_json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_pagination(self, client):
        for i in range(5):
            _create_user(client, f"u{i}", f"u{i}@x.com")
        page1 = client.get("/users?page=1&per_page=2").get_json()
        page2 = client.get("/users?page=2&per_page=2").get_json()
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0]["id"] != page2[0]["id"]


class TestGetUser:
    def test_found(self, client):
        cr = _create_user(client)
        uid = cr.get_json()["id"]
        resp = client.get(f"/users/{uid}")
        assert resp.status_code == 200
        assert resp.get_json()["id"] == uid

    def test_not_found(self, client):
        resp = client.get("/users/99999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestUpdateUser:
    def test_success(self, client):
        uid = _create_user(client).get_json()["id"]
        resp = client.put(
            f"/users/{uid}",
            data=json.dumps({"username": "updated"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "updated"

    def test_not_found(self, client):
        resp = client.put(
            "/users/99999",
            data=json.dumps({"username": "x"}),
            content_type="application/json",
        )
        assert resp.status_code == 404


class TestBulkLoadUsers:
    def test_csv_import(self, client):
        csv_data = "id,username,email,created_at\n1,bulk1,bulk1@x.com,2025-01-01 00:00:00\n2,bulk2,bulk2@x.com,2025-01-02 00:00:00\n"
        data = {"file": (io.BytesIO(csv_data.encode()), "users.csv")}
        resp = client.post("/users/bulk", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("count", body.get("imported")) == 2

    def test_empty_csv(self, client):
        csv_data = "id,username,email,created_at\n"
        data = {"file": (io.BytesIO(csv_data.encode()), "users.csv")}
        resp = client.post("/users/bulk", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("count", body.get("imported")) == 0

    def test_no_file(self, client):
        resp = client.post("/users/bulk", content_type="multipart/form-data")
        assert resp.status_code == 400

    def test_imported_users_queryable(self, client):
        csv_data = (
            "id,username,email,created_at\n10,seeded,seeded@x.com,2025-06-01 12:00:00\n"
        )
        data = {"file": (io.BytesIO(csv_data.encode()), "users.csv")}
        client.post("/users/bulk", data=data, content_type="multipart/form-data")
        resp = client.get("/users/10")
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "seeded"
