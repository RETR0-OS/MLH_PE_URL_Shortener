"""Performance regression tests: ensure list endpoints don't have N+1 queries."""
import json
import logging


class QueryCounter:
    """Counts SQL queries executed by Peewee during a block."""

    def __init__(self):
        self.count = 0
        self._logger = logging.getLogger("peewee")
        self._handler = None

    def __enter__(self):
        self._handler = logging.Handler()
        self._handler.emit = lambda record: setattr(
            self, "count", self.count + 1
        )
        self._logger.addHandler(self._handler)
        self._logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc):
        if self._handler:
            self._logger.removeHandler(self._handler)


def _seed_data(client, n=5):
    """Create n users, each with a URL."""
    for i in range(n):
        user = client.post(
            "/users",
            data=json.dumps({"username": f"perf{i}", "email": f"perf{i}@x.com"}),
            content_type="application/json",
        ).get_json()
        client.post(
            "/urls",
            data=json.dumps(
                {"user_id": user["id"], "original_url": f"https://x.com/{i}", "title": f"T{i}"}
            ),
            content_type="application/json",
        )


class TestQueryBounds:
    def test_list_users_bounded(self, client):
        _seed_data(client, 10)
        with QueryCounter() as qc:
            client.get("/users")
        assert qc.count <= 3, f"GET /users fired {qc.count} queries (expected <=3)"

    def test_list_urls_bounded(self, client):
        _seed_data(client, 10)
        with QueryCounter() as qc:
            client.get("/urls")
        assert qc.count <= 3, f"GET /urls fired {qc.count} queries (expected <=3)"

    def test_list_events_bounded(self, client):
        _seed_data(client, 10)
        with QueryCounter() as qc:
            client.get("/events")
        assert qc.count <= 3, f"GET /events fired {qc.count} queries (expected <=3)"
