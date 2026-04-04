"""Request middleware: X-Request-ID propagation and structured request logging."""
import logging
import time
import uuid

from flask import g, request

logger = logging.getLogger("app.request")


def register_middleware(app):
    @app.before_request
    def _inject_request_id():
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        g.request_start = time.monotonic()

    @app.after_request
    def _log_request(response):
        latency_ms = (time.monotonic() - g.get("request_start", 0)) * 1000
        response.headers["X-Request-ID"] = g.get("request_id", "")
        logger.info(
            "request",
            extra={
                "request_id": g.get("request_id"),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "latency_ms": round(latency_ms, 2),
            },
        )
        return response
