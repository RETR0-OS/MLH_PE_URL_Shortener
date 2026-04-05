"""Performance regression tests: ensure list endpoints don't have N+1 queries."""

import json
import logging


class QueryCounter:
    """Counts SELECT queries executed by Peewee during a block.

    Only counts SELECTs to avoid false positives from background
    thread writes (event_writer) hitting the shared peewee logger.
    """

    def __init__(self):
        self.count = 0
        self._logger = logging.getLogger("peewee")
        self._handler = None

    def _on_emit(self, record):
        msg = str(getattr(record, "msg", ""))
        if "SELECT" in msg:
            self.count += 1

    def __enter__(self):
        self._handler = logging.Handler()
        self._handler.emit = self._on_emit
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
                {
                    "user_id": user["id"],
                    "original_url": f"https://x.com/{i}",
                    "title": f"T{i}",
                }
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
        assert qc.count <= 4, f"GET /events fired {qc.count} queries (expected <=4)"
