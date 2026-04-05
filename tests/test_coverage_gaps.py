"""Tests targeting every uncovered line for 100% coverage."""

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# app/__init__.py  —  lines 44-45  (health_ready DB failure)
# ---------------------------------------------------------------------------
class TestHealthReadyFailure:
    def test_readiness_503_when_db_down(self, client):
        from app.database import db

        original = db.obj.execute_sql

        def _bomb(*a, **kw):
            raise Exception("conn refused")

        db.obj.execute_sql = _bomb
        try:
            resp = client.get("/health/ready")
            assert resp.status_code == 503
            assert resp.get_json()["status"] == "unavailable"
        finally:
            db.obj.execute_sql = original


# ---------------------------------------------------------------------------
# app/__init__.py  —  line 53  (405 handler)
# ---------------------------------------------------------------------------
class TestMethodNotAllowed:
    def test_delete_on_users_returns_405(self, client):
        resp = client.delete("/users")
        assert resp.status_code == 405
        assert resp.get_json()["error"] == "Method not allowed"


# ---------------------------------------------------------------------------
# app/__init__.py  —  line 57  (500 handler)
#   Flask's TESTING mode propagates exceptions; temporarily disable that.
# ---------------------------------------------------------------------------
class TestInternalServerError:
    def test_unhandled_exception_returns_500_json(self, app, client):
        app.config["PROPAGATE_EXCEPTIONS"] = False
        try:
            with patch(
                "app.routes.users.User.select", side_effect=RuntimeError("boom")
            ):
                resp = client.get("/users")
                assert resp.status_code == 500
                assert resp.get_json()["error"] == "Internal server error"
        finally:
            app.config.pop("PROPAGATE_EXCEPTIONS", None)


# ---------------------------------------------------------------------------
# app/database.py  —  line 19  (Docker secret read)
# ---------------------------------------------------------------------------
class TestDockerSecretRead:
    def test_read_secret_from_file(self):
        from app.utils.secrets import read_secret

        with patch("app.utils.secrets.Path") as MockPath:
            mock_instance = MagicMock()
            mock_instance.exists.return_value = True
            mock_instance.read_text.return_value = "  my_secret_value  \n"
            MockPath.return_value = mock_instance
            result = read_secret("test_secret", "default")
            assert result == "my_secret_value"


# ---------------------------------------------------------------------------
# app/database.py  —  lines 52-53  (init_db_standalone)
#   Must save/restore the proxy's underlying database to avoid corrupting
#   the connection for subsequent tests.
# ---------------------------------------------------------------------------
class TestInitDbStandalone:
    def test_init_db_standalone_initialises_proxy(self):
        from app.database import db, init_db_standalone

        saved_obj = db.obj
        try:
            with patch("app.database._create_database") as mock_create:
                mock_db = MagicMock()
                mock_create.return_value = mock_db
                init_db_standalone()
                mock_create.assert_called_once_with(max_connections=4)
        finally:
            db.initialize(saved_obj)


