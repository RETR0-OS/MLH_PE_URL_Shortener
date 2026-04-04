import datetime
import json
import logging

logger = logging.getLogger(__name__)


def log_event(url_id, user_id, event_type, short_code="", original_url="", extra=None):
    from app.database import db
    from app.models.event import Event

    details = {"short_code": short_code, "original_url": original_url}
    if extra:
        details.update(extra)

    try:
        db.connect(reuse_if_open=True)
        Event.create(
            url_id=url_id,
            user_id=user_id,
            event_type=event_type,
            timestamp=datetime.datetime.now(),
            details=json.dumps(details),
        )
    except Exception:
        logger.exception("Failed to log event")


def flush_pending():
    """No-op. Kept for test compatibility."""
    pass
