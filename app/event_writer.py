import datetime
import json
import logging
from concurrent.futures import ThreadPoolExecutor, Future

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)
_futures: list[Future] = []


def _write_event(payload):
    try:
        from app.database import db
        from app.models.event import Event

        db.connect(reuse_if_open=True)
        Event.create(**payload)
    except Exception:
        logger.exception("Failed to log event")


def log_event(url_id, user_id, event_type, short_code="", original_url="", extra=None):
    details = {"short_code": short_code, "original_url": original_url}
    if extra:
        details.update(extra)
    payload = {
        "url_id": url_id,
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": datetime.datetime.now(),
        "details": json.dumps(details),
    }
    fut = _executor.submit(_write_event, payload)
    _futures.append(fut)


def flush_pending():
    """Wait for all in-flight event writes to finish. Used by tests."""
    for fut in _futures:
        fut.result(timeout=5)
    _futures.clear()