# ---------------------------------------------------------------------------
# app/routes/users.py  —  structural errors, field-level validation, integrity
# ---------------------------------------------------------------------------
class TestUserStructuralErrors:
    def test_create_user_no_json_body(self, client):
        resp = client.post("/users", data="not json", content_type="text/plain")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_update_user_no_json_body(self, client):
        user = client.post(
            "/users",
            data=json.dumps({"username": "ub", "email": "ub@x.com"}),
            content_type="application/json",
        ).get_json()
        resp = client.put(
            f"/users/{user['id']}", data="not json", content_type="text/plain"
        )
        assert resp.status_code == 400

    def test_update_user_invalid_email(self, client):
        user = client.post(
            "/users",
            data=json.dumps({"username": "uf", "email": "uf@x.com"}),
            content_type="application/json",
        ).get_json()
        resp = client.put(
            f"/users/{user['id']}",
            data=json.dumps({"email": "bad-email"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_update_user_email_success(self, client):
        user = client.post(
            "/users",
            data=json.dumps({"username": "ue", "email": "ue@x.com"}),
            content_type="application/json",
        ).get_json()
        resp = client.put(
            f"/users/{user['id']}",
            data=json.dumps({"email": "ue_new@x.com"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["email"] == "ue_new@x.com"

    def test_update_user_duplicate_username(self, client):
        client.post(
            "/users",
            data=json.dumps({"username": "uA", "email": "uA@x.com"}),
            content_type="application/json",
        )
        u2 = client.post(
            "/users",
            data=json.dumps({"username": "uB", "email": "uB@x.com"}),
            content_type="application/json",
        ).get_json()
        resp = client.put(
            f"/users/{u2['id']}",
            data=json.dumps({"username": "uA"}),
            content_type="application/json",
        )
        assert resp.status_code == 422
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# app/routes/urls.py  —  structural errors, short-code exhaustion, integrity
# ---------------------------------------------------------------------------
class TestUrlStructuralErrors:
    def _seed_user(self, client):
        return client.post(
            "/users",
            data=json.dumps({"username": "us", "email": "us@x.com"}),
            content_type="application/json",
        ).get_json()["id"]

    def test_create_url_no_json_body(self, client):
        resp = client.post("/urls", data="not json", content_type="text/plain")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_update_url_no_json_body(self, client):
        uid = self._seed_user(client)
        url_id = client.post(
            "/urls",
            data=json.dumps(
                {"user_id": uid, "original_url": "https://x.com", "title": "T"}
            ),
            content_type="application/json",
        ).get_json()["id"]
        resp = client.put(f"/urls/{url_id}", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_update_url_bad_is_active_type(self, client):
        uid = self._seed_user(client)
        url_id = client.post(
            "/urls",
            data=json.dumps(
                {"user_id": uid, "original_url": "https://x.com", "title": "T"}
            ),
            content_type="application/json",
        ).get_json()["id"]
        resp = client.put(
            f"/urls/{url_id}",
            data=json.dumps({"is_active": "yes"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_short_code_exhaustion(self, client):
        uid = self._seed_user(client)
        first = client.post(
            "/urls",
            data=json.dumps(
                {"user_id": uid, "original_url": "https://x.com", "title": "T"}
            ),
            content_type="application/json",
        ).get_json()
        existing_code = first["short_code"]
        with patch("app.routes.urls.generate_short_code", return_value=existing_code):
            resp = client.post(
                "/urls",
                data=json.dumps(
                    {"user_id": uid, "original_url": "https://y.com", "title": "T2"}
                ),
                content_type="application/json",
            )
            assert resp.status_code == 500
            assert "short code" in resp.get_json()["error"].lower()

    def test_create_url_integrity_error(self, client):
        uid = self._seed_user(client)
        from peewee import IntegrityError as PeeweeIntegrityError

        with patch(
            "app.routes.urls.Url.create",
            side_effect=PeeweeIntegrityError("dup short_code"),
        ):
            resp = client.post(
                "/urls",
                data=json.dumps(
                    {"user_id": uid, "original_url": "https://x.com", "title": "T"}
                ),
                content_type="application/json",
            )
            assert resp.status_code == 500
            assert "error" in resp.get_json()

    def test_update_url_integrity_error(self, client):
        uid = self._seed_user(client)
        url_id = client.post(
            "/urls",
            data=json.dumps(
                {"user_id": uid, "original_url": "https://x.com", "title": "T"}
            ),
            content_type="application/json",
        ).get_json()["id"]
        from peewee import IntegrityError as PeeweeIntegrityError

        with patch(
            "app.routes.urls.Url.save",
            side_effect=PeeweeIntegrityError("dup"),
        ):
            resp = client.put(
                f"/urls/{url_id}",
                data=json.dumps({"title": "New"}),
                content_type="application/json",
            )
            assert resp.status_code == 422


# ---------------------------------------------------------------------------
# app/utils/validation.py  —  lines 37-38, 45, 57, 62, 69
# ---------------------------------------------------------------------------
class TestValidationMissingBranches:
    def test_update_user_invalid_email_format(self):
        from app.utils.validation import validate_user_update

        errs = validate_user_update({"email": "not-valid"})
        assert "email" in errs

    def test_update_user_integer_email(self):
        from app.utils.validation import validate_user_update

        errs = validate_user_update({"email": 42})
        assert "email" in errs

    def test_create_url_none_body(self):
        from app.utils.validation import validate_url_create

        result = validate_url_create(None)
        assert "error" in result

    def test_create_url_empty_original_url(self):
        from app.utils.validation import validate_url_create

        errs = validate_url_create({"user_id": 1, "original_url": "   ", "title": "T"})
        assert "original_url" in errs

    def test_create_url_non_string_title(self):
        from app.utils.validation import validate_url_create

        errs = validate_url_create(
            {"user_id": 1, "original_url": "https://x.com", "title": 123}
        )
        assert "title" in errs

    def test_update_url_none_body(self):
        from app.utils.validation import validate_url_update

        result = validate_url_update(None)
        assert "error" in result


# ---------------------------------------------------------------------------
# app/utils/cache.py  —  Redis mocked for all connected-path lines
# ---------------------------------------------------------------------------
class TestCacheWithMockedRedis:
    @pytest.fixture(autouse=True)
    def _reset_cache_module(self):
        """Reset module-level state before each test."""
        import app.utils.cache as cache_mod

        cache_mod._redis_client = None
        cache_mod._circuit_open = False
        cache_mod._circuit_open_until = 0.0
        yield
        cache_mod._redis_client = None
        cache_mod._circuit_open = False
        cache_mod._circuit_open_until = 0.0

    def _make_mock_redis(self):
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = None
        mock_redis.keys.return_value = []
        return mock_redis

    def test_get_redis_connects(self):
        import app.utils.cache as cache_mod

        mock_redis_instance = self._make_mock_redis()
        with patch("redis.Redis", return_value=mock_redis_instance):
            result = cache_mod.get_redis()
            assert result is mock_redis_instance

    def test_get_redis_returns_cached_client(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        cache_mod._redis_client = mock
        result = cache_mod.get_redis()
        assert result is mock

    def test_circuit_resets_after_timeout(self):
        import app.utils.cache as cache_mod

        cache_mod._circuit_open = True
        cache_mod._circuit_open_until = 0.0
        mock = self._make_mock_redis()
        cache_mod._redis_client = mock
        result = cache_mod.get_redis()
        assert result is mock
        assert cache_mod._circuit_open is False

    def test_cache_get_hit(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        mock.get.return_value = '{"id": 1}'
        cache_mod._redis_client = mock
        result = cache_mod.cache_get("url:1")
        assert result == {"id": 1}

    def test_cache_get_miss(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        mock.get.return_value = None
        cache_mod._redis_client = mock
        result = cache_mod.cache_get("url:999")
        assert result is None

    def test_cache_get_redis_error(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        mock.get.side_effect = Exception("conn lost")
        cache_mod._redis_client = mock
        result = cache_mod.cache_get("url:1")
        assert result is None
        assert cache_mod._circuit_open is True

    def test_cache_set_success(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        cache_mod._redis_client = mock
        cache_mod.cache_set("url:1", {"id": 1})
        mock.set.assert_called_once()

    def test_cache_set_redis_error(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        mock.set.side_effect = Exception("write fail")
        cache_mod._redis_client = mock
        cache_mod.cache_set("url:1", {"id": 1})
        assert cache_mod._circuit_open is True

    def test_cache_delete_success(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        cache_mod._redis_client = mock
        cache_mod.cache_delete("url:1")
        mock.delete.assert_called_once_with("url:1")

    def test_cache_delete_redis_error(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        mock.delete.side_effect = Exception("del fail")
        cache_mod._redis_client = mock
        cache_mod.cache_delete("url:1")
        assert cache_mod._circuit_open is True

    def test_cache_delete_pattern_with_keys(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        mock_pipe = MagicMock()
        mock.pipeline.return_value = mock_pipe
        mock.scan.return_value = (0, ["urls:user:1", "urls:user:2"])
        cache_mod._redis_client = mock
        cache_mod.cache_delete_pattern("urls:user:*")
        assert mock_pipe.delete.call_count == 2
        mock_pipe.execute.assert_called_once()

    def test_cache_delete_pattern_no_keys(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        mock_pipe = MagicMock()
        mock.pipeline.return_value = mock_pipe
        mock.scan.return_value = (0, [])
        cache_mod._redis_client = mock
        cache_mod.cache_delete_pattern("urls:user:*")
        mock_pipe.delete.assert_not_called()
        mock_pipe.execute.assert_called_once()

    def test_cache_delete_pattern_redis_error(self):
        import app.utils.cache as cache_mod

        mock = self._make_mock_redis()
        mock.keys.side_effect = Exception("pattern fail")
        cache_mod._redis_client = mock
        cache_mod.cache_delete_pattern("urls:user:*")
        assert cache_mod._circuit_open is True

    def test_cache_read_secret_from_file(self):
        import app.utils.secrets as secrets_mod

        with patch.object(secrets_mod, "Path") as MockPath:
            mock_instance = MagicMock()
            mock_instance.exists.return_value = True
            mock_instance.read_text.return_value = "  secret_val  \n"
            MockPath.return_value = mock_instance
            result = secrets_mod.read_secret("redis_password", "default")
            assert result == "secret_val"

    def test_url_get_cache_hit(self, client):
        user = client.post(
            "/users",
            data=json.dumps({"username": "ch", "email": "ch@x.com"}),
            content_type="application/json",
        ).get_json()
        url = client.post(
            "/urls",
            data=json.dumps(
                {
                    "user_id": user["id"],
                    "original_url": "https://x.com",
                    "title": "T",
                }
            ),
            content_type="application/json",
        ).get_json()

        fake_cached = url.copy()
        with patch("app.routes.urls.cache_get", return_value=fake_cached):
            resp = client.get(f"/urls/{url['id']}")
            assert resp.status_code == 200
            assert resp.get_json()["id"] == url["id"]
