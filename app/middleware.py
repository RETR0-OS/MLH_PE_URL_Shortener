"""Request middleware: X-Request-ID propagation, structured logging, and checkpoint timing."""
import logging
import time
import uuid

from flask import g, request

logger = logging.getLogger("app.request")


def checkpoint(name):
    """Record a named timing checkpoint on the current request."""
    timings = getattr(g, "timings", None)
    if timings is None:
        return
    now = time.monotonic()
    elapsed = (now - g._last_checkpoint) * 1000
    g._last_checkpoint = now
    timings.append((name, round(elapsed, 3)))


def register_middleware(app):
    @app.before_request
    def _inject_request_id():
        now = time.monotonic()
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        g.request_start = now
        g._last_checkpoint = now
        g.timings = []
        checkpoint("middleware")

    @app.after_request
    def _log_request(response):
        checkpoint("after_request")
        total_ms = (time.monotonic() - g.get("request_start", 0)) * 1000
        response.headers["X-Request-ID"] = g.get("request_id", "")

        timings_dict = {name: ms for name, ms in getattr(g, "timings", [])}

        logger.info(
            "request",
            extra={
                "request_id": g.get("request_id"),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "latency_ms": round(total_ms, 2),
                "timings": timings_dict,
            },
        )
        return response
