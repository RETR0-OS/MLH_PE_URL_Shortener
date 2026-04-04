import atexit
import datetime
import json
import logging
import queue
import threading
import time

logger = logging.getLogger(__name__)

_queue = queue.Queue()
_BATCH_SIZE = 50
_FLUSH_INTERVAL = 0.5
_shutdown = threading.Event()
_SENTINEL = "FLUSH"


def _flush(batch):
    if not batch:
        return
    try:
        from app.database import db
        from app.models.event import Event

        db.connect(reuse_if_open=True)
        with db.atomic():
            Event.insert_many(batch).execute()
    except Exception:
        logger.exception("Failed to flush %d events", len(batch))


def _writer_loop():
    batch = []
    while not _shutdown.is_set():
        try:
            item = _queue.get(timeout=_FLUSH_INTERVAL)
            if item is _SENTINEL:
                _flush(batch)
                batch = []
                continue
            batch.append(item)
            if len(batch) >= _BATCH_SIZE:
                _flush(batch)
                batch = []
        except queue.Empty:
            _flush(batch)
            batch = []
    while not _queue.empty():
        try:
            item = _queue.get_nowait()
            if item is not _SENTINEL:
                batch.append(item)
        except queue.Empty:
            break
    _flush(batch)


_writer_thread = threading.Thread(target=_writer_loop, daemon=True)
_writer_thread.start()


def _shutdown_writer():
    _shutdown.set()
    _writer_thread.join(timeout=5)


atexit.register(_shutdown_writer)


def _build_payload(url_id, user_id, event_type, short_code, original_url, extra):
    details = {"short_code": short_code, "original_url": original_url}
    if extra:
        details.update(extra)
    return {
        "url_id": url_id,
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": datetime.datetime.now(),
        "details": json.dumps(details),
    }


def log_event(url_id, user_id, event_type, short_code="", original_url="", extra=None):
    from app.database import _testing

    payload = _build_payload(url_id, user_id, event_type, short_code, original_url, extra)

    if _testing:
        from app.models.event import Event
        Event.create(**payload)
    else:
        _queue.put(payload)


def flush_pending():
    """Force-flush and wait for all queued events to be written."""
    _queue.put(_SENTINEL)
    time.sleep(_FLUSH_INTERVAL + 0.3)
