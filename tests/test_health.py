"""Tests for health/readiness endpoints."""


class TestHealth:
    def test_liveness(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}

    def test_readiness(self, client):
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
