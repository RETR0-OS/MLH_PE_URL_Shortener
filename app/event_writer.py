"""Fire-and-forget event writer using a background thread pool."""
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)


def _write_event(payload):
    try:
        from app.database import db
        from app.models.event import Event

        db.connect(reuse_if_open=True)
        Event.create(**payload)
    except Exception:
        logger.exception("Failed to log event")


def log_event(url_id, user_id, event_type, details=None):
    payload = {
        "url_id": url_id,
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": datetime.datetime.now(datetime.UTC).replace(tzinfo=None),
        "details": details or {},
    }
    _executor.submit(_write_event, payload)
